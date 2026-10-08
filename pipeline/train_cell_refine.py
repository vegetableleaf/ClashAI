"""Train ONLY a ``CellRefine`` module (model_gen) on top of a frozen generalist checkpoint (L73 centre-column fix).

    python -m pipeline.train_cell_refine --base icebow/data/pipeline/gen_v32_s0/gen_s0.pt \
        --data icebow/data/pipeline/gen_dataset_v32_fv5.npz --epochs 2 --amp bf16

Imitation cell CE on the TRAIN play rows, teacher-forced on the pro's card, with train_gen's mirror augmentation
(``train_gen.losses``, p = 0.5) and the base's grid. Every base parameter is frozen and the base runs in eval mode
(no dropout), so the card / gate / wait / value heads are bit-for-bit the base's. The module's output projection
starts at zero, so step 0 IS the base. Selection: lowest cell NLL on a fixed seed-0 sample of VAL play rows.
Writes ``<base stem>_cellref.pt`` next to the base (never the base itself): the base checkpoint dict with the full
state dict (base + ``cell_refine.*``), ``cell_refine: True`` and ``cell_refine_base`` / ``cell_refine_train`` notes.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from .dataset import load as load_ds
from .eval_gen import evaluate
from .model_gen import load_model
from .train_gen import GenRows, losses


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None, help="default: <base dir>/<base stem>_cellref.pt")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--amp", choices=("none", "bf16"), default="bf16")
    ap.add_argument("--val-sample", type=int, default=20000)
    ap.add_argument("--eval-every", type=int, default=1000, help="steps between val evaluations / checkpoint saves")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--channels", type=int, default=32)
    ap.add_argument("--layers", type=int, default=4, help="dilated conv layers (dilation 2^i; RF +-(2^layers - 1) cells)")
    a = ap.parse_args(argv)
    out = a.out or a.base.with_name(a.base.stem + "_cellref.pt")
    if out.resolve() == a.base.resolve():
        raise SystemExit("refusing to overwrite the base checkpoint")
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, st = load_model(a.base, dev)
    if getattr(model, "cell_refine", None) is not None:
        raise SystemExit("base already has a cell_refine module")
    grid = str(st["args"].get("grid", "lattice"))
    for p in model.parameters():
        p.requires_grad_(False)
    ref = model.add_cell_refine(a.channels, a.layers)
    model.eval()                                       # frozen base: dropout off; CellRefine has no dropout
    arrs, meta = load_ds(a.data)
    play = arrs["y_gate"] == 1
    tr_idx = np.where((arrs["split"] == 0) & play)[0]
    va_all = np.where((arrs["split"] == 1) & play)[0]
    va_idx = np.sort(np.random.default_rng(0).choice(va_all, size=min(a.val_sample, len(va_all)), replace=False))
    rows = GenRows(arrs, tr_idx, dev)
    va = rows.view(va_idx)
    opt = torch.optim.AdamW(ref.parameters(), lr=a.lr, weight_decay=0.01)
    steps = int(a.epochs * (len(tr_idx) // a.bs))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=max(steps, 1), pct_start=0.05)
    amp = a.amp == "bf16" and dev.type == "cuda"
    log = out.with_suffix(".log.jsonl")
    log.write_text("")

    def note(d):
        print(json.dumps(d), flush=True)
        with log.open("a") as f:
            f.write(json.dumps(d) + "\n")

    def val(step):
        ev = evaluate(model, va, grid=grid)
        model.eval()                                   # evaluate() leaves eval mode; keep it that way
        return {"step": step, **{k: ev[k] for k in ("cell_nll", "cell_half_top1", "cell_tile_top1", "card_top1", "n_play")}}

    base_ev = val(0)
    note({"base": str(a.base), "out": str(out), "train_play_rows": int(len(tr_idx)), "val_rows": int(len(va_idx)),
          "steps": steps, "params": sum(p.numel() for p in ref.parameters()), "val0": base_ev})
    best, t0, step, run = base_ev["cell_nll"], time.time(), 0, 0.0
    while step < steps:
        perm = rng.permutation(tr_idx)
        for s in range(0, len(perm) - a.bs + 1, a.bs):
            if step >= steps:
                break
            b = rows.batch(perm[s:s + a.bs])
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                # every base parameter is frozen, so only the cell CE term carries a gradient; the summed loss's
                # other terms are constants and do not change it
                loss, parts = losses(model, b, mirror=rng.random() < 0.5, grid=grid)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(ref.parameters(), 1.0)
            opt.step(); sched.step(); step += 1
            run = 0.98 * run + 0.02 * parts["cell"] if step > 1 else parts["cell"]
            if step % 200 == 0:
                note({"step": step, "of": steps, "cell_loss_ema": round(run, 4),
                      "rows_per_s": round(step * a.bs / (time.time() - t0)), "min": round((time.time() - t0) / 60, 1)})
            if step % a.eval_every == 0 or step == steps:
                ev = val(step)
                note({"val": ev})
                if ev["cell_nll"] < best:
                    best = ev["cell_nll"]
                    sd = {k: v.detach().cpu() for k, v in model.state_dict().items()}
                    torch.save({**st, "model": sd, "cell_refine": True,
                                "cell_refine_base": str(a.base).replace("\\", "/"),
                                "cell_refine_train": {**{k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
                                                      "step": step, "val": ev, "val0": base_ev}}, out)
                    note({"saved": str(out), "step": step, "cell_nll": ev["cell_nll"]})
    note({"done": True, "best_val_cell_nll": best, "base_val_cell_nll": base_ev["cell_nll"],
          "minutes": round((time.time() - t0) / 60, 1)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
