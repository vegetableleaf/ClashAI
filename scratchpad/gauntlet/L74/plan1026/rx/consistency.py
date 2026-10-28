"""Frame (2-tick) vs decision-only traces of the SAME matches: do the two trace sources give the same running totals?
    python consistency.py FRAMES.npz DECISIONS.npz      (build.py outputs; DECISIONS built from decision lines only)
Prints, per feature, mean end total (frame, decision) and the mean / max absolute per-match difference at 60/120/180 s.
"""
import json
import sys

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[5]))
from pipeline import r_exchange as RX  # noqa: E402


def load(p):
    d = np.load(p)
    meta = json.loads(str(d["meta"]))
    return {m["file"]: (d[f"t_{i}"], d[f"L_{i}"], m) for i, m in enumerate(meta)}


A, B = load(sys.argv[1]), load(sys.argv[2])
common = sorted(set(A) & set(B))
print(len(common), "matches in both;", sum(B[f][2]["trace"] == "decision" for f in common), "decision traces")
for tick in (1200, 2400, 3600, None):
    D = []
    for f in common:
        (ta, La, _), (tb, Lb, _) = A[f], B[f]
        if tick is None:
            D.append((La[-1], Lb[-1]))
        elif ta[-1] > tick and tb[-1] > tick:
            D.append((La[np.searchsorted(ta, tick, "right") - 1], Lb[np.searchsorted(tb, tick, "right") - 1]))
    a, b = np.array([x for x, _ in D]), np.array([y for _, y in D])
    print("end" if tick is None else f"{tick // 20}s", f"n {len(D)}")
    for k, name in enumerate(RX.FEATURES):
        for s, side in ((0, "own"), (1, "opp")):
            print(f"  {name:8s} {side}: frame {a[:, s, k].mean():7.2f} decision {b[:, s, k].mean():7.2f} "
                  f"mean|d| {np.abs(a[:, s, k] - b[:, s, k]).mean():6.2f} max|d| {np.abs(a[:, s, k] - b[:, s, k]).max():6.2f}")
