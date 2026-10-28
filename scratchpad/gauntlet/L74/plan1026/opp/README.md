# P2-OPP1: human-like opponent v0 (plan1026 Pillar 2) -- how to re-run

Code: `pipeline/model_gen.py` (GenModel options `timing`, `ability`, `deck_enc` + `n_decks`, `ctx_tokens`; `slot_nll`;
`DeckEncoder`; `add_memory(zero_init=False)`), `pipeline/train_gen.py` (`--opp-*`, `--memory`, `--init` -> `main_opp`).
Tests: `pipeline/tests/test_opp_model.py` (incl. the 8010d5a legacy fingerprint, `opp_identity.py`).

Re-run after a new crforge build (D1 / D2), pod 33308:
```bash
# 0. code copies: /workspace/opp/cb = the re-drive's code copy (driving), /workspace/opp/cbt = git archive of HEAD (training)
# 1. slot-row re-drive (wait_stride 10, play_window 0) + sidecars + memory tables; resumable per shard
bash cb/scratchpad/gauntlet/L74/plan1026/opp/run_slot.sh LIBDIR /workspace/opp/slot_NEW --chunk 250 --limit N --workers W
python cbt/.../opp/check_slot.py /workspace/opp/slot_NEW 5            # invariants: play_dt == wait_dt, grid holes, events
# 2. rows: training file (no-play slots 1/8, weight 8) and the level-A file (every slot, test split, same deck ids)
python cbt/.../opp/rows_to_npz.py --src slot_NEW --vocab cbt/.../opp/vocab_hf.json --hf-replays /workspace/hf_il_replay/data/replays --out hf_slot_NEW.npz
python cbt/.../opp/rows_to_npz.py --src slot_NEW --vocab ... --hf-replays ... --out hf_slot_NEW_test.npz --keep-wait 1 --only-split 2 --deck-map hf_slot_NEW.npz
# 3. pretrain (all heads + joint memory v2); curve_<tag>_s0.jsonl = held-out NLL every 2,500 steps
bash cbt/.../opp/run_pretrain.sh hf_slot_NEW.npz runs/NAME NAME 320 7 STEPS GPU
# 4. level A (THRESHOLDS.json v3, sha-checked)
python cbt/.../opp/level_a.py selftest
python cbt/.../opp/level_a.py --ckpt runs/NAME/opp_NAME_s0.pt --data hf_slot_NEW_test.npz --memory-tables hf_slot_NEW_test_memory.npz --split 2 --out A.json
```
Live split: `live_split.json` (frozen 2026-10-28 09:06 EDT, never rewritten; sealed = every log from 20261028_090648).

## STATUS (P2-OPP re-dispatch, account 2; updated 2026-10-28 18:25 UTC; keep current)
1. Pretrain run 2 FINISHED (40k steps, best held-out total 5.515 at step 40k, 11.2 M params, 2.0 h; ckpt
   `/workspace/opp/v0/m10/opp_m10_s0.pt` sha256 99c231bf...). Level A on HF test split 2 (1.95 M rows, 2,667 replays), THRESHOLDS
   v3 sha 0c42e914 (its A section == v4's, checked): `results/v0_m10_run2/level_a_hf_test.json` (run 1 = step 10k: `results/v0_m10_run1/`).

   | level A (a, measured) | threshold | run 1 (10k) | run 2 (40k) | pass |
   |---|---|---|---|---|
   | card top-1 agreement | >= 43.7% (human ceiling) | 54.9% | 62.2% | yes |
   | cell exact top-1 | >= 27.5% | 18.9% | 22.4% | no |
   | card / cell NLL | (O2b 0.531 / 3.05, other data) | 1.032 / 3.319 | 0.882 / 3.003 | - |
   | card / cell ECE | <= 1.0 pp, n >= 200k | 3.16 / 1.17 | 1.23 / 0.40 (n 115,665 / 136,966) | no (n) |
   | timing slot ECE | <= 0.5 pp | 1.25 | 0.20 | yes |
   | timing rescaled-gap KS | <= 0.02 (>= 5k gaps per archetype) | 0.128 | 0.045 (136,325 gaps pooled) | no |
   | ability press KS | <= 0.05 (>= 2k per hero) | 0.517 | 0.430 (1,755 gaps pooled) | no |
   | memory: late NLL gain real vs other match | > seed gap | 0.127 | 0.125 nats/row, match CI90 [0.109, 0.114] | seed gap not measured (1 seed) |
2. SIM decode `gate_decode='timing_head'` (decision_options.timing_slot_draw / timing_play_draw; e1_eval timing_cfg /
   timing_decide_batch / SelfPlaySide; test pipeline/tests/test_timing_head_decode.py, 8 tests). A timing-head checkpoint
   decodes only this way (by checkpoint content; every other model byte-identical). Needs `opp_sim` in the checkpoint:
   `python attach_sim.py --ckpt X.pt --data TRAIN_ROWS --out X_sim.pt` (band 1 hf_pol, mode 1, era 1; 211 deck ids).
   Seat: slot grid tick % 10 == 0, Bernoulli(h) then the tick j, card + cell drawn at T (cfg T = --opp-T; timing T = 1) from the
   observation AT slot + j, no action delay / look-ahead / anti-stall; slots held by crforge's 20-tick command delay are not
   choosable and their cost is off the elixir (smoke: refusals 6/23 -> 0/19 on the same seed).
   Pod copy for closed loop (33308): `/workspace/opp/cbs` = 32657's /workspace/score/cb (b84b440 tree, P2-SCORE's E4/iu40 rows)
   + pipeline/ of this commit; icebow/data -> /workspace/d2/cb/icebow/data (CLXIII 8d328a43, GEN 05db85a0, E4 430faaee == 32657);
   crforge a677e080 plain copied to /workspace/crforge_main/a677e080/plain (SHA256SUMS OK); tables 16.402.22 identical.
   Opponent: `/workspace/opp/cbs/opp_ckpt/opp_m10_s0_sim.pt` (sha256 88f8bc16...). Smokes: `bash /workspace/opp/smoke.sh CKPT OUT SEEDS T`.
   18:41 UTC: the 33308 CONTAINER RESTARTED (uptime reset; every process on it died, other workers' too: P4 gate gap workers,
   P2-SCORE allref.py, a d2tt gap run). cgroup memory usage was 117.97 GB of 125 GB at 18:30 (incl. page cache; Codex poll);
   my load then = 24 closed-loop workers (~1.2 GB RSS each, measured after the restart: 12 workers = 15.0 GB) + 2 rl smokes.
   Whether my load tipped it is (b) untested. Relaunched at 12 workers 18:42 UTC; smokes relaunched (old logs *_killed.log).
   Level B rows RUNNING (33308, since 18:42 UTC, 12 workers): `/workspace/opp/score/rows/v0m10/` (driver log /workspace/opp/score/v0m10.out),
   CLXIII vs v0 at T 1, crforge a677e080, G2 OFF (same as P2-SCORE's E4 / iu40 rows), seeds 741200 742000 (paired with them), 24 workers.
   Restart (resumable per 480-game block): `cd /workspace/opp/score && (CB=/workspace/opp/cbs LIB=/workspace/crforge_main/a677e080/plain OPP_CKPT=opp_ckpt/opp_m10_s0_sim.pt OPP_T=1.0 WORKERS=12 setsid nohup bash /workspace/opp/cbs/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh v0m10 /workspace/opp/score/rows/v0m10 741200 742000 >> /workspace/opp/score/v0m10.out 2>&1 < /dev/null &)` (24 workers preceded the container restart)
   Score (laptop, after fetching the rows to humanlike/rows/v0m10): `card.py score --name v0m10 --sim .../rows/v0m10 --no-d`.
   rl_royale --smoke before / after this change RUNNING (33308): trees /workspace/opp/cbs_base (6b13c25^) and /workspace/opp/cbs
   (6b13c25), logs /workspace/opp/logs/p2opp_smoke_{before,after}.log (`bash /workspace/opp/pod_rl_smoke.sh TREE RUN`); the W16
   batch / weight shas must be identical. NOTE: pushed BEFORE this smoke finished (COMMON asks for it before the push).
   Codex: `.foreman/scratch/a2/codex/P2OPP_1.md` (low): babysit both, fetch + score, tabulate.
3. NOT STARTED: live opponent-seat slot rows. Spec for the build (reuses opp_model/o1_records.py + slot_redrive.sidecar + rows_to_npz):
   blocks from live_split.json by log NAME before any read (the sealed block is never opened; live_table.main reads every graded log,
   so do not call it); o1_records.build with FRAME_EVERY 2 (its counter miss was the 8-tick cadence) and --spell-targets; the
   reader's frame ticks are on ONE parity per match (e.g. 151, 153, ...), never on tick % 10 == 0, so the live slot grid = the
   frames at (tick - phase) % 10 == 0; opponent play tick = first sighting - (crforge 20 + detector lag), the lag measured on OUR
   seat (tap tick -> first public sighting) so labels use the HF act-tick convention (a, `live_lag.py`, 150 logs per block: decided
   play -> confirmed spawn p50 26 / 24 ticks train / calibration, modes 24-26, a second mode at 42-44 = a re-tap; = our ~6-tick tap
   + crforge's 20 + detection, so an opponent's act tick ~ first sighting - 20, to refine per frame parity); ctx_band 4/5/6 = live L/M/R (trophies / mode),
   era 2; deck ids via --deck-map of the HF rows; the 99% self-check on OUR seat = o1_finalize's check on the new records (O1 missed it
   on the public opponent-elixir counter, 93.8 / 96.2%, and on train-era unit counts, 96.8%). Then `train_gen --init opp_m10_s0.pt`
   on the TRAIN block (+ 20% HF share, lr 1e-5..3e-5, stop on a time-ordered tail of the train block), level A on the calibration block.

## STATUS history (P2-OPP1, updated 2026-10-28 ~13:57 EDT pod clock)
Done + pushed: step 1 model / trainer options + tests (70cd720); live split frozen (0bc4874); slot re-drive, rows_to_npz,
level_a (3c1bcdd, 27988a7, + spool converter).
Running (pod 33308, root@157.157.221.29 -p 33308):
- slot re-drive `/workspace/opp/slot_bec5811a` (log `/workspace/opp/slot_bec5811a.log`, 241 shards = 60k HF replays,
  14 workers, nice 10). Restart (resumable per shard):
  `cd /workspace/opp && setsid nohup bash cb/scratchpad/gauntlet/L74/plan1026/opp/run_slot.sh /workspace/redrive/rd_lib_bec5811a /workspace/opp/slot_bec5811a --chunk 250 --limit 60000 --workers 14 > slot_bec5811a.log 2>&1 &`
- v0 rows `/workspace/opp/v0/hf_slot_v0.npz` (+ `_memory.npz`) from the shards finished at launch (log v0/rows_to_npz.log).
  Code copies: `/workspace/opp/cb` (driving, = pass-1 copy), `/workspace/opp/cbt` (training, git archive + opp/ + humanlike/).
  The 33308 container limit is 125 GB (others use ~80 GB): the in-memory converter was OOM-killed once; it now spools to disk.
Running: v0 pretrain on 33308 GPU1 (log /workspace/opp/v0/m10/train.log, curve v0/m10/curve_m10_s0.jsonl), data = the EXTRACTED dir
/workspace/opp/v0/hf_slot_v0 (6,754,230 rows, 36,727 replays from 168 shards; the 26.7 GB npz was deleted: disk hit 98%).
Restart (fresh; no mid-run resume): `bash cbt/.../opp/run_pretrain.sh /workspace/opp/v0/hf_slot_v0 /workspace/opp/v0/m10 m10 320 7 40000 1`
(11.2 M params, ~1.45k rows/s measured), then the level-A test file + level_a.py on HF split 2.
Not started (need their own tickets): live slot rows for opponent seats (step 3), SIM timing-head decoder + level B (step 4).
- 14:40 update: slot re-drive FINISHED: 60,102 replays (A 18,062 / B 34,482 / unusable 7,558), 41.5 M rows, 241 shards.
  v0 trains on the first 168 shards. Pretrain speed on the loaded pod: 3.7 steps/s (40k steps ~3 h).
  Level-A test file building: `/workspace/opp/v0/hf_slot_v0_test.npz` (all 241 shards, split 2, every slot; log v0/rows_test.log).
  Then: `python cbt/.../opp/level_a.py --ckpt v0/m10/opp_m10_s0.pt --data v0/hf_slot_v0_test.npz --memory-tables v0/hf_slot_v0_test_memory.npz --split 2 --out v0/m10/level_a_hf_test.json`
- 15:20 UTC: pretrain run 1 was OOM-KILLED at step ~10,000 (container oom_kill 2 -> 3, 14:55 UTC; the container is
  shared, limit 125 GB). Kept: `/workspace/opp/v0/m10_run1/` (best = step 10,000, held-out total 6.064; curve copied to
  results/v0_m10_run1/). Run 2 relaunched from scratch, same command (`v0/m10/`, log v0/m10/train.log). main_opp has
  no mid-run resume: an OOM means a fresh restart (or --init from the last checkpoint with a new schedule).
  Level-A test rows are the EXTRACTED dir `/workspace/opp/v0/hf_slot_v0_test` (1,950,054 rows, 2,667 split-2 replays).
- STOP (account switch, ~16:05 UTC). State:
  * RUNNING on 33308: pretrain run 2, PID 96607, GPU1, `/workspace/opp/v0/m10/` (step 10,000 of 40,000 reached, ~4.8 steps/s,
    ~1.8 h left; best checkpoint opp_m10_s0.pt written at each better held-out total). If it dies: restart from scratch with
    `cd /workspace/opp && setsid nohup bash cbt/scratchpad/gauntlet/L74/plan1026/opp/run_pretrain.sh /workspace/opp/v0/hf_slot_v0 /workspace/opp/v0/m10 m10 320 7 40000 1 > v0/m10/train.log 2>&1 &`
  * RUNNING on 33308: level A on run 1's step-10k checkpoint, PID 112745, GPU1, -> `v0/m10_run1/level_a_hf_test.json`
    (first attempt hit CUDA OOM: fixed by streaming batches). Re-run command = the README step 4 with --data v0/hf_slot_v0_test.
  * NEXT: when run 2 finishes, level_a.py on v0/m10/opp_m10_s0.pt; copy curve + level A json to results/; then the
    split tickets: (3) live slot rows for opponent seats (2-tick detection, 10-tick grid, cycle-rule hand, >= 99% self-check)
    + fine-tune with --init on the frozen train block, level A on the calibration block; (4) SIM timing-head decoder
    (decide every 10 ticks, Bernoulli(h), tick-in-slot) + level B vs CLXIII in crforge.
