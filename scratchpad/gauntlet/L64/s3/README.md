# S3 gate harness (L64r) -- built BEFORE the teacher exists

`pipeline/s3_bench.py`. The pre-registered S3 criterion is "searched targets agree with pros >= student
on 500 pro states" (§5cs.53 C). This is the instrument for that sentence.

    build   500 val-replay states, one per replay first then random fill (85 replays here, so no single
            match dominates); carries tag + tick + side so a teacher can RE-DRIVE the engine to the state
    predict runs a checkpoint the same way train_s1.evaluate does -- cell head TEACHER-FORCED on the pro's
            card, checkpoint's own grid offset applied -- so the numbers are comparable to the S1 headline
    score   one file, or a PAIRED McNemar comparison of two

## Measured on the benchmark (icebow v4lat, the current student)

| checkpoint | card | cell | within 1t | mean dist (tiles) |
| --- | --- | --- | --- | --- |
| v4lat s0 | 61.8 | 21.2 | 28.6 | 3.721 |
| v4lat s1 | 60.2 | 21.2 | 30.6 | 3.662 |
| v4lat s2 | -    | 19.4 | -    | -     |

Full-val headline for the same arm was card 62.1 / cell 19.84 / 1t 29.95. The 500-state subsample
reproduces it within ~1.4 pp, which is the sampling error at n=500 -- the instrument is reading the same
thing the S1 evaluation reads.

## The noise floor, and what the gate can actually detect

Two seeds of the SAME arm, paired on the same 500 states:

    s1 vs s0   cell discordant 58, split 29/29, p = 1.00
    s1 vs s2   cell discordant 61, split 35/26, p = 0.31

So **seed churn alone moves ~12% of states** and, correctly, the paired test calls it a null. Minimum
detectable effect at p < 0.05, two-sided, by discordance:

    58 discordant  -> 37/21 split -> 3.2 pp of 500
    100 discordant -> 61/39       -> 4.4 pp
    150 discordant -> 88/62       -> 5.2 pp

**Read this before quoting the gate.** A teacher that beats the student by 2 pp on 500 states has NOT
passed anything -- that is inside seed churn. The gate needs either a >= ~3-5 pp paired win (depending on
how much the teacher and student disagree) or a bigger benchmark. Comparing the two unpaired percentages
side by side, the obvious thing to do, cannot see this at all.
