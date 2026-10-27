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
