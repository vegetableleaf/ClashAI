"""Public-only WHEN models, numpy logistic regression with match-held-out AUC.

python pro_when.py --pros data/pros.pkl.gz --out pro_when.json --table pro_when.jsonl.gz
Input is build_pros.py's normalized matches, NOT engine replay objects. Hidden
opponent fields and opx are never read. Opponent elixir is an intentionally rough
visible-body counter: start 5, regen, subtract newly observed body value. Spawned
children and obscured plays make it uncertain; use the identical counter in SIM.
"""
import argparse
import bisect
import gzip
import json
import pickle
from pathlib import Path

import numpy as np

CARDS = ("Skeletons", "Log", "Knight", "Tornado", "IceWizard", "Tesla", "Xbow", "Rocket")
TOWERS = ("mK", "mL", "mR", "eK", "eL", "eR")
FEATURES = ("own_elixir", "opp_elixir_estimate", "enemy_value_home", "enemy_value_left", "enemy_value_right",
            *("hp_" + k for k in TOWERS), "phase_1x", "phase_2x", "phase_ot", "time_s", "crowns_us", "crowns_them",
            *("hand_" + c for c in CARDS), "seconds_since_play")


def regen(a, b):
    return sum(max(0, min(b, hi) - max(a, lo)) / spe
               for lo, hi, spe in ((0, 120, 2.81), (120, 240, 1.4), (240, float("inf"), .93)))


def opponent_estimates(states):
    """Use increases in visible value per class, not engine IDs / hidden plays.

    This deliberately shares the SIM dump's limited identity resolution: pro
    entity IDs and first-seen times do not make its estimate more informed.
    """
    seen, el, prev, out = {}, 5.0, 0.0, []
    for st in states:
        now = st[0] / 20.0
        el = min(10.0, el + regen(prev, now))
        groups = {}
        for b in st[3]:
            key = b[0]
            groups[key] = groups.get(key, 0.0) + float(b[3])
        for key, value in groups.items():
            el -= max(0.0, value - seen.get(key, 0.0))
        seen = groups
        el = max(0.0, el)
        out.append(el)
        prev = now
    return out


def features(m, i, opp_estimate, tick=None):
    st = m["S"][i]
    t = st[0] if tick is None else tick
    home = [b for b in st[3] if b[2] <= 16]
    values = [sum(float(b[3]) for b in home),
              sum(float(b[3]) for b in st[3] if b[1] < 9), sum(float(b[3]) for b in st[3] if b[1] >= 9)]
    # SIM load_sim stores fractions * 1000; pros supplies actual tower maxima.
    maximum = m.get("twmax", {})
    hp = [float(st[4].get(k) if st[4].get(k) is not None else maximum.get(k, 1000)) /
          max(1.0, float(maximum.get(k, 1000))) for k in TOWERS]
    crowns = []
    for side in ("e", "m"):
        crowns.append(3 if st[4].get(side + "K") == 0 else sum(st[4].get(side + k) == 0 for k in ("L", "R")))
    last = max((p[0] for p in m["P"] if p[0] < t), default=0)
    return [float(st[1]), float(opp_estimate), *values, *hp, float(t < 2400), float(2400 <= t < 3600),
            float(t >= 3600), t / 20.0, *crowns, *(float(c in (st[2] or ())) for c in CARDS), (t - last) / 20.0]


def table(matches):
    from xl2_selectors import harvest
    for m in matches:
        ticks = [s[0] for s in m["S"]]
        estimates = opponent_estimates(m["S"])
        for mo in harvest(m):
            i = max(0, bisect.bisect_right(ticks, mo["t"]) - 1)
            if m["S"][i][1] is None or not m["S"][i][2]:
                continue
            # Both pro sides of one replay must stay in the same partition.
            group = m["file"].rsplit("_s", 1)[0]
            yield {"match": group, **mo, "x": features(m, i, estimates[i], mo["t"])}


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def auc(y, p):
    y, p = np.asarray(y), np.asarray(p)
    if not np.any(y == 1) or not np.any(y == 0):
        return None
    # Average ranks give ties half credit without an N-positive x N-negative matrix.
    order = np.argsort(p, kind="stable")
    ranks = np.empty(len(p), float)
    _, starts, counts = np.unique(p[order], return_index=True, return_counts=True)
    for start, count in zip(starts, counts):
        ranks[order[start:start + count]] = start + (count + 1) / 2
    n = int(y.sum())
    return float((ranks[y == 1].sum() - n * (n + 1) / 2) / (n * (len(y) - n)))


def predict(model, x):
    if model["features"] != list(FEATURES):
        raise ValueError("pro_when feature schema mismatch")
    x = np.asarray(x, float)
    if x.shape[-1] != len(FEATURES) or not np.isfinite(x).all():
        raise ValueError("invalid public features")
    return sigmoid(((x - model["mean"]) / model["scale"]) @ np.asarray(model["coef"]) + model["intercept"])


def fit(rows, seed=74, l2=1.0):
    if len({r["match"] for r in rows}) < 5:
        raise ValueError("need at least five independent pro matches")
    groups = np.array(sorted({r["match"] for r in rows}))
    np.random.default_rng(seed).shuffle(groups)
    held = set(groups[:max(1, len(groups) // 5)])
    mask = np.array([r["match"] not in held for r in rows])
    x, y = np.asarray([r["x"] for r in rows], float), np.asarray([r["target"] for r in rows], float)
    if not np.isfinite(x).all() or x.shape[1] != len(FEATURES):
        raise ValueError("invalid training features")
    if len(set(y[mask])) != 2:
        raise ValueError("training partition needs positive and negative examples")
    mean, scale = x[mask].mean(0), x[mask].std(0)
    scale[scale < 1e-6] = 1.0
    z = np.column_stack([np.ones(mask.sum()), (x[mask] - mean) / scale])
    w = np.zeros(z.shape[1])
    penalty = np.diag([0.0] + [l2] * (len(w) - 1))
    for _ in range(80):
        p = sigmoid(z @ w)
        grad = z.T @ (p - y[mask]) + penalty @ w
        hess = (z.T * (p * (1 - p))) @ z + penalty + np.eye(len(w)) * 1e-8
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.max(np.abs(step)) < 1e-7:
            break
    model = dict(features=list(FEATURES), mean=mean.tolist(), scale=scale.tolist(), coef=w[1:].tolist(), intercept=float(w[0]),
                 l2=l2, seed=seed, train_matches=sorted(set(groups) - held), heldout_matches=sorted(held),
                 train_n=int(mask.sum()), heldout_n=int((~mask).sum()))
    model["heldout_auc"] = auc(y[~mask], predict(model, x[~mask]))
    model["heldout_positive"] = int(y[~mask].sum())
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pros", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--table", required=True)
    a = ap.parse_args()
    with gzip.open(a.pros, "rb") as f:
        rows = list(table(pickle.load(f)))
    with gzip.open(a.table, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    models, errors = {}, {}
    for dr in ("D" + str(i) for i in range(1, 10)):
        try:
            models[dr] = fit([r for r in rows if r["drill"] == dr])
        except ValueError as ex:
            errors[dr] = str(ex)
    result = dict(schema=1, features=list(FEATURES), models=models, unavailable=errors, source=str(Path(a.pros).resolve()))
    Path(a.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: {"n": v["train_n"], "heldout_auc": v["heldout_auc"]} for k, v in models.items()}))
    if errors:
        raise SystemExit("Unfittable drills (recorded, never replaced by invented coefficients): " + str(errors))


if __name__ == "__main__":
    main()
