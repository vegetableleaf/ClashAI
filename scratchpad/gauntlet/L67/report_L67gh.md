**GAUNTLET L67g-h** — live freeze diagnosed + repaired, and the agreement CEILING measured

**Did:** ran down the owner's "it can freeze mid-match" report on his own 4-match log, then measured the gate against pro labels (engine VAL), against real detector frames (unconditioned), and against its own inputs one at a time. Measured the pro-vs-pro agreement ceiling. Measured reranker headroom. Shipped 3 live repairs.

**Found:**
- **RETRACTED (mine, said to the owner in chat):** "the gate ignores elixir". Read off play.py's WAIT lines — but WAIT *is* p<tau, so that sample is truncated at the threshold and conditioned on the outcome. Measured properly, the gate is *calibrated*: engine 0.046→0.472 across elixir 1→10 vs a pro rate of 0.037→0.490; live, unconditioned, 0.109→0.567.
- **Cause of the freeze, and it was my own wiring from last loop (a):** feeding the student the opponent-elixir estimate cuts the live play rate up to 3.2× (frames over tau: 0.278 absent / 0.156 at opp 5 / **0.087 at opp 10**). The estimator ratchets: `est = my_elixir + my_spent − opp_spent` clipped at 10, so every missed enemy play pushes it up permanently.
- **THE CEILING (a):** two pros in near-identical positions agree on the exact cell **27.5%** of the time (40k pro plays, 2,238 replays, 157 players, different-replay AND different-player pairs; plateaus at the closest bins; coincidence floor 5.2%). Student: 21.04 = **76% of ceiling**; within-1-tile 31.87 vs 31.62 (**at** the human rate); card 65.0 vs 43.8 (**better** than a second pro).
- **Reranker headroom (a):** pro's cell in the student's top-3 **44.2%**, top-5 **55.5%**; card top-3 97.6%.
- Owner's unknown-team deck rule was **already live** (TeamTracker veto) and is measured to work: 0 impossible-class detections survive as mine/unknown over 623 frames. Added to the contract path for the offline harnesses.
- Retracted the barrel probe twice (wrong class names → 0 pairs; goblin-centroid association → invalid 12.5 tiles).

**Means:** imitation is nearly exhausted — no corpus reaches a number pros don't reach with each other — but the answer IS in the student's shortlist and its argmax misses it. That licenses search/distillation over *this* model (the old +19.9σ search result was measured on the CNN and is not evidence about the student). Placement gains must come from an objective that evaluates outcomes.

**Next:** verify the freeze repair in a live match (WAIT lines now print `opp~` and `NO-TRAY-MATCH`), then the search adapter: the student runs on a different engine's state contract than the rollout search, so step 1 is student-in-sim, and step 2 the spec's own gate — student→teacher agreement on held-out states BEFORE committing to a full labelling run.

**Cost:** ~3 h wall, CPU only, no training. 3 live repairs, no retrain needed. Running: barrel track probe, pinned-10 label check.
