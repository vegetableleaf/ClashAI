"""e1_eval's follow_ups on SelfPlaySide (the search_s0 benchmark path): the ghost Match's rules (test_e1_follow_up.py), event-driven by
SelfPlayMatch.due -- the same follow_up_verdict, the same landing rule, the opponent keeps deciding meanwhile.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_e1_follow_up_selfplay.py

Fake RoyaleSelfPlayEnv from test_league (every card costs 3; both sides' elixir = truth(side, tick)); scripted learner decisions.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                          # noqa: E402
from pipeline.tests import test_league as TL                               # noqa: E402

D, CELL = 26, 36 * 40 + 5


def spec(slot=1, after=4, **kw):
    return E.follow_up_spec(slot, CELL + 3, after, **kw)


def drive(script, env=None, cfg_over=None):
    """script = {learner decision index: (slot, follow_ups or None)}; every other decision waits; the opponent always waits.
    -> (match, learner decision ticks, opponent decision ticks)."""
    learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
    env = env or TL._SPEnv()
    cfg = TL._cfg("live", record=False, **{"action_delay_ticks": D, **(cfg_over or {})})
    m = E.SelfPlayMatch(env, TL._spec(0, "snapA", 0), 0, cfg, TL._cfg("live", record=False, action_delay_ticks=D), learner, opp)
    lt, ot, i = [], [], 0
    while True:
        due = m.due()
        if not due:
            break
        for s in due:
            s.prepare()
            if s is m.learner:
                lt.append(s._cur[0])
                slot, fus = script.get(i, (None, None))
                i += 1
                dec = {"play": slot is not None, "slot": -1 if slot is None else slot, "cell": CELL if slot is not None else -1,
                       "why": "gate" if slot is not None else "wait"}
                if fus:
                    dec["follow_ups"] = fus
                s.apply(0.9, dec)
            else:
                ot.append(s._cur[0])
                s.apply(0.9, {"play": False, "slot": -1, "cell": -1, "why": "wait"})
    return m, lt, ot


def acts(m):
    return [(t, sd) for t, sd, *_ in m.env.log if sd == 0]


class TestSelfPlayFollowUps(unittest.TestCase):
    def test_second_play_lands_at_its_tick_and_no_decision_until_resolved(self):
        m, lt, ot = drive({0: (0, [spec(after=4)])})
        # first at 90 + 26; asked 4 ticks later it lands 4 - 2 (the first tap's arrival) after it; next decision = first grid tick after
        self.assertEqual(acts(m), [(116, 0), (118, 0)])
        self.assertEqual(lt[:2], [90, 120])
        self.assertEqual(m.learner.follow_n, {"fired": 1})
        self.assertEqual(m.learner.n_att, 2)
        self.assertEqual([p["why"] for p in m.learner.plays], ["gate", "follow_up"])
        self.assertTrue(set(ot[:6]) >= {100, 110, 120}, ot[:6])      # the opponent kept deciding through the window

    def test_unaffordable_follow_up_is_cancelled_after_its_window(self):
        m, lt, _ = drive({0: (0, [spec(after=0, within_ticks=12)])}, env=TL._SPEnv(truth=lambda s, t: 5.0))   # 5 + regen < 3 + 3
        self.assertEqual(acts(m), [(116, 0)])
        self.assertEqual(m.learner.follow_n, {"cancelled_unaffordable": 1})
        self.assertEqual(lt[:2], [90, 120])

    def test_it_waits_on_the_frame_grid_until_it_can_be_paid(self):
        truth = lambda s, t: 5.0 + max(0, t - 90) * 0.05 if s == 0 else 7.0         # noqa: E731  payable from 90 + 18
        m, lt, _ = drive({0: (0, [spec(after=4, within_ticks=20)])}, env=TL._SPEnv(truth=truth))
        self.assertEqual(acts(m), [(116, 0), (116 + 16, 0)])                            # fires at 108: lands 116 + (18 - 2)
        self.assertEqual(m.learner.follow_n, {"fired": 1})

    def test_first_play_refused_before_it_is_decided_cancels_it(self):
        m, _, _ = drive({0: (0, [spec(after=40, within_ticks=4)])}, env=TL._SPEnv(refuse=[(0, 116)]))
        self.assertEqual(acts(m), [(116, 0)])
        self.assertEqual(m.learner.follow_n, {"cancelled_first_unconfirmed": 1})
        m, _, _ = drive({0: (0, [spec(after=40, within_ticks=4, require_first=False)])}, env=TL._SPEnv(refuse=[(0, 116)]))
        self.assertEqual(len(acts(m)), 2)

    def test_an_orphan_follow_up_already_decided_still_lands_when_the_first_is_refused(self):
        m, _, _ = drive({0: (0, [spec(after=4)])}, env=TL._SPEnv(refuse=[(0, 116)]))
        self.assertEqual(acts(m), [(116, 0), (118, 0)])
        self.assertEqual((m.learner.n_att, m.learner.n_acc), (2, 1))

    def test_at_most_two_outstanding_a_third_waits_for_a_landing(self):
        three = lambda within: [spec(slot=1, after=2), spec(slot=2, after=4, within_ticks=within)]        # noqa: E731
        m, _, _ = drive({0: (0, three(10))})
        self.assertEqual(len(acts(m)), 2)
        self.assertEqual(m.learner.follow_n, {"fired": 1, "cancelled_outstanding": 1})
        m, _, _ = drive({0: (0, three(30))})
        self.assertEqual(acts(m), [(116, 0), (116, 0), (116 + 24, 0)])
        self.assertEqual(m.learner.follow_n, {"fired": 2})

    def test_the_first_plays_own_slot_is_busy(self):
        m, _, _ = drive({0: (0, [spec(slot=0, after=2)])})
        self.assertEqual(acts(m), [(116, 0)])
        self.assertEqual(m.learner.follow_n, {"cancelled_slot_busy": 1})

    def test_every_follow_up_reaches_the_engine_at_its_own_landing_tick_while_a_later_one_waits(self):
        truth = lambda s, t: (6.2 if t < 116 else (3.0 if t < 130 else 9.0)) if s == 0 else 7.0   # noqa: E731
        m, _, _ = drive({0: (0, [spec(slot=1, after=2), spec(slot=2, after=4, within_ticks=40)])}, env=TL._SPEnv(truth=truth))
        self.assertEqual(acts(m)[:2], [(116, 0), (116, 0)])               # first play + follow-up 1, not delayed by follow-up 2's wait
        self.assertGreaterEqual(acts(m)[2][0], 130)
        self.assertEqual(m.learner.follow_n, {"fired": 2})

    def test_matches_the_ghost_match_on_the_same_scenarios(self):
        from pipeline.tests import test_e1_action_delay as AD
        from pipeline.tests.test_e1_follow_up import _Env
        for after in (0, 3, 4, 7):
            ghost, env, _ = AD._scripted([dict(AD.PLAY, follow_ups=[E.follow_up_spec(5, AD.CELL, after)])], D, env=_Env(lambda t: 9.0))
            m, _, _ = drive({0: (0, [spec(after=after)])})
            g_off = [c[0] - AD.T for c in env.eng.calls]                   # ghost: engine ticks relative to its decision tick
            s_off = [t - 90 for t, _ in acts(m)]
            self.assertEqual(g_off, s_off, after)
            self.assertEqual(ghost.result()["follow_ups"], m.learner.follow_n and dict(m.learner.follow_n), after)

    def test_flag_absent_is_unchanged_and_the_two_mechanisms_exclude_each_other(self):
        m, lt, _ = drive({0: (0, None), 1: (1, None)})
        self.assertEqual(lt[:3], [90, 120, 150])                            # the old single-play lock
        self.assertEqual(acts(m), [(116, 0), (146, 0)])
        self.assertFalse(getattr(m.learner, "follow_n", None))
        with self.assertRaises(ValueError):
            drive({0: (0, [spec()])}, cfg_over=dict(pipeline_decisions=True))
        with self.assertRaises(ValueError):
            drive({0: (0, [spec()])}, cfg_over=dict(action_delay_ticks=0))


if __name__ == "__main__":
    unittest.main()
