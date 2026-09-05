"""L59 step 1: the geometry reward wired into the sim env (arm G) -- regression + smoke.

(1) `env.geometry.enabled: false` (the committed default) must leave the per-step reward sequence of
    two seeded matches under a FIXED random action stream byte-identical to the pre-wiring code. The
    reference was recorded BEFORE the edit by `scratchpad/gauntlet/L59/reward_ref.py` into
    `scratchpad/gauntlet/L59/reward_ref.npy` (same driver, same seeds, same stream).
(2) `env.geometry.enabled: true`: the same stream runs without exceptions and the reward ledger holds
    `geo_*` keys; per-key fire count and sum are printed per match.
"""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config            # noqa: E402
from clashrl.sim.env import SimMatchEnv      # noqa: E402

REF = Path(__file__).resolve().parents[2] / "scratchpad" / "gauntlet" / "L59" / "reward_ref.npy"
SEEDS = (7, 11)
HOLD_P = 0.2
MAX_STEPS = 400


def fixed_stream_action(env, rng: random.Random):
    """A legal action from a PRIVATE rng (not env.rng, so the stream cannot be moved by the env's
    own draws): hold with HOLD_P, else a random affordable card on a random deployable cell."""
    hand = [i for i, v in enumerate(env.hand_vec) if v >= 0.5
            and env.specs[i].elixir <= env.eng.elixir[0]]
    if not hand or rng.random() < HOLD_P:
        return (0, 0, 0)
    card = rng.choice(hand)
    cells = [c for c, ok in enumerate(env.actions.deployable_mask(card in env.anywhere_ids)) if ok]
    return (1, card, rng.choice(cells))


def make_cfg(enabled: bool):
    cfg = Config.load()
    geo = cfg.data.setdefault("env", {}).setdefault("geometry", {})
    geo["enabled"] = bool(enabled)
    return cfg


def run_matches(cfg, seeds=SEEDS, max_steps=MAX_STEPS):
    """-> (rewards: list of np.ndarray per match, ledgers: list of match_summary dicts).

    `rewards` is the per-step reward MINUS that step's `elixir_trade` delta. The trade ledger keys
    units by `id(u)` (env.py `_trade_reward`), and CPython reuses a dead object's id for the next
    allocation at the same address -- so ONE step in 512 (seed 7, step 94: a -0.3 trade term on a
    skeletons drop) flips with the process's memory layout (measured: flips after `Config.load()`
    twice, after `random.random()`, after importing remote_pool; L59 wire.md s9). Nothing this test
    guards touches the trade ledger, so it compares the rest of the reward byte-for-byte and reports
    the trade term separately."""
    rewards, ledgers = [], []
    for seed in seeds:
        env = SimMatchEnv(cfg, seed=seed)
        env.reset()
        rng = random.Random(1000 + seed)
        rs = []
        for _ in range(max_steps):
            t0 = env.rw_stats.match["elixir_trade"].total if "elixir_trade" in env.rw_stats.match else 0.0
            _obs, r, done, _info = env.step(fixed_stream_action(env, rng))
            t1 = env.rw_stats.match["elixir_trade"].total if "elixir_trade" in env.rw_stats.match else 0.0
            rs.append(float(r) - (t1 - t0))
            if done:
                break
        rewards.append(np.asarray(rs, dtype=np.float64))
        ledgers.append(env.rw_stats.match_summary())
    return rewards, ledgers


class GeometryWiring(unittest.TestCase):
    def test_disabled_is_byte_identical(self):
        self.assertTrue(REF.exists(), f"reference missing: {REF} (run scratchpad/gauntlet/L59/reward_ref.py first)")
        ref = np.load(REF, allow_pickle=True)
        rewards, _ = run_matches(make_cfg(False))
        self.assertEqual(len(rewards), len(ref))
        for i, (a, b) in enumerate(zip(rewards, ref)):
            self.assertEqual(len(a), len(b), f"match {i}: step count {len(a)} vs ref {len(b)}")
            # 1e-9 absolute: subtracting the trade delta leaves float residue (5.6e-17 measured)
            same = np.allclose(a, b, rtol=0.0, atol=1e-9)
            if not same:
                bad = np.nonzero(~np.isclose(a, b, rtol=0.0, atol=1e-9))[0]
                self.fail(f"match {i}: {len(bad)} of {len(a)} steps differ; first at step {bad[0]}: "
                          f"{a[bad[0]]!r} vs ref {b[bad[0]]!r}")
            print(f"[wiring] match {i} seed {SEEDS[i]}: {len(a)} steps, non-trade reward sum {a.sum():+.4f}, identical to ref")

    def test_enabled_runs_and_logs_geo_terms(self):
        rewards, ledgers = run_matches(make_cfg(True))
        any_geo = False
        for i, led in enumerate(ledgers):
            terms = led["terms"]
            geo = {k: v for k, v in terms.items() if k.startswith("geo_")}
            any_geo = any_geo or bool(geo)
            print(f"[wiring] ENABLED match {i} seed {SEEDS[i]}: {len(rewards[i])} steps, "
                  f"reward sum {rewards[i].sum():+.4f}, geo keys {len(geo)}")
            for k in sorted(geo):
                t = geo[k]
                print(f"    {k:<20} fires {t['fires']:>4}  sum {t['total']:+9.4f}  (+{t['pos']} / -{t['neg']})")
        self.assertTrue(any_geo, "no geo_* key fired in the ledger with geometry enabled")


class GeometryReachesWorkers(unittest.TestCase):
    """Part C (lead amendment): the rollout workers are spawned processes that load their own
    Config; they used to call `Config.load()` -- config.yaml from disk -- so a `--config <run yaml>`
    reached the learner and its local twin but not one rollout env. Now the parent's config FILE
    (`Config.source`) plus its in-memory overrides (--size grid, --drill-only) cross the pipe
    (`train_sim_ppo.worker_config_args` -> `RemotePool` -> `_worker`).

    Proof through the REAL CLI path: the real parser parses `--config cfg_armG.yaml train-sim-ppo
    --workers 1 ...`, the real `_cmd_train_sim_ppo` builds the cfg (with its _KeyOverride wrappers),
    `train_sim_ppo` is stubbed to CAPTURE that cfg instead of training, and a 1-worker RemotePool
    built with exactly `worker_config_args(cfg)` reports, from inside the worker, geometry ON while
    config.yaml on disk says OFF -- and OFF with no --config."""

    ARM_G = Path(__file__).resolve().parents[2] / "scratchpad" / "gauntlet" / "L59" / "cfg_armG.yaml"

    def _cfg_from_cli(self, argv):
        """Run the real CLI up to the training call and return the cfg it would train with."""
        import clashrl.cli as cli
        import clashrl.train_sim_ppo as tsp
        captured = {}

        def _stub(cfg, **kw):
            captured["cfg"] = cfg
            captured["kw"] = kw
        real = tsp.train_sim_ppo
        real_argv = sys.argv
        tsp.train_sim_ppo = _stub
        sys.argv = ["clashrl"] + list(argv)
        try:
            cli.main()
        finally:
            tsp.train_sim_ppo = real
            sys.argv = real_argv
        self.assertIn("cfg", captured, "the CLI never reached train_sim_ppo")
        return captured["cfg"], captured["kw"]

    def _probe(self, cfg):
        from clashrl.sim.remote_pool import RemotePool
        from clashrl.train_sim_ppo import worker_config_args
        args = worker_config_args(cfg)
        pool = RemotePool(1, 1, seed=5, drill_frac=0.0, spell_min_value=0.0, **args)
        try:
            return args, pool.probe()
        finally:
            pool.close()

    def test_override_reaches_the_worker_env(self):
        from clashrl.config import Config
        disk = Config.load().get("env", "geometry", "enabled", default=False)
        self.assertFalse(bool(disk), "this test assumes config.yaml ships env.geometry.enabled: false")
        self.assertTrue(self.ARM_G.is_file(), f"missing {self.ARM_G}")
        tail = ["train-sim-ppo", "--workers", "1", "--envs", "1", "--matches", "1",
                "--out", "C:/nonexistent/armG_probe.pt", "--drill-only", "tesla_pulls_the_wincon",
                "--size", "432"]
        # (1) --config cfg_armG.yaml: the worker must load THAT file (geometry ON) and also see the
        #     parent's --size grid and --drill-only override, which live only in the parent's memory
        cfg, kw = self._cfg_from_cli(["--config", str(self.ARM_G)] + tail)
        self.assertEqual(kw.get("workers"), 1)
        args, got = self._probe(cfg)
        print(f"[wiring] --config cfg_armG.yaml --workers 1: shipped {args}")
        print(f"[wiring]   worker probe: {got[0]}")
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["geo_enabled"], got[0])
        self.assertEqual(Path(got[0]["config_source"]).resolve(), self.ARM_G.resolve())
        self.assertEqual(got[0]["geometry"], cfg.get("env", "geometry"))
        self.assertEqual(list(got[0]["grid"]), [18, 24])
        self.assertEqual(list(got[0]["drill_only"]), ["tesla_pulls_the_wincon"])
        # the --out _KeyOverride is a parent-only key; it must not have leaked into the worker's cfg
        self.assertEqual(str(cfg.get("train", "sim_ppo_checkpoint")), "C:/nonexistent/armG_probe.pt")
        # (2) no --config: the worker loads config.yaml (geometry OFF), the pre-L59 behaviour
        cfg0, _ = self._cfg_from_cli(tail)
        args0, got0 = self._probe(cfg0)
        print(f"[wiring] no --config --workers 1: shipped {args0}")
        print(f"[wiring]   worker probe: {got0[0]}")
        self.assertFalse(got0[0]["geo_enabled"], got0[0])
        self.assertEqual(Path(got0[0]["config_source"]).resolve(),
                         (Path(__file__).resolve().parents[1] / "config" / "config.yaml").resolve())
        # (3) a hand-built Config (no source) -> the worker falls back to Config.load()
        from clashrl.sim.remote_pool import RemotePool
        pool = RemotePool(1, 1, seed=5, drill_frac=0.0, spell_min_value=0.0)
        try:
            got2 = pool.probe()
        finally:
            pool.close()
        print(f"[wiring] nothing shipped: {got2[0]}")
        self.assertFalse(got2[0]["geo_enabled"], got2[0])


if __name__ == "__main__":
    unittest.main()
