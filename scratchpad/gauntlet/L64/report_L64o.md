**GAUNTLET loop L64o** — S2: the scaling result replicates on the second deck
**Did:** finished the icebow arms — v3 under the fixed label convention, then v4 (corpus doubled 493 → 953 replays), 3 seeds each, evaluated on the same 6,133 held-out rows as hogeq's.
**Found:**
- (a) **icebow +1.67 pp per doubling** — 18.17 ± 0.15 → **19.84 ± 0.19** exact-cell. Against **hogeq +1.56 pp** (21.00 → 22.56). Two decks, six arms, eighteen runs, no seed overlap in either headline.
- (a) Every head moves, not just placement: NLL 3.33 vs 3.50, card 62.1 vs 59.2, gate bal-acc 74.5 vs 70.2, value 72.2 vs 69.9.
- (a) Convention-free within-1-tile, both decks: hogeq 26.99 → 28.30 → 30.76 (label fix +1.31, data +2.46); icebow 25.76 → 28.03 → 29.95 (label fix +2.27, data +1.92). Mean miss 4.65 → 4.28 and 4.07 → 3.76 tiles.
- (b) The split between "label fix" and "data" is **deck-dependent** — icebow's floor labels were the more damaged, so it gained more from the fix and had less left for the data. Don't quote either deck's split as a general number.
- (b) Two points per deck is not a curve. Nothing here says the next doubling gives another 1.6 rather than 0.8.
**Means:** S2's premise holds on both decks — more pro replays buy real agreement, and the label fix was worth as much again. The scaling question is now "what shape", not "does it work".
**Next:** corpus_v5 = the 52 never-driven + ~500 replays fetched today → the **third** point, the first that can tell linear from flattening. Then the hogeq roster, which has been stuck at 50 players by our own hard-coded cap.
**Cost:** ~3.5 h of one-at-a-time training. Running: icebow backlog drain 410/504, single account.
