"""Sim-side elixir-trade event ledger + threat-response timing port (2026-08-14). The sim grades
with engine ground truth (exact unit identities, exact crossing times), so these drive real
SimMatchEnv instances: deploy units, control the clock, and read the reward stream."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np                                  # noqa: E402
from clashrl.config import Config                   # noqa: E402
from clashrl.sim.env import SimMatchEnv             # noqa: E402
from clashrl.sim.engine import build_spec           # noqa: E402


def _quiet_env(seed=42):
    env = SimMatchEnv(Config.load(), seed=seed)
    env.reset()
    env.opponent.act = lambda eng: None              # deterministic board: the bot stays silent
    return env


def _total(env, name):
    t = env.rw_stats.run.get(name)
    return 0.0 if t is None else t.total


def _kill(env, unit):
    unit.hp = -1.0                                   # engine culls it on the next tick


class TradeLedgerTests(unittest.TestCase):
    def test_prompt_attributed_kill_credits(self):
        env = _quiet_env()
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.62)
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.52, 0.60)
        foe = [u for u in env.eng.units if u.team == 1][-1]
        env.step((False, 0, 0))                      # both tracked; crossing stamped on first sight
        _kill(env, foe)
        env.step((False, 0, 0))                      # dies ~1 s after crossing: inside the grace
        self.assertGreater(_total(env, "elixir_trade"), 0.2,
                           "a 3-elixir kill next to our knight, answered promptly, must credit")

    def test_tower_kill_far_from_units_pays_nothing(self):
        env = _quiet_env(seed=43)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.80, 0.60)
        for _ in range(30):                          # no unit of ours ever fields; towers do the work
            env.step((False, 0, 0))
            if not any(u.team == 1 for u in env.eng.units):
                break
        env.step((False, 0, 0))
        self.assertEqual(_total(env, "elixir_trade"), 0.0,
                         "the towers' kill with nothing of ours nearby is not the policy's trade")

    def test_late_kill_decays_to_zero(self):
        env = _quiet_env(seed=44)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.62)
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.52, 0.60)
        foe = [u for u in env.eng.units if u.team == 1][-1]
        env.step((False, 0, 0))
        # rewrite the ledger so the crossing happened 15 s ago: the answer is ELEVEN+ seconds late
        env._ev_enemy = {uid: (sh, x, y, (tc - 15.0 if tc is not None else None))
                         for uid, (sh, x, y, tc) in env._ev_enemy.items()}
        base = _total(env, "elixir_trade")
        _kill(env, foe)
        env.step((False, 0, 0))
        self.assertAlmostEqual(_total(env, "elixir_trade") - base, 0.0, delta=1e-6,
                               msg="a kill >= trade_late_s after the crossing credits nothing")

    def test_own_troop_loss_debits(self):
        env = _quiet_env(seed=45)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.70)
        mine = [u for u in env.eng.units if u.team == 0][-1]
        env.step((False, 0, 0))
        _kill(env, mine)
        env.step((False, 0, 0))
        self.assertLess(_total(env, "elixir_trade"), -0.2,
                        "our dead knight = -0.3, whoever killed it")

    def test_spell_kill_credits_without_a_nearby_unit(self):
        env = _quiet_env(seed=46)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.70, 0.60)
        foe = [u for u in env.eng.units if u.team == 1][-1]
        env.step((False, 0, 0))
        env._ev_spells.append((0.70, 0.60, 2.0, env.eng.t))   # our rocket just landed here
        base = _total(env, "elixir_trade")
        _kill(env, foe)
        env.step((False, 0, 0))
        self.assertGreater(_total(env, "elixir_trade") - base, 0.2,
                           "a kill inside a recent damage-spell blast is OUR kill, no troop needed")

    def test_playing_a_damage_spell_records_a_cast(self):
        for seed in range(60):                       # find a seed whose opening hand holds a spell
            env = _quiet_env(seed=seed)
            spells = [ci for ci in env._hand_ids() if ci in env.damage_spell_ids]
            if spells:
                break
        self.assertTrue(spells, "no seed in 60 gave an opening damage spell (deck has 2)")
        env.eng.elixir[0] = 10.0
        for cell in (117, 153, 225, 315):            # first legal placement wins
            env.step((True, spells[0], cell))
            if env._ev_spells:
                break
        self.assertTrue(env._ev_spells, "a fielded damage spell must be recorded for attribution")


class ThreatTimingTests(unittest.TestCase):
    def _lit_env(self, seed=50):
        env = _quiet_env(seed=seed)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.30, 0.58)
        env.step((False, 0, 0))                      # _observe refreshes the true threat vector
        assert env._threat_id_true[0] >= 0.5, "an enemy knight on our half must light the threat"
        return env

    def _troop_counter(self, env):
        ci = next(i for i, k in enumerate(env.deck_keys) if "knight" in k)
        tid = env._threat_id_true
        tx, _ = env._threat_pos()
        return ci, tid, tx

    def test_depth_window_gates_positives(self):
        env = self._lit_env()
        ci, tid, tx = self._troop_counter(env)
        tid[7] = 0.40
        mid = env._threat_response(ci, tx, 0.60)
        self.assertGreater(mid, 0.0, "counter + intercept + mid depth must pay")
        env._threat_credits = 0
        tid[7] = 0.05
        self.assertEqual(env._threat_response(ci, tx, 0.60), 0.0,
                         "below min depth = premature: the push is still building")
        tid[7] = 0.90
        self.assertEqual(env._threat_response(ci, tx, 0.60), 0.0,
                         "above max depth = too late: the threat is already on our tower")

    def test_budget_caps_and_hysteresis_refills(self):
        env = self._lit_env(seed=51)
        ci, tid, tx = self._troop_counter(env)
        tid[7] = 0.40
        self.assertGreater(env._threat_response(ci, tx, 0.60), 0.0)
        self.assertGreater(env._threat_response(ci, tx, 0.60), 0.0)
        self.assertEqual(env._threat_response(ci, tx, 0.60), 0.0,
                         "third credit for the same push: the budget is spent")
        for u in list(env.eng.units):                # the push dies; the board goes quiet
            if u.team == 1:
                _kill(env, u)
        for _ in range(5):                           # >= 3 s of sustained engine-time quiet
            env.step((False, 0, 0))
        self.assertEqual(env._threat_credits, 0, "sustained quiet must refill the budget")
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.30, 0.58)
        env.step((False, 0, 0))
        env._threat_id_true[7] = 0.40
        _, _, tx = self._troop_counter(env)
        self.assertGreater(env._threat_response(ci, tx, 0.60), 0.0,
                           "a fresh push after the reset earns fresh credit")

    def test_building_defensive_geometry(self):
        env = self._lit_env(seed=52)
        bi = next(i for i, k in enumerate(env.deck_keys) if "tesla" in k)
        env._threat_id_true[7] = 0.40
        self.assertGreater(env._threat_response(bi, 0.50, 0.65), 0.0,
                           "central tesla in the defensive band pays")
        env._threat_credits = 0
        self.assertEqual(env._threat_response(bi, 0.50, 0.30), 0.0,
                         "a building on the OFFENSIVE half is not a defense")
        self.assertEqual(env._threat_response(bi, 0.50, 0.92), 0.0,
                         "a building jammed at the king is past the pull geometry")


if __name__ == "__main__":
    unittest.main(verbosity=1)
