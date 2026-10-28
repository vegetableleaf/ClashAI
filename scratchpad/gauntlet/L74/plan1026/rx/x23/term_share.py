"""RX-X23 follow-up: how much of variants (i) / (ii) the TRADE term alone pays each SIM policy (uncapped, win units:
0.5 * sum_t beta_trade[phase] * d trade_t), and the committed part of a_lin (C_opp - C_own) on its own, per policy and mode.
Tests the size of the review's section-1 incentive (a_lin pays banking / leaking) directly.

    python term_share.py AN.json SIMROOT [SIMROOT ...]      (AN.json = analyze.py output: the fitted models)
"""
import json
import sys

import numpy as np

import analyze as A


def main():
    res = json.load(open(sys.argv[1]))
    beta = {v: np.array([b[-1] for b in res["models"][v]]) for v in ("i", "ii")}     # trade coefficient per phase
    runs = A.load_sim(sys.argv[2:])
    out = {}
    for (pol, mode), ms in sorted(runs.items()):
        r = {"n": len(ms)}
        for v, key in (("i", "Xi"), ("ii", "Xii")):
            tot = []
            for m in ms.values():
                d = np.diff(np.r_[0.0, m[key][:, -1]])
                ph = np.array([A.RX.phase_index(t) for t in m["t"]])
                tot.append(0.5 * float((beta[v][ph] * d).sum()))
            r[f"trade_{v}"] = float(np.mean(tot))
        cd = [m["C"][-1, 1] - m["C"][-1, 0] for m in ms.values()]
        r["committed_diff_end"] = float(np.mean(cd))                    # elixir, C_opp - C_own at the end
        r["committed_part_i"] = 0.5 * float(np.mean(beta["i"])) * r["committed_diff_end"]   # approx, phase-mean beta
        out[f"{pol}_{mode}"] = r
        print(pol, mode, {k: round(x, 4) for k, x in r.items()}, flush=True)
    json.dump(out, open(sys.argv[1].replace(".json", "_terms.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
