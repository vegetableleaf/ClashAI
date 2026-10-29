# OPP-LEARN-B: the P2 opponent model as the rl_royale LEARNER (strength calibration, REPORT_opponents 3 step 4.3)

Goal: RL the human-like opponent (timing-head GenModel, plan1026/opp checkpoints) for STRENGTH while it stays human-like:
a FIXED pull toward its own imitation init, timing + ability heads FROZEN, win-only reward, partners = the bot pool on our
deck + the human model vs itself on census deck pairs. Part A (fast-loop timing seats) = OPP-LEARN-A; part C (routing this
through the fast loop) comes after both.

## What was built (all opt-in; a gate model / absent key = byte-identical)
| piece | where | how it is switched on |
|---|---|---|
| (1) learner-seat recording | e1_eval `th_record` (called by `timing_decide_batch` under cfg record), `timing_cfg` (record allowed only with `th_learner`), `_record` / `_traj_arrays` (deck_gid / ctx_* ids = `opp_row_keys`, labels th_j / th_ab) | rl_royale `actor_cfg` sets `th_learner` on rollout cfgs when the init is a timing-head model |
| rows | every slot-start / drawn-tick decision is a traj row; lp_card / lp_cell on play rows (mask = the seat's real allowed slots after held plays / Mirror cost, float64 of the float32 heads at T); lp_gate 0, gate_sampled False everywhere; th_j = tick-in-slot drawn at a slot start (-1 none, -2 = the play row at a drawn tick, -3 game over); th_ab = tick an ability press was queued (-1 none); p_gate = sigmoid(hazard) | - |
| (2) `freeze_heads: [timing, ability]` | rl_royale `freeze_heads` (FREEZE_HEADS = timing_head.* / ability_head.*): requires_grad False -> no gradient, Adam never steps them; the smoke checks them bit-identical | config key; absent / null = nothing (hash unchanged) |
| (3) card / cell-only PPO + KL | `policy_terms`: a gate-less model gets x = 0 (never gate-sampled), so lp_gate = 0, KL_gate = 0, gate entropy None; the loss is card / cell PPO + KL on play rows. No new term: the existing loss on these rows IS card / cell only | automatic for a timing-head init |
| (4) fixed pull to the init | NO new key: `beta0 = beta_min = beta_max = lambda` (adapt_beta clamps to lambda every update) with `kl_ref_refresh_every` absent (ref = the frozen init forever). Note: Guards' "beta at clamp" KL stop is then always armed = a plain KL_cell > kl_cell_stop for stop_consecutive updates stop | config |
| (5) opponent-architecture learner | Learner: `self.th` (init has opp.timing) -> `_load_net` via model_gen.load_model (timing / ability heads, deck encoder, ctx tokens, memory); saves + league snapshots carry opp / opp_sim / memory (`opp_learner_meta`); actors rebuild it (`base["opp_init"]`) with GenPolicy(opp_sim); `policy_terms` builds GenPolicy without opp_sim (heads_t only; rows carry the ids); startup / loop skip pro agreement + the ghost screen (both decode a gate model) | automatic; refuses: league off, decide_every != 10, no opp_sim, posture / ability_head / tau_phase / branch / kl_ref_gate / kl_ref_card / pipelining / cf_credit |
| partners | config only: `league_mix {init: 0.4, s1: 0.6}` + `league_specialist: CLXIII` (the s1 slot always plays icebow = the bot on our deck), `league_learner_icebow_share 0` (learner decks = census). A multi-bot pool on our decks needs a decks file the league can read: league_decks drops icebow by design, so `league_exploiters` cannot carry icebow today (b: use the s1 slot, or a follow-up key) | `learner/opp_learner_smoke.yaml` |

Advantage: `advantage: match_loo` (win-only, per-match LOO within the matchup's G repeats; no critic: the opponent's value
head is untrained). T = 1.0 (the imitation temperature; timing_decide_batch and policy_terms both read cfg T).

Known ceiling (ponytail, b, untested): the shared trunk trains, so the frozen heads' OUTPUTS (hazard, tick, ability
hazard) can drift with it even though their weights do not. Measure: the hazard on fixed recorded rows, u0 vs uN.

## Tests (laptop, a)
`icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_opp_learner.py` -> 6 passed:
recorded rows + labels + ctx ids on the fake self-play env; policy_terms recompute of lp_card / lp_cell < 1e-5 (lp_gate 0);
frozen heads grad None + bit-identical after 3 Adam steps while card_q trains (KL_card + KL_cell > 0, KL_gate 0);
adapt_beta fixed at lambda; freeze_heads absent / refusals; config_sha(absent) == config_sha(null); actor_cfg / timing_cfg
unchanged without the opp init. Existing: test_timing_head_decode + test_league 42 passed, 1 skipped, 2 failed -- the same
2 (TestSelfPlayCounters, x_bow vs x-bow names) fail on the unchanged tree too (a: pre-existing).

## OPP-LEARN-C (2026-10-29): bot-partner decode, frozen-head drift monitor, fast-loop learner seat, calibration

### STATUS (keep current)
- The rl_royale.py hunks were swept into LEARNER-SCALE2 daaecbf (identical to this patch; checked by diff); tests, producer /
  compare and the learner/ files are this commit. Lead 10-29: calibration learner on 33308 GPU1 only (RAM <= 30 GB, <= 40
  actors, ONE lambda run at a time: 0.1 first, then 0.03 / 0.3); never the 33903 GPU; bar scored on D3 + the sampled-decode
  number beside it; dry-run on v0 until P2-OPP2 reports v1.
- DONE (code; opt-in, absent = unchanged): (1) bot partner decode + icebow pool, (2) th_drift monitor, (3) fast-loop timing
  LEARNER seat. (4) v0 DRY RUNS (lead 10-29: settle lr / lambda / stop rule before v1), FAST LOOP on 33308 GPU1:
  - oplc_flv0_l01 DONE (lambda 0.1, lr 1e-5, E 64 x G 4, 30 updates 02:22-03:55 UTC, ~180 s per update, PSS 12.7 GB). Curve
    (a): learner/out/curve_oplc_flv0_l01.md (from train_log.jsonl by learner/curve.py). Win rate vs the bot (CLXIII, sampled
    decode, n ~160 per update) 16% at u0 -> 18-21% at u25-29 (noise ~3 pp); vs the frozen init 45% -> 55-71%; KL card / cell
    to the init 0.001 / 0.002 -> 0.026 / 0.033; plays/min 8.54 -> 8.82. Frozen-head drift GROWS with the KL: hazard mean p
    .1886 -> .2195 (+16% relative), mean |dp| 8e-3 -> 3.4e-2, max .19; ability hazard mean |dp| 2e-3.
  - D3 evals (a; CLXIII gap.py D3 = live's greedy stack, G2 on, seed block 741200 paired, 480 games; card.py v6 --no-c --no-d;
    learner/out/TABLE.md): v0fix (= u0) CLXIII 87.7% [84.5, 90.3], B RMS d 0.325, 14 z-fails, lock .75; u0010 87.1% [83.8,
    89.8], RMS 0.316, 12 z-fails, lock .75. u0020 / u0030: Codex OPP-LEARN-C_2 (running).
  - oplc_flv0_l01_lr3 RUNNING (lr 3e-5, else the same, 20 updates, started 03:57 UTC; log /workspace/oplc/logs/oplc_flv0_l01_lr3.log):
    does 3x lr buy strength faster than it buys drift? Its u0010 / u0020 D3 evals are in OPP-LEARN-C_2.
  - Reading (b): at lr 1e-5 the strength channel barely moves in 30 updates (D3 unchanged at u10; sampled-decode +3-5 pp by
    u25) while the frozen hazard drifts steadily: at this rate the human-likeness (timing) check, not the 30-50% bar, will
    stop a long run. Reaching CLXIII 30-50% from ~87% needs far more strength than 30 updates gave.
  Launch / restart (fresh RUN name or --resume):
  `cd /workspace/oplc && CB=/workspace/oplc/cb TABLES=/workspace/crforge_cache/tables/16.635.3 GPU=1 LOGS=/workspace/oplc/logs XMX=3g TMO=36000 FAST_ARGS="--producers 2 --matches 64 --threads 6 --devices cuda:0" setsid nohup bash fl_pod.sh fast RUN 100-121 scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib.yaml init=INIT beta0=L beta_min=L beta_max=L max_updates=N save_every=10 learner_device=cuda n_actors=1 < /dev/null > logs/RUN.out 2>&1 &`
  (n_actors=1: else rl_royale idles 48 actor processes = +30 GB). Evals: strip on 33308 (`learner/strip_ckpt.py`, 135 -> 45 MB),
  relay to 33903 /workspace/opplearnc/calib/ck/, `CB=/workspace/opp/cb WORKERS=15 CPUS=220-251 G2_ON=on OPP_T=1.0 OPP_CKPT=... bash
  /workspace/opp/cb/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh NAME /workspace/opplearnc/calib/rows/NAME 741200`
  (15 workers = 14.9 GB RSS), fetch to learner/rows/NAME, `card.py score --no-c --no-d --out learner/out/NAME`, `strength/tab.py
  learner/rows learner/out`.
  (a) production rl_royale path for comparison (run_calib.sh, 20 CPU actors): 1,173 s per update at PSS 30.6 GB (over the cap;
  stopped by PID after u0000); the fast loop on GPU1 = 180 s (6.5x). Same u0000 twice on GPU (repeatable); fast-on-cuda vs
  production-on-cuda compare (b) owed.
  v1: (P2-OPP2: seed 0 at step 62.5k of 100k at 00:50 UTC, then
  attach_sim + level A + level B v1s0 by Codex P2OPP2_3).
- Pod 33903 (CPUs 200-219, <= ~20 GB; GPU = P2-OPP2's): trees /workspace/opplearnc/cbc_base (HEAD c5383b3 pipeline over
  /workspace/opplearn/cb) and /workspace/opplearnc/cbc (+ this change + HEAD loop / speed dirs); chain /workspace/opplearnc/chainc.sh (= learner/chainc.sh);
  fast loop / compare wrapper /workspace/opplearnc/fl.sh (= learner/fl_pod.sh) (`fl.sh fast RUN CPUS CONFIG [rl args]`, `fl.sh cmp MSG OUT CPUS [compare
  args]`, CPU only); rl logs /workspace/opplearn/logs/oplc_*.log, fast-loop logs /workspace/opplearnc/logs/.
- Pod smokes (a, 33903 CPUs 200-219, crforge fe364ceb + tables 16.635.3, CPU learner):
  | run | tree / path | config (sha) | W16 u0000 batch / weights | W16 u0001 batch / weights | result |
  |---|---|---|---|---|---|
  | oplc_base1 | HEAD c5383b3, rl_royale | succ48_x_s101 (b5e2a2bbafef) | b43dd869 / 3e07cff4 | 70b4b263 / d9fd3a96 | SMOKE PASS |
  | oplc_new1 | + this change, rl_royale | succ48_x_s101 (b5e2a2bbafef) | b43dd869 / 3e07cff4 | 70b4b263 / d9fd3a96 | SMOKE PASS; w16_batch / w16_matches u0000-u0001 byte-identical to base1 (cmp) |
  | oplc_bot1 | + this change, rl_royale | opp_learner_bot_smoke (d7d470c17283), v0 init | cb89adf5 / b3eaf2ad | c3eee81d / 10d4a5ed | SMOKE PASS (freeze 7,062 params unmoved, resume all True) |
  | oplc_fl2 | + this change, FAST LOOP (1 producer x 8 matches, CPU) | same | cb89adf5 / b3eaf2ad | c3eee81d / 10d4a5ed | SMOKE PASS = production's shas on both updates |
  th_drift (a, bot1 = fl2): u0000 hazard mad 1.85e-3 max 7.3e-3 p .1851 -> .1869 tick_kl 7.5e-7, ab mad 8.1e-5; u0001 hazard mad 2.0e-3
  max 8.0e-3 p .1851 -> .1871 tick_kl 1.2e-6, ab mad 1.2e-4 (182 rows = the first batch's rows).
- compare.py (a, CPU, fast_msg_u0000 of oplc_fl1 = 6 init + 2 CLXIII-bot jobs, /workspace/opplearnc/cmp1.json): 8/8 matches
  identical, learner rows 3,192 / 3,192 (every traj key incl. th_j / th_ab / deck_gid / ctx_*), learner decisions 3,192 and
  init-opponent (frozen timing seat) decisions 2,367 identical (row shas), lp max 0, memory tables 8/8, ability presses 9 / 9 per
  side, bot opponent plays equal per match (the bot seats take the fast decide: no _record trace on that path, as before).
- (b) learner vs the identical-weight init won 0/6 at u0000 and 3/6 at u0001 (groups of G 4 repeats are correlated; n too small to
  call). Watch by_opp init ~0.5 in the first calibration updates.

### What was built
| piece | where | switch |
|---|---|---|
| (1) bot partner decode | rl_royale `EXPLOITER_OWN` + `T_gate` (> 0) and `tau_phase` (3 numbers in (0, 1)); `own_opp_cfg` puts them on THAT opponent's cfg (e1_eval.sample_decide_batch reads cfg T_gate / tau_phase). League opponents otherwise keep T_gate None (= their T) and no tau_phase, as before | a league_exploiters entry's keys; absent = cfg unchanged |
| (1) icebow bot pool | `league_exploiters.decks: icebow` = [ICEBOW_DECK], p [1] (league_decks drops icebow by design); the list form takes several bots | the literal "icebow" |
| partners | `learner/opp_learner_bot_smoke.yaml`: bot = CLXIII NOLEAK on icebow, T .5, T_gate .1, tau .35, tau_phase [.35, .45, .55], decide_every 10 (the run's), share .6 + heroiw_press live; human-model partner = league_mix init 1.0 (the frozen imitation init at the run's T 1) for the other .4 | config |
| (2) th_drift | rl_royale `th_drift(model, ref, rows)` + Learner.one_update (timing-head learner only): the first batch's first `TH_DRIFT_ROWS` = 1,024 rows fixed (e1_eval.gen_batch tensors), after every update: hazard / ab_hazard mean + max \|sigmoid diff\| vs ref_init (the init), mean p init -> now, mean KL(init \|\| now) of the tick softmax; log line `[rl] th_drift uNNNN` + rec["th_drift"] in train_log.jsonl | automatic for a timing-head init (no key; a gate model never runs it) |
| (3) fast-loop learner seat | producer.py: learner = model_gen.load_model(base["opp_init"]) + GenPolicy(opp_sim) (actor_main's branch); a timing LEARNER seat allowed when its cfg has th_learner (production's timing_decide_batch -> th_record, _record, _traj_arrays); CfTrain ability mode 3 for a timing seat with the learned ability head, learner or opponent. compare.py: log-prob keys a traj lacks (ab_lp) are skipped | rl base opp_init (set by Learner for a timing-head init) |
| (4) calibration | `learner/opp_learner_calib.yaml` (E 64, G 4, 48 actors, 200 updates, save_every 5, kl_cell_stop 5.0, lambda by override) + `learner/calib_eval.sh` (every saved checkpoint -> one 480-game run_closed block, CLXIII D3 vs it at T 1, G2 on; score on the laptop with card.py --no-c --no-d) | not run yet |

Tests (laptop, a): `pipeline/tests/test_opp_learner.py` 9 passed (6 old + TestDrift 1 + TestBotPartner 2: icebow pool + own
decode, list form draws icebow for every bot matchup, absent keys = own_opp_cfg unchanged, refusals); with test_league +
test_timing_head_decode: 51 passed, 1 skipped, 2 failed = the 2 pre-existing TestSelfPlayCounters failures.

### Findings / concerns
- (b, untested) Partner decode vs eval decode: the bot partner trains at the PILOT's sampled decode (lead's ticket: T_gate .1
  sampled); the calibration bar's "CLXIII SIM win rate" is level B's gap.py D3 = live's greedy LIVE_OPTIONS stack. A snapshot
  can sit inside 30-50% for one and not the other. calib_eval scores D3 (the bar as defined); the in-training
  `exploiter_league` win rate is the sampled-decode number. Lead: say which decode the 30-50% bar means if they differ.
- (b) th_drift rows are fixed per PROCESS (a resume re-picks them from its first batch); the reference stays the init.
- (a) An rl_royale opp-learner checkpoint loads as a timing opponent (e1_eval.load_policy: GenPolicy, timing, opp_sim,
  ability head, memory; oplc_bot1_u0002.pt). gap.py --opp-ckpt on it is (b) untested until the first calib_eval block.
- (a) Fast loop speed at smoke size is NOT faster: 8 matches 392.5 s (1 producer, 2 Java threads, CPU) vs production
  407 s (1 actor, in-flight 8). A timing seat forwards in-process (never on serve.py: TIMING_SEAT.md limits), so the
  11 M-param forward on CPU dominates (b: not profiled). Lever: producers on a GPU device (in-process cuda forward), or
  serve timing models on the server.

### Proposal (NOT built; lead 10-29 asked): a fixed pull on the frozen heads' OUTPUTS ("timing anchor")
- Problem (a, oplc_flv0_l01): freeze_heads keeps the timing / ability head weights fixed, but card / cell PPO moves the shared
  trunk, so the frozen hazard's output moves. On the fixed 1,024 rows its mean |dp| grows with KL (table above). Timing
  human-likeness (gap / rescaled-gap KS, plays/min, lock rhythm) is exactly what level A / B measure.
- Proposal: + lambda_t * mean over the batch's slot-start rows of [ KL_Bernoulli(h_init || h_theta) + h_init * KL(tick_init ||
  tick_theta) ] (+ the same for ab_hazard / ab_tick on rows with a visible ability controller), the init's outputs taken from
  ref_init (already in memory: ref_terms' no-grad pass can return them), gradient into the trunk only (the heads stay frozen).
  This pulls only what the frozen heads output, so it does not pull card / cell, which the strength RL needs to move. A weight
  pull (L2-SP on trunk weights) would also pull card / cell features. One key, e.g. `th_anchor: lambda_t`, absent = today.
- Why not raise lambda instead: lambda pulls card / cell (the strength channel) and only acts on the hazard indirectly.
- Cost: one more head evaluation on rows the policy forward already encodes (the heads are linear on g: ~0 extra), plus
  ref_init's heads (one no-grad pass, shared with ref_terms). Test: frozen heads stay bit-identical; th_drift with the anchor
  on vs off on the same seed (expect mad down, KL card / cell and win-rate trend unchanged).
- Owner rule check: "no KL leash" binds OUR model; this is the opponent's human-likeness pull, the same kind as lambda (b: the
  lead decides).

### Restart
- Smokes: `ssh -p 33903 ... 'cd /workspace/opplearnc && (setsid nohup bash chainc.sh < /dev/null > chainc.out 2>&1 &)'` (rename the
  RUN names first: rl_royale refuses an existing run dir).
- Fast loop: `bash /workspace/opplearnc/fl.sh (= learner/fl_pod.sh) fast RUN 204-211 scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_bot_smoke.yaml --smoke`
  (FASTLOOP_DUMP=1: the msg lands in cbc/scratchpad/gauntlet/L68/rl/RUN/fast_msg_u0000.pkl);
  compare: `bash /workspace/opplearnc/fl.sh (= learner/fl_pod.sh) cmp MSG /workspace/opplearnc/OUT.json 212-219 --in-flight 8 --matches 8 --threads 2`.
- Calibration (after v1): `init=V1_SIM.pt beta0=L beta_min=L beta_max=L` on opp_learner_calib.yaml, one run per L in
  {0.03, 0.1, 0.3}; `calib_eval.sh CKPT_DIR RUN OUTROOT` beside each.

### Codex dispatches
- OPP-LEARN-C_1 (medium; .foreman/scratch/a2/codex/OPP-LEARN-C_1.md): baseline + u0010 relayed (sha equal), run, fetched,
  scored, TABLE.md; BLOCKED before u0020 because P2-OPP2's v1s0 block was running (the ticket said one block at a time; a
  concurrent other job is allowed). Checked by me: 480 / 480 outcome rows each, ENGINE opp_ckpt = the stripped u0010, table
  numbers as reported. OPP-LEARN-C_2 (medium): u0020 (started by me 03:39 UTC) / u0030 / lr3 u0010 / u0020, running (a
  duplicate launch of it was stopped by PID after read-only commands).

## STATUS (OPP-LEARN-B, 2026-10-28)
- Code: private worktree, rebased onto 4dd9911 (LEARNER-SCALE MemRowCache landed; one conflict in policy_terms resolved: my GenPolicy line + their gen_rows), committed as hunks only; the merged tree re-smoked (opplearn_opp3: SMOKE PASS, W16 shas = opp2's). Others'
  uncommitted rl_royale hunks of another worker in the shared tree stay theirs; my patch was applied on top of them).
- Pod smoke (33903 CPUs 200-203, lead OK; crforge fe364ceb + tables 16.635.3 copied from 32657; trees /workspace/opplearn/cb_base
  + cb; script learner/pod_smoke.sh TREE RUN CONFIG; logs /workspace/opplearn/logs/RUN.log): see the Smoke section below.
- Pod smoke RESULTS (a, 33903 CPUs 200-203, fe364ceb + 16.635.3, laptop copies .foreman/scratch/a2/opplearn/logs/):
  | run | tree | config | config sha | W16 u0000 batch / weights | W16 u0001 batch / weights | result |
  |---|---|---|---|---|---|---|
  | opplearn_base2 | 17d006b | succ48_x_s101 | b5e2a2bbafef | b43dd869 / 3e07cff4 | 70b4b263 / d9fd3a96 | SMOKE PASS |
  | opplearn_new2 | 17d006b + this change | succ48_x_s101 | b5e2a2bbafef | b43dd869 / 3e07cff4 | 70b4b263 / d9fd3a96 | SMOKE PASS |
  | opplearn_opp2 | + this change | learner/opp_learner_smoke.yaml (init v0 opp_m10_s0_sim.pt) | dc28331e27cc | f5b6bd67 / b3eaf2ad | 6ecc1abc / 7ac7ec43 | SMOKE PASS |
  base vs new: w16_batch / w16_matches u0000-u0001 files byte-identical (cmp); config sha = the historical b5e2a2bbafef.
  opp learner: freeze_heads 4 tensors (7,062 params) bit-identical + not trainable after 2 updates; beta 0.1 -> 0.1 both
  updates; update-0 on-policy check passed (KL g/c/x 0 / 1e-4 / 1e-4); u0000 213 play rows, 8 matches, ppm 8.08; u0001 KL
  card / cell 1e-4 / 3e-4; u0000 reload state_dict identical; resume check all True. Pod tests: 17 passed (test_opp_learner
  + test_timing_head_decode). pyflakes: only the 2 pre-existing e1_eval warnings (same on the base tree).
  Finding (a; n = 8, so the rate is noise): the s1 partner (CLXIII) won 2 of 8 vs v0 because league opponents sample at
  league_opp_T, unset = the LEARNER's T = 1.0, so CLXIII played at T 1. One league_opp_T covers BOTH partner kinds (the frozen
  human init must stay at T 1). Needed before any strength number is read (b): a per-partner decode (the s1 slot's own T, or
  league_exploiters with an icebow deck pool -- league_decks drops icebow by design).
  Smoke fixes found on the way (in this commit): train_gen --opp checkpoints carry "step", not "epoch" (Learner init_meta);
  policy_terms built GenPolicy(model, ()) which refuses an opponent model without opp_sim.
- Codex: OPPLEARNB_1 (medium): trees + overlay + symlinks done, BLOCKED at the tables copy (ssh -A to 32657: publickey
  denied); I relayed the tables through the laptop (28 files, combined sha256 45b357f8 equal on both pods) and ran pyflakes /
  tests / smokes myself (/workspace/opplearn/chain.sh). (c) Codex reported every copy verified but pod_smoke.sh was missing.
- Restart: `ssh -p 33903 ... 'cd /workspace/opplearn && (setsid nohup bash chain.sh < /dev/null > chain.out 2>&1 &)'` (rename the
  RUN names in chain.sh first: rl_royale refuses an existing run dir).
- Next: (0) a per-partner decode for the bot slot (finding above); (1) the v1 checkpoint as the init once level A/B pass (attach_sim first); (2) the trunk-drift monitor above;
  (3) part C (fast loop) after OPP-LEARN-A; (4) a real calibration run: E 64, G 4, lambda sweep {0.03, 0.1, 0.3} on a GPU learner.
