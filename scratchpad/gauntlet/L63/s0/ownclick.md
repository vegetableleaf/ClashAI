# S0 step 2b: own-click contract test (`pipeline/obs_contract.py` live side vs human clicks)

Started 2026-09-05. Question: on real human-play recordings, how well does `from_live(detections, reads, deck, warp=board_warp(deck))`
reproduce the board position of a unit the human just placed? Ground truth = the board click (window fraction) warped into the
board frame with the same `BoardWarp.frame_to_board` the contract uses on a `Detection`'s `(cx, gy)`.

Labels: (a) = measured here, (b) = inferred/untested.

## 0. Setup facts (read from code/config before running anything)

- Clicks: `label.py:41-80 _extract_plays` returns `{t, slot, nx, ny}` where **`t` is the SLOT-SELECT time (`sel_t`), not the
  board click** (`label.py:69,74`). TRAP #1. I keep `_extract_plays` as-is and recover the board-click time by finding the first
  click event at/after `t` whose normalised (x, y) equals the play's (nx, ny) (exact match on the same `norm()` arithmetic).
- Config values (a, read from yaml, not code defaults): icebow `hand.slots=[[0.305,0.890],[0.499,0.886],[0.680,0.891],[0.870,0.888]]`
  (recalibrated 2026-09-04 for the Play Games window), `hand.click_radius=0.06`, `label.pair_timeout=3.0`, `label.arena_top=0.10`,
  `label.arena_bottom=0.86`. hogeq: `hand.slots=[[0.308,0.887],[0.485,0.887],[0.660,0.884],[0.854,0.884]]`, same radius/timeout/band.
- Warp anchors (a): icebow and hogeq configs carry IDENTICAL `env.my_towers/enemy_towers/board_edges/arena_box/sim.board` values
  (board_edges top 0.129 river 0.4425 bottom 0.762 left 0.048 right 0.950; towers as in config.yaml:1065-1066). `BoardWarp` class
  is byte-identical between `icebow/src/clashrl/actions.py` and `hogeq/src/clashrl/actions.py` (the diff is in ActionSpace only).
- Detector (a): icebow `detect.weights=runs/detect/board-24-5/weights/best.pt`, `detect.imgsz=960`, `observation.detector_conf=0.35`,
  `observation.flying_shadow_offset=0.045`, `env.arena_region=[0.03,0.10,0.97,0.86]` (load_detector passes it as the playfield gate).
  hogeq `detect.weights` points explicitly at icebow's board-24-5 (`hogeq/config/config.yaml:1166`) -- hogeq has NO weights of its own
  (`hogeq/runs/detect` does not exist), so the SAME detector serves both decks. `replay_mine.py` is byte-identical across projects.
- play.py:291,300,410 (a): `load_detector(cfg)` then `.detect(frame, conf=observation.detector_conf)`; live then runs `TeamTracker.tag()`
  on top (motion + own-play evidence). OFFLINE single frames only get the stateless bar/body colour vote, so the unknown-team fraction
  measured here is an UPPER bound on live's (b: live's own-play prior would tag most of these plays 'mine').
- Capture geometry (a): 20260804_173304 region [739,38,669,1182] (video 668x1182); 20260804_192006 [734,20,657,1196]; 20260815_222309
  [734,18,657,1198]; hogeq 20260817_194419 [734,18,657,1198]. The video IS the capture region, so `Detection.cx/cy` (fractions of the
  video frame) and the click `nx, ny` (fractions of the region) live in the SAME frame -- no region/fraction mismatch to fix, apart from
  the 1-px even-width rounding on 173304 (0.15%, ignored). BUT the 08-04 sessions have aspect 0.566/0.549 vs 0.548 for the
  08-14-calibrated anchors: warp validity on those two is exactly what this test measures (TRAP #2, candidate).
- Hand identity: `Vision.recognize_hand` needs `templates/cards/<key>*.png`; both projects have them. `Vision`'s slot cache keys on
  `time.time()` (4 s TTL) -- offline frames are processed far faster than real time, so I set `hand.cache_diff=0` for this run
  (TRAP #3; `label.py` does not do this). For hogeq I load hogeq's config through icebow's clashrl with `cfg.root` pointed at hogeq/.
- events.jsonl `t` and meta `frame_times` share the same clock (session-relative seconds) (a: both start ~0-3 s).

## 1. Run log

- Script: `ownclick_run.py <project> <session> <out.json>` (one process per session; icebow's clashrl + the project's config with
  `cfg.root` = project dir; detector = `load_detector(cfg)` exactly as play.py:300, `.detect(frame, conf=0.35)` as play.py:410).
  Per play: 1 select frame (hand read), 1 pre-click frame (t_click-0.10), every frame in [t_click+0.25, t_click+1.5] (~15 at 12 fps).
  "found" = a candidate on side mine/unknown within 3.0 tiles (euclidean) of the warped click in any window frame; first-sighting
  error is reported at the first such frame. Strict = same BASE class as the hand card; fallback = any deck base class.
- Warp anchors the contract built (a): xa = [(0,0.048),(0.194,0.2475),(0.5,0.49625),(0.806,0.745),(1,0.95)];
  ya = [(0,0.129),(0.203,0.205),(0.5,0.4425),(0.797,0.615),(0.906,0.72),(1,0.762)].
- Smoke, icebow/20260804_192006 (a): 16 plays from 118 events -- same 16 the old labeler kept (dataset.npz acts (16,4)), all 16 board
  clicks recovered, hand read succeeded on 16/16 at the select frame. 256 detector frames, 1,265 detections. 15/16 strict found;
  the miss is a tornado (k5) with no `tornado`/`tornado_aoe` detection in the window at all. Note 20 tray presses at x 0.40/0.54/0.63/0.81
  fall outside `click_radius` of every slot centre and are not plays under the labeler's own rule (not changed here; the 08-04 window
  may have had different slot centres -- b).
- Clicks at frame y >= 0.762 (the `board_edges.bottom` anchor) clamp to board y = 1.000 in `frame_to_board` (k0 ny 0.773, k9 ny 0.762)
  while the game still deployed the card (knight seen 2.07 tiles ABOVE the clamped point). Flagged for the pooled analysis (clamping
  hides the true click row; treat plays with click_board y == 1.0 or 0.0 separately).
- icebow/20260804_173304 (a): 30 plays (old labeler: 30 rows in dataset.npz, agrees), 30/30 board clicks recovered, hand read FAILED on
  5/30 (card None) -- this session's window was 669x1182 and the slot centres in today's config were recalibrated 2026-09-04 on the
  657x1196 Play Games window (b: geometry, not template, is the likely cause). 479 frames, 1,936 detections. Three "plays" click at
  ny 0.855-0.860 (the tray's top edge, just inside `arena_bottom`): they clamp to board y 1.0 and nothing appears (nearest same-class
  10-25 tiles away) -- mis-paired tray clicks, not placements (b). Tornado: 2/4 seen (`tornado_aoe`, first at dt 0.98-1.29 s -- the
  spell needs ~1 s to land), the_log 2/3.
- hogeq/20260817_194419 (a): 53 plays (no dataset.npz to compare), 53/53 clicks recovered, hand read 52/53. 833 frames, 2,312 detections.
  STRICT recall is poor for this deck's own cards and I looked at the frames to see why (`ownclick_frames/hogeq_k*.png`,
  detections near the click listed per frame): the placed unit IS detected at the click but NAMED WRONG -- hog_rider -> `knight`
  (k1, k19; only 4 `hog_rider` boxes in the whole session vs 119 `knight`), mighty_miner -> `tesla` / `knight` / `skeleton_king`
  (k6, k11, k25), firecracker -> `skeletons` (k5) or nothing (k10, k14, k32); the own earthquake IS seen as `earthquake_aoe`
  (k37, dt 1.17 s) but colour-tagged `enemy` (44/54 earthquake boxes in this session are 'enemy'), which the mine/unknown filter
  drops. k36 tesla at frame y 0.425 is ABOVE the river centre (0.4425): a refused placement, correctly nothing appears.
  => the identity failure is the DETECTOR's class head on hogeq's cards (board-24-5 was trained on icebow-era footage; b: its training
  set is thin on hog_rider / mighty_miner / firecracker as OWN units), not the contract's geometry. The position question needs a
  class-agnostic measurement, added below (all detections per frame were saved, so the modes are recomputed offline, no more GPU).

## 2. Results (all (a) measured unless marked (b))

Definitions. Window = detector on every frame with t in [t_click+0.25, t_click+1.5] (12 fps -> 15-16 frames/play) plus one
pre-click frame at t_click-0.10. Click -> board via the SAME `warp.frame_to_board(nx, ny)` that `from_live` applies to
detections. A play is "found" when a candidate unit lies within 3.0 tiles (euclidean, tiles = dx*18, dy*32) of the warped click
in some window frame; the error is taken at the FIRST such frame. Matching modes:
  strict     = same base class as the card read from the hand, side in {mine, unknown}   (the contract as a consumer would use it)
  strict_any = same base class, any side (exposes own units colour-tagged 'enemy')
  deck       = any base class in the deck, side mine/unknown (the fallback the task asked for)
  anynew     = any class, any side, but NOT within 1.0 tile of any detection in the pre-click frame (class-agnostic position test)
"unclamped" = click frame-y < board_edges.bottom (0.762) and inside the x edges, i.e. the warp did not clamp the click to 1.0.
Signed y error = unit_y - click_y in tiles; NEGATIVE = the detection sits ABOVE the click on screen (toward the enemy).

### 2.1 Per session (strict, unclamped plays; the sessions' full blocks incl. all modes are in ownclick_analysis.out)

| session | plays extracted | card id'd | unclamped | strict found (recall) | strict_any | anynew | abs x med/p90 | abs y med/p90 | signed y med/p90 (frac above) | first dt med | team of hit m/u | conf med |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| icebow 20260804_173304 | 30 | 25 | 23 | 18 (0.78) | 19 | 23 (1.00) | 0.30/0.85 | 0.82/1.21 | -0.36/+0.61 (0.72) | 0.33 s | 6/12 | 0.84 |
| icebow 20260804_192006 | 16 | 16 | 14 | 13 (0.93) | 13 | 14 (1.00) | 0.30/0.63 | 0.62/1.79 | +0.30/+1.79 (0.46) | 0.33 s | 4/9 | 0.86 |
| icebow 20260815_222309 | 177 | 169 | 148 | 130 (0.88) | 141 (0.95) | 146 (0.99) | 0.29/0.79 | 0.68/1.79 | -0.27/+1.76 (0.64) | 0.32 s (p90 0.89) | 35/95 | 0.83 |
| hogeq  20260817_194419 | 53 | 52 | 47 | 26 (0.55) | 27 | 41 (0.87) | 0.28/0.81 | 0.82/1.77 | -0.34/+1.77 (0.65) | 0.33 s | 0/26 | 0.80 |

Board-click recovery: 0 plays in any session without a matching click event. Hand read (card identity): 25/30, 16/16, 169/177,
52/53. The 5 misses in 173304 are (b) the 08-04 window geometry vs the 09-04 slot calibration (see traps).
192006's positive median y is n=14 with two enemy-half pocket plays at +1.9/+2.45 tiles; its my-half troop plays are -0.46/-0.84
like the other sessions.

Per-session by kind (strict; n / found / signed-y median):
  173304  troop 8/6 (-0.89, all above)  building 5/5 (-0.06)  spell 10/7 (dt med 0.33)
  192006  troop 6/5 (+0.87, see note)   building 4/4 (+0.53)  spell 4/3
  222309  troop 65/61 (0.94; -0.64, 0.75 above)  building 33/32 (0.97; -0.01)  spell 50/37 (0.74; -0.05; first dt med 0.36, p90 1.18)
  hogeq   troop 34/17 (0.50; anynew 29 = 0.85; -0.72)  building 6/5 (0.83; +0.04)  spell 7/4 (0.57; anynew 7/7)

Per-session detector statistics over ALL window+pre frames (every detection, conf gate 0.35 = observation.detector_conf):
| session | frames | dets | conf p10/p50/p90 | frac conf<0.5 | frac conf>=0.9 | team mine/enemy/unknown | unknown by kind troop/building |
|---|---|---|---|---|---|---|---|
| 173304 | 464  | 1936  | 0.552/0.862/0.922 | 0.071 | 0.213 | 0.298/0.477/0.226 | 0.148/0.372 |
| 192006 | 252  | 1265  | 0.618/0.865/0.914 | 0.052 | 0.233 | 0.335/0.335/0.330 | 0.332/0.312 (spell 0.392) |
| 222309 | 2816 | 11823 | 0.470/0.830/0.909 | 0.125 | 0.140 | 0.371/0.389/0.239 | 0.228/0.250 |
| hogeq  | 821  | 2312  | 0.417/0.782/0.919 | 0.196 | 0.145 | 0.186/0.518/0.296 | 0.303/0.316 |

### 2.2 Pooled (4 sessions, 276 plays, 262 with card identity, 4353 detector frames, 17336 detections)

Recall (placed unit found within 1.5 s):
  all identified plays        strict 192/262 = 0.73
  unclamped identified plays  strict 187/232 = 0.81   strict_any 201/232 = 0.87   deck 207/232 = 0.89   anynew 224/232 = 0.97
  ALL unclamped plays incl. unidentified card, anynew: 235/243 = 0.97
  clamped plays (click frame-y >= 0.762 or at an x edge): 33 rows, 30 identified: strict 5/30 = 0.17 (see 2.4 -- most are not plays)

Position error at first sighting, unclamped, strict (n=187):
  abs x median 0.29 tiles, p90 0.83;  signed x median -0.03, p90 +0.48  (x is unbiased)
  abs y median 0.72 tiles, p90 1.78;  signed y median -0.25, p90 +1.76;  64% of hits ABOVE the click
  window-median signed y (median over all hit frames of a play, then median over plays): -0.31
  first sighting dt: median 0.32 s (= the first window frame; the unit is already visible at +0.25 s), p90 0.87 s
  team of the hit: mine 45 / unknown 142 (strict_any adds 62 hits that are the own unit tagged 'enemy': m/e/u 34/61/106 -> 30% of
  the human's own just-placed units carry the 'enemy' tag, 53% 'unknown', only 17% 'mine' -- offline colour vote, no TeamTracker)
  conf of the hit: median 0.84, p10 0.42, p90 0.91
anynew (n=224): abs x 0.33/1.15, abs y 0.75/1.87, signed y -0.19/+1.61, dt 0.30/0.61.

By kind (strict, unclamped):
| kind | n | found (R) | abs x med/p90 | abs y med/p90 | signed y med/p90 (frac above) | notes |
|---|---|---|---|---|---|---|
| troop    | 113 | 90 (0.80)  | 0.28/0.85 | 0.93/1.56 | -0.64/+1.29 (0.74) | anynew 106 (0.94), signed y -0.60 |
| building | 48  | 46 (0.96)  | 0.32/0.85 | 0.73/2.14 | +0.01/+2.14 (0.48) | x_bow/tesla centred on the click |
| spell    | 71  | 51 (0.72)  | 0.27/0.69 | 0.35/1.78 | -0.05/+1.77 | first dt 0.34/1.19; strict_any 62 (0.87, 26 hits tagged enemy); anynew 71 (1.00), signed y -0.04 |

Restricting to my-half clicks (click board y >= 0.5) the picture is sharper:
  troop    n=73  signed y median -0.73 (mean -0.69)           abs y med 0.75 p90 1.41
  building n=38  signed y median -0.09                         abs y med 0.44 p90 1.41
  spell    n=32  signed y median -0.05                         abs y med 0.28 p90 0.95

By click depth (strict, unclamped; board y):
  back  y>=0.8     n=28  R 0.75  abs y 0.29/0.94  signed y -0.29/+0.13
  mid   0.6-0.8    n=99  R 0.90  abs y 0.64/1.38  signed y -0.55/+0.31 (0.78 above)
  front 0.5-0.6    n=39  R 0.85                   signed y -0.14/+1.23
  enemy half y<0.5 n=66  R 0.67  abs y 1.32/2.59  signed y +1.16/+2.59 (0.27 above)  anynew 62/66, signed y +0.99/+2.54

Per card (strict, unclamped; found/n, signed y median):
  x_bow 21/22 +0.01 | tesla 22/23 +0.01 | tesla_evo 3/3 | skeletons 36/38 -0.65 | ice_wizard 22/25 -0.63 (0.91 above) |
  knight 14/14 -0.17 | knight_evo 10/11 -0.40 | ice_spirit 7/8 -0.52 | the_log 28/30 -0.04 | rocket 10/18 -0.42 (anynew 18/18; the 8
  misses = rocket_aoe tagged enemy or named the_log/tesla) | tornado 13/20 (anynew 20/20; first dt 0.63 med, 1.26 p90 -- the
  tornado_aoe appears later than other spells) | earthquake 0/3 (anynew 3/3 at dt 0.98-1.30, all tagged enemy) |
  firecracker 1/5, firecracker_evo 0/3, hog_rider 0/3 (anynew 2/3, named knight), mighty_miner 0/6 (anynew 6/6, named tesla/knight/
  skeleton_king/phoenix).
  Strict-miss-but-anynew-hit naming (pooled, top): rocket->rocket(enemy) 4, tornado->tornado(enemy) 4, rocket->the_log(enemy) 2,
  firecracker->skeletons 2, mighty_miner->tesla 2, mighty_miner->knight(enemy) 2, then 1 each (full list in ownclick.json
  pooled.strict_miss_named_as).

Spell count: 71 unclamped identified spell plays (rocket 18, tornado 20, the_log 30, earthquake 3) + 5 clamped spell rows.
The detector emits spells only as `*_aoe` transients (rocket_aoe, tornado_aoe, the_log_aoe, earthquake_aoe); `from_live` routes
them to `bs.spells` via vocab.is_spell. Pooled spell detections: n=1468 of 17336 (8.5%).

Pooled detector statistics (n=17336 detections over 4353 frames):
  conf p5/p10/p25/p50/p75/p90/p95/p99 = 0.405/0.471/0.670/0.835/0.884/0.912/0.930/0.970, min 0.350 (the gate), max 0.995
  histogram 0.35..1.00 in 0.05 bins (fraction): .046 .039 .038 .036 .038 .038 .043 .052 .072 .162 .281 .132 .023
    -> a flat floor of ~4%/bin from 0.35 to 0.75 (12.3% below 0.5), then a peak in 0.80-0.95 (57% of detections)
  team mine/enemy/unknown = 0.336/0.412/0.252
  by kind: troop n=11851 unknown 0.235 conf p10/50/90 0.44/0.80/0.90; building n=4017 unknown 0.286 conf 0.78/0.88/0.91;
           spell n=1468 unknown 0.295 conf 0.47/0.85/0.94

### 2.3 What the y sign means
(a) Own troops are detected 0.6-0.8 tiles ABOVE the click at mid depth, buildings and spells are centred on it. The offset scales
with the sprite: over the 73 my-half troop hits, error_y / box_height_in_tiles has median -0.354 (p25/p75 -0.479/-0.158; box
height median 2.53 tiles; per card: skeletons -0.378, ice_wizard -0.372, knight -0.354, ice_spirit -0.325, knight_evo -0.247).
That is the box CENTRE vs the unit's FEET: `from_live` uses `warp.frame_to_board(d.cx, d.gy)` and for ground units
`Detection.gy == cy` (replay_mine.py:88-96 -- ground_cy is only set for flyers via the shadow offset), so a troop's board y is its
sprite centre, ~1/3 of a box above the tile it stands on. Shifting the detection down by k*h gives a residual signed-y median of
-0.42 (k=0.15), -0.31 (0.20), -0.21 (0.25), -0.10 (0.30) with abs y median 0.35 and p90 0.88 at k=0.25 (vs 0.75 / 1.41 unshifted).
(b, untested) the same applies to enemy troops, so the live board is ~0.7 tiles "forward" for every troop relative to the engine,
which reports ground positions.

(a) In the ENEMY half the sign flips: detections sit +1.2 tiles BELOW the click (n=66, anynew median +0.99). Per card: x_bow
+2.28 (n=7), skeletons +1.58, knight +1.10, the_log +2.09 (n=6), but rocket -0.42 and tornado -0.33 (spells land where clicked).
34 of the 66 are troops/buildings clicked at board y 0.46-0.50, i.e. ON the river line (x-bow-at-the-bridge style) or in a pocket.
(b) The game snaps an illegal drop to the nearest legal tile on my side (1-2 tiles below the river), so for these plays the click
is NOT the ground truth -- the snapped tile is. This is a labelling caveat for the IL data path too: label.py stamps the raw click
(nx, ny), so river-edge placements are labelled in the enemy half. The contract is not at fault here; the my-half medians
(troop -0.73 / building -0.09 / spell -0.05) are the contract's real numbers.

### 2.4 The clamped rows (33 of 276)
Clicks at frame y >= 0.762 warp to board y = 1.0. Two populations (a):
  * frame y in [0.762, 0.80): 6 rows (ice_wizard x4, knight x2), anynew 4/6 found at signed y -0.74..-0.93 -> real bottom-row
    placements; board_edges.bottom = 0.762 is the last tile row and the game accepts taps a little below it.
  * frame y in [0.80, 0.86): 25 rows (out of 276 = 9.1%), anynew 0/25 found (vs 235/243 elsewhere) -> NOTHING was placed. These
    are taps on the upper part of a tray card. label.py:48-57: `which_slot` demands ny >= a_bot (0.86) for a slot select while
    `on_arena` admits ny < 0.86, and the card art extends to ~0.84, so a tap on the top of a card while a select is pending is
    emitted as a "play" at the tray edge (and the pending select is consumed, so the real placement that follows is lost).
    hogeq: 5 of its 53 plays; 222309: 17 of 177.

## 3. Calibration of degrade() constants (pipeline/obs_contract.py)

* `_CONF_RANGE = (0.35, 1.0)` uniform: (a) contradicted in shape. Measured conf is p10 0.47 / p50 0.835 / p90 0.91 / p99 0.97,
  with 57% of mass in 0.80-0.95 and a ~4%/bin floor from 0.35 to 0.75. Proposal: sample from the empirical histogram above
  (13 bins), or as a two-part mixture: with prob 0.30 uniform(0.35, 0.78), else clip(normal(0.86, 0.045), 0.35, 0.995). Own
  just-placed units are not special: their first-sighting conf is p10/50/90 0.42/0.84/0.91.
* `_FP_JITTER_TILES = 1.0`: (a) for TRUE positives the position noise is anisotropic: abs x median 0.29, p90 0.83; abs y median
  0.72, p90 1.78, and the y part is mostly a systematic sprite-centre offset (troops -0.7 tiles), not jitter. After removing that
  offset the troop residual is abs y 0.35 / p90 0.88. Proposal: jitter x ~ N(0, 0.45) tiles, y ~ N(-0.6*is_troop, 0.7) tiles, or
  better fix the offset in from_live (section 5) and jitter both with sigma ~0.45. (b) The FP position distribution itself was
  not measured here (no enemy ground truth in human play); 1.0 tile for false positives is untested, not contradicted.
* `unknown_team_rate` (default None): (a) offline colour vote gives unknown 0.252 overall (troop 0.235, building 0.286, spell
  0.295; by session 0.226-0.330). For the human's OWN units it is worse: 53% unknown and 30% 'enemy'. (b) live play.py adds
  TeamTracker persistence which should lower these; treat 0.25 as the upper bound for `unknown_team_rate` and note that a
  non-zero WRONG-team rate (~0.30 for freshly placed own units, ~0.42 for own spells) is not modelled by degrade() at all.
* `DEGRADE_RECALL = 0.855`: (a) consistent with what a same-class consumer sees for own placements at 0.25-1.5 s (strict 0.81,
  strict_any 0.87, class-agnostic 0.97); the remaining loss is class confusion + team tag, not missed boxes.

## 4. Traps hit (all (a) unless noted)
1. `_extract_plays` returns `t` = SLOT-SELECT time, not the board click (label.py:73,77). Windows keyed on it are early by the
   select->place latency. Fixed here by matching the play's normalised (nx, ny) to the next click event; 0 failures / 276.
2. `Vision.recognize_hand` caches per slot with a WALL-CLOCK TTL (`hand.cache_diff`); offline it returns stale slots. Set
   `cfg.data["hand"]["cache_diff"] = 0`.
3. Both projects' packages are named `clashrl`; hogeq was run through icebow's package with `cfg.root = REPO/hogeq` after verifying
   BoardWarp / replay_mine byte-identical. hogeq has no weights of its own: hogeq/config/config.yaml:1166 points at icebow's
   board-24-5 best.pt (absolute path); hogeq/runs/detect does not exist.
4. `frame_to_board` clamps to [0,1]: clicks below the field become y = 1.0 silently and any consumer would see a legal
   back-row unit. 25 of 276 extracted "plays" (9.1%) are tray-card taps admitted by `label.arena_bottom = 0.86` (section 2.4).
5. Team colour vote on spells is noise: 26/62 own spell hits tagged 'enemy'; all 3 own earthquakes and 44/54 earthquake_aoe boxes
   in hogeq tagged 'enemy'. A strict mine/unknown filter hides own spells.
6. Class confusion on hogeq's cards: hog_rider -> knight, mighty_miner -> tesla/knight/skeleton_king/phoenix, firecracker ->
   skeletons/tesla/three_musketeers. Strict recall 0.55 vs class-agnostic 0.87. (b) board-24-5 is icebow-era; its training set
   is thin on those classes as OWN units.
7. 08-04 sessions have a different window aspect (region 669x1182 and 657x1196 vs 657x1198 on 08-15/08-17); 5/30 hand reads fail
   on 173304 and the play geometry is the 09-04 calibration applied to an older layout (b: sub-tile effect, not isolated).
8. River-line / enemy-half clicks (66/232) are snapped by the game; the click is not ground truth there (section 2.3).
9. Tool-level: Git Bash `tail -3` is rejected (use `tail -n 3`); a foreground `sleep` is blocked, wait with a background
   `until grep -q ...` loop; a multi-line heredoc containing pipe tables tripped the Bash tool once (written via a temp file).

## 5. Contract findings and proposed fixes (no file under pipeline/ or icebow/src was modified)

F1 (a) Troop y is the sprite centre, not the ground tile. pipeline/obs_contract.py `from_live`: `bx, by =
   warp.frame_to_board(d.cx, d.gy)`; icebow/src/clashrl/replay_mine.py:88-96 `gy` returns `cy` unless `ground_cy` was set (flyers
   only). Measured: own troops at my-half clicks sit -0.73 tiles (median, n=73) above the click, i.e. -0.354 box heights;
   buildings -0.09, spells -0.05. Fix (in from_live, contract-side, so the detector is untouched): for non-spell, non-building
   classes use `fy = d.gy + K * d.h` with K = 0.25-0.30 (residual median -0.21 / -0.10, abs y median 0.35, p90 0.88 at K=0.25).
   K should be re-measured on flyers separately (b: fly_offset 0.045 already moves them; not measured here, no flyers in either
   deck). A kind lookup exists already (`vocab.kind_of`), so the branch is cheap. Whether K also holds for enemy troops is (b).
F2 (a) Team tags on own units: only 17% 'mine' at first sighting offline; the contract's `side` for a freshly placed own unit is
   'unknown' 53% and 'enemy' 30% of the time. Not a from_live bug (it forwards `d.team`), but degrade() models neither the
   wrong-team case nor the fact that own SPELLS are wrong 42% of the time (26/62). Proposal: add `wrong_team_rate` (troop ~0.15
   b after TeamTracker, spell ~0.4) to degrade(), and have the engine side ignore `side` for spells -- (b) proposal, untested.
F3 (a) `frame_to_board` clamping (actions.py BoardWarp) makes off-field clicks/detections look like legal board-edge positions.
   For from_live this affects detections whose cx/gy fall outside the anchors (tray, top HUD): they become y = 0.0 / 1.0 units.
   Not counted here (all_dets were within the arena_box gate), so the rate is (b). Proposal: in from_live drop detections whose
   raw frame y is outside [board_edges.top - 0.02, board_edges.bottom + 0.03] instead of clamping them.
F4 (a) Labeller, not the contract: label.py:48-57 emits tray-card taps as plays (25/276 = 9.1%, zero of them produced a unit).
   Fix: `which_slot` should test ny >= a_bot - ~0.03 (card top), or `on_arena` should use board_edges.bottom + 0.03 (~0.79)
   rather than `label.arena_bottom` 0.86. Also stamp the board-click time (or both) instead of sel_t (trap 1).
F5 (a) Labeller: river-line clicks (board y 0.46-0.50) label the CLICK, but the unit appears 1-2 tiles below (the game snaps).
   Spells are unaffected (rocket -0.42, tornado -0.33, log varies). (b) Fix: clamp troop/building labels to the nearest legal
   deployable cell (ActionSpace.deployable_mask) before training; measure on this data whether that removes the +1.2 bias.
F6 (a) Detector transients: tornado_aoe first appears at 0.63 s median (p90 1.26) and earthquake_aoe at ~1.0-1.3 s after the
   click, rockets/logs at 0.34 s median. A consumer polling at 0.25 s will miss tornado/earthquake casts for ~0.5-1 s; nothing to
   fix in the contract, but the engine-side spell timing should not assume t_cast = t_first_seen for those two.

## 6. Bottom line
(a) On real human play the live contract reproduces an own placement's X to 0.3 tiles median / 0.8 p90 with no bias, and its Y
to 0.7 tiles median / 1.8 p90 with a class-dependent bias: troops -0.7 tiles (sprite centre above the feet; fixable with a
0.25-0.30 box-height shift, F1), buildings and spells ~0. Same-class recall at 0.25-1.5 s is 0.81 (0.87 ignoring the team tag,
0.97 class-agnostic); the losses are team tags and detector class confusion (hogeq cards), not missing boxes. The human's own
units are tagged 'mine' only 17% of the time offline. Enemy-half / river-edge clicks (28% of plays in this data) are not ground
truth because the game moves the unit; they are excluded from the bias estimates above and flagged for the IL labeller (F5).
Two labeller defects were found on the way (F4 tray taps 9.1%, trap 1 select-time stamp).

Artifacts: ownclick_run.py (GPU, per session), ownclick_analyze.py (offline recompute -> ownclick.json + ownclick_analysis.out),
ownclick_<project>_<session>.json (raw per-play frames + all detections), ownclick_frames/ (annotated hogeq frames).
GPU use: 4353 detector frames total. No game / emulator / engine port touched. No data file modified.

STATUS: complete
