"""The advisor timed out on ~every call, so the model explored with RANDOM cards (user, 2026-08-19).

MEASURED CAUSES, both fixed here:

1. LATENCY. The single-card answer was a JSON object -- `{ "card": "tornado" }`, 10 generated
   tokens at ~44 ms each -- so p50 was 0.855 s against a 0.90 s budget and 30-50% of calls timed
   out. The bare card name costs 3 tokens: p50 0.492 s, and 15/15 calls answered inside the same
   budget where the old shape answered 0/15.

2. THE CIRCUIT BREAKER WAS PERMANENT. Five consecutive failures set disabled=True for the whole
   session, so a slow patch early on meant every later exploration step was a uniform-random card.
   It is now a cooldown with backoff that any single success clears.

A third thing the measurements exposed: the trailing instruction is LOAD-BEARING. On the 13
engine-verified cases in tools/llm_eval.py, "Answer with the card name only." scores 11/13, while
"Reply with ONLY the card name, or hold." scores 3/13 (the model holds 11 times) and appending
nothing scores 0/13. That wording is pinned below because nothing else in the suite can see it.
"""
from __future__ import annotations

import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.llm_advisor import HOLD, LLMAdvisor, _parse_card   # noqa: E402


class _Reply:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps({"message": {"content": self._payload}}).encode()


class _SpyConn:
    """Stands in for the HTTP connection: records the body, replays a scripted answer."""

    def __init__(self, script):
        self.script = list(script)
        self.bodies = []

    def request(self, method, path, body=None, headers=None):
        self.bodies.append(json.loads(body))

    def getresponse(self):
        nxt = self.script.pop(0) if self.script else "tornado"
        if isinstance(nxt, Exception):
            raise nxt
        return _Reply(nxt)

    def close(self):
        pass


def _advisor(script):
    adv = LLMAdvisor()
    conn = _SpyConn(script)
    adv._connection = lambda: conn
    adv._reset = lambda: None            # keep the spy across failures
    return adv, conn


class ParseTests(unittest.TestCase):
    HAND = ["tornado", "tesla", "tesla_evo", "the_log"]

    def test_a_bare_name(self):
        self.assertEqual("tornado", _parse_card("tornado", self.HAND))

    def test_quotes_case_and_punctuation(self):
        self.assertEqual("tesla", _parse_card('  "Tesla."\n', self.HAND))

    def test_a_sentence_still_yields_the_card(self):
        self.assertEqual("the_log", _parse_card("Play the log to clear the swarm.", self.HAND))

    def test_the_longer_name_wins(self):
        """`tesla` is a prefix of `tesla_evo` -- a substring match must not steal the evo."""
        self.assertEqual("tesla_evo", _parse_card("tesla_evo", self.HAND))

    def test_hold_survives(self):
        self.assertEqual(HOLD, _parse_card("hold", self.HAND))

    def test_an_unknown_word_is_returned_for_the_caller_to_reject(self):
        """It must NOT silently become a card: the caller's hand check turns this into a fallback."""
        self.assertNotIn(_parse_card("fireball", self.HAND), self.HAND)


class RequestShapeTests(unittest.TestCase):
    def test_the_single_card_request_sends_no_json_schema(self):
        """The schema's JSON wrapper is the latency: 10 generated tokens instead of 3."""
        adv, conn = _advisor(["tornado"])
        adv.suggest("ENEMY: a hog rider in your half.", ["tornado", "tesla"], 7.0)
        self.assertNotIn("format", conn.bodies[0],
                         "the single-card call is back on the slow JSON-schema path")
        self.assertLessEqual(conn.bodies[0]["options"]["num_predict"], 8)

    def test_the_trailing_instruction_is_the_measured_wording(self):
        """11/13 with this line; 3/13 if it ends with 'or hold'; 0/13 with nothing appended."""
        adv, conn = _advisor(["tornado"])
        adv.suggest("ENEMY: a hog rider in your half.", ["tornado", "tesla"], 7.0)
        prompt = conn.bodies[0]["messages"][0]["content"]
        self.assertTrue(prompt.rstrip().endswith("Answer with the card name only."),
                        "the measured trailing instruction changed -- re-run tools/llm_eval.py "
                        "before accepting a new one")
        self.assertFalse(prompt.rstrip().endswith("or hold."),
                         "this wording measured 3/13: the model holds 11 times")

    def test_the_plan_path_keeps_its_schema(self):
        """A multi-card sequence still needs the structure (and it is off by default)."""
        adv, conn = _advisor(['{"cards": ["tesla", "the_log"]}'])
        adv.suggest_plan("ENEMY: a golem push.", ["tesla", "the_log"], 9.0)
        self.assertIn("format", conn.bodies[0])


class CircuitBreakerTests(unittest.TestCase):
    """The reported symptom was not slowness -- it was the advisor DYING five calls in."""

    def test_it_rests_after_a_failure_streak_instead_of_calling(self):
        adv, conn = _advisor([TimeoutError("timed out")] * 5)
        for _ in range(5):
            adv.suggest("ENEMY: nothing.", ["tornado"], 5.0)
        before = len(conn.bodies)
        self.assertIsNone(adv.suggest("ENEMY: nothing.", ["tornado"], 5.0))
        self.assertEqual(before, len(conn.bodies),
                         "it kept calling a server that just failed 5 times in a row")

    def test_it_comes_back_after_the_cooldown(self):
        """The old code set disabled=True FOREVER: one bad patch meant a whole random session."""
        adv, conn = _advisor([TimeoutError("timed out")] * 5 + ["tornado"])
        for _ in range(5):
            adv.suggest("ENEMY: nothing.", ["tornado"], 5.0)
        self.assertFalse(adv.disabled, "the advisor disabled itself permanently again")
        adv._cooldown_until = time.time() - 0.01          # the rest has elapsed
        self.assertEqual("tornado", adv.suggest("ENEMY: nothing.", ["tornado"], 5.0),
                         "it never tried again after resting")

    def test_one_good_answer_clears_the_backoff(self):
        adv, _ = _advisor([TimeoutError("x")] * 5 + ["tornado"])
        for _ in range(5):
            adv.suggest("ENEMY: nothing.", ["tornado"], 5.0)
        adv._cooldown_until = time.time() - 0.01
        adv.suggest("ENEMY: nothing.", ["tornado"], 5.0)
        self.assertEqual(0, adv._cooldowns)
        self.assertEqual(0.0, adv._cooldown_until)

    def test_the_backoff_grows_when_it_keeps_failing(self):
        adv, _ = _advisor([TimeoutError("x")] * 12)
        for _ in range(5):
            adv.suggest("ENEMY: nothing.", ["tornado"], 5.0)
        first = adv._cooldown_until - time.time()
        adv._cooldown_until = time.time() - 0.01
        for _ in range(5):
            adv.suggest("ENEMY: nothing.", ["tornado"], 5.0)
        second = adv._cooldown_until - time.time()
        self.assertGreater(second, first,
                           "a dead server is re-probed just as often as the first time")


if __name__ == "__main__":
    unittest.main(verbosity=1)
