"""The WAIT/PLAY rule must be the SAME in training, diagnostics and live play.

Found by CLASHAI_IMPLEMENTATION_SPEC.md and confirmed at HEAD: train_rl compared the two gate
logits alone, policy_stats did the same, and play.py added `+ max_card + max_cell` to the PLAY
side. So a DDQN checkpoint learned one gate rule and was deployed under another, and live play
was the odd one out of the three.

Why gate-only is the correct rule: train_rl's card and cell heads are dueling-style ADVANTAGES,
zero at their own argmax over the legal set, so

    max over (card, cell) of Q(s, play, card, cell) == gate[play]

and the comparison is one head against one head. Adding the maxima makes it three heads against
one; since all three are trained on the same TD error, any systematic negative return on plays
pushes them down together and WAIT wins by construction -- the passivity ratchet.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import torch  # noqa: E402


def ddqn_wait(gate_logits) -> bool:
    """The trainer's rule (train_rl.choose): gate logits only."""
    return bool(gate_logits[0, 0] >= gate_logits[0, 1])


def ppo_wait(gate_logits, tau: float) -> bool:
    return bool(torch.sigmoid(gate_logits[0, 1] - gate_logits[0, 0]) <= tau)


class GateParityTests(unittest.TestCase):
    def test_ddqn_gate_ignores_card_and_cell_magnitudes(self):
        """The regression itself: with a WAIT-preferring gate, huge card/cell values must not
        flip the decision to PLAY."""
        gate = torch.tensor([[2.0, 1.0]])          # wait > play
        for bonus in (0.0, 5.0, 50.0, 500.0):
            with self.subTest(bonus=bonus):
                old_rule = bool(gate[0, 0] >= gate[0, 1] + bonus + bonus)
                self.assertTrue(ddqn_wait(gate))
                if bonus > 1.0:
                    self.assertNotEqual(old_rule, ddqn_wait(gate),
                                        "this is the case where the two rules disagreed")

    def test_ddqn_plays_when_the_play_logit_wins(self):
        self.assertFalse(ddqn_wait(torch.tensor([[0.1, 0.9]])))

    def test_ddqn_ties_wait(self):
        """`>=` -- a tie holds. Pinned because flipping it silently doubles the play rate."""
        self.assertTrue(ddqn_wait(torch.tensor([[0.5, 0.5]])))

    def test_live_play_uses_the_trainer_rule(self):
        """Parity by source: play.py must not reintroduce the card/cell maxima."""
        with open(os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "play.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("play_val = gate_logits[0, 1] + card_logits.max()", src,
                         "play.py has drifted back to the three-heads-against-one gate")
        self.assertIn("wait = bool(gate_logits[0, 0] >= gate_logits[0, 1])", src)

    def test_policy_stats_uses_the_trainer_rule(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "src", "clashrl",
                               "policy_stats.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("bool(gq[i, 0] >= gq[i, 1])", src)

    def test_ppo_threshold_behaviour(self):
        """PPO heads are logits, not advantages, so that branch is a thresholded probability."""
        gate = torch.tensor([[0.0, 0.0]])          # sigmoid(0) = 0.5
        self.assertFalse(ppo_wait(gate, tau=0.25))
        self.assertTrue(ppo_wait(gate, tau=0.75))


if __name__ == "__main__":
    unittest.main()
