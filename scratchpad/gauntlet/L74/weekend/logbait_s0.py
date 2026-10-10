"""S8: search_s0 with the LEARNER's deck set to Log Bait (Evo Dart Goblin, Evo Skeleton Army, Valkyrie, Goblin Barrel, Princess, Cannon,
Wall Breakers, Ice Spirit).  Module-level patch (spawned workers re-import this file first); search_s0 reads E.ICEBOW_ENGINE_DECK per match.
    python logbait_s0.py <search_s0 args>"""
import os, sys
sys.path.insert(0, os.getcwd())
from pipeline import e1_eval as E
from pipeline import search_s0 as S
E.ICEBOW_ENGINE_DECK = ("BlowdartGoblin@evolution", "SkeletonArmy@evolution", "Valkyrie", "GoblinBarrel", "Princess", "Cannon",
                        "Wallbreakers", "IceSpirits")
if __name__ == "__main__":
    sys.exit(S.main(sys.argv[1:]))
