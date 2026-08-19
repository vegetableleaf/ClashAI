"""The researched pressure doctrine, wired into the sim (DOCTRINE_RESEARCH.md, 2026-08-19).

The user's report: "even if there are no threats, 'hold' is not the best option -- the model
should cycle back to a hog rider and play it at the bridge as soon as possible." The research
sharpened that into the SEND ladder (§1.1) and the C8 elixir split (§6): quiet single-elixir
sends wait for 7 (the bank keeps the 3-elixir floor every guide holds), double-elixir/OT sends
go at 4, and a PUNISH window -- >=5 enemy elixir committed deep in their half -- overrides every
bar. And the Hog finally has a CELL rule: it was being nominated by the card prior and then
placed by the uniform exploration floor, i.e. anywhere on 432 cells.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                     # noqa: E402
from clashrl.sim import doctrine as D                 # noqa: E402
from clashrl.sim.engine import Unit, build_spec       # noqa: E402
from clashrl.sim.env import SimMatchEnv               # noqa: E402


def _hog_in_hand(env):
    """Cycle non-Hog plays until the Hog is in hand (the deal is deterministic per reset seed)."""
    hog = next(i for i, k in enumerate(env.deck_keys) if k == "hog_rider")
    for _ in range(8):
        if hog in env._hand_ids():
            return hog
        other = next(c for c in env._hand_ids() if c != hog and c != env.ability_id)
        env._play_slot(other)
    raise AssertionError("could not cycle the Hog into hand")


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load())

    def fresh(self, elixir=7.0, t=10.0):
        env = self.env
        env.reset()
        eng = env.eng
        eng.units.clear()
        eng.spells.clear()
        eng.projectiles.clear()
        eng.elixir[0] = float(elixir)
        eng.t = float(t)
        return env, eng

    def enemy(self, eng, key, x, y, level=11):
        sp = build_spec(self.env.db, key, level)
        u = Unit(spec=sp, team=1, x=float(x), y=float(y), hp=sp.hp)
        u.deploy_left = 0.0
        eng.units.append(u)
        return u

    def mine(self, eng, key, x, y, level=13):
        sp = build_spec(self.env.db, key, level)
        u = Unit(spec=sp, team=0, x=float(x), y=float(y), hp=sp.hp)
        u.deploy_left = 0.0
        eng.units.append(u)
        return u


class SendLadderTests(_Base):
    """doctrine_cards: WHEN the Hog is nominated."""

    def _hog_weight(self, env):
        hog = _hog_in_hand(env)
        w = D.doctrine_cards(env) or {}
        return w.get(hog, 0.0)

    def test_quiet_single_elixir_at_six_holds_the_bar(self):
        """C8: a quiet x1 board at 6 elixir does NOT nominate the Hog -- sending would break
        the 3-elixir floor."""
        env, _ = self.fresh(elixir=6.0, t=10.0)
        self.assertEqual(0.0, self._hog_weight(env))

    def test_quiet_single_elixir_at_seven_sends(self):
        env, _ = self.fresh(elixir=7.0, t=10.0)
        self.assertGreater(self._hog_weight(env), 0.0)

    def test_double_elixir_sends_at_four(self):
        env, _ = self.fresh(elixir=4.0, t=150.0)
        self.assertGreater(self._hog_weight(env), 0.0)

    def test_single_elixir_at_four_does_not_send_unprovoked(self):
        env, _ = self.fresh(elixir=4.0, t=10.0)
        self.assertEqual(0.0, self._hog_weight(env))

    def test_a_back_committed_tank_opens_the_punish_window(self):
        """T1: a Golem placed behind their king (>=5 elixir deep in their half) overrides the
        x1 bar -- the Hog is nominated at 4 elixir, and harder than the quiet-board default."""
        env, eng = self.fresh(elixir=4.0, t=10.0)
        self.enemy(eng, "golem", 0.30, 0.10)
        got = self._hog_weight(env)
        self.assertGreater(got, 0.0)
        env_quiet, _ = self.fresh(elixir=7.0, t=10.0)
        self.assertGreater(got, self._hog_weight(env_quiet),
                           "the punish window should outrank the quiet-board default")

    def test_a_pump_deep_in_their_half_is_a_punish_window(self):
        # Review blocker: the Elixir Collector is the single most-punishable commit in the
        # research, and a troop-only kind filter silently excluded it.
        env, eng = self.fresh(elixir=4.0, t=10.0)
        self.enemy(eng, "elixir_collector", 0.30, 0.10)
        self.assertGreater(self._hog_weight(env), 0.0)

    def test_the_pekka_matchup_turns_the_punish_off_in_single_elixir(self):
        # SS5.3: vs a P.E.K.K.A deck in single elixir the T1 window is OFF -- double-lane
        # pressure is what loses that matchup. In double elixir it is back on.
        env, eng = self.fresh(elixir=4.0, t=10.0)
        self.enemy(eng, "pekka", 0.30, 0.10)    # committed behind their king -- and the veto card
        self.assertEqual(0.0, self._hog_weight(env))
        env2, eng2 = self.fresh(elixir=4.0, t=150.0)
        self.enemy(eng2, "pekka", 0.30, 0.10)
        self.assertGreater(self._hog_weight(env2), 0.0, "x2 keeps the affordable send")

    def test_a_surviving_defender_drops_the_send_bar(self):
        # T2 -> C8: "any T1-T4 window -> send at 4". A survivor standing at our tower line
        # (engine-anchored y, where defences actually resolve) opens the window.
        env, eng = self.fresh(elixir=4.0, t=10.0)
        self.mine(eng, "mighty_miner", 0.72, 0.80)   # at the princess line, post-defence
        self.assertGreater(self._hog_weight(env), 0.0)

    def test_a_swarm_deep_in_their_half_is_not_a_punish_window(self):
        """The per-body accounting: 15 skeleton bodies are not 15 elixir of commitment."""
        env, eng = self.fresh(elixir=4.0, t=10.0)
        for i in range(4):
            self.enemy(eng, "skeletons", 0.30 + 0.02 * i, 0.10)
        self.assertEqual(0.0, self._hog_weight(env))


class HogCellTests(_Base):
    """doctrine_cells: WHERE the Hog goes."""

    def _cells(self, env, key="hog_rider"):
        cid = next(i for i, k in enumerate(env.deck_keys) if k == key)
        got = D.doctrine_cells(env, cid)
        self.assertTrue(got, "%s produced no cells" % key)
        return dict(got), cid

    def _grid(self, env, cell):
        gw = int(env.actions.gw)
        return cell % gw, cell // gw

    def test_the_hog_goes_to_the_bridge_rows(self):
        env, _ = self.fresh()
        w, _ = self._cells(env)
        acts = env.actions
        front_gy = acts.coords_to_grid(env.eng.towers[0][0].x, D._OWN_FRONT)[1]
        best = max(w, key=w.get)
        gx, gy = self._grid(env, best)
        self.assertLessEqual(abs(gy - front_gy), 1, "the top hog cell is not on the front row")
        lgx = acts.coords_to_grid(env.eng.towers[0][0].x, D._OWN_FRONT)[0]
        rgx = acts.coords_to_grid(env.eng.towers[0][1].x, D._OWN_FRONT)[0]
        self.assertTrue(min(abs(gx - lgx), abs(gx - rgx)) <= 1,
                        "the top hog cell is not at either bridge (gx=%d)" % gx)

    def test_committed_enemy_mass_pushes_the_hog_to_the_opposite_lane(self):
        env, eng = self.fresh()
        self.enemy(eng, "golem", 0.25, 0.15)          # their left
        w, _ = self._cells(env)
        acts = env.actions
        lgx = acts.coords_to_grid(env.eng.towers[0][0].x, D._OWN_FRONT)[0]
        rgx = acts.coords_to_grid(env.eng.towers[0][1].x, D._OWN_FRONT)[0]
        left_w = max((v for c, v in w.items() if abs(self._grid(env, c)[0] - lgx) <= 1),
                     default=0.0)
        right_w = max((v for c, v in w.items() if abs(self._grid(env, c)[0] - rgx) <= 1),
                      default=0.0)
        self.assertGreater(right_w, left_w, "the punish Hog should prefer the opposite bridge")

    def test_a_surviving_defender_pulls_the_counterpush_to_its_lane(self):
        env, eng = self.fresh()
        self.mine(eng, "mighty_miner", 0.72, 0.58)    # our survivor on the right
        self.enemy(eng, "golem", 0.25, 0.15)          # mass says left is committed -> right anyway
        w, _ = self._cells(env)
        acts = env.actions
        rgx = acts.coords_to_grid(env.eng.towers[0][1].x, D._OWN_FRONT)[0]
        best = max(w, key=w.get)
        self.assertLessEqual(abs(self._grid(env, best)[0] - rgx), 1,
                             "the counter-push should go behind the survivor's lane")


class SupportCellTests(_Base):
    def test_mighty_miner_body_blocks_the_biggest_tank(self):
        env, eng = self.fresh()
        tank = self.enemy(eng, "golem", 0.30, 0.55)
        w, _ = HogCellTests._cells(self, env, "mighty_miner")
        best = max(w, key=w.get)
        gw = int(env.actions.gw)
        cx, cy = env.actions.cell_center(best % gw, best // gw)
        self.assertLess(abs(cx - tank.x) * 18.0, 2.5, "MM is not on the tank's lane")
        self.assertGreaterEqual(cy, tank.y - 0.02, "MM must block DOWN-path of the tank")

    def test_firecracker_kites_a_heavy_from_the_deep_band(self):
        # REVIEW FIX: the P.E.K.K.A must sit past the river centre (y > 0.5) or
        # _deepest_ground_threat returns None and the assertion passes vacuously against the
        # behind-the-king bank spot. Depth is measured from the NEAR BANK (17/32) and bounded
        # ABOVE too, so the king spot can never satisfy it. F-2 band: the 5th tile.
        env, eng = self.fresh()
        self.enemy(eng, "pekka", 0.30, 0.55)
        w, _ = HogCellTests._cells(self, env, "firecracker")
        best = max(w, key=w.get)
        gw = int(env.actions.gw)
        cx, cy = env.actions.cell_center(best % gw, best // gw)
        depth_tiles = (cy - 17.0 / 32.0) * 32.0
        self.assertGreaterEqual(depth_tiles, 3.5, "a P.E.K.K.A gets the 5-tile band, not the 4th")
        self.assertLessEqual(depth_tiles, 7.0, "the spot drifted to the back -- not a kite band")
        self.assertGreater(cx, 0.30, "she should be staggered toward the other lane")

    def test_firecracker_fronts_a_building_targeting_tank(self):
        # F-8: vs a Giant she goes directly IN FRONT (in its path), so the shrapnel pierces
        # into the backline -- the opposite geometry of the kite band.
        env, eng = self.fresh()
        g = self.enemy(eng, "giant", 0.30, 0.55)
        w, _ = HogCellTests._cells(self, env, "firecracker")
        best = max(w, key=w.get)
        gw = int(env.actions.gw)
        cx, cy = env.actions.cell_center(best % gw, best // gw)
        self.assertLess(abs(cx - g.x) * 18.0, 1.6, "she is not in the Giant's lane")
        self.assertGreater(cy, g.y, "she must stand DOWN-path of the tank, not beside it")

    def test_ice_spirit_escorts_our_crossing_hog(self):
        env, eng = self.fresh()
        hog = self.mine(eng, "hog_rider", 0.745, 0.40)
        w, _ = HogCellTests._cells(self, env, "ice_spirit")
        best = max(w, key=w.get)
        gw = int(env.actions.gw)
        cx, _cy = env.actions.cell_center(best % gw, best // gw)
        self.assertLess(abs(cx - hog.x) * 18.0, 2.5, "the escort is not in the Hog's lane")

    def test_quiet_board_still_offers_every_new_card_somewhere(self):
        """No branch may return an empty prior on a quiet board and silently mask the card."""
        env, _ = self.fresh()
        for key in ("hog_rider", "mighty_miner", "firecracker", "ice_spirit"):
            with self.subTest(card=key):
                cid = next(i for i, k in enumerate(env.deck_keys) if k == key)
                got = D.doctrine_cells(env, cid)
                self.assertTrue(got, "%s has no quiet-board spot" % key)

    def test_every_offered_cell_is_deployable(self):
        """All spots clamp to our own half's deployable rows."""
        env, eng = self.fresh()
        self.enemy(eng, "pekka", 0.30, 0.50)
        self.mine(eng, "hog_rider", 0.745, 0.40)
        gw = int(env.actions.gw)
        for key in ("hog_rider", "mighty_miner", "firecracker", "ice_spirit"):
            cid = next(i for i, k in enumerate(env.deck_keys) if k == key)
            for cell, _v in (D.doctrine_cells(env, cid) or []):
                _cx, cy = env.actions.cell_center(cell % gw, cell // gw)
                self.assertGreaterEqual(cy, D._OWN_FRONT - 1.0 / 24.0,
                                        "%s offered an undeployable cell" % key)


class DoctrineTableTests(_Base):
    def test_the_llm_doctrine_table_names_only_cards_this_deck_holds(self):
        """The icebow table steered exploration toward cards this deck does not hold -- and its
        Tesla rules were actively wrong here (quiet board at 10 -> Tesla; the answer is Hog)."""
        import json
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "config" / "llm_doctrine.json"
        if not p.exists():
            self.skipTest("no doctrine table on disk (regeneration pending)")
        rules = json.loads(p.read_text(encoding="utf-8")).get("rules") or {}
        if not rules:
            self.skipTest("doctrine table is empty")
        own = set()
        for k in self.env.deck_keys:
            own.add(k)
            own.add(k[:-4] if k.endswith("_evo") else k)
        named = {r.get("card") for r in rules.values()}
        self.assertLessEqual(named - {"hold", None}, own,
                             "doctrine table names foreign cards: %s" % sorted(named - own))


if __name__ == "__main__":
    unittest.main(verbosity=1)
