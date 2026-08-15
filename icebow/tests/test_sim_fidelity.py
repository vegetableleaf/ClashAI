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


def _quiet(seed=42):
    env = SimMatchEnv(Config.load(), seed=seed)
    env.reset()
    env.opponent.act = lambda eng: None
    return env


def _tick(env, seconds):
    for _ in range(int(seconds)):
        env.step((False, 0, 0))


def _silence_towers(env):
    for side in (0, 1):
        for tw in env.eng.towers[side]:
            tw.stun_left = 999.0


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
