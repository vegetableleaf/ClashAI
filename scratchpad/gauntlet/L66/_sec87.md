### §5cs.87 -- L66f (2026-09-07 07:0x-09:0x UTC): **the S3 search teacher is built and runs the full bench (497/500 states, 46 min on 4 VM slots). Its first gate run is INVALID and must not be read as a result: with 24 near-fixed candidates the exact-cell criterion was unreachable by construction, so the 0.0% measures my sampler, not search. Refined re-run in flight**

**A. What was built (a).** `pipeline/s3_teacher.py`. For each benchmark state it re-drives the replay to the branch tick, places a candidate in `libg`, rolls forward `--horizon` ticks, and scores tower damage dealt minus taken plus a 1/8-weight unit-hitpoint term. Three deliberate constraints so the gate stays a test of search: the **card is teacher-forced** to the pro's slot exactly as `s3_bench.predict` reads the student's cell head; candidates are generated **on the model's own 36x64 lattice** and converted to engine coordinates from there (a continuously-placing teacher would beat a quantised student on sub-cell precision alone); and the score uses **no learned value**, which would otherwise import the student's biases into its own examiner.

**B. Student baseline on these 500 states (a), the bar the teacher must clear.** `s1_icebow_v5lat_s{0,1,2}` via `s3_bench predict`:

| seed | card | exact cell | 1-tile | mean dist (tiles) |
|---|---|---|---|---|
| s0 | 64.39 | 21.93 | 30.38 | 3.34 |
| s1 | 60.76 | 23.94 | 32.19 | 3.48 |
| s2 | 63.58 | 21.93 | 30.99 | 3.47 |

**C. Cost, measured (a).** 497 of 500 states produced a target (99.4%; the 3 losses are ability plays or episodes already terminal at the branch tick), 84 of 85 replays, **~22 s/state per slot and ~46 min wall on 4 slots** at 24 candidates and horizon 120. Each candidate is a full re-drive to the branch tick because the engine protocol has no snapshot op, and that is the entire cost.

**D. THE GATE RUN IS INVALID -- do not read its numbers (c).** It reported teacher exact-cell **0.00%** against the student's 21.9-23.9, mean distance **12.475 tiles**, and `GATE_cell_ge_student: false` on all three seeds with McNemar p ~1e-33. None of that is evidence about search, because of a defect in my candidate generation:

- the teacher used **23 distinct cells across all 497 states** -- the coarse 4x6 lattice is nearly state-independent, since the legal-region bounding box barely changes;
- the criterion is agreement within **0.3 tiles** on a 36x64 lattice of 2,304 cells. A fixed 24-cell menu **cannot land within 0.3 tiles of an arbitrary pro placement except by coincidence**, so 0.0% was determined by the design before the engine ran.

**The failure was guaranteed by construction and the run measures my sampler, not the teacher.** Recorded here rather than quietly re-run, because a "search targets disagree with pros" headline drawn from this would have been exactly the kind of confident wrong conclusion this journal exists to catch. It also sits alongside the earlier candidate bug in the same file (a row-major stride collapsing every proposal onto cx=0) -- **twice now, the sampler rather than the search decided the answer.**

**E. A second signal, real but unmeasured (b).** Teacher `py` median **5.5** against pro median **39.0**: the search overwhelmingly chose the back of its own half. That is consistent with the scoring function rewarding *safety* -- a placement far from the action takes no tower damage and scores ~0, which beats a placement that trades unfavourably. Whether that is the scoring function's fault or a genuine property of one-shot greedy placement is **not established** and needs its own test once D is fixed. It is the next thing to look at if the refined run still disagrees with pros.

**F. The fix now running.** `--refine R` adds a stage B: after the coarse pass, re-search every legal cell within +/-R cells of the best coarse cell at full lattice resolution (R=2 gives 24 coarse + up to 24 fine evaluations, roughly 2x cost). This makes the pre-registered criterion **reachable**, which is the precondition for the gate meaning anything. The pre-registered criterion itself is unchanged -- it was fixed before the teacher existed and is not being tuned to the result.
