# Plan A ledger (owner: record every experiment with its results)

## Pods (rented 10-25; key ~/.ssh/runpod_clashbot; pod-to-pod key ~/.ssh/podlink on 33912)
| port | GPUs / vCPU quota | role |
|---|---|---|
| 33912 | 2x 4090 / 108.8 | hub (restored archive), pro memory dataset + imitation (S3), control arm x_s102 meanwhile |
| 33458 | 1x 4090 / 54.4 (quiet host) | S4 X-Bow lock measurement vs candidate opponents (q_xb: E4, I u40 cal, W18 R1 / R2 / R3 cal) |
| 33522 | 1x 4090 / 54.4 | CLXIII gate baseline (gate48 succ48_o_s91 75) |
| 33569 | 1x 4090 / 54.4 | control arm x_s101 (CLXIII + tower_crown + xbow cost, no memory) |
Restore: /workspace/restore/restore.sh (archive pod_backup_weekend/succ48_1025 + venv rebuilt with exact versions); tests 27 + 5 skip,
smoke PASS on 33912; replicated to the singles (9.2 GB each, env check OK).

## Stages
| stage | status |
|---|---|
| S0 infra | DONE 10-25 15:05Z |
| S1a memory builder | DONE 63a1ebb: pipeline/match_memory.py (45-float events x 128, 54-float summary), 14 tests (planted-bug check: 6 / 6 caught), incremental == offline on 1,756 live decisions, 1.56 ms / decision |
| S1b wiring (model zero-init, storage per match, pro builder, rollouts, live) | in progress (agent) |

## S4 X-Bow denial, measured (memory/xbow_arch.py; reach X-Bow lock = princess -5% in 600 ticks)
| source | matches | lock [95%] | per-match (>= 2 reach): 0 locks / < .5 / >= .5 |
|---|---|---|---|
| SIM CLXIII vs E4 | 960 | 0.585 [0.568, 0.603] | 3% / 25% / 75% |
| SIM vs I u40 cal | 960 | 0.626 | 4% / 22% / 78% |
| SIM vs W18 R1 cal | 960 | 0.589 | 7% / 27% / 73% |
| SIM vs W18 R3 cal | 960 | 0.563 | 7% / 30% / 70% |
| LIVE CLX | 234 | 0.565 [0.521, 0.613] | 9% / 30% / 70% (control: 0.417, 27% shut-outs) |
| LIVE CLXIII | 35 | 0.462 [0.343, 0.574] | 16% / 41% / 59% (bridge 0.222, control 0.318; small n) |
Reading (a): the SIM mean is right (R3 = live CLX), the TAILS are not: live shut-out matches 2-5x more common, live archetypes
swing more (owner's point). S4 target = the pool's shut-out share and per-archetype spread, not the mean: I u40 cal + R3 cal now,
plus a stronger denier (W18 R4, live-Ranked X-Bow starts) for the shut-out tail.

## S1b wiring -- DONE (committed with this entry)
- memory: v1 model flag (fv6 base; absent = identical config hash + byte-identical records, tested). Encoder: card / form embed +
  46-float events -> 2 transformer layers d 64 -> masked mean + query pool; summary (54 + answer card) MLP; ONE zero-init linear
  into the global vector. G-mem-0: CLXIII vs CLXIII + memory on 2,500 pro rows: max |diff| 0 (gate / card / cell / value).
- Storage: per-match event tables (pro ~105 MB on disk for the corpus; per-row would be ~83 GB); features_at() == MatchMemory.
- Pro builder: python -m pipeline.dataset_gen memory --dataset gen_dataset_v32_fv5.npz --out X.npz --workers N (0.2 s / replay).
- Rollouts: 0.94 ms / decision memory build; learner log-probs = actor's within 8e-7 with memory active.
- Live: live_gen own_events now carry x / y / form; 6 recorded CLXIII matches replayed through GenPilot: memory == offline at
  2,174 / 2,174 decisions; +1.0-1.6 ms median per decision (encoder forward extra, GPU not measured).
- X-Bow answer rule: first opponent play in the lane within 4 s and 12 tiles (5 live matches: 14 / 26 answered; old 6-tile rule 3).
- NOTE (a): the live supervisor restarted a BAIT-deck run (wk_bait u60) at 11:51:21 EDT 10-25 and imported the then-uncommitted
  S1b live_gen / e1_eval / model_gen; for a no-memory model the only active change = extra own-play fields; ~3 matches normal;
  owner stopped it 12:15 EDT. Icebow LIVE_OPTIONS / CKPT_OVERRIDE untouched.
- Pod tree for memory work: 33912 /workspace/cb_mem = cb_stepd hard links + laptop pipeline (HEAD + S1b). Tests 52 + 9 skip
  (ROYALE_RUNTIME=fin15-linux needed for test_memory_s1b); rl_royale --smoke PASS with memory (mem_x_s110) and without (x_s101).
