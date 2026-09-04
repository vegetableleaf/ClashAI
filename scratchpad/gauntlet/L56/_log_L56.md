

## L56 (2026-09-04) -- Tesla-outcome probe: the sim does not reward the corner (nor punish it)
- Ran `L56/tesla_probe.py` on c2r_best (play.py greedy rule, tau 0.25, no search): 4 arms x 24 matches x
  2 seeds, only the Tesla cell forced. Per-Tesla damage (upper bound), pooled: own 954 / corner(234) 1040 /
  lane(274) 690 / centre(314) 1157; per seed corner vs centre 1014 vs 1225 and 1070 vs 1067 (95% CIs +-170,
  overlapping both seeds); lane below both on both seeds (CIs disjoint). Kills/Tesla 1.64/1.75/1.26/1.64.
  Match level all noise (W 14/16/10/10 of 48). (a)
- Scripted bots cross RIGHT 55-64% of the time (8/8 arm-seeds); corner Tesla covers the left bridge only. (a)
- Placement history (place_probe seed 0): gatec2 m5k 14 distinct Tesla cells -> m10k 234 at 23/29, x_bow 234
  9/9; c2r resumed that lineage (cell head saturated raw |81|, RAIL GUARD rescale) and kept it 13/30 -> 27/31
  -> 63%. aggro1 locks 347/233, gate05 327: one cell per card in every arm; skeletons@423 in every checkpoint. (a)
- Verdict: the placement landscape is flat between corner and centre in the sim; 234 is a drift-and-stick of
  a coupled cell head (one `cell_conv` for all cards), not a sim payoff. Exploration alone cannot fix it. (b)
  Hypothesis for why 234 specifically: X-Bow reaches the left princess tower from there (10.4 <= 11.5). (b)
- Retract L55 (b) "the sim rewards the corner"; lane cell 274 is worse, not better. (c)
- Next: read the human Tesla/X-Bow cell distribution from the replay corpus (tools/replay_priors.py) -- how
  far off is 234 from what players do -- then spec a placement-prior arm (one change). Exploration arm parked.
- Box idle throughout (1 python proc = Nucleo). HANDOFF §5cs.26.
