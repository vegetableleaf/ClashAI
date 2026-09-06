**GAUNTLET loop L64j** — Square One S2: hogeq engine band under the sampled gate; i=1 half verified on the full set
**Did:** ran all three hogeq S1 checkpoints under `--gate sample` plus a random policy matched to that play volume; full-set fidelity + frame checks on the re-fetched i=1 half; applied and verified the crawler fix; caught a bad drive before it reached corpus v4.
**Found:**
- (a) Sample gate, same 100 paired entries: s0 **85-15**, s1 **79-21**, s2 **84-16** (sd 3.2). Threshold tau 0.5 gave 53 / 19 / 44 (sd 17.6). Accepted plays/match 33 / 27 / 31; the model spends to ~3.4 elixir and 3-crowns often (matches 146-164 s vs 175-190).
- (a) Rate-matched random (p 0.18, 25 plays/match): **15-85**. Same volume, 65-70 fewer wins — the wins are the model's choices, not its activity.
- **Retraction:** L64i's "s1 is the outlier" was the tau rule, not the checkpoint. hogeq's engine instrument is `sample` from here. Whether sample is the right *deploy* rule stays open (it spends to zero against ghosts that cannot punish).
- (a) i=1 hogeq half on the full set: winner agreement 65.3% (145/222) vs v3 67.2%; exact crowns 54.5 vs 56.4 (the n=64 deficit was noise); rotation frame offset 0.008 tiles over 97 cards.
- (b) Two residues: engine ends before the real last play in 52% of rotated matches vs 36.5%; hogeq's two halves differ in real 3-crown rate (17.3% vs 8.1%, z 3.4) while icebow's do not — `i` is not a pure coin flip on hogeq. icebow's half will be the second witness.
- **Trap (a):** the chained i=1 drive ran without `--record-every 20` → replays with no wait frames → corpus v4 would have had 0 new WAIT rows (a hidden play/wait mix change). Build deleted; re-drive with v3's exact flags running (165/274).
**Means:** the hogeq engine read is now usable (band width 6, not 34); the re-fetched half is corpus-grade; S2's first data-scaling point is minutes away from launching itself.
**Next:** the v4 hogeq S1 band on the v3 val rows vs 20.99 ± 0.36 (chained: corpus_v4 → dataset → 3 seeds `--tag v4` → `eval_s1`). Then icebow's re-fetch (283/615, ~12:3x UTC) → drive → corpus_v4/icebow → S1 x3.
**Cost:** ~90 min. Running: icebow re-fetch, hogeq re-drive (37032), chained v4 training. New tooling: `pipeline/eval_s1.py` (one instrument for v3/v4 checkpoints), `train_s1 --tag`, crawler fix in the scraper repo (verified on 5 payloads, not yet used live).
