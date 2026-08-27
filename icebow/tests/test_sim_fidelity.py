"""2026-08-15 fidelity batch, wiki-verified: siege wind-up + Mortar dead zone, Poison DoT
zone, Void count tiers, Graveyard timed edge spawns, Lightning/Vines top-3 targeting, Ronin
parry, real-game tile snap, and the action-latency queue."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl.config import Config          # noqa: E402
from clashrl.sim.env import SimMatchEnv    # noqa: E402
from clashrl.sim.engine import build_spec  # noqa: E402


try:                                     # discovered as a package (python -m unittest discover)
    from ._deckcards import requires_cards
except ImportError:                      # ...or run as a plain script
    from _deckcards import requires_cards


def _quiet(seed=42):
    env = SimMatchEnv(Config.load(), seed=seed)
    env.reset()
    env.opponent.act = lambda eng: None
    return env


def _tick(env, seconds):
    """Advance roughly `seconds` of GAME TIME.

    This used to take one step per second, which silently assumed sim.agent_dt == 1.0 -- the
    helper never honoured its own parameter name. Lowering the decision period to 0.6 s exposed
    it: every "after ~3 s" assertion was really testing 1.8 s. Convert through the env's own dt so
    these stay time-based whatever the period is.
    """
    dt = float(getattr(env, "agent_dt", 1.0)) or 1.0
    for _ in range(max(1, int(round(float(seconds) / dt)))):
        env.step((False, 0, 0))


def _silence_towers(env):
    for side in (0, 1):
        for tw in env.eng.towers[side]:
            tw.stun_left = 999.0


try:                                     # discovered as a package (python -m unittest discover)
    from ._deckcards import a_damage_spell, a_ground_only_troop
except ImportError:                      # ...or run as a plain script
    from _deckcards import a_damage_spell, a_ground_only_troop


class SiegeTests(unittest.TestCase):
    def test_xbow_windup_delays_first_shot(self):
        env = _quiet()
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "x_bow", 11), 0.20, 0.53)
        hp0 = env.eng.towers[1][0].hp
        _tick(env, 3)                                    # still winding up (3.5 s deploy)
        self.assertEqual(env.eng.towers[1][0].hp, hp0, "no shots during the 3.5s wind-up")
        _tick(env, 4)
        self.assertLess(env.eng.towers[1][0].hp, hp0, "locked and firing once deployed")

    def test_mortar_sieges_from_range_but_has_a_dead_zone(self):
        env = _quiet(seed=43)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "mortar", 11), 0.30, 0.45)
        hp0 = env.eng.towers[0][0].hp
        _tick(env, 12)                                   # wind-up + a couple of 5s shells
        self.assertLess(env.eng.towers[0][0].hp, hp0 - 200,
                        "a Mortar 7 tiles out must shell the princess tower")
        env2 = _quiet(seed=44)
        env2.eng.elixir[0] = env2.eng.elixir[1] = 10.0
        assert env2.eng.deploy(1, build_spec(env2.eng.db, "mortar", 11), 0.70, 0.70)
        assert env2.eng.deploy(0, build_spec(env2.eng.db, "knight", 11), 0.70, 0.72)
        _tick(env2, 8)
        kn = next(u for u in env2.eng.units if u.team == 0)
        self.assertGreater(kn.hp, kn.spec.hp * 0.9,
                           "inside the 3.5-tile blind spot the Mortar cannot hit back")


class ZoneSpellTests(unittest.TestCase):
    def test_poison_is_damage_over_time_not_a_blast(self):
        env = _quiet(seed=45)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "bomb_tower", 11), 0.30, 0.40)
        assert env.eng.deploy(1, build_spec(env.eng.db, "bomb_tower", 11), 0.70, 0.40)
        tgt, ctl = [u for u in env.eng.units if u.team == 1]
        assert env.eng.deploy(0, build_spec(env.eng.db, "poison", 11), tgt.x, tgt.y)
        _tick(env, 10)
        extra = ctl.hp - tgt.hp                          # decay cancels out via the control twin
        self.assertGreater(extra, 550, "8 ticks x 92 must accumulate (got %.0f)" % extra)
        self.assertLess(extra, 900, "and not land as one 736 blast plus ticks")

    def test_poison_chips_towers_at_crown_rate(self):
        env = _quiet(seed=46)
        env.eng.elixir[1] = 10.0
        tw = env.eng.towers[0][0]
        hp0 = tw.hp
        assert env.eng.deploy(1, build_spec(env.eng.db, "poison", 11), tw.x, tw.y)
        _tick(env, 10)
        self.assertAlmostEqual(hp0 - tw.hp, 8 * 23, delta=30,
                               msg="8 seconds of crown ticks, 23 each")

    def test_void_melts_a_lone_tank_but_tickles_a_crowd(self):
        env = _quiet(seed=47)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "tombstone", 11), 0.30, 0.40)
        lone = [u for u in env.eng.units if u.team == 1][-1]
        assert env.eng.deploy(0, build_spec(env.eng.db, "void", 11), lone.x, lone.y)
        _tick(env, 5)
        self.assertLessEqual(lone.hp, 0.0, "solo ticks of 696 melt a lone building")
        env2 = _quiet(seed=48)
        ts = build_spec(env2.eng.db, "bomb_tower", 11)
        # five buildings share the zone: every tick stays in the 4+ tier (153), which a
        # bomb tower easily survives -- unlike the swarm case, where void clears the 81hp
        # bodies on tick one and the count COLLAPSES back to the solo tier (also real).
        for ox in (0.28, 0.30, 0.32, 0.29, 0.31):
            env2.eng.elixir[1] = 10.0
            assert env2.eng.deploy(1, ts, ox, 0.40)
        crowd_ts = [u for u in env2.eng.units if u.team == 1][0]
        assert env2.eng.deploy(0, build_spec(env2.eng.db, "void", 11), 0.30, 0.40)
        _tick(env2, 5)
        self.assertGreater(crowd_ts.hp, 100.0,
                           "shared five ways, each tick drops to the 153 tier")

    def test_graveyard_spawns_the_wiki_ring(self):
        env = _quiet(seed=49)
        env.eng.elixir[1] = 10.0
        tw = env.eng.towers[0][0]
        hp0 = tw.hp
        assert env.eng.deploy(1, build_spec(env.eng.db, "graveyard", 11), tw.x, tw.y)
        _tick(env, 2)
        early = sum(1 for u in env.eng.units if u.team == 1)
        self.assertEqual(early, 0, "first Skeleton only after 2.2 s")
        z = env.eng.zones[0]
        _tick(env, 8)
        self.assertGreaterEqual(z.spawned, 10, "~12 Skeletons over the 9 s window")
        _tick(env, 6)
        self.assertLess(tw.hp, hp0, "the ring must actually chip the tower it surrounds")


class TopNSpellTests(unittest.TestCase):
    def test_lightning_ignores_the_swarm(self):
        env = _quiet(seed=50)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        for x in (0.28, 0.32, 0.36):
            assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), x, 0.40)
        assert env.eng.deploy(1, build_spec(env.eng.db, "skeletons", 11), 0.32, 0.42)
        knights = [u for u in env.eng.units if u.spec.base == "knight"]
        skels = [u for u in env.eng.units if u.spec.base == "skeletons"]
        assert env.eng.deploy(0, build_spec(env.eng.db, "lightning", 11), 0.32, 0.40)
        _tick(env, 2)
        for k in knights:
            self.assertLess(k.hp, k.spec.hp, "each high-HP Knight takes the bolt")
        for s in skels:
            self.assertGreater(s.hp, 0.0, "the swarm under the bolt is untouched")

    def test_vines_roots_the_target_in_place(self):
        env = _quiet(seed=51)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.30, 0.30)
        kn = [u for u in env.eng.units if u.team == 1][-1]
        _tick(env, 2)                                    # walking now
        assert env.eng.deploy(0, build_spec(env.eng.db, "vines", 11), kn.x, kn.y)
        _tick(env, 1)
        y_rooted = kn.y
        self.assertGreater(kn.stun_left, 0.5, "vines hold the troop in place")
        self.assertLess(kn.hp, kn.spec.hp - 250, "306 damage on the wrap")
        _tick(env, 1)
        self.assertAlmostEqual(kn.y, y_rooted, delta=0.005, msg="rooted = not moving")


class CombatQuirkTests(unittest.TestCase):
    def test_ronin_parries_the_first_melee_swing(self):
        env = _quiet(seed=52)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        for side in (0, 1):
            for tw in env.eng.towers[side]:
                tw.stun_left = 999.0                     # a clean duel: no tower fire
        assert env.eng.deploy(1, build_spec(env.eng.db, "ronin", 11), 0.50, 0.70)
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.72)
        ron = next(u for u in env.eng.units if u.team == 1)
        kn = next(u for u in env.eng.units if u.team == 0)
        _tick(env, 4)
        self.assertLess(kn.hp, kn.spec.hp - 600,
                        "the parried Knight eats a 742 counter on top of normal swings")
        self.assertGreater(ron.hp, ron.spec.hp - 500,
                           "one Knight swing was blocked outright")

    def test_deploys_snap_to_game_tiles(self):
        env = _quiet(seed=53)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.507, 0.807)
        u = [x for x in env.eng.units if x.team == 0][-1]
        self.assertAlmostEqual(u.x, 9.5 / 18.0, delta=1e-6)
        self.assertAlmostEqual(u.y, 25.5 / 32.0, delta=1e-6)

    def test_action_latency_queues_the_deploy(self):
        env = _quiet(seed=54)
        env.eng.elixir[0] = 10.0
        e0 = env.eng.elixir[0]
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.70, delay_s=0.25)
        self.assertEqual(sum(1 for u in env.eng.units if u.team == 0), 0,
                         "nothing on the board at decision time")
        self.assertLess(env.eng.elixir[0], e0, "but the elixir is already committed")
        env.eng.advance(0.3)
        self.assertEqual(sum(1 for u in env.eng.units if u.team == 0), 1,
                         "the tap lands ~0.25 s later, like the live pipeline")


class BomberEvoPin(unittest.TestCase):
    """User report 2026-08-15: 'the bomber evo fix seems to have been reverted, acting like a
    single-target melee troop'. Engine-level it is NOT (spec: reach 4.5, splash, 2 bounces;
    measured stop-gap 4.9 tiles) -- these pins make sure it can never silently regress."""

    def test_bomber_evo_is_ranged_splash_with_bounces(self):
        env = _quiet(seed=70)
        b = build_spec(env.eng.db, "bomber_evo", 11)
        self.assertGreaterEqual(b.reach, 4.0, "ranged, not melee")
        self.assertTrue(b.splash, "area damage")
        self.assertGreaterEqual(b.bounce_n, 2, "the evo bomb bounces on")
        self.assertGreater(b.proj_speed, 0.0, "thrown bomb, not a sword")

    def test_bomber_evo_attacks_from_range(self):
        from clashrl.sim.engine import _gap
        env = _quiet(seed=71)
        _silence_towers(env)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        # vs a STATIONARY building: a walking target (e.g. a Giant marching past him) will
        # close the distance ITSELF and end up point-blank -- that is real CR, and it is
        # probably what read as "melee" in the sim view. His own stop distance is ranged.
        assert env.eng.deploy(1, build_spec(env.eng.db, "bomb_tower", 11), 0.70, 0.55)
        g = [u for u in env.eng.units if u.team == 1][-1]
        assert env.eng.deploy(0, build_spec(env.eng.db, "bomber_evo", 11), 0.70, 0.78)
        b = [u for u in env.eng.units if u.team == 0][-1]
        _tick(env, 8)
        self.assertGreater(_gap(b.x, b.y, g), 3.0,
                           "he stands off and throws; a melee bomber would be at ~1 tile")
        self.assertLess(g.hp, g.spec.hp - 200, "and the bombs land from out there")


class Batch2Tests(unittest.TestCase):
    def test_battle_ram_breaks_into_barbarians_with_charge_damage(self):
        env = _quiet(seed=60)
        _silence_towers(env)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "bomb_tower", 11), 0.30, 0.60)
        bt = [u for u in env.eng.units if u.team == 1][-1]
        assert env.eng.deploy(0, build_spec(env.eng.db, "battle_ram", 11), 0.30, 0.78)
        hp0 = bt.hp
        _tick(env, 6)
        barbs = [u for u in env.eng.units if u.team == 0 and u.spec.base == "barbarians"]
        ram = [u for u in env.eng.units if u.team == 0 and u.spec.base == "battle_ram"]
        self.assertEqual(len(barbs), 2, "the break reveals the two Barbarians underneath")
        self.assertEqual(len(ram), 0, "the ram is spent on the connect")
        self.assertLess(bt.hp, hp0 - 500, "a charged connect lands 573")

    def test_charge_gallop_doubles_pace(self):
        env = _quiet(seed=61)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "prince", 11), 0.30, 0.62)
        pr = [u for u in env.eng.units if u.team == 0][-1]
        _tick(env, 2)
        y_a = pr.y
        _tick(env, 1)                                    # still walking (run-up not armed)
        walk_rate = (y_a - pr.y) * 32.0
        _tick(env, 2)                                    # armed by now
        y_b = pr.y
        _tick(env, 1)
        gallop_rate = (y_b - pr.y) * 32.0
        self.assertGreater(gallop_rate, walk_rate * 1.5,
                           "an armed charge runs at double pace (%.2f vs %.2f t/s)"
                           % (gallop_rate, walk_rate))

    def test_balloon_bomb_fuses_three_seconds_and_knocks(self):
        env = _quiet(seed=62)
        _silence_towers(env)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.50, 0.62)
        kn = [u for u in env.eng.units if u.team == 1][-1]
        kn.stun_left = 9.0                               # pinned under the bomb; a WALKING unit
        assert env.eng.deploy(0, build_spec(env.eng.db, "balloon", 11), 0.50, 0.60)   # escapes it
        loon = [u for u in env.eng.units if u.team == 0][-1]
        _tick(env, 2)
        loon.x, loon.y = kn.x, kn.y - 0.02               # shot down right over the knight
        loon.hp = -1.0                                   # shot down over the knight
        _tick(env, 1)
        self.assertGreater(kn.hp, kn.spec.hp - 60, "no damage while the fuse burns")
        y0 = kn.y
        _tick(env, 3)
        self.assertLess(kn.hp, kn.spec.hp - 180, "the 240 bomb lands after ~3 s")
        self.assertGreater(abs(kn.y - y0), 0.004, "and shoves the victim away")

    def test_giant_skeleton_bomb_doubles_on_towers(self):
        env = _quiet(seed=63)
        env.eng.elixir[0] = 10.0
        tw = env.eng.towers[1][0]
        hp0 = tw.hp
        assert env.eng.deploy(0, build_spec(env.eng.db, "giant_skeleton", 11), tw.x, tw.y + 0.02)
        gs = [u for u in env.eng.units if u.team == 0][-1]
        _tick(env, 1)
        gs.hp = -1.0
        _tick(env, 4)
        self.assertLess(tw.hp, hp0 - 1200, "688 doubles to 1376 against a crown tower")

    def test_demolisher_keeps_hp_then_enrages_and_detonates(self):
        env = _quiet(seed=64)
        _silence_towers(env)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "goblin_demolisher", 11), 0.70, 0.30)
        dm = [u for u in env.eng.units if u.team == 1][-1]
        _tick(env, 4)
        self.assertAlmostEqual(dm.hp, dm.spec.hp, delta=1.0,
                               msg="no lifetime bleed before the dynamite is lit")
        dm.hp = dm.spec.hp * 0.45
        hp0 = env.eng.towers[0][0].hp
        _tick(env, 1)
        self.assertTrue(dm.enraged, "below half he lights the fuse")
        self.assertTrue(dm.spec.building_only and dm.spec.kamikaze,
                        "and becomes a building-charging bomb")
        _tick(env, 12)
        self.assertLessEqual(dm.hp, 0.0, "connect or fuse: either way he detonates")
        self.assertLess(min(env.eng.towers[0][0].hp, env.eng.towers[0][1].hp), hp0,
                        "the run ends on whichever of our towers was nearest")

    def test_wall_breaker_blast_splashes_troops(self):
        env = _quiet(seed=65)
        _silence_towers(env)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "bomb_tower", 11), 0.30, 0.60)
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.315, 0.615)
        kn = [u for u in env.eng.units if u.team == 1][-1]
        assert env.eng.deploy(0, build_spec(env.eng.db, "wall_breakers", 11), 0.30, 0.72)
        _tick(env, 8)
        self.assertLess(kn.hp, kn.spec.hp - 250,
                        "the barrel blast is AREA (1.5): bystanders take it too")

    def test_evo_cannon_barrage_rings_land_once(self):
        env = _quiet(seed=66)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.43)
        kn = [u for u in env.eng.units if u.team == 0][-1]
        assert env.eng.deploy(1, build_spec(env.eng.db, "cannon_evo", 11), 0.50, 0.35)
        env.eng.advance(0.5)
        self.assertAlmostEqual(kn.hp, kn.spec.hp, delta=1.0, msg="rings are still in the air")
        env.eng.advance(0.7)
        loss = kn.spec.hp - kn.hp
        self.assertGreater(loss, 250, "the barrage lands ~1 s after placement")
        self.assertLess(loss, 400, "overlapping rings damage a target ONCE (304, not 608)")

    def test_walker_paths_around_stopped_ally(self):
        env = _quiet(seed=67)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "bomb_tower", 11), 0.50, 0.42)
        assert env.eng.deploy(0, build_spec(env.eng.db, "musketeer", 11), 0.50, 0.60)
        mk = [u for u in env.eng.units if u.team == 0][-1]
        _tick(env, 3)                                    # she settles in and starts firing
        y_firing = mk.y
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.66)
        _tick(env, 4)
        self.assertLess(abs(mk.y - y_firing), 0.012,
                        "the knight walks AROUND her instead of bulldozing her forward")

    def test_tower_windup_is_paid_once_not_per_kill(self):
        """A tower's opening delay is the weapon coming UP, not a per-corpse tax.

        The lock breaks when a target dies, and re-acquiring used to reset reload_left to the full
        first_hit -- discarding whatever cooldown had already elapsed. Because the tower fires a
        TRAVELLING shot, the body dies ~0.25 s after the shot is loosed, so every kill threw away
        that quarter second: five Bats cost the tower a full extra second, and it read as much
        slower than the real princess (user-reported 2026-08-16). Real behaviour is that once the
        weapon is up it stays up while there is anything in range.
        """
        env = _quiet(seed=91)
        tw = env.eng.towers[0][0]
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "bats", 11), tw.x, tw.y - 5.0 / 32.0)
        n0 = len([u for u in env.eng.units if u.team == 1])
        self.assertGreaterEqual(n0, 4, "need a real swarm for this test")
        t0 = env.eng.t
        for _ in range(1200):
            env.eng.advance(0.05)
            if not [u for u in env.eng.units if u.team == 1 and u.hp > 0]:
                break
        clear = env.eng.t - t0
        # wind-up once + (n0-1) ordinary shots + flight, with slack for deploy and travel
        budget = tw.first_hit + (n0 - 1) * tw.hit_speed + 2.2
        self.assertLess(clear, budget,
                        "%d bats took %.2fs; a per-kill wind-up would cost ~%.2fs more"
                        % (n0, clear, (n0 - 1) * tw.first_hit))

    def test_bomb_tower_shots_do_not_shove_only_its_death_bomb(self):
        """Its shells land for area damage; the shove belongs to the bomb it drops on death.

        One knockback_tiles field drove both, so every lobbed shell pushed the push back and the
        tower defended far better than the real one (user, 2026-08-16).
        """
        env = _quiet(seed=5)
        spec = build_spec(env.eng.db, "bomb_tower", 11)
        self.assertEqual(spec.knockback, 0.0, "shots must not carry knockback")
        self.assertGreater(spec.death_knockback, 0.0, "the death bomb must still shove")
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "bomb_tower", 11), 0.50, 0.42)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.50)
        kn = [u for u in env.eng.units if u.team == 0][-1]
        for _ in range(20):
            env.eng.advance(0.1)
        shoves, prev = 0, kn.y
        for _ in range(80):
            env.eng.advance(0.1)
            if kn.hp <= 0:
                break
            if kn.y - prev > 0.004:          # pushed AWAY from the tower
                shoves += 1
            prev = kn.y
        self.assertEqual(shoves, 0, "bomb-tower shells must not push the knight back")

    def test_hog_pushes_ice_golem_but_bandit_cannot_push_golem(self):
        env = _quiet(seed=68)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "ice_golem", 11), 0.30, 0.60)
        solo = [u for u in env.eng.units if u.team == 0][-1]
        _tick(env, 4)
        solo_prog = 0.60 - solo.y
        env2 = _quiet(seed=68)
        env2.eng.elixir[0] = 10.0
        assert env2.eng.deploy(0, build_spec(env2.eng.db, "ice_golem", 11), 0.30, 0.60)
        ig = [u for u in env2.eng.units if u.team == 0][-1]
        assert env2.eng.deploy(0, build_spec(env2.eng.db, "hog_rider", 11), 0.30, 0.66)
        _tick(env2, 4)
        pushed_prog = 0.60 - ig.y
        self.assertGreater(pushed_prog, solo_prog * 1.1,
                           "a fast heavy Hog shoves the Ice Golem up the lane")


if __name__ == "__main__":
    unittest.main(verbosity=1)


class ChargeResetTests(unittest.TestCase):
    def test_log_hit_disarms_a_charging_prince(self):
        env = _quiet(seed=72)
        _silence_towers(env)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "prince", 11), 0.30, 0.70)
        pr = [u for u in env.eng.units if u.team == 0][-1]
        _tick(env, 5)                                    # well past 2.5 tiles: armed and galloping
        self.assertGreaterEqual(pr.charge_dist, pr.spec.charge_range, "run-up armed")
        assert env.eng.deploy(1, build_spec(env.eng.db, "the_log", 11), pr.x, max(0.52, pr.y - 0.08))
        dists = []
        for _ in range(3):                               # sample around the roll landing: he starts
            _tick(env, 1)                                # RE-EARNING tiles immediately, so the dip
            dists.append(pr.charge_dist)                 # below charge_range is the reset itself
        self.assertLess(min(dists), pr.spec.charge_range,
                        "a Log hit drops the charge: back to walking pace, tiles earned again")

    def test_zap_class_stun_disarms_a_charge_too(self):
        env = _quiet(seed=73)
        _silence_towers(env)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "prince", 11), 0.30, 0.70)
        pr = [u for u in env.eng.units if u.team == 0][-1]
        _tick(env, 5)
        self.assertGreaterEqual(pr.charge_dist, pr.spec.charge_range)
        assert env.eng.deploy(1, build_spec(env.eng.db, "zap", 11), pr.x, pr.y)
        _tick(env, 2)
        self.assertLess(pr.charge_dist, pr.spec.charge_range,
                        "a stun resets the run-up, same as knockback")


class RoyalGiantPin(unittest.TestCase):
    """User check 2026-08-15: RG is a RANGED building-targeting wincon in popular ladder
    decks. Verified correct in-engine (stops at 4.94 vs reach 5.0, shells the tower, ignores
    a knight standing on him) -- pinned here so it can never silently regress."""

    def test_rg_shells_towers_from_range_and_ignores_troops(self):
        from clashrl.sim.engine import _gap
        env = _quiet(seed=80)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "royal_giant", 11), 0.30, 0.55)
        rg = [u for u in env.eng.units if u.team == 1][-1]
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.30, 0.58)
        kn = [u for u in env.eng.units if u.team == 0][-1]
        tw = env.eng.towers[0][0]
        hp0 = tw.hp
        _tick(env, 14)
        self.assertGreater(_gap(rg.x, rg.y, tw), 3.0,
                           "he sieges from RANGE, never walks to the wall")
        self.assertLess(tw.hp, hp0 - 900, "and the cannon shots land on the tower")
        self.assertAlmostEqual(kn.hp, kn.spec.hp, delta=1.0,
                               msg="a troop standing ON him takes nothing: buildings only")


class RocketRefereeTests(unittest.TestCase):
    """2026-08-15: rocket sat at 0 plays across two greedy evals with a clean logit row --
    the referee was charging threat_miss (-1.0) for every defensive rocket on a non-swarm
    push. Damage spells are exempt from the misread penalty (their worth is priced by the
    trade ledger + chip; spell_waste still bills empty casts), same logic as the pull-spell
    exemption that saved tornado."""

    def test_defensive_damage_spell_on_tank_push_is_not_a_misread(self):
        """The spell is picked by ROLE, not by name: icebow answers with the Rocket and hogeq
        with the Earthquake, and the rule under test -- damage spells are exempt from the
        misread penalty -- is the same rule in both decks."""
        from clashrl.sim.engine import build_spec
        env = _quiet(seed=5)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "golem", 11), 0.30, 0.55)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "musketeer", 11), 0.32, 0.52)
        env.step((False, 0, 0))
        tx, _ = env._threat_pos()
        env._threat_credits = 0
        r = env._threat_response(a_damage_spell(env), tx, 0.60)
        self.assertEqual(r, 0.0, "a damage spell is judged by the trade ledger, never -1.0")

    def test_wrong_role_troop_is_still_a_misread(self):
        """Same rule, other side: a troop that cannot reach a flying threat is still a misread.
        icebow picks the Knight here, hogeq the Hog Rider -- whichever ground-only troop it holds."""
        from clashrl.sim.engine import build_spec
        env = _quiet(seed=8)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "balloon", 11), 0.30, 0.55)
        env.step((False, 0, 0))
        env._threat_id_true[7] = 0.40                    # inside the depth window
        tx, _ = env._threat_pos()
        env._threat_credits = 0
        r = env._threat_response(a_ground_only_troop(env), tx, 0.60)
        self.assertLess(r, 0.0, "a ground-only troop against a flying threat stays a misread")


@requires_cards("rocket", why="end-to-end Rocket value (clump vs swarm payout)")
class RocketValueTests(unittest.TestCase):
    """The pull toward good rockets, end-to-end (real env.step -> flight -> deaths ->
    ledger): meaty clumps pay big, swarms pay little, nothing punishes the attempt."""

    def _scene(self, victims, card_key, seed):
        env = _quiet(seed=seed)
        _silence_towers(env)
        slot = env.slot_of[env.deck_keys.index(card_key)]
        env.cycle.remove(slot)
        env.cycle.insert(0, slot)                        # force the card into hand
        for vk, vx, vy in victims:
            env.eng.elixir[1] = 10.0
            assert env.eng.deploy(1, build_spec(env.eng.db, vk, 11), vx, vy)
        env.step((False, 0, 0))
        env.eng.elixir[0] = 10.0
        env.step((True, env.deck_keys.index(card_key), 13 * 18 + 9))
        _tick(env, 5)
        t = env.rw_stats.run.get("elixir_trade")
        m = env.rw_stats.run.get("threat_response")
        return (t.total if t else 0.0), (m.total if m else 0.0)

    def test_rocket_on_meaty_clump_pays_big(self):
        tr, miss = self._scene([("three_musketeers", 0.50, 0.57)], "rocket", 21)
        self.assertGreater(tr, 0.7, "9 elixir of musketeers under one rocket = a ton of value")
        self.assertGreaterEqual(miss, 0.0, "and the referee never bills the attempt")

    def test_rocket_on_swarm_pays_little(self):
        tr_big, _ = self._scene([("three_musketeers", 0.50, 0.57)], "rocket", 22)
        tr_swarm, _ = self._scene([("skeleton_army", 0.50, 0.57)], "rocket", 23)
        self.assertLess(tr_swarm, tr_big * 0.4,
                        "skarmy under a rocket is a fraction of the clump payout — "
                        "the log/ice-wiz opportunity cost does the rest")


class TowerContactTests(unittest.TestCase):
    """2026-08-15 (user report): the Battle Ram connected to a crown tower and just sat there
    until the tower killed it. Cause: reach is published attacker-CENTRE to target-EDGE, but
    tower separation holds a ground body at its OWN radius -- so any unit with radius > reach
    could never satisfy the range test against a tower (ram 0.50 vs 0.75, giant skeleton 0.80
    vs 1.00). Building UNITS hid it because they grant _REACH_SLOP."""

    def _ram_scene(self, seed):
        env = _quiet(seed=seed)
        _silence_towers(env)
        env.eng.elixir[1] = 10.0
        tw = env.eng.towers[0][0]
        assert env.eng.deploy(1, build_spec(env.eng.db, "battle_ram", 11), tw.x, 0.68)
        return env, tw

    def test_ram_breaks_on_its_FIRST_tower_hit(self):
        env, tw = self._ram_scene(91)
        hp0 = tw.hp
        hit_t = barb_t = None
        for _ in range(90):
            env.eng.advance(0.1)
            if hit_t is None and tw.hp < hp0:
                hit_t = env.eng.t
            if barb_t is None and any(u.team == 1 and u.spec.base == "barbarians"
                                      for u in env.eng.units):
                barb_t = env.eng.t
            if hit_t and barb_t:
                break
        self.assertIsNotNone(hit_t, "the ram must actually strike the crown tower")
        self.assertIsNotNone(barb_t, "and break open when it does")
        self.assertAlmostEqual(barb_t, hit_t, delta=0.15,
                               msg="Barbarians drop ON the first hit, not when the ram dies")
        self.assertFalse(any(u.team == 1 and u.spec.base == "battle_ram" for u in env.eng.units),
                         "the ram is spent on the connect")
        self.assertEqual(sum(1 for u in env.eng.units
                             if u.team == 1 and u.spec.base == "barbarians"), 2)

    def test_giant_skeleton_can_hit_a_tower(self):
        env = _quiet(seed=92)
        _silence_towers(env)
        env.eng.elixir[1] = 10.0
        tw = env.eng.towers[0][0]
        hp0 = tw.hp
        assert env.eng.deploy(1, build_spec(env.eng.db, "giant_skeleton", 11), tw.x, 0.68)
        for _ in range(60):
            env.eng.advance(0.1)
        self.assertLess(tw.hp, hp0, "a body pressed against the tower must be able to swing")


class BuildingStackTests(unittest.TestCase):
    """2026-08-15 (user report): buildings could be placed inside each other -- unit separation
    explicitly skips building/building pairs (both are anchored), so two Teslas on one tile
    co-existed and doubled a single footprint's DPS. Real CR snaps the placement instead."""

    def test_repeat_placements_never_overlap(self):
        from clashrl.sim.engine import _dist
        env = _quiet(seed=95)
        tesla = build_spec(env.eng.db, "tesla", 11)
        pts = []
        for _ in range(4):
            env.eng.elixir[0] = 10.0
            assert env.eng.deploy(0, tesla, 0.50, 0.70)      # the SAME spot every time
            u = [x for x in env.eng.units if x.team == 0][-1]
            pts.append((u.x, u.y))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                self.assertGreaterEqual(_dist(*pts[i], *pts[j]), 2 * tesla.radius - 1e-6,
                                        "two buildings must never share a footprint")

    def test_building_snaps_off_a_crown_tower(self):
        from clashrl.sim.engine import _dist
        env = _quiet(seed=96)
        tesla = build_spec(env.eng.db, "tesla", 11)
        tw = env.eng.towers[0][0]
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, tesla, tw.x, tw.y)          # right on top of our princess
        u = [x for x in env.eng.units if x.team == 0][-1]
        self.assertGreaterEqual(_dist(u.x, u.y, tw.x, tw.y), tesla.radius + tw.radius - 1e-6)

    def test_snap_stays_on_its_own_side_of_the_river(self):
        env = _quiet(seed=97)
        xbow = build_spec(env.eng.db, "x_bow", 11)
        for _ in range(3):
            env.eng.elixir[0] = 10.0
            assert env.eng.deploy(0, xbow, 0.50, 0.53)       # just behind the river, stacked
        for u in [x for x in env.eng.units if x.team == 0]:
            self.assertGreater(u.y, 0.5, "a snap must never push a building across the river")


    def test_troops_never_spawn_inside_a_building(self):
        from clashrl.sim.engine import _dist
        env = _quiet(seed=98)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "tesla", 11), 0.50, 0.70)
        tes = [u for u in env.eng.units if u.team == 0][-1]
        for card in ("knight", "skeletons"):
            env.eng.elixir[0] = 10.0
            assert env.eng.deploy(0, build_spec(env.eng.db, card, 11), 0.50, 0.70)  # right ON it
            for u in [x for x in env.eng.units if x.spec.base == card]:
                self.assertGreaterEqual(_dist(u.x, u.y, tes.x, tes.y),
                                        u.spec.radius + tes.spec.radius - 1e-6,
                                        "%s spawned inside the tesla's footprint" % card)

    def test_spawner_children_still_pop_out_at_their_spawner(self):
        env = _quiet(seed=99)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "tombstone", 11), 0.30, 0.40)
        ts = [u for u in env.eng.units if u.team == 1][-1]
        _tick(env, 8)
        skels = [u for u in env.eng.units if u.team == 1 and u.spec.base == "skeletons"]
        self.assertTrue(skels, "the tombstone must still produce skeletons")


    def _submerged_tesla(self, seed):
        env = _quiet(seed=seed)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "tesla", 11), 0.50, 0.70)
        tes = [u for u in env.eng.units if u.team == 0][-1]
        for _ in range(30):
            env.eng.advance(0.1)                     # nothing to shoot -> it retracts
        assert tes.hidden, "the tesla should be submerged with no enemies around"
        return env, tes

    def test_troops_deploy_onto_and_walk_over_a_submerged_tesla(self):
        from clashrl.sim.engine import _dist
        env, tes = self._submerged_tesla(101)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.70)
        kn = [u for u in env.eng.units if u.spec.base == "knight"][-1]
        self.assertLess(_dist(kn.x, kn.y, tes.x, tes.y), kn.spec.radius + tes.spec.radius,
                        "underground: the placement is NOT snapped away")
        for _ in range(10):
            env.eng.advance(0.1)
        self.assertLess(_dist(kn.x, kn.y, tes.x, tes.y), kn.spec.radius + tes.spec.radius,
                        "and the collision pass does not shove it off either")

    def test_a_second_building_still_snaps_off_a_submerged_tesla(self):
        from clashrl.sim.engine import _dist
        env, tes = self._submerged_tesla(102)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "tesla", 11), 0.50, 0.70)
        t2 = [u for u in env.eng.units if u.spec.base == "tesla"][-1]
        self.assertGreaterEqual(_dist(t2.x, t2.y, tes.x, tes.y), 2 * tes.spec.radius - 1e-6,
                                "the ground is still occupied for another STRUCTURE")

    def test_a_risen_tesla_blocks_normally(self):
        from clashrl.sim.engine import _dist
        env, tes = self._submerged_tesla(103)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.50, 0.60)
        for _ in range(20):
            env.eng.advance(0.1)                     # an enemy is near -> it pops up
        self.assertFalse(tes.hidden, "an enemy in range brings the tesla up")
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), tes.x, tes.y)
        kn = [u for u in env.eng.units if u.team == 0 and u.spec.base == "knight"][-1]
        self.assertGreaterEqual(_dist(kn.x, kn.y, tes.x, tes.y),
                                kn.spec.radius + tes.spec.radius - 1e-6,
                                "above ground it blocks placement like any building")


class AirReachabilityTests(unittest.TestCase):
    """2026-08-16 (user report): "the model tried logging air cards". The counter table said
    that was correct -- only the air-defence branch tested the flying bit, so the SWARM branch
    (splash OR spell) credited THE LOG against a flying swarm. The referee was paying for it."""

    def setUp(self):
        import numpy as np
        from clashrl import card_threat
        self.ct = card_threat
        self.env = _quiet(seed=120)
        self.flying = np.zeros(card_threat.IDENTITY_DIM, np.float32)
        self.flying[0] = self.flying[2] = self.flying[3] = 1.0     # present, swarm, FLYING
        self.ground = self.flying.copy()
        self.ground[3] = 0.0

    def _prof(self, key):
        return self.env._deck_profiles[self.env.deck_keys.index(key)]

    def test_log_does_not_counter_a_flying_swarm(self):
        self.assertFalse(self.ct.counters(self._prof("the_log"), self.flying),
                         "the log cannot touch air and must never be credited against it")

    def test_log_still_counters_a_ground_swarm(self):
        self.assertTrue(self.ct.counters(self._prof("the_log"), self.ground),
                        "skeletons/goblins on the ground are exactly what the log is for")

    def test_air_capable_cards_still_counter_air(self):
        """Was a hard-coded icebow card list. Now every card THIS deck holds whose profile says
        it reaches air must be credited against a flying swarm -- which is both deck-agnostic
        and strictly wider coverage than the four names it replaces.

        MEASURED across both decks (21 deck identities): `counters(profile, flying)` agrees with
        `profile.attacks_air` for every single one, so the invariant is exact, not approximate."""
        air = [k for k in self.env.deck_keys if self.ct.profile(self.env.db, k).attacks_air]
        self.assertTrue(air, "a deck with no air answer at all would be a deck bug")
        for key in air:
            self.assertTrue(self.ct.counters(self._prof(key), self.flying),
                            "%s reaches air and must still count" % key)

    def test_ground_only_troops_never_counter_air(self):
        """The other half of the same invariant, over this deck's own ground-only cards."""
        ground = [k for k in self.env.deck_keys if not self.ct.profile(self.env.db, k).attacks_air]
        self.assertTrue(ground, "a deck with no ground-only card would make this test vacuous")
        for key in ground:
            self.assertFalse(self.ct.counters(self._prof(key), self.flying),
                             "%s cannot hit air" % key)

    def test_lightning_and_poison_are_air_capable(self):
        for key in ("lightning", "poison"):
            self.assertTrue(self.ct.profile(self.env.db, key).attacks_air,
                            "%s is an air-targeting spell (wiki); the imported row said otherwise" % key)


class BarrelTimingTests(unittest.TestCase):
    """The two barrels work differently and both reward log timing (2026-08-16, user request).

    GOBLIN BARREL is a SPELL: the barrel is a projectile with no hitbox or health in flight,
    thrown from the King's Tower, and the Goblins only exist once it lands (+ their deploy).
    SKELETON BARREL is an air TROOP that flies at a building and breaks on arrival or death --
    and the wiki is explicit that for 0.5 s afterwards "neither the Barrel nor the Skeletons are
    considered as entities", so a spell cast into that window hits nothing at all."""

    def test_goblin_barrel_flight_scales_with_throw_distance(self):
        prev = 0.0
        for ty in (0.30, 0.55, 0.80):
            env = _quiet(seed=210)
            env.eng.elixir[1] = 10.0
            assert env.eng.deploy(1, build_spec(env.eng.db, "goblin_barrel", 11), 0.30, ty)
            flight = env.eng.spells[-1].t
            self.assertGreater(flight, prev, "a barrel thrown further must take longer to land")
            prev = flight
        self.assertGreater(prev, 0.5, "and the far throw is a real, readable window")

    def test_goblin_barrel_goblins_do_not_exist_during_the_flight(self):
        env = _quiet(seed=211)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "goblin_barrel", 11), 0.25, 0.72)
        env.eng.advance(0.2)
        self.assertEqual(sum(1 for u in env.eng.units if u.spec.base == "goblins"), 0,
                         "in flight the barrel is a projectile -- nothing to hit yet")
        for _ in range(20):
            env.eng.advance(0.1)
        self.assertEqual(sum(1 for u in env.eng.units if u.spec.base == "goblins"), 3,
                         "and three Goblins arrive once it lands")

    def test_a_log_thrown_too_early_misses_the_goblins(self):
        def trial(delay):
            env = _quiet(seed=212)
            _silence_towers(env)
            env.eng.elixir[1] = 10.0
            assert env.eng.deploy(1, build_spec(env.eng.db, "goblin_barrel", 11), 0.25, 0.70)
            t0, thrown = env.eng.t, False
            for _ in range(60):
                env.eng.advance(0.1)
                if not thrown and env.eng.t - t0 >= delay:
                    env.eng.elixir[0] = 10.0
                    env.eng.deploy(0, build_spec(env.eng.db, "the_log", 11), 0.25, 0.76)
                    thrown = True
            return sum(1 for u in env.eng.units if u.spec.base == "goblins" and u.hp > 0)
        self.assertEqual(trial(0.3), 3, "logging while the barrel is still high hits nothing")
        self.assertEqual(trial(0.9), 0, "timed to land as they spawn, it clears all three")

    def test_skeleton_barrel_has_a_limbo_where_nothing_is_hittable(self):
        env = _quiet(seed=213)
        _silence_towers(env)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "skeleton_barrel", 11), 0.30, 0.60)
        barrel = [u for u in env.eng.units if u.team == 1][-1]
        barrel.hp = -1.0                                  # shot down
        env.eng.advance(0.1)
        self.assertFalse(any(u.spec.base == "skeleton_barrel" for u in env.eng.units),
                         "the barrel is gone")
        self.assertEqual(sum(1 for u in env.eng.units if u.spec.base == "skeletons"), 0,
                         "and for 0.5s NOTHING exists -- a spell cast here affects nothing")
        for _ in range(6):
            env.eng.advance(0.1)
        self.assertEqual(sum(1 for u in env.eng.units if u.spec.base == "skeletons"), 7,
                         "then seven Skeletons appear in a circle")
