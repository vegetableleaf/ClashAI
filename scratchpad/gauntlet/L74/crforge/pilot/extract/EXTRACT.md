# A2b-1: live log -> crforge battle inputs (2026-10-27)

Labels: **(a)** measured here, **(b)** plausible but untested, **(c)** contradicted.

## What it does
`extract.py match|validate|batch`. One record per match, with the fields `ReplayBattle.build` / `ScenarioPlan` reads plus what J7 needs:
- **Decks:** both sides, crforge row names, in slot order (battle-log API).
- **Card levels:** level + 16 - maxLevel, from the API.
- **Slot flags:** API evolutionLevel, 1 = evo slot, 2 = hero slot.
- **Towers:** spawn group from the API support card. King and princess levels come from the live tick-0 max hp, looked up in crforge's own table (`towers.tsv`, from `LagProbe towers`) and cross-checked against the API level.
- **Words:** `gen_jobs.word`.
- **Our deal:** `gen_jobs.own_order`.
- **Opponent deal:** `null` + `opp_deal: unknown_live`. Also given:
  - `opp_fitting_deals`: how many of the 8! deals make every extracted opponent play legal under the 4-card cycle;
  - `opp_deal_fit`: one such deal.
  - Both are built from public plays only.
- **Plays (both sides):** from `fights.deployments` / `seen_casts`, reused unedited.
  - Fields: card, deck index, form, x/y in game units, tile, `run_ticks [lo, hi]`, source.
  - Phase-3 births make lo = hi.
  - Ability casts carry tick and name only; the object id is left to the driver.
- **Other fields:** game build, era, `rng_free` (the live_attr.py drawer rule), `own_cycle_fail`, `own_taps`, flags.

Engine facts that `deployments` takes from the RoyaleSim Engine are read from the crforge 16.402.22 tables instead, since there is no SIM on the laptop:
- area-effect life;
- collision radius;
- an `own_unit` shim (`ponytail:` note in the code).

The opponent's hand and elixir are never read; the live `opp_elixir_est` field is not opened.

## Tick convention (a)
- `LagProbe` on pod 33920 (crforge ad8ef3a): a play run on tick R makes its first object on tick R+1, for 13 of 13 cards tested. Zap makes no object.
- This is the parity convention `deployments` already uses (tick = creation - 1). So `run_ticks` are crforge run ticks.
- The given tick is run - 20 (`PLAY_DELAY_TICKS`).

## Validation on the replay-recorded match (a): `validate_1026.json`, `test_extract.py`
Ground truth: `replay_rec/convert.hand_plays`, built from both hands from tick 0. Its own `cycle_check` gives 0 / 0 bad frames.

| check | result |
|---|---|
| decks, both sides, vs the recording's `deck_card_ids` | 2/2 exact |
| slot flags vs `deck_form_flags` | 2/2 exact |
| our deal vs the recording's tick-0 hand + cycle | exact |
| per-card levels vs the recording's body `level` | 13/13 cards seen as bodies agree, 0 disagree |
| towers | L16/L16 both sides; live tick-0 hp = crforge table |
| true opponent deal legal under the extracted opponent plays | yes (one of 6,144 fitting deals) |
| plays matched (same side + deck index, nearest tick ≤ 60) | **72/72** (us 37/37, opponent 35/35); **0 extra**, 0 unplaced |
| run tick inside the truth window | **71/72** (us 36/37, opponent 35/35) |
| run tick exact (phase-3 stamp, lo = hi) | 61/72 |
| own command point vs our confirmed tap | **37/37 exact** (0 mt) |
| opponent tile vs the replay's first-seen body / cast tile | 35/35, max error 7 mt |

Notes:
- **Truth window.** The replay shows a hand change on the play's first-object tick: 59 of 61 phase-3-stamped plays sit 1-2 ticks before the 2-tick-sampled change.
  - So the true run tick is in [previous frame, H-1].
  - The 1 miss is our Knight at 3044: stamped 3044, but the hand had already emptied on the replay frame 3044.
- **Opponent tile check is weak (b).** Both sides of it are body-based reads of the same match (live vs replay). It measures reader consistency, not the opponent's true tap point, which no source gives.
- **Our tiles vs the replay are 30/37.** The 7 misses are the truth's fault:
  - Skeletons: formation centroid vs the tap;
  - 6 Logs (c): `convert.py`'s ROLLING rule places a Log at its first-seen position, which on this reader is the throw from the king tower, 2.3-2.6 tiles behind the tap. The extracted Log point is the projectile target, which equals the tap.
- A first `own_unit` shim ("any first-seen hp") made the Hero IW ice cube into a play: 1 extra. The current shim gives 0.
- **One match only.** The rates are n = 72 plays (b) for other matches.

## Batch (a): post-10-19-06:00 Ranked main-account matches
`extract.py batch`, written to pod 33920 `/workspace/pilot/inputs/`:
- `inputs_post1019.jsonl`: 227 matches, sha256 2c7e1605…;
- `inputs_rngfree.jsonl`: 138 matches, sha256 ca766522…;
- `batch_stats.json`.

| | all | RNG-free |
|---|---:|---:|
| Ranked battles in the battle log after the cut | 227 | |
| extracted (0 skips) | 227 | **138** |
| no flags | | 109 |
| `opp_no_fitting_deal` (an opponent play missed or invented) | 36 | 25 |
| `own_cycle_fail` (an own play out of cycle order) | 6 | 4 |
| plays / exact-tick plays | 17,246 / 14,776 | 10,822 / 9,303 |

Other facts:
- Crowns live vs API: 0 mismatches.
- Builds: all 160402012. No post-maintenance client is in the set; the newest battle is 10-27 08:19Z.
- Phase-3 births: 226/227.
- Towers: 2 matches at L15. Tower troops: Duchess 15, Chef 6, Cannoneer 3.
- 32 inferred opponent Zaps (`unseen_zaps`) have no Zap in the deck. They go to `unplaced`, not to `plays`.
- Drawer counts (Arrows 54, Princess 28, Hunter 9, Skeleton King 4) equal CRFORGE_S0 2c.

## Concerns
1. **Only 138 RNG-free matches, against J7's ≥ 300.**
   - The battle log's 227 Ranked entries span 10-26 12:09Z to 10-27 08:19Z. CRFORGE_S0's "223 pairs, 10-08 to 10-27" is the same set; the 10-08 date is a non-Ranked entry (c).
   - The ~1,200 live log files from 10-19 to 10-26 (not all of them full Ranked matches) have no API entry, so they have no exact levels, opponent deck or tag.
   - Proposed split, A2b-1b: extract those with levels from body max hp and the opponent deck from seen cards, flagging decks with < 8 cards seen. Alternatively wait for the poller to collect more.
2. **36/227 matches have no opponent deal that fits.** Each such match has at least one wrong opponent play. Driver policy is owed: skip them, or relax to misfit ≤ 1.
3. **`own_unit` shim:** Hero Goblins bodies may be dropped (4 opponent decks). Not measured.
4. **Not checked here:** whether hand-slot order matters to any mechanic (CRFORGE_S0 2c, b).
