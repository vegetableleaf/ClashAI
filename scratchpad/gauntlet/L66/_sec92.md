### §5cs.92 -- L66l (2026-09-07 19:0x-19:4x UTC): **the horizon hypothesis is dead too, and it dies informatively: the rollout SATURATES -- horizon 1200 and 2400 choose identically in 18/18 states. All three cheap explanations for the objective's disagreement are now eliminated. What remains is not a bug but a question about the target**

**A. The sweep (a).** Same 18 states, same candidates, opponent inert, damage-only score; horizon the only variable.

| horizon (ticks / seconds) | mean dist to pro | median | py median | within 1 tile |
|---|---|---|---|---|
| 400 / 20 s | 9.09 | 6.31 | 33.0 | 0/18 |
| 1200 / 60 s | **8.35** | 6.19 | 37.5 | 0/18 |
| 2400 / 120 s | **8.35** | 6.19 | 37.5 | 0/18 |

Identical choice: h400 vs h1200 in 7/18, h400 vs h2400 in 7/18, **h1200 vs h2400 in 18/18**.

**B. What the saturation means (a).** Beyond ~60 s of rollout the teacher's decision does not change at all -- not in one state out of eighteen. Either the episode has ended or the board has resolved, so extra lookahead adds no information. **The objective is therefore not short-sighted.** Lengthening the horizon buys 0.74 tiles (9.09 -> 8.35) and then buys nothing, against a gap to the student of ~5 tiles. This also retires the "an x-bow deck's payoff accrues over tens of seconds" reasoning: 120 seconds is most of a match, and it changes nothing.

**C. Three hypotheses, three nulls (a).** Every cheap explanation for why the searched objective disagrees with pro placement is now tested and eliminated:

| hypothesis | test | result |
|---|---|---|
| the unit term rewards hiding (§5cs.88 C) | v2 damage-only score | **contradicted** -- slightly worse |
| an inert opponent makes bad placements look free (§5cs.90 C) | opponent's real plays replayed | **not supported** -- 9.48 vs 9.09, closer in 3/18 |
| the horizon is too short for this deck (§5cs.91 D) | 400 / 1200 / 2400 | **dead** -- saturates at 1200, 18/18 identical |

Together with §5cs.90's oracle check (the near-pro candidate is evaluated and rejected, 1.68 tiles available vs 13.5 chosen), the finding is now well localised: **a greedy single-placement rollout scored on engine damage does not select pro placements, and this is not caused by resolution, reachability, tie-breaking, the unit term, the opponent, or the horizon.**

**D. What is left, and it is not a bug (b).** Two possibilities remain and they are different in kind. (1) **Sequencing**: pro placements are frequently setup for the next card rather than locally optimal, and no single-placement objective can represent that -- testing it means changing what the teacher is (search over short action *sequences*), which is a real build, not a flag. (2) **The target itself may be wrong**: §5cs.53's gate assumed that placements which win engine exchanges are the placements pros make. Three nulls and an oracle check are consistent with those simply being different objectives -- pros play for elixir economy, cycle advantage, tower-race position and opponent modelling that an engine damage counter does not score. **If (2) is true, then a search teacher that agreed with pros would be the surprising result, and pro agreement is the wrong gate for S3 rather than the teacher being broken.**

**E. Recommendation, for the owner.** Do not spend more nights patching the objective: the cheap space is exhausted and each remaining option is either a rebuild (1) or a change of plan (2). The question posted is which. My own reading is that (2) deserves serious weight -- the student reaches 21.9-23.9% pro agreement from supervised imitation alone, while search reaches 0% while demonstrably being *able* to propose the pro's cell, and the most economical explanation of that pattern is that the two objectives do not coincide.

**F. Housekeeping (a).** The VM is idle with nothing in flight, billing ~$0.39/h (~$9/day). I cannot restart it once stopped (no gcloud locally), so it is left running pending the owner's call rather than shut down unilaterally.
