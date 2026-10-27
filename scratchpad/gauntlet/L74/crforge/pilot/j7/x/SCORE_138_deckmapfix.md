arms: ['crforge_force', 'crforge_gate', 'fin15_force', 'fin16_force']; matches graded by every arm: 138; crashes: {'crforge_force': 0, 'crforge_gate': 0, 'fin15_force': 0, 'fin16_force': 0}

## subset all: 138 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.761 [0.688, 0.826] | 0.775 [0.703, 0.841] | 0.725 [0.652, 0.797] | 0.925 [0.906, 0.944] | 0.830 [0.779, 0.877] | 0.855 (n 138) | 54 / 10821 |
| crforge_gate | 0.681 [0.601, 0.761] | 0.696 [0.616, 0.768] | 0.659 [0.580, 0.732] | 0.904 [0.881, 0.927] | 0.797 [0.739, 0.848] | 0.877 (n 138) | 219 / 10821 |
| fin15_force | 0.536 [0.457, 0.609] | 0.565 [0.478, 0.645] | 0.435 [0.355, 0.514] | 0.858 [0.838, 0.878] | 0.714 [0.663, 0.764] | 0.877 (n 138) | 1730 / 10822 |
| fin16_force | 0.536 [0.449, 0.616] | 0.572 [0.486, 0.652] | 0.464 [0.377, 0.543] | 0.879 [0.858, 0.899] | 0.728 [0.678, 0.779] | 0.862 (n 138) | 1476 / 10822 |
   paired crforge_force - fin15_force, seq: +0.225 [+0.152, +0.304]
   paired crforge_force - fin15_force, result: +0.210 [+0.138, +0.290]
   paired crforge_force - fin15_force, timing: +0.290 [+0.217, +0.362]
   paired crforge_force - fin16_force, seq: +0.225 [+0.145, +0.304]
   paired crforge_force - fin16_force, result: +0.203 [+0.123, +0.283]
   paired crforge_force - fin16_force, timing: +0.261 [+0.181, +0.341]
   paired crforge_gate - fin15_force, seq: +0.145 [+0.058, +0.232]
   paired crforge_gate - fin15_force, result: +0.130 [+0.043, +0.217]
   paired crforge_gate - fin15_force, timing: +0.225 [+0.130, +0.312]
   paired crforge_gate - fin16_force, seq: +0.145 [+0.051, +0.239]
   paired crforge_gate - fin16_force, result: +0.123 [+0.029, +0.217]
   paired crforge_gate - fin16_force, timing: +0.196 [+0.109, +0.290]

## subset no-flag: 109 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.798 [0.725, 0.872] | 0.817 [0.743, 0.890] | 0.789 [0.706, 0.862] | 0.950 [0.933, 0.965] | 0.867 [0.817, 0.917] | 0.844 (n 109) | 30 / 8399 |
| crforge_gate | 0.789 [0.716, 0.862] | 0.807 [0.734, 0.881] | 0.780 [0.706, 0.853] | 0.943 [0.926, 0.959] | 0.876 [0.826, 0.922] | 0.872 (n 109) | 61 / 8399 |
| fin15_force | 0.560 [0.459, 0.651] | 0.587 [0.486, 0.670] | 0.459 [0.367, 0.550] | 0.876 [0.854, 0.896] | 0.729 [0.670, 0.784] | 0.862 (n 109) | 1127 / 8400 |
| fin16_force | 0.550 [0.459, 0.642] | 0.578 [0.486, 0.661] | 0.486 [0.394, 0.578] | 0.902 [0.882, 0.921] | 0.739 [0.688, 0.789] | 0.881 (n 109) | 1020 / 8400 |
   paired crforge_force - fin15_force, seq: +0.239 [+0.147, +0.339]
   paired crforge_force - fin15_force, result: +0.229 [+0.138, +0.321]
   paired crforge_force - fin15_force, timing: +0.330 [+0.239, +0.422]
   paired crforge_force - fin16_force, seq: +0.248 [+0.156, +0.349]
   paired crforge_force - fin16_force, result: +0.239 [+0.147, +0.339]
   paired crforge_force - fin16_force, timing: +0.303 [+0.211, +0.404]
   paired crforge_gate - fin15_force, seq: +0.229 [+0.128, +0.330]
   paired crforge_gate - fin15_force, result: +0.220 [+0.119, +0.321]
   paired crforge_gate - fin15_force, timing: +0.321 [+0.220, +0.422]
   paired crforge_gate - fin16_force, seq: +0.239 [+0.147, +0.349]
   paired crforge_gate - fin16_force, result: +0.229 [+0.138, +0.339]
   paired crforge_gate - fin16_force, timing: +0.294 [+0.193, +0.394]

## subset all but opp-deal misfits: 113 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.805 [0.735, 0.876] | 0.823 [0.752, 0.894] | 0.788 [0.708, 0.858] | 0.951 [0.935, 0.966] | 0.872 [0.819, 0.916] | 0.841 (n 113) | 30 / 8776 |
| crforge_gate | 0.770 [0.690, 0.841] | 0.788 [0.717, 0.858] | 0.752 [0.673, 0.823] | 0.943 [0.926, 0.959] | 0.872 [0.823, 0.916] | 0.876 (n 113) | 74 / 8776 |
| fin15_force | 0.549 [0.451, 0.637] | 0.575 [0.478, 0.664] | 0.451 [0.363, 0.540] | 0.877 [0.856, 0.895] | 0.730 [0.673, 0.783] | 0.858 (n 113) | 1236 / 8777 |
| fin16_force | 0.549 [0.451, 0.637] | 0.575 [0.487, 0.664] | 0.487 [0.398, 0.575] | 0.902 [0.884, 0.920] | 0.748 [0.695, 0.796] | 0.876 (n 113) | 1071 / 8777 |
   paired crforge_force - fin15_force, seq: +0.257 [+0.168, +0.354]
   paired crforge_force - fin15_force, result: +0.248 [+0.159, +0.336]
   paired crforge_force - fin15_force, timing: +0.336 [+0.257, +0.425]
   paired crforge_force - fin16_force, seq: +0.257 [+0.168, +0.354]
   paired crforge_force - fin16_force, result: +0.248 [+0.159, +0.345]
   paired crforge_force - fin16_force, timing: +0.301 [+0.212, +0.389]
   paired crforge_gate - fin15_force, seq: +0.221 [+0.124, +0.319]
   paired crforge_gate - fin15_force, result: +0.212 [+0.124, +0.310]
   paired crforge_gate - fin15_force, timing: +0.301 [+0.204, +0.398]
   paired crforge_gate - fin16_force, seq: +0.221 [+0.115, +0.319]
   paired crforge_gate - fin16_force, result: +0.212 [+0.115, +0.310]
   paired crforge_gate - fin16_force, timing: +0.265 [+0.168, +0.363]

## subset opp-deal misfits only: 25 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.560 [0.360, 0.760] | 0.560 [0.360, 0.760] | 0.440 [0.240, 0.640] | 0.809 [0.742, 0.869] | 0.640 [0.520, 0.760] | 0.920 (n 25) | 24 / 2045 |
| crforge_gate | 0.280 [0.120, 0.480] | 0.280 [0.120, 0.480] | 0.240 [0.080, 0.440] | 0.730 [0.649, 0.805] | 0.460 [0.320, 0.600] | 0.880 (n 25) | 145 / 2045 |
| fin15_force | 0.480 [0.280, 0.680] | 0.520 [0.320, 0.720] | 0.360 [0.160, 0.560] | 0.777 [0.711, 0.834] | 0.640 [0.520, 0.760] | 0.960 (n 25) | 494 / 2045 |
| fin16_force | 0.480 [0.280, 0.680] | 0.560 [0.360, 0.760] | 0.360 [0.200, 0.560] | 0.775 [0.708, 0.833] | 0.640 [0.520, 0.760] | 0.800 (n 25) | 405 / 2045 |
   paired crforge_force - fin15_force, seq: +0.080 [+0.000, +0.200]
   paired crforge_force - fin15_force, result: +0.040 [-0.080, +0.160]
   paired crforge_force - fin15_force, timing: +0.080 [+0.000, +0.200]
   paired crforge_force - fin16_force, seq: +0.080 [+0.000, +0.200]
   paired crforge_force - fin16_force, result: +0.000 [-0.160, +0.160]
   paired crforge_force - fin16_force, timing: +0.080 [+0.000, +0.200]
   paired crforge_gate - fin15_force, seq: -0.200 [-0.440, +0.000]
   paired crforge_gate - fin15_force, result: -0.240 [-0.440, -0.040]
   paired crforge_gate - fin15_force, timing: -0.120 [-0.320, +0.080]
   paired crforge_gate - fin16_force, seq: -0.200 [-0.400, +0.000]
   paired crforge_gate - fin16_force, result: -0.280 [-0.480, -0.080]
   paired crforge_gate - fin16_force, timing: -0.120 [-0.320, +0.080]

## subset live >= 1 tower fall: 95 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.800 [0.716, 0.884] | 0.821 [0.737, 0.895] | 0.747 [0.653, 0.832] | 0.930 [0.908, 0.951] | 0.832 [0.763, 0.889] | 0.853 (n 95) | 28 / 5864 |
| crforge_gate | 0.737 [0.642, 0.821] | 0.758 [0.674, 0.842] | 0.705 [0.611, 0.789] | 0.912 [0.883, 0.938] | 0.805 [0.737, 0.868] | 0.863 (n 95) | 133 / 5864 |
| fin15_force | 0.568 [0.474, 0.663] | 0.611 [0.516, 0.705] | 0.421 [0.316, 0.516] | 0.866 [0.843, 0.889] | 0.632 [0.568, 0.695] | 0.895 (n 95) | 593 / 5865 |
| fin16_force | 0.558 [0.453, 0.653] | 0.611 [0.505, 0.705] | 0.453 [0.347, 0.547] | 0.890 [0.867, 0.913] | 0.653 [0.595, 0.711] | 0.895 (n 95) | 444 / 5865 |
   paired crforge_force - fin15_force, seq: +0.232 [+0.137, +0.326]
   paired crforge_force - fin15_force, result: +0.211 [+0.116, +0.305]
   paired crforge_force - fin15_force, timing: +0.326 [+0.232, +0.421]
   paired crforge_force - fin16_force, seq: +0.242 [+0.137, +0.347]
   paired crforge_force - fin16_force, result: +0.211 [+0.105, +0.316]
   paired crforge_force - fin16_force, timing: +0.295 [+0.211, +0.389]
   paired crforge_gate - fin15_force, seq: +0.168 [+0.053, +0.284]
   paired crforge_gate - fin15_force, result: +0.147 [+0.042, +0.263]
   paired crforge_gate - fin15_force, timing: +0.284 [+0.179, +0.400]
   paired crforge_gate - fin16_force, seq: +0.179 [+0.063, +0.295]
   paired crforge_gate - fin16_force, result: +0.147 [+0.032, +0.263]
   paired crforge_gate - fin16_force, timing: +0.253 [+0.147, +0.358]

## refusals and first divergence
- crforge_force: refused {'gate_4': 38, 'ability_no_unit': 10, 'not_placed': 2, 'step_crash:UnsupportedOperationException': 2, 'before_tick_21': 1, 'queue:IllegalArgumentException': 1}; first tower divergence in 85/138 matches, median tick 2168
- crforge_gate: refused {'gate_9': 147, 'gate_4': 43, 'gate_13': 13, 'ability_no_unit': 10, 'not_placed': 2, 'step_crash:UnsupportedOperationException': 2, 'before_tick_21': 1, 'queue:IllegalArgumentException': 1}; first tower divergence in 89/138 matches, median tick 2111
- fin15_force: refused {'never_run_after_end': 1548, 'ability:NO_HERO': 68, 'ability:ABILITY_SPENT': 41, 'OUT_OF_TERRITORY': 34, 'NO_DEPLOY': 20, 'reset_forms_dropped_1:ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effe': 6, 'reset_forms_dropped_2:ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effe': 6, 'play_crash:ValueError': 2}; first tower divergence in 127/138 matches, median tick 1627
- fin16_force: refused {'never_run_after_end': 1299, 'ability:NO_HERO': 68, 'ability:ABILITY_SPENT': 42, 'OUT_OF_TERRITORY': 28, 'NO_DEPLOY': 20, 'reset_forms_dropped_1:ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effe': 6, 'reset_forms_dropped_2:ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effe': 6, 'play_crash:ValueError': 2}; first tower divergence in 119/138 matches, median tick 2236
