# Opponent behaviour: SIM opponents vs real 12k humans

LIVE: 1919 icebow main-account matches since 10-01 (`L74/mix/live_cost_1001.json`), opponent plays reconstructed from reader bodies.  
SIM (primary): `T_e4_u0065`, 960 matches (learner r1 vs the SIM opponent policy).  d = (SIM mean - LIVE mean) / pooled SD, per match; distance = RMS of d over the features that have n >= 5 on both sides; floor = sqrt(1/nL + 1/nS), the distance two draws of the SAME population give by chance (distance <= ~1.5 x floor = indistinguishable).

Features (opponent side, all from the detected plays): `ppm_1x` plays/min before 2:00; `ppm_2x` plays/min in double elixir + overtime; `own_half` / `bridge` / `our_half` share of plays born on their half (y > 19) / within 3 tiles of the river / on our half (y < 13); `first_tick` tick of their first play; `react_s` mean seconds from OUR play to THEIR next play (cap 10 s, none = 10); `react_3s` share of our plays answered within 3 s; `react_lift` = react_3s minus its chance level (a busier opponent answers more often by luck: the share of the match in which a play of theirs starts within the next 3 s); `push_mean` / `push_max` elixir of plays per 8 s window, mean / max over the match; `spell_share` share of VISIBLE plays that are spells (graveyard, barrels, ... ; bodiless spells never appear); `opp_el` the public opponent-elixir counter at the last decision before the play (a +26-tick forecast on both sources).

**Headline (ALL matches, mix-confounded -- read the archetype rows):** largest gaps `react_lift` live -0.05 vs SIM 0.12 (d +2.22); `react_3s` live 0.26 vs SIM 0.49 (d +2.06); `react_s` live 6.16 vs SIM 4.73 (d -1.54); `ppm_2x` live 8.64 vs SIM 11.86 (d +1.26).

## 1. Distance per archetype (primary SIM: T_e4_u0065)

| group | n live | n SIM | distance | floor | ppm_1x | ppm_2x | own_half | bridge | our_half | first_tick | react_s | react_3s | react_lift | push_mean | push_max | spell_share | opp_el |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 1919 | 960 | **1.14** | 0.04 | -0.37 | 1.26 | -0.30 | 0.68 | -0.56 | 1.15 | -1.54 | 2.06 | 2.22 | 0.58 | 0.84 | 0.10 | -0.53 |
| arch:weak_other | 838 | 508 | **1.22** | 0.06 | -0.70 | 1.24 | -0.26 | 0.74 | -0.68 | 1.26 | -1.60 | 2.22 | 2.34 | 0.57 | 1.00 | 0.20 | -0.65 |
| arch:hyperbait | 89 | 32 | **1.18** | 0.21 | -1.11 | 1.43 | -0.97 | 0.58 | 0.65 | 1.48 | -1.14 | 1.79 | 2.02 | 0.97 | 0.94 | -0.40 | -0.54 |
| arch:other | 739 | 420 | **1.08** | 0.06 | -0.15 | 1.36 | -0.27 | 0.59 | -0.49 | 0.93 | -1.55 | 2.00 | 2.12 | 0.53 | 0.65 | -0.06 | -0.48 |
| sig:royalrecruits | 92 | 104 | **1.57** | 0.14 | -0.05 | 2.07 | -0.68 | 1.05 | -0.65 | 1.08 | -2.14 | 2.75 | 2.59 | 0.76 | 0.97 | 1.31 | -1.53 |
| sig:megaknight | 310 | 260 | **1.31** | 0.08 | -0.67 | 1.48 | -0.40 | 0.89 | -0.71 | 1.20 | -1.92 | 2.43 | 2.38 | 0.53 | 0.87 | -0.03 | -0.67 |
| sig:firecracker | 323 | 268 | **1.30** | 0.08 | -0.08 | 1.64 | -0.38 | 0.64 | -0.39 | 0.91 | -2.03 | 2.47 | 2.40 | 0.77 | 0.75 | 0.36 | -0.71 |
| sig:skeletonballoon (small n) | 151 | 6 | **1.24** | 0.42 | -0.47 | 1.44 | -0.08 | 0.60 | -0.73 | 1.88 | -1.29 | 1.98 | 1.74 | 1.43 | 1.30 | -0.64 | -0.68 |
| sig:minipekka | 341 | 190 | **1.23** | 0.09 | -0.87 | 1.28 | -0.18 | 0.58 | -0.54 | 1.21 | -1.78 | 2.24 | 2.23 | 0.76 | 1.11 | 0.11 | -0.20 |
| sig:hogrider | 281 | 756 | **1.06** | 0.07 | -0.47 | 0.99 | -0.22 | 0.52 | -0.49 | 0.90 | -1.57 | 1.90 | 2.26 | 0.39 | 0.68 | 0.35 | -0.46 |

Groups with n < 5 on a side (no comparison): sig:elixirgolem (live 154, SIM 0), arch:golem (live 109, SIM 0), sig:golem (live 109, SIM 0), arch:royal_giant (live 55, SIM 0), arch:royal_giant_monk (live 24, SIM 0), arch:pekka_bridge (live 28, SIM 0), arch:lava_hound (live 37, SIM 0)

## 2. Feature means, live vs SIM, per group

### ALL  (live n=1919, SIM n=960, distance 1.14, floor 0.04)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.33 (n 1918) | 4.81 (n 960) | -0.37 |
| ppm_2x | 8.64 (n 1777) | 11.86 (n 960) | 1.26 |
| own_half | 0.349 (n 1914) | 0.309 (n 960) | -0.30 |
| bridge | 0.570 (n 1914) | 0.670 (n 960) | 0.68 |
| our_half | 0.082 (n 1914) | 0.021 (n 960) | -0.56 |
| first_tick | 258.44 (n 1915) | 440.40 (n 960) | 1.15 |
| react_s | 6.16 (n 1919) | 4.73 (n 960) | -1.54 |
| react_3s | 0.263 (n 1919) | 0.493 (n 960) | 2.06 |
| react_lift | -0.05 (n 1919) | 0.12 (n 960) | 2.22 |
| push_mean | 3.41 (n 1919) | 3.74 (n 960) | 0.58 |
| push_max | 9.66 (n 1919) | 11.17 (n 960) | 0.84 |
| spell_share | 0.053 (n 1915) | 0.062 (n 960) | 0.10 |
| opp_el | 7.74 (n 1915) | 7.31 (n 960) | -0.53 |

### arch:weak_other  (live n=838, SIM n=508, distance 1.22, floor 0.06)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.04 (n 838) | 4.25 (n 508) | -0.70 |
| ppm_2x | 8.22 (n 772) | 10.74 (n 508) | 1.24 |
| own_half | 0.334 (n 838) | 0.300 (n 508) | -0.26 |
| bridge | 0.571 (n 838) | 0.681 (n 508) | 0.74 |
| our_half | 0.095 (n 838) | 0.020 (n 508) | -0.68 |
| first_tick | 256.66 (n 838) | 464.72 (n 508) | 1.26 |
| react_s | 6.32 (n 838) | 4.94 (n 508) | -1.60 |
| react_3s | 0.244 (n 838) | 0.463 (n 508) | 2.22 |
| react_lift | -0.06 (n 838) | 0.12 (n 508) | 2.34 |
| push_mean | 3.47 (n 838) | 3.79 (n 508) | 0.57 |
| push_max | 9.86 (n 838) | 11.62 (n 508) | 1.00 |
| spell_share | 0.045 (n 838) | 0.061 (n 508) | 0.20 |
| opp_el | 7.92 (n 838) | 7.44 (n 508) | -0.65 |

### arch:hyperbait  (live n=89, SIM n=32, distance 1.18, floor 0.21)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.09 (n 89) | 4.94 (n 32) | -1.11 |
| ppm_2x | 9.69 (n 87) | 12.53 (n 32) | 1.43 |
| own_half | 0.387 (n 89) | 0.236 (n 32) | -0.97 |
| bridge | 0.549 (n 89) | 0.640 (n 32) | 0.58 |
| our_half | 0.064 (n 89) | 0.124 (n 32) | 0.65 |
| first_tick | 245.47 (n 89) | 423.12 (n 32) | 1.48 |
| react_s | 5.34 (n 89) | 4.42 (n 32) | -1.14 |
| react_3s | 0.363 (n 89) | 0.554 (n 32) | 1.79 |
| react_lift | 0.02 (n 89) | 0.18 (n 32) | 2.02 |
| push_mean | 3.33 (n 89) | 3.81 (n 32) | 0.97 |
| push_max | 9.45 (n 89) | 10.94 (n 32) | 0.94 |
| spell_share | 0.138 (n 89) | 0.108 (n 32) | -0.40 |
| opp_el | 7.44 (n 89) | 6.97 (n 32) | -0.54 |

### arch:other  (live n=739, SIM n=420, distance 1.08, floor 0.06)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.71 (n 738) | 5.47 (n 420) | -0.15 |
| ppm_2x | 9.20 (n 694) | 13.17 (n 420) | 1.36 |
| own_half | 0.361 (n 734) | 0.326 (n 420) | -0.27 |
| bridge | 0.575 (n 734) | 0.659 (n 420) | 0.59 |
| our_half | 0.063 (n 734) | 0.015 (n 420) | -0.49 |
| first_tick | 260.73 (n 735) | 412.29 (n 420) | 0.93 |
| react_s | 5.99 (n 739) | 4.50 (n 420) | -1.55 |
| react_3s | 0.287 (n 739) | 0.524 (n 420) | 2.00 |
| react_lift | -0.04 (n 739) | 0.12 (n 420) | 2.12 |
| push_mean | 3.35 (n 739) | 3.67 (n 420) | 0.53 |
| push_max | 9.47 (n 739) | 10.65 (n 420) | 0.65 |
| spell_share | 0.065 (n 735) | 0.059 (n 420) | -0.06 |
| opp_el | 7.58 (n 735) | 7.18 (n 420) | -0.48 |

### sig:royalrecruits  (live n=92, SIM n=104, distance 1.57, floor 0.14)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.49 (n 92) | 4.45 (n 104) | -0.05 |
| ppm_2x | 7.30 (n 86) | 10.95 (n 104) | 2.07 |
| own_half | 0.342 (n 92) | 0.269 (n 104) | -0.68 |
| bridge | 0.579 (n 92) | 0.708 (n 104) | 1.05 |
| our_half | 0.079 (n 92) | 0.024 (n 104) | -0.65 |
| first_tick | 260.77 (n 92) | 415.58 (n 104) | 1.08 |
| react_s | 6.73 (n 92) | 4.95 (n 104) | -2.14 |
| react_3s | 0.208 (n 92) | 0.461 (n 104) | 2.75 |
| react_lift | -0.07 (n 92) | 0.11 (n 104) | 2.59 |
| push_mean | 3.54 (n 92) | 3.90 (n 104) | 0.76 |
| push_max | 9.76 (n 92) | 11.37 (n 104) | 0.97 |
| spell_share | 0.048 (n 92) | 0.151 (n 104) | 1.31 |
| opp_el | 8.19 (n 92) | 7.08 (n 104) | -1.53 |

### sig:megaknight  (live n=310, SIM n=260, distance 1.31, floor 0.08)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.72 (n 310) | 4.00 (n 260) | -0.67 |
| ppm_2x | 7.79 (n 288) | 10.51 (n 260) | 1.48 |
| own_half | 0.338 (n 310) | 0.287 (n 260) | -0.40 |
| bridge | 0.559 (n 310) | 0.689 (n 260) | 0.89 |
| our_half | 0.104 (n 310) | 0.024 (n 260) | -0.71 |
| first_tick | 269.24 (n 310) | 504.85 (n 260) | 1.20 |
| react_s | 6.48 (n 310) | 4.89 (n 260) | -1.92 |
| react_3s | 0.228 (n 310) | 0.463 (n 260) | 2.43 |
| react_lift | -0.06 (n 310) | 0.12 (n 260) | 2.38 |
| push_mean | 3.48 (n 310) | 3.80 (n 260) | 0.53 |
| push_max | 10.28 (n 310) | 11.82 (n 260) | 0.87 |
| spell_share | 0.029 (n 310) | 0.027 (n 260) | -0.03 |
| opp_el | 7.94 (n 310) | 7.44 (n 260) | -0.67 |

### sig:firecracker  (live n=323, SIM n=268, distance 1.30, floor 0.08)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.36 (n 323) | 5.25 (n 268) | -0.08 |
| ppm_2x | 8.79 (n 300) | 12.91 (n 268) | 1.64 |
| own_half | 0.349 (n 322) | 0.302 (n 268) | -0.38 |
| bridge | 0.577 (n 322) | 0.665 (n 268) | 0.64 |
| our_half | 0.074 (n 322) | 0.033 (n 268) | -0.39 |
| first_tick | 255.97 (n 323) | 390.07 (n 268) | 0.91 |
| react_s | 6.05 (n 323) | 4.34 (n 268) | -2.03 |
| react_3s | 0.271 (n 323) | 0.539 (n 268) | 2.47 |
| react_lift | -0.05 (n 323) | 0.14 (n 268) | 2.40 |
| push_mean | 3.46 (n 323) | 3.90 (n 268) | 0.77 |
| push_max | 10.08 (n 323) | 11.43 (n 268) | 0.75 |
| spell_share | 0.031 (n 323) | 0.058 (n 268) | 0.36 |
| opp_el | 7.67 (n 323) | 7.12 (n 268) | -0.71 |

### sig:skeletonballoon  (live n=151, SIM n=6, distance 1.24, floor 0.42)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.10 (n 151) | 5.54 (n 6) | -0.47 |
| ppm_2x | 9.45 (n 141) | 12.53 (n 6) | 1.44 |
| own_half | 0.305 (n 151) | 0.294 (n 6) | -0.08 |
| bridge | 0.615 (n 151) | 0.706 (n 6) | 0.60 |
| our_half | 0.080 (n 151) | 0.000 (n 6) | -0.73 |
| first_tick | 238.01 (n 151) | 333.33 (n 6) | 1.88 |
| react_s | 5.88 (n 151) | 4.80 (n 6) | -1.29 |
| react_3s | 0.293 (n 151) | 0.493 (n 6) | 1.98 |
| react_lift | -0.06 (n 151) | 0.08 (n 6) | 1.74 |
| push_mean | 3.45 (n 151) | 4.22 (n 6) | 1.43 |
| push_max | 9.70 (n 151) | 12.00 (n 6) | 1.30 |
| spell_share | 0.042 (n 151) | 0.000 (n 6) | -0.64 |
| opp_el | 7.81 (n 151) | 7.36 (n 6) | -0.68 |

### sig:minipekka  (live n=341, SIM n=190, distance 1.23, floor 0.09)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.07 (n 341) | 4.17 (n 190) | -0.87 |
| ppm_2x | 8.31 (n 304) | 10.83 (n 190) | 1.28 |
| own_half | 0.314 (n 341) | 0.289 (n 190) | -0.18 |
| bridge | 0.588 (n 341) | 0.677 (n 190) | 0.58 |
| our_half | 0.099 (n 341) | 0.034 (n 190) | -0.54 |
| first_tick | 264.70 (n 341) | 480.95 (n 190) | 1.21 |
| react_s | 6.33 (n 341) | 4.84 (n 190) | -1.78 |
| react_3s | 0.243 (n 341) | 0.468 (n 190) | 2.24 |
| react_lift | -0.06 (n 341) | 0.12 (n 190) | 2.23 |
| push_mean | 3.44 (n 341) | 3.88 (n 190) | 0.76 |
| push_max | 9.65 (n 341) | 11.60 (n 190) | 1.11 |
| spell_share | 0.034 (n 341) | 0.042 (n 190) | 0.11 |
| opp_el | 7.63 (n 341) | 7.47 (n 190) | -0.20 |

### sig:hogrider  (live n=281, SIM n=756, distance 1.06, floor 0.07)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.48 (n 281) | 4.76 (n 756) | -0.47 |
| ppm_2x | 8.96 (n 268) | 11.80 (n 756) | 0.99 |
| own_half | 0.336 (n 280) | 0.311 (n 756) | -0.22 |
| bridge | 0.605 (n 280) | 0.667 (n 756) | 0.52 |
| our_half | 0.059 (n 280) | 0.022 (n 756) | -0.49 |
| first_tick | 259.35 (n 281) | 460.24 (n 756) | 0.90 |
| react_s | 6.13 (n 281) | 4.71 (n 756) | -1.57 |
| react_3s | 0.271 (n 281) | 0.496 (n 756) | 1.90 |
| react_lift | -0.05 (n 281) | 0.13 (n 756) | 2.26 |
| push_mean | 3.49 (n 281) | 3.73 (n 756) | 0.39 |
| push_max | 10.07 (n 281) | 11.26 (n 756) | 0.68 |
| spell_share | 0.024 (n 281) | 0.048 (n 756) | 0.35 |
| opp_el | 7.74 (n 281) | 7.37 (n 756) | -0.46 |

## 4. Detector blind spots, measured on the SIM exact plays (primary SIM)

- exact opponent plays 39320; the detector (live code) finds 32056 = 81.5%
- non-spell plays: 30736/31728 = 96.9% found
- spell plays: 1320/7592 = 17.4% found (19.3% of all SIM plays are spells; live sees only the body-dropping ones)
- SIM opponent elixir at play: true 6.10 (mean, exact) vs the public counter 7.18 (last decision before the play). The counter is a +26-tick forecast and never charges invisible spells, so it reads far above the truth; the known pure bias of the live counter is +0.34 (econ_sim_patch.py). `opp_el` is therefore comparable counter-to-counter (live vs SIM), NOT to true elixir, and it drifts up with every invisible spell the opponent casts (SIM opponents cast many).

