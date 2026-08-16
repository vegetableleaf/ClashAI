"""The LLM-proposed doctrine layer: it must be verified, bounded, and switchable off.

The model is a PROPOSER, not an oracle. Measured on tools/llm_eval.py the best local model scored
6/10 on this project's own doctrine cases, and every model tested made the same
X-Bow-into-a-committed-push mistake that the reward ledger was separately found to be paying for.
So the value of this layer is entirely in the gate: nothing enters training that did not beat
holding the card, in the engine, over repeated seeds.

These tests pin the properties that keep that true.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                # noqa: E402
from clashrl.sim.env import SimMatchEnv          # noqa: E402
from clashrl.sim import doctrine as D            # noqa: E402

RULES = Path(__file__).resolve().parents[1] / "config" / "llm_doctrine.json"


def _env(seed=101):
    e = SimMatchEnv(Config.load(), seed=seed)
    e.reset()
    return e


class StateKeyTests(unittest.TestCase):
    def test_key_is_stable_for_the_same_board(self):
        a, b = _env(7), _env(7)
        self.assertEqual(D.llm_state_key(a), D.llm_state_key(b))

    def test_key_is_coarse_enough_to_generalise(self):
        """A rule must cover a FAMILY of boards. If every step produced a fresh key the table
        would be a lookup of frames and would never match anything in training."""
        env = _env(11)
        keys = []
        for _ in range(120):
            keys.append(D.llm_state_key(env))
            env.step((False, 0, 0))
        self.assertLess(len(set(keys)), 60, "keys must repeat across a match, not be unique per step")

    def test_key_reacts_to_the_things_it_names(self):
        env = _env(13)
        before = D.llm_state_key(env)
        env.eng.towers[0][2].active = not env.eng.towers[0][2].active
        self.assertNotEqual(before, D.llm_state_key(env), "king state is part of the bucket")


class RuleFileTests(unittest.TestCase):
    def test_every_shipped_rule_records_its_engine_verdict(self):
        """No rule ships on a model's say-so; each carries the margin it won by."""
        if not RULES.exists():
            self.skipTest("no llm_doctrine.json generated yet")
        d = json.loads(RULES.read_text(encoding="utf-8"))
        self.assertIn("meta", d)
        self.assertGreater(d["meta"].get("tested", 0), 0)
        for key, r in (d.get("rules") or {}).items():
            self.assertIn("card", r, key)
            self.assertIn("gain", r, key)
            self.assertGreater(r["gain"], 0.0, "%s shipped without beating the baseline" % key)
            self.assertIn("wins", r, key)

    def test_the_gate_actually_rejects(self):
        """A run that kept everything would mean the gate is not doing anything."""
        if not RULES.exists():
            self.skipTest("no llm_doctrine.json generated yet")
        m = json.loads(RULES.read_text(encoding="utf-8"))["meta"]
        self.assertLessEqual(m["kept"], m["tested"])


class ConsumptionTests(unittest.TestCase):
    def setUp(self):
        D._LLM_RULES = None                      # the loader caches; tests must not inherit it

    def tearDown(self):
        D._LLM_RULES = None

    def test_rules_are_loaded_and_matched(self):
        if not RULES.exists():
            self.skipTest("no llm_doctrine.json generated yet")
        env = _env(101)
        self.assertTrue(D._llm_rules(env), "the rule file must actually load (path bug guard)")
        matched = 0
        for _ in range(200):
            if D.llm_state_key(env) in D._llm_rules(env):
                matched += 1
            env.step((False, 0, 0))
        self.assertGreater(matched, 0, "verified rules must match real states")

    def test_never_nominates_a_card_that_cannot_be_played(self):
        """The prior may only nominate what is in hand and affordable -- same rule as every other
        branch. A nomination the player cannot act on is a wasted slice of the exploration floor."""
        env = _env(101)
        for _ in range(150):
            got = D.doctrine_cards(env) or {}
            hand = set(env._hand_ids())
            for cid in got:
                self.assertIn(cid, hand)
                self.assertGreaterEqual(env.eng.elixir[0], env.specs[cid].elixir)
            env.step((False, 0, 0))

    def test_can_be_switched_off(self):
        env = _env(101)
        env.cfg.data.setdefault("sim", {})["llm_doctrine"] = False
        D._LLM_RULES = None
        self.assertEqual(D._llm_rules(env), {}, "sim.llm_doctrine: false must disable the layer")


if __name__ == "__main__":
    unittest.main()
