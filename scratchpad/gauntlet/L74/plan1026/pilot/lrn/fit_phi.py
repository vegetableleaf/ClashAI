"""LOOP-LRN: fit reward_shaping's tower_phat potential on the HF exact traces (RX-X23's hfE.npz: 50k HF replays re-driven
on crforge, rd_lib_bec5811a; per match t_i [T] ticks, L_i [T, 2, 6] running losses, meta y / date / end_tick).

    python fit_phi.py HF.npz OUT.json [--boot 50]

Model: P(win) = sigmoid(tower_phat_design(row) . c), the runtime's own design (pipeline.reward_shaping), so the fit and
the training potential cannot disagree. Rows = every 3rd trace sample (as RX-X23), decisive matches only, split by
rx/SPLIT_HF.json (train dates '0'-'3', held-out '4'; fixed before any HF fit). No intercept: antisymmetric in x, so the
HF owner's 66% win prior (RX-X23 finding 4) is not baked in. Ridge 1e-2 IRLS (rx/fit.py's, minus the intercept).
Held-out: AUC / ECE / mean pred vs obs at 60 / 120 / 180 s, both views (the owner's and the mirror), CIs over matches.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
from pipeline import r_exchange as RX                       # noqa: E402
from pipeline import reward_shaping as RS                   # noqa: E402

SPLIT = json.loads((REPO / "scratchpad/gauntlet/L74/plan1026/rx/SPLIT_HF.json").read_text())
BASE = [RX.FEATURES.index(k) for k in ("princess", "king", "king_on", "crowns")]
CK = {"60s": 1200, "120s": 2400, "180s": 3600}


def rows_of(t, L):
    """trace -> tower_phat_record-layout rows [T, 9]: own losses (4), foe losses (4), tick."""
    return np.c_[L[:, 0, BASE], L[:, 1, BASE], t]


def load(path):
    d = np.load(path)
    meta = json.loads(str(d["meta"]))
    M = []
    for i, r in enumerate(meta):
        if r["y"] not in (0, 1):
            continue
        M.append(dict(rows=rows_of(d[f"t_{i}"].astype(float), d[f"L_{i}"].astype(float)), y=int(r["y"]),
                      date=r["date"], end_tick=int(r["end_tick"])))
    return M


def mirror(rows):
    return np.c_[rows[:, 4:8], rows[:, 0:4], rows[:, 8]]


def irls(X, y, ridge=1e-2, iters=60):
    b = np.zeros(X.shape[1])
    R = ridge * np.eye(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        step = np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]) + R, X.T @ (y - p) - R @ b)
        b += step
        if np.abs(step).max() < 1e-8:
            break
    return b


def fit(M, every=3):
    X = np.concatenate([RS.tower_phat_design(m["rows"][::every]) for m in M])
    y = np.concatenate([np.full(len(m["rows"][::every]), m["y"], float) for m in M])
    return irls(X, y)


def auc(p, y):
    y = np.asarray(y, bool)
    _, inv, cnt = np.unique(p, return_inverse=True, return_counts=True)
    r = (np.cumsum(cnt) - (cnt - 1) / 2)[inv]
    return (r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum())


def ece(p, y, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum((idx == k).mean() * abs(p[idx == k].mean() - y[idx == k].mean()) for k in range(bins) if (idx == k).any()))


def calib(c, H, boot, seed=1):
    out = {}
    for ck, tick in CK.items():
        P, Y = [], []
        for m in H:
            if m["end_tick"] <= tick:
                continue
            j = max(np.searchsorted(m["rows"][:, 8], tick, side="right") - 1, 0)
            for rows, y in ((m["rows"][[j]], m["y"]), (mirror(m["rows"][[j]]), 1 - m["y"])):   # both views
                P.append(float(RS.phi_tower_phat(rows, {})[0] + 0.5)); Y.append(y)
        P, Y = np.array(P), np.array(Y, float)
        rng = np.random.default_rng(seed)
        n = len(P) // 2
        bs = []
        for _ in range(boot):                                 # resample MATCHES (both views together)
            k = rng.integers(0, n, n)
            ii = np.r_[2 * k, 2 * k + 1]
            bs.append((auc(P[ii], Y[ii]), ece(P[ii], Y[ii])))
        bs = np.array(bs)
        out[ck] = {"n_matches": n, "auc": float(auc(P, Y)), "auc_ci": np.percentile(bs[:, 0], [2.5, 97.5]).tolist(),
                   "ece": ece(P, Y), "ece_ci": np.percentile(bs[:, 1], [2.5, 97.5]).tolist(),
                   "mean_pred_owner": float(P[0::2].mean()), "mean_obs_owner": float(Y[0::2].mean())}
    return out


def main():
    path, out = sys.argv[1], Path(sys.argv[2])
    boot = int(sys.argv[sys.argv.index("--boot") + 1]) if "--boot" in sys.argv else 50
    M = load(path)
    tr = [m for m in M if SPLIT["train_dates"][0] <= m["date"] <= SPLIT["train_dates"][1]]
    H = [m for m in M if SPLIT["heldout_dates"][0] <= m["date"] <= SPLIT["heldout_dates"][1]]
    c = fit(tr)
    RS.TOWER_PHAT_C = tuple(float(x) for x in c)
    rng = np.random.default_rng(7)
    cb = np.array([fit([tr[i] for i in rng.integers(0, len(tr), len(tr))]) for _ in range(boot)])
    K = len(RS.TOWER_PHAT_KNOTS_S)
    names = [f"{f}@{s}s" for f in ("princess", "king", "king_on", "crowns") for s in RS.TOWER_PHAT_KNOTS_S]
    res = {"data": str(path), "data_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
           "split": SPLIT, "decisive": len(M), "train": len(tr), "heldout_n": len(H),
           "train_rows": int(sum(len(m["rows"][::3]) for m in tr)), "knots_s": list(RS.TOWER_PHAT_KNOTS_S),
           "coef": [round(float(x), 6) for x in c],
           "coef_table": {n: {"c": float(c[i]), "ci": np.percentile(cb[:, i], [2.5, 97.5]).tolist()}
                          for i, n in enumerate(names)},
           "heldout": calib(c, H, boot), "ridge": 1e-2, "every": 3, "n_coef": 4 * K}
    out.write_text(json.dumps(res, indent=1))
    for ck, v in res["heldout"].items():
        print(ck, f"n {v['n_matches']} auc {v['auc']:.3f} {np.round(v['auc_ci'], 3)} ece {v['ece']:.3f} "
              f"{np.round(v['ece_ci'], 3)} owner pred {v['mean_pred_owner']:.3f} obs {v['mean_obs_owner']:.3f}")
    print("coef", res["coef"])


if __name__ == "__main__":
    main()
