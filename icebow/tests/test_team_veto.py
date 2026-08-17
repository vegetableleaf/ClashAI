"""The two HARD CONSTRAINTS the detector audit added, locked in.

Both come from measuring the live pipeline against the three recorded sessions at the live 10 Hz
cadence (tools/detector_audit.py): 158 of 1482 ally-tagged detections (10.7%) named a card that is
not in the deck, so they were wrong by construction. These are not tuned heuristics -- they are
facts about the game -- so they get tests rather than a threshold to babysit.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402

from clashrl.replay_mine import BoardDetector, Detection, TeamTracker  # noqa: E402

OWN = ["knight", "tesla", "x_bow", "skeletons", "the_log"]


def _det(cls, cx=0.5, cy=0.5, bar=None, body=None):
    return Detection(cls, cx, cy, 0.05, 0.05, 0.9, "unknown", None, bar, body)


class TestDeckVeto(unittest.TestCase):
    def test_side_prior_claims_an_enemy_spell_without_the_veto(self):
        """The bug the veto exists for: an Earthquake landing on OUR tower is born deep in our half
        and never moves, so the first-seen-side prior calls it ours. 40 of the 158 measured."""
        d = _det("earthquake", cy=0.73)
        TeamTracker(own_cards=None).tag([d], 0.0)
        self.assertEqual(d.team, "mine")

    def test_veto_turns_an_impossible_ally_into_an_enemy(self):
        d = _det("earthquake", cy=0.73)
        TeamTracker(own_cards=OWN).tag([d], 0.0)
        self.assertEqual(d.team, "enemy")

    def test_veto_resolves_unknown_for_a_card_we_do_not_own(self):
        """'unknown' is not a safe abstention: the canvas paints it as an enemy while the
        interaction block drops it. A card outside the deck is the opponent's, so say so."""
        d = _det("ronin", cy=0.50)            # mid-board, no bar, no motion -> no evidence at all
        TeamTracker(own_cards=OWN).tag([d], 0.0)
        self.assertEqual(d.team, "enemy")

    def test_veto_leaves_our_own_units_alone(self):
        d = _det("tesla", cy=0.73)            # deep in our half, a card we own -> still ours
        TeamTracker(own_cards=OWN).tag([d], 0.0)
        self.assertEqual(d.team, "mine")

    def test_veto_cannot_see_the_mirror_case(self):
        """Stated as a test so the limit is not forgotten: an ENEMY Knight is in our deck too, so
        the veto passes it through and the audit counts it as correct. The residual is real."""
        d = _det("knight", cy=0.73)
        TeamTracker(own_cards=OWN).tag([d], 0.0)
        self.assertEqual(d.team, "mine")      # wrong in a mirror match, and undetectable here

    def test_own_play_anchor_still_wins_for_a_card_we_own(self):
        tr = TeamTracker(own_cards=OWN)
        tr.record_play(0.5, 0.30, 0.0, base="the_log")    # our Log cast on THEIR half
        d = _det("the_log", cy=0.30)
        tr.tag([d], 0.1)
        self.assertEqual(d.team, "mine")

    def test_anchor_without_a_base_cannot_claim_someone_elses_card(self):
        """record_play(base=None) matches ANY detection near the point; the veto stops it claiming
        a card we do not own."""
        tr = TeamTracker(own_cards=OWN)
        tr.record_play(0.5, 0.70, 0.0, base=None)
        d = _det("mega_knight", cy=0.70)
        tr.tag([d], 0.1)
        self.assertEqual(d.team, "enemy")

    def test_veto_is_off_by_default(self):
        """Offline/labelling callers construct the tracker without a deck and must be unaffected."""
        d = _det("earthquake", cy=0.73)
        TeamTracker().tag([d], 0.0)
        self.assertEqual(d.team, "mine")


class _FakeBox:
    def __init__(self, xyxy, cls_id, conf):
        self.xyxy = np.array([xyxy], dtype=float)
        self.cls = np.array([cls_id], dtype=float)
        self.conf = np.array([conf], dtype=float)


class _FakeModel:
    """One box on the grass, one down in the card tray, same x."""

    def predict(self, frame, conf=0.0, imgsz=960, verbose=False):
        return [type("R", (), {"boxes": [_FakeBox([40, 70, 50, 76], 0, 0.9),
                                         _FakeBox([40, 89, 50, 95], 1, 0.9)]})()]


class TestPlayfieldGate(unittest.TestCase):
    """The detector names the ART ON THE CARDS IN YOUR HAND. Those boxes sit below the arena and
    were entering the board pipeline as units -- 40 of 3761 detections across the sessions, 39 of
    them tagged MINE, because the tray is at the bottom of the frame and the side prior reads the
    bottom of the frame as our half."""

    @staticmethod
    def _detector(arena_box):
        # a 100x100 frame puts the box centres at y = 0.73 (grass) and y = 0.92 (tray)
        return BoardDetector(_FakeModel(), {0: "knight", 1: "mother_witch"}, arena_box=arena_box)

    def test_ungated_keeps_the_tray_box(self):
        got = self._detector(None).detect(np.zeros((100, 100, 3), np.uint8), conf=0.1)
        self.assertEqual(sorted(d.base for d in got), ["knight", "mother_witch"])

    def test_gate_drops_the_tray_box(self):
        got = self._detector([0.03, 0.10, 0.97, 0.86]).detect(
            np.zeros((100, 100, 3), np.uint8), conf=0.1)
        self.assertEqual([d.base for d in got], ["knight"])


if __name__ == "__main__":
    unittest.main()
