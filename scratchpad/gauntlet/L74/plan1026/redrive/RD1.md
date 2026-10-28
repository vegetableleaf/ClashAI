# P2-RD1: HF IL_Replay re-driven through crforge F635c -> opponent rows (pass 1 of 3, 2026-10-28)

Labels: (a) measured here, (b) plausible, untested, (c) contradicted.

## STATUS (keep current)
- Done: pass-1 code (redrive.py, run.sh, build_lib.sh); 1k pilot; full run 1,010 shards on pod 33308
  `/workspace/redrive/full_bec5811a` (lib `/workspace/redrive/rd_lib_bec5811a`, code copy `/workspace/redrive/cb`).
- In progress: re-drive of 12 shards whose files the 10-28 02:22 host reboot left empty (log
  `/workspace/redrive/full_bec5811a.log`); then `verify_out.py` (must print `"bad": {}`) and the manifest.
- Next: tower-troop re-drive into the same output (needs the D1-C facade, c1853e0 / 387f006):
  1. sync `pipeline/crforge_core.py`, `scratchpad/gauntlet/L74/crforge/facade/CfCore.java` and `redrive/` from HEAD into
     `/workspace/redrive/cb` (git archive HEAD ... | ssh ... tar -x --no-same-owner);
  2. `mkdir rd_lib_bec5811a_tt && cp -r rd_lib_bec5811a/lib rd_lib_bec5811a/BUILD.json rd_lib_bec5811a_tt/` (no facade/:
     run.sh compiles the new CfCore.java there);
  3. `setsid -f bash -c "bash cb/scratchpad/gauntlet/L74/plan1026/redrive/run.sh rd_lib_bec5811a_tt full_bec5811a
     --workers 40 --redo unusable:tower_troop: > full_bec5811a_tt.log 2>&1"` (resumable: shards_redo/ markers);
  4. `python verify_out.py full_bec5811a`, then record the new tiers / manifest (facade_sha256_by_file) here.
- Self-check (2) and (1): not started (see Not done).

## Re-run on a new crforge build (passes 2 and 3)
```bash
# on the fork's pod (F635c: 30408)
bash build_lib.sh /workspace/f635/crforge_fork NEWREF /workspace/f635/rd_lib_NEW     # clean worktree build + BUILD.json
# copy rd_lib_NEW to pod 33308:/workspace/redrive/, then on 33308 (code copy /workspace/redrive/cb, see run.sh):
setsid nohup bash /workspace/redrive/cb/scratchpad/gauntlet/L74/plan1026/redrive/run.sh \
    /workspace/redrive/rd_lib_NEW /workspace/redrive/full_NEW --chunk 250 --workers 50 > full_NEW.log 2>&1 &
python -I summarize.py /workspace/redrive/full_NEW                                  # tiers / reasons
```
`run.sh` compiles the facade (`CfCore.java`) against the new lib on first use. Resumable: a shard with
`OUT/shards/<sid>.json` is skipped. Tables: `CRFORGE_TABLES` (default 16.402.22; for a 16.635 pass set it).

## Pass 1 build (a)
- crforge `clashbot-up-e5462c82` = **bec5811a**, rebuilt in a clean worktree on 30408: core jar sha256 `63b78b8a...`
  (= CRFORGE_S0 F635c's). Tables 16.402.22: the directory hash is the same on 30408 and 33308 (`a2294d2b...`);
  `contentSha` 97869d43. Facade CfCore.java f31af91c (HEAD, compiled against this lib).
- The facade's `card_table_stamp()["crforge"]` is its hard-coded `CRFORGE_PIN` (ad8ef3a), not the loaded lib; the
  manifest drops it and carries `crforge_build` from BUILD.json instead.

## Method (decisions, each measured or labelled)
- Sides: team = side 0 (low y), HF `native_world_units` used as is (milli-tiles).
- **Given tick = HF tick (offset 0) (a).** 200 replays, offset 0 vs -20: not_enough_elixir cuts 22 vs 100, tier A 27 vs 8.
- **Deal (HF has none).** Production `deal_order` (untimed first fit) gave 21 not_in_hand cuts / 200; 20 of them came
  1-20 ticks after the side's previous play, before its 4th play ran (a). crforge keeps a given card in hand until it runs
  (given + 20 < t). `timed_deal` = the same first fit with that rule: not_in_hand 21 -> 2, tier A 27 -> 33 (a).
  After a side's 4th play has run, its hand is the same under every fitting deal (derivation; test_redrive.py checks the
  fitter). Rows up to then carry `hand_inferred = true` (22.6% of rows in one shard, (a)).
- **Ability presses.** HF candidates are not authoritative (`ability_source_authoritative` false). With 2 candidate
  buttons, the one crforge accepts is pressed if exactly one does: ability_identity_unavailable 28 -> 15 / 200, tier A
  33 -> 38 (a). Still ambiguous or none legal = a cut.
- **RNG.** No battle seed in HF: crforge seed 0. Matches with an RNG card (J7's list: Arrows, Princess, Hunter,
  Skeleton King, ...) use the engine's own draws; what that costs in tier A is unmeasured (b).
- **Validity.** A = every play and press accepted at its tick, the match ends, crowns == HF crowns. B = prefix before the
  first refusal, or the whole match when only the crowns differ / no end. Unusable = blocked before driving (tower troop,
  not 1v1, card missing), setup refused, or no accepted play. Rows of a B match stop before the cut (frames < cut; a
  wait row needs a later accepted play, so the last waits before the cut drop).
- **Rows** = `pipeline.dataset_gen.build(feature_version=5)` per shard (fv6 models read fv5 data), public observation,
  opponent elixir = public counter; each shard's npz -> one parquet (`tok` / `unit_form` as per-row lists; schema
  metadata `meta` = the builder's meta incl. its card_vocab (per shard), `shapes`); plus `tag`, `tier`, `hand_inferred`.
  `y_crowns` = the HF result for both tiers.

## Pilot, 1,000 replays (40 shards x 25, round-robin over parts, 40 workers) (a)
| tier | n | reasons |
|---|---|---|
| A | 197 | |
| B | 684 | record_identity AngryBarbarians:1 241; not_enough_elixir 144; game_over (crforge ended first) 114; crowns_mismatch 69; ability_identity_unavailable 66; no_hero 39; not_in_hand 10; ability_not_ready 1 |
| unusable | 119 | tower troop: dagger-duchess 55, royal-chef 50, cannoneer 14 |

- 63.2% of driven plays accepted; crowns match on 296 / 881 driven (incl. B prefixes that ran to the end).
- 162,297 rows (162 / replay), 23.5 MB parquet; 0 shard errors; wall 195 s; 6.7 s drive + 0.7 s rows per replay-worker.
- **Largest loss is not the engine:** 241 / 1,000 (24%) are cut when an evolved Elite Barbarians appears. The pro2
  recorder maps bodies to native ids from `research/ext/cr-native-sandbox/.../live_card_catalog.json`, whose
  AngryBarbarians row had `evolution_form_id: null` **on the pod's code copy** (a).
  - **Cause: a stale untracked file, not a missing id (a).** `research/ext` is not in git; the pod copy (rsync'd from
    `/workspace/d2/cb`, 152 cards, sha256 7b01d9ac...) predates the W9 10-20 extension. The laptop catalogue (153 cards,
    936cd3c4...) already has AngryBarbarians `evolution_form_id` 13000043, asserted by
    `pipeline/tests/test_vocab_extension.py::test_catalog_names_round_trip`. No catalogue edit was needed or made.
  - The id is confirmed three ways (a): crforge tables 16.402.22 and 16.635.3 both have `spells_evolved` (table id 13)
    row `AngryBarbarians_EV1` at index 43 -> 13,000,043 (the same rule gives Barbarians 13000008 and RageBarbarian
    13000035, the catalogue's values); the live reader census (`L74/identity/census.json`) saw card_id 13000043,
    max_hp 2143, 166 states in 3 live matches; and the laptop catalogue above.
  - Fix: the laptop catalogue was copied to the pod code copy (old one kept as `live_card_catalog.pod_stale_7b01d9ac.json`).
    Every shard of the first full run was affected (40 / 40 shards, 2,367 / 10,000 replays), so that run was stopped and
    restarted from scratch (below) rather than re-driven shard by shard.
- The pilot's rows were written before the unit_form column fix and were deleted; its grades / manifest stay.

## Full run (in progress at commit)
- Run 1 (stale catalogue, 50 workers) stopped by exact PID after ~45 shards; kept as
  `/workspace/redrive/full_bec5811a_stalecat_aborted` (do not use its rows). It also loaded the pod: each JPype JVM
  started ~66 threads (default GC / JIT pools sized to 108 cores); pod load average reached 461 with the other
  crforge workers (a). run.sh now sets `JAVA_TOOL_OPTIONS=-XX:+UseSerialGC -XX:ActiveProcessorCount=1`.
- Run 2: pod 33308, `/workspace/redrive/full_bec5811a` (log `/workspace/redrive/full_bec5811a.log`), synced
  catalogue, 1,010 shards x 250, 45 workers.

Run 1's first wave, kept for reference: Outputs: `rows/<part>_<lo>.parquet`, `grades/<sid>.jsonl` (per replay tier, reason,
cut), `shards/<sid>.json`, `manifest.json` (crforge build sha, tables, facade sha, code head, totals, per file sha256).
First 38 shards (9,500 replays, (a)): A 2,046 (21.5%) / B 6,195 / unusable 1,259; 64.5% of driven plays accepted;
0 shard errors; ~700 s wall per 250-replay shard at 50 workers (38 shards in ~12 min, ~13 replays/s), so the
1,010 shards take about 5 h (b, extrapolated). ~40-46k rows per shard -> ~42 M rows. Disk 93 GB free after the first
wave; parquet ~6 GB projected (b).

## Tower troops (13% unusable): the facade lacks them, crforge has them
- crforge (a, by code at bec5811a): `Standard1v1Battle.Towers(spawnGroup, kingLevel, level)` takes a spawn group, and
  `battle/replay/ReplayScenario.java` builds all four selections: `King_PrincessTowers`, `King_CannonTowers`,
  `King_KnifeTowers` (Dagger Duchess), `King_ChefTowers` (Royal Chef); the 16.402.22 tables carry their rows
  (characters, buildings, projectiles, support_cards, ...). How faithful their behaviour is: unmeasured (b).
- The facade (a): `CfCore.reset` hard-codes `PRINCESS_TOWERS` for both sides; `CrforgeCore.set_tower_troops` raises
  NotImplementedError; `card_table_stamp` / body_map have no tower-troop bodies.
- Work estimate (b): facade + `CrforgeCore.reset` pass a spawn group per side (HF `tower_card` -> group) ~0.5 day;
  body_map / spell_objects / native-catalogue identities for the troop bodies and their shots (Duchess daggers, Chef
  pancakes, Cannoneer shells), so the public observation and row builder encode them, plus tests ~1 day; a fidelity
  check (SME on live matches with those towers) is separate and needs such matches.

## Not done
- **Self-check, decided 10-28: (2) now (builder on the live reader frames, non-extrapolated fields), (1) after D1
  (crforge re-drive of the live matches). Neither has run yet.**
  - Live `decision.public` (pipeline/public_decision_audit.py) holds own_hand, own_elixir_raw, model_own_elixir,
    opponent_elixir_estimate, raw_bodies, model_bodies, model_towers, model_projectiles / effects at model_tick =
    raw_tick + 24. Reader `frame` events hold ents (side, x, y, native card id, hp, max_hp, kind, address), proj, fx,
    elixir, for every reader frame (~every 2 ticks).
  - Fields the extrapolation leaves alone (pipeline/extrapolate.py docstring, (a) by code) = what (2) compares:
    tower hp / alive, every body's identity (class, form, side) and HP, new or deploying bodies' positions, the
    opponent elixir estimate (the caller's public counter), own hand / next.
  - Excluded as extrapolated: moving bodies' positions (+ v x 24), the clock / phase (t_sec + 24), my elixir (+ regen),
    projectile / effect timers (v4 view), own_effects pushes, pending own plays and predicted Skeleton Barrel drops
    (decisions with non-zero `public_lookahead_counts` or a pending tap are left out).
  - Own hand has no source independent of the live hand reader (frame events do not log the hand), so (2) cannot
    test it; it is tested by (1).
  - Missing piece: no live-log -> builder recording adapter exists in the repo (searched L72 / L74 / pipeline). It must map
    frame `ents` to the recording's native entity rows and feed `recording_observers` / `from_engine` per decision tick.
