"""L67aa N1 (HANDOFF 5cs.99 AF): the live Tornado assist never aims at a building.

run14's first T2 trigger log: 2 of 8 Tornado assist moves aimed at buildings a Tornado cannot pull -- an enemy elixir
collector (the nearest-enemy fallback) and an "enemy x_bow" on our half (the king-activation trigger), very likely our
own X-Bow tagged enemy. `reward.tornado_pullable` drops building tracks before the assist looks at them.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import card_threat                                           # noqa: E402
from clashrl.cards import CardDB                                          # noqa: E402
from clashrl.config import Config                                         # noqa: E402
from clashrl.reward import nado_king_cell, tornado_pullable               # noqa: E402

PLAY = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "play.py")
MY_ANCHORS = [[0.245, 0.615], [0.745, 0.615], [0.495, 0.72]]             # icebow env.my_towers (L, R, king)


class _Acts:
    def cell_at(self, x, y):
        return (round(x, 3), round(y, 3))


class TornadoPullable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db = CardDB(Config.load())
        cls.kind = staticmethod(lambda b: db.kind(card_threat.base_key(str(b))))

    def test_buildings_are_dropped_units_are_kept(self):
        tracks = [(0.57, 0.58, 0, 0, "x_bow"), (0.14, 0.15, 0, 0, "elixir_collector"), (0.50, 0.60, 0, 0, "tesla_evo"),
                  (0.45, 0.50, 0, 0, "knight"), (0.61, 0.65, 0, 0, "prince"), (0.56, 0.19, 0, 0, "electro_dragon")]
        kept = [t[4] for t in tornado_pullable(tracks, self.kind)]
        self.assertEqual(kept, ["knight", "prince", "electro_dragon"])

    def test_tracks_without_a_base_or_an_unknown_kind_are_kept(self):
        tracks = [(0.5, 0.5, 0, 0), (0.3, 0.3, 0, 0, None), (0.2, 0.2, 0, 0, "not_a_card")]
        self.assertEqual(len(tornado_pullable(tracks, self.kind)), 3)

    def test_the_run14_case_a_building_alone_no_longer_fires_the_king_pull(self):
        xbow = [(0.57, 0.58, 0.0, 0.0, "x_bow")]                              # the 09:43:28 trigger
        self.assertIsNotNone(nado_king_cell(xbow, MY_ANCHORS, _Acts()), "precondition: unfiltered it fires")
        self.assertIsNone(nado_king_cell(tornado_pullable(xbow, self.kind), MY_ANCHORS, _Acts()))

    def test_a_real_deep_attacker_still_fires_it(self):
        prince = [(0.61, 0.65, 0.0, 0.0, "prince"), (0.57, 0.58, 0.0, 0.0, "x_bow")]
        self.assertIsNotNone(nado_king_cell(tornado_pullable(prince, self.kind), MY_ANCHORS, _Acts()))


class PlayWiring(unittest.TestCase):
    def test_play_filters_the_tornado_tracks_before_the_assist(self):
        with open(PLAY, encoding="utf-8") as fh:
            src = fh.read()
        if "nado_king_cell(_tk" not in src:
            self.skipTest("this deck's play.py has no Tornado assist")
        self.assertIn("tornado_pullable(_tk", src)
        self.assertLess(src.index("tornado_pullable(_tk"), src.index("nado_king_cell(_tk"))


if __name__ == "__main__":
    unittest.main()
