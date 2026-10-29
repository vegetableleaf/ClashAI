# P3-FORK3 (account 2, 2026-10-29): STATUS ADDENDUM (read first; P3-FORK2's addendum and P3-FORK's status follow)

## PAUSED 2026-10-29 ~18:25 UTC (lead wrap-up, owner usage 80%) -- RESTART POINT
- Pod 32657: NOTHING of mine runs (f3oplcB3, f3ftR4, f3redir stopped by exact PIDs at ~18:15; 0 rl_royale / spawn_main left; GPU 1 MiB).
  f3base2 (5 upd), f3ftR3 (2 upd), f3redir (2 upd) finished their data; f3oplcB3 / f3ftR4 have u0 only (128 matches each).
- Data on the laptop (gitignored) `cf/data/`: f3base2.jsonl 1ece94c8, f3ftR3.jsonl 73853351, f3ftR4.jsonl 600124fb, f3oplcB3.jsonl
  f7e8a944, f3redir.jsonl e11447ce (pod copies /workspace/cf3/logs/, sha equal), opp_response_human.json; f3_arms.md = P4_F3_ARMS.md.
- RESULTS + verdict: P4_AUDIT.md section 9 (read it). One line: the forced-Rocket negative price is (a) real in the SIM after every
  artifact check (engine, two human-like opponents, horizon to the end, spec fixes); the chip itself is paid +0.09 / +0.18; on the
  human estimand (chosen moments) the SIM equals live and pros; Tornado-redirect's negative price was a target-rule artifact
  (fixed opt-in cf_redirect_king_tiles: -> +0.003, ~0).
- NEXT artifact check (in order): (1) "chosen-like moments": a Rocket alternative only where the policy's own P(Rocket) is high
  (opt-in key, not built), compare with rocket_played; (2) rerun ftR / oplcB to >= 3 updates (critic adapted) and with an
  opponent calibrated on X-Bow defence once P2-OPP has one (lock .47), since the displaced-line term depends on it;
  (3) training rows for prefix steps (P6_DESIGN 5) before any macro gets weight; (4) lead: switch on cf_redirect_king_tiles 9.0
  and cf_rocket_lead drift in production configs (both opt-in, hash-neutral off).
- Commands (from /workspace/cf3 on 32657; tree cfh10 = commit 8743a53 code incl. the redirect key; cfh9 = the same minus it):
  arms `TREE=/workspace/cf3/cfh10 TIMEOUT_S=25200 MAXU=3 ./fork3_run.sh RUN CPUS N ftR|oplcB|base actor_timeout_s=14400 in_flight=2`
  (timing-head opponents: ~250-400 s per match per actor -> keep actor_timeout_s 14400 + in_flight 2, else the actors time out at
  3600 s in a loop); redirect `CFP="{tornado_redirect: 0.05, rocket_tornado: 0.0, rocket: 0.0, rocket_played: 0.0, xbow_after_fail:
  0.0, wincon: 0.0, siege: 0.0, xbow: 0.0, idle_full: 0.0, log_bait: 0.0, random: 0.0}" ... base cf_redirect_king_tiles=9.0`.
  Tables: `python fork3_tables.py base=data/f3base2.jsonl ftR=data/f3ftR_all.jsonl oplcB=data/f3oplcB3.jsonl --from-update 0`,
  `p4_audit.py DUMP --from-update 1`, `sim_assoc.py DUMP`, `python -B opp_response.py both` (laptop).
- Codex: P3FORK3_1 (babysit + collect, low) x2 -> BLOCKED both times (own watcher bug; then the stopped f3ftR2 run had no dump);
  collection done by me. Ticket .foreman/scratch/a2/codex/P3FORK3_1.md.

Job (owner 10-29 morning): find WHY the SIM prices the Rocket family negative and remove any SIM / opponent / measurement artifact;
never tune numbers until they turn positive. Labels: (a) measured, (b) plausible / untested, (c) contradicted.

## Built (commit "P3-FORK3: cf_credit opt-in diagnostics + the two P6 macros ..."; smokes f3smoke2 + f3smoke3 SMOKE PASS on 5e8089a4)
- Also `cf_redirect_king_tiles` (null = off; tornado_redirect also needs the unit within N tiles of OUR king; see Findings) and
  the fork engine-refusal guard (a JVM exception inside a fork set drops that sample, match record `fork_errors`; ours re-raise).
- pipeline/cf_credit.py (opt-in, absent = byte-identical + the historical hash): `cf_rocket_empty` (the rocket / xbow_after_fail /
  rocket_cycle triggers also fork a Rocket into a point with nothing within 5.5 tiles: elixir + card cycle, no damage -> the
  decomposition rocket_princess - rocket_empty = the chip's own value, rocket_empty - chosen = the price of spending it);
  `cf_diag_plays` (cf_diag dg records list both sides' cards landed since the root: what the opponent does after our Rocket);
  the P6 macros as opt-in triggers `rocket_cycle` (= library rocket_cycle.after2) and `def_xbow` (= def_xbow_hard, with the
  counter-lock PREFIX executor: the fork learner's decision replaced by the scripted step at its first availability), library
  pinned by sha 828cedf7 (test). NOT built: training rows for prefix steps after the root (P6_DESIGN 5).
- Tests: pipeline/tests/test_cf_credit.py 38 pass / 3 skip on pod 32657 (crforge 5e8089a4, tree cfh8, logs/f3_test4.log);
  new: TestRocketEmpty, TestMacros (library pin, config / hash, matchup_ctx), TestMacroPrefixFork (engine: the prefix plays its
  card in its own fork only; candidate 0's Q identical with / without the prefix candidate; the real match untouched).
- scratchpad/gauntlet/L74/plan1026/cf/fork3_run.sh (pod launcher, arms base / ftR / oplcB), opp_response.py (human side of the
  opponent check), sync_tree.sh now also strips CR from .json (the archived LIBRARY.json had CRLF on the pod: sha a023eea5).

## Running (pod 32657, started ~13:50 UTC, tree /workspace/cf3/cfh8, crforge 5e8089a4 + facade build_5e, tables 16.402.22)
- f3smoke (CPUs 26-27): the real `rl_royale --smoke` with the new keys + macros on (log logs/f3smoke.log; wait for SMOKE PASS).
- f3base (CPUs 0-8, 9 actors): the cfaud3 pilot league = the 5e8089a4 baseline arm.
- f3ftR (CPUs 9-17, 9 actors): every matchup vs ftR (/workspace/cf3/opp/opp_ft_s0_R_sim.pt, sha 28ef721b, from 33903).
- f3oplcB (CPUs 18-25, 8 actors): every matchup vs arm B u0120 (/workspace/cf3/opp/oplc_ftR_l003_a10_u0120.pt, sha 7aefe312;
  the strongest arm-B checkpoint at launch: CLXIII W 383/480 in the lead's D3).
- NAMES (actual): f3base2 (base), f3smoke2 / f3smoke3 (SMOKE PASS). f3ftR2 / f3oplcB2 were STOPPED at 15:42 (exact PIDs): a match
  vs the timing-head opponents with forks takes ~250-400 s per actor (smoke f3smk_ftR3: 8 matches / 4 actors in 505 s), so an
  actor's 8 in-flight matches passed actor_timeout_s 3600 and every actor was killed + restarted in a loop (log "ACTOR n CRASH
  (process timed out)", JVM hs_err files in cfh9/). Relaunched 15:43 as f3ftR3 (CPUs 9-18, 10 actors) and f3oplcB3 (19-27, 9)
  with actor_timeout_s=14400 in_flight=2 MAXU=2 TIMEOUT_S=25200 (run.sh now takes TIMEOUT_S; default 14400 unchanged):
  `TIMEOUT_S=25200 MAXU=2 ./fork3_run.sh f3ftR3 9-18 10 ftR actor_timeout_s=14400 in_flight=2`.
- All: 5 updates x 128 matches, policy fixed (critic warm-up = max_updates), cf_diag + plays, rocket_empty, macros (rocket_cycle
  p 1 to the end, def_xbow p 0.3 horizon 1200), Rocket family as cfaud3 (rocket 0.006, rocket_tornado 0.5, tornado_redirect
  0.004, xbow_after_fail 0.05, rocket_played 1), horizon 900 + sweep 150..1200, audit_p 0.3. Dumps logs/<run>.jsonl.
- Restart (only if dead; not resumable, use a new name): `ssh -p 32657 ... 'cd /workspace/cf3 && ./fork3_run.sh RUN CPUS N ARM'`.
- Stop: exact PIDs (pgrep -n -f "^/workspace/venvf16/bin/python -u -m pipeline.rl_royale --run RUN"), then the PIDs in
  cfh8/icebow/data/bench/rl_royale/RUN/actors.pid.

## Results 5e8089a4 (f3base2 DONE 16:10, collected data/f3base2.jsonl sha 1ece94c8, tables data/f3base2_tables.md + _fork3.md;
## opponent arms f3ftR3 / f3ftR4 / f3oplcB3 MAXU 2, u1 due ~18:00-18:45 UTC; draft section 9 for P4_AUDIT in progress)
- (a, base u1-4, 512 matches) chip Rocket - policy -0.230 [-0.264, -0.196] (terminal -0.087 [-0.236, +0.055]); Rocket into nothing
  - policy -0.321 [-0.363, -0.280] (terminal -0.243 [-0.387, -0.097]); chip itself (princess - empty) +0.089 [+0.064, +0.113]
  (terminal +0.181 [+0.070, +0.293]). The SIM pays for the chip; the price is the spend at an unchosen moment.
- (a) sim_assoc.py: the live-style association inside the SIM (CLXIII's own chip Rockets vs could-but-did-not, own princess HP lost
  over 45 s, 1x) base -0.033 [-0.077, +0.013], cfaud3 +0.008 = live +0.004 = pros -0.005: the SIM reproduces the human estimand.
- (a, u0 only, critic not adapted) opponents: Rocket into nothing base -0.315 / ftR -0.363 / oplcB -0.337; own princess lost after a
  forced chip +0.171 / +0.156 / +0.110; foe princess lost -0.048 / -0.169 / -0.157 (vs the human-like opponents the displaced
  X-Bow line is worth more: they let it lock). rocket_cycle to the end -0.051 / +0.015 / +0.017 (n 775 / 56 / 73).
- (a) macros base: rocket_cycle end -0.062 [-0.103, -0.021] (human win +0.091); def_xbow def - bridge 1200 -0.066, end +0.044
  [-0.174, +0.258] (n 35; human +0.117); the policy's own continuation Rockets within 600 ticks in 1% (control = no Rocket).

## Findings so far (cfaud3 re-reads are fe364ceb; the 5e8089a4 arms above replace them when done)
- (a) Human side (opp_response.py -> data/opp_response_human.json; association with selection: people chip when it looks safe).
  45 s after a chip Rocket vs "Rocket in hand, >= 4 elixir, no Rocket" moments, OWN princess HP lost (princess units):
  pros 1x -0.005 [-0.023, +0.016] (n 327 Rockets), 2x +0.020 [+0.003, +0.038] (446), OT +0.049 [+0.031, +0.064] (580);
  live CLXIII vs humans 1x +0.004 [-0.043, +0.056] (29), 2x -0.064 (16), OT -0.095 (11). Their opponents' plays in the window:
  pros 1x +0.10 [-0.11, +0.32], live 1x -0.49 [-1.01, +0.01]. SIM forced chip Rocket (cfaud3): own princess lost +0.21 1x / +0.16 2x.
- (a) The SIM does NOT price the policy's OWN Rockets negative: rocket_played wait - chosen = -0.035 [-0.072, +0.001] (n 159, i.e.
  its Rockets are worth +0.035 vs waiting), own princess lost +0.017 [-0.02, +0.05] (no defence cost), foe princess lost -0.035.
  The -0.24 is the price of a Rocket FORCED at a random affordable decision vs the policy's own action there; humans' lifts are at
  moments they chose. Estimand mismatch (measurement), not by itself a SIM defect. At selected moments SIM and humans agree:
  no defence cost, chip ~ +0.03..0.06 net.
- (a) Time profile of the forced chip Rocket (cfaud3, rocket_princess - chosen, 150 / 300 / 450 / 600 / 750 / 900 ticks): foe
  princess lost +0.087 / +0.062 / +0.020 / -0.020 / -0.059 / -0.078 (the chip lands, then the policy's own line out-damages it by
  ~0.165); own princess lost +0.011 / +0.063 / +0.119 / +0.149 / +0.183 / +0.198; own crowns lost +0.121 at 900; FOE plays -0.42 at
  450, foe elixir +0.68 at 450 (the opponent, no longer answering our line, banks and then pushes). Reading (b): the cost is the
  displaced pressure of the policy's own line, collected by the SIM opponent; the opponent arms test whether a human-like
  opponent collects it the same way.
- (a) Tornado to our king is NOT an engine gap; the trigger's target rule is too wide. tornado_king - tornado_on (cfaud3) by the
  unit's distance to OUR king: < 9 tiles (n 53) our king activated +0.061 [+0.019, +0.122] at 150 ticks, own princess lost -0.038
  [-0.086, +0.007] at 900, dQ +0.020 [-0.038, +0.080]; 9-12 tiles (n 103) dQ -0.109 [-0.169, -0.052], own princess lost +0.047;
  12+ (n 96) dQ -0.022. crforge does activate the king when the pull brings the unit near it; redirect_target accepts units within
  12 tiles of our princess, mostly too far for the pull to reach the king (candidate fix, opt-in, not built: a king-distance limit).
- (a) Engine on the Rocket path (ENG's SME.md, not re-measured here): elixir regen exact (178 / 357 per tick, both sides to 1e-4),
  Rocket crown-tower damage 546 = live 7/7, overtime tiebreak = the game (15 FRESH2/3 OT matches exact to the end). Pooled strict
  fresh battles exact 109/132 (CP lower 0.762): fights given the same inputs match live, so the forced-Rocket defence cost comes from
  the two policies, not the engine (b: the inexact 17% are not split by phase of play).

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
- RESULTS (details P4_AUDIT.md, tables P4_TABLES_cfaud3/4.md, persona P4_PERSONA_cfaud3.md): cfaud3 DONE (1,024 matches, 1,926 samples u>=2); cfaud4 (cf_rocket_lead=drift A/B) died at u5 on a crforge
  engine exception (Deflect ... king tower without a target, not modelled) after 4 usable updates. Pod 32657: NOTHING of mine is running; trees cfh5 (cfaud1-3), cfh6 (cfaud4 + cf_rocket_lead).
- Codex: ticket .foreman/scratch/a2/codex/P3FORK2_1.md (collect + tabulate) was written but NOT dispatched: the run ended while I was working on it and the collection took 3 commands (latency); no Codex dispatch this seat.
- NEXT (lead's 10-28 evening order): macro prefix alternatives, opt-in, starting with (1) rocket_cycle.after2 / Rocket cycling after a failed X-Bow in 2x/OT (horizon 600) and (2) def_xbow_hard (horizon 1200 / end, K 2);
  executor per MACROS.md "What P3-FORK needs" (our-frame tiles -> cells, abort if the card is not in hand, 'none' prefix = mask the card class for the window, pin LIBRARY.json sha 828cedf7...); candidate rows for EVERY prefix
  action (P6_DESIGN.md prefix rows); cheapest root for rocket_cycle = the OT/2x states (ot_start_share). NOT built in this seat (the audit consumed it).
- Current run (superseded): cfaud3 (same config as cfaud1 + cf_cap_ticks=40000), started 21:03 UTC, dump /workspace/cf3/logs/cfaud3.jsonl.
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
