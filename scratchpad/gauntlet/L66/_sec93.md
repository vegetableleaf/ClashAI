### §5cs.93 -- L66m (2026-09-07 11:4x-13:1x UTC): **owner delegated the S3 call ("you decide"). Decision: PRO AGREEMENT STAYS and the teacher is what must change. The sequencing hypothesis is then TESTED and DEAD: with the pro's own follow-ups replayed, the pro's cell still ranks a median 24th of 49 candidates (27th without them; paired median difference 0). Spells agree with the objective, troops and buildings do not -- which points at the replayed opponent being an ORACLE future, testable next**

**A. The ruling and the decision (owner, 2026-09-07).** "You decide whether you want to stick with pro agreement or try out another path... I trust your judgement." Decision: **pro agreement stays.** Three reasons, none of them new numbers:

1. It is the only calibrated instrument this project has. Winrate is excluded by guardrail (+/-12 pp at n=16); a learned value function would import the student's own biases into its examiner (§5cs.87 A); the engine's own reward produced no measured gain across four PPO arms and ~1,500 matches (L62l). A rollout objective is a *hypothesis about what good play is*, and §5cs.90 B measured that this hypothesis disagrees with pros by 13.5 tiles while pro-like cells sat in the candidate set. Trusting the objective over the pros would be walking back into the reward-shaping era with a different reward.
2. The failure is localised to the objective, not to search (oracle 1.68 tiles vs chosen 13.54, §5cs.90 B). A gate that the teacher cannot pass is doing its job; moving it would be tuning the criterion to the result, which the pre-registration exists to prevent.
3. The teacher's role in DAgger is to label states the *student* visits. If it cannot reproduce pro doctrine on *pro* states -- the easy case, where the answer is known -- there is no basis for trusting its labels off-distribution, whatever the gate says.

So "another path" means another **teacher**, not another gate. Two candidates were open (§5cs.92): search over action sequences, or a teacher that is not a one-shot rollout at all. Both are rebuilds of days, and nothing measured so far says which. That is what this loop tests.

**B. The test (a).** `s3_teacher.py --opponent both --include-pro`: after the candidate is placed, **both** sides' recorded plays continue at their real ticks through the 400-tick window -- the pro's own follow-ups included -- and the pro's actual cell is added to the candidate set so its score and rank are read directly. Same 12 tags (~70 states), same seed, same 48-cell candidate menu, under `both` and under the existing `replay` (opponent only) as the paired control. This deliberately leaks the pro's continuation into the score; that is the point, not a defect:

- if the pro's cell ranks near the top *given its own follow-ups* but not without them, the objective is consistent with pro doctrine and what the one-shot teacher lacks is the **sequence** -- the rebuild is a teacher whose rollout continues with a policy (the student's), i.e. one-step lookahead under self-play continuation, and pro agreement stays reachable;
- if the pro's cell ranks badly **even with its own follow-ups**, then the pro's actual trajectory scores worse than a hypothetical one under this objective, the tower-damage objective is not what pros optimise over a 20 s window, and no continuation fix rescues it -- the search teacher as designed is dead and S3 needs a different teacher entirely.

Cost: ~1 h on 4 slots (49 candidates x full re-drive per state). Engine services had died with the previous ssh session (the §5cs.47 tree-kill trap, all four ports closed on arrival); restarted under `nohup setsid`.

**C. Caveats registered before the numbers (b).** The pro's follow-ups were placed relative to the pro's x-bow, so under `both` a near-pro candidate inherits synergy a far candidate does not -- this biases the `both` ranking *toward* the pro cell. A "pro ranks well under both" result is therefore the weaker of the two possible findings and licenses only "sequencing matters", not "a policy-continuation teacher will pass the gate". A "pro ranks badly under both" result is not subject to that bias and is the stronger finding. 12 tags is a screen, not a confirmation; the full-bench read follows only if the screen is positive.

**D. Bookkeeping.** The UTC stamps on §5cs.90-92 are inconsistent with the VM clock (this section written at 11:5x UTC, after sections stamped 19:xx UTC the "same day"); those were mislabelled local/UTC, the ordering is right.

**E. RESULT (a), 65 paired states / 12 tags, 49 candidates each incl. the pro's cell, horizon 400, score v2.**

| mode | pro rank, median of 49 | pro in top quartile | pro co-best (gap 0) | pro >500 HP behind best | chosen -> pro, mean / median tiles |
|---|---|---|---|---|---|
| `replay` (opponent's plays only) | 27 | 26.2% | 15/65 | 26/65 | 10.26 / 10.78 |
| **`both` (pro's own follow-ups too)** | **24** | 36.9% | 18/65 | 21/65 | 10.79 / 9.80 |

Paired per state, rank(both) - rank(replay): improved in 26, worse in 20, unchanged in 19, **median difference 0**. Chosen cell identical across modes in only 11/65 -- the objective is sensitive to the continuation, it just does not move toward the pro. The pro's cell, given the pro's own next plays and the opponent's real responses, sits a median 227 HP behind the best candidate (q3: 591).

**This is the strong branch of B.** Supplying the pro's actual sequence does not make the pro's placement score well. The one-shot rollout is not failing for lack of sequence; the tower-damage objective itself ranks the pro's real trajectory below the median random legal cell. Under this objective the search teacher as designed **cannot** be made to agree with pros, and the sequencing rebuild (§5cs.92) is **not** worth building -- (c) by this measurement, to the extent replayed follow-ups stand in for searched ones (caveat C cuts the other way here: the synergy bias should have *helped* the pro cell under `both`, and it still lost).

**F. Per-card breakdown (a, small n -- a screen, not a finding).** Pro's rank under `both` / `replay`:

| card | n | rank both | rank replay | co-best | >500 behind |
|---|---|---|---|---|---|
| skeletons | 13 | 10 | 21 | 6 | 4 |
| ice-wizard | 10 | 35 | 33.5 | 1 | 2 |
| tesla | 10 | 22.5 | 25.5 | 3 | 1 |
| knight | 9 | 33 | 37 | 0 | 6 |
| the-log | 8 | 14.5 | **1** | 4 | 2 |
| tornado | 7 | 7 | 5 | 2 | 2 |
| x-bow | 6 | 26.5 | 33 | 1 | 3 |
| rocket | 2 | 7 | 7 | 1 | 1 |

**Spells agree with the objective; troops and buildings do not.** Also note the back-of-board bias is gone (chosen py median 33.5 vs pro 39) yet the distance is still ~10 tiles -- the teacher now picks cells at the pro's *depth* but elsewhere on the board.

**G. What that pattern suggests, and the test (b).** A spell's effect is immediate and local; a troop or building placement is a hedge against what the opponent does *next*. The rollout replays the opponent's recorded plays -- it has an **oracle future**. Against a known future, the best candidate is the one that exploits the exact timing and lane of the opponent's next card; a pro's hedge is worse in every fixed future and best only in expectation over futures. That would produce exactly F: spells ranked well, troops badly, and no help from the pro's own follow-ups (which do not remove the oracle). It also explains why `replay` did not beat `none` in §5cs.91 -- both are single fixed futures.

Test, cheap and decisive for this hypothesis: score each candidate as the **mean over K jittered opponent futures** (opponent play ticks shifted by U(-J, +J), positions jittered ~1 tile), the **same K futures for every candidate** in a state (common random numbers, so the ranking compares like with like), pro's follow-ups kept exact (`both`). If the pro cell's rank rises materially (median 24 -> top quartile) the objective is fine and the teacher needs an *expectation* over an opponent model -- a rebuild whose shape is then known (sampled continuation, K futures, ~Kx cost). If it does not, the tower-damage objective is not what pros optimise and the engine teacher is closed. K=4, J=60 ticks (3 s), 65 states: ~4x this loop's cost, ~2.5 h on 4 slots.

**H. Not established (b).** Everything in F-G rests on 65 states in 12 replays with 2-13 states per card; a per-card claim needs the full bench. The "oracle future" mechanism is a hypothesis that fits the pattern; G is the measurement that tests it. Nothing here says a stochastic-future teacher would pass the gate -- only whether that is the right thing to build.
