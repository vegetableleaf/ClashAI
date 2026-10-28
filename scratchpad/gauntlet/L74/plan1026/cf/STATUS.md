# P3-FORK (cf_credit, R_fork) STATUS -- updated 2026-10-28 ~14:30 EDT (re-dispatch, account 2)

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

## Running / done on pod 32657 (logs /workspace/cf3/logs, tree /workspace/cf3/cfh = HEAD pipeline + working-tree cf_credit.py)
- cfpilot2: the L1 pilot, owner return (shaping tower_phat), CLXIII init, 6 updates x 128 matches, critic warm-up all updates,
  n_actors 26, CPUs 0-27, CF_DUMP /workspace/cf3/logs/pilot2.jsonl, memwatch logs/cfpilot2.mem.tsv. Launched/babysat by Codex
  (.foreman/scratch/a2/codex/P3FORK_1.md); results land in plan1026/cf/data/ (pilot2.jsonl, pilot2_report.json, pilot2_tables.md).
- done: cfmem1 (4 actors, 16 matches), cfrepro40 (u0000 only, killed with SIGINT to its PID after update 0), cfmini1 (2 actors,
  new triggers on: tornado_redirect fired and collated, rows +34, slope 1.34/25).

## Commands
- Sync code: `bash plan1026/cf/sync_tree.sh pipeline/cf_credit.py ...` (REF=HEAD for committed versions); tests on the pod:
  `ssh ... 'cd /workspace/cf3 && ./test_pod.sh 0-3 pipeline/tests/test_cf_credit.py -k NewTrigger'` (crforge engine).
- Run (returns at once): `cd /workspace/cf3 && CF_DUMP=logs/X.jsonl TREE=/workspace/cf3/cfh GUARD_GB=100 ./guarded.sh crforge RUN 0-27
  --config scratchpad/gauntlet/L74/plan1026/cf/cf_pilot_clxiii.yaml max_updates=6 critic_warmup_updates=6 n_actors=26 E=32 G=4
  screen_every=1000 proagree_every=1000 learner_device=cuda ability_bc_matches=64 screen_entries=8 "screen_seeds=[0]"
  cf_audit_p=0.2 cf_cap_ticks=40000 "cf_p={...}"` (the cf_p of the pilot is in the Codex ticket).
- Report: `research/ext/Royale/.venv/Scripts/python.exe plan1026/cf/pilot_report.py plan1026/cf/data/pilot2.jsonl --from-update 2`.

## Next
1. pilot2 verdicts per trigger: SNR >= 0.5 (else more K / matched horizon / control variate, never dropped), slope in [0.7, 1.3],
   cost; set P_DEFAULT from the budget model; re-run at the new defaults to confirm <= 1x fork ticks.
2. P6 macro prefixes + Java forks: design notes written (P6_DESIGN.md, JAVA_FORKS.md); not built.
