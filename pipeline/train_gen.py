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
from .eval_gen import GenRows, evaluate, val_rows
from .model_gen import GenModel, mirror_gen
from .model_v3 import cell_label

REPO = Path(__file__).resolve().parents[1]


def _ce(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Cross-entropy over the rows with a real target (>= 0); exactly 0 when there are none (a plain
    ``ignore_index=-1`` mean is 0/0 = NaN there, and -inf pad logits make ``logits.sum() * 0`` NaN too)."""
    ok = target >= 0
    return Fn.cross_entropy(logits[ok], target[ok]) if ok.any() else logits.new_zeros(())


def losses(model: GenModel, b: dict, mirror: bool, grid: str = "floor") -> tuple[torch.Tensor, dict]:
    tok, sc, past, xy = b["tok"], b["sc"], b["past"], b["xy"]
    if mirror:
        tok, sc, past, xy = mirror_gen(tok, sc, past, xy)
    play = b["gate"] > 0.5
    out = model(dict(b, tok=tok, sc=sc, past=past), card=b["card"], form=b["form"])
    parts = {}
    if play.any():
        parts["cell"] = Fn.cross_entropy(out["cell"][play], cell_label(xy[play], grid))
        parts["card"] = _ce(out["card"][play], b["slot"][play])
    if (~play).any():
        parts["wait"] = 0.5 * _ce(out["wait"][~play], b["wait"][~play])
    parts["gate"] = Fn.binary_cross_entropy_with_logits(out["gate"], b["gate"])
    parts["value"] = 0.5 * Fn.cross_entropy(out["value"], b["value"])
    return sum(parts.values()), {k: float(v.detach()) for k, v in parts.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=20)
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
    ap.add_argument("--select", default="cell_tile_top1")
    ap.add_argument("--val-sample", type=int, default=30000,
                    help="per-epoch all-deck val = a FIXED seed-0 sample of N val rows (0 = all); v3val is always full")
    a = ap.parse_args(argv)
    arrs, meta = load_ds(a.data)
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
    vocab_list = meta["card_vocab"]
    model = GenModel(d=a.d, layers=a.layers, d_c=a.d_c, n_cards=len(vocab_list)).to(dev)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
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
        for s in range(0, len(perm) - a.bs + 1, a.bs):
            b = rows.batch(perm[s:s + a.bs])
            loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5, grid=a.grid)
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
