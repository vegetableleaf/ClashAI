"""L58 step 0: the radius-graded placement geometry (research/RADIUS_REWARD_PROPOSALS.md).

Every case here is a NUMBER the doc states or the brief demands, computed on a hand-built board
so the test says which formula moved, not which engine tick did. The one engine-backed test
checks the adapter (`board_from_engine`) and that the module's tile metric equals `engine._dist`
-- the reward and the `sim-view --radii` overlay both read radii through `radii_of`, so a drift
between the two would be a second source of truth.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl import geometry_reward as G          # noqa: E402
from clashrl.geometry_reward import Board, BoardObj, band, score_placement   # noqa: E402


def T(x_tile: float, y_tile: float):
    """Tile coordinates (18 x 32, team 0 at HIGH y) -> normalised."""
    return x_tile / 18.0, y_tile / 32.0


def towers(left_alive=True, right_alive=True, king_awake=False, enemy_left=True, enemy_right=True):
    """Both sides' towers at the engine's tile-derived anchors (princess (3.5|14.5, 6.5|25.5),
    king (9, 3|29)); dead towers are simply NOT on the board (doc §7.5)."""
    out = []
    for team, py, ky in ((0, 25.5, 29.0), (1, 6.5, 3.0)):
        for x, alive in ((3.5, left_alive if team == 0 else enemy_left),
                         (14.5, right_alive if team == 0 else enemy_right)):
            if alive:
                out.append(BoardObj(team, "tower", "princess", *T(x, py), 8.0, 8.0, 1.5, 4000, 4000,
                                    king=False, active=True, roles=("tower",)))
        out.append(BoardObj(team, "tower", "king", *T(9.0, ky), 8.5, 8.5, 2.0, 7000, 7000,
                            king=True, active=(king_awake if team == 0 else False), roles=("tower",)))
    return out


def hog(x_tile, y_tile):
    return BoardObj(1, "troop", "hog_rider", *T(x_tile, y_tile), 0.8, 9.5, 0.6, 1400, 1400, 4.0, 2.0,
                    building_only=True, roles=("win_condition",))


TESLA = dict(base="tesla", kind="building", r_atk=5.5, r_sight=5.5, r_body=0.5, deploy_time=1.0,
             speed=0.0, building_only=False, is_spell=False, spell_radius=0.0)
XBOW = dict(base="x_bow", kind="building", r_atk=11.5, r_sight=11.5, r_body=0.6, deploy_time=3.5,
            speed=0.0, building_only=False, is_spell=False, spell_radius=0.0, siege=True)
SKELETONS = dict(base="skeletons", kind="troop", r_atk=0.5, r_sight=5.5, r_body=0.5, deploy_time=1.0,
                 speed=1.5, building_only=False, is_spell=False, spell_radius=0.0, hp=81.0)
TORNADO = dict(base="tornado", kind="spell", r_atk=5.5, r_sight=0.0, r_body=0.5, deploy_time=0.0,
               speed=0.0, building_only=False, is_spell=True, spell_radius=5.5, pull_radius=5.5)


def at(card: dict, x_tile: float, y_tile: float) -> dict:
    x, y = T(x_tile, y_tile)
    return dict(card, x=x, y=y)


class BandShape(unittest.TestCase):
    def test_plateau_ramps_and_zero(self):
        self.assertEqual(band(3.0, 2.0, 5.0, 2.0), 1.0)
        self.assertEqual(band(2.0, 2.0, 5.0, 2.0), 1.0)      # edges are inclusive
        self.assertEqual(band(5.0, 2.0, 5.0, 2.0), 1.0)
        self.assertAlmostEqual(band(1.0, 2.0, 5.0, 2.0), 0.5)  # linear ramp below
        self.assertAlmostEqual(band(6.0, 2.0, 5.0, 2.0), 0.5)  # ...and above
        self.assertEqual(band(0.0, 2.0, 5.0, 2.0), 0.0)
        self.assertEqual(band(7.0, 2.0, 5.0, 2.0), 0.0)
        self.assertEqual(band(9.0, 2.0, 5.0, 2.0), 0.0)
        self.assertEqual(band(5.5, 2.0, 5.0, 0.0), 0.0)        # w = 0 -> a hard box
        for x in (0.0, 1.9, 2.0, 3.5, 5.0, 6.1, 8.0):
            self.assertTrue(0.0 <= band(x, 2.0, 5.0, 2.0) <= 1.0)


class P1PullBand(unittest.TestCase):
    """The doc's worked example: hog at the left bridge (3.5, 16); Tesla at the pros' modal
    (9, 21) vs the policy's corner (1.5, 18.5)."""

    def setUp(self):
        self.board = Board(objs=towers() + [hog(3.5, 16.0)], team=0)

    def test_centre_beats_corner(self):
        centre = score_placement(self.board, at(TESLA, 9.0, 21.0))
        corner = score_placement(self.board, at(TESLA, 1.5, 18.5))
        self.assertEqual(centre["threat_base"], "hog_rider")
        self.assertAlmostEqual(centre["p1_pull_band"], 1.0)          # in band, pulled, both towers cover
        self.assertAlmostEqual(centre["p2_cover"], 1.0)
        self.assertAlmostEqual(corner["p2_cover"], 0.5)              # left tower only
        # L59 path P1 (RAW band, no P2 factor): the corner sits 2.0 - 0.5 = 1.5 tiles beside the
        # bridge -> left-tower line, below lo = 1.8 -> on the ramp: (1.5 - (1.8 - 2.0)) / 2.0 = 0.85.
        # The snapshot band (march gap 2.7 tiles, in band) is still 1.0 -- kept as `p1_snapshot`.
        self.assertAlmostEqual(corner["p1_pull_band"], 0.85)
        self.assertAlmostEqual(corner["p1_snapshot"], 1.0)
        self.assertAlmostEqual(centre["p1_snapshot"], 1.0)
        self.assertGreater(centre["p1_pull_band"], corner["p1_pull_band"])
        # placement_credit re-applies the P2 factor: centre 1.0 x 1.0 vs corner 0.85 x 0.75, and the
        # corner also pays the d_path close penalty -(1.8 - 1.5) / 1.8 = -0.167 (hog is melee)
        self.assertAlmostEqual(G.placement_credit(centre, "building"), 1.0)
        self.assertAlmostEqual(corner["p1_close_penalty"], -0.3 / 1.8)
        self.assertEqual(corner["p1_close_snapshot"], 0.0)
        # lead ruling 6.3: the credit charges the SNAPSHOT close penalty (0 here), not the d_path form
        self.assertAlmostEqual(G.placement_credit(corner, "building"), 0.85 * 0.75)
        self.assertEqual(centre["p1_close_penalty"], 0.0)
        self.assertEqual(corner["p1_close_snapshot"], 0.0)          # 2.7 tiles from the hog itself: no snapshot penalty
        # d_threat = gap to the hog's hitbox edge: hypot(5.5, 5) - 0.6 = 6.83 tiles (band 1.8 .. 9.5)
        self.assertAlmostEqual(centre["d_threat"], 6.83, places=1)

    def test_corner_vs_right_lane_hog_is_not_pulled(self):
        board = Board(objs=towers() + [hog(14.5, 16.0)], team=0)
        corner = score_placement(board, at(TESLA, 1.5, 18.5))
        self.assertEqual(corner["p1_pull_band"], 0.0)                # d_march ~13 > 9.5, and the tower is nearer

    def test_close_penalty_tesla_on_pekka(self):
        pekka = BoardObj(1, "troop", "pekka", *T(4.5, 20.0), 1.2, 5.0, 0.75, 3000, 3000, 7.0, 0.75,
                         roles=("tank",))
        board = Board(objs=towers() + [pekka], team=0)
        s = score_placement(board, at(TESLA, 4.5, 20.5))
        self.assertAlmostEqual(s["p1_close_penalty"], -1.0)          # inside r_atk + 1: hit before it shoots
        self.assertEqual(s["p1_pull_band"], 0.0)
        self.assertGreaterEqual(s["p1_close_penalty"], -1.0)         # bounded
        far = score_placement(board, at(TESLA, 5.5, 23.0))           # 2.66 tiles: outside lo = 2.2, still nearer than the tower (4.09)
        self.assertEqual(far["p1_close_snapshot"], 0.0)              # snapshot: outside lo, no penalty
        # L59: the brief's close penalty is measured on d_path -- this tile is 1.52 - 0.5 = 1.02 tiles
        # beside the pekka's march line to the left princess, INSIDE lo = 2.2, so it now fires
        # (-(2.2 - 1.02) / 2.2 = -0.536) even though the pekka is 2.66 tiles away. Pinned here so the
        # difference between the two forms is visible (wire.md flags it for the gate rerun).
        self.assertAlmostEqual(far["p1_close_penalty"], -0.536, places=2)
        self.assertGreater(far["p1_pull_band"], 0.0)
        centre = score_placement(board, at(TESLA, 9.0, 21.0))        # 4.11 tiles, but the L princess is 4.09: NOT pulled
        self.assertEqual(centre["p1_pull_band"], 0.0)

    def test_no_penalty_for_a_ranged_threat(self):
        musk = BoardObj(1, "troop", "musketeer", *T(4.5, 20.0), 6.0, 5.5, 0.5, 700, 700, 4.0, 1.0)
        board = Board(objs=towers() + [musk], team=0)
        s = score_placement(board, at(TESLA, 4.5, 24.0))             # 4 tiles away: inside lo = 7 but not melee
        self.assertEqual(s["p1_close_penalty"], 0.0)


class P3Intercept(unittest.TestCase):
    def test_doc_tiles(self):
        board = Board(objs=towers() + [hog(3.5, 16.0)], team=0)
        modal = score_placement(board, at(SKELETONS, 3.0, 17.0))
        beside = score_placement(board, at(SKELETONS, 5.0, 19.0))
        king_front = score_placement(board, at(SKELETONS, 9.3, 24.1))
        self.assertAlmostEqual(modal["p3_intercept"], 1.0)
        self.assertGreater(beside["p3_intercept"], 0.0)
        self.assertLess(king_front["p3_intercept"], modal["p3_intercept"])
        self.assertLess(king_front["p3_intercept"], 0.5)


class P6Siege(unittest.TestCase):
    """Doc §7.5: dead towers do not exist to this term."""

    def test_dead_princess_scores_zero_and_king_is_in_band(self):
        alive = Board(objs=towers(), team=0)
        s_alive = score_placement(alive, at(XBOW, 3.5, 17.5))       # gap to L princess 9.5: band 8.5 .. 11.5
        self.assertAlmostEqual(s_alive["p6_siege"], 1.0)
        left_dead = Board(objs=towers(enemy_left=False), team=0)
        s_dead = score_placement(left_dead, at(XBOW, 3.5, 17.5))     # nearest ALIVE princess is 14 tiles off
        self.assertEqual(s_dead["p6_siege"], 0.0)
        both_dead = Board(objs=towers(enemy_left=False, enemy_right=False), team=0)
        s_king = score_placement(both_dead, at(XBOW, 9.0, 14.5))     # gap to the king 9.5: band 9.0 .. 11.5
        self.assertAlmostEqual(s_king["p6_siege"], 1.0)
        s_old = score_placement(both_dead, at(XBOW, 3.5, 17.5))      # the old left-reaching tile: gap to king 13.5
        self.assertEqual(s_old["p6_siege"], 0.0)

    def test_centre_bow_is_not_offensive_and_enemy_building_softens(self):
        board = Board(objs=towers(), team=0)
        self.assertEqual(score_placement(board, at(XBOW, 8.5, 22.0))["p6_siege"], 0.0)
        cannon = BoardObj(1, "building", "cannon", *T(3.5, 15.0), 5.5, 5.5, 0.6, 700, 700, 3.0, 0.0)
        under = Board(objs=towers() + [cannon], team=0)
        self.assertEqual(score_placement(under, at(XBOW, 3.5, 17.5))["p6_siege"], 0.0)


class BridgeBlock(unittest.TestCase):
    def test_detected_with_hog_approaching(self):
        board = Board(objs=towers() + [hog(3.5, 12.0)], team=0)      # 4 tiles from the bridge, far side
        s = score_placement(board, at(SKELETONS, 3.5, 16.0))
        self.assertEqual(s["bridge_block_detected"], 1.0)
        self.assertEqual(s["bridge_block_case"], 1.0)                # B1: a hog-role wincon
        self.assertAlmostEqual(s["p5_timing"], 1.0)                  # never penalised for being early
        self.assertAlmostEqual(s["p3_intercept"], 1.0)               # the bridge tile is the intercept

    def test_not_detected_on_a_quiet_board(self):
        s = score_placement(Board(objs=towers(), team=0), at(SKELETONS, 3.5, 16.0))
        self.assertEqual(s["bridge_block_detected"], 0.0)
        self.assertEqual(s["bridge_block_case"], 0.0)
        self.assertEqual(s["p5_timing"], 0.0)
        self.assertEqual(s["threat_base"], "")

    def test_not_detected_away_from_the_bridge_or_far_hog(self):
        board = Board(objs=towers() + [hog(3.5, 12.0)], team=0)
        self.assertEqual(score_placement(board, at(SKELETONS, 9.0, 21.0))["bridge_block_detected"], 0.0)
        far = Board(objs=towers() + [hog(3.5, 2.0)], team=0)         # 14 tiles > 9.5 + 3
        self.assertEqual(score_placement(far, at(SKELETONS, 3.5, 16.0))["bridge_block_detected"], 0.0)

    def test_anti_cases(self):
        support = [BoardObj(1, "troop", "goblin", *T(3.5, 10.0 - i), 0.5, 5.5, 0.4, 100, 100, 1.0, 1.5)
                   for i in range(3)]
        board = Board(objs=towers() + [hog(3.5, 12.0)] + support, team=0)
        s = score_placement(board, at(SKELETONS, 3.5, 16.0))
        self.assertEqual(s["bridge_block_detected"], 1.0)
        self.assertEqual(s["bridge_block_case"], 0.0)                # >= 3 trailing supports
        self.assertEqual(s["p5_timing"], 0.0)                        # no credit, no penalty
        ma = BoardObj(1, "troop", "magic_archer", *T(3.5, 12.0), 7.0, 5.5, 0.5, 500, 500, 4.0, 1.0)
        s2 = score_placement(Board(objs=towers() + [ma], team=0), at(SKELETONS, 3.5, 16.0))
        self.assertEqual(s2["bridge_block_case"], 0.0)               # B9


class TornadoAway(unittest.TestCase):
    def test_away_is_one_when_pulled_straight_back(self):
        board = Board(objs=towers(), team=0)
        h = hog(3.5, 20.0)                                           # on our side, walking +y to the left tower
        self.assertAlmostEqual(G.tornado_away(board, h, *T(3.5, 17.0), board.own_towers()), 1.0)
        self.assertAlmostEqual(G.tornado_away(board, h, *T(3.5, 23.0), board.own_towers()), 0.0)
        self.assertAlmostEqual(G.tornado_away(board, h, *T(8.0, 20.0), board.own_towers()), 0.5)

    def test_nado_terms(self):
        board = Board(objs=towers() + [hog(3.5, 20.0)], team=0)
        back = score_placement(board, at(TORNADO, 3.5, 17.0))
        self.assertGreater(back["p4_nado"], 0.0)
        self.assertEqual(back["p4_king_activation"], 0.0)
        self.assertAlmostEqual(back["p4_spell_frac"], 1.0)
        king = score_placement(board, at(TORNADO, 3.5, 23.0))        # pulls it toward the tower...
        self.assertEqual(king["p4_nado"], 0.0)
        self.assertEqual(king["p4_king_activation"], 1.0)            # ...under the sleeping king (gap 6.2 <= 8.5)
        awake = Board(objs=towers(king_awake=True) + [hog(3.5, 20.0)], team=0)
        self.assertEqual(score_placement(awake, at(TORNADO, 3.5, 23.0))["p4_king_activation"], 0.0)


class Bounds(unittest.TestCase):
    def test_every_term_bounded_and_deterministic(self):
        objs = towers() + [hog(3.5, 12.0),
                           BoardObj(1, "troop", "valkyrie", *T(14.0, 19.0), 1.2, 5.5, 0.5, 1900, 1900, 4.0, 1.0,
                                    splash=True, roles=("tank", "splash")),
                           BoardObj(1, "troop", "goblin", *T(9.0, 19.0), 0.5, 5.5, 0.4, 100, 100, 1.0, 1.5)]
        board = Board(objs=objs, team=0)
        cards = (TESLA, XBOW, SKELETONS, TORNADO)
        for card in cards:
            for xt in (1.5, 3.5, 9.0, 14.5, 16.5):
                for yt in (16.0, 18.5, 21.0, 24.0, 28.0):
                    a = score_placement(board, at(card, xt, yt))
                    b = score_placement(board, at(card, xt, yt))
                    self.assertEqual(a, b)
                    for k in G.TERM_KEYS:
                        v = a[k]
                        if k in ("d_threat", "d_path"):
                            self.assertGreaterEqual(v, 0.0)
                        elif k in ("p1_close_penalty", "p1_close_snapshot", "p7_fragility"):
                            self.assertTrue(-1.0 <= v <= 0.0, (card["base"], xt, yt, k, v))
                        else:
                            self.assertTrue(0.0 <= v <= 1.0, (card["base"], xt, yt, k, v))

    def test_lone_skeleton_is_not_a_threat(self):
        sk = BoardObj(1, "troop", "skeleton", *T(3.5, 20.0), 0.5, 5.5, 0.4, 81, 81, 0.33, 1.5)
        s = score_placement(Board(objs=towers() + [sk], team=0), at(TESLA, 9.0, 21.0))
        self.assertEqual(s["threat_base"], "")
        self.assertEqual(s["p1_pull_band"], 0.0)

    def test_fragility(self):
        valk = BoardObj(1, "troop", "valkyrie", *T(4.5, 20.0), 1.2, 5.5, 0.5, 1900, 1900, 4.0, 1.0,
                        splash=True, roles=("tank", "splash"))
        board = Board(objs=towers() + [valk], team=0)
        on_top = score_placement(board, at(SKELETONS, 4.5, 21.0))
        self.assertAlmostEqual(on_top["p7_fragility"], -1.0)
        away = score_placement(board, at(SKELETONS, 4.5, 24.0))
        self.assertEqual(away["p7_fragility"], 0.0)
        self.assertEqual(score_placement(board, at(TESLA, 4.5, 21.0))["p7_fragility"], 0.0)   # never a building


ICE_WIZARD = dict(base="ice_wizard", kind="troop", r_atk=5.5, r_sight=5.5, r_body=0.5, deploy_time=1.0,
                  speed=1.0, building_only=False, is_spell=False, spell_radius=0.0, hp=590.0,
                  roles=("splash",))
SKELETONS_ROLED = dict(SKELETONS, roles=("swarm",))


class L59PathP1AndRestrictions(unittest.TestCase):
    """L59 (HANDOFF 5cs.29): path-based P1, P2 buildings-only, P7 not for swarm, credit helpers."""

    def test_a_preplaced_tesla_vs_hog_at_enemy_bridge_approach(self):
        # Hog still on the ENEMY half at own-frame y = 11 (5 tiles short of the left bridge; at
        # y = 12 the snapshot march gap 10.9 is still on the band's outer ramp, 0.28).
        board = Board(objs=towers() + [hog(3.5, 11.0)], team=0)
        s = score_placement(board, at(TESLA, 9.0, 21.0))
        self.assertEqual(s["threat_base"], "hog_rider")
        # snapshot: march gap = 5 (to the bridge) + hypot(5.5, 5) - 0.5 = 11.9 tiles > r_sight 9.5 + w -> 0
        self.assertEqual(s["p1_snapshot"], 0.0)
        s12 = score_placement(Board(objs=towers() + [hog(3.5, 12.0)], team=0), at(TESLA, 9.0, 21.0))
        self.assertLess(s12["p1_snapshot"], 0.3)
        self.assertAlmostEqual(s12["p1_pull_band"], 1.0)
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
        full.update(p1_close_penalty=0.0, p1_close_snapshot=0.0, p7_fragility=0.0)
        self.assertAlmostEqual(G.placement_credit(full, "building"), 1.0)     # P1 + P6 capped at 1.0
        worst = {k: 0.0 for k in G.TERM_KEYS}
        worst.update(p1_close_penalty=-1.0, p1_close_snapshot=-1.0, p7_fragility=-1.0)
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
        # the path ends at the left princess (3.5, 25.5): d_path = hypot(5.5, 5.5) - 0.5 = 7.28 tiles
        # (inside the band lo 1.8 .. hi 9.5) but the princess (9.5 march) is nearer than the Tesla
        # (hypot(5.5, 15) - 0.5 = 15.5): pull_ok = 0 zeroes the band
        self.assertAlmostEqual(s["d_path"], 7.28, places=1)

    def test_bridge_block_case_is_full_timing_credit(self):
        board = Board(objs=towers() + [hog(3.5, 14.0)], team=0)
        s = score_placement(board, at(SKELETONS, 3.5, 17.0))
        if s["bridge_block_case"] == 1.0:
            self.assertAlmostEqual(G.timing_credit(s), 1.0)
        self.assertTrue(0.0 <= G.timing_credit(s) <= 1.0)


class RadiiOneSourceOfTruth(unittest.TestCase):
    def test_radii_of_shapes(self):
        class Spec:
            kind, reach, sight, siege, spell_radius = "troop", 0.8, 9.5, False, 0.0
        class Siege(Spec):
            reach, sight, siege = 11.5, 11.5, True
        class Spell:
            kind, spell_radius = "spell", 2.5
        class Tower:
            king = True
        self.assertEqual(G.radii_of(Spec()), (0.8, 9.5))
        self.assertEqual(G.radii_of(Siege(), siege_sight=11.5), (11.5, 11.5))
        self.assertEqual(G.radii_of(Spell()), (2.5, 0.0))
        self.assertEqual(G.radii_of(Tower(), king_range=8.5, tower_range=8.0), (8.5, 8.5))
        Tower.king = False
        self.assertEqual(G.radii_of(Tower(), king_range=8.5, tower_range=8.0), (8.0, 8.0))

    def test_engine_adapter_and_metric_parity(self):
        from clashrl.config import Config
        from clashrl.sim import engine as E
        from clashrl.sim.env import SimMatchEnv
        env = SimMatchEnv(Config.load())
        env.reset()
        eng = env.eng
        for (ax, ay, bx, by) in ((0.1, 0.2, 0.7, 0.9), (0.5, 0.5, 0.5, 0.8), (0.0, 0.0, 1.0, 1.0)):
            self.assertAlmostEqual(G.tile_dist(ax, ay, bx, by), E._dist(ax, ay, bx, by))
        spec = E.build_spec(eng.db, "x_bow", 11)
        self.assertEqual(G.radii_of(spec, siege_sight=eng.siege_sight), (spec.reach, eng.siege_sight))
        eng.elixir[0] = 10.0
        self.assertTrue(eng.deploy(0, spec, 1.5 / 18.0, 18.5 / 32.0))
        eng.advance(0.1)
        board = G.board_from_engine(eng, 0)
        kinds = sorted(o.kind for o in board.objs)
        self.assertEqual(kinds, ["building"] + ["tower"] * 6)
        bow = next(o for o in board.objs if o.kind == "building")
        self.assertEqual((bow.r_atk, bow.r_sight), (11.5, 11.5))
        self.assertTrue(bow.deploying)                                # 3.5 s wind-up, included + flagged
        self.assertIn("win_condition", bow.roles)
        self.assertEqual(board.tower_range, eng.tower_range)
        self.assertEqual(board.bridges_x, tuple(eng.lanes))
        # kill the enemy left princess: it must vanish from the board (doc §7.5)
        eng.towers[1][0].alive = False
        eng.towers[1][0].hp = 0.0
        board2 = G.board_from_engine(eng, 0)
        self.assertEqual(sum(1 for o in board2.objs if o.kind == "tower"), 5)
        # role-average radii come from the KB and are cached
        ra, rs = G.role_average_radii("hog_rider", eng.db)
        self.assertGreater(rs, 0.0)
        self.assertEqual(G.role_average_radii("hog_rider", eng.db), (ra, rs))


if __name__ == "__main__":
    unittest.main()
