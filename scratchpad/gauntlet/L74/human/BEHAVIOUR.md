# Opponent behaviour: SIM opponents vs real 12k humans

LIVE: 1919 icebow main-account matches since 10-01 (`L74/mix/live_cost_1001.json`), opponent plays reconstructed from reader bodies.  
SIM (primary): `CALIB_gen1_T30`, 480 matches (learner r1 vs the SIM opponent policy).  d = (SIM mean - LIVE mean) / pooled SD, per match; distance = RMS of d over the features that have n >= 5 on both sides; floor = sqrt(1/nL + 1/nS), the distance two draws of the SAME population give by chance (distance <= ~1.5 x floor = indistinguishable).

Features (opponent side, all from the detected plays): `ppm_1x` plays/min before 2:00; `ppm_2x` plays/min in double elixir + overtime; `own_half` / `bridge` / `our_half` share of plays born on their half (y > 19) / within 3 tiles of the river / on our half (y < 13); `first_tick` tick of their first play; `react_s` mean seconds from OUR play to THEIR next play (cap 10 s, none = 10); `react_3s` share of our plays answered within 3 s; `react_lift` = react_3s minus its chance level (a busier opponent answers more often by luck: the share of the match in which a play of theirs starts within the next 3 s); `push_mean` / `push_max` elixir of plays per 8 s window, mean / max over the match; `spell_share` share of VISIBLE plays that are spells (graveyard, barrels, ... ; bodiless spells never appear); `opp_el` the public opponent-elixir counter at the last decision before the play (a +26-tick forecast on both sources).

**Headline (ALL matches, mix-confounded -- read the archetype rows):** largest gaps `react_3s` live 0.26 vs SIM 0.43 (d +1.42); `react_lift` live -0.05 vs SIM 0.05 (d +1.30); `react_s` live 6.16 vs SIM 5.06 (d -1.12); `ppm_2x` live 8.64 vs SIM 11.54 (d +1.08).

## 1. Distance per archetype (primary SIM: CALIB_gen1_T30)

| group | n live | n SIM | distance | floor | ppm_1x | ppm_2x | own_half | bridge | our_half | first_tick | react_s | react_3s | react_lift | push_mean | push_max | spell_share | opp_el |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 1919 | 480 | **0.75** | 0.05 | 0.30 | 1.08 | -0.00 | 0.30 | -0.40 | 0.48 | -1.12 | 1.42 | 1.30 | 0.37 | 0.21 | 0.36 | -0.50 |
| arch:royal_giant (small n) | 55 | 13 | **1.77** | 0.31 | 0.81 | 2.52 | -0.30 | 0.66 | -0.43 | 0.68 | -2.65 | 2.99 | 2.35 | 2.25 | 0.74 | 1.58 | -1.70 |
| arch:hyperbait | 89 | 24 | **1.04** | 0.23 | 0.85 | 1.73 | -0.79 | 0.67 | 0.15 | -0.32 | -1.50 | 1.61 | 0.86 | 1.45 | 0.47 | -0.89 | -0.58 |
| arch:weak_other | 838 | 194 | **0.98** | 0.08 | 0.42 | 1.41 | 0.04 | 0.31 | -0.46 | 0.76 | -1.48 | 1.87 | 1.47 | 0.58 | 0.31 | 0.90 | -0.67 |
| arch:pekka_bridge | 28 | 15 | **0.83** | 0.32 | 0.28 | 1.71 | 0.46 | -0.06 | -0.43 | 0.08 | -1.24 | 1.30 | 0.78 | 0.73 | -0.44 | - | 0.53 |
| arch:lava_hound | 37 | 20 | **0.80** | 0.28 | -0.14 | 1.56 | 0.22 | 0.32 | -0.76 | 0.18 | -1.19 | 1.31 | 1.17 | 0.43 | 0.13 | 0.21 | -0.57 |
| arch:golem | 109 | 46 | **0.73** | 0.18 | 0.42 | 1.21 | 0.10 | 0.35 | -0.50 | 0.35 | -1.01 | 1.39 | 1.27 | -0.19 | -0.08 | 0.47 | -0.09 |
| arch:other | 739 | 166 | **0.67** | 0.09 | 0.30 | 0.94 | -0.01 | 0.30 | -0.41 | 0.43 | -0.90 | 1.29 | 1.33 | 0.09 | 0.18 | 0.02 | -0.44 |
| sig:firecracker (small n) | 323 | 13 | **1.21** | 0.28 | 1.27 | 2.37 | -0.50 | 0.85 | -0.49 | 0.01 | -1.76 | 2.19 | 1.19 | 0.77 | -0.13 | 0.31 | -0.72 |
| sig:royalrecruits (small n) | 92 | 8 | **1.19** | 0.37 | 0.70 | 1.49 | -0.26 | 0.49 | -0.37 | 0.19 | -1.75 | 2.23 | 1.99 | 1.04 | 0.21 | 0.71 | -1.31 |
| sig:skeletonballoon | 151 | 26 | **1.16** | 0.21 | 0.33 | 2.09 | -0.40 | 0.82 | -0.64 | 0.46 | -1.90 | 1.97 | 1.23 | 1.16 | 0.48 | 0.01 | -1.02 |
| sig:hogrider | 281 | 47 | **1.04** | 0.16 | 1.07 | 1.55 | -0.13 | 0.50 | -0.55 | 0.07 | -1.55 | 2.01 | 1.61 | 0.13 | -0.18 | 0.28 | -0.89 |
| sig:megaknight (small n) | 310 | 13 | **0.93** | 0.28 | 0.06 | 1.44 | 0.13 | 0.24 | -0.45 | 0.41 | -1.45 | 1.84 | 1.64 | 0.42 | 0.31 | 0.14 | -0.57 |
| sig:golem | 109 | 46 | **0.73** | 0.18 | 0.42 | 1.21 | 0.10 | 0.35 | -0.50 | 0.35 | -1.01 | 1.39 | 1.27 | -0.19 | -0.08 | 0.47 | -0.09 |
| sig:minipekka | 341 | 43 | **0.47** | 0.16 | -0.15 | 0.36 | 0.23 | 0.20 | -0.53 | 0.42 | -0.52 | 0.89 | 1.00 | -0.12 | 0.04 | 0.22 | -0.13 |
| sig:elixirgolem | 154 | 15 | **0.46** | 0.27 | -0.19 | 0.10 | 0.10 | 0.26 | -0.36 | 0.53 | -0.25 | 0.79 | 1.10 | -0.43 | 0.23 | 0.19 | 0.01 |

Groups with n < 5 on a side (no comparison): arch:royal_giant_monk (live 24, SIM 2)

## 2. Feature means, live vs SIM, per group

### ALL  (live n=1919, SIM n=480, distance 0.75, floor 0.05)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.33 (n 1918) | 5.75 (n 480) | 0.30 |
| ppm_2x | 8.64 (n 1777) | 11.54 (n 464) | 1.08 |
| own_half | 0.349 (n 1914) | 0.349 (n 480) | -0.00 |
| bridge | 0.570 (n 1914) | 0.617 (n 480) | 0.30 |
| our_half | 0.082 (n 1914) | 0.035 (n 480) | -0.40 |
| first_tick | 258.44 (n 1915) | 320.81 (n 480) | 0.48 |
| react_s | 6.16 (n 1919) | 5.06 (n 480) | -1.12 |
| react_3s | 0.263 (n 1919) | 0.426 (n 480) | 1.42 |
| react_lift | -0.05 (n 1919) | 0.05 (n 480) | 1.30 |
| push_mean | 3.41 (n 1919) | 3.62 (n 480) | 0.37 |
| push_max | 9.66 (n 1919) | 10.04 (n 480) | 0.21 |
| spell_share | 0.053 (n 1915) | 0.084 (n 480) | 0.36 |
| opp_el | 7.74 (n 1915) | 7.31 (n 480) | -0.50 |

### arch:royal_giant  (live n=55, SIM n=13, distance 1.77, floor 0.31)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.49 (n 55) | 6.39 (n 13) | 0.81 |
| ppm_2x | 8.96 (n 52) | 14.38 (n 13) | 2.52 |
| own_half | 0.317 (n 55) | 0.275 (n 13) | -0.30 |
| bridge | 0.594 (n 55) | 0.695 (n 13) | 0.66 |
| our_half | 0.089 (n 55) | 0.029 (n 13) | -0.43 |
| first_tick | 259.35 (n 55) | 346.92 (n 13) | 0.68 |
| react_s | 6.14 (n 55) | 3.84 (n 13) | -2.65 |
| react_3s | 0.266 (n 55) | 0.558 (n 13) | 2.99 |
| react_lift | -0.06 (n 55) | 0.08 (n 13) | 2.35 |
| push_mean | 3.50 (n 55) | 4.45 (n 13) | 2.25 |
| push_max | 10.09 (n 55) | 11.38 (n 13) | 0.74 |
| spell_share | 0.052 (n 55) | 0.175 (n 13) | 1.58 |
| opp_el | 7.70 (n 55) | 6.59 (n 13) | -1.70 |

### arch:hyperbait  (live n=89, SIM n=24, distance 1.04, floor 0.23)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.09 (n 89) | 7.03 (n 24) | 0.85 |
| ppm_2x | 9.69 (n 87) | 13.49 (n 24) | 1.73 |
| own_half | 0.387 (n 89) | 0.260 (n 24) | -0.79 |
| bridge | 0.549 (n 89) | 0.663 (n 24) | 0.67 |
| our_half | 0.064 (n 89) | 0.077 (n 24) | 0.15 |
| first_tick | 245.47 (n 89) | 225.42 (n 24) | -0.32 |
| react_s | 5.34 (n 89) | 4.14 (n 24) | -1.50 |
| react_3s | 0.363 (n 89) | 0.535 (n 24) | 1.61 |
| react_lift | 0.02 (n 89) | 0.09 (n 24) | 0.86 |
| push_mean | 3.33 (n 89) | 3.97 (n 24) | 1.45 |
| push_max | 9.45 (n 89) | 10.17 (n 24) | 0.47 |
| spell_share | 0.138 (n 89) | 0.074 (n 24) | -0.89 |
| opp_el | 7.44 (n 89) | 6.92 (n 24) | -0.58 |

### arch:weak_other  (live n=838, SIM n=194, distance 0.98, floor 0.08)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.04 (n 838) | 5.53 (n 194) | 0.42 |
| ppm_2x | 8.22 (n 772) | 11.20 (n 193) | 1.41 |
| own_half | 0.334 (n 838) | 0.340 (n 194) | 0.04 |
| bridge | 0.571 (n 838) | 0.622 (n 194) | 0.31 |
| our_half | 0.095 (n 838) | 0.038 (n 194) | -0.46 |
| first_tick | 256.66 (n 838) | 332.11 (n 194) | 0.76 |
| react_s | 6.32 (n 838) | 5.02 (n 194) | -1.48 |
| react_3s | 0.244 (n 838) | 0.425 (n 194) | 1.87 |
| react_lift | -0.06 (n 838) | 0.05 (n 194) | 1.47 |
| push_mean | 3.47 (n 838) | 3.79 (n 194) | 0.58 |
| push_max | 9.86 (n 838) | 10.42 (n 194) | 0.31 |
| spell_share | 0.045 (n 838) | 0.117 (n 194) | 0.90 |
| opp_el | 7.92 (n 838) | 7.41 (n 194) | -0.67 |

### arch:pekka_bridge  (live n=28, SIM n=15, distance 0.83, floor 0.32)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.85 (n 28) | 5.09 (n 15) | 0.28 |
| ppm_2x | 7.61 (n 26) | 10.22 (n 14) | 1.71 |
| own_half | 0.309 (n 28) | 0.363 (n 15) | 0.46 |
| bridge | 0.607 (n 28) | 0.599 (n 15) | -0.06 |
| our_half | 0.084 (n 28) | 0.038 (n 15) | -0.43 |
| first_tick | 259.82 (n 28) | 265.33 (n 15) | 0.08 |
| react_s | 6.40 (n 28) | 5.61 (n 15) | -1.24 |
| react_3s | 0.224 (n 28) | 0.338 (n 15) | 1.30 |
| react_lift | -0.07 (n 28) | -0.00 (n 15) | 0.78 |
| push_mean | 3.28 (n 28) | 3.58 (n 15) | 0.73 |
| push_max | 10.07 (n 28) | 9.33 (n 15) | -0.44 |
| spell_share | 0.000 (n 28) | 0.000 (n 15) | - |
| opp_el | 8.08 (n 28) | 8.40 (n 15) | 0.53 |

### arch:lava_hound  (live n=37, SIM n=20, distance 0.80, floor 0.28)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.80 (n 37) | 4.69 (n 20) | -0.14 |
| ppm_2x | 7.07 (n 31) | 9.42 (n 17) | 1.56 |
| own_half | 0.348 (n 37) | 0.380 (n 20) | 0.22 |
| bridge | 0.518 (n 37) | 0.570 (n 20) | 0.32 |
| our_half | 0.134 (n 37) | 0.050 (n 20) | -0.76 |
| first_tick | 275.03 (n 37) | 295.50 (n 20) | 0.18 |
| react_s | 6.81 (n 37) | 5.77 (n 20) | -1.19 |
| react_3s | 0.195 (n 37) | 0.329 (n 20) | 1.31 |
| react_lift | -0.08 (n 37) | 0.02 (n 20) | 1.17 |
| push_mean | 3.12 (n 37) | 3.30 (n 20) | 0.43 |
| push_max | 8.68 (n 37) | 8.90 (n 20) | 0.13 |
| spell_share | 0.007 (n 37) | 0.013 (n 20) | 0.21 |
| opp_el | 7.90 (n 37) | 7.52 (n 20) | -0.57 |

### arch:golem  (live n=109, SIM n=46, distance 0.73, floor 0.18)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.58 (n 109) | 4.89 (n 46) | 0.42 |
| ppm_2x | 7.97 (n 92) | 9.54 (n 39) | 1.21 |
| own_half | 0.378 (n 109) | 0.390 (n 46) | 0.10 |
| bridge | 0.512 (n 109) | 0.562 (n 46) | 0.35 |
| our_half | 0.110 (n 109) | 0.047 (n 46) | -0.50 |
| first_tick | 262.86 (n 109) | 308.26 (n 46) | 0.35 |
| react_s | 6.49 (n 109) | 5.72 (n 46) | -1.01 |
| react_3s | 0.207 (n 109) | 0.330 (n 46) | 1.39 |
| react_lift | -0.07 (n 109) | 0.02 (n 46) | 1.27 |
| push_mean | 3.51 (n 109) | 3.43 (n 46) | -0.19 |
| push_max | 9.70 (n 109) | 9.57 (n 46) | -0.08 |
| spell_share | 0.018 (n 109) | 0.045 (n 46) | 0.47 |
| opp_el | 7.32 (n 109) | 7.24 (n 46) | -0.09 |

### arch:other  (live n=739, SIM n=166, distance 0.67, floor 0.09)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.71 (n 738) | 6.22 (n 166) | 0.30 |
| ppm_2x | 9.20 (n 694) | 12.26 (n 162) | 0.94 |
| own_half | 0.361 (n 734) | 0.359 (n 166) | -0.01 |
| bridge | 0.575 (n 734) | 0.621 (n 166) | 0.30 |
| our_half | 0.063 (n 734) | 0.020 (n 166) | -0.41 |
| first_tick | 260.73 (n 735) | 332.41 (n 166) | 0.43 |
| react_s | 5.99 (n 739) | 5.02 (n 166) | -0.90 |
| react_3s | 0.287 (n 739) | 0.447 (n 166) | 1.29 |
| react_lift | -0.04 (n 739) | 0.06 (n 166) | 1.33 |
| push_mean | 3.35 (n 739) | 3.41 (n 166) | 0.09 |
| push_max | 9.47 (n 739) | 9.80 (n 166) | 0.18 |
| spell_share | 0.065 (n 735) | 0.066 (n 166) | 0.02 |
| opp_el | 7.58 (n 735) | 7.19 (n 166) | -0.44 |

### sig:firecracker  (live n=323, SIM n=13, distance 1.21, floor 0.28)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.36 (n 323) | 6.87 (n 13) | 1.27 |
| ppm_2x | 8.79 (n 300) | 14.09 (n 13) | 2.37 |
| own_half | 0.349 (n 322) | 0.276 (n 13) | -0.50 |
| bridge | 0.577 (n 322) | 0.711 (n 13) | 0.85 |
| our_half | 0.074 (n 322) | 0.014 (n 13) | -0.49 |
| first_tick | 255.97 (n 323) | 256.92 (n 13) | 0.01 |
| react_s | 6.05 (n 323) | 4.46 (n 13) | -1.76 |
| react_3s | 0.271 (n 323) | 0.500 (n 13) | 2.19 |
| react_lift | -0.05 (n 323) | 0.04 (n 13) | 1.19 |
| push_mean | 3.46 (n 323) | 3.90 (n 13) | 0.77 |
| push_max | 10.08 (n 323) | 9.85 (n 13) | -0.13 |
| spell_share | 0.031 (n 323) | 0.051 (n 13) | 0.31 |
| opp_el | 7.67 (n 323) | 7.08 (n 13) | -0.72 |

### sig:royalrecruits  (live n=92, SIM n=8, distance 1.19, floor 0.37)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.49 (n 92) | 5.26 (n 8) | 0.70 |
| ppm_2x | 7.30 (n 86) | 10.05 (n 8) | 1.49 |
| own_half | 0.342 (n 92) | 0.307 (n 8) | -0.26 |
| bridge | 0.579 (n 92) | 0.655 (n 8) | 0.49 |
| our_half | 0.079 (n 92) | 0.038 (n 8) | -0.37 |
| first_tick | 260.77 (n 92) | 275.00 (n 8) | 0.19 |
| react_s | 6.73 (n 92) | 5.09 (n 8) | -1.75 |
| react_3s | 0.208 (n 92) | 0.419 (n 8) | 2.23 |
| react_lift | -0.07 (n 92) | 0.06 (n 8) | 1.99 |
| push_mean | 3.54 (n 92) | 3.96 (n 8) | 1.04 |
| push_max | 9.76 (n 92) | 10.12 (n 8) | 0.21 |
| spell_share | 0.048 (n 92) | 0.098 (n 8) | 0.71 |
| opp_el | 8.19 (n 92) | 7.29 (n 8) | -1.31 |

### sig:skeletonballoon  (live n=151, SIM n=26, distance 1.16, floor 0.21)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.10 (n 151) | 6.49 (n 26) | 0.33 |
| ppm_2x | 9.45 (n 141) | 13.74 (n 26) | 2.09 |
| own_half | 0.305 (n 151) | 0.253 (n 26) | -0.40 |
| bridge | 0.615 (n 151) | 0.733 (n 26) | 0.82 |
| our_half | 0.080 (n 151) | 0.014 (n 26) | -0.64 |
| first_tick | 238.01 (n 151) | 273.85 (n 26) | 0.46 |
| react_s | 5.88 (n 151) | 4.34 (n 26) | -1.90 |
| react_3s | 0.293 (n 151) | 0.491 (n 26) | 1.97 |
| react_lift | -0.06 (n 151) | 0.04 (n 26) | 1.23 |
| push_mean | 3.45 (n 151) | 4.07 (n 26) | 1.16 |
| push_max | 9.70 (n 151) | 10.54 (n 26) | 0.48 |
| spell_share | 0.042 (n 151) | 0.043 (n 26) | 0.01 |
| opp_el | 7.81 (n 151) | 7.13 (n 26) | -1.02 |

### sig:hogrider  (live n=281, SIM n=47, distance 1.04, floor 0.16)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.48 (n 281) | 6.97 (n 47) | 1.07 |
| ppm_2x | 8.96 (n 268) | 13.10 (n 47) | 1.55 |
| own_half | 0.336 (n 280) | 0.318 (n 47) | -0.13 |
| bridge | 0.605 (n 280) | 0.677 (n 47) | 0.50 |
| our_half | 0.059 (n 280) | 0.005 (n 47) | -0.55 |
| first_tick | 259.35 (n 281) | 267.02 (n 47) | 0.07 |
| react_s | 6.13 (n 281) | 4.72 (n 47) | -1.55 |
| react_3s | 0.271 (n 281) | 0.486 (n 47) | 2.01 |
| react_lift | -0.05 (n 281) | 0.06 (n 47) | 1.61 |
| push_mean | 3.49 (n 281) | 3.56 (n 47) | 0.13 |
| push_max | 10.07 (n 281) | 9.77 (n 47) | -0.18 |
| spell_share | 0.024 (n 281) | 0.041 (n 47) | 0.28 |
| opp_el | 7.74 (n 281) | 6.99 (n 47) | -0.89 |

### sig:megaknight  (live n=310, SIM n=13, distance 0.93, floor 0.28)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.72 (n 310) | 4.78 (n 13) | 0.06 |
| ppm_2x | 7.79 (n 288) | 10.32 (n 12) | 1.44 |
| own_half | 0.338 (n 310) | 0.357 (n 13) | 0.13 |
| bridge | 0.559 (n 310) | 0.599 (n 13) | 0.24 |
| our_half | 0.104 (n 310) | 0.043 (n 13) | -0.45 |
| first_tick | 269.24 (n 310) | 314.62 (n 13) | 0.41 |
| react_s | 6.48 (n 310) | 5.24 (n 13) | -1.45 |
| react_3s | 0.228 (n 310) | 0.400 (n 13) | 1.84 |
| react_lift | -0.06 (n 310) | 0.06 (n 13) | 1.64 |
| push_mean | 3.48 (n 310) | 3.70 (n 13) | 0.42 |
| push_max | 10.28 (n 310) | 10.85 (n 13) | 0.31 |
| spell_share | 0.029 (n 310) | 0.038 (n 13) | 0.14 |
| opp_el | 7.94 (n 310) | 7.49 (n 13) | -0.57 |

### sig:golem  (live n=109, SIM n=46, distance 0.73, floor 0.18)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.58 (n 109) | 4.89 (n 46) | 0.42 |
| ppm_2x | 7.97 (n 92) | 9.54 (n 39) | 1.21 |
| own_half | 0.378 (n 109) | 0.390 (n 46) | 0.10 |
| bridge | 0.512 (n 109) | 0.562 (n 46) | 0.35 |
| our_half | 0.110 (n 109) | 0.047 (n 46) | -0.50 |
| first_tick | 262.86 (n 109) | 308.26 (n 46) | 0.35 |
| react_s | 6.49 (n 109) | 5.72 (n 46) | -1.01 |
| react_3s | 0.207 (n 109) | 0.330 (n 46) | 1.39 |
| react_lift | -0.07 (n 109) | 0.02 (n 46) | 1.27 |
| push_mean | 3.51 (n 109) | 3.43 (n 46) | -0.19 |
| push_max | 9.70 (n 109) | 9.57 (n 46) | -0.08 |
| spell_share | 0.018 (n 109) | 0.045 (n 46) | 0.47 |
| opp_el | 7.32 (n 109) | 7.24 (n 46) | -0.09 |

### sig:minipekka  (live n=341, SIM n=43, distance 0.47, floor 0.16)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.07 (n 341) | 4.92 (n 43) | -0.15 |
| ppm_2x | 8.31 (n 304) | 9.06 (n 40) | 0.36 |
| own_half | 0.314 (n 341) | 0.349 (n 43) | 0.23 |
| bridge | 0.588 (n 341) | 0.622 (n 43) | 0.20 |
| our_half | 0.099 (n 341) | 0.029 (n 43) | -0.53 |
| first_tick | 264.70 (n 341) | 320.00 (n 43) | 0.42 |
| react_s | 6.33 (n 341) | 5.88 (n 43) | -0.52 |
| react_3s | 0.243 (n 341) | 0.332 (n 43) | 0.89 |
| react_lift | -0.06 (n 341) | 0.02 (n 43) | 1.00 |
| push_mean | 3.44 (n 341) | 3.37 (n 43) | -0.12 |
| push_max | 9.65 (n 341) | 9.72 (n 43) | 0.04 |
| spell_share | 0.034 (n 341) | 0.050 (n 43) | 0.22 |
| opp_el | 7.63 (n 341) | 7.52 (n 43) | -0.13 |

### sig:elixirgolem  (live n=154, SIM n=15, distance 0.46, floor 0.27)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.33 (n 154) | 5.13 (n 15) | -0.19 |
| ppm_2x | 8.47 (n 130) | 8.65 (n 14) | 0.10 |
| own_half | 0.315 (n 154) | 0.329 (n 15) | 0.10 |
| bridge | 0.560 (n 154) | 0.602 (n 15) | 0.26 |
| our_half | 0.125 (n 154) | 0.069 (n 15) | -0.36 |
| first_tick | 263.47 (n 154) | 305.33 (n 15) | 0.53 |
| react_s | 6.21 (n 154) | 6.00 (n 15) | -0.25 |
| react_3s | 0.252 (n 154) | 0.325 (n 15) | 0.79 |
| react_lift | -0.06 (n 154) | 0.01 (n 15) | 1.10 |
| push_mean | 3.32 (n 154) | 3.12 (n 15) | -0.43 |
| push_max | 9.27 (n 154) | 9.67 (n 15) | 0.23 |
| spell_share | 0.036 (n 154) | 0.049 (n 15) | 0.19 |
| opp_el | 7.52 (n 154) | 7.53 (n 15) | 0.01 |

## 3. Other SIM opponent policies, ALL archetypes (their deck mixes differ from live; read the distance as a ranking only)

| SIM set | n | distance | floor | ppm_1x | ppm_2x | own_half | bridge | our_half | first_tick | react_s | react_3s | react_lift | push_mean | push_max | spell_share | opp_el |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gen_v1_s0 opp, T 0.3 | 480 | **0.75** | 0.05 | 0.30 | 1.08 | -0.00 | 0.30 | -0.40 | 0.48 | -1.12 | 1.42 | 1.30 | 0.37 | 0.21 | 0.36 | -0.50 |
| T_e4_d10_r0 | 960 | **0.97** | 0.04 | -0.14 | 1.07 | 0.23 | 0.11 | -0.44 | 1.00 | -1.39 | 1.78 | 1.92 | 0.58 | 0.67 | 0.17 | -0.48 |
| T_gen3_d20_r20 | 960 | **0.54** | 0.04 | -0.19 | 0.60 | 0.07 | 0.23 | -0.42 | 0.92 | -0.91 | 0.83 | 0.76 | -0.06 | -0.07 | 0.08 | 0.36 |
| T_e4_d20_r20 | 960 | **0.70** | 0.04 | -0.43 | 0.80 | 0.34 | 0.00 | -0.46 | 1.21 | -1.17 | 1.03 | 0.97 | 0.10 | 0.26 | 0.13 | 0.52 |
| S_v32_d10_r0 | 960 | **0.93** | 0.04 | 0.17 | 1.16 | -0.30 | 0.58 | -0.41 | 0.59 | -1.42 | 1.72 | 1.62 | 0.65 | 0.27 | 0.15 | -0.83 |
| S_v32_d20_r20 | 960 | **0.69** | 0.04 | -0.04 | 0.96 | -0.23 | 0.50 | -0.40 | 0.83 | -1.31 | 1.17 | 0.91 | 0.34 | 0.16 | 0.10 | -0.07 |
| T_gen3_d20_r0 | 960 | **0.63** | 0.04 | -0.12 | 0.70 | 0.04 | 0.28 | -0.46 | 0.78 | -0.96 | 1.12 | 1.20 | 0.19 | 0.30 | 0.10 | -0.17 |
| T_gen3_d30_r0 | 960 | **0.63** | 0.04 | -0.20 | 0.63 | 0.04 | 0.27 | -0.44 | 0.89 | -0.91 | 1.07 | 1.25 | 0.08 | 0.36 | 0.10 | -0.15 |
| T_gen3_d30_r20 | 960 | **0.55** | 0.04 | -0.31 | 0.47 | 0.12 | 0.21 | -0.44 | 1.02 | -0.80 | 0.78 | 0.83 | -0.18 | -0.06 | 0.08 | 0.61 |
| T_e4_d20_r0 | 960 | **0.88** | 0.04 | -0.27 | 1.03 | 0.28 | 0.06 | -0.44 | 1.09 | -1.42 | 1.52 | 1.58 | 0.51 | 0.58 | 0.15 | -0.21 |
| T_e4_d30_r0 | 960 | **0.87** | 0.04 | -0.38 | 0.96 | 0.31 | 0.04 | -0.44 | 1.18 | -1.30 | 1.44 | 1.57 | 0.39 | 0.75 | 0.15 | -0.20 |
| T_e4_d30_r20 | 960 | **0.73** | 0.04 | -0.51 | 0.71 | 0.40 | -0.04 | -0.48 | 1.30 | -1.13 | 1.07 | 1.08 | 0.07 | 0.20 | 0.10 | 0.69 |

## 4. Detector blind spots, measured on the SIM exact plays (primary SIM)

- exact opponent plays 18053; the detector (live code) finds 14788 = 81.9%
- non-spell plays: 13666/13967 = 97.8% found
- spell plays: 1122/4086 = 27.5% found (22.6% of all SIM plays are spells; live sees only the body-dropping ones)
- SIM opponent elixir at play: true 6.15 (mean, exact) vs the public counter 7.20 (last decision before the play). The counter is a +26-tick forecast and never charges invisible spells, so it reads far above the truth; the known pure bias of the live counter is +0.34 (econ_sim_patch.py). `opp_el` is therefore comparable counter-to-counter (live vs SIM), NOT to true elixir, and it drifts up with every invisible spell the opponent casts (SIM opponents cast many).

