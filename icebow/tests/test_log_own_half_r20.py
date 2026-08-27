"""RULING 20 -- The Log's CAST POINT is own-half; its CORRIDOR still crosses the river.

Owner (2026-08-27): "The Log's cast point is restricted to the caster's own half (plus pockets),
but its corridor still rolls across the river."

This file is BYTE-IDENTICAL in icebow and hogeq (parity_check enforces it), and it matters in both:
**both shipped decks play The Log**, so unlike ruling 18 -- whose card neither deck holds -- this
one really does change the agent's own action space.

THE EVIDENCE. Cards revid 437053 names three exceptions to "spells can be cast anywhere", and only
three: "WITH THE EXCEPTION OF The Log, Barbarian Barrel, and Royal Delivery". Ruling 18 shipped
Royal Delivery and recorded the other two in conflicts.md as a separate measured commit; this is
that commit. Two independent card-page confirmations for the barrel, both archived under
`research/sim_parity/webcache/`:

    Barbarian_Barrel.wikitext      "It can only be deployed on the player's own side."
    Barbarian_Barrel_Hero.live.wikitext (revid 437523, the HERO form) says it verbatim too.

THE HALF THAT IS A TRAP, and the reason `NothingElseWasClampedTests` exists. An earlier bug
(§5 of HANDOFF) had `anywhere_ids` set to the literal {rocket, miner}, so EVERY other spell was
forbidden from the enemy half -- the offensive Log, the river Tornado lock and hogeq's whole
Hog+Earthquake combo were actions the policy could not take at all. Ruling 20 adds exactly two
cards by KB FLAG and must not narrow the spell rule by one inch.

MEASURED, in the SIM'S BOARD SPACE (18x24 action grid, river at ny 0.5, deploy line gy=13):

    card              cast aimed at gy=0   ->  clamped   cast ny   corridor reaches   past river
    the_log                    gy=0            gy=13      0.5625        0.2625         7.60 tiles
    barbarian_barrel           gy=0            gy=13      0.5625        0.4219         2.50 tiles
    rocket / tornado           gy=0            gy=0       0.1000        (not a roll)   unclamped

⚠ MEASUREMENT TRAP, and it cost a pass here. `ActionSpace(cfg)` is the LIVE action space: its
`arena_box` is the screen rectangle and `cell_center` runs the perspective warp, so gy=13 comes
back as ny=0.4788 -- already "past" a river the sim puts at 0.5, which reads as the clamp having
failed. The SIM re-anchors the same grid through `sim.env._board_action_space`, where the warp is
the identity and gy=13 is a board-true 0.5625. Anything asserting a board coordinate must build
the board space, never the live one.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                        # noqa: E402
from clashrl.config import Config                                       # noqa: E402
from clashrl.sim.env import _board_action_space                         # noqa: E402
from clashrl.sim.engine import (Unit, _Spell, build_spec, _RIVER,       # noqa: E402
                                _TILES_X, _TILES_Y)
from test_sim_status_effects import _make_engine                        # noqa: E402

LVL = 11
CLAMPED = ("the_log", "barbarian_barrel")
UNCLAMPED = ("rocket", "tornado", "earthquake", "fireball", "arrows", "zap", "goblin_barrel")


def _board():
    cfg = Config.load(str(ROOT / "config" / "config.yaml"))
    return cfg, CardDB(cfg), _board_action_space(cfg)


class TheCastPointIsOwnHalfTests(unittest.TestCase):
    """Half one of the ruling: WHERE the card may be put."""

    def setUp(self):
        self.cfg, self.db, self.A = _board()
        self.gw, self.gh = int(self.A.gw), int(self.A.gh)

    def test_the_log_and_the_barrel_clamp_to_the_deploy_line(self):
        gx = self.gw // 2
        for key in CLAMPED:
            with self.subTest(card=key):
                for gy in range(0, self.A.min_own_gy):        # every row in the ENEMY half
                    out = self.A.deploy_clamp(False, gy * self.gw + gx)
                    self.assertGreaterEqual(out // self.gw, self.A.min_own_gy,
                                            "row %d stayed in the enemy half" % gy)
                    self.assertEqual(gx, out % self.gw, "the clamp must not move the LANE")

    def test_the_deepest_aim_lands_exactly_on_the_deploy_line(self):
        gx = self.gw // 2
        out = self.A.deploy_clamp(False, 0 * self.gw + gx)
        _nx, ny = self.A.cell_center(out % self.gw, out // self.gw)
        print("\n[R20] aimed at the enemy BACK row (gy=0) -> gy=%d, cast ny=%.4f "
              "(river %.2f, deploy line gy=%d of %d)"
              % (out // self.gw, ny, _RIVER, self.A.min_own_gy, self.gh))
        self.assertEqual(self.A.min_own_gy, out // self.gw)
        self.assertGreater(ny, _RIVER, "the CAST POINT is on our own side of the river")

    def test_a_pocket_placement_is_still_legal(self):
        """Ruling 20 says "own half PLUS POCKETS". Taking an enemy princess grants territory across
        the river; a clamped card must still reach it, or the ruling would have deleted the pocket
        for The Log -- the one card most often played into exactly that gap."""
        if "pocket" not in type(self.A).deployable_mask.__code__.co_varnames:
            self.skipTest("this deck's Actions has no pocket parameter (deck-specific)")
        closed = self.A.deployable_mask(False)
        left = self.A.deployable_mask(False, pocket=(True, False))
        self.assertGreater(sum(left), sum(closed), "an open pocket must add legal cells")
        added = [c for c in range(self.gw * self.gh) if left[c] and not closed[c]]
        self.assertTrue(added)
        for c in added:
            self.assertLess(c // self.gw, self.A.min_own_gy, "a pocket cell is across the river")


class TheCorridorStillCrossesTheRiverTests(unittest.TestCase):
    """Half two, and the half that makes the ruling non-trivial: clamping the CAST must not delete
    the OFFENSIVE Log. Asserting the cast point alone would pass with a corridor of length zero --
    so every assertion here is about the REACH."""

    def setUp(self):
        self.cfg, self.db, self.A = _board()
        self.gw = int(self.A.gw)

    def _reach(self, key):
        """ny the corridor's leading edge attains from the DEEPEST legal cast (team 0 rolls toward
        ny=0), and the cast ny it started from."""
        sp = build_spec(self.db, key, LVL)
        out = self.A.deploy_clamp(False, 0 * self.gw + self.gw // 2)
        _nx, ny = self.A.cell_center(out % self.gw, out // self.gw)
        return ny, ny - sp.roll_len / _TILES_Y

    def test_the_logs_corridor_reaches_7_6_tiles_past_the_river(self):
        ny, reach = self._reach("the_log")
        past = (_RIVER - reach) * _TILES_Y
        print("\n[R20] the_log: cast ny=%.4f -> corridor reaches ny=%.4f = %.2f tiles PAST the "
              "river. The offensive Log survives the clamp." % (ny, reach, past))
        self.assertLess(reach, _RIVER, "the corridor MUST still cross the river")
        self.assertAlmostEqual(0.5625, ny, places=4)
        self.assertAlmostEqual(0.2625, reach, places=4)
        self.assertAlmostEqual(7.60, past, places=2)

    def test_the_barrels_corridor_reaches_2_5_tiles_past_the_river(self):
        """The wiki predicts this number independently: "If the Barbarian Barrel is placed at most
        2 tiles from the river, the Barbarian will spawn at the opposing side of the Arena"."""
        ny, reach = self._reach("barbarian_barrel")
        past = (_RIVER - reach) * _TILES_Y
        print("[R20] barbarian_barrel: cast ny=%.4f -> reaches ny=%.4f = %.2f tiles PAST the river."
              % (ny, reach, past))
        self.assertLess(reach, _RIVER, "the barrel's corridor crosses too (4.5 > 2.0 tiles)")
        self.assertAlmostEqual(0.4219, reach, places=4)
        self.assertAlmostEqual(2.50, past, places=2)

    def test_a_log_cast_at_the_deploy_line_really_DAMAGES_a_body_across_the_river(self):
        """The geometry above, executed. A clamp that were enforced inside the engine rather than
        in the action space would pass both tests above and fail this one."""
        eng = _make_engine()
        sp = build_spec(eng.db, "the_log", LVL)
        out = self.A.deploy_clamp(False, 0 * self.gw + self.gw // 2)
        nx, ny = self.A.cell_center(out % self.gw, out // self.gw)
        # a knight 4 tiles PAST the river, dead ahead of the corridor
        vy = _RIVER - 4.0 / _TILES_Y
        vic = Unit(build_spec(eng.db, "knight", LVL), 1, nx, vy, 3000.0)
        vic.deploy_left = 0.0
        eng.units.append(vic)
        hp0 = vic.hp
        eng._resolve_spell(_Spell(0, nx, ny, sp, 0.0))
        for _ in range(200):                                  # let a SWEPT roll (ruling 21) arrive
            eng.advance(0.05)
            if vic.hp < hp0:
                break
        print("[R20] a Log cast at the deploy line (ny=%.4f) hit a body at ny=%.4f "
              "(%.1f tiles past the river): %.0f -> %.0f hp"
              % (ny, vy, (_RIVER - vy) * _TILES_Y, hp0, vic.hp))
        self.assertLess(vic.hp, hp0, "the clamped cast must still reach across the river")


class NothingElseWasClampedTests(unittest.TestCase):
    """THE REGRESSION GUARD for §5's "every spell was forbidden from the enemy half" bug. Ruling 20
    adds TWO cards by flag. Any spell that silently joins them here is that bug returning."""

    def setUp(self):
        self.cfg, self.db, self.A = _board()
        self.gw = int(self.A.gw)

    def test_rocket_and_tornado_and_the_rest_still_aim_anywhere(self):
        for key in UNCLAMPED:
            with self.subTest(card=key):
                self.assertFalse(build_spec(self.db, key, LVL).own_half_only,
                                 "%s must keep the whole board" % key)

    def test_an_unflagged_spell_passes_the_clamp_untouched(self):
        """`deploy_clamp(anywhere=True, ...)` is the exemption the flag removes; this pins that the
        exemption itself still works, so the flag is doing the narrowing and not the rule."""
        for gy in range(0, self.A.min_own_gy):
            cell = gy * self.gw + self.gw // 2
            self.assertEqual(cell, self.A.deploy_clamp(True, cell))

    def test_the_flagged_set_is_exactly_two_spells_plus_royal_delivery(self):
        flagged = sorted(k for k in self.db.cards
                         if "own_half_only" in set((self.db.get(k) or {}).get("flags") or ()))
        self.assertEqual(["barbarian_barrel", "royal_delivery", "the_log"], flagged)

    def test_the_HERO_barrel_inherits_the_flag_from_the_base_row(self):
        """`barbarian_barrel_hero` is a minimal overlay ({damage, spawns_troop, ability_*}); it
        must pick the flag up from the base rather than needing its own copy, or the two forms of
        one card would diverge the first time either is edited."""
        self.assertTrue(build_spec(self.db, "barbarian_barrel_hero", LVL).own_half_only)


class TheCardIsStillASpellTests(unittest.TestCase):
    """The flag changes WHERE it may be put, not WHAT it is."""

    def test_both_clamped_rollers_keep_their_corridor(self):
        _cfg, db, _A = _board()
        for key in CLAMPED:
            with self.subTest(card=key):
                sp = build_spec(db, key, LVL)
                self.assertEqual("spell", sp.kind)
                self.assertTrue(sp.rolls)
                self.assertGreater(sp.roll_len, 0.0)
                self.assertGreater(sp.spell_dmg, 0.0)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
