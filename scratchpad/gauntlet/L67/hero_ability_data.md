# L67 — Hero Ice Wizard ("Frosty Fella") pro-usage data audit

Date: 2026-09-12. Read-only pass: no network, no engine/VM, no training.
Labels: (a) measured (number + source), (b) plausible untested, (c) contradicted.

Ability under study (owner-supplied): hero Ice Wizard, ability "Frosty Fella", 2 elixir. It spawns a snowman (321 HP)
behind the Ice Wizard's current target, deals 108 area damage once, then freezes every enemy within 2.5 tiles for 7 s
or until the snowman is destroyed.

Scripts used (session scratchpad, read-only, print counts only): `hero_count.py`, `ability_rows.py`,
`press_per_deploy.py`, `adoption.py`, plus inline polars scans of the HF parquet (icebow venv, POLARS_MAX_THREADS=2).

## Log (appended as work proceeds)

### Q1. Where the replay data and crawler code live, and what dates they cover

| set | path | battles | battle dates (UTC) | plays file(s) |
|---|---|---|---|---|
| icebow crawl1 | `icebow/data/royaleapi/{battles,plays}.csv` | 53 | 2026-08-26 .. 2026-08-29 19:42 | plays.csv (old 7-column schema: side, card, ability) |
| icebow crawl2 | `icebow/data/royaleapi/crawl2/` | 2,073 (2,005 on/after 08-04; 1,071 on/after 09-01) | 2021-10-23 .. **2026-09-06 08:09** | plays_ext.csv (1,237 tags), plays_ext_i1.csv (1,405 tags, has attr_i) |
| hogeq crawl2 | `hogeq/data/royaleapi/crawl2/` | 953 (931 on/after 08-04; 436 on/after 09-01) | 2024-08-30 .. **2026-09-06 15:05** | plays_ext.csv (595 tags), plays_ext_i1.csv (645 tags) |
| HF icebow/hogeq subsets | `scratchpad/gauntlet/ext/crawl_hf_{icebow,hogeq}/` | 766 / 523 | no timestamps (anonymised) | plays_ext.csv |
| HF full dump (FirstLight / VanguardX101 IL_Replay) | `scratchpad/gauntlet/L67/hf/replays/part-*.parquet` (52 parts, 788 MB) | 252,238 replays | no timestamps; contains berserker-hero and valkyrie-hero (released 2026-08-03), so it reaches past 08-03 | payload_json events |
| raw replay HTML | `*/crawl2/payloads/*.html` | 614 icebow, 297 hogeq | — | — |

(a) The latest battle in ANY local crawl is 2026-09-06 15:05 UTC (hogeq crawl2). The owner unlocked hero Ice Wizard
on 2026-09-12, so **every local dataset predates it by at least 6 days**. The wiki hero ledger
(`research/sim_parity/ledger/r1b_heroes.json`, fetched 2026-08-25) lists 18 hero pages (16 live, 2 announced: Battle
Healer, Mega Knight) and no Ice Wizard hero, not even as announced.

Crawler code (outside the repo), `C:/Users/benpe/clash-replay-scraper/`:
- `crawl_deck.py`: deck-parameterised, the current crawler.
- `crawl_icebow.py`: frozen; it produced icebow crawl2.
- `royale/pipeline.py`: the crawl stages.
- `royale/parse.py`: HTML parsers, including `is_variation`.
- `royale/transport.py`: Cloudflare clearance and the session-cookie curl.
- `royale/cookies.py`.

In-repo helpers:
- `scratchpad/gauntlet/L64/xy_why/refetch/crawl_par.py` and `refetch_par.py`: sharded replay fetch.
- `scratchpad/gauntlet/L67/hf_to_crawl.py` and `hf_to_crawl_deck.py`: HF parquet to the crawl2 layout.
- `research/sandbox_tools/replay_drive.py` and `replay_batch.py`: engine replay.

### Q2. How heroes/champions are named, and what exists

Naming (a):
- **RoyaleAPI deck strings:** heroes are `<base>-hero` (16 slugs seen, e.g. `knight-hero`, `berserker-hero`), evolutions
  are `<base>-ev1`, and champions are plain slugs (`golden-knight`, `mighty-miner`, `archer-queen`, `skeleton-king`,
  `goblinstein`, `monk`, `boss-bandit`, `little-prince`).
- **In the plays timeline a hero deploy uses the BASE slug.** Icebow: of 1,480 hero deck-sides with plays, 1,467 show
  the base slug and 0 show `-hero` (13 never played it). Hogeq: 470/470 base slug. So a hero shows up only in the
  battle's deck string, never on a play row. For Ice Wizard this means an `ice-wizard` play is a hero play only if that
  side's deck string holds `ice-wizard-hero`.
- **CardDB:** `icebow/config/cards.yaml` has 203 keys and `cards_stats.json` 180 (hogeq has the same counts). Both
  have 16 `<base>_hero` keys, the same 16 as the slugs. Champions carry `champion: true` in cards_stats.json (8 keys).
  **There is no `ice_wizard_hero` in cards.yaml, cards_stats.json or card_mechanics.json, in either deck.**
  `CardKB.ability_identity` only creates an ability action for cards with `ability_bomb_damage` (the Mighty Miner shape).
- **Sandbox engine catalog** (`research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json`, game_version
  15.535.29, generated 2026-08-24): 16 hero forms (Balloon, BarbLog, Berserker, Bowler, DarkPrince, EliteArcher, Giant,
  Goblins, IceGolemite, Knight, MegaMinion, MiniPekka, Musketeer, Tombstone, Valkyrie, Wizard), each with
  `hero_ability_max_charges: 1`. **IceWizard has `hero_form: null`.** This engine build cannot spawn the hero Ice
  Wizard or Frosty Fella.
- **Live templates:** the owner's `ice_wizard_hero_*.png` files (11 in cards/, 2 in next/) are already loaded as
  `ice_wizard` by the prefix loader (HANDOFF L67ae trap).

Search for hero Ice Wizard under every naming variant (`ice.?wizard.?(hero|champ)`, `hero.?ice.?wizard`, snowman,
frosty) (a):
- **icebow crawl1:** 0.
- **icebow crawl2:** 0. Its 2,166 `ice-wizard` deck-sides are all the base card.
- **hogeq crawl2:** 0 (58 base).
- **HF icebow/hogeq subsets:** 0.
- **HF full dump:** 0 of 252,238 replays. The literal `"ice-wizard-hero"`, the regex and snowman/frosty all return 0.
  The same scan finds every live hero (replays containing it): berserker-hero 98,324, valkyrie-hero 31,929,
  wizard-hero 30,247, balloon-hero 29,350, mini-pekka-hero 25,220, knight-hero 23,490, giant-hero 23,235,
  mega-minion-hero 22,695, bowler-hero 19,895, barbarian-barrel-hero 18,567, dark-prince-hero 15,473,
  musketeer-hero 15,397, tombstone-hero 15,251, ice-golem-hero 13,064, magic-archer-hero 8,994, goblins-hero 6,476.
  mega-knight-hero and battle-healer-hero are 0. The base `"ice-wizard"` appears in 19,644 replays (7.8%). The
  scan works; the hero is simply absent.
- => **0 battles, 0 plays, 0 ability presses of hero Ice Wizard exist locally.** Pro-usage data needs a new crawl.

Ability presses per hero/champion in existing data (attr_ability == 1; every one has attr_card `_invalid`) (a):

| file | ability rows | replays with at least 1 | attributable (the pressing side has exactly 1 hero/champion) | ambiguous (2 on that side) |
|---|---|---|---|---|
| icebow crawl1 plays.csv | 141 | 40 | 134 | 7 |
| icebow crawl2 plays_ext.csv | 2,829 | 941 | 2,489 | 340 |
| icebow crawl2 plays_ext_i1.csv | 3,040 | 1,051 | 2,679 | 361 (11.9%) |
| hogeq crawl2 plays_ext.csv | 2,416 | 566 | 2,295 | 121 |
| hogeq crawl2 plays_ext_i1.csv | 2,616 | 614 | 2,476 | 140 (5.4%) |
| HF icebow subset | 1,642 | 573 | 1,398 | 244 |
| HF hogeq subset | 1,886 | 483 | 1,727 | 159 |
| HF full dump | 854,195 `activate_ability` events | — | FirstLight marks `ability_source_authoritative: false` and lists `ability_source_candidates` | — |

Top attributed presses:
- **icebow plays_ext_i1:** golden-knight 319, knight-hero 299, balloon-hero 229, valkyrie-hero 223, berserker-hero 216,
  archer-queen 207, tombstone-hero 161, wizard-hero 152, goblinstein 108, skeleton-king 95, mini-pekka-hero 94, ...,
  ice-golem-hero 11, giant-hero 11.
- **hogeq plays_ext_i1:** mighty-miner 1,521 (the deck's own champion), golden-knight 137, archer-queen 93,
  wizard-hero 82, balloon-hero 81, ...

Attribution rules (a unless marked):
- **Two ability cards can share a deck.** One hero plus one champion, or two heroes (Hero slot plus Wild slot), is
  legal. Wiki Heroes master page, verbatim in the r1b ledger: "Only two Heroes can be in a deck at a time ... 1 Hero
  and 1 Champion at the same time". Deck-sides with more than 1 hero/champion: icebow crawl2 155, hogeq 68, HF
  icebow 68, HF hogeq 51.
- **Hero abilities are single-use PER DEPLOY, not per match.** Sources: wiki history 2026-08-04 ("made every ability
  single-use") and the engine catalog's `hero_ability_max_charges: 1`. Test on battles from 2026-08-04 on,
  single-ability sides only (`press_per_deploy.py`):
  - icebow: 1,723 of 1,724 hero presses had an unspent deploy of that hero before them (1 violation); hogeq: 546/551
    (5 violations).
  - No press came before the hero/champion's first deploy (icebow 0/2,610, hogeq 0/2,429).
  - A hero is pressed 0-5+ times per side per match (icebow 1-hero sides: 0:501, 1:327, 2:206, 3:120, 4:65, 5+:67).
    One charge per match is therefore **(c) contradicted**; one charge per deploy fits.
- **Timing alone rarely settles a 2-ability side.** Candidate = deployed and, for a hero, still holding a charge. This
  resolves only 37 of 346 icebow and 20 of 133 hogeq presses; the rest stay ambiguous. A hero-Ice-Wizard analysis
  should keep sides where hero IW is the ONLY hero/champion.
- **Press timing, a proxy for how pros use hero abilities** (icebow, single-ability sides, battles from 08-04 on):
  - Seconds from the hero's last deploy to the press: median 6.2 (p10 1.9, p25 3.5, p75 10.4, p90 15.7). 21% come
    within 3 s and 4% after more than 20 s.
  - Presses by match phase: 0-60 s 223, 60-120 s 268, 120-180 s 507, overtime 726. Heroes are pressed mostly late,
    in double elixir and overtime (b: part of that is simply more deploys late).
  - Champions: median 7.5 s. Hogeq heroes: median 8.0 s.

### Q3. What an ability-press row contains, and whether the engine can rebuild the state at the press

Row content (a):
- **crawl2 CSV row:** `replay_tag, play_index, tick, seconds, x_units, y_units, tile_x, tile_y, attr_ability=1,
  attr_card=_invalid, attr_s (red|blue), attr_t (= tick in 3,040/3,040), attr_i (seat flag)`.
- **x/y on ability rows are the literal string "None"**: icebow i1 3,040/3,040, hogeq i1 2,616/2,616. TRAP: a naive
  "x is set" count reports 3,040 because "None" is non-empty. The raw HTML agrees:
  `<div class="red marker" data-x="None" data-y="None" data-c="_invalid" data-t="1174" data-i="1" data-s="o">`
  and the timeline `<img class="replay_card" data-card="_invalid" data-ability="1" data-t="1174" data-s="red" src="">`.
- **HF events:** `kind: activate_ability, card_key: null, coordinates: null, replay_tick_20hz, side,
  ability_source_candidates [...]`. No more than the CSV has.
- => **A press carries only the tick (20 Hz) and the side.** No hero identity, no target, no position, no elixir.
  Everything else must come from reconstruction.

Can `research/sandbox_tools/replay_drive.py` rebuild the state at the press? (a on the code, b on fidelity)
- **Today it skips presses.** Ability rows are logged as `skipped: "ability plays not driven by this version"` (line
  400). Deal inference also ignores them, which is correct: an ability is not a card and does not rotate the cycle.
- **The engine API exists.**
  - `NativeRoyaleEnv.use_ability(side, entity_id)` (native_core/env.py:285), and `joint_act` with
    `{"type": "ability", "entity_id": ...}`.
  - Entities expose `entity_id` (the 5,000,000-series generation key) and `ability_state_code`, named `ready`,
    `on_cooldown`, `all_charges_consumed`, `not_enough_elixir`, `casting`, etc. Hand items expose `has_hero`
    (form_flags & 2).
  - `deck_spec` already passes `form: "hero"` from `split_slug`.
  - Nothing in the repo calls `use_ability` yet (grep: 0 callers).
- **Fidelity so far, without abilities** (HANDOFF §5ay / §5cs.59): icebow 99.2% of plays accepted (211/268 replays),
  hogeq 98.7% (17,514/17,745), determinism 27/27 SAME. When a press is skipped, the presser keeps 1-3 elixir and the
  enemy never takes the ability's effect, so the state drifts after the first press (b: size unmeasured).
- **Blocker for Ice Wizard (a).** The engine catalog (game 15.535.29) has no IceWizard hero form, so the current engine
  cannot deploy the hero. `card_for_slug("ice-wizard")` resolves to the base card, and a press would be refused.
  Rebuilding a hero-IW replay needs a newer libg runtime with that form, which is out of scope here.
- **Partial workaround (b).** A snapshot at the press tick of the state BEFORE the press is still possible, using the
  base Ice Wizard as a stand-in (same body and attack). The IW position, its likely target, the enemies within
  2.5 tiles of that target, tower HP and both elixirs should hold up to the first press of the match (each drive
  after that drifts). Validate the stand-in on replays whose first press is late.

Code change to drive presses (design only, not run):
1. **`drive()`, at an ability row:** take `obs = env.observe()`. Candidates are own-side entities with hero form or a
   champion identity and `ability_state_name == "ready"`.
   - Exactly one candidate: call `env.use_ability(side, entity_id)`. On `not_enough_elixir` (1050), wait up to
     `elixir_slack` ticks, as for plays. Log 1014 (ability_exhausted) and other codes as divergences.
   - Zero or several: log `ability_unresolved` with the candidate list (the attribution problem above).
2. **`record_plays`:** also store the full observation BEFORE each press as a `play_frames` entry with `ability: true`.
   Include the hero's entity id, x, y and hp; its current target, if the engine state exposes one (unknown, check
   `env.observe()` keys); every enemy entity with its distance to the hero and to the target; towers; both elixirs.
   That row is the Frosty Fella measurement.
3. **`grade`:** add `abilities_driven`, `abilities_accepted` and `ability_rejected_by_reason`. First A/B on the existing
   16-hero corpus: does driving presses raise `crowns_match` against skipping them? That validates the change before
   any IW replay exists.
4. **Engine runtime:** a newer libg build with the IceWizard hero form (catalog regeneration plus parity check) is a
   prerequisite for IW replays. Separate, owner-approved step.

### Q4. How to find hero-Ice-Wizard battles on RoyaleAPI (crawl DESIGN only, no requests sent)

What the existing crawler supports (a, from code):
- **Endpoints.**
  - `/decks/stats/{deck}/similar` gives deck variations (`pipeline.similar_decks`).
  - `/decks/stats/{deck}/players/ratings` gives player boards for ANY deck slug (`pipeline.rated_players`).
  - `/player/{tag}/battles/history[?before=<ms>]` returns 10 battles per page. The parser (`parse.battles`) returns
    `team_deck` AND `opponent_deck` strings plus `battle_timestamp` for every row that has a replay button.
  - `/data/replay` returns the replay HTML.
- **Login.** `Curl.get` (history, deck pages) sends only the Cloudflare `cf_clearance` cookie. `Curl.json`
  (`/data/replay`) adds the RoyaleAPI session cookie (`auth=True`), and the crawl_deck.py docstring says replays are
  "login-gated". **So finding battles needs only Cloudflare clearance; fetching the replay (the ability presses) needs
  the crawl2 session mechanism.**
- **Filter.** The crawl keeps a battle only if `parse.is_variation(team_deck, seed)` holds: the player's OWN deck has
  the seed's 8 base cards, with evo/hero swaps allowed. The icebow crawl would therefore already keep an icebow pro's
  `ice-wizard-hero` games. It drops every hero-IW game on the opponent side and in other decks.
- **Rosters on disk:** icebow 228 players (206 walked), hogeq 115 (98 walked); `roster.json`. §5cs.73: the ratings
  boards run out near 228, and that discovery source is the ceiling.
- **Throughput:** 1 account gives 5.87-6.85 replays/min (mean 6.36). 429s are counted **per IP**: three accounts
  bought 1.23x throughput with 3.8x the 429s (§5cs.73), so extra accounts do not help. One logged run:
  97 requests for 48 replays (about 2 per replay, including 429 retries), limiter peak 2.94 req/s
  (`L64/crawl_runs.jsonl`). The history-page rate is not logged separately (b: same limiter, so a similar pace).

Discovery options (all (b), untested):
1. **Re-walk the existing rosters (343 players)** with a different filter. Keep a battle when `ice-wizard-hero` is in
   `team_deck` OR `opponent_deck`, and stop paging a player once a page's oldest `battle_timestamp` predates the hero
   release. Needs no new parser. The yield depends on adoption:
   - Since 08-04, icebow pros' own decks used a hero/champion in 491 of 2,006 battles, all `knight-hero` (51 players);
     1,515 had none (a).
   - They already run base Ice Wizard, so hero IW is a drop-in for that slot (b). Unlocking it costs 200 hero shards,
     so not every pro will have it yet (b).
2. **Ratings board for the hero seed:** `/decks/stats/ice-wizard-hero,knight-ev1,rocket,skeletons,tesla-ev1,the-log,
   tornado,x-bow/players/ratings` (slugs sorted, as the crawler emits them). The existing code takes it unchanged.
   This finds players who run the hero in icebow.
3. **Card-centred:** RoyaleAPI's card page for the hero, or its popular-decks search with an include-card filter (from
   memory the query parameter is `inc=<slug>`; verify with ONE probe after approval). This finds non-icebow hero-IW
   decks, which the owner also wants. **Needs a new parser** (none in `parse.py`).
4. **Top Path-of-Legends leaderboard, then histories, filtered on either side.** Needs a leaderboard parser. It is the
   least biased sample of "any match with hero IW" but has the lowest hit rate.

Expected hit rate p (share of scanned battles that contain hero IW on either side):
- **(a) Adoption of past new heroes on OPPONENT decks** (ladder at pro rating, crawl2, `adoption.py`), by days since
  release:

  | hero (released 2026-08-03) | days 14-20 | days 21-27 | days 28-34 |
  |---|---|---|---|
  | berserker-hero | 19.5% (n 113) | 11.5% (n 1,006) | 10.1% (n 1,814) |
  | valkyrie-hero | 5.3% | 5.4% | 6.4% |

  Days 0-13 have n = 4 in total, so there is no first-week measurement. Tombstone-hero (released 06-01) sits at 4.9%
  after day 35.
- **(a) The base card's reach:** `ice-wizard` is in 5.0% of opponent decks in crawl2 (151/3,026) and in 7.8% of HF
  replays on either side (19,644/252,238). Hero IW cannot exceed the IW base rate plus switchers.
- **(b) Working band for the first 1-2 weeks:** p ≈ 1-5% on general ladder battles and ≈ 10-30% on the rosters of
  icebow pros who unlocked it.

Request estimate for about 200 hero-IW battles with replays (b, built from the (a) rates above):

| scenario | p | battles to scan | history pages (clearance only) | replay requests (login) | wall time at ~6/min |
|---|---|---|---|---|---|
| icebow-pro rosters, adopters | 0.20 | 1,000 | ~350 (1+ page per roster player) | ~450 (225 fetches x 2) | ~2 h |
| mixed rosters + ratings board | 0.05 | 4,000 | ~400-600 | ~450 | ~2.5-3 h |
| general ladder only | 0.01 | 20,000 | ~2,000 | ~450 | ~6.5 h |

- **The time window binds too.** Only battles after the release count. 343 roster players at a median 2 kept battles
  per active day (p75 6; since 08-27, a) give roughly 700-2,000 battles in the first week. Waiting 5-7 days after
  release before crawling is therefore the cheapest way to reach 200 (b).
- **Go/no-go probe (pre-register it):** 1 history page for each of 30 roster players (30 requests, no login). Measure
  p. Continue only if p ≥ 0.03 in the first week; otherwise wait or switch to option 3.
- **Crawler changes:**
  - a `has_card(b, "ice-wizard-hero")` filter (either side) replacing `is_variation`;
  - a new output dir kept away from crawl2 (e.g. `icebow/data/royaleapi/crawl_hero_iw/`) so the training corpora do
    not change;
  - an entry in `crawl_par.CRAWLS`, and fresh `players_done`/`replays_done` files there (the existing marks would skip
    every roster player);
  - per battle, record which side holds the hero and whether hero IW is that side's ONLY hero/champion (attribution,
    Q2).

How pro use would be measured from the crawl (b):
- **Without the engine** (timeline only, available immediately):
  - per attributable press: the time since the IW deploy and the match phase;
  - the enemy deploys (card, x, y, t) and own deploys (e.g. a Tornado) in the previous ~5 s;
  - both elixir estimates from the timeline;
  - the IW's deploy cell.

  This gives "what push triggered the press". The IW's position at the press is unknown (median 6 s of walking).
- **With the engine, after a runtime that has the hero form:** the full pre-press snapshot (Q3 design). The headline
  mechanism metric is enemy units within 2.5 tiles of the IW's target at the press (HANDOFF H3).
- **Proxy corpus available now, without crawling:** hero abilities with a similar decoy / crowd-control mechanism,
  pressed by icebow pros themselves. `knight-hero` Triumphant Taunt (taunt + shield) has 299 attributable presses in
  icebow i1, `magic-archer-hero` (decoy) 30, `ice-golem-hero` Snowstorm (area damage + slow) 11. The same timeline
  analysis can be built and tested on these while waiting (b: how well they stand in for IW use is untested).

### Q5. Situations where a 2.5-tile freeze plus a 321-HP snowman decoy helps an X-Bow / Ice Wizard deck (all (b))

State the live bot actually has (a, from code), which corrects the brief on HP:
- **Detections** (`replay_mine.Detection`; play loop `d.base`, `d.team`): class, team (mine/enemy/unknown), cx, cy,
  w, h, conf, `ground_cy` for flyers.
- **(c) No per-unit HP live.** `obs_contract.Unit.hp_frac` is documented "engine: hp/max_hp; live: None". The brief's
  "detector tracks with ... hp" holds for the engine, not live.
- **Tower HP:** `TowerHpTracker` reads per-tower HP digits (enemy and own boxes). `obs_contract` blanks a live king's
  hp_frac.
- **Elixir:** own elixir as an integer from the bar; `opp_elixir` from `OpponentElixirEstimator` (L67f), possibly None.
- **Threats:** `ThreatTracker` provides motion tracks, approach speed, `enemy_has_wc`/`wc_active` (a
  tower-targeting win condition on the board) and projectile-toward-tower.
- **Time:** `t_sec`, `double_elixir`, `overtime`. Own plays are logged by play.py.
- **Ability tap path: already in hogeq `play.py`, not in icebow.** The button tap is at `hand.ability_button`
  [0.963, 0.758]. `_champion_on_board` checks the detector for `base == champ and team == mine`, and a spent flag per
  body matches the single-use-per-deploy rule measured in Q2. Icebow `play.py` has no ability code (grep).
  - Hero templates already load as `ice_wizard`, and the owner's deck uses the hero, so every own `ice_wizard`
    detection is the hero.
  - **Keep the Frosty Fella trigger a RULE outside the policy action space.** `CardDB.ability_identity` would not emit
    it (no `ability_bomb_damage`), and adding an identity changes checkpoint width silently (its docstring warns).
- **Scale:** hogeq config comments give 0.064 frame width = 2.2 tiles and 0.28 = 9.6 tiles, about 0.029 frame units
  per tile, so **2.5 tiles ≈ 0.073** (b: derived from comments; check on the board warp).
- **Not observable live:** the IW's current target. Approximate it with the enemy detection nearest the own IW within
  IW range (look up `range_tiles` for ice_wizard in cards_stats.json).

| # | situation | why the freeze or decoy helps | rule test on live features |
|---|---|---|---|
| 1 | Hog / Ram / Battle Ram / Balloon plus support reaching the Tesla or X-Bow | Snowman spawns behind the target, so the win condition and its support stack inside 2.5 tiles; the building and tower hit freely for up to 7 s. Building-targeting win conditions do not attack the snowman (b: game rule to confirm), so only the support or a spell can end the freeze early | `wc_active`; enemy win-condition track within ~0.1 of own Tesla/X-Bow detection; at least 2 enemy detections within 0.073 of it; own `ice_wizard` detected within range; own elixir ≥ 2; not spent this deploy |
| 2 | Enemy ground troops attacking a LOCKED X-Bow at the bridge (Knight, Valkyrie, Mini P.E.K.K.A., Bandit, swarm) | Freeze keeps the X-Bow alive and firing on the tower | Own X-Bow detection forward of `xbow_forward_board_y`; at least 1 enemy ground detection within ~0.05 of it; own IW on board nearby |
| 3 | Tank or building-targeter walking at the X-Bow (Giant, Royal Giant, Golem, Electro Giant) | 7 s frozen outside or at the edge of X-Bow range buys shots; the tank will not break the snowman itself | Enemy detection with a tank class moving toward own X-Bow/Tesla (ThreatTracker approach speed); distance to own building < ~0.15; tank's support within 0.073 |
| 4 | Tornado pull into a cluster | Tornado packs a spread push into 2.5 tiles, then the freeze covers all of it plus IW splash (the doctrine's Tornado synergy) | Own Tornado played in the last ~1.5 s; at least 3 enemy detections within 0.073 of the Tornado cell; own IW in range |
| 5 | Counter-push: own X-Bow or troops on the enemy princess, enemy defenders arrive | Freezing the defenders gives the X-Bow up to 7 s on the tower. **Open question with the highest value: does "every enemy" include crown towers?** If it does (the Freeze spell does), a freeze near the tower also stops it shooting the X-Bow | Enemy princess alive with `TowerHpTracker` hp_frac known; own X-Bow in range of it; at least 1 fresh enemy detection within ~0.1 of own X-Bow |
| 6 | Overtime or tower finishing | Low enemy tower HP plus a short freeze of defenders or the tower (see 5) secures the crown | `overtime` or t > 150 s; enemy princess hp_frac < ~0.25; own attacking units near that tower; enemy detections within 0.073 |
| 7 | Swarm on own tower (Skeleton Army, Goblin Gang, Graveyard skeletons, Bats) | 108 area damage likely kills Skeleton/Bat-class units outright (b: check their level-scaled HP in cards_stats) and freezes the rest | At least 4 enemy small-class detections within 0.073 of each other on own half; Log not in hand or already committed |
| 8 | Protect the IW itself or the Tesla from a single big melee (P.E.K.K.A., Mega Knight, Prince) | Decoy plus freeze removes 7 s of DPS | Enemy heavy-melee class within ~0.07 of own IW or Tesla |

Do NOT press (doctrine: triage, cheapest sufficient answer; all (b)):
- **A lone cheap unit.** Require at least ~4 enemy elixir inside 0.073 (per-class `elixir` from cards_stats), or a
  win condition.
- **Against splash that deletes 321 HP in about one hit** (Valkyrie, Bowler, Executioner, P.E.K.K.A.). The freeze ends
  when the snowman dies.
- **When `opp_elixir` ≥ the cost of a likely breaker spell** seen this match (Log/Zap/Fireball).
- **When no enemy is within IW range.** With no target, where the snowman spawns is unknown; check in a friendly
  battle.

Mechanism metric for any rule (H3): enemies inside 2.5 tiles at the press, freeze duration (the snowman's lifetime,
seen as its detection disappearing, which needs a snowman template/class), and tower damage taken in the 7 s after,
compared with matched unpressed situations.

## Summary of labels
- (a) 0 hero-IW battles, plays or presses in all local data (icebow crawl1, crawl2, hogeq crawl2, HF subsets, HF full
  252,238). The newest local battle is 2026-09-06 15:05 UTC, six days before the owner's unlock.
- (a) CardDB (both decks) and the engine catalog (15.535.29) lack an Ice Wizard hero. The engine cannot replay hero-IW
  games until the runtime has the form.
- (a) Press rows = tick + side only (x/y = the string "None", card `_invalid`). Hero identity must come from the deck
  string; 5-12% of presses sit on 2-ability sides and stay ambiguous.
- (a) Hero abilities are single-use per deploy: 1,723/1,724 icebow and 546/551 hogeq presses fit. "Once per match" is
  (c).
- (a) Replays need login (`/data/replay`, `auth=True`); discovery via history pages needs only Cloudflare clearance.
  429s are per IP; ~6.4 replays/min.
- (b) About 200 hero-IW battles cost ~350-2,000 history pages plus ~450 replay requests (~2-6.5 h), depending on
  adoption. Do the 30-request probe first, and wait 5-7 days after release.
- (c) The brief's premise "live tracks with hp" is wrong: live unit HP is None. Tower HP is available.

STATUS: complete
