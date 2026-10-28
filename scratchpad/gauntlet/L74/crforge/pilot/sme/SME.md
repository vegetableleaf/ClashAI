# crforge SME test 1: the 10-26 replay-recorded match (ticket A2b-3, plan1026 Pillar 1, Stage 1), 2026-10-27

Labels: **(a)** measured here (number + file), **(b)** plausible but untested, **(c)** contradicted.
Engine: crforge `ad8ef3a` on pod 33920, JDK 17, tables 16.402.22. Pod work dir: `/workspace/pilot/sme`.
Ground truth: replay recording `icebow/data/replay_rec/rec_20261026_130926.jsonl` (sha256 `cf60bb2c…f9f8b`), 2,068
in-battle reader frames on distinct ticks, tick 0 to 4136. Secondary: the live client's own P3 capture of the same
match, `icebow/data/p3_captures/live_play_20261026_130453/frames.jsonl` (2,004 frames, board only).

## Verdict
- **Strict SME: FAIL for both seed candidates (a).** No candidate matches every reader frame.
- **Candidate A (s3 = -1462933474, seed 2032924539): 2,065 / 2,068 frames exact (0.99855) (a).**
  - Every unit, tower, projectile and area effect matches: side, x, y and HP exactly.
  - Both sides' elixir match to 1e-4, and both hands and queues match.
  - The 3 frames that are not exact are reader reads that straddle a game step, measured below. **No engine divergence
    is seen in this match under seed A (a, for 1 match).**
  - P3 (live client) frames: 2,003 / 2,004 board-exact (a).
- **Candidate B (s3 = -1043283422): 2,044 / 2,068 (a).** It fails on all 3 of the match's Princess volleys
  (21 frames): the decorative arrows spread differently, by 2 to 100 game units.
  - **So the seed is identified: A (a).** This is the first G1 "trace check" (CRFORGE_S0.md, Route 2) to work, on 1 match.
- **The two seeds of each s3 give the same board trace (a).** The traces are identical line for line apart from an
  object hash printed in the ability outcome. That fits the G1 model: the seed only matters through s3.
- **Planted bug (a): 1 HP off one unit fails.** One Ice Spirit is set 1 HP low at tick 198. The exact frames drop
  2,065 to 2,064, and the first divergence becomes tick 198 with `dHP = -1`. A 1e-4 elixir change and a 1-HP change
  also fail in `sme.py selftest`.

## Inputs (what crforge was given)
| input | value | source |
|---|---|---|
| decks, slot order | side 0 (opponent #Y2PR8YLG9): GoblinBarrel, Valkyrie, SkeletonArmy, Wallbreakers, Princess, BlowdartGoblin, IceSpirits, Cannon. Side 1 (us): Knight, IceWizard, Tesla, Log, Xbow, Rocket, Tornado, Skeletons | recording tick 0 `deck_card_ids`, mapped to names via the tables |
| slot flags | both sides [1,2,1,0,0,0,0,0]: evolution slots 0 and 2, hero slot 1 | recording `deck_form_flags` |
| card levels (crforge counts from 1) | all 16, except the opponent's Ice Spirit at 15 | battle log 20261026T170813Z: API Ice Spirit 15/16, every other card at max |
| towers | Princess towers, king 16, princess 16 | recording tick 0: 7,728 / 4,858 on both sides |
| account words | side 0: 29372692, side 1: 83616782 | `seeds/jobs/rec1026_std.txt` |
| player-data draws | 2 x `addPlayerData(1)` | `ReplayBattle.build` |
| seed | A: 2032924539 (or -2060719996). B: -2064661162 (or 2028985001) | `seeds/results/rec1026_std.out` |
| commands | 72 plays + 3 hero abilities (1 ours, 2 opponent). Each runs at `run`, given at `run - 20` (crforge's only legal delay) | recovered from the recording, below |

**Unit mapping, verified on tick 0 (a).**
- Reader x/y equal crforge x/y: game units, 1 tile = 1000, side 0 at the bottom. The 6 towers match in position and
  HP: kings (9000, 3000) and (9000, 29000), princess towers (3500/14500, 6500/25500).
- Reader `elixir_raw` = crforge `MatchSide.elixir` (1/10000): 60000 on both sides at tick 0. Regen is 178 per tick,
  then 357 per tick in double elixir: the same in both.
- `hand_deck_indices` = `Hand.slots()` and `cycle_deck_indices` = `Hand.queue()`. Tick 0 deals: side 0
  [2,7,1,6] + [3,5,0,4], side 1 [5,3,7,0] + [6,2,4,1], the same in both.
- **Ticks:** reader frame `game_tick = g` equals crforge observation line `t = g`, the state before step g runs. A play
  with run tick R is first visible at line R + 1. Check: the Ice Spirit run at 197 shows at 198 in both, with elixir
  85244 in both.

**Command recovery (a): `sme.py fit` + `polish`, logs in `results/fitA_fit_log.jsonl`.**
- **A play** is a deck index leaving a hand slot between two frames t_prev < t. A slot reading -1 while the next card
  arrives is not a play; the first version counted those wrongly, and that was fixed.
- **An ability** is an elixir drop with the hand unchanged. The unit it names is the side's latest hero play,
  `cmdK_0` (unit index 0 in all 3 cases).
- **Point:** the new objects' anchor at t: the spell projectile's target, the area effect's centre, or the centroid of
  the new units.
  - **All 72 recovered points equal the anchor, rounded (a).**
  - A search over the 25 points of the 500-unit grid around each anchor was available, and none of it was needed.
- **Run tick:** a search over R in [t_prev, t] (2-3 options), scored on the frames from t_prev to t+20.
  - Exact ties are re-scored on frames up to t+120.
  - Then a greedy pass moves one R by ±1 inside its interval when the whole-match mismatch falls. It made 1 move:
    the Ice Spirit at 3732 went to 3731.
  - Chosen R - t_prev: 0 for 30 commands, 1 for 44, 2 for 1.
- All 72 plays were placed (match code 0), and the 3 abilities ran with outcome code 0.
- **The inputs do not depend on the seed (a).** A and B were fitted separately and gave identical command lists.

## The comparator (`sme.py`: `canon_rec` / `canon_sim` / `diff`)
Each recorded frame is checked against the crforge observation for the same tick. A frame is exact only if all of the
following hold, with no tolerance:
- the multisets of towers (side, x, y, hp), units (side, x, y, hp), projectiles (side, x, y) and area effects
  (side, x, y) are equal;
- each side's (elixir, hand, queue) is equal.

Each unmatched object is paired with the nearest object of the same side, which gives (dx, dy, dHP). A frame that
equals the sim one or two ticks off is classified `frame_label_shift`; strict SME still counts it as a failure.
Card identity is not compared, because reader card ids and crforge row names have no shared key. Within an exact frame,
a swapped identity would also need identical HP and position (b).

## Per-candidate result (`results/pol{A,B}_score.json`, frame lists in `results/pol{A,B}_score_frames.jsonl`)
| | A | B |
|---|---:|---:|
| recorded frames | 2,068 | 2,068 |
| exact frames | **2,065 (0.99855)** | 2,044 (0.98839) |
| side 1 (ours) elixir + hand exact | 2,065 | 2,065 |
| first non-exact frame | 682 (whole frame = sim 683) | 682 |
| first divergence not a pure label shift | 3040 (reader torn read, below) | **971: Princess volley 1, deco arrows dx/dy 2-11 units** |
| Princess volleys exact (3 in the match: 971, 1513, 3807) | 3 / 3 | 0 / 3 |
| P3 live frames, board exact | 2,003 / 2,004 | 1,982 / 2,004 |
| SME pass | no (3 frames) | no (24 frames) |

## Divergence census, candidate A: all 3 non-exact frames are reads across a game step (a: `tornck.py`)
Each recorded object was checked against every sim tick from t-2 to t+2.

| frame | what it is | evidence |
|---|---|---|
| 682 | mislabelled: it is tick 683 | all 16 objects and both sides' elixir/hand equal sim 683; sim 682 differs (Tesla HP 606 vs 602, princess tower 4858 vs 4658) |
| 3040 | read during step 3041 | 21 moving objects and both elixirs equal only sim 3041. One X-Bow bolt that sim 3041 holds is missing: created later in the step than the read (b) |
| 3044 | torn between ticks 3044 and 3045 | 7 objects match only sim 3044, 15 only sim 3045; side 1's hand/elixir match neither |
| (P3) 2799 | read during a step | 1 unit (HP 101) and 1 projectile of sim 2799 are absent; every other object matches |

- Frames 3043 and 3047 on either side of these are exact. That rules out an engine state divergence through them,
  since the engine is deterministic (a).
- **Whether the reader flags these frames: no (a).** Every frame carries `applied_replay_tick = -1`, and `read_us` does
  not separate them (586 / 698 / 2,046 µs, against a p50 of 665).
- So by the plan's definition, which excludes only frames the reader flags itself, these 3 frames count as failures.
- **Fix (b):** read `game_tick` again after each frame and flag the frame when it changed. Under candidate A, with
  that flag, this match would pass SME (2,065 / 2,065 unflagged frames).

## Mechanisms that diverge
- **Engine (crforge): none seen in this match under seed A (a).** That covers 72 plays and 3 hero abilities, including:
  - evolved bodies of Knight (2), Tesla (1) and Skeleton Army (1 play, 15 bodies);
  - hero Ice Wizard and hero Valkyrie with their abilities;
  - Princess random volleys, X-Bow, Tesla, Log, Tornado, Goblin Barrel and Wall Breakers;
  - double elixir and overtime to tick 4136.
  - Not covered: Rocket was never played in this match, so it is untested here.
- **Seed:** only the Princess deco-arrow spread depends on it (a). Under seed B the volleys diverge and then heal.
  Every other frame of B is identical to A.
- **Reader:** 3 / 2,068 recorded frames (0.15%) and 1 / 2,004 P3 frames are torn or mislabelled reads.
- **Earlier "divergences" that were input errors (c, contradicted as engine faults).** History: `results/v1_fitA_score.json`, `v2_fitA_score.json`.
  - **v2: the first divergence was tick 1511, and 1,479 / 2,067 frames were exact.** In v2 the Princess and the Tesla
    were each fitted 1 tick early (1481 and 1505). The Princess then fired at the fresh Tesla 1 tick early, the
    error spread for about 100 frames, then healed. With the R tie-break (1482 and 1506) the frames become exact.
  - **The 3065-4134 run in v2 was also an input error.** The Knight was fitted at 3043 because the torn frame 3044
    pointed there; at 3044 it is exact.
  - **v3: the Ice Spirit's jump at 3755 came 1 tick early.** The unit stands still while it deploys, so the frames
    cannot place R within the 2-tick gap; whole-match scoring moved it to 3731.
  - Lesson for the extractor (A2b-1): **a 1-tick error in one play's run tick can cost about 100 frames.**

## Caveats
- **Run ticks are fitted inside the observed window (b).** The recording has a frame about every 2 ticks, so
  each R is chosen from 2-3 ticks, every one of them consistent with the frames.
  - So a 1-tick deploy-timing error on one card form cannot be told apart from input timing on this one match.
  - A systematic offset would push R to one end of each window. The split of 30 / 44 / 1 does not show that.
  - The replay's own command stream (`cmd.t2`, the run tick), which this recording does not hold, would settle it.
- **The packed item (`pd`) was not checked.** The recording does not hold it. Evolution is crforge's own count, and it
  matched every evolved body (the frames are exact) (a).
- **Sample size: this is 1 match.** The plan's target (95% lower bound ≥ 0.999) needs about 2,996 clean matches, and
  D1's SME pilot needs 45/50. This match is in the RNG stratum, and it passed every frame that is not a torn read.

## Reproduce (pod 33920; `L=/workspace/crforge/env/build/install/env/lib`)
```
cd /workspace/pilot/sme && javac -d build -cp "$L/*" SmeRun.java && python3 sme.py selftest
python3 sme.py fit    --rec data/rec.jsonl --p3 data/p3.jsonl --seed 2032924539 --out fitA      # ~8 min, 24 threads
python3 sme.py polish --rec data/rec.jsonl --p3 data/p3.jsonl --plan fitA/plan.json --out polA
python3 sme.py score  --rec data/rec.jsonl --p3 data/p3.jsonl --plan polA/plan.json --out polA
python3 sme.py score  --rec data/rec.jsonl --plan polA/plan.json --out polA --perturb             # must fail
python3 onsets.py polA/score_frames.jsonl; python3 tornck.py polA/full/o0.jsonl data/rec.jsonl 3044
```
`data/rec.jsonl` and `data/p3.jsonl` are copies of the two ground-truth files (shas above); they are not committed.

## Files
- `SmeRun.java`: the threaded batch driver. It builds the battle as `ReplayBattle.build` does and dumps every tick.
- `sme.py`: fit / polish / score / selftest.
- Helpers: `inspect.py`, `onsets.py`, `shiftcheck.py`, `tornck.py`, `variant.py`, `inputs_summary.py`, `showfit.py`,
  `cover.py` (replay vs P3: 1,098 / 1,099 shared ticks give equal entity sets).
- `results/`: plans, fit logs, scores, per-frame diffs, the planted-bug runs, the polish moves, and the v1/v2 scores.
- Pod only: the full sim traces, `/workspace/pilot/sme/pol{A,B}/full/o0.jsonl`, about 12 MB each.

---

# SME on live-log matches (ticket A2b-3b), 2026-10-27

Inputs:
- A2b-1's `inputs_rngfree.jsonl` (pod `/workspace/pilot/inputs`, sha256 `ca766522…`): 138 RNG-free post-10-19 Ranked
  matches, 109 of them unflagged. It was used read-only.
- Each match's live log (`L68/live_reader`), turned into reader frames by `live_frames.py`. A frame gives the board,
  our elixir, and our hand at decision ticks; the queue is never observed.

Work dir: pod 33920 `/workspace/pilot/sme_live`, runs `run2` (raw comparator) and `run3` (with the
representation map). Results: `results/live/`.

## Verdict
- **D1 "SME pilot" row: FAIL.** Only **13 / 109** unflagged matches (13 / 138 all) are exact apart from torn frames
  (a). The target is 45 / 50, and 13 / 109 is about 6 / 50.
- **The failures' first divergences fall in 11 mechanism classes plus 1 crforge refusal, not ≤ 5 (a, coarse rules in
  `agg_live.py mech()`).**
  - Most onsets are transient: 437 of 521 episodes heal; median 2 episodes per failing match.
  - Still, 84 of 136 scored matches end in a divergence that never heals.
- **The comparator and frames are sound on live data (a).** The 10-26 match's live-log frames, scored against the
  replay-fitted plan (seed A), are exact on **1,983 / 1,983** frames, our elixir and hand included. So the
  live-side failures come from inputs or the engine, not from the frame conversion.

## Method (`sme_live.py`)
1. **Plan** from the A2b-1 record: decks, levels, slot flags, towers (spawn group + levels) and words.
   - Seed 1: the match is RNG-free, so nothing draws after the deal.
   - Both deals are forced with `Hand.rearrange`: ours from the log, the opponent's = A2b-1's `opp_deal_fit`.
   - Commands sit at the extractor's `tick` and point, with given = run - 20.
   - An ability names the side's latest play of its card, `cmdK_0`. If that play was refused, the ability is
     dropped and logged.
2. **Repair (inputs only).** Episode by episode: at each divergence onset d, every command run in [d-120, d] tries
   - the other run ticks of its extracted window [lo, hi], and
   - for opponent plays only (our taps are exact, A2b-1 37/37), the 8 points 500 units around its point.

   The variant that moves the first divergence latest is kept. An onset nothing fixes is given up and the next
   onset is tried, up to 40 rounds.
3. **Score:** every live frame is one of:
   - exact;
   - `torn_t1`: the whole frame equals sim t+1;
   - `torn_mixed`: an isolated frame whose every object is held by sim t or t+1;
   - div.

   The first true divergence is the first div frame.
4. **Representation map (`repr_v1.json`, run3 only).**
   - Dropped: crforge characters without hit points. They had no recorded object at their point at any run2 onset:
     SkeletonContainerNew 44, RageBarbarianBottle 21, BalloonHero_Bomb 13, BombTowerBomb 7, GiantSkeletonBomb 5,
     MightyMinerBomb 4, BalloonBomb 3, RageBarbarianBottleEvo 3, Musketeer_hero_DummyBuilding 1.
   - Remapped: RageBottle counts as an area effect; it sat on the reader's Rage effect 8 / 8 times.
   - Effect: D1 moved only from 12 to 13. Numbers below are run3 unless marked.

## Opponent deal (a)
- Scoring each deal is not needed. **336 / 336** alternative fitting deal classes (3 per match: other initial hand
  sets and queue orders) gave a sim trace identical on every tick, board and our side, to A2b-1's deal.
- So in crforge only legality depends on the opponent's deal, and taking the best deal equals taking any deal.
- **The 29 flagged matches fail as expected (25 `opp_no_fitting_deal`, 4 `own_cycle_fail`).** For the
  no-fitting-deal ones, the default deal makes the match refuse opponent plays, so their bodies are missing.
  - The 9 scored matches with an exact share under 0.05 are all `opp_no_fitting_deal`.
  - That includes `live_play_20261026_090406` (0.000) and `live_play_20261026_203234` (0.000).

## Totals (run3)
| | value |
|---|---:|
| matches scored / crforge refused the input | 136 / 2 (GoblinDrill evo after a refused play: "not modelled") |
| live frames | 293,942 |
| exact frames | 171,677 (0.584) |
| per-match exact share | min 0.000, p25 0.168, median 0.603, p75 0.966, max 1.000 |
| torn frames (reader) | 132 in 52 matches: 28 `torn_t1` + 104 `torn_mixed` |
| first true divergence tick | median 720 (p25 413, p75 1682) |
| matches exact apart from torn frames | 13 / 138; **13 / 109 unflagged** |

The per-match rows are in `results/live/run3_table.tsv`. Columns: frames, exact share, torn_t1, torn_mixed, div frames,
first true divergence tick, its quantity and card, repair rounds, kept offsets and refused plays. Episode details
are in `run3_results.jsonl`.

## First true divergence of the 96 failing unflagged matches (`d1_live.py`)
| n | mechanism (rule) | label |
|---:|---|---|
| 32 | body position: the same body, off by \|dx\|+\|dy\| ≤ 10 (4), ≤ 100 (16), ≤ 500 (11), > 500 (1) | (b) movement, collision or targeting; mostly hero Valkyrie, hero Ice Wizard, Graveyard skeletons, Knight, Golden Knight |
| 15 | our live elixir is a whole card cost lower than the sim for 1 frame (13158 vs 23158) | (b) live client: our own elixir drops 1 tick before crforge's step. The replay shows the battle agreeing with crforge (a), so this is a live-client view, not the battle |
| 12 | Lightning: the reader shows a bolt projectile on the target with the HP not yet taken; crforge took it 1 tick earlier and has no bolt | (a) pattern; heals the next frame |
| 9 + 6 | HP only at the same points: sim more (9) or less/mixed (6) damage; often periodic (Earthquake: tower -72, X-Bow -416 every 20 ticks) | (b) hit / pulse timing 1 tick early in crforge |
| 8 | a recorded body with no sim body near | (b) a play missed or late in the extraction, or a unit crforge did not make |
| 4 + 3 + 3 + 2 | projectile-only; Earthquake pulse; other spell effects (Poison / Freeze / Rage / Tornado); area-effect start/end | (b) timing |
| 1 + 1 | a sim body the reader lacks; crforge refused the input | |

All 12 classes, across all 521 described episodes, with healed counts: `results/live/run3_summary.json` `mechanisms`.

The reader-side torn reads (132 frames) are already excluded. What-if: excluding also the live own-elixir class
and the three spell-timing classes would turn only 5 more failing matches into passes (18 / 109). **The large
classes are body movement and damage timing.**

## Over-fitting guard (a)
- **Kept run ticks never leave the extractor's window, by construction.**
  - Of 11,009 commands, 395 are kept at a tick other than the extractor's `tick`: +1 386, -1 8, and +71 for 1.
  - The +71 is a pre-log Goblin Barrel whose window is [0, 150].
- **Moved points:** opponent points were moved only where that delayed a divergence. `points_moved` is per match in
  `run3_results.jsonl`.
- **Probe outside the window (1-2 ticks past lo/hi, at the first 5 onsets of each match, never kept).**
  - 110 distinct commands in 61 matches would move an onset later.
  - By card: Lightning 27, abilities 21, Earthquake 20, Poison 11, Skeletons 7, Ice Wizard 7, Knight 6.
  - By offset: +1 for 118 variants, +2 for 77, -1 for 38, -2 for 4.
  - These spell windows are pinned by the spell's own first-seen object (A2b-1 phase-3 births), and the spell's
    objects themselves match. The out-of-window gain is the strike/pulse arriving 1 tick later, so this points
    at crforge's spell-hit timing rather than the extraction (b, untested).

## What this means for D1
- **The engine is not shown exact on live play.** The replay-recorded match had no Lightning, Earthquake, Poison or
  Graveyard (it had Log, Tornado, Princess, X-Bow and heroes). It was exact apart from torn reads, but on live
  matches these cards and body movement diverge in most matches.
- **Next measurements (b):**
  1. Record replays of matches with Lightning / Earthquake (CRFORGE_S0 §4 procedure). That splits "crforge 1 tick
     early" from "the live client 1 tick late", since the 10-26 replay showed no such offset.
  2. Diff the 32 body-position onsets against fin16 on the same inputs. Engine-specific or input-specific?
  3. A2b-1: the 29 flagged matches and the 8 missing-body onsets are extraction work.

## Files (A2b-3b)
- Scoring and repair: `sme_live.py` (fit + score + over-fit probe + deal check) and `live_frames.py` (live log to
  frames, laptop). `sme.py`'s `diff` now treats an unobserved hand/queue (`None`) as unknown.
- `SmeRun.java` additions: forced deals, tower spawn groups, Mirror plays and `skip` commands. A dropped ability keeps
  its index.
- Analysis: `agg_live.py` (census, `mech()` rules), `d1_live.py`, `stats_live.py`, `repr_stats.py`, `repr_v1.json`,
  `pos_census.py`, `shift_live.py`, `track_live.py`, `insp_live.py`, `find_eps.py`.
- Results: `results/live/run3_{summary.json,table.tsv,results.jsonl}` and `results/live/run2_summary.json`.
- Pod only: per-match plans `/workspace/pilot/sme_live/run{2,3}/<match>/plan.json`, plus the converted frames.

---

# Fix loop (ticket A2c)

Fork:
- Pod 33920 `/workspace/crforge_fork`, branch `clashbot-fix`, cut from the pin `ad8ef3a`. `/workspace/crforge` is not
  touched.
- Core tests on the fork, unmodified:
  `./gradlew :core:test -Pcrforge.cache=/workspace/crforge_cache -Pcrforge.assetSource=file:///workspace/crforge_cache/none`
  gives **2,140 tests, 0 failures, 0 errors, 2 skipped (a)**, as the plan expects.
- **No crforge patch was needed in round 1 (a, below).** The fork therefore equals the pin, and there is no patch
  file under `crforge/fork/`.

| round | mechanism | fix | unflagged matches exact apart from torn | exact frames (138 matches) | regressions |
|---|---|---|---:|---:|---|
| 0 (run3) | | | 13 / 109 | 171,677 | |
| 1a (run4) | Lightning + Earthquake + Poison timing | input: fx-dated spell casts +1 run tick (every fx spell card) | 16 / 109 | 187,945 | **1**: `live_play_20261026_100756`. Its Zap is gap-dated, not countdown-dated |
| **1 (run5)** | the same | input: +1 run tick only on countdown-dated casts (`lo = hi`) of fx spell cards | **17 / 109** | **188,233** | **0** (13 exact stay exact; +4) |

## Round 1: Lightning "strike 1 tick early, no bolt"
The cause is the input dating, not crforge (a). The A2b-3b reading "crforge strikes early" is **(c) contradicted**.

**Measurements on run3 (`bolt_check.py`, `aeo_check.py`), recorded frame at the sim's tick + k:**

| object | k = -1 | k = 0 | k = +1 | k = +2 |
|---|---:|---:|---:|---:|
| Lightning bolt shown | 0/97 | 0/74 | **81/100** | 0/74 |
| struck target's hp already reduced | | | | 38/38 (always) |
| Lightning area effect present, at its first sim line + k | | 1/30 | **38/38** | |
| Lightning area effect present, at its last sim line + k | | | **31/31** | 0/39 |
| Earthquake area effect present, at its first sim line + k | | 0/32 | **30/30** | |

**The whole cast is 1 tick late, not just the strike.**
- The area effect starts and ends late too. An early strike alone would shift only the bolt.
- So the run tick crforge was given is 1 too early.

**The source of the early run tick:**
- `fights.seen_casts` (A2b-1's extractor) dates an area-effect spell from its countdown with RoyaleSim's rule:
  `made = first - (life - remaining)/50`, run = `made - 1`. RoyaleSim makes the area the tick after the command.
- crforge makes it in the command's own step. `BattleWorld.castSpell` creates it in the command pass, and the
  opening cleanup admits it, so it shows at line R+1 with one 50 ms update spent.
- So for crforge, run = `made`. Probe: Lightning, Earthquake, Poison and Tornado all show at R+1, the bolt at R+11.
- The extractor already has this +1 for Tornado (`PULL_AREAS` lag). That is why Tornado and Log, the
  `SpellAsDeploy` spells, were exact on the 10-26 replay.
- The 10-26 recording has no Lightning, so the live frames are the only evidence here.

**The fix, in my write set (`sme_live.plan_from`, `SME_FX_SHIFT=1`).**
- It applies to countdown-dated `spell_seen` plays (`lo = hi`) of every spell card made by an area effect alone:
  no projectile, not `SpellAsDeploy`, no summoned unit. That covers Lightning 84, Poison 80, Earthquake 62, Vines 26,
  Graveyard 24, Freeze 16, Clone 8, DarkMagic 3, GoblinCurse 1.
- Gap-dated Zaps keep their window.
- **For A2b-1:** the same +1 belongs in `seen_casts` for crforge (b, a one-line change; it is not mine to edit).

**After round 1 (run5, a):**
- Lightning bolt at k=0 98/100 (k=±1 0/76); hp reduced at +1 39/39. Area effect start 38/38 at k=0 (k=-1 1/31),
  end k=0 32/32, k=+1 0/39.
- Poison start and end aligned the same way.
- The "Lightning strike timing" class went from 57 onsets to 0 and "Earthquake pulse timing" from 20 to 0.
- The over-fit probe no longer lists any spell: before, Lightning 27, Earthquake 20, Poison 11. Now abilities 27,
  Skeletons 11, Ice Wizard 10, Knight 9 (59 commands).
- Rescored all 138 matches. The 50 unflagged matches with a shifted cast went from 0 exact to 4; the other 59
  unflagged stayed at 13 exact.
- Kept run ticks other than the extractor's: 446 of about 11,000 commands, +1 for 435, -1 for 10, +71 for 1
  (the pre-log Goblin Barrel). All are inside the windows, the shifted spell windows included.

## Item (2): Earthquake and the damage-timing class
**Earthquake needs no crforge change (a).**
- Its start came right with round 1.
- At its end, the counts of Earthquake effects at the point (Earthquake 3,000 ms plus EarthquakeHiddenDamage
  3,050 ms; the reader shows both as card 28000014) agree on 216 of 218 boundary frames (`eq_count.py`).

**The remaining 14 "hp only" first divergences (run5) split three ways (b, from the onset details):**

| n | what it is | likely side |
|---:|---|---|
| 6 | the reader shows hp -1 for an evolved Witch, evolved Bats or the hero Tombstone visual dummy, while the sim has its hp | reader |
| 4 | an Ice Golem hero's death area: the sim has 110 more damage on the bodies around it, and the area is 50 units off the reader's IceGolemite effect | **crforge candidate for round 2** |
| 4 | one X-Bow / tower hit lands a tick apart (rec ±306 to 429 hp) | unknown |

**Not fixed in this round.** The plan says one mechanism per fix, and these are three. The Ice Golem hero death area
is the first one with evidence pointing at crforge.

## Item (3): body-position dossier, top 10 (earliest onsets of the 32 run3 cases; no fix)
Sources: `results/live/dossier_body_position_top10.txt` (`dossier.py`, `dossier_abil.py`).

| match | body | play (source) | creation → first offset | offset over time | at the onset |
|---|---|---|---|---|---|
| 20261027_033729 | hero Valkyrie, opp | first_seen 217 | 218 → 307 (+89) | 5 → 300 in 8 frames, then holds ~300 | Valkyrie ability cmd at 307 (window 307-308) |
| 20261026_184912 | Golden Knight, opp | first_seen 292 | 293 → 413 (+120) | grows ~120/frame to 1,121 (a dash), then the twin is lost | no ability command |
| 20261026_212917 | Golden Knight, opp | first_seen 372 | 373 → 454 (+81) | jumps to 1,094 / 378, then constant | no ability command |
| 20261026_085635 | Golden Knight, opp | first_seen 265 | 266 → 515 (+249) | 707 two frames later | no ability command |
| 20261026_162012 | hero Valkyrie, opp | first_seen 297 | 298 → 517 (+219) | to -269 in 3 frames, back to -150 | Valkyrie ability at 519 (519-520) |
| 20261026_144615 | hero Valkyrie, opp | first_seen 441 | 442 → 534 (+92) | ≤150 for 7 frames, back to 0 at 548 (heals) | ValkyrieHero_AEO on her; ability at 532 |
| 20261027_022821 | hero Ice Wizard, ours | own_tap 448 | 449 → 540 (+91) | (-6, +7) holding | its floating cube at 0 distance |
| 20261027_011738 | hero Valkyrie, opp | first_seen 476 | 477 → 544 (+67) | ~110 then (57, -34) holding | ValkyrieHero_AEO on her; ability at 542 |
| 20261027_005727 | Knight, ours | own_tap 417 | 418 → 633 (+215) | (0, -9) holding | nothing within 1,200 |
| 20261027_001702 | hero Valkyrie, opp | first_seen 679 | 680 → 715 (+35) | grows to 935, then about 800 | no ability command |

**Readings:**
- **Not a deploy-point or deploy-tick error (a, 10/10).** Every body is exact from its creation for 35-249 ticks;
  none is off on its first frames.
- **8 of 10 are champion or hero bodies.**
  - **Hero Valkyrie (5):** 4 onsets fall on or 2 ticks after a Valkyrie ability command. That points at the
    ability: its `cast_seen` dating (2-tick window), or crforge's hero-Valkyrie ability motion (b). The over-fit
    probe's top class is abilities (27 commands that would be better outside their window), which fits either.
  - **Golden Knight (3):** no ability command anywhere near the onset, and the recorded body runs ahead about 120
    units a frame (a dash). `fights.seen_casts` says champions are not counted, so the Golden Knight's dash is
    never given to crforge.
- **Classification:**
  - Golden Knight: extraction (champion ability missing) (b, strong).
  - Hero Valkyrie: open between the ability's dating and crforge.
  - Our hero Ice Wizard (-6, +7 next to its floating cube) and our Knight (0, -9): small offsets 91 and 215 ticks
    after deploy. Collision or push (b).
- **Next measurement (b):**
  1. Add champion ability casts to the extractor.
  2. Re-run the over-fit probe on ability commands only, with a wider window (±3).
  3. If hero Valkyrie still moves wrong with the best ability tick, it is crforge's.

## Files (A2c)
- Spell-timing checks: `bolt_check.py`, `aeo_check.py`, `eq_count.py`.
- Dossier: `dossier.py`, `dossier_abil.py`.
- The `SME_FX_SHIFT` input correction in `sme_live.py`.
- Results: `results/live/run5_{summary.json,table.tsv,results.jsonl}` and
  `results/live/dossier_body_position_top10.txt`.
- Pod: run4 and run5 under `/workspace/pilot/sme_live/`; the fork under `/workspace/crforge_fork`.

## Extractor: round-1 dating in `extract.py` (a)
- **Change:** `extract.py` now gives a countdown-dated area-effect cast its `made` tick as its run tick
  (`dated: fx_made`).
- **Why not `fights.py`:** `fights.seen_casts` is left alone. RoyaleSim's made - 1 is right for RoyaleSim, and the
  parity harness shares that file.
- **Extractor test:** `test_extract.py` passes. It gives the same numbers as EXTRACT.md: us 37 matched / 36 in window /
  31 exact tick; opponent 35 / 35 / 30.
- **Agreement check (`agree_fx.py`):** on 5 Lightning / Earthquake / Poison / Zap matches, the re-extracted play ticks
  equal `SME_FX_SHIFT`'s 5 / 5. That includes the gap-dated Zap match, which stays unshifted.
- **Not re-batched:** the pod's `inputs_rngfree.jsonl` was not rebuilt, so the runs below still apply the shift in
  `sme_live`.

# Fix loop round 2

| sub-round | mechanism | change | exact apart from torn (unflagged) | exact frames | regressions |
|---|---|---|---:|---:|---|
| start (run5) | | | 17 / 109 | 188,233 | |
| 2.1 (run6) | live own elixir 1 frame early | comparator: a read inside the step's command pass counts as torn (`torn_cmd`) | **24 / 109** | 188,233 | 0 (+7) |
| 2.2 (run7) | Golden Knight ability never extracted | input: GK ability cast at each dash burst (`SME_GK=1`) | **25 / 109** | 197,203 | 0 (+1) |
| 2.3 (run8) | hero Ice Golem "death area" (110 extra damage) | input: drop a hero Ice Golem "cast" that is its death (`SME_GOLEM=1`) | **27 / 109** | 202,444 | 0 (+2) |
| 2.4 (run9) | reader hp -1 bodies | comparator: a recorded hp -1 is a placeholder, given the hp of the sim body at the same point (`SME_HP_PLACEHOLDER=1`) | **28 / 109** | 204,647 | 0 (+1) |

## 2.1: the live own-elixir class is a reader read in the middle of a step (a)
Source: `elixir_check.py` on run5, unflagged matches.

**What the recorded frame shows at the run tick R of each of our plays:**
- equal to the sim: 2,303;
- **lower by exactly the card's cost: 74 (3.1%)** (Skeletons 29, Ice Wizard 25, Knight 18, X-Bow 4, Tesla 3, Log 2);
- at R-1: equal 2,025, with 6 odd values;
- at R+1 and R+2: equal 1,910 and 2,319.

**In those 74 frames:**
- the board equals the sim at R exactly (no unit of the play yet);
- our elixir is the sim's at R minus the cost, without the step's regen;
- the next step reaches the sim's value by regen alone.

So the frame was read inside step R: after the command pass took the cost, before the regen and the spawn.
That is a torn read.

**What it is not:**
- **Not crforge's elixir model.** The elixir equals the sim at R+1 and R+2. The 10-26 match's live frames are
  1,983 / 1,983 exact. The replay agrees with crforge.
- **Not the extractor.** The unit appears at R+1 as the sim says, so R is right.
- **Not the new-client local apply (160635001's tap + ~10).**
  - Run - tap lags of the 74 early frames are 21-27 for 71 of them, the same as the 2,303 equal ones (mostly 22-24).
  - The drop sits on the battle's run tick, not 10 ticks after the tap.
  - All 138 matches are build 160402012.

**Comparator rule (`SME_TORN_CMD=1`, `cmd_pass_read`):**
- The frame's only differences are our elixir.
- The elixir is lower by whole elixir.
- The next tick reaches the sim by 178 or 357 regen alone.

40 frames are reclassified as `torn_cmd`; 4 own-elixir onsets with other arithmetic stay counted.

## 2.2: champion abilities and the hero Valkyrie dating
**Golden Knight (a).**
- The reader shows nothing for its cast: the phase-2 `ability` is `{pending 0, timer 0}` throughout, and
  `fights.seen_casts` skips champions.
- The cast does show as a dash. The body moves 300-640 units in 2 ticks, against a walk of about 55, in behaviour
  state 3, retargeting between hits (`live_play_20261026_212917` 454-458).
- **crforge probe:** `useAbility` at run 310 first moves the Golden Knight at line 312.
- **Rule (`gk_dashes`):** each dash burst (> 100 units a tick, first frame of a burst, one cast per 100 ticks) becomes
  an ability command. Its window is [previous frame - 1, burst frame - 2].
- **Result:**
  - `live_play_20261026_085635` becomes exact (183 → 1,765 exact frames).
  - `212917`: first divergence moves from 454 to 4,564.
  - `184912`: still diverges at 413, but heals (131 → 2,333 exact frames).
- **Other champions are not done here** (one mechanism per sub-round). Extracted ability counts on the 109 unflagged:
  Monk 19 / 20 plays, Mighty Miner 6 / 64; Archer Queen 0 / 23, Boss Bandit 0 / 21, Goblinstein 0 / 16.

**Hero Valkyrie dating is right; the delay is crforge's (b) (`valk_check.py`, run6, 33 clean casts).**
- The game's first hero-Valkyrie area is at R+2 on all 33.
- crforge's first `ValkyrieHero_AEO` is at R+2 on 24, but later on 9 (R+3 to R+25).
- So in 9 / 33 crforge starts the ability's spin late. That is a crforge candidate (the ability waiting on something,
  perhaps an attack in progress), not a dating fault.
- 31 more casts were not usable: an earlier area was already present.

## 2.3: the hero Ice Golem class is a misread cast, not crforge (a)
**The table is not the cause.** Read on the cached 16.402.22 tables (the fork uses the same):
- `IceGolemiteHero` has `Base: CHARACTER.IceGolemite`, its own `DeathAreaEffect: IceGolemiteHero_Death_Aeo`
  (slow) and `OnDeathAction: IceGolemiteDeathExplosion` (spawns `IceGolemiteDeathArea`, 33 base damage).
- crforge makes both at a hero golem's death, and so does the game. On the death explosion's victims, the recorded
  hp drops by crforge's drop in 6 cases; 11 show other drops and 1 none (`golem_check.py`).

**The extra 110 comes from a misread ability cast (`golem_onsets.py`, all 4 onsets).**
- The ability's `IceGolemiteHero_Damage_AEO` deals it: `HitSpeed` 1500, it follows the golem and stays after the
  golem dies. The "50 units off" area is that AEO, still following, against the reader's death area.
- In all 4 onsets an extracted `cast_seen` ability sits exactly 1 tick before the golem's death.
- At the onset the recorded frame holds exactly the 2 death areas, and later 1 (`Death_Aeo`, 1 s). It never holds the
  3-second ability areas.
- **Cause:** `seen_casts` dates an instant hero's cast from its ability area row (card 203000038). The hero golem's
  death areas carry the same card id.

**Measured:** 38 of the 45 hero Ice Golem "casts" on the 109 unflagged matches are its death. The golem body is
present at the last frame ≤ R and absent at the first frame ≥ R+2.

**Rule (`golem_death_cast`):** those casts are dropped. The fix belongs in `seen_casts` / A2b-1; not edited
here (`fights.py` is shared with the parity harness).

## 2.4: reader hp -1 is a placeholder (a)
Source: `hp_placeholder.py`, raw live logs of the 138 matches.
- **Every recorded body row with hp -1 also reads max_hp -1: 10,384 / 10,384.** No real hp reads like that, so it is
  the reader failing to read the hp component, not a value.
- **Where it happens:**

| card | rows with hp -1 | bodies |
|---|---:|---|
| 203000088 (hero Tombstone visual dummy) | 7,796 / 46,893 | 41 of 44 always -1 |
| 13000049 | 2,102 / 3,180 | -1 only some of the time (28 bodies) |
| 13000007 | 393 / 3,192 | -1 only some of the time (4 bodies) |
| 13000004 | 87 / 1,735 | -1 only some of the time (1 body) |
| 6 other cards | 1 row each | |

The three 13000xxx ids are evolved forms (Bats / Witch / Skeleton-type in the onsets).
- **Comparator:** a recorded hp -1 body takes the sim hp of a body at the very same (side, x, y). Its position must
  still match exactly.

## Round 2 status
- **17 → 28 / 109 over 4 sub-rounds**, 0 regressions in each (+7, +1, +2, +1). Exact frames 188,233 → 204,647.
- **Now stopped:** the ticket's ordered list is done. Neither stop rule fired (no two zero sub-rounds; 28 < 45).
- **What fails now (run9), first true divergence of the 81 failing unflagged matches:**

| matches | class |
|---:|---|
| 44 | body position |
| 8 | body missing in sim |
| 8 | projectile-only |
| 5 | sim body missing in the reader |
| 5 | own elixir with other arithmetic |
| 5 + 2 | hp only |
| 3 | spell / area timing |

- **Candidates for round 3, one mechanism each:**
  1. Archer Queen, Boss Bandit and Goblinstein ability casts: 0 extracted against 23 / 21 / 16 plays.
  2. The hero Valkyrie spin starting late in crforge, 9 of 33 clean casts. That is a fork patch candidate.
  3. A dossier rerun of the 44 body-position onsets on run9.

# Fix loop round 3

| sub-round | mechanism | change | exact apart from torn (unflagged) | exact frames | regressions |
|---|---|---|---:|---:|---|
| start (run9) | | | 28 / 109 | 204,647 | |
| 3.1 (run10) | Archer Queen / Boss Bandit / Goblinstein ability casts never extracted | input: casts dated from the reader's phase-2 ability buffs (`SME_CHAMP=1`) | **31 / 109** | 220,450 | 0 (+3) |
| 3.2 | hero Valkyrie spin late in crforge | **none**: not crforge (below), no fork patch | 31 / 109 | 220,450 | 0 (+0) |
| 3.3 (run12) | SME-layer input rules | moved into `extract.py`; inputs regenerated (`/workspace/pilot/inputs_v2`); SME input flags off | 31 / 109 | 220,450 | 0 (+0; 138 / 138 matches identical to run10) |

**Stop rule:** two sub-rounds in a row gained 0 (3.2, 3.3), so round 3 stops before 3.4. The body-position
dossier rerun is owed.

## 3.2: the "late hero Valkyrie spin" is a consequence, not crforge (a; `valk_late.py`, run10)
- **All 10 late casts sit on a board that was already diverged at the cast.** At `083722`/3101, for example,
  the recorded frame holds a hero Ice Wizard and units the sim lacks.
- **Why crforge waits:** its spin starts when `ValkyrieHero_Charge_Target` (`WaitForTarget`,
  `ValkyrieHero_Charge_Shape` radius 5,500) finds a ground target. On those boards the target the game had was
  missing or elsewhere.
- **On exact boards the spin is on time:** 0 casts are late; the 24 aligned casts all start at R+2, as in the game.
- **No patch.** The fork branch `clashbot-fix` is still the pin.

## 3.3: one copy of the input rules (a)
**What moved:** `extract.py` (`crforge_casts`) now applies the Golden Knight dash casts, the champion buff casts,
the hero Ice Golem death-cast drop and the round-1 made dating.
- It imports the functions from `sme_live.py` / `live_frames.py`, so the SME layer and the extractor share one copy.
- `fights.seen_casts` is not edited, because RoyaleSim's dating differs.

**Checks:**
- **Parity harness tests (`L74/parity/tests`), before and after:** identical, 97 passed and 1 failed. The failure is
  the pre-existing `test_own_timing::test_ext_forms_map_reader_ids_to_catalog_forms`.
- **`test_extract.py`:** passes, with unchanged numbers.

**Regenerated inputs:**
- `regen_inputs.py` re-extracted the same 138 matches with the same battle-log entries, written to pod
  `/workspace/pilot/inputs_v2/inputs_rngfree.jsonl` (sha256 `ff769468…`). Flags are unchanged on 138 / 138.
- The first regeneration (run11) differed on 3 matches. Its made dating also shifted Rage, whose area comes from a
  RageBottle unit, not `castSpell`; the SME rule never shifted Rage.
- With summoning spells excluded (`summoning_spells`), **run12 equals run10 on 138 / 138 matches** (counts and first
  divergence). Runs no longer need `SME_FX_SHIFT` / `SME_GK` / `SME_GOLEM` / `SME_CHAMP`.
- Rage's own dating is left open (b). On run11 it was mixed: 2 matches 2 ticks worse, 1 match +738 exact frames.

## 3.1: champion casts from ability buffs (a)
These three champions show no dash, unlike the Golden Knight. **Their cast shows in the reader's phase-2 unit buff
rows**, with remaining and duration in ms:
- `ArcherQueenRapid` on the Archer Queen;
- `BossBandit_ability_buff` on the Boss Bandit (`Invisible: 1`, 1,000 ms);
- `goblinstein_doctor_aura` on the doctor.

**Converter:** `live_frames.py` now keeps them as `B` rows, and all 138 matches were re-converted to
`/workspace/pilot/sme_live/frames2`. The board rows are unchanged, so run10 vs run9 is a clean comparison.

**crforge probe, `useAbility` at run 310, buff first shown at:**

| champion | buff line | unit that takes the command |
|---|---:|---|
| Archer Queen | 314 | the play's unit 0 |
| Boss Bandit | 314 | the play's unit 0 |
| Goblinstein | 311 | the doctor, the play's unit 1 |

To read buffs, `SmeRun` now writes each body's buff names as row field 11.

**Rule (`buff_casts`):**
- A cast's start is the first sighting - (duration - remaining)/50.
- R = start - delay, with window ±1.
- One cast per side and buff per 40 ticks.

**Result:** 3 of the 10 unflagged matches with these champions became exact (`020913`, `220317`, `180015`), and
`172835`, `210720` and `000233` gained 2,000+ exact frames each. One first divergence sits on a cast: at `180015`/407 the sim fired an Archer Queen
arrow 20 ticks before the game, and her extracted cast is at 405. With it, the match is exact.

# Fix loop round 4 (ticket A2c round 4)

Engine: the upstream-sync fork build **`008aa626`** (branch `clashbot-upstream-20261027`), frozen for these runs at
pod `/workspace/pilot/lib_008aa626` (core jar sha256 `e94447c0…`); SmeRun built against it in `build_008aa626`.
Runs: `run_fork.sh RUN LIB BUILD [VAR=val ...]` (pod `/workspace/pilot/sme_live/`, inputs `inputs_v2`, frames2).
No crforge patch in this round: `clashbot-fix` / `clashbot-upstream-20261027` still carry none.

| sub-round | mechanism | change | exact apart from torn (unflagged) | exact frames | regressions |
|---|---|---|---:|---:|---|
| 4.0 (run13) | engine switch to `008aa626` | none (SME_LIB / SME_BUILD only) | 31 / 109 | 220,450 | 0; **138 / 138 matches identical to run12** (counts, first divergence, every episode; 138 / 138 plans byte-identical) |
| (run14, superseded) | reader read inside a step | comparator `torn_step`, first version | 39 / 109 | 220,450 | 0 (+8); **unsafe, see 4.1** |
| **4.1 (run16)** | reader read inside a step | comparator `torn_step` (`SME_TORN_STEP=1`): two movers, isolated frame | **38 / 109** | 220,450 | **0 (+7)** |
| **4.2 (run17)** | hero Valkyrie cast dated 1 tick late for crforge | input: `cast_seen` Valkyrie ability window -1 (`SME_VALK=1`) | **39 / 109** | **224,126** | **0 (+1)** |

**Not reached: 45 / 109.** Neither stop rule fired (+7, +1). The round stops here: the remaining body-position
onsets split into small classes (table below) that each need their own investigation; no third fix is staged.

## 4.0-1: the 41 body-position onsets, classified (a; `dossier2.py`, `t1check.py`, `tgt_frames.py`)
Method, per onset t0 with previous recorded frame tp (exact or torn):
- `dossier2.py` (SmeRun with `SME_TGT=1`: each body row gets its targeting reference id) gives every displaced body's
  recorded and sim motion tp → t0, its sim target and its recorded target (phase-3 `attack.target_gen`, laptop
  `tgt_frames.py`, mapped to the sim id by position at tp), the nearest bodies and the area effects / projectiles near.
- `t1check.py`: the onset frame's diff against sim t0, t0+1 and t0+2, and the frames after it.
- The over-fit probe of each run (run ticks 1-2 outside the window), aggregated over all 138 matches.

| n | mechanism | evidence | side |
|---:|---|---|---|
| 16 | **reader read inside step t0+1** | the frame equals sim t0+1 apart from what the step adds last: bodies killed in the step still listed at hp 0 / -1, a death spawn's parent still listed, a projectile at its impact point with the hp not yet taken, our elixir before the step's regen. The next frames are exact again in 15 / 16. Bodies show 2 ticks of motion over a 1-tick frame gap | reader |
| 5 | **hero Valkyrie ability 1 tick late** | 12 Valkyrie `cast_seen` casts (of 73) move a divergence later at lo-1; no other hero's ability shows that (IceWizard, Balloon, Bowler, IceGolemite: 1-2 each, both directions). crforge: buffs on R+1, charge (150 / tick) and `ValkyrieHero_AEO` on R+2 (probe on `144615`, `033729`) | input dating |
| 4 | hero Valkyrie, other | walking or charging faster in the game (178 vs 119 units over 2 ticks); no ability-probe hit | open (b) |
| 4 | Golden Knight dash | sim dash 144-214 units over 2 ticks against the game's 71-112; moving the dash command by -2..+2 fixes 0 of 4 (`212917`, `030315`, `180652`, `001141`; `184912` at -2) | open (b): dash length, not its tick |
| 5 | small steering offsets (1-25 units) | same target in both, no body within 1,000, no area effect / projectile near | open (b): pathing / steering rounding |
| 3 | hero Ice Wizard and its cube | hero and cube at one point (the pairing skips them); 16 / 60 unit offsets | open (b) |
| 2 | game body ~1.15x faster | `200616` Inferno Dragon and hero Mini PEKKA both 2.29 ticks of motion in 2 ticks; `020134` Ronin 2.31 | open (b) |
| 2 | swarm collision / push | Goblin Gang, evolved Skeleton Army: lateral moves up to 300 units, a stationary goblin moved (3, 6) | crforge candidate (b) |

- **Retarget: 0 onsets (a).** On every paired body the sim target equals the recorded target at tp; 4 bodies differ at
  t0, all on frames classed above.
- **Not seen (0 each, a): path / bridge choice, knockback, spawn offset, extraction gap.** No displaced body was near a
  Log / Tornado / pushback object except on frames already classed (reader / Valkyrie).
- The run3 dossier's collision/push reading of the small offsets (hero Ice Wizard -6,+7; Knight 0,-9) is **not
  supported (c for collision on those two)**: no body is near either at the offset, and the Knight's onset has moved
  (run12: 5148), where it is a step read.

## 4.1: comparator rule `torn_step` (a)
A frame t is torn (`step_read`, `SME_TORN_STEP=1`) when it is a read inside step t+1:
- **at least two** sim bodies move between t and t+1, and **every** one is read at its t+1 point;
- every recorded body sits at the t+1 point of a sim body with that body's hp at t or t+1 (or the -1 placeholder), or
  at (or within 200 units of) the t point of a body the step removes, with hp 0 / -1 / its t hp;
- every sim t+1 body not read is new in step t+1. Projectiles / areas: every recorded one sits at a t or t+1 point (a
  projectile the step removes also at a body's point), and every one not read is new in the step;
- our elixir and hand are those of t or t+1;
- the frame is **isolated**: no div or torn_step neighbour frame.

**Why the first version (run14) was unsafe (c for it).** It needed one mover and no isolation. The Valkyrie fix (run15
vs run14) then turned 7 + 10 of its torn_step frames (`083722`, `162012`) into exact frames: they had been a hero
Valkyrie one tick ahead, which one mover cannot tell from a step read. Audit on run15 (`ts_movers.py`): 27 of 67
torn_step frames had one mover, 12 of them one run of consecutive frames (`183044`, one Knight). With two movers and
isolation (run16) the gain is +7 instead of +8 (`002429` drops out) and the torn_step frames are 38.

**Planted checks (`step_test.py`, the 8 onsets classed torn_step):** one stepping body moved by 1 unit gives `div`
8 / 8; our elixir +1 gives `div` 8 / 8.

**Gained (run16):** `145939`, `170600`, `172314`, `210249`, `211757`, `021852`, `025651`.

**Reader fix (b, not in my write set):** as for round 2.1 and the 10-26 replay: read `game_tick` again after the
frame and flag the frame when it changed.

## 4.2: hero Valkyrie dating for crforge (a, input)
- `seen_casts` dates a state-10 hero cast for RoyaleSim (cast starts on R+1): R in [prev frame, first - 1].
- crforge's Valkyrie takes `ValkyrieHero_Damage_Reduction_Buff` / `AttackChain` on R+1 and starts its charge on R+2,
  as its Golden Knight moves on R+2 (round 2.2). Rule (`valk_shift`): R and its window 1 tick earlier, Valkyrie
  `cast_seen` only.
- Other heroes keep their dating: the over-fit probe shows no lo-1 preference for them (Knight 9, Dark Prince 9,
  Wizard 20, Mini PEKKA 7 casts).
- Gained: `004901` (720 div frames → 0). Also `154319` 959 → 3 div frames, `083722` 896 → 90 (run15 vs run14).
- (b) Whether the game's state 10 marks the charge start (so the lag is crforge's own) or crforge's Valkyrie is a
  tick slow cannot be told without a recorded command stream; the input rule fits the frames either way.
- **Owed:** the rule lives in `sme_live.valk_shift` behind `SME_VALK`. `extract.crforge_casts` does not call it yet,
  because `inputs_v2` would then be shifted twice. Moving it needs an inputs_v3 regeneration with `SME_VALK` off.

## What fails now (run17): first true divergence of the 70 failing unflagged matches
33 body position, 9 body missing in the sim, 7 projectile only, 7 own elixir (other arithmetic), 5 + 1 hp only,
4 sim body missing in the reader, 3 spell / area timing (`results/live/run17_cmp.txt`).

**Next candidates, one mechanism each (b):** the Golden Knight dash length (4), the hero Valkyrie walk / charge speed
(4), swarm collision (2, a fork-patch candidate), the ~1.15x speed pair (2). None alone reaches 45.

## Files (round 4)
- `dossier2.py` (all-match dossier), `tgt_frames.py` (laptop: reader targets), `t1check.py`, `step_test.py`,
  `step_why.py`, `ts_movers.py`, `run_fork.sh`.
- `sme_live.py`: `repr_rows`, `step_read` and its isolation pass (`SME_TORN_STEP`), `valk_shift` (`SME_VALK`).
- `SmeRun.java`: an optional 13th row field, the targeting reference id (`SME_TGT=1`; off in every scored run).
- Results: `results/live/run16_{results.jsonl,cmp.txt}`, `run17_{results.jsonl,cmp.txt}`, `dossier2_run12.{jsonl,txt}`,
  `dossier2_run14.jsonl`, `t1check_run13.jsonl`.

# Fix loop round 5 (ticket A2c round 5)

Same engine (`lib_008aa626`), comparator `SME_TORN_STEP=1`. Inputs are regenerated by `regen_inputs.py` from
`extract.py` at each input change (pod `/workspace/pilot/inputs_v{3,4,5,6}`); `run_fork.sh` takes `INPUTS=` and
`REPR=`. Bar (coordinator, 10-27): D1 = SME >= 45 / 50, i.e. >= 99 / 109 here; iterate until two zero-gain sub-rounds.

| sub-round | mechanism | change | exact apart from torn (unflagged) | exact frames | regressions |
|---|---|---|---:|---:|---|
| 5.0 (run18) | one copy of the 4.2 rule | `extract.crforge_casts` calls `valk_shift`; inputs_v3 (73 Valkyrie casts shifted, nothing else); `SME_VALK` off | 39 / 109 | 224,126 | 0; **138 / 138 identical to run17** |
| **5.1 (run19)** | our own Ice Wizard press dated off the elixir drop | input: `own_press_elixir` (inputs_v4; 15 presses, 6 moved) | **40 / 109** | **224,529** | **0 (+1, `030951`)** |
| 5.3 (run20) | Rage dated as a cast, its bottle unseen | input: `bottle_lag` (Rage R = area made - 10, 16 casts, inputs_v5) + comparator `repr_v2` (RageBottle dropped, not mapped) | 40 / 109 | **227,262** (+2,733) | 0 (+0) |
| 5.4 (run21) | Golden Knight dash starting below 100 / tick | input: dash start from the first frame > 63 / tick (19 of 36 casts moved) | 39 / 109 | 225,116 | **1** (`085635`): **rejected**, rule left off (`SME_GK_ACCEL=0`) |

**Stop rule fired:** 5.3 and 5.4 gained no match. Kept state = run20: **40 / 109, 227,262 exact frames**, inputs_v5
(sha256 `49321a87…`, byte-identical to a fresh `extract.py` regeneration with the 5.4 rule off), `repr_v2.json`.

## 5.1: steering offsets and the Ice Wizard / cube cases, classified (a)
Per onset, every command run in [t0-130, t0] was swept by -3..+3 ticks (and the suspects by up to -14):

| match | first divergence | what it is | side |
|---|---|---|---|
| `142027`, `182050`, `233957` (IW / cube) | hero IW and cube 16-30 units off; our elixir 2 high | **our IW press tick**: the tap-dated tick lies outside the frame pair where our elixir drops by the ability's 2 elixir (crforge takes the cost on R, shows it on R+1) on 6 of 15 presses (`142027` 1-2 late, `182050` 5 late, `233957` 1-2 early, `095134`, `164443`, `230512` early). Rule `own_press_elixir`: R in [prev, first-1] of that drop | **extraction** (fixed, 5.1: the three onsets moved to 1990 / 3464 / 5461) |
| `211239` (cube) | cube 60 units (one tick of its float) behind | no single command in -3..+3 helps | open (b) |
| `164443` (GK, 1 unit) | the game GK turns and speeds to 84 / tick at 744-746; the extracted dash cast is at 750 (first frame > 100 / tick) | dash start missed: R = 743 makes the first divergence 3213 | extraction, but the general rule (5.4) regressed `085635`; open |
| `170912` (Skeleton, 19 units) | its target, a Firecracker, recoils while the skeleton runs at it; same target in both | crforge steering toward a moving target (b) | crforge candidate, no patch |
| `180336` (EliteArcher hero, 9 / 23) | no command shift helps; same target | open (b) | |
| `234837` (Knight vs hero Giant, 1-3 units) | no command shift helps; the Knight targets the Giant | open (b): contact / collision rounding | |

## 5.2 / 5.3: "swarm collision" and "1.15x faster" are both Rage (a)
- `200616` (Inferno Dragon 59.8 → 76.9 a tick; hero Mini PEKKA 62 → 116), `020134` (Ronin) and the swarm case
  `175027` (Goblin Gang 84 → 96 a tick) all speed up 1-2 ticks after the reader's Rage area appears (`fxlook.py`).
  Rage's buff is `SpeedMultiplier` 130 (tables 16.402.22). So these are **not speed tables, levels or collision**
  (c for both readings).
- The reader's Rage row is the area itself: its countdown reads 4,500 ms (full life) on its first frame (raw log,
  `200616`@1014). crforge makes Rage as `RageBottle`, a building with `DeployTime` 500 whose death makes the area: the
  area shows 10 ticks after the command. The reader lists no bottle (no hit points), so the old dating (R = made - 1)
  put crforge's area 9 ticks late, and `repr_v1` had mapped the bottle onto the reader's area by coincidence (c for
  that mapping).
- Rule: R = made - `DeployTime`/50 for a summoning spell whose summoned character is a bottle with a
  `DeathAreaEffect` (only Rage; `extract.bottle_lag`), and RageBottle dropped in `repr_v2.json`. The sweep put the
  first divergence of `200616` / `020134` from 1014 / 1613 to 2545 / 2497 at exactly this R (-9 from the old tick).
- run20: `175027` is down to 1 div frame (own elixir, 4375). `200616` and `020134` now first diverge on a Rage
  **`RageDamage` 1 tick late**: the game shows the Rage area and its `SpawnAreaEffectObject` (`RageDamage`) on the
  same frame, crforge makes the chained area on the Rage area's first update, the next tick
  (`AreaEffectEntity` line ~581). That is a crforge-side candidate (one fix for every Rage); **no patch written**
  this round.
- `040821` (evolved Skeleton Army "collision"): its onset is 2 ticks after an opponent Rascals play (`first_seen`
  2113); the Rascal boy is 481 units off. Extraction-side play point of a multi-body card (b), not collision.

## 5.4: rejected
Dating the Golden Knight dash from the first frame faster than 63 / tick fixed `164443`'s onset but cost
`085635` (exact → not) and 2,146 exact frames overall. The rule is left in `gk_dashes` behind `SME_GK_ACCEL` (default
0, off), so `extract.py` reproduces inputs_v5.

## What fails now (run20): first true divergence of the 69 failing unflagged matches
| n | mechanism group |
|---:|---|
| 27 | body position (by the round 4-5 dossiers, not re-run on run20: Golden Knight dash 4, hero Valkyrie other 4, steering / contact 4, cube 1, play point 1; the rest unclassified) |
| 10 | body in the reader, none near in the sim (play missed / late / not made) |
| 9 | our elixir a card cost low for 1 frame (other arithmetic than torn_cmd) |
| 7 | projectile only (launch timing / flight) |
| 6 | hp only |
| 4 | sim body missing in the reader |
| 5 | spell / area timing (3 of them Rage's chained `RageDamage` 1 tick late) |
That is well over the plan's 5 mechanisms; D1 (99 / 109) is not in reach with input rules alone.

## Files (round 5)
- `extract/extract.py`: `crforge_casts` calls `valk_shift` and `own_press_elixir`; `bottle_lag` (Rage dating).
- `sme_live.py`: `own_press_elixir`; `gk_dashes` start rule behind `SME_GK_ACCEL` (off).
- `repr_v2.json` (pod and here): RageBottle dropped.
- Results: `results/live/run{18,19,20,21}_{results.jsonl,cmp.txt}`.

---

# Fix loop round 6 (ticket A2c round 6.0-6.3, worker a2c6)

Same engine (`lib_008aa626`), `repr_v2.json`. Runs on pod 33920 `/workspace/pilot/sme_live/r6*` (named so they cannot
clash with another worker's runs). Each row is cumulative on the one before. **0 regressions in every sub-round.**

| sub-round | class | where | change | exact apart from torn (unflagged) | exact frames | gained |
|---|---|---|---|---:|---:|---|
| start (run20) | | | | 40 / 109 | 227,262 | |
| **6.1 (r61)** | read inside step t+1, fewer than 2 movers | reader (comparator rule) | `step_read`: our elixir equal to sim t+1's and not to sim t's stands in for the two-mover count (`SME_STEP_CLOCK=1`) | **44 / 109** | 227,262 | `212111`, `222240`, `002429`, `022821` |
| **6.2 (r62)** | command-pass read at triple elixir | reader (comparator rule) | `cmd_pass_read` also accepts a 537 regen (`SME_TORN_CMD3=1`) | **48 / 109** | 227,262 | `144057`, `210720`, `032352`, `040302` |
| **6.3a (r63a)** | Rage dated a tick late | extractor | `table_shims.life` follows SummonCharacter -> DeathAreaEffect -> LifeDuration (10 Rage commands -1; inputs_v8) | **51 / 109** | **228,990** | `200616`, `224041`, `020134` |
| **6.3b (r63b)** | our own Ice Wizard press dated from the reader's cast | extractor | `own_press_elixir` also for our `cast_seen` presses (`SME_OWN_CAST=1`; 10 of 125 moved; inputs_v9) | **54 / 109** | **229,357** | `154839`, `175027`, `182050` |
| **6.6 (r66)** | a troop row with an unmapped id (card -1) read as a tower | comparator (`canon_live`) | a card -1 row is a tower only with the reader's building kind 12/13 (`SME_KIND_T=1`) | **57 / 109** | **230,987** | `183750`, `200941`, `201701` |
| 6.7 (r67) | hero IW deploy area taken for an ability cast | extractor | drop it (`iw_deploy_cast`, `SME_IW_DEPLOY=1`; 10 casts; inputs_v10) | 57 / 109 | 231,646 | 0 |
| **6.8 (r68)** | opponent hero IW cast 2-3 ticks late | extractor | date it from the ability's 50 ms area (`iw_area_cast`, `SME_IW_AREA=1`; 2 casts; inputs_v11) | **58 / 109** | **233,238** | `014151` |
| 6.9 (r69) | hero Goblins / hero Tombstone plays dropped as role-children | extractor | `own_unit` also exact from `unit_hp.tsv` (`SME_UNIT_HP=1`; 33 plays added in 9 matches; inputs_v12) | 58 / 109 | **239,565** | 0 on the 109; 7 flagged matches lose `opp_no_fitting_deal` (116 unflagged by v12's own flags) |
| BP merge check (r6bp) | body position (other worker, 1d8badc) | extractor | `bp_rules.apply` hook in `extract.match`, SME_BP_VALK/GK/GIANT/RASCALS on, on inputs_v9 (inputs_v13) with r63b's comparator | **67 / 109** vs r63b | **245,973** | 13, the same set as the worker's bpA; 0 lost |
| **combined A (r6xa)** | all extractor rules | extractor | inputs_v14 = all of 6.3a-6.9 + bp_rules (VALK/GK/GIANT/RASCALS); comparator 6.1/6.2/6.6 | **71 / 109** vs r69 | **256,184** | 13 |
| **combined B (r6xb)** | placeholder in torn_mixed | comparator | `SME_BP_MIXPH=1` (BP worker's diff, planted 15 / 15 there) | **73 / 109** | 256,184 | 2 |
| **combined C (r6xc)** | read inside a step, matched against crforge's own in-step states | comparator | `SME_BP_SNAP=1` with SnapRun (BP worker's diff, planted 35 / 35 there) | **79 / 109** | 256,184 | 6 |

## 6.0: all 69 failures of run20, classified (a)
Tools (all on run20's plans, `SME_TORN_STEP=1`):
- `diag6.py`: per onset, the diff against sim t0-2 .. t0+2, why `step_read` rejects it, the mover count, our elixir
  around it and the commands near it.
- `sweep6.py`: every command in [t0-130, t0+15] moved by -3..+3 (a command after t0 also back to t0-3); scored to t0+400.
- `cls6.py`: the class rules, first match wins.
- 138 onsets in total: 68 first onsets, plus the 70 later ones in the same matches. 1 match is refused by crforge
  (`225213`, GoblinDrill evolution).
- Results: `results/live/{diag6all,sweep6all}_run20.jsonl`, `cls6_run20.tsv`.

| class | where | first onsets | all onsets | matches it alone blocks (run20) | cost | fixed in |
|---|---|---:|---:|---:|---|---|
| read inside step t+1 with our elixir already t+1's (0-1 movers) | reader | 8 | 12 | 4 (+2 with the 3x class) | comparator rule, 1 line | 6.1 |
| command-pass read at triple elixir (regen 537) | reader | 4 | 12 | 2 (+2 with the class above) | comparator rule, 1 line | 6.2 |
| Rage one tick late | extractor (`life` None) | 3 | 6 | 3 | extractor, 4 lines | 6.3a |
| our own IW press dated from the cast, not the elixir drop | extractor | 5 | 6 | 3 | extractor, reuse `own_press_elixir` | 6.3b |
| a troop row with an unmapped id (card -1) read as a tower | comparator (`canon_live`) | 4 | 13 | 3 (+1) | comparator, use the reader's kind | 6.6 (staged) |
| hero IW deploy area taken for an ability cast | extractor (`seen_casts`) | 3 | 5 | -- | extractor rule | 6.7 (staged) |
| hero Valkyrie cast dated from the spin, charge 3-16 ticks earlier | extractor | 4 (+1 partial) | 5 | 3 | extractor rule (body-position worker) | -- |
| Golden Knight dash start | extractor | 2 | 2 | 0 alone | (body-position worker) | -- |
| other hero ability casts 1-3 ticks off (Bowler, Balloon, opponent IW) | extractor | 3 | 6 | 2 | opponent IW: 6.8 (staged); Bowler / Balloon one case each (b) | -- |
| open: body position (steering / contact, GK dash length, Rascals formation, IW cube, ...) | crforge / unknown (b) | 15 | 31 | | (body-position worker) | |
| open: projectile (Goblin Barrel evolution decoys, Balloon bomb, tower shot) | unknown (b) | 5 | 17 | | | |
| open: body missing / extra (Goblins never extracted `224856`, MiniPekka hero, ...) | extractor / unknown (b) | 4 | 12 | | | |
| open: hp only (`192935`, `204518`, `010245`) | unknown (b) | 3 | 5 | | | |
| open: Earthquake pulse (`222712`, behind an IW deploy cast) | -- | 1 | 1 | | | |

**Projection (a, from the sweep + rules, each match counted when all its onsets are in fixed classes):** the first
four classes reach 54 / 109 (measured: 54 / 109). With the tower-label, IW-deploy and Valkyrie classes: about 60 / 109.
**28 of the 68 failing matches have at least one onset in an open class**, mostly body position. So D1 (99 / 109) needs
the open classes, not more input dating.

### Hypothesis (i): "own elixir one card cost low" is partly the IW press read one frame early -- confirmed, but the cause is the dating (a)
- **The 9 run20 onsets of that class split into two classes.**
  - **4 (`154319`, `210720`, `032352`, `040302`) are the round-2.1 command-pass read at triple elixir.** The board
    equals sim t0. Our elixir is lower by a whole card cost, and sim t0+1 is reached by one 537 regen.
    `cmd_pass_read` only allowed 178 / 357 (6.2 fixes this; 12 onsets in all).
  - **5 (`175027`, `154839`, `182050`, `220728`, `004031`) are our own Ice Wizard presses with no logged tap.** They
    are dated from the reader's cast (`cast_seen`, 125 of our 140 presses), so `own_press_elixir` (round 5.1, `own_press`
    only) never saw them.
- **The game's elixir drop is 1-12 ticks before the cast_seen tick.**
- **Probe (`cmdprobe6.py`), the press moved into the drop window:** `175027`, `182050` and `154839` become exact.
  `220728` moves from 778 to 3007; 3007 is the IW deploy class. `004031` moves from 2083 to 3482. Its drop holds our
  Skeletons as well, so the rule skips it.
- **Rule (6.3b):** the same function on our `cast_seen` presses. A drop whose frame pair holds one of our card plays is
  not taken. Without that, a Log / Tornado / X-Bow drop was taken on 5 casts: `100018`, `144057`, `204837`, `004031`,
  `030951`.

### Hypothesis (ii): some "bodies the sim lacks" are step reads rejected for < 2 movers -- confirmed for some (a)
- **Of the 10 run20 "body in the reader, none near in the sim" onsets:**
  - 4 are a different class: a troop read as a tower (`172835`, `201701`, `183750`, `200941`; 6.6).
  - 3 are reads of step t0+1 (our elixir = sim t0+1): `080929`, `094126`, `002021`. `step_read` still fails them, but not
    on the mover count. It fails on the IW deploy area (6.7) and, in `080929`, on a dead Battle Ram read at its moved
    point with its old hp.
  - The other 3 are a Goblins play never extracted (`224856`), the Rascals formation (`010613`) and `233957`.
- **The two-mover rule was the blocker on 8 first onsets in other classes:** `142027`, `001141`, `014928`, `002429`
  (1 mover) and `144057`, `222240`, `212111`, `022821` (0 movers). Each frame's elixir is sim t0+1's (a per-tick clock:
  regen every tick), while the board is at t0+1 with the step's removals not yet in (hp 0 bodies still listed).
- **Why the clock is safe where 1 mover was not (round 4.1):** a single body one tick ahead does not change our elixir.

### Planted checks (a)
- **6.1, `step_test6.py`, on the 12 onsets the clock rule classes torn_step:** each planted change must take the frame
  out of torn_step.

  | planted change | caught |
  |---|---:|
  | our elixir set to sim t's (the clock gone) | 12 / 12 |
  | our elixir +1 | 12 / 12 |
  | one live recorded body moved 1 unit | 9 / 9 (3 frames have no live unit row) |
  | a hp-0 body given hp 5 | 10 / 10 |

- **6.2, `cmd_test6.py`, on the 12 triple-elixir torn_cmd frames:** each planted change must make the frame div.

  | planted change | caught |
  |---|---:|
  | elixir +1 | 12 / 12 |
  | elixir -1 | 12 / 12 |
  | elixir 0.5 elixir lower still | 12 / 12 |
  | one live unit moved 1 unit | 12 / 12 |

- Outputs: `results/live/{steptest6,cmdtest6,kindtest6}_run20.txt`.

## 6.6-6.9 (owner 10-27: no fin16 fallback; iterate every class but body position, which another worker owns)
- **6.6, a troop read as a tower (a).** `canon_live` called every card -1 row a tower. Across all 138 matches' frames:
  - card -1 rows on the 6 tower points: 1,881,839, all with kind 12 or 13;
  - card -1 rows anywhere else: 1,426, all with kind 14 or 15 (troops).

  At the 4 run20 onsets those troops were the Witch Mother's VoodooHog: same (side, x, y, hp) as the sim's unit.
  - Rule: a tower is card -1 **and** kind 12 / 13.
  - Planted checks (`kind_test6.py`): the relabelled row moved 1 unit, 13 / 13 div; its hp +1, 13 / 13 div.
- **6.7, hero IW deploy area (a for the area; the onsets stay).** `iwfx6.py` lists every 203000023 area on the 138
  matches:
  - **a real cast** makes a 50 ms area at R+4 (or 0 ms at R+5), then a ~1,000,000 ms area at R+7..8;
  - **10 areas sit on an Ice Wizard play's point on its first frame:** 9 with no countdown, 1 at 1 ms. Each made a bogus
    `cast_seen` cast 1-2 ticks before the deploy.

  Dropping those casts is right: +659 exact frames, 0 regressions. **But the 5 onsets on those frames stay.** They are
  the hero IW's cube on its deploy frame, not the cast. The body-position worker's census (906e414) covers the cube.
- **6.8, opponent IW cast dated from its area (a).** On 16 of 18 opponent casts the 50 ms area is first seen at
  `cast_seen` + 4 (50 ms left) or + 5 (0 ms left). The other 2 sit 2-3 ticks late (`014151`@1266, `211239`@5544), and
  the sweep fixes both at exactly made - 4. Our own casts keep the elixir dating.
- **6.9, hero Goblins / hero Tombstone plays (a).** The `own_unit` shim (">= 45% of the card's biggest body") could not
  tell a hero's units from children of its larger ability object. So every opponent hero Goblins and hero Tombstone play
  was dropped. That is extract.py's own ponytail note.
  - `224856`: 4 goblins at 323 hp, never played. Its first divergence moves from 365 to 493, and div frames fall from
    1,659 to 36.
  - With `unit_hp.tsv` (exact max hp per level, base and hero rows) the shim also accepts an exact unit hp. 33 plays come
    back in 9 matches.
  - **7 of those matches lose `opp_no_fitting_deal`:** the deal now fits, so the missing plays were the reason. Scored
    on v12's own flags, 116 matches are unflagged and 58 are exact. The 7 new ones all still diverge (first at 550-4012).
- **Zero-gain sub-rounds: 6.7 and 6.9, not consecutive.** Exact frames still rose: +659 and +6,327.

## Combined run (r6xa-c) and the second pod
- **r6xc = 79 / 109 with 0 regressions** against r69 (my line), r6bp, bpA, bpB and bpC.
- **Against bpD (BP worker, 76 / 109) it lacks `154319` and `233957`.** bpD's in-step SNAP uses SnapRun2 on the
  clashbot-bp TickProbe build (`fork/bp/clashbot-bp_0001_TickProbe.patch`). That build is not on pod 33920 or 33308
  yet; r6xc used SnapRun on the frozen `lib_008aa626`.
- **Pod 33308** (JDK 17.0.20.1 from apt, as `pod_setup.sh`): lib, SmeRun / SnapRun builds, frames2, inputs_v12 / v14,
  the original inputs, the tables and `pilot/sme` are sha-identical to 33920 (one tree hash, `ce83e863...`).
  **r6xa run there is byte-identical to 33920's r6xa** (results.jsonl sha256 `98a1cb9d9c524253...`).

# A2c-BP2: 080929, 094126, 000233 (body-position line, pod 32657)

Base: **bpD reproduced exactly (a)**: `bp/runD.sh bp2D0` = bpD on all 138 matches (`bp/same.py`: 138 / 138 identical,
76 / 109). Runs: `bp/runB.sh RUN INPUTS LIB [VAR=val]` from a pod copy of `pilot/sme` (`/workspace/pilot/bp2/sme`) with
the FITNEXT patch; comparator = bpD's (r63b + MIXPH + SNAP on SnapRun2). Each row is cumulative on the one before.

| run | match | layer | change | exact apart from torn | exact frames | regressions | gained |
|---|---|---|---|---:|---:|---|---|
| bpD | | | | 76 / 109 | 245,973 | | |
| **bp2a** | 094126 | extractor | `SME_BP_PRESS=1` (bp_rules.press_from_drop): our cast_seen ability with no elixir drop at its tick takes the nearest earlier unexplained drop (2 casts move; inputs = inputs_v9_bpall + `bp/bp_post.py`, flags off = byte-identical) | **77 / 109** | 246,845 | 0 | `094126` |
| bp2b | 080929 | fitter | `SME_BP_FITNEXT=1` (`fork/bp/sme_live_bp2_fitnext.diff`): `variants_at` also varies a command run after the onset whose window reaches back to it | 77 / 109 | 246,887 | 0 | 0 (080929 episode 3131-3216 healed, +42 frames) |
| **bp2c** | 080929, 145247 | comparator (instrumentation) | crforge fork `clashbot-bp` 05533954 (`fork/bp/clashbot-bp_0002_TickProbeDrain.patch`): a TickProbe point after each entity a cleanup round drains; SNAP sees those states | **79 / 109** | 246,887 | 0 | `080929`, `145247` |

## 094126@3485: our hero IW press dated 166 ticks late (a, extractor)
- Our elixir is 20,000 below the sim from frame 3485 to 3651, equal before and after (`bp/tr.py`): the game took the
  2-elixir press between frames 3483 and 3485; the extractor dated it from the cast (cast_seen 3651).
- Probe: the press at R = 3483 makes our elixir and the hero IW / cube path exact from 3485; whole match 872 -> 102 div
  frames (`bp/win.py ... 53:3483`). crforge holds the cast as the game does.
- Census (`bp/press_census.py`, `results/live/bp/press_census_v9.txt`): 140 own abilities, 126 on an elixir drop, 14 on
  none; 7 drops that no card play or ability explains, 2 of them before an own cast_seen cast (094126 gap 166, 100018
  gap 23; `own_press_elixir` looks 15 ticks either side). The rule moves exactly those 2. Self-check `bp/test_press.py`.
- The next onset (4576, our Rocket 1 tick early) was the fitter's: spell_seen window [4574, 4575], R = 4575 exact. The
  fitter reached it once 3485 healed. Rocket census (`rocket_census.txt`): own spell_seen Rockets 31 at offset 0, 12 at
  +1, 1 at -1; the window covers them, no rule needed.
- Extract hook: `fork/bp/extract_bp2_press_hook.diff` adds `bp_rules.PRESS` to the hook's gate (a2c6 merges). The hook's
  frames (`live_frames.convert`) equal frames2 on 094126 (2,537 / 2,537 frames).

## 080929: two onsets, both fixed (a)
- **3131-3216 (fitter blind spot).** Frame 3131: our elixir 2 below the sim; our Log ran at 3132 (spell_seen window
  [3131, 3133]). R = 3131 makes 3131 a command-pass read (torn_cmd) and every frame to 3216 exact. The fitter never tried
  it: `variants_at` takes only commands run in [d - 120, d], and the Log ran at d + 1. FITNEXT keeps R inside the
  extractor's window.
- **2007 (reader read inside the end cleanup).** The frame is sim 2008 except that the hero IW (hp 0) and its cube are
  still listed at their moved point. The Princess bolt that killed it is gone. In crforge the end cleanup drains every
  removable entity from the live list (`EntityHolder.drainRemovable`), then tells of each removal. No observer point
  lay between the bolt leaving (4000113, first in id order) and the hero leaving, so SnapRun2 had no such state. With
  the drain point, state `51:drain/-1/4000113` equals the frame (0 diffs, our elixir from state 43).
  `145247`@3032 fits the same way: after 2 of 3 drains (`110:drain/-1/5000065`).
- Fork 05533954: one `TickProbe.tell("drain", ...)` line. Core tests 2,140, 0 failures, 2 skipped
  (`coretest_clashbot_bp2.txt`). Traces of all 138 plans identical on lib_bp vs lib_bp2: 138 identical, the same 2
  GoblinDrill refusals in both (`trace_ident_bp2.txt`).
- Planted checks (`bp/snap_test.py bp2c bp2b`): live body moved 1 unit 2 / 2, hp + 1 2 / 2, projectile moved 1 unit
  2 / 2, our elixir + 1 2 / 2 (`snaptest_bp2c.txt`).

## 000233@4599: crforge re-routes onto a near node (classified; not fixed)
- Two skeletons, one on each side, target each other from step 4597. At 4599 both are 2 units off (side 1: rec (10981,
  21504) vs sim (10983, 21505)); targets agree (reader target_gen).
- No push, no avoidance blend (0), and one displacement in the movement visit (`bp/instep.py`).
- Scratch debug build (`bp/dbgrun.py`, a print in `Displacement.displace`, not committed). In step 4599 crforge aims
  skeleton 5000119 at (11250, 21250). That is a node of its rebuilt route, 458 units away, inside the 1,000-unit node
  advance, popped after the step. In 4598 it aimed at (11750, 20750). The game's 2-tick move, (126, -124), is exactly
  2 x (63, -62), the step toward (11750, 20750) (a). The other skeleton's aim changes in the same step, (13750, 16750)
  -> (13750, 17250). Evidence: `results/live/bp/aims_bp2.txt`.
- The same pattern is seen on **170912@745 (a for crforge's aim, b for the game's)**: right after a route rebuild,
  crforge aims at an adjacent node 432 units away, (7250, 17250) instead of (6250, 17250).
- **Hypothesis (b):** after a route rebuild, the game does not aim at a first node already inside the advance radius;
  either it pops that node first or it does not rebuild then.
  - Counter-evidence: 000233's own rebuild at 4597 also aimed at the near node, and frame 4597 is exact. There, both
    aims give nearly the same direction, so that frame cannot decide (b).
- **Census owed** before any fork change: every displacement whose aim node is within 1,000 units and differs from the
  previous tick's aim without a pop, on the 138 matches' clean stretches; the outcome is whether the next frames stay
  exact. It needs the aim print as a TickProbe-style hook (instrumentation) in the clashbot-bp fork.
  - `replan_census.py` does not see these events: the node is popped in the same step, so line to line the next node
    looks unchanged.

---

# Fix loop round 7 (worker a2c6)

Same config as r6xc (inputs_v14 and every comparator flag). The main run uses `lib_bp`, the clashbot-bp TickProbe build
(fork 008aa626 + `clashbot-bp_0001_TickProbe.patch`, built on pod 33920 with gradle offline), and SnapRun2 for the
in-step SNAP. Pod 33308 got the same lib by copy (core jar sha256 `73b19425f039dd4e`).

| sub-round | class | layer | change | exact apart from torn (unflagged) | exact frames | gained |
|---|---|---|---|---:|---:|---|
| start (r6xc) | | | | 79 / 109 | 256,184 | |
| **7.0 (r70)** | in-step reads | comparator | SNAP on SnapRun2 / `lib_bp` (bpD's build) | **81 / 109** | 256,184 | `154319`, `233957` |
| **7.1 (r71)** | Bowler press held through a freeze; Balloon throw dated 1-2 ticks off | extractor | `hero7_cast` (`SME_HERO7=1`; inputs_v15, 4 casts) | **83 / 109** | **256,991** | `183044`, `235915` |
| **7.3 + 7.4 (r74)** | own Knight tapped before its elixir drop; own press on a drop shared with Skeletons; Rascals girls on the back edge | extractor | `own_play_elixir` + a cost-split drop pair (`SME_OWNPLAY7=1`) and `rascals_back` (`SME_RASCAL7=1`; inputs_v17) | **85 / 109** | **257,585** | `004031`, `010613` |
| 7.2 (r75) | hero Ice Golem death read as a cast (101112@658) | extractor | `golem_death_fx` (`SME_GOLEM7=1`; inputs_v18, 1 cast) | 85 / 109 | **260,209** | 0 |
| **7.5 (r76)** | own IW press long before its cast (BP2) | extractor | `bp_rules.press_from_drop` (`SME_BP_PRESS=1`; inputs_v19, 2 casts: 094126, 100018) | **86 / 109** | **261,093** | `094126` |
| 7.6 (r77) | fitter varies commands just after the onset (BP2) | comparator / fitter | `SME_BP_FITNEXT=1` | 86 / 109 | 261,135 | 0 |
| **7.7 (r78)** | in-step SNAP on the drain probe (BP2) | comparator | `lib_bp2` = 0001 + `clashbot-bp_0002_TickProbeDrain.patch`, SnapRun2 rebuilt | **88 / 109** | 261,135 | `080929`, `145247` |

0 regressions in every row against the row before. The final run r78 also loses no match against bpD, bp2a, bp2b
or bp2c.

**The two press rules compose.** `own_press_elixir` (6.3b / 7.3) puts a cast inside a drop pair within 15 ticks.
`press_from_drop` (BP2, run after it in `extract.match`) only takes casts that are on no drop. So the regen with both
moves exactly BP2's 2 casts and nothing else.

**Identity checks (a).** `lib_bp` with SnapRun (v1) reproduces r6xc byte for byte (r7id on 33308, results sha256
`41ea29de6cffeb7e`). r73 (7.3 alone, inputs_v16) is still running on 33308; it is not used above.

## Dating signals, checked on every cast of the hero (a)
- **Hero Bowler, 183044: the press is held through a freeze.**
  - The reader shows `pending_on_body` = 1 from 2834 to 2912, while the Bowler is frozen (`IceWizardHero_FreezeBuff`);
    the cast follows the freeze's end.
  - crforge holds a pending press through a freeze too. R = 2833 / 2834 (the pending rise) and 2912 / 2913 all give an
    exact match. cast_seen's 2915 does not.
  - Census (`herobuf7.py`): pending rises on 1 of 3 Bowler casts. Balloon has 1 rise, but its throw is dated by its
    projectile instead. Wizard, Knight, Mini PEKKA, Dark Prince, Mega Minion, Ice Golem, Mighty Miner, Musketeer, Electro
    Wizard, Elite Archer and Tombstone have 0.
  - `BowlerHero_ability_buff` is made at R+4..5 on all 3 casts, so it cannot tell the held press.
- **Hero Balloon: the throw's projectile (card 203000006) is first read 4 ticks after the press on 8 of 11 throws.**
  - Rule: R = first - 4, from the first frame that shows a NEW projectile.
  - 4 throws move: `235915` 3044 -> 3046 (the sweep's exact tick), `230512`@2558, `235355`@4913.
  - The Balloon unit has no ability or buff field at its throws.
- **Hero Ice Golem, 101112@658, was a death read as a cast (round 2.3's class; the body test missed it).**
  - Its 203000038 areas read 1000 / 0 ms. Every real cast reads its 3 s area at 2950 ms on R+2 (7 / 7).
  - Rule `golem_death_fx` (`SME_GOLEM7=1`, inputs_v18): r75.
- **Own plays (`ownplay7.py`): 4,741 of 4,837 tap-dated plays sit inside their elixir-drop pair.**
  - 95 sit on the pair's last frame: that is the round-2.1 read, already torn_cmd.
  - **1 sits before it:** `171753`'s Knight (tap 1768, drop 1770 -> 1773). Moved to 1770, its onset moves to 1789; still
    open.
  - `004031`'s press shares its drop with our Skeletons (3 elixir = 2 + 1). The pair is now kept when the drop minus
    the costs of the plays in the pair is still >= 1.5 elixir. `004031` is exact.
- **Rascals, 010613@2186: the case `bp_rules.rascals_point` leaves out.**
  - The girls stand on the back edge (y 31000), so the formation cannot be read from them.
  - Any play y at or past the edge gives crforge the game's formation (31000 / 31499 / 31508 / 31768 all identical),
    so y = the edge.
  - Two plays move: `010613` (now exact) and `004901` (stays exact).
- **Not extractor (b):** `181217`. The hero Mini PEKKA leaves the reader's unit list at 3041, 2 frames after its cast
  timer starts; crforge keeps it. That is a representation or crforge question.
- **`224856` (hero Goblins second wave) is not traced.**

# A2c-BP3: the near-node rebuild census and the body-position singles (pod 32657)

**Base: bp2c reproduced (a).** `bp2/runB.sh bp3R0 bp2/in_press lib_bp2 SME_BP_FITNEXT=1` against bp2c: 79 / 109 -> 79 / 109,
246,887 -> 246,887 exact frames, 0 regressions, 0 gained.

## Instrumentation: fork patch 0003 MoveProbe (a)
- `fork/bp/clashbot-bp_0003_MoveProbe.patch` (branch `clashbot-bp3` c9889402 on 05533954, worktree
  `/workspace/pilot/bp3/crforge`; applied by `bp3/apply_moveprobe.py`). When `MoveProbe.CURRENT` is set it is told:
  - `disp`: every displacement (start point, aim point, budget, arrival bit);
  - `replan`: every ground route search (goal changed, held route kept, new route size / next node / the node after it,
    the held route's next node, goal node, held goal node, reference point, and the goal the reference's point at the
    start of the tick would give, computed by a probe-only `MovementQueries.probeEndpointFromTickStart`; the endpoint
    scan is pure there: no visitor, stateless predicates).
- Unset, nothing calls it. Core tests 2,140, 0 failures, 2 skipped. Traces of all 138 plans on lib_bp2 vs lib_bp3:
  138 identical, the same 2 GoblinDrill refusals (`results/live/bp3/trace_ident_bp3.txt`).
- Tracer `bp3/AimRun.java` (from BpRun by `bp3/mk_aimrun.py`): per tick the probe events and every character
  (id, name, side, x, y, hp, reference). Dossier tool `bp3/aim_one.py RUN MATCH T0 T1 [IDs]`.

## Item 1: every rebuild with a near node, crforge's aim vs the game (a)
`bp3/aim_census.py` on bp2c's plans (136 runnable): a search whose first displacement arrives at the new route's next
node in the same step. For each, the step toward two alternatives is computed: alt1 = the new route's next-but-one node
(the game pops the near node first), alt0 = the held route's next node (the game does not rebuild). An event counts
when (1) a pure step toward an alternative differs from the step toward crforge's aim and (2) the body matched a
recorded body exactly at the frame before. The outcome is read at the next frame: the recorded body sits at crforge's
point, or at the point moved by an alternative's difference (+-3 units), or neither.
Rows: `results/live/bp3/aim3_bp2c.jsonl.gz`; tables: `results/live/bp3/aim_census_bp2c.txt`.

| events | crforge | alt1 | alt0 | neither | gone |
|---|---:|---:|---:|---:|---:|
| 70,154 found; 50,051 deciding with an exact frame before | 49,495 | 41 | 26 | 326 | 163 |
| of those, in clean stretches (t <= first divergence) | **40,451** | 2 | 1 | 38 | 131 |

- **(c) "the game pops a near node before stepping" is contradicted:** in clean stretches the game follows crforge's
  aim at the near node 40,451 times; 3 events go the other way, and they are the onsets themselves (000233@4598/4599,
  180336@2910).
- **(c) "the game takes the reference where it stood at the start of the tick" (H4) is contradicted twice:**
  - scratch build `bp3/variant_h4.py` (not committed): of 41 matches finished, 23 exact matches diverge, 7 diverge
    earlier, 0 gain (`results/live/bp3/h4_partial_vs_bp2c.txt`; run stopped);
  - census: 6,979 clean events where the reference's own move earlier in the same tick is what changed the goal
    (`by_ref_move`: the tick-start goal equals the held goal) follow crforge; 2 do not (the onsets).
- **000233@4599 is a consequence, not the cause (a for the arithmetic, b for the cause).** Skeleton 5000119's goal
  flips from node 1215 to 1251 because its reference (skeleton 5000116, moved earlier in the step) puts cell 1251's
  centre 936.08 units away. The game's 5000116 is 2 units off at 4599 ((13703, 16313)), 938.18 units away. A range
  between those two values keeps the held goal, so there is no rebuild, which is the game's move toward the old node.
  The earlier onset is 5000116 itself at 4598-4599. No character is within 1,800 units (Manhattan) of it and there is no
  area. Yet its displacements run off the pure step (4597: (-18, 124) for a 90 budget). Hypothesis (b, untested): it is
  clamped along the bridge cell edge by GridMove. **Owed (b):** the skeleton's attack range (to confirm the 936 / 938
  window), and a census of bridge-edge clamps (GridMove proposal vs outcome on edge cells) in clean stretches.
- **No fork change** (no census evidence for one).

## Item 2: the singles, the combination that makes each one unique
- **164443@3213, Ram landing (a for the game's move).** From 3211 (exact), the game's Ram is exactly two pure 60 steps
  with **no push at 3212**: (9848, 17100) -> (9840, 17159) -> (9836, 17218) = the recorded point. crforge pushes
  the Ram (-16, -2) by the enemy Skeleton 5000058 on its first visit after the jump (3212). The skeleton's recorded push
  (148, 24) points from the Ram's point before its 3212 move (b: by hand (147, 24); crforge (149, 15) from its moved
  point). Combination: **first moving visit after a river-jump landing + an overlapping enemy ground body + a lander
  whose push from that body is not zero** (crforge's layer test `(ownerHeight > 0) == (other.zTotal < 1)`; the
  landing visit leaves the last arc sample's height until the next pre-hook). Earlier census: 7 clean contact
  landings (HogRider 5, RoyalHog 1, RoyalHog_EV1 1) vs this 1. **Owed:** for those 7, whether crforge pushed the lander
  on that visit (if it did and the game agreed, the subtype is the Ram's mass / attached rider).
- **180336@2910, Elite Archer hero (a for the event, b for the game).** A near-node rebuild whose goal change comes
  from the reference's (Knight 5000057) move earlier in the step. The census subtype holds 6,979 clean agreeing
  events, so this is not the combination. Neither alternative reproduces the game's (109, -38) two-step move
  (length 115 < 120; the archer stops at 2911 in both). **Owed:** the archer's stop-in-range point (attack range vs
  the moving Knight), dossier of 2911 with the targeting fields.
- **211239@1532, opponent hero IW (a for the timing).** Its target (our IW 5000022) dies at 1527 while it stands
  still (budget 0) 6,478 units from it. crforge moves it first at 1533 (replan to the princess tower); the recorded
  body moves at 1532, one tick earlier. Combination: **target death while the hero IW stands with a target out of
  attack range**. **Owed:** census of target-death -> first move delay per unit type (BpRun's targeting timers).
- **014928@5183, hero IW 29 units (a for the event).** Walking to the left bridge on route node (3250, 18750), no
  rebuild in crforge 5177-5189. The game turns about 16 degrees further down from 5182 (two-tick moves (35, -113),
  (26, -116), (21, -117), (17, -118)). No body within 2,500 units but its own cube; a same-side BarbLog
  released a Barbarian at (2500, 15000) at 5172 and it starts moving at 5184. Combination (b): **a ground route
  after a same-side BarbLog ends on the lane**. **Owed:** whether the game rebuilt at 5182 (a cost-overlay change from
  the log's end or the Barbarian's start) - MoveProbe replan census around every BarbLog end.

## Files (A2c-BP3)
`bp3/`: MoveProbe.java, apply_moveprobe.py, mk_aimrun.py, AimRun.java, aim_census.py, aim_one.py, aim_sum.py,
variant_h4.py (scratch). `fork/bp/clashbot-bp_0003_MoveProbe.patch`. `results/live/bp3/`. Pod 32657:
`/workspace/pilot/bp3/` (lib_bp3, build_aim, lib_h4 scratch), `/workspace/pilot/sme_live/bp3R0` (repro), `bp3h4`
(partial, scratch).

# A2c-M: the crforge / unknown-mechanics cluster (worker a2cm, pod 33308)

Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted.

Baseline: `m0` is r6xc rerun on pod 33308 (inputs_v14, repr_v2, comparator flags as r6xc, MIXPH + SNAP). It equals
r6xc exactly: **79 / 109, 256,184 exact frames**, the same torn counts (a). Runs live in `/workspace/mech/` on 33308
(`run_m.sh`). m2 and m3 re-ran only the matches their change touches (`m2`: the 15 matches whose inputs changed; `m3`:
the 60 matches not exact in m1 or touched by m2). The other rows were merged from the run before, because a match's
result depends only on its own inputs, and CROSS only re-classes div frames after the repair.

| run | mechanism | layer | change | exact apart from torn (unflagged) | exact frames | regressions | gained |
|---|---|---|---|---:|---:|---|---|
| m0 | | | r6xc rerun | 79 / 109 | 256,184 | | |
| **m1** | evolved Goblin Barrel point; Goblin Drill dig start; hero Balloon throw dating | extractor | `mech_rules` SME_MECH_GB + DRILL + HB | **83 / 109** | **260,224** | 0 | `165839`, `041602`, `235355`, `235915` |
| m2 | Zap dated from its ZapFreeze buff | extractor | SME_MECH_ZAP | 83 / 109 | 260,224 | 0 | 0 |
| **m3** | a body crossed between t and t+1 in an in-step read | comparator | `mech_torn` SME_MECH_CROSS | **84 / 109** | 260,224 | 0 | `192935` |

**Net: 79 -> 84 / 109, +4,040 exact frames, 0 regressions in each step (a).** The match crforge refused (`225213`)
now runs. **No crforge patch:** no case in this cluster was traced to crforge's mechanics. The fork branch
`clashbot-mech` (pod 33308 `/workspace/crforge_mech`, cut from `008aa626`) has no commits, so core tests were not re-run.

## Evolved Goblin Barrel decoy (`165839`@2539, `041602`@2276): the play point, not the decoy (c for crforge)
- **The game's flights:** both barrels start at the king's centre and fly to x = 9000 ± d. At 041602 they move
  (95, 388) a tick from (9000, 3000), toward 14500 and 3500.
- **crforge has the same rule:** the decoy is thrown from the barrel's start to `18000 - aimX`
  (ActionMirroredExtraSpell, BattleEvolutionTest).
- **The cause is the extractor's point.** It averaged the two barrels into x = 9000, so crforge threw both
  barrels almost straight ahead.
- **How the real barrel is told apart:** it lands Goblins (323 hp) and the decoy lands GoblinDummy (130 hp), under one
  reader card id.
- **Rule SME_MECH_GB:** when two mirrored barrel projectiles show, x becomes the mean x of the landing group with the
  higher hp.
  - It changes 2 of the 45 Goblin Barrel plays, the only evolved ones: 9000 -> 6499 and 9000 -> 14500.
  - **Both matches become exact (a)**, decoy flights included, so crforge's decoy is right.

## `225213` refused by crforge: the evolved Goblin Drill's point was its dig start (a)
- **Why crforge refused:** the play at 2415 was given at (9228, 28177), on the player's own king. That is where the
  reader first shows the evolved drill's dig body (card 13000108, kind 15) leaving the king.
- **Why the extractor missed the surface:** `drill_surface` found none for this evolved drill, so the point stayed.
  The drill surfaced at (4000, 9000) on 2487.
- **What followed:** crforge refused the play at its placement. The next Goblin Drill play then hit
  `checkCountKnown`: "after a play of it refused at its placement ... not modelled".
- **Rule SME_MECH_DRILL:** a drill play within 2000 of a king takes the first kind-12 drill row of its side within
  150 ticks.
  - 2 plays change: `225213`@2415 and `174147`@2496. 174147 is flagged and was the other refused match.
  - **Both matches now run (a).**
- **225213's new first divergence is 3588, not a drill:**
  - our elixir is 2.0 below the sim's, our hand is unchanged, and our hero Ice Wizard is 13 / 8 units off;
  - no Ice Wizard ability is in the inputs after 3061;
  - so it is an own Ice Wizard press that was not extracted (b; it belongs to the own-press rules, not mine).

## Hero Balloon throw (`235355`@2681; also fixes `235915`): extractor dating (a)
- **crforge:** it shows `BalloonHero_Skeletrooper_Projectile` first on line R+3 on 9 / 9 casts (`hb_census.py`).
- **The game:** the reader shows the throw as a moving projectile row of card 203000006.
  - On 6 casts, the first sighting minus (R+3) is 0 or +1, which is the frame sampling.
  - The others are -9, -1 and +2.
- **Why the dating is off:** `seen_casts` dates the cast from the trooper's landing with RoyaleSim's flight speeds.
- **Rule SME_MECH_HB:** R = (first frame with the throw) - 3, with the window back to the frame before.
  - 5 of 11 windows change.
  - **235355 and 235915 become exact (a).**
  - The table's reading of 235355 ("Balloon death bomb, a no-hp character dropped by repr") is **(c) contradicted**:
    the balloon is alive, at 2046 hp, and the projectile is the throw.

## Zap: dating confirmed but no gain; two Zaps never extracted (`204518`@723, `010245`@573)
- **Dating (a):** a Zap puts ZapFreeze (500 ms) on everything it hits, so the buff's made tick c is exact.
  - crforge, given the Zap at run R, hits on line R+1 with a fresh buff, so R = c - 1.
  - Of the 36 extracted Zaps (`a2cm_zap_census.txt`), 22 sit at c - 1 and 12 at c - 2.
  - Every Zap the SME repair had moved went to c - 1.
  - With SME_MECH_ZAP, `001702`'s evolved Knight is exact at 2492: it was 60 units off.
- **No match gained:** 001702 still diverges at 2492, on a Skeleton.
  - That Zap is `inferred` (no area row), at the point (2300, 17836). The game's Zap killed a Skeleton at
    (3106, 14059), which lies outside the sim's area.
  - So the inferred point is about 1000+ units off (b).
- **The 2 missed Zaps (a):**
  - 204518@723: our X-Bow takes ZapFreeze (450 ms left, made 722) and 306 damage.
  - 010245@573: our princess tower takes ZapFreeze and 77 damage, Zap's tower damage (77 on all 13 tower hits of
    extracted Zaps).
  - Neither match has a Zap play, and the reader showed no Zap area.
  - That accounts for the X-Bow's 306 and the tower's 77 in the table.
- **Why they are not added (b):** 951 ZapFreeze groups in the 138 matches have no extracted Zap. Other sources give
  the same damage, for example 204518@1077 / 1119 (306 on a princess tower, which a Zap would hit for 77). A rule
  needs a discriminator, such as a sim check in the repair stage. Not done.

## `192935`@382: a read between the game's per-entity updates (a); comparator rule SME_MECH_CROSS
- **What the frame shows:**
  - our Knight at its t point with its t+1 hp (the Mega Knight's 429 already taken);
  - every other object at t, our elixir t's;
  - the X-Bow bolt removed, but the Mega Knight it hits not yet damaged;
  - the next frames exact. It is the match's only div frame.
- **Why SnapRun cannot match it:** crforge's in-step states move every body before any hit. `EntityHolder.tick` runs
  its passes slot by slot (the snapdiff shows the impact state with all bodies moved).
- **Rule:** an isolated div frame where every object is a sim t / t+1 tuple, or the cross (t position, t+1 hp) /
  (t+1 position, t hp) of one sim body present on both lines. Our elixir and hand are checked as in torn_mixed.
- **Planted checks (`mech_torn_test.py`): 13 / 13 caught.**
  - The crossed rows hp ±1, x+1, y-1, or another body's t+1 hp.
  - Our elixir +1, an extra projectile, another body moved 1 unit.
- **It re-classes exactly 1 frame in the 60 matches it ran on.**

## Not fixed: evidence for the next owner
- **`222712`@4183 ("Earthquake pulse") is two things:**
  - The frame is an in-step read of 4184: our elixir is sim 4184's, and our hero IW cube still sits on its deploy
    point. The reader does not show EarthquakeHiddenDamage there yet; it shows it from 4186.
  - A Skeleton next to our hero IW deploy at (499, 18499) is pushed further in the game. The game moves it
    1655 -> 1803 by that read; the sim moves it 1655 -> 1730 -> 1773 -> 1802 over 4183-4185.
  - The (30, -33) offset persists through 4186-4191. That points at crforge's deploy-overlap push profile
    (b, crforge candidate; a census of deploy pushes is owed).
- **`172835`@2831:** crforge's Knight swerves for 2 ticks, (16, -48) and (26, -43) instead of (36, -35), at the tick
  the WitchMother takes 429 and starts moving. The game's Knight walks straight. No body is within 4500 of it. It is
  a target or route change (b; it needs the BpRun target trace).
- **`001141`@5399:** the game's Golden Knight dashes 5399 -> 5401 (791 units in 2 ticks), with no GoldenKnightCharge
  buff and no GK ability in inputs_v14 between 5350 and 5450. crforge's walking GK takes an X-Bow bolt (-98) that the
  dashing one does not. It is a missed GK dash cast (b; bp_rules GK owner).
- **`000233`:** skipped (BP2).

## Files (A2c-M)
- Code:
  - `mech_rules.py`: input rules, the same hook shape as bp_rules; `mech_inputs.py` applies them to an inputs file.
  - `mech_torn.py` and `mech_torn_test.py`: the CROSS rule and its planted checks.
  - `mech_hooks.diff`: the two hooks for the extract.py / sme_live.py owners to merge.
- Tools:
  - `near.py` (rec vs sim rows near a point), `snapdiff.py` (frame vs crforge's in-step states);
  - `hb_census.py`, `buff_census.py` (buff casts against plays, with hp drops).
- Results: `results/live/a2cm_m{1,2,3}_{cmp.txt,results.jsonl}`, `results/live/a2cm_zap_census.txt`.
- Pod 33308 `/workspace/mech/`:
  - `in_m1` = inputs_v14 with GB + DRILL + HB; `in_m2` = in_m1 with ZAP;
  - `sme_m/` is a copy of pilot/sme with the CROSS hook.

---

# A2c-BP4: the four owed body-position censuses (pod 32657)

**Base: r78 reproduced exactly (a).** a2c6's r78 config (chain7.sh on 33920: inputs_v19, every comparator flag, SnapRun2
`build_snap2b`, FITNEXT) copied to 32657 `/workspace/pilot/bp4/from33920`; `bp4/runR.sh bp4R0 lib_bp3 inputs_v19` on
the MoveProbe build: results.jsonl byte-identical to r78 (sorted), **88 / 109**, 261,135 exact frames, 0 regressions,
0 gained. All censuses below run on bp4R0's plans (136 runnable).

**No crforge mechanic change and no extractor / comparator rule** in this ticket: no census supports one (below), so
nothing beyond the repro is measured on the 109. (The F635c base `clashbot-up-e5462c82` landed meanwhile; a mechanic
patch would have to sit on it; none was made.)

## Instrumentation: fork patch 0004 (a)
`fork/bp/clashbot-bp_0004_MoveProbe4.patch` (branch `clashbot-bp4` dddef00d on clashbot-bp3 c9889402, applied by
`bp4/apply_probe4.py`). MoveProbe is also told:
- `prop` (in Displacement, before GridMove): proposal after the blend, the push added, push count, blend, groundPushed,
  stuck, the proposal GridMove gets, the point after GridMove;
- `push` (in PushPass, per neighbour that pushes): other id, dx, dy, reach, magnitude, other mass, other radius, moves
  bit, push x / y added, mass term, own mass;
- `replan` gains the scan radius R, the goal at R-25 / -50 / -75 / -100 and the goal with the reference at its cell's
  centre (probe-only `MovementQueries.probeEndpointAt`, a pure scan).

Unset, nothing calls it. Core tests 2,140, 0 failures, 2 skipped (`results/live/bp4/coretest_bp4.txt`); SmeRun traces of
all 138 bp4R0 plans on lib_bp3 vs lib_bp4: 138 identical, the same 2 GoblinDrill refusals in both
(`trace_ident_bp4.txt`). Tracer `bp4/AimRun4.java` (`mk_aimrun4.py`): AimRun plus state, z and targeting timers per
character and every projectile / area per tick. Dossier tools: `bp4/ent.py` (SmeRun rows by id) and
`bp3/tools/aim_one.py` with `LIB=lib_bp4`.

## Item 1: 000233@4599, skeleton 5000116 "2 units off" (a for the cause, b for why)
- **(c) The bridge-edge clamp hypothesis is contradicted.** 5000116's off-step move is a push from its sibling Skeleton
  5000117 (same play, 960 units away, reach 1,000 = 500 + 500, overlap 40 -> (-21, 34) at 4597; (-1, 1) at 4598;
  (-2, 4) at 4599). BP3's "no character within 1,800 units" missed it, and BP2's "no push" was wrong. GridMove
  returned start + proposal on every one of these steps (`prop`).
- **The skeleton's scan range is 1,000** (range 500 + own radius 500, `AttackRange.attackRangeWithRadius`; probe value).
- **(a) The game's two-tick move is reproduced exactly** by crforge's pushes with the aim (13750, 17250) at both 4598 and
  4599 (enumeration over 12 x 12 node aims and push variants; one match). That aim is the held route's next node: the
  game did not re-goal 5000116 at 4598, while crforge's goal flips 1497 -> 1498 (new cell 962.76 from reference 5000119,
  inside R = 1,000). 5000119@4599 is the same event the other way (936.08).
- **Census `bp4/goal_census.py`** (every goal change with a held route whose first step differs from the held-node step;
  `goal_bp4R0.log`): 25,808 clean deciding events, **25,804 follow crforge, 4 keep the held route** (000233@4598,
  000233@4599, 180336@2910, 101112@5923). Each alternative endpoint rule is contradicted (c). Counts are clean events
  where the variant keeps the held goal but the game follows crforge's change: tick-start reference 7,117; R-25 4,705;
  R-50 9,091; R-75 11,004; R-100 11,402; reference cell centre 4,870.
- **(c) Re-aiming at a node already popped is fine:** `repop_census.py` finds 27,724 clean events where the rebuilt
  route's next node is one the unit reached within 30 ticks, and all follow crforge except 2 that go to the node after
  (the 000233 pair).
- **(c) Order, margin, timing and mutual targeting do not separate the 4:** within "side-1 unit, side-0 reference that
  moved earlier in the tick", 3,650 follow crforge (`bp4/gsum2.py`); with new-goal margin R - d < 10, 1,039 follow
  crforge; 1 tick after the reference changed, 1,126 follow crforge; with mutual targeting, 8,560 follow crforge.
- **GridMove clamp census (`clamp_census.py`, as owed):** 4,479 clean clamps with an exact frame before, 835 of them in
  the river rows 30-33. All follow crforge except 1 skeleton (100018@368, `neither`) and 1 MegaKnight that is unclamped
  in the game (211757@3477, a jump frame). Bridge edges agree (a).
- Open (b): what keeps the game's goal at 4598. Not tested yet: the reference point as the game's targeting stored it
  for a reference retargeted in the same tick (both skeletons retargeted at 4597).

## Item 2: 164443@3213, Ram landing (a for the mechanism, b for the cause)
- **(a) Both of the game's bodies are reproduced by "the Skeleton's push pass ran before the Ram moved".** The
  Skeleton's recorded push (148, 24) is exactly the Ram's push from its pre-move point (9848, 17100): overlap 66 x mass
  4 = 264, +1, clamped to 150. After that push the Skeleton stands 1,168 units from the Ram in x (> reach 1,100), so
  the Ram is not pushed and walks two pure 60 steps to the recorded point. crforge visits the Ram (5000055) before the
  Skeleton (5000058).
- **Landing census `land_census.py`:** 116 clean pushed visits after a JUMPING exit, and all follow crforge except the
  Ram. With an enemy pusher at k = 1, HogRider 6, RoyalHog 1 and RoyalHog_EV1 2 follow crforge and the Ram 1 does not.
  So "crforge pushes the lander on its first visit" is right (a).
- **Order census `order_census.py`** (B pushed by an A that moved earlier in the tick; the push replica is checked against
  the probe and 2,123 visits where it does not match are skipped). Clean, exact before: **70,318 follow crforge's
  interleaved order, 1 follows the pre-move point (the Ram)**.
  - Attacking B with a cross-side mover: 2,857 follow crforge, against that 1.
  - Cross-side landers at k <= 3: HogRider 4 and RoyalHog 2 follow crforge (034147@507/508: HogRider 5000012 before
    Skeleton 5000013, both exact).
  - The Ram (RamRider mount; its rider 5000054 is listed before it) as an earlier mover elsewhere: Skeleton 32, Knight
    14 and Barbarian 1 follow crforge.
- Open (b): why the game runs this Ram after the Skeleton on its first visit after landing. The 138 matches hold only
  one RamRider landing with a discriminating push, so no census can test a Ram-only order rule.

## Item 3: 211239@1532, hero IW first move after its target's death (a for the census)
`death_census.py`: the unit held reference R at t-1, R is gone at t, and the unit stood still for 3 ticks and was exact
before.
- 6,082 clean events: **6,071 crforge, 5 earlier (the game moved one tick sooner), 6 neither**. Every "earlier" event
  has delay 6 and a direct kill (no enemy projectile or area near R): Bat 170600@2152, Knight_EV1 171232@5586, Knight
  172314@1783, hero IW + cube 211239@1527. Delay 6 with a direct kill: 2,047 follow crforge.
- Hero IW: 553 follow crforge at delay 1 and 222 at delay 6 (116 of them out of range, > 5,500); 1 is earlier (211239).
- (c) Not separating: whether the unit is visited before or after R (u_before_r), load timer > 0, death cause class.
- Open (b): the 5 delay-6 direct kills. Next: who made the kill and where the kill falls in the tick (needs a damage
  probe).

## Item 4: 014928@5183, hero IW turn after a Barbarian Barrel end (a for the census)
`barb_census.py` (RAD 12,000, WIN 30; `barb12_bp4R0.log`): 350 log ends, 1,023 unit windows.
- Same-side walkers on the lane, clean: 365 stay exact through the window (162 of them with no crforge replan). 5
  diverge: 2 are air units (BalloonHero, BabyDragon) and 3 replanned in crforge.
- 014928's hero IW 5000218 (no crforge replan, div 5183) is the only ground walker without a replan that diverges.
- The Barbarian (5000220) leaves the log at 5165 at (2500, 15000) and stands until 5184 in crforge; the game's IW turns
  from 5182. Hypothesis (b, untested): its deploy end changes the friendly occlusion overlay a tick or two earlier in the
  game than in crforge, and the IW rebuilds. Census owed: every same-side ground deploy end against walkers' overlay
  replans.

## 180336@2910
In the goal census it is one of the 4 "kept" events: Elite Archer hero, R 7,600, new goal 7,573.22 from Knight 5000057,
which moved earlier in the tick. Margin, order, timing and mutual targeting do not separate it (item 1). It stays in
item 1's open class with 000233 and 101112@5923 (b).

## Files (A2c-BP4)
- `bp4/`: apply_probe4.py, AimRun4.java, mk_aimrun4.py, ent.py, runR.sh, verify4.sh, goal_census.py, gsum2.py,
  repop_census.py, clamp_census.py, land_census.py, order_census.py, death_census.py, barb_census.py.
- `fork/bp/clashbot-bp_0004_MoveProbe4.patch`.
- `results/live/bp4/`: rows (.jsonl.gz), summaries (.log), coretest, trace identity.
- Pod 32657: `/workspace/pilot/bp4/` (lib_bp4, build_aim4, from33920, a2c6/r78) and `/workspace/pilot/sme_live/bp4R0`.

# A2c-BP5: the last body-position singles (pod 32657)

Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted. All censuses run on bp4R0's plans (136
runnable; bp4R0 = r78, 88 / 109).

**No crforge mechanic change, no extractor or comparator rule:** no census below supports one, so nothing is measured on
the 109 beyond the instrumentation identity. Combined state unchanged: r78 = 88 / 109.

## Base: probes 0001-0004 ported onto F635c `clashbot-up-e5462c82` (a)
- Pod 32657, worktree `/workspace/pilot/bp5/crforge`, branch `clashbot-bp5`: bec5811a (bundled from 30408) + 0001-0004
  by `git am -3`, clean (334c1d63, fdc6f68d, 277028c4, 0d086747), + **0005** (fabb2fe7, below).
- Core tests (`bp5/ct.sh`, `-Pcrforge.dataVersion`): **16.402.22 2182/0 (29 skipped), 16.635.3 2182/0 (6 skipped)**, on
  0001-0004 (`ct_bp5.out`) and on 0001-0005 (`ct_bp5k.out`); the same counts as the F635c head.
- Traces of all 138 bp4R0 plans, lib_bp4 (old base + 0001-0004) vs lib_bp5 and vs lib_bp5k: **138 identical** each, the
  same 2 GoblinDrill refusals (`trace_ident_bp5.txt`, `trace_ident_bp5k.txt`). So the F635c base plays r78 exactly.
- **Fork patch 0005** `fork/bp/clashbot-bp_0005_DmgProbe.patch` (`bp5/apply_probe5.py`): MoveProbe point `dmg` in
  `BattleWorld.dealDamage` (target, attacker, damage, died). Instrumentation only; unset, nothing calls it.

## Tracers (no fork change; `bp5/mk_aimrun*.py` write them from `bp4/AimRun4.java`)
- AimRun5: on every `replan`, `rpx` = the endpoint goal with the reference at its point at the end of t-1 .. t-6 and at
  the unit's acquisition replan (computed in the callback: unit not yet moved, this tick's grid).
- AimRun6 / 7: `srch` (full crforge search from the unit's cell and its 8 neighbours to a goal), `held` (held route),
  `epc` (every qualifying endpoint cell with rank and distances), on env-selected unit / ticks.
- AimRun8: a WorldObserver (`hit`, `rm`) in the same ordered event list as the probe events.
- AimRun9: at every displacement of a unit holding a ground route of 2+ nodes, a fresh search from its start cell to the
  held goal; `fr` when its next node is not the node crforge stepped toward.

## Item 1: the "kept old route" subtype (000233 x2, 180336@2910, 101112@5923)
`goal6.py` (bp4 goal census + rpx + order / state features) reproduces bp4: 25,808 clean deciding events, 25,804 crforge,
the same 4 kept (`goal6.log`).
- **(c) Lagged reference.** Goal with the reference where it stood at the end of t-k; clean events where the variant
  keeps the held goal but the game follows crforge's change (`g5sum.log`): k=1 7,117; k=2 12,722; k=3 10,367;
  k=4 8,246; k=5 6,200; k=6 4,622. k=2 keeps all 4 and is the most contradicted.
- **(c) Reference frozen at acquisition.** The acquisition-time point keeps all 4 (a) but contradicts 3,512 clean
  events, 1,862 of them within 1-3 ticks of the acquisition (age 1: 801, 2: 614, 3: 447).
- **(a) What the 4 share:** the unit acquired this reference 1-3 ticks before (and replanned then), the held goal is
  still inside R, and the new goal is a neighbour cell of the held one.
- **(c) None of these separates.** Inside "age 1-3 and the acquisition goal is the held one" (1,866 events) each split
  has hundreds following crforge (`g6sep.log`, crforge / kept):
  - the reference displaced earlier in the step 870 / 3;
  - the reference replanned earlier in the step 238 / 1;
  - mutual targeting 730 / 3;
  - the reference retargeted in the same tick as the unit 457 / 3;
  - the unit before the reference in holder order 973 / 1;
  - the tick-start reference keeps the goal 869 / 3;
  - the unit in state 1: 1,862 / 4; the unit's timers all zero 1,657 / 4;
  - a neighbour-cell goal change 1,780 / 4.
- Open (b): the cause. Not tested yet: the endpoint scan with the unit's position other than at visit start, and the
  route search from a cell other than the unit's (both need the variant inside the engine, replayed per event).

## Item 2: 211239 and the four other delay-6 "earlier" moves (kill attribution)
`death5.py` (bp4 death census on AimRun8 + lib_bp5k) reproduces bp4: 6,082 clean, 6,071 crforge, 5 earlier, 6 neither.
Kill attribution for the 2,052 delay-6 direct kills (`d5sum.log`):
- **(a) Killers of the 5:**
  - 170600: the Bat killed the Skeleton itself (direct hit);
  - 172314: the Knight killed the Skeleton itself;
  - 171232: the ElixirGolem4 was killed by a projectile impact;
  - 211239: our hero IW (and so the cube's reference) was killed by the opponent's Pekka (5000025, 1,345 damage, direct).
  - Every kill lands in the damage drain, after U's visit.
- **(c) Not separating** (crforge-following delay-6 direct kills with the same value):
  - hit kind dmg 1,638;
  - killer = U 955;
  - killer visited after U in the step 1,163; after U in holder order 1,321;
  - R after U in holder order 932;
  - killing hit after U's events 1,653;
  - U attacking (state 2) 2,046; U load timer > 0 1,270;
  - U's attack timer one tick before its HitSpeed (Bat, Knight) 545 (`bp5/d5hs.py`).
- **(a) The game's R is not removed earlier:** 211239's recorded R is alive at 1526 (hp 528) and gone at 1528, which fits
  crforge's kill at 1527.
- Open (b): what moves U one tick sooner. The recorded frames are 2 ticks apart, so the game's kill tick and first-move
  tick are each known only to within 2 ticks; frames every tick around the 5 would be needed.

## Item 3: 014928@5183 (hero IW turn after a Barbarian Barrel)
- **(c) "The Barbarian from the Barbarian Barrel finishes deploying earlier in the game" is contradicted.**
  - `deploy_census.py`, first move: crforge's first tick off the spawn point, against the frames around the game's last
    frame with the body on it. **Every BarbLog Barbarian agrees, 107 / 107**; all clean spawned units: 7,473 agree,
    3 earlier.
  - 014928's Barbarian 5000220 is exact at 5183 and 5185 and moves first at 5184 in both.
  - The frame code 14 is not the deploy state: it ends before crforge's deploy end for 1,875 units whose first move
    still agrees (`deploy.log`).
- **(a) The game's turn is a fresh route search from the IW's cell at 5182.**
  - Aim fit (`bp5/aimfit.py`) of the game's 2-tick moves: 5181 -> 5183 = aims (2750,19250) then (2750,18750); then
    (2750,18750) twice; then (2750,18750), (2750,18250).
  - crforge's search from the IW's cell (4,39) at 5182 to its goal 871 (`srch`) ends ... 1301, 1337, 1373: exactly those
    nodes. crforge's held route (searched at 5146 from another cell) ends ... 1302, 1338 (equal cost, one column right).
  - The game then stops at 5196-5197, 6,580 from our X-Bow; crforge stops at 5198-5199, 6,574 from it (the same
    acquisition range, reached later on the longer route).
- **(c) "The game re-searches when the unit enters a new cell" is contradicted** (`fresh_census.py`, `fresh.log`). Clean
  events where a fresh search would step elsewhere and a frame decides:
  - 280,123 follow the held route with no cell change; **53,658 follow it with a cell change**;
  - 1 follows the fresh route (001141@5399, GoldenKnight);
  - 014928@5182 falls between frames, so the census does not decide it.
- **(c) A deploying unit as an occluder** (scratch `GridEntity.occludesCells` variant, not committed): the side-1 hash
  changes at 5163 and 5184 and crforge re-searches, but retention keeps the held route both times; the IW is unchanged.
- **(a)** The IW's goal 871 is the first plain cell: 868-870 are rank 1 under our X-Bow's footprint (`epc`). Nothing in
  crforge changes at 5182: no birth, death, state change, projectile or area near the lane.
- Open (b): what triggers the game's re-search at 5182 (a goal change by one cell, or an overlay-hash change that
  retention lets through).

## Files (A2c-BP5)
- `bp5/`: the scripts above; `build.sh`, `ct.sh`, `aim4.py` (runner), dossiers `dos.py`, `ev.py`, `kev.py`, `fr.py`,
  `born.py`, `pa.py`.
- `fork/bp/clashbot-bp_0005_DmgProbe.patch`. `results/live/bp5/`.
- Pod 32657 `/workspace/pilot/bp5/`: worktree `crforge` (branch clashbot-bp5), lib_bp5, lib_bp5k, build_aim5-9,
  `fresh_bp4R0.jsonl.gz` (4.5 MB rows, not copied), scratch `crforge_v` / lib_vdep.

# A2c-BP6: engine variants (a) unit position for the goal, (b) search start cell; replayed per event (pod 32657)

Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted. All censuses on bp4R0's plans (136 runnable,
= r78, 88 / 109), engine lib_bp5k (F635c + probes 0001-0005). **No crforge mechanic change**: no variant below keeps the
targets without contradicting thousands of clean events, so nothing was patched or measured on the 109. Combined state
unchanged: r78 = 88 / 109.

## Machinery: AimRun10 (in-tracer engine variants, `bp6/mk_aimrun10.py`, census `bp6/var_census.py`)
At every MoveProbe `disp` of a ground unit (start point, aim, budget; the callback runs after the step, so the end point is
known) the tracer replays the variant decision with this tick's grid and the unit's real queries (`GridMovementQueries.search`,
the endpoint scan re-implemented as `ReferenceEndpoint.selectEndpoint` with the unit point as a parameter; checked against
crforge's own goal on every disp, 6,935 mismatching disps skipped: explicit / game-mode goals). An event is a variant whose
predicted node gives a pure step other than crforge's; outcome at the first recorded frame >= t with the unit exact at the frame
before: `crforge`, `var` (recorded body within 3 units of the sim point moved by the step difference), `neither`, `gone`.
1,467,229 events, 1,164,174 clean with an exact frame before (`results/live/bp6/var.log`; rows of the targets and every `var`
outcome: `var_targets.jsonl`; all rows on the pod, `var_bp4R0.jsonl.gz`, 18.7 MB).

## (a) Goal from another unit position: (c), all six
| variant (unit point for the endpoint scan) | clean crforge | var | kept targets |
|---|---:|---:|---|
| 1 end of t-1 (before this tick's pushes) | 5 | 0 | none |
| 2 end of t-2 | 5,189 | 0 | none |
| 3 end of this tick's move (after its push) | 5,003 | 0 | none |
| 4 midpoint of start and end | 2,444 | 0 | none |
| 5 start + (e1 - e2), extrapolated | 5,323 | 0 | none |
| 6 start cell's centre | 5,880 | 0 | none |
| 7 unit and reference both at end of t-1 | 7,386 | 3 | 101112@5923, 180336@2910, 000233@4599 |

- In all 4 kept events, every unit-position variant gives crforge's new goal: the goal flip comes from the **reference's** point,
  not the unit's (a). Only 7 (reference lagged, as BP5's k=1) keeps 3; 000233@4598 needs the reference at end of t-2 (lag set {2}).
- **(c) A periodic refresh of the reference point** (`bp6/lagphase.py` on goal6 rows; lag = phase of a period P = 2..6 keyed by
  absolute tick, ticks since acquisition, or unit id): best fit leaves >= 5,197 events inconsistent for every P and key
  (`lagphase.log`; the 4 kept need lags {1-5}, {1-6}, {2}, {1-5}).
- **(c) Swap-remove update order** (the game moving its last entity into a dead entity's slot, so the unit runs before its
  reference; `bp6/swap_test.py`, `swap.log`): where it reorders unit and reference, the reference-at-e1 prediction keeps the held
  goal in 1,507 clean events (all characters + projectiles + areas) or 1,527 (characters only), and the game follows crforge's
  change in 1,506 / 1,525 of them.

## (b) Route searched from another cell: (c), all fourteen
| start cell | clean crforge | var | kept targets |
|---|---:|---:|---|
| 1 cell at end of t-1 | 6 | 0 | none |
| 2 nearest-centre rounding ((x+250)/500) | 33,256 | 0 | none |
| 3 held route's next node (cell being entered) | 25,798 | 3 | 000233@4598, 000233@4599, 101112@5923 |
| 4 previous distinct aim node | 27,417 | 2 | 000233@4599, 101112@5923 |
| 5 cell at end of this tick's move | 7,200 | 0 | none |
| 6-13 the 8 neighbours of the start cell | 38,280 - 49,836 each | 0-1 | 000233@4598 (11, 12), 4599 (8) |
| 14 last node reached (arrival bit) | 28,819 | 3 | 000233@4598, 000233@4599, 101112@5923 |

- Shadow routes (each variant route held and aligned with crforge's route by nodes walked since the search, first difference
  reported) cover the route-tail case. At 014928's 5146 search the variants that exist there (2, 5, 6-13; the unit had no held
  route or reached node, and its e1 cell is its own) all differ at the first step, where the game is exact; none reproduces the
  5182 turn.
- (a) All 4 kept events re-aim at a node the unit popped 1-3 ticks before (000233 1215 and 1534, 101112 1180, 180336 1228);
  variants 3 / 14 keep 3 of them, but BP4's repop census already holds 27,676 clean goal-change re-aims that the game follows.

## 014928@5182: what triggers the re-search (b open; two triggers contradicted)
- `fr2` (a fresh search from the start cell to the held goal on every disp; 642,288 clean follow the held route, **2 follow the
  fresh one: 001141@5398 / 5399 GoldenKnight, step difference (1, 4) only**, 241 neither). 014928@5182 is `neither` here: its
  2-tick frame holds two aims (1373, then 1337 after the pop), so one-step tests cannot decide it.
- **(c) "Re-search when the unit enters a cell off its route"**: 014928's start cell 1408 is not on the route searched at 5146
  and was entered at the 5182 visit; clean events with the same flags (off-route, cell changed) 37,796 + 1,262 follow the held
  route, 0 the fresh one.
- **No sub-tick evidence (a):** the IW does not attack from 5146 to 5198 (timers 0, state 1), its and its cube's hp are constant,
  and no projectile or area comes from or near it; frames 5181 (exact) and 5183 bound the re-search to the 5182 visit.
- **(b) Owed:** crforge ends the BarbLog Barbarian's deploy at 5183 (state 4 -> 1), and the recording's code 14 -> 15 also falls
  between 5181 and 5183. If the game ended it at 5182, it coincides with the turn. A same-side deploy end as a re-search trigger
  (not an occluder hash change: BP5's VDEP variant moved the hash at 5184 and retention kept the route) is untested: it needs a
  census of every same-side deploy end against ground walkers' fresh-search events, then a scratch build. The GoldenKnight
  (001141@5398) re-search follows its slow by the enemy hero IW cube (budget 60 -> 42 at 5397); 014928's IW has no speed change at
  5182, so a speed-change trigger does not cover both (a).

## Files (A2c-BP6)
- `bp6/`: mk_aimrun10.py (AimRun10 from bp5 AimRun5), var_census.py, evd.py (event dossier), lagphase.py, swap_test.py.
- `results/live/bp6/`: var.log, var_targets.jsonl, lagphase.log, swap.log.
- Pod 32657 `/workspace/pilot/bp6/`: AimRun10.java, build_aim10, var_bp4R0.jsonl(.gz), work/all (AimRun5 traces of 136 matches).

---

# Fix loop round 8 (worker a2c8)

Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted.

**Base reproduced (a).** On pod 33920:
- r8r0 (r78's chain on `lib_bp2`) is byte-identical to r78 (`results.jsonl` sha256 `145731fe9d9d446c`).
- **r8f0 on the new crforge base F635c** is byte-identical to r78 too. That base is `clashbot-up-e5462c82` @ bec5811a +
  TickProbe 0001 + 0002, copied from pod 30408's `lib_up2snap` (core jar sha256 `3db370f4fa878c03`) to
  `/workspace/pilot/lib_f635c` on 33920 and 33308. Every run below uses it.
- inputs_v19 regenerated on the laptop with the round-7 flag set (UNIT_HP IW_DEPLOY IW_AREA HERO7 OWNPLAY7 RASCAL7 GOLEM7
  OWN_CAST BP_VALK BP_GK BP_GIANT BP_RASCALS BP_PRESS) is byte-identical to the pod's v19 (sha256 `863006cdb1fceeab`).

**Code.** Runs use `/workspace/pilot/sme8` (this tree's sme with the round-8 code) and `sme_live/run8.sh`, with r78's
comparator flags plus the extras in each row.
- **Identity check r80 (a):** sme8 code (A2c-M hooks, HIDDEN, BANNER and GK8 code in, all flags off) on v19 with
  F635c is byte-identical to r78.
- With every new flag off, `extract.py` regenerates v19 byte for byte.

| sub-round | class | layer | change | exact apart from torn (unflagged) | exact frames | gained |
|---|---|---|---|---:|---:|---|
| start (r78 = r8r0 = r8f0 = r80) | | | | 88 / 109 | 261,135 | |
| **8.1 (r81)** | A2c-M input rules: evolved Goblin Barrel point, Goblin Drill dig start, hero Balloon throw | extractor | `mech_rules` hook in `extract.match` (SME_MECH_GB/DRILL/HB; inputs_v20 `7af4cb38`); one Balloon rule (below) | **91 / 109** | **264,455** | `165839`, `235355`, `041602` (225213 now runs) |
| 8.2 (r82) | Zap dated from ZapFreeze | extractor | SME_MECH_ZAP (inputs_v21 `a938a168`, 15 matches change) | 91 / 109 | 264,455 | 0 |
| **8.3 (r83)** | a body crossed between t and t+1 | comparator | `mech_torn` hook in `sme_live.do_match` (SME_MECH_CROSS) | **92 / 109** | 264,455 | `192935` |
| **8.4 (r84)** | hero Mini PEKKA unlisted by the reader during its cast | comparator (+ extractor data) | `extract.reader_hidden` + `sme_live.hidden_ok`, class `torn_hidden` (SME_HIDDEN; inputs_v22 `2a6ef262`) | **93 / 109** | 264,455 | `181217` |
| **8.5 (r85)** | hero Goblins banner press | SME driver (SmeRun / SnapRun2) | the press names the live banner by object id (SME_BANNER) | **94 / 109** | **264,491** | `224856` |
| **8.6 (r86)** | Golden Knight dash hidden by a mislabelled frame | extractor | `gk_dashes` guard (SME_GK8; inputs_v23 `ef845038`, 1 cast) | **95 / 109** | **264,912** | `001141` |
| **8.7 (r87)** | own hero press seen only as a charge drop | extractor | `own_charge_presses` (SME_CHARGE8; inputs_v24 `1c0e0699`, 1 press) | **96 / 109** | **264,960** | `225213` |

**0 regressions in every row** against the row before. r87 against r80: 8 gained, 0 lost.

## 8.1: one hero Balloon rule (a)
- The round-7.1 rule (`hero7_cast`: R = first new projectile - 4, window [prev - 3, first - 4]) and A2c-M's HB
  (`mech_rules.hb_throw`: a moving throw, window [prev + 1 - 3, first - 3]) both dated the throw.
- **HB is the one measured against crforge:** crforge shows the throw on line R+3 on 9 / 9 casts. It also tells a throw
  from a death bomb by movement.
- So `hero7_cast` now leaves Balloon to HB when SME_MECH_HB=1. 5 casts differ from v19:
  - `230512` 2555-2556 -> 2556-2557, and 3785 -> 3785-3786;
  - `235355` 2687 -> 2677-2678 (this one heals the match);
  - `235355` 4910-4911 -> 4911-4912;
  - `235915` 3045-3046 -> 3046-3047.
- Each of the 3 cases round 7 had moved keeps an overlapping tick, and `235915` stays exact.

## 8.4: 181217, the hero Mini PEKKA the reader stops listing (a)
- **What the game does with the body: it keeps it.** The body leaves the reader's ents and phase-2 unit lists at 3041,
  2 ticks after its cast starts (cast_timer 2, kind 15 -> 14 on 3039). Yet our princess towers' projectiles keep
  targeting its address (`0x76ac94313eb0`) through 3095.
- **The projectiles' target points are crforge's body, exactly.** Of the 28 frames 3041-3095, 22 carry a target point,
  and on those 22 the point equals crforge's MiniPekkaHero row. The track includes the Tornado pull, (6902, 22652) ->
  (9265, 26367). On the 6 frames with no point the body is not read.
- crforge's body dies on 3097, the first frame with no projectile in the game too.
- So crforge is right and the reader drops a live object. That makes this a reader-representation gap.
- **Census (`a2c8/hidden_census.py`, all 138 matches):** a body that leaves ents while a projectile still targets it
  occurs exactly twice, and both are a hero Mini PEKKA 2 ticks into its cast: `181217`@3041 and `213436`@778 (flagged).
- **Every hero Mini PEKKA cast (`a2c8/mp_census.py`): 10 casts.**
  - 8 stay listed (kind 14 for 18 ticks, then back to 15).
  - The 2 above vanish.
  - Why the reader drops those 2 is not traced. The ability's ActionSetCharacterLevel (+1 / +2 / +3 / +5 levels by
    stack) is a candidate (b).
- **Rule:**
  - `extract.reader_hidden` writes `reader_hidden` = [{side, crforge name, last, end, track}] into the record. The
    track's point comes from a projectile already seen in the frame before, because a projectile fired this frame
    carries its fire-time point (3057: 9060 / 8864).
  - `sme_live.hidden_ok` then takes exactly one sim row of that side and name out of the comparison, at the track
    point when the frame has one. The frame must otherwise be exact.
  - It is a torn class (`torn_hidden`), not exact, because the reader shows no hp.
- **Planted checks (`a2c8/hidden_test.py`, `results/live/a2c8_hidden_test.txt`).** On 181217 the base frame passes
  28 / 28, and each planted change is caught:

  | planted change | caught |
  |---|---:|
  | the sim row moved 1 unit (tracked frames) | 22 / 22 |
  | a second sim row with the same name | 28 / 28 |
  | another name | 28 / 28 |
  | another side | 28 / 28 |
  | a recorded body moved 1 unit | 28 / 28 |
  | our elixir +1 | 28 / 28 |

  On 213436, which is flagged and already diverged, every planted change is caught as well.
- **Limit (b):** on the 6 untracked frames the hidden body's position is not checked.

## 8.5: 224856, the hero Goblins second wave (a)
- **Game:** the last goblin falls at about 431, and the banner (card 203000002, kind 13, 4082 hp) stands at its point
  from 437. The opponent's press (cast_seen 481, window 481-482) sends the second wave: goblins at x ± 1000, y + 500,
  read from 493 / 499. The banner is gone at 505.
- **crforge (r78 plan):** the ability command names the play's unit `cmd3_0`, a dead goblin. Nothing runs: the side's
  elixir rises by regen alone over 470-500 and no ability use is recorded. The banner decays until 563.
- **crforge does model the banner's ability, but only when the command names the banner by object id**
  (`BattleGoblinHeroTest.theBannersAbilitySendsTheSecondWave`). The game's command names an object, so the gap is in
  our SME driver.
- **Census (`a2c8/gob_census.py`):** the 138 matches hold 1 hero Goblins ability, and it is this banner press (the reader
  shows the banner and 0 goblins at its tick).
- **Fix (SmeRun.java and bp/SnapRun2.java, `queueBanners`):**
  - a plan ability command marked `banner` (plan_from marks it under SME_BANNER=1) is queued in the tick loop;
  - once the side's GoblinHero_Flag_Building is live, before the run tick, it goes in by object id with its given tick;
  - with no banner by run - 1, it goes in by name as before.
  - Result: 224856 is exact on every frame (1,766 / 1,766).
- **Limit (b):** the deferred command is queued after any same-tick command queued up front.

## 8.6: 001141, a Golden Knight dash hidden by a mislabelled frame (a)
- The frames labelled 5390 / 5391 show a fresh knight move 116 units "in one tick". `gk_dashes` took that as a dash
  burst and set its one-cast-per-chain gate (100 ticks).
- The real dash, 5399 -> 5401 (464, 646), was therefore never cast.
- `bp_rules.not_a_dash` then dropped the fake burst as a mislabelled pair. The match ended with no cast, which is A2c-M's
  "missed GK dash".
- **Rule SME_GK8:** inside `gk_dashes`, the same two-tick test before the gate. A one-tick pair whose speed does not hold
  to the next frame two or more ticks on is no burst.
- **Census over the 138 matches:** it changes exactly 1 cast, adding 001141 5399 [5398, 5399]. No other cast moves.

## 8.7: 225213@3588, our hero Ice Wizard press with no cast seen (a)
- **What the reader shows:** at 3588 our elixir drops 2.0 (59,888 + 714 regen - 20,000 = 41,316 over 3586 -> 3588). The
  hero IW's `own_action.charges_raw` goes 1 -> 0 on the same frame (state 2 -> 7). No cast area follows, and there is no
  tap.
- **Census (`a2c8/charge_census.py`, our side only, `results/live/a2c8_charge_census.txt`):** 122 own charge drops; 121
  have an extracted own press in [drop - 30, drop + 2]. 225213@3588 is the only one without.
- **Rule `extract.own_charge_presses` (SME_CHARGE8):** a drop with no press becomes a press with R in [prev, drop - 1].
  It adds exactly that 1 press. 225213 is exact apart from torn.

## Not fixed this round (evidence for the next step)
- **`171753`@1789, our Knight 2 ticks late (a for the disagreement; b for the cause).** The frame-1770 elixir is pre-cost
  (95,060 = 94,704 + 2 × 178), so R >= 1770. The game's Knight, though, starts walking at 1789 = crforge's start for
  R = 1768: crforge with R = 1770 moves it at 1791, the same path 2 ticks behind.
  - The two signals disagree by 2 ticks, on the only play of 4,837 whose tap precedes its drop pair (round 7).
  - A census of the tap -> drop -> first-move gap per own troop is owed. The first try (`a2c8/knight_census.py`) mis-reads
    the reader's deploy-snap point, so it is not used.
- **`101112`@5923 (new: 660 was fixed by 7.2):** our Knight is 21 units off, (-19, -10), 25 ticks after an opponent
  Fireball (5898). The frames before are exact, and no single-command shift helps (sweep). Possibly the Fireball
  knockback (b, untraced).
- **`204518`, `010245`:** unextracted Zaps (A2c-M). A general Zap rule still needs a discriminator. Most of the
  ZapFreeze groups come from Electro units, not Zap. Not started.
- **Others' items, untouched:** body-position singles (BP: 164443, 170912, 180336, 211239, 000233, 014928), `172835`,
  `222712`, `001702` (A2c-M leads in their sections). The full table is in `results/SME.md`.

## Files (round 8)
- `extract.py`: the A2c-M hook, `reader_hidden` (SME_HIDDEN), `own_charge_presses` (SME_CHARGE8).
- `sme_live.py`: the CROSS hook (SME_MECH_CROSS), `hidden_ok` / `torn_hidden` (SME_HIDDEN), banner marking
  (SME_BANNER), `gk_dashes` guard (SME_GK8), and Balloon left to HB (SME_MECH_HB).
- `SmeRun.java` and `bp/SnapRun2.java`: `queueBanners`.
- `a2c8/`: censuses, planted test, trace tools, `run8.sh`, `chain8c.sh`, and the patch scripts.
- Results: `results/live/r8{0..7}_{results.jsonl,cmp.txt}`, `a2c8_{diag_r78.jsonl,cls_r78.tsv,on_first.txt}`, the
  census outputs, and `a2c8_hidden_test.txt`.
- Pod 33920: `/workspace/pilot/{sme8,lib_f635c,inputs_v20..v24,a2c8}`, runs `sme_live/r8*`.

---

# A2c-9Z: the Zap cluster (worker a2c9z, pod 33920)

Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted.

**Base reproduced (a).** `r9z0` (r87's command on a copy of sme8, `/workspace/pilot/sme9z`, `sme_live/run9z.sh`) is
byte-identical to r87 (`results.jsonl` sha256 `b906fbbec39d3c6d`). With both new flags off, `extract.py` regenerates
inputs_v24 byte for byte (sha256 `1c0e0699`, `a2c9z/regen9z.sh` = v24's flag set).

| run | change | layer | inputs | exact apart from torn (unflagged) | exact frames | regressions | gained |
|---|---|---|---|---:|---:|---|---|
| r9z0 = r87 | | | v24 | 96 / 109 | 264,960 | | |
| **r9z3** | Zaps the reader never shows, added from ZapFreeze buff groups | extractor | `SME_ZAP_ADD` (v25c `da218b6d`, 12 Zaps in 8 matches) | **98 / 109** | **275,425** | 0 | `204518`, `010245` |
| **r9z4** | an extracted Zap's point re-solved from its buff group | extractor | + `SME_ZAP_POINT` (v25d `59517ff0`, 2 points) | **99 / 109** | **275,509** | 0 | `001702` |

r9z1 / r9z2 were the same two steps before the crown-tower fix below (97 then 98 / 109, 0 regressions); they are kept in
`results/live/` but are not the chain. **D1 (99 / 109) is reached (a).**

## The discriminator (a; `a2c9z/zap_census.py`, `a2c9z/zap_eval.py`, `results/live/a2c9z_zap_eval.txt`)
- **What puts ZapFreeze on a body, from the 987 groups (made tick c, source side) in the 138 matches:** Zap; Lightning
  (decks without Zap or Electro cards: 48 groups, X-Bow -1,697 / tower -423); Electro Spirit (-159); hero Electro Wizard
  (-376 / -195); and Electro Dragon, Electro Giant (reflect) and Electro Wizard, which at level 16 deal **exactly a
  Zap's 306 / 307** (205 Zap-sized groups in decks without Zap, all but one with one of these bodies alive near).
- So damage alone does not separate Zap from three Electro units. **The rule (`mech_rules.zap_is_cast`):**
  1. the source side's deck (battle log) holds Zap;
  2. every hit body with a known hp drop took that level's Zap damage (troop / building 305..319 at 16, crown tower 77);
     a body with no hp of its own (hero IW cube) or a damage-reduction buff (evolved Knight's Fortify) is skipped;
  3. no Electro body of the source side is alive within 9,000 units of a hit over [c - 4, c + 1]. 9,000 covers the
     largest reach seen in the negative set (8,035, an Electro Dragon chain).
- **Precision.** Negative set = the 749 groups of decks without Zap, classified as if they held a level-16 Zap:
  **1 / 749 pass** (172835@4551, an Electro Dragon deck where no Electro body was read). With the deck test, 0.
- **Recall.** Positive A = 21 groups of Zap decks with no Electro card: **20 / 21** (235355@5989 is missed: the hero
  IW took 326, a Zap plus 20). Positive B = the 36 groups matched to an extracted (H-ZAP-inferred) Zap: **30 / 36**.
  The 6 misses have an Electro Giant / Dragon 2.1-7.4 tiles from the hits (5) or the 326 drop (1). The rule only adds,
  so these 6 plays stay; whether 161448@559/591 are Zaps or Electro Giant reflects is open (b).
- **Independent check, the opponent's card cycle (a).** The 12 added Zaps never make a fitting deal unfitting
  (0 cases); 4 of them turn a flagged `opp_no_fitting_deal` match into a fitting one (090406, 194858, 213436, 022149).
  All 4 of those matches are then **exact on every frame** in r9z3 (they stay outside the 109 count, which uses the
  A2b-1 flags).

## SME_ZAP_ADD (a)
- A buff group passing the rule with no Zap play of its side within 3 ticks of c - 1 becomes a Zap play at
  R = c - 1 (the round-8 ZapFreeze dating), deck index from the battle-log deck.
- Point: the 100-unit grid point covering every buff holder, then the most victim-side bodies that died in the hit gap
  (hp <= the Zap's damage), then the fewest victim-side bodies without the buff, then the widest margin (up to 300) to
  every reach edge, then nearest the centroid. Reach = 2,500 + the body's collision radius (crforge tables).
- **Crown-tower fix (a):** 204518@1822's Zap also killed our 33-hp princess tower, which a dead-body list of troops
  missed (r9z1: 204518 then failed at 1823 with the tower alive in the sim). Dead crown towers count when their hp <=
  the tower damage (77). Census: it moves 2 points, 204518@1821 and 090406@4493; 090406 stays exact.
- **All 12 adds (`results/live/a2c9z_zap_changes.txt`):** clean 204518@721 (X-Bow -306, the Electro Dragon 17 tiles off),
  204518@1821, 010245@571 (princess tower -77, no Electro card in the deck); flagged 090406 x2, 161448, 194858, 204837,
  213436 x3, 022149.

## SME_ZAP_POINT (a)
- An extracted Zap matched to a buff group keeps its point when that point covers every holder and every dead body
  (150 units of slack: a frame is up to 2 ticks from the hit) and no unbuffed body; otherwise it is re-solved as above.
- Without the slack, 180652 and 235355 (both exact) would have moved: their holders sat 91 and 21 units past the reach.
- **It moves 2 of 36 points:** 001702@2491 (2300, 17836) -> (3200, 16797), which now covers the 3 Skeletons the game's
  Zap killed (one was 667 units outside the old reach), and 204837@3322 (flagged).

## Planted checks (a; `a2c9z/zap_test.py`: ok 13)
The rule rejects an Electro body 7 tiles away, Lightning-sized and Electro Spirit-sized drops, 306 on a crown tower, the
wrong level and a group of only Fortify hits; the point solver moves a point to cover the dead and away from an
unbuffed body, and keeps a consistent point. The comparator is unchanged.

## What fails now (r9z4, 10 / 109)
000233@4599, 014928@5183, 101112@5923, 164443@3213, 170912@745, 171753@1789, 172835@2831, 180336@2911, 211239@1532,
222712@4183: 9 body position and 1 Earthquake pulse (`r9z4_cmp.txt`); none involves a Zap.

## Files (A2c-9Z)
- `mech_rules.py`: `zap_groups`, `zap_is_cast`, `zap_point`, `zap_buffs` (SME_ZAP_ADD / SME_ZAP_POINT); `extract.py`:
  the one call after the A2c-M hook.
- `a2c9z/`: `zap_census.py` (group census), `zap_eval.py` (precision / recall / cycle check), `zap_dry.py` (every add and
  re-point on an inputs file), `zap_why.py` (a point against its group), `zap_test.py`, `regen9z.sh`.
- Results: `results/live/r9z{0..4}_{results.jsonl,cmp.txt}`, `a2c9z_zap_eval.txt`, `a2c9z_zap_changes.txt`,
  `a2c9z_inputs_v24_v25d.txt`.
- Pod 33920: `/workspace/pilot/{sme9z,inputs_v25a..v25d}`, runs `sme_live/r9z*`, `run9z.sh`, `chain9z*.sh`.

---

# A2c-9T: own-play dating, area clock, and the route-kept singles (worker a2c9t, pod 32657)

Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted.

Matches: `171753`@1789, `101112`@5923, `222712`@4183, `172835`@2831. No crforge change: every case traced to the extractor,
the reader, or the open route-kept class (below).

**Base reproduced (a).**
- `r90` (r87's command, run on 32657 from 33920's sme8 / lib_f635c / inputs_v24) is byte-identical to r87 (sha256 `b906fbbe`).
- On the laptop, regen with v24's flag set reproduces v24 byte for byte (`1c0e0699`). With the 9Z flags it reproduces
  v25d (`59517ff0`).
- After 9Z landed, the chain is rebased on **r9z4 (99 / 109, 275,509 exact frames)**, copied to 32657 with sha256 `83267f51`.

| run | change | layer | inputs | exact apart from torn (unflagged) | exact frames | regressions | gained |
|---|---|---|---|---:|---:|---|---|
| r9z4 | (9Z) | | v25d | 99 / 109 | 275,509 | | |
| **r93** | SME_LATE9 + SME_MADE9 (one play each, in different matches) | extractor + comparator | v27 `157e183a` = v25d + 2 plays | **99 / 109** | **276,305** (+796: 171753 +704, 222712 +92) | 0 (136 matches byte-identical to r9z4) | 0 (both matches have a later onset) |

`r93o` reran the 2 changed matches alone (a match's result depends only on its own inputs):
- **171753:** 869 -> 1,573 exact; first div 1789 -> **3293**; 1770 is `torn_late`.
- **222712:** 2,863 -> 2,955 exact; first div 4183 -> **4742**; frame 4183 is now `torn_snap`.

## 9.1 171753@1789: the game ran our Knight at its birth stamp, and frame 1770 is read before the game heard it (a)
- **Three signals for the play** (tap 1742; game object 5000047):
  - **The game's own stamp:** phase-3 birth for 5000047 reads card tick 1768 and creation 1769.
  - **The first move:** the game moves at 1789 (kind 14 -> 15, 42-unit step). crforge moves on R+21 (1789 for R = 1768,
    1791 for R = 1770).
  - **The read:** frame 1770 shows our elixir pre-cost (95,060 = 94,704 + 2 x 178) and no Knight. 1773 shows both.
  - Round 7.3's `own_play_elixir` moved R to the drop (1770). That fixed the elixir and broke the walk.
- **The census the round-8 worker owed** (`a2c9/own_census.py` on r87 plans + BP5's `deploy_census.py`;
  `results/live/a2c9_own_census.txt`) covers every own `own_tap` play, 4,841 of them. 4,840 are dated by the birth stamp
  (lo = hi); the other is this one.
  - **Elixir drop vs R:**
    - in the pair holding R+1: 4,720;
    - on the pair ending at R (the round-2.1 in-step read, `torn_cmd`): 95;
    - no drop found: 26;
    - **a frame after R still pre-cost: 0 of 4,840.** Only 171753's Knight would be one, with R = 1768.
  - **First move vs crforge (clean):** 1,687 agree. 2 are 1-tick frame pairs, game earlier (180652@4514, 220728@3389,
    both our Knights, in matches that stay exact).
  - **Input lag R - tap:** 21-27 for 4,334 plays; 40-44 for 330 (taps made short of elixir); 171753's is 26 with R = 1768.
  - **So the birth stamp dates all 4,841 plays (a).** The elixir signal disagrees on exactly one frame, 1770.
- **What frame 1770 is (a for the frame, b for the netcode):**
  - It equals, on every object, crforge's line 1770 with the Knight run on 1770 instead: no body, cost untaken.
  - So it is the game's history before it heard the play. The game then re-ran from 1768: 1773 is exact with R = 1768.
  - This is crforge's own `checkDelay` model: a command heard late runs in a history replayed from before its run tick.
- **Rule SME_LATE9:**
  - **Extractor (`own_play_elixir`):** a birth-stamped play (lo = hi) keeps R. The frames in (R, last pre-cost frame]
    become `late_reads`, here [1770]. Census: changes exactly 1 play of 4,841.
  - **Comparator (`late_reclass`, after the fit as SNAP / CROSS):** a listed frame t that is div is `torn_late` when it
    equals, by the full diff, crforge's line t with that play run at t. That is crforge's own state with no tolerance.
- **Planted checks (`a2c9/late_test.py`, `results/live/a2c9_late_test.txt`):** the base frame passes. Every planted
  change is caught (6 / 6):
  - our elixir +1;
  - our elixir with the cost taken;
  - one of our bodies moved 1 unit;
  - the Knight added at its point;
  - an opponent body removed;
  - a projectile added.

  The same frame unlisted, and the next frame 1773 unlisted, stay div.
- **Next onset 3293, open (b):** the opponent's hero IW and its cube are 1 unit off in y (20,999 vs 20,998), then 30 units
  at 3303. Not traced. (2536, an opponent Fireball 1 tick off, is repaired by the fitter.)

## 9.2 222712@4183: the Earthquake was dated from a mislabelled first frame (a); the deploy push is contradicted (c)
- **The Earthquake area (gen 3000035):**
  - It reads 2950 ms on the frame labelled 4183, then 2850 / 2750 / 2650 on 4186 / 4188 / 4190.
  - By the later three, the area was made on 4184, so R = 4183. The first frame, which is a read of line 4184, gives 4182.
  - The second area (hidden damage, gen 3000036) is first listed on 4186 at 2950 ms. That is crforge's
    EarthquakeHiddenDamage for R = 4183 exactly.
- **With R = 4183 (a):**
  - Skeleton 5000103 is exact from 4186. Its -50% Earthquake slow starts a tick later. The "stronger deploy push" was this
    tick of full speed: the game's 2-tick move (148, -78) is 2 x (74, -39).
  - **So "a stronger deploy push in the game" (A2c-M) is (c).** No position on frame 4183 differs from crforge's line 4184.
    A deploy-push census is therefore not owed for this match.
  - Frame 4183 is crforge's line 4184 apart from 3 listings: no IW cube, the IW deploy area as A, and no Earthquake area
    yet. SNAP finds it as an in-step state of step 4184 (`torn_snap` in r93o).
- **Census (`a2c9/fx_clock.py`, `results/live/a2c9_fx_clock.txt`; every reader area gen in the 138 matches with 3+
  sightings):**
  - 3,079 gens: the first sighting is on the clock of the later ones.
  - 3 gens are off: this Earthquake, and 2 areas of card 203000011 in 154319, which date no play.
- **Rule SME_MADE9 (`sme_live.fx_made_clock`, called from `extract.match`):**
  - It applies to an `fx_made` play whose area's first sighting disagrees with 2 of its next 3.
  - R moves by the difference (dated `fx_made_clock`).
  - Changes exactly 1 play (v25d -> v27 diff: 222712 Earthquake 4182 -> 4183, and 171753's Knight from 9.1).
- **Next onset 4742, open (b):** our Skeleton 5000117's step at 4742 is (-17, -96) in the game and (-43, -83) in crforge.
  It is a heading change, the same shape as the route-kept class. Not traced.

## 9.3 101112@5923: not the Fireball (c); a route kept on a reference cell change (a for the event)
- **The Fireball does not touch the onset (c):**
  - It is played 5897 at (14500, 23500), and its projectile is still in flight at 5925 ((13189, 18633), 600 a tick), so it
    lands about 5933, after the onset.
  - Its point is 6,000+ units from the Knight.
  - No ground troop near the Knight is displaced before 5923.
  - A Fireball knockback census would test nothing here, so it is not run.
- **The event:**
  - Our Knight (slowed by the hero Ice Golem area) walks to the opponent Skeleton 5000154.
  - At 5923 the Skeleton crosses into a new cell row (y 10,466 -> 10,555). crforge's goal flips 855 -> 891, a diagonal
    step (29, -30).
  - The game holds the route: its 2-tick move is crforge's next two steps.
  - It is BP4's "kept held route" event (goal census: 25,804 follow crforge, 4 keep, this one among them). BP6 variant 7
    (reference at end of t-1) keeps it, but 7,386 clean events contradict that variant.

## 9.4 172835@2831: the same class (a for the event)
- **crforge (AimRun5, `bp6/work/all`):** our Knight 5000057 re-plans at 2830, goal 1032 instead of its held 1031. It steps
  toward (12750, 18250) and (13250, 17750), then re-plans back to 1031 at 2832.
- **The trigger:** its reference, the WitchMother, takes 429 and starts moving at 2830 (reference point (11332, 12789) ->
  (11170, 12636) between the two re-plans).
- **The game** walks straight, (36, -35) a tick: no re-plan.
- No body is within 4,500, and the VoodooProjectile 9 units off follows the Knight's x.

## Mechanisms for D1 (per match)
| match | first div r9z4 -> r93 | mechanism | status |
|---|---|---|---|
| 171753 | 1789 -> 3293 | own command heard late (birth-stamped R, rollback read) | fixed (LATE9); next: opponent hero IW 1 unit, untraced (b) |
| 222712 | 4183 -> 4742 | area dated from a mislabelled first frame | fixed (MADE9); next: route / heading change (b) |
| 101112 | 5923 | crforge goal flip on the reference's move; the game keeps its held route | open, the 9R route-kept class |
| 172835 | 2831 | the same goal flip (reference starts moving) | open, the 9R route-kept class |

## Files (A2c-9T)
- **Code:** `sme_live.py` (`own_play_elixir` late branch, `late_reclass`, `fx_made_clock`, LATE9 / MADE9) and the
  `extract.py` call.
- **Tools (`a2c9/`):**
  - censuses: `own_census.py`, `fx_clock.py`; planted checks: `late_test.py`;
  - plan and comparison helpers: `simk.py`, `planmod.py`, `chk.py`, `cmp1.py`, `near9.py`, `indiff.py`;
  - run and process control: `run9.sh`, `killtree.sh`.
- **Results:** `results/live/a2c9_{own_census.txt,own_census.jsonl.gz,fx_clock.txt,late_test.txt,deploy_r87.log}`,
  `r93_{results.jsonl,cmp.txt}` (results sha256 `eed5f304`).
- **Pod 32657:** `/workspace/pilot/{sme9,inputs_v25,v26,v27,a2c9}`, runs `sme_live/r90`, `r93`, `r93o`. r91 / r92 / r9id
  were stopped unfinished when the base moved to r9z4.
