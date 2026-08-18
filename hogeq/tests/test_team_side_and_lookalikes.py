"""The three ways our own units were read as ENEMIES, locked in (user-reported 2026-08-18).

The deck veto (test_team_veto.py) fixed the opposite error -- enemies read as ours. These are the
remaining paths by which the policy ended up answering its own cards:

1. A defensive BUILDING fell through every evidence rank. It is placed at the front of our half
   (y 0.52-0.60), in front of `deep_mine_y` (0.62); it never marches; it shows no HP bar until
   damaged, and an Evo Tesla hides underground so often shows none at all. Verdict: "unknown".
2. detect_obs painted "unknown" into an ENEMY channel (`_channel_of` maps everything that is not
   "mine" there), so that Tesla appeared to the policy as an enemy attacking building.
3. The deck veto turned a MISREAD of our own card into a phantom enemy: our Mighty Miner detected
   as "miner" is not in the deck, so a hard-evidence "mine" verdict was flipped to "enemy" by
   construction -- the veto amplifying a naming error into a team error.

The fixes: a building-specific side prior split at the RIVER (a building standing on our half can
only have been placed by us -- placement legality, not a soft prior), the canvas skipping
"unknown" outright (the sim never produces the category; painting a guess is out-of-distribution),
and a curated LOOKALIKES rescue that keeps hard-evidence "mine" verdicts and relabels the
detection to the deck twin.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402

from clashrl.replay_mine import Detection, TeamTracker  # noqa: E402

#: This deck (hogeq); the icebow copy of this file swaps its own list in.
OWN = ["hog_rider", "firecracker", "mighty_miner", "tesla", "the_log",
       "earthquake", "skeletons", "ice_spirit"]
BUILDINGS = {"tesla", "cannon", "inferno_tower", "goblin_cage", "bomb_tower", "x_bow", "mortar"}


def _det(cls, cx=0.5, cy=0.5, bar=None, body=None):
    return Detection(cls, cx, cy, 0.05, 0.05, 0.9, "unknown", None, bar, body)


def _tracker(**kw):
    kw.setdefault("own_cards", OWN)
    kw.setdefault("is_building", lambda b: b in BUILDINGS)
    return TeamTracker(**kw)


class TestBuildingSidePrior(unittest.TestCase):
    def test_our_tesla_at_the_front_of_our_half_is_ours(self):
        """The reported bug: y=0.55 is in front of deep_mine_y (0.62), no motion, no bar --
        the old tracker returned 'unknown' and the canvas painted it as an enemy."""
        d = _det("tesla", cy=0.55)
        _tracker().tag([d], 0.0)
        self.assertEqual("mine", d.team)

    def test_an_enemy_building_on_their_half_is_theirs(self):
        d = _det("inferno_tower", cy=0.40)
        _tracker().tag([d], 0.0)
        self.assertEqual("enemy", d.team)

    def test_the_river_gray_zone_stays_unknown(self):
        """Between building_enemy_y (0.46) and building_mine_y (0.50) the prior abstains --
        bars and motion get to decide, not a coin flip. A DECK building probes this (a
        non-deck one would be resolved to enemy by the veto, which is that rule's job)."""
        d = _det("tesla", cy=0.48)
        _tracker().tag([d], 0.0)
        self.assertEqual("unknown", d.team)

    def test_an_open_pocket_voids_the_prior(self):
        """Our left princess down -> the enemy can deploy INTO our half in that lane, so a
        building there must not be presumed ours."""
        tr = _tracker()
        tr.set_towers([False, True], [True, True])
        d = _det("inferno_tower", cx=0.25, cy=0.55)
        tr.tag([d], 0.0)
        self.assertEqual("enemy", d.team)   # non-deck building: veto resolves the abstention

    def test_a_troop_is_not_given_the_building_prior(self):
        """A knight at y=0.55 is in front of deep_mine_y and is NOT a building: the old rules
        apply unchanged and it stays unknown until it moves or bleeds."""
        d = _det("knight", cy=0.55)
        _tracker().tag([d], 0.0)
        self.assertEqual("enemy", d.team)   # knight is not in THIS deck: veto resolves unknown

    def test_without_the_helper_nothing_changes(self):
        """is_building unset -> the prior is inert (monitor constructs TeamTracker bare)."""
        d = _det("tesla", cy=0.55)
        TeamTracker(own_cards=OWN).tag([d], 0.0)
        self.assertEqual("unknown", d.team)


class TestLookalikeRescue(unittest.TestCase):
    def test_marching_miner_is_our_mighty_miner(self):
        """Motion (rank 2) says ours + 'miner' is a curated lookalike of mighty_miner ->
        keep 'mine' AND relabel, instead of manufacturing a phantom enemy."""
        tr = _tracker()
        d0 = _det("miner", cy=0.60)
        tr.tag([d0], 0.0)
        d1 = _det("miner", cy=0.54)          # net dy -0.06: marching toward the enemy
        tr.tag([d1], 0.5)
        self.assertEqual("mine", d1.team)
        self.assertEqual("mighty_miner", d1.base)

    def test_a_static_deep_miner_is_still_the_enemys(self):
        """Rank-4 deep-half prior does NOT qualify for the rescue: an enemy really can park a
        Miner deep in our half, and the veto must keep winning that argument."""
        d = _det("miner", cy=0.70)
        _tracker().tag([d], 0.0)
        self.assertEqual("enemy", d.team)
        self.assertEqual("miner", d.base)

    def test_a_cannon_on_our_half_is_our_tesla(self):
        """BUILDING lookalike at rank 4 IS rescued: the building prior is placement legality,
        not a soft guess -- a cannon standing on our half can only be our Tesla misread."""
        d = _det("cannon", cy=0.55)
        _tracker().tag([d], 0.0)
        self.assertEqual("mine", d.team)
        self.assertEqual("tesla", d.base)

    def test_a_cannon_on_their_half_stays_an_enemy_cannon(self):
        d = _det("cannon", cy=0.40)
        _tracker().tag([d], 0.0)
        self.assertEqual("enemy", d.team)
        self.assertEqual("cannon", d.base)

    def test_the_anchor_rescues_and_relabels_too(self):
        """We just played the Mighty Miner there and the detector says 'miner': rank-1 ground
        truth + lookalike -> ours, relabelled."""
        tr = _tracker()
        tr.record_play(0.5, 0.6, 0.0, base=None)      # play recorded without a base
        d = _det("miner", cx=0.5, cy=0.6)
        tr.tag([d], 0.5)
        self.assertEqual("mine", d.team)
        self.assertEqual("mighty_miner", d.base)

    def test_a_lookalike_of_a_card_we_do_not_own_is_not_rescued(self):
        """wizard -> ice_wizard is in the table, but this deck holds no ice_wizard: the alias
        map is built from OUR deck, so the rescue never fires."""
        tr = _tracker()
        d0 = _det("wizard", cy=0.60)
        tr.tag([d0], 0.0)
        d1 = _det("wizard", cy=0.54)
        tr.tag([d1], 0.5)
        self.assertEqual("enemy", d1.team)

    def test_an_enemy_marching_lookalike_is_not_ours(self):
        """A ram_rider marching DOWN (toward us) is enemy by motion; the rescue only applies
        to 'mine' verdicts."""
        tr = _tracker()
        d0 = _det("ram_rider", cy=0.40)
        tr.tag([d0], 0.0)
        d1 = _det("ram_rider", cy=0.46)
        tr.tag([d1], 0.5)
        self.assertEqual("enemy", d1.team)
        self.assertEqual("ram_rider", d1.base)


class TestUnknownIsNotPainted(unittest.TestCase):
    def _db(self):
        from clashrl.cards import CardDB
        from clashrl.config import Config
        return CardDB(Config.load())

    def test_an_unknown_detection_paints_no_channel(self):
        from clashrl import detect_obs
        d = _det("tesla", cy=0.55)                    # team left "unknown"
        ch = detect_obs.detection_channels([d], self._db(), 64, 36)
        self.assertEqual(0.0, float(ch.sum()),
                         "an unsided unit was painted into the observation")

    def test_a_sided_detection_still_paints(self):
        from clashrl import detect_obs
        d = _det("tesla", cy=0.55)
        d.team = "mine"
        ch = detect_obs.detection_channels([d], self._db(), 64, 36)
        self.assertGreater(float(ch[:, :, 4].sum()), 0.0, "my building channel is empty")
        d.team = "enemy"
        ch = detect_obs.detection_channels([d], self._db(), 64, 36)
        self.assertGreater(float(ch[:, :, 2].sum()), 0.0, "enemy building channel is empty")
        self.assertEqual(0.0, float(ch[:, :, 4].sum()))


if __name__ == "__main__":
    unittest.main(verbosity=1)
