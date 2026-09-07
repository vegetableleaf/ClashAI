### §5cs.83 -- L66b (2026-09-07 04:0x-04:4x UTC): **the deck identifier is CALIBRATED and found its first true positive -- `NYAWcJcGU3E` scores 0.730, above all three known-icebow controls, with all eight cards at 0.73-0.83. Threshold 0.60 separates two populations with a 0.06 gap. Hit rate 1/9, whose 95% band (2-43%) brackets the answer, so a 100-video sweep is running**

**A. Separation, at the slice length §5cs.82 E established (a), `profile180*.json`.**

| population | file | worst_icebow (min over the 8 cards of that card's max score) |
|---|---|---|
| known icebow | ctrl_hunter1_180s | 0.625 |
| known icebow | ctrl_hunter2_180s | 0.670 |
| known icebow | ctrl_hunter3_180s | 0.687 |
| **discovered icebow** | **NYAWcJcGU3E** | **0.730** |
| other decks (8 channel videos) | -- | 0.500, 0.509, 0.517, 0.530, 0.534, 0.548, 0.565, 0.500 |

Threshold **0.60**: min positive 0.625, max negative 0.565, gap 0.060. `NYAWcJcGU3E`'s per-card profile is unambiguous -- tornado 0.730, tesla 0.759, ice_wizard 0.766, x_bow 0.778, rocket 0.804, knight 0.752, the_log 0.829, skeletons 0.765 -- eight cards, none weak. Against it the strongest non-icebow card reaches 0.779, so even its *worst* deck member is within 0.05 of the best false match; the discriminator is that all eight clear 0.73 at once, which no other deck's profile does.

**B. It confirms the retraction rather than softening it (c -> a).** `NYAWcJcGU3E` is the exact video whose hand strip I flagged by eye (tornado, rocket, greyed x-bow) and which the discarded 20-second pilot scored 0.545 and called negative. Same video, same instrument, longer slice: **0.545 -> 0.730**. The pilot did not merely lack power; it inverted a positive. Had the sweep been built on it, the channel would have been written off as having no icebow at all.

**C. The number that decides the plan is still uncertain (a, and honestly so).** Hit rate **1 of 9 = 11.1%**, Wilson 95% CI **2.0% - 43.5%**. Against 441.6 channel hours that is **49 h of icebow footage, band 9-192 h** -- and one corpus doubling needs 78-139 h (§5cs.80 C). **The point estimate is SHORT of a doubling and the band straddles it**, so the honest statement is that nine videos cannot answer this. Sampling 100 tightens the rate to about +/-6 pp, which is enough to separate "not worth it" from "one doubling" -- that sweep is running (`sweep.sh`, 4-way parallel, ~21 MB per video).

**D. Cost model, now measured not estimated (a).** 180 s at <=720p averages **21 MB** and about 2 min of wall clock per video serially, 4-way parallel in the sweep; profiling is ~26 s per video single-core. Stage 1 over all 1,382 videos is therefore ~29 GB and, at 4-way parallelism, roughly 12 hours -- or about 3 hours at 16-way. Stage 2 (full download of the hits only) is ~1.4 GB per hit-hour.

**E. Unchanged and still the largest unknown (b).** Everything above is about how much icebow footage EXISTS. What a mined replay is worth relative to a sandbox-driven one is still unmeasured, and the +1.50 pp/doubling slope was fitted entirely on engine-driven data with exact unit state. A mined corpus carries detector noise in both the observation and the label. **Nothing here licenses assuming they are interchangeable**, and the cheapest way to find out is to mine one hit-video and compare a model trained with it against one trained without.
