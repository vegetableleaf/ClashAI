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

## 3. Which add-on lost its value: rules vs grafted heads (960 pairs; D3 ungrafted isolates the rules)

| Checkpoint | Rules (D3 ungrafted - D1) | Grafted heads (D3 grafted - D3 ungrafted) |
|---|---|---|
| ADAPT final | +2.92 [-0.94, +6.77] | **+5.83 [+1.98, +9.69]** |
| update 20 | +0.94 [-2.92, +4.79] | +4.38 [+0.52, +8.33] |
| update 40 | -0.62 [-4.38, +3.23] | +2.92 [-0.94, +6.88] |
| update 60 (r1) | +1.15 [-2.60, +5.00] | +1.04 [-3.02, +5.00] |

- **Measured:** the decay is mostly the grafted heads (r3c-trunk CellRefine + TowerRefine); the rules are worth ~1-3 pp in
  the SIM throughout.
- **Measured (code):** `weekend/graft_generic.py` also copies OLD's `projectile_target_in.*` (5 tensors) over the arm's
  OWN RL-trained ones (max |delta| 0.38 on r1, 0.37 on ADAPT). Testing a heads-only graft that keeps the arm's own
  projectile layers (`G1`, running).
- **G1 result (heads-only graft, 960 pairs):** r1: heads-only 43.33% vs full graft 41.88% = +1.46 [+0.00, +2.92]; ADAPT:
  -1.04 [-2.60, +0.52]. So overwriting r1's own projectile layers costs ~1.5 pp (borderline); heads-only vs ungrafted:
  ADAPT +4.79 [+1.04, +8.65], r1 +2.50 [-1.56, +6.46]. Main loss = heads fitted on r3c's trunk no longer fit r1's trunk.
  Proposed fix (not started; owner decision): re-fit CellRefine/TowerRefine on each new RL trunk (`pipeline/
  train_cell_refine.py` + the tower-refine trainer) instead of grafting r3c's; and stop grafting `projectile_target_*`.
  r1 heads-only checkpoint (pod C only, `newsim_base_main_u0060_g1.pt`, sha 5ca58ddd) = a +1.5 pp SIM candidate, not staged.
