# L64 hogeq ghost pool -- making the engine ghost-pool machinery deck-agnostic

Started 2026-09-06. Subagent of the gauntlet loop. Rules: no git add/commit, nothing under */data/ touched
except the new hogeq pool + temp files, no process killed, no config of running runs changed.

## 0. Findings from reading (before any edit)

- (a) measured: `scratchpad/gauntlet/L62/build_ghost_pool.py` (211 lines) is icebow-specific in exactly 3
  places: `CRAWL = icebow/data/royaleapi/crawl2`, `OUT_DIR = icebow/data/ghost_pool`, and the
  `ICEBOW_BASES` frozenset used for the "our deck on exactly one side" test. `RD.deck_for_side`,
  `infer_deals`, the catalog and the evolution-form filter are all deck-agnostic.
- (a) measured: `research/sandbox_tools/replay_drive.py:41 set_crawl(deck_or_path)` already exists (L63e)
  and resolves a deck name to `<deck>/data/royaleapi/crawl2`; the builder does NOT need it because it
  reads the csv files itself, but the same path convention is used.
- (a) measured: hogeq corpus exists at `hogeq/data/royaleapi/crawl2/{battles.csv (268 KB), plays_ext.csv
  (3.3 MB)}` (Sep 2 12:23), same columns as icebow's crawl2 (`replay_tag, deck, ..., team_deck,
  opponent_deck, ...`). The hogeq deck string in the corpus:
  `earthquake,firecracker-ev1,hog-rider,ice-spirit,mighty-miner,skeletons,tesla-ev1,the-log`.
- (a) measured: the hogeq deck (pipeline/decks/hogeq.yaml, source hogeq/config/cards.yaml:36-47):
  hog_rider, firecracker_evo, mighty_miner, tesla_evo, the_log, earthquake, skeletons, ice_spirit.
  key_base() form: {hog_rider, firecracker, mighty_miner, tesla, the_log, earthquake, skeletons, ice_spirit}.
- (a) measured: `engine_env.py` reads the entry keys `icebow_side`, `icebow_deck`, `icebow_commands`,
  `ghost_side`, `ghost_deck`, `ghost_commands` at 3 places (`_side_plays`, `_resolve_decks`, `reset`).
  `_deck_spec` is generic (card_id, form, level). The sim-side objects from `V2.init_worker()` (icebow
  config) are used only by the OLD obs path and `_sync_cycle`; `pipeline.engine_play` overrides
  `_render` and never calls `env.step`, so for engine_play the hogeq deck never touches the icebow
  `deck_keys` / `slot_of_base`. `_sync_cycle` returns False for a non-icebow deck (KeyError branch) and
  `reset` then sets `sim.cycle = range(8)` -- harmless for engine_play, but it means the OLD
  `EngineMatchEnv.step` path (used by the L62 PPO trainer) is still icebow-only. Left as is; noted.
- (a) measured: `pipeline/engine_play.py` resolves `load_deck('hogeq')` through
  `pipeline/decks/hogeq.yaml` (data_dir hogeq/data); `deck_index_of_slot` is built from
  `deck.slot_of(vocab.engine_key(name))` over the ENGINE's dealt deck -> deck-agnostic as long as every
  engine name of the 8 hogeq cards maps to a vocab key matching the yaml's base keys (checked in the smoke).
- (a) measured: no unit test exists for build_ghost_pool.py (grep pipeline/tests, scratchpad/gauntlet/L62).
- (a) measured: ports 37031/37032 have ESTABLISHED clients (busy 100-match runs); 38031/38032 LISTENING
  with no client -> smokes use 38031.

## DECISION (loud): JSON key names are KEPT as `icebow_side` / `icebow_deck` / `icebow_commands`

They now mean "OUR deck's side" for whichever deck the pool was built for. Rationale: the icebow pool
must stay byte-identical (it is consumed by running experiments), and engine_env / engine_play read
those names. The builder writes a `deck` field ONLY into the `_build.json` meta, never into the jsonl
rows, so the icebow rows do not change. engine_env.py gets a small alias so a future pool may also
spell them `our_side` / `our_deck` / `our_commands`.

## 1. Builder parameterised (scratchpad/gauntlet/L62/build_ghost_pool.py, 211 -> 237 lines)

Changes: `--deck {icebow,hogeq}` (default icebow), `--out PATH` override; `DECK_BASES` = {icebow: ICEBOW_BASES,
hogeq: HOGEQ_BASES}; `paths_for(deck, out)` -> (`<deck>/data/royaleapi/crawl2`, `<deck>/data/ghost_pool/
pool_env_v0.jsonl`, `..._build.json`); `main(deck, out)`. Meta json gains `deck` and `our_side_keys`; the
jsonl rows are unchanged in shape and key names. File has CRLF line endings (trap: a python
str.replace with "\n" does not match; use the Edit tool or splitlines).

Verification (a) measured, commands in this dir (`build_orig_icebow.out`, `build_new_icebow.out`):
- The pre-edit builder (`git show HEAD:...` -> `build_ghost_pool_ORIG.py`, with ROOT and OUT_DIR patched to
  `tmp_orig/`) and the new builder `--deck icebow --out tmp_new/pool_env_v0.jsonl` were run on the SAME
  corpus snapshot: `cmp tmp_orig/pool_env_v0.jsonl tmp_new/pool_env_v0.jsonl` -> IDENTICAL (490 rows each).
- NEW vs the on-disk `icebow/data/ghost_pool/pool_env_v0.jsonl` (477 rows, built 2026-09-05 13:19 from
  1,228 battles) DIFFERS at line 349 -- because the icebow crawl kept running: battles.csv is now 1,254
  lines (1,253 rows). All 477 on-disk rows appear VERBATIM in the new 490-row file; the 13 extra rows are 13
  new tags. So the difference is corpus growth, not the code change.
- DECISION: the on-disk icebow pool was NOT overwritten (running 100-match runs on 37031/37032 read it; a
  477 -> 490 swap would change their sampling order). The 490-row rebuild is at
  `scratchpad/gauntlet/L64/hogeq_pool/tmp_new/pool_env_v0.jsonl` if the lead wants to promote it.

## 2. hogeq pool built: hogeq/data/ghost_pool/pool_env_v0.jsonl (a) measured

`PYTHONHASHSEED=0 python scratchpad/gauntlet/L62/build_ghost_pool.py --deck hogeq` (2.1 s; `build_hogeq.out`,
`pool_stats.txt`):
- corpus: 598 battle rows, 595 distinct tags with plays; the hogeq deck was on exactly one side in ALL of
  them (0 refused for the deck test; the crawl was already deck-filtered); refused: play_not_positioned 244,
  no_native_evolution_form 107 (opponent evos this client build lacks), no_plays_rows 3, no_consistent_deal 3.
- n = 241 entries; our side is engine side 1 (blue) in all 241 (same as icebow's 477/477).
- result from our side: 138 win / 103 loss / 0 draw (57.3% win; icebow pool 335/142 = 70.2%).
- positioned plays per side: ours mean 48.1 (median 47), ghost mean 37.6 (median 35, min 1, max 81);
  955 ability commands (mighty_miner) in total. icebow pool: ours 47.7 / ghost 42.8.
- match length (last play): mean 228.6 s, median 232.7 s, min 28.8 s, max 298.9 s (icebow: mean 253.9 s).
- our-deck engine names: Earthquake, Firecracker@evolution, HogRider, IceSpirits, MightyMiner, Skeletons,
  Tesla@evolution, Log; all 8 map through `vocab.engine_key` -> `Deck.slot_of` onto the 8 hogeq.yaml slots
  (checked offline: slots 5,1,0,7,2,6,3,4). sim_key reference field resolved for 1928/1928 our-deck items.

## 3. engine_env.py (505 -> 513 lines) and engine_play.py (364 -> 367 lines)

- engine_env: new `ours(entry, what)` accessor (accepts `our_side|deck|commands`, falls back to
  `icebow_*`); used at the 3 read sites (`_side_plays`, `_resolve_decks`, `reset`). Behaviour for the
  existing pool is unchanged (same keys read). `_deck_spec` / level (11) are already deck-agnostic.
  NOT changed: `_sync_cycle` + `step()` still index the sim-side icebow `slot_of_base` / `deck_keys`, so the
  OLD `EngineMatchEnv.step` path (L62 PPO trainer) is icebow-only; engine_play never uses it.
- engine_play: `--pool` now defaults to `<deck.data_dir>/ghost_pool/pool_env_v0.jsonl` (for icebow that is
  the very same file as `engine_env.POOL_DEFAULT`; falls back to POOL_DEFAULT if missing).

## 4. PORT TRAP (c) contradicts the brief: 38031 is NOT a fourth engine instance

(a) measured: `scratchpad/gauntlet/ext/cr_sandbox_internals.md` §8 and `native_core/worker.py:69-70,210-212`:
port 37031+slot is the adb-forward transport and 38031+slot the direct transport of the SAME guest
service (single-threaded accept loop, one in-flight request per worker). netstat: 37031/37032 are owned by
PID 59132 (adb) and 38031/38032 by PID 54304 (the qemu VM) -- two doors, two slots. The brief's
"engine instances also listen on 38031 and 38032" is therefore wrong: with thr_ck2 (s1_icebow_s2 x100) on
37031 and thr_ck1 (s1_icebow_s1 x100) on 37032, BOTH slots were busy.
My first icebow recheck on 38031 (03:32 local) hung on `eng.reset` for the 120 s client timeout
(`icebow_recheck.txt` first attempt, traceback kept as `icebow_recheck_attempt1_38031.txt`). (b) untested
but consistent with §8: the direct server serves one persistent connection at a time, so the queued
connection never got its reset read and the running thr_ck2 match was not touched; thr_ck2 kept producing
matches at its usual ~18 s cadence through 03:35. No process was killed.
Plan: wait for thr_ck1 (99/100 at 03:35) to finish, then use 38032 (slot 2 direct) for both smokes.

## 5. icebow recheck on 38032 (slot 2 direct) -- (a) measured, IDENTICAL

`PYTHONHASHSEED=0 python -m pipeline.engine_play icebow --ckpt icebow/data/pipeline/s1_icebow_s0.pt --port 38032
--matches 2 --seed 0 --out .../icebow_recheck/` (`icebow_recheck.txt`), run in the ~90 s window between thr_ck1
finishing and the lead's rnd13_s0 taking slot 2:
- 099P9CL8L2QJ WIN 2-1 at 240.9 s, 473 decisions, 38 plays / 38 accepted, ghosts 22/22, p_gate mean 0.2985,
  parity true, unmapped [];  02GY9R09LU8J LOSS 0-3 at 78.1 s, 9 plays / 7 accepted (not_enough_elixir_13 x2),
  ghosts 5/16, p_gate mean 0.2887, parity true.
- Field-by-field against `L64/engine_play_none/smoke_thr_recheck.txt`: both result lines IDENTICAL on all 26
  fields other than wall_s / log (21.5 s and 7.4 s wall here). Same result on the direct transport as the
  reference got on the adb transport (37031) -> the transport does not change the match.

## 6. Offline tests (a) measured
- `python -m unittest pipeline.tests.test_engine_play`: 3 tests OK (`unittest_engine_play.txt`).
- `pipeline.tests.test_obs_contract` + `test_dataset`: 24 tests OK (`unittest_others.txt`).
- No test exists for build_ghost_pool.py; none added. Offline consistency check (`offline_alias_check.txt`):
  hogeq pool loads 241 rows through `engine_env.load_pool`; `ours()` prefers `our_*` over `icebow_*`; the
  default icebow pool still loads 477; `HOGEQ_BASES` / `ICEBOW_BASES` equal the base keys of
  `pipeline/decks/{hogeq,icebow}.yaml`.

## 7. hogeq smoke: WAITING FOR A SLOT
The first hogeq attempt on 38032 (03:37) timed out at reset: the lead's rnd13_s0 (PID 75768, s1_icebow_s0
--policy random x100) took 37032 at 03:37:16, ~60 s after thr_ck1 ended; thr_ck2 (PID 5588, x100, started
03:27) holds 37031. `wait_and_smoke.sh` polls netstat every 5 s and runs the model smoke then the
`--gate none` control on the first freed slot's direct port (log: `wait_and_smoke.log`).

## 8. hogeq smoke on the engine (a) measured -- slot 2 direct port 38032, seed 0, s1_hogeq_s0.pt (epoch 20, val tile 0.213)

Slot 2 freed at 04:00:20 (rnd13_s0 done); `wait_and_smoke.sh` ran both smokes 04:00:20-04:01:25. Files:
`smoke_hogeq.txt` + `smoke/*.jsonl` (model, gate threshold tau 0.5), `smoke_hogeq_none.txt` + `smoke_none/`.
NO harness fix was needed: card vocab, deck slots, `to_tokens`, parity all worked first try for hogeq.

| match | tag | outcome | s | plays / accepted | refuse | ghosts ok/total | parity | unmapped | p_gate mean/p90 | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| m0 model | 09J9JVLQ8YRR | LOSS 1-2 | 201.0 | 29 / 26 | native_4 x3 | 25 / 45 | true | [] | 0.337 / 0.493 | 18.2 s |
| m1 model | 020YPYJJ9LLR | WIN 3-1 | 299.2 | 70 / 63 | native_4 x7 | 61 / 61 | true | [] | 0.350 / 0.506 | 26.8 s |
| m0 none | 09J9JVLQ8YRR | LOSS 0-3 | 87.6 | 0 / 0 | - | 8 / 45 | true | [] | 0.437 / 0.702 | 7.0 s |
| m1 none | 020YPYJJ9LLR | LOSS 0-3 | 70.4 | 0 / 0 | ghost native_4 x1 | 8 / 61 | true | [] | 0.592 / 0.728 | 6.0 s |

- Summary model: 1W-1L, 4-3 crowns, 99 plays / 89 accepted / 10 refused, 11.88 plays/min, ghosts 86 ok / 0
  refused; none-control: 0W-2L, 0-6, ghosts 16 ok / 1 refused. deal_cache_hit false on the model run (first
  time these tags were dealt; the cache in `L62/deal_cache.json` then served the none run: hit true).
- Cards played (accepted), m1: hog_rider 11, skeletons 11, the_log 10, ice_spirit 10, earthquake 9,
  firecracker_evo 6, mighty_miner 5, tesla_evo 1; m0: ice_spirit 4, skeletons 5, firecracker_evo 5,
  mighty_miner 4, hog_rider 4, tesla_evo 3, the_log 1. All 8 deck slots were exercised through
  `deck_index_of_slot` -> engine `act` (a). Board y of accepted spells: the_log 0.55, earthquake 0.34.
- The engine name IceSpirits -> vocab ice_spirit and MightyMiner -> mighty_miner worked (a); mighty_miner's
  ability is NOT exposed by engine_play (it plays hand cards only) -- the 955 ability commands in the pool are
  ghost/our recorded abilities that `_side_plays` filters out, same as for icebow (no ability plays there).
- `native_4` refusals (a, `native4_probe.txt`): all 10 own refusals lie in the last 3 s of the match
  (t = 296.0-299.0 of a 299.2 s match; 199.5-200.5 of a 201.0 s match), elixir 9.2-10.0, hand cards in
  hand. NOT hogeq-specific: the icebow x100 runs show native_4 in 78/100 (thr_ck1) and 84/100 (rnd13_s0)
  matches. (b) untested: result_code 4 = the engine's end-of-battle deploy freeze (the "end-of-battle gate"
  of L62c); it is unnamed in `RESULT_CODE_NAMES` in both engine_env.py and engine_play.py -- worth adding as
  "battle_over" once the lead confirms the code's meaning against libg.
- Sanity vs the pool (a): 09J9JVLQ8YRR: recorded win crowns(side0,side1)=[0, 1] ghost plays 45 020YPYJJ9LLR: recorded loss crowns(side0,side1)=[1, 0] ghost plays 61. The model run reproduced neither (LOSS 1-2 / WIN 3-1 vs recorded), the
  none-control lost both 0-3 within 88 s -- same shape as icebow's none control (0-100 over 100 entries, §5cs.65).

## 9. What did NOT work / traps
- (c) The brief's "engine instances also listen on 38031 and 38032": 3803x is the direct transport to the same
  slot as 3703x (§4). Two of my smoke attempts timed out at `eng.reset` (120 s) because the slot was busy;
  no running match was disturbed as far as the running logs show (thr_ck2 and rnd13_s0 kept their cadence).
- Byte-identity of the icebow pool against the ON-DISK file is impossible while the crawler runs (§1);
  identity was proven ORIG-builder vs NEW-builder on one snapshot, and the on-disk file was left alone.
- CRLF line endings in build_ghost_pool.py (python str.replace with "\n" silently fails to match).
- `_sync_cycle` / `EngineMatchEnv.step` remain icebow-only (sim-side `slot_of_base`, `deck_keys`); only the
  engine_play path is deck-agnostic. The OLD PPO trainer path would need `V2.init_worker` parameterised by
  deck config before hogeq could train there.

## 10. Files changed (no git add; lead stages)
- scratchpad/gauntlet/L62/build_ghost_pool.py  211 -> 237 lines (--deck/--out, DECK_BASES, paths_for, meta fields)
- scratchpad/gauntlet/L62/engine_env.py         505 -> 513 lines (ours() accessor, 3 read sites, POOL_DEFAULT comment)
- pipeline/engine_play.py                      364 -> 367 lines (per-deck default pool path)
- NEW hogeq/data/ghost_pool/pool_env_v0.jsonl (241 rows, 3.86 MB) + pool_env_v0_build.json
- scratchpad/gauntlet/L62/deal_cache.json gained 2 hogeq tags (written by env.close(); the concurrent icebow
  runs also rewrite it -- last writer wins, it is only a cache)
- everything else under scratchpad/gauntlet/L64/hogeq_pool/ (probe outputs, temp pools, this md)

STATUS: complete
