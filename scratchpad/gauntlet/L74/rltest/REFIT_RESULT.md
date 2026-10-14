# Head refit on r1's own trunk (pod 2026-10-14, L40, 13.6-core cgroup quota): NOT better in the SIM

Recipe: `refit_heads.sh newsim_base_main_u0060.pt r1` (CellRefine 48x5 2 ep, then TowerRefine w_chip 2 4000 steps, folded),
torch 2.11.0+cu128, code a572fee, laptop RoyaleSim data (cards.json 9547932d). Scoring: `gap.py --arms D3`, runtime
20261012-linux (royalesim 0.1.33), seeds 741200 + 742000 = 960 pairs, `validate.paired_drift` (as in FINDING.md).

## Outputs (`icebow/data/bench/rl_royale/newsim_base_main/`)
- `newsim_base_main_u0060_cellref.pt` c4fe8508...; val cell_nll 3.1169 -> 3.0216 (r3c's old fit: 3.0765 -> 3.0009)
- `newsim_base_main_u0060_refit.pt` **08457f1e...** (TowerRefine `L73/chip_rocket/tr_w2_r1.pt`)
- TowerRefine VAL, base -> refit: top1 .6366 -> .6466, card_nll .8773 -> .8160, cell_nll 3.019 -> 2.9967,
  chip_val_live_rocket .1291 -> .3113 (old tr_w2 on r3c: .6433 -> .6555, .8233 -> .7969, 2.987 -> 2.9672, .1689 -> .3444)

## SIM, D3 live stack, 960 pairs
| Arm | 741200 | 742000 | 960 |
|---|---|---|---|
| (a) refit | 40.83% | 38.33% | **39.58%** (380) |
| (b) r1 full graft (live) | 41.46% | 42.29% | 41.88% (402) |
| (c) r1 heads-only graft | 43.33% | 43.33% | 43.33% (416) |
| r1 no refine heads (trajd3u, earlier pod) | | | 40.83% (392) |

- refit - full graft: **-2.29 pp [-6.15, +1.56]**
- refit - heads-only: **-3.75 pp [-7.50, +0.10]**
- refit - no heads: -1.25 [-5.21, +2.71]; heads-only - full: +1.46 [+0.00, +2.92] (= FINDING.md)
- Environment check: (b) and (c) reproduced the 10-13/14 rows game for game (480/480 outcomes on each seed set).

Measured: re-fitting the heads on r1's trunk did not recover the add-on value; in the SIM it scores below both grafts
(CI vs heads-only just touches 0). None of the gaps is established; the heads add <= ~2.5 pp on r1 either way.
- Contradicted as the cause: "the old recipe had a 2,000-update barrel-branch step first". That step
  (`L73/barrel_branch/train_branch.py`) trains ONLY the 5 projectile_target_* tensors on a frozen base; r1 already has
  RL-trained ones, and replacing them with OLD's cost -1.46 pp (G1, FINDING.md section 3).
- Offline fit != closed-loop value: the refit's offline gains are as large as r3c's (cell_nll -0.095 vs -0.076;
  chip_val .13 -> .31 vs .17 -> .34) but buy nothing in play. Untested hypothesis: heads fitted to PRO imitation data
  pull r1's RL-tuned placements back toward pro placements. Test (owner decision): fit the heads on r1's own winning
  SIM rollouts instead of pro data, or train them inside RL (the owner's goal: the model learns what the add-ons do).
Copies: `C:/Users/benpe/pod_backup_weekend/pod1014_refit/` (sha-verified).
