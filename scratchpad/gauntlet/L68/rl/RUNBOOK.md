# RL on RoyaleSim -- runbook (L68)

Trainer: `pipeline/rl_royale.py`, defaults `pipeline/rl_royale.yaml` (every key commented with its source).
Design: `scratchpad/gauntlet/L68/rl_plan.md` (binding), `scratchpad/gauntlet/L67/e1_engine_rl_design.md` 3.2-3.6, 4.2.
All commands from the repo root; the trainer runs in the **Royale venv** (it has royalesim; the icebow venv does not).


## 0. Offline tests (icebow venv, no engine, ~1-2 min)
```
icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_rl_royale pipeline.tests.test_rl_gen -v
```

## 1. Smoke (~10-20 min on the busy box)
```
research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run smoke_<date> --smoke
```
E=4, G=2, 1 actor, 8 in flight, 2 updates, screen on 8 held-out entries, pro agreement on 1,000 VAL rows. It checks:
u0000 reloads through `engine_play.load_model` with identical pro agreement; update 0 is on-policy (max |ratio-1| < 1e-4,
KL < 1e-6 per head, else AssertionError = a bug); a fresh learner through `--resume` restores update / beta / optimizer
/ rng / guards. Last line `SMOKE PASS` (exit 0) or `SMOKE FAIL: <check>` (exit 1). Delete its two dirs afterwards
(`scratchpad/gauntlet/L68/rl/smoke_<date>`, `icebow/data/bench/rl_royale/smoke_<date>`).

## 2. Start
```
research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run <name>
research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run <name> E=8 n_actors=2     # any key=value override
```
Refuses an existing non-empty run dir (use a new name, or `--resume`). Startup (~5-10 min): loadable-entry scan
(cached in `entries.json`: train 299, held-out 58), init pro agreement on all 13,761 v3 VAL rows (`init_proagree.json`),
init held-out screen on the 58 (`init_screen.json`), `<name>_u0000.pt` (= the init). Then one update per ~64 matches.

Files: `scratchpad/gauntlet/L68/rl/<name>/` = `train.log` (one human line per update), `train_log.jsonl` (everything),
`config.yaml`, `pid.json` (learner + actor PIDs while running), `entries.json`, `init_*.json`.
Checkpoints: `icebow/data/bench/rl_royale/<name>/` = `<name>_latest.pt` (every update), `<name>_u{NNNN}.pt`
(NNNN = updates done, every `save_every`), `<name>_crash_*.pt` on a crash.

## 3. Watch -- the fields that matter (`train_log.jsonl`, type "update")
| field | healthy | why |
|---|---|---|
| `plays_per_min` vs update 0 | within 0.6x-1.6x (stop rule, 2 in a row) | gate collapse / over-play (engA) |
| `kl_cell`, `beta_next` | kl_cell near `kl_target` 0.10; beta moving inside [0.03, 3] | the leash; beta at 3.0 with KL_cell > 0.5 = stop |
| `kl_gate`, `kl_card` | small (< 0.1) | gate drift is the historical collapse channel |
| `mixed_group_share` | > 0.3 | share of entries whose G rollouts disagree = the gradient's real sample size |
| `entropy` vs `entropy_init` | same order | a head going deterministic; stop = any head < `entropy_floor_frac` 0.5 x init's on the same rows, 2 in a row (E1 3.4) |
| `clip_frac`, `ratio_mean` | clip_frac < ~0.2, ratio_mean ~1 | step size |
| `first_minibatch.ratio_maxdev` | < 1e-4 every update (measured ~8e-6) | on-policy integrity (asserted at update 0) |
| `screen.delta_pp`, `ci_lo_pp`/`ci_hi_pp`, `better`/`worse` | the signal; stop = delta <= -10 pp AND CI upper < 0 | held-out RoyaleSim, 58 entries x seeds 0,1,2, entry-clustered paired vs init (every `screen_every`) |
| `proagree_delta_pp` | > -1 pp cell | tripwire: cell < -1 pp AND screen delta <= 0 = stop; hard stop -3 pp cell/card, -0.05 gate |
| `screen_guards.init` / `.cand` (`outlived_win_share`, `low_delivered_win_share`, `ghost_refused_per_match`) | cand within init + 15 pp / init + 10 pp / max(2x, +1.0) of init | ghost-exploit guards (E1 4.2.1-3) on the HELD-OUT SCREEN, same 174 matches, single occurrence at a screen; also on the screen line as `guards outlived i->c ...` |
| per-update `outlived_win_share`, `low_delivered_win_share`, `ghost_refused_per_match`, `ghost_undelivered_per_match` | -- | train-batch MONITORS only, never a stop (see below) |
| `winrate` | descriptive only | train entries are revisited; never a verdict |
| `visits_distinct`, `visits_max` | -- | pool revisits (299 entries) |
| `wall_*`, `actor_s_per_match`, `*_gpu_peak_mb` | -- | throughput |

**Why the exploit guards are measured on the held-out screen (L68).** The first 30-update run, `rl30_20260924`,
stopped after update 5 on `<=10-delivered win share EMA 0.110 > update-0 0.000 + 0.10` -- a false alarm. Each update
trains on 16 freshly sampled ghosts: update 0's batch happened to contain no ghost with <= 15 recorded plays (median
51 `ghost_plays`), while updates 1-5 drew 1-4 such short-script ghosts whose matches land in the <= 10-delivered bucket
whatever the policy does (update 4's 0.241 = the batch with 3 ghosts of <= 10 recorded plays). The outlived-the-script
share swung 0.265 (update 0) -> 0.581 -> 0.314 -> 0.373 -> 0.379 -> 0.302 over the same updates, and the ghost-refused
rate has the same flaw: one train batch against another measures which opponents were
sampled, not a change in the policy. The held-out screen replays the SAME 58 ghosts x seeds 0,1,2 for the init and every
candidate, so a rise there is the policy's. The train-batch values stay in train_log.jsonl as monitors; plays/min keeps
its update-0 baseline (a property of the gate, far less sampling-dependent). A run started by the older code resumes
fine: its obsolete guard state is dropped and, because its cached init screen holds outcomes only, `--resume` re-runs
the init screen once with the init weights (logged `init screen rebuilt ...`, ~3-5 min) to get the init side.

NOT implemented (monitors you read by hand, not stop rules): E1 4.2.4 won-match length drift (+20 s flag) -- read
`won_seconds_mean` against update 0; E1 4.2.5 per-ghost flip list -- the screen logs only `better`/`worse` counts, not
which entries flipped.

**Screen noise (measured L68, run noise_L68, 3 updates at the default config, KL_cell 0.002-0.006):** paired deltas
-0.6 / +1.1 / +0.6 pp, 95% CI half-width ~6-8 pp (e.g. [-8.0, +7.5]), and 35-46 of the 174 (tag, k) pairs flip
(better/worse ~22/23) even though the policy has barely moved -- the greedy live rule turns tiny weight changes into
whole-match flips. So a screen delta inside roughly +-8 pp says nothing; read the CI, not the point estimate. (The old
8-entry, 1-seed smoke screen swung -25 pp on 2 flips.)

**Gradient clip (measured):** every step's gradient norm exceeds `grad_clip` 0.5 (mean 1.3-2.0), so each step is a
fixed-length step in the gradient's direction; at lr 1e-5 KL_cell still stays ~0.002-0.006 per update. Because KL_cell
is far below kl_target / 1.5, adaptive beta halves every update (0.3 -> 0.15 -> 0.075 -> 0.0375) and sits at its 0.03
floor from ~update 4. That is the rule working as written, not a fault. Watch: KL_cell climbing toward 0.10 over tens
of updates (then beta starts rising again); `clip_frac` above ~0.2 or `ratio_mean` drifting off 1 (steps too large for
the clip); if KL_cell is still < 0.01 after ~20 updates, the policy is effectively frozen at this lr -- raising lr is an
owner decision, like kl_target.

`tail -f` the human log: `Get-Content scratchpad/gauntlet/L68/rl/<name>/train.log -Wait -Tail 20`.

## 4. Stop
Create `scratchpad/gauntlet/L68/rl/<name>/STOP` (any content). The learner finishes the current update, saves
`_latest.pt`, logs `STOP after update N: STOP file present`, closes the actors, exits 0. Every automatic stop rule ends
the same way with its reason on the STOP line (a non-finite loss/gradient/parameter logs `NON-FINITE at update N`,
writes `<name>_crash_u{N}_*.pt` instead and leaves `_latest.pt` at the last good update, then the same STOP line and
exit 0). If a crash left `<name>_u{NNNN}.pt` but not the matching `_latest.pt`, `--resume` re-runs that update and
keeps the existing numbered file (logged `already exists ... kept`). That kept `u{NNNN}` holds the ABORTED attempt's
weights: it is not an ancestor of `_latest.pt` or of any later checkpoint (the re-run of that update produced different
weights that were only written to `_latest.pt`), so do not treat it as a point on the run's lineage.

Do not kill the learner mid-update unless it hangs. The learner writes `pid.json` (learner + actors) and `actors.pid`
(one actor PID per line, rewritten on every actor restart) in the run dir and deletes both on a clean exit. An idle
actor exits on its own within ~30 s of the learner going away; an actor in the middle of a job finishes that job first
(bounded only by the job's own length), then sees the learner is gone and exits WITHOUT sending its results (its result
queue never blocks process exit; measured L68: a mid-job actor exited ~91 s after a hard learner kill). If the learner
was killed hard, stop the actors now instead of waiting (PowerShell, from the repo root). The file outlives a hard kill
and Windows reuses PIDs, so the one-liner only stops a PID that is STILL a python `multiprocessing` child -- never an
unrelated process that inherited the number:
```
Get-Content scratchpad/gauntlet/L68/rl/<name>/actors.pid | ForEach-Object { $p = Get-CimInstance Win32_Process -Filter "ProcessId = $_"; if ($p -and $p.Name -eq 'python.exe' -and $p.CommandLine -match 'multiprocessing') { Stop-Process -Id $_ -Force } }
```
Verify nothing is left (actors show up as `multiprocessing.spawn` children, not by the module name):
```
Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -match 'rl_royale|multiprocessing' } | Select-Object ProcessId, CommandLine
```
(other projects' multiprocessing children match the second pattern too -- compare with `actors.pid` before killing).

## 5. Resume
Delete the STOP file first (resume refuses while it exists), then
```
research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run <name> --resume [key=value ...]
```
Continues from `<name>_latest.pt`: update counter, beta, Adam state, entry-sampling rng, visit counts, stop-rule
counters/EMAs, init baselines (pro agreement, init screen per tag). A changed config is allowed and logged
(`RESUME with a changed config`), e.g. a raised `max_updates`.

## 6. Gate a checkpoint
RoyaleSim held-out, 3 seeds (paired vs the init):
```
icebow/.venv/Scripts/python.exe -m pipeline.rl_gate --commands --engine royale --init-ckpt icebow/data/pipeline/s1_icebow_v6aug_s1.pt --cand-ckpt icebow/data/bench/rl_royale/<name>/<name>_u0050.pt --out-root scratchpad/gauntlet/L68/rl/<name>/gate_royale_u0050
```
run the two printed `e1_eval` lines, then
```
icebow/.venv/Scripts/python.exe -m pipeline.rl_gate --init scratchpad/gauntlet/L68/rl/<name>/gate_royale_u0050/init --cand scratchpad/gauntlet/L68/rl/<name>/gate_royale_u0050/cand --json scratchpad/gauntlet/L68/rl/<name>/gate_royale_u0050/report.json
```
Real engine (the verdict that counts): same with `--engine real` (boot both engine slots first, ports 38031/38032; see
HANDOFF / `e1/_boot.ps1`), four printed lines (init/cand x slot0/slot1). Pro agreement for criterion (ii) is not in
rl_gate: read `proagree` from train_log.jsonl or run, for an S1 checkpoint,
`icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 icebow --data icebow/data/pipeline/s1_dataset.npz <ckpt>`;
for a GENERALIST checkpoint (`"gen": True`, every run with a gen init) `eval_s1` is WRONG (it is S1-only) -- use
`icebow/.venv/Scripts/python.exe -m pipeline.eval_gen --ckpt <ckpt> --data icebow/data/pipeline/gen_dataset_v1.npz --out scratchpad/gauntlet/L68/rl/<name>/eval_gen_<u>.json`
and read its v3val block (the rows the trainer's tripwire uses).
**Condition (T12b).** A run trained under the live condition must be gated under it: add
`--config scratchpad/gauntlet/L68/rl/<name>/config.yaml` to `rl_gate --commands`; every printed e1_eval line then
carries the run's `--noise-off / --opp-elixir / --action-delay / --extrapolate` (a comment line shows which). Without
`--config` the lines are the old default condition.
No "best on held-out" selection: gate the checkpoint you decided to gate before looking at screens.

## 7. Generalist init and live-condition keys (L68 T11)
**Generalist.** Pass a generalist checkpoint (a train_gen `"gen": True` file) as `init`; the trainer detects it:
```
research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run <name> init=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
```
- Actors play `e1_eval.GenPolicy` (as icebow, vs the same ghost pool) and record the generalist's OWN input rows
  (`e1_eval.GEN_ROW_KEYS`: zeroed-slot `sc`, (card, form, x, y, dt) past, hand/next/deck identities, `hand_slot`).
- The learner recomputes the sampler's distribution through the sampler's own `GenPolicy.heads_t`: gate as S1; card =
  the 4 hand-position logits scattered onto their deck slots, softmax / T over the ALLOWED slots (== allowed hand
  positions); cell = `cell_logits_gen` for the sampled card's identity + form, softmax / T over 2,304. PPO ratio and
  KL(pi || init) (gate / card / cell, adaptive beta on KL_cell) use exactly these; the update-0 on-policy assert applies.
- Pro agreement = `eval_gen.evaluate` on the dataset_gen v3val rows (`proagree_data_gen`, default
  `icebow/data/pipeline/gen_dataset_v1.npz`, `v3val == 1` = S1's 13,761 v3 VAL rows; loaded key by key, ~11 s, the
  full set ~2.5 min on CPU). Measured (a): reproduces the checkpoint's recorded v3val exactly (cell 0.2071, card 0.6457,
  gate_bal 0.7669). The tripwire / hard stops are relative to THIS init measurement, not to S1's numbers.
- Checkpoints add `gen`/`d_c`/`card_vocab`: load with `eval_gen.load_model` or `e1_eval.load_policy` (so `e1_eval
  --ckpt`, `rl_gate`, `run_screen.py` take them); `engine_play.load_model` does NOT (it is S1-only).

**Conditions** (`rl_royale.yaml`, defaults = the old behaviour; any can be a `key=value` override; recorded in
`config.yaml` and on the startup log line). They go into EVERY actor match -- rollouts, the init screen and every
held-out screen -- so training and evaluation run under the same conditions:

| key | default | live condition | meaning |
|---|---|---|---|
| `noise_off` | `[]` | `all` | e1_view.Noise components off (list, comma string, or `all` = clean obs, the memory-reader path) |
| `opp_elixir` | `null` | `counter` | opponent elixir from the public-events counter (bodiless spells dropped); `counter_all` = every play |
| `action_delay_ticks` | `0` | `26` | a play decided at T lands at T + D (live tap->land ~24-27 ticks) |
| `extrapolate_ticks` | `0` | `26` | each decision sees the board advanced H ticks (pipeline/extrapolate.py) |

Measured reference (HANDOFF "ACTION DELAY" / "EXTRAPOLATION", greedy screen, 58 distinct matches): generalist clean +
counter 0.983 -> + delay 26 0.828 -> + extrapolate 26 0.862. NOTE: with `noise_off=all` the eval seeds k=0/1/2 replay
IDENTICAL screen matches (HANDOFF correction), so the 174-match screen is 58 distinct matches; its CI is entry-clustered
and stays valid, but `better`/`worse` counts triple-count each entry. Rollouts are unaffected (their obs seed varies
per (entry, g, update) and the behaviour sampler is stochastic). Resuming a run started before T11 logs the four new
keys (plus `proagree_data_gen`) as a changed config -- expected.

Smoke with the live condition (CPU; measured 458 s wall, 2026-09-25, T11smoke_gen: SMOKE PASS):
```
CUDA_VISIBLE_DEVICES= research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run T11smoke_gen --smoke init=icebow/data/pipeline/gen_v1_s0/gen_s0.pt noise_off=all opp_elixir=counter action_delay_ticks=26 extrapolate_ticks=26 learner_device=cpu actor_device=cpu
```
Tests: `icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_rl_gen.py`.

## 9. Self-play LEAGUE (L68 T12b)
Owner design (rulings 2026-09-25): ONE learner = the generalist; opponents = a pool of FROZEN policies; every match under
the live condition on BOTH sides; evaluation unchanged (held-out ghost screen + pro-agreement tripwire + guards).

**Start the real run (GPU; owner-approved start only -- the laptop is shared):**
```
research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run <name> init=icebow/data/pipeline/gen_v1_s0/gen_s0.pt league=true noise_off=all opp_elixir=counter action_delay_ticks=26 extrapolate_ticks=26
```
Everything else is the yaml default (the recommended block below). `league=true` refuses a non-generalist init.

**Recommended league block (the yaml defaults; `leash: max` is the yaml default for new runs):**
| key | value | why |
|---|---|---|
| `league_opp_policy` | `sample` | the opponent plays the learner's own tempered rule (T 0.5, its own RNG): (1) G rollouts of one matchup then differ on BOTH sides, so more LOO groups carry a mixed outcome (the gradient's sample size); (2) under `noise_off=all` a greedy (`live`) frozen opponent is a deterministic function of the board, a fixed line the learner can learn to exploit instead of learning the game; (3) snapshot-vs-learner is symmetric. `live` = the frozen policy exactly as it plays for real -- switch if the owner wants the greedy opponent. |
| `league_mix` | latest 0.35, older 0.25, init 0.2, s1 0.2 | latest snapshot = the hardest current opponent (the self-play core); older snapshots (uniform over the pool minus the newest) = anti-forgetting / anti-cycling; init = the pro-imitated style (closest to ladder opponents, and the anchor the tripwire measures against); S1 = the icebow expert on the owner's deck. Renormalised over what exists: before the first snapshot `latest` IS the init (init effectively 0.55/0.75 -> 73% with s1 27%); `older` needs 2 snapshots. |
| `league_snapshot_every` / `_keep` | 10 / 8 | a snapshot = 10 updates of drift (KL_cell measured 0.002-0.006 per update at lr 1e-5, so consecutive snapshots are distinct but close); 8 kept = the last 80 updates of history. |
| `league_icebow_share` | 0.2 | P(learner deck = icebow) = 0.2 exactly (icebow is removed from the census list, so it only enters here); opponent decks: 0.2 icebow too, and the S1 specialist ALWAYS icebow -> opponents play icebow P(s1) + (1 - P(s1)) x 0.2 = 0.36 of matches once 2 snapshots exist (0.41 before, P(s1) = 0.27). |
| `league_deck_alpha` / `_floor` | 0.5 / 0.5 | other decks: P(deck i) = max(sides_i^0.5, 0.5 x mean_j sides_j^0.5), normalised over the 182 census decks (183 loadable minus icebow). Measured: max 3.87% (rank 2, 14,305 sides), min 0.27% (22 decks at the floor), effective decks 1/sum p^2 = 112, head-20 share 30.6%. Plain frequency (alpha 1) would give max 16.8%, effective 22.7, head-20 62% -- the long tail would be starved. |

**One update (league on).** `sample_matchups` draws E matchups from the learner's rng (resume continues the stream),
in this order per matchup: opponent (`league_mix`), learner deck, opponent deck (S1 -> icebow), learner side (uniform
0/1), deal seed. Each matchup is one LOO group, run G times (behaviour seeds differ per g on both sides; the deal, decks,
sides and opponent are the group's). Actors run `e1_eval.run_selfplay_batch` on `RoyaleSelfPlayEnv`: per round every
side that decides now (across all in-flight matches) is observed FIRST, then one forward + one batched decide per
policy (the learner, and each distinct frozen opponent in flight), then all act -- a play made on a tick is invisible to
that tick's decisions (board and counter alike). Each side: its own mirrored view (`from_engine(raw, side)`), obs /
behaviour RNGs (the opponent's tag is `<tag>:opp`), past plays, anti-stall clock, extrapolation state. Delay D: a decided
play is queued and lands at T + D while the OTHER side keeps deciding; the deciding side's next decision is the first
grid tick after landing (same as the ghost path). Opp-elixir counter: fed the OTHER side's ACCEPTED plays at their
LANDING tick (dataset_gen card slug, e.g. `the-log`), never either side's elixir. Only the learner's side is recorded;
frozen opponents are read from their checkpoint files by the actors (`e1_eval.load_policy`, cached per path) and never
receive a gradient or a write. Reward and outcome are the learner side's (`RoyaleSelfPlayEnv.outcome(side)`).
A self-play record fills the ghost keys with the opponent: `ghost_delivered` = its accepted plays, `ghost_refused` =
refused at landing, `ghost_undelivered` = unlanded; `won_after_script` is always False (no script).

**Snapshots.** Every `league_snapshot_every` updates (after the update, before `_latest.pt`):
`icebow/data/bench/rl_royale/<name>/<name>_snap_u{NNNN}.pt` = the weights + the keys `e1_eval.load_policy` reads (gen,
args, d_c, card_vocab, epoch, n_params, deck) -- no optimizer moments, no rl state: 5.40 MB (5,400,725 bytes, measured T12bsmoke_a2; the gen_s0 init file is 5.40 MB) (the first T12b version,
a full checkpoint, measured 16.1 MB). The pool keeps the newest `league_snapshot_keep`; an EVICTED snapshot file is
deleted right after `_latest.pt` (which holds the new pool) is saved, so a crash in between leaves an orphan file,
never a saved pool naming a missing one. Numbered checkpoints `<name>_u{NNNN}.pt` are separate files and are never
deleted. If a snapshot file for the current update already exists (crash after it, then `--resume` re-ran the update):
identical weights -> kept (logged); different weights -> the run STOPS (RuntimeError "already exists with DIFFERENT
weights"): move that file aside and resume again. The pool rides in the checkpoint's `rl.league`; `--resume` restores
it and the sampling rng. League keys are checked at startup (`validate_league`): snapshot_every / keep integers >= 1,
mix weights finite >= 0 over latest/older/init/s1 with a positive sum, icebow share in [0, 1], alpha / floor >= 0,
opp policy live|sample -- a bad value exits with the key named.

**Opp-elixir counter in simulation (T12b a2, measured).** RoyaleSim's regen schedule is NOT the real engine's
(`.foreman/scratch/T12b/elixir_schedule_probe.py`, every tick of a mirror all-spell match, both sides): start 6.0 at
tick 0 (same); 1/56 per tick on [0, 2400) (real 0.0178); 1/28 from 2400 THROUGH overtime (real: triple, 0.0537, from
4800); the match ends at tick 6000 (real regen stops 6002). `royale_env.REGEN_SCHEDULE` holds it; every RoyaleSim env
(`RoyalePoolEnv` / `RoyaleSelfPlayEnv`, i.e. rollouts AND the held-out screen) declares it and e1_eval's counter uses
it; anything else (the real engine, live) keeps the real `opp_elixir_count.REGEN_SCHEDULE` (default, unchanged).
Effect (`.foreman/scratch/T12b/counter_probe*.py`, estimate minus TRUE opponent elixir per decision):
| path | arm | real schedule (before) | RoyaleSim schedule (now) |
|---|---|---|---|
| self-play, 8 league matchups, both sides, 5.5k decisions | counter_all | MAE 0.421 (0.081 < tick 4800, 4.754 after) | MAE 0.000 |
| | counter | MAE 3.598, bias +3.596 | MAE 3.544, bias +3.544 |
| ghost screen, 8 held-out entries, 2.3k decisions | counter_all | MAE 0.044 | MAE 0.000 |
| | counter | MAE 0.769 | MAE 0.757 |
With the schedule fixed, counter_all is exact, so ALL of the remaining `counter` error is bodiless spells (log, zap,
arrows, fireball, rocket, tornado, ...) -- the real-world error mechanism, not a simulator drift. Self-play's error is
~4.7x the ghost path's because its opponents play more of them: 178 dropped of 708 counted plays (25%) vs 26 of 188
(14%) on the ghost screen, and a dropped spell keeps the estimate high until the cap. Not fixed here:
`pipeline/extrapolate.py` forecasts MY elixir with the real schedule on RoyaleSim too (differs only after tick 4800).

**Leash (owner ruling).** `leash: max` steers adaptive beta on max(KL_gate, KL_card, KL_cell); `cell` = the old
KL_cell-only rule exactly (unit test + the T12b equivalence run). A run started before the key resumes with `cell`
(logged). The KL stop rule (beta at clamp AND KL_cell > 0.5 or KL_gate > 0.1) is unchanged.

**Watch (train_log.jsonl, league on):** `league.by_opp.{init,snapshot,s1}` (n, W/L/D, winrate of the learner),
`league.by_deck.{icebow,head,tail}` (learner deck bucket; head = the 20 most-played census decks), `league.draws`,
`league.plays_per_min` / `league.opp_plays_per_min`, `matchups` (opponent id, decks, side per group), `snapshot` /
`league_pool`, `leash`, `kl_leash`, `kl_driver` (the head that drove beta). Human line: `(leash max: <head>)` and
`| league wr init .xx/n snapshot .xx/n s1 .xx/n D n +snap_uNNNN`. Self-play win rates are DESCRIPTIVE: the opponents
move with the learner; the verdicts stay the held-out ghost screen, pro agreement and rl_gate.

**Smoke (CPU, league + live condition + gen init):**
```
CUDA_VISIBLE_DEVICES= research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run T12bsmoke --smoke init=icebow/data/pipeline/gen_v1_s0/gen_s0.pt league=true noise_off=all opp_elixir=counter action_delay_ticks=26 extrapolate_ticks=26 learner_device=cpu actor_device=cpu
```
(`--smoke` sets `league_snapshot_every: 1`, so both updates add a snapshot and update 1 can draw one; the resume
check also compares the league pool.) Measured 2026-09-25, T12bsmoke: SMOKE PASS in 632 s wall (1 actor, 2 threads, 8
in flight): per update 8 self-play matches, rollout 82-87 s (~10.5 actor-s per match, both sides batched), PPO update
51-61 s on ~2,000-2,100 rows, held-out screen (24 matches) 99-118 s; u0000 added `snap_u0001`, u0001 drew it (4 of 8
matches) and added `snap_u0002`; resume check restored update / beta / optimizer / rng / guards / league pool.
**CPU estimate for the real shape** (E 16 x G 4 = 64 matches, ~16k rows; NOT measured at that size, scaled from the
smoke): rollout ~64 x 10.5 / 3 actors ~ 3.7 min (less if the bigger in-flight batch amortises better), PPO ~8x the
smoke's ~56 s ~ 7.5 min, plus the screen (174 matches, ~4.5 actor-s each / 3 actors ~ 4.4 min every 10 updates) and
full pro agreement (~2.5 min every 5) -> ~12-13 min per update on CPU. The real run is meant for the GPU.

## 8. The KL budget is the owner's
`kl_target` (default 0.10) is NEVER changed by the trainer. Raising it is a manual owner decision, taken only after a
real-engine `rl_gate` PASS on a checkpoint trained at the current target; then `--resume` with `kl_target=<new>` on the command
line (logged as a changed config), and record the decision in HANDOFF.
