# Opponent behaviour: SIM opponents vs real 12k humans

LIVE: 1919 icebow main-account matches since 10-01 (`L74/mix/live_cost_1001.json`), opponent plays reconstructed from reader bodies.  
SIM (primary): `ECON_r1`, 960 matches (learner r1 vs the SIM opponent policy).  d = (SIM mean - LIVE mean) / pooled SD, per match; distance = RMS of d over the features that have n >= 5 on both sides; floor = sqrt(1/nL + 1/nS), the distance two draws of the SAME population give by chance (distance <= ~1.5 x floor = indistinguishable).

Features (opponent side, all from the detected plays): `ppm_1x` plays/min before 2:00; `ppm_2x` plays/min in double elixir + overtime; `own_half` / `bridge` / `our_half` share of plays born on their half (y > 19) / within 3 tiles of the river / on our half (y < 13); `first_tick` tick of their first play; `react_s` mean seconds from OUR play to THEIR next play (cap 10 s, none = 10); `react_3s` share of our plays answered within 3 s; `react_lift` = react_3s minus its chance level (a busier opponent answers more often by luck: the share of the match in which a play of theirs starts within the next 3 s); `push_mean` / `push_max` elixir of plays per 8 s window, mean / max over the match; `spell_share` share of VISIBLE plays that are spells (graveyard, barrels, ... ; bodiless spells never appear); `opp_el` the public opponent-elixir counter at the last decision before the play (a +26-tick forecast on both sources).

**Headline (ALL matches, mix-confounded -- read the archetype rows):** largest gaps `react_3s` live 0.26 vs SIM 0.48 (d +1.87); `react_lift` live -0.05 vs SIM 0.09 (d +1.84); `react_s` live 6.16 vs SIM 4.75 (d -1.45); `ppm_2x` live 8.64 vs SIM 12.20 (d +1.28).

## 1. Distance per archetype (primary SIM: ECON_r1)

| group | n live | n SIM | distance | floor | ppm_1x | ppm_2x | own_half | bridge | our_half | first_tick | react_s | react_3s | react_lift | push_mean | push_max | spell_share | opp_el |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 1919 | 960 | **0.97** | 0.04 | 0.19 | 1.28 | 0.18 | 0.16 | -0.46 | 0.65 | -1.45 | 1.87 | 1.84 | 0.57 | 0.51 | 0.39 | -0.48 |
| arch:royal_giant_monk (small n) | 24 | 7 | **1.87** | 0.43 | 0.32 | 2.25 | 0.81 | -0.76 | -0.33 | 1.23 | -2.53 | 3.66 | 3.04 | 1.31 | 0.62 | 1.73 | -1.87 |
| arch:royal_giant | 55 | 28 | **1.61** | 0.23 | 0.92 | 2.03 | -0.03 | 0.37 | -0.38 | 0.49 | -2.19 | 2.79 | 2.90 | 1.56 | 0.88 | 1.40 | -1.47 |
| arch:pekka_bridge | 28 | 19 | **1.40** | 0.30 | -0.15 | 2.61 | 0.19 | 0.21 | -0.53 | 0.55 | -2.16 | 2.55 | 1.75 | 1.29 | 0.53 | - | 0.13 |
| arch:weak_other | 838 | 375 | **1.21** | 0.06 | 0.38 | 1.69 | 0.13 | 0.30 | -0.58 | 0.82 | -1.85 | 2.34 | 2.01 | 0.78 | 0.63 | 0.80 | -0.62 |
| arch:lava_hound | 37 | 38 | **1.18** | 0.23 | -0.44 | 1.31 | 0.41 | 0.30 | -1.06 | 0.65 | -1.55 | 2.35 | 2.31 | 0.49 | 0.95 | -0.12 | 0.06 |
| arch:hyperbait | 89 | 59 | **1.18** | 0.17 | 0.68 | 2.05 | -0.46 | 0.28 | 0.24 | -0.08 | -1.80 | 2.07 | 1.23 | 1.46 | 0.70 | -0.82 | -0.88 |
| arch:golem | 109 | 95 | **1.00** | 0.14 | -0.63 | 0.87 | 0.55 | 0.09 | -0.67 | 1.07 | -1.31 | 1.94 | 1.94 | -0.54 | 0.08 | 0.59 | -0.11 |
| arch:other | 739 | 339 | **0.86** | 0.07 | 0.20 | 1.18 | 0.20 | 0.07 | -0.38 | 0.44 | -1.24 | 1.67 | 1.71 | 0.47 | 0.43 | 0.13 | -0.35 |
| sig:firecracker | 323 | 35 | **1.33** | 0.18 | 1.11 | 2.42 | -0.24 | 0.58 | -0.44 | 0.10 | -1.96 | 2.59 | 1.77 | 0.85 | 0.18 | 0.40 | -0.76 |
| sig:skeletonballoon | 151 | 72 | **1.28** | 0.14 | 0.51 | 2.13 | -0.19 | 0.56 | -0.52 | 0.29 | -2.17 | 2.38 | 1.81 | 0.87 | 0.36 | 0.01 | -1.07 |
| sig:royalrecruits | 92 | 22 | **1.22** | 0.24 | 0.44 | 1.73 | -0.08 | 0.09 | -0.02 | 0.79 | -1.72 | 2.27 | 1.92 | 0.75 | 0.73 | 0.58 | -1.51 |
| sig:megaknight | 310 | 37 | **1.21** | 0.17 | 0.13 | 1.70 | 0.01 | 0.41 | -0.53 | 0.59 | -1.91 | 2.49 | 2.23 | 0.46 | 0.62 | 0.13 | 0.02 |
| sig:hogrider | 281 | 100 | **1.01** | 0.12 | 0.62 | 1.61 | 0.15 | 0.25 | -0.58 | 0.36 | -1.54 | 1.96 | 1.68 | 0.49 | 0.08 | 0.46 | -0.48 |
| sig:golem | 109 | 95 | **1.00** | 0.14 | -0.63 | 0.87 | 0.55 | 0.09 | -0.67 | 1.07 | -1.31 | 1.94 | 1.94 | -0.54 | 0.08 | 0.59 | -0.11 |
| sig:elixirgolem | 154 | 23 | **0.93** | 0.22 | -0.73 | 0.14 | 0.74 | -0.06 | -0.62 | 1.88 | -0.67 | 1.35 | 1.93 | -0.41 | 0.10 | 0.28 | 0.19 |
| sig:minipekka | 341 | 75 | **0.79** | 0.13 | -0.70 | 0.59 | 0.36 | 0.03 | -0.47 | 0.72 | -0.95 | 1.51 | 1.74 | -0.12 | 0.33 | 0.28 | -0.10 |

## 2. Feature means, live vs SIM, per group

### ALL  (live n=1919, SIM n=960, distance 0.97, floor 0.04)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.33 (n 1918) | 5.61 (n 960) | 0.19 |
| ppm_2x | 8.64 (n 1777) | 12.20 (n 935) | 1.28 |
| own_half | 0.349 (n 1914) | 0.374 (n 960) | 0.18 |
| bridge | 0.570 (n 1914) | 0.595 (n 960) | 0.16 |
| our_half | 0.082 (n 1914) | 0.031 (n 960) | -0.46 |
| first_tick | 258.44 (n 1915) | 337.53 (n 960) | 0.65 |
| react_s | 6.16 (n 1919) | 4.75 (n 960) | -1.45 |
| react_3s | 0.263 (n 1919) | 0.480 (n 960) | 1.87 |
| react_lift | -0.05 (n 1919) | 0.09 (n 960) | 1.84 |
| push_mean | 3.41 (n 1919) | 3.74 (n 960) | 0.57 |
| push_max | 9.66 (n 1919) | 10.58 (n 960) | 0.51 |
| spell_share | 0.053 (n 1915) | 0.088 (n 960) | 0.39 |
| opp_el | 7.74 (n 1915) | 7.32 (n 960) | -0.48 |

### arch:royal_giant_monk  (live n=24, SIM n=7, distance 1.87, floor 0.43)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.04 (n 24) | 5.27 (n 7) | 0.32 |
| ppm_2x | 7.08 (n 23) | 11.68 (n 7) | 2.25 |
| own_half | 0.321 (n 24) | 0.426 (n 7) | 0.81 |
| bridge | 0.667 (n 24) | 0.574 (n 7) | -0.76 |
| our_half | 0.011 (n 24) | 0.000 (n 7) | -0.33 |
| first_tick | 249.62 (n 24) | 351.43 (n 7) | 1.23 |
| react_s | 6.36 (n 24) | 4.43 (n 7) | -2.53 |
| react_3s | 0.235 (n 24) | 0.528 (n 7) | 3.66 |
| react_lift | -0.05 (n 24) | 0.13 (n 7) | 3.04 |
| push_mean | 3.15 (n 24) | 3.79 (n 7) | 1.31 |
| push_max | 9.38 (n 24) | 10.43 (n 7) | 0.62 |
| spell_share | 0.000 (n 24) | 0.077 (n 7) | 1.73 |
| opp_el | 8.22 (n 24) | 7.32 (n 7) | -1.87 |

### arch:royal_giant  (live n=55, SIM n=28, distance 1.61, floor 0.23)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.49 (n 55) | 6.62 (n 28) | 0.92 |
| ppm_2x | 8.96 (n 52) | 14.31 (n 28) | 2.03 |
| own_half | 0.317 (n 55) | 0.313 (n 28) | -0.03 |
| bridge | 0.594 (n 55) | 0.647 (n 28) | 0.37 |
| our_half | 0.089 (n 55) | 0.040 (n 28) | -0.38 |
| first_tick | 259.35 (n 55) | 313.57 (n 28) | 0.49 |
| react_s | 6.14 (n 55) | 3.94 (n 28) | -2.19 |
| react_3s | 0.266 (n 55) | 0.592 (n 28) | 2.79 |
| react_lift | -0.06 (n 55) | 0.14 (n 28) | 2.90 |
| push_mean | 3.50 (n 55) | 4.27 (n 28) | 1.56 |
| push_max | 10.09 (n 55) | 11.61 (n 28) | 0.88 |
| spell_share | 0.052 (n 55) | 0.171 (n 28) | 1.40 |
| opp_el | 7.70 (n 55) | 6.55 (n 28) | -1.47 |

### arch:pekka_bridge  (live n=28, SIM n=19, distance 1.40, floor 0.30)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.85 (n 28) | 4.73 (n 19) | -0.15 |
| ppm_2x | 7.61 (n 26) | 11.06 (n 19) | 2.61 |
| own_half | 0.309 (n 28) | 0.330 (n 19) | 0.19 |
| bridge | 0.607 (n 28) | 0.636 (n 19) | 0.21 |
| our_half | 0.084 (n 28) | 0.034 (n 19) | -0.53 |
| first_tick | 259.82 (n 28) | 302.63 (n 19) | 0.55 |
| react_s | 6.40 (n 28) | 5.03 (n 19) | -2.16 |
| react_3s | 0.224 (n 28) | 0.439 (n 19) | 2.55 |
| react_lift | -0.07 (n 28) | 0.07 (n 19) | 1.75 |
| push_mean | 3.28 (n 28) | 3.90 (n 19) | 1.29 |
| push_max | 10.07 (n 28) | 11.00 (n 19) | 0.53 |
| spell_share | 0.000 (n 28) | 0.000 (n 19) | - |
| opp_el | 8.08 (n 28) | 8.16 (n 19) | 0.13 |

### arch:weak_other  (live n=838, SIM n=375, distance 1.21, floor 0.06)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.04 (n 838) | 5.51 (n 375) | 0.38 |
| ppm_2x | 8.22 (n 772) | 12.06 (n 368) | 1.69 |
| own_half | 0.334 (n 838) | 0.353 (n 375) | 0.13 |
| bridge | 0.571 (n 838) | 0.619 (n 375) | 0.30 |
| our_half | 0.095 (n 838) | 0.028 (n 375) | -0.58 |
| first_tick | 256.66 (n 838) | 350.59 (n 375) | 0.82 |
| react_s | 6.32 (n 838) | 4.68 (n 375) | -1.85 |
| react_3s | 0.244 (n 838) | 0.484 (n 375) | 2.34 |
| react_lift | -0.06 (n 838) | 0.09 (n 375) | 2.01 |
| push_mean | 3.47 (n 838) | 3.91 (n 375) | 0.78 |
| push_max | 9.86 (n 838) | 11.00 (n 375) | 0.63 |
| spell_share | 0.045 (n 838) | 0.114 (n 375) | 0.80 |
| opp_el | 7.92 (n 838) | 7.43 (n 375) | -0.62 |

### arch:lava_hound  (live n=37, SIM n=38, distance 1.18, floor 0.23)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.80 (n 37) | 4.44 (n 38) | -0.44 |
| ppm_2x | 7.07 (n 31) | 9.13 (n 36) | 1.31 |
| own_half | 0.348 (n 37) | 0.408 (n 38) | 0.41 |
| bridge | 0.518 (n 37) | 0.565 (n 38) | 0.30 |
| our_half | 0.134 (n 37) | 0.027 (n 38) | -1.06 |
| first_tick | 275.03 (n 37) | 359.74 (n 38) | 0.65 |
| react_s | 6.81 (n 37) | 5.54 (n 38) | -1.55 |
| react_3s | 0.195 (n 37) | 0.391 (n 38) | 2.35 |
| react_lift | -0.08 (n 37) | 0.08 (n 38) | 2.31 |
| push_mean | 3.12 (n 37) | 3.36 (n 38) | 0.49 |
| push_max | 8.68 (n 37) | 10.42 (n 38) | 0.95 |
| spell_share | 0.007 (n 37) | 0.004 (n 38) | -0.12 |
| opp_el | 7.90 (n 37) | 7.95 (n 38) | 0.06 |

### arch:hyperbait  (live n=89, SIM n=59, distance 1.18, floor 0.17)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.09 (n 89) | 6.83 (n 59) | 0.68 |
| ppm_2x | 9.69 (n 87) | 14.28 (n 59) | 2.05 |
| own_half | 0.387 (n 89) | 0.320 (n 59) | -0.46 |
| bridge | 0.549 (n 89) | 0.595 (n 59) | 0.28 |
| our_half | 0.064 (n 89) | 0.085 (n 59) | 0.24 |
| first_tick | 245.47 (n 89) | 239.15 (n 59) | -0.08 |
| react_s | 5.34 (n 89) | 3.97 (n 59) | -1.80 |
| react_3s | 0.363 (n 89) | 0.574 (n 59) | 2.07 |
| react_lift | 0.02 (n 89) | 0.12 (n 59) | 1.23 |
| push_mean | 3.33 (n 89) | 3.99 (n 59) | 1.46 |
| push_max | 9.45 (n 89) | 10.49 (n 59) | 0.70 |
| spell_share | 0.138 (n 89) | 0.078 (n 59) | -0.82 |
| opp_el | 7.44 (n 89) | 6.71 (n 59) | -0.88 |

### arch:golem  (live n=109, SIM n=95, distance 1.00, floor 0.14)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.58 (n 109) | 4.08 (n 95) | -0.63 |
| ppm_2x | 7.97 (n 92) | 9.31 (n 88) | 0.87 |
| own_half | 0.378 (n 109) | 0.443 (n 95) | 0.55 |
| bridge | 0.512 (n 109) | 0.523 (n 95) | 0.09 |
| our_half | 0.110 (n 109) | 0.034 (n 95) | -0.67 |
| first_tick | 262.86 (n 109) | 426.84 (n 95) | 1.07 |
| react_s | 6.49 (n 109) | 5.54 (n 95) | -1.31 |
| react_3s | 0.207 (n 109) | 0.370 (n 95) | 1.94 |
| react_lift | -0.07 (n 109) | 0.08 (n 95) | 1.94 |
| push_mean | 3.51 (n 109) | 3.23 (n 95) | -0.54 |
| push_max | 9.70 (n 109) | 9.84 (n 95) | 0.08 |
| spell_share | 0.018 (n 109) | 0.063 (n 95) | 0.59 |
| opp_el | 7.32 (n 109) | 7.22 (n 95) | -0.11 |

### arch:other  (live n=739, SIM n=339, distance 0.86, floor 0.07)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.71 (n 738) | 6.05 (n 339) | 0.20 |
| ppm_2x | 9.20 (n 694) | 12.98 (n 330) | 1.18 |
| own_half | 0.361 (n 734) | 0.390 (n 339) | 0.20 |
| bridge | 0.575 (n 734) | 0.586 (n 339) | 0.07 |
| our_half | 0.063 (n 734) | 0.025 (n 339) | -0.38 |
| first_tick | 260.73 (n 735) | 316.34 (n 339) | 0.44 |
| react_s | 5.99 (n 739) | 4.71 (n 339) | -1.24 |
| react_3s | 0.287 (n 739) | 0.493 (n 339) | 1.67 |
| react_lift | -0.04 (n 739) | 0.09 (n 339) | 1.71 |
| push_mean | 3.35 (n 739) | 3.63 (n 339) | 0.47 |
| push_max | 9.47 (n 739) | 10.24 (n 339) | 0.43 |
| spell_share | 0.065 (n 735) | 0.077 (n 339) | 0.13 |
| opp_el | 7.58 (n 735) | 7.27 (n 339) | -0.35 |

### sig:firecracker  (live n=323, SIM n=35, distance 1.33, floor 0.18)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.36 (n 323) | 6.78 (n 35) | 1.11 |
| ppm_2x | 8.79 (n 300) | 14.61 (n 35) | 2.42 |
| own_half | 0.349 (n 322) | 0.313 (n 35) | -0.24 |
| bridge | 0.577 (n 322) | 0.666 (n 35) | 0.58 |
| our_half | 0.074 (n 322) | 0.020 (n 35) | -0.44 |
| first_tick | 255.97 (n 323) | 267.14 (n 35) | 0.10 |
| react_s | 6.05 (n 323) | 4.29 (n 35) | -1.96 |
| react_3s | 0.271 (n 323) | 0.541 (n 35) | 2.59 |
| react_lift | -0.05 (n 323) | 0.08 (n 35) | 1.77 |
| push_mean | 3.46 (n 323) | 3.94 (n 35) | 0.85 |
| push_max | 10.08 (n 323) | 10.40 (n 35) | 0.18 |
| spell_share | 0.031 (n 323) | 0.058 (n 35) | 0.40 |
| opp_el | 7.67 (n 323) | 7.04 (n 35) | -0.76 |

### sig:skeletonballoon  (live n=151, SIM n=72, distance 1.28, floor 0.14)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.10 (n 151) | 6.72 (n 72) | 0.51 |
| ppm_2x | 9.45 (n 141) | 13.94 (n 68) | 2.13 |
| own_half | 0.305 (n 151) | 0.281 (n 72) | -0.19 |
| bridge | 0.615 (n 151) | 0.691 (n 72) | 0.56 |
| our_half | 0.080 (n 151) | 0.028 (n 72) | -0.52 |
| first_tick | 238.01 (n 151) | 258.33 (n 72) | 0.29 |
| react_s | 5.88 (n 151) | 4.16 (n 72) | -2.17 |
| react_3s | 0.293 (n 151) | 0.544 (n 72) | 2.38 |
| react_lift | -0.06 (n 151) | 0.10 (n 72) | 1.81 |
| push_mean | 3.45 (n 151) | 3.91 (n 72) | 0.87 |
| push_max | 9.70 (n 151) | 10.32 (n 72) | 0.36 |
| spell_share | 0.042 (n 151) | 0.043 (n 72) | 0.01 |
| opp_el | 7.81 (n 151) | 7.07 (n 72) | -1.07 |

### sig:royalrecruits  (live n=92, SIM n=22, distance 1.22, floor 0.24)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.49 (n 92) | 5.00 (n 22) | 0.44 |
| ppm_2x | 7.30 (n 86) | 10.67 (n 21) | 1.73 |
| own_half | 0.342 (n 92) | 0.331 (n 22) | -0.08 |
| bridge | 0.579 (n 92) | 0.593 (n 22) | 0.09 |
| our_half | 0.079 (n 92) | 0.077 (n 22) | -0.02 |
| first_tick | 260.77 (n 92) | 340.00 (n 22) | 0.79 |
| react_s | 6.73 (n 92) | 5.10 (n 22) | -1.72 |
| react_3s | 0.208 (n 92) | 0.431 (n 22) | 2.27 |
| react_lift | -0.07 (n 92) | 0.07 (n 22) | 1.92 |
| push_mean | 3.54 (n 92) | 3.83 (n 22) | 0.75 |
| push_max | 9.76 (n 92) | 11.05 (n 22) | 0.73 |
| spell_share | 0.048 (n 92) | 0.091 (n 22) | 0.58 |
| opp_el | 8.19 (n 92) | 7.12 (n 22) | -1.51 |

### sig:megaknight  (live n=310, SIM n=37, distance 1.21, floor 0.17)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.72 (n 310) | 4.86 (n 37) | 0.13 |
| ppm_2x | 7.79 (n 288) | 10.80 (n 36) | 1.70 |
| own_half | 0.338 (n 310) | 0.339 (n 37) | 0.01 |
| bridge | 0.559 (n 310) | 0.627 (n 37) | 0.41 |
| our_half | 0.104 (n 310) | 0.034 (n 37) | -0.53 |
| first_tick | 269.24 (n 310) | 340.27 (n 37) | 0.59 |
| react_s | 6.48 (n 310) | 4.84 (n 37) | -1.91 |
| react_3s | 0.228 (n 310) | 0.464 (n 37) | 2.49 |
| react_lift | -0.06 (n 310) | 0.10 (n 37) | 2.23 |
| push_mean | 3.48 (n 310) | 3.73 (n 37) | 0.46 |
| push_max | 10.28 (n 310) | 11.41 (n 37) | 0.62 |
| spell_share | 0.029 (n 310) | 0.038 (n 37) | 0.13 |
| opp_el | 7.94 (n 310) | 7.95 (n 37) | 0.02 |

### sig:hogrider  (live n=281, SIM n=100, distance 1.01, floor 0.12)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.48 (n 281) | 6.45 (n 100) | 0.62 |
| ppm_2x | 8.96 (n 268) | 13.41 (n 100) | 1.61 |
| own_half | 0.336 (n 280) | 0.356 (n 100) | 0.15 |
| bridge | 0.605 (n 280) | 0.639 (n 100) | 0.25 |
| our_half | 0.059 (n 280) | 0.005 (n 100) | -0.58 |
| first_tick | 259.35 (n 281) | 304.00 (n 100) | 0.36 |
| react_s | 6.13 (n 281) | 4.65 (n 100) | -1.54 |
| react_3s | 0.271 (n 281) | 0.493 (n 100) | 1.96 |
| react_lift | -0.05 (n 281) | 0.06 (n 100) | 1.68 |
| push_mean | 3.49 (n 281) | 3.77 (n 100) | 0.49 |
| push_max | 10.07 (n 281) | 10.21 (n 100) | 0.08 |
| spell_share | 0.024 (n 281) | 0.055 (n 100) | 0.46 |
| opp_el | 7.74 (n 281) | 7.32 (n 100) | -0.48 |

### sig:golem  (live n=109, SIM n=95, distance 1.00, floor 0.14)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.58 (n 109) | 4.08 (n 95) | -0.63 |
| ppm_2x | 7.97 (n 92) | 9.31 (n 88) | 0.87 |
| own_half | 0.378 (n 109) | 0.443 (n 95) | 0.55 |
| bridge | 0.512 (n 109) | 0.523 (n 95) | 0.09 |
| our_half | 0.110 (n 109) | 0.034 (n 95) | -0.67 |
| first_tick | 262.86 (n 109) | 426.84 (n 95) | 1.07 |
| react_s | 6.49 (n 109) | 5.54 (n 95) | -1.31 |
| react_3s | 0.207 (n 109) | 0.370 (n 95) | 1.94 |
| react_lift | -0.07 (n 109) | 0.08 (n 95) | 1.94 |
| push_mean | 3.51 (n 109) | 3.23 (n 95) | -0.54 |
| push_max | 9.70 (n 109) | 9.84 (n 95) | 0.08 |
| spell_share | 0.018 (n 109) | 0.063 (n 95) | 0.59 |
| opp_el | 7.32 (n 109) | 7.22 (n 95) | -0.11 |

### sig:elixirgolem  (live n=154, SIM n=23, distance 0.93, floor 0.22)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.33 (n 154) | 4.52 (n 23) | -0.73 |
| ppm_2x | 8.47 (n 130) | 8.71 (n 22) | 0.14 |
| own_half | 0.315 (n 154) | 0.419 (n 23) | 0.74 |
| bridge | 0.560 (n 154) | 0.550 (n 23) | -0.06 |
| our_half | 0.125 (n 154) | 0.031 (n 23) | -0.62 |
| first_tick | 263.47 (n 154) | 443.04 (n 23) | 1.88 |
| react_s | 6.21 (n 154) | 5.66 (n 23) | -0.67 |
| react_3s | 0.252 (n 154) | 0.373 (n 23) | 1.35 |
| react_lift | -0.06 (n 154) | 0.07 (n 23) | 1.93 |
| push_mean | 3.32 (n 154) | 3.12 (n 23) | -0.41 |
| push_max | 9.27 (n 154) | 9.43 (n 23) | 0.10 |
| spell_share | 0.036 (n 154) | 0.056 (n 23) | 0.28 |
| opp_el | 7.52 (n 154) | 7.69 (n 23) | 0.19 |

### sig:minipekka  (live n=341, SIM n=75, distance 0.79, floor 0.13)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.07 (n 341) | 4.33 (n 75) | -0.70 |
| ppm_2x | 8.31 (n 304) | 9.54 (n 70) | 0.59 |
| own_half | 0.314 (n 341) | 0.370 (n 75) | 0.36 |
| bridge | 0.588 (n 341) | 0.592 (n 75) | 0.03 |
| our_half | 0.099 (n 341) | 0.038 (n 75) | -0.47 |
| first_tick | 264.70 (n 341) | 367.60 (n 75) | 0.72 |
| react_s | 6.33 (n 341) | 5.50 (n 75) | -0.95 |
| react_3s | 0.243 (n 341) | 0.399 (n 75) | 1.51 |
| react_lift | -0.06 (n 341) | 0.09 (n 75) | 1.74 |
| push_mean | 3.44 (n 341) | 3.37 (n 75) | -0.12 |
| push_max | 9.65 (n 341) | 10.25 (n 75) | 0.33 |
| spell_share | 0.034 (n 341) | 0.055 (n 75) | 0.28 |
| opp_el | 7.63 (n 341) | 7.55 (n 75) | -0.10 |

## 3. Other SIM opponent policies, ALL archetypes (their deck mixes differ from live; read the distance as a ranking only)

| SIM set | n | distance | floor | ppm_1x | ppm_2x | own_half | bridge | our_half | first_tick | react_s | react_3s | react_lift | push_mean | push_max | spell_share | opp_el |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| E4 opp, T 0.1 (the SIM default; 960 games) | 960 | **0.97** | 0.04 | 0.19 | 1.28 | 0.18 | 0.16 | -0.46 | 0.65 | -1.45 | 1.87 | 1.84 | 0.57 | 0.51 | 0.39 | -0.48 |
| E4 opp, T 0.03 | 480 | **1.02** | 0.05 | 0.10 | 1.36 | 0.18 | 0.15 | -0.42 | 0.88 | -1.40 | 1.96 | 1.97 | 0.52 | 0.52 | 0.41 | -0.48 |
| gen_v1_s0 opp, T 0.3 | 480 | **0.75** | 0.05 | 0.30 | 1.08 | -0.00 | 0.30 | -0.40 | 0.48 | -1.12 | 1.42 | 1.30 | 0.37 | 0.21 | 0.36 | -0.50 |
| rdef r3c opp, T 0.1 | 480 | **0.93** | 0.05 | 0.29 | 1.35 | 0.15 | 0.14 | -0.37 | 0.68 | -1.37 | 1.81 | 1.67 | 0.55 | 0.36 | 0.40 | -0.55 |
| r1 as opp, T 0.03 | 480 | **0.90** | 0.05 | -0.06 | 1.14 | 0.48 | -0.08 | -0.50 | -0.58 | -1.25 | 1.71 | 1.74 | 0.51 | 0.55 | 0.25 | -0.40 |
| r1 as opp, T 0.1 | 480 | **0.91** | 0.05 | 0.02 | 1.15 | 0.44 | -0.03 | -0.50 | -0.74 | -1.24 | 1.72 | 1.72 | 0.53 | 0.60 | 0.30 | -0.44 |

## 4. Detector blind spots, measured on the SIM exact plays (primary SIM)

- exact opponent plays 40825; the detector (live code) finds 33101 = 81.1%
- non-spell plays: 30442/31208 = 97.5% found
- spell plays: 2659/9617 = 27.6% found (23.6% of all SIM plays are spells; live sees only the body-dropping ones)
- SIM opponent elixir at play: true 6.04 (mean, exact) vs the public counter 7.20 (last decision before the play). The counter is a +26-tick forecast and never charges invisible spells, so it reads far above the truth; the known pure bias of the live counter is +0.34 (econ_sim_patch.py). `opp_el` is therefore comparable counter-to-counter (live vs SIM), NOT to true elixir, and it drifts up with every invisible spell the opponent casts (SIM opponents cast many).

