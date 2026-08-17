import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from clashrl.cards import CardDB
from clashrl.sim.engine import SimEngine, build_spec
from clashrl.sim.engine import Unit


class DummyCfg:
    def __init__(self):
        self._data = {
            "sim": {
                "my_tower_level": 15,
                "my_tower_troop": "princess",
                "tower_first_hit": 0.8,
                "tower_troops": None,
                "king_tower": None,
                "opponent_tower_weights": None,
                "tower_range": 7.5,
                "king_range": 7.0,
                "regulation_s": 180.0,
                "overtime_s": 60.0,
                "siege_sight": 11.5,
                "sight_tiles": 5.5,
                "tower_projectile_tiles_s": 10.0,
                "slow_factor": 0.5,
                "slow_duration": 2.0,
                "stun_duration": 0.5,
                "freeze_duration": 1.0,
                "collision": True,
                "board": {
                    "tiles_x": 18.0,
                    "tiles_y": 32.0,
                    "bridge_tiles": [3.5, 14.5],
                    "bridge_width_tiles": 3.0,
                    "river_width_tiles": 2.0,
                    "princess_tile": [3.5, 6.5],
                    "king_tile": [9.0, 3.0],
                },
            }
        }

    def get(self, section, key, default=None):
        return self._data.get(section, {}).get(key, default)


def _make_engine():
    cfg = DummyCfg()
    db = CardDB(path=ROOT / "config" / "cards.yaml")
    return SimEngine(cfg, db, random.Random(0))


class SimStatusEffectsTests(unittest.TestCase):
    def test_tower_keeps_its_lock_until_reset(self):
        eng = _make_engine()
        tower = eng.towers[0][0]
        far = Unit(spec=build_spec(eng.db, "knight"), team=1, x=tower.x, y=tower.y - 0.15, hp=100.0)
        near = Unit(spec=build_spec(eng.db, "skeletons"), team=1, x=tower.x, y=tower.y - 0.05, hp=100.0)
        eng.units.extend([far, near])

        eng._tower_fire(0, tower, tower.first_hit + 0.01)
        self.assertIs(tower.target, near, "the tower should lock the nearest target when it first acquires")

        nearer = Unit(spec=build_spec(eng.db, "skeletons"), team=1, x=tower.x, y=tower.y - 0.02, hp=100.0)
        eng.units.append(nearer)
        tower.reload_left = 0.0
        eng._tower_fire(0, tower, tower.hit_speed + 0.01)
        self.assertIs(tower.target, near,
                      "a closer enemy must not steal crown-tower aggro until the current lock is reset")

        eng._apply_status(1, build_spec(eng.db, "zap"), tower)
        tower.stun_left = 0.0
        tower.reload_left = 0.0
        eng._tower_fire(0, tower, tower.first_hit + 0.01)
        self.assertIs(tower.target, nearer,
                      "after a stun/freeze reset the tower should recalculate and pick the new nearest foe")

    def test_status_effects_apply_to_crown_towers(self):
        eng = _make_engine()
        tower = eng.towers[0][2]

        eng._apply_status(0, build_spec(eng.db, "zap"), tower)
        self.assertGreater(tower.stun_left, 0.0)

        eng._apply_status(0, build_spec(eng.db, "ice_wizard"), tower)
        self.assertGreater(tower.slow_left, 0.0)
        self.assertLess(tower.slow_mult, 1.0)

        eng._apply_status(0, build_spec(eng.db, "freeze"), tower)
        self.assertGreater(tower.stun_left, 0.0)

    def test_ice_wizard_splash_slows_nearby_towers(self):
        eng = _make_engine()
        ice_wizard = build_spec(eng.db, "ice_wizard")
        tower = eng.towers[1][2]
        target = Unit(
            spec=build_spec(eng.db, "skeletons"),
            team=1,
            x=tower.x,
            y=tower.y,
            hp=100.0,
        )
        eng.units.append(target)

        eng._land_hit(0, "unit", target, ice_wizard, 20.0, 20.0)

        self.assertGreater(tower.slow_left, 0.0)
        self.assertLess(tower.slow_mult, 1.0)

    def test_fisherman_slow_only_applies_on_first_hit(self):
        eng = _make_engine()
        target = type("DummyUnit", (), {})()
        target.spec = build_spec(eng.db, "minions")
        target.team = 0
        target.hidden = False
        target.invis_left = 0.0
        target.slow_left = 0.0
        target.slow_mult = 1.0
        target.fisherman_slowed = False

        eng._apply_status(0, build_spec(eng.db, "fisherman"), target)
        self.assertGreater(target.slow_left, 0.0)

        target.slow_left = 0.2
        eng._apply_status(0, build_spec(eng.db, "fisherman"), target)
        self.assertEqual(target.slow_left, 0.2)
        self.assertTrue(getattr(target, "fisherman_slowed", False))


if __name__ == "__main__":
    unittest.main()
