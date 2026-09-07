### §5cs.91 -- L66j (2026-09-07 18:0x-18:4x UTC): **the opponent-model hypothesis is NOT SUPPORTED. Giving the rollout the opponent's real recorded plays made pro agreement slightly worse (9.48 vs 9.09 tiles), closer in only 3 of 18 states. §5cs.90 C's leading explanation is dead; the horizon and greedy-sequencing hypotheses remain**

**A. The test (a).** `--opponent replay` applies the OTHER side's recorded plays at their real ticks during the rollout window; `--opponent none` is the inert opponent every earlier run used. Only the opponent's plays are replayed -- replaying our own future plays would leak the pro's continuation into a score meant to judge a single placement. Same shard (18 states), same candidates, same horizon 400, same damage-only score: the opponent model is the only variable.

| arm | mean dist to pro | median | py median |
|---|---|---|---|
| opponent = none (inert) | **9.09 tiles** | 6.31 | 33.0 |
| opponent = replay (real plays) | **9.48 tiles** | 8.67 | 26.5 |
| pro | -- | -- | 42.0 |

Identical choice in 7/18 states; `replay` closer than `none` in **3/18**. **No improvement, and the sign is wrong.**

**B. What this kills and what it does not (a for the null, b for the scope).** §5cs.90 C named "no opponent model" as the leading explanation for the teacher's disagreement, on the reasoning that an inert opponent makes punishable placements look free. **That is not what is happening.** At n=18 a small effect cannot be excluded -- the difference is well inside what 18 paired states can resolve -- but there is no large one, so it is not the reason the teacher sits 9.5 tiles from the pro while the student sits at 3.4.

**C. The limitation this test could never escape (b).** The opponent's recorded plays were a response to the PRO's placement, not to our candidate. So `replay` is "the opponent does what they actually did", not a reactive opponent. A genuinely reactive opponent (a policy responding to our candidate) is a much larger build and is NOT justified by this result -- the null here is evidence against opponent modelling being the bottleneck at all, so building a reactive one to chase it would be spending days on a hypothesis that just failed its cheap version.

**D. What remains, in the order worth testing.** (1) **Horizon**: an x-bow deck's payoff is chip damage accrued over tens of seconds; 400 ticks (20 s) may still be far too short for the objective to see what a pro placement is for. This is a one-flag sweep (400 / 1200 / 2400) on one shard. (2) **Greedy single placement ignores sequencing**: pro placements are often setup for the next card, and no single-placement objective can value that -- this one is not cheap to test and would change what the teacher is. (3) The possibility that **pro agreement is simply the wrong target for a search teacher** -- pros optimise a game the engine's damage counter does not measure, and §5cs.53's gate assumed otherwise. That is a question about the plan, not the code, and it belongs to the owner.

**E. Standing status.** S3 gate: answered and failed (§5cs.90). Cause: the objective, established by the oracle check. Leading explanation for the objective's disagreement: **eliminated**. The teacher, the gate harness, the VM and the 4-slot pipeline are all built and working -- what is missing is a scoring rule that agrees with pro doctrine, and there is no longer a cheap hypothesis on the table for what it should be.
