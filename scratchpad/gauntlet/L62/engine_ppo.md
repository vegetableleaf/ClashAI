# L62 -- engine_ppo: first PPO on the REAL CR engine (EngineMatchEnv), control vs KL-to-init arm
Started 2026-09-05 (local). Written as I go. Every number MEASURED on this box unless marked (b) untested.

## 0. Inputs read (not re-derived)
- scratchpad/gauntlet/L62/engine_env.md + engine_env.py (EngineMatchEnv), run_engine_env.py (GreedyPolicy: masked action selection, ckpt load)
- icebow/src/clashrl/train_sim_ppo.py: compute_gae (l.43), PPONet (l.232-260), masked_logits (l.637-680), log-prob factorisation (l.1379-1390), loss assembly (l.1616-1627), save() (l.1023), --init path (l.489-515: PolicyNet.load_compat + gate load, value head fresh, value warmup)
- icebow/data/bench/bcA_run.yaml: the VALUES (sim: ppo_*; train: gamma) -- recorded in section 2
- scratchpad/gauntlet/L61/read_ckpt.py -- checkpoint format test

## 1. Box at start (MEASURED)
- Free RAM 9568 MB (Available MBytes counter 9708) of 32164 MB, BEFORE the VM. VM ~4.3 GB -> ~5.3 GB left.
  That is BELOW the ">6 GB after the VM" line in the brief. Recorded, not hidden; the two trainer processes'
  RSS is measured below before the launch decision.
- CPU: Intel Core Ultra 9 386H, 16 cores / 16 logical, load 53% at the time of the check.
- Untouched: crawler python PIDs 29444 + 53824 (started 11:46), owner's Nucleo uvicorn PID 63608 (port 8765).
- No qemu / no worker service listening on 37031/37032 at start.

## 2. engine_ppo.py -- what it is (scratchpad/gauntlet/L62/engine_ppo.py)
- Policy = PPONet (PolicyNet + gate + value + value_d; the sim trainer's hazard head is OMITTED -- it is inert at
  coef 0 and not part of the checkpoint layout). CPU, torch threads 2.
- Init = icebow/data/bc_pro/models/bc_bias_native_s0.pt, sha256 a1273d5d700aef0a... (ASSERTED at launch, read-only).
  Loaded EXACTLY as bcA's --init path (train_sim_ppo.py l.489-515): `PolicyNet.load_compat` (asserted 0 dropped
  tensors), gate loaded, VALUE HEAD FRESH. NOTE: the init file carries a `value` key (|w| 5.54 -- c2r's SIM critic,
  `bc_pro.source = c2r_best_36k_backup.pt`); bcA discarded it and so do I -- it valued the sim's shaped reward.
  Fresh critic => `--value_warmup 60` minibatches critic-only, as bcA (ppo_value_warmup: 60).
- Reference pi_ref = a frozen deep copy of the init (per-board estimate, NOT the board-blind cell_bias_map alone).
- Rollout: ONE EngineMatchEnv (`--port`), N=`--rollout` decisions (1024), episodes span rollouts, bootstrap V(s_last);
  tail-capped endings are TRUNCATIONS in compute_gae (trunc=), engine terminations are terminal.
- Sampling = masked_logits semantics, PURE policy (no exploration floors, no gate prior, no spell mask/veto, no drills):
  card masked to in-hand AND affordable (elixir_vec*10 >= cost), PLAY gate masked when nothing playable, cell masked
  by deployable_mask(anywhere?, pocket_code) of the SAMPLED card (pocket = env.sim.pocket_state(0), as run_engine_env).
  Stored: obs uint8, hand/next/elx/thr, cellmask, (g,c,cell), logp, V.
- Update: GAE(gamma, lambda) -> batch-normalised advantages; new_lp = lp_g[g] + play*(lp_c[c] + lp_cell[cell]);
  clipped surrogate on the JOINT ratio; MSE value loss; entropy = gate + play*card at --ent, cell entropy separately
  at the annealed cell coef (bcA: 0.05 -> 0.008 over 3000 episodes); Adam eps 1e-5; grad clip; head-norm cap x2.0 of
  the init's card_head / cell_conv[-1] weight norm (bcA ppo_head_norm_mult 2.0).
  KL term = kl_coef * mean over PLAY rows of KL(pi_theta(cell|board,card) || pi_ref(cell|board,card)), both
  log_softmax over the card's deployable mask (renormalised); the card-head KL to the ref is logged, not penalised.
  The ref log-probs are computed ONCE per update, batched (a per-decision batch-1 ref forward would cost as much as
  the policy itself: ~7 ms).
- Rail metric: pre-tanh cell logits (`PolicyNet._cell_logits`) of the sampled card (wait rows: the argmax playable
  card), |.| over that card's deployable cells, p99 over the rollout -- the same quantity read_ckpt prints.
- Checkpoints: `{out_prefix}_m0.pt` before any update, `_m{N}.pt` at every --save_every crossing, `_latest.pt`
  (atomic replace), `_crash*.pt` on abort. Layout = train_sim_ppo.save(): model/gate/value/value_d/algo/grid/n_cards/
  n_cells/threat_dim/in_ch/deck/best_wr/matches/arena_size (+ an `engine_ppo` dict). Asserts at launch: no
  `{out_prefix}_*.pt` exists, the log does not exist, and out_prefix is not under icebow/data/ unless
  icebow/data/bench/engA_*.
- Seeds: random/numpy/torch from --seed; pool sampling = random.Random(seed).randrange(len(pool)) per episode
  (env.reset(index=)), so both arms see the same tag sequence; action sampling uses a torch.Generator(seed).

### 2.1 Hyper-parameters USED (the VALUES from icebow/data/bench/bcA_run.yaml, not cfg.get defaults)
| knob | value | yaml key |
| --- | --- | --- |
| gamma | 0.994 | train.gamma |
| GAE lambda | 0.95 | sim.ppo_gae_lambda |
| clip | 0.2 | sim.ppo_clip (clip_play_mult 1.0, per_head false) |
| lr | 2.5e-4 | sim.ppo_lr (Adam, eps 1e-5) |
| entropy gate+card | 0.02 | sim.ppo_entropy |
| cell entropy | 0.05 -> 0.008 over 3000 episodes | sim.ppo_cell_entropy / _floor / _anneal |
| epochs | 4 | sim.ppo_epochs |
| minibatch | 512 | sim.ppo_minibatch (rollout 1024 => 2 minibatches x 4 epochs = 8 per update) |
| vf_coef | 0.5 | sim.ppo_vf_coef |
| max grad norm | 0.5 | sim.ppo_max_grad_norm |
| head norm mult | 2.0 | sim.ppo_head_norm_mult |
| value warmup | 60 minibatches | sim.ppo_value_warmup (= the first 7.5 updates are critic-only) |
| NOT used (doctrine/scaffold) | explore floors 0.15/0.15, gate prior coef 2.0, spell target mask, drills, hazard 0.5, distill, search | -- |

## 3. VM boot (MEASURED)
- 13:36:35 `_boot.ps1` (`worker start --workers 2 --base-port 37031`): attempt 1 FAILED (exit 1, the ~1-in-3
  flake, 5m50s lost), attempt 2 started 13:42:25 and was ready at 13:43:09 (44 s). Both slots tick 10, hash
  d036bec06e300550, towers 3052x4/4824x2. qemu-system-x86_64-headless PID 54304 (WS 3706 MB), adb PID 59132.
- Available RAM after boot: 5742 MB.
- PORTS: the brief names 37031/37032; those are the ADB-FORWARD ports of slots 0/1. Their DIRECT-transport twins are
  38031/38032 (emulator tcp redir, same two slots). L61 measured the direct transport at ~2 ms/RPC vs ~20 ms per
  observe over adb, and every L62 throughput number was taken on 38031. A match is ~600 observes + ~660 steps, so
  adb would add ~20 s per match (6x slower). Everything below therefore runs on 38031 (slot 0 = control) and
  38032 (slot 1 = KL arm). Same engine slots, faster pipe.
- Box load during the smoke: CPU 90% (crosvm / the other agent's rendering / crawler), vs 53% before. All s/match
  numbers below carry that contention and are SLOWER than L62's 3.1 s/match bench.

## 4. Smoke (MEASURED) -- 5 matches per arm, sequential on slot 0 (38031), seed 41, --value_warmup 0 so the policy
##    actually moves inside 2 updates (with the 60-minibatch warm-up both updates would be critic-only)
Logs: scratchpad/gauntlet/L62/smoke/engA_smoke_{ctrl,kl}.log; checkpoints beside them.

control (--kl_coef 0):
  upd 1  m=2 dec=1024  ep_r -0.952 WLD 1/1/0 len 191s | pl +0.0355 vl 0.6484 ent 0.284 cell_ent 3.869 kl_cell 0.0093 kl_card 0.0006 kl_term 0 clip 0.234 | last-epoch pl +0.0252 kl_cell 0.0157 | raw_p99 6.33 max 24.1 | p_play 0.099 | roll 21.4s upd 13.2s
  upd 2  m=5 dec=2048  ep_r -2.060 WLD 1/2/0 len 202s | pl +0.0151 vl 0.9310 ent 0.278 cell_ent 3.798 kl_cell 0.0338 kl_card 0.0052 kl_term 0 clip 0.133 | last-epoch pl +0.0124 kl_cell 0.0536 | raw_p99 8.69 max 21.6 | p_play 0.097 | roll 21.2s upd 11.8s
KL arm (--kl_coef 0.1):
  upd 1  m=2 dec=1024  ep_r -0.952 WLD 1/1/0 len 191s | pl +0.0356 vl 0.6477 ... kl_cell 0.0087 kl_card 0.0006 kl_term +0.0009 clip 0.234 | last-epoch pl +0.0253 kl_cell 0.0177 kl_term +0.0018 | raw_p99 6.33 | roll 33.8s (pol 8.2s) upd 17.8s
  upd 2  m=5 dec=2048  ep_r -2.060 WLD 1/2/0 len 202s | pl +0.0188 vl 0.9180 ... kl_cell 0.0311 kl_card 0.0053 kl_term +0.0031 clip 0.131 | last-epoch pl +0.0138 kl_cell 0.0568 kl_term +0.0057 | raw_p99 8.69 | roll 30.2s (pol 6.3s) upd 12.0s
- No NaN/inf anywhere (the trainer raises on a non-finite loss part or parameter; it did not). Losses finite.
- Checkpoints saved: _m0, _m5, _latest for both arms.
- Pairing works: the two arms' rollouts are IDENTICAL (same tags, same 1024 actions, same rewards) -- the pool
  sequence and the action generator are seed-driven. After update 1 the arms differ (kl_cell 0.0338 vs 0.0311),
  and at m5 the parameter distance ctrl-vs-kl is |dtheta| 0.058 against 0.521 ctrl-vs-init: the term acts.
- FORMAT TEST PASSED: `read_ckpt.py ../scratchpad/gauntlet/L62/smoke/engA_smoke_ctrl_m0.pt` ->
  [v1 sim boards] top1 15.44 top5 46.61 ; [v2 engine boards] top1 15.00 top5 43.51 -- the init's numbers EXACTLY;
  and torch.equal(m0.model, init.model) and (gate) both True. read_ckpt's own rails line on the pro-board set:
  p99 10.9, frac>8 0.025 (the brief's "~9.5" is the same quantity on a different board sample; on the ROLLOUT boards
  my metric reads 6.33 at init).
- Rail metric moved 6.33 -> 8.69 in TWO updates at coef 0 and at 0.1 alike (the KL term is not what holds it
  yet; watch the launched runs).
- p_play ~0.10 sampled (~38 plays per 190 s match; the greedy BC in L62 made 15.9 accepted plays/match).
- s/match here 7.7-18 s including updates (rollout 21-34 s per 1024 decisions, ~2.6 matches; update 12-18 s).
  The bench's 3.1 s/match was on a 53%-loaded box with greedy stepping and no update.

### 4.1 The KL coefficient -- |KL term| / |policy loss| at coef 0.1 (MEASURED) and the choice (b)
- Strictly AT INIT the ratio is 0/0: pi_theta == pi_ref so KL = 0 (and its gradient is 0), and on epoch 0 the ratio
  is exactly 1 so the surrogate is -mean(normalised adv) ~ 0. The ratio only exists once the policy has moved.
- update 1 (epoch-avg): 0.0009 / 0.0356 = 0.025 ; last epoch 0.0018 / 0.0253 = 0.07
- update 2 (epoch-avg): 0.0031 / 0.0188 = 0.16  ; last epoch 0.0057 / 0.0138 = 0.41
  It rises because KL rises with drift (0.009 -> 0.034 per update at coef 0) while |pl| falls.
- By the brief's rule (ratio < 0.05 -> pick the coef that puts it near 0.5): using update 2 (the first update whose
  rollout was actually collected off the reference), 0.1 x 0.5/0.16 = 0.31 (avg) or 0.1 x 0.5/0.41 = 0.12 (last
  epoch). CHOSEN: **--kl_coef 0.3** -- puts the update-2 average ratio at ~0.5 (last-epoch ~1.2). This is a
  labelled (b) choice from a 2-update smoke on a non-stationary ratio, NOT a tuned value; the ratio will
  self-limit as the penalty binds (higher coef -> less drift -> lower KL).

## 5. LAUNCH (MEASURED) -- 13:49:44 local = 17:49:44 UTC, 2026-09-05, via engA_launch.ps1
`powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62\engA_launch.ps1`
(Start-Process, hidden window, stdout/stderr redirected to L62/engA_{ctrl,kl}_20260905.{stdout,stderr}; PIDs in engA_pids.json)

| arm | port (slot) | kl_coef | out_prefix | log | launcher PID | WORKER PID (the real process, 1.93 GB RSS) |
| --- | --- | --- | --- | --- | --- | --- |
| control | 38031 (slot 0) | 0 | icebow/data/bench/engA_ctrl | scratchpad/gauntlet/L62/engA_ctrl_20260905.log | 51956 | **31628** |
| KL | 38032 (slot 1) | 0.3 (b) | icebow/data/bench/engA_kl | scratchpad/gauntlet/L62/engA_kl_20260905.log | 32284 | **54320** |
Common: `--matches 2000 --seed 41 --rollout 1024 --save_every 250 --value_warmup 60` (+ all section-2.1 defaults).
The venv python.exe is a launcher: the PID Start-Process returns is a 4 MB shim whose CHILD is the trainer.
VM: qemu-system-x86_64-headless PID **54304** (3748 MB), adb PID 59132.

First update lines (verbatim, both arms -- identical by construction: same seed, same tags, same actions, and
the first 60 minibatches are critic-only so the parameters are identical too):
  ctrl [upd 1] m=2 dec=1024 | win ep_r -0.952 (last50 -0.952) WLD 1/1/0 cum 1/1/0 len 191s | pl +0.0484 vl 0.6478 ent 0.291 cell_ent 3.860 kl_cell 0.0157 kl_card 0.0006 kl_term +0.0000 clip 0.261 vpred +1.616 ret +1.638 | last-epoch pl +0.0475 kl_cell 0.0147 kl_term +0.0000 | raw_p99 6.33 max 24.1 | p_play 0.099 | s/match 9.65 roll 26.6s (pol 4.5s) upd 12.7s warm_mb 8 cell_coef 0.0500 elapsed 0.7m
  kl   [upd 1] m=2 dec=1024 | ... identical ... kl_term +0.0047 ... last-epoch kl_term +0.0044 | raw_p99 6.33 max 24.1 | p_play 0.099 | s/match 9.56 roll 26.2s (pol 4.6s) upd 12.5s warm_mb 8
By update 6 (KL arm): m=20 dec=6144 cum WLD 3/17/0, len 124-241 s, raw_p99 5.6-9.1 (init 6.33), p_play 0.086-0.115.

### 5.1 Throughput and expected finish (MEASURED over the first 4 min, both arms concurrent, box CPU 83-90%)
- Per update: rollout 26-33 s for 1024 decisions (policy 4.5-5.1 s of it) + update 11.2-12.7 s  => ~40 s / 1024 decisions.
- Matches: ctrl 16 in 3.4 min, kl 20 in 4.0 min => **~12 s/match** each arm (aggregate ~6 s/match for the pair).
  For scale: L62's greedy bench on a 53%-loaded box was 3.1 s/match; the difference is the update (~30% of wall),
  sampling instead of greedy, and the busier box (crosvm + the other agent's rendering).
- 2000 matches at 12 s/match = 6.7 h; matches are shortening (124-152 s as the sampled policy loses faster), which
  lowers decisions/match, so: **expected finish ~20:30-21:30 local (00:30-01:30 UTC, Sep 6)** if the box load stays
  as it is. Checkpoints _m250, _m500, ... every ~50 min.
- RAM: each trainer 1.93 GB RSS; Available MBytes 2502 after launch (5742 before). Tight. If the other agent's
  rendering grows the box will page; nothing here can prevent that.

### 5.2 Warm-up caveat (MEASURED, the one thing I would change)
The critic warm-up (bcA's 60 minibatches) trains the value head on the SHARED trunk, so it moves the policy: kl_cell
0.016 -> 0.088 after ONE critic-only update (upd 2), before any policy gradient. In the launched code the KL term
is computed and logged but NOT in the loss during warm-up, so the KL arm is unrestrained for the first 7.5 updates
(~20 matches) and identical to the control over that stretch; from update 8 the penalty pulls it back toward the
ref (the KL is a loss on the distribution, so the drift is recoverable). I tried to stop and relaunch with the
term active in warm-up; the sandbox refused the process kill (Stop-Process / taskkill both blocked), so the pair
runs as launched. The code as launched is archived as engine_ppo_launched_20260905.py; engine_ppo.py now has
`--kl_in_warmup` (default 1) for any re-run -- the running pair is equivalent to `--kl_in_warmup 0`.

## 6. HOW TO STOP EVERYTHING
1. Trainers (each writes `_crash{N}_{ts}.pt` on a clean abort; a hard kill just loses the current rollout, the last
   `_m{N}.pt` / `_latest.pt` on disk stay valid):
     taskkill /PID 31628 /F      (control worker)     taskkill /PID 51956 /F   (its launcher shim)
     taskkill /PID 54320 /F      (KL worker)          taskkill /PID 32284 /F   (its launcher shim)
2. Then the engine services + VM (from research/ext/cr-native-sandbox, its own venv + runtime env):
     cd C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox ; . .\runtime.env.ps1
     .\.venv\Scripts\python.exe -m native_core.worker stop --workers 2 --stop-vm
   expect `vm_stopped: true`; verify no qemu-system-x86_64-headless (was PID 54304) and `adb devices` empty.
3. Do NOT stop the VM while the trainers run (every env.step is an RPC to it).
Leave alone: crawler PIDs 29444/53824, Nucleo uvicorn PID 63608 (port 8765).

## 7. Files
- scratchpad/gauntlet/L62/engine_ppo.py (trainer; `--kl_in_warmup` added post-launch), engine_ppo_launched_20260905.py
  (the exact code the running pair executes), engA_launch.ps1 (re-runnable launch), engA_pids.json, _boot.ps1 / _boot_ppo.log
- smoke: scratchpad/gauntlet/L62/smoke/engA_smoke_{ctrl,kl}{.log,_m0.pt,_m5.pt,_latest.pt}
- run outputs: icebow/data/bench/engA_{ctrl,kl}_m0.pt / _m{250..2000}.pt / _latest.pt ; logs in L62/engA_*_20260905.log
- Nothing under icebow/src/ modified; icebow/data/ghost_pool/pool.jsonl untouched; init checkpoint read-only
  (sha256 asserted); nothing committed; no secrets printed.

## 8. FIRST 10 MINUTES OF THE PAIR (MEASURED at 13:59 local; both arms advancing, 14 updates each, no NaN/stderr beyond the init-check warning)
| upd | m (ctrl/kl) | ctrl kl_cell | KL-arm kl_cell | ctrl raw_p99 | KL-arm raw_p99 | note |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2/2 | 0.016 | 0.016 | 6.33 | 6.33 | identical (warm-up) |
| 6 | 20/20 | 1.146 | 1.146 | 6.90 | 6.90 | identical; still warm-up |
| 7 | 24/24 | 1.068 | 1.068 | 9.37 | 9.37 | last identical update |
| 8 | 26/26 | 1.080 | 0.989 | 10.73 | 10.73 | KL term enters the loss (warm_mb 0) |
| 10 | 32/32 | 0.767 | 0.126 | 12.99 | 6.44 | |
| 14 | 42/42 | ~0.72 (upd 13) | 0.095 | 12.98 | 10.51 | cum WLD ctrl 7/34/0 (upd 13), KL 6/36/0 |
Reading (measured): the critic warm-up alone -- six critic-only updates on the shared trunk -- carried BOTH arms to
kl_cell 1.15 nats from the init before a single policy-gradient step. That is the bcA recipe's warm-up doing to the
engine run what it presumably did to bcA. The KL arm (coef 0.3) recovers to ~0.1 nats within 3 updates after the
term enters; the control stays at 0.7-1.0 nats and its cell-head rail metric is already 13 (init 6.3, bcA final 72).
Win rate is 15% for both at m=42 (sampled policy vs pool ghosts); no separation on winrate is expected this early.
Process memory at 13:59: ctrl WS 2112 MB / private 3054 MB, KL WS 1994 / private 2940; Available 2.2-2.5 GB. WS grew
~100 MB in the first 10 min; if that is a steady leak the pair will page out before m=2000 -- watch `Available MBytes`
and the private-bytes of PIDs 31628/54320 at the _m250 checkpoint (~14:40 local); if either exceeds ~4 GB, stop that
arm (section 6) and resume from `_latest.pt` is NOT implemented (no `--resume`) -- a restart is a restart from m0.

STATUS: complete
