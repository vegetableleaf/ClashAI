# P3-FORK pilot results (2026-10-28, pod 32657; dumps / reports in plan1026/cf/data, gitignored)

Labels: (a) measured. Sources: pilot2.jsonl (cfpilot2), pilot3.jsonl (cfpilot3, noise study), pilot4.jsonl (cfpilot4, validation).

- pilot2: peak cgroup 67.3 GB, peak summed RSS 44.7 GB, cgroup oom / oom_kill at the end 12 / 5
- pilot3: peak cgroup 46.1 GB, peak summed RSS 46.5 GB, cgroup oom / oom_kill at the end 12 / 5
- pilot4: peak cgroup 47.3 GB, peak summed RSS 43.5 GB, cgroup oom / oom_kill at the end 12 / 5

### pilot2 (lib_cfclone3, K 2, horizon 600, pilot probabilities, from update 2)
Owner return (R_win + tower_phat), critic warm-up, 26 actors.

512 matches, 2907 samples; fork ticks / match tick 5.87; critic slope levels 0.79 +- 0.03 (n 1508), diffs 0.72 +- 0.07 (n 983).

| trigger | samples | per match | SNR | SNR 90% CI | fork ticks / sample | alternatives: mean advantage (n) |
|---|---|---|---|---|---|---|
| idle_full | 112 | 0.22 | 0.00 | [0.00, 0.75] | 2470 | chosen +0.004, play_now -0.004 |
| log_bait | 434 | 0.85 | 0.63 | [0.37, 0.87] | 2959 | chosen +0.010, wait -0.010 |
| random | 71 | 0.14 | 0.00 | [0.00, 0.70] | 3169 | chosen +0.014, sampled -0.011 |
| rocket | 219 | 0.43 | 1.23 | [1.00, 1.45] | 3912 | chosen +0.118, rocket_clump -0.074, rocket_princess -0.080 |
| rocket_played | 71 | 0.14 | 1.47 | [0.83, 2.11] | 3898 | chosen -0.002, second_card -0.014, wait +0.016 |
| rocket_tornado | 331 | 0.65 | 1.47 | [1.26, 1.72] | 5508 | chosen +0.180, combo -0.138, rocket_clump -0.125, wait +0.142 |
| siege | 160 | 0.31 | 1.09 | [0.79, 1.33] | 5547 | chosen +0.026, front +0.006, rocket_on -0.071, troop_on -0.003, wait -0.012 |
| tornado_redirect | 654 | 1.28 | 1.14 | [0.99, 1.29] | 4823 | chosen +0.082, tornado_king -0.062, tornado_on -0.034, wait +0.084 |
| wincon | 151 | 0.29 | 0.71 | [0.38, 1.01] | 3448 | cheap_on +0.031, chosen +0.031, rocket_on -0.130, troop_on -0.005, wait +0.005 |
| xbow | 506 | 0.99 | 0.92 | [0.78, 1.06] | 5809 | chosen +0.057, wait +0.036, xbow_defensive -0.066, xbow_other_lane -0.027 |
| xbow_after_fail | 198 | 0.39 | 0.96 | [0.76, 1.17] | 5702 | chosen +0.058, rocket_princess -0.084, wait +0.045, xbow_defensive -0.017, xbow_reach +0.039 |

### pilot4 (fe364ceb, DEFAULTS, horizon 600 / 300 for the five weak triggers, from update 1)
cf_p = P_DEFAULT (+ rocket_tornado 0.055, tornado_redirect 0.0011), cf_audit_p 0.1.

384 matches, 468 samples; fork ticks / match tick 0.71; critic slope levels 0.80 +- 0.11 (n 116), diffs -0.13 +- 0.53 (n 69).

| trigger | samples | per match | SNR | SNR 90% CI | fork ticks / sample | alternatives: mean advantage (n) |
|---|---|---|---|---|---|---|
| idle_full | 94 | 0.24 | 2.21 | [0.53, 4.03] | 1818 | chosen -0.004, play_now +0.004 |
| log_bait | 114 | 0.30 | 0.52 | [0.31, 0.86] | 1572 | chosen -0.009, wait +0.009 |
| random | 50 | 0.13 | 0.77 | [0.00, 0.88] | 1698 | chosen +0.007, sampled -0.006 |
| rocket | 33 | 0.09 | 0.89 | [0.00, 1.69] | 3058 | chosen +0.120, rocket_clump -0.125, rocket_princess -0.063 |
| rocket_played | 24 | 0.06 | 0.76 | [0.00, 1.35] | 3501 | chosen +0.018, second_card -0.006, wait -0.012 |
| rocket_tornado | 19 | 0.05 | 1.30 | [0.38, 2.25] | 4554 | chosen +0.145, combo -0.127, rocket_clump -0.099, wait +0.172 |
| siege | 12 | 0.03 | 1.65 | [0.85, 3.01] | 2074 | chosen +0.025, front +0.001, rocket_on -0.131, troop_on +0.048, wait -0.093 |
| tornado_redirect | 26 | 0.07 | 1.41 | [0.68, 2.35] | 4920 | chosen +0.096, tornado_king -0.112, tornado_on +0.013, wait +0.016 |
| wincon | 54 | 0.14 | 1.63 | [1.29, 2.13] | 2164 | cheap_on -0.114, chosen +0.046, rocket_on -0.100, troop_on -0.017, wait +0.056 |
| xbow | 26 | 0.07 | 0.95 | [0.57, 1.29] | 5572 | chosen +0.027, wait +0.074, xbow_defensive -0.057, xbow_other_lane -0.044 |
| xbow_after_fail | 16 | 0.04 | 0.52 | [0.00, 1.14] | 5061 | chosen +0.016, rocket_princess -0.083, wait +0.078, xbow_defensive -0.022, xbow_reach +0.086 |


## Verdicts (labels as in the lead's ticket)
- SNR target >= 0.5 (a): pilot2 (K 2, 600 ticks, 2,907 samples): idle_full 0.0 and random 0.0 FAIL (CI upper 0.75 / 0.70), log_bait 0.63, wincon 0.71, every other
  trigger 0.92-1.47. Noise study (pilot3, same samples at several horizons / K, from update 1): K 2 at 300 ticks gives idle_full 0.77, log_bait 0.78, wincon 1.31,
  siege 1.15, random 1.23 (vs 0.29 / 0.52 / 0.83 / 0.68 / 0.80 at 600); K 4 at 600 gives 1.26 / 0.41 / 1.19 / n.a. / 1.32. So the fix is the horizon (and it halves the
  cost); K 4 helps idle_full and random only. Defaults: HORIZON_DEFAULT 300 for those five. Pilot4 (defaults, small n): all >= 0.5 (log_bait 0.52, xbow_after_fail 0.52 at
  n 16: borderline, CIs wide at 1x sample counts).
- Caveat (b): SNR rises as the horizon shrinks for EVERY trigger (pilot4 sweep: rocket_tornado 3.55 / 2.39 / 1.55 / 1.3 at 150 / 300 / 450 / 600). A short horizon
  measures the immediate state difference (elixir spent) consistently, which is not the same as the action's value; so the horizon is cut only where SNR failed.
- Critic slope band [0.7, 1.3] (a): levels 0.79 +- 0.03 (n 1,508, pilot2), 0.85 +- 0.05 pooled pilot3 + pilot4; within-sample differences 0.717 +- 0.072 (n 983, pilot2),
  0.66 +- 0.17 pooled pilot3 + 4 at 600, 0.75 +- 0.30 at 300, 0.72 +- 0.22 at 450: INSIDE the band but at its lower edge: the critic exaggerates the difference
  between two candidates by ~1.4x (b: elixir-spend pricing). At 1x the per-update audit has ~60 samples (cf_audit_p 0.1 x ~1.2 samples / match x 512): the per-update
  slope SE is ~0.45, so the band gate needs >= 8 updates pooled or cf_audit_p 0.3 during gate runs. A calibration factor (advantage x slope) is the available fix if the
  owner wants the exaggeration removed (not applied).
- Cost (a): pilot probabilities 5.87x match ticks (pilot2) -> 3.6x (pilot3) -> DEFAULTS 0.71x (pilot4, 1.2 samples / match, fork 9.7 s of 106 s wall per match). The
  model predicted 1.0x with cf_audit_p 0.2; with 0.1 there is ~29% headroom (P_DEFAULT can be raised by up to 1.4x).
- Signal share (b): at 1x the forks give ~0.3 extra PPO rows per match against ~330 real rows: ~0.1-0.2% of the gradient at cf_w 1. R_fork matters only with a larger
  cf_w (or more fork budget); that is a lead / owner knob.
- SIM findings the forks expose (a, pilot2 from update 2; for the P4 audit): a Rocket played now on a clump / princess is worth -0.074 / -0.080 vs the policy's own
  action (n 219); combo -0.138 vs lone Rocket -0.125 (n 331, no difference resolved; the Tornado's 3 elixir is priced and the combo is NOT better here); Tornado into
  our king -0.062, centre on the unit -0.034, wait +0.084, chosen +0.082 (n 654): the SIM does not reward the king redirect inside 30 s.
