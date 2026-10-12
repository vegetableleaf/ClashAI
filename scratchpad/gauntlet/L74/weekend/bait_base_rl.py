"""S11 training: pipeline.rl_royale with the LEARNER deck FIXED to Log Bait in base forms (see bait_base_s0.py).  Opponents, opponent decks,
sides and seeds are drawn exactly as before (the original sample_matchups runs, then only the learner deck fields are overwritten), so the
league, the census weighting and the rng stream are unchanged.  Run from the repo root:  python bait_base_rl.py <rl_royale args>
The "icebow" learner-deck bucket label is kept: it is the monitors' name for the fixed learner deck."""
import os, sys
sys.path.insert(0, os.getcwd())
from pipeline import rl_royale as R
LOGBAIT_BASE = ["BlowdartGoblin", "SkeletonArmy", "Valkyrie", "GoblinBarrel", "Princess", "Cannon", "Wallbreakers", "IceSpirits"]
_orig = R.sample_matchups


def sample_matchups(*a, **k):
    out = _orig(*a, **k)
    for m in out:
        m["learner_deck"], m["learner_deck_name"], m["learner_bucket"] = list(LOGBAIT_BASE), "logbait_base", "icebow"
    return out


R.sample_matchups = sample_matchups
if __name__ == "__main__":
    sys.exit(R.main())
