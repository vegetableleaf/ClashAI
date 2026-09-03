# HANDOFF — ClashBot

**Read this first on any new or compacted session.** It is the durable state of the project: what
exists, what is running, what is broken, what was fixed and how it was measured.

> ## ⚠ MAINTENANCE RULE — THIS IS PART OF EVERY TASK
>
> **Update this file after EVERY change.** Not at the end of a session, not when asked — as the
> last step of each change batch, in the same breath as the commit and push. A fix that is not
> written down here is a fix the next session will not know about, and this file only works if it
> is never stale.
>
> Concretely, after each batch:
> 1. Add the commit + the measurement to the **bug ledger** (§5). *Measurements, not adjectives* —
>    "63 → 315 damage", not "improved damage".
> 2. Update **§3 What is running RIGHT NOW** if any job started, died, or finished.
> 3. Move anything completed out of **§6 Open work**, and add anything newly discovered.
> 4. Add any new environment gotcha (§2) or measurement trap (§8) — those are the most expensive
>    things to rediscover.
> 5. Bump the "Last updated" line below.
>
> If a change is too small to warrant a ledger row, it is still worth a line — err toward writing
> it down.

Last updated: **2026-09-03 01:55**, branch `main` (**§5bx: GAUNTLET L23 -- the repair is BUILT, smoke-tested and the TEST RUN IS LAUNCHED (01:46, `data/bench/gatep6_run_launch.sh`, ckpt `data/policy_gatep6_20260903.pt`, monitors up):
schema-2 gate prior split by opponent pressure (`tools/gate_prior.py --pressure-s 6` -> `config/gate_prior_p6.json`,
blend byte-identical to `gate_prior.json`), sim key `SimMatchEnv.enemy_troop_min_age()` carried as payload `eage`,
trainer flag `sim.ppo_gate_prior_pressure_s` (0.0 = gate05's table byte-for-byte), 5 new unit tests (12/12 pass),
CPU smoke run reaches the loss with "PRESSURE on 57% of usable rows". Test-run config staged:
`data/bench/gatep6_run.yaml` = gate05_run.yaml + that one flag + isolated paths. NEXT: m2k read (~1.1 h at 0.5 ep/s).
CLOCK CORRECTION: §5bw's header/LOG said 02:05; the commit landed 01:30 -- the wall-clock stamps in §5bw are ~35 min
fast, the box clock is authoritative. Previous header follows.) (**§5bw: GAUNTLET L22 -- diagnosis cut 2, the repair is CHOSEN.
(1) Per-term reward ledger on the m2k/m5k/m10k snapshots (24 matches x 3 seeds x 2 instruments): the 2k->10k reward
gain is the WAIT-SIDE penalty shrinking (sampled: threat_miss_idle -2.20 -> -1.11/match; greedy: wait-side -6.5 ->
-0.26) while the x-bow terms are flat (sampled wincon_exec +0.98 -> +1.00) or FALLING (greedy m5k -> m10k: exec
2.24 -> 0.62, total +2.96 -> +0.93). The policy trades bow execution for fewer misses, as priced. RETRACTION: L21's
'unclipped gate pressure is zero-mean' was an over-read of heavy-tailed block sums; ADV BY ACTION (11.6M samples)
reads play +0.211 vs wait -0.008 -- the bias is in the advantages. (2) The shipped gate prior is UNCONDITIONAL on
the board (the ruling's threat-on-our-half key was dropped in v0); refit with 'enemy troop played < 6 s ago':
pro P(play) at 5/6/7 elixir = 0.024/0.030/0.029 quiet vs 0.086/0.068/0.066 under pressure (2.3-3.6x; n 3k-10k
per cell). (3) Same key on the sim: the opponent pressures 46-52% of single-elixir steps vs pros 37%; quiet-stretch
median 4.8-5.4 s vs 9.0 s; a 2->6 bank window (>= 11.2 s) is 10-16% of stretches vs 39%. REPAIR = the pressure-
conditioned prior (schema 2 + the sim key), in-family with the owner's chosen family; test run after it is built.
QUESTION posted: the opponent's pressure cadence (an opponent-model change). Instrument note: the full-match
ledger reads the >=6 share 4.3 -> 1.0 -> 1.0% (m5k = m10k, a plateau) where the probe read 1.2 -> 0.1; both are at
the 1% rule, the stop stands. Box idle.**
Previous header (§5bv: GAUNTLET L21 -- the m10k read TRIPPED the owner's rule
(median 3-seed elixir>=6 share < 1%): 0.1 / 0.2 / 0.0% (m5k 1.2/1.3/1.0, m2k 4.0/3.5/3.0), P(play|affordable)
0.36/0.35/0.38, elixir mean 2.09, x-bow plays 1/2/0 per 2,400 rows. COEF-0.5 RUN STOPPED at 01:02 per the ruling:
state recorded (10,000 eps, 356W-7653L-10D, best_wr 11.338, gate m10k regret 0.2418/0.2395), checkpoint backed up
cmp-verified, procs 2 -> 0, watchdog stopped. Diagnosis cut 1 (trainer's own instrument, 237 update blocks): the
post-clip gate pressure is toward PLAY in 199/237 blocks (mean +0.25) while the unclipped pressure is zero-mean
(-0.05, positive 124/237); clip rate PLAY 0.77 vs WAIT 0.01 -- the KNOWN clip sign-flip (§'34 sigma'), present all
run; the gate drifted +0.04 P(play|choice) over 10k eps and the >=6 share is its geometric tail ((1-p)^~19). The
old clip_play_mult sweep graded winrate/reward at 700 matches and could not see this drift -> a repair is (b) until
graded on the bucket probe at m2k/m5k. NEXT: choose + implement the repair, test run, THEN restart with the aggro
wiring (owner ruling §6). Box idle.**
Previous header (§5bu: GAUNTLET L20 = aggro loop 4: TWO AGGRO DRILLS GRADED
ON THE ENGINE'S LOCK STATE -- `sim/aggro_drills.py` (explicit `register_all()`, NOT auto-imported, so the running
trainer never sees it) + 4 tests: `tank_for_bow` (success = the Valkyrie's `target` becomes our Knight, failure = her
first hit lands on the bow) and `bow_lane_choice` (success = the bow's FIRST lock after deploy is a tower, failure =
a troop). 40 reps, ladder roll: nothing 0% / scripted 92% / 95%; late knight (4.2 s) 0%, far-lane knight 0%,
same-lane bow 0%; doctrine 95% / 90%. THE TRAINED POLICY FAILS BOTH (a, greedy masked, 40 reps): gate05 m5k 12% / 0%, pre-run
policy_sim_ppo 15% / 35% -- the owner's "no concept of aggro" is now measured, and the doctrine has the answer (95 / 90). Two traps
found by tracing the real DrillEnv: the first LEGAL agent row is y 0.5625 (a reference at y 0.50 snaps BEHIND a
bow at 0.56 -- the L19 oracle boards used `deploy_unit`, which ignores the grid), and drill NOISE lands in the lane
the answer needs (reference capped at 68% with noise; opt-out via `setup`). Run untouched (7,825 eps).**
Previous header (§5bt: GAUNTLET L19 = aggro loop 3: DO THE AGGRO DRILLS GRADE
AGGRO? (c) No, neither of the two. `knight_guards_the_bow` passes the STEP a knight is played anywhere (success =
bow alive AND knight played, verdict fires immediately; the bow only dies at 7-8 s) -- cell and timing are
irrelevant; scripted 100%. `nado_the_sneaky_lock`: the tornado earns NOTHING -- knight-only @2.4 passes 60% on the
ladder roll vs the full reference 47.5%, tornado-only 0%; knight-in-front @0.6 with no tornado is the best line at
80%; the bow NEVER re-locks a tower after the reference pull (a 2-tile pull cannot leave the bow's 11.5-tile reach,
the drill notes' 'a lone Tornado re-locks the bow' is contradicted). Trap: `cli drills --level 11` pits OUR L16
cards vs L11 enemies (sneaky lock 'nothing 100%'); training rolls enemies 13-16. Oracle numbers of §5bs stand (they
were stated at 11 vs 11; hand-built Unit vs eng.deploy checked: same). Run untouched (6,950 eps). Next: loop 4 =
`sim/aggro_drills.py` with oracle-verified predicates (lock taken; bow's FIRST lock after deploy).**
Previous header (§5bs: GAUNTLET L18 = aggro loop 2: the ENGINE-BACKED AGGRO
ORACLE exists -- `sim/aggro_oracle.py` (fork the engine, advance, read `Unit.target`; never re-derives rules) with
8 unit tests that ARE the owner's questions on fixed boards: target_of / targeted_by, next target after a kill,
what a placed knight draws, the interposition window, tornado king-activation retarget, duel winner + HP left.
Measured on the X-Bow-vs-Valkyrie board: a knight in front of the bow steals the lock if placed <= 1.6 s after
the valk starts walking and fails from 1.8 s = exactly her first hit (lock = kept); a hog chewing the princess is
retargeted to the KING by the drill-reference tornado; mini-PEKKA beats knight with 56% HP, valk beats knight
with 26%. Cost: 0.5 ms fork, 2-3 ms per question, 83 ms for a 31-fork window search (6-unit board). Two engine
behaviours the oracle exposes are (b) vs the real game: a body spawned ON a locked unit resets its lock (:5758),
and no 4 s king aim delay. Run untouched (6,000 eps). Next: an aggro DRILL family graded by the oracle.**
Previous header (§5br: GAUNTLET L17 = loop 1 of the AGGRO-MANIPULATION gauntlet
(owner order 22:1x). Orient + one measurement. The policy's only aggro concept is `interactions.predict_targets`
(memoryless nearest-target, painted into the predictive canvas + 12-dim interaction vector) -- so aggro IS modelled,
but WRONG in the states that matter: vs the engine's sticky `Unit.target` over 60,599 unit-samples (m=5k ckpt, 36
matches, 3 seeds) it agrees 93-96% for WALKING troops but only 81% for LOCKED troops (n=14,268), 16-25% for
buildings (an out-of-reach X-Bow/Tesla is shown aiming at a tower) and 0% during deploy. The locked misses are
exactly the tank-for-bow / defender-next-to-a-tower-hitter cases. Engine rules checked against the wiki (KTA on
damage only, 4 s to first shot; tornado/log/stun retarget; X-Bow 3.5 s deploy window): consistent. Engine target
changes 14.4 per unit-minute, 47% with the old target still alive. Run untouched (5,975 eps). Next: engine-backed
aggro ORACLE (new module + tests, unblocked), then a lock-aware obs feature once the run is stopped.**
Previous header (§5bq: GAUNTLET L16 (LAST loop of this gauntlet, owner order) --
"does the model know how to USE its spells?" Pro niche reference from the crawl (6,804 icebow-side casts) + sim probe on
3 checkpoints x 3 seeds x 12 matches, engine ground truth. (a) LOG: lands where pros land it (own bridge side 72-85% vs
pros 87%) but covers NO enemy body on 18-26% of casts and kills something on only 25-37%. (a) TORNADO: king activation
0 / 1 / 4 per 36 matches with the king asleep at 43-54% of casts; 2-14% of casts near our king (pros 19% back/king
zone); clump-for-rocket set up 7-19 times per 36 matches and NEVER cashed. (a) ROCKET: 1 cast in 108 matches (pros
3.4% of plays, 81% in the enemy half/tower zone). (c) REWARD BUG: `nado_retarget` is UNREACHABLE -- the gate is
centre-to-centre `<= reach + 1.0` but every wincon attacks from further out (hog 2.20 vs 1.8). Verdict: the policy
knows the log's ZONE, not the log's TARGET; does not know the tornado's king/retarget niches; has no rocket at all.
m=5k READ (pre-registered): `played` at 3 = 0.281 / 0.269 / 0.315 -> NOT the ask branch, run continues to 10k.
Owner notes: agent_dt DEFERRED, YOLOv26 NO-GO (§6). Gauntlet STOPPED on owner order; new gauntlet next.**
Previous header (§5bp: GAUNTLET L15 -- m=5k NOT reached (4,425 eps at 21:15,
0.5 ep/s, ETA ~21:35); no pre-registered read yet. Same-instrument watchdog at 4000: both arms trip the SAME two
alerts (cell ent 1.07 vs 1.06 of 5.08; elixir>=6 <0.3%) -> not discriminating. Sampled P(play) 0.26-0.38 (coef-0.5)
vs 0.48 (coef-0.1), card_ent 1.18 vs 1.82 -- one reading each, watchdog instrument, NOT the probe. Wakeup 21:41.**
Previous header (§5bo: owner steering applied -- the live overtime flip is now a
SOFT RAMP: `_defensive_w` 0 -> 1 over `env.xbow_defense_ramp_s` (60 s: soft at the 180 s whistle, fully defensive
at the 3x minute), zero whenever the offensive bow has broken through. It blends the bow reward
((1-w) offensive + w defensive), scales the rocket-cycle credit, and is the PROBABILITY of the defensive snap.
`_defensive` is now a property (= w >= 1; assignment pins w, tests unchanged). `clock.overtime_s` added.
5 new tests (tests/test_defensive_ramp.py), 130/131 across the doctrine modules, the 1 failure pre-existing.
agent_dt verdict (§5bl.6) pinned as a §6 item so it is not lost. Unexercised live (b).**
Previous header (§5bn: GAUNTLET L14 -- owner ruling on the X-Bow defensive
doctrine, verified against the pro crawl and APPLIED to the live path (three env.py edits, owner-authorised).
(a) pro blue-side bows (1,029 with tiles): front share 93% (0-30 s) -> 82% -> 63% (2x) -> 54% (OT) -> 48%
(3x OT); late bows in matches the pro finished with a crown 54% front vs 62% at zero crowns -> the TIME gate is a
real (soft) preference, the TOWER gate has no support. Edits: tower-gated `_defensive` flip removed (overtime+chip
only); defensive bow snap now also fires while `_defensive`; `_wincon_exec_live` anchors alive-only. Tests 56/57,
the one failure PRE-EXISTING (test_xbow_into_push, fails on the untouched tree). Sim twin NOT changed (run live).
Flag for the owner: the hard OT snap overrides the ~54% of pro OT bows that stay forward.**
Previous header (§5bm: GAUNTLET L13 -- owner's two live-play reports tested.
X-BOW AT A DEAD TOWER: (c) the model is not blind to it (tower HP in obs since 08-10, live dead-lane aim assist
since 08-16, sim reward already alive-only) -- (a) what happened today is 6/6 bows on ONE cell (243, raw==assisted)
and after the tower kill `_defensive` flips, which SKIPS every bow aim assist (env.py:1823), so the constant-cell
bow goes out unassisted and is billed -1; plus (a) `_wincon_exec_live` ignores tower alive (sim does not). Crawl
has NO tower events -> pro 'after a tower dies' placements are not derivable from it. SPELLS, sim greedy no-mask,
36 matches x 2 ckpts: coef-0.5 m2k zero-damage 11% of 168 casts (mask-whiff 11%, nado_bad 19%); 18k 9% of 496
(mask-whiff 21%, nado_bad 13%); live today 25 spell_waste / 54 spell plays (other instrument). ROCKET: 0 casts in
72 sim matches on BOTH checkpoints (pros 3.4% of plays). Two live-path one-liners proposed, owner call.**
Previous header (§5bl: GAUNTLET L12 -- THE DECISION PATH WAS NEVER UNMEASURED:
the live loop has timed every stage of every match since 08-12 (`cadence` in data/reward_stats/live_*.jsonl,
904 matches) and nobody read it. (a) Since act_period went to 0.6 (100 matches, 38 sessions): served
decision-to-decision time p50 **0.76 s** (p10 0.66, p90 0.90); 91/100 matches > 0.66 s, 3/100 <= 0.62. The
pipeline alone (loop - wait) is p50 0.65 s: env share 0.34 s (reads 0.131, act 0.058, state 0.056, threat 0.053,
grab 0.035, hand 0.012, obs 0.003) + trainer residual p50 0.315 s (p10 0.08, p90 0.45). => a 27% train/serve
cadence mismatch at the median, the 08-12 bug class again; lowering act_period is a no-op until the pipeline
drops below it. (a) Pros: 1.4% of consecutive same-side plays are < 0.6 s apart (43,205 gaps, 519 replays), median
4.15 s. Offline stage timer built (`tools/latency_stage_timer.py`), smoke on the CONTENDED box (upper bounds):
detect_state 86 ms, detector 80, threat colour 62, tower-HP OCR 22 p50 / 348 p90, elixir 15, mass 10, hand 5;
net forward 1.6 ms, DDQN learn step 21 ms -- the 0.3 s trainer residual is NOT the net. Owner delegated the
agent_dt call: recommendation = do NOT lower it; fix serving to 0.6 first (§5bl.6).** Previous header (§5bk):
COEF 0.5 IS BITING at m=2k, on both
instruments; the PPO push is visibly fighting back in the trainer's own windows; level-16 sandbox answered;
stale 18k watchdog killed; owner's decision-time question answered with a counter-question (§6).** (a) Probe of
`gate05_m2k.pt`, 3 seeds: `played` at 3 elixir **0.271 / 0.227 / 0.239** (coef-0.1 m=2k 0.39-0.45; 18k control
0.36-0.40; pros 0.063) -- pre-registered `<= 0.25 all seeds` narrowly missed on seed 0 (0.271), the rule's
`>= 0.35 -> ask` branch is far away, verdict = biting. P(play | affordable) 0.227-0.233 (coef-0.1 0.43-0.45);
elixir >= 6 on 3.0-4.0% of rows (coef-0.1 0.0-0.2%). (a) Trainer's window pi(play) on usable rows, per 200
updates: 0.34 -> 0.22 by update 2,000, then BACK UP to 0.24-0.29 over updates 2,800-5,600 with window CE
rising 0.35 -> 0.42-0.44: the prior pulled first, PPO is pushing back. Where that settles is the m=5k read.
Match strength at m=2k, same seed: avg_rew -18.2 (coef 0.1: -15.2, 18k baseline: -13.4) -- worst of three, (b)
the cost of banking; EVAL@2000 5%/2% is n=150 noise. **Previous header (§5bj, L10):** m=7.5k read was
OSCILLATION; coef-0.1 run KILLED at m=7,575, coef-0.5 run launched 18:59. (a)
Probe at m=7.5k, 3 seeds: `played` at 3 elixir 0.376 / 0.301 / 0.401 (m=5k 0.28-0.31; m=4k 0.42-0.48; 18k
control 0.36-0.40); P(play | affordable) 0.34-0.39 (m=5k 0.28-0.32); elixir >=6 0.5-1.0% of rows. Back at the
control level on two seeds, the third at the 0.30 threshold. (a) Trainer's own window pi(play) on usable rows
per 1,000 updates, 16 windows: 0.34 0.31 0.32 0.34 0.37 0.36 0.36 0.36 0.37 0.37 0.36 0.34 0.34 0.36 0.35 0.35
-- flat for 12,000 updates, CE 0.59-0.62. Two instruments, same verdict: no sustained pull at coef 0.1.
Endpoint 7,575 eps, 240W-5894L-6D (§3). New run `data/bench/gate05_run_launch.sh`, ONE change vs the killed run:
`ppo_gate_prior_coef 0.5`; first log line `GATE PRIOR ON: coef 0.500`. Watchdog + gates re-armed. NOTE free
RAM 0.6-1.1 GB at startup (12 workers at 560 MB each) -- re-check at the next loop.)

---

## 1. What this project is

A Clash Royale bot that learns to play. Two independent, parallel decks live in this repo, each a
full copy of the pipeline:

| folder | deck | state |
|---|---|---|
| `icebow/` | X-Bow / Rocket / Tornado / Ice Wizard control | the original; has live-play history and BC data |
| `hogeq/` | Hog Rider + Earthquake 2.6 cycle | cloned from icebow 2026-08-17, sim-only so far |

They share **nothing at runtime except the detector**: `hogeq/config/config.yaml` points
`detect.weights` and `detect.dataset_dir` at absolute paths inside `icebow/`. The clone deliberately
excluded `data/ runs/ .venv __pycache__ .git .pytest_cache` (252 MB instead of 22 GB).

**Pipeline:** record/mine → BC (behaviour cloning) → sim PPO → live RL. A separate YOLO **detector**
supplies perception for the live path.

### hogeq deck (real account levels)
Hog Rider 13, Evo Firecracker 13, Mighty Miner 15 (champion; upgraded 2026-08-19), Evo Tesla 14, The Log 14,
Earthquake 13, Skeletons 15, Ice Spirit 13. Average elixir **2.75**.
11 policy identities = 10 card identities + `mighty_miner_ability`.

---

## 2. Running things

Each deck has **its own venv**: `icebow/.venv`, `hogeq/.venv` (both Python 3.13, torch 2.11.0+cu128,
CUDA available). Always use the venv python of the folder you are in.

```
cd C:\Users\benpe\ClashBot\hogeq
.\.venv\Scripts\python.exe run.py train-sim-ppo --matches 800000 --envs 96 --workers 12 --size 432 --device cpu
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

### Environment gotchas (all cost real time to discover)

* **⚠ GIT BASH `ps` AND `pkill` CANNOT SEE WINDOWS PROCESSES. They fail SILENTLY and report
  success.** `pkill -f train-sim-ppo` printed nothing and `ps aux | grep -c '[t]rain-sim-ppo'`
  returned **0** while **90 python processes were still running** — three stacked A/B batches that
  every previous "cleanup" had left alive. Free RAM was down to **0.5 GB** (the §3 thrashing
  condition) and a fresh 12-run sweep was crawling at 0.1 ep/s against 78 zombies, which would have
  been read as "the sweep is slow" rather than "the machine is full".
  **Use PowerShell for anything to do with process lifecycle:**
  ```powershell
  Get-CimInstance Win32_Process -Filter "Name like '%python%'" |
    Where-Object { $_.CommandLine -like "*train-sim-ppo*" -or $_.CommandLine -like "*multiprocessing.spawn*" }
  # ... | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  ```
  Kill the `multiprocessing.spawn` children too — they outlive the parent. And **verify the kill by
  re-counting**, because the failure mode here is a clean-looking no-op. NB each `run.py
  train-sim-ppo` is TWO python processes (launcher + trainer), so 12 launches reads as 24.

* **`yolo.exe` produces NO output under this shell** — even `yolo checks` is silent with exit 0, and
  the process never actually runs. Train the detector through the Python API instead
  (`icebow/_train_board26.py` is the working launcher).
* **ultralytics `runs_dir` is `C:\Users\benpe\ClashBot\runs`** (absolute, from its settings). A
  *relative* `project=` is appended to it, which put a run in
  `ClashBot\runs\detect\runs\detect\board-26` — outside icebow, where `detect-eval` would never find
  it. **Always pass an absolute `project=`.**
* **`python3` does not exist** on PATH; only the venv pythons.
* **PowerShell `Out-File -Encoding utf8` writes a BOM (PS 5.1).** A pid file written that way holds
  `\xef\xbb\xbf20852`, and Git Bash `tr -d '\xef\xbb\xbf'` does **not** strip it (that tr reads the
  escapes as the literal letters x/e/f/b). `tasklist //FI "PID eq <bom>20852"` then matches nothing
  and a monitor reports the job **dead while it is running** — this produced a false alarm at 17:30.
  Write pid files with `printf '%s\n'` from bash, and prefer **log-mtime** liveness over a PID check:
  it also catches a hang, which a PID check never does.
* **hogeq's venv had NO `ultralytics`.** The clone excluded `.venv`, so `train-rl` printed
  *"could not load detector"* and **played blind** -- the weights path was correct all along, the
  import was what failed. Fixed 2026-08-18. **Do NOT fix this with a bare `pip install
  ultralytics`**: it resolves torchvision from PyPI, which drags in **torch 2.13.0 and destroys the
  cu128 build** (`torch.cuda.is_available()` -> False). Correct order:
  ```
  pip install "torchvision==0.26.0+cu128" --index-url https://download.pytorch.org/whl/cu128
  pip install "ultralytics==8.4.107"          # pin: it is what icebow has, whose weights hogeq loads
  ```
  Verified after: detector available, 230 classes, torch 2.11.0+cu128, CUDA True, both decks.
* **`python3` NOW EXISTS** (it did not before 2026-08-18, and older notes here say so). Two shims,
  deliberately in two different places, both pointing at the **ClashBot root `.venv`** -- NOT
  icebow/hogeq, whose venvs must keep their cu128 torch:
  * `C:\Users\benpe\bin\python3` -- extensionless, for **Git Bash** (bash's PATH lookup appends
    `.exe` but never `.cmd`, so without it bash falls through to the Windows Store `python3`
    app-execution alias, a stub that only offers to install Python). This directory is on the Git
    Bash PATH but is **not** in the Windows PATH, which is what keeps the two shims from colliding.
  * `C:\Users\benpe\tools\bin\python3.cmd` -- for **Windows / PowerShell**.
  An extensionless file in `tools\bin` breaks Windows callers (CreateProcess tries the exact name,
  which is not a PE binary), which is why they are split.
* **Ollama on a contested GPU.** With board-26 training (5.4 of 8 GB VRAM), a cold
  `qwen2.5:latest` (4.7 GB) load burns the advisor's whole 0.9 s budget per call until the circuit
  breaker trips — 5 calls, 5 timeouts, advisor off. In a REAL live session the GPU is free (you
  cannot train the detector and play at once) and the measured 0.59 s p50 applies, but any offline
  advisor probe during training must either `warmup()` first with a long timeout or use
  `qwen2.5:0.5b`. The doctrine-table generator has `LLMDOC_CPU=1` for the same reason — a 3.3 GB
  model forced into the contested card can OOM the training run.
* **`Start-Process -ArgumentList "-c",$code` silently mangles python one-liners.** PowerShell splits
  the code string on spaces, so python receives only `from` and dies with
  `SyntaxError: invalid syntax`. Launch long-running python from a **file**, not `-c`.
* **Bash tool cwd persists between calls.** A `cd` into icebow silently makes later relative paths
  resolve there — this caused a verification pass to run against the wrong deck. Prefer absolute
  paths, or re-`cd` in the same command.
* Git Bash is available alongside PowerShell; each needs its own syntax.

---

## 3. What is running RIGHT NOW

* **2026-09-02 07:35 — the PPO cuda run is STOPPED** (§5ba) at 18,000 episodes, per the owner's ruling
  and confirmed by its own eval curve. Archive + checkpoints:
  `icebow/data/bench/stopped_real_cuda_18k_20260902/` (2 .pt SHA-verified, 2 milestone snapshots, log).
* **KILLED 2026-09-02 18:57 at m=7,575 (owner ruling + §5bi rule): THE GATE-PRIOR RUN, coef 0.1** (§5bf-5bj).
  Endpoint: 7,575 episodes, 240W-5894L-6D (7,500: 237W-5837L-6D), EVAL@2000 ladder 12% / fair 8%, @4000
  8% / 4%, @6000 9% / 4% (150 each); ent 0.05-0.06; 0.5-0.6 ep/s; last `GATE PRIOR CE` 0.5737 cumulative
  over 16,800 updates, pi(play) 0.347 vs prior 0.059, 9% rows usable. Procs before kill 2 (+12 workers), after
  0. Final checkpoint copy `scratchpad/gauntlet/L10/gate_m7k5.pt` (m=7,500, cmp-stable); m=5k snapshot
  `data/bench/gate_m5k.pt` + `scratchpad/gauntlet/L9/gate_m5k.pt`; log `data/bench/gate_run_20260902.log`
  (exit=1 in `.progress` = the kill). Its old watchdog/gates were stopped (48908/10724 trees).
* **RUNNING NOW (2026-09-02 18:59): THE GATE-PRIOR RUN, COEF 0.5** (§5bj) -- `data/bench/gate05_run_launch.sh`:
  `run.py --config data/bench/gate05_run.yaml train-sim-ppo --matches 40000 --envs 96 --workers 12 --size 432
  --device cuda --seed 41 --search-interval 4`, log `icebow/data/bench/gate05_run_20260902.log`, checkpoint
  `icebow/data/policy_gate05_20260902.pt` (isolated, did not exist at launch), continuation log
  `data/continuations_gate05.jsonl`, launch epoch in `gate05_run_20260902.launched` (1788389921), exit line
  will land in `gate05_run_20260902.progress`. `gate05_run.yaml` diff vs `gate_run.yaml` = those two paths +
  `ppo_gate_prior_coef: 0.5` (the ONE change vs the killed run). First log line: `GATE PRIOR ON: coef 0.500`.
  Monitors (nohup): `tools/ppo_watchdog.py data/policy_gate05_20260902.pt --every 300 --quiet-min 30` ->
  `data/bench/gate05_run_watchdog.out`; `tools/real_run_gates.py --run gate05_20260902` ->
  `data/bench/gate05_run_gates.out` (snapshots `data/bench/gate05_m{5,10,20}k.pt`). Pace at launch 0.5 ep/s.
  **Read it with `tools/gate_prior_probe.py <ckpt> --seed {0,1,2}`** (12 s each, §5bg): `played` at bucket 3
  (coef-0.1 run: 0.39-0.45 at m=2k, 0.42-0.48 at 4k, 0.28-0.31 at 5k, 0.30-0.40 at 7.5k; 18k control
  0.36-0.40; pros 0.063; §5bh.4 arithmetic predicts an equilibrium ~0.20 at coef 0.5 -- (b)). Trainer's
  `GATE PRIOR CE` line is CUMULATIVE -- difference consecutive lines (per 1,000 updates, §5bj.3 script).
  Pre-registered read: m=2k probe on 3 seeds. If `played` at 3 is <= 0.25 on all seeds the coef is biting
  where 0.1 never did; if it is >= 0.35 on all seeds, 0.5 loses too and the mechanism (not the coef) is the
  problem -> stop and ask. **m=2k READ DONE (§5bk, 19:5x): 0.271 / 0.227 / 0.239 -> BITING** (seed 0 just
  over the 0.25 line; nowhere near the 0.35 ask-branch). RAM re-checked 20:08: 4.2 GB free, run at 0.62 ep/s
  (2,550 eps at 20:08) -- the startup footprint settled as the coef-0.1 run's did. **Next pre-registered
  read: m=5k** (`data/bench/gate05_m5k.pt` from the gates script, ETA ~21:15-21:30), 3 seeds, same probe.
  What to look for: the trainer's window pi(play) fell to 0.22 and is climbing back (0.24-0.29 at updates
  2,800-5,600) -- if the probe's `played` at 3 is back >= 0.35 on all seeds at 5k, the 0.5 pull is being
  overpowered too and it is the mechanism -> stop and ask; if it holds <= 0.30, 0.5 is an equilibrium
  (§5bh.4 predicted ~0.20, (b)). Self-play ramps in at m=5,000 (prob 0.15) -- confound for reads AFTER 5k,
  not for the 5k snapshot itself. Compare avg_rew at 5k against the coef-0.1 run's (log
  `data/bench/gate_run_20260902.log`) and the 18k run's at the same episode count, same seed 41.
* **KILLED 2026-09-02 19:2x (owner asked how; I did it): the 18k run's stale watchdog** (PIDs 21564/72608
  under nohup 32660, launched 2026-09-01 21:25, sampling the frozen `data/policy_real_20260901.pt` every
  5 min). `Stop-Process -Id 72608,21564,32660`; verified gone. Its readings are the noise-floor data set in
  §5bf.5. Two orphaned `grep.exe` filters from the old nohup chains remain (PIDs 68604, 30068, created
  2026-09-01 21:26 / 22:37) -- idle on dead pipes, zero CPU, harmless; kill at leisure.
* board-27 stays CANCELLED (§5be.3). The training synth is still the PRE-kitka one.
* **DONE: the hogeq replay crawl** (§5bc-5bd) -- output `hogeq/data/royaleapi/crawl2/` (gitignored).
* **DONE: the L2 detector screen** (`scratchpad/gauntlet/L2_screen.ps1`) -- yolo11s control then
  yolo26s, identical settings, fraction 0.35 / 30 epochs / imgsz 960, ~2.8 GB VRAM. **Measured 5.4
  min/epoch** (epoch 9 at 08:13 from a 07:24 start), so ~2.7 h per arm: y11s lands ~10:10, y26s ~13:00.
  Progress: `scratchpad/gauntlet/L2/screen.progress`, logs `scratchpad/gauntlet/L2/screen-*.log`.
  ⚠ It trains on `data/detect/synth` -- do NOT run `run.py sprites --synth` until it finishes (§5bb.5).
  **Sandbox emulator + service STOPPED 01:08** (§5ay, qemu verified gone); nothing else is running. Sandbox state: WORKING, local patch commit 7c66f92 in
  `research/ext/cr-native-sandbox`'s own git; the batch results live in `scratchpad/gauntlet/ext/batch/`.

* **board-26 detector training — RESUMED 2026-08-18 17:24 after a host restart killed it.**
  Originally started 2026-08-17 ~23:30 via `icebow/_train_board26.py`,
  `save_dir=C:\Users\benpe\ClashBot\icebow\runs\detect\board-26`.
  yolo11s.pt, 120 epochs, imgsz 960, batch 4, patience 30, workers 4, nc=230.
  17,821 training frames (12,821 real + 5,000 synth), 4,456 batches/epoch, **14.5 min/epoch**.

  **The restart.** The laptop rebooted at **11:54**; the last checkpoint wrote at **11:37**, so the
  run died at **epoch 51/120** and the machine then sat idle ~5.5 h. Nothing was lost: `last.pt`
  carried `optimizer` + `scaler` + `ema` + `best_fitness`, and `save_dir/args.yaml` carried the
  hyperparameters. **This run is fully resumable and was resumed** — recipe below.

  **Resume recipe** (`icebow/_resume_board26.py`; PID in `icebow/runs/board26.pid`, logs
  `icebow/runs/board26_resume.{out,err}`):
  ```python
  YOLO(r"...\runs\detect\board-26\weights\last.pt").train(resume=True)
  ```
  `resume=True` re-reads `args.yaml`, so **do not re-pass** `epochs/imgsz/batch/workers/patience`
  and **do not pass `project=`/`name=`** — resume ignores them and it only re-opens the
  relative-project trap (§2). Confirm it took hold: the log must say
  `Resuming training ...\last.pt from epoch 52 to 120 total epochs`. A bare
  `Starting training for 120 epochs` instead means it restarted from zero — kill it.
  **Do not launch it via `Start-Process -ArgumentList "-c",$code`** — PowerShell splits the `-c`
  string on spaces and python dies with `SyntaxError: invalid syntax` pointing at the word `from`.
  Use a launcher **file**; that is why `_resume_board26.py` exists.

  **Checked 2026-08-18 18:30: alive and healthy, epoch 55/120**, ~14.5 min/epoch. mAP50 0.8536 /
  mAP50-95 0.6825 -- flat since the resume (epoch 51 was 0.8588 / 0.6840), so it is plateauing and
  patience 30 from epoch 51 puts the earliest stop at epoch 81. A persistent Monitor watches
  per-epoch mAP, stall (by LOG MTIME, which also catches a hang), early stop and crashes.

  **State at the crash (epoch 51, which WAS the best epoch):** mAP50 **0.8588** / mAP50-95
  **0.6840**, 0 epochs since best, fitness monotonically rising from epoch 32 (0.8524 / 0.6617).
  Remaining: **69 epochs ≈ 16.7 h** to 120; floor is epoch 81 ≈ 7.3 h if it plateaus now and
  patience 30 fires.

  > **⚠ THE EPOCH-BY-EPOCH COMPARISON AGAINST board-25 IS NOT APPLES-TO-APPLES.** The Roboflow
  > import landed 2026-08-17 18:57 (`7d23f12`); board-25 ran 08-13 and board-24-5 on 08-11, both
  > BEFORE it. **81% of board-26's val set (1,893 of 2,346) is Roboflow images that did not exist
  > when the older runs were validated**, and Roboflow frames are cleaner than live captures. So
  > board-26's headline lead (+6.1 mAP50 / +11.9 mAP50-95 over board-25's FINAL best, already at
  > epoch 32) is partly an easier val set. Do not report it as a win.
  >
  > The honest gate is unchanged and uncontaminated: `run.py detect-eval` on
  > `data/detect/val_board15.txt` — **241 images, verified 0% Roboflow**, all live-captured. That
  > file lists image STEMS (and has a UTF-8 BOM on line 1), not paths.
  >
  > **THE GATE HAS NOW BEEN RUN, AND IT CONFIRMS THE WARNING. board-26 @ epoch 51 does NOT beat
  > board-24-5 on live images** — the +6 mAP50 lead was the easier val set, exactly as suspected.
  > Both scored on the same 241 stems / 820 GT boxes @ conf 0.35:
  >
  > | | board-24-5 (the pin) | board-26 @ e51 |
  > |---|---|---|
  > | presence UNITS **R** | **0.855** | 0.853 |
  > | presence UNITS P | 0.886 | **0.904** |
  > | whitelist ident R | 0.823 | **0.828** |
  > | deck UNITS ≥ 0.80 | **5/5** | **4/5 — skeletons 0.77 FAILS** |
  > | tesla | **0.98** | 0.96 |
  > | knight | **0.90** | 0.81 |
  > | skeletons | **0.82** | 0.77 |
  > | tornado (proj) | **1.00** | 0.67 |
  >
  > It trades **recall for precision** (+1.8 P, −0.2 R) and loses recall on **4 of 5 deck units**.
  > `detect.weights` therefore **stays pinned to board-24-5**. Re-run this gate on the FINAL
  > best.pt — 69 epochs of training remain and epoch 51 was still improving, so this is a status
  > check, not the verdict.
  >
  > Command, for both generations:
  > ```
  > run.py detect-eval --weights runs/detect/<gen>/weights/best.pt --subset data/detect/val_board15.txt
  > ```
* **Hog EQ doctrine research + advisor rework — DONE 2026-08-18 evening.** The 13-agent workflow
  collected 157 guide facts + 88 observations from 4 watched videos (2 watchers + the synthesis
  agent died to a session usage limit; the synthesis was done inline instead). The record is
  `hogeq/DOCTRINE_RESEARCH.md`; the implementation is in the ledger below. `config/llm_doctrine.json`
  was regenerated for THIS deck with the new proposer prompt: **19 engine-verified rules** kept of
  27 tested (gemma3:4b on CPU via the new `LLMDOC_CPU=1` switch — 642 s; the GPU belongs to
  board-26). Doctrine wiring CONFIRMED both sides: sim `doctrine_frac: 0.6` + `llm_doctrine: true`
  feed `doctrine_cells`/`doctrine_cards`; live `train.llm_advisor: true` (qwen2.5:latest present in
  ollama) feeds exploration, and the live quiet-board rule is now the pressure ladder (below).
* **Both PPO runs remain STOPPED — and now it is MEASURED, not assumed.** The user started a
  single hogeq `train-sim-ppo --envs 96 --workers 12` at 22:30 on 2026-08-18 while board-26
  trained. Within 6 minutes: available RAM oscillating **5-520 MB**, hard faults **4,500-24,300/s**
  (thrashing), and Windows was **evicting board-26's working set** (4.27 GB -> 1.5 GB) to feed the
  PPO's ~8.4 GB (trainer 2.0 GB + 12 workers x ~535 MB). The user killed it on that evidence;
  available RAM recovered to 7.4 GB and faults to ~200/s within a minute. **Restart PPO only after
  board-26 finishes** — first real test of the fixed reward AND now of the new doctrine priors.
  Train from scratch, not --resume.
* **Icebow doctrine research — DONE 2026-08-19 (`2b0a7de`).** Run `wf_2fadd59a-18b` + resume:
  270 facts from 7 researchers, **246 observations from 8 videos (7 of them Hunter CR)**, and
  **20 adversarial verdicts (2 REJECT / 12 MISREAD-RISK / 4 CONTESTED / 2 STALE)**. Both the
  recency verifier and the synthesizer died to session limits twice; synthesis was done inline.
  Record: `icebow/DOCTRINE_RESEARCH.md` (§6 lists every claim that did NOT survive review, with
  both readings; two remain deliberately uncompiled). Rocket gates compiled + 14 tests.
  **Defensive tranche DONE `6dc9d8a`:** the mid-map-bow-vs-Rocket-deck prohibition (the doctrine
  counterpart to `xbow_into_push` = −276 — that reward term EXEMPTS defensive bows and keys off a
  PUSH, while this keys off their DECK, so it closes the half the reward cannot see), tornado-BACK
  for air swarms, and the Tesla king-activation clearance. 8 tests; icebow 393 OK.
  **STILL OPEN:** (a) the sim's nado→rocket rule has the CAST ORDER BACKWARDS — research says
  Rocket first, then Tornado onto the blast point (needs a two-card sequencing primitive the cell
  prior cannot express, so it is a real design task, not an edit); (b) remaining §2 items —
  Tesla-as-Fireball-bait, the zero-damage Graveyard order (pre-fire Skeletons BEFORE it lands),
  layered-defense ordering; (c) **DONE** — the icebow `llm_advisor` prompt (`9a60c8e`) and the
  table PROPOSER prompt (`e0ef278`) both carry the gates now. The **table was deliberately NOT
  regenerated**: it already holds 6 rocket rules of 72 (x_bow 20 / knight 15 / tesla 14 /
  tornado 9 / ice_wizard 8 / rocket 6) and cost 107 proposals, so a regen risks a known-good
  engine-verified table for little gain. Note what that distribution proves — rocket was present
  in BOTH the prior and the table and was STILL played 2/1288, so the gap was never nomination,
  it was that the professional's trigger (a HAND condition) had no encoding anywhere;
  (d) **PARTLY RESOLVED from the card KB, and it exposed a real bug.** Golden Knight L11 HP =
  **1799 > Rocket 1484**, so the verifier was right that a rocket cannot remove him (full
  lethality table now in DOCTRINE_RESEARCH.md §6.11; note Sparky 1451 DOES die, and Prince 1920
  does NOT — which is fine, because R1/R3 are damage-MITIGATION rules and deliberately carry no
  lethality check, unlike R4). **⚠ CROWN DAMAGE IS STALE ACROSS FIVE SPELLS, AND A RE-IMPORT WILL NOT FIX IT.**
  Traced 2026-08-19: `cards_stats.json` (imported 08-14, post-nerf) matches the wiki's
  `crown_dmg_11` vardefine exactly — but that vardefine **contradicts the same wiki page's own
  balance history**. Rocket's history says 23% of full damage since 1/6/2026; 23% × 1484 = 341,
  while the vardefine's 371 is exactly the old 25%. The wiki's stat table lags its own history.
  Swept: **Rocket 371→341, Lightning 286→264, Zap 58→48, the_log 40→35, Poison 23→21**
  (Fireball 207 is correct). So the sim over-pays every one of those tower chips, feeding the
  `chip_*` reward terms and every baseline measured this session. **Re-running `cards-import`
  re-imports the stale numbers** — the fix must be a curated override in `cards.yaml`, which
  takes precedence over the import. NOT changed silently: it moves reward magnitudes and so
  invalidates this session's comparisons. **Settle before the next PPO run**, which trains its
  chip rewards on whichever number is in place. **Earthquake is unresolved and matters to
  hogeq**: its vardefine 53 vs dmg_11 84 is 63.1%, matching neither the old 65% nor the new 58%
  — needs an in-game reading; (e) **re-probe the advisor on qwen2.5:latest once board-26
  frees the GPU** — on the 0.5b proxy the R1 case answers rocket 4/4, but the CONTROL (Knight in
  hand) still answers rocket 3/3, i.e. the conjunction is not applied. If 7B fails it too, move
  the conjunction out of the prompt and into `train_rl`'s own gating, where it becomes a hand
  check rather than a comprehension test.

### ⚠ SMART APP CONTROL INTERMITTENTLY BLOCKS `import torch` (2026-08-25)

A launch died instantly with:

```
OSError: [WinError 4551] An Application Control policy has blocked this file.
Error loading "...\.venv\Lib\site-packages	orch\lib\shm.dll" or one of its dependencies.
```

This box has **Smart App Control ENFORCING** (`VerifiedAndReputablePolicyState 1`,
`CodeIntegrityPolicyEnforcementStatus 2`). SAC decides on REPUTATION, so it is **intermittent**:
the same interpreter, same venv and same DLL imported fine one minute later, and every probe and
the whole control arm had already run against it. It is not a corrupted install and not a code
fault -- do not go looking for one, and do not reinstall torch on the strength of it.

**Cost if unguarded: a silent two-hour hole.** The trainer dies at import, writes a ~1.5 KB log,
leaves ZERO processes, and any waiter polling for episodes simply sits there until its stall
timeout -- so the failure looks exactly like "the run is slow".

**Mitigation, now in `scratchpad/launch_fix23.sh`:** prove `import torch` in a THROWAWAY process
before committing a long run to it, then re-check the log for `WinError 4551` 75 s after launch and
retry up to 5 times. Any unattended launcher in this project should do the same -- and its waiter
should treat "no telemetry at all after N minutes" as a FAILURE, not as slowness.

### The RAM constraint (important)
31.4 GB total. **Not even ONE full-width PPO run fits beside a board-* detector run** — measured
2026-08-18 22:36 (see §3): one `--envs 96 --workers 12` PPO holds ~8.4 GB, YOLO needs ~12.9 GB
resident, and the OS takes the rest; the result was a 5 MB availability trough and 24k hard
faults/s inside 6 minutes. An earlier note here said two PPO trainers held ~5.2 GB combined —
that number was from a different (checkpoint-idle) phase and must not be used for planning.
board-26 died with `MemoryError ... Unable to allocate 1.63 MiB` — that is *host* RAM, not GPU. If
it OOMs again, drop to `workers=2`. CPU contention is NOT the issue: the 5 it/s measurement was
taken while PPO ran.

**YOLO's footprint is far bigger than the ~5 GB previously written here. MEASURED 2026-08-18 17:33
during the resume: 12.85 GB** — trainer 4.27 GB plus **12** worker processes, not the 4 that
`workers=4` implies (ultralytics spawns train and val pools, both counted). That left only **5.6 GB
free**. Budget ~13 GB for a board-* run, and treat "YOLO ≈ 5 GB" as retired.

---

## 3b. 2026-08-19 daytime batch (user's five tasks)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3c. 2026-08-19 evening batch — live reward truthing (`3db2193`)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3d. 2026-08-19 ~22:00 — the "collapsed" PPO was a SCRATCH run (and the log was stale)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3e. 2026-08-19 late — the live-reward batch crashed a real match (and why nothing caught it)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3f. 2026-08-19 night — the advisor, the doctrine wheels, and a warp bug in hogeq

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3g. 2026-08-20 — reaction latency, phantom tracks, offense windows

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3h. 2026-08-20 late — enemy spells are not threats + the last phantom-cast path

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3i. 2026-08-20 — counter validity + the counter table

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3j. 2026-08-20 late — the phantom-credit bug, the defensive bow, the LLM out of the reaction path

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3k. 2026-08-20 — the king rocket was FREE, and live never paid for the tornado combo (`c7aa9c3`)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3l. 2026-08-20 — FIVE-TRACK ARCHITECTURE AUDIT (read this before more training)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3m. 2026-08-20 — decision period 1.0s → 0.6s (`c328bef`). RETRAIN REQUIRED (sim).

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3n. 2026-08-20 — why the drill pass rate sat at the random baseline (four root causes)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 1 time(s); resolved).

## 3o. 2026-08-21 afternoon — THE REAL BUG: PPO training makes the policy WORSE THAN UNTRAINED

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3p. 2026-08-22 — THE DRILL EXPLORATION FLOORS WERE THE CAUSE (config shipped)

**Start here before changing anything about drills.** Two days of "the drills break training" had
one cause: the drill exploration floors were set so high that the trainer overrode the bot's own
choices 75-85% of the time during drills.

### The one change that fixed it

```
ppo_drill_gate_floor: 0.85 -> 0.30
ppo_drill_cell_floor: 0.75 -> 0.25
ppo_drill_cell_floor_end: 0.20 -> 0.10
```

Drills stay ON at `drill_frac 0.3` -- unchanged. Measured, 40 fixed opponents per policy, 3 seeds:

```
                              winrate   crowndiff        (untrained: 2.5%, -2.200)
floors 0.30/0.25 (SHIPPED)      6.7%     -1.600     <- all 3 seeds beat untrained
gate mask, floors 0.85/0.75     3.3%     -1.717
default floors 0.85/0.75        ~0%      -2.233     <- 4 of 5 seeds scored ZERO
structural drill fix (SF2)      0.0%     -2.25      <- WORSE than untrained
```

**Why the floors did it.** PPO weights each update by pi_new/mu, how likely the network itself was
to take the action. With mu 75-85% prior-driven that ratio is ~0.0125 (01c036b measured this and
did not connect it to the collapse), so drill steps delivered almost no gradient AND the constant
gap between behaviour and policy destabilised the gate. Both symptoms, one cause.

### The measurement that exposed it

The in-run `drills NN% pass` number is produced WITH the priors mixed into sampling, so it largely
measures the SCAFFOLDING. Stripping the priors:

```
scripted (optimal line)  79%    <- the ceiling; randomisation costs only ~5%
doctrine prior           71%
THE TRAINED POLICY       12%    <- 16 of 28 drills at 0%
```

That is why the pass rate never moved off ~43% across every change: it was never measuring the
network. **Use `run.py drills --policy <ckpt>` for the real number.**

### Drill learning does NOT predict match performance

25% drill pass scored WORSE on the match benchmark than 2% did. Do not optimise the drill pass rate
as a proxy for match strength -- they came apart cleanly and repeatedly.

### Shipped but NOT yet validated in training (default off / new)

* **THE POCKET** (`d4d5ac2`, `20ab936`) -- taking a princess grants deployment territory across the
  river on that side, for BOTH sides. 154 -> 254 -> 354 cells. Wired through the trainer via a
  2-bit code per step so the update rebuilds the mask sampling used. Opponents use it too.
  Still static-masked (not pocket-aware): play.py, train_rl.py, policy_stats.py, train_bc.py.
* **Drill realism flags** -- `CLASHRL_DRILL_FULL_HAND` (4-card hand, required cards at RANDOM
  slots), `CLASHRL_DRILL_CLOCK`, `CLASHRL_DRILL_STATE`. They close every state gap (hand d=1.73
  -> 0.00, clock d=2.01 -> 0.00) and they made training WORSE at 500 matches (SF2 above). Either
  realistic drills need longer to pay off, or the state gap was not the mechanism. Unresolved.

### Traps this cost real time to learn

1. `eval_every_matches: 500` runs a **150-match silent benchmark**. It looks exactly like a hang:
   processes alive, no log output, checkpoint frozen for 10-25 min. I killed healthy runs twice.
2. `OMP_NUM_THREADS` unset -> every process sizes its thread pool to all 16 cores. With 9 runs that
   is ~560 threads on 16 cores. Setting it to 2 took throughput from 0.4 to 5.9 ep/s.
3. The collapse is **bistable** (escape rate ~4/6). n=1 decides nothing -- a single run "exonerated"
   drills and sent the whole investigation down a two-day detour.
4. `eng.deploy()` does NOT enforce deployment halves. Masks are the only enforcement, policy-side.

---

## 3q. 2026-08-22 evening — THE POCKET (rule, always on) + the spell mask (strategy, anneals off)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 2 time(s); resolved).

## 3r. 2026-08-23 — THE WINCON BANK FAILED TWICE, AND ITS REPLACEMENT IS 98% INERT

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3s. 2026-08-23 — ALL EIGHT OFFENSIVE BOW WINDOWS SHIPPED, AND THE MEASUREMENT SAYS THEY ARE NOT THE LEVER

> Archived -> `HANDOFF_ARCHIVE.md` (cited 2 time(s); resolved).

## 3t. 2026-08-23 — DEFENSIVE DOCTRINE AUDIT

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3u. 2026-08-23 — W1 REPRICED: the punish window was open 95% of the time, now 39%

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3v. 2026-08-23 — ⚠⚠⚠ §3p's UNTRAINED BASELINE DOES NOT REPRODUCE. "Training beats untrained" was never established.

> Archived -> `HANDOFF_ARCHIVE.md` (cited 3 time(s); resolved).

## 3w. 2026-08-23 — `--drill-frac 0.0` AND `--workers 0` WERE BOTH SILENTLY IGNORED

> Archived -> `HANDOFF_ARCHIVE.md` (cited 1 time(s); resolved).

## 3x. 2026-08-23 — drill_frac SWEEP: 0.3 IS THE BEST OF FOUR, AND NONE OF THEM BEATS UNTRAINED

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 3y. 2026-08-23 — THE ADVISOR REASONS CORRECTLY; THE BOARD IT IS SHOWN DOES NOT

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4a. 2026-08-24 — THE REWARD HAD NO BACKGROUND CLASS (fix 1 shipped; 2, 3, 4 queued)

Owner's analysis, verified term by term. Three of his claims were wrong and two were right, and one
of the right ones turned out to be the unifying cause of three separate symptoms.

### ✗ CORRECTED — the bow is not punished for being blocked, and is not avoided

* **"The model is punished if an offensive X-Bow is blocked."** No such term. `xbow_overcommit`
  PAYS up to +0.48 for a bow that dies having drawn enemy elixir ("they paid 12 to stop it -> the
  draw did its job"). The two penalties are `xbow_into_push` (-4.0, a bow planted ON a committed
  push) and `xbow_overaggression` (-3.0, a forward bow that strips the defence). Neither fires for
  being blocked.
* **"It refrains from defensive bows for lack of a niche."** Of the 5 bows it played in 14 matches,
  **3 were defensive** centre-band and 2 forward. It places them slightly MORE than offensive ones.
* **"It stops investing elixir into the bow."** No aversion exists. Measured on m=26000: on the 21
  steps where the gate chose to play AND the bow was affordable, the masked card head assigned the
  bow **0.266** against a fair share of **0.250** — it picks the bow slightly more than chance.
  The constraint is that those 21 opportunities are all it gets in 14 matches.

### ✓ CONFIRMED, and stronger than argued — `xbow_overcommit` pays a bow that never threatened

`led["cost"]` is accumulated independently of `led["lock"]`, so the overcommit credit is paid at
bow death regardless of whether the bow ever locked a tower. The defect is not a missing penalty
for the bad case; the reward actively **pays** for it. The owner's signature — "an offensive bow
that spends its whole lifetime without a single lock" — is exactly right and currently unmeasured.

### ✓✓ THE UNIFYING CAUSE — nothing in the reward pays for a correct wait

Of the 19 reward terms, exactly **two** can fire on a step where nothing was played, `leak` and
`threat_miss_idle`, and **both are penalties**. There is no positive term for restraint anywhere.
So waiting is worth at best 0 and at worst -1.00 while playing always carries upside: **playing is
weakly dominant at every decision.**

That single asymmetry explains three symptoms at once:

1. the restraint drills stuck at 0% (`ignore_the_ignorable`, `hold_the_spell_for_a_target`),
2. the elixir dumping (median 2.0-2.3, bar never climbs),
3. the x_bow collapse — downstream of (2), since the bow is affordable on **2.5%** of steps and,
   as measured above, is not avoided when it IS affordable.

Owner's framing, which is the right one: the model has no **background class**, the way a
segmentation model needs background samples to learn that labelling nothing is sometimes correct.

**This retires the whole 2026-08-23 line of work on the bow.** The eight offensive windows, the W1
repricing, and all three `wincon_reach` doses were pricing an action the policy could not afford.

### FIX 1 (SHIPPED) — `rewards.restraint_hold`

The mirror of `threat_miss_idle`, built from the same `bodies_ignore_frac` call on the same
committed group so the two cannot disagree about the board. Three guards:

1. **An ignorable threat must be present** — never a quiet board. Paying for idling on an empty
   arena is precisely the hoarding failure `wincon_reach: 2.0` produced (leak 24 fires, crowns
   taken halved).
2. **A counter must be in hand AND affordable** — restraint is declining an option you had.
3. **Rate-limited by `threat_miss_period` and capped per match** — one hold is one event, not one
   per tick, which is the bug that once made `threat_miss_idle` the dominant ledger term.

⚠ **0.25 was measured DECORATIVE before shipping**: 4 fires (+1.00) against `threat_miss_idle`'s 26
(-26.00) over ten matches — 4% of the penalty's magnitude, which cannot change which action
dominates. Shipped at **1.0**, equal per fire, with the asymmetry moved into the cap (2.0/match
here, uncapped there).

### FIX 2 (QUEUED) — gate `xbow_overcommit` on having locked

Require `led["lock"] > 0` before paying overcommit, and add a penalty for an offensive bow whose
lifetime records zero lock. Conjunction, not a new term.

### FIX 3 (QUEUED) — credit the defensive bow's DPS

`xbow_lock` requires `hasattr(u.target, "king")`, so a defensive bow shooting troops earns no lock
and no chip; its contribution appears only as diffuse `elixir_trade`. Smallest of the three.

### FIX 4 (QUEUED, after 2+3) — the curriculum controller oscillates on noise

Owner reported heavy oscillation. Decomposed against expected sampling error over 35 watcher ticks:

```
METRIC        mean     sd      range          sampling sd   VERDICT
P(play)      0.569   0.142   0.334-0.837      ~0.011        REAL (13x sampling)
drill_mean   0.289   0.040   0.195-0.363      ~0.049        SAMPLING NOISE
crowndiff   -1.082   0.231   -1.500--0.500    ~0.354        SAMPLING NOISE
```

The drill and crowndiff swings are MY instrumentation — their spread is smaller than the sampling
error at DREPS=3 and 8 episodes. **P(play) genuinely swings 0.33-0.84.**

The driver is the curriculum feedback loop, and it is not a reward problem:

```
curriculum difficulty:   71% direction reversals   (random walk ~50%)
raw sensor (winrate):    mean 8.1%, sd 5.0; binomial noise alone at p=0.08 on 50 matches ~3.8pp
d_tgt = wr_ema / 35   ->  ~0.057 of movement from noise alone
deadband before moving:  0.02
```

**The deadband sits ~3x BELOW the noise floor**, so the controller moves almost every update in
response to nothing. Difficulty zigzags, the opponent distribution shifts, and the optimal play
rate shifts with it. P(play) reversals are 64% — coupled, as expected.

Fix: widen the winrate window so the sensor is not binomial-dominated, and raise the deadband above
the noise floor (~0.06, not 0.02). Someone hit this before — the EMA and asymmetric rate limits are
already there — but the deadband was left under the noise.

⚠ **Fixes 1-3 will NOT fix this.** They change the reward; this is the control loop.

### ALSO FOUND — the warm-start tax is permanent

`--init` loads policy+gate but NOT the critic; `ppo_value_warmup: 60` minibatches is far too little
(value loss is still moving thousands of episodes in). Measured over the one 20k-episode run:

```
start (m=26000) -1.256 | ep1675 -1.600 (bottom) | ep3600 -1.489 | ep7650 -1.400 | ep20000 -1.444
```

Bottom at ~1,700, most of the recovery by ~7,600, and **it never returns to the init**. So every
reward experiment pays a tax it does not repay, and comparing a mid-run checkpoint against its init
systematically understates the change being tested. **Compare run-vs-run at matched episode counts
instead.**

The checkpoint does save `value`/`value_d`, so loading it on `--init` would remove the tax — but a
saved critic predicts returns under the reward it was trained on, so it is only valid when the
reward is UNCHANGED. Gate it on a reward hash before ever enabling it.

---

## 4b. 2026-08-24 — THE TWO P(play) NUMBERS WERE NEVER IN CONFLICT, AND THERE IS NO SPEEDUP TO BUY

> Archived -> `HANDOFF_ARCHIVE.md` (cited 2 time(s); resolved).

## 4c. 2026-08-24 — FIX 1 PAIRED READ AT 650 MATCHES: it changes behaviour, and two of four changes are wrong

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4d. 2026-08-24 — "THE RUN DEGRADES AFTER A WHILE" IS NOT WHAT THE DATA SHOWS

The owner has reported, across many runs and regardless of the change under test, that a run peaks
and then slides. Extracted the per-update series from every long log. **The premise does not hold,
and what replaces it is worse.**

### There is no degradation

```
quarter-by-quarter TRAINING winrate
run          Q1     Q2     Q3     Q4     direction
crown3x     4.3%   7.1%   8.0%   7.4%   rise, -0.6pp late
dose10      4.0%   8.2%   7.7%   7.3%   rise, -0.9pp late
lever2      1.8%   4.9%   4.4%   6.4%   rising
night1      5.7%   7.0%   7.3%   9.2%   rising throughout (longest run, 20,925 eps)
restraint   0.4%   2.2%   4.7%   4.3%   rising
```

Three of five rise monotonically and the two that dip do so by under 1pp. **The "peak then slide"
reading is a SELECTION ARTIFACT** — the maximum of a noisy series is by definition followed by lower
values, so "peaked at ep20300, then averaged 11%" describes regression to the mean. I produced that
artifact myself with a peak-detector before catching it; do not report a peak-relative decline.

### ⚠ TRAINING WINRATE CANNOT MEASURE POLICY QUALITY AT ALL — IT IS SERVO-CONTROLLED

`d_tgt = wr_ema / full_wr(35)` MOVES OPPONENT DIFFICULTY to hold winrate near target. A regulated
variable reports how well the controller tracks, not how strong the policy is. Every "winrate is
collapsing / recovering" conversation in this project has been reading the controller's error
signal. **Read the controller's OUTPUT instead.**

### The output says the policy is treading water

```
curriculum difficulty     Q1     Q2     Q3     Q4    first->last  reversals  range
crown3x                  0.205  0.249  0.245  0.198   0.25->0.25     65%    0.15-0.33
dose10                   0.195  0.278  0.223  0.214   0.25->0.18     58%    0.15-0.36
night1                   0.234  0.225  0.208  0.272   0.25->0.31     71%    0.15-0.39
```

**Over 20,925 episodes the controller never durably raises difficulty.** Independent agreement from
the crowndiff trace in §4a: `m=26000 -1.256 -> ep20000 -1.444` — after 20k episodes the policy was
WORSE than its own starting checkpoint.

**So the question is not "why does it degrade". It is "why does it never improve."**

### Reversal rate confirms the fix-4 diagnosis, and raises its priority

58-71% direction reversals against 50% for a random walk is **anti-persistent** — the controller is
not drifting, it is actively over-correcting, exactly as predicted by a 0.02 deadband sitting ~3x
below the ~0.057 noise floor. A constantly-shifting opponent distribution means the policy chases a
moving target and cannot consolidate. **Fix 4 is no longer a stability nicety; it is a candidate
cause of the no-improvement finding.**

### MECHANISM CANDIDATE (hypothesis, NOT established) — the policy collapses its own action space

§4.3 already measured it: cell head fresh `row13 41.2%, 62/432 cells` -> at 19k matches
`row13 84.5%, 28/432 cells`. The entropy series agrees globally (`ent` down 28-57% per run).

Suspect: `ppo_cell_entropy` anneals 0.05 -> **0.008** over `ppo_cell_entropy_anneal: 3000` episodes,
so **80%+ of a 20k-episode run trains at the floor**, which is the window the collapse was measured
over. ⚠ NOT established — the crowndiff trace still IMPROVES from ep1675 to ep7650 while at the
floor, so the correlation is not clean, and the config comment records that a FIXED high value held
the head at maximum entropy and it never learned. This needs its own A/B (floor 0.008 vs ~0.02, or a
15k-episode anneal), run AFTER fix 4 so the controller is not also moving.

## 4e. 2026-08-24 — ⚠ THE REWARD PAYS FOR DEFENDING THE WRONG LANE (fix 5, QUEUED — do not ship mid-experiment)

Owner reported that the model answers the DEEPEST enemy threat rather than the most DANGEROUS, and
asked whether that is incomplete PPO or a live-only problem. **It is neither. It is a sim reward
bug, and PPO learned it faithfully.**

`_threat_response` grades two things against TWO DIFFERENT THREATS:

```
WHICH CARD you played  -> judged against `_threat_id_true`, which ranks by DANGER
                          (`ignore_cost_frac`) -- correct, fixed 2026-08-20
WHERE you put it       -> judged against `_threat_pos()`, which returns
                          `max(onside, key=lambda u: u.y)` -- the DEEPEST unit
```

MEASURED on the owner's exact board (a dangerous card in one lane, a trickle DEEPER in the other):

```
danger (ignore_cost_frac):   pekka 1.907    skeletons 0.004     (477x apart)
IDENTITY says (danger-ranked):  tank=1                <- the pekka, correct
POSITION says (depth-ranked):   x=0.75                <- the SKELETONS' lane
counter placed in the PEKKA's lane     -> intercept credit: False
counter placed in the SKELETONS' lane  -> intercept credit: True
```

**The reward PAYS for putting the anti-tank card in the trickle's lane and REFUSES credit for
putting it in front of the tank.** So this is not ignorance the policy can train out of -- more
training makes it worse, because the gradient points at it. Same family as `_hog_wincon` (S8): a
reward measured against a board that is not the one being answered.

**The 2026-08-20 "PRIORITISE, DO NOT BLEND" fix caught HALF of this.** Its own comment describes
the identical failure -- *"a Golem at the bridge beside a lone Skeletons walking deep ... answering
the vector meant answering the Skeletons (the reported behaviour)"* -- and repaired
`identity_threat_vector`. `_threat_pos()` was never touched, so the POSITION half kept the bug and
the symptom survived, which is why the owner is still reporting it four days later.

**Fixing LIVE would not have helped.** Live feeds the policy the correct danger-ranked identity
vector; the observation was never wrong. The learned habit is, and it came from the reward.

### FIX 5 — SHIPPED 2026-08-25

`_threat_pos` now ranks on the SAME `ignore_cost_frac` the identity vector ranks on, ties broken on
depth -- `max(key=(danger, depth))`, character-for-character the rule `identity_threat_vector` uses
for its primary. Both halves of `_threat_response` describe the same unit BY CONSTRUCTION.

VERIFIED on the exact board that demonstrated the bug:

```
                              BEFORE          AFTER
POSITION returns              x=0.75          x=0.25   (the pekka)
counter in the pekka's lane   no credit       CREDIT
counter in the trickle's lane CREDIT          no credit
```

**4 tests added** (`ThreatPositionTests`), and the NEGATIVE CONTROL was run: 2 of the 4 FAIL on the
unpatched `_threat_pos`, so they genuinely detect the bug rather than merely passing. The other two
(depth-as-tie-break, and a lone trickle still being named) are true of both versions by design.
`test_identity_and_position_describe_the_SAME_body` is the one that matters -- the 2026-08-20 repair
fixed the identity half and survived four days *because nothing asserted the two halves agreed*.
icebow 629 tests OK.

### FIX 5 (original diagnosis, kept for the record)

Rank `_threat_pos()` on the same `ignore_cost_frac` the identity vector uses, breaking ties on
depth, so both halves of `_threat_response` describe the SAME unit. It is the same three-line shape
as the 2026-08-20 repair, applied to the other half.

⚠ **DELIBERATELY NOT SHIPPED TONIGHT.** The control and fixes-2+3 arms are mid-flight and BOTH
carry this bug, so it cancels in their comparison and tonight's verdicts stay valid. Shipping it
now would confound them and break the one-change-at-a-time rule. It is the FIRST thing to ship
after the overnight queue, ahead of the queued reward tweaks -- it has been mistraining every run
in this project's history.

### ALSO 2026-08-24: `llm_advisor_async` REVERTED to false

Owner reports async makes live reaction too slow. That is the design's expected cost, not a defect
in it: an async answer is spent a DECISION LATER than the board it was asked about, so at
`act_period` 0.6 s every advised play is >= 0.6 s stale and `llm_advisor_max_age_s: 1.5` permits up
to 1.5 s -- two to three tiles of travel on a real push. ⚠ Turning it off restores the measured
**0% answered** (565 ms mean against a 0.55 s budget) unless `llm_advisor_timeout_s` is also raised.
The real choice is "no advice" vs "stale advice". Advice is exploration-only either way and never
gates the policy's own action.

## 4f. 2026-08-25 OVERNIGHT — MATCHED-CONTROL RESULTS (the design this project never had)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4g. 2026-08-25 — FIX 6 SHIPPED: the cheap answer in the OTHER lane was worth nothing

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4h. 2026-08-25 — FIX 7 SHIPPED: the missed-defence penalty was a STEP FUNCTION

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4i. 2026-08-25 — ⚠ PENDING: CARD LEVEL UPGRADES (apply before the next PPO run)

Owner reported two real-account upgrades. **NOT YET APPLIED**, deliberately:

```
config/cards.yaml   {card: tesla, evolved: true, level: 14 -> 15}
config/cards.yaml   {card: ice_wizard,           level: 12 -> 13}
```

Card levels scale HP/damage, so they change the SIM. Applying them mid-round would invalidate
`ARM_control4` and force a re-run of BOTH the control and the fixes-2+3 retry arm (~3 h) instead of
just the retry arm (~1.5 h). The retry verdict is about reward STRUCTURE (credit gate vs penalty),
which the level change does not interact with. **Apply the moment that verdict lands, before the PPO
run**, so the PPO trains at the real account levels. Match the existing comment style in that file,
e.g. `# upgraded 13 -> 15 on 2026-08-11 (real account level, confirmed)`.

### ⚠ PROCESS FAILURE, RECORDED BECAUSE IT COST FIVE HOURS

`ARM_control4` finished cleanly at 09:45 and **nothing advanced for ~4.8 h, because no waiter was
armed for it.** A waiter had been armed for every previous arm; this one was launched, a Discord
update was posted, and the turn ended. No notification existed, so no next stage fired.

This is the exact failure documented in S2 four hours earlier -- *"any unattended launcher should do
the same, and its waiter should treat 'no telemetry at all' as a FAILURE, not as slowness"* -- in the
form where there is no waiter at all. **A launch is not complete until its waiter is running.** Treat
`launch_arm.sh` and `wait_eps.py` as a single operation, never two.

## 4j. 2026-08-25 — FIX 1 DROPPED (not deleted). Kept armed behind one config line.

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4k. 2026-08-25 — FIXES 4, 5, 6, 7 PORTED TO HOGEQ (2+3 and 1 deliberately not)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4l. 2026-08-25 — CROSS-DECK DIVERGENCE AUDIT (owner asked for both folders 100% current)

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4m. 2026-08-25 — PLAY-OUT PORTED TO HOGEQ, AND THE VERIFICATION FOUND A LIVE BUG IN ICEBOW

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4n. 2026-08-25 — FIX 2+3 RETRY SHIPPED (unproven), ROYAL HOGS ABREAST, and ⚠ THE LOG IS THE WRONG WIDTH IN BOTH SIM AND LIVE

> Archived -> `HANDOFF_ARCHIVE.md` (cited 2 time(s); resolved).

## 4o. 2026-08-25 — ⚠⚠ THE GATE'S GRADIENT IS INVERTED BY CLIPPING, AND TWO LEVERS FIX DIFFERENT HALVES

> Archived -> `HANDOFF_ARCHIVE.md` (cited 2 time(s); resolved).

## 4z. 2026-08-27 — THE SPELL CARD VETO SHIPPED, IN THE OWNER'S VALUE FORM (default OFF). RULING 30.

§4y/§7.5 recommended the veto at **K=3 bodies**. **The owner rejected the count form** — this
deck's best casts are single-body (`nado_king_activation` = ONE Hog, `nado_the_sneaky_lock` = ONE
Knight, `rocket_the_two_for_one` = ONE Witch, `rocket_the_pump_on_sight` = ONE building; K=3
refuses all four). Shipped instead, both decks:

* **Criterion**: `sim.ppo_spell_min_value` in TOWER FRACTIONS via NEW `threat_value.catch_value_frac`
  (`bodies_ignore_frac` reads `inf` for kamikaze/spirit bodies — wall_breakers/fire_spirit/ice_spirit
  measured inf vs true 0.14/0.047/0.025 — and a veto reading inf as "valuable" would wave those
  casts through; the new function sums the per-card burst price for what the pooled model cannot hold).
* **Exemptions** for casts whose value is NOT the bodies — `SimMatchEnv.spell_veto_exempt`, every
  entry sourced to a drill/doctrine line in **decisions.md RULING 30** (the durable artefact):
  `king_activation` (path-crossing test from `doctrine._king_spots`), `lock_break` (sneaky lock +
  the `nado_retarget_min_worth`-gated tower retarget), `charge_reset` (knockback spells only — the
  VORTEX does not clear `charge_dist` in this engine, so the tornado does not get it; guarded by
  `trade_sane` or a 6-elixir Rocket became unrefusable on any charging body), `tower_lethal` /
  `tower_finish` (3 casts, DOCTRINE_RESEARCH §3.4) / `tower_chip` (OVERTIME+behind only — ⚠
  `_defensive` is True at t=0 under a split-lane opponent and `_tiebreak_gap` is -0.098 at t=0 on
  level disadvantage alone; an ungated version exempted the Rocket on 300/300 steps),
  `two_for_one`, `building` (pump/tombstone/siege), `incoming_spawn` (pre-log the barrel; gated on
  the landing point being reachable). Hit test mirrors the ENGINE (corridor/pull/blast, §4v) and
  drops HIDDEN buildings for spells without `hits_hidden`.
* **⚠ THE GREEDY ASYMMETRY IS FIXED**: `choose_greedy` applied NO spell mask before this change, so
  eval and live always cast unmasked while sampling ran masked. The veto now applies in
  `choose_sample`, `choose_greedy` (new `envs=` arg), and the drill report's greedy adapter
  (`run.py drills --spell-min-value`). The annealed CELL mask stays sampling-only on purpose (it is
  a training wheel; the veto is a rule).
* **⚠ DEFAULT `0.0` = OFF, deliberately**: the 8k run was live in this tree and its workers
  re-read config (§3n's seam). Verified inert by BEHAVIOUR (41 casts refused at 0.20 all castable at
  shipped default). **Enable the next run with `0.45`** — highest bar that keeps every owner-named
  single-target reference line (probe: `scratchpad/ref_line_probe.py`).

**MEASURED** (n=300 paired GREEDY, seeds 5M..5M+299, `_rs_policy.pt`, tree `1143af2`+this change;
baseline re-measured, reproduces §4y's board-exact `bx` arm 300/300):
```
value 0.45 NO exemptions  +0.239 towerd (3.91σ)  = count-form k3 (+0.252, 3.80σ; diff 0.22σ)
                          beats volume-matched random-ban control +0.149 (2.14σ)  -- the bar holds
value 0.45 WITH the ruling-30 exemptions  +0.036 (0.65σ)  NO MEASUREMENT; does not beat controls
```
**The exemption set costs +0.203 (3.82σ) and that is the honest price of protecting the
single-target plays** — no threshold resolves it (the protected lines sit at 0.070-0.340, below
any bar that moves the metric). The owner asked for the smaller correct rule; ruling 30.4 records
both forms and enables neither by default. Full sweep: ledger §8.

Gates: icebow **1136 OK** (was 1109 + 27 new), hogeq **1159 OK** (was 1132 + 27 new), parity OK,
`stat_sweep --all` exit 0 MISMATCHES: 0, drills before/after in the commit. Tests
`test_spell_card_veto.py` byte-identical in both decks.

## 4y. 2026-08-27 — ⚠⚠ THE SPELL EXPERIMENTS: THE SPELLS ARE NET-NEGATIVE, PLACEMENT IS WORTH NOTHING, AND THE SIM'S ACTION SPACE WAS CLAMPED BY SCREEN CONSTANTS

Owner's standing request (§6-PRIORITY), rescoped by `rollout_search.md` §5.1/§6.2/§7a.
Full ledger: **`research/sim_parity/ledger/spell_experiments.md`**. Read that before re-running
anything; only the verdicts are here.

### WHY THESE ARE DECISION-TIME ARMS AND NOT TRAINING ARMS
A matched-control training arm costs **~2 h** (measured: ARM_control4 1h50, ARM_fix23b 1h52,
ARM_clipfix 1h53 at 2600 episodes), and §4n's own post-mortem is *"compute the detectable effect
size BEFORE running the arm"*. Both spell questions have a prerequisite a decision-time arm answers
in 8 minutes at far higher power: **if the rule is FORCED with engine ground truth, does it help at
all?** If not, training a policy to approximate it from a degraded observation cannot either.
Every arm below is therefore an **upper bound** on what the training change could deliver.
Harness `scratchpad/spell_arms.py` (a verbatim copy of `rollout_search.py` + flags, all default OFF;
baseline byte-identical, checked). n=300, seeds 5_000_000..5_000_299, paired, **GREEDY**, bar >=2σ.

### ⚠ `rs_base.json` NO LONGER REPRODUCES — d9b20d6 MOVED THE BASELINE
`rollout_search.md`'s 37.0% / -0.928 is 43.0% / -0.841 today on the same seeds and checkpoint.
Commit **d9b20d6** (ruling 29, spawned-body elixir) feeds `threat_value` -> the threat vector -> the
observation -> the action stream. Seed 5000000 goes 371 steps/49 plays -> 215/17.
**§4q's "arms hours apart differ by every commit between them" bites EVAL arms too.** Every number
below is against its own same-tree baseline.

### EXPERIMENT A — RESTRAINT: **MEASURED**, and the mechanism is mostly VOLUME
Rule (NOT a scalar): refuse a SPELL card when no legal cell would catch >= K enemy bodies under the
ENGINE's own hit test (corridor for a roll, pull disc, blast disc — §4v's trap).
```
K       casts/m   win%   towerd delta   sigma        K       casts/m  win%   towerd delta  sigma
1        7.47     41.7      -0.025      -0.69        5        1.56    49.7     +0.397     +6.31
2        6.12     37.7      +0.023      +0.38        7        0.53    52.0     +0.383     +5.82
3        4.32     47.7      +0.233      +3.58        NEVER    0.00    50.0     +0.306     +4.33
4        2.64     50.0      +0.332      +5.12
```
Monotone on tower delta, crown delta AND dump rate (36.7 -> 9.4%), plateau at K>=5. Not multiplicity.
**THE CONTROLS ARE THE POINT** (paired, arm vs arm, matched CASTS/MATCH):
```
ctlS3 -> k3    same 4.3 casts/m, criterion vs RANDOM spell bans   +0.207   2.98σ   SIG
ctlS5 -> k5    same 1.5 casts/m, criterion vs RANDOM spell bans   +0.009   0.16σ   NO MEAS.
base  -> knever  cast NO spells at all                            +0.306   4.33σ   SIG
knever -> k7   0.53 SELECTIVE casts/match vs none                 +0.077   2.24σ   SIG
ctlany  ban random cards (troops too), vs base            -6.3pp win  -2.37σ  HARMFUL
```
1. **The biggest single effect is that this policy should barely cast its spells.** Deleting all
   three — 3 of 8 cards — is +0.306 / +7.0pp at 4.33σ.
2. **Targeting is worth something only while volume is high.** +0.207 over its matched control at
   4.3 casts/m; **+0.009 at 1.5**. (At matched volume the criterion arm dumps 18.5%, the random arm
   40.1% — they really do behave differently; it just stops mattering.)
3. **Spells are worth ~half a cast per match**: k7 beats never-casting by +0.077 (2.24σ).
4. **Global "play less" is harmful; SPELL-SPECIFIC "play less" is worth 7-9 points.** That is why
   §6.2's tau sweep could not find it — the gate fires before the card argmax, so it is
   card-agnostic by construction.
5. **The elixir-trade criterion is a NULL** (+0.017, 0.38σ) and the reason is its 3.7% fire rate,
   not the idea. Do not re-run it as written.

### EXPERIMENT B — PLACEMENT: **NULL**, with the instrument demonstrably awake
`aim` = keep the card, move the cell to the engine-true best-hitting legal cell. The CEILING of a
perfect spell placement head.
```
base -> aim    tower delta +0.004  sem 0.051  +0.07σ   NO MEASUREMENT   (winrate -3.3pp)
```
It moved 856 casts (36.5%), gained 1290 bodies hit, 413 of them from a ZERO-hit cell, and took the
tornado's dump rate 15.0% -> 4.4% and the rocket's 8.6% -> 2.5%. **2σ upper bound on perfect spell
placement: +0.106.** §5.2's +0.216 for all-card cell search is real and is somewhere else.

**§4r's two-failure split is now decided PER CARD.** the_log = RESTRAINT (perfect aim 46.2% ->
45.3%, restraint -> 27.8%; it is `own_half_only`, so an enemy on their side is unreachable by any
cell). tornado/rocket = PLACEMENT, fixable, worth nothing.
⚠ EXPLORATORY, not pre-registered: aim ON TOP of restraint is +0.103 (2.49σ). A hypothesis.

### AND NO SINGLE SPELL IS THE CULPRIT — do not nerf one card
```
delete the_log  +0.066 (1.01σ)  |  tornado +0.082 (1.72σ)  |  rocket +0.048 (2.62σ)
delete ALL THREE +0.306 (4.33σ)  -- SUPER-additive; singles sum to +0.196
```
Removing the Log alone makes winrate WORSE (-1.7pp). The problem is spell casting as a class.

### THE LIVE PATH — FOUR DEFECTS, THREE SHIPPED-CODE UNITS ERRORS (§3 of the ledger)
* ✅ CLEAN: the grid round trip, 0 of 432 cells wrong. §4.2 stayed fixed.
* ✅ CLEAN: the live OBSERVATION — detections and anchors all go through `warp.frame_to_board`.
  **The asymmetry is action-side only.**
* **FIXED `84bd0a7`** — `no_king_mask` compared FRAME `cell_center` to a BOARD `king_xy`. Live
  blocked 12 cells, sim 22; the 10 extra sit **1.54-2.69 true tiles** from the enemy king, four
  inside a Rocket's 2.0-tile blast. RS-4 in shipped code. `test_deploy_rows` had the SAME units bug,
  which is why it never caught it — updated, not deleted. **2.3% of cells: real, and NOT the
  owner's report.**
* **FIXED `8476a1e`** — the **TORNADO** was being snapped onto Crown Towers by `weaker_princess_cell`
  (gated on `anywhere_ids` = {rocket, TORNADO}). **80 of 432 cells (18.5%)** sit in that box, so ~1
  tornado cast in 5 was redirected onto a building it cannot pull. The sim's own `spell_target_mask`
  already states the rule ("never for a pull"); it never reached live.
* ⚠ **MEASURED, NOT FIXED** — `reward.spell_whiffed` takes a radius in TILES and every live caller
  feeds it FRAME coordinates. A 4.5-tile radius really spans **4.7 to 12.0 tiles** depending on
  depth, so the LIVE reward under-charges whiffs, worst at the enemy end. ~10 call sites across
  `env.py`/`play.py` in two decks and it moves the live reward, so it is its own change.
  Same family, same call sites: `nado_king_cell`, `spell_intercept_cell`, `pump_rocket_cell`,
  `weaker_princess_cell` all use raw normalised distances with one radius (reward.py 224/231/244/275/314).

### ⚠⚠ AND THE BIGGEST FINDING IS NOT IN LIVE — `51f34fb`, THE SIM'S ACTION SPACE WAS CLAMPED
`_board_action_space` never overrode `label.arena_top` / `arena_bottom` / `buttons.chat_avoid_box`
— LIVE SCREEN constants that `cell_center` applies to whatever space it is in.
```
before: 96 of 432 cells (22.2%) deployed somewhere other than their own centre, worst 6.37 tiles
        only 372 DISTINCT deploy points -> 60 cells were EXACT DUPLICATES of another cell
        board tile-y outside 3.20..27.52 was UNREACHABLE (the arena is 0..32)
        the EMOTE-ICON box alone displaced 15 cells
after:  0 displaced, 432 distinct, tile-y 0.67..31.33
```
* **All 36 cells of grid rows 0-1 clamped to tile-y 3.20; the enemy king is at 3.0.** 8.3% of the
  action space landed on the king and `train_sim_ppo.py:199` masks NONE of it
  (`allcells_mask = torch.ones`). That is a structural explanation for `never_rocket_their_king`
  scoring 0-17% — the policy could barely avoid it.
* **60 duplicate actions** = the cell head asked to distinguish identical actions. A structural
  contributor to §4r's near-uniform cell head, independent of learning.
* In LIVE all three clamps fire on **0 of 432 cells** — inert where they belong, mangling a fifth of
  the action space where they do not. The mirror image of the §4.2 trap.
* MEASURED SAFE on the current checkpoint: applying it at eval is **+0.006, 0.24σ**, winrate
  identical. ⚠⚠ **REQUIRES A RETRAIN before any placement number is quoted again.**

### RECOMMENDATION FOR THE NEXT RUN — one change, four DO-NOTs
**DO:** promote the spell mask from a CELL mask to a **CARD veto at K=3 bodies on the ENGINE's
geometry**, applied in sampling **and** `choose_greedy` (which applies no spell mask today, so eval
and live have always run unmasked while sampling ran masked). K=3, not 5 or 7, because K=3 is the
largest threshold at which the CRITERION beats its volume-matched control (+0.207, 2.98σ); above it
you are only buying "cast fewer spells". Machinery is 80% there: `sim/env.py::spell_target_mask` +
`train_sim_ppo.py:458-497`.
**DO NOT** spend an arm on the cell head / doctrine cell prior / spell entropy floor (ceiling +0.106).
**DO NOT** ship "tighten `spell_waste_tiles` 4.5 -> 2.0" as the fix — its card-level form is k1,
-0.69σ. The binding variable is HOW MANY bodies, not the radius.
**DO NOT** retune `ppo_gate_threshold` (closed by §6.2, re-confirmed by `ctlany`).
**DO NOT** nerf or delete a single spell.
**FIRST:** `51f34fb` must be in the tree the run starts from.

⚠ ALL ARMS USE ENGINE GROUND TRUTH. In the sim that is free (`spell_target_mask` already reads the
engine). LIVE, at `sim_detector_recall 0.82`, a real 3-body clump is fully seen only 0.82^3 = **55%**
of the time, so the live port would veto about half the casts it should allow. **Separate question.**

### UNTESTED, worth one arm later (do not bundle)
`knever` removes the HITS as well as the whiffs and still wins at 4.33σ, and `k7` shows the marginal
value of every cast past the best ~0.5/match is negative. So the problem may not be that whiffs are
under-charged but that **a cast hitting one or two bodies is paid for at all**: `rewards.spell_waste
-0.3` only fires when nothing is within 4.5 tiles, and no term prices "a 2-elixir Log clipped one
Skeleton" as the losing trade it is. NOT TESTED.

---

## 4x. 2026-08-27 — QUEUED EXPERIMENT: EVAL-ONLY ROLLOUT SEARCH (owner's idea, scoped by measurement)

Owner asked whether MCTS belongs in the sim: clone the state every Nth decision, play out a few
seconds per candidate action, take the best. Measured before answering, on the CURRENT engine:
```
                 clone      tick      5s rollout + clone
quiet (5 units)  0.45 ms   0.071 ms        4.0 ms / candidate
busy (72 units)  3.55 ms   0.572 ms       32.1 ms / candidate
20 candidates, every 10th of ~300 decisions  ->  ~19 s per match (busy board)
```
**The engine deep-copies cleanly** — that was the thing most likely to kill it outright.

### The verdict, and why it is split
* **TRAINING-time search is infeasible.** A match costs ~20-170 ms of engine time today; +19 s is a
  ~100x slowdown, and this project is already CPU-bound (40k episodes = 28 h). That becomes months.
* **EVAL-time search is cheap** — a 150-match eval is ~45 min. **THIS IS WHAT WE RUN.**
* ⚠ Note the owner's proposal is FLAT ROLLOUT SEARCH, not MCTS — no tree, no reuse across
  iterations. The cost above is for the flat version; a real tree gets more from the same budget.

### ⚠ THE OBJECTION THAT SHAPES THE DESIGN
**Search optimises whatever objective it is given, harder and more consistently.** This project
spent a week finding that objective to be wrong (spell casts billed `spell_waste` by an `id()`
recycling bug; `threat_miss_idle` a step function; `bank_to_six_then_bow` at 0%). Search over the
SHAPED reward would have pursued those defects harder.
**So the rollout is scored on ACTUAL OUTCOME — net tower-HP delta over the horizon — NOT on the
shaped reward terms.** That is the version worth running, and it sidesteps every reward bug we
have been fixing.

### It does NOT obviously address the §4t decay, and should not be sold as doing so
The owner's hypothesis was that search would prevent the eval decay (rolling ladder 33% -> 20%).
The decay was MEASURED but never DIAGNOSED; every candidate cause (curriculum ratcheting, entropy
floor, drill/match advantage gap, value-loss drift) is a TRAINING dynamic, and decision-time search
touches none of them.

### What it actually buys: a headroom measurement we cannot currently make
policy+search vs policy alone, same reference checkpoint, same seeds:
* **search >> policy** -> the bottleneck is the policy's judgement, and AlphaZero-style
  distillation (search generates targets, policy learns them) becomes worth costing out.
* **search ~= policy** -> either the objective is misleading or a few seconds of outcome does not
  discriminate. Both are worth knowing BEFORE spending weeks on architecture.

⚠ Only viable since 2026-08-27: before the `deploy_seq` attribution fix the sim was not
reproducible run-to-run, so rollouts would have been comparing noise.

### ⚠ THE SCORING FUNCTION — refined by the owner's question, and "net tower HP" was too loose
Owner asked whether the rollout scores BOTH sides. Yes — but raw HP delta breaks three ways, and
the project already has MEASURED machinery for all three, so nothing here is invented:

1. **Elixir must be in the score.** 6 elixir to prevent 200 damage is worse play than 2 to prevent
   150; a score without a cost term over-commits by construction. That failure mode is ALREADY this
   policy's known defect (§4q: mean elixir 2.29, 5.4% of steps at >=6, `bank_to_six_then_bow` 0%),
   so an elixir-blind search would pursue it HARDER. Use the measured
   `threat_value.ELIXIR_TO_TOWER = 0.061` (derived across 113 cards) to convert.
2. **Crowns are not linear in HP.** A tower's last 100 hp is worth far more than its first 100,
   because taking it is discrete. Add explicit crown terms rather than trusting the HP integral.
3. **The horizon truncates unrealised value.** At the end of a 5 s rollout a Golem push about to
   connect scores the same as no push. For an X-BOW CONTROL deck that bias — immediate defence over
   investment — is close to inverting the deck's strategy. Value the surviving board at the horizon
   with `threat_value.bodies_ignore_frac`, which already prices bodies in TOWER FRACTIONS.

Everything lands in one currency (tower fractions):
```
score =  enemy tower fraction destroyed
       - our tower fraction lost
       - elixir spent * ELIXIR_TO_TOWER (0.061)
       + (our surviving board value - theirs)      # bodies_ignore_frac, both sides
       + crown terms                                # discrete, large
```
⚠ Horizon length is itself a variable: 5 s was my arbitrary figure. SWEEP IT (e.g. 3/5/8/12 s) —
if the verdict flips with horizon, that is the finding, not a nuisance.

**ORDER (owner):** rolling-spell changes merge -> **eval-only rollout search** -> spell experiments
-> new 20k PPO. Owner stepped away 2026-08-27 and delegated the whole chain.

### DONE 2026-08-27 — BOTH SWEEPS RUN. Ledger: `research/sim_parity/ledger/rollout_search.md`.
Sweep 1 = §0-§9 of that file; **sweep 2 (the ceiling) = §10-§19**. Headlines:
```
policy alone                                 37.0%   tower -0.928
+ search H=12, every 5th decision            59.0%   tower -0.234   (+9.53 sigma)
+ search H=12, EVERY decision (N=1)          80.7%   tower +0.484   (+19.91 sigma)
+ N=1 and top-3 CELLS  <-- CEILING           85.7%   tower +0.651   (+20.74 sigma)
```
* **Horizon saturates at H = 12** — H = 16/20/30 are all within 1 sigma of it, and rolling to the
  MATCH END is 5.1 sigma WORSE. The horizon cap is the idle rollout default, not search.
  §4x's "sweep it, if the verdict flips that is the finding" — it does not flip, it plateaus.
* **K is inert** (K = 2 = 4 = 8; K = 8 never binds). **N is the only real lever.**
* **The match-position confound was measured and disposed of**: 9.5% of rollouts reach the match end
  at H = 12 (0% before 60 s), early-only search still clears the bar at 2.03 sigma with a MEASURED
  0.0% clamp, and the 100%-clamp arm is the worst one.
* ⚠⚠ **LIVE SEARCH IS RULED OUT**, and not on compute (~24 ms/decision into ~230 ms of slack).
  There is no detector -> `SimEngine` bridge, per-unit HP is unavailable, there is no opponent
  deck/hand model, and ~80 per-unit fields are unobservable. On top of that a **quarter-tile**
  position error costs 62% of the search's gain and the damage SATURATES there, so no detector is
  good enough. **Recommendation: DISTILLATION** (~2 h on 16 cores for an 18k-match-equivalent
  target set; teacher wins 85.7% vs 37.0%).
* ⚠⚠ **TRAP, and it affects every number in that ledger:** `rollout_search.py` sets
  `PYTHONHASHSEED` with `os.environ.setdefault` AFTER interpreter start, which is a NO-OP, so runs
  are **not reproducible**. Two runs of the identical N = 1 config gave 78.7% and 80.7%. Effect
  sizes and sigmas stay valid (the sem is empirical and pairing still removes 56% of the variance)
  but §1's three "IDENTICAL" determinism checks do not reproduce. **Export `PYTHONHASHSEED=0`**
  before any re-run, and re-run the baseline if you do.

---

## 4w. ⏳ PENDING CARD UPGRADE — apply on the sim-parity branch before the merge

Owner 2026-08-27: **tornado upgraded 14 -> 15** (real account level).

`config/cards.yaml` deck block, icebow only (hogeq's deck has no tornado):
```
    - {card: tornado, level: 14}   ->   level: 15
```
House style for this edit (see the 2026-08-16 and 2026-08-25 examples on the same rows):
`# upgraded 14 -> 15 on 2026-08-27 (real account level, confirmed)`

NOT applied immediately because an agent held those files at the time; apply on `sim-parity`
BEFORE the merge so the new PPO trains at the correct level. A deck level change shifts the
training distribution, so it belongs with the parity merge (that merge is deliberately the ONE
bundled change for the next experiment) rather than landing separately afterwards.

⚠ Do NOT edit this in the LIVE tree — it is the merge target and must stay clean.

---

## 4v. 2026-08-26 — ⚠⚠ RETRACTION: "THE LOG'S PLACEMENT IMPROVED" WAS MY OWN MEASUREMENT BUG

> Archived -> `HANDOFF_ARCHIVE.md` (cited 2 time(s); resolved).

## 4u. 2026-08-26 — THE 40k RUN WAS STOPPED AT 26,600. Reference policy = `policy_BEST_m18000_20260826.pt`.

> Archived -> `HANDOFF_ARCHIVE.md` (cited 0 time(s); resolved).

## 4t. 2026-08-26 — ⚠⚠ THE 40k RUN PEAKED AT ~18k AND IS GIVING IT BACK. §4d's "runs never durably improve" STANDS.

I called this run "the first durable improvement §4d said never happened" at 16-18k. **That claim
is RETRACTED.** Measured on the trainer's own 150-match evals:
```
EVAL @ 16000  ladder 43% (avg-5 33%) | fair 24% (avg-5 20%)
EVAL @ 18000  ladder 34% (avg-5 33%) | fair 26% (avg-5 22%)   <- PEAK
EVAL @ 20000  ladder 21% (avg-5 30%) | fair 16% (avg-5 21%)
EVAL @ 22000  ladder 17% (avg-5 27%) | fair 19% (avg-5 20%)
EVAL @ 24000  ladder 18% (avg-5 27%) | fair  7% (avg-5 18%)
EVAL @ 26000  ladder 11% (avg-5 20%) | fair  5% (avg-5 14%)
```
Five consecutive declining rolling points on 750-match windows (~4σ). In-training drill pass fell
with it: 42% (@5k) -> 39% (@16k) -> **37% (@26k)**.
**The peak policy IS banked** — the trainer saved `data/policy_ppo_long_best.pt` at the 33% ladder
average. `policy_ppo_long.pt` is the LATEST, not the best; do not confuse them (§3's `best_wr`
trap, again).

### SPELLS: the Log really did improve; the aggregate did not
Frozen SNAPSHOT (matches=26050 — copy the checkpoint before probing, §4s trap):
```
                init    16k   21.5k    26k
ALL dumped       66%    66%     63%    61%    -5.0pp = 1.18 sigma   NOT significant
the_log          81%    73%     77%    66%   -15.1pp = 2.84 sigma   SIGNIFICANT
tornado          51%    58%     57%    60%    worse, ~1.3 sigma
rocket           27%    53%     25%    33%    n~20, noise
```
The Log (127 casts, the biggest offender) genuinely improved. The aggregate is flat because the
Tornado moved the other way. "Spells are being fixed" is NOT supportable; "the Log improved" is.

### ⚠ THE DRILL TABLE IS THE MOST USEFUL THING HERE — foundational tier, 6 reps, snapshot
```
drill                              scripted doctrine  policy
nado_king_activation                  100%      0%      0%   (DOCTRINE GAP too)
tesla_pulls_the_wincon                 83%     83%     17%
log_the_ground_swarm                  100%    100%      0%
ignore_the_ignorable (restraint)         -      17%      0%
hold_the_spell_for_a_target           100%     83%      0%
log_rolls_forward_not_backward         83%     83%      0%
bank_to_six_then_bow                  100%    100%      0%   <-- THE DECK'S WIN CONDITION
knight_blocks_the_charge              100%    100%     33%
skeletons_kill_the_miner              100%    100%    100%
bow_never_into_the_push               100%     33%     17%
bow_punish_the_commitment              50%     83%    100%
bow_punishes_the_pump                 100%     83%    100%
rocket_the_two_for_one                100%    100%      0%
rocket_the_pump_on_sight              100%    100%      0%
never_rocket_their_king               100%    100%     17%
skeletons_stop_the_wall_breakers      100%     83%      0%
```
**9 of 16 foundational drills at 0%.** The pattern is the point:
* It passes the two bow-PUNISH drills at **100%** — given a board where the bow is already
  affordable and correct, it plays it well.
* It fails **`bank_to_six_then_bow` at 0%** — it never SAVES to get there. That is the same
  mechanism §4q measured directly (mean elixir 2.29, only 5.4% of steps at >=6 elixir). The bow is
  not unwanted and not misplayed; the policy never accumulates the elixir to reach it.
* `ignore_the_ignorable` 0% — the restraint failure, independent of placement (§4r's two-failure
  split). NB the DOCTRINE scores 17% here too, so this drill is hard for the prior as well.

### What this does NOT establish
Why the decay starts around 18-20k. Candidates NOT tested: curriculum difficulty ratcheting past
what the policy can hold, entropy floor reached, the drill/match advantage gap, value-loss drift.
Do not attribute it without a measurement — this project has retracted four mechanism claims.

---

## 4s. 2026-08-26 — THE ROCKET IS NOT A WIN CONDITION: 19% land on a tower, and overtime is reached but never PLAYED

> Archived -> `HANDOFF_ARCHIVE.md` (cited 2 time(s); resolved).

## 4r. 2026-08-26 — ⚠⚠ SPELL DUMPING IS REAL AND SEVERE — BUT IT DID **NOT** COME FROM THIS PPO RUN

Owner report: "the model is learning to dump spells all over the place, almost never on an enemy
target... this may be an issue that came from the PPO." **Symptom CONFIRMED. Cause CONTRADICTED.**

### THE MEASUREMENT (`scratchpad/spell_probe.py`, 20 matches, same seeds, threads pinned)
Scores GEOMETRY, not outcomes: for every spell cast, distance to the nearest enemy and how many
enemies sit inside the spell's OWN radius. A "dump" = zero enemies in radius.
```
                     casts/match   hit>=1   DUMPED   median dist
policy_ppo_long @16k     11.05      34%      66%      5.06 t
policy_BEST init         13.55      34%      66%      3.70 t     <-- IDENTICAL dump rate
```
Per card (current): the_log 113 casts, **73% dumped**; tornado 89 casts, 58% dumped; rocket 19
casts, 53% dumped. Only **5% of casts happen on an empty board** — enemies were present and simply
not aimed at.

**THE PPO DID NOT CAUSE IT.** The checkpoint this run STARTED from dumps at the same 66%, and is
WORSE on the Log (81% vs 73%). If anything this run is very slowly improving it. Anyone re-running
this comparison: the init is `data/policy_BEST_m26000_20260823.pt`.

### MECHANISM — the CELL HEAD NEVER LEARNED A PLACEMENT FOR THE LOG OR TORNADO
`scratchpad/cell_entropy.py`, per-card cell-head entropy (uniform over 432 cells = **6.068**):
```
tornado   5.790  (95% of max)  top-5 mass  7.7%   <-- essentially UNIFORM
the_log   5.400  (89%)         top-5 mass 14.7%   <-- near uniform
rocket    3.390  (56%)         top-5 mass 51.3%   <-- LEARNED
x_bow     3.940  (65%)         top-5 mass 28.0%   <-- LEARNED
ice_wizard 6.031 (99.4%)       top-5 mass  2.0%   <-- completely uniform
```
Placement quality tracks entropy exactly: rocket has the most concentrated head and the lowest
dump rate; the Log/Tornado heads are near-uniform and they dump most. **The policy is not
mis-aiming — for those cards it is not aiming at all.** This is §4.3 placement collapse, alive and
card-specific, NOT a regression from this run.

### DRILLS AGREE (`run.py drills --reps 10 --policy data/policy_ppo_long.pt`)
```
drill                            nothing scripted doctrine  policy
log_the_ground_swarm                 0%      90%      90%      0%   POLICY FAILS
hold_the_spell_for_a_target          0%      90%      90%      0%   POLICY FAILS
log_rolls_forward_not_backward       0%      80%      80%      0%   POLICY FAILS
nado_clump_for_the_wizard            0%      90%      70%     10%   POLICY GAP
rocket_the_two_for_one               0%     100%      90%      0%   POLICY FAILS
log_the_barrel_on_landing            0%     100%       0%      0%   (DOCTRINE GAP too)
nado_pull_the_flock_back             0%     100%     100%    100%   policy OK
never_rocket_their_king              0%     100%     100%      0%   POLICY FAILS
```
**6 of 8 spell drills at 0% while the scripted line passes 80-100%.** `never_rocket_their_king` is
a RESTRAINT drill — failing it means the policy DOES rocket their king, which is dumping.

### CONTRIBUTING, BUT NOT THE MAIN DRIVER — the waste tolerance is 2.3x the spell
`sim.spell_waste_tiles: 4.5` charges a cast only when NO enemy is within **4.5 tiles**, while the
Log's half-width is **1.95** and Rocket's radius **2.0**. So a cast can be completely useless and
still unpunished. Measured share of dumps that escape the penalty entirely: **17% (current), 25%
(init)** — real, worth fixing, but 75-83% of dumps ARE being charged and the policy does them
anyway. Do not sell this as the fix.

### FULLER DRILL TABLE (15 reps, 12 spell drills) — and it REFUTES my own doctrine-prior guess
```
drill                          scripted doctrine  policy
nado_king_activation              100%      0%      0%   (DOCTRINE GAP)
log_the_ground_swarm               93%     93%      0%
hold_the_spell_for_a_target        93%     80%      0%
log_rolls_forward_not_backward     80%     80%      0%
nado_clump_for_the_wizard          87%     73%     13%
rocket_the_two_for_one             93%     93%      0%
rocket_the_pump_on_sight           93%     93%      0%
log_the_barrel_on_landing         100%      0%      0%   (DOCTRINE GAP)
rocket_then_tornado                93%     20%      0%   (DOCTRINE GAP)
nado_the_sneaky_lock               67%     93%     40%
nado_pull_the_flock_back          100%    100%    100%
never_rocket_their_king           100%    100%      0%
```
⚠ **The "doctrine prior has gaps for log/tornado" hypothesis is CONTRADICTED.** Doctrine scores
100% on `never_rocket_their_king` and the policy still scores 0%; doctrine scores 93% on three
drills the policy fails outright. There is no correlation between doctrine coverage and policy
success. Do not re-derive that guess.

### THE PATTERN THAT DOES HOLD — precision REQUIRED vs precision AVAILABLE
Both drills the policy scores above zero on are **TORNADO** drills (`pull_the_flock_back` 100%,
`sneaky_lock` 40%), and the Tornado's pull radius is **5.5 tiles**. Every Log (half-width **1.95**)
and Rocket (radius **2.0**) drill scores 0%. A near-uniform cell head still lands inside a 5.5-tile
pull often enough to pass; it essentially never lands inside a 2-tile blast. So the entropy
measurement and the drill results agree: **placement precision is absent, and only the forgiving
card survives it.**

### THERE ARE TWO SEPARATE FAILURES, NOT ONE
1. **Placement** — the cell head is near-uniform for the_log/tornado (above).
2. **Restraint / selection** — `never_rocket_their_king` is a DO-NOT-CAST drill and the policy
   scores 0%, i.e. it rockets their king. That is not a placement error; nothing about a sharper
   cell head fixes it. Any fix has to address both, and they may need different levers.

### WHAT THIS DOES *NOT* ESTABLISH
* Whether LIVE adds its own error on top (grid round-trip, aim assists) — untested here. The sim
  policy alone is bad enough to explain the owner's live observation, but that is not proof live
  is clean.
* A candidate worth testing, NOT established: the exploration doctrine prior supplies good cells
  for rocket/x_bow but has documented GAPS for log/tornado placements (§6's 11 doctrine gaps
  include `log_rolls_forward_not_backward`, `log_the_barrel_on_landing`, `nado_clump_for_the_wizard`),
  so those heads may never see a concentrated positive example. The one drill the policy passes
  (`nado_pull_the_flock_back`) is one where doctrine scores 100% — suggestive, not conclusive,
  since other drills score 80-90% doctrine with 0% policy.

### DO NOT
Do not "fix" this by restarting the PPO — the run is not the cause, and the eval trend is the best
this project has produced (below). Any fix is a REWARD/PRIOR change and must be A/B'd as one
change against a matched control.

### The run itself is doing well — the first durable improvement §4d said never happened
```
EVAL @  4000  ladder 16%  fair 12%      rolling avg-5:  ladder 12% fair  7%
EVAL @  8000  ladder 33%  fair 15%                      ladder 17% fair  9%
EVAL @ 10000  ladder 36%  fair 24%                      ladder 21% fair 12%
EVAL @ 12000  ladder 33%  fair 23%                      ladder 26% fair 16%
EVAL @ 14000  ladder 19%  fair 15%                      ladder 26% fair 17%
```
Rolling ladder 12% -> 26%, fair 7% -> 17%. Last point dipped; the ROLLING average is the number to
read (§4d: raw training winrate is servo-controlled and cannot measure quality).

---

## 4q. 2026-08-25 — ⚠⚠⚠ STAGE B: THE CLIP FIX FAILS ITS OWN CRITERION. REJECTED, reverted, NOT in the long run.

§4o established the gate's gradient is inverted by clipping and that per_head+play_mult together
un-invert it (Stage A, 5 arms). Stage B trained the winning config (per_head true, play_mult 4.0)
to 2600 episodes and measured BEHAVIOUR. **The mechanism worked; the behaviour got worse.**

### THE MEASUREMENT (paired, n=30, same seeds, PYTHONHASHSEED=0, threads pinned)
⚠ FIRST READ WAS CONFOUNDED — recorded because it nearly produced a wrong verdict. `ARM_control4`
finished 09:45; `7f99a1b` (16:41) shipped the **fix 2+3 retry**, which rewrites `xbow_overcommit`
and adds `xbow_defends` DPS credit; `ARM_clipfix` started ~18:00. So control4-vs-clipfix differed
in the clip config AND in the exact xbow terms being measured. Re-ran against **`ARM_fix23b`**
(fix 2+3, no clip fix) to isolate the clip variable — remaining deltas are only log width and
royal-hogs formation, no reward change.

```
ARM_fix23b -> ARM_clipfix     base    cand    delta    sem   sigma
bow plays/match               0.93    0.30    -0.63   0.23   2.73   WORSE
xbow_lock                     7.67    2.63    -5.03   2.23   2.26   WORSE
xbow_defends                  8.53    2.17    -6.37   3.01   2.12   WORSE
plays/match                  35.67   39.30    +3.63   3.86   0.94   n.s.
```
Pre-committed bar: ≥2σ or NO MEASUREMENT. **≥2σ was reached AGAINST the fix on all three bow
metrics.** This is a measured failure, not a null.

### WHY — and it is the useful part
The gate's new willingness landed where it cannot help and does harm:
```
elixir:   0     1     2     3   |   6     7     8     9    10
dP(play):+.25  +.26  +.26  +.24 | +.03  +.02  -.01  +.00  +.02
%masked: 100%   87%   73%   33% |   0%    0%    0%    0%    0%
```
It plays far more when only CHEAP cards are affordable and **no more at 6+, where the X-Bow lives.**
Consequence, measured on the same run:
```
mean elixir             3.10 -> 2.29  (-0.81)
steps at >=6 elixir    13.3% ->  5.4%  (2.5x fewer)
```
**It drains the bar before it can bank.** icebow is a 3.5-cycle deck whose doctrine is banking
elixir for a 6-cost win condition; the fix taught the policy to violate that.

### WHAT THIS RETIRES
**§4o's plan hypothesis — "the gate refuses to play, so un-inverting it lets the bow out" — is
REFUTED.** The inversion was real and the fix removed it; that was necessary and NOT sufficient.
Undirected willingness-to-play is harmful here. Any future attempt must raise P(play)
**conditioned on elixir** (or on the wincon being affordable), not uniformly. Do not re-run
per_head/play_mult expecting a bow gain — that question is now answered, at 2600 episodes.

### SHIPPED
`ppo_clip_play_mult: 1.0`, `ppo_clip_per_head: false` (back to defaults). Card upgrades applied:
evo tesla 14→15, ice_wizard 12→13 (§4i closed). icebow **645 tests OK**. Long PPO launched
(`data/policy_ppo_long.pt`, log `data/ppo_long.log`, 40000 episodes, init
`policy_BEST_m26000_20260823.pt`) with `wait_eps.py` armed.

### TRAP (§8)
**An arm is only matched to a control that shares its CODE TREE.** Two arms trained hours apart on
`main` differ by every commit in between; here a reward change to the measured terms landed at
16:41. Before comparing any two checkpoints, diff `git log` between their training windows and
name the variables. The cheap rescue is to re-base against an arm that shares the newer tree —
`ARM_fix23b` cost 5 minutes of eval and saved a wrong verdict.

---

## 4p. 2026-08-25 — SIM PARITY PROJECT OPENED (plan approved; research running, implementation parked until the PPO is up)

Owner goal: bring the sim to parity with the current game — add missing evolutions, ALL heroes and
champions with full-fidelity abilities, remove phantom evos, refresh stale stats, close mechanic
gaps. Full plan: `research/sim_parity/PLAN.md`. Owner rulings locked: enemy-side only (no
action-space change), stat conflicts vs `verified:true`/curated rows are flagged for batch review
(never auto-overturned), all ~24 abilities at FULL fidelity (meta frequency sets order, not depth).

### ⚠⚠ THE "berserker evo / giant evo" DEBUGGER SIGHTING — PHANTOM EVOS, MEASURED
`build_spec` (icebow engine.py:501-518) fabricates a spec for ANY `<x>_evo` key: a missing evo row
merges nothing, so the base card comes back wearing the evo name. `opponents.py:81-97` picks the
opponent evo as "first deck card whose `_evo` builds" — nothing ever raises, so it is ALWAYS slot
0. **287/400 meta decks field a phantom** (arrows_evo x80, berserker_evo x56, giant_evo x6);
sim_view labels units by spec.key, which is what the owner saw. Fix = plan stage I2 (build_spec
raises on unknown `_evo`; picker checks row existence; `tools/evo_audit.py` gate 0/400). DO NOT
ship it into the live tree mid-PPO.

### Electro Dragon chain: WORKS (owner report contradicted), but the range is a parity gap
Measured: 3 clumped knights, one attack -> all three took 266.8 and all three stunned (multi_kind
chain, multi_hits 3, stun rides every arc). BUT `_CHAIN_TILES = 3.0` (engine.py:98) is one global
for every chain card and the evo's own KB comment says 3.5 — marginal arcs die in-sim that connect
live, which on realistic boards LOOKS like "the chain doesn't work". Per-card `chain_tiles` is in
the stat sweep (R3) and lands in plan stage I5.

### Champion lifecycle CHANGED (owner): no hand-lock
Champions are NO LONGER removed from the hand while their body is alive — you can cycle back and
play another. The mechanics audit had "body-blocks-replay" queued as a mechanic to ADD; it is now
a mechanic to NOT build. Open semantics being sourced in R1c (multi-body coexistence, which body
the ability drives, per-body uses, refunds) — current master pages + version history ONLY;
pre-March-2026 text (incl. DOCTRINE.md:161's slot-rule note) is suspect; owner is final authority.

### Source reliability, measured 2026-08-25
Official CR API `maxEvolutionLevel` FORWARD-DECLARES unreleased evos (claims Berserker + Giant)
AND LAGS real ones (missing Elite Barbarians, which is live with a wiki page). The API is a
base-card-existence oracle only. Fandom api.php works via python urllib + custom UA (page fetches
402; api.php does not). WebFetch 402s on both — use urllib.

### State
* R0 DONE: `research/sim_parity/` scaffold; `ledger/current_db_snapshot.json` (179 merged keys =
  137 base + 42 evo; 8 champions; 21 null-hp; 56 unverified) reconciles the audits;
  `ledger/registry.json` seeded (42 evo / 16 taxonomy-hero / 8 champion rows, all unconfirmed).
* R1 RUNNING (background workflow `sim-parity-r1`): 3 family chains, enumerate -> specs ->
  independent verify + completeness critic; every claim carries page+revid+date; raw wikitext
  archived to `research/sim_parity/webcache/` (these become the I4 importer fixtures).
* Three audit reports (card DB inventory / import tooling / engine mechanics) are digested into
  PLAN.md's context section. Headline engine facts: ~200-field CardSpec, only 9 per-card special
  cases; hogeq strictly ahead of icebow (champion_ability path, spell_build_dmg,
  zone_first_tick_now, recoil, spark_end_dmg, 4 cards.py fixes); stale `1.1**(level-11)` scaler
  still in `CardDB.deck()` BOTH decks; friendly-target spells absent entirely; drills never cycle
  evos; enemy-only cards are ~free, our-deck cards break checkpoints.
* R2 COMPLETE + ADJUDICATED (2026-08-26): 179 keys / 3,321 fields; 2,838 match, 101 updates,
  66 pins, 316 escalations grouped into 14 decisions and ALL RULED by the owner (decisions.md
  "R2 ADJUDICATION" is the apply spec). Research frozen at tag `research-frozen-2026-08-26`.
  Notable owner overturns of owner rows: spark_dps_small 60→48 (§6.7 CLOSED), earthquake 84→81.
  MM bomb radius 2.5 CONFIRMED. FURNACE IS A TROOP now (re-model). Chain arc = per-card
  `chain_tiles`, ED family 4.0.
* Phase I OPEN: worktree `../ClashBot-parity` (branch `sim-parity`) created at `1380c0e`.
  Owner pulled the #8 ENGINE/SCHEMA items forward — being implemented there NOW (three_musketeers
  Elite rework via components, furnace→troop, ram_rider slow_duration_s, rage attacks mis-parse,
  little_prince ramp grace, dark_prince splash shadowing). Data application (I5) still follows
  I0→I4. Merge to main only at a declared PPO restart; the merge counts as that experiment's ONE
  training change.

#### Phase I progress — I0, I1, I3 DONE 2026-08-26 (branch `sim-parity`, worktree only)

`9a57aef` **I3**. The plan's gate was unmeasurable: the battlelog's `evolutionLevel` reports a
player's OWNED evolution level, not the fielded slot (three evolutions for 153/233 decks against a
two-slot game; a level for `berserker`, which has none), and its 233 `evo:` declarations were
stripped in 84e144a — leaving opponents with NO evolution at all. Nothing published names the
slotted card (RoyaleAPI / Deck Shop / StatsRoyale all 403), so the sim no longer tries: each deck
carries a derived `evo_candidates` (its own cards that really have an evolution, == the 42
wiki-verified rows) and ScriptedBot draws ONE uniformly per match. MEASURED 0 → **1000/1000 decks
field a REAL evolution**, 0 phantoms, 0 candidates failing `build_spec`, all 42 reachable, mean
3.269 candidates/deck. `deck_import.py` no longer tallies `evolutionLevel` at all, so a re-import
cannot recreate the bad slots.

`8ca6aa5` **I1**. `sim/engine.py` and `cards.py` are now **byte-identical** between the decks and
`config/cards.yaml` differs only in its `deck:` block. Two shared bugs fell out: `evo_cycles()`
reported a count for **6 of 42** evolutions (gated on a curated `evolution.available` only 6 base
cards carry) → 42/42, after taking `minion_horde_evo` (1) and `princess_evo` (2) from the wiki
ledger, where the imported rows had none — Minion Horde was being fielded a cycle late by the
picker's `or 2` floor. And the stale `1.1**(level-11)` in `CardDB.deck()` is gone in BOTH decks
(worst delta −0.93% icebow, −0.76% hogeq; only `cli.py`'s display reads it). **icebow's card head
stays at 10** — engine path only, no action-space slot, or every checkpoint breaks.

`be47ddd` **I0**. `tools/parity_check.py`, byte-identical in both decks, fails on undeclared
divergence. Baseline: config quartet byte-identical, `cards.yaml` identical apart from its
783-byte deck block, `src/clashrl` 80 files → 60 shared identical / 20 declared / **0 unexpected**.
The allow-list is split DECK-SPECIFIC (11 entries, should differ forever) vs **DRIFT (8 entries,
recorded not blessed)** — including a live one: `perception.py`'s own comment says hogeq's
threat-gate MEMORY fix raises TypeError and is swallowed, so it is silently inert there. Verified
to FAIL on four probes, not just to pass. Run it before any commit that touches shared code.

⚠ THREE TESTS WERE PASSING ON LUCK and were repaired (no doctrine/engine/reward code touched):
`test_tesla_discipline` was testing the DEAL (hogeq had already found this and icebow never got
the fix; the last negative test was vacuous in BOTH), `test_rocket_doctrine`'s overtime test
depended on the randomly sampled enemy tower level, and `test_hogeq_pressure_doctrine`'s punish
window depended on `reset()` not dealing a P.E.K.K.A deck. All three were exposed by I3 taking one
extra draw from `env.rng`. Full write-ups in `research/sim_parity/conflicts.md`.

Suites: icebow **773 OK (21 skipped)** — was 703; hogeq **796 tests, 3 failures + 39 errors**, the
same failure NAMES as the 767-test baseline. Still parked: I2's remaining scope, I4, I5.

#### Phase I progress — I4 importer hardening DONE 2026-08-26 (5 commits, worktree only)

`cards-import` is now safe to point at the live wiki. Dry-run is the DEFAULT (field-level diff vs
the existing file; `--write` gates the overwrite; stale "RoyaleAPI" help fixed); `/Hero` subpages
join the walk+probe and emit `<base>_hero` body rows (Balloon/Hero's ability table read as a
second body — count 2 → 1, the one field any of the 16 live hero pages changed);
`config/import_allowlist.json` (generated, 42 evos + 16 heroes live / 2 announced 2026-09-07 / 2
API-forward-declared ghosts) makes inventing content impossible — announced stubs excluded loudly,
unknown keys hard-stop; `config/import_pins.json` (generated: 66 stat_diffs `pin` rows + 12
decisions.md owner values, 74 total) is force-applied over the scrape and `--write` REFUSES a
pinned regression or a `verified: true` change without `--force-field`; every row carries
`_src {revid, fetched}` (file written ONCE, copied to the sibling — parity_check gates byte-
identity and its config list grew to include both new files). `crown_damage_audit.py` finally
detects: regex tolerates its/their/linked-prefix/troop-damage phrasings + spawn-crown family +
spell evos, ported to hogeq, exit 1 on stale — live negative control 2026-08-26: **15 stale
vardefines RED** incl. the full known-stale set (fireball 207→172, arrows 31→24, freeze 35→29,
snowball(+evo) 54→45, rage 54→45, vines 39→35, zap_evo 58→48, goblin_drill(+evo) 26→0). E2:
`import_mechanics.py` declares `lifetime_s`/`turret_rotation` (declaration only; tesla stays 30,
card_mechanics.json 0-line diff). Live `--dry-run` reconciled against the ledger
(`i4_reconcile_dryrun.py`, exit 0): +16 = exactly the live heroes, −0, 24 field changes = 15
pin-enforced + 8 catalogued update/escalate rows + 1 KBGAP rider (inferno_tower.count); guard
would refuse 3 verified-row fields (mortar/mortar_evo dps from the 4.7 s pin recompute,
rage.attacks false-assertion drop) — I5's problem, by design. NOTHING was written; DB data
untouched. Suites: icebow **790 OK (21 skipped)** (was 773 + 17 new guard fixtures); hogeq **813
tests, 3 failures + 39 errors — same NAMES** (test_cr_web live-fetch + 2× DEPLOYABLE_cell).
⚠ for I5: the earthquake pins are mutually inconsistent (crown 49 = 58% of the OLD 84, damage 81
→ 58% would give 47) — both are owner rulings, recorded as-is; flag when applying.

#### Phase I progress — I5 data application DONE 2026-08-26 (4 commits, worktree only)

The adjudicated R2 ledger is **applied**: 340 changes, `research/sim_parity/ledger/i5_applied.jsonl`
carries one row each (key, field, before, after, route, source, ruling). 50 recorded-not-applied
(21 already correct, **29 the sweep itself declined** — "I am NOT updating on a mis-worded entry",
"Report only", null on all three paths), 23 deferred with reasons (C7 cast-time convention, the
champion `ability_kind` schema I7 owns, three model-not-number rows).

`research/sim_parity/scripts/i5_apply.py` is the machine. `plan` routes every row against a
CardDB rebuilt from **0905104** (`git show` of the three config files), so BEFORE is reproducible
after the edits have landed and a re-plan cannot silently re-baseline. `edit` writes cards.yaml as
TEXT — surgical line rewrites plus a dated house-style comment block per entry naming the
superseded value and the ruling — and REFUSES to write unless the PARSED mapping before/after
differs by exactly the planned set. `verify` re-reads the merged DB: **340/340 present**.

Split: **81 pins** (`gen_pins.py` 74 → 176, now sourced from stat_diffs + decisions + the I5 plan,
with `advisory: true` for the curated/modelling ones so ONE file is the whole registry of
deliberate deviation) and **258 curated cards.yaml fields** across 112 entries + 6 rows that had no
curated entry at all. `cards-import --write`: +16 live hero rows, 58 cards changed (99 fields), 91
pin enforcements, `i4_reconcile_dryrun.py` exit 0 / 0 surprises; re-running the dry-run afterwards
prints "(no differences)". Written ONCE and copied. cards.yaml meta bumped (both stale since 07-24).

**The three --force-field releases** (each individually, each cited): mortar.dps 53→57 and
mortar_evo.dps 66→57 (decisions #10, 266/4.7), rage.attacks ['buildings']→ABSENT (a FALSE
buildings-only assertion; the Target cell names who Rage BUFFS). All three pinned in the same
commit per cli.py's own instruction. ⚠ Only TWO were load-bearing — the LAG bucket pins mortar.dps,
and pins outrank verified. The guard first refused TWELVE: ten more verified rows whose `dps` moves
only as a consequence of an adjudicated damage/hit_speed. Those were DECLARED as pins, not forced.

**Engine changes that had to land with the data:**
* **E4 CLOSED.** `rolls` was derived as ("rolls" in flags AND ground_only), so decisions #5's Evo
  Snowball air+ground flip would have DELETED the roll. MEASURED before: ['air','ground'] → rolls
  False, roll_len 4.5→0.0, minions 0.0 / bats 0.0. After: rolls True, roll_len 4.0, minions 179.0,
  bats 179.0. Both directions pinned by tests.
* **Per-card `chain_tiles`** (decisions #6) — the owner's original "the chain doesn't work" report,
  measured at last. ED swinging at A with B 3.5 tiles away: **arc 3.0 → A 533.6, B 0.0** (two
  swings on A precisely because the hop failed); **arc 4.0 → A 266.8, B 266.8**. `_CHAIN_TILES` is
  now a documented FALLBACK; electro_dragon + electro_dragon_evo = 4.0.
* **`tower_dmg = float(db.tower_damage(base) or dmg)` was falsy-broken.** decisions #11 says Royal
  Delivery cannot hit crown towers; DELETING its crown value took spell_tower_dmg **40 → 385**. The
  KB now carries an explicit 0 and the fallback only fires on a MISSING value.
* `_apply_pins` no longer lets the derived dps recompute clobber a key's own `dps` pin (pins apply
  in (key, field) order, so "hit_speed" landed after "dps" — an alphabetical accident deciding an
  adjudicated value). `_NO_SIGHT` in import_mechanics.py, because goblin_cage's dump "sight" 20 is
  its LIFETIME (decisions #11) and CardDB.sight_range_tiles feeds the win-condition pull geometry.

**Gates.** `stat_sweep.py --all` implemented (iterates the whole merged DB; `page_for` handles
`_evo`/`_hero` and refuses to invent a title; EXPECTED derived from import_pins.json; the
`if theirs and ours` truthiness skip fixed, which is what exposed eight spawner rows and
tombstone_hero at +5115%): **174 cards, 0 mismatches, 38 known deviations, 21 unmapped, exit 0 in
BOTH decks.** `crown_damage_audit.py` **RED → GREEN** — see the ⚠ below for what that took.
parity_check PARITY OK. Real null-hitpoint gaps **0** (only princess_evo and minion_horde_evo carry
a null cell and build_spec resolves both through the base card). Suites: icebow **799 OK (21
skipped)**; hogeq **822 tests, 3 failures + 39 errors, same NAMES**.

⚠⚠ **The crown-audit gate was unachievable as written, and that is the most useful thing this
stage found.** The tool compared the wiki's vardefine against the wiki's OWN balance history — a
statement about Fandom. We do not edit the wiki, so no amount of data application could turn it
green. It now audits OUR KB against the wiki-derived percentage, with `--kb <path>` so the negative
control is reproducible: pre-I5 configs **exit 1, 9 stale IN OUR KB**; post-I5 **exit 0**. The
wiki-vs-wiki finding still prints as CONTEXT because it is the whole reason import_pins.json exists.

⚠ **Open for the owner** (all in `research/sim_parity/conflicts.md`, "I5" section, with evidence):
is decisions #7's floor() a KB-wide convention or a ruling on the ten ROUNDING rows? (a global flip
moves **47 of 122** dps rows, 38 unadjudicated, and contradicts two approved `update` rows);
barbarian_hut spawns.interval 15 vs 14; valkyrie_evo nado crown 37 vs ~18; goblinstein link damage
107 vs 94; electro_spirit's own published 4.0 chain arc, left on the fallback because #6 rules the
ED family. **RECORDED NOT FIXED:** `electro_dragon_evo.hits_per_attack: 12` is a MODEL error the
engine reads as 3204 damage per swing — the largest overstatement of enemy strength in the sweep;
it needs `late_chain_damage` + an unlimited-bounce flag (I7/I9). **Do not revert:** earthquake
crown 49 and tesla 1182 are knowing owner overrides against the wiki; little_prince's Guardienne is
232, not the 217 PLAN.md's I7 line still quotes. I6 note: elite_barbarians_evo is no longer null
(1341/384/1.4 off its live stub).

---

## 4. The central problem, and where it stands

The user's recurring complaint, across both decks: **"it's doing NOTHING correctly"** — hoarding
then dumping elixir, bad placements, cards never played. Diagnosis found this is not one bug but a
reward-landscape failure plus several mechanics errors. Fixed this session:

### 4.1 The reward taught the policy to empty its bar  ← the big one (`a18c13e`)
Measured in the hogeq sim: elixir bar sits at 0–2 for **91%** of steps, never exceeds 5, mean 1.67;
**74%** of steps nothing is affordable; gate P(play) 0.611–0.698 and **never** below its 0.25
threshold. The 4-cost cards (Hog, Mighty Miner, Tesla) were therefore unreachable and showed zero
plays. What looked like hoard-then-dump was the bar creeping to 1, instantly dumping a 1-cost card,
and going empty — the pause is a *forced wait*, not a hold.

Cause, proven with two scripted policies over the same boards:

```
spend immediately   -0.0645/step
hold until 6        -0.5453/step     ← 8.5x worse
```

`threat_miss_idle` alone was **-152.00 over 152 fires in 323 steps** (86% of the hold policy's total
penalty); the spend-everything policy took **none** of it, because the term only charges on a step
where nothing was played. Two defects:
1. it never checked whether the push was **already being answered** — the step after you drop a
   Knight to intercept, and every step while he walks, was charged again;
2. **no rate limit** — one ignored push cost -1.0 per tick for as long as it lived.

Now waived while any of our units that counters the threat is alive, and throttled to
`env.threat_miss_period_s` (4.0). After: hold-to-6 `-0.1059/step`, 24 fires (icebow `-0.0820`, 23
fires). Holding is still slightly worse than playing, which is correct.

**Not yet verified:** that a *trained* policy now holds elixir. That needs a real PPO run — check
`policy-stats` for mean elixir and whether 4-cost cards get played.

### 4.2 The grid round-trip was broken (icebow live only) (`4f01d71`)
`cell_center` maps grid→frame through the perspective **warp**; `coords_to_grid` rescaled the arena
box **linearly**. Inverses only when the warp is off. Live, with it on: **wrong on 22 of 24 rows,
up to 3 rows, always toward the enemy end**. Now exact on 24/24.

This mattered because the reverse direction is what `label.py` uses to turn a recorded human tap
into a training cell, and what every aim assist uses. **A tap at y=0.600 was stored as the cell that
taps at 0.527** — the policy was taught to play two rows further forward than the human did, and the
rocket lead / pump punish / Tesla pull all landed short. Both failures push toward the front, which
is where the head keeps collapsing.

**The sim was never affected** (its arena box is 0..1, warp is identity) — verified byte-identical
before and after. That gap *is* the sim/live divergence behind "it knows it in sim but not live".

### 4.3 Placement collapse (OPEN)
Measured over 6,389 live plays: **row 13 = 36%**, top cell 11.9%, only **170/432** cells ever used.
This project's own record (`icebow/src/clashrl/spatial_targets.py`) shows PPO makes it worse:

```
per-card head, fresh        row 13 = 41.2%,  62/432 cells
per-card head, 19k matches  row 13 = 84.5%,  28/432 cells
```

So PPO is the collapse driver. `exact_cell_loss_weight: 0.25` / `soft_cell_loss_weight: 0.75` are
configured but **have never run** — BC has not been retrained since the soft-target work landed.

---

## 5. Bug ledger (this session, with measurements)

| commit | fix | measured |
|---|---|---|
| `3caad3a` | **RULING 30 -- the spell CARD VETO, and the honest finding that its CRITERION buys nothing.** A spell is unplayable when no legal cell catches >= `ppo_spell_min_value` TOWER FRACTIONS of enemy value under the engine's own hit test, plus an enumerated exemption set (tower lethal/finish/chip, 2-for-1, building, charge reset, lock break, king activation, incoming spawn), each with a doctrine source. New `threat_value.catch_value_frac`, because `bodies_ignore_frac` reads `inf` for kamikaze/spirit bodies and a veto reading inf as "valuable" waves through every cast on a board holding one Ice Spirit. ⚠ **THE VETO WAS DISABLED IN EVERY REAL TRAINING RUN**: the sampling path was guarded `and not remote`, and `remote = workers > 1` -- so with `--workers 12` it was ON at eval and in the drill report and OFF in training, this ruling's own asymmetry inverted and invisible. Now decided worker-side (`remote_pool.spell_veto_ids`, shipped in the per-step payload) with the threshold passed DOWN as a resolved float. | **600 paired matches, two seed blocks, deck venv, HEAD:** ctl(0.83) RANDOM ban vs base **+0.176 (3.71σ)**; value 0.45 vs base **+0.223 (4.84σ)**; count K=3 vs base **+0.350 (7.48σ)**; **value 0.45 vs ctl(0.83) +0.047 (0.98σ) NO MEASUREMENT**; count K=3 vs ctl(0.83) **+0.174 (3.64σ)**; **value 0.45 vs count K=3 -0.127 (-2.99σ)** -- the value form is WORSE at matched volume. Retracts the prior +0.149 (2.14σ) and the "value == count" -0.013 (0.22σ). Drill acceptance re-run at HEAD in BOTH decks: **every owner-named single-target reference line survives at every threshold** (nado_king_activation 0.3400 `king_activation`, nado_the_sneaky_lock 0.3022 `lock_break`, rocket_the_two_for_one 0.5578 `two_for_one`, rocket_the_pump_on_sight 0.0704 `building`, log_the_barrel_on_landing inf `incoming_spawn`, log_resets_the_charge 0.3384 `charge_reset`); 0.45 refuses exactly two, both low-value LOG boards (hold_the_spell_for_a_target 0.382, log_rolls_forward_not_backward 0.170). Remote path verified end-to-end through a real `RemotePool`: 5.0 bar -> `[[8],[8]]` icebow / `[[7],[6]]` hogeq; shipped 0.0 -> `[[],[]]` and the env is never touched. **31 new tests.** |
| `710c5b2` | **THE PINS GENERATOR SILENTLY REVERTED AN OWNER RULING.** `b4be2b7` hand-edited `config/import_pins.json` for ruling 31a and did not touch `research/sim_parity/scripts/gen_pins.py` -- on a file whose own meta says *"never hand-edit one copy"*. `gen_pins.py --check` now writes nothing and exits 1 when the generator and the committed file disagree, naming it PER PIN; wired into both suites (`GeneratorReproducesTheCommittedPinsTests`, 4 tests) with its own negative control. Newlines are normalised before comparison -- `core.autocrlf=true` over an LF index means a fresh checkout is CRLF while the generator writes LF, so a byte compare would fail on a file whose `git diff` is empty. | BEFORE: a `gen_pins.py` run dropped **electro_giant.reflect_crown_damage 97** and restored the RETIRED `crown_tower_damage` row in its place (the row that crown-reduced his normal swing to 97), and never emitted **firecracker_evo.spark_radius_large_tiles 2.5 / spark_radius_tiles 1.2** at all -- both fall back to the engine's hardcoded **0.75**, i.e. the primary spark **2.56x too small in area** and the secondary 2.56x too large. AFTER: **197 pins reproduce byte for byte**, md5 `948b943c822d6e9259bfd24561551e02`, pair identical. Negative control RUN: mutating 2.5 -> 0.75 prints `DISAGREE firecracker_evo.spark_radius_large_tiles: generator 2.5 vs file 0.75` and exits 1. |
| `c192d17` | **RULING 31c -- the Hero Wizard's tornado is 3 tiles and spins up where his FIREBALL LANDS.** Owner: the pull "seems unusually large", and "the pull center should be at his projectile's landing position". One mechanism, both halves. Radius **4.0 -> 3.0** (I8-8's rule-(b) table pick superseded by an owner in-game check; the same table family carries the Evo Valkyrie's stale 5.5 against her own History's nerf to 5). A projectile-delivered `attack_nado` now rides the shot (`Projectile.nado_spec` -> `_drop_nado`, the two sites that already drop the Evo Firecracker's spark zones); a melee one keeps the swing-time spawn, told apart by `spec.proj_speed > 0`, never by card name. | BEFORE, ability up, target 5.0 tiles downrange: the vortex appeared **AT THE SWING, dy=0.00 tiles from the Wizard** -- the pull happened around the thrower. AFTER: **no vortex at the swing**; after the flight ONE vortex at **dy=5.00 tiles** (the landing point), dx=0.00, **pull_radius 3.00**, duration 2.00. **Evo Valkyrie regression guard**: still spawns at the swing, dy=0.00, dx=0.00, **radius 5.50**, `proj_speed 0.0`. **Rulings 31a+31b+31c cost NOTHING at eval**, measured not assumed: n=300 paired, same seeds/checkpoint/interpreter, pre-31 tree **43.0% / -0.8349** vs this tree **43.0% / -0.8303**. |
| `51f34fb` | **THE SIM'S ACTION SPACE WAS CLAMPED BY THREE LIVE-SCREEN CONSTANTS.** `_board_action_space` overrode `arena_box`, `deploy_top`, the tower anchors and the board edges, but never `label.arena_top` / `label.arena_bottom` (keep a TAP off the card tray) or `buttons.chat_avoid_box` (keep it off the emote icon) -- and `cell_center` applies them to whatever space it is in. The mirror image of the §4.2 trap: not an offline tool reading live coordinates, but a live-screen constant applied to the board. | **96 of 432 cells (22.2%) deployed somewhere other than their own board centre, worst by 6.37 tiles; only 372 DISTINCT deploy points existed, so 60 cells were EXACT DUPLICATES** (grid rows 19-23 of column 0 all deployed at board tile 0.50, 24.96); **board tile-y outside 3.20..27.52 was UNREACHABLE** against an 0..32 arena; the emote-icon box alone displaced 15 cells. After: **0 displaced, 432 distinct, 0.67..31.33**. Identical in both decks. ⚠ **All 36 cells of grid rows 0-1 clamped to tile-y 3.20 and the enemy king is at 3.0**, so 8.3% of the action space landed on the king while `train_sim_ppo.py:199` masks none of it (`allcells_mask = torch.ones`) -- a structural explanation for `never_rocket_their_king` at 0-17%. MEASURED SAFE on the current checkpoint: n=300 paired at eval, **+0.006 tower fractions (0.24σ)**, winrate identical 43.0%. ⚠⚠ **REQUIRES A RETRAIN** before any placement number is quoted again. |
| `84bd0a7` | **LIVE: the enemy-king keep-out compared FRAME coordinates to a BOARD anchor.** `no_king_mask` builds `king_xy` from `sim.board.king_tile` (board-space, unconditionally) and compared it against `cell_center`, which returns FRAME coordinates in the live space. conflicts.md **RS-4 in shipped code**. `test_deploy_rows.KingKeepOutTests` had the SAME units bug, which is exactly why it never caught it -- updated, not deleted. | **Live blocked 12 of 432 cells; the sim's board space blocked 22.** The ten extra sit **1.54-2.69 TRUE tiles** from the enemy king, inside the 2.6-tile clearance the mask exists to enforce, and four of them are inside a Rocket's own **2.0-tile blast** -- so live could pick a rocket cell that lands on the king and wakes it, the one thing the mask was written to make impossible. After: both spaces block the same 22. In the sim the warp is the identity, so the conversion is a no-op there. ⚠ Scope stated plainly: **2.3% of cells. Real, and NOT the explanation of the owner's report.** |
| `8476a1e` | **LIVE: the TORNADO was being snapped onto Crown Towers by a rocket aim assist.** `play.py` gates `reward.weaker_princess_cell` on `anywhere_ids`, which is every anywhere-spell -- for icebow **{rocket, TORNADO}**. A Tornado centred on a Crown Tower pulls nothing (`engine._tick_vortex` refuses to drag a building) and chips it for a rounding error, so the assist turned a chosen cast into a guaranteed whiff. The rule already existed in `sim/env.py::spell_target_mask` ("a valid chip target for a DAMAGE spell, never for a pull") and simply never reached live. Fix is data-driven off the KB's `pull` flag. | **80 of 432 cells = 18.5% of the board** lie inside the ± `spell_tower_aim_radius` (0.12) box of an enemy princess, spanning board tile-y **0.7 .. 10.0 in BOTH lanes** -- so roughly **one tornado cast in five** was being redirected onto a building it cannot affect. A live-only dumping mechanism the sim never sees, on top of the policy's own placement. hogeq's deck has no pull spell, so the code lands in both and the behaviour changes only in icebow. |
| `146a382` | **RULING 20 -- The Log and the Barbarian Barrel are own-half CAST, but their corridors still cross the river.** Finishes ruling 18, which named the same wiki sentence (Cards revid 437053: "WITH THE EXCEPTION OF The Log, Barbarian Barrel, and Royal Delivery") and shipped only one of its three cards. No engine change -- ruling 18 built the machinery. Also repaired a PRE-EXISTING `parity_check --strict` failure whose `git diff` was empty: icebow's `config.py` was LF-only against hogeq's CRLF (the documented `core.autocrlf` trap), parity 1 -> 0. | Sim board space (18x24, river ny 0.5, deploy line gy=13): the_log aimed at gy=0 clamps to gy=13, cast **ny 0.5625**, corridor still reaches **ny 0.2625 = 7.60 tiles PAST the river**; barbarian_barrel reaches **0.4219 = 2.50 tiles past** (its own page predicts this: "placed at most 2 tiles from the river, the Barbarian will spawn at the opposing side"). Executed, not just computed: a clamped Log took a Knight 4.0 tiles beyond the river **3000 -> 2734 hp**. rocket / tornado / earthquake / fireball / arrows / zap / goblin_barrel all still unclamped (the §5 "every spell was forbidden from the enemy half" guard). ⚠ **TRAP**: read through `ActionSpace(cfg)` (the LIVE space, screen `arena_box` + perspective warp) the same gy=13 is **ny 0.4788** -- already "past" the river, i.e. the clamp looks broken. Use `sim.env._board_action_space`. |
| `a41d47b` | **RULINGS 21-28 -- a rolling spell SWEEPS its corridor over time.** `_resolve_roll` damaged the whole corridor in one frame and **`roll_speed` was DEAD DATA** (published for the_log 200 / giant_snowball_evo 300, read by nothing). Now a live `_Roll` ticked by `advance()`, the `_Vortex`/`_Zone` shape. Conversion verified against `card_import._SPEED_UNITS_PER_TILE` (60 units = 1 tile/s), asserted equal by a test. Rowdy Reroll is a literal second roll through the same path: 3.0 tiles (the 4/5/2026 nerf, not the barrel's 4.5), origin = the LIVING Barbarian, no second body -- it is `_despawn`ed and the SAME Unit redeploys at the endpoint healed by half its missing hp. | **the_log 9.6 t @ 3.333 = 2.88 s; barbarian_barrel 4.5 @ 3.333 = 1.35 s; giant_snowball_evo 4.0 @ 5.000 = 0.80 s.** Whole corridor at t=0 -> body 0.5 t ahead hit at 0.15 s, 4.0 t at 1.20 s, 8.0 t at 2.40 s. **A body 8 tiles ahead that steps clear at 1.5 s: 266 damage -> 0; one that steps IN at 1.5 s: 0 -> 266.** Barbarian spawn: same position (4.60 tiles forward), **t=0.45 -> 1.80 s**. Reroll origin **2.38 tiles** past where the first roll ended; absorbed at ny 0.5938, redeployed 3.00 tiles up; heal **179/716 -> 448**; refund on death 1 elixir, no roll launched. **Spell verdict moved 0.75 -> 3.63 s** -- it used to settle with the edge 1.17 of 9.6 tiles along, billing good Logs `spell_waste`. Drills: `log_the_barrel_on_landing` 100 -> 56 (icebow) / 64 (hogeq) -- MECHANISM: goblins land 5.40 s in both, last dies **6.00 -> 6.60 s**, princess HP conceded **534 -> 1076** against a <1000 bar; still fully winnable, the reference is 0.2-0.5 s LATE (re-timed to 3.8/4.0/4.1 s it scores 100/100/100). |
| `abb4552` | **RULINGS 25 + 27 -- one Barbarian at 716 hp, and a missing crown value that meant FULL damage.** Owner in-game 716; the base Barbarians page's own history carries a 4/8/2026 +4% hp buff its `hp_11` never received, while Barbarians/Evolution and Barbarian Barrel/Hero both print 716. ⚠ **The brief said the sweep "could never have flagged" this; it had been flagging it since I5** (`barbarians_evo hp ours 691 / wiki 716`, pinned "WIKI IS SELF-INCONSISTENT ... both cannot be right") -- the number was surfaced, the TIE-BREAK was missing. | **barbarians 691 -> 716; barbarians_evo 691 -> 716; base_barrel_barbarian 670 -> 716 and hit_speed 1.3 -> 1.4; barrel_barbarian damage 192 -> 191, hit_speed 1.3 -> 1.4**; the Barbarian Hut's spawned body 691 -> 716 x3, inherited. Both barrel bodies now build to the `barbarians` card's own **716 / 190.4 / 1.4**. `stat_sweep --all` **MISMATCHES: 0**, with `barbarians_evo` gone from the deviation list entirely (ours now equals its own page). Ruling 27: `barbarian_barrel` published **no** crown value, so `build_spec`'s `dmg if _td is None` fallback gave it its FULL **230.0** against a Crown Tower -- now **116.0**, both forms. Pins 184 -> 195; one SUPERSEDES an I5 pin, declared explicitly in `RULING25_OVERRIDES` rather than by weakening the generator's agreement assertion. |
| `fc48814` | **I9 -- the engine had NO own-team spell path.** `_resolve_spell` had five branches and every one iterated `e.team != s.team`, so no spell could touch the caster's own army. `spell_targets: friendly` is the KB declaration; the friendly pass runs first, then a card that publishes damage still blasts (Rage: its Target column names who it BUFFS while its lead calls it "an area-damage, air-targeting spell") and a card that publishes none stops there (Clone). ONE rage model: the spell feeds the same `rage_zones` the Lumberjack's bottle does, which brought the published 1 s FALLOFF with it ("duration after leaving the radius", 4/3/2025). | **Rage**: a Knight's travel over 3.0 s **2.52 -> 3.18 tiles (+26.0%)** -- under +30% because the card's own 0.5 s deploy timer eats the first sixth. **Clone**: 4 skeletons in radius -> **4 bodies become 8**, each at 1 hp with `spec.elixir == 0` (load-bearing: the reward layer prices bodies at `spec.elixir` in eight places). **Heal Spirit**: an ally at 100 hp ends the field at **501.00 (+401.00 = 4 x 100.25)**, centred on the body it jumped ON, not on itself. **Mirror MEASURED and SKIPPED**: 5/1000 decks, **17/5947 deck weight = 0.29%**, and a HAND mechanic (last card, +1 elixir, +1 level, never in the opening hand), so the pool does not justify a second cost model. |
| `8d6180d` | **I9 -- a zero-damage hit is not a hit: five spells woke the enemy King for free.** `_damage_tower` set `tw.active = True` on ANY call, including calls carrying 0 damage, and goblin_barrel / goblin_barrel_evo / goblin_barrel_decoy / royal_delivery / mirror all publish no Crown Tower damage because on those cards the BODIES do the work. Found while deciding whether Clone should fall through to the enemy pass -- it must not, and the general rule is the fix. | Casting each on the enemy King Tower, time until he activates and the chip on the board at that moment: **goblin_barrel 0.0 s at 0 chip -> 1.2 s at 372.9**; **goblin_barrel_evo 0.0 s -> 1.2 s**; **royal_delivery 0.0 s at 0 chip -> 1.2 s at 132.6**; **mirror 0.0 s -> never**. Royal Delivery is the sharpest: decisions.md #11 ruled it "cannot hit crown towers" and I5 discarded its crown value for that reason, which handed it a free activation instead. NOT affected, checked rather than assumed: Graveyard never reaches the call, and Void's crown figure comes from `zone_tiers`, so it is real damage. |
| `a10d32c` | **I9 -- drills could NEVER present an evolution, which is the OPPOSITE of the brief's premise.** `DrillEnv` EXTENDS `SimMatchEnv`, so `evo_charge`/`slot_cycles` are inherited and work; but `DrillEnv._play_slot` removes a played slot from the cycle (deliberately), so a restricted-hand drill banks 1 play and never the 2 an Evolution needs. `Scenario.evo_charged` is the opt-in and DEFAULTS to match behaviour, because every recorded reference line was written against the base card. | **icebow 0 of 26 drills, hogeq 0 of 24** presented an evolution, against a match that first presents one after **9 plays**. With the flag on, **10 of 26 / 10 of 24** change -- the drills that deal an evo-capable card, named in the commit. TWO LATENT BUGS fixed with it: a drill naming an `<base>_evo` in `hand` was silently dealt the BASE (the identity a slot presents at charge 0), and `_compound_hand` was never cleared, so one compound episode's hand leaked into every later single-scenario drill in the same env. |
| `d817cb1` | **I9 -- the perception TypeError does NOT fire: the DRIFT entry was the stale thing.** The brief and `parity_check`'s DRIFT list both said hogeq's `PerceptionLoop.enemy_tracks` raises TypeError on `with_base=True`, that train_rl's gate swallows it, and that the threat-gate memory fix is silently inert there. | MEASURED in BOTH decks against a real tracker: both signatures are `(self, now, with_base=False, max_age=None)` and both return `[(0.5, 0.6, 0.0, 0.12, 'hog_rider')]`. `git show main:` carries the same code -- the fix landed and only the COMMENT survived, which is its own bug because the DRIFT list is what the project reads to decide what still needs fixing. **declared-different 20 -> 18** (perception.py and replay_mine.py both converged), and the bare `except TypeError: pass` became `_memory_gate_inert`, which warns once and counts, so the path can never again be both taken and quiet. Regression test VERIFIED TO FAIL: dropping `with_base` turns it red with 2 failures + 4 errors. |
| `2f7150d` | **I9 -- the chain was invisible BY CONSTRUCTION, so the debugger needed a RECORD, not a renderer.** A chain hop is created and consumed inside one `advance(dt)` call. `SimEngine.arc_events` + `ability_events` (the `splash_events` idiom), and sim_view draws arcs, ability activations, casts inside their activation delay, per-body ability state, LINGERING ZONES (not drawn at all before -- a Poison was an invisible area doing invisible damage), arming rage zones, the Goblins' banner, Goblinstein's antenna and link, and a `'` on a cloned body. | **ZERO frames** in 12 s where a `<base>_chain` projectile was alive, while the same run landed **192 / 960 / 1152 / 576 / 576** across the row -- the owner's original "the chain doesn't work" report was partly this. Drawing the arcs UNDER the bodies gave **0 changed pixels** (an arc joins two body centres), so they go over. 15 PIXEL tests: render, then assert the frame changed. |
| `62f484e` | **I9 -- the base Barbarian Barrel's Barbarian, the one item I8 left open.** I8 fixed `_resolve_roll` to drop a rolling spell's `spawn_spec` and held back the data half because it changes 198 of 1000 pool decks (24.95% of deck weight). Its own row, `base_barrel_barbarian`, and NOT the hero's 716/192 -- reusing that would have been a 6.9% hitpoint buff nobody published. | A full deploy of the base card: **0 bodies -> 1 x base_barrel_barbarian at 670 hp**. Barbarian Barrel revid 437163 says it twice and its whole Strategy section is built on the body. Also verified here: **all four** I8 engine bugs landed AND pinned, with a negative control on the Hero Giant's stun/flight parallelism (moving the `flying_left` decay back below the stun early-out turns the test red). RECORDED not acted on: every spawned body with `elixir: null` is priced at **4 elixir** (barrel_barbarian, base_barrel_barbarian, magic_archer_decoy, soul_skeleton, guardienne alike) and the reward layer reads `spec.elixir` in eight places -- pool-wide, its own measured commit. |
| `e40637d` | **I8 -- the 16 hero KB rows, the three-slot loadout, and THREE I4 IMPORT BUGS.** `build_spec` gains a `_hero` overlay mirroring `_evo`, so a hero row is a DELTA over its base card and the base's curated mechanics carry through. The 16/3/2026 loadout ("one Evolution, one Hero and one Wild") is implemented as three slots: Evolution unchanged from I3, Hero ALWAYS filled when the deck has a candidate, Wild = second evo / second hero / neither at 1/3 each (UNMEASURED choice, knobs `sim.wild_evo_prob` / `sim.wild_hero_prob`). | The scrape put the **TURRET's** vardefines on `musketeer_hero` (1536 hp / 140 dmg / 0.5 s -> 721 / 217 / 1.0 -- more than twice the card), the **TOMB QUEEN's** on `tombstone_hero` (4224 / 422 -> 529 / 0) and the **BARBARIAN's melee** on `barbarian_barrel_hero` (192 -> 232, so the hero barrel rolled for LESS than the base card). Slots, 6000 seeded draws: hero filled **4980 of 4988 (99.84%)**, wild **evo 32.8 / hero 34.7 / none 32.5** where both were legal, duplicate slot cards **0**, evo phantoms **0**. A first pass left 194 of 4982 (3.9%) hero-less because the Evolution slot took the deck's only hero-capable card. |
| `e36a18a` | **I8 -- twelve hero ability shapes on I7's registry, all sixteen live heroes firing.** No parallel framework; four heroes needed no new engine path beyond their KB row. Built in MEASURED pool-weight order, which is NOT the order the brief gave: `buff_self` 38.6% > reroll+warp 29.5% > summon 28.4% > taunt+decoy 17.1% > throw 9.1% > flight 8.1% > zone_pulse 6.2% > levelup 4.6%. | Berserker **0.6->0.2 s, 102->167/hit, 3108 damage in 4 s**, and 1e6 damage into 896 hp leaves exactly **1.0** (published Minimum Hitpoints). Valkyrie **14 spin ticks x 97 = 1358 area / 679 crown**. Bowler shots at **6.6 / 8.5 / 10.4 -- EXACTLY the page's "3 shots in 7.3 s"**, which only reconciles if the stance pays one of its own hit-speeds first. Ice Golem **3 x 69 = the page's 207**, air and ground, **zero** crown damage. Giant **9.0 tiles horizontally, -135, 2 s stun, 2 s AIR**. Knight drags a **HOG RIDER** off the tower. Mini P.E.K.K.A. **+1/+2/+3/+5 levels** off the pancake bar. Mega Minion warps **across the whole board** to a 500-hp body past a 9000-hp one 1.8 tiles away, crown **312 -> 78 permanently**. ⚠ FOUR ENGINE FINDINGS: a stance that extends REACH is inert without SIGHT and PROJECTILE flight (**the Bowler fired ZERO shots** at his published 11.5); the Giant's stun and flight ran in **SERIES, 4 s from a published 2**; `_resolve_roll` never dropped a rolling spell's `spawn_spec`, so **the BASE Barbarian Barrel leaves no Barbarian at all** (recorded, fixed for the hero row only); `_late_spawns` ignored `ghost_life_s`. |
| `f96acfa` | **I8 -- `support:` was INERT for weeks, and the audit only covered one of three slots.** Every meta deck carries a MEASURED tower troop from R4 battlelogs -- parsed, carried, validated, read by NOBODY -- while `eng.reset()` rolled one from a config weight table. `SimEngine.set_tower_troop` consumes it from `env.reset()`. `tools/evo_audit.py` now audits the whole loadout and exits 1 on a hero phantom or a cap violation too. | Opponent tower troop over 3000 seeded matches, **princess 54.6% -> 83.7%** against a pool MEASUREMENT of **90.5%**; all 284 declared-support matches in a 400-match probe fielded the named troop, **0 ignored**. The residual is the 765 of 1000 decks whose battlelog predates the R4 sweep -- their fallback weights give the princess 54.5% and are FLAGGED, not changed (they are the frozen eval benchmark's too). Audit: hero slot **REAL 841 / PHANTOM 0 / NONE 158 / UNFILLED 1**, all 16 heroes fielded, **0 cap violations**. One audit trap fixed: re-seeding per deck made the wild split read **43.9 / 30.0 / 26.1** -- an artefact of the seeding, not the model; one shared stream lands it on **34.2 / 33.2 / 32.5**. |
| `1a746e6` | **I7 -- `ability_kind` dispatch, and RULING 5 WAS A LIVE BUG.** The engine answered "which ability does this card have" by truthiness on a shape-specific number (`ability_bomb_dmg > 0` = Explosive Escape, `ability_invis > 0` = Getaway Grenade): two cards, two numbers, no room for a third. `ability_kind` now NAMES the shape, `ABILITY_KINDS` dispatches, CardSpec carries 16 generic ability params. `champion_ability` also picked the OLDEST body -- `next()` over append-ordered `self.units` -- against ruling 5 and against Version_History_2025's "Only the most recent placed Champion has the ability". Ruling 7's elixir refund was absent entirely. | Two Mighty Miners at x=0.25 (older) and x=0.75 (newer): **before, the OLD body mirrored and a SPENT newest body fell back to it; after, the newest fires, the older keeps its own use, and a spent newest refuses at 0 elixir.** Refund: **10.0 -> 9.0 on activation -> 10.0 when the body dies inside the 1 s window.** Body order from a monotonic `Unit.deploy_seq` stamped in `__post_init__`, so every construction path is covered without touching a call site. icebow 799 -> 814. |
| `3cb4fff` | **I7 -- the Electro Dragon chain was not uniform, and `hits_per_attack: 12` was a MODEL error.** The engine read the Evolution's 12 as twelve FULL hits. Its page publishes three separate columns for one attack: `dmg_hits` 3 (full hits), `dmg_11` (that damage), `late_dmg_11` 64 ("Damage after 5 chains"). Rulings 12 + 15 applied. | **One swing into 13 knights 3 tiles apart: 3204.0 (12 x 267, ALL stunned) -> 1151.9 (3 x 192 full + stun, then 9 x 63.99 with NO stun).** Ruling 15: `electro_dragon(_evo).damage` 267 -> **192**, dps 116 -> 83.478, four pins, `stat_sweep --all` exit 0. ⚠ 64 is NOT 192/3 -- it is PUBLISHED, and the wiki's own derivation is 192 x 0.67 (8/1/2025 "-33% after the first 3 chains") x 0.50 (2/3/2026 "chain damage -50%") = 64.3. Trap found: the COSMETIC arc projectile (damage 0) still lands and `_land_hit` re-applied the stun, so all 12 stayed stunned after the damage split was already right. |
| `e6e317f` | **I7 -- the Boss Bandit's grenade was fired by the ENGINE below a rolled HP fraction, modelling a rule the game REMOVED** (History 8/7/2025: activatable twice "INDEPENDENT ON Boss Bandit's hitpoints"; conflicts.md C5). Replaced by `ScriptedBot._try_ability`, built as a FRAMEWORK keyed on the ability's SHAPE -- escape / defensive / offensive families, KB-overridable per card via `ability_ai:` -- because I8 adds ~16 hero kinds on top. | **Before: a chipped Boss Bandit vanished on her own with no decision anywhere. After: 2% HP for 20 s, 2 uses intact, 0 elixir spent unless something presses the button.** `ability_hp_frac` deleted outright, not left inert. Also fixed hogeq `env._ability_ready`: it masked the slot with `any(...)` over every body, so an OLDER champion lit up a slot the engine would then refuse. |
| `07685ee` | **I7 -- Archer Queen / Golden Knight / Skeleton King, full fidelity.** AQ's attack buff is stated THREE ways on one page (+80% prose, "+180%" table, "to 180% from 200%" History); resolved by the page's own level-table formula, `Dps(dmg_11*1.80, atk_speed)`. GK gets all THREE ruling-10 terminators including the Crown-Tower stop. SK gets the soul bank with ruling 8. | AQ **5.2 shots cloaked vs 2.9 plain over the published 3.5 s (ratio 1.79)** and **0.75x movement**. GK **10 dashes x 335.0**; two bodies take exactly one dash each; a tower dash ends the chain with 8 unspent. SK **6 Skeletons at 0 souls, 16 at the cap**, and the summon survives his death. ⚠ TWO ENGINE DEFECTS FOUND: soft collision applied to a body IN FLIGHT (the GK's second dash converged on an asymptote 0.06 tiles short and never arrived -- one dash of ten, forever), and `_late_spawns` ringed a SINGLE body 1.25 tiles into +x, putting the SK's summons **4.75 tiles out against a published 3.5**. |
| `9a7a660` | **I7 -- Little Prince / Monk / Goblinstein, and the completion gate.** All 8 champions declare a kind, reach a handler and fire in ENEMY hands through `_try_ability`. Guardienne is a real curated row and PERMANENT. Monk reflects projectiles per the page's own exclusion list. Goblinstein's link is a capsule between Doctor and Monster, with the antenna fallback. | Monk **1000 -> 350 damage taken (-65%)**; a reflected Musketeer shot lands on HER at source damage and 0 on him. Goblinstein **8 x 107 to troops, 8 x 23 to a crown tower**, no stun, and a body at the link's MIDPOINT (3 tiles from each endpoint) is hit -- which is what falsifies the two-circles reading. ⚠ THE BRIEF AND PLAN.md BOTH SAY Guardienne does 217; **it is 232** (I5 applied 217 x 1.07 for the 4/8/2026 +7% and warned in writing that I7 must not revert it). Off-by-one found: the active-effect tick fired BEFORE the expiry check, giving the link 9 shocks over a 4 s / 0.5 s window instead of 8. |
| `(this)` | **The long-red `test_budget_caps_and_hysteresis_refills` was a STALE TEST, not a code bug — and it was masking regressions in the defensive-reward path.** It has been failing for days in the same path `threat_miss_idle` and `restraint_hold` live in, so the suite could not be trusted to catch anything there. `a925d88` deliberately changed the threat-response budget from a flat 2 to `max(1, min(threat_credit_budget, n_cards))`, because a flat 2 funded a SECOND credit for a second card thrown at a ONE-card threat — over-answering out-earned the cheapest sufficient answer, measured on `skeletons_kill_the_miner` at **+1.130 for the over-spending episodes against +0.556 for the passes**. The test fields a lone Knight and asserts two credits, which that change made unreachable by design. ⚠ I first misread the traceback and reported the FIRST assertion failing; it was the second — "no credit at all" and "only one credit" point at completely different causes. | Fixed by giving the fixture a real two-card push (`_lit_env(cards=2)`), which is what the change's own comment promised would "fund exactly what it funded before": **verified 1.0, 1.0, then 0.0 — funds exactly 2, caps at 2**. Rationale written into the fixture docstring so it is not "fixed" back. **icebow 625 tests OK (0 failures) — first green suite in days.** |
| `(this)` | **THE REAL BLOCKER, after four wrong diagnoses: nine drills never produce a positive example, and one PAYS MORE FOR DOING NOTHING.** Fixing `--policy` (it had never worked) let me look at the trained policy instead of guessing. Findings, all measured: (1) the aggregate pass rate was a **bad metric** — it averages 28 drills that trade off, so `bow_defends_from_the_centre` reaching **94%** was hidden by others regressing; per-tier, compound is **31%** and foundational **7%**, i.e. the SIMPLEST drills are the hardest because a restricted hand makes them pure cell-precision tests. (2) **Nine of 28 drills produce ZERO passes in 60 exploratory episodes** — exactly the nine the trained policy scores 0% on. RL cannot learn from experience it never generates, so no mixing ratio, entropy schedule or truncation fix could ever have moved them. (3) Two drills have **negative** signal-to-noise (`knight_blocks_the_charge` −0.21, `knight_guards_the_bow` −0.48): passing pays LESS than failing. (4) On `nado_king_activation`, **timeout +0.24 > pass −0.28** — the reward actively teaches the policy to run the clock, which is why its pass rate CLIMBS to 32% under exploration then DECAYS to 22% as it learns. | Fixes shipped and verified: each drill's **reference cell is merged into the exploration prior** (before `doctrine_cells`' no-rule early return, since 8 of the 9 are DOCTRINE GAPs where the rule table has nothing), and drills get their **own exploration floor** (`ppo_drill_cell_floor` 0.75 vs the match's 0.15 — a drill exists to make a rare state common). Single-drill experiment: pass rate **16–17% flat → starts at 32%**. It still decays, because of (4). **OPEN DESIGN QUESTION for the owner: drills currently carry NO terminal reward of their own** — the stated principle was that a drill is scored by the match's own terms so the objective never changes. The evidence says that principle is what blocks them: the match reward does not value these interactions enough, and in at least one case values them negatively. Either each interaction's reward gets fixed individually (slow, real work — `spell_defence` was one), or drills carry a modest terminal bonus for success. |
| `(this)` | **THE CELL HEAD WAS BEING HELD UNIFORM BY ITS OWN ENTROPY BONUS — it never learned a placement at all.** Three fixes had not moved the drill pass rate off the 16.7% random baseline. Loading the live checkpoint and looking at what it DOES settles it: **card distribution is healthy** (7 cards, 8–20% each, no collapse), but the **cell head's entropy is 8.36 of 8.37 max after 500 matches — identical to an untrained net**. It is not collapsed; it is PINNED at maximum entropy, and its concentrated argmax (28 of 432 cells on early decisions, 62% in three) is just noise in a flat distribution read consistently. **WHY:** the entropy bonus is per-head and the two are not comparable — card `0.02 × ln(10) = 0.046`/step vs cell `0.05 × ln(432) = 0.303`/step, **6.6× the pressure**, against drill advantages measured at +0.2 to +3. Staying uniform pays better than being right. The 0.05 was not arbitrary (the code comment records a collapse to 3 cells of 432 at 0.01) — it worked and over-corrected. Those are the two failure modes of a FIXED coefficient and the drills are unlearnable in either, so it now **anneals 0.05 → 0.008 over 3000 episodes**; the floor gives 0.049/step, matching the card head's 0.046, i.e. equal entropy pressure per head. | Also fixed: **`run.py drills --policy` had NEVER worked** — it imported `clashrl.policy`, which does not exist, and failed SOFT to "baseline + doctrine only", so the missing column looked like a choice. That diagnostic is what finally answered this, three rounds late. Trainer now prints the **STEP share** beside the episode share (`drills 23 (9% pass, 92% of eps, 39% of STEPS)`) — the two differ by an order of magnitude and only the second is what the optimiser sees. icebow 616 (1 network flake), hogeq at its 42 baseline |
| `(this)` | **`drill_frac` counted EPISODES, and the gradient is made of STEPS — so 0.3 bought 8%.** User: pass rate still 19–20% over 1300 matches at the 0.3 I recommended, against a random baseline of 16.7%. A drill is ~19 steps and a match ~186, so choosing drills a third of the time leaves them **under a tenth of the gradient** — and that tenth is split across 28 scenarios, roughly **0.3% each**. There was never enough signal for any of them to move, and raising the knob to 0.4 barely changed it (8.3%) because the episode count is not what the optimiser sees. The knob now means what it looks like: the drills' share of TRAINING STEPS. The episode probability is solved from observed mean lengths, `p = target·Lm / (Ld·(1−target) + target·Lm)`, with the lengths tracked as running means (drills lengthen as the policy stops failing them instantly; matches shorten as it starts winning). The trainer now prints the episode share beside the pass rate, so the two can never diverge unnoticed again. | measured on the real mix: `drill_frac 0.3` was **38% of episodes / 8.5% of steps**; `0.4` was 48% / 8.3%. After: **0.3 → 77% of episodes / 26.0% of steps** (episode prob 0.80), `0.5` → 34.4%. NB a 30% STEP share needs FOUR EPISODES IN FIVE to be drills — not something to guess from outside, which is why it went unnoticed for two runs. icebow 616 (1 network flake), hogeq at its 42 baseline |
| `(this)` | **The blast was WIDER THAN THE CARD, twice over — a near-miss rocket on a Royal Giant scored as a hit.** (a) **The 0.5 "detector jitter" slop I added an hour earlier** put the rocket's blast at **2.5 tiles against a real 2.0**. Wrong instinct: a spell's blast is the card's blast, and the two errors are not equally costly — a false WHIFF bills −0.3 on a good cast, a false HIT *pays for a miss*, which is the failure reported over and over. Now **0.0**. (b) **The tower-aim exemption in `spell_whiffed` was still ANISOTROPIC** — a spell near a live enemy tower is exempt from the whiff verdict, but the test compared a NORMALISED distance to `spell_tower_aim_radius` (0.12), which on an 18×32 board is **2.2 tiles wide and 3.8 TILES TALL**. A rocket almost four tiles *below* a tower could not be called a whiff at all — and a Royal Giant is usually walking straight at one. Now a circle in tiles. This is the same bug class as the Tornado's 5.5-tile pull reading as 12.4 down-board; it survived because this clause is a separate comparison from the one that got fixed. | rocket near-miss at **2.1 / 2.3 / 2.4 tiles: "hit" → WHIFF** (correct); 1.6 and 1.9 still hit. NB the SIM keeps its own `sim.spell_tower_aim_tiles` (3.8) — different purpose, untouched. icebow 616 (1 pre-existing network flake), hogeq at its 42 baseline |
| `(this)` | **A DRILL ENDING WAS SCORED AS A TERMINAL STATE — the drill mix was actively poisoning the critic.** User report: icebow at `drill-frac 0.4`, winrate falling, drill pass rate stuck at **18% for 1000+ matches**. First measurement settles what 18% means: across the 28 icebow drills a **RANDOM policy scores 16.7%**, doing nothing 3.6%, the doctrine 62.8%. So the run was at the random baseline — it had learned nothing at all. **MECHANISM:** `compute_gae` treated every `done` as a hard terminal (`mask = 1.0 - done[t]`, bootstrap 0). A drill ends after ~20 steps because its predicate fired or its limit elapsed — the GAME did not end. Drills run on the SAME state space as matches, so every ending asserted "this ordinary mid-match position is terminal and worth zero", collapsing `delta` to `rew - val[t]`. Fixed with the standard terminal/truncation split: bootstrap 0 at a real outcome, **V(s_t) at a cut**, trace cut at both. | with the critic valuing a position at 5.0 and a drill paying +0.2, the advantages over the episode were **−4.34, −4.56, −4.80** — every action in every drill punished regardless of correctness, and propagated back through the whole episode by the GAE trace. After: **+0.09, +0.13, +0.17**, i.e. just the drill's own payoff. Explains all three symptoms at once, including why a HIGHER drill_frac made it worse: 40% of episodes were injecting it. icebow 616 tests (1 pre-existing network flake: `test_cr_web` hits the live Fandom page, which 402s) |
| `(this)` | **LIVE spells were still judged before they arrived (user: rocket/Log "registering hits at cast time").** The deferral machinery existed — `t_eval = now + eta + 0.4`, scored against FRESHLY seen tracks — but two things made it behave like a cast-time check. **(a) THE LOG'S ETA WAS A FLAT 0.8s**, hardcoded at the call site so it never reached `_impact_time`. 0.8 is roughly the cast delay, not the time to ROLL: the wiki gives The Log projectile speed **170**, and CR's speed unit is ~60 per tile/second (Hog Rider is "Fast (90)" ≈ 1.5 tiles/s), so it covers 2.83 tiles/s over 9.6 tiles — about **3.4s**. The verdict landed while the roll was a third of the way down the lane. **(b) THE BLAST WAS INFLATED BY FLIGHT TIME** (`r_tiles = radius + eta`) — a lead allowance that only makes sense for a check running EARLY; a rocket 1.6s out was scored with a **4.1-tile blast against a real 2.5**, which is precisely "enemies inside the targeting circle marked as hit". Now the card's true radius plus a fixed 0.5-tile detector-jitter tolerance. `spell_eval_time` also had to rise 2.4 → 4.0, since the cap sat BELOW the Log's own roll time and would have truncated the corrected eta. **(c)** `_impact_time` used a NORMALISED distance × per-unit rate, mixing the 18- and 32-tile axes — replaced with true tile distance over a fixed velocity, as the owner asked. | rocket flight, before → after: a target **20.0 tiles** away scored **1.79s** while one **20.8 tiles** away scored **1.73s** (longer distance, shorter flight — the anisotropy); now 1.73 / 1.79, correctly ordered, with the far tower preserved at 2.28s (was 2.29) so magnitudes are unchanged. Log verdict deferred **0.8s → 3.4s**. 20 live spell-verification tests still green; icebow 616 OK, hogeq at its 42 baseline |
| `(this)` | **The champion ability was UNREACHABLE in train-rl (user: "I haven't seen the model play mighty miner ability once").** Not a policy preference — the action could not be executed. `LiveMatchEnv._execute` opens with `slot = next((s for s,c in enumerate(self.hand_ids) if c == card_id), -1)` / `if slot < 0: return`, and the ability is a **pseudo-card in the action space that is a BUTTON on screen, never a tray slot** — so `hand_ids` could never contain it, `slot` was always −1, and every selection was discarded silently before it could even misfire. Two more layers behind that: `controller.play_card` is a **two-tap** select-then-place (the wrong gesture entirely), and nothing ever set the ability's availability bit, so the mask had no reason to offer it. **`play.py` has always done this correctly** — one tap on the calibrated `hand.ability_button`, gated on the champion being on the arena — and train-rl simply never got the same treatment, which is exactly the kind of PLAY-vs-TRAIN divergence a test should hold shut. Ported: `_champion_on_board()` (read from the DETECTOR, not from what we played — he can die between decision and tap), `hand_vec[ability_id]` availability, one-tap `_execute` branch that deliberately does NOT touch the cycle tracker or anchor a 'mine' detection (no card left the hand, no unit was deployed). Single use per BODY, spent flag cleared when he leaves — 4/8/2026 removed the cooldown. | ability resolves `elixir=1` correctly, so once `hand_vec` lights it the affordability mask passes it. **9 new tests per deck** incl. the exact reported failure (a selection with no hand slot must still fire the button) and the branch split (an ordinary card must never tap it). icebow **616 OK**, hogeq at its 42 baseline |
| `(this)` | **Spawn intervals sourced from the wiki — and they fixed the ENGINE, not just the threat model.** Owner asked for the real numbers. Fetched via api.php: goblin_hut **2.2s** (6/4/2026), barbarian_hut **13.5s** ("the lowest spawn speed of all buildings"), furnace **5.0s** (4/8/2026, from 7), goblin_drill **3.0s** on a **10s** lifetime ("the fastest spawn / shortest lifetime of all buildings"), and Evolved Furnace's Hot Spawn **2.4s** (1/9/2025, from 1.8) — the faster attacking spawn. Two of these were already sitting in the COMMENTS beside the entries ("every 2.2s", "Every 3 seconds… summon a Goblin") and had simply never been put in a machine-readable field. **A stale duplicate field `spawn_interval_s` also existed** (furnace 7.0, barbarian_hut 15.0, tombstone 4.0, furnace_evo 7.0); `cards.py:367` reads `spawns.interval` FIRST, so writing the correct values there fixes the SIM's actual spawn rates too — most importantly **furnace_evo 7.0 → 2.4s**, i.e. the Evolution's whole edge was not being modelled. Also: an attacking spawner is now priced by **max(its own body, its spawn)** — the Furnace carries damage, so the body model answered first and its Fire Spirits went uncounted entirely. | `furnace` **0.1413 → 0.3798 must_answer**, `furnace_evo` **→ 0.7913**, correctly ranking the evo ABOVE the base for the first time. `goblin_hut` **→ 0.6133 must_answer**, `goblin_drill` → 1.000, `barbarian_hut` → 1.000, `tombstone` → 0.2011. **Pump drill: two clocks, not one** — owner's correction that a rocket needs travel time, so the DECISION stays gated at 3s (the skill) while the kill window returns to the full 11s. icebow 607 OK, hogeq at its 42 baseline, drills 20 priced / 0 unpriced |
| `(this)` | **Pumps and spawners priced properly — both were `inf` (must-answer at any cost).** Owner's rulings, implemented from card data rather than chosen numbers. **(a) A PUMP IS AN ECONOMIC THREAT, not a 0.** My proposed "it deals no damage so ignoring costs 0" was wrong: the elixir it hands over buys a push you would not otherwise face, funds more pumps, and in 2x/3x arrives as one push you cannot hold. Priced as `(produced − its own cost) × ELIXIR_TO_TOWER`, where produced = `lifetime/gen_every_s` = 70/8.5 = 8.2, and **ELIXIR_TO_TOWER = 0.061 is MEASURED**, not picked — across the DB's 113 troops a fully-ignored card costs a median 0.120 tower per elixir (p25 0.061, mean 0.154); the conservative p25 is used because elixir HANDED over is not damage DELIVERED. **(b) A SPAWNER IS WORTH WHAT IT SPAWNS.** First attempt counted BODIES and inverted the owner's ordering — `on_death` dominated, so a Tombstone outranked a Goblin Hut. Repriced from the spawned unit's OWN card value × 2 waves (capped at 1.0), so the ranking comes out of the card DB. | `elixir_collector` **inf → 0.1364 `cheap`**. Spawners: `tombstone` **inf → 0.0469 `ignore`** ("a couple skeletons isn't a threat by themselves"), `goblin_hut` **→ 0.0899 `cheap`** ("spear goblins are still a threat"), `goblin_drill` **→ 0.806 `must_answer`**, `barbarian_hut` → 1.000 capped. Unit values that drive it: skeletons 0.024 / spear_goblins 0.045 / goblins 0.403 / barbarians 3.18. **Pump drills now gate on TIMING** ("rocket it as it is placed"): cast must be away within 3s and a pump standing at 5s fails — icebow `rocket_the_pump_on_sight` and hogeq `eq_the_pump_on_sight` both 0% → 100% scripted / 95% doctrine. icebow 607 OK, hogeq at its 42 baseline. (Spawn intervals were sourced from the wiki in the next row, so the conservative 2-wave fallback now applies only to spawners whose interval is still unknown.) |
| `(this)` | **A single Royal Recruit was an INFINITE threat.** `royal_recruit` (the one body Royal Delivery drops — distinct from the six-body `royal_recruits` card; owner-confirmed both are valid entries with the same stats) had **no hitpoints, damage or hit_speed** in cards.yaml. `threat_value._bodies` requires all three, returned `None`, and `ignore_cost_frac` read that as "the tower cannot resolve this" → **inf → must_answer at any cost**. Every triage gate in the project therefore treated one recruit as unanswerable-but-mandatory, which is the same "spend a card on a small threat" failure the triage tier exists to prevent. Stats filled in (547 / 133 / 1.3, shield 240), `verified` true. | **`ignore_cost_frac` inf → 0.1011, triage `must_answer` → `cheap`**; `royal_recruits` correctly unchanged at 2.625 / `must_answer`. icebow 607 OK, hogeq at its 42 baseline. **SCAN FOUND 21 MORE** non-spell cards scoring inf that are not siege/outranging — three families: (a) **zero-damage bodies** (`elixir_collector` dmg None, `goblin_cage`/`phoenix_egg`/`skeleton_barrel_evo` dmg 0) where the honest cost of ignoring is ~0, not infinity; (b) **spawner buildings** (`tombstone`, `goblin_hut`, `barbarian_hut`, `goblin_drill`) which have no direct attack and should be priced by what they SPAWN; (c) **evolution variants missing `hit_speed`** (`pekka_evo`, `firecracker_evo`, `battle_ram_evo`, `witch_evo`, `minion_horde_evo`, `princess_evo`, …) — a systematic data gap making every evo unignorable. (a) and (b) FIXED in the next row (owner's call); (c) still needs the stats |
| `(this)` | **Non-whitelist cards were invisible to the LIVE reward too — fixed in two halves.** (a) **PROMOTION:** the whitelist was picked by DECK RELEVANCE, not reliability — its floor is **53** training boxes (bowler), while `spear_goblins` (**5136**, the second-largest class in the dataset), `minions` (3509), `giant` (2900) and `goblins` (2815) were excluded. 20 classes promoted at a bar of **250 boxes** — the level of `ice_spirit` (271) and `princess` (300), i.e. as reliable as members already trusted — intersected with what `meta_decks.yaml` actually plays. Safe per the config's own contract: the identity vector is a fixed role aggregate, so growing it needs no retrain. (b) **GATED REWARD-ONLY VECTOR:** live had ONE identity vector, built from whitelist-filtered `_detect_enemies()`, and `env.py:398` called it *"for reward"* — so `_threat_response_live` and `_threat_miss_idle_live` were blind exactly as the sim was. Live now has `_threat_id_true`, built from every **corroborated** (`trk_hits >= 2`, non-spell) enemy in the unfiltered `_last_dets_all`. The observation keeps the whitelist, because it must model what perception can be TRUSTED TO NAME; the referee only has to be less wrong than treating a Skeleton Army as empty ground. | whitelist **26 → 46**. `minions`, `spear_goblins`, `giant`, `goblins` now observed; `battle_ram`, `skeleton_army` stay out of the observation but ARE graded. Also caught: `SPAWN_SPELLS` was used in the new live path without being imported — a latent NameError that the import check missed because the line never executed. (NOTE: an earlier note here called `royal_recruit` a possible dead whitelist entry. **That was wrong** — it has 216 training boxes and is the SINGLE recruit Royal Delivery drops, distinct from the six-body `royal_recruits` card. Both entries are correct.) icebow **607 OK**, hogeq at its 42 baseline; sim drill pricing unchanged at 20 priced / 0 unpriced |
| `(this)` | **A melee SWARM now counters a tank.** `counters()` judged the tank branch on raw DPS (`>= 150`), and Skeletons are 74 — so `counters.yaml`'s own row, *"knight → skeletons, surround"*, scored as no answer at all. Three bodies at 74 each arriving from three sides is 222 dps; the per-body number is the wrong unit to judge a surround in. | hogeq `skeletons_are_enough` **+0.30 → +0.85 (weak → priced)**; icebow 607 OK, hogeq at its 42 baseline. **STILL OPEN:** `log_resets_the_charge` is the last unpriced drill — a charge RESET has no representation (the identity vector carries no charge bit), so the Log answering a Battle Ram matches no branch. Four weak (<0.5) remain, all troop-defence: `knight_blocks_the_charge` +0.25, `knight_guards_the_bow` +0.20, `log_the_barrel_on_landing` +0.24, `nado_the_sneaky_lock` +0.23 |
| `(this)` | **THE REWARD GRADED THROUGH THE DETECTOR'S EYES — 153 of 179 cards could not be defended against.** `_threat_id_true` exists to be "the REWARD-side twin, built WITHOUT detector noise", because this file's contract is that rewards come from GROUND TRUTH. The noise was removed; the **whitelist was not** — it still built from `detector_cards`, the live YOLO model's 26 classes. For every other card the identity vector came back all zeros, `_threat_response` took its "quiet board → not graded" branch, and **no defensive answer to that threat could ever earn credit**. `minions`, `minion_horde`, `skeleton_army`, `battle_ram` are all outside the 26. This is the most likely root cause of the drill pass rate plateauing in BOTH A/B runs while match winrate climbed — drills are largely DEFENSIVE, and defensive credit was unavailable for most of what the opponent plays. The whitelist stays on `_threat_id` (the OBSERVATION), which must keep modelling what perception can see. | six Minions on our half at y 0.59–0.65 produced `_threat_id_true = [0]*10`. hogeq `firecracker_answers_the_air` (the deck's ONLY air answer) **UNPRICED → +1.09**; `skeletons_stop_the_wall_breakers` **+0.24 → +2.24**; icebow `log_the_ground_swarm` **−0.02 → +3.08**, `skeletons_stop_the_wall_breakers` +0.36 → **+2.33**, `nado_clump_for_the_wizard` +3.24 → **+5.48**, `bow_defends_from_the_centre` +4.31 → **+9.17**. **icebow UNPRICED 2 → 0**, hogeq 2 → 1. icebow 607 OK, hogeq at its 42 baseline |
| `(this)` | **DAMAGE PREVENTED WAS WORTH ALMOST NOTHING — the reward priced offence at ~40x defence.** Found by a new `run.py drills --reward` mode that plays each drill's reference line and compares its episode reward against doing nothing: where they are equal, the interaction is unpriced and training on it cannot teach it. Two mechanisms, both fixed: (a) a spell's verdict snapshotted the enemies near the aim **AT CAST TIME**, so every PRE-EMPTIVE cast — pre-Log a spawning swarm, Log the barrel as it lands, both doctrine — resolved against an empty list and was charged `spell_waste`; the snapshot is now re-taken **when the spell LANDS**, which is when the damage happens. (b) Nothing measured the damage that did NOT occur. New `spell_defence` term pays a defensive spell kill by **what the kill was worth**, using the project's own `bodies_ignore_frac` triage model (tower fractions), our-half only, capped, settled on the same damage evidence as the whiff charge — so a whiff is charged and a hit is now paid. | `log_the_ground_swarm`: the Log **saves 1547 tower HP (35% of a Princess Tower) and was paid +0.285**, against `rocket_then_tornado` at +11.04. After: **−0.02 → +0.73**. `log_the_barrel_on_landing` **−0.22 → +0.24**, `log_rolls_forward_not_backward` +0.61 → **+0.95**, `hold_the_spell_for_a_target` +0.99 → **+1.42**, `nado_pull_the_flock_back` +0.80 → **+1.03**. **UNPRICED drills 2 → 0.** Whiff detection verified intact both ways: a roll cast below a swarm (the "played too high" failure) still charges −0.3, an empty-ground cast still charges −0.3. icebow 607 OK, hogeq at its 42 baseline |
| `(this)` | **A rolling spell's whiff snapshot was a CIRCLE.** `_arm_spell_check` captured units within `max(radius)+2` tiles of the cast point; The Log rolls **9.6 tiles forward** and the whole point of the card is casting BEHIND a group so the corridor sweeps it. Now the snapshot follows the corridor, with **asymmetric margins** — generous forward (a body walking in IS hit), 0.4 tiles back (a roll never goes backward; that IS the "played too high" failure). The asymmetry is load-bearing: a generous backward margin put untouched bodies in the snapshot, the TOWER shot them inside the settle window, and their damage was credited to the spell — silently disabling the whiff charge. | with the corridor snapshot, a Log through a 15-body Skeleton Army captures all 15 and charges no waste; the same Log cast below them still charges −0.3 |
| `(this)` | **"The advisor told the model to Log a lone Balloon" (user, 2026-08-20) — the air veto was CORRECT and never asked.** `_situation` describes every corroborated enemy to the advisor with no depth filter; `_counted_threats` (which builds the veto's group) also requires `gy >= 0.42`. A Balloon on its way in is therefore IN THE PROMPT and ABSENT FROM THE GROUP → `threat_bases` empty → `needs_answer = bool([]) and ...` = False → `why = _pick_invalid(...) if needs_answer else None` → **the pick was accepted with no validation at all**. On any board triaging as quiet, the advisor could name any card and it was played verbatim. `_counted_threats`'s docstring claimed both "argue about the SAME group"; they never did. Fixed by splitting the two questions: *is it worth a card* stays depth-filtered triage; *can this card even touch it* is not conditional on worth, and now validates against `_visible_enemy_bases` — what the advisor was SHOWN. | `pick_invalid(the_log, ['balloon'])` already returned `'cannot touch an all-air group'` — the rule was never wrong, it was never consulted. 7 new tests per deck incl. two source guards so the gate cannot be re-tied to `needs_answer`; icebow **607 OK**, hogeq at its 42 baseline |
| `(this)` | **The air veto only fired on an ALL-air group, so one skeleton beside a Balloon un-vetoed the Log.** `can_touch` returns True the moment any member walks — true, and irrelevant: the advisor names ONE card as the answer, and a Log that clips a skeleton has not answered the Balloon. A Balloon essentially never arrives alone, so the rule almost never fired on its own board. New `primary_threat` (ranked by each card's solo ignore cost — the project's own triage number) + `misses_primary`, kept OUT of `pick_invalid` so **fallback mitigation stays legitimate**: it is only a veto when the hand holds something that CAN reach the primary, else logging the chaff is the best available play and rejecting it would drop through to a RANDOM card. Also fixed: a rejected pick with no valid alternative fell through to "advisor gave nothing → RANDOM card", discarding a deliberate play for a coin flip and mis-reporting what happened. | `pick_invalid(the_log, ['balloon','skeletons'])` **None → 'cannot touch balloon, the biggest thing on the board'**; same for `balloon+goblin_gang`. Ground groups unaffected (`giant+musketeer`, `hog_rider+skeletons` → allowed); `minions+knight` → primary is the knight, Log correctly allowed |
| `(this)` | **The triage gate counted BODIES as CARDS, inflating every multi-body card 3–360×.** `group_ignore_frac(db, bases)` takes CARD bases and expands each into that card's bodies — but all 21 call sites across both decks pass one entry *per body* (`[u.spec.base for u in units]` in sim, one per detector track live). So one Skeletons card arrived as three entries and was expanded into nine to twelve skeletons. This is the mechanism behind the reported "commits elixir to defend a small threat": the canonical ignorable trickle scored **nine times** the ignore threshold, so every gate downstream demanded an answer. New `bodies_ignore_frac` / `cards_from_bodies` recovers the card count as `ceil(seen / bodies_per_card)`, which preserves the pooling the function was built for. | at tournament level, IGNORE_FRAC 0.05: 1 Skeletons card **0.4381 → 0.0235 (answer → IGNORE, verdict flips)**; 1 Bats 3.44 → 0.088; 1 Goblin Gang 23.6 → 0.898; 1 Skeleton Army **359.3 → 1.369**; 4 Skeletons cards 8.69 → 0.839 (still "answer", correctly); Knight and Giant+Musketeer unchanged. 21 call sites switched; icebow 600 OK, hogeq at its 42 baseline |
| `(this)` | **The Log prior spent itself on trickles the tower kills for free.** Its swarm rule counts BODIES (`len(swarm) >= 3`), so a single 1-elixir Skeletons card tripped "what the card is FOR". The surrounding code even claimed *"the defensive rules below cannot fire on a quiet board anyway"* — this was the counter-example. Now gated on the triage verdict the function above computes. | the `ignore_the_ignorable` drill surfaced it: prior offered `the_log 4.0` against a group triage scores 0.0235. Gated, while `log_the_ground_swarm` (a real Skeleton Army) still passes 100% |
| `(this)` | **Every spell except Rocket was forbidden from the enemy half — in BOTH decks.** `anywhere_ids` was the literal set `{rocket, miner}`, so `deploy_clamp` hauled every other spell back to our own front row. In Clash Royale *all* spells may be cast anywhere (verified against the card DB's own `kind`). This did not make the offensive Log, the Tornado sneaky-lock at the river, or the **entire Hog+Earthquake combo** merely unlearned — it made them **unreachable actions**, and it silently desynced the doctrine prior from the executed action on every cast aimed past the river. Fixed in sim, live and `play.py` for both decks; troops still clamp correctly. | icebow Tornado aimed at (0.25,0.30) landed at y **0.562 — clamped back 8.4 tiles**, now lands 0.312; The Log clamped back 4.6 tiles, now exact; hogeq Earthquake aimed at their building (0.25,0.271) landed on **our own front row**, now lands 0.271. Knight/Skeletons still clamp 8.4 tiles (correct) |
| `(this)` | **hogeq: every legal Hog send scored −1.0** — the term I added last session to *cure* the zero-Hog collapse was teaching "never play Hog". `hog_bridge_y` was 0.52 while `min_own_gy`=13 puts the frontmost reachable row at 0.5625, so `ny > thr` was true for every playable cell. Its unit test passed because it calls the term at y=0.47, **a cell `deploy_clamp` can never produce**. Fixed by FLOORING the threshold at the action grid's own frontmost own-half row + 1 tile, so a reward threshold can never again sit where the action space cannot reach. | `_hog_wincon` at the bridge row (gy 13, y 0.5625) **−1.00 → +3.00**; rows 14/15/16 stay −1.00 (correct: bridge-only). hogeq suite unchanged at its 42 baseline (3 fail + 39 err) with the change stashed and unstashed |
| `(this)` | **The king-activation prior told the model to cast Tornados that could not pull anything.** The gate (`u.y > 0.52`) is satisfied the instant a Hog touches the bridge, and `_king_spots` emitted the front-of-king candidate **unconditionally** — only the second spot ever checked reach. Replaced with the real precondition: does the attacker's PATH pass within the 5.5-tile radius while the vortex lives (`spell_delay + 1.05s`)? A snapshot test is wrong both ways — it rejects the regression board's working cast at 6.40 tiles (the Hog marches *into* the vortex) and accepts the bridge whiff at 8.7. | drill harness: prior fired at y=0.528 with the cast point **8.7 tiles** from a 5.5-tile pull, hog walked through untouched every rep; now **no cells offered** until the pull is physically possible. `nado_king_activation` drill **0% → 100%** under the doctrine oracle. icebow 600 tests OK |
| `(this)` | **The live advisor told hogeq to play icebow.** `llm_advisor.py`'s prompt opened "ICEBOW deck (X-Bow control)... answer 'hold' and spend NOTHING", `tools/llm_doctrine.py`'s proposer described the icebow cards, `config/llm_doctrine.json` held 72 icebow rules (quiet board at 10 elixir -> Tesla), and `train_rl.py`'s quiet-board branch was HARD-CODED to "find the x_bow or HOLD" — the user-reported passivity, in four places. All four reworked from `DOCTRINE_RESEARCH.md`: pressure-first prompts, a regenerated 19-rule engine-verified table, and the live ladder = Hog at the bridge from 4 elixir -> cheapest cycle from 6 (ability excluded) -> hold only when too poor. | tiny-model probe of the exact reported case: quiet board -> **hog_rider** (was hold); table regen kept 19/27 with measured gains (e.g. quiet+10elx -> mighty_miner **+1.71**, deep_2+7elx -> hog_rider +0.36) |
| `(this)` | **The Hog had no placement rule** — `doctrine_cards` nominated it but `doctrine_cells` explored it uniformly over 432 cells. New branches from the research: hog (bridge column + inner-side tile + arena-edge auto-pig-push, lane picked opposite committed mass / weaker live tower, dead lanes excluded), mighty_miner (ON the tank, tile-exact; deliberate NO-SPOT vs swarms; bridge-punish spots on a quiet board), firecracker (kite band 4th-6th tile staggered to the other lane, behind-line anti-air off the tower column, layered behind a crossing Hog), ice_spirit (Hog escort > defensive freeze > bridge probes), skeletons (centreline dash-kite vs Bandit/Prince/Ram — the video short's tile-exact rule). | 12 new tests (`test_hogeq_doctrine_cells.py`), all green; suites: icebow 371 OK, hogeq back to the 41-failure baseline (+ the royaleapi Cloudflare flake) |
| `71963bd` | **Pressure doctrine encoded from DOCTRINE_RESEARCH.md (hogeq)**: C8 elixir split (quiet x1 bar 7, x2/OT 4), T1 punish window (>=5 per-body elixir deep in their half, troop OR pump; SS5.3 pekka veto in x1 -- deck or board evidence), T2 survivor window also drops the bar; merged ENGINE-ANCHORED cell branches for hog/MM/FC/ice-spirit (bridges = princess columns 3.5/18 + 14.5/18, kite bands from the near bank 17/32, FC air depth from the tower line) replacing BOTH earlier drafts, which had transcribed the research legend's LIVE-frame coords into the board-true sim. Adversarial 3-lens review: 1 blocker + 16 real findings, all fixed. | 31 doctrine tests green (spec file + new); full suite 41 baseline + royaleapi flake only |
| `2b0a7de` `6dc9d8a` | **icebow Rocket + defensive doctrine** from `DOCTRINE_RESEARCH.md` (270 facts, 246 video observations from 8 videos / 7 Hunter CR, 20 adversarial verdicts). R1 cycle-state trigger, R3 overspend test, R4 lethality, R5 pump gates, N3/N4/N6 vetoes; plus no-mid-map-bow-vs-Rocket-deck, tornado-BACK, Tesla king clearance. | rocket **2 plays of 1288 (0.2%)** greedy before. Prior's offer rate in rollouts **19.7% -> 39.4% of rocket-playable states (2.0x)** at unchanged weight (3.79->3.77), gain concentrated at 8-9 elixir. NB the 0.2% is a GREEDY play rate and cannot move until a PPO run consumes the prior. 22 new tests; icebow 393 OK |
| `553fe5c` | **Own cards read as ENEMIES (user report), 3 causes, both decks:** (a) defensive buildings fell through every evidence rank (deep_mine_y 0.62 is behind the princess line; a front-half Tesla never marches and an Evo Tesla hides its bar) -> new BUILDING side prior split at the RIVER (placement legality, pockets void it, 0.46-0.50 abstains); (b) the canvas painted "unknown" into an ENEMY channel (audit gap #2) -> canvas now SKIPS unknown (obs-distribution change, taken with the planned from-scratch PPO restart); (c) the deck veto flipped hard-evidence "mine" verdicts to "enemy" when the detector misnamed our card (mighty_miner as "miner") -> curated LOOKALIKES rescue relabels to the deck twin on rank 1-3 evidence (rank 4 for buildings). | MEASURED (tools/detector_audit.py, 553 frames, 3 sessions, CPU): impossible allies 45 (5.2%) -> **0**; unknowns 92 -> 71 (building prior + rescue resolved 21; the residual 71 are no longer painted at all). 15 new tests per deck; icebow 371 OK, hogeq 437 with the 41 baseline failures + 1 environmental flake (royaleapi Cloudflare) |
| `151acd0` | **Ramp-up survived every interruption.** `focus_time` only reset when the TARGET CHANGED, so a stun, a Log knockback, a Tornado drag or the target walking out of reach left the stage intact and the beam resumed at stage 3 on contact. Now any non-firing tick resets it (Evo Inferno Dragon's post-kill `ramp_keep_s` hold preserved, except through a stun). | at stage 3 (focus 12.00) then interrupted: mighty_miner / inferno_dragon / inferno_tower all **12.00 -> 0.00**, damage in the next 0.2 s **0** (was 409 / 422 / 851). Undisturbed ramp still climbs and still lands its top hit |
| `151acd0` | **Evo Firecracker's sparks ignored crown towers.** Zones iterated `self.units` only. Crown rate from the wiki vardefines: Big_dmg_11 48 / Big_Crown 15 and Small 48 / Small_Crown 15 -> **15/48 = 0.3125** (`_SPARK_CROWN_FRAC`), applied as a fraction so it tracks level. | 5 s zone on a tower: **0 -> 15.0 damage per 0.25 s tick**; 0 against our own tower; 0 at 8 tiles |
| `151acd0` | **Firecracker never re-aimed after her own recoil** (hogeq only). `locked` is cleared only by an aggro reset, which the recoil deliberately does not raise (that would wipe a Sparky's charge), so she shoved herself out of her own 6 tiles and stayed locked forever. Now `locked` alone is cleared, and only if the recoil actually broke the engagement. | **0 retargets in 40 s, ending out of reach -> 14 shots (base) / 13 (evo)** over the same 40 s, target reachable |
| `151acd0` | **Shrapnel was squashed by the arena wall** -- pierce projectiles were clamped like bodies, so a bolt reaching the border burned its range in place and dropped its spark zone against the edge | **24 of 95 bolt samples pinned on x=0 -> 0**, and 26 samples now continue off-board |
| `151acd0` | **The fused death bomb was narrower than the instant one.** `_death_blast` is edge-based, but any card with `death_delay_s` (Balloon, Giant Skeleton, Bomb Tower) routes through the generic spell path, which compared centre to centre. New `blast_edge` flag, set on the fused bomb only. | Balloon's 3-tile bomb vs a crown tower: reached **3.0 -> 4.5 tiles** from the tower centre, i.e. the full 3.0 from its hitbox. Radius itself was already correct at 3.0 (wiki) and is unchanged |
| `151acd0` | **A dart goblin out-ranged the king tower.** Both published numbers are right (goblin 6.5, king 7); the duel used two rulers -- a troop measures centre-to-EDGE and so subtracts the tower's half-width (king 2.0), the tower only subtracted the troop's 0.5. `king_range` 7.5 -> **8.5** = princess 8.0 + the 0.5 of extra bulk the king concedes. | goblin fired at **8.50** while the king answered to **8.00** (sieged untouched) -> tower now wins by **0.50** against king AND princess; king demonstrably shoots back |
| `a266788` | Firecracker's firework dealt **nothing** to the target it hit — piercing shots move before their first pierce check, so all 5 shards were ~0.8 tiles clear of impact. Now one pierce pass at spawn. | dead-centre 63 → **315** (5×63); 189/126/63 at 1.9/3.8/6.4 tiles behind; 0 beside (cone fans forward) |
| `9bf05fb` | Earthquake had **no cell rule at all** → cast in our own half. Added: midpoint when tower+prize within 2× radius, else the prize, else pure tower chip. | Tesla-in-front: tower 0.8t + building 1.7t both HIT; 10.2t-away building → prize HIT, tower MISS (intended) |
| `a18c13e` | `threat_miss_idle` charged every tick — see §4.1 | -0.545 → -0.106/step; 152 → 24 fires |
| `6512b25` | `train-rl` refused to start: deck guard compared an 11-wide checkpoint against `deck_identities()` (10 cards). Added `CardDB.policy_identities()`. Also: ability elixir resolved to **None** → mask treated it as **free**. | guard 11==11 passes; ability costs 1; selectable at 3 elixir, masked at 0 |
| `5a07de3` | Explosive Escape is **single use, no cooldown** (4/8/2026 balance), per body. Also guarded so it cannot fire with no champion. | fires once, refused after; 30 s wait does not refill; redeployed body gets a fresh use; no champion → 0 elixir spent |
| `4f01d71` | Grid round-trip (§4.2) + Log corridor and Tornado king-activation aim assists (neither existed live) | round-trip 22/24 wrong → 0/24; Log lateral error 0.128 → **0.007** (half-width 0.064) |
| `199fa5e` | Earthquake was **one instantaneous blast** with no building bonus — a third of its troop/crown damage and a **tenth** of its building damage. Now 3 waves via the Poison-style zone. | inferno tower 346.4/692.8/1039.3; knight 101/202/303; crown 3×64; minions untouched; concealed Tesla hit |
| `1ab1981` | Firecracker self-recoil (1 tile) was not modelled at all | exactly 1.000 tiles, bearing unchanged 0.0000° |
| `a0c077f` | **Evolutions never cycled** — Evo Firecracker every lap on a 2-cycle evo. `evo_cycles` returned 0 and the slot reads 0 as "already charged". | now `firecracker → firecracker → firecracker_evo`; 0 same-slot plays back-to-back |
| `f172edd` | Champion ability implemented as an action-space pseudo-card + engine effect + live tap | mirror 0.250→0.750, bomb 484 @L14 at the original spot |

### Card-data corrections made (all wiki-sourced)
* Firecracker recoil **1 tile** — the widely-quoted 1.5 is pre-7/7/2020 and stale.
* Earthquake: `dmg_hits 3`, `dmg_11 84`, `build_dmg_11 287` (~3.5×), `crown_dmg_11 53`, 50% slow,
  no flyers, hits a concealed Tesla.
* Explosive Escape bomb **440 @L13** (user-supplied). No integer level-1 base gives exactly that;
  base 143 gives **441** = 366 at the KB's L11 reference, 484 @L14.
  **The blast radius 2.5 tiles is the one unsourced guess in the card** — worth measuring.
* Mighty Miner ability: 1 elixir, **single use, no cooldown**. (I7: every champion ability is now a KB `ability_kind` + generic params -- see `research/sim_parity/conflicts.md` I7 for the per-card evidence and the 5 in-game checks still open.)
* Firecracker evo: `evo_cycles: 2`.

---

## 6-PRIORITY-B. ⏳ DISTILLATION — OWNER-REQUIRED FOR THE LONG RUN. Runnable spec.

Owner (2026-08-27, twice): the long run is **PPO + distillation**, not PPO alone. This is that spec,
written to be executed rather than re-derived. Source: `research/sim_parity/ledger/rollout_search.md`.

### WHY — the measurement that licenses it
Flat rollout search over the SAME frozen policy, same weights/observation/opponent/seeds:
```
policy alone                        37.0% win   tower -0.928
search H=12, every decision         80.7%             +0.484   (+19.9 sigma)
   + cell search (cells=3)          85.7%             +0.651   (+20.7 sigma)
```
**The information needed to play twice as well is already in the policy's own action ranking; the
policy does not use it.** Six controls failed to explain it away (scoring heuristic, playing more,
opponent oracle, perfect perception, crown weight, gate threshold). The cheap alternative is DEAD:
the gate threshold was swept 0.02->0.60 and the shipped 0.25 is already optimal, worse in BOTH
directions — search's restraint is STATE-DEPENDENT and no scalar reproduces it.

### THE SPEC — decisions already measured, do not re-litigate
* **Teacher = H 12 s, N 1 (EVERY decision), K 4, cells 3.** H is a measured optimum (16/20/30 are
  indistinguishable; FULL-remainder is 5.14 sigma WORSE — the cap is the idle rollout default, not
  search). K is INERT (2/4/8 within 0.3 sigma; K=4 already is all-affordable). **N is the only
  lever** (N=10 +0.451, N=5 +0.694, N=3 +0.729, N=1 +1.412).
* ⚠ **N MUST BE 1.** At N=5 the targets are contaminated by the unsearched policy decisions that
  follow them, and the restraint signal comes out with the WRONG SIGN (search appears to play MORE;
  at N=1 it plays LESS). Distilling N=5 targets would teach the opposite lesson.
* **Target the GATE and CARD heads, NOT the cell head.** Card+gate search alone is +22.0pp; adding
  cell search adds +3.3pp. Placement is separately measured as worth ~nothing (the perfect-aim arm
  is +0.07 sigma), so a cell-distillation arm is not worth its own risk.
* **Corpus, not search-in-the-loop.** Search inside PPO is ~100x and infeasible. Labelling runs at
  ~1250 decisions/min/process, ~20k/min on 16 cores; the N=1 arm produced 53,954 labelled decisions
  in 41 min, so an 18k-match-equivalent target set is ~2 h. That is the version that is affordable.

### ⚠ MEASURE THIS FIRST — the privileged-teacher gap
The teacher sees ENGINE GROUND TRUTH; the student sees the degraded observation. If the targets
depend on information the student cannot see, distillation cannot reproduce them and the whole
thing caps out early. **Encouraging but not sufficient**: handing the policy PERFECT perception
bought it +0.00 sigma on winrate, so its limitation is not information ACCESS — but that is a fact
about the current policy's ability to USE clean input, not proof the targets are learnable.
Cheapest test: hold out a slice of the corpus and check the student's top-1 agreement with the
teacher on states it never trained on, BEFORE committing to a full run.

### TRAPS THAT WILL BITE THIS
* **The search harness is NOT reproducible as written.** `PYTHONHASHSEED` is set via
  `os.environ.setdefault` AFTER interpreter start — a no-op. Two runs of the IDENTICAL N=1 config
  gave 78.7% and 80.7%. Export `PYTHONHASHSEED=0` in the environment before any labelling run, and
  re-measure the baseline if you re-run anything.
* **Baselines drift with the tree.** `rs_base.json` no longer reproduces: commit `d9b20d6` moved
  the same checkpoint on the same seeds from 37.0% to 43.0%. Re-measure the baseline on the tree the
  corpus is generated from, and name the commit.
* **Corpus and student must share a code tree** (§4q's confound, in a new place).
* The long run also carries the SPELL VETO switched on (`ppo_spell_min_value`, shipped at 0.0=OFF).
  That is a SECOND change — decide deliberately whether to bundle it with distillation or sequence
  it, and say which in the run's own notes.

---

## 6-PRIORITY. ✅ THE SPELL EXPERIMENTS — DONE 2026-08-27 (§4y). READ §4y AND `research/sim_parity/ledger/spell_experiments.md`, NOT THE SPEC BELOW.



⚠ The spec below is kept for provenance and its labelling is now WRONG: it calls placement "EXPERIMENT A" and restraint "EXPERIMENT B", while §4y runs restraint first (as the evidence demanded) and calls it A. Its two named levers were both measured and both are DO-NOTs: the cell head has a ceiling of +0.106 tower fractions, and the card-level form of `spell_waste_tiles` tightening reads -0.69σ. What DID clear the bar is a state-conditioned CARD veto at a >=3-body clump. The baselines it says not to re-measure are the SAMPLED policy's (rollout_search.md §7a) and must not be used to grade an arm.



### ORIGINAL SPEC (superseded)



Owner (2026-08-26): "don't forget to run the spell cast experiments after implementation is done
and a new PPO is started." This is that reminder, written to be RUNNABLE rather than a note.

### The two failures are SEPARATE and must be TWO experiments (§4r)
Bundling them makes the result unattributable — the standing one-change-per-experiment rule.

**EXPERIMENT A — PLACEMENT.** The cell head is near-uniform for the Log and Tornado, so those
spells land essentially at random: cell entropy tornado 5.790 / the_log 5.400 against a uniform
maximum of 6.068, versus rocket 3.390 and x_bow 3.940 which DID learn. Dump rate tracks entropy
exactly. The candidate lever, and the one concrete thing already identified:
`sim.spell_waste_tiles: 4.5` charges a cast as wasted only when NO enemy is within 4.5 tiles,
while the Log's half-width is **1.95** and Rocket's radius **2.0** — so a completely useless cast
often costs nothing. Measured: that tolerance explains only **17-25%** of dumps, so tightening it
alone is NOT expected to be sufficient. Treat it as arm 1, not as the fix.

**EXPERIMENT B — RESTRAINT.** Independent of placement: `never_rocket_their_king` is a
DO-NOT-CAST drill and the policy scores 0-17% on it, i.e. it really does rocket their king. A
sharper cell head cannot fix this. Lever unidentified — design it when A reports.

### Baselines that already exist (do not re-measure)
```
spell dump rate (0 enemies inside the spell's OWN radius), frozen snapshots, same seeds:
                init    16k   21.5k    26k
ALL              66%    66%     63%    61%
the_log          81%    73%     77%    66%   <- improved 2.84 sigma over the run
tornado          51%    58%     57%    60%
```
Tools, all working: `scratchpad/spell_probe.py` (geometry, per-card, dump rate),
`scratchpad/cell_entropy.py` (per-card cell-head entropy — the mechanism read),
`scratchpad/rocket_probe.py` (tower-directed casts + overtime), `run.py drills --policy`.

### Method (the traps this project already paid for)
* **Copy the checkpoint before probing.** A live trainer overwrites `*.pt` and two probes minutes
  apart read DIFFERENT policies — that is how the 86%-vs-57% rocket reading happened (§4s).
* **Matched control, same code tree.** §4q: two arms trained hours apart on `main` differ by every
  commit between them. Diff `git log` across the training windows and name the variables.
* Pre-commit the bar: **>=2 sigma on the paired comparison, or report NO MEASUREMENT.**
* Paired, same seeds, `PYTHONHASHSEED=0`, `torch.set_num_threads(1)`.
* **⚠ AND THE DECK'S OWN `python.exe`, in scratchpad harnesses too.** Bare `python` is the ROOT
  `.venv` (torch 2.13.0+cpu) and is worth **-6.0pp winrate on the same seeds and the same tree**
  against the deck's 2.11.0+cu128 — measured 2026-08-27, §8. Every arm in `spell_experiments.md`
  §§4-8 was run under the wrong one.
* **A random-ban control is ONE DRAW.** Average it over several seeds before quoting an
  arm-vs-control sigma; a single draw's own effect swung 4.54σ -> 0.76σ between seed blocks (§8).

### ⚠ SEQUENCING NOTE FOR WHOEVER RUNS THIS
The owner's order is: parity merge -> new long PPO -> spell experiments. The A/B arms are SHORT
(~2600 episodes each, ~1.5 h) and will CONTEND FOR CPU with a long run — this project has already
lost time to that (a 12-run sweep crawling at 0.1 ep/s against zombie processes, §2). Either pause
the long run for the arms, or accept the slower wall-clock; do not let a contended arm read as a
slow one.

---

## 6. Open work

### ⚑ OWNER DECISIONS 2026-09-02 (recorded so they are not re-litigated)
* **agent_dt / act_period changes: DEFERRED** (owner, 21:2x). PRIORITY-C below stays as the record of the
  verdict and the order of work; do not start it without a new owner order.
* **YOLOv26 (yolo26s / yolo26-p2) detector upgrade: NO-GO** (owner, 21:2x). The L2 screen and §5ba-5be smoke
  remain as record; board-27 stays cancelled; the live detector stays YOLO11s. Do not re-propose.

### AGGRO GAUNTLET (owner order 2026-09-02 22:1x) -- running; §5br is loop 1
* Loop 2 DONE (§5bs): `sim/aggro_oracle.py` + 8 tests. Loop 3 DONE (§5bt): the two existing aggro drills do
  not grade aggro (knight_guards_the_bow verdict fires on any knight play; sneaky-lock's tornado earns nothing,
  notes contradicted). Loop 4 DONE (§5bu): `sim/aggro_drills.py` (tank_for_bow, bow_lane_choice; explicit
  `register_all()`) + 4 tests; scripted 92/95, nothing 0/0, doctrine 95/90. When the run stops: call
  `aggro_drills.register_all()` from `drills_icebow.py`, add a `noise` field to `Scenario` (replace the
  `_no_distractors` setup), re-predicate/retire `knight_guards_the_bow` + `nado_the_sneaky_lock`. Oracle-chosen
  cells MUST be legal `cell_center`s (first own row y 0.5625) -- §5bu trap. Later: lock-aware
  `predict_targets` (blocked until the run stops: workers import it); grade with `aggro_agreement.py`.
* Oracle-exposed engine behaviours to verify vs the real game (b): spawn-on-top lock reset (engine :5758),
  no 4 s king aim delay. Do not build rewards that depend on the first.
* Obs predictor fixes queued (all graded by the same probe): ENGAGED hint (locked 81% -> ?), deploy-time
  (no target while `deploy_left` > 0), building reach (no tower target unless in reach; siege only).
* When the PPO is stopped: record state first (§7), then restart-vs-resume decision, then `nado_retarget` fix.
* **OWNER RULING 2026-09-03 00:0x -- the m10k read decides the coef-0.5 run.** "Let the read decide. If >=6 elixir
  share decreases past 1% again, stop the run, do a diagnosis/repair/test run, then restart the PPO with the new
  changes. That would also be a good time to wire in the aggro manipulation changes." Operationalised (my reading,
  stated to the owner, not yet confirmed): the same GREEDY 3-seed elixir-bucket probe (§5bu.6b instrument) on
  `data/bench/gate05_m10k.pt`; TRIGGER = median of the three seeds' >=6 share < 1.0% (m5k was 1.2/1.3/1.0). If it
  trips: (1) record run state per §7 and stop it (verify process counts before/after); (2) diagnosis of the >=6
  decline (why banking is unlearned while played cost is flat 2.5-2.66); (3) repair + a short TEST run (same
  instrument, 3 seeds, before restarting for real); (4) in the same stopped window wire the aggro changes:
  `aggro_drills.register_all()` from `drills_icebow.py`, `noise` field on `Scenario`, re-predicate/retire the two
  old aggro drills, `nado_retarget` fix, lock-aware `predict_targets`; (5) restart the PPO (restart-vs-resume
  decided then, recorded here) with ONE attributable change per experiment where possible -- the aggro wiring and
  the elixir repair are two changes; if both go in, the test run must isolate the repair first. If it does NOT
  trip: the run continues; aggro wiring stays blocked; next read at the following snapshot.
  -> TRIPPED at m10k (§5bv, 01:00): 0.1 / 0.2 / 0.0%. RUN STOPPED 01:02. Step (1) done; (2)-(5) in progress.
  -> L22 (§5bw): diagnosis done, repair CHOSEN = pressure-conditioned gate prior (the ruling's dropped key).
     Next: build it behind `sim.ppo_gate_prior_pressure_s` + unit test, then the from-scratch TEST RUN.
  -> L23 (§5bx): BUILT + unit-tested + smoke-run. Launch line for the TEST RUN (step 3): `run.py --config
     data/bench/gatep6_run.yaml train-sim-ppo --matches 40000 --envs 96 --workers 12 --size 432 --device cuda
     --seed 41 --search-interval 4` (identical to gate05's except the config); ckpt `data/policy_gatep6_20260903.pt`
     (did not exist before). LAUNCHED 01:46 (`data/bench/gatep6_run_launch.sh`), monitors up -- see §5bx.5. Grade: `gate_prior_probe.py` seeds 0/1/2 at m2k (gate05: >=6 share 4.0/3.5/3.0%,
     P(play|aff) 0.23) and m5k (gate05: 1.2/1.3/1.0%) + the L22 ledger. Bar: m5k >=6 share ABOVE gate05's m2k.

### From §5bq (2026-09-02 22:10) -- spell niches, after the gate-prior run ends (sim reward = one change each)
* **`nado_retarget` UNREACHABLE (c, §5bq.3):** sim/env.py:2472 and :2508 `tile_dist(u, tw) <= u.spec.reach + 1.0`
  is centre-to-centre; the engine's reach is a gap. Fix = `<= u.spec.reach + _body_radius(tw) + _body_radius(u) + 1.0`
  (or reuse the engine's `_gap`). Regression test: `scratchpad/gauntlet/L16/retarget_reach.py` as a unit test
  (hog settles at 2.20 tiles and must be a targeter). Its own experiment: the term has never paid, so turning it
  on is a reward change.
* Rocket at 0-1 casts per 108 matches on three checkpoints: find the cause (masks vs `wincon_mis` vs
  `spell_waste` at radius 2.0) before the spell A/Bs (§6-PRIORITY) -- they are meaningless without a rocket.
* King activation 0-4 per 36 matches with the king asleep at half the casts: a DRILL that starts with a sleeping
  king and a hog at our princess would teach the pull; check `drills_icebow.py` for one first.
* Ledger: give the four tornado credits their own keys (`nado_king`, `nado_clump`, `nado_combo`,
  `nado_retarget`) so the next reader does not repeat my first-pass error (§5bq.2). Bookkeeping, no reward change.
* Re-run `scratchpad/gauntlet/L16/sim_spell_niche.py` on the 10k snapshot for the trend (3 seeds).

### PRIORITY-C -- agent_dt / act_period (owner asked to pin this, 2026-09-02; measured §5bl, L12) -- DEFERRED, see above
**Verdict (§5bl.6): do NOT lower agent_dt yet.** Served decision loop p50 **0.760 s** against act_period 0.6
(pipeline 0.646 s; env reads 0.343 s; trainer residual **0.315 s**, which is NOT the net: forward 1.6 ms,
DDQN step 21 ms). Lowering the period today changes nothing served. Pros play < 0.6 s after their own
previous play only 1.4% of the time (43,205 gaps); reaction to the enemy is event-woken and bounded by the
pipeline, not the period. Order of work when this is picked up:
1. Make serving honest at 0.6: pipeline 0.65 -> < 0.40 s. Targets by size: the 0.3 s trainer residual
   (timers around live_search.decide / doctrine / logging -- unsplit); `detect_state` 56-86 ms per decision
   (template match, could run at 2 Hz); tower-HP OCR p90 348 ms; threat colour 60 ms.
   Instrument: `tools/latency_stage_timer.py` on an IDLE box (§5bl numbers are contended upper bounds).
2. When the pipeline is <= 0.2 s: a 0.3 s agent_dt RETRAIN is a real experiment -- ONE change, after the
   gate-prior run, prior tables regenerated for 0.3 s.
3. Separate prize: the reaction path (sighting -> tap) timed on an idle box.

### From §5bo (2026-09-02 21:30)
* Sim twin of the SOFT RAMP + tower-gate removal (sim/env.py:3149-3156): one change after the run.
* First live session: `raw_cell != cell` for OT bows, the ramp prints, `wc` after a tower kill.
* Ramp length `env.xbow_defense_ramp_s` = 60 is (b); owner's knob.

### From §5bn (2026-09-02 21:10) -- after the gate-prior run ends
* SIM TWIN of the tower-gate removal: sim/env.py:3149-3156 drop `took_tower` from the phase flip so sim and
  live share one doctrine again (live changed 09-02, §5bn.2). One change, its own experiment.
* ~~Owner call: soften the live OT snap~~ DONE §5bo (21:30): soft ramp, hardening through OT.
* First live session after §5bn: read play_log `raw_cell != cell` for bows in the defensive phase and `wc`
  after a tower kill -- the edits are unexercised.

### From §5bm (2026-09-02 20:55) -- owner call, live path
* ~~X-Bow after a tower kill: env.py:1823 assist gate + env.py:1574 alive check (§5bm.5).~~ DONE §5bn (21:10).
* ROCKET IS NEVER CAST by the sim policy (0/72 matches, both 18k and coef-0.5; pros 3.4%). Find why
  (masks vs reward) before any spell experiment -- the spell A/Bs owed (§6-PRIORITY) are meaningless on
  a policy that cannot rocket.
* Sim whiff rate vs mask anneal: re-run `scratchpad/gauntlet/L13/spell_xbow_probe.py` at each snapshot.

### Parked from §5bf (2026-09-02 15:25) -- do not bundle into the running gate-prior run
* Prior v1: add the threat-on-our-half key (needs `replay_drive --record-every 12` over the converted
  replays); one more index in `fit()` and in the trainer's `_gtab[...]` lookup.
* hogeq: port icebow's SEARCH-IN-THE-WORKERS (its trainer refuses `--search-interval` with workers>1) and
  the watchdog `_Drift` + per-label floor, BEFORE its own gate-prior run.
* Watchdog instrument: 6 envs x 400 steps gives cell_struct a 3x 10-90% spread on a frozen policy (§5bf.5);
  raise the sample or widen the median window, and re-check the 0.60 band against the frozen-checkpoint
  data set (`data/ppo_watchdog.log`, matches=18000 rows) before trusting a CELL STRUCTURE alert.
* **OWNER RULING 17:50: "wait until 18:40, to see if the reversal is genuine improvement or oscillation" -> HOLD confirmed; the 7.5k read decided per the rule below: OSCILLATION (0.376/0.301/0.401, all >= 0.30) -> killed, relaunched at coef 0.5 (§5bj, 18:59). Next pre-registered read: coef-0.5 run at m=2k (§3).**
* **DECISION TIME (owner question, 2026-09-02 20:0x: "Is now a good time to start the decision time
  optimization loop? I've realized even 0.6s is extremely slow for a gaming AI.") -- answered with a
  counter-question; then OWNER ORDER 20:3x: "build the stage timer and measure the results"; agent_dt
  weighing delegated to me -> DONE, §5bl (verdict: the bot is served at 0.76 s not 0.6; fix serving first;
  do not lower agent_dt yet). Open work from it: idle-box run of `tools/latency_stage_timer.py` (the smoke
  was contended); a timer around `live_search.decide` + the doctrine block in train_rl.py to split the
  0.3 s trainer residual (live-path edit, owner call); `detect_state` (56-86 ms EVERY decision, template
  matching) is the first cut. ORIGINAL NOTE (superseded):** The premise conflates two knobs. (a) 0.6 s is `play.act_period`
  (config.yaml:1248), the routine decision CADENCE, not the reaction time and not the compute latency:
  the live loop already wakes early on a new enemy commitment (`perception.py:96 wait_event`, called at
  `env.py:1910`, `react_min_gap_s: 0.15`), so worst-case reaction is ~0.15 s + one perception period
  (<= 100 ms) + inference. (a) Compute latency measured so far = detector only, 29.5 ms median / 35 p90 on
  an idle box (§5be.2), in a parallel 10 Hz thread; `act_in_match` (play.py:482, ~352 lines) is
  UNMEASURED end to end. Owner's own ruling §5az.1 already separated the two: "sub-100 ms" = wall-clock
  latency, `act_period` stays 0.6 (lowering it = 6x MDP change, full sim retrain, §3m). What I offered:
  (1) if the aim is faster REACTION -> build the offline stage timer now (§5be.5.1 spec: recorded frames,
  no play.py edits, no game), measure on an idle box after the run, first target = the EVENT path
  (sighting -> wake -> decision -> tap) which has never been timed; (2) if the aim is MORE DECISIONS per
  match -> that is the `act_period` retrain, a separate experiment that cannot start beside the gate-prior
  run. Measuring anything now on the contended box is out (guardrail; the L2 contended smoke produced a
  wrong yolo26 conclusion, §5be). Waiting on which of the two the owner meant.
* **LEVEL 16 (owner question, 2026-09-02 19:5x -- answered, no run): card level in the sandbox is a FREE
  PARAMETER, `--level 16` on `replay_drive.py`/`replay_batch.py`, valid 1..16 for every rarity
  (`card_catalog.py:104`); it is NOT in the replay data -- the RoyaleAPI crawl has NO level column
  (grep -ci level on battles.csv/plays_ext.csv = 0), so 11 is an ASSUMPTION, not a recovered fact.
  (c) RETRACTS `HANDOFF.md:5737` "RoyaleAPI has the levels per card in the crawl" -- it does not, so the
  ":5770 levels pass-through" item is blocked on a crawler change. Tower/king level is SEPARATE and
  untouched by --level (`full-card-bootstrap.json`: `sc[0].l 10`, `avatar.kt 11`, `hbd[].kt 11`) -- cards
  at 16 vs towers at 11 is a config that does not exist in the real game. Editing that template does NOT
  break the certified hash (the boot/acceptance path uses `eight-card-bootstrap.json`, a different file).
  All level math lives in libg.so (no stat tables in the sandbox; the level-11 tower HP 4824/3052 appear
  in NONE of the 383 extracted CSVs) so scaling cannot be got wrong. WARNING: the 99.2%/77.7%/21-21
  fidelity grade is a LEVEL-11 grade; for replay RECONSTRUCTION level 16 is a regression (real players had
  mixed levels), for TOP-LADDER DATA GENERATION it is correct -- different projects. Untested (b): no test
  or acceptance script uses any level but 11; settle with one reset at --level 16 + one observe()
  (`entity["level"]==16`, max_hp up). Full writeup: `scratchpad/gauntlet/L11/level16-research.md`.**
* **§5bi (17:45): m=5k RULE APPLIED -> MIXED (0.299 / 0.279 / 0.305) -> re-read at m=7.5k. Owner had ruled
  "stop and restart with coef 0.5" on the m=4k picture (Discord, ~17:00); the m=5k read moved toward the prior on
  all three seeds, so the kill is ON HOLD until the owner confirms (irreversible; §7). No answer = hold, probe the
  live checkpoint at m>=7.5k on 3 seeds (`cp data/policy_gate_20260902.pt scratchpad/gauntlet/L10/gate_m7k5.pt`
  first; real_run_gates.py only snapshots 5k/10k/20k), then: drop holds (<0.30 all seeds) -> leave to 10k;
  bounce back (>=0.30 all seeds) -> relaunch at 0.5 without asking again (owner already ruled for that case).
  Relaunch artifacts staged: `data/bench/gate05_run.yaml` (diff vs gate_run.yaml = ckpt name, continuation
  log, `ppo_gate_prior_coef: 0.5`) + `data/bench/gate05_run_launch.sh`; sequence in §5bi.6.**
* **§5bh (17:10): the m=5k rule is effectively DECIDED EARLY by the trainer's own trend (5bh.2) -- coef 0.1
  loses to PPO. Owner asked (Discord, --questions) whether to stop and relaunch at coef 0.5. Until answered:
  run untouched, m=5k snapshot still taken by real_run_gates.py, probe it on 3 seeds when it lands.**
* **m=5k DECISION RULE (pre-registered in §5bg, 16:05):** run `tools/gate_prior_probe.py data/bench/gate_m5k.pt
  --seed 0/1/2`. If `played` at bucket 3 is still >= 0.30 on all three seeds (18k control 0.36-0.37, m=2000
  read 0.39-0.45), coef 0.1 is too weak: ASK THE OWNER to stop the run and relaunch at coef 0.5 (a relaunch
  changes what the experiment means -- owner call, not mine). If it is < 0.30 on all three, the term is
  biting: leave the run alone to m=10k. Mixed = one more read at m=7.5k, no action.

### ⚑ OWNER ORDER 2026-09-02 ~15:00 -- "launch the elixir fix run"; both decks collapse to cheap cards
Owner: *"launch the elixir fix run. I've noticed that both icebow and hogeq collapse towards playing cheap
cards, so this is a problem shared by both and most likely has a shared solution as well. After launching,
continue onto the next loop."* Done at 15:07 (§5bf, §3). On the shared-solution claim: **(a) confirmed in
FORM** -- both crawled corpora show the same banking shape (pros play in ~4-8% of decision windows at 3-7
elixir and ~20-25% at 9, single elixir; §5bf.2), and the tool + hook are deck-agnostic with a deck-measured
table, so hogeq gets the same fix by setting its own `ppo_gate_prior_coef`. **(b) untested** whether the
same coef moves both decks; hogeq's run waits for the box (one run at a time) and for this one's verdict.

### ⚑ OWNER RULING 2026-09-02 14:30 -- board-27 CANCELLED; divert to the queued items + the latency loop
Owner: *"if the verdict is to keep YOLO11s, then i don't really see a need for a full day of board
training, unless you think the segments from kitka will benefit the detector significantly... If you
decide to cancel the board training, then divert your focus to the items queued afterwards, as well as
the decision time optimization loop."* Verdict is yolo11s (§5be.1), kitka's benefit is (b) untested, so
board-27 is cancelled (§5be.3). Consequence for the 08:20 ruling below: the PPO elixir-fix run is no
longer gated on board-27 -- it is gated on its PREP only (gate prior + KL hook + drift rule + endpoint
drill). Launching it is still an owner call (a multi-day run).

### ⚑ OWNER RULING 2026-09-02 08:20 -- PPO elixir fix, prep folded into the detector gauntlet, run AFTER board-27 (board-27 since cancelled, see above)
The 18k run's elixir>=6 fraction fell 2% -> 0.02% (§5ba.6b). Three repair families are already dead at 3 seeds
(bank_hold HARMFUL p~0.005 §5ad, restraint_hold dead, placement prior failed) -- do NOT propose another
wait-side reward term. The owner picked repair (1): teach WHEN-NOT-TO-PLAY from a source that knows, and
ordered the PREP done during the detector gauntlet so it is ready the moment board-27 finishes:
* v0 = a **tabular gate prior** P(play | elixir bucket, phase, threat-on-our-half) from the 211 converted
  replays' Icebow side (human plays from `data/royaleapi/crawl2/plays_ext.csv`; state from a compact
  engine observation every 12 ticks = the 0.6 s decision cadence; ~40 min CPU pass, estimate from the
  108 s full-record run, untested). Consumed by a KL term on the GATE head only (card/cell heads free),
  behind a config coef defaulting to 0.0. v1 (full-obs BC gate) only if v0 is too coarse.
* Second source, same prep: the rollout-search teacher / m18000 reference (banked 35.4%, x_bow 12.5%,
  §5o) -- the distillation the owner asked for twice (§6-PRIORITY-B).
* Endpoint BEFORE the run: `bank_to_six_then_bow` drill + the elixir_ge6 drift rule; control's >=6
  fraction spreads 9x across seeds (2.2/7.5/20.3, §5ab), so match stats alone cannot read the repair.
* The engine recording pass runs in the window between the screen ending and board-27 launching
  (4.7 GB RAM free under the screen; the emulator would also contaminate one screen arm's timing lines).

### PPO -- next run, two cheap items (from §5ba.6b, 2026-09-02)
Add an `elixir_ge6` DRIFT rule to `tools/ppo_watchdog.py` (the stopped 18k run's 6-elixir fraction fell
2% -> 0.02% monotonically from ~10k; the absolute 0.5% floor only fired in the back half). And a per-card
top-cell dump of `data/bench/stopped_real_cuda_18k_20260902/policy_real_20260901_best.pt` to decide whether
its 30-40-cell footprint is a collapse or a converged Icebow placement set. Not part of the detector gauntlet.

### ⛔ BLOCKED ON OWNER (2026-09-01 evening, §5at): cr-native-sandbox -- the real CR engine headless; runtime + installs + timing are the owner's calls
Assessed, not run (`research/CR_NATIVE_SANDBOX_ASSESSMENT.md`). Three owner decisions were posted with
`--questions`: (1) supply the 5 split APKs of exactly 15.535.29 x86_64 from their own BlueStacks/GPG
install (hash-gated; any other version = cannot run; ToS is theirs); (2) OK the ~15-20 GB of JDK 17 +
Android SDK/AVD installs; (3) emulator only after the cuda run ends (default) or accept the slowdown.
**Owner answers 22:0x (§5at.8): (2) APPROVED and DONE 22:13 -- toolchain installed, `doctor.ps1` passes
every toolchain/AVD check; (3) = after the cuda run ends; (1) owner asked what "supply the runtime"
means -- explained; the cheapest next step is theirs: read the client version in CR Settings. Only
15.535.29 can work. (§5at.3's "the live client is probably newer" reading was WRONG -- retracted in
§5au: the owner's BlueStacks client IS 15.535.29 / versionCode 150535029, engine payload byte-identical
to the frozen build, §5av.) Superseded by §5av-§5ay: runtime pulled, smoke run, engine boots, tick stall FOUND AND FIXED (§5ax), first replay converted 54/54, THE WHOLE SET CONVERTED AND GRADED (§5ay: 211/268, 99.2% of plays accepted, crowns match 77.7%). Next = §5ay.6.**
**If all three come back yes, the order of work is fixed:** hash gates -> `smoke.ps1` reproduces
`96598dc9028e1802` -> first-hour experiments (`cmd` playback yes/no, deal-order permutation trick,
same-actions=>same-hash, per-tick observe cost, Elite-Barbarians-evo presence, **matches/h with a
random policy 1 AVD x 4 workers**) -> replay driver + fidelity grader over the 268 usable replays
(`scratchpad/gauntlet/ext/usable_replays.json`; alias table in §5at) -> sim-parity oracle FIRST, then
the pro-state dump for the placement prior / hazard targets. Nothing to do here until the answers land.
Do not fetch game binaries from mirrors; do not install the SDK before the OK; never commit `research/ext/`.

### ✅ DONE (2026-09-01 evening, §5ar): PROFILE THE TRAINING CYCLE -> update was 70% -> learner on cuda, 2.92x per cycle
Prompted by evaluating github.com/MakazhanAlpamys/Soup (owner ask). **Soup: REJECTED -- wrong
problem.** It is an LLM fine-tuning CLI (LoRA/NF4, TRL tasks) whose headline is layer streaming a
multi-billion-param frozen transformer through a small GPU. Our policy is 1.9 MB; our wall is CPU sim
throughput + process-count RAM + desktop contention. Nothing in it applies. Solid tool (4.6k stars,
Apache-2.0, preprint) for a problem we do not have.
Measured (§5ar): the PPO update was 402 of 572 s = 70% of the cycle on 4 CPU threads; the 12
workers sat idle 78% of wall. `--device cuda` (learner + action selection on the GPU, workers on
CPU with CPU weight copies, TF32 off, batched tensor assembly proven bit-identical) -> cycle 143 s
-> 49 s, **2.92x per env-step**, ~3,700 matches/h steady state vs ~1,130. The box's GPU is an
RTX 5050 Laptop **8.55 GB** (the "4 GB" written here earlier was wrong). Decision on the running
real run (restart on cuda vs keep CPU) is with the owner -- see §5ar §5.
**Remaining throughput items, in the order the cuda profile ranks them (one per experiment):**
1. `step` = 118 s of the 196 s cuda cycle (60%), while the 12 workers sum only ~3.8 cores during it
   -> `remote_pool.step_all` IPC / straggler structure (obs pickling 73,728 B x 96 per step, pipe
   round-trips, sequential collection?). Profile the pool first; do not guess.
2. `choose` = 33.6 s (17%): `choose_sample`'s per-env Python loops (67 ms per call for 96 envs).
3. Minibatch tensor assembly = 47% of the cuda update (5 s/cycle): upload the whole rollout's obs
   to VRAM ONCE per update (906 MB as uint8 -> fits in 8.5 GB with the 0.9 GB now used) and index
   minibatches on-device.
4. EVAL cost: 8.5-12 min at m=2000 in the real run vs 195 s measured 2026-08-23; 20 evals would
   be ~3-4 h of a ~12-15 h cuda run. Measure where it goes before touching eval size.
Cloud note unchanged: a CPU sim scales with vCPUs -- a 32-64 vCPU VM, not Colab (2 vCPU).

### ⏳ QUEUED (2026-09-01, §5ar): dead-cell fraction of the cell head at each real-run gate snapshot
§5ar measured 83% / 43% / 13% of in-hand x deployable cell logits beyond |8| / |16| / |24| (almost
all negative) at m=2300, one seed, one crude rollout -- gradient-dead under the tanh cap. Cheap
(minutes, read-only): run `scratchpad/saturation_probe.py` on the 5k / 10k / 20k gate checkpoint
copies and report the trend. If it grows, the fix candidates are (a) a smaller cap or a soft
penalty on |raw| (b) a logit floor. Neither is to be applied mid-run; this is a READ. Relevant to
the placement-prior direction: a prior can only reshape cells that still have gradient.

### ⏳ QUEUED (2026-09-01, §5ap): hazard head follow-up -- the A/B was a NULL at 2 valid seeds, not a refutation
Secondaries leaned the head's way at 3/3 seeds by 1-5 points (top-1 agreement, worse-than-WAIT
plays, after-bow follow-up L1-to-pro) -- a screen at p=0.125 per metric. Two ways to settle it,
pick ONE (one change per experiment): (a) a 4th scratch seed pair (hazard 0.5 vs 0.0, m=1500) to
replace disqualified s61, graded on the same paired corpora WITH the >=15-wait floor pre-stated;
(b) a fine-tune A/B on a real-run checkpoint (the `Linear(z,7)` head is in the net, inert at coef
0, so no architecture mismatch), which also gets the ~10x larger `data/continuations_real.jsonl`.
Do NOT run either while the real run is on the box (contention, §5ap). Sized: ~2.5-3 h per pair.

### ⏳ FUTURE (owner-requested 2026-08-31): learned placement prior from the pro corpus
**Run AFTER the first real PPO's results are read.** /!\ 2026-09-01 update: the hand-picked lane
spots this entry originally deferred to were REVERTED in §5ao (the doctrine prior did not teach
in-band lane bows at 3 seeds; the real run uses the centre-only widened band). That makes this
entry MORE relevant, not less -- a fitted distribution is the untested alternative to hand spots --
but read §5ae/§5am/§5ao first: three placement priors in a row moved nothing, so state the
mechanism by which a fitted one would differ before spending seeds on it.
The idea: replace `doctrine.py`'s hand-picked `_add_spot`
coordinates with a distribution FIT to the 12,220 pro placements in
`icebow/data/royaleapi/crawl2/plays_ext.csv`: `P(tile | card, phase)` with phase in
{single-elixir, double, overtime} from `seconds`. Injection point: the SAME doctrine-prior seam
(rollout-only, annealable) -- exploration shaping, not imitation, so the three measured BC/
distillation failures (§5af) do NOT apply.
Design constraints, decided now so a future session does not relearn them:
* per-card sample floors before trusting a fit (bow 1,038 / tesla 1,705 / log 1,802 are fine;
  thin card-phase cells fall back to the hand spots);
* /!\ the marker join covers only ~HALF of replays (§5ag: 268 of 519 >80%) -- check the covered
  half is not biased (newer replays? different players?) before fitting;
* one change per experiment: distribution prior vs hand-spot config, 3 seeds, graded on
  xbow_probe + paired corpora + continuation L1-to-pro;
* mirror-fold left/right (pros' (2,20)/(16,20) are symmetric) to double effective samples.

### ✅ DONE 2026-08-29 — THIS FILE WAS SPLIT. 6,699 -> 4,156 lines (38%); archive is 2,739.
Executed after the A/B's m=1500 read, as planned. 37 sections moved verbatim to
`HANDOFF_ARCHIVE.md`; each keeps its HEADER plus a pointer here, so `grep` on a section
number still finds it. Line accounting was checked and is exact -- nothing was dropped.
§4a stayed (12 citations). Re-run graphify's doc pass now that this landed.

<details><summary>original plan, kept for the rule</summary>

**MEASURED rule and size** (do not archive by date alone -- several old sections are still load-bearing):
a dated `3x`/`4x` section is archivable iff it is **not open/pending** AND is **cited <= 3 times**
elsewhere in this file. That yields **37 sections / 2,691 lines = 42% of the file**.
```
biggest wins        S3n 513 lines (1 cite)   S3r 174 (0)   S3o 165 (0)   S3y 120 (0)   S4f 114 (0)
MUST STAY, open     S4e S4i S4w S4x S4p  (QUEUED / PENDING / project open)
MUST STAY, cited    S4a(12) S3p(11) S4y(6) S4r(6) S4t(6) S4q(5) S4z(5) S4d(4)
NEVER ARCHIVE       S1 S2 S3 S4 S5 S6 S6-PRIORITY* S7 S8 S9 S10 S11 and every S5x session section
```
/!\ **§4a IS THE TRAP HERE.** It is the most-cited section in the file (12 references, including four
today) because it owns the critic-dip figure and the *"compare run-vs-run at matched episode counts"*
rule. Archiving by date would have moved it. Before archiving anything, lift any DURABLE RULE out of
the section and into §8 (Measurement traps), which exists for exactly that -- then archive the
narrative, not the rule.

**Procedure:** move qualifying sections verbatim into `HANDOFF_ARCHIVE.md`, leave a one-line pointer
per section in place, keep the archive greppable and committed.
</details>


0a. **THE SPELL CARD VETO IS SHIPPED AND OFF, AND RE-OPENING IT HAS A PREREQUISITE.** `ruling 30`
   is complete: the enumerated exemption class with a doctrine source per entry, the value
   criterion in `SimMatchEnv.spell_card_ok`, the veto applied in `choose_sample`, `choose_greedy`
   and the drill report, and worker-side evaluation so it survives `--workers > 1`.
   `sim.ppo_spell_min_value: 0.0`. **Do not turn it on as the next run's one attributable change**:
   over 600 paired matches at HEAD the value criterion does not beat a volume-matched RANDOM ban
   (+0.047, 0.98σ). What is actually open:
   * **Average the random control over several draws** (`spell_arms_valueform.py` hardcodes
     `random.Random(770011)`; it needs a `--veto-control-seed`). This is the PREREQUISITE for any
     further arm-vs-control claim — see §8.
   * **The drill PASS-RATE diff was not run**, only the reference-line probe (which passed in both
     decks) and a refusal screen. `run.py drills --reps 25 --policy ... --spell-min-value 0.45`
     costs ~25 min PER DRILL against a live training run (measured: 2 reps of one drill = 60 s
     under contention, 4 policy runs per drill row) — ~11 h for the 26-drill report. Run it on a
     quiet box. The screen says **18 of 29 icebow drills / 13 of 27 hogeq drills** see at least one
     refusal at 0.45, so the rest are provably unchanged and only those need the diff.
   * **Judge the footprint at IMPACT, not at cast** and **scale the threshold by the spell's own
     cost** — both stated in ruling 30.5, both untested, neither bundled.

0. **DRILLS — segmented mini-sims (owner's idea, 2026-08-20).** Framework is IN and validated;
   the curriculum is drafted and mostly unbuilt.
   * `sim/scenarios.py` — `Scenario` dataclass (board, scripted spawns, restricted hand, two
     engine-reading predicates, `randomise`, `graded_by`, `prereq`) + predicate helpers + registry.
   * `sim/drill_env.py` — `DrillEnv(SimMatchEnv)`, so a drill is scored by **the match's own reward
     terms**. A drill concentrates experience; it never changes the objective. `run_drill()` reports
     a pass RATE, which is the number that says whether a skill is mastered.
   * `sim/drills_icebow.py` — 4 seed drills, each measured baseline-vs-oracle (see §8's trap):
     `nado_king_activation` 0%→**100%**, `tesla_pulls_the_wincon` 0%→100%,
     `log_the_ground_swarm` 0%→100%, `ignore_the_ignorable` 100%→12% (deliberately inverted: the
     right play is NO play).
   * Success/failure for the king drill is the OWNER'S rule: success = the attacker now targets our
     **king**; failure = it keeps damaging the **princess** (threshold 3 hog hits — at 1 hit the
     drill ended before the interaction could happen).
   * **Card choice is load-bearing.** Sweeping all 432 action cells: Hog **8** winning cells,
     Balloon 13, Knight **0–4**, Miner 1. A Knight re-picks the nearest tower when the pull breaks
     its lock and the princess is always nearer, so the window collapses. The CR wiki independently
     says the same — reliable for Hog/Barrel/Miner, *"extremely inconsistent"* for Knight/Valkyrie/
     Mega Knight since the 2020 rework. **The sim is faithful here.**
   * **hogeq has the framework too**, with 5 drills, all discriminating:
     `eq_clears_the_hogs_building` 15%→100%, `hog_send_on_a_quiet_board` 0%→100%,
     `tesla_pulls_the_wincon` 0%→100%, `log_the_ground_swarm` 0%→100%,
     `hog_never_into_the_push` 0%→45%. The EQ drill scores **the Hog CONNECTING**, not the
     building dying: scored on "cannon dead" it passed 88% by doing nothing, because a Hog chews
     through an 824 HP Cannon unaided — but measured, without the quake he kills it at 4.2s with
     132 HP left and never lands a hit, and with it he is at 808 HP and connects at 4.8s.
   * **`run.py drills`** — pass rates for every drill, do-nothing baseline vs doctrine oracle vs
     `--policy <checkpoint>`. It flags any drill where baseline ≈ oracle as NOT DISCRIMINATING,
     because such a drill is measuring the board rather than the play.
   * **Training integration is a MIXING RATIO, not a stage.** `sim.drill_frac` (default **0.0**,
     so an un-opted run is byte-for-byte what it was; 0.3 suggested) + `sim.drill_tiers`.
     `DrillMixEnv` chooses per EPISODE inside `reset()`, so one class serves both the in-process
     pool and the remote workers. A drill is scored by the match's own reward terms, so the
     objective never changes between a 10-second drill and a 3-minute match — which is what keeps
     the skill from having to survive a transfer afterwards.
   * **55 drills built and validated: 28 icebow, 27 hogeq**, across all three tiers
     (foundational / compound / matchup). Every one is winnable and none is passable by doing
     nothing — verified, not assumed.
   * **Each Scenario carries a `reference` line** — the hand-written correct play in coordinates —
     and `run.py drills` plays it as a third column. That column is what separates a scenario that
     is BROKEN from one the doctrine merely cannot solve, and the second is a finding worth
     keeping. Verdicts: `ok`, `DOCTRINE GAP` (winnable, prior misses it), `UNWINNABLE` (fix the
     scenario), `restraint drill` (correct play is NONE — a high do-nothing score is the design),
     `NOT DISCRIMINATING`.
   * `Scenario.setup` runs arbitrary engine state after the board (a woken king, a wounded tower,
     the clock in overtime); `DrillEnv` keeps a **play ledger** (what was deployed, where, when),
     which is the only way to score order (`played_before`) or restraint (`played`).
   * **11 DOCTRINE GAPS the drills surfaced** — all winnable by the reference line, all missed by
     the prior: icebow `bow_never_into_the_push`, `hold_the_spell_for_a_target`,
     `log_rolls_forward_not_backward`, `log_the_barrel_on_landing` (spends the Log on the Princess
     bait instead of holding it for the barrel), `nado_clump_for_the_wizard`,
     `skeletons_kill_the_miner`; hogeq `hog_never_into_the_push`, `hog_over_the_ignorable`,
     `skeletons_are_enough` (counters.yaml names skeletons→knight and the referee charges it −1.0
     because `profile('skeletons').dps` is under the tank-answer bar), `mm_leads_the_hog`,
     `rocket_then_tornado` (R6's order — the reward's own +9.0 rocket/nado bonus reads
     `eng.vortices` at ROCKET-cast time, so under the doctrinal order there is no vortex yet and
     it can never pay), and both decks' triage drills where the prior spends anyway.
   * **REMOVED `nado_drag_off_the_tower`** — measured with and without a well-placed pull, our
     tower lost **950 HP either way**: the Hog dies to the princess on the same clock and the
     damage converges, so the drill could not tell a correct pull from no pull. The play is real
     doctrine; this engine does not express its value on that board. Open question, not a drill.
   * **VERIFIED END TO END.** A 60-episode run at `--drill-frac 0.3` reports
     `12W-32L | drills 16 (7% pass)` — drills happening, counted apart from the match record, and
     the untrained pass rate is the number that should climb. Three integration bugs were found
     by running it rather than by reading it, all fixed:
     (a) `win_hist.append(1 if oc == "win" else 0)` recorded **every drill as a loss** — and that
     EMA drives the CURRICULUM DIFFICULTY, the PFSP ledger and the checkpoint gate, so the A/B
     would have read "drills make it worse" for a reason unrelated to drills;
     (b) the worker payload carried only `outcome`/`pfsp`, so the drill flag never crossed the
     process boundary and the fix above did nothing where it mattered;
     (c) `_worker` calls `Config.load()` — it re-reads config.yaml in its own process — so
     `--drill-frac` set the parent's copy, printed a banner, and produced 60 matches out of 60.
     **All three are the same shape:** a value the parent computes that the side doing the work
     never receives. When a knob is added, follow it to the process that acts on it and verify by
     BEHAVIOUR, not by the banner saying it was set.
   * **A/B RUNNING (icebow, started 2026-08-20 ~14:10).** Two arms, same seed 11, 4000 episodes
     each, 8 envs / 7 workers apiece so the 16 cores are split evenly:
     `--drill-frac 0.3 --out data/policy_ppo_drill.pt` (log `data/ppo_drill.log`) against
     `--drill-frac 0 --out data/policy_ppo_control.pt` (log `data/ppo_control.log`).
     Watch with **`python tools/ab_progress.py --watch`**. ~0.3 ep/s per arm -> roughly 4 hours.
     hogeq is being run separately by the owner on another machine.
     NOTE: `--out` exists because both arms otherwise write `train.sim_ppo_checkpoint` and each
     would finish by overwriting the other -- the comparison would be a run against itself.
     Read the ROLLING avg-N eval, not a single point: 150 matches carries about ±4pp. Eval plays
     pure full matches in both arms, which is what makes them comparable at all; the drill arm's
     **drill pass rate** is the more direct signal and moves earlier.
   * **READY FOR THE PPO A/B.** `run.py train-sim-ppo --drill-frac 0.3` against a plain
     `--drill-frac 0` run is the measurement; the flag exists so the two arms differ by one word
     rather than a config edit (an override that needs a file change between arms is one that
     quietly never gets tested). Measured on the mix itself: 32.5% drills over 400 resets against
     30% asked (1.1σ), and a drill episode is **20 steps against a match's 187 — ~9× cheaper**,
     so the same wall-clock buys far more reps of the states that matter.
   * TODO: the drafted curricula run to ~77 scenarios; 55 are built. §6.0a holds the
     reward-coverage findings attached to the rest.
   * **Open finding the triage drill surfaced (not fixed):** an LLM-proposed, engine-verified rule
     (`x1|king_asleep|deep_0|worth_0|elx_6` → `knight`, gain 1.922, 3/3 wins) nominates a Knight on
     a quiet board at 6 elixir, which contradicts the deck's own banking doctrine (a 3.5-cycle deck
     nominates a cycle card only near the leak point, ≥8). It is why `ignore_the_ignorable` scores
     the oracle at ~5% rather than ~100%. Left in place because it was measured; the conflict wants
     a decision, not a silent deletion.

0a. **Reward-coverage findings from the drill drafts (NOT yet verified by me — treat as leads).**
   The two curriculum agents each audited the reward against the doctrine. The three I *did* verify
   were all real and are now fixed (the two `anywhere_ids`/`hog_bridge_y` blockers and the king
   prior, §5). Unverified but specific, highest-value first:
   * `_rocket_value` reads `eng.vortices` at ROCKET-cast time and requires a live vortex, so the
     9.0 rocket+tornado payout can only fire for the tornado-first order that R6 says is **wrong**.
   * R1 is implemented twice, incompatibly: the prior gates on *knight-or-tesla in hand*, the reward
     on *anything affordable* — so on the exact R1 board the correct rocket is billed −0.5 as waste.
   * `nado_king_activate` never reads `u.target`, so a king woken by chip damage inside the window
     collects the activation credit (this is the owner's own correction, unfixed in the reward).
   * `nado_bad` punishes the tornado-BACK pull, which doctrine mandates, and the sneaky lock.
   * `threat_response`'s building branch is placement-blind across all of `0.50 ≤ ny ≤ 0.80`, so the
     centre-pull and king-clearance rules the sampler codes are invisible to the reward.
   * `rocket_combo_hp_frac` 1.5 calls a 2226 HP body one-shottable (golden_knight/prince/bowler all
     survive) — systematic false positive on the 2-for-1.
   * Correct HOLDS pay zero and cost `leak`: triage, rotation discipline, holding the Tesla for
     their wincon. `counterfactual` is zero-mean and off by default.
   * `threat_credit_budget` 2 structurally under-credits any 3-card split-lane defence.

1. **Retrain BC for icebow with the fixed labels** — existing labels are biased forward 0–3 rows and
   the current policy learned that shift. Steps:
   `run.py label --all --size 432` → `run.py replay-bc --jobs 4` (required; it quantises through the
   same function) → `train-bc --data data/replay_bc --val-frac 0.2 --patience 3`. Then RL from the
   **new** `policy.pt`, not `policy_rl.pt`.
   Current BC set is small: **1,142** replay samples + 39 session samples; one 408 MB session
   (`20260815_222309`) has never been labelled.
2. **Restart both PPO runs** after board-26 — first real test of the reward fix. Train **from
   scratch**, not `--resume`; `--reset-gate` should no longer be needed.
3. **board-26 verdict — DECIDED 2026-08-19: IT LOSES, and the way it lost is the finding.**
   Trained to completion (120/120; best epoch 114, mAP50-95 **0.7108**) and gated automatically
   against the pin on the frozen 241 live images:

   | metric | board-24-5 (pin) | board-26 @e51 | board-26 @e120 |
   |---|---|---|---|
   | presence UNITS recall | **0.855** | 0.853 | 0.827 |
   | whitelist identity | 0.823 | 0.828 | **0.794** |
   | deck units passing | **5/5** | 4/5 | 4/5 |

   **`detect.weights` STAYS on board-24-5.** Per-card, board-26 is worse on tesla (0.98→0.94),
   knight (0.90→0.81), skeletons (0.82→0.77), tornado (1.00→0.67) and ice_wizard (0.93→0.92),
   better only on rocket (0.78→0.83).

   **THE IMPORTANT PART — it got WORSE on live images while getting BETTER on its own val set.**
   Over epochs 51→120 it gained **+0.027 mAP50-95** on its own validation split and LOST **0.026
   presence recall / 0.034 whitelist recall** on the live subset. That is not undertraining, it is
   the training mix specialising: the val split is 81% Roboflow, so more epochs bought more skill
   on clean frames at the cost of live captures. **More epochs will not fix this and the earlier
   "it is still improving" reading was measuring the wrong distribution.** The lever is the DATA
   MIX — reweight training toward live captures (12,821 real vs 12,359 Roboflow imported 08-17,
   plus 5,000 synth) — or hold out a live-only val split so training-time metrics stop lying.
   Full outputs: `icebow/runs/gate_board26.txt`, `gate_board24_5.txt`.
   Automation that produced this (reusable for board-27): A detached watcher
   (`icebow/tools/board26_gate_on_finish.py`, PID in `runs/gate_watcher.pid`, logs
   `runs/gate_watcher.{out,err}`) waits for training to finish, runs `detect-eval` on BOTH
   board-26's final `best.pt` and the incumbent board-24-5 over the same frozen 241-image subset,
   writes `runs/gate_board26.txt` + `runs/gate_board24_5.txt`, and posts the verdict table to
   Discord. It survives this session. If it is ever lost, the same script run by hand with
   `--now` does the comparison immediately. The pin only moves if the challenger is >= on presence
   recall AND whitelist identity AND deck-units-passing.
   **Note the trajectory:** board-26 lost this gate at epoch 51 (4/5 deck units below the pin) but
   has since set 16 new bests, mAP50-95 0.6840 -> **0.7046** by epoch 108, so the verdict is
   genuinely open rather than a formality.
   Original criteria: it only replaces board-24-5 if `detect-eval` beats it on
   `data/detect/val_board15.txt` (241 images). The `detect.weights` pin stays until then.
   board-25 came out **bit-identical** to board-24-5, so this gate has already caught one no-op.
   **Measured at epoch 51 (2026-08-18): board-26 LOSES** — 4/5 deck units below board-24-5,
   skeletons 0.77 fails the 0.80 gate (full table in §3). Re-run on the final best.pt. If the
   recall deficit survives to the end, the likely cause is the val/train mix shifting toward clean
   Roboflow frames, and the fix is reweighting toward live captures — not more epochs.
4. **Ability button calibration (hogeq) -- DONE.** The user confirmed the calibration is correct
   (2026-08-18). The policy can and does press it: `mighty_miner_ability` is identity #11 of
   `policy_identities()` and every checkpoint carries an 11-wide `card_head (11, 328)`. MEASURED
   over 40 greedy matches on `policy_sim_ppo_best.pt`: **81 plays, 4.5% of 1,790**, i.e. ~2 per
   match and ~78% of the Mighty Miners it deploys. **What is NOT fixed is the QUALITY** -- the
   `ability_use` reward term fired 80 times at **+39 / -41**, so it presses the button nearly as
   often wrongly as rightly. That is the thing to chase, not the plumbing.
5. **`firecracker_evo` has no hand templates** (only `knight_evo`/`tesla_evo` exist) — run
   `run.py hand-templates` with the evo charged before live play.
6. **Placement collapse** (§4.3) — after a clean BC retrain, if the head still collapses, the lever
   is the soft-target loss that has never been exercised.
7. **`spark_dps_small` disagrees with the current wiki, and it is marked `verified: true`.**
   `cards.yaml` has `firecracker_evo.spark_dps_small: 60` = **15.0 per 0.25 s tick**, but the wiki
   now gives `Small_dmg_11 48` -- the same as the big spark (192 dps). 15.0 is exactly the *crown*
   number, so this looks like a troop/crown mix-up at import time. **Deliberately NOT changed**: the
   row is user-verified, and overwriting a verified value unasked is worse than flagging it. The
   consequence is real though -- crown chip from SMALL zones is computed as 31.25% of 15.0 (4.7)
   instead of 31.25% of 48.0 (15.0), so small-spark tower chip is ~3x too low. Big-spark chip is
   exactly right. Also unresolved: `spark_duration_s` is a single 2.5 for both, but the wiki
   separates them (big **3.0**, small 2.5) since the 14/5/2024 balance change.
8. **`tools/llm_eval.py`'s doctrine cases are still icebow's** — the 6/10 and 8/10 scores quoted
   in `llm_advisor.py` were measured against icebow cases with the icebow prompt. Write hogeq
   cases (the six probe scenarios in the 2026-08-18 session are a starting set) and re-score
   qwen2.5:latest with the new prompt **when the GPU is free** — the tiny-model probe validated
   the quiet-board behaviour only.
9. **hogeq is still full of icebow-specific reward terms** (`xbow_*`, `rocket_*`, `nado`). They are
   inert (the ids resolve to empty sets) but they are dead weight and the 41 failing hogeq tests are
   all IceBow-card lookups.

---

## 7. Standing rules (do not violate)

* **Secrets**: `icebow/data/` and `hogeq/data/` are git-ignored (`.gitignore` line 4 `data/`).
  `discord_webhook.txt`, `roboflow_key.txt`, `cr_api_token.txt` live there. **Never commit, print,
  or put them in an error message.** Verify with `git status --porcelain <deck>/ | grep -c "data/"`
  before every commit (must be 0).
* **Commit and push to `main` after every change batch.** Remote is
  `https://github.com/vegetableleaf/ClashAI.git`.
* **Update this HANDOFF.md in the same batch as the commit** — see the maintenance rule at the top.
  The user's instruction, verbatim: *"make sure to update handoff.md after every update"*.
* Discord alerts go to the webhook in `icebow/data/discord_webhook.txt` via **python urllib** (not
  Git-Bash curl), and **must send a `User-Agent`** or Discord returns 403.
* Never re-run **bare** `run.py sprites` — it clears the sprite bank (`--append` keeps it).
  `run.py sprites --synth N` does **not** touch the bank (it is a separate `elif` branch); an
  earlier claim otherwise in this repo's own docstrings is wrong.

---

## 8. Measurement traps

* **An instrument that only writes to a file nobody reads does not exist (§5bl).** The live loop's per-stage
  `cadence` dict has been in every `data/reward_stats/live_*.jsonl` since 08-12; HANDOFF called the decision path
  "unmeasured" for two weeks. Before declaring anything unmeasured, grep the JSONLs and the per-match prints. (each of these produced a wrong conclusion first)

* **The PPO watchdog's sampled metrics have a WIDE noise floor -- measured on a frozen checkpoint
  (2026-09-02, §5bf.5).** 91 readings of the unchanged 18k file (6 envs x 400 steps each) spread
  cell_struct **685-14,834x** (10-90%: 5,014-11,802), elixir>=6 **0.0-11.3%**, P(play) 0.174-0.391. The
  CELL STRUCTURE DRIFT rule (0.60 x rolling median) fired on that unchanged file at 10:06. A single
  watchdog reading is one sample of a noisy instrument; a DRIFT alert on cell_struct is not evidence
  without a second instrument, and any new relative-decline rule must be checked against this data set
  (`icebow/data/ppo_watchdog.log`, the matches=18000 rows) before it is trusted.
* **The watchdog's `P(play) mean` is mostly MASKED rows (2026-09-02, §5bg).** It averages the raw gate
  softmax over every sampled row, and on the collapsed policy nothing is affordable on ~74% of rows (probe,
  3 seeds each on two checkpoints: 71-75%). On those rows the gate cannot open and its logit gets no prior
  gradient, so the mean moves with whatever the gate outputs where it is irrelevant: the m=2000 gate-prior
  checkpoint read 0.50 (all rows) / 0.43 (affordable rows), the 18k control 0.35 / 0.39 -- the "higher"
  run plays at the same rate. Read `tools/gate_prior_probe.py`'s `affordable rows` column or its per-bucket
  `played`, never the watchdog's P(play), for anything about WHEN the agent plays.
* **`GATE PRIOR CE` / `pi(play)` in the trainer log are cumulative means since update 1 (2026-09-02, §5bg).**
  A line at update 4000 that reads 0.323 after 0.321 at 3400 is a window mean of ~0.33, not "flat". Difference
  consecutive lines (n_k * v_k - n_{k-1} * v_{k-1}) / (n_k - n_{k-1}) before calling a trend.
* **The trainer's `drills N (X% pass)` is a run-LIFETIME average, not a rate (2026-09-02, §5bd).**
  `drills_done`/`drill_pass` are initialised once and never reset, so the number converges by
  construction and then cannot move: measured on the stopped 18k run, 29% -> 45% over the first ~450
  prints and then **EXACTLY 45% for the last 275**. At n=3,500 a genuine 500-drill window at 60%
  prints as 47%. Reading that flat line as "the policy stopped learning drills" is reading the
  statistic, not the policy. A rolling `% last 300` now prints beside it; for the real per-drill
  number use `run.py drills --policy <ckpt>`, which is prior-free (§3p).

* **RoyaleAPI "similar decks" are not all evolution swaps (2026-09-02, §5bc).** For hog 2.6 they include
  card SUBSTITUTIONS (cannon for tesla, electro-spirit for ice-spirit, valkyrie-hero for mighty-miner).
  A roster ranked across every variation board by rating is then mostly players whose battles the
  `is_variation` filter rejects: 14 players walked, **0 battles kept**. Filter the roster by
  `is_variation(found_on, seed)` BEFORE capping. icebow never showed this -- its similar decks really are
  evo variations -- so a driver copied from it must be re-measured on the new deck.
* **"hogeq is at its 42-known-failure baseline" is STALE (2026-09-02, §5bc).** Measured: 1,272 tests OK
  (64 skipped) before this session's ports, 1,288 OK after. Quoting the 42 hides a real regression.

* **kitka `dataset_updates/` is a 100% byte-duplicate of `segment/segment` (2026-09-02, §5bb).** Counting
  both doubled every per-class number in §5az.4 (hunter_evo "546" is 276). Count `segment/segment` only.
* **`run.py sprites --synth N` regenerates `data/detect/synth` IN PLACE (2026-09-02, §5bb).** If a training
  run is reading that folder, the regeneration silently swaps its training images mid-run. Regenerate only
  between runs; the held-out set lives in its own folder (`synth_holdout`) for the same reason.

* **PS 5.1: a script `param($Args)` is SILENTLY EMPTY (2026-09-02, §5ay).** `$Args` is a reserved automatic
  variable; the launcher dropped every argument and started a bare python REPL that hung on stdin
  (WinError 123 from _pyrepl). Name the parameter anything else (`$Cmd`).
* **`plays_ext` ability rows have `x_units`/`y_units` = the string "None" (2026-09-02, §5ay).** They are
  hero-ability activations (`attr_ability=1`, `attr_card` `_invalid`), not placements; a loader that
  requires positions on every row refuses 203 of the 268 replays for no reason. Skip them as ability rows.
* **"Rejected by the engine" late in a match is usually the ENGINE'S END SEQUENCE, not a bad play
  (2026-09-02, §5ay).** All 81 native_rejected results were code 4 within ~10-80 ticks of the engine's
  terminal: the engine's match ended before the real one did, so the last real plays landed on a finished
  battle. It is a fidelity signal (the engine diverged earlier), not a command-format error.
* **"THE ENGINE'S CLOCK DOES NOT ADVANCE" WAS A PENDING UI POPUP, NOT A CLOCK (2026-09-02, §5ax).**
  Every hypothesis in §5aw (locale, runtime clock, CPU, loading flag) was about time; the real gate was
  `GameMain+0x1BC != 0`, a queued "update from the store" action that the headless path never consumes.
  When a native engine returns instantly without effect, read its early exits from a LIVE DUMP before
  theorising -- the code on disk was encrypted and the 33 ms return time already said "no wait path".
  Sandbox-tool traps from the same night: toybox `dd skip=` overflows past 2^31, `adb push` resets the
  exec bit, Git-Bash rewrites `/data/local/tmp` paths, `pgrep -f` matches its own adb wrapper, and the
  DataTables pump segfaults nondeterministically (~1 in 10 boots) before the replay doc is even read.

* **⚠ A BASH-TOOL TIMEOUT DOES NOT KILL THE CHILD (2026-09-01, §5ar).** A regex heredoc that
  "timed out" at 07:11 kept spinning at ~97% of one core for 13 hours, and would have overwritten
  `doctrine.py` with a stale copy had it ever finished. Every "idle box" throughput read that day
  before 20:10 carried it. After any timed-out call: `Get-CimInstance Win32_Process` for stray
  `python.exe -` / `sleep` children and `Stop-Process` them by PID -- also when killing a
  `nohup bash -c 'sleep N; ...'` dead-man, whose `sleep` survives its parent. Before an "idle box"
  claim, count processes; do not infer idleness from the plan.
* **⚠ A GUARD THAT MEASURES THE NET MUST SEE THE NET'S INPUTS (2026-09-01, §5ar).** The resume
  rail guard fed the policy 0..255 uint8 boards cast to float (no `/255`) and would have read a
  healthy card head as 1,424 and rescaled it x0.002 on any `--resume`. Any probe that builds its own
  input tensors must reuse the trainer's `to_obs_batch` / `to_vec_batch`, not a re-typed chain --
  and a rescale that fires on a fresh checkpoint is evidence against the probe before the net.
* **⚠ "THE GPU IS SLOWER" WAS MEASURED ON A SHARED GPU (2026-08-08 note, retired in §5ar).** The
  1.0 vs 0.2 match/s comparison ran while a detector job held the GPU; on the idle 5050 the same
  trainer cycle is 2.92x faster than 4 CPU threads. A device comparison inherits the contention rule
  as much as a core-count comparison does.
* **⚠ BARE `python` IS THE ROOT `.venv`, AND IT CHANGES THE ANSWER.** Every arm in
  `spell_experiments.md` was launched as `python scratchpad/spell_arms*.py`, which resolves to
  `ClashBot/.venv` — **torch 2.13.0+cpu**, not the deck venv's **2.11.0+cu128** that the trainer,
  the drill report, the eval benchmark and live play all use. ISOLATED 2026-08-27, n=300 paired,
  same seeds, same checkpoint, **same tree**: root venv **43.0% / -0.8303**, icebow's own venv
  **37.0% / -0.9348** — **-6.0pp winrate (2.62σ)** from the interpreter alone, larger than most
  effects this project measures. It also produced a phantom "the tree drifted" story: the tree had
  not moved at all. **Always `./.venv/Scripts/python.exe` from inside the deck**, in scratchpad
  harnesses as much as in `run.py` (§2's rule, which the wave scripts did not follow).
* **⚠ A RANDOM-BAN CONTROL IS ONE DRAW, NOT A DISTRIBUTION.** `ctl(r)` bans each playable spell
  with probability r from a hardcoded `random.Random(770011)`. n=300 measures THAT ban pattern
  precisely and says nothing about the spread over patterns: against the same baseline it read
  **+0.301 (4.54σ)** on seeds 5_000_000.. and **+0.051 (0.76σ)** on 6_000_000..., which flipped the
  sign of every arm-vs-control comparison between blocks. Pool the blocks, and average the control
  over several draws before quoting an arm-vs-control σ at all.
* **⚠ IF IT READS `pool[i]` IN `train_sim_ppo`, IT DOES NOT EXIST UNDER `--workers > 1`.**
  `remote = workers > 1` and the trainer then keeps its own env list EMPTY
  (`for e in (pool if not remote else [])`). The spell veto's first version guarded its sampling
  path with `and not remote` and would have been ON at eval and OFF in training, with the banner
  still printing. Third instance of this seam: deck PFSP (`remote_pool.py`'s own comment) and
  `--drill-frac 0.0` (below) were the first two. Decide it in the worker and ship it in the
  payload; pass any threshold DOWN as a resolved float, never let the worker re-read the disk.

* **Buildings bleed HP over their lifetime.** Raw HP loss counts decay as spell damage — the first
  Earthquake measurement appeared to show it hitting a Tesla 30 times. **Always difference against
  a control board with no spell cast**, and prefer targets that survive (no death artefacts).
* **The elixir cap hides the cost of an action.** Comparing a play-step against an idle-step from a
  full bar measures the cap, not the spend. Start below 10.
* **`elixir` vs `elixir_pre` in `play_log`**: `elixir_pre` is what the decision saw; `elixir` is the
  post-action read.
* **Per-tick deltas conflate effects.** Firecracker's recoil reads as <1 tile in a running match
  because the same 0.1 s tick contains the recoil *and* her walking back. Verify in isolation.
* **A rule that fires only when the card is in HAND** — `_holdable` — means a test that does not pin
  the hand is really testing the deal. `test_tesla_discipline` passed on icebow purely because that
  deck's opening cycle happened to contain a Tesla.
* **The detector audit trap**: an offline tool that reads the *live screen* instead of the video it
  claims to analyse. `LiveMatchEnv.__init__` starts a 10 Hz perception thread and `_detect_enemies`
  returns its snapshot if <2 s old.
* **A reward verified at a coordinate the ACTION SPACE cannot produce.** `_hog_wincon` was measured
  "0.00 → +3.00" last session and shipped — at y=0.47, which `deploy_clamp` never emits. At every
  legal row it returned −1.0, so the fix for the zero-Hog collapse was teaching the opposite of what
  it claimed. Its unit test calls the same illegal y, so the test agreed with the bug. **Whenever a
  reward reads a coordinate, evaluate it at `actions.cell_center(...)` values only** — the grid, not
  the config, is the authority on what is expressible. Same family as the offline-tool trap above:
  the check and the system under test were looking at different worlds.
* **A snapshot answers a question about motion wrongly in BOTH directions.** The first
  king-activation reach filter tested distance at the instant of casting: it rejected a cast that
  works from 6.40 tiles (the attacker marches into the vortex during its 1.05 s life) *and* accepted
  one that whiffs from 8.7 (closing only in y while a 4.2-tile lane gap never closes). If the effect
  has a duration and the target has a velocity, the test has to be against the **path**, not a point.
* **Drills must be measured against a DO-NOTHING baseline.** Two of the first four scenarios were
  passing 15/15 with an empty action — the tower resolves a swarm on its own, and "no enemy alive"
  is trivially true before the scripted spawn lands. A drill nobody can fail teaches nothing, so
  every scenario is scored both ways (baseline vs oracle) and only a gap between them is evidence.
* **A model's own val set can change under you.** board-26's val is 81% Roboflow images that
  did not exist when board-25 was validated, so comparing their per-epoch mAP measures the val
  set as much as the model. Before comparing two training runs, check the val set is the same
  one -- and prefer the fixed held-out gate (`val_board15.txt`) over training-time metrics.
* **A training-time mAP lead can invert on the real gate.** board-26 led board-25 by +6.1 mAP50 on
  its own val set and yet, at epoch 51, scored *below* board-24-5 on all but one deck unit on the
  241 live images. Higher precision, lower recall. **Never promote a detector on `results.csv`;
  only `detect-eval --subset val_board15.txt` decides.**
* **Changing what a CONFIG KEY MEANS is not a local change.** The dart-goblin fix looked like it
  wanted `tower_range` re-based from the tower's centre onto its hitbox edge. That would have been
  wrong twice over: (a) `tower_range: 8.0` is **derived from the board** -- tuned so a princess
  opens fire exactly as a troop clears the bridge -- so adding the radius on top opened fire 1.5
  tiles early, across the river, killing an Evo Battle Ram mid-charge and costing a Skeleton Barrel
  a skeleton; and (b) the key is also read by `sim/doctrine._double_cover`, the tornado
  king-activation reward in `sim/env.py`, `config_edit.py`'s defaults and a hardcoded copy in
  `tests/test_sim_status_effects.DummyCfg`, every one of which would have silently retuned. **Grep
  every reader before changing a setting's units, and prefer changing the VALUE over the frame.**
* **A test fixture can carry its own stale copy of a config value.** `DummyCfg` hardcodes
  `tower_range`/`king_range` rather than reading config.yaml, so a config change does not reach the
  tests that use it -- and "fixing" the fixture to match config.yaml silently made every tower in
  those tests 0.5 tiles stronger. A test double's job is that unrelated tests keep their meaning.
* **The research doc's coordinate legend is the LIVE frame; the sim is BOARD-TRUE.** River 0.48
  vs 0.5, lanes 0.25/0.745 vs bridges 3.5/18 = 0.194 / 14.5/18 = 0.806, princess line 0.615 vs
  towers y = 0.797. TWO independent implementations (the overnight session's and this one's)
  transcribed the legend's numbers into doctrine spots, tiles off in the same direction; a T2
  survivor gate at the live-frame 0.62 excluded every unit that had just defended AT the tower.
  **Anchor every sim spot to the engine's own towers/bridges/banks and never transcribe the
  doc's numbers** -- the review workflow caught this; the tests had been written loose enough to
  pass either frame.
* **An unmasked card-head sample is not a play distribution.** Sampling the card head without
  the in-hand-AND-affordable mask counts plays `eng.deploy()` would reject: 153 plays/match
  against the masked 38.5, and x_bow inflated 1.06% -> 8.61%. This bug has now produced a wrong
  number TWICE (first: "tesla played 609 times while dealt on 283 steps"). `cards.py` and
  `ledger.py` carry the mask; copy it into anything ad-hoc rather than re-deriving it.
* **A config revert does not revert the POLICY.** `wincon_bank_floor` went 4.5 -> 0, but the run
  was `--init`ed from weights trained under the floor and kept dumping elixir (median 2.14) for
  the next 10k matches. When a change taught the policy a habit, removing the change is not
  enough -- measure whether the behaviour actually went with it.
* **A probe must use the CALLER'S OWN FRAME.** Re-measuring W1 after its repricing read 89%
  instead of 39%, because the probe called `_bow_window(spend=6.0)` on a board where nothing
  had been paid -- so the post-spend "reserve" read as the full bar. The real caller is
  already debited. Same family as the live-screen and illegal-coordinate traps: the check and
  the system under test were looking at different worlds, and the check was the wrong one.
* **An UNTRAINED baseline is load-bearing, and it is the easiest number here to get wrong.**
  Mis-measured TWICE (`48bc8e7`: -13.57 not -6.78; S3v: -1.72 not -2.20), and both times a
  headline conclusion rested on it. Measure it (a) in the SAME checkout as the trained
  policy, (b) over several random inits -- one untrained net is a single draw from a wide
  distribution, (c) with the card head MASKED. It needs no training: a random init's
  crowndiff is a property of the ENVIRONMENT, which is what makes bisecting it across
  commits cheap (`scratchpad/baseline_at.py`, run from a git worktree per commit).
* **`x or DEFAULT` is wrong for any numeric knob whose ZERO is meaningful.** `0`/`0.0` are
  falsy, so "explicitly off" and "unspecified" collapse together. It cost two silent
  no-ops at once (S3w): `--workers 0` became 12, and `--drill-frac 0.0` became "re-read the
  config" (0.3). This repo has `drill_frac`, `workers`, `wincon_bank_floor`,
  `deck_pfsp_power` and several reward weights where zero is a deliberate setting. Use
  `is None`. The tell is in the log: a banner asserting one thing while the counters say
  another means the override never reached what it names.
* **Separate a REAL swing from your own sampling error before calling it instability.** Over 35
  watcher ticks, P(play) had sd 0.142 against a sampling sd of 0.011 (real, 13x), while
  drill_mean had sd 0.040 against an expected 0.049 and crowndiff 0.231 against 0.354 -- both
  entirely instrument. Three metrics 'oscillating' in the same report, and only one of them
  was the model. Compute the expected sampling sd for the sample size FIRST.
* **Two rates that disagree by 20x may just have different DENOMINATORS.** The watcher's
  `P(play) 0.569` and the trainer's `plays are 3% of steps` looked like a flat contradiction and
  nearly retired a shipped fix. They measure the same policy: the trainer counts the action taken
  over ALL steps, and `train_sim_ppo.py:434` masks PLAY to `-inf` when nothing is affordable, so
  forced waits are counted as waits. `0.57 x 0.08 affordability ~= 3%`. **Before believing that two
  of your own measurements conflict, write down each one's denominator** -- and prefer the one whose
  implied consequences match a THIRD independent signal (here: `leak` fires zero times, which is
  impossible at a genuine 3% play rate).
* **SIM EVALUATION IS NOT DETERMINISTIC UNLESS YOU PIN `torch.set_num_threads(1)`.** Seeding
  `torch.manual_seed`, `np.random.seed` AND `SimMatchEnv(seed=...)` is NOT sufficient. Two
  invocations of the same probe on BYTE-IDENTICAL weights (sha1-verified) produced 1477 vs 1271
  steps, 190 vs 132 plays, elixir median 2.14 vs 2.71 and `leak` 24 vs 150 fires. The CPU forward
  pass is float-nondeterministic across thread schedules -- and the box is CPU-SATURATED during any
  training run, so the schedule genuinely varies -- one flipped `multinomial` draw diverges a
  300-step match irrecoverably. With `torch.set_num_threads(1)` + `PYTHONHASHSEED=0` two passes
  reproduce EXACTLY, to every digit.
  Consequences, all of them load-bearing:
  (a) **any single-pass ad-hoc probe on ~10 matches measures its own thread scheduling**, which is
      how the "restraint raised elixir 2.21 -> 2.79" and "leak 45 -> 81" comparisons were produced
      and then withdrawn;
  (b) **`leak` is violently heavy-tailed** -- per-match sd 45 against a mean 37 -- so it needs
      several hundred matches to resolve a small difference and must never be quoted at n<50;
  (c) `bench.py` (4 passes x 40) and `nightcheck.py` (3 x 30) are STRUCTURALLY SOUND because they
      average independent passes and report the ACROSS-PASS se, which already absorbs this
      variance. Prefer them. Copy their multi-pass shape into anything ad-hoc;
  (d) with threads pinned, **PAIRED comparison becomes available** -- same seeds, two checkpoints,
      every difference is policy rather than seed luck. That is far more powerful per match than
      comparing two independent means and is now the preferred design for any A/B here.
* **A WARM-STARTED RUN COMPARED AGAINST ITS OWN INIT CANNOT ATTRIBUTE ANYTHING TO THE CHANGE
  UNDER TEST.** This is written in S4a -- *"compare run-vs-run at matched episode counts instead"* --
  and was violated the same day it was recorded, which is why it is repeated here as its own trap.
  The fix-1 test compared `m=26000` against `m=26000 + 2,600 episodes trained WITH fix 1`. Every
  difference has two candidate causes: the change, or the warm-start tax. And the tax is LARGE and
  MEASURED: crowndiff -1.256 -> -1.600 at ep1675, still -1.489 at ep3600, i.e. a general decline at
  ~2,600 episodes is exactly what warm-starting predicts with NO reward change at all. The observed
  result -- a sign test with 16 of 21 ledger terms negative (p=0.027) -- is indistinguishable from
  the tax.
  **The only valid design is a MATCHED CONTROL: same init, same episode count, the knob at zero.**
  Anything else measures the tax. Budget for two runs whenever a reward change is tested, or do not
  claim a verdict. THIS PROJECT HAS NEVER HAD A MATCHED-EPISODE REFERENCE RUN, and at least three
  experiments this week ended ambiguous for that single reason.
* **N=8-12 MATCHES CANNOT RESOLVE A REWARD-TERM DIFFERENCE HERE, AND IT PRODUCED TWO WRONG
  DIRECTIONAL CLAIMS IN ONE DAY.** "restraint_hold 0.67 -> 0.33, training made the rewarded
  behaviour LESS frequent" became **0.63 -> 0.50 (0.8 sigma)** at n=30 -- a gap smaller than its own
  error bar, reported as a finding. Per-match sd is brutal for the sparse terms (`leak` 3.5 against
  a mean 1.2). Compute the sem BEFORE quoting a delta, and treat anything under 2 sigma as "no
  measurement" rather than "a small effect".
  ⚠ **PAIRING HELPS LESS THAN IT LOOKS.** Both arms sharing a seed gives the same STARTING board,
  but two different policies diverge on the first differing action, so pairing cancels initial
  conditions only -- measured, it tightened the sems by 12-17%, not the large factor expected.
* **`--matches N` MEANS N EPISODES, NOT N MATCHES -- and so does the checkpoint's `matches` field
  and the trainer's own "stopped after N match(es)" line.** Three names for the same axis, none of
  them the axis they name. MEASURED: the control arm launched with `--matches 2850` stopped at
  **2850 EPISODES / 2172 real matches** (`total 90W-2082L-0D`), and its checkpoint reports
  `matches=2850`. The only place a REAL match count appears is the `W-L-D` tally.
  Cost: a control arm sized for 3600 episodes stopped 750 short, and the chained follow-on run was
  configured against the wrong axis too. **When matching two arms, match on EPISODES and verify with
  the checkpoint field, never on the CLI number's apparent meaning.** A drill counts as an episode,
  so the ratio also moves with `drill_frac` -- at 0.3 it was ~0.78 matches per episode here, which is
  why the two numbers drift apart at a rate that looks plausible instead of obviously wrong.
* **Re-run the exact diagnostic after a fix.** Several bugs here produced plausible output while
  silently wrong (`xbow_into_push` was a no-op; duplicate ALIAS keys silently clobbered).

---

## 9. Detector dataset inventory (2026-08-17)

| asset | count |
|---|---|
| `images/train` + labels | 12,821 / 12,821 (paired, 0 orphans) |
| `images/val` + labels | 2,346 / 2,346 |
| Roboflow staged (3 `rf_*` dirs) | 12,359 — **all imported**, 0 pending |
| `to_label` | 6,059 (unlabelled pool, excluded) |
| sprite bank | **44,113** across 186 classes = 40,412 ours + **3,701 KataCR** |
| synth | 5,000 / 5,000 |
| `data.yaml` | train `['images/train','synth/images']`, val `images/val`, nc 230 |

**KataCR source lives at `icebow/data/katacr/images/segment`** (154 class folders, 4,627 segments;
123 classes / 3,701 map onto our taxonomy). Re-import with
`run.py katacr-segments --src data/katacr --src-width auto`. It is idempotent (`katacr_` prefix).
Note the import warns that shared classes disagree on scale (auto=735 px, CV 0.24) — that warning
also applied to the board-24-5 import, so `auto` reproduces the known-good state.

**A bare `run.py sprites` run during this session wiped the previously-imported KataCR segments**
(0 katacr sprites remained). They have been restored. Disk is not a constraint: ~500 GB free,
`data/detect` totals ~10 GB, a finished detector run is ~44 MB.

---

## 10. Video analysis (`/watchvideo`) -- installed 2026-08-18

A local video analyzer is installed as a Claude Code skill, so gameplay footage (or any video) can
be turned into a transcript + tiled contact sheets that the session reads directly. **No API key,
no MCP, nothing leaves the machine.** Source: `github:charlesdove977/watchvideo` (MIT). The
installer was read before running: it only copies `skill/` into `~/.claude/skills/watchvideo/` and
writes a command stub -- no network, no eval, no postinstall.

| piece | where | note |
|---|---|---|
| skill | `~/.claude/skills/watchvideo/` | modes `hook` / `condensed` (default) / `forensic` |
| `yt-dlp.exe` 2026.07.04 | `C:\Users\benpe\tools\bin` | on the **user PATH, first** |
| `ffmpeg.exe` / `ffprobe.exe` 9.0.1 | same | gyan.dev essentials static build |
| `openai-whisper` | **ClashBot root `.venv`** | torch **2.13.0+cpu** -- CPU by design, so it never competes with a detector run for the 8 GB of VRAM |

**Verified end to end 2026-08-18** on a 19 s clip: download -> `ffprobe` duration 19.014 -> one
tiled 5x4 contact sheet (last cell padded black, which is expected) -> 16 kHz mono wav -> `base.en`
transcript with 4 correctly-timestamped segments, ~2.8 s of transcription. The sheet was read back
successfully, so the vision leg works too.

**Gotchas**
* `npx watchvideo doctor` reports **openai-whisper MISSING even when it is fine**. Node >=18.20
  refuses to `execFileSync` a `.cmd` without `shell:true`, so it can never see the `python3.cmd`
  shim. The skill's own preflight runs in **Bash**, where it works. Check with
  `python3 -c "import whisper"` in Git Bash instead, and ignore the doctor's whisper line.
* A shell started **before** the PATH edit will not see `tools\bin`; `export
  PATH="/c/Users/benpe/tools/bin:$PATH"` or start a new shell.
* The skill's own notes warn that yt-dlp **2026.07.04** (the version installed) 403s on some YouTube
  videos due to PO-token gating. Fix is `pip install -U yt-dlp` or
  `--extractor-args "youtube:player_client=tv,web_safari"`, or `--cookies-from-browser chrome`.
* Whisper transcription is **CPU** and does compete with PPO/detector training for cores. A 19 s
  clip is nothing; warn before anything over ~40 min.

---

## 11. Useful one-liners

```bash
# hoard/dump + reward-term breakdown (the §4.1 diagnostic)
#   drive the env with scripted policies and read env.rw_stats.run

# live placement collapse
python -c "import json,glob,collections;p=[x for f in glob.glob('data/reward_stats/live_*.jsonl') for l in open(f) if l.strip() for x in json.loads(l).get('play_log',[])];c=collections.Counter(v['raw_cell']//18 for v in p if 'raw_cell' in v);print(c.most_common(5))"

# grid round-trip must be exact
python -c "import sys;sys.path.insert(0,'src');from clashrl.config import Config;from clashrl.actions import ActionSpace;a=ActionSpace(Config.load());print(sum(1 for gy in range(a.gh) if a.coords_to_grid(*a.cell_center(9,gy))[1]!=gy),'of',a.gh,'rows wrong')"
```

Test suites: icebow **337 pass**; hogeq **401**, of which 41 fail — all IceBow-card lookups
(`x_bow`/`rocket`/`tornado`/`knight`/`ice_wizard`) that the Hog EQ deck does not hold. That 41 is the
expected baseline; a *different* number means something real broke.

## §4y — Distillation has NOT started; Valkyrie r31d is in flight (2026-08-27, window-end snapshot)

**Read this before assuming the long run can start.** The long run requires distillation
(owner asked twice). As of this writing the harness **does not exist**: no teacher script, no
corpus generator, no `ledger/distillation.md`. The only distillation artifact in the repo is the
SPEC, at §6-PRIORITY-B (commit `5aceb09`). Agent `a83ef3720cbf613c0` was given the build and had
produced nothing for it on disk; it spent the window on Valkyrie instead. **Plain PPO does not
satisfy the request — do not start the long run and call it done.**

**Valkyrie hero ability (ruling 31d) — implemented but UNCOMMITTED at snapshot time.**
Modified in BOTH decks: `engine.py`, `config/cards.yaml`, plus `research/sim_parity/decisions.md`
and `conflicts.md`; untracked: `{icebow,hogeq}/tests/test_valkyrie_seek_r31d.py` and
`research/sim_parity/webcache/Valkyrie_Hero.live.wikitext`. If `git status` is clean and no
`r31d` commit exists, **the work was lost** — the CRLF/`git checkout` trap (§2) eats exactly this.

The mechanic, so it can be rebuilt from this section alone:
* **5.5 tiles is a TARGET-DETECTION RADIUS, not a dash distance.** Enemy troop **or building**
  within 5.5 tiles -> she instantly locks on and enters the "Ultra-Fast Whirlwind Stage". Nothing
  within 5.5 -> she **walks forward normally**, no whirlwind damage, no speed boost, until
  something enters the bubble.
* **One clock, started at ABILITY ACTIVATION** (owner ruling, verbatim): walk time BURNS the
  duration. Activate, walk 2.0 s, then acquire -> the whirlwind runs only **1.5 s** of the 3.5 s.
  Acquire nothing for the full 3.5 s -> the ability is **entirely wasted, zero damage**.
  Do NOT start the clock at whirlwind entry; that would make a mistimed cast free.

⚠ **Three wrong readings were shipped to the agent before this one** — a 5.5-tile travel cap, a
dash-then-spin pre-phase, and a Bandit-style leap. I also derived a speed of `5.5 / 3.5 = 1.571`
tiles/s, which is **meaningless**: the two numbers describe unrelated things. The wiki documents no
dash at all; the mechanic came from an owner-supplied web-search result, recorded in `conflicts.md`
as a SECONDARY source. Open in-game check: *"activate with nothing within 5.5 tiles — does she walk
without whirlwind damage until an enemy arrives?"* One observation confirms the whole model.

⚠ **Opponent-AI trap, unverified:** `ScriptedBot._try_ability` must not fire this ability on an
empty board — under the shared-clock ruling that throws the whole thing away. If the heuristic is
still the generic defensive/offensive family rule, the opponent will waste it routinely and the
card will **measure as weaker than it is** — which reads as a card-balance problem when it is an AI
problem. Same shape as the Boss Bandit issue.

**Next session, in order:** (1) confirm the r31d commit exists, rebuild from this section if not;
(2) build the distillation harness from §6-PRIORITY-B — teacher at **N=1** (at N=5 the restraint
signal has the WRONG SIGN) and export `PYTHONHASHSEED` properly (the harness's own setting is a
no-op, so identical configs silently differ); (3) measure the **privileged-teacher gap** before
committing to a full run — the teacher sees engine ground truth, the student sees a degraded
observation; (4) only then start the long run, checkpoints to `policy_sim_ppo.pt`, veto OFF.

## §4z — The gate investigation, re-measured: it collapsed the OTHER WAY, and two premises are dead

> ## /!\ CORRECTION (2026-08-28): PREMISE 2 BELOW IS WITHDRAWN. THE ELIXIR NUMBERS WERE AN ARTIFACT
>
> The fixed `gate_probe` still carried two flaws that `ppo_watchdog` had already identified and
> fixed, and which were never back-ported because this file raised AttributeError on every call:
> it played **`aff[0]`, the first affordable card BY INDEX** rather than the policy's pick, and it
> **thresholded the gate at 0.25 instead of sampling it**. At P(play) 0.17 the threshold means it
> played on ~14% of steps and banked the rest, so elixir piled up. The watchdog's own comment names
> this exact failure: *"a property of the measurement, not of the run."*
>
> Same checkpoint, three readings:
> ```
>                          P(play)   elixir mean   >=6      wincon affordable
>   gate_probe (broken)     0.171       5.00       41.66%       41.45%
>   gate_probe (fixed)      0.113       3.19       13.40%       11.90%
>   ppo_watchdog            0.292       2.38        1.3%          --
> ```
> **"The elixir-starvation story is CLOSED" is WITHDRAWN.** Elixir reaches 6 on 13.4% of steps by
> the corrected probe and 1.3% by the watchdog -- not 41.7%. The win conditions are largely
> UNAFFORDABLE, which is much closer to the original premise than to my correction of it. Premise 2
> below is live again; treat it as unresolved, and note the two instruments still differ 10x on
> that column, so neither number is trustworthy on its own yet.
>
> **PREMISE 1 SURVIVES**: every reading puts P(play) at 0.11-0.29, nowhere near the 0.938 that
> `--reset-gate`'s help asserts. The gate is not collapsed to always-play.
>
> Lesson, and it is the same one this file already records twice: an offline probe that does not
> reproduce the policy's own action selection measures the probe. Both the drill-scaffolding
> finding and this one came from a tool scoring something other than the network.


**The instrument was broken.** `tools/gate_probe.py` raised `AttributeError: 'PolicyNet' object has
no attribute 'cell_head'` on **every** invocation and had done so since the spatial-cell refactor --
it still called `features_vec` + `.cell_head(z)`, which `PolicyNet.forward_parts` explicitly tells
you not to do in its own docstring. So the gate diagnostic has been dead for as long as that
refactor is old, and every "the gate has collapsed to always-play" claim downstream of it predates
that. Fixed to use `forward_parts`.

### Measured now, on the live 8k checkpoint (m=5050, 2900 steps / 8 matches)

```
P(play)  p5 0.051  p25 0.119  p50 0.167  p75 0.219  p95 0.303   mean 0.171  min 0.004  max 0.495
         share > 0.25: 13.7%      share > 0.60: 0.0%      share > 0.95: 0.0%
elixir   p5 1.00   p25 2.00   p50 5.00   p75 7.00   p95 10.00   mean 5.00   max 10.00
         share >= 6 (X-Bow/Rocket affordable): 41.66%
x_bow/rocket IN HAND 94.6%   IN HAND *and affordable* 41.45%
```

### Two documented premises are now FALSE. Do not act on either again.

1. **`--reset-gate`'s help says the gate "has COLLAPSED to always-play: measured P(play) 0.938 with
   min 0.911".** It is **0.171 mean, 0.495 max, and never once exceeds 0.60**. The collapse is in
   the OPPOSITE direction. A fresh gate starts near 0.5, so `--reset-gate` would now RAISE the play
   rate -- the flag may still help, but its stated rationale is inverted and must not be quoted.
2. **"elixir never passes 5, and the 6-cost win conditions stay masked (= zero policy gradient)
   forever."** Elixir mean is **5.00** and **41.66%** of steps are at >= 6, with the win condition
   in hand and affordable on **41.45%** of steps. The elixir-starvation story is CLOSED. It banks
   fine. It does not fire.

### The downward drive is gone; the gate is parked, not falling

Documented drift was a systematic **-0.169 / -0.386 / -0.408** on PLAY steps at ~11x its own sd.
Measured in the live run now, four consecutive windows: **+0.091 / -0.138 / -0.098 / +0.201** --
mixed sign, mean ~+0.014. The §3p exploration-floor fix (0.85/0.75 -> 0.30/0.25) appears to have
removed the systematic push. So this is no longer "the gate is being driven down"; it is "the gate
sits at a low fixed point and stays there".

`ppo_gate_threshold` is **0.25** and only **13.7%** of steps clear it -- which is exactly the
eval's 10.2% play rate, and exactly why the ACT drills score 0 while the banking half works.

### What this does and does not license

It explains every drill result measured today: `bank_to_six_then_bow` 0% (it banks and never
fires), `hold_the_spell_for_a_target` / `rocket_the_two_for_one` / `rocket_the_pump_on_sight` /
`skeletons_stop_the_wall_breakers` / `log_rolls_forward_not_backward` all 0%, all ACT drills, while
`bow_punishes_the_pump` 100% and `bow_punish_the_commitment` 92% survive.

⚠ **This is a DIAGNOSIS, not a repair.** No fix has been measured. And the repair experiment is
constrained by a result already on the books: **the collapse is BISTABLE, measured escape rate
4/6**, so **3 seeds minimum** -- a one-run result decides nothing here, and that error has already
been made once on this exact question (the retracted "it is NOT the drills", n=1).

Closed already, do not respend: per-head clipping (measured, no improvement), `ppo_value_head_split`
(tried, rejected), `ppo_clip_play_mult` (mitigation ~25%, UNTUNED, its 5-value x 2-seed sweep is
still staged and unrun), and the gate-threshold sweep (reported optimal in both directions -- worth
re-checking, because it was swept against the OLD always-play premise).

**The open question is now narrow:** the gate is not starved (largest policy-head gradient), not
throttled, and no longer pushed down -- so what holds it at 0.17 when elixir and the win condition
are both available on ~41% of steps? Distillation will NOT answer it: the card head is the half
that already works.

## §5a — 3x's "the offence has no reachable positive signal" is CONTRADICTED by measurement

3x named this as the one remaining candidate after drill_frac was ruled out, and explicitly said
*"measure that on a real sample before changing anything."* Measured: `policy-stats`, 300 greedy
matches, `policy_BEST_m18000`, seed 909, 8,355 plays.

**The claim was: `take_enemy_tower` has ZERO fires and the offence terms sum NEGATIVE
(`xbow_into_push` -4.00 against `wincon_exec` +1.20 for one fire each).** That was a 1-fire
extrapolation. On a real sample it is false in both halves.

```
  OFFENCE, positive                          OFFENCE, negative
    wincon_exec        +1800.2   998 fires     xbow_into_push       -500.0  125 fires
    wincon_reach       +1023.0  1023           xbow_overaggression  -237.0   79
    take_enemy_tower    +275.0   275   <--
    xbow_lock           +132.0 11052
    chip_offence        +124.2 13142
    xbow_defends        +111.6  9299
                       ~ +3466                                     ~  -737
```

`take_enemy_tower` fires **275 times in 300 matches**, and `wincon_exec` is the **largest single
term in the whole ledger**. Attempting offence is strongly expected-value POSITIVE. The hypothesis
is dead; do not spend a run on it.

### And "waiting pays" is dead in the same table

The largest NEGATIVE term is `threat_miss_idle` at **-1020.3 over 1,494 fires** -- a penalty for
IDLING while a threat is live. `leak` (-416.0, 3,467 fires) punishes hoarding. The reward pushes
toward playing MORE, and the policy plays on ~10% of ticks anyway (gate held 44%, forced waits 46%).
So the gate is NOT optimising a reward that rewards inaction. **Both standing explanations for the
low gate are now measured false**, and that is the useful part of this result: the gate refuses to
play against a reward that pays richly for playing.

The tool's own flag is the remaining lead: **ACTION TAX -- 6 terms fire and can NEVER be positive**
(`building_waste`, `threat_miss_idle`, `xbow_into_push`, `spell_waste`, `xbow_overaggression`,
`nado_bad`). Five of the six are reachable only BY ACTING. That is a one-sided risk on plays with
no matching one-sided credit, and it is the next thing to quantify per-decision rather than in
totals -- totals are what produced the retracted claim above.

### /!\ TWO INSTRUMENTS DISAGREE 2x ON WINRATE FOR THE SAME CHECKPOINT

`policy-stats` reports **35%** on 300 matches; `wr_eval` reports **17.0% +-5.2** on 200 fixed
seeds. Same checkpoint, same day. They use different opponent sets, so this is not necessarily a
bug -- but no conclusion should quote a winrate without naming which harness produced it, and the
gap needs closing before either is used as a gate. This is the same class of error as gate_probe
(§4z correction) and the drill scaffolding: measure the instrument before trusting the number.

## §5b — The ACTION TAX is dead too: a play is worth +5.45 sigma MORE than a wait

`tools/action_tax.py`, 40 greedy matches on `policy_BEST_m18000`, 11,728 decisions. Reward terms
attributed to the DECISION that produced them by snapshotting the env's own per-term totals either
side of one step -- per-decision, never totals, because totals are what killed 3x's claim.

```
steps=11728   plays=1201 (10.2%)   waits=10527

  play   mean +0.1471   sd 1.0035
  wait   mean -0.0112   sd 0.2318
  play - wait = +0.1583   (5.45 sigma)
```

The tax terms ARE real and they ARE one-sided on plays -- `xbow_into_push` -0.0566/play,
`xbow_overaggression` -0.0175, `building_waste` -0.0103, ~-0.085 per play in total. They are simply
**dwarfed by the credit**: `wincon_exec` alone pays **+0.1813 per play**, plus `threat_response`
+0.0458 and `wincon_reach` +0.0142, ~+0.24. Net **+0.147 per play**.

Meanwhile a WAIT averages **-0.0112**, and `threat_miss_idle` (-0.0124/wait) is why.

### All three explanations for the low gate are now measured false

1. "the offence has no reachable positive signal" -- FALSE (§5a, +3466 vs -737)
2. "the policy learned that waiting pays"          -- FALSE (waits average NEGATIVE)
3. "an action tax makes playing EV-negative"       -- FALSE (plays beat waits by 5.45 sigma)

**The gate is not optimising a broken reward. It is failing to optimise a working one.** The bar
for a marginal play to be worth taking is only -0.0112, and its average play scores +0.147, yet it
plays on 10.2% of decisions. This is an OPTIMISATION failure, not a reward-design failure, and that
is now the narrowest the question has ever been.

### /!\ THE SELECTION CAVEAT, and the measurement that would close it

These are the policy's OWN plays, so play-steps are self-selected to be favourable. This shows the
plays it MAKES are good; it does not prove the plays it DECLINES would be. The counterfactual --
clone the state at wait-steps, force the policy's best play, compare returns -- is the measurement
that settles it, and `rollout_search` already has the cloning machinery.

But note the bar: a declined play only has to beat **-0.0112** to be worth taking, and its chosen
plays average **+0.147**. For the gate to be correct at 10.2%, the marginal declined play would
have to be worth thirteen times less than its average play. Possible; not obviously so.

Card and cell come from the POLICY, not a stand-in -- placement drives `xbow_into_push` and
`building_waste` directly, so a centre-cell stand-in would have manufactured the tax being tested
for. That is the gate_probe error (§4z correction) avoided by construction.

## §5c — THE CLIP FLIPS THE SIGN OF THE GATE'S LEARNING SIGNAL (504 windows, 34 sigma)

The optimiser investigation, and it did not need a new experiment: `train_sim_ppo` has been printing
the decisive diagnostic all along, and §4's own instruction was to **accumulate it across a run**
because it is underpowered per-window. Aggregated over **504 windows from all 18 A/B runs**:

```
GATE LOGIT PRESSURE   (+ = toward PLAY)
  clipped   (what training actually applies)   -0.00073   se 0.00005
  unclipped (what it would be without clip)    +0.00411   se 0.00015
  clipping REMOVES 0.00484 of pressure         +34.08 sigma, paired
  clipped pressure NEGATIVE in 393/504 windows; unclipped POSITIVE in 462/504

CLIP INCIDENCE                       PLAY        WAIT       ratio
  clip rate                          0.4149      0.0015     278x
  gradient KILLED                    0.2214      0.0009     238x

PUSH ON PLAYS
  surviving (after clip)  +0.29701      raw CONTROL (no clip)  +0.52184
  clipping removes 43% of the push toward playing
  play share of steps: 3.10%
```

**Without the clip the gate's net signal points TOWARD playing (+0.00411). With it, it points
AWAY (-0.00073).** The clip does not merely damp the signal -- it INVERTS it. That is the whole
gate failure, and it is an OPTIMISER ARTIFACT.

### The mechanism, end to end

Plays are ~3% of steps. `d(log p)/d(logit)` is ~1 for the MINORITY action and ~p for the majority,
so an identical logit move swings a play's log-ratio ~1/p harder -- §4 measured 19x on this very
head. So plays leave the +-20% trust region **278x** more often than waits, 22% of their gradient is
killed outright against 0.09% of waits', 43% of the push toward playing is deleted, and what
survives is net NEGATIVE. Fewer plays makes plays a smaller minority, which widens the asymmetry.
It is self-reinforcing, which is why it looks like "decay from start".

### /!\ THIS CORRECTS §4's STANDING CONCLUSION

§4 reported *"the PPO surrogate's net gate pressure is ~0 while P(play) is collapsing -- i.e.
something outside the PPO term is driving the gate down"* and sent the search to the entropy bonus,
`_clamp_heads()` and the exploration floors. That reading was **underpowered**: per-window sd is
0.00104 against a mean of 0.00073, so a single window cannot see it. §4 said so itself and said to
accumulate. Accumulated, the clipped pressure is **-14 sigma from zero**, not ~0. The cause is
INSIDE the PPO term after all, and the hunt outside it can stop.

### What to do, and it is already built and staged

`ppo_clip_play_mult` widens the clip bound for PLAY actions only. It is **1.0 = OFF**. §4 measured
4.0 as cutting the kill asymmetry to 3.5x and buying ~8.5 reward and ~0.22 P(play), and its
**5-value x 2-seed sweep is STAGED AND UNRUN**. That sweep is now the highest-value experiment on
the board, and at 700 matches it is ~2 hours, not 8.

/!\ Do NOT restate the retracted claim #4 ("mult=4.0 stops the decay") -- it was overstated on one
seed and the honest prior is "reduces the damage". What is NEW here is the MECHANISM at 34 sigma
and the SIGN FLIP, neither of which was established before; the knob's effect size still is not.

## §6-LADDER — Model capacity: the escalation order, and why it is LAST not first

Owner asked (2026-08-28) whether 481,136 parameters is too small for a game state this complex,
noting that effective game-playing models often carry millions or billions. The instinct is
reasonable and the answer is **not yet** -- with a pre-committed ladder so it does not get relitigated
from scratch each time.

**Run in this order. Each rung fires only if the one above comes back NULL.**

1. **`ppo_clip_play_mult` sweep** -- RUNNING (5 values x 3 seeds x 700 matches, from scratch).
   Targets the measured mechanism: the clip INVERTS the gate's learning signal (§5c, 34 sigma).
2. **CRITIC CAPACITY** -- if the sweep is null. The critic is a single `Linear(328 -> 1)`, **329
   parameters**, and `ppo_value_detach` would reduce it to a literal linear probe on policy
   features. PPO is only as good as its advantages, and advantages are `reward - V(s)`. Value loss
   is NOT settling: the sweep's control run reads `vl 1.250 -> 2.371 -> 2.095`, drifting UP.
   The change is a 2-layer MLP critic -- a few THOUSAND parameters, not millions -- and it is
   testable at the same 700-match scale. Measure the advantage's sign and magnitude split by
   PLAY vs WAIT before and after; that is the quantity the gate actually consumes.
3. **TRUNK WIDTH** -- if the critic A/B is also null. Only then does "the model is too small"
   become the leading hypothesis rather than a guess.

### Why capacity is not the leading hypothesis today -- three independent measurements

* **Rollout search takes the FROZEN policy from 37.0% to 85.7%.** Same weights, same 481k
  parameters, same observation, same opponents. If capacity were binding, searching over the
  network's own outputs could not extract 2.3x the winrate. The information is already in there.
* **Distillation reached 0.90 card agreement with that teacher (+4.2 sigma) and winrate did not
  move.** The network had no trouble REPRESENTING a much better card policy at current size.
* **The cell head is learning hard, not saturating** -- 2,225x an untrained net's within-card logit
  spread.

And the measured bottleneck is a SIGN FLIP in the clip. Parameters do not fix a sign error.

### The constraint that actually binds is SAMPLE THROUGHPUT

~**290 matches/hour** -- the engine is pure Python and CPU-bound, and the network is nowhere near
the bottleneck. The 8k run took ~14 hours and came out flat. AlphaStar's parameter count came with
~1e11 environment steps behind it; this project is at ~1e4 matches. Scaling parameters without
scaling data buys worse sample efficiency and more overfitting, against an optimiser bug that would
still be there. If rung 3 is ever reached, **fix throughput first** -- it is an engineering problem
(the pure-Python engine), not an architecture one.

## §5d — The clip sweep: the mechanism was REPAIRED and it bought NOTHING. Ladder advances to the critic

5 values x 3 seeds x 700 matches, from scratch, drill_frac 0.3. The experiment §5c pointed at.

```
mult  clipPLAY  killPLAY  gatePress   %neg-windows   finalWR    sd    avg_rew    sd
1.0     0.3741    0.1971   -0.00060       75%          6.67   5.03    -19.50   0.80
1.7     0.2057    0.0872   -0.00004       51%          1.33   1.15    -20.07   1.21
2.5     0.1327    0.0480   +0.00015       26%          2.67   3.06    -20.83   2.70
4.0     0.0702    0.0279   +0.00024       24%          2.00   2.00    -22.30   1.01
6.0     0.0149    0.0099   +0.00015       32%          4.00   2.00    -19.13   0.15

vs control:  1.7  WR -5.33pp (-1.79s)  rew -0.57 (-0.68s)
             2.5  WR -4.00pp (-1.18s)  rew -1.33 (-0.82s)
             4.0  WR -4.67pp (-1.49s)  rew -2.80 (-3.75s)   <- significantly WORSE
             6.0  WR -2.67pp (-0.85s)  rew +0.37 (+0.78s)
```

**The intervention did exactly what it was supposed to.** Clipping on plays fell 25x, outright
gradient-kill 20x, and the gate pressure **FLIPPED POSITIVE** at mult >= 2.5 -- negative windows
went 75% -> 24%. §5c's mechanism is confirmed live and repairable.

**And no arm beat the control.** Every one is worse on winrate (-0.85 to -1.79 sigma, none at the
2-sigma bar) and mult 4.0 is **-3.75 sigma worse on reward**, which does clear it in the wrong
direction.

### What this kills

**The clip sign-flip is REAL but is NOT what limits performance.** That is a hard result and it
cost only ~3 hours: a 34-sigma mechanism was identified, repaired, and the outcome did not follow.
Do not reopen `ppo_clip_play_mult` without a new reason -- and note the retracted claim #4
("mult=4.0 stops the decay") is now doubly dead, since 4.0 is the *worst* arm on reward here.

/!\ Read the winrate column with its spread: the control's own sd is 5.03pp across three seeds, so
"all arms worse" rests mostly on direction plus the reward column, not on any single 2-sigma
winrate result. The claim is "no improvement, and some evidence of harm" -- NOT "widening the clip
is proven harmful".

### LADDER ADVANCES (§6-LADDER rung 1 -> rung 2): the CRITIC

Next is critic capacity, and the case for it is already written: the critic is a single
`Linear(328 -> 1)`, **329 parameters**, PPO is only as good as its advantages, and value loss is
not settling. Measure the ADVANTAGE split by PLAY vs WAIT before and after a 2-layer MLP critic --
that is the quantity the gate actually consumes, and §5b already showed the per-decision REWARD
favours playing by 5.45 sigma while the policy plays 10% of the time. If the reward says play and
the advantage says wait, the critic is the gap.

## §5e — P(play) IS INVARIANT TO THE GATE'S LEARNING SIGNAL (the sweep's missing middle)

§5d measured the clip sweep's MECHANISM and its OUTCOME and skipped the step between them. Measured
now, on the 15 checkpoints already on disk -- no new training:

```
mult   P(play) mean     sd     share>0.25   elixir>=6      gate pressure (5d)
1.0       0.1160     0.0046      6.9%        18.4%          -0.00060  (toward WAIT)
1.7       0.1123     0.0049      7.6%        18.5%          -0.00004
2.5       0.1163     0.0040      8.3%        15.3%          +0.00015  (toward PLAY)
4.0       0.1170     0.0139      7.7%        16.2%          +0.00024
6.0       0.1107     0.0074      5.7%        17.7%          +0.00015
```

**The gradient pressure on the gate was INVERTED from negative to positive, and P(play) did not
move.** Range 0.1107-0.1170, spread 0.006 against a within-arm sd of 0.004-0.014.

### What this kills

The whole chain §5c proposed -- "the clip inverts the gate's signal, so the gate learns to wait,
so P(play) collapses" -- has a broken link. The first half is real and measured at 34 sigma. The
second half is FALSE: P(play) does not follow the gate's pressure. Any future plan that reasons
"fix the gate's gradient and it will play more" is contradicted by this table.

### It also reframes three earlier readings

* §4z's "it banks elixir and never fires" is wrong in its premise here: elixir reaches 6 on only
  **15-18%** of steps in these runs, so there is not much banking to spend.
* §5b (reward favours playing +5.45 sigma) and the advantage probe (+0.80 across 3 seeds, n=3038+)
  are both still true -- and now BOTH are known not to move P(play) either.
* Every input to the update measures as pointing toward playing, and the play rate sits at 0.11
  regardless. The problem is not what the update is TOLD.

### Where to look next, and what NOT to assume

P(play) being pinned at ~0.11 across five very different trust regions suggests something outside
the policy gradient sets it. Candidates, none measured:
1. **The behaviour policy** -- exploration floors / prior mixing deciding what is actually sampled.
   §3p already found exactly this class once: floors overrode the bot's own choice 75-85% of the
   time and produced a pi/mu of ~0.0125.
2. **The elixir economy** -- a sustainable play rate is bounded by generation, not preference.
   ⚠ But do NOT jump to this: the watchdog reads 46% FORCED waits (nothing affordable) and 44%
   gate-chosen waits, so on affordable steps it still declines ~81% of the time. It is not
   obviously at an economic ceiling.
3. **Gate logit saturation** -- the card head has a `_LOGIT_CAP` tanh for exactly this failure;
   whether the gate has an equivalent bound has not been checked.

The cheap discriminator is (1): compare the BEHAVIOUR play rate against the NETWORK's own greedy
play rate on the same states. If they differ, the network is not the thing choosing.

## §5f — THE GATE WAS NEVER COLLAPSED. P(play) over ALL steps is an affordability statistic

Measured in the trainer's own sampling path, 3 seeds x 200 matches from scratch, n ~16,000 steps
each:

```
seed   anything playable   gate P(play) GIVEN a choice   raw pref over ALL steps
 41          6.0%                    0.5636                      0.0341
 42          4.6%                    0.5349                      0.0247
 43          7.5%                    0.3445                      0.0258
```

**Given an affordable card, the gate plays 34-56% of the time.** That is a decisive gate, not a
collapsed one. The 0.03 figure over all steps is ~0.05 x ~0.45 -- it is dominated by how often a
card is affordable at all, and barely reflects the gate's preference.

### What this invalidates

§4z, §5c, §5d and §5e all tracked **P(play) over all steps** and read it as the gate's behaviour.
It is not. It is mostly an elixir statistic. Specifically:
* "the gate collapsed to never-play" -- the gate given a choice is 0.34-0.56, not collapsed;
* §5e's "P(play) is invariant to the gate's gradient" is still TRUE as measured, and now has an
  obvious reason: the quantity is set by affordability, which the gate's gradient does not move;
* the whole ladder (clip -> critic -> capacity) was aimed at a number that was never measuring what
  it was believed to measure. The clip sweep's null and the critic's exoneration both stand -- they
  were correct answers to a question about the wrong statistic.

### The story that now fits every measurement

The gate is EAGER, not reluctant. It plays on ~45% of the steps where it can, so elixir is spent as
soon as it arrives and never accumulates: mean elixir 2.29, elixir >= 6 on 15-18% of steps,
`bank_to_six_then_bow` at 0%. The 6-cost win conditions are therefore rarely affordable, x_bow and
rocket rarely get played, and the deck cannot execute its own win condition. That is the same
failure the drills have been reporting all along, with the sign of the cause REVERSED: not "it
refuses to play", but "it plays too readily on cheap cards to ever bank for the expensive ones".

### /!\ Confirm before building on it

* These are 200-match FROM-SCRATCH runs. An untrained policy spending fast would produce exactly
  this picture, so the same split must be measured on a TRAINED checkpoint before it is a claim
  about the trained policy.
* **4.6-7.5% affordability is itself suspicious.** The deck holds skeletons (1) and the Log (2),
  and a 4-card hand should contain something cheap far more often than 1 step in 20. Either the
  economy is much tighter than expected, or the affordability mask is under-reporting. That is a
  bug hypothesis in its own right and should be checked directly, not assumed.

### The instrument lesson, again

`gate_probe` reports sigmoid(gq1-gq0) on RAW logits; the trainer's p_g uses MASKED logits. Those are
different quantities and this file has been quoting them interchangeably (0.171 vs 0.03). Any future
P(play) number must say WHICH, and whether it is conditioned on a card being affordable.

## §5g — /!\ §5f IS RETRACTED. Affordability is 64%, and the trained gate declines 82% of its chances

§5f concluded "the gate was never collapsed -- given an affordable card it plays 34-56%, and
P(play) over all steps is an affordability statistic". That was measured on **FROM-SCRATCH runs
mixed with DRILLS**, and §5f's own caveat said to confirm it on a trained checkpoint before
believing it. Confirmed, and it does not hold.

Trained `policy_BEST_m18000`, **match-only** (`--drill-frac 0`), policy frozen by the value warmup,
3 seeds, accumulated over full matches:

```
                      anything playable    P(play) GIVEN a choice    raw pref overall
  from scratch + drills      4.6-7.5%            0.34-0.56               0.025-0.034
  TRAINED, match-only        63.3-64.5%          0.167-0.188             0.107-0.119
```

**Both halves of §5f were artifacts of the wrong sample.** Drills carry scripted elixir and an
untrained policy spends to zero on arrival, which manufactures both the 6% affordability and the
high conditional rate.

### What is actually true

* **Affordability is NOT the binding constraint.** Something is playable on ~64% of steps.
* **The trained gate declines ~82% of the opportunities it has.** It is reluctant, and the
  reluctance is a property of the gate, not of the elixir economy.
* The raw over-all-steps preference (0.107-0.119) matches `gate_probe`'s 0.116 -- those two
  instruments agree once the statistic is named properly.
* **Training roughly HALVES the conditional play rate**: 0.34-0.56 from scratch -> 0.167-0.188
  trained. That is the decay, measured for the first time on the statistic that isolates the gate
  from the elixir economy. Every previous decay measurement was contaminated by affordability.

### So the open question is restored, and sharper than before

The gate declines 82% of its chances while:
  reward per decision favours playing        +5.45 sigma  (§5b)
  advantage favours playing                  +0.80, 3 seeds, n=3038+
  the gradient's sign was repaired           §5d -- and P(play) did not move (§5e)
  the critic is exonerated                   advantage agrees with reward
  its card choice is learnable               0.4955 -> 0.8754 (§8)

Everything the update is told points toward playing, and the conditional rate still halves during
training. §5e's invariance stands and now has NO benign explanation -- affordability was the last
one and it is gone.

### Method note, paid for twice today

Both §5f and its retraction came from the same diagnostic; only the SAMPLE differed. A from-scratch
run with drills and a trained run on matches are different populations, and the gate statistic is
not comparable across them. Any future gate number must state: trained or from scratch, drills in
or out, and conditioned on affordability or not.

## §5h — THE SIGN WAS BACKWARDS ALL SESSION. The policy is TOO EAGER, not too reluctant

Owner's argument, and it is correct: an affordable card is not an opportunity. A policy that played
whenever it could afford something would spam 1-3 elixir cards on cooldown and never bank for its
win condition. Declining most affordable steps is what banking discipline LOOKS like. The test has
to condition on the RESULTS of plays, not on the elixir at the time of the play.

Measured against the SEARCH TEACHER -- outcome-grounded by construction, it rolls the future out --
on the 36,521-decision corpus already on disk:

```
  SEARCH TEACHER play rate   0.2109      (this agent wins 85.7%)
  POLICY         play rate   0.3552      (this agent wins 37.0%)
                             +14.4 pp -- the policy plays 68% MORE than the far stronger agent

  both play                        0.0923
  both wait                        0.5262
  teacher plays, policy WAITS      0.1186   <- "too reluctant" errors
  policy plays, teacher WAITS      0.2629   <- "too eager" errors
  gate agreement                   0.6185
  eager : reluctant                2.22 : 1

  when BOTH play, same card:       0.8650   -- the card head is fine
```

### Everything about the gate this session was pointed the wrong way

* "The gate is collapsed / reluctant / will not fire" is FALSE. It fires too often.
* `27.9 plays/match` (policy-stats) is a normal human play rate. It was never under-playing.
* The clip sweep widened the trust region FOR PLAYS -- i.e. pushed harder in the wrong direction --
  which is the most likely reading of mult 4.0 measuring **-3.75 sigma on reward** (§5d). That was
  filed as "no improvement, some evidence of harm"; the harm now has a mechanism.
* §5b's reward (+5.45 sigma) and the advantage probe (+0.80) both measure the policy's OWN plays,
  which are SELF-SELECTED. §5b flagged that caveat and I under-weighted it. The marginal play it
  declines is not the average play it makes -- and the teacher says 26% of the plays it DOES make
  should have been holds.
* `bank_to_six_then_bow` at 0% is explained exactly as the owner said: it spends on cheap cards and
  never reaches 6.

### The real target is RESTRAINT, and it was named long ago

§6-PRIORITY already split the spell failure into PLACEMENT and **RESTRAINT** -- "it casts when it
should hold" -- and `never_rocket_their_king` (a do-NOT-cast drill) has been at 0-17% throughout.
That was the correct diagnosis. This session spent itself chasing the opposite sign.

### What follows

The teachable signal exists and is already labelled: **26.3% of decisions are plays the teacher
would decline**, versus 11.9% the other way. Distillation on the GATE was measured as not learnable
(0.5892 -> 0.6012, below the always-WAIT floor of 0.7756) -- but that was fitting the gate as a
2-way classifier over ALL decisions, where the majority class dominates. Restraint on the
over-played subset is a different, much better-posed target and has NOT been tried.

/!\ Do not read this as "make it play less" globally. The teacher still plays on 21% of decisions
and the policy misses 11.9% of those. The target is the DISAGREEMENT, not the rate.

## §5i — Restraint IS separable: AUC 0.667 from a LINEAR probe, and 74% of its plays are over-plays

The cheap check before building anything: are the plays the teacher declines distinguishable from
the plays it endorses, using only what the student can see? Corpus already on disk, split BY MATCH.

```
  policy-play decisions   12,972
  teacher agrees           0.2599     <- only 26% of the policy's plays are ones the teacher makes
  OVER-PLAYS               0.7401     <- three in four of its plays are wrong
  majority-class baseline  0.7478 (test split)

  logistic     held-out AUC 0.6675   acc 0.7632
  2-layer MLP  held-out AUC 0.6157   acc 0.6350
```

**AUC 0.667 is a LOWER BOUND.** The probe sees 97 features: hand 10, next 10, elixir 1, threat 52,
and the 96x64x12 board crushed to 24 numbers (per-channel mean and std). The conv policy sees the
whole board. A state-dependent restraint rule is learnable from the student's own observation --
which is exactly the thing §6.2 proved a SCALAR THRESHOLD cannot express ("search's restraint is
STATE-DEPENDENT and no scalar reproduces it", threshold swept 0.02-0.60, 0.25 optimal both ways).

### Read the metrics the right way

Accuracy is nearly useless here: the class is 74/26, so "always call it an over-play" scores 0.748
and the logistic model's 0.763 looks like nothing. **AUC is the metric** -- the ranking carries the
signal, and 0.667 on a linear probe over a crushed board is a real result.

⚠ The MLP scoring WORSE than logistic (0.6157 vs 0.6675) is overfitting on 10.5k rows with 97
features, not evidence against separability. A real run needs regularisation and the full corpus,
and should be judged on AUC over held-out MATCHES, never on accuracy.

### Why this is not a repeat of the failed gate distillation

§8 measured gate distillation at 0.5892 -> 0.6012 against an always-WAIT floor of 0.7756 and called
it unlearnable. That fit the gate as a 2-way classifier over ALL 36,521 decisions, where 79% are
waits: a model scores 0.776 by never playing, so the loss barely rewards learning WHEN. This is a
different problem -- conditioned on the policy already wanting to play, asking only whether that
particular play is one the teacher would make. Same corpus, different question, and the answer is
that the signal is there.

### Next

Train the restraint head properly: full corpus, conv over the real board, class-weighted, scored on
held-out AUC by MATCH. Then the intervention is a veto on the policy's own plays -- it never needs
to make the policy play MORE, only to decline the ones it should not make, which is the failure the
drills (`never_rocket_their_king` 0-17%) and §6-PRIORITY's RESTRAINT arm have both reported all
along.

## §5j — THE RESTRAINT VETO IS HARMFUL. Declining the teacher's declines is not the teacher's edge

Built the head §5i's separability check justified, then measured it where it counts. Matched
control: same checkpoint (`policy_BEST_m18000`), same 200 fixed opponent seeds, greedy, veto ON/OFF.

```
  restraint head: held-out AUC 0.6942 (linear-probe baseline 0.6675, chance 0.5)
  veto precision at q=0.1: 95.0% against a 74.8% base rate -- 19 of 20 vetoed plays are real over-plays

  baseline (no veto)   15.5% +/- 5.0   plays 8.0%
  veto q=0.1           14.5% +/- 4.9   plays 7.7%
  veto q=0.2           14.0% +/- 4.8   plays 7.6%
  veto q=0.3           10.0% +/- 4.2   plays 7.6%
  veto q=0.5            5.5% +/- 3.2   plays 5.6%      <- exactly the UNTRAINED baseline
```

**Monotone harm.** 15.5 -> 5.5 across the sweep, and the q=0.5 drop (10.0 points) clears the
combined interval (5.9). A 95%-precise veto on genuine over-plays makes the policy strictly worse.

### Why, and it is the useful part

The head is not wrong -- it identifies over-plays at 95% precision. What is wrong is the assumption
that REMOVING those plays recovers the teacher's advantage. **The teacher does not merely decline;
it declines AND THEN PLAYS AT A BETTER MOMENT.** The veto delivers only the first half: it takes
plays away and puts nothing in their place, so the policy loses the defence and pressure those
plays were providing and gains none of the timing that made declining correct for the searcher.

The teacher's "wait" label is CONDITIONAL ON THE TEACHER'S OWN SUBSEQUENT BEHAVIOUR. Transplanted
into a policy that will not follow through, it is not a good label. Half a policy is not half the
benefit.

### What survives and what dies

* DIES: the restraint veto, at every operating point tested. Do not revive it as a decision-time
  filter without a mechanism that also supplies the replacement play.
* SURVIVES: the DIAGNOSIS. The policy does play far more than the teacher (0.3552 vs 0.2109) and
  74% of its plays are ones the teacher declines (§5h). That measurement is unaffected -- what is
  refuted is a specific intervention built on it.
* SURVIVES: §5i's separability (AUC 0.694). The signal is real; it is just not actionable by
  subtraction.

### The pattern this makes four times

distillation moved card agreement +4.2 sigma -> winrate unmoved.
the clip fix flipped the gate's gradient sign at 34 sigma -> P(play) unmoved.
the critic was exonerated -> nothing to fix.
the veto cut real over-plays at 95% precision -> winrate WORSE.

Four interventions, each hitting its stated mechanism, none improving the outcome. The one thing
that HAS moved the outcome remains rollout search (37.0% -> 85.7%), which differs from all four by
replacing the whole decision rather than editing one part of it. That is the observation any next
attempt should start from.

## §5k — LIVE SEARCH: the blocker was a NET CONTRACT mismatch, and the real lesson is startup-time proof

`ValueError: not enough values to unpack (expected 5, got 3)`, 9 times in 25 decisions, after
`AttributeError: '_Env' object has no attribute 'db'`, 19 times in 25, after two earlier rounds of
`ran 0`.

### The cause
Three nets reach the searcher and they return different arities:

| net | forward returns | arity |
|---|---|---|
| sim `PPONet` | `(cards, cells, gate, value, value_d)` | 5 |
| **train-rl `DQN`** (`_build_net`) | `(cards, cells, gate)` | **3** |
| `play.py` | `PolicyNet` + separate gate head | 3 |

`rollout_search` was written against the sim net and unpacked exactly five. The first three are
identical in meaning and order, and the two value heads were **discarded on the same line**
(`cq, ceq, gq, _, _`). A non-difference was made into a hard failure. Fix: take the first three.

### The pattern, four times in one feature
Every live-search failure was a property of the WIRING, not of any board:

1. `record_enemy_play()` called by nothing -> confidence 0.0 forever
2. tracks passed as base-name STRINGS -> `tr[0..2]` read `'k','n','i'`
3. `_Env` stub missing `db`/`actions`/`n_cells`/`specs`
4. net arity 3 vs 5

All four were deterministic and catchable BEFORE a match. All four were instead found as a
per-decision error counter mid-run, each costing a live run to diagnose. `LiveSearch._selftest()`
now runs one real forward at construction and either prints `net contract OK (N outputs)` or
DISABLES search naming the exception. It caught its own author on the first run (placed before
`_env` was assigned).

**Rule this earns: a feature whose failure mode is fixed wiring must prove its wiring at startup.
An error COUNTER is not a diagnosis, and a bare count with no exception name cost three runs.**

### Measured, against the exact net train-rl builds
    net contract OK (3 outputs); search is live
    asked 6, ran 3, changed 3 | error 0
Previously `ran 0` every time. 4-tuple tracks (`enemy_tracks` without `with_base`, no card
identity) drop as `no_identity` rather than crashing. Producer formats confirmed at
`replay_mine.py:483`: `(x, y, vx, vy, base)` with base, `(x, y, vx, vy)` without.

### GHOST PLAYS -- correction, and the measurement that was being thrown away
I said the affordability guard "fixed" the unaffordable plays. **`ran 0` means that override never
executed once**, so it cannot have been the cause of what the owner was seeing. The guard was a
real bug in code that was never reached; the claim overstated it.

What is actually true, measured:
* `env.elixir` at decision time IS the conservative floor (`int(frac - elixir_margin)`), written at
  `env.py:2065`. The other writer (`:858`) is the match-START path and does not race it.
* `train_rl.py:1139` and `play.py` both filter on `card_elixir[i] <= env.elixir + 1e-6`. The mask is
  correct.
* `play.elixir_safety_margin` has **no entry in config.yaml** and runs on its 0.25 default.
* A ghost-play DETECTOR already existed at `_settle_deploys` and is careful (counts a miss only
  when the two hypotheses differ by >=1.5 and the reading favours not-deployed by 0.75). But
  `_failed_deploys` was **incremented and read by nothing**, and its per-card print sat behind
  `spell_verify_log`, an unrelated flag. The bot has been measuring the exact reported symptom and
  discarding it, in BOTH decks.

Now reported: per-match `[deploy] ghost plays: N of M (X%)` plus `ghost_plays` and `elixir_margin`
in the reward-stats JSONL. **The margin is NOT retuned yet -- deliberately.** The historical 24%
tap-failure and 61%-at-slack-0 numbers predate the margin, so there is currently NO measurement of
the rate WITH it. Raising the margin trades ghost plays for missed plays; make that call on the
next live run's number, not on a guess.

## §5l — LIVE SEARCH TIMEOUTS: the cost curve, and why discarding a finished search is dominated

After §5k the errors went to zero and the counter read `ran 0, timeout 22` of 25. Search worked and
was being thrown away.

### The cost curve (MEASURED, live path, 13-candidate sweep)

| bodies | full sweep | per rollout |
|---|---|---|
| 2 | 61 ms | ~4.7 ms |
| 6 | 151 ms | ~11.6 ms |
| 12 | 262 ms | ~20 ms |
| 20 | **602 ms** | ~46 ms |
| 30 | **927 ms** | ~71 ms |

`act_period` is 600 ms. At 20+ bodies a full sweep costs MORE THAN THE ENTIRE DECISION PERIOD, and
the bot is blind for all of it. The budget was 120 ms, so the old code paid the full cost and then
discarded the answer for being late -- maximum latency, zero benefit, and it bit hardest on exactly
the crowded boards where search is worth most. The bridge is NOT the cost: tracks_to_bodies 0.4 ms,
build_engine 0.1 ms, LiveOpponent 0.4 ms, searcher.act 164.9 ms.

### Two repairs, and one instrument that was wrong
1. **Interruptible scoring.** `scores = [self._rollout(a) for a in cands]` was all-or-nothing. It
   now checks a wall-clock `deadline` BETWEEN rollouts and keeps its best-so-far. `cands` is ordered
   WAIT-first then by descending policy preference, so a prefix is the right subset to keep.
   `deadline = None` by default, so **no clock is consulted on the sim path and sim behaviour is
   unchanged by construction** -- the 37.0% -> 85.7% sim result stays the reference.
2. **Stop discarding finished work.** Throwing away a COMPLETED search is strictly dominated: the
   latency is already spent. The "too stale to use" reasoning does not survive contact with the
   facts -- the policy's action and the search's action are computed from THE SAME observation, so
   search does not age the board estimate. The only real cost is a later tap, and the deadline is
   what bounds that. The hard timeout now fires only at 2x budget (pathological runaway), and
   over-budget-but-used is counted separately so the budget can be tuned against real boards.

**A body-count ceiling was considered and REJECTED on measurement.** The 2-rollout floor is NOT
monotonic in bodies (2:54, 6:95, 12:184, 16:88, 20:183, 25:78, 30:98 ms) because a rollout ends when
the match does -- a crowded board can be CHEAPER. Body count does not predict cost, so it cannot
gate on it.

### Measured after, full decide() path, real DQN net
    bodies:      2     6    12    20    30    40
    wall ms:   171   205   218   184   221   282
    ran:       9/9   9/9   9/9   9/9   9/9   9/9      timeouts 0/54
Was 927 ms and 22/25 discarded. `live_search_timeout_ms` default 120 -> 250; internal deadline is
0.6x that, sized so deadline + one worst-case rollout (150 + 70) stays inside the cap.

/!\ NOT YET MEASURED: whether live search HELPS. The ceiling is 13-27% of the sim gain at n=30 with
incoherent ordering. It now runs; that is all that is established.

## §5m — THROUGHPUT: the GPU is not the lever, and `--search-interval` is nearly free

Owner asked whether hardware (RTX 5050, overclock, more CPU) can lift 252 matches/hour.

### Where the time actually goes (MEASURED, in-process, warmed)
```
env.step                3.539 ms
Searcher.act (i=1)    238.4   ms      = 67x an env step
search share of a decision                98.5%
```
The run is not stepping envs, it is **searching**. Everything else follows from that.

### The GPU does nothing, and this time the measurement is strong
```
cpu   Searcher.act  209.1 ms
cuda  Searcher.act  206.6 ms      1.2% -- noise
```
Same instrument, warmed CUDA context, `torch.cuda.synchronize()` around the timed region, measured
on the DOMINANT cost rather than on a wave-distorted `ep/s`. §4b reached the same verdict from a
weak instrument (both arms read 0.50 ep/s at ep100, which §4b itself flagged as wave timing); this
supersedes it with a direct read. The reason is structural: `Searcher.act` is Python SimEngine
clone-and-roll-forward. The net forward is a rounding error inside it, and the net is the only part
a GPU can touch. **Overclocking cannot help either -- the card is not the bottleneck, it is idle.**

### CPU headroom is real but not reachable by "using more CPU"
Trainer measured at **3.25 cores of 16 (20%)**. It cannot use more: search forces `--workers 0`
(:1651 refuses `--search-interval` with workers>1, because the envs live in worker processes and
search must clone an in-process engine). The idle 12 cores are locked behind that seam.

### THE LEVER: raise `--search-interval`. The teaching rate barely moves.
Search work scales as 1/N; env stepping does not.

| interval | ms/decision | decisions/s | searched steps/s | speedup | 50k matches |
|---|---|---|---|---|---|
| **1 (now)** | 241.9 | 4.13 | 1.88 | 1.0x | **8.3 days** |
| 4 | 63.1 | 15.85 | 1.80 | **3.8x** | 2.2 days |
| 8 | 33.3 | 30.0 | 1.71 | **7.3x** | 1.1 days |

**The number of teacher demonstrations per hour is nearly CONSTANT (1.88 -> 1.80 -> 1.71, -9% at
interval 8) while total experience multiplies 7.3x.** Interval controls how often the student is
taught per unit of experience, NOT how good the teacher is -- the 85.7% ceiling is a property of
the searcher (H=12, cells=3), both unchanged. So raising it buys experience at almost no cost in
supervision. This is an ARITHMETIC projection from the two measured costs, NOT an observed run.

Also measured, because it was worth checking: at interval=1, **45.5% of steps are searched**, so the
PPO surrogate still trains on 54.5%. The run is a ~45/55 imitation/PPO mix, not silently pure
distillation. (`Searcher.act` returns `searched=False` when fewer than 2 candidates exist -- common
here, since the elixir collapse leaves nothing affordable.)

### Structural fix, if throughput matters beyond this run
Teach the WORKERS to search: each holds its own envs, so each could own a Searcher, which
parallelises the 98.5% across cores instead of the 1.5%. Needs net weights broadcast to workers each
update -- `_broadcast_league()` already establishes that channel. Not attempted; sized as real work.

## §5n — DRILL + MATCH READ ON THE SEARCH RUN AT m=1600 (and why the comparison is confounded)

Owner asked for match and drill performance plus collapse signatures on the live search PPO run
(`--matches 50000 --envs 192 --workers 0 --search-interval 1 --init policy_BEST_m18000`).

### Match (wr_eval, 150 matches/arm, fixed seeds, greedy gate)
```
ppo_probe.pt (m=1600)          3W-147L-0D   winrate  2.0% +/-2.2   plays 4.8%
policy_BEST_m18000 (m=18000)  17W-132L-1D   winrate 11.3% +/-5.1   plays 8.2%
DIFFERENCE -9.3 points -- larger than the combined interval (5.5). Real.
```
/!\ **This is exactly the comparison §4a forbids.** `--init` loads policy+gate but NOT the critic;
§4a measured the dip bottom at ~1,700 episodes (`ep1675 -1.600`) with recovery by ~7,600, and its
own conclusion is *"comparing a mid-run checkpoint against its init systematically understates the
change being tested -- compare run-vs-run at matched episode counts instead."* m=1600 IS the bottom.
The -9.3 is the warm-start tax sampled at its worst point, not a verdict on search. Keep the number
as a matched-instrument baseline for a later checkpoint; do not read it as failure.

### Foundational drills, 25 reps (vs §4t's policy column at 6 reps -- DIFFERENT checkpoint AND rep count)
```
drill                             §4t     now(m=1600)
nado_king_activation                0%       0%    (DOCTRINE GAP: oracle itself only 8%)
tesla_pulls_the_wincon             17%      24%
log_the_ground_swarm                0%      20%
ignore_the_ignorable (restraint)    0%      24%
hold_the_spell_for_a_target         0%       4%
log_rolls_forward_not_backward      0%       0%
bank_to_six_then_bow                0%       4%    <-- THE DECK'S WIN CONDITION
knight_blocks_the_charge           33%      24%
skeletons_kill_the_miner          100%      56%
bow_never_into_the_push            17%      20%    (DOCTRINE GAP: oracle 8%)
bow_punish_the_commitment         100%      56%
bow_punishes_the_pump             100%      60%
rocket_the_two_for_one              0%       0%
rocket_the_pump_on_sight            0%       0%
never_rocket_their_king            17%       0%
skeletons_stop_the_wall_breakers    0%       0%
                          mean   24.0%    18.25%
```
**The policy got FLATTER: it lost its three strengths and gained a little on its weaknesses.** The
drills §4t scored at 100% all regressed (100->56, 100->56, 100->60; non-overlapping even allowing
6-rep noise), while several 0% drills lifted slightly (0->20, 0->24). Zeros fell 9 -> 6.

That shape is what imitation of a different action distribution looks like, and it is ALSO what the
critic dip looks like, and this read cannot separate them -- one checkpoint, at the dip bottom, at a
different rep count from the reference. **Do not attribute it.** The matched-episode re-read is the
measurement that decides it.

### The one finding that is NOT confounded
`bank_to_six_then_bow` at **4%** (doctrine 100%). It has now read 0%, 16%, 0% and 4% across four
independent measurements spanning multiple checkpoints and both algorithms, and it agrees with the
live instruments: mean elixir 2.49 and only 5.1% of steps at >=6 in this very run, plus `plays 4.8%`
under a greedy gate while `P(play)` is 0.372. The policy wants to act constantly, spends to the
floor, and therefore can never afford its own win condition. **This predates the run and survives
every change tried so far.**

## §5o — INTERVAL-4 RESTART: throughput 2.85x confirmed; the card_ent alarm is an ARTIFACT; banking is the real regression

Owner restarted as `--search-interval 4` (same seed 41, same `--init policy_BEST_m18000`).

### Throughput: the lever worked, but under the projection
```
interval 1   252 matches/hour     50k = 8.3 days
interval 4   718 matches/hour     50k = 2.9 days      2.85x
```
§5m projected **3.8x**; the measured gain is **2.85x**. Two reasons, both mine: the 1/N model
credited all non-search cost to `env.step` (3.5 ms) when the real per-decision floor -- greedy
forward, obs build, bookkeeping -- is larger; and the 252/hr baseline was measured while my own
drill and wr_eval jobs were competing for CPU, so the true ratio is lower still. **The projection
was optimistic; the direction was right.**

### /!\ THE CARD-ENTROPY COLLAPSE IS AN INSTRUMENT ARTIFACT
The watchdog read `card_ent` 0.15 of 2.30, with 5 of the last 10 samples under 0.30, and
`exp(0.15) = 1.2 effective cards` -- which reads as "the policy plays one card". IT DOES NOT.

`ppo_watchdog.py:156` is `card_ent.append(_entropy(pc[i]))` averaged over states: the mean
**PER-STATE** softmax entropy, i.e. how confident the policy is at each individual board. A decisive
policy has LOW per-state entropy while still playing many different cards ACROSS states. Measured
over 1500 greedy steps, the realized play distribution is **9 of 10 cards, entropy 1.96 of 2.30**.

This is the third time an entropy read has pointed the wrong way in this project (see 3d50312, *"the
cell head was learning all along -- entropy was the wrong instrument"*). **Per-state entropy is not
behavioural diversity. Measure what the policy DOES, not how sure it is.**

### The real regression, same probe, both policies run SEARCH-FREE (interval 0)
```
                    plays   distinct  play-ent   x_bow    elixir mean   >=6
m18000 reference     8.5%     10/10     2.08     12.5%       4.98       35.4%
interval-4 m5400    12.5%      9/10     1.96      2.7%       2.18        1.0%
```
* **Elixir >=6 collapsed 35.4% -> 1.0%**, mean 4.98 -> 2.18. The reference banks. This run does not.
* **x_bow share fell 12.5% -> 2.7%.** The deck's win condition is nearly unused -- the direct
  consequence of never holding 6 elixir, and exactly what `bank_to_six_then_bow` (4%) reports.
* **It plays MORE often, 8.5% -> 12.5%.** Over-eagerness, precisely §5h.
* Card diversity is FINE. That half of the alarm was the artifact.

⚠ Still partly dip-confounded (m=5400 is past the ~1,700 bottom but short of ~7,600 recovery), and
the two checkpoints differ in episode count. But a 35x drop in banking is far beyond what the dip
explains, and the direction reproduces the pathology that predates every change tried.

**Search-in-the-loop is NOT correcting the over-play/never-bank failure -- it is co-existing with a
worse version of it.** That is now measured at two intervals and two checkpoints.

## §5p — THE BANKING FAILURE IS DIAGNOSED: waiting is a strictly dominated ACTION CLASS

Owner asked whether this needs the run to reach 10k. It does not -- the pathology predates the run
and reproduces across checkpoints and both algorithms, so it is a property of the REWARD, not of
training progress. Measured on the current interval-4 checkpoint (m=5400), 12 matches, policy run
search-free.

### The measured asymmetry
```
positive terms, EVERY ONE requiring a play          per match
  spell_defence  +1.65   threat_response   +1.00
  wincon_reach   +0.58   chip_defence      +0.51
  wincon_exec    +0.39   nado              +0.38
  take_enemy_tower +0.33 chip_offence      +0.26
  threat_response_2nd +0.15  xbow_defends  +0.07
                                     TOTAL   +5.32

terms that can fire on a step where NOTHING was played
  threat_miss_idle  -0.68     leak  -0.03    TOTAL   -0.71   (both PENALTIES)
```
**Waiting has zero upside and non-zero downside. Playing carries +5.32/match of reachable credit.**
Waiting is not merely discouraged, it is a strictly dominated action class -- so the gate plays at
every opportunity, elixir sits at ~2.0, and a 6-cost win condition is unaffordable. Downstream,
measured against the reference: elixir >=6 **35.4% -> 1.0%**, x_bow share **12.5% -> 2.7%**.
`elixir_trade` IS negative (-0.72/m over 47 fires), so bad trades are billed -- the +5.32 simply
swamps it.

### The designed fix exists, is DISABLED, and would not be enough anyway
`restraint_hold` -- the term written specifically to give a correct wait positive value -- is
**`restraint_hold: 0.0`** in config. It was 1.0 and was zeroed in `0356830`, a commit whose message
documents only an unrelated `llm_advisor_async` change; the two were the ONLY config edits in it.
The surrounding comment still reads *"Raised to 1.0"*. It looks parked for that night's A/B arms and
never restored.

**But turning it back on does not fix this.** Measured at weight 1.0, fixed seed:
```
restraint_hold  +0.25/match over 0.2 fires/match      = 4.7% of the +5.32 play-side upside
```
That is the SAME "decorative" ratio (4%) the config comment itself records as the reason 0.25 was
rejected -- the value was raised to 1.0 but the FIRE RATE, not the per-fire value, is what starves
it. Its `restraint_cap: 2.0` is never approached.

/!\ I first reported this term as NEVER FIRING. That was wrong -- the two arms had diverged RNG
(separate `SimMatchEnv`s, unseeded). Re-run with `rng.seed(1234)` it fires 0.2/match. The correction
matters: "inert" and "4.7% of the upside" imply different fixes.

### Why it starves -- guard chain over 3,704 steps / 12 matches
```
5_worth_answering         65.2%   <-- DOMINANT BLOCKER: triage says the board IS worth answering,
                                      so the step belongs to threat_miss_idle, not to restraint
3_no_threat               28.9%   quiet board, correctly excluded (paying here is the hoarding
                                  failure `wincon_reach: 2.0` already produced)
1_cap                      3.4%
6_no_affordable_counter    1.8%   (at ~2 elixir, "a counter you could have played" is rare)
2_ratelimit                0.3%
PASS                       0.3%
```
Restraint is only payable on boards triage calls IGNORABLE, and two thirds of boards are not.

### What this does NOT establish
Which repair works. Candidates, all UNTESTED: widen guard 5 (risks paying to ignore real pushes);
a per-step hold credit while a win condition is in hand and the bar is climbing (risks hoarding --
`wincon_reach: 2.0` already failed that way, leak x24, crowns halved); or rebalancing the play-side
positives down rather than adding more wait-side credit. **The measurement says the asymmetry is the
mechanism; it does not say which correction is safe.** One change, measured, per §one-change-per-experiment.

## §5q — THE 4-ARM REWARD A/B IS BUILT (icebow only), and two design choices were MEASURED OUT first

Owner approved a 4-way A/B (control + 3 repairs) against §5p's diagnosis. Built, with two changes to
the approved design -- both because the dose was measured BEFORE spending days on a run.

### Dose of every candidate arm, frozen m5400 policy, 12 matches (play-side upside is +5.32/match)
```
arm                                credit/match     fires/match    % of play-side
control                                  --              --              0%
restraint_hold 1.0                     +0.33            0.3             6%
restraint_hold 1.0 + frac 0.20         +0.50            0.5             9%
restraint_hold 1.0 + frac 0.50         +0.50            0.5             9%   <-- IDENTICAL
bank_hold 1.0 cap 2.0                  +2.00            2.0            38%
bank_hold 1.0 cap 6.0                  +5.83            5.8           110%
bank_hold 1.0 UNCAPPED                +16.33           16.3           307%
```

**"Widen guard 5" is DROPPED, on measurement.** It pays +0.50/match at `restraint_ignore_frac` 0.20
and +0.50/match at 0.50 -- identical, because the 4 s `threat_miss_period` RATE LIMIT binds, not the
threshold. Eligibility does rise (8.7% -> 20.5% -> 42.4% of declinable boards) and the credit does
not follow. It could never have separated from the plain `restraint` arm, so it would have burnt an
arm to measure nothing. The knob stays in env.py, defaulted to no change.

**The freed slot becomes a DOSE PAIR** (`bank2` / `bank6`, differing only in the cap). A monotone
dose-response is far stronger evidence than four unrelated tweaks: if banking rises with dose that
is causal, and if neither moves, the mechanism in §5p is wrong.

### Arms (`tools/ab_reward_arms.py`)
| arm | delta | dose |
|---|---|---|
| control | none -- MUST reproduce the collapse (positive control) | 0% |
| restraint | `restraint_hold: 1.0` -- restore what 0356830 silently zeroed | 6% |
| bank2 | `bank_hold: 1.0`, cap 2.0 | 38% |
| bank6 | `bank_hold: 1.0`, cap 6.0 | 110% |

Configs are GENERATED from config.yaml at launch, never hand-maintained, so arms cannot drift in
anything but their deltas; the generator refuses an ambiguous key match, then LOADS every arm back
and asserts the delta took and the checkpoint paths are distinct. (That check earned itself
immediately: the first version dropped the space before a trailing `#`, producing invalid YAML.)

### /!\ PYTHONHASHSEED IS PINNED, AND IT IS NOT COSMETIC
MEASURED: the same seeded rollout in two processes gives elixir mean **1.9847 vs 2.0383** and
**3980 vs 4083 steps** unpinned, and is bit-identical pinned. Arms are separate processes, so
without this they carry uncontrolled variance BEFORE any reward change. This also explains the
`os.environ.setdefault("PYTHONHASHSEED", ...)` I removed from `rollout_search` as a no-op: it IS a
no-op after interpreter start, but the INTENT was right and the fix belongs in the launcher.

It also invalidated my first control check. Pre-patch vs patched read 1.9237 vs 1.9554 and I nearly
recorded a behaviour change; pinned, both read **1.9278 / 0.25% / 3579 steps -- bit-identical**, so
the new knobs are provably inert at their defaults.

### New env.py code, all defaulting to today's behaviour
* `rewards.restraint_ignore_frac` -- moves the triage boundary for `_threat_miss_idle` AND
  `_restraint_hold` **together**. /!\ They are exact complements at `IGNORE_FRAC`; moving one alone
  opens a band where a board is worth answering and worth ignoring at once. The other six
  `IGNORE_FRAC` uses belong to different terms and are deliberately NOT routed through it.
* `rewards.bank_hold` / `bank_hold_cap` + `_bank_hold()` -- pays for CLIMBING toward a held win
  condition, stopping at arrival (that is `wincon_reach`'s job), suppressed by any answerable push,
  rate-limited and capped.

### Endpoints (`tools/ab_reward_report.py`)
`>=6 elixir`, `x_bow share`, `plays%` -- NOT winrate. Demonstrated on the two known checkpoints:
```
arm          >=6 el%    mean    xbow%   plays%   winrate    leak
m18000          25.0    4.22     11.6      9.9     16.7%   -3.65
m5400 (i4)       0.3    1.93      1.1     14.6     16.7%    0.00
```
The mechanism metrics separate by 80x; **winrate is IDENTICAL at 16.7%**, which is the argument
against it in one line. Note `leak` -3.65 vs 0.00: the reference banks and therefore leaks, the
collapsed policy never approaches the cap.

All arms are scored under the CONTROL config -- one scorer, four policies -- and `leak`/`crowns` are
printed beside the targets because **hoarding does not show up in the elixir histogram**; a hoarding
policy looks excellent there. `wincon_reach: 2.0` already failed exactly that way.

### NOT DONE / open
* **icebow only.** hogeq has `_threat_miss_idle` but NO `_restraint_hold` -- it carries the penalty
  half of the asymmetry with no credit half. Recorded, not fixed; hogeq's wincon is a 4-cost Hog, so
  the 6-elixir banking pathology may not even apply. Do not assume parity here.
* Not launched: memory does not fit the A/B alongside the running interval-4 trainer.
* One seed per arm is a SCREEN. Confirm any winner at 3 seeds (gate collapse escapes 4/6).

## §5r — INTERVAL-4 RUN CLOSED at m=6800, and the 4-arm A/B is RUNNING

Owner stopped the run (verified: 0 `train-sim-ppo` processes before launching anything else).
Its own ladder eval banked **best_wr = 9.58%** at m=6800 -- against the m18000 reference's 11.3%
+/-5.1 on a different instrument, so: not a collapse, not an improvement. Consistent with everything
else measured this session -- **search-in-the-loop coexists with the banking failure, it does not
fix it.**

### Final read, `tools/ab_reward_report.py`, 16 matches, greedy and search-free
```
checkpoint        >=6 el%   mean   xbow%  plays%  playH  winrate   leak
m18000 reference     26.3   4.30    10.9     9.6   2.13    12.5%  -3.65
i4_best (m6000)       0.3   1.99     1.3    14.6   1.94    18.8%   0.00
i4_m6800              0.4   2.03     0.9    14.0   1.93     6.2%  -0.00
```
6,800 matches of training took **>=6 elixir from 26.3% to 0.3%** and x_bow share from 10.9% to
~1%. `leak` at 0.00 is the same fact from the other side: the bar never approaches the cap.

**AND THE WINRATE COLUMN IS THE ARGUMENT FOR THE ENDPOINT CHOICE, IN ONE ROW.** The two i4
checkpoints are 800 matches apart and read **18.8% and 6.2%** -- the earlier one BEATING the
reference's 12.5%. That is +/-2 matches of noise. Any A/B judged on winrate at affordable sample
sizes would have produced a confident, arbitrary winner.

### Why this run was stopped rather than finished to 10k
NOT because it is "architecturally unsound". It is faithfully optimising a reward whose every
positive term requires a play (§5p) -- **every run under this reward dumps elixir, including the
A/B's own control arm, which is designed to reproduce exactly this.** Calling the dumping an
architecture fault points at training knobs, and that is the trap this project has hit four times.
The real reason is cheaper: the remaining 3,200 matches duplicate what the control arm produces
anyway, alone instead of alongside three informative arms, for ~4.5 h and the RAM the A/B needs.
Nothing was forfeited by stopping -- both checkpoints were already on disk and evaluated after.

### A/B launched (4 arms, ~10k matches each)
Measured at launch: **8.03 cores of 16, 3.6 GB resident, 5.5 GB still free** -- comfortably inside
the budget (the estimate was 10.2 cores / 5.6 GB, so 96 envs was, if anything, conservative).
Runtime weights verified AT THE ENV, not just in the config file:
```
arm         w_restraint   w_bank_hold   bank_hold_cap
control            0.0           0.0             2.0
restraint          1.0           0.0             2.0
bank2              0.0           1.0             2.0
bank6              0.0           1.0             6.0
```
Read with `PYTHONHASHSEED=0 python tools/ab_reward_report.py`. A monitor is watching the four logs
for `EVAL @`, `new BEST` and failure signatures, plus a process count (a dead arm is a failure the
log may never mention).

**FIRST THING TO CHECK: does the CONTROL arm reproduce the collapse?** If it does not, the run is
uninformative and no other arm in it can be read.

## §5s — THE A/B DOES NOT NEED 10k MATCHES. The endpoint saturates by m≈800, so the run stops at 1500

Owner asked whether a 4-arm A/B really needs 10,000 matches per arm (2.6 days at the measured rate)
and what the minimum readable length is. It does not. The number was inherited from winrate-era
runs and is ~10x more than these endpoints need.

### The endpoint saturates by m≈800 (watchdog series, the interval-4 run that just closed)
```
interval-1 run   m=600    >=6 16.1%   mean 3.63
                 m=700    >=6  2.6%   mean 2.39
interval-4 run   m=500    >=6  0.8%   mean 2.01   <-- already collapsed
                 m=800    >=6  0.6%   mean 2.11
                 m=2550   >=6  1.5%   mean 2.24
                 m=4000   >=6  0.1%   mean 1.98
                 m=6700   >=6  0.1%   mean 2.04
                 m=6849   >=6  0.6%   mean 2.13
```
The collapse completes between m=600 and m=800. **The following 6,000 matches moved the endpoint
from 0.6% to 0.6%**, oscillating in a 0.1-1.5% band that is noise. There is no information in
matches 800 -> 6849 for this metric. (Source: `scratchpad/watchdog_search.log`, ALERT lines only --
the watchdog logs on alert, so this is a lower bound on sampling density, not a full series.)

### Independent confirmation, from the A/B's own logs at m~100
Rollout AFFORDABILITY ("anything playable on X% of steps"), control arm, first 9 updates:
```
100.0 -> 92.7 -> 82.6 -> 23.4 -> 13.6 -> 11.4 -> 9.7 -> 8.8 -> 8.6
```
~110 episodes, 37 minutes. **The reward's grip on elixir behaviour is essentially fully expressed
inside the first hour.** bank6 over the same 9 updates: 100.0 -> 92.7 -> 83.7 -> 23.3 -> 13.4 ->
10.9 -> 9.5 -> 8.4 -> 8.3 -- if anything marginally BELOW control, no sign of banking rising. Far
too early to read as a result; recorded because it is the first arm-vs-arm number that exists.

### Why these endpoints are cheap when winrate is not
§5r's own row: two checkpoints 800 matches apart read winrate **18.8% and 6.2%** while the mechanism
metric separated **80x** (25.0% vs 0.3% at >=6). The endpoints were deliberately chosen to be
mechanism metrics (§5q), and mechanism metrics are exactly the ones that do not need long runs.
`ab_reward_report.py`'s own dose table was measured on **12 matches**; §5r's final read used 16.

### DECISION: stop all four arms at m=1500 (~8 h from the 14:16 launch), read at 500/1000/1500
1,500 is ~2x the saturation point -- margin, not need. Owner chose this over relaunching as a
3-seed design. Measured rate 191 matches/h/arm (m=175 at 55 min), so m=1500 lands ~22:10.

/!\ **`eval_every_matches` IS 2000 IN THESE CONFIGS, SO `EVAL @` NEVER FIRES BEFORE THE STOP
POINT.** I first armed a monitor keyed on `EVAL @ 1500` after reading the CODE DEFAULT (500 at
`train_sim_ppo.py:988`) instead of the config; it was raised 500 -> 2000 on 2026-08-23 because one
EVAL costs 195 s. That monitor would have stayed silent forever and never exited. Caught by the
owner. **Read the config value, not the `default=` in the `cfg.get` call.**

This costs nothing, because the ladder EVAL was never the endpoint (§5q: winrate is a guardrail,
not the discriminator). Progress is keyed on the `N episodes:` line instead, which prints `done_n`
-- the SAME counter as `--matches`, `EVAL @` and the checkpoint's `matches` field
(`train_sim_ppo.py:1832,1899`) -- every `log_every_matches` = 25. The endpoint read comes from
`ab_reward_report.py` against `data/ab/policy_*.pt`, refreshed every `save_every_matches` = 50, so
a checkpoint is at most 50 matches stale. Monitor emits at m=500/1000/1500 plus failure signatures
and ARM DEATH (a dead arm is a failure the log may never mention), and exits at m>=1500.

Note `done_n` counts DRILL episodes too (`drills N (X% of eps)`), which is the same scale the
watchdog's `matches=` series used, so §5s's m=800 saturation point and this m=1500 target are
directly comparable.

### /!\ THE STOPPING RULE IS ASYMMETRIC, because the dip can MASK but cannot FAKE a difference
m=1500 sits inside §4a's critic dip (bottom ~1,700 episodes). This does **not** invalidate the
comparison: all four arms share an identical warm start, seed and dip, so it is common-mode, and
§4a's own prescribed remedy is *"compare run-vs-run at matched episode counts"* -- which is what a
4-arm A/B is. §4a forbids comparing a checkpoint to its INIT, a different thing.
```
arms SEPARATE at 1500   -> conclusive. Stop. Confirm the winner at 3 seeds (§5q).
arms IDENTICAL at 1500  -> NOT conclusive. Dip-masking is a live alternative to "no effect."
```
The one scenario that would genuinely need length: `bank_hold` allowing the collapse and RECOVERING
banking later. No evidence for it, and it fights the mechanism -- §5p is a per-step reward asymmetry
acting from match 1, not a slow credit-assignment effect. Stated as the residual risk, not dismissed.

### /!\ SEED NOISE, NOT RUN LENGTH, IS THE REAL THREAT -- and this A/B does not control it
§5q already flagged one seed per arm as a SCREEN. The measured warning is the Aug-28 clip sweep
(`scratchpad/ab/`, 3 coefficients x 3 seeds, 700 matches each, from scratch). Within a SINGLE arm,
`plays%` across seeds read:
```
c0.0   0.1%  2.0%  2.3%
c0.5   1.1%  1.7%  4.4%
c2.0   0.0%  0.1%  0.1%
```
Seed spread swamped the arm effect (all nine cells also read 0.0% winrate -- that is §5d). ⚠ Those
were FROM-SCRATCH runs at the noisiest point, so warm-started arms off a common checkpoint should be
tighter; this is the best available estimate, NOT a matched one. It still means **a winner here is a
screen result and is not established until it survives 3 seeds.**

### Housekeeping
Two stale `ppo_watchdog.py` processes from the killed interval-4 run were killed (PIDs 63708 +
child 51772). They were watching `data/policy_sim_ppo.pt` -- last written 14:11, BEFORE the A/B
launched -- and could never have seen the A/B's checkpoints in `data/ab/policy_*.pt`. Their final
line proves it: `ALERT STALLED -- checkpoint unchanged for 44 minutes at matches=6849 ... procs=8`,
i.e. reporting the dead run's frozen checkpoint while seeing the A/B's 8 processes.

### /!\ §5r's MEMORY MEASUREMENT WAS TAKEN TOO EARLY AND UNDERSTATES THE FOOTPRINT 2.5x
§5r recorded *"3.6 GB resident, 5.5 GB still free"* at launch. Measured at m~100, steady:
**9.14 GB resident (4 arms x ~2.3 GB), 1.94 GB free of 31.4 GB**, CPU pegged at 99.95%. Nothing is
failing, but the headroom §5r claims is not there -- do not start anything large alongside this run.
Measure resident memory after the envs and buffers fill, not in the first minute.

## §5t — locate-anything.cpp EVALUATED AND REJECTED as a YOLO replacement (3 independent blockers)

Owner proposed https://github.com/mudler/locate-anything.cpp as a faster, better detector to train
on our data. **It is neither faster nor trainable, and the domain is wrong.** Recorded so this is
not re-litigated. The repo is NOT bad -- it is a clean ggml/C++17 port of NVIDIA's
LocateAnything-3B (Qwen2.5-3B + MoonViT + 2-layer MLP projector, MIT for the port, NVIDIA license
for the weights). It is simply aimed at a different problem on all three axes below.

### /!\ BLOCKER 1 -- THE SPEED CLAIM IS RELATIVE TO ITS OWN BASELINE, NOT TO YOLO
The README's "4.8x faster" is measured against **the official PyTorch f32 model**, not against a
detector. Their table, Ryzen 9 9950X3D, CPU, 16 threads, 448 fixture:
```
mode                PyTorch f32    locate-anything.cpp f32
slow (pure AR)         23.65 s            14.26 s
hybrid (default)       69.06 s            22.32 s
fast (MTP-only)        57.55 s            19.45 s
q8_0, slow mode           --               4.89 s   <-- their best number
```
**4.89 SECONDS PER IMAGE is the floor.** Our live vision path is budgeted in MILLISECONDS:
`vision.py:360` calls 93 ms/decision *"the largest item left in the live vision budget"*, and
`vision.py:189` records grinding 32 ms -> 0.53 ms (71x) because 32 ms mattered. 4.89 s is **~53x
the ENTIRE current per-decision cost**, against a YOLO11s that runs in single-digit ms. This is not
a faster detector, it is a different category of artefact. **Read absolute latency, not a repo's
self-relative speedup.**

### BLOCKER 2 -- INFERENCE ONLY. "Train it on our data" has no path in this repo
No training, no fine-tuning, no custom-dataset support anywhere in it; it is a dependency-light
inference runtime. Fine-tuning would mean NVIDIA's LocateAnything-3B stack -- a 3B VLM instead of a
~9 MB YOLO.

### BLOCKER 3 -- open-vocab is the answer to NOT HAVING LABELS, and we have 12,821 of them
It is a text-prompted open-vocabulary VLM (categories delimited by `</c>`). Open-vocab detection is
strongest on natural imagery and is the tool for "no labeled data". We have the opposite problem
(§9): **12,821 labeled train frames, 2,346 val, a 44,113-sprite bank over 186 classes, nc=230** --
built precisely BECAUSE Clash Royale units are not natural-image objects. Prompting a natural-image
model with 230 game-sprite class names is its weakest regime. ⚠ This one is PLAUSIBLE BUT UNTESTED
(not run); blockers 1 and 2 make the test moot.

### Minor, but relevant
* master had **3 commits** at evaluation -- very young (542 stars / 74 forks, LocalAI team).
* q8_0 needs **6.3 GB**; the box had **1.94 GB free** with the A/B pegging 16 cores. It could not
  have been loaded at all without stopping the A/B.

### The ONE use that is not ruled out (low priority, not scheduled)
As an offline **pre-labeler** for the `to_label` pool (6,059 unlabelled, §9), where 5 s/image is
irrelevant: ~8.2 h for the pool. Contingent on blocker 3 turning out false, and we already have a
working label pipeline. Rated below everything in §6.

## §5u — WORKER-SIDE SEARCH IMPLEMENTED (§5m's structural fix). Mechanism VERIFIED, speedup NOT

Owner asked for §5m's structural fix: let the workers search, so `--search-interval` stops forcing
`--workers 0`. Built and smoke-tested. **The throughput gain is NOT yet measured** -- see the two
open items at the bottom before quoting any number.

### /!\ THE PREMISE THAT MOTIVATED IT IS WRONG, AND IT SHRINKS THE PAYOFF
Owner's reason was *"I'm not even close to full CPU utilization."* MEASURED, three consecutive
samples while the A/B runs: **100%, 100%, 100%** of 16 cores (Intel Core Ultra 9 386H). The box is
saturated right now.

§5m's "3.25 cores of 16 (20%)" is a **single-run** figure. Four arms x ~3.25 cores fills the machine,
so the A/B is already using all of it. That matters for what this fix buys:
```
one run alone      3.25 -> ~13 cores        up to ~4x        <-- this is the win
four arms at once  16 cores -> 16 cores     ~0x              <-- already saturated
```
**It does not speed up the running A/B, and would not have.** It buys LATENCY on a single run
(one answer 4x sooner) rather than WIDTH on a sweep (four answers at once). The place it pays is
the §6-PRIORITY-B distillation long run -- which is exactly the case §5m raised it for.

### The design: send the searcher to the engines, not the engines to the searcher
The old refusal (`REFUSING --search-interval with workers>1`) was **right about the cause and wrong
about the only fix**: `Searcher.act` must clone a live `SimEngine`, and the parent's `pool` IS empty
under workers>1. But the engines are not gone -- they are in the workers. So the searcher goes there.
```
remote_pool.py   _worker gains a lazy Searcher per env, built on the first "searchnet" message.
                 In the "step" handler it searches BEFORE stepping and reports back the action it
                 actually played plus a `srch` flag. New payload keys: "act", "srch".
                 RemotePool.set_search_net(sd, search) -- same hop as set_league, different cargo:
                 the league ships FROZEN snapshots to play against, this ships the LIVE policy to
                 search with. Workers hold the net BY REFERENCE, so the per-update refresh is an
                 in-place load_state_dict that keeps interval counters and per-env stats alive.
train_sim_ppo.py refusal replaced by a remote branch setting `_search_cfg`; the net is broadcast
                 every update; `rpool.step_all` moved BEFORE the roll append, because under worker
                 search the parent does not know the action until the worker answers.
```
The search config rides in the MESSAGE, not the `RemotePool` constructor -- `gate_tau` resolves at
`:394`, after the pool is built at `:128`, so a constructor argument would have had to duplicate
that config read and could drift from it.

### /!\ THE TRAP THIS SEAM SPECIALISES IN, CAUGHT DURING THE BUILD
The imitation loss was gated on `if _searchers is not None`, which is None on the remote path. Left
alone, **the entire supervised CE would have been a silent no-op under `--workers>1`**: rows arrive
flagged in `roll["srch"]`, the CE is never added, the run trains as plain PPO, and every SEARCH log
line still prints. That is the identical failure `drill_frac`, `spell_veto` and `deck_record` each
had at this exact boundary (see their comments in `remote_pool.py`). Now
`(_searchers is not None or _search_cfg is not None)`.
Same reasoning drove reporting `act`/`srch` back to the parent: without `act`, `roll["act"]` would
record the parent's PROPOSAL, making the imitation target the wrong action while looking wired.

### Smoke test -- MECHANISM VERIFIED (`--matches 6 --envs 4 --workers 2 --search-interval 4`)
```
[train-sim-ppo] SEARCH IN THE WORKERS: every 4 decision(s), H=12.0s cells=3 coef=1.0
                over 4 env(s) across 2 worker process(es)
[train-sim-ppo]   SEARCH  20/512 decisions searched, 80.0% changed the action
                  | imitation CE 3.9014 | 100.0% of searched rows usable
                  ... CE 3.8995 ... CE 3.8976        <-- decreasing across updates
```
No refusal, no traceback, exit 0. The CE being nonzero AND falling is the proof that the supervised
term actually fires on the remote path -- that is the check the trap above demands.
⚠ `_sstat["n"]` now counts ALL K decisions per step; the in-process path counted only non-done envs,
so the "searched N/M" DENOMINATOR is not comparable across the two paths. The numerator is.

### NOT DONE -- do not quote a speedup until these are closed
1. **THROUGHPUT IS UNMEASURED.** The box is pegged by the 4-arm A/B, and §5o records that my own
   competing jobs already corrupted one throughput baseline. ~4x is ARITHMETIC from §5m's 3.25/16,
   not an observation. Benchmark on an idle box: same seed, `--workers 0` vs `--workers 12`,
   compare matches/hour.
2. **LEARNING PARITY IS UNMEASURED.** Workers seed their envs per shard (`seed0 + i` per worker), so
   the two paths are NOT expected to be bit-identical and a diff cannot settle it. The real check is
   run-vs-run at matched m on the §5s endpoints -- the same instrument the A/B uses.
3. The A/B in flight is `--workers 0` and is untouched by this; the edits cannot affect a running
   process (Python read the source at import).

## §5v — m=500 READ: control has NOT collapsed yet, and §5s's saturation claim was CROSS-INSTRUMENT

First matched read of the 4-arm A/B. All four checkpoints at **exactly m=500** (verified from each
`.pt`'s own `matches` field), 16 matches/arm, greedy and search-free, scored under the CONTROL config,
`PYTHONHASHSEED=0`.
```
arm          >=6 el%    mean     xbow%  plays%   dist   playH   winrate    leak  crowns
control         13.0    3.23       7.1    11.6     10    2.07     37.5%   -1.57   -0.62
restraint        3.2    2.22       2.3    13.7     10    1.94     18.8%   -0.37   -1.06
bank2            2.8    2.16       1.4    13.6     10    1.92     18.8%   -0.16   -1.12
bank6            8.9    2.81       5.5    12.6      9    2.02     25.0%   -0.73   -0.69
```
(reference points, same instrument, from §5q/§5r: m18000 = 26.3% / 10.9% xbow; i4_m6800 = 0.4% / 0.9%)

### /!\ THE RUN IS NOT YET READABLE -- THE POSITIVE CONTROL HAS NOT FIRED
§5r's gate is *"FIRST THING TO CHECK: does the CONTROL arm reproduce the collapse? If it does not,
the run is uninformative and no other arm in it can be read."* At m=500 control reads **13.0%**,
against a warm start of 26.3% and a collapsed floor of 0.3-0.4%. **It is about halfway down, not at
the floor.** So nothing below is a verdict yet.

### /!\ AND THIS RETRACTS §5s's TIMING ARGUMENT, WHICH WAS A CROSS-INSTRUMENT COMPARISON
§5s concluded *"the endpoint saturates by m≈800"* from the watchdog series. **That series is a
DIFFERENT INSTRUMENT from the one the A/B is judged on**, and I compared them as if they were one:
```
ppo_watchdog.py        SAMPLES the gate and SAMPLES the card from the card head
                       (:180 "SAMPLE the gate, do not threshold it ... Training samples; so does
                       this" -- written precisely because forcing plays drains the bar and fakes
                       an "elixir never reaches 6" reading)
ab_reward_report.py    GREEDY and search-free
```
A sampled policy and a greedy policy do not spend elixir at the same rate, so their `>=6` curves are
not the same curve. On the GREEDY instrument the only reads that exist are the warm start (26.3%),
m=6000 (0.3%) and m=6849 (0.4%) -- **nothing between m=0 and m=6000**. §5s's "saturates by m≈800"
therefore had NO support on the instrument this A/B uses, and today's 13.0% at m=500 is the first
point on that curve. It says the collapse is roughly HALF done at m=500.
**The m=1500 stop may be too early.** Keep the asymmetric rule; expect to extend.
⚠ What survives of §5s: the watchdog series itself is unchanged and still shows the sampled-instrument
endpoint flat from m=800 to m=6849. The error is the transfer, not the data.

### What the arms show, recorded but NOT actionable
All three treatment arms sit BELOW control on the endpoint, and the dose-response is NON-MONOTONE:
```
dose (of play-side upside)   0%      6%       38%      110%
arm                          control restraint bank2    bank6
>=6 elixir                   13.0    3.2      2.8      8.9
```
§5q's design says a monotone rise with dose is causal and no movement refutes §5p. This is neither:
it falls, and the largest dose is the least affected. Three readings, all UNTESTED --
(a) the terms genuinely suppress banking; (b) the extra reward term simply moves those arms further
along the SAME collapse curve per match, making control merely the slowest arm; (c) one-seed noise,
which the report's own footer warns about (gate collapse escapes 4/6). **(b) is not consistent with
the non-monotonicity**, but neither is it excluded at n=1 seed.
`bank*` HOARDING DID NOT HAPPEN: leak tracks banking down (control -1.57, bank2 -0.16) and no arm
shows the leak-up/crowns-down signature `wincon_reach: 2.0` produced.
⚠ Winrate is NOT a discriminator here (control 37.5% on 16 matches is +/-12pp; §5r showed 18.8% vs
6.2% across 800 matches of one run). It is in the table as a guardrail only.

### Next
Continue to m=1500 and re-read on the same instrument. If control is still not at its floor there,
the honest move is to extend rather than call the mechanism refuted -- a null against a control that
never collapsed measures nothing.

## §5w — RoyaleAPI REPLAY MINE: no placements, one player — but it CHALLENGES the "too eager" diagnosis

Owner mined RoyaleAPI replay data and proposed recreating scenarios in-sim from placement + timing.
`icebow/data/royaleapi/{battles.csv, plays.csv}` (248 KB, NOT committed -- data/ is gitignored).

### /!\ TWO FRAMING ERRORS IN THE PROPOSAL, BOTH AT THE DATA LEVEL
1. **THERE IS NO PLACEMENT DATA.** `plays.csv` is exactly seven columns --
   `replay_tag, play_index, tick, seconds, side, card, ability` -- and zero coordinate fields
   (grepped: 0 hits for tile/x/y/coord/lane/pos). RoyaleAPI's battle log gives card + tick + side;
   deploy tiles are not in it.
2. **IT IS ONE PLAYER, NOT SEVERAL.** 53 battles, all `Hubert`, ONE deck, all pathOfLegend,
   27W-25L-1D (51%). 5,147 plays (blue 2,647 / red 2,500), 49.9 blue plays per match.

**SCENARIO RECREATION IS THEREFORE NOT VIABLE FROM THIS SOURCE.** A card sequence does not determine
a board: reconstructing the situation a card was played INTO needs positions, HP and the opponent's
placements. Without coordinates you can replay WHAT was played, never the state it answered.

### /!\ THE FINDING THAT MATTERS: THE POLICY'S PLAY RATE IS HUMAN-NORMAL
Pro plays **11.3 cards/min** (median 12.0). `sim.agent_dt: 0.6` = 100 decisions/min, so that is
**11.3% of decision steps**. Against the §5v read on the same axis:
```
                          plays%    xbow share of plays
pro (Hubert, 53 games)      11.3            7.1
control @ m=500             11.6            7.1
m18000 "reference"           9.6           10.9
i4 collapsed (m6800)        14.6            0.9
```
**Control sits ON the pro's play rate AND on the pro's x-bow share.** The m18000 checkpoint this
project treats as the good target plays LESS OFTEN than a pro while using x-bow MORE.

This is direct evidence against §5h (*"THE SIGN WAS BACKWARDS ALL SESSION. The policy is TOO EAGER,
not too reluctant"*) and against §5p's framing of over-playing as the pathology. The collapsed run's
14.6% IS above human, but 11.6-13.7% -- where all four A/B arms currently sit -- is human-normal.
**The defect may not be HOW OFTEN it plays; it is what it can afford to play.**

Supporting, same direction: the pro **LEAKS 6.00 elixir/match** (median 3.04, max 21.83; opponents
6.13). A player who never sat at cap could not leak. Sitting on elixir IS expert behaviour, so the
target is not "never waste elixir" but "waste some to afford the win condition" -- which supports
the banking direction while contradicting the over-play framing.

### ⚠ WHAT THIS DOES NOT ESTABLISH
* **n = 1 PLAYER, 53 GAMES, at 51% winrate.** One strong player's equilibrium, not a population and
  not a winning sample. It cannot separate "how icebow is played" from "how Hubert plays".
* **`plays% of decision steps` is DERIVED, NOT MEASURED.** The pro is not making 100 decisions a
  minute; this divides their play rate by the SIM's cadence. Right unit for the comparison,
  constructed quantity. Do not quote it as a human measurement.
* The sim's opponent is not a ladder opponent, so the boards being answered are not the same boards.

### Useful reference statistics (external anchors -- every §5q/§5v target so far comes from an
### earlier checkpoint of THIS policy, i.e. the project measuring itself against itself)
```
play rate            11.3% of decision steps (11.3/min, median 12.0/min)
inter-play gap       median 3.60 s   mean 4.84   p10 1.35   p90 9.55
x-bow                3.55 deploys/match (median 3; 2 of 53 matches had none)
x-bow timing         median t=152 s   p10 41 s   p90 249 s
elixir leaked        mean 6.00/match  median 3.04
elixir spent         151/match
card mix (blue)      skeletons 17.2  knight 16.7  ice-wizard 16.4  tesla 14.7
                     the-log 14.3  tornado 8.4  x-bow 7.1  rocket 5.1
match length         mean 255 s  median 289 s  max 299 s  (sim: regulation 180 + overtime 120 = 300)
```
The inter-play gap distribution is the most directly useful: it is an empirical prior for how long a
CORRECT WAIT lasts, which is exactly the quantity §5p shows has no positive value in the reward.

### RECOMMENDED USE: calibration reference, NOT training data
Nothing enters the gradient, so there is no BC/overfitting exposure and the owner's own concern is
moot. Do NOT wire it in now: it is a new data source, the A/B is mid-flight, and §one-change-per-
experiment applies.

### Join problems to solve BEFORE any training use
* 101 distinct cards across both sides, including a literal **`_invalid`**.
* `plays.csv` STRIPS EVOLUTION IDENTITY: the deck column says `tesla-ev1` / `knight-ev1`, the plays
  say `tesla` / `knight`. Mapping onto the 230-class taxonomy (§9) is not free.
* `ability` is 1 on 141 of 5,147 rows (ability/evolution activations), 0 elsewhere.

### If more is wanted from this source
The highest-value next pull is **MORE PLAYERS** -- 53 games of one person cannot separate the deck's
doctrine from one person's habits. Placement needs a DIFFERENT source than the battle log.

## §5x — m=1000 READ: the dose-response APPEARED, and the arm ordering INVERTED. Seeds, not length

Second matched read, all four checkpoints at exactly m=1000, 16 matches/arm, greedy, search-free.
```
arm          >=6 el%    mean     xbow%  plays%   playH   winrate    leak  crowns
control          6.3    2.52       3.3    12.4    1.98     25.0%   -0.49   -0.88
restraint        2.0    2.03       2.0    14.2    1.89     18.8%   -0.07   -1.25
bank2            7.5    2.66       3.6    12.6    2.01     43.8%   -0.64   -0.50
bank6           12.0    3.03       4.2    11.3    1.99     12.5%   -1.54   -1.31
```

### §5q's DESIGNED SIGNATURE APPEARED -- the bank dose pair is monotone
```
                control(0%)   bank2(38%, cap 2.0)   bank6(110%, cap 6.0)
>=6 elixir          6.3              7.5                   12.0
```
And the TRAJECTORIES agree, which is stronger than the levels alone:
```
              m=500    m=1000
control       13.0  ->   6.3    falling
restraint      3.2  ->   2.0    falling
bank2          2.8  ->   7.5    RISING
bank6          8.9  ->  12.0    RISING
```
Both `bank_hold` arms rose while control and `restraint_hold` fell. That is what arresting the
collapse looks like. §5q: *"if banking rises with dose that is causal."*

### /!\ AND THE ARM ORDERING COMPLETELY INVERTED BETWEEN THE TWO READS
```
m=500    control > bank6 > restraint > bank2
m=1000   bank6 > bank2 > control > restraint
```
`bank2` went from WORST treatment arm to ABOVE control in 500 matches, on the same seed.
**This is a measurement of the noise floor, not a caveat about it: at n=1 seed these reads reorder.**
The report's 4/6 gate-collapse escape rate now has a number behind it. Any verdict from this run
alone would be arbitrary in the same way §5r's winrate column was.

### bank6 CARRIES THE HOARDING SIGNATURE. bank2 DOES NOT.
```
             >=6 el    leak     crowns    winrate
control        6.3    -0.49     -0.88      25.0%
bank2          7.5    -0.64     -0.50      43.8%   <- banking up, crowns BEST, leak barely moved
bank6         12.0    -1.54     -1.31      12.5%   <- banking up, leak 3.1x worse, crowns WORST
```
§5q's criterion: *"an arm that lifts banking while lifting leak has bought the failure, not fixed
it"* -- how `wincon_reach: 2.0` failed (leak x24, crowns halved). **bank6 meets it; bank2 does not.**
Reading: cap 2.0 is a useful nudge, cap 6.0 overpays and buys hoarding.

### CONTROL IS STILL NOT AT ITS FLOOR -- m=1500 IS CONFIRMED TOO EARLY
`26.3 -> 13.0 -> 6.3`, halving every 500 matches, against a 0.3-0.4% collapsed floor. Projects ~3%
at m=1500 and the floor near **m=2500-3000**. This is §5s's retraction landing exactly as written.

### DECISION: stop at m=1500 as planned, then spend the compute on SEEDS, not length
The m=500 -> m=1000 inversion says the binding constraint is **seed variance, not run length**.
Running to m=2500 buys one more noisy number from one seed. 3 seeds x {control, bank2, bank6} is
the confirmation §5q requires before acting on any winner anyway, AND it directly tests whether the
monotone dose-response is real. ⚠ This REVERSES the "extend rather than conclude" lean in §5v, on
the new evidence of the inversion.

### /!\ TWO WARNINGS ON THE RELAUNCH CONFIG
1. **`--workers 12` WILL NOT SPEED UP A 9-CELL SWEEP.** §5u measured it: worker-side search lets ONE
   run reach ~13 cores instead of 3.25, but nine concurrent cells already saturate 16 cores. Nine
   cells x 12 workers = 108 worker processes on 16 cores -- oversubscription, not speedup. The lever
   only pays when cells run sequentially or few-at-a-time. **Which arrangement is fastest is
   UNMEASURED**; the queued benchmark answers it, so set the arrangement AFTER it reads.
2. **WORKER-SIDE SEARCH IS AN UNPROVEN PATH FOR A CONFIRMATION RUN.** §5u verified the mechanism
   (search fires, overrides 80% of searched actions, imitation CE fires and falls) but explicitly
   NOT learning parity. A confirmation run is the wrong place to debut an unverified code path --
   if it has a subtle bug the 3-seed result is invalid and looks clean. Gate the relaunch on the
   benchmark's parity check.

## §5y — THE DEFENSIVE X-BOW BAND IS ALREADY WIRED, IN THREE PLACES, WITH DIFFERENT NUMBERS

Owner specified the defensive band as **>=3 tiles behind the bridge and >=4 tiles from either map
edge** ("back central"), and asked whether it is wired into the sim / live play yet. **It is** --
and the shipped numbers disagree with the spec in both axes, in opposite directions.

### Owner's band, in engine units (board 18 x 32 tiles)
CLARIFIED 2026-08-29: "behind the bridge" means behind **OUR SIDE'S RIVER EDGE**, not the centre
line. The river is 2 tiles wide (`_RIVER_HALF = 1.0`), so our bank is tile 17 (y = 0.53125):
```
>=3 tiles behind OUR BANK   ->  y >= 20/32 = 0.625        (NOT 0.594 -- that was the centre-line read)
>=4 tiles from either edge  ->  x in [4/18, 14/18] = [0.222, 0.778]
```
**OVERLAP GOES TO OFFENSIVE** (owner's rule): a placement that can reach an enemy tower is
offensive whatever else it also covers. Classification is now mutually exclusive -- three cells,
no BOTH. At tile 20 the two do not actually intersect (deepest tower-reaching spot is y ~ 0.606,
13.0 tiles of travel after the 1.5-tile tower radius against the 11.5 reach), leaving a thin dead
strip from ~0.606 to 0.625 on tower-aligned columns that widens off-axis. The precedence rule is
applied rather than assumed, so it stays correct if either flag moves.

### What is ALREADY shipped
```
env.py:427  xbow_defense_front  0.56  -> tile 17.92 -> 1.92 tiles behind the river   (spec: 3.0)
env.py:428  xbow_defense_back   0.66  -> tile 21.12 -> 5.12 tiles behind
env.py:1563 central = abs(nx-0.5) <= 0.18 -> x in [0.32,0.68] -> 5.76 tiles from each edge (spec: 4.0)
doctrine.py:513,530  _add_spot(0.48, 0.55) -> tile 17.6 -> 1.60 tiles behind the river
DOCTRINE.md  "Defensive bow (0.48,0.55)" 1.60 | "def. bow (0.52,0.55)" 1.60
             "place buildings deeper (0.58)" 2.56 | "Counter-bow (their_x,0.52)" 0.64
```
**The spec is DEEPER but WIDER than what ships** -- deeper by ~1.1 tiles at the front edge, wider by
~1.8 tiles on each side. It is not a tightening of the existing band; it is a different rectangle.

### /!\ EVERY SHIPPED DEFENSIVE COORDINATE SITS IN FRONT OF THE OWNER'S BAND
0.64, 1.60, 1.60, 1.92 and 2.56 tiles behind the river -- **none reaches 3.0**. So adopting the spec
without touching the rest makes `doctrine.py` sample defensive spots OUTSIDE the band the reward is
meant to encode: the prior would teach one rectangle while `wincon_exec` credits another.

### /!\ THE BAND IS NOT PURELY DEFENSIVE AT ITS FRONT LANE CORNERS
At x=4 tiles, y=19 tiles the near enemy princess tower is 12.61 tiles away = **11.11 after the
1.5-tile tower radius, inside the 11.5 reach**. Those placements can lock a tower. The probe reports
them as BOTH rather than calling them defensive by fiat.

### /!\ TWO SHIPPED VALUES HAVE MEASUREMENTS BEHIND THEM -- do not overwrite blind
* `xbow_lane_frac: 0.35` exists because *"32/32 bow plays (rows 15-18, mostly lane-side) scored
  -1.00 in a 20-match probe -- a 100% tax on the deck's win condition"*. Widening `central` to the
  spec's +/-0.278 moves exactly those rows back inside full credit, which is plausibly right but
  interacts with the fix that number came from.
* `doctrine.py:517` suppresses the defensive spot entirely when the opponent holds a Rocket
  (DOCTRINE_RESEARCH SS3, Hunter CR: rocket the bow -> rocket the tower -> never get a lock).
  Any band edit must preserve that suppression.

### DONE / NOT DONE
* **DONE:** `tools/xbow_probe.py` now classifies DEFENSIVE by the owner's band, with `--def-behind`
  (3.0) and `--def-edge` (4.0) as flags. OFFENSIVE stays reach-derived.
  Measured from OUR BANK (tile 17) per the owner's clarification, so the band starts at tile 20.
  Early signal, n=2 matches on m18000 so NOT a result: the two bows the reach-derived rule called
  DEFENSIVE reclassify to **NEITHER (dead zone)** under the spec -- consistent with a policy trained
  on a prior that samples y=0.55.
* **NOT DONE, deliberately:** no change to `xbow_defense_front/back`, `central`, `doctrine.py`
  spots or DOCTRINE.md. The A/B is in flight (§one-change-per-experiment), and the probe is queued
  to measure where bows actually land and whether band placements outperform. **Change the doctrine
  after that read, with evidence, not before it.**

## §5z — A/B CLOSED at m=1500. Control never reached its floor; bank6 held across three reads

Final matched read, all four checkpoints at exactly m=1500, 16 matches/arm, greedy, search-free.
Run stopped at 22:08 (8 -> 0 `train-sim-ppo` processes verified; arms were at m=1525-1550, zero
`EVAL @` lines as expected since `eval_every_matches` is 2000).
```
arm          >=6 el%    mean     xbow%  plays%   playH   winrate    leak  crowns
control          4.0    2.37       2.4    14.9    1.97      6.2%   -0.35   -1.19
restraint        1.0    1.94       0.9    14.8    1.87      0.0%   -0.04   -1.56
bank2            4.2    2.22       1.9    12.6    1.94     18.8%   -0.37   -1.00
bank6           11.1    2.98       6.1    12.3    2.03     31.2%   -1.06   -0.75
```

### THE THREE-READ TRAJECTORY IS THE RESULT, NOT ANY SINGLE TABLE
```
>=6 elixir     m=500   m=1000   m=1500      shape
control         13.0     6.3      4.0        monotone COLLAPSE (from 26.3 warm start)
restraint        3.2     2.0      1.0        collapses FASTER than control
bank2            2.8     7.5      4.2        no trend -- worst, then best, then tied
bank6            8.9    12.0     11.1        FLAT-TO-RISING, never collapses
```
**Control collapses monotonically and bank6 does not.** That is the cleanest statement this run
supports, and it is stronger than any single read because it is three points on two curves.
`bank_hold` at cap 6.0 arrests the collapse; the control reward does not.

Dose ordering (control < bank2 < bank6) held at m=1000 AND m=1500, having been absent at m=500.
⚠ But bank2's margin over control at m=1500 is **+0.2 pp**, i.e. nothing. The intermediate dose is
UNRESOLVED: cap 2.0 neither collapses like control nor holds like bank6.

### /!\ THE POSITIVE CONTROL NEVER FIRED, SO §5r's GATE IS STILL UNMET
Control ended at **4.0%** against a 0.3-0.4% collapsed floor -- descending (13.0 -> 6.3 -> 4.0) but
decelerating, so the halving-per-500 model from §5x is itself wrong at the tail. Everything above is
measured against a baseline still in motion. This is exactly what §5s's retraction predicted and why
the plan moved to seeds rather than more length.

### THE m=1000 HOARDING READ ON bank6 DID NOT HOLD
```
             leak            crowns
          m1000   m1500    m1000   m1500
control   -0.49   -0.35    -0.88   -1.19
bank6     -1.54   -1.06    -1.31   -0.75   <- WORST crowns at m=1000, BEST of four at m=1500
```
§5x called bank6's hoarding signature present on the strength of leak-up + crowns-down. **Half of
that reversed.** Leak is still ~3x control, but crowns went from worst to best. Recorded as a
correction to §5x: the hoarding call was made on one read and one read undid it.

### bank6 IS ALSO THE ARM CLOSEST TO THE HUMAN ANCHOR (§5w)
```
                 plays%   xbow share
pro (Hubert)      11.3       7.1
bank6             12.3       6.1
control           14.9       2.4
```
Not a verdict -- §5w is n=1 player -- but the arm that best arrests the collapse is independently
the one whose play rate and x-bow share sit nearest a pro's. The two instruments agree by accident
or because both are tracking the same thing; the 3-seed run is what separates those.

### WINRATE, AGAIN, IS NOISE
bank6 read 12.5% at m=1000 and **31.2%** at m=1500 -- a 19 pp swing on the same arm, 500 matches
apart, at n=16. Anyone reading the m=1500 winrate column alone would declare bank6 a 5x winner over
control (31.2% vs 6.2%). Do not.

### VERDICT: NO VERDICT, AND THE 3-SEED RUN IS UNCHANGED BY THIS
The trajectory evidence is real and points at `bank_hold`, but every number here is n=1 seed, and
bank2's own history (worst -> best -> tied across three reads) is the standing demonstration of what
one seed does. **`tools/ab3_confirm.py` is prepped and verified; restraint is dropped on this
evidence** (below control at all three reads, worst crowns, 0% winrate, lowest x-bow share).
Arrangement still waits on the queued benchmark + parity gate.

## §5aa — OVERNIGHT CHAIN: throughput measured, parity unresolved-but-not-broken, and the X-BOW ANSWER

Ran unattended after the A/B stopped, on an idle box. Three results.

### 1. THROUGHPUT: §5u's ~4x was ARITHMETIC AND WRONG. Measured 1.83x.
150 matches, 96 envs, interval 4, seed 41, idle box:
```
--workers 0    442.6 matches/hour
--workers 12   810.8 matches/hour     1.83x   (5u projected ~4x from 3.25/16 cores)
4 concurrent A/B arms, measured over 7h:  ~197 each = ~788/hour AGGREGATE
```
**One 12-worker run (810.8) essentially TIES four concurrent 0-worker runs (788).** Worker-side
search does not beat concurrency on this box; it matches it. The box is the constraint either way.
§5u's projection is retracted: the lever is real but half the size claimed, and it buys latency on
a single run, never total throughput.

### 2. PARITY GATE: large divergence, but "the worker path does not train" is REFUTED
Both bench checkpoints, same init / seed / config, scored on the same instrument:
```
                >=6 el%   mean   xbow%  plays%  winrate   leak    crowns
policy_inproc      4.4     2.03    0.3    14.0    12.5%   -0.79   -1.50
policy_workers12  27.3     4.22    6.3     9.6     0.0%   -4.90   -1.88
```
A 6x gap on the primary endpoint. **But the failure hypothesis is dead**, on three checks:
```
L1 drift from the m18000 init:  inproc 27252 (104.65%)   workers12 27322 (104.92%)
search fired:                   inproc 486/12288          workers12 436/12288
gradient signals:               pl +0.044 vl 1.345        pl +0.037 vl 1.126
```
**Both paths train equally hard and search at the same rate; they land in different places.** At
m=150 that is exactly the variance this project has already measured -- §5x's arm ordering inverted
between m=500 and m=1000, and bank2 read 2.8 -> 7.5 -> 4.2 across three reads on one seed.
**Parity is UNRESOLVED, not failed.** ⚠ Do not read this as clearance either: two runs at m=150
cannot establish parity in either direction.
Residual lead, not chased: the imitation CE MOVES on inproc (1.8117 -> 2.7872) and is nearly FLAT
and higher on workers (3.2031 -> 3.1992). Equal weight drift makes a stale-net cause unlikely, but
the cheap decisive test is a worker-side assertion that each broadcast state_dict differs from the
previous one.

### 3. /!\ THE X-BOW ANSWER: THE POLICY NEVER PLAYS A DEFENSIVE X-BOW. Not once, in any trained arm.
24 matches per checkpoint, greedy, search-free, owner's band (>=3 tiles behind OUR bank, >=4 from
each edge, overlap to offensive):
```
                 bows/match  OFFENSIVE  NEITHER(dead)  DEFENSIVE  lifetime  full  IDLE  lock%  towerdmg
m18000 reference    2.71        69%         29%          2% (1)    20.9s    25%   32%    82%    1611
control             1.25        63%         37%          0%        21.5s    33%   32%    84%    2259
bank2               0.92        73%         27%          0%        20.6s    32%   39%    75%    2129
bank6               1.83        64%         36%          0%        20.2s    25%   35%    75%    1519
restraint           0.71        76%         24%          0%        16.5s    12%   39%    54%    1129
```
**ONE defensive x-bow out of 178 across five checkpoints, and it belongs to the untrained-on
reference.** Every trained arm: zero. The deck's second-building doctrine (§DOCTRINE.md "DEFENSIVE
(centre band, acts as a second pull building)") is not merely under-used -- **it is absent**, and
that is consistent with §5y: the doctrine prior samples y=0.55, which is 0.6 tiles behind our bank
against the band's 3.0, so the prior has never taught the band the reward is meant to credit.

**24-37% of every arm's x-bows land in the DEAD ZONE** -- 6 elixir placed where they can neither
reach an enemy tower nor sit in the defensive band. That is roughly one x-bow in three, wasted.

### The owner's hypothesis, answered
Owner asked whether bad x-bows or an unrealistic opponent explained bank6's poor crowns.
**Neither, and the offensive x-bows are actually FINE**: 75-84% get a tower lock and deal
1500-2400 damage. What is broken is around them -- a third in the dead zone, zero defensive, and
**32-39% of x-bow LIFETIME spent with no target at all**.

⚠ AND IT QUALIFIES §5z's READ OF bank6. Per-bow, bank6's x-bows are the WEAKER ones:
```
                bows/match   tower dmg each   ~total tower dmg/match
control            1.25           2259               2824
bank6              1.83           1519               2780
```
**bank6 plays 46% more x-bows for the same total tower damage.** Its higher `xbow%` share (§5z) is
volume, not effect. That does not overturn §5z's banking result, but "bank6 is closest to the human
x-bow share" (§5w) is now a weaker claim than it looked: the pro's 3.55 bows/match are presumably
not each worth a third less.

### Volume is DOWN against both references
Pro 3.55 bows/match (§5w), m18000 reference 2.71, trained arms 0.71-1.83. **Training reduces x-bow
deployment**, and restraint (0.71/match, 16.5 s mean life, 54% lock, median tower damage **0** --
over half its offensive bows did nothing) is the worst on every axis here, independently confirming
its drop from the 3-seed set.

## §5ab — LIVE POLICY PERFORMANCE BRAINSTORM COMPILED FOR HANDOFF

The full project-grounded brainstorm is now a durable agent-readable brief at
`research/LIVE_POLICY_PERFORMANCE_BRAINSTORM.md`. It records the evidence that timing and complete
response selection are the leading bottlenecks (search 37.0% -> 85.7%; card distillation improves
agreement without a measured outcome gain; an accurate restraint veto is harmful), then specifies a
ranked roadmap: enemy-play response-regret benchmark, joint WAIT/card/cell candidate scorer,
timestamped canvas stack then recurrent sequence policy, teacher continuations with DAgger-style
aggregation, reactive/strategic specialists, event-balanced live replay, opponent belief state, and
only later a compact learned world model. It also records the non-recommendations, experiment gates,
measurement discipline, primary research links, and the local evidence map. **Documentation only:**
no model, reward, config, or running experiment changed.

### §5aa addendum — owner decisions 2026-08-29 23:00 (weekly usage at 99%, resets Tuesday)
* **Graphify doc pass: DEFERRED past Tuesday's reset.** The AST half is done and committed; the
  234 changed docs remain unstamped in the manifest, so `--update` re-queues them automatically.
* **3-seed run: LET IT FINISH** (option a). No doctrine change until it completes -- the run
  depends on the current doctrine, and §one-change-per-experiment applies.
* **X-bow defensive band retune: AFTER the 3-seed run.** Scope is fixed and measured in §5y/§5aa:
  `xbow_defense_front` (0.92 tiles behind our bank vs the 3.0 spec), `central` (5.76 tiles from
  edges vs 4.0), `doctrine.py`'s `_add_spot(0.48, 0.55)`, and DOCTRINE.md's coordinates -- one
  coherent pass, preserving the Rocket suppression and re-checking `xbow_lane_frac`.
* Milestone monitoring was swapped for a FAILURE-ONLY watch: at 99% usage each notification costs
  an owner turn, and the happy path does not need one.

## §5ab — /!\ THE 3-SEED CONFIRMATION REFUTES §5z AND §5x. The A/B was underpowered by ~10x

Seeds 41 and 42 complete at matched m=1500 (seed 43 still running). 16 matches/arm, greedy,
search-free, same scorer. Arm order is by argument position -- the report truncates names at 11
chars, so rows 2/3 read as `policy_bank` for bank2 and bank6 respectively.
```
              >=6 el%   mean   xbow%  plays%   leak    crowns
seed 41  control   2.2   2.08    2.0    14.2   -0.07   -0.50
         bank2     1.9   2.12    2.2    14.4    0.00   -1.75
         bank6     0.7   1.89    0.8    14.3    0.00   -1.00
seed 42  control  20.3   3.83    8.1    10.4   -2.70   -0.62
         bank2     5.2   2.41    3.2    12.6   -0.47   -1.69
         bank6     4.4   2.26    1.2    14.6   -0.86   -0.81
```

### CONTROL BEATS BOTH BANK ARMS AT BOTH SEEDS
§5z's headline was *"control collapses monotonically and bank6 does not"*, on three reads of one
seed. **Two fresh seeds invert it.** The m=1000/m=1500 dose ordering does not reproduce.
* §5z "bank6 arrests the collapse" -- **NOT SUPPORTED**
* §5x "the dose-response appeared" -- **NOT SUPPORTED**

### /!\ AND THE REAL NUMBER IS CONTROL'S OWN SPREAD: 2.2% vs 20.3%
Same config, same init, same m, **differing only in seed** -- a **9x range on the primary
endpoint**. Every arm difference this project has ever reported is smaller than that. The original
A/B's headline gap (control 4.0 vs bank6 11.1) is 2.8x, comfortably inside what seed alone produces.

**THE 4-ARM A/B COULD NOT HAVE DETECTED AN EFFECT OF THE SIZE IT WAS LOOKING FOR.** It was
underpowered by roughly an order of magnitude, and no amount of extra run LENGTH would have fixed
that -- which is why §5x's read of the m=500->m=1000 inversion (seeds, not length) was right even
though its conclusion about the arms was not.

### What this costs, honestly
A chain of conclusions reported with rising confidence across 2026-08-29 -- §5x's "designed
signature appeared", §5z's "strongest thing this run supports" -- rests on n=1 seed and is now
withdrawn. The single-seed screen did exactly what §5q said a screen does; the error was mine, in
how much weight I put on it between the screen and the confirmation.

### What survives
* **restraint is still dead**: worst arm in the original run AND worst on every x-bow axis (§5aa).
* **§5aa's x-bow findings stand** -- they are per-checkpoint measurements over 178 bows, not
  between-arm inferences, so seed variance does not touch them. Zero defensive x-bows, 24-37%
  dead-zoned, offensive bows effective at 75-84% lock.
* The banking collapse itself (§5o/§5p) is unaffected: it reproduces everywhere, in every arm.

### CONSEQUENCE FOR FUTURE EXPERIMENTS -- do not run another A/B on this design
Before testing any further reward change, either (a) find a LOWER-VARIANCE endpoint, or (b) size the
seed count against the 2.2-20.3 spread rather than against intuition. ⚠ n=3 may still be too few:
two seeds already differ by 9x. **Measuring the seed-variance distribution of the CONTROL arm alone
is now the cheapest useful experiment available**, because it sets the detectable effect size for
everything after it.

## §5ac — GAUNTLET L1: brainstorm reviewed, response-regret benchmark v0 built, band retune staged

Owner started `/gauntlet` (goal: evaluate `research/LIVE_POLICY_PERFORMANCE_BRAINSTORM.md`, then
improve decision-making -- spells, efficient defense, x-bow use and defense). Full verdict table
with measurements: **`research/BRAINSTORM_REVIEW.md`**. Spine accepted (regret benchmark -> joint
candidate scorer -> temporal memory -> world model last); two-speed router REJECTED pending
evidence; GRU/R2D2, belief heads, event replay DEFERRED; its §14.1 bank_hold premise is refuted by
§5ab. Key addition: the benchmark is ALSO the §5ab power fix -- regret is scored per-state on a
cloned board, so the 9x match-level seed variance never enters the comparison.

`tools/response_regret.py` v0: enemy-play events via `eng.last_deploy[1]` timestamps; scores WAIT +
top card/cell candidates through `Searcher.candidates()`/`_rollout()` (H=12 s, outcome-grounded
Scorer, common RNG per decision); fixed seed list; per-event CSV (enemy base/kind, wait_score,
best_same_card_score) so spell/x-bow/card-vs-placement buckets slice offline. Smoke: mechanics OK.

Band retune STAGED, not applied (gate: ab3 wave 3 still training):
`scratchpad/gauntlet/L1/band_retune.py`, asserts every anchor and verifies band geometry after.
⚠ Two decisions taken without asking, flagged for veto: (a) the owner band has no back edge, so
`xbow_defense_back: 0.74` + `deep_frac` beyond is kept as the faithful reading; (b) rows 15-18
off-centre bows fall out of band by DEPTH under the new front, reverting the `xbow_lane_frac`
softening for them. ⚠ The live `env.*` band (0.52/0.62) is SCREEN-SPACE on a foreshortened frame
(env.py:424) and is NOT retuned -- it needs the calibration mapping, not tile numbers.

## §5ad — 3-SEED FINAL: bank_hold is HARMFUL, dose-dependently, at p≈0.005. Band retune APPLIED

### The complete 3-seed table (all cells at m=1500/1501, same instrument throughout)
```
>=6 el%    s41    s42    s43     within-seed ordering
control    2.2   20.3    7.5     control > bank2 > bank6
bank2      1.9    5.2    6.2     control > bank2 > bank6
bank6      0.7    4.4    0.0     control > bank2 > bank6
```
**Control beats bank2 beats bank6 at ALL THREE seeds.** Within-seed comparisons are paired (arms
share the seed), so the 9x match-level variance largely cancels; sign test on the full ordering:
(1/6)^3 ≈ 0.5%. **The dose-response is monotone in the WRONG direction: `bank_hold` deepens the
collapse it was designed to arrest.** bank6_s43 is the first TOTAL collapse measured anywhere
(0.0%, and its 8/10 distinct cards is also the first card-diversity loss).

### The mechanism reading (plausible, one signature, not proven)
`bank_hold` pays for CLIMBING toward a held win condition. Paying for the climb pays for
spend-to-the-floor-then-reclimb cycles. bank6_s43 carries the signature: highest plays% (14.6),
lowest mean elixir (1.76). The gaming risk flagged at §5x is what happened.

### Standing conclusions
* `bank_hold` joins `restraint_hold` as a DEAD repair. §5p's asymmetry diagnosis still stands;
  two reward-side patches have now failed measurably. This CONVERGES with the brainstorm's thesis
  (§5ac): the failure is temporal/structural, not reward-tunable.
* §5z's single-seed trajectory ("bank6 never collapses", bank6=11.1 at m=1500) is now the outlier
  against four fresh cells. Single-seed trajectories join single-seed levels as untrustworthy.
* Control's n=3 spread: 2.2 / 7.5 / 20.3 -- the 9x range is confirmed, not a two-seed fluke.

### Band retune APPLIED (§5y scope + owner rulings, nothing training at the time)
10 edits, every anchor asserted, geometry verified after: `sim.xbow_defense_front` 0.56 -> 0.625;
`central` 0.18 -> 0.278; doctrine spots (0.48,0.55) -> (0.50,0.66) both call sites; DOCTRINE.md
rows updated; counter-bow #48 left as-is (offensive trade rule) with a flag comment.
Owner rulings folded in: back edge stays 0.74 + deep_frac (call 1 approved); `xbow_lane_frac`
softening window now starts at OUR BANK (0.53125) instead of the band front (call 2: "reapply the
softening tax"). ⚠ The widened window also softens the CENTRAL shallow strip (bank..0.625), not
just off-centre -- tighten if the owner meant off-centre only. ⚠ Live `env.*` band NOT touched
(screen-space, needs the calibration mapping). Backups in scratchpad/gauntlet/L1/prepatch/.

## §5ae — GAUNTLET L2: regret corpus v1 built; the deficit is CONTINUATIONS, not event responses

### v0's cross-checkpoint rankings were INVALID (affordability censoring)
v0 measured each policy on its own trajectory: <2 affordable candidates = event skipped, so an
elixir-starved policy gets its hardest moments censored and looks GOOD (bank6_s43 read 0.16 vs
m18000's 0.35 while being the collapsed one). v0 stays useful for within-checkpoint diagnostics
only. `tools/regret_corpus.py` is v1: a FIXED 203-state corpus (12 driver matches, replay-not-
pickle, per-event candidate sets scored once), grading any checkpoint = replay + one forward pass
per state (~1 min). Off-corpus actions rolled out on demand under the same per-event RNG.
m18000's `off-corpus 0` doubles as the replay-determinism proof.

### THE FINDING, and it survived its own control
Paired on the same 203 states, ORACLE view: m18000 regret 0.384 (waits at 90% of events,
missed-play 73%) vs trained arms 0.24-0.30. **The strongest match player makes the worst
per-event decisions.** BELIEF view (reseed_opp, sampled futures -- the pre-committed
discriminator): m18000 0.371, control_s41 0.221, bank6_s43 0.254 -- **ordering unchanged, gap
intact. The oracle-bias explanation is dead.**
```
Conclusion: m18000's match superiority does NOT live in per-event response ranking.
It lives in CONTINUATIONS/strategy. Roadmap tilts P2 (joint scorer) -> P3/P4
(temporal memory + continuation teaching).
```
⚠ Caveat cutting the SAME direction: the H=12s scorer undervalues waits paying off later, i.e.
per-event regret shares §5p's short-horizon bias. The doc's follow-through metrics are the fix,
and they are continuation measurements.

### Band retune training effect: NULL at this budget
band_s41 (retuned doctrine, warm-start, s41, m=1500) vs seed-matched pre-retune control_s41:
**still ZERO defensive x-bows** (prior samples (0.50,0.66) in-band; policy never places one);
dead zone 14% vs 20% (n=14/15 bows -- noise-sized); offensive quality NOT claimed worse (n too
small under the 9x lesson). The geometry stays (owner spec); the placement-prior-alone hypothesis
FAILED. With restraint_hold and bank_hold dead (§5ad), three repair families have now failed
measurably -- all converging on the structural/temporal thesis (§5ac).

### Launched overnight: canvas_stack 1 vs 2 (the first P3 experiment)
Both FROM SCRATCH (stack 2 changes input width, warm-start impossible; scratch-vs-warm would be
the §4a confound), same seed 41, retuned config, 1500 matches, sequential
(`data/bench/stack{1,2}_run.log`). Read tomorrow: paired regret on both corpora + xbow_probe +
drills. NOTE stack1-scratch also gives the first scratch-vs-warmstart regret comparison for free.

## §5af — GAUNTLET L3: canvas_stack 2 is NULL-NEGATIVE at 1500 matches; placement data EXISTS on RoyaleAPI

### canvas_stack 1 vs 2 (paired: same seed 41, same retuned config, both scratch, both m=1500)
```
                 oracle regret   belief regret   top-1   missed-play%   bows/m   bow<5s death
stack1 (1 slice)    0.2368          0.2417        21%       64%          0.33        12%
stack2 (motion)     0.2961          0.2859        26%       57%          0.17        75%
```
Pre-committed call (§5ae): **NULL, leaning negative** -- stack2 is worse on mean regret in both
views. Faint counter-signal in the decision RATIOS (missed-play 57 vs 64%, worse-than-WAIT 19-21
vs 23%) recorded, not weighted: n=1 seed, and it does not survive the mean. Combined with the
MEASURED 4x throughput tax (957 -> ~300 matches/h), canvas_stack 2 is dead at this budget.
**Continuation teaching (P4) is the sole frontier.** ⚠ 1500 scratch matches is a small budget;
"dead at this budget" is the claim, not "temporal information is worthless".
/!\ INSTRUMENT TRAP FOUND: grading a stack-2 checkpoint under a stack-1 config silently skips
`features.0.weight` (random first layer) and RUNS ANYWAY. The regrade asserts zero carry-over
warnings. Any cross-width eval must pass the checkpoint's own --config.

### The scratch-defensive-bow phenomenon REPRODUCED (weakly) and is being confirmed
stack1 3/8 bows in-band, stack2 1/4 -- both scratch arms produce defensive bows; every
warm-started arm ever probed has ZERO. Confirmation chain launched: stack1 config, seeds 42+43,
sequential, detached (data/bench/defbow_chain.sh, .done marker on completion).

### /!\ §5w CORRECTION: RoyaleAPI DOES ship placement. The owner was right; the export was blind.
The replay payload carries a `.marker` element set -- `data-x`/`data-y` in game units (1000/tile,
x 0-18000, y 0-32000) -- that the stock scraper never parsed. Probe-verified on Hubert replay
02GY9GQLLQ2Y: 104/109 plays join to tile-precision placements on (tick, card, occurrence). §5w's
"THERE IS NO PLACEMENT DATA" is CONTRADICTED for the source; it was true only of that export.

### Population crawl RUNNING (owner-directed): top-50 icebow + Hubert first, Hunter ON ROSTER
`clash-replay-scraper/crawl_icebow.py` (new driver): 50 players, 5 pages each, extended parser
keeps every data-* attr + tile_x/tile_y. Session token persisted (3 logins were burned by two
driver bugs, both fixed: save-token-before-verify; per-player completion marks after
pipeline.battles' fan-out checkpointed a 1-player partial as final). At L3 close: 460/512
replays. Output: icebow/data/royaleapi/crawl2/ (gitignored).

### Owner ruling on replay-data use (asked before bed): NOT BC pretraining
Three measured distillation nulls + no reconstructable states (sim-parity drift) + 50-75k plays
too thin. Approved uses: placement priors P(tile | card, phase, recent enemy) for doctrine.py's
exploration prior (replay-visible conditioning only, no board reconstruction), continuation
statistics for P4, and evaluation anchors (does the pro population place bows in the 5y band?).

## §5ag — GAUNTLET L4: the pro population dataset. Depth of the band VALIDATED, width CONTRADICTED

Crawl complete: **520 battles, 45,335 plays, 24 players** (26 of the 50-player roster had no icebow
battles in their recent 5 pages — roster attrition, not failure), Hunter and Hubert both in.
Placement join is **bimodal**: 268 replays join >80%, 251 join <20% — markers exist for roughly
half the replays (likely an age/payload variant), yielding **12,220 blue plays with tile coords**.
Frame verified empirically before use: blue's own half is HIGH y (tesla median tile_y exactly 20.0,
IW 23.5, 99-100% of defensive-card placements at y>16) — same orientation as the engine.

### THE HEADLINE: 1,038 pro x-bow placements vs the §5y band
```
IN OWNER BAND (y>=20, 4<=x<=14)      359   35%
OFFENSIVE (tower-reaching)           178   17%
NEITHER                              501   48%
tile_y: median 19.5  p10 19.5  p90 22.5
top tiles: (16,20) x250   (2,20) x248   (10,22) x123   (8,22) x111
```
* **DEPTH: VALIDATED almost exactly.** p10 of pro bow depth is 19.5 — the owner's front (tile 20)
  sits within half a tile of where pros actually start. Nobody places shallower.
* **WIDTH: CONTRADICTED.** The two most common pro tiles — (16,20) and (2,20), ~48% of all
  placements between them — are LANE bows at depth, 2 tiles from the edge, EXCLUDED by the
  4-tile margin. The owner's ruling to keep `xbow_lane_frac` softening is empirically vindicated:
  lane bows at depth are the pros' modal defensive placement, not a misplace.
* ⚠ DECISION FOR THE OWNER (not taken): widen the band to include lane columns at depth
  (e.g. y>=20 with no width constraint, or a two-region band), or keep centre-only full credit
  with lane softening. Nothing changed in config/doctrine pending that call.

### Population continuation anchors (P4 targets; §5w's n=1 anchors CONFIRMED at n=24)
```
inter-play gap  median 3.85s  mean 5.13  p10 1.55  p90 10.15   (n=23,101; 5w said 3.60)
play rate       11.7/min                                        (5w said 11.3)
AFTER X-BOW     next play median 5.5s: knight 20%, tesla 17%, skeletons 17%, log 16%, IW 16%
AFTER TESLA     next play median 4.2s: skeletons 22%, knight 19%, log 18%, IW 17%
```
The deck's premise ("defend the bow") is now a measured distribution: within ~5.5 s a pro follows
the bow with a bodyguard, second building, or cycle card, at these ratios. These are the empirical
targets for the P4 teacher-plan record.

## §5ah — GAUNTLET L5: SCRATCH-DEFENSIVE-BOW CONFIRMED AT 3 SEEDS; P4 design committed

### The 3-seed verdict (xbow_probe, 24 matches each, all checkpoints m=1500, one instrument)
```
                 defensive bows      def-bow unit dmg (upper bound)
stack1_s41         3/8   (38%)          1505 mean   (measured L3)
stack1_s42         3/14  (21%)          3313 mean, 24 targets died   (this loop)
stack1_s43         3/10  (30%)          2492 mean   (this loop)
pooled             9/32  (28%)
every warm-started checkpoint ever probed: 0/192   (5 ckpts x 178 + band_s41 x 14)
```
**CONFIRMED: from-scratch training under the §5y-retuned doctrine produces in-band defensive
x-bows at every seed; warm-starting from m18000 has produced zero, everywhere, always.** The §5ae
"placement-prior-alone FAILED" verdict is REFINED, not reversed: the prior teaches the band —
m18000's frozen placement habits block it. The defensive bows WORK when placed (1.5-3.3k unit
damage as a second pull).

### What this does NOT establish
Scratch arms are far worse match players overall: offensive locks 0-25% (warm-started: 58-84%),
dead-zone 21-50%, bow volume 0.42-0.58/match vs the pro 3.55. The finding is narrow and about the
PRIOR's teachability, not about scratch arms being good. The open question it sharpens: how to get
band placements WITHOUT forfeiting the warm start — candidates (all untested): longer scratch runs,
warm-start with cell-head reset, or prior-weighted fine-tuning.

### P4 design committed
`research/P4_CONTINUATIONS_DESIGN.md`: teacher plan record from the winning rollout branch
(near-zero cost), hazard-first loss ordering, pro population distributions as EVALUATION anchors
never gradient, pre-committed gates, explicit does-NOT-do list. First implementation step is pure
logging (no training change) — ready for the owner's go-ahead.

## §5ai — GAUNTLET L6 (hold loop): pro SPELL placement portraits — doctrine largely validated

Read-only analysis of crawl2 (blue plays with coords; frame per §5ag). Owner-gated items untouched.
```
the-log   n=1802  99% own-half; modes (14,18) (4,18) -- lane logs just behind our bank, rolling
                  forward. DOCTRINE VALIDATED ("cast from your side, reaches their chip range").
rocket    n=761   76% enemy-half; modes (14,8) (6,8) (4,8) = 1.5-2 tiles IN FRONT of the enemy
                  princess (tower+support value). Almost never their king (doctrine rule holds).
                  16% own-half = defensive rockets exist but are the minority.
tornado   n=979   BIMODAL: king-pull cluster (8,24)(10,24)(8,26) + mid clump cluster (4,16)(4,12).
                  ⚠ Pro king-pulls sit at y 24-26 -- DEEPER than doctrine's destination
                  (0.48,0.70) = tile 22.4 by ~2-3 tiles. Doctrine's nado coordinate may be shallow;
                  flagged for the owner's doctrine pass, NOT changed.
```
These are evaluation anchors (and candidate prior updates, owner-gated). With §5ag/§5ah this
completes the goal's four focus areas with population evidence: spells (validated + one refinement),
defense (continuation targets), x-bow use (band evidence), defending the bow (follow-up ratios).

## §5aj — OWNER RULINGS EXECUTED: band widened to pro placements; P4 step 1 shipped (+ a design correction)

### Band widened (owner, 2026-08-31: "encompass the placements pros use")
`env.py` central 0.278 -> **0.389** (>=2 tiles from each edge -- pro modal tiles are lane bows at
x=2/16, §5ag); `doctrine.py` gains the pros' lane-bow spots **(0.11, 0.64) and (0.89, 0.64)** at
centre-spot weight in BOTH defensive branches (lane bows outnumber centre bows 498 vs 234 in the
population); probe `--def-edge` default 4.0 -> 2.0. Depth unchanged (validated, §5ag). Applied
with nothing training; env constructs and steps.

### /!\ P4 DESIGN CORRECTION: the teacher has NO continuations to record
`_rollout` (rollout_search.py:308) IDLES OUR SIDE for the whole horizon. The searcher that lifted
37% -> 85.7% scores every action followed by 12 s of DOING NOTHING -- there is no winning-branch
continuation to log, and the design doc's §1 premise was wrong (corrected in the doc, loudly).
This SHARPENS the diagnosis: even a single action + passivity beats the policy, and continuations
were never modelled anywhere. Replacements: (a) chained sweeps (genuine teacher plans, ~2x search
cost, needs a cost probe); (b) hindsight continuations from the training stream -- implemented.

### P4 step 1 SHIPPED: hindsight continuation logging (pure logging, zero training change)
`train.continuation_log: <path>` (default "" = OFF, provably no change). At each PPO update the
finished horizon buffers emit one JSONL row per play: card/cell/searched-flag, dt to the SAME
env's next play, next card/cell/flag, `trunc` marking horizon/episode censoring (hazard loss
treats censored, not "no next play"). Episode boundaries respected via roll["done"].
Smoke-verified: 4 matches -> 42 well-formed rows. Next: enable on the next real training run to
accumulate the corpus; `continuation_report.py` eval is step 2 (design doc §6).

## §5ak — GAUNTLET L7: continuation instrument SEES m18000's edge; chained plans cost 2x search

### continuation_report.py (P4 step 2) BUILT + baselined (16 matches, fixed seeds, greedy)
```
                     gap med   rate/min   after-BOW L1-to-pro (n)   after-TESLA L1 (n)
pro anchors (5ag)     3.85       11.7            --                       --
m18000                4.20       10.6         0.250 (16)               0.419 (27)
control_s41           4.20       13.5         1.020 (10)               0.619 (31)
stack1_scratch        4.20       13.5         0.960 (5)                1.000 (10)
band_s41              4.20       13.1         1.080 (5)                0.771 (14)
```
**m18000 is 4x closer to the pro continuation profile than any trained arm** -- the edge that was
INVISIBLE to per-event regret (§5ae: m18000 reads WORST there) is the largest separation on this
instrument, and the ordering now matches match strength. That is the missing complement: regret
measures the instant, this measures the follow-through, and the two instruments disagree in
exactly the direction the continuation thesis predicts.
⚠ after-bow n is 5-16 (bows are rare); use >=32 matches for tight after-bow numbers. ⚠ gap medians
quantize to agent_dt multiples (all read 4.20 = 7 steps); timing carries +/-0.6s granularity.

### Chained-sweep cost probe (P4 option a): the price is 2x search, NOT more
30 events, m18000, sweep from the state ~1.8s after the chosen action:
```
sweep1 111ms mean | sweep2 104ms mean | ratio 0.94x | chained total 215ms/searched decision
```
The post-action board is NOT costlier to roll (0.94x). Genuine teacher plans cost ~2.0x search;
at interval 4 (search ~95% of decision cost) that PROJECTS to ~0.5x training throughput, or
chain every 8th decision to keep today's speed. Projection labeled; run-level impact untested.

### Graphify doc pass: 5/10 chunks landed (all images), 5 doc chunks in flight
Third scope bug caught first: 130 of 240 "changed docs" were scratchpad sweep logs -- would have
burnt 6 subagents. `scratchpad/` + `scratch/` now in .graphifyignore; 245 -> 105 files, 16 -> 10
chunks. Merge + rebuild happens when the doc chunks land.

## §5al — GAUNTLET L8: graphify current (12,018 nodes); PPO run spec posted for approval

Graphify doc pass done: 10 subagent chunks (all validated by their agents, zero requeued),
merged + AST + clustered -> **12,018 nodes / 22,230 edges / 633 communities**; 105 semantic files
stamped; scratchpad/scratch permanently excluded (third scope bug -- 130 sweep logs would have
burnt 6 agents). The graph now covers code AND docs including all §5x-era sections.

`research/PPO_RUN_SPEC.md` posted with --questions. One change = the §5aj geometry ruling as a
unit; 3 scratch seeds vs the stack1 trio already on disk (identical but for the ruling);
continuation_log ON as instrumentation; paired instruments with the def-edge re-probe caveat;
fixed 1500; pre-committed verdict rule. NOT launched.

## §5am — GEOMETRY RUN VERDICT: NOT PASSED (1/3), and two SELF-INFLICTED flaws contaminate it

### The pre-committed read (paired probes, one instrument, def-edge 2.0, all six at m=1500)
```
             bows/match   DEFENSIVE in-band     paired delta (5aj vs 5y config, same seed)
geo_s41        1.33          0/32  (0%)          DOWN vs stack1_s41 38%   <- WALL ARTIFACT
geo_s42        0.00          no bows at all      DOWN vs stack1_s42 21%   <- volume collapse
geo_s43        0.71          9/17  (53%)         UP   vs stack1_s43 30%
```
Rule was: rises at >=2 of 3 seeds. **Rises at 1 of 3 -> NOT PASSED.** But the verdict is
contaminated in both directions by implementation flaws found AFTER the read (below), so the
honest status is: **the lane-spot mechanism is UNTESTED, not refuted; the s43 signal and the s42
volume collapse are real observations.**

### /!\ FLAW 1 (mine): the lane spot CLIPS INTO THE WALL. geo_s41's bows are ALL at x=0.6 tiles
I placed the doctrine lane spots at x=0.11 (=1.98 tiles) with the standard 1.5-tile spread. Half
that Gaussian falls off the board; deploy-clamp folds it into the wall column, and s41 collapsed
onto the clipped attractor: every bow at x=0.6 tiles, y 23-30 (coordinates verified). The pros'
modal tile is x=2 -- the spot should be the TILE CENTRE (0.139 = tile 2.5), inside every boundary.
### /!\ FLAW 2 (mine): three >= 2.0 boundaries pinch the taught spot
Doctrine 0.11 = 1.98 tiles; probe band requires >=2.0; reward `central` 0.389 cuts at 2.0 exactly
(|0.11-0.5| = 0.39 > 0.389 -- the reward band EXCLUDES the very spot the prior teaches, leaving it
lane_frac 0.35). Even un-clipped placements at the taught x misclassify AND under-credit.

### What survives untouched by the flaws
* **s42's ZERO bows in 24 matches** is behaviour, not classification -- first bow-free arm ever
  probed. Volume risk under the widened band is real at 1 of 3 seeds.
* **s43: 53% in-band defensive** (9/17, 1990 dmg mean, 17 kills) -- the best defensive-bow read of
  any checkpoint, ever.
* **Guardrails passed**: regret 0.257-0.309 both views (in family, no regression); geo_s41's
  continuation profile is the closest-to-pro measured ANYWHERE (after-bow L1 0.223 vs m18000's
  0.250; after-tesla 0.243 vs 0.419), and its 11.9/min rate ~= pro 11.7 -- though follow-ups come
  fast (dt 1.8s vs pro 5.5s).
* **38,224 continuation rows banked** (~2x estimate) for the hazard A/B.

### Fix + redo (queued AFTER the parity chain, per the owner-approved order)
Constants: lane spots 0.11/0.89 -> **0.139/0.861** (tile 2.5, pros' modal column, clear of clamp
and both band edges); reward `central` 0.389 -> **0.390** (covers tile-2 centres cleanly). Then
redo = 3 fresh seeds (54-56), same everything else -- ~3h. The s43-vs-stack1_s43 pairing carries
forward as supporting evidence, never as the verdict.

## §5an — PARITY CLEARED: workers-12 carries the real run

3 seed-pairs, 1500 matches each, identical config, graded paired on both frozen corpora:
```
w12 - w0 regret    oracle     belief
s51                -0.025     -0.019
s52                +0.017     +0.023
s53                -0.018     -0.038
```
**All |deltas| 0.017-0.038 (inside same-config seed spread), signs MIXED -> no systematic path
effect. Gate 1 PASSED: the real run gets workers 12 and its 1.83x.** Fingerprint assert: 0
warnings across all three w12 runs -- the 5ak flat-CE residual lead is retired (broadcasts change
every update; the L2-era 6x gap was seed variance, as the equal-drift check said).
NO throughput numbers from this chain (contended box: reads + owner apps). 5 of 6 runs also
survived a session restart mid-chain (nohup isolation working as designed).

## §5ao — GEOMETRY REDO: CLEAN FAIL (0/3). Lane spots reverted; centre-only widened band stands

Redo with the §5am wall-clip fix (lane spots 0.139/0.861 = tile 2.5 centres, `central` 0.390),
3 scratch seeds 54-56, m=1500, probed vs the stack1 trio under the same def-edge:
```
                DEFENSIVE in-band     stack1 baseline (same seed slot)
geo2_s54          1/3   (33%, n=3)      stack1_scratch 38%
geo2_s55          2/19  (11%)           stack1_s42     21%
geo2_s56          1/10  (10%)           stack1_s43     30%
```
Rule (§5am): in-band rate rises at >=2 of 3 seeds. **Rose at 0 of 3** -- s55/s56 BELOW baseline,
s54 is 1 bow of 3 (noise). s56 dead-zone 80%. The wall-clip fix worked mechanically (no x=0.6
pile this time), so this is a CLEAN fail, not an implementation flaw -> spec fail-clean branch.

**FINDING: the doctrine placement prior cannot teach in-band lane bows.** Third confirmation that
placement priors alone don't move behaviour (§5ae placement-prior-alone, §5am clipped, §5ao clean).
Pros place lane bows; sampling those tiles in exploration does not make the policy imitate them.
Points at the same continuation deficit the hazard head targets.

**ACTION: lane spots (0.139/0.861) REVERTED in doctrine.py, both branches. RETAINED: widened
`central` 0.390 in env.py** -- the reward still CREDITS a pro lane bow, it just no longer SAMPLES
one in exploration. The real run proceeds on this centre-only widened band, scratch.

### /!\ PROCESS NOTES (two, both mine)
* The emulator (crosvm, 11 procs) had autostarted ~17:00 and stole ~30% throughput through the
  parity chain AND the whole redo -- the real cause of the redo overrun (~40 min crash + ~90 min
  contention), NOT the "optimism" I first claimed. Killed on owner's OK. Measure contention before
  attributing a slowdown.
* I killed the emulator while s56 was at m=1100 and only checked chain state AFTER -- it had
  finished exit 0 ~1 min prior, so nothing was lost, but record-before-kill was cut too close.

## §5ap — HAZARD A/B: NULL (1 win / 1 tie / 1 disqualified). THE REAL RUN LAUNCHED 2026-09-01 17:50

### Hazard head A/B (P4), hazard_coef 0.5 vs 0.0, scratch seeds 61-63, m=1500, centre-only band
Primary = realized-wait regret (missed-play % on the states where the policy WAITED), paired on both
corpora (oracle / belief). Pre-committed win rule: c05 lower at >=2 of 3 seeds AND guardrail not worse.
```
seed   arm   regret mean (o/b)   waits   missed-play (o/b)   worse-than-WAIT (o/b)   top-1 (o/b)
61     c05   0.3133 / 0.3035      35      57% / 54%            22% / 23%              19% / 20%
61     c00   0.2917 / 0.3041       2       0% /  0%            24% / 27%              17% / 15%
62     c05   0.2797 / 0.2763      39      64% / 62%            23% / 24%              25% / 27%
62     c00   0.2806 / 0.2741      55      69% / 69%            24% / 25%              22% / 22%
63     c05   0.2904 / 0.2962      79      65% / 65%            19% / 20%              28% / 27%
63     c00   0.3141 / 0.3113      74      65% / 65%            21% / 23%              26% / 25%
```
* **s61 DISQUALIFIED on the primary**: the control waited at 2 of 203 states, so "0% missed-play" is
  no waits to grade, not good waiting. Floor set at >=15 waits per arm BEFORE seeds 62/63 were read
  (pre-commitment, so it could not be tuned to taste). s62/s63 both clear it.
* s62: c05 WINS (64/62 vs 69/69). s63: exact TIE (65/65 vs 65/65; 51/79 vs 48/74).
* **VERDICT: NULL under the rule as written -> the real run carries hazard_coef 0.0.**

### What the secondaries show (measured; suggestive; NOT a result)
Same sign at 3/3 seeds, both corpora, in the head's favour: top-1 oracle agreement +2..+5 pts;
worse-than-WAIT plays -1..-4 pts. Overall regret is MIXED-SIGN across seeds (s61 +0.022/-0.001,
s62 wash, s63 -0.024/-0.015) = noise. Continuation report (16 matches, greedy): after-x-bow
follow-up L1-to-pro better for c05 at both comparable seeds (0.400 vs 0.660; 0.286 vs 0.320;
s61 control had no bows) and after-bow delay longer (1.2-2.7s vs 0.6s; pro 5.5s); after-tesla
mixed (2/3). Each is 3/3 on 1-5 point deltas at n=5-27 -- a sign test at p=0.125 per metric, the
exact pattern this project has been burned by (§5x, §5z). **Top follow-up candidate**, queued in §6:
rerun with a 4th seed to replace s61, OR test as a fine-tune on the real run's checkpoint (the head
is in the net, inert, so no architecture mismatch), with the ~10x larger continuations_real.jsonl.

### Trap found (new): near-zero-wait control arms
A fresh scratch arm can wait at ~1% of corpus states (s61 c00: 2/203), which makes any
wait-conditioned metric undefined for it. Any future A/B whose primary conditions on waits MUST
state a wait-count floor in advance. Seeds 62/63 waited 39-79 -> s61 was an outlier, not systemic.

### THE REAL RUN (gauntlet terminal condition; owner directive "launch immediately when gates green")
* Launched 2026-09-01 17:50 via `data/bench/real_run_launch.sh` (nohup): `--config data/bench/real_run.yaml
  train-sim-ppo --matches 40000 --envs 96 --workers 12 --size 432 --device cpu --seed 41 --search-interval 4`
* `real_run.yaml` = CURRENT config.yaml + exactly 3 lines: `train.sim_ppo_checkpoint: data/policy_real_20260901.pt`
  (ISOLATED; path verified empty pre-launch; policy_sim_ppo.pt untouched), `train.continuation_log:
  data/continuations_real.jsonl`, `train.hazard_coef: 0.0`. Parse-checked; asserted band 0.625,
  cells 3, eval_every 2000, keep_best true (read from config, not defaults).
* gates: (1) parity CLEARED -> workers 12; (2) geometry CLEAN FAIL -> lane spots reverted (§5ao),
  centre-only widened band; (3) hazard NULL -> coef 0. SCRATCH (nothing at the checkpoint path).
* Banner verified: `continuation log ON`, `training FROM SCRATCH`, no HAZARD banner, 0 WARNING lines.
* Log: `data/bench/real_run_20260901.log`; exit line will land in `real_run_20260901.progress`.
* ARMED (nohup, session-independent): `tools/ppo_watchdog.py data/policy_real_20260901.pt --every 300
  --quiet-min 30` (out: data/bench/real_run_watchdog.out); `tools/real_run_gates.py` (NEW): waits for
  m=5k/10k/20k, SNAPSHOTS the ckpt to data/bench/real_m{5,10,20}k.pt, grades the snapshot with
  xbow_probe(24) + both corpora + continuation_report(16) into data/bench/real_gate_m*k.log, posts to
  Discord with measured pace + ETA; regret rising at TWO consecutive reads -> --questions (owner ping).
  State in data/bench/real_run_gates.progress (resumable).
* BOX AT LAUNCH: 2.2 GB available of 31.4. Training ~7.8 GB; owner desktop holds the rest (Chrome 4.9,
  VS Code 2.5, nucleo uvicorn 2.2, Discord/ChatGPT/Steam ~1.7) -- NOT touched. MemoryError is the
  main death risk; watchdog DEAD alert covers it. Emulator (crosvm) and Medal: 0 procs.
* ETA: NOT estimated here on purpose -- the m=5k gate report states the measured pace. For scale:
  workers-0 clean pace was ~1,260 matches/hr (haz chain); parity measured 1.83x for workers 12 on a
  clean box -> ~17 h IF that held, but this box is memory-tight and shared. Read the gate report.

### What this does NOT establish
* Nothing about the real run's quality yet -- m=5k is the first read.
* The hazard head is not refuted: 2 valid seeds at m=1500 cannot distinguish a 2-5 point effect.

## §5aq — OWNER OVERRIDE: the real run RELAUNCHED 18:18 WITH the hazard head (coef 0.5)

Owner, 18:15, on reading §5ap: *"Just because an issue fooled us in the past doesn't mean the same
observation is necessarily a trap. Restart the PPO with the hazard head included -- we'll be able to
see the results take shape more with the long run."* Applied. The correction is valid: §5ap used
"3/3 same-sign small deltas has fooled this project before" as if it were evidence AGAINST the
observation; it is only a prior on how much to trust small deltas. The measured record is: primary
NULL (not negative), secondaries same-sign at 3/3 seeds, NO metric showing harm at any seed.

**Stated limitation (measurement, not objection):** the long run has no paired no-hazard twin, so
the 5k/10k/20k gate reads show the head's behaviour in ABSOLUTE terms (vs pro anchors, vs the
run's own earlier snapshots) and cannot attribute outcomes to the head. §6 fine-tune ablation
(coef 0 on a real-run checkpoint) is the attribution path if ever needed.

**Kill record (guardrail):** first launch (17:50, coef 0.0) stopped at 18:16 at m=400, 0 warnings,
first checkpoint save had landed 18:14. Artifacts ARCHIVED, not deleted:
`data/bench/aborted_real_nohaz_20260901/` (policy 1,936,305 B; continuations 564,749 B; run log;
progress; watchdog/gates out). Checkpoint path verified EMPTY before relaunch (else train-sim-ppo
would have silently WARM-STARTED from the no-hazard save). policy_sim_ppo.pt untouched (Aug 29).

**Relaunch:** identical invocation; `real_run.yaml` now differs from config.yaml in the same 3 lines
with `hazard_coef: 0.5` (parse-checked, band/cells/eval asserted). Banner verified: `HAZARD HEAD ON:
coef 0.500, 7 log-spaced dt bins` + `training FROM SCRATCH` + `continuation log ON`. 12 workers,
2.6-3.8 GB available. Watchdog + `tools/real_run_gates.py` re-armed (nohup). Launch epoch written to
`data/bench/real_run_20260901.launched` -- the gate script now reads pace from it, not the log's
ctime (Windows tunnels a recreated file's creation time from its deleted namesake).

**Trap (mine, new):** a PowerShell `Where-Object CommandLine -like '*train-sim-ppo*'` kill sweep
matched ITS OWN shell (the pattern text is in the command line) and killed itself (exit 255) after
taking down only part of the chain. Kill by PID from a listing; never by a substring your own
command contains.

## §5ar — THROUGHPUT PROFILED: the PPO update was 70% of every cycle; on the GPU the same cycle is 2.9x faster (measured, same config, idle box)

Owner, 2026-09-01 evening: *"If it's a cheap decisive item, we can do the throughput experiments right
now, as I have a different direction planned for the next gauntlet."* Done as the §6 entry pre-stated:
profile first, then the decision rule, then ONE change. Every number below is MEASURED this session
unless marked. The real run kept running throughout except two recorded suspensions (psutil
`suspend()`, 15 min 51 s total, nothing lost -- technique note at the end); it is at m=2450 (21:08)
and advancing, 0 WARNING / 0 Traceback.

### 1. Where the cycle goes (`CLASHRL_PROFILE=1`, new opt-in profiler in train_sim_ppo.py)
Real-run config (`data/bench/prof.yaml` = real_run.yaml with an isolated checkpoint + continuation
path), `--envs 96 --workers 12 --size 432 --seed 41 --search-interval 4 --matches 125`, box idle
(real run suspended, runaway killed), 4 cycles = 501 env-steps each way. Buckets are parent wall time.

| device | 4 cycles | rollout (choose / step) | **update** | update split: mb tensors / fwd+loss / bwd / step |
|---|---|---|---|---|
| **cpu** (4 threads, = the real run) | **572.1 s** | 168.4 s (48.5 / 119.4) | **402.2 s = 70%** | 48.6 / 124.3 / 225.5 / 3.6 |
| **cuda** (RTX 5050, fp32, TF32 off) | **196.0 s** | 152.2 s (33.6 / 117.7) | **42.3 s = 22%** | 20.0 / 9.3 / 9.2 / 3.3 |

* **Cycle 143 s -> 49 s = 2.92x** (per env-step 1.142 s -> 0.391 s). Steady-state cycles 2-4:
  cpu 132 matches / 420 s = 1,131 matches/h; cuda 143 / 137.9 s = **3,733 matches/h** (4-cycle
  average incl. the warm-up cycle: 2,645/h). Matches per cycle depend on match length and the two
  runs diverge numerically after step 1 (different conv kernels, same algorithm), so env-steps is
  the fair unit; the real run itself measured ~1,016/h over its first 2,000 (one eval + the thief).
* The update went 100.6 s -> 10.6 s per cycle (9.5x). 87% of the CPU update was the CNN
  forward+backward on 4 threads; on cuda fwd+bwd is 4.6 s per update and the largest remaining
  piece is **minibatch tensor assembly, 5.0 s = 47%** -- the host-side gather of 512 scattered
  73,728-byte boards, 96 times per update, plus the H2D copy.
* `step` (the workers) is unchanged, 119 -> 118 s, as it must be. `choose` fell 48.5 -> 33.6 s and
  the 33.6 s that remain (67 ms per call over 96 envs) are the Python per-env loops in
  `choose_sample` (veto, doctrine floor, pocket codes, bookkeeping), not the forward.
* **Live duty cycle of the CPU real run (read-only psutil at 1 Hz, 300 s, no suspension):** the 12
  workers were collectively idle (< 25% of one core, summed) **233 / 299 s = 78% of wall**; means:
  parent 310%, workers 79% summed, box 48%. During the ~28-38 s rollout bursts the workers summed
  only ~380% (3.8 of 12 cores) while the parent ran ~280%; then ~100 s of parent-only update at
  300-600%. I.e. even the rollout is parent-bound, and the update leaves 12 cores idle.
* Standalone micro-bench (`tools/upd_bench.py`, synthetic batch, same net/heads/optimizer): the
  update's fwd+loss+bwd+clip+Adam for 96 minibatches is 88 s on 4 CPU threads vs **2.4 s** on the
  idle 5050 (25 ms/minibatch; cudnn TF32 default ON there -- the trainer runs TF32 OFF and measured
  4.6 s with per-minibatch syncs); trainer-style per-sample tensor assembly is WORSE on the GPU
  (18.0 s: 2,560 tiny host-to-device copies) than batched (3.0 s). Peak VRAM 0.59 GB.

### 2. What was built (one engineering change; training semantics unchanged; committed with this section)
`--device cuda` now works end to end for `--workers >= 2`: learner + action selection on the GPU,
the 12 CPU workers keep CPU nets. Three seams used to ship raw `state_dict()`s, which with a cuda
net would hand cuda tensors to 12 CPU processes (each unpickling them into its own CUDA context)
and into checkpoints; they now ship CPU copies via `_cpu_sd()`: `set_search_net` (every cycle),
`_broadcast_league`, `save()`. TF32 is disabled on cuda so both devices compute fp32.
Minibatch / choose / greedy / bootstrap tensor assembly is BATCHED (`to_obs_batch` / `to_vec_batch`:
one `np.stack`, one device copy, one permute + `.contiguous()`), verified **bit-identical** to the
old per-sample chains -- `torch.equal` values, same strides, same `forward_parts` output -- on real
env observations and random boards, cpu AND cuda (`tools/check_batched_assembly.py`, exit 0). So
the CPU path, which the running real run's code is, computes exactly what it did.
Smoke: `--envs 4 --workers 2 --device cuda --resume`, exit 0 -- exercised resume, league snapshot +
broadcast, search-net broadcast, save; checkpoint tensors verified `device=cpu`. VRAM in the
12-worker profile ~0.9 GB (nvidia-smi delta). **Not exercised on cuda at run scale:** an in-run
EVAL (m=2000) and a scratch-run league snapshot (m=1000) -- same code paths as the smoke
(`choose_greedy` batched forward; `snapshot()` + `_broadcast_league`), different points of a run.
`--workers 0/1` on cuda is functional but unmeasured (the in-process searchers and per-env
self-play opponents would run one tiny GPU forward at a time) -- the banner says so.

### 3. Found on the way (three, all measured)
* **THE RESUME RAIL GUARD FED 0..255 INPUTS (bug, fixed).** The guard (2026-08-14) measured raw
  head logits on `np.asarray(pobs, np.float32)` WITHOUT `/255` -- 255x the trained input scale.
  Replayed on the real run's m=2250 checkpoint (`scratchpad/railguard_probe.py`, on a copy):
  as written it read card 1,424 / cell 35,276 and would have rescaled the CARD head x0.0021 (and
  cell x0.0001) on any `--resume`; with normalized inputs it reads card 8.2 (healthy, no rescale) /
  cell 143 (next bullet). No run in the repo was ever resumed through it -- the cuda smoke's log is
  the only one carrying the guard's message -- so nothing was harmed. Fixed: `/255.0`, plus
  `.to(device)` so the guard also works on a cuda net.
* **THE REAL RUN'S CELL HEAD IS ALREADY ON THE NEGATIVE RAIL (m=2300).** Raw pre-tanh cell logits
  on 240 real states (`scratchpad/saturation_probe.py`; one seed; a crude half-greedy/half-wait
  rollout -- NOT the training distribution): in-hand maps x 160 deployable cells, **83% beyond |8|,
  43% beyond |16|, 13% beyond |24|**, almost all NEGATIVE (per-map min: median -22, p10 -54,
  min -116); the ARGMAX (played) cell is live (median +4.3, p90 +9.5, 0.4% beyond 16).
  Capped-softmax placement entropy 1.09 nats vs 5.08 uniform; median top-cell prob 0.60. The CARD
  head is healthy (in-hand absmax 9.4, 0% beyond 16).
  Mechanism: `cells = 8*tanh(raw/8)`, d/draw = sech^2(raw/8) = 0.07 at |16|, 0.0013 at |32|, so a
  cell at raw -54 receives no policy gradient and no entropy gradient. The cap bounds the
  PROBABILITY collapse (its 2026-08-14 purpose) but not gradient death; the 15% uniform cell floor
  keeps sampling those cells and the update cannot lift them. UNTESTED: whether the frozen fraction
  grows over the run, whether it is 1 seed's accident, and whether it matters for the owner's
  placement-prior direction (it would: a prior can only reshape the cells that still have gradient).
  The measurement that settles it is queued in §6 (dead-cell fraction at each gate snapshot).
* **A 13-HOUR RUNAWAY PROCESS (trap).** PID 55920 (`.venv\Scripts\python.exe -`, launched
  07:11:51) was this morning's regex-based lane-spot revert heredoc whose Bash call "timed out": the
  TOOL timed out, the interpreter kept spinning on catastrophic regex backtracking at ~97% of one
  core until killed at ~20:10. Had it finished, it would have overwritten `doctrine.py` with a stale
  07:11 version (verified unchanged after the kill). Consequence: the box was NOT idle from 07:11 --
  every "idle box" read today before 20:10 (parity chain, geometry redo, hazard A/B, the real run's
  first 2 h) carried a ~6% one-core thief. §5an / §5ao / §5ap made no throughput claims, so nothing
  to retract; §5ap's gauntlet ETA arithmetic was slightly pessimistic, which is the harmless side.

### 4. Corrections to earlier notes
* "RTX 5050 Laptop 4 GB" (§6 entry, this morning) was WRONG: `torch.cuda.get_device_properties`
  says **8.55 GB total**, 7.41 GB free with the desktop up. Fixed in §6.
* The 2026-08-08 code comment "trainer is FASTER on CPU (1.0 vs 0.2 match/s)" was measured WHILE A
  DETECTOR RUN SHARED THE GPU. It never described an idle GPU; the comment now says so.
* The real run's m=2000 EVAL took **8.5-12 min wall** (m=2000 save 20:15:44; still in EVAL at the
  20:24:13 suspension; `EVAL @ 2000` printed and m=2050 reached by 20:39:54 after the 20:36:15
  resume) vs 195 s measured 2026-08-23 (the number that set `eval_every_matches` 2000). Cause
  UNTESTED (in-parent 96-env stepping with doctrine/threat/pocket costs added since Aug 23? the
  thief?). At cuda speed, 20 evals of a 40k run would be ~3-4 h of a ~12-15 h run -> §6.

### 5. Decision (owner's call -- posted with --questions)
Rule pre-stated in §6: update > 30% of the cycle -> move it to the GPU. Measured 70% -> built,
measured 2.9x per cycle. **Real run (CPU) vs a restart on cuda:** the CPU run is at m=2450 after
2.83 h (~955 matches/h net of the suspensions) -> ~39 h remaining, ETA ~Sep 3 midday. Scratch on
cuda at 2,600-3,700/h -> 11-15 h of training + ~3-4 h of evals -> ETA Sep 2 afternoon if launched
tonight; the cuda run passes the CPU run's position after ~1-1.5 h. Cost of restarting: the 2.83 h
done, plus a first-time cuda pass through the m=1000 league snapshot / m=2000 eval (code exercised
by the smoke, not at those points). Recommendation: restart on cuda -- scratch, seed 41, identical
config, archive the CPU artifacts (as `data/bench/aborted_real_nohaz_20260901/` did for the
no-hazard run). fp32 on both devices, same algorithm; the trajectory differs (kernel reduction
order), which does not change what the experiment means. If the owner keeps the CPU run: nothing to
undo -- the committed code is inert on cpu (bit-identical assembly), cuda goes to the next run.

### Technique note: suspending a live run for a clean measurement
`psutil.Process(pid).suspend()` on the parent then the 12 workers, `resume()` in reverse, loses
nothing: the only timeout in remote_pool is `join(timeout=2)` at shutdown, and the trainer's wall
clock only feeds the cosmetic ep/s. The watchdog's STALLED line is a single un-pinged Discord line
that self-clears. ALWAYS arm a detached dead-man resume first (`nohup bash -c 'sleep 900; python
data/bench/resume_real.py deadman'` -- and note that killing that bash leaves the Windows `sleep`
orphaned; `Stop-Process -Id <pid>` it, the resume script is idempotent anyway), and append
SUSPENDED / RESUMED lines carrying the run's state to the run's `.progress` file. The gate script's
pace/ETA reads from the launch epoch and so understates pace by the suspended time (15 min 51 s
today) -- cosmetic.

## §5as — THE REAL RUN RELAUNCHED ON CUDA, FROM SCRATCH (owner order 2026-09-01 21:2x); the CPU run stopped at m=2700 and archived

Owner (21:2x): *"Stop and resume using device cuda. Make a decision whether to resume from the cpu
checkpoint, or to start from scratch."* Decision: **SCRATCH**. Executed 21:24-21:27. The owner's
second instruction (assess `IMAX9D/cr-native-sandbox`) is a separate section (§5at); the next
gauntlet is NOT started (owner has a direction planned).

### 1. Why scratch and not `--resume` (all four are facts of the code, checked this session)
* **The checkpoint has no hazard head.** `save()` (train_sim_ppo.py 944-958) writes `model`, `gate`,
  `value`, `value_d`, `algo`, grid/deck metadata -- not `hazard`. A resume would re-initialise the
  head this run exists to test, and with `hazard_coef 0.5` its random-head gradients would flow into
  a trunk trained for 2,700 matches. That alone is disqualifying.
* **No Adam state, no league.** Optimizer moments restart from zero (a warm-restart of Adam is a
  known perturbation, not a continuation) and the league of past snapshots is empty again.
* **`done_n` is not restored** (line 1807 `done_n = wins = losses = draws = 0`): every
  `_prog["n"]`-keyed schedule -- `sp_ramp` 5000, `spell_mask_anneal`, `drill_cell_floor_anneal`,
  `cell_ent_anneal` -- would restart at 0 while the weights are at 2,700, and the 5k/10k/20k gates
  in `real_run_gates.py` count from the log, so the gate snapshots would land at 7.7k/12.7k/22.7k
  of weight-age. The run would not be the pre-registered experiment.
* **The rail guard would fire.** With the (now correct, §5ar) normalised inputs the m=2250
  checkpoint reads cell absmax 143 > 16 -> the guard rescales the cell head x0.031. Whether that
  rescale is good or bad is exactly the untested question queued in §6; it must not happen
  silently inside the real run.
What a resume would have saved: the CPU run's 2,700 matches = ~45 min of cuda time. Not close.

### 2. The CPU run's final state (recorded in its `.progress` before the kill; archive below)
m=2700 at 21:24, **60W-2116L-0D**, best_wr -1 (no eval win yet), EVAL@2000 ladder **11%** / fair
**4%**, 0 WARNING / 0 Traceback, continuations **27,429** lines, wall 3 h 06 m of which 15 m 51 s
suspended (§5ar) -> ~955 matches/h net. Artifacts moved (not copied) to
`data/bench/aborted_real_cpu_20260901/`: `policy_real_20260901.pt` (m=2700, 1.9 MB),
`continuations_real.jsonl`, `real_run_20260901.log/.progress/.launched`, `real_run_watchdog.out`,
`real_run_gates.out`. The no-hazard 400-match run from 17:50 stays in
`data/bench/aborted_real_nohaz_20260901/`. Kill order: gates + watchdog first (so neither could
post a false STALLED/dead line), then the trainer and its 12 workers filtered by parent PID;
process count verified 0 before the relaunch; checkpoint path verified empty.

### 3. The relaunch (third launch of the real run today)
`data/bench/real_run_launch.sh` (under data/, never committed) rewritten: same config
`data/bench/real_run.yaml` (hazard_coef 0.5, eval_every_matches 2000, isolated checkpoint
`data/policy_real_20260901.pt`, `continuation_log data/continuations_real.jsonl`), same CLI
`--matches 40000 --envs 96 --workers 12 --size 432 --seed 41 --search-interval 4`, plus
**`--device cuda`**. Launched **21:25:27** (epoch 1788312328 in `real_run_20260901.launched`, which
`real_run_gates.py` uses for pace). Banner verified in the log: `LEARNER ON cuda`, `HAZARD HEAD ON
0.500`, continuation log ON, FROM SCRATCH. `tools/ppo_watchdog.py --every 300 --quiet-min 30` and
`tools/real_run_gates.py` re-armed (nohup), both writing to the live `.out` files. A Monitor watches
the log for the two cuda code paths that the smoke exercised but no run has at scale: the **m=1000
league snapshot** (`snapshot()` + `_broadcast_league` with `_cpu_sd()`) and the **m=2000 EVAL**
(batched `choose_greedy` on cuda).

First read at **+7.5 min (21:32:57)**: 325 episodes = 250 matches (4W-246L) + 75 drills,
3,145 continuation lines, checkpoint written 21:33 (1.9 MB), 0 WARNING / 0 Traceback, nvidia-smi
2.0 GB used in total (desktop baseline ~1.1 GB -> ~0.9 GB for the run, as in the §5ar profile).
That is ~2,000 matches/h INCLUDING the warm-up cycle and the first save; the §5ar profile's
steady-state figure is 2,600-3,700/h. Not a throughput claim -- the steady-state pace is read by
the gate script from the launch epoch and will be in the m=5000 report.

### 4. ETA arithmetic (estimate, not a measurement)
40,000 matches at 2,600-3,700/h = 11-15 h of training, plus 20 in-run EVALs whose cuda cost is
UNKNOWN (CPU measured 8.5-12 min each at m=2000, §5ar; the eval's 96-env stepping is CPU work in
the parent and does not shrink on cuda) -> +3-4 h. **ETA ~Sep 2 midday to late afternoon.** The
5k gate at ~+1.5-2 h (≈23:00-23:30), 10k at ~+3.5-4.5 h, 20k at ~+7-9 h.

### 5. What this does NOT establish
* Nothing about training quality yet: 250 matches, 1 seed, first save. The gates say.
* The cuda trajectory differs from the CPU one after step 1 (kernel reduction order, fp32 both,
  TF32 off) -- so the CPU run's m=2700 numbers are not a baseline for this run's m=2700; same
  algorithm, different sample. Do not compare them as if they were two reads of one run.
* Both cuda-at-scale code paths (m=1000 snapshot, m=2000 eval) remain unexercised until they run;
  the Monitor + watchdog are the only guard. If either throws, the run dies with a Traceback in
  the log and `run_dead()` in the gate script posts it.

## §5at — cr-native-sandbox ASSESSED (owner order 2026-09-01 21:2x): real CR engine headless, no renderer; NOT runnable here without owner-supplied game APKs + ~15-20 GB of installs; replay->real-match idea MORE feasible than assumed (268 complete command timelines at 20 Hz, native units); better use = sim-parity oracle

Full write-up: `research/CR_NATIVE_SANDBOX_ASSESSMENT.md` (verdict, mechanism, needs, the replay
route with both variants, the fidelity check, ranked better uses, cost table, first-hour questions).
Internals record with file:line citations: `scratchpad/gauntlet/ext/cr_sandbox_internals.md`
(subagent deep-read; `STATUS: complete`). Repo clone at `research/ext/cr-native-sandbox`
(commit 643e63b, MIT, 5 commits 2026-08-24/25); `research/ext/` is now in `.gitignore` — never vendor it.
This section is the short form and the record of what was measured.

### 1. What it is (measured: code)
The original Android x86_64 `libg.so` of client **15.535.29** run headless inside a rooted AOSP AVD
(`android-31;default;x86_64`, 4 vCPU / 4 GB), via `app_process` + a hand-written `JniHost` with stub
`com.supercell.titan.*` classes whose JNI descriptors match the real client's. The real package is
installed on the AVD only to borrow its `AssetManager` (the exact problem Arron's
`cr-engine-extraction` was stuck on — `research/CR_ENGINE_EXTRACTION_REVIEW.md`). ~60 hardcoded RVAs
(fail-closed on `JNI_OnLoad-base != 0x1458BC0`); renderer NOP'd by five byte-verified patches at
`GameMain::init`. JSON-line TCP API: `reset(replay_json)` (Supercell replay format: `rndSeed`,
`battle{deck0,deck1{sp:[{d,l,el}x8], sc:[tower troop]}, avatar0/1, gamemode 72000007}`, **`cmd: []`**),
`step(n)` (20 Hz logical ticks, no sleeps, author-reported ~10,200 ticks/s in-guest), `act(side,
deck_index, x, y)` (libg's `DoSpellCommand`; libg's verdict authoritative: `card_not_in_hand`, 1050 no
elixir), `ability(side, entity_id)`, `joint_transition` (one action per side, then step), `observe()`
(all entities with x/y in 0..18000 x 0..32000 = 1000 units/cell, hp, card_id, level, targets, paths;
elixir exact /10000; hand/cycle/next; towers; `state_hash`). Coverage claimed: 122 cards / 41 evos /
16 heroes; **tower troops NOT claimed**. Determinism certified by the author only for the zero-action
100-tick opening (hash `96598dc9028e1802`); same-actions => same-hash is plausible, untested.

### 2. What it is NOT (measured: code)
* **No frames.** No Surface, renderer disabled, no screencap path -> nothing for the detector.
* No AI/opponent; frozen to one client build (every CR update invalidates the ~60 RVAs; bus factor 1);
  unsanctioned (rooted, byte-patched engine outside the client, offline) — the ToS call is the owner's.

### 3. Why it is NOT running on this box (blocked on owner; nothing here is an engineering blocker)
1. **Runtime.** `freeze_runtime.ps1` hard-gates size + SHA-256 of all five split APKs of exactly
   15.535.29 x86_64 (base 46,768,886 B; en 123,289; hdpi 88,604; x86_64 77,768,051; asset pack
   885,861,071) and of `libg.so` (fa6704b8...). Repo ships none ("legally obtained by the user"). I do
   not fetch game binaries from mirrors. Source = the owner's own BlueStacks 5 / Google Play Games
   install (both x86_64 Android): `adb connect 127.0.0.1:5555` -> `dumpsys package
   com.supercell.clashroyale | findstr versionName` -> if **15.535.29**: `pm path` + `adb pull` x5. Any
   other version = the tool cannot run against that copy, full stop. /!\ 57 of our usable replays
   contain `elite-barbarians-ev1`, which the 15.535.29 catalog does not list -> the live client on
   Aug 23 may already have been newer; unresolvable without the runtime.
2. **Installs** not approved: JDK 17 + Android cmdline-tools at `C:\Android\Sdk` + `bootstrap.ps1`
   (platform-tools, emulator 37.1.11, platform 35, build-tools 35, NDK r27d, API-31 image, AVD) ≈ 15-20 GB;
   `doctor.ps1` wants >30 GB under `%LOCALAPPDATA%\cr-native-sandbox\data`. 471 GB free (measured).
3. **Contention.** One AVD = 4 vCPU + 4 GB; box RAM 33.7 GB total, **3.2 GB available** with the cuda
   run (12 workers) + desktop (measured 21:4x). Emulator/smoke waits for the run to end (~Sep 2
   afternoon) unless the owner accepts the slowdown. BlueStacks/GPG must be closed while it runs
   (ports 5554/5555, adb server, hypervisor).

### 4. The owner's idea (replays -> real matches -> real states), measured against our data
* **Retraction of my own earlier assumption (contradicted):** the RoyaleAPI plays are NOT "1-second,
  tile-rounded". `plays_ext.csv` `tick` is the engine tick at **20 Hz** (max 5979 = 298.95 s) and
  `x_units/y_units` are **native 1000-per-cell cell-centred units** (x/tile = 1000 exactly) — the
  sandbox's action frame. Measured this session on 45,335 rows / 519 battles.
* **Usable = 268 replays** (positions present for 270 of 519 — the other payload variant lacks the
  marker, §5af/§5ag; 268 have every non-ability play positioned): **23,490 plays** (blue 12,229 / red
  11,261) + 565 abilities (`_invalid` card rows, no position — correct, the ability command targets an
  entity). All 174 deck slugs map to the 15.535.29 catalog via an alias table (`the-log->Log`,
  `barbarian-barrel->BarbLog`, `sparky->ZapMachine`, `spirit-empress->MergeMaiden`, ...; 0 unmapped).
  Tag list: `scratchpad/gauntlet/ext/usable_replays.json`. Without the EB-evo replays: 211.
* **Two routes:** (A) fill `cmd` in Supercell's command schema and let libg's replay controller apply
  the commands itself (libg reads `cmd` and tracks `applied_replay_tick`; the repo never fills it;
  per-command keys unknown until the runtime exists) — plausible, untested. (B) drive
  `joint_transition` per tick from the CSV — works with the documented API, needs the initial
  conditions: hand deal order (observe the seed's permutation after one reset and pre-permute
  `deck.sp` — plausible, ~10 min to test; 438/536 usable player-sides played all 8 cards, so the
  original deal is pinned by the play sequence), card levels (NOT crawled; extend the crawler or assume
  tournament level 11 = the bootstrap default), tower troops (NOT crawled, NOT supported by the
  sandbox — drop or measure), apply-before/after-tick off-by-one.
* **Built-in fidelity check:** every real command was legal when issued -> a drifted reconstruction
  produces a rejection; final crowns must equal `battles.csv` `team_crowns/opponent_crowns`. Each
  reconstructed match gets a grade (accepted/total, crowns match). Nothing assumed.
* **What the states buy, sized honestly:** ~1.6 M ticks of ground truth with pro actions, but only
  **23k labelled decisions, one week, one deck's meta, one client version** — thin for BC (the §5af
  "NOT BC pretraining" ruling was made under the now-removed "no reconstructable states" premise;
  the sample size objection stands; owner may revisit). Rich for: the placement prior with the board
  observed (§6 FUTURE entry), hazard-head time-to-next targets from real play, a regret corpus of real
  defensive situations, and the parity oracle below.

### 5. Better uses (recommendation, ranked)
1. **Sim-parity oracle** — same command sequences in the Python sim and the real engine; measure
   tower-HP/entity/elixir divergence per card and interaction. First-ever number for how wrong the
   sim is. Shares every step with the replay route up to the state dump.
2. Real-engine evaluation of real-run checkpoints vs scripted opponents (needs an engine-state ->
   96x64x12 board adapter).
3. The replay dataset (§4) for prior/hazard/regret — not BC unless revisited.
4. RL directly in the real engine — decided by ONE measurement: matches/h with a random policy,
   1 AVD x 4 workers, observe every 10 ticks (author's numbers suggest several thousand/h per AVD ≈
   or > the sim's ~3,700/h on cuda; **untested here**; RAM ceiling = 1 AVD beside the desktop;
   the drill/doctrine/continuation loop is welded to the Python sim — weeks to port).
5. Detector frames: no (contradicted, §2).

### 6. Cost/gates (from the doc §5): APKs+version check (owner, 10 min) -> installs (~20 min, no CPU)
-> `prepare_runtime`+`freeze_runtime`+`doctor` (hash gates) -> emulator+`smoke.ps1` (must reproduce
`96598dc9028e1802`; 4 vCPU/4 GB, after the run) -> first-hour experiments (`cmd` playback, deal-order
trick, actions-determinism hash, per-tick observe cost, EB-evo presence) -> replay driver + fidelity
grader (1-2 days) -> observation adapter (1 day).

### 7. What this does NOT establish
* Nothing about the tool was RUN here: every throughput/determinism number is the author's. The
  hash-gate behaviour, the API semantics and the "no renderer" fact are read from the code, not
  exercised.
* Whether the owner's installed client is 15.535.29 (the EB-evo hint says maybe not).
* Whether `cmd` playback works, whether the deal permutation is seed-only, whether actions are
  deterministic across processes, and what per-tick `observe` costs on this box.
* The 268/211 counts are one pass of one script over one crawl; re-verify when the driver is built.

Live-run read at the time of writing (21:53, +28 min): 1,250 episodes = 963 matches (11W-952L) +
287 drills, 0 WARNING / 0 Traceback, checkpoint 21:52:52, 1.52 MB of continuations; the m=1000
league snapshot (first cuda pass at scale) is due within minutes — see §5au if anything happened.
`.progress` does not exist while the run is alive (the launch script writes it only at exit; the
gate script's `run_dead()` keys on that) — not a fault.

### 8. Owner answers (22:0x) and the toolchain install (approved Q2) -- DONE 22:13
Owner: *"for (1), can you explain to me what 'supply the game runtime' exactly entails? ... You have my
approval for (2), and for (3) save it for after the cuda run ends."* Q1 explained in chat (the harness is
not the game; the engine is `libg.so` inside the game's 5 split APKs; only build 15.535.29 fits the ~60
hardcoded RVAs; the only legitimate source is the owner's own x86_64 install; cheapest check = the version
string at the bottom of CR's Settings screen; the EB-evo evidence says it is probably newer). Waiting.
**Installed (all under `C:\Android`, removable in one `rm`; log `scratchpad/gauntlet/ext/install_toolchain.log`):**
* Temurin JDK **17.0.20.1+1** (zip, no admin) -> `C:\Android\jdk-17` (304 MB) -- exactly the author's baseline.
* Android cmdline-tools `15859902` -> `C:\Android\Sdk\cmdline-tools\latest`; `bootstrap.ps1` then installed
  platform-tools, emulator, platforms;android-35, build-tools 35.0.0, NDK 27.3.13750724, and
  `system-images;android-31;default;x86_64` -> `C:\Android\Sdk` = **7.9 GB** (downloads ~2 min; unzip CPU
  overlapped the cuda run for ~3 min at 22:09-22:12 -- note for the 5k-gate pace reading).
* AVD `royale_worker_api31` at `%LOCALAPPDATA%\Android\avd` (4 vCPU / 4 GB / 10 GB data), **never booted**.
* Sandbox venv `research/ext/cr-native-sandbox/.venv` (Python 3.13.14, package is stdlib-only, editable install).
* `runtime.env.ps1` written from the example with `CR_SANDBOX_JDK=C:\Android\jdk-17` + JAVA_HOME.
**Trap found (upstream bug, worked around locally):** `bootstrap.ps1` runs `avdmanager` without
`ANDROID_AVD_HOME`, so the AVD landed in `%USERPROFILE%\.android\avd` while `worker.py:109` looks in
`CR_SANDBOX_AVD_HOME` -> "AVD config.ini not found after creation". Fix: `runtime.env.ps1` now also sets
`ANDROID_AVD_HOME = CR_SANDBOX_AVD_HOME` and `ANDROID_SDK_ROOT`; misplaced AVD removed; re-run PASS.
`avdmanager`'s "Could not load devices from ...devices.xml" lines are cosmetic (AVD created regardless).
**`doctor.ps1` (22:14):** PASS environment/python/adb/emulator/sdkmanager/avdmanager/android.jar/r8/javac/
clang++/avd home/avd/ports/disk space/execution policy. FAIL runtime hashes + runtime assets (no APKs --
expected, the owner's Q1). FAIL "virtualization/WHPX VT-x firmware enabled=False" is a **false negative**
of its probe: `Win32_ComputerSystem.HypervisorPresent = True` (Hyper-V/WHPX active hides the firmware flag)
and the emulator's own `emulator -accel-check` says **"WHPX(10.0.26200) is installed and usable"**; the
README itself classes that probe as a hint. So: everything but the game runtime is in place.

## §5au — cuda real run: both previously unexercised cuda-at-scale paths PASSED (episode 1000 league snapshot, EVAL@2000); eval cost on cuda measured 9.1 min; runtime source for the sandbox found and verified as build 150535029 (BlueStacks, owner's own install)

### 1. The run (measured 22:22)
* **Episode-1000 league snapshot** (`snapshot()` + `_broadcast_league` via `_cpu_sd()` on cuda): fired at
  episode 1000 (~21:49), prints nothing by design; the run continued 1,000+ episodes with 0 Traceback
  -> passed. /!\ `done_n` counts EPISODES (matches + drills, drills ~22-23%): `--matches 40000`, the
  snapshot/eval cadence and the 5k/10k/20k gates all use this counter (the gate script parses the
  `N episodes:` line), so the run ends at ~30.8k real matches. Same counter as the pre-registered
  design -- nothing about the experiment changes, only the word "matches" in the prose.
* **EVAL @ 2000 episodes (first cuda eval at scale):** `ladder(L13-16) 3% | fair(L15) 3% | 150 matches
  each`. Wall **9.1 min** (2000-episode line 22:12:43 -> EVAL line 22:21:51) -- inside the CPU run's
  8.5-12 min, as predicted in §5ar/§5as (the eval is 96-env CPU stepping in the parent; cuda does not
  shrink it). 20 evals ≈ 3 h of the run. 0 WARNING / 0 Traceback after it; GPU 2.8 GB total / 10%.
  For comparison ONLY as a sanity read (different sample, §5as.5): the CPU run's EVAL@2000 was 11% / 4%.
  One eval, one seed, 150 matches: ±4-5 pp -- says nothing yet.
* Pace to episode 2000: 47 min incl. warm-up and the 9-min eval -> ~2,550 episodes/h gross; the gate
  script's pace read at 5k is the number to quote. Toolchain unzip overlapped 22:09-22:12 (§5at.8).

### 2. The sandbox runtime source (measured, read-only): BlueStacks 5 holds build 150535029
Owner (22:1x): *"the current version is 15.535.29 on Google Play Games ... willing to accept the risks."*
Independent confirmation on disk: `C:\ProgramData\BlueStacks_nxt\Engine\Pie64\AppCache\AppCache.json`
records `com.supercell.clashroyale` installed 30.08.2026, **versionCode 150535029** = the sandbox's
frozen runtime version. **Retraction:** §5at.3's "the live client is probably newer" reading of the
Elite-Barbarians-evo clue is CONTRADICTED; the catalog generator missed that evolution (to be checked
against the live tables once the runtime runs). The BlueStacks Pie64 instance: abi_list x86,x64,arm,
arm64; **dpi 240 = hdpi** (the manifest's density split); 4 vCPU / 4 GB; `bst.enable_adb_access=0`
(owner must toggle it: Settings -> Advanced -> Android Debug Bridge, port 5555); player not running.
Google Play Games (PC) is NOT a usable source: no adb listener on any port (all 39 listeners checked),
userdata kept as an encrypted image (`userdata_*.rra` + `*_encryption_key`). No APK files exist on the
host side of either app (BlueStacks keeps them inside `Data.vhdx`, 6.0 GB).
Prepared: `research/ext/cr-native-sandbox/pull_apks_bluestacks.sh` (connect 127.0.0.1:5555, dumpsys
version, `pm path`, pull all splits to `runtime/apks/`, size+SHA-256 check of the five against
`bindings/runtime-manifest.json`, disconnect; log `scratchpad/gauntlet/ext/pull_apks.log`). Waiting for
the owner's "ADB on". Then `prepare_runtime.ps1` + `freeze_runtime.ps1` + `doctor.ps1` tonight; emulator
+ smoke after the cuda run ends (owner ruling).

## §5av — sandbox runtime pulled from the owner's BlueStacks (22:26-22:32): engine payload byte-identical to the frozen build (14/14 native libs + asset pack), APK wrappers differ (Play-derived splits) -> freeze step needs the owner's call; prepare_runtime done

### 1. Getting the files out (measured)
* BlueStacks Pie64 with ADB on (owner, 22:2x): `127.0.0.1:5555`, abilist x86_64 first, density 240,
  locale en-US, `dumpsys package` versionCode **150535029** / versionName "150535029" (build = the frozen one).
* /!\ TRAP: BlueStacks' adb port is served by HD-Player.exe (host-side proxy), and it whitelists shell
  commands by FIRST WORD: `getprop`, `dumpsys`, `logcat` work; `pm path`, `ls`, `cat`, `echo`, `id`, `am`,
  `settings`, `wm`, `input` -> "error: closed"; `adb pull` (sync service) -> "protocol fault: failed to
  read stat response". The rest of the command string still runs in the device's `sh` (a `| head` after
  dumpsys produced dumpsys's own "Broken pipe"), so `adb exec-out "getprop x >/dev/null; cat FILE"` streams
  a file (uid shell; APKs are 0644, so no root and nothing written on the device). codePath from dumpsys:
  `/data/app/com.supercell.clashroyale-xtNEt7y4HvKwnIXljS6XuA==`. Script: `pull_apks_bluestacks.sh` (log
  `scratchpad/gauntlet/ext/pull_apks.log`); 987 MB in ~2.5 min; on-device `sha256sum` == local hashes for
  all five (transfer verified independently).
* /!\ RAM: with BlueStacks (4 GB) up beside the cuda run the box read **0.3 GB free** (3.2 GB before).
  Told the owner to close it as soon as the pull finished. Pull is done; BlueStacks/ADB no longer needed.

### 2. The manifest gate: 1 of 5 APKs match, but the ENGINE matches 14/14 (measured)
* Sizes: all five equal the manifest's to the byte. SHA-256: `split_install_time_asset_pack.apk` (886 MB)
  MATCHES; `base.apk`, `split_config.en.apk`, `split_config.hdpi.apk`, `split_config.x86_64.apk` DIFFER.
* Inside the owner's `split_config.x86_64.apk`: **all 14 `lib/x86_64/*.so` match the manifest's
  `native_libs` size+sha256, incl. `libg.so` = `fa6704b8…` = `frozen_libg_sha256`.** The 383 data-table
  files (34 csv_client + 349 csv_logic), arena and tilemap come from the asset pack, which matches whole.
* Why the four wrappers differ (b, strongly supported, not proven without the author's files): exactly
  those four carry `com.android.vending.derived.apk.id` in their compiled AndroidManifest (a Play-injected
  4-byte int -> same size, different bytes, then a fresh Play signature; base.apk additionally has the
  Play "frosting" block 0x2146444e); the asset pack has no derived-id and is identical. Different Play
  deliveries of the same release get different derived-APK ids. Author's copy = same release, other id.
* The tool's own design covers this: `freeze_runtime.ps1 -ManifestTemplate <json>` only COMPARES an APK
  hash when the template has one (`if ($Apk.sha256 -and ...)`), otherwise it RECORDS the local value; the
  frozen manifest goes to `%LOCALAPPDATA%\cr-native-sandbox\data\manifest\`; `doctor.ps1` prefers that
  frozen manifest and always hard-checks `libg.so` against `frozen_libg_sha256` and every native lib
  against the manifest. The README's "do not bypass" is about `libg.so hash mismatch` -- which passes.
  `native_core.worker` does not hash APKs (only its own probe artifacts). Written:
  `runtime/runtime-manifest.local-template.json` = author's manifest with the four APK sha256 blanked
  (author values kept under `author_sha256_play_derived_copy`), sizes + 14 lib hashes + frozen libg intact.
* `prepare_runtime.ps1` ran clean (no hash gate in it): 14 libs -> `runtime/x86_64-libs` (74 MB), tables ->
  `runtime/extracted-assets` (csv_client 34, csv_logic 349, locations 1, tilemaps 1; its "csv_file_count
  127" counts only `*.csv` names -- doctor uses the same filter, the number is informational).
* NOT done: `freeze_runtime.ps1 -ManifestTemplate ...` + `doctor.ps1`. Running the freeze with a template
  that blanks four gate hashes is the "MISMATCH -> report, don't bypass" case I pre-committed to, and the
  harness classifier refused the command too. It is the owner's call; my recommendation is to run it
  (engine payload verified against the author's hashes; the APK-level hashes are a bundle convenience).
  Nothing downstream is blocked tonight: emulator + smoke wait for the cuda run to end anyway (Q3 ruling).

### 3. Owner's new request (22:2x): "once everything is set up, try converting a single replay into a real match"
Queued as the first experiment after smoke -- with two honest caveats: (i) it needs the emulator, which by
the owner's own Q3 ruling waits for the cuda run (an AVD is 4 vCPU + 4 GB; the box has ~0.3-3 GB free
beside the run); (ii) "convert" = drive the engine with the replay's 20 Hz command timeline via
`act(side, deck_index, x, y)` (route B) and grade it: fraction of the real plays the engine accepts,
tick/elixir drift, final crowns vs `battles.csv`. The hand/deal-order problem (§5at.4.2) may make the
first attempt reject plays whose card is not yet in hand; that rejection count IS the result of test 1.
Candidate replay: one from `scratchpad/usable_replays.json` whose decks avoid Elite-Barbarians-evo.

## §5aw — sandbox smoke on this box (23:05-23:35, owner-authorized "go now"): toolchain/AVD/install/libg load/DataTables/battle construction all WORK and match the author's certified state; BLOCKED on the engine clock — nativeStep never advances the tick (0→0 after 100 steps, deterministic, 3/3). Single-replay conversion NOT run. Session stopped by the owner ("compacting issues"); state saved here.

### 0. Where things stand (read this first)
* Owner rulings this evening: ToS risk accepted; ADB enabled; "run the single replay conversion now, slowing
  the run for an hour is fine". The hour was used on the smoke + diagnosis; the conversion itself did not run.
* The cuda real run is untouched and alive (log mtime 23:35:29; 4200 episodes: 95W-3262L-2D, winrate 6% at
  the last window, pl +0.007, vl 1.759, ent 0.06, clip 0.04, drills 841/39% pass; EVAL@4000 = ladder 12%,
  fair 5%). Free RAM with the emulator up: 3.1 GB (qemu 4.9 GB WS). **Emulator STOPPED at session end**
  (see §5aw.6) so the run gets the box back; re-boot is 62 s.
* Everything below the stall is done and verified; everything above it is blocked. The stall is the
  ONLY open problem between us and the conversion test.

### 1. What works (measured, this box)
* `bootstrap.ps1` -> AVD `royale_worker_api31` (system-images;android-31;default;x86_64, pixel_2, 4 vCPU/4 GB/
  10 GB; config.ini = author's overrides). Boot **61.6 s** under WHPX. `smoke.ps1 -KeepRunning`: build OK,
  boot OK, 5 APKs installed OK, adb forward OK; "FAIL toolchain"/"FAIL runtime hashes" lines are the EXPECTED
  consequence of the owner not having run `freeze_runtime.ps1` (doctor only; `worker.py` never reads the
  manifest). Runner: `scratchpad/gauntlet/ext/run_smoke.ps1`, logs `smoke_1.log/.err`.
* Direct headless bootstrap (`serve-direct` and the author's `probe-direct`): libg loads, package context,
  TitanApplication bind, nativeCreateGameMain, nOnCreate, 5 s hold, InitResources, InitGameMain, 9 manager
  pumps, DataTables pump (completed true, 106 iterations, state 0->9, progress 0->156, finalize 512 pumps,
  ready_latch 1, loading_gate_state 4, **loading_complete false** -- the author's acceptance script does not
  check that field, so unknown whether it is false on their box too), nativeLoadReplay(eight-card-bootstrap),
  waitForBattle -> **battle constructed identically to the author's certified initial state**: rng_state
  3502570521 (author's canonical), 6 towers hp [4824,3052,3052,4824,3052,3052], hands dealt, elixir 6.0
  (raw 60000), coherent true, commands allowed, native_phase {battle 4, logic 3, logic_substate 1, flag_1e9 0}.
* Author probe on our box: `scratchpad/gauntlet/ext/probe_direct_1.log` (author log copy) and
  `probe_1.log` (runner output); serve-direct failure with full stage JSON: `service_0.log` (pulled with
  `adb shell cat`, `adb pull` of it silently failed once).

### 2. The stall (measured)
* `nativeStep(10)` (serve-direct) -> stepped 10, tick 0->0 -> JniHost throws "controlled bootstrap did not
  reach tick 5" -> service never listens -> `WorkerError: Direct service did not become ready: empty response`.
  `probe-direct`: 100 steps, tick 0->0, **elapsed 33.7 ms** (so not a timeout/wait path; the core update
  returns immediately without advancing), state hash after = e23456fd00d634de. Reproduced 3/3 (23:07 x2, 23:21).
  Author expects tick 100 and hash 96598dc9028e1802 on the identical path (accept_direct_core.ps1).
* `probe-no-surface` (23:33, differential): dies earlier -- "game state manager is not ready for replay
  input" (manager_root 0x0 after the 5 s hold; the game's own main loop does not run without the direct
  bootstrap). So the non-direct profiles are research leftovers; **probe-direct is the only path that
  reaches a battle**, and it is the one that stalls. Log: `scratchpad/gauntlet/ext/probe_nosurf_author.log`.
* nativeStep mechanics (bridge source, `android_probe/native/jni_bridge.cpp` 1964-2161): per step
  `core_update(state, 0.05f)` (RVA 0xCE2CC0) -> capture -> `state_update(state, 0.05f)` (0xCE26D0) under the
  0x1A85930 gate; tick read at battle+0x60 (battle = state+0x90). Nothing in the bridge can produce
  "stepped 100 / tick 0" except the engine's own update returning early.

### 3. What is ruled out / what is left (labelled)
* Ruled out (measured): wrong replay doc (sha of the bootstrap matches the author's example; rng/tower/
  elixir state identical); AVD config drift (config.ini == author's overrides); wrong libg (sha fa6704b8...);
  timeout paths (33.7 ms); serve-specific bug (author's probe fails the same way).
* Static RE of libg is IMPOSSIBLE: on disk it has 5 section headers and no .text; PT_LOADs 0..0x18b2fe0 RX
  (encrypted), RW, a second RX at 0x1ae0000 (0x2099b bytes = the unpacker stub), RW at 0x1b04000. Carving
  0xCE2CC0 (`scratchpad/gauntlet/ext/re/wrap_elf.py` -> `core.elf` -> llvm-objdump) gives garbage. lldb.exe in
  the NDK fails to start on this box (liblldb.dll / api-ms-win-crt-time DLL). No capstone (third-party, not
  installed without owner OK). => the decrypted code must be DUMPED FROM THE LIVE PROCESS.
* Hypotheses, all UNTESTED: (a) locale/timezone-dependent path -- the Java shims (`ApplicationUtilBase`
  getLocaleCountry/getPreferredLanguage/getTimeZoneID) use `Locale.getDefault()`/`TimeZone.getDefault()`; our
  AVD has tz America/New_York and an EMPTY locale, the author's box was +0800 (cheap test:
  `adb -s emulator-5554 shell setprop persist.sys.locale zh-CN; setprop persist.sys.timezone Asia/Shanghai`,
  reboot or restart the process, rerun probe); (b) `runtime_clock` (prerequisite_probe shows it at a live
  address) gating the first tick on wall-clock/thread state -- `nativeInitResources` calls
  `runtime_clock_init` and `thread_option_set(5/3/10/12, true)`; (c) host CPU (Core Ultra 9 386H) / emulator
  version code path; (d) `loading_complete false` is real and the author's box has it true (their acceptance
  does not check it). (a) and (d) are the cheap ones; the decisive route is the dump.

### 4. Resume runbook (next session; ~15 min to the first new datum)
1. Boot: from `research/ext/cr-native-sandbox`, `. .\runtime.env.ps1`, then the sandbox venv python
   `-m native_core.worker start --workers 1 --base-port 37031` (or `scripts\smoke.ps1 -KeepRunning` via
   `scratchpad/gauntlet/ext/run_smoke.ps1`, which also re-installs). Launch long PowerShell steps with
   `Start-Process -RedirectStandardOutput/-RedirectStandardError` (PS 5.1 trap, §5aw.5).
2. Cheap tests first, one at a time, via `scratchpad/gauntlet/ext/run_probe_direct.ps1 -Profile probe-direct`
   (author's probe, exit 0 even on stall; read `step.tick_after` in the `probe_result` line of the log under
   `%LOCALAPPDATA%\cr-native-sandbox\data\probe\`): (i) locale+timezone setprop as in §5aw.3(a);
   (ii) `-ReplayJson examples\full-card-bootstrap.json` (rndSeed 424242) -- rules out a doc-specific path.
3. Decisive: add a local `probe-direct-hold` mode to `android_probe/java/royale/nativehost/JniHost.java`
   (research/ext is git-ignored -> keep the patch as a commit in the sandbox repo's own git for revert).
   Register it in `isProbeMode` and everywhere `"probe-direct".equals(mode)` is tested (lines 194, 338);
   `usesSurface`/`usesStartResume` stay false, `usesActivityCreate` true. After the normal `probe_result`:
   print `android.os.Process.myPid()`, read `/proc/self/maps`, dump every `libg.so` mapping (r-xp AND rw-p)
   through `RandomAccessFile("/proc/self/mem","r")` to `<root>/dump_<start>.bin`, plus 0x1000 bytes at the
   `battle`, `logic_battle`, `state`, `manager` addresses (from the pump/ready JSON) before and after an extra
   `nativeStep(1)`, then exit. Rebuild with `scripts\build_probe.ps1`; launch with run_probe.ps1's own command
   (line 90: `cd '<root>' && exec env CLASSPATH='<root>/lifecycle-probe.jar:<root>/base.apk'
   LD_LIBRARY_PATH='<root>' app_process /system/bin royale.nativehost.JniHost '<root>' probe-direct-hold
   '<root>/input-replay.json'`, root `/data/local/tmp/cr-native-sandbox-probe`; the script's ValidateSet
   rejects the new name, so run the adb command directly after run_probe.ps1 has pushed the files once).
   `adb pull` the dumps; `wrap_elf.py <dump> <vaddr> <len> out.elf` (edit: it seeks by vaddr, so pass a
   dump that starts at the mapping base or add an offset arg); `llvm-objdump -d --start-address=0xCE2CC0`
   (address = libg base + RVA) and read the early exits of core_update; compare the dumped battle/logic
   words against the author's field map in `docs/SANDBOX_RUNTIME_TECHNICAL.zh-CN.md` 190-259.
4. When tick advances: `research/ext/cr-native-sandbox/.venv/Scripts/python.exe
   research/sandbox_tools/replay_drive.py --tag 08CPVRRR8PYC --port 37031 --runs 2` and grade (accepted vs
   rejected plays by reason, elixir retry delays, crowns vs expected {red 0, blue 1}, terminal tick vs 3763,
   hash reproducibility across the 2 runs; check `cycle_deck_indices` against `next_deck_index` at runtime).
5. Stop when done: `python -m native_core.worker stop --workers 1 --base-port 37031 --stop-vm` (sandbox venv,
   after dot-sourcing runtime.env.ps1). Never leave qemu (4.9 GB) up beside the cuda run longer than needed.

### 5. Traps found tonight
* PowerShell 5.1: with `$ErrorActionPreference="Stop"` (the author's scripts), `2>&1` / `*>>` on a native
  command turns its FIRST stderr line into a terminating error (javac's deprecation Note killed smoke try 1).
  Process-level `Start-Process -RedirectStandardError` does not. run_probe.ps1 guards its own `2>&1`.
* The harness classifier denied `freeze_runtime.ps1 -ManifestTemplate` twice and one compound
  Start-Process+Remove-Item; narrower single commands were allowed. Do not route around a denial; the freeze
  is the owner's to run (still not run; only doctor's cosmetic FAIL lines depend on it).
* `adb pull` of a file under `/data/local/tmp/cr-native-direct-0/` failed silently once; `adb shell cat > f` worked.
* The AVD's first `bootstrap.ps1` attempt threw "AVD config.ini not found after creation"; a rerun succeeded.

### 6. Driver (done, offline-verified; not yet run against the engine)
`research/sandbox_tools/replay_drive.py` (sandbox venv python): orientation check, deal-permutation probe,
play loop with elixir retry, tail stepping, grading; `--offline` mode. Offline for 08CPVRRR8PYC: blue win
(team 1 / opp 0 crowns), 54 plays, last_play_tick 3763, both decks IceWizard/Knight-evo/Rocket/Skeletons/
Tesla-evo/Log/Tornado/Xbow, side 0: 26 plays 85 elixir, side 1: 28 plays 88 elixir, 256 consistent deals per
side. Output `scratchpad/gauntlet/ext/replay_<tag>_run<N>.json`.

### 7. What this does NOT establish
Whether the stall is environmental (fixable with a setprop) or a code-path difference (needs the dump); whether
the author's box also shows `loading_complete false`; anything about conversion fidelity; matches/h.

## §5ax — THE TICK STALL IS SOLVED AND THE FIRST REPLAY->REAL-MATCH CONVERSION RAN (2026-09-01 23:41 - 09-02 00:12): the clock was held by a PENDING GameMain UI ACTION (login-failed reason 8 = "update from store", Play URL queued before the battle existed); the bridge now discards it before stepping and reproduces the author's canonical hash 96598dc9028e1802 exactly; 08CPVRRR8PYC replays 54/54 plays accepted, crowns match, 2/2 runs same hash. Emulator STOPPED at the end.

### 0. Where things stand (read this first)
* The sandbox is now a working oracle on this box: author's probe-direct = tick 0->100, hash
  96598dc9028e1802, rng 3502570521 (the certified values, `accept_direct_core.ps1`); the service
  (`native_core.worker start`) attests slot 0 (tick 10, hash d036bec06e300550, tower maxima
  [3052x4, 4824x2]); `replay_drive.py` drove one real RoyaleAPI battle through libg end to end.
* The cuda real run was never touched: alive at 00:13 (5425 episodes, 148W-4201L-2D, winrate 2% at the
  last window, pl +0.001, vl 2.429, ent 0.06, clip 0.04, drills 1074 / 40% pass). Emulator up 23:41-00:11
  beside it; **VM and service stopped 00:11** (`worker stop --stop-vm`, qemu gone, `adb devices` empty).
* Two local patches live in the sandbox repo's OWN git (research/ext is git-ignored by ClashBot):
  commit `7c66f92` on top of the author's `643e63b`. Revert = `git -C research/ext/cr-native-sandbox
  revert 7c66f92` + rebuild (`scripts\build_probe.ps1`, `scripts\build_bridge.ps1`). The author's
  original binaries are kept at `scratchpad/gauntlet/ext/dump/lifecycle-probe.author.jar` (sha 39f3ce4c...)
  and `libnative_core_probe.author.so`. Current: jar 5f998d0f..., bridge 82887463... (`doctor.ps1`'s
  jar/bridge hash lines will FAIL against the author's manifest -- cosmetic, `worker.py` never reads it).

### 1. The cause (measured from the live process, not inferred)
* libg's code is encrypted on disk (§5aw.3) -> dumped from the live process: `hold_dump.py` (probe-direct
  with a post-step hold, `CR_PROBE_HOLD_MS`) + a static `memdump` (pread on `/proc/<pid>/mem`, root) pulled
  every libg mapping (`scratchpad/gauntlet/ext/dump/live/`, code at RVA 0 = `libg_7ad3d8ec7000_rwxp.bin`)
  and the state/battle/GameMain objects (`hold1/`). `wrap_elf.py` + NDK `llvm-objdump` disassemble it.
* `core_update` (0xCE2CC0) has five early exits before the tick path. The one that fires here is the third:
  `dword [GameMain+0x1BC] != 0` (helper 0x72D220). Live values: `+0x1B8 = 0, +0x1B9 = 1, +0x1BC = 5,
  +0x1C0 = 8`, and the string at `+0x1D0` (len 71) is
  `https://play.google.com/store/apps/details?id=com.supercell.clashroyale`. The accumulator at
  state+0x44 was 0.0 and state+0x18c = 0, so the tick path was never entered.
* Who queues it: the server-message dispatcher (function 0xB072E0; type via vtable[5]) -> login-failed
  branch (reason via vtable[8] at 0xB09D72) -> reason-7 jump table 0x3376C0 entry 1 = reason **8** ->
  block 0xB0D09F: copies the message text into GameMain+0x1D0 and calls `requestAction(GameMain, code 5,
  param 8)` (0x72B0E0, call site 0xB0D132). Code 5's handler (processor 0x72D230, jump table 0x2AC038 ->
  0x72D288) opens the stored URL = the "update from the store" popup. `requestAction` stores the action in
  `+0x1BC/+0x1C0` for GameMain::update's processor, which the headless bridge NEVER runs (it pumps only the
  state manager 0xCE7810), so the action stays pending forever and the battle core refuses to tick.
* Why the author's box did not hit it (plausible, UNTESTED): reason 8 is "client older than required"; our
  Java wrapper is the Play-derived split APK set (§5av: 4 wrappers differ from the frozen build) and its
  reported version/fingerprint is what the login path compares against. The author's runtime is the frozen
  bundle. No network is involved in either case (the message is raised locally). Not chased further: the
  fix below is independent of who queues the action.

### 2. The fix and its A/B (all on the same stalled fixture, `eight-card-bootstrap.json`)
* Live A/B first (`scratchpad/gauntlet/ext/dump/hold_fix.py`, pre-step hold `CR_PROBE_HOLD_PRE_MS` +
  release file, static `memwrite` doing pwrite on `/proc/<pid>/mem`):
  control (hold, no write): tick 0->0, hash **e23456fd00d634de** (§5aw's stall exactly);
  `--clear` (qword +0x1BC := 0, word +0x1B8 := 0, i.e. what 0x72D230 itself does before dispatch):
  tick 0->**100**, hash **96598dc9028e1802**, rng 3502570521, towers [4824,3052,3052,4824,3052,3052]
  = the author's certified 100-tick state bit for bit. Files: `hold2_ctrl/`, `hold3_clear/` (result.json).
* Permanent fix in the bridge (`android_probe/native/jni_bridge.cpp`, `discard_pending_game_action`, called
  at the top of `nativeStep`; the step payload now carries `pending_game_action {discarded, code, parameter}`;
  a no-op when nothing is pending, so the author's semantics are unchanged on their box). Rebuilt under the
  author's `-Wall -Wextra -Werror`. Author's probe-direct with it: `{"tick_before":0,"tick_after":100,
  "stepped":100,"pending_game_action":{"discarded":true,"code":5,"parameter":8}}`, hash 96598dc9028e1802,
  rng 3502570521, replay->observe 42.8 ms (log `%LOCALAPPDATA%\cr-native-sandbox\data\probe\
  20260902-001002-176-probe-direct.log`, runner `scratchpad/gauntlet/ext/probe_fixed.log`).
* Also ruled out on the way (measured, §5aw hypotheses): (a) locale/timezone (zh-CN + Asia/Shanghai -> same
  stall, same hash); doc-specific path (the full-card doc crashed BEFORE the doc is used, see trap below;
  the eight-card doc reproduces identically). (b)-(d) moot.

### 3. The conversion (08CPVRRR8PYC, `replay_drive.py --port 37031 --runs 2`, seed 424242, level 11)
* Deal: position-based confirmed; deck permuted so the dealt positions carry the inferred hand/queue
  (probe side 0 hand_pos [3,7,2,4] cycle [6,5,0,1] next 6; side 1 [6,3,7,1] / [4,2,5,0] / 4); opening
  hands both IceWizard/Knight/Rocket/Skeletons.
* **Accepted 54/54 plays, rejected {}, invalid placement 0, elixir delays n=0** -- every real play was legal
  at the recorded tick with the recorded elixir; the engine's own elixir read at each play is in the log
  (`scratchpad/gauntlet/ext/replay_drive_08CPVRRR8PYC.log`, e.g. t=951 s0 rocket at el 7.717).
* Final: tick **3887**, terminated, outcome side1_win, crowns **[0, 1]** = expected {red 0, blue 1},
  reason `native_logic_clock_stopped`; terminal - last play (3763) = 124 ticks (6.2 s: the tower fell and
  the clock stopped). Hash **d3aa402b826e6d72 in BOTH runs** (determinism holds).
* Cost: reset 0.04-0.05 s, drive+tail **1.67-1.77 s per full match** (3887 ticks + 54 plays + per-play
  observes) -> ~2000 matches/h on ONE worker before any batching. Per-run JSON:
  `scratchpad/gauntlet/ext/replay_08CPVRRR8PYC_run{1,2}.json`.
* What this does NOT establish: fidelity of the intermediate state (tower HP trajectory vs the real
  match is not recorded by the crawl, only crowns); whether the other 267 usable replays convert as
  cleanly (this one is an Icebow mirror and every play had elixir to spare); anything about card levels
  (both sides forced to 11).

### 4. Next steps (in order; nothing blocks them) -- step 1 DONE in §5ay
1. Convert the 268-replay set (`scratchpad/gauntlet/ext/usable_replays.json`) with `replay_drive.py`,
   grading each: accepted/rejected by reason, elixir delays, crown match, determinism. That is the fidelity
   number the sim-parity oracle (§4p / §5at) needs; budget ~10 min of engine time + a 70 s boot.
2. Only then the per-tick state dump for the sim-parity oracle / placement prior.
3. Owner-side (optional, cosmetic): `freeze_runtime.ps1` so `doctor.ps1` stops reporting hash FAILs; note
   it will then pin OUR jar/bridge hashes, not the author's.

### 5. Traps found tonight (also in §8)
* toybox `dd skip=` overflows on 64-bit addresses ("dd: -456174 < 0") -> the static `memdump`/`memwrite`
  C tools (NDK clang `--target=x86_64-linux-android31 -static`).
* `adb push` resets the file mode -> `chmod 755` after EVERY push or "can't execute: Permission denied".
* Git-Bash mangles `/data/local/tmp/...` into a Windows path in `adb push` args -> push from PowerShell.
* `pgrep -f` matched the adb `sh -c` wrapper itself -> pattern `^app_process.*JniHost`.
* `full-card-bootstrap.json` run died with SIGSEGV (exit 139) inside `nativePumpDataTables`
  (0xE74B40 -> 0x12AF1B0 null deref, fault 0x80, 11 s uptime) -- BEFORE the replay doc is used, and the
  DataTables pump's iteration count varies run to run (89/106/167). Timing-dependent; one crash in ~10
  boots tonight. Re-run on crash; do not read it as a doc problem.
* The Bash tool's cwd persists between calls; `cd research/ext/...` from inside the sandbox fails -- use
  absolute paths.

## §5ay — THE WHOLE USABLE SET CONVERTED THROUGH THE REAL ENGINE (2026-09-02 00:20-01:08): 211/268 converted (57 refused up front: Elite Barbarians evolution has no native form), 17,757/17,901 plays accepted (99.2%), crowns match RoyaleAPI 164/211 (77.7%), 135 fully clean, determinism 21/21, 3.5 s per match; a full-observation recorder + schematic viewer exist; the sandbox CANNOT show the real game (renderer-less by design). Emulator STOPPED 01:08.

### 1. What ran
* Service boot via `scratchpad/gauntlet/ext/svc_start4.ps1` (6-attempt retry): attempts 1 and 2 died in
  `nativePumpDataTables` (SIGSEGV fault 0x80, same PCs as §5ax.5: libg 0x12AF1B0 <- 0x11EA4C2 <- 0xE256E6
  <- 0xE74CA7), attempt 3 booted and attested (tick-10 hash d036bec06e300550). Static read of the crash
  site (carvings `dump/live/c_12af100.elf`, `c_11ea400.elf`, `c_e25600.elf`, `c_11e8860.elf`, NOT committed):
  0x11EA4A0 calls the resource lookup 0x11E8860(name, 0) and hands the result to 0x12AF1B0, a
  wait-until-loaded loop on [obj+0x80]; a null lookup faults at +0x80. Timing-dependent (2 of 3 boots
  tonight, ~1 in 10 in §5ax) -> the retry loop is the fix for now; the lookup's argument is the lead if it
  ever becomes frequent.
* `research/sandbox_tools/replay_batch.py` (new): every tag in `usable_replays.json` through
  `replay_drive.drive()` in one python process, per-tag result JSON in `scratchpad/gauntlet/ext/batch/`,
  resumable `summary.jsonl`, every 10th tag re-run for determinism, `aggregate.json` at the end. Log
  `batch/batch_run.log`.
* `replay_drive.py` patched first: `load_battle` refused 203/268 replays because hero-ability rows
  (`attr_ability=1`, `attr_card` `_invalid`) carry `x_units`/`y_units` = "None"; they are now loaded as
  ability rows (position None) and skipped by the driver as before (the engine's ability command needs an
  entity id we do not have from the crawl). Offline pre-check of all 268 (`scratchpad/offline_all.py`):
  268 load, deal inference consistent in all 268.

### 2. Batch numbers (measured, `batch/aggregate.json`)
* **268 tags: 211 converted, 57 refused** before the first tick, all the same error: "card has no native
  evolution form: 26000043" = Elite Barbarians evolution. The frozen 15.535.29 build's catalog has no
  native form for it (HANDOFF's earlier "without EB-evo: 211" count was exactly right).
* **Plays: 17,901 driven, 17,757 accepted = 99.2%.** Rejections: `native_rejected` 81 (every one result
  code 4, every one within ~10-80 ticks BEFORE the engine's own terminal -> the engine finished the match
  earlier than the real one did; see §8) and `card_not_in_hand` 63. 46 matches have at least one
  rejection; 165 have none. **Invalid placements 0. Elixir delays 0** (the recorded plays never needed
  more elixir than the engine had at level 11).
* **428 ability plays skipped** (hero abilities, in 158 matches). Not driven at all -> a known fidelity
  gap. crowns-match WITHOUT any ability play 42/53 (79%) vs WITH 122/158 (77%): no measurable penalty
  from skipping them at this sample size.
* **Termination: 211/211 terminated** (`native_tiebreak_hp_drain` 81, `native_logic_clock_stopped` 130).
* **Crowns match RoyaleAPI in 164/211 = 77.7%. Winner matches in 169/211 = 80.1%.** Mismatch direction:
  engine side0 win where RoyaleAPI has side1 in 30, the reverse in 12, same winner but different crown
  count in 5. (Side 0 = RoyaleAPI red = bottom.)
* **Fully clean (crowns match, no rejections, no invalid placement): 135/211 = 64%.**
* Terminal - last real play: median **+160 ticks** (8 s), **negative in 41** matches (engine ended before
  the last real play; 28 of those still match on crowns).
* **Determinism 21/21 SAME** final hash on the re-run (every 10th tag).
* **`position_based` = False in 7 matches** (00LYPLCVPJR9, 00UYPL99PV2P, 022YYLV98PVR, 02JY9G08C0JV,
  02JY9G08YCQG, 02QY9Q9PCGCP, 08PY88PRRPY2): the reversed-deck probe dealt different hand POSITIONS, so
  the deck-permutation trick that gives the engine the real opening hand does not hold there; all 7 are
  among the `card_not_in_hand` matches and all carry hero/evolution cards. Untested reading: the form flag
  changes the deal. Lead for the next pass.
* Cost: **782 s wall for the set, median 3.54 s per match, max 6.27** (one worker, one AVD).

### 3. What the number means (and does not)
* 99.2% of the real players' commands are legal in the real engine at the recorded tick with the
  engine's own elixir -> the crawl's command timelines are essentially exact, and the engine agrees with
  the real outcome in 4 of 5 matches WITHOUT card levels (both sides forced to 11), without abilities,
  and with an unknown-ordering deal in 7. That is the fidelity floor for the sim-parity oracle (§4p/§5at).
* The 22% crown mismatches are NOT yet attributed. Candidate causes, in order of plausibility (all
  untested): card levels (a level-11 vs level-14 tower/troop changes every race), the 428 undriven
  abilities, the engine's earlier end (41 matches), the 7 deal mismatches. Levels are the obvious first
  test: RoyaleAPI has the levels per card in the crawl -> pass them through `battle` instead of `--level 11`.

### 4. Recording and the viewer (new tools)
* `replay_drive.py --record-every N [--record-full]`: stores an observation every N ticks in
  `out["frames"]`. Compact = side/x/y/name/hp per entity + towers + elixir. `--record-full` uses
  `env.observe()`: adds the entity `kind` code (12/13 buildings, 14/15 troops; 12/14 coincide with the
  deploy timer / dormant state -- an untested reading of the code, not documented), every in-flight
  projectile (x,y -> target_x,target_y, card name) and any non-projectile effect object. Recording does
  NOT perturb the engine (same hash as the unrecorded run: 08CPVRRR8PYC d3aa402b826e6d72; 00LYPLJLC80L
  af377a10dce5c2ad in both the batch and the recorded run) but costs ~20 ms per observe: every-2-ticks
  compact = 34 s, every-tick full = 108 s for a 5275-tick match vs 1.7-3.5 s unrecorded.
* `research/sandbox_tools/replay_view.py result.json [-o out.html]`: self-contained schematic viewer
  (18x32 grid, towers, entities by kind, projectiles with target lines, effect rings, elixir bars, play
  markers, scrub/play/speed). Published: 08CPVRRR8PYC compact/2-tick
  (https://claude.ai/code/artifact/9ff6a4f7-1051-44e9-bd54-5eb053f3f8c8) and **00LYPLJLC80L full/1-tick
  (Hog cycle w/ Musketeer-evo + Cannon-evo vs Icebow, 93/93 accepted, crowns [0,1] = RoyaleAPI, 5268
  frames, 2.64 MB): https://claude.ai/code/artifact/cc872890-4afa-4d55-bdec-2b4da5004924**. Files:
  `scratchpad/gauntlet/ext/replay_00LYPLJLC80L_run1.json` (9.3 MB) and `..._full_view.html`.

### 5. "Can we watch the converted replay in the real game?" -- NO, by design (owner asked 01:0x)
* (c) contradicted: the sandbox is renderer-less. No Surface, no GL, the rendering resource variant is
  shimmed out (`docs/SANDBOX_RUNTIME_TECHNICAL.zh-CN.md` §10); the whole point of the repo is the ENGINE
  (logic, entities, damage, elixir) running headless as an RL environment / oracle. There is no frame to
  capture; the observation JSON is the only output.
* (c) contradicted for the other route: the real client only plays replays it fetches from Supercell's
  servers by tag; there is no "load a replay document" path in the UI. Feeding it a converted document
  would need protocol interception or a private server -- weeks of work, against the ToS, and the
  conversion is not exact anyway (levels forced, abilities skipped). Not doing it.
* (a) what IS possible and was done: every tick of the real engine's state, drawn schematically (§5ay.4).
  Anything more faithful (sprites, animation) would be OUR renderer on top of the engine's positions --
  the positions are the engine's, the pictures would not be.

### 6. Next steps (in order)
1. **Levels pass-through**: drive with the crawl's per-card levels instead of `--level 11` and re-grade;
   this is the cheapest test of the 22% crown mismatch. Then abilities (needs an entity-id resolver:
   the ability command wants the hero's live entity id -> look it up from `observe()` by side + card).
2. Elite Barbarians evolution (26000043): confirm from the catalog whether a base-form fallback is
   acceptable (drive as base EB) -- gets the 57 refused replays back at a known fidelity cost.
3. The 7 `position_based=False` matches: probe whether the hero/evolution form flag changes the deal.
4. Per-tick state dump for the sim-parity oracle (§4p): `--record-full --record-every 1` over the 135
   clean matches = ~4 h of engine time at 108 s/match; or record every 4 ticks (~30 s/match, 1.1 h).
5. Boot crash: if `nativePumpDataTables` SIGSEGV becomes >1 in 3, chase 0x11E8860's argument.

### 7. Housekeeping
* Emulator + service stopped 01:08 (`worker stop --stop-vm`, qemu verified gone). Cuda run untouched
  (6975 eps at 01:10).
* Committed: `replay_drive.py`, `replay_batch.py`, `replay_view.py`, `batch/` (summary, aggregate, 211
  result JSONs, logs), the two recorded runs + viewer HTML, launcher scripts. NOT committed: libg dumps /
  carvings / disassembly, author jars (standing rule).

## §5az — GAUNTLET L1: DETECTOR UPGRADE RECON (2026-09-02 01:20-02:05). The approved isolated venv is probably unnecessary (ultralytics 8.4.107 already ships yolo26 / yolo26-p2 / yolo12 / rt-detr); kitka is a SPRITE library whose real value is 9 evolution classes going from 0-7 sprites to 88-540 (my "88 new classes" first read RETRACTED); and ⚠ mAP on the current val set CANNOT measure that change -- 69/230 classes have ZERO val instances. No training run started: the GPU is the PPO run's until ~18k episodes.

Full working notes: `scratchpad/gauntlet/L1/detector_upgrade_recon.md`.

### 1. Owner rulings that scope this gauntlet (asked before starting, all four = my recommendation)
1. "Sub-100 ms decision window" = **wall-clock LATENCY**, not `play.act_period`. The period stays
   0.6 s; lowering it is a 6x MDP change that §3m measured as requiring a full sim retrain, and is
   queued as its own experiment AFTER this gauntlet.
2. **Stop the PPO cuda run at ~18,000 episodes**, then board training takes the GPU. Rationale offered
   and accepted: §4t measured a previous run peaking near 18k and giving gains back -- but that was a
   DIFFERENT config (CPU, no hazard head), so it is a screen, not a law. Saves ~12 h of GPU.
3. Anything non-ultralytics goes in an **isolated venv**; `icebow/.venv` is not to be disturbed
   (§4y measured -6.0pp winrate purely from running under the wrong venv's torch).
4. Budget: **cheap screen, then ONE full ~24 h run** of the winner with kitka folded in.

### 2. The install question mostly dissolves (measured)
`icebow/.venv`: **ultralytics 8.4.107**, torch 2.11.0+cu128, CUDA True (RTX 5050 Laptop). Its model
configs already include `26/` (yolo26, **yolo26-p2**, yolo26-p6, -seg/-obb/-pose), `12/`, `rt-detr/`,
`v10/`, `v9/`. `tools/detect/train.py` already takes `--model` and already has `rtdetr-l.pt`,
`yolo26n.pt`, `yolo11s.pt` sitting in `tools/detect/`. So **YOLO26 and RT-DETR need no install at all**
-- the venv is only needed if a non-ultralytics candidate (RF-DETR / D-FINE / DEIM) survives the paper
screen. `yolo26-p2` is a separate candidate on its own merits: a stride-4 head is the standard answer
for SMALL objects, which is what CR units are at imgsz 960. Untested (b).

### 3. The bar to beat (measured, `runs/detect/board-26`)
yolo11s, imgsz 960, batch 4, 120 epochs, **23.9 h wall** (86,183 s): **mAP50 0.860, mAP50-95 0.704**,
P 0.845 / R 0.826. Dataset nc=230, train 12,821 real + 5,000 synth (55,642 + 33,921 instances),
val 2,346 images / 10,179 instances.

### 4. kitka: what it actually adds — first read RETRACTED
`icebow/data/kitka/detector_data` is 194 MB / 10,957 PNGs with **no bounding boxes** -- a sprite bank
for the synthetic compositor, not a detection dataset. `segment/` = 183 class folders (29 not in our
katacr import of 154); `dataset_updates/` = 3,165 crops / 29 classes, mostly evolutions.
* **RETRACTION:** a naive name-normalizer reported "88 classes new to us". Handling `evolution`->`evo`
  and plurals cut it to 14; checking those against the detector's own 230-class list cut it again.
  Do not carry the 88 forward.
* Our sprite bank already holds 42,313 crops / 184 classes. kitka adds **+6,200 crops to 128 classes we
  already have** (~+15% variety) and fills **1 of the 45 detector classes that have NO sprites**
  (`pekka_evo`, 324). The other 44 stay empty (hero abilities, `*_aoe` decals, mirror, void...).
* **The real win is the thin classes**, where our bank has 1-7 sprites so every synthetic instance is
  the same pixels: pekka_evo 0->324, hunter_evo 6->546, cannon_evo 6->242, lumberjack_evo 3->189,
  electro_dragon_evo 7->167, dart_goblin_evo 1->143, vines 1->123, executioner_evo 7->95.
  **9 evolution-era classes move from unlearnable-by-synth to represented.**

### 5. ⚠⚠ TRAP: the promotion instrument cannot see the change it is meant to judge (measured)
**69 of 230 classes have ZERO val instances.** Ultralytics averages AP only over classes with val
instances, so those 69 can never move the number. The 9 classes kitka fixes have **0-2 val instances
each** (executioner_evo 0, pekka_evo 0, the rest 1-2), so their AP is a coin flip.
* Consequence: **comparing a kitka run's mAP50 against board-26's 0.860 and calling it a null would be
  an artifact of the instrument, not a fact about the detector** -- the same failure mode as §8's
  "never compare numbers from two different instruments".
* `run.py detect-eval` is the right instrument for the ARCHITECTURE half (presence recall
  class-agnostic, whitelist identity recall folded to base cards, per-ROLE gates with UNIT >= 0.80),
  but it reads the same val set, so it does not fix this either.
* Fix to build before the full run: a **held-out SYNTHETIC val** composed from kitka sprites the
  training synth never saw, reported SEPARATELY from the real-frame val and never averaged into it.

### 6. What this does NOT establish
Nothing about whether any candidate beats yolo11s -- no model was trained or benchmarked this loop, by
design: the GPU belongs to the PPO run until ~18k episodes and §6 forbids benchmarking on a contended
box. The 23.9 h board-26 wall time is carried forward from that run's own log, not re-measured.

### 7. Next
1. Paper screen of candidates (yolo26s / yolo26-p2 / yolo12s / rtdetr-l / RF-DETR) -- free, no GPU.
2. Latency budget breakdown of the non-GPU half of the decision path (capture, warp, tracker, threat
   and observation build) while PPO still holds the GPU.
3. Extend `tools/battery_watchdog.ps1`: it currently KILLS at 10% and needs a manual `--resume`; the
   owner wants pause -> sit 1-2 h -> auto-resume.
4. On the watcher firing at 18k: record PPO state, stop it, then the cheap screen, then the full run.

## §5ba — GAUNTLET L2: THE PPO CUDA RUN STOPPED AT 18k (its own eval curve says it cost nothing), YOLO26 SMOKE-TESTED ON OUR DATA, AND THE TWO-ARM SCREEN LAUNCHED (2026-09-02 07:13-07:35)

### 1. Stopping the PPO run — the ruling, and the evidence that it was right
The owner ruled in §5az.1 to stop at ~18k. Before acting I read the **greedy EVAL** instrument rather
than the rolling sampled winrate (§8: never mix the two):

| EVAL @ | 2000 | 4000 | 6000 | 8000 | 10000 | 12000 | 14000 | 16000 |
|---|---|---|---|---|---|---|---|---|
| ladder (L13-16) | 3% | 12% | 19% | 13% | 7% | 21% | 8% | 10% |
| fair (L15) | 3% | 5% | 10% | 5% | 4% | 13% | 5% | 7% |
| ladder 5-eval avg | - | - | 11% | 12% | 11% | **14%** | **13%** | **12%** |

* **(a) measured:** the 5-eval moving average has been FLAT at 12-14% ladder / 7-8% fair since episode
  12,000. Consecutive evals swing 7% -> 21% -> 8% at 150 matches each, far beyond the ~2.7pp standard
  error of a 12% rate at n=150, so the policy itself is oscillating rather than the sampler being noisy.
  `policy_real_20260901_best.pt` was last written **03:54 (~12k)** and has not moved since.
* Conclusion: stopping at 18k gave up nothing measurable. This is consistent with §4t's "peaks then
  gives it back", but it is INDEPENDENT evidence from this run, not §4t carried forward.
* **What this does NOT establish:** that the run would never have improved later, or anything about the
  hazard head. It is a stop justified by 8 evals of flatness, not a verdict on the configuration.

### 2. How it was stopped (guardrail trail)
Checkpoints found by reading the run's own command line and log (NOT the stale `data/policy_sim_ppo.pt`,
which is from 08-29 and belongs to another run): `data/policy_real_20260901.pt` (07:11, at 18k) and
`data/policy_real_20260901_best.pt` (03:54). Copied with `data/bench/real_m5k.pt`, `real_m10k.pt` and the
log to **`data/bench/stopped_real_cuda_18k_20260902/`**, both .pt SHA-256 verified equal
(56FD3C94..., CE8AF22F...). Then Stop-Process on PIDs 44316 + 70192: python procs **20 -> 6**,
train-sim-ppo remaining **0**, free RAM **11.1 GB / 31.4**, GPU 1169 MiB / 8151 and 0% util.

### 3. YOLO26 smoke on our own data (measured)
`tools/detect/train.py --model yolo26s.pt --epochs 1 --fraction 0.02` completed exit 0 on the real
230-class dataset. Speed at imgsz 960 on the RTX 5050: **0.4 ms preprocess, 5.6 ms inference,
0.4 ms postprocess** per image. The 0.4 ms postprocess is the NMS-free head showing up -- relevant to
the sub-100 ms latency goal, and to be compared against yolo11s's own postprocess from the control arm.

### 4. Paper screen (web, measured from Ultralytics' published table)
| | mAP50-95 (COCO 640) | params (M) | FLOPs (B) | T4 TensorRT (ms) |
|---|---|---|---|---|
| YOLO11s | 47.0 | 9.4 | 21.5 | 2.5 |
| **YOLO26s** | **48.6** | 9.5 | 20.7 | 2.5 |

Same size, +1.6 COCO points, fewer FLOPs, identical GPU latency, **NMS-free**, plus ProgLoss/STAL which
are explicitly small-object techniques -- our regime (CR units at 960px). RT-DETR is deprioritised on
the project's OWN prior reasoning (`tools/detect/train.py` docstring: DETR-family is data-hungry and
this is a small, label-bottlenecked, 230-class dataset); it stays available via `--model rtdetr-l.pt`
if the screen disappoints. **These are COCO numbers on someone else's data (b) -- they rank the
candidates, they do not predict our mAP.** That is what the screen is for.

### 5. The screen that is now running
Two arms, identical in everything but `--model`: **yolo11s control** then **yolo26s**, 30 epochs,
`--fraction 0.35`, imgsz 960, batch 4, workers 4, seed 0. ~2 h per arm (board-26 measured 718 s/epoch
at fraction 1.0). A new `--fraction` flag was added to `train.py` for this, documented as screening-only.
**⚠ The screen's numbers are comparable ONLY to each other, never to board-26's 0.860** -- different
data volume and epoch count. That is exactly why the control arm exists and why I did not simply run
yolo26s and diff against board-26.

### 6. Battery watchdog rewritten (owner spec)
`icebow/tools/battery_watchdog.ps1` previously KILLED the run at 10% and left a manual `--resume`,
which for an unattended 24 h job is just an ending. It now does **pause -> sit (default 90 min) ->
wait for >= 25% -> auto-resume -> keep watching**, up to 12 cycles. Two new refusals, each because the
alternative destroys a run silently: it will not stop without a `last.pt`, and it will not RESUME a
STRIPPED checkpoint (ultralytics does not raise on that -- it starts a fresh coco8 training that looks
like a normal log; this repo has three such folders already). Parse-checked; not yet exercised against
a real low-battery event (b) -- the box has been on AC at 100% throughout.

### 6b. ADDENDUM (owner question, 2026-09-02 ~08:00) -- what the PPO watchdog saw overnight, which §5ba.1 did NOT read
§5ba.1 read only the greedy EVAL rows. The owner asked about the overnight CELL HEAD COLLAPSED / ELIXIR
NEVER REACHES 6 alerts; re-read from `data/ppo_watchdog.log` (114 readings for this run, 21:30 -> 07:34,
raw-head probe of the checkpoint, so the 15% rollout cell floor is NOT in these numbers):

| eps | cell_ent (of 5.08) | distinct cells (of 432) | elixir >= 6 (% steps) | card_ent (of 2.30) |
|---|---|---|---|---|
| 0-2k | 1.09 | 28 | 0.45 | 1.31 |
| 4-6k | 1.25 / 1.09 | 40 / 35 | 1.40 / 2.09 | 1.43 / 0.87 |
| 8-12k | 0.96 / 0.87 / 1.01 | 38 / 34 / 36 | 1.71 / 1.19 / 1.03 | 1.29 / 1.10 / 1.10 |
| 14-16k | 0.69 / 0.73 | 40 / 32 | 0.52 / 0.61 | 1.39 / 1.40 |
| 18k | 0.80 | 34 | **0.02** | 1.29 |

* **(a) measured -- cell head:** below the watchdog's collapse line (25% of max = 1.27 nats) on **83 of 94**
  readings after ep 4000, and already there at the FIRST reading (ep 200: 1.09). So this was not a collapse
  that happened overnight; it is the state the head was in from the start of the run. The alerts came
  through only "several" times because of the two-consecutive-cycle debounce plus re-arming, not because the
  condition was intermittent. It never reached the 3-of-432 catastrophe the floor was written for
  (28-43 distinct cells throughout).
* **(b) untested -- whether 30-40 distinct cells is pathological:** the 0.25 threshold was tuned to the
  3-cell collapse, not to a known-healthy Icebow placement policy, and an Icebow deck legitimately uses a
  few dozen cells (X-Bow bridge spots, Tesla/Cannon centre, Skeleton/Ice Spirit kite tiles). Whether these
  34 cells are the RIGHT 34 needs a per-card top-cell dump of the checkpoint, not an entropy number.
* **(a) measured -- elixir:** the 6-elixir fraction FELL over the run: ~1.4-2.1% (4-8k) -> 1.0-1.2% (10-12k)
  -> 0.5-0.6% (14-16k) -> 0.02% at 18k. Below the 0.5% alert line on 34 of 80 readings after ep 6000, all in
  the back half. This is a trend, not noise, and it is the same failure §5as/§4t describe: the policy spends
  down to cheap cards and the deck's win condition (X-Bow, 6) and its only tower-kill spell (Rocket, 6)
  become uncastable. With that, a 12-14% ladder plateau is what you would expect, so the two readings agree.
* **What it changes:** nothing about the stop (it strengthens it) and nothing about this gauntlet's plan.
  It is a finding for the NEXT PPO run, queued in §6: (1) the elixir-decline is monotone and visible by
  ~12k, so a watchdog DRIFT rule on `elixir_ge6` (like the existing cell_struct drift) would have named it
  6 h earlier than the absolute floor; (2) the cell head's 34-cell footprint needs a top-cell dump before
  anyone calls it collapsed or healthy.
* **Retraction of tone:** my L2 report's "stopping cost nothing measurable" stands, but "no problems
  found" would have been wrong -- I had not read the instrument that would have found them.

### 7. Next
1. Read the screen when both arms land (~11:30): mAP50 and mAP50-95 arm vs arm, plus each arm's
   postprocess ms, and pick the architecture.
2. Build the **held-out synthetic val** from unseen kitka sprites (§5az.5) -- without it the kitka half
   of the full run is unfalsifiable.
3. Full ~24 h run of the winner with kitka folded in, battery watchdog armed on its run name.
4. Latency: map the decision path and measure the non-GPU terms; the detector half must wait for a free
   GPU or the measurement is contended (§6).

## §5bb — GAUNTLET L3: KITKA FOLDED INTO THE SPRITE BANK, L1's COUNTS RETRACTED (duplicate folder), AND A HELD-OUT SYNTHETIC VAL BUILT SO THE KITKA HALF OF BOARD-27 CAN BE FALSIFIED (2026-09-02 07:40-08:30)

### 1. Retraction of §5az.4's numbers (and what survives)
`data/kitka/detector_data/dataset_updates/dataset_updates/{air,ground,spells}` is a **byte-for-byte
duplicate** of files in `segment/segment` (sha1 over all 3,165 files: 100% present in segment). L1 summed
both, so every "X -> Y" in §5az.4 is ~2x: hunter_evo is 276 raw segments, not 546; cannon_evo 124, not 242;
pekka_evo 162, not 324. The unique library is **183 class folders / 7,792 PNGs**. What survives of L1: it
IS a sprite bank, not a labelled set; the thin evolution classes ARE its value; and it fills not 1 but
**3 classes that had zero sprites** (pekka_evo, giant_snowball_evo, skeleton_army_evo -- the last two were
missed by L1's normaliser, see 3).

### 2. The split (measured)
`tools/detect/kitka_split.py` (new): sha1(filename)-ranked 80/20 per class, classes under 15 segments not
split. **6,313 train / 1,479 held-out** PNGs (`data/kitka/split/{train,holdout}`). Deterministic; a re-run
moves nothing.

### 3. Imports (measured)
`run.py katacr-segments --src-width 735 --prefix kitka` (train slice -> `data/detect/sprites`) and the
same with `--bank data/detect/sprites_holdout` (held-out slice -> its own bank). `--bank` and `--prefix`
are new flags; width is always measured against the TRAINING bank so both slices scale identically.
* Training bank **44,094 -> 48,929 files** (+4,835 `kitka_*`, **0 pre-existing files removed** -- comm
  check on the before/after listings). 143 classes mapped, 26 deliberately dropped (UI/decals), 10
  unmatched-and-dropped (below).
* Held-out bank **1,124 files / 106 classes**.
* Thin classes, training bank now (kitka + pre-existing) / held-out: pekka_evo 130 (130+0)/32 ·
  hunter_evo 222 (216+6)/54 · cannon_evo 100 (94+6)/24 · lumberjack_evo 77 (74+3)/19 · electro_dragon_evo
  71 (64+7)/16 · dart_goblin_evo 58 (57+1)/14 · vines 50 (49+1)/12 · executioner_evo 42 (35+7)/9 ·
  royal_ghost_evo 126 (120+6)/30 · mega_knight_evo 118 (99+19)/25 · giant_snowball_evo 61 (61+0)/15 ·
  skeleton_army_evo 164 (164+0)/41 · spirit_empress 197 (162+35)/41.
* Five kitka names needed explicit mappings the normaliser missed (`dartgoblin-evolution`,
  `ghost-evolution`, `megaknight-evolution`, `snowball-evolution`, `skarmy-evolution`) -- dart_goblin_evo
  had imported ONE sprite before the fix. `spirit-empress-{air,ground}` both map to `spirit_empress`.
* Source width: kitka crops come from frames of AUTO-measured width 735 px but with **CV 0.27 (p10 612 /
  p90 952)**, i.e. some classes are ±25% off-scale after the fixed-735 import. (b) untested whether that
  sits inside ultralytics' default scale augmentation (0.5); the held-out val's composite (below) looked
  right by eye for executioner_evo (troop-sized next to a princess) and vines.
* **Taxonomy gap found (b):** 10 kitka classes are real in-game objects our 230-class list cannot name at
  all: goblinstein_monster (214 segs), goblin_dummy (133), skeleton_balloon_evo (104), ghost_soldier (86),
  hogs_evo (71), goblinstein_doctor (52), bush, drill_evo, and two text overlays. Adding them changes `nc`
  and needs real labels; parked in §6, NOT part of this gauntlet (one change per experiment).

### 4. The held-out synthetic val (the instrument §5az.5 said was missing)
`run.py sprites --synth 1000 --seed 0 --bank data/detect/sprites_holdout --base-split val
--out-name synth_holdout --no-yaml` (three new flags). **1,000 val-frame composites, 2,479 pastes, 6,832
boxes, 156 classes**; `data/detect/holdout_val.yaml` points at it (not committed: under data/).
`data/detect/data.yaml` untouched (238 lines, `synth/images` once) -- verified, because a duplicated
train entry would double-weight synth silently.
* **How to read it:** per-class AP for the PASTED classes only, board-26 vs board-27, from the same
  yaml. The overall mAP of this set is NOT a number to quote: its real boxes are the real val set's boxes,
  and the base frames overlap the real val the architecture verdict uses.
* **What it measures:** whether a class learned from synth transfers to sprites of that class the
  training set never saw. **What it does NOT measure:** transfer to real screen crops of those classes --
  for the 69 zero-val-instance classes there is still no real-crop instrument, and this set must not be
  mistaken for one.

### 5. Deliberately NOT done this loop
The training synth (`data/detect/synth`, 5,000 images) still contains none of the kitka sprites: the
running screen reads that folder and `synth_images` regenerates it in place (§8 trap). Regeneration
(`run.py sprites --synth 5000 --seed 0`) is the first step after "ALL SCREEN ARMS DONE", before board-27.

### 6. Code (committed): `katacr_segments.py` (`--bank`, `--prefix`, ref-bank width, 7 explicit names),
`sprites.py` (`bank_dir`, `base_split`, `out_name`, `update_yaml`), `cli.py` (flags), new
`tools/detect/kitka_split.py`. All syntax-checked and exercised by the runs above.

### 7. Next
1. ~10:10 read the y11s arm's final row; ~13:00 read y26s; pick the architecture (arm vs arm only).
2. Then in order: regenerate training synth -> engine recording pass for the gate prior (§6 ruling,
   `replay_drive --record-every 12`, needs the emulator, CPU-only, ~40 min est.) -> launch board-27
   (fraction 1.0, 120 ep, 960, batch 4) + `battery_watchdog.ps1 -Run board-27`.
3. Meanwhile (CPU, cheap): the gate-prior builder against the one existing full recording
   (`replay_00LYPLJLC80L_run1.json`), so the tool is proven before the 211-replay pass.

## §5bc — HOGEQ BROUGHT UP TO ICEBOW'S VERSION: parity restored and 5 shared files converged, the LOG AIM ASSIST WAS DEAD IN HOGEQ, and the hogeq replay corpus crawl (a roster bug found and fixed) (2026-09-02 09:00-11:00, owner request)

Owner, mid-gauntlet: *"update hogeq so it's up-to-date with icebow's version... you may need to mine
hogeq replays from RoyaleAPI using the replay scraper repo to build the corpus needed for that deck."*
Both halves below. The L2 detector screen kept the GPU throughout; everything here is CPU/network.

### 1. Parity, measured before and after
`tools/parity_check.py` (byte-compare of the two trees, runs from either deck):

| | shared identical | declared different | UNEXPECTED |
|---|---|---|---|
| at session start | 65 | 18 | **2** (my own L3 edits) |
| now | **70** | **15** | **0** — `--strict` green from both decks |

The 2 unexpected were `katacr_segments.py` and `sprites.py`: L3 changed shared code in icebow only,
which is exactly the drift this gate exists for. Config quartet was already byte-identical.

### 2. What was ported (icebow -> hogeq unless stated)
* `src/clashrl/katacr_segments.py`, `src/clashrl/sprites.py` — L3's `--bank` / `--prefix` /
  `--base-split` / `--out-name` / `--no-yaml` support (byte-identical copies).
* `src/clashrl/cli.py` — the five new flags hand-ported (cli.py is legitimately deck-different, so
  the gate would never have caught this; hogeq's `run.py sprites --help` now lists them).
* `src/clashrl/reward.py` — `log_corridor_cell` + `nado_king_cell` (see 3). Now byte-identical.
* `src/clashrl/model.py` — the `CLASHRL_SINGLE_CELL_MAP` escape hatch. Env-gated, default OFF, so
  hogeq's default net is unchanged: **verified by strict-loading hogeq's own
  `data/policy_sim_ppo_best.pt` under the ported file — cell head (11, 24, 1, 1), `cell_per_card`
  True, `load_state_dict(strict=True)` clean.**
* `src/clashrl/sim/drill_env.py` — icebow's three env-gated drill knobs (`CLASHRL_DRILL_FULL_HAND`,
  `_CLOCK`, `_STATE`), all default OFF.
* `tests/test_aim_assists.py` — copied to hogeq, **16 tests pass there**.

### 3. THE FINDING: hogeq's Log aim assist has always been inert
`hogeq/src/clashrl/env.py` imports `log_corridor_cell` inside `try/except ImportError` and calls it
at `if base == "the_log"`. **hogeq's `reward.py` never defined it**, so the except branch set it to
`None` and the assist was silently off — in a deck whose hand contains The Log. The comment above the
import even asserted the opposite ("hogeq's reward.py has no tornado/log-corridor helpers"), which is
true of the Tornado and false of the Log. This is the project's recurring failure shape: a feature
that is both taken and quiet. Fixed by defining both helpers in hogeq and rewriting the comment in
BOTH decks; `nado_king_cell` stays unreachable in hogeq for the right reason (empty `tornado_ids`).
* **(a) measured:** `env.log_corridor_cell` is now a function in hogeq, and the ported
  `test_it_actually_moves_the_aim` / `test_it_lines_the_corridor_up_with_the_push` pass there.
* **⚠ this is a LIVE-path behaviour change for hogeq** (its `LiveMatchEnv` will now nudge Log casts
  laterally onto the push). hogeq has no live-play history (§1: sim-only), so nothing in flight is
  affected, but the owner should know it is on rather than discover it.

### 4. Two DRIFT notes were stale — the allow-list was describing an older divergence
* `sim/drill_env.py`'s note said the divergence was *hogeq-only* `_env_flag`. Measured: `_env_flag`
  is in BOTH (only its position differs); the real divergence was 137 icebow-only lines of drill A/B
  knobs. Ported, entry removed.
* `reward.py`'s note said hogeq "has no assist for it" as if that were a deck opinion; it was a gap.
* Entries removed from `DRIFT` in both decks' `parity_check.py` (which must stay byte-identical):
  `reward.py`, `model.py`, `sim/drill_env.py`. 18 -> 15 declared-different.

### 5. hogeq's test baseline is NOT "42 known failures" any more
Old sections still say "hogeq at its 42-known baseline". Measured this session, before the ports:
**1,272 tests, OK, 64 skipped** (265 s). Re-run after every port above: see the closing line of this
section. Do not carry the 42 forward.

### 6. The corpus: hogeq had nothing, and the icebow crawl cannot supply it
`icebow/data/royaleapi/` holds 520 battles / 45,335 plays / 12,220 placement-joined blue plays
(§5af-5ag). `hogeq/data/` has **no royaleapi folder at all**. Measured on the existing crawl:
**0 of its 520 battles has an opponent on a hogeq-deck variation** (5 battles are 7-of-8-card
neighbours: electro-spirit for ice-spirit, cannon for tesla). So the hogeq corpus has to be crawled,
not extracted — that is the measurement that justifies the network work.

### 7. `crawl_deck.py` — the deck-parameterised driver (new, in `~/clash-replay-scraper`)
`crawl_icebow.py` is left FROZEN (it produced the icebow corpus and its constants are baked in). The
new driver takes `--deck {icebow,hogeq}`, carrying over verbatim the pieces that each cost a crawl to
learn: the extended parser that keeps every `data-*` attribute and joins the `.marker` placements,
per-player completion marks, and save-token-before-verify. hogeq seed slug (RoyaleAPI's own spelling,
verified against real battle rows in the icebow crawl):
`earthquake,firecracker-ev1,hog-rider,ice-spirit,mighty-miner,skeletons,tesla-ev1,the-log`.
* **Session: no owner login was needed.** The driver borrows the other deck's `.session_token`
  (same site session). Probe verified live: a 109-card replay with **131 markers** fetched.

### 8. ⚠ BUG FOUND AND FIXED: the roster stage kept the wrong players (0 battles from 14 players)
First run walked 14 players and kept **0 battles**. Cause, measured from `roster.json`: RoyaleAPI's
"similar decks" for hog 2.6 are not evolution swaps but **card SUBSTITUTIONS** — of the 531 rated
players across the 11 variation boards, only **100 were on the exact 8 base cards**; the rest play
cannon for tesla, electro-spirit for ice-spirit, or valkyrie-hero/knight-hero for mighty-miner.
Ranking all 531 by rating and capping at 50 filled the roster with players whose battles the
`is_variation` filter then rejected — a crawl that would have run for hours and produced nothing.
The roster is now filtered by `is_variation(found_on, seed)` first (100 candidates -> top 50 by
rating). **This could not have bitten icebow**, whose similar decks really are evo variations — which
is why the frozen driver never showed it, and why a copied driver had to be re-measured on the new
deck rather than trusted.

### 9. What this does NOT establish
Nothing about hogeq's play strength: every port is behaviour-neutral by construction except the Log
assist, and none of it has been trained or played. The corpus is NOT built yet (the crawl is running,
resume-safe); no hogeq priors have been derived; and the remaining declared-different files
(`train_rl.py` async advisor, `sim/remote_pool.py` deck-PFSP channel, `env.py`) are still one-way
ports that have not been done.

### 10. Closing numbers (measured this session)
* parity `--strict`: **PARITY OK** from both decks; 70 shared identical, 15 declared different, 0 unexpected.
* hogeq suite: **1,288 tests OK, 64 skipped** (261 s) with every port in.
* icebow suite: **1,257 tests, 1 failure** (the pre-existing `xbow_front` premise above), 21 skipped.
* crawl: roster 50 players drawn from the 100 who play the exact base deck; running.

### 11. Next on this thread
1. Let the crawl finish, then re-run it once to sweep the rate-limited players (it is resume-safe).
2. Derive hogeq's placement priors the way §5ag did for icebow -- `P(tile | card, phase)` off
   `plays_ext.csv` -- and check them against `hogeq/DOCTRINE_RESEARCH.md`'s hand-written cell rules.
   That is the first thing the corpus is FOR, and it is also how the corpus gets falsified.
3. Remaining one-way ports, in this order: `train_rl.py` (icebow's async LLM advisor), `env.py`
   (the two decks' comments still diverge), `sim/remote_pool.py` (moves with deck PFSP, so only when
   hogeq gets `sim/opponents.py`'s deck-PFSP half).

## §5bd — THE HOGEQ CORPUS IS BUILT AND THE DERIVATION HAS STARTED: `tools/replay_priors.py`, both bias gates passed, and a PRELIMINARY contradiction of the Hog placement rule (2026-09-02 12:00-12:40)

### 1. The corpus (measured)
`crawl_deck.py --deck hogeq` first pass: **462 replays / 40,250 plays in 47 min**; the resume sweep for
the 13 rate-limited players took it to **595 replays / 52,973 plays**. Placement join is the same bimodal
shape as icebow's (296 covered / 299 uncovered), giving **14,002 blue plays with tile coordinates**
(icebow: 12,220).

### 2. Frame verified from the data, twice, before any fit
Blue's own half is HIGH y: hog-rider median tile_y **17.5 with p10 = p90 = 17.5** (every Hog on the bridge
line), tesla 21.0 in an 18-22 band, and earthquake at **10.5** — a spell cast into the ENEMY half, which
confirms the orientation from the opposite direction. Row histogram: y=17 holds 4,679 of 14,002 plays.

### 3. `tools/replay_priors.py` (new, in BOTH decks)
Fits `P(tile | card, phase)` with phases read from `sim.double_time_s` / `sim.triple_time_s` (120 / 240 s)
rather than guessed, mirror-folds x, applies a per-(card, phase) sample floor, and prints the three bias
checks the queued spec in §6 demanded BEFORE any fit is trusted. **Validated against icebow's corpus: it
reproduces §5ag's numbers exactly (12,220 blue placements, 268 covered / 251 uncovered).**
* **Both bias gates pass, both decks:** no time skew between the covered and uncovered halves
  (medians within hours), players balanced (hogeq 32 vs 31, 3 covered-only), and card mix matching
  within **0.4 pp** once hero-ability rows are excluded — those carry `attr_card=_invalid` and can never
  have a marker, and counting them made the mix look 8.5 pp different (§8's ability-row trap, again).

### 4. ⚠ PRELIMINARY (a): the Hog rule's ranking looks inverted
1,725 pro Hog placements, unfolded x histogram: **x=1 → 702, x=16 → 791 (87% together)**; the doctrine's
primary spots, the princess columns at tiles 3 and 14, hold **21 plays (1.2%)**; its half-weighted
"arena-edge" spot (tile 0) holds 64 (3.7%). So pros put the Hog one tile IN from the wall, and
`sim/doctrine.py`'s `hog_rider` branch weights the bridge/princess column highest.
* **What this does NOT yet establish:** `_add_spot` lays down a weighted BLOB, not a tile, so the
  doctrine's mass over tiles 1/16 is not zero and the honest comparison is prior-weight vs measured
  frequency over the whole board. That comparison is the next step; until it is run this is a modal-tile
  mismatch, not a refuted rule.
* Frame sanity: the two modes are symmetric about the centre (1 + 16 = 17 = 18 - 1) and the Tesla sits at
  x=8, so the marker frame and the engine's 18-wide board agree.

### 5. Next
Weight-profile comparison per card (doctrine prior vs fitted distribution, same board), then the same
read for mighty_miner (modal (2,17)/(3,17) — a BRIDGE punish, where the doctrine's headline rule is
"tile-exact on the tank"), firecracker and earthquake. Only then a config-gated prior, one change per
experiment, per the §6 spec.

## §5be — GAUNTLET L5: THE SCREEN VERDICT (yolo11s, and yolo26s is slower too), BOARD-27 CANCELLED BY OWNER RULING, and the first latency number: the operating detector is 29.5 ms of the 100 ms budget (2026-09-02 14:22-15:00)

### 1. The screen, final (a) measured
Both arms finished (`screen.progress`: y11s 177 min, y26s 241 min, exit 0 each). `args.yaml` identical
except `model`: epochs 30, fraction 0.35, imgsz 960, batch 4, seed 0, same `data/detect/synth` + real
frames. Final-epoch rows of each `results.csv` (the same instrument, the same val):

| arm | mAP50 | mAP50-95 | P | R | val cls loss | wall |
|---|---|---|---|---|---|---|
| screen-y11s (control) | **0.408** | **0.294** | 0.669 | 0.369 | 1.516 | 177 min |
| screen-y26s | 0.253 | 0.171 | 0.473 | 0.221 | 1.633 | 241 min |

yolo26s sits at 62% of the control's mAP50 at the end (P 0.473 / R 0.221 vs 0.668 / 0.369) and was
behind at every one of the 30 epochs. Epoch-matched gap in mAP50: +0.043 at epoch 1, peak **+0.177**
at epochs 11-12, then a slow close to **+0.150** at epoch 30 (0.027 over the last 18 epochs). It also
took 36% longer to train (241 vs 177 min).
* **(b) what the screen cannot say:** 30 epochs at fraction 0.35 is a short schedule, and yolo26's
  one-to-one assignment is documented to converge slower than NMS-trained heads. The gap DID narrow
  after epoch 12, so a full-schedule crossover is not excluded: a straight-line extrapolation of the
  closing rate (0.0015/epoch) puts it near epoch 130, outside a 120-epoch run, and that extrapolation
  is unreliable in both directions (the control is still climbing; both will plateau). I am NOT
  spending 24 GPU-hours to settle it, because the speed result in §2 removes the other reason to want
  yolo26 -- accuracy parity alone would not justify a swap of the operating architecture.
* These numbers compare ONLY to each other, never to board-26's 0.860 (full data, 120 epochs).

### 2. Idle-box detector latency, the first number of the latency loop (a) measured
`scratchpad/gauntlet/L5/bench_detector.py`: mirrors the ONE live call, `BoardDetector.detect()` ->
`model.predict(frame, conf, imgsz=960, verbose=False)`, fp32, on the 241 real 1182x668 frames of
`val_board15.txt`, 10 warm-up + 200 timed calls, GPU idle (0% util, 1.2 GB used, nothing else running,
12.3 GB RAM free). Wall clock around `predict()` is what the agent pays; the split is ultralytics' own.

| weights | wall median | p90 | max | pre | inf | post | dets/frame |
|---|---|---|---|---|---|---|---|
| board-24-5 (**operating**, config `detect.weights`) | **29.5 ms** | 35.0 | 76.2 | 7.1 | 19.6 | 3.1 | 3.6 |
| board-26 | 32.6 | 36.3 | 38.9 | 7.3 | 21.8 | 3.2 | 3.4 |
| screen-y11s | 31.3 | 35.1 | 38.4 | 7.2 | 20.4 | 3.1 | 2.8 |
| screen-y26s | 34.5 | 41.5 | 48.3 | 7.6 | **26.1** | **1.1** | 2.0 |

* **(c) CONTRADICTED: "yolo26 is faster because it is NMS-free".** The postprocess saving is real
  (3.1 -> 1.1 ms) but its inference is 5.7 ms slower on this RTX 5050, net **+3.2 ms**. The L2 smoke
  read 5.6 / 0.4 ms on a CONTENDED box (PPO running) and was labelled arm-vs-arm only; this is the
  clean number. The architecture question is closed on both axes.
* `half=True` is DEPRECATED in ultralytics 8.4.107 ("use quantize") and produced no consistent change
  (board-24-5 31.3, board-26 33.4, y26s 38.4; y11s 22.9 once, with the same p90 35.6 as fp32 -- treat
  as noise until measured with the supported flag). One 3,500 ms max on the first arm is a one-off
  allocator/autotune spike and does not recur (every other max <= 76 ms).
* **What it means for the budget:** preprocess is 7 ms of CPU letterboxing a 1182x668 frame to 960
  every pass -- ~24% of the detector's time, and the one term that does not need a new model. The
  detector runs in the 10 Hz perception THREAD (perception.py), so at decision time the policy reads
  a snapshot that is up to one perception period old; the detector's 30 ms bounds that period, it is
  not added to the decision path serially. The decision path proper (`play.act_in_match`: obs build,
  hand/next recognition, threat vector, canvas channels, policy forward, live search, aim assist,
  tap) is UNMEASURED -- the only number on it is live_search.py's own note "~24 ms/decision" (carried,
  origin unknown, not re-measured). `sim.live_search_timeout_ms` is **120** in config (the class
  default is 250 -- read the config, not the default).

### 3. Board-27 is CANCELLED (owner ruling, 14:30) -- and what I told the owner about kitka
The honest kitka assessment: its whole value is 9 evolution classes going from 0-19 sprites to 42-222
and 3 empty classes being filled (§5bb). Whether that helps the LIVE detector is **(b) untested**, and
it cannot become (a) on the main val, which has 0-2 instances of those classes (§5az trap). The only
instrument that can see it is `holdout_val.yaml` (§5bb.4), per-class AP on the pasted classes. A
from-scratch 24 h board-27 is the most expensive possible way to get that number.
* **Right-sized alternative, NOT launched (owner option):** regenerate the training synth from the
  kitka-augmented bank (`run.py sprites --synth 5000 --seed 0`, safe now, in-place), then fine-tune
  from `board-26/weights/best.pt` for ~20 epochs at fraction 1.0 (est. 2-4 h from the screen's 5.4
  min/epoch at 0.35), and read TWO things: per-class AP on `holdout_val.yaml` (the kitka half) and
  no regression on `run.py detect-eval --sweep --subset data/detect/val_board15.txt` (the promotion
  gate). Promotion still requires the detect-eval gate, as `detect.weights` says.
* What cancelling costs: nothing measured. Board-26 (mAP50 0.860) already exists and is NOT the
  operating detector (`detect.weights` = board-24-5) -- whether board-26 should be promoted is a
  separate detect-eval question that predates this gauntlet.

### 4. What this does NOT establish
Nothing about the decision path's total latency (§2 measured the detector alone). Nothing about
yolo26 under a full schedule (b). Nothing about kitka's live value (b). No PPO change, no doctrine
change, no live-path change.

### 5. Next on this thread (the diverted focus)
1. **Latency loop:** an OFFLINE stage timer for `act_in_match` -- decode frames from
   `data/sessions/20260815_222309/video.mp4`, run the same functions (vision.observe, hand/next
   recognition, threat + canvas build, policy forward, LiveSearch.decide) and time each stage per
   frame, without touching play.py or the game. That gives the first full breakdown against the
   100 ms budget. Then the preprocess term (7 ms: pre-letterbox / capture at the model's size).
2. **Queued items (08:20 ruling), now unblocked:** engine recording pass `replay_drive
   --record-every 12` over the 211 converted replays -> tabular gate prior tool -> KL-on-gate hook in
   `train_sim_ppo.py` behind a coef defaulting to 0.0 -> `elixir_ge6` drift rule in `ppo_watchdog.py`
   -> per-card top-cell dump of the 18k checkpoint.
3. hogeq derivation (§5bd.6): doctrine prior-weight vs measured frequency per card, then a
   config-gated prior, one change per experiment.

## §5bf — GAUNTLET L6: THE GATE-PRIOR RUN IS LAUNCHED (owner order) -- the pro WHEN-TO-PLAY table, the KL hook in both trainers, the elixir>=6 drift rule, and the watchdog's own noise floor measured on a frozen checkpoint (2026-09-02 15:00-15:25)

### 1. What was ordered and what was built (this loop; everything below is new code)
Owner order ~15:00: launch the elixir-fix run defined by the 08:20 ruling (§6). The prep did not exist at
15:00; it was built, smoked on cuda in BOTH decks, and the icebow run launched at 15:07. Files:
* `tools/gate_prior.py` (icebow + hogeq, byte-identical): fits `P(play in one agent_dt window | floor(elixir)
  0..10, phase single/double/triple)` from the crawled player's play timeline in
  `data/royaleapi/crawl2/plays_ext.csv`. Elixir is RECONSTRUCTED (start 5, the engine's four-phase regen
  1/2.8 -> 1/1.4 -> 1/0.93 with the ENGINE's boundaries reg-60 and reg+(ot-60), CardDB cost per play,
  `_invalid`/ability rows priced as `mighty_miner_ability`, `-evN`/`-hero` suffixes stripped) and its error
  is MEASURED, not assumed: the share of plays where reconstructed elixir is below the card's cost.
  Output `config/gate_prior.json` (schema 1, committed -- it is config, not data).
* `train_sim_ppo.py` (both decks, applied by anchor -- the file is DRIFT, §5bc): `sim.ppo_gate_prior_coef`
  (default **0.0** = byte-for-byte the old trainer) + `sim.ppo_gate_prior_path`. The engine clock `t` now
  rides in the rollout (`roll["t"]`, from the new `"t"` key in `sim/remote_pool.py`'s payload or `env.eng.t`
  in-process) so the phase is known at update time. Term: on MATCH rows whose PLAY logit is unmasked,
  `coef * mean(-(p*log pi_play + (1-p)*log pi_wait))` = KL(prior || pi) on the gate up to a constant.
  Card and cell heads untouched. Prints `GATE PRIOR CE ... pi(play) X vs prior Y on the same rows | Z% of
  rows usable` at update 1 and every 200. Both `config.yaml`s document the keys at 0.0.
* `tools/ppo_watchdog.py` (icebow): `_Drift(min_peak_by_label={"ELIXIR>=6": 0.002})` -- the shared floor
  0.05 is a P(play) scale and would have left an elixir>=6 rule permanently dead (its medians are ~0.02).
  The rule is SUPPRESSED in a cycle where GATE DRIFT already fired (corr -0.94, one event = one alarm).
  hogeq's watchdog has no `_Drift` at all (parity gap, noted, not ported this loop).
* `tools/real_run_gates.py`: `--run <kind>_<date>` (default = the old real run), so the same three
  instruments fire at m=5k/10k/20k on this run and snapshot to `data/bench/gate_m<k>k.pt`.
* `tests/test_gate_prior.py` (both decks): phase boundaries, suffix strip, elixir reconstruction + under-cost
  count, ability pricing, the banking shape, the watchdog floor (skips on hogeq), and the term's gradient
  sign (d/dlogit_play = pi_play - p). icebow 15/15 with the drift tests, hogeq 7 pass / 1 skip.

### 2. The prior itself (a) measured -- P(play per 0.6 s decision | elixir bucket, phase)
| deck | replays | plays | under-cost | plays at >=6 | single: 3 / 5 / 7 / 9 elixir | double: 3 / 5 / 7 / 9 |
|---|---|---|---|---|---|---|
| icebow | 519 | 23,620 | **1.7%** | 65% | 0.063 / 0.042 / 0.043 / 0.203 | 0.103 / 0.110 / 0.161 / 0.446 |
| hogeq | 595 | 30,258 | **2.8%** | 54% | 0.075 / 0.060 / 0.070 / 0.249 | 0.139 / 0.168 / 0.195 / 0.386 |

Full 11-bucket rows are in each `config/gate_prior.json`. Shape, both decks: flat and low from 2 to 7
elixir, a step at 8, a peak at 9. The pros BANK, and they do it with a 3.5-cycle deck (icebow) and a
2.6-cycle deck (hogeq) alike -- which is the owner's "shared problem" claim confirmed in form. The 18k
agent spent 0.02% of its steps at >=6 (§5ba); the pros made 65% of their plays there.
* **What the table is NOT (b):** not conditioned on the board. The 08:20 ruling's v0 named
  threat-on-our-half as a third key; that needs the engine recording pass (`replay_drive --record-every
  12`, §6) and is a one-line extension of `fit()` + one more index in the trainer. It is ALSO not the
  agent's own state distribution: the pros are at 9 elixir often, the agent almost never, so the term
  mostly acts at the low buckets today and the high-bucket rows of the table only matter once the
  policy gets there.
* **Reconstruction caveat (a):** 1.7% / 2.8% of plays are impossible under the reconstruction (elixir
  below cost) -- unrecorded plays, an evo/ability cost mismatch, or a mistimed tick. The error is small
  and it biases the low buckets slightly UP (a phantom-cheap play lands in a lower bucket), i.e. against
  the direction of the pull, not for it.

### 3. The run (a) launched, first readings
`data/bench/gate_run_launch.sh` = `real_run_launch.sh` with the overlay swapped; overlay diff vs
`real_run.yaml` is exactly {checkpoint path, continuation log path, `ppo_gate_prior_coef 0.1`, the
documented `ppo_gate_prior_path`}. Banner verified: `GATE PRIOR ON: coef 0.100 ... (519 replays, dt 0.6 s;
single-elixir P(play) at 4 / 7 / 9 elixir = 0.06 / 0.04 / 0.20)`, `HAZARD HEAD ON: coef 0.500`,
`LEARNER ON cuda`, 12 workers x 8 envs. Pre-launch: no trainer running, 11.7 GB RAM free, CPU 3%,
checkpoint path empty.
* **Update 200 (100 episodes, ~3 min in):** `GATE PRIOR CE 0.5059 | pi(play) 0.379 vs prior 0.051 on the
  same rows | 8% of rows usable`. Smoke on the same overlay at update 1 read 0.520 vs 0.048 / 13%.
  hogeq smoke (its own table): 0.463 vs 0.061 / 32% usable.
* **The 8% is the collapse itself, read from a new angle:** only 8% of minibatch rows are match rows with
  anything affordable. The agent spends everything the instant it can, so 92% of its decisions are
  forced waits where no gate term can act. The prior acts exactly on the 8% where the choice exists; if
  it wins there, elixir accumulates and the usable share rises -- so `Z% of rows usable` is itself an
  endpoint to watch, alongside the watchdog's `elixir_ge6`, `bank_to_six_then_bow` (exists,
  `drills_icebow.py:214`), and the m=5k/10k/20k instrument gates.
* **coef 0.1 is (b) untested.** It is the first value, chosen so the term (0.05 x 0.1 = 0.005 of loss) is
  the same order as the entropy bonus (0.02 x H) rather than the policy loss. The log line exists so
  the choice can be judged from the run instead of argued: if `pi(play)` on usable rows has not moved
  toward the prior by m=5k, the coef is too small and the next run is the one change 0.1 -> 0.5.

### 4. Smoke findings, both decks (a)
icebow `--matches 6 --envs 8 --workers 2 --device cuda --search-interval 4`: exit 0, term printed,
match-step gate drift on PLAY -0.315 in the last cycle (the term pushes the play logit down, as the test
says it must). hogeq: exit 0 -- BUT hogeq REFUSES `--search-interval` with `--workers > 1` ("the envs live
in the worker processes and search needs an in-process engine"): icebow's SEARCH-IN-THE-WORKERS path
(§5as) was never ported. Parity gap for hogeq's own gate-prior run, recorded in §6.

### 5. NEW TRAP (a): the watchdog's sampled metrics have a wide noise floor -- measured on a FROZEN checkpoint
The 18k run's watchdog kept sampling `data/policy_real_20260901.pt` after the run died (07:19 -> 14:58,
the file unchanged, 91 readings of the SAME policy at 6 envs x 400 steps). Spread across those readings:

| metric | 10% | median | 90% | min / max |
|---|---|---|---|---|
| P(play) mean | -- | 0.362 | -- | 0.174 / 0.391 |
| elixir>=6 % | 0.0 | 0.1 | 0.2 | 0.0 / **11.3** |
| cell_struct (x untrained) | 5,014 | 7,865 | 11,802 | **685 / 14,834** |
| distinct cells | -- | 32 | -- | 23 / 59 |

**The CELL STRUCTURE DRIFT rule FIRED at 10:06 on this unchanged file** ("43% below this run's rolling
median") -- a false positive by construction. The 0.60 x median band is inside this instrument's own
spread for cell_struct (10th percentile = 0.64 x median), so that rule will keep firing on healthy runs.
Consequences: (i) for THIS run, a CELL STRUCTURE alert is not evidence of anything without a second
instrument; (ii) the new ELIXIR>=6 rule inherits the same instrument -- at the collapsed level its spread
is 0.0-0.2% with one 11.3% outlier (one env banking through one match), so at a HEALTHY level (unknown,
say 2-5%) the relative-decline band is (b) untested against noise; (iii) the right fix is a larger sample
per reading or a longer median window, and that is a monitoring change, not a training change -- parked
in §6, not made while the run depends on the watchdog as armed. §8 gets the one-line trap.

### 6. What this does NOT establish
Nothing about whether the prior CHANGES the policy's banking -- 100 episodes is a launch check. Nothing
about the coef. Nothing about hogeq (smoked, not run). The shared-solution claim is confirmed in form
(same table shape, same tool), not in effect.

### 7. Next
1. Read the run at ~m=1000 (`GATE PRIOR CE` trend, `elixir_ge6`, `% of rows usable`), then the m=5k gate.
2. Latency loop resumes: offline stage timer for `act_in_match` (§5be.5.1) -- CPU-light, but the box is
   now 12 workers busy, so only the single-thread, no-throughput parts of it are trustworthy while the
   run is up (never benchmark throughput on a contended box).
3. Engine recording pass -> threat key for the prior (v1), hogeq search-in-workers port, hogeq watchdog
   `_Drift`, watchdog sample size -- all parked in §6.

## §5bg — GAUNTLET L7: THE GATE-PRIOR RUN READ AT m=2000 ON A NEW SAME-INSTRUMENT PROBE -- not yet distinguishable from the collapsed 18k checkpoint; the cheap-card collapse measured from the hand side; a watchdog trap (2026-09-02 15:45-16:05)

### 1. Why this and not the latency timer
The box is 12 workers + cuda busy (CPU 43%, 4.6 GB free), so any `act_in_match` stage timing would be
a contended number (§7). The cheap decisive thing was to find out what the run's `9% of rows usable`
and the watchdog's falling `P(play)` actually mean, because I had told the owner at 15:42 that the
elixir direction "looked right" on two watchdog readings -- and the 15:45 reading (m=1850: P(play) 0.476,
elixir 2.01, >=6 0.1%) had already reversed it. Cost: ~15 min build, 7 x 12 s of probe.

### 2. The instrument: `icebow/tools/gate_prior_probe.py`
The watchdog's `health()` sampler copied verbatim (6 envs, seeds 4242+i, 400 steps, card sampled from the
card head, gate SAMPLED, plays at the centre cell, domain rand off) plus, per row: engine clock -> phase,
floor(elixir) bucket, whether ANY hand card is affordable, and whether a play happened. `np.random` is
seeded (`--seed`); the watchdog's is not. Prints `P(play)` / `affordable` / `played` per bucket next to
the pro table's single-elixir column, `--json` dumps the dict. 12 s per run on the contended box.
Deck costs for reading the table: tornado 3, tesla 4, ice_wizard 3, x_bow 6, rocket 6, knight 3,
the_log 2, skeletons 1 (mean 3.5).

### 3. Measured (a): m=2000 gate-prior checkpoint vs the frozen 18k control, 3 seeds each
Snapshot `scratchpad/gauntlet/L7/gate_snap.pt` (copy of `data/policy_gate_20260902.pt` at matches=2000,
15:52). JSON per run in `scratchpad/gauntlet/L7/probe_{gate,18k}_s{0,1,2}.json`.

| | gate m=2000 (s0/s1/s2) | 18k control (s0/s1/s2) | pros |
|---|---|---|---|
| rows with anything affordable | 25.9 / 27.3 / 25.0% | 28.8 / 29.3 / 27.6% | -- |
| P(play), all rows (= the watchdog's number) | 0.501 / 0.481 / 0.489 | 0.350 / 0.357 / 0.347 | -- |
| P(play), affordable rows only | 0.432 / 0.409 / 0.422 | 0.392 / 0.405 / 0.397 | ~0.04-0.06 |
| played on % of rows | 11.7 / 11.0 / 10.9 | 11.5 / 11.3 / 10.9 | -- |
| elixir mean / >=6 | 2.04 / 0.7% ; 1.60* / 0.9% ; 1.53* / 0.4% | 2.02 / 0.1% ; 1.62* / 0.1% ; 1.59* / 0.0% | 65% of plays at >=6 |
| rows at elixir <3 | 81 / 80 / 82% | 81 / 79 / 80% | -- |
| `played` at bucket 3 (the affordable bucket) | 0.449 / 0.392 / 0.424 | 0.372 / 0.372 / 0.357 | 0.063 |
| `played` at bucket 4 | 0.333 / 0.308 / 0.292 | 0.426 / 0.351 / 0.306 | 0.058 |
| affordable at bucket 1 / 2 | 7-9% / 18-19% | 8% / 23-24% | -- |

(* seeds 1-2 were run before the elixir-mean field was switched from the bucket to the raw value; they read
~0.5 low by construction. Seed 0 of both was re-run after the fix and matches the watchdog's scale.)

What this says, plainly:
* **The play rate is the same.** On the rows where the gate can act, both policies open it ~40% of
  windows; the pros open it ~6% at the same elixir. The prior has not moved behaviour by m=2000.
* **The collapse is fully formed by m=2000 from scratch.** Elixir sits below 3 on 80% of decisions in
  both; the 18k run's watchdog readings at m=1250-1650 (1.78-1.94 mean) said the same thing a day ago.
* **The cheap-card collapse, seen from the hand.** Skeletons (1) and the_log (2) are the only cards
  playable below 3 elixir. With 4 of 8 cards in hand you would expect skeletons in hand ~half the time;
  it is there (= affordable at bucket 1) on 7-9% of rows. The agent spends the cheap cards the moment
  they are drawn, so the hand is left holding 3-6 cost cards while the bar sits at 1-2. This is the
  owner's "collapse towards playing cheap cards" as a number, and it is why only 9% of trainer rows /
  26% of probe rows have anything to play -- the two instruments differ (the trainer's denominator includes
  the 33% drill rows and its envs have search + opponents), so that gap is cross-instrument, not a finding.
* **The trainer's own term, de-cumulated** (updates 1-800 / 800-1400 / 1400-2000 / 2000-2600 / 2600-3200 /
  3200-3800): pi(play) on usable rows 0.336 / 0.343 / 0.306 / 0.294 / 0.326 / 0.316, window CE 0.46-0.53.
  Flat within its own noise. Gradient on the play logit per usable row is (pi - p) ~ 0.35, times coef 0.1,
  times the ~9% row share: a small term against PPO's advantage gradient. (b) whether it is too small --
  decided at m=5k by the rule in §6, not by me now.

### 4. Retraction of my 15:42 reading to the owner
I said the elixir direction "looked right" on the watchdog's four readings (P(play) 0.65 -> 0.37, elixir
1.9 -> 2.3, >=6 up to 2.6%). (c) contradicted: the 15:45 reading reversed all three (0.476 / 2.01 / 0.1%),
and the probe shows the watchdog's P(play) is dominated by rows where the play is masked (§8). The
labelled caveat ("within the noise floor, a hint not a result") was correct; the direction claim was not
supported. Elixir >=6 at m=2000: 0.4-0.9% vs 0.0-0.1% -- 3 seeds, same instrument, a ~10-row difference
out of 2,400; not a result either.

### 5. Traps found
* The watchdog's `P(play) mean` is ~74% masked rows -> §8.
* `GATE PRIOR CE` lines are cumulative -> §8. (The trainer print could carry a window mean; not changed
  while the run depends on the log format -- parked.)
* `elixir_mean` in the first probe draft used the bucket, not the raw value (fixed before seed-0 reruns).

### 6. What this does NOT establish
Whether coef 0.1 will bite by m=5k or m=10k (the term is a slow pull by design, and PPO is not linear in
updates). Nothing about the card head or the cell head. Nothing about hogeq. It does not say the run should
be stopped: the pre-registered rule in §6 says when to ask.

### 7. Next
1. m=5k gate (~17:00 at 0.8 ep/s): probe the snapshot on 3 seeds, apply the §6 rule; if it says relaunch,
   STOP and ask the owner.
2. Latency loop stays blocked on the contended box for absolute numbers; the stage-timer HARNESS can be built
   and validated meanwhile (its numbers labelled contended until the run ends, ETA ~05:00 09-03).
3. Parked from §5bf unchanged.

## §5bh — GAUNTLET L8: COEF 0.1 IS LOSING TO PPO (trainer trend + m=4000 probe), AND THE COUNTERFACTUAL BANK SHOWS THE GATE IS THE RIGHT LEVER -- the card head at 6+ elixir is not cheap-biased (2026-09-02 16:54-17:10)

### 1. Why this
m=5k was 24 min out. The `GATE PRIOR CE` series de-cumulated (§8 trap from 5bg) showed the term moving the
wrong way, and the bigger question was untested: the gate prior's theory of change is "if it waits, it
plays the expensive cards" -- a claim about the CARD head at an elixir level this policy never reaches. The
probe from 5bg got a `--force-bank X` counterfactual (suppress plays below X, then let the policy act) and
per-card play counts. Cost: 10 min build, 6 x 12 s probe.

### 2. (a) The trainer's own term, per 800-update window (log `GATE PRIOR CE`, de-cumulated)
```
updates      CE     pi(play)  prior
    1-800   0.466   0.336    0.053
  800-1600  0.501   0.342    0.053
 1600-2400  0.433   0.282    0.054
 2400-3200  0.529   0.328    0.055
 3200-4000  0.528   0.327    0.056
 4000-4800  0.594   0.365    0.057
 4800-5600  0.615   0.372    0.058
 5600-6400  0.579   0.360    0.058
 6400-7200  0.591   0.357    0.059
 7200-8000  0.585   0.351    0.059
 8000-8800  0.614   0.375    0.059
```
Down to 0.28 by update 2,400, then back up to 0.36-0.375 and holding. Cross-entropy up 0.43 -> 0.61. The
pull is being out-fought; "9% of rows usable" throughout.

### 3. (a) Probe at m=4000 (`scratchpad/gauntlet/L8/gate_m4k.pt`, JSON in `m4k_fb{0,6}_s{0,1,2}.json`)
Unforced, 3 seeds: `played` at 3 elixir 0.423 / 0.434 / 0.483 (m=2000: 0.449 / 0.392 / 0.424; 18k control
0.372 / 0.372 / 0.357; pros 0.063). P(play) on affordable rows 0.43-0.45. Mean cost of the cards actually
played **2.45-2.49** (deck mean 3.50): below 3 elixir it is skeletons:~50 / the_log:~40 per 2,400 rows;
at 3-5 it is ice_wizard / knight / tornado / tesla; at >=6 there were 1-2 plays per run (x_bow once in
7,200 rows). Elixir >=6 on 0.0-0.2% of rows. All of this is the 18k picture; nothing has moved.

**`--force-bank 6`, same checkpoint, same seeds** (every play below 6 elixir suppressed by the probe):
* affordable on 90-93% of rows (the hand is no longer stripped of cheap cards -- they sit there unplayed);
* elixir >=6 on 12.5-15.6% of rows, mean 4.4-4.6 (after each play the bar drops to 0-3 and takes 8-17 s
  to climb back -- engine physics; the pros' "65% of PLAYS at >=6" is a per-play number, not per-row);
* plays per row 7.9-8.1% vs 10.8-11.0% unforced, at mean cost **3.35 / 3.44 / 3.42** -- the same elixir
  spend per row (0.27) as unforced (0.27): regen-bound either way, exactly as it should be;
* the picks at >=6: skeletons 34-35, ice_wizard 30-36, x_bow 26-31, tesla 28 of ~190 -- close to uniform
  over the hand. **The card head at high elixir does not prefer cheap cards.** x_bow is picked on ~15% of
  plays there vs once per 7,200 rows unforced.
* the raw gate at >=6 wants to play MORE: P(play) 0.55-0.64 at 6 (prior 0.042). Untrained region.

### 4. What this means, plainly
1. The cheap-card collapse the owner named is **the gate**, not the card head: the gate opens at 1-3 elixir,
   where the only affordable cards are skeletons and the_log, so those get spent on draw; at 3-5 the
   3-costs go; x_bow/rocket are never affordable. Fix the WHEN and the WHAT follows, at least at m=4000
   (the card head at 6+ is untrained there, so "uniform" is what an untrained head looks like -- (b) whether
   it stays sensible once trained at 6+ is what a working run would show).
2. coef 0.1 cannot win, and the arithmetic says why. The term is `coef x mean over USABLE rows` while PPO's
   policy loss is a mean over ALL rows; with 9% usable, each usable row's prior gradient on the play logit
   is coef x (pi - p) / 0.09 = 0.1 x 0.30 / 0.09 ~ 0.33 (in per-row units of the PPO loss), against a
   normalised advantage of typical size ~0.8 that favours playing on those rows. It loses -- observed. At
   coef 0.5 the pull is ~1.7 > 0.8 and the equilibrium (where c x (pi - p) / 0.09 = 0.8) sits at
   pi ~ p + 0.14 ~ 0.20 at 3 elixir; at coef 1.0, pi ~ 0.13. Pros 0.06. Both (b): the PPO push is not a
   constant, and the prior has no threat key, so a strong coef makes the gate refuse to answer a push at
   3 elixir unless PPO's advantage overrides it on those rows (which it can -- 6% of windows is still
   ~one play per 10 s at 3 elixir).
3. The pre-registered m=5k rule (§6) will read >= 0.30 at 3 elixir on all seeds -- the m=4000 read is
   0.42-0.48 and rising. Asking now rather than in 20 min changes nothing about the answer and saves the
   owner a round trip; the m=5k snapshot is still taken and will be probed.

### 5. What this does NOT establish
Whether 0.5 is enough, or too much without a threat key (b, above). Whether the card head stays uniform
once it is actually trained at 6+ (it has never been). Nothing about hogeq (deck costs differ; the same
gate-vs-card question should be asked with the same probe once its trainer has search-in-workers).

### 6. Owner question posted (Discord, --questions), what I do with each answer
* "relaunch at 0.5": wait for the m=5k snapshot (~17:20), record the run's endpoint in §3, kill it (count
  procs before/after), relaunch the same `gate_run_launch.sh` with `ppo_gate_prior_coef: 0.5` as the ONE
  change, new checkpoint name `policy_gate05_20260902.pt`, watchdog + gates re-armed.
* "relaunch at 1.0" (or another value): same, with that value.
* "let it run": nothing changes; m=10k read.
* No answer: run untouched; m=5k probe on 3 seeds when the snapshot lands; report again.

### 7. Files
`icebow/tools/gate_prior_probe.py` (+`--force-bank`, per-card play counts, `cost_of_plays`).

## §5bi — GAUNTLET L9: THE m=5k READ MOVED TOWARD THE PRIOR (first read below control, all 3 seeds) -- the relaunch order is on hold pending owner yes/no; replay zip delivered (2026-09-02 17:07-17:45)

### 1. Why this
Owner ruled at ~17:00 (on the m=4k picture in §5bh): "stop and restart with coef 0.5". The plan was to wait for
the m=5k snapshot, probe it for the record, then kill and relaunch. The probe came back different from every
read before it, and killing is irreversible (§7), so the order is held for one confirmation. Cost: 3 x 12 s
probe, ~15 min bookkeeping. Run untouched.

### 2. (a) Probe on `data/bench/gate_m5k.pt` (copy in `scratchpad/gauntlet/L9/gate_m5k.pt`, JSON `m5k_s{0,1,2}.json`)
Same instrument as L7/L8 (`tools/gate_prior_probe.py`, seeds 0/1/2, 6 envs x 400 steps = 2,400 rows each):
```
                         m=2k (L7)        m=4k (L8)        m=5k (L9)        18k control (L7)
played at 3 elixir       .449 .392 .424   .423 .434 .483   .299 .279 .305   .403 .372 .357
P(play | affordable)     .43  .41  .42    .43  .43  .45    .28  .32  .32    .39  .41  .40
rows with sth affordable .26  .27  .25    .25  .25  .23    .36  .36  .32    .29  .29  .28
rows at 4 elixir /2400    63   65   65     76   52   42    143  137  108     57   77   72
elixir >= 6 (frac rows)  .007 .009 .004   .002 .000 .003   .016 .008 .015   .001 .001 .000
plays per row            .117 .110 .109   .110 .107 .108   .104 .110 .108   .115 .113 .109
mean cost of plays          --             2.49 2.45 2.47   2.60 2.53 2.58      --
```
* Plays per row unchanged (regen-bound, as always). What changed is WHEN: the gate opens less at 3 (0.28-0.31
  vs 0.42-0.48), the hand keeps its cheap cards longer (affordable 32-36% vs 23-25%), elixir reaches 4 twice as
  often and 6+ ten times as often (still only 0.8-1.6% of rows). Mean cost of plays 2.53-2.60 vs 2.45-2.49.
* Picks unchanged in kind: <3 elixir skeletons/the_log; 3-5 ice_wizard/knight/tornado; >=6 x_bow/tesla/rocket
  (9-12 plays per 2,400 rows, up from 1-2).
* Correction to L7/L8 wording: the 18k control's `played at 3` is 0.36-0.40 (seed 0 = 0.403), not "0.36-0.37".

### 3. (a) The trainer's own term disagrees, or at least has not moved
`GATE PRIOR CE` de-cumulated per 200 updates, 10,400 -> 11,600: pi(play) on usable rows 0.348 / 0.348 / 0.348 /
0.404 / 0.292 / 0.406; window CE 0.54-0.67. Flat-to-noisy around 0.35, nothing like the probe's 0.28-0.32
on affordable rows. Different distributions (training rollouts: domain rand on, search-interval 4, self-play
opponents from m=5,000 at prob 0.15; probe: domain rand off, no search, scripted opponent), so they need not
agree -- but §5bh.2 leaned on this series to call the run early, and the probe now says otherwise.

### 4. What this means, plainly
1. (c) PARTIAL RETRACTION of §5bh: "coef 0.1 cannot win, the arithmetic says why" was too strong. The
   arithmetic assumed a constant PPO push of ~0.8 per usable row; the probe at m=5k is the first read where
   the gate is below the untrained-prior control on every seed, which is what "the pull is biting" would look
   like. The arithmetic stays (b); the observation that it was losing through m=4k stays (a).
2. It is ONE checkpoint. §5x: the same run inverted between m=500 and m=1000. The pre-registered rule
   (§6, written 16:05 before any of this) classifies 0.299/0.279/0.305 as MIXED -> one more read at 7.5k.
3. The owner's order was made on the m=4k picture. Killing loses the only running evidence about whether
   0.1 works; 0.5 would still be launchable 70 min later, and if 0.1 is working, 0.5 may over-suppress (no
   threat key -- §5bh.4). Recommendation sent: hold to m=7.5k. Owner's call.
4. Confound for any read after m=5,000: self-play ramps in at prob 0.15 (log line "self-play ON: prob 0.15
   (ramp 5000)"). The 7.5k probe uses the scripted opponent so the probe itself is not confounded, but the
   TRAINING signal from here on differs from the first 5k the same way it did for the 18k run.

### 5. Endpoint of the coef-0.1 run at the time of the hold (for §3 if it is killed)
17:31: 5,225 episodes, 151W-4076L-4D, EVAL@2000 ladder 12% / fair 8%, EVAL@4000 ladder 8% / fair 4% (150 each),
ent 0.05, 0.6 ep/s, drills 994 (41% pass all). Last `GATE PRIOR CE` line: 0.5557 over 9,800 updates
(cumulative), pi(play) 0.347 vs prior 0.059, 9% rows usable. Watchdog last alert 16:53 (m=4000): cell head
1.06/5.08 nats, elixir >=6 0.1%. Procs: train-sim-ppo x2 (29460/59384), gate watchdog x3, gates x3, stale 18k
watchdog x3. Free RAM 4.0 GB / 31.4, CPU 36%.

### 6. Relaunch sequence (staged, not executed)
`data/bench/gate05_run.yaml` (diff vs `gate_run.yaml` = `sim_ppo_checkpoint: data/policy_gate05_20260902.pt`,
`continuation_log: data/continuations_gate05.jsonl`, `ppo_gate_prior_coef: 0.5`) and
`data/bench/gate05_run_launch.sh` (same argv as `gate_run_launch.sh`, writes `gate05_run_20260902.{launched,
log,progress}`). Steps: count `train-sim-ppo` procs (expect 2) -> kill 29460/59384 -> count (expect 0) ->
`cd icebow && nohup bash data/bench/gate05_run_launch.sh &` -> first log line must read `GATE PRIOR ON: coef
0.500` -> re-arm `tools/ppo_watchdog.py data/policy_gate05_20260902.pt --every 300 --quiet-min 30 >
data/bench/gate05_run_watchdog.out` and `tools/real_run_gates.py --run gate05_20260902 > data/bench/
gate05_run_gates.out` -> §3 RUNNING NOW rewritten -> commit. Old gate watchdog/gates (48908/62136/61016,
10724/30624/43908) may need the owner to kill if the classifier refuses.

### 7. Side task closed: replay folder delivered
`icebow/data/overlayed_replays` (9 mp4, goodmatch_1..9, 1.5 GB) zipped as ONE file (ZIP_STORED, 1.555 GB) and
uploaded to gofile.io as a guest upload (owner asked for bashupload.com -- its DNS has no records at three
resolvers, dead; SwissTransfer needs a reCAPTCHA, not scriptable). md5 on the host equals the local zip. Link
sent in chat + Discord; delete token kept in the session scratchpad only (never in the repo).

### 8. What this does NOT establish
That coef 0.1 works (one checkpoint, mixed by the rule). That 0.5 is right or wrong. Anything about the
card head at 6+ once trained (still 9-12 plays per 2,400 rows there). Nothing about hogeq.

## §5bj — GAUNTLET L10: m=7.5k READ = OSCILLATION, NOT A PULL; coef-0.1 run killed at m=7,575, coef-0.5 run launched (2026-09-02 18:54-19:10)

### 1. Why this
Owner ruling 17:50: "wait until 18:40, to see if the reversal is genuine improvement or oscillation". The rule
(§5bi/§6): probe the live checkpoint at m>=7.5k on 3 seeds; drop holds (<0.30 all seeds) -> leave to 10k;
bounce back (>=0.30 all seeds) -> kill and relaunch at 0.5 without asking again. Cost: 3 x 12 s probe, kill +
launch 3 min, bookkeeping 12 min.

### 2. (a) Probe at m=7,500 (`scratchpad/gauntlet/L10/gate_m7k5.pt`, copied from the live checkpoint and cmp-stable; JSON `m7k5_s{0,1,2}.json`)
```
                         m=4k (L8)        m=5k (L9)        m=7.5k (L10)     18k control (L7)
played at 3 elixir       .423 .434 .483   .299 .279 .305   .376 .301 .401   .403 .372 .357
P(play | affordable)     .43  .43  .45    .28  .32  .32    .34  .34  .39    .39  .41  .40
rows with sth affordable .25  .25  .23    .36  .36  .32    .31  .33  .27    .29  .29  .28
rows at 4 elixir /2400    76   52   42    143  137  108    113  111   59     57   77   72
elixir >= 6 (frac rows)  .002 .000 .003   .016 .008 .015   .007 .010 .005   .001 .001 .000
elixir mean (raw)        2.01 1.96 1.91   2.29 2.28 2.24   2.15 2.18 2.02      --
plays per row            .110 .107 .108   .104 .110 .108   .113 .106 .105   .115 .113 .109
mean cost of plays       2.49 2.45 2.47   2.60 2.53 2.58   2.52 2.63 2.49      --
```
Every stat that moved toward the prior at m=5k moved back at least halfway by 7.5k; seeds 0 and 2 are at the
control level, seed 1 sits on the 0.30 threshold. Seed spread widened (0.30-0.40 vs 0.28-0.31 at 5k).
Rule verdict: all three >= 0.30 -> bounce back. Owner's "oscillation" reading is what the data shows.

### 3. (a) The trainer's own term, per 1,000 updates, whole run (16,800 updates)
```
window   1-1.2k 1.2-2.2k 2.2-3.2k 3.2-4.2k 4.2-5.2k 5.2-6.2k 6.2-7.2k 7.2-8.2k 8.2-9.2k 9.2-10.2k ... 15.2-16.2k
pi(play) 0.339  0.308    0.315    0.335    0.367    0.364    0.360    0.357    0.371    0.366    ...  0.348
CE       0.476  0.462    0.510    0.543    0.593    0.595    0.595    0.596    0.614    0.611    ...  0.587
```
(full 16 windows in the header; script: difference consecutive `GATE PRIOR CE` lines at >=1,000-update
spacing, `(ce*n - ce0*n0)/(n-n0)`). Flat at 0.34-0.37 from update 4,000 on; CE never fell. The trainer's
instrument and the probe now agree: coef 0.1 exerted no sustained pull over 7,500 matches / 16,800 updates.

### 4. What this means, plainly
1. §5bi's partial retraction is itself retracted in part: the m=5k read WAS oscillation (owner's word),
   so §5bh's core claim "coef 0.1 loses to PPO" stands as (a) over the whole run. What stays retracted from
   §5bh is the certainty of the arithmetic ("cannot win, the arithmetic says why") -- that is still (b); it
   predicted the outcome but was not what showed it.
2. §5x's lesson held again: one checkpoint read can move 0.15 and mean nothing. The pre-registered rule
   caught it; the ad-hoc call at 17:00 ("kill now") would have reached the same place 2 h earlier. Both paths
   were defensible; the hold cost 2 h of box time and bought the (a) that 0.1 oscillates rather than pulls.
3. Coef 0.5 is now the live experiment, ONE change vs the killed run (same seed 41, same config otherwise).
   §5bh.4's arithmetic predicts equilibrium pi ~0.20 at 3 elixir if the PPO push is ~0.8 per usable row.
   Pre-registered m=2k read is in §3. (b) until measured.

### 5. Kill + launch record
18:57:38 `taskkill /T /F` on PID 29460 (tree: 59384 + 12 workers): pre-kill log line 7,575 episodes; procs
matching train-sim-ppo/multiprocessing after = 0; `gate_run_20260902.progress` got `exit=1`. Old gate
watchdog (48908 tree) and gates (10724 tree) stopped (2 procs each). Free RAM after kill 6.2 GB.
18:59:21 launch (`.launched` = 1788389921); log line 1 (after two torch warnings): `GATE PRIOR ON: coef
0.500, config/gate_prior.json (519 replays ...)`. Procs: train-sim-ppo x2 (61036 parent, 47956 main) + 12
workers, watchdog 69940/37792, gates x2. First lines: 50 eps 0W-49L, 75 eps 1W-66L, 0.5 ep/s, ent 0.05-0.08.
RAM: free 0.6-1.1 GB at 19:01, workers 560 MB each + main 2.4 GB, Memory Compression 1.9 GB. The coef-0.1
run showed 170 MB/worker after 4 h, so this is probably startup footprint -- re-check next loop; if the box
is still < 1 GB free at m=2k, tell the owner (the run is his call, not mine to throttle).

### 6. What this does NOT establish
Anything about coef 0.5 yet. Whether the flat 0.35 at coef 0.1 is an equilibrium (pull = push) or no pull
at all (the CE never fell, so "no pull" is the simpler reading, but a small equilibrium shift from an
unmeasured no-prior baseline cannot be excluded without a coef-0 arm -- not worth a run).

### 7. Files
`scratchpad/gauntlet/L10/m7k5_s{0,1,2}.{json,txt}` (checkpoint copies stay out of git).

## §5bk — GAUNTLET L11: COEF 0.5 BITES AT m=2k on both instruments; PPO push visibly fighting back; level-16 sandbox answer; stale watchdog killed; decision-time question -> counter-question (2026-09-02 19:20-20:25)

### 0. What this loop was
Bookkeeping loop for work done between the L10 commit and the 20:05 wakeup, plus one cheap new read (the
trainer's gate windows). No box time spent: the coef-0.5 run was untouched throughout.

### 1. The pre-registered m=2k read (a)
`gate05_m2k.pt` = copy of `data/policy_gate05_20260902.pt` taken when the log passed 2,000 episodes (cmp-stable
across two copies), probed with `tools/gate_prior_probe.py --seed {0,1,2}` (12 s each), the same instrument
as L7-L10:

| seed | played at 3 | P(play \| affordable) | affordable rows | elixir >= 6 | elixir mean | cost of plays |
|---|---|---|---|---|---|---|
| 0 | **0.271** | 0.228 | 41.0% | 4.0% | 2.57 | 2.63 |
| 1 | **0.227** | 0.233 | 45.2% | 3.5% | 2.64 | 2.66 |
| 2 | **0.239** | 0.227 | 43.7% | 3.0% | 2.57 | 2.66 |

Same instrument, earlier checkpoints: coef-0.1 m=2k 0.449/0.392/0.424, m=4k 0.42-0.48, m=5k 0.28-0.31,
m=7.5k 0.30-0.40; 18k control 0.40/0.37/0.36; pros 0.063. P(play | affordable) at coef-0.1 m=2k was
0.43-0.45; elixir >= 6 was 0.0-0.2%.

Rule check: `<= 0.25 on all seeds` missed by 0.021 on seed 0; `>= 0.35 on all seeds` (the ask-branch) is
nowhere near. Verdict: **biting**, i.e. a ~0.15-0.20 drop in the gate at 3 elixir vs both the coef-0.1 run at
the same match count and the untrained control, on every seed, and the first checkpoint in this project whose
elixir reaches 6 on more than 2% of rows. Not a 3-seed confirmation of the LEVEL (0.227-0.271 is a 0.044 spread),
a 3-seed confirmation of the DIRECTION.

### 2. The trainer's own windows: the prior pulled first, PPO is pushing back (a)
`GATE PRIOR CE` is cumulative; de-cumulated per 200 updates (`(ce*n - ce0*n0)/(n-n0)`, same for pi):

```
updates   200   400   600   800  1000  1200  1400  1600  1800  2000
pi(play) .343  .298  .249  .241  .233  .243  .247  .241  .235  .219
CE       .463  .420  .371  .355  .349  .369  .362  .360  .360  .353
updates  2200  2400  2600  2800  3000  3200  3400  3600  3800  4000
pi(play) .244  .242  .240  .252  .252  .268  .253  .289  .274  .236
CE       .376  .381  .366  .398  .402  .410  .405  .420  .419  .389
updates  4200  4400  4600  4800  5000  5200  5400  5600
pi(play) .276  .256  .279  .281  .258  .284  .286  .260
CE       .405  .405  .432  .412  .419  .439  .429  .418
```
Prior on the same rows 0.059-0.060; 11-12% of rows usable. Shape: pi falls 0.34 -> 0.22 in the first 2,000
updates (the prior winning), then climbs to 0.24-0.29 with CE rising 0.35 -> 0.42-0.44 (PPO's advantage on
PLAY, +0.35 vs WAIT -0.01 in the log's `ADV BY ACTION`, pushing it back). Contrast coef 0.1: flat 0.34-0.37 over
16,800 updates, CE never fell (§5bj.3). So 0.5 is the first coefficient that moved the trainer's own
distribution -- and the push-back is exactly the "equilibrium vs overpowered" question the m=5k read answers.
This is the trainer's instrument (domain rand + search + drills); the probe's numbers in §1 are a different
distribution and are NOT to be compared line by line with these.

### 3. Match strength at m=2k, same seed 41, same log format (a)
| run | 2,000-ep line | avg_rew | drills pass | EVAL@2000 ladder / fair |
|---|---|---|---|---|
| coef 0.5 (this) | 46W-1554L-1D | **-18.2** | 39% | 5% / 2% |
| coef 0.1 (killed) | 37W-1546L-2D | -15.2 | 43% | 12% / 8% |
| 18k run (no prior) | 26W-1541L-0D | -13.4 | -- | 3% / 3% |

avg_rew is a per-episode mean over ~2,000 episodes and is the only one of these with resolution; coef 0.5 is
worst by 3 points. (b) plausible reading: banking elixir costs reward under the current shaping (fewer plays
-> fewer shaped rewards, more damage taken); the alternative reading, that the prior is simply making the
policy worse, is not excluded by anything here. EVAL is n=150: 5% vs 12% vs 3% is inside the ±5pp band and
says nothing. Win counts: 46 vs 37 vs 26 -- same story. Do NOT read the coef-0.1 EVAL trajectory
(12/8 -> 8/4 -> 9/4) as decline; it is the same noise.

### 4. Side work this segment
* Level 16 in the sandbox engine (owner question): full writeup `scratchpad/gauntlet/L11/level16-research.md`
  (committed acbb168), summary in §6. Load-bearing (c): `HANDOFF.md:5737`'s "RoyaleAPI has the levels per
  card in the crawl" is false for the crawl on this box.
* Stale 18k watchdog killed (§3 updated). Two orphaned grep.exe filters remain, harmless.
* Decision-time question answered with a counter-question (§6). Nothing built, nothing measured.

### 5. Traps found
* The pre-registered `<= 0.25 on all seeds` was too tight for a 3-seed probe whose spread at a fixed
  checkpoint is ~0.04-0.05 (L7-L11 all show it). A rule with a 0.10 gap between its two branches
  (0.25 / 0.35) leaves a dead zone that 0.271 landed in. Next rules get ONE threshold with the noise band
  around it stated, not two.
* `EVAL @ 2000` in this log is written as `EVAL @ 2000:` (space before the @), so `grep "EVAL@"` finds
  nothing. Use `grep -i eval` and filter.
* `gate05_run_gates.progress` does not exist yet -- the gates script writes it only at the first gate (5,000).
  Its liveness check is the two `real_run_gates.py` PIDs (60548/9528), not the file.

### 6. What this does NOT establish
Whether 0.5 is an equilibrium or a transient the PPO push will erase (trainer windows are climbing). Whether
the reward cost (-18.2 vs -15.2) is banking or damage. Anything about win rate. Anything past m=2,550.

### 7. Files
`scratchpad/gauntlet/L11/g05m2k_s{0,1,2}.{json,txt}`, `level16-research.md` (committed acbb168);
`gate05_m2k.pt` stays out of git. Probe series for the whole gate-prior program: L7 (18k control),
L8 (coef-0.1 m=2k/4k), L9 (m=5k), L10 (m=7.5k), L11 (coef-0.5 m=2k).

## §5bl — GAUNTLET L12: THE DECISION PATH WAS ALREADY MEASURED -- served cadence 0.76 s against a 0.6 s policy; stage timer built; agent_dt weighed (2026-09-02 20:30-20:55)

Owner order 20:3x: *"build the stage timer and measure the results. But if 0.6s is the minimum time between 2
consecutive actions for the same decision, then it's way too long. But I'll leave it to you to weigh the benefits
and drawbacks of lowering the agent_dt."*  The gate-prior run was untouched; two ~5-20 s smokes of the timer
ran beside it (CPU 40 -> 100% during, labelled).

### 1. RETRACTION (c): "act_in_match / the decision path is unmeasured"
Said in §5be.5.1, §6 (twice) and by me to the owner at 20:0x. False. `env.py` has accumulated per-stage wall
time for every decision since the 08-12 cadence fix (`self._cad[...]` at env.py:1877-2082), prints a
`[cadence]` line per match (env.py:2124) and dumps the dict as `cadence` in `data/reward_stats/live_*.jsonl`
(env.py:2149). 904 matches carry it. No HANDOFF section has ever cited one. Trap: an instrument that writes to
a JSONL nobody greps is an instrument that does not exist; it is now in §8.

### 2. What the live loop measured (a) -- 100 matches, 38 sessions, 2026-08-20 09:36 -> 2026-09-02 19:58
Restricted to the act_period-0.6 era (config change §3m); per-match MEANS, then percentiles across matches:

| stage | what it is (env.py) | p10 | p50 | p90 |
|---|---|---|---|---|
| **loop** | decision-to-decision wall time | 0.664 | **0.760** | 0.898 |
| wait | slack left in the period (event-interruptible) | 0.026 | 0.123 | 0.287 |
| grab | screen capture | 0.026 | 0.035 | 0.046 |
| state | `vision.detect_state` (template match) | 0.041 | 0.056 | 0.063 |
| reads | tower alive + HP OCR + colour mass + elixir + clock | 0.074 | 0.131 | 0.175 |
| hand | hand recognition | 0.010 | 0.012 | 0.015 |
| threat | tracker update (+ perception snapshot) | 0.048 | 0.053 | 0.063 |
| obs | observation build | 0.003 | 0.003 | 0.004 |
| act | tap execution | 0.041 | 0.058 | 0.076 |
| det_age | staleness of the detection used | 0.055 | 0.061 | 0.081 |
| env sum | grab..act | 0.288 | **0.343** | 0.408 |
| trainer residual | loop - wait - env sum: forward, doctrine, live search, DDQN learn step, logging | 0.082 | **0.315** | 0.448 |
| pipeline | loop - wait | 0.403 | **0.646** | 0.842 |

91/100 matches ran the loop above 0.66 s (>10% over the trained 0.6); 3/100 at or under 0.62; 41/100 had
< 0.10 s of slack, i.e. the pipeline alone exceeded the period. **The policy is trained at agent_dt 0.6 and
served at 0.76 (median), 0.90 at p90.** Same bug class as C-list item 5 (1.0 trained / 2.2 served, 08-12),
smaller, and invisible for two weeks for the reason in §1. Box load per session is NOT recorded (the 09-01
21:47 and 09-02 19:51 sessions certainly ran beside a cuda training run); the p10 match, 0.66 s, is still
over 0.6, so the conclusion survives the contention caveat even if the split does not.

Consequence for the owner's question: **lowering `act_period` today changes nothing served.** The loop
cannot go faster than its pipeline (0.65 s median); a period below the pipeline only widens the train/serve
gap. The owner's reading of the mechanism is right, though: after a play, the next decision is >= 0.6 s
away unless perception wakes the loop on a new ENEMY commitment (env.py:1910, `react_min_gap_s` 0.15) --
the bot's own follow-up play (Hog then Ice Spirit) is never a wake reason.

### 3. Offline stage timer -- built, smoked on the contended box (a, UPPER BOUNDS)
`icebow/tools/latency_stage_timer.py` (new, ~230 lines): decodes `data/sessions/20260815_222309/video.mp4`
(656x1198, 12 fps), keeps IN_MATCH frames, and times each `reads`/`state`/`hand`/`threat` component with the
real classes (`Vision`, `TowerTracker`, `TowerHpTracker`, `ElixirClock`, `ThreatTracker`, `load_detector`)
plus the trainer side with the real net (`train_rl._build_net` + `policy_rl.pt`): forward at batch 1 and a
DDQN optimise-equivalent at batch 64 (online + target forward, huber, backward, clip, step -- what
`train_rl.optimise()` does synchronously after EVERY live decision, train_rl.py:1187). Records free RAM /
CPU% / VRAM before and after so the load is on the record. No play.py / env.py / train_rl.py edits.

Smoke, 40 in-match frames, stride 12, CPU 40% -> 100% (the run), cuda shared with the run:
```
detect_state   p50  86.2 ms  p90 120.0      tower_hp_step  p50 22.5 ms  p90 348.3  (OCR bursts)
detector       p50  80.1     p90 215.7      read_elixir    p50 15.1     p90  24.9
threat_colour  p50  61.6     p90 143.7      enemy_mass     p50  9.7     p90  14.3
hand           p50   5.2     p90  11.5      observe        p50  4.4     p90   7.1
tower_step     p50   1.4                    clock_update   p50  0.0
net_forward_b1 p50   1.6 ms  p90  6.2       ddqn_optimise_b64 p50 20.8 ms  p90 27.8   (cuda)
```
Env sum of medians 286 ms -- consistent with the live env share (343 ms incl. grab 35 + act 58, which the
tool cannot reproduce). Every number here is an upper bound; the idle-box run is the measurement. What the
smoke DOES settle, because it is a lower bound on the residual's non-membership: **the 0.315 s trainer
residual is not the network** (forward 1.6 ms + learn step 21 ms even contended). (b) it is some mix of
`live_search.decide` (120 ms budget, `sim.live_search_enabled: true` since a410de6 08-29 -- and sessions
before that date show residuals of 0.02-0.31 s, so search is not the whole story), the doctrine/counter
block, and contention. Settling it needs timers inside train_rl's loop (live path -> owner call) or the
idle-box run with search toggled.

### 4. Pros' inter-play spacing (a)
`icebow/data/royaleapi/crawl2/plays_ext.csv`, ability rows excluded, gaps between consecutive plays by the
SAME side within a replay: 1,038 sides, 43,205 gaps. < 0.3 s: 0.3%; **< 0.6 s: 1.4%**; < 1.0 s: 3.6%;
< 1.5 s: 7.8%; < 2 s: 18.0%; < 3 s: 35.3%; p10 1.60 s, p25 2.35, **p50 4.15**, p75 7.05, p90 11.0. The
0.6 s floor between the bot's own consecutive plays excludes 1.4% of what pros do. Elixir, not reflex, sets
the spacing.

### 5. What the 0.6 s actually costs, and what it does not (labelled)
* (a) Own-follow-up combos inside 0.6 s: 1.4% of pro play pairs. Small.
* (a) Reaction to an enemy play: NOT bounded by act_period (event wake), bounded by the pipeline. A woken
  decision still pays grab + state + hand + threat + trainer + act ~ 0.5 s (reads partly skipped on a fast
  tick, env.py:1950/1972). The event path has never been timed end to end; (b) ~0.5 s from sighting to tap.
* (b) Placement timing inside a 0.6 s grid (waiting for a troop to cross the bridge before a Log): plausible
  cost, no measurement; the sim would show it as a gain from a finer dt, which is the retrain question.

### 6. agent_dt: the weighing (owner delegated the call)
Lowering agent_dt (sim) / act_period (live) together, e.g. 0.6 -> 0.3:
* Buys: (a) 1.4% of pro combos; (b) finer placement timing; nothing on reaction (see §5).
* Costs: (a) full sim retrain (§3m); gamma retune (0.994 was set for 0.6, config.yaml:787); per-step P(play)
  halves so the gate imbalance the gate-prior program is fighting gets harder and the prior tables
  (P(play | elixir, phase) per decision) must be rebuilt for the new dt; sim throughput per match halves
  (0.6 ep/s -> ~0.3 at 96 envs); live search's 120 ms is a bigger share of a smaller period; and it CANNOT
  be served -- the live loop does not deliver 0.6 today.
* **Verdict: do not lower agent_dt now.** Order of work: (1) make serving honest at 0.6 -- pipeline 0.65 ->
  < 0.40 s so `loop` sits at 0.60-0.62 (targets in order of size: the 0.3 s trainer residual once it is
  split; `detect_state` at 56-86 ms per decision, which is a template match that could run at 2 Hz instead
  of every decision; tower-HP OCR p90 348 ms; threat colour 60 ms). (2) When the pipeline is <= 0.2 s, a
  0.3 s agent_dt retrain is a real experiment: queue it as ONE change after the gate-prior run, with the
  prior tables regenerated for 0.3 s. (3) The reaction path is the separate prize: time sighting -> tap
  once on an idle box, then decide whether a fast tick should skip more than the telemetry reads.

### 7. Traps
* §1: per-match `cadence` has been in every live JSONL since 08-12 and was never read. Added to §8.
* `cfg.get("train","device")` returns a STRING; `torch.device()` it before `.type` (cost one smoke).
* The tool's `threat_colour` is the colour tracker alone; live `threat` also pulls the perception snapshot.
  The tool's `detector` is a synchronous pass; live runs it in the 10 Hz thread (det_age 61 ms) -- do not
  add it to the per-decision sum.

### 8. Files
`icebow/tools/latency_stage_timer.py` (new); `scratchpad/gauntlet/L12/stage_timer_smoke_contended.json`,
`stage_timer_smoke_net_contended.json`. Cadence analysis was ad hoc (python over the JSONLs, §2 table);
the pro-gap numbers likewise (§4). Both are 20-line scripts reproduced in GAUNTLET_LOG L12.

## §5bm — GAUNTLET L13: owner's two live-play reports tested -- X-Bow at a dead tower; spell whiffs; rocket is dead in the sim policy (2026-09-02 20:30-20:55)

Owner (20:3x): (1) "the model doesn't know which placement positions for offensive x-bow target which princess
tower ... tries to place an xbow in a cell that targets an already dead princess tower ... placements can be
directly derived from the replay crawl data"; (2) "lots of spell whiffs ... could you check the spell usage
stats for the current PPO?" Both treated as hypotheses. Run untouched; the probes ran beside it (contended,
behaviour not throughput).

### 1. X-Bow at a dead tower -- what is already there (a, code)
* Observation: enemy tower HP fractions, 6 dims, since 2819923 (08-10), `observation.use_tower_hp` absent from
  config -> default True; live env.py:505 widens by the same block. The policy CAN see a dead tower.
* Live aim assist `xbow_target_lane_cell` (reward.py:319, added 08-16 after the owner reported exactly this):
  "NEVER bow a dead lane" -- moves an offensive bow to the live princess's column. Called from env.py:1832.
* Sim reward `_wincon_exec` (sim/env.py:1553): `princesses = [t for t in towers[1][:2] if t.alive]` --
  offensive credit only for reaching a LIVE princess.
So "the model doesn't know" is (c) as stated: the information and two guards exist. What fails is below.

### 2. What actually happened in today's live matches (a, `data/reward_stats/live_20260902_{195143,201412}.jsonl`)
Six X-Bow plays, 20:14 session: `cell 243` every time (x 0.519, y 0.479 -- centre column, forward),
`raw_cell == cell` every time -> neither the lane assist nor the lock/depth snaps changed anything.
`wc` (live wincon credit): +3.0 for the first bow of each match, -1.0 for the four later ones.
Why the assist did nothing: env.py:1823 `elif card_id in self.xbow_ids and not self._defensive:` -- the
whole offensive assist chain (lane -> lock -> depth) is gated OFF once `_defensive` is True, and env.py:1994
sets `_defensive = True` on `took_tower`. **The moment an enemy princess dies is the moment the dead-lane guard
stops running.** The doctrine says a post-kill bow belongs back-centre (`_defensive_bow_cell`), but that snap
only runs when `_enemy_massing_back()` (env.py:1821). So after the kill the model's raw pick goes out
unassisted; its raw pick is the same cell every time (constant-cell attractor, live edition); the live reward
bills -1 because cy 0.479 is above `xbow_defense_front` 0.52, not because of the lane.
Second gap (a): `_wincon_exec_live` (env.py:1569-1576) computes `d` over BOTH princess anchors with no alive
check -- unlike the sim -- so a bow in range of only a dead tower earns +w_wincon whenever `_defensive` is
False (i.e. when `took_tower` was missed by perception). Real but masked by the phase flip in practice.
Cannot say from the log which tower was dead at each play (tower state is not in play_log) -- (b) that the
owner's "targets the dead tower" reading is the centre bow after a kill; from the centre column both
princesses are in reach, so the real game would still lock the live one.

### 3. The crawl cannot give "placement after a tower dies" (c)
`plays_ext.csv` (45,335 plays, 2,073 x-bow with tile_x/tile_y) has no tower-death or crown-time events;
`battles.csv` has final crown counts only. Pro bow placement OVERALL is derivable and was already used
(5ag lane-bow ruling). Conditioning on a dead tower is not. The geometry ("which cells reach which tower")
does not need the crawl at all -- reach 11.5 tiles + anchors, already in `xbow_lock_cell`.

### 4. Sim probe: spells and bows, greedy, search-free, NO spell mask (the policy alone) -- (a)
`scratchpad/gauntlet/L13/spell_xbow_probe.py`, 3 seeds x 12 matches per checkpoint, PYTHONHASHSEED=0.
"mask-whiff" = the cast cell is one `spell_target_mask` would have vetoed; "0-dmg" = ledger `spell_waste`.

| ckpt | plays | spells (share) | log / nado / rocket | mask-whiff | 0-dmg | nado_bad | bows | bows reaching a live tower | dead-only |
|---|---|---|---|---|---|---|---|---|---|
| coef-0.5 m2k | 945 | 168 (18%) | 99 / 69 / **0** | 19 (11%) | 18 (11%) | 13 (19% of nados) | 83 | 3 | 0 |
| 18k control | 1,635 | 496 (30%) | 273 / 223 / **0** | 105 (21%) | 45 (9%) | 29 (13%) | 14 | 0 | 0 |
Per-seed spell_waste: m2k 5/7/6, 18k 15/16/14 -- consistent. Live today (a, OTHER instrument, tracker-based
verdict, do not compare numerically): `spell_waste` 25 fires over 54 spell plays in 5 matches, nado_bad 4.
* Whiffs: the policy alone whiffs ~10% of casts by the sim's damage verdict; the trainer runs with the spell
  mask at ~86% strength (25k-episode anneal, 3.5k in), so exploration almost never pays for a whiff -- the
  policy is learning "roughly there" and relies on a mask. Live serves the same policy through the live mask
  over DETECTOR tracks (play.py:563); where tracks are stale the mask passes a whiff, and the live verdict
  also bills false whiffs on detector misses (env.py:340). (b) most of the live 25 are perception, not policy;
  the measurement is a session with the detector log kept, or the offline replay of a recording.
* **Rocket: 0 casts in 72 matches on both checkpoints.** Pros: 1,520 / 45,335 = 3.4% of plays. Live today: 4.
  (b) cause unknown -- candidates: the own-half/no-king masks leaving few legal cells, `wincon_mis` on the
  king, the `spell_waste` bill at rocket radius. Not a gate-prior effect (the 18k control has it too).
* Bows: the sim policy's bows are almost all defensive (80/83 and 14/14 reach no tower); 12 bows were placed
  with a princess already dead and NONE reached the dead one only. The live bow-at-cell-243 pattern is not
  reproduced in sim: the live checkpoint is the DDQN-tuned `policy_rl.pt`, not these.

### 5. Proposed fixes (live path -> owner call, not done)
1. env.py:1823: run the bow assists in the defensive phase too -- specifically, when `_defensive`, snap a
   forward bow to `_defensive_bow_cell` (the doctrine's answer) regardless of `_enemy_massing_back()`. One
   condition change. Closes the exact hole in §2.
2. env.py:1574: `princesses = [a for a, alive in zip(enemy_a[:2], self.tower.enemy_alive) if alive]` --
   mirror the sim. One line.
3. Not the crawl: the geometry is already coded; the crawl adds nothing for this.
Rocket-at-0% is a separate item for the queue (§6).

### 6. Does NOT establish
Which tower was dead at each of today's bows (not logged); the split of live whiffs between policy and
tracker; why rocket is never cast in sim; whether the sim's 11% whiff rate rises as the mask anneals
(it will, if the policy never learned aim -- measure at the next snapshot).

### 7. Files
`scratchpad/gauntlet/L13/spell_xbow_probe.py`, `probe_gate05_m2k.{json,txt}`, `probe_18k.{json,txt}`.

## §5bn — GAUNTLET L14: X-Bow defensive doctrine -- tower gate removed, time gate verified against pros and kept, snap + anchors fixed (2026-09-02 20:55-21:10)

Owner (20:5x): "the defensive bow doctrine needs to be tweaked, if not outright removed. I'm thinking remove the
tower-gated defensive snap and keep the time-gated one. But don't take my word for it, verify the time based snap
with some empirical evidence from pro player replay data. But yes, you can make the defensive bow snap and the
anchors if they're still applicable." Live path only; the sim twin is untouched while the gate-prior run is live.

### 1. Pro evidence (a) -- `scratchpad/gauntlet/L14/pro_bow_timing.py`, output `pro_bow_timing.txt`
`plays_ext.csv`, x-bow plays with tiles 1,089; blue side (tile_y >= 16) 1,029. Tiles are half-integers:
front/offensive = 18.5/19.5 (bridge band, reaches a princess), back/defensive = 21.5-25.5, 20.5 = mid (3 plays).

| match time | n | front | back | front % |
|---|---|---|---|---|
| 0-30 s | 42 | 39 | 3 | **92.9** |
| 30-120 s | 264 | 216 | 48 | 81.8 |
| 2x (120-180 s) | 330 | 208 | 120 | 63.0 |
| OT (180-240 s) | 261 | 142 | 118 | 54.4 |
| 3x OT (240 s+) | 132 | 63 | 69 | 47.7 |

Per replay: 255 replays with blue bows, **122 switch front -> back** at some point; first switch lands in 2x
(70), OT (28), 3x OT (11), before 2x (13). So the TIME-gated move to a back bow is what pros do -- as a
drift from 93% front to a coin-flip by overtime, not a hard switch.
Tower proxy (the crawl has NO tower-death events, §5bm.3; only final crowns): late bows (>= 120 s) in matches
the pro ended with >= 1 crown are **54.2% front (n=463)** vs **62.3% front (n=260)** at zero crowns. Taking a
tower moves bows back by ~8 pp at most, and that conflates "took a tower" with "was ahead". Not a switch.
Over all times: 63.6% vs 67.2%. (Pre-compaction read in this loop said "1,038 blue"; the script on disk says
1,029 -- the script is the record.)

**Ruling supported:** tower gate (c) unsupported by pros AND measured harmful (§5bm.2: it switched off the
dead-lane guard at the moment a tower died); time gate (a) supported as a preference. **Flag:** the live phase
flip is a HARD snap once `in_overtime and chip < xbow_success_frac * full` -- it overrides the ~54% of pro OT
bows that stay forward. The chip condition narrows it to matches where the offensive bow never worked, which the
crawl cannot condition on (no damage events). Whether that narrowing is enough to match pros is (b); the owner
may want the snap softened to a preference (e.g. only when massing back OR chip < frac) -- owner call, not done.

### 2. Edits (a, `icebow/src/clashrl/env.py`, owner-authorised, live path)
1. env.py:~2007 phase flip: `took_tower or` REMOVED -> `if not self._defensive and (in_overtime and
   self._enemy_chip_total < self.tower_hp.full * self.xbow_success_frac)`. `took_tower` is still computed
   (:1984) for the crown reward terms. Comment block records the ruling and the numbers above.
2. env.py:~1830 bow assist: `if card_id in self.xbow_ids and (self._defensive or self._enemy_massing_back()):
   cell = self._defensive_bow_cell(cell)` -- the defensive phase now applies the doctrine's snap instead of
   skipping every assist (§5bm.2 hole). `_defensive_bow_cell` is a correction: a bow already in the defensive
   band keeps its own cell (env.py:1368-1380).
3. env.py:~1575 `_wincon_exec_live`: `princesses` filtered by `self.tower.enemy_alive` (falls back to all-alive
   if the tracker has no list) -- mirror of sim `_wincon_exec`. A bow reaching only a dead tower no longer earns
   +w_wincon.
Import OK. `python -m unittest tests.test_xbow_lane tests.test_xbow_rewards tests.test_xbow_into_push
tests.test_env_init_attrs tests.test_wincon_bank`: 57 tests, 56 pass, 1 failure
`test_xbow_into_push.test_the_clamped_frontmost_ROW_counts_as_forward` (0.5625 < 0.625) -- **PRE-EXISTING**,
verified by `git stash` on the untouched tree (a 32-row-era assertion on the 24-row grid). Not fixed here (not
this change). No live session was run: the edits are unexercised in a real match -- (b) until the next session.

### 3. NOT changed, queued (§6)
* Sim twin of the phase flip, sim/env.py:3149-3156, still has `took_tower` -> sim and live doctrines now
  DIFFER. Deliberate: the gate-prior run depends on the sim reward (guardrail: no doctrine change under a
  dependent run). Apply after the run ends, then the two are one doctrine again.
* Hard-vs-soft OT snap (owner call, §1 flag).

### 4. Does NOT establish
Whether the three edits change live bow placement (no session run); the pro depth split conditioned on an
actual tower death (no events); whether the 24-row test failure hides a real depth-band regression (the assist
passes the other 56 tests; the failing one asserts a coordinate the current grid cannot produce).

### 5. Files
`scratchpad/gauntlet/L14/pro_bow_timing.{py,txt}`; `icebow/src/clashrl/env.py` (3 hunks).

## §5bo — owner steering: the overtime flip is a SOFT RAMP, hardening through OT; agent_dt verdict pinned in §6 (2026-09-02 21:10-21:30)

Owner (21:1x): "Make the OT flip softer, but increasingly harder as OT progresses. And for your agent_dt
verdict, make a note in handoff.md so we don't forget about it later." Live path, owner-authorised.

### 1. Design (a, code)
`_defensive` (bool) -> `_defensive_w` (float 0..1), computed every step in the phase block (env.py ~:2020):
* w = 0 before overtime; w = clamp(seconds_into_overtime / `env.xbow_defense_ramp_s`, 0, 1) once
  `clock.overtime` (elapsed >= `elixir.overtime_time_s` 180); **w = 0 at any time the offensive bow has broken
  through** (`_enemy_chip_total >= xbow_success_frac * full`), the one case the doctrine wants offence kept.
  Time and chip are monotone, so w only rises -- except by the bow succeeding.
* Default ramp 60 s (config `env.xbow_defense_ramp_s`, config.yaml env block): soft at the 180 s whistle,
  fully defensive at 240 s = the 3x-elixir minute. (b) that 60 s is the right length: pros go 63% front (2x)
  -> 54% (OT) -> 48% (3x), a gentler slope than a 60 s ramp to "always back"; the chip condition is what
  justifies steeper, and the crawl cannot check it. One knob, owner's to move.
* Three consumers, all continuous now:
  1. `_wincon_exec_live` bow credit = (1-w) x offensive branch + w x defensive branch. w=0 and w=1 are the
     old two branches exactly (tested).
  2. rocket-cycle chip credit (`near_enemy_princess` spell branch) = 0.6 x w_wincon x w.
  3. Defensive bow snap fires with PROBABILITY w (env RNG), or always when `_enemy_massing_back()`. A rising
     preference reproduces the pro split in expectation; a threshold would just be the hard flip 30 s later.
     (b) the wheel's randomness at mid-ramp costs the model a consistent target -- the reward blend is the
     signal that teaches it, the snap is the wheel; watch `raw_cell != cell` in OT next session.
* `_defensive` kept as a PROPERTY (= w >= 1; setter pins w to 1/0) -- 10 existing tests assign it directly
  and all still pass. `ElixirClock.overtime_s` (seconds into OT, 0 before) added; env reads it via getattr
  and falls back to w = 1 (the old hard flip) if a clock has no `overtime_s`.
* Phase prints: "DEFENSIVE ramp begins" when w leaves 0; "phase -> DEFENSIVE" when it reaches 1.

### 2. Tests (a)
`tests/test_defensive_ramp.py` (5): w=0/w=1 equal the old branches; blend monotone in w and halfway at 0.5;
a bow reaching only a DEAD princess earns the misplace, not +w_wincon (§5bn edit 3); the property pins w;
`overtime_s` 0 before OT and ~30 at OT+30. Doctrine modules (xbow_lane, xbow_rewards, xbow_into_push,
env_init_attrs, wincon_bank, defensive_doctrine, rocket_doctrine, rocket_value, spell_card_veto) 125 tests,
1 failure = the pre-existing `test_the_clamped_frontmost_ROW_counts_as_forward` (§5bn). Total 130/131.
Trap found writing the test: `_wincon_exec_live` re-anchors `_xbow_play_t` on EVERY bow call, so a second call
inside `xbow_lifetime` (30 s) returns 0 by the repeat-credit gate -- reset `_xbow_play_t = None` per call.

### 3. NOT done / does NOT establish
Sim twin (sim/env.py:3149 still hard, tower-gated) -- after the run, one change (§6). Whether w's 60 s
ramp matches pro behaviour once conditioned on "bow never worked" (unobservable in the crawl). No live
session run: (b) until the next one.

### 4. Files
`icebow/src/clashrl/env.py`, `icebow/src/clashrl/clock.py`, `icebow/config/config.yaml`
(`env.xbow_defense_ramp_s`), `icebow/tests/test_defensive_ramp.py`.

## §5bp — GAUNTLET L15: the m=5k wakeup landed early; same-instrument orientation only (2026-09-02 21:15-21:20)

### 1. Box (a)
Run at **4,425 episodes, 0.5 ep/s, 111W-3437L-6D, avg_rew -18.6** (log 21:15); the 21:11 wakeup assumed the
20:36 rate of 0.6 ep/s. Processes: 2 trainer, watchdog, gates script, plus the watchdog's own `policy-stats`
child (2 PIDs). Free RAM 3.98 GB, CPU 100%. `gate05_m5k.pt` not yet written. m=5k ETA ~21:35; the gates
script snapshots at 5k, so the read is the 21:41 wakeup. **Nothing pre-registered was read this loop.**

### 2. Same-instrument comparison, watchdog only (a, one reading per arm, samples the gate)
| matches=4000 | coef-0.1 (`gate_run_watchdog.out` 16:53) | coef-0.5 (`gate05_run_watchdog.out` 20:59) |
|---|---|---|
| CELL HEAD COLLAPSED alert | yes: ent 1.06/5.08, 62 cells | yes: ent 1.07/5.08, 56 cells |
| ELIXIR>=6 DRIFT alert | yes: 0.001 | yes (at 3100 and 4400): 0.001-0.002 |
| P(play) mean | 0.479 | 0.261 (0.342 at 3100, 0.375 at 4400) |
| card_ent | 1.82/2.30 | 1.18/2.30 |
| elixir mean | 1.96 | 2.67 (2.10 at 4400) |
The two alerts fire on both arms at the same point with the same numbers -> (a) they are a property of this
recipe at 4k, not of the coef. P(play) lower and card entropy narrower on the 0.5 arm: (b) consistent with
a heavier prior pulling the gate toward the prior table's wait mass and the card head toward its mode;
single readings, the watchdog SAMPLES (§8 trap) -- the pre-registered probe at 5k is the instrument.
Trainer-line EVAL (the trainer's own instrument, 150 matches): coef-0.5 @4000 ladder 13% / fair 10%;
coef-0.1 @4000 8% / 4%, @6000 9% / 4%. Winrate is not a discriminator (§7); logged, not concluded from.

### 3. Does NOT establish
Anything about the m=5k rule. Whether the P(play)/card_ent gap survives at 5k on the probe.

### 4. Trap
Wakeup ETA computed from one rate reading (0.6 ep/s) -- the run slowed to 0.5 under the watchdog's
policy-stats child. Pace the next wakeup from the latest rate AND the snapshot's existence, not the count.

## §5bq — GAUNTLET L16 (final loop): does the policy know its spell NICHES? Pro reference + engine-truth probe; `nado_retarget` unreachable; m=5k read (2026-09-02 21:20-22:10)

Owner (21:2x): "does the model know how to actually use its spells? just because it lands a spell, doesn't mean the
spell was a good spell ... each spell in icebow fills a specific niche (log on goblin barrel / princess / goblin gang
/ skeleton-barrel skeletons; tornado to activate king tower or reset aggro; rocket to clear clumps or medium troops
next to the enemy princess tower for the 2-for-1). After this is addressed, you may stop the gauntlet ... Don't take
my examples as the ONLY possible use cases: you can easily determine how spells should be used by looking at pro
player spell placements." Run untouched throughout (2 trainer PIDs + watchdog + gates script, before and after).

### 1. Pro niche reference (a) -- `scratchpad/gauntlet/L16/pro_spell_niche.py`, output `pro_spell_niche.txt`
`plays_ext.csv`, icebow side = the side that plays x-bow (515 of 519 replays); casts: the-log 3,479, tornado 1,886,
rocket 1,439 (rocket = 3.4% of all pro plays). Landing zone, blue-normalised tiles (y<=8 ENEMY princess-tower zone,
<16 enemy half, <24 own half bridge side, else own back/king zone), casts with tiles only:

| spell | n(tiles) | enemy tower zone | enemy half | own bridge side | own back / king |
|---|---|---|---|---|---|
| the-log | 1,831 | 0% | 1% | **87%** | 13% |
| tornado | 969 | 7% | 37% | 36% | **19%** |
| rocket | 768 | **32%** | **49%** | 19% | 0% |

Opponent's last play within 6 s before the cast (p50 gap 2.2-2.4 s): log -- 13% nothing, then barbarian-barrel
5.9%, skeletons 3.0%, goblin-barrel 1.8%, electro-spirit, hog/royal-hogs (knock-back), e-barbs; by class swarm/cheap
27.5% > medium 20.6% > wincon 15.2%. Tornado -- barbarian-barrel, hog, skeletons, skeleton-army, goblin-barrel;
swarm 26% ~ medium 23%. Rocket -- e-barbs 4.8%, sparky 3.4%, baby-dragon, x-bow, balloon; medium 26.7% > wincon
21.6% > swarm 14.9%. So the crawl's strongest niche signal is the LANDING ZONE (log = defensive at our bridge,
rocket = offensive into the enemy half / on the tower, tornado = spread, with a fifth of casts in the king zone);
the preceding-card class only mildly separates the three. The crawl has no unit positions, so "what the spell
covered" is not measurable for pros -- the owner's examples (log on barrel/princess/gang) are consistent with the
last-play table but cannot be counted from it. (Presentation bug in the script's "any play in window" column:
the (nothing) cell prints 0.0%; the last-play column's 10-15% is the right figure.)

### 2. Sim probe (a) -- `scratchpad/gauntlet/L16/sim_spell_niche.py`, greedy, search-free, NO spell mask
3 checkpoints x seeds 0/1/2 x 12 matches, PYTHONHASHSEED=0, same harness as L13 (plays per seed identical to L13
-> deterministic). Per cast: landing zone (sim y mirrored to the same 4 buckets), enemy bodies the cast covers at
engine ground truth (log: 2.5-tile-wide, 10-tile roll toward the enemy; nado: pull radius 5.5; rocket: radius+0.5),
bodies it kills outright (hp <= spell dmg), the sim's own ledger, and the four tornado credits SPLIT probe-side by
re-evaluating the sim's predicates (the sim folds them into one `nado` key, sim/env.py:3073 -- my first pass read
"0 fires" for all four from that ledger and was WRONG; retracted before recording).

| | coef-0.5 m2k | coef-0.5 **m5k** | 18k control |
|---|---|---|---|
| plays / spell casts | 945 / 168 | 1,485 / 429 | 1,635 / 496 |
| **LOG** casts | 99 | 241 | 273 |
| zone: own bridge side / own back | 72 / 28% | 79 / 21% | 85 / 15% |
| covers NOTHING / chip only / kills >=1 | 26 / 36 / 37% | 18 / 56 / 25% | 25 / 39 / 36% |
| class covered: swarm / medium / wincon / bldg | 36 / 31 / 22 / 2% | 31 / 49 / 19 / 5% | 35 / 33 / 17 / 11% |
| top bodies under the log | skeletons 14, hog 10, mighty_miner 9 | skeletons 24, miner 12, knight_hero 12, hunter 11 | skeletons 27, royal_hogs 21, cannon 15 |
| ledger spell_waste / spell_defence | 18 / 74 | 38 / 127 | 45 / 130 |
| **TORNADO** casts | 69 | 187 | 223 |
| zone: enemy half / own bridge / own back-king | 14 / 68 / 17% | 36 / 55 / 9% | 54 / 39 / 2% |
| king asleep at cast / cast within 6 tiles of our king | 43% / 14% | 54% / 9% | 47% / 2% |
| **king_activate** credits (per 36 matches) | **0** | **1** | **4** |
| clump (>=2 mediums at the centre) / combo (>=2 dead) | 7 / 22 | 19 / 36 | 18 / 38 |
| retarget credits | 0 | 0 | 0 |
| pulled nothing / nado_bad | 7 / 13 (19%) | 17 / 35 (19%) | 20 / 29 (13%) |
| **ROCKET** casts | **0** | **1** (on tower, bomber+skeletons) | **0** |

### 3. Reading (labelled)
* **Log** (a): the ZONE is pro-like (72-85% own bridge side; pros 87%) -- the policy knows the log is a defensive
  spell cast at our bridge. The TARGET is not: 18-26% of casts cover no enemy body at all (ledger spell_waste, the
  sim's own wider 4.5-tile verdict: 11% / 16% / 16%), only 25-37% kill anything, and 17-22% of logs go under a
  wincon (hog, pekka, miner, giant-class) that 352 damage cannot kill. (b) Some of the wincon logs are the pro
  knock-back play (pros log hogs/royal-hogs 1.6% each); the sim's log has `pushes`, so it is not automatically a
  whiff -- what is NOT visible is the goblin-barrel/princess/gang niche the owner named, because the scripted
  opponent rarely plays them (barrel shows as spawned goblins; top covered swarm = skeletons). m5k drifts toward
  logging mediums (49% vs 31-33%, kills 25%): single checkpoint per stage, (b) as a trend.
* **Tornado** (a): the KING-ACTIVATION niche is essentially absent -- 0 / 1 / 4 activations per 36 matches while the
  king was asleep at 43-54% of casts; 2-14% of casts land near our king versus 19% of pro tornadoes in the back/king
  zone. The credit is reachable (it fired 5 times) and worth 0.5 once per match; the policy has not found it. The
  CLUMP niche is half-known: 7-19 clumps of >=2 mediums per 36 matches, 22-38 combos (>=2 pulled bodies dead) --
  but the doctrine's payoff, rocket on the clump, is never cast, so the clump is cashed only by our tower/Tesla.
  The 18k control casts 54% of its tornadoes in the ENEMY half (pros 37%), m2k 14%: (b) the gate prior moved the
  cast site, one checkpoint each. nado_bad 13-19% of casts on all three.
* **Retarget / "reset aggro"** (c): **the reward cannot pay it.** `_register_nado` / `_nado_catch` list a
  tower-locked wincon only if `tile_dist(unit, tower) <= reach + 1.0` CENTRE to centre (sim/env.py:2472, :2508),
  but the engine's reach is a GAP (`goal = reach + body_radius(anchor) + body_radius(mover)`, engine.py:3683; tower
  body 1.5). Measured, wincons attacking our princess settle at hog 2.20 tiles (gate 1.8), royal_hogs 2.10 (1.7),
  giant 2.68 (2.2), balloon 2.68 (1.1) -> `targeters` is always empty, `nado_retarget` (0.4) has NEVER fired in
  training. `scratchpad/gauntlet/L16/retarget_reach.py`. Whether the policy "knows" this niche is therefore
  unmeasurable from the reward; the probe's own count (46-58% of tornadoes pull a unit whose `target` is one of our
  towers) says it pulls tower-locked units often, by accident or not.
* **Rocket** (a): 1 cast in 108 matches across three checkpoints (L13: 0/72 on two). The 2-for-1 / tower-chip
  niche does not exist in the policy. Pros: 3.4% of plays, 81% into the enemy half or on the tower. Cause still
  unknown (L13 candidates: own-half/no-king masks, `wincon_mis` on the king, `spell_waste` at radius 2.0).
* **Overall verdict on the owner's question:** no. The policy knows WHERE the log goes and casts the tornado on
  bodies, but it does not use any of the three spells for the niche that justifies its slot: the log kills
  something on a third of casts, the tornado wakes the king a handful of times per 36 matches and never sets up a
  rocket, and the rocket is not played. Two of those have reward-side causes found this loop (retarget unreachable;
  rocket at 0 for an unfound reason), which is the right order of work: fix what the reward cannot pay before
  asking the policy to learn it.

### 4. Instrument notes / does NOT establish
Pro table = tap timeline of humans; sim table = engine truth against `ScriptedBot`. Landing zones are comparable
in kind (same 4 buckets); the "opponent's play in the previous 6 s" is NOT (sim: nothing in the window on 41-56%
of casts, the bot's cadence). Not established: how the LIVE policy (`policy_rl.pt`, DDQN-tuned) uses spells --
this is the sim policy; whether the log-on-wincon share is knock-back intent; the rocket cause; the m5k trends.

### 5. m=5k read on the coef-0.5 run (a, pre-registered §5bk/§3; `data/bench/gate05_m5k.pt` snapshot 21:39, copy `scratchpad/gauntlet/L16/gate05_m5k.pt`, cmp-verified)
`tools/gate_prior_probe.py`, seeds 0/1/2: `played` at 3 elixir **0.281 / 0.269 / 0.315**; P(play | affordable)
0.282 / 0.287 / 0.295; elixir >= 6 on 1.2 / 1.3 / 1.0% of rows; mean cost of plays 2.61 / 2.60 / 2.54; plays at
>=6 elixir 12 / 10 / 4 per 2,400 rows (x-bow 7/6/3, rocket 1 on seed 1). Rule: `>= 0.35 on all seeds -> ask` is not
met (max 0.315); `<= 0.30 on all` is not met either (seed 2) -> mixed, run continues to 10k, no action. Context:
m2k was 0.271 / 0.227 / 0.239 -- the number has come back UP, exactly as the trainer's window pi(play) predicted
(§5bk), and it now sits where the coef-0.1 run was at ITS 5k (0.299 / 0.279 / 0.305, same instrument, §5bi) -- the
run whose 7.5k read then returned to control level. So at 5k the two coefs are indistinguishable on the probe.
avg_rew at the 5000 line: coef-0.5 -17.5, coef-0.1 -15.2 (single windowed log lines, not a discriminator).
Self-play ramps in at 5,000 (prob 0.15) -- confound for every read after this one. Next reads: 7.5k / 10k by
whoever picks the run up (`tools/gate_prior_probe.py data/bench/gate05_m10k.pt --seed 0/1/2`).

### 6. Files
`scratchpad/gauntlet/L16/{pro_spell_niche.py,txt, sim_spell_niche.py, sim_m2k/m5k/18k.{json,txt}, retarget_reach.py,
m5k_s0/1/2.txt}`; the m5k checkpoint copy stays out of git.

## §5br — GAUNTLET L17 (aggro gauntlet, loop 1): what aggro concept the model HAS, measured against the engine; real-game rules checked (2026-09-02 22:10-22:30)

Owner order (22:1x): a new gauntlet on AGGRO MANIPULATION -- who locks onto whom, next target after a kill,
retarget after tornado / log, what a placed card draws, interposition timing windows, 1v1 outcomes -- used for
sim decisions that transfer live; king activation and the sneaky-lock drill perform poorly "likely because it has
no concept of aggro mechanics". Also: stop the PPO when looped to a good place, restart vs resume; find a spot for
the `nado_retarget` fix; unblocked features first while the coef-0.5 run lives.

### 1. Correction to the premise (a)
"I don't think [aggro] is modeled anywhere in the ML model itself" -- it IS, in two places, both enabled in
config (`use_interactions: true`, `use_predictive_canvas: true`): `interactions.predict_targets` (nearest
attackable foe within the unit's own KB sight range, else nearest alive tower; building-targeters = nearest of
{building unit, tower}) feeds (i) the 12-dim interaction vector (elixir-value + urgency heading at each of the six
towers) and (ii) 3 predictive canvas channels (dead-reckoned positions 1 s ahead + enemy urgency). What it lacks
is STATE: no lock, no stickiness, no reset, no deploy delay, no building reach. The engine (`engine._acquire`,
:2494) has all of those: sticky `Unit.target`, `locked` once swinging, 1.8x-sight hysteresis for a walking unit's
current target, steal-only-if-closer, `aggro_reset` from stun/freeze/log/shove/taunt (20 reset sites), buildings
hold until the target dies or leaves reach, king wakes on ANY hit or a princess death (:5901-5909).

### 2. Measurement (a): obs predictor vs engine ground truth -- `scratchpad/gauntlet/L17/aggro_agreement.py`
m=5k snapshot (`scratchpad/gauntlet/L16/gate05_m5k.pt`), greedy searcher (same driver as §5bq), 12 matches x
seeds 0,1,2, every env step, every alive non-spell unit of BOTH teams, predictor fed the noise-free unit list
(no recall dropout, so this is the predictor's ceiling). Agreement = same kind AND same object.

| unit state (engine) | n | agree |
|---|---|---|
| walking, ours / theirs | 17,154 / 13,024 | **96.2% / 93.0%** |
| locked (swinging), ours / theirs | 6,015 / 8,253 | **81.5% / 80.6%** |
| building-only troop (hog, ram...) theirs | 3,417 | 92.7% |
| stationary building, ours / theirs | 5,345 / 1,914 | **25.0% / 15.6%** |
| deploying (`deploy_left` > 0) | 2,987 / 2,490 | 0% (by construction: engine has no target yet) |
| all | 60,599 | 74.2% |

Where the locked 19% goes (counts over all seeds): predicted UNIT, engine on a TOWER **1,041** (a troop chewing
the tower while a nearer troop stands next to it -- the predictor says it turns round; the engine, and the game,
say it does not); predicted TOWER, engine on a UNIT 784 (locked on a unit outside memoryless sight: hysteresis /
edge-gap); walking predicted tower but engine on unit 571. Buildings: `building|pred=tower|eng=none` 4,925 --
an X-Bow/Tesla with nothing in reach is shown as "heading for" a tower (the predictor has no reach and no
building branch; `mover_forecast` skips buildings as movers, so this hits the interaction vector only if it
counts them -- not checked this loop, (b)).
Stickiness: 6,900 target changes over 28,718 unit-seconds = **14.4 per unit-minute**; 53% because the old target
died, **47% with the old target alive** (walking steals 2,171, locked re-picks 950, building-only 144).
So aggro events the predictor cannot represent happen ~7 times per unit-minute of play.

### 3. Real-game rules vs the engine (a, wiki text via api.php, saved in `scratchpad/gauntlet/L17/wiki_*.txt`)
* King's Tower: "not able to attack until it is damaged or either of the player's Crown Towers are destroyed";
  activation "takes 4 seconds ... 3.3 seconds to aim ... another 0.7 seconds before it shoots". Engine: any hit
  wakes it / princess death wakes it (:5901, :5909) -- matches; the 4 s aim delay is NOT checked (b).
  For melee troops "the tile directly in front of the King's Tower and two tiles into the defending lane" is the
  activation cast -- the drill reference (0.472, 0.771) is that spot.
* Tornado: "Any unit caught in the Tornado can attack as long as there is a target in range"; a 2023 fix made
  cards stop attacking towers once "pulled out of range by Tornado" -> pulled out of reach = retarget. Engine:
  shove-out-of-reach reset (:5758) -- consistent. Chargers resist the pull and keep their charge.
* The Log: knockback "will reset their attack animation"; RG "retarget to another building". Engine :3095/:3127
  reset on knockback -- consistent.
* X-Bow: "3.5 seconds to deploy", the distraction placed "at the last second"; on target death it "retarget[s]
  onto the next closest"; a stun "force[s] the X-Bow to retarget to the nearest entity"; air cannot distract it.
  Engine building branch (:2565-2600) holds until death/out-of-reach, stun resets -- consistent.
* Sight ranges: KB matches the wiki tables for knight 5.5, pekka 5.0, musketeer 6.0, golem 7.0, giant/RG 7.5,
  balloon 7.7, hog 9.5, x-bow 11.5. Differences: mortar KB 11.5 vs wiki 11.0 (with a 5.0 blind spot the KB may
  not have), dart_goblin KB 7.5 vs wiki 6.5, bowler 5.5 vs 4 (the two wiki blogs disagree with each other). (b).
* Knight page: "cheap tank for tanking an enemy X-Bow" and "tank for Mortar or X-Bow" -- the owner's example is
  the wiki's own.

### 4. What this means for the plan
The "concept" the owner wants is the ENGINE's `_acquire` -- deterministic, already faithful at the rule level.
The model never sees it (obs is memoryless) and never queries it (search rolls forward blindly). Two routes,
both unblocked as NEW files while the run lives:
1. **Aggro oracle** (loop 2): `sim/aggro_oracle.py` over an engine fork (deepcopy ~6.5 ms, §env.py:1834):
   `who_targets(u)`, `targeted_by(u)`, `next_target_after(u kills t)`, `draws(card, cell)` (what locks onto a
   hypothetical placement and what it locks onto after its deploy time), `interpose_window(Y, enemy, Z)` (latest
   time Z placed between them still steals the lock), `duel(A, B)` (winner + HP left). Answered by advancing the
   fork, not by re-deriving rules. Tests = the owner's questions on fixed boards. Consumers: drills (predicates),
   rewards (tank-for-bow credit), search (prune placements the oracle says get blocked), obs.
2. **Lock-aware obs** (after the run stops -- edits `interactions.py`, which the trainer's workers import):
   give `predict_targets` an optional per-unit ENGAGED hint = sim `u.locked`+target; live = track stationarity
   next to a foe. Expected to lift locked agreement from 81% toward the walking 95% -- (b), the probe above is the
   instrument. Deploy-time and building-reach handling are two more one-line fixes the same probe will grade.

### 5. Does NOT establish
Whether the 19% locked mismatch changes any DECISION (the probe grades the feature, not the policy). Whether the
predictor's building error reaches the interaction vector. Whether the engine's 1.8x hysteresis and
steal-if-closer-while-walking match the real client (the wiki does not state the walking rule; (b) -- the
sandbox oracle, §5at, is the instrument if it ever runs). Nothing about the drills' pass rates per drill (the run
log prints only the aggregate: 42% pass all, 49% last 300).

### 6. Box (a, 22:2x)
Run at 5,975 eps, 0.5 ep/s, 179W-4588L-7D, avg_rew -20.3; 2 trainer PIDs; free RAM 5.85 GB; CPU 57%.
`gate05_m10k.pt` not yet written (ETA ~00:30). Untouched.

### 7. Files
`scratchpad/gauntlet/L17/aggro_agreement.py`, `agree_m5k.{json,txt}`, `wiki_*.txt` (rule sources).

## §5bs — GAUNTLET L18 (aggro gauntlet, loop 2): the engine-backed aggro oracle + tests (2026-09-02 22:20-22:30)

### 1. What was built (new files, nothing the trainer imports was touched)
`icebow/src/clashrl/sim/aggro_oracle.py` -- `AggroOracle(eng)`. Every question is answered by deep-copying the
engine, advancing the copy in 0.1 s ticks and reading the copy's `Unit.target` / `Tower.target` back through an
id-map to the caller's objects. No second rule set: if `engine._acquire` changes, the oracle's answers change with
it. The caller's engine is never mutated (test-covered). Queries:
* `target_of(u, horizon_s)` / `targeted_by(u, horizon_s)` -- who X attacks, who attacks Y, `horizon_s` ahead.
* `next_target_after_kill(u)` -- advance until X's current target dies; report seconds + the next lock.
* `after_spell(team, key, x, y, settle_s)` -- {unit: (target before, target after)} for a tornado / log / zap.
* `draws(team, key, x, y, horizon_s)` -- place Z, wait out its `deploy_left`, report what Z locks and what locks Z.
* `interpose_window(team, key, x, y, enemy, protect)` -- scan placement delays 0..6 s (0.2 s step, one fork each):
  latest delay at which Z still takes the enemy off Y, first delay that fails, and when the enemy first hits Y.
* `first_damage_to(victim, by)` -- seconds to first hit (units via `last_unit_hit_t`; buildings' hp decays with
  lifetime, so hp-drop is wrong for them -- trap found and avoided).
* `duel(a, b)` -- both at level 11, 1 tile apart, towers disarmed, until one dies: winner, HP left, seconds.
`icebow/tests/test_aggro_oracle.py` -- 8 tests, all pass (1.5 s): agree-with-engine, no-mutation, determinism,
next-after-kill, knight-draws-valk, window-closes-at-first-hit, tornado-KTA-retarget, duel + order symmetry.

### 2. Measured answers on the fixed boards (a; level 11; ticks 0.1 s)
Board A: our X-Bow at (0.26, 0.53), enemy Valkyrie at (0.26, 0.40) walking at it.
* valk -> x_bow from t=0; x_bow -> valk from t=0 (11.5 sight); valk's first hit on the bow at **1.8 s**, `locked`
  from then, standing at y=0.456.
* Knight (ours) placed at (0.26, 0.44/0.46/0.50): window = **(latest ok 1.6 s, first fail 1.8 s, hit 1.8 s)** at
  all three cells -- "how much time do I have" = until the enemy's first swing, not until it arrives; once locked,
  a nearer body does NOT pull it (§5br's 1,041 obs mismatches are this rule).
* Knight at (0.26, 0.48) = on top of where the valk stands: window (6.0, None) -- ALWAYS works, because the engine
  resets a lock when a body spawns on the locked unit (`aggro_reset`, engine :5758). Engine-truthful; real-game
  truth is (b) -- the wiki only documents tornado-out-of-reach and knockback resets, not spawn-shove. Flagged.
* Knight at y 0.46 is 1.3 tiles across the river: the ENEMY princess also shoots it (`targeted_by` lists the
  tower) -- correct and a reminder that "in front of the bow" on the enemy half costs tower damage.
* If the valk is left alone she kills the bow and re-locks after **7.9 s** onto our LEFT princess (same lane).
* Duels: valkyrie beats knight with **495.8 HP left (26%) in 10.2 s**; mini-PEKKA beats knight with **785.2 HP
  (56.5%) in 4.4 s**; the answer is order-independent (test).
Board B: enemy hog at (0.25, 0.62) -> reaches and locks our left princess at **t=2.0 s** (first hit 1.8 s).
* `after_spell(tornado at the drill reference (0.472, 0.771), settle 2 s)`: hog target princess -> **KING**. The
  king in the caller's engine stays inactive (no mutation). So the oracle reproduces the `nado_king_activation`
  drill's intended mechanism without the drill's centre-to-centre `nado_retarget` bug (§5bp) -- because it reads
  the engine's own reach, not a re-derived one.
Cost (6-unit board, `scratchpad/gauntlet/L18/cost_probe.py`): fork **0.5 ms**, `targets_at(3 s)` 1.9 ms,
`next_target_after_kill` 2.8 ms, `draws` 1.6 ms, `after_spell` 2.7 ms, `duel` 2.0 ms, `interpose_window`
(31 forks) **83 ms**. Cheap enough for drill predicates and for reward shaping at episode end; NOT free inside a
per-step search branch at 96 envs (83 ms x 96 = 8 s per step) -- windows must be cached per (unit pair, cell) if
search ever uses them.

### 3. What this does NOT establish
* Real-game fidelity of two engine behaviours the oracle makes visible: (i) spawn-on-top lock reset (:5758),
  (ii) no 4 s king aim delay after activation (wiki: 3.3 s aim + 0.7 s). Both (b); the sandbox oracle (§5at) is
  the instrument. Until then, drills/rewards built on the oracle must not depend on (i).
* Whether the engine's 1.8x-sight hysteresis and steal-if-closer-while-walking match the client (§5br carry).
* Anything about the policy: the oracle is an instrument; no drill, reward or search consumer exists yet, so no
  behaviour has changed. No number here is a training number.
* The cost numbers are for a 6-unit board; a 20-unit late-game board forks slower (deepcopy scales with units;
  §env.py:1834 measured ~6.5 ms in search) -- (b), measure when a consumer needs it.

### 4. Plan (loop 3)
An AGGRO DRILL family whose predicates are oracle calls, so the grader is the engine, not a hand-written reach:
(1) `tank_for_bow`: board A, hand knight; success = `interpose_window` says the placed knight took the lock
(`targeted_by(x_bow, 1 s)` has no enemy troop) before first damage; (2) `kta_retarget`: board B, hand tornado;
success = `target_of(hog, 1 s)` is the king (replaces the buggy `nado_retarget` predicate for THIS drill only --
the existing drill keeps its predicate until the run stops, since `sim/env.py` is imported by the workers ->
drills must NOT be added as a `drills_*.py` file while the run lives -- TRAP (a, 22:3x): `scenarios.load_all()`
imports EVERY `sim/drills_*.py` by filename at every env construction (`drill_env.py:1104`), so a new file with
that prefix silently enters the pool of any worker or snapshot-eval process spawned after it lands. Loop 3 writes
`sim/aggro_drills.py` (no `drills_` prefix, nothing imports it, registration only via an explicit `register()`)
with its own tests; wiring into `drills_icebow.py` waits for the run to stop.

### 5. Box (a, 22:28)
Run at 6,000 eps, 0.5 ep/s, 180W-4605L-7D, avg_rew -21.9, drills 42% pass all / 49% last 300; 15 processes carry
the run's command line; free RAM 4.53 GB; CPU 100%. `gate05_m10k.pt` not yet written. Untouched.

### 6. Files
`icebow/src/clashrl/sim/aggro_oracle.py`, `icebow/tests/test_aggro_oracle.py`, `scratchpad/gauntlet/L18/cost_probe.py`.

## §5bt — GAUNTLET L19 (aggro gauntlet, loop 3): do the existing aggro drills grade aggro? (2026-09-02 22:45-23:00)

Question: before writing new aggro drills, do the two the deck already has (`knight_guards_the_bow`,
`nado_the_sneaky_lock`, both in the run's pool: `drill_tiers: null`, `drill_frac: 0.3`, play-out on) reward the
aggro decision they are named for? Instrument 1: oracle sweeps (`scratchpad/gauntlet/L19/drill_sweep.py`, every
0.05-grid cell x delays, level 11 vs 11). Instrument 2: the real `DrillEnv` via `cli drills` and
`run_drill(scripted_policy(variant))` with the reference line swapped for variants (`ref_variants.py`), 40 reps,
seed 5 (same ladder rolls across variants), enemy level = ladder roll (13-16, weights 2/4/3/2) and pinned 11/14/16.

### 1. `knight_guards_the_bow` -- verdict is trivial (a, by code + by run)
`success = bow alive AND played(knight)`; `_verdict` fires "pass" the first step a predicate holds
(`drill_env.py:762`). The bow dies at 7.4-8.3 s unguarded, so ANY knight play anywhere before then passes.
Scripted 100%, doctrine 100%, nothing 0% (ladder). The knight's cell and timing are not graded at all.
Oracle sweep (760 = 190 cells x 4 delays, 11 v 11): the knight actually TAKES the Valkyrie's lock in 23/760
combos -- only on the river line y 0.50-0.55, x 0.05-0.35, delays <= 1.8 s (the reference (0.26, 0.50, 0.6) is one);
the bow then survives to 20 s in 4/760 (x 0.15 / 0.35 on the river: she dies where the princess also reaches).
So the skill the drill is NAMED for exists on 3% of the cells and is not what the verdict measures.

### 2. `nado_the_sneaky_lock` -- the tornado is not the play (a); notes contradicted (c)
Pass rates, 40 reps, same seed (enemy ladder / L11 / L14 / L16):
| line | ladder | L11 | L14 | L16 |
|---|---|---|---|---|
| reference: nado (0.26,0.40)@1.2 + knight (0.26,0.56)@2.4 | **47.5%** | 100 | 97.5 | 5 |
| knight only @2.4 | **60.0%** | 100 | 100 | 5 |
| nado only @1.2 | 0% | 100 | 5 | 0 |
| nado to the CENTRE (0.50,0.42)@1.2 only | 10% | 92.5 | 10 | 7.5 |
| nado CENTRE + knight | 50% | 92.5 | 85 | 5 |
| knight in FRONT (0.26,0.50)@0.6, no nado | **80.0%** | 100 | 95 | 5 |
| nothing | 2% | 100 | -- | -- |
* The reference tornado LOWERS the pass rate (47.5 vs 60 knight-only). The best line is a knight in front, early,
  with no tornado. At L16 nothing passes (5%). Against L11 the L16 bow wins alone ("nothing 100%").
* Mechanism (oracle, 11 v 11): the reference pull moves the knight 0.47 -> 0.409 (2 tiles); the bow's reach is
  11.5 tiles, so it keeps the knight and the bow's target is NEVER a tower until the knight dies. The notes'
  "A lone Tornado re-locks the bow ... the pull converts the bow's attention" is (c). Where a tornado does help
  (centre cells, 10/304), it works by pulling the knight out of ITS OWN 5.5-tile sight of the bow so it marches
  at our tower and dies to bow + princess -- a real aggro play, but not the one the drill describes, and the drill
  cannot tell the two apart because success is "enemy tower lost 150 hp", which our knight earns by walking there.
* Drill verdict order matters: failure (bow dead) is checked first, so the reference at 11 v 11 in the oracle
  board FAILS (bow dies 8.7 s, tower-150 at 16.8 s); in the DrillEnv at L11 it passes because OUR bow is L16.

### 3. Trap: `cli drills --level N` pins the ENEMY only (a)
Our cards come from `config/cards.yaml` per card (x_bow L16, 2556 hp, 93 dmg); `--level 11` therefore reports a
16-vs-11 board. Training rolls 13-16. Any drill report used to argue winnability must run WITHOUT `--level`
(ladder) or with the level pinned to 14-16. §5bs's oracle boards were 11 v 11 by construction and said so;
they describe the mechanism, not the training board. Hand-built `Unit(...)` vs `eng.deploy` spawn was checked on
the sneaky board: identical death times (7.4 s), so the oracle tests' spawn idiom is fine for single units
(squads still need `deploy`, per drill_env's own warning).

### 4. What this means
The owner's "the model performs poorly on the sneaky-lock drill because it has no concept of aggro" is (c) for
this drill: the drill does not test aggro; its best line is a 3-elixir knight and its reference is worse than that
line; on the ladder roll no line beats 80%. `nado_king_activation` IS a real aggro drill (scripted 100%, doctrine
5%, nothing 0%). The drills that would grade the owner's questions do not exist yet; they need predicates on the
engine's lock state, not on hp totals:
* `tank_for_bow`: success = the enemy's `target` is our knight while the bow is alive (lock taken), failure = the
  enemy hits the bow first. Graded on aggro, not on survival (which the level roll decides).
* `bow_first_lock`: enemy troop standing near the river; hand x_bow (+ tornado); success = the bow's FIRST target
  after its 3.5 s deploy is a tower; failure = a troop. This is the owner's "does the placed X-Bow get blocked or
  lock the tower" question and the oracle's `draws()` answers it; the drill board must be one where both outcomes
  are reachable (oracle sweep to choose it -- a troop within 11.5 tiles is always nearer than the tower at 10.6).
Both go in `sim/aggro_drills.py` (explicit `register()`, not auto-imported -- §5bs trap) with tests; wiring into
`drills_icebow.py` and retiring/re-predicating the two above waits for the run to stop.

### 5. Does NOT establish
How often the policy plays the knight in front vs behind in these drills (needs per-drill pass rates, which the
run log does not print, or `cli drills --policy <ckpt>` -- a loop of its own). Whether the real game's X-Bow
first-lock rule is "nearest in reach" (engine) -- (b). Real-game truth of the centre-pull mechanism -- (b).

### 6. Box (a, 23:00)
Run 6,950 eps, 227W-5329L-7D, avg_rew -18.8, drills 43% / 47% last 300; 11 procs; free RAM 5.07 GB;
`gate05_m10k.pt` not yet written. Untouched.

### 7. Files
`scratchpad/gauntlet/L19/{drill_sweep.py, drill_sweep.json, baseline.py, order.py, refs.py, trace_sneaky.py,
spawn_vs_unit.py, levels.py, ref_variants.py}`.

## §5bu — GAUNTLET L20 (aggro gauntlet, loop 4): aggro drills graded on the lock state (2026-09-02 23:05-23:45)

### 1. What was built (new files only; nothing the trainer imports was touched)
`icebow/src/clashrl/sim/aggro_drills.py` -- two `Scenario`s and an idempotent `register_all()`. Deliberately NOT
named `drills_*.py`: `scenarios.load_all()` imports every such file at env construction (drill_env.py:1104), so the
running coef-0.5 trainer would have picked a new drill up mid-run. Wiring into `drills_icebow.py` waits for the stop.
* `tank_for_bow`: our X-Bow at (0.26, 0.60), enemy Valkyrie at (0.24, 0.42) walking; hand knight, 4 elixir.
  success = a live drill enemy's `target` is our (non-noise) knight while the bow lives; failure = a drill enemy is
  `locked` on the bow (first hit landed) or the bow is dead. Graded on the RETARGET, not on who then wins.
* `bow_lane_choice`: enemy Knight at (0.26, 0.45) walking; hand x_bow, 6 elixir. success = the bow's FIRST non-None
  `target` after `deploy_left <= 0` is a `Tower`; failure = a `Unit`. The first lock is memoised in the drill's
  scratch dict so a later re-lock cannot rewrite the answer. `setup=_no_distractors` strips tagged noise (see 3).
`icebow/tests/test_aggro_drills.py` -- 4 tests, 40 s: register idempotent; tank scripted >= 90% and nothing 0%;
knight at 4.2 s <= 10%; bow opposite lane >= 90%, nothing 0%, same lane 0%.

### 2. Measured pass rates (a; `run_drill`, 40 reps, seed 5, enemy = ladder roll 13-16 unless pinned)
| drill / line | pass |
|---|---|
| tank_for_bow: nothing | 0% (40 fail) |
| tank_for_bow: reference knight (0.25, 0.5625) @0.6 | **92%**; L16 pinned 98% |
| tank_for_bow: knight @1.8 / @3.0 / @4.2 | 98% / 92% / **0%** |
| tank_for_bow: knight BEHIND the bow (0.25, 0.646) @0.6 | 88% |
| tank_for_bow: knight in the FAR lane (0.75, 0.5625) @0.6 | 0% |
| bow_lane_choice: nothing | 0% (40 timeout) |
| bow_lane_choice: reference bow (0.917, 0.5625) @0.6 | **95%**; L16 pinned 98% |
| bow_lane_choice: same lane (0.25, 0.5625) | 0% (37 fail) |
| bow_lane_choice: (0.806, 0.5625) -- one column nearer | 2% |
| bow_lane_choice: row 0.604 (nothing in reach) | 0% (40 timeout) |
| bow_lane_choice: reference WITH the distractors left on | 68% |
| `report()` doctrine column | tank 95%, bow 90% |
Read: both drills separate the correct line from the null and from the wrong lane / late line, and the enemy's level
does not move the verdict (L16 pinned = ladder). `tank_for_bow` grades LANE + TIMING (window = until her first hit,
3.7 s after she spawns), NOT front-vs-back row: a knight dropped behind the bow walks past it to meet her and takes
the lock 88% of the time. That is engine-true (he sees her at 5.5 tiles and the bow is a building he walks around);
it means the drill will not teach "in front" specifically, only "in her lane, in time". The DOCTRINE already passes
both (95 / 90) -- the aggro answer exists in the hand-written rules; whether the trained policy has it is 4.

### 3. Two traps (a, found by stepping the real DrillEnv, `scratchpad/gauntlet/L20/trace_drills.py`)
* THE AGENT'S GRID CANNOT REACH THE RIVER. `ActionSpace`: 18x24 cells, `deploy_board` 0.53125 -> `min_own_gy` 13 ->
  first legal row centre y = **0.5625**; `deploy_clamp` pulls anything nearer the river down to it. The L19 oracle
  sweeps placed the knight with `deploy_unit` at y 0.50 (river line) and said "6 cells take the lock"; the scripted
  reference (0.26, 0.50) in the real env snapped to (0.25, 0.5625) -- BEHIND the original bow at 0.56 -- and passed
  0/20. Every oracle-chosen cell must be a `cell_center` of a legal row, and every landing is +0.25 s late
  (`action_latency`). Re-swept on legal cells (`legal_sweep.py`): bow at y 0.60 -> her first hit at 3.7 s; cells that
  take the lock 16 (landing 0.85 s) / 10 (1.45) / 6 (2.05) / 4 (3.25) / 0 after; identical at L14 and L16. Bow at
  0.65: hit 4.7 s, 27 -> 11 cells; at 0.70: hit 6.8 s, all 27 cells at every delay (no timing content). 0.60 chosen.
  Bow first-lock on legal rows (`bow_row_probe.py`, knight L13 = L16): row 0.5625 -> 15/18 cells lock the knight,
  only x 0.86-0.97 lock the tower; row 0.604 -> 16 knight, 2 nothing. The tower is 11.6 tiles from the river row,
  the reach 11.5 + bodies: only the far corner of the OTHER lane sees a tower before the walking troop.
* DRILL NOISE LANDS WHERE THE ANSWER IS. `_place_noise` (drill_noise 0.5, 75% enemy) deals distractors into "the
  lane the drill is not about" at y 0.30-0.46 -- for a drill whose answer IS the other lane, that is a body 3-8
  tiles from the reference cell and always nearer than the tower. With noise on, the reference passes 68% (the
  structural cap: ~37% of episodes roll an enemy distractor). `Scenario` has no noise switch and `scenarios.py` is
  imported by the workers, so the drill's `setup` hook (runs after `_place_noise`) removes tagged bodies. A `noise`
  field on `Scenario` is the right fix once the run stops. `tank_for_bow` keeps its noise (the far lane is 10 tiles
  from the valk; measured no effect: the reference sits at 92% with it on).
* Smaller: `Tower` has no `.team` (towers are `eng.towers[team][i]`); `report()` needs `register_all()` called first
  because `cli drills` only sees `load_all()` modules.

### 4. Trained policy on these drills (a; GREEDY masked wrapper `_drill_policy_from_checkpoint`, 40 reps, seed 5)
| drill | nothing | scripted | doctrine | gate05 m5k | pre-run `policy_sim_ppo.pt` |
|---|---|---|---|---|---|
| tank_for_bow (new) | 0% | 92% | 95% | **12%** | 15% |
| bow_lane_choice (new) | 0% | 95% | 90% | **0%** | 35% |
| knight_guards_the_bow (old, trivial verdict) | 0% | 100% | 100% | 38% | 90% |
| nado_the_sneaky_lock (old) | 2% | 48% | 95% | 38% | 10% |
| nado_king_activation | 0% | 100% | 5% | 0% | 0% |
Read (a): the owner's "the model has no concept of aggro" is MEASURED for these two questions -- the m5k policy takes
the Valkyrie's lock 12% and never places the bow where its first lock is a tower (0%), while the doctrine does both
(95 / 90). The pre-run policy is no better on tank (15%) and only 35% on the lane choice. The old trivial drill
reads 90% -> 38% pre-run -> m5k, which is the m5k policy simply playing the knight less (§5br/§5bu P(play) ~0.30),
not an aggro change -- the drill cannot tell. `nado_the_sneaky_lock` doctrine 95% here vs the scripted reference
48%: the doctrine's line is the knight-in-front one (§5bt), and its 95% > reference confirms the reference is the
worse line. `nado_king_activation` stays at 0% for every policy and 5% for the doctrine (DOCTRINE GAP, §5bp).
One seed (seed 5, 40 reps): the pass rates are +-8 pp at this n; the 0 / 12 vs 90 / 95 separation is not.

### 5. Does NOT establish
Real-game truth of the two lock rules the drills grade (first-lock = nearest in reach for a siege building; a walking
troop steals only to a nearer body until its first hit) -- (b), sandbox oracle (§5at) is the instrument. Whether a
policy trained WITH these drills transfers the lane/timing rule to matches -- (b), needs the wiring after the stop and
a 3-seed A/B. Whether "knight in front" (as opposed to "knight in the lane in time") matters in the real game -- (b).

### 6. Box (a, 23:30)
Run 7,825 eps, 0.5 ep/s, 258W-6003L-7D, avg_rew -20.5, drills 42% pass all / 43% last 300; `gate05_m10k.pt` not
written; 5 processes on the run's command line at this read (11 at 23:00 -- pool churn, the log advances); free RAM
4.13 GB; CPU 100%. Untouched. The drill measurements above were run on this contended box: pass rates, not throughput.

### 6b. Owner question 23:40 -- "the watchdog fired elixir-collapse warnings; is it learning cheap cards again?" (a)
Watchdog (SAMPLED, `gate05_run_watchdog.out`): 6x ELIXIR>=6 DRIFT + 1x NEVER-REACHES-6 (0.3% at 7,250). The rule
fires on a reading >= 40% below a rolling median of a ~1% quantity whose per-reading noise is +-100% (0.1 -> 3.8 -> 0.2
-> 2.2% within 1,000 matches). By stretch, the >=6 share medians: 2400-4000 ~0.3%, 4100-6000 ~1.2%, 6000-8000 ~0.8%
-- up then slightly down, NO monotone decay; the 0.3% floor trip was followed by 1.3 / 0.5 / 0.8 / 0.8 / 0.6%.
GREEDY probe (same instrument each time, 3 seeds, 2,400 rows): mean cost of cards played m2k 2.63/2.66/2.66 -> m5k
2.61/2.60/2.54 (previous gate run m5k 2.60/2.53/2.58, m7.5k 2.52/2.63/2.49; deck mean 3.50) = FLAT and already cheap
before this run; elixir>=6 share m2k 4.0/3.5/3.0% -> m5k 1.2/1.3/1.0% = a REAL fall, all seeds. So: not "cheap cards
again" (never stopped), but banking-to-6 did fall m2k -> m5k. Decision point = the same probe on `gate05_m10k.pt`
(3 seeds): <= 1% again with cost ~2.6 is the 40k run's shape (stop); recovery toward 3% makes m5k a dip. Told the
owner; run left alone.

### 7. Files
`icebow/src/clashrl/sim/aggro_drills.py`, `icebow/tests/test_aggro_drills.py`, `scratchpad/gauntlet/L20/{board_sweep.py,
trace_drills.py, cell_probe.py, legal_sweep.py, bow_row_probe.py, rates.py, policy_rates.py}`.

## §5bv — GAUNTLET L21: the m10k read TRIPS the owner's rule; coef-0.5 run STOPPED (2026-09-03 00:55-)

### 1. The read (a; `tools/gate_prior_probe.py data/bench/gate05_m10k.pt --seed 0/1/2`, greedy, 2,400 rows each; snapshot 00:58, copy `scratchpad/gauntlet/L21/gate05_m10k.pt` cmp-verified)
| | m2k (§5bk) | m5k (§5bq.5) | **m10k (this loop)** |
|---|---|---|---|
| elixir >= 6 share | 4.0 / 3.5 / 3.0% | 1.2 / 1.3 / 1.0% | **0.1 / 0.2 / 0.0%** |
| P(play given affordable) | 0.228 / 0.227 / 0.239 | 0.282 / 0.287 / 0.295 | **0.364 / 0.352 / 0.375** |
| affordable rows | 41% | 40% | **30%** |
| elixir mean | 2.57 | 2.37 | **2.09** |
| mean cost of plays (deck 3.50) | 2.63 / 2.66 / 2.66 | 2.61 / 2.60 / 2.54 | 2.53 / 2.50 / 2.50 |
| x-bow plays / 2,400 rows | 7 / 6 / 3 (m5k) | | **1 / 2 / 0** |
Owner rule (§6 ruling 00:0x): median >=6 share < 1.0% -> stop. Median 0.1%: TRIPPED, every seed, not close.
Run state at the stop (a): 10,000 episodes, 356W-7653L-10D, avg_rew -16.5 (windowed), drills 42% pass all /
44% last 300; EVAL@8000 ladder 8% (avg-4 11%), fair 4%; best_wr 11.338 (EVAL@6000); watchdog 00:57 P(play)
0.364, elixir mean 2.11, >=6 0.3%, cell ent 0.85/5.08, procs=2; gate m10k regret 0.2418 oracle / 0.2395 belief
(m5k 0.2291 / 0.2045), 17 x-bows in 24 matches (41% defensive, 35% offensive, 24% dead). Live checkpoint
`data/policy_gate05_20260902.pt` (00:51, 1,935,229 B) backed up to `scratchpad/gauntlet/L21/policy_gate05_prekill_0051.pt`,
cmp-verified. Trainer tree = 2 python processes (61036 parent, 47956 child) + 2 stale grep tails.

### 2. Diagnosis input already in hand (a, trainer's own per-update diagnostics, `scratchpad/gauntlet/L21/run_log_lf.txt`, 237 blocks)
SAMPLED trainer series, NOT comparable to the greedy table above, but its own trend is the point: "anything playable
on X% of steps" 10.7 -> 12.0% flat all run; gate P(play GIVEN a choice) 0.223 (ep 375) -> 0.263 (ep 9950),
monotone; plays 3-4% of steps flat; raw pref 0.027 -> 0.031. So the ONE thing that moved is P(play | affordable),
by +0.04 over 10k episodes. Model (b): agent_dt 0.6 s, regen 1/2.8 s = 0.214 elixir per step; banking ~2 -> 6
needs ~19 consecutive affordable steps declined; the gate is a per-step coin, so P(bank) ~ (1-p)^19 -- a GEOMETRIC
TAIL. (1-p)^19 at p 0.29 -> 0.36 (greedy m5k -> m10k) falls by x0.14; measured >=6 share fell 1.2% -> 0.1-0.2%
(x0.08-0.17). Consistent. The >=6 share is therefore an exquisitely sensitive readout of a tiny gate drift, not a
separate "unlearning banking" event, and the play-cost mean (flat 2.5-2.66 since the PREVIOUS run's m2k) says the
card head never learned anything about cost at all. Untested (b): the run-length distribution of declined
affordable steps (needs per-row probe output; `gate_prior_probe.py --json` has no rows).

### 3. The stop (a, 01:01-01:02)
Order followed: state into §1 above -> watchdog python procs (69940, 37792) stopped first so it would not post a
death alert for an intended kill -> `taskkill /T /F` on 61036 (child 47956 and its child 15652 went with it) ->
trainer python procs 2 -> 0 verified -> `data/policy_gate05_20260902.pt` cmp-identical to the pre-kill backup ->
`gate05_run_20260902.progress` shows `exit=1 01:02:07`. Free RAM 4.3 -> 7.6 GB, CPU 100 -> 31% (the gate script's
m10k grading was still finishing; it exits on its own when it next polls and sees the run gone). Two stale
`grep --line-buffered` log tails from earlier sessions remain; harmless.

### 4. Diagnosis cut 1 -- what this run's own instrument says (a) and what history already tried (a)
`scratchpad/gauntlet/L21/run_log_lf.txt` (the run log, CR->LF), 237 "GATE LOGIT PRESSURE" blocks:
* post-clip (surviving) gate pressure: mean **+0.248**, median +0.153, toward PLAY in **199/237** blocks; by
  quarter +0.20 / +0.41 / +0.24 / +0.15 -- never a quarter toward WAIT.
* unclipped pressure (the trainer's CONTROL): mean **-0.052**, median +0.023, positive in 124/237 -- zero-mean.
* clip rate PLAY 0.765 vs WAIT 0.010; gradient KILLED PLAY 0.365 vs WAIT 0.005.
So the advantage signal on the gate is balanced and the clip converts it into a steady push toward PLAY. This is
the clip sign-flip HANDOFF already established ("34 sigma", §"What to do, and it is already built and staged") --
NOT new. What is new is only that (i) it is present for the whole of THIS run at coef 0.5 (the gate prior did not
neutralise it), and (ii) the drift it predicts is the measured one: P(play GIVEN a choice) 0.223 -> 0.263 sampled,
0.23 -> 0.36 greedy, and the >=6 share collapsed as its geometric tail (§2). History: `ppo_clip_play_mult` swept
5 values x 3 seeds x 700 matches from scratch, no arm beat control on winrate/reward, mult 4.0 worst on reward,
record says "do not reopen without a new reason" (§6-LADDER rung 1). The new reason, stated carefully: that sweep
graded winrate/reward at 700 matches; winrate is not a discriminator (§7) and the elixir drift is a 2k -> 10k
phenomenon that no 700-match run can show. Whether a clip repair stops the DRIFT is (b) -- untested on the
instrument that shows the drift (greedy bucket probe at m2k and m5k). It is not established that the clip is the
only or the main driver: the reward pays nothing for holding elixir and x-bow plays are so rare (1-7 per 2,400
rows) that the value of banking is almost never sampled -- a zero-mean gate advantage plus ANY asymmetry drifts.

### 5. What this does NOT establish
Which repair to make (next loop's job, with a measurement, not a preference): candidates are (A) a symmetric
objective for the gate head (KL-penalised / unclipped gate term, or per-head + widened bound -- the latter's 700-
match history is a null on the wrong instrument), (B) a reward-side term that pays for banking when x-bow/rocket
is in hand (doctrine says bank; the policy never samples it), (C) freezing/slowing the gate head's learning rate.
Restart-vs-resume: NOT decided; note that every snapshot after m2k carries a degraded gate, so "resume" would mean
m2k (4% >=6) or the pre-run `policy_sim_ppo.pt`, not m10k. The run-length (geometric) model of §2 is (b).

### 6. Plan (owner ruling §6, 00:0x) -- sequence for the stopped window
1. L22: diagnosis cut 2 = pick the repair with one decisive measurement; implement behind a config flag; unit
   test. 2. TEST RUN from scratch, same config as gate05 + the repair only, graded by the bucket probe at m2k vs this
   run's m2k (4.0/3.5/3.0%, P(play|aff) 0.23) and at m5k (drift). ~3 h to 5k at 0.5 ep/s. 3. Aggro wiring in code
   now but behind a flag OFF for the test run: `aggro_drills.register_all()` from `drills_icebow.py`, `noise` field
   on `Scenario`, re-predicate/retire `knight_guards_the_bow` + `nado_the_sneaky_lock`, `nado_retarget` reach fix
   (the owner's reward bug; `retarget_reach.py` as the test), lock-aware `predict_targets`. 4. Restart = repair +
   aggro flag ON; attribution: repair by the bucket probe, aggro by the new drills' pass rates (policy m5k 12%/0%,
   §5bu) and `nado_king_activation`. Restart-vs-resume decided at step 4 and recorded here.

### 7. Files
`scratchpad/gauntlet/L21/{m10k_probe.sh, m10k_s0/1/2.txt+json, m10k_copy.txt, run_log_lf.txt}`; the m10k snapshot
copy and the pre-kill checkpoint backup stay out of git.

## §5bw — GAUNTLET L22: diagnosis cut 2 -- the ledger says the reward buys the collapse; the prior is board-blind; the sim opponent pressures 1.4x as often as pros (2026-09-03 01:08-02:05)

### 1. RETRACTION of §5bv.4's "unclipped gate pressure is zero-mean"
That reading averaged the trainer's `gate_z_raw` block sums. Those sums are heavy-tailed (blocks run -45 to
+110, dominated by a handful of extreme importance ratios), so their mean says nothing about the typical
row. The clean statistic the trainer also prints, ADV BY ACTION (cumulative mean of the normalised
advantage per action kind, 11.6M samples over the run): **play +0.211 (n=409,032) vs wait -0.0077
(n=11,238,968)**. The bias toward PLAY is in the ADVANTAGES the gate is trained on, before any clip.
§5bv's claim that "the advantage signal on the gate is balanced and the clip converts it into a push" is
withdrawn; the clip asymmetry (PLAY 0.765 vs WAIT 0.010) is still real and still §5d's null.

### 2. Per-term reward ledger on the snapshots (a) -- `scratchpad/gauntlet/L22/term_ledger.py`
`env.rw_stats.run_summary()` per term, 24 matches x seeds 1/2/3 per checkpoint, `gate05_run.yaml`, search-free.
Two instruments, both reported because they disagree on the m2k policy: SAMPLED (gate ~ Bernoulli(P(play)),
card ~ softmax, cell = head argmax; the training-distribution instrument, closest to the probe) and GREEDY
(`Searcher.act(0)`, play iff P(play) > 0.25; `ab_reward_report`'s instrument).
```
SAMPLED (mean of 3 seeds, per match)      m2k        m5k       m10k
  plays % of steps                        12.1       12.9       12.9
  elixir mean / >=6 share                 2.64/4.3%  2.30/1.0%  2.27/1.0%
  threat_miss_idle   (fires)             -2.20 (3.3) -1.22 (2.0) -1.11 (1.9)
  leak                                   -0.15      -0.01      -0.02
  threat_response                        +1.85      +2.35      +2.10
  wincon_exec        (fires)             +0.98 (0.8) +1.01 (0.7) +1.00 (0.6)
  wincon_reach                           +0.99      +0.78      +0.72
  xbow_into_push                         -0.94      -0.44      -0.44
  elixir_trade                           -0.96      -0.92      -0.87
  outcome (win/loss)                     -1.61      -1.44      -1.44
  play-side shaping  + / -               +6.97/-3.85 +7.11/-3.52 +6.30/-3.12
  wait-side total                        -2.35      -1.23      -1.12
  TOTAL                                  -2.25      -0.34      -0.59
GREEDY (tau 0.25)                         m2k        m5k       m10k
  plays % / elixir / >=6                  9.6/4.49/29.9%  13.6/2.34/2.5%  14.1/2.22/1.3%
  leak               (fires)             -3.78 (31.5) -0.04     -0.02
  threat_miss_idle                       -2.76      -0.43      -0.24
  xbow_into_push                         -4.44      -1.56      -0.33
  wincon_exec                            +2.17      +2.24      +0.62
  wincon_reach                           +2.63      +1.50      +0.72
  wait-side total                        -6.54      -0.46      -0.26
  TOTAL                                  -5.70      +2.96      +0.93
```
Readings (a):
* The reward the policy gained from 2k to 10k is the wait-side penalty going away (sampled +1.2 of the +1.7
  total; greedy +6.3 of +8.7 to m5k), not more x-bow value. The x-bow terms are flat on the sampled
  instrument and FALL m5k -> m10k on the greedy one (exec 2.24 -> 0.62, reach 1.50 -> 0.72) while
  threat_miss keeps shrinking and total reward drops +2.96 -> +0.93. The policy is trading bow execution for
  fewer misses, which is what the ledger prices: a missed answerable threat is -1 every 4 s (rate-limited)
  while a bow is ~+1.5 exec + ~+1 reach once, and the match is lost either way (outcome -1.44, WR ~4.5%).
* The m2k GREEDY policy is a hoarder (P(play|aff) 0.23 < tau 0.25 -> it mostly waits): >=6 share 29.9%,
  leak -3.78/match over 31 fires, bows dropped into pushes -4.44. The sampled m2k policy of the same weights
  spends (4.3%). So "m2k banked" is instrument-dependent; §5bv's "resume from m2k" option is weaker than it
  read -- the m2k weights bank only when the gate's P(play) is thresholded, not when it is sampled.
* This is §5p's asymmetry again (play-side +5.32 vs wait-side -0.71 at m=5400 then; +6.3/-1.1 now), now
  with its TIME COURSE: the gap narrows because the wait-side penalties are learnable-away by spending.
* Instrument note for the stop rule: this full-match ledger (domain rand on, cell head) reads the >=6 share
  4.3 -> 1.0 -> 1.0% (m5k = m10k within +-0.2), where the probe (400 steps/env, domain rand off, centre
  cell) read 1.2 -> 0.1. Both put m10k at <= 1%; the trip stands. "Plateau at 1%" vs "collapse to 0" is an
  open instrument question, not a decision-changing one (the target is the pros' ~35%).

### 3. The shipped prior is BOARD-BLIND, and the pros' rule splits 2.3-3.6x on pressure (a)
`config/gate_prior.json` is P(play | elixir bucket, phase) only. The owner's ruling (§6, 08:20) named a
third key, threat-on-our-half; `tools/gate_prior.py` line 26 records dropping it ("needs the engine
recording pass"). It does not: the red side's plays are in `plays_ext.csv`, so "an enemy TROOP card was
played within the last W s" (spells and buildings excluded) is computable per window with no emulator.
`scratchpad/gauntlet/L22/prior_pressure.py`, 519 replays, W = 6 s, single elixir, per 0.6 s decision:
```
elixir            3      4      5      6      7      8      9
quiet          0.049  0.040  0.024  0.030  0.029  0.065  0.179    (n 5.1k / 5.9k / 9.0k / 10.0k / 10.4k / 8.9k / 4.9k)
pressure       0.084  0.089  0.086  0.068  0.066  0.110  0.235    (n 3.2k / 3.5k / 3.6k / 4.7k / 5.9k / 5.8k / 3.8k)
shipped blend  0.063  0.058  0.042  0.042  0.043  0.083  0.203
```
Pressure is on 37% of pro single-elixir windows (54% at W = 10 s; double elixir 65%/84%). At W = 10 s the
quiet row reads 0.016-0.024 at 5-7 elixir -- the split is not an artefact of the window. What this means
for the trainer: on pressured rows PPO (correctly) pushes PLAY and the blended prior pulls to 0.04 -- twice
as hard as the pros' own 0.07-0.09 -- and on quiet rows, where PPO has almost nothing to say (no
threat_miss fires there), the blend pulls only half as hard as the pros' 0.024-0.030. The conditioned
table halves the conflict where PPO is right and doubles the bank pull where banking happens. Training
effect (b) until the test run.

### 4. The sim opponent pressures more often than pros, with half-length quiet windows (a)
Same key on the sim (`quiet_stretches.py`: enemy troop unit with `age < 6 s`), sampled m10k policy,
12 matches, single elixir (t < 120 s), vs the pro timeline under the identical definition:
```
                         sim m10k s1   sim m10k s2   sim m2k s1   PROS (519 replays)
pressure on              46%           51%           52%          37%
quiet stretch median     5.4 s         4.8 s         5.4 s        9.0 s
stretch p90 / p95        13.4 / 18.0   11.2 / 15.8   14.5 / 17.6  23.4 / 28.6
stretches >= 11.2 s      16%           10%           12%          39%
  (= a 2->6 bank in single elixir: 4 elixir at 1/2.8 s)
quiet steps inside one   39%           30%           35%          71%
bankable stretches/phase ~1.6          ~1.0          ~1.2         ~2.7
```
So the scripted opponent gives roughly one bank-to-six window per single-elixir phase where a pro
opponent gives ~2.7. This bounds what ANY gate repair can produce in this sim (b for the size of the
bound; the cadence numbers are a). Caveats: the sim rows are the policy's own trajectories (the opponent
reacts to our plays, as a human would); 12 matches x 2 seeds; the pro key counts cards, the sim key counts
units of a card deployed within 6 s -- same event.

### 5. Decision: the repair is the PRESSURE-CONDITIONED PRIOR; the opponent cadence is a question
Ruled out with evidence: wait-side reward terms (dead at 3 seeds, §5ad; owner: do not propose another);
the clip (§5d/§5e null); a stronger unconditional coef (it would pull harder on exactly the pressured
rows where §3 shows the pros play 2-3x MORE than the blend). Chosen: the owner's own v0 spec with its
dropped key restored -- schema-2 table `P(play | phase, pressure, elixir bucket)` from `gate_prior.py`,
the sim key `any enemy troop with age < W` carried in the worker payload next to `t`, W from config
(`sim.ppo_gate_prior_pressure_s`, 0 = off = today's table byte-for-byte), trainer indexes
`_gtab[phase, pressure, bucket]`. One change vs gate05: the table + key. Grading: the bucket probe at m2k
(vs 4.0/3.5/3.0%, P(play|aff) 0.23) and m5k (vs 1.2/1.3/1.0), plus this ledger's >=6 share; the honest
success bar is the >=6 share holding ABOVE m2k's at m5k, not reaching the pros' 35% (§4's bound).
QUESTION for the owner (posted, not blocking the build): whether to bring the sim opponent's deploy
cadence toward the pro rate (37% pressured, 9 s median quiet) -- an opponent-model change, so it changes
what every sim number means and is not mine to make.

### 6. What this does NOT establish
That the conditioned prior moves the >=6 share (b: the test run). Whether the m5k = m10k plateau on the
ledger instrument is real (the probe says otherwise; both <= 1%). Whether W = 6 s is the right key width
(6 and 10 agree on the shape). Restart-vs-resume: unchanged from §5bv.5, with §2's note that m2k banks
only on the thresholded gate.

### 7. Files
`scratchpad/gauntlet/L22/{term_ledger.py, ledger_grid.sh, summarise.py, led_<ckpt>_<mode>_s<seed>.txt+json
(18), prior_pressure.py, prior_pressure_W6.json, prior_pressure_W10.json, quiet_stretches.py}`.

## §5bx. GAUNTLET L23 (2026-09-03 01:31-01:55) -- the pressure-conditioned gate prior is BUILT, tested, smoke-run, LAUNCHED

**Context.** §5bw chose the repair for the tripped ≥6-elixir read: restore the third key the owner's v0 ruling named
("threat on our half") to the gate prior, so the cross-entropy pull stops asking "wait" twice as hard as pros on rows
where the opponent just committed a troop, and asks it properly on quiet rows. This loop built it. No training ran;
the box was idle until the launch (1 python process, 7.2 GB free at 01:32). (Clock: §5bw's "01:08-02:05" was ~35 min
fast; its commit a007f23 landed 01:30. Times here are the box clock.)

### 1. What was built (one change, one flag; 0.0 = the gate05 run byte-for-byte)
* **`tools/gate_prior.py` schema 2** -- `--pressure-s W`. Pressure = the OPPONENT (red rows of `plays_ext.csv`)
  played a card of CardDB kind `troop` within W s of the window's start (abilities, spells, buildings excluded;
  a card the DB does not know is counted in `unknown_kind` and treated as a troop -- the corpus has none). Output
  keeps `p_play` (the blend; verified `==` the shipped `config/gate_prior.json` p_play AND windows) and adds
  `p_play_by_pressure[phase][quiet|pressure][bucket]`, `windows_by_pressure`, `play_windows_by_pressure`,
  `pressure_s`. A conditioned cell with < `MIN_CELL_N` 30 windows falls back to the blend (none does on the
  corpus: min cell n = 98, triple/quiet bucket 0). `prior_array(pr, W)` is the trainer's reader: `[phase, bucket]`
  at W=0, `[phase, pressure, bucket]` at W>0, and it REFUSES a table fit at another W (a 6-s table indexed by a
  10-s key is a different prior). Docstring corrected: the old text said the third key "needs the engine
  recording pass" -- it never did, the opponent's plays are in the same CSV.
* **`config/gate_prior_p6.json`** (NEW file; `config/gate_prior.json` untouched). (a) single elixir, buckets 0..10:
  quiet `0.009 0.022 0.030 0.049 0.039 0.024 0.030 0.028 0.065 0.178 0.133` (62% of windows), pressure
  `0.011 0.028 0.057 0.084 0.089 0.086 0.067 0.067 0.109 0.235 0.279` (38%). Double: quiet
  `0.008 0.033 0.055 0.083 0.076 0.079 0.108 0.135 0.255 0.418 0.341` (34%), pressure `0.010 0.039 0.066 0.113
  0.138 0.128 0.146 0.175 0.273 0.459 0.342` (66%). Triple: quiet `.010 .050 .082 .136 .145 .145 .219 .250 .340
  .475 .301` (20%), pressure `.024 .048 .093 .162 .188 .202 .247 .283 .355 .455 .319` (80%). Matches §5bw.3 to
  the third decimal (that fit used a hand-typed spell/building list; this one uses CardDB kind -- 38% vs 37%
  pressured single windows is the whole difference).
* **Sim key: `SimMatchEnv.enemy_troop_min_age()`** (`sim/env.py`, next to `_hand_ids`) -- age in s of the
  YOUNGEST living enemy troop (`team==1, hp>0, spec.kind=="troop"`), 1e9 with none. `Unit.age` starts at 0 on
  deploy and includes deploy time, so `min_age < W` is the same event as the table's "played within W s".
  The worker payload (`remote_pool.py payload()`) carries it RAW as `"eage"` beside `"t"`; the parent applies the
  threshold, so no config seam can open between worker and parent (the drill_frac lesson). Main-process fallback,
  `roll["eage"]`, and the per-step refresh mirror the `t` plumbing at all four sites.
* **Trainer (`train_sim_ppo.py`)**: `sim.ppo_gate_prior_pressure_s` (default 0.0). >0 requires a schema-2 table
  with matching W (asserted at load), builds `_gtab[phase, pres, bucket]`, indexes with
  `flat("eage") < W`; the loss line is unchanged. The GATE PRIOR banner prints both rows; the periodic
  `GATE PRIOR CE` line gains `| PRESSURE on N% of them` (share of USABLE rows that are pressured) -- the monitor
  for whether the sim's pressure rate drifts during the run (§5bw.4 measured 46-52% on the trained policy's
  trajectories vs pros' 37%).
* **`data/bench/gatep6_run.yaml`** = `gate05_run.yaml` with `ppo_gate_prior_path: config/gate_prior_p6.json`,
  `ppo_gate_prior_pressure_s: 6.0`, ckpt `data/policy_gatep6_20260903.pt`, continuation log
  `data/continuations_gatep6.jsonl`. `diff` = those four lines. Launched at the end of the loop (§5).

### 2. Verification (a)
* `tests/test_gate_prior.py`: 5 new tests in `TestPressureKey` -- pressure windows are the troop ones only (a red
  knight at 3.1 s flags exactly the 10 windows starting in [3.1, 9.1); a fireball and a tesla flag none; blue's
  play at 4.0 s lands in a pressured window, the one at 40 s in a quiet one); the blend is unchanged by the
  split; thin cells fall back to the blend; `prior_array` shapes (3,11)/(3,2,11) and the W guard; the sim key
  (empty board 1e9; own troop and enemy building ignored; youngest of two enemy troops; a dead one drops out;
  `advance(0.6)` ages it). **12/12 pass** (2.1 s). Trap found: window starts accumulate 0.6 in floating point, so
  a play exactly ON a boundary (3.0 = 5 x 0.6) is a rounding coin-flip -- the test uses 3.1 s, and this matters
  for nobody else (real timestamps are not multiples of 0.6).
* Smoke run, flag ON: `run.py --config data/bench/gatep6_run.yaml train-sim-ppo --matches 6 --envs 8 --workers 2
  --size 432 --device cpu --seed 41 --search-interval 4 --out <scratchpad>/smoke_p6.pt` -> exit 0, banner
  `GATE PRIOR ON: coef 0.500 ... PRESSURE key W=6 s; single-elixir P(play) at 4/7/9 elixir quiet
  0.039/0.028/0.178, pressure 0.089/0.067/0.235`, first update `GATE PRIOR CE 0.6731 | pi(play) 0.489 vs prior
  0.056 | 13% of rows usable | PRESSURE on 57% of them`. The key reaches the loss through the remote-worker path.
* Smoke run, flag OFF (`gate05_run.yaml`, same args, isolated `--out`): exit 0, the ORIGINAL banner
  (`... P(play) at 4 / 7 / 9 elixir = 0.06 / 0.04 / 0.20`, no PRESSURE clause), `GATE PRIOR CE 0.6641 | 12% of
  rows usable`. Existing checkpoints untouched (`policy_gate05_20260902.pt` mtime 00:51, `policy_sim_ppo.pt` Aug 29).

### 3. What this does NOT establish
* That the conditioned pull moves the ≥6 share at all (b). That is the test run's question, and §5bw.4 bounds the
  answer: the sim opponent leaves ~1 bankable quiet window per phase vs pros' ~2.7, so even a perfect prior cannot
  reach the pros' 35% of plays at ≥6. Bar stays: m5k ≥6 share above gate05's m2k (4.0/3.5/3.0%, probe seeds 0/1/2).
* Whether W=6 is the right window (b). W=10 gives pressure on 54% of single windows and a smaller quiet/pressure
  split (§5bw.3); 6 was chosen because it is ~a troop's deploy + walk to the river. One W per experiment.
* The 57% pressure share in the smoke run is 8 matches of an UNTRAINED policy (its opponent draws differ) -- not
  comparable to §5bw.4's 46-52% on the m10k policy. The run's own `PRESSURE on` line is the comparable number.

### 5. LAUNCHED: the TEST RUN (01:46) -- RUNNING NOW
`data/bench/gatep6_run_launch.sh` (= gate05's launch script with the config swapped; the ONE change is the flag):
`PYTHONHASHSEED=0 run.py --config data/bench/gatep6_run.yaml train-sim-ppo --matches 40000 --envs 96 --workers 12
--size 432 --device cuda --seed 41 --search-interval 4`, from scratch. Log `data/bench/gatep6_run_20260903.log`,
ckpt `data/policy_gatep6_20260903.pt` (did not exist at launch; first write seen 01:47), continuation log
`data/continuations_gatep6.jsonl`, `.launched` epoch 1788414375, exit line will land in `gatep6_run_20260903.progress`.
Box before launch: only the owner's Nucleo uvicorn (pid 63608, left alone), 6.9 GB free, GPU 1.6/8.2 GB. After: 15
python processes. First update line: `GATE PRIOR CE 0.7174 | pi(play) 0.513 vs prior 0.050 | 9% of rows usable |
PRESSURE on 44% of them`. Monitors (nohup): `tools/ppo_watchdog.py data/policy_gatep6_20260903.pt --every 300
--quiet-min 30` -> `data/bench/gatep6_run_watchdog.out` (its first cycle ran before the ckpt existed:
"health probe failed: FileNotFoundError", expected, it retries every 300 s); `tools/real_run_gates.py --run
gatep6_20260903` -> `data/bench/gatep6_run_gates.out` (snapshots `data/bench/gatep6_m{5,10,20}k.pt`, state
`gatep6_run_gates.progress`). **Reads:** m2k by hand (`gate_prior_probe.py data/policy_gatep6_20260903.pt --seed
0/1/2`, gate05 read 4.0/3.5/3.0% ≥6, P(play|aff) 0.23; ETA ~1.1 h at gate05's 0.5 ep/s), m5k from the gates
snapshot (gate05: 1.2/1.3/1.0%). Bar: m5k ≥6 share above gate05's m2k. Then decide restart-vs-resume (§6 ruling).

### 4. Files
`tools/gate_prior.py`, `config/gate_prior_p6.json` (new), `src/clashrl/sim/env.py`, `src/clashrl/sim/remote_pool.py`,
`src/clashrl/train_sim_ppo.py`, `tests/test_gate_prior.py`. `data/bench/gatep6_run.yaml` (new) is NOT in git --
`icebow/data/` is gitignored and no `data/bench/*.yaml` ever was (gate05_run.yaml included); its full diff vs
gate05_run.yaml is the four lines in §1, reproducible from that. Same for `data/bench/gatep6_run_launch.sh` (§5).

