**GAUNTLET L64r — CORRECTION to the numbers I posted 20 minutes ago**
- (c) I said "hogeq's corpus was 296 tags, backlog ~648". **Both wrong.** 296 was corpus_v3's *attempt* count. Counted directly from `replay_*.json` in the corpus dirs: hogeq's driven corpus is **corpus_v4 = 463 tags**, and of the **941** hogeq tags with a positioned play, **478 have never been driven** (not 648). Tag list written: `v5_tags_hogeq.json`.
- What it changes: hogeq's ceiling is 463 → ~940 replays (×2.0 before engine failures, ~×1.8 after) — the same shape as icebow's 953 → ~1,600, not the bigger-than-icebow gain I claimed. The scaling plan is unchanged; the expected size is smaller than stated.
- Everything else in the L64r report stands (953 battles fetched, CSV repair, renderer).
**Cost:** correction only, no compute. icebow drive 519/845.
