"""pipeline/reward_shaping.py (L69 R2): potentials, telescoping, side symmetry, dead towers, crowns, terminal.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_reward_shaping.py

Pure python on synthetic raw() states (royale_env.RoyalePoolEnv.raw's crown_towers shape); no engine needed.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline import reward_shaping as R    # noqa: E402

KING, PRINCESS = 4824, 3052                 # RoyaleSim level-11 max_hp (search_s0.engine_tower_level)


def state(hp0=(KING, PRINCESS, PRINCESS), hp1=(KING, PRINCESS, PRINCESS), crowns=None, drop_dead=False):
    """A raw() state with side s's towers at hp (king, princess L, princess R); hp <= 0 = destroyed."""
    tw = []
    for s, hps in ((0, hp0), (1, hp1)):
        for i, (typ, mx) in enumerate((("king", KING), ("princess", PRINCESS), ("princess", PRINCESS))):
            if drop_dead and hps[i] <= 0:
                continue
            tw.append({"side": s, "type": typ, "x": float(i), "y": 0.0, "hp": hps[i], "max_hp": mx,
                       "destroyed": hps[i] <= 0})
    st = {"tick": 0, "players": [], "entities": [], "effects": [], "episode": {"crown_towers": tw}}
    if crowns is not None:
        st["crowns"] = list(crowns)
    return st


def random_match(rng: random.Random, n: int) -> list[dict]:
    """n states with monotonically falling tower HP on both sides (towers only lose HP), some towers dying."""
    hp = {0: [KING, PRINCESS, PRINCESS], 1: [KING, PRINCESS, PRINCESS]}
    out = []
    for _ in range(n):
        for s in (0, 1):
            for i in range(3):
                if rng.random() < 0.3:
                    hp[s][i] = max(0, hp[s][i] - rng.randint(0, 900))
        out.append(state(tuple(hp[0]), tuple(hp[1])))
    return out


class TestPotentials(unittest.TestCase):
    def test_start_is_zero(self):
        s = state()
        self.assertEqual(R.phi_tower(s, 0), 0.0)
        self.assertEqual(R.phi_crown(s, 0), 0.0)
        self.assertEqual(R.crowns(s), (0, 0))

    def test_tower_fraction_uses_each_towers_max_hp(self):
        s = state(hp1=(KING // 2, PRINCESS, PRINCESS))           # foe king at half: -0.5 of one tower
        self.assertAlmostEqual(R.phi_tower(s, 0), 0.5 / 3)
        s = state(hp0=(KING, PRINCESS // 4, PRINCESS))           # own princess at a quarter
        self.assertAlmostEqual(R.phi_tower(s, 0), -0.75 / 3)

    def test_side_symmetry(self):
        rng = random.Random(1)
        for s in random_match(rng, 50):
            self.assertAlmostEqual(R.phi_tower(s, 0), -R.phi_tower(s, 1))
            self.assertAlmostEqual(R.phi_crown(s, 0), -R.phi_crown(s, 1))
            self.assertAlmostEqual(R.phi(s, 0, 0.7, 0.3), -R.phi(s, 1, 0.7, 0.3))
        ms = random_match(random.Random(2), 30)
        f0 = R.shaping_terms(ms, 0, 0.99, (1.0, 1.0))["F"]
        f1 = R.shaping_terms(ms, 1, 0.99, (1.0, 1.0))["F"]
        for a, b in zip(f0, f1):
            self.assertAlmostEqual(a, -b)

    def test_dead_towers_count_zero_listed_or_dropped(self):
        for drop in (False, True):
            s = state(hp1=(KING, 0, PRINCESS), drop_dead=drop)
            self.assertAlmostEqual(R.phi_tower(s, 0), 1.0 / 3)
            self.assertEqual(R.crowns(s), (1, 0))
            s = state(hp1=(KING, -50, PRINCESS), drop_dead=drop)   # negative hp: dead, not a negative fraction
            self.assertAlmostEqual(R.phi_tower(s, 0), 1.0 / 3)
        s = state(hp0=(0, 0, 0), hp1=(KING, PRINCESS, PRINCESS), drop_dead=True)
        self.assertAlmostEqual(R.phi_tower(s, 1), 1.0)

    def test_crowns_derived(self):
        self.assertEqual(R.crowns(state(hp0=(KING, 0, 0))), (0, 2))
        self.assertEqual(R.crowns(state(hp0=(0, PRINCESS, PRINCESS))), (0, 3))    # king down = 3, towers standing
        self.assertEqual(R.crowns(state(hp0=(0, 0, PRINCESS), hp1=(KING, 0, PRINCESS))), (1, 3))
        self.assertAlmostEqual(R.phi_crown(state(hp0=(KING, 0, 0)), 1), 2 / 3)

    def test_attached_crowns_win(self):
        s = state(hp1=(KING, 0, PRINCESS), crowns=(0, 0))        # the engine's count overrides the derivation
        self.assertEqual(R.crowns(s), (0, 0))
        self.assertAlmostEqual(R.phi_crown(state(crowns=(2, 1)), 0), 1 / 3)

    def test_weights(self):
        s = state(hp0=(KING, 0, PRINCESS))
        self.assertAlmostEqual(R.phi(s, 0, 0.4, 0.2), 0.4 * (-1 / 3) + 0.2 * (-1 / 3))


class TestShaping(unittest.TestCase):
    def test_telescoping_gamma_one(self):
        rng = random.Random(0)
        for _ in range(20):
            ms = random_match(rng, rng.randint(1, 80))
            for side in (0, 1):
                sh = R.shaping_terms(ms, side, 1.0, (0.6, 0.4))
                self.assertAlmostEqual(sum(sh["F"]), -R.phi(ms[0], side, 0.6, 0.4), places=12)
                self.assertAlmostEqual(sum(sh["tower"]) + sum(sh["crown"]), sum(sh["F"]), places=12)

    def test_telescoping_discounted(self):
        rng = random.Random(3)
        for gamma in (0.999, 0.9, 0.5):
            ms = random_match(rng, 60)
            sh = R.shaping_terms(ms, 0, gamma, (1.0, 1.0))
            self.assertAlmostEqual(sum(gamma ** t * f for t, f in enumerate(sh["F"])), -R.phi(ms[0], 0, 1.0, 1.0),
                                   places=12)
            # the shaping part of every decision's return-to-go is exactly -Phi(s_t)
            for t, g in enumerate(R.returns_to_go(sh["F"], gamma)):
                self.assertAlmostEqual(g, -R.phi(ms[t], 0, 1.0, 1.0), places=12)

    def test_undiscounted_sum_with_gamma_below_one(self):
        # sum F (no discount) = -Phi(s_0) - (1 - gamma) * sum_{t>=1} Phi(s_t): a small bonus for low-potential states
        ms = random_match(random.Random(4), 40)
        g = 0.999
        sh = R.shaping_terms(ms, 0, g, (1.0, 1.0))
        want = -sh["phi"][0] - (1 - g) * sum(sh["phi"][1:])
        self.assertAlmostEqual(sum(sh["F"]), want, places=12)

    def test_terminal_potential_is_zero(self):
        ms = [state(), state(hp1=(KING, 0, PRINCESS)), state(hp1=(0, 0, PRINCESS))]
        sh = R.shaping_terms(ms, 0, 1.0, (1.0, 1.0))             # default T = len: the last state is a decision
        self.assertEqual(len(sh["F"]), 3)
        self.assertEqual(sh["phi"][-1], 0.0)
        self.assertAlmostEqual(sh["F"][-1], -R.phi(ms[2], 0, 1.0, 1.0))
        sh = R.shaping_terms(ms, 0, 1.0, (1.0, 1.0), terminal_index=2)   # ms[2] IS the terminal: its Phi ignored
        self.assertEqual(len(sh["F"]), 2)
        self.assertAlmostEqual(sh["F"][1], 0.0 - R.phi(ms[1], 0, 1.0, 1.0))
        self.assertAlmostEqual(sum(sh["F"]), 0.0)                # Phi(s_0) = 0 at a symmetric start
        with self.assertRaises(ValueError):
            R.shaping_terms(ms, 0, 1.0, (1.0, 1.0), terminal_index=0)
        with self.assertRaises(ValueError):
            R.shaping_terms(ms, 0, 1.0, (1.0, 1.0), terminal_index=4)

    def test_per_term_breakdown(self):
        ms = [state(), state(hp1=(KING, 0, PRINCESS), crowns=(1, 0))]
        sh = R.shaping_terms(ms, 0, 1.0, (0.5, 0.25))
        self.assertAlmostEqual(sh["tower"][0], 0.5 * (1 / 3))
        self.assertAlmostEqual(sh["crown"][0], 0.25 * (1 / 3))
        self.assertAlmostEqual(sh["F"][0], sh["tower"][0] + sh["crown"][0])


if __name__ == "__main__":
    unittest.main()
