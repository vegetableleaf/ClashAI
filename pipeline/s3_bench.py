"""S3's pre-registered gate: does a SEARCHED target agree with the pro at least as often as the student?

Spec (§5cs.53 C): "searched targets agree with pros >= student on 500 pro states". This module is the
instrument for that sentence, built BEFORE the teacher exists so the criterion cannot be tuned to the
result it is meant to judge.

Three subcommands:

  build   fixed 500-state benchmark from VAL replays only -- one row per accepted pro play, carrying the
          replay tag + tick + side, so a teacher can RE-DRIVE the engine to that exact state (the tokenised
          dataset row alone is not enough; the engine needs the tag and the tick).
  predict run an S1 checkpoint over the benchmark rows -> predictions.jsonl (the student baseline; the same
          argmax read as train_s1.evaluate, so the numbers are comparable to the S1 headline).
  score   agreement of one prediction file, or a PAIRED comparison of two.

Why paired. Student and teacher are read at the SAME states, so the question is not "are these two
proportions different" but "on how many states did they disagree, and which way". McNemar's exact test on
the discordant pairs is the right instrument and is far more powerful than comparing two independent
proportions: 500 states with a 2 pp unpaired difference is noise, while 40 discordant pairs splitting
30/10 is not. Reporting the unpaired numbers side by side -- the obvious thing to do -- is the trap this
docstring exists to prevent.

Metrics, all computed against the pro's own (card, cell):
  card    predicted deck slot == the pro's slot
  cell    exact placement cell (<= 0.3 tiles, train_s1.evaluate's convention-free read)
  1t      within one tile
  dist    mean tile distance

usage:
  python -m pipeline.s3_bench build icebow --data icebow/data/pipeline/s1_dataset.npz --out scratchpad/.../bench500.json
  python -m pipeline.s3_bench predict icebow <bench.json> --ckpt <ck.pt> --out <pred.jsonl>
  python -m pipeline.s3_bench score <bench.json> <student.jsonl> [--vs <teacher.jsonl>]
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


# ------------------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------------------
def build(argv) -> int:
    ap = argparse.ArgumentParser(prog="s3_bench build")
    ap.add_argument("deck")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)

    z = np.load(a.data, allow_pickle=False)
    tags, split, gate = z["tags"], z["split"], z["y_gate"]
    sel = np.flatnonzero((split == 1) & (gate == 1))          # VAL replays, accepted pro plays only
    if len(sel) < a.n:
        raise SystemExit(f"only {len(sel)} val play rows, need {a.n}")
    rng = np.random.default_rng(a.seed)
    # one state per replay first, then fill -- a benchmark that draws 40 states from one long match is a
    # benchmark of that match. Spread across replays, then top up at random from what is left.
    rep = z["rep"][sel]
    order = rng.permutation(len(sel))
    seen, first, rest = set(), [], []
    for i in order:
        (first if rep[i] not in seen else rest).append(i)
        seen.add(rep[i])
    pick = (first + rest)[:a.n]
    rows = []
    for i in pick:
        r = int(sel[i])
        rows.append({"tag": str(tags[int(z["rep"][r])]), "tick": int(z["tick"][r]), "side": int(z["side"][r]),
                     "row": r, "slot": int(z["y_slot"][r]),
                     "x": float(z["y_xy"][r][0]), "y": float(z["y_xy"][r][1])})
    meta = {"deck": a.deck, "data": str(a.data), "n": len(rows), "seed": a.seed,
            "replays": len({r["tag"] for r in rows}), "val_play_rows_available": int(len(sel))}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"meta": meta, "rows": rows}), encoding="utf-8")
    print(json.dumps(meta))
    return 0


# ------------------------------------------------------------------------------------------------------
# predict (student baseline)
# ------------------------------------------------------------------------------------------------------
def predict(argv) -> int:
    ap = argparse.ArgumentParser(prog="s3_bench predict")
    ap.add_argument("deck")
    ap.add_argument("bench", type=Path)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args(argv)

    import torch                                              # local: build/score must not need torch
    from .dataset import load as load_ds
    from .model_v3 import S1Model
    from .obs_contract import load_deck
    from .train_s1 import GRID_X, GRID_Y, Rows, hand_mask_from_sc

    bench = json.loads(a.bench.read_text(encoding="utf-8"))
    arrs, _ = load_ds(Path(bench["meta"]["data"]))
    idx = np.asarray([r["row"] for r in bench["rows"]], dtype=np.int64)
    dev = torch.device(a.device)
    st = torch.load(a.ckpt, map_location=dev)
    args = st.get("args", {})
    grid = args.get("grid", "floor")
    off = 0.5 if grid == "floor" else 0.0                     # train_s1.evaluate's own cell->tile read
    model = S1Model(d=args.get("d", 128), layers=args.get("layers", 4)).to(dev)
    model.load_state_dict(st["model"])
    model.eval()
    rows = Rows(arrs, idx, dev)
    load_deck(a.deck)                                         # validates the deck name early

    recs = []
    with torch.no_grad():
        for s0 in range(0, len(idx), 256):
            ids = idx[s0:s0 + 256]
            b = rows.batch(ids)
            # card_slot = the PRO's slot, exactly as train_s1.evaluate does it: the cell head is
            # teacher-forced on the true card there, so a number read any other way is not comparable
            # to the S1 headline (18.17 / 19.84). The teacher must be read the same way.
            out = model(b["tok"], b["mask"], b["sc"], b["past"],
                        card_slot=b["slot"].clamp(min=0), hand_mask=hand_mask_from_sc(b["sc"]))
            slot = out["card"].argmax(-1).cpu().numpy() if "card" in out else out["slot"].argmax(-1).cpu().numpy()
            cell = out["cell"].argmax(-1).cpu().numpy()
            for k in range(len(ids)):
                recs.append({"slot": int(slot[k]),
                             "px": float(int(cell[k]) % GRID_X) + off,
                             "py": float(int(cell[k]) // GRID_X) + off})
    if len(recs) != len(idx):
        raise SystemExit(f"predicted {len(recs)} rows for {len(idx)} benchmark states")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for r, p_ in zip(bench["rows"], recs):
            f.write(json.dumps({"tag": r["tag"], "tick": r["tick"], **p_}) + chr(10))
    print(json.dumps({"out": str(a.out), "rows": len(recs), "ckpt": str(a.ckpt), "grid": grid,
                      "epoch": st.get("epoch")}))
    return 0


# ------------------------------------------------------------------------------------------------------
# score
# ------------------------------------------------------------------------------------------------------
def _hits(bench: dict, preds: list[dict]) -> dict:
    """Per-state boolean vectors, so a paired test is possible. `px`/`py` are grid units WITH the
    checkpoint's own offset already applied by predict(), so scoring is convention-free: a floor-grid and
    a lattice-grid policy are read the same way here (the §5cs.70 label trap)."""
    from .train_s1 import GRID_X, GRID_Y
    by_key = {(p["tag"], p["tick"]): p for p in preds}
    card, cell, one_t, dist = [], [], [], []
    for r in bench["rows"]:
        p = by_key.get((r["tag"], r["tick"]))
        if p is None:
            raise SystemExit("prediction missing for %s@%s" % (r["tag"], r["tick"]))
        card.append(bool(p["slot"] == r["slot"]))
        dx = (p["px"] / GRID_X - r["x"]) * (GRID_X / 2)
        dy = (p["py"] / GRID_Y - r["y"]) * (GRID_Y / 2)
        d = math.hypot(dx, dy)
        dist.append(d); cell.append(d <= 0.3); one_t.append(d <= 1.0)
    return {"card": np.array(card), "cell": np.array(cell), "1t": np.array(one_t), "dist": np.array(dist)}


def _mcnemar(a: np.ndarray, b: np.ndarray) -> dict:
    """Exact two-sided McNemar on the discordant pairs (binomial, p = 0.5). a = baseline, b = challenger."""
    n01 = int((~a & b).sum())          # baseline wrong, challenger right
    n10 = int((a & ~b).sum())          # baseline right, challenger wrong
    n = n01 + n10
    if n == 0:
        return {"b_only": 0, "a_only": 0, "discordant": 0, "p_two_sided": 1.0}
    k = min(n01, n10)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return {"b_only": n01, "a_only": n10, "discordant": n, "p_two_sided": min(1.0, 2 * tail)}


def score(argv) -> int:
    ap = argparse.ArgumentParser(prog="s3_bench score")
    ap.add_argument("bench", type=Path)
    ap.add_argument("preds", type=Path, help="baseline predictions (the student)")
    ap.add_argument("--vs", type=Path, help="challenger predictions (the searched teacher)")
    a = ap.parse_args(argv)
    bench = json.loads(a.bench.read_text(encoding="utf-8"))

    def rd(p):
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    A = _hits(bench, rd(a.preds))
    n = len(bench["rows"])
    rep = {"n": n, "replays": bench["meta"]["replays"],
           "A": {k: (round(float(A[k].mean()) * 100, 2) if k != "dist" else round(float(A[k].mean()), 3))
                 for k in ("card", "cell", "1t", "dist")}}
    if a.vs:
        B = _hits(bench, rd(a.vs))
        rep["B"] = {k: (round(float(B[k].mean()) * 100, 2) if k != "dist" else round(float(B[k].mean()), 3))
                    for k in ("card", "cell", "1t", "dist")}
        rep["paired"] = {k: _mcnemar(A[k], B[k]) for k in ("card", "cell", "1t")}
        # the gate: the searched target must agree at least as often on exact cell
        rep["GATE_cell_ge_student"] = bool(B["cell"].mean() >= A["cell"].mean())
    print(json.dumps(rep, indent=1))
    return 0


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("build", "predict", "score"):
        print(__doc__); return 2
    return {"build": build, "predict": predict, "score": score}[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
