# L64 engine_play harness record (2026-09-06)

Harness: `pipeline/engine_play.py` (CLI `python -m pipeline.engine_play icebow --ckpt ... --port 37031 --matches 2 --seed 0 --out scratchpad/gauntlet/L64/engine_play/`).
Offline test: `pipeline/tests/test_engine_play.py` (3 tests, `python -m unittest pipeline.tests.test_engine_play` -> OK, 0.04 s).
Per-decision logs: `scratchpad/gauntlet/L64/engine_play/<tag>_m<i>.jsonl`; run summary `summary_icebow_s0.json`; stdout of run 2 in `smoke_run2.txt`.
Probe scripts left in the out dir: `_probe_m1.py` (no-play tower-HP trace), `_probe_code.py` (result-code probe).

## Design
- World/opponent = L62 `EngineMatchEnv` (reset, deal resolution + cache, ghost driving `_advance_to`/`_fire_ghosts_at`, termination). Subclass `RawEngineEnv` overrides `_render` to return the RAW `observe()` dict (old FakeEngine/SimMatchEnv obs path never runs) and `_resolve_decks` to keep `final_decks` (engine deck order).
- Obs: `compact_raw(state)` strips the raw state to what training PLAY rows saw (`dataset._as_compact`: entities without `kind`, no effects/projectiles, no history) -> `from_engine` raw branch -> `to_tokens(bs, 64)` + `dataset._past` over our ACCEPTED plays.
- Parity check (per match, first decision tick): `from_engine(compact_raw(state)) == from_engine(list_frame(state))` where `list_frame` is the recorder's snapshot format. (a) measured True in both matches, so the raw and list branches agree on a live tick.
- Decision rule `decide()`: every `--decide-every` 10 ticks (0.5 s); play iff sigmoid(gate) > `--tau` 0.5 (or `--gate sample`); card = argmax hand-masked card logits; cell = argmax of `model.cell_logits` for that card; cell centre -> `board_to_engine` (exact inverse of `obs_contract._engine_xy`) -> `eng.act(side, deck_index, x, y)`. Deck slot -> engine deck_index via `deck.slot_of(vocab.engine_key(final_decks name))` (all 8 slots asserted).
- Ports: all four slots were UP (37031/37032 via adb forward PID 59132, 38031/38032 direct PID 54304); only TIME_WAIT connections. No service started. Used 37031 as instructed.
- Model on CPU by default (`--device`); the GPU is the trainer's.

## Raw state at a decision tick (shape, not a dump)
- top keys: applied_replay_tick, coherent, effect_count, effects, effects_classified, elapsed_seconds, entities, entity_count, episode, kind, players, projectile_count, projectiles, rng_*, schema_version, state_hash*, tick, tick_after, unclassified_effect_count
- episode keys: command_gate_code, commands_allowed, crown_towers, crowns, crowns_by_side, native_phase, outcome, result_source, terminal_tick, terminated, termination_reason, tower_snapshot_complete, truncated, winner
- one player: `{side:1, player_index:1, elixir:7, elixir_raw:76020, elixir_exact:7.602, refill_timer:0, next_deck_index:4, deck_to_hand:[...8], hand_deck_indices:[6,3,7,1], cycle_deck_indices:[4,2,5,0], hand:[{hand_index:0, deck_index:6, card_id:26000023, level:11, form_flags:0, has_evolution:False, has_hero:False, name:'IceWizard'}, ...]}`
- one entity (a crown tower shows up here too, card_id -1, dropped by from_engine): `{id, generation_key, creation_ordinal, category, kind:12, side:0, x:9000, y:3000, x2, y2, card_id:-1, level:11, hp:4824, max_hp:4824, behavior_state, ability_*, pending_damage, target, ..., entity_id:5000000}`; real units additionally carry `name` (from CARD_NAMES) plus native_card_id / base_card_id / form fields from `observed_card`.
- one crown tower: `{id, side:0, type:'king', lane:None, x:9000, y:3000, hp:4824, max_hp:4824, destroyed:False}`

## Fields from_engine needed that the raw state lacks
- `engine_deck` (for `next_deck_index` -> name): not in the state; built from the env's deal-resolved `final_decks[side]` as `Name@form` (form != base), the `replay_drive.py:317` convention. Verified all 8 names map to the 8 deck slots.
- Nothing else: hand names come from `players[].hand[].name`, towers from `episode.crown_towers`, elixir from `elixir_exact`. `unmapped` stayed empty in both matches.

## Smoke: 2 matches, seed 0, tau 0.5, threshold gate, port 37031 (all (a) measured; run twice, byte-identical outcomes/ticks/play counts = deterministic)
- m0 `099P9CL8L2QJ` side 1: WIN 2-1, 240.9 s (4818 ticks, native_logic_clock_stopped), 473 decisions, 38 plays / 38 accepted / 0 refused, 9.46 plays/min, ghosts 22/22 accepted, p_gate mean 0.2985 p90 0.4909, wall 24.4 s (run 1, deal-cache miss) / 24.3 s (run 2, hit).
- m1 `02GY9R09LU8J` side 1: LOSS 0-3, 78.1 s (1562 ticks), 148 decisions, 9 plays / 7 accepted / 2 refused (both `not_enough_elixir_13`), 6.91 plays/min (5.38 accepted/min), ghosts 5/16 delivered before the end, 0 refused, p_gate mean 0.2887 p90 0.4765, wall 7.5 s.
- SUMMARY: 1W 0D 1L, crowns 2 for / 4 against, 47 plays / 45 accepted / 2 refused, 8.84 plays/min, ghost 27 ok / 0 refused, wall 15.9 s per match (~38 s total incl. model + env init).
- Reference: pool icebow-side human plays/min mean over 477 entries = 10.93; the harness's 8.84 is the same order (2 matches, not a measurement of the policy).
- Card mix m0: ice_wizard 7, skeletons 7, tesla 6, knight 6, x_bow 5, log 4, rocket 2, tornado 1. First play at 16.0 s (ice wizard behind king, cell 2251 = board (0.54, 0.98)); x-bow at 20.0 s on cell 1409 = board (0.15, 0.62) = 4 tiles from the river, offensive lane.

## Traps / findings
1. `result_code 13` is "not enough elixir" in this engine build, NOT the documented 1050 (docs/API.md 2 lists 1050). (a) measured with `_probe_code.py`: elixir 1.602, 3-cost cards refused with 13 (placement_valid True), 1-cost accepted; both harness refusals were at 2.79 / 2.97 elixir for 3-cost cards, accepted 0.5 s later at 3.15. Consequence for L62 `engine_env.py`: its ghost elixir-slack retry keys on code 1050 only, so a ghost short of elixir gets counted as refused (`native_13`) immediately instead of retried up to 40 ticks -- did not fire here (0 ghost refusals), but it will understate ghost fidelity in the 500-match run unless 13 is added there. Not changed (L62 file is not mine).
2. m1's 0-3 at 78 s is the GHOST, not a harness bug: (a) `_probe_m1.py` replays the same tag with NO plays from us and the towers go 3052/3052/4824 -> all 0 between t=50 s and t=70 s (terminal tick 1404, crowns [3,0]); ghost deck golem / night-witch / musketeer-evo / mega-minion-hero / pekka, first 5 plays undefended. The real match was an icebow win 1-0 at 176 s. With our 7 accepted plays the loss came 8 s later (tick 1562). Expect some pool entries to be un-winnable for a non-defending policy; grade on agreement, not this.
3. Trainer checkpoint rewrite: `torch.load` is wrapped in a 5x retry with 3 s sleep (it never tripped here). The trainer was mid-run (s1_icebow_s0.pt epoch 14, val cell_tile_top1 0.1812 at load time) -- the number in the run header is whatever epoch the file held.
4. `EngineMatchEnv.close()` writes `scratchpad/gauntlet/L62/deal_cache.json` (already untracked) with the new tags -- benign, same as the L62 trainers did. Warmup: reset already advances to tick 90 (the deploy gate), first decision is at t=4.5 s.
5. Windows arg passing: avoided multi-line `python -c`; probes are files.

STATUS: complete
