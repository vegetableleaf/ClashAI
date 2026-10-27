arms: ['crforge_force', 'crforge_gate', 'fin15_force', 'fin16_force']; matches graded by every arm: 138; crashes: {'crforge_force': 0, 'crforge_gate': 0, 'fin15_force': 0, 'fin16_force': 0}

## subset all: 138 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.761 [0.688, 0.826] | 0.775 [0.703, 0.841] | 0.725 [0.652, 0.797] | 0.925 [0.906, 0.944] | 0.830 [0.779, 0.877] | 0.855 (n 138) | 54 / 10821 |
| crforge_gate | 0.681 [0.601, 0.761] | 0.696 [0.616, 0.768] | 0.659 [0.580, 0.732] | 0.904 [0.881, 0.927] | 0.797 [0.739, 0.848] | 0.877 (n 138) | 219 / 10821 |
| fin15_force | 0.522 [0.442, 0.601] | 0.558 [0.478, 0.638] | 0.420 [0.341, 0.500] | 0.842 [0.820, 0.863] | 0.692 [0.634, 0.746] | 0.891 (n 138) | 1801 / 10822 |
| fin16_force | 0.522 [0.435, 0.609] | 0.558 [0.471, 0.645] | 0.449 [0.362, 0.529] | 0.859 [0.834, 0.881] | 0.703 [0.645, 0.757] | 0.891 (n 138) | 1588 / 10822 |
   paired crforge_force - fin15_force, seq: +0.239 [+0.159, +0.312]
   paired crforge_force - fin15_force, result: +0.217 [+0.138, +0.290]
   paired crforge_force - fin15_force, timing: +0.304 [+0.225, +0.377]
   paired crforge_force - fin16_force, seq: +0.239 [+0.167, +0.319]
   paired crforge_force - fin16_force, result: +0.217 [+0.138, +0.304]
   paired crforge_force - fin16_force, timing: +0.275 [+0.196, +0.355]
   paired crforge_gate - fin15_force, seq: +0.159 [+0.065, +0.254]
   paired crforge_gate - fin15_force, result: +0.138 [+0.051, +0.232]
   paired crforge_gate - fin15_force, timing: +0.239 [+0.145, +0.333]
   paired crforge_gate - fin16_force, seq: +0.159 [+0.065, +0.254]
   paired crforge_gate - fin16_force, result: +0.138 [+0.043, +0.232]
   paired crforge_gate - fin16_force, timing: +0.210 [+0.116, +0.304]

## subset no-flag: 109 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.798 [0.725, 0.872] | 0.817 [0.743, 0.890] | 0.789 [0.706, 0.862] | 0.950 [0.933, 0.965] | 0.867 [0.817, 0.917] | 0.844 (n 109) | 30 / 8399 |
| crforge_gate | 0.789 [0.716, 0.862] | 0.807 [0.734, 0.881] | 0.780 [0.706, 0.853] | 0.943 [0.926, 0.959] | 0.876 [0.826, 0.922] | 0.872 (n 109) | 61 / 8399 |
| fin15_force | 0.523 [0.431, 0.615] | 0.560 [0.468, 0.651] | 0.422 [0.330, 0.514] | 0.860 [0.834, 0.883] | 0.706 [0.642, 0.771] | 0.881 (n 109) | 1260 / 8400 |
| fin16_force | 0.523 [0.431, 0.615] | 0.550 [0.459, 0.633] | 0.459 [0.367, 0.550] | 0.882 [0.856, 0.905] | 0.711 [0.651, 0.771] | 0.908 (n 109) | 1149 / 8400 |
   paired crforge_force - fin15_force, seq: +0.275 [+0.183, +0.376]
   paired crforge_force - fin15_force, result: +0.257 [+0.165, +0.358]
   paired crforge_force - fin15_force, timing: +0.367 [+0.275, +0.459]
   paired crforge_force - fin16_force, seq: +0.275 [+0.183, +0.376]
   paired crforge_force - fin16_force, result: +0.266 [+0.174, +0.367]
   paired crforge_force - fin16_force, timing: +0.330 [+0.239, +0.422]
   paired crforge_gate - fin15_force, seq: +0.266 [+0.165, +0.367]
   paired crforge_gate - fin15_force, result: +0.248 [+0.147, +0.349]
   paired crforge_gate - fin15_force, timing: +0.358 [+0.257, +0.459]
   paired crforge_gate - fin16_force, seq: +0.266 [+0.165, +0.376]
   paired crforge_gate - fin16_force, result: +0.257 [+0.156, +0.367]
   paired crforge_gate - fin16_force, timing: +0.321 [+0.220, +0.422]

## subset all but opp-deal misfits: 113 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.805 [0.735, 0.876] | 0.823 [0.752, 0.894] | 0.788 [0.708, 0.858] | 0.951 [0.935, 0.966] | 0.872 [0.819, 0.916] | 0.841 (n 113) | 30 / 8776 |
| crforge_gate | 0.770 [0.690, 0.841] | 0.788 [0.717, 0.858] | 0.752 [0.673, 0.823] | 0.943 [0.926, 0.959] | 0.872 [0.823, 0.916] | 0.876 (n 113) | 74 / 8776 |
| fin15_force | 0.522 [0.425, 0.611] | 0.558 [0.460, 0.646] | 0.425 [0.336, 0.513] | 0.860 [0.837, 0.882] | 0.708 [0.646, 0.765] | 0.876 (n 113) | 1335 / 8777 |
| fin16_force | 0.531 [0.434, 0.619] | 0.558 [0.460, 0.646] | 0.469 [0.381, 0.558] | 0.882 [0.859, 0.904] | 0.721 [0.659, 0.774] | 0.903 (n 113) | 1167 / 8777 |
   paired crforge_force - fin15_force, seq: +0.283 [+0.195, +0.381]
   paired crforge_force - fin15_force, result: +0.265 [+0.177, +0.363]
   paired crforge_force - fin15_force, timing: +0.363 [+0.274, +0.451]
   paired crforge_force - fin16_force, seq: +0.274 [+0.177, +0.372]
   paired crforge_force - fin16_force, result: +0.265 [+0.177, +0.363]
   paired crforge_force - fin16_force, timing: +0.319 [+0.221, +0.416]
   paired crforge_gate - fin15_force, seq: +0.248 [+0.150, +0.354]
   paired crforge_gate - fin15_force, result: +0.230 [+0.133, +0.336]
   paired crforge_gate - fin15_force, timing: +0.327 [+0.221, +0.434]
   paired crforge_gate - fin16_force, seq: +0.239 [+0.133, +0.345]
   paired crforge_gate - fin16_force, result: +0.230 [+0.124, +0.336]
   paired crforge_gate - fin16_force, timing: +0.283 [+0.177, +0.389]

## subset opp-deal misfits only: 25 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.560 [0.360, 0.760] | 0.560 [0.360, 0.760] | 0.440 [0.240, 0.640] | 0.809 [0.742, 0.869] | 0.640 [0.520, 0.760] | 0.920 (n 25) | 24 / 2045 |
| crforge_gate | 0.280 [0.120, 0.480] | 0.280 [0.120, 0.480] | 0.240 [0.080, 0.440] | 0.730 [0.649, 0.805] | 0.460 [0.320, 0.600] | 0.880 (n 25) | 145 / 2045 |
| fin15_force | 0.520 [0.320, 0.720] | 0.560 [0.360, 0.760] | 0.400 [0.200, 0.600] | 0.758 [0.694, 0.816] | 0.620 [0.500, 0.740] | 0.960 (n 25) | 466 / 2045 |
| fin16_force | 0.480 [0.280, 0.680] | 0.560 [0.360, 0.760] | 0.360 [0.200, 0.560] | 0.755 [0.687, 0.816] | 0.620 [0.500, 0.740] | 0.840 (n 25) | 421 / 2045 |
   paired crforge_force - fin15_force, seq: +0.040 [+0.000, +0.120]
   paired crforge_force - fin15_force, result: +0.000 [-0.120, +0.120]
   paired crforge_force - fin15_force, timing: +0.040 [+0.000, +0.120]
   paired crforge_force - fin16_force, seq: +0.080 [+0.000, +0.200]
   paired crforge_force - fin16_force, result: +0.000 [-0.160, +0.160]
   paired crforge_force - fin16_force, timing: +0.080 [+0.000, +0.200]
   paired crforge_gate - fin15_force, seq: -0.240 [-0.480, +0.000]
   paired crforge_gate - fin15_force, result: -0.280 [-0.480, -0.080]
   paired crforge_gate - fin15_force, timing: -0.160 [-0.360, +0.040]
   paired crforge_gate - fin16_force, seq: -0.200 [-0.400, +0.000]
   paired crforge_gate - fin16_force, result: -0.280 [-0.480, -0.080]
   paired crforge_gate - fin16_force, timing: -0.120 [-0.320, +0.080]

## subset live >= 1 tower fall: 95 matches
| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |
|---|---|---|---|---|---|---|---|
| crforge_force | 0.800 [0.716, 0.884] | 0.821 [0.737, 0.895] | 0.747 [0.653, 0.832] | 0.930 [0.908, 0.951] | 0.832 [0.763, 0.889] | 0.853 (n 95) | 28 / 5864 |
| crforge_gate | 0.737 [0.642, 0.821] | 0.758 [0.674, 0.842] | 0.705 [0.611, 0.789] | 0.912 [0.883, 0.938] | 0.805 [0.737, 0.868] | 0.863 (n 95) | 133 / 5864 |
| fin15_force | 0.526 [0.432, 0.621] | 0.579 [0.484, 0.674] | 0.379 [0.284, 0.474] | 0.849 [0.823, 0.875] | 0.611 [0.542, 0.679] | 0.916 (n 95) | 675 / 5865 |
| fin16_force | 0.526 [0.432, 0.621] | 0.579 [0.484, 0.674] | 0.421 [0.316, 0.516] | 0.869 [0.841, 0.897] | 0.626 [0.563, 0.689] | 0.916 (n 95) | 517 / 5865 |
   paired crforge_force - fin15_force, seq: +0.274 [+0.179, +0.379]
   paired crforge_force - fin15_force, result: +0.242 [+0.137, +0.347]
   paired crforge_force - fin15_force, timing: +0.368 [+0.274, +0.474]
   paired crforge_force - fin16_force, seq: +0.274 [+0.168, +0.379]
   paired crforge_force - fin16_force, result: +0.242 [+0.137, +0.347]
   paired crforge_force - fin16_force, timing: +0.326 [+0.232, +0.421]
   paired crforge_gate - fin15_force, seq: +0.211 [+0.095, +0.337]
   paired crforge_gate - fin15_force, result: +0.179 [+0.063, +0.295]
   paired crforge_gate - fin15_force, timing: +0.326 [+0.221, +0.442]
   paired crforge_gate - fin16_force, seq: +0.211 [+0.095, +0.326]
   paired crforge_gate - fin16_force, result: +0.179 [+0.063, +0.295]
   paired crforge_gate - fin16_force, timing: +0.284 [+0.168, +0.400]

## refusals and first divergence
- crforge_force: refused {'gate_4': 38, 'ability_no_unit': 10, 'not_placed': 2, 'step_crash:UnsupportedOperationException': 2, 'queue:IllegalArgumentException': 1, 'before_tick_21': 1}; first tower divergence in 85/138 matches, median tick 2168
- crforge_gate: refused {'gate_9': 147, 'gate_4': 43, 'gate_13': 13, 'ability_no_unit': 10, 'not_placed': 2, 'step_crash:UnsupportedOperationException': 2, 'queue:IllegalArgumentException': 1, 'before_tick_21': 1}; first tower divergence in 89/138 matches, median tick 2111
- fin15_force: refused {'never_run_after_end': 1601, 'ability:NO_HERO': 68, 'OUT_OF_TERRITORY': 53, 'ability:ABILITY_SPENT': 41, 'NO_DEPLOY': 20, 'reset_forms_dropped_1:ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effe': 6, 'reset_forms_dropped_2:ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effe': 6, 'WATER': 2}; first tower divergence in 128/138 matches, median tick 1490
- fin16_force: refused {'never_run_after_end': 1394, 'ability:NO_HERO': 67, 'OUT_OF_TERRITORY': 47, 'ability:ABILITY_SPENT': 42, 'NO_DEPLOY': 20, 'reset_forms_dropped_1:ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effe': 6, 'reset_forms_dropped_2:ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effe': 6, 'WATER': 2}; first tower divergence in 122/138 matches, median tick 1843
