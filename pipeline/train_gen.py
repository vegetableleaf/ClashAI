"""Generalist trainer: ``dataset_gen`` npz -> ``GenModel`` checkpoint + per-epoch metrics json.

    python -m pipeline.train_gen --data icebow/data/pipeline/gen_dataset_starter.npz --seed 0 --epochs 16 \
        --out-dir scratchpad/gauntlet/L68/generalist/run_s0 --grid lattice [--limit-rows N] [--deck-weighting sqrt]

Mirrors ``train_s1`` (AdamW lr 3e-4, wd 0.01, OneCycle pct 0.05, bs 256, grad clip 1.0, mirror p = 0.5, same loss
weights): cell CE on PLAY rows teacher-forced on the pro's card IDENTITY, card CE over the 4 hand positions on PLAY
rows, gate BCE on all rows, 0.5 x wait CE (pointer over the 8 deck cards) on WAIT rows, 0.5 x crown-diff CE on all
rows (card / wait: rows with no valid target are excluded, and a head with none in the batch contributes 0).
Each epoch scores the FULL v3val rows (the S1-comparable instrument) and a FIXED seed-0 sample of ``--val-sample`` all-deck
val rows (default 30,000; ids recorded in the history json); checkpoint = best ``--select`` metric (S1's default
cell_tile_top1) on that sample, written to ``--out-dir/gen[_tag]_s<seed>.pt`` with S1's layout + ``gen`` /
``card_vocab`` / ``d_c``.
``--limit-rows N``: a seeded random N of the TRAIN rows (v3val is always complete).
``--deck-weighting sqrt``: each epoch draws len(train) rows WITH replacement, row weight 1 / sqrt(train rows of its
deck), so a deck's share goes as sqrt(its rows) instead of its rows (icebow/hogeq sides dominate the starter).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

from .dataset import load as load_ds
from .eval_gen import GenRows as LegacyGenRows, evaluate, val_rows
from .model_gen import GenModel, mirror_gen, slot_nll
from .model_v3 import cell_label

REPO = Path(__file__).resolve().parents[1]


# P2-OPP1 row columns: row_w (wait-slot subsampling weight), card_ok (0 = hand inferred: no card label), slot_ok /
# slot_ev / slot_tick (the timing head's 10-tick slot rows), ab_ok / ab_ev / ab_tick (ability press), deck_gid, ctx_*
OPP_ROW_KEYS = ("row_w", "card_ok", "slot_ok", "slot_ev", "slot_tick", "ab_ok", "ab_ev", "ab_tick", "deck_gid",
                "ctx_band", "ctx_mode", "ctx_era")


class GenRows(LegacyGenRows):
    """Versioned batching; legacy datasets take the original batch path unchanged."""
    def __init__(self, arrs, idx, device):
        super().__init__(arrs, idx, device)
        self.unit_form = torch.as_tensor(arrs["unit_form"], dtype=torch.long) if "unit_form" in arrs else None
        self.opp_past = torch.as_tensor(arrs["opp_past"], device=device) if "opp_past" in arrs else None
        # P2-OPP1 per-row columns (rows_to_npz / slot rows); absent in every legacy dataset = no extra batch key
        self.opp_extra = {k: torch.as_tensor(np.asarray(arrs[k])).to(device) for k in OPP_ROW_KEYS if k in arrs}

    def batch(self, ids):
        b = super().batch(ids)
        if self.opp_extra:
            t = torch.as_tensor(np.asarray(ids), device=self.dev)
            b.update({k: v[t] for k, v in self.opp_extra.items()})
        if self.unit_form is not None:
            from .train_s1 import MAX_U
            ids = np.asarray(ids)
            src = torch.from_numpy(self.off[ids, None] + np.arange(MAX_U)[None, :])
            if len(self.unit_form):
                f = self.unit_form[src.clamp(max=len(self.unit_form) - 1)].to(self.dev)
            else:
                f = torch.zeros(src.shape, dtype=torch.long, device=self.dev)
            b["unit_form"] = f.masked_fill(~b["mask"], 0)
            b["opp_past"] = self.opp_past[torch.as_tensor(ids, device=self.dev)]
        return b


def _ce(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Cross-entropy over the rows with a real target (>= 0); exactly 0 when there are none (a plain
    ``ignore_index=-1`` mean is 0/0 = NaN there, and -inf pad logits make ``logits.sum() * 0`` NaN too)."""
    ok = target >= 0
    return Fn.cross_entropy(logits[ok], target[ok]) if ok.any() else logits.new_zeros(())


def losses(model: GenModel, b: dict, mirror: bool, grid: str = "floor", rocket_context_weight: float = 1.0,
           heads=None) -> tuple[torch.Tensor, dict]:
    """``heads``: the loss terms summed into the returned loss (None = all: cell, card, wait, gate, value -- unchanged);
    the parts dict always reports every term (Plan A S3 trains the memory adapter on gate / card / cell only)."""
    total, parts = _losses(model, b, mirror, grid, rocket_context_weight)
    use = parts if heads is None else {k: v for k, v in parts.items() if k in heads}
    return (sum(use.values()) if use else total * 0.0), {k: float(v.detach()) for k, v in parts.items()}


def _mirrored(model: GenModel, b: dict, mirror: bool):
    """The batch as the model sees it (left-right mirrored when ``mirror``) -> (tok, sc, past, xy, b)."""
    tok, sc, past, xy = b["tok"], b["sc"], b["past"], b["xy"]
    if mirror:
        tok, sc, past, xy = mirror_gen(tok, sc, past, xy)
    if mirror and "opp_past" in b:
        op = b["opp_past"].clone()
        op[..., 2] = torch.where(op[..., 0] > 0, 1 - op[..., 2], op[..., 2])
        b = dict(b, opp_past=op)
    if mirror and 'projectiles' in b:
        b = dict(b)
        for key, xcols in (('projectiles', (2, 4)), ('effects', (2,))):
            obj = b[key].clone()
            for col in xcols:
                known = obj[..., 0] > 0
                if getattr(model, 'feature_version', 1) >= 6 and key == 'projectiles' and col == 4:
                    known = known & (obj[..., 4] >= 0) & (obj[..., 5] >= 0)
                obj[..., col] = torch.where(known, 1-obj[..., col], obj[..., col])
            b[key] = obj
    if mirror and "mem_ev" in b:                         # Plan A memory v1: events' own-frame x and tower lane mirrored too
        from .match_memory import mirror_ev
        b = dict(b, mem_ev=mirror_ev(b["mem_ev"]))
    return tok, sc, past, xy, b


def _losses(model: GenModel, b: dict, mirror: bool, grid: str = "floor", rocket_context_weight: float = 1.0):
    if getattr(model, "opp", None) and (model.opp["timing"] or model.opp["ability"]):
        return opp_losses(model, b, mirror, grid)
    tok, sc, past, xy, b = _mirrored(model, b, mirror)
    play = b["gate"] > 0.5
    out = model(dict(b, tok=tok, sc=sc, past=past), card=b["card"], form=b["form"])
    parts = {}
    if rocket_context_weight != 1.0:
        from .rocket_context import row_weights, mean_loss, weighted_ce
        weights = row_weights(b['rocket_context_probability'], rocket_context_weight)
        if play.any():
            parts['cell'] = weighted_ce(out['cell'][play], cell_label(xy[play], grid), weights[play])
            parts['card'] = weighted_ce(out['card'][play], b['slot'][play], weights[play])
        if (~play).any():
            parts['wait'] = .5*weighted_ce(out['wait'][~play], b['wait'][~play], weights[~play])
        parts['gate'] = mean_loss(Fn.binary_cross_entropy_with_logits(out['gate'], b['gate'], reduction='none'), weights)
        parts['value'] = .5*weighted_ce(out['value'], b['value'], weights)
        return sum(parts.values()), parts
    if play.any():
        parts["cell"] = Fn.cross_entropy(out["cell"][play], cell_label(xy[play], grid))
        parts["card"] = _ce(out["card"][play], b["slot"][play])
    if (~play).any():
        parts["wait"] = 0.5 * _ce(out["wait"][~play], b["wait"][~play])
    parts["gate"] = Fn.binary_cross_entropy_with_logits(out["gate"], b["gate"])
    parts["value"] = 0.5 * Fn.cross_entropy(out["value"], b["value"])
    return sum(parts.values()), parts


def _wmean(x: torch.Tensor, w: torch.Tensor) -> torch.Tensor:
    return (x * w).sum() / w.sum() if len(x) and float(w.sum()) > 0 else x.new_zeros(())


def opp_losses(model: GenModel, b: dict, mirror: bool, grid: str = "lattice"):
    """P2-OPP1 loss (a model with the timing and / or ability head). cell = CE on play rows; card = CE on play rows with
    a known hand (``card_ok``); wait = 0.5 x CE on wait rows; timing = the per-slot survival NLL (model_gen.slot_nll)
    on slot rows; ability = the same for the press head; value = 0.5 x CE. Every term but cell / card is a ``row_w``
    weighted mean (no-play slots kept at 1/k carry weight k, so the timing sum stays the exact likelihood)."""
    tok, sc, past, xy, b = _mirrored(model, b, mirror)
    out = model(dict(b, tok=tok, sc=sc, past=past), card=b["card"], form=b["form"])
    w = b["row_w"].float() if "row_w" in b else torch.ones_like(b["gate"])
    play = b["gate"] > 0.5
    parts = {}
    if play.any():
        parts["cell"] = Fn.cross_entropy(out["cell"][play], cell_label(xy[play], grid))
        cok = play & (b["card_ok"] > 0) if "card_ok" in b else play
        parts["card"] = _ce(out["card"][cok], b["slot"][cok])
    wr = ~play & (b["wait"] >= 0)
    if wr.any():
        parts["wait"] = 0.5 * _wmean(Fn.cross_entropy(out["wait"][wr], b["wait"][wr], reduction="none"), w[wr])
    if "hazard" in out:
        s = b["slot_ok"] > 0
        parts["timing"] = _wmean(slot_nll(out["hazard"][s], out["tick"][s], b["slot_ev"][s], b["slot_tick"][s]), w[s])
    if "ab_hazard" in out and "ab_ok" in b:
        s = b["ab_ok"] > 0
        parts["ability"] = _wmean(slot_nll(out["ab_hazard"][s], out["ab_tick"][s], b["ab_ev"][s], b["ab_tick"][s]), w[s])
    parts["value"] = 0.5 * _wmean(Fn.cross_entropy(out["value"], b["value"], reduction="none"), w)
    return sum(parts.values()), parts


@torch.no_grad()
def evaluate_opp(model: GenModel, rows: "GenRows", bs: int = 512, grid: str = "lattice") -> dict:
    """Held-out NLL per head (the opp_losses definitions, summed over rows, no mirror, eval mode) + top-1 card / cell.
    ``total`` = cell + card + timing + ability + 0.5 wait + 0.5 value (the training weights)."""
    model.eval()
    acc = dict.fromkeys(("cell", "card", "wait", "timing", "tick", "ability", "value", "cell_top1", "card_top1", "n_cell",
                         "n_card", "w_wait", "w_slot", "n_ev", "w_ab", "w_all", "hz_sum", "ev_sum"), 0.0)
    for s0 in range(0, len(rows.idx), bs):
        b = rows.batch(rows.idx[s0:s0 + bs])
        out = model(b, card=b["card"], form=b["form"])
        w = b["row_w"].float() if "row_w" in b else torch.ones_like(b["gate"])
        play = b["gate"] > 0.5
        if play.any():
            lab = cell_label(b["xy"][play], grid)
            acc["cell"] += float(Fn.cross_entropy(out["cell"][play].float(), lab, reduction="sum"))
            acc["cell_top1"] += float((out["cell"][play].argmax(-1) == lab).sum())
            acc["n_cell"] += int(play.sum())
            cok = (play & (b["card_ok"] > 0) if "card_ok" in b else play) & (b["slot"] >= 0)
            if cok.any():
                acc["card"] += float(Fn.cross_entropy(out["card"][cok].float(), b["slot"][cok], reduction="sum"))
                acc["card_top1"] += float((out["card"][cok].argmax(-1) == b["slot"][cok]).sum())
                acc["n_card"] += int(cok.sum())
        wr = ~play & (b["wait"] >= 0)
        if wr.any():
            acc["wait"] += float((Fn.cross_entropy(out["wait"][wr].float(), b["wait"][wr], reduction="none") * w[wr]).sum())
            acc["w_wait"] += float(w[wr].sum())
        if "hazard" in out:
            s = b["slot_ok"] > 0
            if s.any():
                hz, tk = out["hazard"][s].float(), out["tick"][s].float()
                acc["timing"] += float((slot_nll(hz, tk, b["slot_ev"][s], b["slot_tick"][s]) * w[s]).sum())
                acc["w_slot"] += float(w[s].sum())
                acc["hz_sum"] += float((torch.sigmoid(hz) * w[s]).sum())
                acc["ev_sum"] += float((b["slot_ev"][s].float() * w[s]).sum())
                e = b["slot_ev"][s] > 0
                if e.any():
                    acc["tick"] += float(Fn.cross_entropy(tk[e], b["slot_tick"][s][e].long(), reduction="sum"))
                    acc["n_ev"] += int(e.sum())
        if "ab_hazard" in out and "ab_ok" in b:
            s = b["ab_ok"] > 0
            if s.any():
                acc["ability"] += float((slot_nll(out["ab_hazard"][s].float(), out["ab_tick"][s].float(), b["ab_ev"][s],
                                                  b["ab_tick"][s]) * w[s]).sum())
                acc["w_ab"] += float(w[s].sum())
        acc["value"] += float((Fn.cross_entropy(out["value"].float(), b["value"], reduction="none") * w).sum())
        acc["w_all"] += float(w.sum())
    r = {"cell": acc["cell"] / max(acc["n_cell"], 1), "card": acc["card"] / max(acc["n_card"], 1),
         "wait": acc["wait"] / max(acc["w_wait"], 1e-9), "timing": acc["timing"] / max(acc["w_slot"], 1e-9),
         "tick": acc["tick"] / max(acc["n_ev"], 1), "ability": acc["ability"] / max(acc["w_ab"], 1e-9),
         "value": acc["value"] / max(acc["w_all"], 1e-9), "cell_top1": acc["cell_top1"] / max(acc["n_cell"], 1),
         "card_top1": acc["card_top1"] / max(acc["n_card"], 1),
         "hazard_mean": acc["hz_sum"] / max(acc["w_slot"], 1e-9), "event_rate": acc["ev_sum"] / max(acc["w_slot"], 1e-9),
         "n_cell": int(acc["n_cell"]), "n_card": int(acc["n_card"]), "w_slot": acc["w_slot"], "w_ab": acc["w_ab"]}
    r["total"] = r["cell"] + r["card"] + r["timing"] + r["ability"] + 0.5 * r["wait"] + 0.5 * r["value"]
    return r


def main_opp(a, arrs: dict, meta: dict) -> int:
    """P2-OPP1 trainer (``--opp-timing`` / ``--opp-ability`` ...): step-based, a held-out NLL curve every
    ``--eval-every`` steps (``curve_<tag>.jsonl``), checkpoint = best held-out ``total``. ``--init`` = fine-tune from a
    checkpoint with the same options (live rows). Data = rows_to_npz output (split 0 train / 1 held-out)."""
    from .model_gen import load_model
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rng = np.random.default_rng(a.seed)
    if a.opp_timing:
        rb = meta.get("row_builder") or {}
        if (int(rb.get("wait_stride", -1)), int(rb.get("play_window", -1))) != (10, 0) or "slot_ok" not in arrs:
            raise ValueError("--opp-timing needs SLOT rows (wait_stride 10, play_window 0, slot_* columns): stride-40 / "
                             "window-20 rows drop the 20 ticks before every play, so the slot likelihood would not be exact")
    if a.hand_inferred not in ("mask_card", "drop"):
        raise ValueError("--hand-inferred: mask_card | drop")
    keep = np.ones(len(arrs["split"]), bool)
    if a.hand_inferred == "drop" and "card_ok" in arrs:
        keep = np.asarray(arrs["card_ok"]) > 0
    tr_idx = np.where((arrs["split"] == 0) & keep)[0]
    va_all = np.where((arrs["split"] == 1) & keep)[0]
    va_idx = np.sort(np.random.default_rng(0).choice(va_all, size=min(a.eval_rows, len(va_all)), replace=False))
    rows = GenRows(arrs, tr_idx, dev)
    va = rows.view(va_idx)
    vocab_list = meta["card_vocab"]
    ctx = dict(kv.split("=") for kv in a.opp_ctx.split(",")) if a.opp_ctx else {}
    opp = dict(timing=a.opp_timing, ability=a.opp_ability, deck_enc=a.opp_deck_enc,
               n_decks=int(np.max(arrs["deck_gid"])) if a.opp_deck_enc else 0,
               ctx_tokens={k: int(v) for k, v in ctx.items()})
    if a.init is not None:
        model, st0 = load_model(a.init, dev, memory=a.memory)
        o0 = st0.get("opp") or {}
        if {k: v for k, v in o0.items() if k != "n_decks"} != {k: v for k, v in opp.items() if k != "n_decks"}:
            raise ValueError(f"--init {a.init} options {o0} differ from these {opp}")
        if st0["card_vocab"] != vocab_list:
            raise ValueError("--init card_vocab differs from the data's (build the rows with rows_to_npz --vocab-from)")
    else:
        model = GenModel(d=a.d, layers=a.layers, d_c=a.d_c, n_cards=len(vocab_list), feature_version=a.feature_version,
                         **opp).to(dev)
        if a.memory:
            model.add_memory(version=a.memory, zero_empty=True, zero_init=False)
    if a.memory:
        from .dataset_gen import checkpoint_gid, load_memory_tables
        if a.memory_tables is None:
            raise ValueError("--memory needs --memory-tables")
        packed, row_tab, _ = load_memory_tables(a.memory_tables)
        rows.memory, rows.memory_version = (packed, row_tab, arrs["tick"]), a.memory
        rows.memory_gid = checkpoint_gid(vocab_list)
        va.memory, va.memory_version, va.memory_gid = rows.memory, rows.memory_version, rows.memory_gid
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=max(a.max_steps, 1), pct_start=0.05)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{a.tag}_s{a.seed}" if a.tag else f"s{a.seed}"
    ckpt, curve = a.out_dir / f"opp_{tag}.pt", a.out_dir / f"curve_{tag}.jsonl"
    amp = a.amp == "bf16" and dev.type == "cuda"
    if amp:
        torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = True
    _args = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()}
    _args.update(feature_version=model.feature_version, d=model.d, layers=len(model.encoder.layers), d_c=model.d_c)

    def save(path, step, ev):
        torch.save({"model": model.state_dict(), "args": _args, "deck": "generalist", "step": step, "val": ev,
                    "n_params": n_params, "gen": True, "card_vocab": vocab_list, "d_c": model.d_c, "opp": model.opp,
                    "memory": a.memory, "data_meta": {k: meta.get(k) for k in ("source", "row_builder", "data_sha256")}},
                   path)

    best, t0, step, tot, nb, parts_acc = float("inf"), time.time(), 0, 0.0, 0, {}
    print(json.dumps({"opp": model.opp, "n_params": n_params, "train_rows": int(len(tr_idx)), "val_rows": int(len(va_idx)),
                      "device": str(dev)}), flush=True)
    with curve.open("a") as cf:
        ev0 = evaluate_opp(model, va, grid=a.grid)
        cf.write(json.dumps({"step": 0, "rows_seen": 0, **ev0}) + "\n"); cf.flush()
        while step < a.max_steps:
            perm = rng.permutation(tr_idx)
            for s0 in range(0, len(perm) - a.bs + 1, a.bs):
                model.train()
                b = rows.batch(perm[s0:s0 + a.bs])
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                    loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5, grid=a.grid)
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); sched.step()
                step += 1; nb += 1; tot += float(loss.detach())
                for k, v in parts.items():
                    parts_acc[k] = parts_acc.get(k, 0.0) + v
                if step % a.eval_every == 0 or step == a.max_steps:
                    ev = evaluate_opp(model, va, grid=a.grid)
                    rec = {"step": step, "rows_seen": step * a.bs, "train_loss": tot / max(nb, 1),
                           "train_parts": {k: v / max(nb, 1) for k, v in parts_acc.items()},
                           "seconds": round(time.time() - t0), "lr": sched.get_last_lr()[0], **ev}
                    cf.write(json.dumps(rec) + "\n"); cf.flush()
                    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()
                                      if k != "train_parts"}), flush=True)
                    tot, nb, parts_acc = 0.0, 0, {}
                    if ev["total"] < best:
                        best = ev["total"]
                        save(ckpt, step, ev)
                    save(a.out_dir / f"opp_{tag}_last.pt", step, ev)
                if step >= a.max_steps:
                    break
    print(json.dumps({"FINAL": tag, "best_total": best, "ckpt": str(ckpt), "n_params": n_params,
                      "seconds": round(time.time() - t0)}), flush=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature-version", type=int, choices=(1, 2, 3, 4, 5, 6), default=None)
    ap.add_argument('--smoke-one-batch', action='store_true', help='One forward/backward only; no model or deployment checkpoint.')
    ap.add_argument('--rocket-context-weight', type=float, default=None,
                    help='Maximum pro-context loss weight from held-out selection; legacy default 1.')
    ap.add_argument('--exclude-defensive-xbow-context', action='store_true',
                    help='Owner-authorized overnight five-target contract; tactical label awaits Tuesday.')
    ap.add_argument('--inputs-only-deadline-fallback', action='store_true',
                    help='Owner-authorized 02:30 deadline fallback; requires explicit context weight 1.')
    ap.add_argument('--rocket-context-artifact', type=Path,
                    help='Verified probability.npy and artifact.json sidecar for this exact dataset.')
    ap.add_argument('--inputs-only-arm', action='store_true',
                    help='Lead 2026-10-04: gen_v3.1a A/B arm = every v4 input, NO context weighting (weight None/1, no '
                         'artifact); gen_v3.1b adds the six-target weighting, so its effect is attributable.')
    ap.add_argument('--allow-causal-tti-unknowns', action='store_true',
                    help='Owner decision2: past-motion estimates plus explicit unknown masks for ambiguous/new tracks.')
    ap.add_argument('--mmap-cache-dir', type=Path,
                    help='Fresh directory for version4 disk-backed dataset arrays; identical values, bounded heap.')
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--cue-data", type=Path, default=None,
                    help="step d: a cue sidecar of THIS --data (scratchpad/gauntlet/L74/stepd/cue_sidecar.py) -> the model "
                         "gets the zero-init cue_in layer and every unit token its 22 cue floats. Absent = unchanged")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--amp", choices=("none", "bf16"), default="none",
                    help="bf16 autocast for the TRAINING forward/loss (+ TF32 matmuls); eval stays fp32. 2026-10-03 "
                         "profile (L70/speed): 244 -> 150 ms/step on the RTX 5050. Default none = byte-identical")
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--d", type=int, default=128)
    ap.add_argument("--layers", type=int, default=4)
    ap.add_argument("--d-c", type=int, default=64, help="card identity embedding width")
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--grid", default="floor", choices=("floor", "lattice"))
    ap.add_argument("--limit-rows", type=int, default=0)
    ap.add_argument("--deck-weighting", default="none", choices=("none", "sqrt"))
    ap.add_argument("--row-weights", type=Path, default=None,
                    help="step d: a per-row weight .npy for THIS --data (L74/stepd/row_weights.py: unfavourable "
                         "matchups x3); each epoch draws len(train) rows with replacement in proportion. Absent = unchanged")
    ap.add_argument("--select", default="cell_tile_top1")
    ap.add_argument("--val-sample", type=int, default=30000,
                    help="per-epoch all-deck val = a FIXED seed-0 sample of N val rows (0 = all); v3val is always full")
    # P2-OPP1 (plan1026 Pillar 2): any of these switches to main_opp; absent = the legacy trainer unchanged
    ap.add_argument("--opp-timing", action="store_true", help="timing head (10-tick slot survival) replaces the gate")
    ap.add_argument("--opp-ability", action="store_true", help="ability-press head (same slot structure)")
    ap.add_argument("--opp-deck-enc", action="store_true", help="set-transformer deck encoder + deck id (20%% dropout)")
    ap.add_argument("--opp-ctx", default="", help="context tokens, e.g. band=8,mode=8,era=8 (ids from the rows)")
    ap.add_argument("--memory", default=None, choices=(None, "v1", "v2"), help="joint memory encoder (opp trainer)")
    ap.add_argument("--memory-tables", type=Path, default=None)
    ap.add_argument("--hand-inferred", default="mask_card", help="mask_card (no card label on hand-inferred rows) | drop")
    ap.add_argument("--init", type=Path, default=None, help="opp trainer: fine-tune from this checkpoint")
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--eval-every", type=int, default=2000)
    ap.add_argument("--eval-rows", type=int, default=100000)
    a = ap.parse_args(argv)
    opp_mode = a.opp_timing or a.opp_ability or a.opp_deck_enc or bool(a.opp_ctx) or a.init is not None
    if a.mmap_cache_dir is not None:
        from .dataset_spool import load_mapped
        arrs, meta = load_mapped(a.data, a.mmap_cache_dir)
    else:
        arrs, meta = load_ds(a.data)
    version = int(meta.get("feature_version", 1))
    expected_data_version = 5 if a.feature_version == 6 else a.feature_version
    if a.feature_version is not None and max(expected_data_version, 2) != max(version, 2):
        raise ValueError("feature version does not match dataset")
    a.feature_version = version if a.feature_version is None else a.feature_version
    if opp_mode:
        if a.max_steps <= 0:
            raise ValueError("the opp trainer needs --max-steps")
        return main_opp(a, arrs, meta)
    if a.rocket_context_artifact is not None:
        from .rocket_context import load_weight_artifact
        probability, evidence = load_weight_artifact(a.rocket_context_artifact, a.data)
        arrs['rocket_context_probability'] = probability
        meta['rocket_context'] = evidence
    if version >= 4:
        from .projectile_observation import require_complete_training
        require_complete_training(meta, allow_causal_tti_unknowns=a.allow_causal_tti_unknowns)
        if not a.smoke_one_batch:
            if a.exclude_defensive_xbow_context or a.inputs_only_deadline_fallback:
                raise ValueError('Owner 2026-10-04 cancelled proxy/exclusion/deadline training')
            if a.inputs_only_arm:
                if a.rocket_context_weight not in (None, 1.0) or a.rocket_context_artifact is not None:
                    raise ValueError('--inputs-only-arm trains WITHOUT context weighting (no weight > 1, no artifact)')
            else:
                from .rocket_context import require_weight_artifact
                require_weight_artifact(arrs, meta, a.rocket_context_weight)
    if a.rocket_context_weight is not None and (not np.isfinite(a.rocket_context_weight) or a.rocket_context_weight < 1):
        raise ValueError('Rocket context weight must be finite and >= 1')
    if version < 4 and a.rocket_context_weight not in (None, 1.0):
        raise ValueError('Rocket context weighting requires public-only version 4')
    if a.cue_data is not None:
        import hashlib
        with np.load(a.cue_data, allow_pickle=False) as cz:
            cmeta = json.loads(str(cz["meta"]))
            h = hashlib.sha256()
            with a.data.open("rb") as f:
                for blk in iter(lambda: f.read(1 << 22), b""):
                    h.update(blk)
            if cmeta["data_sha256"] != h.hexdigest() or cz["cue"].shape[0] != len(arrs["tok"]):
                raise ValueError(f"--cue-data {a.cue_data} was built for another dataset (sha / token count differ)")
            arrs["cue"] = cz["cue"]
        meta["cue_sidecar"] = cmeta
    if meta.get("grid") != a.grid:
        print(json.dumps({"warning": f"dataset built with grid {meta.get('grid')!r}, training with {a.grid!r}"}))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rng = np.random.default_rng(a.seed)
    tr_idx = np.where(arrs["split"] == 0)[0]
    if a.limit_rows and a.limit_rows < len(tr_idx):
        tr_idx = np.sort(rng.choice(tr_idx, size=a.limit_rows, replace=False))
    va_idx = val_rows(arrs, a.val_sample)
    v3_idx = np.where(arrs["v3val"] == 1)[0]
    rows = GenRows(arrs, tr_idx, dev)                            # one device copy; val / v3val are views
    va, v3 = rows.view(va_idx), rows.view(v3_idx)
    p_row = None
    if a.deck_weighting == "sqrt":
        n_dk = np.bincount(arrs["deck_id"][tr_idx])
        p_row = 1.0 / np.sqrt(n_dk[arrs["deck_id"][tr_idx]])
        p_row /= p_row.sum()
    if a.row_weights is not None:
        if p_row is not None:
            raise ValueError("--row-weights and --deck-weighting sqrt are exclusive")
        w = np.load(a.row_weights)
        if w.shape != (len(arrs["split"]),) or not np.all(np.isfinite(w)) or (w < 0).any():
            raise ValueError(f"--row-weights {a.row_weights}: need {len(arrs['split'])} finite non-negative weights")
        p_row = w[tr_idx].astype(np.float64)
        p_row /= p_row.sum()
    vocab_list = meta["card_vocab"]
    model = GenModel(d=a.d, layers=a.layers, d_c=a.d_c, n_cards=len(vocab_list), feature_version=a.feature_version).to(dev)
    if a.cue_data is not None:
        model.add_cue_in()                                    # zero-init (STEP_C_SPEC 3); trained from row 1 here
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    if a.smoke_one_batch:
        if a.amp == 'bf16' and dev.type != 'cuda':
            raise ValueError('BF16 smoke requires CUDA; refusing a silent fp32 smoke')
        b = rows.batch(tr_idx[:a.bs])
        with torch.autocast(dev.type, dtype=torch.bfloat16, enabled=a.amp == 'bf16'):
            loss, _ = losses(model, b, mirror=not a.no_mirror, grid=a.grid)
        if not torch.isfinite(loss): raise ValueError('Nonfinite smoke loss')
        loss.backward()
        if not all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()):
            raise ValueError('Nonfinite smoke gradients')
        opt.step()
        result=dict(status='TRAIN_GEN_ONE_BATCH_PASS',amp=a.amp,device=str(dev),rows=len(b['gate']),loss=float(loss.detach()),deployment_evidence=False)
        (a.out_dir/'smoke.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result)); return 0
    steps = a.epochs * (len(tr_idx) // a.bs)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=max(steps, 1), pct_start=0.05)
    tag = f"{a.tag}_s{a.seed}" if a.tag else f"s{a.seed}"
    ckpt = a.out_dir / f"gen_{tag}.pt"
    hist, best = [], -1.0
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    for ep in range(a.epochs):
        model.train()
        te = time.time()
        perm = rng.permutation(tr_idx) if p_row is None else rng.choice(tr_idx, size=len(tr_idx), p=p_row)
        tot, nb, parts_acc = 0.0, 0, {}
        amp = a.amp == "bf16" and dev.type == "cuda"
        if amp:                                          # TF32 for the fp32 parts the autocast leaves (optimizer etc.)
            torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = True
        for s in range(0, len(perm) - a.bs + 1, a.bs):
            b = rows.batch(perm[s:s + a.bs])
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5, grid=a.grid,
                                     rocket_context_weight=a.rocket_context_weight or 1.0)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step()
            tot += float(loss.detach()); nb += 1
            for k, v in parts.items():
                parts_acc[k] = parts_acc.get(k, 0.0) + v
            if nb % 200 == 0:
                print(json.dumps({"epoch": ep + 1, "step": nb, "of": len(perm) // a.bs,
                                  "rows_per_s": round(nb * a.bs / (time.time() - te)), "loss": round(tot / nb, 4)}),
                      flush=True)
        train_s = time.time() - te
        ev = evaluate(model, va, grid=a.grid)
        ev_v3 = evaluate(model, v3, grid=a.grid)
        ev.update({"epoch": ep + 1, "train_loss": tot / max(nb, 1),
                   "train_parts": {k: v / max(nb, 1) for k, v in parts_acc.items()}, "train_seconds": round(train_s, 1),
                   "seconds": round(time.time() - t0),
                   "gpu_peak_mb": round(torch.cuda.max_memory_allocated() / 2 ** 20) if dev.type == "cuda" else None,
                   "v3val": ev_v3})
        hist.append(ev)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in ev.items()
                          if k not in ("train_parts", "v3val")}), flush=True)
        print(json.dumps({"v3val": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in ev_v3.items()}}), flush=True)
        if ev[a.select] > best:
            best = ev[a.select]
            _args = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()}
            torch.save({"model": model.state_dict(), "args": _args, "deck": "generalist", "epoch": ep + 1, "val": ev,
                        "n_params": n_params, "gen": True, "card_vocab": vocab_list, "d_c": a.d_c}, ckpt)
        (a.out_dir / f"hist_gen_{tag}.json").write_text(json.dumps({"seed": a.seed, "n_params": n_params,
                                                                     "ckpt": str(ckpt), "val_sample": a.val_sample,
                                                                     "val_rows": va_idx.tolist(), "hist": hist}))
    st = torch.load(ckpt, map_location=dev)
    model.load_state_dict(st["model"])
    ev_tr = evaluate(model, rows.view(rng.choice(tr_idx, size=min(len(tr_idx), 20000), replace=False)), grid=a.grid)
    bestv = max(hist, key=lambda h: h[a.select])
    final = {"seed": a.seed, "n_params": n_params, "best_val": bestv, "train_subset": ev_tr, "ckpt": str(ckpt),
             "epochs": a.epochs, "train_rows": int(len(tr_idx)), "seconds": round(time.time() - t0)}
    (a.out_dir / f"final_gen_{tag}.json").write_text(json.dumps(final, indent=1))
    print(json.dumps({"FINAL": tag, "epoch": bestv["epoch"], "val_cell_half": bestv["cell_half_top1"],
                      "val_card": bestv["card_top1"], "v3val_cell_half": bestv["v3val"]["cell_half_top1"],
                      "v3val_card": bestv["v3val"]["card_top1"], "v3val_gate_bal": bestv["v3val"]["gate_bal_acc"],
                      "train_cell_half": ev_tr["cell_half_top1"], "n_params": n_params}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
