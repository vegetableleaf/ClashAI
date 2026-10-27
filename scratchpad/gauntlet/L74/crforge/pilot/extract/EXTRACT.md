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

# A2b-1b: matches with no battle-log entry (2026-10-27)
`extract.py batch_noapi` (`match(api=False)` -> `derive_sides`). Every API-backed record also carries `derived` (the same derivation from the log alone); `check_levels` scores it against the API (`check_levels.json`).

## Rules
- **Levels (per-card mapping).**
  - Each body's first-seen max hp is looked up in crforge's unit table for that card row and form: `unit_hp.tsv`, from `LagProbe unithp` on the pod. It covers 276 rows × levels 1-16, and every body the play makes, children included.
  - Only a hit at exactly one level counts as a vote. The card takes the level most of its bodies vote for.
  - A card with no body (spells) takes its side's modal body level (`level_src: mode`).
  - Our own side is read the same way.
- **Our deck:** exact, from our own `own_hand` (deck_index, name, form): slot order and forms.
- **Opponent deck:** the cards its extracted plays show, in first-seen order; inferred Zaps do not count.
  - An unseen slot is `None`, flagged `deck_seen:<n>`.
  - Deck indices are first-seen order, not the real slot order. Nothing reads the opponent's slot order except the deal, which J7 fits anyway (`opp_deal_fit`).
- **Slot flags:** the highest form a card was seen in, from plays or bodies (1 evo, 2 hero). A form never seen reads 0. That cannot matter (b): an evo that never evolved live, or a hero never played, behaves like flag 0 over the match.
- **Towers:** the tick-0 max hp looked up in crforge's tower table.
- **Words:** ours from our tag; the opponent's is unknown (null).
- **RNG-free rule:** no SEEN card of either side is a drawer (Arrows, Princess, Hunter, Skeleton King).
  - An unseen slot was never played, and G0's drawers draw only when they act. So an unseen drawer cannot draw, unless one of its plays was missed (b).
  - A missed play shows as `opp_no_fitting_deal` or `own_cycle_fail`. The stricter rules below exclude those.

## Validation on the 226 API-backed matches (a, `check_levels.json`)
| item | us | opponent |
|---|---:|---:|
| card levels from body hp | 1126/1126 exact | **1307/1307 exact** |
| card levels from side mode (spells) | 682/682 | **348/377 = 92.3%** (misses: 28 one level low, 3 two low; Arrows, Graveyard, Fireball, ...) |
| slot flags | 1808/1808 | 1623/1684 = 96.4% |
| towers (group, level, king level) | 226/226 | 226/226 |
| deck complete (8 seen) | 226/226 | 132/226 |
| seen card not in the API deck | 0 | 0 |
| API cards never seen / of them flagged evo-hero | 0 | 124 / 29 |

The match logged as `151416` has no end-of-match towers, so the derived pass skipped it; the API set stays the 227 already on the pod.

RNG-free, live-seen rule vs the API deck rule, over 226 matches:

| live rule | API rule | n |
|---|---|---:|
| free | free | 138 |
| free | not free | 16 |
| not free | free | 0 |
| not free | not free | 72 |

- The 16 are mostly an unseen Arrows (13). Under crforge's RNG model an unplayed drawer does not draw, so these are RNG-free unless a play was missed (b).
- With `cycle_ok` (both cycle checks pass): 123 live-free, of which 109 are API-free.
- With `deck8` (cycle_ok + all 8 opponent cards seen): 72 live-free, of which **72/72 are API-free** (a).

## Batch (a, `noapi_stats.json`), written to pod `/workspace/pilot/inputs/inputs_expanded.jsonl`
1,002 matches, sha256 bdfc877e…:
- 1,451 live logs on or after 10-19 06:00. 228 are claimed by a battle-log entry, leaving 1,223 to try.
- Skipped: 118 no frames, 101 not the main account (princess ≠ 4858), 1 no end-of-match towers, 1 corrupt JSON line.

Usable for J7, RNG-free under each flag rule (expanded + API-backed):

| rule | expanded | API-backed (A2b-1) | total |
|---|---:|---:|---:|
| any (RNG-free by seen cards) | 673 | 138 | 811 |
| cycle_ok (own cycle legal and ≥ 1 opponent deal fits) | 475 | 109 | 584 |
| deck8 (cycle_ok + all 8 opponent cards seen) = no flags | **292** | 109 | **401** |

## Caveats
- **Game mode unknown (b).** These logs carry no battle-log entry, so they may hold ladder matches as well as Ranked ones. Opponent towers below L16 occur in 79/1,002 matches, against 2/227 in the Ranked set.
- **11 records have `game_build` None.** Their first `phase2` row is null. The other 991 are on build 160402012.
- **Short logs:** 44 matches have < 10 opponent plays, and 18 have their last play before tick 2000. They are not filtered out.
- **Spell levels by mode** are 92.3% right on the opponent side. J7 should treat a spell level as ±1 (b).
