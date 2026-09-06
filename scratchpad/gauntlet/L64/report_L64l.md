**GAUNTLET loop L64l** — Square One S2: first clean data-scaling point (hogeq)
**Did:** finished the chained bands on hogeq, all on the same 6,133 v3 val rows, 3 seeds each: naive v4 (floor, the record of the trap), v3 under `--grid lattice` (new baseline), v4 under lattice. Added a convention-free placement instrument (checkpoint's own inverse of its argmax vs the pro point: within 1 tile, mean miss in tiles).
**Found:**
- (a) v3 lattice: 20.91/21.02/21.08 (21.00 ± 0.09), NLL 3.61. v4 lattice: 22.84/21.90/22.95 (22.56 ± 0.58), NLL 3.41. **+1.56 pp for 1.9× replays**, no seed overlap. Card 57.8 vs 55.0, gate 66.6 vs 61.1, value 57.9 vs 55.1.
- (a) Convention-free within-1-tile: v3 floor 26.99 → v3 lattice 28.30 → v4 lattice 30.76; mean miss 4.65 → 4.59 → 4.28 tiles. Convention +1.3 pp, data +2.5 pp, and they add.
- (a) Naive v4 (record): floor tile 23.10 ± 0.32 but exact-cell 13.36 / NLL 4.2 — the trap, not a scaling number. Trap: a lattice checkpoint's "tile" = its "half"; never in a column with floor tile numbers.
- (b) Whether +1.5 pp/doubling holds to ×10 is untested — three points are not a curve.
**Means:** S2 is doing what it was bought for: more pro data moves every head, and the label fix was worth almost as much as the data. Corpus growth continues.
**Next:** score `s1_hogeq_v4lat_s0` on the sample-gate engine instrument (27/100, same 100 entries as 85/79/84 — one seed, a screen), then the icebow side (i=1 fidelity/handedness → corpus_v4/icebow → lattice bands vs floor 18.22 ± 0.11).
**Cost:** ~1h45 of one-at-a-time training. Running: engine read (ETA ~15:10 UTC), icebow i=1 drive 407/560.
