"""OPPONENT CADENCE knob `sim.bot_attack_floor` (HANDOFF §5cc, GAUNTLET L29).

MEASURED (§5bw.4 / §5cc): the non-beatdown ScriptedBot attacks on the FIRST step it can afford any
offensive card, so it pressures ~56% of single-elixir steps with a 4.8 s quiet median and gives the
agent ~0.6 bank-to-six windows per phase; pros: 37%, 9.0 s, ~2.7. The floor makes a cycle/control/
siege bot bank to N elixir before it ATTACKS. Defence is untouched, beatdown (which already holds to
9.5) is untouched, and the floor is TRAINING-ONLY: make_opponent(adaptive=False) -- the eval
benchmark's path -- always builds the historical bot, so eval curves stay comparable.
"""
from __future__ import annotations

import copy
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
from clashrl.sim.engine import SimEngine, Unit, build_spec, _TILES_X, _TILES_Y   # noqa: E402
from clashrl.sim.opponents import ScriptedBot, make_opponent         # noqa: E402
from test_sim_status_effects import DummyCfg                         # noqa: E402

_CFG = Config.load(ROOT / "config" / "config.yaml")
_DB = CardDB(path=ROOT / "config" / "cards.yaml")
_DECK = ["cannon", "knight", "archers", "musketeer", "fireball", "zap", "hog_rider", "skeletons"]


def _cfg(floor):
    data = copy.deepcopy(_CFG.data); data.setdefault("sim", {})["bot_attack_floor"] = floor
    return Config(data=data, root=_CFG.root)


def _deploys(style, elixir, floor, threat=False, steps=5, seed=3):
    eng = SimEngine(DummyCfg(), _DB, random.Random(seed)); eng.reset()
    bot = ScriptedBot(_CFG, _DB, random.Random(seed), _DECK, style, attack_floor=floor)
    bot.anywhere_prob = 0.0
    if threat:
        eng.units.append(Unit(spec=build_spec(_DB, "hog_rider", 11), team=0,
                              x=3.5 / _TILES_X, y=14.0 / _TILES_Y, hp=1600.0))
    n = 0
    for _ in range(steps):
        eng.elixir[1] = float(elixir)
        before = len(eng.units); bot.act(eng); n += len(eng.units) - before
    return n


class AttackFloorTests(unittest.TestCase):

    def test_default_floor_is_the_historical_bot(self):
        self.assertEqual(ScriptedBot(_CFG, _DB, random.Random(0), _DECK, "cycle").attack_floor, 0.0)
        self.assertEqual(float(_CFG.get("sim", "bot_attack_floor", default=-1.0)), 0.0,
                         "config ships the knob OFF (0 = attack on the first affordable step)")
        self.assertGreater(_deploys("cycle", 4.0, 0.0), 0, "floor 0: a 4-elixir bot attacks at once")

    def test_a_cycle_bot_banks_to_the_floor_before_attacking(self):
        self.assertEqual(_deploys("cycle", 6.9, 7.0), 0, "under the floor: banks")
        self.assertGreater(_deploys("cycle", 7.0, 7.0), 0, "at the floor: attacks")
        self.assertEqual(_deploys("control", 5.0, 7.0), 0)
        self.assertGreater(_deploys("control", 9.0, 7.0), 0)

    def test_defence_ignores_the_floor(self):
        self.assertGreater(_deploys("cycle", 4.0, 7.0, threat=True), 0,
                           "a Hog on our side is answered at 4 elixir even with a 7 floor")

    def test_beatdown_keeps_its_own_9p5_rule(self):
        self.assertEqual(_deploys("beatdown", 9.0, 0.0), 0)
        self.assertEqual(_deploys("beatdown", 9.0, 7.0), 0)
        self.assertGreater(_deploys("beatdown", 10.0, 7.0), 0)

    def test_floor_is_training_only(self):
        cfg = _cfg(7.0)
        for _ in range(6):
            eval_bot = make_opponent(cfg, _DB, random.Random(1), [], adaptive=False)
            self.assertEqual(eval_bot.attack_floor, 0.0, "eval path (adaptive=False): historical cadence")
            train_bot = make_opponent(cfg, _DB, random.Random(1), [], adaptive=True)
            self.assertEqual(train_bot.attack_floor, 7.0, "training path reads sim.bot_attack_floor")


if __name__ == "__main__":
    unittest.main()
