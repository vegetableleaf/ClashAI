**GAUNTLET loop L64g** — engine checkpoint band for icebow; hogeq reaches the engine
**Did:** ran the s1 and s2 icebow checkpoints on the same 100 paired entries; a higher-rate random control (p 0.13); subagent made the ghost-pool builder + engine env deck-agnostic and built the hogeq pool (241 entries from 598 battles); launched hogeq s0 ×100 + its two controls.
**Found (a):**
- 3 checkpoints, threshold gate: **75-25 / 71-29 / 71-29** wins; survival over no-plays +115 / +112 / +112 s (SE ~5.3); crowns against 0.86 / 0.93 / 0.86. Val-tile ordering does not predict engine ordering — the three are indistinguishable on the engine at n=100.
- Random at p 0.13 (15.2 plays/min, 7.7 accepted/min): **3W-97L**, +44 s. Survival per accepted play ~5.7 s random vs ~11.8 s model. The "any plays beat a replay" hypothesis is buried twice.
- hogeq pool: 241 entries, our side won 57% of them (icebow 70%), 228 s mean length. hogeq smoke on the engine worked first try (vocab, slots, parity all fine): 1 loss 1-2, 1 win 3-1; no-plays control 0-3 twice at 70-88 s. Icebow behaviour after the refactor: byte-identical recheck.
**Trap (a):** 38031/38032 are the DIRECT doors to the same two engines as 37031/37032 — two slots, not four; a client on the direct door while the adb door is busy hangs 120 s on reset.
**Means:** S1 icebow is a reproducible engine result across training seeds. Next gain per Square One is S2/S3 (more corpus, search teacher), not the ablation — I'll take that order unless told otherwise.
**Next:** hogeq s0 ×100 vs its no-plays and random controls (running on both slots, ~45 min), then S2 corpus scoping.
**Cost:** ~55 min; both engine slots busy until ~09:45 UTC; GPU idle.
