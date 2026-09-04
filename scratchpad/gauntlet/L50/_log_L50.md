- L50 (2026-09-04 14:23-15:3x): THE m30k READ. Snapshot c2r_m30k.pt at 14:56 (log 30050). Sampled-gate probe, same
  instrument as L44/L46: c2r_m30k >=6 share 3.3/5.2/2.3 (seeds 0/1/2) + 3.2/2.5/3.1 (disjoint 3/4/5) = mean 3.3%,
  band 2.3-5.2; reference gatec2_m10k 2.7/3.8/2.4 (mean 3.0, reproduces L46 exactly -- deterministic probe). NOT
  COLLAPSED: no seed <=1%; P(play) 0.16 vs 0.17; play cost 2.7 both. Trajectory m5k 4.0 -> m10k 5.5 -> m20k 1.2 ->
  m30k 3.3: the m20k dip reversed. EVAL@30k ladder 31% / fair 24% (n=150, context only). Decision: no restart, c2r
  runs to 40k (~20:30). Owner Q answered: sandbox engine = measuring instrument, not training env; sim-parity oracle
  step 1 (our sim's crowns-match on the engine's 211 replays) queued next by owner ruling. HANDOFF 5cs.20.
