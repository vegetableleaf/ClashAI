# P3-FORK2 (fresh seat, account 2) -- 2026-10-28 evening: STATUS ADDENDUM (read first; the P3-FORK status below it is the predecessor's)

Labels: (a) measured, (b) plausible / untested, (c) contradicted.

## Landed by P3-FORK2
- 9807c71: P_DEFAULT rocket_tornado 0.055 / tornado_redirect 0.0011 (combo falls back to 0.0 for a config without action_delay_ticks /
  with pipeline_decisions, tap_loss, tap_slow; explicit cf_p > 0 there is refused); cf_adv_scale (training advantage x factor, the critic-slope
  calibration, opt-in, hash-neutral at 1.0, range (0, 2]); cf_diag (P4 audit record: sample ctx, per-fork dg = Phi / critic parts + tower
  snapshot + plays since the root at every stop, candidate meta, match opp). Tests 34/34 local (RoyaleSim) and 31 pass / 3 skip on pod 32657
  (crforge fe364ceb). p4_audit.py (tables), p4_persona.py (persona fork test).
## Running
- cfaud1 on pod 32657 (P4 audit + persona strata), started 20:50 UTC: tree /workspace/cf3/cfh5, CPUs 0-27, 26 actors, 8 updates x 128 matches, cf_diag,
  horizon 900 (+ sweep 150..750), audit_p 0.4. Log /workspace/cf3/logs/cfaud1.log, dump logs/cfaud1.jsonl, mem logs/cfaud1.mem.tsv.
  Restart (only if dead; resumable? NO -- start again with a new run name): see the command in "Commands" below with RUN=cfaud2.
- LESSONS (both cost a restart): CF_DUMP must be an ABSOLUTE path (relative = the run's TREE, which has no logs/); the per-match fork cap
  cf_cap_ticks (default 8000) throttles a high-p audit to ~1 sample/match (cfaud2 u0: 124 samples, ~400 capped, fork 1.64x) -> audit runs set
  cf_cap_ticks=40000. cfaud1 (CRASH: relative CF_DUMP) and cfaud2 (cap) were stopped; cfaud2 u0 kept as data/cfaud2_u0.jsonl (128 matches, tooling test).
- Current run: cfaud3 (same config as cfaud1 + cf_cap_ticks=40000), started 21:03 UTC, dump /workspace/cf3/logs/cfaud3.jsonl.
  Command (from /workspace/cf3, ssh to 32657): `CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib CRFORGE_FACADE_BUILD=/workspace/cf3/build_fe
  CF_DUMP=/workspace/cf3/logs/cfaudN.jsonl TREE=/workspace/cf3/cfh5 GUARD_GB=100 ./guarded.sh crforge cfaudN 0-27 --config
  scratchpad/gauntlet/L74/plan1026/cf/cf_pilot_clxiii.yaml max_updates=8 critic_warmup_updates=8 n_actors=26 E=32 G=4 screen_every=1000 proagree_every=1000
  learner_device=cuda ability_bc_matches=64 screen_entries=8 "screen_seeds=[0]" cf_diag=true "cf_horizon_sweep=[150,300,450,600,750]" cf_horizon_ticks=900
  "cf_horizon_by={wincon: 900, siege: 900}" cf_audit_p=0.4 cf_cap_ticks=40000 "cf_p={rocket: 0.003, rocket_played: 1.0, rocket_tornado: 0.5, tornado_redirect: 0.004,
  wincon: 0.015, siege: 0.1, xbow_after_fail: 0.03, xbow: 0.1, idle_full: 0.0, log_bait: 0.0, random: 0.0}"`
- Collect + tabulate after it ends: Codex ticket .foreman/scratch/a2/codex/P3FORK2_1.md (cfaud1 -> read cfaud3 in the ticket's names), tools p4_audit.py / p4_persona.py.

# P3-FORK (cf_credit, R_fork) STATUS -- updated 2026-10-28 ~16:10 EDT (re-dispatch, account 2): step 1-3 done

Labels: (a) measured, (b) plausible / untested, (c) contradicted.

## Landed
- 1091bd7: cf_credit (K = 2 CRN continuations, Q in the trainer's own return incl. tower_phat Phi, A_i = Q_i - mean_j Q_j on ALL
  candidates, per-trigger reliability shrink, `random` coverage trigger, audit to the match end), hooks in e1_eval / search_s0 /
  rl_royale (absent / null / false = byte-identical, historical config hash).
- 034ea10: opt-in triggers `rocket_tornado` (combo = Rocket at the pull centre + a follow_ups Tornado, vs the best lone blast /
  wait) and `tornado_redirect` (both princesses up; Tornado centre toward our king vs on the unit vs wait), cf_p 0 by default
  (no condition read, no RNG draw, cf-on hash unchanged -- pinned by a test); `cond` / `cond_ticks` in the match record (the
  offline budget model); pilot_report.py with `k_for_snr_0.5`, cost per sample and the budget model (recommended cf_p);
  pod tooling (memwatch.py, guarded.sh, sync_tree.sh, test_pod.sh); P6_DESIGN.md; JAVA_FORKS.md.
- Tests: pipeline/tests/test_cf_credit.py 29/29 locally (RoyaleSim 20261006); crforge on pod 32657: TestForks + OnStates +
  NewTrigger* 10/10 (the new combo fork plays Rocket, then the scripted Tornado 12 ticks later on crforge).
  Pre-existing failures on clean HEAD (not ours): test_rl_gae TestDefaultIsParent.test_one_update_identical, test_search_s0 x3,
  test_league TestSelfPlayCounters x2.

## Why cfpilot1 died (step 1)
- (a) The learner process was killed HARD 10 min 1.5 s after the 40 actors started (actors.pid 15:20:27.9, last log write
  15:30:29.5; run dir still holds pid.json + actors.pid, which rl_royale's `finally` unlinks => no exception, no `[rl] CRASH`
  line, no Traceback, no hs_err => SIGKILL / SIGTERM / SIGHUP, not a JVM or Python crash). It died before the first `u0000`
  line (the pilot was in warm start / init screen).
- (a) The SAME configuration re-run alone (cfrepro40: 40 actors, cuda learner, cf on, CF_DUMP) is healthy: init + warm start
  (186 s) + the 702-match init screen (338 s) + update 0 with forks (128 matches, 552 s) with no death; footprint 41 GB at actor
  spawn, 56 GB after 9 min, 64 GB peak cgroup (40 actors x 1.2-2.0 GB RSS, learner 3.4 GB, JVM heap per actor only ~0.2 GB,
  CRFORGE_XMX 4g is not the driver), cgroup memory.events oom / oom_kill unchanged (12 / 5) across all my runs.
- (b) Most probable cause: the cgroup (125 GB, SHARED with every job on the pod) hit its limit while 3-4 other jobs ran
  (smokes in cb / cbhead / cfp, trigger_audit2, pytest: log mtimes up to 15:46) and the kernel OOM-killed the biggest process,
  which is the learner (3.4 GB vs <= 2 GB per actor); memory.events oom_kill = 5 is cumulative over the pod's life and cannot
  date it. (c) NOT a deterministic bug of the config, and NOT the 600 s actor-ready wait (pid.json was written at 15:20:45).
- Fix in place (b): (1) n_actors sized to the budget: 26 actors = ~42 GB (the pilot below), never 40 on a shared cgroup;
  (2) guarded.sh runs memwatch.py on the run's process tree: it SIGKILLs only that run's own PIDs if the cgroup passes
  GUARD_GB (100), so a runaway kills the run, not a neighbour or the learner at random, and writes the trace
  logs/RUN.mem.tsv; (3) launch with setsid/nohup + `< /dev/null` (an ssh session end must not signal the run).
- Orphans: a killed learner leaves its 40 actors alive until their current job ends (they check parent.is_alive() only when
  idle, every 30 s) -- kill them by the PIDs in <run_dir>/actors.pid (done for cfrepro40).

## Results (details + tables: PILOT_RESULTS.md; data/ is gitignored, kept on the laptop and pod 32657 /workspace/cf3/logs)
- pilot2 (cfpilot2, lib_cfclone3, Codex-run): 6 x 128 matches, all triggers incl. the two new ones, K 2 / 600 ticks. SNR >= 0.5 for 9 of 11 triggers; idle_full and
  random 0.0. Slope levels 0.79, differences 0.717 +- 0.072 (in band, lower edge). Fork cost 5.87x.
- pilot3 (cfpilot3, fe364ceb): noise study (horizon sweep + K 4): horizon 300 with K 2 gives SNR >= 0.77 for the five weak triggers at half the cost.
- pilot4 (cfpilot4, fe364ceb, DEFAULTS): fork cost 0.71x match ticks (target <= 1x), SNR >= 0.5 on all 11 (small n), slope levels 0.80; the per-update slope on
  differences is too noisy at 1x sample counts (n 69, SE 0.53): gate it pooled over >= 8 updates or with cf_audit_p 0.3.
- Defaults now in cf_credit: P_DEFAULT (1.0x model), HORIZON_DEFAULT {idle_full, log_bait, wincon, siege, random: 300}; rocket_tornado / tornado_redirect stay opt-in
  (measured p 0.055 / 0.0011 for 1x). New opt-in knobs: cf_k_by, cf_horizon_by, cf_horizon_sweep (diagnostic).
- Cause of cfpilot1's death: see above (b, OOM-kill of the learner on the shared cgroup most probable; not reproduced in isolation; guard + 26 actors in place).

## Engine
- Lead 10-28: crforge clashbot-main fe364ceb is the lib for NEW runs. pilot2 ran on lib_cfclone3 (finished on it); pilot3 / pilot4 ran on
  CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib + facade rebuilt to /workspace/cf3/build_fe (javac against that lib; same CfCore.java c003fc74), tables 16.402.22.
  run.sh takes CRFORGE_LIB / CRFORGE_FACADE_BUILD / CRFORGE_TABLES overrides. Do not compare pilot2 against pilot3 / 4 numbers as a paired A/B (different lib).

## Pod 32657 now: nothing of mine is running (cfpilot2/3/4 finished; trees cfh, cfh2, cfh3, cfh4 = hard-link copies, cfh4 = the committed cf_credit 65e80370276f343c).

## Commands
- Sync code: `TREE_NAME=cfh4 bash plan1026/cf/sync_tree.sh pipeline/cf_credit.py ...` (REF=HEAD for committed versions; never into a tree a run is using);
  tests on the pod (crforge): `ssh ... 'cd /workspace/cf3 && TREE_NAME=cfh4 ./test_pod.sh 0-3 pipeline/tests/test_cf_credit.py -k NewTrigger'`.
- Run (returns at once; GUARD_GB is a CGROUP-wide limit, so a neighbour's memory counts): `cd /workspace/cf3 && CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib
  CRFORGE_FACADE_BUILD=/workspace/cf3/build_fe CF_DUMP=logs/X.jsonl TREE=/workspace/cf3/cfh4 GUARD_GB=100 ./guarded.sh crforge RUN 0-27 --config
  scratchpad/gauntlet/L74/plan1026/cf/cf_pilot_clxiii.yaml max_updates=4 critic_warmup_updates=4 n_actors=26 E=32 G=4 screen_every=1000 proagree_every=1000
  learner_device=cuda ability_bc_matches=64 screen_entries=8 "screen_seeds=[0]" [cf_horizon_sweep=[150,300,450]] ["cf_p={...}"]`.
- Traps: `pgrep -f "rl_royale --run X"` matches the ssh shell that contains it (use `^/workspace/venvf16/bin/python -u -m pipeline.rl_royale --run X`); the first
  update line appears after ~7-12 min.
- Report: `research/ext/Royale/.venv/Scripts/python.exe plan1026/cf/pilot_report.py plan1026/cf/data/X.jsonl --from-update 1 [--cost-scale t=f] [--weights t=w]`.

## Codex dispatches
- P3FORK_1 (.foreman/scratch/a2/codex/P3FORK_1.md, medium): launched + babysat cfpilot2 (~75 min), collected, ran pilot_report, wrote pilot2_tables.md. Outcome DONE; its
  numbers re-checked against my own run of pilot_report (matches 512, samples 2,907 identical).

## Next
1. Lead / owner: enable rocket_tornado / tornado_redirect in a production cf_p (p 0.055 / 0.0011 = 1x share) and decide cf_w (signal share ~0.1-0.2% at cf_w 1) and
   whether to calibrate the advantage by the within-sample slope (~0.72).
2. P6 prefix executor + Java forks: designs in P6_DESIGN.md / JAVA_FORKS.md; not built.
3. Pilots with the pillar-2 human-like opponents once rollouts use them (forks use the match's own opponent).
