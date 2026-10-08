"""Live value of X-Bows by class (classes.py) and Rockets, in states with an enemy princess down (live_matches.jsonl).
Associations, not effects: the states differ (who is ahead, phase, what the opponent holds).
    python scratchpad/gauntlet/L74/deadlane/value_table.py"""
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from classes import cls  # noqa: E402

M = [json.loads(l) for l in open(os.path.join(HERE, "live_matches.jsonl"))]


def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else float("nan")


for fam in ("towerref_w2", "ALL"):
    ms = [m for m in M if fam == "ALL" or m["ckpt"] == fam]
    rows = []
    for m in ms:
        for p in m["plays"]:
            if not p["down"]:
                continue
            c = "ROCKET" if p["card"] == "Rocket" else cls(p["X"], 32 - p["Y"], {"K": True, "L": "eL" not in p["down"], "R": "eR" not in p["down"]})
            rows.append(dict(p, c=c, ot_match=m["ot"]))
    n_down = sum(bool(m["eprin_down_s"]["eL"] or m["eprin_down_s"]["eR"]) for m in ms)
    print(f"\n=== {fam}: {len(ms)} matches, {n_down} with an enemy princess down")
    print("per match (all matches) by phase 1x/2x/OT: " + "; ".join(
        f"{c} {[sum(r['c'] == c and r['ph'] == ph for r in rows) for ph in ('1x', '2x', 'OT')]} = "
        f"{sum(r['c'] == c for r in rows) / len(ms):.3f}" for c in ("KONLY", "DL_LOCK", "DL_BACK", "OFF_P", "DEF", "ROCKET")))
    print("class   ph  n    life_s  king_dmg  enemy_tower_dmg  my_tower_dmg_20s  opp_spent_10s  king_awake  match_win")
    for c in ("KONLY", "DL_LOCK", "DL_BACK", "OFF_P", "DEF", "ROCKET"):
        for ph in ("1x", "2x", "OT", None):
            q = [r for r in rows if r["c"] == c and (ph is None or r["ph"] == ph)]
            if not q:
                continue
            print(f"{c:7s} {ph or 'all':3s} {len(q):4d} {mean([r.get('life') for r in q]):7.1f} {mean([r['king_dmg'] for r in q]):9.0f} "
                  f"{mean([r['tower_dmg'] for r in q]):16.0f} {mean([r['my20'] for r in q]):17.0f} {mean([r['opp10'] for r in q]):14.2f} "
                  f"{mean([r['king_kind'] == 13 for r in q]):11.2f} {mean([r['result'] == 'WIN' for r in q]):10.2f}")
