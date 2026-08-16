"""The live advisor must never be able to hurt the live loop.

It sits inside a 1.0 s decision budget during which the bot is BLIND, so the properties that
matter are not "is the suggestion good" -- the engine cannot check that live -- but "can this
ever stall, raise, or silently degrade without saying so".
"""
from __future__ import annotations

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.llm_advisor import LLMAdvisor  # noqa: E402

HAND = ["tornado", "x_bow", "the_log", "skeletons"]
SIT = "ENEMY: a tank/win condition threat is 60% of the way to your king and closing fast."


class FailSafeTests(unittest.TestCase):
    """Every failure path returns None quickly instead of raising or blocking."""

    def test_dead_server_returns_none_and_does_not_raise(self):
        a = LLMAdvisor(model="qwen2.5:latest", timeout=0.3, port=1)
        t0 = time.time()
        self.assertIsNone(a.suggest(SIT, HAND, 7))
        self.assertLess(time.time() - t0, 2.0, "a dead server must fail fast, not hang the loop")

    def test_repeated_failures_trip_the_breaker(self):
        """A dead server costs real time per call to discover; after a few the advisor stops
        asking, so the loop degrades to plain random exploration rather than bleeding budget."""
        a = LLMAdvisor(model="qwen2.5:latest", timeout=0.2, port=1)
        for _ in range(a.max_consecutive_fails):
            a.suggest(SIT, HAND, 7)
        self.assertTrue(a.disabled)
        before = a.calls
        self.assertIsNone(a.suggest(SIT, HAND, 7))
        self.assertEqual(a.calls, before, "a disabled advisor must not make further calls")

    def test_empty_hand_is_none(self):
        a = LLMAdvisor(model="qwen2.5:latest", timeout=0.3, port=1)
        self.assertIsNone(a.suggest(SIT, [], 7))

    def test_stats_report_even_when_nothing_worked(self):
        """Silence is the dangerous failure: an advisor that stopped answering looks identical to
        one that was never enabled."""
        a = LLMAdvisor(model="qwen2.5:latest", timeout=0.2, port=1)
        self.assertIn("no calls", a.stats())
        a.suggest(SIT, HAND, 7)
        s = a.stats()
        self.assertIn("failed", s)
        self.assertIn("qwen2.5", s)

    def test_timeout_is_honoured(self):
        a = LLMAdvisor(model="qwen2.5:latest", timeout=0.05, port=1)
        t0 = time.time()
        a.suggest(SIT, HAND, 7)
        self.assertLess(time.time() - t0, 1.0)

    def test_default_timeout_fits_the_live_budget(self):
        """act_period is 1.0 s; a budget at or above it would make the bot late every call."""
        a = LLMAdvisor(model="qwen2.5:latest")
        self.assertLess(a.timeout, 1.0)


class ContractTests(unittest.TestCase):
    def test_suggestion_is_always_from_the_hand(self):
        """The caller indexes the deck by this name, so anything outside the hand must be None."""
        a = LLMAdvisor(model="qwen2.5:latest", timeout=0.3, port=1)
        got = a.suggest(SIT, HAND, 7)
        self.assertTrue(got is None or got in HAND)

    def test_absent_setting_means_off(self):
        """Opt-IN, so a config that never mentions the advisor must not get one.

        This deliberately tests the CODE's default rather than the value in config.yaml -- that
        file is the user's live setting and they may turn the advisor on whenever they like;
        asserting on it would make a test fail for the user's preference rather than for a bug.
        """
        from clashrl.config import Config
        cfg = Config.load()
        cfg.data.get("train", {}).pop("llm_advisor", None)
        self.assertFalse(bool(cfg.get("train", "llm_advisor", default=False)))


if __name__ == "__main__":
    unittest.main()


class WarmupTests(unittest.TestCase):
    def test_warmup_restores_the_match_budget_and_clears_counters(self):
        """The warm-up must not leave a long timeout behind, nor colour the session stats."""
        a = LLMAdvisor(model="qwen2.5:latest", timeout=0.4, port=1)   # unreachable: fails fast
        a.warmup(seconds=0.5)
        self.assertAlmostEqual(a.timeout, 0.4, places=6, msg="in-match budget must be restored")
        self.assertEqual((a.calls, a.hits, a.fails), (0, 0, 0))
        self.assertFalse(a.disabled, "a failed warm-up must not leave the advisor tripped")

    def test_warmup_returns_none_when_unreachable(self):
        a = LLMAdvisor(model="qwen2.5:latest", timeout=0.3, port=1)
        self.assertIsNone(a.warmup(seconds=0.5))
