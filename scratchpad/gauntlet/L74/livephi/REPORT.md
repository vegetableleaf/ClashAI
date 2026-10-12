# LIVEPHI: REJECT

Status: offline experiment complete; changes uncommitted. No policy trained, network used, live script changed, or deployment performed.

## Dataset and method

Frozen candidate list: 1304 logs since 2026-10-08. Included 772 decisive main-account X-Bow matches, 268,175 decision rows. Exact `phase_stats.read_live` selection and final public tower-scorecard labels; this is a result proxy, not a separate authoritative result event. Draws and post-300-second drain decisions dropped. The supplied approximate count was not forced.

Exclusions: {'draw': 3, 'no_public_decisions': 34, 'no_end_event': 3, 'other_account_tower_signature': 490, 'no_xbow_in_own_hand': 2}.

| Split | Calendar dates | Matches | Wins | Rows | 1x | 2x | 3x | First 30 s |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| train | 20261008–20261010 | 553 | 293 | 185,578 | 110,212 | 68,078 | 7,288 | 22,095 |
| validation/calibration | 20261011–20261011 | 58 | 29 | 19,974 | 12,083 | 7,412 | 479 | 2,452 |
| held-out test | 20261012–20261012 | 161 | 77 | 62,623 | 36,017 | 24,103 | 2,503 | 7,309 |

Latest whole calendar-date block nearest 20% is test (20.9%); the same rule chooses calibration from earlier dates. Match clusters never cross splits. Labels, IDs, dates, policy actions and file names are absent from features.

Features: exact logged model-time public bodies/towers/elixir rebuilt with the live policy's `obs_contract.to_tokens`, the same scalar channels and token mask, then a fixed 35-dimensional board projection (25 scalars, five pooled body quantities per side). This small model intentionally omits card identity, hand, next card, action history and projectiles. It is not a replacement policy trunk. Opponent elixir is only the logged public counter estimate.

Model: 35→32 tanh→1 MLP, 1,185 learned parameters; single CPU thread, 30 epochs, validation-selected epoch 13, 26.65 s including calibration. Training uses inverse row-count match weights. Positive-slope Platt calibration fitted on validation only. `phi_live.pt` stores normalization and calibration; SHA256 `aaeaab1a399fd12e034e8e3623d7bb164325991a9e4592438ad727a564bb91e8`.

Baseline: `rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt`, SHA256 `41b52a8375483f7c3350b1837a3432f354e34304e87da8fa6fe508d7160fe6d8`. Its frozen value scalar is P(win)−P(loss); tower_crown uses the existing 0.3/0.3 weights. For Brier, each baseline gets its own positive-slope Platt fit on the same validation matches (separate maps for raw and smoothed scores); no test/pro labels enter calibration.

Baseline input limitation: logs do not contain a full input tensor. Model-time board and object arrays are exact; public opponent history uses every available public frame plus decision snapshots, with the live Hero deduplication step. Confirmed own actions rebuild past; own next card is padded unknown, and pending-hand/ability detail may differ. Frame events' EVAL_ONLY opponent elixir is discarded by an allowlist and a poison-field test. Therefore the frozen value-head comparison is on reconstructed public inputs, not a claim of bit-identical original full input tensors. L73 pro inputs are exact original rows and were checked against saved scalar/label arrays.

Reconstruction audit: `baseline_input_repair.json` verifies the history correction left all 219 validation/test matches' trained board features bit-identical. Only finalized input-revision-3 baseline predictions are accepted. `baseline_parity.json` verifies the value-only extraction equals the full checkpoint's `encode_gen` value output exactly on four persisted real rows.

Full-input fidelity diagnostic on matching-checkpoint test logs: 80 matches, 29,547 rows, |rebuilt gate−logged gate| median 0.0246, p95 0.1471. This also reflects differing live options; it is not Phi error.

Phases: 1x [0,120), 2x [120,240), 3x [240,300) seconds. Rows are decision-weighted; 95% percentile CIs use 500 paired bootstrap draws by match. Pro bootstraps resample replay IDs, carrying both perspectives together. All methods use exactly the same evaluated rows. AUC gain is positive; Brier improvement is negative.

## Held-out live AUC / Brier

### Raw

| Phase | Rows / matches | Method | AUC [95% CI] | Brier [95% CI] |
|---|---:|---|---|---|
| all | 62,623 / 161 | live_phi | 0.7673 [0.7144, 0.8151] | 0.2014 [0.1771, 0.2278] |
| all | 62,623 / 161 | value_phi | 0.7774 [0.7253, 0.8220] | 0.1944 [0.1729, 0.2185] |
| all | 62,623 / 161 | tower_crown | 0.7470 [0.6905, 0.8030] | 0.2067 [0.1824, 0.2309] |
| 1x | 36,017 / 161 | live_phi | 0.6888 [0.6366, 0.7414] | 0.2275 [0.2065, 0.2495] |
| 1x | 36,017 / 161 | value_phi | 0.7059 [0.6419, 0.7594] | 0.2216 [0.2000, 0.2458] |
| 1x | 36,017 / 161 | tower_crown | 0.6577 [0.5928, 0.7140] | 0.2356 [0.2146, 0.2591] |
| 2x | 24,103 / 153 | live_phi | 0.8541 [0.7967, 0.9077] | 0.1595 [0.1198, 0.1977] |
| 2x | 24,103 / 153 | value_phi | 0.8571 [0.8076, 0.9061] | 0.1538 [0.1236, 0.1840] |
| 2x | 24,103 / 153 | tower_crown | 0.8371 [0.7813, 0.8939] | 0.1655 [0.1316, 0.1998] |
| 3x | 2,503 / 30 | live_phi | 0.7285 [0.5409, 0.8952] | 0.2300 [0.1420, 0.3279] |
| 3x | 2,503 / 30 | value_phi | 0.7958 [0.6318, 0.9257] | 0.1949 [0.1202, 0.2834] |
| 3x | 2,503 / 30 | tower_crown | 0.7726 [0.5739, 0.9237] | 0.1887 [0.1247, 0.2599] |
| first30s | 7,309 / 161 | live_phi | 0.5232 [0.4665, 0.5761] | 0.2540 [0.2462, 0.2632] |
| first30s | 7,309 / 161 | value_phi | 0.5454 [0.4792, 0.6053] | 0.2550 [0.2407, 0.2701] |
| first30s | 7,309 / 161 | tower_crown | 0.5092 [0.4484, 0.5632] | 0.2648 [0.2519, 0.2789] |

| Phase | Paired difference | ΔAUC [95% CI] | ΔBrier [95% CI] |
|---|---|---|---|
| all | live_phi − value_phi | -0.0102 [-0.0424, 0.0222] | 0.0070 [-0.0101, 0.0237] |
| all | live_phi − tower_crown | 0.0203 [-0.0130, 0.0572] | -0.0053 [-0.0206, 0.0091] |
| 1x | live_phi − value_phi | -0.0170 [-0.0508, 0.0170] | 0.0059 [-0.0092, 0.0215] |
| 1x | live_phi − tower_crown | 0.0311 [-0.0154, 0.0779] | -0.0081 [-0.0233, 0.0064] |
| 2x | live_phi − value_phi | -0.0030 [-0.0388, 0.0315] | 0.0057 [-0.0185, 0.0302] |
| 2x | live_phi − tower_crown | 0.0170 [-0.0093, 0.0432] | -0.0060 [-0.0246, 0.0154] |
| 3x | live_phi − value_phi | -0.0674 [-0.2364, 0.0822] | 0.0351 [-0.0395, 0.1230] |
| 3x | live_phi − tower_crown | -0.0441 [-0.2316, 0.1326] | 0.0413 [-0.0359, 0.1305] |
| first30s | live_phi − value_phi | -0.0223 [-0.0964, 0.0555] | -0.0010 [-0.0160, 0.0133] |
| first30s | live_phi − tower_crown | 0.0140 [-0.0661, 0.1015] | -0.0108 [-0.0255, 0.0035] |

### Causal trailing 10-second mean

| Phase | Rows / matches | Method | AUC [95% CI] | Brier [95% CI] |
|---|---:|---|---|---|
| all | 62,623 / 161 | live_phi | 0.7631 [0.7066, 0.8144] | 0.2012 [0.1773, 0.2271] |
| all | 62,623 / 161 | value_phi | 0.7745 [0.7197, 0.8212] | 0.1957 [0.1733, 0.2209] |
| all | 62,623 / 161 | tower_crown | 0.7352 [0.6767, 0.7936] | 0.2113 [0.1868, 0.2359] |
| 1x | 36,017 / 161 | live_phi | 0.6851 [0.6307, 0.7408] | 0.2259 [0.2061, 0.2465] |
| 1x | 36,017 / 161 | value_phi | 0.7020 [0.6378, 0.7565] | 0.2227 [0.2005, 0.2465] |
| 1x | 36,017 / 161 | tower_crown | 0.6470 [0.5822, 0.7035] | 0.2382 [0.2179, 0.2610] |
| 2x | 24,103 / 153 | live_phi | 0.8474 [0.7847, 0.9043] | 0.1615 [0.1212, 0.2010] |
| 2x | 24,103 / 153 | value_phi | 0.8534 [0.7998, 0.9048] | 0.1559 [0.1243, 0.1880] |
| 2x | 24,103 / 153 | tower_crown | 0.8254 [0.7658, 0.8854] | 0.1723 [0.1371, 0.2080] |
| 3x | 2,503 / 30 | live_phi | 0.7300 [0.5267, 0.9010] | 0.2279 [0.1424, 0.3215] |
| 3x | 2,503 / 30 | value_phi | 0.7985 [0.6208, 0.9412] | 0.1910 [0.1163, 0.2804] |
| 3x | 2,503 / 30 | tower_crown | 0.7387 [0.5088, 0.9127] | 0.1989 [0.1310, 0.2790] |
| first30s | 7,309 / 161 | live_phi | 0.5184 [0.4519, 0.5837] | 0.2510 [0.2448, 0.2574] |
| first30s | 7,309 / 161 | value_phi | 0.5443 [0.4690, 0.6127] | 0.2510 [0.2378, 0.2648] |
| first30s | 7,309 / 161 | tower_crown | 0.5059 [0.4467, 0.5601] | 0.2606 [0.2506, 0.2725] |

| Phase | Paired difference | ΔAUC [95% CI] | ΔBrier [95% CI] |
|---|---|---|---|
| all | live_phi − value_phi | -0.0115 [-0.0456, 0.0239] | 0.0055 [-0.0128, 0.0225] |
| all | live_phi − tower_crown | 0.0279 [-0.0078, 0.0677] | -0.0101 [-0.0252, 0.0042] |
| 1x | live_phi − value_phi | -0.0169 [-0.0538, 0.0215] | 0.0032 [-0.0119, 0.0182] |
| 1x | live_phi − tower_crown | 0.0381 [-0.0112, 0.0878] | -0.0123 [-0.0271, 0.0018] |
| 2x | live_phi − value_phi | -0.0060 [-0.0440, 0.0299] | 0.0056 [-0.0193, 0.0306] |
| 2x | live_phi − tower_crown | 0.0220 [-0.0061, 0.0492] | -0.0108 [-0.0305, 0.0111] |
| 3x | live_phi − value_phi | -0.0686 [-0.2712, 0.0924] | 0.0369 [-0.0426, 0.1251] |
| 3x | live_phi − tower_crown | -0.0088 [-0.2169, 0.1775] | 0.0290 [-0.0484, 0.1157] |
| first30s | live_phi − value_phi | -0.0259 [-0.1189, 0.0704] | 0.0000 [-0.0128, 0.0131] |
| first30s | live_phi − tower_crown | 0.0125 [-0.0774, 0.1074] | -0.0096 [-0.0231, 0.0038] |

## L73 pro transfer AUC / Brier

### Raw

| Phase | Rows / matches | Method | AUC [95% CI] | Brier [95% CI] |
|---|---:|---|---|---|
| all | 45,431 / 187 | live_phi | 0.6614 [0.6208, 0.7016] | 0.2544 [0.2362, 0.2718] |
| all | 45,431 / 187 | value_phi | 0.7002 [0.6464, 0.7520] | 0.2245 [0.2028, 0.2467] |
| all | 45,431 / 187 | tower_crown | 0.6757 [0.6233, 0.7310] | 0.2271 [0.2101, 0.2437] |
| 1x | 24,356 / 187 | live_phi | 0.6073 [0.5675, 0.6449] | 0.2557 [0.2427, 0.2699] |
| 1x | 24,356 / 187 | value_phi | 0.6595 [0.6101, 0.7097] | 0.2353 [0.2177, 0.2531] |
| 1x | 24,356 / 187 | tower_crown | 0.6060 [0.5568, 0.6582] | 0.2414 [0.2292, 0.2548] |
| 2x | 17,695 / 177 | live_phi | 0.7221 [0.6649, 0.7704] | 0.2502 [0.2270, 0.2763] |
| 2x | 17,695 / 177 | value_phi | 0.7512 [0.6902, 0.8059] | 0.2068 [0.1810, 0.2357] |
| 2x | 17,695 / 177 | tower_crown | 0.7428 [0.6759, 0.7999] | 0.2101 [0.1878, 0.2349] |
| 3x | 3,380 / 63 | live_phi | 0.6714 [0.5680, 0.7663] | 0.2668 [0.2264, 0.3098] |
| 3x | 3,380 / 63 | value_phi | 0.6887 [0.5653, 0.8008] | 0.2396 [0.1835, 0.3031] |
| 3x | 3,380 / 63 | tower_crown | 0.7155 [0.5832, 0.8275] | 0.2121 [0.1750, 0.2512] |
| first30s | 6,232 / 187 | live_phi | 0.5069 [0.4727, 0.5401] | 0.2544 [0.2500, 0.2589] |
| first30s | 6,232 / 187 | value_phi | 0.5589 [0.5120, 0.6095] | 0.2574 [0.2442, 0.2704] |
| first30s | 6,232 / 187 | tower_crown | 0.4908 [0.4556, 0.5297] | 0.2570 [0.2541, 0.2601] |

| Phase | Paired difference | ΔAUC [95% CI] | ΔBrier [95% CI] |
|---|---|---|---|
| all | live_phi − value_phi | -0.0389 [-0.0788, 0.0004] | 0.0299 [0.0132, 0.0464] |
| all | live_phi − tower_crown | -0.0143 [-0.0417, 0.0126] | 0.0273 [0.0208, 0.0342] |
| 1x | live_phi − value_phi | -0.0522 [-0.0978, -0.0118] | 0.0205 [0.0070, 0.0354] |
| 1x | live_phi − tower_crown | 0.0013 [-0.0340, 0.0336] | 0.0143 [0.0092, 0.0193] |
| 2x | live_phi − value_phi | -0.0291 [-0.0684, 0.0141] | 0.0433 [0.0237, 0.0620] |
| 2x | live_phi − tower_crown | -0.0207 [-0.0474, 0.0094] | 0.0400 [0.0283, 0.0493] |
| 3x | live_phi − value_phi | -0.0174 [-0.1135, 0.0940] | 0.0272 [-0.0258, 0.0743] |
| 3x | live_phi − tower_crown | -0.0442 [-0.1057, 0.0251] | 0.0547 [0.0351, 0.0774] |
| first30s | live_phi − value_phi | -0.0521 [-0.1200, 0.0052] | -0.0030 [-0.0157, 0.0113] |
| first30s | live_phi − tower_crown | 0.0160 [-0.0278, 0.0541] | -0.0026 [-0.0067, 0.0016] |

### Causal trailing 10-second mean

| Phase | Rows / matches | Method | AUC [95% CI] | Brier [95% CI] |
|---|---:|---|---|---|
| all | 45,431 / 187 | live_phi | 0.6601 [0.6194, 0.7006] | 0.2512 [0.2341, 0.2679] |
| all | 45,431 / 187 | value_phi | 0.7023 [0.6465, 0.7570] | 0.2236 [0.2010, 0.2470] |
| all | 45,431 / 187 | tower_crown | 0.6715 [0.6183, 0.7276] | 0.2279 [0.2111, 0.2443] |
| 1x | 24,356 / 187 | live_phi | 0.6043 [0.5636, 0.6433] | 0.2522 [0.2401, 0.2655] |
| 1x | 24,356 / 187 | value_phi | 0.6578 [0.6080, 0.7103] | 0.2355 [0.2170, 0.2541] |
| 1x | 24,356 / 187 | tower_crown | 0.6009 [0.5527, 0.6546] | 0.2421 [0.2303, 0.2549] |
| 2x | 17,695 / 177 | live_phi | 0.7255 [0.6663, 0.7746] | 0.2470 [0.2251, 0.2721] |
| 2x | 17,695 / 177 | value_phi | 0.7559 [0.6928, 0.8128] | 0.2050 [0.1776, 0.2352] |
| 2x | 17,695 / 177 | tower_crown | 0.7398 [0.6718, 0.7990] | 0.2109 [0.1886, 0.2349] |
| 3x | 3,380 / 63 | live_phi | 0.6710 [0.5627, 0.7666] | 0.2662 [0.2246, 0.3091] |
| 3x | 3,380 / 63 | value_phi | 0.6947 [0.5656, 0.8131] | 0.2359 [0.1756, 0.3023] |
| 3x | 3,380 / 63 | tower_crown | 0.7096 [0.5810, 0.8244] | 0.2139 [0.1763, 0.2533] |
| first30s | 6,232 / 187 | live_phi | 0.5024 [0.4610, 0.5425] | 0.2513 [0.2482, 0.2544] |
| first30s | 6,232 / 187 | value_phi | 0.5483 [0.4964, 0.6058] | 0.2592 [0.2452, 0.2728] |
| first30s | 6,232 / 187 | tower_crown | 0.4947 [0.4585, 0.5329] | 0.2557 [0.2539, 0.2576] |

| Phase | Paired difference | ΔAUC [95% CI] | ΔBrier [95% CI] |
|---|---|---|---|
| all | live_phi − value_phi | -0.0422 [-0.0838, 0.0006] | 0.0276 [0.0103, 0.0446] |
| all | live_phi − tower_crown | -0.0114 [-0.0393, 0.0150] | 0.0234 [0.0169, 0.0300] |
| 1x | live_phi − value_phi | -0.0534 [-0.1028, -0.0093] | 0.0168 [0.0025, 0.0328] |
| 1x | live_phi − tower_crown | 0.0034 [-0.0321, 0.0372] | 0.0101 [0.0052, 0.0148] |
| 2x | live_phi − value_phi | -0.0304 [-0.0731, 0.0159] | 0.0420 [0.0214, 0.0611] |
| 2x | live_phi − tower_crown | -0.0143 [-0.0409, 0.0165] | 0.0361 [0.0240, 0.0449] |
| 3x | live_phi − value_phi | -0.0238 [-0.1244, 0.0925] | 0.0303 [-0.0275, 0.0800] |
| 3x | live_phi − tower_crown | -0.0386 [-0.1033, 0.0365] | 0.0523 [0.0305, 0.0740] |
| first30s | live_phi − value_phi | -0.0459 [-0.1198, 0.0166] | -0.0080 [-0.0212, 0.0058] |
| first30s | live_phi − tower_crown | 0.0077 [-0.0425, 0.0552] | -0.0045 [-0.0074, -0.0013] |

## Calibration and step jitter

Ten equal-width reliability bins, mean predicted probability, observed win rate, and ECE overall/per phase are retained in `results.json`.

| Cohort | Phase | live_phi ECE | value_phi ECE | tower_crown ECE |
|---|---|---:|---:|---:|
| live | all | 0.0727 | 0.0470 | 0.0557 |
| live | 1x | 0.0769 | 0.0705 | 0.0783 |
| live | 2x | 0.0629 | 0.0334 | 0.0692 |
| live | 3x | 0.1332 | 0.1046 | 0.1756 |
| live | first30s | 0.0539 | 0.0712 | 0.1073 |
| pro | all | 0.1449 | 0.0695 | 0.0674 |
| pro | 1x | 0.1081 | 0.0684 | 0.0705 |
| pro | 2x | 0.1869 | 0.0629 | 0.0668 |
| pro | 3x | 0.1977 | 0.1114 | 0.0784 |
| pro | first30s | 0.0433 | 0.0713 | 0.0749 |

Test Brier of the constant training row win-prior predictor: 0.2523. Calibration gate was predeclared as ECE ≤ .05 and Brier no worse than that constant predictor.

| Cohort | Potential | Std of consecutive ΔPhi | Match TV mean | Match TV median |
|---|---|---:|---:|---:|
| live | live_phi | 0.04437 | 7.6299 | 7.1465 |
| live | value_phi | 0.02438 | 5.7142 | 5.1777 |
| live | tower_crown | 0.00737 | 0.4089 | 0.3252 |
| live | live_phi_10s | 0.00776 | 1.9416 | 1.8720 |
| live | value_phi_10s | 0.00378 | 1.0928 | 1.0237 |
| live | tower_crown_10s | 0.00200 | 0.3324 | 0.2843 |
| pro | live_phi | 0.07706 | 5.7300 | 5.5439 |
| pro | value_phi | 0.03982 | 3.4072 | 3.1830 |
| pro | tower_crown | 0.00922 | 0.2532 | 0.2183 |
| pro | live_phi_10s | 0.02374 | 1.8931 | 1.8337 |
| pro | value_phi_10s | 0.01187 | 1.0595 | 1.0134 |
| pro | tower_crown_10s | 0.00471 | 0.2138 | 0.1766 |

Jitter uses default shaping units: live_phi=.5×(2P−1), value_phi=.5×value scalar, tower_crown=.3×tower+.3×crown. TV excludes the forced terminal reset; each trajectory's TV and delta std are retained in `results.json`. Pro sides are separate trajectories. Smoothing averages prior decision rows in [tick−200,tick], including current row, never future rows.

| Cohort | Paired jitter difference | Δstep std [95% CI] | Δmean TV [95% CI] |
|---|---|---|---|
| live | live_phi-value_phi | 0.0200 [0.0179, 0.0219] | 1.9157 [1.5056, 2.2876] |
| live | live_phi-tower_crown | 0.0370 [0.0347, 0.0392] | 7.2211 [6.6079, 7.8636] |
| live | live_phi_10s-value_phi_10s | 0.0040 [0.0036, 0.0043] | 0.8489 [0.7434, 0.9567] |
| live | live_phi_10s-tower_crown_10s | 0.0058 [0.0054, 0.0062] | 1.6093 [1.4654, 1.7453] |
| pro | live_phi-value_phi | 0.0372 [0.0348, 0.0397] | 2.3228 [2.0867, 2.5525] |
| pro | live_phi-tower_crown | 0.0678 [0.0654, 0.0703] | 5.4768 [5.1382, 5.8278] |
| pro | live_phi_10s-value_phi_10s | 0.0119 [0.0109, 0.0128] | 0.8336 [0.7628, 0.9078] |
| pro | live_phi_10s-tower_crown_10s | 0.0190 [0.0182, 0.0200] | 1.6793 [1.5811, 1.7760] |

## Exploitability diagnostics

Own-elixir partial dependence on every held-out row (all other encoded inputs fixed):

| Elixir | Mean P(win) |
|---:|---:|
| 0 | 0.38624 |
| 1 | 0.41731 |
| 2 | 0.44707 |
| 3 | 0.47453 |
| 4 | 0.49903 |
| 5 | 0.52029 |
| 6 | 0.53858 |
| 7 | 0.55467 |
| 8 | 0.56972 |
| 9 | 0.58500 |
| 10 | 0.60160 |

5→10 elixir ΔP(win): **0.0813 [0.0766, 0.0859]**; positive on 93.6% of rows. In default Phi units the difference is identical. Gate: upper CI ≤ .01; this is a sensitivity screen, not proof that a legal banking trajectory gains return. Potential shaping still telescopes.

own_tower_hp: fractions [0.05, 0.25, 0.5, 0.75, 1], mean P(win) [0.06751, 0.12927, 0.3084, 0.53779, 0.63579]; full-minus-5% 0.5683 [0.5416, 0.5986]. Alive/known flags fixed; only standing known towers varied. Diagnostic counterfactuals can be off-manifold.

enemy_tower_hp: fractions [0.05, 0.25, 0.5, 0.75, 1], mean P(win) [0.92819, 0.88624, 0.81376, 0.70505, 0.42958]; full-minus-5% -0.4986 [-0.5222, -0.4739]. Alive/known flags fixed; only standing known towers varied. Diagnostic counterfactuals can be off-manifold.

Own troops alive: retain fractions [0, 0.5, 1], mean counts [0.0, 0.435, 1.152], P(win) [0.44492, 0.45955, 0.48096]; all−none 0.0360 [0.0305, 0.0417]. Buildings are retained. 644 stratified-in-time rows; match bootstrap. Removal changes the corresponding token pooling only; no elixir refund.

L73 behavior checks reused: late PLAY leaving <3 elixir vs ≥3, and near-cap WAIT (≥9.5) vs lower-elixir WAIT. Outcome reference is residualized within 30-second clock × crown-difference × tower-HP-difference strata. These are observational associations, not causal penalties from pros.

| Cohort | Behavior | Rows | Outcome residual [CI] | live_phi Δ10s [CI] |
|---|---|---:|---|---|
| live | overspend_late_lt3 | 1,950 | -0.0981 [-0.2471, 0.0699] | -0.0282 [-0.0546, -0.0013] |
| live | kept_late_ge3 | 1,378 | 0.0821 [-0.0651, 0.2257] | -0.0163 [-0.0362, 0.0034] |
| live | leak_wait_ge9_5 | 1,886 | 0.1495 [-0.0204, 0.3129] | -0.0039 [-0.0373, 0.0308] |
| live | wait_below9_5 | 54,998 | -0.0010 [-0.1177, 0.1235] | -0.0006 [-0.0077, 0.0068] |
| pro | overspend_late_lt3 | 3,824 | -0.0595 [-0.0968, -0.0188] | -0.0163 [-0.0278, -0.0052] |
| pro | kept_late_ge3 | 4,643 | 0.0206 [-0.0209, 0.0676] | -0.0381 [-0.0493, -0.0278] |
| pro | leak_wait_ge9_5 | 1,506 | 0.0204 [-0.0552, 0.0984] | 0.0132 [-0.0063, 0.0317] |
| pro | wait_below9_5 | 30,665 | 0.0072 [-0.0001, 0.0138] | 0.0187 [0.0159, 0.0215] |

Relative behavior contrasts use the same match-bootstrap weights for both groups. A positive change contrast can indicate a relative preference even if both groups' absolute changes are negative. Changes here use raw 2P−1 scores; default shaping weight halves them.

| Cohort | Contrast | Outcome residual difference [CI] | Raw live_phi Δ10s difference [CI] | Smoothed live_phi Δ10s difference [CI] |
|---|---|---|---|---|
| live | overspend_minus_kept | -0.1802 [-0.2679, -0.0831] | -0.0119 [-0.0430, 0.0167] | -0.0567 [-0.0766, -0.0353] |
| live | leak_minus_other_wait | 0.1505 [0.0283, 0.2529] | -0.0033 [-0.0346, 0.0331] | 0.0173 [-0.0021, 0.0385] |
| pro | overspend_minus_kept | -0.0801 [-0.1575, -0.0072] | 0.0218 [0.0081, 0.0377] | -0.0188 [-0.0314, -0.0058] |
| pro | leak_minus_other_wait | 0.0132 [-0.0709, 0.0923] | -0.0055 [-0.0259, 0.0124] | -0.0138 [-0.0296, -0.0007] |

Pro behavior conflict flags (negative outcome residual/difference upper CI, positive Phi-change/difference lower CI): ['overspend_minus_kept']. These flag observational disagreement, not causal exploitability or additional behavior rewards. An empty list is absence of detected conflict, not proof of safety.

The detected raw overspending contrast reverses sign after trailing-10-second smoothing; it is not a detected overspending preference of the default smoothed option. Elixir partial dependence and the failed AUC/calibration gates independently reject the candidate.

## Learner integration and verdict

Opt in only with `shaping: live_phi`, `advantage: gae`, `critic_warmup_updates: >0`. Existing value-Phi weight/window/critic-scale validation is reused. Null `shaping_phi_ckpt` resolves to this directory's `phi_live.pt`. Loaded once on learner device, eval mode, no gradients; actors only record ticks. Terminal Phi is 0; F=gamma×Phi(next)−Phi(current). No behavior-paying terms or YAML default changes.

Predeclared gates: {"decision": "reject", "auc_gate": false, "calibration_gate": false, "no_banking_gate": false}.

**REJECT**. This verdict concerns an offline potential predictor only. No policy was trained or deployed.

Files: `build.py`, `fit.py`, `baselines.py`, `pro.py`, `evaluate.py`, `report.py`, `verify.py`, `GATES.md`, source/dataset manifests, per-match shards, `dataset.npz`, `pro_inputs.npz`, `pro_dataset.npz`, `phi_live.pt`, `training.json`, `results.json`, `heldout_predictions.npz`, `VERIFICATION.json`. Pipeline edits: `pipeline/live_phi.py`, `pipeline/rl_royale.py`, `pipeline/tests/test_live_phi.py`.

Tests and final verification are recorded in `VERIFICATION.json`; rerun commands and provenance in `README.md`. Checkpoint is a local experimental artifact and remains opt-in even if the statistical gates pass.