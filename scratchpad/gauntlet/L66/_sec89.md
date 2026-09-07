### §5cs.89 -- L66h (2026-09-07 13:0x-15:0x UTC): **the back-of-board bias is EXPLAINED and it was a tie-break artifact: ~40% of candidates tie at the maximum and "first wins" resolved every plateau to the lowest cy. Random tie-breaking cuts back-third placements from 7/18 to 2/18 -- but the teacher is still ~9 tiles from the pro against the student's 3.4, so it is a partial fix, not the answer**

**A. The measurement §5cs.88 F asked for (a), `scratchpad/gauntlet/L66/dump_cands.jsonl`, 18 states / 854 candidate evaluations.** Per-candidate scores, not just the winner:

| quantity | value |
|---|---|
| fraction of candidates tied at the maximum | median **0.39**, mean 0.40 |
| states where >50% of candidates tie at the max | 6 / 18 |
| score spread (max - min) within a state | median **213.1** |
| cy of the chosen winner | median **3.0** |
| lowest cy offered in that state | median **3.0** |

**The last two lines are the finding.** The landscape is *not* flat -- a spread of 213 means the score does discriminate -- but there is a large plateau at the top, and `try_cells` kept the FIRST maximum while candidates are generated in ascending cy. So in the median state the winner simply *was* the lowest-cy candidate on offer. **Explanation 2 of §5cs.88 D is confirmed: the 12.5-tile bias was an artifact of tie-break order, not of the objective.**

**B. The fix, and its limits (a).** Random tie-breaking among equal maxima (reservoir sampling, seeded), re-run on the same 18 states at two horizons:

| run | py median | in own back third | mean distance to pro |
|---|---|---|---|
| old, first-wins | 37.5 | 7/18 | 9.88 tiles |
| tie-break, horizon 120 | 32.0 | **2/18** | 9.62 tiles |
| tie-break, horizon 400 | 33.0 | **2/18** | **9.09 tiles** |
| pro | 42.0 | -- | -- |
| *student v5lat, full bench* | -- | -- | *3.34-3.48* |

Back-third placements fall from 39% to 11%, confirming the mechanism. **Distance barely moves: 9.88 -> 9.09 tiles, still ~2.7x the student's.** A longer horizon helps slightly and is kept.

**C. What B does NOT establish (b), and a caution against my own subset.** These 18 states are **not representative of the full bench**: the old run scored py median 37.5 and 7/18 back-third here, against 5.5 and 53% over all 497. The subset happens to be one where the artifact bit least, so **the improvement measured here is a lower bound on the fix and the residual 9-tile gap is an upper bound on nothing** -- 18 states is too few to size either. The full-bench run (tie-break, horizon 400, 4 slots, `nohup setsid` so it outlives the ssh session) is in flight and is the number that counts.

**D. Status (unchanged in substance).** The pre-registered S3 gate is still **not answered**. Two teacher defects are now found and fixed (a degenerate candidate sampler, §5cs.87; positional tie-breaking, here) and one hypothesis is dead (the unit-hp objection, §5cs.88 C). Whether searched targets agree with pros as often as the student does remains open, and **nothing measured so far licenses a claim either way** -- every teacher number to date has been dominated by a defect of mine rather than by search.

**E. A process trap worth keeping (a).** A deploy of `s3_teacher.py` silently did not apply: the remote command was `pkill ...; sleep 2; tar -xf - -C ~/cb && echo DEPLOYED`, and `DEPLOYED` printed while the file was unchanged (`grep -c dump_scores` = 0 remotely, 1 locally). The next run then failed on an unrecognised argument. **An echo that runs regardless of the copy is not a deploy check** -- verify the artifact on the far side, which is now done inline after every deploy. Related: an earlier `timeout 3000` on an ssh wrapper was shorter than the 90-minute job it was waiting on, and killed the wrapper while the remote work continued unattended; long remote runs now use `nohup setsid`.
