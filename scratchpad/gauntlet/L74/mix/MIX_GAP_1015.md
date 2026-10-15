# Live 12k opponents vs our training opponents (2026-10-15)

Live: 1,919 icebow MAIN-account matches since 10-01 (`live_cost.py`, `live_cost_1001.txt/.json`), overall win 49.5%.
Training: the F1 run's opponent decks `icebow/data/rltest/decks_rl.json` (999 decks, weighted as rl_royale.deck_weights with
the run's alpha/floor). Live % = share of matches in which the card was SEEN (a lower bound on deck membership); train % =
weighted share of training opponent decks containing it.

| card | live % | train % | live win % when seen | cost (matches lost vs an average opponent) |
|---|---|---|---|---|
| megaknight | 16.2 | 1.8 | 37.4 | +37.5 |
| firecracker | 16.8 | 2.5 | 43.3 | +19.9 |
| minipekka | 17.8 | 6.7 | 43.1 | +21.8 |
| hogrider | 14.6 | 6.8 | -- | -- |
| elixirgolem | 8.0 | 1.9 | 40.3 | +14.2 |
| royalrecruits | 4.8 | 1.3 | 37.0 | +11.5 |
| skeletonballoon | 7.9 | 5.2 | 34.4 | +22.8 |
| skeletonarmy | 14.6 | 14.2 | 42.7 | +19.1 |
| barbarians | 6.8 | 5.4 | 35.1 | +18.9 |
| golem | 5.7 | 21.7 | 35.8 | +15.0 |
| angrybarbarians (E-Barbs) | 8.9 | 24.9 | 37.6 | +20.2 |
| lavahound | 1.9 | 9.1 | 33.3 | +5.3 |
| royalgiant | 4.1 | 9.2 | 52.7 | -1.8 |

(a) The training mix is the pro / IL_Replay meta plus the 10-10 owner weighting of Golem / Lava / RG / PEKKA-BS / hyperbait:
it OVER-represents Golem (4x), E-Barbs (3x), Lava (5x), RG (2x) and UNDER-represents the cards that cost the most at 12k:
Mega Knight (9x under), Firecracker (7x), Elixir Golem (4x), Royal Recruits (4x), Mini PEKKA (2.7x), Hog (2x).
Per-card costs overlap (cards co-occur in decks). Beatdown overall: 763/1,919 live matches (40%), win 42.9%.
