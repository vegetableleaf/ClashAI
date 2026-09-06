"""S1 trainer: ``pipeline.dataset`` npz -> ``S1Model`` checkpoint + per-epoch metrics json.

    python -m pipeline.train_s1 icebow --seed 0 --epochs 20 --out-dir scratchpad/gauntlet/L64/s1
    python -m pipeline.train_s1 icebow --baseline            # board-blind histogram baseline, same val rows

Losses: cell CE on PLAY rows (teacher-forced on the pro's card), hand-masked card CE on PLAY rows, gate BCE
on all rows, wait-for-card CE on WAIT rows, crown-diff CE on all rows. Mirror augmentation with p = 0.5.
Metrics (val, PLAY rows unless stated): cell top-1 at half-tile (2,304 cells) and at 1-tile (576) given the
pro's card; card top-1 (hand-masked); joint = card AND 1-tile cell; gate accuracy / balanced accuracy at 0.5
(all rows); wait top-1 (WAIT rows); value accuracy; global-embedding spread (mean pairwise cosine over 512
random val rows -- the old trunk measured 0.991). Checkpoint = best val 1-tile cell top-1. Both decks share
this file unchanged.
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
from .model_v3 import (GRID_X, GRID_Y, N_SLOTS, S1Model, VALUE_CLASSES, cell_index, cell_label, hand_mask_from_sc,
                       tile_of_cell,
                       mirror_batch)
from .obs_contract import F as TOK_F, load_deck

REPO = Path(__file__).resolve().parents[1]
MAX_U = 64


class Rows:
    """Dataset arrays on one device, batched by index with per-batch padding."""

    def __init__(self, arrs: dict, idx: np.ndarray, device):
        self.a, self.idx, self.dev = arrs, idx, device
        self.off = arrs["off"]
        self.tok_all = torch.from_numpy(arrs["tok"])
        self.sc = torch.from_numpy(arrs["sc"]).to(device)
        self.past = torch.from_numpy(arrs["past"]).to(device)
        self.xy = torch.from_numpy(arrs["y_xy"]).to(device)
        self.slot = torch.from_numpy(arrs["y_slot"].astype(np.int64)).to(device)
        self.gate = torch.from_numpy(arrs["y_gate"].astype(np.float32)).to(device)
        self.wait = torch.from_numpy(arrs["y_wait_slot"].astype(np.int64)).to(device)
        cr = arrs["y_crowns"].astype(np.int64)
        self.value = torch.from_numpy(np.clip(cr[:, 0] - cr[:, 1], -3, 3) + 3).to(device)

    def batch(self, ids: np.ndarray) -> dict:
        n = len(ids)
        tok = torch.zeros(n, MAX_U, TOK_F)
        mask = torch.zeros(n, MAX_U, dtype=torch.bool)
        for k, i in enumerate(ids):
            a, b = self.off[i], self.off[i + 1]
            m = min(b - a, MAX_U)
            tok[k, :m] = self.tok_all[a:a + m]
            mask[k, :m] = True
        ids_t = torch.from_numpy(ids).to(self.dev)
        return {"tok": tok.to(self.dev), "mask": mask.to(self.dev), "sc": self.sc[ids_t], "past": self.past[ids_t],
                "xy": self.xy[ids_t], "slot": self.slot[ids_t], "gate": self.gate[ids_t], "wait": self.wait[ids_t],
                "value": self.value[ids_t]}


def losses(model: S1Model, b: dict, mirror: bool, grid: str = "floor") -> tuple[torch.Tensor, dict]:
    tok, sc, past, xy = b["tok"], b["sc"], b["past"], b["xy"]
    if mirror:
        tok, sc, past, xy = mirror_batch(tok, sc, past, xy)
    play = b["gate"] > 0.5
    hm = hand_mask_from_sc(sc)
    slot_tf = b["slot"].clamp(min=0)
    out = model(tok, b["mask"], sc, past, card_slot=slot_tf, hand_mask=hm)
    parts = {}
    if play.any():
        cell_t = cell_label(xy[play], grid)
        parts["cell"] = Fn.cross_entropy(out["cell"][play], cell_t)
        parts["card"] = Fn.cross_entropy(out["card"][play], b["slot"][play])
    if (~play).any():
        parts["wait"] = 0.5 * Fn.cross_entropy(out["wait"][~play], b["wait"][~play])
    parts["gate"] = Fn.binary_cross_entropy_with_logits(out["gate"], b["gate"])
    parts["value"] = 0.5 * Fn.cross_entropy(out["value"], b["value"])
    return sum(parts.values()), {k: float(v.detach()) for k, v in parts.items()}


@torch.no_grad()
def evaluate(model: S1Model, rows: Rows, bs: int = 512, grid: str = "floor") -> dict:
    model.eval()
    n = len(rows.idx)
    agg = {"cell_half": 0, "cell_tile": 0, "card": 0, "joint": 0, "n_play": 0, "gate_tp": 0, "gate_tn": 0,
           "n_pos": 0, "n_neg": 0, "wait": 0, "n_wait": 0, "value": 0, "cell_nll": 0.0}
    gs = []
    for s in range(0, n, bs):
        ids = rows.idx[s:s + bs]
        b = rows.batch(ids)
        hm = hand_mask_from_sc(b["sc"])
        out = model(b["tok"], b["mask"], b["sc"], b["past"], card_slot=b["slot"].clamp(min=0), hand_mask=hm)
        play = b["gate"] > 0.5
        if play.any():
            logits = out["cell"][play]
            xy = b["xy"][play]
            t_half = cell_label(xy, grid)
            pred = logits.argmax(-1)
            agg["cell_half"] += int((pred == t_half).sum())
            agg["cell_nll"] += float(Fn.cross_entropy(logits, t_half, reduction="sum"))
            # 1-tile: sum probabilities of the 4 half-tile cells in each tile, compare argmax tiles
            p = logits.softmax(-1).view(-1, GRID_Y // 2, 2, GRID_X // 2, 2).sum((2, 4)).flatten(1)
            t_tile = cell_index(xy, GRID_X // 2, GRID_Y // 2) if grid == "floor" else tile_of_cell(t_half)
            tile_ok = p.argmax(-1) == t_tile
            agg["cell_tile"] += int(tile_ok.sum())
            card_ok = out["card"][play].argmax(-1) == b["slot"][play]
            agg["card"] += int(card_ok.sum())
            agg["joint"] += int((card_ok & tile_ok).sum())
            agg["n_play"] += int(play.sum())
        g_pred = out["gate"] > 0
        agg["gate_tp"] += int((g_pred & play).sum()); agg["gate_tn"] += int((~g_pred & ~play).sum())
        agg["n_pos"] += int(play.sum()); agg["n_neg"] += int((~play).sum())
        if (~play).any():
            agg["wait"] += int((out["wait"][~play].argmax(-1) == b["wait"][~play]).sum()); agg["n_wait"] += int((~play).sum())
        agg["value"] += int((out["value"].argmax(-1) == b["value"]).sum())
        if len(gs) < 4:
            gs.append(out["g"])
    g = torch.cat(gs)[:512]
    g = Fn.normalize(g, dim=-1)
    cos = (g @ g.t())
    spread = float((cos.sum() - cos.diag().sum()) / (len(g) * (len(g) - 1)))
    np_ = max(agg["n_play"], 1)
    return {"cell_half_top1": agg["cell_half"] / np_, "cell_tile_top1": agg["cell_tile"] / np_,
            "card_top1": agg["card"] / np_, "joint_top1": agg["joint"] / np_, "cell_nll": agg["cell_nll"] / np_,
            "gate_acc": (agg["gate_tp"] + agg["gate_tn"]) / max(n, 1),
            "gate_bal_acc": 0.5 * (agg["gate_tp"] / max(agg["n_pos"], 1) + agg["gate_tn"] / max(agg["n_neg"], 1)),
            "wait_top1": agg["wait"] / max(agg["n_wait"], 1), "value_acc": agg["value"] / max(n, 1),
            "emb_cosine": spread, "n_play": agg["n_play"], "n": n}


def baseline(arrs: dict, grid: str = "floor") -> dict:
    """Board-blind histogram: per card, the most common cell on TRAIN play rows; top-1 on VAL play rows.
    Card baseline: the most common slot among the hand (train frequency), evaluated on val."""
    tr = (arrs["split"] == 0) & (arrs["y_gate"] == 1)
    va = (arrs["split"] == 1) & (arrs["y_gate"] == 1)
    xy = torch.from_numpy(arrs["y_xy"]); slot = arrs["y_slot"].astype(np.int64)
    res = {}
    for name, gx, gy in (("half", GRID_X, GRID_Y), ("tile", GRID_X // 2, GRID_Y // 2)):
        c = (cell_index(xy, gx, gy) if grid == "floor" else
             (cell_label(xy, grid) if name == "half" else tile_of_cell(cell_label(xy, grid)))).numpy()
        best = {}
        for s in range(N_SLOTS):
            m = tr & (slot == s)
            best[s] = np.bincount(c[m], minlength=gx * gy).argmax() if m.any() else 0
        pred = np.array([best[s] for s in slot[va]])
        res[f"cell_{name}_top1"] = float((pred == c[va]).mean())
    freq = np.bincount(slot[tr], minlength=N_SLOTS).astype(float)
    hand = arrs["sc"][:, 7:43].reshape(-1, 4, 9)[:, :, :N_SLOTS].sum(1) > 0
    pred = np.where(hand[va], freq[None, :], -1).argmax(1)
    res["card_top1"] = float((pred == slot[va]).mean())
    res["n_val_play"], res["n_train_play"] = int(va.sum()), int(tr.sum())
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--data", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--d", type=int, default=128)
    ap.add_argument("--layers", type=int, default=4)
    ap.add_argument("--no-mirror", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=REPO / "scratchpad" / "gauntlet" / "L64" / "s1")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--tag", default="", help="checkpoint name suffix: s1_<deck>[_<tag>]_s<seed>.pt (default: none)")
    ap.add_argument("--grid", default="floor", choices=("floor", "lattice"),
                    help="placement label convention (model_v3.cell_label); stored in the checkpoint args")
    a = ap.parse_args(argv)
    deck = load_deck(a.deck)
    arrs, meta = load_ds(a.data or (deck.data_dir / "pipeline" / "s1_dataset.npz"))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    if a.baseline:
        r = baseline(arrs, a.grid)
        (a.out_dir / f"baseline_{a.deck}.json").write_text(json.dumps(r, indent=1))
        print(json.dumps({"deck": a.deck, "baseline": r}))
        return 0
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tr_idx = np.where(arrs["split"] == 0)[0]; va_idx = np.where(arrs["split"] == 1)[0]
    tr, va = Rows(arrs, tr_idx, dev), Rows(arrs, va_idx, dev)
    model = S1Model(d=a.d, layers=a.layers).to(dev)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    steps = a.epochs * (len(tr_idx) // a.bs)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=max(steps, 1), pct_start=0.05)
    tag = f"{a.deck}_{a.tag}_s{a.seed}" if a.tag else f"{a.deck}_s{a.seed}"
    ckpt = deck.data_dir / "pipeline" / f"s1_{tag}.pt"
    hist, best = [], -1.0
    rng = np.random.default_rng(a.seed)
    t0 = time.time()
    for ep in range(a.epochs):
        model.train()
        perm = rng.permutation(tr_idx)
        tot, nb, parts_acc = 0.0, 0, {}
        for s in range(0, len(perm) - a.bs + 1, a.bs):
            b = tr.batch(perm[s:s + a.bs])
            loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5, grid=a.grid)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step()
            tot += float(loss); nb += 1
            for k, v in parts.items():
                parts_acc[k] = parts_acc.get(k, 0.0) + v
        ev = evaluate(model, va, grid=a.grid)
        ev.update({"epoch": ep + 1, "train_loss": tot / max(nb, 1),
                   "train_parts": {k: v / max(nb, 1) for k, v in parts_acc.items()}, "seconds": round(time.time() - t0)})
        hist.append(ev)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in ev.items() if k != "train_parts"}), flush=True)
        if ev["cell_tile_top1"] > best:
            best = ev["cell_tile_top1"]
            ckpt.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"model": model.state_dict(), "args": vars(a) | {"out_dir": str(a.out_dir), "data": str(a.data)},
                        "deck": a.deck, "epoch": ep + 1, "val": ev, "n_params": n_params}, ckpt)
        (a.out_dir / f"hist_{tag}.json").write_text(json.dumps({"deck": a.deck, "seed": a.seed, "n_params": n_params,
                                                                 "ckpt": str(ckpt), "hist": hist}, indent=1))
    # train-set agreement of the best checkpoint (the S1 gate quotes train AND val)
    model.load_state_dict(torch.load(ckpt, map_location=dev)["model"])
    sub = Rows(arrs, rng.choice(tr_idx, size=min(len(tr_idx), 20000), replace=False), dev)
    ev_tr = evaluate(model, sub, grid=a.grid)
    final = {"deck": a.deck, "seed": a.seed, "n_params": n_params, "best_val": max(hist, key=lambda h: h["cell_tile_top1"]),
             "train_subset": ev_tr, "ckpt": str(ckpt), "epochs": a.epochs, "seconds": round(time.time() - t0)}
    (a.out_dir / f"final_{tag}.json").write_text(json.dumps(final, indent=1))
    print(json.dumps({"FINAL": tag, "val_cell_tile": final["best_val"]["cell_tile_top1"],
                      "val_cell_half": final["best_val"]["cell_half_top1"], "train_cell_tile": ev_tr["cell_tile_top1"],
                      "card": final["best_val"]["card_top1"], "joint": final["best_val"]["joint_top1"],
                      "emb_cos": final["best_val"]["emb_cosine"], "epoch": final["best_val"]["epoch"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
