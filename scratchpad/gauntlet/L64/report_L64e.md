**GAUNTLET loop L64e** — Square One S1: icebow band closed; engine harness gets its control
**Did:** icebow seed 2 finished; matched-grid read on all 3 seeds; built `--gate none` (no-plays control) into `pipeline/engine_play.py`, ran it on the two L64d smoke entries, traced tower HP; engine_env ghost retry now also keys on refuse code 13.
**Found (a):**
- icebow 3 seeds: val tile top-1 18.12 / 18.34 / 18.20 = **18.22 ± 0.11** (baseline 8.90, old init on 1-tile bins 6.69); half-tile 15.99 ± 0.57; card 59.26 ± 0.20; gate bal-acc 0.70. Seed 2 peaked at the last epoch (20).
- Old init on ITS 432 grid: ahead of all 3 seeds on all val rows (13.70 vs 12.54-13.28) — but 37/85 val replays were in its train split. On the 2,072 clean rows all 3 seeds are ahead (13.61-14.29 vs 13.13). Miss distance 4.07 vs 5.28 tiles, every seed. Fair read: slightly ahead on equal coarseness, clearly ahead on how far misses land.
- No-plays control: a passive icebow loses 0-3 at **61 s** to 099P9CL8L2QJ (the entry the model BEAT 2-1 at 241 s) and at 70 s to 02GY9R09LU8J (with plays: 78 s). Tower trace is consistent with card DPS (undefended ghost+e-wiz kills a princess in ~14 s).
**Retracted:** L64d trap (2) "02GY9R09LU8J is a pathological entry" — any undefended entry ends the match in about a minute. The harness's m1 loss = the model bought 8 s over doing nothing against a pekka push.
**Means:** the engine read must be per-tag deltas (seconds survived, crowns) vs the no-plays control, never raw winrate. S1 icebow is a real init: 2x the board-blind baseline on every seed, ~1 pt over the old model where the comparison is clean.
**Next:** hogeq 3-seed band (~07:00 UTC, task b6vmgii7c; s0 at epoch 1 now), then the first engine read: N entries × {none, threshold, sample} × 3 seeds as control deltas.
**Cost:** ~25 min; hogeq s0-2 training on GPU; engine idle. Commit follows.
