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
from .model_gen import GenModel, mirror_gen
from .model_v3 import cell_label

REPO = Path(__file__).resolve().parents[1]


class GenRows(LegacyGenRows):
    """Versioned batching; legacy datasets take the original batch path unchanged."""
    def __init__(self, arrs, idx, device):
        super().__init__(arrs, idx, device)
        self.unit_form = torch.as_tensor(arrs["unit_form"], dtype=torch.long) if "unit_form" in arrs else None
        self.opp_past = torch.as_tensor(arrs["opp_past"], device=device) if "opp_past" in arrs else None

    def batch(self, ids):
        b = super().batch(ids)
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


def _losses(model: GenModel, b: dict, mirror: bool, grid: str = "floor", rocket_context_weight: float = 1.0):
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
    a = ap.parse_args(argv)
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
