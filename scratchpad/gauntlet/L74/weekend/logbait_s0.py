"""S8: search_s0 with the LEARNER's deck set to Log Bait (Evo Dart Goblin, Evo Skeleton Army, Valkyrie, Goblin Barrel, Princess, Cannon,
Wall Breakers, Ice Spirit).  Module-level patch of Runner.setup (spawned workers re-import this file first); E.ICEBOW_ENGINE_DECK is NOT touched
(selfplay_deck keys the icebow yaml deck on it).    python logbait_s0.py <search_s0 args>"""
import os, sys
sys.path.insert(0, os.getcwd())
from pipeline import e1_eval as E
from pipeline import search_s0 as S
LOGBAIT = ["BlowdartGoblin@evolution", "SkeletonArmy@evolution", "Valkyrie", "GoblinBarrel", "Princess", "Cannon", "Wallbreakers", "IceSpirits"]


def setup(self, opp_id, seed, opp_deck, tag=None):
    spec = {"tag": tag or f"s0:{opp_id}:{seed}", "opp": {"id": opp_id}, "learner_deck": list(LOGBAIT), "opp_deck": list(opp_deck),
            "learner_side": int(seed) % 2, "seed": int(seed)}
    opp, ocfg = self.opps[opp_id]
    return E.SelfPlayMatch(self.make_env(), spec, 0, {**self.lcfg, "entry_index": 0}, {**ocfg, "entry_index": 0}, self.learner, opp)


S.Runner.setup = setup
if __name__ == "__main__":
    sys.exit(S.main(sys.argv[1:]))
