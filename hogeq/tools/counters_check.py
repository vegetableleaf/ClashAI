"""Regression guard for `card_threat.counters()` -- the role table the referee grades defence with.

Every case here was a real bug once, and each is recorded in that function's own comments. The table
is widened and narrowed often enough (five times in this project's history) that the strict cases
need something that fails loudly rather than a careful reading of the diff.

    python tools/counters_check.py          # exits non-zero on any regression

The last widening is the reason this exists. `counters()` returned False for a threat matching no
role class, and `_threat_response` fined the defence -1.0 as a misread -- measured, **74 of 154
non-spell cards** were in that hole, including mini_pekka, sparky, prince, musketeer, wizard and
archer_queen. The fix drops the `win_condition` requirement from the body-answers-a-ground-threat
branch, and the cases below are what must NOT come along with it: tanks still need real DPS, a
building or a melee swarm; air still needs air defence; our own siege still cannot defend.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import numpy as np                                      # noqa: E402
from clashrl.config import Config                       # noqa: E402
from clashrl.cards import CardDB                        # noqa: E402
from clashrl import card_threat as ct                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
cfg = Config.load(os.path.join(HERE, "..", "config", "config.yaml"))
db = CardDB(cfg)


def tid(**bits):
    """An identity block with the named class bits set -- the same layout identity_threat_vector
    builds (see IDENTITY_DIM)."""
    v = np.zeros(ct.IDENTITY_DIM, dtype=np.float32)
    v[0] = 1.0
    for k, i in (("tank", 1), ("swarm", 2), ("flying", 3), ("siege", 4),
                 ("wincon", 5), ("bldg", 6)):
        if bits.get(k):
            v[i] = 1.0
    v[7] = 0.5
    return v


CASES = [
    ("the_log",    dict(swarm=True, flying=True),  False, "log cannot hit a flying swarm"),
    ("knight",     dict(flying=True, wincon=True), False, "ground body cannot block a Balloon"),
    ("skeletons",  dict(flying=True),              False, "ground swarm vs air"),
    ("hog_rider",  dict(tank=True),                False, "a building-targeter is not a tank answer"),
    ("skeletons",  dict(tank=True),                True,  "a melee swarm surrounds a tank"),
    ("ice_wizard", dict(tank=True),                False, "52 dps is not a tank answer"),
    ("tesla",      dict(tank=True),                True,  "a building answers a tank"),
    ("tesla",      dict(bldg=True),                True,  "a building pulls a building-targeter"),
    ("knight",     dict(),                         True,  "a body answers a plain ground threat"),
    ("knight",     dict(wincon=True),              True,  "a body answers a bare win condition"),
    ("x_bow",      dict(),                         False, "our own siege cannot defend"),
    ("tornado",    dict(),                         False, "a spell is not a body"),
]


def main() -> int:
    bad = 0
    for card, bits, want, why in CASES:
        try:
            got = ct.counters(ct.profile(db, card), tid(**bits))
        except Exception as e:                           # noqa: BLE001
            print("!! %-11s raised %s" % (card, e))
            bad += 1
            continue
        ok = (got == want)
        bad += 0 if ok else 1
        print("%s %-11s vs %-30s = %-5s (want %-5s)  %s"
              % ("  " if ok else "!!", card,
                 str(sorted(k for k in bits)) or "[plain ground]", got, want, why))
    print("")
    print("%d regression(s)" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
