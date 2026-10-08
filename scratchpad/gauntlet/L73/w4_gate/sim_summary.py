"""W4 SIM summary: per arm (base / hbt = threshold + hazard below tau / haz = pure hazard) and benchmark (v2 vs S1,
v3 vs gen): wins, idle share (< 5 learner plays), paired sign test vs base, and per-phase economy / cards.
  python sim_summary.py ~/w4/sim"""
import json, math, os, sys
from collections import Counter

O = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/w4/sim")
PH = ("1x", "2x", "OT")
CHEAP = {"Skeletons", "Log"}


def load(name):
    out = {}
    for s in ("evo", "lad"):
        p = f"{O}/{name}_{s}/matches.jsonl"
        if not os.path.exists(p): continue
        for l in open(p):
            r = json.loads(l)
            if r["arm"] == "plain": out[(s, r["tag"])] = r
    return out


def score(r): return {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def wilson(k, n, z=1.96):
    if not n: return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def beh(r):
    b = r["behaviour"]
    return b if isinstance(b, dict) else eval(b)          # older writers stored a repr string


for bench in ("v2", "v3"):
    base = load(f"{bench}_base")
    for arm in ("base", "hbt", "haz"):
        R = load(f"{bench}_{arm}")
        if not R: continue
        n = len(R); w = sum(score(r) for r in R.values())
        idle = sum(r["plays_accepted"] < 5 for r in R.values()); lo, hi = wilson(idle, n)
        line = f"{bench} {arm:4s} n={n} wins {w:.0f} ({w / n:.3f})  idle(<5 plays) {idle}/{n} = {idle / n:.3f} [{lo:.2f},{hi:.2f}]"
        if arm != "base" and base:
            keys = sorted(set(base) & set(R))
            up = sum(score(R[k]) > score(base[k]) for k in keys); dn = sum(score(R[k]) < score(base[k]) for k in keys)
            hp = sum(R[k]["tower_hp_diff"] - base[k]["tower_hp_diff"] for k in keys) / max(len(keys), 1)
            line += f"  | paired vs base n={len(keys)} better {up} worse {dn} sign p={sign_p(up, dn):.4f} tower-hp delta {hp:+.0f}"
        print(line)
        for ph in PH:
            plays = mins = el_w = leak_w = 0.0; cards = Counter()
            for r in R.values():
                b = beh(r)
                if "economy" not in b:          # a 0-play game carries no economy block: count its minutes only
                    t = r["end_tick"] / 1200.0; mins += max(0.0, min(t, (2, 3, 1e9)[PH.index(ph)]) - (0, 2, 3)[PH.index(ph)])
                    continue
                e = b["economy"][ph]
                plays += e["plays"]; mins += e["minutes"]
                if e["elixir_at_play"] is not None: el_w += e["elixir_at_play"] * e["plays"]
                if b["leak_ge_9_5"][ph] is not None: leak_w += b["leak_ge_9_5"][ph] * e["minutes"]
                cards.update(b["phase_cards"][ph])
            tot = sum(cards.values())
            if not mins: continue
            print(f"    {ph}: plays/min {plays / mins:.2f}  elixir@play {el_w / max(plays, 1):.2f}  time at >=9.5 {leak_w / mins:.3f}"
                  f"  cheap(Skel+Log) {sum(cards[c] for c in CHEAP) / max(tot, 1):.3f}  "
                  + ", ".join(f"{c} {v / tot:.2f}" for c, v in cards.most_common(8)))
