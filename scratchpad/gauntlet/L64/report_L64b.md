**GAUNTLET loop L64b** — Square One S1 (imitation v3), overnight
**Did:** Found and fixed a label leak in the S1 dataset, threw away the first training run, rebuilt both datasets, relaunched 3 seeds x 2 decks.
**Found (measured):**
- Leak: gate balanced accuracy 0.98 from epoch 1 — not skill. "Play" rows were built from full play frames (entities with a `kind` column → deploying flag, plus spell effects); "wait" rows from compact frames that have neither. The model could read "is this a play row" straight off the token columns.
- After the fix, token columns 8-13 average 0.000 for both row types in both decks. What still differs is real: units/row 5.18 vs 4.00, my elixir 0.70 vs 0.49 (pros play when they have elixir).
- Rebuilt datasets: identical row counts (icebow 21,687 play / 56,590 wait; hogeq 9,797 / 23,421). 24 tests OK. Board-blind baselines identical to L64a: icebow tile 8.90%, hogeq 11.45%.
- Leaked run (8 epochs) is kept ONLY as a diagnostic: tile 16.8% best. Not an S1 number.
**Trap:** `TaskStop` on the seed chain killed only the wrapper shell; the script and its trainer kept going and started seed 1. Killed the tree by PID, verified 0 trainers, then relaunched.
**Cost of the fix (untested):** S1 rows now never show a spell in flight or a deploying flag, which the live path does provide. Restoring needs re-driving both corpora with effects recorded every tick (~2.5 h engine). Parked in §6.
**Means:** nothing about S1 quality yet; the first honest numbers land ~06:50 UTC.
**Next:** read the 3 icebow finals (mean ± spread vs 8.90%), check gate bal-acc is well under 0.98 with the leak gone (if not, another leak), then re-score the old trunk on these val rows so old 15.44% and new numbers are on one instrument.
**Cost:** ~15 min; training chain running (task b6vmgii7c, ETA ~1 h 45). Commit 58f1b82.
