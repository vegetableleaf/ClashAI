# W12: tonight's arms vs W7's calibrated opponent (fin15, all16)

Setup. Each arm's grafted u130 checkpoint (rlarm_<RUN>_u0130_grafted.pt; CLX = rlarm_stepd_ctrl_nos2_u0130_grafted.pt) vs the R6 u20 opponent
(w7opp.pt, sha256 3452256458450fcc8fc4848445e5c06c64970ad0b1b8a60c1a915208509c475b) at T 0.1, decide 40, default reaction. Tool: pod/opp_eval_fin15.sh
(opp_eval.sh with fin13 -> fin15 and an overridable base dir; every other setting unchanged: arm D3, live-mirrored pool, --levels all16, step-d EXTRA + --crown-log, sampled ability head).
Seeds 741200/742000 (std) and 743000/744000 (fresh), 480 games each, one isolated /workspace/o3w12 copy per pod. Pairing key = (seed, tag, learner_side, opp_deck, occurrence); all keys matched (n = 960 per split, 1920 pooled).
Results pulled sha-verified to C:/Users/benpe/pod_backup_weekend/tonight1020/<RUN>/. Analysis: w12_analyze.py (same dir).

## Win rate, paired vs CLX (delta = arm - CLX, percentage points)

| arm | split | n | win% | CLX win% | delta pp | 95% CI |
|---|---|---|---|---|---|---|
| tn_base_s74 | std | 960 | 63.9 | 64.3 | -0.42 | [-4.28, +3.45] |
| tn_base_s74 | fresh | 960 | 63.1 | 63.6 | -0.52 | [-4.26, +3.22] |
| tn_base_s74 | pooled | 1920 | 63.5 | 64.0 | -0.47 | [-3.16, +2.22] |
| tn_base_s75 | std | 960 | 67.7 | 64.3 | +3.44 | [-0.27, +7.15] |
| tn_base_s75 | fresh | 960 | 67.9 | 63.6 | +4.27 | [+0.54, +8.00] |
| tn_base_s75 | pooled | 1920 | 67.8 | 64.0 | +3.85 | [+1.22, +6.48] |
| tn_lead_s74 | std | 960 | 66.0 | 64.3 | +1.77 | [-1.99, +5.53] |
| tn_lead_s74 | fresh | 960 | 64.3 | 63.6 | +0.62 | [-3.01, +4.26] |
| tn_lead_s74 | pooled | 1920 | 65.2 | 64.0 | +1.20 | [-1.41, +3.81] |
| tn_rocket_s74 | std | 960 | 60.7 | 64.3 | -3.54 | [-7.44, +0.36] |
| tn_rocket_s74 | fresh | 960 | 60.6 | 63.6 | -3.02 | [-6.85, +0.81] |
| tn_rocket_s74 | pooled | 1920 | 60.7 | 64.0 | -3.28 | [-6.02, -0.55] |
| tn_tornado_s74 | std | 960 | 59.3 | 64.3 | -5.00 | [-8.81, -1.19] |
| tn_tornado_s74 | fresh | 960 | 59.9 | 63.6 | -3.75 | [-7.67, +0.17] |
| tn_tornado_s74 | pooled | 1920 | 59.6 | 64.0 | -4.38 | [-7.11, -1.64] |
| tn_redirect_s74 | std | 960 | 62.9 | 64.3 | -1.35 | [-5.00, +2.29] |
| tn_redirect_s74 | fresh | 960 | 64.6 | 63.6 | +0.94 | [-2.88, +4.75] |
| tn_redirect_s74 | pooled | 1920 | 63.8 | 64.0 | -0.21 | [-2.85, +2.43] |
| clx_fin15 | std | 960 | 64.3 | - | - | - |
| clx_fin15 | fresh | 960 | 63.6 | - | - | - |
| clx_fin15 | pooled | 1920 | 64.0 | - | - | - |

## Crown slices (pooled 1920 games per arm, per-game means from crown.summary)

| arm | n | lost_princess | gave_back | king_end | tornados_after_fall | toward_after_fall | rockets_tower |
|---|---|---|---|---|---|---|---|
| tn_base_s74 | 1920 | 40.1% | 4.4% | 0.871 | 0.363 | 0.622 | 0.382 |
| tn_base_s75 | 1920 | 36.0% | 4.5% | 0.875 | 0.287 | 0.637 | 0.454 |
| tn_lead_s74 | 1920 | 37.9% | 4.0% | 0.860 | 0.340 | 0.811 | 0.424 |
| tn_rocket_s74 | 1920 | 41.2% | 3.7% | 0.846 | 0.248 | 0.647 | 0.496 |
| tn_tornado_s74 | 1920 | 42.4% | 4.0% | 0.850 | 0.227 | 0.399 | 0.382 |
| tn_redirect_s74 | 1920 | 40.4% | 5.6% | 0.839 | 0.291 | 0.490 | 0.501 |
| clx_fin15 | 1920 | 40.5% | 5.4% | 0.837 | 0.369 | 0.827 | 0.347 |

## Reading (labels: a = measured, b = plausible untested)

- (a) Only tn_base_s75 (+3.85 pp, CI [+1.22, +6.48]) beats CLX pooled; only tn_tornado_s74 (-4.38 [-7.11, -1.64]) and tn_rocket_s74 (-3.28 [-6.02, -0.55]) are below it. tn_base_s74, tn_lead_s74, tn_redirect_s74 are inside noise.
- (a) The two tn_base arms are the same config and differ by 4.3 pp pooled (63.5 vs 67.8): training-seed variance is as large as the best arm's gain. tn_base_s75's win is NOT evidence for the base recipe; the base-vs-lead-vs-redirect ordering is unresolved at one seed each.
- (a) The CIs are 95% per comparison with 6 arms x 3 splits and no multiplicity correction; the tn_base_s75 lower bound (+1.22) does not survive a Bonferroni-style widening (b).
- (a) The tornado arm has the lowest tornados_after_fall (0.227 vs CLX 0.369) and toward_after_fall (0.399 vs 0.827) and the lowest win rate; the rocket arm has the highest rockets_tower (0.496) and also loses to CLX. More rocket-to-tower or fewer post-fall tornados did not convert to wins here (b: the opponent punishes them / the reward over-weighted them; untested).
- (a) lost_princess is within 36-42% for every arm; the best arm (tn_base_s75) has the lowest (36.0%) and the worst (tornado 42.4%) the highest, consistent with the win-rate order.
- Single opponent model (one checkpoint, one temperature), SIM only; nothing was deployed.
