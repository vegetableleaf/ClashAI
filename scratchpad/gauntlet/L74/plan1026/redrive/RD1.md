# P2-RD1: HF IL_Replay re-driven through crforge F635c -> opponent rows (pass 1 of 3, 2026-10-28)

Labels: (a) measured here, (b) plausible, untested, (c) contradicted.

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
  AngryBarbarians row has `evolution_form_id: null` (a). Adding it is a production catalogue / vocabulary change (not
  done; needs an owner/foreman call; the id pattern suggests 13000043, (b) unverified).
- The pilot's rows were written before the unit_form column fix and were deleted; its grades / manifest stay.

## Full run (in progress at commit)
Pod 33308, `/workspace/redrive/full_bec5811a` (main PID 1576976, log `/workspace/redrive/full_bec5811a.log`),
1,010 shards x 250, 50 workers. Outputs: `rows/<part>_<lo>.parquet`, `grades/<sid>.jsonl` (per replay tier, reason,
cut), `shards/<sid>.json`, `manifest.json` (crforge build sha, tables, facade sha, code head, totals, per file sha256).
First 38 shards (9,500 replays, (a)): A 2,046 (21.5%) / B 6,195 / unusable 1,259; 64.5% of driven plays accepted;
0 shard errors; ~700 s wall per 250-replay shard at 50 workers (38 shards in ~12 min, ~13 replays/s), so the
1,010 shards take about 5 h (b, extrapolated). ~40-46k rows per shard -> ~42 M rows. Disk 93 GB free after the first
wave; parquet ~6 GB projected (b).

## Not done
- **Self-check (builder on our seat vs live decision inputs, >= 99% fields): not run.** Live `decision` events carry
  `public` = own_hand, own_elixir_raw, opponent_elixir_estimate, raw_bodies, and the model's BoardState at model_tick =
  raw + 24 (look-ahead extrapolation). Open choice: (1) the builder on a crforge re-drive of the live match (A2b inputs)
  compares engine + builder; (2) the builder on the live reader frames compares the builder alone, but only on the
  un-extrapolated fields (hand, raw elixir, raw bodies/towers), since the builder does not extrapolate.
