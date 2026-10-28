# Persona fork test: trigger xbow_after_fail, 207 samples, 168 matches (opponent meta present in 207)

## again-wait  (mean dQ, 90% cluster CI; * = CI excludes 0)

| dimension | level | n | mean | 90% CI |
|---|---|---|---|---|
| aggression | aggression < 0.0 | 84 | -0.057 | [-0.116, +0.002] |
| aggression | aggression >= 0.0 | 73 | +0.009 | [-0.067, +0.082] |
| all | all | 157 | -0.026 | [-0.074, +0.020] |
| archetype | hyperbait | 23 | -0.120 * | [-0.202, -0.034] |
| archetype | other | 43 | -0.002 | [-0.110, +0.095] |
| archetype | royal_giant | 19 | +0.106 | [-0.067, +0.317] |
| archetype | weak_other | 49 | -0.024 | [-0.090, +0.048] |
| bank | bank < 2.0 | 83 | -0.033 | [-0.097, +0.032] |
| bank | bank >= 2.0 | 74 | -0.019 | [-0.084, +0.048] |
| lane_bias | lane_bias < 0.0 | 78 | -0.026 | [-0.100, +0.051] |
| lane_bias | lane_bias >= 0.0 | 79 | -0.027 | [-0.088, +0.035] |
| spell_delay | spell_delay < 2 | 61 | -0.051 | [-0.109, +0.010] |
| spell_delay | spell_delay >= 2 | 96 | -0.011 | [-0.080, +0.057] |
| temperature | temperature < 1.0 | 72 | -0.006 | [-0.073, +0.058] |
| temperature | temperature >= 1.0 | 85 | -0.043 | [-0.110, +0.024] |
| type | exploiter | 61 | -0.017 | [-0.080, +0.048] |
| type | exploiter_league | 52 | -0.036 | [-0.123, +0.040] |
| type | init | 24 | +0.001 | [-0.162, +0.173] |
| type | snapshot | 20 | -0.064 | [-0.164, +0.047] |

Half-vs-half differences (level A minus level B), 90% CI; sign change flagged:

| dimension | A | B | diff | 90% CI | sign change |
|---|---|---|---|---|---|
| aggression | aggression < 0.0 | aggression >= 0.0 | -0.065 | [-0.162, +0.025] | no |
| archetype | hyperbait | other | -0.119 | [-0.240, +0.018] | no |
| archetype | hyperbait | royal_giant | -0.227 * | [-0.451, -0.029] | no |
| archetype | hyperbait | weak_other | -0.096 | [-0.203, +0.013] | no |
| archetype | other | royal_giant | -0.108 | [-0.341, +0.093] | no |
| archetype | other | weak_other | +0.022 | [-0.106, +0.144] | no |
| archetype | royal_giant | weak_other | +0.130 | [-0.055, +0.352] | no |
| bank | bank < 2.0 | bank >= 2.0 | -0.015 | [-0.105, +0.080] | no |
| lane_bias | lane_bias < 0.0 | lane_bias >= 0.0 | +0.001 | [-0.096, +0.098] | no |
| spell_delay | spell_delay < 2 | spell_delay >= 2 | -0.039 | [-0.130, +0.054] | no |
| temperature | temperature < 1.0 | temperature >= 1.0 | +0.037 | [-0.056, +0.127] | no |
| type | exploiter | exploiter_league | +0.019 | [-0.084, +0.124] | no |
| type | exploiter | init | -0.017 | [-0.188, +0.161] | no |
| type | exploiter | snapshot | +0.048 | [-0.086, +0.167] | no |
| type | exploiter_league | init | -0.037 | [-0.223, +0.149] | no |
| type | exploiter_league | snapshot | +0.028 | [-0.112, +0.154] | no |
| type | init | snapshot | +0.065 | [-0.135, +0.258] | no |

## rocket-wait  (mean dQ, 90% cluster CI; * = CI excludes 0)

| dimension | level | n | mean | 90% CI |
|---|---|---|---|---|
| aggression | aggression < 0.0 | 103 | -0.128 * | [-0.181, -0.072] |
| aggression | aggression >= 0.0 | 97 | -0.162 * | [-0.252, -0.073] |
| all | all | 200 | -0.144 * | [-0.196, -0.093] |
| archetype | hyperbait | 25 | -0.253 * | [-0.352, -0.155] |
| archetype | other | 51 | -0.044 | [-0.147, +0.054] |
| archetype | royal_giant | 30 | -0.134 | [-0.326, +0.093] |
| archetype | weak_other | 66 | -0.164 * | [-0.236, -0.100] |
| bank | bank < 2.0 | 103 | -0.137 * | [-0.217, -0.051] |
| bank | bank >= 2.0 | 97 | -0.152 * | [-0.215, -0.086] |
| lane_bias | lane_bias < 0.0 | 101 | -0.122 * | [-0.202, -0.041] |
| lane_bias | lane_bias >= 0.0 | 99 | -0.167 * | [-0.230, -0.106] |
| spell_delay | spell_delay < 2 | 81 | -0.222 * | [-0.300, -0.150] |
| spell_delay | spell_delay >= 2 | 119 | -0.092 * | [-0.161, -0.024] |
| temperature | temperature < 1.0 | 94 | -0.203 * | [-0.277, -0.137] |
| temperature | temperature >= 1.0 | 106 | -0.092 * | [-0.161, -0.016] |
| type | exploiter | 83 | -0.177 * | [-0.240, -0.109] |
| type | exploiter_league | 64 | -0.112 * | [-0.199, -0.028] |
| type | init | 30 | -0.080 | [-0.261, +0.128] |
| type | snapshot | 23 | -0.202 * | [-0.320, -0.087] |

Half-vs-half differences (level A minus level B), 90% CI; sign change flagged:

| dimension | A | B | diff | 90% CI | sign change |
|---|---|---|---|---|---|
| aggression | aggression < 0.0 | aggression >= 0.0 | +0.034 | [-0.068, +0.136] | no |
| archetype | hyperbait | other | -0.209 * | [-0.354, -0.065] | no |
| archetype | hyperbait | royal_giant | -0.119 | [-0.364, +0.104] | no |
| archetype | hyperbait | weak_other | -0.089 | [-0.207, +0.027] | no |
| archetype | other | royal_giant | +0.090 | [-0.167, +0.314] | no |
| archetype | other | weak_other | +0.120 | [-0.001, +0.242] | no |
| archetype | royal_giant | weak_other | +0.030 | [-0.175, +0.268] | no |
| bank | bank < 2.0 | bank >= 2.0 | +0.015 | [-0.089, +0.119] | no |
| lane_bias | lane_bias < 0.0 | lane_bias >= 0.0 | +0.045 | [-0.056, +0.150] | no |
| spell_delay | spell_delay < 2 | spell_delay >= 2 | -0.130 * | [-0.239, -0.033] | no |
| temperature | temperature < 1.0 | temperature >= 1.0 | -0.111 * | [-0.216, -0.010] | no |
| type | exploiter | exploiter_league | -0.064 | [-0.169, +0.053] | no |
| type | exploiter | init | -0.097 | [-0.293, +0.095] | no |
| type | exploiter | snapshot | +0.025 | [-0.108, +0.160] | no |
| type | exploiter_league | init | -0.032 | [-0.243, +0.178] | no |
| type | exploiter_league | snapshot | +0.089 | [-0.053, +0.241] | no |
| type | init | snapshot | +0.122 | [-0.095, +0.357] | no |

## rocket-again  (mean dQ, 90% cluster CI; * = CI excludes 0)

| dimension | level | n | mean | 90% CI |
|---|---|---|---|---|
| aggression | aggression < 0.0 | 79 | -0.089 * | [-0.148, -0.035] |
| aggression | aggression >= 0.0 | 71 | -0.170 * | [-0.265, -0.072] |
| all | all | 150 | -0.128 * | [-0.182, -0.075] |
| archetype | hyperbait | 23 | -0.089 * | [-0.180, -0.010] |
| archetype | other | 42 | -0.023 | [-0.147, +0.115] |
| archetype | royal_giant | 19 | -0.237 * | [-0.519, -0.013] |
| archetype | weak_other | 46 | -0.168 * | [-0.242, -0.105] |
| bank | bank < 2.0 | 79 | -0.111 * | [-0.188, -0.038] |
| bank | bank >= 2.0 | 71 | -0.146 * | [-0.222, -0.068] |
| lane_bias | lane_bias < 0.0 | 74 | -0.110 * | [-0.179, -0.050] |
| lane_bias | lane_bias >= 0.0 | 76 | -0.144 * | [-0.231, -0.061] |
| spell_delay | spell_delay < 2 | 57 | -0.200 * | [-0.275, -0.135] |
| spell_delay | spell_delay >= 2 | 93 | -0.083 * | [-0.162, -0.008] |
| temperature | temperature < 1.0 | 68 | -0.229 * | [-0.321, -0.146] |
| temperature | temperature >= 1.0 | 82 | -0.044 | [-0.106, +0.027] |
| type | exploiter | 60 | -0.166 * | [-0.238, -0.104] |
| type | exploiter_league | 47 | -0.091 | [-0.224, +0.043] |
| type | init | 24 | -0.089 | [-0.208, +0.025] |
| type | snapshot | 19 | -0.147 * | [-0.288, -0.024] |

Half-vs-half differences (level A minus level B), 90% CI; sign change flagged:

| dimension | A | B | diff | 90% CI | sign change |
|---|---|---|---|---|---|
| aggression | aggression < 0.0 | aggression >= 0.0 | +0.081 | [-0.037, +0.193] | no |
| archetype | hyperbait | other | -0.066 | [-0.226, +0.083] | no |
| archetype | hyperbait | royal_giant | +0.148 | [-0.084, +0.437] | no |
| archetype | hyperbait | weak_other | +0.079 | [-0.029, +0.189] | no |
| archetype | other | royal_giant | +0.214 | [-0.040, +0.513] | no |
| archetype | other | weak_other | +0.145 * | [+0.005, +0.302] | no |
| archetype | royal_giant | weak_other | -0.070 | [-0.349, +0.169] | no |
| bank | bank < 2.0 | bank >= 2.0 | +0.035 | [-0.075, +0.139] | no |
| lane_bias | lane_bias < 0.0 | lane_bias >= 0.0 | +0.034 | [-0.079, +0.138] | no |
| spell_delay | spell_delay < 2 | spell_delay >= 2 | -0.117 * | [-0.227, -0.016] | no |
| temperature | temperature < 1.0 | temperature >= 1.0 | -0.185 * | [-0.297, -0.076] | no |
| type | exploiter | exploiter_league | -0.075 | [-0.226, +0.070] | no |
| type | exploiter | init | -0.076 | [-0.206, +0.056] | no |
| type | exploiter | snapshot | -0.019 | [-0.158, +0.134] | no |
| type | exploiter_league | init | -0.001 | [-0.167, +0.174] | no |
| type | exploiter_league | snapshot | +0.056 | [-0.126, +0.259] | no |
| type | init | snapshot | +0.057 | [-0.113, +0.244] | no |

