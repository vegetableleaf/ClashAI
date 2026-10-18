# Candidate SIM comparisons

Reference: ICEBOW Mark CLIII: LEVELS, grafted checkpoint edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952. Standard seeds 741200+742000 and fresh seeds 743000+744000; 960 paired games each. The existing live_cmp / validate.paired_drift method uses 10,000 paired bootstrap draws within census and learner side. Draws count as non-wins. No live conclusions or deployment follow from these scores.

| Evaluation context | Candidate arm | Seed set | Wins / games | Win rate % [Wilson 95% CI] | CLIII wins | Delta vs CLIII, pp [paired 95% CI] |
|---|---|---|---|---|---|---|
| cue_same_code | cue_ab2_sample | std | 692/960 | 72.08 [69.16, 74.83] | 642/960 | +5.21 [+1.67, +8.85] |
| cue_same_code | cue_ab2_sample | fresh | 638/960 | 66.46 [63.41, 69.37] | 626/960 | +1.25 [-2.19, +4.69] |
| cue_same_code | cue_ab2_sample | pooled | 1330/1920 | 69.27 [67.17, 71.29] | 1268/1920 | +3.23 [+0.73, +5.68] |
| cue_same_code | cue_ab2 | std | 687/960 | 71.56 [68.63, 74.33] | 642/960 | +4.69 [+1.15, +8.23] |
| cue_same_code | cue_ab2 | fresh | 646/960 | 67.29 [64.26, 70.19] | 626/960 | +2.08 [-1.36, +5.52] |
| cue_same_code | cue_ab2 | pooled | 1333/1920 | 69.43 [67.33, 71.45] | 1268/1920 | +3.39 [+0.94, +5.83] |
| c3_same_code | c3_ab | std | pending | unavailable | unavailable | no complete paired result |
| c3_same_code | c3_ab | fresh | pending | unavailable | unavailable | no complete paired result |
| c3_same_code | c3_ctl | std | 653/960 | 68.02 [65.00, 70.89] | 642/960 | +1.15 [-2.40, +4.69] |
| c3_same_code | c3_ctl | fresh | 642/960 | 66.88 [63.84, 69.78] | 626/960 | +1.67 [-1.77, +5.00] |
| c3_same_code | c3_ctl | pooled | 1295/1920 | 67.45 [65.32, 69.51] | 1268/1920 | +1.41 [-1.04, +3.80] |
| combo_off | combo_ctl_c3 | std | 624/960 | 65.00 [61.93, 67.95] | 642/960 | -1.88 [-5.52, +1.67] |
| combo_off | combo_ctl_c3 | fresh | 619/960 | 64.48 [61.40, 67.44] | 626/960 | -0.73 [-4.06, +2.60] |
| combo_off | combo_ctl_c3 | pooled | 1243/1920 | 64.74 [62.57, 66.85] | 1268/1920 | -1.30 [-3.75, +1.20] |
| combo_off | combo_rew_c3 | std | 637/960 | 66.35 [63.31, 69.27] | 642/960 | -0.52 [-4.06, +2.92] |
| combo_off | combo_rew_c3 | fresh | 613/960 | 63.85 [60.77, 66.83] | 626/960 | -1.35 [-4.79, +2.08] |
| combo_off | combo_rew_c3 | pooled | 1250/1920 | 65.10 [62.94, 67.20] | 1268/1920 | -0.94 [-3.33, +1.51] |
| combo_offc | combo_ctl_c3 | std | 625/960 | 65.10 [62.03, 68.05] | 643/960 | -1.88 [-5.52, +1.67] |
| combo_offc | combo_ctl_c3 | fresh | 616/960 | 64.17 [61.08, 67.14] | 624/960 | -0.83 [-4.27, +2.50] |
| combo_offc | combo_ctl_c3 | pooled | 1241/1920 | 64.64 [62.47, 66.74] | 1267/1920 | -1.35 [-3.80, +1.15] |
| combo_offc | combo_rew_c3 | std | 636/960 | 66.25 [63.20, 69.17] | 643/960 | -0.73 [-4.27, +2.71] |
| combo_offc | combo_rew_c3 | fresh | 610/960 | 63.54 [60.45, 66.53] | 624/960 | -1.46 [-4.90, +2.08] |
| combo_offc | combo_rew_c3 | pooled | 1246/1920 | 64.90 [62.73, 67.00] | 1267/1920 | -1.09 [-3.44, +1.35] |

The cue rerun uses the frozen C3 source and pinned fork36 SIM with both models evaluated in the same isolated environment. That pod has PyTorch 2.8.0; the original training/evaluation pods use 2.11.0, so original and rerun rows are kept separate. The original cue_ab2 archive used different evaluation code and is excluded from the promotion comparisons. C3 control/reference and combo control/reward public evaluation identities agree at all 21 checked paths, including matching absent optional files. The combo offc rows include the existing combo-rule setting; off rows are the historical promotion protocol. The added fresh offc follow-up uses the same frozen combo tree and settings as the original standard offc runs.

Each confidence interval is nominal. Arms are correlated, and no multiple-comparison correction has been applied. Pooled results are descriptive; they do not replace the requirement for a positive lower paired CI on both standard and fresh sets. A SIM pass is a candidate finding, with no demonstrated transfer to live.

## CLIII reference results

| Context | Seed set | Wins / games | Win rate % [Wilson 95% CI] |
|---|---|---|---|
| cue_same_code | std | 642/960 | 66.88 [63.84, 69.78] |
| cue_same_code | fresh | 626/960 | 65.21 [62.14, 68.16] |
| c3_same_code | std | 642/960 | 66.88 [63.84, 69.78] |
| c3_same_code | fresh | 626/960 | 65.21 [62.14, 68.16] |
| combo_off | std | 642/960 | 66.88 [63.84, 69.78] |
| combo_off | fresh | 626/960 | 65.21 [62.14, 68.16] |
| combo_offc | std | 643/960 | 66.98 [63.94, 69.88] |
| combo_offc | fresh | 624/960 | 65.00 [61.93, 67.95] |

## Recorded behavior

Counts use the existing habit log and accepted-press records. Deltas resample matched games within census and learner side (2,000 draws). More presses or spells are not automatically better; these are behavior checks, not causal quality scores. Where available, presses_froze counts presses followed by at least one frozen enemy within the existing two-second observation; frozen_elixir is the catalogue elixir value of frozen enemies, not a causal economic reward.

| Context / candidate | Seeds | Metric | CLIII / candidate mean | Delta [paired 95% CI] |
|---|---|---|---|---|
| cue_same_code / cue_ab2_sample | std | accepted_ability_presses_per_game | 1.718 / 0.930 | -0.787 [-0.903, -0.682] |
| cue_same_code / cue_ab2_sample | std | rocket_per_game | 0.613 / 0.596 | -0.017 [-0.084, +0.046] |
| cue_same_code / cue_ab2_sample | std | tornado_per_game | 1.075 / 1.067 | -0.008 [-0.102, +0.087] |
| cue_same_code / cue_ab2_sample | std | presses_froze_per_game | 1.172 / 0.698 | -0.474 [-0.564, -0.385] |
| cue_same_code / cue_ab2_sample | std | frozen_elixir_per_game | 8.265 / 5.403 | -2.862 [-3.634, -2.110] |
| cue_same_code / cue_ab2_sample | fresh | accepted_ability_presses_per_game | 1.700 / 0.948 | -0.752 [-0.874, -0.635] |
| cue_same_code / cue_ab2_sample | fresh | rocket_per_game | 0.572 / 0.552 | -0.020 [-0.082, +0.040] |
| cue_same_code / cue_ab2_sample | fresh | tornado_per_game | 1.157 / 1.155 | -0.002 [-0.100, +0.102] |
| cue_same_code / cue_ab2_sample | fresh | presses_froze_per_game | 1.148 / 0.681 | -0.467 [-0.567, -0.375] |
| cue_same_code / cue_ab2_sample | fresh | frozen_elixir_per_game | 7.924 / 5.040 | -2.884 [-3.690, -2.147] |
| cue_same_code / cue_ab2 | std | accepted_ability_presses_per_game | 1.718 / 0.334 | -1.383 [-1.489, -1.283] |
| cue_same_code / cue_ab2 | std | rocket_per_game | 0.613 / 0.559 | -0.053 [-0.117, +0.009] |
| cue_same_code / cue_ab2 | std | tornado_per_game | 1.075 / 1.079 | +0.004 [-0.098, +0.103] |
| cue_same_code / cue_ab2 | std | presses_froze_per_game | 1.172 / 0.257 | -0.915 [-0.997, -0.837] |
| cue_same_code / cue_ab2 | std | frozen_elixir_per_game | 8.265 / 2.302 | -5.963 [-6.674, -5.310] |
| cue_same_code / cue_ab2 | fresh | accepted_ability_presses_per_game | 1.700 / 0.329 | -1.371 [-1.483, -1.261] |
| cue_same_code / cue_ab2 | fresh | rocket_per_game | 0.572 / 0.565 | -0.007 [-0.073, +0.054] |
| cue_same_code / cue_ab2 | fresh | tornado_per_game | 1.157 / 1.133 | -0.024 [-0.131, +0.075] |
| cue_same_code / cue_ab2 | fresh | presses_froze_per_game | 1.148 / 0.251 | -0.897 [-0.982, -0.812] |
| cue_same_code / cue_ab2 | fresh | frozen_elixir_per_game | 7.924 / 2.166 | -5.758 [-6.494, -5.072] |
| c3_same_code / c3_ctl | std | accepted_ability_presses_per_game | 1.718 / 1.698 | -0.020 [-0.142, +0.101] |
| c3_same_code / c3_ctl | std | rocket_per_game | 0.613 / 0.507 | -0.105 [-0.171, -0.041] |
| c3_same_code / c3_ctl | std | tornado_per_game | 1.075 / 1.039 | -0.036 [-0.136, +0.070] |
| c3_same_code / c3_ctl | std | presses_froze_per_game | 1.172 / 1.121 | -0.051 [-0.153, +0.046] |
| c3_same_code / c3_ctl | std | frozen_elixir_per_game | 8.265 / 7.602 | -0.663 [-1.458, +0.146] |
| c3_same_code / c3_ctl | fresh | accepted_ability_presses_per_game | 1.700 / 1.810 | +0.110 [-0.014, +0.237] |
| c3_same_code / c3_ctl | fresh | rocket_per_game | 0.572 / 0.486 | -0.085 [-0.147, -0.025] |
| c3_same_code / c3_ctl | fresh | tornado_per_game | 1.157 / 1.185 | +0.028 [-0.073, +0.130] |
| c3_same_code / c3_ctl | fresh | presses_froze_per_game | 1.148 / 1.209 | +0.061 [-0.040, +0.158] |
| c3_same_code / c3_ctl | fresh | frozen_elixir_per_game | 7.924 / 8.293 | +0.369 [-0.436, +1.140] |
| combo_off / combo_ctl_c3 | std | accepted_ability_presses_per_game | 1.718 / 1.621 | -0.097 [-0.215, +0.022] |
| combo_off / combo_ctl_c3 | std | rocket_per_game | 0.613 / 0.503 | -0.109 [-0.178, -0.042] |
| combo_off / combo_ctl_c3 | std | tornado_per_game | 1.075 / 1.084 | +0.009 [-0.084, +0.106] |
| combo_off / combo_ctl_c3 | fresh | accepted_ability_presses_per_game | 1.700 / 1.610 | -0.090 [-0.205, +0.025] |
| combo_off / combo_ctl_c3 | fresh | rocket_per_game | 0.572 / 0.504 | -0.068 [-0.131, -0.009] |
| combo_off / combo_ctl_c3 | fresh | tornado_per_game | 1.157 / 1.092 | -0.066 [-0.171, +0.030] |
| combo_off / combo_rew_c3 | std | accepted_ability_presses_per_game | 1.718 / 1.752 | +0.034 [-0.089, +0.144] |
| combo_off / combo_rew_c3 | std | rocket_per_game | 0.613 / 0.599 | -0.014 [-0.079, +0.052] |
| combo_off / combo_rew_c3 | std | tornado_per_game | 1.075 / 0.825 | -0.250 [-0.338, -0.160] |
| combo_off / combo_rew_c3 | fresh | accepted_ability_presses_per_game | 1.700 / 1.765 | +0.065 [-0.056, +0.191] |
| combo_off / combo_rew_c3 | fresh | rocket_per_game | 0.572 / 0.554 | -0.018 [-0.079, +0.043] |
| combo_off / combo_rew_c3 | fresh | tornado_per_game | 1.157 / 0.916 | -0.242 [-0.332, -0.151] |
| combo_offc / combo_ctl_c3 | std | accepted_ability_presses_per_game | 1.699 / 1.627 | -0.072 [-0.189, +0.048] |
| combo_offc / combo_ctl_c3 | std | rocket_per_game | 0.682 / 0.544 | -0.139 [-0.207, -0.070] |
| combo_offc / combo_ctl_c3 | std | tornado_per_game | 1.125 / 1.129 | +0.004 [-0.085, +0.100] |
| combo_offc / combo_ctl_c3 | fresh | accepted_ability_presses_per_game | 1.679 / 1.621 | -0.058 [-0.176, +0.059] |
| combo_offc / combo_ctl_c3 | fresh | rocket_per_game | 0.637 / 0.554 | -0.083 [-0.148, -0.020] |
| combo_offc / combo_ctl_c3 | fresh | tornado_per_game | 1.235 / 1.150 | -0.085 [-0.190, +0.014] |
| combo_offc / combo_rew_c3 | std | accepted_ability_presses_per_game | 1.699 / 1.721 | +0.022 [-0.091, +0.136] |
| combo_offc / combo_rew_c3 | std | rocket_per_game | 0.682 / 0.732 | +0.050 [-0.019, +0.122] |
| combo_offc / combo_rew_c3 | std | tornado_per_game | 1.125 / 0.952 | -0.173 [-0.267, -0.077] |
| combo_offc / combo_rew_c3 | fresh | accepted_ability_presses_per_game | 1.679 / 1.742 | +0.062 [-0.070, +0.185] |
| combo_offc / combo_rew_c3 | fresh | rocket_per_game | 0.637 / 0.689 | +0.051 [-0.015, +0.119] |
| combo_offc / combo_rew_c3 | fresh | tornado_per_game | 1.235 / 1.048 | -0.188 [-0.282, -0.090] |

## Original archived results

These completed runs are retained with their own win-rate intervals. Cue and C3 used different evaluation code, so their totals are not a valid paired comparison against each other.

| Archive | Seed set | Wins / games | Win rate % [Wilson 95% CI] |
|---|---|---|---|
| original cue / cue_ab2 | standard | 687/960 | 71.56 [68.63, 74.33] |
| original cue / cue_ab2_sample | standard | 692/960 | 72.08 [69.16, 74.83] |
| C3 reference / clIII_ref | standard | 642/960 | 66.88 [63.84, 69.78] |
| C3 reference / clIII_ref | fresh | 626/960 | 65.21 [62.14, 68.16] |
| combo off / combo_ctl_c3 | standard | 624/960 | 65.00 [61.93, 67.95] |
| combo offc / combo_ctl_c3 | standard | 625/960 | 65.10 [62.03, 68.05] |
| combo off / combo_rew_c3 | standard | 637/960 | 66.35 [63.31, 69.27] |
| combo offc / combo_rew_c3 | standard | 636/960 | 66.25 [63.20, 69.17] |
