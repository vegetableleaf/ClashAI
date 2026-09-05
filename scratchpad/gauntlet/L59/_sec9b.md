`python -m unittest discover -s tests -t .` with the s9.1 rulings applied (before the s9.7 amendment):
`Ran 1332 tests in 330.651s -- FAILED (failures=1, skipped=21)`; the one failure is the pre-existing
`test_xbow_into_push.XbowIntoPushTests.test_the_clamped_frontmost_ROW_counts_as_forward` (0.5625 < 0.625,
fails identically on the untouched HEAD tree, s8). 1332 = 1331 (s8) + the worker test. Nothing else changed.

### 9.7 Lead amendment to Part C -- the seam fixed generally (config PATH + parent overrides, not one dict)
**Does `Config` record its source?** No: `config.py` `Config` was `data` + `root` only; `load()` computed
`cfg_path` and dropped it. Added (additive, `src/clashrl/config.py` 16-20, 33):
`source: Optional[Path] = None`, set to `Path(cfg_path).resolve()` by `load()`. Default None keeps the
five `Config(data=..., root=...)` hand-constructors (sim_bench.py, 4 tests) working. The `_KeyOverride` /
`_DrillFracOverride` proxies forward unknown attributes (`__getattr__`), so `getattr(cfg, "source")` on
the wrapped cfg that `_cmd_train_sim_ppo` hands to `train_sim_ppo` resolves to the file `--config` named --
no threading of `args.config` through cli.py was needed, and cli.py is unchanged.

**What crosses the pipe now** (`src/clashrl/train_sim_ppo.py` 112-131 `worker_config_args(cfg)`, used at
185 `RemotePool(..., **worker_config_args(cfg))`):
- `config_path` = `cfg.source` (str) -- the worker does `Config.load(config_path)`; None (hand-built
  Config) -> `Config.load()`, the old behaviour (`remote_pool.py` 66-71).
- `overrides` = `[(key_tuple, value)]` for the parent's IN-MEMORY config changes that no file load can
  see: `("action","grid")` (`--size` mutates `cfg.data` in `_sized_config`) and `("sim","drill_only")`
  (`--drill-only` is a `_KeyOverride` proxy). Resolved values, never sentinels; a None value means
  "absent in the parent too" and is not shipped (setting it would turn a `get(..., default=X)` into None).
  Applied into `cfg.data` in the worker before `make_train_env` (`remote_pool.py` 72-79).
- `drill_frac` and `spell_min_value` keep their explicit arguments exactly as before (not regressed).
- `--out` (`train.sim_ppo_checkpoint`) is a parent-only key (the learner writes the checkpoint); it is
  not shipped and the test asserts the parent still resolves it.
`RemotePool.__init__` (311-317) takes `config_path=None, overrides=None`; spawn args 332-333; the
`("probe",)` reply (292-299) now also reports `config_source`, `grid`, `drill_only` from inside the worker.

**Pre-existing seam defects this closes (measured by the probe's "no --config" / "nothing shipped" rows):**
(1) EVERY env-side key of a `--config` run yaml stopped at the learner -- the parent and its local twin
env ran the yaml, every rollout env ran `config/config.yaml`. For the one run yaml I measured
(`data/bench/c2r_run.yaml`, s7.2) the only env-side key that differs is `observation.lock_aware_targets`,
absent there vs `false` on disk with coded default `false` -- the same value both ways, so THAT run's
rollout envs were not affected; the defect is structural (any env-side key that DOES differ, e.g.
`env.geometry.enabled` for arm G, would have been silently OFF in every worker). (2) `--drill-only <name>` never reached a worker: `drill_env.py` 1155 reads
`sim.drill_only` off the WORKER's cfg, which was the disk value (None) -- so under workers the flag
printed its banner and every drill still ran (the "nothing shipped" probe row shows `drill_only: None`,
which is what HEAD's workers saw). (3) `--size 576` with a 432 config.yaml would have built 576-cell
parent twins over 432-cell worker envs (not exercised; the grid override is shipped now).
Not claimed: whether any past run actually depended on (1)-(3) -- that is a log question for the lead.

**Proof, through the REAL CLI path** (`tests/test_geometry_wiring.py` 109-192 `GeometryReachesWorkers`):
the real argparse parser parses `--config <cfg_armG.yaml> train-sim-ppo --workers 1 --envs 1 --matches 1
--out C:/nonexistent/armG_probe.pt --drill-only tesla_pulls_the_wincon --size 432`; the real
`_cmd_train_sim_ppo` builds the cfg (with its `_KeyOverride` wrappers); `train_sim_ppo` is stubbed to
CAPTURE that cfg instead of training (no env built in the parent, nothing written); then a 1-worker
`RemotePool(1, 1, seed=5, drill_frac=0.0, spell_min_value=0.0, **worker_config_args(cfg))` is spawned
and probed. Output (`test_geometry_wiring_v3.txt`, verbatim, paths shortened):
```
[cli] --size 432 -> action.grid [18, 24]
[train-sim-ppo] checkpoint -> C:/nonexistent/armG_probe.pt
[train-sim-ppo] DRILL-ONLY: tesla_pulls_the_wincon
[wiring] --config cfg_armG.yaml --workers 1: shipped {'config_path': '...\\L59\\cfg_armG.yaml', 'overrides': [(('action', 'grid'), [18, 24]), (('sim', 'drill_only'), ['tesla_pulls_the_wincon'])]}
[wiring]   worker probe: {'geo_enabled': True, 'geometry': {'enabled': True, 'w_geom': 2.0, 'w_time': 1.0, 'pre_place_s': 3.0, 'p7_enabled': False, 'log_all_terms': True}, 'config_source': '...\\L59\\cfg_armG.yaml', 'grid': [18, 24], 'drill_only': ['tesla_pulls_the_wincon'], 'cls': 'SimMatchEnv'}
[wiring] no --config --workers 1: shipped {'config_path': '...\\icebow\\config\\config.yaml', 'overrides': [(('action', 'grid'), [18, 24]), (('sim', 'drill_only'), ['tesla_pulls_the_wincon'])]}
[wiring]   worker probe: {'geo_enabled': False, 'geometry': {'enabled': False, ...}, 'config_source': '...\\icebow\\config\\config.yaml', 'grid': [18, 24], 'drill_only': ['tesla_pulls_the_wincon'], 'cls': 'SimMatchEnv'}
[wiring] nothing shipped: {'geo_enabled': False, 'geometry': {'enabled': False, ...}, 'config_source': '...\\icebow\\config\\config.yaml', 'grid': [18, 24], 'drill_only': None, 'cls': 'SimMatchEnv'}
```
Asserted: with `--config cfg_armG.yaml` the worker's env has `geo_enabled True`, its `config_source`
IS cfg_armG.yaml, its geometry block equals the parent's, grid [18,24] and drill_only
['tesla_pulls_the_wincon'] arrived; with no `--config` the worker loads config.yaml and reports
`geo_enabled False`; with nothing shipped (hand-built Config) it falls back to `Config.load()`.
n = 1 worker x 1 env per row, 3 rows. `tests.test_geometry_wiring -v`: `Ran 3 tests in 14.351s -- OK`;
the byte-identical regression re-run standalone after ALL edits:
`tests.test_geometry_wiring.GeometryWiring.test_disabled_is_byte_identical` -> `Ran 1 test in 1.329s OK`,
match 0 seed 7 222 steps non-trade sum -10.9461 identical, match 1 seed 11 290 steps -9.1382 identical.
`tests.test_geometry_reward`: `Ran 26 tests in 0.816s -- OK`. Seam-adjacent modules re-run green:
test_spell_card_veto (its source-inspection tests of train_sim_ppo / remote_pool), test_wincon_bank,
test_aggro_drills, test_lock_aware_targets, test_nado_retarget_reach, test_bot_attack_floor
(the direct `Config(data=, root=)` constructors) -- `OK`.

**Arm G launch after the amendment** -- the s9.5 line is unchanged and is now the mechanism itself:
`cd /c/Users/benpe/ClashBot/icebow && PYTHONHASHSEED=0 .venv/Scripts/python.exe run.py --config C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/cfg_armG.yaml train-sim-ppo --out data/policy_armG.pt --seed 41 --envs 96 --workers 12 --size 432 --device cuda --search-interval 4 --matches <N>`
Every key of `cfg_armG.yaml` (a full config.yaml copy, only `env.geometry.enabled: true` differs) now
reaches all 12 workers because each loads that same file; no per-key shipping. The control arm is the
same line without `--config` (or with a full copy that keeps `enabled: false`). NOT started.
Footprint: `git diff --stat -- src tests config`: 7 files, +415/-23 (+ untracked
`tests/test_geometry_wiring.py`); no `data/` change; live `src/clashrl/env.py` untouched; no commits.

### 9.8 Full suite after the amendment (`suite_after_v3.txt`)
