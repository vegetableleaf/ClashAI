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
