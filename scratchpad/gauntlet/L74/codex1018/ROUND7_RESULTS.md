# Round 7: paired readout against FIN12

SIM fight parity, not candidate win rate. CIs resample whole matches in pairs (2,000 draws, seed 0), using the existing strict-fight and card-agreement definitions. Completed affected-match files replace the matching FIN12 files, as in diag_night/r5c/cmp.py. Positive deltas are percentage points of raw agreement. These are correlated exploratory arms, without multiple-comparison correction. A statistical gain alone is not a verifier land verdict.

| Arm | Cohort | Raw agreement [95% CI] | Delta pp [paired 95% CI] | Up / down | Fights |
|---|---|---|---|---|---|
| S-EK-HITTICK | full | 0.9191 [0.9137, 0.9245] | +0.033 [-0.011, +0.080] | 16 / 8 | 16506 |
| S-EK-HITTICK | upgraded | 0.9255 [0.9179, 0.9325] | +0.045 [-0.023, +0.117] | 8 / 4 | 8858 |
| S-PULSE-TWICE | full | 0.9188 [0.9134, 0.9242] | +0.002 [+0.000, +0.007] | 1 / 0 | 16506 |
| S-PULSE-TWICE | upgraded | 0.9251 [0.9176, 0.9319] | +0.004 [+0.000, +0.013] | 1 / 0 | 8858 |
| H-FIXED-AIM v1 | full | 0.9187 [0.9133, 0.9241] | -0.006 [-0.019, +0.000] | 0 / 1 | 16506 |
| H-FIXED-AIM v1 | upgraded | 0.9250 [0.9176, 0.9319] | +0.000 [+0.000, +0.000] | 0 / 0 | 8858 |
| H-FIXED-AIM v2 | full | 0.9193 [0.9140, 0.9247] | +0.052 [+0.012, +0.105] | 9 / 0 | 16507 |
| H-FIXED-AIM v2 | upgraded | 0.9255 [0.9180, 0.9327] | +0.051 [+0.000, +0.141] | 5 / 0 | 8858 |
| r7c joint | full | 0.9197 [0.9143, 0.9250] | +0.088 [+0.026, +0.158] | 26 / 8 | 16507 |
| r7c joint | upgraded | 0.9260 [0.9184, 0.9331] | +0.100 [+0.008, +0.220] | 14 / 4 | 8858 |
| H-VOLLEY | full | 0.9193 [0.9140, 0.9247] | +0.052 [+0.012, +0.105] | 9 / 0 | 16507 |
| H-VOLLEY | upgraded | 0.9255 [0.9180, 0.9327] | +0.051 [+0.000, +0.141] | 5 / 0 | 8858 |
| H-TPL-ANYBODY | full | 0.9188 [0.9135, 0.9241] | +0.004 [-0.028, +0.037] | 5 / 6 | 16506 |
| H-TPL-ANYBODY | upgraded | 0.9250 [0.9175, 0.9320] | -0.004 [-0.049, +0.043] | 2 / 3 | 8858 |
| H-CUBE-DATE v1 | full | 0.9196 [0.9142, 0.9248] | +0.076 [+0.019, +0.140] | 47 / 25 | 16511 |
| H-CUBE-DATE v1 | upgraded | 0.9258 [0.9183, 0.9327] | +0.080 [-0.004, +0.176] | 23 / 11 | 8858 |
| H-CUBE-DATE v2 (available shards) | full | 0.9193 [0.9139, 0.9246] | +0.046 [-0.018, +0.113] | 23 / 12 | 16505 |
| H-CUBE-DATE v2 (available shards) | upgraded | 0.9259 [0.9182, 0.9330] | +0.087 [-0.034, +0.213] | 23 / 12 | 8857 |
| H-VOLLEY + H-CUBE-DATE v2 | full | 0.9203 [0.9150, 0.9257] | +0.151 [+0.053, +0.255] | 60 / 26 | 16511 |
| H-VOLLEY + H-CUBE-DATE v2 | upgraded | 0.9268 [0.9192, 0.9341] | +0.174 [+0.015, +0.342] | 32 / 12 | 8857 |
| H-NEGHP | full | 0.9177 [0.9122, 0.9230] | -0.110 [-0.188, -0.044] | 0 / 0 | 16729 |
| H-NEGHP | upgraded | 0.9243 [0.9169, 0.9313] | -0.071 [-0.158, +0.004] | 0 / 0 | 8993 |
| S-EVOWITCH-CLOCK | full | 0.9189 [0.9134, 0.9242] | +0.006 [+0.000, +0.019] | 1 / 0 | 16506 |
| S-EVOWITCH-CLOCK | upgraded | 0.9250 [0.9176, 0.9319] | +0.000 [+0.000, +0.000] | 0 / 0 | 8858 |
| verifier H-VOLLEY | full | 0.9193 [0.9140, 0.9247] | +0.052 [+0.012, +0.105] | 9 / 0 | 16507 |
| verifier H-VOLLEY | upgraded | 0.9255 [0.9180, 0.9327] | +0.051 [+0.000, +0.141] | 5 / 0 | 8858 |
| verifier H-FIXED-AIM v2 | full | 0.9193 [0.9140, 0.9247] | +0.052 [+0.012, +0.105] | 9 / 0 | 16507 |
| verifier H-FIXED-AIM v2 | upgraded | 0.9255 [0.9180, 0.9327] | +0.051 [+0.000, +0.141] | 5 / 0 | 8858 |
| verifier S-PULSE-TWICE | full | 0.9188 [0.9134, 0.9242] | +0.002 [+0.000, +0.007] | 1 / 0 | 16506 |
| verifier S-PULSE-TWICE | upgraded | 0.9251 [0.9176, 0.9319] | +0.004 [+0.000, +0.013] | 1 / 0 | 8858 |
| verifier S-EK-HITTICK | full | 0.9191 [0.9137, 0.9245] | +0.033 [-0.011, +0.080] | 16 / 8 | 16506 |
| verifier S-EK-HITTICK | upgraded | 0.9255 [0.9179, 0.9325] | +0.045 [-0.023, +0.117] | 8 / 4 | 8858 |
| verifier joint | full | 0.9203 [0.9150, 0.9257] | +0.151 [+0.053, +0.255] | 60 / 26 | 16511 |
| verifier joint | upgraded | 0.9268 [0.9192, 0.9341] | +0.174 [+0.015, +0.342] | 32 / 12 | 8857 |
| verifier H-CUBE-DATE | full | 0.9198 [0.9144, 0.9252] | +0.099 [+0.013, +0.185] | 51 / 26 | 16510 |
| verifier H-CUBE-DATE | upgraded | 0.9263 [0.9185, 0.9333] | +0.123 [-0.015, +0.266] | 27 / 12 | 8857 |
| H-SNAP-BACK | full | 0.9195 [0.9140, 0.9246] | +0.066 [+0.001, +0.135] | 34 / 18 | 16509 |
| H-SNAP-BACK | upgraded | 0.9260 [0.9186, 0.9329] | +0.100 [+0.001, +0.199] | 15 / 5 | 8859 |
| H-PREROLL | full | 0.9206 [0.9151, 0.9259] | +0.175 [+0.035, +0.324] | 149 / 110 | 16508 |
| H-PREROLL | upgraded | 0.9267 [0.9187, 0.9337] | +0.163 [-0.061, +0.368] | 63 / 45 | 8861 |
| H-PREROLL + H-SNAP-BACK (upgraded arm only) | upgraded | 0.9271 [0.9194, 0.9339] | +0.206 [-0.038, +0.420] | 71 / 49 | 8862 |
| H-IW-PRESS-DATE v4 | full | 0.9196 [0.9141, 0.9250] | +0.078 [-0.022, +0.183] | 56 / 34 | 16522 |
| H-IW-PRESS-DATE v4 | upgraded | 0.9265 [0.9187, 0.9335] | +0.145 [+0.004, +0.297] | 29 / 12 | 8858 |
| H-IW-PRESS-DATE v5 | full | 0.9188 [0.9133, 0.9244] | +0.001 [-0.117, +0.118] | 57 / 46 | 16518 |
| H-IW-PRESS-DATE v5 | upgraded | 0.9256 [0.9179, 0.9330] | +0.056 [-0.105, +0.216] | 28 / 19 | 8856 |
| S-HOLD-REACH | full | 0.9191 [0.9137, 0.9243] | +0.031 [-0.001, +0.072] | 8 / 3 | 16506 |
| S-HOLD-REACH | upgraded | 0.9254 [0.9180, 0.9322] | +0.037 [-0.017, +0.103] | 5 / 2 | 8858 |
| verifier null | full | 0.9188 [0.9134, 0.9242] | +0.000 [+0.000, +0.000] | 0 / 0 | 16506 |
| verifier null | upgraded | 0.9250 [0.9176, 0.9319] | +0.000 [+0.000, +0.000] | 0 / 0 | 8858 |
| closer H-SNAP-BACK | full | 0.9195 [0.9140, 0.9246] | +0.066 [+0.001, +0.135] | 34 / 18 | 16509 |
| closer H-SNAP-BACK | upgraded | 0.9260 [0.9186, 0.9329] | +0.100 [+0.001, +0.199] | 15 / 5 | 8859 |
| closer S-HOLD-REACH | full | 0.9191 [0.9137, 0.9243] | +0.031 [-0.001, +0.072] | 8 / 3 | 16506 |
| closer S-HOLD-REACH | upgraded | 0.9254 [0.9180, 0.9322] | +0.037 [-0.017, +0.103] | 5 / 2 | 8858 |

H-FIXED-AIM v2 and H-VOLLEY address the same volley issue; do not add their gains. The two IW press-date approaches also overlap. The r7a joint was only run on the upgraded cohort; no full-cohort result is implied. The cube-v2 row uses the available finished shards and is not evidence of unseen shards. Fight eligibility and denominators can change between arms: for example, H-NEGHP has zero changed common-fight scores but a different fight count, so its raw-agreement delta is not a common-fight improvement. The paired intervals resample whole matches and retain those denominator changes.

Raw per-result tables below describe each result directory itself, which can be a subset or a shard. Compare populations before comparing their raw percentages. These are the original scorer CIs, not substituted for the paired full-cohort comparisons above.

| Pod / result directory | Cohort | Matches | Fights | Raw agreement [95% CI] |
|---|---|---:|---:|---|
| 19899 / v7c_hr | all | 492 | 16506 | 0.919 [0.914, 0.924] |
| 19899 / v7c_snap | all | 492 | 16509 | 0.919 [0.914, 0.925] |
| 19899 / FIN12 | all | 492 | 16506 | 0.919 [0.913, 0.924] |
| 19899 / r7a_J_st | all | 265 | 8862 | 0.927 [0.919, 0.934] |
| 19899 / r7a_P2_oth | all | 227 | 7647 | 0.913 [0.905, 0.922] |
| 19899 / r7a_P2_st | all | 265 | 8861 | 0.927 [0.919, 0.934] |
| 19899 / r7a_S2_oth | all | 187 | 6471 | 0.907 [0.899, 0.915] |
| 19899 / r7a_S2_st | all | 211 | 7435 | 0.923 [0.915, 0.931] |
| 19899 / r7b_hr | all | 492 | 16506 | 0.919 [0.914, 0.924] |
| 19899 / r7b_hr_stamped | stamped | 265 | 8858 | 0.925 [0.918, 0.932] |
| 19899 / r7b_pd | all | 492 | 16522 | 0.920 [0.914, 0.925] |
| 19899 / r7b_pd5 | all | 492 | 16518 | 0.919 [0.913, 0.924] |
| 19899 / r7b_pd5_stamped | stamped | 265 | 8856 | 0.926 [0.918, 0.933] |
| 19899 / r7b_pd_stamped | stamped | 265 | 8858 | 0.926 [0.919, 0.934] |
| 19899 / v7_r7b_null | all | 10 | 558 | 0.884 [0.857, 0.917] |
| 15617 / v7_r7c_ht_stamped | stamped | 265 | 8858 | 0.925 [0.918, 0.933] |
| 15617 / v7_r7d_cube_arm | all | 333 | 11638 | 0.916 [0.909, 0.923] |
| 15617 / v7_r7d_joint | all | 353 | 12432 | 0.918 [0.912, 0.925] |
| 15617 / v7_r7c_ht | all | 492 | 16506 | 0.919 [0.914, 0.924] |
| 15617 / r7c_fixaim | all | 110 | 4230 | 0.918 [0.908, 0.927] |
| 15617 / r7c_fixaim2 | all | 110 | 4231 | 0.920 [0.910, 0.929] |
| 15617 / r7c_ht | all | 492 | 16506 | 0.919 [0.914, 0.924] |
| 15617 / r7c_joint | all | 492 | 16507 | 0.920 [0.914, 0.925] |
| 15617 / r7c_pulse | all | 19 | 590 | 0.915 [0.883, 0.940] |
| 15617 / r7d_cube2_st0 | all | 89 | 2960 | 0.927 [0.914, 0.939] |
| 15617 / r7d_cube2_st1 | all | 89 | 3005 | 0.930 [0.917, 0.942] |
| 15617 / r7d_cube2_st20 | all | 22 | 647 | 0.931 [0.902, 0.957] |
| 15617 / r7d_cube2_st21 | all | 22 | 877 | 0.917 [0.894, 0.937] |
| 15617 / r7d_cube2_st22 | all | 21 | 666 | 0.912 [0.884, 0.942] |
| 15617 / r7d_cube_st0 | all | 89 | 2960 | 0.927 [0.915, 0.939] |
| 15617 / r7d_cube_st1 | all | 89 | 3007 | 0.929 [0.915, 0.941] |
| 15617 / r7d_cube_st2 | all | 87 | 2891 | 0.922 [0.908, 0.933] |
| 15617 / r7d_cube_un0 | all | 76 | 2473 | 0.916 [0.904, 0.929] |
| 15617 / r7d_cube_un1 | all | 76 | 2732 | 0.916 [0.904, 0.929] |
| 15617 / r7d_cube_un2 | all | 75 | 2448 | 0.904 [0.888, 0.919] |
| 15617 / r7d_ewc | all | 85 | 2813 | 0.897 [0.882, 0.912] |
| 15617 / r7d_joint_st0 | all | 89 | 2960 | 0.927 [0.914, 0.939] |
| 15617 / r7d_joint_st1 | all | 89 | 3005 | 0.930 [0.917, 0.942] |
| 15617 / r7d_joint_st2 | all | 87 | 2892 | 0.923 [0.909, 0.935] |
| 15617 / r7d_joint_un0 | all | 76 | 2473 | 0.916 [0.904, 0.929] |
| 15617 / r7d_joint_un1 | all | 76 | 2732 | 0.917 [0.904, 0.929] |
| 15617 / r7d_joint_un2 | all | 75 | 2449 | 0.905 [0.889, 0.920] |
| 15617 / r7d_ng0 | all | 106 | 3687 | 0.906 [0.895, 0.918] |
| 15617 / r7d_ng1 | all | 106 | 3595 | 0.907 [0.894, 0.919] |
| 15617 / r7d_ng2 | all | 104 | 3613 | 0.908 [0.896, 0.920] |
| 15617 / r7d_tpl | all | 105 | 3775 | 0.911 [0.899, 0.924] |
| 15617 / r7d_vol | all | 53 | 2096 | 0.926 [0.914, 0.938] |
| 15617 / v7_r7c_fixaim | all | 492 | 16507 | 0.919 [0.914, 0.925] |
| 15617 / v7_r7c_pulse | all | 19 | 590 | 0.915 [0.883, 0.940] |
| 15617 / v7_r7c_pulse_rest | all | 473 | 15916 | 0.919 [0.913, 0.924] |
| 15617 / v7_r7d_vol | all | 53 | 2096 | 0.926 [0.914, 0.938] |
