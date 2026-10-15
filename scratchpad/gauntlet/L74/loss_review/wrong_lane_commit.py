"""Owner complaint 2026-10-15 ~18:00 (live F1 u250): "commited 9 elixir on the other lane when there was a megaknight and witch about
to take its tower, which is already very low". Counts, per live checkpoint (icebow main account), WRONG-LANE COMMITS:
a 10-second window in which we spend >= COMMIT elixir on plays in one lane (own-frame x side of 9 tiles, centre +-1.5 excluded)
while the enemy has >= THREAT elixir of troops on OUR half in the OTHER lane and our princess in that lane is below LOW hp_frac.
Enemy value = catalog elixir of visible enemy troop bodies (hp-scaled), from the reader bodies; our tower hp from model_towers.
    python wrong_lane_commit.py [--since 20261013] [--list 5]     (prints the worst events with log + tick for review)
"""
import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, "C:/Users/benpe/ClashBot")
from pipeline.obs_contract import _catalog_names  # noqa: E402

LOGS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
NAMES = {"fce50ebb": "r1", "693889c3": "F1 s74 u65", "4987c582": "F1 s76", "00c845c0": "F1 u250"}
COST = {"Xbow": 6, "Tesla": 4, "IceWizard": 3, "Tornado": 3, "Rocket": 6, "Knight": 3, "Log": 2, "Skeletons": 1}
COMMIT, THREAT, LOW, WIN_T = 6.0, 7.0, 0.5, 200


def cost_of(name, _cache={}):
    """Catalog name (CamelCase) -> elixir via pipeline.opp_elixir_count.card_cost (snake_case keys); unknown -> 3.0."""
    if name not in _cache:
        import re
        from pipeline.opp_elixir_count import card_cost
        c = card_cost(re.sub(r"(?<!^)(?=[A-Z])", "_", str(name)).lower())
        _cache[name] = 3.0 if c is None else c
    return _cache[name]


def run(since, n_list):
    names = _catalog_names()
    S = collections.defaultdict(collections.Counter); events = []
    for f in sorted(glob.glob(LOGS + "live_play_2026*.jsonl")):
        if os.path.basename(f)[10:18] < since:
            continue
        with open(f, encoding="utf-8", errors="replace") as fh:
            head = json.loads(fh.readline()); m = NAMES.get(str(head.get("ckpt_sha256", ""))[:8])
            if head.get("dry_run") or not m:
                continue
            plays = []; first = True; ok = True; flagged = False; ticks = 0
            for line in fh:
                if not line.startswith('{"event": "decision"'):
                    continue
                d = json.loads(line); p = d["public"]; dec = d.get("decision") or {}; t = d["tick"]; o = p["observer_side"]
                if first:
                    pr = sorted(b["max_hp"] for b in p["raw_bodies"] if b["side"] == o and b.get("kind") == 13)
                    if pr != [4424, 4424]:
                        ok = False; break
                    first = False
                ticks += 1
                if dec.get("play"):
                    x = dec["xy"][0] * 18
                    if abs(x - 9) > 1.5:
                        plays.append((t, int(x >= 9), COST.get(dec.get("name"), 3), dec.get("name")))
                if flagged:
                    continue
                tw = {x.get("lane"): x for x in (p.get("model_towers") or []) if x["side"] == 0 and x.get("kind") == "princess"}
                threat = [0.0, 0.0]; who = [[], []]
                for b in p["raw_bodies"]:
                    if b["side"] == o or b["card_id"] == -1 or b.get("kind") not in (14, 15, 12):
                        continue
                    bx, by = ((b["x"], b["y"]) if o == 0 else (18000 - b["x"], 32000 - b["y"]))
                    if by > 16000 or abs(bx / 1000 - 9) <= 1.5:
                        continue
                    nm = names.get(int(b["card_id"]), str(b["card_id"]))
                    v = cost_of(nm) * max(0.0, b["hp"]) / max(1.0, b["max_hp"])
                    lane = int(bx >= 9000); threat[lane] += v; who[lane].append(nm)
                for lane in (0, 1):
                    t_ow = tw.get("L" if lane == 0 else "R")
                    if threat[lane] < THREAT or not t_ow or not t_ow["alive"] or t_ow["hp_frac"] >= LOW:
                        continue
                    other = sum(c for (pt, l, c, _) in plays if l != lane and t - WIN_T <= pt <= t)
                    if other >= COMMIT:
                        flagged = True
                        S[m]["events"] += 1
                        events.append((other, threat[lane], m, os.path.basename(f), t, t_ow["hp_frac"], sorted(set(who[lane]))[:5],
                                       [n for (pt, l, c, n) in plays if l != lane and t - WIN_T <= pt <= t]))
                        break
            if ok and ticks:
                S[m]["matches"] += 1
    for m, c in S.items():
        print(f"{m:12} matches {c['matches']:4d}  matches with a wrong-lane commit {c['events']:4d} ({100*c['events']/max(c['matches'],1):.1f}%)")
    print(f"\nworst {n_list} (our elixir spent in the other lane in the last {WIN_T} ticks, enemy value on our half in the threatened lane):")
    for e in sorted(events, reverse=True)[:n_list]:
        print(f"  {e[2]:10} {e[3]} tick {e[4]}: spent {e[0]:.0f} other lane (cards {e[7]}) while {e[1]:.1f} elixir of {e[6]} "
              f"was on our half at our {e[5]:.2f}-hp tower")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--since", default="20261013"); ap.add_argument("--list", type=int, default=8)
    a = ap.parse_args(); run(a.since, a.list)
