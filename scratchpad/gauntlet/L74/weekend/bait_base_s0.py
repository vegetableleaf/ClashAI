"""S11 eval: search_s0 with the LEARNER deck = Log Bait in BASE forms (owner 2026-10-10: Dart Goblin, Skeleton Army, Valkyrie, Goblin Barrel,
Princess, Cannon, Wall Breakers, Ice Spirit; no evo, no hero).  Same patch as logbait_s0.py (S8, which used the evo forms); only the deck differs.
    python bait_base_s0.py <search_s0 args>"""
import os, sys
sys.path.insert(0, os.getcwd())
from pipeline import e1_eval as E
from pipeline import search_s0 as S
LOGBAIT_BASE = ["BlowdartGoblin", "SkeletonArmy", "Valkyrie", "GoblinBarrel", "Princess", "Cannon", "Wallbreakers", "IceSpirits"]


def setup(self, opp_id, seed, opp_deck, tag=None):
    spec = {"tag": tag or f"s0:{opp_id}:{seed}", "opp": {"id": opp_id}, "learner_deck": list(LOGBAIT_BASE), "opp_deck": list(opp_deck),
            "learner_side": int(seed) % 2, "seed": int(seed)}
    opp, ocfg = self.opps[opp_id]
    return E.SelfPlayMatch(self.make_env(), spec, 0, {**self.lcfg, "entry_index": 0}, {**ocfg, "entry_index": 0}, self.learner, opp)


S.Runner.setup = setup
if __name__ == "__main__":
    sys.exit(S.main(sys.argv[1:]))
