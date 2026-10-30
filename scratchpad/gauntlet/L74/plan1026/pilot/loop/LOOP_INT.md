# LOOP-INT: the fast crforge training loop (integrator)

Labels: (a) measured, (b) untested, (c) contradicted.

## STATUS (keep current; 2026-10-28 ~18:30 EDT, re-dispatch on account 2)
- FASTLOOP-FIX (10-30, account 3; restart point = this bullet): the fast loop on
  origin/main is exact again and plays the live CLXIII partner incl. its rocket_tornado follow-ups.
  (a) ROOT CAUSE of MEMFULL-LOOP's `AssertionError: (16, 15)`: neither the follow_ups guard (it RAISES, never skips -- (c)
  for that hypothesis) nor the MEM-FULL change: a thread race in the FAST-LIVEOPP wiring. CfCtx.build's -2 compares the
  SHARED Names.missing size before / after its unit pass, so another CfTrain pool thread's obs miss fails an innocent
  'live' row -> CfTrain.ctxRow threw -> the match counted as crashed -> P.run `skipped` (fast 15, prod 16). Evidence: the
  same msg + origin/main code reran 16 / 16 at --matches 8 --threads 2 (no skip: timing), and at --matches 16 --threads 8
  (fast only) gave 15 + 1 skipped, first_crash `java.lang.IllegalStateException: CfCtx.build -2: a body without a Names
  entry after the obs` (33903 /workspace/mfl/out/race_a.log). Fix (CfTrain.ctxRow): rebuild while -2 is not this row's
  own miss (TrainMatch.missed; -2 returns before any Seat / output write); same settings after: 16 / 16 identical,
  0 skipped (racefix_a.json).
  (a) keys-absent identity, origin/main code, a NON-live B0 msg (33308 lint_m1 u0000, B0 vs B0 memory both seats, run
  under 33903's runtime stamp: compare --runtime-here): 16 / 16 identical, tables 16 / 16, MEM rows 5,257 / 5,257, lp max
  3.1e-6 (abs_m1_main.json). After the follow-up port (same msg): 16 / 16, 5,257 / 5,257 (fu_m1.json).
  (a) follow-ups PORTED (CfTrain setFollowUps / followStart / followCheck / landQ / verdict = SelfPlaySide's event-driven
  _follow_start / _follow_check / _follow_resolved; producer._follow_ups; the guard is gone). Live compare (CLXIII live
  partner, the corrected msg of cmp_live2_u5_48 + 96 more jobs of the same u0005 source, CPU): 144 / 144 matches identical
  (48 / 48 on the PLATEAU msg), 0 skipped, 6 follow-up plans (3 fired, 2 cancelled, 1 open at match end), memory tables
  144 / 144, ability results 144 / 144, lp max 2.9e-6 (bar 1e-5; TF32 off as before). Planted rule test: CfTrain.verdict ==
  follow_up_verdict on 800 cases, all 8 branches (test_follow_verdict.py).
  (a) MEM-FULL keys ON (memory_e_max 256 + board snap, mfl.yaml, a real keys-on msg dumped by smoke_mfl.sh): 8 / 8
  identical (the smoke's msg has 8 jobs), memory tables 8 / 8, MEM rows (mem_h vs the learner rebuild) 2,737 / 2,737,
  ability 8 / 8 (296 labels) (mflon_cmp.json).
  (a) smokes: (1) keys ON fast loop (smoke_mfl.sh RUN=mflon_smoke2, mfl.yaml: B0 + memory_e_max 256 + board snap, CPU
  serve eager + CPU learner, critic_warmup_updates=1 because tower_phat refuses 0): SMOKE PASS, u0001 = a real PPO policy
  step through the widened encoder (KL g/c/x .0091/.0015/.0023, 20 steps), resume check all True incl. ability head /
  opt; the u0001 msg compare: 8 / 8, tables 8 / 8, MEM rows 2,768 / 2,768, ability 8 / 8 (1,095 head decisions, 17
  presses) -> keys-on total 16 / 16 matches, 5,505 / 5,505 MEM rows. (2) opp_learner_calib_live.yaml on the fast loop
  (smoke_live.sh RUN=fixlive_smoke1, the arm's recipe: ftR init, beta .003, lr 3e-5, th_anchor 10; 1 x 16 CPU): SMOKE
  PASS, league line `frozen 0.12/8` / `frozen 0.00/8` = the frozen CLXIII partner, resume check all True, freeze_heads ok.
  (a) speed, the live config, u0000 (64 matches, the same jobs both runs, 33903 under its full cgroup quota):
  2 producers x 32 matches x 3 Java threads on 10 CPUs: CPU forwards 1,686 s = 137 matches/h (forward 1,587 of 1,629 s
  per producer: the in-process CPU forward IS the cost; decide_py 30 s, java 8 s); cuda:0 forwards (as launch_arm.sh)
  80.9 s = 2,849 matches/h, 605 rows/s (per producer forward 44 s, decide_py 17 s, java 6-8 s of ~70 s), 0 skipped.
  Production arm: 256 matches / update in roll 739-822 s + upd 24-30 s (u0011-u0013) = ~1,180 matches/h on 22 CPUs.
  (b, projection, untested at that size): 256 matches / update at 2,849/h = ~325 s roll + ~28 s cuda learner = ~350
  s / update (~2.3x faster than production's ~800 s) on 10 CPUs; more producers on the arm's 22 CPUs should scale until
  the shared GPU forward / Python decide binds. The earlier "~6.5x" stays (b).
  NOT done / open: the arm itself was NOT moved (lead's call; it runs production rl_royale on cb2's pipeline, and the
  verified fast-loop code is origin/main's loop on origin/main's pipeline -- origin/main's producer needs
  match_memory.opts, which cb2's pipeline may lack: (b) untested); follow-up coverage = 6 plans / 3 fired in 144 live
  jobs (only rocket_tornado emits follow_ups; no `afford_ticks` / `require_first False` case occurs in production).
  Restart (33903; trees /workspace/mfl/cbg = origin/main + this work, cb = origin/main + compare.py only):
  laptop `bash scratchpad/gauntlet/L74/plan1026/pilot/loop/mfl/ship_mfl.sh /workspace/mfl/X.tar /workspace/mfl/cbX` builds a
  tree; compare `CB=TREE CPUS=.. bash TREE/scratchpad/gauntlet/L74/plan1026/pilot/loop/mfl/cmp_mfl.sh MSG OUT [--skip-jobs K
  --max-jobs N --runtime-here --fast-only]`; msgs /workspace/mfl/in/ (live144.msg.pkl, lint_m1_u0000.pkl, mflon_u000{0,1}.pkl),
  /workspace/fliv/out/cmp_live{_b8,2_u5_48}.json.msg.pkl; smokes `CB=TREE bash .../mfl/smoke_live.sh RUN CPUS` (FL / RL / GPU / LD
  env) and `CB=TREE bash .../mfl/smoke_mfl.sh RUN`; results /workspace/mfl/out/. Nothing of mine left running.
- LOOP-INT2 (fresh seat, 10-28 ~20:00 EDT): step (a) hero abilities WIRED (CfTrain stage 7 = CfAbil commands / options;
  the pending queue + one-at-a-time recheck + CfCore.ability press inside advanceTo (production's _advance_to stops on
  every pending press); accepted presses -> CfAbil.pressed, CfPubObj.press, CfMem.Log.press; plays -> CfAbil.played +
  ability_deployments; seat modes RULE (opponents) / LABEL (B6 warm start: no head in the message) / HEAD (learner,
  production's e1_eval.ability_decide called from the fast decide; server mode: policy_server's ability call); result
  ability_presses / deployments / fallback / ability_head; server weight version = 2 u + (1 with the head), traj wver =
  version // 2). pilot.yaml now runs on the fast loop (lint_pa1, 33308: warm start 128 rule rollouts through FastPool
  = 14,251 IW labels, BCE 0.0771 -> 0.0393).
  - compare (a) LABEL msg (warm start, 16 of 128 jobs, in-process cuda, 8 in flight; 33308 cmp_pa_label_b8.json):
    16/16 matches identical (every traj key incl. ab_cand / ab_feat / ab_q: 1,827 labels), ability result fields 16/16,
    presses 22 / 17 per side both paths; lp max 1.9e-6. Memory: first run tables 13/16 (out_value_10 / vpe of 3 early
    plays, fast > prod), MEM rows 4,418 / 5,201; a rerun of the same msg 16/16 tables, 5,201 / 5,201 rows
    (cmp_pa_label_b8d.json) = run-to-run variation. Cause (b, consistent with both runs): producer._mem_bodies took the
    FIRST stopped match holding a missing body's entity id, and entity ids restart in every battle; which matches stop
    together depends on thread timing. Fixed (cc3473d): CfTrain.memBodyKey -- only a match whose entity gives the same
    CfMem key is a candidate, all candidates must resolve to one unit, else RuntimeError.
  - compare (a) HEAD msg, SERVER mode (lint_pa3 u0001 = the pilot with the warm-started head, barrel_decoy_sim on, 16 of
    32 jobs, 8 in flight; 33308 cmp_pa_head_srv.json): 16/16 identical, ability results 16/16 (1,850 head decisions, 24
    presses; engine presses 23 / 26 per side both paths), memory tables 16/16, MEM rows 5,245 / 5,245, v_old max 8.1e-7,
    wver 0 mismatches; lp max gate 1.06e-5, card 3.0e-6, cell 9.6e-6, ab_lp 2.3e-6 (server bar 5e-5). The fix fired:
    mem_eid_in_other_matches 1 (an id held by another match with another key), mem_eid_shared 5.
  - dev run (a) lint_pa3 = pilot.yaml on the fast loop + E=8 max_updates=3 n_actors=8 screen_entries=8 (2 producers x 16,
    server eager, 33308): warm start 128 matches / 14,398 labels, init screen 24 matches 59 s, u0000-u0002 (critic
    warm-up) rollout 72-96 s for 32 matches, ability dec 3,057-4,072 per update. Records for LOOP-LRN / LEARNER-SCALE:
    33308:/workspace/loop/records/lint_pa3/records_u000{0,1,2}.pkl. compare.py --init (server mode: the learner's
    architecture; was opps[0], which hung the head compare on a strict state-dict mismatch).
  - 33308 container restart ~16:53 EDT (all processes, incl. ENG-SME's gap.py, died; reported to the lead). Lead budget:
    LOOP-INT2 <= 40 GB on 33308, one job at a time, memory.usage_in_bytes checked before each launch.
  - Codex LOOP-INT_3 (medium, .foreman/scratch/a2/codex/LOOP-INT_3.md): DONE (its BLOCKED = one K2 GPU metric only).
    33553, ref_bench (B0 + memory, no abilities, T_gate 0.3), K 3 x M 256 = 768 matches / update, 2 actors, learner
    alongside, means of u0001-u0002 (.foreman/scratch/a2/int/bench_grid3.md / .json):
    | | eager | graphs |
    |---|---|---|
    | rollout wall s / matches per h | 130 / 21.2k | 91 / 30.5k |
    | learner s | 110 | 117 |
    | update period s / updates per h | 384 / 10.5 | 330 / 12.7 |
    | overall matches per h | 8.1k | 9.7k |
    | peak container GB / max producer RSS GB / GPU MiB | 44.2 / 9.6 / 17,955 | 44.5 / 9.7 / 18,137 |
    | kl_stop step / rows-used fraction | e0 mb138-195 / 0.17 | e0 mb138-238 / 0.19 |
    Busy CPU 4-5 cores: the rollout is round-latency bound, not core bound.
- DONE, correctness (a): compare.py (production actor_main vs producer, same process, cuda, TF32 off) 16/16 matches
  identical at batch 1 and at 8 in flight, with the fast decide too (`33308:/workspace/loop/cmp_*.json`), lp max 2.3e-6.
  rl_royale-vs-fastloop through the learner, 3 updates with PPO policy updates (`lint_c3_rl` / `lint_c3_fast`, 33308):
  every batch key identical except lp_* bits, outcomes 16/16, all train-log monitors identical; weights bits differ only
  via the lp float noise. With critic warm-up (`lint_c2_*`): weights_sha identical at u0000-u0002.
- DONE, crash recovery (a): FastPool restarts a dead producer and replays its share; `lint_crash` (FASTLOOP_CRASH_TEST=0.5,
  33308): 1 producer restart (exit -6), run completed, weights_sha 3e07cff4 / 0a5fa812 / 72a69c3f = the crash-free run's.
  Crash rate per producer-hour on 33553 benches: 0 seen in ~1.5 producer-h (b: small sample; not counted systematically yet).
- DONE, throughput (a, 33553 = clean 1x 4090, 54 vCPU; `33553:/workspace/loop/b/*.json`):
  | config | matches/h | core-s/match (producers) | all-in incl. server |
  |---|---|---|---|
  | 1 prod x 512 x 8 thr, in-process fwd, production decide | 12.5k | 1.57 | - |
  | 1 prod x 512 x 8 thr, in-process fwd, fast decide | 18.8k | 0.82 | - |
  | 4 prod x 256 x 4 thr, LOOP-SRV server (eager, fp32), fast decide | **48.9k** | **0.63** | **0.70** (server 0.88 cores) |
  Split per match (last row): Java engine 0.25 + obs 0.04 core-s; Python decide 0.055 s, gather 0.009, job start 0.026,
  forward wait 0.088 s; GPU util 57%; 680 rows/match (incl. in-progress rows). NOT yet: learner running alongside, more
  producers (GPU not saturated), graphs mode, the 8x PRO 6000 projection write-up (inputs: SPEED.md k: PRO 6000 fp32
  41.1k vs 4090 21.0k rows/s bare; LOOP-SRV mix 16.1k rows/s per 4090 -> ~31k per PRO 6000 (b) -> ~160k matches/h per
  inference GPU at ~700 rows/match; CPU at 0.70 core-s/match: 300k/h needs ~58 cores).
- RE-DISPATCH (account 2, 10-28 ~17:30 EDT) progress, in the ticket's order:
  1. DONE (a) compare.py SERVER mode (`--server eager`: producer forwards on serve.py, same cuda device; then every
     learner row's v_old vs production's critic on the same rows and wver == update): ref_v0 msg (lint_d1 u0000, 16
     matches, 8 in flight): 16/16 identical, lp max gate 4.5e-6 / card 5.2e-6 / cell 6.6e-6, v_old max 7.1e-7 on 5,125
     rows, 0 wver mismatches (`33308:/workspace/loop/cmp_srv_b8.json`).
  2a. DONE (a) CfMem wired (CfTrain stage 6 = CfMem observe + features after pub.build; CfMem.Log per core fed every
     accepted play at its act tick with playForm read before the play and the pool-unit point (ACT now 7 ints);
     MEM_KEYS rows per seat in memB; table misses filled by producer._mem_bodies from production's raw() of the stopped
     battle; learner traj gets mem_t, result["memory"] = CfMem.table via obs_id.JavaMem.java_table; memory opponents
     allowed when their memory is v2 with the learner's gid). Check config `ref_mem.yaml` (ref_v0 + init B0 + the pilot
     memory keys), msg lint_m1 u0000 (16 matches, opponents latest / init = B0, memory both seats). compare.py now also
     checks (FASTLOOP_MEMHASH=1) every learner event table byte-identical AND every learner row's rollout MEM_KEYS ==
     match_memory.rows_features of PRODUCTION's table (the learner's rebuild; needed because B0's mem.out is exactly 0, so
     at u0 a wrong memory row would not move a single log-prob):
     - in-process (cuda, 8 in flight): 16/16 identical, tables 16/16, MEM rows 5,257/5,257, lp max 2.1e-6
       (`cmp_mem_b8.json`).
     - server mode: 16/16 identical, tables 16/16, MEM rows 5,257/5,257, v_old max 7.6e-7, wver 0; lp max gate 4.1e-6,
       card 4.6e-6, **cell 1.14e-5 = ABOVE the spec's 1e-5** (`cmp_mem_srv.json`). Cause (b, plausible): B0's
       cell_refine convs on a different GPU batch (server batch vs production's 8-in-flight batch; LOOP-LRN saw the same
       batch-size-dependent conv kernels, 6.4e-6 in weights). Bar NOT loosened: the lead decides; measurement owed =
       production vs production at in_flight 1 vs 8 on the same device (its own noise floor).
  3. FOUND (a) GB-DECOY in the PRODUCTION SIM: `decoy_probe.py` (RoyaleSelfPlayEnv on crforge, the e1_eval / rl_royale
     env; tables 16.402.22, lib_cfclone; `33308:/workspace/loop/decoy_probe.out`): the plain barrel is one 'goblin-barrel'
     projectile object; the EVOLVED cast (evo row [112, 2, 1, 2] = next play evolved) makes NO spell entry: the real
     barrel (aim 62982, 477000) and the decoy (aim 261018 = 324000 - 62982, the mirror) are both unit shots with firer -1,
     and production's projectile objects (projectile_observation.objects source 'sim') are EMPTY for the whole flight.
     Why (a, tables): spells_other GoblinBarrel names Projectile 'GoblinBarrelSpell'; the evo rows
     GoblinBarrelSpell_EV1 / _EV1_Decoy are not reached by crforge_core.spell_objects, so the facade's spellObj lacks
     them. So: production SIM shows no barrel during an evo flight; live with --barrel-decoy on shows the real one (and
     decide rules log_barrel / barrel_lane see it). The fast loop matches production exactly (same CfPubObj, byte-
     identical obs), so it has the same gap. NOT changed (it changes production SIM obs; lead / owner call). Proposal:
     crforge_core.spell_objects + CfCore map GoblinBarrelSpell_EV1 -> the Goblin Barrel card and
     GoblinBarrelSpell_EV1_Decoy -> barrel_decoy.DECOY_KEY (dropped by B0's / CLXIII's vocab = live's flag-on view),
     behind an opt-in key (absent = today's bytes), then the obs identity harness + smokes re-run.
  2b. DONE (a) record_phi tower_phat (CfTrain.towerRow: state()'s alive crown towers per row -> production's
     reward_shaping.state_record on a state holding exactly what tower_phat reads) and 2c. opp_style (styled opponents
     through pipeline.loop_opp.decide = production's styled_decisions on stand-in sides; style spell delay = ACT int 7;
     run_selfplay_batch's group key; result["opp_style"]). Check config `ref_pilot_noiw.yaml` = pilot.yaml minus the
     hero-ability keys; msg lint_pn2 u0000 (32 matches: opponents 4 externals + B0; the w14opp_I exploiter and E4 were
     NOT drawn in this sample), ON THE PILOT LIB (fe364ceb + 16.635.3, lead 10-28):
     - server mode: 32/32 identical (every non-lp traj key incl. phi_state, mem_t; opponent plays 32/32 equal, 1,376),
       tables 32/32, MEM rows 10,209/10,209, v_old max 7.9e-7, wver 0; lp max gate **1.33e-5**, card 5.7e-6, cell
       **1.48e-5** (`cmp_pn_srv.json`). lp_gate is the gate logit's fp32 noise x 1/T_gate (T_gate 0.1 = x10).
     - in-process (cuda, 8 in flight; styled heads moved to CPU for loop_opp): 32/32 identical, tables 32/32, MEM rows
       10,209/10,209, lp max gate 4.8e-7 / card 1.4e-6 / cell 4.4e-6 (33308 cmp_pn_b8.json) -> the server-mode lp excess is
       the server's batch composition (fp32), not the wiring. Msg: /workspace/loop/cb/scratchpad/gauntlet/L68/rl/lint_pn2/fast_msg_u0000.pkl.
  2d. NOT DONE: CfAbil / hero presses / the B6 ability head (pilot.yaml: hero_abilities, ability_head, heroiw_press,
     ability_features) -> NotImplementedError. Also needed then: rl_royale's 128-match rule warm start goes through
     ActorPool.run('selfplay') = FastPool (route it to production actors or support label mode).
     CfCtx: NOT needed for production exactness: rl_royale's sampled decode has no decide rules at the pilot cfg (fast_ok
     holds; sample_rules == DecisionOptions()). pilot.yaml's `fastloop.decode: live` has no rl_royale counterpart; the
     fast loop does not implement it (lead decision if wanted: add it to rl_royale first, opt-in).
  4. fastloop --server (serve.py per device, weights pushed per update, producers on CPU) + the pilot.yaml `fastloop:`
     block stripped: lint_ms1 (ref_mem + stored_values + kl_stop_prev 0.02, beta 0; 33308): 3 updates, u0001 kl_stop at
     e1 mb24 (KL 0.0289), learner 13-23 s / update (32 matches). pilot.yaml itself: blocked by 2d.
  5. Bench with the learner (33553, Codex): LOOP-INT_1 (K 6 x M 256, 24 actors) and LOOP-INT_2 (K 4 x M 256, 8
     actors, XMX 5g) both hit 33553's 62 GB CONTAINER cap (memory.limit_in_bytes; free -g shows the host). Measured on
     LOOP-INT_2's u0000 rollout (B0 + memory both seats, fe364ceb): 1,024 matches in 169.8 s = 21.7k/h, 686 rows/match,
     9.6 cores busy = 1.59 core-s/match all-in, GPU 33%, producers 7-9.8 GB RSS, container peak 61.98 GB before the
     learner finished u0000. Report: .foreman/scratch/a2/int/bench_grid2.md. updates/h NOT measured.
  6. PROJECTION.md (draft, (b) overall numbers): synchronous loop ~130-200k matches/h at N 4,096-8,192 on the box;
     300k/h needs overlap or a multi-GPU learner; RAM >= 400 GB; AVX512 boot-gate env proposal.
  LIB SWITCH (lead 10-28): run.sh / bench.sh / 33308 cmp.sh default to /workspace/crforge_main/fe364ceb/plain/lib
  (core 3440d441664b7caa) + tables 16.635.3, facade build loop/jbuild_fe364ceb. Results before it (1, 2a, lint_ms1)
  are on lib_cfclone + 16.402.22; 2b/2c and the 33553 numbers are on fe364ceb.
  RUNNING at the hand-off (10-28 ~20:15 EDT): Codex LOOP-INT_3 (medium; .foreman/scratch/a2/codex/LOOP-INT_3.md) on 33553:
  ref_bench K 3 x M 256 (768 matches / update), 2 actors, XMX 4g, eager then graphs, learner alongside, with the
  rows-used fraction per update; laptop process sh.exe PIDs 57644 / 5112 (detached: no notification), output
  .foreman/scratch/a2/int/bench_grid3.md / .json, events codex_LOOP-INT_3.jsonl; pod runs bench3_k3_m256_{eager,graphs}.
  Codex dispatches: LOOP-INT_1 (medium): stopped by me (OOM design error, my ticket; its Codex process tree killed by PID
  incl. a Codex-spawned StudioMCP child); LOOP-INT_2 (medium): BLOCKED on the 62 GB cap (correct per its decision tree).
- Restart: (all 33308 unless noted) compare: `[FASTLOOP_MEMHASH=1] CPUS=140-151 [GPU=1] bash /workspace/loop/cmp.sh MSG.pkl
  OUT.json [--server eager] --in-flight 8 --matches 8 --threads 4`; msgs: ref_v0 =
  /workspace/loop/cb/scratchpad/gauntlet/L68/rl/lint_d1/fast_msg_u0000.pkl, ref_mem = .../lint_m1/fast_msg_u0000.pkl
  (dumped by `CFG=.../ref_mem.yaml FASTLOOP_DUMP=1 FAST_ARGS="--producers 1 --matches 16 --threads 4 --devices cuda:0"
  run.sh fast RUN 140-151 E=4 max_updates=1`). Sync laptop -> pod: `.foreman/scratch/a2/int/sync.sh PORT paths...`
  (strips CR). Decoy probe: run.sh's env + CRFORGE_FACADE_BUILD=.../loop/jbuild, `python decoy_probe.py --casts 3`.
- Restart: bench `ssh -p 33553 ...; cd /workspace/loop && bash cb/scratchpad/gauntlet/L74/plan1026/pilot/loop/bench.sh
  OUT.json 0-31 --producers 4 --matches 256 --threads 4 --server eager --warm 150 --seconds 120` (33553 tree:
  /workspace/loop/cb = pod copy + these files; venv /workspace/venv; ship pipeline/policy_server.py from origin/main).
  A/B arms: `33308: cd /workspace/loop/cb && scratchpad/gauntlet/L74/plan1026/pilot/loop/run.sh rl|fast RUN CPUS k=v`.
  compare: `bash /workspace/loop/cmp.sh MSG.pkl OUT.json [--in-flight 8 --matches 8 --threads 4]` (33308).
- Nothing left running by me (33308 lint_* runs DONE; 33553 bench exited). 33553 is KEEP (clean throughput pod).

## Pilot on 33308: two arms (lead 10-28 evening; LOOP-INT2)
- Tree: 33308:/workspace/loop/cb = origin/main pipeline/ (incl. 2072dc7 barrel_decoy_sim, 3866761 micro_batch) + pilot.yaml
  (barrel_decoy_sim true) + loop/ files (synced by .foreman/scratch/a2/int/sync.sh). Engine fe364ceb plain lib + tables
  16.635.3 (run.sh defaults); JDK 17; CfAbil.EXACT checked by the producer at start (RuntimeError if false).
- One arm = `loop/pilot_arm.sh ARM GPU CPUS k=v...`: learner + serve.py (eager) on that GPU, 3 producers x 256 matches x 4
  threads + ActorPool actors on CPUS, out dir /workspace/loop/pilot/pilot_ARM (throughput.jsonl, STOP, FINAL), log
  /workspace/loop/logs/pilot_ARM.log, checkpoints /workspace/loop/cb/icebow/data/bench/rl_royale/pilot_ARM/. STOP_AT=epoch
  writes STOP then (rl_royale finishes the update, saves _latest, fastloop writes FINAL = the last numbered checkpoint).
- Laptop mirror: `bash scratchpad/gauntlet/L74/plan1026/pilot/loop/pull_ckpt.sh pilot_S` (and pilot_L), in the background:
  every 300 s each new numbered checkpoint -> C:/Users/benpe/pod_backup_weekend/loop/pilot_ARM/ sha256-verified; at FINAL
  also _latest.pt. LOOP-OPS' launcher NOT used: it builds a fresh tree + venv + 84 artifacts per W and 33308 has 9.3 GB free.
- READY_TO_TRAIN_ON_33308 (POSTPONED by the owner 10-28 ~19:30 until opponent v1; do not start). Before the start:
  re-sync origin/main pipeline/ + loop/ into /workspace/loop/cb (LOOP-ASYNC is editing fastloop.py / the producer protocol
  in the shared tree: take only committed code), the lead clears the pod, then (STOP_AT = the lead's auto-stop epoch):
  `cd /workspace/loop/cb && STOP_AT=T bash scratchpad/gauntlet/L74/plan1026/pilot/loop/pilot_arm.sh S 0 0-119 E=192 n_actors=16 save_every=5`
  `cd /workspace/loop/cb && STOP_AT=T bash scratchpad/gauntlet/L74/plan1026/pilot/loop/pilot_arm.sh L 1 128-247 E=192 n_actors=16 save_every=3 minibatch=65536 micro_batch=1024 lr=1.6e-4`
  (start L ~60 s after S: both compile the same facade build dir), then on the laptop `pull_ckpt.sh pilot_S` /
  `pull_ckpt.sh pilot_L` in the background. Expected (b, from LOOP-INT_3's measured 768-match point without abilities):
  arm S ~384 s / update = ~10 updates/h, ~8k matches/h, save_every 5 = ~30 min; arm L ~130 s rollout + LEARNER-SCALE's
  4-5 min learner + ~140 s overhead = ~6-7 updates/h, ~5k matches/h, save_every 3 = ~30 min. Start-up ~20 min (proagree,
  128-match B6 warm start, 702-match init screen on 16 actors), then 5 critic warm-up updates (no policy steps).
  Memory (b): ~44.5 GB measured per arm at 768 matches + 14 more idle actors x ~0.6 GB = ~53 GB per arm, ~106 GB both,
  inside the 125 GB cap only with the pod cleared; fallback MATCHES=192 E=144 (576 matches) per arm. GPU ~18 GB per arm.
- Any process outside rl_royale that plays the pilot's conditions (compare.py, e1_eval gate scripts, remote actors) must
  export CRFORGE_BARREL_DECOY_SIM=1 and ROYALE_HEROIW_PRESS=live (rl_royale sets both for its own children).

## Opponent as the learner (v1 strength calibration, REPORT_opponents 3 step 4.3; lead 10-28 ~19:30) -- gap analysis
What exists (a, read 10-28): e1_eval timing-head decode (is_timing, timing_cfg, timing_decide_batch, th_ability, th_costs,
th_decided; P2-OPP 6b13c25) for a FROZEN opponent seat; rl_royale's KL to the frozen init with beta in [beta_min, beta_max]
(beta0 = beta_min = beta_max = lambda already gives a FIXED pull to the init); shaping none + advantage gae = win-only;
league_external / league_opp_live (bot pool on our decks), league_learner_icebow_share (learner decks from the census).
What is missing (each opt-in, absent = identical):
1. e1_eval: timing_cfg refuses `record`; a timing-head LEARNER seat needs records: per play row lp_card / lp_cell (T),
   allowed mask, the slot rows (hazard / tick draws: frozen, ratio 1) only as critic / GAE rows; th_ability presses likewise.
2. rl_royale: no timing path at all (no is_timing): minibatch_loss assumes a gate head (heads["gate"], lp_gate); the
   learner needs (a) `freeze_heads` (requires_grad False on hazard / tick / ab_hazard / ab_tick + their exclusion from the
   PPO terms), (b) the card / cell PPO + KL terms on play rows only, (c) `kl_ref_fixed: lambda` (= fixed beta, no
   adapt_beta, KL to the frozen imitation init on card / cell; or an alias of beta0 = beta_min = beta_max), (d) the
   update-0 identity assert for a gate-less model, (e) partner mix 60 / 40 (bot pool over our decks / human model vs
   itself on census deck pairs) -- check sample_matchups' existing keys first.
3. Fast loop: CfTrain ports the delayed-play schedule only (setJob refuses delay <= 0) -- a timing seat (frozen opponent
   OR learner) needs SelfPlaySide.apply's timing branch (th_tick re-decide at slot + j, play issued at the drawn tick, the
   next slot), per-seat extrapolate_ticks (0 for timing; CfTrain's extrap is per producer today), held plays + th_costs
   (Mirror) + th_decided in the decide, th_ability queued j ticks on through CfAbil (a 4th seat mode), and the producer's
   decide calling production's timing_decide_batch. compare.py then exercises the opponent-as-learner path.
Proposed split: (A) fast-loop timing seats for FROZEN P2 opponents (needed by the pilot too once v1 is in the pool) +
compare; (B) rl_royale / e1_eval opponent-learner keys + tests + smoke (pipeline owner = a learner worker, hunk commits);
(C) fast-loop routing of (B) + compare exactness. A before C; B in parallel.

## Lead rulings 10-28 (after the re-dispatch report)
- lp bar: in-process forwards 1e-5; SERVER mode 5e-5 WITH actions / outcomes / event tables / memory rows identical
  (measured server 1.33e-5 gate, 1.48e-5 cell, pilot-noiw msg; in-process 4.4e-6). rl_royale's update-0 assert unchanged.
- Known limitation: training rollouts use rl_royale's sampled decode and do NOT apply live's decide rules (finishers,
  barrel_lane, Rocket rules ...) while live does; CLXIII was trained the same way, so pilot-vs-CLXIII live is a fair
  comparison; the real successor must close it. pilot.yaml's fastloop.decode / live_options keys are dropped.
- The loop stays ALTERNATING (production's schedule) for the pilot; start at 4,096 matches / update on the 8x box and
  report the rows-used fraction per update (kl_stop_prev 0.02 binds).
- AVX512: untested (no pod / laptop has it); the boot gate stays strict (failure = BOOT FAILED, fixed on the box first).
- GB-DECOY SIM fix: BUILD it (opt-in, production facade + fast loop, absent key = byte-identical), on in pilot.yaml.
- NEXT TICKET order: (a) CfAbil + ability head + the 128-match ability warm start through the fast loop; (b) GB-DECOY;
  (c) learner-alongside bench within 33553's 62 GB (3 x 256, 2 actors); (d) pilot.yaml on fastloop >= 3 updates on 33308,
  records kept for LOOP-LRN.

## FAST-LIVEOPP: 'live'-policy seats (a frozen opponent with the deployed decision stack; 2026-10-30)
Why: OPP-PLATEAU's next experiment trains the opponent against CLXIII playing D3's LIVE_OPTIONS stack
(league_opp_policy live + league_opp_live); the fast loop refused it (`policy 'live': the fast loop samples`).
Spec -- what production's live decide reads (e1_eval.selfplay_decide live branch: ability_decide, posture_live,
decision_options.match_kwargs(sides), live_decide_batch) beyond the model row, at this option set (a, code read):
- the decision's engine BoardState `m._cur[1]` (my frame, look-ahead board): t_sec, my_elixir, my_hand, the 6 towers
  (hp_frac, alive, lane), every unit (cls, side, x, y, hp_frac, form) -> tau_phase / xbow / dead-lane (enemy alive),
  rocket_dead_target (princess_dead_state, enemy_body_tiles), tau_threatened (tau_threat_state), log_air (log_air_board),
  barrel_lane (barrel_goblin_tiles), rocket_value / rocket_tornado (the board itself);
- the raw state `m.state` at the decision tick: episode.crown_towers (side, type, x, y, hp, max_hp, destroyed) -> lethal
  (+ rocket_kills_king, lethal_log's record_hp history, lethal_quiet's recently_hit) and entities (log_air ground children);
- per-match history: princess-dead runs, tau threat state, the HP history, done_plays (landing tick, slot, cell centre);
- the row's projectile tokens (log_aim log_barrel), the deck names / ids, the per-match decision RNG (match_kwargs' seed).
All of it = LOOP-CTX's CfCtx.build output (HEAD 36 doubles + 8 sections, CfCtx.java header), identity-tested 10-28.
Wiring (as built, 33d1c0c / 9dd1cc8): CfTrain.enableCtx(Tables) once; setCtx(i, live0, live1) per job (after setJob);
reset() gives each live seat a fresh CfCtx.Seat; build() stage 1 runs CfCtx.build on the seat's TrainMatch right after its
obs into a thread-local scratch, then row r's slot (r * CTX doubles: {n, data}); a Tables miss (-1) rewinds the obs and
stops the row at stage 1 (Python's _fill runs cf_ctx.fill_missing, the obs re-runs); land(): an accepted play ->
Seat.played(pendLand, slot, cell). Producer: _ctx_on (cf_ctx.tables / options_for on the first live cfg; one option set
per JVM), _ctx_kwargs (cf_ctx.decode + cf_ctx.kwargs, match_kwargs' rng_decision_options seeding), _prod_group's live
branch = selfplay_decide's. A live group never goes to serve.py (live_decide_batch reads enc): in-process forward.
Opt-in: no 'live' seat = ctx None = no CfCtx call, no buffer (bytes as before). Refused: cfg pipeline_decisions / cfg follow_ups
on a live seat; gate_decode hazard, rocket_value_lead on / blend, rocket_value_threat on (cf_ctx.options_for).
Exactness (a): 16 / 16 identical (PLATEAU.md STATUS FAST-LIVEOPP; 33903 /workspace/fliv/out/cmp_live_b8.json).
Tools: msg_live.py (dumped msg -> live partner msg; --raw = path fix-up only), cmp_live.sh (compare on 33903's
/workspace/fliv/cb; RAW=1 = the no-live regression), fliv_tree.sh, fliv_smoke.sh.
Follow-ups (PORTED by FASTLOOP-FIX 10-30): the 48-job compare was 47 / 48 -- every divergence started on the decision
after a `rocket_tornado` play, whose decision carries follow_ups (decision_options.py ~2196: [{slot, cell, after_ticks,
within_ticks, afford_ticks None, require_first True}] from _sim_follow_up). Correction (c) to the spec that stood here: a
SELF-PLAY side does NOT run Match._apply_follow_ups (the ghost Match's, which advances the env inside one side's apply);
SelfPlaySide.apply -> _follow_start, and SelfPlayMatch.due drives it event-style (e1_eval.py ~2119-2196, ~2364-2403): the
first play waits in the seat's `pend` list at tick + self.delay (NOT + opp_style's _style_delay), each follow-up is a task
checked at grid(max(tick + after, tick + arrival)) on the 2-tick frame grid, at every due() stop after that tick's landings
(follow_up_verdict on raw() elixir_exact / the core hand / pend slots + costs, follow_up_have = min(10, elixir +
regen_between) - reserved), fire -> pend at max(land_a + max(t - tick - arrival, 0), t + 1), wait -> t + 2 unless past
expire; resolved -> next decision tick + de * ((last landing - tick) // de + 1); nxt includes pend heads and check ticks;
the other seat keeps its own schedule (no shared-env advance inside an apply). CfTrain port (as built): setFollowUps(r,
arrival, costs, ints) from producer._follow_ups after the live decide writes the play; apply() -> followStart; due() lands
the seat queue after the delayed play, then followCheck(i, s, t) for both seats, then done / mask / nxt (pend heads + check
ticks); land() returns accepted (a_landed / a_acc of the first play); verdict() = the rule list, planted-tested against the
Python (test_follow_verdict.py: 800 cases, all 8 branches). JVM totals in P.run stats "follow_ups" [plans, fired,
cancelled]. Only a 'live' seat's decide emits follow_ups; no follow_ups = no queue / task touched (rows as before).
CfCtx race (found by FASTLOOP-FIX): CfCtx.build's -2 compares the SHARED Names.missing size before / after its unit pass, so
another pool thread's obs miss fails an innocent row -> ctxRow threw -> the match counted as crashed (skipped). ctxRow now
rebuilds while -2 is not this row's own miss (TrainMatch.missed); -2 returns before any Seat / output write.

## Design (as built)
- `CfTrain.java`: N facade matches per producer on T threads. Per match: e1_eval.SelfPlayMatch.due / SelfPlaySide.apply /
  Match._land ported (delayed plays, crforge's 20-tick engine delay, landing before deciding, tail cap, warm-up), every
  deciding seat's GenModel row built by the obsid builders in Match.prepare's order (rows at fixed slots 2 * match + seat).
  A builder that meets an unfilled table key leaves its row at that stage; Python fills, `rebuild()` resumes it.
- `producer.py`: one process, in-process JVM. Per job: real `e1_eval.SelfPlaySide`s built on a capture-only env (decks,
  slots, costs, RNG streams, cfg exactly as SelfPlayMatch.__init__). Per round: one forward per policy on a batch gathered
  from the JVM buffers, then PRODUCTION `SelfPlaySide.pre`, `e1_eval.sample_decide_batch`, `SelfPlaySide._record`;
  actions back into Java. Results = SelfPlayMatch.result's fields (monitor-only approximations listed in result["fastloop"]).
- `fastloop.py`: rl_royale's own `main` with ActorPool.run('selfplay') routed to K producers (everything else unchanged).
  Entry / STOP / FINAL / throughput.jsonl: see its docstring (LOOP-OPS' launcher calls it).
- `compare.py`: production actor vs producer on a dumped message, all sides' decisions traced (`show_div.py` prints the first
  divergence). `bench.py` / `bench.sh`: throughput without the learner.

## Found and fixed (a)
- cf_loop_obs.Cohort.fill resolved opponent detector keys from the key's form, which lacks STATUS_EVOLVED (CfOppElixir key);
  production resolves the real raw() entity -> an evolved card read as form 0 in opp_past / opp_cycle (4 / 4 matches diverged
  at ticks 1900-2700). producer._fill restores bit 8 from the body row name (CfCore.evolvedBit's rule): then 16 / 16 identical.
- fastloop shadowed `run` (FINAL never written; LOOP-OPS found it).

## Not ported yet (each raises NotImplementedError, never silently wrong)
hero presses, memory, opp_style / exploiter decode, decide rules in the sampled decide, record_phi / habit / crown / spell
tracking, tower troops, mid-match starts, posture / ability heads.
