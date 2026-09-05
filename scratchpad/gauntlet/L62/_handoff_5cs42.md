
### §5cs.42 -- L62c (2026-09-05 17:3x-17:5x UTC): EngineMatchEnv v0 BUILT AND MEASURED -- SimMatchEnv-interface env on the real engine with a recorded-human ghost opponent; cell<->engine inverse EXACT (9,368/9,368); determinism 3/3; **1,159 matches/h one slot, 1,847/h two slots on one VM with the BC policy in the loop** (cuda NOT faster at batch 1); RETRACTION of the planned "ghost rejection rate" diagnostic -- a ghost never desyncs (0 game-state refusals in 799 commands), it goes STALE and RUNS OUT (**50% of ghost commands never fire** because the BC policy loses faster than the human it replaced: 4W/36L vs those humans' 26W/14L); a real engine rule found (no deploys before tick 90 = 4.5 s countdown). VM stopped 17:33 UTC.

Source: `scratchpad/gauntlet/L62/engine_env.md` (agent, STATUS complete). Code `L62/engine_env.py` (EngineMatchEnv),
`build_ghost_pool.py` -> `icebow/data/ghost_pool/pool_env_v0.jsonl` (477 entries, own schema with `deck_index` in the
engine's final permuted order; outside git), `prewarm_deal_cache.py`, `run_engine_env.py` (map/smoke/det/bench, greedy
policy), `analyze_bench.py`. A crawler (2 procs) ran throughout; every wall number includes it. (a) unless marked.

**A. The env.** `reset() -> obs`, `step((play, card_id, cell)) -> (obs, r, done, info)`, `hand_vec/next_vec/elixir_vec/
threat_vec`, n_cards 10, n_cells 432, threat_dim 52, obs (96,64,12) -- the trainer's contract. card_id = DECK IDENTITY
index into `deck_keys` (evos separate), cell row-major on 18x24, `deploy_clamp` first -- verified against
`sim/env.py:3161`. Obs = the L61 adapter verbatim (`frame_to_engine` + `SimMatchEnv._update_vectors`); the hand is
overwritten from the engine's `hand_deck_indices` each step (engine hand, not a cycle model). Ghost = the recorded
human's `(tick, deck_index, x, y)` list issued at its ticks with the 40-tick elixir slack; our side acts every 10
ticks (0.5 s). Reward, unshaped, engine-only: `(their tower HP lost - ours)/3052 + d(crowns) + terminal +-3`
(`reward_spec()` returns the formula). Boot 73 s first try (the 1-in-3 flake did not bite).
- Cell<->(x,y): the inverse is exact (9,368/9,368 pro plays recover their cell, residual 0.0003 tiles); the
  (x,y)->cell->(x,y) round trip is the grid quantisation alone: mean 0.381 tiles, max 0.834 (= L61's 0.383 / 0.833).
- **Engine rule the replay driver never met:** every deploy is refused with result_code 22 (`placement_valid: true`)
  until tick 90 = 4.5 s -- the pre-battle countdown; the crawl's earliest human play is tick 102. Episodes now start
  at tick 90 (final hash unchanged).
- Determinism: 3/3 identical final state_hash / tick / crowns / reward; CPU and cuda policies identical.

**B. Throughput with `bc_bias_native_s0.pt` greedy in the loop.** 1 slot CPU **3.11 s/match = 1,159/h**; cuda 3.13
(NOT faster: batch-1 launch overhead, policy share 28% -> 36.5% -> use CPU workers); 2 slots one VM **1.95 s/match
aggregate = 1,847/h (1.59x)**, per-slot +20% (= L61's contention). Per decision: observe (full) 3.87 ms, step 2.62,
obs render 1.52, act 1.61, policy ~7.3 ms (CPU, 2 threads). The biggest lever is the FULL observe -- only the
`kind` (deploying) flag needs it; compact is ~1.6 ms (L61). vs the sim trainer's ~2,880/h on 16 cores (§5cs.35):
the engine at 2 slots is 0.64x the sim's match rate at 100% parity instead of 26%.

**C. RETRACTION of the planned diagnostic.** §5cs.40 asked for "ghost rejection rate as the match diverges". Raw:
0.35 rejections/match, 0% at 0-60 s rising to 11.7% at 180-240 s -- looks like desync. **It is not:** every rejection
is `native_4` and lands 0.55-4.0 s before the terminal tick; the engine's terminal state reports
`commands_allowed: false, command_gate_code: 4` = the end-of-battle gate. **0 ghost plays refused for a game-state
reason in 799 commands over 40 matches.** Mechanically obvious in hindsight: the ghost is a separate player whose
elixir/hand/cycle we cannot touch; placement legality only widens when a tower falls; the 40-tick slack absorbs
elixir timing. A recorded ghost does not desync -- it goes STALE (answers a board that no longer exists; the pool
agent's ~1-in-12 time-locked-reaction floor, §5cs.41 E) and it RUNS OUT: **787/1,579 ghost commands (50%, per-match
median 54%) were never attempted because the match ended first.** Trap: never use a rejection counter as a
staleness instrument on this env.

**D. Sanity, 40 matches, greedy BC.** 40/40 terminated (0 tail-capped), mean length 168.6 s (67-307), **4W/36L**,
crowns 0.70 for / 2.50 against, our plays 15.9 accepted/match, 0 unmapped entities, mean episode reward -6.17. The
human icebow players went 26W/14L on the same 40 battles -- the ghost pool is not an easy pool and the BC head is
far below the players it replaces. Baseline, not a bug. (Winrate is quoted as a description of the pool, not as a
discriminator.)

**E. v0 limits, unaddressed (agent §9, endorsed):** ghost cannot react (half its plan is dead weight once we are
worse than the human); one replay seed 424242 for every episode (opening deals never vary -- varying it is one line
but the deal cache key must become (tag, seed) and a miss costs a reset; b); card levels constant 11; evo form in
`hand_vec` is the sim's charge rule, the engine decides (b, unquantified); spells in flight not rendered (both
datasets); all 477 entries have icebow on side 1 -- the mirror path is implemented, never exercised; decision cadence
0.5 s untuned; whether PPO learns from the unshaped reward at this cadence is UNTESTED -- that is the next
experiment.

**Decision (owner order §5cs.40 "start the engine training").** Next build = a standalone engine PPO driver
(`train_sim_ppo` is one 2,378-line closure -- not reusable piecewise): PPONet copied, `masked_logits` semantics
reproduced, GAE + clipped surrogate, plus a per-board KL(policy cell dist || pro prior for the chosen card) term.
The PAIR launches together, one slot each on the same VM, same init `bc_bias_native_s0.pt`, same seed: control
(coef 0) vs KL arm -- one change. ~2.2 h per 2,000 matches per slot. Grade with `L61/read_ckpt.py` (pro agreement
on both val sets + rails) at m500/m1000/m2000, never winrate.
