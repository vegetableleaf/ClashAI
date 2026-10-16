"""DIAGNOSTIC ONLY (candidate, not built in reward_shaping): preflight_a3p.py's checks on the A3' + crown variant
Phi = w clip(b_e dE + b_t dT + b_c dC, +-cap), dC = foe princesses destroyed - own, b from fit_crown.py (ROWS_R1,
CROWN_FIT_R1.txt). Check i is NOT re-run for the variant (its correlation code reads TRADE2_B directly); the [i] lines
it prints are A3''s.     python preflight_a3p_crown.py"""
import sys
from pathlib import Path
import numpy as np
sys.path[:0] = [str(Path(__file__).resolve().parents[4]), str(Path(__file__).resolve().parent)]
from pipeline import reward_shaping as RS
import preflight_a3p as A
B3 = np.array([(0.066, 2.752, 0.738), (0.134, 2.754, 2.115), (0.145, 3.570, 0.0)])
def phi_crown_variant(rows, p):
    r = np.atleast_2d(np.asarray(rows, dtype=np.float64))
    dE, dT, ph = RS.trade2_parts(r)
    dC = (r[:, 8:10] <= 0).sum(1) - (r[:, 5:7] <= 0).sum(1)
    b = B3[ph]
    cap = float(p["shaping_t2_cap"])
    return float(p["shaping_t2_w"]) * np.clip(b[:, 0] * dE + b[:, 1] * dT + b[:, 2] * dC, -cap, cap)
RS.phi_trade2 = phi_crown_variant
sys.argv = sys.argv[:1]
raise SystemExit(A.main())
