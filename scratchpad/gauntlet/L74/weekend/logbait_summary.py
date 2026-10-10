"""S8 summary: the old live model playing Log Bait.  python logbait_summary.py RUN_DIR[,RUN_DIR] OUT.txt"""
import collections, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from wk_stats import load, win
import archetypes as A

rows = load(sys.argv[1])
n = len(rows)
w = sum(r["outcome"] == "win" for r in rows); d = sum(r["outcome"] == "draw" for r in rows)
p = (w + 0.5 * d) / max(1, n)
hw = 1.96 * (p * (1 - p) / max(1, n)) ** 0.5
fb = collections.Counter(json.dumps(r.get("form_fallbacks")) for r in rows)
ab = collections.Counter()
for r in rows:
    for card, k in (r.get("ability_presses", {}).get(str(r["learner_side"])) or {}).items():
        ab[card] += k
by = {}
for r in rows:
    a = A.classify(r["opp_deck"]); x = by.setdefault(a, [0, 0.0]); x[0] += 1; x[1] += win(r) + 0.5 * (r["outcome"] == "draw")
L = ["S8 Log Bait baseline: old live model (towerref_w2), learner deck Evo Dart Goblin, Evo Skeleton Army, Valkyrie, Goblin Barrel, Princess, Cannon, Wall Breakers, Ice Spirit",
     f"{n} games (seeds 0:240 evo + 0:240 lad, the usual opponents T .3, live flags): win {100 * p:.1f}% [{100 * (p - hw):.1f}, {100 * (p + hw):.1f}] (W {w} D {d} L {n - w - d})",
     f"form_fallbacks per match (engine's report of cards that fell back to the base form): {dict(fb)}",
     f"hero/evo ability presses by the learner: {dict(ab)}",
     "by opponent archetype: " + ", ".join(f"{a} n {c} win {100 * s / c:.0f}%" for a, (c, s) in sorted(by.items()))]
L.append("VERDICT: baseline recorded; evo forms " + ("loaded as decked (no fallbacks reported)" if set(fb) <= {"[]", "null"} else "NOT all loaded: see form_fallbacks"))
Path(sys.argv[2]).write_text("\n".join(L) + "\n")
print("\n".join(L))
