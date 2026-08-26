"""Six user-reported sim defects, 2026-08-18. Every number here was measured before the fix.

RAMP-UP SURVIVED EVERYTHING (Mighty Miner / Inferno Dragon / Inferno Tower). The stages only ever
reset when the TARGET CHANGED, so a stun, a Log knockback, a Tornado drag or the target simply
walking out of reach left `focus_time` untouched and the beam resumed at full stage 3 the instant
contact returned. Measured: knocked back 3 tiles, a Mighty Miner went focus 6.60 -> 6.70, stage 3
-> 3. Resetting an Inferno by displacing or zapping it is a core interaction and the sim had none
of it.

EVO FIRECRACKER'S SPARKS IGNORED CROWN TOWERS. The lingering zones iterated `self.units` only, so a
tower standing in a spark field took literally nothing -- measured 0 damage from a 5 s zone placed
directly on it. The wiki's own vardefines give the reduced crown rate exactly: Big_dmg_11 48 with
Big_Crown_dmg_11 15, Small_dmg_11 48 with Small_Crown_dmg_11 15 -- 15/48 = 0.3125 for both.

FIRECRACKER NEVER RE-AIMED AFTER RECOILING. `locked` means "already swinging, nothing else exists"
and only an aggro reset clears it -- but the recoil deliberately raises none (that would wipe a
Sparky's charge). She shoved herself out of her own 6 tiles and stayed locked on an unreachable
target: measured ZERO retargets over 40 s, ending out of reach.

SHRAPNEL WAS SQUASHED BY THE ARENA WALL. Pierce projectiles were clamped like bodies, so a bolt
that reached the border stopped there, burned its remaining range in place and dropped its spark
zone against the edge. Measured 24 of 95 bolt samples sitting exactly on x=0.

THE FUSED DEATH BOMB WAS NARROWER THAN THE INSTANT ONE. `_death_blast` is edge-based, but a card
with `death_delay_s` (Balloon, Giant Skeleton, Bomb Tower) routes through the generic spell path,
which compared centre to centre -- shrinking the SAME 3-tile bomb by each target's own radius.
Measured against a crown tower: it reached 3.0 tiles from the tower's CENTRE instead of 3.0 from
its hitbox, so 1.5 tiles of the published radius were missing.

A DART GOBLIN OUT-RANGED THE KING TOWER. Both published numbers are right (wiki: goblin 6.5, king
7). The error was that the two sides of the duel used different rulers -- a troop shooting a tower
measures centre-to-EDGE and so SUBTRACTS the tower's half-width (2.0 for the king), while the tower
only subtracted the troop's ~0.5. Measured: the goblin opened fire at 8.50 tiles from the king's
centre, the king answered only to 8.00, and it sieged untouched.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                                          # noqa: E402
from clashrl.sim.env import SimMatchEnv                                    # noqa: E402
from clashrl.sim.engine import (Unit, build_spec, replace, _Spell, _gap,   # noqa: E402
                                _body_radius, _REACH_SLOP, _TILES_Y,
                                _SPARK_CROWN_FRAC)

LVL = 11


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())
        cls.db = cls.env.db

    def fresh(self):
        self.env.reset()
        e = self.env.eng
        e.units.clear()
        e.spells.clear()
        e.projectiles.clear()
        e.spark_zones.clear()
        return e


class RampResetTests(_Base):
    """The ramp climbs only while the unit is ACTUALLY firing."""

    RAMPERS = ("mighty_miner", "inferno_dragon", "inferno_tower")

    def _saturate(self, name):
        """Pin both bodies together until the ramp is at its top stage, then hand them back."""
        e = self.fresh()
        a = build_spec(self.db, name, LVL)
        t = build_spec(self.db, "giant", LVL)
        atk = Unit(spec=a, team=0, x=0.50, y=0.55, hp=a.hp)
        tgt = Unit(spec=t, team=1, x=0.50, y=0.55 - (a.reach * 0.5) / _TILES_Y, hp=t.hp * 400)
        e.units += [atk, tgt]
        ax, ay, tx, ty = atk.x, atk.y, tgt.x, tgt.y
        for _ in range(120):                       # 12 s -- three stages need 6 s
            atk.x, atk.y, tgt.x, tgt.y = ax, ay, tx, ty
            e.advance(0.1)
        self.assertGreater(atk.focus_time, a.stage_time * (len(a.dmg_stages) - 1),
                           "%s never reached its top stage, so the probe proves nothing" % name)
        return e, atk, tgt, a

    def test_the_ramp_reaches_its_top_stage_when_undisturbed(self):
        """The control. A reset that also breaks the normal case is not a fix."""
        for name in self.RAMPERS:
            with self.subTest(card=name):
                e, atk, tgt, a = self._saturate(name)
                before, hp = atk.focus_time, tgt.hp
                e.advance(0.1)
                e.advance(0.1)
                self.assertGreaterEqual(atk.focus_time, before,
                                        "an undisturbed ramp must keep climbing")
                self.assertGreater(hp - tgt.hp, a.dmg_stages[-1] * 0.9,
                                   "a top-stage hit should land")

    def _disrupt(self, name, how):
        e, atk, tgt, a = self._saturate(name)
        push = a.reach + tgt.spec.radius + 2.0     # guaranteed to clear reach AND the slop
        if how == "stun":
            atk.stun_left = 0.5
        elif how == "freeze":
            atk.stun_left = 2.0
        elif how == "knock":
            atk.y += push / _TILES_Y               # Log / Snowball / Explosive Escape
        elif how == "drag":
            tgt.y -= push / _TILES_Y               # Tornado pulling the TARGET away
        hp = tgt.hp
        e.advance(0.1)
        e.advance(0.1)
        return atk.focus_time, hp - tgt.hp, a

    def test_any_interruption_drops_the_ramp_to_stage_one(self):
        for name in self.RAMPERS:
            for how in ("stun", "freeze", "knock", "drag"):
                with self.subTest(card=name, interruption=how):
                    focus, _dealt, _a = self._disrupt(name, how)
                    self.assertLess(focus, 0.3,
                                    "%s kept its ramp through a %s" % (name, how))

    def test_no_top_stage_hit_lands_after_an_interruption(self):
        """The reset is evaluated at the START of a tick, so it trails the event by one 0.1 s
        step. That costs nothing, and this is the assertion that proves it: during the lag the
        unit is out of reach (or stunned) and cannot swing, so no stage-3 damage leaks through."""
        for name in self.RAMPERS:
            for how in ("stun", "freeze", "knock", "drag"):
                with self.subTest(card=name, interruption=how):
                    _focus, dealt, a = self._disrupt(name, how)
                    self.assertLess(dealt, a.dmg_stages[-1] * 0.5,
                                    "%s landed a ramped hit after a %s" % (name, how))

    def test_an_inferno_tower_resets_when_its_target_walks_out_of_reach(self):
        """It cannot be displaced -- but the target leaving is the same interruption, and this is
        the case the old target-changed-only rule could never catch: the target never changed."""
        e = self.fresh()
        it = build_spec(self.db, "inferno_tower", LVL)
        g = build_spec(self.db, "giant", LVL)
        tw = Unit(spec=it, team=0, x=0.50, y=0.60, hp=it.hp)
        gi = Unit(spec=g, team=1, x=0.50, y=0.60 - 3.0 / _TILES_Y, hp=g.hp * 400)
        e.units += [tw, gi]
        gx, gy = gi.x, gi.y
        for _ in range(120):
            gi.x, gi.y = gx, gy
            e.advance(0.1)
        self.assertGreater(tw.focus_time, 4.0)
        # NOTE an Inferno Tower's sight (6.0) equals its reach (6.0), so a target that leaves its
        # reach also leaves its sight and is dropped -- there is no "same target, out of range"
        # state to isolate for this card. What matters is the outcome the user asked for: the beam
        # does not keep its stage while it is not firing.
        gi.x, gi.y = 0.10, 0.10                    # far outside the tower's 6 tiles
        e.advance(0.1)
        e.advance(0.1)
        self.assertLess(tw.focus_time, 0.3)


class SparkCrownDamageTests(_Base):
    def _soak(self, offset_tiles=0.0, team=1):
        """Park one big-spark zone on a tower and return the damage it took."""
        e = self.fresh()
        fc = build_spec(self.db, "firecracker_evo", LVL)
        tw = [t for t in e.towers[team] if t.alive][0]
        hp0 = tw.hp
        tick = fc.spark_dps_big * 0.25
        e.spark_zones.append([tw.x, tw.y + offset_tiles / _TILES_Y, fc.spark_r, 0,
                              e.t + 3.0, tick, e.t])
        for _ in range(35):
            e.advance(0.1)
        return hp0 - tw.hp, tick

    def test_the_published_crown_fraction_is_exactly_15_over_48(self):
        self.assertAlmostEqual(15.0 / 48.0, _SPARK_CROWN_FRAC, places=6)

    def test_a_spark_zone_on_a_tower_chips_it_at_the_reduced_rate(self):
        dealt, tick = self._soak()
        self.assertGreater(dealt, 0.0, "towers took nothing at all")
        # whole ticks only -- the 0.25 s cadence lands on the 0.1 s step grid
        ticks = round(dealt / (tick * _SPARK_CROWN_FRAC))
        self.assertGreater(ticks, 4)
        self.assertAlmostEqual(dealt, ticks * tick * _SPARK_CROWN_FRAC, places=3,
                               msg="crown damage is not a clean multiple of the reduced tick")

    def test_it_is_reduced_and_not_the_full_troop_damage(self):
        dealt, tick = self._soak()
        n = round(dealt / (tick * _SPARK_CROWN_FRAC))
        self.assertLess(dealt, n * tick * 0.5, "the tower is taking near-full troop damage")

    def test_a_zone_nowhere_near_the_tower_does_nothing(self):
        dealt, _tick = self._soak(offset_tiles=-8.0)
        self.assertEqual(0.0, dealt)

    def test_our_own_tower_is_not_chipped_by_our_own_sparks(self):
        dealt, _tick = self._soak(team=0)
        self.assertEqual(0.0, dealt, "a spark zone damaged the team that cast it")


class RecoilRetargetTests(_Base):
    """She must re-open the choice when her own recoil breaks the engagement."""

    def _run(self, key):
        e = self.fresh()
        f = build_spec(self.db, key, LVL)
        k = build_spec(self.db, "knight", LVL)
        a = Unit(spec=f, team=0, x=0.50, y=0.62, hp=f.hp * 500)   # survive, so we measure HER
        n = Unit(spec=k, team=1, x=0.50, y=0.62 - (f.reach - 0.4) / _TILES_Y, hp=k.hp * 400)
        e.units += [a, n]
        stuck = shots = 0
        prev = a.cooldown
        for _ in range(400):
            e.advance(0.1)
            if a.cooldown > prev:
                shots += 1
            prev = a.cooldown
            if a.locked and a.target is not None \
                    and _gap(a.x, a.y, a.target) > f.reach + _REACH_SLOP:
                stuck += 1
        return shots, stuck, f

    def test_she_keeps_firing_instead_of_locking_onto_an_unreachable_target(self):
        for key in ("firecracker", "firecracker_evo"):
            with self.subTest(card=key):
                shots, stuck, _f = self._run(key)
                self.assertGreater(shots, 8, "she stopped shooting altogether")
                # one tick per shot is the recoil step itself, before the next tick re-evaluates
                self.assertLessEqual(stuck, shots + 2,
                                     "she is parked on a target she cannot reach")

    def test_the_recoil_does_not_wipe_a_charge(self):
        """Only `locked` is cleared -- NOT aggro_reset, which a real shove raises. Routing the
        recoil through that would reset a Sparky's charge and every ramp, which is exactly what
        the recoil is documented not to do."""
        e = self.fresh()
        f = build_spec(self.db, "firecracker_evo", LVL)
        k = build_spec(self.db, "knight", LVL)
        a = Unit(spec=f, team=0, x=0.50, y=0.62, hp=f.hp * 500)
        n = Unit(spec=k, team=1, x=0.50, y=0.62 - 0.5 / _TILES_Y, hp=k.hp * 400)
        e.units += [a, n]
        for _ in range(80):
            e.advance(0.1)
            self.assertFalse(a.aggro_reset, "the recoil raised an aggro reset")


class SparkBorderTests(_Base):
    def test_shrapnel_leaves_the_board_instead_of_piling_up_on_the_wall(self):
        e = self.fresh()
        fc = build_spec(self.db, "firecracker_evo", LVL)
        k = build_spec(self.db, "knight", LVL)
        a = Unit(spec=fc, team=0, x=0.055, y=0.60, hp=fc.hp)      # hard against the left wall
        t = Unit(spec=k, team=1, x=0.055, y=0.50, hp=k.hp * 400)
        e.units += [a, t]
        xs = []
        for _ in range(200):
            e.advance(0.1)
            xs += [p.x for p in e.projectiles if p.pierce]
        self.assertTrue(xs, "no shrapnel was ever in flight")
        self.assertFalse([x for x in xs if abs(x) < 1e-9],
                         "a bolt was pinned exactly on the arena wall")
        self.assertTrue([x for x in xs if x < 0.0],
                        "no bolt continued past the border -- it is still being clamped")


class FusedBombGeometryTests(_Base):
    """A death bomb measures its radius to the hitbox EDGE, delayed or not."""

    def _bomb(self, edge, offset_tiles):
        e = self.fresh()
        b = build_spec(self.db, "balloon", LVL)
        tw = [t for t in e.towers[1] if t.alive][0]
        hp0 = tw.hp
        spec = replace(b, spell_dmg=b.death_dmg, spell_radius=b.death_radius,
                       spell_tower_dmg=b.death_dmg * b.death_crown_mult,
                       pulls=False, rolls=False, zone_s=0.0, top_n_targets=0, spawn_count=0,
                       decoy_mirror=False, zap_pulses=0, death_delay_s=0.0, blast_edge=edge)
        e.spells.append(_Spell(0, tw.x, tw.y + offset_tiles / _TILES_Y, spec, 0.05))
        for _ in range(10):
            e.advance(0.1)
        return hp0 - tw.hp, _body_radius(tw)

    def test_the_balloons_radius_is_the_published_three_tiles(self):
        b = build_spec(self.db, "balloon", LVL)
        self.assertAlmostEqual(3.0, b.death_radius, places=3)   # wiki: Death Damage Splash Radius 3
        self.assertAlmostEqual(3.0, b.death_delay_s, places=3)  # ...on a 3 sec fuse

    def test_the_fused_bomb_reaches_three_tiles_from_the_towers_hitbox(self):
        _d, half = self._bomb(True, 0.0)
        b = build_spec(self.db, "balloon", LVL)
        hit, _ = self._bomb(True, b.death_radius + half - 0.1)
        self.assertGreater(hit, 0.0, "the bomb fell short of its own published radius")
        miss, _ = self._bomb(True, b.death_radius + half + 0.5)
        self.assertEqual(0.0, miss, "the bomb reached beyond its radius")

    def test_edge_measurement_is_wider_than_the_centre_measurement_it_replaced(self):
        """The regression guard: this is the whole defect, in one comparison."""
        b = build_spec(self.db, "balloon", LVL)
        _d, half = self._bomb(True, 0.0)
        probe = b.death_radius + half - 0.1                     # inside edge-range, outside centre
        self.assertGreater(self._bomb(True, probe)[0], 0.0)
        self.assertEqual(0.0, self._bomb(False, probe)[0],
                         "the old centre-based rule should NOT have reached here")

    def test_an_ordinary_thrown_spell_is_unchanged(self):
        """Only death bombs carry blast_edge; Earthquake and the Log keep centre measurement."""
        for key in ("earthquake", "the_log"):
            spec = build_spec(self.db, key, LVL)
            self.assertFalse(spec.blast_edge, "%s must not be edge-measured" % key)


class TowerReachTests(_Base):
    """No card whose published range is SHORTER than a tower's may siege it untouched."""

    def _duel_limits(self, tw, card):
        sp = build_spec(self.db, card, LVL)
        rng = self.env.eng.king_range if tw.king else self.env.eng.tower_range
        unit_max = sp.reach + _body_radius(tw)      # centre-to-centre where the card can open fire
        tower_max = rng + sp.radius                 # ...and where the tower can answer
        return unit_max, tower_max, sp

    def test_a_dart_goblin_cannot_outrange_either_tower(self):
        e = self.fresh()
        for tw in e.towers[1]:
            with self.subTest(king=tw.king):
                unit_max, tower_max, _ = self._duel_limits(tw, "dart_goblin")
                self.assertGreaterEqual(tower_max, unit_max,
                                        "a dart goblin opens fire at %.2f, the tower answers only "
                                        "to %.2f" % (unit_max, tower_max))

    def test_the_king_answers_a_goblin_parked_at_its_maximum_reach(self):
        e = self.fresh()
        king = [t for t in e.towers[1] if t.king][0]
        for t in e.towers[1]:
            if not t.king:
                t.alive = False                     # isolate the king from its princesses
        dg = build_spec(self.db, "dart_goblin", LVL)
        d = dg.reach + _body_radius(king) - 0.05    # the furthest the goblin can shoot from
        u = Unit(spec=dg, team=0, x=king.x, y=king.y + d / _TILES_Y, hp=dg.hp * 200)
        e.units.append(u)
        hp0 = u.hp
        for _ in range(300):
            e.advance(0.1)
        self.assertLess(u.hp, hp0, "the goblin sieged the king untouched")

    def test_cards_that_SHOULD_outrange_a_tower_still_do(self):
        """The fix must not make towers unbeatable: a siege card's whole identity is out-ranging
        them. X-Bow 11.5 and Princess 9.0 are both longer than any tower and must stay that way."""
        e = self.fresh()
        prin = [t for t in e.towers[1] if not t.king][0]
        for card in ("x_bow", "princess"):
            with self.subTest(card=card):
                unit_max, tower_max, _ = self._duel_limits(prin, card)
                self.assertGreater(unit_max, tower_max,
                                   "%s must still out-range a princess tower" % card)

    def test_short_ranged_cards_are_still_beaten_by_a_princess_tower(self):
        e = self.fresh()
        prin = [t for t in e.towers[1] if not t.king][0]
        for card in ("musketeer", "firecracker", "hog_rider", "royal_giant"):
            with self.subTest(card=card):
                unit_max, tower_max, _ = self._duel_limits(prin, card)
                self.assertGreaterEqual(tower_max, unit_max)

    def test_both_towers_end_up_with_the_same_reach_from_their_own_edge(self):
        """The king is 0.5 tiles wider, so a centre-measured king range must exceed the princess's
        by exactly that to be equally effective. This is the arithmetic the fix encodes."""
        e = self.fresh()
        king = [t for t in e.towers[1] if t.king][0]
        prin = [t for t in e.towers[1] if not t.king][0]
        self.assertAlmostEqual(e.king_range - _body_radius(king),
                               e.tower_range - _body_radius(prin), places=3)


if __name__ == "__main__":
    unittest.main(verbosity=1)
