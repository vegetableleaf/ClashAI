from pathlib import Path
p = Path("C:/Users/benpe/ClashBot/icebow/tests/test_geometry_reward.py")
s = p.read_text(encoding="utf-8")

def rep(old, new):
    global s
    assert s.count(old) == 1, old[:80]
    s = s.replace(old, new)

rep('''        self.assertAlmostEqual(corner["p2_cover"], 0.5)              # left tower only
        self.assertAlmostEqual(corner["p1_pull_band"], 0.75)         # band 1 x (0.5 + 0.5 x 0.5)
        self.assertGreater(centre["p1_pull_band"], corner["p1_pull_band"])
''', '''        self.assertAlmostEqual(corner["p2_cover"], 0.5)              # left tower only
        # L59 path P1 (RAW band, no P2 factor): the corner sits 2.0 - 0.5 = 1.5 tiles beside the
        # bridge -> left-tower line, below lo = 1.8 -> on the ramp: (1.5 - (1.8 - 2.0)) / 2.0 = 0.85.
        # The snapshot band (march gap 2.7 tiles, in band) is still 1.0 -- kept as `p1_snapshot`.
        self.assertAlmostEqual(corner["p1_pull_band"], 0.85)
        self.assertAlmostEqual(corner["p1_snapshot"], 1.0)
        self.assertAlmostEqual(centre["p1_snapshot"], 1.0)
        self.assertGreater(centre["p1_pull_band"], corner["p1_pull_band"])
        # placement_credit re-applies the P2 factor: centre 1.0 x 1.0 vs corner 0.85 x 0.75
        self.assertAlmostEqual(G.placement_credit(centre, "building"), 1.0)
        self.assertAlmostEqual(G.placement_credit(corner, "building"), 0.85 * 0.75)
''')

rep('''        far = score_placement(board, at(TESLA, 5.5, 23.0))           # 2.66 tiles: outside lo = 2.2, still nearer than the tower (4.09)
        self.assertEqual(far["p1_close_penalty"], 0.0)
        self.assertGreater(far["p1_pull_band"], 0.0)
''', '''        far = score_placement(board, at(TESLA, 5.5, 23.0))           # 2.66 tiles: outside lo = 2.2, still nearer than the tower (4.09)
        self.assertEqual(far["p1_close_snapshot"], 0.0)              # snapshot: outside lo, no penalty
        # L59: the brief's close penalty is measured on d_path -- this tile is 1.52 - 0.5 = 1.02 tiles
        # beside the pekka's march line to the left princess, INSIDE lo = 2.2, so it now fires
        # (-(2.2 - 1.02) / 2.2 = -0.536) even though the pekka is 2.66 tiles away. Pinned here so the
        # difference between the two forms is visible (wire.md flags it for the gate rerun).
        self.assertAlmostEqual(far["p1_close_penalty"], -0.536, places=2)
        self.assertGreater(far["p1_pull_band"], 0.0)
''')

rep('''                    for k in G.TERM_KEYS:
                        v = a[k]
                        if k == "d_threat":
                            self.assertGreaterEqual(v, 0.0)
                        elif k in ("p1_close_penalty", "p7_fragility"):
''', '''                    for k in G.TERM_KEYS:
                        v = a[k]
                        if k in ("d_threat", "d_path"):
                            self.assertGreaterEqual(v, 0.0)
                        elif k in ("p1_close_penalty", "p1_close_snapshot", "p7_fragility"):
''')

rep('''class RadiiOneSourceOfTruth(unittest.TestCase):
''', '''ICE_WIZARD = dict(base="ice_wizard", kind="troop", r_atk=5.5, r_sight=5.5, r_body=0.5, deploy_time=1.0,
                  speed=1.0, building_only=False, is_spell=False, spell_radius=0.0, hp=590.0,
                  roles=("splash",))
SKELETONS_ROLED = dict(SKELETONS, roles=("swarm",))


class L59PathP1AndRestrictions(unittest.TestCase):
    """L59 (HANDOFF 5cs.29): path-based P1, P2 buildings-only, P7 not for swarm, credit helpers."""

    def test_a_preplaced_tesla_vs_hog_at_enemy_bridge_approach(self):
        # Hog still on the ENEMY half at own-frame y = 12 (4 tiles short of the left bridge).
        board = Board(objs=towers() + [hog(3.5, 12.0)], team=0)
        s = score_placement(board, at(TESLA, 9.0, 21.0))
        self.assertEqual(s["threat_base"], "hog_rider")
        # snapshot: march gap = 4 (to the bridge) + hypot(5.5, 5) - 0.5 = 10.9 tiles > r_sight 9.5 + w -> 0
        self.assertEqual(s["p1_snapshot"], 0.0)
        # path: the tile is 5.5 - 0.5 = 5.0 tiles beside the bridge -> left-tower segment: in band
        self.assertAlmostEqual(s["d_path"], 5.0)
        self.assertAlmostEqual(s["p1_pull_band"], 1.0)
        self.assertGreater(s["p1_pull_band"], s["p1_snapshot"])
        self.assertEqual(s["p1_close_penalty"], 0.0)

    def test_b_path_p1_at_least_snapshot_for_bridge_hog(self):
        board = Board(objs=towers() + [hog(3.5, 16.0)], team=0)
        s = score_placement(board, at(TESLA, 9.0, 21.0))
        self.assertGreaterEqual(s["p1_pull_band"], s["p1_snapshot"])
        self.assertAlmostEqual(s["p1_pull_band"], 1.0)
        self.assertAlmostEqual(s["p1_snapshot"], 1.0)

    def test_c_p2_is_zero_for_a_skeleton_placement(self):
        board = Board(objs=towers() + [hog(3.5, 16.0)], team=0)
        s = score_placement(board, at(SKELETONS, 3.5, 24.0))       # deep, both-tower cover as a building
        self.assertEqual(s["p2_cover"], 0.0)
        self.assertEqual(score_placement(board, at(TORNADO, 3.5, 20.0))["p2_cover"], 0.0)
        self.assertGreater(score_placement(board, at(TESLA, 3.5, 24.0))["p2_cover"], 0.0)

    def test_d_p7_zero_for_swarm_unchanged_for_ice_wizard(self):
        valk = BoardObj(1, "troop", "valkyrie", *T(4.5, 20.0), 1.2, 5.5, 0.5, 1900, 1900, 4.0, 1.0,
                        splash=True, roles=("tank", "splash"))
        board = Board(objs=towers() + [valk], team=0)
        self.assertEqual(score_placement(board, at(SKELETONS_ROLED, 4.5, 21.0))["p7_fragility"], 0.0)
        # without a role the term still fires (the sim adapter passes roles through `placement_from_spec`)
        self.assertAlmostEqual(score_placement(board, at(SKELETONS, 4.5, 21.0))["p7_fragility"], -1.0)
        iw = score_placement(board, at(ICE_WIZARD, 4.5, 21.0))
        self.assertAlmostEqual(iw["p7_fragility"], -1.0)
        self.assertEqual(score_placement(board, at(ICE_WIZARD, 4.5, 26.0))["p7_fragility"], 0.0)

    def test_e_placement_credit_bounds(self):
        full = {k: 1.0 for k in G.TERM_KEYS}
        full.update(p1_close_penalty=0.0, p7_fragility=0.0)
        self.assertAlmostEqual(G.placement_credit(full, "building"), 1.0)     # P1 + P6 capped at 1.0
        worst = {k: 0.0 for k in G.TERM_KEYS}
        worst.update(p1_close_penalty=-1.0, p7_fragility=-1.0)
        self.assertAlmostEqual(G.placement_credit(worst, "building"), G.CREDIT_FLOOR)
        self.assertAlmostEqual(G.placement_credit(worst, "troop"), 0.0)             # p7 off by default
        self.assertAlmostEqual(G.placement_credit(worst, "troop", p7_enabled=True), G.CREDIT_FLOOR)
        self.assertEqual(G.placement_credit(full, "spell"), 0.0)
        half = dict(worst, p1_pull_band=1.0, p2_cover=0.0)
        self.assertAlmostEqual(G.placement_credit(half, "building"), 0.5 + G.CREDIT_FLOOR)
        self.assertAlmostEqual(G.timing_credit(dict(p5_timing=0.4)), 0.4)
        self.assertAlmostEqual(G.timing_credit(dict(p5_timing=3.0)), 1.0)
        # every hand-board placement lands inside [FLOOR, CAP]
        board = Board(objs=towers() + [hog(3.5, 16.0)], team=0)
        for card, kind in ((TESLA, "building"), (XBOW, "building"), (SKELETONS, "troop"), (TORNADO, "spell")):
            for xt in (1.5, 3.5, 9.0, 14.5, 16.5):
                for yt in (16.0, 18.5, 21.0, 24.0, 28.0):
                    c = G.placement_credit(score_placement(board, at(card, xt, yt)), kind, p7_enabled=True)
                    self.assertTrue(G.CREDIT_FLOOR <= c <= G.CREDIT_CAP, (card["base"], xt, yt, c))

    def test_f_pull_ok_false_behind_the_king(self):
        board = Board(objs=towers() + [hog(3.5, 16.0)], team=0)
        s = score_placement(board, at(TESLA, 9.0, 31.0))            # behind the king vs a left-lane hog
        self.assertEqual(s["p1_pull_band"], 0.0)
        self.assertEqual(s["p1_snapshot"], 0.0)
        # the tile is 5.5 tiles beside the hog's line but the left princess (9.5 march) is nearer
        # than the Tesla (hypot(5.5, 15) - 0.5 = 15.5): pull_ok = 0 zeroes the band
        self.assertAlmostEqual(s["d_path"], 5.0, places=1)

    def test_bridge_block_case_is_full_timing_credit(self):
        board = Board(objs=towers() + [hog(3.5, 14.0)], team=0)
        s = score_placement(board, at(SKELETONS, 3.5, 17.0))
        if s["bridge_block_case"] == 1.0:
            self.assertAlmostEqual(G.timing_credit(s), 1.0)
        self.assertTrue(0.0 <= G.timing_credit(s) <= 1.0)


class RadiiOneSourceOfTruth(unittest.TestCase):
''')

p.write_text(s, encoding="utf-8")
print("tests patched")
