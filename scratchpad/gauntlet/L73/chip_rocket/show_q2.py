import pickle, os, sys, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
f = sys.argv[1] if len(sys.argv) > 1 else "q2_live_R1e_gen_v32.pkl"
D = pickle.load(open(os.path.join(HERE, f), "rb")); rows = D["rows"]; RNG = np.random.default_rng(1)
kind = np.array([r["kind"] for r in rows]); ph = D["ph"]; cl = np.array([r["id"] for r in rows]); split = np.array([r["split"] for r in rows])
U, inv = np.unique(cl, return_inverse=True)


def ci(v, m):
    v = np.asarray(v, float)[m]; c = inv[m]
    s = np.bincount(c, v, len(U)); k = np.bincount(c, None, len(U))
    S = RNG.integers(0, len(U), (1000, len(U))); r = s[S].sum(1) / np.maximum(k[S].sum(1), 1)
    return f"{v.mean():.3f}[{np.percentile(r,2.5):.3f},{np.percentile(r,97.5):.3f}]"


for mn, out in D["res"].items():
    for sub_name, m0 in (("CHIP all", kind == "chip"), ("CHIP OT", (kind == "chip") & (ph == 2)), ("CHIP val", (kind == "chip") & (split == 1)), ("CATCH all", kind == "catch")):
        print(f"== {mn} | {sub_name} n={m0.sum()}")
        for var, R in out.items():
            if sub_name.startswith("CATCH") and var != "control": continue
            top = collections.Counter(np.array(R["top"])[m0 & np.array(R["play"])].tolist())
            tp = sum(top.values())
            line = (f"  {var:24s} gate {ci(R['gate'], m0)} P(Rk|aff) {ci(R['p_rocket'], m0)} rank1 {ci(np.array(R['rank']) == 1, m0)} "
                    f"LIVE play {ci(R['play'], m0)} LIVE Rocket {ci(R['live_rocket'], m0)} Rk-cell-on-tower {ci(R['rocket_cell_on_tower'], m0)} "
                    f"P(Rk on tower) {ci(R['p_rocket_tower'], m0)} offX-top {ci(R['xbow_top_offensive'], m0)}")
            print(line)
            if var == "control": print("     live-rule card when playing:", {k: f"{v/tp:.2f}" for k, v in top.most_common()})
        c = out["control"]
        for var, R in out.items():
            if var == "control" or sub_name.startswith("CATCH"): continue
            d = np.array(R["p_rocket"]) - np.array(c["p_rocket"]); dl = np.array(R["live_rocket"], float) - np.array(c["live_rocket"], float)
            dt = np.array(R["p_rocket_tower"]) - np.array(c["p_rocket_tower"])
            ratio = np.mean(np.array(R["p_rocket_tower"])[m0]) / max(np.mean(np.array(c["p_rocket_tower"])[m0]), 1e-9)
            print(f"     delta {var:24s} dP(Rk|aff) {ci(d, m0)} dLIVE-Rocket {ci(dl, m0)} dP(Rk on tower) {ci(dt, m0)} ratio P(Rk on tower) {ratio:.2f}")
