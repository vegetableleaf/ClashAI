# P4 audit tables: 745 samples from cfaud4.jsonl (updates >= 1)

samples per trigger: rocket 177, rocket_tornado 248, siege 95, wincon 225

### dQ at the main horizon: all / phase / score

| trigger | alternative | split | label | n | mean dQ | 90% CI |
|---|---|---|---|---|---|---|
| rocket | rocket_clump | all | all | 100 | -0.166 * | [-0.234, -0.100] |
| rocket | rocket_clump | phase | 1x | 54 | -0.249 * | [-0.329, -0.169] |
| rocket | rocket_clump | phase | 2x | 25 | -0.059 | [-0.223, +0.087] |
| rocket | rocket_clump | phase | OT | 21 | -0.082 | [-0.241, +0.076] |
| rocket | rocket_clump | score | ahead | 22 | -0.077 | [-0.236, +0.093] |
| rocket | rocket_clump | score | behind | 34 | -0.120 * | [-0.212, -0.036] |
| rocket | rocket_clump | score | even | 44 | -0.247 * | [-0.349, -0.136] |
| rocket | rocket_clump | tesla | tesla in hand | 41 | -0.162 * | [-0.282, -0.040] |
| rocket | rocket_clump | tesla | tesla not in hand | 59 | -0.169 * | [-0.253, -0.092] |
| rocket | rocket_princess | all | all | 177 | -0.230 * | [-0.281, -0.179] |
| rocket | rocket_princess | phase | 1x | 111 | -0.286 * | [-0.340, -0.235] |
| rocket | rocket_princess | phase | 2x | 36 | -0.198 * | [-0.339, -0.074] |
| rocket | rocket_princess | phase | OT | 30 | -0.062 | [-0.192, +0.072] |
| rocket | rocket_princess | score | ahead | 41 | -0.084 | [-0.192, +0.019] |
| rocket | rocket_princess | score | behind | 58 | -0.246 * | [-0.329, -0.172] |
| rocket | rocket_princess | score | even | 78 | -0.294 * | [-0.370, -0.221] |
| rocket | rocket_princess | tesla | tesla in hand | 79 | -0.213 * | [-0.293, -0.135] |
| rocket | rocket_princess | tesla | tesla not in hand | 98 | -0.243 * | [-0.310, -0.184] |
| rocket_tornado | combo | all | all | 248 | -0.325 * | [-0.379, -0.275] |
| rocket_tornado | combo | close_ot | close OT (even crowns, |hp margin| <= .25) | 17 | -0.236 | [-0.461, +0.000] |
| rocket_tornado | combo | phase | 1x | 90 | -0.497 * | [-0.581, -0.408] |
| rocket_tornado | combo | phase | 2x | 90 | -0.248 * | [-0.323, -0.177] |
| rocket_tornado | combo | phase | OT | 68 | -0.201 * | [-0.291, -0.112] |
| rocket_tornado | combo | score | ahead | 55 | -0.358 * | [-0.472, -0.244] |
| rocket_tornado | combo | score | behind | 67 | -0.176 * | [-0.264, -0.099] |
| rocket_tornado | combo | score | even | 126 | -0.391 * | [-0.466, -0.320] |
| rocket_tornado | combo | tesla | tesla in hand | 112 | -0.235 * | [-0.310, -0.165] |
| rocket_tornado | combo | tesla | tesla not in hand | 136 | -0.400 * | [-0.467, -0.333] |
| rocket_tornado | rocket_clump | all | all | 245 | -0.152 * | [-0.193, -0.112] |
| rocket_tornado | rocket_clump | close_ot | close OT (even crowns, |hp margin| <= .25) | 17 | -0.123 | [-0.298, +0.067] |
| rocket_tornado | rocket_clump | phase | 1x | 90 | -0.209 * | [-0.287, -0.131] |
| rocket_tornado | rocket_clump | phase | 2x | 88 | -0.121 * | [-0.191, -0.062] |
| rocket_tornado | rocket_clump | phase | OT | 67 | -0.114 * | [-0.184, -0.048] |
| rocket_tornado | rocket_clump | score | ahead | 52 | -0.229 * | [-0.331, -0.133] |
| rocket_tornado | rocket_clump | score | behind | 67 | -0.082 * | [-0.148, -0.025] |
| rocket_tornado | rocket_clump | score | even | 126 | -0.157 * | [-0.220, -0.097] |
| rocket_tornado | rocket_clump | tesla | tesla in hand | 111 | -0.099 * | [-0.163, -0.041] |
| rocket_tornado | rocket_clump | tesla | tesla not in hand | 134 | -0.196 * | [-0.246, -0.143] |
| rocket_tornado | wait | all | all | 133 | +0.003 | [-0.042, +0.044] |
| rocket_tornado | wait | phase | 1x | 43 | +0.039 | [-0.044, +0.120] |
| rocket_tornado | wait | phase | 2x | 49 | +0.002 | [-0.059, +0.063] |
| rocket_tornado | wait | phase | OT | 41 | -0.033 | [-0.110, +0.039] |
| rocket_tornado | wait | score | ahead | 34 | -0.007 | [-0.068, +0.056] |
| rocket_tornado | wait | score | behind | 37 | -0.078 | [-0.176, +0.007] |
| rocket_tornado | wait | score | even | 62 | +0.057 | [-0.007, +0.122] |
| rocket_tornado | wait | tesla | tesla in hand | 59 | +0.047 | [-0.019, +0.110] |
| rocket_tornado | wait | tesla | tesla not in hand | 74 | -0.031 | [-0.087, +0.023] |
| siege | front | all | all | 84 | -0.018 | [-0.077, +0.037] |
| siege | front | phase | 1x | 38 | +0.029 | [-0.035, +0.088] |
| siege | front | phase | 2x | 27 | -0.129 * | [-0.264, -0.006] |
| siege | front | phase | OT | 19 | +0.047 | [-0.022, +0.142] |
| siege | front | score | behind | 36 | -0.051 | [-0.152, +0.049] |
| siege | front | score | even | 37 | -0.015 | [-0.077, +0.040] |
| siege | front | tesla | tesla in hand | 27 | +0.025 | [-0.060, +0.096] |
| siege | front | tesla | tesla not in hand | 57 | -0.038 | [-0.110, +0.031] |
| siege | rocket_on | all | all | 36 | -0.259 * | [-0.389, -0.140] |
| siege | rocket_on | phase | 1x | 17 | -0.316 * | [-0.442, -0.202] |
| siege | rocket_on | score | behind | 16 | -0.231 * | [-0.450, -0.014] |
| siege | rocket_on | score | even | 17 | -0.290 * | [-0.420, -0.170] |
| siege | rocket_on | tesla | tesla not in hand | 22 | -0.278 * | [-0.420, -0.113] |
| siege | troop_on | all | all | 56 | -0.060 | [-0.146, +0.025] |
| siege | troop_on | phase | 1x | 24 | -0.040 | [-0.085, +0.009] |
| siege | troop_on | phase | 2x | 18 | -0.076 | [-0.241, +0.080] |
| siege | troop_on | score | behind | 26 | -0.017 | [-0.130, +0.087] |
| siege | troop_on | score | even | 23 | -0.034 | [-0.138, +0.082] |
| siege | troop_on | tesla | tesla in hand | 15 | -0.167 * | [-0.391, -0.029] |
| siege | troop_on | tesla | tesla not in hand | 41 | -0.020 | [-0.111, +0.072] |
| siege | wait | all | all | 26 | -0.109 * | [-0.169, -0.035] |
| siege | wait | tesla | tesla not in hand | 17 | -0.059 | [-0.126, +0.015] |
| wincon | cheap_on | all | all | 31 | -0.035 | [-0.140, +0.058] |
| wincon | cheap_on | tesla | tesla not in hand | 20 | +0.070 | [-0.023, +0.154] |
| wincon | rocket_on | all | all | 77 | -0.103 * | [-0.169, -0.042] |
| wincon | rocket_on | phase | 1x | 27 | -0.154 * | [-0.270, -0.037] |
| wincon | rocket_on | phase | 2x | 28 | -0.070 | [-0.182, +0.040] |
| wincon | rocket_on | phase | OT | 22 | -0.084 | [-0.197, +0.001] |
| wincon | rocket_on | score | ahead | 17 | -0.018 | [-0.162, +0.108] |
| wincon | rocket_on | score | behind | 36 | -0.076 * | [-0.157, -0.005] |
| wincon | rocket_on | score | even | 24 | -0.204 * | [-0.337, -0.080] |
| wincon | rocket_on | tesla | tesla in hand | 19 | -0.094 * | [-0.188, -0.008] |
| wincon | rocket_on | tesla | tesla not in hand | 58 | -0.106 * | [-0.183, -0.027] |
| wincon | troop_on | all | all | 216 | -0.028 | [-0.066, +0.012] |
| wincon | troop_on | close_ot | close OT (even crowns, |hp margin| <= .25) | 22 | +0.082 | [-0.048, +0.216] |
| wincon | troop_on | phase | 1x | 79 | -0.021 | [-0.084, +0.039] |
| wincon | troop_on | phase | 2x | 81 | -0.032 | [-0.093, +0.028] |
| wincon | troop_on | phase | OT | 56 | -0.029 | [-0.115, +0.053] |
| wincon | troop_on | score | ahead | 54 | -0.010 | [-0.086, +0.070] |
| wincon | troop_on | score | behind | 80 | -0.058 * | [-0.112, -0.004] |
| wincon | troop_on | score | even | 82 | -0.010 | [-0.074, +0.060] |
| wincon | troop_on | tesla | tesla in hand | 67 | -0.024 | [-0.079, +0.037] |
| wincon | troop_on | tesla | tesla not in hand | 149 | -0.029 | [-0.082, +0.018] |
| wincon | wait | all | all | 49 | -0.003 | [-0.063, +0.056] |
| wincon | wait | phase | 2x | 21 | -0.054 | [-0.150, +0.050] |
| wincon | wait | phase | OT | 17 | +0.067 | [-0.007, +0.162] |
| wincon | wait | score | ahead | 19 | +0.022 | [-0.061, +0.111] |
| wincon | wait | score | even | 17 | -0.074 | [-0.189, +0.040] |
| wincon | wait | tesla | tesla in hand | 19 | +0.007 | [-0.103, +0.115] |
| wincon | wait | tesla | tesla not in hand | 30 | -0.010 | [-0.082, +0.064] |

### dQ at the main horizon: trigger-specific splits

| trigger | alternative | split | label | n | mean dQ | 90% CI |
|---|---|---|---|---|---|---|
| rocket | rocket_clump | arch | other | 30 | -0.150 * | [-0.289, -0.008] |
| rocket | rocket_clump | arch | weak_other | 35 | -0.150 * | [-0.243, -0.066] |
| rocket | rocket_clump | denier | favourable / neutral | 65 | -0.150 * | [-0.233, -0.070] |
| rocket | rocket_clump | denier | unfavourable archetype (X-Bow denier) | 35 | -0.197 * | [-0.326, -0.077] |
| rocket | rocket_clump | elixir | elixir < 8 | 86 | -0.153 * | [-0.232, -0.077] |
| rocket | rocket_clump | opp | exploiter | 39 | -0.128 * | [-0.248, -0.002] |
| rocket | rocket_clump | opp | exploiter_league | 30 | -0.162 * | [-0.284, -0.045] |
| rocket | rocket_clump | opp | init | 31 | -0.219 * | [-0.326, -0.121] |
| rocket | rocket_clump | opp_bank | bank<2 | 52 | -0.179 * | [-0.268, -0.091] |
| rocket | rocket_clump | opp_bank | bank>=2 | 48 | -0.153 * | [-0.263, -0.051] |
| rocket | rocket_clump | policy | policy played | 17 | -0.067 | [-0.216, +0.092] |
| rocket | rocket_clump | policy | policy waited | 83 | -0.187 * | [-0.261, -0.110] |
| rocket | rocket_clump | safe_idle | safe & idle (no foe on our half, policy waited) | 56 | -0.219 * | [-0.318, -0.119] |
| rocket | rocket_clump | threat | foe on our half | 32 | -0.115 * | [-0.224, -0.009] |
| rocket | rocket_clump | threat | no foe body on our half | 68 | -0.191 * | [-0.274, -0.103] |
| rocket | rocket_clump | value_rocket_clump | 4-6 | 35 | -0.067 | [-0.179, +0.055] |
| rocket | rocket_clump | value_rocket_clump | <4 | 45 | -0.278 * | [-0.379, -0.182] |
| rocket | rocket_clump | xbow_hand | no xbow in hand | 32 | -0.131 * | [-0.261, -0.010] |
| rocket | rocket_clump | xbow_hand | xbow in hand | 68 | -0.183 * | [-0.266, -0.098] |
| rocket | rocket_princess | arch | golem | 19 | -0.100 | [-0.250, +0.096] |
| rocket | rocket_princess | arch | other | 56 | -0.186 * | [-0.277, -0.095] |
| rocket | rocket_princess | arch | weak_other | 55 | -0.283 * | [-0.368, -0.203] |
| rocket | rocket_princess | denier | favourable / neutral | 111 | -0.234 * | [-0.300, -0.174] |
| rocket | rocket_princess | denier | unfavourable archetype (X-Bow denier) | 66 | -0.223 * | [-0.305, -0.143] |
| rocket | rocket_princess | elixir | elixir < 8 | 146 | -0.230 * | [-0.287, -0.177] |
| rocket | rocket_princess | elixir | elixir >= 8 | 31 | -0.230 * | [-0.354, -0.109] |
| rocket | rocket_princess | opp | exploiter | 75 | -0.271 * | [-0.356, -0.189] |
| rocket | rocket_princess | opp | exploiter_league | 56 | -0.178 * | [-0.270, -0.090] |
| rocket | rocket_princess | opp | init | 46 | -0.226 * | [-0.294, -0.157] |
| rocket | rocket_princess | opp_bank | bank<2 | 87 | -0.242 * | [-0.318, -0.163] |
| rocket | rocket_princess | opp_bank | bank>=2 | 90 | -0.218 * | [-0.286, -0.156] |
| rocket | rocket_princess | policy | policy played | 21 | -0.110 | [-0.291, +0.075] |
| rocket | rocket_princess | policy | policy waited | 156 | -0.246 * | [-0.298, -0.195] |
| rocket | rocket_princess | safe_idle | safe & idle (no foe on our half, policy waited) | 119 | -0.266 * | [-0.327, -0.207] |
| rocket | rocket_princess | threat | foe on our half | 44 | -0.179 * | [-0.289, -0.074] |
| rocket | rocket_princess | threat | no foe body on our half | 133 | -0.247 * | [-0.302, -0.191] |
| rocket | rocket_princess | value_rocket_clump | 4-6 | 35 | -0.047 | [-0.149, +0.065] |
| rocket | rocket_princess | value_rocket_clump | <4 | 45 | -0.313 * | [-0.409, -0.214] |
| rocket | rocket_princess | xbow_hand | no xbow in hand | 66 | -0.194 * | [-0.271, -0.119] |
| rocket | rocket_princess | xbow_hand | xbow in hand | 111 | -0.251 * | [-0.319, -0.184] |
| rocket_tornado | combo | arch | golem | 47 | -0.341 * | [-0.481, -0.215] |
| rocket_tornado | combo | arch | other | 85 | -0.252 * | [-0.333, -0.176] |
| rocket_tornado | combo | arch | pekka_bridge | 22 | -0.610 * | [-0.754, -0.464] |
| rocket_tornado | combo | arch | weak_other | 63 | -0.301 * | [-0.395, -0.207] |
| rocket_tornado | combo | denier | favourable / neutral | 148 | -0.273 * | [-0.336, -0.211] |
| rocket_tornado | combo | denier | unfavourable archetype (X-Bow denier) | 100 | -0.403 * | [-0.492, -0.315] |
| rocket_tornado | combo | elixir | elixir < 8 | 92 | -0.312 * | [-0.395, -0.233] |
| rocket_tornado | combo | elixir | elixir >= 8 | 156 | -0.333 * | [-0.403, -0.268] |
| rocket_tornado | combo | opp | exploiter | 90 | -0.400 * | [-0.481, -0.321] |
| rocket_tornado | combo | opp | exploiter_league | 91 | -0.237 * | [-0.324, -0.153] |
| rocket_tornado | combo | opp | init | 67 | -0.345 * | [-0.456, -0.241] |
| rocket_tornado | combo | opp_bank | bank<2 | 124 | -0.383 * | [-0.467, -0.301] |
| rocket_tornado | combo | opp_bank | bank>=2 | 124 | -0.268 * | [-0.333, -0.208] |
| rocket_tornado | combo | policy | policy played | 133 | -0.304 * | [-0.378, -0.232] |
| rocket_tornado | combo | policy | policy waited | 115 | -0.350 * | [-0.414, -0.285] |
| rocket_tornado | combo | safe_idle | safe & idle (no foe on our half, policy waited) | 71 | -0.499 * | [-0.587, -0.412] |
| rocket_tornado | combo | threat | foe on our half | 98 | -0.162 * | [-0.236, -0.096] |
| rocket_tornado | combo | threat | no foe body on our half | 150 | -0.432 * | [-0.502, -0.366] |
| rocket_tornado | combo | value_combo | 6-8 | 147 | -0.343 * | [-0.410, -0.277] |
| rocket_tornado | combo | value_combo | 8+ | 101 | -0.299 * | [-0.380, -0.224] |
| rocket_tornado | combo | value_rocket_clump | 4-6 | 82 | -0.338 * | [-0.424, -0.262] |
| rocket_tornado | combo | value_rocket_clump | 6-8 | 100 | -0.269 * | [-0.344, -0.200] |
| rocket_tornado | combo | value_rocket_clump | 8+ | 42 | -0.370 * | [-0.528, -0.224] |
| rocket_tornado | combo | value_rocket_clump | <4 | 21 | -0.481 * | [-0.691, -0.282] |
| rocket_tornado | combo | xbow_hand | no xbow in hand | 106 | -0.367 * | [-0.440, -0.297] |
| rocket_tornado | combo | xbow_hand | xbow in hand | 142 | -0.294 * | [-0.365, -0.226] |
| rocket_tornado | rocket_clump | arch | golem | 46 | -0.212 * | [-0.359, -0.088] |
| rocket_tornado | rocket_clump | arch | other | 84 | -0.101 * | [-0.160, -0.045] |
| rocket_tornado | rocket_clump | arch | pekka_bridge | 22 | -0.265 * | [-0.384, -0.144] |
| rocket_tornado | rocket_clump | arch | weak_other | 62 | -0.087 * | [-0.166, -0.012] |
| rocket_tornado | rocket_clump | denier | favourable / neutral | 146 | -0.095 * | [-0.146, -0.049] |
| rocket_tornado | rocket_clump | denier | unfavourable archetype (X-Bow denier) | 99 | -0.235 * | [-0.313, -0.165] |
| rocket_tornado | rocket_clump | elixir | elixir < 8 | 91 | -0.170 * | [-0.233, -0.115] |
| rocket_tornado | rocket_clump | elixir | elixir >= 8 | 154 | -0.141 * | [-0.198, -0.084] |
| rocket_tornado | rocket_clump | opp | exploiter | 89 | -0.231 * | [-0.303, -0.163] |
| rocket_tornado | rocket_clump | opp | exploiter_league | 89 | -0.076 * | [-0.137, -0.016] |
| rocket_tornado | rocket_clump | opp | init | 67 | -0.148 * | [-0.230, -0.065] |
| rocket_tornado | rocket_clump | opp_bank | bank<2 | 122 | -0.179 * | [-0.240, -0.120] |
| rocket_tornado | rocket_clump | opp_bank | bank>=2 | 123 | -0.124 * | [-0.184, -0.070] |
| rocket_tornado | rocket_clump | policy | policy played | 130 | -0.144 * | [-0.199, -0.088] |
| rocket_tornado | rocket_clump | policy | policy waited | 115 | -0.161 * | [-0.220, -0.102] |
| rocket_tornado | rocket_clump | safe_idle | safe & idle (no foe on our half, policy waited) | 71 | -0.226 * | [-0.306, -0.152] |
| rocket_tornado | rocket_clump | threat | foe on our half | 96 | -0.064 * | [-0.114, -0.012] |
| rocket_tornado | rocket_clump | threat | no foe body on our half | 149 | -0.208 * | [-0.266, -0.151] |
| rocket_tornado | rocket_clump | value_combo | 6-8 | 146 | -0.143 * | [-0.195, -0.092] |
| rocket_tornado | rocket_clump | value_combo | 8+ | 99 | -0.165 * | [-0.233, -0.103] |
| rocket_tornado | rocket_clump | value_rocket_clump | 4-6 | 82 | -0.125 * | [-0.190, -0.065] |
| rocket_tornado | rocket_clump | value_rocket_clump | 6-8 | 100 | -0.094 * | [-0.151, -0.041] |
| rocket_tornado | rocket_clump | value_rocket_clump | 8+ | 42 | -0.296 * | [-0.427, -0.175] |
| rocket_tornado | rocket_clump | value_rocket_clump | <4 | 21 | -0.241 * | [-0.396, -0.086] |
| rocket_tornado | rocket_clump | xbow_hand | no xbow in hand | 104 | -0.150 * | [-0.224, -0.082] |
| rocket_tornado | rocket_clump | xbow_hand | xbow in hand | 141 | -0.153 * | [-0.206, -0.105] |
| rocket_tornado | wait | arch | golem | 22 | -0.038 | [-0.116, +0.035] |
| rocket_tornado | wait | arch | other | 45 | +0.059 | [-0.004, +0.126] |
| rocket_tornado | wait | arch | weak_other | 37 | +0.010 | [-0.086, +0.105] |
| rocket_tornado | wait | denier | favourable / neutral | 82 | +0.037 | [-0.015, +0.095] |
| rocket_tornado | wait | denier | unfavourable archetype (X-Bow denier) | 51 | -0.051 | [-0.121, +0.012] |
| rocket_tornado | wait | elixir | elixir < 8 | 41 | -0.044 | [-0.129, +0.033] |
| rocket_tornado | wait | elixir | elixir >= 8 | 92 | +0.024 | [-0.027, +0.077] |
| rocket_tornado | wait | opp | exploiter | 44 | -0.049 | [-0.122, +0.024] |
| rocket_tornado | wait | opp | exploiter_league | 51 | +0.076 * | [+0.013, +0.138] |
| rocket_tornado | wait | opp | init | 38 | -0.034 | [-0.117, +0.053] |
| rocket_tornado | wait | opp_bank | bank<2 | 66 | -0.002 | [-0.070, +0.060] |
| rocket_tornado | wait | opp_bank | bank>=2 | 67 | +0.008 | [-0.045, +0.069] |
| rocket_tornado | wait | policy | policy played | 133 | +0.003 | [-0.042, +0.044] |
| rocket_tornado | wait | threat | foe on our half | 54 | +0.027 | [-0.053, +0.102] |
| rocket_tornado | wait | threat | no foe body on our half | 79 | -0.013 | [-0.062, +0.036] |
| rocket_tornado | wait | value_combo | 6-8 | 68 | +0.007 | [-0.059, +0.075] |
| rocket_tornado | wait | value_combo | 8+ | 65 | -0.001 | [-0.055, +0.052] |
| rocket_tornado | wait | value_rocket_clump | 4-6 | 39 | -0.039 | [-0.125, +0.040] |
| rocket_tornado | wait | value_rocket_clump | 6-8 | 53 | +0.005 | [-0.060, +0.069] |
| rocket_tornado | wait | value_rocket_clump | 8+ | 28 | +0.048 | [-0.031, +0.139] |
| rocket_tornado | wait | xbow_hand | no xbow in hand | 54 | -0.001 | [-0.060, +0.056] |
| rocket_tornado | wait | xbow_hand | xbow in hand | 79 | +0.006 | [-0.050, +0.068] |
| siege | front | arch | weak_other | 76 | -0.028 | [-0.087, +0.029] |
| siege | front | denier | favourable / neutral | 82 | -0.020 | [-0.078, +0.031] |
| siege | front | elixir | elixir < 8 | 78 | -0.025 | [-0.082, +0.029] |
| siege | front | opp | exploiter | 60 | -0.008 | [-0.083, +0.060] |
| siege | front | opp_bank | bank<2 | 54 | -0.039 | [-0.124, +0.031] |
| siege | front | opp_bank | bank>=2 | 30 | +0.020 | [-0.042, +0.085] |
| siege | front | policy | policy played | 15 | -0.131 | [-0.331, +0.032] |
| siege | front | policy | policy waited | 69 | +0.007 | [-0.050, +0.056] |
| siege | front | safe_idle | safe & idle (no foe on our half, policy waited) | 33 | -0.000 | [-0.081, +0.072] |
| siege | front | target | other mortar | 52 | -0.026 | [-0.115, +0.052] |
| siege | front | target_class | other | 84 | -0.018 | [-0.077, +0.037] |
| siege | front | threat | foe on our half | 40 | -0.012 | [-0.081, +0.047] |
| siege | front | threat | no foe body on our half | 44 | -0.023 | [-0.094, +0.040] |
| siege | front | xbow_hand | no xbow in hand | 23 | -0.064 | [-0.173, +0.028] |
| siege | front | xbow_hand | xbow in hand | 61 | -0.000 | [-0.060, +0.057] |
| siege | rocket_on | arch | weak_other | 31 | -0.276 * | [-0.413, -0.137] |
| siege | rocket_on | denier | favourable / neutral | 34 | -0.273 * | [-0.404, -0.150] |
| siege | rocket_on | elixir | elixir < 8 | 29 | -0.232 * | [-0.368, -0.108] |
| siege | rocket_on | opp | exploiter | 22 | -0.154 | [-0.325, +0.009] |
| siege | rocket_on | opp_bank | bank<2 | 19 | -0.276 * | [-0.504, -0.079] |
| siege | rocket_on | opp_bank | bank>=2 | 17 | -0.240 * | [-0.361, -0.133] |
| siege | rocket_on | policy | policy waited | 29 | -0.200 * | [-0.307, -0.094] |
| siege | rocket_on | safe_idle | safe & idle (no foe on our half, policy waited) | 17 | -0.278 * | [-0.382, -0.185] |
| siege | rocket_on | target | other mortar | 19 | -0.159 | [-0.361, +0.019] |
| siege | rocket_on | target_class | other | 36 | -0.259 * | [-0.389, -0.140] |
| siege | rocket_on | threat | foe on our half | 16 | -0.174 * | [-0.342, -0.004] |
| siege | rocket_on | threat | no foe body on our half | 20 | -0.327 * | [-0.467, -0.203] |
| siege | rocket_on | xbow_hand | xbow in hand | 28 | -0.279 * | [-0.415, -0.133] |
| siege | troop_on | arch | weak_other | 51 | -0.055 | [-0.147, +0.037] |
| siege | troop_on | denier | favourable / neutral | 54 | -0.053 | [-0.142, +0.034] |
| siege | troop_on | elixir | elixir < 8 | 51 | -0.057 | [-0.148, +0.031] |
| siege | troop_on | opp | exploiter | 37 | -0.061 | [-0.150, +0.024] |
| siege | troop_on | opp_bank | bank<2 | 32 | -0.070 | [-0.161, +0.021] |
| siege | troop_on | opp_bank | bank>=2 | 24 | -0.045 | [-0.207, +0.103] |
| siege | troop_on | policy | policy waited | 47 | -0.016 | [-0.092, +0.064] |
| siege | troop_on | safe_idle | safe & idle (no foe on our half, policy waited) | 21 | -0.085 | [-0.193, +0.013] |
| siege | troop_on | target | other mortar | 32 | -0.057 | [-0.170, +0.041] |
| siege | troop_on | target_class | other | 56 | -0.060 | [-0.146, +0.025] |
| siege | troop_on | threat | foe on our half | 31 | -0.044 | [-0.197, +0.079] |
| siege | troop_on | threat | no foe body on our half | 25 | -0.079 | [-0.178, +0.004] |
| siege | troop_on | xbow_hand | xbow in hand | 43 | -0.025 | [-0.113, +0.058] |
| siege | wait | arch | weak_other | 21 | -0.125 * | [-0.198, -0.043] |
| siege | wait | denier | favourable / neutral | 26 | -0.109 * | [-0.169, -0.035] |
| siege | wait | elixir | elixir < 8 | 23 | -0.156 * | [-0.229, -0.076] |
| siege | wait | opp_bank | bank<2 | 18 | -0.148 * | [-0.215, -0.062] |
| siege | wait | policy | policy played | 26 | -0.109 * | [-0.169, -0.035] |
| siege | wait | target | other xbow | 16 | -0.110 | [-0.182, +0.007] |
| siege | wait | target_class | other | 26 | -0.109 * | [-0.169, -0.035] |
| siege | wait | threat | no foe body on our half | 17 | -0.067 | [-0.146, +0.006] |
| siege | wait | xbow_hand | xbow in hand | 16 | -0.060 | [-0.169, +0.066] |
| wincon | cheap_on | denier | favourable / neutral | 22 | -0.042 | [-0.150, +0.055] |
| wincon | cheap_on | elixir | elixir < 8 | 28 | -0.044 | [-0.156, +0.061] |
| wincon | cheap_on | opp_bank | bank>=2 | 17 | -0.096 | [-0.219, +0.010] |
| wincon | cheap_on | policy | policy waited | 26 | -0.025 | [-0.142, +0.083] |
| wincon | cheap_on | target_class | hoglike | 20 | -0.052 | [-0.194, +0.066] |
| wincon | cheap_on | threat | foe on our half | 31 | -0.035 | [-0.140, +0.058] |
| wincon | cheap_on | xbow_hand | xbow in hand | 26 | -0.053 | [-0.171, +0.059] |
| wincon | rocket_on | arch | other | 22 | -0.120 * | [-0.234, -0.008] |
| wincon | rocket_on | arch | weak_other | 27 | -0.156 * | [-0.253, -0.067] |
| wincon | rocket_on | denier | favourable / neutral | 49 | -0.140 * | [-0.211, -0.071] |
| wincon | rocket_on | denier | unfavourable archetype (X-Bow denier) | 28 | -0.039 | [-0.164, +0.077] |
| wincon | rocket_on | elixir | elixir < 8 | 68 | -0.101 * | [-0.165, -0.038] |
| wincon | rocket_on | opp | exploiter | 26 | -0.136 * | [-0.262, -0.017] |
| wincon | rocket_on | opp | exploiter_league | 29 | -0.101 * | [-0.187, -0.016] |
| wincon | rocket_on | opp | init | 22 | -0.068 | [-0.194, +0.041] |
| wincon | rocket_on | opp_bank | bank<2 | 38 | -0.112 * | [-0.221, -0.004] |
| wincon | rocket_on | opp_bank | bank>=2 | 39 | -0.095 * | [-0.163, -0.032] |
| wincon | rocket_on | policy | policy waited | 65 | -0.117 * | [-0.191, -0.044] |
| wincon | rocket_on | target | hoglike hogrider | 17 | -0.167 * | [-0.334, -0.009] |
| wincon | rocket_on | target_class | heavy | 30 | -0.064 | [-0.164, +0.029] |
| wincon | rocket_on | target_class | hoglike | 41 | -0.167 * | [-0.261, -0.080] |
| wincon | rocket_on | threat | foe on our half | 77 | -0.103 * | [-0.169, -0.042] |
| wincon | rocket_on | xbow_hand | xbow in hand | 69 | -0.092 * | [-0.161, -0.025] |
| wincon | troop_on | arch | golem | 38 | -0.065 | [-0.181, +0.058] |
| wincon | troop_on | arch | hyperbait | 15 | -0.059 | [-0.179, +0.066] |
| wincon | troop_on | arch | lava_hound | 24 | +0.033 | [-0.061, +0.136] |
| wincon | troop_on | arch | other | 64 | -0.017 | [-0.087, +0.048] |
| wincon | troop_on | arch | pekka_bridge | 17 | -0.116 | [-0.319, +0.086] |
| wincon | troop_on | arch | weak_other | 51 | +0.007 | [-0.046, +0.063] |
| wincon | troop_on | denier | favourable / neutral | 115 | -0.006 | [-0.051, +0.036] |
| wincon | troop_on | denier | unfavourable archetype (X-Bow denier) | 101 | -0.052 | [-0.119, +0.016] |
| wincon | troop_on | elixir | elixir < 8 | 206 | -0.022 | [-0.060, +0.017] |
| wincon | troop_on | opp | exploiter | 69 | -0.019 | [-0.081, +0.043] |
| wincon | troop_on | opp | exploiter_league | 75 | -0.022 | [-0.085, +0.041] |
| wincon | troop_on | opp | init | 72 | -0.042 | [-0.113, +0.031] |
| wincon | troop_on | opp_bank | bank<2 | 109 | -0.009 | [-0.069, +0.055] |
| wincon | troop_on | opp_bank | bank>=2 | 107 | -0.046 * | [-0.091, -0.001] |
| wincon | troop_on | policy | policy played | 40 | -0.034 | [-0.099, +0.025] |
| wincon | troop_on | policy | policy waited | 176 | -0.026 | [-0.073, +0.017] |
| wincon | troop_on | target | heavy elixirgolem | 26 | -0.115 | [-0.239, +0.002] |
| wincon | troop_on | target | heavy golem | 27 | -0.061 | [-0.163, +0.054] |
| wincon | troop_on | target | heavy lavahound | 19 | +0.009 | [-0.108, +0.128] |
| wincon | troop_on | target | hoglike battleram | 32 | -0.052 | [-0.178, +0.079] |
| wincon | troop_on | target | hoglike hogrider | 38 | +0.001 | [-0.108, +0.101] |
| wincon | troop_on | target | hoglike royalhogs | 15 | -0.010 | [-0.098, +0.085] |
| wincon | troop_on | target | other balloon | 22 | +0.030 | [-0.055, +0.108] |
| wincon | troop_on | target_class | heavy | 98 | -0.040 | [-0.096, +0.015] |
| wincon | troop_on | target_class | hoglike | 96 | -0.028 | [-0.089, +0.034] |
| wincon | troop_on | target_class | other | 22 | +0.030 | [-0.055, +0.108] |
| wincon | troop_on | threat | foe on our half | 216 | -0.028 | [-0.066, +0.012] |
| wincon | troop_on | xbow_hand | no xbow in hand | 51 | -0.100 * | [-0.163, -0.040] |
| wincon | troop_on | xbow_hand | xbow in hand | 165 | -0.005 | [-0.049, +0.038] |
| wincon | wait | denier | favourable / neutral | 25 | -0.074 * | [-0.149, -0.003] |
| wincon | wait | denier | unfavourable archetype (X-Bow denier) | 24 | +0.071 | [-0.016, +0.172] |
| wincon | wait | elixir | elixir < 8 | 45 | -0.014 | [-0.075, +0.053] |
| wincon | wait | opp | exploiter_league | 21 | -0.081 | [-0.159, +0.010] |
| wincon | wait | opp | init | 19 | +0.119 * | [+0.020, +0.224] |
| wincon | wait | opp_bank | bank<2 | 29 | -0.020 | [-0.107, +0.079] |
| wincon | wait | opp_bank | bank>=2 | 20 | +0.020 | [-0.046, +0.086] |
| wincon | wait | policy | policy played | 49 | -0.003 | [-0.063, +0.056] |
| wincon | wait | target_class | heavy | 23 | +0.040 | [-0.047, +0.135] |
| wincon | wait | target_class | hoglike | 21 | -0.041 | [-0.143, +0.052] |
| wincon | wait | threat | foe on our half | 49 | -0.003 | [-0.063, +0.056] |
| wincon | wait | xbow_hand | no xbow in hand | 17 | -0.051 | [-0.165, +0.076] |
| wincon | wait | xbow_hand | xbow in hand | 32 | +0.022 | [-0.043, +0.089] |

### Horizon profile: mean dQ (alt - chosen), same samples in every column (terminal = audited samples only)


| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_clump | yes | 33 | -0.165 [-0.30, -0.04] | -0.095 [-0.14, -0.05] | -0.141 [-0.19, -0.09] | -0.175 [-0.24, -0.11] | -0.192 [-0.29, -0.10] | -0.132 [-0.25, -0.01] | -0.516 [-0.75, -0.31] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_clump | no | 92 | -0.160 [-0.23, -0.09] | -0.081 [-0.10, -0.06] | -0.118 [-0.15, -0.09] | -0.154 [-0.19, -0.12] | -0.173 [-0.22, -0.13] | -0.145 [-0.21, -0.08] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_princess | yes | 65 | -0.312 [-0.38, -0.24] | -0.101 [-0.13, -0.08] | -0.189 [-0.23, -0.15] | -0.248 [-0.30, -0.20] | -0.288 [-0.35, -0.22] | -0.299 [-0.36, -0.23] | -0.401 [-0.61, -0.19] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket | rocket_princess | no | 165 | -0.247 [-0.30, -0.20] | -0.087 [-0.10, -0.07] | -0.151 [-0.18, -0.13] | -0.197 [-0.23, -0.16] | -0.231 [-0.27, -0.19] | -0.236 [-0.28, -0.19] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | combo | yes | 68 | -0.336 [-0.44, -0.24] | -0.220 [-0.26, -0.18] | -0.256 [-0.31, -0.20] | -0.288 [-0.36, -0.22] | -0.308 [-0.39, -0.23] | -0.344 [-0.44, -0.25] | -0.024 [-0.21, +0.16] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | combo | no | 215 | -0.348 [-0.41, -0.29] | -0.206 [-0.23, -0.18] | -0.252 [-0.28, -0.22] | -0.293 [-0.33, -0.26] | -0.318 [-0.36, -0.27] | -0.341 [-0.39, -0.29] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | rocket_clump | yes | 66 | -0.173 [-0.27, -0.09] | -0.116 [-0.15, -0.09] | -0.116 [-0.15, -0.08] | -0.144 [-0.19, -0.10] | -0.132 [-0.18, -0.08] | -0.136 [-0.21, -0.07] | +0.017 [-0.17, +0.20] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | rocket_clump | no | 213 | -0.169 [-0.22, -0.12] | -0.113 [-0.13, -0.09] | -0.136 [-0.16, -0.11] | -0.154 [-0.19, -0.13] | -0.154 [-0.19, -0.12] | -0.165 [-0.21, -0.13] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | wait | yes | 34 | +0.083 [-0.00, +0.18] | +0.003 [-0.02, +0.02] | -0.015 [-0.04, +0.01] | +0.023 [-0.03, +0.07] | +0.027 [-0.04, +0.10] | +0.062 [-0.01, +0.14] | +0.095 [-0.06, +0.26] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| rocket_tornado | wait | no | 113 | +0.004 [-0.04, +0.05] | -0.004 [-0.01, +0.01] | -0.006 [-0.02, +0.01] | -0.009 [-0.03, +0.02] | -0.005 [-0.04, +0.03] | -0.007 [-0.05, +0.03] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| siege | front | yes | 31 | -0.056 [-0.16, +0.04] | +0.006 [-0.02, +0.03] | +0.012 [-0.03, +0.05] | +0.030 [-0.03, +0.09] | -0.040 [-0.11, +0.03] | -0.031 [-0.13, +0.07] | +0.071 [-0.24, +0.38] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| siege | front | no | 80 | -0.019 [-0.08, +0.04] | -0.003 [-0.02, +0.02] | -0.018 [-0.05, +0.01] | +0.005 [-0.04, +0.04] | -0.008 [-0.05, +0.03] | -0.006 [-0.06, +0.05] |
| siege | rocket_on | no | 33 | -0.281 [-0.39, -0.18] | -0.136 [-0.17, -0.10] | -0.152 [-0.20, -0.11] | -0.173 [-0.24, -0.11] | -0.185 [-0.27, -0.11] | -0.236 [-0.32, -0.15] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| siege | troop_on | yes | 22 | +0.001 [-0.12, +0.13] | +0.023 [-0.00, +0.05] | +0.047 [-0.00, +0.09] | +0.056 [-0.01, +0.14] | -0.041 [-0.12, +0.05] | +0.001 [-0.10, +0.11] | -0.077 [-0.38, +0.20] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| siege | troop_on | no | 52 | -0.028 [-0.10, +0.05] | -0.006 [-0.03, +0.02] | -0.006 [-0.04, +0.02] | +0.011 [-0.04, +0.06] | -0.024 [-0.07, +0.02] | -0.009 [-0.07, +0.05] |
| siege | wait | no | 23 | -0.081 [-0.15, -0.02] | -0.047 [-0.07, -0.02] | -0.045 [-0.08, -0.00] | -0.038 [-0.07, -0.00] | -0.048 [-0.11, +0.01] | -0.082 [-0.14, -0.02] |
| wincon | cheap_on | no | 28 | -0.039 [-0.15, +0.06] | -0.055 [-0.11, -0.01] | -0.072 [-0.12, -0.03] | -0.068 [-0.15, -0.00] | -0.030 [-0.10, +0.03] | -0.005 [-0.08, +0.06] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| wincon | rocket_on | yes | 29 | -0.095 [-0.20, +0.01] | -0.067 [-0.10, -0.03] | -0.102 [-0.17, -0.04] | -0.093 [-0.19, -0.00] | -0.088 [-0.19, +0.01] | -0.090 [-0.19, +0.00] | -0.008 [-0.27, +0.26] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| wincon | rocket_on | no | 67 | -0.119 [-0.19, -0.05] | -0.061 [-0.09, -0.04] | -0.082 [-0.12, -0.05] | -0.089 [-0.14, -0.04] | -0.123 [-0.18, -0.07] | -0.106 [-0.17, -0.05] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| wincon | troop_on | yes | 84 | -0.028 [-0.09, +0.03] | -0.024 [-0.05, +0.00] | -0.040 [-0.07, -0.01] | -0.012 [-0.06, +0.03] | -0.039 [-0.09, +0.01] | -0.034 [-0.10, +0.02] | -0.051 [-0.21, +0.11] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| wincon | troop_on | no | 199 | -0.039 [-0.08, +0.00] | -0.013 [-0.03, -0.00] | -0.019 [-0.04, +0.00] | -0.010 [-0.04, +0.02] | -0.028 [-0.06, +0.00] | -0.037 [-0.07, +0.00] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 | qend |
|---|---|---|---|---|---|---|---|---|---|---|
| wincon | wait | yes | 16 | +0.066 [-0.06, +0.20] | -0.019 [-0.06, +0.03] | -0.019 [-0.10, +0.06] | +0.063 [-0.05, +0.18] | +0.067 [-0.06, +0.20] | +0.050 [-0.08, +0.18] | -0.132 [-0.47, +0.20] |

| trigger | alternative | audited | n | q | qh150 | qh300 | qh450 | qh600 | qh750 |
|---|---|---|---|---|---|---|---|---|---|
| wincon | wait | no | 45 | -0.003 [-0.07, +0.07] | -0.003 [-0.02, +0.02] | -0.029 [-0.07, +0.01] | +0.021 [-0.03, +0.08] | +0.046 [-0.01, +0.11] | +0.003 [-0.06, +0.07] |

