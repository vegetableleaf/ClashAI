# L62 -- EngineMatchEnv v0: a PPO training environment backed by the REAL CR engine
Started 2026-09-05 13:0x. Every number MEASURED on this box unless explicitly marked UNTESTED.
Box note: a crawler (2 python procs, icebow wave4) is running throughout; all wall-clock numbers below
include that contention.

## 0. Inputs read (not re-derived)
- scratchpad/gauntlet/L61/engine_bc_v2.md  -- engine boot/throughput/adapter/name-mapping facts.
- scratchpad/gauntlet/L61/build_bc_v2.py   -- THE ADAPTER (engine frame -> FakeEngine -> SimMatchEnv._update_vectors).
- scratchpad/gauntlet/L61/replay_drive_rec.py, research/sandbox_tools/replay_drive.py -- engine API.
- scratchpad/gauntlet/ext/svc_start4.ps1   -- flaky-boot retry wrapper.
- scratchpad/gauntlet/L62/ghost_pool.md    -- NOT PRESENT at 13:02 when this run started; the ghost-pool
  schema was therefore derived independently from replay_drive.load_battle (see section 2).

## 1. Boot (MEASURED)
- 13:02:26 `scratchpad/gauntlet/L62/_boot.ps1` (svc_start4 wrapper, but `--workers 2 --base-port 37031`).
  Attempt 1 succeeded, `=== end 13:03:39` -> **73 s, no retry needed** (L61's ~1-in-3 flakiness did not bite).
- Both slots ready: slot 0 port 37031, slot 1 port 37032; tick 10, state_hash d036bec06e300550 on both;
  tower_max_hp [3052 x4 princess, 4824 x2 king]. Direct transport mappings host 38031/38032 -> guest 37031/37032.
- Host ports 37031, 37032, 38031, 38032 all accept TCP. 37031/2 = adb forward, 38031/2 = emulator redir
  ("direct transport"); L61 measured the direct one at ~2 ms/RPC.
- Free RAM before boot 11524 MB.

## 2. Ghost pool (BUILT HERE -- ghost_pool.md was absent at 13:02, so the schema is mine)
Builder `scratchpad/gauntlet/L62/build_ghost_pool.py`, output `icebow/data/ghost_pool/pool.jsonl` (+ pool_build.json).
Source = the 211 already-driven L61 records `scratchpad/gauntlet/ext/batch_v2/replay_<tag>.json` (which already
contain the engine's dealt positions and the FINAL permuted deck order) x the crawl timeline
`icebow/data/royaleapi/crawl2/plays_ext.csv` via `replay_drive.load_battle`. Using the batch records means an
episode needs ZERO extra engine resets for deal inference (the driver spends 2 resets per match on the deal probe).
Schema, one JSON object per line:
  tag, icebow_side, opp_side, seed (424242), level (11)
  decks["0"|"1"]      [{card_id, form, level}] x8, in the FINAL permuted order -> `deck_index` for env.act
  deck_names, deck_slugs  parallel labels
  our_bases           deck_index -> sim base key for the icebow side (policy card_id -> deck_index)
  ghost_plays         [[tick, deck_index, x, y], ...] the HUMAN opponent's recorded 20 Hz timeline
  own_plays           the icebow player's own recorded timeline (reference only; not driven in v0)
  expected            {result, crowns_ours, crowns_theirs} from RoyaleAPI
  l61_final_hash, l61_accepted, l61_driven, opening_hand_l61, opp_deck_str, last_play_tick
MEASURED: **202 entries** from 211 records. 9 skipped: 7 "deal not position-based" (the driver cannot place the
inferred hand on the dealt positions, so the ghost would desync at tick 0), 2 icebow-vs-icebow. Every entry has
icebow_side = 1 (RoyaleAPI "blue" = team_deck); side 0 is never icebow in the converted set.
Ghost plays per match: median 44.5, min 2, max 78.

## 2b. OWNERSHIP CORRECTION (13:20)
A second agent owns `icebow/data/ghost_pool/pool.jsonl` (schema in `scratchpad/gauntlet/L62/ghost_pool.md` Ã‚Â§0).
My first builder had written that path; per the coordinator's ruling it now writes ONLY
**`icebow/data/ghost_pool/pool_env_v0.jsonl`** (+ `pool_env_v0_build.json`) and `EngineMatchEnv.POOL_DEFAULT`
points there. `pool.jsonl` is never written by me again. All numbers below are on pool_env_v0.
(The Ã‚Â§2 pool described above -- 202 entries derived from the L61 batch -- was the first cut and is
superseded; only its deal-order table survives, as the prewarmed `deal_cache.json`.)

### pool_env_v0 (MEASURED, built 13:19 from the LIVE crawl -- 1228 battles.csv rows at that moment)
`scratchpad/gauntlet/L62/build_ghost_pool.py`, derived from `icebow/data/royaleapi/crawl2` through
`replay_drive.load_battle / deck_for_side / infer_deals`. **477 entries**, all `icebow_side = 1`.
Refused: play_not_positioned 504, no_native_evolution_form 225 (the engine's own `validate_deck` rejects a
`-ev1` card with no evolution form in this client build -- filtered here rather than crashing at reset),
icebow_deck_not_on_exactly_one_side 3, no_plays_rows 15, no_consistent_deal 3, ghost_has_no_positioned_play 1.
Ghost positioned plays per match: median 44, min 2, max 81; 21462 ghost commands in total.
Per line: tag, result, icebow_side/ghost_side, icebow_deck/ghost_deck (8 x {slug,name,sim_key,card_id,form,
cost,level} in battles.csv order), icebow_commands/ghost_commands ({tick,seconds,card,name,card_id,
deck_index,x,y,ability}), final_crowns [side0,side1], duration_ticks, plays, deal_candidates, battle meta.

## 3. EngineMatchEnv (`scratchpad/gauntlet/L62/engine_env.py`)
Interface identical to `SimMatchEnv`: `reset() -> obs`, `step((play, card_id, cell)) -> (obs, reward, done,
info)`, attributes `hand_vec / next_vec / elixir_vec / threat_vec / n_cards (10) / n_cells (432) /
threat_dim (52) / obs_shape (96,64,12) / deck_keys / anywhere_ids`.
ACTION CONVENTION verified against `icebow/src/clashrl/sim/env.py:3161` and `actions.py`: `Action =
(play 0/1, card_id, cell)` where **card_id is the DECK IDENTITY index into `deck_keys`** (evolutions are
separate identities: `knight` and `knight_evo`), NOT a hand position; `cell` is row-major `gy*gw + gx` over
the 18x24 grid, and `actions.deploy_clamp(anywhere, cell)` is applied before conversion, exactly as the sim
does. `play=0` is a deliberate no-op.

### 3.1 What each piece is wired to
- **Episode source**: one ghost-pool entry. The deck order the engine is given is the L61/replay_drive
  procedure verbatim: `infer_deals` -> probe the engine's dealt positions -> `sp_order_for` -> `deck_spec`
  -> `build_replay(template, deck0, deck1, seed=424242)`. The permuted order is CACHED per tag in
  `scratchpad/gauntlet/L62/deal_cache.json` (204 tags prewarmed for free from the L61 batch's `final_decks`
  by `prewarm_deal_cache.py`), so a cached tag costs 1 engine reset and an uncached one costs 2.
  MEASURED: `reset()` median 0.015-0.028 s; deal resolution median 0.00 s, i.e. below the timer even on a
  cache miss (24/40 of the bench matches were misses).
- **Ghost opponent**: `env.act(side=ghost_side, deck_index, x, y)` at the ghost's EXACT recorded tick --
  `_advance_to()` splits each decision chunk so the engine stops on every ghost tick (a `step` RPC costs the
  same for 1 tick as for 20, L61: 1.7 vs 2.0 ms, so this is nearly free). Elixir-slack retry is the
  driver's: a `not_enough_elixir` (1050) refusal is re-issued on the next tick for up to 40 ticks.
- **Our side**: fixed cadence, default every 10 ticks = 0.5 s. `card_id -> base key -> ghost-pool deck_index`
  (both `knight` and `knight_evo` map to the one deck slot the engine holds); `cell -> (x, y)` by the inverse
  mirror below. `env.cycle` is overwritten from the ENGINE's own `hand_deck_indices`/`cycle_deck_indices`
  every step, so the hand the policy sees is the engine's, not a cycle model (L61's BC build had 0.85% hand
  mismatch from modelling it; here it is 0 by construction).
- **Observation**: `build_bc_v2.frame_to_engine` + `SimMatchEnv._update_vectors()`, driven at the decision
  cadence (`agent_dt = 0.5 s`). 0 unmapped entities across every match run below.
- **Warm-up**: episodes start at tick 90 -- see Ã‚Â§3.3.

### 3.2 Cell <-> engine (x, y): the inverse, and its verified error
FORWARD (L51/L61 mirror, icebow_side = 1): `X,Y = 18000-x, 32000-y`; `nx = X/18000`, `ny = 1 - Y/32000`;
cell = nearest `actions.cell_center`.
INVERSE (`cell_to_engine`): `nx,ny = cell_center(gx,gy)`; `X = nx*18000`, `Y = (1-ny)*32000`;
`x,y = 18000-X, 32000-Y`.
MEASURED over **9368 real pro plays** (every icebow-side positioned play in the pool):
- the inverse is EXACT: cell -> (x,y) -> cell recovers the same cell **9368/9368**, max residual
  **0.000333 tiles** (integer rounding of engine units only).
- engine (x,y) -> cell -> engine (x,y) round-trip error = the placement grid's own quantisation:
  **mean 0.381 tiles, median 0.500, p90 0.501, max 0.834** (1 tile = 1000 engine units). This matches L61's
  independently measured snap distance (mean 0.383, max 0.833), so the two directions agree.

### 3.3 A real engine rule the replay driver never hit (MEASURED here)
The engine refuses EVERY deploy with `result_code 22` (`placement_valid: true`, `placement_reason: "valid"`)
until **tick 90 = 4.5 s**: the pre-battle countdown. Probed directly -- the same act at ticks 10,15,...,85 is
refused and at tick 90 is accepted. `replay_drive` never saw it because the earliest human play in the whole
crawl is tick 102 (median first play 199). `EngineMatchEnv` therefore starts each episode at tick 90
(`warmup_ticks=90`), which removes ~9 forced-illegal decisions per match and changes nothing else (the
episode's final state hash was identical before and after the change).

### 3.4 Reward -- EXACT formula, UNSHAPED
Engine state only. Nothing from the sim's shaped ledger (threat_response, wincon_exec, elixir_trade,
drills, gates, geometry, restraint/bank, nado, spell settlement) is ported. Per decision step:

    dmg_them = max(0, sum(their 3 tower HP)_prev - sum(their 3 tower HP)_now)     # a tower gone from the
    dmg_us   = max(0, sum(our  3 tower HP)_prev - sum(our  3 tower HP)_now)       #   list counts as HP 0
    r  =  w_hp    * (dmg_them - dmg_us) / princess_max_hp        # princess_max_hp = 3052 on this build
    r += w_crown  * (d(our crowns) - d(their crowns))            # crowns = enemy/own crown towers at 0 HP
    if done:  r += w_outcome * (+1 win | -1 loss | 0 draw)       # winner from engine `last_episode`
    defaults: w_hp = 1.0, w_crown = 1.0, w_outcome = 3.0

So one full princess tower of chip = +1.0, destroying it adds +1.0, and the match verdict is +/-3.0.
`info` carries tick, outcome, crowns, terminated/tail_capped, termination_reason, ghost counters, our
counters and the play that was issued. `EngineMatchEnv.reward_spec()` returns this formula as a string.

## 4. Determinism (MEASURED)
`run_engine_env.py det --index 0 --repeats 3`, greedy `bc_bias_native_s0.pt` on CPU, tag 000YLY0JCPGL:
**3/3 identical** -- final `state_hash` 08633a4e3495b521 in all three, tick 6144, crowns (1,2), episode
reward -4.5927. Nothing about the cache or the run order perturbs it. The same tag run with the policy on
**cuda** produced the same outcomes as CPU across the whole 20-match bench.
(Sim-side RNG is pinned per episode: `sim.rng.seed(crc32(tag:seed))`, `domain_rand` disabled.)

## 5. Throughput with a REAL policy in the loop (MEASURED)
Policy = `icebow/data/bc_pro/models/bc_bias_native_s0.pt` loaded as a native `PolicyNet`
(in_ch 12, n_cards 10, n_cells 432, threat_dim 52, grid 18x24, deck order asserted == `env.deck_keys`),
greedy card (masked to in-hand AND affordable), greedy cell (masked by `deployable_mask` for that card),
play/wait from the checkpoint's own gate head -- i.e. `train_sim_ppo.masked_logits` reproduced.
**A crawler (2 python procs) was running throughout; every number includes that contention.**

| configuration | matches | wall | s/match | matches/hour |
| --- | --- | --- | --- | --- |
| 1 slot, policy on CPU | 20 | 62.1 s | **3.107** | **1159** |
| 1 slot, policy on cuda | 20 | 62.5 s | 3.125 | 1152 |
| 2 slots on the ONE VM, CPU (concurrent, 20 each) | 40 | **77.9 s** | **1.95** aggregate | **1847** |

- Two slots = **1.59x** one slot; per-slot s/match 3.11 -> 3.73 (+20%), the same mild contention L61
  measured for the replay driver (1.65x, +20%).
- cuda is NOT faster: at batch size 1 the launch overhead exceeds the conv, and the policy's share of wall
  time went UP (28.0% CPU -> 36.5% cuda). Use CPU workers.
- Where the time goes (instrumented single match, 606 decisions / 6144 ticks -- the instrumentation itself
  inflates the total, so read the per-call numbers): `observe()` full **3.87 ms** x 608, `step()` **2.62 ms**
  x 664, obs render (`frame_to_engine` + `_update_vectors`) **1.52 ms** x 607, `act()` 1.61 ms, greedy policy
  ~7.3 ms per decision on CPU with 2 torch threads. The single biggest lever is the FULL observe: only the
  entity `kind` field (deploying flag) needs it, and `observe_compact` is ~1.6 ms (L61).

## 6. The v0 diagnostic: how fast does a ghost stop making sense?
40 distinct matches (the two concurrent 20-match runs), 1579 ghost commands, greedy BC policy.
`scratchpad/gauntlet/L62/analyze_bench.py` -> `analysis_bench.json`.

### 6.1 Rejections
- **mean 0.35 rejections per match**, median 0, max 2; **27/40 matches had ZERO**. Overall rate 1.8%.
- By match time: 0-60 s **0.0%** (0/221), 60-120 s **0.48%** (1/210), 120-180 s **2.25%** (6/267),
  180-240 s **11.7%** (7/60), 240 s+ 0.0% (0/34). Median first rejection at **163 s**.
- **BUT: every single rejection is the same code, `native_4`, and every one lands 0.55-4.0 s before the
  match's terminal tick** (ghost: 11-80 ticks before the end, n=14; our own side: 1-75 ticks before the end,
  n=9). The engine's terminal `last_episode` reports `commands_allowed: false, command_gate_code: 4` -- so
  result_code 4 is the END-OF-BATTLE COMMAND GATE, not a divergence. **Corrected count: ZERO ghost plays
  were refused for a game-state reason (card not in hand, illegal placement, elixir past the 40-tick slack)
  in 799 attempted commands over 40 matches.** The apparent "grows with match time" curve is entirely an
  artefact of matches ending; it is not desync.
- This is mechanically expected in hindsight and worth stating plainly: the ghost is a SEPARATE player. Their
  elixir bar, hand and cycle evolve independently of what we do, so nothing we do can put a card out of their
  hand. The only two channels by which the engine could refuse their play are (a) placement legality, which
  only WIDENS when a tower falls, and (b) elixir timing, which the 40-tick slack absorbs. **A recorded ghost
  does not desync. It goes STALE (answering a board that no longer exists) and it RUNS OUT -- neither of
  which the rejection counter can see.**

### 6.2 The number that actually measures staleness: UNDELIVERED commands
- **787 of 1579 ghost commands (50%) were never attempted at all** because the match ended first;
  per-match median **54%**. The greedy BC policy loses faster than the human it replaced (36/40 losses vs
  those humans' 26/40 wins on the same battles), so half of each ghost's plan never happens.
- This is the honest v0 limit: a ghost is a fixed script whose relevance decays; it does not resist,
  it does not adapt, and half of it is dead weight once the policy is worse than the player it replaced.

## 7. Sanity read, 40 matches (MEASURED)
- **terminated 40/40** (0 tail-capped at 7200 ticks). Termination reasons observed include
  `native_tiebreak_hp_drain`.
- Outcomes with the greedy BC checkpoint: **4 win / 36 loss / 0 draw**. Mean crowns **0.70 for / 2.50
  against**. (On the same 40 battles the human icebow players went 26 win / 14 loss -- the ghost pool is
  not an easy pool, and the BC policy is far below the players it replaces. This is a BASELINE, not a bug.)
- Match length: mean **168.6 s**, median 167.5 s, min 67.2 s, max 307.2 s (regulation 180 s + overtime).
- Our own plays: **15.9 accepted per match**; our reject rate 3.3%, all of it the end-of-battle gate (Ã‚Â§6.1).
- 0 unmapped entity names in any match (L61's 101/101 name map holds).
- Mean episode reward -6.17 under the formula in Ã‚Â§3.4 (dominated by -3 terminal + ~-2.5 crowns).

## 8. Files
- `scratchpad/gauntlet/L62/engine_env.py` -- EngineMatchEnv (the deliverable)
- `scratchpad/gauntlet/L62/build_ghost_pool.py` -> `icebow/data/ghost_pool/pool_env_v0.jsonl` + `_build.json`
- `scratchpad/gauntlet/L62/prewarm_deal_cache.py` -> `deal_cache.json` (204 tags)
- `scratchpad/gauntlet/L62/run_engine_env.py` -- map / smoke / det / bench harness + the greedy policy
- `scratchpad/gauntlet/L62/analyze_bench.py` -> `analysis_bench.json`
- results: `map_roundtrip.json`, `det_slot0.json`, `bench_slot0.json`, `bench_conc_a.json`,
  `bench_conc_b.json`, `bench_cuda.json`, `bench_ourrej.json`, `analysis_bench.json`, `_boot.log`
- nothing committed; nothing under `icebow/src/clashrl/` modified; `icebow/data/` written only under
  `ghost_pool/pool_env_v0*`.

## 9. Known limits of v0 (UNADDRESSED, not measured away)
1. **The ghost cannot react.** Ã‚Â§6.2: half its commands never fire. A v1 needs either a reactive scripted
   opponent, self-play, or a policy trained on the ghost's own recorded distribution.
2. **One replay seed (424242) for every episode.** The opening deal positions are therefore fixed and only
   the deck contents vary. Varying the seed is one line but invalidates the per-tag deal cache (the key must
   become (tag, seed)) and costs one extra reset per episode on a miss. UNTESTED.
3. **Card levels are a constant fill of 11.** The crawl records none. Inherited from L61.
4. **Evolution identity is modelled, not read.** The engine's hand does not expose whether a slot is
   currently the evolved form, so `hand_vec` uses the sim's evo-charge rule (`_play_slot`) while the ENGINE
   decides what actually deploys. `deck_index` addressing is unaffected; only the observation's
   base-vs-evo channel can disagree. Not quantified here.
5. **Spells in flight are still not rendered** (no obs channel exists on either side) -- inherited from L61.
6. **All 477 pool entries have icebow on side 1.** The mirror path (`icebow_side == 0`) is implemented but
   NEVER EXERCISED on this box.
7. **The reward is unshaped by design.** It is dense only in tower chip; long stretches score exactly 0.
   Whether PPO can learn from it at this cadence is UNTESTED -- that is the next experiment, not a claim.
8. **Decision cadence 0.5 s** (10 ticks) is a default, not a tuned choice; 606 decisions per 307 s match.
9. **Throughput context**: 1847 matches/h on two slots is ~1 match every 2 s. The current sim PPO worker
   pool is far faster than this; whether the fidelity buys back the sample cost is UNTESTED.


## 10. Shutdown
13:33 `worker stop --workers 2 --stop-vm` -> both services stopped, `vm_stopped: true`; no qemu process
left, `adb devices` empty. Nothing committed. Nothing under `icebow/src/clashrl/` modified.

STATUS: complete
