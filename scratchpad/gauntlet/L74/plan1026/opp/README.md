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

## STATUS (P2-OPP2, account 2; updated 2026-10-29 06:30 UTC; keep current)
RESULTS 10-29 (a; THRESHOLDS v6 26568167; level B = CLXIII D3 vs the opponent at T 1, fe364ceb, G2 on, seeds 741200 742000
742800 743600; files results/{v0fix,v1_s0,ft_s0}/):

| | v0fix (v0 + decode fixes) | v1 s0 (241 shards, CellRefine, 100k) | ft_s0 (v1 s0 + live train + 20% HF) | pilot bar |
|---|---|---|---|---|
| level A HF test: card / cell top-1 | 62.2 / 22.4% | 65.3 / 27.40% (cell bar 27.5) | - | |
| level A HF: timing KS / ability KS | 0.045 / 0.43 | 0.0145 (pass) / 0.39 | - | |
| level A live_cal: card / cell / timing KS | - | 54.6 / 21.5% / 0.117 | 56.0 / 24.0% / 0.043 | |
| live_cal hazard vs rate / slot ECE | - | 0.107 vs 0.080 / 2.67 pp | 0.086 vs 0.080 / 0.61 pp | |
| B-live RMS d (1,920 / 1,919 / 1,920 games) | 0.33 | 0.34 | 0.31 | <= 0.20 (stretch 0.05) |
| C-live AUC | 0.984 | 0.977 | 0.974 | <= 0.60 |
| lock / zero-lock / P(lock / fail) (live .47/.12/.36) | .75/.00/.70 | .70/.01/.64 | .75/.00/.68 | v6 margins |
| CLXIII SIM win | 88.3% | 82.2% | 88.4% | 30-50% |

Fine-tune: /workspace/opp/live/run_ft.sh (bs 128, lr 2e-5, 12k steps, held-out = live split 1 tail), data mix_rows.py ->
/workspace/opp/live/mix_train (398,096 + 46,935 live, 111,379 HF = 20.0%); best 11k total 5.206; live rows carry no ability
labels (w_ab 0). Chain /workspace/opp/live/after_ft.sh: _sim.pt (band 6 / mode 1 / era 2 = live Ranked) -> level A -> smoke ->
level B ftR (rows /workspace/opp/score/rows/ftR, log /workspace/opp/score/ftR.out; resumable: rerun its last line).
crforge fe364ceb crashed one v1s0 worker (UnsupportedOperationException target_is_ground on PrincessTower_1_2): that block's
D3/matches.jsonl is empty; merge the worker files (cat D3/0*/matches.jsonl) before tab_closed.py. card.py needs icebow/.venv python.
Seed 1 (PID 5431, run_s1) running, ETA ~10:30 UTC. Nothing else of mine runs on 33903 (level B ftR DONE 06:13).
Reading (a): every column FAILS the pilot bar. The fine-tune fixes live TIMING (live_cal KS 0.117 -> 0.043) and nudges style
(RMS 0.34 -> 0.31) but not strength (CLXIII 88.4%) or siege defence (lock 0.75 vs 0.47): imitation alone leaves the opponent far
weaker than live humans at stopping X-Bow locks. Next lever = strength calibration (V1-STRENGTH / LOOP-INT2), base checkpoint
/workspace/opp/live/ft_s0/opp_ft_s0_R_sim.pt (closest style + live timing); v1 s0 _sim.pt is the stronger one (82.2%).

## STATUS history (P2-OPP2, 2026-10-28 22:20 UTC)
RUNNING on 33903 (22:20 UTC; ssh -p 33903 root@157.157.221.29):
- v1 pretrain seed 0, PID 4608, /workspace/opp/v1/run_s0/ (restart command below). Measured 10k steps in ~38 min (~4.4 steps/s) ->
  100k ~04:00 UTC 10-29. Held-out at 10k (own held-out set, NOT v0's: b-level comparison only): total 6.109 (v0 6.061), cell
  3.319 (3.325), cell top-1 19.1% (18.6%), card top-1 52.3% (54.4%); the one-cycle peak is later (5k vs 2k steps).
- seed 1 queued: /workspace/opp/v1/after_s0.sh (PID 5431) waits for PID 4608, then runs seed 1 -> /workspace/opp/v1/run_s1/
  (log /workspace/opp/v1/run_s1.train.log), ETA ~10:30 UTC. Not in parallel: seed 0 holds 12.9 GB GPU, no mid-run resume.
- level B of v0 WITH this commit's decode fixes (baseline for v1, same config v1 will get): run_closed.sh PID 5885, CLXIII vs
  opp_m10_s0_sim.pt T 1, fe364ceb, G2 ON (f6c2ae0), 32 workers, seeds 741200 742000 742800 743600 (4 x 480 = 1,920 games),
  rows /workspace/opp/score/rows/v0fix/, driver log /workspace/opp/score/v0fix.out, ETA ~07:30 UTC. Restart (resumable per block):
  `cd /workspace/opp/score && (CB=/workspace/opp/cb LIB=/workspace/crforge_main/fe364ceb/plain OPP_CKPT=/workspace/opp/cbs/opp_ckpt/opp_m10_s0_sim.pt OPP_T=1.0 WORKERS=32 G2_ON=on setsid nohup bash /workspace/opp/cb/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh v0fix /workspace/opp/score/rows/v0fix 741200 742000 742800 743600 >> /workspace/opp/score/v0fix.out 2>&1 < /dev/null &)`
  Score: fetch rows to opp_model/humanlike/rows/v0fix, `card.py score --name v0fix --sim .../rows/v0fix --no-d` under THRESHOLDS v6.
Codex P2OPP2_3 (medium, dispatched 22:30 UTC; ticket .foreman/scratch/a2/codex/P2OPP2_3.md, log P2OPP2_3.log, events
  P2OPP2_3.jsonl): babysits all of the above, scores v0fix under v6, and on seed 0's end runs attach_sim + level A + a v1 smoke +
  level B v1s0 (same 4 seeds, G2 on) + card.py v6; seed 1 level A. Its numbers are CLAIMS until checked here.
NEXT (this seat): seed 0 done -> attach_sim.py (--data /workspace/opp/v1/hf_slot_v1) -> level_a.py on hf_slot_v1_test (+ its
  _memory.npz, split 2) -> level B v1 (same run_closed command, OPP_CKPT = the v1 _sim.pt, NAME v1s0) -> card.py v6; seed 1 ->
  level A + memory seed gap. Pilot bar (lead 10-28): v6 B-live RMS d <= 0.20, siege facts inside v6 margins, CLXIII SIM win 30-50%.
Pod: 33903 (1x 4090, 125 GB cgroup, 120 GB /workspace) = ALL my GPU + closed-loop work (lead 10-28). 33308 GPU1 released
(nothing of mine ran there after 20:00 UTC; its container restarted again ~20:53 UTC, not my load).
Step 1 (CPU-side decode gaps; e1_eval timing hunks + tests; pod smoke = see below):
- (a) v0 level B refusals (960 games, 27,778 opponent plays, 1,531 refused = 5.5%): 1,303 in a match's last 80 ticks with 0
  accepted there (crforge refuses every play once the match is decided; diag on 33308 diag1: reason game_over, incl. ALL three
  hero Mega Minion refusals at 4.9-6.7 elixir = they were game_over, not a Mega Minion bug); Mirror 70 / 110 refused
  not_enough_elixir (crforge LadderMatch.mirrorItem bytecode: cost = min(Mirror + repeated card, max elixir), the repeated card =
  lastPlayedCopy; our table had Mirror's catalogue cost); the remaining ~160 spread over cards at 3-10% (cause not split; b).
- Fixes (e1_eval, timing-head seats only; every other model unchanged): th_costs (Mirror = last issued non-Mirror card + 1,
  cap 10, unplayable before any card), th_decided (the engine's own check_deploy says GAME_OVER -> no play, no draw),
  th_ability (the learned ability head: at each slot start with a visible own ability controller (rows' ab_ok) Bernoulli(h) +
  tick j from its own stream, a READY button is queued j ticks on; SelfPlaySide.prepare keeps the env's v2 rule off that seat).
  Tests: test_timing_head_decode.py TestEngineGaps (3; the GAME_OVER one needs royalegym = pod only).
- Tick-in-slot head (a): it is NOT broken. HF slot labels (1,887,461 play slots, v0 rows): offset 0 never, 1 = 26.7%, 2-8 ~10%
  each, 9 = 3.8%; that marginal's entropy = 2.08 nats = the head's held-out 2.0795 (ln 8 is a coincidence): the head learned the
  marginal and there is no further within-slot signal. The offset-1 pile-up (plays at offsets 0 and ~60% of 9 moved to 1) is a
  re-drive timing artefact (shape a, cause b: the pass-1 driver's frame / command order); the decode reproduces it (+<= 0.1 s).
Step 3 code: train_gen --opp-cell-refine C,LAYERS (fresh opp model gets CellRefine; absent = v0 build); rows_to_npz --out
  without .npz = EXTRACTED dir written directly (no npz + unzip copies; checked equal to the npz path on a synthetic spool).
Step 2 (live opponent-seat rows) NOT STARTED; findings for the build (a): opp_model/out/live_matches.jsonl.gz is STALE (3,372
  rows, newest 20261019_235402, no mode field; 1,087 icebow >= 12k since 10-15 17:26 in the train block) -> the builder must list
  logs BY NAME from L68/live_reader inside live_split.json's blocks (train: 20261015_172600 <= ts < 20261025_000000; calibration:
  20261025_000000 <= ts < 20261028_090648; never open ts >= sealed_from) and call live_table.parse_log per listed log only
  (never live_table.main). Bands (REPORT_opponents 1.3): live_L = 12.0-12.9k trophies, live_M = 13k+, live_R = Ranked.
  Plan: plan1026/opp/build_live.py = o1_records.build with FRAME_EVERY 2 + SPELL_TARGETS, opponent log tick = first sighting
  - 20 (play frame = last frame <= that tick), record ticks shifted by -phase (phase = first frame tick % 10; <= 0.45 s clock
  shift, ponytail ceiling) so rows_to_npz's tick % 10 grid is the frame grid; dataset_gen.build(wait_stride 10, play_window 0)
  + slot_redrive.sidecar + memory tables per shard; rows_to_npz with ctx_band 4/5/6, era 2, --deck-map of the HF rows;
  o1_finalize self-check on OUR seat >= 99% before any training.
  Mode (Ranked vs ladder) is NOT in live_table.parse_log; Ranked lists today = clx_ranked/rows.json (static, 233 logs) and
  P2-SCORE's v5 / v6 all-matches human reference (HUMANLIKE.md 11.1-11.2): take the mode from the v6 reference builder (b).
Step 1 pod smoke (33903, crforge fe364ceb, v0 opp_m10_s0_sim.pt vs CLXIII, seeds 741200-741205, DIAG=1; trees
/workspace/opp/cb_base = HEAD 39901d6, /workspace/opp/cb = this change; logs /workspace/opp/logs/smoke_cb*.log) (a):
  base: 15 / 157 opponent plays refused (Mirror 7 of 8 not_enough_elixir, game_over 7, Witch 1); new: 0 / 174 refused, Mirror 2
  played / 0 refused. Ability: the first new run pressed NOTHING for the opponent (heads_t dropped ab_hazard / ab_tick, and the
  env rule was already off for the seat) -> fixed in GenPolicy.heads_t; re-run (seeds 741201 / 02 / 04, the 3 hero decks): 1
  press per match (Valkyrie, Mega Minion, Mini P.E.K.K.A), 262 of 1,056 slot starts with a visible controller, mean h 0.013
  (max 0.108); the env's v2 rule pressed 1-2 per match on the same decks. 1 Witch refusal at 5.85 elixir left (cause b).
  test_opp_model's legacy fingerprint FAILS on the pod for HEAD too (platform floats; passes on the laptop) = not this change.
v1 (33903; code copy /workspace/opp/cb = HEAD 39901d6 + this commit's files, icebow/data -> /workspace/icebow_data, venv
/workspace/venvf16 built from PyPI + fin16 wheel b5c35101 + JPype1 1.7.1 + pyarrow 26; crforge /workspace/crforge_main/fe364ceb):
- rows (a): ALL 241 shards -> /workspace/opp/v1/hf_slot_v1 (EXTRACTED dir, 9,693,018 rows = 8,716,121 train / 488,468 held-out
  / 488,429 test, 52,544 replays, 2,711,442 play slots, 303 deck ids; v0: 6.75 M rows, 168 shards, 211 ids; 526 s) + _memory.npz;
  level-A test dir hf_slot_v1_test (split 2, every slot, --deck-map hf_slot_v1). Rebuild: `bash /workspace/opp/v1/build_rows.sh`.
- RUNNING: pretrain seed 0 = v0's recipe + CellRefine(32, 4), 100k steps (v0 40k), d 320 x 7, bs 256, lr 3e-4 one-cycle;
  /workspace/opp/v1/run_s0/{train.log, curve_v1_s0.jsonl, opp_v1_s0.pt}; 11,290,371 params; GPU 12.9 GB, util 88%.
  Restart (fresh; no mid-run resume): `cd /workspace/opp && (OPP_CODE=/workspace/opp/cb CELL_REFINE=32,4 setsid nohup bash /workspace/opp/cb/scratchpad/gauntlet/L74/plan1026/opp/run_pretrain.sh /workspace/opp/v1/hf_slot_v1 /workspace/opp/v1/run_s0 v1 320 7 100000 0 0 > /workspace/opp/v1/run_s0/train.log 2>&1 < /dev/null &)`
  Seed 1 = the same with run_s1 and last arg 1 (after seed 0, or alongside if the GPU allows).
- Then: attach_sim.py (opp_sim, deck ids from hf_slot_v1) -> level A on hf_slot_v1_test (same scorer as v0) -> level B on fe364ceb,
  >= 4 x 480-game blocks (>= 1,900 games), card.py under THRESHOLDS v6 (sha 26568167; lead 10-28).
Codex: P2OPP2_1 (setup through the laptop, low) STOPPED (relay ~2 MB/s); P2OPP2_2 (venv from PyPI + copies, low) did the venv +
  crforge + tables (checked: versions, CUDA, wheel sha, crforge SHA256SUMS + manifest equal) and was STOPPED during the data copy;
  the data went pod to pod by rsync with ssh agent forwarding (lead 10-28), slot shards checked (1,206 files, 4,460,796,283 bytes,
  slot-sidecar md5 equal both sides). Logs .foreman/scratch/a2/codex/P2OPP2_{1,2}.log.
Split (owner 10-28 ~19:30): step 2 (live rows) -> V1-LIVEROWS, strength calibration -> V1-STRENGTH; this seat = decoder + model.

## STATUS history (P2-OPP re-dispatch, account 2; 2026-10-28 20:20 UTC)
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
   Level B rows (33308, 18:42-19:57 UTC, 12 workers; DONE): `/workspace/opp/score/rows/v0m10/` (driver log /workspace/opp/score/v0m10.out),
   CLXIII vs v0 at T 1, crforge a677e080, G2 OFF (same as P2-SCORE's E4 / iu40 rows), seeds 741200 742000 (paired with them), 24 workers.
   Restart (resumable per 480-game block): `cd /workspace/opp/score && (CB=/workspace/opp/cbs LIB=/workspace/crforge_main/a677e080/plain OPP_CKPT=opp_ckpt/opp_m10_s0_sim.pt OPP_T=1.0 WORKERS=12 setsid nohup bash /workspace/opp/cbs/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh v0m10 /workspace/opp/score/rows/v0m10 741200 742000 >> /workspace/opp/score/v0m10.out 2>&1 < /dev/null &)` (24 workers preceded the container restart)
   Score (laptop, after fetching the rows to humanlike/rows/v0m10): `card.py score --name v0m10 --sim .../rows/v0m10 --no-d`.
   rl_royale --smoke before / after this change (33308; DONE): trees /workspace/opp/cbs_base (6b13c25^) and /workspace/opp/cbs
   (6b13c25), logs /workspace/opp/logs/p2opp_smoke_{before,after}.log (`bash /workspace/opp/pod_rl_smoke.sh TREE RUN`); the W16
   batch / weight shas must be identical. NOTE: pushed BEFORE this smoke finished (COMMON asks for it before the push). RESULT (a): on a677e080 BOTH trees fail the same way (ActorCrash: crforge giantbuffer_enchanting_buff on LittlePrince, logs *_a677.log); on fe364ceb (lead 10-28: the new default lib; facade c003fc74 compiled into /workspace/opp/score/facade_fe364ceb; `LIB=... FAC=... pod_rl_smoke.sh`) BOTH SMOKE PASS, config sha b5e2a2bbafef, W16 u0000 batch 8377367c / weights 3e07cff4, u0001 batch 30c3c03f / weights 542bd835 identical, w16_batch / w16_matches u0000-u0001 files byte-identical (logs p2opp_fe_{before,after}.log). Level B v0m10 stays on a677e080 (started there; pairs with the E4 / iu40 rows); new closed-loop runs go on fe364ceb.
   Codex: `.foreman/scratch/a2/codex/P2OPP_1.md` (low): babysit both, fetch + score, tabulate -> BLOCKED after 697 s (33308 ssh
   timed out = the container restart); the rest was done by hand.
   LEVEL B DONE (19:57 UTC, 960 games, 480 + 480; `results/v0_m10_run2/level_b_card_v0m10.txt`, `level_b_tab.json`,
   `level_b_ENGINE.json`). Scored under THRESHOLDS **v5** (sha 438a7692, registered by P2-SCORE before this score; B-live / C-live
   on the all-matches recency-weighted human reference, 4,752 matches, n_eff 3,417), `--no-d` (sealed block never opened). (a):

   | item | live humans | v0 (960) | E4 (1,913; same v5 reference, rescored here) |
   |---|---|---|---|
   | B-live RMS d, 25 stats (limit 0.10) | - | **0.34** (13 TOST fails; model games >= 1,900: no) | 0.60 (19 fails) |
   | worst stats | | gap_p10 -0.74, pocket_share -0.72, split_rate +0.59, spell_depth +0.57, react_s -0.53 | react_lift +1.55, react_3s +1.25, react_s -1.06 |
   | C-live AUC (limit 0.56) | | 0.978 [0.972, 0.985] | 0.984 [0.980, 0.988] |
   | X-Bow lock rate | 0.47 | 0.76 (+0.29) | 0.57 (+0.10) |
   | zero-lock share | 0.12 | 0.01 | 0.03 |
   | P(lock / prev failed) | 0.36 | 0.68 | - |
   | CLXIII win (live Ranked ~48%) | | 89.1% (855/960), OT 31.5% | - |
   | opponent plays / min, refused | | 8.84, 5.5% | - |

   Reading: v0 nearly halves E4's style distance on the same reference (0.34 vs 0.60) but is 3.4x the limit, trivially told apart
   (C 0.978), and far weaker than humans (CLXIII 89% vs ~48% live; it lets X-Bows lock 76% vs 47%). VERDICT FAIL (A not given to
   card.py: level A is item 1 above).
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
4. NEXT (no-discard: each is an iteration, nothing dropped), in order:
   a. Data + schedule: pretrain on ALL 241 shards (60,102 replays; v0 used 168 = 36,727) with a longer schedule; the held-out curve
      still fell at 40k with lr annealed to 0 (5.5455 -> 5.5152 over the last 7.5k steps) (a). Plus seed 2 (memory seed gap).
   b. Cell head: v0 has NO CellRefine (REPORT section 2 specifies cell head + CellRefine); cell exact 22.4% vs ceiling 27.5% is the
      largest level-A gap (a); CellRefine closing it is (b) untested.
   c. Tick head: held-out tick NLL 2.0795 = ln 8 from step 2,500 on = uniform over the 8 occupied in-slot ticks: no within-slot
      signal learned (a). Harmless for decode (draws stay on the support) but the timing KS 0.045 is the hazard (rescaled mean 1.029,
      hazard mean 0.0772 vs rate 0.0752: ~3% over-prediction (a)) + this.
   d. Level-A sufficiency: card / cell ECE need n >= 200k decisions; the HF test split gives 115,665 / 136,966 even at 1.95 M rows,
      so ECE can only pass on split 1+2 or more replays: a scoring-size decision for P2-SCORE / the lead (c: cannot pass as defined).
   e. SIM decode gaps found (a, 4 diagnosed smoke games): Mirror refused 7x for not_enough_elixir (our cost table has Mirror's
      nominal cost, the engine charges last card + 1); hero Mega Minion refused at 4.9-6.7 elixir (cause unknown, b); a play at
      game end ('game_over'). Learned ability head is not decoded in the SIM (the env's v2 rule presses for the seat); ability KS 0.43.
   f. B-live sufficiency needs >= 1,900 model games: next v0 / v1 closed loop = 4 blocks on fe364ceb (lead 10-28) with a CLXIII-vs-E4
      fe364ceb baseline from P2-SCORE if a paired comparison is wanted; G2 on once the follow_ups tap fix lands.
   g. Strength (CLXIII 89% vs ~48% live) is the REPORT's calibration step (band token, then card / cell T, then fixed-lambda RL with
      frozen timing) and comes after B improves; the live fine-tune (step 3, bands 4/5/6) is the first lever on both.
   h. Style latent z: only if B3 (between-match spread) fails once the means are close; today B fails on means (RMS 0.34), so the
      B3 fail is not yet evidence for z (b).

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
