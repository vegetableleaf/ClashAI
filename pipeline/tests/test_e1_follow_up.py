"""e1_eval's follow-up plays (L74 latency2): a decision with ``follow_ups`` plays second cards decided ``after_ticks`` later
without waiting for the first to land, as live_play --follow-up-taps does. Same fake-engine harness as test_e1_action_delay.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_e1_follow_up.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                          # noqa: E402
from pipeline.tests import test_e1_action_delay as AD                     # noqa: E402
from pipeline.tests.test_e1_opp_counter import T                          # noqa: E402

D = 26
# icebow deck slot costs (the fake engine's): slot 2 = 3, slot 5 = 3, slot 1 = 4, slot 3 = 6; in hand: slots 2, 5, 3, 1
PLAY = AD.PLAY                                                              # slot 2 (3 elixir), cell CELL
CELL = AD.CELL


class _Env(AD._Env):
    """Elixir of side 0 follows ``el(tick)`` (the fake state's is a constant)."""

    def __init__(self, el=lambda t: 9.0, **kw):
        super().__init__(**kw)
        self.el = el

    def _state(self):
        st = super()._state()
        st["players"][0] = dict(st["players"][0], elixir_exact=float(self.el(self.tick)))
        return st


def run(follow_ups, env=None, delay=D, script=None, **cfg):
    env = env or _Env()
    play = dict(PLAY, follow_ups=follow_ups) if follow_ups is not None else PLAY
    return AD._scripted(script or [play], delay, env=env, **cfg)


def spec(slot=5, after=4, **kw):          # slot 5 = 3 elixir, in the fake hand (slots 2, 5, 3, 1 are)
    return E.follow_up_spec(slot, CELL + 3, after, **kw)


def acts(env):
    return [c[0] for c in env.eng.calls]


class TestFollowUps(unittest.TestCase):
    def test_second_play_lands_right_after_the_first_and_no_decision_in_between(self):
        m, env, ticks = run([spec(after=4)])
        # first at T + 26; the follow-up asked 4 ticks later lands 4 - 2 (the first tap's arrival) = 2 ticks after it
        self.assertEqual(acts(env), [T + D, T + D + 2])
        self.assertEqual(ticks[:2], [T, T + 30])                          # next decision = first grid tick after the last landing
        r = m.result()
        self.assertEqual((r["plays_attempted"], r["plays_accepted"]), (2, 2))
        self.assertEqual(r["follow_ups"], {"fired": 1})
        self.assertEqual([p["why"] for p in r["plays"]], ["gate", "follow_up"])
        self.assertEqual([p["land_tick"] for p in r["plays"]], [T + D, T + D + 2])
        self.assertEqual([p[0] for p in m.done_plays], [T + D, T + D + 2])   # past plays carry the landing ticks

    def test_arrival_config_shifts_the_landing_and_never_before_the_first(self):
        _, env, _ = run([spec(after=4)], follow_arrival_ticks=4)
        self.assertEqual(acts(env), [T + D, T + D])                       # asked 4 apart, the first tap took 4: together
        _, env, _ = run([spec(after=0)], follow_arrival_ticks=2)
        self.assertEqual(acts(env), [T + D, T + D])

    def test_it_is_charged_against_the_elixir_the_first_play_has_not_spent_yet(self):
        m, env, _ = run([spec(after=0, within_ticks=20)], env=_Env(lambda t: 5.0))     # 5 + 6-tick regen < 3 + 3
        self.assertEqual(acts(env), [T + D])
        self.assertEqual(m.result()["follow_ups"], {"cancelled_unaffordable": 1})
        # exactly covered with the regeneration of the horizon: 5.9 + 6/56 = 6.007 >= 6
        _, env, _ = run([spec(after=0)], env=_Env(lambda t: 5.9))
        self.assertEqual(len(acts(env)), 2)

    def test_it_waits_on_the_frame_grid_until_it_can_be_paid_and_never_fires_late(self):
        rising = _Env(lambda t: 5.0 + max(0, t - T) * 0.05)               # enough from T + 18
        m, env, _ = run([spec(after=4, within_ticks=20)], env=rising)
        self.assertEqual(acts(env), [T + D, T + D + (18 - 2)])
        self.assertEqual(m.result()["follow_ups"], {"fired": 1})
        slow = _Env(lambda t: 5.0 + max(0, t - T) * 0.05)
        m, env, _ = run([spec(after=4, within_ticks=8)], env=slow)              # window ends at T + 12: dropped
        self.assertEqual(acts(env), [T + D])
        self.assertEqual(m.result()["follow_ups"], {"cancelled_unaffordable": 1})

    def test_first_play_refused_before_the_follow_up_is_decided_cancels_it(self):
        m, env, _ = run([spec(after=40, within_ticks=4)], env=_Env(refuse_at=[T + D]))
        self.assertEqual(acts(env), [T + D])                              # only the (refused) first
        self.assertEqual(m.result()["follow_ups"], {"cancelled_first_unconfirmed": 1})
        m, env, _ = run([spec(after=40, within_ticks=4, require_first=False)], env=_Env(refuse_at=[T + D]))
        self.assertEqual(len(acts(env)), 2)

    def test_an_orphan_follow_up_already_decided_still_lands_when_the_first_is_refused(self):
        m, env, _ = run([spec(after=4)], env=_Env(refuse_at=[T + D]))     # live: the second tap is already out
        self.assertEqual(acts(env), [T + D, T + D + 2])
        self.assertEqual(m.result()["plays_accepted"], 1)

    def test_at_most_two_plays_outstanding_a_third_waits_for_a_landing(self):
        # A (slot 2) + follow-up 1 (slot 5) are outstanding; follow-up 2 (slot 1, 4 elixir) is decided 4 ticks after A
        three = lambda within: [spec(slot=5, after=2), spec(slot=1, after=4, within_ticks=within)]     # noqa: E731
        m, env, _ = run(three(10))                                      # window closes before anything lands (T + 14)
        self.assertEqual(len(acts(env)), 2)
        self.assertEqual(m.result()["follow_ups"], {"fired": 1, "cancelled_outstanding": 1})
        m, env, _ = run(three(30))                                      # the first two land at T + 26: it is decided then
        self.assertEqual(acts(env), [T + D, T + D, T + D + 24])         # asked 22 ticks after T -> 22 - 2 after A's landing
        self.assertEqual(m.result()["follow_ups"], {"fired": 2})

    def test_a_slot_with_a_play_outstanding_is_busy_and_a_card_not_in_hand_is_cancelled(self):
        m, env, _ = run([spec(slot=2, after=2)])                        # the first play's own slot
        self.assertEqual(acts(env), [T + D])
        self.assertEqual(m.result()["follow_ups"], {"cancelled_slot_busy": 1})
        m, env, _ = run([spec(slot=0, after=2)])                        # slot 0's card is not in the hand: no attempt at all
        self.assertEqual(acts(env), [T + D])
        self.assertEqual(m.result()["follow_ups"], {"cancelled_slot_changed": 1})
        self.assertEqual(m.result()["plays_attempted"], 1)              # live cancels it too: nothing is tapped / refused

    def test_every_follow_up_reaches_the_engine_at_its_own_landing_tick_while_a_later_one_waits(self):
        # follow-up 1 (slot 5, 3 elixir) fires at once and lands with the first play at T + 26; follow-up 2 (slot 1, 4 elixir)
        # cannot be paid from T + 26 (it was, before) until T + 40. The engine must not run on to T + 40 before it is sent follow-up 1.
        poor = _Env(lambda t: 6.2 if t < T + 26 else (3.0 if t < T + 40 else 9.0))
        m, env, _ = run([spec(slot=5, after=2), spec(slot=1, after=4, within_ticks=40)], env=poor)
        self.assertEqual(acts(env)[:2], [T + D, T + D])                    # first play and follow-up 1, at their landing tick
        self.assertEqual(len(acts(env)), 3)
        self.assertEqual(acts(env)[2], m.result()["plays"][2]["land_tick"])  # follow-up 2 too: recorded tick == engine tick
        self.assertEqual([p["land_tick"] for p in m.result()["plays"][:2]], [T + D, T + D])
        self.assertGreaterEqual(acts(env)[2], T + 40)
        # and the elixir the SIM believes it has after the landing is the engine's: follow-up 1 is no longer "outstanding"
        self.assertEqual(m.result()["follow_ups"], {"fired": 2})

    def test_follow_ups_are_judged_on_the_frame_grid_after_the_first_tap_returned(self):
        # asked 3 ticks after the decision: the first frame at or after it is T + 4 (frames are 2 ticks apart from T), and it
        # lands at the first play's landing + (4 - 2)
        _, env, _ = run([spec(after=3)])
        self.assertEqual(acts(env), [T + D, T + D + 2])

    def test_no_key_is_byte_identical_to_a_play_without_follow_ups(self):
        a, ea, ta = run(None, script=[PLAY, PLAY])
        b, eb, tb = AD._scripted([PLAY, PLAY], D, env=_Env())
        self.assertEqual((AD._strip(a.result()), ea.eng.calls, ta), (AD._strip(b.result()), eb.eng.calls, tb))
        self.assertNotIn("follow_ups", a.result())
        c, ec, tc = run([], script=[dict(PLAY, follow_ups=[]), PLAY])      # an empty list is also "no follow-ups"
        self.assertEqual((AD._strip(c.result()), ec.eng.calls, tc), (AD._strip(a.result()), ea.eng.calls, ta))

    def test_the_spec_and_the_self_play_side(self):
        self.assertEqual(spec(after=4)["require_first"], True)
        with self.assertRaises(ValueError):
            E.follow_up_spec(0, 0, -1)
        side = E.SelfPlaySide.__new__(E.SelfPlaySide)
        side._record = lambda p, d: T
        side.env, side.cfg, side.delay = SimpleNamespace(hero_abilities=False), {"decide_every": 10}, D
        with self.assertRaises(NotImplementedError):
            side.apply(0.9, dict(PLAY, follow_ups=[spec()]))


class TestSharedVerdict(unittest.TestCase):
    base = dict(tick=100, due=100, expire=110, blocked=None, first_failed=False, slot_changed=False, slot_busy=False,
                n_out=1, have=5.0, cost=3.0)

    def v(self, **kw):
        return E.follow_up_verdict(**{**self.base, **kw})

    def test_order_and_answers(self):
        self.assertEqual(self.v(), ("fire", ""))
        self.assertEqual(self.v(first_failed=True, slot_changed=True), ("cancel", "first_unconfirmed"))
        self.assertEqual(self.v(slot_changed=True, tick=200), ("cancel", "slot_changed"))        # before expiry
        self.assertEqual(self.v(tick=111, blocked="unaffordable"), ("cancel", "unaffordable"))
        self.assertEqual(self.v(tick=111), ("cancel", "late"))
        self.assertEqual(self.v(tick=99), ("wait", "early"))
        self.assertEqual(self.v(slot_busy=True), ("cancel", "slot_busy"))
        self.assertEqual(self.v(n_out=E.FOLLOW_MAX_OUT), ("wait", "outstanding"))
        self.assertEqual(self.v(have=2.9), ("wait", "unaffordable"))
        self.assertEqual(self.v(have=3.0), ("fire", ""))


class TestLiveTwin(unittest.TestCase):
    """live_play.follow_verdict and Match.apply must answer 'can it be paid?' with ONE formula and ONE default horizon."""

    def test_same_formula_and_horizon(self):
        sys.path.insert(0, str(REPO / "scratchpad/gauntlet/L68/live_reader"))
        import live_play as lp
        self.assertEqual(lp.FOLLOW_AFFORD_TICKS, E.FOLLOW_AFFORD_TICKS)
        for el in (2.0, 5.7, 5.9, 6.4, 8.2, 9.99):
            for tick in (500, 2399, 2401, 3601):
                for reserved in (0.0, 3.0):
                    fu = {"d": {"hand_pos": 1, "deck_index": 1, "name": "Knight", "follow": {"after_ticks": 0}},
                          "first": None, "due": 0, "expire": 10 ** 6}
                    me = {"hand_deck_indices": [0, 1, 2, 3], "elixir_raw": int(el * 1e4)}
                    pend = [{"d": {"hand_pos": 0, "name": "Knight"}}] if reserved else []
                    live = lp.follow_verdict(fu, tick, me, pend)[0] == "fire"
                    sim = E.follow_up_have(int(el * 1e4) / 1e4, tick, E.FOLLOW_AFFORD_TICKS, reserved) + 1e-6 >= 3.0
                    self.assertEqual(live, sim, (el, tick, reserved))


if __name__ == "__main__":
    unittest.main()
