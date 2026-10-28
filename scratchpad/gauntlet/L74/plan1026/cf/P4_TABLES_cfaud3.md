# P4 audit tables: 1926 samples from cfaud3.jsonl (updates >= 2)

samples per trigger: rocket 257, rocket_played 159, rocket_tornado 299, siege 208, tornado_redirect 252, wincon 248, xbow 296, xbow_after_fail 207

### dQ at the main horizon: all / phase / score

| trigger | alternative | split | label | n | mean dQ | 90% CI |
|---|---|---|---|---|---|---|
| rocket | rocket_clump | all | all | 148 | -0.202 * | [-0.258, -0.146] |
| rocket | rocket_clump | phase | 1x | 75 | -0.312 * | [-0.386, -0.237] |
| rocket | rocket_clump | phase | 2x | 49 | -0.129 * | [-0.219, -0.035] |
| rocket | rocket_clump | phase | OT | 24 | -0.006 | [-0.128, +0.117] |
| rocket | rocket_clump | score | ahead | 29 | -0.139 * | [-0.249, -0.020] |
| rocket | rocket_clump | score | behind | 46 | -0.134 * | [-0.210, -0.061] |
| rocket | rocket_clump | score | even | 73 | -0.270 * | [-0.361, -0.181] |
| rocket | rocket_clump | tesla | tesla in hand | 60 | -0.283 * | [-0.379, -0.188] |
| rocket | rocket_clump | tesla | tesla not in hand | 88 | -0.147 * | [-0.215, -0.082] |
| rocket | rocket_princess | all | all | 256 | -0.241 * | [-0.280, -0.199] |
| rocket | rocket_princess | phase | 1x | 160 | -0.327 * | [-0.378, -0.279] |
| rocket | rocket_princess | phase | 2x | 67 | -0.144 * | [-0.230, -0.050] |
| rocket | rocket_princess | phase | OT | 29 | +0.009 | [-0.071, +0.097] |
| rocket | rocket_princess | score | ahead | 50 | -0.155 * | [-0.228, -0.082] |
| rocket | rocket_princess | score | behind | 73 | -0.124 * | [-0.190, -0.054] |
| rocket | rocket_princess | score | even | 133 | -0.338 * | [-0.397, -0.275] |
| rocket | rocket_princess | tesla | tesla in hand | 109 | -0.275 * | [-0.340, -0.204] |
| rocket | rocket_princess | tesla | tesla not in hand | 147 | -0.216 * | [-0.266, -0.167] |
| rocket_played | second_card | all | all | 159 | -0.069 * | [-0.111, -0.031] |
| rocket_played | second_card | phase | 1x | 65 | -0.074 * | [-0.137, -0.008] |
| rocket_played | second_card | phase | 2x | 41 | -0.020 | [-0.094, +0.055] |
| rocket_played | second_card | phase | OT | 53 | -0.101 * | [-0.172, -0.034] |
| rocket_played | second_card | score | ahead | 33 | -0.065 | [-0.140, +0.003] |
| rocket_played | second_card | score | behind | 59 | -0.035 | [-0.107, +0.040] |
| rocket_played | second_card | score | even | 67 | -0.101 * | [-0.166, -0.036] |
| rocket_played | second_card | tesla | tesla in hand | 65 | -0.119 * | [-0.186, -0.054] |
| rocket_played | second_card | tesla | tesla not in hand | 94 | -0.034 | [-0.083, +0.018] |
| rocket_played | wait | all | all | 159 | -0.035 | [-0.072, +0.001] |
| rocket_played | wait | phase | 1x | 65 | -0.017 | [-0.067, +0.033] |
| rocket_played | wait | phase | 2x | 41 | -0.064 | [-0.137, +0.012] |
| rocket_played | wait | phase | OT | 53 | -0.034 | [-0.103, +0.034] |
| rocket_played | wait | score | ahead | 33 | -0.041 | [-0.100, +0.021] |
| rocket_played | wait | score | behind | 59 | -0.068 * | [-0.131, -0.008] |
| rocket_played | wait | score | even | 67 | -0.003 | [-0.066, +0.064] |
| rocket_played | wait | tesla | tesla in hand | 65 | -0.049 | [-0.098, +0.002] |
| rocket_played | wait | tesla | tesla not in hand | 94 | -0.025 | [-0.079, +0.026] |
| rocket_tornado | combo | all | all | 299 | -0.314 * | [-0.360, -0.272] |
| rocket_tornado | combo | phase | 1x | 123 | -0.450 * | [-0.518, -0.379] |
| rocket_tornado | combo | phase | 2x | 106 | -0.253 * | [-0.324, -0.181] |
| rocket_tornado | combo | phase | OT | 70 | -0.168 * | [-0.248, -0.101] |
| rocket_tornado | combo | score | ahead | 43 | -0.300 * | [-0.424, -0.175] |
| rocket_tornado | combo | score | behind | 123 | -0.164 * | [-0.212, -0.122] |
| rocket_tornado | combo | score | even | 133 | -0.457 * | [-0.533, -0.390] |
| rocket_tornado | combo | tesla | tesla in hand | 124 | -0.289 * | [-0.360, -0.220] |
| rocket_tornado | combo | tesla | tesla not in hand | 175 | -0.331 * | [-0.390, -0.275] |
| rocket_tornado | rocket_clump | all | all | 299 | -0.259 * | [-0.301, -0.219] |
| rocket_tornado | rocket_clump | phase | 1x | 123 | -0.367 * | [-0.427, -0.308] |
| rocket_tornado | rocket_clump | phase | 2x | 106 | -0.206 * | [-0.275, -0.138] |
| rocket_tornado | rocket_clump | phase | OT | 70 | -0.152 * | [-0.258, -0.061] |
| rocket_tornado | rocket_clump | score | ahead | 43 | -0.312 * | [-0.444, -0.182] |
| rocket_tornado | rocket_clump | score | behind | 123 | -0.129 * | [-0.186, -0.069] |
| rocket_tornado | rocket_clump | score | even | 133 | -0.363 * | [-0.428, -0.302] |
| rocket_tornado | rocket_clump | tesla | tesla in hand | 124 | -0.232 * | [-0.292, -0.173] |
| rocket_tornado | rocket_clump | tesla | tesla not in hand | 175 | -0.279 * | [-0.337, -0.223] |
| rocket_tornado | wait | all | all | 146 | +0.040 | [-0.003, +0.086] |
| rocket_tornado | wait | phase | 1x | 61 | +0.008 | [-0.041, +0.058] |
| rocket_tornado | wait | phase | 2x | 54 | +0.080 * | [+0.005, +0.158] |
| rocket_tornado | wait | phase | OT | 31 | +0.031 | [-0.095, +0.169] |
| rocket_tornado | wait | score | ahead | 25 | +0.005 | [-0.100, +0.116] |
| rocket_tornado | wait | score | behind | 53 | -0.012 | [-0.057, +0.034] |
| rocket_tornado | wait | score | even | 68 | +0.093 * | [+0.018, +0.173] |
| rocket_tornado | wait | tesla | tesla in hand | 59 | -0.004 | [-0.060, +0.054] |
| rocket_tornado | wait | tesla | tesla not in hand | 87 | +0.069 * | [+0.009, +0.136] |
| siege | front | all | all | 192 | -0.018 | [-0.063, +0.029] |
| siege | front | phase | 1x | 117 | -0.023 | [-0.063, +0.016] |
| siege | front | phase | 2x | 58 | -0.055 | [-0.149, +0.026] |
| siege | front | score | ahead | 29 | -0.045 | [-0.114, +0.025] |
| siege | front | score | behind | 75 | -0.013 | [-0.074, +0.054] |
| siege | front | score | even | 88 | -0.014 | [-0.100, +0.078] |
| siege | front | tesla | tesla in hand | 61 | -0.024 | [-0.114, +0.068] |
| siege | front | tesla | tesla not in hand | 131 | -0.016 | [-0.055, +0.025] |
| siege | rocket_on | all | all | 78 | -0.206 * | [-0.275, -0.142] |
| siege | rocket_on | phase | 1x | 48 | -0.197 * | [-0.280, -0.116] |
| siege | rocket_on | phase | 2x | 24 | -0.241 * | [-0.401, -0.108] |
| siege | rocket_on | score | behind | 27 | -0.163 * | [-0.255, -0.068] |
| siege | rocket_on | score | even | 39 | -0.211 * | [-0.350, -0.083] |
| siege | rocket_on | tesla | tesla in hand | 30 | -0.198 * | [-0.353, -0.056] |
| siege | rocket_on | tesla | tesla not in hand | 48 | -0.211 * | [-0.305, -0.126] |
| siege | troop_on | all | all | 136 | -0.029 | [-0.079, +0.020] |
| siege | troop_on | phase | 1x | 85 | -0.023 | [-0.072, +0.023] |
| siege | troop_on | phase | 2x | 41 | -0.053 | [-0.139, +0.053] |
| siege | troop_on | score | ahead | 22 | -0.089 * | [-0.164, -0.017] |
| siege | troop_on | score | behind | 52 | -0.029 | [-0.094, +0.042] |
| siege | troop_on | score | even | 62 | -0.009 | [-0.094, +0.081] |
| siege | troop_on | tesla | tesla in hand | 35 | -0.021 | [-0.103, +0.066] |
| siege | troop_on | tesla | tesla not in hand | 101 | -0.032 | [-0.089, +0.026] |
| siege | wait | all | all | 51 | -0.024 | [-0.092, +0.040] |
| siege | wait | phase | 1x | 29 | +0.030 | [-0.029, +0.081] |
| siege | wait | score | even | 27 | +0.030 | [-0.049, +0.111] |
| siege | wait | tesla | tesla not in hand | 33 | -0.033 | [-0.126, +0.053] |
| tornado_redirect | tornado_king | all | all | 252 | -0.160 * | [-0.199, -0.123] |
| tornado_redirect | tornado_king | close_ot | close OT (even crowns, |hp margin| <= .25) | 20 | -0.132 * | [-0.255, -0.002] |
| tornado_redirect | tornado_king | phase | 1x | 120 | -0.154 * | [-0.204, -0.104] |
| tornado_redirect | tornado_king | phase | 2x | 76 | -0.113 * | [-0.175, -0.052] |
| tornado_redirect | tornado_king | phase | OT | 56 | -0.234 * | [-0.331, -0.136] |
| tornado_redirect | tornado_king | score | ahead | 80 | -0.131 * | [-0.194, -0.071] |
| tornado_redirect | tornado_king | score | behind | 60 | -0.211 * | [-0.305, -0.121] |
| tornado_redirect | tornado_king | score | even | 112 | -0.152 * | [-0.202, -0.104] |
| tornado_redirect | tornado_king | tesla | tesla in hand | 108 | -0.126 * | [-0.182, -0.071] |
| tornado_redirect | tornado_king | tesla | tesla not in hand | 144 | -0.185 * | [-0.234, -0.135] |
| tornado_redirect | tornado_on | all | all | 252 | -0.111 * | [-0.149, -0.075] |
| tornado_redirect | tornado_on | close_ot | close OT (even crowns, |hp margin| <= .25) | 20 | +0.094 | [-0.084, +0.285] |
| tornado_redirect | tornado_on | phase | 1x | 120 | -0.149 * | [-0.197, -0.102] |
| tornado_redirect | tornado_on | phase | 2x | 76 | -0.086 * | [-0.150, -0.024] |
| tornado_redirect | tornado_on | phase | OT | 56 | -0.065 | [-0.164, +0.041] |
| tornado_redirect | tornado_on | score | ahead | 80 | -0.098 * | [-0.151, -0.049] |
| tornado_redirect | tornado_on | score | behind | 60 | -0.100 * | [-0.192, -0.012] |
| tornado_redirect | tornado_on | score | even | 112 | -0.127 * | [-0.184, -0.068] |
| tornado_redirect | tornado_on | tesla | tesla in hand | 108 | -0.129 * | [-0.187, -0.075] |
| tornado_redirect | tornado_on | tesla | tesla not in hand | 144 | -0.098 * | [-0.149, -0.047] |
| tornado_redirect | wait | all | all | 45 | +0.005 | [-0.043, +0.048] |
| tornado_redirect | wait | score | ahead | 20 | -0.003 | [-0.084, +0.059] |
| tornado_redirect | wait | tesla | tesla in hand | 22 | +0.004 | [-0.040, +0.047] |
| tornado_redirect | wait | tesla | tesla not in hand | 23 | +0.007 | [-0.078, +0.078] |
| wincon | cheap_on | all | all | 37 | -0.050 | [-0.119, +0.016] |
| wincon | cheap_on | tesla | tesla in hand | 20 | -0.037 | [-0.107, +0.024] |
| wincon | rocket_on | all | all | 72 | -0.203 * | [-0.284, -0.128] |
| wincon | rocket_on | phase | 1x | 25 | -0.201 * | [-0.310, -0.080] |
| wincon | rocket_on | phase | 2x | 26 | -0.221 * | [-0.387, -0.080] |
| wincon | rocket_on | phase | OT | 21 | -0.181 * | [-0.328, -0.060] |
| wincon | rocket_on | score | behind | 27 | -0.098 | [-0.220, +0.005] |
| wincon | rocket_on | score | even | 29 | -0.239 * | [-0.335, -0.148] |
| wincon | rocket_on | tesla | tesla in hand | 25 | -0.114 * | [-0.208, -0.017] |
| wincon | rocket_on | tesla | tesla not in hand | 47 | -0.249 * | [-0.358, -0.151] |
| wincon | troop_on | all | all | 235 | -0.037 | [-0.071, +0.000] |
| wincon | troop_on | phase | 1x | 91 | -0.050 * | [-0.100, -0.002] |
| wincon | troop_on | phase | 2x | 87 | -0.019 | [-0.080, +0.036] |
| wincon | troop_on | phase | OT | 57 | -0.042 | [-0.136, +0.048] |
| wincon | troop_on | score | ahead | 66 | -0.081 * | [-0.155, -0.012] |
| wincon | troop_on | score | behind | 76 | +0.029 | [-0.025, +0.084] |
| wincon | troop_on | score | even | 93 | -0.059 | [-0.129, +0.003] |
| wincon | troop_on | tesla | tesla in hand | 95 | -0.017 | [-0.064, +0.031] |
| wincon | troop_on | tesla | tesla not in hand | 140 | -0.050 | [-0.104, +0.003] |
| wincon | wait | all | all | 55 | -0.014 | [-0.087, +0.062] |
| wincon | wait | phase | 2x | 21 | +0.056 | [-0.050, +0.173] |
| wincon | wait | score | ahead | 23 | -0.027 | [-0.162, +0.118] |
| wincon | wait | tesla | tesla in hand | 25 | +0.030 | [-0.079, +0.147] |
| wincon | wait | tesla | tesla not in hand | 30 | -0.051 | [-0.147, +0.046] |
| xbow | wait | all | all | 296 | +0.006 | [-0.024, +0.035] |
| xbow | wait | close_ot | close OT (even crowns, |hp margin| <= .25) | 20 | +0.021 | [-0.079, +0.122] |
| xbow | wait | phase | 1x | 131 | +0.001 | [-0.040, +0.043] |
| xbow | wait | phase | 2x | 89 | +0.027 | [-0.026, +0.077] |
| xbow | wait | phase | OT | 76 | -0.008 | [-0.071, +0.053] |
| xbow | wait | score | ahead | 82 | +0.033 * | [+0.001, +0.068] |
| xbow | wait | score | behind | 76 | +0.004 | [-0.064, +0.071] |
| xbow | wait | score | even | 138 | -0.008 | [-0.052, +0.035] |
| xbow | wait | tesla | tesla in hand | 92 | -0.008 | [-0.060, +0.042] |
| xbow | wait | tesla | tesla not in hand | 204 | +0.013 | [-0.020, +0.046] |
| xbow | xbow_defensive | all | all | 296 | -0.147 * | [-0.182, -0.112] |
| xbow | xbow_defensive | close_ot | close OT (even crowns, |hp margin| <= .25) | 20 | -0.245 * | [-0.366, -0.128] |
| xbow | xbow_defensive | phase | 1x | 131 | -0.187 * | [-0.239, -0.136] |
| xbow | xbow_defensive | phase | 2x | 89 | -0.112 * | [-0.188, -0.042] |
| xbow | xbow_defensive | phase | OT | 76 | -0.118 * | [-0.179, -0.056] |
| xbow | xbow_defensive | score | ahead | 82 | -0.013 | [-0.049, +0.023] |
| xbow | xbow_defensive | score | behind | 76 | -0.150 * | [-0.229, -0.072] |
| xbow | xbow_defensive | score | even | 138 | -0.224 * | [-0.283, -0.164] |
| xbow | xbow_defensive | tesla | tesla in hand | 92 | -0.202 * | [-0.262, -0.147] |
| xbow | xbow_defensive | tesla | tesla not in hand | 204 | -0.122 * | [-0.167, -0.078] |
| xbow | xbow_other_lane | all | all | 296 | -0.066 * | [-0.102, -0.031] |
| xbow | xbow_other_lane | close_ot | close OT (even crowns, |hp margin| <= .25) | 20 | -0.112 * | [-0.228, -0.016] |
| xbow | xbow_other_lane | phase | 1x | 131 | -0.095 * | [-0.146, -0.043] |
| xbow | xbow_other_lane | phase | 2x | 89 | -0.062 | [-0.139, +0.009] |
| xbow | xbow_other_lane | phase | OT | 76 | -0.021 | [-0.088, +0.041] |
| xbow | xbow_other_lane | score | ahead | 82 | +0.009 | [-0.037, +0.051] |
| xbow | xbow_other_lane | score | behind | 76 | -0.065 | [-0.148, +0.015] |
| xbow | xbow_other_lane | score | even | 138 | -0.111 * | [-0.168, -0.054] |
| xbow | xbow_other_lane | tesla | tesla in hand | 92 | -0.101 * | [-0.170, -0.035] |
| xbow | xbow_other_lane | tesla | tesla not in hand | 204 | -0.050 * | [-0.093, -0.010] |
| xbow_after_fail | rocket_princess | all | all | 200 | -0.157 * | [-0.213, -0.103] |
| xbow_after_fail | rocket_princess | close_ot | close OT (even crowns, |hp margin| <= .25) | 24 | -0.139 | [-0.350, +0.053] |
| xbow_after_fail | rocket_princess | phase | 1x | 41 | -0.299 * | [-0.370, -0.225] |
| xbow_after_fail | rocket_princess | phase | 2x | 78 | -0.194 * | [-0.270, -0.122] |
| xbow_after_fail | rocket_princess | phase | OT | 81 | -0.050 | [-0.152, +0.057] |
| xbow_after_fail | rocket_princess | score | ahead | 42 | -0.142 * | [-0.240, -0.048] |
| xbow_after_fail | rocket_princess | score | behind | 86 | -0.072 | [-0.146, +0.007] |
| xbow_after_fail | rocket_princess | score | even | 72 | -0.268 * | [-0.371, -0.170] |
| xbow_after_fail | rocket_princess | tesla | tesla in hand | 79 | -0.138 * | [-0.201, -0.075] |
| xbow_after_fail | rocket_princess | tesla | tesla not in hand | 121 | -0.170 * | [-0.250, -0.086] |
| xbow_after_fail | wait | all | all | 51 | -0.051 | [-0.137, +0.030] |
| xbow_after_fail | wait | phase | OT | 31 | -0.057 | [-0.182, +0.048] |
| xbow_after_fail | wait | tesla | tesla not in hand | 34 | -0.109 * | [-0.227, -0.006] |
| xbow_after_fail | xbow_defensive | all | all | 206 | -0.068 * | [-0.120, -0.016] |
| xbow_after_fail | xbow_defensive | close_ot | close OT (even crowns, |hp margin| <= .25) | 24 | -0.199 | [-0.442, +0.004] |
| xbow_after_fail | xbow_defensive | phase | 1x | 41 | -0.171 * | [-0.253, -0.095] |
| xbow_after_fail | xbow_defensive | phase | 2x | 78 | -0.069 * | [-0.128, -0.008] |
| xbow_after_fail | xbow_defensive | phase | OT | 87 | -0.019 | [-0.109, +0.076] |
| xbow_after_fail | xbow_defensive | score | ahead | 42 | -0.042 | [-0.126, +0.042] |
| xbow_after_fail | xbow_defensive | score | behind | 92 | -0.001 | [-0.073, +0.079] |
| xbow_after_fail | xbow_defensive | score | even | 72 | -0.169 * | [-0.268, -0.075] |
| xbow_after_fail | xbow_defensive | tesla | tesla in hand | 83 | -0.026 | [-0.087, +0.041] |
| xbow_after_fail | xbow_defensive | tesla | tesla not in hand | 123 | -0.097 * | [-0.168, -0.025] |
| xbow_after_fail | xbow_reach | all | all | 157 | -0.028 | [-0.076, +0.019] |
| xbow_after_fail | xbow_reach | phase | 1x | 37 | -0.061 | [-0.132, +0.011] |
| xbow_after_fail | xbow_reach | phase | 2x | 64 | -0.062 * | [-0.121, -0.004] |
| xbow_after_fail | xbow_reach | phase | OT | 56 | +0.033 | [-0.061, +0.134] |
| xbow_after_fail | xbow_reach | score | ahead | 26 | -0.072 | [-0.161, +0.006] |
| xbow_after_fail | xbow_reach | score | behind | 77 | -0.005 | [-0.076, +0.070] |
| xbow_after_fail | xbow_reach | score | even | 54 | -0.038 | [-0.118, +0.040] |
| xbow_after_fail | xbow_reach | tesla | tesla in hand | 68 | -0.056 | [-0.121, +0.007] |
| xbow_after_fail | xbow_reach | tesla | tesla not in hand | 89 | -0.006 | [-0.071, +0.060] |

### dQ at the main horizon: trigger-specific splits

| trigger | alternative | split | label | n | mean dQ | 90% CI |
|---|---|---|---|---|---|---|
| rocket | rocket_clump | elixir | elixir < 8 | 123 | -0.165 * | [-0.222, -0.108] |
| rocket | rocket_clump | elixir | elixir >= 8 | 25 | -0.386 * | [-0.542, -0.229] |
| rocket | rocket_clump | opp | exploiter | 73 | -0.182 * | [-0.262, -0.100] |
| rocket | rocket_clump | opp | exploiter_league | 53 | -0.154 * | [-0.244, -0.063] |
| rocket | rocket_clump | opp_bank | bank<2 | 65 | -0.204 * | [-0.291, -0.124] |
| rocket | rocket_clump | opp_bank | bank>=2 | 83 | -0.200 * | [-0.272, -0.124] |
| rocket | rocket_clump | policy | policy played | 30 | -0.356 * | [-0.495, -0.219] |
| rocket | rocket_clump | policy | policy waited | 118 | -0.163 * | [-0.218, -0.104] |
| rocket | rocket_clump | safe_idle | safe & idle (no foe on our half, policy waited) | 77 | -0.239 * | [-0.313, -0.170] |
| rocket | rocket_clump | threat | foe on our half | 46 | -0.064 | [-0.149, +0.033] |
| rocket | rocket_clump | threat | no foe body on our half | 102 | -0.264 * | [-0.332, -0.198] |
| rocket | rocket_clump | value_rocket_clump | 4-6 | 48 | -0.203 * | [-0.286, -0.130] |
| rocket | rocket_clump | value_rocket_clump | 6-8 | 38 | -0.189 * | [-0.302, -0.074] |
| rocket | rocket_clump | value_rocket_clump | <4 | 48 | -0.210 * | [-0.303, -0.114] |
| rocket | rocket_clump | xbow_hand | no xbow in hand | 52 | -0.182 * | [-0.285, -0.080] |
| rocket | rocket_clump | xbow_hand | xbow in hand | 96 | -0.213 * | [-0.276, -0.147] |
| rocket | rocket_princess | elixir | elixir < 8 | 206 | -0.207 * | [-0.252, -0.159] |
| rocket | rocket_princess | elixir | elixir >= 8 | 50 | -0.380 * | [-0.467, -0.297] |
| rocket | rocket_princess | opp | exploiter | 128 | -0.243 * | [-0.302, -0.180] |
| rocket | rocket_princess | opp | exploiter_league | 83 | -0.220 * | [-0.286, -0.154] |
| rocket | rocket_princess | opp | init | 30 | -0.260 * | [-0.373, -0.151] |
| rocket | rocket_princess | opp_bank | bank<2 | 119 | -0.225 * | [-0.285, -0.165] |
| rocket | rocket_princess | opp_bank | bank>=2 | 137 | -0.255 * | [-0.313, -0.199] |
| rocket | rocket_princess | policy | policy played | 36 | -0.364 * | [-0.487, -0.253] |
| rocket | rocket_princess | policy | policy waited | 220 | -0.221 * | [-0.262, -0.177] |
| rocket | rocket_princess | safe_idle | safe & idle (no foe on our half, policy waited) | 159 | -0.263 * | [-0.315, -0.209] |
| rocket | rocket_princess | threat | foe on our half | 68 | -0.139 * | [-0.212, -0.064] |
| rocket | rocket_princess | threat | no foe body on our half | 188 | -0.278 * | [-0.326, -0.229] |
| rocket | rocket_princess | value_rocket_clump | 4-6 | 47 | -0.234 * | [-0.312, -0.158] |
| rocket | rocket_princess | value_rocket_clump | 6-8 | 38 | -0.259 * | [-0.383, -0.134] |
| rocket | rocket_princess | value_rocket_clump | <4 | 48 | -0.256 * | [-0.358, -0.160] |
| rocket | rocket_princess | xbow_hand | no xbow in hand | 94 | -0.201 * | [-0.266, -0.131] |
| rocket | rocket_princess | xbow_hand | xbow in hand | 162 | -0.264 * | [-0.317, -0.210] |
| rocket_played | second_card | elixir | elixir < 8 | 99 | -0.094 * | [-0.146, -0.038] |
| rocket_played | second_card | elixir | elixir >= 8 | 60 | -0.029 | [-0.086, +0.029] |
| rocket_played | second_card | opp | exploiter | 52 | -0.040 | [-0.110, +0.023] |
| rocket_played | second_card | opp | exploiter_league | 88 | -0.069 * | [-0.125, -0.013] |
| rocket_played | second_card | opp_bank | bank<2 | 90 | -0.061 * | [-0.116, -0.004] |
| rocket_played | second_card | opp_bank | bank>=2 | 69 | -0.080 * | [-0.141, -0.016] |
| rocket_played | second_card | policy | policy played | 159 | -0.069 * | [-0.111, -0.031] |
| rocket_played | second_card | threat | foe on our half | 27 | -0.046 | [-0.110, +0.017] |
| rocket_played | second_card | threat | no foe body on our half | 132 | -0.074 * | [-0.121, -0.028] |
| rocket_played | second_card | xbow_hand | no xbow in hand | 86 | -0.085 * | [-0.152, -0.016] |
| rocket_played | second_card | xbow_hand | xbow in hand | 73 | -0.050 * | [-0.096, -0.006] |
| rocket_played | wait | elixir | elixir < 8 | 99 | -0.057 * | [-0.110, -0.004] |
| rocket_played | wait | elixir | elixir >= 8 | 60 | +0.002 | [-0.044, +0.049] |
| rocket_played | wait | opp | exploiter | 52 | -0.003 | [-0.057, +0.052] |
| rocket_played | wait | opp | exploiter_league | 88 | -0.060 * | [-0.112, -0.009] |
| rocket_played | wait | opp_bank | bank<2 | 90 | -0.043 | [-0.090, +0.009] |
| rocket_played | wait | opp_bank | bank>=2 | 69 | -0.024 | [-0.085, +0.036] |
| rocket_played | wait | policy | policy played | 159 | -0.035 | [-0.072, +0.001] |
| rocket_played | wait | threat | foe on our half | 27 | -0.037 | [-0.115, +0.037] |
| rocket_played | wait | threat | no foe body on our half | 132 | -0.034 | [-0.079, +0.009] |
| rocket_played | wait | xbow_hand | no xbow in hand | 86 | -0.039 | [-0.099, +0.019] |
| rocket_played | wait | xbow_hand | xbow in hand | 73 | -0.030 | [-0.076, +0.013] |
| rocket_tornado | combo | elixir | elixir < 8 | 101 | -0.286 * | [-0.363, -0.215] |
| rocket_tornado | combo | elixir | elixir >= 8 | 198 | -0.328 * | [-0.387, -0.275] |
| rocket_tornado | combo | opp | exploiter | 143 | -0.367 * | [-0.435, -0.301] |
| rocket_tornado | combo | opp | exploiter_league | 92 | -0.247 * | [-0.323, -0.181] |
| rocket_tornado | combo | opp | init | 44 | -0.299 * | [-0.414, -0.182] |
| rocket_tornado | combo | opp | snapshot | 20 | -0.271 * | [-0.437, -0.127] |
| rocket_tornado | combo | opp_bank | bank<2 | 153 | -0.314 * | [-0.375, -0.255] |
| rocket_tornado | combo | opp_bank | bank>=2 | 146 | -0.314 * | [-0.379, -0.252] |
| rocket_tornado | combo | policy | policy played | 146 | -0.327 * | [-0.392, -0.265] |
| rocket_tornado | combo | policy | policy waited | 153 | -0.301 * | [-0.362, -0.243] |
| rocket_tornado | combo | safe_idle | safe & idle (no foe on our half, policy waited) | 92 | -0.369 * | [-0.444, -0.298] |
| rocket_tornado | combo | threat | foe on our half | 113 | -0.209 * | [-0.279, -0.144] |
| rocket_tornado | combo | threat | no foe body on our half | 186 | -0.378 * | [-0.430, -0.325] |
| rocket_tornado | combo | value_combo | 6-8 | 191 | -0.290 * | [-0.337, -0.241] |
| rocket_tornado | combo | value_combo | 8+ | 108 | -0.356 * | [-0.435, -0.276] |
| rocket_tornado | combo | value_rocket_clump | 4-6 | 184 | -0.244 * | [-0.291, -0.197] |
| rocket_tornado | combo | value_rocket_clump | 6-8 | 65 | -0.470 * | [-0.581, -0.364] |
| rocket_tornado | combo | value_rocket_clump | 8+ | 27 | -0.263 * | [-0.430, -0.107] |
| rocket_tornado | combo | value_rocket_clump | <4 | 23 | -0.494 * | [-0.644, -0.357] |
| rocket_tornado | combo | xbow_hand | no xbow in hand | 109 | -0.398 * | [-0.467, -0.333] |
| rocket_tornado | combo | xbow_hand | xbow in hand | 190 | -0.266 * | [-0.320, -0.214] |
| rocket_tornado | rocket_clump | elixir | elixir < 8 | 101 | -0.248 * | [-0.335, -0.162] |
| rocket_tornado | rocket_clump | elixir | elixir >= 8 | 198 | -0.266 * | [-0.315, -0.216] |
| rocket_tornado | rocket_clump | opp | exploiter | 143 | -0.274 * | [-0.343, -0.208] |
| rocket_tornado | rocket_clump | opp | exploiter_league | 92 | -0.223 * | [-0.285, -0.164] |
| rocket_tornado | rocket_clump | opp | init | 44 | -0.271 * | [-0.396, -0.154] |
| rocket_tornado | rocket_clump | opp | snapshot | 20 | -0.297 * | [-0.460, -0.151] |
| rocket_tornado | rocket_clump | opp_bank | bank<2 | 153 | -0.269 * | [-0.329, -0.214] |
| rocket_tornado | rocket_clump | opp_bank | bank>=2 | 146 | -0.249 * | [-0.316, -0.183] |
| rocket_tornado | rocket_clump | policy | policy played | 146 | -0.270 * | [-0.335, -0.203] |
| rocket_tornado | rocket_clump | policy | policy waited | 153 | -0.250 * | [-0.310, -0.194] |
| rocket_tornado | rocket_clump | safe_idle | safe & idle (no foe on our half, policy waited) | 92 | -0.308 * | [-0.384, -0.233] |
| rocket_tornado | rocket_clump | threat | foe on our half | 113 | -0.184 * | [-0.248, -0.126] |
| rocket_tornado | rocket_clump | threat | no foe body on our half | 186 | -0.305 * | [-0.362, -0.250] |
| rocket_tornado | rocket_clump | value_combo | 6-8 | 191 | -0.255 * | [-0.302, -0.208] |
| rocket_tornado | rocket_clump | value_combo | 8+ | 108 | -0.268 * | [-0.350, -0.181] |
| rocket_tornado | rocket_clump | value_rocket_clump | 4-6 | 184 | -0.228 * | [-0.278, -0.178] |
| rocket_tornado | rocket_clump | value_rocket_clump | 6-8 | 65 | -0.327 * | [-0.427, -0.230] |
| rocket_tornado | rocket_clump | value_rocket_clump | 8+ | 27 | -0.220 * | [-0.430, -0.012] |
| rocket_tornado | rocket_clump | value_rocket_clump | <4 | 23 | -0.366 * | [-0.471, -0.265] |
| rocket_tornado | rocket_clump | xbow_hand | no xbow in hand | 109 | -0.316 * | [-0.387, -0.241] |
| rocket_tornado | rocket_clump | xbow_hand | xbow in hand | 190 | -0.227 * | [-0.279, -0.177] |
| rocket_tornado | wait | elixir | elixir < 8 | 32 | +0.123 | [-0.014, +0.280] |
| rocket_tornado | wait | elixir | elixir >= 8 | 114 | +0.016 | [-0.024, +0.057] |
| rocket_tornado | wait | opp | exploiter | 69 | +0.059 | [-0.020, +0.140] |
| rocket_tornado | wait | opp | exploiter_league | 48 | +0.008 | [-0.032, +0.050] |
| rocket_tornado | wait | opp_bank | bank<2 | 72 | +0.047 | [-0.007, +0.101] |
| rocket_tornado | wait | opp_bank | bank>=2 | 74 | +0.033 | [-0.032, +0.107] |
| rocket_tornado | wait | policy | policy played | 146 | +0.040 | [-0.003, +0.086] |
| rocket_tornado | wait | threat | foe on our half | 52 | +0.043 | [-0.021, +0.109] |
| rocket_tornado | wait | threat | no foe body on our half | 94 | +0.038 | [-0.019, +0.098] |
| rocket_tornado | wait | value_combo | 6-8 | 82 | +0.034 | [-0.022, +0.099] |
| rocket_tornado | wait | value_combo | 8+ | 64 | +0.047 | [-0.025, +0.117] |
| rocket_tornado | wait | value_rocket_clump | 4-6 | 81 | +0.037 | [-0.022, +0.104] |
| rocket_tornado | wait | value_rocket_clump | 6-8 | 42 | +0.056 | [-0.023, +0.144] |
| rocket_tornado | wait | xbow_hand | no xbow in hand | 45 | +0.046 | [-0.011, +0.105] |
| rocket_tornado | wait | xbow_hand | xbow in hand | 101 | +0.037 | [-0.021, +0.097] |
| siege | front | elixir | elixir < 8 | 185 | -0.010 | [-0.054, +0.035] |
| siege | front | opp | exploiter | 147 | -0.007 | [-0.061, +0.049] |
| siege | front | opp | exploiter_league | 33 | -0.071 | [-0.152, +0.022] |
| siege | front | opp_bank | bank<2 | 87 | -0.054 | [-0.122, +0.017] |
| siege | front | opp_bank | bank>=2 | 105 | +0.011 | [-0.044, +0.068] |
| siege | front | policy | policy played | 35 | -0.070 | [-0.155, +0.010] |
| siege | front | policy | policy waited | 157 | -0.007 | [-0.053, +0.043] |
| siege | front | safe_idle | safe & idle (no foe on our half, policy waited) | 80 | -0.008 | [-0.062, +0.047] |
| siege | front | target | other mortar | 155 | -0.011 | [-0.062, +0.042] |
| siege | front | target_class | other | 192 | -0.018 | [-0.063, +0.029] |
| siege | front | threat | foe on our half | 94 | -0.017 | [-0.087, +0.052] |
| siege | front | threat | no foe body on our half | 98 | -0.020 | [-0.067, +0.026] |
| siege | front | xbow_hand | no xbow in hand | 65 | +0.014 | [-0.075, +0.097] |
| siege | front | xbow_hand | xbow in hand | 127 | -0.035 | [-0.075, +0.009] |
| siege | rocket_on | elixir | elixir < 8 | 72 | -0.206 * | [-0.280, -0.136] |
| siege | rocket_on | opp | exploiter | 63 | -0.209 * | [-0.296, -0.130] |
| siege | rocket_on | opp_bank | bank<2 | 35 | -0.284 * | [-0.403, -0.165] |
| siege | rocket_on | opp_bank | bank>=2 | 43 | -0.142 * | [-0.216, -0.075] |
| siege | rocket_on | policy | policy played | 21 | -0.238 * | [-0.397, -0.095] |
| siege | rocket_on | policy | policy waited | 57 | -0.194 * | [-0.276, -0.111] |
| siege | rocket_on | safe_idle | safe & idle (no foe on our half, policy waited) | 35 | -0.240 * | [-0.345, -0.136] |
| siege | rocket_on | target | other mortar | 61 | -0.169 * | [-0.245, -0.098] |
| siege | rocket_on | target_class | other | 78 | -0.206 * | [-0.275, -0.142] |
| siege | rocket_on | threat | foe on our half | 29 | -0.158 * | [-0.294, -0.022] |
| siege | rocket_on | threat | no foe body on our half | 49 | -0.235 * | [-0.320, -0.152] |
| siege | rocket_on | xbow_hand | no xbow in hand | 21 | -0.189 * | [-0.327, -0.054] |
| siege | rocket_on | xbow_hand | xbow in hand | 57 | -0.212 * | [-0.288, -0.138] |
| siege | troop_on | elixir | elixir < 8 | 131 | -0.034 | [-0.086, +0.019] |
| siege | troop_on | opp | exploiter | 105 | -0.005 | [-0.070, +0.060] |
| siege | troop_on | opp | exploiter_league | 27 | -0.108 * | [-0.169, -0.033] |
| siege | troop_on | opp_bank | bank<2 | 59 | -0.055 | [-0.131, +0.029] |
| siege | troop_on | opp_bank | bank>=2 | 77 | -0.010 | [-0.075, +0.059] |
| siege | troop_on | policy | policy played | 22 | -0.015 | [-0.125, +0.110] |
| siege | troop_on | policy | policy waited | 114 | -0.032 | [-0.083, +0.020] |
| siege | troop_on | safe_idle | safe & idle (no foe on our half, policy waited) | 62 | -0.022 | [-0.081, +0.036] |
| siege | troop_on | target | other mortar | 103 | -0.018 | [-0.080, +0.046] |
| siege | troop_on | target_class | other | 136 | -0.029 | [-0.079, +0.020] |
| siege | troop_on | threat | foe on our half | 66 | -0.032 | [-0.102, +0.047] |
| siege | troop_on | threat | no foe body on our half | 70 | -0.027 | [-0.085, +0.025] |
| siege | troop_on | xbow_hand | no xbow in hand | 43 | -0.008 | [-0.083, +0.067] |
| siege | troop_on | xbow_hand | xbow in hand | 93 | -0.040 | [-0.097, +0.020] |
| siege | wait | elixir | elixir < 8 | 48 | -0.035 | [-0.108, +0.033] |
| siege | wait | opp | exploiter | 34 | -0.015 | [-0.100, +0.077] |
| siege | wait | opp_bank | bank<2 | 24 | -0.072 | [-0.184, +0.030] |
| siege | wait | opp_bank | bank>=2 | 27 | +0.019 | [-0.056, +0.101] |
| siege | wait | policy | policy played | 51 | -0.024 | [-0.092, +0.040] |
| siege | wait | target | other mortar | 41 | -0.005 | [-0.083, +0.069] |
| siege | wait | target_class | other | 51 | -0.024 | [-0.092, +0.040] |
| siege | wait | threat | foe on our half | 26 | +0.034 | [-0.063, +0.115] |
| siege | wait | threat | no foe body on our half | 25 | -0.083 | [-0.174, +0.003] |
| siege | wait | xbow_hand | no xbow in hand | 24 | +0.017 | [-0.087, +0.111] |
| siege | wait | xbow_hand | xbow in hand | 27 | -0.060 | [-0.155, +0.027] |
| tornado_redirect | tornado_king | counter | counter in hand | 252 | -0.160 * | [-0.199, -0.123] |
| tornado_redirect | tornado_king | dist | dist 6+ | 167 | -0.140 * | [-0.189, -0.089] |
| tornado_redirect | tornado_king | dist | dist < 6 | 85 | -0.199 * | [-0.263, -0.141] |
| tornado_redirect | tornado_king | elixir | elixir < 8 | 245 | -0.161 * | [-0.201, -0.124] |
| tornado_redirect | tornado_king | opp | exploiter | 134 | -0.160 * | [-0.207, -0.113] |
| tornado_redirect | tornado_king | opp | exploiter_league | 71 | -0.176 * | [-0.250, -0.106] |
| tornado_redirect | tornado_king | opp | init | 34 | -0.162 * | [-0.253, -0.083] |
| tornado_redirect | tornado_king | opp_bank | bank<2 | 116 | -0.196 * | [-0.253, -0.137] |
| tornado_redirect | tornado_king | opp_bank | bank>=2 | 136 | -0.129 * | [-0.177, -0.086] |
| tornado_redirect | tornado_king | policy | policy played | 45 | -0.175 * | [-0.273, -0.090] |
| tornado_redirect | tornado_king | policy | policy waited | 207 | -0.156 * | [-0.197, -0.116] |
| tornado_redirect | tornado_king | safe_idle | safe & idle (no foe on our half, policy waited) | 36 | -0.195 * | [-0.311, -0.084] |
| tornado_redirect | tornado_king | target | other barbarians | 21 | -0.203 * | [-0.352, -0.084] |
| tornado_redirect | tornado_king | target | other skeletons | 35 | -0.193 * | [-0.284, -0.106] |
| tornado_redirect | tornado_king | target_class | heavy | 22 | -0.163 * | [-0.294, -0.031] |
| tornado_redirect | tornado_king | target_class | hoglike | 24 | -0.172 * | [-0.277, -0.071] |
| tornado_redirect | tornado_king | target_class | other | 206 | -0.158 * | [-0.199, -0.119] |
| tornado_redirect | tornado_king | threat | foe on our half | 205 | -0.154 * | [-0.197, -0.113] |
| tornado_redirect | tornado_king | threat | no foe body on our half | 47 | -0.185 * | [-0.281, -0.096] |
| tornado_redirect | tornado_king | xbow_hand | no xbow in hand | 97 | -0.136 * | [-0.188, -0.086] |
| tornado_redirect | tornado_king | xbow_hand | xbow in hand | 155 | -0.175 * | [-0.226, -0.124] |
| tornado_redirect | tornado_on | counter | counter in hand | 252 | -0.111 * | [-0.149, -0.075] |
| tornado_redirect | tornado_on | dist | dist 6+ | 167 | -0.077 * | [-0.124, -0.027] |
| tornado_redirect | tornado_on | dist | dist < 6 | 85 | -0.179 * | [-0.238, -0.126] |
| tornado_redirect | tornado_on | elixir | elixir < 8 | 245 | -0.111 * | [-0.150, -0.071] |
| tornado_redirect | tornado_on | opp | exploiter | 134 | -0.114 * | [-0.164, -0.066] |
| tornado_redirect | tornado_on | opp | exploiter_league | 71 | -0.148 * | [-0.233, -0.070] |
| tornado_redirect | tornado_on | opp | init | 34 | -0.090 * | [-0.174, -0.002] |
| tornado_redirect | tornado_on | opp_bank | bank<2 | 116 | -0.136 * | [-0.187, -0.085] |
| tornado_redirect | tornado_on | opp_bank | bank>=2 | 136 | -0.090 * | [-0.148, -0.035] |
| tornado_redirect | tornado_on | policy | policy played | 45 | -0.147 * | [-0.230, -0.074] |
| tornado_redirect | tornado_on | policy | policy waited | 207 | -0.104 * | [-0.145, -0.063] |
| tornado_redirect | tornado_on | safe_idle | safe & idle (no foe on our half, policy waited) | 36 | -0.155 * | [-0.280, -0.030] |
| tornado_redirect | tornado_on | target | other barbarians | 21 | -0.081 * | [-0.151, -0.015] |
| tornado_redirect | tornado_on | target | other skeletons | 35 | -0.148 * | [-0.266, -0.036] |
| tornado_redirect | tornado_on | target_class | heavy | 22 | -0.058 | [-0.166, +0.034] |
| tornado_redirect | tornado_on | target_class | hoglike | 24 | +0.024 | [-0.126, +0.201] |
| tornado_redirect | tornado_on | target_class | other | 206 | -0.133 * | [-0.172, -0.095] |
| tornado_redirect | tornado_on | threat | foe on our half | 205 | -0.100 * | [-0.140, -0.057] |
| tornado_redirect | tornado_on | threat | no foe body on our half | 47 | -0.162 * | [-0.269, -0.062] |
| tornado_redirect | tornado_on | xbow_hand | no xbow in hand | 97 | -0.104 * | [-0.160, -0.052] |
| tornado_redirect | tornado_on | xbow_hand | xbow in hand | 155 | -0.116 * | [-0.166, -0.065] |
| tornado_redirect | wait | counter | counter in hand | 45 | +0.005 | [-0.043, +0.048] |
| tornado_redirect | wait | dist | dist 6+ | 30 | +0.031 | [-0.009, +0.072] |
| tornado_redirect | wait | elixir | elixir < 8 | 43 | +0.020 | [-0.028, +0.060] |
| tornado_redirect | wait | opp | exploiter | 24 | +0.003 | [-0.045, +0.050] |
| tornado_redirect | wait | opp_bank | bank>=2 | 26 | +0.017 | [-0.024, +0.057] |
| tornado_redirect | wait | policy | policy played | 45 | +0.005 | [-0.043, +0.048] |
| tornado_redirect | wait | target_class | other | 42 | +0.003 | [-0.046, +0.049] |
| tornado_redirect | wait | threat | foe on our half | 34 | -0.015 | [-0.073, +0.038] |
| tornado_redirect | wait | xbow_hand | no xbow in hand | 28 | +0.027 | [-0.017, +0.070] |
| wincon | cheap_on | elixir | elixir < 8 | 35 | -0.030 | [-0.097, +0.033] |
| wincon | cheap_on | opp_bank | bank>=2 | 21 | -0.008 | [-0.109, +0.087] |
| wincon | cheap_on | policy | policy waited | 32 | -0.059 | [-0.135, +0.022] |
| wincon | cheap_on | threat | foe on our half | 37 | -0.050 | [-0.119, +0.016] |
| wincon | cheap_on | xbow_hand | xbow in hand | 27 | -0.055 | [-0.144, +0.033] |
| wincon | rocket_on | elixir | elixir < 8 | 69 | -0.200 * | [-0.285, -0.125] |
| wincon | rocket_on | opp | exploiter | 42 | -0.218 * | [-0.335, -0.113] |
| wincon | rocket_on | opp_bank | bank<2 | 34 | -0.218 * | [-0.349, -0.107] |
| wincon | rocket_on | opp_bank | bank>=2 | 38 | -0.188 * | [-0.289, -0.094] |
| wincon | rocket_on | policy | policy waited | 60 | -0.213 * | [-0.299, -0.129] |
| wincon | rocket_on | target_class | heavy | 29 | -0.249 * | [-0.409, -0.117] |
| wincon | rocket_on | target_class | hoglike | 38 | -0.180 * | [-0.274, -0.093] |
| wincon | rocket_on | threat | foe on our half | 72 | -0.203 * | [-0.284, -0.128] |
| wincon | rocket_on | xbow_hand | xbow in hand | 57 | -0.221 * | [-0.315, -0.133] |
| wincon | troop_on | elixir | elixir < 8 | 232 | -0.034 | [-0.070, +0.003] |
| wincon | troop_on | opp | exploiter | 118 | -0.056 * | [-0.108, -0.006] |
| wincon | troop_on | opp | exploiter_league | 70 | -0.003 | [-0.074, +0.066] |
| wincon | troop_on | opp | init | 42 | +0.013 | [-0.056, +0.077] |
| wincon | troop_on | opp_bank | bank<2 | 118 | -0.020 | [-0.075, +0.033] |
| wincon | troop_on | opp_bank | bank>=2 | 117 | -0.053 * | [-0.102, -0.004] |
| wincon | troop_on | policy | policy played | 42 | -0.016 | [-0.071, +0.035] |
| wincon | troop_on | policy | policy waited | 193 | -0.041 | [-0.085, +0.002] |
| wincon | troop_on | target | heavy golem | 29 | -0.011 | [-0.082, +0.055] |
| wincon | troop_on | target | heavy royalgiant | 31 | -0.087 | [-0.211, +0.031] |
| wincon | troop_on | target | hoglike battleram | 20 | +0.013 | [-0.069, +0.110] |
| wincon | troop_on | target | hoglike hogrider | 34 | -0.018 | [-0.097, +0.058] |
| wincon | troop_on | target | hoglike royalhogs | 23 | +0.088 | [-0.006, +0.177] |
| wincon | troop_on | target | other balloon | 36 | -0.013 | [-0.133, +0.096] |
| wincon | troop_on | target_class | heavy | 110 | -0.071 * | [-0.125, -0.018] |
| wincon | troop_on | target_class | hoglike | 89 | -0.004 | [-0.057, +0.045] |
| wincon | troop_on | target_class | other | 36 | -0.013 | [-0.133, +0.096] |
| wincon | troop_on | threat | foe on our half | 235 | -0.037 | [-0.071, +0.000] |
| wincon | troop_on | xbow_hand | no xbow in hand | 62 | +0.001 | [-0.050, +0.051] |
| wincon | troop_on | xbow_hand | xbow in hand | 173 | -0.050 * | [-0.096, -0.005] |
| wincon | wait | elixir | elixir < 8 | 55 | -0.014 | [-0.087, +0.062] |
| wincon | wait | opp | exploiter | 36 | -0.002 | [-0.105, +0.103] |
| wincon | wait | opp_bank | bank<2 | 27 | +0.051 | [-0.031, +0.136] |
| wincon | wait | opp_bank | bank>=2 | 28 | -0.077 | [-0.193, +0.040] |
| wincon | wait | policy | policy played | 55 | -0.014 | [-0.087, +0.062] |
| wincon | wait | target_class | heavy | 34 | -0.054 | [-0.170, +0.067] |
| wincon | wait | threat | foe on our half | 55 | -0.014 | [-0.087, +0.062] |
| wincon | wait | xbow_hand | xbow in hand | 37 | -0.030 | [-0.127, +0.070] |
| xbow | wait | elixir | elixir < 8 | 198 | +0.009 | [-0.026, +0.045] |
| xbow | wait | elixir | elixir >= 8 | 98 | +0.001 | [-0.049, +0.053] |
| xbow | wait | opp | exploiter | 151 | +0.016 | [-0.025, +0.056] |
| xbow | wait | opp | exploiter_league | 86 | -0.022 | [-0.089, +0.043] |
| xbow | wait | opp | init | 39 | -0.013 | [-0.079, +0.051] |
| xbow | wait | opp | snapshot | 20 | +0.098 * | [+0.045, +0.154] |
| xbow | wait | opp_bank | bank<2 | 145 | -0.011 | [-0.056, +0.033] |
| xbow | wait | opp_bank | bank>=2 | 151 | +0.024 | [-0.015, +0.062] |
| xbow | wait | policy | policy played | 296 | +0.006 | [-0.024, +0.035] |
| xbow | wait | threat | foe on our half | 68 | +0.013 | [-0.047, +0.072] |
| xbow | wait | threat | no foe body on our half | 228 | +0.004 | [-0.027, +0.036] |
| xbow | wait | xbow_hand | xbow in hand | 296 | +0.006 | [-0.024, +0.035] |
| xbow | xbow_defensive | elixir | elixir < 8 | 198 | -0.139 * | [-0.185, -0.097] |
| xbow | xbow_defensive | elixir | elixir >= 8 | 98 | -0.162 * | [-0.228, -0.099] |
| xbow | xbow_defensive | opp | exploiter | 151 | -0.113 * | [-0.161, -0.062] |
| xbow | xbow_defensive | opp | exploiter_league | 86 | -0.178 * | [-0.259, -0.101] |
| xbow | xbow_defensive | opp | init | 39 | -0.207 * | [-0.272, -0.146] |
| xbow | xbow_defensive | opp | snapshot | 20 | -0.152 * | [-0.299, -0.029] |
| xbow | xbow_defensive | opp_bank | bank<2 | 145 | -0.131 * | [-0.180, -0.081] |
| xbow | xbow_defensive | opp_bank | bank>=2 | 151 | -0.162 * | [-0.218, -0.112] |
| xbow | xbow_defensive | policy | policy played | 296 | -0.147 * | [-0.182, -0.112] |
| xbow | xbow_defensive | threat | foe on our half | 68 | -0.131 * | [-0.200, -0.063] |
| xbow | xbow_defensive | threat | no foe body on our half | 228 | -0.151 * | [-0.191, -0.108] |
| xbow | xbow_defensive | xbow_hand | xbow in hand | 296 | -0.147 * | [-0.182, -0.112] |
| xbow | xbow_other_lane | elixir | elixir < 8 | 198 | -0.067 * | [-0.113, -0.023] |
| xbow | xbow_other_lane | elixir | elixir >= 8 | 98 | -0.064 * | [-0.122, -0.007] |
| xbow | xbow_other_lane | opp | exploiter | 151 | -0.008 | [-0.055, +0.039] |
| xbow | xbow_other_lane | opp | exploiter_league | 86 | -0.129 * | [-0.212, -0.051] |
| xbow | xbow_other_lane | opp | init | 39 | -0.155 * | [-0.220, -0.091] |
| xbow | xbow_other_lane | opp | snapshot | 20 | -0.058 | [-0.164, +0.043] |
| xbow | xbow_other_lane | opp_bank | bank<2 | 145 | -0.043 | [-0.093, +0.007] |
| xbow | xbow_other_lane | opp_bank | bank>=2 | 151 | -0.088 * | [-0.140, -0.037] |
| xbow | xbow_other_lane | policy | policy played | 296 | -0.066 * | [-0.102, -0.031] |
| xbow | xbow_other_lane | threat | foe on our half | 68 | -0.034 | [-0.107, +0.036] |
| xbow | xbow_other_lane | threat | no foe body on our half | 228 | -0.075 * | [-0.119, -0.034] |
| xbow | xbow_other_lane | xbow_hand | xbow in hand | 296 | -0.066 * | [-0.102, -0.031] |
| xbow_after_fail | rocket_princess | elixir | elixir < 8 | 180 | -0.139 * | [-0.193, -0.087] |
| xbow_after_fail | rocket_princess | elixir | elixir >= 8 | 20 | -0.327 * | [-0.503, -0.173] |
| xbow_after_fail | rocket_princess | opp | exploiter | 83 | -0.191 * | [-0.258, -0.124] |
| xbow_after_fail | rocket_princess | opp | exploiter_league | 64 | -0.139 * | [-0.239, -0.038] |
| xbow_after_fail | rocket_princess | opp | init | 30 | -0.085 | [-0.266, +0.125] |
| xbow_after_fail | rocket_princess | opp | snapshot | 23 | -0.180 * | [-0.298, -0.064] |
| xbow_after_fail | rocket_princess | opp_bank | bank<2 | 103 | -0.166 * | [-0.249, -0.076] |
| xbow_after_fail | rocket_princess | opp_bank | bank>=2 | 97 | -0.148 * | [-0.211, -0.085] |
| xbow_after_fail | rocket_princess | policy | policy played | 51 | -0.167 * | [-0.262, -0.076] |
| xbow_after_fail | rocket_princess | policy | policy waited | 149 | -0.154 * | [-0.219, -0.085] |
| xbow_after_fail | rocket_princess | safe_idle | safe & idle (no foe on our half, policy waited) | 81 | -0.224 * | [-0.308, -0.142] |
| xbow_after_fail | rocket_princess | threat | foe on our half | 95 | -0.076 * | [-0.143, -0.007] |
| xbow_after_fail | rocket_princess | threat | no foe body on our half | 105 | -0.231 * | [-0.307, -0.159] |
| xbow_after_fail | rocket_princess | xbow_hand | xbow in hand | 200 | -0.157 * | [-0.213, -0.103] |
| xbow_after_fail | wait | elixir | elixir < 8 | 40 | -0.069 | [-0.171, +0.021] |
| xbow_after_fail | wait | opp | exploiter | 24 | -0.052 | [-0.145, +0.039] |
| xbow_after_fail | wait | opp_bank | bank<2 | 25 | -0.119 | [-0.279, +0.004] |
| xbow_after_fail | wait | opp_bank | bank>=2 | 26 | +0.015 | [-0.077, +0.110] |
| xbow_after_fail | wait | policy | policy played | 51 | -0.051 | [-0.137, +0.030] |
| xbow_after_fail | wait | threat | foe on our half | 27 | +0.025 | [-0.011, +0.073] |
| xbow_after_fail | wait | threat | no foe body on our half | 24 | -0.137 | [-0.318, +0.024] |
| xbow_after_fail | wait | xbow_hand | xbow in hand | 51 | -0.051 | [-0.137, +0.030] |
| xbow_after_fail | xbow_defensive | elixir | elixir < 8 | 185 | -0.066 * | [-0.118, -0.015] |
| xbow_after_fail | xbow_defensive | elixir | elixir >= 8 | 21 | -0.085 | [-0.216, +0.046] |
| xbow_after_fail | xbow_defensive | opp | exploiter | 83 | -0.110 * | [-0.191, -0.034] |
| xbow_after_fail | xbow_defensive | opp | exploiter_league | 69 | -0.043 | [-0.126, +0.032] |
| xbow_after_fail | xbow_defensive | opp | init | 30 | -0.012 | [-0.193, +0.190] |
| xbow_after_fail | xbow_defensive | opp | snapshot | 24 | -0.066 | [-0.150, +0.018] |
| xbow_after_fail | xbow_defensive | opp_bank | bank<2 | 106 | -0.098 * | [-0.172, -0.022] |
| xbow_after_fail | xbow_defensive | opp_bank | bank>=2 | 100 | -0.036 | [-0.103, +0.030] |
| xbow_after_fail | xbow_defensive | policy | policy played | 50 | -0.117 * | [-0.229, -0.012] |
| xbow_after_fail | xbow_defensive | policy | policy waited | 156 | -0.052 | [-0.110, +0.007] |
| xbow_after_fail | xbow_defensive | safe_idle | safe & idle (no foe on our half, policy waited) | 87 | -0.041 | [-0.104, +0.021] |
| xbow_after_fail | xbow_defensive | threat | foe on our half | 96 | -0.068 | [-0.144, +0.007] |
| xbow_after_fail | xbow_defensive | threat | no foe body on our half | 110 | -0.068 * | [-0.135, -0.005] |
| xbow_after_fail | xbow_defensive | xbow_hand | xbow in hand | 206 | -0.068 * | [-0.120, -0.016] |
| xbow_after_fail | xbow_reach | elixir | elixir < 8 | 147 | -0.022 | [-0.074, +0.031] |
| xbow_after_fail | xbow_reach | opp | exploiter | 61 | -0.020 | [-0.084, +0.046] |
| xbow_after_fail | xbow_reach | opp | exploiter_league | 52 | -0.036 | [-0.123, +0.040] |
| xbow_after_fail | xbow_reach | opp | init | 24 | +0.001 | [-0.162, +0.173] |
| xbow_after_fail | xbow_reach | opp | snapshot | 20 | -0.064 | [-0.164, +0.047] |
| xbow_after_fail | xbow_reach | opp_bank | bank<2 | 83 | -0.036 | [-0.099, +0.029] |
| xbow_after_fail | xbow_reach | opp_bank | bank>=2 | 74 | -0.019 | [-0.084, +0.048] |
| xbow_after_fail | xbow_reach | policy | policy waited | 156 | -0.026 | [-0.072, +0.023] |
| xbow_after_fail | xbow_reach | safe_idle | safe & idle (no foe on our half, policy waited) | 87 | -0.037 | [-0.094, +0.016] |
| xbow_after_fail | xbow_reach | threat | foe on our half | 69 | -0.012 | [-0.094, +0.067] |
| xbow_after_fail | xbow_reach | threat | no foe body on our half | 88 | -0.040 | [-0.099, +0.016] |
| xbow_after_fail | xbow_reach | xbow_hand | xbow in hand | 157 | -0.028 | [-0.076, +0.019] |

### Horizon profile: mean dQ (alt - chosen), same samples in every column (terminal = audited samples only)


| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_clump | yes | 56 | -0.211 [-0.30, -0.13] | -0.124 [-0.15, -0.09] | -0.165 [-0.21, -0.12] | -0.205 [-0.28, -0.13] | -0.254 [-0.33, -0.18] | -0.216 [-0.30, -0.13] | -0.112 [-0.26, +0.03] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_clump | no | 130 | -0.230 [-0.29, -0.17] | -0.126 [-0.15, -0.10] | -0.172 [-0.20, -0.14] | -0.207 [-0.25, -0.16] | -0.242 [-0.30, -0.19] | -0.220 [-0.28, -0.16] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_princess | yes | 97 | -0.242 [-0.30, -0.18] | -0.109 [-0.13, -0.09] | -0.129 [-0.16, -0.10] | -0.171 [-0.21, -0.13] | -0.224 [-0.28, -0.17] | -0.244 [-0.30, -0.19] | -0.220 [-0.36, -0.09] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_princess | no | 235 | -0.262 [-0.31, -0.22] | -0.115 [-0.13, -0.10] | -0.154 [-0.17, -0.13] | -0.201 [-0.23, -0.17] | -0.242 [-0.28, -0.21] | -0.264 [-0.31, -0.22] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_played | second_card | yes | 56 | -0.066 [-0.12, -0.01] | -0.047 [-0.08, -0.01] | -0.092 [-0.14, -0.04] | -0.050 [-0.11, +0.01] | -0.095 [-0.15, -0.04] | -0.064 [-0.12, -0.01] | +0.020 [-0.15, +0.20] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_played | second_card | no | 124 | -0.058 [-0.10, -0.01] | -0.033 [-0.05, -0.01] | -0.064 [-0.10, -0.03] | -0.041 [-0.08, -0.00] | -0.043 [-0.09, +0.00] | -0.038 [-0.09, +0.01] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_played | wait | yes | 56 | +0.027 [-0.04, +0.10] | -0.009 [-0.04, +0.02] | -0.013 [-0.06, +0.03] | +0.022 [-0.04, +0.09] | -0.023 [-0.08, +0.04] | +0.004 [-0.06, +0.07] | +0.000 [-0.20, +0.21] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_played | wait | no | 124 | -0.044 [-0.09, +0.00] | -0.008 [-0.03, +0.01] | -0.028 [-0.06, -0.00] | -0.022 [-0.06, +0.02] | -0.039 [-0.08, +0.00] | -0.046 [-0.09, -0.00] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | combo | yes | 109 | -0.333 [-0.41, -0.26] | -0.189 [-0.22, -0.16] | -0.236 [-0.27, -0.20] | -0.255 [-0.31, -0.20] | -0.290 [-0.35, -0.23] | -0.326 [-0.39, -0.26] | -0.187 [-0.34, -0.04] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | combo | no | 272 | -0.338 [-0.38, -0.29] | -0.209 [-0.23, -0.19] | -0.258 [-0.29, -0.23] | -0.281 [-0.31, -0.25] | -0.296 [-0.33, -0.26] | -0.340 [-0.39, -0.30] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | rocket_clump | yes | 109 | -0.280 [-0.35, -0.22] | -0.140 [-0.17, -0.11] | -0.181 [-0.22, -0.15] | -0.213 [-0.26, -0.17] | -0.239 [-0.29, -0.19] | -0.259 [-0.32, -0.20] | -0.215 [-0.38, -0.06] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | rocket_clump | no | 272 | -0.271 [-0.31, -0.23] | -0.150 [-0.17, -0.13] | -0.183 [-0.21, -0.16] | -0.220 [-0.25, -0.19] | -0.247 [-0.28, -0.21] | -0.265 [-0.30, -0.23] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | wait | yes | 54 | +0.018 [-0.04, +0.08] | -0.015 [-0.04, +0.00] | -0.007 [-0.03, +0.02] | +0.002 [-0.03, +0.03] | +0.027 [-0.02, +0.07] | -0.001 [-0.05, +0.05] | +0.024 [-0.09, +0.14] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | wait | no | 133 | +0.029 [-0.01, +0.07] | -0.009 [-0.02, +0.00] | -0.020 [-0.04, -0.00] | -0.015 [-0.03, +0.01] | +0.017 [-0.01, +0.04] | +0.010 [-0.02, +0.04] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| siege | front | yes | 88 | +0.001 [-0.05, +0.06] | -0.006 [-0.02, +0.01] | -0.011 [-0.04, +0.02] | -0.035 [-0.07, +0.00] | -0.024 [-0.07, +0.02] | -0.010 [-0.06, +0.04] | -0.044 [-0.18, +0.08] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| siege | front | no | 191 | -0.019 [-0.06, +0.03] | +0.001 [-0.01, +0.01] | -0.013 [-0.03, +0.00] | -0.029 [-0.06, -0.00] | -0.019 [-0.06, +0.02] | -0.021 [-0.06, +0.02] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| siege | rocket_on | yes | 41 | -0.087 [-0.19, +0.01] | -0.087 [-0.12, -0.05] | -0.077 [-0.13, -0.03] | -0.153 [-0.22, -0.09] | -0.131 [-0.21, -0.06] | -0.099 [-0.18, -0.01] | -0.005 [-0.27, +0.26] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| siege | rocket_on | no | 78 | -0.206 [-0.28, -0.14] | -0.099 [-0.13, -0.07] | -0.109 [-0.14, -0.07] | -0.179 [-0.23, -0.13] | -0.205 [-0.27, -0.15] | -0.197 [-0.26, -0.14] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| siege | troop_on | yes | 60 | +0.019 [-0.03, +0.08] | -0.021 [-0.04, -0.00] | +0.001 [-0.02, +0.03] | -0.036 [-0.07, -0.00] | -0.016 [-0.06, +0.03] | +0.005 [-0.06, +0.06] | +0.023 [-0.17, +0.20] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| siege | troop_on | no | 135 | -0.030 [-0.08, +0.02] | -0.009 [-0.02, +0.01] | -0.014 [-0.03, +0.00] | -0.030 [-0.06, -0.00] | -0.020 [-0.06, +0.02] | -0.026 [-0.07, +0.02] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| siege | wait | yes | 25 | +0.014 [-0.05, +0.07] | -0.007 [-0.03, +0.02] | +0.010 [-0.03, +0.05] | -0.004 [-0.05, +0.05] | +0.020 [-0.03, +0.07] | +0.027 [-0.03, +0.08] | -0.128 [-0.39, +0.14] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| siege | wait | no | 51 | -0.024 [-0.09, +0.04] | +0.000 [-0.02, +0.02] | -0.007 [-0.04, +0.02] | +0.008 [-0.04, +0.06] | +0.021 [-0.04, +0.08] | -0.008 [-0.07, +0.05] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| tornado_redirect | tornado_king | yes | 96 | -0.121 [-0.17, -0.07] | -0.097 [-0.12, -0.07] | -0.128 [-0.16, -0.10] | -0.131 [-0.17, -0.09] | -0.136 [-0.18, -0.09] | -0.136 [-0.18, -0.09] | -0.098 [-0.25, +0.05] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| tornado_redirect | tornado_king | no | 232 | -0.157 [-0.20, -0.12] | -0.095 [-0.11, -0.08] | -0.132 [-0.16, -0.11] | -0.135 [-0.16, -0.11] | -0.152 [-0.18, -0.12] | -0.160 [-0.20, -0.13] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| tornado_redirect | tornado_on | yes | 96 | -0.110 [-0.16, -0.06] | -0.068 [-0.09, -0.05] | -0.099 [-0.13, -0.07] | -0.114 [-0.15, -0.08] | -0.149 [-0.20, -0.10] | -0.132 [-0.18, -0.09] | +0.043 [-0.09, +0.18] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| tornado_redirect | tornado_on | no | 232 | -0.129 [-0.17, -0.10] | -0.073 [-0.09, -0.06] | -0.101 [-0.12, -0.08] | -0.107 [-0.13, -0.08] | -0.142 [-0.17, -0.11] | -0.141 [-0.18, -0.11] |
| tornado_redirect | wait | no | 37 | +0.007 [-0.05, +0.06] | -0.001 [-0.02, +0.02] | -0.013 [-0.05, +0.03] | -0.037 [-0.09, +0.01] | -0.012 [-0.06, +0.03] | -0.006 [-0.06, +0.04] |
| wincon | cheap_on | no | 33 | -0.056 [-0.13, +0.02] | +0.000 [-0.03, +0.03] | +0.002 [-0.03, +0.03] | -0.007 [-0.06, +0.04] | -0.012 [-0.07, +0.05] | -0.046 [-0.12, +0.03] |
| wincon | rocket_on | no | 60 | -0.243 [-0.33, -0.16] | -0.141 [-0.17, -0.11] | -0.159 [-0.20, -0.12] | -0.208 [-0.26, -0.15] | -0.224 [-0.29, -0.16] | -0.265 [-0.35, -0.19] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| wincon | troop_on | yes | 72 | -0.035 [-0.08, +0.01] | -0.006 [-0.02, +0.01] | -0.031 [-0.05, -0.01] | -0.037 [-0.07, -0.00] | -0.025 [-0.07, +0.02] | -0.026 [-0.07, +0.02] | -0.097 [-0.23, +0.04] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| wincon | troop_on | no | 210 | -0.032 [-0.07, +0.00] | -0.013 [-0.03, -0.00] | -0.020 [-0.04, -0.00] | -0.020 [-0.05, +0.01] | -0.027 [-0.06, +0.01] | -0.028 [-0.06, +0.01] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| wincon | wait | yes | 27 | -0.021 [-0.13, +0.11] | +0.038 [-0.00, +0.08] | +0.046 [-0.00, +0.11] | +0.045 [-0.04, +0.14] | +0.058 [-0.03, +0.16] | +0.039 [-0.05, +0.14] | +0.118 [-0.16, +0.41] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| wincon | wait | no | 47 | +0.003 [-0.07, +0.09] | +0.035 [-0.00, +0.08] | +0.044 [-0.00, +0.10] | +0.054 [-0.00, +0.12] | +0.062 [-0.00, +0.13] | +0.054 [-0.01, +0.13] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow | wait | yes | 101 | +0.025 [-0.03, +0.08] | +0.002 [-0.02, +0.02] | -0.003 [-0.03, +0.03] | +0.007 [-0.03, +0.05] | +0.019 [-0.03, +0.07] | +0.024 [-0.02, +0.07] | -0.100 [-0.23, +0.04] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow | wait | no | 265 | +0.007 [-0.03, +0.04] | +0.003 [-0.01, +0.01] | -0.011 [-0.03, +0.01] | -0.005 [-0.03, +0.02] | +0.009 [-0.02, +0.04] | +0.015 [-0.01, +0.04] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow | xbow_defensive | yes | 101 | -0.128 [-0.19, -0.07] | -0.025 [-0.05, -0.00] | -0.100 [-0.13, -0.07] | -0.155 [-0.20, -0.11] | -0.144 [-0.19, -0.09] | -0.136 [-0.19, -0.08] | -0.045 [-0.17, +0.09] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow | xbow_defensive | no | 265 | -0.160 [-0.20, -0.12] | -0.028 [-0.04, -0.02] | -0.110 [-0.13, -0.09] | -0.159 [-0.19, -0.13] | -0.166 [-0.20, -0.13] | -0.160 [-0.20, -0.12] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow | xbow_other_lane | yes | 101 | -0.051 [-0.12, +0.01] | -0.026 [-0.04, -0.01] | -0.028 [-0.06, +0.00] | -0.040 [-0.09, +0.01] | -0.055 [-0.11, -0.00] | -0.046 [-0.11, +0.01] | -0.122 [-0.27, +0.04] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow | xbow_other_lane | no | 265 | -0.077 [-0.12, -0.04] | -0.026 [-0.04, -0.02] | -0.043 [-0.06, -0.02] | -0.070 [-0.10, -0.04] | -0.089 [-0.13, -0.05] | -0.080 [-0.12, -0.04] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | rocket_princess | yes | 74 | -0.258 [-0.35, -0.17] | -0.084 [-0.11, -0.06] | -0.105 [-0.15, -0.06] | -0.169 [-0.23, -0.10] | -0.219 [-0.30, -0.14] | -0.219 [-0.30, -0.14] | -0.247 [-0.43, -0.06] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | rocket_princess | no | 166 | -0.206 [-0.26, -0.16] | -0.085 [-0.10, -0.07] | -0.103 [-0.13, -0.07] | -0.147 [-0.19, -0.11] | -0.179 [-0.23, -0.14] | -0.175 [-0.22, -0.13] |
| xbow_after_fail | wait | no | 36 | -0.018 [-0.10, +0.07] | -0.004 [-0.03, +0.02] | -0.028 [-0.06, +0.00] | -0.030 [-0.08, +0.02] | -0.041 [-0.12, +0.03] | -0.039 [-0.11, +0.03] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | xbow_defensive | yes | 76 | -0.115 [-0.18, -0.05] | -0.029 [-0.05, -0.01] | -0.036 [-0.07, -0.00] | -0.067 [-0.11, -0.02] | -0.101 [-0.15, -0.05] | -0.077 [-0.13, -0.02] | -0.092 [-0.23, +0.05] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | xbow_defensive | no | 169 | -0.082 [-0.13, -0.04] | -0.034 [-0.05, -0.02] | -0.036 [-0.06, -0.01] | -0.072 [-0.10, -0.04] | -0.085 [-0.12, -0.05] | -0.060 [-0.10, -0.02] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | xbow_reach | yes | 59 | -0.060 [-0.13, +0.02] | -0.018 [-0.04, +0.00] | +0.007 [-0.03, +0.05] | +0.000 [-0.05, +0.06] | -0.037 [-0.10, +0.03] | -0.018 [-0.09, +0.06] | -0.054 [-0.24, +0.13] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| xbow_after_fail | xbow_reach | no | 135 | -0.038 [-0.08, +0.01] | -0.020 [-0.04, -0.01] | -0.001 [-0.02, +0.02] | -0.003 [-0.04, +0.03] | -0.014 [-0.05, +0.03] | -0.011 [-0.05, +0.03] |

### Where dQ comes from (main stop, alt - chosen): Phi (towers) vs critic vs snapshot and play-count differences

| trigger | alternative | dQ | dPhi | dCritic | d own princess lost | d own king lost | d FOE princess lost | d foe king lost | d own crowns lost | d foe crowns lost | d own elixir | d foe elixir | d own plays | d FOE plays | d own king on | d foe king on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_clump (n 148) | -0.202 [-0.26, -0.15] | -0.125 [-0.16, -0.09] | -0.171 [-0.21, -0.13] | +0.157 [+0.11, +0.20] | +0.030 [+0.01, +0.05] | -0.103 [-0.14, -0.06] | +0.004 [+0.00, +0.01] | +0.092 [+0.04, +0.15] | -0.018 [-0.05, +0.01] | -0.226 [-0.61, +0.13] | +0.058 [-0.27, +0.37] | -0.330 [-0.48, -0.17] | -0.115 [-0.24, +0.01] | +0.041 [-0.01, +0.09] | +0.055 [+0.00, +0.11] |
| rocket | rocket_princess (n 256) | -0.241 [-0.28, -0.20] | -0.127 [-0.15, -0.11] | -0.192 [-0.22, -0.16] | +0.198 [+0.16, +0.23] | +0.031 [+0.02, +0.05] | -0.078 [-0.11, -0.05] | -0.001 [-0.00, +0.00] | +0.121 [+0.08, +0.16] | -0.036 [-0.06, -0.01] | -0.088 [-0.34, +0.16] | +0.175 [-0.07, +0.41] | -0.345 [-0.44, -0.25] | -0.193 [-0.30, -0.09] | +0.101 [+0.07, +0.14] | -0.034 [-0.06, -0.01] |
| rocket_played | second_card (n 159) | -0.069 [-0.11, -0.03] | -0.030 [-0.06, -0.00] | -0.036 [-0.07, +0.00] | -0.004 [-0.04, +0.04] | -0.011 [-0.02, +0.00] | -0.067 [-0.11, -0.03] | -0.000 [-0.00, +0.00] | -0.010 [-0.05, +0.03] | +0.005 [-0.02, +0.03] | +0.334 [-0.04, +0.69] | +0.431 [+0.09, +0.74] | +0.798 [+0.63, +0.96] | -0.106 [-0.25, +0.04] | -0.020 [-0.06, +0.03] | +0.005 [-0.02, +0.04] |
| rocket_played | wait (n 159) | -0.035 [-0.07, +0.00] | -0.026 [-0.04, -0.01] | -0.050 [-0.09, -0.01] | +0.017 [-0.02, +0.05] | -0.008 [-0.02, +0.00] | -0.035 [-0.07, -0.01] | -0.000 [-0.00, +0.00] | -0.005 [-0.04, +0.03] | -0.015 [-0.03, +0.00] | +0.360 [+0.02, +0.68] | -0.105 [-0.40, +0.17] | +0.181 [+0.02, +0.33] | -0.093 [-0.25, +0.06] | -0.010 [-0.05, +0.03] | -0.010 [-0.03, +0.02] |
| rocket_tornado | combo (n 299) | -0.314 [-0.36, -0.27] | -0.165 [-0.19, -0.14] | -0.213 [-0.24, -0.18] | +0.220 [+0.18, +0.26] | +0.041 [+0.03, +0.06] | -0.087 [-0.12, -0.06] | +0.002 [+0.00, +0.00] | +0.165 [+0.12, +0.22] | -0.043 [-0.07, -0.02] | +0.090 [-0.17, +0.35] | +0.123 [-0.13, +0.36] | -0.285 [-0.40, -0.17] | -0.296 [-0.39, -0.20] | +0.131 [+0.09, +0.17] | +0.267 [+0.21, +0.33] |
| rocket_tornado | rocket_clump (n 299) | -0.259 [-0.30, -0.22] | -0.135 [-0.15, -0.11] | -0.192 [-0.22, -0.16] | +0.167 [+0.13, +0.20] | +0.029 [+0.02, +0.04] | -0.124 [-0.15, -0.10] | +0.008 [+0.01, +0.01] | +0.098 [+0.06, +0.13] | -0.044 [-0.07, -0.02] | -0.025 [-0.24, +0.19] | +0.099 [-0.13, +0.31] | -0.423 [-0.54, -0.30] | -0.238 [-0.35, -0.13] | +0.084 [+0.05, +0.12] | +0.063 [+0.02, +0.10] |
| rocket_tornado | wait (n 146) | +0.040 [-0.00, +0.09] | +0.021 [+0.00, +0.04] | +0.013 [-0.02, +0.05] | +0.012 [-0.02, +0.04] | -0.000 [-0.00, +0.00] | +0.008 [-0.03, +0.04] | -0.000 [-0.00, +0.00] | -0.009 [-0.04, +0.02] | +0.009 [-0.03, +0.04] | +0.103 [-0.17, +0.38] | -0.153 [-0.43, +0.12] | -0.030 [-0.15, +0.09] | +0.052 [-0.04, +0.15] | -0.026 [-0.06, +0.01] | +0.000 [-0.03, +0.03] |
| siege | front (n 192) | -0.018 [-0.06, +0.03] | -0.017 [-0.04, +0.00] | -0.013 [-0.04, +0.01] | -0.006 [-0.03, +0.03] | +0.010 [+0.00, +0.02] | -0.037 [-0.07, -0.01] | +0.001 [+0.00, +0.00] | +0.032 [-0.02, +0.09] | -0.020 [-0.06, +0.01] | -0.063 [-0.31, +0.20] | -0.200 [-0.43, +0.02] | +0.058 [-0.08, +0.19] | +0.091 [-0.02, +0.19] | +0.023 [-0.01, +0.07] | -0.015 [-0.05, +0.02] |
| siege | rocket_on (n 78) | -0.206 [-0.28, -0.14] | -0.075 [-0.10, -0.05] | -0.122 [-0.17, -0.08] | +0.066 [+0.00, +0.13] | +0.004 [-0.00, +0.01] | -0.128 [-0.16, -0.09] | -0.000 [-0.00, +0.00] | +0.068 [+0.02, +0.12] | -0.041 [-0.08, -0.01] | -0.048 [-0.44, +0.32] | -0.327 [-0.66, -0.00] | -0.397 [-0.58, -0.21] | +0.014 [-0.12, +0.17] | +0.055 [+0.00, +0.11] | -0.034 [-0.07, +0.00] |
| siege | troop_on (n 136) | -0.029 [-0.08, +0.02] | -0.011 [-0.03, +0.01] | -0.025 [-0.06, +0.01] | -0.024 [-0.06, +0.01] | +0.004 [-0.00, +0.01] | -0.038 [-0.06, -0.01] | -0.001 [-0.00, +0.00] | +0.004 [-0.04, +0.05] | -0.036 [-0.07, -0.00] | -0.235 [-0.54, +0.06] | +0.042 [-0.22, +0.30] | +0.187 [+0.06, +0.31] | +0.071 [-0.05, +0.20] | +0.012 [-0.04, +0.06] | -0.032 [-0.07, +0.00] |
| siege | wait (n 51) | -0.024 [-0.09, +0.04] | -0.009 [-0.03, +0.01] | -0.023 [-0.07, +0.02] | -0.013 [-0.06, +0.03] | -0.002 [-0.01, +0.00] | -0.005 [-0.03, +0.02] | +0.000 [+0.00, +0.00] | +0.000 [-0.04, +0.04] | -0.043 [-0.09, -0.01] | +0.007 [-0.47, +0.44] | -0.239 [-0.69, +0.18] | -0.152 [-0.35, +0.07] | +0.130 [-0.05, +0.34] | +0.000 [-0.04, +0.04] | -0.043 [-0.09, -0.01] |
| tornado_redirect | tornado_king (n 252) | -0.160 [-0.20, -0.12] | -0.070 [-0.09, -0.05] | -0.087 [-0.11, -0.06] | +0.074 [+0.05, +0.10] | +0.007 [+0.00, +0.01] | -0.071 [-0.10, -0.05] | -0.000 [-0.00, +0.00] | +0.027 [-0.00, +0.06] | -0.037 [-0.06, -0.01] | -0.091 [-0.31, +0.14] | +0.051 [-0.16, +0.26] | +0.201 [+0.10, +0.30] | -0.007 [-0.11, +0.09] | +0.037 [+0.01, +0.07] | -0.034 [-0.06, -0.01] |
| tornado_redirect | tornado_on (n 252) | -0.111 [-0.15, -0.07] | -0.066 [-0.09, -0.05] | -0.072 [-0.10, -0.05] | +0.060 [+0.03, +0.09] | +0.006 [+0.00, +0.01] | -0.070 [-0.10, -0.05] | +0.000 [-0.00, +0.00] | +0.026 [+0.00, +0.05] | -0.038 [-0.06, -0.02] | -0.244 [-0.46, -0.02] | +0.016 [-0.20, +0.22] | +0.168 [+0.07, +0.26] | +0.014 [-0.08, +0.11] | +0.036 [+0.01, +0.07] | -0.036 [-0.06, -0.01] |
| tornado_redirect | wait (n 45) | +0.005 [-0.04, +0.05] | +0.008 [-0.02, +0.04] | +0.022 [-0.03, +0.07] | -0.013 [-0.07, +0.04] | -0.000 [-0.01, +0.01] | +0.024 [-0.03, +0.07] | +0.000 [+0.00, +0.00] | -0.016 [-0.05, +0.00] | -0.078 [-0.14, -0.02] | +0.107 [-0.49, +0.70] | +0.243 [-0.27, +0.76] | -0.047 [-0.31, +0.22] | +0.047 [-0.25, +0.31] | +0.031 [+0.00, +0.09] | -0.078 [-0.14, -0.02] |
| wincon | cheap_on (n 37) | -0.050 [-0.12, +0.02] | -0.039 [-0.10, +0.01] | -0.076 [-0.15, +0.00] | +0.006 [-0.07, +0.09] | -0.011 [-0.03, +0.01] | -0.026 [-0.11, +0.06] | -0.001 [-0.00, +0.00] | +0.058 [+0.00, +0.13] | -0.058 [-0.13, +0.00] | +0.187 [-0.54, +0.87] | -0.210 [-0.81, +0.37] | +0.250 [+0.00, +0.52] | +0.173 [-0.19, +0.58] | +0.019 [-0.08, +0.12] | -0.058 [-0.13, +0.00] |
| wincon | rocket_on (n 72) | -0.203 [-0.28, -0.13] | -0.091 [-0.13, -0.06] | -0.136 [-0.20, -0.07] | +0.084 [+0.04, +0.14] | +0.024 [+0.01, +0.05] | -0.118 [-0.17, -0.07] | +0.000 [-0.00, +0.00] | +0.061 [+0.01, +0.12] | -0.061 [-0.11, -0.02] | +0.381 [-0.21, +0.98] | +0.554 [+0.15, +0.96] | -0.520 [-0.75, -0.29] | -0.531 [-0.79, -0.29] | +0.061 [+0.02, +0.11] | -0.051 [-0.10, -0.01] |
| wincon | troop_on (n 235) | -0.037 [-0.07, +0.00] | -0.027 [-0.05, -0.01] | -0.011 [-0.04, +0.02] | +0.001 [-0.02, +0.03] | -0.006 [-0.01, +0.00] | -0.040 [-0.07, -0.01] | +0.002 [-0.00, +0.01] | +0.027 [+0.01, +0.05] | -0.030 [-0.05, -0.01] | -0.044 [-0.29, +0.21] | +0.102 [-0.13, +0.32] | +0.079 [-0.04, +0.20] | -0.085 [-0.21, +0.03] | +0.009 [-0.02, +0.03] | -0.030 [-0.05, -0.01] |
| wincon | wait (n 55) | -0.014 [-0.09, +0.06] | +0.016 [-0.02, +0.06] | +0.002 [-0.05, +0.06] | -0.012 [-0.06, +0.03] | -0.028 [-0.08, +0.02] | +0.028 [-0.01, +0.07] | -0.003 [-0.01, -0.00] | -0.028 [-0.11, +0.04] | -0.042 [-0.09, +0.00] | -0.388 [-0.86, +0.12] | -0.100 [-0.54, +0.33] | +0.028 [-0.19, +0.21] | -0.069 [-0.31, +0.18] | -0.014 [-0.10, +0.06] | -0.028 [-0.07, +0.01] |
| xbow | wait (n 296) | +0.006 [-0.02, +0.03] | +0.008 [-0.01, +0.03] | +0.011 [-0.01, +0.03] | -0.022 [-0.05, +0.00] | -0.001 [-0.01, +0.01] | -0.007 [-0.04, +0.02] | +0.001 [+0.00, +0.00] | -0.007 [-0.03, +0.01] | -0.012 [-0.04, +0.01] | -0.056 [-0.31, +0.20] | +0.039 [-0.16, +0.23] | +0.070 [-0.04, +0.18] | -0.017 [-0.12, +0.08] | +0.007 [-0.02, +0.04] | +0.002 [-0.02, +0.03] |
| xbow | xbow_defensive (n 296) | -0.147 [-0.18, -0.11] | -0.069 [-0.09, -0.05] | -0.053 [-0.08, -0.03] | -0.081 [-0.11, -0.06] | -0.008 [-0.01, -0.00] | -0.233 [-0.27, -0.20] | +0.002 [-0.00, +0.00] | -0.023 [-0.04, -0.00] | -0.065 [-0.09, -0.04] | +0.149 [-0.08, +0.38] | +0.048 [-0.14, +0.25] | -0.148 [-0.24, -0.05] | -0.113 [-0.21, -0.01] | -0.039 [-0.07, -0.01] | -0.056 [-0.08, -0.03] |
| xbow | xbow_other_lane (n 296) | -0.066 [-0.10, -0.03] | -0.029 [-0.05, -0.01] | -0.043 [-0.07, -0.02] | +0.005 [-0.03, +0.04] | +0.003 [-0.00, +0.01] | -0.065 [-0.10, -0.03] | +0.000 [-0.00, +0.00] | +0.026 [+0.00, +0.06] | -0.007 [-0.04, +0.03] | -0.184 [-0.44, +0.08] | -0.026 [-0.24, +0.18] | +0.100 [+0.01, +0.19] | +0.014 [-0.09, +0.11] | +0.031 [+0.00, +0.06] | +0.002 [-0.03, +0.04] |
| xbow_after_fail | rocket_princess (n 200) | -0.157 [-0.21, -0.10] | -0.097 [-0.13, -0.07] | -0.149 [-0.19, -0.11] | +0.119 [+0.08, +0.16] | +0.019 [+0.01, +0.03] | -0.064 [-0.10, -0.03] | -0.001 [-0.00, +0.00] | +0.055 [+0.02, +0.10] | -0.020 [-0.04, -0.00] | -0.033 [-0.32, +0.24] | +0.220 [-0.03, +0.48] | -0.359 [-0.48, -0.24] | -0.395 [-0.55, -0.23] | +0.027 [-0.00, +0.06] | -0.020 [-0.04, -0.00] |
| xbow_after_fail | wait (n 51) | -0.051 [-0.14, +0.03] | +0.022 [-0.03, +0.07] | +0.065 [-0.00, +0.14] | -0.015 [-0.07, +0.04] | +0.005 [-0.00, +0.01] | +0.061 [-0.04, +0.16] | +0.000 [+0.00, +0.00] | +0.000 [-0.09, +0.08] | +0.104 [+0.04, +0.17] | +0.032 [-0.72, +0.81] | +0.016 [-0.70, +0.77] | +0.312 [+0.00, +0.62] | -0.104 [-0.38, +0.17] | +0.021 [-0.08, +0.10] | +0.104 [+0.04, +0.17] |
| xbow_after_fail | xbow_defensive (n 206) | -0.068 [-0.12, -0.02] | -0.050 [-0.08, -0.03] | -0.058 [-0.09, -0.02] | -0.003 [-0.03, +0.02] | +0.003 [-0.00, +0.01] | -0.095 [-0.14, -0.06] | -0.001 [-0.00, +0.00] | +0.031 [+0.00, +0.07] | -0.023 [-0.05, -0.00] | +0.315 [+0.03, +0.62] | +0.386 [+0.11, +0.68] | -0.291 [-0.42, -0.17] | -0.221 [-0.38, -0.07] | +0.012 [-0.03, +0.05] | -0.016 [-0.04, +0.01] |
| xbow_after_fail | xbow_reach (n 157) | -0.028 [-0.08, +0.02] | -0.002 [-0.03, +0.02] | -0.058 [-0.10, -0.02] | +0.009 [-0.02, +0.04] | +0.008 [+0.00, +0.02] | -0.005 [-0.04, +0.03] | -0.002 [-0.00, +0.00] | +0.024 [-0.01, +0.06] | -0.005 [-0.03, +0.02] | +0.117 [-0.20, +0.43] | +0.302 [-0.01, +0.61] | -0.231 [-0.36, -0.10] | -0.061 [-0.25, +0.12] | +0.000 [-0.05, +0.04] | -0.005 [-0.03, +0.02] |

### Contrasts between two alternatives (a - b), same columns

| trigger | alternative | dQ | dPhi | dCritic | d own princess lost | d own king lost | d FOE princess lost | d foe king lost | d own crowns lost | d foe crowns lost | d own elixir | d foe elixir | d own plays | d FOE plays | d own king on | d foe king on |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_clump - rocket_princess (n 147) | +0.050 [+0.01, +0.09] | +0.001 [-0.02, +0.02] | +0.043 [+0.01, +0.07] | -0.073 [-0.11, -0.04] | -0.020 [-0.04, -0.00] | -0.050 [-0.07, -0.03] | +0.005 [+0.00, +0.01] | -0.083 [-0.13, -0.04] | -0.023 [-0.05, -0.00] | -0.079 [-0.32, +0.17] | -0.052 [-0.33, +0.23] | -0.050 [-0.16, +0.06] | +0.069 [-0.03, +0.16] | -0.083 [-0.12, -0.04] | +0.050 [+0.00, +0.10] |
| rocket_played | second_card - wait (n 159) | -0.034 [-0.08, +0.01] | -0.012 [-0.04, +0.02] | -0.012 [-0.05, +0.03] | -0.002 [-0.04, +0.04] | +0.000 [-0.01, +0.01] | -0.045 [-0.08, -0.01] | +0.000 [-0.00, +0.00] | -0.005 [-0.04, +0.03] | +0.019 [-0.00, +0.05] | -0.022 [-0.37, +0.33] | +0.508 [+0.18, +0.85] | +0.660 [+0.48, +0.84] | +0.019 [-0.14, +0.18] | -0.005 [-0.05, +0.04] | +0.019 [-0.01, +0.05] |
| rocket_tornado | combo - rocket_clump (n 299) | -0.055 [-0.09, -0.02] | -0.033 [-0.05, -0.01] | -0.022 [-0.05, +0.01] | +0.054 [+0.02, +0.09] | +0.008 [-0.01, +0.03] | +0.041 [+0.02, +0.06] | -0.007 [-0.01, -0.00] | +0.069 [+0.02, +0.12] | +0.002 [-0.01, +0.01] | +0.152 [-0.08, +0.39] | +0.106 [-0.12, +0.34] | +0.107 [-0.01, +0.21] | -0.083 [-0.18, +0.01] | +0.050 [+0.00, +0.10] | +0.209 [+0.14, +0.27] |
| rocket_tornado | combo - wait (n 146) | -0.367 [-0.44, -0.30] | -0.203 [-0.24, -0.17] | -0.247 [-0.29, -0.20] | +0.238 [+0.18, +0.30] | +0.044 [+0.02, +0.07] | -0.118 [-0.16, -0.08] | +0.001 [-0.00, +0.00] | +0.196 [+0.12, +0.28] | -0.089 [-0.13, -0.05] | -0.047 [-0.45, +0.34] | +0.145 [-0.20, +0.51] | -0.339 [-0.50, -0.18] | -0.433 [-0.56, -0.30] | +0.138 [+0.08, +0.20] | +0.210 [+0.12, +0.29] |
| rocket_tornado | rocket_clump - wait (n 146) | -0.310 [-0.38, -0.24] | -0.153 [-0.18, -0.12] | -0.224 [-0.26, -0.18] | +0.164 [+0.11, +0.21] | +0.028 [+0.01, +0.04] | -0.158 [-0.21, -0.12] | +0.010 [+0.01, +0.01] | +0.089 [+0.04, +0.14] | -0.080 [-0.12, -0.05] | -0.250 [-0.61, +0.11] | -0.010 [-0.35, +0.32] | -0.406 [-0.58, -0.25] | -0.250 [-0.40, -0.12] | +0.076 [+0.03, +0.12] | +0.054 [-0.01, +0.12] |
| siege | front - rocket_on (n 73) | +0.168 [+0.11, +0.23] | +0.052 [+0.03, +0.08] | +0.120 [+0.08, +0.16] | -0.026 [-0.09, +0.03] | +0.000 [-0.01, +0.02] | +0.100 [+0.07, +0.13] | +0.002 [+0.00, +0.01] | -0.014 [-0.08, +0.05] | +0.058 [+0.02, +0.10] | -0.095 [-0.45, +0.27] | -0.016 [-0.28, +0.25] | +0.370 [+0.15, +0.59] | +0.123 [-0.04, +0.29] | -0.007 [-0.06, +0.04] | +0.058 [+0.02, +0.10] |
| siege | front - troop_on (n 129) | +0.021 [-0.02, +0.06] | -0.011 [-0.03, +0.01] | +0.015 [-0.01, +0.04] | +0.005 [-0.02, +0.03] | +0.005 [-0.00, +0.01] | -0.004 [-0.02, +0.01] | +0.003 [+0.00, +0.01] | +0.038 [+0.00, +0.08] | +0.000 [-0.03, +0.03] | +0.058 [-0.21, +0.31] | -0.019 [-0.25, +0.22] | -0.090 [-0.19, +0.01] | -0.043 [-0.15, +0.06] | +0.030 [+0.00, +0.06] | +0.004 [-0.02, +0.03] |
| siege | front - wait (n 35) | -0.059 [-0.14, +0.02] | -0.045 [-0.08, -0.01] | -0.026 [-0.08, +0.03] | +0.070 [+0.01, +0.13] | +0.002 [+0.00, +0.00] | -0.043 [-0.09, +0.01] | +0.000 [+0.00, +0.00] | +0.045 [-0.02, +0.11] | +0.045 [-0.02, +0.11] | +0.038 [-0.56, +0.62] | -0.029 [-0.49, +0.46] | -0.030 [-0.23, +0.17] | +0.045 [-0.16, +0.23] | +0.061 [+0.00, +0.12] | +0.045 [-0.02, +0.11] |
| siege | rocket_on - troop_on (n 50) | -0.167 [-0.25, -0.09] | -0.081 [-0.12, -0.04] | -0.088 [-0.14, -0.04] | +0.096 [+0.02, +0.17] | +0.007 [-0.00, +0.02] | -0.097 [-0.13, -0.06] | +0.001 [+0.00, +0.00] | +0.083 [+0.02, +0.14] | -0.021 [-0.08, +0.04] | +0.297 [-0.18, +0.77] | -0.009 [-0.38, +0.38] | -0.417 [-0.69, -0.13] | -0.125 [-0.30, +0.06] | +0.073 [+0.03, +0.12] | -0.010 [-0.07, +0.05] |
| siege | rocket_on - wait (n 21) | -0.136 [-0.28, -0.01] | -0.039 [-0.08, +0.00] | -0.067 [-0.17, +0.03] | +0.001 [-0.08, +0.09] | +0.001 [-0.00, +0.00] | -0.081 [-0.14, -0.01] | +0.000 [+0.00, +0.00] | +0.000 [-0.05, +0.05] | -0.025 [-0.07, +0.00] | -0.619 [-1.42, +0.20] | +0.259 [-0.20, +0.75] | -0.425 [-0.79, -0.08] | +0.075 [-0.16, +0.33] | +0.000 [-0.05, +0.05] | -0.025 [-0.07, +0.00] |
| tornado_redirect | tornado_king - tornado_on (n 252) | -0.048 [-0.08, -0.02] | -0.004 [-0.02, +0.01] | -0.018 [-0.04, +0.00] | +0.013 [-0.01, +0.03] | +0.001 [-0.00, +0.00] | -0.004 [-0.02, +0.01] | -0.000 [-0.00, +0.00] | +0.000 [-0.02, +0.02] | +0.002 [-0.01, +0.01] | +0.121 [-0.06, +0.29] | +0.024 [-0.14, +0.18] | +0.026 [-0.05, +0.11] | -0.017 [-0.10, +0.06] | +0.002 [-0.02, +0.03] | +0.002 [-0.01, +0.01] |
| tornado_redirect | tornado_king - wait (n 45) | -0.180 [-0.27, -0.10] | -0.096 [-0.14, -0.06] | -0.128 [-0.19, -0.07] | +0.152 [+0.10, +0.20] | -0.002 [-0.02, +0.01] | -0.032 [-0.08, +0.02] | +0.000 [+0.00, +0.00] | +0.097 [+0.02, +0.19] | +0.000 [-0.06, +0.06] | +0.415 [-0.18, +1.01] | +0.346 [-0.21, +0.93] | +0.161 [-0.08, +0.44] | -0.226 [-0.45, +0.02] | +0.097 [-0.02, +0.21] | +0.000 [-0.06, +0.06] |
| tornado_redirect | tornado_on - wait (n 45) | -0.153 [-0.24, -0.07] | -0.106 [-0.15, -0.06] | -0.110 [-0.18, -0.04] | +0.175 [+0.11, +0.24] | +0.011 [-0.01, +0.04] | -0.050 [-0.11, +0.01] | +0.000 [+0.00, +0.00] | +0.113 [+0.00, +0.23] | -0.016 [-0.10, +0.06] | -0.216 [-0.80, +0.37] | -0.035 [-0.68, +0.57] | +0.113 [-0.15, +0.35] | -0.032 [-0.29, +0.21] | +0.097 [-0.03, +0.23] | -0.016 [-0.10, +0.06] |
| wincon | cheap_on - troop_on (n 37) | +0.051 [-0.02, +0.13] | +0.014 [-0.02, +0.05] | -0.039 [-0.09, +0.02] | -0.012 [-0.07, +0.05] | +0.008 [-0.01, +0.02] | +0.005 [-0.06, +0.07] | +0.000 [+0.00, +0.00] | +0.056 [+0.00, +0.13] | +0.019 [+0.00, +0.06] | -0.259 [-1.00, +0.54] | -0.549 [-1.17, +0.11] | +0.444 [+0.13, +0.74] | +0.519 [+0.20, +0.85] | +0.056 [+0.00, +0.13] | +0.019 [+0.00, +0.06] |
| wincon | rocket_on - troop_on (n 72) | -0.119 [-0.18, -0.05] | -0.043 [-0.08, -0.01] | -0.109 [-0.17, -0.05] | +0.100 [+0.05, +0.15] | +0.016 [-0.00, +0.04] | -0.037 [-0.08, +0.00] | +0.001 [+0.00, +0.00] | +0.029 [-0.02, +0.09] | +0.020 [+0.00, +0.04] | +0.022 [-0.55, +0.59] | +0.115 [-0.23, +0.49] | -0.402 [-0.64, -0.17] | -0.147 [-0.36, +0.07] | +0.039 [-0.02, +0.10] | +0.020 [+0.00, +0.04] |
| wincon | troop_on - wait (n 42) | +0.011 [-0.06, +0.08] | -0.014 [-0.06, +0.03] | +0.026 [-0.05, +0.10] | +0.010 [-0.04, +0.07] | +0.009 [-0.03, +0.05] | -0.080 [-0.15, -0.02] | -0.006 [-0.02, +0.00] | +0.000 [-0.07, +0.07] | -0.018 [-0.07, +0.03] | +0.135 [-0.45, +0.77] | +0.360 [-0.18, +0.91] | +0.089 [-0.17, +0.33] | +0.107 [-0.19, +0.38] | -0.036 [-0.09, +0.02] | -0.018 [-0.07, +0.03] |
| xbow | wait - xbow_defensive (n 296) | +0.153 [+0.12, +0.19] | +0.085 [+0.06, +0.11] | +0.070 [+0.04, +0.10] | +0.053 [+0.03, +0.08] | +0.006 [+0.00, +0.01] | +0.229 [+0.19, +0.26] | -0.001 [-0.00, +0.00] | +0.009 [-0.01, +0.03] | +0.058 [+0.03, +0.09] | -0.172 [-0.41, +0.06] | -0.001 [-0.22, +0.20] | +0.221 [+0.12, +0.33] | +0.058 [-0.04, +0.15] | +0.037 [+0.01, +0.07] | +0.063 [+0.03, +0.09] |
| xbow | wait - xbow_other_lane (n 296) | +0.072 [+0.04, +0.11] | +0.035 [+0.02, +0.06] | +0.052 [+0.02, +0.08] | -0.024 [-0.06, +0.00] | -0.005 [-0.01, +0.00] | +0.055 [+0.02, +0.09] | +0.001 [-0.00, +0.00] | -0.029 [-0.06, -0.00] | -0.007 [-0.04, +0.03] | +0.145 [-0.12, +0.40] | +0.025 [-0.20, +0.25] | -0.067 [-0.17, +0.04] | -0.033 [-0.13, +0.07] | -0.017 [-0.05, +0.01] | -0.002 [-0.04, +0.03] |
| xbow | xbow_defensive - xbow_other_lane (n 296) | -0.081 [-0.11, -0.05] | -0.055 [-0.08, -0.04] | -0.024 [-0.05, +0.00] | -0.074 [-0.10, -0.05] | -0.010 [-0.02, -0.00] | -0.178 [-0.21, -0.15] | +0.001 [-0.00, +0.00] | -0.034 [-0.05, -0.02] | -0.067 [-0.10, -0.04] | +0.338 [+0.10, +0.57] | +0.022 [-0.16, +0.20] | -0.264 [-0.36, -0.17] | -0.122 [-0.21, -0.03] | -0.046 [-0.07, -0.02] | -0.067 [-0.10, -0.04] |
| xbow_after_fail | rocket_princess - wait (n 51) | -0.117 [-0.19, -0.05] | -0.112 [-0.17, -0.05] | -0.113 [-0.20, -0.02] | +0.085 [-0.01, +0.17] | +0.074 [+0.02, +0.14] | -0.135 [-0.25, -0.02] | +0.002 [+0.00, +0.01] | +0.025 [-0.05, +0.12] | -0.125 [-0.23, -0.03] | +0.024 [-0.86, +0.96] | +0.301 [-0.21, +0.86] | -0.450 [-0.70, -0.21] | -0.600 [-0.96, -0.23] | -0.025 [-0.10, +0.05] | -0.125 [-0.23, -0.03] |
| xbow_after_fail | rocket_princess - xbow_defensive (n 199) | -0.086 [-0.13, -0.04] | -0.044 [-0.06, -0.02] | -0.080 [-0.11, -0.05] | +0.115 [+0.08, +0.15] | +0.016 [+0.01, +0.03] | +0.044 [+0.02, +0.07] | +0.000 [-0.00, +0.00] | +0.035 [-0.00, +0.07] | -0.004 [-0.02, +0.02] | -0.303 [-0.58, -0.04] | -0.090 [-0.32, +0.14] | -0.047 [-0.16, +0.07] | -0.171 [-0.31, -0.03] | +0.019 [-0.02, +0.06] | -0.008 [-0.03, +0.01] |
| xbow_after_fail | rocket_princess - xbow_reach (n 150) | -0.128 [-0.18, -0.07] | -0.081 [-0.10, -0.06] | -0.085 [-0.12, -0.05] | +0.109 [+0.07, +0.15] | -0.000 [-0.00, +0.00] | -0.033 [-0.06, -0.01] | +0.000 [+0.00, +0.00] | +0.028 [-0.00, +0.06] | -0.014 [-0.03, +0.00] | -0.129 [-0.37, +0.11] | -0.171 [-0.43, +0.09] | -0.175 [-0.30, -0.05] | -0.198 [-0.35, -0.05] | +0.019 [-0.02, +0.06] | -0.014 [-0.03, +0.00] |
| xbow_after_fail | wait - xbow_defensive (n 50) | +0.069 [-0.03, +0.17] | +0.051 [+0.00, +0.10] | +0.046 [-0.00, +0.09] | +0.088 [+0.02, +0.16] | -0.008 [-0.04, +0.01] | +0.138 [+0.05, +0.23] | -0.002 [-0.01, +0.00] | +0.024 [+0.00, +0.07] | +0.143 [+0.05, +0.25] | +0.420 [-0.39, +1.27] | -0.640 [-1.33, +0.02] | +0.619 [+0.30, +0.93] | +0.571 [+0.32, +0.85] | +0.048 [+0.00, +0.10] | +0.143 [+0.05, +0.25] |
| xbow_after_fail | xbow_defensive - xbow_reach (n 156) | -0.027 [-0.06, +0.01] | -0.048 [-0.07, -0.02] | -0.021 [-0.05, +0.01] | +0.004 [-0.02, +0.03] | -0.007 [-0.01, -0.00] | -0.085 [-0.12, -0.05] | -0.000 [-0.00, +0.00] | +0.014 [-0.01, +0.04] | -0.019 [-0.04, +0.00] | +0.167 [-0.11, +0.46] | -0.110 [-0.36, +0.13] | -0.125 [-0.24, -0.02] | -0.106 [-0.26, +0.05] | +0.005 [-0.03, +0.04] | -0.019 [-0.04, +0.00] |

### Critic slope of the terminal return on the horizon return (audited samples; PLAN band [0.7, 1.3])

| trigger | levels slope (n) | within-sample diffs slope (n) |
|---|---|---|
| rocket | 0.86 +- 0.07 (212) | 0.56 +- 0.14 (121) |
| rocket_played | 0.84 +- 0.09 (132) | 0.58 +- 0.27 (80) |
| rocket_tornado | 0.83 +- 0.06 (296) | 0.52 +- 0.13 (191) |
| siege | 0.81 +- 0.05 (281) | 0.48 +- 0.15 (181) |
| tornado_redirect | 0.80 +- 0.06 (265) | 0.89 +- 0.17 (168) |
| wincon | 0.89 +- 0.10 (154) | 1.01 +- 0.20 (84) |
| xbow | 0.76 +- 0.05 (321) | 0.72 +- 0.14 (201) |
| xbow_after_fail | 0.84 +- 0.07 (235) | 0.69 +- 0.14 (155) |
| ALL | 0.81 +- 0.02 (1896) | 0.64 +- 0.05 (1181) |

