"""The rollout opponent for LIVE search: does it actually hold what we think they hold?"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                      # noqa: E402
from clashrl.config import Config                                     # noqa: E402
from clashrl.sim.live_opponent import LiveOpponent, infer_style, pad_deck   # noqa: E402
from clashrl.sim.opponent_cycle import OpponentCycle                   # noqa: E402

_DB = CardDB(path=ROOT / "config" / "cards.yaml")
_CFG = Config.load(ROOT / "config" / "config.yaml")
DECK = ["knight", "archers", "musketeer", "fireball", "zap", "hog_rider", "skeletons", "cannon"]


class LiveOpponentTests(unittest.TestCase):

    def test_the_bots_hand_becomes_the_hand_we_believe_they_hold(self):
        """THE POINT. Without this the rollout opponent plays a random cycle and search is
        defending against cards they cannot actually have."""
        op = LiveOpponent(_CFG, _DB, random.Random(0), DECK)
        want = ["hog_rider", "zap", "cannon", "musketeer"]
        placed = op.sync_hand(want)
        self.assertEqual(placed, 4)
        self.assertEqual(sorted(op.hand_keys), sorted(want))

    def test_it_syncs_from_an_OpponentCycle_end_to_end(self):
        oc = OpponentCycle(DECK)
        for c in ("knight", "archers", "fireball", "skeletons"):
            oc.record_play(c)
        op = LiveOpponent(_CFG, _DB, random.Random(0), DECK)
        op.sync(oc)
        self.assertEqual(sorted(op.hand_keys), sorted(oc.hand()))

    def test_it_reports_how_much_of_the_hand_it_could_place(self):
        """A caller that asked for 4 and got 2 is looking at a deck estimate that disagrees with
        the bot's, and must treat the rollout opponent as a guess."""
        op = LiveOpponent(_CFG, _DB, random.Random(0), DECK)
        self.assertEqual(op.sync_hand(["hog_rider", "not_in_this_deck", "zap"]), 2)
        self.assertEqual(op.sync_hand([]), 0)

    def test_a_partial_deck_is_padded_to_eight(self):
        """ScriptedBot needs eight cards to cycle. A two-card observation must not crash it."""
        op = LiveOpponent(_CFG, _DB, random.Random(0), ["hog_rider", "zap"])
        self.assertEqual(len(op.deck), 8)
        self.assertIn("hog_rider", op.deck)
        self.assertIn("zap", op.deck)

    def test_padding_only_uses_real_cards(self):
        deck = pad_deck(_DB, ["hog_rider"])
        for c in deck:
            self.assertIn(c, _DB.cards, f"padded with {c}, which is not a real card")

    def test_style_is_inferred_and_falls_back_to_control(self):
        self.assertEqual(infer_style(["golem", "baby_dragon"]), "beatdown")
        self.assertEqual(infer_style(["x_bow", "tesla"]), "siege")
        self.assertEqual(infer_style(["wizard", "valkyrie"]), "control")

    def test_it_actually_plays_in_an_engine(self):
        """The wrapper must still be a working opponent, not just a hand-holder."""
        from clashrl.sim.engine import SimEngine
        from test_sim_status_effects import DummyCfg
        eng = SimEngine(DummyCfg(), _DB, random.Random(0))
        eng.reset()
        eng.elixir[1] = 10.0
        op = LiveOpponent(_CFG, _DB, random.Random(1), DECK)
        op.sync_hand(["hog_rider", "knight", "archers", "zap"])
        before = len(eng.units)
        for _ in range(40):
            op.act(eng)
            eng.advance(0.1)
            if len(eng.units) > before:
                break
        self.assertGreater(len(eng.units), before, "the rollout opponent never played anything")


if __name__ == "__main__":
    unittest.main()
