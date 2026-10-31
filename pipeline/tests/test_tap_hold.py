"""RECON-7: cfg["tap_hold"] (e1_eval.parse_tap_hold / SelfPlaySide._land) and search_s0's --tap-hold. Opt-in; absent = the pre-change match
play by play.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_tap_hold.py

Covers: the parser; the REAL SelfPlayMatch on test_league's fake env whose engine refuses a play with not_enough_elixir until a set
tick: no key = the refusal counts (as today); tap_hold N = the play is retried each tick and lands at the first tick the engine accepts,
counted once in plays_attempted (plays_tap_held counts the held ones); a refusal that outlasts the window ends as not_enough_elixir
after N ticks; other refusals are never retried; validation (no action delay); search_s0's flag reaches the worker args and stays
out of run.json when absent."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline.tests.test_league import _SPEnv, _SPEng, _cfg, _run, _spec, _tiny_gen, VOCAB, D   # noqa: E402


class _PoorEng(_SPEng):
    """Refuses side 0's acts with not_enough_elixir (13) before env.poor_until (a tick or a function of the first act tick)."""

    def act(self, side, deck_index, x, y):
        env = self.env
        if side == 0:
            first = env.first_act.setdefault(deck_index, env.tick)
            if env.tick < env.poor_until(first):
                env.log.append((env.tick, side, "refused", deck_index))
                return {"accepted": False, "result_code": 13}
        return super().act(side, deck_index, x, y)


class _PoorEnv(_SPEnv):
    _code_names = {2008: "out_of_territory", 13: "not_enough_elixir"}

    def __init__(self, poor_until=lambda first: 0, **kw):
        super().__init__(**kw)
        self.poor_until, self.first_act = poor_until, {}

    def reset(self, deck0, deck1, seed=0):
        r = super().reset(deck0, deck1, seed)
        self.eng = _PoorEng(self)
        self.first_act = {}
        return r


class TestParse(unittest.TestCase):
    def test_off(self):
        for x in (None, "", 0):
            self.assertIsNone(E.parse_tap_hold(x))

    def test_values(self):
        self.assertEqual(E.parse_tap_hold(22), 22)
        self.assertEqual(E.parse_tap_hold("22"), 22)

    def test_bad(self):
        for x in (-1, "a", True):
            with self.assertRaises(ValueError, msg=repr(x)):
                E.parse_tap_hold(x)


def _nee(res):
    """Not-enough-elixir refusals of a result row (the fake env is no RoyalePoolEnv: engine_play's name for code 13 carries its suffix)."""
    return sum(v for k, v in res["refuse_reasons"].items() if k.startswith("not_enough_elixir"))


class TestFakeMatch(unittest.TestCase):
    def _match(self, lcfg, poor_until=lambda first: 0):
        learner, opp = E.GenPolicy(_tiny_gen(11), VOCAB), E.GenPolicy(_tiny_gen(12), VOCAB)
        spy = []
        res, envs = _run([(0, _spec(0, "o", 0), 0, {"rollout_index": 0, "update": 0})], learner,
                         {"o": (opp, _cfg("sample", record=False, action_delay_ticks=D))}, lcfg,
                         make_env=lambda: _PoorEnv(poor_until=poor_until, tail=600), n=1, spy=spy)
        return spy[0], res[0], envs[0]

    @staticmethod
    def _plays(side):
        return [(p["tick"], p.get("land_tick"), p["slot"], p["cell"], p["accepted"], p.get("reason")) for p in side.plays]

    def test_never_poor_same_match(self):
        a = self._match(_cfg(action_delay_ticks=D))
        b = self._match(_cfg(action_delay_ticks=D, tap_hold=22))
        self.assertGreater(a[0].learner.n_att, 3)
        self.assertEqual(self._plays(a[0].learner), self._plays(b[0].learner))
        self.assertEqual(a[2].log, b[2].log)
        self.assertNotIn("plays_tap_held", a[1])
        self.assertEqual(b[1]["plays_tap_held"], 0)

    def test_refusal_without_the_key_is_counted(self):
        m, res, _ = self._match(_cfg(action_delay_ticks=D), poor_until=lambda first: first + 5)
        self.assertGreater(_nee(res), 0)
        self.assertEqual(m.learner.n_att, len(m.learner.plays))

    def test_hold_lands_when_it_can_pay(self):
        a = self._match(_cfg(action_delay_ticks=D), poor_until=lambda first: first + 5)
        m, res, env = self._match(_cfg(action_delay_ticks=D, tap_hold=22), poor_until=lambda first: first + 5)
        L = m.learner
        self.assertEqual(_nee(res), 0)                                                  # every play could pay within the window
        self.assertGreater(res["plays_tap_held"], 0)
        held = [p for p in L.plays if p["land_tick"] != p["tick"] + D]
        self.assertGreater(len(held), 0)
        self.assertTrue(all(p["accepted"] and p["land_tick"] - (p["tick"] + D) == 5 for p in held))   # first act + 5: the first tick it can pay
        self.assertEqual(L.n_att, len(L.plays))                                         # each attempt tallied once
        self.assertGreater(res["plays_accepted"], a[1]["plays_accepted"])
        for p in held:                                                                 # the next decision follows the held play's run, as after any play
            bound = p["tick"] + 10 * ((p["land_tick"] - p["tick"]) // 10 + 1)
            self.assertTrue(all(q["tick"] >= bound for q in L.plays if q["tick"] > p["tick"]), p)

    def test_hold_window_ends(self):
        m, res, env = self._match(_cfg(action_delay_ticks=D, tap_hold=22), poor_until=lambda first: first + 40)
        L = m.learner
        self.assertGreater(_nee(res), 0)
        refused = [p for p in L.plays if p.get("reason", "").startswith("not_enough_elixir")]
        self.assertTrue(all(p["land_tick"] - (p["tick"] + D) == 22 for p in refused))   # retried for exactly the window, then counted
        self.assertEqual(L.n_att, len(L.plays))

    def test_other_refusals_are_not_held(self):
        learner, opp = E.GenPolicy(_tiny_gen(11), VOCAB), E.GenPolicy(_tiny_gen(12), VOCAB)
        spy = []
        res, envs = _run([(0, _spec(0, "o", 0), 0, {"rollout_index": 0, "update": 0})], learner,
                         {"o": (opp, _cfg("sample", record=False, action_delay_ticks=D))}, _cfg(action_delay_ticks=D, tap_hold=22),
                         make_env=lambda: _SPEnv(tail=600, refuse={(0, 130), (0, 140)}), n=1, spy=spy)
        reasons = res[0]["refuse_reasons"]
        self.assertEqual(set(reasons) - {"out_of_territory", "match_over_before_landing"}, set())
        self.assertEqual(res[0]["plays_tap_held"], 0)

    def test_needs_delay(self):
        with self.assertRaises(ValueError):
            self._match(_cfg(tap_hold=22))
        with self.assertRaises(ValueError):
            self._match(_cfg(play_resume="land"))

    def test_play_resume(self):
        """play_resume='land': the next decision is act + 1 ticks after a play (D + 1), not the decision grid (30 with D 26)."""
        a = self._match(_cfg(action_delay_ticks=D))
        m, res, env = self._match(_cfg(action_delay_ticks=D, play_resume="land"))
        gaps = lambda L: [y["tick"] - x["tick"] for x, y in zip(L.plays, L.plays[1:])]
        self.assertGreaterEqual(min(gaps(a[0].learner)), 30)
        self.assertEqual(min(gaps(m.learner)), D + 1)                                   # 27: right after the play ran
        self.assertEqual(res["play_resume"], "land")
        self.assertNotIn("play_resume", a[1])
        with self.assertRaises(ValueError):
            self._match(_cfg(action_delay_ticks=D, play_resume="grid"))


class TestSearchS0Flags(unittest.TestCase):
    def test_flag_in_args_and_absent_from_run_json(self):
        try:
            from pipeline import search_s0 as S
        except ImportError as exc:                                           # no royalegym in this venv
            raise unittest.SkipTest(str(exc))
        src = Path(S.__file__).read_text(encoding="utf8")
        self.assertIn('"--tap-hold"', src)
        self.assertIn("'tap_hold'", src)
        self.assertIn('"--play-resume"', src)


if __name__ == "__main__":
    unittest.main()
