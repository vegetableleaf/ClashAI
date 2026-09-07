### §5cs.88 -- L66g (2026-09-07 09:0x-13:0x UTC): **the sampler defect is FIXED (23 -> 85 distinct cells) and the gate still fails identically -- teacher exact-cell 0.00%, mean distance 12.56 tiles. The cause is a real back-of-board bias, and BOTH of my explanations for it are now contradicted or untested. The S3 gate is NOT answered and no "search disagrees with pros" claim is licensed by any of this**

**A. The refined run (a).** `--refine 2` re-searches the full lattice within +/-2 cells of the best coarse cell. 497/500 states, 84/85 replays, ~40 s/state/slot, ~2 h wall on 4 slots (2x the coarse run, as expected). It **fixed what §5cs.87 D diagnosed**: distinct teacher cells went from 23 across 497 states to **85**. The gate result did not move:

| | card | exact cell | 1-tile | mean dist |
|---|---|---|---|---|
| student v5lat s0 / s1 / s2 | 64.4 / 60.8 / 63.6 | **21.93 / 23.94 / 21.93** | 30.4 / 32.2 / 31.0 | 3.34 / 3.48 / 3.47 |
| teacher, coarse (§5cs.87) | 100.0 | 0.00 | 1.01 | 12.475 |
| **teacher, refined** | 100.0 | **0.00** | 2.01 | **12.562** |

`GATE_cell_ge_student: false` on all three seeds. Card is 100% by construction (teacher-forced) and is not evidence of anything.

**B. What is actually wrong (a).** The teacher places at the back of its own half: **median py 5.5 against the pros' 39.0**, and **264 of 497 (53%) in its own back third** (py < 16). Pro placements sit in a tight band (q1 35, q3 47) that the teacher rarely enters. A 12.5-tile mean distance on an 18x32 board is that bias, not noise.

**C. Explanation 1 -- CONTRADICTED (c).** I attributed it to the scoring function's unit term: `unit_swing` counted our units' *current* hitpoints, so placing a card adds its full hp to our side and placing it out of harm's way preserves that hp, while placing it into a fight spends it. The mechanism is real, so I wrote a v2 score that never counts our own units' hp as a gain -- damage only: enemy tower hp lost, plus enemy unit hp destroyed at 1/8, minus our tower hp lost. **On 68 states scored both ways, v2 median py is 5.5 with 38/68 in the back third, against v1's 28.5 and 32/68 on the same states.** Removing the term did not help and by that measure made it slightly worse. **The hypothesis is wrong.**

**D. Explanation 2 -- UNTESTED, and the data I have cannot decide it (b).** If the 120-tick (6 s) horizon leaves most candidates indistinguishable, the argmax is a tie-break, and `try_cells` keeps the FIRST maximum while coarse candidates are generated in ascending cy -- lowest cy is the back of the board. That would produce exactly this bias for both scoring functions, which fits. What I checked does **not** test it: best-scores vary richly *across states* (65 distinct values in 68, median 189), but the tie-break story is about spread *among candidates within* one state, which the output does not record. **Stating this as the cause would be a guess.**

**E. Status, plainly.** The pre-registered S3 gate is **not answered**. The teacher is not yet a valid instrument: one defect was found and fixed, a second is confirmed to exist and its cause is unknown. **Nothing here supports "searched targets do not agree with pros"** -- that claim would require a teacher whose placements are not dominated by an unexplained positional bias, and this one's are.

**F. The next measurement, specified.** Add a per-candidate score dump (state, cell, score) for ~10 states and read the within-state spread: if a large fraction of candidates tie at the maximum, D is the cause and the fixes are a longer horizon (so placements resolve) plus random tie-breaking; if scores are well separated and the maximum genuinely sits at the back, then the score is measuring something real that disagrees with pro doctrine and the horizon/objective needs rethinking rather than patching. That distinction is one short run and it should come before any further full-bench pass -- each of those is 2 hours.
