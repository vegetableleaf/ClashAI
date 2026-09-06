**GAUNTLET loop L64n** — S2 corpus growth: how fast can the crawl actually go?
**Did:** measured where the fetch time goes; fixed the backoff; ran an A/B/A experiment on the owner's three throwaway accounts; widened the crawl roster; retracted a number I'd carried forward.
**Found:**
- (a) **RETRACTION.** §5cs.72's "+457 unfetched icebow battles" is wrong — counted directly: **16** never fetched, **52** usable-but-never-driven, 226 driven-and-failed. The i=1 backfill is exhausted. I carried that number from a session summary without checking it.
- (a) **The bottleneck was ours.** The fetch loop slept a flat 120 s on every 429 *and* dropped the tag — 63%/63%/62% of three earlier runs' wall clock. Re-queueing after 15 s (the transport already has a working AIMD limiter underneath): **3.44 → 6.36 replays/min, 1.8×, free.**
- (a) **The 429 is per-IP, not per-account.** A/B/A, same code, same box, 60 replays per shard: 1 account 5.87 then 6.85/min; 3 accounts **7.81 combined = 1.23×**, each shard only 2.58-2.88/min, and 3.01 429s per replay vs 1.00. Per-account budgets would have shown ~3×. Drift ruled out — the after-run beat the before-run.
- (a) Roster widened 150 → **228** players only; the ratings boards had no more. Discovery: 1,253 → **2,076 battles**; fetched 1,253 → **1,572** (+319 real replays, 236 of them from the experiment itself).
**Means:** more accounts are not the lever, and I've said no to the rotating-IP idea — that's circumvention infrastructure, and (a) it'd likely be slower since cf_clearance is IP-pinned. Fetch speed isn't the real cap anyway: **the discovery source is.** 228 players is the ceiling of the ratings boards.
**Next:** icebow v4-lattice band lands ~17:1x — the loop's actual result. Then drive the 52 + 319 new replays into corpus_v5 for the third scaling point.
**Cost:** ~80 min, all of it network-bound. Running: icebow v4-lattice seed 2 of 3.
