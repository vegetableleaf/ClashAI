"""I9 -- the `with_base` contract, and why a swallowed exception must not read as working.

BYTE-IDENTICAL in icebow and hogeq.

THE HISTORY. `TeamTracker.enemy_tracks` grew a `with_base` argument so the threat gate could
triage its REMEMBERED enemies by card name. `PerceptionLoop.enemy_tracks` is a lock-guarded
passthrough to it, and hogeq's copy carried a comment saying the parameter had never been ported
there -- so `enemy_tracks(..., with_base=True)` raised TypeError, `train_rl`'s gate caught it with
a bare `pass`, and the memory half of the gate was inert for the whole time the perception loop
was running. `tools/parity_check.py` carried it on the DRIFT list.

MEASURED 2026-08-27, in BOTH decks: the TypeError does NOT fire. Both signatures are
`(self, now, with_base=False, max_age=None)` and both return the base. The code had been fixed and
the comment and the DRIFT entry were stale -- which is its own kind of bug, because the DRIFT list
is what the project uses to decide what still needs fixing.

Nothing pinned it, though, and the swallow that hid it is still there and still has to be (a
perception hiccup must never break training). So: this file pins the contract, and the gate's
`except TypeError` now calls `_memory_gate_inert`, which says so once and counts.
"""
from __future__ import annotations

import inspect
import io
import sys
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl import train_rl                                    # noqa: E402
from clashrl.perception import PerceptionLoop                   # noqa: E402
from clashrl.replay_mine import TeamTracker                     # noqa: E402


class _Cfg:
    def get(self, *a, **k):
        return k.get("default")


def _loop_with_one_remembered_enemy():
    """A PerceptionLoop over a real TeamTracker holding one REMEMBERED enemy track -- the exact
    object the threat gate reads when the detector blinks."""
    tk = TeamTracker()
    now = time.time()
    tk._tracks = [{"team": "enemy", "t": now, "t0": now - 2.0, "x": 0.5, "y": 0.6,
                   "x0": 0.5, "y0": 0.3, "hits": 9, "base": "hog_rider",
                   "bm": 0, "be": 0, "rank": 0}]
    return PerceptionLoop(_Cfg(), None, tk, conf=0.5), tk, now


class WithBaseContractTests(unittest.TestCase):
    def test_the_passthrough_and_the_tracker_have_the_same_signature(self):
        a = inspect.signature(PerceptionLoop.enemy_tracks)
        b = inspect.signature(TeamTracker.enemy_tracks)
        self.assertEqual(list(a.parameters), list(b.parameters),
                         "the passthrough must forward exactly what the tracker accepts")
        self.assertIn("with_base", a.parameters)
        self.assertIn("max_age", a.parameters)

    def test_the_passthrough_returns_the_base_as_a_keyword_argument(self):
        """This is the assertion that goes red if the parameter is ever dropped again. The gate
        calls it BY KEYWORD, so a positional-only reordering has to fail here too."""
        loop, _tk, now = _loop_with_one_remembered_enemy()
        got = loop.enemy_tracks(now, with_base=True)
        self.assertEqual(len(got), 1)
        self.assertEqual(len(got[0]), 5, "with_base appends the card name")
        self.assertEqual(got[0][4], "hog_rider")

    def test_the_passthrough_returns_the_base_positionally_too(self):
        loop, _tk, now = _loop_with_one_remembered_enemy()
        self.assertEqual(loop.enemy_tracks(now, True)[0][4], "hog_rider")

    def test_without_it_the_tracks_are_positions_only(self):
        loop, _tk, now = _loop_with_one_remembered_enemy()
        got = loop.enemy_tracks(now)
        self.assertEqual(len(got[0]), 4, "the default is unchanged for position-only callers")

    def test_the_tracker_itself_agrees_with_its_passthrough(self):
        loop, tk, now = _loop_with_one_remembered_enemy()
        self.assertEqual(loop.enemy_tracks(now, with_base=True),
                         tk.enemy_tracks(now, with_base=True))

    def test_max_age_is_forwarded_and_not_dropped(self):
        """The other parameter this passthrough has to carry: a spell-impact verdict must not run
        on 4.5 s-old memory, and it asks for freshness through here."""
        loop, _tk, now = _loop_with_one_remembered_enemy()
        self.assertEqual(loop.enemy_tracks(now, True, 10.0)[0][4], "hog_rider")
        self.assertEqual(loop.enemy_tracks(now + 5.0, True, 1.0), [],
                         "a stale track must be filtered by max_age")


class SwallowedExceptionTests(unittest.TestCase):
    """The gate catches TypeError so a perception hiccup cannot break training. It must not be
    possible for that catch to be QUIET, because quiet is how the original bug survived."""

    def test_a_tracker_without_with_base_really_does_raise(self):
        """The failure mode is real, not hypothetical -- which is why the catch exists at all."""
        class _Old:
            def enemy_tracks(self, now):
                return []
        with self.assertRaises(TypeError):
            _Old().enemy_tracks(time.time(), with_base=True)

    def test_the_gate_reports_the_first_time_its_memory_half_goes_dark(self):
        class _Old:
            pass
        before = train_rl._MEMORY_GATE_INERT
        train_rl._MEMORY_GATE_INERT = 0
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                train_rl._memory_gate_inert(_Old())
                train_rl._memory_gate_inert(_Old())
            out = buf.getvalue()
            self.assertIn("WARNING", out)
            self.assertIn("with_base", out)
            self.assertEqual(out.count("WARNING"), 1, "loud once, then counted")
            self.assertEqual(train_rl._MEMORY_GATE_INERT, 2)
        finally:
            train_rl._MEMORY_GATE_INERT = before

    def test_the_real_objects_never_take_that_path(self):
        """The counter is the proof: exercising the gate's own call against the real
        PerceptionLoop must not trip it."""
        before = train_rl._MEMORY_GATE_INERT
        loop, _tk, now = _loop_with_one_remembered_enemy()
        try:
            loop.enemy_tracks(now, with_base=True)
        except TypeError:                                    # pragma: no cover -- the regression
            train_rl._memory_gate_inert(loop)
        self.assertEqual(train_rl._MEMORY_GATE_INERT, before,
                         "the threat gate's memory half is live in this deck")


if __name__ == "__main__":
    unittest.main()
