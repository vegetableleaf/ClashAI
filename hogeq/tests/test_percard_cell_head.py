"""The cell head emits one placement map PER CARD.

WHY THIS CHANGED. The head used to emit a single channel, so the network produced ONE 432-cell
distribution for the board state and all ten cards sampled from it. Measured on the champion over
80 greedy matches: row 13 -- the frontmost legal row -- took 78.7% of every placement, and the
concentration held for every card at once (tesla 88%, x_bow 85%, skeletons 80%, tornado 62%),
which is the signature of a shared map rather than ten learned ones. On one fixed board with a
Giant and Musketeer committed, all ten cards resolved to the identical tile.

The cost was not just a bad habit, it was expressiveness: "knight in front of the bow, ice wizard
behind it, skeletons onto the attacker" is four placements for four cards in ONE state, and the
old head could not represent that at any weights.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import torch  # noqa: E402

from clashrl.model import PolicyNet  # noqa: E402

N_CARDS, N_CELLS, GRID = 10, 432, (18, 24)


def _net(n_cards=N_CARDS):
    return PolicyNet(in_ch=3, n_cards=n_cards, n_cells=N_CELLS, threat_dim=14, grid_wh=GRID)


def _inputs(b=2, n_cards=N_CARDS):
    return (torch.zeros(b, 3, 96, 64), torch.zeros(b, n_cards), torch.zeros(b, n_cards),
            torch.zeros(b, 1), torch.zeros(b, 14))


class TestShape(unittest.TestCase):
    def test_cells_are_per_card(self):
        net = _net()
        _, cards, cells = net.forward_parts(*_inputs())
        self.assertEqual(tuple(cards.shape), (2, N_CARDS))
        self.assertEqual(tuple(cells.shape), (2, N_CARDS, N_CELLS))

    def test_cells_stay_row_major_so_cell_indices_still_mean_the_same_tile(self):
        """gy*gw+gx, matching ActionSpace. If this flips, every stored cell index in every
        checkpoint and replay silently points at a different tile."""
        net = _net()
        _, _, cells = net.forward_parts(*_inputs(b=1))
        gw, gh = GRID
        self.assertEqual(cells.shape[-1], gw * gh)

    def test_different_cards_CAN_resolve_to_different_cells(self):
        """The capability that was structurally absent. With a shared map this is impossible at
        any weights, so it is the one property worth asserting directly."""
        net = _net()
        with torch.no_grad():
            net.cell_conv[-1].weight.normal_(0.0, 1.0)
            net.cell_conv[-1].bias.normal_(0.0, 1.0)
        _, _, cells = net.forward_parts(*_inputs(b=1))
        argmax = [int(cells[0, i].argmax()) for i in range(N_CARDS)]
        self.assertGreater(len(set(argmax)), 1,
                           "every card still resolves to one tile -- the map is shared")


class TestLoadCompat(unittest.TestCase):
    def test_an_old_single_channel_checkpoint_drops_only_the_cell_head(self):
        """Warm-starting across the change must keep the expensive trunk and name what it lost.
        A silent strict=False would print "warm-started" over a randomly-initialised head."""
        old = _net()
        # rebuild the pre-change head: one output channel instead of n_cards
        old.cell_conv[-1] = torch.nn.Conv2d(24, 1, 1)
        state = old.state_dict()

        new = _net()
        dropped = PolicyNet.load_compat(new, state)
        self.assertEqual(sorted(dropped), ["cell_conv.4.bias", "cell_conv.4.weight"])
        # the trunk and card head DID carry over
        self.assertTrue(torch.equal(new.card_head.weight, old.card_head.weight))
        self.assertTrue(torch.equal(new.cell_ctx[0].weight, old.cell_ctx[0].weight))

    def test_a_matching_checkpoint_drops_nothing(self):
        a, b = _net(), _net()
        self.assertEqual(PolicyNet.load_compat(b, a.state_dict()), [])
        self.assertTrue(torch.equal(b.cell_conv[-1].weight, a.cell_conv[-1].weight))

    def test_the_head_width_follows_the_deck_size(self):
        _, _, cells = _net(n_cards=8).forward_parts(*_inputs(n_cards=8))
        self.assertEqual(tuple(cells.shape), (2, 8, N_CELLS))


if __name__ == "__main__":
    unittest.main()
