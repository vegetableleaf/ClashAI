"""RULING 31c -- the Hero Wizard's tornado spawns at his FIREBALL'S LANDING POINT, radius 3.

Sources: Wizard/Hero revid 437515 ("While he is flying ... his fireballs also create 3 tile
radius tornadoes, which does its own damage (reduced against crown towers), similar to the
Evolved Valkyrie") + the owner report 2026-08-27: the pull radius "seems unusually large --
check it", and "the pull center should be at his projectile's landing position, not starting
position".

RADIUS: the page splits 3 (prose) vs 4 (its ability table's Radius column); I8-8 took the table
under rule (b). The owner's in-game look sides with the prose, and an owner check outranks a
lone table column -- the same table family carries the Evo Valkyrie's stale 5.5 radius against
her own History's 1/12/2025 nerf to 5. Superseded to 3.0; the competing 4 stays recorded in
conflicts.md I8-8.

CENTRE, MEASURED before the fix: with the ability up, the vortex appeared at the SWING, centred
dy=0.00 tiles from the Wizard, while his target stood 5 tiles downrange -- the pull happened
around the thrower. After: no vortex until the fireball lands, then it spawns dy=5.0 (the
landing point). The Evo Valkyrie's whirlwind is a melee spin and KEEPS her own centre; the two
are told apart by the attack's delivery shape (spec.proj_speed > 0 -- the same field that routes
a swing through _launch), never by card name.

SHARED, byte-identical in both decks: every assertion is about the ENGINE and the KB, not a deck.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _p in (str(SRC), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                   # noqa: E402
from clashrl.sim.engine import (SimEngine, Unit, build_spec,       # noqa: E402
                                _TILES_X, _TILES_Y)

from test_sim_status_effects import DummyCfg                       # noqa: E402


def _engine() -> SimEngine:
    return SimEngine(DummyCfg(), CardDB(path=ROOT / "config" / "cards.yaml"), random.Random(0))


class WizardNadoTests(unittest.TestCase):
    def test_the_radius_is_the_proses_three(self):
        spec = build_spec(CardDB(path=ROOT / "config" / "cards.yaml"), "wizard_hero", 11)
        self.assertAlmostEqual(spec.attack_nado_r, 3.0, places=3)

    def test_the_vortex_spawns_at_the_fireballs_landing_point_not_at_the_wizard(self):
        eng = _engine()
        wz = Unit(spec=build_spec(eng.db, "wizard_hero", 11), team=0, x=0.5, y=0.50, hp=832.0)
        kn = Unit(spec=build_spec(eng.db, "knight", 11), team=1,
                  x=0.5, y=0.50 + 5.0 / _TILES_Y, hp=1e6)
        eng.units += [wz, kn]
        wz.ability_active_s = 5.0
        eng._attack(wz, "unit", kn)
        self.assertEqual(len(eng.vortices), 0,
                         "no tornado at the SWING -- it rides the fireball")
        for _ in range(40):
            eng._tick_projectiles(0.1)
        self.assertEqual(len(eng.vortices), 1, "one fireball, one tornado, after the flight")
        v = eng.vortices[0]
        self.assertAlmostEqual((v.y - wz.y) * _TILES_Y, 5.0, delta=0.35,
                               msg="centred on the LANDING point, ~5 tiles downrange")
        self.assertAlmostEqual((v.x - wz.x) * _TILES_X, 0.0, places=1)
        self.assertAlmostEqual(v.spec.pull_radius, 3.0, places=3)
        self.assertAlmostEqual(v.spec.pull_duration, wz.spec.attack_nado_s, places=3)

    def test_without_the_ability_his_fireballs_spin_nothing(self):
        eng = _engine()
        wz = Unit(spec=build_spec(eng.db, "wizard_hero", 11), team=0, x=0.5, y=0.50, hp=832.0)
        kn = Unit(spec=build_spec(eng.db, "knight", 11), team=1,
                  x=0.5, y=0.50 + 5.0 / _TILES_Y, hp=1e6)
        eng.units += [wz, kn]
        eng._attack(wz, "unit", kn)
        for _ in range(40):
            eng._tick_projectiles(0.1)
        self.assertEqual(len(eng.vortices), 0)

    def test_the_evo_valkyries_whirlwind_still_centres_on_her(self):
        """REGRESSION GUARD: her Tornado 'pull[s] all units towards HER' (Valkyrie/Evolution
        revid 437367) -- a melee spin (proj_speed 0), so the landing-point rule must not move
        it. Spawns at the swing, on her own coordinates, radius 5.5 untouched."""
        eng = _engine()
        vk = Unit(spec=build_spec(eng.db, "valkyrie_evo", 11), team=0, x=0.5, y=0.50, hp=1908.0)
        kn = Unit(spec=build_spec(eng.db, "knight", 11), team=1,
                  x=0.5, y=0.50 + 1.0 / _TILES_Y, hp=1e6)
        eng.units += [vk, kn]
        self.assertEqual(vk.spec.proj_speed, 0.0, "the distinguishing shape: her spin is melee")
        self.assertGreater(build_spec(eng.db, "wizard_hero", 11).proj_speed, 0.0,
                           "...and his fireball flies")
        eng._attack(vk, "unit", kn)
        self.assertEqual(len(eng.vortices), 1, "her vortex appears AT the swing")
        v = eng.vortices[0]
        self.assertAlmostEqual((v.x - vk.x) * _TILES_X, 0.0, places=3)
        self.assertAlmostEqual((v.y - vk.y) * _TILES_Y, 0.0, places=3,
                               msg="centred on HER, not on her target")
        self.assertAlmostEqual(v.spec.pull_radius, 5.5, places=3)


if __name__ == "__main__":
    unittest.main()
