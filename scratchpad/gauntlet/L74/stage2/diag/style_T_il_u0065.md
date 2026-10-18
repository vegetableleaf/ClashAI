# Opponent behaviour: SIM opponents vs real 12k humans

LIVE: 1919 icebow main-account matches since 10-01 (`L74/mix/live_cost_1001.json`), opponent plays reconstructed from reader bodies.  
SIM (primary): `T_il_u0065`, 960 matches (learner r1 vs the SIM opponent policy).  d = (SIM mean - LIVE mean) / pooled SD, per match; distance = RMS of d over the features that have n >= 5 on both sides; floor = sqrt(1/nL + 1/nS), the distance two draws of the SAME population give by chance (distance <= ~1.5 x floor = indistinguishable).

Features (opponent side, all from the detected plays): `ppm_1x` plays/min before 2:00; `ppm_2x` plays/min in double elixir + overtime; `own_half` / `bridge` / `our_half` share of plays born on their half (y > 19) / within 3 tiles of the river / on our half (y < 13); `first_tick` tick of their first play; `react_s` mean seconds from OUR play to THEIR next play (cap 10 s, none = 10); `react_3s` share of our plays answered within 3 s; `react_lift` = react_3s minus its chance level (a busier opponent answers more often by luck: the share of the match in which a play of theirs starts within the next 3 s); `push_mean` / `push_max` elixir of plays per 8 s window, mean / max over the match; `spell_share` share of VISIBLE plays that are spells (graveyard, barrels, ... ; bodiless spells never appear); `opp_el` the public opponent-elixir counter at the last decision before the play (a +26-tick forecast on both sources).

**Headline (ALL matches, mix-confounded -- read the archetype rows):** largest gaps `react_lift` live -0.05 vs SIM 0.10 (d +1.86); `react_3s` live 0.26 vs SIM 0.47 (d +1.81); `react_s` live 6.16 vs SIM 4.83 (d -1.39); `ppm_2x` live 8.64 vs SIM 11.56 (d +1.03).

## 1. Distance per archetype (primary SIM: T_il_u0065)

| group | n live | n SIM | distance | floor | ppm_1x | ppm_2x | own_half | bridge | our_half | first_tick | react_s | react_3s | react_lift | push_mean | push_max | spell_share | opp_el |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 1919 | 960 | **0.98** | 0.04 | -0.12 | 1.03 | -0.35 | 0.72 | -0.55 | 0.93 | -1.39 | 1.81 | 1.86 | 0.45 | 0.56 | 0.00 | -0.68 |
| arch:hyperbait | 89 | 26 | **1.14** | 0.22 | -0.86 | 1.27 | -0.74 | 0.52 | 0.42 | 2.17 | -0.98 | 1.39 | 1.28 | 1.18 | 1.24 | -0.93 | -0.63 |
| arch:weak_other | 838 | 520 | **1.02** | 0.06 | -0.28 | 0.98 | -0.28 | 0.72 | -0.64 | 0.91 | -1.46 | 1.89 | 1.95 | 0.37 | 0.54 | 0.10 | -0.81 |
| arch:other | 739 | 414 | **0.97** | 0.06 | -0.01 | 1.10 | -0.40 | 0.71 | -0.49 | 0.85 | -1.38 | 1.82 | 1.82 | 0.45 | 0.53 | -0.12 | -0.65 |
| sig:skeletonballoon (small n) | 151 | 6 | **1.40** | 0.42 | -0.46 | 1.21 | -0.59 | 1.07 | -0.73 | 0.94 | -1.83 | 2.38 | 2.36 | 1.02 | 1.48 | -0.64 | -1.61 |
| sig:royalrecruits | 92 | 104 | **1.31** | 0.14 | 0.34 | 1.67 | -0.51 | 0.83 | -0.56 | 0.61 | -1.93 | 2.22 | 1.86 | 0.68 | 0.68 | 1.07 | -1.87 |
| sig:firecracker | 323 | 264 | **1.15** | 0.08 | 0.16 | 1.47 | -0.31 | 0.65 | -0.48 | 0.74 | -1.85 | 2.24 | 1.96 | 0.68 | 0.38 | 0.24 | -0.84 |
| sig:megaknight | 310 | 252 | **1.11** | 0.08 | -0.25 | 0.94 | -0.35 | 0.88 | -0.75 | 0.95 | -1.71 | 2.09 | 2.08 | 0.20 | 0.37 | -0.13 | -0.87 |
| sig:minipekka | 341 | 202 | **1.05** | 0.09 | -0.49 | 0.73 | -0.16 | 0.60 | -0.61 | 1.03 | -1.52 | 2.03 | 2.12 | 0.18 | 0.64 | -0.03 | -0.51 |
| sig:hogrider | 281 | 746 | **0.93** | 0.07 | -0.22 | 0.79 | -0.29 | 0.57 | -0.48 | 0.72 | -1.42 | 1.69 | 1.94 | 0.26 | 0.35 | 0.29 | -0.63 |

Groups with n < 5 on a side (no comparison): sig:elixirgolem (live 154, SIM 0), arch:golem (live 109, SIM 0), sig:golem (live 109, SIM 0), arch:royal_giant (live 55, SIM 0), arch:royal_giant_monk (live 24, SIM 0), arch:pekka_bridge (live 28, SIM 0), arch:lava_hound (live 37, SIM 0)

## 2. Feature means, live vs SIM, per group

### ALL  (live n=1919, SIM n=960, distance 0.98, floor 0.04)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.33 (n 1918) | 5.16 (n 960) | -0.12 |
| ppm_2x | 8.64 (n 1777) | 11.56 (n 946) | 1.03 |
| own_half | 0.349 (n 1914) | 0.302 (n 960) | -0.35 |
| bridge | 0.570 (n 1914) | 0.676 (n 960) | 0.72 |
| our_half | 0.082 (n 1914) | 0.023 (n 960) | -0.55 |
| first_tick | 258.44 (n 1915) | 399.67 (n 960) | 0.93 |
| react_s | 6.16 (n 1919) | 4.83 (n 960) | -1.39 |
| react_3s | 0.263 (n 1919) | 0.470 (n 960) | 1.81 |
| react_lift | -0.05 (n 1919) | 0.10 (n 960) | 1.86 |
| push_mean | 3.41 (n 1919) | 3.69 (n 960) | 0.45 |
| push_max | 9.66 (n 1919) | 10.65 (n 960) | 0.56 |
| spell_share | 0.053 (n 1915) | 0.054 (n 960) | 0.00 |
| opp_el | 7.74 (n 1915) | 7.17 (n 960) | -0.68 |

### arch:hyperbait  (live n=89, SIM n=26, distance 1.14, floor 0.22)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.09 (n 89) | 5.23 (n 26) | -0.86 |
| ppm_2x | 9.69 (n 87) | 12.15 (n 26) | 1.27 |
| own_half | 0.387 (n 89) | 0.268 (n 26) | -0.74 |
| bridge | 0.549 (n 89) | 0.630 (n 26) | 0.52 |
| our_half | 0.064 (n 89) | 0.102 (n 26) | 0.42 |
| first_tick | 245.47 (n 89) | 494.62 (n 26) | 2.17 |
| react_s | 5.34 (n 89) | 4.50 (n 26) | -0.98 |
| react_3s | 0.363 (n 89) | 0.518 (n 26) | 1.39 |
| react_lift | 0.02 (n 89) | 0.14 (n 26) | 1.28 |
| push_mean | 3.33 (n 89) | 3.89 (n 26) | 1.18 |
| push_max | 9.45 (n 89) | 11.38 (n 26) | 1.24 |
| spell_share | 0.138 (n 89) | 0.073 (n 26) | -0.93 |
| opp_el | 7.44 (n 89) | 6.92 (n 26) | -0.63 |

### arch:weak_other  (live n=838, SIM n=520, distance 1.02, floor 0.06)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.04 (n 838) | 4.72 (n 520) | -0.28 |
| ppm_2x | 8.22 (n 772) | 10.53 (n 510) | 0.98 |
| own_half | 0.334 (n 838) | 0.298 (n 520) | -0.28 |
| bridge | 0.571 (n 838) | 0.678 (n 520) | 0.72 |
| our_half | 0.095 (n 838) | 0.024 (n 520) | -0.64 |
| first_tick | 256.66 (n 838) | 398.54 (n 520) | 0.91 |
| react_s | 6.32 (n 838) | 5.03 (n 520) | -1.46 |
| react_3s | 0.244 (n 838) | 0.438 (n 520) | 1.89 |
| react_lift | -0.06 (n 838) | 0.09 (n 520) | 1.95 |
| push_mean | 3.47 (n 838) | 3.71 (n 520) | 0.37 |
| push_max | 9.86 (n 838) | 10.79 (n 520) | 0.54 |
| spell_share | 0.045 (n 838) | 0.052 (n 520) | 0.10 |
| opp_el | 7.92 (n 838) | 7.30 (n 520) | -0.81 |

### arch:other  (live n=739, SIM n=414, distance 0.97, floor 0.06)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.71 (n 738) | 5.70 (n 414) | -0.01 |
| ppm_2x | 9.20 (n 694) | 12.80 (n 410) | 1.10 |
| own_half | 0.361 (n 734) | 0.309 (n 414) | -0.40 |
| bridge | 0.575 (n 734) | 0.675 (n 414) | 0.71 |
| our_half | 0.063 (n 734) | 0.016 (n 414) | -0.49 |
| first_tick | 260.73 (n 735) | 395.12 (n 414) | 0.85 |
| react_s | 5.99 (n 739) | 4.60 (n 414) | -1.38 |
| react_3s | 0.287 (n 739) | 0.508 (n 414) | 1.82 |
| react_lift | -0.04 (n 739) | 0.10 (n 414) | 1.82 |
| push_mean | 3.35 (n 739) | 3.66 (n 414) | 0.45 |
| push_max | 9.47 (n 739) | 10.44 (n 414) | 0.53 |
| spell_share | 0.065 (n 735) | 0.055 (n 414) | -0.12 |
| opp_el | 7.58 (n 735) | 7.02 (n 414) | -0.65 |

### sig:skeletonballoon  (live n=151, SIM n=6, distance 1.40, floor 0.42)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.10 (n 151) | 5.54 (n 6) | -0.46 |
| ppm_2x | 9.45 (n 141) | 11.90 (n 6) | 1.21 |
| own_half | 0.305 (n 151) | 0.224 (n 6) | -0.59 |
| bridge | 0.615 (n 151) | 0.776 (n 6) | 1.07 |
| our_half | 0.080 (n 151) | 0.000 (n 6) | -0.73 |
| first_tick | 238.01 (n 151) | 286.67 (n 6) | 0.94 |
| react_s | 5.88 (n 151) | 4.38 (n 6) | -1.83 |
| react_3s | 0.293 (n 151) | 0.528 (n 6) | 2.38 |
| react_lift | -0.06 (n 151) | 0.13 (n 6) | 2.36 |
| push_mean | 3.45 (n 151) | 4.00 (n 6) | 1.02 |
| push_max | 9.70 (n 151) | 12.33 (n 6) | 1.48 |
| spell_share | 0.042 (n 151) | 0.000 (n 6) | -0.64 |
| opp_el | 7.81 (n 151) | 6.77 (n 6) | -1.61 |

### sig:royalrecruits  (live n=92, SIM n=104, distance 1.31, floor 0.14)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.49 (n 92) | 4.82 (n 104) | 0.34 |
| ppm_2x | 7.30 (n 86) | 10.71 (n 102) | 1.67 |
| own_half | 0.342 (n 92) | 0.286 (n 104) | -0.51 |
| bridge | 0.579 (n 92) | 0.685 (n 104) | 0.83 |
| our_half | 0.079 (n 92) | 0.029 (n 104) | -0.56 |
| first_tick | 260.77 (n 92) | 335.58 (n 104) | 0.61 |
| react_s | 6.73 (n 92) | 5.11 (n 104) | -1.93 |
| react_3s | 0.208 (n 92) | 0.412 (n 104) | 2.22 |
| react_lift | -0.07 (n 92) | 0.06 (n 104) | 1.86 |
| push_mean | 3.54 (n 92) | 3.92 (n 104) | 0.68 |
| push_max | 9.76 (n 92) | 10.92 (n 104) | 0.68 |
| spell_share | 0.048 (n 92) | 0.127 (n 104) | 1.07 |
| opp_el | 8.19 (n 92) | 6.98 (n 104) | -1.87 |

### sig:firecracker  (live n=323, SIM n=264, distance 1.15, floor 0.08)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.36 (n 323) | 5.56 (n 264) | 0.16 |
| ppm_2x | 8.79 (n 300) | 12.69 (n 264) | 1.47 |
| own_half | 0.349 (n 322) | 0.310 (n 264) | -0.31 |
| bridge | 0.577 (n 322) | 0.663 (n 264) | 0.65 |
| our_half | 0.074 (n 322) | 0.027 (n 264) | -0.48 |
| first_tick | 255.97 (n 323) | 369.85 (n 264) | 0.74 |
| react_s | 6.05 (n 323) | 4.45 (n 264) | -1.85 |
| react_3s | 0.271 (n 323) | 0.515 (n 264) | 2.24 |
| react_lift | -0.05 (n 323) | 0.11 (n 264) | 1.96 |
| push_mean | 3.46 (n 323) | 3.88 (n 264) | 0.68 |
| push_max | 10.08 (n 323) | 10.74 (n 264) | 0.38 |
| spell_share | 0.031 (n 323) | 0.048 (n 264) | 0.24 |
| opp_el | 7.67 (n 323) | 7.02 (n 264) | -0.84 |

### sig:megaknight  (live n=310, SIM n=252, distance 1.11, floor 0.08)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.72 (n 310) | 4.44 (n 252) | -0.25 |
| ppm_2x | 7.79 (n 288) | 10.13 (n 248) | 0.94 |
| own_half | 0.338 (n 310) | 0.290 (n 252) | -0.35 |
| bridge | 0.559 (n 310) | 0.687 (n 252) | 0.88 |
| our_half | 0.104 (n 310) | 0.022 (n 252) | -0.75 |
| first_tick | 269.24 (n 310) | 449.05 (n 252) | 0.95 |
| react_s | 6.48 (n 310) | 5.00 (n 252) | -1.71 |
| react_3s | 0.228 (n 310) | 0.444 (n 252) | 2.09 |
| react_lift | -0.06 (n 310) | 0.11 (n 252) | 2.08 |
| push_mean | 3.48 (n 310) | 3.63 (n 252) | 0.20 |
| push_max | 10.28 (n 310) | 10.94 (n 252) | 0.37 |
| spell_share | 0.029 (n 310) | 0.022 (n 252) | -0.13 |
| opp_el | 7.94 (n 310) | 7.26 (n 252) | -0.87 |

### sig:minipekka  (live n=341, SIM n=202, distance 1.05, floor 0.09)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.07 (n 341) | 4.58 (n 202) | -0.49 |
| ppm_2x | 8.31 (n 304) | 10.18 (n 198) | 0.73 |
| own_half | 0.314 (n 341) | 0.292 (n 202) | -0.16 |
| bridge | 0.588 (n 341) | 0.680 (n 202) | 0.60 |
| our_half | 0.099 (n 341) | 0.028 (n 202) | -0.61 |
| first_tick | 264.70 (n 341) | 445.45 (n 202) | 1.03 |
| react_s | 6.33 (n 341) | 4.99 (n 202) | -1.52 |
| react_3s | 0.243 (n 341) | 0.453 (n 202) | 2.03 |
| react_lift | -0.06 (n 341) | 0.12 (n 202) | 2.12 |
| push_mean | 3.44 (n 341) | 3.57 (n 202) | 0.18 |
| push_max | 9.65 (n 341) | 10.82 (n 202) | 0.64 |
| spell_share | 0.034 (n 341) | 0.032 (n 202) | -0.03 |
| opp_el | 7.63 (n 341) | 7.21 (n 202) | -0.51 |

### sig:hogrider  (live n=281, SIM n=746, distance 0.93, floor 0.07)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.48 (n 281) | 5.16 (n 746) | -0.22 |
| ppm_2x | 8.96 (n 268) | 11.60 (n 736) | 0.79 |
| own_half | 0.336 (n 280) | 0.304 (n 746) | -0.29 |
| bridge | 0.605 (n 280) | 0.673 (n 746) | 0.57 |
| our_half | 0.059 (n 280) | 0.023 (n 746) | -0.48 |
| first_tick | 259.35 (n 281) | 412.98 (n 746) | 0.72 |
| react_s | 6.13 (n 281) | 4.78 (n 746) | -1.42 |
| react_3s | 0.271 (n 281) | 0.480 (n 746) | 1.69 |
| react_lift | -0.05 (n 281) | 0.11 (n 746) | 1.94 |
| push_mean | 3.49 (n 281) | 3.67 (n 746) | 0.26 |
| push_max | 10.07 (n 281) | 10.65 (n 746) | 0.35 |
| spell_share | 0.024 (n 281) | 0.042 (n 746) | 0.29 |
| opp_el | 7.74 (n 281) | 7.19 (n 746) | -0.63 |

## 4. Detector blind spots, measured on the SIM exact plays (primary SIM)

- exact opponent plays 36498; the detector (live code) finds 30176 = 82.7%
- non-spell plays: 29062/29892 = 97.2% found
- spell plays: 1114/6606 = 16.9% found (18.1% of all SIM plays are spells; live sees only the body-dropping ones)
- SIM opponent elixir at play: true 5.90 (mean, exact) vs the public counter 7.08 (last decision before the play). The counter is a +26-tick forecast and never charges invisible spells, so it reads far above the truth; the known pure bias of the live counter is +0.34 (econ_sim_patch.py). `opp_el` is therefore comparable counter-to-counter (live vs SIM), NOT to true elixir, and it drifts up with every invisible spell the opponent casts (SIM opponents cast many).

