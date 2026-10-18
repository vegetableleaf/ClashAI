# Opponent behaviour: SIM opponents vs real 12k humans

LIVE: 35 icebow main-account matches since 10-01 (`L74/mix/live_cost_1001.json`), opponent plays reconstructed from reader bodies.  
SIM (primary): `S_v32_d10_r0`, 960 matches (learner r1 vs the SIM opponent policy).  d = (SIM mean - LIVE mean) / pooled SD, per match; distance = RMS of d over the features that have n >= 5 on both sides; floor = sqrt(1/nL + 1/nS), the distance two draws of the SAME population give by chance (distance <= ~1.5 x floor = indistinguishable).

Features (opponent side, all from the detected plays): `ppm_1x` plays/min before 2:00; `ppm_2x` plays/min in double elixir + overtime; `own_half` / `bridge` / `our_half` share of plays born on their half (y > 19) / within 3 tiles of the river / on our half (y < 13); `first_tick` tick of their first play; `react_s` mean seconds from OUR play to THEIR next play (cap 10 s, none = 10); `react_3s` share of our plays answered within 3 s; `react_lift` = react_3s minus its chance level (a busier opponent answers more often by luck: the share of the match in which a play of theirs starts within the next 3 s); `push_mean` / `push_max` elixir of plays per 8 s window, mean / max over the match; `spell_share` share of VISIBLE plays that are spells (graveyard, barrels, ... ; bodiless spells never appear); `opp_el` the public opponent-elixir counter at the last decision before the play (a +26-tick forecast on both sources).

**Headline (ALL matches, mix-confounded -- read the archetype rows):** largest gaps `react_lift` live -0.07 vs SIM 0.08 (d +1.75); `react_3s` live 0.25 vs SIM 0.47 (d +1.59); `react_s` live 6.13 vs SIM 4.76 (d -1.31); `ppm_2x` live 8.99 vs SIM 11.77 (d +0.86).

## 1. Distance per archetype (primary SIM: S_v32_d10_r0)

| group | n live | n SIM | distance | floor | ppm_1x | ppm_2x | own_half | bridge | our_half | first_tick | react_s | react_3s | react_lift | push_mean | push_max | spell_share | opp_el |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ALL | 35 | 960 | **0.86** | 0.17 | 0.19 | 0.86 | -0.35 | 0.46 | -0.26 | 0.39 | -1.31 | 1.59 | 1.75 | 0.66 | 0.22 | -0.02 | -0.69 |
| arch:other (small n) | 11 | 398 | **0.91** | 0.31 | -0.01 | 0.78 | -0.34 | 0.38 | -0.15 | 0.29 | -1.32 | 1.62 | 2.04 | 0.76 | 0.37 | 0.14 | -0.70 |
| arch:weak_other | 18 | 342 | **0.87** | 0.24 | 0.19 | 0.85 | -0.33 | 0.57 | -0.53 | 0.45 | -1.27 | 1.65 | 1.71 | 0.65 | 0.29 | -0.15 | -0.53 |
| sig:minipekka (small n) | 5 | 150 | **1.28** | 0.45 | 0.03 | - | 0.26 | -0.05 | -0.22 | 0.83 | -2.08 | 2.41 | 2.73 | 0.71 | 0.45 | 0.59 | -0.55 |
| sig:megaknight (small n) | 9 | 170 | **1.11** | 0.34 | -0.04 | 1.54 | 0.05 | 0.49 | -0.91 | 0.46 | -1.79 | 2.10 | 1.72 | 1.12 | 0.68 | -0.30 | -0.21 |
| sig:firecracker (small n) | 6 | 116 | **0.92** | 0.42 | 0.90 | - | -0.85 | 1.07 | -0.61 | -0.18 | -1.53 | 1.52 | 1.30 | 0.79 | -0.13 | -0.29 | -0.24 |

Groups with n < 5 on a side (no comparison): sig:elixirgolem (live 3, SIM 84), arch:royal_giant (live 1, SIM 22), sig:skeletonballoon (live 3, SIM 62), arch:hyperbait (live 3, SIM 80), sig:hogrider (live 4, SIM 158), arch:pekka_bridge (live 1, SIM 20), sig:royalrecruits (live 2, SIM 28), arch:golem (live 1, SIM 56), sig:golem (live 1, SIM 56), arch:royal_giant_monk (live 0, SIM 20), arch:lava_hound (live 0, SIM 22)

## 2. Feature means, live vs SIM, per group

### ALL  (live n=35, SIM n=960, distance 0.86, floor 0.17)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 5.25 (n 35) | 5.58 (n 960) | 0.19 |
| ppm_2x | 8.99 (n 33) | 11.77 (n 952) | 0.86 |
| own_half | 0.345 (n 35) | 0.308 (n 960) | -0.35 |
| bridge | 0.601 (n 35) | 0.656 (n 960) | 0.46 |
| our_half | 0.053 (n 35) | 0.036 (n 960) | -0.26 |
| first_tick | 258.69 (n 35) | 348.44 (n 960) | 0.39 |
| react_s | 6.13 (n 35) | 4.76 (n 960) | -1.31 |
| react_3s | 0.246 (n 35) | 0.468 (n 960) | 1.59 |
| react_lift | -0.07 (n 35) | 0.08 (n 960) | 1.75 |
| push_mean | 3.38 (n 35) | 3.78 (n 960) | 0.66 |
| push_max | 9.77 (n 35) | 10.13 (n 960) | 0.22 |
| spell_share | 0.068 (n 35) | 0.066 (n 960) | -0.02 |
| opp_el | 7.73 (n 35) | 6.97 (n 960) | -0.69 |

### arch:other  (live n=11, SIM n=398, distance 0.91, floor 0.31)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 6.04 (n 11) | 6.02 (n 398) | -0.01 |
| ppm_2x | 9.42 (n 10) | 12.40 (n 394) | 0.78 |
| own_half | 0.346 (n 11) | 0.308 (n 398) | -0.34 |
| bridge | 0.608 (n 11) | 0.657 (n 398) | 0.38 |
| our_half | 0.046 (n 11) | 0.036 (n 398) | -0.15 |
| first_tick | 260.09 (n 11) | 325.33 (n 398) | 0.29 |
| react_s | 6.06 (n 11) | 4.62 (n 398) | -1.32 |
| react_3s | 0.258 (n 11) | 0.497 (n 398) | 1.62 |
| react_lift | -0.07 (n 11) | 0.09 (n 398) | 2.04 |
| push_mean | 3.24 (n 11) | 3.70 (n 398) | 0.76 |
| push_max | 9.27 (n 11) | 9.86 (n 398) | 0.37 |
| spell_share | 0.061 (n 11) | 0.075 (n 398) | 0.14 |
| opp_el | 7.53 (n 11) | 6.77 (n 398) | -0.70 |

### arch:weak_other  (live n=18, SIM n=342, distance 0.87, floor 0.24)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.79 (n 18) | 5.07 (n 342) | 0.19 |
| ppm_2x | 8.71 (n 17) | 10.86 (n 342) | 0.85 |
| own_half | 0.333 (n 18) | 0.298 (n 342) | -0.33 |
| bridge | 0.614 (n 18) | 0.678 (n 342) | 0.57 |
| our_half | 0.053 (n 18) | 0.024 (n 342) | -0.53 |
| first_tick | 274.17 (n 18) | 378.19 (n 342) | 0.45 |
| react_s | 6.26 (n 18) | 5.01 (n 342) | -1.27 |
| react_3s | 0.225 (n 18) | 0.425 (n 342) | 1.65 |
| react_lift | -0.09 (n 18) | 0.05 (n 342) | 1.71 |
| push_mean | 3.45 (n 18) | 3.86 (n 342) | 0.65 |
| push_max | 9.94 (n 18) | 10.40 (n 342) | 0.29 |
| spell_share | 0.060 (n 18) | 0.048 (n 342) | -0.15 |
| opp_el | 7.84 (n 18) | 7.30 (n 342) | -0.53 |

### sig:minipekka  (live n=5, SIM n=150, distance 1.28, floor 0.45)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.75 (n 5) | 4.79 (n 150) | 0.03 |
| ppm_2x | 8.48 (n 4) | 10.54 (n 148) | - |
| own_half | 0.265 (n 5) | 0.287 (n 150) | 0.26 |
| bridge | 0.675 (n 5) | 0.670 (n 150) | -0.05 |
| our_half | 0.060 (n 5) | 0.043 (n 150) | -0.22 |
| first_tick | 216.60 (n 5) | 433.33 (n 150) | 0.83 |
| react_s | 6.82 (n 5) | 5.05 (n 150) | -2.08 |
| react_3s | 0.162 (n 5) | 0.422 (n 150) | 2.41 |
| react_lift | -0.12 (n 5) | 0.07 (n 150) | 2.73 |
| push_mean | 3.39 (n 5) | 3.79 (n 150) | 0.71 |
| push_max | 9.80 (n 5) | 10.56 (n 150) | 0.45 |
| spell_share | 0.000 (n 5) | 0.056 (n 150) | 0.59 |
| opp_el | 7.57 (n 5) | 7.03 (n 150) | -0.55 |

### sig:megaknight  (live n=9, SIM n=170, distance 1.11, floor 0.34)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.79 (n 9) | 4.74 (n 170) | -0.04 |
| ppm_2x | 7.71 (n 8) | 10.51 (n 170) | 1.54 |
| own_half | 0.296 (n 9) | 0.301 (n 170) | 0.05 |
| bridge | 0.611 (n 9) | 0.667 (n 170) | 0.49 |
| our_half | 0.093 (n 9) | 0.032 (n 170) | -0.91 |
| first_tick | 297.11 (n 9) | 405.18 (n 170) | 0.46 |
| react_s | 6.49 (n 9) | 5.03 (n 170) | -1.79 |
| react_3s | 0.195 (n 9) | 0.418 (n 170) | 2.10 |
| react_lift | -0.09 (n 9) | 0.06 (n 170) | 1.72 |
| push_mean | 3.25 (n 9) | 3.92 (n 170) | 1.12 |
| push_max | 9.89 (n 9) | 10.88 (n 170) | 0.68 |
| spell_share | 0.051 (n 9) | 0.030 (n 170) | -0.30 |
| opp_el | 7.59 (n 9) | 7.40 (n 170) | -0.21 |

### sig:firecracker  (live n=6, SIM n=116, distance 0.92, floor 0.42)

| feature | live mean | SIM mean | d |
|---|---:|---:|---:|
| ppm_1x | 4.47 (n 6) | 5.65 (n 116) | 0.90 |
| ppm_2x | 10.68 (n 4) | 12.20 (n 116) | - |
| own_half | 0.390 (n 6) | 0.290 (n 116) | -0.85 |
| bridge | 0.529 (n 6) | 0.671 (n 116) | 1.07 |
| our_half | 0.081 (n 6) | 0.039 (n 116) | -0.61 |
| first_tick | 346.67 (n 6) | 315.17 (n 116) | -0.18 |
| react_s | 5.92 (n 6) | 4.53 (n 116) | -1.53 |
| react_3s | 0.282 (n 6) | 0.481 (n 116) | 1.52 |
| react_lift | -0.05 (n 6) | 0.07 (n 116) | 1.30 |
| push_mean | 3.61 (n 6) | 4.06 (n 116) | 0.79 |
| push_max | 10.33 (n 6) | 10.14 (n 116) | -0.13 |
| spell_share | 0.081 (n 6) | 0.057 (n 116) | -0.29 |
| opp_el | 7.27 (n 6) | 7.02 (n 116) | -0.24 |

## 4. Detector blind spots, measured on the SIM exact plays (primary SIM)

- exact opponent plays 38864; the detector (live code) finds 30760 = 79.1%
- non-spell plays: 29528/30230 = 97.7% found
- spell plays: 1232/8634 = 14.3% found (22.2% of all SIM plays are spells; live sees only the body-dropping ones)
- SIM opponent elixir at play: true 5.48 (mean, exact) vs the public counter 6.79 (last decision before the play). The counter is a +26-tick forecast and never charges invisible spells, so it reads far above the truth; the known pure bias of the live counter is +0.34 (econ_sim_patch.py). `opp_el` is therefore comparable counter-to-counter (live vs SIM), NOT to true elixir, and it drifts up with every invisible spell the opponent casts (SIM opponents cast many).

