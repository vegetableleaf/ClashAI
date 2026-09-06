**GAUNTLET loop L64i** — Square One S2: hogeq engine read + first fidelity test of the rotated i=1 half
**Did:** ran the three hogeq S1 checkpoints, a no-plays control and a rate-matched random control on 100 paired ghost entries; diffed the per-decision logs; drove the first 80 re-fetched hogeq replays (rotated 180°) through the engine and checked lane handedness.
**Found:**
- (a) hogeq, threshold tau 0.5: s0 **53-47**, s1 **19-1-80**, s2 **44-56**; random p 0.13 **18-82**; no-plays **0-100**. Crowns against 1.40 / 2.06 / 1.46 (no-plays 2.87). Not a closed band like icebow's 75/71/71.
- (a) The outlier plays **17.4** accepted cards/match vs 26.8 / 24.9 with the SAME p_gate median (0.361 vs 0.352/0.356). p90 is 0.48-0.49 for all three — under tau. Fraction of decisions above tau 0.059 vs 0.083/0.077; hog plays 174 vs 293/253, earthquake 52 vs 179/120; elixir at decision 8.73 vs 8.0 (banks at the cap). Same mechanism as L62j: a few hundredths of calibration moves the play rate by a third.
- (b) If tau is the cause, the same checkpoint under `--gate sample` lands near s0/s2 — `smp_ck1` running (12/100).
- (a) Rotated i=1 half, first 64 ok hogeq rows: engine-vs-real winner agreement **64.1%** vs corpus_v3 **67.2%**; accept 97.6% vs 98.7%. Blue tesla left-fraction 0.224 vs 0.279 in the old half — a mirror would give 0.776, so the 180° rotation is the right transform.
- (b) exact-crowns 43.8% vs 56.4% and terminal-vs-last-play median −101 vs +120 on n=64 — re-read on the full set before calling it.
**Means:** icebow's engine instrument is fine; hogeq's is tau-fragile (trap recorded). The re-fetched half looks usable for corpus v4 on the one deck tested so far.
**Next:** score smp_ck1; relaunch the icebow re-fetch when hogeq's finishes (260/299); then corpus v4 + S1 re-run (3 seeds/deck, one change = corpus).
**Cost:** ~70 min. Running: smp_ck1 (37031, ~25 min), hogeq re-fetch, chained hogeq i=1 drive (37032).
