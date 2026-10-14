# Overnight 2026-10-13/14: RL tests, and why RL looked like it hurt

All SIM numbers: `L74/gap/gap.py`, CAL set c (E4 at T .1), evo + lad censuses, paired by census/seed/side, runtime
0.1.33; "960 pairs" = seed sets 741200 + 742000. Copies: `pod_backup_weekend/pods1013/rltest/`.

## 1. One-change RL test: play/wait temperature (T_gate) 0.1 vs today's T .5
r1's exact config, continued from its final pre-graft checkpoint (newsim_base_main_u0060).

| Measure | 20 updates | 60 updates |
|---|---|---|
| Greedy, no rules (D1) vs start: control | +2.08 [-3.54, +7.71] | +2.92 [-2.50, +8.33] |
| Greedy, no rules (D1) vs start: T_gate | +0.00 [-5.83, +5.62] | +0.42 [-5.21, +6.04] |
| Deployed (rules + grafted heads) vs r1, 960 pairs: control | | **-5.94 [-9.69, -2.29]** (fresh seeds alone -5.83) |
| Deployed vs r1, 960 pairs: T_gate | | -3.85 [-7.81, +0.00] |
| Deployed, T_gate vs control | | +2.08 [-1.77, +5.83] |

Measured: T_gate changes the model (sampled at the old T .5 it loses 11.5 pp) but neither arm improves greedy play.
The staged T_gate model (`icebow/data/bench/rl_royale/rltest/`) is NOT recommended.

## 2. r1's own training run, scored at each checkpoint (960 pairs each)

| Checkpoint | Plain greedy D1 | Deployed D3 (rules + grafted heads) | Add-ons' value (D3 - D1) | Deployed, normal IW |
|---|---|---|---|---|
| ADAPT final (r1's start) | 38.33% | 47.08% | **+8.75 [+4.79, +12.60]** | 50.31% |
| update 20 | 40.83% | 46.15% | +5.31 [+1.46, +9.27] | 47.19% |
| update 40 | 41.77% | 44.06% | +2.29 [-1.77, +6.25] | 48.12% |
| update 60 (= r1; reproduces r1g game for game) | 39.69% | 41.88% | +2.19 [-1.88, +6.15] | 45.42% |

- **Measured:** RL did NOT hurt the plain policy (+1.35 [-2.50, +5.10] over the run); the deployed player fell
  -5.21 [-9.17, -1.25] because the add-ons' value shrank from ~+9 pp to ~+2 pp as RL changed the model under them
  (the rules were hand-tuned on earlier models; the refine heads were trained on another trunk and grafted on).
- **Contradicted:** "the decline is because r1 trained with the normal Ice Wizard but is scored with the hero": the decline
  is the same under the normal Ice Wizard (-4.90 [-8.85, -0.83]).
- Consequence for the training architecture: anything bolted on after training (rules, grafted heads) loses fit as RL
  proceeds; the model must learn what they do (owner's goal) or be trained with them in place.
- Caveat: the SIM's ranking of r1 vs the old live model (-2.60 [-6.56, +1.35]) disagrees with live A/B1 so far (r1 ahead).
