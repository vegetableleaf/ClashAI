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
