# P4 audit tables: 1820 samples from f3base2.jsonl (updates >= 1)

samples per trigger: def_xbow 126, rocket 349, rocket_cycle 620, rocket_played 89, rocket_tornado 256, tornado_redirect 188, xbow_after_fail 192

### dQ at the main horizon: all / phase / score

| trigger | alternative | split | label | n | mean dQ | 90% CI |
|---|---|---|---|---|---|---|
| def_xbow | wait | all | all | 126 | +0.042 | [-0.009, +0.094] |
| def_xbow | wait | close_ot | close OT (even crowns, |hp margin| <= .25) | 13 | +0.120 | [-0.081, +0.325] |
| def_xbow | wait | phase | 1x | 29 | +0.019 | [-0.083, +0.122] |
| def_xbow | wait | phase | 2x | 51 | +0.029 | [-0.046, +0.101] |
| def_xbow | wait | phase | OT | 46 | +0.070 | [-0.017, +0.162] |
| def_xbow | wait | score | ahead | 57 | -0.004 | [-0.045, +0.036] |
| def_xbow | wait | score | behind | 26 | +0.161 * | [+0.003, +0.345] |
| def_xbow | wait | score | even | 43 | +0.030 | [-0.063, +0.128] |
| def_xbow | wait | tesla | tesla in hand | 46 | +0.131 * | [+0.041, +0.231] |
| def_xbow | wait | tesla | tesla not in hand | 80 | -0.010 | [-0.068, +0.054] |
| def_xbow | xbow_def_tile | all | all | 126 | -0.074 * | [-0.129, -0.018] |
| def_xbow | xbow_def_tile | close_ot | close OT (even crowns, |hp margin| <= .25) | 13 | +0.079 | [-0.137, +0.248] |
| def_xbow | xbow_def_tile | phase | 1x | 29 | -0.116 * | [-0.235, -0.001] |
| def_xbow | xbow_def_tile | phase | 2x | 51 | -0.098 * | [-0.167, -0.033] |
| def_xbow | xbow_def_tile | phase | OT | 46 | -0.022 | [-0.111, +0.072] |
| def_xbow | xbow_def_tile | score | ahead | 57 | -0.057 * | [-0.101, -0.020] |
| def_xbow | xbow_def_tile | score | behind | 26 | -0.161 | [-0.336, +0.030] |
| def_xbow | xbow_def_tile | score | even | 43 | -0.045 | [-0.147, +0.053] |
| def_xbow | xbow_def_tile | tesla | tesla in hand | 46 | -0.076 | [-0.157, +0.004] |
| def_xbow | xbow_def_tile | tesla | tesla not in hand | 80 | -0.073 * | [-0.141, -0.003] |
| def_xbow | xbow_reach_lane | all | all | 20 | -0.051 | [-0.139, +0.036] |
| def_xbow | xbow_reach_lane | phase | 2x | 12 | -0.040 | [-0.144, +0.023] |
| def_xbow | xbow_reach_lane | score | ahead | 11 | +0.000 | [+0.000, +0.000] |
| def_xbow | xbow_reach_lane | tesla | tesla not in hand | 14 | -0.073 | [-0.200, +0.054] |
| rocket | rocket_clump | all | all | 193 | -0.197 * | [-0.247, -0.148] |
| rocket | rocket_clump | close_ot | close OT (even crowns, |hp margin| <= .25) | 12 | -0.203 * | [-0.389, -0.046] |
| rocket | rocket_clump | phase | 1x | 99 | -0.290 * | [-0.360, -0.223] |
| rocket | rocket_clump | phase | 2x | 53 | -0.114 * | [-0.188, -0.042] |
| rocket | rocket_clump | phase | OT | 41 | -0.078 | [-0.179, +0.024] |
| rocket | rocket_clump | score | ahead | 51 | -0.104 * | [-0.192, -0.016] |
| rocket | rocket_clump | score | behind | 41 | -0.094 * | [-0.177, -0.006] |
| rocket | rocket_clump | score | even | 101 | -0.285 * | [-0.354, -0.221] |
| rocket | rocket_clump | tesla | tesla in hand | 80 | -0.259 * | [-0.343, -0.181] |
| rocket | rocket_clump | tesla | tesla not in hand | 113 | -0.153 * | [-0.209, -0.099] |
| rocket | rocket_empty | all | all | 317 | -0.321 * | [-0.363, -0.280] |
| rocket | rocket_empty | close_ot | close OT (even crowns, |hp margin| <= .25) | 16 | -0.319 * | [-0.532, -0.086] |
| rocket | rocket_empty | phase | 1x | 212 | -0.401 * | [-0.454, -0.350] |
| rocket | rocket_empty | phase | 2x | 59 | -0.219 * | [-0.287, -0.148] |
| rocket | rocket_empty | phase | OT | 46 | -0.087 | [-0.206, +0.039] |
| rocket | rocket_empty | score | ahead | 84 | -0.267 * | [-0.355, -0.182] |
| rocket | rocket_empty | score | behind | 62 | -0.166 * | [-0.244, -0.081] |
| rocket | rocket_empty | score | even | 171 | -0.405 * | [-0.456, -0.353] |
| rocket | rocket_empty | tesla | tesla in hand | 136 | -0.355 * | [-0.421, -0.291] |
| rocket | rocket_empty | tesla | tesla not in hand | 181 | -0.296 * | [-0.347, -0.250] |
| rocket | rocket_princess | all | all | 349 | -0.230 * | [-0.264, -0.196] |
| rocket | rocket_princess | close_ot | close OT (even crowns, |hp margin| <= .25) | 16 | -0.255 * | [-0.467, -0.022] |
| rocket | rocket_princess | phase | 1x | 226 | -0.298 * | [-0.344, -0.255] |
| rocket | rocket_princess | phase | 2x | 71 | -0.129 * | [-0.187, -0.068] |
| rocket | rocket_princess | phase | OT | 52 | -0.071 | [-0.167, +0.022] |
| rocket | rocket_princess | score | ahead | 91 | -0.138 * | [-0.209, -0.066] |
| rocket | rocket_princess | score | behind | 71 | -0.104 * | [-0.162, -0.044] |
| rocket | rocket_princess | score | even | 187 | -0.323 * | [-0.369, -0.278] |
| rocket | rocket_princess | tesla | tesla in hand | 150 | -0.259 * | [-0.309, -0.208] |
| rocket | rocket_princess | tesla | tesla not in hand | 199 | -0.208 * | [-0.253, -0.164] |
| rocket_cycle | rocket_empty | all | all | 377 | -0.095 * | [-0.150, -0.039] |
| rocket_cycle | rocket_empty | close_ot | close OT (even crowns, |hp margin| <= .25) | 97 | -0.152 * | [-0.271, -0.028] |
| rocket_cycle | rocket_empty | phase | 2x | 86 | -0.041 | [-0.150, +0.065] |
| rocket_cycle | rocket_empty | phase | OT | 291 | -0.111 * | [-0.172, -0.053] |
| rocket_cycle | rocket_empty | score | ahead | 127 | +0.014 | [-0.034, +0.071] |
| rocket_cycle | rocket_empty | score | behind | 115 | -0.108 | [-0.223, +0.002] |
| rocket_cycle | rocket_empty | score | even | 135 | -0.186 * | [-0.283, -0.092] |
| rocket_cycle | rocket_empty | tesla | tesla in hand | 165 | -0.097 * | [-0.176, -0.021] |
| rocket_cycle | rocket_empty | tesla | tesla not in hand | 212 | -0.093 * | [-0.159, -0.029] |
| rocket_cycle | rocket_princess | all | all | 619 | -0.062 * | [-0.103, -0.021] |
| rocket_cycle | rocket_princess | close_ot | close OT (even crowns, |hp margin| <= .25) | 159 | -0.104 * | [-0.195, -0.010] |
| rocket_cycle | rocket_princess | phase | 2x | 130 | -0.079 | [-0.179, +0.023] |
| rocket_cycle | rocket_princess | phase | OT | 489 | -0.057 * | [-0.100, -0.016] |
| rocket_cycle | rocket_princess | score | ahead | 206 | +0.019 | [-0.019, +0.060] |
| rocket_cycle | rocket_princess | score | behind | 198 | -0.066 | [-0.149, +0.007] |
| rocket_cycle | rocket_princess | score | even | 215 | -0.135 * | [-0.215, -0.059] |
| rocket_cycle | rocket_princess | tesla | tesla in hand | 270 | -0.100 * | [-0.163, -0.034] |
| rocket_cycle | rocket_princess | tesla | tesla not in hand | 349 | -0.032 | [-0.082, +0.020] |
| rocket_cycle | wait | all | all | 126 | -0.054 | [-0.118, +0.006] |
| rocket_cycle | wait | close_ot | close OT (even crowns, |hp margin| <= .25) | 37 | -0.001 | [-0.132, +0.124] |
| rocket_cycle | wait | phase | OT | 126 | -0.054 | [-0.118, +0.006] |
| rocket_cycle | wait | score | ahead | 63 | -0.016 | [-0.063, +0.028] |
| rocket_cycle | wait | score | behind | 26 | -0.222 * | [-0.422, -0.060] |
| rocket_cycle | wait | score | even | 37 | -0.001 | [-0.132, +0.124] |
| rocket_cycle | wait | tesla | tesla in hand | 63 | -0.031 | [-0.093, +0.030] |
| rocket_cycle | wait | tesla | tesla not in hand | 63 | -0.077 | [-0.183, +0.015] |
| rocket_played | second_card | all | all | 89 | -0.068 | [-0.146, +0.005] |
| rocket_played | second_card | phase | 1x | 43 | -0.096 * | [-0.177, -0.005] |
| rocket_played | second_card | phase | 2x | 22 | -0.139 | [-0.334, +0.063] |
| rocket_played | second_card | phase | OT | 24 | +0.047 | [-0.074, +0.177] |
| rocket_played | second_card | score | ahead | 22 | -0.181 * | [-0.370, -0.034] |
| rocket_played | second_card | score | behind | 21 | +0.029 | [-0.075, +0.154] |
| rocket_played | second_card | score | even | 46 | -0.059 | [-0.166, +0.049] |
| rocket_played | second_card | tesla | tesla in hand | 46 | -0.046 | [-0.147, +0.055] |
| rocket_played | second_card | tesla | tesla not in hand | 43 | -0.093 | [-0.209, +0.022] |
| rocket_played | wait | all | all | 89 | +0.040 | [-0.029, +0.110] |
| rocket_played | wait | phase | 1x | 43 | +0.002 | [-0.061, +0.075] |
| rocket_played | wait | phase | 2x | 22 | +0.096 | [-0.050, +0.261] |
| rocket_played | wait | phase | OT | 24 | +0.058 | [-0.085, +0.202] |
| rocket_played | wait | score | ahead | 22 | -0.035 | [-0.150, +0.067] |
| rocket_played | wait | score | behind | 21 | +0.095 | [-0.026, +0.255] |
| rocket_played | wait | score | even | 46 | +0.051 | [-0.071, +0.167] |
| rocket_played | wait | tesla | tesla in hand | 46 | +0.095 * | [+0.010, +0.194] |
| rocket_played | wait | tesla | tesla not in hand | 43 | -0.018 | [-0.128, +0.083] |
| rocket_tornado | combo | all | all | 256 | -0.335 * | [-0.384, -0.288] |
| rocket_tornado | combo | close_ot | close OT (even crowns, |hp margin| <= .25) | 16 | -0.432 * | [-0.721, -0.102] |
| rocket_tornado | combo | phase | 1x | 108 | -0.428 * | [-0.488, -0.367] |
| rocket_tornado | combo | phase | 2x | 85 | -0.276 * | [-0.375, -0.187] |
| rocket_tornado | combo | phase | OT | 63 | -0.257 * | [-0.367, -0.146] |
| rocket_tornado | combo | score | ahead | 58 | -0.291 * | [-0.391, -0.197] |
| rocket_tornado | combo | score | behind | 68 | -0.182 * | [-0.264, -0.107] |
| rocket_tornado | combo | score | even | 130 | -0.436 * | [-0.506, -0.365] |
| rocket_tornado | combo | tesla | tesla in hand | 115 | -0.361 * | [-0.426, -0.304] |
| rocket_tornado | combo | tesla | tesla not in hand | 141 | -0.314 * | [-0.385, -0.248] |
| rocket_tornado | rocket_clump | all | all | 256 | -0.297 * | [-0.351, -0.245] |
| rocket_tornado | rocket_clump | close_ot | close OT (even crowns, |hp margin| <= .25) | 16 | -0.206 | [-0.452, +0.085] |
| rocket_tornado | rocket_clump | phase | 1x | 108 | -0.395 * | [-0.465, -0.324] |
| rocket_tornado | rocket_clump | phase | 2x | 85 | -0.237 * | [-0.348, -0.139] |
| rocket_tornado | rocket_clump | phase | OT | 63 | -0.209 * | [-0.310, -0.106] |
| rocket_tornado | rocket_clump | score | ahead | 58 | -0.288 * | [-0.397, -0.173] |
| rocket_tornado | rocket_clump | score | behind | 68 | -0.190 * | [-0.282, -0.108] |
| rocket_tornado | rocket_clump | score | even | 130 | -0.357 * | [-0.426, -0.286] |
| rocket_tornado | rocket_clump | tesla | tesla in hand | 115 | -0.329 * | [-0.397, -0.267] |
| rocket_tornado | rocket_clump | tesla | tesla not in hand | 141 | -0.271 * | [-0.344, -0.198] |
| rocket_tornado | wait | all | all | 141 | +0.016 | [-0.035, +0.067] |
| rocket_tornado | wait | close_ot | close OT (even crowns, |hp margin| <= .25) | 10 | +0.054 | [-0.198, +0.370] |
| rocket_tornado | wait | phase | 1x | 53 | +0.038 | [-0.032, +0.110] |
| rocket_tornado | wait | phase | 2x | 45 | +0.027 | [-0.065, +0.127] |
| rocket_tornado | wait | phase | OT | 43 | -0.022 | [-0.120, +0.083] |
| rocket_tornado | wait | score | ahead | 39 | -0.030 | [-0.101, +0.030] |
| rocket_tornado | wait | score | behind | 36 | -0.017 | [-0.108, +0.074] |
| rocket_tornado | wait | score | even | 66 | +0.061 | [-0.021, +0.146] |
| rocket_tornado | wait | tesla | tesla in hand | 63 | -0.038 | [-0.115, +0.034] |
| rocket_tornado | wait | tesla | tesla not in hand | 78 | +0.060 | [-0.011, +0.134] |
| tornado_redirect | tornado_king | all | all | 188 | -0.079 * | [-0.123, -0.039] |
| tornado_redirect | tornado_king | close_ot | close OT (even crowns, |hp margin| <= .25) | 15 | -0.004 | [-0.207, +0.193] |
| tornado_redirect | tornado_king | phase | 1x | 77 | -0.064 * | [-0.115, -0.013] |
| tornado_redirect | tornado_king | phase | 2x | 55 | -0.112 * | [-0.196, -0.028] |
| tornado_redirect | tornado_king | phase | OT | 56 | -0.066 | [-0.160, +0.026] |
| tornado_redirect | tornado_king | score | ahead | 53 | -0.094 * | [-0.165, -0.030] |
| tornado_redirect | tornado_king | score | behind | 37 | -0.137 * | [-0.240, -0.028] |
| tornado_redirect | tornado_king | score | even | 98 | -0.048 | [-0.104, +0.011] |
| tornado_redirect | tornado_king | tesla | tesla in hand | 80 | -0.078 * | [-0.144, -0.021] |
| tornado_redirect | tornado_king | tesla | tesla not in hand | 108 | -0.079 * | [-0.135, -0.023] |
| tornado_redirect | tornado_on | all | all | 188 | -0.066 * | [-0.104, -0.029] |
| tornado_redirect | tornado_on | close_ot | close OT (even crowns, |hp margin| <= .25) | 15 | -0.139 | [-0.363, +0.051] |
| tornado_redirect | tornado_on | phase | 1x | 77 | -0.058 * | [-0.111, -0.009] |
| tornado_redirect | tornado_on | phase | 2x | 55 | -0.094 * | [-0.171, -0.020] |
| tornado_redirect | tornado_on | phase | OT | 56 | -0.050 | [-0.131, +0.029] |
| tornado_redirect | tornado_on | score | ahead | 53 | -0.046 * | [-0.092, -0.003] |
| tornado_redirect | tornado_on | score | behind | 37 | -0.063 | [-0.158, +0.038] |
| tornado_redirect | tornado_on | score | even | 98 | -0.078 * | [-0.136, -0.021] |
| tornado_redirect | tornado_on | tesla | tesla in hand | 80 | -0.058 | [-0.124, +0.007] |
| tornado_redirect | tornado_on | tesla | tesla not in hand | 108 | -0.072 * | [-0.118, -0.030] |
| tornado_redirect | wait | all | all | 31 | +0.013 | [-0.109, +0.127] |
| tornado_redirect | wait | phase | 2x | 13 | -0.096 | [-0.280, +0.084] |
| tornado_redirect | wait | phase | OT | 13 | +0.137 | [-0.034, +0.324] |
| tornado_redirect | wait | score | ahead | 13 | -0.057 | [-0.207, +0.067] |
| tornado_redirect | wait | score | even | 13 | +0.074 | [-0.086, +0.254] |
| tornado_redirect | wait | tesla | tesla in hand | 14 | +0.121 | [-0.084, +0.330] |
| tornado_redirect | wait | tesla | tesla not in hand | 17 | -0.077 | [-0.185, +0.021] |
| xbow_after_fail | rocket_empty | all | all | 149 | -0.259 * | [-0.317, -0.205] |
| xbow_after_fail | rocket_empty | close_ot | close OT (even crowns, |hp margin| <= .25) | 12 | -0.177 * | [-0.335, -0.046] |
| xbow_after_fail | rocket_empty | phase | 1x | 47 | -0.357 * | [-0.454, -0.265] |
| xbow_after_fail | rocket_empty | phase | 2x | 65 | -0.225 * | [-0.314, -0.133] |
| xbow_after_fail | rocket_empty | phase | OT | 37 | -0.194 * | [-0.309, -0.094] |
| xbow_after_fail | rocket_empty | score | ahead | 32 | -0.144 * | [-0.263, -0.026] |
| xbow_after_fail | rocket_empty | score | behind | 47 | -0.152 * | [-0.242, -0.063] |
| xbow_after_fail | rocket_empty | score | even | 70 | -0.382 * | [-0.465, -0.308] |
| xbow_after_fail | rocket_empty | tesla | tesla in hand | 68 | -0.227 * | [-0.316, -0.136] |
| xbow_after_fail | rocket_empty | tesla | tesla not in hand | 81 | -0.285 * | [-0.360, -0.212] |
| xbow_after_fail | rocket_princess | all | all | 188 | -0.222 * | [-0.273, -0.172] |
| xbow_after_fail | rocket_princess | close_ot | close OT (even crowns, |hp margin| <= .25) | 20 | -0.279 * | [-0.524, -0.076] |
| xbow_after_fail | rocket_princess | phase | 1x | 52 | -0.272 * | [-0.354, -0.192] |
| xbow_after_fail | rocket_princess | phase | 2x | 79 | -0.222 * | [-0.312, -0.135] |
| xbow_after_fail | rocket_princess | phase | OT | 57 | -0.176 * | [-0.283, -0.081] |
| xbow_after_fail | rocket_princess | score | ahead | 42 | -0.098 | [-0.202, +0.002] |
| xbow_after_fail | rocket_princess | score | behind | 58 | -0.134 * | [-0.218, -0.054] |
| xbow_after_fail | rocket_princess | score | even | 88 | -0.339 * | [-0.422, -0.262] |
| xbow_after_fail | rocket_princess | tesla | tesla in hand | 87 | -0.223 * | [-0.309, -0.138] |
| xbow_after_fail | rocket_princess | tesla | tesla not in hand | 101 | -0.221 * | [-0.285, -0.160] |
| xbow_after_fail | wait | all | all | 28 | +0.016 | [-0.103, +0.134] |
| xbow_after_fail | wait | phase | 2x | 13 | -0.015 | [-0.144, +0.108] |
| xbow_after_fail | wait | phase | OT | 13 | +0.016 | [-0.196, +0.238] |
| xbow_after_fail | wait | score | ahead | 11 | -0.036 | [-0.085, +0.007] |
| xbow_after_fail | wait | score | even | 13 | +0.038 | [-0.136, +0.229] |
| xbow_after_fail | wait | tesla | tesla in hand | 12 | +0.194 * | [+0.036, +0.370] |
| xbow_after_fail | wait | tesla | tesla not in hand | 16 | -0.118 | [-0.260, +0.031] |
| xbow_after_fail | xbow_defensive | all | all | 191 | -0.103 * | [-0.143, -0.061] |
| xbow_after_fail | xbow_defensive | close_ot | close OT (even crowns, |hp margin| <= .25) | 20 | -0.218 * | [-0.464, -0.026] |
| xbow_after_fail | xbow_defensive | phase | 1x | 53 | -0.081 * | [-0.159, -0.009] |
| xbow_after_fail | xbow_defensive | phase | 2x | 80 | -0.082 * | [-0.143, -0.021] |
| xbow_after_fail | xbow_defensive | phase | OT | 58 | -0.152 * | [-0.249, -0.059] |
| xbow_after_fail | xbow_defensive | score | ahead | 43 | -0.007 | [-0.080, +0.062] |
| xbow_after_fail | xbow_defensive | score | behind | 59 | -0.053 | [-0.122, +0.015] |
| xbow_after_fail | xbow_defensive | score | even | 89 | -0.183 * | [-0.253, -0.116] |
| xbow_after_fail | xbow_defensive | tesla | tesla in hand | 90 | -0.071 * | [-0.135, -0.007] |
| xbow_after_fail | xbow_defensive | tesla | tesla not in hand | 101 | -0.131 * | [-0.190, -0.075] |
| xbow_after_fail | xbow_reach | all | all | 172 | -0.018 | [-0.063, +0.026] |
| xbow_after_fail | xbow_reach | close_ot | close OT (even crowns, |hp margin| <= .25) | 17 | -0.091 | [-0.267, +0.066] |
| xbow_after_fail | xbow_reach | phase | 1x | 52 | -0.074 | [-0.165, +0.015] |
| xbow_after_fail | xbow_reach | phase | 2x | 72 | +0.057 | [-0.018, +0.131] |
| xbow_after_fail | xbow_reach | phase | OT | 48 | -0.068 * | [-0.135, -0.003] |
| xbow_after_fail | xbow_reach | score | ahead | 33 | +0.025 | [-0.076, +0.125] |
| xbow_after_fail | xbow_reach | score | behind | 58 | +0.077 * | [+0.001, +0.155] |
| xbow_after_fail | xbow_reach | score | even | 81 | -0.103 * | [-0.172, -0.041] |
| xbow_after_fail | xbow_reach | tesla | tesla in hand | 82 | -0.035 | [-0.108, +0.036] |
| xbow_after_fail | xbow_reach | tesla | tesla not in hand | 90 | -0.002 | [-0.060, +0.057] |

### dQ at the main horizon: trigger-specific splits

| trigger | alternative | split | label | n | mean dQ | 90% CI |
|---|---|---|---|---|---|---|
| def_xbow | wait | elixir | elixir < 8 | 104 | +0.005 | [-0.045, +0.059] |
| def_xbow | wait | elixir | elixir >= 8 | 22 | +0.215 * | [+0.060, +0.358] |
| def_xbow | wait | opp | exploiter | 92 | +0.056 | [-0.005, +0.117] |
| def_xbow | wait | opp | exploiter_league | 16 | +0.046 | [-0.090, +0.216] |
| def_xbow | wait | opp | init | 18 | -0.033 | [-0.091, +0.042] |
| def_xbow | wait | opp_bank | bank<2 | 71 | +0.002 | [-0.057, +0.063] |
| def_xbow | wait | opp_bank | bank>=2 | 55 | +0.093 * | [+0.009, +0.179] |
| def_xbow | wait | policy | policy played | 126 | +0.042 | [-0.009, +0.094] |
| def_xbow | wait | threat | foe on our half | 23 | +0.079 | [-0.059, +0.220] |
| def_xbow | wait | threat | no foe body on our half | 103 | +0.033 | [-0.016, +0.087] |
| def_xbow | wait | xbow_hand | xbow in hand | 126 | +0.042 | [-0.009, +0.094] |
| def_xbow | xbow_def_tile | elixir | elixir < 8 | 104 | -0.080 * | [-0.135, -0.024] |
| def_xbow | xbow_def_tile | elixir | elixir >= 8 | 22 | -0.046 | [-0.184, +0.084] |
| def_xbow | xbow_def_tile | opp | exploiter | 92 | -0.054 | [-0.121, +0.013] |
| def_xbow | xbow_def_tile | opp | exploiter_league | 16 | -0.063 | [-0.183, +0.050] |
| def_xbow | xbow_def_tile | opp | init | 18 | -0.189 * | [-0.293, -0.055] |
| def_xbow | xbow_def_tile | opp_bank | bank<2 | 71 | -0.097 * | [-0.173, -0.014] |
| def_xbow | xbow_def_tile | opp_bank | bank>=2 | 55 | -0.045 | [-0.112, +0.021] |
| def_xbow | xbow_def_tile | policy | policy played | 126 | -0.074 * | [-0.129, -0.018] |
| def_xbow | xbow_def_tile | threat | foe on our half | 23 | -0.110 * | [-0.203, -0.022] |
| def_xbow | xbow_def_tile | threat | no foe body on our half | 103 | -0.066 * | [-0.130, -0.001] |
| def_xbow | xbow_def_tile | xbow_hand | xbow in hand | 126 | -0.074 * | [-0.129, -0.018] |
| def_xbow | xbow_reach_lane | elixir | elixir < 8 | 17 | -0.061 | [-0.165, +0.037] |
| def_xbow | xbow_reach_lane | opp | exploiter | 15 | -0.009 | [-0.073, +0.068] |
| def_xbow | xbow_reach_lane | opp_bank | bank>=2 | 12 | -0.061 | [-0.209, +0.024] |
| def_xbow | xbow_reach_lane | policy | policy played | 20 | -0.051 | [-0.139, +0.036] |
| def_xbow | xbow_reach_lane | threat | no foe body on our half | 19 | -0.071 | [-0.156, +0.009] |
| def_xbow | xbow_reach_lane | xbow_hand | xbow in hand | 20 | -0.051 | [-0.139, +0.036] |
| rocket | rocket_clump | elixir | elixir < 8 | 157 | -0.169 * | [-0.227, -0.119] |
| rocket | rocket_clump | elixir | elixir >= 8 | 36 | -0.317 * | [-0.422, -0.213] |
| rocket | rocket_clump | opp | exploiter | 104 | -0.181 * | [-0.236, -0.126] |
| rocket | rocket_clump | opp | exploiter_league | 49 | -0.211 * | [-0.333, -0.090] |
| rocket | rocket_clump | opp | init | 40 | -0.220 * | [-0.342, -0.111] |
| rocket | rocket_clump | opp_bank | bank<2 | 85 | -0.189 * | [-0.263, -0.114] |
| rocket | rocket_clump | opp_bank | bank>=2 | 108 | -0.203 * | [-0.269, -0.144] |
| rocket | rocket_clump | policy | policy played | 40 | -0.222 * | [-0.312, -0.142] |
| rocket | rocket_clump | policy | policy waited | 153 | -0.190 * | [-0.250, -0.136] |
| rocket | rocket_clump | safe_idle | safe & idle (no foe on our half, policy waited) | 108 | -0.223 * | [-0.291, -0.155] |
| rocket | rocket_clump | threat | foe on our half | 60 | -0.144 * | [-0.220, -0.066] |
| rocket | rocket_clump | threat | no foe body on our half | 133 | -0.220 * | [-0.282, -0.163] |
| rocket | rocket_clump | value_rocket_clump | 4-6 | 63 | -0.166 * | [-0.250, -0.087] |
| rocket | rocket_clump | value_rocket_clump | 6-8 | 39 | -0.250 * | [-0.388, -0.127] |
| rocket | rocket_clump | value_rocket_clump | 8+ | 21 | -0.085 | [-0.179, +0.008] |
| rocket | rocket_clump | value_rocket_clump | <4 | 70 | -0.228 * | [-0.300, -0.162] |
| rocket | rocket_clump | xbow_hand | no xbow in hand | 72 | -0.225 * | [-0.306, -0.147] |
| rocket | rocket_clump | xbow_hand | xbow in hand | 121 | -0.180 * | [-0.237, -0.120] |
| rocket | rocket_empty | elixir | elixir < 8 | 250 | -0.306 * | [-0.352, -0.262] |
| rocket | rocket_empty | elixir | elixir >= 8 | 67 | -0.377 * | [-0.466, -0.286] |
| rocket | rocket_empty | opp | exploiter | 171 | -0.298 * | [-0.351, -0.246] |
| rocket | rocket_empty | opp | exploiter_league | 84 | -0.326 * | [-0.416, -0.235] |
| rocket | rocket_empty | opp | init | 62 | -0.379 * | [-0.462, -0.299] |
| rocket | rocket_empty | opp_bank | bank<2 | 143 | -0.304 * | [-0.364, -0.242] |
| rocket | rocket_empty | opp_bank | bank>=2 | 174 | -0.336 * | [-0.389, -0.284] |
| rocket | rocket_empty | policy | policy played | 42 | -0.261 * | [-0.338, -0.187] |
| rocket | rocket_empty | policy | policy waited | 275 | -0.331 * | [-0.377, -0.286] |
| rocket | rocket_empty | safe_idle | safe & idle (no foe on our half, policy waited) | 200 | -0.371 * | [-0.424, -0.318] |
| rocket | rocket_empty | threat | foe on our half | 90 | -0.245 * | [-0.316, -0.169] |
| rocket | rocket_empty | threat | no foe body on our half | 227 | -0.352 * | [-0.400, -0.305] |
| rocket | rocket_empty | value_rocket_clump | 4-6 | 53 | -0.371 * | [-0.465, -0.282] |
| rocket | rocket_empty | value_rocket_clump | 6-8 | 36 | -0.425 * | [-0.551, -0.293] |
| rocket | rocket_empty | value_rocket_clump | 8+ | 15 | -0.296 * | [-0.492, -0.119] |
| rocket | rocket_empty | value_rocket_clump | <4 | 60 | -0.307 * | [-0.392, -0.226] |
| rocket | rocket_empty | xbow_hand | no xbow in hand | 118 | -0.315 * | [-0.381, -0.253] |
| rocket | rocket_empty | xbow_hand | xbow in hand | 199 | -0.325 * | [-0.376, -0.272] |
| rocket | rocket_princess | elixir | elixir < 8 | 277 | -0.206 * | [-0.245, -0.168] |
| rocket | rocket_princess | elixir | elixir >= 8 | 72 | -0.321 * | [-0.391, -0.255] |
| rocket | rocket_princess | opp | exploiter | 191 | -0.209 * | [-0.254, -0.163] |
| rocket | rocket_princess | opp | exploiter_league | 89 | -0.264 * | [-0.348, -0.187] |
| rocket | rocket_princess | opp | init | 69 | -0.243 * | [-0.313, -0.177] |
| rocket | rocket_princess | opp_bank | bank<2 | 161 | -0.213 * | [-0.263, -0.164] |
| rocket | rocket_princess | opp_bank | bank>=2 | 188 | -0.245 * | [-0.292, -0.197] |
| rocket | rocket_princess | policy | policy played | 51 | -0.184 * | [-0.259, -0.110] |
| rocket | rocket_princess | policy | policy waited | 298 | -0.238 * | [-0.276, -0.200] |
| rocket | rocket_princess | safe_idle | safe & idle (no foe on our half, policy waited) | 220 | -0.257 * | [-0.302, -0.213] |
| rocket | rocket_princess | threat | foe on our half | 94 | -0.170 * | [-0.231, -0.114] |
| rocket | rocket_princess | threat | no foe body on our half | 255 | -0.252 * | [-0.294, -0.209] |
| rocket | rocket_princess | value_rocket_clump | 4-6 | 63 | -0.214 * | [-0.299, -0.135] |
| rocket | rocket_princess | value_rocket_clump | 6-8 | 39 | -0.326 * | [-0.451, -0.208] |
| rocket | rocket_princess | value_rocket_clump | 8+ | 21 | -0.178 * | [-0.317, -0.050] |
| rocket | rocket_princess | value_rocket_clump | <4 | 70 | -0.223 * | [-0.293, -0.161] |
| rocket | rocket_princess | xbow_hand | no xbow in hand | 133 | -0.237 * | [-0.292, -0.183] |
| rocket | rocket_princess | xbow_hand | xbow in hand | 216 | -0.225 * | [-0.269, -0.183] |
| rocket_cycle | rocket_empty | elixir | elixir < 8 | 361 | -0.089 * | [-0.144, -0.033] |
| rocket_cycle | rocket_empty | elixir | elixir >= 8 | 16 | -0.227 * | [-0.470, -0.049] |
| rocket_cycle | rocket_empty | opp | exploiter | 196 | -0.089 * | [-0.166, -0.015] |
| rocket_cycle | rocket_empty | opp | exploiter_league | 105 | -0.148 * | [-0.281, -0.019] |
| rocket_cycle | rocket_empty | opp | init | 76 | -0.036 | [-0.104, +0.029] |
| rocket_cycle | rocket_empty | opp_bank | bank<2 | 174 | -0.088 | [-0.181, +0.002] |
| rocket_cycle | rocket_empty | opp_bank | bank>=2 | 203 | -0.100 * | [-0.162, -0.040] |
| rocket_cycle | rocket_empty | policy | policy played | 82 | -0.163 * | [-0.252, -0.079] |
| rocket_cycle | rocket_empty | policy | policy waited | 295 | -0.076 * | [-0.142, -0.013] |
| rocket_cycle | rocket_empty | safe_idle | safe & idle (no foe on our half, policy waited) | 151 | -0.068 | [-0.153, +0.014] |
| rocket_cycle | rocket_empty | threat | foe on our half | 191 | -0.128 * | [-0.198, -0.062] |
| rocket_cycle | rocket_empty | threat | no foe body on our half | 186 | -0.060 | [-0.132, +0.010] |
| rocket_cycle | rocket_empty | xbow_hand | no xbow in hand | 166 | -0.094 * | [-0.169, -0.023] |
| rocket_cycle | rocket_empty | xbow_hand | xbow in hand | 211 | -0.095 * | [-0.163, -0.029] |
| rocket_cycle | rocket_princess | elixir | elixir < 8 | 596 | -0.060 * | [-0.101, -0.019] |
| rocket_cycle | rocket_princess | elixir | elixir >= 8 | 23 | -0.117 | [-0.271, +0.006] |
| rocket_cycle | rocket_princess | opp | exploiter | 362 | -0.029 | [-0.075, +0.014] |
| rocket_cycle | rocket_princess | opp | exploiter_league | 141 | -0.150 * | [-0.290, -0.028] |
| rocket_cycle | rocket_princess | opp | init | 116 | -0.055 | [-0.119, +0.005] |
| rocket_cycle | rocket_princess | opp_bank | bank<2 | 296 | -0.065 * | [-0.124, -0.004] |
| rocket_cycle | rocket_princess | opp_bank | bank>=2 | 323 | -0.059 * | [-0.117, -0.005] |
| rocket_cycle | rocket_princess | policy | policy played | 126 | -0.098 * | [-0.174, -0.030] |
| rocket_cycle | rocket_princess | policy | policy waited | 493 | -0.052 * | [-0.101, -0.010] |
| rocket_cycle | rocket_princess | safe_idle | safe & idle (no foe on our half, policy waited) | 248 | -0.054 | [-0.111, +0.005] |
| rocket_cycle | rocket_princess | threat | foe on our half | 311 | -0.089 * | [-0.145, -0.031] |
| rocket_cycle | rocket_princess | threat | no foe body on our half | 308 | -0.034 | [-0.085, +0.014] |
| rocket_cycle | rocket_princess | xbow_hand | no xbow in hand | 279 | -0.058 * | [-0.119, -0.001] |
| rocket_cycle | rocket_princess | xbow_hand | xbow in hand | 340 | -0.065 * | [-0.112, -0.019] |
| rocket_cycle | wait | elixir | elixir < 8 | 112 | -0.061 * | [-0.132, -0.000] |
| rocket_cycle | wait | elixir | elixir >= 8 | 14 | +0.000 | [-0.142, +0.142] |
| rocket_cycle | wait | opp | exploiter | 82 | -0.036 | [-0.100, +0.025] |
| rocket_cycle | wait | opp | exploiter_league | 23 | +0.000 | [-0.099, +0.081] |
| rocket_cycle | wait | opp | init | 21 | -0.186 | [-0.457, +0.044] |
| rocket_cycle | wait | opp_bank | bank<2 | 66 | -0.044 | [-0.125, +0.031] |
| rocket_cycle | wait | opp_bank | bank>=2 | 60 | -0.066 | [-0.171, +0.016] |
| rocket_cycle | wait | policy | policy played | 126 | -0.054 | [-0.118, +0.006] |
| rocket_cycle | wait | threat | foe on our half | 66 | -0.089 * | [-0.171, -0.016] |
| rocket_cycle | wait | threat | no foe body on our half | 60 | -0.016 | [-0.094, +0.061] |
| rocket_cycle | wait | xbow_hand | no xbow in hand | 58 | +0.032 | [-0.034, +0.100] |
| rocket_cycle | wait | xbow_hand | xbow in hand | 68 | -0.128 * | [-0.215, -0.044] |
| rocket_played | second_card | elixir | elixir < 8 | 58 | -0.092 | [-0.191, +0.006] |
| rocket_played | second_card | elixir | elixir >= 8 | 31 | -0.024 | [-0.124, +0.091] |
| rocket_played | second_card | opp | exploiter | 40 | -0.052 | [-0.163, +0.068] |
| rocket_played | second_card | opp | exploiter_league | 38 | -0.082 | [-0.200, +0.036] |
| rocket_played | second_card | opp | init | 11 | -0.080 | [-0.284, +0.060] |
| rocket_played | second_card | opp_bank | bank<2 | 37 | -0.006 | [-0.131, +0.110] |
| rocket_played | second_card | opp_bank | bank>=2 | 52 | -0.113 * | [-0.209, -0.024] |
| rocket_played | second_card | policy | policy played | 89 | -0.068 | [-0.146, +0.005] |
| rocket_played | second_card | threat | no foe body on our half | 80 | -0.043 | [-0.129, +0.036] |
| rocket_played | second_card | xbow_hand | no xbow in hand | 56 | -0.017 | [-0.097, +0.069] |
| rocket_played | second_card | xbow_hand | xbow in hand | 33 | -0.156 * | [-0.304, -0.014] |
| rocket_played | wait | elixir | elixir < 8 | 58 | +0.017 | [-0.072, +0.111] |
| rocket_played | wait | elixir | elixir >= 8 | 31 | +0.084 * | [+0.013, +0.166] |
| rocket_played | wait | opp | exploiter | 40 | +0.057 | [-0.012, +0.132] |
| rocket_played | wait | opp | exploiter_league | 38 | +0.038 | [-0.099, +0.184] |
| rocket_played | wait | opp | init | 11 | -0.013 | [-0.066, +0.044] |
| rocket_played | wait | opp_bank | bank<2 | 37 | +0.055 | [-0.036, +0.141] |
| rocket_played | wait | opp_bank | bank>=2 | 52 | +0.030 | [-0.060, +0.130] |
| rocket_played | wait | policy | policy played | 89 | +0.040 | [-0.029, +0.110] |
| rocket_played | wait | threat | no foe body on our half | 80 | +0.071 * | [+0.006, +0.138] |
| rocket_played | wait | xbow_hand | no xbow in hand | 56 | +0.105 * | [+0.031, +0.187] |
| rocket_played | wait | xbow_hand | xbow in hand | 33 | -0.070 | [-0.217, +0.065] |
| rocket_tornado | combo | elixir | elixir < 8 | 91 | -0.308 * | [-0.401, -0.223] |
| rocket_tornado | combo | elixir | elixir >= 8 | 165 | -0.350 * | [-0.408, -0.294] |
| rocket_tornado | combo | opp | exploiter | 142 | -0.343 * | [-0.410, -0.282] |
| rocket_tornado | combo | opp | exploiter_league | 64 | -0.318 * | [-0.431, -0.221] |
| rocket_tornado | combo | opp | init | 50 | -0.336 * | [-0.435, -0.235] |
| rocket_tornado | combo | opp_bank | bank<2 | 121 | -0.372 * | [-0.448, -0.300] |
| rocket_tornado | combo | opp_bank | bank>=2 | 135 | -0.303 * | [-0.366, -0.242] |
| rocket_tornado | combo | policy | policy played | 141 | -0.339 * | [-0.410, -0.270] |
| rocket_tornado | combo | policy | policy waited | 115 | -0.331 * | [-0.398, -0.267] |
| rocket_tornado | combo | safe_idle | safe & idle (no foe on our half, policy waited) | 73 | -0.389 * | [-0.479, -0.309] |
| rocket_tornado | combo | threat | foe on our half | 96 | -0.276 * | [-0.359, -0.195] |
| rocket_tornado | combo | threat | no foe body on our half | 160 | -0.371 * | [-0.434, -0.310] |
| rocket_tornado | combo | value_combo | 6-8 | 150 | -0.384 * | [-0.454, -0.322] |
| rocket_tornado | combo | value_combo | 8+ | 106 | -0.267 * | [-0.344, -0.193] |
| rocket_tornado | combo | value_rocket_clump | 4-6 | 152 | -0.348 * | [-0.411, -0.286] |
| rocket_tornado | combo | value_rocket_clump | 6-8 | 72 | -0.317 * | [-0.416, -0.224] |
| rocket_tornado | combo | value_rocket_clump | 8+ | 23 | -0.278 * | [-0.437, -0.133] |
| rocket_tornado | combo | xbow_hand | no xbow in hand | 102 | -0.350 * | [-0.429, -0.277] |
| rocket_tornado | combo | xbow_hand | xbow in hand | 154 | -0.326 * | [-0.388, -0.263] |
| rocket_tornado | rocket_clump | elixir | elixir < 8 | 91 | -0.289 * | [-0.385, -0.201] |
| rocket_tornado | rocket_clump | elixir | elixir >= 8 | 165 | -0.301 * | [-0.361, -0.243] |
| rocket_tornado | rocket_clump | opp | exploiter | 142 | -0.325 * | [-0.391, -0.264] |
| rocket_tornado | rocket_clump | opp | exploiter_league | 64 | -0.181 * | [-0.292, -0.083] |
| rocket_tornado | rocket_clump | opp | init | 50 | -0.365 * | [-0.484, -0.252] |
| rocket_tornado | rocket_clump | opp_bank | bank<2 | 121 | -0.345 * | [-0.421, -0.276] |
| rocket_tornado | rocket_clump | opp_bank | bank>=2 | 135 | -0.254 * | [-0.324, -0.187] |
| rocket_tornado | rocket_clump | policy | policy played | 141 | -0.264 * | [-0.335, -0.194] |
| rocket_tornado | rocket_clump | policy | policy waited | 115 | -0.337 * | [-0.410, -0.270] |
| rocket_tornado | rocket_clump | safe_idle | safe & idle (no foe on our half, policy waited) | 73 | -0.378 * | [-0.465, -0.293] |
| rocket_tornado | rocket_clump | threat | foe on our half | 96 | -0.248 * | [-0.329, -0.167] |
| rocket_tornado | rocket_clump | threat | no foe body on our half | 160 | -0.326 * | [-0.392, -0.264] |
| rocket_tornado | rocket_clump | value_combo | 6-8 | 150 | -0.376 * | [-0.449, -0.310] |
| rocket_tornado | rocket_clump | value_combo | 8+ | 106 | -0.185 * | [-0.258, -0.114] |
| rocket_tornado | rocket_clump | value_rocket_clump | 4-6 | 152 | -0.391 * | [-0.458, -0.328] |
| rocket_tornado | rocket_clump | value_rocket_clump | 6-8 | 72 | -0.155 * | [-0.242, -0.075] |
| rocket_tornado | rocket_clump | value_rocket_clump | 8+ | 23 | -0.099 | [-0.273, +0.060] |
| rocket_tornado | rocket_clump | xbow_hand | no xbow in hand | 102 | -0.322 * | [-0.419, -0.234] |
| rocket_tornado | rocket_clump | xbow_hand | xbow in hand | 154 | -0.280 * | [-0.339, -0.224] |
| rocket_tornado | wait | elixir | elixir < 8 | 49 | -0.009 | [-0.092, +0.073] |
| rocket_tornado | wait | elixir | elixir >= 8 | 92 | +0.029 | [-0.039, +0.098] |
| rocket_tornado | wait | opp | exploiter | 77 | -0.020 | [-0.082, +0.042] |
| rocket_tornado | wait | opp | exploiter_league | 34 | +0.156 * | [+0.039, +0.270] |
| rocket_tornado | wait | opp | init | 30 | -0.049 | [-0.142, +0.040] |
| rocket_tornado | wait | opp_bank | bank<2 | 64 | -0.004 | [-0.093, +0.083] |
| rocket_tornado | wait | opp_bank | bank>=2 | 77 | +0.033 | [-0.020, +0.088] |
| rocket_tornado | wait | policy | policy played | 141 | +0.016 | [-0.035, +0.067] |
| rocket_tornado | wait | threat | foe on our half | 54 | -0.019 | [-0.087, +0.048] |
| rocket_tornado | wait | threat | no foe body on our half | 87 | +0.038 | [-0.027, +0.106] |
| rocket_tornado | wait | value_combo | 6-8 | 67 | +0.022 | [-0.054, +0.100] |
| rocket_tornado | wait | value_combo | 8+ | 74 | +0.011 | [-0.052, +0.074] |
| rocket_tornado | wait | value_rocket_clump | 4-6 | 70 | +0.039 | [-0.035, +0.112] |
| rocket_tornado | wait | value_rocket_clump | 6-8 | 49 | -0.011 | [-0.092, +0.065] |
| rocket_tornado | wait | value_rocket_clump | 8+ | 16 | +0.005 | [-0.172, +0.183] |
| rocket_tornado | wait | xbow_hand | no xbow in hand | 53 | +0.001 | [-0.087, +0.095] |
| rocket_tornado | wait | xbow_hand | xbow in hand | 88 | +0.025 | [-0.033, +0.083] |
| tornado_redirect | tornado_king | counter | counter in hand | 188 | -0.079 * | [-0.123, -0.039] |
| tornado_redirect | tornado_king | dist | dist 6+ | 129 | -0.061 * | [-0.109, -0.012] |
| tornado_redirect | tornado_king | dist | dist < 6 | 59 | -0.117 * | [-0.204, -0.034] |
| tornado_redirect | tornado_king | elixir | elixir < 8 | 178 | -0.068 * | [-0.112, -0.024] |
| tornado_redirect | tornado_king | elixir | elixir >= 8 | 10 | -0.275 * | [-0.419, -0.134] |
| tornado_redirect | tornado_king | opp | exploiter | 103 | -0.102 * | [-0.154, -0.051] |
| tornado_redirect | tornado_king | opp | exploiter_league | 38 | -0.081 | [-0.177, +0.017] |
| tornado_redirect | tornado_king | opp | init | 47 | -0.026 | [-0.125, +0.072] |
| tornado_redirect | tornado_king | opp_bank | bank<2 | 78 | -0.157 * | [-0.223, -0.095] |
| tornado_redirect | tornado_king | opp_bank | bank>=2 | 110 | -0.023 | [-0.077, +0.035] |
| tornado_redirect | tornado_king | policy | policy played | 31 | -0.120 * | [-0.229, -0.015] |
| tornado_redirect | tornado_king | policy | policy waited | 157 | -0.071 * | [-0.117, -0.023] |
| tornado_redirect | tornado_king | safe_idle | safe & idle (no foe on our half, policy waited) | 29 | +0.004 | [-0.118, +0.124] |
| tornado_redirect | tornado_king | target | hoglike battleram | 11 | -0.005 | [-0.153, +0.142] |
| tornado_redirect | tornado_king | target | other barbarians | 10 | -0.094 | [-0.283, +0.121] |
| tornado_redirect | tornado_king | target | other skeletons | 21 | -0.080 | [-0.209, +0.058] |
| tornado_redirect | tornado_king | target_class | hoglike | 31 | -0.024 | [-0.109, +0.054] |
| tornado_redirect | tornado_king | target_class | other | 149 | -0.096 * | [-0.143, -0.048] |
| tornado_redirect | tornado_king | threat | foe on our half | 151 | -0.095 * | [-0.140, -0.051] |
| tornado_redirect | tornado_king | threat | no foe body on our half | 37 | -0.014 | [-0.110, +0.086] |
| tornado_redirect | tornado_king | xbow_hand | no xbow in hand | 88 | -0.041 | [-0.109, +0.030] |
| tornado_redirect | tornado_king | xbow_hand | xbow in hand | 100 | -0.112 * | [-0.170, -0.058] |
| tornado_redirect | tornado_on | counter | counter in hand | 188 | -0.066 * | [-0.104, -0.029] |
| tornado_redirect | tornado_on | dist | dist 6+ | 129 | -0.072 * | [-0.121, -0.022] |
| tornado_redirect | tornado_on | dist | dist < 6 | 59 | -0.054 | [-0.113, +0.007] |
| tornado_redirect | tornado_on | elixir | elixir < 8 | 178 | -0.057 * | [-0.097, -0.019] |
| tornado_redirect | tornado_on | elixir | elixir >= 8 | 10 | -0.221 * | [-0.400, -0.063] |
| tornado_redirect | tornado_on | opp | exploiter | 103 | -0.070 * | [-0.118, -0.026] |
| tornado_redirect | tornado_on | opp | exploiter_league | 38 | -0.063 | [-0.171, +0.045] |
| tornado_redirect | tornado_on | opp | init | 47 | -0.060 | [-0.133, +0.020] |
| tornado_redirect | tornado_on | opp_bank | bank<2 | 78 | -0.063 * | [-0.125, -0.003] |
| tornado_redirect | tornado_on | opp_bank | bank>=2 | 110 | -0.068 * | [-0.117, -0.020] |
| tornado_redirect | tornado_on | policy | policy played | 31 | -0.125 * | [-0.238, -0.025] |
| tornado_redirect | tornado_on | policy | policy waited | 157 | -0.054 * | [-0.095, -0.012] |
| tornado_redirect | tornado_on | safe_idle | safe & idle (no foe on our half, policy waited) | 29 | -0.013 | [-0.134, +0.115] |
| tornado_redirect | tornado_on | target | hoglike battleram | 11 | -0.036 | [-0.139, +0.090] |
| tornado_redirect | tornado_on | target | other barbarians | 10 | -0.125 | [-0.271, +0.017] |
| tornado_redirect | tornado_on | target | other skeletons | 21 | -0.186 * | [-0.318, -0.059] |
| tornado_redirect | tornado_on | target_class | hoglike | 31 | -0.042 | [-0.095, +0.018] |
| tornado_redirect | tornado_on | target_class | other | 149 | -0.079 * | [-0.125, -0.032] |
| tornado_redirect | tornado_on | threat | foe on our half | 151 | -0.077 * | [-0.116, -0.040] |
| tornado_redirect | tornado_on | threat | no foe body on our half | 37 | -0.019 | [-0.112, +0.086] |
| tornado_redirect | tornado_on | xbow_hand | no xbow in hand | 88 | -0.027 | [-0.084, +0.031] |
| tornado_redirect | tornado_on | xbow_hand | xbow in hand | 100 | -0.100 * | [-0.154, -0.051] |
| tornado_redirect | wait | counter | counter in hand | 31 | +0.013 | [-0.109, +0.127] |
| tornado_redirect | wait | dist | dist 6+ | 23 | -0.017 | [-0.160, +0.139] |
| tornado_redirect | wait | elixir | elixir < 8 | 30 | +0.023 | [-0.101, +0.138] |
| tornado_redirect | wait | opp | exploiter | 21 | +0.002 | [-0.117, +0.135] |
| tornado_redirect | wait | opp_bank | bank<2 | 13 | -0.077 | [-0.283, +0.086] |
| tornado_redirect | wait | opp_bank | bank>=2 | 18 | +0.077 | [-0.066, +0.243] |
| tornado_redirect | wait | policy | policy played | 31 | +0.013 | [-0.109, +0.127] |
| tornado_redirect | wait | target_class | other | 24 | +0.038 | [-0.105, +0.184] |
| tornado_redirect | wait | threat | foe on our half | 23 | +0.058 | [-0.072, +0.182] |
| tornado_redirect | wait | xbow_hand | no xbow in hand | 21 | +0.015 | [-0.129, +0.153] |
| tornado_redirect | wait | xbow_hand | xbow in hand | 10 | +0.008 | [-0.201, +0.207] |
| xbow_after_fail | rocket_empty | elixir | elixir < 8 | 140 | -0.244 * | [-0.303, -0.187] |
| xbow_after_fail | rocket_empty | opp | exploiter | 72 | -0.324 * | [-0.412, -0.240] |
| xbow_after_fail | rocket_empty | opp | exploiter_league | 48 | -0.206 * | [-0.306, -0.109] |
| xbow_after_fail | rocket_empty | opp | init | 29 | -0.184 * | [-0.280, -0.097] |
| xbow_after_fail | rocket_empty | opp_bank | bank<2 | 65 | -0.326 * | [-0.412, -0.249] |
| xbow_after_fail | rocket_empty | opp_bank | bank>=2 | 84 | -0.206 * | [-0.280, -0.136] |
| xbow_after_fail | rocket_empty | policy | policy played | 18 | -0.275 * | [-0.407, -0.138] |
| xbow_after_fail | rocket_empty | policy | policy waited | 131 | -0.256 * | [-0.319, -0.198] |
| xbow_after_fail | rocket_empty | safe_idle | safe & idle (no foe on our half, policy waited) | 85 | -0.296 * | [-0.375, -0.222] |
| xbow_after_fail | rocket_empty | threat | foe on our half | 58 | -0.204 * | [-0.280, -0.130] |
| xbow_after_fail | rocket_empty | threat | no foe body on our half | 91 | -0.293 * | [-0.367, -0.222] |
| xbow_after_fail | rocket_empty | xbow_hand | xbow in hand | 149 | -0.259 * | [-0.317, -0.205] |
| xbow_after_fail | rocket_princess | elixir | elixir < 8 | 177 | -0.211 * | [-0.263, -0.159] |
| xbow_after_fail | rocket_princess | elixir | elixir >= 8 | 11 | -0.390 * | [-0.547, -0.248] |
| xbow_after_fail | rocket_princess | opp | exploiter | 100 | -0.260 * | [-0.330, -0.194] |
| xbow_after_fail | rocket_princess | opp | exploiter_league | 57 | -0.203 * | [-0.309, -0.095] |
| xbow_after_fail | rocket_princess | opp | init | 31 | -0.133 * | [-0.215, -0.061] |
| xbow_after_fail | rocket_princess | opp_bank | bank<2 | 88 | -0.301 * | [-0.382, -0.226] |
| xbow_after_fail | rocket_princess | opp_bank | bank>=2 | 100 | -0.152 * | [-0.212, -0.092] |
| xbow_after_fail | rocket_princess | policy | policy played | 27 | -0.228 * | [-0.334, -0.133] |
| xbow_after_fail | rocket_princess | policy | policy waited | 161 | -0.221 * | [-0.276, -0.168] |
| xbow_after_fail | rocket_princess | safe_idle | safe & idle (no foe on our half, policy waited) | 103 | -0.256 * | [-0.328, -0.190] |
| xbow_after_fail | rocket_princess | threat | foe on our half | 76 | -0.185 * | [-0.256, -0.114] |
| xbow_after_fail | rocket_princess | threat | no foe body on our half | 112 | -0.247 * | [-0.315, -0.182] |
| xbow_after_fail | rocket_princess | xbow_hand | xbow in hand | 188 | -0.222 * | [-0.273, -0.172] |
| xbow_after_fail | wait | elixir | elixir < 8 | 25 | +0.049 | [-0.066, +0.169] |
| xbow_after_fail | wait | opp | exploiter | 14 | +0.073 | [-0.047, +0.215] |
| xbow_after_fail | wait | opp | init | 10 | -0.014 | [-0.154, +0.117] |
| xbow_after_fail | wait | opp_bank | bank<2 | 12 | +0.061 | [-0.063, +0.166] |
| xbow_after_fail | wait | opp_bank | bank>=2 | 16 | -0.018 | [-0.190, +0.173] |
| xbow_after_fail | wait | policy | policy played | 28 | +0.016 | [-0.103, +0.134] |
| xbow_after_fail | wait | threat | foe on our half | 19 | -0.025 | [-0.170, +0.123] |
| xbow_after_fail | wait | xbow_hand | xbow in hand | 28 | +0.016 | [-0.103, +0.134] |
| xbow_after_fail | xbow_defensive | elixir | elixir < 8 | 180 | -0.106 * | [-0.149, -0.064] |
| xbow_after_fail | xbow_defensive | elixir | elixir >= 8 | 11 | -0.052 | [-0.246, +0.104] |
| xbow_after_fail | xbow_defensive | opp | exploiter | 104 | -0.146 * | [-0.207, -0.087] |
| xbow_after_fail | xbow_defensive | opp | exploiter_league | 57 | -0.050 | [-0.119, +0.019] |
| xbow_after_fail | xbow_defensive | opp | init | 30 | -0.051 | [-0.116, +0.008] |
| xbow_after_fail | xbow_defensive | opp_bank | bank<2 | 88 | -0.138 * | [-0.205, -0.076] |
| xbow_after_fail | xbow_defensive | opp_bank | bank>=2 | 103 | -0.072 * | [-0.123, -0.022] |
| xbow_after_fail | xbow_defensive | policy | policy played | 27 | -0.178 * | [-0.289, -0.081] |
| xbow_after_fail | xbow_defensive | policy | policy waited | 164 | -0.090 * | [-0.134, -0.049] |
| xbow_after_fail | xbow_defensive | safe_idle | safe & idle (no foe on our half, policy waited) | 105 | -0.088 * | [-0.143, -0.038] |
| xbow_after_fail | xbow_defensive | threat | foe on our half | 78 | -0.118 * | [-0.185, -0.060] |
| xbow_after_fail | xbow_defensive | threat | no foe body on our half | 113 | -0.092 * | [-0.146, -0.040] |
| xbow_after_fail | xbow_defensive | xbow_hand | xbow in hand | 191 | -0.103 * | [-0.143, -0.061] |
| xbow_after_fail | xbow_reach | elixir | elixir < 8 | 163 | -0.014 | [-0.064, +0.033] |
| xbow_after_fail | xbow_reach | opp | exploiter | 95 | -0.039 | [-0.110, +0.023] |
| xbow_after_fail | xbow_reach | opp | exploiter_league | 54 | +0.000 | [-0.077, +0.083] |
| xbow_after_fail | xbow_reach | opp | init | 23 | +0.027 | [-0.052, +0.121] |
| xbow_after_fail | xbow_reach | opp_bank | bank<2 | 80 | -0.031 | [-0.100, +0.037] |
| xbow_after_fail | xbow_reach | opp_bank | bank>=2 | 92 | -0.006 | [-0.069, +0.057] |
| xbow_after_fail | xbow_reach | policy | policy waited | 164 | -0.013 | [-0.059, +0.031] |
| xbow_after_fail | xbow_reach | safe_idle | safe & idle (no foe on our half, policy waited) | 105 | -0.004 | [-0.066, +0.055] |
| xbow_after_fail | xbow_reach | threat | foe on our half | 64 | -0.039 | [-0.104, +0.025] |
| xbow_after_fail | xbow_reach | threat | no foe body on our half | 108 | -0.005 | [-0.069, +0.056] |
| xbow_after_fail | xbow_reach | xbow_hand | xbow in hand | 172 | -0.018 | [-0.063, +0.026] |

### Horizon profile: mean dQ (alt - chosen), same samples in every column (terminal = audited samples only)


| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| def_xbow | wait | yes | 35 | +0.053 [-0.04, +0.15] | -0.021 [-0.06, +0.01] | -0.038 [-0.09, +0.01] | +0.001 [-0.07, +0.07] | +0.026 [-0.05, +0.10] | +0.023 [-0.06, +0.11] | +0.098 [-0.10, +0.31] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| def_xbow | wait | no | 109 | +0.013 [-0.04, +0.07] | -0.013 [-0.03, -0.00] | -0.034 [-0.06, -0.01] | -0.034 [-0.07, -0.00] | -0.032 [-0.07, +0.00] | -0.019 [-0.06, +0.02] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| def_xbow | xbow_def_tile | yes | 35 | -0.131 [-0.24, -0.04] | -0.027 [-0.06, +0.00] | -0.098 [-0.14, -0.06] | -0.154 [-0.22, -0.10] | -0.145 [-0.21, -0.08] | -0.158 [-0.24, -0.09] | +0.040 [-0.17, +0.26] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| def_xbow | xbow_def_tile | no | 109 | -0.078 [-0.13, -0.02] | -0.014 [-0.03, +0.00] | -0.066 [-0.09, -0.04] | -0.125 [-0.15, -0.10] | -0.131 [-0.17, -0.09] | -0.102 [-0.14, -0.06] |
| def_xbow | xbow_reach_lane | no | 19 | -0.054 [-0.15, +0.04] | -0.023 [-0.05, -0.00] | -0.004 [-0.05, +0.04] | -0.008 [-0.07, +0.05] | -0.006 [-0.07, +0.05] | +0.006 [-0.06, +0.07] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_clump | yes | 63 | -0.124 [-0.21, -0.04] | -0.102 [-0.13, -0.07] | -0.121 [-0.16, -0.08] | -0.174 [-0.22, -0.12] | -0.174 [-0.24, -0.11] | -0.159 [-0.23, -0.09] | -0.006 [-0.20, +0.19] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_clump | no | 177 | -0.209 [-0.26, -0.16] | -0.114 [-0.13, -0.10] | -0.132 [-0.16, -0.11] | -0.181 [-0.22, -0.15] | -0.195 [-0.24, -0.15] | -0.206 [-0.25, -0.16] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_empty | yes | 103 | -0.329 [-0.40, -0.27] | -0.174 [-0.19, -0.15] | -0.202 [-0.23, -0.18] | -0.261 [-0.30, -0.22] | -0.282 [-0.34, -0.23] | -0.325 [-0.38, -0.27] | -0.243 [-0.39, -0.10] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_empty | no | 297 | -0.349 [-0.39, -0.31] | -0.187 [-0.20, -0.17] | -0.219 [-0.24, -0.20] | -0.272 [-0.30, -0.25] | -0.297 [-0.33, -0.26] | -0.332 [-0.37, -0.29] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_princess | yes | 112 | -0.180 [-0.23, -0.13] | -0.091 [-0.11, -0.07] | -0.114 [-0.14, -0.09] | -0.166 [-0.20, -0.14] | -0.172 [-0.21, -0.13] | -0.188 [-0.23, -0.14] | -0.087 [-0.24, +0.06] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_princess | no | 327 | -0.245 [-0.28, -0.21] | -0.104 [-0.11, -0.09] | -0.132 [-0.15, -0.11] | -0.176 [-0.20, -0.15] | -0.204 [-0.23, -0.18] | -0.228 [-0.26, -0.20] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_cycle | rocket_empty | yes | 42 | -0.048 [-0.20, +0.11] | -0.018 [-0.04, +0.00] | -0.022 [-0.06, +0.01] | -0.035 [-0.08, +0.01] | -0.069 [-0.13, -0.01] | -0.090 [-0.16, -0.02] | -0.044 [-0.29, +0.18] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_cycle | rocket_empty | no | 122 | -0.072 [-0.16, +0.02] | -0.026 [-0.04, -0.01] | -0.044 [-0.07, -0.02] | -0.041 [-0.07, -0.01] | -0.064 [-0.11, -0.02] | -0.060 [-0.11, -0.01] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_cycle | rocket_princess | yes | 71 | -0.027 [-0.14, +0.09] | -0.011 [-0.03, +0.00] | -0.023 [-0.06, +0.01] | -0.049 [-0.08, -0.02] | -0.039 [-0.09, +0.01] | -0.034 [-0.09, +0.02] | -0.001 [-0.17, +0.15] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_cycle | rocket_princess | no | 230 | -0.088 [-0.16, -0.01] | -0.012 [-0.02, -0.00] | -0.037 [-0.05, -0.02] | -0.057 [-0.08, -0.04] | -0.066 [-0.10, -0.04] | -0.068 [-0.10, -0.03] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_played | second_card | yes | 21 | -0.010 [-0.11, +0.10] | -0.012 [-0.05, +0.03] | -0.010 [-0.06, +0.04] | -0.053 [-0.12, +0.03] | -0.017 [-0.09, +0.07] | -0.026 [-0.12, +0.07] | +0.092 [-0.34, +0.57] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_played | second_card | no | 70 | -0.086 [-0.18, -0.00] | -0.017 [-0.04, +0.01] | -0.049 [-0.08, -0.01] | -0.075 [-0.13, -0.02] | -0.082 [-0.14, -0.02] | -0.081 [-0.16, -0.01] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_played | wait | yes | 21 | +0.085 [-0.02, +0.20] | +0.018 [-0.01, +0.05] | +0.058 [+0.01, +0.11] | +0.097 [+0.03, +0.17] | +0.073 [-0.00, +0.15] | +0.063 [-0.02, +0.16] | +0.032 [-0.28, +0.37] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_played | wait | no | 70 | +0.052 [-0.01, +0.12] | +0.004 [-0.01, +0.02] | +0.015 [-0.01, +0.04] | +0.046 [+0.01, +0.09] | +0.017 [-0.02, +0.06] | +0.049 [-0.01, +0.11] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | combo | yes | 65 | -0.361 [-0.47, -0.26] | -0.177 [-0.22, -0.14] | -0.285 [-0.35, -0.23] | -0.293 [-0.36, -0.23] | -0.331 [-0.42, -0.25] | -0.348 [-0.46, -0.25] | -0.031 [-0.25, +0.18] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | combo | no | 220 | -0.347 [-0.40, -0.29] | -0.183 [-0.20, -0.16] | -0.260 [-0.29, -0.23] | -0.288 [-0.33, -0.25] | -0.304 [-0.35, -0.26] | -0.335 [-0.39, -0.28] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | rocket_clump | yes | 65 | -0.313 [-0.41, -0.22] | -0.156 [-0.19, -0.12] | -0.211 [-0.26, -0.17] | -0.246 [-0.30, -0.19] | -0.296 [-0.37, -0.22] | -0.302 [-0.40, -0.21] | -0.033 [-0.24, +0.17] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | rocket_clump | no | 220 | -0.302 [-0.36, -0.25] | -0.142 [-0.16, -0.12] | -0.197 [-0.23, -0.17] | -0.242 [-0.28, -0.20] | -0.265 [-0.31, -0.22] | -0.286 [-0.34, -0.23] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | wait | yes | 35 | -0.001 [-0.08, +0.08] | +0.011 [-0.01, +0.03] | -0.019 [-0.06, +0.01] | -0.024 [-0.07, +0.02] | -0.029 [-0.09, +0.04] | -0.029 [-0.11, +0.06] | +0.151 [-0.04, +0.36] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | wait | no | 113 | +0.038 [-0.02, +0.09] | -0.001 [-0.01, +0.01] | -0.013 [-0.04, +0.01] | +0.002 [-0.03, +0.03] | +0.014 [-0.02, +0.05] | +0.021 [-0.03, +0.07] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| tornado_redirect | tornado_king | yes | 54 | -0.077 [-0.14, -0.02] | -0.119 [-0.15, -0.09] | -0.101 [-0.14, -0.06] | -0.080 [-0.13, -0.03] | -0.086 [-0.15, -0.03] | -0.089 [-0.15, -0.03] | -0.084 [-0.30, +0.14] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| tornado_redirect | tornado_king | no | 175 | -0.073 [-0.11, -0.03] | -0.093 [-0.11, -0.08] | -0.104 [-0.12, -0.08] | -0.088 [-0.11, -0.06] | -0.091 [-0.12, -0.06] | -0.080 [-0.11, -0.04] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| tornado_redirect | tornado_on | yes | 54 | -0.072 [-0.14, +0.01] | -0.114 [-0.14, -0.09] | -0.089 [-0.13, -0.06] | -0.059 [-0.11, -0.01] | -0.065 [-0.12, -0.01] | -0.078 [-0.14, -0.02] | -0.187 [-0.39, +0.03] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| tornado_redirect | tornado_on | no | 175 | -0.060 [-0.10, -0.02] | -0.075 [-0.09, -0.06] | -0.091 [-0.11, -0.07] | -0.069 [-0.09, -0.05] | -0.070 [-0.10, -0.04] | -0.064 [-0.10, -0.03] |
| tornado_redirect | wait | no | 27 | -0.020 [-0.14, +0.09] | -0.003 [-0.03, +0.02] | -0.014 [-0.04, +0.02] | -0.057 [-0.13, +0.01] | -0.027 [-0.12, +0.07] | +0.020 [-0.09, +0.13] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | rocket_empty | yes | 45 | -0.272 [-0.35, -0.18] | -0.154 [-0.19, -0.12] | -0.146 [-0.19, -0.10] | -0.185 [-0.25, -0.12] | -0.241 [-0.31, -0.17] | -0.266 [-0.35, -0.18] | -0.170 [-0.37, +0.03] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | rocket_empty | no | 132 | -0.263 [-0.32, -0.21] | -0.153 [-0.17, -0.13] | -0.176 [-0.21, -0.15] | -0.217 [-0.26, -0.18] | -0.252 [-0.30, -0.20] | -0.265 [-0.32, -0.21] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | rocket_princess | yes | 53 | -0.271 [-0.36, -0.18] | -0.069 [-0.10, -0.04] | -0.108 [-0.16, -0.06] | -0.145 [-0.21, -0.08] | -0.217 [-0.29, -0.14] | -0.267 [-0.36, -0.18] | -0.337 [-0.57, -0.11] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | rocket_princess | no | 159 | -0.232 [-0.29, -0.18] | -0.065 [-0.08, -0.05] | -0.102 [-0.13, -0.08] | -0.156 [-0.19, -0.12] | -0.197 [-0.24, -0.15] | -0.223 [-0.27, -0.17] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | wait | yes | 10 | +0.043 [-0.07, +0.16] | -0.009 [-0.05, +0.03] | -0.084 [-0.23, +0.01] | -0.092 [-0.20, +0.02] | -0.065 [-0.17, +0.04] | +0.030 [-0.08, +0.14] | -0.012 [-0.40, +0.38] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | wait | no | 20 | -0.024 [-0.12, +0.07] | -0.018 [-0.05, +0.01] | -0.060 [-0.14, -0.00] | -0.037 [-0.12, +0.04] | -0.056 [-0.13, +0.01] | +0.002 [-0.08, +0.08] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | xbow_defensive | yes | 53 | -0.148 [-0.24, -0.07] | -0.021 [-0.04, +0.00] | -0.030 [-0.07, +0.01] | -0.067 [-0.12, -0.02] | -0.093 [-0.15, -0.04] | -0.131 [-0.22, -0.05] | -0.061 [-0.24, +0.11] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | xbow_defensive | no | 162 | -0.098 [-0.14, -0.06] | -0.019 [-0.03, -0.01] | -0.022 [-0.04, -0.00] | -0.058 [-0.09, -0.03] | -0.072 [-0.11, -0.04] | -0.093 [-0.13, -0.05] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | xbow_reach | yes | 45 | +0.023 [-0.07, +0.12] | +0.005 [-0.03, +0.04] | +0.015 [-0.04, +0.07] | +0.049 [-0.01, +0.12] | +0.029 [-0.05, +0.11] | +0.016 [-0.07, +0.11] | -0.000 [-0.19, +0.19] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | xbow_reach | no | 149 | -0.014 [-0.06, +0.04] | -0.016 [-0.03, +0.00] | +0.005 [-0.02, +0.03] | +0.001 [-0.03, +0.04] | -0.020 [-0.06, +0.02] | -0.018 [-0.07, +0.03] |

### Where dQ comes from (main stop, alt - chosen): Phi (towers) vs critic vs snapshot and play-count differences

| trigger | alternative | dQ | dPhi | dCritic | d own princess lost | d own king lost | d FOE princess lost | d foe king lost | d own crowns lost | d foe crowns lost | d own elixir | d foe elixir | d own plays | d FOE plays | d own king on | d foe king on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| def_xbow | wait (n 126) | +0.042 [-0.01, +0.09] | +0.002 [-0.03, +0.04] | +0.025 [-0.02, +0.07] | -0.003 [-0.03, +0.03] | +0.001 [-0.00, +0.00] | +0.015 [-0.03, +0.07] | -0.001 [-0.00, +0.00] | +0.023 [-0.01, +0.06] | +0.031 [-0.02, +0.08] | +0.357 [+0.05, +0.67] | +0.101 [-0.28, +0.49] | -0.054 [-0.24, +0.12] | -0.146 [-0.40, +0.11] | +0.031 [-0.02, +0.08] | +0.031 [-0.02, +0.08] |
| def_xbow | xbow_def_tile (n 126) | -0.074 [-0.13, -0.02] | -0.068 [-0.10, -0.03] | -0.067 [-0.12, -0.02] | +0.024 [-0.01, +0.06] | +0.005 [+0.00, +0.01] | -0.121 [-0.18, -0.06] | +0.001 [+0.00, +0.00] | +0.015 [-0.01, +0.04] | -0.045 [-0.09, +0.00] | +0.176 [-0.23, +0.59] | -0.131 [-0.47, +0.19] | -0.142 [-0.33, +0.05] | -0.127 [-0.38, +0.14] | +0.022 [-0.02, +0.06] | -0.045 [-0.09, +0.00] |
| rocket | rocket_clump (n 193) | -0.197 [-0.25, -0.15] | -0.112 [-0.14, -0.09] | -0.139 [-0.18, -0.10] | +0.135 [+0.09, +0.18] | +0.028 [+0.01, +0.05] | -0.087 [-0.12, -0.06] | +0.003 [+0.00, +0.01] | +0.082 [+0.03, +0.14] | -0.036 [-0.06, -0.01] | -0.243 [-0.51, +0.02] | -0.083 [-0.32, +0.19] | -0.392 [-0.52, -0.27] | -0.098 [-0.20, +0.01] | +0.056 [+0.01, +0.10] | +0.007 [-0.03, +0.04] |
| rocket | rocket_empty (n 317) | -0.321 [-0.36, -0.28] | -0.156 [-0.18, -0.14] | -0.234 [-0.26, -0.20] | +0.201 [+0.17, +0.23] | +0.029 [+0.02, +0.04] | -0.146 [-0.17, -0.12] | -0.000 [-0.00, +0.00] | +0.125 [+0.09, +0.16] | -0.050 [-0.08, -0.03] | -0.266 [-0.48, -0.06] | -0.075 [-0.28, +0.12] | -0.343 [-0.45, -0.24] | -0.114 [-0.20, -0.03] | +0.131 [+0.10, +0.16] | -0.047 [-0.07, -0.02] |
| rocket | rocket_princess (n 349) | -0.230 [-0.26, -0.20] | -0.103 [-0.12, -0.09] | -0.170 [-0.20, -0.14] | +0.177 [+0.15, +0.21] | +0.024 [+0.01, +0.04] | -0.053 [-0.08, -0.03] | -0.000 [-0.00, +0.00] | +0.080 [+0.05, +0.11] | -0.031 [-0.05, -0.01] | -0.306 [-0.51, -0.11] | -0.149 [-0.35, +0.05] | -0.272 [-0.36, -0.18] | -0.137 [-0.23, -0.04] | +0.091 [+0.06, +0.12] | -0.026 [-0.04, -0.01] |
| rocket_played | second_card (n 89) | -0.068 [-0.15, +0.01] | -0.029 [-0.07, +0.01] | -0.038 [-0.08, +0.01] | +0.047 [-0.00, +0.10] | -0.010 [-0.02, +0.00] | -0.039 [-0.07, -0.01] | +0.000 [+0.00, +0.00] | -0.008 [-0.05, +0.03] | -0.008 [-0.05, +0.03] | +0.243 [-0.23, +0.73] | +0.433 [+0.08, +0.79] | +0.823 [+0.59, +1.06] | -0.023 [-0.18, +0.13] | +0.000 [-0.05, +0.05] | -0.008 [-0.05, +0.03] |
| rocket_played | wait (n 89) | +0.040 [-0.03, +0.11] | +0.016 [-0.01, +0.04] | +0.036 [-0.01, +0.08] | -0.061 [-0.10, -0.02] | -0.009 [-0.03, +0.01] | -0.036 [-0.06, -0.01] | +0.001 [-0.00, +0.00] | -0.023 [-0.07, +0.01] | +0.000 [-0.04, +0.04] | +0.102 [-0.30, +0.54] | +0.438 [+0.04, +0.85] | +0.180 [+0.01, +0.36] | +0.000 [-0.18, +0.18] | -0.047 [-0.11, +0.01] | +0.000 [-0.04, +0.04] |
| rocket_tornado | combo (n 256) | -0.335 [-0.38, -0.29] | -0.171 [-0.20, -0.15] | -0.218 [-0.25, -0.18] | +0.189 [+0.15, +0.23] | +0.035 [+0.02, +0.06] | -0.118 [-0.15, -0.09] | +0.001 [-0.00, +0.00] | +0.120 [+0.06, +0.18] | -0.054 [-0.08, -0.03] | +0.026 [-0.23, +0.27] | +0.217 [-0.01, +0.44] | -0.342 [-0.46, -0.22] | -0.198 [-0.30, -0.09] | +0.090 [+0.05, +0.13] | +0.185 [+0.12, +0.25] |
| rocket_tornado | rocket_clump (n 256) | -0.297 [-0.35, -0.25] | -0.158 [-0.19, -0.13] | -0.214 [-0.25, -0.18] | +0.166 [+0.12, +0.21] | +0.029 [+0.01, +0.05] | -0.143 [-0.18, -0.11] | +0.009 [+0.01, +0.01] | +0.098 [+0.06, +0.14] | -0.049 [-0.08, -0.02] | -0.013 [-0.26, +0.24] | -0.043 [-0.27, +0.18] | -0.443 [-0.56, -0.32] | -0.141 [-0.26, -0.02] | +0.073 [+0.03, +0.11] | +0.082 [+0.04, +0.13] |
| rocket_tornado | wait (n 141) | +0.016 [-0.03, +0.07] | +0.015 [-0.01, +0.04] | +0.025 [-0.02, +0.07] | -0.002 [-0.05, +0.05] | +0.004 [-0.02, +0.02] | +0.001 [-0.04, +0.04] | +0.003 [-0.00, +0.01] | -0.015 [-0.08, +0.04] | +0.015 [-0.01, +0.04] | +0.127 [-0.17, +0.41] | +0.175 [-0.14, +0.51] | -0.143 [-0.30, +0.01] | -0.128 [-0.25, -0.01] | -0.020 [-0.06, +0.02] | +0.010 [-0.02, +0.04] |
| tornado_redirect | tornado_king (n 188) | -0.079 [-0.12, -0.04] | -0.034 [-0.05, -0.02] | -0.039 [-0.07, -0.01] | +0.038 [+0.01, +0.06] | -0.001 [-0.00, +0.00] | -0.050 [-0.08, -0.02] | +0.000 [-0.00, +0.00] | -0.007 [-0.03, +0.01] | +0.020 [+0.01, +0.04] | +0.023 [-0.22, +0.28] | +0.037 [-0.19, +0.26] | +0.154 [+0.04, +0.27] | -0.111 [-0.25, +0.03] | -0.003 [-0.03, +0.03] | +0.023 [+0.01, +0.04] |
| tornado_redirect | tornado_on (n 188) | -0.066 [-0.10, -0.03] | -0.033 [-0.05, -0.02] | -0.040 [-0.07, -0.01] | +0.025 [+0.00, +0.05] | -0.002 [-0.00, +0.00] | -0.056 [-0.08, -0.03] | -0.001 [-0.00, +0.00] | +0.003 [-0.02, +0.03] | +0.007 [-0.01, +0.02] | -0.071 [-0.32, +0.18] | -0.066 [-0.31, +0.16] | +0.184 [+0.08, +0.30] | -0.102 [-0.25, +0.03] | -0.016 [-0.05, +0.02] | +0.007 [-0.01, +0.02] |
| tornado_redirect | wait (n 31) | +0.013 [-0.11, +0.13] | +0.046 [-0.04, +0.15] | +0.003 [-0.11, +0.12] | -0.008 [-0.06, +0.04] | +0.019 [+0.00, +0.06] | +0.065 [-0.07, +0.22] | +0.000 [+0.00, +0.00] | +0.056 [+0.00, +0.17] | +0.083 [+0.03, +0.16] | +0.177 [-0.53, +0.81] | -0.296 [-1.02, +0.38] | -0.083 [-0.34, +0.21] | +0.194 [-0.18, +0.58] | +0.000 [+0.00, +0.00] | +0.083 [+0.03, +0.16] |
| xbow_after_fail | rocket_empty (n 149) | -0.259 [-0.32, -0.20] | -0.125 [-0.15, -0.10] | -0.164 [-0.21, -0.12] | +0.143 [+0.10, +0.19] | +0.005 [-0.00, +0.01] | -0.116 [-0.16, -0.07] | +0.000 [+0.00, +0.00] | +0.062 [+0.03, +0.10] | -0.019 [-0.05, +0.00] | -0.331 [-0.65, -0.02] | -0.290 [-0.61, -0.00] | -0.062 [-0.21, +0.09] | -0.019 [-0.18, +0.14] | +0.076 [+0.03, +0.13] | -0.019 [-0.05, +0.00] |
| xbow_after_fail | rocket_princess (n 188) | -0.222 [-0.27, -0.17] | -0.099 [-0.13, -0.07] | -0.152 [-0.19, -0.11] | +0.162 [+0.12, +0.21] | +0.020 [+0.01, +0.04] | -0.040 [-0.07, -0.01] | +0.000 [+0.00, +0.00] | +0.110 [+0.06, +0.16] | -0.012 [-0.04, +0.01] | -0.205 [-0.50, +0.07] | -0.178 [-0.44, +0.08] | -0.154 [-0.29, -0.02] | -0.059 [-0.19, +0.07] | +0.106 [+0.06, +0.15] | -0.012 [-0.04, +0.01] |
| xbow_after_fail | wait (n 28) | +0.016 [-0.10, +0.13] | +0.027 [-0.05, +0.11] | -0.002 [-0.11, +0.10] | +0.018 [-0.03, +0.06] | +0.001 [+0.00, +0.00] | +0.007 [-0.10, +0.12] | +0.000 [+0.00, +0.00] | +0.000 [+0.00, +0.00] | +0.000 [-0.15, +0.15] | -0.896 [-1.80, +0.06] | -0.536 [-1.23, +0.16] | +0.500 [+0.08, +0.92] | -0.038 [-0.46, +0.31] | +0.038 [+0.00, +0.12] | +0.000 [-0.15, +0.15] |
| xbow_after_fail | xbow_defensive (n 191) | -0.103 [-0.14, -0.06] | -0.048 [-0.07, -0.03] | -0.046 [-0.08, -0.02] | -0.001 [-0.02, +0.02] | +0.001 [-0.01, +0.01] | -0.107 [-0.14, -0.07] | -0.000 [-0.00, +0.00] | +0.004 [-0.02, +0.02] | -0.044 [-0.08, -0.01] | +0.056 [-0.21, +0.33] | -0.271 [-0.55, +0.01] | -0.146 [-0.26, -0.03] | +0.073 [-0.08, +0.23] | +0.018 [-0.01, +0.05] | -0.044 [-0.08, -0.01] |
| xbow_after_fail | xbow_reach (n 172) | -0.018 [-0.06, +0.03] | -0.004 [-0.03, +0.02] | -0.011 [-0.05, +0.02] | +0.031 [-0.00, +0.06] | -0.005 [-0.01, +0.00] | +0.020 [-0.02, +0.06] | +0.000 [+0.00, +0.00] | +0.024 [+0.00, +0.05] | -0.012 [-0.05, +0.02] | +0.107 [-0.19, +0.41] | -0.149 [-0.40, +0.10] | -0.068 [-0.21, +0.07] | +0.036 [-0.10, +0.17] | +0.048 [+0.01, +0.09] | -0.004 [-0.04, +0.03] |

### Contrasts between two alternatives (a - b), same columns

| trigger | alternative | dQ | dPhi | dCritic | d own princess lost | d own king lost | d FOE princess lost | d foe king lost | d own crowns lost | d foe crowns lost | d own elixir | d foe elixir | d own plays | d FOE plays | d own king on | d foe king on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| def_xbow | wait - xbow_def_tile (n 126) | +0.116 [+0.05, +0.17] | +0.069 [+0.02, +0.11] | +0.071 [+0.02, +0.13] | -0.012 [-0.05, +0.02] | -0.005 [-0.01, +0.00] | +0.137 [+0.07, +0.20] | -0.001 [-0.00, +0.00] | +0.023 [-0.03, +0.08] | +0.061 [+0.01, +0.11] | +0.192 [-0.29, +0.66] | +0.003 [-0.36, +0.37] | +0.205 [-0.00, +0.40] | +0.023 [-0.24, +0.31] | +0.038 [-0.03, +0.11] | +0.061 [+0.01, +0.11] |
| rocket | rocket_clump - rocket_empty (n 164) | +0.147 [+0.11, +0.18] | +0.064 [+0.04, +0.08] | +0.126 [+0.09, +0.16] | -0.122 [-0.16, -0.09] | -0.028 [-0.05, -0.01] | +0.035 [+0.02, +0.05] | +0.004 [+0.00, +0.01] | -0.125 [-0.17, -0.08] | +0.000 [-0.02, +0.02] | +0.076 [-0.13, +0.29] | +0.049 [-0.16, +0.25] | -0.090 [-0.20, +0.02] | -0.043 [-0.12, +0.04] | -0.117 [-0.16, -0.08] | +0.043 [+0.01, +0.08] |
| rocket | rocket_clump - rocket_princess (n 193) | +0.039 [+0.00, +0.08] | -0.001 [-0.02, +0.02] | +0.050 [+0.02, +0.08] | -0.069 [-0.10, -0.04] | -0.013 [-0.02, -0.00] | -0.057 [-0.07, -0.04] | +0.003 [+0.00, +0.01] | -0.046 [-0.08, -0.01] | -0.003 [-0.02, +0.01] | -0.069 [-0.29, +0.15] | +0.082 [-0.13, +0.30] | -0.076 [-0.17, +0.02] | +0.010 [-0.08, +0.10] | -0.066 [-0.10, -0.03] | +0.033 [+0.01, +0.06] |
| rocket | rocket_empty - rocket_princess (n 317) | -0.089 [-0.11, -0.06] | -0.050 [-0.06, -0.04] | -0.061 [-0.08, -0.04] | +0.023 [+0.00, +0.05] | +0.008 [+0.00, +0.02] | -0.090 [-0.10, -0.08] | +0.000 [-0.00, +0.00] | +0.045 [+0.02, +0.07] | -0.021 [-0.04, -0.00] | +0.058 [-0.09, +0.20] | +0.132 [-0.01, +0.28] | -0.113 [-0.18, -0.04] | +0.011 [-0.05, +0.08] | +0.032 [+0.01, +0.06] | -0.023 [-0.04, -0.00] |
| rocket_played | second_card - wait (n 89) | -0.109 [-0.18, -0.04] | -0.067 [-0.10, -0.04] | -0.085 [-0.13, -0.04] | +0.106 [+0.06, +0.16] | +0.003 [-0.01, +0.01] | -0.027 [-0.06, +0.01] | -0.001 [-0.00, +0.00] | +0.015 [-0.02, +0.05] | -0.023 [-0.05, +0.00] | +0.140 [-0.18, +0.47] | -0.009 [-0.37, +0.35] | +0.638 [+0.44, +0.85] | +0.008 [-0.17, +0.20] | +0.046 [-0.01, +0.10] | -0.023 [-0.05, +0.00] |
| rocket_tornado | combo - rocket_clump (n 256) | -0.039 [-0.08, +0.00] | -0.013 [-0.03, +0.01] | -0.005 [-0.04, +0.03] | +0.021 [-0.02, +0.06] | +0.009 [-0.01, +0.02] | +0.021 [+0.00, +0.04] | -0.008 [-0.01, -0.00] | +0.028 [-0.01, +0.07] | -0.008 [-0.03, +0.01] | +0.048 [-0.22, +0.30] | +0.269 [+0.04, +0.51] | +0.112 [+0.01, +0.23] | -0.101 [-0.20, -0.00] | +0.022 [-0.02, +0.06] | +0.087 [+0.03, +0.14] |
| rocket_tornado | combo - wait (n 141) | -0.355 [-0.43, -0.29] | -0.179 [-0.21, -0.14] | -0.234 [-0.28, -0.18] | +0.209 [+0.14, +0.27] | +0.027 [+0.00, +0.05] | -0.122 [-0.16, -0.08] | -0.003 [-0.01, +0.00] | +0.121 [+0.05, +0.18] | -0.074 [-0.12, -0.03] | +0.120 [-0.25, +0.49] | +0.256 [-0.02, +0.54] | -0.342 [-0.53, -0.16] | -0.147 [-0.28, -0.02] | +0.111 [+0.05, +0.17] | +0.137 [+0.05, +0.22] |
| rocket_tornado | rocket_clump - wait (n 141) | -0.280 [-0.35, -0.21] | -0.157 [-0.20, -0.12] | -0.193 [-0.25, -0.14] | +0.171 [+0.10, +0.25] | +0.029 [+0.00, +0.06] | -0.122 [-0.16, -0.08] | +0.007 [+0.00, +0.01] | +0.096 [+0.03, +0.17] | -0.059 [-0.11, -0.01] | -0.204 [-0.53, +0.14] | -0.103 [-0.39, +0.19] | -0.436 [-0.60, -0.28] | -0.021 [-0.16, +0.11] | +0.074 [+0.03, +0.12] | +0.080 [+0.01, +0.15] |
| tornado_redirect | tornado_king - tornado_on (n 188) | -0.013 [-0.05, +0.02] | -0.002 [-0.02, +0.01] | -0.000 [-0.02, +0.02] | +0.007 [-0.01, +0.03] | -0.000 [-0.00, +0.00] | +0.007 [-0.02, +0.03] | +0.001 [+0.00, +0.00] | +0.000 [-0.02, +0.02] | +0.013 [+0.00, +0.03] | +0.067 [-0.12, +0.25] | +0.083 [-0.13, +0.28] | -0.016 [-0.10, +0.06] | +0.007 [-0.07, +0.08] | +0.007 [-0.02, +0.03] | +0.016 [+0.00, +0.03] |
| tornado_redirect | tornado_king - wait (n 31) | -0.132 [-0.25, -0.01] | -0.056 [-0.11, +0.00] | -0.052 [-0.13, +0.03] | +0.038 [-0.02, +0.10] | -0.018 [-0.05, +0.00] | -0.071 [-0.19, +0.04] | +0.000 [+0.00, +0.00] | -0.053 [-0.16, +0.00] | -0.079 [-0.16, -0.02] | -0.064 [-0.59, +0.50] | -0.093 [-0.73, +0.45] | +0.184 [-0.19, +0.55] | -0.079 [-0.40, +0.26] | +0.000 [+0.00, +0.00] | -0.079 [-0.16, -0.02] |
| tornado_redirect | tornado_on - wait (n 31) | -0.138 [-0.25, -0.02] | -0.094 [-0.16, -0.04] | -0.106 [-0.19, -0.02] | +0.082 [-0.01, +0.19] | -0.020 [-0.06, +0.00] | -0.115 [-0.21, -0.02] | +0.000 [+0.00, +0.00] | -0.059 [-0.18, +0.00] | -0.088 [-0.17, -0.03] | -0.001 [-0.55, +0.60] | +0.327 [-0.31, +0.93] | +0.206 [-0.18, +0.59] | -0.118 [-0.39, +0.19] | +0.000 [+0.00, +0.00] | -0.088 [-0.17, -0.03] |
| xbow_after_fail | rocket_empty - rocket_princess (n 149) | -0.048 [-0.08, -0.02] | -0.035 [-0.05, -0.02] | -0.019 [-0.04, +0.00] | +0.005 [-0.02, +0.03] | -0.012 [-0.03, +0.00] | -0.072 [-0.09, -0.06] | +0.000 [+0.00, +0.00] | -0.037 [-0.07, -0.00] | +0.000 [+0.00, +0.00] | +0.021 [-0.21, +0.23] | -0.085 [-0.28, +0.10] | -0.042 [-0.13, +0.06] | -0.028 [-0.14, +0.08] | -0.005 [-0.03, +0.02] | +0.000 [+0.00, +0.00] |
| xbow_after_fail | rocket_empty - xbow_defensive (n 148) | -0.161 [-0.20, -0.12] | -0.082 [-0.10, -0.06] | -0.134 [-0.17, -0.10] | +0.153 [+0.11, +0.19] | +0.004 [-0.01, +0.02] | -0.028 [-0.05, -0.01] | +0.000 [+0.00, +0.00] | +0.051 [+0.02, +0.08] | +0.005 [+0.00, +0.01] | -0.230 [-0.52, +0.05] | +0.014 [-0.23, +0.26] | +0.014 [-0.10, +0.13] | -0.060 [-0.21, +0.08] | +0.042 [+0.01, +0.08] | +0.005 [+0.00, +0.01] |
| xbow_after_fail | rocket_empty - xbow_reach (n 132) | -0.241 [-0.30, -0.19] | -0.113 [-0.14, -0.09] | -0.142 [-0.18, -0.11] | +0.091 [+0.06, +0.12] | +0.007 [-0.00, +0.02] | -0.139 [-0.18, -0.10] | -0.000 [-0.00, -0.00] | +0.040 [+0.01, +0.07] | -0.015 [-0.04, +0.00] | -0.392 [-0.64, -0.14] | -0.057 [-0.31, +0.18] | -0.065 [-0.17, +0.05] | -0.175 [-0.32, -0.03] | +0.020 [-0.02, +0.06] | -0.025 [-0.05, +0.00] |
| xbow_after_fail | rocket_princess - wait (n 27) | -0.246 [-0.38, -0.12] | -0.186 [-0.29, -0.08] | -0.225 [-0.36, -0.07] | +0.235 [+0.11, +0.36] | +0.015 [-0.00, +0.04] | -0.100 [-0.22, +0.01] | +0.000 [+0.00, +0.00] | +0.042 [+0.00, +0.12] | -0.083 [-0.17, +0.00] | +0.440 [-0.36, +1.22] | -0.102 [-1.03, +0.82] | -0.667 [-1.04, -0.33] | -0.250 [-1.00, +0.33] | +0.000 [-0.08, +0.08] | -0.083 [-0.17, +0.00] |
| xbow_after_fail | rocket_princess - xbow_defensive (n 187) | -0.123 [-0.16, -0.09] | -0.060 [-0.08, -0.04] | -0.117 [-0.15, -0.09] | +0.176 [+0.14, +0.21] | +0.017 [+0.00, +0.03] | +0.048 [+0.03, +0.06] | +0.000 [+0.00, +0.00] | +0.102 [+0.06, +0.15] | +0.012 [+0.00, +0.03] | -0.287 [-0.57, -0.01] | +0.164 [-0.08, +0.43] | +0.039 [-0.07, +0.15] | -0.075 [-0.22, +0.06] | +0.079 [+0.04, +0.12] | +0.012 [+0.00, +0.03] |
| xbow_after_fail | rocket_princess - xbow_reach (n 169) | -0.210 [-0.27, -0.16] | -0.093 [-0.12, -0.07] | -0.144 [-0.18, -0.11] | +0.116 [+0.08, +0.15] | +0.027 [+0.01, +0.05] | -0.069 [-0.10, -0.04] | -0.000 [-0.00, -0.00] | +0.088 [+0.05, +0.14] | -0.021 [-0.04, +0.00] | -0.326 [-0.60, -0.06] | -0.002 [-0.23, +0.21] | -0.063 [-0.18, +0.04] | -0.109 [-0.23, +0.00] | +0.063 [+0.02, +0.10] | -0.029 [-0.05, -0.01] |
| xbow_after_fail | wait - xbow_defensive (n 27) | +0.181 [+0.03, +0.34] | +0.097 [+0.02, +0.18] | +0.124 [-0.01, +0.26] | -0.015 [-0.09, +0.05] | +0.001 [+0.00, +0.00] | +0.122 [-0.00, +0.24] | +0.000 [+0.00, +0.00] | +0.000 [+0.00, +0.00] | +0.077 [+0.00, +0.15] | -0.317 [-1.29, +0.71] | -0.290 [-1.00, +0.40] | +0.462 [+0.00, +0.88] | +0.231 [-0.42, +1.00] | +0.038 [+0.00, +0.12] | +0.077 [+0.00, +0.15] |
| xbow_after_fail | xbow_defensive - xbow_reach (n 171) | -0.073 [-0.12, -0.03] | -0.030 [-0.05, -0.01] | -0.021 [-0.05, +0.01] | -0.041 [-0.07, -0.02] | +0.008 [-0.00, +0.02] | -0.109 [-0.14, -0.08] | -0.000 [-0.00, -0.00] | -0.016 [-0.04, +0.01] | -0.020 [-0.04, -0.00] | -0.082 [-0.34, +0.18] | -0.193 [-0.41, +0.02] | -0.114 [-0.23, -0.00] | -0.024 [-0.15, +0.09] | -0.012 [-0.04, +0.02] | -0.028 [-0.05, -0.01] |

### Critic slope of the terminal return on the horizon return (audited samples; PLAN band [0.7, 1.3])

| trigger | levels slope (n) | within-sample diffs slope (n) |
|---|---|---|
| def_xbow | 0.77 +- 0.13 (68) | 0.87 +- 0.17 (34) |
| rocket | 0.83 +- 0.05 (348) | 0.88 +- 0.11 (233) |
| rocket_cycle | - | - |
| rocket_played | 1.03 +- 0.15 (63) | 1.07 +- 0.33 (42) |
| rocket_tornado | 0.77 +- 0.08 (179) | 0.91 +- 0.17 (108) |
| tornado_redirect | 0.71 +- 0.10 (137) | 1.05 +- 0.29 (80) |
| xbow_after_fail | 0.74 +- 0.06 (205) | 0.70 +- 0.16 (141) |
| ALL | 0.79 +- 0.03 (1000) | 0.84 +- 0.07 (638) |

