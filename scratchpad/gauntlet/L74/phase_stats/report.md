# X-Bow phase measurement

Offline run: 2026-10-12T15:19:53.828543+00:00. Since 20261008. All rates below have 95% CIs in brackets; total is the numerator and n is the number of independent matches/replay clusters unless stated. Big losses overlap losses. Human exposure sums player-sides; CIs cluster both sides by replay.

## Corrected human X-Bow placement

Bot vs icebow-like humans — placement audit below uses all observed human X-Bow sides to reconcile the original bug. Human orientation evidence: data-i is constant across both teams in each HTML replay. Index 1 puts team at raw y<16, index 0 puts team at raw y>16; opponent is opposite. Rotate x and y only when that side is at the top. Raw coordinates, side and orientation are saved in pro_plays.jsonl. Missing/unknown orientation is unavailable, never silently guessed. X-Bow classes bridge (16<=y<=21), defensive (>21), enemy_side (<16), unavailable partition every X-Bow.

| Phase / histogram class | Bot per minute | Human X-Bow sides per minute |
|---|---|---|
| 1x bridge | 0.63 [0.60, 0.66]; total=912, n=775m | 0.73 [0.60, 0.86]; total=67, n=46m |
| 1x defensive | 0.13 [0.11, 0.15]; total=185, n=775m | 0.07 [0.01, 0.12]; total=6, n=46m |
| 1x enemy_side | 0.00 [0.0000, 0.0026]; total=0, n=775m | 0.00 [0.00, 0.04]; total=0, n=46m |
| 1x unavailable | 0.00 [0.0000, 0.0026]; total=0, n=775m | 0.00 [0.00, 0.04]; total=0, n=46m |
| 1x total | 0.76 [0.73, 0.79]; total=1097, n=775m | 0.79 [0.67, 0.92]; total=73, n=46m |
| 2x bridge | 1.03 [0.98, 1.07]; total=1005, n=747m | 1.24 [0.99, 1.50]; total=98, n=45m |
| 2x defensive | 0.23 [0.20, 0.26]; total=224, n=747m | 0.46 [0.29, 0.62]; total=36, n=45m |
| 2x enemy_side | 0.00 [0.0000, 0.0030]; total=1, n=747m | 0.00 [0.00, 0.05]; total=0, n=45m |
| 2x unavailable | 0.00 [0.0000, 0.0038]; total=0, n=747m | 0.00 [0.00, 0.05]; total=0, n=45m |
| 2x total | 1.26 [1.21, 1.30]; total=1230, n=747m | 1.70 [1.49, 1.91]; total=134, n=45m |
| 3x bridge | 0.70 [0.55, 0.86]; total=79, n=167m | 1.09 [0.62, 1.55]; total=26, n=33m |
| 3x defensive | 0.14 [0.08, 0.21]; total=16, n=167m | 0.17 [0.01, 0.32]; total=4, n=33m |
| 3x enemy_side | 0.00 [0.00, 0.03]; total=0, n=167m | 0.00 [0.00, 0.15]; total=0, n=33m |
| 3x unavailable | 0.00 [0.00, 0.03]; total=0, n=167m | 0.00 [0.00, 0.15]; total=0, n=33m |
| 3x total | 0.85 [0.68, 1.01]; total=95, n=167m | 1.25 [0.78, 1.73]; total=30, n=33m |

## Video metrics

Bot vs icebow-like humans: overlap >=5/8 n=41 sides; X-Bow + Tesla n=36 sides. Selected: icebow-like humans, n=41. The minimum 15-side criterion is met.

All brackets are approximate 95% CIs. Rates use match/replay-cluster ratio-of-sums intervals; means use the same cluster ratio with event counts as denominator. Fractions use a cluster-effective-size Wilson envelope around the sandwich interval, keeping nonzero uncertainty at 0/100%. n is independent clusters for rates, event observations for means/fractions; C states cluster count. No-data and one-cluster continuous/rate intervals are explicitly not estimable. Rates always retain numerator and exposure. Human sides share replay clusters.

### Top ten follow-up findings

1. Bot vs icebow-like humans (placement audit uses all human X-Bow sides): 40 first-phase X-Bows were misrotated into enemy_side. Corrected bridge/min 0.73 [0.60, 0.86]; total=67, n=46m; defensive/min 0.07 [0.01, 0.12]; total=6, n=46m.
2. Bot vs icebow-like humans: 41 sides overlap at least five Icebow cards; 36 have X-Bow + Tesla. Selected comparison icebow_like has 41 sides.
3. Bot only: the largest first-phase X-Bow placement group is observed Hog Rider: placements/min 0.689 [0.605, 0.773]; n=104, C=104; total=134, den=194.559; following enemy tower HP loss over a complete 20s 1216.021 [959.874, 1472.168]; n=95, C=68; total=115522, den=95.000. Damage includes every source.
4. Bot only: first-phase active-opponent empty-engagement proxy plays/min 0.154 [0.134, 0.174]; n=775, C=775; total=222, den=1441.338; nominal elixir/min 0.161 [0.140, 0.182]; n=775, C=775; total=232, den=1441.338.
5. Bot vs icebow-like humans: first-phase opposite-lane response fraction bot 0.175 [0.146, 0.209]; n=2690, C=739; total=472, den=2690.000; comparison 0.075 [0.023, 0.216]; n=133, C=41; total=10, den=133.000. Enemy bot placements are first-sighting proxies.
6. Bot only: first-phase Tesla delay after tank crossing 7.533 [5.910, 9.156]; n=118, C=92; total=888.9, den=118.000 seconds; survival fraction among resolved matched Teslas 0.495 [0.378, 0.613]; n=97, C=82; total=48, den=97.000.
7. Bot only: first-phase defensive troop lateral offset averages 2.570 [2.481, 2.659]; n=2347, C=729; total=6032.13, den=2347.000 tiles.
8. Bot only: first-phase all-supports-before-tank disappearance fraction 0.484 [0.409, 0.560]; n=283, C=205; total=137, den=283.000.
9. Bot only: first-phase enemy spell contacts with clumping/min 0.079 [0.062, 0.096]; n=775, C=775; total=114, den=1441.338; nominal clustered elixir/min 0.272 [0.188, 0.356]; n=775, C=775; total=392, den=1441.338.
10. Bot only: first-phase offensive commits/min while ahead 1.244 [1.150, 1.339]; n=449, C=449; total=440, den=353.566; while behind 1.116 [1.026, 1.206]; n=395, C=395; total=393, den=352.212. Following own tower HP loss while behind 540.872 [430.983, 650.761]; n=336, C=226; total=181733, den=336.000.

### Metric support

| Metric | Comparison | Public data support |
|---|---|---|
| a | bot only | First-seen enemy body placement and no observed engagement proxy; six-second coverage required. Human: unavailable |
| b | bot vs icebow-like humans | First-seen enemy body placement proxy; own public elixir at onset and response. Human: Timing/lane only; exact HTML placements. |
| c | bot only | Observed tank river crossing, reactive Tesla delay and survival to push end. Human: unavailable |
| d | bot only | Defensive troop lateral offset while a known ground troop is on our side. Human: unavailable |
| e | bot only | Support/tank public body disappearance intervals, with ties and censoring. Human: unavailable |
| f | bot only | Maximum simultaneous clumped bodies per existing enemy spell tower-contact episode. Human: unavailable |
| g | bot vs icebow-like humans | Observed-card census archetype; placements and all-source enemy tower HP loss in full next 20s. Human: Placements/archetype only; damage unavailable. |
| h | bot only | Observed HP-state exposure, offensive commits and all-source own tower HP loss in full next 20s. Human: unavailable |

### Bot vs icebow-like humans — all; human column = icebow-like humans

| Phase / card or placement | Bot /min [95% CI] | Human /min [95% CI] |
|---|---|---|
| 1x Skeletons | 1.41 [1.39, 1.44]; total=2035, n=775m | 1.35 [1.24, 1.46]; total=110, n=41m |
| 1x Log | 1.26 [1.23, 1.29]; total=1819, n=775m | 1.09 [0.98, 1.20]; total=89, n=41m |
| 1x Knight | 1.30 [1.27, 1.32]; total=1868, n=775m | 1.07 [0.94, 1.19]; total=87, n=41m |
| 1x Ice Wizard | 1.34 [1.32, 1.36]; total=1929, n=775m | 0.49 [0.31, 0.68]; total=40, n=41m |
| 1x Tornado | 0.48 [0.45, 0.51]; total=692, n=775m | 0.25 [0.12, 0.37]; total=20, n=41m |
| 1x Tesla | 1.04 [1.02, 1.07]; total=1506, n=775m | 0.79 [0.65, 0.92]; total=64, n=41m |
| 1x X-Bow | 0.76 [0.73, 0.79]; total=1097, n=775m | 0.71 [0.57, 0.86]; total=58, n=41m |
| 1x Rocket | 0.15 [0.13, 0.16]; total=209, n=775m | 0.06 [0.00, 0.12]; total=5, n=41m |
| 1x bridge X-Bow | 0.63 [0.60, 0.66]; total=912, n=775m | 0.64 [0.49, 0.79]; total=52, n=41m |
| 1x defensive X-Bow | 0.13 [0.11, 0.15]; total=185, n=775m | 0.07 [0.01, 0.14]; total=6, n=41m |
| 1x enemy_side X-Bow | 0.00 [0.0000, 0.0026]; total=0, n=775m | 0.00 [0.00, 0.05]; total=0, n=41m |
| 1x unavailable X-Bow | 0.00 [0.0000, 0.0026]; total=0, n=775m | 0.00 [0.00, 0.05]; total=0, n=41m |
| 1x Rocket tower | 0.10 [0.09, 0.12]; total=147, n=775m | 0.02 [0.00, 0.06]; total=2, n=41m |
| 1x left enemy_side | 0.12 [0.10, 0.14]; total=170, n=775m | 0.16 [0.05, 0.27]; total=13, n=41m |
| 1x left bridge | 1.63 [1.56, 1.71]; total=2356, n=775m | 1.20 [0.91, 1.49]; total=98, n=41m |
| 1x left own_front | 1.43 [1.36, 1.50]; total=2059, n=775m | 1.64 [1.35, 1.94]; total=134, n=41m |
| 1x left own_back | 0.80 [0.74, 0.86]; total=1152, n=775m | 0.97 [0.76, 1.18]; total=79, n=41m |
| 1x right enemy_side | 0.13 [0.12, 0.15]; total=194, n=775m | 0.11 [0.04, 0.18]; total=9, n=41m |
| 1x right bridge | 1.20 [1.13, 1.27]; total=1729, n=775m | 1.04 [0.80, 1.29]; total=85, n=41m |
| 1x right own_front | 1.79 [1.72, 1.86]; total=2586, n=775m | 1.66 [1.34, 1.97]; total=135, n=41m |
| 1x right own_back | 0.63 [0.58, 0.68]; total=909, n=775m | 0.79 [0.53, 1.04]; total=64, n=41m |
| 2x Skeletons | 2.37 [2.33, 2.41]; total=2315, n=747m | 2.22 [2.05, 2.39]; total=158, n=40m |
| 2x Log | 1.91 [1.85, 1.96]; total=1866, n=747m | 1.66 [1.47, 1.85]; total=118, n=40m |
| 2x Knight | 2.37 [2.33, 2.41]; total=2316, n=747m | 1.77 [1.59, 1.95]; total=126, n=40m |
| 2x Ice Wizard | 2.44 [2.40, 2.48]; total=2385, n=747m | 0.73 [0.43, 1.03]; total=52, n=40m |
| 2x Tornado | 0.85 [0.80, 0.90]; total=832, n=747m | 0.35 [0.17, 0.53]; total=25, n=40m |
| 2x Tesla | 1.78 [1.74, 1.83]; total=1745, n=747m | 1.60 [1.42, 1.78]; total=114, n=40m |
| 2x X-Bow | 1.26 [1.21, 1.30]; total=1230, n=747m | 1.45 [1.21, 1.69]; total=103, n=40m |
| 2x Rocket | 0.42 [0.38, 0.46]; total=411, n=747m | 0.41 [0.20, 0.61]; total=29, n=40m |
| 2x bridge X-Bow | 1.03 [0.98, 1.07]; total=1005, n=747m | 1.01 [0.75, 1.28]; total=72, n=40m |
| 2x defensive X-Bow | 0.23 [0.20, 0.26]; total=224, n=747m | 0.44 [0.26, 0.61]; total=31, n=40m |
| 2x enemy_side X-Bow | 0.00 [0.0000, 0.0030]; total=1, n=747m | 0.00 [0.00, 0.05]; total=0, n=40m |
| 2x unavailable X-Bow | 0.00 [0.0000, 0.0038]; total=0, n=747m | 0.00 [0.00, 0.05]; total=0, n=40m |
| 2x Rocket tower | 0.32 [0.28, 0.36]; total=314, n=747m | 0.22 [0.06, 0.39]; total=16, n=40m |
| 2x left enemy_side | 0.39 [0.34, 0.43]; total=379, n=747m | 0.60 [0.33, 0.88]; total=43, n=40m |
| 2x left bridge | 2.89 [2.72, 3.06]; total=2830, n=747m | 1.93 [1.53, 2.32]; total=137, n=40m |
| 2x left own_front | 2.12 [2.01, 2.24]; total=2077, n=747m | 2.84 [2.31, 3.37]; total=202, n=40m |
| 2x left own_back | 1.09 [1.00, 1.19]; total=1070, n=747m | 1.24 [0.81, 1.67]; total=88, n=40m |
| 2x right enemy_side | 0.36 [0.31, 0.40]; total=350, n=747m | 0.32 [0.12, 0.53]; total=23, n=40m |
| 2x right bridge | 2.89 [2.72, 3.05]; total=2823, n=747m | 2.31 [1.81, 2.80]; total=164, n=40m |
| 2x right own_front | 2.71 [2.59, 2.83]; total=2651, n=747m | 3.32 [2.83, 3.80]; total=236, n=40m |
| 2x right own_back | 0.94 [0.85, 1.03]; total=920, n=747m | 0.93 [0.62, 1.23]; total=66, n=40m |
| 3x Skeletons | 3.33 [3.14, 3.52]; total=374, n=167m | 2.97 [2.60, 3.34]; total=73, n=31m |
| 3x Log | 2.92 [2.73, 3.11]; total=328, n=167m | 2.97 [2.54, 3.40]; total=73, n=31m |
| 3x Knight | 3.37 [3.21, 3.54]; total=379, n=167m | 2.60 [2.15, 3.05]; total=64, n=31m |
| 3x Ice Wizard | 3.53 [3.39, 3.68]; total=397, n=167m | 1.34 [0.69, 1.99]; total=33, n=31m |
| 3x Tornado | 1.51 [1.32, 1.70]; total=170, n=167m | 0.45 [0.14, 0.75]; total=11, n=31m |
| 3x Tesla | 2.57 [2.38, 2.76]; total=289, n=167m | 2.40 [1.87, 2.92]; total=59, n=31m |
| 3x X-Bow | 0.85 [0.68, 1.01]; total=95, n=167m | 1.14 [0.67, 1.60]; total=28, n=31m |
| 3x Rocket | 1.48 [1.28, 1.67]; total=166, n=167m | 0.65 [0.20, 1.10]; total=16, n=31m |
| 3x bridge X-Bow | 0.70 [0.55, 0.86]; total=79, n=167m | 1.02 [0.56, 1.48]; total=25, n=31m |
| 3x defensive X-Bow | 0.14 [0.08, 0.21]; total=16, n=167m | 0.12 [0.00, 0.25]; total=3, n=31m |
| 3x enemy_side X-Bow | 0.00 [0.00, 0.03]; total=0, n=167m | 0.00 [0.00, 0.15]; total=0, n=31m |
| 3x unavailable X-Bow | 0.00 [0.00, 0.03]; total=0, n=167m | 0.00 [0.00, 0.15]; total=0, n=31m |
| 3x Rocket tower | 1.39 [1.19, 1.59]; total=156, n=167m | 0.53 [0.14, 0.92]; total=13, n=31m |
| 3x left enemy_side | 1.19 [0.94, 1.44]; total=134, n=167m | 1.18 [0.64, 1.72]; total=29, n=31m |
| 3x left bridge | 4.83 [4.09, 5.58]; total=543, n=167m | 3.54 [2.58, 4.49]; total=87, n=31m |
| 3x left own_front | 2.03 [1.74, 2.32]; total=228, n=167m | 4.92 [3.76, 6.08]; total=121, n=31m |
| 3x left own_back | 1.21 [0.87, 1.55]; total=136, n=167m | 1.22 [0.58, 1.86]; total=30, n=31m |
| 3x right enemy_side | 1.02 [0.82, 1.23]; total=115, n=167m | 0.57 [0.15, 0.99]; total=14, n=31m |
| 3x right bridge | 4.92 [4.20, 5.64]; total=553, n=167m | 3.37 [2.41, 4.34]; total=83, n=31m |
| 3x right own_front | 3.11 [2.71, 3.52]; total=350, n=167m | 3.94 [2.77, 5.12]; total=97, n=31m |
| 3x right own_back | 1.24 [0.88, 1.59]; total=139, n=167m | 0.61 [0.25, 0.97]; total=15, n=31m |

### Bot vs icebow-like humans — wins; human column = icebow-like humans

| Phase / card or placement | Bot /min [95% CI] | Human /min [95% CI] |
|---|---|---|
| 1x Skeletons | 1.40 [1.37, 1.43]; total=1046, n=399m | 1.50 [1.29, 1.71]; total=30, n=10m |
| 1x Log | 1.24 [1.20, 1.28]; total=928, n=399m | 1.15 [0.89, 1.41]; total=23, n=10m |
| 1x Knight | 1.30 [1.27, 1.34]; total=976, n=399m | 1.05 [0.71, 1.39]; total=21, n=10m |
| 1x Ice Wizard | 1.31 [1.28, 1.34]; total=983, n=399m | 0.15 [0.00, 0.36]; total=3, n=10m |
| 1x Tornado | 0.41 [0.36, 0.45]; total=303, n=399m | 0.15 [0.00, 0.36]; total=3, n=10m |
| 1x Tesla | 1.07 [1.03, 1.11]; total=803, n=399m | 0.80 [0.50, 1.10]; total=16, n=10m |
| 1x X-Bow | 0.80 [0.75, 0.84]; total=596, n=399m | 0.70 [0.44, 0.96]; total=14, n=10m |
| 1x Rocket | 0.15 [0.13, 0.18]; total=114, n=399m | 0.05 [0.00, 0.15]; total=1, n=10m |
| 1x bridge X-Bow | 0.67 [0.63, 0.71]; total=501, n=399m | 0.70 [0.44, 0.96]; total=14, n=10m |
| 1x defensive X-Bow | 0.13 [0.10, 0.15]; total=95, n=399m | 0.00 [0.00, 0.18]; total=0, n=10m |
| 1x enemy_side X-Bow | 0.00 [0.0000, 0.0049]; total=0, n=399m | 0.00 [0.00, 0.18]; total=0, n=10m |
| 1x unavailable X-Bow | 0.00 [0.0000, 0.0049]; total=0, n=399m | 0.00 [0.00, 0.18]; total=0, n=10m |
| 1x Rocket tower | 0.11 [0.08, 0.13]; total=80, n=399m | 0.00 [0.00, 0.18]; total=0, n=10m |
| 1x left enemy_side | 0.10 [0.07, 0.12]; total=73, n=399m | 0.15 [0.00, 0.30]; total=3, n=10m |
| 1x left bridge | 1.67 [1.56, 1.78]; total=1249, n=399m | 1.35 [0.91, 1.79]; total=27, n=10m |
| 1x left own_front | 1.36 [1.27, 1.45]; total=1015, n=399m | 1.20 [0.54, 1.86]; total=24, n=10m |
| 1x left own_back | 0.84 [0.76, 0.93]; total=630, n=399m | 0.90 [0.40, 1.40]; total=18, n=10m |
| 1x right enemy_side | 0.14 [0.11, 0.17]; total=105, n=399m | 0.15 [0.00, 0.36]; total=3, n=10m |
| 1x right bridge | 1.24 [1.13, 1.34]; total=924, n=399m | 1.15 [0.69, 1.61]; total=23, n=10m |
| 1x right own_front | 1.74 [1.65, 1.84]; total=1305, n=399m | 1.80 [1.05, 2.55]; total=36, n=10m |
| 1x right own_back | 0.60 [0.53, 0.67]; total=448, n=399m | 1.40 [0.86, 1.94]; total=28, n=10m |
| 2x Skeletons | 2.34 [2.28, 2.39]; total=1271, n=399m | 2.28 [1.89, 2.67]; total=42, n=10m |
| 2x Log | 1.84 [1.77, 1.91]; total=1001, n=399m | 1.58 [1.24, 1.91]; total=29, n=10m |
| 2x Knight | 2.32 [2.27, 2.38]; total=1263, n=399m | 1.58 [1.11, 2.04]; total=29, n=10m |
| 2x Ice Wizard | 2.44 [2.39, 2.49]; total=1326, n=399m | 0.33 [0.00, 0.74]; total=6, n=10m |
| 2x Tornado | 0.73 [0.67, 0.80]; total=398, n=399m | 0.38 [0.00, 0.87]; total=7, n=10m |
| 2x Tesla | 1.83 [1.77, 1.89]; total=995, n=399m | 1.63 [1.26, 1.99]; total=30, n=10m |
| 2x X-Bow | 1.33 [1.27, 1.40]; total=726, n=399m | 1.63 [1.15, 2.11]; total=30, n=10m |
| 2x Rocket | 0.48 [0.43, 0.54]; total=263, n=399m | 0.33 [0.00, 0.70]; total=6, n=10m |
| 2x bridge X-Bow | 1.09 [1.03, 1.15]; total=595, n=399m | 1.20 [0.55, 1.84]; total=22, n=10m |
| 2x defensive X-Bow | 0.24 [0.20, 0.28]; total=130, n=399m | 0.43 [0.09, 0.78]; total=8, n=10m |
| 2x enemy_side X-Bow | 0.00 [0.0000, 0.0054]; total=1, n=399m | 0.00 [0.00, 0.20]; total=0, n=10m |
| 2x unavailable X-Bow | 0.00 [0.0000, 0.0068]; total=0, n=399m | 0.00 [0.00, 0.20]; total=0, n=10m |
| 2x Rocket tower | 0.38 [0.32, 0.43]; total=205, n=399m | 0.16 [0.00, 0.40]; total=3, n=10m |
| 2x left enemy_side | 0.47 [0.41, 0.54]; total=258, n=399m | 0.87 [0.17, 1.57]; total=16, n=10m |
| 2x left bridge | 3.01 [2.78, 3.23]; total=1635, n=399m | 1.63 [0.89, 2.37]; total=30, n=10m |
| 2x left own_front | 1.96 [1.83, 2.10]; total=1067, n=399m | 2.61 [1.78, 3.43]; total=48, n=10m |
| 2x left own_back | 1.09 [0.96, 1.23]; total=595, n=399m | 0.92 [0.13, 1.72]; total=17, n=10m |
| 2x right enemy_side | 0.41 [0.34, 0.48]; total=222, n=399m | 0.27 [0.01, 0.53]; total=5, n=10m |
| 2x right bridge | 3.08 [2.85, 3.30]; total=1674, n=399m | 2.82 [1.79, 3.86]; total=52, n=10m |
| 2x right own_front | 2.54 [2.38, 2.70]; total=1380, n=399m | 3.86 [2.82, 4.89]; total=71, n=10m |
| 2x right own_back | 0.76 [0.65, 0.86]; total=412, n=399m | 1.20 [0.62, 1.77]; total=22, n=10m |
| 3x Skeletons | 3.24 [2.99, 3.48]; total=201, n=93m | 3.24 [2.48, 3.99]; total=21, n=8m |
| 3x Log | 2.93 [2.68, 3.19]; total=182, n=93m | 3.08 [2.09, 4.08]; total=20, n=8m |
| 3x Knight | 3.19 [2.95, 3.43]; total=198, n=93m | 2.00 [0.92, 3.09]; total=13, n=8m |
| 3x Ice Wizard | 3.43 [3.21, 3.65]; total=213, n=93m | 1.39 [0.00, 3.07]; total=9, n=8m |
| 3x Tornado | 1.55 [1.32, 1.78]; total=96, n=93m | 0.15 [0.00, 0.45]; total=1, n=8m |
| 3x Tesla | 2.58 [2.31, 2.85]; total=160, n=93m | 2.93 [2.08, 3.77]; total=19, n=8m |
| 3x X-Bow | 0.77 [0.57, 0.98]; total=48, n=93m | 0.93 [0.13, 1.72]; total=6, n=8m |
| 3x Rocket | 1.71 [1.44, 1.98]; total=106, n=93m | 0.62 [0.00, 1.79]; total=4, n=8m |
| 3x bridge X-Bow | 0.68 [0.47, 0.88]; total=42, n=93m | 0.77 [0.00, 1.60]; total=5, n=8m |
| 3x defensive X-Bow | 0.10 [0.02, 0.17]; total=6, n=93m | 0.15 [0.00, 0.45]; total=1, n=8m |
| 3x enemy_side X-Bow | 0.00 [0.00, 0.06]; total=0, n=93m | 0.00 [0.00, 0.57]; total=0, n=8m |
| 3x unavailable X-Bow | 0.00 [0.00, 0.06]; total=0, n=93m | 0.00 [0.00, 0.57]; total=0, n=8m |
| 3x Rocket tower | 1.68 [1.40, 1.95]; total=104, n=93m | 0.46 [0.00, 1.35]; total=3, n=8m |
| 3x left enemy_side | 1.45 [1.08, 1.82]; total=90, n=93m | 1.23 [0.26, 2.21]; total=8, n=8m |
| 3x left bridge | 5.12 [4.01, 6.24]; total=318, n=93m | 3.08 [1.03, 5.13]; total=20, n=8m |
| 3x left own_front | 1.93 [1.56, 2.31]; total=120, n=93m | 4.32 [2.71, 5.92]; total=28, n=8m |
| 3x left own_back | 1.01 [0.63, 1.40]; total=63, n=93m | 1.54 [0.20, 2.89]; total=10, n=8m |
| 3x right enemy_side | 1.16 [0.87, 1.45]; total=72, n=93m | 0.77 [0.00, 1.68]; total=5, n=8m |
| 3x right bridge | 4.49 [3.58, 5.41]; total=279, n=93m | 4.01 [1.87, 6.15]; total=26, n=8m |
| 3x right own_front | 3.03 [2.47, 3.59]; total=188, n=93m | 5.24 [3.02, 7.46]; total=34, n=8m |
| 3x right own_back | 1.19 [0.71, 1.67]; total=74, n=93m | 0.77 [0.00, 1.61]; total=5, n=8m |

### Bot vs icebow-like humans — losses; human column = icebow-like humans

| Phase / card or placement | Bot /min [95% CI] | Human /min [95% CI] |
|---|---|---|
| 1x Skeletons | 1.42 [1.39, 1.46]; total=979, n=373m | 1.30 [1.17, 1.43]; total=80, n=31m |
| 1x Log | 1.28 [1.24, 1.33]; total=883, n=373m | 1.07 [0.95, 1.19]; total=66, n=31m |
| 1x Knight | 1.29 [1.25, 1.32]; total=884, n=373m | 1.07 [0.94, 1.20]; total=66, n=31m |
| 1x Ice Wizard | 1.36 [1.33, 1.40]; total=938, n=373m | 0.60 [0.38, 0.82]; total=37, n=31m |
| 1x Tornado | 0.56 [0.52, 0.61]; total=386, n=373m | 0.28 [0.13, 0.42]; total=17, n=31m |
| 1x Tesla | 1.01 [0.97, 1.05]; total=696, n=373m | 0.78 [0.63, 0.93]; total=48, n=31m |
| 1x X-Bow | 0.72 [0.68, 0.77]; total=498, n=373m | 0.72 [0.54, 0.89]; total=44, n=31m |
| 1x Rocket | 0.14 [0.11, 0.16]; total=95, n=373m | 0.07 [0.00, 0.14]; total=4, n=31m |
| 1x bridge X-Bow | 0.59 [0.55, 0.64]; total=409, n=373m | 0.62 [0.44, 0.80]; total=38, n=31m |
| 1x defensive X-Bow | 0.13 [0.11, 0.15]; total=89, n=373m | 0.10 [0.01, 0.18]; total=6, n=31m |
| 1x enemy_side X-Bow | 0.00 [0.0000, 0.0054]; total=0, n=373m | 0.00 [0.00, 0.06]; total=0, n=31m |
| 1x unavailable X-Bow | 0.00 [0.0000, 0.0054]; total=0, n=373m | 0.00 [0.00, 0.06]; total=0, n=31m |
| 1x Rocket tower | 0.10 [0.07, 0.12]; total=67, n=373m | 0.03 [0.00, 0.08]; total=2, n=31m |
| 1x left enemy_side | 0.14 [0.11, 0.17]; total=96, n=373m | 0.16 [0.02, 0.30]; total=10, n=31m |
| 1x left bridge | 1.59 [1.49, 1.70]; total=1097, n=373m | 1.15 [0.80, 1.51]; total=71, n=31m |
| 1x left own_front | 1.50 [1.40, 1.60]; total=1033, n=373m | 1.79 [1.47, 2.10]; total=110, n=31m |
| 1x left own_back | 0.76 [0.67, 0.84]; total=520, n=373m | 0.99 [0.76, 1.23]; total=61, n=31m |
| 1x right enemy_side | 0.13 [0.10, 0.16]; total=89, n=373m | 0.10 [0.03, 0.17]; total=6, n=31m |
| 1x right bridge | 1.16 [1.06, 1.25]; total=796, n=373m | 1.01 [0.72, 1.30]; total=62, n=31m |
| 1x right own_front | 1.85 [1.74, 1.95]; total=1270, n=373m | 1.61 [1.26, 1.96]; total=99, n=31m |
| 1x right own_back | 0.67 [0.59, 0.74]; total=458, n=373m | 0.59 [0.34, 0.83]; total=36, n=31m |
| 2x Skeletons | 2.40 [2.34, 2.47]; total=1035, n=345m | 2.20 [2.02, 2.38]; total=116, n=30m |
| 2x Log | 1.99 [1.91, 2.07]; total=857, n=345m | 1.69 [1.46, 1.92]; total=89, n=30m |
| 2x Knight | 2.42 [2.36, 2.48]; total=1044, n=345m | 1.84 [1.66, 2.02]; total=97, n=30m |
| 2x Ice Wizard | 2.44 [2.38, 2.50]; total=1050, n=345m | 0.87 [0.51, 1.23]; total=46, n=30m |
| 2x Tornado | 1.00 [0.92, 1.08]; total=430, n=345m | 0.34 [0.17, 0.51]; total=18, n=30m |
| 2x Tesla | 1.72 [1.66, 1.79]; total=743, n=345m | 1.59 [1.38, 1.81]; total=84, n=30m |
| 2x X-Bow | 1.16 [1.09, 1.23]; total=500, n=345m | 1.39 [1.11, 1.66]; total=73, n=30m |
| 2x Rocket | 0.34 [0.29, 0.40]; total=147, n=345m | 0.44 [0.19, 0.68]; total=23, n=30m |
| 2x bridge X-Bow | 0.94 [0.87, 1.01]; total=406, n=345m | 0.95 [0.67, 1.23]; total=50, n=30m |
| 2x defensive X-Bow | 0.22 [0.17, 0.27]; total=94, n=345m | 0.44 [0.23, 0.64]; total=23, n=30m |
| 2x enemy_side X-Bow | 0.00 [0.0000, 0.0086]; total=0, n=345m | 0.00 [0.00, 0.07]; total=0, n=30m |
| 2x unavailable X-Bow | 0.00 [0.0000, 0.0086]; total=0, n=345m | 0.00 [0.00, 0.07]; total=0, n=30m |
| 2x Rocket tower | 0.25 [0.20, 0.30]; total=108, n=345m | 0.25 [0.03, 0.46]; total=13, n=30m |
| 2x left enemy_side | 0.28 [0.23, 0.34]; total=121, n=345m | 0.51 [0.23, 0.79]; total=27, n=30m |
| 2x left bridge | 2.73 [2.47, 2.99]; total=1176, n=345m | 2.03 [1.56, 2.50]; total=107, n=30m |
| 2x left own_front | 2.33 [2.14, 2.52]; total=1003, n=345m | 2.92 [2.26, 3.58]; total=154, n=30m |
| 2x left own_back | 1.10 [0.96, 1.24]; total=474, n=345m | 1.35 [0.84, 1.86]; total=71, n=30m |
| 2x right enemy_side | 0.29 [0.23, 0.36]; total=126, n=345m | 0.34 [0.08, 0.61]; total=18, n=30m |
| 2x right bridge | 2.64 [2.39, 2.89]; total=1137, n=345m | 2.13 [1.56, 2.69]; total=112, n=30m |
| 2x right own_front | 2.93 [2.75, 3.11]; total=1263, n=345m | 3.13 [2.59, 3.67]; total=165, n=30m |
| 2x right own_back | 1.17 [1.02, 1.32]; total=506, n=345m | 0.83 [0.48, 1.19]; total=44, n=30m |
| 3x Skeletons | 3.44 [3.15, 3.73]; total=173, n=74m | 2.87 [2.45, 3.29]; total=52, n=23m |
| 3x Log | 2.90 [2.61, 3.20]; total=146, n=74m | 2.93 [2.45, 3.40]; total=53, n=23m |
| 3x Knight | 3.60 [3.38, 3.82]; total=181, n=74m | 2.81 [2.35, 3.28]; total=51, n=23m |
| 3x Ice Wizard | 3.66 [3.48, 3.83]; total=184, n=74m | 1.32 [0.66, 1.99]; total=24, n=23m |
| 3x Tornado | 1.47 [1.15, 1.79]; total=74, n=74m | 0.55 [0.15, 0.95]; total=10, n=23m |
| 3x Tesla | 2.57 [2.29, 2.84]; total=129, n=74m | 2.21 [1.56, 2.85]; total=40, n=23m |
| 3x X-Bow | 0.93 [0.67, 1.20]; total=47, n=74m | 1.21 [0.65, 1.78]; total=22, n=23m |
| 3x Rocket | 1.19 [0.93, 1.46]; total=60, n=74m | 0.66 [0.20, 1.13]; total=12, n=23m |
| 3x bridge X-Bow | 0.74 [0.50, 0.97]; total=37, n=74m | 1.10 [0.55, 1.66]; total=20, n=23m |
| 3x defensive X-Bow | 0.20 [0.09, 0.31]; total=10, n=74m | 0.11 [0.00, 0.26]; total=2, n=23m |
| 3x enemy_side X-Bow | 0.00 [0.00, 0.07]; total=0, n=74m | 0.00 [0.00, 0.20]; total=0, n=23m |
| 3x unavailable X-Bow | 0.00 [0.00, 0.07]; total=0, n=74m | 0.00 [0.00, 0.20]; total=0, n=23m |
| 3x Rocket tower | 1.03 [0.77, 1.30]; total=52, n=74m | 0.55 [0.11, 0.99]; total=10, n=23m |
| 3x left enemy_side | 0.87 [0.57, 1.18]; total=44, n=74m | 1.16 [0.50, 1.82]; total=21, n=23m |
| 3x left bridge | 4.47 [3.55, 5.40]; total=225, n=74m | 3.70 [2.62, 4.78]; total=67, n=23m |
| 3x left own_front | 2.15 [1.69, 2.61]; total=108, n=74m | 5.13 [3.66, 6.60]; total=93, n=23m |
| 3x left own_back | 1.45 [0.86, 2.04]; total=73, n=74m | 1.10 [0.36, 1.85]; total=20, n=23m |
| 3x right enemy_side | 0.86 [0.57, 1.14]; total=43, n=74m | 0.50 [0.02, 0.97]; total=9, n=23m |
| 3x right bridge | 5.45 [4.31, 6.58]; total=274, n=74m | 3.15 [2.06, 4.23]; total=57, n=23m |
| 3x right own_front | 3.22 [2.63, 3.82]; total=162, n=74m | 3.48 [2.14, 4.81]; total=63, n=23m |
| 3x right own_back | 1.29 [0.76, 1.82]; total=65, n=74m | 0.55 [0.16, 0.94]; total=10, n=23m |

### Bot vs icebow-like humans — big_losses; human column = icebow-like humans

| Phase / card or placement | Bot /min [95% CI] | Human /min [95% CI] |
|---|---|---|
| 1x Skeletons | 1.37 [1.30, 1.45]; total=278, n=114m | 1.22 [0.79, 1.64]; total=14, n=6m |
| 1x Log | 1.27 [1.19, 1.35]; total=257, n=114m | 1.04 [0.66, 1.42]; total=12, n=6m |
| 1x Knight | 1.22 [1.15, 1.29]; total=247, n=114m | 1.13 [0.81, 1.45]; total=13, n=6m |
| 1x Ice Wizard | 1.32 [1.25, 1.39]; total=267, n=114m | 0.61 [0.04, 1.18]; total=7, n=6m |
| 1x Tornado | 0.67 [0.58, 0.76]; total=135, n=114m | 0.52 [0.04, 1.00]; total=6, n=6m |
| 1x Tesla | 0.87 [0.79, 0.95]; total=176, n=114m | 0.52 [0.29, 0.75]; total=6, n=6m |
| 1x X-Bow | 0.84 [0.76, 0.91]; total=169, n=114m | 0.52 [0.08, 0.96]; total=6, n=6m |
| 1x Rocket | 0.12 [0.08, 0.17]; total=25, n=114m | 0.17 [0.00, 0.51]; total=2, n=6m |
| 1x bridge X-Bow | 0.72 [0.65, 0.79]; total=146, n=114m | 0.43 [0.04, 0.83]; total=5, n=6m |
| 1x defensive X-Bow | 0.11 [0.07, 0.16]; total=23, n=114m | 0.09 [0.00, 0.26]; total=1, n=6m |
| 1x enemy_side X-Bow | 0.00 [0.00, 0.02]; total=0, n=114m | 0.00 [0.00, 0.32]; total=0, n=6m |
| 1x unavailable X-Bow | 0.00 [0.00, 0.02]; total=0, n=114m | 0.00 [0.00, 0.32]; total=0, n=6m |
| 1x Rocket tower | 0.09 [0.05, 0.13]; total=18, n=114m | 0.09 [0.00, 0.26]; total=1, n=6m |
| 1x left enemy_side | 0.14 [0.09, 0.19]; total=28, n=114m | 0.09 [0.00, 0.26]; total=1, n=6m |
| 1x left bridge | 1.42 [1.24, 1.61]; total=288, n=114m | 0.35 [0.15, 0.55]; total=4, n=6m |
| 1x left own_front | 1.46 [1.29, 1.63]; total=295, n=114m | 1.82 [1.31, 2.33]; total=21, n=6m |
| 1x left own_back | 0.51 [0.41, 0.62]; total=104, n=114m | 0.96 [0.75, 1.16]; total=11, n=6m |
| 1x right enemy_side | 0.17 [0.12, 0.22]; total=34, n=114m | 0.17 [0.00, 0.38]; total=2, n=6m |
| 1x right bridge | 1.27 [1.10, 1.44]; total=257, n=114m | 1.30 [0.52, 2.09]; total=15, n=6m |
| 1x right own_front | 1.99 [1.78, 2.20]; total=403, n=114m | 1.82 [0.68, 2.97]; total=21, n=6m |
| 1x right own_back | 0.72 [0.59, 0.85]; total=145, n=114m | 0.69 [0.07, 1.32]; total=8, n=6m |
| 2x Skeletons | 2.52 [2.33, 2.72]; total=150, n=86m | 0.76 [0.00, 1.64]; total=3, n=5m |
| 2x Log | 1.83 [1.61, 2.06]; total=109, n=86m | 0.51 [0.00, 1.13]; total=2, n=5m |
| 2x Knight | 2.24 [2.04, 2.43]; total=133, n=86m | 0.51 [0.00, 1.43]; total=2, n=5m |
| 2x Ice Wizard | 2.24 [2.03, 2.45]; total=133, n=86m | 0.25 [0.00, 0.74]; total=1, n=5m |
| 2x Tornado | 1.36 [1.15, 1.57]; total=81, n=86m | 0.00 [0.00, 0.94]; total=0, n=5m |
| 2x Tesla | 1.28 [1.08, 1.48]; total=76, n=86m | 0.51 [0.00, 1.09]; total=2, n=5m |
| 2x X-Bow | 0.81 [0.63, 0.98]; total=48, n=86m | 0.25 [0.00, 0.75]; total=1, n=5m |
| 2x Rocket | 0.32 [0.19, 0.45]; total=19, n=86m | 0.25 [0.00, 0.72]; total=1, n=5m |
| 2x bridge X-Bow | 0.64 [0.48, 0.80]; total=38, n=86m | 0.25 [0.00, 0.75]; total=1, n=5m |
| 2x defensive X-Bow | 0.17 [0.06, 0.28]; total=10, n=86m | 0.00 [0.00, 0.94]; total=0, n=5m |
| 2x enemy_side X-Bow | 0.00 [0.00, 0.06]; total=0, n=86m | 0.00 [0.00, 0.94]; total=0, n=5m |
| 2x unavailable X-Bow | 0.00 [0.00, 0.06]; total=0, n=86m | 0.00 [0.00, 0.94]; total=0, n=5m |
| 2x Rocket tower | 0.20 [0.10, 0.31]; total=12, n=86m | 0.00 [0.00, 0.94]; total=0, n=5m |
| 2x left enemy_side | 0.25 [0.12, 0.38]; total=15, n=86m | 0.00 [0.00, 0.94]; total=0, n=5m |
| 2x left bridge | 2.19 [1.58, 2.79]; total=130, n=86m | 0.25 [0.00, 0.72]; total=1, n=5m |
| 2x left own_front | 2.54 [2.01, 3.07]; total=151, n=86m | 0.76 [0.00, 2.15]; total=3, n=5m |
| 2x left own_back | 1.43 [1.10, 1.76]; total=85, n=86m | 0.51 [0.00, 1.53]; total=2, n=5m |
| 2x right enemy_side | 0.24 [0.11, 0.36]; total=14, n=86m | 0.51 [0.00, 1.13]; total=2, n=5m |
| 2x right bridge | 1.60 [1.14, 2.06]; total=95, n=86m | 0.76 [0.00, 1.64]; total=3, n=5m |
| 2x right own_front | 2.84 [2.31, 3.38]; total=169, n=86m | 1.78 [0.07, 3.49]; total=7, n=5m |
| 2x right own_back | 1.51 [1.13, 1.90]; total=90, n=86m | 0.25 [0.00, 0.72]; total=1, n=5m |
| 3x Skeletons | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x Log | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x Knight | 9.76 [95% CI not estimable]; total=1, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x Ice Wizard | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x Tornado | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x Tesla | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x X-Bow | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x Rocket | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x bridge X-Bow | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x defensive X-Bow | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x enemy_side X-Bow | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x unavailable X-Bow | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x Rocket tower | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x left enemy_side | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x left bridge | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x left own_front | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x left own_back | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x right enemy_side | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x right bridge | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x right own_front | 0.00 [95% CI not estimable]; total=0, n=1m | unavailable (n=0; 95% CI not estimable) |
| 3x right own_back | 9.76 [95% CI not estimable]; total=1, n=1m | unavailable (n=0; 95% CI not estimable) |

### Video outcomes: all

Bot only unless the comparison column says bot vs icebow-like humans. Per-minute values use phase minutes except state/archetype rows, which use their own exposure. Means/fractions show event n and cluster C. Human column = icebow-like humans.

| Phase / metric (unit) | Comparison | Bot [95% CI] | Human [95% CI] |
|---|---|---|
| 1x clump_bodies (per_minute) | bot only | 0.218 [0.171, 0.264]; n=775, C=775; total=314, den=1441.338 | unavailable |
| 2x clump_bodies (per_minute) | bot only | 0.562 [0.448, 0.676]; n=747, C=747; total=550, den=978.213 | unavailable |
| 3x clump_bodies (per_minute) | bot only | 1.700 [1.146, 2.253]; n=167, C=167; total=191, den=112.370 | unavailable |
| 1x clump_contacts (per_minute) | bot only | 0.388 [0.341, 0.435]; n=775, C=775; total=559, den=1441.338 | unavailable |
| 2x clump_contacts (per_minute) | bot only | 0.843 [0.748, 0.939]; n=747, C=747; total=825, den=978.213 | unavailable |
| 3x clump_contacts (per_minute) | bot only | 1.691 [1.358, 2.023]; n=167, C=167; total=190, den=112.370 | unavailable |
| 1x clump_elixir (per_minute) | bot only | 0.272 [0.188, 0.356]; n=775, C=775; total=392, den=1441.338 | unavailable |
| 2x clump_elixir (per_minute) | bot only | 0.804 [0.608, 1.000]; n=747, C=747; total=786.333, den=978.213 | unavailable |
| 3x clump_elixir (per_minute) | bot only | 2.569 [1.604, 3.534]; n=167, C=167; total=288.667, den=112.370 | unavailable |
| 1x clump_episodes (per_minute) | bot only | 0.079 [0.062, 0.096]; n=775, C=775; total=114, den=1441.338 | unavailable |
| 2x clump_episodes (per_minute) | bot only | 0.197 [0.160, 0.235]; n=747, C=747; total=193, den=978.213 | unavailable |
| 3x clump_episodes (per_minute) | bot only | 0.578 [0.395, 0.762]; n=167, C=167; total=65, den=112.370 | unavailable |
| 1x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.003]; n=775, C=775; total=0, den=1441.338 | unavailable |
| 2x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.004]; n=747, C=747; total=0, den=978.213 | unavailable |
| 3x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.033]; n=167, C=167; total=0, den=112.370 | unavailable |
| 1x commit.ahead (per_minute) | bot only | 1.244 [1.150, 1.339]; n=449, C=449; total=440, den=353.566 | unavailable |
| 2x commit.ahead (per_minute) | bot only | 2.706 [2.583, 2.829]; n=441, C=441; total=981, den=362.555 | unavailable |
| 3x commit.ahead (per_minute) | bot only | 4.685 [4.203, 5.167]; n=79, C=79; total=175, den=37.352 | unavailable |
| 1x commit.behind (per_minute) | bot only | 1.116 [1.026, 1.206]; n=395, C=395; total=393, den=352.212 | unavailable |
| 2x commit.behind (per_minute) | bot only | 2.745 [2.619, 2.871]; n=412, C=412; total=933, den=339.901 | unavailable |
| 3x commit.behind (per_minute) | bot only | 4.366 [3.946, 4.787]; n=71, C=71; total=167, den=38.247 | unavailable |
| 1x commit.level (per_minute) | bot only | 1.420 [1.351, 1.488]; n=715, C=715; total=1013, den=713.605 | unavailable |
| 2x commit.level (per_minute) | bot only | 2.894 [2.738, 3.050]; n=397, C=397; total=697, den=240.857 | unavailable |
| 3x commit.level (per_minute) | bot only | 4.623 [4.136, 5.109]; n=70, C=70; total=146, den=31.583 | unavailable |
| 1x commit_damage.ahead (mean) | bot only | 390.950 [305.661, 476.240]; n=341, C=196; total=133314, den=341.000 | unavailable |
| 2x commit_damage.ahead (mean) | bot only | 244.296 [194.561, 294.032]; n=597, C=270; total=145845, den=597.000 | unavailable |
| 3x commit_damage.ahead (mean) | bot only | 241.122 [137.172, 345.072]; n=74, C=39; total=17843, den=74.000 | unavailable |
| 1x commit_damage.behind (mean) | bot only | 540.872 [430.983, 650.761]; n=336, C=226; total=181733, den=336.000 | unavailable |
| 2x commit_damage.behind (mean) | bot only | 424.853 [361.231, 488.475]; n=707, C=268; total=300371, den=707.000 | unavailable |
| 3x commit_damage.behind (mean) | bot only | 199.551 [123.580, 275.521]; n=89, C=41; total=17760, den=89.000 | unavailable |
| 1x commit_damage.level (mean) | bot only | 342.024 [284.352, 399.696]; n=848, C=517; total=290036, den=848.000 | unavailable |
| 2x commit_damage.level (mean) | bot only | 305.021 [235.179, 374.863]; n=526, C=240; total=160441, den=526.000 | unavailable |
| 3x commit_damage.level (mean) | bot only | 311.837 [186.963, 436.712]; n=80, C=34; total=24947, den=80.000 | unavailable |
| 1x commit_full.ahead (per_minute) | bot only | 0.964 [0.873, 1.056]; n=449, C=449; total=341, den=353.566 | unavailable |
| 2x commit_full.ahead (per_minute) | bot only | 1.647 [1.524, 1.770]; n=441, C=441; total=597, den=362.555 | unavailable |
| 3x commit_full.ahead (per_minute) | bot only | 1.981 [1.600, 2.362]; n=79, C=79; total=74, den=37.352 | unavailable |
| 1x commit_full.behind (per_minute) | bot only | 0.954 [0.865, 1.043]; n=395, C=395; total=336, den=352.212 | unavailable |
| 2x commit_full.behind (per_minute) | bot only | 2.080 [1.943, 2.217]; n=412, C=412; total=707, den=339.901 | unavailable |
| 3x commit_full.behind (per_minute) | bot only | 2.327 [1.957, 2.697]; n=71, C=71; total=89, den=38.247 | unavailable |
| 1x commit_full.level (per_minute) | bot only | 1.188 [1.122, 1.255]; n=715, C=715; total=848, den=713.605 | unavailable |
| 2x commit_full.level (per_minute) | bot only | 2.184 [2.013, 2.354]; n=397, C=397; total=526, den=240.857 | unavailable |
| 3x commit_full.level (per_minute) | bot only | 2.533 [2.126, 2.940]; n=70, C=70; total=80, den=31.583 | unavailable |
| 1x cycle_assessed (per_minute) | bot only | 1.333 [1.281, 1.386]; n=775, C=775; total=1922, den=1441.338 | unavailable |
| 2x cycle_assessed (per_minute) | bot only | 2.360 [2.268, 2.453]; n=747, C=747; total=2309, den=978.213 | unavailable |
| 3x cycle_assessed (per_minute) | bot only | 3.978 [3.677, 4.279]; n=167, C=167; total=447, den=112.370 | unavailable |
| 1x cycle_candidates (per_minute) | bot only | 1.475 [1.421, 1.529]; n=775, C=775; total=2126, den=1441.338 | unavailable |
| 2x cycle_candidates (per_minute) | bot only | 2.769 [2.676, 2.863]; n=747, C=747; total=2709, den=978.213 | unavailable |
| 3x cycle_candidates (per_minute) | bot only | 4.841 [4.515, 5.167]; n=167, C=167; total=544, den=112.370 | unavailable |
| 1x cycle_elixir_at_play (mean) | bot only | 6.067 [5.717, 6.417]; n=222, C=199; total=1346.84, den=222.000 | unavailable |
| 2x cycle_elixir_at_play (mean) | bot only | 4.934 [4.642, 5.225]; n=287, C=224; total=1415.93, den=287.000 | unavailable |
| 3x cycle_elixir_at_play (mean) | bot only | 5.090 [4.572, 5.609]; n=56, C=49; total=285.067, den=56.000 | unavailable |
| 1x cycle_empty (per_minute) | bot only | 0.154 [0.134, 0.174]; n=775, C=775; total=222, den=1441.338 | unavailable |
| 2x cycle_empty (per_minute) | bot only | 0.293 [0.259, 0.328]; n=747, C=747; total=287, den=978.213 | unavailable |
| 3x cycle_empty (per_minute) | bot only | 0.498 [0.384, 0.613]; n=167, C=167; total=56, den=112.370 | unavailable |
| 1x cycle_empty_elixir (per_minute) | bot only | 0.161 [0.140, 0.182]; n=775, C=775; total=232, den=1441.338 | unavailable |
| 2x cycle_empty_elixir (per_minute) | bot only | 0.310 [0.272, 0.348]; n=747, C=747; total=303, den=978.213 | unavailable |
| 3x cycle_empty_elixir (per_minute) | bot only | 0.516 [0.394, 0.639]; n=167, C=167; total=58, den=112.370 | unavailable |
| 1x kill_assessed (per_minute) | bot only | 0.196 [0.170, 0.223]; n=775, C=775; total=283, den=1441.338 | unavailable |
| 2x kill_assessed (per_minute) | bot only | 0.361 [0.309, 0.412]; n=747, C=747; total=353, den=978.213 | unavailable |
| 3x kill_assessed (per_minute) | bot only | 0.570 [0.396, 0.743]; n=167, C=167; total=64, den=112.370 | unavailable |
| 1x kill_pushes (per_minute) | bot only | 0.273 [0.240, 0.307]; n=775, C=775; total=394, den=1441.338 | unavailable |
| 2x kill_pushes (per_minute) | bot only | 0.521 [0.460, 0.583]; n=747, C=747; total=510, den=978.213 | unavailable |
| 3x kill_pushes (per_minute) | bot only | 0.952 [0.722, 1.182]; n=167, C=167; total=107, den=112.370 | unavailable |
| 1x kill_supports_first (per_minute) | bot only | 0.095 [0.078, 0.112]; n=775, C=775; total=137, den=1441.338 | unavailable |
| 2x kill_supports_first (per_minute) | bot only | 0.171 [0.140, 0.202]; n=747, C=747; total=167, den=978.213 | unavailable |
| 3x kill_supports_first (per_minute) | bot only | 0.320 [0.205, 0.436]; n=167, C=167; total=36, den=112.370 | unavailable |
| 1x kill_supports_first_fraction (fraction) | bot only | 0.484 [0.409, 0.560]; n=283, C=205; total=137, den=283.000 | unavailable |
| 2x kill_supports_first_fraction (fraction) | bot only | 0.473 [0.393, 0.555]; n=353, C=200; total=167, den=353.000 | unavailable |
| 3x kill_supports_first_fraction (fraction) | bot only | 0.562 [0.391, 0.720]; n=64, C=39; total=36, den=64.000 | unavailable |
| 1x pressure_complete (per_minute) | bot vs icebow-like humans | 1.866 [1.784, 1.949]; n=775, C=775; total=2690, den=1441.338 | 1.632 [1.383, 1.881]; n=41, C=41; total=133, den=81.517 |
| 2x pressure_complete (per_minute) | bot vs icebow-like humans | 1.743 [1.626, 1.860]; n=747, C=747; total=1705, den=978.213 | 2.405 [2.005, 2.804]; n=40, C=40; total=171, den=71.116 |
| 3x pressure_complete (per_minute) | bot vs icebow-like humans | 1.442 [1.099, 1.784]; n=167, C=167; total=162, den=112.370 | 1.016 [0.559, 1.473]; n=31, C=31; total=25, den=24.604 |
| 1x pressure_elixir (mean) | bot only | 6.801 [6.701, 6.901]; n=2690, C=739; total=18294.9, den=2690.000 | unavailable |
| 2x pressure_elixir (mean) | bot only | 5.149 [5.028, 5.271]; n=1705, C=562; total=8779.16, den=1705.000 | unavailable |
| 3x pressure_elixir (mean) | bot only | 4.331 [3.937, 4.724]; n=162, C=67; total=701.542, den=162.000 | unavailable |
| 1x pressure_response_elixir (mean) | bot only | 8.307 [8.156, 8.458]; n=472, C=350; total=3920.87, den=472.000 | unavailable |
| 2x pressure_response_elixir (mean) | bot only | 6.868 [6.696, 7.040]; n=400, C=275; total=2747.2, den=400.000 | unavailable |
| 3x pressure_response_elixir (mean) | bot only | 6.106 [5.357, 6.854]; n=36, C=24; total=219.799, den=36.000 | unavailable |
| 1x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.175 [0.146, 0.209]; n=2690, C=739; total=472, den=2690.000 | 0.075 [0.023, 0.216]; n=133, C=41; total=10, den=133.000 |
| 2x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.235 [0.194, 0.281]; n=1705, C=562; total=400, den=1705.000 | 0.199 [0.094, 0.372]; n=171, C=38; total=34, den=171.000 |
| 3x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.222 [0.124, 0.366]; n=162, C=67; total=36, den=162.000 | 0.280 [0.092, 0.563]; n=25, C=14; total=7, den=25.000 |
| 1x pressure_responses (per_minute) | bot vs icebow-like humans | 0.327 [0.298, 0.357]; n=775, C=775; total=472, den=1441.338 | 0.123 [0.048, 0.198]; n=41, C=41; total=10, den=81.517 |
| 2x pressure_responses (per_minute) | bot vs icebow-like humans | 0.409 [0.363, 0.454]; n=747, C=747; total=400, den=978.213 | 0.478 [0.310, 0.646]; n=40, C=40; total=34, den=71.116 |
| 3x pressure_responses (per_minute) | bot vs icebow-like humans | 0.320 [0.180, 0.461]; n=167, C=167; total=36, den=112.370 | 0.285 [0.066, 0.503]; n=31, C=31; total=7, den=24.604 |
| 1x pressure_windows (per_minute) | bot vs icebow-like humans | 1.885 [1.801, 1.969]; n=775, C=775; total=2717, den=1441.338 | 1.632 [1.383, 1.881]; n=41, C=41; total=133, den=81.517 |
| 2x pressure_windows (per_minute) | bot vs icebow-like humans | 1.845 [1.724, 1.967]; n=747, C=747; total=1805, den=978.213 | 2.405 [2.005, 2.804]; n=40, C=40; total=171, den=71.116 |
| 3x pressure_windows (per_minute) | bot vs icebow-like humans | 1.691 [1.294, 2.087]; n=167, C=167; total=190, den=112.370 | 1.057 [0.607, 1.506]; n=31, C=31; total=26, den=24.604 |
| 1x pull_centre (per_minute) | bot only | 0.760 [0.713, 0.807]; n=775, C=775; total=1095, den=1441.338 | unavailable |
| 2x pull_centre (per_minute) | bot only | 1.709 [1.601, 1.817]; n=747, C=747; total=1672, den=978.213 | unavailable |
| 3x pull_centre (per_minute) | bot only | 2.670 [2.236, 3.104]; n=167, C=167; total=300, den=112.370 | unavailable |
| 1x pull_inward_offset (mean) | bot only | 1.735 [1.616, 1.855]; n=2347, C=729; total=4072.88, den=2347.000 | unavailable |
| 2x pull_inward_offset (mean) | bot only | 1.553 [1.449, 1.657]; n=3639, C=691; total=5650.62, den=3639.000 | unavailable |
| 3x pull_inward_offset (mean) | bot only | 1.412 [1.112, 1.712]; n=669, C=135; total=944.369, den=669.000 | unavailable |
| 1x pull_offset (mean) | bot only | 2.570 [2.481, 2.659]; n=2347, C=729; total=6032.13, den=2347.000 | unavailable |
| 2x pull_offset (mean) | bot only | 2.576 [2.501, 2.650]; n=3639, C=691; total=9372.99, den=3639.000 | unavailable |
| 3x pull_offset (mean) | bot only | 2.618 [2.415, 2.822]; n=669, C=135; total=1751.72, den=669.000 | unavailable |
| 1x pull_placements (per_minute) | bot only | 1.628 [1.564, 1.693]; n=775, C=775; total=2347, den=1441.338 | unavailable |
| 2x pull_placements (per_minute) | bot only | 3.720 [3.566, 3.874]; n=747, C=747; total=3639, den=978.213 | unavailable |
| 3x pull_placements (per_minute) | bot only | 5.954 [5.397, 6.510]; n=167, C=167; total=669, den=112.370 | unavailable |
| 1x pull_side (per_minute) | bot only | 0.869 [0.821, 0.917]; n=775, C=775; total=1252, den=1441.338 | unavailable |
| 2x pull_side (per_minute) | bot only | 2.011 [1.911, 2.111]; n=747, C=747; total=1967, den=978.213 | unavailable |
| 3x pull_side (per_minute) | bot only | 3.284 [2.921, 3.647]; n=167, C=167; total=369, den=112.370 | unavailable |
| 1x tank_complete (per_minute) | bot only | 0.518 [0.472, 0.565]; n=775, C=775; total=747, den=1441.338 | unavailable |
| 2x tank_complete (per_minute) | bot only | 0.663 [0.585, 0.742]; n=747, C=747; total=649, den=978.213 | unavailable |
| 3x tank_complete (per_minute) | bot only | 0.756 [0.543, 0.970]; n=167, C=167; total=85, den=112.370 | unavailable |
| 1x tank_crossings (per_minute) | bot only | 0.670 [0.615, 0.726]; n=775, C=775; total=966, den=1441.338 | unavailable |
| 2x tank_crossings (per_minute) | bot only | 1.036 [0.935, 1.136]; n=747, C=747; total=1013, den=978.213 | unavailable |
| 3x tank_crossings (per_minute) | bot only | 1.344 [1.039, 1.648]; n=167, C=167; total=151, den=112.370 | unavailable |
| 1x tank_preexisting_tesla (fraction) | bot only | 0.382 [0.331, 0.436]; n=966, C=436; total=369, den=966.000 | unavailable |
| 2x tank_preexisting_tesla (fraction) | bot only | 0.484 [0.422, 0.546]; n=1013, C=367; total=490, den=1013.000 | unavailable |
| 3x tank_preexisting_tesla (fraction) | bot only | 0.576 [0.434, 0.706]; n=151, C=62; total=87, den=151.000 | unavailable |
| 1x tank_tesla_delay (mean) | bot only | 7.533 [5.910, 9.156]; n=118, C=92; total=888.9, den=118.000 | unavailable |
| 2x tank_tesla_delay (mean) | bot only | 7.335 [6.441, 8.229]; n=282, C=174; total=2068.4, den=282.000 | unavailable |
| 3x tank_tesla_delay (mean) | bot only | 5.972 [4.664, 7.279]; n=57, C=34; total=340.4, den=57.000 | unavailable |
| 1x tank_tesla_response (per_minute) | bot only | 0.082 [0.062, 0.101]; n=775, C=775; total=118, den=1441.338 | unavailable |
| 2x tank_tesla_response (per_minute) | bot only | 0.288 [0.243, 0.333]; n=747, C=747; total=282, den=978.213 | unavailable |
| 3x tank_tesla_response (per_minute) | bot only | 0.507 [0.338, 0.676]; n=167, C=167; total=57, den=112.370 | unavailable |
| 1x tank_tesla_survival (fraction) | bot only | 0.495 [0.378, 0.613]; n=97, C=82; total=48, den=97.000 | unavailable |
| 2x tank_tesla_survival (fraction) | bot only | 0.610 [0.508, 0.703]; n=205, C=125; total=125, den=205.000 | unavailable |
| 3x tank_tesla_survival (fraction) | bot only | 0.743 [0.536, 0.899]; n=35, C=28; total=26, den=35.000 | unavailable |
| 1x xbow.Balloon (per_minute) | bot vs icebow-like humans | 0.716 [0.588, 0.845]; n=35, C=35; total=47, den=65.608 | 0.500 [0.000, 1.480]; n=2, C=2; total=2, den=4.000 |
| 2x xbow.Balloon (per_minute) | bot vs icebow-like humans | 1.317 [1.092, 1.542]; n=35, C=35; total=60, den=45.550 | 2.250 [1.760, 2.740]; n=2, C=2; total=9, den=4.000 |
| 3x xbow.Balloon (per_minute) | bot vs icebow-like humans | 1.146 [0.231, 2.060]; n=10, C=10; total=9, den=7.856 | 2.460 [1.351, 3.570]; n=2, C=2; total=4, den=1.626 |
| 1x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 0.556 [0.392, 0.720]; n=24, C=24; total=24, den=43.178 | 0.750 [0.260, 1.240]; n=2, C=2; total=3, den=4.000 |
| 2x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 1.049 [0.766, 1.333]; n=22, C=22; total=29, den=27.633 | 0.750 [0.260, 1.240]; n=2, C=2; total=3, den=4.000 |
| 3x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 1.538 [0.059, 3.017]; n=4, C=4; total=4, den=2.601 | 1.000 [0.000, 2.960]; n=2, C=2; total=2, den=2.000 |
| 1x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 0.991 [0.874, 1.107]; n=28, C=28; total=52, den=52.488 | 0.833 [0.000, 1.698]; n=3, C=3; total=5, den=6.000 |
| 2x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 1.068 [0.850, 1.287]; n=28, C=28; total=39, den=36.508 | 1.333 [1.007, 1.660]; n=3, C=3; total=8, den=6.000 |
| 3x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 1.228]; n=5, C=5; total=0, den=3.005 | 0.000 [0.000, 1.821]; n=3, C=3; total=0, den=2.026 |
| 1x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 0.812 [0.713, 0.911]; n=68, C=68; total=103, den=126.839 | unavailable |
| 2x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 1.123 [0.956, 1.290]; n=65, C=65; total=88, den=78.340 | unavailable |
| 3x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 0.915 [0.312, 1.518]; n=11, C=11; total=6, den=6.558 | unavailable |
| 1x xbow.Giant (per_minute) | bot vs icebow-like humans | 0.749 [0.565, 0.932]; n=17, C=17; total=23, den=30.727 | 0.667 [0.000, 1.531]; n=3, C=3; total=4, den=6.000 |
| 2x xbow.Giant (per_minute) | bot vs icebow-like humans | 1.556 [1.148, 1.964]; n=15, C=15; total=28, den=17.999 | 1.570 [0.961, 2.179]; n=3, C=3; total=7, den=4.459 |
| 3x xbow.Giant (per_minute) | bot vs icebow-like humans | 0.621 [0.000, 2.133]; n=2, C=2; total=1, den=1.610 | 0.895 [0.526, 1.264]; n=2, C=2; total=1, den=1.117 |
| 1x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 0.754 [0.658, 0.849]; n=73, C=73; total=103, den=136.609 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 1.369 [1.242, 1.495]; n=71, C=71; total=130, den=94.989 | 2.500 [95% CI not estimable]; n=1, C=1; total=5, den=2.000 |
| 3x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 0.929 [0.335, 1.523]; n=13, C=13; total=9, den=9.692 | 2.000 [95% CI not estimable]; n=1, C=1; total=2, den=1.000 |
| 1x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | 0.933 [0.672, 1.195]; n=12, C=12; total=21, den=22.497 | 0.750 [0.260, 1.240]; n=2, C=2; total=3, den=4.000 |
| 2x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | 1.891 [1.470, 2.311]; n=12, C=12; total=26, den=13.752 | 1.750 [1.260, 2.240]; n=2, C=2; total=7, den=4.000 |
| 3x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | 1.471 [0.000, 3.488]; n=2, C=2; total=2, den=1.360 |
| 1x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 0.856 [0.708, 1.004]; n=30, C=30; total=48, den=56.085 | 0.750 [0.260, 1.240]; n=2, C=2; total=3, den=4.000 |
| 2x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 1.190 [0.955, 1.424]; n=29, C=29; total=42, den=35.302 | 0.650 [0.267, 1.033]; n=2, C=2; total=2, den=3.076 |
| 3x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 1.218]; n=5, C=5; total=0, den=3.028 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.934 |
| 1x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | 0.533 [95% CI not estimable]; n=1, C=1; total=1, den=1.875 | unavailable |
| 2x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | 0.946 [95% CI not estimable]; n=1, C=1; total=1, den=1.057 | unavailable |
| 3x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | 0.533 [95% CI not estimable]; n=1, C=1; total=1, den=1.875 | unavailable |
| 2x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | 1.934 [95% CI not estimable]; n=1, C=1; total=2, den=1.034 | unavailable |
| 3x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Golem (per_minute) | bot vs icebow-like humans | 0.948 [0.825, 1.072]; n=42, C=42; total=73, den=76.969 | unavailable |
| 2x xbow.Golem (per_minute) | bot vs icebow-like humans | 0.939 [0.779, 1.099]; n=39, C=39; total=42, den=44.730 | unavailable |
| 3x xbow.Golem (per_minute) | bot vs icebow-like humans | 0.746 [0.365, 1.126]; n=5, C=5; total=2, den=2.682 | unavailable |
| 1x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 0.854 [0.706, 1.001]; n=25, C=25; total=40, den=46.866 | 0.833 [0.507, 1.160]; n=3, C=3; total=5, den=6.000 |
| 2x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 1.375 [1.139, 1.611]; n=25, C=25; total=50, den=36.367 | 1.667 [0.489, 2.844]; n=3, C=3; total=10, den=6.000 |
| 3x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 1.312 [0.568, 2.057]; n=9, C=9; total=7, den=5.333 | 0.000 [0.000, 2.586]; n=3, C=3; total=0, den=1.427 |
| 1x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.689 [0.605, 0.773]; n=104, C=104; total=134, den=194.559 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=2.000 |
| 2x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 1.138 [1.007, 1.269]; n=103, C=103; total=169, den=148.506 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=2.000 |
| 3x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.462 [0.178, 0.745]; n=34, C=34; total=11, den=23.830 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.951 |
| 1x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 0.960 [0.848, 1.072]; n=18, C=18; total=32, den=33.328 | unavailable |
| 2x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 1.151 [0.892, 1.409]; n=16, C=16; total=19, den=16.514 | unavailable |
| 3x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 1.000 [95% CI not estimable]; n=1, C=1; total=1, den=1.000 | unavailable |
| 1x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 0.595 [0.449, 0.741]; n=26, C=26; total=29, den=48.741 | unavailable |
| 2x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 1.254 [1.036, 1.473]; n=26, C=26; total=47, den=37.468 | unavailable |
| 3x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 1.408 [0.709, 2.108]; n=8, C=8; total=5, den=3.550 | unavailable |
| 1x xbow.Miner (per_minute) | bot vs icebow-like humans | 0.828 [0.671, 0.986]; n=17, C=17; total=26, den=31.392 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Miner (per_minute) | bot vs icebow-like humans | 1.486 [1.253, 1.719]; n=16, C=16; total=33, den=22.209 | 2.500 [95% CI not estimable]; n=1, C=1; total=5, den=2.000 |
| 3x xbow.Miner (per_minute) | bot vs icebow-like humans | 0.589 [0.039, 1.139]; n=4, C=4; total=2, den=3.394 | 1.737 [95% CI not estimable]; n=1, C=1; total=1, den=0.576 |
| 1x xbow.Mortar (per_minute) | bot vs icebow-like humans | 0.660 [0.532, 0.787]; n=38, C=38; total=47, den=71.231 | 0.375 [0.000, 0.844]; n=4, C=4; total=3, den=8.000 |
| 2x xbow.Mortar (per_minute) | bot vs icebow-like humans | 1.337 [1.147, 1.526]; n=38, C=38; total=68, den=50.876 | 0.983 [0.447, 1.520]; n=4, C=4; total=6, den=6.102 |
| 3x xbow.Mortar (per_minute) | bot vs icebow-like humans | 0.526 [0.100, 0.953]; n=8, C=8; total=3, den=5.698 | 1.000 [0.000, 2.960]; n=2, C=2; total=2, den=2.000 |
| 1x xbow.Other (per_minute) | bot vs icebow-like humans | 0.806 [0.683, 0.929]; n=47, C=47; total=70, den=86.856 | 1.000 [0.020, 1.980]; n=2, C=2; total=4, den=4.000 |
| 2x xbow.Other (per_minute) | bot vs icebow-like humans | 1.245 [1.088, 1.403]; n=44, C=44; total=71, den=57.009 | 1.200 [0.494, 1.906]; n=2, C=2; total=4, den=3.334 |
| 3x xbow.Other (per_minute) | bot vs icebow-like humans | 1.586 [0.808, 2.364]; n=9, C=9; total=12, den=7.567 | 1.000 [95% CI not estimable]; n=1, C=1; total=1, den=1.000 |
| 1x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 0.973 [0.625, 1.321]; n=10, C=10; total=18, den=18.502 | unavailable |
| 2x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 1.371 [0.748, 1.995]; n=8, C=8; total=12, den=8.751 | unavailable |
| 3x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 2.913 [95% CI not estimable]; n=1, C=1; total=1, den=0.343 | unavailable |
| 1x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 0.622 [0.473, 0.772]; n=24, C=24; total=28, den=44.985 | 1.000 [95% CI not estimable]; n=1, C=1; total=2, den=2.000 |
| 2x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 1.102 [0.819, 1.384]; n=24, C=24; total=36, den=32.679 | 2.500 [95% CI not estimable]; n=1, C=1; total=5, den=2.000 |
| 3x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 0.924 [0.000, 2.466]; n=4, C=4; total=2, den=2.164 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 |
| 1x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 0.800 [0.628, 0.972]; n=30, C=30; total=45, den=56.236 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=2.000 |
| 2x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 1.358 [1.101, 1.615]; n=30, C=30; total=58, den=42.712 | 2.000 [95% CI not estimable]; n=1, C=1; total=4, den=2.000 |
| 3x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 0.318 [0.000, 0.784]; n=10, C=10; total=2, den=6.290 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.976 |
| 1x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 0.750 [0.647, 0.853]; n=37, C=37; total=52, den=69.359 | 0.812 [0.555, 1.070]; n=8, C=8; total=13, den=16.000 |
| 2x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 1.461 [1.293, 1.630]; n=37, C=37; total=67, den=45.844 | 1.153 [0.450, 1.855]; n=8, C=8; total=14, den=12.145 |
| 3x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 1.557 [0.854, 2.260]; n=6, C=6; total=7, den=4.496 | 1.675 [0.666, 2.684]; n=4, C=4; total=5, den=2.985 |
| 1x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | 0.800 [0.277, 1.323]; n=2, C=2; total=3, den=3.749 | 1.000 [1.000, 1.000]; n=3, C=3; total=6, den=6.000 |
| 2x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | 1.749 [0.890, 2.609]; n=2, C=2; total=4, den=2.287 | 1.833 [1.507, 2.160]; n=3, C=3; total=11, den=6.000 |
| 3x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | 1.717 [95% CI not estimable]; n=1, C=1; total=1, den=0.583 | 1.834 [0.000, 4.191]; n=3, C=3; total=5, den=2.726 |
| 1x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 0.349 [0.051, 0.648]; n=13, C=13; total=8, den=22.898 | unavailable |
| 2x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 1.043 [0.682, 1.403]; n=11, C=11; total=15, den=14.387 | unavailable |
| 3x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 1.014 [0.000, 2.163]; n=3, C=3; total=3, den=2.958 | unavailable |
| 1x xbow.Sparky (per_minute) | bot vs icebow-like humans | 0.772 [0.459, 1.085]; n=7, C=7; total=10, den=12.953 | unavailable |
| 2x xbow.Sparky (per_minute) | bot vs icebow-like humans | 1.621 [1.078, 2.164]; n=5, C=5; total=9, den=5.552 | unavailable |
| 3x xbow.Sparky (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 0.764 [0.610, 0.918]; n=12, C=12; total=17, den=22.259 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 2x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 1.538 [1.161, 1.915]; n=11, C=11; total=23, den=14.953 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 3x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 0.984 [0.399, 1.570]; n=4, C=4; total=2, den=2.032 | 3.330 [95% CI not estimable]; n=1, C=1; total=3, den=0.901 |
| 1x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 0.524 [0.345, 0.702]; n=24, C=24; total=23, den=43.928 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.517 |
| 2x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 1.390 [1.210, 1.570]; n=23, C=23; total=45, den=32.377 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 1.039 [0.057, 2.021]; n=7, C=7; total=4, den=3.849 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.X-Bow (per_minute) | bot vs icebow-like humans | 1.013 [0.826, 1.201]; n=10, C=10; total=19, den=18.747 | unavailable |
| 2x xbow.X-Bow (per_minute) | bot vs icebow-like humans | 1.325 [0.934, 1.716]; n=10, C=10; total=17, den=12.828 | unavailable |
| 3x xbow.X-Bow (per_minute) | bot vs icebow-like humans | 0.798 [0.167, 1.429]; n=2, C=2; total=1, den=1.252 | unavailable |
| 1x xbow_damage.Balloon (mean) | bot only | 1545.425 [1188.046, 1902.804]; n=40, C=29; total=61817, den=40.000 | unavailable |
| 2x xbow_damage.Balloon (mean) | bot only | 942.325 [657.025, 1227.625]; n=40, C=27; total=37693, den=40.000 | unavailable |
| 3x xbow_damage.Balloon (mean) | bot only | 898.375 [65.415, 1731.335]; n=8, C=5; total=7187, den=8.000 | unavailable |
| 1x xbow_damage.Battle Ram (mean) | bot only | 1865.778 [1303.557, 2427.999]; n=18, C=15; total=33584, den=18.000 | unavailable |
| 2x xbow_damage.Battle Ram (mean) | bot only | 1026.524 [365.816, 1687.232]; n=21, C=13; total=21557, den=21.000 | unavailable |
| 3x xbow_damage.Battle Ram (mean) | bot only | 544.500 [0.000, 1611.720]; n=2, C=2; total=1089, den=2.000 | unavailable |
| 1x xbow_damage.Electro Giant (mean) | bot only | 1479.116 [1031.330, 1926.903]; n=43, C=26; total=63602, den=43.000 | unavailable |
| 2x xbow_damage.Electro Giant (mean) | bot only | 901.586 [291.529, 1511.644]; n=29, C=20; total=26146, den=29.000 | unavailable |
| 3x xbow_damage.Electro Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Elixir Golem (mean) | bot only | 1781.516 [1492.281, 2070.752]; n=91, C=60; total=162118, den=91.000 | unavailable |
| 2x xbow_damage.Elixir Golem (mean) | bot only | 1244.930 [895.220, 1594.639]; n=71, C=46; total=88390, den=71.000 | unavailable |
| 3x xbow_damage.Elixir Golem (mean) | bot only | 1294.500 [183.078, 2405.922]; n=6, C=5; total=7767, den=6.000 | unavailable |
| 1x xbow_damage.Giant (mean) | bot only | 1720.850 [1125.395, 2316.305]; n=20, C=14; total=34417, den=20.000 | unavailable |
| 2x xbow_damage.Giant (mean) | bot only | 883.100 [391.336, 1374.864]; n=20, C=11; total=17662, den=20.000 | unavailable |
| 3x xbow_damage.Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Barrel (mean) | bot only | 1059.280 [794.931, 1323.630]; n=82, C=56; total=86861, den=82.000 | unavailable |
| 2x xbow_damage.Goblin Barrel (mean) | bot only | 945.310 [651.421, 1239.200]; n=87, C=52; total=82242, den=87.000 | unavailable |
| 3x xbow_damage.Goblin Barrel (mean) | bot only | 1333.000 [233.534, 2432.466]; n=4, C=4; total=5332, den=4.000 | unavailable |
| 1x xbow_damage.Goblin Drill (mean) | bot only | 1256.526 [781.058, 1731.995]; n=19, C=10; total=23874, den=19.000 | unavailable |
| 2x xbow_damage.Goblin Drill (mean) | bot only | 515.875 [180.861, 850.889]; n=16, C=10; total=8254, den=16.000 | unavailable |
| 3x xbow_damage.Goblin Drill (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Giant (mean) | bot only | 1961.000 [1560.581, 2361.419]; n=43, C=26; total=84323, den=43.000 | unavailable |
| 2x xbow_damage.Goblin Giant (mean) | bot only | 844.143 [461.706, 1226.580]; n=28, C=18; total=23636, den=28.000 | unavailable |
| 3x xbow_damage.Goblin Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Machine (mean) | bot only | 3615.000 [95% CI not estimable]; n=1, C=1; total=3615, den=1.000 | unavailable |
| 2x xbow_damage.Goblin Machine (mean) | bot only | 75.000 [95% CI not estimable]; n=1, C=1; total=75, den=1.000 | unavailable |
| 3x xbow_damage.Goblin Machine (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Goblinstein (mean) | bot only | 25.500 [95% CI not estimable]; n=2, C=1; total=51, den=2.000 | unavailable |
| 3x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Golem (mean) | bot only | 2145.493 [1833.634, 2457.352]; n=69, C=39; total=148039, den=69.000 | unavailable |
| 2x xbow_damage.Golem (mean) | bot only | 1141.312 [667.003, 1615.622]; n=32, C=28; total=36522, den=32.000 | unavailable |
| 3x xbow_damage.Golem (mean) | bot only | 51.000 [95% CI not estimable]; n=1, C=1; total=51, den=1.000 | unavailable |
| 1x xbow_damage.Graveyard (mean) | bot only | 1632.057 [1192.540, 2071.574]; n=35, C=23; total=57122, den=35.000 | unavailable |
| 2x xbow_damage.Graveyard (mean) | bot only | 953.306 [642.872, 1263.739]; n=36, C=23; total=34319, den=36.000 | unavailable |
| 3x xbow_damage.Graveyard (mean) | bot only | 17.000 [0.000, 50.320]; n=3, C=3; total=51, den=3.000 | unavailable |
| 1x xbow_damage.Hog Rider (mean) | bot only | 1216.021 [959.874, 1472.168]; n=95, C=68; total=115522, den=95.000 | unavailable |
| 2x xbow_damage.Hog Rider (mean) | bot only | 912.768 [713.594, 1111.942]; n=125, C=73; total=114096, den=125.000 | unavailable |
| 3x xbow_damage.Hog Rider (mean) | bot only | 1011.714 [14.148, 2009.281]; n=7, C=7; total=7082, den=7.000 | unavailable |
| 1x xbow_damage.Lava Hound (mean) | bot only | 2092.556 [1595.963, 2589.148]; n=27, C=18; total=56499, den=27.000 | unavailable |
| 2x xbow_damage.Lava Hound (mean) | bot only | 1297.375 [664.824, 1929.926]; n=16, C=11; total=20758, den=16.000 | unavailable |
| 3x xbow_damage.Lava Hound (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Mega Knight (mean) | bot only | 1409.680 [903.239, 1916.121]; n=25, C=20; total=35242, den=25.000 | unavailable |
| 2x xbow_damage.Mega Knight (mean) | bot only | 804.265 [424.400, 1184.130]; n=34, C=21; total=27345, den=34.000 | unavailable |
| 3x xbow_damage.Mega Knight (mean) | bot only | 216.000 [0.000, 539.400]; n=2, C=2; total=432, den=2.000 | unavailable |
| 1x xbow_damage.Miner (mean) | bot only | 1445.250 [1069.036, 1821.464]; n=20, C=13; total=28905, den=20.000 | unavailable |
| 2x xbow_damage.Miner (mean) | bot only | 1056.833 [514.435, 1599.231]; n=24, C=15; total=25364, den=24.000 | unavailable |
| 3x xbow_damage.Miner (mean) | bot only | 880.000 [129.320, 1630.680]; n=2, C=2; total=1760, den=2.000 | unavailable |
| 1x xbow_damage.Mortar (mean) | bot only | 1776.943 [1272.586, 2281.300]; n=35, C=28; total=62193, den=35.000 | unavailable |
| 2x xbow_damage.Mortar (mean) | bot only | 1093.152 [677.571, 1508.733]; n=46, C=29; total=50285, den=46.000 | unavailable |
| 3x xbow_damage.Mortar (mean) | bot only | 1206.000 [12.360, 2399.640]; n=2, C=2; total=2412, den=2.000 | unavailable |
| 1x xbow_damage.Other (mean) | bot only | 1327.315 [881.318, 1773.312]; n=54, C=35; total=71675, den=54.000 | unavailable |
| 2x xbow_damage.Other (mean) | bot only | 1041.811 [640.547, 1443.075]; n=53, C=35; total=55216, den=53.000 | unavailable |
| 3x xbow_damage.Other (mean) | bot only | 198.286 [4.673, 391.898]; n=7, C=5; total=1388, den=7.000 | unavailable |
| 1x xbow_damage.P.E.K.K.A (mean) | bot only | 1166.692 [524.584, 1808.801]; n=13, C=7; total=15167, den=13.000 | unavailable |
| 2x xbow_damage.P.E.K.K.A (mean) | bot only | 1192.333 [554.976, 1829.691]; n=9, C=5; total=10731, den=9.000 | unavailable |
| 3x xbow_damage.P.E.K.K.A (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Ram Rider (mean) | bot only | 1661.261 [1067.933, 2254.589]; n=23, C=17; total=38209, den=23.000 | unavailable |
| 2x xbow_damage.Ram Rider (mean) | bot only | 1303.333 [799.040, 1807.627]; n=21, C=14; total=27370, den=21.000 | unavailable |
| 3x xbow_damage.Ram Rider (mean) | bot only | 323.000 [95% CI not estimable]; n=1, C=1; total=323, den=1.000 | unavailable |
| 1x xbow_damage.Royal Giant (mean) | bot only | 1430.053 [1026.055, 1834.050]; n=38, C=23; total=54342, den=38.000 | unavailable |
| 2x xbow_damage.Royal Giant (mean) | bot only | 1133.022 [788.060, 1477.983]; n=46, C=26; total=52119, den=46.000 | unavailable |
| 3x xbow_damage.Royal Giant (mean) | bot only | 1608.000 [95% CI not estimable]; n=1, C=1; total=1608, den=1.000 | unavailable |
| 1x xbow_damage.Royal Hogs (mean) | bot only | 1236.333 [791.583, 1681.084]; n=36, C=27; total=44508, den=36.000 | unavailable |
| 2x xbow_damage.Royal Hogs (mean) | bot only | 1096.000 [767.396, 1424.604]; n=44, C=27; total=48224, den=44.000 | unavailable |
| 3x xbow_damage.Royal Hogs (mean) | bot only | 583.667 [0.000, 1240.982]; n=3, C=3; total=1751, den=3.000 | unavailable |
| 1x xbow_damage.Rune Giant (mean) | bot only | 1838.500 [0.000, 5342.000]; n=2, C=2; total=3677, den=2.000 | unavailable |
| 2x xbow_damage.Rune Giant (mean) | bot only | 224.250 [95% CI not estimable]; n=4, C=1; total=897, den=4.000 | unavailable |
| 3x xbow_damage.Rune Giant (mean) | bot only | 51.000 [95% CI not estimable]; n=1, C=1; total=51, den=1.000 | unavailable |
| 1x xbow_damage.Skeleton Barrel (mean) | bot only | 1430.200 [779.347, 2081.053]; n=5, C=3; total=7151, den=5.000 | unavailable |
| 2x xbow_damage.Skeleton Barrel (mean) | bot only | 1621.700 [561.179, 2682.221]; n=10, C=7; total=16217, den=10.000 | unavailable |
| 3x xbow_damage.Skeleton Barrel (mean) | bot only | 812.000 [290.640, 1333.360]; n=2, C=2; total=1624, den=2.000 | unavailable |
| 1x xbow_damage.Sparky (mean) | bot only | 1515.556 [659.818, 2371.293]; n=9, C=7; total=13640, den=9.000 | unavailable |
| 2x xbow_damage.Sparky (mean) | bot only | 1359.833 [0.000, 2974.970]; n=6, C=5; total=8159, den=6.000 | unavailable |
| 3x xbow_damage.Sparky (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Three Musketeers (mean) | bot only | 1832.941 [1277.184, 2388.699]; n=17, C=12; total=31160, den=17.000 | unavailable |
| 2x xbow_damage.Three Musketeers (mean) | bot only | 600.056 [7.329, 1192.782]; n=18, C=7; total=10801, den=18.000 | unavailable |
| 3x xbow_damage.Three Musketeers (mean) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 1x xbow_damage.Wall Breakers (mean) | bot only | 1422.722 [865.284, 1980.161]; n=18, C=13; total=25609, den=18.000 | unavailable |
| 2x xbow_damage.Wall Breakers (mean) | bot only | 1244.294 [764.495, 1724.093]; n=34, C=21; total=42306, den=34.000 | unavailable |
| 3x xbow_damage.Wall Breakers (mean) | bot only | 36.000 [0.000, 106.560]; n=2, C=2; total=72, den=2.000 | unavailable |
| 1x xbow_damage.X-Bow (mean) | bot only | 1539.125 [1062.132, 2016.118]; n=16, C=10; total=24626, den=16.000 | unavailable |
| 2x xbow_damage.X-Bow (mean) | bot only | 918.714 [202.479, 1634.949]; n=14, C=7; total=12862, den=14.000 | unavailable |
| 3x xbow_damage.X-Bow (mean) | bot only | 445.000 [95% CI not estimable]; n=1, C=1; total=445, den=1.000 | unavailable |
| 1x xbow_full.Balloon (per_minute) | bot only | 0.610 [0.480, 0.739]; n=35, C=35; total=40, den=65.608 | unavailable |
| 2x xbow_full.Balloon (per_minute) | bot only | 0.878 [0.691, 1.065]; n=35, C=35; total=40, den=45.550 | unavailable |
| 3x xbow_full.Balloon (per_minute) | bot only | 1.018 [0.301, 1.736]; n=10, C=10; total=8, den=7.856 | unavailable |
| 1x xbow_full.Battle Ram (per_minute) | bot only | 0.417 [0.267, 0.567]; n=24, C=24; total=18, den=43.178 | unavailable |
| 2x xbow_full.Battle Ram (per_minute) | bot only | 0.760 [0.454, 1.066]; n=22, C=22; total=21, den=27.633 | unavailable |
| 3x xbow_full.Battle Ram (per_minute) | bot only | 0.769 [0.359, 1.179]; n=4, C=4; total=2, den=2.601 | unavailable |
| 1x xbow_full.Electro Giant (per_minute) | bot only | 0.819 [0.672, 0.966]; n=28, C=28; total=43, den=52.488 | unavailable |
| 2x xbow_full.Electro Giant (per_minute) | bot only | 0.794 [0.544, 1.045]; n=28, C=28; total=29, den=36.508 | unavailable |
| 3x xbow_full.Electro Giant (per_minute) | bot only | 0.000 [0.000, 1.228]; n=5, C=5; total=0, den=3.005 | unavailable |
| 1x xbow_full.Elixir Golem (per_minute) | bot only | 0.717 [0.621, 0.814]; n=68, C=68; total=91, den=126.839 | unavailable |
| 2x xbow_full.Elixir Golem (per_minute) | bot only | 0.906 [0.739, 1.073]; n=65, C=65; total=71, den=78.340 | unavailable |
| 3x xbow_full.Elixir Golem (per_minute) | bot only | 0.915 [0.312, 1.518]; n=11, C=11; total=6, den=6.558 | unavailable |
| 1x xbow_full.Giant (per_minute) | bot only | 0.651 [0.460, 0.842]; n=17, C=17; total=20, den=30.727 | unavailable |
| 2x xbow_full.Giant (per_minute) | bot only | 1.111 [0.694, 1.528]; n=15, C=15; total=20, den=17.999 | unavailable |
| 3x xbow_full.Giant (per_minute) | bot only | 0.000 [0.000, 2.291]; n=2, C=2; total=0, den=1.610 | unavailable |
| 1x xbow_full.Goblin Barrel (per_minute) | bot only | 0.600 [0.504, 0.696]; n=73, C=73; total=82, den=136.609 | unavailable |
| 2x xbow_full.Goblin Barrel (per_minute) | bot only | 0.916 [0.760, 1.071]; n=71, C=71; total=87, den=94.989 | unavailable |
| 3x xbow_full.Goblin Barrel (per_minute) | bot only | 0.413 [0.082, 0.743]; n=13, C=13; total=4, den=9.692 | unavailable |
| 1x xbow_full.Goblin Drill (per_minute) | bot only | 0.845 [0.573, 1.116]; n=12, C=12; total=19, den=22.497 | unavailable |
| 2x xbow_full.Goblin Drill (per_minute) | bot only | 1.163 [0.859, 1.468]; n=12, C=12; total=16, den=13.752 | unavailable |
| 3x xbow_full.Goblin Drill (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 1x xbow_full.Goblin Giant (per_minute) | bot only | 0.767 [0.618, 0.915]; n=30, C=30; total=43, den=56.085 | unavailable |
| 2x xbow_full.Goblin Giant (per_minute) | bot only | 0.793 [0.560, 1.026]; n=29, C=29; total=28, den=35.302 | unavailable |
| 3x xbow_full.Goblin Giant (per_minute) | bot only | 0.000 [0.000, 1.218]; n=5, C=5; total=0, den=3.028 | unavailable |
| 1x xbow_full.Goblin Machine (per_minute) | bot only | 0.533 [95% CI not estimable]; n=1, C=1; total=1, den=1.875 | unavailable |
| 2x xbow_full.Goblin Machine (per_minute) | bot only | 0.946 [95% CI not estimable]; n=1, C=1; total=1, den=1.057 | unavailable |
| 3x xbow_full.Goblin Machine (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblinstein (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.875 | unavailable |
| 2x xbow_full.Goblinstein (per_minute) | bot only | 1.934 [95% CI not estimable]; n=1, C=1; total=2, den=1.034 | unavailable |
| 3x xbow_full.Goblinstein (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Golem (per_minute) | bot only | 0.896 [0.768, 1.025]; n=42, C=42; total=69, den=76.969 | unavailable |
| 2x xbow_full.Golem (per_minute) | bot only | 0.715 [0.582, 0.849]; n=39, C=39; total=32, den=44.730 | unavailable |
| 3x xbow_full.Golem (per_minute) | bot only | 0.373 [0.000, 0.981]; n=5, C=5; total=1, den=2.682 | unavailable |
| 1x xbow_full.Graveyard (per_minute) | bot only | 0.747 [0.612, 0.882]; n=25, C=25; total=35, den=46.866 | unavailable |
| 2x xbow_full.Graveyard (per_minute) | bot only | 0.990 [0.788, 1.192]; n=25, C=25; total=36, den=36.367 | unavailable |
| 3x xbow_full.Graveyard (per_minute) | bot only | 0.562 [0.142, 0.983]; n=9, C=9; total=3, den=5.333 | unavailable |
| 1x xbow_full.Hog Rider (per_minute) | bot only | 0.488 [0.406, 0.570]; n=104, C=104; total=95, den=194.559 | unavailable |
| 2x xbow_full.Hog Rider (per_minute) | bot only | 0.842 [0.711, 0.972]; n=103, C=103; total=125, den=148.506 | unavailable |
| 3x xbow_full.Hog Rider (per_minute) | bot only | 0.294 [0.100, 0.487]; n=34, C=34; total=7, den=23.830 | unavailable |
| 1x xbow_full.Lava Hound (per_minute) | bot only | 0.810 [0.685, 0.935]; n=18, C=18; total=27, den=33.328 | unavailable |
| 2x xbow_full.Lava Hound (per_minute) | bot only | 0.969 [0.660, 1.278]; n=16, C=16; total=16, den=16.514 | unavailable |
| 3x xbow_full.Lava Hound (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 1x xbow_full.Mega Knight (per_minute) | bot only | 0.513 [0.377, 0.649]; n=26, C=26; total=25, den=48.741 | unavailable |
| 2x xbow_full.Mega Knight (per_minute) | bot only | 0.907 [0.688, 1.127]; n=26, C=26; total=34, den=37.468 | unavailable |
| 3x xbow_full.Mega Knight (per_minute) | bot only | 0.563 [0.000, 1.169]; n=8, C=8; total=2, den=3.550 | unavailable |
| 1x xbow_full.Miner (per_minute) | bot only | 0.637 [0.435, 0.839]; n=17, C=17; total=20, den=31.392 | unavailable |
| 2x xbow_full.Miner (per_minute) | bot only | 1.081 [0.872, 1.289]; n=16, C=16; total=24, den=22.209 | unavailable |
| 3x xbow_full.Miner (per_minute) | bot only | 0.589 [0.039, 1.139]; n=4, C=4; total=2, den=3.394 | unavailable |
| 1x xbow_full.Mortar (per_minute) | bot only | 0.491 [0.377, 0.606]; n=38, C=38; total=35, den=71.231 | unavailable |
| 2x xbow_full.Mortar (per_minute) | bot only | 0.904 [0.703, 1.105]; n=38, C=38; total=46, den=50.876 | unavailable |
| 3x xbow_full.Mortar (per_minute) | bot only | 0.351 [0.000, 0.756]; n=8, C=8; total=2, den=5.698 | unavailable |
| 1x xbow_full.Other (per_minute) | bot only | 0.622 [0.489, 0.754]; n=47, C=47; total=54, den=86.856 | unavailable |
| 2x xbow_full.Other (per_minute) | bot only | 0.930 [0.755, 1.105]; n=44, C=44; total=53, den=57.009 | unavailable |
| 3x xbow_full.Other (per_minute) | bot only | 0.925 [0.281, 1.570]; n=9, C=9; total=7, den=7.567 | unavailable |
| 1x xbow_full.P.E.K.K.A (per_minute) | bot only | 0.703 [0.346, 1.059]; n=10, C=10; total=13, den=18.502 | unavailable |
| 2x xbow_full.P.E.K.K.A (per_minute) | bot only | 1.028 [0.441, 1.616]; n=8, C=8; total=9, den=8.751 | unavailable |
| 3x xbow_full.P.E.K.K.A (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.343 | unavailable |
| 1x xbow_full.Ram Rider (per_minute) | bot only | 0.511 [0.351, 0.671]; n=24, C=24; total=23, den=44.985 | unavailable |
| 2x xbow_full.Ram Rider (per_minute) | bot only | 0.643 [0.381, 0.904]; n=24, C=24; total=21, den=32.679 | unavailable |
| 3x xbow_full.Ram Rider (per_minute) | bot only | 0.462 [0.000, 1.233]; n=4, C=4; total=1, den=2.164 | unavailable |
| 1x xbow_full.Royal Giant (per_minute) | bot only | 0.676 [0.510, 0.842]; n=30, C=30; total=38, den=56.236 | unavailable |
| 2x xbow_full.Royal Giant (per_minute) | bot only | 1.077 [0.847, 1.307]; n=30, C=30; total=46, den=42.712 | unavailable |
| 3x xbow_full.Royal Giant (per_minute) | bot only | 0.159 [0.000, 0.484]; n=10, C=10; total=1, den=6.290 | unavailable |
| 1x xbow_full.Royal Hogs (per_minute) | bot only | 0.519 [0.394, 0.644]; n=37, C=37; total=36, den=69.359 | unavailable |
| 2x xbow_full.Royal Hogs (per_minute) | bot only | 0.960 [0.732, 1.187]; n=37, C=37; total=44, den=45.844 | unavailable |
| 3x xbow_full.Royal Hogs (per_minute) | bot only | 0.667 [0.204, 1.130]; n=6, C=6; total=3, den=4.496 | unavailable |
| 1x xbow_full.Rune Giant (per_minute) | bot only | 0.533 [0.533, 0.534]; n=2, C=2; total=2, den=3.749 | unavailable |
| 2x xbow_full.Rune Giant (per_minute) | bot only | 1.749 [0.890, 2.609]; n=2, C=2; total=4, den=2.287 | unavailable |
| 3x xbow_full.Rune Giant (per_minute) | bot only | 1.717 [95% CI not estimable]; n=1, C=1; total=1, den=0.583 | unavailable |
| 1x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.218 [0.000, 0.452]; n=13, C=13; total=5, den=22.898 | unavailable |
| 2x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.695 [0.353, 1.037]; n=11, C=11; total=10, den=14.387 | unavailable |
| 3x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.676 [0.004, 1.349]; n=3, C=3; total=2, den=2.958 | unavailable |
| 1x xbow_full.Sparky (per_minute) | bot only | 0.695 [0.395, 0.995]; n=7, C=7; total=9, den=12.953 | unavailable |
| 2x xbow_full.Sparky (per_minute) | bot only | 1.081 [0.705, 1.456]; n=5, C=5; total=6, den=5.552 | unavailable |
| 3x xbow_full.Sparky (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Three Musketeers (per_minute) | bot only | 0.764 [0.610, 0.918]; n=12, C=12; total=17, den=22.259 | unavailable |
| 2x xbow_full.Three Musketeers (per_minute) | bot only | 1.204 [0.672, 1.736]; n=11, C=11; total=18, den=14.953 | unavailable |
| 3x xbow_full.Three Musketeers (per_minute) | bot only | 0.492 [0.000, 1.175]; n=4, C=4; total=1, den=2.032 | unavailable |
| 1x xbow_full.Wall Breakers (per_minute) | bot only | 0.410 [0.239, 0.580]; n=24, C=24; total=18, den=43.928 | unavailable |
| 2x xbow_full.Wall Breakers (per_minute) | bot only | 1.050 [0.820, 1.280]; n=23, C=23; total=34, den=32.377 | unavailable |
| 3x xbow_full.Wall Breakers (per_minute) | bot only | 0.520 [0.029, 1.011]; n=7, C=7; total=2, den=3.849 | unavailable |
| 1x xbow_full.X-Bow (per_minute) | bot only | 0.853 [0.683, 1.024]; n=10, C=10; total=16, den=18.747 | unavailable |
| 2x xbow_full.X-Bow (per_minute) | bot only | 1.091 [0.578, 1.605]; n=10, C=10; total=14, den=12.828 | unavailable |
| 3x xbow_full.X-Bow (per_minute) | bot only | 0.798 [0.167, 1.429]; n=2, C=2; total=1, den=1.252 | unavailable |

### Video outcomes: wins

Bot only unless the comparison column says bot vs icebow-like humans. Per-minute values use phase minutes except state/archetype rows, which use their own exposure. Means/fractions show event n and cluster C. Human column = icebow-like humans.

| Phase / metric (unit) | Comparison | Bot [95% CI] | Human [95% CI] |
|---|---|---|
| 1x clump_bodies (per_minute) | bot only | 0.249 [0.181, 0.317]; n=399, C=399; total=186, den=747.898 | unavailable |
| 2x clump_bodies (per_minute) | bot only | 0.616 [0.461, 0.771]; n=399, C=399; total=335, den=543.875 | unavailable |
| 3x clump_bodies (per_minute) | bot only | 1.675 [0.878, 2.473]; n=93, C=93; total=104, den=62.079 | unavailable |
| 1x clump_contacts (per_minute) | bot only | 0.420 [0.354, 0.486]; n=399, C=399; total=314, den=747.898 | unavailable |
| 2x clump_contacts (per_minute) | bot only | 0.848 [0.726, 0.969]; n=399, C=399; total=461, den=543.875 | unavailable |
| 3x clump_contacts (per_minute) | bot only | 1.401 [1.005, 1.798]; n=93, C=93; total=87, den=62.079 | unavailable |
| 1x clump_elixir (per_minute) | bot only | 0.293 [0.178, 0.409]; n=399, C=399; total=219.333, den=747.898 | unavailable |
| 2x clump_elixir (per_minute) | bot only | 1.014 [0.705, 1.322]; n=399, C=399; total=551.333, den=543.875 | unavailable |
| 3x clump_elixir (per_minute) | bot only | 3.071 [1.509, 4.634]; n=93, C=93; total=190.667, den=62.079 | unavailable |
| 1x clump_episodes (per_minute) | bot only | 0.088 [0.064, 0.113]; n=399, C=399; total=66, den=747.898 | unavailable |
| 2x clump_episodes (per_minute) | bot only | 0.210 [0.160, 0.259]; n=399, C=399; total=114, den=543.875 | unavailable |
| 3x clump_episodes (per_minute) | bot only | 0.580 [0.309, 0.851]; n=93, C=93; total=36, den=62.079 | unavailable |
| 1x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.005]; n=399, C=399; total=0, den=747.898 | unavailable |
| 2x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.007]; n=399, C=399; total=0, den=543.875 | unavailable |
| 3x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.059]; n=93, C=93; total=0, den=62.079 | unavailable |
| 1x commit.ahead (per_minute) | bot only | 1.230 [1.115, 1.346]; n=252, C=252; total=291, den=236.500 | unavailable |
| 2x commit.ahead (per_minute) | bot only | 2.744 [2.611, 2.877]; n=342, C=342; total=824, den=300.286 | unavailable |
| 3x commit.ahead (per_minute) | bot only | 4.828 [4.291, 5.365]; n=65, C=65; total=151, den=31.274 | unavailable |
| 1x commit.behind (per_minute) | bot only | 1.270 [1.092, 1.447]; n=124, C=124; total=135, den=106.306 | unavailable |
| 2x commit.behind (per_minute) | bot only | 3.140 [2.895, 3.384]; n=102, C=102; total=257, den=81.859 | unavailable |
| 3x commit.behind (per_minute) | bot only | 4.463 [3.699, 5.228]; n=20, C=20; total=46, den=10.306 | unavailable |
| 1x commit.level (per_minute) | bot only | 1.490 [1.395, 1.585]; n=368, C=368; total=592, den=397.387 | unavailable |
| 2x commit.level (per_minute) | bot only | 3.049 [2.838, 3.260]; n=225, C=225; total=442, den=144.958 | unavailable |
| 3x commit.level (per_minute) | bot only | 4.612 [4.164, 5.060]; n=44, C=44; total=83, den=17.997 | unavailable |
| 1x commit_damage.ahead (mean) | bot only | 281.917 [208.966, 354.867]; n=240, C=132; total=67660, den=240.000 | unavailable |
| 2x commit_damage.ahead (mean) | bot only | 173.353 [136.560, 210.146]; n=501, C=229; total=86850, den=501.000 | unavailable |
| 3x commit_damage.ahead (mean) | bot only | 198.082 [93.668, 302.496]; n=61, C=30; total=12083, den=61.000 | unavailable |
| 1x commit_damage.behind (mean) | bot only | 237.686 [146.089, 329.282]; n=121, C=84; total=28760, den=121.000 | unavailable |
| 2x commit_damage.behind (mean) | bot only | 227.218 [159.630, 294.805]; n=216, C=80; total=49079, den=216.000 | unavailable |
| 3x commit_damage.behind (mean) | bot only | 157.357 [39.680, 275.035]; n=28, C=13; total=4406, den=28.000 | unavailable |
| 1x commit_damage.level (mean) | bot only | 225.144 [174.251, 276.037]; n=513, C=298; total=115499, den=513.000 | unavailable |
| 2x commit_damage.level (mean) | bot only | 197.997 [148.544, 247.450]; n=347, C=150; total=68705, den=347.000 | unavailable |
| 3x commit_damage.level (mean) | bot only | 252.396 [94.960, 409.831]; n=48, C=18; total=12115, den=48.000 | unavailable |
| 1x commit_full.ahead (per_minute) | bot only | 1.015 [0.902, 1.128]; n=252, C=252; total=240, den=236.500 | unavailable |
| 2x commit_full.ahead (per_minute) | bot only | 1.668 [1.535, 1.802]; n=342, C=342; total=501, den=300.286 | unavailable |
| 3x commit_full.ahead (per_minute) | bot only | 1.950 [1.504, 2.397]; n=65, C=65; total=61, den=31.274 | unavailable |
| 1x commit_full.behind (per_minute) | bot only | 1.138 [0.966, 1.310]; n=124, C=124; total=121, den=106.306 | unavailable |
| 2x commit_full.behind (per_minute) | bot only | 2.639 [2.361, 2.916]; n=102, C=102; total=216, den=81.859 | unavailable |
| 3x commit_full.behind (per_minute) | bot only | 2.717 [2.055, 3.379]; n=20, C=20; total=28, den=10.306 | unavailable |
| 1x commit_full.level (per_minute) | bot only | 1.291 [1.197, 1.385]; n=368, C=368; total=513, den=397.387 | unavailable |
| 2x commit_full.level (per_minute) | bot only | 2.394 [2.166, 2.621]; n=225, C=225; total=347, den=144.958 | unavailable |
| 3x commit_full.level (per_minute) | bot only | 2.667 [2.146, 3.188]; n=44, C=44; total=48, den=17.997 | unavailable |
| 1x cycle_assessed (per_minute) | bot only | 1.332 [1.258, 1.405]; n=399, C=399; total=996, den=747.898 | unavailable |
| 2x cycle_assessed (per_minute) | bot only | 2.348 [2.233, 2.463]; n=399, C=399; total=1277, den=543.875 | unavailable |
| 3x cycle_assessed (per_minute) | bot only | 4.043 [3.654, 4.432]; n=93, C=93; total=251, den=62.079 | unavailable |
| 1x cycle_candidates (per_minute) | bot only | 1.428 [1.352, 1.504]; n=399, C=399; total=1068, den=747.898 | unavailable |
| 2x cycle_candidates (per_minute) | bot only | 2.686 [2.569, 2.803]; n=399, C=399; total=1461, den=543.875 | unavailable |
| 3x cycle_candidates (per_minute) | bot only | 4.816 [4.423, 5.209]; n=93, C=93; total=299, den=62.079 | unavailable |
| 1x cycle_elixir_at_play (mean) | bot only | 6.121 [5.712, 6.531]; n=127, C=113; total=777.391, den=127.000 | unavailable |
| 2x cycle_elixir_at_play (mean) | bot only | 4.914 [4.528, 5.300]; n=170, C=131; total=835.441, den=170.000 | unavailable |
| 3x cycle_elixir_at_play (mean) | bot only | 5.149 [4.484, 5.815]; n=28, C=25; total=144.179, den=28.000 | unavailable |
| 1x cycle_empty (per_minute) | bot only | 0.170 [0.142, 0.198]; n=399, C=399; total=127, den=747.898 | unavailable |
| 2x cycle_empty (per_minute) | bot only | 0.313 [0.265, 0.360]; n=399, C=399; total=170, den=543.875 | unavailable |
| 3x cycle_empty (per_minute) | bot only | 0.451 [0.303, 0.600]; n=93, C=93; total=28, den=62.079 | unavailable |
| 1x cycle_empty_elixir (per_minute) | bot only | 0.178 [0.147, 0.209]; n=399, C=399; total=133, den=747.898 | unavailable |
| 2x cycle_empty_elixir (per_minute) | bot only | 0.327 [0.276, 0.379]; n=399, C=399; total=178, den=543.875 | unavailable |
| 3x cycle_empty_elixir (per_minute) | bot only | 0.467 [0.311, 0.624]; n=93, C=93; total=29, den=62.079 | unavailable |
| 1x kill_assessed (per_minute) | bot only | 0.211 [0.171, 0.252]; n=399, C=399; total=158, den=747.898 | unavailable |
| 2x kill_assessed (per_minute) | bot only | 0.370 [0.302, 0.437]; n=399, C=399; total=201, den=543.875 | unavailable |
| 3x kill_assessed (per_minute) | bot only | 0.644 [0.402, 0.887]; n=93, C=93; total=40, den=62.079 | unavailable |
| 1x kill_pushes (per_minute) | bot only | 0.269 [0.220, 0.318]; n=399, C=399; total=201, den=747.898 | unavailable |
| 2x kill_pushes (per_minute) | bot only | 0.502 [0.422, 0.582]; n=399, C=399; total=273, den=543.875 | unavailable |
| 3x kill_pushes (per_minute) | bot only | 1.063 [0.748, 1.378]; n=93, C=93; total=66, den=62.079 | unavailable |
| 1x kill_supports_first (per_minute) | bot only | 0.108 [0.082, 0.134]; n=399, C=399; total=81, den=747.898 | unavailable |
| 2x kill_supports_first (per_minute) | bot only | 0.164 [0.124, 0.203]; n=399, C=399; total=89, den=543.875 | unavailable |
| 3x kill_supports_first (per_minute) | bot only | 0.370 [0.209, 0.532]; n=93, C=93; total=23, den=62.079 | unavailable |
| 1x kill_supports_first_fraction (fraction) | bot only | 0.513 [0.407, 0.617]; n=158, C=108; total=81, den=158.000 | unavailable |
| 2x kill_supports_first_fraction (fraction) | bot only | 0.443 [0.342, 0.549]; n=201, C=119; total=89, den=201.000 | unavailable |
| 3x kill_supports_first_fraction (fraction) | bot only | 0.575 [0.364, 0.762]; n=40, C=24; total=23, den=40.000 | unavailable |
| 1x pressure_complete (per_minute) | bot vs icebow-like humans | 1.851 [1.738, 1.963]; n=399, C=399; total=1384, den=747.898 | 1.600 [1.001, 2.199]; n=10, C=10; total=32, den=20.000 |
| 2x pressure_complete (per_minute) | bot vs icebow-like humans | 1.695 [1.551, 1.840]; n=399, C=399; total=922, den=543.875 | 2.662 [2.113, 3.211]; n=10, C=10; total=49, den=18.410 |
| 3x pressure_complete (per_minute) | bot vs icebow-like humans | 1.224 [0.886, 1.563]; n=93, C=93; total=76, den=62.079 | 1.079 [0.004, 2.154]; n=8, C=8; total=7, den=6.486 |
| 1x pressure_elixir (mean) | bot only | 6.835 [6.698, 6.971]; n=1384, C=376; total=9459.08, den=1384.000 | unavailable |
| 2x pressure_elixir (mean) | bot only | 5.090 [4.927, 5.252]; n=922, C=312; total=4692.56, den=922.000 | unavailable |
| 3x pressure_elixir (mean) | bot only | 4.445 [3.956, 4.933]; n=76, C=38; total=337.783, den=76.000 | unavailable |
| 1x pressure_response_elixir (mean) | bot only | 8.375 [8.173, 8.578]; n=235, C=170; total=1968.23, den=235.000 | unavailable |
| 2x pressure_response_elixir (mean) | bot only | 6.998 [6.795, 7.202]; n=207, C=152; total=1448.65, den=207.000 | unavailable |
| 3x pressure_response_elixir (mean) | bot only | 6.256 [5.088, 7.423]; n=12, C=11; total=75.0697, den=12.000 | unavailable |
| 1x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.170 [0.131, 0.217]; n=1384, C=376; total=235, den=1384.000 | 0.094 [0.000, 0.449]; n=32, C=10; total=3, den=32.000 |
| 2x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.225 [0.173, 0.285]; n=922, C=312; total=207, den=922.000 | 0.184 [0.046, 0.510]; n=49, C=10; total=9, den=49.000 |
| 3x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.158 [0.067, 0.329]; n=76, C=38; total=12, den=76.000 | 0.429 [0.043, 0.846]; n=7, C=3; total=3, den=7.000 |
| 1x pressure_responses (per_minute) | bot vs icebow-like humans | 0.314 [0.272, 0.356]; n=399, C=399; total=235, den=747.898 | 0.150 [0.000, 0.300]; n=10, C=10; total=3, den=20.000 |
| 2x pressure_responses (per_minute) | bot vs icebow-like humans | 0.381 [0.326, 0.435]; n=399, C=399; total=207, den=543.875 | 0.489 [0.147, 0.831]; n=10, C=10; total=9, den=18.410 |
| 3x pressure_responses (per_minute) | bot vs icebow-like humans | 0.193 [0.082, 0.304]; n=93, C=93; total=12, den=62.079 | 0.463 [0.000, 1.121]; n=8, C=8; total=3, den=6.486 |
| 1x pressure_windows (per_minute) | bot vs icebow-like humans | 1.868 [1.753, 1.983]; n=399, C=399; total=1397, den=747.898 | 1.600 [1.001, 2.199]; n=10, C=10; total=32, den=20.000 |
| 2x pressure_windows (per_minute) | bot vs icebow-like humans | 1.802 [1.652, 1.952]; n=399, C=399; total=980, den=543.875 | 2.662 [2.113, 3.211]; n=10, C=10; total=49, den=18.410 |
| 3x pressure_windows (per_minute) | bot vs icebow-like humans | 1.450 [1.058, 1.842]; n=93, C=93; total=90, den=62.079 | 1.079 [0.004, 2.154]; n=8, C=8; total=7, den=6.486 |
| 1x pull_centre (per_minute) | bot only | 0.678 [0.613, 0.743]; n=399, C=399; total=507, den=747.898 | unavailable |
| 2x pull_centre (per_minute) | bot only | 1.346 [1.213, 1.479]; n=399, C=399; total=732, den=543.875 | unavailable |
| 3x pull_centre (per_minute) | bot only | 2.320 [1.753, 2.886]; n=93, C=93; total=144, den=62.079 | unavailable |
| 1x pull_inward_offset (mean) | bot only | 1.706 [1.523, 1.889]; n=1083, C=366; total=1848.01, den=1083.000 | unavailable |
| 2x pull_inward_offset (mean) | bot only | 1.375 [1.218, 1.532]; n=1689, C=369; total=2322.61, den=1689.000 | unavailable |
| 3x pull_inward_offset (mean) | bot only | 1.334 [0.893, 1.775]; n=324, C=71; total=432.201, den=324.000 | unavailable |
| 1x pull_offset (mean) | bot only | 2.656 [2.524, 2.787]; n=1083, C=366; total=2875.99, den=1083.000 | unavailable |
| 2x pull_offset (mean) | bot only | 2.550 [2.437, 2.664]; n=1689, C=369; total=4307.31, den=1689.000 | unavailable |
| 3x pull_offset (mean) | bot only | 2.639 [2.359, 2.920]; n=324, C=71; total=855.165, den=324.000 | unavailable |
| 1x pull_placements (per_minute) | bot only | 1.448 [1.363, 1.533]; n=399, C=399; total=1083, den=747.898 | unavailable |
| 2x pull_placements (per_minute) | bot only | 3.105 [2.914, 3.297]; n=399, C=399; total=1689, den=543.875 | unavailable |
| 3x pull_placements (per_minute) | bot only | 5.219 [4.538, 5.900]; n=93, C=93; total=324, den=62.079 | unavailable |
| 1x pull_side (per_minute) | bot only | 0.770 [0.711, 0.830]; n=399, C=399; total=576, den=747.898 | unavailable |
| 2x pull_side (per_minute) | bot only | 1.760 [1.634, 1.885]; n=399, C=399; total=957, den=543.875 | unavailable |
| 3x pull_side (per_minute) | bot only | 2.900 [2.479, 3.320]; n=93, C=93; total=180, den=62.079 | unavailable |
| 1x tank_complete (per_minute) | bot only | 0.527 [0.461, 0.592]; n=399, C=399; total=394, den=747.898 | unavailable |
| 2x tank_complete (per_minute) | bot only | 0.763 [0.653, 0.873]; n=399, C=399; total=415, den=543.875 | unavailable |
| 3x tank_complete (per_minute) | bot only | 0.822 [0.523, 1.120]; n=93, C=93; total=51, den=62.079 | unavailable |
| 1x tank_crossings (per_minute) | bot only | 0.643 [0.566, 0.720]; n=399, C=399; total=481, den=747.898 | unavailable |
| 2x tank_crossings (per_minute) | bot only | 1.076 [0.939, 1.212]; n=399, C=399; total=585, den=543.875 | unavailable |
| 3x tank_crossings (per_minute) | bot only | 1.498 [1.078, 1.918]; n=93, C=93; total=93, den=62.079 | unavailable |
| 1x tank_preexisting_tesla (fraction) | bot only | 0.399 [0.326, 0.477]; n=481, C=214; total=192, den=481.000 | unavailable |
| 2x tank_preexisting_tesla (fraction) | bot only | 0.523 [0.443, 0.602]; n=585, C=212; total=306, den=585.000 | unavailable |
| 3x tank_preexisting_tesla (fraction) | bot only | 0.559 [0.384, 0.721]; n=93, C=39; total=52, den=93.000 | unavailable |
| 1x tank_tesla_delay (mean) | bot only | 7.230 [4.976, 9.484]; n=50, C=38; total=361.5, den=50.000 | unavailable |
| 2x tank_tesla_delay (mean) | bot only | 6.958 [5.779, 8.137]; n=145, C=95; total=1008.9, den=145.000 | unavailable |
| 3x tank_tesla_delay (mean) | bot only | 6.768 [4.959, 8.578]; n=33, C=17; total=223.35, den=33.000 | unavailable |
| 1x tank_tesla_response (per_minute) | bot only | 0.067 [0.040, 0.094]; n=399, C=399; total=50, den=747.898 | unavailable |
| 2x tank_tesla_response (per_minute) | bot only | 0.267 [0.212, 0.321]; n=399, C=399; total=145, den=543.875 | unavailable |
| 3x tank_tesla_response (per_minute) | bot only | 0.532 [0.280, 0.783]; n=93, C=93; total=33, den=62.079 | unavailable |
| 1x tank_tesla_survival (fraction) | bot only | 0.524 [0.351, 0.691]; n=42, C=36; total=22, den=42.000 | unavailable |
| 2x tank_tesla_survival (fraction) | bot only | 0.647 [0.518, 0.757]; n=116, C=76; total=75, den=116.000 | unavailable |
| 3x tank_tesla_survival (fraction) | bot only | 0.778 [0.470, 0.998]; n=18, C=14; total=14, den=18.000 | unavailable |
| 1x xbow.Balloon (per_minute) | bot vs icebow-like humans | 0.711 [0.530, 0.893]; n=21, C=21; total=28, den=39.366 | 0.500 [0.000, 1.480]; n=2, C=2; total=2, den=4.000 |
| 2x xbow.Balloon (per_minute) | bot vs icebow-like humans | 1.320 [1.030, 1.610]; n=21, C=21; total=40, den=30.306 | 2.250 [1.760, 2.740]; n=2, C=2; total=9, den=4.000 |
| 3x xbow.Balloon (per_minute) | bot vs icebow-like humans | 0.942 [0.343, 1.541]; n=7, C=7; total=5, den=5.307 | 2.460 [1.351, 3.570]; n=2, C=2; total=4, den=1.626 |
| 1x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 0.600 [0.292, 0.909]; n=8, C=8; total=9, den=14.997 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 1.164 [0.718, 1.609]; n=8, C=8; total=13, den=11.172 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 3x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 6.140]; n=2, C=2; total=0, den=0.601 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 |
| 1x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 0.953 [0.791, 1.114]; n=14, C=14; total=25, den=26.247 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 2x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 1.473 [1.235, 1.711]; n=14, C=14; total=27, den=18.327 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 3x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 4.679]; n=2, C=2; total=0, den=0.788 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 |
| 1x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 0.850 [0.722, 0.978]; n=27, C=27; total=43, den=50.615 | unavailable |
| 2x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 1.096 [0.844, 1.347]; n=27, C=27; total=39, den=35.599 | unavailable |
| 3x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 0.505 [0.000, 1.135]; n=5, C=5; total=2, den=3.957 | unavailable |
| 1x xbow.Giant (per_minute) | bot vs icebow-like humans | 1.067 [1.067, 1.067]; n=3, C=3; total=6, den=5.623 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Giant (per_minute) | bot vs icebow-like humans | 1.514 [0.288, 2.739]; n=3, C=3; total=6, den=3.964 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 3x xbow.Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | 1.000 [95% CI not estimable]; n=1, C=1; total=1, den=1.000 |
| 1x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 0.815 [0.657, 0.974]; n=36, C=36; total=55, den=67.450 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 1.421 [1.250, 1.592]; n=36, C=36; total=72, den=50.664 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 1.018 [0.058, 1.977]; n=6, C=6; total=4, den=3.930 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | 1.067 [0.820, 1.313]; n=9, C=9; total=18, den=16.872 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | 1.973 [1.481, 2.465]; n=9, C=9; total=19, den=9.631 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 0.900 [0.716, 1.084]; n=16, C=16; total=27, den=29.992 | 1.000 [95% CI not estimable]; n=1, C=1; total=2, den=2.000 |
| 2x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 1.179 [0.871, 1.487]; n=16, C=16; total=24, den=20.358 | 0.930 [95% CI not estimable]; n=1, C=1; total=1, den=1.076 |
| 3x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 2.304]; n=3, C=3; total=0, den=1.601 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | 0.533 [95% CI not estimable]; n=1, C=1; total=1, den=1.875 | unavailable |
| 2x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | 0.946 [95% CI not estimable]; n=1, C=1; total=1, den=1.057 | unavailable |
| 3x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Golem (per_minute) | bot vs icebow-like humans | 1.209 [1.049, 1.369]; n=15, C=15; total=34, den=28.117 | unavailable |
| 2x xbow.Golem (per_minute) | bot vs icebow-like humans | 1.047 [0.740, 1.355]; n=15, C=15; total=17, den=16.229 | unavailable |
| 3x xbow.Golem (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 0.833 [0.621, 1.046]; n=16, C=16; total=25, den=29.994 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 1.522 [1.308, 1.736]; n=16, C=16; total=32, den=21.022 | 2.500 [95% CI not estimable]; n=1, C=1; total=5, den=2.000 |
| 3x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 0.717 [0.000, 2.612]; n=3, C=3; total=1, den=1.395 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.284 |
| 1x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.745 [0.627, 0.863]; n=58, C=58; total=81, den=108.724 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 1.274 [1.094, 1.454]; n=58, C=58; total=111, den=87.123 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.604 [0.185, 1.022]; n=21, C=21; total=9, den=14.912 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 0.914 [0.722, 1.107]; n=7, C=7; total=12, den=13.123 | unavailable |
| 2x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 1.077 [0.846, 1.309]; n=7, C=7; total=9, den=8.353 | unavailable |
| 3x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 1.000 [95% CI not estimable]; n=1, C=1; total=1, den=1.000 | unavailable |
| 1x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 0.593 [0.406, 0.780]; n=18, C=18; total=20, den=33.743 | unavailable |
| 2x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 1.266 [0.986, 1.547]; n=18, C=18; total=34, den=26.848 | unavailable |
| 3x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 1.569 [0.693, 2.445]; n=7, C=7; total=4, den=2.550 | unavailable |
| 1x xbow.Miner (per_minute) | bot vs icebow-like humans | 0.825 [0.660, 0.990]; n=11, C=11; total=17, den=20.605 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Miner (per_minute) | bot vs icebow-like humans | 1.490 [1.196, 1.784]; n=11, C=11; total=21, den=14.096 | 2.500 [95% CI not estimable]; n=1, C=1; total=5, den=2.000 |
| 3x xbow.Miner (per_minute) | bot vs icebow-like humans | 0.620 [0.000, 1.544]; n=2, C=2; total=1, den=1.612 | 1.737 [95% CI not estimable]; n=1, C=1; total=1, den=0.576 |
| 1x xbow.Mortar (per_minute) | bot vs icebow-like humans | 0.562 [0.392, 0.731]; n=19, C=19; total=20, den=35.613 | 1.000 [95% CI not estimable]; n=1, C=1; total=2, den=2.000 |
| 2x xbow.Mortar (per_minute) | bot vs icebow-like humans | 1.419 [1.132, 1.706]; n=19, C=19; total=40, den=28.190 | 1.000 [95% CI not estimable]; n=1, C=1; total=2, den=2.000 |
| 3x xbow.Mortar (per_minute) | bot vs icebow-like humans | 0.565 [0.113, 1.017]; n=7, C=7; total=3, den=5.311 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 |
| 1x xbow.Other (per_minute) | bot vs icebow-like humans | 0.830 [0.669, 0.991]; n=27, C=27; total=42, den=50.611 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Other (per_minute) | bot vs icebow-like humans | 1.251 [1.074, 1.429]; n=27, C=27; total=43, den=34.361 | 0.750 [95% CI not estimable]; n=1, C=1; total=1, den=1.334 |
| 3x xbow.Other (per_minute) | bot vs icebow-like humans | 1.333 [0.000, 3.062]; n=3, C=3; total=4, den=3.000 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 1.067 [0.599, 1.535]; n=6, C=6; total=12, den=11.248 | unavailable |
| 2x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 1.439 [0.723, 2.155]; n=6, C=6; total=11, den=7.645 | unavailable |
| 3x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 2.913 [95% CI not estimable]; n=1, C=1; total=1, den=0.343 | unavailable |
| 1x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 0.698 [0.515, 0.881]; n=13, C=13; total=17, den=24.367 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 1.593 [1.335, 1.851]; n=13, C=13; total=26, den=16.325 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 2.145 [95% CI not estimable]; n=1, C=1; total=2, den=0.932 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 0.838 [0.627, 1.050]; n=21, C=21; total=33, den=39.365 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 1.383 [1.045, 1.720]; n=21, C=21; total=42, den=30.378 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 0.179 [0.000, 0.561]; n=8, C=8; total=1, den=5.591 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 0.753 [0.625, 0.882]; n=17, C=17; total=24, den=31.866 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 1.522 [1.310, 1.735]; n=17, C=17; total=35, den=22.992 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 1.975 [1.137, 2.813]; n=4, C=4; total=6, den=3.038 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 0.400 [0.000, 1.184]; n=4, C=4; total=3, den=7.498 | unavailable |
| 2x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 1.145 [0.504, 1.787]; n=4, C=4; total=7, den=6.112 | unavailable |
| 3x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 0.511 [0.000, 1.534]; n=2, C=2; total=1, den=1.958 | unavailable |
| 1x xbow.Sparky (per_minute) | bot vs icebow-like humans | 0.889 [0.192, 1.586]; n=3, C=3; total=5, den=5.624 | unavailable |
| 2x xbow.Sparky (per_minute) | bot vs icebow-like humans | 1.273 [0.639, 1.908]; n=3, C=3; total=4, den=3.142 | unavailable |
| 3x xbow.Sparky (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 0.747 [0.491, 1.003]; n=5, C=5; total=7, den=9.373 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 1.128 [0.834, 1.422]; n=5, C=5; total=7, den=6.207 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.328 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 0.533 [0.343, 0.724]; n=16, C=16; total=16, den=29.993 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 1.387 [1.189, 1.585]; n=16, C=16; total=32, den=23.072 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 0.748 [0.000, 1.976]; n=5, C=5; total=2, den=2.674 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.X-Bow (per_minute) | bot vs icebow-like humans | 1.067 [0.869, 1.264]; n=8, C=8; total=16, den=14.998 | unavailable |
| 2x xbow.X-Bow (per_minute) | bot vs icebow-like humans | 1.308 [0.852, 1.764]; n=8, C=8; total=14, den=10.703 | unavailable |
| 3x xbow.X-Bow (per_minute) | bot vs icebow-like humans | 0.798 [0.167, 1.429]; n=2, C=2; total=1, den=1.252 | unavailable |
| 1x xbow_damage.Balloon (mean) | bot only | 1757.148 [1350.431, 2163.865]; n=27, C=18; total=47443, den=27.000 | unavailable |
| 2x xbow_damage.Balloon (mean) | bot only | 1093.036 [721.205, 1464.866]; n=28, C=18; total=30605, den=28.000 | unavailable |
| 3x xbow_damage.Balloon (mean) | bot only | 1104.200 [0.000, 2406.243]; n=5, C=4; total=5521, den=5.000 | unavailable |
| 1x xbow_damage.Battle Ram (mean) | bot only | 2493.571 [1790.252, 3196.891]; n=7, C=5; total=17455, den=7.000 | unavailable |
| 2x xbow_damage.Battle Ram (mean) | bot only | 1573.000 [611.221, 2534.779]; n=8, C=4; total=12584, den=8.000 | unavailable |
| 3x xbow_damage.Battle Ram (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Electro Giant (mean) | bot only | 1726.480 [1061.050, 2391.910]; n=25, C=14; total=43162, den=25.000 | unavailable |
| 2x xbow_damage.Electro Giant (mean) | bot only | 1285.526 [375.905, 2195.148]; n=19, C=11; total=24425, den=19.000 | unavailable |
| 3x xbow_damage.Electro Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Elixir Golem (mean) | bot only | 1771.205 [1259.208, 2283.202]; n=39, C=26; total=69077, den=39.000 | unavailable |
| 2x xbow_damage.Elixir Golem (mean) | bot only | 1566.219 [962.521, 2169.917]; n=32, C=20; total=50119, den=32.000 | unavailable |
| 3x xbow_damage.Elixir Golem (mean) | bot only | 2293.500 [0.000, 5181.560]; n=2, C=2; total=4587, den=2.000 | unavailable |
| 1x xbow_damage.Giant (mean) | bot only | 1267.667 [23.944, 2511.390]; n=6, C=3; total=7606, den=6.000 | unavailable |
| 2x xbow_damage.Giant (mean) | bot only | 943.667 [526.404, 1360.929]; n=3, C=2; total=2831, den=3.000 | unavailable |
| 3x xbow_damage.Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Barrel (mean) | bot only | 1142.587 [802.274, 1482.900]; n=46, C=27; total=52559, den=46.000 | unavailable |
| 2x xbow_damage.Goblin Barrel (mean) | bot only | 1415.273 [979.996, 1850.550]; n=44, C=27; total=62272, den=44.000 | unavailable |
| 3x xbow_damage.Goblin Barrel (mean) | bot only | 1000.000 [0.000, 2860.040]; n=2, C=2; total=2000, den=2.000 | unavailable |
| 1x xbow_damage.Goblin Drill (mean) | bot only | 1372.235 [893.586, 1850.885]; n=17, C=9; total=23328, den=17.000 | unavailable |
| 2x xbow_damage.Goblin Drill (mean) | bot only | 540.500 [115.089, 965.911]; n=10, C=7; total=5405, den=10.000 | unavailable |
| 3x xbow_damage.Goblin Drill (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Giant (mean) | bot only | 1898.520 [1372.201, 2424.839]; n=25, C=15; total=47463, den=25.000 | unavailable |
| 2x xbow_damage.Goblin Giant (mean) | bot only | 1040.941 [462.359, 1619.523]; n=17, C=11; total=17696, den=17.000 | unavailable |
| 3x xbow_damage.Goblin Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Machine (mean) | bot only | 3615.000 [95% CI not estimable]; n=1, C=1; total=3615, den=1.000 | unavailable |
| 2x xbow_damage.Goblin Machine (mean) | bot only | 75.000 [95% CI not estimable]; n=1, C=1; total=75, den=1.000 | unavailable |
| 3x xbow_damage.Goblin Machine (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Golem (mean) | bot only | 1850.697 [1345.279, 2356.115]; n=33, C=15; total=61073, den=33.000 | unavailable |
| 2x xbow_damage.Golem (mean) | bot only | 1593.231 [917.280, 2269.181]; n=13, C=12; total=20712, den=13.000 | unavailable |
| 3x xbow_damage.Golem (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Graveyard (mean) | bot only | 1517.136 [993.177, 2041.095]; n=22, C=14; total=33377, den=22.000 | unavailable |
| 2x xbow_damage.Graveyard (mean) | bot only | 1267.042 [931.032, 1603.051]; n=24, C=15; total=30409, den=24.000 | unavailable |
| 3x xbow_damage.Graveyard (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Hog Rider (mean) | bot only | 1303.286 [966.592, 1639.979]; n=56, C=41; total=72984, den=56.000 | unavailable |
| 2x xbow_damage.Hog Rider (mean) | bot only | 891.529 [676.652, 1106.407]; n=85, C=46; total=75780, den=85.000 | unavailable |
| 3x xbow_damage.Hog Rider (mean) | bot only | 1406.200 [154.623, 2657.777]; n=5, C=5; total=7031, den=5.000 | unavailable |
| 1x xbow_damage.Lava Hound (mean) | bot only | 2389.273 [1869.565, 2908.981]; n=11, C=7; total=26282, den=11.000 | unavailable |
| 2x xbow_damage.Lava Hound (mean) | bot only | 1737.625 [509.497, 2965.753]; n=8, C=6; total=13901, den=8.000 | unavailable |
| 3x xbow_damage.Lava Hound (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Mega Knight (mean) | bot only | 1293.353 [665.891, 1920.815]; n=17, C=13; total=21987, den=17.000 | unavailable |
| 2x xbow_damage.Mega Knight (mean) | bot only | 1039.826 [513.675, 1565.977]; n=23, C=14; total=23916, den=23.000 | unavailable |
| 3x xbow_damage.Mega Knight (mean) | bot only | 381.000 [95% CI not estimable]; n=1, C=1; total=381, den=1.000 | unavailable |
| 1x xbow_damage.Miner (mean) | bot only | 1664.429 [1255.566, 2073.291]; n=14, C=10; total=23302, den=14.000 | unavailable |
| 2x xbow_damage.Miner (mean) | bot only | 1107.867 [354.661, 1861.073]; n=15, C=10; total=16618, den=15.000 | unavailable |
| 3x xbow_damage.Miner (mean) | bot only | 1263.000 [95% CI not estimable]; n=1, C=1; total=1263, den=1.000 | unavailable |
| 1x xbow_damage.Mortar (mean) | bot only | 1839.750 [1059.084, 2620.416]; n=16, C=13; total=29436, den=16.000 | unavailable |
| 2x xbow_damage.Mortar (mean) | bot only | 1026.548 [518.455, 1534.642]; n=31, C=17; total=31823, den=31.000 | unavailable |
| 3x xbow_damage.Mortar (mean) | bot only | 1206.000 [12.360, 2399.640]; n=2, C=2; total=2412, den=2.000 | unavailable |
| 1x xbow_damage.Other (mean) | bot only | 1596.711 [1083.449, 2109.972]; n=38, C=24; total=60675, den=38.000 | unavailable |
| 2x xbow_damage.Other (mean) | bot only | 1298.000 [730.799, 1865.201]; n=29, C=23; total=37642, den=29.000 | unavailable |
| 3x xbow_damage.Other (mean) | bot only | 40.000 [95% CI not estimable]; n=1, C=1; total=40, den=1.000 | unavailable |
| 1x xbow_damage.P.E.K.K.A (mean) | bot only | 1235.800 [379.161, 2092.439]; n=10, C=5; total=12358, den=10.000 | unavailable |
| 2x xbow_damage.P.E.K.K.A (mean) | bot only | 965.000 [439.147, 1490.853]; n=8, C=4; total=7720, den=8.000 | unavailable |
| 3x xbow_damage.P.E.K.K.A (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Ram Rider (mean) | bot only | 1768.600 [1065.915, 2471.285]; n=15, C=12; total=26529, den=15.000 | unavailable |
| 2x xbow_damage.Ram Rider (mean) | bot only | 1414.333 [772.853, 2055.814]; n=15, C=10; total=21215, den=15.000 | unavailable |
| 3x xbow_damage.Ram Rider (mean) | bot only | 323.000 [95% CI not estimable]; n=1, C=1; total=323, den=1.000 | unavailable |
| 1x xbow_damage.Royal Giant (mean) | bot only | 1588.467 [1116.894, 2060.039]; n=30, C=17; total=47654, den=30.000 | unavailable |
| 2x xbow_damage.Royal Giant (mean) | bot only | 1268.343 [881.259, 1655.426]; n=35, C=18; total=44392, den=35.000 | unavailable |
| 3x xbow_damage.Royal Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Royal Hogs (mean) | bot only | 1756.688 [1037.598, 2475.777]; n=16, C=13; total=28107, den=16.000 | unavailable |
| 2x xbow_damage.Royal Hogs (mean) | bot only | 1106.955 [683.420, 1530.489]; n=22, C=14; total=24353, den=22.000 | unavailable |
| 3x xbow_damage.Royal Hogs (mean) | bot only | 850.000 [158.120, 1541.880]; n=2, C=2; total=1700, den=2.000 | unavailable |
| 1x xbow_damage.Rune Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Rune Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Rune Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Skeleton Barrel (mean) | bot only | 878.500 [95% CI not estimable]; n=2, C=1; total=1757, den=2.000 | unavailable |
| 2x xbow_damage.Skeleton Barrel (mean) | bot only | 2280.000 [1214.317, 3345.683]; n=5, C=3; total=11400, den=5.000 | unavailable |
| 3x xbow_damage.Skeleton Barrel (mean) | bot only | 1078.000 [95% CI not estimable]; n=1, C=1; total=1078, den=1.000 | unavailable |
| 1x xbow_damage.Sparky (mean) | bot only | 1539.200 [312.678, 2765.722]; n=5, C=3; total=7696, den=5.000 | unavailable |
| 2x xbow_damage.Sparky (mean) | bot only | 2702.667 [906.724, 4498.609]; n=3, C=3; total=8108, den=3.000 | unavailable |
| 3x xbow_damage.Sparky (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Three Musketeers (mean) | bot only | 2043.143 [1113.022, 2973.264]; n=7, C=5; total=14302, den=7.000 | unavailable |
| 2x xbow_damage.Three Musketeers (mean) | bot only | 1389.800 [1021.975, 1757.625]; n=5, C=3; total=6949, den=5.000 | unavailable |
| 3x xbow_damage.Three Musketeers (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Wall Breakers (mean) | bot only | 1182.846 [497.478, 1868.214]; n=13, C=10; total=15377, den=13.000 | unavailable |
| 2x xbow_damage.Wall Breakers (mean) | bot only | 1336.667 [836.320, 1837.013]; n=24, C=15; total=32080, den=24.000 | unavailable |
| 3x xbow_damage.Wall Breakers (mean) | bot only | 72.000 [95% CI not estimable]; n=1, C=1; total=72, den=1.000 | unavailable |
| 1x xbow_damage.X-Bow (mean) | bot only | 1385.846 [862.044, 1909.648]; n=13, C=8; total=18016, den=13.000 | unavailable |
| 2x xbow_damage.X-Bow (mean) | bot only | 576.636 [17.283, 1135.990]; n=11, C=5; total=6343, den=11.000 | unavailable |
| 3x xbow_damage.X-Bow (mean) | bot only | 445.000 [95% CI not estimable]; n=1, C=1; total=445, den=1.000 | unavailable |
| 1x xbow_full.Balloon (per_minute) | bot only | 0.686 [0.507, 0.865]; n=21, C=21; total=27, den=39.366 | unavailable |
| 2x xbow_full.Balloon (per_minute) | bot only | 0.924 [0.675, 1.173]; n=21, C=21; total=28, den=30.306 | unavailable |
| 3x xbow_full.Balloon (per_minute) | bot only | 0.942 [0.343, 1.541]; n=7, C=7; total=5, den=5.307 | unavailable |
| 1x xbow_full.Battle Ram (per_minute) | bot only | 0.467 [0.158, 0.775]; n=8, C=8; total=7, den=14.997 | unavailable |
| 2x xbow_full.Battle Ram (per_minute) | bot only | 0.716 [0.157, 1.276]; n=8, C=8; total=8, den=11.172 | unavailable |
| 3x xbow_full.Battle Ram (per_minute) | bot only | 0.000 [0.000, 6.140]; n=2, C=2; total=0, den=0.601 | unavailable |
| 1x xbow_full.Electro Giant (per_minute) | bot only | 0.953 [0.791, 1.114]; n=14, C=14; total=25, den=26.247 | unavailable |
| 2x xbow_full.Electro Giant (per_minute) | bot only | 1.037 [0.620, 1.453]; n=14, C=14; total=19, den=18.327 | unavailable |
| 3x xbow_full.Electro Giant (per_minute) | bot only | 0.000 [0.000, 4.679]; n=2, C=2; total=0, den=0.788 | unavailable |
| 1x xbow_full.Elixir Golem (per_minute) | bot only | 0.771 [0.630, 0.911]; n=27, C=27; total=39, den=50.615 | unavailable |
| 2x xbow_full.Elixir Golem (per_minute) | bot only | 0.899 [0.626, 1.172]; n=27, C=27; total=32, den=35.599 | unavailable |
| 3x xbow_full.Elixir Golem (per_minute) | bot only | 0.505 [0.000, 1.135]; n=5, C=5; total=2, den=3.957 | unavailable |
| 1x xbow_full.Giant (per_minute) | bot only | 1.067 [1.067, 1.067]; n=3, C=3; total=6, den=5.623 | unavailable |
| 2x xbow_full.Giant (per_minute) | bot only | 0.757 [0.000, 1.602]; n=3, C=3; total=3, den=3.964 | unavailable |
| 3x xbow_full.Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblin Barrel (per_minute) | bot only | 0.682 [0.528, 0.836]; n=36, C=36; total=46, den=67.450 | unavailable |
| 2x xbow_full.Goblin Barrel (per_minute) | bot only | 0.868 [0.667, 1.070]; n=36, C=36; total=44, den=50.664 | unavailable |
| 3x xbow_full.Goblin Barrel (per_minute) | bot only | 0.509 [0.000, 1.058]; n=6, C=6; total=2, den=3.930 | unavailable |
| 1x xbow_full.Goblin Drill (per_minute) | bot only | 1.008 [0.798, 1.217]; n=9, C=9; total=17, den=16.872 | unavailable |
| 2x xbow_full.Goblin Drill (per_minute) | bot only | 1.038 [0.665, 1.412]; n=9, C=9; total=10, den=9.631 | unavailable |
| 3x xbow_full.Goblin Drill (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblin Giant (per_minute) | bot only | 0.834 [0.643, 1.024]; n=16, C=16; total=25, den=29.992 | unavailable |
| 2x xbow_full.Goblin Giant (per_minute) | bot only | 0.835 [0.520, 1.150]; n=16, C=16; total=17, den=20.358 | unavailable |
| 3x xbow_full.Goblin Giant (per_minute) | bot only | 0.000 [0.000, 2.304]; n=3, C=3; total=0, den=1.601 | unavailable |
| 1x xbow_full.Goblin Machine (per_minute) | bot only | 0.533 [95% CI not estimable]; n=1, C=1; total=1, den=1.875 | unavailable |
| 2x xbow_full.Goblin Machine (per_minute) | bot only | 0.946 [95% CI not estimable]; n=1, C=1; total=1, den=1.057 | unavailable |
| 3x xbow_full.Goblin Machine (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblinstein (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.Goblinstein (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Goblinstein (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Golem (per_minute) | bot only | 1.174 [0.991, 1.356]; n=15, C=15; total=33, den=28.117 | unavailable |
| 2x xbow_full.Golem (per_minute) | bot only | 0.801 [0.545, 1.057]; n=15, C=15; total=13, den=16.229 | unavailable |
| 3x xbow_full.Golem (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Graveyard (per_minute) | bot only | 0.733 [0.546, 0.921]; n=16, C=16; total=22, den=29.994 | unavailable |
| 2x xbow_full.Graveyard (per_minute) | bot only | 1.142 [0.874, 1.409]; n=16, C=16; total=24, den=21.022 | unavailable |
| 3x xbow_full.Graveyard (per_minute) | bot only | 0.000 [0.000, 2.644]; n=3, C=3; total=0, den=1.395 | unavailable |
| 1x xbow_full.Hog Rider (per_minute) | bot only | 0.515 [0.406, 0.624]; n=58, C=58; total=56, den=108.724 | unavailable |
| 2x xbow_full.Hog Rider (per_minute) | bot only | 0.976 [0.797, 1.154]; n=58, C=58; total=85, den=87.123 | unavailable |
| 3x xbow_full.Hog Rider (per_minute) | bot only | 0.335 [0.071, 0.600]; n=21, C=21; total=5, den=14.912 | unavailable |
| 1x xbow_full.Lava Hound (per_minute) | bot only | 0.838 [0.627, 1.049]; n=7, C=7; total=11, den=13.123 | unavailable |
| 2x xbow_full.Lava Hound (per_minute) | bot only | 0.958 [0.581, 1.335]; n=7, C=7; total=8, den=8.353 | unavailable |
| 3x xbow_full.Lava Hound (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 1x xbow_full.Mega Knight (per_minute) | bot only | 0.504 [0.325, 0.683]; n=18, C=18; total=17, den=33.743 | unavailable |
| 2x xbow_full.Mega Knight (per_minute) | bot only | 0.857 [0.573, 1.140]; n=18, C=18; total=23, den=26.848 | unavailable |
| 3x xbow_full.Mega Knight (per_minute) | bot only | 0.392 [0.000, 1.131]; n=7, C=7; total=1, den=2.550 | unavailable |
| 1x xbow_full.Miner (per_minute) | bot only | 0.679 [0.476, 0.883]; n=11, C=11; total=14, den=20.605 | unavailable |
| 2x xbow_full.Miner (per_minute) | bot only | 1.064 [0.766, 1.363]; n=11, C=11; total=15, den=14.096 | unavailable |
| 3x xbow_full.Miner (per_minute) | bot only | 0.620 [0.000, 1.544]; n=2, C=2; total=1, den=1.612 | unavailable |
| 1x xbow_full.Mortar (per_minute) | bot only | 0.449 [0.284, 0.614]; n=19, C=19; total=16, den=35.613 | unavailable |
| 2x xbow_full.Mortar (per_minute) | bot only | 1.100 [0.835, 1.365]; n=19, C=19; total=31, den=28.190 | unavailable |
| 3x xbow_full.Mortar (per_minute) | bot only | 0.377 [0.000, 0.810]; n=7, C=7; total=2, den=5.311 | unavailable |
| 1x xbow_full.Other (per_minute) | bot only | 0.751 [0.600, 0.901]; n=27, C=27; total=38, den=50.611 | unavailable |
| 2x xbow_full.Other (per_minute) | bot only | 0.844 [0.678, 1.010]; n=27, C=27; total=29, den=34.361 | unavailable |
| 3x xbow_full.Other (per_minute) | bot only | 0.333 [0.000, 0.987]; n=3, C=3; total=1, den=3.000 | unavailable |
| 1x xbow_full.P.E.K.K.A (per_minute) | bot only | 0.889 [0.448, 1.330]; n=6, C=6; total=10, den=11.248 | unavailable |
| 2x xbow_full.P.E.K.K.A (per_minute) | bot only | 1.046 [0.359, 1.734]; n=6, C=6; total=8, den=7.645 | unavailable |
| 3x xbow_full.P.E.K.K.A (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.343 | unavailable |
| 1x xbow_full.Ram Rider (per_minute) | bot only | 0.616 [0.455, 0.776]; n=13, C=13; total=15, den=24.367 | unavailable |
| 2x xbow_full.Ram Rider (per_minute) | bot only | 0.919 [0.541, 1.297]; n=13, C=13; total=15, den=16.325 | unavailable |
| 3x xbow_full.Ram Rider (per_minute) | bot only | 1.072 [95% CI not estimable]; n=1, C=1; total=1, den=0.932 | unavailable |
| 1x xbow_full.Royal Giant (per_minute) | bot only | 0.762 [0.564, 0.961]; n=21, C=21; total=30, den=39.365 | unavailable |
| 2x xbow_full.Royal Giant (per_minute) | bot only | 1.152 [0.855, 1.449]; n=21, C=21; total=35, den=30.378 | unavailable |
| 3x xbow_full.Royal Giant (per_minute) | bot only | 0.000 [0.000, 0.660]; n=8, C=8; total=0, den=5.591 | unavailable |
| 1x xbow_full.Royal Hogs (per_minute) | bot only | 0.502 [0.335, 0.669]; n=17, C=17; total=16, den=31.866 | unavailable |
| 2x xbow_full.Royal Hogs (per_minute) | bot only | 0.957 [0.656, 1.258]; n=17, C=17; total=22, den=22.992 | unavailable |
| 3x xbow_full.Royal Hogs (per_minute) | bot only | 0.658 [0.019, 1.298]; n=4, C=4; total=2, den=3.038 | unavailable |
| 1x xbow_full.Rune Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.Rune Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Rune Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.267 [0.000, 0.789]; n=4, C=4; total=2, den=7.498 | unavailable |
| 2x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.818 [0.065, 1.571]; n=4, C=4; total=5, den=6.112 | unavailable |
| 3x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.511 [0.000, 1.534]; n=2, C=2; total=1, den=1.958 | unavailable |
| 1x xbow_full.Sparky (per_minute) | bot only | 0.889 [0.192, 1.586]; n=3, C=3; total=5, den=5.624 | unavailable |
| 2x xbow_full.Sparky (per_minute) | bot only | 0.955 [0.945, 0.965]; n=3, C=3; total=3, den=3.142 | unavailable |
| 3x xbow_full.Sparky (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Three Musketeers (per_minute) | bot only | 0.747 [0.491, 1.003]; n=5, C=5; total=7, den=9.373 | unavailable |
| 2x xbow_full.Three Musketeers (per_minute) | bot only | 0.806 [0.157, 1.454]; n=5, C=5; total=5, den=6.207 | unavailable |
| 3x xbow_full.Three Musketeers (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.328 | unavailable |
| 1x xbow_full.Wall Breakers (per_minute) | bot only | 0.433 [0.237, 0.629]; n=16, C=16; total=13, den=29.993 | unavailable |
| 2x xbow_full.Wall Breakers (per_minute) | bot only | 1.040 [0.780, 1.301]; n=16, C=16; total=24, den=23.072 | unavailable |
| 3x xbow_full.Wall Breakers (per_minute) | bot only | 0.374 [0.000, 0.988]; n=5, C=5; total=1, den=2.674 | unavailable |
| 1x xbow_full.X-Bow (per_minute) | bot only | 0.867 [0.676, 1.058]; n=8, C=8; total=13, den=14.998 | unavailable |
| 2x xbow_full.X-Bow (per_minute) | bot only | 1.028 [0.419, 1.636]; n=8, C=8; total=11, den=10.703 | unavailable |
| 3x xbow_full.X-Bow (per_minute) | bot only | 0.798 [0.167, 1.429]; n=2, C=2; total=1, den=1.252 | unavailable |

### Video outcomes: losses

Bot only unless the comparison column says bot vs icebow-like humans. Per-minute values use phase minutes except state/archetype rows, which use their own exposure. Means/fractions show event n and cluster C. Human column = icebow-like humans.

| Phase / metric (unit) | Comparison | Bot [95% CI] | Human [95% CI] |
|---|---|---|
| 1x clump_bodies (per_minute) | bot only | 0.177 [0.117, 0.238]; n=373, C=373; total=122, den=687.816 | unavailable |
| 2x clump_bodies (per_minute) | bot only | 0.499 [0.330, 0.667]; n=345, C=345; total=215, den=431.012 | unavailable |
| 3x clump_bodies (per_minute) | bot only | 1.730 [0.974, 2.486]; n=74, C=74; total=87, den=50.291 | unavailable |
| 1x clump_contacts (per_minute) | bot only | 0.352 [0.286, 0.418]; n=373, C=373; total=242, den=687.816 | unavailable |
| 2x clump_contacts (per_minute) | bot only | 0.842 [0.690, 0.995]; n=345, C=345; total=363, den=431.012 | unavailable |
| 3x clump_contacts (per_minute) | bot only | 2.048 [1.493, 2.603]; n=74, C=74; total=103, den=50.291 | unavailable |
| 1x clump_elixir (per_minute) | bot only | 0.212 [0.114, 0.309]; n=373, C=373; total=145.667, den=687.816 | unavailable |
| 2x clump_elixir (per_minute) | bot only | 0.545 [0.331, 0.759]; n=345, C=345; total=235, den=431.012 | unavailable |
| 3x clump_elixir (per_minute) | bot only | 1.949 [1.016, 2.881]; n=74, C=74; total=98, den=50.291 | unavailable |
| 1x clump_episodes (per_minute) | bot only | 0.065 [0.043, 0.088]; n=373, C=373; total=45, den=687.816 | unavailable |
| 2x clump_episodes (per_minute) | bot only | 0.183 [0.124, 0.242]; n=345, C=345; total=79, den=431.012 | unavailable |
| 3x clump_episodes (per_minute) | bot only | 0.577 [0.338, 0.815]; n=74, C=74; total=29, den=50.291 | unavailable |
| 1x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.005]; n=373, C=373; total=0, den=687.816 | unavailable |
| 2x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.009]; n=345, C=345; total=0, den=431.012 | unavailable |
| 3x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.073]; n=74, C=74; total=0, den=50.291 | unavailable |
| 1x commit.ahead (per_minute) | bot only | 1.276 [1.113, 1.439]; n=196, C=196; total=149, den=116.761 | unavailable |
| 2x commit.ahead (per_minute) | bot only | 2.493 [2.176, 2.810]; n=97, C=97; total=152, den=60.974 | unavailable |
| 3x commit.ahead (per_minute) | bot only | 3.949 [2.966, 4.932]; n=14, C=14; total=24, den=6.077 | unavailable |
| 1x commit.behind (per_minute) | bot only | 1.052 [0.948, 1.157]; n=269, C=269; total=257, den=244.187 | unavailable |
| 2x commit.behind (per_minute) | bot only | 2.620 [2.473, 2.766]; n=308, C=308; total=675, den=257.654 | unavailable |
| 3x commit.behind (per_minute) | bot only | 4.330 [3.823, 4.837]; n=51, C=51; total=121, den=27.942 | unavailable |
| 1x commit.level (per_minute) | bot only | 1.333 [1.234, 1.432]; n=344, C=344; total=417, den=312.736 | unavailable |
| 2x commit.level (per_minute) | bot only | 2.661 [2.433, 2.889]; n=169, C=169; total=252, den=94.712 | unavailable |
| 3x commit.level (per_minute) | bot only | 4.637 [3.661, 5.614]; n=26, C=26; total=63, den=13.586 | unavailable |
| 1x commit_damage.ahead (mean) | bot only | 650.040 [438.993, 861.087]; n=101, C=64; total=65654, den=101.000 | unavailable |
| 2x commit_damage.ahead (mean) | bot only | 614.531 [397.333, 831.729]; n=96, C=41; total=58995, den=96.000 | unavailable |
| 3x commit_damage.ahead (mean) | bot only | 443.077 [134.890, 751.263]; n=13, C=9; total=5760, den=13.000 | unavailable |
| 1x commit_damage.behind (mean) | bot only | 714.827 [560.291, 869.363]; n=214, C=141; total=152973, den=214.000 | unavailable |
| 2x commit_damage.behind (mean) | bot only | 511.796 [427.813, 595.779]; n=491, C=188; total=251292, den=491.000 | unavailable |
| 3x commit_damage.behind (mean) | bot only | 218.918 [122.662, 315.174]; n=61, C=28; total=13354, den=61.000 | unavailable |
| 1x commit_damage.level (mean) | bot only | 523.798 [403.584, 644.011]; n=331, C=216; total=173377, den=331.000 | unavailable |
| 2x commit_damage.level (mean) | bot only | 518.282 [339.530, 697.035]; n=177, C=89; total=91736, den=177.000 | unavailable |
| 3x commit_damage.level (mean) | bot only | 401.000 [199.457, 602.543]; n=32, C=16; total=12832, den=32.000 | unavailable |
| 1x commit_full.ahead (per_minute) | bot only | 0.865 [0.708, 1.022]; n=196, C=196; total=101, den=116.761 | unavailable |
| 2x commit_full.ahead (per_minute) | bot only | 1.574 [1.253, 1.896]; n=97, C=97; total=96, den=60.974 | unavailable |
| 3x commit_full.ahead (per_minute) | bot only | 2.139 [1.596, 2.682]; n=14, C=14; total=13, den=6.077 | unavailable |
| 1x commit_full.behind (per_minute) | bot only | 0.876 [0.771, 0.982]; n=269, C=269; total=214, den=244.187 | unavailable |
| 2x commit_full.behind (per_minute) | bot only | 1.906 [1.750, 2.061]; n=308, C=308; total=491, den=257.654 | unavailable |
| 3x commit_full.behind (per_minute) | bot only | 2.183 [1.743, 2.623]; n=51, C=51; total=61, den=27.942 | unavailable |
| 1x commit_full.level (per_minute) | bot only | 1.058 [0.964, 1.153]; n=344, C=344; total=331, den=312.736 | unavailable |
| 2x commit_full.level (per_minute) | bot only | 1.869 [1.622, 2.115]; n=169, C=169; total=177, den=94.712 | unavailable |
| 3x commit_full.level (per_minute) | bot only | 2.355 [1.723, 2.987]; n=26, C=26; total=32, den=13.586 | unavailable |
| 1x cycle_assessed (per_minute) | bot only | 1.332 [1.255, 1.408]; n=373, C=373; total=916, den=687.816 | unavailable |
| 2x cycle_assessed (per_minute) | bot only | 2.376 [2.224, 2.528]; n=345, C=345; total=1024, den=431.012 | unavailable |
| 3x cycle_assessed (per_minute) | bot only | 3.897 [3.424, 4.371]; n=74, C=74; total=196, den=50.291 | unavailable |
| 1x cycle_candidates (per_minute) | bot only | 1.522 [1.445, 1.599]; n=373, C=373; total=1047, den=687.816 | unavailable |
| 2x cycle_candidates (per_minute) | bot only | 2.870 [2.719, 3.021]; n=345, C=345; total=1237, den=431.012 | unavailable |
| 3x cycle_candidates (per_minute) | bot only | 4.872 [4.325, 5.419]; n=74, C=74; total=245, den=50.291 | unavailable |
| 1x cycle_elixir_at_play (mean) | bot only | 5.994 [5.383, 6.606]; n=95, C=86; total=569.452, den=95.000 | unavailable |
| 2x cycle_elixir_at_play (mean) | bot only | 4.961 [4.514, 5.409]; n=117, C=93; total=580.488, den=117.000 | unavailable |
| 3x cycle_elixir_at_play (mean) | bot only | 5.032 [4.224, 5.839]; n=28, C=24; total=140.888, den=28.000 | unavailable |
| 1x cycle_empty (per_minute) | bot only | 0.138 [0.111, 0.165]; n=373, C=373; total=95, den=687.816 | unavailable |
| 2x cycle_empty (per_minute) | bot only | 0.271 [0.221, 0.322]; n=345, C=345; total=117, den=431.012 | unavailable |
| 3x cycle_empty (per_minute) | bot only | 0.557 [0.379, 0.734]; n=74, C=74; total=28, den=50.291 | unavailable |
| 1x cycle_empty_elixir (per_minute) | bot only | 0.144 [0.115, 0.173]; n=373, C=373; total=99, den=687.816 | unavailable |
| 2x cycle_empty_elixir (per_minute) | bot only | 0.290 [0.234, 0.346]; n=345, C=345; total=125, den=431.012 | unavailable |
| 3x cycle_empty_elixir (per_minute) | bot only | 0.577 [0.383, 0.770]; n=74, C=74; total=29, den=50.291 | unavailable |
| 1x kill_assessed (per_minute) | bot only | 0.182 [0.147, 0.216]; n=373, C=373; total=125, den=687.816 | unavailable |
| 2x kill_assessed (per_minute) | bot only | 0.353 [0.273, 0.432]; n=345, C=345; total=152, den=431.012 | unavailable |
| 3x kill_assessed (per_minute) | bot only | 0.477 [0.229, 0.726]; n=74, C=74; total=24, den=50.291 | unavailable |
| 1x kill_pushes (per_minute) | bot only | 0.279 [0.235, 0.323]; n=373, C=373; total=192, den=687.816 | unavailable |
| 2x kill_pushes (per_minute) | bot only | 0.548 [0.451, 0.644]; n=345, C=345; total=236, den=431.012 | unavailable |
| 3x kill_pushes (per_minute) | bot only | 0.815 [0.479, 1.151]; n=74, C=74; total=41, den=50.291 | unavailable |
| 1x kill_supports_first (per_minute) | bot only | 0.081 [0.059, 0.104]; n=373, C=373; total=56, den=687.816 | unavailable |
| 2x kill_supports_first (per_minute) | bot only | 0.181 [0.131, 0.231]; n=345, C=345; total=78, den=431.012 | unavailable |
| 3x kill_supports_first (per_minute) | bot only | 0.258 [0.095, 0.422]; n=74, C=74; total=13, den=50.291 | unavailable |
| 1x kill_supports_first_fraction (fraction) | bot only | 0.448 [0.345, 0.556]; n=125, C=97; total=56, den=125.000 | unavailable |
| 2x kill_supports_first_fraction (fraction) | bot only | 0.513 [0.388, 0.637]; n=152, C=81; total=78, den=152.000 | unavailable |
| 3x kill_supports_first_fraction (fraction) | bot only | 0.542 [0.271, 0.812]; n=24, C=15; total=13, den=24.000 | unavailable |
| 1x pressure_complete (per_minute) | bot vs icebow-like humans | 1.889 [1.766, 2.011]; n=373, C=373; total=1299, den=687.816 | 1.642 [1.369, 1.915]; n=31, C=31; total=101, den=61.517 |
| 2x pressure_complete (per_minute) | bot vs icebow-like humans | 1.810 [1.616, 2.004]; n=345, C=345; total=780, den=431.012 | 2.315 [1.809, 2.820]; n=30, C=30; total=122, den=52.706 |
| 3x pressure_complete (per_minute) | bot vs icebow-like humans | 1.710 [1.075, 2.345]; n=74, C=74; total=86, den=50.291 | 0.993 [0.490, 1.497]; n=23, C=23; total=18, den=18.118 |
| 1x pressure_elixir (mean) | bot only | 6.765 [6.618, 6.911]; n=1299, C=361; total=8787.56, den=1299.000 | unavailable |
| 2x pressure_elixir (mean) | bot only | 5.221 [5.037, 5.405]; n=780, C=248; total=4072.3, den=780.000 | unavailable |
| 3x pressure_elixir (mean) | bot only | 4.230 [3.623, 4.836]; n=86, C=29; total=363.759, den=86.000 | unavailable |
| 1x pressure_response_elixir (mean) | bot only | 8.233 [8.008, 8.458]; n=235, C=178; total=1934.79, den=235.000 | unavailable |
| 2x pressure_response_elixir (mean) | bot only | 6.728 [6.452, 7.005]; n=193, C=123; total=1298.55, den=193.000 | unavailable |
| 3x pressure_response_elixir (mean) | bot only | 6.030 [5.058, 7.003]; n=24, C=13; total=144.73, den=24.000 | unavailable |
| 1x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.181 [0.139, 0.232]; n=1299, C=361; total=235, den=1299.000 | 0.069 [0.015, 0.234]; n=101, C=31; total=7, den=101.000 |
| 2x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.247 [0.185, 0.323]; n=780, C=248; total=193, den=780.000 | 0.205 [0.085, 0.417]; n=122, C=28; total=25, den=122.000 |
| 3x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.279 [0.126, 0.510]; n=86, C=29; total=24, den=86.000 | 0.222 [0.021, 0.547]; n=18, C=11; total=4, den=18.000 |
| 1x pressure_responses (per_minute) | bot vs icebow-like humans | 0.342 [0.299, 0.384]; n=373, C=373; total=235, den=687.816 | 0.114 [0.026, 0.202]; n=31, C=31; total=7, den=61.517 |
| 2x pressure_responses (per_minute) | bot vs icebow-like humans | 0.448 [0.372, 0.524]; n=345, C=345; total=193, den=431.012 | 0.474 [0.279, 0.670]; n=30, C=30; total=25, den=52.706 |
| 3x pressure_responses (per_minute) | bot vs icebow-like humans | 0.477 [0.201, 0.753]; n=74, C=74; total=24, den=50.291 | 0.221 [0.028, 0.414]; n=23, C=23; total=4, den=18.118 |
| 1x pressure_windows (per_minute) | bot vs icebow-like humans | 1.909 [1.784, 2.033]; n=373, C=373; total=1313, den=687.816 | 1.642 [1.369, 1.915]; n=31, C=31; total=101, den=61.517 |
| 2x pressure_windows (per_minute) | bot vs icebow-like humans | 1.907 [1.707, 2.107]; n=345, C=345; total=822, den=431.012 | 2.315 [1.809, 2.820]; n=30, C=30; total=122, den=52.706 |
| 3x pressure_windows (per_minute) | bot vs icebow-like humans | 1.988 [1.254, 2.723]; n=74, C=74; total=100, den=50.291 | 1.049 [0.557, 1.540]; n=23, C=23; total=19, den=18.118 |
| 1x pull_centre (per_minute) | bot only | 0.846 [0.778, 0.914]; n=373, C=373; total=582, den=687.816 | unavailable |
| 2x pull_centre (per_minute) | bot only | 2.167 [2.000, 2.334]; n=345, C=345; total=934, den=431.012 | unavailable |
| 3x pull_centre (per_minute) | bot only | 3.102 [2.438, 3.766]; n=74, C=74; total=156, den=50.291 | unavailable |
| 1x pull_inward_offset (mean) | bot only | 1.753 [1.594, 1.913]; n=1254, C=360; total=2198.86, den=1254.000 | unavailable |
| 2x pull_inward_offset (mean) | bot only | 1.712 [1.573, 1.851]; n=1935, C=319; total=3312.66, den=1935.000 | unavailable |
| 3x pull_inward_offset (mean) | bot only | 1.485 [1.072, 1.897]; n=345, C=64; total=512.168, den=345.000 | unavailable |
| 1x pull_offset (mean) | bot only | 2.496 [2.376, 2.616]; n=1254, C=360; total=3129.94, den=1254.000 | unavailable |
| 2x pull_offset (mean) | bot only | 2.603 [2.503, 2.702]; n=1935, C=319; total=5036.29, den=1935.000 | unavailable |
| 3x pull_offset (mean) | bot only | 2.599 [2.304, 2.893]; n=345, C=64; total=896.554, den=345.000 | unavailable |
| 1x pull_placements (per_minute) | bot only | 1.823 [1.727, 1.919]; n=373, C=373; total=1254, den=687.816 | unavailable |
| 2x pull_placements (per_minute) | bot only | 4.489 [4.262, 4.717]; n=345, C=345; total=1935, den=431.012 | unavailable |
| 3x pull_placements (per_minute) | bot only | 6.860 [5.976, 7.744]; n=74, C=74; total=345, den=50.291 | unavailable |
| 1x pull_side (per_minute) | bot only | 0.977 [0.901, 1.053]; n=373, C=373; total=672, den=687.816 | unavailable |
| 2x pull_side (per_minute) | bot only | 2.322 [2.167, 2.478]; n=345, C=345; total=1001, den=431.012 | unavailable |
| 3x pull_side (per_minute) | bot only | 3.758 [3.147, 4.369]; n=74, C=74; total=189, den=50.291 | unavailable |
| 1x tank_complete (per_minute) | bot only | 0.513 [0.448, 0.579]; n=373, C=373; total=353, den=687.816 | unavailable |
| 2x tank_complete (per_minute) | bot only | 0.543 [0.432, 0.654]; n=345, C=345; total=234, den=431.012 | unavailable |
| 3x tank_complete (per_minute) | bot only | 0.676 [0.373, 0.979]; n=74, C=74; total=34, den=50.291 | unavailable |
| 1x tank_crossings (per_minute) | bot only | 0.704 [0.624, 0.784]; n=373, C=373; total=484, den=687.816 | unavailable |
| 2x tank_crossings (per_minute) | bot only | 0.991 [0.840, 1.141]; n=345, C=345; total=427, den=431.012 | unavailable |
| 3x tank_crossings (per_minute) | bot only | 1.153 [0.712, 1.595]; n=74, C=74; total=58, den=50.291 | unavailable |
| 1x tank_preexisting_tesla (fraction) | bot only | 0.366 [0.296, 0.441]; n=484, C=221; total=177, den=484.000 | unavailable |
| 2x tank_preexisting_tesla (fraction) | bot only | 0.431 [0.339, 0.528]; n=427, C=154; total=184, den=427.000 | unavailable |
| 3x tank_preexisting_tesla (fraction) | bot only | 0.603 [0.377, 0.793]; n=58, C=23; total=35, den=58.000 | unavailable |
| 1x tank_tesla_delay (mean) | bot only | 7.756 [5.460, 10.051]; n=68, C=54; total=527.4, den=68.000 | unavailable |
| 2x tank_tesla_delay (mean) | bot only | 7.773 [6.406, 9.139]; n=136, C=78; total=1057.1, den=136.000 | unavailable |
| 3x tank_tesla_delay (mean) | bot only | 4.877 [3.209, 6.545]; n=24, C=17; total=117.05, den=24.000 | unavailable |
| 1x tank_tesla_response (per_minute) | bot only | 0.099 [0.070, 0.127]; n=373, C=373; total=68, den=687.816 | unavailable |
| 2x tank_tesla_response (per_minute) | bot only | 0.316 [0.240, 0.391]; n=345, C=345; total=136, den=431.012 | unavailable |
| 3x tank_tesla_response (per_minute) | bot only | 0.477 [0.260, 0.694]; n=74, C=74; total=24, den=50.291 | unavailable |
| 1x tank_tesla_survival (fraction) | bot only | 0.473 [0.321, 0.630]; n=55, C=46; total=26, den=55.000 | unavailable |
| 2x tank_tesla_survival (fraction) | bot only | 0.562 [0.402, 0.710]; n=89, C=49; total=50, den=89.000 | unavailable |
| 3x tank_tesla_survival (fraction) | bot only | 0.706 [0.432, 0.928]; n=17, C=14; total=12, den=17.000 | unavailable |
| 1x xbow.Balloon (per_minute) | bot vs icebow-like humans | 0.724 [0.547, 0.901]; n=14, C=14; total=19, den=26.242 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Balloon (per_minute) | bot vs icebow-like humans | 1.312 [0.949, 1.675]; n=14, C=14; total=20, den=15.244 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Balloon (per_minute) | bot vs icebow-like humans | 1.569 [0.000, 4.382]; n=3, C=3; total=4, den=2.549 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 0.532 [0.336, 0.729]; n=16, C=16; total=15, den=28.182 | 1.000 [95% CI not estimable]; n=1, C=1; total=2, den=2.000 |
| 2x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 0.972 [0.597, 1.347]; n=14, C=14; total=16, den=16.461 | 1.000 [95% CI not estimable]; n=1, C=1; total=2, den=2.000 |
| 3x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 2.000 [0.040, 3.960]; n=2, C=2; total=4, den=2.000 | 2.000 [95% CI not estimable]; n=1, C=1; total=2, den=1.000 |
| 1x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 1.029 [0.857, 1.201]; n=14, C=14; total=27, den=26.242 | 0.500 [0.000, 1.480]; n=2, C=2; total=2, den=4.000 |
| 2x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 0.660 [0.449, 0.871]; n=14, C=14; total=12, den=18.182 | 1.250 [0.760, 1.740]; n=2, C=2; total=5, den=4.000 |
| 3x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 1.664]; n=3, C=3; total=0, den=2.217 | 0.000 [0.000, 3.596]; n=2, C=2; total=0, den=1.026 |
| 1x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 0.807 [0.668, 0.946]; n=40, C=40; total=60, den=74.350 | unavailable |
| 2x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 1.131 [0.899, 1.363]; n=37, C=37; total=47, den=41.542 | unavailable |
| 3x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 1.538 [0.803, 2.273]; n=6, C=6; total=4, den=2.601 | unavailable |
| 1x xbow.Giant (per_minute) | bot vs icebow-like humans | 0.677 [0.472, 0.883]; n=14, C=14; total=17, den=25.103 | 0.750 [0.000, 2.220]; n=2, C=2; total=3, den=4.000 |
| 2x xbow.Giant (per_minute) | bot vs icebow-like humans | 1.568 [1.133, 2.002]; n=12, C=12; total=22, den=14.035 | 1.627 [0.436, 2.817]; n=2, C=2; total=4, den=2.459 |
| 3x xbow.Giant (per_minute) | bot vs icebow-like humans | 0.621 [0.000, 2.133]; n=2, C=2; total=1, den=1.610 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.117 |
| 1x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 0.694 [0.587, 0.801]; n=37, C=37; total=48, den=69.159 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 1.309 [1.119, 1.498]; n=35, C=35; total=58, den=44.325 | 2.500 [95% CI not estimable]; n=1, C=1; total=5, den=2.000 |
| 3x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 0.868 [0.059, 1.677]; n=7, C=7; total=5, den=5.762 | 2.000 [95% CI not estimable]; n=1, C=1; total=2, den=1.000 |
| 1x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | 0.533 [0.000, 1.137]; n=3, C=3; total=3, den=5.624 | 0.750 [0.260, 1.240]; n=2, C=2; total=3, den=4.000 |
| 2x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | 1.699 [0.834, 2.564]; n=3, C=3; total=7, den=4.121 | 1.750 [1.260, 2.240]; n=2, C=2; total=7, den=4.000 |
| 3x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | 1.471 [0.000, 3.488]; n=2, C=2; total=2, den=1.360 |
| 1x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 0.805 [0.563, 1.047]; n=14, C=14; total=21, den=26.093 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 2x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 1.205 [0.827, 1.582]; n=13, C=13; total=18, den=14.943 | 0.500 [95% CI not estimable]; n=1, C=1; total=1, den=2.000 |
| 3x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 2.584]; n=2, C=2; total=0, den=1.427 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.934 |
| 1x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | 0.533 [95% CI not estimable]; n=1, C=1; total=1, den=1.875 | unavailable |
| 2x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | 1.934 [95% CI not estimable]; n=1, C=1; total=2, den=1.034 | unavailable |
| 3x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Golem (per_minute) | bot vs icebow-like humans | 0.798 [0.655, 0.941]; n=27, C=27; total=39, den=48.852 | unavailable |
| 2x xbow.Golem (per_minute) | bot vs icebow-like humans | 0.877 [0.694, 1.060]; n=24, C=24; total=25, den=28.501 | unavailable |
| 3x xbow.Golem (per_minute) | bot vs icebow-like humans | 0.746 [0.365, 1.126]; n=5, C=5; total=2, den=2.682 | unavailable |
| 1x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 0.889 [0.715, 1.063]; n=9, C=9; total=15, den=16.872 | 1.000 [1.000, 1.000]; n=2, C=2; total=4, den=4.000 |
| 2x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 1.173 [0.697, 1.649]; n=9, C=9; total=18, den=15.345 | 1.250 [0.000, 2.720]; n=2, C=2; total=5, den=4.000 |
| 3x xbow.Graveyard (per_minute) | bot vs icebow-like humans | 1.523 [0.964, 2.083]; n=6, C=6; total=6, den=3.938 | 0.000 [0.000, 3.229]; n=2, C=2; total=0, den=1.143 |
| 1x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.617 [0.501, 0.734]; n=46, C=46; total=53, den=85.835 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=2.000 |
| 2x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.945 [0.779, 1.110]; n=45, C=45; total=58, den=61.383 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=2.000 |
| 3x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.224 [0.000, 0.506]; n=13, C=13; total=2, den=8.918 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.951 |
| 1x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 0.990 [0.849, 1.131]; n=11, C=11; total=20, den=20.204 | unavailable |
| 2x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 1.225 [0.749, 1.702]; n=9, C=9; total=10, den=8.161 | unavailable |
| 3x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 0.533 [0.305, 0.762]; n=7, C=7; total=7, den=13.123 | unavailable |
| 2x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 1.265 [0.925, 1.606]; n=7, C=7; total=13, den=10.275 | unavailable |
| 3x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | 1.000 [95% CI not estimable]; n=1, C=1; total=1, den=1.000 | unavailable |
| 1x xbow.Miner (per_minute) | bot vs icebow-like humans | 0.834 [0.476, 1.193]; n=6, C=6; total=9, den=10.787 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Miner (per_minute) | bot vs icebow-like humans | 1.479 [1.053, 1.905]; n=5, C=5; total=12, den=8.113 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Miner (per_minute) | bot vs icebow-like humans | 0.561 [0.000, 1.526]; n=2, C=2; total=1, den=1.783 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Mortar (per_minute) | bot vs icebow-like humans | 0.758 [0.574, 0.942]; n=19, C=19; total=27, den=35.618 | 0.167 [0.000, 0.493]; n=3, C=3; total=1, den=6.000 |
| 2x xbow.Mortar (per_minute) | bot vs icebow-like humans | 1.234 [0.997, 1.471]; n=19, C=19; total=28, den=22.686 | 0.975 [0.126, 1.824]; n=3, C=3; total=4, den=4.102 |
| 3x xbow.Mortar (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.388 | 2.000 [95% CI not estimable]; n=1, C=1; total=2, den=1.000 |
| 1x xbow.Other (per_minute) | bot vs icebow-like humans | 0.773 [0.578, 0.967]; n=20, C=20; total=28, den=36.245 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 2x xbow.Other (per_minute) | bot vs icebow-like humans | 1.236 [0.936, 1.536]; n=17, C=17; total=28, den=22.648 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 3x xbow.Other (per_minute) | bot vs icebow-like humans | 1.752 [0.942, 2.561]; n=6, C=6; total=8, den=4.567 | 1.000 [95% CI not estimable]; n=1, C=1; total=1, den=1.000 |
| 1x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 0.827 [0.268, 1.386]; n=4, C=4; total=6, den=7.254 | unavailable |
| 2x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 0.904 [0.701, 1.107]; n=2, C=2; total=1, den=1.106 | unavailable |
| 3x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 0.534 [0.289, 0.778]; n=11, C=11; total=11, den=20.618 | 1.000 [95% CI not estimable]; n=1, C=1; total=2, den=2.000 |
| 2x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 0.611 [0.334, 0.889]; n=11, C=11; total=10, den=16.354 | 2.500 [95% CI not estimable]; n=1, C=1; total=5, den=2.000 |
| 3x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 2.995]; n=3, C=3; total=0, den=1.232 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 |
| 1x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 0.711 [0.409, 1.013]; n=9, C=9; total=12, den=16.871 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=2.000 |
| 2x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 1.297 [0.956, 1.639]; n=9, C=9; total=16, den=12.333 | 2.000 [95% CI not estimable]; n=1, C=1; total=4, den=2.000 |
| 3x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 1.430 [0.000, 3.255]; n=2, C=2; total=1, den=0.699 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.976 |
| 1x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 0.758 [0.592, 0.924]; n=19, C=19; total=27, den=35.618 | 0.812 [0.555, 1.070]; n=8, C=8; total=13, den=16.000 |
| 2x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 1.424 [1.142, 1.706]; n=19, C=19; total=30, den=21.070 | 1.153 [0.450, 1.855]; n=8, C=8; total=14, den=12.145 |
| 3x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 0.686 [0.000, 1.531]; n=2, C=2; total=1, den=1.458 | 1.675 [0.666, 2.684]; n=4, C=4; total=5, den=2.985 |
| 1x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | 0.800 [0.277, 1.323]; n=2, C=2; total=3, den=3.749 | 1.000 [1.000, 1.000]; n=3, C=3; total=6, den=6.000 |
| 2x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | 1.749 [0.890, 2.609]; n=2, C=2; total=4, den=2.287 | 1.833 [1.507, 2.160]; n=3, C=3; total=11, den=6.000 |
| 3x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | 1.717 [95% CI not estimable]; n=1, C=1; total=1, den=0.583 | 1.834 [0.000, 4.191]; n=3, C=3; total=5, den=2.726 |
| 1x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 0.325 [0.041, 0.609]; n=9, C=9; total=5, den=15.400 | unavailable |
| 2x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 0.967 [0.492, 1.441]; n=7, C=7; total=8, den=8.276 | unavailable |
| 3x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 2.000 [95% CI not estimable]; n=1, C=1; total=2, den=1.000 | unavailable |
| 1x xbow.Sparky (per_minute) | bot vs icebow-like humans | 0.682 [0.415, 0.950]; n=4, C=4; total=5, den=7.328 | unavailable |
| 2x xbow.Sparky (per_minute) | bot vs icebow-like humans | 2.075 [1.644, 2.506]; n=2, C=2; total=5, den=2.410 | unavailable |
| 3x xbow.Sparky (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 0.776 [0.569, 0.983]; n=7, C=7; total=10, den=12.887 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 2x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 1.829 [1.350, 2.308]; n=6, C=6; total=16, den=8.747 | 1.500 [95% CI not estimable]; n=1, C=1; total=3, den=2.000 |
| 3x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 1.174 [0.674, 1.674]; n=3, C=3; total=2, den=1.703 | 3.330 [95% CI not estimable]; n=1, C=1; total=3, den=0.901 |
| 1x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 0.502 [0.097, 0.907]; n=8, C=8; total=7, den=13.935 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.517 |
| 2x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 1.397 [0.982, 1.812]; n=7, C=7; total=13, den=9.306 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 1.702 [0.708, 2.696]; n=2, C=2; total=2, den=1.175 | unavailable; n=0; 95% CI not estimable |
| 1x xbow.X-Bow (per_minute) | bot vs icebow-like humans | 0.800 [0.277, 1.323]; n=2, C=2; total=3, den=3.750 | unavailable |
| 2x xbow.X-Bow (per_minute) | bot vs icebow-like humans | 1.412 [0.496, 2.328]; n=2, C=2; total=3, den=2.125 | unavailable |
| 3x xbow.X-Bow (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Balloon (mean) | bot only | 1105.692 [473.014, 1738.371]; n=13, C=11; total=14374, den=13.000 | unavailable |
| 2x xbow_damage.Balloon (mean) | bot only | 590.667 [236.487, 944.846]; n=12, C=9; total=7088, den=12.000 | unavailable |
| 3x xbow_damage.Balloon (mean) | bot only | 555.333 [95% CI not estimable]; n=3, C=1; total=1666, den=3.000 | unavailable |
| 1x xbow_damage.Battle Ram (mean) | bot only | 1466.273 [710.235, 2222.310]; n=11, C=10; total=16129, den=11.000 | unavailable |
| 2x xbow_damage.Battle Ram (mean) | bot only | 690.231 [1.869, 1378.592]; n=13, C=9; total=8973, den=13.000 | unavailable |
| 3x xbow_damage.Battle Ram (mean) | bot only | 544.500 [0.000, 1611.720]; n=2, C=2; total=1089, den=2.000 | unavailable |
| 1x xbow_damage.Electro Giant (mean) | bot only | 1135.556 [614.327, 1656.784]; n=18, C=12; total=20440, den=18.000 | unavailable |
| 2x xbow_damage.Electro Giant (mean) | bot only | 172.100 [6.670, 337.530]; n=10, C=9; total=1721, den=10.000 | unavailable |
| 3x xbow_damage.Electro Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Elixir Golem (mean) | bot only | 1789.250 [1452.545, 2125.955]; n=52, C=34; total=93041, den=52.000 | unavailable |
| 2x xbow_damage.Elixir Golem (mean) | bot only | 938.737 [521.741, 1355.732]; n=38, C=25; total=35672, den=38.000 | unavailable |
| 3x xbow_damage.Elixir Golem (mean) | bot only | 795.000 [0.000, 1795.216]; n=4, C=3; total=3180, den=4.000 | unavailable |
| 1x xbow_damage.Giant (mean) | bot only | 1915.071 [1229.032, 2601.111]; n=14, C=11; total=26811, den=14.000 | unavailable |
| 2x xbow_damage.Giant (mean) | bot only | 872.412 [291.909, 1452.915]; n=17, C=9; total=14831, den=17.000 | unavailable |
| 3x xbow_damage.Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Barrel (mean) | bot only | 952.833 [536.275, 1369.392]; n=36, C=29; total=34302, den=36.000 | unavailable |
| 2x xbow_damage.Goblin Barrel (mean) | bot only | 464.419 [202.778, 726.060]; n=43, C=25; total=19970, den=43.000 | unavailable |
| 3x xbow_damage.Goblin Barrel (mean) | bot only | 1666.000 [0.000, 3381.000]; n=2, C=2; total=3332, den=2.000 | unavailable |
| 1x xbow_damage.Goblin Drill (mean) | bot only | 273.000 [95% CI not estimable]; n=2, C=1; total=546, den=2.000 | unavailable |
| 2x xbow_damage.Goblin Drill (mean) | bot only | 474.833 [0.000, 1111.255]; n=6, C=3; total=2849, den=6.000 | unavailable |
| 3x xbow_damage.Goblin Drill (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Giant (mean) | bot only | 2047.778 [1403.770, 2691.786]; n=18, C=11; total=36860, den=18.000 | unavailable |
| 2x xbow_damage.Goblin Giant (mean) | bot only | 540.000 [102.086, 977.914]; n=11, C=7; total=5940, den=11.000 | unavailable |
| 3x xbow_damage.Goblin Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Machine (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Goblin Machine (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Goblin Machine (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Goblinstein (mean) | bot only | 25.500 [95% CI not estimable]; n=2, C=1; total=51, den=2.000 | unavailable |
| 3x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Golem (mean) | bot only | 2415.722 [2077.897, 2753.547]; n=36, C=24; total=86966, den=36.000 | unavailable |
| 2x xbow_damage.Golem (mean) | bot only | 832.105 [230.413, 1433.797]; n=19, C=16; total=15810, den=19.000 | unavailable |
| 3x xbow_damage.Golem (mean) | bot only | 51.000 [95% CI not estimable]; n=1, C=1; total=51, den=1.000 | unavailable |
| 1x xbow_damage.Graveyard (mean) | bot only | 1826.538 [1035.125, 2617.952]; n=13, C=9; total=23745, den=13.000 | unavailable |
| 2x xbow_damage.Graveyard (mean) | bot only | 325.833 [43.105, 608.562]; n=12, C=8; total=3910, den=12.000 | unavailable |
| 3x xbow_damage.Graveyard (mean) | bot only | 17.000 [0.000, 50.320]; n=3, C=3; total=51, den=3.000 | unavailable |
| 1x xbow_damage.Hog Rider (mean) | bot only | 1090.718 [687.003, 1494.433]; n=39, C=27; total=42538, den=39.000 | unavailable |
| 2x xbow_damage.Hog Rider (mean) | bot only | 957.900 [532.693, 1383.107]; n=40, C=27; total=38316, den=40.000 | unavailable |
| 3x xbow_damage.Hog Rider (mean) | bot only | 25.500 [0.000, 75.480]; n=2, C=2; total=51, den=2.000 | unavailable |
| 1x xbow_damage.Lava Hound (mean) | bot only | 1888.562 [1119.659, 2657.466]; n=16, C=11; total=30217, den=16.000 | unavailable |
| 2x xbow_damage.Lava Hound (mean) | bot only | 857.125 [299.177, 1415.073]; n=8, C=5; total=6857, den=8.000 | unavailable |
| 3x xbow_damage.Lava Hound (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Mega Knight (mean) | bot only | 1459.667 [383.060, 2536.273]; n=6, C=6; total=8758, den=6.000 | unavailable |
| 2x xbow_damage.Mega Knight (mean) | bot only | 311.727 [0.000, 671.479]; n=11, C=7; total=3429, den=11.000 | unavailable |
| 3x xbow_damage.Mega Knight (mean) | bot only | 51.000 [95% CI not estimable]; n=1, C=1; total=51, den=1.000 | unavailable |
| 1x xbow_damage.Miner (mean) | bot only | 933.833 [436.093, 1431.573]; n=6, C=3; total=5603, den=6.000 | unavailable |
| 2x xbow_damage.Miner (mean) | bot only | 971.778 [162.488, 1781.068]; n=9, C=5; total=8746, den=9.000 | unavailable |
| 3x xbow_damage.Miner (mean) | bot only | 497.000 [95% CI not estimable]; n=1, C=1; total=497, den=1.000 | unavailable |
| 1x xbow_damage.Mortar (mean) | bot only | 1724.053 [1045.440, 2402.665]; n=19, C=15; total=32757, den=19.000 | unavailable |
| 2x xbow_damage.Mortar (mean) | bot only | 1230.800 [476.960, 1984.640]; n=15, C=12; total=18462, den=15.000 | unavailable |
| 3x xbow_damage.Mortar (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Other (mean) | bot only | 687.500 [98.570, 1276.430]; n=16, C=11; total=11000, den=16.000 | unavailable |
| 2x xbow_damage.Other (mean) | bot only | 732.250 [284.208, 1180.292]; n=24, C=12; total=17574, den=24.000 | unavailable |
| 3x xbow_damage.Other (mean) | bot only | 224.667 [0.000, 449.599]; n=6, C=4; total=1348, den=6.000 | unavailable |
| 1x xbow_damage.P.E.K.K.A (mean) | bot only | 936.333 [860.982, 1011.684]; n=3, C=2; total=2809, den=3.000 | unavailable |
| 2x xbow_damage.P.E.K.K.A (mean) | bot only | 3011.000 [95% CI not estimable]; n=1, C=1; total=3011, den=1.000 | unavailable |
| 3x xbow_damage.P.E.K.K.A (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Ram Rider (mean) | bot only | 1460.000 [310.085, 2609.915]; n=8, C=5; total=11680, den=8.000 | unavailable |
| 2x xbow_damage.Ram Rider (mean) | bot only | 1025.833 [134.078, 1917.589]; n=6, C=4; total=6155, den=6.000 | unavailable |
| 3x xbow_damage.Ram Rider (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Royal Giant (mean) | bot only | 836.000 [238.257, 1433.743]; n=8, C=6; total=6688, den=8.000 | unavailable |
| 2x xbow_damage.Royal Giant (mean) | bot only | 702.455 [0.000, 1429.776]; n=11, C=8; total=7727, den=11.000 | unavailable |
| 3x xbow_damage.Royal Giant (mean) | bot only | 1608.000 [95% CI not estimable]; n=1, C=1; total=1608, den=1.000 | unavailable |
| 1x xbow_damage.Royal Hogs (mean) | bot only | 860.526 [304.257, 1416.796]; n=19, C=13; total=16350, den=19.000 | unavailable |
| 2x xbow_damage.Royal Hogs (mean) | bot only | 1085.045 [566.561, 1603.530]; n=22, C=13; total=23871, den=22.000 | unavailable |
| 3x xbow_damage.Royal Hogs (mean) | bot only | 51.000 [95% CI not estimable]; n=1, C=1; total=51, den=1.000 | unavailable |
| 1x xbow_damage.Rune Giant (mean) | bot only | 1838.500 [0.000, 5342.000]; n=2, C=2; total=3677, den=2.000 | unavailable |
| 2x xbow_damage.Rune Giant (mean) | bot only | 224.250 [95% CI not estimable]; n=4, C=1; total=897, den=4.000 | unavailable |
| 3x xbow_damage.Rune Giant (mean) | bot only | 51.000 [95% CI not estimable]; n=1, C=1; total=51, den=1.000 | unavailable |
| 1x xbow_damage.Skeleton Barrel (mean) | bot only | 1798.000 [1458.267, 2137.733]; n=3, C=2; total=5394, den=3.000 | unavailable |
| 2x xbow_damage.Skeleton Barrel (mean) | bot only | 963.400 [0.000, 2575.360]; n=5, C=4; total=4817, den=5.000 | unavailable |
| 3x xbow_damage.Skeleton Barrel (mean) | bot only | 546.000 [95% CI not estimable]; n=1, C=1; total=546, den=1.000 | unavailable |
| 1x xbow_damage.Sparky (mean) | bot only | 1486.000 [17.005, 2954.995]; n=4, C=4; total=5944, den=4.000 | unavailable |
| 2x xbow_damage.Sparky (mean) | bot only | 17.000 [0.000, 61.427]; n=3, C=2; total=51, den=3.000 | unavailable |
| 3x xbow_damage.Sparky (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Three Musketeers (mean) | bot only | 1685.800 [927.502, 2444.098]; n=10, C=7; total=16858, den=10.000 | unavailable |
| 2x xbow_damage.Three Musketeers (mean) | bot only | 296.308 [0.000, 876.772]; n=13, C=4; total=3852, den=13.000 | unavailable |
| 3x xbow_damage.Three Musketeers (mean) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 1x xbow_damage.Wall Breakers (mean) | bot only | 2046.400 [1157.107, 2935.693]; n=5, C=3; total=10232, den=5.000 | unavailable |
| 2x xbow_damage.Wall Breakers (mean) | bot only | 1022.600 [0.000, 2103.055]; n=10, C=6; total=10226, den=10.000 | unavailable |
| 3x xbow_damage.Wall Breakers (mean) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 1x xbow_damage.X-Bow (mean) | bot only | 2203.333 [1174.116, 3232.551]; n=3, C=2; total=6610, den=3.000 | unavailable |
| 2x xbow_damage.X-Bow (mean) | bot only | 2173.000 [402.467, 3943.533]; n=3, C=2; total=6519, den=3.000 | unavailable |
| 3x xbow_damage.X-Bow (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Balloon (per_minute) | bot only | 0.495 [0.323, 0.667]; n=14, C=14; total=13, den=26.242 | unavailable |
| 2x xbow_full.Balloon (per_minute) | bot only | 0.787 [0.514, 1.061]; n=14, C=14; total=12, den=15.244 | unavailable |
| 3x xbow_full.Balloon (per_minute) | bot only | 1.177 [0.000, 3.287]; n=3, C=3; total=3, den=2.549 | unavailable |
| 1x xbow_full.Battle Ram (per_minute) | bot only | 0.390 [0.222, 0.558]; n=16, C=16; total=11, den=28.182 | unavailable |
| 2x xbow_full.Battle Ram (per_minute) | bot only | 0.790 [0.419, 1.161]; n=14, C=14; total=13, den=16.461 | unavailable |
| 3x xbow_full.Battle Ram (per_minute) | bot only | 1.000 [1.000, 1.000]; n=2, C=2; total=2, den=2.000 | unavailable |
| 1x xbow_full.Electro Giant (per_minute) | bot only | 0.686 [0.455, 0.917]; n=14, C=14; total=18, den=26.242 | unavailable |
| 2x xbow_full.Electro Giant (per_minute) | bot only | 0.550 [0.332, 0.768]; n=14, C=14; total=10, den=18.182 | unavailable |
| 3x xbow_full.Electro Giant (per_minute) | bot only | 0.000 [0.000, 1.664]; n=3, C=3; total=0, den=2.217 | unavailable |
| 1x xbow_full.Elixir Golem (per_minute) | bot only | 0.699 [0.569, 0.830]; n=40, C=40; total=52, den=74.350 | unavailable |
| 2x xbow_full.Elixir Golem (per_minute) | bot only | 0.915 [0.699, 1.130]; n=37, C=37; total=38, den=41.542 | unavailable |
| 3x xbow_full.Elixir Golem (per_minute) | bot only | 1.538 [0.803, 2.273]; n=6, C=6; total=4, den=2.601 | unavailable |
| 1x xbow_full.Giant (per_minute) | bot only | 0.558 [0.357, 0.758]; n=14, C=14; total=14, den=25.103 | unavailable |
| 2x xbow_full.Giant (per_minute) | bot only | 1.211 [0.735, 1.688]; n=12, C=12; total=17, den=14.035 | unavailable |
| 3x xbow_full.Giant (per_minute) | bot only | 0.000 [0.000, 2.291]; n=2, C=2; total=0, den=1.610 | unavailable |
| 1x xbow_full.Goblin Barrel (per_minute) | bot only | 0.521 [0.409, 0.632]; n=37, C=37; total=36, den=69.159 | unavailable |
| 2x xbow_full.Goblin Barrel (per_minute) | bot only | 0.970 [0.730, 1.211]; n=35, C=35; total=43, den=44.325 | unavailable |
| 3x xbow_full.Goblin Barrel (per_minute) | bot only | 0.347 [0.000, 0.776]; n=7, C=7; total=2, den=5.762 | unavailable |
| 1x xbow_full.Goblin Drill (per_minute) | bot only | 0.356 [0.000, 1.053]; n=3, C=3; total=2, den=5.624 | unavailable |
| 2x xbow_full.Goblin Drill (per_minute) | bot only | 1.456 [1.045, 1.867]; n=3, C=3; total=6, den=4.121 | unavailable |
| 3x xbow_full.Goblin Drill (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 1x xbow_full.Goblin Giant (per_minute) | bot only | 0.690 [0.456, 0.924]; n=14, C=14; total=18, den=26.093 | unavailable |
| 2x xbow_full.Goblin Giant (per_minute) | bot only | 0.736 [0.377, 1.095]; n=13, C=13; total=11, den=14.943 | unavailable |
| 3x xbow_full.Goblin Giant (per_minute) | bot only | 0.000 [0.000, 2.584]; n=2, C=2; total=0, den=1.427 | unavailable |
| 1x xbow_full.Goblin Machine (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.Goblin Machine (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Goblin Machine (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblinstein (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.875 | unavailable |
| 2x xbow_full.Goblinstein (per_minute) | bot only | 1.934 [95% CI not estimable]; n=1, C=1; total=2, den=1.034 | unavailable |
| 3x xbow_full.Goblinstein (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Golem (per_minute) | bot only | 0.737 [0.596, 0.878]; n=27, C=27; total=36, den=48.852 | unavailable |
| 2x xbow_full.Golem (per_minute) | bot only | 0.667 [0.511, 0.822]; n=24, C=24; total=19, den=28.501 | unavailable |
| 3x xbow_full.Golem (per_minute) | bot only | 0.373 [0.000, 0.981]; n=5, C=5; total=1, den=2.682 | unavailable |
| 1x xbow_full.Graveyard (per_minute) | bot only | 0.771 [0.587, 0.954]; n=9, C=9; total=13, den=16.872 | unavailable |
| 2x xbow_full.Graveyard (per_minute) | bot only | 0.782 [0.498, 1.066]; n=9, C=9; total=12, den=15.345 | unavailable |
| 3x xbow_full.Graveyard (per_minute) | bot only | 0.762 [0.364, 1.160]; n=6, C=6; total=3, den=3.938 | unavailable |
| 1x xbow_full.Hog Rider (per_minute) | bot only | 0.454 [0.329, 0.580]; n=46, C=46; total=39, den=85.835 | unavailable |
| 2x xbow_full.Hog Rider (per_minute) | bot only | 0.652 [0.485, 0.818]; n=45, C=45; total=40, den=61.383 | unavailable |
| 3x xbow_full.Hog Rider (per_minute) | bot only | 0.224 [0.000, 0.506]; n=13, C=13; total=2, den=8.918 | unavailable |
| 1x xbow_full.Lava Hound (per_minute) | bot only | 0.792 [0.630, 0.954]; n=11, C=11; total=16, den=20.204 | unavailable |
| 2x xbow_full.Lava Hound (per_minute) | bot only | 0.980 [0.463, 1.498]; n=9, C=9; total=8, den=8.161 | unavailable |
| 3x xbow_full.Lava Hound (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Mega Knight (per_minute) | bot only | 0.457 [0.308, 0.607]; n=7, C=7; total=6, den=13.123 | unavailable |
| 2x xbow_full.Mega Knight (per_minute) | bot only | 1.071 [0.753, 1.389]; n=7, C=7; total=11, den=10.275 | unavailable |
| 3x xbow_full.Mega Knight (per_minute) | bot only | 1.000 [95% CI not estimable]; n=1, C=1; total=1, den=1.000 | unavailable |
| 1x xbow_full.Miner (per_minute) | bot only | 0.556 [0.088, 1.025]; n=6, C=6; total=6, den=10.787 | unavailable |
| 2x xbow_full.Miner (per_minute) | bot only | 1.109 [0.844, 1.375]; n=5, C=5; total=9, den=8.113 | unavailable |
| 3x xbow_full.Miner (per_minute) | bot only | 0.561 [0.000, 1.526]; n=2, C=2; total=1, den=1.783 | unavailable |
| 1x xbow_full.Mortar (per_minute) | bot only | 0.533 [0.374, 0.693]; n=19, C=19; total=19, den=35.618 | unavailable |
| 2x xbow_full.Mortar (per_minute) | bot only | 0.661 [0.393, 0.929]; n=19, C=19; total=15, den=22.686 | unavailable |
| 3x xbow_full.Mortar (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.388 | unavailable |
| 1x xbow_full.Other (per_minute) | bot only | 0.441 [0.224, 0.659]; n=20, C=20; total=16, den=36.245 | unavailable |
| 2x xbow_full.Other (per_minute) | bot only | 1.060 [0.715, 1.405]; n=17, C=17; total=24, den=22.648 | unavailable |
| 3x xbow_full.Other (per_minute) | bot only | 1.314 [0.473, 2.155]; n=6, C=6; total=6, den=4.567 | unavailable |
| 1x xbow_full.P.E.K.K.A (per_minute) | bot only | 0.414 [0.000, 0.945]; n=4, C=4; total=3, den=7.254 | unavailable |
| 2x xbow_full.P.E.K.K.A (per_minute) | bot only | 0.904 [0.701, 1.107]; n=2, C=2; total=1, den=1.106 | unavailable |
| 3x xbow_full.P.E.K.K.A (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Ram Rider (per_minute) | bot only | 0.388 [0.103, 0.673]; n=11, C=11; total=8, den=20.618 | unavailable |
| 2x xbow_full.Ram Rider (per_minute) | bot only | 0.367 [0.059, 0.675]; n=11, C=11; total=6, den=16.354 | unavailable |
| 3x xbow_full.Ram Rider (per_minute) | bot only | 0.000 [0.000, 2.995]; n=3, C=3; total=0, den=1.232 | unavailable |
| 1x xbow_full.Royal Giant (per_minute) | bot only | 0.474 [0.202, 0.747]; n=9, C=9; total=8, den=16.871 | unavailable |
| 2x xbow_full.Royal Giant (per_minute) | bot only | 0.892 [0.606, 1.178]; n=9, C=9; total=11, den=12.333 | unavailable |
| 3x xbow_full.Royal Giant (per_minute) | bot only | 1.430 [0.000, 3.255]; n=2, C=2; total=1, den=0.699 | unavailable |
| 1x xbow_full.Royal Hogs (per_minute) | bot only | 0.533 [0.338, 0.729]; n=19, C=19; total=19, den=35.618 | unavailable |
| 2x xbow_full.Royal Hogs (per_minute) | bot only | 1.044 [0.710, 1.379]; n=19, C=19; total=22, den=21.070 | unavailable |
| 3x xbow_full.Royal Hogs (per_minute) | bot only | 0.686 [0.000, 1.531]; n=2, C=2; total=1, den=1.458 | unavailable |
| 1x xbow_full.Rune Giant (per_minute) | bot only | 0.533 [0.533, 0.534]; n=2, C=2; total=2, den=3.749 | unavailable |
| 2x xbow_full.Rune Giant (per_minute) | bot only | 1.749 [0.890, 2.609]; n=2, C=2; total=4, den=2.287 | unavailable |
| 3x xbow_full.Rune Giant (per_minute) | bot only | 1.717 [95% CI not estimable]; n=1, C=1; total=1, den=0.583 | unavailable |
| 1x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.195 [0.000, 0.460]; n=9, C=9; total=3, den=15.400 | unavailable |
| 2x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.604 [0.264, 0.944]; n=7, C=7; total=5, den=8.276 | unavailable |
| 3x xbow_full.Skeleton Barrel (per_minute) | bot only | 1.000 [95% CI not estimable]; n=1, C=1; total=1, den=1.000 | unavailable |
| 1x xbow_full.Sparky (per_minute) | bot only | 0.546 [0.528, 0.564]; n=4, C=4; total=4, den=7.328 | unavailable |
| 2x xbow_full.Sparky (per_minute) | bot only | 1.245 [0.202, 2.288]; n=2, C=2; total=3, den=2.410 | unavailable |
| 3x xbow_full.Sparky (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Three Musketeers (per_minute) | bot only | 0.776 [0.569, 0.983]; n=7, C=7; total=10, den=12.887 | unavailable |
| 2x xbow_full.Three Musketeers (per_minute) | bot only | 1.486 [0.757, 2.215]; n=6, C=6; total=13, den=8.747 | unavailable |
| 3x xbow_full.Three Musketeers (per_minute) | bot only | 0.587 [0.000, 1.360]; n=3, C=3; total=1, den=1.703 | unavailable |
| 1x xbow_full.Wall Breakers (per_minute) | bot only | 0.359 [0.005, 0.712]; n=8, C=8; total=5, den=13.935 | unavailable |
| 2x xbow_full.Wall Breakers (per_minute) | bot only | 1.075 [0.575, 1.575]; n=7, C=7; total=10, den=9.306 | unavailable |
| 3x xbow_full.Wall Breakers (per_minute) | bot only | 0.851 [0.354, 1.348]; n=2, C=2; total=1, den=1.175 | unavailable |
| 1x xbow_full.X-Bow (per_minute) | bot only | 0.800 [0.277, 1.323]; n=2, C=2; total=3, den=3.750 | unavailable |
| 2x xbow_full.X-Bow (per_minute) | bot only | 1.412 [0.496, 2.328]; n=2, C=2; total=3, den=2.125 | unavailable |
| 3x xbow_full.X-Bow (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |

### Video outcomes: big_losses

Bot only unless the comparison column says bot vs icebow-like humans. Per-minute values use phase minutes except state/archetype rows, which use their own exposure. Means/fractions show event n and cluster C. Human column = icebow-like humans.

| Phase / metric (unit) | Comparison | Bot [95% CI] | Human [95% CI] |
|---|---|---|
| 1x clump_bodies (per_minute) | bot only | 0.114 [0.006, 0.221]; n=114, C=114; total=23, den=202.351 | unavailable |
| 2x clump_bodies (per_minute) | bot only | 0.236 [0.026, 0.445]; n=86, C=86; total=14, den=59.432 | unavailable |
| 3x clump_bodies (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x clump_contacts (per_minute) | bot only | 0.301 [0.181, 0.422]; n=114, C=114; total=61, den=202.351 | unavailable |
| 2x clump_contacts (per_minute) | bot only | 0.538 [0.283, 0.793]; n=86, C=86; total=32, den=59.432 | unavailable |
| 3x clump_contacts (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x clump_elixir (per_minute) | bot only | 0.069 [0.000, 0.146]; n=114, C=114; total=14, den=202.351 | unavailable |
| 2x clump_elixir (per_minute) | bot only | 0.168 [0.000, 0.389]; n=86, C=86; total=10, den=59.432 | unavailable |
| 3x clump_elixir (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x clump_episodes (per_minute) | bot only | 0.044 [0.003, 0.086]; n=114, C=114; total=9, den=202.351 | unavailable |
| 2x clump_episodes (per_minute) | bot only | 0.118 [0.013, 0.222]; n=86, C=86; total=7, den=59.432 | unavailable |
| 3x clump_episodes (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.018]; n=114, C=114; total=0, den=202.351 | unavailable |
| 2x clump_unknown_values (per_minute) | bot only | 0.000 [0.000, 0.062]; n=86, C=86; total=0, den=59.432 | unavailable |
| 3x clump_unknown_values (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x commit.ahead (per_minute) | bot only | 1.311 [1.013, 1.608]; n=78, C=78; total=52, den=39.669 | unavailable |
| 2x commit.ahead (per_minute) | bot only | 1.651 [1.001, 2.301]; n=15, C=15; total=11, den=6.662 | unavailable |
| 3x commit.ahead (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x commit.behind (per_minute) | bot only | 1.208 [1.034, 1.381]; n=97, C=97; total=100, den=82.810 | unavailable |
| 2x commit.behind (per_minute) | bot only | 1.798 [1.440, 2.157]; n=86, C=86; total=75, den=41.702 | unavailable |
| 3x commit.behind (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.049 | unavailable |
| 1x commit.level (per_minute) | bot only | 1.500 [1.275, 1.725]; n=107, C=107; total=111, den=73.997 | unavailable |
| 2x commit.level (per_minute) | bot only | 2.781 [1.803, 3.758]; n=24, C=24; total=19, den=6.832 | unavailable |
| 3x commit.level (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x commit_damage.ahead (mean) | bot only | 405.600 [145.377, 665.823]; n=35, C=23; total=14196, den=35.000 | unavailable |
| 2x commit_damage.ahead (mean) | bot only | 1563.000 [283.464, 2842.536]; n=4, C=4; total=6252, den=4.000 | unavailable |
| 3x commit_damage.ahead (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x commit_damage.behind (mean) | bot only | 1014.954 [739.932, 1289.976]; n=87, C=53; total=88301, den=87.000 | unavailable |
| 2x commit_damage.behind (mean) | bot only | 1332.364 [827.245, 1837.483]; n=44, C=23; total=58624, den=44.000 | unavailable |
| 3x commit_damage.behind (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x commit_damage.level (mean) | bot only | 731.253 [396.687, 1065.819]; n=79, C=58; total=57769, den=79.000 | unavailable |
| 2x commit_damage.level (mean) | bot only | 148.889 [0.000, 317.614]; n=9, C=6; total=1340, den=9.000 | unavailable |
| 3x commit_damage.level (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x commit_full.ahead (per_minute) | bot only | 0.882 [0.597, 1.168]; n=78, C=78; total=35, den=39.669 | unavailable |
| 2x commit_full.ahead (per_minute) | bot only | 0.600 [0.137, 1.063]; n=15, C=15; total=4, den=6.662 | unavailable |
| 3x commit_full.ahead (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x commit_full.behind (per_minute) | bot only | 1.051 [0.870, 1.232]; n=97, C=97; total=87, den=82.810 | unavailable |
| 2x commit_full.behind (per_minute) | bot only | 1.055 [0.721, 1.389]; n=86, C=86; total=44, den=41.702 | unavailable |
| 3x commit_full.behind (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.049 | unavailable |
| 1x commit_full.level (per_minute) | bot only | 1.068 [0.856, 1.279]; n=107, C=107; total=79, den=73.997 | unavailable |
| 2x commit_full.level (per_minute) | bot only | 1.317 [0.803, 1.832]; n=24, C=24; total=9, den=6.832 | unavailable |
| 3x commit_full.level (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x cycle_assessed (per_minute) | bot only | 1.255 [1.114, 1.396]; n=114, C=114; total=254, den=202.351 | unavailable |
| 2x cycle_assessed (per_minute) | bot only | 2.053 [1.716, 2.390]; n=86, C=86; total=122, den=59.432 | unavailable |
| 3x cycle_assessed (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x cycle_candidates (per_minute) | bot only | 1.542 [1.396, 1.688]; n=114, C=114; total=312, den=202.351 | unavailable |
| 2x cycle_candidates (per_minute) | bot only | 2.911 [2.528, 3.294]; n=86, C=86; total=173, den=59.432 | unavailable |
| 3x cycle_candidates (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x cycle_elixir_at_play (mean) | bot only | 6.144 [4.607, 7.681]; n=18, C=17; total=110.593, den=18.000 | unavailable |
| 2x cycle_elixir_at_play (mean) | bot only | 4.666 [2.969, 6.363]; n=8, C=8; total=37.3308, den=8.000 | unavailable |
| 3x cycle_elixir_at_play (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x cycle_empty (per_minute) | bot only | 0.089 [0.049, 0.129]; n=114, C=114; total=18, den=202.351 | unavailable |
| 2x cycle_empty (per_minute) | bot only | 0.135 [0.046, 0.224]; n=86, C=86; total=8, den=59.432 | unavailable |
| 3x cycle_empty (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x cycle_empty_elixir (per_minute) | bot only | 0.089 [0.049, 0.129]; n=114, C=114; total=18, den=202.351 | unavailable |
| 2x cycle_empty_elixir (per_minute) | bot only | 0.135 [0.046, 0.224]; n=86, C=86; total=8, den=59.432 | unavailable |
| 3x cycle_empty_elixir (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x kill_assessed (per_minute) | bot only | 0.128 [0.079, 0.178]; n=114, C=114; total=26, den=202.351 | unavailable |
| 2x kill_assessed (per_minute) | bot only | 0.168 [0.063, 0.273]; n=86, C=86; total=10, den=59.432 | unavailable |
| 3x kill_assessed (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x kill_pushes (per_minute) | bot only | 0.282 [0.202, 0.361]; n=114, C=114; total=57, den=202.351 | unavailable |
| 2x kill_pushes (per_minute) | bot only | 0.320 [0.179, 0.460]; n=86, C=86; total=19, den=59.432 | unavailable |
| 3x kill_pushes (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x kill_supports_first (per_minute) | bot only | 0.054 [0.021, 0.088]; n=114, C=114; total=11, den=202.351 | unavailable |
| 2x kill_supports_first (per_minute) | bot only | 0.084 [0.014, 0.154]; n=86, C=86; total=5, den=59.432 | unavailable |
| 3x kill_supports_first (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x kill_supports_first_fraction (fraction) | bot only | 0.423 [0.221, 0.629]; n=26, C=23; total=11, den=26.000 | unavailable |
| 2x kill_supports_first_fraction (fraction) | bot only | 0.500 [0.140, 0.860]; n=10, C=9; total=5, den=10.000 | unavailable |
| 3x kill_supports_first_fraction (fraction) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x pressure_complete (per_minute) | bot vs icebow-like humans | 1.819 [1.608, 2.030]; n=114, C=114; total=368, den=202.351 | 1.563 [0.879, 2.247]; n=6, C=6; total=18, den=11.518 |
| 2x pressure_complete (per_minute) | bot vs icebow-like humans | 1.195 [0.753, 1.637]; n=86, C=86; total=71, den=59.432 | 2.540 [1.587, 3.493]; n=5, C=5; total=10, den=3.938 |
| 3x pressure_complete (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable; n=0; 95% CI not estimable |
| 1x pressure_elixir (mean) | bot only | 6.916 [6.588, 7.245]; n=368, C=112; total=2545.24, den=368.000 | unavailable |
| 2x pressure_elixir (mean) | bot only | 5.477 [4.549, 6.405]; n=71, C=34; total=388.838, den=71.000 | unavailable |
| 3x pressure_elixir (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x pressure_response_elixir (mean) | bot only | 8.139 [7.742, 8.537]; n=82, C=67; total=667.421, den=82.000 | unavailable |
| 2x pressure_response_elixir (mean) | bot only | 7.094 [6.050, 8.137]; n=20, C=12; total=141.875, den=20.000 | unavailable |
| 3x pressure_response_elixir (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.223 [0.145, 0.326]; n=368, C=112; total=82, den=368.000 | 0.056 [0.000, 0.511]; n=18, C=6; total=1, den=18.000 |
| 2x pressure_response_fraction (fraction) | bot vs icebow-like humans | 0.282 [0.127, 0.515]; n=71, C=34; total=20, den=71.000 | 0.000 [0.000, 0.500]; n=10, C=4; total=0, den=10.000 |
| 3x pressure_response_fraction (fraction) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x pressure_responses (per_minute) | bot vs icebow-like humans | 0.405 [0.334, 0.476]; n=114, C=114; total=82, den=202.351 | 0.087 [0.000, 0.256]; n=6, C=6; total=1, den=11.518 |
| 2x pressure_responses (per_minute) | bot vs icebow-like humans | 0.337 [0.088, 0.585]; n=86, C=86; total=20, den=59.432 | 0.000 [0.000, 0.937]; n=5, C=5; total=0, den=3.938 |
| 3x pressure_responses (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable; n=0; 95% CI not estimable |
| 1x pressure_windows (per_minute) | bot vs icebow-like humans | 1.838 [1.625, 2.051]; n=114, C=114; total=372, den=202.351 | 1.563 [0.879, 2.247]; n=6, C=6; total=18, den=11.518 |
| 2x pressure_windows (per_minute) | bot vs icebow-like humans | 1.296 [0.837, 1.754]; n=86, C=86; total=77, den=59.432 | 2.540 [1.587, 3.493]; n=5, C=5; total=10, den=3.938 |
| 3x pressure_windows (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable; n=0; 95% CI not estimable |
| 1x pull_centre (per_minute) | bot only | 1.013 [0.872, 1.154]; n=114, C=114; total=205, den=202.351 | unavailable |
| 2x pull_centre (per_minute) | bot only | 3.029 [2.542, 3.516]; n=86, C=86; total=180, den=59.432 | unavailable |
| 3x pull_centre (per_minute) | bot only | 9.756 [95% CI not estimable]; n=1, C=1; total=1, den=0.103 | unavailable |
| 1x pull_inward_offset (mean) | bot only | 1.866 [1.574, 2.159]; n=430, C=112; total=802.538, den=430.000 | unavailable |
| 2x pull_inward_offset (mean) | bot only | 1.968 [1.617, 2.320]; n=334, C=65; total=657.451, den=334.000 | unavailable |
| 3x pull_inward_offset (mean) | bot only | 5.000 [95% CI not estimable]; n=1, C=1; total=5, den=1.000 | unavailable |
| 1x pull_offset (mean) | bot only | 2.498 [2.288, 2.707]; n=430, C=112; total=1073.95, den=430.000 | unavailable |
| 2x pull_offset (mean) | bot only | 2.607 [2.338, 2.875]; n=334, C=65; total=870.723, den=334.000 | unavailable |
| 3x pull_offset (mean) | bot only | 5.000 [95% CI not estimable]; n=1, C=1; total=5, den=1.000 | unavailable |
| 1x pull_placements (per_minute) | bot only | 2.125 [1.951, 2.300]; n=114, C=114; total=430, den=202.351 | unavailable |
| 2x pull_placements (per_minute) | bot only | 5.620 [5.074, 6.166]; n=86, C=86; total=334, den=59.432 | unavailable |
| 3x pull_placements (per_minute) | bot only | 9.756 [95% CI not estimable]; n=1, C=1; total=1, den=0.103 | unavailable |
| 1x pull_side (per_minute) | bot only | 1.112 [0.965, 1.259]; n=114, C=114; total=225, den=202.351 | unavailable |
| 2x pull_side (per_minute) | bot only | 2.591 [2.116, 3.066]; n=86, C=86; total=154, den=59.432 | unavailable |
| 3x pull_side (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x tank_complete (per_minute) | bot only | 0.400 [0.297, 0.504]; n=114, C=114; total=81, den=202.351 | unavailable |
| 2x tank_complete (per_minute) | bot only | 0.252 [0.077, 0.428]; n=86, C=86; total=15, den=59.432 | unavailable |
| 3x tank_complete (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x tank_crossings (per_minute) | bot only | 0.712 [0.562, 0.861]; n=114, C=114; total=144, den=202.351 | unavailable |
| 2x tank_crossings (per_minute) | bot only | 0.791 [0.394, 1.188]; n=86, C=86; total=47, den=59.432 | unavailable |
| 3x tank_crossings (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x tank_preexisting_tesla (fraction) | bot only | 0.389 [0.266, 0.527]; n=144, C=71; total=56, den=144.000 | unavailable |
| 2x tank_preexisting_tesla (fraction) | bot only | 0.255 [0.092, 0.538]; n=47, C=22; total=12, den=47.000 | unavailable |
| 3x tank_preexisting_tesla (fraction) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x tank_tesla_delay (mean) | bot only | 6.826 [3.458, 10.195]; n=17, C=15; total=116.05, den=17.000 | unavailable |
| 2x tank_tesla_delay (mean) | bot only | 4.075 [0.252, 7.898]; n=8, C=7; total=32.6, den=8.000 | unavailable |
| 3x tank_tesla_delay (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x tank_tesla_response (per_minute) | bot only | 0.084 [0.040, 0.128]; n=114, C=114; total=17, den=202.351 | unavailable |
| 2x tank_tesla_response (per_minute) | bot only | 0.135 [0.035, 0.234]; n=86, C=86; total=8, den=59.432 | unavailable |
| 3x tank_tesla_response (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x tank_tesla_survival (fraction) | bot only | 0.308 [0.067, 0.594]; n=13, C=12; total=4, den=13.000 | unavailable |
| 2x tank_tesla_survival (fraction) | bot only | 0.250 [0.000, 0.811]; n=4, C=3; total=1, den=4.000 | unavailable |
| 3x tank_tesla_survival (fraction) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Balloon (per_minute) | bot vs icebow-like humans | 0.960 [0.751, 1.169]; n=5, C=5; total=9, den=9.373 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Balloon (per_minute) | bot vs icebow-like humans | 0.689 [0.000, 1.646]; n=5, C=5; total=2, den=2.903 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Balloon (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 0.954 [0.752, 1.155]; n=6, C=6; total=9, den=9.438 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | 0.746 [0.128, 1.364]; n=4, C=4; total=2, den=2.682 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Battle Ram (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 1.174 [0.964, 1.383]; n=5, C=5; total=11, den=9.373 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | 0.406 [0.000, 0.926]; n=5, C=5; total=2, den=4.922 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Electro Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 0.928 [0.721, 1.136]; n=17, C=17; total=29, den=31.233 | unavailable |
| 2x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 0.753 [0.373, 1.134]; n=14, C=14; total=7, den=9.292 | unavailable |
| 3x xbow.Elixir Golem (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x xbow.Giant (per_minute) | bot vs icebow-like humans | 0.607 [0.206, 1.008]; n=5, C=5; total=5, den=8.242 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=2.000 |
| 2x xbow.Giant (per_minute) | bot vs icebow-like humans | 1.533 [1.019, 2.047]; n=3, C=3; total=4, den=2.609 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.459 |
| 3x xbow.Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 0.878 [0.687, 1.070]; n=8, C=8; total=13, den=14.798 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | 1.325 [0.870, 1.779]; n=6, C=6; total=5, den=3.774 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Goblin Barrel (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Goblin Drill (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 0.680 [0.155, 1.206]; n=4, C=4; total=5, den=7.348 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | 1.708 [0.000, 3.849]; n=3, C=3; total=2, den=1.171 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Goblin Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow.Goblin Machine (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow.Goblinstein (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Golem (per_minute) | bot vs icebow-like humans | 0.796 [0.600, 0.993]; n=13, C=13; total=18, den=22.608 | unavailable |
| 2x xbow.Golem (per_minute) | bot vs icebow-like humans | 0.782 [0.257, 1.306]; n=10, C=10; total=6, den=7.678 | unavailable |
| 3x xbow.Golem (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Graveyard (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Graveyard (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Graveyard (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.593 [0.335, 0.851]; n=11, C=11; total=12, den=20.223 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | 0.669 [0.232, 1.106]; n=10, C=10; total=5, den=7.473 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Hog Rider (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 1.016 [0.806, 1.225]; n=6, C=6; total=11, den=10.831 | unavailable |
| 2x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | 0.389 [0.000, 1.092]; n=4, C=4; total=1, den=2.571 | unavailable |
| 3x xbow.Lava Hound (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow.Mega Knight (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Miner (per_minute) | bot vs icebow-like humans | 0.707 [95% CI not estimable]; n=1, C=1; total=1, den=1.414 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Miner (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Miner (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Mortar (per_minute) | bot vs icebow-like humans | 0.800 [0.498, 1.102]; n=4, C=4; total=6, den=7.498 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=2.000 |
| 2x xbow.Mortar (per_minute) | bot vs icebow-like humans | 0.950 [0.618, 1.281]; n=4, C=4; total=3, den=3.159 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.026 |
| 3x xbow.Mortar (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Other (per_minute) | bot vs icebow-like humans | 0.700 [0.352, 1.047]; n=6, C=6; total=7, den=10.002 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Other (per_minute) | bot vs icebow-like humans | 0.000 [0.000, 2.112]; n=3, C=3; total=0, den=1.747 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Other (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 1.115 [1.065, 1.166]; n=3, C=3; total=6, den=5.379 | unavailable |
| 2x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.063 | unavailable |
| 3x xbow.P.E.K.K.A (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 0.800 [0.277, 1.323]; n=2, C=2; total=3, den=3.750 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | 0.926 [0.814, 1.038]; n=2, C=2; total=2, den=2.160 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Ram Rider (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 1.067 [95% CI not estimable]; n=1, C=1; total=2, den=1.874 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | 1.009 [95% CI not estimable]; n=1, C=1; total=1, den=0.991 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Royal Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 0.838 [0.527, 1.149]; n=7, C=7; total=11, den=13.123 | 1.000 [1.000, 1.000]; n=3, C=3; total=6, den=6.000 |
| 2x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | 0.865 [0.000, 1.773]; n=7, C=7; total=4, den=4.623 | 0.408 [0.000, 1.196]; n=3, C=3; total=1, den=2.452 |
| 3x xbow.Royal Hogs (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | 1.067 [95% CI not estimable]; n=1, C=1; total=2, den=1.874 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.287 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Rune Giant (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 0.330 [0.000, 0.742]; n=4, C=4; total=2, den=6.064 | unavailable |
| 2x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | 1.969 [1.070, 2.868]; n=2, C=2; total=2, den=1.016 | unavailable |
| 3x xbow.Skeleton Barrel (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Sparky (per_minute) | bot vs icebow-like humans | 0.838 [0.334, 1.343]; n=2, C=2; total=3, den=3.579 | unavailable |
| 2x xbow.Sparky (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow.Sparky (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 0.854 [0.408, 1.300]; n=2, C=2; total=3, den=3.513 | unavailable; n=0; 95% CI not estimable |
| 2x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.313 | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Three Musketeers (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | 1.231 [95% CI not estimable]; n=1, C=1; total=1, den=0.812 | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.517 |
| 2x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 3x xbow.Wall Breakers (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable; n=0; 95% CI not estimable |
| 1x xbow.X-Bow (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow.X-Bow (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow.X-Bow (per_minute) | bot vs icebow-like humans | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Balloon (mean) | bot only | 732.667 [0.000, 1655.739]; n=6, C=4; total=4396, den=6.000 | unavailable |
| 2x xbow_damage.Balloon (mean) | bot only | 781.000 [95% CI not estimable]; n=1, C=1; total=781, den=1.000 | unavailable |
| 3x xbow_damage.Balloon (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Battle Ram (mean) | bot only | 876.333 [41.412, 1711.255]; n=6, C=5; total=5258, den=6.000 | unavailable |
| 2x xbow_damage.Battle Ram (mean) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 3x xbow_damage.Battle Ram (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Electro Giant (mean) | bot only | 1013.625 [188.897, 1838.353]; n=8, C=5; total=8109, den=8.000 | unavailable |
| 2x xbow_damage.Electro Giant (mean) | bot only | 51.000 [51.000, 51.000]; n=2, C=2; total=102, den=2.000 | unavailable |
| 3x xbow_damage.Electro Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Elixir Golem (mean) | bot only | 1881.000 [1329.829, 2432.171]; n=26, C=16; total=48906, den=26.000 | unavailable |
| 2x xbow_damage.Elixir Golem (mean) | bot only | 1016.400 [159.996, 1872.804]; n=5, C=5; total=5082, den=5.000 | unavailable |
| 3x xbow_damage.Elixir Golem (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Giant (mean) | bot only | 2436.667 [44.413, 4828.921]; n=3, C=3; total=7310, den=3.000 | unavailable |
| 2x xbow_damage.Giant (mean) | bot only | 3599.000 [95% CI not estimable]; n=1, C=1; total=3599, den=1.000 | unavailable |
| 3x xbow_damage.Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Barrel (mean) | bot only | 1704.400 [1023.985, 2384.815]; n=10, C=7; total=17044, den=10.000 | unavailable |
| 2x xbow_damage.Goblin Barrel (mean) | bot only | 1525.333 [211.801, 2838.866]; n=3, C=3; total=4576, den=3.000 | unavailable |
| 3x xbow_damage.Goblin Barrel (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Drill (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Goblin Drill (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Goblin Drill (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Giant (mean) | bot only | 2045.600 [714.800, 3376.400]; n=5, C=3; total=10228, den=5.000 | unavailable |
| 2x xbow_damage.Goblin Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Goblin Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblin Machine (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Goblin Machine (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Goblin Machine (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Goblinstein (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Golem (mean) | bot only | 2808.059 [2381.656, 3234.461]; n=17, C=12; total=47737, den=17.000 | unavailable |
| 2x xbow_damage.Golem (mean) | bot only | 10.000 [0.000, 29.600]; n=4, C=4; total=40, den=4.000 | unavailable |
| 3x xbow_damage.Golem (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Graveyard (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Graveyard (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Graveyard (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Hog Rider (mean) | bot only | 1312.667 [703.779, 1921.554]; n=9, C=6; total=11814, den=9.000 | unavailable |
| 2x xbow_damage.Hog Rider (mean) | bot only | 1221.750 [81.811, 2361.689]; n=4, C=3; total=4887, den=4.000 | unavailable |
| 3x xbow_damage.Hog Rider (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Lava Hound (mean) | bot only | 2151.300 [959.301, 3343.299]; n=10, C=6; total=21513, den=10.000 | unavailable |
| 2x xbow_damage.Lava Hound (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Lava Hound (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Mega Knight (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Mega Knight (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Mega Knight (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Miner (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Miner (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Miner (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Mortar (mean) | bot only | 3111.800 [2501.464, 3722.136]; n=5, C=4; total=15559, den=5.000 | unavailable |
| 2x xbow_damage.Mortar (mean) | bot only | 2718.500 [2554.840, 2882.160]; n=2, C=2; total=5437, den=2.000 | unavailable |
| 3x xbow_damage.Mortar (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Other (mean) | bot only | 1276.333 [0.000, 3493.803]; n=3, C=3; total=3829, den=3.000 | unavailable |
| 2x xbow_damage.Other (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Other (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.P.E.K.K.A (mean) | bot only | 936.333 [860.982, 1011.684]; n=3, C=2; total=2809, den=3.000 | unavailable |
| 2x xbow_damage.P.E.K.K.A (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.P.E.K.K.A (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Ram Rider (mean) | bot only | 2212.000 [95% CI not estimable]; n=2, C=1; total=4424, den=2.000 | unavailable |
| 2x xbow_damage.Ram Rider (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Ram Rider (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Royal Giant (mean) | bot only | 1260.500 [95% CI not estimable]; n=2, C=1; total=2521, den=2.000 | unavailable |
| 2x xbow_damage.Royal Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Royal Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Royal Hogs (mean) | bot only | 715.800 [0.000, 1838.174]; n=5, C=4; total=3579, den=5.000 | unavailable |
| 2x xbow_damage.Royal Hogs (mean) | bot only | 670.333 [0.000, 1479.596]; n=3, C=2; total=2011, den=3.000 | unavailable |
| 3x xbow_damage.Royal Hogs (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Rune Giant (mean) | bot only | 3626.000 [95% CI not estimable]; n=1, C=1; total=3626, den=1.000 | unavailable |
| 2x xbow_damage.Rune Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Rune Giant (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Skeleton Barrel (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Skeleton Barrel (mean) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.000 | unavailable |
| 3x xbow_damage.Skeleton Barrel (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Sparky (mean) | bot only | 2652.500 [1203.080, 4101.920]; n=2, C=2; total=5305, den=2.000 | unavailable |
| 2x xbow_damage.Sparky (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Sparky (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Three Musketeers (mean) | bot only | 2442.667 [1095.929, 3789.404]; n=3, C=2; total=7328, den=3.000 | unavailable |
| 2x xbow_damage.Three Musketeers (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Three Musketeers (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.Wall Breakers (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.Wall Breakers (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.Wall Breakers (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_damage.X-Bow (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_damage.X-Bow (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_damage.X-Bow (mean) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Balloon (per_minute) | bot only | 0.640 [0.249, 1.031]; n=5, C=5; total=6, den=9.373 | unavailable |
| 2x xbow_full.Balloon (per_minute) | bot only | 0.345 [0.000, 1.041]; n=5, C=5; total=1, den=2.903 | unavailable |
| 3x xbow_full.Balloon (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Battle Ram (per_minute) | bot only | 0.636 [0.364, 0.907]; n=6, C=6; total=6, den=9.438 | unavailable |
| 2x xbow_full.Battle Ram (per_minute) | bot only | 0.373 [0.000, 1.013]; n=4, C=4; total=1, den=2.682 | unavailable |
| 3x xbow_full.Battle Ram (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Electro Giant (per_minute) | bot only | 0.854 [0.597, 1.110]; n=5, C=5; total=8, den=9.373 | unavailable |
| 2x xbow_full.Electro Giant (per_minute) | bot only | 0.406 [0.000, 0.926]; n=5, C=5; total=2, den=4.922 | unavailable |
| 3x xbow_full.Electro Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Elixir Golem (per_minute) | bot only | 0.832 [0.657, 1.008]; n=17, C=17; total=26, den=31.233 | unavailable |
| 2x xbow_full.Elixir Golem (per_minute) | bot only | 0.538 [0.248, 0.828]; n=14, C=14; total=5, den=9.292 | unavailable |
| 3x xbow_full.Elixir Golem (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.103 | unavailable |
| 1x xbow_full.Giant (per_minute) | bot only | 0.364 [0.035, 0.693]; n=5, C=5; total=3, den=8.242 | unavailable |
| 2x xbow_full.Giant (per_minute) | bot only | 0.383 [0.000, 1.304]; n=3, C=3; total=1, den=2.609 | unavailable |
| 3x xbow_full.Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblin Barrel (per_minute) | bot only | 0.676 [0.408, 0.943]; n=8, C=8; total=10, den=14.798 | unavailable |
| 2x xbow_full.Goblin Barrel (per_minute) | bot only | 0.795 [0.131, 1.459]; n=6, C=6; total=3, den=3.774 | unavailable |
| 3x xbow_full.Goblin Barrel (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblin Drill (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.Goblin Drill (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Goblin Drill (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblin Giant (per_minute) | bot only | 0.680 [0.155, 1.206]; n=4, C=4; total=5, den=7.348 | unavailable |
| 2x xbow_full.Goblin Giant (per_minute) | bot only | 0.000 [0.000, 3.151]; n=3, C=3; total=0, den=1.171 | unavailable |
| 3x xbow_full.Goblin Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblin Machine (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.Goblin Machine (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Goblin Machine (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Goblinstein (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.Goblinstein (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Goblinstein (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Golem (per_minute) | bot only | 0.752 [0.558, 0.946]; n=13, C=13; total=17, den=22.608 | unavailable |
| 2x xbow_full.Golem (per_minute) | bot only | 0.521 [0.223, 0.819]; n=10, C=10; total=4, den=7.678 | unavailable |
| 3x xbow_full.Golem (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Graveyard (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.Graveyard (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Graveyard (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Hog Rider (per_minute) | bot only | 0.445 [0.169, 0.721]; n=11, C=11; total=9, den=20.223 | unavailable |
| 2x xbow_full.Hog Rider (per_minute) | bot only | 0.535 [0.072, 0.999]; n=10, C=10; total=4, den=7.473 | unavailable |
| 3x xbow_full.Hog Rider (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Lava Hound (per_minute) | bot only | 0.923 [0.730, 1.117]; n=6, C=6; total=10, den=10.831 | unavailable |
| 2x xbow_full.Lava Hound (per_minute) | bot only | 0.000 [0.000, 1.435]; n=4, C=4; total=0, den=2.571 | unavailable |
| 3x xbow_full.Lava Hound (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Mega Knight (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.Mega Knight (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Mega Knight (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Miner (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=1.414 | unavailable |
| 2x xbow_full.Miner (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Miner (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Mortar (per_minute) | bot only | 0.667 [0.405, 0.928]; n=4, C=4; total=5, den=7.498 | unavailable |
| 2x xbow_full.Mortar (per_minute) | bot only | 0.633 [0.000, 1.319]; n=4, C=4; total=2, den=3.159 | unavailable |
| 3x xbow_full.Mortar (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Other (per_minute) | bot only | 0.300 [0.011, 0.589]; n=6, C=6; total=3, den=10.002 | unavailable |
| 2x xbow_full.Other (per_minute) | bot only | 0.000 [0.000, 2.112]; n=3, C=3; total=0, den=1.747 | unavailable |
| 3x xbow_full.Other (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.P.E.K.K.A (per_minute) | bot only | 0.558 [0.000, 1.209]; n=3, C=3; total=3, den=5.379 | unavailable |
| 2x xbow_full.P.E.K.K.A (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.063 | unavailable |
| 3x xbow_full.P.E.K.K.A (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Ram Rider (per_minute) | bot only | 0.533 [0.000, 1.579]; n=2, C=2; total=2, den=3.750 | unavailable |
| 2x xbow_full.Ram Rider (per_minute) | bot only | 0.000 [0.000, 1.708]; n=2, C=2; total=0, den=2.160 | unavailable |
| 3x xbow_full.Ram Rider (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Royal Giant (per_minute) | bot only | 1.067 [95% CI not estimable]; n=1, C=1; total=2, den=1.874 | unavailable |
| 2x xbow_full.Royal Giant (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.991 | unavailable |
| 3x xbow_full.Royal Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Royal Hogs (per_minute) | bot only | 0.381 [0.082, 0.680]; n=7, C=7; total=5, den=13.123 | unavailable |
| 2x xbow_full.Royal Hogs (per_minute) | bot only | 0.649 [0.000, 1.403]; n=7, C=7; total=3, den=4.623 | unavailable |
| 3x xbow_full.Royal Hogs (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Rune Giant (per_minute) | bot only | 0.534 [95% CI not estimable]; n=1, C=1; total=1, den=1.874 | unavailable |
| 2x xbow_full.Rune Giant (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.287 | unavailable |
| 3x xbow_full.Rune Giant (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.000 [0.000, 0.608]; n=4, C=4; total=0, den=6.064 | unavailable |
| 2x xbow_full.Skeleton Barrel (per_minute) | bot only | 0.984 [0.535, 1.434]; n=2, C=2; total=1, den=1.016 | unavailable |
| 3x xbow_full.Skeleton Barrel (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Sparky (per_minute) | bot only | 0.559 [0.530, 0.588]; n=2, C=2; total=2, den=3.579 | unavailable |
| 2x xbow_full.Sparky (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Sparky (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Three Musketeers (per_minute) | bot only | 0.854 [0.408, 1.300]; n=2, C=2; total=3, den=3.513 | unavailable |
| 2x xbow_full.Three Musketeers (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.313 | unavailable |
| 3x xbow_full.Three Musketeers (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.Wall Breakers (per_minute) | bot only | 0.000 [95% CI not estimable]; n=1, C=1; total=0, den=0.812 | unavailable |
| 2x xbow_full.Wall Breakers (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.Wall Breakers (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 1x xbow_full.X-Bow (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 2x xbow_full.X-Bow (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |
| 3x xbow_full.X-Bow (per_minute) | bot only | unavailable; n=0; 95% CI not estimable | unavailable |

### Video definitions, exclusions and censoring

- Each table labels bot only or bot vs icebow-like humans. If the overlap cohort is smaller than 15 sides, comparison columns explicitly use X-Bow + Tesla fallback; the exact overlap cohort is also retained. Sides qualify from all observed cards, not a reconstructed hidden deck. Big losses overlap losses. Draws remain in all.
- All brackets are approximate 95% CIs. Rates use match/replay-cluster ratio-of-sums intervals; means use the same cluster ratio with event counts as denominator. Fractions use a cluster-effective-size Wilson envelope around the sandwich interval, keeping nonzero uncertainty at 0/100%. n is independent clusters for rates, event observations for means/fractions; C states cluster count. No-data and one-cluster continuous/rate intervals are explicitly not estimable. Rates always retain numerator and exposure. Human sides share replay clusters.
- Human orientation evidence: data-i is constant across both teams in each HTML replay. Index 1 puts team at raw y<16, index 0 puts team at raw y>16; opponent is opposite. Rotate x and y only when that side is at the top. Raw coordinates, side and orientation are saved in pro_plays.jsonl. Missing/unknown orientation is unavailable, never silently guessed. X-Bow classes bridge (16<=y<=21), defensive (>21), enemy_side (<16), unavailable partition every X-Bow.
- Bot enemy placements are first-seen public nonspell bodies, excluding bodies present at the first decision and after >2s gaps; same-card bodies within 1s and 5 tiles are grouped. Spawned tokens, evolution changes, duplicate identities and transforms can still masquerade as placements; spells without a persistent body are absent. This is a lower-coverage placement proxy, not a confirmed enemy card-play feed. Observation intervals and source keys are saved. Human placements are exact HTML markers. No enemy elixir or hand is used.
- (a) Cheap play strictly after a first-seen enemy placement by <=4s. Assess only a complete 6s decision window, no gap >2s, fresh board, and an observed spawned troop matched by card, <=3 tiles, <=3s; unmatched troops are unknown. Engagement proxy: matched troop within 2.5 tiles of enemy body/tower; Log swept footprint intersects enemy body/tower. This cannot certify targeting or actual hits. Empty-proxy count and nominal own card elixir use total phase minutes; candidates/assessed counts disclose missing coverage.
- (b) Enemy raw placement transformed into our frame must have y<9. First own X-Bow/Knight/Rocket strictly later by <=6s in the other x<9/x>=9 lane is a response. Each enemy placement is an opportunity; overlapping windows may share a response. Fraction excludes incomplete windows; opportunity/rate counts and exclusions are retained. Bot own elixir at first public enemy sighting and last public decision before response are separate. Human elixir is unavailable.
- (c) Tank names (catalog IDs resolve to names) include Giant, Golem, Royal/Electro/Goblin Giant, PEKKA, Lava Hound, Hog Rider, Ram Rider/Battle Ram, Balloon, Mega Knight. Same tracked body must cross y<16 to y>=16 within 3s. First-seen intrusions are excluded. Push ends after 3s with no nonbuilding enemy on our side in the crossing lane; gaps >2s/end censor it. First Tesla after crossing, on our side and same lane or within 2 tiles of centre, supplies delay; existing Teslas are flagged separately. Response delays are conditional on observed responses, not zero for missing responses. Newly placed Tesla is matched to a body within 1.5 tiles/3s. Survival requires closed push and matched identity alive at end, or confirmed disappearance before end; unmatched/censored is null.
- (d) Own Knight/Ice Wizard/Skeletons at y>=16 with a known enemy ground troop at y>=16. Lateral offset is absolute x minus lane centre 3.5/14.5; signed inward offset is also exported. Centre pull means >=1.5 tiles inward; all other placements are side. Flying catalog aliases are excluded, unknown bodies are excluded, ambiguous transformation forms remain a limitation. Position does not prove a successful pull.
- (e) Support set is non-tank enemy troops within 6 tiles of tank at crossing. Public disappearance requires last observed body then two missing decisions within 3s, before tiebreak. Lifespans split after >3s gaps to reduce address reuse. Supports-first requires every support disappearance upper bound <= tank last-visible tick; tank-first requires tank disappearance upper bound <= every support last-visible tick. Overlapping intervals or mixed support order are separate; censored observations are excluded from assessed fraction. Death transforms/visibility gaps are not certified kills.
- (f) Existing enemy_spells episodes are tower contacts, not all enemy casts. At each observed matching spell footprint, retain own bodies having another own body within 2.5 tiles inside the footprint. Report maximum simultaneous count and corresponding nominal catalog elixir per episode, excluding towers. Separate clusters may be included; unknown costs are counted, not imputed. A spell touching two towers may appear twice, as in the original episode definition; summons/copy spells remain contact proxies. Counts do not prove damage or deaths.
- (g) Read the literal ARCH precedence list from crapi/census.py without executing it; normalize catalog/HTML names. First matching observed card wins, else Other. Bot uses only visible bodies/projectiles; human uses observed cards. Spawned cards can bias bot archetype. Placement rate denominator is phase exposure of matches in that archetype. Damage averages include only full, gap-free next 20s and are all sources, never X-Bow-attributable.
- (h) State is sum of public remaining own tower HP minus enemy tower HP, >+1000 ahead, <-1000 behind, otherwise level. Missing towers count zero (public disappearance may flicker); all known king/princess HP is included. State exposure uses only decision intervals <=2s, split at phase boundaries. Commits: bridge X-Bow or Knight (16<=y<=21), Rocket whose geometry touches an enemy tower. Count only commits within a valid observed state interval. Per-state rates divide by time in that state, not all match time. HP taken means own tower HP lost over the next 20s, all sources, only complete windows; overlapping windows can count the same damage.
- Video receipts: video_events.jsonl contains event kinds, matches, phases, eligibility, body identities, timing and disappearance intervals. report.json retains all outcome splits and denominators, cohort IDs, observed opponent cards/archetype and per-match state exposure. Older measurements below preserve their original definitions; their broad human cohorts are historical comparison context, not the new icebow comparison.

## Previous-ticket measurements (regenerated)


## Ten findings

1. Selected 775 completed main-account X-Bow matches: 399 wins, 373 losses, 3 tower-state draws; 114 big losses (a subset of losses). This includes 28 clear terminal defeats before 2:00 that the original scorecard's duration cutoff would discard.
2. Net tower HP per minute (dealt minus taken): 1x -484.54 [-627.68, -341.40]; total=-698390, n=775m; 2x -36.36 [-237.86, 165.14]; total=-35566, n=747m; 3x 1055.58 [654.14, 1457.03]; total=118616, n=167m.
3. In eventual losses, net tower HP/minute: 1x -1587.82 [-1809.71, -1365.93]; total=-1.09213e+06, n=373m; 2x -1984.85 [-2310.19, -1659.52]; total=-855497, n=345m; 3x -325.73 [-746.57, 95.12]; total=-16381, n=74m.
4. In big losses, tower HP taken/minute: 1x 5176.42 [4647.39, 5705.45]; total=1.04745e+06, n=114m; 2x 9292.64 [8171.84, 10413.44]; total=552277, n=86m; 3x 5385.37 [CI unavailable]; total=552, n=1m.
5. Among 108 matches with at least 30 seconds in each phase, 3x minus 1x net HP/min averages 1205.1 (95% CI 754.3 to 1655.8). Later-phase comparisons remain conditional on survival.
6. Own elixir at confirmed plays: 1x 6.06 (n=11155); 2x 5.18 (n=13100); 3x 4.78 (n=2198).
7. Own elixir at observed push crossings: 1x 4.22 (n=3868); 2x 4.07 (n=2915); 3x 4.17 (n=368).
8. Confirmed bot plays/minute: 1x 7.74 [7.68, 7.80]; total=11155, n=775m; 2x 13.39 [13.27, 13.52]; total=13100, n=747m; 3x 19.56 [19.07, 20.05]; total=2198, n=167m. Human X-Bow sides: 1x 8.17 [7.78, 8.55]; total=751, n=46m; 2x 14.39 [13.49, 15.28]; total=1134, n=45m; 3x 18.97 [17.33, 20.62]; total=454, n=33m.
9. Quiet defensive-spend proxy, elixir/minute: 1x 2.52 [2.37, 2.67]; total=3635, n=775m; 2x 2.11 [1.92, 2.30]; total=2066, n=747m; 3x 1.61 [1.09, 2.13]; total=181, n=167m. This measures the stated heuristic, not proven waste.
10. Rocket-on-tower geometry counts/rates per minute: 1x 0.10 [0.09, 0.12]; total=147, n=775m; 2x 0.32 [0.28, 0.36]; total=314, n=747m; 3x 1.39 [1.19, 1.59]; total=156, n=167m. Actual spell chip and enemy elixir killed are not identifiable from these snapshots.

## Selection and coverage

Selection: {"candidate_files": 1250, "excluded": {"no_end_event": 3, "no_public_decisions": 34, "no_xbow_in_own_hand": 2, "other_account_tower_signature": 436}, "included": 775}.
Human corpus: 848 files, 848 usable unique replays, 1696 player-sides, 46 sides observed playing X-Bow. Rank/top-100 provenance is owner-supplied, not independently certified by these replay pages.
Main-account proxy: initial own princess maximum HP 4424 and king 7032. Smaller tower signatures are excluded. Nearby ladder trophy reads are attached per match when available; tower signatures do not uniquely prove account identity.
Selection requires an end event, Xbow in the observed OWN hand, and at least two final tower bodies. The scorecard duration rule (last tick >=2400) is retained except for clear early terminal records: battle_over_hands_visible stop, zero surviving towers on one side and at least two on the other. These earlier defeats must not disappear from a study of 1x collapses. Their IDs and a strict scorecard-only sensitivity summary are in report.json. Last-observed tower outcomes can miss a final hit and label a tiebreak loss as a draw. Final crowns in bot metadata are scorecard proxies, not result-screen crowns.
Each selected file has checkpoint path/hash, fast-plays flag, SHA256, observed ticks and account evidence in report.json. Active/changing files are excluded. Metrics use confirmed card plays; unmatched tap attempts and hero abilities are counted separately. Observed exposure starts at the first decision; no unlogged opening is invented. Missing/gapped elixir time is excluded from cap occupancy.

## Clock verification

| Phase | Tick interval | Own regen elixir/s, mean [95% CI across match means] | Intervals / matches |
|---|---|---|---|
| 1x | [0, 2400) | 0.356000 [0.356000, 0.356000] | 231862 / 775 |
| 2x | [2400, 4800) | 0.714000 [0.714000, 0.714000] | 158624 / 742 |
| 3x | [4800, 6000) | 1.074000 [1.074000, 1.074000] | 19398 / 163 |

Ticks run at 20/s (device-clock interval measurements are retained per match). Positive uncapped own-elixir changes over <=1s verify regeneration; spend/cap intervals are excluded. Baseline-rate estimates retain intervals within 0.02 elixir/s of each phase’s empirical median, removing elixir awards/corrections; rejected counts are retained. Boundary bins around 119/120 and 239/240 seconds retain unfiltered positive rates in report.json. Regulation 2:00 through overtime 4:00 is 2x. The 5:00+ tiebreak drain is excluded from all combat metrics, but the final decision still supplies the scorecard label.

## Bot versus human plays

| Phase | Bot confirmed plays/min | Human all decks plays/min | Human X-Bow plays/min |
|---|---|---|---|
| 1x | 7.74 [7.68, 7.80]; total=11155, n=775m | 6.82 [6.62, 7.01]; total=22875, n=848m | 8.17 [7.78, 8.55]; total=751, n=46m |
| 2x | 13.39 [13.27, 13.52]; total=13100, n=747m | 12.72 [12.55, 12.89]; total=32411, n=815m | 14.39 [13.49, 15.28]; total=1134, n=45m |
| 3x | 19.56 [19.07, 20.05]; total=2198, n=167m | 18.54 [18.14, 18.95]; total=10392, n=364m | 18.97 [17.33, 20.62]; total=454, n=33m |

### 1x: card rates, bot versus humans

| Card, per minute | Bot | Human all decks | Human X-Bow sides |
|---|---|---|---|
| Skeletons | 1.41 [1.39, 1.44]; total=2035, n=775m | 0.48 [0.44, 0.51]; total=1597, n=848m | 1.45 [1.34, 1.55]; total=133, n=46m |
| Log | 1.26 [1.23, 1.29]; total=1819, n=775m | 0.21 [0.18, 0.23]; total=688, n=848m | 1.11 [1.00, 1.22]; total=102, n=46m |
| Knight | 1.30 [1.27, 1.32]; total=1868, n=775m | 0.18 [0.16, 0.20]; total=603, n=848m | 1.12 [1.01, 1.23]; total=103, n=46m |
| Ice Wizard | 1.34 [1.32, 1.36]; total=1929, n=775m | 0.08 [0.06, 0.09]; total=256, n=848m | 0.35 [0.19, 0.51]; total=32, n=46m |
| Tornado | 0.48 [0.45, 0.51]; total=692, n=775m | 0.07 [0.06, 0.08]; total=228, n=848m | 0.15 [0.06, 0.24]; total=14, n=46m |
| Tesla | 1.04 [1.02, 1.07]; total=1506, n=775m | 0.07 [0.06, 0.09]; total=249, n=848m | 0.63 [0.49, 0.78]; total=58, n=46m |
| X-Bow | 0.76 [0.73, 0.79]; total=1097, n=775m | 0.02 [0.01, 0.03]; total=73, n=848m | 0.79 [0.67, 0.92]; total=73, n=46m |
| Rocket | 0.15 [0.13, 0.16]; total=209, n=775m | 0.01 [0.00, 0.01]; total=27, n=848m | 0.02 [0.00, 0.05]; total=2, n=46m |

### 2x: card rates, bot versus humans

| Card, per minute | Bot | Human all decks | Human X-Bow sides |
|---|---|---|---|
| Skeletons | 2.37 [2.33, 2.41]; total=2315, n=747m | 0.86 [0.80, 0.91]; total=2184, n=815m | 2.27 [2.10, 2.45]; total=179, n=45m |
| Log | 1.91 [1.85, 1.96]; total=1866, n=747m | 0.41 [0.36, 0.45]; total=1035, n=815m | 1.66 [1.48, 1.84]; total=131, n=45m |
| Knight | 2.37 [2.33, 2.41]; total=2316, n=747m | 0.39 [0.34, 0.43]; total=992, n=815m | 1.98 [1.76, 2.20]; total=156, n=45m |
| Ice Wizard | 2.44 [2.40, 2.48]; total=2385, n=747m | 0.17 [0.14, 0.20]; total=426, n=815m | 0.55 [0.29, 0.80]; total=43, n=45m |
| Tornado | 0.85 [0.80, 0.90]; total=832, n=747m | 0.15 [0.13, 0.17]; total=375, n=815m | 0.29 [0.13, 0.45]; total=23, n=45m |
| Tesla | 1.78 [1.74, 1.83]; total=1745, n=747m | 0.18 [0.15, 0.21]; total=454, n=815m | 1.40 [1.16, 1.63]; total=110, n=45m |
| X-Bow | 1.26 [1.21, 1.30]; total=1230, n=747m | 0.05 [0.04, 0.07]; total=134, n=815m | 1.70 [1.49, 1.91]; total=134, n=45m |
| Rocket | 0.42 [0.38, 0.46]; total=411, n=747m | 0.04 [0.03, 0.06]; total=112, n=815m | 0.30 [0.13, 0.47]; total=24, n=45m |

### 3x: card rates, bot versus humans

| Card, per minute | Bot | Human all decks | Human X-Bow sides |
|---|---|---|---|
| Skeletons | 3.33 [3.14, 3.52]; total=374, n=167m | 1.41 [1.28, 1.55]; total=793, n=364m | 2.88 [2.49, 3.28]; total=69, n=33m |
| Log | 2.92 [2.73, 3.11]; total=328, n=167m | 0.82 [0.70, 0.94]; total=459, n=364m | 2.84 [2.37, 3.32]; total=68, n=33m |
| Knight | 3.37 [3.21, 3.54]; total=379, n=167m | 0.59 [0.49, 0.68]; total=329, n=364m | 2.59 [2.14, 3.04]; total=62, n=33m |
| Ice Wizard | 3.53 [3.39, 3.68]; total=397, n=167m | 0.30 [0.22, 0.37]; total=168, n=364m | 1.17 [0.52, 1.82]; total=28, n=33m |
| Tornado | 1.51 [1.32, 1.70]; total=170, n=167m | 0.20 [0.16, 0.25]; total=114, n=364m | 0.42 [0.11, 0.73]; total=10, n=33m |
| Tesla | 2.57 [2.38, 2.76]; total=289, n=167m | 0.36 [0.28, 0.43]; total=199, n=364m | 2.38 [1.86, 2.91]; total=57, n=33m |
| X-Bow | 0.85 [0.68, 1.01]; total=95, n=167m | 0.05 [0.03, 0.08]; total=30, n=364m | 1.25 [0.78, 1.73]; total=30, n=33m |
| Rocket | 1.48 [1.28, 1.67]; total=166, n=167m | 0.10 [0.06, 0.14]; total=57, n=364m | 0.54 [0.13, 0.96]; total=13, n=33m |

### Placement comparisons

All lane × zone rates and X-Bow cell histograms for both cohorts are in report.json. Below are the placements most directly comparable without board state.

| Phase / placement, per minute | Bot | Human all decks | Human X-Bow sides |
|---|---|---|---|
| 1x Bridge X-Bow | 0.63 [0.60, 0.66]; total=912, n=775m | 0.02 [0.01, 0.03]; total=67, n=848m | 0.73 [0.60, 0.86]; total=67, n=46m |
| 1x Defensive X-Bow | 0.13 [0.11, 0.15]; total=185, n=775m | 0.00 [0.0001, 0.0034]; total=6, n=848m | 0.07 [0.01, 0.12]; total=6, n=46m |
| 1x Rocket tower geometry | 0.10 [0.09, 0.12]; total=147, n=775m | 0.00 [0.0020, 0.0063]; total=14, n=848m | 0.00 [0.00, 0.04]; total=0, n=46m |
| 2x Bridge X-Bow | 1.03 [0.98, 1.07]; total=1005, n=747m | 0.04 [0.02, 0.05]; total=98, n=815m | 1.24 [0.99, 1.50]; total=98, n=45m |
| 2x Defensive X-Bow | 0.23 [0.20, 0.26]; total=224, n=747m | 0.01 [0.01, 0.02]; total=36, n=815m | 0.46 [0.29, 0.62]; total=36, n=45m |
| 2x Rocket tower geometry | 0.32 [0.28, 0.36]; total=314, n=747m | 0.02 [0.02, 0.03]; total=63, n=815m | 0.15 [0.03, 0.28]; total=12, n=45m |
| 3x Bridge X-Bow | 0.70 [0.55, 0.86]; total=79, n=167m | 0.05 [0.02, 0.07]; total=26, n=364m | 1.09 [0.62, 1.55]; total=26, n=33m |
| 3x Defensive X-Bow | 0.14 [0.08, 0.21]; total=16, n=167m | 0.01 [0.00, 0.01]; total=4, n=364m | 0.17 [0.01, 0.32]; total=4, n=33m |
| 3x Rocket tower geometry | 1.39 [1.19, 1.59]; total=156, n=167m | 0.08 [0.05, 0.11]; total=44, n=364m | 0.42 [0.08, 0.76]; total=10, n=33m |

## Bot: all

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Observed minutes (n matches) | 1441.3 (n=775) | 978.2 (n=747) | 112.4 (n=167) |
| Own elixir at decisions | 5.08 (n=158899) | 4.53 (n=99869) | 4.40 (n=10270) |
| Own elixir at plays | 6.06 (n=11155) | 5.18 (n=13100) | 4.78 (n=2198) |
| Enemy units on our side at play | 0.95 (n=11155) | 1.51 (n=13100) | 1.70 (n=2198) |
| Enemy nominal elixir on our side | 3.18 (n=11155) | 4.96 (n=13100) | 5.64 (n=2198) |
| Own bodies alive at play | 1.29 (n=11155) | 2.41 (n=13100) | 3.32 (n=2198) |
| Elixir at push crossing | 4.22 (n=3868) | 4.07 (n=2915) | 4.17 (n=368) |
| Response seconds, observed responses | 2.72 (n=2518) | 2.13 (n=2140) | 1.38 (n=291) |
| X-Bow elixir | 8.82 (n=1097) | 7.58 (n=1230) | 7.03 (n=95) |
| X-Bow following 20s tower damage, all sources | 1543.23 (n=1097) | 1012.59 (n=1230) | 849.28 (n=95) |
| Cap seconds/min, both endpoints at 10 | 1.38 [1.22, 1.55]; total=1995.5, n=775m | 0.42 [0.24, 0.59]; total=407, n=747m | 0.08 [0.01, 0.16]; total=9.15, n=167m |
| Plays/min | 7.74 [7.68, 7.80]; total=11155, n=775m | 13.39 [13.27, 13.52]; total=13100, n=747m | 19.56 [19.07, 20.05]; total=2198, n=167m |
| Cheap quiet cycles/min | 1.03 [0.97, 1.09]; total=1487, n=775m | 1.00 [0.91, 1.10]; total=983, n=747m | 1.10 [0.69, 1.51]; total=124, n=167m |
| Quiet defensive plays/min | 0.91 [0.85, 0.96]; total=1306, n=775m | 0.74 [0.67, 0.81]; total=725, n=747m | 0.53 [0.35, 0.71]; total=59, n=167m |
| Quiet defensive elixir/min | 2.52 [2.37, 2.67]; total=3635, n=775m | 2.11 [1.92, 2.30]; total=2066, n=747m | 1.61 [1.09, 2.13]; total=181, n=167m |
| Overcommit engagements/min | 0.07 [0.06, 0.08]; total=100, n=775m | 0.20 [0.17, 0.23]; total=196, n=747m | 0.40 [0.28, 0.52]; total=45, n=167m |
| Overcommit excess elixir/min | 0.10 [0.07, 0.13]; total=146.967, n=775m | 0.42 [0.35, 0.50]; total=415.717, n=747m | 1.10 [0.72, 1.47]; total=123.3, n=167m |
| Tower HP dealt/min | 1430.83 [1351.92, 1509.75]; total=2.06232e+06, n=775m | 1939.19 [1822.33, 2056.05]; total=1.89694e+06, n=747m | 2214.46 [1881.00, 2547.92]; total=248839, n=167m |
| Tower HP taken/min | 1915.38 [1778.26, 2052.50]; total=2.76071e+06, n=775m | 1975.55 [1816.14, 2134.96]; total=1.93251e+06, n=747m | 1158.88 [966.00, 1351.76]; total=130223, n=167m |
| Crowns gained/min | 0.10 [0.09, 0.12]; total=150, n=775m | 0.34 [0.30, 0.37]; total=328, n=747m | 0.58 [0.44, 0.71]; total=65, n=167m |
| Crowns lost/min | 0.18 [0.15, 0.21]; total=258, n=775m | 0.37 [0.32, 0.41]; total=358, n=747m | 0.41 [0.29, 0.53]; total=46, n=167m |
| Positive trade PROXY/min | 2.24 [2.18, 2.31]; total=3233, n=775m | 1.91 [1.82, 1.99]; total=1866, n=747m | 1.51 [1.27, 1.76]; total=170, n=167m |
| Negative trade PROXY/min | 0.23 [0.21, 0.26]; total=332, n=775m | 0.45 [0.40, 0.49]; total=436, n=747m | 0.66 [0.51, 0.81]; total=74, n=167m |
| Net nominal trade PROXY/min | 19.66 [18.31, 21.02]; total=28343.3, n=775m | 17.15 [15.35, 18.95]; total=16777.5, n=747m | 10.92 [6.82, 15.02]; total=1226.92, n=167m |
| X-Bow observed tower locks/min | 0.49 [0.46, 0.52]; total=708, n=775m | 0.58 [0.54, 0.62]; total=569, n=747m | 0.28 [0.19, 0.38]; total=32, n=167m |
| Rocket tower targets/min | 0.10 [0.09, 0.12]; total=147, n=775m | 0.32 [0.28, 0.36]; total=314, n=747m | 1.39 [1.19, 1.59]; total=156, n=167m |
| Enemy big-spell contact episodes/min | 0.04 [0.03, 0.05]; total=52, n=775m | 0.08 [0.06, 0.10]; total=77, n=747m | 0.27 [0.14, 0.39]; total=30, n=167m |
| Enemy other-spell contact episodes/min | 0.14 [0.11, 0.16]; total=197, n=775m | 0.40 [0.34, 0.45]; total=387, n=747m | 0.97 [0.75, 1.19]; total=109, n=167m |
| Spell-associated HP taken/min, not causal | 49.97 [35.18, 64.76]; total=72024, n=775m | 90.41 [66.88, 113.94]; total=88443, n=747m | 244.75 [162.52, 326.97]; total=27502, n=167m |
| Unattributed HP taken/min | 1865.41 [1729.25, 2001.57]; total=2.68868e+06, n=775m | 1885.14 [1727.97, 2042.30]; total=1.84407e+06, n=747m | 914.13 [736.17, 1092.10]; total=102721, n=167m |

## Bot: wins

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Observed minutes (n matches) | 747.9 (n=399) | 543.9 (n=399) | 62.1 (n=93) |
| Own elixir at decisions | 5.27 (n=82359) | 4.58 (n=55484) | 4.41 (n=5702) |
| Own elixir at plays | 6.30 (n=5749) | 5.32 (n=7243) | 4.80 (n=1204) |
| Enemy units on our side at play | 0.71 (n=5749) | 1.05 (n=7243) | 1.62 (n=1204) |
| Enemy nominal elixir on our side | 2.33 (n=5749) | 3.45 (n=7243) | 5.22 (n=1204) |
| Own bodies alive at play | 1.33 (n=5749) | 2.58 (n=7243) | 3.37 (n=1204) |
| Elixir at push crossing | 4.37 (n=2032) | 4.06 (n=1709) | 4.07 (n=219) |
| Response seconds, observed responses | 2.45 (n=1260) | 2.09 (n=1245) | 1.40 (n=166) |
| X-Bow elixir | 8.77 (n=596) | 7.54 (n=726) | 7.05 (n=48) |
| X-Bow following 20s tower damage, all sources | 1574.67 (n=596) | 1199.07 (n=726) | 1283.96 (n=48) |
| Cap seconds/min, both endpoints at 10 | 1.38 [1.18, 1.58]; total=1031.7, n=399m | 0.22 [0.04, 0.39]; total=117.85, n=399m | 0.08 [0.00, 0.16]; total=4.75, n=93m |
| Plays/min | 7.69 [7.61, 7.76]; total=5749, n=399m | 13.32 [13.16, 13.47]; total=7243, n=399m | 19.39 [18.72, 20.07]; total=1204, n=93m |
| Cheap quiet cycles/min | 1.16 [1.08, 1.24]; total=867, n=399m | 1.23 [1.08, 1.38]; total=669, n=399m | 1.10 [0.52, 1.67]; total=68, n=93m |
| Quiet defensive plays/min | 1.03 [0.96, 1.10]; total=771, n=399m | 0.88 [0.79, 0.98]; total=480, n=399m | 0.58 [0.32, 0.84]; total=36, n=93m |
| Quiet defensive elixir/min | 2.90 [2.69, 3.11]; total=2168, n=399m | 2.49 [2.22, 2.75]; total=1352, n=399m | 1.72 [1.00, 2.45]; total=107, n=93m |
| Overcommit engagements/min | 0.08 [0.06, 0.10]; total=61, n=399m | 0.20 [0.16, 0.23]; total=107, n=399m | 0.37 [0.22, 0.52]; total=23, n=93m |
| Overcommit excess elixir/min | 0.11 [0.08, 0.15]; total=85.8667, n=399m | 0.39 [0.30, 0.49]; total=214.117, n=399m | 1.03 [0.56, 1.51]; total=64.2, n=93m |
| Tower HP dealt/min | 1522.34 [1410.30, 1634.37]; total=1.13855e+06, n=399m | 2422.24 [2252.70, 2591.78]; total=1.3174e+06, n=399m | 3008.85 [2484.68, 3533.02]; total=186787, n=93m |
| Tower HP taken/min | 990.32 [906.26, 1074.37]; total=740656, n=399m | 930.62 [840.76, 1020.48]; total=506140, n=399m | 834.26 [618.67, 1049.85]; total=51790, n=93m |
| Crowns gained/min | 0.13 [0.10, 0.15]; total=96, n=399m | 0.51 [0.46, 0.56]; total=275, n=399m | 1.05 [0.82, 1.28]; total=65, n=93m |
| Crowns lost/min | 0.01 [0.00, 0.02]; total=10, n=399m | 0.04 [0.03, 0.06]; total=23, n=399m | 0.00 [0.00, 0.06]; total=0, n=93m |
| Positive trade PROXY/min | 2.29 [2.20, 2.37]; total=1711, n=399m | 2.07 [1.95, 2.18]; total=1124, n=399m | 1.84 [1.48, 2.19]; total=114, n=93m |
| Negative trade PROXY/min | 0.26 [0.23, 0.30]; total=196, n=399m | 0.47 [0.41, 0.53]; total=258, n=399m | 0.53 [0.35, 0.71]; total=33, n=93m |
| Net nominal trade PROXY/min | 17.23 [15.57, 18.89]; total=12888.1, n=399m | 17.83 [15.40, 20.26]; total=9697.5, n=399m | 14.90 [8.49, 21.31]; total=924.85, n=93m |
| X-Bow observed tower locks/min | 0.53 [0.49, 0.57]; total=398, n=399m | 0.73 [0.67, 0.78]; total=395, n=399m | 0.37 [0.24, 0.50]; total=23, n=93m |
| Rocket tower targets/min | 0.11 [0.08, 0.13]; total=80, n=399m | 0.38 [0.32, 0.43]; total=205, n=399m | 1.68 [1.40, 1.95]; total=104, n=93m |
| Enemy big-spell contact episodes/min | 0.05 [0.03, 0.07]; total=38, n=399m | 0.09 [0.06, 0.12]; total=51, n=399m | 0.19 [0.07, 0.31]; total=12, n=93m |
| Enemy other-spell contact episodes/min | 0.16 [0.13, 0.19]; total=121, n=399m | 0.42 [0.35, 0.50]; total=230, n=399m | 0.92 [0.62, 1.21]; total=57, n=93m |
| Spell-associated HP taken/min, not causal | 45.60 [30.67, 60.53]; total=34104, n=399m | 74.14 [55.73, 92.55]; total=40322, n=399m | 227.63 [116.92, 338.34]; total=14131, n=93m |
| Unattributed HP taken/min | 944.72 [861.86, 1027.58]; total=706552, n=399m | 856.48 [767.39, 945.57]; total=465818, n=399m | 606.63 [440.01, 773.25]; total=37659, n=93m |

## Bot: losses

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Observed minutes (n matches) | 687.8 (n=373) | 431.0 (n=345) | 50.3 (n=74) |
| Own elixir at decisions | 4.88 (n=75953) | 4.47 (n=44109) | 4.40 (n=4568) |
| Own elixir at plays | 5.80 (n=5359) | 5.00 (n=5806) | 4.76 (n=994) |
| Enemy units on our side at play | 1.21 (n=5359) | 2.09 (n=5806) | 1.80 (n=994) |
| Enemy nominal elixir on our side | 4.10 (n=5359) | 6.87 (n=5806) | 6.15 (n=994) |
| Own bodies alive at play | 1.25 (n=5359) | 2.19 (n=5806) | 3.25 (n=994) |
| Elixir at push crossing | 4.03 (n=1819) | 4.09 (n=1191) | 4.32 (n=149) |
| Response seconds, observed responses | 2.99 (n=1247) | 2.19 (n=883) | 1.36 (n=125) |
| X-Bow elixir | 8.88 (n=498) | 7.64 (n=500) | 7.01 (n=47) |
| X-Bow following 20s tower damage, all sources | 1505.78 (n=498) | 735.40 (n=500) | 405.36 (n=47) |
| Cap seconds/min, both endpoints at 10 | 1.39 [1.12, 1.65]; total=954.8, n=373m | 0.67 [0.33, 1.01]; total=289.15, n=345m | 0.09 [0.00, 0.21]; total=4.4, n=74m |
| Plays/min | 7.79 [7.69, 7.89]; total=5359, n=373m | 13.47 [13.27, 13.67]; total=5806, n=345m | 19.77 [19.06, 20.47]; total=994, n=74m |
| Cheap quiet cycles/min | 0.90 [0.81, 0.98]; total=616, n=373m | 0.72 [0.61, 0.84]; total=312, n=345m | 1.11 [0.52, 1.70]; total=56, n=74m |
| Quiet defensive plays/min | 0.77 [0.70, 0.85]; total=532, n=373m | 0.57 [0.48, 0.66]; total=244, n=345m | 0.46 [0.21, 0.71]; total=23, n=74m |
| Quiet defensive elixir/min | 2.12 [1.91, 2.34]; total=1460, n=373m | 1.65 [1.39, 1.91]; total=711, n=345m | 1.47 [0.72, 2.22]; total=74, n=74m |
| Overcommit engagements/min | 0.06 [0.04, 0.07]; total=38, n=373m | 0.20 [0.16, 0.24]; total=86, n=345m | 0.44 [0.24, 0.64]; total=22, n=74m |
| Overcommit excess elixir/min | 0.09 [0.05, 0.13]; total=60.1, n=373m | 0.46 [0.33, 0.59]; total=199.1, n=345m | 1.18 [0.58, 1.77]; total=59.1, n=74m |
| Tower HP dealt/min | 1338.93 [1228.27, 1449.60]; total=920940, n=373m | 1313.58 [1179.98, 1447.18]; total=566170, n=345m | 1233.86 [935.80, 1531.92]; total=62052, n=74m |
| Tower HP taken/min | 2926.75 [2690.67, 3162.84]; total=2.01307e+06, n=373m | 3298.44 [2986.15, 3610.72]; total=1.42167e+06, n=345m | 1559.59 [1227.48, 1891.70]; total=78433, n=74m |
| Crowns gained/min | 0.08 [0.06, 0.10]; total=54, n=373m | 0.12 [0.09, 0.15]; total=53, n=345m | 0.00 [0.00, 0.07]; total=0, n=74m |
| Crowns lost/min | 0.36 [0.31, 0.41]; total=248, n=373m | 0.78 [0.69, 0.87]; total=335, n=345m | 0.91 [0.65, 1.18]; total=46, n=74m |
| Positive trade PROXY/min | 2.19 [2.10, 2.28]; total=1508, n=373m | 1.71 [1.58, 1.83]; total=735, n=345m | 1.11 [0.83, 1.40]; total=56, n=74m |
| Negative trade PROXY/min | 0.20 [0.16, 0.23]; total=135, n=373m | 0.40 [0.34, 0.47]; total=173, n=345m | 0.82 [0.57, 1.06]; total=41, n=74m |
| Net nominal trade PROXY/min | 22.37 [20.22, 24.53]; total=15388.5, n=373m | 16.35 [13.66, 19.04]; total=7047.65, n=345m | 6.01 [1.73, 10.29]; total=302.067, n=74m |
| X-Bow observed tower locks/min | 0.45 [0.41, 0.49]; total=309, n=373m | 0.40 [0.35, 0.45]; total=171, n=345m | 0.18 [0.06, 0.30]; total=9, n=74m |
| Rocket tower targets/min | 0.10 [0.07, 0.12]; total=67, n=373m | 0.25 [0.20, 0.30]; total=108, n=345m | 1.03 [0.77, 1.30]; total=52, n=74m |
| Enemy big-spell contact episodes/min | 0.02 [0.01, 0.03]; total=14, n=373m | 0.06 [0.03, 0.09]; total=26, n=345m | 0.36 [0.12, 0.60]; total=18, n=74m |
| Enemy other-spell contact episodes/min | 0.11 [0.07, 0.14]; total=73, n=373m | 0.36 [0.28, 0.44]; total=156, n=345m | 1.03 [0.69, 1.38]; total=52, n=74m |
| Spell-associated HP taken/min, not causal | 55.13 [28.72, 81.54]; total=37920, n=373m | 111.65 [63.58, 159.72]; total=48121, n=345m | 265.87 [141.96, 389.79]; total=13371, n=74m |
| Unattributed HP taken/min | 2871.62 [2637.05, 3106.19]; total=1.97515e+06, n=373m | 3186.79 [2879.08, 3494.50]; total=1.37355e+06, n=345m | 1293.71 [961.89, 1625.54]; total=65062, n=74m |

## Bot: big losses

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Observed minutes (n matches) | 202.4 (n=114) | 59.4 (n=86) | 0.1 (n=1) |
| Own elixir at decisions | 4.59 (n=22353) | 4.47 (n=5970) | 2.44 (n=6) |
| Own elixir at plays | 5.35 (n=1554) | 4.36 (n=749) | 2.71 (n=1) |
| Enemy units on our side at play | 1.62 (n=1554) | 3.69 (n=749) | 4.00 (n=1) |
| Enemy nominal elixir on our side | 5.81 (n=1554) | 12.77 (n=749) | 16.00 (n=1) |
| Own bodies alive at play | 1.25 (n=1554) | 1.81 (n=749) | 0.00 (n=1) |
| Elixir at push crossing | 3.69 (n=502) | 4.15 (n=95) | unavailable |
| Response seconds, observed responses | 3.53 (n=360) | 2.05 (n=77) | unavailable |
| X-Bow elixir | 8.89 (n=169) | 7.72 (n=48) | unavailable |
| X-Bow following 20s tower damage, all sources | 1850.73 (n=169) | 819.94 (n=48) | unavailable |
| Cap seconds/min, both endpoints at 10 | 2.00 [1.35, 2.65]; total=404.7, n=114m | 3.13 [1.32, 4.95]; total=186.15, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Plays/min | 7.68 [7.46, 7.90]; total=1554, n=114m | 12.60 [11.83, 13.38]; total=749, n=86m | 9.76 [95% CI not estimable]; total=1, n=1m |
| Cheap quiet cycles/min | 0.60 [0.48, 0.72]; total=122, n=114m | 0.37 [0.15, 0.59]; total=22, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Quiet defensive plays/min | 0.51 [0.40, 0.62]; total=103, n=114m | 0.24 [0.11, 0.36]; total=14, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Quiet defensive elixir/min | 1.42 [1.10, 1.73]; total=287, n=114m | 0.79 [0.38, 1.21]; total=47, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Overcommit engagements/min | 0.02 [0.00, 0.05]; total=5, n=114m | 0.12 [0.04, 0.20]; total=7, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Overcommit excess elixir/min | 0.02 [0.00, 0.05]; total=4.8, n=114m | 0.30 [0.05, 0.55]; total=18.0333, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Tower HP dealt/min | 1848.02 [1635.81, 2060.23]; total=373948, n=114m | 1039.93 [750.15, 1329.72]; total=61805, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Tower HP taken/min | 5176.42 [4647.39, 5705.45]; total=1.04745e+06, n=114m | 9292.64 [8171.84, 10413.44]; total=552277, n=86m | 5385.37 [95% CI not estimable]; total=552, n=1m |
| Crowns gained/min | 0.11 [0.07, 0.15]; total=22, n=114m | 0.27 [0.16, 0.38]; total=16, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Crowns lost/min | 0.84 [0.71, 0.96]; total=169, n=114m | 2.68 [2.31, 3.04]; total=159, n=86m | 19.51 [95% CI not estimable]; total=2, n=1m |
| Positive trade PROXY/min | 1.92 [1.77, 2.07]; total=388, n=114m | 0.67 [0.47, 0.88]; total=40, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Negative trade PROXY/min | 0.10 [0.06, 0.14]; total=20, n=114m | 0.15 [0.06, 0.24]; total=9, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Net nominal trade PROXY/min | 23.15 [19.17, 27.13]; total=4684.53, n=114m | 6.46 [3.07, 9.84]; total=383.7, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| X-Bow observed tower locks/min | 0.59 [0.52, 0.66]; total=120, n=114m | 0.34 [0.21, 0.46]; total=20, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Rocket tower targets/min | 0.09 [0.05, 0.13]; total=18, n=114m | 0.20 [0.10, 0.31]; total=12, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Enemy big-spell contact episodes/min | 0.00 [0.00, 0.01]; total=1, n=114m | 0.02 [0.00, 0.05]; total=1, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Enemy other-spell contact episodes/min | 0.11 [0.05, 0.18]; total=23, n=114m | 0.27 [0.10, 0.44]; total=16, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Spell-associated HP taken/min, not causal | 105.91 [31.24, 180.58]; total=21431, n=114m | 215.66 [27.83, 403.48]; total=12817, n=86m | 0.00 [95% CI not estimable]; total=0, n=1m |
| Unattributed HP taken/min | 5070.51 [4540.25, 5600.77]; total=1.02602e+06, n=114m | 9076.98 [7979.08, 10174.87]; total=539460, n=86m | 5385.37 [95% CI not estimable]; total=552, n=1m |

## Cards played per minute

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| IceWizard | 1.34 [1.32, 1.36]; total=1929, n=775m | 2.44 [2.40, 2.48]; total=2385, n=747m | 3.53 [3.39, 3.68]; total=397, n=167m |
| Knight | 1.30 [1.27, 1.32]; total=1868, n=775m | 2.37 [2.33, 2.41]; total=2316, n=747m | 3.37 [3.21, 3.54]; total=379, n=167m |
| Log | 1.26 [1.23, 1.29]; total=1819, n=775m | 1.91 [1.85, 1.96]; total=1866, n=747m | 2.92 [2.73, 3.11]; total=328, n=167m |
| Rocket | 0.15 [0.13, 0.16]; total=209, n=775m | 0.42 [0.38, 0.46]; total=411, n=747m | 1.48 [1.28, 1.67]; total=166, n=167m |
| Skeletons | 1.41 [1.39, 1.44]; total=2035, n=775m | 2.37 [2.33, 2.41]; total=2315, n=747m | 3.33 [3.14, 3.52]; total=374, n=167m |
| Tesla | 1.04 [1.02, 1.07]; total=1506, n=775m | 1.78 [1.74, 1.83]; total=1745, n=747m | 2.57 [2.38, 2.76]; total=289, n=167m |
| Tornado | 0.48 [0.45, 0.51]; total=692, n=775m | 0.85 [0.80, 0.90]; total=832, n=747m | 1.51 [1.32, 1.70]; total=170, n=167m |
| Xbow | 0.76 [0.73, 0.79]; total=1097, n=775m | 1.26 [1.21, 1.30]; total=1230, n=747m | 0.85 [0.68, 1.01]; total=95, n=167m |

## Lane × zone placements per minute

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| left.bridge | 1.63 [1.56, 1.71]; total=2356, n=775m | 2.89 [2.72, 3.06]; total=2830, n=747m | 4.83 [4.09, 5.58]; total=543, n=167m |
| left.enemy_side | 0.12 [0.10, 0.14]; total=170, n=775m | 0.39 [0.34, 0.43]; total=379, n=747m | 1.19 [0.94, 1.44]; total=134, n=167m |
| left.own_back | 0.80 [0.74, 0.86]; total=1152, n=775m | 1.09 [1.00, 1.19]; total=1070, n=747m | 1.21 [0.87, 1.55]; total=136, n=167m |
| left.own_front | 1.43 [1.36, 1.50]; total=2059, n=775m | 2.12 [2.01, 2.24]; total=2077, n=747m | 2.03 [1.74, 2.32]; total=228, n=167m |
| right.bridge | 1.20 [1.13, 1.27]; total=1729, n=775m | 2.89 [2.72, 3.05]; total=2823, n=747m | 4.92 [4.20, 5.64]; total=553, n=167m |
| right.enemy_side | 0.13 [0.12, 0.15]; total=194, n=775m | 0.36 [0.31, 0.40]; total=350, n=747m | 1.02 [0.82, 1.23]; total=115, n=167m |
| right.own_back | 0.63 [0.58, 0.68]; total=909, n=775m | 0.94 [0.85, 1.03]; total=920, n=747m | 1.24 [0.88, 1.59]; total=139, n=167m |
| right.own_front | 1.79 [1.72, 1.86]; total=2586, n=775m | 2.71 [2.59, 2.83]; total=2651, n=747m | 3.11 [2.71, 3.52]; total=350, n=167m |

## Own spell targeting geometry per minute

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Log.both | 0.66 [0.63, 0.69]; total=951, n=775m | 0.98 [0.92, 1.03]; total=954, n=747m | 1.50 [1.28, 1.73]; total=169, n=167m |
| Log.neither | 0.06 [0.05, 0.08]; total=92, n=775m | 0.13 [0.11, 0.16]; total=131, n=747m | 0.25 [0.12, 0.38]; total=28, n=167m |
| Log.tower | 0.15 [0.13, 0.17]; total=219, n=775m | 0.05 [0.04, 0.07]; total=53, n=747m | 0.07 [0.02, 0.13]; total=8, n=167m |
| Log.units | 0.39 [0.36, 0.41]; total=557, n=775m | 0.74 [0.69, 0.80]; total=728, n=747m | 1.09 [0.90, 1.29]; total=123, n=167m |
| Rocket.both | 0.02 [0.01, 0.02]; total=23, n=775m | 0.05 [0.03, 0.06]; total=45, n=747m | 0.09 [0.04, 0.14]; total=10, n=167m |
| Rocket.neither | 0.01 [0.01, 0.02]; total=18, n=775m | 0.03 [0.02, 0.04]; total=29, n=747m | 0.01 [0.00, 0.03]; total=1, n=167m |
| Rocket.tower | 0.09 [0.07, 0.10]; total=124, n=775m | 0.27 [0.24, 0.31]; total=269, n=747m | 1.30 [1.11, 1.49]; total=146, n=167m |
| Rocket.units | 0.03 [0.02, 0.04]; total=44, n=775m | 0.07 [0.05, 0.09]; total=68, n=747m | 0.08 [0.01, 0.15]; total=9, n=167m |
| Tornado.both | 0.10 [0.08, 0.11]; total=143, n=775m | 0.18 [0.15, 0.20]; total=173, n=747m | 0.44 [0.32, 0.55]; total=49, n=167m |
| Tornado.neither | 0.14 [0.12, 0.16]; total=200, n=775m | 0.12 [0.10, 0.14]; total=116, n=747m | 0.12 [0.06, 0.18]; total=13, n=167m |
| Tornado.tower | 0.01 [0.00, 0.01]; total=9, n=775m | 0.01 [0.00, 0.02]; total=10, n=747m | 0.03 [0.00, 0.06]; total=3, n=167m |
| Tornado.units | 0.24 [0.21, 0.26]; total=340, n=775m | 0.54 [0.50, 0.59]; total=533, n=747m | 0.93 [0.75, 1.12]; total=105, n=167m |

## Enemy spell tower-contact candidates per minute

| Metric | 1x | 2x | 3x |
|---|---|---|---|
| Arrows | 0.05 [0.03, 0.07]; total=72, n=775m | 0.16 [0.12, 0.20]; total=155, n=747m | 0.38 [0.22, 0.54]; total=43, n=167m |
| BarbLog | 0.02 [0.01, 0.03]; total=30, n=775m | 0.03 [0.02, 0.05]; total=33, n=747m | 0.06 [0.01, 0.11]; total=7, n=167m |
| Earthquake | 0.00 [0.0000, 0.0026]; total=0, n=775m | 0.00 [0.0000, 0.0038]; total=0, n=747m | 0.00 [0.00, 0.03]; total=0, n=167m |
| Fireball | 0.03 [0.02, 0.04]; total=40, n=775m | 0.05 [0.03, 0.07]; total=49, n=747m | 0.13 [0.05, 0.21]; total=15, n=167m |
| Lightning | 0.00 [0.0000, 0.0021]; total=1, n=775m | 0.00 [0.0000, 0.0049]; total=2, n=747m | 0.00 [0.00, 0.03]; total=0, n=167m |
| Log | 0.06 [0.04, 0.07]; total=83, n=775m | 0.18 [0.14, 0.21]; total=172, n=747m | 0.44 [0.27, 0.62]; total=50, n=167m |
| Poison | 0.00 [0.0000, 0.0026]; total=0, n=775m | 0.00 [0.0000, 0.0038]; total=0, n=747m | 0.00 [0.00, 0.03]; total=0, n=167m |
| Rocket | 0.01 [0.00, 0.01]; total=11, n=775m | 0.03 [0.01, 0.04]; total=26, n=747m | 0.13 [0.03, 0.24]; total=15, n=167m |
| Snowball | 0.01 [0.00, 0.01]; total=12, n=775m | 0.03 [0.01, 0.04]; total=27, n=747m | 0.08 [0.01, 0.15]; total=9, n=167m |
| Vines | 0.00 [0.0000, 0.0026]; total=0, n=775m | 0.00 [0.0000, 0.0038]; total=0, n=747m | 0.00 [0.00, 0.03]; total=0, n=167m |
| Zap | 0.00 [0.0000, 0.0026]; total=0, n=775m | 0.00 [0.0000, 0.0038]; total=0, n=747m | 0.00 [0.00, 0.03]; total=0, n=167m |

## Definitions and limits

- Rate CIs: ratio-of-sums, match-cluster delta-method normal 95% intervals; human sides cluster by replay. Nonnegative lower bounds are truncated at zero. Zero events use a rule-of-three-style upper bound. Small groups and rare events have approximate coverage; one-cluster CIs are unavailable. Means have their actual observation n; repeated decisions are not independent matches.
- Lane uses own-frame x<9 left, otherwise right. Zones use y<15 enemy side, 15–18 bridge, >18–<24 own front, >=24 own back; own edge is y=32. The broader X-Bow offensive bridge class is y=16–21; deeper bows are defensive. Cells are floor(tile x), floor(tile y). Human coordinates use data-i: rotate team when index=1, opponent when index=0; bot raw bodies rotate only for observer side 0. Bot play/model xy has mirrored x: placement x=18−18*xy[0], y=32*xy[1]. This is checked against actual post-confirmation public X-Bow/Tesla body coordinates; placement alignment errors are reported.
- At-play board and elixir use the last PUBLIC decision at or before the confirmed tap attempt, max age 2s for board. Raw elixir is preferred over the play-event forecast; both are retained. Tower HP means include present towers only; destroyed/missing towers are explicit in event receipts. Units are bodies (buildings included at play); Hero Ice Wizard floating-cube duplicates are removed by category/position.
- Nominal body elixir = catalog card cost / standard spawn count. It is NOT actual opponent spend: spawned tokens, split cards, evolutions, death spawns, abilities, duplicate identities and transformations can violate it. Unknown IDs are counted and receive no imputed value. Exact enemy committed/killed elixir and exact elixir trades are unavailable.
- Push starts when the same observed enemy body moves from y<16 to y>=16 within <=3s, in a lane without an active engagement. Ends after 3s with no enemy on our side in that lane. First-seen intrusions are counted separately and do not masquerade as bridge crossings. Elixir is the first post-crossing public sample, with interval uncertainty exported; flying river crossings are included.
- Response = first confirmed own-side card play in that lane (central plays may cover either lane), excluding offensive bridge X-Bows, from crossing until engagement end. Each play goes to at most one engagement. Pre-positioned defence is not a response; no response is censored, not zero. All nominal own spending here excludes abilities. Completed engagements with no unknown entrant value yield trade PROXY = nominal entrant value minus reactive card spend; it does not establish killed value. Engagement totals are assigned to onset phase, so cross-phase spending differs from play-phase totals.
- Quiet cycle = cost <=3 and no visible enemy body at y>=12 (our half plus a 4-tile enemy-side buffer). Quiet defence proxy uses that same threat test and an own-side y>=18 Tesla/IceWizard/Knight/Skeletons/Tornado play. Reported elixir is spend flagged by this heuristic, not proven waste. Overcommit proxy = max(0, reactive spend − nominal entrant value − 2); excludes censored/unknown-value engagements.
- Tower identification requires card_id=-1 AND fixed tower coordinates within 0.2 tiles; moving unknown bodies also use -1 in these logs. Legacy ID-only scorecard outcomes are retained for comparison. Damage uses monotonically decreasing public HP through tick<6000; absence is accepted only with no later reappearance and two missing decisions (or the terminal closed observation). Remaining princess HP removed automatically after king death is excluded from combat damage. HP increases are flagged. Damage is assigned to the observation phase, so boundary damage may shift by one sampling interval. Crowns derive from princess destruction or three for king destruction. Missing opening/end observations can undercount damage and crowns.
- Observed X-Bow lock requires an own X-Bow projectile aimed at a live enemy tower and exactly one own X-Bow alive near that placement. No observed lock means unknown/undetected, not proven no lock. Follow-up damage is total enemy tower HP loss in the next <=20 seconds after placement; locked-target damage is also exported. It includes other attackers/spells and is right-censored near match end. No source-specific damage is claimed.
- Own spell target types are deployment-time geometric footprints, not proven targets/hits. Log/Barbarian Barrel use a forward strip; other spells use explicit approximate radii plus tower radius 1 tile or unit margin 0.5. Rocket-on-tower counts include both tower-only and tower+units. Following 8s target tower HP loss is all-source association; true chip and enemy elixir killed are null.
- Enemy spell counts are sampled projectile-target/spell-body tower-contact EPISODES, not certified hits or casts. Dedupe same spell/tower until >2s observation gap; multi-tower spells count contacts per tower. Radius/target geometry can misclassify; invisible instant spells can be missed completely. Zero observed Poison/Earthquake/Vines is not zero actual usage. Tower HP drops from first sighting through last sighting+5s are spell-associated; damage intervals are deduplicated across candidates. GoblinBarrel/Graveyard/Clone/Mirror/RoyalDelivery summon/copy contacts are separate and do not qualify damage as direct-spell-associated. Remaining damage is unattributed, NOT certified unit damage. Exact spell-versus-unit damage is unavailable.
- Cap occupancy is the observed time with both interval endpoints at >=9.999 elixir and <=2s apart; endpoint-any cap seconds provide a sensitivity measure, not a strict mathematical upper bound if unseen spend/regen happens. No interpolation bridges larger gaps. Multiply by measured phase regen for nominal leaked elixir; no opportunity-cost claim.
- The subset surviving to 3x differs from early-ending matches. Paired comparisons require >=30s in each phase and accompany aggregate findings. Checkpoint/fast flags are tags, not randomized treatments. Missing historical pipeline_decisions is interpreted as false by the scorecard convention, with fast_flag_recorded=false explicitly retained. No causal model-quality or policy-change recommendation follows from these measurements.

## What the human HTML supports

Directly supported: card, tick, side and placement; match end marker; final crowns from captured URL; per-phase plays/card rates, lane/zone, X-Bow cell/bridge/defensive histograms, and Rocket tower-target geometry. Both sides are reported for all decks, X-Bow sides separately, with win/loss/big-loss splits in report.json. Duplicate timeline and map entries are reconciled by using map markers once; ability markers are excluded from card counts.
Unsupported: decision-time or actual play-time elixir; per-phase cap/leak time (HTML has only whole-match aggregate leakage); living units, troop HP and tower HP; push crossings, response timing, defence commitments or trades; X-Bow tower locks and following damage; spell target units/kills/actual chip; threat-conditioned cycling or wasted spend; phase-resolved crowns and damage; enemy spell hits and spell-versus-unit damage. No simulator reconstruction or inferred opponent hidden state was substituted.
The human corpus has no checkpoint or fast-plays flags. X-Bow classification requires an observed X-Bow play and may miss decks that never played it. These opponents, levels, deck mix and selection rules differ from the bot sample; the comparison is descriptive.

## Audit files

`report.json` contains all rate denominators/CIs, outcome splits, checkpoint × fast-plays splits, per-match phase summaries, coverage and input hashes. `plays.jsonl` holds confirmed bot play states and X-Bow/spell receipts. `pushes.jsonl` holds engagements. `enemy_spells.jsonl` holds public contact candidates. `pro_plays.jsonl` holds parsed human plays. No opponent hidden state is exported.

Rerun: `python phase_stats.py --since 20261008`. Tests: use an installed pytest interpreter with `-B -m pytest -q -p no:cacheprovider test_phase_stats.py`; disable plugin autoload.
