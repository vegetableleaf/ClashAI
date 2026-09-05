
## 9. Lead rulings on the s6 flags -- APPLIED (this section supersedes s5.2/5.3/5.5, s7.3 and the s8 suite line)

### 9.1 What changed (all `L59` hunks; `git diff --stat -- src tests config`: 6 files, +369/-21)
- **6.1** `src/clashrl/sim/env.py` 1040-1052 `_geo_credit`: `credit = (w_time*P5 + w_geom*place*gate) if place > 0 else 0.0`
  where `place = placement_credit(terms, kind, p7_enabled)`. A right-role card with no positive placement
  part (troop behind the king; a building once `pull_ok` = 0 and P6 = 0) earns nothing, timing included.
- **6.2** kept: the gate's late edge stays `t_hit + 1.0`; `deep_ok` NOT re-added on the geometry path.
- **6.3** `src/clashrl/geometry_reward.py` 662-680 `placement_credit(building)`: the close term is now
  `max(FLOOR, p1_close_snapshot)` (the gap to the threat's CURRENT position, i.e. dropping on top of it);
  `p1_close_penalty` (d_path form) is still computed and logged (`geo_p1_close`) but not charged.
  Tests updated: `test_centre_beats_corner` (corner credit 0.85*0.75 = 0.6375, the d_path penalty no longer
  charged), `test_e_placement_credit_bounds` (worst-case dict carries `p1_close_snapshot=-1`).
- **6.4** left as is; recorded (s5.5 scenario rows 1-5: P1 1.0, credit 0 while the hog is on the enemy half).
- **6.5** `src/clashrl/sim/env.py` 1749-1757 X-Bow offensive branch: `val = self.w_wincon * p6_siege`
  (w_wincon 3.0, the weight the flat credit had); `bow_first_frac` (< 30 s) and the split-push /
  hostile-deck factors below it unchanged. Range of the offensive credit is now [0, 3.0] (was flat 3.0).
- **6.6** left.
- **Part C** first done as (b) -- shipping only the resolved `env.geometry` dict -- then SUPERSEDED by the
  lead's amendment (general seam fix, s9.7): no `geometry` kwarg survives in `remote_pool.py` /
  `train_sim_ppo.py` (`grep -n "geometry=" src/clashrl/train_sim_ppo.py src/clashrl/sim/remote_pool.py`
  -> nothing). s9.2 below is the (b)-era test output, kept as the record of that step; s9.7 has the current one.

### 9.2 Test output (verbatim; `test_geometry_reward.txt`, `test_geometry_wiring.txt`)
`python -m unittest tests.test_geometry_reward`: `Ran 26 tests in 0.795s -- OK`.
`python -m unittest tests.test_geometry_wiring -v`:
```
test_override_reaches_the_worker_env (tests.test_geometry_wiring.GeometryReachesWorkers.test_override_reaches_the_worker_env) ... ok
test_disabled_is_byte_identical (tests.test_geometry_wiring.GeometryWiring.test_disabled_is_byte_identical) ... ok
test_enabled_runs_and_logs_geo_terms (tests.test_geometry_wiring.GeometryWiring.test_enabled_runs_and_logs_geo_terms) ... ok

----------------------------------------------------------------------
Ran 3 tests in 11.557s

OK
[wiring] worker probe with the shipped override: {'geo_enabled': True, 'geometry': {'enabled': True, 'w_geom': 2.0, 'w_time': 1.0, 'pre_place_s': 3.0, 'p7_enabled': False, 'log_all_terms': True}, 'cls': 'SimMatchEnv'}
[wiring] worker probe with nothing shipped: {'geo_enabled': False, 'geometry': {'enabled': False, 'w_geom': 2.0, 'w_time': 1.0, 'pre_place_s': 3.0, 'p7_enabled': False, 'log_all_terms': True}, 'cls': 'SimMatchEnv'}
[wiring] match 0 seed 7: 222 steps, non-trade reward sum -10.9461, identical to ref
[wiring] match 1 seed 11: 290 steps, non-trade reward sum -9.1382, identical to ref
[wiring] ENABLED match 0 seed 7: 222 steps, reward sum -10.9461, geo keys 4
    geo_gate             fires   17  sum  +16.9484  (+17 / -0)
    geo_p3               fires    1  sum   +1.0000  (+1 / -0)
    geo_p5               fires    3  sum   +2.9484  (+3 / -0)
    geo_threat_module    fires    8  sum   +8.0000  (+8 / -0)
[wiring] ENABLED match 1 seed 11: 290 steps, reward sum -5.1382, geo keys 8
    geo_credit           fires    2  sum   +6.0000  (+2 / -0)
    geo_gate             fires   24  sum  +23.3333  (+24 / -0)
    geo_p2               fires    1  sum   +1.0000  (+1 / -0)
    geo_p3               fires    7  sum   +4.4157  (+7 / -0)
    geo_p4               fires    1  sum   +0.3333  (+1 / -0)
    geo_p5               fires    7  sum   +6.3333  (+7 / -0)
    geo_paid_module_threat fires    1  sum   +1.0000  (+1 / -0)
    geo_threat_module    fires   11  sum  +11.0000  (+11 / -0)
```
The worker test builds a real 1-worker `RemotePool` (spawned process) with the parent's resolved block
(`enabled: True`) while `config/config.yaml` on disk says `false`: the worker reports `geo_enabled True`
and the shipped block; with nothing shipped it reports the disk value `False`. n = 1 worker x 1 env, each way.
The byte-identical regression was ALSO run standalone after every edit
(`python -m unittest tests.test_geometry_wiring.GeometryWiring.test_disabled_is_byte_identical`): OK,
222 + 290 steps identical to the reference. (The ENABLED sums are "reward sum" as before -- the enabled
test does not subtract the trade term -- match 0 now pays no geometry credit at all: its single paid
credit of s5.4 was the timing-only ice-wizard payment that 6.1 removes.)

### 9.3 A pre-existing nondeterminism found while doing that (NOT caused by this brief; not fixed -- the lead's call)
The first standalone rerun of the byte-identical test after adding the worker test FAILED at one step
(match 0 seed 7 step 94: 0.0 vs ref -0.3), the same step that flipped in discover mode (s6.7). Bisected in
fresh processes (`_seam.py`, n=5 modes): the sequence matches the reference in a bare process and after
`import torch`, but flips after ANY of `random.random()`, `Config.load()` twice, or `import
clashrl.sim.remote_pool` -- i.e. it depends on the process's memory layout, not on the RNG. The differing
term is `elixir_trade` (-0.3 on a skeletons drop at t=57.0 with 6 skeleton-army bodies on the board; same
board and action both ways, `_seam3.py`). `SimMatchEnv._trade_reward` (env.py 2134-2225) keys its
per-unit ledgers by `id(u)`; CPython reuses a dead object's address for the next allocation, so a new
unit can inherit a dead unit's ledger entry depending on allocation history. Consequence for training:
the trade term is ~1-in-500-steps noisy across processes (one step in 512 here) -- small, but it means no
per-step reward sequence is reproducible across processes until the ledger keys on a unit serial
instead of `id()`. Handling here: `run_matches` now records the per-step reward MINUS that step's
`elixir_trade` delta (nothing in this brief touches the trade ledger), the reference was RE-RECORDED
from the untouched HEAD tree (`git archive HEAD icebow/src/clashrl` unpacked to `L59/_head/`, imported
first by `reward_ref.py`, asserted `not hasattr(SimMatchEnv, "_geo_credit")`; old total-reward
reference kept as `reward_ref_total_v1.npy`), and the comparison uses `atol=1e-9` (the subtraction
leaves 5.6e-17 residue). Pre-edit non-trade sums: match 0 -10.9461, match 1 -9.1382; the post-edit
disabled path reproduces both to 1e-9 at every step.

### 9.4 Probes re-run under the rulings (every number from the run; `*_v2.txt`)
- `geo_probe_v2.txt` (the two wiring matches, enabled): paid credits n=2, both +3.000 (skeletons vs giant,
  p3 1.0, p5 1.0). The two timing-only payments of s5.5 (ice_wizard +0.948, skeletons at t=1.8 s +1.000)
  are gone, as 6.1 intends.
- `geo_probe2_v2.txt` (seeds 20..31, 12 ladder matches, 366 scored placements): building scored 4 paid 0;
  troop scored 218 paid 22 (was 27), credit min +0.114 median +2.000 max +3.000, placement part > 0 on
  22/22 (was 18/27), timing part > 0 on 22/22, gate < 1 on 9/22, module-picked threat among the paid 1/22;
  spell scored 144 paid 0 (P4 nonzero 17/144, log-only). P3 nonzero 61/218 (mean 0.533), P5 nonzero
  61/218 (mean 0.817) -- unchanged, they are logged terms.
- `geo_scenario_v2.txt` (Hog down the left lane vs Tesla at (9,21); n=11 enabled + 6 disabled rows):
  ```
  hog tile y   8.5  8.7 11.1 12.3 13.5 | 14.7  15.9  17.1 | 18.3  20.7  23.1
  tid0 (env)     0    0    0    0    0 |    1     1     1 |    1     1     1
  P1 path     1.00 1.00 1.00 1.00 1.00 | 1.00  1.00  1.00 | 0.00  0.00  0.00
  P5          0.00 0.00 0.00 0.07 0.46 | 0.85  1.00  1.00 | 1.00  1.00  1.00
  credit v1   0    0    0    0    0    | 2.848 3.000 3.000 | 1.000 1.000 1.000
  credit v2   0    0    0    0    0    | 2.848 3.000 3.000 | 0     0     0
  old binary  0    -    0    -    0    |   -   0      -    | 1.000 1.000  -
  ```
  After the ruling the Tesla is paid only while the pull is possible (hog tile 14.7-17.1: +2.85/+3.0/+3.0),
  nothing once the hog has locked on the tower (18.3+) and nothing at t_hit 0.1 s -- the late-answer
  payment of flag 6.2 was a timing-only payment and 6.1 removes it for buildings whose pull is gone
  (it remains for a troop counter placed with P3 > 0 late). The old binary's +1.0 at hog 18.3/20.7 is
  the credit the graded version stops paying.
- Credit ranges now: `placement_credit` in [-0.3, 1.0]; env credit for a building/troop is 0 or in
  (0, 3.0] (a positive placement part is required, so the -0.6 floor of s5.3 is unreachable: the snapshot
  close penalty can only reduce a positive P1 credit, and if it drives `place` to <= 0 nothing is paid);
  X-Bow offensive `w_wincon*P6` in [0, 3.0].

### 9.5 How arm G is launched (nothing under `data/` written by me) -- see s9.7 for the mechanism after the amendment
- Mechanism: `run.py --config <full run yaml> train-sim-ppo ...`. The yaml must be a FULL config (the
  flag REPLACES config.yaml) and must CONTAIN the `env.geometry` block with `enabled: true` -- the
  parent resolves it and ships it to every rollout worker; a yaml without the block ships `None` and the
  workers fall back to the disk `config/config.yaml` (`enabled: false`).
- Ready file: `C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/cfg_armG.yaml` = `icebow/config/config.yaml`
  with the single change `env.geometry.enabled: true` (verified by `Config.load`, s7.2). Launch line:
  `cd /c/Users/benpe/ClashBot/icebow && PYTHONHASHSEED=0 .venv/Scripts/python.exe run.py --config C:/Users/benpe/ClashBot/scratchpad/gauntlet/L59/cfg_armG.yaml train-sim-ppo --out data/policy_armG.pt --seed 41 --envs 96 --workers 12 --size 432 --device cuda --search-interval 4 --matches <N>`
  (`--out` so the default checkpoint is not overwritten; `--resume`/`--init` per the lead's choice of
  starting weights). If arm G is meant to be "c2r + geometry", the lead derives the yaml from
  `data/bench/c2r_run.yaml` + the 7-line block instead (s7.2 lists the measured differences).
- Proof the override reaches the workers: `tests/test_geometry_wiring.py::GeometryReachesWorkers` (s9.2).
  On a live launch the same check is `RemotePool.probe()`; the banner alone is not evidence (s7.3).
- NOT started. No commits. `data/` untouched. `src/clashrl/env.py` (live) untouched.

### 9.6 Full suite after the rulings (`suite_after_v2.txt`)
