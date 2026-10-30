"""opp_learner_calib.yaml -> opp_learner_calib_live.yaml: the CLXIII partner plays gap.py D3's LIVE_OPTIONS stack
(league_frozen_opponent + league_opp_policy live + league_opp_live = live_subset.py KEEP + tau .35) instead of the pilot's
sampled T .5 decode (league_exploiters). Everything else byte-identical."""
import re, sys
src = r"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib.yaml"
dst = src.replace("opp_learner_calib.yaml", "opp_learner_calib_live.yaml")
t = open(src, encoding="utf-8").read()
t, n1 = re.subn(r"\nleague_opp_policy: sample\n", "\nleague_opp_policy: live\n", t)
t, n2 = re.subn(r"\nleague_exploiters:\n(- .*\n(   .*\n)*)", "\n", t)
assert n1 == 1 and n2 == 1, (n1, n2)
head = ("# PLATEAU.md next experiment (OPP-PLATEAU 10-30): = opp_learner_calib.yaml with the CLXIII partner on gap.py D3's\n"
        "# LIVE_OPTIONS decision stack (fast-loop-supported subset; own_effects / afford_ticks / follow_up_taps / G2 taps are\n"
        "# refused by producer.UNSUPPORTED_CFG and stay off) via league_frozen_opponent (100% CLXIII on icebow, = arm E's share)\n"
        "# + league_opp_policy live + league_opp_live. Why: D3 opp-win = 0.05 + 0.51 x training win vs the sampled T .5\n"
        "# partner (24 checkpoints, r .78): half of every training gain is lost against the stack D3 scores.\n")
tail = ("league_frozen_opponent: icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt\n"
        "league_opp_live: {barrel_lane: 'on', card_levels: [Rocket=16, Log=16], lethal_log: 'on', lethal_quiet: 1.0,\n"
        "  lethal_rocket: ot_behind, log_aim: log_barrel, log_air: block, rocket_dead_target: block, rocket_tornado: only,\n"
        "  rocket_tornado_lone: combo, rocket_tornado_order: either, rocket_tornado_window: measured, rocket_value: 9.0,\n"
        "  rocket_value_hitbox: edge, rocket_value_mode: damage, spell_aim: rocket_area, tau_phase: [0.35, 0.45, 0.55],\n"
        "  tau_threatened: 0.2, tornado_river: full, xbow_class: class_sample, xbow_class_floor: 0.3, xbow_dead_lane: block,\n"
        "  tau: 0.35}\n")
open(dst, "w", encoding="utf-8", newline="\n").write(head + t + tail)
import yaml
c = yaml.safe_load(open(dst, encoding="utf-8"))
o = yaml.safe_load(open(src, encoding="utf-8"))
print("changed keys:", sorted(k for k in set(c) | set(o) if c.get(k) != o.get(k)))
sys.path.insert(0, r"C:/Users/benpe/ClashBot")
from pipeline.decision_options import options_from_config
lv = dict(c["league_opp_live"]); lv.pop("tau")
options_from_config(lv); print("league_opp_live parses as DecisionOptions:", len(lv), "fields")
