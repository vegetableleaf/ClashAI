"""Two user reports, 2026-08-20.

1. "IT LEARNED TO ROCKET CYCLE THE OPPONENT KING TOWER????? disable chip rewards on king tower."

   Chip was never the payoff: _chip_progress slices [:2] -- princesses only -- in BOTH envs, and
   the king's HP is not even read live (env.enemy_tower_hp_boxes holds two boxes). MEASURED, a
   king rocket scored 0.0. Zero was the bug. It is not a reward, but it is not a COST either,
   and it dodges the leak penalty, so dumping six elixir into the king was a FREE cycle and the
   policy learned exactly that. The live `near_enemy_king -> w_wincon_mis` guard did exist but
   sat in the MINER branch; the rocket branch fell through to `return 0.0`.

2. "IT STILL DOESN'T UNDERSTAND THE PLACEMENT FOR ROCKET TORNADO... the tornado and rocket need
   to be cast in the same tile for the combo to work most effectively."

   The sim has priced that combo since 2026-08-16 (rocket_nado_mult / rocket_nado_window_s).
   LIVE HAD NO SUCH TERM, which is precisely why a sim-trained checkpoint carried the TIMING
   across and never the placement: nothing in the live reward ever paid for landing on the clump
   the tornado had just gathered.
"""
from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config          # noqa: E402
from clashrl.sim.env import SimMatchEnv    # noqa: E402


def _live_src():
    p = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "env.py")
    with io.open(p, encoding="utf-8") as fh:
        return fh.read()


class KingRocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load(), seed=3)
        cls.env.reset()
        cls.rid = next((i for i, s in enumerate(cls.env.specs) if s.base == "rocket"), None)

    def _val(self, x, y):
        return self.env._wincon_exec(self.rid, x, y)

    def test_rocketing_the_enemy_king_is_a_misplace(self):
        k = self.env.eng.towers[1][2]
        self.assertLess(self._val(k.x, k.y), 0.0,
                        "a king rocket is free again -- it dodges the leak penalty, which is how "
                        "'rocket cycling the king' became the policy's favourite dump")

    def test_rocketing_a_princess_is_still_worth_it(self):
        p = self.env.eng.towers[1][0]
        self.assertGreater(self._val(p.x, p.y), 0.0,
                           "the fix took the real chip play down with it")

    def test_the_king_penalty_is_at_least_as_bad_as_an_empty_cast(self):
        """Empty grass is 0.0 here and separately billed by spell_waste; the king must not be the
        CHEAPER of the two, or it stays the preferred place to dump six elixir."""
        k = self.env.eng.towers[1][2]
        self.assertLessEqual(self._val(k.x, k.y), self._val(0.5, 0.35))


class KingChipTests(unittest.TestCase):
    """"Disable chip rewards on king tower" -- they were already off; pin it so nobody re-adds."""

    def test_sim_chip_progress_counts_princesses_only(self):
        env = SimMatchEnv(Config.load(), seed=4)
        env.reset()
        towers = env.eng.towers[1]
        before = env._chip_progress(towers)
        towers[2].hp = max(1, towers[2].max_hp // 2)          # halve the KING
        self.assertEqual(before, env._chip_progress(towers),
                         "king damage moved the chip reward")

    def test_live_chip_progress_slices_to_two(self):
        src = _live_src()
        self.assertIn("for hp in list(hp_list)[:2]:", src,
                      "live chip progress no longer restricts itself to the princess towers")

    def test_live_reads_only_two_enemy_hp_boxes(self):
        """The king's HP is not even read on the offence side, so it cannot leak into chip."""
        boxes = Config.load().get("env", "enemy_tower_hp_boxes", default=[])
        self.assertEqual(2, len(boxes), "a third (king) HP box appeared on the enemy side")


class LiveKingBranchTests(unittest.TestCase):
    """The live env needs a window and a detector, so the branch is checked in source."""

    def test_the_rocket_branch_rejects_the_king(self):
        src = _live_src()
        i = src.index("if card_id in self.rocket_ids:")
        j = src.index("if card_id in self.miner_ids:", i) if "if card_id in self.miner_ids:" in src[i:] else len(src)
        branch = src[i:j]
        self.assertIn("near_enemy_king", branch,
                      "the live rocket branch fell back through to `return 0.0` on a king aim -- "
                      "the guard is in the MINER branch and never applied to a rocket")


class NadoRocketComboTests(unittest.TestCase):
    """The combo is a SAME-TILE play; live now both pays for it and (with wheels) aims it."""

    def test_live_records_the_tornado_cast_point(self):
        src = _live_src()
        self.assertIn("self._last_nado = (cx, cy, time.time())", src,
                      "the tornado's cast point is not remembered, so the rocket cannot aim at it")

    def test_live_pays_the_combo(self):
        src = _live_src()
        self.assertIn("self.rocket_nado_mult", src,
                      "live still has no reward for the tornado-bundled rocket -- the reason a "
                      "sim-trained policy kept the timing and lost the placement")

    def test_the_combo_credit_requires_BOTH_the_window_and_the_tile(self):
        src = _live_src()
        i = src.index("nado = getattr(self, \"_last_nado\", None)")
        window = src[i:i + 600]
        self.assertIn("rocket_nado_window_s", window, "the timing half of the combo is gone")
        self.assertIn("rocket_nado_radius", window, "the SAME-TILE half of the combo is gone")

    def test_the_wheel_snaps_the_rocket_onto_the_tornado(self):
        src = _live_src()
        self.assertIn("SAME TILE AS THE TORNADO", src,
                      "the wheels no longer place the rocket on the tornado's tile")

    def test_the_window_and_radius_are_configured(self):
        cfg = Config.load()
        self.assertGreater(float(cfg.get("env", "rocket_nado_window_s", default=0)), 0.0)
        r = float(cfg.get("env", "rocket_nado_radius", default=0))
        self.assertGreater(r, 0.0)
        self.assertLess(r, 0.2, "the 'same tile' radius grew into 'anywhere nearby'")


if __name__ == "__main__":
    unittest.main(verbosity=1)
