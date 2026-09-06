### §5cs.64 -- L64e (2026-09-06 06:0x-06:2x UTC): **icebow S1 3-seed band CLOSED -- val tile top-1 18.22 +/- 0.11 (18.12 / 18.34 / 18.20), half-tile 15.99 +/- 0.57, card 59.26 +/- 0.20; on the old init's own 432 grid the old model is ahead of ALL THREE seeds on all val rows (13.70 vs 12.54-13.28) and BEHIND all three on the 2,072 rows it never trained on (13.13 vs 13.61-14.29); no-plays control built into the engine harness (`--gate none`) and the L64d "pathological entry" hypothesis is CONTRADICTED: a passive icebow loses 0-3 to BOTH smoke entries by 61-70 s.**

**A. icebow band (a), `L64/s1/final_icebow_s{0,1,2}.json`, best-epoch val on 13,761 rows / 3,796 plays, board-blind baseline tile 8.90 / half 8.48 / card 48.05.**
| seed | best ep | tile | half | card | joint | gate bal-acc | wait | value | emb cos |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 14 | 18.12 | 15.36 | 59.17 | 10.62 | 0.715 | 47.5 | 69.2 | 0.201 |
| 1 | 14 | 18.34 | 16.15 | 59.51 | 10.75 | 0.671 | 47.3 | 70.7 | 0.205 |
| 2 | 20 | 18.20 | 16.49 | 59.11 | 10.17 | 0.705 | 47.6 | 69.6 | 0.178 |
| mean | | **18.22** | **15.99** | **59.26** | 10.51 | 0.697 | 47.5 | 69.8 | 0.195 |
Seed-to-seed range: tile 0.22 pt, half 1.13 pt, card 0.40 pt, gate bal-acc 4.4 pt. Tile top-1 is a stable instrument at this n (2.05x baseline, every seed); half-tile is the noisier one. Seed 2's best epoch was the LAST one (20) -- the schedule may be short for some seeds; (b) untested whether 30 epochs adds anything, one seed x 30 would say.

**B. Matched grid, all three seeds (a), `L64/matched_grid.py`, `matched_grid_s2.json`; same 3,796 plays, old init = `bc_bias_native_s0.pt` per §5cs.62-B.**
| instrument | s0 | s1 | s2 | mean | old init |
|---|---|---|---|---|---|
| 1-tile bins, all rows | 17.31 | 17.89 | 18.18 | 17.79 | 6.69 |
| old's 432 grid, all rows | 12.54 | 13.28 | 13.07 | 12.96 | **13.70** |
| old's 432 grid, clean 2,072 rows | 13.61 | 14.29 | 14.14 | **14.01** | 13.13 |
| miss distance mean (tiles) | 4.07 | 4.08 | 4.06 | 4.07 | 5.28 |
| within 2 tiles | 44.2 | 44.3 | 44.7 | 44.4 | 31.4 |
Reading: on the old model's home grid over ALL val rows the old model beats every seed (by 0.4-1.2 pt; seed band 0.74 pt) -- but 1,724 of those rows come from 37 replays that were in ITS train split (§5cs.62-B), and on the 2,072 rows neither model trained on every seed beats it (by 0.5-1.2 pt). The fair comparison is the clean one: **on equal coarseness the S1 model is slightly ahead, not level, and the margin is about one seed-band wide** -- a real but small edge, plus a large edge on how far misses land (4.07 vs 5.28 tiles, within-2-tiles 44 vs 31%). Not established: whether the 1-pt clean margin survives a different val split (the 85-replay val is fixed by crc32 tag hash); a second split would need retraining.

**C. No-plays control (a), `pipeline/engine_play.py --gate none`, `L64/engine_play_none/`.** The model still runs (p_gate logged) but never acts; ghosts, clock and outcome are the engine's. Run on the two L64d smoke entries, seed 0, port 37031: `099P9CL8L2QJ` (the entry the model BEAT 2-1 at 240.9 s) -- passive loss 0-3 at **61.0 s**; `02GY9R09LU8J` -- passive loss 0-3 at **70.2 s** (with plays: 0-3 at 78.1 s). Tower trace (`_probe_towers.py`, level 11, princess 3,052 / king 4,824 HP): 099's left princess loses 2,109 HP between 24.5 and 34.5 s to the undefended royal-ghost + e-wiz push (~210 DPS, consistent with card stats), king dies 54.5-61 s; 02G's pekka push takes the right princess in <10 s (44.5-54.5) and the king in ~16 s. **So §5cs.63 trap (2) is withdrawn:** 02G is not a pathological entry -- ANY undefended entry ends a match in about a minute in this engine, and the harness's m1 loss means the model's 7 accepted plays bought 8 s over doing nothing against that push. This is exactly what the control instrument is for: per tag, `seconds survived - no-plays seconds` and `crowns vs no-plays crowns` are the readings, not raw winrate. Threshold smoke re-run after the fix below: byte-identical to L64d (WIN 2-1 240.9 s / LOSS 0-3 78.1 s, 45/47 accepted, ghosts 27/27, 0 refused).
Also applied: `L62/engine_env.py` ghost retry now keys on result_code 13 as well as 1050 (RESULT_CODE_NAMES gained 13). No ghost in either smoke match had hit the 13 path, so the fix is inert on these two and matters only for the long run.

**D. Box.** hogeq seeds 0-2 running (task b6vmgii7c, hogeq s0 at epoch 1/20 at 06:2x UTC; ~13 min per hogeq seed -> ALL_SEEDS_DONE ~07:00 UTC). Engine idle; the CPU-only control runs above took 7 s per match beside the trainer.

**E. Next.** hogeq band at ~07:00 (vs baseline 11.45/11.45/42.32; no old-model comparison exists for hogeq). Then the first engine read on the S1 checkpoints: N pool entries x {no-plays, threshold tau 0.5, sample} x 3 seeds, scored as survival/crown deltas vs the per-tag control; N sized by the ~16 s wall per match.
