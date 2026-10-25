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

## 10-25 evening (17:40Z on)
- D1 deny opponent cfg CHECKED: no hazard keys (only a comment mentions it); gate_decode defaults to 'threshold' in
  decision_options.py, so the opponents' live stack has no forced play. D1 s74 on 33458 (u5 at 17:40Z, ~4 min / update).
- D1 s75 (replication seed, only `seed` differs) launched on 33522 17:5xZ from /workspace/cb_mem (= cb_stepd + 33458's cb_mem
  pipeline + D1 inputs relayed via the laptop); rl_royale --smoke PASS first. 33522 had been idle since its CLXIII gate queue
  finished 16:20Z (rows in /workspace/pushcal/ev/g48_succ48_o_s91_u0075_{e4,cal}).
- S3 step-0 identity on GPU: memory-vs-base 5.72e-6 = base-vs-base 5.72e-6 at max |out| 39.7 (fp32 GPU rounding, 1-2 ulp).
  Check made relative (1e-6 x max |out|) and both numbers logged; the exact-0 identity stays the CPU test.
- Per-card X-Bow counters, pro tables (xbow_cards.py -> xbow_cards_pro.out): 8,874 resolved own reach X-Bows, lock 0.507;
  unanswered 0.606. Lowest lock when ANSWERED by (n >= 60): E-Giant 0.16, Goblinstein 0.23, Giant 0.24, PEKKA 0.26,
  Giant Skeleton 0.28, Ice Golem 0.33, Ice Spirit 0.35, Bowler 0.36 (tanking the X-Bow / counter-push). DECK view (opponent
  played the card at any time; not causal): Goblinstein 0.36, Zappies 0.37, Archers 0.38 ... Lava 0.74, Skeleton Dragons 0.69,
  Balloon 0.65 (air beatdown = X-Bow locks). Pro X-Bow players, not our bot: a prior, not the bot's own rates.
- OWNER APPROVED S1c (10-25 ~18:20Z): per-card counter priors, cycle / counter-ready, king-activated, damage margin + trend,
  lock-likelihood head (pro + live X-Bow outcomes, frozen input, logged live); S3 then on the extended inputs; S4 pool D1 +
  I u40 cal + W18 R3 with fast-cycle counter decks; Tornado / king-activation parity, then a redirect-credit RL arm of its own;
  gate metrics (attempts vs score, Rocket cycling vs OT margin, behind > 2,000 -> seeks a lock, king activation / redirect vs pros).
  Dispatched: worker A = memory v2 + lock head; worker B = Tornado / king parity; worker C = gate_metrics.py + pro rates.
- S3 smoke (100 steps, GPU 1 of 33912): PASS. 104 frozen tensors unchanged; val loss 5.429 -> 5.003, cell top-1 0.171 -> 0.199,
  card top-1 0.576 -> 0.573, gate bal-acc 0.707 -> 0.682 (100 steps, lr warm-up only: no verdict). 0.165 s / step.
- Target-leak check (leak_check.py, 200,000 pro play rows): 0 rows with a visible own play at tick >= the row tick; the newest
  visible own play is >= 1 tick old (median 86). The cell gain is not the target leaking.
- S3 v1 CONTROL launched 18:25Z (2 epochs, bf16, /workspace/s3/v1ctrl on 33912): the baseline the v2 (S1c) S3 is measured
  against (one change per experiment); not the S3 that feeds S5.
- Live per-card X-Bow view (xbow_arch.py --live CLX_PARITY --cards 15 -> xbow_cards_live.out): answered by Mega Knight 0.13
  (n 38), Knight 0.45, Valkyrie 0.47, Tesla 0.48; unanswered 0.74 (n 223). Deck view lowest: Barbarian Barrel 0.34 (n 89),
  Tombstone 0.35, Poison 0.35, Tornado 0.38, Bowler 0.38 (small n, whole-match reveal).
- Pool check (pool_counters.py): decks_live_train_beat3 has 112 / 895 fast (avg <= 3.2) decks with >= 1 X-Bow counter =
  9.9% of training weight (>= 2 counters: 7.0%), at live frequency by construction (weights = live sides).
- S1c DONE (70eac89). S3 v1 control FINAL: val loss 5.471 -> 4.720, card +3.1 pp, cell +3.1 pp, gate bal-acc +0.9 pp; probes
  toward pros (X-Bow after >= 2 fails 12.2 -> 9.4%, pro 8.6; Rocket 1.1 -> 5.7%, pro 8.6). Memory zeroed = worse than CLXIII
  (gate 64.1%): the adapter now relies on memory. RL proagree scores memory models with an EMPTY memory (TODO: pass tables).
- S3 v2 (S1c inputs) launched 19:2xZ on 33912 GPU 1 (/workspace/s3/v2).
- x_s101 / x_s102 (no-memory controls, tower_crown + xbow cost): BOTH drift-tripped (x101 at u50, x102 at u75): seconds at full
  13.5 -> 30.3 / 32.2 s, first play 12.7 -> 28.7 / 31.0 s, win -5.0 / -4.1 pp vs u0. Verdict (a): that recipe re-learns the
  leak; it is NOT used for the memory arms.
- S5 pair launched 19:30Z, CLXIII's own recipe (succ48_o_s91), seed 105, 100 updates, drift_test (CB override -> cb_mem):
  mem_o_s105 (33912, init = S3 v1 adapter mem_best, memory v1) vs ctrl_o_s105 (33569, init = CLXIII raw). ONE change: memory.
  Graft check: graft_generic keeps all 36 memory tensors; eval_gen loads it as memory v1.
