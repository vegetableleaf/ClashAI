**GAUNTLET loop L64c** — Square One S1, overnight
**RETRACTION (§5cs.48, L62i grid ruling).** My probe measured the LIVE tap-screen ActionSpace and read screen-fractions as board tiles — a unit error. On the grid the trainer actually uses, **432 = 1.333 tiles per row — you were right**, and **576 has ZERO snap error** on all 2,657 pro x-bow placements (pros place on the x.5 lattice, which the 18x32 centres hit exactly). My "576 would push 55% out of reach" claim is withdrawn. What still stands: at 432 the worst backward snap is 0.5 tiles and 0 of 242 in-reach x-bows are pushed out of reach at either grid, so the "one tile back, out of reach" mechanism is still not what happened; the short x-bows you saw on the collapsed KL arm are policy error (untested). Moot for the new model (half-tile head).
**Did:** re-scored the old imitation init on the SAME 3,796 val plays the new model is graded on; read S1 seed 0.
**Found (measured):**
- Old init, its own 432 grid, same plays: 13.70 / 41.73 top-1/top-5 (its 15.00 on its own val reproduced exactly). 37 of the 85 val replays were in its train split; on the 2,072 clean rows: 13.13 / 41.51. At 1-tile bins: 6.69%.
- S1 icebow seed 0 (ONE seed = a screen): val tile top-1 **18.1%** / half-tile 15.4% (board-blind 8.9 / 8.5), card 59.2% (48.1), gate balanced acc 0.715 (the leaked 0.98 is gone), value 69%, emb cosine 0.20 (old trunk 0.991 — no collapse).
- Matched grids, same plays: 1-tile new 17.3 vs old 6.7; on the old model's own 432 grid new 12.5 vs old 13.7 (clean rows 13.6 vs 13.1); miss distance mean 4.07 vs 5.28 tiles, within 2 tiles 44% vs 31%.
**Means:** the honest comparison is "level with the old init on its coarse grid, better on fine placement and on how far misses land" — not "2x better". Whether it beats the old init at all waits on the 3-seed band.
**Also:** Monitor events re-invoke the loop too (fired 05:16 on schedule) — second overnight trigger confirmed.
**Next:** seeds 1-2 icebow (~06:10 UTC) then hogeq x3 (~06:45): 3-seed mean ± band per deck on both instruments.
**Cost:** ~25 min; chain running (task b6vmgii7c). Commit e3bc18b.
