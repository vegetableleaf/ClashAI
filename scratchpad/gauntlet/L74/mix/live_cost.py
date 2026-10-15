"""Trophy cost by opponent archetype / signature card, ICEBOW on the MAIN account only (owner 10-15 plan step 1).
live_history.py mixes in the second account's bait matches; this keeps a log only if its first decision shows two own
princesses at max_hp 4424 (main account, level 15) AND no bait card in the own hand over the match. Enemy cards seen and the
inferred result follow live_history.py exactly (every 10th decision's raw_bodies; last decision's towers: crowns, then hp).
Cost of a group = n x (overall win rate - group win rate) = the matches it costs vs an average opponent (> 0 = hurts).
    python live_cost.py OUT_PREFIX [--since 20261001]   -> OUT_PREFIX.txt + OUT_PREFIX.json (rows for re-use)
"""
import argparse
import collections
import glob
import json
import math
import os
import sys

sys.path[:0] = ["C:/Users/benpe/ClashBot", "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/weekend"]
from pipeline.obs_contract import catalog_card_form  # noqa: E402
import archetypes as A  # noqa: E402

LOGS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
BAIT = {"GoblinBarrel", "SkeletonArmy", "Princess", "Valkyrie", "BlowdartGoblin", "Wallbreakers", "Cannon", "IceSpirits"}


def one(f):
    seen, hand, last, n, first, ended = set(), set(), None, 0, None, False
    for line in open(f, encoding="utf-8", errors="replace"):
        if line.startswith('{"event": "decision"'):
            n += 1
            if first is None or n % 10 == 1:
                d = json.loads(line); p = d["public"]
                if first is None:
                    first = p
                hand |= {h["name"] for h in p.get("own_hand", [])}
                for b in p["raw_bodies"]:
                    if b["side"] != p["observer_side"] and b["card_id"] != -1:
                        nm = catalog_card_form(b["card_id"])[0]
                        if nm:
                            seen.add(nm)
            last = line
        elif line.startswith('{"event": "end"') or line.startswith('{"event": "stop"'):
            ended = True
    if not ended or n < 20 or last is None or first is None:
        return None
    own = first["observer_side"]
    pr = [b["max_hp"] for b in first["raw_bodies"] if b["side"] == own and b.get("kind") == 13]
    if sorted(pr) != [4424, 4424] or hand & BAIT:
        return None
    t = json.loads(last)["public"]["model_towers"]
    mine = [x for x in t if x["side"] == 0]; theirs = [x for x in t if x["side"] == 1]
    cm, ct = sum(not x["alive"] for x in theirs), sum(not x["alive"] for x in mine)
    hm, ht = sum(x["hp_frac"] if x["alive"] else 0 for x in mine), sum(x["hp_frac"] if x["alive"] else 0 for x in theirs)
    res = 1 if (cm, hm - ht) > (ct, 0) else 0 if (cm, hm - ht) < (ct, 0) else (1 if hm > ht else 0)
    return os.path.basename(f), res, sorted({A.canon(x) for x in seen})


def table(groups, wbar, title, min_n):
    L = [f"\n== {title} (n >= {min_n}), sorted by cost = n x ({100*wbar:.1f}% - win%)"]
    rows = []
    for k, v in groups.items():
        if len(v) >= min_n:
            p = sum(v) / len(v)
            rows.append((len(v) * (wbar - p), k, len(v), p))
    for cost, k, n, p in sorted(rows, reverse=True):
        se = math.sqrt(p * (1 - p) / n)
        L.append(f"  {k:22} n {n:4d}  win {100*p:5.1f}% [{100*(p-1.96*se):5.1f}, {100*(p+1.96*se):5.1f}]  cost {cost:+6.1f}")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--since", default="20261001")
    a = ap.parse_args()
    rows = []
    for f in sorted(glob.glob(LOGS + "live_play_2026*.jsonl")):
        if os.path.basename(f)[10:18] < a.since:
            continue
        r = one(f)
        if r:
            rows.append(r)
    wbar = sum(r[1] for r in rows) / len(rows)
    arch, card = collections.defaultdict(list), collections.defaultdict(list)
    for name, res, seen in rows:
        arch[A.classify(seen)].append(res)
        arch["BEATDOWN(any tank)" if set(seen) & (A.TANK | {"threemusketeers"}) else "NOT beatdown"].append(res)
        for c in seen:
            card[c].append(res)
    L = [f"icebow MAIN-account live matches since {a.since}: {len(rows)}; overall win {100*wbar:.1f}%"]
    L += table(arch, wbar, "archetype", 10)
    L += table(card, wbar, "signature card seen", 25)
    open(a.out + ".txt", "w").write("\n".join(L) + "\n")
    json.dump(rows, open(a.out + ".json", "w"))
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
