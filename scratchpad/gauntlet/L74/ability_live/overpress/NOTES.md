# Hero IW overpress diagnosis (10-18)

Finding: ICEBOW cue_ab (CXXXVIII + learned ability head, 65 updates) is -5.00 pp [-8.65, -1.46] vs CXXXVIII on the
promotion eval and presses 4.08 / match (64% of IW deploys) vs the rule's 1.88 (28%).

## Root cause (measured)

The training environment presses the learner's Hero Ice Wizard with a DIFFERENT rule than the eval and live do.

* `ROYALE_HEROIW_PRESS` is never set by any training chain (cue_ab `chain_ab.sh`, grep of L74 *.sh). Unset = `off` ->
  `royale_env._v2_gate`: IceWizard has no v2 model -> the generic range rule `_near` ("any enemy within IW range +
  1.5 tiles").  The eval (`gap.py`, default `--iw-press live`) uses `LiveIWPolicy` (the live rule).
* The training pipeline cannot use the live rule at all: `rl_royale.Learner._entries` builds
  `RoyalePoolEnv(decision_ticks=...)` without hero abilities, and `royale_env` raises
  "Live IW press rule needs hero_abilities and ability_policy v2" (`train_wslive_fail1.log`).
* So the warm start cloned the generic rule: 3,933 labels / 128 rollouts, q mean 0.2423 -> 7.45 positive labels / match.
  With the live rule (shim `train_boot.py`): 11,934 labels, q mean 0.0244 -> 2.27 / match.

Same 960 paired games (fork36, D3, seeds 741200 + 742000), vs Mark CXXXVIII with the live rule:

| arm | presses/m | per deploy | win % | delta pp [95% CI] |
|---|---|---|---|---|
| CXXXVIII, IW never pressed (cx_never) | 0.00 | 0.00 | 66.88 | +3.65 [+0.94, +6.35] |
| live-label warm start, greedy (ws_live) | 0.75 | 0.11 | 65.73 | +2.50 [-0.21, +5.21] |
| CXXXVIII, live rule (promo) | 1.88 | 0.28 | 63.23 | 0 |
| live-label warm start, sampled (ws_live_sample) | 2.11 | 0.32 | 63.02 | -0.21 [-3.12, +2.71] |
| cue_ab u65 greedy (promo) | 4.08 | 0.64 | 58.23 | -5.00 [-8.65, -1.46] |
| cue_ab u65 sampled (ab_sample) | 4.78 | 0.76 | 58.12 | -5.10 [-8.65, -1.35] |
| generic-label warm start u0000, greedy (ws_greedy) | 5.19 | 0.81 | 54.79 | -8.44 [-11.88, -5.00] |
| CXXXVIII, generic rule = TRAINING env (cx_off) | 5.43 | 0.84 | 52.60 | -10.62 [-14.17, -7.08] |
| generic-label warm start u0000, sampled (ws_sample) | 5.51 | 0.85 | 50.10 | -13.12 [-16.67, -9.58] |

Determinism: ability_stats on (outcomes_boot.py) reproduced the promotion eval's chunk 00000 exactly, 12/12 games.
Pros 2.34 / match, 32% of deploys; live CXXXVIII rule 1.41, 23%.

PPO did not double the press rate: it CUT it, 5.19 -> 4.08 / match greedy (5.56 -> 4.78 sampled), and won back
+3.4 pp. In training (train_log) accepted presses / match fell 6.00 -> 5.46 (first vs last 10 updates); the
per-decision rate fell 0.24 -> 0.155 mostly because pressable decisions / match rose 26.0 -> 37.5 (fewer presses keep
the button pressable longer). The environment did not reward over-pressing; it handed the head an over-pressing teacher.

## The five questions -- see the final report for all numbers.

Scripts: train_curve.py, train_trend.py (Q4); eval_rates.py, eval_timing.py, head_stats.py, compare_arms.py (evals);
live_cost.py (Q1); live_freeze.py, cube_hp.py, freeze_by_card.py, live_charge.py, live_button.py (Q2 live);
sim_probe.py (Q2/Q5 SIM); run_overpress.sh, run_overpress2.sh, run_wslive.sh, run_rerun.sh, run_wslive_sample.sh
(pod runners), outcomes_boot.py + pyout.sh (ability_stats + sampled head decoding), train_boot.py (live-rule shim).
Results: pod 14009 /workspace/ab/overpress, copied to C:/Users/benpe/pod_backup_weekend/overpress.
