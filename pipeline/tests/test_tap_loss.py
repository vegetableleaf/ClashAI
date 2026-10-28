"""L74 W18: cfg["tap_loss"] (e1_eval.parse_tap_loss / SelfPlaySide) and search_s0's --tap-loss / --opp-tau.
Opt-in; absent = the pre-change match play by play.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_tap_loss.py

Covers: the parser (off, string, dict, bad windows / values); the REAL SelfPlayMatch on test_league's fake env: rates 0 =
the same decisions, plays and engine acts as no key; a high rate = some learner plays never reach the engine (reason
tap_lost, counted in plays_tap_lost), the learner's decision schedule and the opponent's plays unchanged; validation
(no action delay); search_s0's flags reach the worker args and stay out of run.json when absent."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline.tests.test_league import _SPEnv, _cfg, _run, _spec, _tiny_gen, VOCAB, D   # noqa: E402


class TestParse(unittest.TestCase):
    def test_off(self):
        for x in (None, "", {}):
            self.assertIsNone(E.parse_tap_loss(x))

    def test_values(self):
        self.assertEqual(E.parse_tap_loss("1x:0.02, ot3x:0.08"), {"1x": .02, "2x": 0.0, "ot2x": 0.0, "ot3x": .08})
        self.assertEqual(E.parse_tap_loss({"2x": .5}), {"1x": 0.0, "2x": .5, "ot2x": 0.0, "ot3x": 0.0})
        self.assertEqual([E.tap_loss_p(E.parse_tap_loss("1x:.1,2x:.2,ot2x:.3,ot3x:.4"), t) for t in (0, 2399, 2400, 3600, 4800, 7000)],
                         [.1, .1, .2, .3, .4, .4])

    def test_bad(self):
        for x in ("3x:0.1", "1x:1.0", "1x:-0.1", "1x", "1x:a", {"1x": True}):
            with self.assertRaises(ValueError, msg=repr(x)):
                E.parse_tap_loss(x)


class TestFakeMatch(unittest.TestCase):
    def _match(self, lcfg):
        learner, opp = E.GenPolicy(_tiny_gen(11), VOCAB), E.GenPolicy(_tiny_gen(12), VOCAB)
        spy = []
        res, envs = _run([(0, _spec(0, "o", 0), 0, {"rollout_index": 0, "update": 0})], learner,
                         {"o": (opp, _cfg("sample", record=False, action_delay_ticks=D))}, lcfg,
                         make_env=lambda: _SPEnv(tail=600), n=1, spy=spy)
        return spy[0], res[0], envs[0]

    @staticmethod
    def _plays(side):
        return [(p["tick"], p.get("land_tick"), p["slot"], p["cell"], p["accepted"]) for p in side.plays]

    def test_zero_rates_same_match(self):
        a = self._match(_cfg(action_delay_ticks=D))
        b = self._match(_cfg(action_delay_ticks=D, tap_loss="1x:0,2x:0"))
        self.assertGreater(a[0].learner.n_att, 3)
        self.assertEqual(self._plays(a[0].learner), self._plays(b[0].learner))
        self.assertEqual(self._plays(a[0].opp), self._plays(b[0].opp))
        self.assertEqual(a[2].log, b[2].log)
        self.assertNotIn("plays_tap_lost", a[1])
        self.assertEqual(b[1]["plays_tap_lost"], 0)

    def test_high_rate_loses_plays(self):
        a = self._match(_cfg(action_delay_ticks=D))
        m, res, env = self._match(_cfg(action_delay_ticks=D, tap_loss="1x:0.6"))
        L = m.learner.side
        lost = [p for p in m.learner.plays if p.get("reason") == "tap_lost"]
        self.assertGreater(len(lost), 0)
        self.assertEqual(res["plays_tap_lost"], len(lost))
        self.assertEqual(res["refuse_reasons"].get("tap_lost"), len(lost))
        acts = [t for (t, sd, *_) in env.log if sd == L]                         # a lost play never reaches the engine
        self.assertEqual(sorted(acts), sorted(p["land_tick"] for p in m.learner.plays if p.get("reason") != "tap_lost"
                                              and p.get("reason") != "match_over_before_landing"))
        self.assertTrue(all(not p["accepted"] for p in lost))
        # the fake board is f(tick): the opponent's plays do not depend on ours, so they are unchanged
        self.assertEqual(self._plays(a[0].opp), self._plays(m.opp))

    def test_slow_taps_land_late(self):
        self.assertEqual(E.parse_tap_slow("0.2:18"), (0.2, 18))
        for x in ("1.0:18", "0.2:0", "0.2", "a:b"):
            with self.assertRaises(ValueError, msg=x):
                E.parse_tap_slow(x)
        base = self._match(_cfg(action_delay_ticks=D))
        m, res, env = self._match(_cfg(action_delay_ticks=D, tap_slow="0.5:18"))
        late = [p for p in m.learner.plays if p.get("land_tick") == p["tick"] + D + 18]
        self.assertGreater(len(late), 0)
        self.assertEqual(res["plays_tap_slow"], len(late))                  # every recorded play carries its land_tick
        self.assertTrue(all(p.get("land_tick") in (p["tick"] + D, p["tick"] + D + 18) for p in m.learner.plays))
        self.assertEqual(self._plays(base[0].opp), self._plays(m.opp))
        z = self._match(_cfg(action_delay_ticks=D, tap_slow="0:18"))          # P 0 = the same match
        self.assertEqual(self._plays(base[0].learner), self._plays(z[0].learner))
        self.assertEqual(base[2].log, z[2].log)

    def test_needs_delay(self):
        with self.assertRaises(ValueError):
            self._match(_cfg(tap_loss="1x:0.1"))


class TestFollowUps(unittest.TestCase):
    """G2 with the live stack's follow_ups plays (was: ValueError): every tap -- the first play and each fired follow-up -- draws
    its own loss / slowness; rates 0 = the same match as no key."""

    def _drive(self, **over):
        from pipeline.tests import test_e1_follow_up_selfplay as FU
        m, lt, _ = FU.drive({0: (0, [FU.spec(after=4)]), 3: (2, [FU.spec(slot=3, after=4)])}, cfg_over=over or None)
        return m, lt, FU.acts(m)

    def test_zero_rates_same_match(self):
        a = self._drive()
        b = self._drive(tap_loss="1x:0", tap_slow="0:18")
        self.assertEqual(a[2], b[2])
        self.assertEqual(a[1], b[1])
        self.assertEqual(dict(a[0].learner.follow_n), dict(b[0].learner.follow_n))
        self.assertEqual(len(a[2]), 4)

    def test_lost_taps_never_reach_the_engine(self):
        m, _, acts = self._drive(tap_loss="1x:0.95")
        lost = [p for p in m.learner.plays if p.get("reason") == "tap_lost"]
        self.assertGreater(len(lost), 0)
        self.assertEqual(m.learner.n_tap_lost, len(lost))
        self.assertEqual(sorted(t for t, _ in acts), sorted(p["land_tick"] for p in m.learner.plays if p.get("reason") != "tap_lost"))

    def test_slow_taps_land_late(self):
        base = self._drive()
        m, _, acts = self._drive(tap_slow="0.95:18")
        self.assertGreater(m.learner.n_tap_slow, 0)
        self.assertEqual(base[0].learner.plays[0]["land_tick"] + 18, m.learner.plays[0]["land_tick"])  # a slow first tap
        self.assertGreater(m.learner.plays[1]["land_tick"], m.learner.plays[0]["land_tick"])            # its follow-up after it
        self.assertEqual(m.learner.plays[1]["why"], "follow_up")


class TestSearchS0Flags(unittest.TestCase):
    def setUp(self):
        try:
            from pipeline import search_s0 as S
        except ImportError as exc:                                           # no royalegym in this venv
            raise unittest.SkipTest(str(exc))
        self.S = S

    def test_flags_parse(self):
        src = (REPO / "pipeline" / "search_s0.py").read_text(encoding="utf-8")
        for flag in ("--opp-tau", "--tap-loss", "--tap-slow"):
            self.assertEqual(src.count(f'ap.add_argument("{flag}"'), 1, flag)
        self.assertIn("'opp_tau', 'tap_loss', 'tap_slow', 'probe_xbow_start') or v is not None)", src)      # absent = not written to run.json
        self.assertIn("learner_cfg['tap_loss'] = E.parse_tap_loss(args['tap_loss'])", src)


if __name__ == "__main__":
    unittest.main()
