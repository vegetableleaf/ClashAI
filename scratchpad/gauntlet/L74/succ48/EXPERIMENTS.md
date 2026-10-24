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
| S1 | succ48_a: cal30 + tau_phase + habit (idle .05, trade .02) + leak .005, 300 upd, no-hazard eval | s74 / 32525 | FAIL u100 (trade x2: u75 -0.384, u100 -0.362). Full-elixir s 62.1 -> 58.5 / 60.9 / 51.3 / 48.7 (u25-100); win 0.646 / 0.658 / 0.677 / 0.678 (u0 0.615); idle 0.195 / 0.172 / 0.139 / 0.150 (u0 0.188) |
| S2 | succ48_a | s75 / 33591 | PASS through u125: full s 59.3 / 64.1 / 54.8 / 38.4 / 27.2; win 0.657 / 0.674 / 0.726 / 0.688 / 0.693; trade -0.03..-0.22 n.s.; idle -0.030 at u125 |
| S3 | succ48_b: a with leak .01 | s74 / 33572 | u100 FAIL x1 (trade -0.333) then u125 PASS: full s 57.8 / 36.0 / 18.7 / 44.9 / 36.0; win 0.677 / 0.701 / 0.669 / 0.666 / 0.720; first play 41 -> 12-34 s |
| S4 | succ48_c: a with idle .1, trade .01 | s74 / 33401 | FAIL u150 (trade -0.359 + proagree): full s 52.3 / 29.7 / 34.2 / 39.8 / 32.3 / 25.5; win 0.667 / 0.724 / 0.720 / 0.690 / 0.693 / 0.636 |

Reading (a): the leak penalty works (best 18.7 s at full, target 12.5); E4 win 0.67-0.72 vs CLX-with-hazard 0.709 on the same
seeds. Every FAIL is the defence-trade gate: spending the formerly wasted elixir lowers trade / push (CLX itself trades -0.33
without the hazard play, E11). DECISION 10-24 15:00Z (lead): trade materiality bar 0.25 -> 0.50 (drift_check.py, all pods);
trade stays reported and is compared with CLX-with-hazard in the final gate. Note: 32525 / 33401 sat idle 07:25 / 09:27 ->
15:08Z (my watcher looked in the wrong folders) -- ~13 pod-hours lost.

| id | arm | seed / pod | result |
|---|---|---|---|
| S5 | succ48_d: BRANCH of S3 (b_s74) u125 (init = that ckpt, sha 16e7d958), leak .015, trade .04 | s77 / 32525 | running (train 15:08Z) |
| S6 | succ48_e: BRANCH of S2 (a_s75) u125 (sha 7b6ee5f9), leak .015, trade .04 | s78 / 33401 | running (15:09Z) |

S5 (d_s77) u25 FAIL: seconds at full 36.0 -> 49.4 [+5.7, +21.3], first play 23 -> 38 s, win -0.053 [-0.109, 0.000]. Cause (a, by
the weights): trade .04 > leak .015 made WASTING elixir cheaper than over-paying, so the policy held more. Stopped at u~35
with S6 (same weights, u~28). DECISION: leak weight must exceed trade weight; LEAK_MATCH_CAP 0.3 -> 0.6 (a > 20 s leak still
gets gradient); shaping_critic_scale 2.2 (bound 1 + 0.3 + 0.3 + 0.6).

| id | arm | seed / pod | result |
|---|---|---|---|
| S7 | succ48_f: BRANCH of S3 (b_s74) u150 (sha 9300ba4c; leak 24.8 s, win 0.644), leak .03, trade .02, cap .6 | s79 / 32525 | running (17:06Z) |
| S8 | succ48_g: BRANCH of S2 (a_s75) u150 (sha 7aeb2f19; leak 32.1 s, win 0.693), leak .03, trade .02, cap .6 | s80 / 33401 | running (17:07Z) |
| S2 end | succ48_a_s75 stopped at u~185 for S10 | s75 / 33591 | u150 PASS (full 32.1, win 0.693); u175 PASS but full 38.1, win 0.641 (falling) |
| S3 end | succ48_b_s74 stopped at u~188 for S9 | s74 / 33572 | u150 PASS (full 24.8, first play 13.8 s, win 0.644); u175 full 46.2, first play 40.1 s, win 0.626 -- the leak OSCILLATES with low leak weight (18.7 / 44.9 / 36.0 / 24.8 / 46.2) |
| S9 | succ48_h: BRANCH of S3 u75 (its best leak 18.7 s, win 0.669), leak .03, trade .02, cap .6 | s81 / 33572 | running (17:44Z) |
| S10 | succ48_i: BRANCH of S2 u125 (full 27.2, win 0.693), leak .03, trade .02, cap .6 | s82 / 33591 | running (17:47Z) |
| S7 u25 | succ48_f (32525) | s79 | PASS: full 24.8 -> 17.1 [-13.8, -1.4], first play 13.8 -> 10.4 s, win 0.644 -> 0.673, trade +0.25, idle / ignored flat |
| S8 u25 | succ48_g (33401) | s80 | PASS: full 32.1 -> 27.5, first play 28.9 -> 20.8 s, win 0.685 (-0.007), trade -0.20 -> +0.04 |
| S7 u50 | succ48_f (32525) | s79 | PASS: **full 11.1 s (target 12.5 MET)**, first play 10.4 s, win 0.674, idle -0.024, ignored -0.027, trade +0.14 -> gate48 running on u50 |
| S8 u50 | succ48_g (33401) | s80 | PASS but leak STALLED: full 32.7 (u25 27.5), first play 30.4 s, win 0.676 -> stopped (a-lineage does not fix the leak) |
| S9 u25 | succ48_h (33572) | s81 | PASS: full 18.7 -> 11.6 s (target met), first play 9.5 s, win 0.657 |
| S11 | succ48_j: BRANCH of S7 (f) u50 (sha 91ba1666), same weights | s83 / 33401 | running (replaces g) |
| S10 u25 | succ48_i (33591) | s82 | FAIL: idle +0.030 [+0.005, +0.057]; leak 27.2 -> 22.9; win 0.665 -> stopped (a-lineage twice weaker) |
| S12 | succ48_k: BRANCH of S9 (h) u25 (sha 1535d51e; leak 11.6 s), same weights | s84 / 33591 | running (replaces i) |
