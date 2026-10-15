"""Owner complaints 2026-10-15 ~17:30 (live F1 s76), measured per live checkpoint on icebow main-account matches:
 1. cheap immediate defence instead of saving: own elixir at play, share of plays at < 3 elixir, cheap cards (Skeletons, Log)
    played within 20 ticks of a new enemy body appearing on our half
 2. Rocket vs offensive X-Bow when far behind: in decisions where our towers trail theirs by >= 0.5 princess tower (hp-frac sum),
    the Rocket vs X-Bow plays (Rocket aimed at an enemy princess = 'tower Rocket'); the decode reason (why) is kept
 3. offensive X-Bows in both lanes: per match, lanes (left/right) of offensive X-Bows (placed within 4 tiles of the river) and
    the end state: both enemy princesses damaged (< 85%) with none destroyed
    python owner_three.py [--since 20261013]
"""
import argparse
import collections
import glob
import json
import os

LOGS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
NAMES = {"fce50ebb": "r1", "693889c3": "F1 s74", "4987c582": "F1 s76"}
CHEAP = {"Skeletons", "Log"}


def towers(p):
    t = p.get("model_towers") or []
    own = [x for x in t if x["side"] == 0 and x.get("kind", x.get("type")) != "king"]
    return t


def margin(p):
    """Our princess hp-frac sum minus theirs (dead = 0), from model_towers (side 0 = us, 1 = them, 3 per side: K, L, R)."""
    t = p.get("model_towers") or []
    mine = [x for x in t if x["side"] == 0]; theirs = [x for x in t if x["side"] == 1]
    f = lambda xs: sum((x["hp_frac"] if x["alive"] else 0.0) for x in xs[1:]) if len(xs) == 3 else None
    a, b = f(mine), f(theirs)
    return None if a is None or b is None else a - b, theirs


def run(since):
    S = collections.defaultdict(lambda: collections.Counter())
    E = collections.defaultdict(list)
    for fpath in sorted(glob.glob(LOGS + "live_play_2026*.jsonl")):
        if os.path.basename(fpath)[10:18] < since:
            continue
        with open(fpath, encoding="utf-8", errors="replace") as fh:
            head = json.loads(fh.readline())
            m = NAMES.get(str(head.get("ckpt_sha256", ""))[:8])
            if head.get("dry_run") or not m:
                continue
            first = True; seen_enemy = {}; xb_lanes = set(); last = None; ok = True; prev_tick = None
            for line in fh:
                if not line.startswith('{"event": "decision"'):
                    continue
                d = json.loads(line); p = d["public"]; dec = d.get("decision") or {}; tick = d["tick"]
                o = p["observer_side"]
                if first:
                    pr = sorted(b["max_hp"] for b in p["raw_bodies"] if b["side"] == o and b.get("kind") == 13)
                    names = {h.get("name") for h in p.get("own_hand", [])}
                    if pr != [4424, 4424] or names & {"Valkyrie", "GoblinBarrel", "Princess"}:
                        ok = False; break
                    first = False
                # new enemy bodies on our half (own frame y <= 16 tiles)
                fresh = False
                for b in p["raw_bodies"]:
                    if b["side"] == o or b["card_id"] == -1:
                        continue
                    y = (b["y"] if o == 0 else 32000 - b["y"]) / 1000
                    a = b.get("address")
                    if a not in seen_enemy:
                        seen_enemy[a] = tick
                        if y <= 16:
                            fresh = True
                if fresh:
                    S[m]["push_events"] += 1
                last = p
                if not dec.get("play"):
                    continue
                name = dec.get("name"); el = float(p.get("own_elixir_raw") or 0)
                S[m]["plays"] += 1; S[m]["elixir_sum"] += el; S[m]["low3"] += int(el < 3)
                recent_push = any(0 <= tick - t <= 20 for a, t in seen_enemy.items())
                if name in CHEAP and recent_push:
                    S[m]["cheap_quick"] += 1
                if name in CHEAP:
                    S[m]["cheap"] += 1
                mg, theirs = margin(p)
                x, y = dec["xy"][0] * 18, dec["xy"][1] * 32
                if name == "Xbow" and y >= 12:
                    xb_lanes.add(int(x >= 9))
                if mg is not None and mg <= -0.5:
                    S[m]["behind_plays"] += 1
                    if name == "Rocket":
                        tower = y >= 22 and (abs(x - 3.5) <= 3 or abs(x - 14.5) <= 3)
                        S[m]["behind_rocket_tower" if tower else "behind_rocket_units"] += 1
                        S[m]["behind_rocket_why_" + str(dec.get("why", "model"))] += 1
                    if name == "Xbow":
                        S[m]["behind_xbow"] += 1
            if not ok or last is None:
                continue
            S[m]["matches"] += 1
            mg, theirs = margin(last)
            if len(theirs) == 3:
                pr = theirs[1:]
                both_dmg = all(x["alive"] and x["hp_frac"] < 0.85 for x in pr)
                E[m].append((len(xb_lanes), both_dmg))
    for m, c in S.items():
        n = c["plays"]
        print(f"== {m}: {c['matches']} matches, {n} plays")
        print(f"   1. elixir at play {c['elixir_sum']/max(n,1):.2f}; plays at < 3 elixir {100*c['low3']/max(n,1):.1f}%; "
              f"cheap (Skeletons/Log) {100*c['cheap']/max(n,1):.1f}% of plays, {c['cheap_quick']} within 20 ticks of a fresh enemy body on our half")
        bp = c["behind_plays"]
        print(f"   2. plays while >= 0.5 tower behind: {bp}; Rocket at a tower {c['behind_rocket_tower']}, Rocket at units "
              f"{c['behind_rocket_units']}, X-Bow {c['behind_xbow']}; rocket reasons "
              f"{ {k[len('behind_rocket_why_'):]: v for k, v in c.items() if k.startswith('behind_rocket_why_')} }")
        ev = E[m]; both = [b for l, b in ev if l == 2]; one = [b for l, b in ev if l == 1]
        print(f"   3. matches with offensive X-Bows in BOTH lanes {len(both)} / {len(ev)} ({100*len(both)/max(len(ev),1):.0f}%); "
              f"of those ending with both enemy princesses damaged and none down: {sum(both)} ({100*sum(both)/max(len(both),1):.0f}%); "
              f"one-lane matches: {sum(one)}/{len(one)} ({100*sum(one)/max(len(one),1):.0f}%)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--since", default="20261013")
    run(ap.parse_args().since)
