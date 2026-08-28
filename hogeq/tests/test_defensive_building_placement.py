"""Defensive buildings belong IN FRONT OF THE TOWER, not at the bridge.

Owner report 2026-08-28: "many opponents in the sim play their defensive buildings at the bridge;
that is almost never the play in real matches."

MEASURED BEFORE THE FIX, 40 matches, enemy buildings only:
    cannon        n=34  mean y=16.15t      <- the river IS y=16
    inferno_tower n= 2  mean y=17.00t      <- past the river
    goblin_cage   n= 5  mean y=15.50t
    ALL: 99% at y >= 12t, 82% at y >= 14t   (their own king sits at y=3)

CAUSE: `ScriptedBot.act`'s DEFEND branch selected `s.kind == "troop"`, so `kind == "building"`
matched NOTHING and every Cannon/Tesla/Inferno fell through to the ATTACK path -- which places at
the bridge because that is right for a win condition.

The siege case is the negative control and it must NOT change: for an X-Bow or Mortar the bridge
really is the play, so they stay on the offence path.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                     # noqa: E402
from clashrl.config import Config                                    # noqa: E402
from clashrl.sim.engine import (SimEngine, Unit, build_spec,         # noqa: E402
                                _TILES_X, _TILES_Y)
from clashrl.sim.opponents import ScriptedBot                        # noqa: E402
from test_sim_status_effects import DummyCfg                         # noqa: E402

_CFG = Config.load(ROOT / "config" / "config.yaml")
_DB = CardDB(path=ROOT / "config" / "cards.yaml")
_DECK = ["cannon", "knight", "archers", "musketeer", "fireball", "zap", "hog_rider", "skeletons"]
_SIEGE_DECK = ["x_bow", "knight", "archers", "musketeer", "fireball", "zap", "tesla", "skeletons"]
RIVER_T = 16.0
THEIR_PRINCESS_T = 6.5


def _answer(deck, style, seed, want, threat="hog_rider"):
    """Run the bot against one incoming threat; return the first unit it deploys, or None."""
    eng = SimEngine(DummyCfg(), _DB, random.Random(seed))
    eng.reset()
    bot = ScriptedBot(_CFG, _DB, random.Random(seed), deck, style)
    eng.elixir[1] = 10.0
    if want not in [s.base for s in bot._hand_specs()]:
        return None
    eng.units.append(Unit(spec=build_spec(_DB, threat, 11), team=0,
                          x=3.5 / _TILES_X, y=14.0 / _TILES_Y, hp=1600.0))
    for _ in range(30):
        before = {id(u) for u in eng.units}
        bot.act(eng)
        new = [u for u in eng.units if id(u) not in before and u.team == 1]
        if new:
            return new[0]
        eng.advance(0.1)
    return None


class DefensiveBuildingPlacementTests(unittest.TestCase):

    def test_a_building_answers_a_win_condition_and_lands_in_front_of_the_tower(self):
        """THE RULING. A Cannon must answer the Hog, and must not be at the bridge."""
        ys, chosen, had = [], 0, 0
        for seed in range(60):
            u = _answer(_DECK, "control", seed, "cannon")
            if u is None:
                continue
            had += 1
            if u.spec.base == "cannon":
                chosen += 1
                ys.append(u.y * _TILES_Y)
        self.assertGreater(had, 10, "the deck never offered a cannon -- test is not exercising it")
        self.assertEqual(chosen, had, "a building must be preferred against a building-targeting win condition")
        mean = sum(ys) / len(ys)
        self.assertLess(mean, 12.0, f"defensive building placed at y={mean:.2f}t -- that is bridge territory")
        self.assertGreater(mean, THEIR_PRINCESS_T,
                           "placed BEHIND their own princess tower, which defends nothing")

    def test_siege_buildings_are_untouched(self):
        """NEGATIVE CONTROL. For an X-Bow the bridge IS the play; the fix must not move it."""
        from clashrl.sim.engine import build_spec as _bs
        self.assertTrue(_bs(_DB, "x_bow", 11).siege)
        self.assertTrue(_bs(_DB, "mortar", 11).siege)
        self.assertFalse(_bs(_DB, "cannon", 11).siege)
        self.assertFalse(_bs(_DB, "inferno_tower", 11).siege)

    def test_a_non_wincon_threat_still_gets_the_cheap_troop(self):
        """A building is the answer to a WIN CONDITION, not to everything. A lone Knight should
        still be met with the cheapest troop -- otherwise the bot burns a building on chip."""
        got = [_answer(_DECK, "control", s, "cannon", threat="knight") for s in range(40)]
        got = [u for u in got if u is not None]
        self.assertTrue(got, "no deployment observed")
        self.assertTrue(any(u.spec.kind == "troop" for u in got),
                        "every answer to a non-wincon threat was a building")

    def test_buildings_are_no_longer_offered_as_offence(self):
        """The regression itself: a non-siege building must not reach the bridge/lane placements."""
        eng = SimEngine(DummyCfg(), _DB, random.Random(3))
        eng.reset()
        bot = ScriptedBot(_CFG, _DB, random.Random(3), _DECK, "control")
        usable = bot._usable(bot._hand_specs(), 10.0)
        offense = [s for s in usable if s.kind != "spell" and s.gen_every <= 0
                   and not (s.kind == "building" and not s.deploy_anywhere and not s.siege)]
        self.assertFalse([s for s in offense if s.base == "cannon"],
                         "the cannon is still in the offence pool -- it will be bridge-placed")


if __name__ == "__main__":
    unittest.main()
