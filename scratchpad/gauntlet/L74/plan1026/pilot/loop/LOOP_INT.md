# LOOP-INT: the fast crforge training loop (integrator)

Labels: (a) measured, (b) untested, (c) contradicted.

## STATUS (keep current)
- DONE (a): skeleton end to end on 33308 (run `lint_smoke1`, 2 updates); correctness vs production `rl_royale.actor_main`
  on one dumped actor message (16 matches, same process, cuda, TF32 off, batch-1 forwards): **16 / 16 matches identical**
  (every side's decisions, every traj key byte for byte), log-prob max |diff| 2.3e-6 (`/workspace/loop/cmp_d1_16_b1.json`).
- RUNNING: batched comparison (fast 8 matches in flight vs production in_flight 8, `cmp_d1_16_b8.json`); 3-update A/B
  `lint_c2_rl` vs `lint_c2_fast` (33308, logs /workspace/loop/logs/); first throughput bench on 33553 (`/workspace/loop/b/`).
- NEXT: throughput grid on 33553 (K producers x M matches x T threads), per-stage split, 8x RTX PRO 6000 projection;
  wire LOOP-SRV's PolicyServer (one per GPU) in place of the per-producer forward; then LOOP-MEM (CfMem), LOOP-IW (CfAbil),
  LOOP-OPP (loop_opp), LOOP-CTX (CfCtx) one at a time, each re-running compare.py.

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
