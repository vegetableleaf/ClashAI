"""The WHEN-NOT-TO-PLAY prior (tools/gate_prior.py) and the two consumers it feeds.

Owner ruling 2026-09-02 08:20 (HANDOFF 6 / 5bf): the 18k run's elixir>=6 share fell 2% -> 0.02%
and three wait-side reward terms are dead at 3 seeds, so the fix is a cross-entropy pull of the
GATE head toward a pro P(play | elixir bucket, phase) table. These tests pin what can go wrong
silently: the elixir reconstruction (start 5, four-phase regen, CardDB cost), the phase boundaries
(the ENGINE's, not a guess), the term's direction, and the watchdog floor that would otherwise
make the elixir>=6 drift rule dead on arrival.
"""
import csv
import importlib.util
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Cfg:
    """Only what fit() reads: sim.agent_dt / regulation_s / overtime_s."""
    def get(self, sec, key, default=None):
        return {"agent_dt": 0.6, "regulation_s": 180.0, "overtime_s": 120.0}.get(key, default)


class _DB:
    COST = {"knight": 3, "fireball": 4, "mighty_miner_ability": 1, "tesla": 4}
    KIND = {"knight": "troop", "fireball": "spell", "tesla": "building"}

    def elixir(self, name):
        return self.COST.get(name)

    def kind(self, name):
        return self.KIND.get(name)


def _csv(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
    w = csv.DictWriter(f, fieldnames=["replay_tag", "attr_s", "seconds", "attr_card", "attr_ability"])
    w.writeheader()
    for r in rows:
        w.writerow(r)
    f.close()
    return Path(f.name)


class TestPhaseAndRate(unittest.TestCase):
    def test_boundaries_are_the_engines(self):
        gp = _load("gate_prior")
        reg, ot = 180.0, 120.0
        self.assertEqual(gp._phase(0.0, reg, ot), "single")
        self.assertEqual(gp._phase(119.9, reg, ot), "single")
        self.assertEqual(gp._phase(120.0, reg, ot), "double")      # reg - 60
        self.assertEqual(gp._phase(239.9, reg, ot), "double")      # overtime's first minute is still double
        self.assertEqual(gp._phase(240.0, reg, ot), "triple")      # reg + (ot - 60)
        self.assertAlmostEqual(gp._rate(0.0, reg, ot), 1 / 2.8)
        self.assertAlmostEqual(gp._rate(150.0, reg, ot), 1 / 1.4)
        self.assertAlmostEqual(gp._rate(250.0, reg, ot), 1 / 0.93)

    def test_evo_and_hero_suffixes_strip(self):
        gp = _load("gate_prior")
        self.assertEqual(gp._base("knight-ev1"), "knight")
        self.assertEqual(gp._base("knight-hero"), "knight")
        self.assertEqual(gp._base("ice-spirit"), "ice-spirit")


class TestFit(unittest.TestCase):
    def test_elixir_is_reconstructed_and_undercost_is_counted(self):
        """Start 5, knight at t=0 -> 2 left; a fireball 2 s later needs 4, has 2.7: UNDER cost."""
        gp = _load("gate_prior")
        src = _csv([
            {"replay_tag": "r1", "attr_s": "blue", "seconds": "0.1", "attr_card": "knight", "attr_ability": "0"},
            {"replay_tag": "r1", "attr_s": "blue", "seconds": "2.0", "attr_card": "fireball", "attr_ability": "0"},
            {"replay_tag": "r1", "attr_s": "red", "seconds": "3.0", "attr_card": "knight", "attr_ability": "0"},
        ])
        pr = gp.fit(src, _Cfg(), _DB(), side="blue")
        self.assertEqual(pr["replays"], 1)
        self.assertEqual(pr["plays"], 2)                          # red's play is not the crawled side
        self.assertAlmostEqual(pr["reconstruction_under_cost_frac"], 0.5)
        self.assertEqual(pr["unpriced"], {})
        # first window starts at 5 elixir with a play in it
        self.assertEqual(pr["play_windows"]["single"][5], 1)
        self.assertGreater(sum(pr["windows"]["single"]), 0)

    def test_ability_rows_are_priced_as_the_ability(self):
        gp = _load("gate_prior")
        src = _csv([
            {"replay_tag": "r1", "attr_s": "blue", "seconds": "1.0", "attr_card": "_invalid", "attr_ability": "1"},
        ])
        pr = gp.fit(src, _Cfg(), _DB(), side="blue")
        self.assertEqual(pr["plays"], 1)
        self.assertEqual(pr["unpriced"], {})
        self.assertEqual(pr["reconstruction_under_cost_frac"], 0.0)

    def test_banking_shape_is_readable_from_the_table(self):
        """A player who never plays below 9 elixir produces p_play 0 at 0..8 and >0 at 9/10."""
        gp = _load("gate_prior")
        rows = []
        t = 0.0
        for k in range(9):                      # a knight every 12 s: regen 12/2.8 = 4.3 > 3
            t += 12.0
            rows.append({"replay_tag": "r1", "attr_s": "blue", "seconds": f"{t:.1f}",
                         "attr_card": "knight", "attr_ability": "0"})
        pr = gp.fit(_csv(rows), _Cfg(), _DB(), side="blue")
        tbl = pr["p_play"]
        self.assertEqual(sum(tbl["single"][:7]), 0.0)
        self.assertGreater(tbl["single"][10] + tbl["single"][9], 0.0)
        self.assertEqual(sum(pr["windows"]["double"]), 0, "no double-elixir windows before 120 s")


class TestPressureKey(unittest.TestCase):
    """Schema 2 (HANDOFF 5bw/5bx): the ruling's dropped third key. Pressure = the OPPONENT played a
    TROOP within W s. Spells and buildings are not pressure; the blended p_play is unchanged; the
    trainer's array is [phase, pressure, bucket] and refuses a table fit at another W."""

    def _rows(self):
        return [
            {"replay_tag": "r1", "attr_s": "red", "seconds": "3.1", "attr_card": "knight-ev1", "attr_ability": "0"},
            {"replay_tag": "r1", "attr_s": "red", "seconds": "20.0", "attr_card": "fireball", "attr_ability": "0"},
            {"replay_tag": "r1", "attr_s": "red", "seconds": "30.0", "attr_card": "tesla", "attr_ability": "0"},
            {"replay_tag": "r1", "attr_s": "blue", "seconds": "4.0", "attr_card": "knight", "attr_ability": "0"},
            {"replay_tag": "r1", "attr_s": "blue", "seconds": "40.0", "attr_card": "knight", "attr_ability": "0"},
        ]

    def test_pressure_windows_are_the_troop_ones_only(self):
        gp = _load("gate_prior")
        pr = gp.fit(_csv(self._rows()), _Cfg(), _DB(), side="blue", pressure_s=6.0)
        self.assertEqual(pr["schema"], 2)
        self.assertEqual(pr["pressure_s"], 6.0)
        self.assertEqual(pr["unknown_kind"], {})
        wp = pr["windows_by_pressure"]["single"]
        # the red knight at 3.1 s flags the windows starting in [3.1, 9.1): 3.6 .. 9.0, 10 of them
        # at dt 0.6; the fireball (spell) and tesla (building) flag none. (3.1, not 3.0: window
        # starts accumulate 0.6 in floating point and a play ON a boundary is a rounding coin-flip.)
        self.assertEqual(sum(wp["pressure"]), 10)
        self.assertEqual(sum(wp["quiet"]) + sum(wp["pressure"]), sum(pr["windows"]["single"]))
        # blue's play at 4.0 s falls in a pressured window; the one at 40.0 s in a quiet one
        self.assertEqual(sum(pr["play_windows_by_pressure"]["single"]["pressure"]), 1)
        self.assertEqual(sum(pr["play_windows_by_pressure"]["single"]["quiet"]), 1)

    def test_blend_is_unchanged_by_the_split(self):
        gp = _load("gate_prior")
        p1 = gp.fit(_csv(self._rows()), _Cfg(), _DB(), side="blue")
        p2 = gp.fit(_csv(self._rows()), _Cfg(), _DB(), side="blue", pressure_s=6.0)
        self.assertEqual(p1["schema"], 1)
        self.assertEqual(p1["p_play"], p2["p_play"])
        self.assertEqual(p1["windows"], p2["windows"])
        self.assertNotIn("p_play_by_pressure", p1)

    def test_thin_cells_fall_back_to_the_blend(self):
        """Every cell here has < MIN_CELL_N windows, so the split table must equal the blend."""
        gp = _load("gate_prior")
        pr = gp.fit(_csv(self._rows()), _Cfg(), _DB(), side="blue", pressure_s=6.0)
        for key in gp.PRESSURE_KEYS:
            self.assertEqual(pr["p_play_by_pressure"]["single"][key], pr["p_play"]["single"])

    def test_prior_array_shape_and_w_guard(self):
        gp = _load("gate_prior")
        pr = gp.fit(_csv(self._rows()), _Cfg(), _DB(), side="blue", pressure_s=6.0)
        self.assertEqual(gp.prior_array(pr, 0.0).shape, (3, 11))
        self.assertEqual(gp.prior_array(pr, 6.0).shape, (3, 2, 11))
        with self.assertRaises(AssertionError):
            gp.prior_array(pr, 10.0)                       # a table fit at 6 s is not a 10 s prior
        p1 = gp.fit(_csv(self._rows()), _Cfg(), _DB(), side="blue")
        with self.assertRaises(AssertionError):
            gp.prior_array(p1, 6.0)                        # schema 1 has no split

    def test_sim_key_is_the_youngest_living_enemy_troop(self):
        """SimMatchEnv.enemy_troop_min_age: 1e9 on an empty board, the youngest enemy TROOP's age
        otherwise; enemy buildings, own troops and dead troops do not count."""
        try:
            from clashrl.config import Config
            from clashrl.sim.engine import Unit, build_spec
            from clashrl.sim.env import SimMatchEnv
        except Exception as e:
            self.skipTest(f"sim env import: {e}")
        env = SimMatchEnv(Config.load()); env.reset()
        e = env.eng
        e.units.clear(); e.spells.clear(); e.projectiles.clear()
        self.assertEqual(env.enemy_troop_min_age(), 1e9)

        def spawn(key, team, y, age=0.0, hp=None):
            s = build_spec(e.db, key, 11)
            u = Unit(spec=s, team=team, x=0.3, y=y, hp=s.hp if hp is None else hp)
            u.age = age
            e.units.append(u)
            return u

        spawn("knight", 0, 0.6, age=1.0)                           # ours: not pressure
        spawn("tesla", 1, 0.4, age=0.5)                            # their building: not pressure
        self.assertEqual(env.enemy_troop_min_age(), 1e9)
        old = spawn("knight", 1, 0.3, age=9.0)
        self.assertAlmostEqual(env.enemy_troop_min_age(), 9.0)
        young = spawn("valkyrie", 1, 0.35, age=2.5)
        self.assertAlmostEqual(env.enemy_troop_min_age(), 2.5)
        young.hp = 0.0                                             # dead: not pressure
        self.assertAlmostEqual(env.enemy_troop_min_age(), 9.0)
        # ...and age advances with the engine, so the key expires on its own
        e.advance(0.6)
        self.assertGreater(env.enemy_troop_min_age(), 9.0)
        del old


class TestWatchdogFloor(unittest.TestCase):
    def test_elixir_rule_arms_at_its_own_floor(self):
        """The shared min_peak 0.05 is a P(play) scale; elixir>=6 medians on the 18k run were
        ~0.02, so without a per-label floor the rule can NEVER fire. With 0.002 it does."""
        try:
            wd = _load("ppo_watchdog")
        except Exception as e:                                   # torch/env missing
            self.skipTest(f"ppo_watchdog import: {e}")
        if not hasattr(wd, "_Drift") or not hasattr(wd._Drift(), "min_peak_by_label"):
            self.skipTest("this deck's watchdog has no per-label floor (hogeq has no _Drift)")
        dead = wd._Drift()
        live = wd._Drift(min_peak_by_label={"ELIXIR>=6": 0.002})
        series = [0.020, 0.021, 0.019, 0.022, 0.020, 0.018, 0.021, 0.005]
        self.assertEqual([m for v in series if (m := dead.check("ELIXIR>=6", v, 6000))], [])
        fired = [m for v in series if (m := live.check("ELIXIR>=6", v, 6000))]
        self.assertEqual(len(fired), 1)
        self.assertIn("ELIXIR>=6 DRIFT", fired[0])
        # and the GATE rule is untouched by the per-label dict
        g = wd._Drift(min_peak_by_label={"ELIXIR>=6": 0.002})
        for v in (0.48, 0.50, 0.49, 0.51, 0.50, 0.49):
            self.assertIsNone(g.check("GATE", v, 5000))
        self.assertIsNotNone(g.check("GATE", 0.25, 5000))


class TestTermMath(unittest.TestCase):
    def test_cross_entropy_pulls_toward_the_prior(self):
        """The trainer's term: -(p log pi_play + (1-p) log pi_wait). Its gradient on the play
        logit is (pi_play - p): positive (push DOWN) when the policy plays more than the pros."""
        try:
            import torch
        except Exception as e:
            self.skipTest(f"torch: {e}")
        logit = torch.tensor([[0.0, 2.0]], requires_grad=True)   # pi_play = 0.88
        lp = torch.log_softmax(logit, dim=1)
        p = torch.tensor([0.06])                                  # pros at 4 elixir, single
        ce = -(p * lp[:, 1] + (1 - p) * lp[:, 0]).mean()
        ce.backward()
        self.assertGreater(float(logit.grad[0, 1]), 0.0, "play logit must be pushed DOWN")
        self.assertAlmostEqual(float(logit.grad[0, 1]),
                               float(torch.sigmoid(torch.tensor(2.0))) - 0.06, places=5)
        # ...and the term is minimised exactly at pi_play = p
        best = torch.tensor([[math.log(1 - 0.06), math.log(0.06)]])
        lp2 = torch.log_softmax(best, dim=1)
        ce2 = -(p * lp2[:, 1] + (1 - p) * lp2[:, 0]).mean()
        self.assertLess(float(ce2), float(ce))


if __name__ == "__main__":
    unittest.main()
