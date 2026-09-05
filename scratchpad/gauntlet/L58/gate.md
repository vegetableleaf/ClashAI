# L58 gate progress (validation gate for the radius-graded reward)

Started 2026-09-04. Brief: scratchpad/gauntlet/L58/BRIEF_gate.md. Module: icebow/src/clashrl/geometry_reward.py
(read in full; API = board_from_engine / placement_from_spec / score_placement / role_average_radii).

## 0. Preconditions
- Free RAM 5.2 GB / 32 GB. Only python process = the Nucleo uvicorn (pid 63608, port 8765) -- left alone.
  No training process running.
- Replay set: the L51 driver's default tag list is `scratchpad/gauntlet/ext/batch/replay_*.json` = 211 tags
  (the 211 of the 268 usable replays that the engine batch converted, HANDOFF 5ay). Part 1 runs on these 211.
- Side convention (driver docstring): side 0 = red = team 0 (own half HIGH sim y); side 1 = BLUE = the
  icebow player (211/211 per L51) = team 1, own half LOW sim y. Candidate tiles are given in the team-0 frame
  and mirrored (x -> 1-x, y -> 1-y) for side 1.
- Locked tiles per card (HANDOFF 5cs.27, L56 tesla_probe.json): buildings/spells/ice_wizard -> corner
  (1.5,18.5) [Tesla/Tornado/Ice Wizard maps share the cell]; skeletons -> (9.3,24.1); knight -> (11.8,24.1).

## 1. Part 1 -- pro replays through the sim (DONE; 79 s wall)
Files: `gate_replay.py` (imports the L51 driver, re-implements `drive()` with the scoring hook BEFORE each
accepted `eng.deploy`; L51's file untouched), `gate_summarise.py`, outputs in `p1/` and copied to
`gate_plays.csv` (6,639 rows) + `gate_summary.txt` (the full per-card x term x radii tables, sections A-D).
Smoke (--limit 20): 648 plays, 7 s; full: 211 replays, 0 errors, 6,639 scored plays of the 8 icebow cards
(blue/icebow side 5,825; red side 814 -- the opponent rarely carries these cards), threat present for
5,463/6,639 plays.

Method notes (what the numbers mean):
- Candidates = the brief's 8 tiles + right-lane mirrors of corner/lane (corner_R (16.5,18.5), lane_R
  (13.5,20.5)) + the 3x4 grid x in {3,9,15} x y in {18,22,26,30} = 22 candidates, all in the team-0 frame
  (own half HIGH y), mirrored x->18-x, y->32-y for side 1. Pro tile = the raw crawl units (x_units/18000,
  1 - y_units/32000), unsnapped, exactly what the driver hands the engine.
- Rank = 1 + number of candidates STRICTLY better (a tie shares the best rank), so rank 1 with `tie1`
  means "nothing beats it but it is level with >= 1 candidate" -- usually both are 0.
- Summed score = equal-weight sum of the 10 graded terms (p1_pull_band, p1_close_penalty, p2_cover,
  p3_intercept, p4_spell_frac, p4_nado, p4_king_activation, p5_timing, p6_siege, p7_fragility). The doc
  does not fix weights; this is the plain sum.
- "ra" (role-average) = every ENEMY troop/building's r_atk/r_sight replaced by `role_average_radii`
  (the threat's band is what the model must derive from role bits); the placed card keeps its own radii.
  Threat identity is unchanged under role radii in 5,825/5,825 blue plays (the threat pick uses value +
  march distance, not radii).

### 1a. Pro tile vs the policy's locked tile, blue side, per-card radii (strict pro>lock / tie / pro<lock; n)
| card | n | SUM pro>lock / tie / < | median rank (of 27, p1b) | terms where pros are AHEAD (>,<) | terms where pros are BEHIND (>,<) |
|---|---|---|---|---|---|
| tesla | 807 | 0.633 / 0.180 / 0.187 | 4 | p1_pull_band .323/.152; p2_cover .540/.161 | p1_close_penalty .050/.031 (flat) |
| x-bow | 543 | 0.110 / 0.055 / 0.834 | 8 | p2_cover .300/.061 | p6_siege .018/.895; p1_pull_band .094/.105 (flat) |
| skeletons | 979 | 0.398 / 0.382 / 0.220 (vs TRUE lock (9.5,31.3)) | 6 | p3_intercept .347/.002; p5_timing .268/.086 | p2_cover .020/.231; p7_fragility .001/.076 |
| knight | 978 | 0.510 / 0.396 / 0.094 (vs TRUE lock (12.5,31.3)) | 6 | p3_intercept .358/.007; p5_timing .246/.055 | p2_cover .127/.143 (flat) |
| ice-wizard | 922 | 0.441 / 0.338 / 0.220 | 6 | p2_cover .223/.065; p3 .208/.146; p5 .219/.124; p7 .040/.023 | -- |
| tornado | 425 | 0.689 / 0.019 / 0.292 | 7 | p4_spell_frac .539/.136; p4_nado .560/.240 | p2_cover .292/.499 |
| the-log | 866 | 0.336 / 0.343 / 0.321 | 9 | p4_spell_frac .300/.054 | p2_cover .082/.367 |
| rocket | 305 | 0.157 / 0.193 / 0.649 | 22 | p4_spell_frac .184/.079 | p2_cover .010/.711 |

(canonical Part 1 outputs = `p1b/` (copied to `gate_plays.csv` / `gate_summary.txt`); `p1/` kept for the diff.
p5_timing for BUILDINGS is identical on every tile -- tie 1.000 for tesla and x-bow: t_resp = deploy_time
only, no travel, so P5 is a when-to-play term with no placement gradient for a building.)

CORRECTION (p1b re-run, canonical): the brief/HANDOFF locked troop cells (9.3,24.1)/(11.8,24.1) are
mis-converted cell centres. `env.actions.cell_center` on the 18x24 grid gives cell 423 -> (9.5,31.33) and
426 -> (12.5,31.33) (tile frame, own half HIGH y), i.e. BEHIND the king tower, and Part 2 confirms the
policy actually lands skeletons on (9.5,31.3) 492/504 times. The skeletons/knight rows above are from the
p1b run against those TRUE locked tiles (26 candidates, `p1b/`); the first pass (`p1/`, 22 candidates,
mis-converted lock) gave skeletons 0.253/0.280/0.467 and knight 0.269/0.339/0.392 -- that reading is
withdrawn. Pro blue skeletons within 1.5 tiles of the true lock: 8.9% (n=979; 5.4% of the mis-converted
cell, so HANDOFF 5cs.27's 4.9% was measured against the wrong tile); knight 0.0% of (12.5,31.3) and 0.0%
of the observed (12.5,30.0) (n=978). Pro median own-frame y: skeletons 19.5, knight 21.5; only 15%/23%
of pro plays have y >= 28.

Reading: under the equal-weight SUM the pro tile outranks the locked tile for tesla (63%), tornado (69%),
knight (51% vs 9%), ice-wizard (44% vs 22%) and skeletons (40% vs 22%); for x-bow (11% vs 83%) and rocket
(16% vs 65%) the LOCKED tile wins more often; the log is flat (34/32). The terms that carry the pro-vs-locked signal in the right direction
are P1 (tesla), P4 (all three spells), P5/P3 (troops, weakly), P2 for tesla/ice-wizard. Terms that work
AGAINST the pros:
- P2_cover for TROOPS: pros put skeletons/knight on the river bank (blue modal skeleton tiles (10,18) n=81,
  (4,18) 76, (14,18) 64, (8,18) 59 -- 2 tiles behind the river) where princess cover is 0.39-0.41; the
  TRUE locked skeleton cell (9.5,31.3) behind the king gets mean 0.559 vs pro 0.470 -> pro<lock 23.1% vs
  pro>lock 2.0% (n=979). For the knight the true lock (12.5,31.3) is flat (12.7% vs 14.3%). P2 alone
  would hold skeletons on the policy's current behind-the-king cell; it is P3 (pro>lock 35%, lock ~0
  because a unit behind the king cannot intercept) and P5 (27%/9%) that pull the SUM the pros' way.
- P2_cover for SPELLS (the CHOICE "cover of the cast point"): 78.7% of pro rockets and 37.2% of pro
  tornados land on the ENEMY half (median rocket own-frame y = 8.5), where cover is 0 by construction ->
  rocket pro<lock 71%, log 37%, tornado 50%. Cover of a cast point is meaningless for an offensive spell;
  this is the term that puts the pros' rocket at rank 22/23.
- P6_siege: the corner tile (1.5,18.5) reads 0.95-0.98 (impl_geometry finding: the RUNNING engine's
  corner bow reaches the princess, gap 10.67 < 11.5) and the pros' lane bows (16,20) n=155 / (2,20) n=133
  read 0.915 / 0.94 -- essentially level; the "pro<lock 89.5%" is dominated by these ~0.03 differences
  plus the pros' CENTRE bows ((8,22) n=57, (10,22) n=50: defensive bows, P6 = 0 by design vs corner 0.98).
  P6 is not wrong about offense, but the sum then ranks a pro defensive bow far below the corner.
- P7_fragility (skeletons): pros drop skeletons ON the threat (pro<lock 7.2%, >0.4%); the term penalises
  exactly the pros' surround placement. Small n_active (78/979) but always against the pros.

### 1b. Per-card vs role-average radii (fraction of blue plays where the pro tile's RANK is unchanged)
| term | all blue plays (n=5,825) | only when the term is active (n) |
|---|---|---|
| p1_pull_band | 0.929 (tesla 0.654, x-bow 0.751) | 0.517 (n=437) -- mean pro pc 0.547 vs ra 0.566 |
| p1_close_penalty | 0.995 | 0.317 (n=41) -- pc -0.345 vs ra -0.109 (the role-average r_atk is > 2.0 for most melee roles: the penalty mostly switches OFF) |
| p2_cover | 1.000 | 1.000 (radii-free by construction) |
| p3_intercept | 0.988 | 0.966 (n=969) |
| p4_* | 1.000 | 1.000 (radii-free) |
| p5_timing | 0.890 (troops 0.76-0.80) | 0.857 (n=1,757) |
| p6_siege | 0.993 (x-bow 0.930) | 0.937 (n=378) |
| p7_fragility | 0.99+ | 0.338 (n=139) -- pc -0.695 vs ra -0.698 (same magnitude, different rank: the ra r_atk moves which candidates are inside) |

Verdict: for the terms the doc 7.8 flip condition cares about (P1 band, P7), the role-average band changes
the pro tile's rank on about half of the plays where the term fires; P2/P4 are unaffected, P3/P5/P6 > 0.86.
Directionally (pro>lock fractions) per-card and role-average agree to within 0.01-0.03 on every card/term.

### 1c. GATE RULE (doc s3): Tesla at the pros' modal tile (9,21) vs the corner (1.5,18.5) on boards whose
picked threat is Hog / Giant / PEKKA -- n=350 boards (hog 156, giant 126, pekka 68; threat median own-frame
y 17.9 = just past the river, x 10.9). Scored with the level-11 Tesla spec, per-card radii.
| term | median(modal - corner) | mean modal | mean corner | modal>corner | modal<corner | verdict |
|---|---|---|---|---|---|---|
| p1_pull_band | 0.000 (both 0 on 44% of boards; on the 196 ACTIVE boards median +0.25, modal>corner 74%, < 20%) | 0.371 | 0.192 | 0.414 | 0.114 | keep (flat on the literal median, modal ahead wherever it fires; hog 35%/11%, giant 55%/10%, pekka 32%/16%) |
| p1_close_penalty | 0.000 | -0.014 | -0.024 | 0.080 | 0.046 | keep/flat |
| p2_cover | +0.500 | 0.813 | 0.404 | 0.817 | 0.000 | keep |
| p5_timing | 0.000 | 0.805 | 0.805 | 0 | 0 | flat (tile-independent for a building) |
| p3/p4/p6/p7 | inactive for a Tesla | | | | | n/a |
| SUM | +0.500 | 1.974 | 1.377 | 0.880 | 0.057 | keep |

NO term ranks the modal Tesla tile BELOW the corner on the median board -> nothing is dropped by the
doc s3 rule as written. The rule's weak spot: P1 is a snapshot (impl_geometry deviation 4), so on 44% of
Hog/Giant/PEKKA boards it is 0 for BOTH tiles (the threat is still outside both bands when the pro taps)
and the median difference is 0 -- the ranking signal is there (74/20 on active boards) but nearly half
of the Tesla plays get no P1 gradient at all.

### 1d. Terms I recommend dropping / restricting BEFORE training (list; code untouched)
1. P2_cover applied to SPELLS -- contradicts the pros on all three spells (rocket 71% below the locked
   tile, log 37%, tornado 50%); it is the CHOICE in impl_geometry, not the doc's formula.
2. P2_cover applied to TROOPS -- ranks the pros' river-bank skeletons below the policy's true
   behind-the-king cell (23% below vs 2% above, n=979; knight flat 13/14) and on its own would REINFORCE
   that cell. Keep it for buildings (tesla 54%/16% in the pros' favour; it is the one term that separates
   (9,21) from the corner). If kept for troops, P3+P5 outweigh it in the SUM (skeletons 40/22, knight 51/9).
3. P5_timing for BUILDINGS has no placement gradient (identical on every tile) -- harmless as a
   placement term, but it inflates the summed score's mean (the Part 2 w calibration) without shaping
   placement; exclude it from the band mean used for w_geom, or treat it as a play-timing term.
4. P7_fragility for skeletons -- fires against the pros' surround placement on every active play
   (0.4% for, 7.2% against); consider restricting to ranged low-HP counters (ice wizard 4.0% for /
   2.3% against, fine).
Not dropped: P1 (the gate rule passes; 74/20 on active boards), P3, P4 (all in the pros' favour), P6
(level between corner and lane bows; only the centre/defensive bow is scored 0, by design).

### 1e. Extra detail (blue Tesla, per-card radii)
- Pro Tesla tiles (raw units, rounded): (9,21) n=135, (9,19) 71, (9,22) 68, (9,18) 67, (9,20) 49, (5,18) 35.
  P1 on the pros' modal (9,21): mean 0.211 vs corner 0.143 (sum 1.64 vs 1.14, median rank 1 of 23);
  (9,19): 0.332 vs 0.115; (9,22): 0.322 vs 0.221; (9,18) river-bank Tesla: sum 1.20 vs 1.15, median rank
  15 (P2 cover is low at the bank). P1 > 0 on 40.9% of the 807 pro Tesla plays (mean 0.62 when it fires;
  threat gap median 6.2 tiles) -- the snapshot P1 is silent on 59% of the pros' Teslas.
- Bridge block (s7.4) detected on 532/5,825 blue plays, case = 1 on 160.

## 2. Part 2 -- the policy's own placements (DONE; 553 s wall, 3 seeds x 24 matches)
`policy_probe.py`: L56 tesla_probe harness (greedy card + greedy cell, own-half mask, gate tau = 0.25 = the
live/sim `rl_gate_tau`, config line 911), ckpt `data/bench/c2r_best_36k_backup.pt` (exists, 1.9 MB,
read-only), seeds 1234/5678/9012 x 24 matches, domain_rand off. The ENGINE INSTANCE's bound `deploy` is
wrapped from the probe (env.py untouched) and every accepted team-0 placement is scored with
`board_from_engine(env.eng, 0)` BEFORE the deploy. Trap found in the first launch: `env.reset()` keeps the
same engine object, so re-installing the wrapper on every reset double-wrapped it (10,042 "placements" in
24 matches = k copies in match k); fixed with an install guard, verified 31+16+25 = 72 placements over 3
matches. Also collects the Part 3 (trunk z, enemy base) pairs at steps with exactly one enemy troop on our
half. ~7 s per match.

### 2a. Results (`p2/policy_scores.csv` 2,485 accepted placements, 72 matches, mean match 190.6 s; threat present 1,996/2,485)
| card | n | per match (min-max) | landing tiles (tile frame, own half HIGH y) | p1 mean / frac>0 | SUM mean / q25 q50 q75 | w = min(2, 1/mean SUM) |
|---|---|---|---|---|---|---|
| skeletons | 504 | 7.00 (2-15) | (9.5,31.3) x492 | 0 / 0 (troop) | 0.665 / 0.50 0.50 1.00 | 1.50 |
| knight | 473 | 6.57 (2-13) | (12.5,30.0) x184, (3.5,18.0) x72, (14.5,18.0) x50 | 0 / 0 | 0.781 / 0.50 0.50 1.00 | 1.28 |
| ice_wizard | 471 | 6.54 (2-14) | (1.5,18.0) x208, (3.5,18.0) x125 | 0 / 0 | 0.713 / 0.31 0.50 1.00 | 1.40 |
| tesla | 416 | 5.78 (1-14) | (1.5,18.0) x244, (3.5,18.0) x69, (12.5,18.0) x45 | 0.103 / 0.224 | 1.042 / 0.50 1.00 1.50 | 0.96 |
| the_log | 337 | 4.68 (1-12) | (3.5,18.0) x130, (14.5,18.0) x85 | 0 / 0 | 0.700 / 0.50 0.50 1.00 | 1.43 |
| x_bow | 209 | 2.90 (0-7) | (1.5,18.0) x127, (3.5,18.0) x46 | 0.074 / 0.177 | 1.297 / 0.81 1.50 1.50 | 0.77 |
| tornado | 75 | 1.04 (0-4) | (0.5,18.0) x13, (0.5,16.7) x10, (17.5,18.0) x9 | 0 / 0 | 1.008 / 0.47 1.07 1.54 | 0.99 |
| rocket | 0 | 0 | never played by the greedy policy in 72 matches | -- | -- | -- |

Pooled: SUM mean 0.828 (n=2,485) -> **implied w_geom(sum) = 1.21**; per seed 0.811 / 0.826 / 0.845 (n=766/894/825,
stable). P1_pull_band, buildings only (n=625): mean 0.093, frac>0 0.208, q90 0.48 -> w_geom(p1) capped at
2.00 (buildings with a threat present, n=473: mean 0.123, frac>0 0.275, still 2.00). P1 over ALL
placements 0.023. Term means for the policy's own tiles: tesla p2 0.35, p5 0.61, p1 0.10, p1_close -0.02;
x_bow p6 0.64, p2 0.36, p5 0.25; skeletons p2 0.45, p3 0.003 (behind the king it never intercepts), p5 0.22;
knight p2 0.36, p3 0.20, p5 0.22; tornado p4_spell_frac 0.62, p4_nado 0.17.
With the 1d list applied (SUM minus building-P5 and minus P2 for troops/spells): mean 0.430 -> w_geom 2.00.

Reading. (a) Measured: the policy's locked tiles already score ~0.83 on the equal-weight sum, and for
x-bow/tesla ~1.0-1.3, mostly from terms with no placement gradient at the locked tile (building P5 0.61 for
tesla; P6 0.64 for the corner bow; P2 0.45 for behind-the-king skeletons). So a w_geom of 1.21 on the raw
sum pays the policy ~1 reward-unit per placement for what it does now; the placement GRADIENT the pros
would add (P1 for tesla 0.10 -> ~0.21-0.33 at the pros' tiles per 1e; P3 for troops 0 -> 0.24) is 0.1-0.3
per placement, i.e. a 1.21 weight buys 0.15-0.4 of reward delta per placement. (b) Untested: whether that
delta is large enough against the win/tower reward scale to move the argmax cell -- the brief's calibration
rule fixes w from the mean, not from the delta; I recommend calibrating on the SUM with the 1d terms
removed (0.430 -> w = 2.00, the cap), which pays less for standing still and more for the gradient.
(c) The rocket never fires under tau 0.25 in 72 matches (n=0), so no Part 2 rocket calibration exists;
the Part 1 rocket finding (P2 puts the pros' offensive rocket at rank 26/27) stands on its own.

## 3. Part 3 -- linear probe (doc 7.8 flip condition) (DONE; `probe.txt`, fit < 1 min)
Pairs collected in the Part 2 run at steps with EXACTLY one enemy troop on our half: n=6,264 (72 matches),
trunk feature z = `net.policy.forward_parts(...)[0][0]` (d=328), label = that troop's base card, 83 classes.
Ridge one-vs-rest least squares (numpy), features standardised on train, split BY MATCH (58 train / 14
test matches = 4,979 / 1,285 steps), seed 0.
| model | train acc | test acc (n=1,285) |
|---|---|---|
| ridge lam=1 | 0.523 | 0.120 |
| ridge lam=10 | 0.516 | 0.123 |
| ridge lam=100 | 0.487 | 0.111 |
| majority card ('knight') | -- | 0.063 |
| role-oracle (most common TRAIN card given the TRUE role) | -- | 0.303 |
| role-of-predicted-card (lam=10) | -- | 0.311 |
| role probe (lam=10) vs majority role 'win_condition' | -- | 0.394 vs 0.260 |

Per-class test recall (lam=10, classes with >= 20 test steps): knight 0.49 (n=81), skeletons 0.46 (26),
hog_rider 0.29 (102), inferno_dragon 0.28 (109), balloon 0.20 (20), lava_hound 0.18 (84), ice_golem 0.12
(137); 0.00 for archer_queen (38), bowler (24), executioner (58), goblin_giant (23), golden_knight (56),
mighty_miner (137), miner (56), musketeer (35), pekka (30).

Reading. (a) Measured: card identity is barely linearly decodable from the trunk (12% test, 2x the
majority baseline, with a 52% train / 12% test gap = the probe memorises matches); the ROLE probe reaches
39% vs 26% majority, and the card probe's predicted role is right 31% of the time, about equal to the
role-oracle baseline (30%). The trunk carries roughly role-level information about the single enemy on
our half, not card-level -- consistent with the L5x finding that the detector/obs channels are
role-tagged. (b) Untested: a non-linear probe, or probing the obs channels directly, would tell whether
the card identity is absent from the INPUT or merely not linearly separable in the trunk; not run.
Consequence for the reward: graded terms that need the exact enemy radii (per-card mode) are asking the
policy to act on information it does not linearly hold; Part 1 B shows the per-card vs role-average
radii leave the pro tile's SUM rank unchanged on 80.3% of blue plays (n=5,825; per term: P1 92.7%, P5
88.7%, P3 98.8%, P7 98.4%, all others >= 99.3%; per card SUM: tesla 68%, skeletons 71%, knight 78%,
ice-wizard 71%, spells 100%; threat identity unchanged 100%), so the role-average mode changes the
ranking on ~1 in 5 troop/building plays but never the threat pick, and it matches what the trunk can see.

## 4. Close-out
- Part 1 DONE (canonical `p1b/` -> `gate_plays.csv`, `gate_summary.txt`, `gate_tesla_probe.csv`); Part 2
  DONE (`p2/policy_scores.csv`, `policy_match_counts.csv`, `policy_summary.txt`); Part 3 DONE (`probe.txt`).
- Gate rule (doc s3) drops NOTHING: on the 350 Hog/Giant/PEKKA Tesla boards no term ranks (9,21) below the
  corner on the median board (P1 median diff 0, modal>corner 41% vs 11%; P2 +0.5 on the median; P5 flat;
  P3/P7 inactive for a building; SUM +0.5, modal>corner 88% vs 6%).
- Recommended drops/restrictions from the pro evidence (1d; code untouched): P2 for spells, P2 for troops
  (or accept that P3+P5 outweigh it), building-P5 excluded from the w calibration, P7 restricted for
  skeletons.
- Implied w_geom: 1.21 on the raw equal-weight SUM (mean 0.828, n=2,485); 2.00 (cap) on the SUM with the
  1d terms removed (0.430) or on building P1 alone (0.093).
- Corrections to upstream claims: brief/HANDOFF locked troop cells (9.3,24.1)/(11.8,24.1) are
  mis-converted -> (9.5,31.33)/(12.5,31.33) (env.actions.cell_center, grid 18x24); 5cs.27's "4.9% of pro
  skeletons within 1.5 tiles" becomes 8.9% against the true tile.
- Not touched: src/, data/, git. Nucleo uvicorn (pid 63608, port 8765) left alone.

STATUS: complete
