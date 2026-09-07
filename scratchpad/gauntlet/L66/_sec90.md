### §5cs.90 -- L66i (2026-09-07 17:0x-18:0x UTC): **the S3 gate is ANSWERED and the searched teacher FAILS it -- and for the first time the failure is not an artifact of mine. The candidate set contains placements 1.68 tiles from the pro; the rollout objective rejects them and picks ones 13.5 tiles away. The greedy one-shot rollout does not agree with pro doctrine**

**A. The gate, with every known defect fixed (a).** Teacher v3 = 2-D stratified candidates (§5cs.87 fix) + full-lattice refinement (§5cs.88 fix) + random tie-breaking (§5cs.89 fix) + damage-only score + horizon 400. 497/500 states, 84/85 replays, ~75 min on 4 slots.

| | card | exact cell | 1-tile | mean dist |
|---|---|---|---|---|
| student v5lat s0 / s1 / s2 | 64.4 / 60.8 / 63.6 | **21.93 / 23.94 / 21.93** | 30.4 / 32.2 / 31.0 | 3.34 / 3.48 / 3.47 |
| teacher v1 (coarse, §5cs.87) | 100 | 0.00 | 1.01 | 12.475 |
| teacher v2 (refined, §5cs.88) | 100 | 0.00 | 2.01 | 12.562 |
| **teacher v3 (all fixes)** | 100 | **0.00** | 2.01 | **9.478** |

`GATE_cell_ge_student: false` on all three seeds, McNemar p ~1e-33 to ~1e-36 on cell. Card 100% is teacher-forcing by construction and carries no information.

**B. Why this one is not another artifact (a) -- the oracle check.** The obvious objection to every previous run was that the teacher could not *reach* the pro's cell. Measured directly from the per-candidate dump: for each state, the distance from the pro's placement to the **nearest candidate the teacher actually evaluated**.

| | mean | median |
|---|---|---|
| **oracle** (best candidate available to it) | **1.68 tiles** | 1.77 |
| **chosen** (what the score selected) | **13.54 tiles** | 14.84 |

**The near-pro placement was in the candidate set, was evaluated, and was rejected.** Reachability is not the constraint; the objective is. This is the measurement that separates "my search is broken" from "search disagrees with pros", and it lands on the second.

**C. What is and is not established.** Established (a): under a greedy one-shot rollout scored by tower damage dealt minus taken plus enemy units destroyed, over 400 ticks, **the best-scoring placement is systematically not the pro's placement** -- 9.5 tiles away on the full bench, against a student at 3.4. Not established (b): that *search* cannot beat the student. What failed is one specific objective. Three untested candidate causes, in the order I would test them: **no opponent model** (the rollout lets the opponent do nothing, so placements that would be punished look free); **horizon still short relative to an x-bow deck's payoff**, which accrues over tens of seconds of chip damage rather than one exchange; and **greedy single-placement scoring ignores sequencing**, while pro placements are often setup for the next card rather than locally optimal.

**D. A caveat on the oracle number (b).** It comes from the 18-state per-candidate dump taken before the tie-break fix, so the *chosen* column there (13.54) is the pre-fix teacher; the post-fix teacher is 9.478 on the full 497. The **oracle** column is a property of the candidate set, which the tie-break patch does not change, so it transfers -- but strictly the oracle for the v3 run is unmeasured, and a per-candidate dump on the fixed teacher would close that gap cheaply.

**E. Also still true and unchanged.** Exact-cell 0.00% is itself partly reachability-limited: an oracle of 1.68 tiles is far above the criterion's 0.3, so **no teacher with this candidate budget could score well on exact cell**, and the distance comparison is the honest one to read. The pre-registered criterion is not being revised to fit -- it is being reported as failed, with the note that the metric was more demanding than the search resolution ever supported.

**F. The recommendation.** Do not spend more compute widening the candidate set: B shows the objective, not the resolution, is what rejects pro-like placements. The next experiment is the **opponent model** -- re-run a subset with the opponent's real recorded plays continuing through the rollout window instead of an inert opponent, which is available for free from the replay and directly tests the first hypothesis in C. That is a one-shard, ~20-minute run and it should come before any further full-bench pass.
