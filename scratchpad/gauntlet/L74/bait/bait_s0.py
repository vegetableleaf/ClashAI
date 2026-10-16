"""Bait (owner's friend, 2026-10-16) eval: search_s0 with the LEARNER deck fixed to the friend's Log Bait deck in its decked
forms (Hero Valkyrie, Evo Skeleton Army, Evo Goblin Barrel, Princess, Dart Goblin, Wall Breakers, Ice Spirit, Cannon).
Same patch as L74/weekend/logbait_s0.py (module level, so spawned workers re-import it); E.ICEBOW_ENGINE_DECK untouched.
    python bait_s0.py <search_s0 args>             plain search_s0
    python bait_s0.py --worker <livecal args>      livecal.worker (no anti-stall) -- what bait_eval.py runs per chunk"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'scratchpad/gauntlet/L74/livecal')]
from pipeline import e1_eval as E  # noqa: E402
from pipeline import search_s0 as S  # noqa: E402

DECK = ["Valkyrie@hero", "SkeletonArmy@evolution", "GoblinBarrel@evolution", "Princess", "BlowdartGoblin", "Wallbreakers",
        "IceSpirits", "Cannon"]


def setup(self, opp_id, seed, opp_deck, tag=None):
    spec = {"tag": tag or f"s0:{opp_id}:{seed}", "opp": {"id": opp_id}, "learner_deck": list(DECK), "opp_deck": list(opp_deck),
            "learner_side": int(seed) % 2, "seed": int(seed)}
    opp, ocfg = self.opps[opp_id]
    return E.SelfPlayMatch(self.make_env(), spec, 0, {**self.lcfg, "entry_index": 0}, {**ocfg, "entry_index": 0}, self.learner, opp)


S.Runner.setup = setup
if __name__ == "__main__":
    os.chdir(ROOT)
    if sys.argv[1:2] == ["--worker"]:
        import livecal
        sys.exit(livecal.worker())
    sys.exit(S.main(sys.argv[1:]))
