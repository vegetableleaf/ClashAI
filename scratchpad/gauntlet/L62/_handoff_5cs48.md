
### §5cs.48 -- L62i (2026-09-05 20:0x UTC, owner claim tested): **(c) CONTRADICTED ON BOTH HALVES -- grid 432 does NOT snap an x-bow a tile back, and switching to 576 would CREATE that failure in 55% of offensive x-bow placements.** Owner: "size 432 is causing the policy to snap one of the offensive x-bow positions one tile too far back... I suggest trying size 576." Measured on all **2,617 real pro x-bow placements** in the crawl, through the same `ActionSpace` the trainer quantises with: the 432 grid's row pitch is **0.499 tiles** (not 1.333 -- the grid spans 19.7 tiles, not 32), backward shift p99 **0.304 tiles**, and for the 240 x-bows actually within reach of an enemy princess tower quantisation adds **0.000 tiles** and puts **0 of 240 out of reach**. At 576 the pitch is **0.374 tiles**, the mean |dy| is **3x worse** (0.289 vs 0.097), and **132 of 240 (55.0%) in-reach pro x-bows are pushed OUT of reach**. The cause is PHASE, not resolution: pros place on the half-tile lattice and 0.499 aligns with it; 0.374 does not.

Measured by the lead: `scratchpad/gauntlet/L62/grid_quant_probe{,2,3}.py` (read-only; no checkpoint, no
running process touched). Source rows `icebow/data/royaleapi/crawl2/plays_ext.csv` (`attr_card == "x-bow"`,
2,617 with positions). (a) unless marked.

**A. The grid is not what its docstring says.** `actions.py:5` calls 18x32 "one cell per board tile". Measured
through `cell_center`, both grids span the SAME box -- columns 1.38..16.57 tiles (x pitch **1.026**, identical at
both sizes, so this claim is about ROWS only) and rows 7.91..27.62 = **19.7 tiles**, not 32. So 24 rows = 0.499
tiles/row and 32 rows = 0.374 tiles/row. The docstring is stale relative to the calibrated `arena_box`; nothing
reads it, but it is what makes "576 = one cell per tile" sound right. **Trap: the 1.333-tiles/row figure that makes
the owner's mechanism plausible does not exist at any grid size.**

**B. Quantisation on real pro x-bow placements (2,617).**

| grid | row pitch | mean abs dy | p99 abs dy | max abs dy | mean backward | backward > 1 tile |
| --- | --- | --- | --- | --- | --- | --- |
| 18x24 (432) | **0.499** | **0.097** | 0.304 | 1.877 | +0.008 | 0.11% |
| 18x32 (576) | 0.374 | 0.289 | 0.340 | 1.815 | **-0.155** | 0.11% |

The 1.87-tile maxima are the same 3 placements at BOTH sizes -- rows outside the grid's 7.91..27.62 span, clamped to
the edge row. Resolution does not fix them and 576 does not either. Everything else is bounded by ~0.34 tiles.

**C. The functional test (the owner's actual claim).** x-bow reach 11.5 tiles centre-to-centre + 1.5 tile tower
radius = 13.0 to tower centre (engine-measured 13.04, §5cs.43); enemy princess towers taken from the sim at
(3.5, 6.5) / (14.5, 6.5) and (3.5, 25.5) / (14.5, 25.5) tiles, the enemy pair chosen as the one on the other half
from the placement (avoids the unestablished blue/red -> side mapping). Of 2,617 pro x-bows, **240 are within reach
of a princess tower** ((b) the other 91% are defensive placements or my 13.0 threshold is too tight -- unverified,
and it does not affect the comparison since both grids use the same subset):
- **432: 0 of 240 pushed out of reach, worst distance added +0.000 tiles.**
- **576: 132 of 240 (55.0%) pushed out of reach, worst +0.340 tiles.**
Mechanism: pro x-bow placements sit on the HALF-TILE lattice (`tile_y` values are all X.5), 0.499 pitch lands on it,
0.374 does not. And because an offensive x-bow is placed AT the range boundary, a 0.2-0.3 tile backward shift is
exactly the difference between hitting the tower and sitting there -- which is why the finer grid is worse.

**D. What IS true, since the owner's observation is real.** The symptom was seen in `sim-view` on
`engA_kl_m253.pt` -- the COLLAPSED checkpoint (§5cs.46: 0.12 plays/match, gate constant, cell head 1+ nat from the
pro prior). (b) The most probable cause is the policy choosing the wrong CELL, not the grid quantising the right one:
at 0.499 tiles/row a ONE-CELL policy error is ~0.5 tiles, which for a boundary-placed x-bow is exactly "sits there
and does not reach". Note the asymmetry this creates: 576 would shrink a one-cell error to 0.374 tiles, but its
systematic phase penalty (+0.155 mean backward, 55% out of reach) costs far more than the 0.125 tiles it saves.
(b) A phase-preserving refinement -- 48 rows at 0.25 tiles/row (864 cells), still aligned to the half-tile lattice --
would give finer control without the phase cost; NOT recommended now, because it changes `n_cells` and therefore
invalidates the BC init, both `bc_pro` val sets and the running pair.

**E. Cost of the proposed change, for the record.** `n_cells` is baked into `bc_bias_native_s0.pt` (432), both
grading val sets, `engine_env.cell_to_engine`, and every engA/engB checkpoint. Switching grids is not a config flip:
it is a BC re-fit plus a new val set plus a relaunch, i.e. the whole IL pipeline. That cost is why this was measured
before it was attempted.

**Not established.** Why only 240/2,617 pro x-bows are in tower reach (threshold or frame; (b) worth a look because
if the frame is off by a row the subset changes -- the 432-vs-576 CONTRAST is robust to it, the absolute 55% is not);
what actually made the watched x-bow fall short (the collapsed checkpoint is the hypothesis, not a measurement);
whether the 3 clamped placements matter in play.
