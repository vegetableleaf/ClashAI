### §5cs.86 -- L66e (2026-09-07 06:3x-07:0x UTC): **VERDICT: anonymous video mining is NOT worth continuing. Best case +0.3 to +0.5 pp for days of work and ~46 h of throttled downloading, with an untested discount on top. Engine slots scale 2.68x at 4 slots (3,400 matches/hour), so S3 is now the cheap path and mining is the expensive one**

**A. The owner's ruling and the question it left.** "I'm not risking my account" -- so the cookie route is closed, and the question is whether *anonymous* mining is worth continuing. This is that verdict.

**B. What mining would return (b, arithmetic on measured inputs).** Hit rate 1/20 = 5.0% [0.9-23.6%] (§5cs.85 E) over 441.6 channel hours, at 170 s of battle per match (§5cs.80 C):

| icebow supply | matches | doublings | gain at 1.50 pp/doubling |
|---|---|---|---|
| point estimate, 22 h | 259-466 | 0.21-0.36 | **+0.32 to +0.54 pp** |
| optimistic bound, 104 h | 1,224-2,202 | 0.80-1.23 | +1.21 to +1.84 pp |

**C. What it would cost (a for the rate, b for the extrapolation).** Anonymous fetching is now rate-limited by bot detection after ~11 videos at 4-way parallelism. Serial fetching may evade it -- **untested** -- but at the measured ~2 min per 180 s slice, classifying all 1,382 videos is **~46 hours of wall clock** before a single frame is mined, then full downloads of the ~70 hits, then the mining pipeline itself (board->tile homography, hand and elixir reading, IDM labelling, the precision/recall gate) which is days of work and entirely unbuilt.

**D. The discount nobody has measured (b).** Every number above assumes a mined replay is worth as much as a sandbox-driven one. It almost certainly is not: the +1.50 pp/doubling slope was fitted on replays with exact unit state, while a mined replay carries detector noise in **both the observation and the label**. The true return is the table in B times an unknown factor <= 1.

**E. VERDICT: stop.** Half a percentage point, conditional on an untested download workaround, an unbuilt pipeline, and an unmeasured quality discount -- against S3, where §5cs.85 just moved compute from 347 local hours per 100k matches to **69 VM-hours (~$27)**, and where the engine produces exact-state data without a rate limiter or a terms-of-service question. Mining is not refuted as an idea; it is simply the worse use of the same nights. The instruments (`deckid.py`, `profile.py`, `sweep.sh`) are committed and calibrated, so if the channel's icebow fraction is ever worth re-testing, the cost is one command, not a rebuild.

**F. Slot scaling, measured (a).** Four slots in one AVD, same 24 tags each, all four returning 17 files:

| slots | per-slot median | aggregate | speedup | efficiency |
|---|---|---|---|---|
| 1 | 2.48 s | 1,267 matches/h | 1.00x | 100% |
| 4 | 3.58-3.67 s | **3,400 matches/h** | **2.68x** | 67% |

Sub-linear, as expected, and the likely reason is that the emulator was launched with `-cores 4` (`worker.py:147-155`) on an 8-vCPU host -- so four slots saturate the guest's four cores. **Untested:** whether relaunching the AVD with `-cores 8` recovers the rest. 3,400 matches/hour is already ~12x the local box, so this is not the bottleneck for anything S3 needs next.
