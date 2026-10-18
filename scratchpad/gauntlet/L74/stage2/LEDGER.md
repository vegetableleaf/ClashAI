# Stage 2 run ledger (night 10-17/18)

Every run: code hash, config sha, pod, seeds, result. The per-look knob ledger (written BEFORE a result is read) is
`ledger.jsonl` (`ledger_add.py`). Gate frozen first: `gate/FROZEN.txt` sha256 `8ff35b582492c923...` (03:42 UTC), before any
candidate result was read.

## Code and inputs

| item | value |
|---|---|
| pod checkout | `/workspace/cb_tt` = the factorial checkout; every SIM file = git HEAD `7c93f19` (checked file by file against `git archive HEAD`; it differs only in the live-path files `live_gen.py`, `live_gen_v2.py`, `live_options.py`) |
| Stage-2 overlay (P5/P6) | `pod/s2_manifest.sha` (sha `f6122be245af`); + raw E4 `rdef_e4_u0020.pt` and the new `s2_hog_e4.yaml` copied by hand at 04:0x UTC (sha-checked) |
| runtime | fork36-linux (RoyaleSim 0.1.36 wheel), `/workspace/venvf36`, `ROYALE_HEROIW_FORM=hero` |
| 13k checkout | `/workspace/cb_13k` = cb_tt copy, `L74/levels/live_levels.json` replaced by `levels13k.json` (sha `3547c8d3`) |
| eval EXTRA | `--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014` (= the promotion eval), gap.py arm D3, `--census-file` per run |
| seeds | every eval 741200 + 742000 (2 x 480 = 960 paired games); training seed 74 |

| checkpoint | sha256 (prefix) |
|---|---|
| Mark CXXXVIII grafted (13k learner, frozen training opponent) | 0fba110c |
| Mark CXXIV = rlarm_gae_u0250_grafted (12k learner) | 00c845c0 |
| E4 grafted (SIM default opponent, Phase B baseline) | 430faaee |
| E4 RAW rdef_e4_u0020 (Phase C init) | 7fb66681 |
| gen_v32_s0 (imitation, Phase C init, Phase B B2-B4) | 61011b6c |
| exploiter grafted (B5) | 862bfe92 |

| config | sha256 | resolved config sha (rl_royale.config_sha) |
|---|---|---|
| cfg/base_exploit.yaml (= 10-16 rlarm_exploit.yaml) | c3e9f913 | |
| cfg/s2_hog_e4.yaml (init RAW E4) | a985f70a | 0fafea1ad292 |
| cfg/s2_hog_il.yaml (init gen_v32_s0) | 2b58cf67 | 4f2358f7609a |
| resolved diff s2_hog_e4 vs s2_hog_il | `['init']` only (cfgcheck_s2 PASS on both pods) | |
| pools/decks_hog_train.json | 7444e046 | 242 decks, 621 sides |

## Runs

| run | pod | what | seeds | result |
|---|---|---|---|---|
| dry tt / k13 | P5 | 2-match gap D3, CXXXVIII vs E4, cb_tt / cb_13k | 741200-01 | DRY_OK both; tt row 741200 = win end 4283, identical to the factorial ref_cxxxviii row; k13 rows draw profiles 4 / 11 of the 48-profile 13k table |
| dry gen40 / expl | P6 | 2-match, opp gen_v32_s0 T .1 decide 40 / exploiter T .1 | 741200-01 | DRY_OK both (receipt opp 61011b6c / 862bfe92, opp_decide_every 40) |
| s2_hog_il_smoke | P5 | rl_royale --smoke | 74 | SMOKE PASS (round trip identical, resume check ok); 03:47-03:55 UTC |
| s2_hog_e4_smoke (1st) | P6 | rl_royale --smoke, init GRAFTED E4 w2 | 74 | SMOKE FAIL: reload cell_nll 2.92876994 vs 2.92876984 (float non-determinism in the grafted cell_refine head). Fixed: init = RAW E4 (no refine heads; matches gen_v32_s0, which has none) |
| s2_hog_e4_smoke (2nd) | P6 | --smoke, init RAW E4 (cfg a985f70a) | 74 | SMOKE PASS (round trip identical); 04:05-04:14 UTC |
| s2_hog_il | P5 | train 65 updates, cfg 2b58cf67, config sha 4f2358f7609a | 74 | DONE 03:55-08:07 UTC (3.9 min/update; PLAN assumed 2.4). Win vs frozen CXXXVIII 0.27 (u0) -> 0.55 (u60). KL weight beta at its floor 0.03 from u10; KL g/c/x 0.09/0.06/0.05 at u60 (< target 0.10). Pro agreement card 0.657 -> 0.649, gate 0.776 -> 0.744. Ckpts u0025/45/60/65 copied, sha ok |
| s2_hog_e4 | P6 | train 65 updates, cfg a985f70a, config sha 0fafea1ad292 | 74 | DONE 04:14-08:40 UTC (4.1 min/update). Win vs frozen 0.38 -> 0.57 (u60). beta 0.03 floor; KL 0.06/0.05/0.05. Pro agreement card 0.649 -> 0.642, gate 0.752 -> 0.728. Ckpts copied, sha ok |
| C_{il,e4}_u{0025,0045,0065}_{13k,12k} | P5 (il), P6 (e4) | Hog gate: learner CXXXVIII (cb_13k levels) / CXXIV (cb_tt), pool decks_hog_eval, --opp-ckpt arm ckpt, T .1 | 741200 + 742000 | 12 x 960 rows, all DONE + copied (08:07-10:16 UTC, ~15 min each). Scores: phaseC.out; pair: diag/c_pair.out; merge: diag/merge_rows.out |
| B1-B6 (11 runs) | P5: B1, B2, B6, B5-CXXIV; P6: B3, B4, B5-CXXXVIII | full pool decks_live_eval, flags per ledger.jsonl | 741200 + 742000 | 11 x 960 rows, all DONE + copied (03:52-11:19 UTC). Scores: phaseB.out; paired vs E4: diag/b_pair.out |
| T_{il,e4}_u0065, T_e4base | P6 | style telemetry (cb_tel), CXXIV learner, Hog pool, 480 games | 741200 | diagnostic for S2-08 style distance (see report) |
| prep smokes s2_all_il_sA / s2_hog_il_ts / s2_all_e4_sA | P5 | --smoke only (S2-09 pre-ship check; NOT training) | 74 | see report |

Prep smokes (S2-09, P5, 11:22-11:52 UTC): s2_all_il_sA PASS (config sha fa71b8fa7d99, 895 decks), s2_hog_il_ts PASS
(47ffb382f6cf), s2_all_e4_sA PASS (b59b58c2a2fc; the first try failed only because P5 lacked the raw E4 file -> copied, sha ok).

## Results (scored only after FROZEN.txt; every look in ledger.jsonl, result_read set by score_s2.py)

Phase B (full gate, 960 games per Mark; primary cells failed of 9; paired win delta vs E4 T .1, diag/b_pair.out):

| cand | fails | CXXXVIII win (13k cells) | CXXIV win | OT share 13k / 12k | reg-loss 13k / 12k | non-Hog reg (live 41.7) |
|---|---|---|---|---|---|---|
| B0 E4 T .1 | 6 | 63.2 | 59.4 | 60.3 / 68.6 | 13.5 / 13.5 | 58.6 z +3.67 |
| B1 E4 T .3 | 5 | 67.2 (+4.0 [+0.5, +7.5]) | 58.1 (-1.2) | 57.4 / 66.1 | 15.9 / 15.7 | 55.7 z +3.05 |
| B2 gen d10 | 6 | 67.1 (+3.9) | 63.8 (+4.4) | 56.1 / 61.1 | 17.5 / 16.2 | 59.5 z +3.98 |
| B3 gen d20 | 6 | 65.9 (+2.7) | 60.4 (+1.0) | 55.4 / 62.5 | 16.9 / 18.2 | 53.2 z +2.55 |
| B4 gen d40 | 5 (+12k omnibus PASS) | 62.4 (-0.8) | 56.6 (-2.8) | 50.9 / 59.5 | 19.3 / 19.5 | 53.5 z +2.62 |
| B5 exploiter | 4 (+12k omnibus fail) | 51.7 (-11.6) | 46.2 (-13.1) | 70.3 / 75.4 | 14.1 / 14.2 | 45.7 z +0.83 PASS |
| B6 E4 + 13k levels (13k only) | 13k: 2 + omnibus | 61.2 (-2.0 [-5.8, +1.9]) | (= B0) | 60.8 / - | 13.0 / - | 58.6 |

No candidate within reach of every primary cell -> no 1,920 confirming run. Phase C (Hog gate, 4 cells): no checkpoint of either
arm passes (phaseC.out); il u0065 fails only 13k Hog win (51.2% vs live 28.6%, z -2.06).
