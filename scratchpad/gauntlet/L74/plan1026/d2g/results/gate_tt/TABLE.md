# D2 CLXIII re-baseline with tower troops (ENG-SME step 3, 2026-10-28; pod 33308 /workspace/d2tt)
Labels: (a) measured. 4 seeds x 480 paired games per cell (741200 742000 743000 744000), gap.py D3 all16, CLXIII NOLEAK
8d328a43, lib /workspace/d2/stage/lib, tables 16.402.22; tower troops = `--opp-tower-troops DaggerDuchess:0.028,
Cannoneer:0.028,ChefTower:0.014` (the historical gate's flag). "No troops" = the earlier D2-G rows (results/gate/).

| suite | engine | no troops (earlier) | with troops | troop effect, paired |
|---|---|---:|---:|---:|
| E4 | crforge | 70.10% | **70.47%** [68.39, 72.47] | +0.36 pp [-0.32, +1.05] |
| E4 | fin16 | 74.58% | **74.53%** [72.53, 76.43] | -0.05 pp [-0.66, +0.55] |
| iu40 | crforge | 56.04% | **56.09%** [53.86, 58.30] | +0.05 pp [-0.62, +0.72] |
| iu40 | fin16 | 59.43% | **59.32%** [57.11, 61.50] | -0.10 pp [-0.72, +0.51] |

crforge - fin16 (paired), with troops: E4 **-4.06 pp [-6.63, -1.50]** (was -4.48); iu40 **-3.23 pp [-5.94, -0.52]** (was -3.39).
- Control (a): the new tree without troops reproduces the earlier rows 480 / 480 on both engines (control_cmp.txt), so the
  differences above are the troops only. Tower troops change little (troop decks are ~7% of opponents by the flag).
- The crforge gap to fin16 stays significant on both suites (CI below 0).
- Pod 33308's container restarted twice during the run (~18:41 UTC and ~20:53 UTC, by container uptime); gate.sh redid the partial
  seeds; last 3 seeds ran at 6-8 workers within ENG-SME's 25 GB budget (cgroup usage ~18-40 GB total pod at the checks).
Files: {cf,rs}_{e4,iu40}_SEED.jsonl, ctl_{cf,rs}_e4_741200.jsonl, score_e4.txt, score_iu40.txt, troop_effect.txt,
control_cmp.txt, summaries.txt, README.txt (Codex ENG-SME_3c/3d setup notes).
