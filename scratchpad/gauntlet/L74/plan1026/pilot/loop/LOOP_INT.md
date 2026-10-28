# LOOP-INT: the fast crforge training loop (integrator)

Labels: (a) measured, (b) untested, (c) contradicted.

## STATUS (keep current; 2026-10-28 ~18:30 EDT, re-dispatch on account 2)
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
    presses 22 / 17 per side both paths; lp max 1.9e-6. OPEN: memory tables 13/16 equal (vals / vpe differ in 3), MEM
    rows 4,418 / 5,201: under diagnosis (decisions unaffected at B0: mem.out = 0).
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
