"""The live-search decision maker -- specifically, that every guard actually refuses.

A live feature that silently never fires looks identical to one that fires and does nothing, so
each skip path is asserted by NAME here. And the fallback contract is the safety property that
matters: `decide()` returning None means "keep the policy's action", so every failure degrades to
today's behaviour rather than to nothing.
"""
from __future__ import annotations

import random
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                   # noqa: E402
from clashrl.config import Config                                  # noqa: E402
from clashrl.sim.live_search import LiveSearch                     # noqa: E402

_DB = CardDB(path=ROOT / "config" / "cards.yaml")
_CFG = Config.load(ROOT / "config" / "config.yaml")
DECK = ["knight", "archers", "musketeer", "fireball", "zap", "hog_rider", "skeletons", "cannon"]
POLICY = (3, 100)


class _Actions:
    @staticmethod
    def frame_to_board(fx, fy):
        return 0.5, 0.5


def _ls(**kw):
    ls = LiveSearch(_CFG, _DB, random.Random(0), None, "cpu", _Actions(), **kw)
    return ls


def _seen_full_deck(ls):
    for c in DECK:
        ls.record_enemy_play(c)
    return ls


class LiveSearchGuardTests(unittest.TestCase):

    def test_disabled_by_default_and_keeps_the_policy(self):
        ls = _ls()
        self.assertFalse(ls.enabled)
        self.assertIsNone(ls.decide([], [], 5.0, POLICY))
        self.assertEqual(ls.stats["skip_disabled"], 1)

    def test_low_confidence_refuses(self):
        """Below the bar we are guessing at their hand, so the rollout opponent would be fiction."""
        ls = _ls(enabled=True, min_confidence=0.9)
        ls.record_enemy_play("hog_rider")                    # 1/8 of a deck
        self.assertIsNone(ls.decide([{"base": "knight", "x": 1, "y": 1}], [], 5.0, POLICY))
        self.assertEqual(ls.stats["skip_conf"], 1)

    def test_a_stale_frame_refuses(self):
        ls = _seen_full_deck(_ls(enabled=True, max_frame_age_s=0.2))
        self.assertIsNone(ls.decide([], [], 5.0, POLICY, frame_t=time.time() - 5.0))
        self.assertEqual(ls.stats["skip_stale"], 1)

    def test_an_empty_board_refuses(self):
        """With nothing detected the bridge hands the searcher an empty arena it will happily win."""
        ls = _seen_full_deck(_ls(enabled=True, min_bodies=1))
        self.assertIsNone(ls.decide([], [], 5.0, POLICY))
        self.assertEqual(ls.stats["skip_bodies"], 1)

    def test_a_search_failure_degrades_to_the_policy_and_does_not_raise(self):
        """THE SAFETY PROPERTY. net=None makes the real searcher fail; the match must continue."""
        ls = _seen_full_deck(_ls(enabled=True))
        out = ls.decide([{"base": "knight", "x": 1, "y": 1}], [], 5.0, POLICY)
        self.assertIsNone(out)
        self.assertEqual(ls.stats["skip_error"], 1)

    def test_agreement_with_the_policy_returns_None_not_the_action(self):
        """If search picks what the policy already picked, nothing should change downstream."""
        ls = _seen_full_deck(_ls(enabled=True))
        ls._search = lambda eng, opp: POLICY
        self.assertIsNone(ls.decide([{"base": "knight", "x": 1, "y": 1}], [], 5.0, POLICY))
        self.assertEqual(ls.stats["kept_policy"], 1)
        self.assertEqual(ls.stats["changed"], 0)

    def test_a_real_disagreement_is_returned(self):
        ls = _seen_full_deck(_ls(enabled=True))
        ls._search = lambda eng, opp: (7, 200)
        self.assertEqual(ls.decide([{"base": "knight", "x": 1, "y": 1}], [], 5.0, POLICY), (7, 200))
        self.assertEqual(ls.stats["changed"], 1)

    def test_a_search_wait_is_distinguishable_from_keep_policy(self):
        """WAIT must not be confused with None: one holds the card, the other plays the policy's."""
        ls = _seen_full_deck(_ls(enabled=True))
        ls._search = lambda eng, opp: LiveSearch.WAIT
        self.assertEqual(ls.decide([{"base": "knight", "x": 1, "y": 1}], [], 5.0, POLICY),
                         LiveSearch.WAIT)
        self.assertEqual(ls.stats["waited"], 1)

    def test_a_slow_search_is_discarded(self):
        ls = _seen_full_deck(_ls(enabled=True, timeout_ms=1.0))
        def _slow(eng, opp):
            time.sleep(0.05)
            return (7, 200)
        ls._search = _slow
        self.assertIsNone(ls.decide([{"base": "knight", "x": 1, "y": 1}], [], 5.0, POLICY))
        self.assertEqual(ls.stats["skip_timeout"], 1)

    def test_summary_names_every_skip_reason(self):
        ls = _ls()
        ls.decide([], [], 5.0, POLICY)
        for word in ("disabled", "conf", "bodies", "stale", "timeout", "error"):
            self.assertIn(word, ls.summary())


if __name__ == "__main__":
    unittest.main()
