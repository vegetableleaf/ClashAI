# Experiment ledger (owner 10-23: "record every experiment done with its results")

All drift checks: 960 board-recorded E4 matches (seed blocks 741200 + 742000) vs the run's own u0, drift_check.py. From
10-23 ~13:00Z the scorer is fixed (sim_value child pricing) and the gates use 99% intervals; elixir at play is watch-only.
Numbers are candidate - u0 [interval]. Pods: 157.157.221.29 ports 32525 / 33572 / 33591 / 33401.

## 10-22 / 10-23 (before succ48)

| id | recipe (vs previous) | seed / pod | result |
|---|---|---|---|
| E1 | drift_tg_e1i: rollout gate tau .27 -> .35, T_gate .1 (live gate), no CLX leash | s74 / 32525 | FAIL u100: hazard share +0.010 [+0.005, +0.015]; idle -0.019, full-elixir s -7.4 |
| E1 | same | s75 / 33572 | FAIL u50: elixir at play +0.249, hazard +0.015 (banking) |
| E1 | same | s76 / 33572 | FAIL u50: idle +0.030, ignored +0.029 (fixed scorer: +0.037 / +0.040); trainer ignored STOP until u76 (bug fixed) |
| E2 | E1 s74 u100 vs CLX, pooled 1,920 | 32525 | E4 -1.93 pp [-4.56, +0.70]; I u40 +1.82 [-0.98, +4.62] |
| E3 | push calibration (opp_model/PUSH_CAL.md) | 32525 | the 1.75x push gap was a scorer bug; E4 ~20-25% soft, I u40 ~25-30% hard (push size) |
| E4 | W18 R1 / R3 / R2 u40 opponents on the push gate | 32525 | cells failed of 42: E4 8, I u40 12, R1 8, R3 9, R2 12 -- none fixes push size |
| E5 | I u40 decode sweep (push_cal report_q5.out) | 32525 | decide 20 + tau .2: 1 / 42 cells (default 12); CLX wins 59.6% vs it (default 49.7%) |
| E6 | x70: exploiter share .3 -> .7 | s74 / 33572 | FAIL u75: trade -0.403, hazard +0.011 (over-defending) |
| E6 | same | s76 / 33401 | u50 PASS (win +0.004, idle +0.002); stopped for habc |
| E7 | x70cal: x70 + calibrated exploiter decode (decide 20, tau .2) | s74 / 32525 | habits clean to u75; stopped by the old 1.5 pp card pro-agreement bar (-1.66 pp) |
| E7 | same | s75 / 33591 | FAIL u75: hazard +0.022 (2nd consecutive) |
| E7 | same | s76 / 33401 | FAIL u100: trade -0.446 (over-defending); idle -0.045, ignored -0.050; win -0.007 |
| E8 | cal30: drift_tg + calibrated decode only (share .3) | s74 / 32525 | FAIL u100: hazard +0.016 (2 consecutive); win -0.054 [-0.109, 0.000]; idle / ignored / trade clean |
| E8 | same | s75 / 33591 | u25 / u50 PASS (u50 win +0.043, idle +0.015, ignored +0.018); stopped for succ48 |
| E8 | same | s76 / 33572 | u25 / u50 PASS (u50 win +0.014, idle -0.030, ignored -0.030); stopped for succ48 |
| E9 | habc: cal30 + habit terms (idle .1 / threat, trade .01 / elixir penalty-only) | s74 / 33401 | u50 PASS; u75 FAIL trade -0.307 [-0.606, -0.025] (idle -0.029, ignored -0.034, win +0.035); stopped ~u80 |
| E9 | same, NO-HAZARD eval | s75 / 32525 | u25 PASS (win +0.057, ignored -0.031); stopped for succ48 |
| E10 | the drift init with vs without the hazard play (eval only) | 32525 | E4 win 0.700 -> 0.615; seconds at >= 9.9 elixir 18.0 -> 62.1 / match |
| E11 | CLX without the hazard play vs CLX with it (eval only, same seeds) | 32525 | win 0.706 vs 0.709 (-0.003, n.s.) BUT seconds at full 52.6 vs 12.5 (+40), first play 39.7 vs 12.8 s, plays / min -0.97, trade -0.52: CLX leaks badly; the soft E4 does not punish it |

Owner rulings during these: banking situational (elixir at play = watch); scorer fixed; opponents calibrated; pro-agreement
bar 5 pp; reward terms approved; hazard play stripped from live + eval; training gets per-phase thresholds only; 48 h mandate.

## succ48 (from 10-24 01:00Z; PLAN.md)

| id | arm | seed / pod | result |
|---|---|---|---|
| S1 | succ48_a: cal30 + tau_phase + habit (idle .05, trade .02) + leak .005, 300 upd, no-hazard eval | s74 / 32525 | running (train 01:00Z) |
| S2 | succ48_a | s75 / 33591 | running (01:01Z) |
| S3 | succ48_b: a with leak .01 | s74 / 33572 | running (01:01Z) |
| S4 | succ48_c: a with idle .1, trade .01 | s74 / 33401 | running (01:01Z) |
