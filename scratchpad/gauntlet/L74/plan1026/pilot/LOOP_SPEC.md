# Fast crforge training loop: shared spec (2026-10-28; owner: "full fast loop today, several hundred thousand matches/h")

Every LOOP-* ticket works against this file. If you need to change an interface, message the lead (and the integrator,
LOOP-INT); don't change it silently. Labels: (a) measured, (b) untested, (c) contradicted.

## Goal
PPO training of B0 (CLXIII + the S3-aux memory encoder, sha 3d75a25d, coupling zero, so identical to CLXIII at u0) on
crforge at >= 300k matches/h on a rented 8x RTX PRO 6000 pod (about 27 vCPU per GPU, 96 GB each), with:
- rollouts: actions and outcomes identical to rl_royale's crforge path; log-probs within 1e-5 (in-process forwards).
  LEAD 10-28: in SERVER mode (LOOP-SRV forwards) log-probs within 5e-5, WITH actions / outcomes / event tables / memory
  rows identical (GPU batch composition changes fp32 rounding; measured 1.33e-5 gate / 1.48e-5 cell at T_gate 0.1,
  loop/LOOP_INT.md 2b); rl_royale's own update-0 on-policy assert is unchanged;
- the learner: rl_royale's PPO math (GAE gamma_tick 0.99994, lambda 0.95, lr 1e-5, clip 0.2, critic warm-up 5, batch
  512 matches) plus the NEW opt-in kl_stop_prev 0.02 (rl_royale had no KL early stop; LOOP-LRN adds it: minibatch KL to
  the previous update's policy via kl_ref_refresh_every 1), with the KL penalty off (beta0 = beta_min = beta_max = 0;
  the owner's no-leash rule);
- the reward: R_win + potential shaping gamma*Phi(s') - Phi(s), Phi = P_hat(win | tower terms, time to go) - 0.5,
  Phi(terminal) = 0.

## Measured building blocks (read their docs)
- crforge engine in long-lived JVMs: 0.09 core-s/match; CfLoop = Java envs + Java obs at about 0.27 core-s/match total
  (scratchpad/gauntlet/L74/speed/crforge/SPEED_CRFORGE.md; obsid/CfLoop.java, cf_loop_obs.py).
- Java observation: all 20 GenModel keys byte-identical to production at the live cfg (obsid/: CfSpeed, CfObsBind,
  CfIdent, CfOppElixir, CfPubObj, CfCue; obs_id.py is the per-key identity harness).
- GPU policy server: pipeline/policy_server.py (S4b, d685350): producer processes write row blocks to shared memory and
  run decision_options.decide; the server only does forwards; bucketed batch sizes (a new batch shape costs about 210 ms
  on first use); 98.6% of bare forward rate.
- rl_royale's crforge path (the reference for correctness): ROYALE_ENGINE=crforge, pipeline/crforge_core.py; production
  config succ48_x_s101; learner_deterministic option (f42674c); the unit-type cache.
- crforge build: the consolidated clashbot-main from CF-MAIN (crforge/fork/MAIN.md when it lands); until then
  lib_cfclone on pod 30408 / lib_f635c.

## Architecture (per pod; the integrator owns the final call)
1. Env processes: K JVMs (start at 12 JVMs x 4 threads per 54 cores, as S3 measured best), each thread running M
   matches in lockstep (CfLoop), building the Java obs for every seat that decides this tick.
2. Producer processes (Python, one per JVM): read obs blocks from shared memory, call the GPU server for forwards,
   run decide() (LEAD 10-28: rl_royale's own sampled decode, NOT the live decision rules: rl_royale has no live decode;
   known limitation, see loop/LOOP_INT.md),
   write actions back to the JVM, and append each finished match's trajectory to the record queue.
3. GPU policy server(s): one per inference GPU; serves the learner policy AND the frozen opponent pool (several
   models; the S4 Merged vmap only covers same-architecture models, so serve others separately); weight versions are
   pushed by the learner.
4. Learner: 1+ GPUs (DDP if one GPU can't keep up); consumes trajectories in rl_royale's collate format; PPO update per
   512 matches; pushes weights; checkpoints copied off-pod.
5. Orchestrator: starts and supervises everything, with a clean stop (STOP file) and a throughput log
   (matches/h, rows/s per stage).

## Interfaces
- Obs block: GenModel input arrays keyed exactly as obs_id.py compares (tok, mask, sc, unit_form, past, the hand/deck
  identity keys, opp_past, projectiles, effects, own_ability, opp_cycle, cue, plus the memory and ability inputs below).
- Missing in Java today (each its own ticket; until it lands the integrator may compute it in Python from Java-exported
  events, with the speed cost logged):
  a. memory v2 tables (e1_eval.Match._memory) -> LOOP-MEM;
  b. decide-rule context (everything decision_options.decide reads besides model outputs: enemy_alive, lethal state,
     projectiles, Barrel goblins, ...) -> LOOP-CTX;
  c. the IW press observation (royale_env.ability_commands / ability_options) -> agent D2-T2 (a64b9e73ee1723145);
  d. per-opponent decide intervals and the opponent policies' own inputs -> LOOP-OPP.
- Trajectory record: exactly what rl_royale.collate consumes per match (LOOP-REC defines it, with a converter test
  against rl_royale's own records).
- Correctness: each Java port is byte-identical to the production Python on >= 38,400 seat-rows through the obsid
  harness. End to end: the integrator compares against rl_royale's crforge path on the same seeds and opponents.

## Rules for every LOOP ticket
- Path-limited commits (git commit -- <paths>) plus push; never git add -A; never stage another agent's files.
- Production behaviour unchanged when the new code is off (fin16 and rl_royale's rows byte-identical: smoke batch shas
  crforge e816a6a4 / f060b678, fin16 d4ef5467 / 6cd7292f).
- pyflakes plus a real smoke before pushing trainer/eval code.
- Stop processes by exact PID only (a hook blocks pkill -f and killall); never `python -`; never read or log the
  opponent's hidden hand or elixir in live-facing features.
- Pods: 33308 (2x4090, 108 cores, 251 GB; root@157.157.221.29 -p 33308), 30408, 32657, 33920 (SSH
  ~/.ssh/runpod_clashbot; hosts in SME.md / SPEED docs). They are shared: check load and memory first; integration and
  throughput runs have priority on 33308.
- Report DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT with (a)/(b)/(c) labels.
