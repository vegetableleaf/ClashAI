

### §5cs.29 -- L58 (2026-09-04): radius-graded reward STEP 0 built (geometry_reward.py + sim-view --radii) and the VALIDATION GATE run on 211 pro replays + 72 c2r_best matches: no term is dropped by the doc §3 rule (modal Tesla (9,21) beats the corner on the sum 88%/6%), but the equal-weight SUM ranks the pros ABOVE the locked tile for only 2 of 8 cards -- P2 cover on troops/spells and P7 on skeletons work AGAINST the pros, building P5 has no placement gradient, snapshot P1 is silent on 59% of pro Teslas; w_geom = 2.0 (cap) on the restricted sum; trunk holds ROLE-level enemy identity only (linear probe 12% card / 39% role); TWO RETRACTIONS (corner bow reaches the princess; locked troop cells were mis-converted)

**Built (commit c642a73).** `icebow/src/clashrl/geometry_reward.py` (pure; `radii_of` is the one radius
table for reward AND overlay; `board_from_engine`, `score_placement` -> P1..P7 + bridge-block + tornado
away/king terms), `tests/test_geometry_reward.py` (19 OK), `sim-view --radii` overlay (flag off =
byte-identical frames 103/103). Nothing wired into env.py yet. Details + CHOICE list:
`scratchpad/gauntlet/L58/impl_geometry.md`. Gate files: `gate.md`, `gate_replay.py`, `gate_plays.csv`
(6,639 rows), `gate_summary.txt`, `p2/policy_scores.csv` (2,485), `probe.txt`.

**(c) RETRACTION 1 -- the corner X-Bow DOES reach the enemy princess.** §5cs.27 / doc rev 1-3 said it
does not, quoting the engine comment at `engine.py:2567` (11.18 tiles at y 0.56). The running engine's
`_gap` from (1.5,18.5) to the princess hitbox edge is 10.67 < 11.5 and a deployed bow there locks and
damages the tower (4858 -> 4568 in 6 s). The comment is stale. L56 (b)(1) "234 is rewarded because it
reaches the tower" goes back to (b) untested; §5ag's 17%/48% reaching/neither split needs `_gap`.

**(c) RETRACTION 2 -- the locked troop cells.** §5cs.26/27 gave the Skeletons cell as tile (9.3,24.1) and
the Knight cell (11.8,24.1): mis-converted (`env.actions.cell_center`, grid 18x24). Measured landing
tiles in 72 c2r_best matches: skeletons (9.5,31.3) x492/504, knight (12.5,30.0) x184 + bridge tiles
(3.5,18)/(14.5,18) x122. Pro skeletons within 1.5 tiles of the TRUE cell: 8.9% (not 4.9%) -- behind the
king is a pro spot too (§5cs.27's own pro modal (9,31)/(8,31)).

**(a) measured -- gate Part 1 (211 replays, 6,639 icebow-card plays, 22 candidate tiles + pro tile).**
Pro tile beats / loses to the locked tile on the equal-weight SUM (against the TRUE locked cells):
tesla 63%/19% (n=807), tornado 69%/29% (425), knight 51%/9% (978), ice-wizard 44%/22% (922), skeletons
40%/22% (979), log 34%/32% (866), rocket 16%/65% (305), x-bow 11%/83% (543). Terms in the pros' favour:
P1 (tesla 32/15), P2 for BUILDINGS (tesla 54/16), P4 (all spells), P3 (skeletons 35/0, knight 36/1 -- a
unit behind the king cannot intercept), P5 (troops 27/9). Terms AGAINST the pros: P2 on troops
(skeletons 2/23 -- pros use the river bank, cover 0.47 vs 0.56 behind the king; on its own P2 would HOLD
the current cell), P2 on spells (79% of pro rockets land on the enemy half, cover 0 by construction ->
rocket 1/71, median rank 22), P7 on skeletons (0.1/7.6 -- pros surround), P6 (corner 0.95-0.98 vs pro
lane bows 0.92-0.94 = level; pro centre bows are defensive, P6 0 by design -> 2/90). Building P5 is
tile-independent (tie 100%). Doc §3 gate rule on 350 Hog/Giant/PEKKA Tesla boards: modal (9,21) vs
corner -- P1 median diff 0 (both 0 on 44%; on the 196 active boards +0.25, 74%/20%), P2 +0.50
(82%/0%), SUM +0.50 (88%/6%) -> nothing dropped. Snapshot P1 fires on 40.9% of pro Teslas only (threat
gap median 6.2 tiles when it fires): pros PRE-PLACE while the threat is still outside the band.
Per-card vs role-average radii (pro-tile rank unchanged): P1 93% of all plays but 52% where P1 fires
(n=437), P7 34% where it fires (n=139), P5 86% (n=1,757), P3/P6 > 0.93, P2/P4 radii-free; the pro>lock
fractions agree to 0.01-0.03 on every card x term.

**(a) measured -- Part 2 (c2r_best, 3 seeds x 24 matches, tau 0.25, 2,485 placements).** Per match:
skeletons 7.0, knight 6.6, ice_wizard 6.5, tesla 5.8, log 4.7, x_bow 2.9, tornado 1.0, rocket 0 (never
under tau 0.25). SUM mean 0.828 (per seed 0.811/0.826/0.845) -> w 1.21 raw; with the 1d restrictions
(no P2 on troops/spells, no building-P5) mean 0.430 -> **w_geom = 2.0 (cap)**. Building P1 mean 0.093,
>0 on 21%. The locked tiles already earn ~0.8-1.3 from gradient-free terms (tesla P5 0.61, corner bow P6
0.64, skeletons P2 0.45); the pro-direction delta is 0.1-0.3 per placement.

**(a) measured -- Part 3 linear probe (6,264 single-enemy steps, split by match).** Card identity from
the trunk: 12% test (majority 6%, 83 classes, train 52% = memorising); ROLE 39% vs 26% majority. The
trunk holds role-level identity, not card-level -> the §7.8 decision (no obs change in run 1) stands,
and the role-average band is what the model can act on; per-card radii kept in the reward (owner's
intent; the per-card deviation is noise around the role mean the trunk can see -- directionally identical).

**(b) plausible, untested.** (1) A PATH-based P1 (band on the min distance from the building to the
threat's forward lane path, not its current position) would fire on the 59% of pro Teslas the snapshot
misses -- measurement: rerun Part 1 with it. (2) Whether a 0.1-0.3 per-placement delta at w 2.0 moves
the argmax cell against the outcome terms -- that is the training arm. (3) Bridge-block detected on
532/5,825 pro plays, case=1 on 160: the case logic is untested against the video's examples.

**Decisions for step 1 (env wiring).** P2 -> buildings only. P7 -> not for swarm cards. Building P5 -> a
play-timing term, excluded from the placement sum and from w. P1 -> path-based (b1) before wiring.
w_geom 2.0. Per-card radii. Bridge-block credit as §7.4. Live: log-only.

**Traps found.** (1) `env.reset()` keeps the same engine object -- a deploy wrapper installed per reset
double-wraps (10,042 "placements" in 24 matches); guard the install. (2) `sim-view` has no duration
flag; a 1-match mp4 is the full 180 s. (3) No pytest in the venv -- `python -m unittest`. (4) Greedy
c2r_best never plays Rocket at tau 0.25 (n=0 in 72 matches).
