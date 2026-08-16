"""Wave-3 evolution mechanics (2026-08-14 sweep 3): the 17 remaining evos.
Focused behavior tests -- spec-level values are asserted inline where a full
engagement would only re-prove the build_spec overlay."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_sim_status_effects import _make_engine
from clashrl.sim.engine import build_spec, _dist


def _one(eng, team):
    return [u for u in eng.units if u.team == team][-1]


class EvoWave3Tests(unittest.TestCase):
    def test_mega_knight_uppercut(self):
        eng = _make_engine()
        mk = build_spec(eng.db, "mega_knight_evo", 11)
        self.assertEqual(mk.uppercut_tiles, 4.0)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, mk, 0.50, 0.55))
        eng.elixir = [10.0, 10.0]
        # 2.5 tiles out: clear of his 430 SPAWN blast (radius 1.3), inside walking range, and
        # under his 3.5-tile jump minimum -- the first hp drop is his SWING, with the uppercut.
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.55 + 2.5 / 32.0))
        kn = _one(eng, 0)
        y0 = kn.y
        for _ in range(120):
            eng.advance(0.05)
            if kn.hp < kn.spec.hp - 100:                 # his swing landed
                break
        self.assertGreater(kn.y, y0 + 1.5 / 32.0,
                           "the uppercut launches the knight back toward ITS OWN tower")

    def test_hunter_net_roots(self):
        eng = _make_engine()
        hu = build_spec(eng.db, "hunter_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, hu, 0.50, 0.50))
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.60))
        kn = _one(eng, 0)
        rooted = False
        for _ in range(60):
            eng.advance(0.1)
            if kn.stun_left > 2.0:
                rooted = True
                break
        self.assertTrue(rooted, "the net must root the closest unit for ~3 s")

    def test_wizard_shield_burst(self):
        eng = _make_engine()
        wz = build_spec(eng.db, "wizard_evo", 11)
        self.assertAlmostEqual(wz.shield_burst_dmg, 281.0, delta=1)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, wz, 0.50, 0.55))
        wiz = _one(eng, 1)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.57))
        kn = _one(eng, 0)
        for _ in range(14):
            eng.advance(0.1)
        hp0 = kn.hp
        wiz.shield_left = 1.0
        eng._hurt(wiz, 50.0)                             # strips the shield -> burst
        self.assertLess(kn.hp, hp0 - 200, "the Fire Shield explosion must hit the knight")

    def test_witch_heals_on_skeleton_death(self):
        eng = _make_engine()
        wi = build_spec(eng.db, "witch_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, wi, 0.50, 0.40))
        witch = _one(eng, 1)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, build_spec(eng.db, "skeletons", 11), 0.50, 0.45))
        skels = [u for u in eng.units if u.team == 1 and u.spec.base == "skeletons"]
        for _ in range(14):
            eng.advance(0.1)
        hp0 = witch.hp
        for sk in skels:
            sk.hp = 0.0
        eng.advance(0.1)
        # Re-sourced 2026-08-16 from the Evolution page's own vardefines, whose table headers name
        # them: heal_11 76 is "Skeleton Death Heal" (we carried 109) and maks_hp_11 1039 is "Max
        # Hitpoints", i.e. 1039/839 = +23.8% overheal, not the +30% that had been read off a stale
        # RoyaleAPI blurb. The old base of 796 was itself back-derived from that stale 30%.
        self.assertGreaterEqual(witch.hp, min(witch.spec.hp * 1.238, hp0 + 3 * 76) - 1,
                                "76 per friendly skeleton death, overheal to +23.8%")

    def test_minion_horde_iframes(self):
        eng = _make_engine()
        mh = build_spec(eng.db, "minion_horde_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, mh, 0.50, 0.40))
        m = _one(eng, 1)
        hp0 = m.hp
        eng._hurt(m, 30.0)                               # first hit LANDS...
        self.assertAlmostEqual(m.hp, hp0 - 30.0, delta=1)
        eng._hurt(m, 500.0)                              # ...then immunity eats the second
        self.assertAlmostEqual(m.hp, hp0 - 30.0, delta=1)
        m.iframes_left = 0.0                             # window over
        eng._hurt(m, 30.0)
        self.assertAlmostEqual(m.hp, hp0 - 60.0, delta=1)

    def test_princess_slow_volley(self):
        eng = _make_engine()
        pr = build_spec(eng.db, "princess_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50, 0.60))
        victim = _one(eng, 0)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, pr, 0.50, 0.60 - 6.0 / 32.0))
        slowed = False
        for _ in range(80):
            eng.advance(0.05)
            if victim.slow_left > 5.0:                   # the 7 s slow, not a generic one
                slowed = True
                break
        self.assertTrue(slowed, "her first volley slows for 7 s")

    def test_dart_goblin_poison_ticks(self):
        eng = _make_engine()
        dg = build_spec(eng.db, "dart_goblin_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50, 0.60))
        victim = _one(eng, 0)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, dg, 0.50, 0.60 - 5.5 / 32.0))
        for _ in range(60):
            eng.advance(0.05)
            if victim.poison_left > 0.0:
                break
        self.assertGreater(victim.poison_left, 0.0, "a dart must poison the victim")
        self.assertGreater(victim.poison_take, 0.0)

    def test_cannon_deploy_volley(self):
        eng = _make_engine()
        cn = build_spec(eng.db, "cannon_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.55))
        kn = _one(eng, 0)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, cn, 0.50, 0.55 - 4.5 / 32.0))
        hp0 = kn.hp
        for _ in range(30):
            eng.advance(0.05)
        self.assertLess(kn.hp, hp0 - 80, "the 9-ball volley must catch a knight in its fan")

    def test_goblin_giant_low_hp_spawner(self):
        eng = _make_engine()
        gg = build_spec(eng.db, "goblin_giant_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, gg, 0.50, 0.40))
        giant = _one(eng, 1)
        for _ in range(14):
            eng.advance(0.1)
        giant.hp = giant.spec.hp * 0.4                   # below the 50% gate
        for _ in range(50):                              # 5 s -> ~2 spawn ticks
            eng.advance(0.1)
        gobs = [u for u in eng.units if u.team == 1 and u.spec.base == "goblins"]
        self.assertGreaterEqual(len(gobs), 2, "below 50% he summons a goblin every 2.2 s")

    def test_skarmy_general_ghosts(self):
        eng = _make_engine()
        sa = build_spec(eng.db, "skeleton_army_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, sa, 0.50, 0.45))
        gen = [u for u in eng.units if u.team == 1 and u.spec.base == "skarmy_general"]
        self.assertEqual(len(gen), 1, "the shielded General deploys with the army")
        skels = [u for u in eng.units if u.spec.key == "skeleton_army_evo"]
        self.assertGreaterEqual(len(skels), 10)
        for _ in range(14):
            eng.advance(0.1)
        skels[0].hp = 0.0
        eng.advance(0.1)
        ghosts = [u for u in eng.units if u.invis_left > 9000.0]
        self.assertEqual(len(ghosts), 1, "a skeleton dying near its General becomes a ghost")
        gen[0].hp = 0.0
        eng.advance(0.1)
        eng.advance(0.1)
        ghosts = [u for u in eng.units if u.invis_left > 9000.0 and u.hp > 0]
        self.assertEqual(len(ghosts), 0, "ghosts vanish with the General")

    def test_snowball_carry_roll(self):
        eng = _make_engine()
        sb = build_spec(eng.db, "giant_snowball_evo", 11)
        self.assertTrue(sb.rolls and sb.carry_roll)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.50))
        kn = _one(eng, 0)
        for _ in range(12):
            eng.advance(0.1)
        y0 = kn.y
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, sb, kn.x, kn.y - 0.5 / 32.0))
        for _ in range(14):
            eng.advance(0.1)
        self.assertGreater(kn.y, y0 + 2.5 / 32.0, "Snow Bowling sweeps the knight to the roll's end")
        self.assertGreater(kn.slow_left, 2.0, "and slows for 4 s")

    def test_battle_ram_bounces_and_breaks_into_evo_barbs(self):
        eng = _make_engine()
        br = build_spec(eng.db, "battle_ram_evo", 11)
        eng.elixir = [10.0, 10.0]
        # Both on the SAME side of the river: the ram is not a river-jumper, so a cross-river
        # spawn detours via the bridge and never arrives inside the test window.
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50, 0.70))
        bow = _one(eng, 0)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, br, 0.50, 0.52))   # ~4.6-tile run-up: the charge arms
        ram = _one(eng, 1)
        bounced = False
        for _ in range(200):
            prev_hp, prev_y = bow.hp, ram.y
            eng.advance(0.05)
            if prev_hp - bow.hp > 200:                   # the ram landed (bounce is same-tick)
                self.assertGreater(ram.hp, 0.0, "Super Charge: it does NOT die on impact")
                self.assertLess(ram.y, prev_y - 2.0 / 32.0, "and it BOUNCES back off the target")
                bounced = True
                break
        self.assertTrue(bounced, "the ram must land its charge on the building")
        ram.hp = 0.0
        eng.advance(0.1)
        barbs = [u for u in eng.units if u.team == 1 and u.spec.key == "barbarians_evo"]
        self.assertEqual(len(barbs), 2, "death breaks it into EVOLVED barbarians")

    def test_royal_hogs_air_drop(self):
        eng = _make_engine()
        rh = build_spec(eng.db, "royal_hogs_evo", 11)
        self.assertTrue(rh.flying)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, rh, 0.50, 0.45))
        hog = _one(eng, 1)
        self.assertTrue(hog.spec.flying)
        eng._hurt(hog, 10.0)                             # first damage -> they fall
        self.assertFalse(hog.spec.flying, "hurt hogs fall to the ground")

    def test_lumberjack_ghost(self):
        eng = _make_engine()
        lj = build_spec(eng.db, "lumberjack_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, lj, 0.50, 0.50))
        jack = _one(eng, 1)
        for _ in range(14):
            eng.advance(0.1)
        jack.hp = 0.0
        eng.advance(0.1)
        ghosts = [u for u in eng.units if u.spec.base == "lumberjack_ghost"]
        self.assertEqual(len(ghosts), 1, "his ghost rises where he fell")
        self.assertTrue(ghosts[0].ghost, "and nothing can target it")
        self.assertTrue(eng.rage_zones, "the base death-Rage still drops")
        for _ in range(70):                              # ghost_life 5 s (+ deploy time)
            eng.advance(0.1)
        self.assertFalse([u for u in eng.units if u.spec.base == "lumberjack_ghost"],
                         "the ghost dissolves after its time")

    def test_goblin_cage_hooks_passersby(self):
        eng = _make_engine()
        gc = build_spec(eng.db, "goblin_cage_evo", 11)
        self.assertEqual(gc.hook_max, 3.0)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, gc, 0.50, 0.55))
        cage = _one(eng, 1)
        eng.elixir = [10.0, 10.0]
        # 0.38, not 0.42: the Goblin Cage's body is 1.0 tiles (game-file collision_radius 1000,
        # imported 2026-08-16 -- it used to take the 0.5 baseline fallback). At 0.42 the Knight now
        # starts INSIDE the cage's reach, so the cage just brawls him and the hook never fires --
        # which is correct behaviour, not a regression. 0.38 puts him back where the test means him
        # to be: a passer-by outside reach but inside the 3-tile hook. Verified he is reeled 0.60
        # tiles there.
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.38, 0.55))
        kn = _one(eng, 0)
        for _ in range(12):
            eng.advance(0.1)
        kn.stun_left = 30.0                              # pinned: only the hook can move him
        d0 = _dist(kn.x, kn.y, cage.x, cage.y)
        moved = False
        for _ in range(80):
            eng.advance(0.1)
            kn.stun_left = 30.0
            if _dist(kn.x, kn.y, cage.x, cage.y) < d0 - 0.15:
                moved = True
                break
        # Fisherman-hook semantics: the reel brings the victim INTO REACH (then the cage brawls),
        # not inside the building -- the strategic effect (yank + engage) is what matters.
        self.assertTrue(moved, "the cage must reel a pinned passer-by toward itself")

    def test_inferno_dragon_keeps_stage_on_kill(self):
        eng = _make_engine()
        idr = build_spec(eng.db, "inferno_dragon_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, idr, 0.50, 0.55))
        drag = _one(eng, 1)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.57))
        kn = _one(eng, 0)
        for _ in range(80):
            eng.advance(0.1)
            if drag.focus_time > 4.0:
                break
        self.assertGreater(drag.focus_time, 4.0, "the beam must be ramped before the kill")
        kn.hp = 0.0
        eng.advance(0.1)
        eng.advance(0.1)
        self.assertGreater(drag.focus_time, 3.0, "the stage is KEPT after the kill (9 s hold)")


if __name__ == "__main__":
    unittest.main(verbosity=1)
