# L74 replay_rec: pro replay data from the game's own replay viewer

This replaces the RoyaleAPI crawl, which Cloudflare blocks for an honestly automated browser. Nothing here hides
automation. The memory reader watches a replay that the game itself plays.
Status 2026-10-08:
- Sections 1–5: offline preparation.
- The device feasibility test PASSED at 21:08. The lead ran it and the owner navigated by hand.
- Section 6: the harvest build, with no device commands from this worker.
Labels: **(a)** measured (number + source), **(b)** plausible but untested, **(c)** contradicted.

## 1. In-game replay sources (public web research, 2026-10-08)

| source | what it offers | volume | notes |
|---|---|---|---|
| **TV Royale** | 1 channel per arena and per Ranked league (33 channels when the wiki page was written) | 1 new replay per channel per hour, each kept for 24 h, so at most 24 per channel at any time (a) | Path of Legends (now "Ranked") replays were added 2024-03-18 (a). The game picks "upset matches, three crown draws, unusual decks and close calls", so these are not simply the top players' games (a). The top 200 players show their rank (a). A watched replay turns grey (a). |
| Battle-log replays | our own last matches | ours only | We already get these from the reader. They add no pro data. |
| Clan-shared and friendly-battle replays | whatever clanmates share; friendly battles can be watched live or as a replay | depends on the clan | (a) wiki Clans / Friendly Battle |
| Other players' battle logs | not found in any source | none | (b) not available in-game; RoyaleAPI gets them through the official API, not the client |
| Tournament replays | 2019: "Third-party tournament organizers can now access replays via deeplinks" | n/a | Not a practical source. |

- **Menu path (b, must be measured on the device):** the wiki says TV Royale moved to the Battle section (2016-07-04) and then
  to the Battle Tab (2019-04-15). A third-party guide (undated) says there is a TV icon labelled "Replays" at the top left of the Battle tab. Our own
  main-screen capture (`L70/ladder_nav/raw/main3.png`) shows **no TV icon** on the Battle tab. The candidates are the
  menu button (top right) and the Social tab. The dry run in section 4 finds it.
- **Playback speed (b, unverified):** the wiki confirms replay controls exist ("Show and hide replay controls by
  tapping the screen", 2016-02-29; "Fixed replay controls not being available in certain replays", 2019-09-30;
  "skipping past the 'Pick' phase in a Draft replay", 2022). A search-engine summary of a 2016 TouchArcade article
  says replays play at "slow, normal, or fast" speed, but the page returned HTTP 403, so this is not verified.
  `feasibility.py` prints `ticks_per_s` (20 = real time), which settles the question.
- **Ranked today:** "Ranked Mode (formerly Path of Legends)". Unlocking it needs 15,000 seasonal trophies, and the
  leagues now start at Master I (Supercell June 2025 release notes). So the Ranked channels are the high-skill channels.
- **Expected daily volume (b):** at most 24 new replays per channel per day. With the top 2–3 Ranked channels that is
  **about 48–72 high-skill replays a day**. If a replay can only play at real time (3–4 min) plus navigation, that is
  about 3–5 h of emulator time a day. For comparison, the whole icebow crawl2 holds 2,073 battles. The decks are mixed
  pro decks, not ours: an X-Bow / Icebow deck will be rare, so this source feeds the generalist far more than any
  single-deck model. This has not been measured.

Sources: Clash Royale Fandom wiki through api.php (pages `TV Royale`, `Version History/2016`, `/2017`, `/2019`, `/2022`,
`/2023`, `Clans`, `Friendly Battle`; fetched 2026-10-08, raw wikitext in `.foreman/scratch/replay_rec/wiki/`, not committed);
https://supercell.com/en/games/clashroyale/blog/release-notes/june-update-2025/ ;
https://androidphoria.com/games/salir-tv-royale-clash-royale (2016) ;
thetechylife.com "How do I Share a Replay on Clash Royale" (seen only in a search result; undated).

## 2. Reader capability verdict (code reading)

**What one reader frame holds** (`L70/reader/<reader source, local only>` emit_player / emit_chain, `<reader source, local only>`):
- Top level: `game_tick`, `battle_active`, `coherent`, `failure`, `applied_replay_tick`, `chain` (pointers), and `sample_monotonic_us`.
- `players[2]`: `side`, `elixir_raw`, `refill_timer`, `next_deck_index`, `hand_deck_indices[4]`, `cycle_deck_indices`.
  It also holds `deck_card_ids[8]` and `deck_form_flags[8]` (0/1/2 = base/evo/hero), but **only for a side whose hand
  is visible**: `read_visible_deck` returns early when every hand index is -1.
- `entities`: `address`, `category` (the generation id), `kind`, `side`, `x`, `y`, `card_id` (evo ids are 13xxxxxx and hero ids
  are 2030xxxxx), `hp`, `max_hp`, `level`, `behavior_state_raw`, `evo`.
- `--extended` adds `projectiles` (`side`, `x`, `y`, `target_x`, `target_y`, `card_id`) and `effects` (`side`, `x`, `y`,
  `card_id`, `remaining_ms`). L70 FINDINGS: a Rocket's target equals the logged cast point, and a Tornado effect sits at the cast point (a).

**What assumes "I am a player in this battle":**
- In a live battle the opponent's hand reads -1, so exactly one side is visible.
- `pipeline/live_mem.py:24 my_side_of` **raises ValueError unless exactly one hand is visible**. Everything that calls it
  breaks on a spectated replay: `board_state`, `live_gen(_v2).GenPilot.observe/row/guard_cells`, and
  `opp_elixir_count.PlayDetector.feed` when `my_side` is unset (it returns `[]`).
- `live_play.py:723` treats "both hands visible" as the results/replay screen and stops after 20 such frames. So it would
  harmlessly refuse to act in a replay.
- `deck_of(frame, side)` and `to_observe(frame, side, names)` take the side explicitly. They work for **either** side when
  both hands are visible, and `to_observe` copies only that side's player block.
- `PublicObserver(side)` presets `my_side` and never calls `my_side_of`, so it works on any frame.

**Choosing "me":** run the row builder once per side `s in (0, 1)`:
- Use `deck_of(frame, s)` and `to_observe(frame, s, names)`, then `from_engine(..., s, ...)`, which mirrors side 1.
- Take `opp_elixir` from `PublicObserver(s).estimate_at`, never from the other player's `elixir_raw`.
- Take the opponent history from `PublicObserver(s)` plays.
- This keeps the public-only rule: A's own hand, plus the opponent's PUBLIC plays only.
- The converter in this folder writes crawl rows, which go through the same `replay_drive` → driven corpus →
  `dataset_gen` path as the crawl, so that rule is enforced downstream exactly as it is today.

**Settled by the device test (2026-10-08 21:08; the owner navigated by hand; recording
`icebow/data/replay_rec/rec_20261008_210824.jsonl`, Ultimate Champion channel):**
- (a) Both hands are visible in a TV Royale replay: 793 of 793 frames are spectator frames, with both hands, next cards,
  elixir and decks with forms.
- (a) The reader's battle chain resolves in the replay viewer: `failure` is `none` on every frame.
- (a) `applied_replay_tick` is **-1** in the replay, against 200 at tick 206 in a live battle (`probe1.jsonl`). That is a
  second spectator signal; it is not used yet.
- (a) Speed: the owner says every replay plays at up to 4x. With 4x on, the recording ran at **73.1 ticks/s**.
- (a) In the replay the game first empties the played slot (`hand [3, 4, -1, 6]`, and the cycle grows to 5), then
  refills it one sample later. Two plays can land inside one 100 ms sample at 4x (Hog + Musketeer at t4848). Section 6
  covers the fixes.

## 3. What was built (this folder)

- `recorder.py`: **observe-only**. It contains no input or tap code, loads no model, and runs only the read-only sampler.
  - It stops the sampler by its exact device PID (`echo $$; exec …`), never with a pattern kill, because a `live_play.py`
    sampler may be running at the same time.
  - It saves every reader line with the host time.
  - It logs battle_start / battle_end (inactive or stalled for 3 s, tick reset, or `--max-seconds`).
  - It **refuses (exit 3)** when most of the first 20 advancing frames show exactly one visible hand (we are playing), and
    also when 20 such frames in a row appear later.
- `convert.py`: turns a recording into `battles.csv` + `plays_ext_i1.csv` in the crawl2 schema for **both** sides, with extra
  columns `form`, `detect` and `located`. It refuses a recording of a battle we played.
  - **hand path:** a hand-slot rotation gives the card and tick (the same receipt `live_play` uses to confirm our plays).
    The position is the first public object born for that card and side:
    - bodies: the centroid of the cohort;
    - spells: the projectile's `target_x/y`, or for the Log / Barbarian Barrel the first-seen position, or the effect's position;
    - Goblin Drill / Miner: followed until they stop, because they are first seen at the king tower.
  - **body path** (no hands visible): `PublicObserver` once per seat.
  - Not detected: hero/champion ability presses (there is no reader field for a press) and Mirror's identity.
- `test_replay_rec.py`: 5 synthetic-frame tests: the recorder records and ends; it refuses a player seat; the hand path
  gets all 7 plays across both sides exactly (troop, evo, hero deck flag, Rocket target, rolling Log, Tornado effect, drill
  follow); the body path works with hidden hands; and the output loads in `research/sandbox_tools/replay_drive.py`
  (`load_battle`, `deck_for_side`, `infer_deals` finds a legal hand cycle).
- `validate_live.py` → `validation_live.json`: the converter graded on our own recorded live matches.

### Converter accuracy on our own live matches (a)

The test covers 60 finished live matches from 2026-10-08 00:30–19:45 (several decks), with 2,512 confirmed own plays as truth.
The logs keep only public bodies per frame (no hands, no projectiles, no `category`; the generation is emulated from
address reuse).

| metric | result |
|---|---|
| body path, card and tick within 5 ticks (bodies, n=1,919) | **99.79 %** (tick error p50/p90 = 0/0) |
| body path precision (detections of my side that match a confirmed play) | **100 %** of 1,941 |
| body path, cell within 1 tile of the intended cell (matched plays) | **99.74 %** |
| hand path, located (bodies) | **99.74 %**; within 1 tile **99.74 %**, or 99.90 % excluding 4 plays the GAME moved (live err_tiles 2.0, building overlap) |
| spells (n=593: Log 312, Tornado 161, Rocket 79, Goblin Barrel 26, Snowball 15) | **not measurable here**: the logs hold no projectiles/effects. Only the Goblin Barrel shows, through its goblins, 57 ticks late (26/26) |

Notes:
- Misses (4 bodies): Skeletons / Skeleton Army / X-Bow bodies that the 100 ms log never captured.
- Fixed while measuring: reused addresses (key on card_id too), and the Goblin Drill first seen at the king tower (19–22 tiles
  off, 1/10 still 1.25 tiles off after the fix). Miner is untested (it was never in our decks).
- Caveat: the truth tick is the frame where our hand rotated, and the bodies are born on that same frame, so tick error 0 is
  partly by construction. The hand path's card and tick need no proof (it is live_play's own confirmation rule). Its
  spell positions rest on the L70 Rocket/Tornado evidence, not on this test.

## 4. Navigation plan (no taps now)

Dry run: `nav_dryrun.py --png …` classifies saved screens offline. `nav_dryrun.py --device` takes read-only screencaps every 2 s while the owner
navigates by hand. It runs `ladder_nav.Classifier` and `friend_nav.Classifier`, prints the step and the tap the future navigator
WOULD make, and saves every unknown screen for template cutting. It was checked offline on `fixtures/content_update.png`, which it classified as `content_update`.

| step | screen (how it is recognised) | action |
|---|---|---|
| 1 | `main` (ladder_nav `battle` template; exists) | tap the TV Royale entry. The button and its location are **to measure** (menu button / Social tab / Battle tab) |
| 2 | `tv_list` (**new template**) | open the channel dropdown once |
| 3 | `tv_channels` (**new**) | tap the highest Ranked league channel |
| 4 | `tv_list` | tap the first replay row that is not grey (grey = watched; a saturation test like ladder_nav `green_buttons`) |
| 5 | `loading` (ladder_nav `logo`) | wait |
| 6 | in replay: **reader**, not screen (`battle_active` + both hands visible) | `recorder.py`, no taps; optionally tap speed-up if it exists (allowlisted point, **to measure**) |
| 7 | end screen (**new**, or ladder_nav `results_ok` if it matches) | tap OK/back to return to `tv_list`; loop to 4; when no grey-free rows remain, wait for the hourly replay or change channel |
| any | `popup_x` / `conn_lost` / `content_update` | ladder_nav rules: red X / STOP / STOP |

Taps would use an allowlist of rectangles like `ladder_nav.TARGETS` / `FORBIDDEN` (never the Shop tab, never "copy deck", never a
player profile).

## 5. Device feasibility test (~15 min, owner OK first; nothing else using adb)

1. (3 min) `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/nav_dryrun.py --device --every 2 --seconds 180`.
   While it runs, navigate by hand: main → TV Royale → channel list → highest Ranked channel → replay list. Screens land in
   `icebow/data/replay_rec/screens/` and become the templates.
2. (6–8 min) Start one replay by hand, then run `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/feasibility.py`.
   It records with no taps until the battle ends (10 min cap) and then converts. If speed controls exist, try 2x for part
   of it.
3. (2 min) Read the printout:
   - `active` > 0 and no `failure` other than `none` → the reader resolves replays;
   - `seats.spectator` is most frames → hand path (exact cards/ticks for both sides);
   - `ticks_per_s` (20 = real time; above 20 = speed-up works);
   - `applied_replay_tick_minus_tick`;
   - `projectiles_seen` > 0;
   - plays and positioned counts per side, and both decks read.
4. If `active` = 0 or it refuses: send the recording file to the lead. The replay viewer's battle object path differs from
   live, and that is a reader reverse-engineering task, not a converter one.
   Pass = the reader resolves; both sides have plays and decks; ≥ 90 % of plays are positioned.
   Rerun the conversion offline later with `convert.py REC.jsonl`, or check it with `feasibility.py --recording REC.jsonl`.

## 6. Harvest build (lead ticket 2026-10-08 evening; no device command run by this worker)

**Converter fixes from the device recording (a):**
- A slot that leaves a card, to -1 or to another card, is the play, timed at that frame. The refill from -1 to a card is
  not a play. Before this fix, the play frame showed the emptied slot as the deck's last card, so 7 of 123 play rows held
  a hand without the played card.
- When two plays land in one sample, they are ordered by their place in the reader's cycle.
- New `convert.cycle_check`: it drives the first frame's hand and queue through the detected plays and compares the result
  with the reader on every frame. Device replay: **0 and 0 of 763 frames differ** on the two sides. So every play was
  found, none was invented, and the order is right.
- `replay_drive.offline_report` on the converted CSV now finds a legal hand cycle for both sides (256 deals each). Before
  the ordering fix, side 1 had 0.

**Dataset bridge (3):** `to_record.py` writes the recording in the engine re-drive's own `replay_*.json` schema
(frames / play_frames / log / final_decks, `record_native` and `record_full`). So
`dataset_gen --corpus DIR --feature-version 4` builds rows from the **real** game states, with no VM and no engine.
- The device replay gives 342 rows: 45 + 78 play rows and 119 + 100 wait rows. Every play row has its card in the
  actor's own hand, and the labels are on the board.
- Public-only proof (`test_to_record.py`): scrambling one side's hand, next card, elixir and log `hand_before` leaves
  every array of the **other** side's rows byte-identical, on the synthetic battle and on the device replay. The scramble
  does change the scrambled side's own rows.
- Play frames carry only the actor's player block. The opponent's elixir column is the public estimate (dataset_gen fv4).
- The CSV route still works too: `harvest` writes `OUT/crawl/` in the crawl2 schema for the VM re-drive, and
  `replay_drive.load_battle`, `deck_for_side` and `infer_deals` pass on it.

**Navigator (1):**
- `tv_templates.py` cuts the templates into `icebow/data/replay_rec/templates/`.
- `tv_nav.py` holds the Classifier, the pure `decide()` and the tap allowlist.
- `harvest.py` runs the loop. `--dry-run` sends no taps and makes no recording. It stops on any screen it does not know
  for 20 s, on conn_lost / content_update, and on any tap outside its rectangle.
- Templates built so far, from the 10-08 captures: `rp_close`, `rp_pause`, `spd_x1`, `spd_x05`, `spd_x4` and `rp_rewind`.
  They classify every capture correctly: 6 of 6 controls screens with the right speed label, and 104 others (live battle,
  replay with the controls hidden, end screens) as unknown.
- **Missing: the TV Royale menu screens were never saved.** The old dry run kept only `unknown` screens, and ladder_nav
  calls any screen with a red X `popup_x`. `nav_dryrun.py --device` now saves every capture as `<class>_<HHMMSS>.png`.
  `harvest.py` refuses a real run until `tv_nav.missing_templates()` is empty:
  - `tv_entry`, `tv_list_hdr`, `tv_channel_btn`, `tv_channels_hdr`, `tvch_ultimate_champion`, `tv_row_play`, `rp_exit`.
- **Capture pass (~3 min, lead OK + owner):** run `nav_dryrun.py --device --every 1 --seconds 180`. Walk main → TV Royale →
  channel list → Ultimate Champion → replay list (with one row grey) → start a replay → let it end → leave the end
  screen. Then add the SPEC rows in `tv_templates.py` and run `tv_templates.py --check`.
- Speed: tap the speed button (shown by tapping the arena) until the label reads x4, at most 5 taps. The reader's tick
  rate (≥ 60/s) confirms it. The cycle seen: x1 → x0.5 → … x4. The x2 label was never captured.

**Harvest (2):** `harvest.py` works one channel at a time, in the order Ultimate Champion → Royal → Grand → Champion →
Master III/II/I → top arena (`tv_nav.CHANNELS`).
- On a channel it takes the first replay row that is not grey; the game greys watched replays itself.
- The recorder opens BEFORE the row is tapped, so the replay is recorded from tick 0.
- At replay end it runs convert, the checks, the dedupe, `to_record`, and appends a manifest row.
- A replay is rejected when:
  - the hands are hidden;
  - a deck is not 8 cards;
  - a side has fewer than 5 plays;
  - less than 90 % of a side's plays are positioned;
  - the first tick is above 200;
  - `cycle_check` shows any mismatch;
  - or it is a duplicate: same decks and ≥ 80 % of plays matching on side, card and a tick within 16.
- Offline: `harvest.py --process REC.jsonl`. The device replay gets `rejected: started_late:381`, because the owner
  started the recorder after the replay; every other check passes.
- Tests: `test_harvest.py`, 7 tests (process accept / duplicate / late / played-in; dedupe jitter; the full decide cycle
  with every tap allowlisted; stops; a dry run that never taps; ReaderPump recording one replay; the classifier on the
  device captures).

**Throughput (4):**
- (a) Device recording: 4x ran at 73.1 game ticks/s.
- (a) Crawl battle length, last-play tick over 2,050 replays: mean 4,731, median 4,931, p90 5,957 ticks.
- So the replay itself takes about **65–70 s at 4x** (p90 about 85 s).
- (b) Navigation per replay: VS/loading about 4 s (10-08 captures), plus speed taps 1–3 s, plus exit and back to the list
  5–10 s, about 15–20 s in all. That is **about 85–90 s per replay, roughly 40 replays an hour**.
- (a/b) Supply: TV Royale adds 1 replay per channel per hour and keeps each for 24 h (wiki), so **at most 24 new per
  channel per day**. The top 4 Ranked channels give at most about 96 high-skill replays a day, about 2.5 h of
  emulator time.
- The owner sees "hundreds" across all arena and rank channels. How many are viable after the checks (meme or upset
  picks, draws) is unmeasured, and so is the exact number of Ranked channels.
