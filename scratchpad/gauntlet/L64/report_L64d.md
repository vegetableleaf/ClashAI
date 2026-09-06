**GAUNTLET loop L64d** — Square One S1, overnight
**Did:** read icebow seed 1; built the harness that lets the NEW model play on the real engine (vs the L62 ghost opponents), 2-match smoke.
**Found (measured):**
- Seed 1: val tile top-1 18.34% / half 16.15% (seed 0: 18.12 / 15.36). On the old init's own 432 grid: 13.28 vs old 13.70 (rows the old model never trained on: 14.29 vs 13.13). Two seeds agree; the band waits on seed 2 (~06:05 UTC).
- Harness `pipeline/engine_play.py`: 2 matches, 1W-1L, 45 of 47 plays accepted, 8.8 plays/min (pool humans on the icebow side: 10.9). Deterministic on re-run. 3 offline tests OK. n=2 says nothing about winrate.
**Traps:** engine refusal code 13 = not enough elixir (the L62 ghost retry only knows 1050 — fix before the 500-match run); one ghost pool entry 3-crowns us by 70 s even if we never play — the big run needs a per-tag "no plays" control so those entries are visible.
**Means:** the S3 grading path (engine winrate vs the old init at n=500) now has its new-model half; the old-init half is the L62 engine PPO env at m0.
**Next:** seed 2 closes the icebow band, then hogeq x3 (~06:45); then the first engine read with the no-plays control.
**Cost:** ~20 min; chain running (task b6vmgii7c). Commit see git log.
