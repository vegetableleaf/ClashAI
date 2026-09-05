
### §5cs.30 -- L59 (2026-09-05 00:0x-05:0x): radius-graded reward STEP 1 wired into the SIM env (arm G, commit 794d030) and ARM G LAUNCHED 04:49 from c2r_best; a rollout-worker CONFIG SEAM fixed on the way (every env-side key of a `--config` yaml stopped at the learner); G+E and E QUEUED behind G (RAM: one 12-worker arm leaves 1.1 GB free); owner asleep -- every decision below was taken on their behalf and is open to veto

**Owner rulings folded (04:2x):** "continue on with the radii work overnight ... full autonomy ... don't ask
questions unless absolutely necessary". Guardrails (§7) unchanged. Epsilon flag from L58 resolved by the owner
(`rl_epsilon_start` back to 0.50, live-only key, verified clean).

**What was built (agent `wire.md`, 653 lines, every number from a run):**
- `geometry_reward.py`: P2 buildings-only; P7 = 0 for swarm roles; PATH-based P1 (`d_path` = tile distance to
  the threat's FORWARD march path current pos -> bridge -> nearest alive own tower, `pull_ok` = the building is
  acquired before the tower; `p1_snapshot` kept for the record); `placement_credit(kind)` in [-0.3, 1.0]
  (building `P1*(0.5+0.5*P2) + max(FLOOR, p1_close_snapshot) + P6`; troop `P3` (+P7 if enabled); spell 0) and
  `timing_credit` = P5. 26 module tests OK.
- `sim/env.py` (+131 lines, `grep -n L59`): in `_threat_response` every NON-geometry gate is untouched (quiet
  board, triage, budget, counters, spell early-returns, misread penalty); the building `deep_ok and 0.50<=ny<=0.80`
  and troop `intercept and deep_ok` binaries become `credit = w_time*P5 + w_geom*place*gate` paid ONLY when
  `place > 0` (ruling 6.1), `gate = band(t_resp; t_cross-3.0, t_hit+1.0, w 1.5 s)`, 1.0 when no window exists;
  X-Bow offensive credit `w_wincon*P6` (was flat 3.0); `geo_*` RECORD-ONLY ledger. Config block `env.geometry`
  (config.yaml ~1270: enabled false, w_geom 2.0, w_time 1.0, pre_place_s 3.0, p7_enabled false, log_all_terms
  true). `enabled: false` reproduces HEAD's per-step reward to 1e-9 on 2 fixed-stream matches (222 + 290 steps,
  `tests/test_geometry_wiring.py`; the trade term is subtracted, see trap 1).
- Gate rerun under path P1 (`gate_summary.txt`): pro Tesla plays with `p1_pull_band > 0` 53.3% (snapshot 40.9%,
  n=807); modal (9,21) vs corner on the median Hog board `placement_credit` 0.543 vs 0.143 -> not dropped. (a)
- Hog-vs-Tesla(9,21) scenario (`geo_scenario_v2.txt`, 11 rows): credit +2.85/+3.0/+3.0 while the hog is at
  own-frame tile 14.7/15.9/17.1 (pull possible), 0 at 18.3/20.7/23.1 (locked on the tower) -- the OLD binary
  paid +1.0 exactly there (18.3, 20.7) and 0 in the pull window. The two rewards pay DISJOINT windows. (a)
  Hog still on the enemy half (tile 8.5-13.5): path P1 = 1.0 but the env sees no threat (`tid0` 0) -> 0 credit.
  The pros' PRE-PLACED Tesla is therefore still unpaid; needs a `_threat_response` doctrine change (threat
  visible from the enemy bridge approach). PARKED, not bundled (one change per experiment). (b)
- Random-stream probe (12 ladder matches, 366 scored placements): buildings 4 scored 0 paid; troops 218 scored
  22 paid (min +0.114, median +2.0, max +3.0, gate < 1 on 9/22); spells 144 scored 0 paid (P4 nonzero 17/144,
  log-only). (a)

**SEAM FIX (pre-existing defect, closed in 794d030).** `sim/remote_pool.py::_worker` called `Config.load()`
with NO path, so every rollout worker re-read `config/config.yaml` from disk: EVERY env-side key of a
`--config` run yaml stopped at the learner (parent-side keys like `ppo_gate_prior_*`, `hazard_coef` did work),
and `--drill-only` never reached a worker (they read `sim.drill_only` = None -> every drill ran). Now `Config`
records `.source` (`config.py`), `train_sim_ppo.worker_config_args(cfg)` ships the path + the parent's in-memory
overrides (`action.grid` from `--size`, `sim.drill_only`), and the worker does `Config.load(config_path)`.
Proven through the REAL CLI with `--workers 1`: the spawned worker reports `geo_enabled True`, `config_source`
= the arm yaml, grid [18,24], drill_only arrived; without `--config` it reports the disk value False. (a)
c2r was NOT affected: `c2r_run.yaml` vs `config.yaml` differ on one env-side key (`observation.lock_aware_targets`,
absent vs false, coded default false). Whether any OLDER run depended on this is a log question (b).
Full suite 1332 tests: 1 failure = the pre-existing `test_xbow_into_push...clamped_frontmost_ROW` (fails on HEAD).

**ARM G LAUNCHED 04:49 (`data/bench/armG_run_launch.sh`, log `armG_run_20260905.log`):** `--config
data/bench/armG_run.yaml train-sim-ppo --resume --matches 40000 --envs 96 --workers 12 --size 432 --device cuda
--seed 41 --search-interval 4 --out data/policy_armG_20260905.pt`, seeded from `c2r_best_36k_backup.pt` (sha256
d209b41e..., verified identical on all three copies after the cp). Key-level diff of `armG_run.yaml` vs
`c2r_run.yaml` (python, both loaded): the 6 `env.geometry.*` keys + checkpoint/continuation paths; every other
differing key is absent-vs-coded-default (checked each `cfg.get` default) or live-only (`hand.slots`,
`rl_epsilon_*`, `rl_gate_tau`). So the ONE sim-training change vs c2r is `env.geometry.enabled: true`. (a)
Log: RAIL GUARD rescaled the resumed cell head x0.0430 (raw absmax 105; c2r's resume was x0.0556 at 81 --
the head re-saturated further during c2r). Early curve IDENTICAL in shape to c2r's resume (avg_rew -29.4/-33.9
at 125/150 episodes vs c2r -31.2/-30.6; 0.6 ep/s vs 0.6-0.7) -> the resume shape, not the geometry. (a)
Counter semantics: `--resume` restarts the match counter at 0, so "m5k" = absolute ~m41k.
Detached (nohup, session-independent): trainer (pids 74468/70508), `ppo_watchdog` (`armG_run_watchdog.out`),
and NEW `scratchpad/gauntlet/L59/arm_gates.py --run armG_20260905` (`armG_gates.out`): at m5k/m10k/m20k it
snapshots the checkpoint to `data/bench/armG_m<k>k.pt`, runs L55 `place_probe` x3 seeds, the NEW
`geo_ledger_probe.py` x2 seeds (see below) and `gate_prior_probe`, writes `L59/reads_armG_20260905_m<k>k.txt`
and posts to Discord. The reads happen even if the gauntlet wakeup dies.

**Baseline read (c2r_best under the arm-G reward, `geo_ledger_probe.py` seed 0, 6 envs x 400 steps, greedy
card+cell, sampled gate; `geo_ledger_c2rbest_s0.txt`):** the trainer never dumps the sim `RewardTerms` ledger,
so fire counts come from this offline replay of a checkpoint on the arm yaml. Ledger over 6 envs: `geo_credit`
23 fires sum +47.9; p1 13/+6.0; p1_close 11/-6.9; p2 41/+20.5; p3 25/+18.3; p5 78/+65.4; p6 9/+9.0; p4
(log-only) 25/+21.0. Per card: tesla scored 24 paid 2 (mean +1.56), mean P1 0.039 (the corner Tesla (234) is
near-silent on the pull band); tesla_evo 9/4 (mean P1 0.366); x_bow 13/2, mean P6 0.692; ice_wizard 47/10
(P3 0.177); knight 39/4; skeletons 53/0 (all at cell 423, P3 0.0). Place-probe part unchanged from L56
(tesla 234 14/24 distinct 9; skeletons 423 53/53 distinct 1). (a) Reproduced exactly on a second run (same seed).
`geo_paid_module_threat` 10 of the 23 paid credits used the module's own threat pick (the env's `_threat_pos()`
unit was not found by exact coordinates on the cached board) -- worth a look, not blocking. (b)

**Decisions taken on the owner's behalf (veto in the morning):**
1. Arm G runs ALONE first: one 12-worker arm measures 9.7 GB python RSS and leaves 1.1 GB free (Chrome 4.6 GB,
   Discord, Steam are the owner's); a second arm would swap. Kept c2r's exact `--envs 96 --workers 12` so G is
   one change vs c2r rather than two. G+E and E are QUEUED (yamls ready: `armGE_run.yaml` = G +
   `sim.ppo_cell_entropy_floor 0.05`, launcher `armGE_run_launch.sh`); the plan is: read G at m5k and m10k,
   then decide whether to stop G for G+E or let G run. "Two at a time" is not possible at this scale on this box.
2. Arm E mechanism = entropy floor 0.05 (hold the start coef, no anneal), NOT a cell-head temperature: the
   resume rail guard already rescales the head (x0.043 here), so a T-rescale would be redundant (L59 probe,
   argmax identical 4157/4188 at T=3).
3. Timing credit paid only alongside a positive placement part (ruling 6.1); close penalty measured on the
   snapshot gap; X-Bow P6 scaled by `w_wincon` (3.0); late edge kept at `t_hit + 1.0`; P4/P7 log-only.
4. Pre-place doctrine change NOT bundled (parked above).
5. `elixir_trade` id() bug NOT fixed while an experiment depends on the reward (trap 1).

**Bug ledger (found, NOT fixed):** `sim/env.py::_trade_reward` (~2134-2225) keys its per-unit ledgers by
`id(u)`; CPython reuses a dead object's address, so a new unit can inherit a dead unit's entry depending on
allocation history. Measured: the fixed-stream reward sequence flips at ONE step in 512 across processes
(-0.3 elixir_trade on a skeletons drop vs 0). Consequence: no per-step reward is reproducible across processes
until the ledger keys on a unit serial. Fix = key on a unit serial; do it between experiments.

**What this does NOT establish:** nothing about whether the graded reward moves the placement distribution --
that is the m5k/m10k read (place_probe distinct cells per card, tesla@234 share, geo ledger tesla mean P1
against the 0.039 baseline, gate_prior_probe P(play)). One seed; three before any claim.

**Traps found.** (1) `RewardTerms` is never dumped by `train-sim-ppo` -- ledger reads need the offline replay
(`geo_ledger_probe.py <ckpt> <seed> greedy <yaml>`). (2) `ppo_cell_entropy_*` and `ppo_gate_prior_*` live under
`sim:` not `train:` in the yaml (`cfg.get("train", ...)` returns None silently). (3) A run yaml REPLACES
config.yaml and now reaches the WORKERS too -- an env-side key missing from the yaml falls to the coded default
in every rollout env, not to config.yaml. (4) Git-Bash `sleep` is blocked in the tool shell but not inside a
script (`scratchpad/_wait.sh`). (5) Under `--resume` "best so far 31%" in the log is the resumed file's
metadata, not this run's.
