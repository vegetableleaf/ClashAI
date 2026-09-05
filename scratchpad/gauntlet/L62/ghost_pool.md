# L62 -- Ghost pool: recorded human opponents for the real-engine training env
Started 2026-09-05. Every number below is MEASURED on this box unless explicitly marked REASONING or UNTESTED.

Source corpus: `icebow/data/royaleapi/crawl2/` (crawl ACTIVELY RUNNING; snapshot row counts recorded in §1).
Conversion pipeline: `research/sandbox_tools/replay_drive.py` (load_battle / deck_for_side / infer_deals /
sp_order_for / deck_spec / build_replay), same name mapping as L61 §5ay/BC-v2.

## 0. SCHEMA (stable -- read this section, it is written first and does not change)

File: `icebow/data/ghost_pool/pool.jsonl` -- one JSON object per usable battle, UTF-8, one line each,
no trailing commas, ordered by `tag`.

```jsonc
{
  "tag": "00QYPQ2JJ9PC",          // str, RoyaleAPI replay_tag; primary key, unique in the file
  "rating": 3429,                  // int OR "" -- the ICEBOW player's rating (Path of Legend rating,
                                   //   NOT trophies) as recorded in battles.csv; "" when the crawl has none
  "rank": 1,                       // int OR "" -- CORRECTION (measured, see §5): this is the player's
                                   //   rank on RoyaleAPI's leaderboard FOR THIS DECK (roster.json,
                                   //   150 players), NOT a global ladder rank. Range 1..99 in the pool.
  "result": "loss",                // "win" | "loss", FROM THE ICEBOW SIDE
  "icebow_side": 1,                // int engine side (0 or 1). RoyaleAPI "blue" -> 1, "red" -> 0.
                                   //   battles.csv team_deck is the "blue" player, and the crawl is seeded
                                   //   from icebow players, so this is 1 for nearly every row (exceptions
                                   //   are icebow-vs-icebow mirrors, see §2).
  "ghost_side": 0,                 // int, = 1 - icebow_side
  "icebow_deck": [                 // list of 8, IN THE ORDER deck_spec() WANTS (= the order returned by
                                   //   deck_for_side(battle, side), i.e. battles.csv deck-string order).
                                   //   Feed straight to deck_spec(order, level) after sp_order_for().
    {"slug": "ice-wizard",         //   RoyaleAPI slug (form suffix stripped)
     "name": "IceWizard",          //   engine/catalog internal_name (what resolve_card() takes)
     "sim_key": "ice_wizard",      //   sim cards.yaml key (L61 name map); null if unmapped
     "card_id": 26000023,          //   engine card_id (resolve_card result)
     "form": "base",               //   "base" | "evolution" | "hero"
     "cost": 3,                    //   catalog elixir
     "level": 11}                  //   int -- SEE THE LEVEL CAVEAT BELOW
  ],
  "ghost_deck": [ ... same shape, 8 items ... ],
  "ghost_commands": [              // the opponent's 20 Hz command timeline, tick-ascending
    {"tick": 198,                  //   int, engine tick (20 per second)
     "seconds": 9.9,               //   float, crawl's own seconds column
     "card": "bomber",             //   RoyaleAPI slug
     "name": "Bomber",             //   engine internal_name
     "sim_key": "bomber",          //   sim key or null
     "deck_index": 3,              //   index into ghost_deck of the card played (deck_spec order)
     "x": 9000, "y": 5500,         //   engine units, 1000 per cell; null for ability presses
     "ability": 0}                 //   1 = hero/evolution ability press (no card, no position; the
                                   //     replay driver SKIPS these -- see §6)
  ],
  "icebow_commands": [ ... same shape, for reference / imitation learning ... ],
  "final_crowns": [0, 1],          // [side0_crowns, side1_crowns] -- ENGINE SIDE ORDER, not team/opponent
  "duration_ticks": 5710,          // int, tick of the LAST play in the battle (crawl records no match end;
                                   //   this is a lower bound on match length, NOT the terminal tick)
  "plays": 77,                     // int, total plays both sides (= battles.csv `plays`)
  "battle_type": "pathOfLegend",
  "battle_timestamp": 1788130968,  // int unix seconds
  "player_tag": "JJUJ0Q908",       // icebow player's tag (crawl seed player)
  "opponent_tag": "JLJVRV8V2",     // ghost player's tag ("" if absent)
  "deal_candidates": {"0": 6, "1": 2}, // number of (opening hand, draw queue) assignments consistent with
                                   //   each side's play sequence, from infer_deals(). >0 for both sides is
                                   //   a hard requirement for inclusion. Keyed by engine side, as strings.
                                   //   MEASURED median 256 -- never unique; see §6.
  "mirror": false,                 // bool -- true when the ghost deck is the icebow deck (icebow mirror).
                                   //   2 of 447.
  "engine_verified": null          // null, OR the real engine's own verdict for this tag from L61's
                                   //   batch_v2 drive (211 of 447 have one):
                                   //   {position_based, same_cards_after_permute, accepted, plays_driven,
                                   //    rejected{}, invalid_placement, crowns_match, engine_crowns,
                                   //    expected_crowns, terminated, termination_reason, final_tick,
                                   //    state_hash}.  A null here means the tag converts on paper but the
                                   //    engine has NEVER driven it -- UNTESTED.
}
```

**LEVEL CAVEAT (measured):** battles.csv carries NO card levels. `level` is a constant fill (11 =
tournament standard, the same value L61's batch used). It is not data from the match.

**COORDINATES:** x,y are the crawl's `x_units`,`y_units` -- engine units, 1000 per cell, 18 columns
(0..18000) x 32 rows (0..32000). Engine side 0 plays rows 0..14 (low y), side 1 rows 17..31 (high y).
`env.act(side, deck_index, x, y)` takes them unchanged.

**HOW TO DRIVE A GHOST:** build the replay exactly as `replay_drive.drive()` does
(`infer_deals` -> `sp_order_for(deck, hand_positions, cycle_positions, deal)` -> `deck_spec(order, level)`
-> `build_replay`), then for the ghost side issue `env.act(ghost_side, cmd["deck_index_after_sp_order"], x, y)`
at each `tick`. NOTE: `deck_index` in this file indexes the **battles.csv deck order**; after `sp_order_for`
permutes the deck for the engine's dealt positions you must re-index by slug (the driver does exactly this
with its `index_of` dict). The slug is the stable key.

Loader: `scratchpad/gauntlet/L62/ghost_pool.py` -- `load_pool(path) -> list[dict]`,
`sample(pool, rng, rating_range=None)`.


## 1. Corpus snapshot (the crawl is LIVE -- these are the numbers at read time)

Copied to `scratchpad/gauntlet/L62/snap/` at **2026-09-05 13:03 local / 17:03 UTC**; every number in
this document is computed from that snapshot, never from the live files (which were not written to).

| file | data rows at snapshot |
| `icebow/data/royaleapi/crawl2/battles.csv` | **1148** battles (1148 distinct replay_tags, no duplicate tag rows) |
| `icebow/data/royaleapi/crawl2/plays_ext.csv` | **101351** play rows over **1137** distinct tags |
| tags in plays_ext but not in battles.csv | 4 (ignored -- no battle row = no decks) |

The corpus has grown a long way past the 268 tags L61/§5ay worked from.

## 2. Conversion result

`scratchpad/gauntlet/L62/build_pool.py` (offline; reuses `replay_drive.split_slug`, `card_for_slug`,
`infer_deals`, `SIDE_OF`, `DECK_COL_OF_SIDE` unchanged, and calls the engine's own
`native_core.card_catalog.validate_deck` so a deck is only accepted if `build_replay` would accept it).

| | count |
| battles in snapshot | 1148 |
| **CONVERT -> in `pool.jsonl`** | **447** |
| refused | 701 |

Of the 447: **337 wins / 110 losses** from the icebow side (75.4% win rate -- the crawl is seeded from
the deck's leaderboard, so it is heavily win-biased; see §5). 2 are icebow-vs-icebow mirrors
(`mirror: true`). All 447 have a rating and a rank. Both decks and every played card name map:
`deck_cards_unmapped_sim_key = []`, `ghost_cmds_unmapped_sim_key = 0` (170 distinct card variants,
120 distinct base cards, all resolved to a catalog card_id AND to a sim `cards.yaml` key).

**211 of the 447 have already been driven through the real engine** (L61's batch_v2). Those carry an
`engine_verified` block copied from that batch: 204/211 position-based deal, 17757/17901 plays
accepted (99.2%), **164/211 (77.7%) ended on the same crowns as the real match**. The other 236 are
convertible on paper and have NOT been engine-driven -- treat them as UNTESTED until a batch run
covers them.

### Refused tags and why (full list: `scratchpad/gauntlet/L62/refused.json`)

| reason | tags | what it is |
| `play_not_positioned` | **574** | the crawl recorded ticks/cards/sides but **no x/y at all** for this replay. Bimodal, not partial: within an affected tag 90-100% of rows have empty `x_units`/`y_units`, and 129 tags have zero positioned rows. Not correlated with battle_type or date, and interleaved with good tags in file order -- so it is a per-replay property of the crawl's payload, not a crawl phase. Example: `00QYPQ2JJ9PC`, all 77 rows unpositioned. |
| `no_native_evolution_form` | **111** | a deck asks for an evolution the engine build has no `evolution_form` for. **100% of these are `elite-barbarians`** -- the same single blocker L61 found (57/268 there, 111/1148 here; over ALL non-converted battles the deck test fails on elite-barbs 207 times). |
| `no_plays_rows` | 15 | battle row exists, plays_ext has nothing for the tag (crawl in flight). Tags: 022YYYV9RGJQ 08UPPU9V8LCL 092PPUG2UGRL 092PPUG2C9J2 00YYPPR2VP0Y 08JPVCJQPRY0 00GYP9VJGR9R 00GYP9VJPGPJ 00GYP9VJ8QUC 00QYPYRC0CLJ 00QYPYPPUGL0 00JYPLJCQJJY 099P9JJ292YL 02QY9Q8YCLU9 00VYPPG2CR8U |
| `side0_no_positioned_plays` | 1 | `02GY9R002Q9Y` -- side 0 has only ability presses. |
| `play_count_mismatch` | **0 (was 7)** | 7 replays had every play row appended TWICE, byte-identical (verified on 00GYPYVCQL2G: 134 rows, 67 distinct play_index, 67 distinct full rows). The builder now de-duplicates exact rows before the count check; 3 of the 7 then converted, the rest hit another reason. Tags: 00GYPYVCQL2G 00UYPQ2JUL8V 00UYPQ2JJGJG 00GYPYCGCLYP 08QPVU0GY8CP 00GYPYCQPQCL 00GYPYCQ0CJU |

Nothing was refused for "no consistent deal" among positioned tags, and only 4 among all 1148
(see §4 ceiling). No hero-form refusals at all.

## 3. Opponent deck diversity -- and whether "10,000 distinct decks" is reachable

Measured on the 447 converted battles (deck identity = the sorted set of 8 (slug, form) pairs, so
`knight` and `knight-ev1` count as different cards):

- **314 distinct ghost decks** in 447 battles.
- **259 of the 314 (82.5%) appear exactly once.** Frequency histogram (decks seen k times):
  `1x:259  2x:27  3x:6  4x:10  5x:3  6x:4  7x:4  9x:1`. The most-repeated deck appears 9 times.
- **437 distinct opponent player tags** in 447 battles -- almost every match is a different human.
  (83 distinct icebow players, drawn from a 150-player RoyaleAPI leaderboard for this deck.)
- **170 distinct opponent card variants / 120 distinct base cards.** Only 4 variants appear in a
  single deck; the card vocabulary is essentially saturated, the deck space is not.
- Top 10 ghost decks by frequency (`-evo` = evolution slot, `-her` = hero slot):

| n | deck |
| 9 | barbarian-barrel, battle-ram-evo, giant-skeleton, mother-witch, royal-ghost-evo, vines, wizard-her, zappies |
| 7 | cannon, dart-goblin, goblin-barrel-evo, ice-spirit, princess, skeleton-army-evo, valkyrie-her, wall-breakers |
| 7 | balloon-her, barbarian-barrel, bomb-tower, giant-snowball, ice-golem, miner, musketeer-evo, skeletons-evo |
| 7 | archers-evo, barbarian-barrel, bomb-tower, electro-spirit, goblinstein, lightning, royal-hogs-evo, skeletons |
| 7 | cannon-evo, fireball, hog-rider, ice-golem, ice-spirit, musketeer-her, skeletons-evo, the-log |
| 6 | archers-evo, electro-spirit, fireball, knight-her, skeletons, tesla-evo, the-log, x-bow |
| 6 | arrows, elixir-golem, lightning, night-witch, rage, skeleton-army-evo, skeleton-king, witch-evo |
| 6 | barbarian-barrel, cannon-cart, fireball, goblin-gang, goblinstein, minion-horde-evo, mortar-evo, mother-witch |
| 6 | baby-dragon-evo, balloon, barbarian-barrel, bowler, freeze, inferno-dragon-evo, knight-her, tornado |
| 5 | archer-queen, barbarian-barrel, electro-spirit, fireball, goblin-hut, royal-ghost-evo, royal-hogs-evo, skeletons |

Most common opponent cards (number of the 447 decks containing them): barbarian-barrel 131,
the-log 103, fireball 101, skeletons 99, tornado 87, arrows 82, lightning 70, electro-spirit 65,
hog-rider 61, ice-spirit 56, zap 51, skeleton-army-evo 50, berserker-her 50, inferno-dragon-evo 49,
baby-dragon-evo 45.

### Saturation -- new decks per additional battle (MEASURED)
Converted pool, battles in timestamp order: 50 -> 49 decks, 100 -> 93, 200 -> 169, 300 -> 231,
444 -> 312 (447 -> 314). **Marginal rate over the last 100 battles: 0.56 new decks per battle**, down
from 0.94 over the first 50.
Whole corpus (all 1148 battles' `opponent_deck` strings, no conversion needed): **715 distinct decks,
598 of them seen once**; 100 -> 87, 250 -> 203, 500 -> 357, 750 -> 493, 1000 -> 644, 1148 -> 715.
The corpus curve is still near-linear at slope ~0.55-0.6.

### So: is 10,000 distinct decks reachable from this corpus?
**No -- not from this corpus, and not close.** MEASURED: the pool has 314; the entire crawl, converted
or not, contains 715. Extrapolating the measured marginal rate (0.56 new decks/battle, and falling)
gives, as a REASONING estimate, on the order of **20,000-30,000 crawled battles to reach 10,000
distinct decks** -- an 18-26x larger crawl -- and that assumes the rate does not decay further, which
it will. What it would actually take:

1. **Fix the two conversion blockers first; that is the cheapest 2x.** MEASURED ceiling (§4): 473 more
   battles would convert *today* if the crawl backfilled x/y, adding **273 ghost decks the pool does
   not have** -> 587 distinct decks from the existing 1148 battles. Adding an elite-barbarians
   evolution form to the engine build unlocks a further 207 battles.
2. **Crawl wider, not deeper.** Every additional icebow player brings mostly new opponents (437
   distinct opponents in 447 battles), but the *deck* pool is the bottleneck: the meta at this rating
   does not contain 10,000 decks that actually get played.
3. **REASONING, not measured:** 10,000 decks is only reachable by *synthesising* decks (sampling legal
   8-card decks from the observed 120-card vocabulary) and pairing them with a scripted or learned
   opponent -- at which point they are no longer ghosts. A ghost pool's size is bounded by how many
   real matches you can mine. The choice is explicit: ghosts give real human *policies* over few decks;
   synthetic decks give deck coverage with no policy behind them.

## 4. Conversion ceiling (`scratchpad/gauntlet/L62/ceiling.py`, MEASURED)

Re-running every acceptance test except the positional one, over all 1148 battles:

| outcome | battles |
| already converted | 447 |
| **would convert if x/y were backfilled** | **473** |
| deck asks for a missing evolution form (all elite-barbarians) | 207 |
| no play rows at all | 15 |
| no consistent (hand, queue) deal | 4 |
| plays a card outside its deck / a side with no plays | 2 |

So **920 of 1148 (80.1%)** of the corpus is convertible once positions exist, giving **587 distinct
ghost decks** (314 now + 273 new). The highest-value engineering item for this pool is the crawler's
position backfill, not more crawling.

## 5. Rating / trophy coverage (MEASURED) -- and what is missing

`battles.csv` carries **`rating`, `rank`, `wins_7d` for the ICEBOW player only. There is NO opponent
rating, trophy or card-level column anywhere in the crawl** (checked all 30 battles.csv columns and
`battles_raw.json`). Ghost strength can only be inferred indirectly, through matchmaking, from the
icebow player's rating.

Two naming traps: **`rating` is a Path-of-Legend rating, not trophies**, and **`rank` is the player's
rank on RoyaleAPI's leaderboard for THIS DECK** (roster.json holds 150 such players, ratings
1923-3429), not a global ladder rank.

Icebow-player rating over the 447 pooled battles: min **1923**, p10 2072, median **2282**, mean 2332,
p90 2762, max **3429**. Buckets of 500: `1500-1999: 8`, `2000-2499: 363`, `2500-2999: 52`,
`3000-3499: 24`. Deck-leaderboard rank: min 1, median 28, max 99.
Battle types: pathOfLegend 434, trail 6, PvP 3, clanMate 3, friendly 1.

**What we have vs what the owner asked for.** The request was coverage "from ~10,000 trophies to top
ladder". MEASURED: we have **none of it expressed in trophies** -- 434/447 battles are Path of Legend,
a mode with no trophy number, and the players are all inside the top 150 of one deck's leaderboard.
81% of the pool sits in a single 500-point rating band (2000-2499). There is **no low/mid-ladder data
at all**, no opponent rating for any battle, and no card levels (see the level caveat in §0) -- and
card levels are exactly what a 10,000-trophy opponent would differ by. Reaching that band means
crawling a different population (trophy-road ladder players of this deck), not more of this leaderboard.

## 6. Ghost command density (MEASURED over the 447 pooled battles)

| quantity | value |
| ghost plays per match | mean **45.1**, median 47, min 2, max 81; **20145** ghost commands total |
| icebow plays per match | mean 47.9, median 54, min 1, max 71; 21397 total |
| seconds between consecutive ghost plays | mean **5.39 s**, median 4.10, p10 1.55, p90 11.0, max 80.65 (19698 gaps; 3 gaps of 0 = two ghost plays on the same tick) |
| mean of the per-match mean gaps | 5.90 s |
| match length (tick of the LAST play / 20) | mean 254 s, median 290 s, min 34 s, max 299 s |
| ghost plays in the first 120 s vs after | 5560 vs 14423 (double elixir roughly doubles the rate, as expected) |
| matches reaching overtime (any play past tick 6000) | **0 of 447** -- these timelines stop at regulation |

**Ability presses are a real hole.** 1000 ghost commands and 26 icebow commands are hero/evolution
ability presses (`ability: 1`), present in **336 of 447 matches**. The crawl records no card and no
position for them, and `replay_drive.drive()` explicitly SKIPS them. They are kept in the pool with
`x/y = null` so a future driver can use them, but as of today a ghost holding a hero card will never
fire its ability -- that is 1000/20145 = **5.0% of ghost actions silently dropped**.

**Deal ambiguity.** `infer_deals` leaves the ghost's opening hand under-determined: median **256** of
1680 assignments are consistent with the play sequence (mean 256.5, max 480, and **never a unique
solution** in 447 battles). Cross-checked against L61's engine batch: my counts equal that batch's
`deal_inference` for all 211 shared tags, 0 mismatches. The driver takes `found[0]`. This does not
threaten legality (all 256 reproduce every play by construction, and the engine accepted 99.2% of
driven plays), but it means the ghost's *hand contents at time t* are not recoverable from this data --
do not feed an opponent-hand observation channel from this pool and call it ground truth.

## 7. What a ghost can and cannot do

*This section is REASONING, plus the measurements explicitly flagged inside it. It is not a measured
claim about training outcomes -- no policy has been trained against this pool yet.*

A ghost is a fixed list of (tick, card, x, y). It replays the same actions at the same clock times no
matter what our policy does. That is valid exactly while the board our policy produces stays close to
the board the ghost's human was actually looking at.

**What it can do, honestly:**
- Supply a *real human deck* played with *real human timing and elixir discipline* -- 45 plays a match
  at a 5.4 s median cadence, across 314 distinct decks and 437 distinct humans. No scripted bot we
  could write reproduces that distribution of openers, cycle habits and spell restraint.
- Serve as a fixed, perfectly reproducible evaluation opponent. Engine determinism is already MEASURED
  (L61: identical `state_hash` across repeat runs, 211/211 tags), so ghost matches are a stable
  benchmark and a stable regression test -- which a self-play opponent can never be.
- Anchor the opening. Before either side has reacted to anything, the ghost's first plays are
  genuinely what a human did in that spot.

**Where it stops being a valid opponent:**
1. **It never answers our push.** The ghost's counters were aimed at the *original* icebow player's
   placements. The moment our policy puts the x-bow in the other lane, the ghost's Tesla goes down in
   the lane we are not attacking. Our agent is then rewarded for a push nobody defended, and learns
   that the push is good when in fact the opponent was simply absent.
2. **Divergence compounds and never re-syncs.** Every tick of difference makes the next ghost command
   less appropriate than the last, and there is no mechanism that brings the two boards back together.
   Late-game commands -- and 14423 of 20145 ghost plays (72%) land after the 120 s double-elixir mark --
   are the least trustworthy part of the timeline, and also the part that decides matches.
3. **Reactivity is a measured share of the ghost's behaviour, and it is exactly the part replay
   destroys.** MEASURED: 59.4% of ghost plays land within 3 s of an icebow play and 78.2% within 5 s.
   Against a circular-shift null (each ghost timeline randomly rotated within its own span, 5 reps)
   those figures are 51.5% and 70.0%. The excess attributable to genuine time-locked reaction is
   therefore **+7.9 points at 3 s and +8.2 at 5 s** -- roughly one ghost play in twelve is demonstrably
   a direct response to what the icebow player had just done. Read that as a floor, not the whole
   story: a human also reacts to unit positions, tower HP and elixir reads with no tight time lock, and
   none of that survives replay either.
4. **Elixir accounting silently drifts.** The driver already waits up to 40 ticks when libg answers
   "not enough elixir", which is necessary precisely because the reconstructed elixir curve is not the
   real one. Against a *different* opponent the ghost's elixir would have been spent on different
   trades, so the same command list is not even the same elixir plan.
5. **It cannot punish anything new.** Any exploit our policy finds -- a degenerate cycle, camping the
   bridge, a placement no human ever tried -- goes unpunished, because punishment requires a decision
   the recording does not contain. A policy trained only on ghosts overfits to the specific holes in
   these 447 timelines.
6. **The crowns are not our crowns.** `final_crowns` is what the *original* match ended on. It is a
   label for imitation, never a reward signal for our agent -- the engine decides our outcome. Even the
   reconstruction fails to reproduce them: MEASURED, only 164/211 engine-driven replays finished on the
   recorded crowns (77.7%).
7. **Known missing capabilities:** ability presses are dropped (5.0% of ghost actions, 336/447
   matches); the ghost's hand is ambiguous (median 256 consistent deals, never unique); no card levels
   are recorded (level 11 fill for both sides); no timeline extends into overtime (0/447).

**Practical reading (REASONING).** Ghosts are sound as (a) the first rung of a curriculum, (b) a frozen
evaluation suite, and (c) the source of *decks* for a real opponent policy. They are not sound as the
sole training opponent past roughly the first 30-60 s of a match. The natural design is a hybrid: run
the ghost's timeline while the boards agree, and hand the ghost's deck to a learned or scripted
opponent the moment our policy's placements diverge from the icebow player's -- with the divergence
measured rather than assumed. **Nothing here measures how fast that divergence actually happens.**
That needs a run (drive a ghost against the current policy and log board distance per tick) and has
NOT been done.

## 8. Files, and a COLLISION to flag

Written by this task:
- `icebow/data/ghost_pool/pool.jsonl` -- 447 records, ~6.5 MB, schema in §0.
- `icebow/data/ghost_pool/pool_meta.json` -- build counts.
- `scratchpad/gauntlet/L62/ghost_pool.py` -- loader (`load_pool`, `sample`, `filter_pool`, `ghost_deck_key`).
- `scratchpad/gauntlet/L62/build_pool.py`, `analyze_pool.py`, `ceiling.py`.
- `scratchpad/gauntlet/L62/analysis.json`, `ceiling.json`, `refused.json`, `engine_verify.json`,
  `sim_card_keys.json`, and the read-only snapshot `snap/battles.csv`, `snap/plays_ext.csv`.

**COLLISION:** another agent working in this directory has its own builder,
`scratchpad/gauntlet/L62/build_ghost_pool.py`, and it wrote `icebow/data/ghost_pool/pool_build.json`
describing a **202**-record pool at the same `pool.jsonl` path (its base was L61's 211 engine-driven
tags, minus 7 "deal not position-based" and 2 "icebow deck on 2 sides"). **`pool.jsonl` as it stands
now is THIS task's 447-record file in the §0 schema**; that agent's 202-record version was overwritten.
Its two exclusions are preserved here as data rather than as filters -- every record carries `mirror`
and `engine_verified.position_based`, so filtering on `engine_verified=True`, `mirror=False` and
`engine_verified["position_based"]` reproduces its 202-battle subset out of the larger file. Someone
should decide which builder owns the path before both run again.

Nothing was committed. Nothing under `icebow/src/` or `icebow/data/royaleapi/` was modified.

STATUS: complete
