"""Bait training: pipeline.rl_royale with the LEARNER deck fixed to bait_s0.DECK (the friend's deck, decked forms).
Opponents, opponent decks, sides and seeds are drawn exactly as the config draws them (the original sample_matchups runs,
then only the learner deck fields are overwritten), so league, census weighting and rng stream are unchanged -- the
L74/weekend/bait_base_rl.py approach. The "icebow" learner bucket label is kept: the monitors' name for the fixed deck.
    python scratchpad/gauntlet/L74/bait/bait_rl.py <rl_royale args>     (from the repo root)"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[3]), str(HERE)]
from pipeline import rl_royale as R  # noqa: E402
from bait_s0 import DECK  # noqa: E402

_orig = R.sample_matchups


def sample_matchups(*a, **k):
    out = _orig(*a, **k)
    for m in out:
        m["learner_deck"], m["learner_deck_name"], m["learner_bucket"] = list(DECK), "bait_friend", "icebow"
    return out


R.sample_matchups = sample_matchups
if __name__ == "__main__":
    sys.exit(R.main())
