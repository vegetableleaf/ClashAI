"""Regression: units that SPLIT ON DEATH must actually spawn their children in the sim.

Before this, golem/lava_hound/elixir_golem had no `spawns.on_death`, so a killed Golem simply
VANISHED -- the defender got the whole 8-elixir tank for free and never faced the second wave.
The children also had no combat stats (they are not cards, so the stats import skips them), which
would have made a "wired" split spawn 0-HP units that evaporate on arrival -- so the tests assert
the children are ALIVE and can fight, not merely that they exist.
"""
from __future__ import annotations

import random
import unittest

from clashrl.cards import CardDB
from clashrl.config import Config
from clashrl.sim.engine import SimEngine, build_spec


def _cfg():
    return Config.load()


class TestDeathSplits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = _cfg()
        cls.db = CardDB(cls.cfg)

    def _kill_and_collect(self, key: str, level: int = 11):
        """Deploy `key`, kill it outright, advance one tick, return the surviving unit specs."""
        eng = SimEngine(self.cfg, self.db, random.Random(7))
        eng.reset()
        spec = build_spec(self.db, key, level)
        eng.elixir[0] = 10.0
        self.assertTrue(eng.deploy(0, spec, 0.25, 0.75), f"{key} failed to deploy")
        parent = [u for u in eng.units if u.team == 0][-1]
        parent.hp = 0.0                      # killed outright -> the death path runs on the next tick
        eng.advance(0.1)
        return [u for u in eng.units if u.team == 0]

    def test_golem_splits_into_two_living_golemites(self):
        kids = self._kill_and_collect("golem")
        self.assertEqual(len(kids), 2, "Golem must split into exactly 2 Golemites")
        for k in kids:
            self.assertEqual(k.spec.base, "golemite")
            self.assertGreater(k.hp, 0.0, "a 0-HP Golemite would evaporate -- stats are missing")
            self.assertGreater(k.spec.dps, 0.0, "Golemites must be able to fight")

    def test_golem_death_blast_has_damage(self):
        """The Golem 'explodes, dealing damage' -- the import left death_damage null, so it was inert."""
        spec = build_spec(self.db, "golem", 11)
        self.assertGreater(spec.death_dmg, 0.0)
        self.assertGreater(spec.death_radius, 0.0)

    def test_lava_hound_splits_into_six_living_pups(self):
        kids = self._kill_and_collect("lava_hound")
        self.assertEqual(len(kids), 6, "Lava Hound must burst into exactly 6 Lava Pups")
        for k in kids:
            self.assertEqual(k.spec.base, "lava_pups")
            self.assertGreater(k.hp, 0.0)
            self.assertTrue(k.spec.flying, "Lava Pups are AIR units")

    def test_lava_hound_has_no_death_damage(self):
        """Fandom: 'the Lava Hound in Clash Royale does not have death damage'."""
        self.assertEqual(build_spec(self.db, "lava_hound", 11).death_dmg, 0.0)

    def test_elixir_golem_chain_splits_twice(self):
        """Elixir Golem -> 2 Golemites, and EACH Golemite -> 2 Blobs (the chain must terminate)."""
        kids = self._kill_and_collect("elixir_golem")
        self.assertEqual(len(kids), 2)
        self.assertEqual({k.spec.base for k in kids}, {"elixir_golemite"})
        for k in kids:
            self.assertGreater(k.hp, 0.0)
        # second split
        blob_spec = build_spec(self.db, "elixir_golemite", 11)
        self.assertEqual(blob_spec.spawner_death, 2)
        self.assertIsNotNone(blob_spec.spawner_spec)
        self.assertEqual(blob_spec.spawner_spec.base, "elixir_blob")
        # ...and the blob terminates it, or the recursion would never end
        self.assertEqual(build_spec(self.db, "elixir_blob", 11).spawner_death, 0)

    def test_splits_are_death_only_not_periodic(self):
        """`on_death` without an `interval` must NOT turn these tanks into spawner buildings."""
        for key in ("golem", "lava_hound", "elixir_golem"):
            self.assertEqual(build_spec(self.db, key, 11).spawner_interval, 0.0, key)

    # --- the Elixir Golem's defining drawback -------------------------------------------------
    def test_elixir_golem_line_refunds_elixir_to_the_opponent(self):
        """Golem 1 + Golemite 0.5 + Blob 0.5 -- without this the sim sees only the upside."""
        self.assertEqual(build_spec(self.db, "elixir_golem", 11).elixir_death, 1.0)
        self.assertEqual(build_spec(self.db, "elixir_golemite", 11).elixir_death, 0.5)
        self.assertEqual(build_spec(self.db, "elixir_blob", 11).elixir_death, 0.5)

    def test_refund_is_paid_to_the_OTHER_team_on_death(self):
        """Measured against a CONTROL death, so passive elixir regen cannot fake the result."""
        def defender_gain(card: str) -> float:
            eng = SimEngine(self.cfg, self.db, random.Random(3))
            eng.reset()
            eng.elixir[0] = 10.0
            self.assertTrue(eng.deploy(0, build_spec(self.db, card, 11), 0.25, 0.75))
            eng.elixir[1] = 2.0                       # the DEFENDER's bar, before the kill
            [u for u in eng.units if u.team == 0][-1].hp = 0.0
            eng.advance(0.1)
            return eng.elixir[1] - 2.0

        refund = defender_gain("elixir_golem") - defender_gain("knight")
        self.assertAlmostEqual(refund, 1.0, places=3,
                               msg="killing the Elixir Golem must hand the defender 1 elixir")

    def test_ordinary_cards_refund_nothing(self):
        """The refund must stay unique to this line -- a Knight dying may not feed the opponent."""
        for key in ("knight", "golem", "lava_hound"):
            self.assertEqual(build_spec(self.db, key, 11).elixir_death, 0.0, key)


if __name__ == "__main__":
    unittest.main()
