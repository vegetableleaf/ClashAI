"""X1 revision candidates (coordinator 10-28): each = tower-only terms + the candidate term(s), phase-split logistic,
held out by DATE (SPLIT.json). Kept only if the AUC gain over tower-only has a CI excluding 0 AND the candidate's
coefficient CI excludes 0 with the expected sign (+, every term is oriented "good for us").

    python candidates.py MATCHES.npz BATTLELOG.jsonl OUT.json [--boot 200] [--traces frame|all]
MATCHES.npz from build.py (needs C_*/LT_*: committed elixir, leak under threat). All terms zero-sum (ours - theirs),
public information only, no banked-elixir term.
  base         princess, king, king_on, crowns (tower-only)
  ref_elixir   running elixir destroyed (the X1 term)          ref_leak  running leak (the X1 term)
  a_lin        (destroyed by us - committed by us) - (destroyed by them - committed by them), running
  a_eng        sum over completed engagements of tanh(trade / 4), trade = a_lin's change inside the engagement;
               engagement = run of activity (a commit, a destruction or tower damage) with gaps < 5 s, credited 5 s
               after it ends
  b_eff        destroyed by us / committed by them  -  destroyed by them / committed by us   (committed floored at 5)
  c_leak_thr   leak only while the other side has a body on the leaking side's half (theirs - ours)
  d_conv10/20  tower damage dealt x positive net elixir destroyed in the previous 10 / 20 s (ours - theirs)
"""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fit as FIT  # noqa: E402

RX = FIT.RX
F = list(RX.FEATURES)
BASE = [F.index(k) for k in ("princess", "king", "king_on", "crowns")]
GAP = 5                       # seconds of quiet that end an engagement (rows are 1 s apart)


def engagements(t, own_net, opp_net, active):
    """running sum of tanh(trade/4) per completed engagement; credited GAP s after the last active row."""
    out = np.zeros(len(t))
    acc, start, last = 0.0, None, None
    for k in range(len(t)):
        if active[k]:
            start = k if start is None else start
            last = k
        if start is not None and (t[k] - t[last]) >= GAP * 20:
            tr = (own_net[last] - own_net[max(start - 1, 0)]) - (opp_net[last] - opp_net[max(start - 1, 0)])
            acc += np.tanh(tr / 4.0)
            start = last = None
        out[k] = acc
    return out


def conversion(t, dmg_by_own, dmg_by_opp, net, window_s):
    """sum over rows of tower damage dealt x max(0, own net destroyed in the last window), minus the mirror."""
    out = np.zeros(len(t))
    acc = 0.0
    j = 0
    for k in range(1, len(t)):
        while t[j] < t[k] - window_s * 20:
            j += 1
        w = net[k] - net[j]
        acc += (dmg_by_own[k] - dmg_by_own[k - 1]) * max(0.0, w) - (dmg_by_opp[k] - dmg_by_opp[k - 1]) * max(0.0, -w)
        out[k] = acc
    return out


def terms(t, L, C, LT):
    X = RX.features(L)
    dest_own, dest_opp = L[:, 1, 4], L[:, 0, 4]                       # destroyed BY us / BY them
    own_net, opp_net = dest_own - C[:, 0], dest_opp - C[:, 1]
    act = np.r_[True, (np.abs(np.diff(C, axis=0)).sum(1) + np.abs(np.diff(L[:, :, [0, 1, 4]].reshape(len(t), -1),
                                                                            axis=0)).sum(1)) > 1e-6]
    net = dest_own - dest_opp
    dmg_own = L[:, 1, 0] + L[:, 1, 1]                                  # tower damage dealt by us (tower units)
    dmg_opp = L[:, 0, 0] + L[:, 0, 1]
    return {
        "ref_elixir": X[:, F.index("elixir")],
        "ref_leak": X[:, F.index("leak")],
        "a_lin": own_net - opp_net,
        "a_eng": engagements(t, own_net, opp_net, act),
        "b_eff": dest_own / np.maximum(C[:, 1], 5) - dest_opp / np.maximum(C[:, 0], 5),
        "c_leak_thr": LT[:, 1] - LT[:, 0],
        "d_conv10": conversion(t, dmg_own, dmg_opp, net, 10),
        "d_conv20": conversion(t, dmg_own, dmg_opp, net, 20),
    }


CANDS = {"ref_elixir": ["ref_elixir"], "ref_leak": ["ref_leak"], "a_lin": ["a_lin"], "a_eng": ["a_eng"],
         "b_eff": ["b_eff"], "c_leak_thr": ["c_leak_thr"], "c_vs_overall": ["c_leak_thr", "ref_leak"],
         "d_conv10": ["d_conv10"], "d_conv20": ["d_conv20"]}


def load(path, battlelog):
    d = np.load(path)
    meta = json.loads(str(d["meta"]))
    M = []
    for i, r in enumerate(meta):
        if FIT.TRACES == "frame" and r["trace"] != "frame":
            continue
        L = d[f"L_{i}"].astype(float)
        T = terms(d[f"t_{i}"], L, d[f"C_{i}"].astype(float), d[f"LT_{i}"].astype(float))
        M.append(dict(r, t=d[f"t_{i}"], base=RX.features(L)[:, BASE], T=T))
    for i, b in FIT.join(M, FIT.battlelog(battlelog)).items():            # the game's verdict where matched
        if b["cm"] != b["co"]:
            M[i]["y"] = int(b["cm"] > b["co"])
    return [m for m in M if m["y"] in (0, 1)]


def design(M, names):
    return [dict(t=m["t"], y=m["y"], end_tick=m["end_tick"],
                 X=np.c_[m["base"], *[m["T"][n] for n in names]] if names else m["base"]) for m in M]


def _init(trd):
    global TRD
    TRD = trd


def _boot(seed):
    rng = np.random.default_rng(seed)
    return FIT.fit_all([TRD[i] for i in rng.integers(0, len(TRD), len(TRD))])


def evaluate(tr, H, names, boot):
    trd, Hd = design(tr, names), design(H, names)
    B = FIT.fit_all(trd)
    B0 = FIT.fit_all(design(tr, []))
    with mp.Pool(min(32, mp.cpu_count()), initializer=_init, initargs=(trd,)) as pool:   # data shipped once per worker
        BS = np.asarray(pool.map(_boot, range(boot)))
    res = {"coef": {}}
    for ph, (pn, _, _) in enumerate(RX.PHASES):
        res["coef"][pn] = {n: {"b": float(B[ph][1 + len(BASE) + k]), "ci": FIT.ci(BS[:, ph, 1 + len(BASE) + k])}
                           for k, n in enumerate(names)}
    H0 = design(H, [])
    for name, tick in list(FIT.CK.items()):
        P, P0, Y = [], [], []
        for m, m0 in zip(Hd, H0):
            x, x0 = FIT.at(m, tick), FIT.at(m0, tick)
            if x is None:
                continue
            ph = RX.phase_index(tick)
            P.append(FIT.predict(B, x, ph)); P0.append(FIT.predict(B0, x0, ph)); Y.append(m["y"])
        P, P0, Y = map(np.asarray, (P, P0, Y))
        rng = np.random.default_rng(1)
        g = []
        for _ in range(1000):
            i = rng.integers(0, len(Y), len(Y))
            g.append(FIT.auc(P[i], Y[i]) - FIT.auc(P0[i], Y[i]))
        res[name] = {"n": int(len(Y)), "auc": FIT.auc(P, Y), "auc_base": FIT.auc(P0, Y),
                     "gain": FIT.auc(P, Y) - FIT.auc(P0, Y), "gain_ci": FIT.ci(g)}
    gain_ok = any(res[k]["gain_ci"][0] > 0 for k in FIT.CK)
    sign_ok = {n: [res["coef"][pn][n]["ci"][0] > 0 for pn, _, _ in RX.PHASES] for n in names}
    sign_bad = {n: [res["coef"][pn][n]["ci"][1] < 0 for pn, _, _ in RX.PHASES] for n in names}
    res["kept"] = bool(gain_ok and all(any(v) for v in sign_ok.values()) and not any(any(v) for v in sign_bad.values()))
    res["sign_ci_positive_by_phase"] = sign_ok
    return res


def main():
    a = sys.argv[1:]
    boot = int(a[a.index("--boot") + 1]) if "--boot" in a else 200
    M = load(a[0], a[1])
    sp = FIT.SPLIT
    tr = [m for m in M if sp["train_dates"][0] <= m["date"] <= sp["train_dates"][1]]
    H = [m for m in M if sp["heldout_dates"][0] <= m["date"] <= sp["heldout_dates"][1]]
    out = {"traces": FIT.TRACES, "train": len(tr), "heldout": len(H), "split": sp}
    if True:
        for c, names in CANDS.items():
            out[c] = r = evaluate(tr, H, names, boot)
            print(c, "KEPT" if r["kept"] else "not kept",
                  {k: f"{r[k]['gain']:+.4f} [{r[k]['gain_ci'][0]:+.4f},{r[k]['gain_ci'][1]:+.4f}]" for k in FIT.CK},
                  {pn: {n: f"{v['b']:+.4f} [{v['ci'][0]:+.4f},{v['ci'][1]:+.4f}]" for n, v in cc.items()}
                   for pn, cc in r["coef"].items()}, flush=True)
    json.dump(out, open(a[2], "w"), indent=1)


if __name__ == "__main__":
    main()
