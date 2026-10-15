"""SIM A/B deltas re-weighted to the LIVE opponent-archetype mix (owner 10-15 plan step 1: the SIM test set has ~35% beatdown,
live ~50%, and F1 gains nothing vs beatdown -> the unweighted SIM delta overstates the live one).
Both sides classified by weekend/archetypes.classify (SIM: the opponent's full deck; live: the enemy cards seen, as
live_history.py). Per archetype: paired win-rate delta (arm - base) over the SIM pairs; live weight = that archetype's share
of live matches since --since. Live-weighted delta = sum w_a d_a / sum w_a over archetypes present in the SIM set, SE likewise (strata independent).
    python live_weighted.py LIVE_JSON BASE_D3 ARM_D3 [--since 20261010]   (D3 = gap.py matches.jsonl paths, comma-joined)
"""
import argparse
import collections
import json
import math
import sys

sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/weekend")
import archetypes as A  # noqa: E402


def load(paths):
    rows = [json.loads(l) for p in paths.split(",") for l in open(p) if l.strip()]
    return {(r["census"], r["seed"]): r for r in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("live_json"); ap.add_argument("base"); ap.add_argument("arm")
    ap.add_argument("--since", default="20261010")
    a = ap.parse_args()
    live = [r for r in json.load(open(a.live_json)) if r[0][10:18] >= a.since]
    # live_history.py rows = [file, arch, res, seen]; live_cost.py rows = [file, res, seen] (icebow main account only)
    lw = collections.Counter(r[1] if len(r) == 4 else A.classify(r[2]) for r in live)
    base, arm = load(a.base), load(a.arm)
    assert base.keys() == arm.keys(), "unpaired"
    by = collections.defaultdict(list)
    for k, b in base.items():
        by[A.classify(b["opp_deck"])].append((arm[k]["outcome"] == "win") - (b["outcome"] == "win"))
    n_live, n_sim = sum(lw.values()), len(base)
    print(f"live matches since {a.since}: {n_live}; SIM pairs: {n_sim}")
    print(f"{'archetype':18} {'live%':>6} {'sim%':>6} {'n':>4} {'delta pp':>9} {'se':>5}")
    tot = tot_var = 0.0
    for k in sorted(set(lw) | set(by), key=lambda k: -lw[k]):
        d = by.get(k, [])
        w = lw[k] / n_live
        if not d:
            print(f"{k:18} {100*w:6.1f} {0:6.1f}    0  (no SIM pairs: weight unrepresented)"); continue
        m = sum(d) / len(d); se = math.sqrt(sum((x - m) ** 2 for x in d) / max(1, len(d) - 1) / len(d))
        tot += w * m; tot_var += (w * se) ** 2
        print(f"{k:18} {100*w:6.1f} {100*len(d)/n_sim:6.1f} {len(d):4d} {100*m:+9.1f} {100*se:5.1f}")
    allm = sum(sum(v) for v in by.values()) / n_sim
    cover = sum(lw[k] for k in by) / n_live
    tot, sd = tot / cover, math.sqrt(tot_var) / cover            # renormalised over the archetypes the SIM set covers
    print(f"\nunweighted SIM delta {100*allm:+.2f} pp; LIVE-WEIGHTED {100*tot:+.2f} pp "
          f"[{100*(tot - 1.96*sd):+.2f}, {100*(tot + 1.96*sd):+.2f}] "
          f"(weights renormalised over the {100*cover:.1f}% of live matches whose archetype the SIM set covers)")


if __name__ == "__main__":
    main()
