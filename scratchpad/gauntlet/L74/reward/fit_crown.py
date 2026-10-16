"""Diagnostic for AUDIT_A3P check ii: does a destroyed princess (a crown) carry win log-odds beyond its hp?
    python fit_crown.py pod_backup_weekend/pod1015_s5/ROWS_R1/rows.jsonl   (AUDIT_A3P.txt check ii diagnostic)
logistic z ~ dE + dT + dC per phase on ROWS_R1 (dC = foe princesses destroyed - own princesses destroyed), match bootstrap."""
import json, sys
from pathlib import Path
import numpy as np
sys.path[:0] = [str(Path(__file__).resolve().parents[4]), str(Path(__file__).resolve().parent)]
from pipeline import reward_shaping as RS
import fit_rho
M = []
for line in open(sys.argv[1], encoding="utf-8"):
    r = json.loads(line)
    if r["z"] == 0:
        continue
    k = np.asarray(r["keep"], bool)
    tr, ts = np.asarray(r["tr_rows"], float)[k], np.asarray(r["ts_rows"], float)[k]
    rows = np.c_[tr, ts[:, :6], ts[:, 10]]
    dE, dT, P = RS.trade2_parts(rows)
    dC = (rows[:, 8:10] <= 0).sum(1) - (rows[:, 5:7] <= 0).sum(1)
    M.append((np.c_[dE, dT, dC], P, float(r["z"] > 0)))
rng = np.random.default_rng(0)
def fit(MM, ph):
    X = np.concatenate([x[P == ph] for x, P, z in MM]); y = np.concatenate([np.full((P == ph).sum(), z) for x, P, z in MM])
    return fit_rho.logit(X, y)[1:], len(y), float((X[:, 2] != 0).mean())
for ph, name in enumerate(("1x", "2x", "OT")):
    b, n, share = fit(M, ph)
    bs = np.array([fit([M[i] for i in rng.integers(0, len(M), len(M))], ph)[0] for _ in range(100)])
    lo, hi = np.percentile(bs, [2.5, 97.5], axis=0)
    print(f"{name}: rows {n} (crown margin != 0 on {share:.1%}) b_e {b[0]:+.3f} [{lo[0]:+.3f},{hi[0]:+.3f}] "
          f"b_t {b[1]:+.3f} [{lo[1]:+.3f},{hi[1]:+.3f}] b_c {b[2]:+.3f} [{lo[2]:+.3f},{hi[2]:+.3f}]")
