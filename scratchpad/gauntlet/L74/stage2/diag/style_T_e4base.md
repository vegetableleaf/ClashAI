# Opponent behaviour: SIM opponents vs real 12k humans

LIVE: 1919 icebow main-account matches since 10-01 (`L74/mix/live_cost_1001.json`), opponent plays reconstructed from reader bodies.  
SIM (primary): `T_e4base`, 960 matches (learner r1 vs the SIM opponent policy).  d = (SIM mean - LIVE mean) / pooled SD, per match; distance = RMS of d over the features that have n >= 5 on both sides; floor = sqrt(1/nL + 1/nS), the distance two draws of the SAME population give by chance (distance <= ~1.5 x floor = indistinguishable).

Features (opponent side, all from the detected plays): `ppm_1x` plays/min before 2:00; `ppm_2x` plays/min in double elixir + overtime; `own_half` / `bridge` / `our_half` share of plays born on their half (y > 19) / within 3 tiles of the river / on our half (y < 13); `first_tick` tick of their first play; `react_s` mean seconds from OUR play to THEIR next play (cap 10 s, none = 10); `react_3s` share of our plays answered within 3 s; `react_lift` = react_3s minus its chance level (a busier opponent answers more often by luck: the share of the match in which a play of theirs starts within the next 3 s); `push_mean` / `push_max` elixir of plays per 8 s window, mean / max over the match; `spell_share` share of VISIBLE plays that are spells (graveyard, barrels, ... ; bodiless spells never appear); `opp_el` the public opponent-elixir counter at the last decision before the play (a +26-tick forecast on both sources).

**Headline (ALL matches, mix-confounded -- read the archetype rows):** largest gaps `react_3s` live 0.26 vs SIM 0.47 (d +1.81); `react_lift` live -0.05 vs SIM 0.09 (d +1.78); `react_s` live 6.16 vs SIM 4.83 (d -1.39); `ppm_2x` live 8.64 vs SIM 11.77 (d +1.21).

## 1. Distance per archetype (primary SIM: T_e4base)

| group | n live | n SIM | distance | floor | ppm_1x | ppm_2x | own_half | bridge | our_half | first_tick | react_s | react_3s | react_lift | push_mean | push_max | spell_share | opp_el |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 1919 | 960 | **0.96** | 0.04 | 0.00 | 1.21 | 0.12 | 0.31 | -0.58 | 0.85 | -1.39 | 1.81 | 1.78 | 0.66 | 0.60 | 0.14 | -0.47 |
| arch:hyperbait | 89 | 22 | **1.05** | 0.24 | -0.74 | 1.48 | -0.29 | 0.05 | 0.45 | 1.17 | -1.36 | 1.74 | 1.69 | 1.02 | 0.77 | -0.71 | -0.13 |
| arch:weak_other | 838 | 500 | **1.04** | 0.06 | -0.25 | 1.21 | 0.11 | 0.39 | -0.66 | 0.97 | -1.42 | 1.95 | 1.96 | 0.60 | 0.69 | 0.23 | -0.62 |
| arch:other | 739 | 438 | **0.91** | 0.06 | 0.18 | 1.25 | 0.17 | 0.19 | -0.53 | 0.64 | -1.39 | 1.73 | 1.62 | 0.68 | 0.49 | 0.02 | -0.43 |
| sig:royalrecruits | 92 | 104 | **1.46** | 0.14 | 0.25 | 2.15 | -0.14 | 0.56 | -0.61 | 0.89 | -2.16 | 2.52 | 2.24 | 0.90 | 0.63 | 1.27 | -1.62 |
| sig:skeletonballoon (small n) | 151 | 6 | **1.45** | 0.42 | -1.02 | 1.56 | -0.67 | 1.14 | -0.73 | 2.11 | -2.00 | 1.86 | 1.47 | 1.52 | 2.06 | -0.64 | -0.71 |
| sig:firecracker | 323 | 266 | **1.09** | 0.08 | 0.41 | 1.60 | 0.05 | 0.27 | -0.43 | 0.60 | -1.83 | 2.13 | 1.72 | 0.87 | 0.48 | 0.30 | -0.51 |
| sig:megaknight | 310 | 254 | **1.09** | 0.08 | -0.18 | 1.41 | 0.05 | 0.53 | -0.80 | 0.87 | -1.62 | 2.06 | 1.98 | 0.55 | 0.57 | -0.06 | -0.56 |
| sig:minipekka | 341 | 164 | **1.04** | 0.10 | -0.36 | 1.17 | 0.20 | 0.26 | -0.59 | 0.90 | -1.55 | 2.00 | 1.90 | 0.71 | 0.83 | 0.18 | -0.09 |
| sig:hogrider | 281 | 752 | **0.89** | 0.07 | -0.10 | 0.94 | 0.22 | 0.12 | -0.56 | 0.65 | -1.35 | 1.64 | 1.83 | 0.49 | 0.45 | 0.37 | -0.41 |

Groups with n < 5 on a side (no comparison): sig:elixirgolem (live 154, SIM 0), arch:golem (live 109, SIM 0), sig:golem (live 109, SIM 0), arch:royal_giant (live 55, SIM 0), arch:royal_giant_monk (live 24, SIM 0), arch:pekka_bridge (live 28, SIM 0), arch:lava_hound (live 37, SIM 0)

## 2. Feature means, live vs SIM, per group

### ALL  (live n=1919, SIM n=960, distance 0.96, floor 0.04)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.33 (n 1918) | 5.33 (n 960) | 0.00 |
| ppm_2x | 8.64 (n 1777) | 11.77 (n 954) | 1.21 |
| own_half | 0.349 (n 1914) | 0.365 (n 960) | 0.12 |
| bridge | 0.570 (n 1914) | 0.616 (n 960) | 0.31 |
| our_half | 0.082 (n 1914) | 0.020 (n 960) | -0.58 |
| first_tick | 258.44 (n 1915) | 382.71 (n 960) | 0.85 |
| react_s | 6.16 (n 1919) | 4.83 (n 960) | -1.39 |
| react_3s | 0.263 (n 1919) | 0.471 (n 960) | 1.81 |
| react_lift | -0.05 (n 1919) | 0.09 (n 960) | 1.78 |
| push_mean | 3.41 (n 1919) | 3.79 (n 960) | 0.66 |
| push_max | 9.66 (n 1919) | 10.74 (n 960) | 0.60 |
| spell_share | 0.053 (n 1915) | 0.065 (n 960) | 0.14 |
| opp_el | 7.74 (n 1915) | 7.34 (n 960) | -0.47 |

### arch:hyperbait  (live n=89, SIM n=22, distance 1.05, floor 0.24)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.09 (n 89) | 5.34 (n 22) | -0.74 |
| ppm_2x | 9.69 (n 87) | 12.50 (n 20) | 1.48 |
| own_half | 0.387 (n 89) | 0.338 (n 22) | -0.29 |
| bridge | 0.549 (n 89) | 0.557 (n 22) | 0.05 |
| our_half | 0.064 (n 89) | 0.104 (n 22) | 0.45 |
| first_tick | 245.47 (n 89) | 332.73 (n 22) | 1.17 |
| react_s | 5.34 (n 89) | 4.30 (n 22) | -1.36 |
| react_3s | 0.363 (n 89) | 0.549 (n 22) | 1.74 |
| react_lift | 0.02 (n 89) | 0.17 (n 22) | 1.69 |
| push_mean | 3.33 (n 89) | 3.82 (n 22) | 1.02 |
| push_max | 9.45 (n 89) | 10.55 (n 22) | 0.77 |
| spell_share | 0.138 (n 89) | 0.088 (n 22) | -0.71 |
| opp_el | 7.44 (n 89) | 7.33 (n 22) | -0.13 |

### arch:weak_other  (live n=838, SIM n=500, distance 1.04, floor 0.06)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.04 (n 838) | 4.75 (n 500) | -0.25 |
| ppm_2x | 8.22 (n 772) | 10.67 (n 496) | 1.21 |
| own_half | 0.334 (n 838) | 0.349 (n 500) | 0.11 |
| bridge | 0.571 (n 838) | 0.630 (n 500) | 0.39 |
| our_half | 0.095 (n 838) | 0.022 (n 500) | -0.66 |
| first_tick | 256.66 (n 838) | 409.72 (n 500) | 0.97 |
| react_s | 6.32 (n 838) | 5.07 (n 500) | -1.42 |
| react_3s | 0.244 (n 838) | 0.441 (n 500) | 1.95 |
| react_lift | -0.06 (n 838) | 0.09 (n 500) | 1.96 |
| push_mean | 3.47 (n 838) | 3.80 (n 500) | 0.60 |
| push_max | 9.86 (n 838) | 11.07 (n 500) | 0.69 |
| spell_share | 0.045 (n 838) | 0.062 (n 500) | 0.23 |
| opp_el | 7.92 (n 838) | 7.47 (n 500) | -0.62 |

### arch:other  (live n=739, SIM n=438, distance 0.91, floor 0.06)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.71 (n 738) | 6.00 (n 438) | 0.18 |
| ppm_2x | 9.20 (n 694) | 12.98 (n 438) | 1.25 |
| own_half | 0.361 (n 734) | 0.384 (n 438) | 0.17 |
| bridge | 0.575 (n 734) | 0.603 (n 438) | 0.19 |
| our_half | 0.063 (n 734) | 0.013 (n 438) | -0.53 |
| first_tick | 260.73 (n 735) | 354.38 (n 438) | 0.64 |
| react_s | 5.99 (n 739) | 4.57 (n 438) | -1.39 |
| react_3s | 0.287 (n 739) | 0.501 (n 438) | 1.73 |
| react_lift | -0.04 (n 739) | 0.09 (n 438) | 1.62 |
| push_mean | 3.35 (n 739) | 3.76 (n 438) | 0.68 |
| push_max | 9.47 (n 739) | 10.37 (n 438) | 0.49 |
| spell_share | 0.065 (n 735) | 0.066 (n 438) | 0.02 |
| opp_el | 7.58 (n 735) | 7.20 (n 438) | -0.43 |

### sig:royalrecruits  (live n=92, SIM n=104, distance 1.46, floor 0.14)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.49 (n 92) | 4.75 (n 104) | 0.25 |
| ppm_2x | 7.30 (n 86) | 10.85 (n 104) | 2.15 |
| own_half | 0.342 (n 92) | 0.327 (n 104) | -0.14 |
| bridge | 0.579 (n 92) | 0.648 (n 104) | 0.56 |
| our_half | 0.079 (n 92) | 0.026 (n 104) | -0.61 |
| first_tick | 260.77 (n 92) | 390.58 (n 104) | 0.89 |
| react_s | 6.73 (n 92) | 5.03 (n 104) | -2.16 |
| react_3s | 0.208 (n 92) | 0.430 (n 104) | 2.52 |
| react_lift | -0.07 (n 92) | 0.07 (n 104) | 2.24 |
| push_mean | 3.54 (n 92) | 3.93 (n 104) | 0.90 |
| push_max | 9.76 (n 92) | 10.88 (n 104) | 0.63 |
| spell_share | 0.048 (n 92) | 0.145 (n 104) | 1.27 |
| opp_el | 8.19 (n 92) | 7.14 (n 104) | -1.62 |

### sig:skeletonballoon  (live n=151, SIM n=6, distance 1.45, floor 0.42)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.10 (n 151) | 4.85 (n 6) | -1.02 |
| ppm_2x | 9.45 (n 141) | 12.71 (n 6) | 1.56 |
| own_half | 0.305 (n 151) | 0.214 (n 6) | -0.67 |
| bridge | 0.615 (n 151) | 0.786 (n 6) | 1.14 |
| our_half | 0.080 (n 151) | 0.000 (n 6) | -0.73 |
| first_tick | 238.01 (n 151) | 363.33 (n 6) | 2.11 |
| react_s | 5.88 (n 151) | 4.22 (n 6) | -2.00 |
| react_3s | 0.293 (n 151) | 0.478 (n 6) | 1.86 |
| react_lift | -0.06 (n 151) | 0.06 (n 6) | 1.47 |
| push_mean | 3.45 (n 151) | 4.26 (n 6) | 1.52 |
| push_max | 9.70 (n 151) | 13.33 (n 6) | 2.06 |
| spell_share | 0.042 (n 151) | 0.000 (n 6) | -0.64 |
| opp_el | 7.81 (n 151) | 7.35 (n 6) | -0.71 |

### sig:firecracker  (live n=323, SIM n=266, distance 1.09, floor 0.08)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.36 (n 323) | 5.92 (n 266) | 0.41 |
| ppm_2x | 8.79 (n 300) | 12.89 (n 266) | 1.60 |
| own_half | 0.349 (n 322) | 0.356 (n 266) | 0.05 |
| bridge | 0.577 (n 322) | 0.614 (n 266) | 0.27 |
| our_half | 0.074 (n 322) | 0.030 (n 266) | -0.43 |
| first_tick | 255.97 (n 323) | 343.76 (n 266) | 0.60 |
| react_s | 6.05 (n 323) | 4.46 (n 266) | -1.83 |
| react_3s | 0.271 (n 323) | 0.508 (n 266) | 2.13 |
| react_lift | -0.05 (n 323) | 0.09 (n 266) | 1.72 |
| push_mean | 3.46 (n 323) | 3.95 (n 266) | 0.87 |
| push_max | 10.08 (n 323) | 10.92 (n 266) | 0.48 |
| spell_share | 0.031 (n 323) | 0.053 (n 266) | 0.30 |
| opp_el | 7.67 (n 323) | 7.27 (n 266) | -0.51 |

### sig:megaknight  (live n=310, SIM n=254, distance 1.09, floor 0.08)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.72 (n 310) | 4.52 (n 254) | -0.18 |
| ppm_2x | 7.79 (n 288) | 10.35 (n 250) | 1.41 |
| own_half | 0.338 (n 310) | 0.345 (n 254) | 0.05 |
| bridge | 0.559 (n 310) | 0.637 (n 254) | 0.53 |
| our_half | 0.104 (n 310) | 0.018 (n 254) | -0.80 |
| first_tick | 269.24 (n 310) | 432.44 (n 254) | 0.87 |
| react_s | 6.48 (n 310) | 5.08 (n 254) | -1.62 |
| react_3s | 0.228 (n 310) | 0.441 (n 254) | 2.06 |
| react_lift | -0.06 (n 310) | 0.09 (n 254) | 1.98 |
| push_mean | 3.48 (n 310) | 3.80 (n 254) | 0.55 |
| push_max | 10.28 (n 310) | 11.28 (n 254) | 0.57 |
| spell_share | 0.029 (n 310) | 0.025 (n 254) | -0.06 |
| opp_el | 7.94 (n 310) | 7.52 (n 254) | -0.56 |

### sig:minipekka  (live n=341, SIM n=164, distance 1.04, floor 0.10)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.07 (n 341) | 4.69 (n 164) | -0.36 |
| ppm_2x | 8.31 (n 304) | 10.53 (n 162) | 1.17 |
| own_half | 0.314 (n 341) | 0.343 (n 164) | 0.20 |
| bridge | 0.588 (n 341) | 0.629 (n 164) | 0.26 |
| our_half | 0.099 (n 341) | 0.029 (n 164) | -0.59 |
| first_tick | 264.70 (n 341) | 416.83 (n 164) | 0.90 |
| react_s | 6.33 (n 341) | 5.01 (n 164) | -1.55 |
| react_3s | 0.243 (n 341) | 0.450 (n 164) | 2.00 |
| react_lift | -0.06 (n 341) | 0.10 (n 164) | 1.90 |
| push_mean | 3.44 (n 341) | 3.85 (n 164) | 0.71 |
| push_max | 9.65 (n 341) | 11.13 (n 164) | 0.83 |
| spell_share | 0.034 (n 341) | 0.046 (n 164) | 0.18 |
| opp_el | 7.63 (n 341) | 7.56 (n 164) | -0.09 |

### sig:hogrider  (live n=281, SIM n=752, distance 0.89, floor 0.07)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.48 (n 281) | 5.33 (n 752) | -0.10 |
| ppm_2x | 8.96 (n 268) | 11.79 (n 746) | 0.94 |
| own_half | 0.336 (n 280) | 0.361 (n 752) | 0.22 |
| bridge | 0.605 (n 280) | 0.620 (n 752) | 0.12 |
| our_half | 0.059 (n 280) | 0.019 (n 752) | -0.56 |
| first_tick | 259.35 (n 281) | 389.79 (n 752) | 0.65 |
| react_s | 6.13 (n 281) | 4.78 (n 752) | -1.35 |
| react_3s | 0.271 (n 281) | 0.478 (n 752) | 1.64 |
| react_lift | -0.05 (n 281) | 0.10 (n 752) | 1.83 |
| push_mean | 3.49 (n 281) | 3.80 (n 752) | 0.49 |
| push_max | 10.07 (n 281) | 10.85 (n 752) | 0.45 |
| spell_share | 0.024 (n 281) | 0.051 (n 752) | 0.37 |
| opp_el | 7.74 (n 281) | 7.38 (n 752) | -0.41 |

## 4. Detector blind spots, measured on the SIM exact plays (primary SIM)

- exact opponent plays 38778; the detector (live code) finds 31614 = 81.5%
- non-spell plays: 30312/31424 = 96.5% found
- spell plays: 1302/7354 = 17.7% found (19.0% of all SIM plays are spells; live sees only the body-dropping ones)
- SIM opponent elixir at play: true 6.07 (mean, exact) vs the public counter 7.17 (last decision before the play). The counter is a +26-tick forecast and never charges invisible spells, so it reads far above the truth; the known pure bias of the live counter is +0.34 (econ_sim_patch.py). `opp_el` is therefore comparable counter-to-counter (live vs SIM), NOT to true elixir, and it drifts up with every invisible spell the opponent casts (SIM opponents cast many).

