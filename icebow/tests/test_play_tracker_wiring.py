"""L67y T1 (HANDOFF 5cs.99 AD): live play's TeamTracker gets the filters train-rl's env.py always had.

play.py built its TeamTracker without `is_spell`, so enemy SPELL detections were served to the aim assists -- among
them a false enemy "earthquake" the detector reads on our own king tower (48 of 270 captured states), which the
Tornado king-activation assist aimed at (41 of 106 run12 Tornados redirected). Pinned two ways: the wiring in
play.py's source, and the behaviour of a tracker built with play.py's exact filter.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import card_threat                                           # noqa: E402
from clashrl.cards import CardDB                                          # noqa: E402
from clashrl.config import Config                                         # noqa: E402
from clashrl.replay_mine import Detection, TeamTracker, own_card_bases    # noqa: E402

PLAY = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "play.py")


def _construction() -> str:
    with open(PLAY, encoding="utf-8") as fh:
        src = fh.read()
    i = src.index("_team_tracker = TeamTracker(")
    depth, j = 0, src.index("(", i)
    for k in range(j, len(src)):
        depth += {"(": 1, ")": -1}.get(src[k], 0)
        if depth == 0:
            return src[i:k + 1]
    raise AssertionError("unbalanced TeamTracker( call in play.py")


def _det(base, x, y, team="unknown"):
    return Detection(base, x, y, 0.05, 0.05, 0.9, team, None, None, None)


class PlayTrackerWiring(unittest.TestCase):
    def test_play_passes_the_three_filters_env_py_passes(self):
        call = _construction()
        for kw in ("is_spell=", "min_hits=", "phantom_stale_s="):
            self.assertIn(kw, call, f"play.py's TeamTracker is missing {kw}")
        self.assertTrue(re.search(r'is_spell=lambda b, _db=_db: _db\.kind\(card_threat\.base_key\(str\(b\)\)\) == "spell"', call),
                        "play.py's is_spell is not the base-folded CardDB spell check this test exercises")


class PlaysSpellFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = CardDB(Config.load())

    def _tracker(self):
        db = self.db
        return TeamTracker(own_cards=own_card_bases(db), min_hits=2, phantom_stale_s=6.0,
                           is_spell=lambda b, _db=db: _db.kind(card_threat.base_key(str(b))) == "spell")

    def _served(self, base, x, y):
        tr = self._tracker()
        tr.tag([_det(base, x, y)], 0.0)
        tr.tag([_det(base, x, y + 0.005)], 0.15)                 # corroborated: min_hits is not what removes it
        return [t[4] for t in tr.enemy_tracks(0.2, True)]

    def test_the_false_enemy_earthquake_on_our_king_is_not_served(self):
        self.assertEqual(self._served("earthquake", 0.495, 0.72), [])

    def test_an_aoe_ring_class_name_is_folded_and_not_served(self):
        self.assertEqual(self._served("earthquake_aoe", 0.495, 0.72), [])

    def test_a_real_enemy_troop_is_still_served(self):
        # a troop in NEITHER deck (hogeq holds hog_rider), so this file stays byte-identical across the two trees
        self.assertEqual(self._served("giant", 0.50, 0.25), ["giant"])

    def test_a_spawn_spell_is_still_served(self):
        self.assertEqual(self._served("goblin_barrel", 0.30, 0.55), ["goblin_barrel"])

    def test_without_the_filter_an_enemy_spell_on_our_king_WAS_served(self):
        # fireball: a spell in NEITHER deck (hogeq owns earthquake, so its deck veto would not call one "enemy")
        tr = TeamTracker(own_cards=own_card_bases(self.db), min_hits=2, phantom_stale_s=6.0)     # play.py before T1
        tr.tag([_det("fireball", 0.495, 0.72)], 0.0)
        tr.tag([_det("fireball", 0.495, 0.725)], 0.15)
        self.assertEqual([t[4] for t in tr.enemy_tracks(0.2, True)], ["fireball"])
        self.assertEqual(self._served("fireball", 0.495, 0.72), [])                               # and with T1 it is not


if __name__ == "__main__":
    unittest.main()
