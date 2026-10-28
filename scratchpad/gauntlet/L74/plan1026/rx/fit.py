"""P3-RX fit + gate X1: phase-split logistic of the real match result on R_exchange running totals.

    python fit.py MATCHES.npz BATTLELOG.jsonl OUT_DIR [--boot 200] [--traces frame|all]
--traces frame (default): only matches with 2-tick frames; all: also per-decision traces (sparser; their leak is
biased, see consistency.py), reported as a sensitivity fit.
MATCHES.npz from build.py; SPLIT.json (this directory) fixes the date split and the opp-leak rule BEFORE fitting.
Writes OUT_DIR/results.json (coefficients, CIs, exchange rates, X1 metrics, reliability tables, leak validation)
and prints a summary. CIs: bootstrap over MATCHES (rows within a match are not independent).
"""
import datetime as dt
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4]))
from pipeline import r_exchange as RX  # noqa: E402

import os  # noqa: E402
SPLIT = json.load(open(os.environ.get("RX_SPLIT", HERE / "SPLIT.json")))      # RX_SPLIT: SPLIT_HF.json for HF traces
F = list(RX.FEATURES)
EXPECT = {"princess": +1, "elixir": +1, "leak": +1}      # x = opp loss - own loss: all three should be > 0
TRACES = sys.argv[sys.argv.index("--traces") + 1] if "--traces" in sys.argv else "frame"
TOWER_ONLY = [F.index(k) for k in ("princess", "king", "king_on", "crowns")]
CK = {"60s": 1200, "120s": 2400, "180s": 3600}


def logit(X, y, ridge=1e-2, iters=60):
    X = np.c_[np.ones(len(X)), X]
    b = np.zeros(X.shape[1])
    R = ridge * np.eye(X.shape[1]); R[0, 0] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        step = np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]) + R, X.T @ (y - p) - R @ b)
        b += step
        if np.abs(step).max() < 1e-8:
            break
    return b


def auc(p, y):
    y = np.asarray(y, bool)
    if y.all() or (~y).all():
        return np.nan
    _, inv, cnt = np.unique(p, return_inverse=True, return_counts=True)
    r = (np.cumsum(cnt) - (cnt - 1) / 2)[inv]              # ranks, ties averaged
    return (r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum())


def ece(p, y, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    tab = []
    e = 0.0
    for k in range(bins):
        m = idx == k
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
            tab.append([k / bins, (k + 1) / bins, int(m.sum()), float(p[m].mean()), float(y[m].mean())])
    return e, tab


def ci(a):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))] if len(a) else [None, None]


def load(path, opp_leak):
    d = np.load(path)
    meta = json.loads(str(d["meta"]))
    M = []
    for i, r in enumerate(meta):
        if TRACES == "frame" and r["trace"] != "frame":
            continue
        L = d[f"L_{i}"].astype(float)
        if not opp_leak:
            L[:, 1, F.index("leak")] = 0.0                 # leak = our own leak only
        M.append(dict(r, t=d[f"t_{i}"], X=RX.features(L), own_leak=float(L[-1, 0, -1]), opp_leak=float(L[-1, 1, -1])))
    return M


def battlelog(path):
    out = []
    for line in open(path, encoding="utf8"):
        if not line.strip():
            continue
        b = json.loads(line)["battle"]
        t = dt.datetime.strptime(b["battleTime"][:15], "%Y%m%dT%H%M%S") - dt.timedelta(hours=4)   # UTC -> EDT
        me, op = b["team"][0], b["opponent"][0]
        out.append(dict(t=t, type=b["type"], cm=me.get("crowns"), co=op.get("crowns"),
                        leak_me=me.get("elixirLeaked"), leak_op=op.get("elixirLeaked")))
    return out


def join(M, BL):
    """one-to-one: a battle whose start (EDT) is 0..6 min after the log file's start time, nearest first."""
    used, pairs = set(), {}
    if not BL:
        return pairs
    for i, m in enumerate(M):
        ft = dt.datetime.strptime(m["file"][10:25], "%Y%m%d_%H%M%S")
        c = [(abs((b["t"] - ft).total_seconds() - 60), j) for j, b in enumerate(BL)
             if j not in used and -60 <= (b["t"] - ft).total_seconds() <= 360]
        if c:
            j = min(c)[1]; used.add(j); pairs[i] = BL[j]
    return pairs


def rows(M, phase):
    lo, hi = RX.PHASES[phase][1:]
    X, y, g = [], [], []
    for k, m in enumerate(M):
        s = (m["t"] >= lo) & (m["t"] < hi)
        X.append(m["X"][s]); y.append(np.full(s.sum(), m["y"])); g.append(np.full(s.sum(), k))
    return np.concatenate(X), np.concatenate(y).astype(float), np.concatenate(g)


def fit_all(M, cols=None):
    B = []
    for ph in range(3):
        X, y, _ = rows(M, ph)
        B.append(logit(X if cols is None else X[:, cols], y))
    return B


def _boot(args):
    M, seed = args
    rng = np.random.default_rng(seed)
    return fit_all([M[i] for i in rng.integers(0, len(M), len(M))])


def at(m, tick):
    """features at the last sampled row <= tick (None if the match ended before tick)."""
    if m["end_tick"] <= tick:
        return None
    j = np.searchsorted(m["t"], tick, side="right") - 1
    return m["X"][max(j, 0)]


def predict(B, x, ph, cols=None):
    b = B[ph]
    z = b[0] + (x if cols is None else x[cols]) @ b[1:]
    return 1 / (1 + np.exp(-z))


def x1(H, B, Bt, boot, seed=1):
    out = {}
    for name in list(CK) + ["end"]:
        P, Pt, Y, XX = [], [], [], []
        for m in H:
            if name == "end":
                x, ph = m["X"][-1], RX.phase_index(int(m["t"][-1]))
            else:
                x, ph = at(m, CK[name]), RX.phase_index(CK[name])
            if x is None:
                continue
            P.append(predict(B, x, ph)); Pt.append(predict(Bt, x, ph, TOWER_ONLY)); Y.append(m["y"]); XX.append(x)
        P, Pt, Y, XX = map(np.asarray, (P, Pt, Y, XX))
        rng = np.random.default_rng(seed)
        bs = []
        for _ in range(boot):
            i = rng.integers(0, len(Y), len(Y))
            bs.append((auc(P[i], Y[i]), ece(P[i], Y[i])[0], auc(P[i], Y[i]) - auc(Pt[i], Y[i])))
        bs = np.asarray(bs)
        e, tab = ece(P, Y)
        out[name] = {"n": int(len(Y)), "wins": int(Y.sum()), "auc": auc(P, Y), "auc_ci": ci(bs[:, 0]),
                     "ece": e, "ece_ci": ci(bs[:, 1]), "auc_tower_only": auc(Pt, Y),
                     "auc_gain_vs_tower_only": auc(P, Y) - auc(Pt, Y), "auc_gain_ci": ci(bs[:, 2]),
                     "reliability": tab,
                     "univariate_auc": {f: auc(XX[:, k], Y) for k, f in enumerate(F)}}
    return out


def main():
    a = sys.argv[1:]
    boot = int(a[a.index("--boot") + 1]) if "--boot" in a else 200
    out = Path(a[2]); out.mkdir(parents=True, exist_ok=True)
    res = {"split": SPLIT, "traces": TRACES}

    # 1. labels + leak validation against the public battle log (decides the pre-registered opp-leak rule)
    M = load(a[0], opp_leak=True)
    BL = battlelog(a[1])
    pairs = join(M, BL)
    agree = [(m["y"], int(b["cm"] > b["co"])) for i, b in pairs.items() if (m := M[i])["y"] >= 0 and b["cm"] != b["co"]]
    v = np.array([(M[i]["own_leak"], M[i]["opp_leak"], b["leak_me"], b["leak_op"]) for i, b in pairs.items()
                  if b["leak_me"] is not None and b["leak_op"] is not None], float).reshape(-1, 4)
    r_own = float(np.corrcoef(v[:, 0], v[:, 2])[0, 1]) if len(v) > 2 else None
    r_opp = float(np.corrcoef(v[:, 1], v[:, 3])[0, 1]) if len(v) > 2 else None
    use_opp = (r_opp is not None and r_opp >= 0.7) or not BL      # no battle log = engine traces: exact elixir
    res["battlelog"] = {"battles": len(BL), "matched": len(pairs), "label_checked": len(agree),
                        "label_agree": int(sum(p == q for p, q in agree)),
                        "leak_n": int(len(v)), "own_leak_r": r_own, "opp_leak_r": r_opp,
                        "own_leak_mae": float(np.abs(v[:, 0] - v[:, 2]).mean()) if len(v) else None,
                        "opp_leak_mae": float(np.abs(v[:, 1] - v[:, 3]).mean()) if len(v) else None,
                        "mean_own_log_vs_battlelog": v[:, [0, 2]].mean(0).tolist() if len(v) else None,
                        "mean_opp_est_vs_battlelog": v[:, [1, 3]].mean(0).tolist() if len(v) else None,
                        "opp_leak_used": bool(use_opp)}
    # battle-log labels override the log's where they are decisive (the game's own verdict incl. tiebreak)
    for i, b in pairs.items():
        if b["cm"] != b["co"]:
            M[i]["y"], M[i]["label_src"] = int(b["cm"] > b["co"]), "battlelog"
    if not use_opp:
        M = load(a[0], opp_leak=False)
        for i, b in pairs.items():
            if b["cm"] != b["co"]:
                M[i]["y"], M[i]["label_src"] = int(b["cm"] > b["co"]), "battlelog"
    M = [m for m in M if m["y"] in (0, 1)]
    tr = [m for m in M if SPLIT["train_dates"][0] <= m["date"] <= SPLIT["train_dates"][1]]
    H = [m for m in M if SPLIT["heldout_dates"][0] <= m["date"] <= SPLIT["heldout_dates"][1]]
    res["data"] = {"decisive": len(M), "train": len(tr), "heldout": len(H),
                   "train_winrate": float(np.mean([m["y"] for m in tr])),
                   "heldout_winrate": float(np.mean([m["y"] for m in H])),
                   "rows_per_phase_train": [int(len(rows(tr, ph)[1])) for ph in range(3)],
                   "body_known_frac_mean": float(np.mean([m["body_known_frac"] for m in M]))}

    # 2. fit + match bootstrap
    B = fit_all(tr)
    Bt = fit_all(tr, TOWER_ONLY)
    with mp.Pool(min(32, mp.cpu_count())) as pool:
        BS = np.asarray(pool.map(_boot, [(tr, s) for s in range(boot)]))         # [boot, 3, 1 + F]
    ei, pi = 1 + F.index("elixir"), 1 + F.index("princess")
    res["coef"] = {}
    for ph, (name, _, _) in enumerate(RX.PHASES):
        c = {"intercept": float(B[ph][0])}
        for k, f in enumerate(F):
            c[f] = {"b": float(B[ph][1 + k]), "ci": ci(BS[:, ph, 1 + k])}
        rho = BS[:, ph, pi] / np.where(BS[:, ph, ei] > 0, BS[:, ph, ei], np.nan)
        c["elixir_per_princess_tower"] = {"rho": float(B[ph][pi] / B[ph][ei]), "ci": ci(rho)}
        c["signs_ok"] = {f: bool(np.sign(B[ph][1 + F.index(f)]) == s and
                                 (np.array(ci(BS[:, ph, 1 + F.index(f)])) * s > 0).all()) for f, s in EXPECT.items()}
        res["coef"][name] = c
    res["beta"] = [list(map(float, b[1:])) for b in B]      # r_exchange.step_rewards beta [3, F]

    # 3. gate X1 on the held-out dates
    res["x1"] = x1(H, B, Bt, boot=1000)
    json.dump(res, open(out / "results.json", "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("data", "battlelog")}, indent=1))
    for name, c in res["coef"].items():
        print(name, {f: f"{c[f]['b']:+.3f} [{c[f]['ci'][0]:+.3f},{c[f]['ci'][1]:+.3f}]" for f in F},
              "rho", f"{c['elixir_per_princess_tower']['rho']:.1f}", c["elixir_per_princess_tower"]["ci"], c["signs_ok"])
    for name, r in res["x1"].items():
        print(name, f"n {r['n']} auc {r['auc']:.3f} {np.round(r['auc_ci'], 3)} ece {r['ece']:.3f} "
              f"{np.round(r['ece_ci'], 3)} tower-only {r['auc_tower_only']:.3f} gain {r['auc_gain_vs_tower_only']:+.3f} "
              f"{np.round(r['auc_gain_ci'], 3)}", "univariate", {f: round(v, 3) for f, v in r["univariate_auc"].items()})


if __name__ == "__main__":
    main()
