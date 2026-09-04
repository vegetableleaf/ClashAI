

### §5cs.27 -- WHERE PROS PUT THESE CARDS vs where the policy puts them (2026-09-04, L57): the policy's X-Bow cell IS the pros' modal lane-bow spot to within ~1 tile (24% of 1,038 pro bows within 1.5 tiles, 50% lane-mirrored), but its Tesla cell matches 2.0% of 1,705 pro Teslas (pros: x=9 dead centre 48%, x 6-11 81%, y 18-22), Skeletons 4.9%, Knight 2.2%. The sim stays flat corner-vs-centre even with the L52 `hidden_pull` mechanic (935 vs 1029, CIs overlap) -- the missing pull is NOT why; it only lifts the lane cell (690 -> 966). Decision put to the owner: a fitted pro placement prior as a KL term on the cell head (mechanism stated; differs from the three failed rollout-sampling priors), or opponent work

**Sources.** `icebow/data/royaleapi/crawl2/plays_ext.csv` (§5ag: 12,220 blue plays with tile coords; blue = the
icebow side, own half HIGH y, river at tile 16). Policy cells -> sim landing tiles read from L56's
`tesla_probe.json` (cell 234 -> tile (1.5, 18.5); 274 -> (4.5, 20.5); 314 -> (8.5, 23.5); 423 -> (9.3, 24.1);
426 -> (11.8, 24.1)). Crawl records buildings on tile corners (§5cs.22 div. 2), so +-0.5 tile of convention
slop applies to every comparison below. Outputs: `scratchpad/gauntlet/L57/pro_tiles.txt`,
`tesla_probe_pull.py/.txt/.json`, `pull_vs_base.txt`.

**(a) measured -- pro placements (blue side, n per card).**
- X-Bow n=1,038: modal tiles (15,19) x250 and (2,19) x248 = 48% -- lane bows 2 tiles from the edge, 3.5
  tiles behind the river; centre (8-9,22) 132. Policy tile (1.5,18.5): 24.2% of pro bows within 1.5 tiles,
  26.4% within 2.5, 50.4% with lanes mirrored. The corner X-Bow is a pro placement pushed ~1 tile to the
  edge and ~1 tile shallower. Live cell 235 (col 1 -> x 2.4) is CLOSER to the pro tile than the sim's 234.
- Tesla n=1,705: x median 9.0 (p10 6, p90 12); x=9 in 811 = 48%, x 6-11 = 81%; y median 20, p10 18,
  p90 22; modal tiles (9,21) 259, (9,18) 155, (9,19) 149, (9,22) 140. Within 2 tiles of either edge: 6.0%.
  Policy tile (1.5,18.5): 2.0% of pro Teslas within 1.5 tiles (3.8% mirrored).
- Skeletons n=1,987: modal (8,17)/(9,17) = centre river bank, or (9,31)/(8,31) behind the king; policy
  tile (9.3,24.1) = 4.9% within 1.5 tiles. Knight n=2,031: modal (9,31)/(8,31) behind the king, lane bank
  (2,17)/(15,17); policy (11.8,24.1) = 2.2%. Ice Wizard n=1,917: (8,31)/(9,31) behind the king. Log
  n=1,802: (14,17)/(3,17) lane bank. Tornado n=979: (8,24)/(9,24) = the classic king-activation pull.
- So the owner's "atrocious" applies to the Tesla / Skeletons / Knight cells, NOT the X-Bow cell: the
  X-Bow is where pros put it. The single-cell lock is the problem for every card; for the X-Bow the
  locked cell happens to be right.

**(a) measured -- sim with the `hidden_pull` patch (L52 mechanic: a hidden Tesla is a pathing target for
building-targeters), same probe/arms/seeds/tau as L56.** Per-Tesla damage (upper bound) pooled, n 281-293:
own 1033 [912,1161], corner 935 [826,1049], lane 966 [843,1095], centre 1029 [894,1164]; per seed corner vs
centre 1075 vs 966 and 824 vs 1087 (all CIs overlap). vs L56 base: own 954, corner 1040, lane 690, centre
1157. The pull lifts the LANE cell (690 -> 966, pooled CIs disjoint; 731 -> 1034 and 644 -> 895 per seed)
and leaves corner = centre. Match level (24/arm/seed): W 9/10/5/6 and 8/8/10/5 -- noise.

**(c) contradicted.** My in-loop hypothesis "the sim cannot tell corner from centre because its Tesla has
no pull" -- with the pull the landscape is flatter, not steeper. Whatever makes pros choose x=9 (a human
opponent switching lanes / spelling the building / not walking into a riverside turret) is not in the
scripted bots, pull or no pull.

**(b) plausible, untested.** (1) The scripted opponents are the flatness: they push lanes open-loop, so a
Tesla that sits ON the left lane path at the river (corner) engages as much as one covering both lanes.
Measurement: the same probe against a lane-switching or building-spelling opponent -- opponent-model
work, not a probe. (2) Shared-map drag (L56 (b)): the X-Bow cell is pro-correct and the Tesla / Tornado /
Ice Wizard maps sit on the same cell; still untested (per-card map correlation on identical states).
(3) A KL term from the cell head toward P(tile | card) fitted on the 12,220 pro placements would move
placement where the three failed priors (§5ae/§5am/§5ao) did not, BY THIS MECHANISM: those priors
SAMPLED pro tiles in rollouts and left PPO to prefer them, and PPO only moves on reward differences --
which L56/L57 now measure as flat between the pro tile and the locked tile. A KL term is a direct
gradient on the map that does not need the sim to reward the pro tile; on a flat landscape it wins by
default, on a sloped one it competes (annealable). Cost: fit (10 min) + one training arm from c2r_best
(~1-2 days at c2r's rate to m10k), read by place_probe (distinct cells; pro-mass-within-1.5-tiles per
card) at m5k/m10k, gate_prior_probe for side effects. Risk: the cell head at resume is saturated
(raw |81|, RAIL GUARD x0.0556) -- the KL gradient through a tanh-capped head may need the guard's
rescale on every resume, not once. This is the owner's call (multi-day run; changes what the policy
learns vs is told; the owner's 2026-08-31 entry asked for the mechanism to be stated first -- done above).

**What this does NOT establish.** Nothing here says a pro-placed Tesla would win more in the sim (it will
not -- flat); it says the live behaviour the owner objects to is a 2%-of-pros placement that the sim
cannot correct on its own. Per-Tesla damage is an upper bound on a proxy; tower HP saved would be the
real value and is match-level noise at n=24.

**Traps found.** (1) Crawl card keys are hyphenated (`x-bow`, `ice-wizard`, `the-log`, `ice-spirit`);
`x_bow` silently returns nothing. (2) Root `python` has no pandas; use csv + numpy. (3) `sim/engine.py`
class is `SimEngine`, not `Engine`; the L51 driver patches a subclass -- monkeypatch `SimEngine._valid_foe`
to apply `hidden_pull` in a probe. (4) `actions.cell_center` returns frame coordinates (cell 234 -> y 0.479,
enemy side); the sim landing point after `deploy_clamp`/warp is y 0.578 = tile 18.5 -- read landing
tiles from unit records, never from `cell_center`.
