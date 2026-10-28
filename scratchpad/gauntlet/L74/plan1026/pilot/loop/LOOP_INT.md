# LOOP-INT: the fast crforge training loop (integrator)

Labels: (a) measured, (b) untested, (c) contradicted.

## STATUS (keep current; 2026-10-28 ~16:30 EDT, account switch STOP)
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
- Uncommitted-before-STOP code is committed with this STATUS (server mode in producer / bench / serve.py: verified by the
  bench run above only; compare.py has NOT yet been run in server mode -> do that first).
- NEXT (in order): (1) compare.py in server mode (exactness with v_old/wver); (2) bench grid on 33553 with server:
  K = 6/8/12 producers, M 256/512, graphs mode, + LOOP-LRN's learner together; (3) wire CfMem (LOOP-MEM, 70a9c3d API in
  SPEED_CRFORGE.md), CfAbil (LOOP-IW, 7a747da; JVM flags --add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED),
  loop_opp (LOOP-OPP 8797e07), CfCtx (LOOP-CTX 2542689) one at a time, compare.py after each; (4) pilot.yaml on
  fastloop (B0 needs CfMem); (5) projection doc. GB-DECOY note (evo barrel decoy rename) tracked, not built.
- Restart: bench `ssh -p 33553 ...; cd /workspace/loop && bash cb/scratchpad/gauntlet/L74/plan1026/pilot/loop/bench.sh
  OUT.json 0-31 --producers 4 --matches 256 --threads 4 --server eager --warm 150 --seconds 120` (33553 tree:
  /workspace/loop/cb = pod copy + these files; venv /workspace/venv; ship pipeline/policy_server.py from origin/main).
  A/B arms: `33308: cd /workspace/loop/cb && scratchpad/gauntlet/L74/plan1026/pilot/loop/run.sh rl|fast RUN CPUS k=v`.
  compare: `bash /workspace/loop/cmp.sh MSG.pkl OUT.json [--in-flight 8 --matches 8 --threads 4]` (33308).
- Nothing left running by me (33308 lint_* runs DONE; 33553 bench exited). 33553 is KEEP (clean throughput pod).

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
