"""L67an (owner 2026-09-12): play.py runs on the S1 student alone when no old CNN checkpoint exists.

Without a student the old rule stands (no checkpoint -> no play). With a CNN present nothing changes. Without one, the
forward pass is replaced by neutral logits whose only job is to keep the hand/affordability masks and the placement
path valid -- the student override then makes the decision.
"""
from __future__ import annotations

import os
import unittest

PLAY = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "play.py")


def _src() -> str:
    with open(PLAY, encoding="utf-8") as fh:
        return fh.read()


class NoCnnWiring(unittest.TestCase):
    def test_no_checkpoint_stops_only_without_a_student(self):
        s = _src()
        self.assertIn('if _no_cnn and not cfg.get("play", "student_ckpt", default=None):', s)
        self.assertLess(s.index("_no_cnn = not ckpt_path.exists()"), s.index('ckpt = torch.load(ckpt_path, map_location="cpu")'))

    def test_the_forward_pass_is_guarded_and_neutral_logits_have_the_net_shapes(self):
        s = _src()
        self.assertIn("if net is not None:", s)
        self.assertIn("card_logits = torch.zeros((1, n_cards), device=device)", s)
        self.assertIn("cell_logits = torch.zeros((1, n_cards, n_cells), device=device)", s)

    def test_sizes_come_from_the_deck_before_they_are_used(self):
        s = _src()
        i = s.index("n_cards = len(vision.deck_keys)")
        self.assertLess(i, s.index("yourhalf_cells = [c for c in range(n_cells)"))
        self.assertLess(i, s.index("_cycle_tracker = CycleTracker(n_cards)"))

    def test_the_deck_guard_only_checks_a_real_checkpoint(self):
        self.assertIn("if ckpt is not None and (n_cards != len(vision.deck_keys)", _src())

    def test_a_failed_student_without_a_cnn_stops(self):
        s = _src()
        self.assertIn("if _no_cnn and _student is None:", s)
        self.assertLess(s.index("if _no_cnn and _student is None:"), s.index("def act_in_match(frame)"))

    def test_the_stale_banner_is_gone(self):
        self.assertNotIn("declines to answer", _src())


class NeutralLogitsKeepTheMasksValid(unittest.TestCase):
    """The exact mask steps play.py applies to the logits, run on the neutral tensors."""

    def test_masks_pick_an_affordable_in_hand_card_and_a_deployable_cell(self):
        try:
            import torch
        except ImportError:
            self.skipTest("torch not installed")
        n_cards, n_cells = 10, 432
        card_logits = torch.zeros((1, n_cards))
        cell_logits = torch.zeros((1, n_cards, n_cells))
        hv = torch.zeros((1, n_cards)); hv[0, [1, 4, 6, 8]] = 1.0             # 4 cards in hand
        card_elixir = [3, 4, 3, 6, 6, 3, 2, 2, 1, 3]
        elixir = 2.0
        card_logits = card_logits.masked_fill(hv < 0.5, float("-inf"))
        for i in range(n_cards):
            if elixir + 1e-6 < card_elixir[i]:
                card_logits[0, i] = float("-inf")
        self.assertFalse(bool(torch.isinf(card_logits).all()))
        card_id = int(card_logits.argmax(1).item())
        self.assertIn(card_id, (6, 8))                                         # in hand AND affordable at 2 elixir
        cmask = torch.zeros(n_cells, dtype=torch.bool); cmask[200:300] = True  # deployable cells
        cell = int(cell_logits[0, card_id].masked_fill(~cmask, float("-inf")).unsqueeze(0).argmax(1).item())
        self.assertTrue(bool(cmask[cell]))

    def test_nothing_affordable_still_waits(self):
        try:
            import torch
        except ImportError:
            self.skipTest("torch not installed")
        card_logits = torch.zeros((1, 3))
        hv = torch.ones((1, 3))
        card_logits = card_logits.masked_fill(hv < 0.5, float("-inf"))
        for i, cost in enumerate((5, 6, 4)):
            if 1.0 + 1e-6 < cost:
                card_logits[0, i] = float("-inf")
        self.assertTrue(bool(torch.isinf(card_logits).all()))


if __name__ == "__main__":
    unittest.main()
