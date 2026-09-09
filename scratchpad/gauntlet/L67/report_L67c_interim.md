**GAUNTLET loop L67c (interim)** — option A (your ruling: A first, then decide B)

**RETRACTION:** L67b said ~2,070 exact-icebow sides in FirstLight's dataset. That came from one outlier shard (41/5,000). Full count over all 252,238 replays: **766** (0.30%). So v6 = 1,638 + 766 = 2,404 replays = +0.55 doublings, not +1.0. S2 slope now predicts **+0.9 pp** exact cell (20.9 → ~21.8), not +1.5.

**Did:** downloaded all 52 replay parts (sha256 ok 52/52, 825 MB); wrote a HF→crawl2 converter; converted 252,238 replays; drove 2 through the local engine as a test (107/107 + 108/108 plays accepted, crowns match, rotation correct); launched the full 766-replay drive on both local engine slots; chained corpus_v6 → dataset → v6lat ×3 seeds → v3 VAL (clean + degraded) behind it.

**Found (measured):** 766 kept, 0 duplicates of our 1,890-battle crawl, 0 unpositioned; 701 Ranked / 38 friendly / 27 challenge-etc. Drive speed 36-42 s/match with both slots busy.

**Means:** A is still worth finishing (it is the same instrument, one change), but the expected gain halved. Decision on B comes after the v6 numbers.

**Next:** wait ~4 h for the drive, ~4 h for 3 seeds + eval; then §5cs.96 with the v6 vs v5lat 20.93±0.49 comparison and the B decision.
**Cost:** ~1 h wall this loop; drive running (2 python + 2 guest engines); commit 7037cb7.
