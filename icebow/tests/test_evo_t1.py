"""T1 evolution mechanics (2026-08-14 batch): Evo Royal Giant recoil, Evo Skeletons
spawn-on-hit, Evo Recruits shield-gated charge, Evo Barbarians self-rage, Evo Valkyrie
whirlwind, Evo Zap growing triple pulse, Evo PEKKA kill-heal, Evo Skeleton Barrel 75% drop.
Each test pins the wiki-swept numbers so a stat drift or a mechanic regression fails loudly."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(SRC), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_sim_status_effects import _make_engine
from clashrl.sim.engine import _TILES_X, _TILES_Y, build_spec


class EvoT1Tests(unittest.TestCase):
    def test_royal_giant_recoil(self):
        eng = _make_engine()
        rg = build_spec(eng.db, "royal_giant_evo", 11)
        self.assertAlmostEqual(rg.recoil_dmg, 81.0, delta=1)   # USER-VERIFIED at level 11
        self.assertEqual(rg.recoil_r, 2.5)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, rg, 0.50, 0.55))
        giant = [u for u in eng.units if u.team == 1][-1]
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.58))
        kn = [u for u in eng.units if u.team == 0][-1]
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "mega_minion", 11), 0.55, 0.55))
        air = [u for u in eng.units if u.team == 0][-1]
        drops_kn = drops_air = 0
        for _ in range(160):                       # 8 s: he walks at the tower and fires
            pk, pa = kn.hp, air.hp
            eng.advance(0.05)
            if pk - kn.hp > 60:                    # recoil blast is 81 (user-verified)
                drops_kn += 1
            if pa - air.hp > 60:
                drops_air += 1
        self.assertGreaterEqual(drops_kn, 1, "ground knight must eat recoil blasts")
        self.assertEqual(drops_air, 0, "air is immune to the recoil")

    def test_skeletons_spawn_on_hit_cap(self):
        eng = _make_engine()
        sk = build_spec(eng.db, "skeletons_evo", 11)
        self.assertEqual(sk.spawn_on_hit_cap, 8)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, sk, 0.50, 0.55))     # 3 evo skeletons
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.58))
        peak = 0
        for _ in range(120):                                # plenty of swings
            eng.advance(0.1)
            n = sum(1 for u in eng.units if u.team == 1 and u.hp > 0
                    and u.spec.key == "skeletons_evo")
            self.assertLessEqual(n, 8, "cap is a MAXIMUM total of 8")
            peak = max(peak, n)
        # peak, not final: once the knight dies they stop swinging (no spawns) and the
        # tower grinds the marchers down -- the growth happened mid-fight.
        self.assertGreater(peak, 3, "landed swings must have spawned extra evo skeletons")

    def _recruit_first_hit(self, break_shields: bool) -> float:
        eng = _make_engine()
        rr = build_spec(eng.db, "royal_recruits_evo", 11)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, rr, 0.50, 0.46))
        squad = [u for u in eng.units if u.team == 1]
        # ONE recruit only. The measurement is a per-tick HP delta, and since the allied-flow
        # pathing fix (2026-08-19) the squad genuinely arrives TOGETHER -- two simultaneous
        # normal swings (2 x 133 = 266) are numerically identical to one charge hit (266), so
        # the multi-body version of this probe cannot distinguish the thing it exists to test.
        # Isolating one body restores the unambiguous reading without touching the doctrine.
        keep = min(squad, key=lambda u: abs(u.x - 0.50))   # the CENTRE recruit: the line spawns
        for u in squad:                                     # wide, and an edge body wanders tiles
            if u is not keep:                               # before meeting the knight mid-board
                u.hp = 0.0
        squad = [keep]
        if break_shields:
            for u in squad:
                u.shield_left = 0.0
        # The knight walks TOWARD the recruits, so he starts 5.8 tiles out -- each side covers
        # ~2.9, comfortably past the 2.5-tile charge run-up (a 3.8-tile gap left them at ~1.9).
        eng.elixir = [10.0, 10.0]
        # SAME LANE AS THE SURVIVING RECRUIT. The probe isolates ONE body, and since the recruits
        # spawn in their real arena-spanning line that body is no longer at x=0.50 -- the centre of
        # a 6-wide line at 3-tile spacing sits ~1.5 tiles off. Dropping the knight at a fixed 0.50
        # meant the two never met inside the window.
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), keep.x, 0.64))
        kn = [u for u in eng.units if u.team == 0][-1]
        # ATTRIBUTE THE DAMAGE. "First HP drop over 50" is not the same as "a recruit hit him":
        # a Princess Tower swing is 157.6 and its range is ~7.5 tiles, so a knight that drifts into
        # tower range on his way to the recruit registers 3 tower hits (464.2) and the probe reads
        # it as a recruit landing 464. That is exactly what happened when the recruits went from a
        # 1.1-tile huddle to their real arena-spanning line: the surviving centre body sits 1.5
        # tiles off the knight's lane, so he meets a tower first. Require the recruit to actually
        # be in reach before believing the number.
        for _ in range(240):
            prev = kn.hp
            eng.advance(0.05)
            if prev - kn.hp > 50:
                r = squad[0]
                gap = (((kn.x - r.x) * _TILES_X) ** 2 + ((kn.y - r.y) * _TILES_Y) ** 2) ** 0.5
                if r.hp > 0 and gap <= r.spec.reach + r.spec.radius + kn.spec.radius + 0.6:
                    return prev - kn.hp                      # the first landed RECRUIT swing
        self.fail("no recruit ever landed a hit")

    def test_recruits_charge_only_after_shield(self):
        self.assertAlmostEqual(self._recruit_first_hit(break_shields=False), 133, delta=2)
        self.assertAlmostEqual(self._recruit_first_hit(break_shields=True), 266, delta=2)

    def test_barbarians_self_rage(self):
        eng = _make_engine()
        bb = build_spec(eng.db, "barbarians_evo", 11)
        # I5, R2 LAG bucket: 5 s, not 3. Every available path says 5; the page's own INTRO PROSE
        # ("increases by 30% for 3 seconds") is the stale one, and the curated 3.0 quoted it.
        self.assertEqual((bb.hit_rage_s, bb.hit_rage_boost), (5.0, 0.30))
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, bb, 0.50, 0.55))
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50, 0.60))
        barb = None
        for _ in range(60):
            eng.advance(0.1)
            raged = [u for u in eng.units if u.team == 1 and u.rage_self_left > 0.0]
            if raged:
                barb = raged[0]
                break
        self.assertIsNotNone(barb, "a swing must self-rage the barbarian")
        self.assertAlmostEqual(eng._rage_mult(barb), 1.30, places=6)
        barb.x, barb.y = 0.10, 0.20                          # drag him away from everything
        for _ in range(60):                                  # > the I5-corrected 5 s window
            eng.advance(0.1)
        self.assertEqual(barb.rage_self_left, 0.0, "rage must expire 5 s after the last swing")

    def test_valkyrie_whirlwind(self):
        eng = _make_engine()
        vk = build_spec(eng.db, "valkyrie_evo", 11)
        self.assertEqual((vk.attack_nado_r, vk.attack_nado_s), (5.5, 0.5))
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, vk, 0.50, 0.55))
        valk = [u for u in eng.units if u.team == 1][-1]
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "knight", 11), 0.50, 0.575))
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "mega_minion", 11), 0.50, 0.68))
        air = [u for u in eng.units if u.team == 0][-1]
        d0 = ((air.x - valk.x) ** 2 * 18 ** 2 + (air.y - valk.y) ** 2 * 32 ** 2) ** 0.5
        hp0 = air.hp
        saw_vortex = False
        for _ in range(60):
            eng.advance(0.05)
            saw_vortex = saw_vortex or bool(eng.vortices)
        d1 = ((air.x - valk.x) ** 2 * 18 ** 2 + (air.y - valk.y) ** 2 * 32 ** 2) ** 0.5
        self.assertTrue(saw_vortex, "her swing must spin up a vortex")
        self.assertLess(d1, d0 - 0.5, "the whirlwind must PULL the air unit toward her")
        self.assertLess(air.hp, hp0, "the whirlwind deals its tornado damage")

    def test_zap_double_pulse(self):
        eng = _make_engine()
        zp = build_spec(eng.db, "zap_evo", 11)
        # I5, R2 LAG bucket, 3-of-3: TWO pulses. 8/10/2024 "increased the second pulse's damage
        # by 100%, but REMOVED THE THIRD PULSE"; dmg_hits = 2 and the infobox says "TWO Zaps".
        # The curated 3 quoted the retired pre-8/10/2024 card text.
        self.assertEqual(zp.zap_pulses, 2)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50, 0.55))
        near = [u for u in eng.units if u.team == 0][-1]
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "x_bow", 11), 0.50 + 3.2 / 18.0, 0.55))
        far = [u for u in eng.units if u.team == 0][-1]
        eng.elixir = [10.0, 10.0]
        # Cast at the near x-bow's SNAPPED position -- troop deploys tile-snap, spells don't,
        # and the 0.1-tile y offset was enough to push the far body just outside the 3.5 ring.
        self.assertTrue(eng.deploy(1, zp, near.x, near.y))
        hits_near = hits_far = 0
        for _ in range(70):                                  # 3.5 s: both pulses
            pn, pf = near.hp, far.hp
            eng.advance(0.05)
            if pn - near.hp > 100:
                hits_near += 1
            if pf - far.hp > 100:
                hits_far += 1
        self.assertEqual(hits_near, 2, "centre body is inside both rings")
        # Tile-snap puts the far body at EXACTLY 3.0 tiles: the 2.5 first ring misses it and the
        # grown 3.0 ring reaches -- one hit, which is still what proves the ring grows at all.
        self.assertEqual(hits_far, 1, "3 tiles out: the first ring misses, the echo reaches")

    def test_pekka_kill_heal_overheal(self):
        eng = _make_engine()
        pk = build_spec(eng.db, "pekka_evo", 11)
        self.assertEqual(pk.hp, 3760.0)                      # imported 5640 was the overheal CAP
        self.assertAlmostEqual(pk.kill_heal, 470.0, delta=1)
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, pk, 0.50, 0.55))
        pekka = [u for u in eng.units if u.team == 1][-1]
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(0, build_spec(eng.db, "skeletons", 11), 0.50, 0.575))
        for _ in range(60):
            eng.advance(0.1)
            if pekka.hp > pk.hp:
                break
        self.assertGreater(pekka.hp, pk.hp, "a kill must OVERHEAL her past deploy hp")
        self.assertLessEqual(pekka.hp, pk.hp * 1.5 + 1)

    def test_skeleton_barrel_evo_two_drops(self):
        eng = _make_engine()
        sb = build_spec(eng.db, "skeleton_barrel_evo", 11)
        self.assertEqual(sb.count, 1)                        # imported 2 was BARRELS carried
        self.assertEqual(sb.hit_dmg, 0.0)
        self.assertEqual(sb.mid_drop_frac, 0.75)
        # I5, R2 PARENT bucket: 190, not 238. P1 (death_11) and P2 (the rendered table + the
        # lead's "64% higher") are ONE 4/8/2025 snapshot, not two witnesses, and two dated 2026
        # nerfs postdate it: 238 * 0.92 * 0.87 = 190.5 -> 190.
        self.assertAlmostEqual(sb.death_dmg, 190.0, delta=1)
        # (a) damaged mid-flight -> first barrel at 75%, second on death: 14 skeletons total
        eng.elixir = [10.0, 10.0]
        self.assertTrue(eng.deploy(1, sb, eng.towers[0][0].x, 0.40))
        barrel = [u for u in eng.units if u.team == 1][-1]
        for _ in range(14):
            eng.advance(0.1)
        barrel.hp = sb.hp * 0.6                              # shot down to 60% -> trigger crosses 75%
        eng.advance(0.1)
        n_mid = sum(1 for u in eng.units if u.team == 1 and u.spec.base == "skeletons")
        self.assertEqual(n_mid, 7, "the 75% barrel drops 7 skeletons mid-flight")
        self.assertTrue(barrel.mid_drop_done)
        barrel.hp = 0.0
        # +0.5 s LIMBO (2026-08-16, wiki): after the barrel breaks, "neither the Barrel nor the
        # Skeletons are considered as entities" -- the death drop's seven arrive only after it.
        for _ in range(8):
            eng.advance(0.1)
        n_all = sum(1 for u in eng.units if u.team == 1 and u.spec.base == "skeletons")
        self.assertEqual(n_all, 14, "death drops the second 7")
        # (b) untouched to the tower -> BOTH barrels at once
        eng2 = _make_engine()
        eng2.elixir = [10.0, 10.0]
        self.assertTrue(eng2.deploy(1, sb, eng2.towers[0][0].x, 0.40))
        b2 = [u for u in eng2.units if u.team == 1][-1]
        for _ in range(300):
            eng2.advance(0.1)
            if b2.hp <= 0:
                break
        self.assertLessEqual(b2.hp, 0.0, "must kamikaze on the tower")
        for _ in range(8):        # +0.5 s LIMBO (2026-08-16) before the bodies exist
            eng2.advance(0.1)
        n2 = sum(1 for u in eng2.units if u.team == 1 and u.spec.base == "skeletons")
        self.assertEqual(n2, 14, "unspent trigger -> both barrels drop at once")


if __name__ == "__main__":
    unittest.main(verbosity=1)
