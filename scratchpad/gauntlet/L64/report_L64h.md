**GAUNTLET loop L64h** — Square One S2 (corpus x3): why half the crawl has no x/y
**Did:** subagent cross-tabbed the x/y-less half of crawl2 against every battle field and read the crawler's marker join; I re-fetched one "uncovered" replay to check the diagnosis, then launched a re-fetch of all uncovered tags with a fixed join.
**Found:**
- (a) x/y is all-or-nothing per replay (icebow 619 full / 612 empty / 6 with exactly one row; hogeq 296 / 295 / 4). NO battle field predicts it: mode 50.4%, win 49.9% vs loss 50.4%, every rating bucket 46-53%, flat over date 2024-2026, hour, crawl wave. Mode and age/expiry explanations: contradicted.
- (a) Cause = crawler join bug. RoyaleAPI markers carry `data-i`; the crawler assumed it was an occurrence index and only ever looked up "0". Fresh fetch of an uncovered tag: 109/109 markers present, ALL `data-i="1"`. The crawler downloaded the positions and threw half of them away. It also kept no raw payloads.
- (a, 2 payloads) `i` is a seat/perspective flag: in i=1 replays the team's plays sit at tile_y median 13.5 (i=0: 18.5). Corpus build must rotate that half by (18-x, 32-y). (b) handedness of the rotation: check per-card x histograms of both halves after the re-fetch.
- (a) Session token still valid, no login needed. Smoke: 3 replays, 287/287 rows with x/y.
**Means:** half of S2's target is already on disk. Expected positioned corpus: icebow 619 -> ~1,237 replays, hogeq 296 -> 595 (2.0x) before any new crawl; +457 more icebow battles listed but never fetched. Then corpus v4 + S1 re-run (same config, 3 seeds/deck) = a clean data-scaling read against 18.22 +/- 0.11 / 20.99 +/- 0.36.
**Also:** L64g's "08:5x UTC" stamps were wrong (commit is 08:04 UTC) — label error only.
**Next:** score the hogeq engine read (thr_s0 ~60/100, no-plays done, random running), then the re-fetch summary + frame check on the i=1 half, then corpus v4.
**Cost:** ~25 min. Running: re-fetch (hogeq now, icebow rerun after — the first icebow attempt died on a 60-s Cloudflare check, connect() hardened), hogeq engine matches on both slots.
