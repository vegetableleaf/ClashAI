

## L57 (2026-09-04) -- pro placements vs the locked cells; hidden_pull does not un-flatten the sim
- Pro corpus (12,220 blue plays, §5ag): X-Bow modal (15,19)/(2,19) = 48% lane bows; the policy's corner
  X-Bow tile (1.5,18.5) has 24% of pro bows within 1.5 tiles (50% lane-mirrored) -> the X-Bow cell is
  pro-correct to ~1 tile. Tesla: pros x=9 centre 48%, x 6-11 81%, y 18-22; policy tile = 2.0% of pro
  Teslas. Skeletons 4.9%, Knight 2.2%. (a)
- L56 probe rerun with the L52 `hidden_pull` mechanic: pooled dmg/Tesla own 1033 / corner 935 / lane 966 /
  centre 1029, all CIs overlap; lane rises 690 -> 966, corner = centre unchanged. (a) Missing pull is not
  why the sim is flat. (c)
- Decision to owner (STOP): fitted pro placement prior as a KL term on the cell head from c2r_best (mechanism
  stated: direct gradient, no reward difference needed -- unlike the 3 failed rollout-sampling priors), or
  opponent-model work, or neither. HANDOFF §5cs.27. Box idle.
