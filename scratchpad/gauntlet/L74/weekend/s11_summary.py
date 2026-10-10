"""S11 summary.  python s11_summary.py EVAL_DIR OUT.txt TRAIN_LOG
Paired (same seeds, sides, opponent decks) Log Bait base-deck games, 0:240 evo + 0:240 lad = 480 each."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wk_compare as C

ev, out, tlog = sys.argv[1:4]
L = ["S11 Log Bait specialist (RL from the generalist fast base rseries_r3c_u0030_barrel, learner deck FIXED to Log Bait, ALL BASE forms: Dart Goblin, Skeleton Army, "
     "Valkyrie, Goblin Barrel, Princess, Cannon, Wall Breakers, Ice Spirit)",
     "opponents: league (latest/older/init snapshots + s1) on census decks weighted toward the unfavourable archetypes (RL alpha 1.0 / floor 0); 60 updates, checkpoint every 10; "
     "dense-defence recipe (run_arm.sh, no branching), seed 11",
     "eval: both sides play Log Bait; opponents gen v1 T .3 on the evo + ladder census; 480 paired games each; decode = tau .35 + --own-effects only (the bait LIVE_OPTIONS have no X-Bow / spell rule)",
     "refs: base = the untrained fast base (no add-ons); gen = the untrained live generalist (base + CellRefine / TowerRefine heads, towerref_w2)"]
try:
    last = [x for x in open(tlog, errors="replace") if re.search(r"\[rl\].*\bu\w*\W*\d+", x)][-1].strip()
    L.append("training log, last update line: " + last[:300])
except Exception:
    L.append("training log: no update line found")
for r in ("base", "gen"):
    L.append(f"ref {r}: {len(C.games(ev, r))} games")
best = None
for name, ref in (("u30", "base"), ("u60", "base"), ("u30g", "gen"), ("u60g", "gen")):
    if not C.games(ev, name):
        L.append(f"{name}: no games (missing checkpoint or eval failed)")
        continue
    L.append(C.line(ev, ref, name))
    d = C.diff(ev, ref, name)
    if ref == "gen" and d[3] is not None and (best is None or d[3] > best[1]):
        best = (name, d[3], d[4])
if best:
    L.append(C.arch_table(ev, "gen", best[0]))
    L.append(f"VERDICT: best grafted checkpoint {best[0]} vs the untrained generalist {best[1]:+.2f} pp (95% CI lower {best[2]:+.2f}): "
             + ("specialist beats the generalist" if best[2] > 0 else "not shown to beat the generalist"))
else:
    L.append("VERDICT: no grafted checkpoint evaluated")
open(out, "w").write("\n".join(L) + "\n")
print("\n".join(L))
