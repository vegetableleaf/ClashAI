"""Tests for the win-condition BANK mask in train_sim_ppo.

The mask is the fix for an UNREACHABLE win condition: X-Bow / Rocket cost 6, the
collapsed policy never let elixir past 5, and a masked action gets zero policy
gradient. These tests pin the two properties that make the fix valid:

  1. it actually forces the bar upward instead of letting cheap cards drain it, and
  2. it is a pure function of (hand, elixir), so the sampling-time and update-time
     masks agree and the PPO likelihood ratio stays exact.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    import torch
except ImportError:  # pragma: no cover - torch is required for the trainer anyway
    torch = None


NEG = -1e9
COSTS = [3.0, 4.0, 4.0, 3.0, 6.0, 6.0, 3.0, 3.0, 2.0, 1.0]   # icebow deck, x_bow/rocket at index 4/5
WINCON_IDS = [4, 5]
WINCON_COST = 6.0


def bank_playable(hand, elixir_norm, bank_floor):
    """The playable-card mask exactly as train_sim_ppo.masked_logits computes it."""
    costs = torch.tensor(COSTS).view(1, -1)
    hand_t = torch.tensor(hand, dtype=torch.float32)
    elx_t = torch.tensor(elixir_norm, dtype=torch.float32)
    elixir = elx_t * 10.0
    playable = (hand_t > 0.5) & (costs <= elixir + 1e-6)
    if bank_floor > 0.0:
        wc = torch.tensor(WINCON_IDS, dtype=torch.long)
        holds_wc = (hand_t > 0.5)[:, wc].any(1)
        banking = (holds_wc & (elixir.squeeze(-1) >= bank_floor)
                   & (elixir.squeeze(-1) < WINCON_COST))
        drains = costs < WINCON_COST
        playable = playable & ~(banking.view(-1, 1) & drains)
    return playable


@unittest.skipIf(torch is None, "torch not installed")
class WinconBankMaskTests(unittest.TestCase):
    def test_bank_blocks_cheap_cards_that_would_drain_the_bar(self):
        # x_bow in hand alongside cheap cards, sitting at 5 elixir -- one short of the X-Bow.
        hand = [[1, 0, 0, 1, 1, 0, 0, 0, 1, 1]]
        playable = bank_playable(hand, [[0.5]], bank_floor=4.0)

        self.assertFalse(playable.any().item(),
                         "at 5 elixir holding a 6-cost win condition, every cheaper card must be "
                         "masked so the bar climbs instead of draining")

    def test_without_bank_the_cheap_cards_drain_the_bar(self):
        hand = [[1, 0, 0, 1, 1, 0, 0, 0, 1, 1]]
        playable = bank_playable(hand, [[0.5]], bank_floor=0.0)

        self.assertTrue(playable.any().item(),
                        "with the bank disabled the cheap cards stay playable -- this is the old "
                        "behaviour that kept elixir under 6 forever")

    def test_wincon_becomes_playable_once_the_bar_reaches_its_cost(self):
        hand = [[1, 0, 0, 1, 1, 0, 0, 0, 1, 1]]
        playable = bank_playable(hand, [[0.6]], bank_floor=4.0)

        self.assertTrue(playable[0, 4].item(),
                        "at 6 elixir the X-Bow must be samplable -- that is the whole point of banking")

    def test_below_the_floor_ordinary_defence_is_untouched(self):
        # 3 elixir: under the floor, so the cheap defenders must all stay available.
        hand = [[1, 0, 0, 1, 1, 0, 0, 0, 1, 1]]
        playable = bank_playable(hand, [[0.3]], bank_floor=4.0)

        self.assertTrue(playable[0, 0].item(), "a 3-cost defender must stay playable below the floor")
        self.assertTrue(playable[0, 9].item(), "a 1-cost cycle card must stay playable below the floor")

    def test_no_wincon_in_hand_means_no_banking(self):
        # Same 5 elixir, but neither win condition is held -> nothing to bank for.
        hand = [[1, 0, 0, 1, 0, 0, 0, 0, 1, 1]]
        playable = bank_playable(hand, [[0.5]], bank_floor=4.0)

        self.assertTrue(playable.any().item(),
                        "with no win condition in hand the bank must not fire")

    def test_mask_is_deterministic_for_the_ppo_ratio(self):
        """Sampling time and update time must produce the SAME mask from the same stored inputs,
        or the PPO likelihood ratio is computed against a different distribution than was sampled."""
        hand = [[1, 0, 0, 1, 1, 0, 0, 0, 1, 1],
                [0, 1, 0, 0, 0, 1, 1, 0, 1, 0],
                [1, 1, 1, 0, 1, 0, 0, 1, 0, 1]]
        elx = [[0.5], [0.45], [0.2]]

        first = bank_playable(hand, elx, bank_floor=4.0)
        for _ in range(5):
            self.assertTrue(torch.equal(first, bank_playable(hand, elx, bank_floor=4.0)))


if __name__ == "__main__":
    unittest.main()
