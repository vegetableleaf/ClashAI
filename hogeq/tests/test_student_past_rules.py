"""L67r F1 / F2 (HANDOFF 5cs.99 X): the card-cycle rule on the student's play history, and the anti-stall idle clock.

F1: the live `past` channel recorded the same card twice inside 3 plays (11% of live plays), a history the pro
training rows never contain, and the gate collapsed on it. F2: the anti-stall clock counted from 0.0 before a match's
first play, forcing a play the first time elixir read 9.
"""
from __future__ import annotations

import os
import random
import sys
import time
import unittest
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.student_live import (PAST_HISTORY, PAST_K, CaptureBudget, HandMemory, StudentPolicy,  # noqa: E402
                                  drop_cycle_repeats)
from pipeline.obs_contract import load_deck                                                         # noqa: E402

# live-style deck keys: indices are tray ids; "knight" is the base of the deck's knight_evo slot
KEYS = ["tornado", "tesla_evo", "ice_wizard", "x_bow", "rocket", "knight_evo", "the_log", "skeletons", "knight"]


def _bare(stall_elixir=9.0, stall_seconds=12.0):
    """A StudentPolicy without a checkpoint: only the state the history and stall rules touch."""
    sp = object.__new__(StudentPolicy)
    sp.deck = load_deck("icebow")
    sp._past = deque(maxlen=PAST_HISTORY)
    sp._last_play_t = None
    sp._plays_match = 0
    sp._match_idx = 0
    sp.stats = {}
    sp.stall_elixir, sp.stall_seconds = stall_elixir, stall_seconds
    sp.hand_memory = HandMemory()
    sp.capture = CaptureBudget()
    return sp


def _play(sp, *names):
    for n in names:
        sp.record_play(KEYS.index(n), (0.5, 0.7), KEYS)


def _slots(sp):
    """Deck slots the MODEL sees, newest first."""
    return [int(s) for s in sp._past_array(time.time())[:, 0] if s >= 0]


S = {n: i for i, n in enumerate(load_deck("icebow").cards)}


class CycleRule(unittest.TestCase):
    def test_a_repeat_inside_three_plays_drops_the_older_phantom(self):
        sp = _bare()
        _play(sp, "ice_wizard", "skeletons", "ice_wizard")
        self.assertEqual(_slots(sp), [S["ice_wizard"], S["skeletons"]])
        self.assertEqual(sp.stats["past_repeat_dropped"], 1)

    def test_an_immediate_repeat(self):
        sp = _bare()
        _play(sp, "tornado", "the_log", "the_log")
        self.assertEqual(_slots(sp), [S["the_log"], S["tornado"]])

    def test_a_legal_return_after_three_other_plays_is_kept(self):
        sp = _bare()
        _play(sp, "tornado", "the_log", "skeletons", "ice_wizard", "tornado")
        self.assertEqual(_slots(sp), [S["tornado"], S["ice_wizard"], S["skeletons"]])
        self.assertNotIn("past_repeat_dropped", sp.stats)

    def test_dropping_a_phantom_lets_the_real_older_play_back_into_view(self):
        sp = _bare()
        _play(sp, "rocket", "tornado", "the_log", "ice_wizard", "the_log")
        self.assertEqual(_slots(sp), [S["the_log"], S["ice_wizard"], S["tornado"]])

    def test_evo_and_base_are_the_same_card(self):
        sp = _bare()
        _play(sp, "knight_evo", "the_log", "knight")
        self.assertEqual(_slots(sp), [S["knight_evo"], S["the_log"]])

    def test_the_model_never_sees_a_repeated_card_whatever_the_bot_records(self):
        rng = random.Random(7)
        sp = _bare()
        for _ in range(2000):
            _play(sp, rng.choice(KEYS))
            got = _slots(sp)
            self.assertEqual(len(got), len(set(got)))
            self.assertLessEqual(len(got), PAST_K)

    def test_drop_helper_only_looks_at_the_newest_window(self):
        d = deque([(1, 0, 0, 0), (2, 0, 0, 0), (3, 0, 0, 0), (1, 0, 0, 0)], maxlen=8)
        self.assertEqual(drop_cycle_repeats(d, 2), 1)          # 2 is inside the newest 3
        self.assertEqual([e[0] for e in d], [1, 3, 1])
        d = deque([(5, 0, 0, 0), (1, 0, 0, 0), (2, 0, 0, 0), (3, 0, 0, 0)], maxlen=8)
        self.assertEqual(drop_cycle_repeats(d, 5), 0)          # 5 is 4 plays back: a legal return


class IdleClock(unittest.TestCase):
    def test_match_start_starts_the_clock(self):
        sp = _bare()
        sp.reset_match()
        t0 = sp._last_play_t
        self.assertIsNotNone(t0)
        self.assertFalse(sp._stalled(9.0, t0 + 4.0))           # the old rule fired here, at t ~4 s
        self.assertTrue(sp._stalled(9.0, t0 + 12.5))

    def test_below_stall_elixir_never_stalls(self):
        sp = _bare()
        sp.reset_match()
        self.assertFalse(sp._stalled(8.0, sp._last_play_t + 60))

    def test_a_play_restarts_the_clock(self):
        sp = _bare()
        sp.reset_match()
        _play(sp, "the_log")
        self.assertFalse(sp._stalled(9.0, sp._last_play_t + 5.0))
        self.assertTrue(sp._stalled(9.0, sp._last_play_t + 12.0))

    def test_without_a_match_start_the_first_high_elixir_decision_starts_the_clock(self):
        sp = _bare()
        self.assertFalse(sp._stalled(9.0, 1000.0))
        self.assertFalse(sp._stalled(9.0, 1011.0))
        self.assertTrue(sp._stalled(9.0, 1012.0))

    def test_disabled(self):
        sp = _bare(stall_elixir=None)
        self.assertFalse(sp._stalled(10.0, 1e9))

    def test_reset_match_clears_the_history_and_play_count(self):
        sp = _bare()
        _play(sp, "the_log", "tornado")
        sp.reset_match()
        self.assertEqual((_slots(sp), sp._plays_match), ([], 0))


if __name__ == "__main__":
    unittest.main()
