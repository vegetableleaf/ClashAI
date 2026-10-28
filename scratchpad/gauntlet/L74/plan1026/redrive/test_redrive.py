"""python -I test_redrive.py -- timed_deal / base checks (no engine needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from redrive import base, timed_deal  # noqa: E402

S = list("abcdefgh")
# e given 10 ticks after a: a is still pending, so e must already be in hand (untimed first fit puts e at the queue front)
o = timed_deal(S, [(0, "a"), (10, "e")])
assert o is not None and {"a", "e"} <= {S[i] for i in o[:4]}, o
# 30 ticks later a has run, so the queue front may be the next card
o = timed_deal(S, [(0, "a"), (30, "e")])
assert o[:4] == [0, 1, 2, 3] and S[o[4]] == "e", o
# a card cannot come back before 4 other plays
assert timed_deal(S, [(0, "a"), (40, "a")]) is None
assert timed_deal(S, [(0, "a"), (30, "b"), (60, "c"), (90, "d"), (120, "a")]) is None
assert timed_deal(S, [(0, "a"), (30, "b"), (60, "c"), (90, "d"), (120, "e"), (150, "a")]) is not None
assert base("battle-ram-ev1") == "battle-ram" and base("wizard-hero") == "wizard" and base("x-bow") == "x-bow"
print("ok")
