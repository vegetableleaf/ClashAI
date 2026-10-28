# P3-FORK (cf_credit, R_fork) STATUS -- updated 2026-10-28 ~12:10 EDT

## Done (committed)
- pipeline/cf_credit.py rebuilt from wip_cf_credit with REWARD_REVIEW section 4 fixes: K = 2 CRN continuations per
  candidate (continuation 0 = the real RNG states), Q in the trainer's own return (gamma_tick; V_eff = Phi + s v_net,
  Phi = shaping tower_phat computed at the fork stop, or 0), A_i = Q_i - mean_j Q_j for ALL candidates (candidate 0
  replaces the decision row's GAE advantage), per-trigger reliability shrink, `random` coverage trigger
  (policy-sampled alternatives), audit runs to the match end (slope_audit), per-match tick cap. Hooks:
  e1_eval.selfplay_decide + Runner.hook, search_s0.fork_into(fresh), rl_royale collate/cf_append, gae_batch,
  minibatch_loss, ref_terms, actor_base, load_config, config_sha, CF_DUMP env (pilot dump, no cfg key).
- Tests: pipeline/tests/test_cf_credit.py 23/23 locally (RoyaleSim 20261006); on pod 32657 crforge: TestForks +
  OnStates 4/4 (fork determinism, isolation, CRN reseed, audit, baseline = real continuation draw for draw).
- Smokes (pod 32657, cpu learner): cf ABSENT = known shas: fin16 d4ef5467/6cd7292f SMOKE PASS (cfsm_off_rs);
  crforge u0000 e816a6a4 (cfsm2_off_cf) = HEAD tree e816a6a4/f060b678 SMOKE PASS (cfsm_head_cf).
  cf ON: SMOKE PASS on fin16 (cfsm_on_rs) and crforge (cfsm2_on_cf); real-match plays identical with forks on.
- Pre-existing failures (same on a clean HEAD worktree): test_rl_gae TestDefaultIsParent.test_one_update_identical,
  test_search_s0 x3, test_league TestSelfPlayCounters x2.

## Running (pod 32657, logs /workspace/cf3/logs)
- L1 pilot: cfpilot1 (tree /workspace/cf3/cfp, CPUs 0-47, cuda learner), CF_DUMP /workspace/cf3/logs/pilot1.jsonl,
  6 updates x 128 matches, all critic warm-up. Report: `python scratchpad/gauntlet/L74/plan1026/cf/pilot_report.py
  /workspace/cf3/logs/pilot1.jsonl --from-update 3` (PYTHONPATH=/workspace/cf3/cfp).
- trigger_audit2 (24 crforge matches, CPUs 228-235) -> /workspace/cf3/logs/trigger_audit2.json.
- Restart a run: `cd /workspace/cf3 && [CF_DUMP=...] [TREE=...] ./run.sh ENGINE RUN CPUS --config CFG [overrides]`
  (local copy: scratchpad/gauntlet/L74/plan1026/cf/run.sh; crforge = lib_cfclone3 + facade c003fc74 in cf3/build).

## Next
1. Pilot verdicts: per-trigger SNR (target >= 0.5), slope audit in [0.7, 1.3], cost; set P_DEFAULT from the
   measured fire rates so fork ticks <= 1x match ticks.
2. Not done yet (NOT dropped): Rocket + Tornado combo, Tornado redirect, P6 macro prefixes (multi-step
   alternatives); wiring into the fast loop (Java fork + seat-state copy; interface sent to LOOP-INT).
