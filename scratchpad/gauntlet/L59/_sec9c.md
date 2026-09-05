`python -m unittest discover -s tests -t .` after ALL edits (rulings + the s9.7 seam fix):
`Ran 1332 tests in 341.218s -- FAILED (failures=1, skipped=21)`; the one failure is the same pre-existing
`test_xbow_into_push.XbowIntoPushTests.test_the_clamped_frontmost_ROW_counts_as_forward` (0.5625 < 0.625,
fails identically on the untouched HEAD tree, s8). Identical pass/fail set to s9.6 (1332 tests, 1 fail,
21 skipped); the only difference is the wiring test's body. Suite time 341 s vs 331 s (v2), n=1 each.

## 10. File index (all under `C:/Users/benpe/ClashBot/`)
- Edited: `icebow/src/clashrl/geometry_reward.py`, `icebow/src/clashrl/sim/env.py`,
  `icebow/src/clashrl/config.py` (additive `source`), `icebow/src/clashrl/sim/remote_pool.py`,
  `icebow/src/clashrl/train_sim_ppo.py` (`worker_config_args` + the RemotePool call),
  `icebow/config/config.yaml` (block added only, 1270-1276), `icebow/tests/test_geometry_reward.py`;
  new `icebow/tests/test_geometry_wiring.py`. `cli.py` and the live `src/clashrl/env.py`: untouched.
- L59 scratch (`scratchpad/gauntlet/L59/`): `gate_replay.py`, `gate_analyze.py`, `gate_summary.txt`,
  `gate_run.log`, `p1/` (gate_plays.csv, gate_tesla_probe.csv, drive_summary.jsonl);
  test outputs `test_geometry_reward.txt`, `test_geometry_wiring.txt` (b-era), `test_geometry_wiring_v3.txt`
  (current); reference `reward_ref.py`, `reward_ref.npy` (non-trade, from the HEAD tree in `_head/`),
  `reward_ref_total_v1.npy` (old total-reward ref); suites `suite_before.txt`, `suite_after.txt`,
  `suite_after_v2.txt`, `suite_after_v3.txt` (final); probes `geo_probe.py/.txt/_v2.txt`,
  `geo_probe2.py/.txt/_v2.txt`, `geo_scenario.py/.txt/_v2.txt`; seam bisect `_seam.py`, `_seam2.py`,
  `_seam3.py`; `cfg_armG.yaml`; patch scripts `_patch_a.py`, `_patch_tests.py`, `_patch_env.py`,
  `_patch_rulings.py`; section drafts `_sec9.md`, `_sec9b.md`, `_sec9c.md`; `_head/` = `git archive HEAD
  icebow/src/clashrl` (read-only, for the reference recording). Pre-existing L59 files not mine:
  `armE_T3.txt`, `arm_gates.py`, `cell_sat_probe.*`, `make_armE_ckpt.py`.

STATUS: complete
