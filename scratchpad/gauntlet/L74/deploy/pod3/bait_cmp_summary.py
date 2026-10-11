"""BAIT_CMP summary.  python bait_cmp_summary.py EVAL_DIR OUT.txt   (EVAL_DIR/{gen,spec}_{evo,lad}/matches.jsonl)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wk_compare as C
ev, out = sys.argv[1:3]
n = {k: len(C.games(ev, k)) for k in ("gen", "spec")}
L = ["BAIT_CMP: Log Bait specialist (wk_bait_u0060_g) vs the live generalist (rseries_r3c_u0030_barrel2k_cellref_towerref_w2), both playing the Log Bait BASE deck",
     "(Dart Goblin, Skeleton Army, Valkyrie, Goblin Barrel, Princess, Cannon, Wall Breakers, Ice Spirit).",
     "opponent: CAL set c yardstick (rdef_e4 graft, T 0.1, sample), census decks evo + ladder, seeds 0:240 each = 480 paired games; decode tau .35 + --own-effects, hero abilities v2 (no X-Bow / spell rules: the bait deck has none).",
     f"games played: gen {n['gen']}, spec {n['spec']}", C.line(ev, "gen", "spec"), C.arch_table(ev, "gen", "spec")]
d = C.diff(ev, "gen", "spec")
if d[3] is None or d[0] != 480:
    L.append(f"VERDICT: incomplete (paired games {d[0]} of 480)")
else:
    L.append("VERDICT: specialist " + ("beats the generalist" if d[4] > 0 else "is worse than the generalist" if d[5] < 0 else "is not distinguishable from the generalist")
             + f" ({d[3]:+.2f} pp, 95% CI [{d[4]:+.2f}, {d[5]:+.2f}]). Nothing deployed.")
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
