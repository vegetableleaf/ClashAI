"""A3' exchange rate (HANDOFF 10-15 ~03:30): how much is one princess tower of HP worth in elixir, by match phase?
Logistic P(win) ~ b0 + b_e * elixir margin + b_t * tower margin per decision row of the dumped audit matches
(preflight_a1a2.py audit --dump-rows; rows_pod.sh), fit separately per phase; rho = b_t / b_e (elixir per princess-tower
of HP). 95% CIs by bootstrapping MATCHES (rows within a match are not independent).
  elixir margin = (E_own + V_own) - (E_opp + V_opp)                      (trade_record row; the audit's E_opp is TRUE)
  tower margin  = sum own princess hp frac + K x own king frac - same for the foe (princess units, K = king/princess hp)
    python fit_rho.py ROWS.jsonl [ROWS.jsonl ...]
    python fit_rho.py --foe-king 0 ROWS.jsonl     A3' (reward_shaping phi_trade2): the FOE king's hp left out of the
                                                 tower margin (A1's king weight 0; doctrine: never the king tower)
"""
import json
import sys

import numpy as np

K = 4824 / 3052                     # RoyaleSim level-11 king / princess max hp (reward_shaping.KING_PER_PRINCESS)
K_FOE = K                           # weight of the FOE king in the tower margin (--foe-king; A3' uses 0)
PHASES = (("1x", 0, 2400), ("2x", 2400, 3600), ("OT", 3600, 10 ** 9))


def load(paths):
    M = []
    for p in paths:
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            if r["z"] == 0:
                continue
            keep = np.asarray(r["keep"], bool)
            tr, ts, t = (np.asarray(r[k], float)[keep] for k in ("tr_rows", "ts_rows", "ticks"))
            e = tr[:, 0] + tr[:, 1] - tr[:, 2] - tr[:, 3]
            tw = (ts[:, 1] + ts[:, 2] + K * ts[:, 0]) - (ts[:, 4] + ts[:, 5] + K_FOE * ts[:, 3])
            M.append((np.c_[e, tw, t], float(r["z"] > 0)))
    return M


def logit(X, y, iters=50):
    """Newton-Raphson logistic regression with an intercept (tiny ridge for stability) -> coefficients."""
    X = np.c_[np.ones(len(X)), X]
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        H = X.T @ (X * (p * (1 - p))[:, None]) + 1e-6 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p) - 1e-6 * b)
        b += step
        if np.abs(step).max() < 1e-9:
            break
    return b


def fit(M, lo, hi):
    X, y = [], []
    for rows, z in M:
        m = (rows[:, 2] >= lo) & (rows[:, 2] < hi)
        X.append(rows[m, :2]); y.append(np.full(m.sum(), z))
    X, y = np.concatenate(X), np.concatenate(y)
    return logit(X, y), len(y)


def main(paths, boot=200, seed=0):
    M = load(paths)
    print(f"{len(M)} decisive matches, {sum(len(r) for r, _ in M)} rows")
    rng = np.random.default_rng(seed)
    for name, lo, hi in PHASES:
        (b0, be, bt), n = fit(M, lo, hi)
        bs = []
        for _ in range(boot):
            (_, e, t), _ = fit([M[i] for i in rng.integers(0, len(M), len(M))], lo, hi)
            bs.append((e, t, t / e if e > 0 else np.nan))
        bs = np.asarray(bs)
        ci = lambda c: np.nanpercentile(bs[:, c], [2.5, 97.5])
        print(f"{name}: rows {n:6d}  b_elixir {be:+.3f} {ci(0).round(3)}  b_tower {bt:+.3f} {ci(1).round(3)}  "
              f"rho = elixir per princess-tower {bt / be:+.1f} {ci(2).round(1)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--foe-king"]:
        K_FOE, args = float(args[1]), args[2:]
    main(args)
