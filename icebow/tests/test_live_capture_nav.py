"""L67q: the navigator's no-match ceiling and the student's freeze CaptureBudget (HANDOFF 5cs.99 V).

The owner's 8 h run lost 3 h 45 min to a Windows popup over the results screen (the navigator tapped a LOCATED Play
Again ~16,000 times), and the freeze capture spent its whole budget in match 1. These pin the replacements: recover
after 2 min, never press a key into a window that is not the game, give up once at 10 min; capture anti-stall moments
and late pinned waits, per match.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                                         # noqa: E402
from clashrl.nav import MenuNavigator                                     # noqa: E402
from clashrl.states import GameState                                      # noqa: E402
from clashrl.student_live import CaptureBudget                            # noqa: E402


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class _Controller:
    def __init__(self, focus_ok=True):
        self.taps, self.keys, self.focus_ok, self.focus_calls = [], [], focus_ok, 0

    def tap(self, x, y):
        self.taps.append((x, y))

    def force_focus(self):
        self.focus_calls += 1
        return self.focus_ok

    def press_key(self, key):
        self.keys.append(key)

    def _hwnd(self):
        return None


class _Vision:
    def locate(self, frame, tpl, thr):
        return None


def _nav(focus_ok=True):
    logs, alerts = [], []
    ctl = _Controller(focus_ok)
    nav = MenuNavigator(Config.load(), ctl, _Vision(), log=logs.append)
    clock = _Clock()
    nav._now, nav._sleep = clock, (lambda s: None)
    nav._screenshot = lambda tag: f"<{tag}>"
    nav._foreground = lambda: ("Windows popup", False)
    nav._alert = alerts.append
    nav.recover_after, nav.recover_every, nav.give_up_after = 120.0, 60.0, 600.0
    return nav, ctl, clock, logs, alerts


def _run(nav, clock, state, until_s, step=5.0):
    start = clock.t
    while clock.t - start <= until_s:
        nav.handle(None, state)
        clock.t += step


def _recover_lines(logs):
    return [l for l in logs if "-> recover #" in l]


class NoMatchCeiling(unittest.TestCase):
    def test_no_recovery_before_the_ceiling(self):
        nav, ctl, clock, logs, _ = _nav()
        _run(nav, clock, GameState.MATCH_END, 115)
        self.assertEqual(_recover_lines(logs), [])
        self.assertEqual(ctl.keys, [])
        self.assertFalse(nav.give_up)

    def test_recovery_fires_at_the_ceiling_and_repeats_no_faster_than_recover_every(self):
        nav, ctl, clock, logs, _ = _nav()
        _run(nav, clock, GameState.MATCH_END, 175)          # 0..175 s: one recovery at 120
        self.assertEqual(len(_recover_lines(logs)), 1)
        self.assertEqual(ctl.keys, ["esc"])
        _run(nav, clock, GameState.MATCH_END, 10)           # 180..190 s: the second one
        self.assertEqual(len(_recover_lines(logs)), 2)

    def test_escape_is_never_sent_when_the_game_is_not_in_front(self):
        nav, ctl, clock, logs, _ = _nav(focus_ok=False)
        _run(nav, clock, GameState.MATCH_END, 130)
        self.assertEqual(ctl.focus_calls, 1)
        self.assertEqual(ctl.keys, [])
        self.assertIn("force focus FAILED", _recover_lines(logs)[0])

    def test_escape_is_never_sent_on_home(self):
        nav, ctl, clock, logs, _ = _nav()
        _run(nav, clock, GameState.HOME, 130)
        self.assertEqual(len(_recover_lines(logs)), 1)
        self.assertEqual(ctl.keys, [])

    def test_give_up_sets_the_flag_and_alerts_exactly_once(self):
        nav, ctl, clock, logs, alerts = _nav()
        _run(nav, clock, GameState.UNKNOWN, 600)
        self.assertTrue(nav.give_up)
        self.assertEqual(len(alerts), 1)
        self.assertIn("Another window was in front", alerts[0])
        _run(nav, clock, GameState.UNKNOWN, 120)
        self.assertEqual(len(alerts), 1)

    def test_reaching_a_match_resets_the_timer(self):
        nav, ctl, clock, logs, _ = _nav()
        _run(nav, clock, GameState.MATCH_END, 100)
        nav.reset_state()                                   # play.py calls this every in-match iteration
        _run(nav, clock, GameState.MATCH_END, 100)
        self.assertEqual(_recover_lines(logs), [])

    def test_zero_disables_both(self):
        nav, ctl, clock, logs, alerts = _nav()
        nav.recover_after = nav.give_up_after = 0.0
        _run(nav, clock, GameState.MATCH_END, 900, step=30.0)
        self.assertEqual((_recover_lines(logs), alerts, nav.give_up), ([], [], False))


class FreezeCaptureBudget(unittest.TestCase):
    def test_opening_and_low_elixir_waits_are_not_captured(self):
        b = CaptureBudget()
        self.assertIsNone(b.choose(p_play=0.01, gate_tau=0.27, stalled=False, elixir=9, t_sec=10))
        self.assertIsNone(b.choose(p_play=0.01, gate_tau=0.27, stalled=False, elixir=5, t_sec=90))
        self.assertIsNone(b.choose(p_play=0.20, gate_tau=0.27, stalled=False, elixir=9, t_sec=90))

    def test_late_pinned_high_elixir_is_captured_spaced_and_capped_per_match(self):
        b = CaptureBudget(per_match_pinned=2)
        self.assertEqual(b.choose(p_play=0.01, gate_tau=0.27, stalled=False, elixir=9, t_sec=30), "pinned_hi")
        self.assertIsNone(b.choose(p_play=0.01, gate_tau=0.27, stalled=False, elixir=9, t_sec=32))   # < 5 s gap
        self.assertEqual(b.choose(p_play=0.01, gate_tau=0.27, stalled=False, elixir=9, t_sec=36), "pinned_hi")
        self.assertIsNone(b.choose(p_play=0.01, gate_tau=0.27, stalled=False, elixir=9, t_sec=60))   # match cap
        b.reset_match()
        self.assertEqual(b.choose(p_play=0.01, gate_tau=0.27, stalled=False, elixir=9, t_sec=30), "pinned_hi")

    def test_every_stall_is_captured_up_to_the_match_budget(self):
        b = CaptureBudget(per_match_stall=3)
        got = [b.choose(p_play=0.1, gate_tau=0.27, stalled=True, elixir=9, t_sec=t) for t in (15, 40, 70, 100)]
        self.assertEqual(got, ["stall", "stall", "stall", None])
        self.assertIsNone(b.choose(p_play=0.5, gate_tau=0.27, stalled=True, elixir=9, t_sec=120))    # not a stall

    def test_session_cap_bounds_a_runaway_run(self):
        b = CaptureBudget(per_match_stall=10, session_cap=4)
        n = 0
        for _ in range(3):
            n += sum(b.choose(p_play=0.1, gate_tau=0.27, stalled=True, elixir=9, t_sec=t) is not None
                     for t in (20, 40))
            b.reset_match()
        self.assertEqual(n, 4)


if __name__ == "__main__":
    unittest.main()
