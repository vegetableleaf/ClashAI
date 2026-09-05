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

Last updated: **2026-09-05 22:3x UTC**, branch `main`.

### Where the project stands (read this, then §6 / §7 / §8)

**The best policy we have is the imitation model**, `icebow/data/bc_pro/models/bc_bias_native_s0.pt`
(behaviour cloning on pro placements; **15.44 / 46.61** top-1/top-5 pro-cell agreement on v1 boards,
15.00 / 43.51 on v2). Nothing since has beaten it.

**Reinforcement learning on top of it has now failed twice on the real engine** (§5cs.44-51). Four
arms, ~1,500 engine matches: with a KL leash to the init the policy stays exactly where it started
(15.44 -> 16.33 -> 15.64 over 500 matches); without one it degenerates (-> 6.87, with 26% of its
placement logits railed). The unshaped engine reward has produced **no measured gain in pro
agreement, ever**. That is the central open problem, and it is a REWARD/DATA problem, not an
algorithm one -- see §5cs.51 D for what is closed and what is not.

**What was fixed today and matters going forward:**
* The **deploy rule** is now `sim.ppo_gate_rule: sample` (owner ruling) via one shared
  `clashrl/gate_rule.py` -- viewers and graders sample the gate instead of thresholding it at 0.25.
  A pro-calibrated gate (pro mean P(play) 0.111) essentially never crosses 0.25, so the old rule
  rendered every calibrated checkpoint catatonic (0.1-1.5 plays/match; 17.2-24.5 under sampling).
  `play.py` (live) and the sim trainer's greedy bench deliberately still use the threshold.
* The **gate prior** (Bernoulli CE toward the pro play-rate table, coef 2.0) prevents the gate
  collapse that killed the engA pair. Keep it in any future run.
* **Engine visualiser** published (`scratchpad/gauntlet/L62/live_view.py`, artifact
  https://claude.ai/code/artifact/3aca72fa-8f09-40e9-9d59-65c0dc2e03d2): the sim debugger's whole
  feature set -- radii, P1 band, term readout, gate probability -- on real engine frames.
* **Grid 432 is correct**; the owner's 576 proposal was measured and contradicted (§5cs.48).

**Never quote a pro-agreement number without a play rate beside it** (§5cs.46 retraction) and never
compare two instruments (§8). Older headers and the full narrative are in `HANDOFF_ARCHIVE.md`.

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

**2026-09-05 22:3x UTC -- NOTHING IS TRAINING (L63b: proposal posted, awaiting approval; L63: research phase of the new gauntlet; 5 research agents writing to `scratchpad/gauntlet/L63/`).** The engB engine-PPO pair was killed at m=602/609
(§5cs.51, owner ruling); engA before it (§5cs.46). Box state verified at the kill: python processes
7 -> 3, free RAM 5.0 GB.

* **Alive and NOT to be touched:** the replay crawler (PIDs 29444 + 53824, `crawl_icebow.py expand 150`),
  the owner's Nucleo uvicorn (PID 63608, port 8765). The sandbox VM `qemu-system-x86_64-headless`
  (PID 54304, 413 MB) is UP with both engine slots now FREE (ports 38031/38032, 37031/37032).
* **Checkpoints that matter.** IL init `icebow/data/bc_pro/models/bc_bias_native_s0.pt`
  (sha a1273d5d, 15.44/46.61 v1, 15.00/43.51 v2) -- the best policy we have, and the thing every
  engine-PPO arm failed to beat. Evidence-only: `data/bench/engB_{ctrl,kl}_{m0,m250,m500|m502,latest}.pt`
  and the engA set. `data/bench/` is gitignored.
* **Instruments** (never mix two of them in one comparison): `scratchpad/gauntlet/L61/read_ckpt.py`
  (pro cell agreement, deterministic, CONDITIONAL ON A PLAY -- always quote a play rate beside it);
  `clashrl.cli policy-stats` and `L62/gate_probe.py` (sim, now honouring `sim.ppo_gate_rule`);
  the engine train logs' own GATE readout. Gate health = `p_gate` within ~0.7-1.3x of `gp_target`
  AND p50/p90/max not coincident (§5cs.49).
* **Open lines with the box now free:** bridge v2 dynamic verification (`L62/re_verify_bridge.py
  deploy --bridge v2`, port 37041); the live-socket run of the engine visualiser (`L62/live_view.md` §6);
  the distillation teacher (§6-PRIORITY-B). Full list in §6.
* History of what USED to run here (the cuda run, the gate-prior sweeps, floor7/aggro/gatec2/c2r,
  engA) is in `HANDOFF_ARCHIVE.md`.

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
| L48c (2026-09-04, engine.py `crowns()`) | **CROWNS ARE COUNTED AS DEAD TOWERS, NOT AS CR CROWNS.** Owner-reported from sim_view, confirmed in `engine.py:5970` `crowns()`: a king kill with one princess still standing counts 2, real CR awards 3 the moment the king falls. Outcome/winrate correct (`_check_end` ends on the king); `crown_delta`, "crowns taken/lost", the search scorer's `crown_w` term and the per-tower `take_enemy_tower`/`lose_own_tower` reward all read the undercount. FIXED L48c per owner ruling (A): `crowns()` returns 3 on a dead enemy king -- reporting AND reward; c2r trained wholly on the old count, first training effect = the next run (5cs.17). Post-fix crown_delta is a NEW instrument. | 48 ceiling matches each: doctrine 5 of 12 king losses undercounted (crown_delta -1.000 read / -1.104 real); policy 8 of 12 (-0.354 read / -0.521 real); our own king kills 0/48 both legs |

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

### ⚑ TOP OF THE QUEUE as of 2026-09-05 21:5x UTC (everything below this block predates the engine era)

**CLOSED today, do not restart without a new reason:** engine PPO, both pairs (engA §5cs.46, engB
§5cs.51). The questions they were launched to answer are answered -- the gate prior prevents the gate
collapse, the KL leash prevents forgetting, and neither buys any pro agreement. **The box is idle.**

**The new gauntlet ARRIVED 2026-09-05 22:0x (L63, §5cs.52): scrap the pipeline, research, propose a new one,
then implement with a live-training final layer. Research phase running; proposal next loop.**

**OWNER RULINGS 2026-09-05 22:4x (answers to the §5cs.52 questions; do not re-litigate):**
1. Live-play path MAY be touched for this gauntlet (guardrail superseded for this gauntlet only).
2. The real engine (cr-native-sandbox) is IN as a training / proxy environment -- "the highest fidelity
   environment we have outside the actual game". Sim, its reward, PPO/DQN trainers, policy net: dropped.
3. The live session behind the "worse than a scripted bot" report used the **KL checkpoint** (engB_kl_*), i.e. the
   init-equivalent policy (15.64 top-1) -- the report is a read of the BC init on screen-detector observations.
4. Budget: unlimited box time for now; cloud compute if free via student programmes, otherwise quote the price first.
5. Proxy gates allowed (agreement-with-play-rate -> engine winrate n>=100 -> live); **live grading has the final say.** The pre-gauntlet candidate list is kept for reference: Until it arrives, the standing candidates, ranked by the lead:
1. **Improve the imitation, not the RL.** The 15.44/46.61 init is the ceiling everything else is
   measured against, and it was fit on ~1,000 pro boards. More replays (the crawler is still running;
   deck pool 314 -> 587 with the x/y backfill, owner's bar is >1,000) and/or a better BC recipe is
   the only line with a demonstrated mechanism behind it.
2. **The distillation teacher** (§6-PRIORITY-B, owner-requested twice, never run). Teacher must be
   N=1. This is the one route that could raise the ceiling rather than defend it.
3. **A shaped/denser engine reward** -- untested, and the honest reading of §5cs.51 is that the
   reward is the untested half. Cheap screen: score the existing reward terms against pro plays.
4. **Bridge v2 dynamic verification** (`L62/re_verify_bridge.py deploy --bridge v2`, port 37041) --
   both engine slots are free now; unblocks buffs + area effects in the observation and the viewer.
5. **Live-socket run of the engine visualiser** (`L62/live_view.md` §6) -- 10 minutes, needs a slot.

**Unresolved question put to the owner and not yet answered:** which checkpoint file was loaded for
the live-play session that produced the "worse than a scripted bot" report (§5cs.51 C.4). If it was
`engB_ctrl_*`, that was the degenerate arm and the report says nothing about the KL arm.

### ⚑ OWNER RULING 2026-09-04 14:4x -- SIM-PARITY ORACLE, queued immediately after the m30k read + verdict
Owner asked whether the sandbox engine (cr-native-sandbox, §5at-§5ay) can raise the sim's fidelity. Answer given:
yes as a MEASURING instrument, not as a training env (no opponent, ~30x slower per worker with observe() per decision,
reset/branch cost unmeasured; it touches only the mechanics half of the gap -- nothing for perception/latency or the
gate). Owner: "sure, queue it after the m30k read + verdict." The order of work, one loop each:
1. **Sim-side timeline driver** (no emulator needed; runs beside c2r): drive the crawl's 20 Hz command timelines
   (`data/royaleapi/crawl2/plays_ext.csv`, the same 211 tags the engine converted, `scratchpad/gauntlet/ext/batch/`)
   through OUR sim with both sides scripted-off, and grade crowns / winner against RoyaleAPI exactly as §5ay graded
   the engine (engine: crowns 77.7%, winner 80.1%, clean 64%). Same conversion caveats apply (levels, abilities
   skipped) so the two numbers are comparable. THE number: our sim's crowns-match on the same 211 replays. If it is
   close to the engine's 77.7%, mechanics are a small part of the gap and the sandbox is a calibration tool; if it is
   far below, mechanics are a large unmeasured part and the per-tick oracle becomes the main line.
   **DONE L51 (§5cs.21): sim 26.1% crowns / 44.1% winner vs engine 77.7% / 80.1% on the same 211; the miss is
   one-directional against the X-Bow side (sim 23 wins for it vs 129 real); mirror test symmetric -> deck
   mechanics. Item 2 is warranted.**
2. NOW WARRANTED by (1) -- after c2r ends (emulator): engine per-tick dump (`--record-full --record-every 4`, ~1.1 h over the 135
   clean matches, §5ay.6 item 4 -- emulator, NOT beside c2r) + tick-level diff (positions, death ticks, tower HP,
   elixir) -> a ranked list of mechanic divergences, each its own fix experiment.
   **L52 (§5cs.22): the diff tool exists (`scratchpad/gauntlet/L52/tick_diff.py`, `SIMDIR=<simrec dir>`); three
   divergences from the two recorded clips (spell edge, corner buildings, hidden-tesla pull) are driver patches
   (`--patch`) and a population NULL (26.1 -> 26.5%). RECORD FIRST the swarm/bait mismatches: 08QPVCPC9QQU,
   00LYPLJLYQCR, 020YPYYVJR0V, 02JY9GPPVPPG, 00GYPYPYUQQY, 022YYL8R2GG0, 092PPVY2CGG8 (evo skarmy, sim 3-0 <100 s)
   and the 20 early-collapse tags listed by `L52/compare.py`-style query; then the rest of the 135.**
   **L53 (§5cs.23): first window to read = 08QPVCPC9QQU ticks 430-560 (where is the real evo-army pack when the
   Ice Wizard lands at tick 506, and does it survive its deploy second); then the knight+tower vs evo-army damage
   total. Sim-side numbers to compare against: unanswered 3947, +knight 3947, +ice wizard 0.**
3. Levels pass-through in the engine (§5ay.6 item 1) sharpens the oracle's own floor before trusting the diff.
Not queued: training inside the engine; the "ghost pro" eval (our side in the engine vs the recorded pro's commands)
stays a candidate for a periodic fidelity eval only.

### ⚑ OWNER RULINGS 2026-09-03 23:4x (owner asleep; gauntlet runs overnight)
* Sim-side slot-31 parity arm (`sim/env.py:643 mem[5] = eng.elixir[1]/10`, own retrain): PERMITTED to launch "if c2r is
  stopped, or paused (by your discretion)". Not while c2r runs.
* `play.py` gets the same `env.opp_mem_slot5` switch as train-rl's env (default legacy `opp_estimate`) -- DONE 23:4x.
* Overnight defaults stated to the owner: c2r m5k gate + collapse protocol; train_rl stop-path fix (stop before
  re-queueing); hand-recognition audit next; 2 matches per live session, eps 0 / learning off, <= ~2 sessions/hour;
  window re-maximized between sessions only; nothing outside the game window.

### ⚑ OWNER RULING 2026-09-03 23:3x -- c2r collapse protocol
"If the PPO collapses again, diagnose the cause (did the reach fix cause it or something else?) then restart the PPO with
whatever repairs you decide to implement." Pre-registered (5cr.9): the m5k gate read on the SAME instruments as gatec2/gate05
(greedy probe 3 seeds: elixir>=6 share + mean card cost; drills; watchdog P(play)/cell_struct). COLLAPSE = the 40k shape:
greedy >=6 share <= 1% on all 3 seeds while gatec2_m10k reads ~3% on the same probe the same day, or watchdog P(play) mean
< 0.05 / > 0.90, or the cell head flat/collapsed. Attribution design if it trips: c2r differs from gatec2 by FOUR things
(reach fix, optimizer reset, RAIL-GUARD cell-head x0.0556, +N matches) -- the reach fix is testable in isolation: two
short arms from gatec2_m10k, reach on vs off, same seed, ~2000 matches each, read on the same probe; the optimizer/rail
pair is testable by a resume WITHOUT the rescale. Only then restart with the repair. As of m4000 (23:21) the watchdog
reads P(play) 0.197 / >=6 3.0% / cell_struct 9175 vs the init's 0.166 / 3.1% / 9588 -- NOT collapsed; the 23:05 DRIFT
alerts were single readings of a +-100%-noise instrument (0.5% -> 2.2 -> 1.8 -> 3.0% on the next three).

### ⚑ AGGRO ARM QUEUE (owner order 2026-09-03 07:45 + 17:3x)
* **aggro1** RUNNING since 17:22 (§5cn): gate05 recipe from scratch + `sim.aggro_drills: true`. Read at m2k / m5k.
* **aggro1b** (owner 17:3x, §5cn.7): same recipe + `--init data/bench/gatec2_m10k.pt`. AFTER aggro1's m5k read, never
  concurrently. Before launch: confirm the trainer's `--init` resets optimizer + match counter (else it is a resume).
* then `env.nado_retarget_reach_fix` (the reward bug fix) as its own arm, then `observation.lock_aware_targets`.
* **sim-parity arm (owner 18:2x, §5co.5): engine `spell_delay` 0.4 -> 1.0 s** (engine.py:855, every spell but royal
  delivery), after aggro1b. Owner 19:1x: "the delay is 1.0 s for ALL spells, confirmed from online sources" -- no
  measurement step needed. The sim's log whiff is 21-25% on every arm and the policy can never learn a lead the sim does
  not need. ONE change vs the base recipe; read on spellprobe log/tornado whiff both slices + the m5k gate.
* deferred: `sim.bot_attack_floor` arm (owner 10:5x); coef-1.0 and coverage arms NOT taken.

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
     (did not exist before). LAUNCHED 01:46 (`data/bench/gatep6_run_launch.sh`), monitors up -- see §5bx.5.
  -> L24 (§5by): m2k read FAILS the bar's direction: 0.9/0.8/0.5% at m2,350 vs gate05 m2k 4.0/3.5/3.0. Running on to
     the pre-registered m5k read (ETA ~03:50 at 0.7 ep/s). Owner question re-posted: opponent cadence (see §5by.4).
  -> L25 (§5bz): m5k read 1.4/1.1/2.0% -- bar FAILED, tie with gate05's m5k. Run stopped 04:16. Box idle. A/B/C open;
     aggro wiring proceeds (unblocked).
  -> L26 (§5ca): step 4 BUILT: `sim.aggro_drills` + `env.nado_retarget_reach_fix`, both default false. At the
     restart, turning either on is a change; both on = two changes (owner's call, §5ca.4). Grade: `gate_prior_probe.py` seeds 0/1/2 at m2k (gate05: >=6 share 4.0/3.5/3.0%,
     P(play|aff) 0.23) and m5k (gate05: 1.2/1.3/1.0%) + the L22 ledger. Bar: m5k >=6 share ABOVE gate05's m2k.
  -> L27 (§5cb): the last aggro item BUILT: `observation.lock_aware_targets` (default false). Engine agreement 74.2 ->
     95.8% with engine hints; a live-style proxy reaches 89.7%. Turning it on at the restart = a THIRD change (and a
     sim-to-real seam until live carries the hint) -- owner's call, §5cb.4.
  -> L28 (05:48): HOLD. No ruling, no steering, box idle. Nothing unblocked remains (the live tracker that would close
     the lock-aware seam is live-path work: sessions are raw video + clicks, no per-frame detections -- not a cheap probe).
  -> L29 (§5cc): Path A PREPARED. The opponent cadence had no knob; `sim.bot_attack_floor` added (default 0 = historical,
     eval bots untouched). Floor 7 gives non-beatdown bots 42% pressure / 2.2 bankable windows per phase (from 56% / 0.62;
     pros 37% / 2.7). Path A is now launchable the moment the owner rules: `sim.bot_attack_floor: 7`, one change.
  -> L30 (§5cd): OWNER RULED 07:4x -- A (then C with caution if A fails); cadence toward the pros: yes; aggro flags one at a
     time in the order aggro_drills -> reach fix -> lock-aware. Path A LAUNCHED 07:48 (floor7_run, from scratch). Reads: m2k
     by hand (~1.1 h), m5k from the gates snapshot; bar = m5k >=6 share above gate05's 1.2/1.3/1.0%.
  -> L31 (§5ce): m2k SCREEN (not the bar): floor7 @m2450 >=6 share 1.2/1.3/0.5% vs gate05 m2k 4.0/3.5/3.0 -- below, like
     gatep6. Cross probe (c): a fixed policy's >=6 share does NOT move with the opponent's floor (gate05 5.0/4.5/2.4 @f0 vs
     4.5/3.5/4.3 @f7; floor7 1.5/1.8/0.9 vs 1.8/1.4/1.0) -- the "opponent bounds the bank" premise of Path A fails at m2k.
     Run continues to the m5k bar as pre-registered; if it fails there, C with caution (owner order) -- and C's premise
     (the policy's own eagerness is the lever) is the one this probe supports.
  -> L32 (§5cf): **PATH A FAILED.** m5k >=6 share 0.7/0.9/0.5 vs the bar 1.2/1.3/1.0, 3/3 seeds below, own trend DOWN from
     m2450. Regret gate regressed too (0.271/0.2483 vs 0.2291/0.2045 at the same count). Run stopped at m5950, ckpt kept.
     Next arm is C (stronger gate-prior coef) -- BLOCKED on one owner question: floor in or out of C (§5cf.5).
  -> L33 (§5cg): OWNER RULED 10:5x -- C with coef 2.0, floor OUT of C and DEFERRED (not dropped). LAUNCHED 11:20
     (`gatec2_run`, one change vs gatep6). Bars in §5cg.2; m2k screen ~12:25, m5k bar ~14:00 + eval.
  -> L34 (§5ch): m2k SCREEN 3.5/4.4/3.4% (gate05 m2k 4.0/3.5/3.0; gatep6 0.9/0.8/0.5). Coef bites: in-run pi(play) flat
     0.15 (gatep6 0.24). Level suppressed uniformly, shape not learned. Drills 39% = gate05's 38%. m5k bar ~13:55.
  -> L35 (§5ci): owner question (elixir/x-bow/spell trend). MY ERROR: violated the documented PYTHONHASHSEED=0 rule (gates set it,
     ad-hoc runs did not); my first x-bow read this loop is retracted. Matched-m2k card mix: gatec2 SPELL 14.0% /
     x_bow 13.2% vs gate05 21.6/8.0, floor7 25.2/5.3, gatep6 29.4/3.3. Elixir trend not callable yet.
  -> L36 (§5cj): gatec2 m5k -- bar PASSES (2.3/1.7/2.0), caution guards COLLAPSE (regret 0.2924 worst of all arms; wrong
     waits 33 vs gate05's 5). Pre-registered verdict: NOT a pass. Run left going to m10k. QUESTION OPEN: next arm.
  -> L37 (§5ck): OWNER RULED 14:2x -- wait for m10k (rebound chance), then aggro work regardless: aggro_drills -> reach
     fix -> lock-aware, one change each. Base for the first aggro arm decided by the m10k read (§5ck.2 rule).
  -> L38 (§5cl): owner question (spells). New engine-attributed spell probe, validated == cardmix. gatec2 spell share
     14.0 -> 11.6 -> 19.8% over m2450/m5000/m6800 (recovering toward gate05's 28.3); log whiff 73 -> 14 -> 24%;
     tornado whiff 0% at m5k+ vs gate05 9%; rocket ~0 everywhere (my "rocket went up" claim RETRACTED same loop).
  -> L39 (§5cm): m8600 + DISJOINT SLICES. §5cl.3's "recovery" RETRACTED (c): share 14.0/11.6/19.8+19.4/13.7+9.8 has no
     direction; noise band 0.4-0.6pp so the m6800 rise was real and did not persist. ROCKET rose at m8600 (10 and 7
     casts/16 matches, 2.3/1.1% of plays) -- highest measured, partly reversing §5cl.4. Drills + EVAL still climbing.
  -> L40 (§5cn): m10k READ = NO-REBOUND + HELD. Regret 0.2824/0.2805 (bar 0.2418), wrong waits 33/203 (bar 15) -- same 33
     as m5k. >=6 2.7/3.8/2.4% (up). Rule fired: gatec2 STOPPED at m10150 (backed up); AGGRO ARM 1 = gate05 recipe from
     scratch + `sim.aggro_drills: true` launched 17:22 as `aggro1_20260903`. Read at m2k/m5k on the ledger + drill counters.
  -> L42 (§5co): LIVE SPELL AIM FIX shipped (owner-authorized): cast-delay lead for log / rocket / tornado on both live
     paths, gate-after-lead, back-slop 1 tile; `env.spell_cast_delay_s: 1.0` is (b) until measured. aggro1 m2500 first
     look: tank_for_bow 36% (gate05 m5k 12%), bow_lane 0, nado_king 0; >=6 share 2.5/1.0/1.2 (3 seeds).
  -> L41 (§5cn.7, owner 17:3x): **FUTURE ARM "aggro1b" = same flag, `--init data/bench/gatec2_m10k.pt`** -- owner: gatec2
     "produced the best results we've seen of any checkpoint" (a on EVAL 25/20%, crowns 24 vs 8 per 32 matches, x-bow dmg
     1676 vs 676; c on regret/defense). Run AFTER aggro1's m5k read so the flag and the init are separable. Full m10k
     stat sheet vs gate05 m10k in §5cn.7: spell share 11.0/9.0 vs 27.2/27.3; rocket FELL BACK 10/7 -> 4/2 (m8600 rise
     was a wobble, c); tornado 0.20/0.09 per min with 20-27% whiff.

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

## 5x. Session narrative -- RECENT ONLY

Everything before §5cs.43 (2026-09-05 17:1x UTC) lives verbatim in **`HANDOFF_ARCHIVE.md`**, with a
section index at the end of this file. Grep the archive by section id (`§5bw`, `§5cj`, ...). The
sections kept below are the engine era: the real-engine environment, the two PPO pairs, the gate
work, the visualiser, and the verdict.

### §5cs.43 -- L62d (2026-09-05 17:1x-18:1x UTC, owner ask): SIM_VIEW DEBUGGER NOW RENDERS REAL-ENGINE FRAMES (one renderer, two feeds; `sim_view.py` unchanged, 52/52 tests) with the L58 radii overlay, P1 band and term readout intact; **first ground-truth read of the radius table: the engine's reach is CENTRE-TO-TARGET-EDGE, so every drawn ring / reward P-term radius is 0.5-1.0 tiles INSIDE where the engine actually fires** (princess tower first shot up to 8.48 edge / 8.98 centre vs table 8.0; Musketeer 6.53 vs 6.0; Cannon 5.84 vs 5.5); (c) lingering zones are NOT in the bridge's `effects` (23,169/23,169 full frames have effects == projectiles); (a) the L61 recorder dropped every rich per-entity field the bridge exports (target, deploy timer, attack timers, ability state, level) -- a one-line recorder change + re-record recovers them, no bridge work.

Source: `scratchpad/gauntlet/L62/engine_view.md` (agent, STATUS complete); code `L62/engine_view.py`; renders + stills
`scratchpad/gauntlet/ext/engine_view/` (outside git; the owner should look at `00LYPLJLC80L_s1_full_readout_tick1591.png`
and the two mp4s). (a) unless marked.

**A. Owner ask and answer.** "Should the sim view debugger be transitioned to the engine, preserving the radii work?"
Yes: `render_frame` reads the engine through 15 attributes that the L61 adapter already supplies, so the L58 layer
(`_draw_radii`, P1 annulus, `score_placement` readout) runs on engine boards unchanged. Pushback recorded: on the engine
the debugger's job changes from catching OUR mechanics bugs to catching ADAPTER bugs, showing ghost staleness, and
checking `radii_of` against ground truth. Follow-up ask: "can the non-transferring features be re-implemented -- it
does not change mechanics". Correct that it is read-only; corrected the premise that "replay data shows interactions":
the crawl holds commands only, interactions come from the engine's observe, and the observe is bounded by which libg
struct offsets the sandbox bridge reads (`jni_bridge.cpp` ~1278-1420). The buff set (stun/slow/freeze/shield/invis/
rage/souls) needs a new offset hunt in the bridge (sandbox-side C++ + host-hash re-pin) -- a separate task.

**B. Built.** `view_engine_from_frame(frame, focus_side, spec_of)` -> `EngineView` accepted by `render_frame` as is
(30 engine attrs + 19 unit attrs all present -- no getattr default masks a missing field); `render_recording(...)` ->
mp4 (1.74 ms/frame), focus plays scored exactly as `_score_last_placement`, opponent plays as orange diamonds, `?` for
unmapped (0 unmapped over all 211 batch_v2 recordings); `view_engine_from_observe(state)` consumes the bridge's RAW
full observe (target -> attack link, `event_timer_ms` -> deploy_left (inferred), `attack_progress_ms` -> attacking
(inferred), ability_state_code 2/10/11 -> ability tag / cast ring (docs' code table), non-projectile effects -> zones);
spawner children (Graveyard/Witch skeletons, Clone) recovered from name + max_hp. Pixel checks: tower px error **0** vs
`SimMatchEnv.reset()` (1 tile = 1,000 engine units on both axes, anchors coincide); focus_side=1 view is the exact
reflection of focus_side=0; radii overlay changes 5,197 px; a Tesla placement with a real P1 band (threat goblinstein,
band 2.2-5.5, p1 -0.10 p2 +0.50 p5 +1.00) changes 42,603 px. HUD carries a fixed "ENGINE FEED: status/zones/arcs/
abilities not exported" tag. Feature table (rendered / inferred / not exported) in engine_view.md §8.4.

**C. The radius table vs the engine (§6; first shot = new projectile within 1.2 tiles of a same-side body after >= 2 s
idle; Tesla is hit-scan -> read from 220-hp drops, n=26).** Centre-to-EDGE first-shot max minus `radii_of`: princess
tower **+0.48** (8.48 edge / 8.98 centre, n=30; the wiki says 7.5), cannon +0.34 (n=3), x_bow +0.10 (13.04 at a tower =
11.5 + 1.5 tower radius, within 0.06), tesla +0.07, ice_wizard +0.13 (6.94 at a tower ~ 5.5 + 1.5), musketeer +0.53
typical and ONE 8.88-tile shot from `Musketeer@evolution` (b: evo sniper, one shot). Reading: the engine tests reach
centre-to-target-edge, the sim `_gap` convention -- the TABLE is right to 0.1-0.35 tiles for x_bow/tesla/ice_wizard/
cannon -- but the overlay draws and the reward scores the BARE `reach` (centre-to-centre), so rings sit 0.5-1.0 tiles
inside the engine's actual fire point on a Hog/Knight/Golem-sized body; the sim engine additionally adds `_REACH_SLOP`
0.6 the table does not carry. The princess tower's 8.48 is a LOWER bound on acquisition (first shot lands after the
wind-up while the target walks in; b: needs a target-lock export to pin 8.5 vs 9.0). Consequence for the radius-graded
reward and the L58 doctrine: P-term geometry was scored ~0.5-1 tile short of the real game; not changed here (owner's
call, and no arm depends on it now).

**D. What the engine does not export (c/a).** Lingering zones: over ALL 23,169 full frames on disk `effects ==
projectiles`, including frames captured inside the lifetime of 58 graveyard / 57 poison / 184 tornado / 43 freeze /
66 earthquake / 60 goblin-drill / 18 void plays -> the bridge's effect gate (4M category, side in {0,1}, in-bounds)
never passes area effects; a new registry/offset is needed. Zap/Poison/Tornado/Graveyard/Freeze/Rage/Clone/Earthquake/
Void/Mirror/GoblinCurse are never a projectile nor an effect; Log/BarbLog/Fireball/Rocket/Arrows/Snowball/Lightning/
GoblinBarrel ARE projectiles and render. Recorder drop (a): the L61 `snapshot()` kept `[side,x,y,name,hp,max_hp,kind]`
per entity and nothing else, so target/deploy timer/attack timers/ability state/level/paths are exported-but-absent on
disk; proposed one-line change (keep the raw dicts, drop `path_nodes` to stay ~10x smaller) in §8.6, NOT applied (needs
a re-record on the VM). `kind` 14 also flips on 9 old bodies within ~1.5 s of Ice Spirit / Ice Wizard / Log
interactions -> likely "cannot act" (deploying OR frozen/stunned), not only deploying (b; the L61 deploying flag in the
policy obs inherits this).

**Not established:** nothing about live-env rendering (the env agent's frames are not wired to the viewer yet -- next
loop, one call per decision on `EngineMatchEnv`); the evo-Musketeer range; the engine's acquisition radius proper.
Trap: the HUD tag overflows the 460-px canvas -- cosmetic, widen or shorten before the owner reads stills.

### §5cs.44 -- L62e (2026-09-05 17:4x-18:0x UTC, owner order "start the engine training"): FIRST PPO ON THE REAL ENGINE IS RUNNING -- pair launched 17:49:44 UTC from `bc_bias_native_s0.pt` (sha a1273d5d, asserted read-only), control (`--kl_coef 0`, worker PID 31628, direct port 38031) vs KL-to-frozen-init (`--kl_coef 0.3`, PID 54320, port 38032), same seed 41, same ghost-tag sequence, one VM (qemu 54304). **Finding before any policy gradient: the bcA-style critic warm-up (60 critic-only minibatches on the SHARED trunk) moved BOTH arms ~1.15 nats of per-board cell-KL away from the pro init** (control kl_cell 0.95-1.20 at m=48 with raw-logit p99 13.6 vs the init's 6.3; the KL arm recovers to 0.08 within 3 updates once the term enters at update 8). ~12 s/match per arm on an 83-90%-loaded box -> 2,000 matches lands ~00:30-01:30 UTC Sep 6 (not the 2.2 h §5cs.42 extrapolated from the greedy bench). VM left running under the pair.

Source: `scratchpad/gauntlet/L62/engine_ppo.md` (agent, STATUS complete); code `L62/engine_ppo.py` (the file the pair runs is
frozen as `L62/engine_ppo_launched_20260905.py`), launcher `L62/engA_launch.ps1`, PIDs `L62/engA_pids.json`, logs
`L62/engA_{ctrl,kl}_20260905.log`; checkpoints `icebow/data/bench/engA_{ctrl,kl}_m{N}.pt` every 250 + `_latest.pt`
(outside git). (a) unless marked.

**A. What the driver is.** PPONet (PolicyNet + gate + value + value_d; hazard head omitted) loaded exactly as bcA's
`--init` path (`PolicyNet.load_compat`, 0 dropped tensors, gate loaded, VALUE HEAD FRESH -- the init carries c2r's SIM
critic, discarded as bcA did). Rollout 1,024 decisions from ONE `EngineMatchEnv`, episodes span rollouts, tail-caps are
truncations in GAE. Sampling = `masked_logits` semantics, pure policy: no explore floors, no gate prior, no spell
mask/veto, no drills, no distill, no search. Update = GAE(0.994, 0.95), clip 0.2, lr 2.5e-4, ent 0.02 (gate+card),
cell-ent 0.05 -> 0.008 over 3,000 episodes, 4 epochs x 512 minibatch, vf 0.5, grad-norm 0.5, head-norm cap 2.0x,
value warm-up 60 minibatches -- every value read from `bcA_run.yaml`, not `cfg.get` defaults (table in engine_ppo.md
§2.1). KL term = kl_coef x mean over PLAY rows of KL(pi(cell | board, chosen card) || pi_ref), both renormalised over
the card's deployable mask; pi_ref = frozen deep copy of the init, evaluated once per update batched. Rail metric =
pre-tanh cell logits of the sampled card, p99 over the rollout (same quantity `read_ckpt.py` prints). Checkpoint layout
= `train_sim_ppo.save()` + an `engine_ppo` dict; `read_ckpt.py` on `_m0.pt` reproduces the init EXACTLY (v1 15.44/46.61,
v2 15.00/43.51) -- the grading instrument reads these files. Smoke: coef 0 and 0.1, 5 matches each, no NaN.
kl_coef 0.3 chosen from the smoke (|KL term|/|policy loss| 0.025 at update 1, 0.16 at update 2 at coef 0.1) -- (b) a
guess at "about half the policy loss", not a tuned value.

**B. The warm-up drift (the finding).** During the 60 critic-only minibatches the shared trunk is trained on the value
target with no policy loss; the policy heads see a moved trunk. Both arms' kl_cell rose to ~1.15 nats by update 7
before ANY policy gradient. Consequence: the control's starting point for PPO is ~1 nat from the pro prior (bcA had
the same warm-up and ended at 6.47/21.12 -- how much of that fall was warm-up is untested); the KL arm pulls back to
0.08-0.09 within 3 updates of the term entering (kl_term +0.024-0.028 vs pl +0.008-0.014). `engine_ppo.py` now has
`--kl_in_warmup` (default 1); the running pair is `--kl_in_warmup 0` (the agent's kill/relaunch was refused by its
tool sandbox; the lead chose to keep the pair rather than restart: both arms share the drift, kl_coef stays the only
difference, and the drifted control is precisely the bcA-like baseline). Parked arm: trunk-frozen warm-up.

**C. Throughput and box (a, contended -- NOT a benchmark).** Per arm: rollout 27-28 s per 1,024 decisions (policy
4.7 s of it) + update 12 s -> 10-17 s/match (3-4 matches per rollout). Direct transport 38031/38032 (~2 ms/RPC) vs the
adb forward 37031/37032 (~20 ms). RAM: 5.3-5.7 GB free after the VM, **2.2-2.5 GB free after both trainers** (~2 GB WS,
~3 GB private each, not climbing over 10 min) -- below the brief's 6 GB line; recorded, accepted because nothing else
heavy is to be launched (the RE agent is capped at 1 GB). No `--resume`: a stopped arm restarts from m0. Stop runbook
engine_ppo.md §6 (taskkill the 4 PIDs incl. launcher shims 51956/32284, then `worker stop --workers 2 --stop-vm`).

**D. Early state at m=45-48 (descriptive only).** control cum 7W/41L, KL 7W/38L (sampled policy, not greedy; winrate is
not a discriminator); p_play 0.03-0.06 per 0.5-s decision (~17 plays/match, matches the greedy bench's 15.9); pl
+0.008-0.026, vl 0.44-0.68, clip 0.03-0.05; cell_ent control 3.07-3.29 vs KL 3.74; raw_p99 control 13.0-13.6 vs KL
10.5-11.0. Grading at m250/m500 with `L61/read_ckpt.py` (both val sets + rails) is the instrument; expected m250
~18:40 UTC, m500 ~19:30 UTC.

**Not established:** whether the unshaped engine reward is learnable at this cadence (nothing at m=48 says either
way); whether coef 0.3 is the right strength (one value, one seed -- a screen); how much of bcA's fall was warm-up.
Traps: (1) a critic warm-up on a shared trunk IS a policy change -- log KL through warm-up on every future run; (2)
`s/match` under a 2-trainer + crawler + agent load is not comparable with §5cs.42's 1.95 s greedy bench; (3) the agent's
tool sandbox cannot kill processes -- process control stays with the lead (PowerShell `taskkill /PID <pid> /T /F`).

### §5cs.45 -- L62f (2026-09-05 18:1x-18:4x UTC): **THE m250 GRADE SEPARATES THE ARMS AND THE KL ARM IS NOT PINNED** -- control (kl 0) fell to 11.25/32.97 (v1) and 10.95/33.53 (v2) from the init's 15.44/46.61 and 15.00/43.51, i.e. **-4.2 top-1 / -13.6 top-5** in 250 matches; the KL arm (kl 0.3) is at **16.73/44.02 (v1) and 16.28/42.69 (v2) -- top-1 ABOVE the init on both val sets (+1.29 / +1.28) with top-5 essentially held** (-2.59 / -0.82). Arm gap at m250: **+5.48 top-1 / +11.05 top-5** (v1). Plus: the bridge RE (owner-authorised) produced a full offset table and a built, uncommitted-to-deploy v2 bridge exporting buffs and area effects, with a **(c) contradiction of the v1 bridge's core assumption** -- area-effect objects are the 3M global-id series, not 4M, which is exactly why zones never appeared in `effects`.

Sources: this section's grades measured by the lead with `L61/read_ckpt.py` on `icebow/data/bench/engA_ctrl_m250.pt` and
`engA_kl_m253.pt` (deterministic instrument, fixed val sets -- re-running reproduces exactly); RE from
`scratchpad/gauntlet/L62/bridge_re.md` (agent, STATUS complete), artifacts `scratchpad/gauntlet/ext/re/bridge_v2/`.
(a) unless marked.

**A. The m250 grade (the result).**

| arm | v1 top1/top5 | v2 top1/top5 | rails frac>8 / p99 | vs init |
| --- | --- | --- | --- | --- |
| init `bc_bias_native_s0` | 15.44 / 46.61 | 15.00 / 43.51 | -- / 6.3 (train-log) | -- |
| control kl 0, m250 | **11.25 / 32.97** | **10.95 / 33.53** | 0.026 / 9.6 | -4.19 / -13.64 |
| KL 0.3, m253 | **16.73 / 44.02** | **16.28 / 42.69** | 0.015 / 8.9 | **+1.29 / -2.59** |

Reading: the control is reproducing bcA's collapse (15.44/46.61 -> 6.47/21.12 at m2k) on the same trajectory and at the
same early rate; the KL arm is NOT pinned to the init -- it MOVED, and moved toward the pro placements on top-1 while
trading a little top-5 mass, which is a sharpening (rails also lower than the control: p99 8.9 vs 9.6). This is the
outcome named in advance as the interesting one, not a post-hoc reading. **Where the control loses first is the
low-frequency cards:** rocket 1.9/18.9 vs the KL arm's 13.2/32.1, tornado 1.4/5.6 vs 2.8/22.2, skeletons 6.1/19.4 vs
12.2/35.0 -- consistent with a policy contracting onto a few cards/cells that the unshaped reward tolerates.
**Limits, stated plainly:** ONE checkpoint, ONE seed, ONE coefficient. `read_ckpt.py` is deterministic on a fixed val
set, so the numbers carry no instrument noise -- but the across-seed band for a 250-match engine run is UNMEASURED (b),
and a 1.3-point top-1 rise is inside what a second seed could plausibly erase. What is far outside any plausible band
is the 5.5 / 11.1-point ARM GAP. Confirmation is m500/m1000/m2000 on this pair, then a second seed.

**B. RE of the bridge (owner order "reverse engineer the remaining features, you have my permission").** Static work
only, on the §5ax live libg dump (15.535.29, x86_64); no VM touched while the pair trains. Sandbox commit **`81e5dff`**
`bridge: export buffs + area_effects (RE, unverified)` (sandbox's own git, on top of 7c66f92); nothing committed to
ClashBot. Every offset in bridge_re.md cites a function RVA + instruction.
- **(c) The v1 bridge's series assumption is wrong.** Object type is vtable slot 2 (`0xf6dd60: mov eax,3` area effect,
  `0xf7f250: mov eax,4` projectile) and global ids are `type*1M + n`, so **area effects are 3M..4M and 4M is
  projectiles only** (dispatch 0x10b90db/0x10b913b). The bridge gated `effects` on the 4M series -> it was listing
  projectiles a second time. That is the mechanism behind §5cs.43's measurement that `effects == projectiles` in
  23,169/23,169 frames: the two findings, reached independently and by different methods, agree.
- **(c) There is no freeze/stun flag on a character.** The engine folds `HitSpeedMultiplier` / `SpawnSpeedMultiplier`
  over the buff list (0xfb2b00 / 0xfb2bc0); "frozen" IS a buff with -100 multipliers. So the generic buff export is not
  merely convenient, it is the only faithful representation -- a boolean stun/freeze channel would be an invention.
- Offsets (a): character components bitmask +0x30 / array +0x18 / count +0x24, **buff manager = component[3]**
  (getter 0xf852e0); manager vtable 0x196ec68, array +0x18, count +0x24 (ctor 0xfb08f0, update 0xfb0b10, add 0xfb1130,
  remove 0xfb2240); buff instance 0x70 B: +0x00 owner, **+0x08 remaining ms (-1 = permanent), +0x0C total ms**,
  +0x18 data*, +0x28 level, +0x38 instigator, +0x40 instigator side, +0x54 shield hp (tick 0xf78200 does
  `max([+8],50)-50` -- a 50 ms decrement, i.e. one tick). `LogicAreaEffectObject` vtable 0x19691f8, size 0x150,
  ctor 0xf6b410: +0x48 data, +0x78 side, +0x7c/+0x80 x/y, +0xfc level, +0x100 elapsed, +0x114 life override; life =
  `[+0x114]` if >=0 else `data+0x170 + level*data+0x174` (0xdd5ff5). Data columns: buff HitSpeedMultiplier +0xe0,
  SpeedMultiplier +0xe4, DamageReduction +0xc0, Invisible +0x108, Shield +0x140, HitpointMultiplier +0x19c,
  DamagePerSecond +0x1d0, LockTarget +0x200, SwitchTeam +0x220; AEO Radius +0x17c, MaxRadius +0xb8, LifeDuration
  +0x170/+0x174/+0x178, Damage +0x124, HitSpeed +0x118, OnlyEnemies +0x129, ControlsBuff +0x194 (full list §3).
- **What v2 exports**: per character `buffs:[{name, data_id, remaining_ms, total_ms, level, instigator_side, shield_hp,
  flags, hit_speed_multiplier, speed_multiplier, spawn_speed_multiplier, damage_reduction, hitpoint_multiplier,
  damage_per_second, heal_per_second, invisible, lock_target, switch_team, ...}]` + `buff_manager_count`; top level
  `area_effects:[{id, name, side, x, y, level, elapsed_ms, life_ms, remaining_ms, radius, max_radius, current_radius,
  grows, damage, hit_speed_ms, controls_buff, hits_air/ground, only_enemies, follow_behaviour, ...}]` +
  `class_histogram`, `bridge_ext:"buffs_area_effects_v2_unverified"`. ADD-ONLY: existing fields unchanged, new fields
  not hashed (state_hash preserved), compact path gains zero reads, selection is vtable-keyed so a wrong series
  assumption cannot leak junk.
- **Deployment state (important):** `artifacts/libnative_core_probe.so` was deliberately RESTORED to v1
  (sha 82887463..., verified by the lead at 18:36 UTC) because the worker pool's `_service_artifacts_current` hash
  check would otherwise redeploy the bridge and RESTART THE LIVE TRAINING WORKERS on the next `start_service()`.
  v2 (sha 9b63a7a0...) sits in `scratchpad/gauntlet/ext/re/bridge_v2/libnative_core_probe.v2.so`, deployed only by the
  runbook `L62/re_verify_bridge.py` (own remote root, port 37041, refuses 37031/37032/38031/38032).

**C. Verification, NOT run (b throughout).** `L62/re_verify_bridge.py`: `deploy --bridge v2`, `drive` (pool tag
092PPVPCRCPC carries Poison/Tornado/Graveyard/Ice Spirit/Log from both sides; `--synthetic` scripts Freeze/Zap/Rage
because the pool has none), `compare v1.jsonl v2.jsonl` asserting every pre-existing field and the state_hash are
byte-identical. Until that runs, EVERY offset above is static-only: the Name column -> data+0x28 is (b), shield +0x54
as live HP is (b), the tournament-cap branch is unexercised, AEO +0x94/+0x98/+0xac are exported raw with no meaning.
Per-hit events (splash flashes, chain arcs) were skipped by design.

**Not established / traps.** (1) Nothing here says the KL arm's advantage survives to m2000 or to a second seed --
m500 is ~19:30 UTC. (2) The arms share the ~1.15-nat critic-warm-up drift (§5cs.44), so this is a comparison of two
drifted starts, not init-vs-init. (3) Trap recorded: **the worker pool redeploys artifacts by hash on service start** --
never leave a modified `.so` in `artifacts/` while an experiment runs. (4) Trap: a bridge "effects" list validated only
by "is it non-empty" would have passed for months; it was listing projectiles twice.

### §5cs.46 -- L62g (2026-09-05 18:5x-19:1x UTC): **RETRACTION AND KILL -- THE PLAY GATE COLLAPSED IN BOTH ENGINE-PPO ARMS, AND §5cs.45's "the KL arm beats the init" DOES NOT MEAN WHAT IT SAID.** Owner watched `engA_kl_m253` in sim-view and reported it "rarely playing cards"; measured, that is an understatement: **0.12 plays/match vs the init's 36.2 on the same instrument, and its gate probability NEVER crosses the 0.25 deploy threshold (max 0.2326 over 710 decisions)** -- the gate head has gone nearly state-independent and parks just below tau. The pro-agreement metric could not see it: `read_ckpt.py` scores the per-card CELL map conditional on a play, and never touches the gate. Pair KILLED at m=422 (owner's ruling, 19:04 UTC); relaunching with the sim trainer's gate prior restored in BOTH arms.

Measured by the lead this loop with `scratchpad/gauntlet/L62/gate_probe.py` (new) and `clashrl.cli policy-stats`
(16 matches, seed 4242, `--size 432`, greedy, sim); raw JSON `L62/pstats_engA_{kl_m0,kl_m253,ctrl_m250}.json`.
(a) unless marked.

**A. The measurement (one instrument, three checkpoints -- sim, greedy, the deploy rule `sigmoid(g1-g0) > 0.25`).**

| checkpoint | plays/match | p(play) mean / p90 / **max** | frac > tau | affordable cards/decision | elixir at play |
| --- | --- | --- | --- | --- | --- |
| init `engA_kl_m0` (= BC init) | **36.19** | 0.1875 / 0.3073 / **0.6307** | 0.220 | 1.11 (59% have >=1) | 3.61 |
| `engA_ctrl_m250` (kl 0) | 1.12 | 0.0924 / 0.2236 / **0.3440** | 0.036 | 3.75 (100%) | 8.44 |
| `engA_kl_m253` (kl 0.3) | **0.12** | 0.1554 / 0.2325 / **0.2326** | **0.000** | 3.98 (100%) | 9.50 |

The KL arm's p90 (0.2325) and max (0.2326) are the same number to four decimals: over 710 decisions on varied boards
the gate emits a near-CONSTANT, and that constant sits under tau, so greedy play is not rare but arithmetically
impossible. It is NOT a masking artifact -- the collapsed arms have ~4 affordable cards at 100% of decisions (they sit
on capped elixir) against the init's 1.11 at 59% (the init spends). Card diversity died with it: `engA_kl_m253` never
played 9 of its 10 cards in 16 matches; the control never played 6. Human reference (§5cs.41 D, different instrument,
quoted as scale not as a comparison): pro ghosts play **45.1 cards/match**.

**B. RETRACTION of §5cs.45's reading.** §5cs.45 reported the KL arm at 16.73/44.02 (v1) and 16.28/42.69 (v2), top-1
ABOVE the init, and read it as "moved toward pro placements, not pinned". The numbers are correct and reproduce; the
READING was wrong. `read_ckpt.py` measures top-1/top-5 agreement of the per-card cell map GIVEN a card and a board --
it is conditional on playing and never evaluates the gate. It therefore graded the aiming of a policy that does not
shoot, and it would have scored a permanently-waiting policy just as well. **The arm GAP (+5.5 top-1 / +11.1 top-5)
still stands as a statement about the cell heads;** "the KL arm improves on the BC init" does NOT stand as a statement
about play. Trap for the record, and it is the whole reason this was missed: **every conditional metric needs an
unconditional companion** -- agreement without a play-rate readout is not a policy grade.

**C. Cause (b, and it is the lead's design error).** `engine_ppo.py` §2.1 lists, deliberately, "NOT used
(doctrine/scaffold): explore floors 0.15/0.15, gate prior coef 2.0, spell target mask, drills, hazard, distill,
search". The gate prior is not doctrine: `train_sim_ppo.py:340-348, 1758-1772` is a Bernoulli cross-entropy pulling
the GATE HEAD ONLY toward the pro `P(play | elixir bucket, phase)` table that `tools/gate_prior.py` fit from the
crawled replays (`config/gate_prior.json`: schema 1, 519 replays, 23,620 plays; single-elixir p_play 0.063 at 3 elixir,
0.203 at 9; double 0.446 at 9), with play-masked rows excluded and card/cell heads untouched. bcA HAD it; the engine
driver dropped it. So the engine run changed TWO things at once -- the environment AND the removal of the gate scaffold
-- which breaks one-change-per-experiment, and the predicted failure is exactly what happened. Secondary reading (b):
with an unshaped reward and a losing baseline, the immediate return of playing (elixir spent, card dies, counterpush)
is locally negative while the terminal penalty is shared by waiting, so "wait" is a local optimum the entropy
coefficient 0.02 on gate+card cannot hold open.

**D. Kill (owner ruling, "stop and relaunch with the gate scaffold").** State at kill, both arms m=422:
control pl +0.0021 vl 0.4546 ent 0.107 cell_ent 3.524 kl_cell 1.2150 raw_p99 7.55, cum 23W/399L; KL pl +0.0013
vl 0.3790 ent 0.165 cell_ent 3.567 kl_cell 0.0182 kl_term +0.0055 raw_p99 10.39, cum 23W/399L. `taskkill /PID <p> /T /F`
on 51956, 32284 (shims) and their children 31628, 54320. Verified: python processes **7 -> 3**, the three guarded
survivors alive (crawler 29444 + 53824, owner's uvicorn 63608), qemu 54304 UP and reused, free RAM 2.4 -> **8.6 GB**.
Checkpoints kept as evidence: `engA_{ctrl_m250, kl_m253, *_m0, *_latest}.pt`.

**E. The relaunch (agent running).** Same design, ONE difference from the killed run: `--gate_prior_coef 2.0` in BOTH
arms, so `--kl_coef` (0 vs 0.3) remains the only between-arm variable. Same init (sha asserted, read-only), seed 41,
bcA_run.yaml values, warm-up 60, `--kl_in_warmup 0`, rollout 1024, 2,000 matches, direct ports 38031/38032. New
prefixes `engB_ctrl` / `engB_kl` and logs `engB_*_20260905.log` so the killed run's evidence is not overwritten.
New monitoring in the update line (NOT an experimental variable): `p_gate` mean/p90, `frac_gt_tau`, `gp_ce`,
`gp_target`. Deliberately NOT bundled: exploration floors, the critic-warm-up fix, any kl_coef retune, any reward
change -- each is a separate arm.

**Not established.** Whether the gate prior actually prevents the collapse on the ENGINE (that is what engB tests);
whether the collapse also happens with the prior at a lower coef; the greedy play rate of these checkpoints on ENGINE
boards (b -- the probe above is the sim, because the VM was running the experiment under test; the engine's own
sampled `p_play` was 0.028-0.058, which is a DIFFERENT instrument and must not be compared with the sim greedy rate);
how much of the cell-map agreement change in §5cs.45 survives once the policy plays at a pro-like rate.

### §5cs.47 -- L62h (2026-09-05 19:2x-19:5x UTC): **engB PAIR RELAUNCHED WITH THE PRO GATE PRIOR IN BOTH ARMS AND THE GATE IS ALIVE** -- control (kl 0, worker PID 71976, port 38031) vs KL-to-frozen-init 0.3 (PID 46364, 38032), `--gate_prior_coef 2.0` in BOTH so `--kl_coef` is still the only between-arm variable; at update 1 both arms report **p_gate 0.2157, p90 0.3815, frac_gt_tau 0.3208, gp_ce 0.5050, gp_target 0.0784** -- byte-identical between arms, which is the determinism check passing (same init, seed 41, ghost sequence; they can only diverge through kl_coef). Against the killed engA KL arm's frac_gt_tau **0.0000**. Three launch failures fixed on the way, all mine or the launcher's, none the engine's.

Source: `scratchpad/gauntlet/L62/engine_ppo_v2.md` (agent, STATUS complete) for the patch and its offline checks; the
launch, the recovery and the readouts measured by the lead. Logs `L62/engB_{ctrl,kl}_20260905.log`, launcher
`engB_launch.ps1`, preflight `engB_preflight.py`, checkpoints `icebow/data/bench/engB_{ctrl,kl}_m{N}.pt` (outside git).
(a) unless marked.

**A. The patch (agent, 17 exact-string edits to `engine_ppo.py`, 521 -> 627 lines).** `loss += coef *
mean(-(p*log pi_play + (1-p)*log pi_wait))` over rows where the PLAY logit is unmasked (the sim's exact exclusion
`gq_m[:,1] > _NEG*0.5`), target `p = gate_prior.json[phase][elixir bucket]` read BEFORE `env.step()` (which advances
tick and elixir); card and cell heads untouched -- verified by gradient check: `gate.weight |grad| 33.93` with
`card_head.grad None` and `cell_conv[-1].grad None`. Phase from tick: double from 120 s, triple from 240 s (b -- the
4.5 s pre-battle countdown may offset this; identical in both arms). Unit check of the lookup 27/27 PASS
(single/3 0.062606, single/9 0.203290, double/9 0.446343; bucket edges at 2.999 -> 2, 2.9999995 -> 3).
`--gate_prior_coef 0.0` proven byte-for-byte equal to the pre-patch file (18/18 shared log fields identical, all 33
parameter tensors `torch.equal` after 2 updates at kl 0.3). New monitoring on every update line, existing field names
unchanged: `p_gate` mean/p90, `frac_gt_tau`, `gp_ce`, `gp_target`, `gp_rows`. `_m0` reproduces the init EXACTLY
(v1 15.44/46.61, v2 15.00/43.51; all 27 model + all gate tensors `torch.equal` to `bc_bias_native_s0.pt`).

**B. Calibration the brief did not have (agent, (a) from the table itself).** A gate that MATCHES the prior does NOT
sit above tau: over gate_prior.json's own 212,265 windows the mean target is 0.1109 and only **8.14%** exceed
tau = 0.25 -- the largest single-elixir entry in the whole table is 0.2033, below tau. So a healthy `frac_gt_tau`
should FALL from the launch value and settle near **0.05-0.10**, not the BC init's sim-measured 0.22; the alarm line
stays "heading for <= 0.02". What the prior actually restores is STATE DEPENDENCE -- targets span 0.010-0.459, so a
gate that fits them cannot be the constant engA collapsed to. Second finding, deliberately UNFIXED (one change per
experiment): the table is fitted at **dt 0.6 s** while engine_ppo decides every **0.5 s** (`decision_ticks 10`), i.e.
~20% more plays/second than pros; identical in both arms, so it does not confound the contrast. Proposal
`--decision_ticks 12` parked.

**C. The three launch failures (all fixable, none the engine's fault; recorded because each is a trap).**
1. **My `taskkill /T` on the engA trainers killed the two IN-GUEST WORKER SERVICES with them** (`worker status` ->
   `services [false, false]` with `vm_ready true`). The agent could not recover -- its one `worker start` attempt was
   refused by its tool sandbox -- so it correctly stopped and reported instead of guessing. Recovered by the lead with
   the existing `L62/_boot.ps1`; both slots `ready: true` at 19:30 UTC, VM never restarted.
   **TRAP: tree-killing a trainer takes the engine service down; restart it before the next launch.**
2. The launcher's preflight passed a multi-line here-string to `python -c`; Windows argument passing mangled it into a
   syntax error. Moved to `engB_preflight.py`.
3. The preflight then reported "SLOTS DOWN: IndexError" -- it called `NativeRoyaleEnv.observe()` with NO BATTLE
   CONSTRUCTED. The service was healthy the whole time. Rewritten to do what the trainer does (`EngineMatchEnv(port)`
   + `reset(index=0)`); both slots return `obs (96,64,12) tick 90`. **TRAP: a liveness probe that does not exercise
   the caller's own path can report a false death.**

**D. State at launch.** Both arms `--matches 2000 --seed 41 --rollout 1024 --save_every 250 --value_warmup 60
--kl_in_warmup 0 --gate_prior_coef 2.0`; banner confirms the table (519 replays, 23,620 plays, dt 0.6). RSS ~2.0 GB
each, free RAM 3.7 GB, guarded processes verified alive after launch (crawler 29444 + 53824, owner's uvicorn 63608,
qemu 54304). At update 1: pl +0.0370, vl 0.6677, ent 0.272, cell_ent 3.704, kl_cell 0.1195, raw_p99 6.33,
p_play 0.099, s/match 6.76 (uncontended by a second trainer only for that first rollout).

**Not established.** Whether the prior HOLDS the gate open past m=50 (that is the whole point of the run -- the first
real check is frac_gt_tau at m30-50, then m250); whether the collapse would also be prevented at a lower coef; the
tick -> phase mapping; the 0.6 s / 0.5 s dt mismatch's effect on learned play rate; anything about pro agreement
(no engB checkpoint beyond m0 exists yet). engA's checkpoints are retained as the counterfactual.

### §5cs.48 -- L62i (2026-09-05 20:0x UTC, owner claim tested): **(c) CONTRADICTED ON BOTH HALVES -- grid 432 does NOT snap an x-bow a tile back, and switching to 576 would CREATE that failure in 55% of offensive x-bow placements.** Owner: "size 432 is causing the policy to snap one of the offensive x-bow positions one tile too far back... I suggest trying size 576." Measured on all **2,617 real pro x-bow placements** in the crawl, through the same `ActionSpace` the trainer quantises with: the 432 grid's row pitch is **0.499 tiles** (not 1.333 -- the grid spans 19.7 tiles, not 32), backward shift p99 **0.304 tiles**, and for the 240 x-bows actually within reach of an enemy princess tower quantisation adds **0.000 tiles** and puts **0 of 240 out of reach**. At 576 the pitch is **0.374 tiles**, the mean |dy| is **3x worse** (0.289 vs 0.097), and **132 of 240 (55.0%) in-reach pro x-bows are pushed OUT of reach**. The cause is PHASE, not resolution: pros place on the half-tile lattice and 0.499 aligns with it; 0.374 does not.

Measured by the lead: `scratchpad/gauntlet/L62/grid_quant_probe{,2,3}.py` (read-only; no checkpoint, no
running process touched). Source rows `icebow/data/royaleapi/crawl2/plays_ext.csv` (`attr_card == "x-bow"`,
2,617 with positions). (a) unless marked.

**A. The grid is not what its docstring says.** `actions.py:5` calls 18x32 "one cell per board tile". Measured
through `cell_center`, both grids span the SAME box -- columns 1.38..16.57 tiles (x pitch **1.026**, identical at
both sizes, so this claim is about ROWS only) and rows 7.91..27.62 = **19.7 tiles**, not 32. So 24 rows = 0.499
tiles/row and 32 rows = 0.374 tiles/row. The docstring is stale relative to the calibrated `arena_box`; nothing
reads it, but it is what makes "576 = one cell per tile" sound right. **Trap: the 1.333-tiles/row figure that makes
the owner's mechanism plausible does not exist at any grid size.**

**B. Quantisation on real pro x-bow placements (2,617).**

| grid | row pitch | mean abs dy | p99 abs dy | max abs dy | mean backward | backward > 1 tile |
| --- | --- | --- | --- | --- | --- | --- |
| 18x24 (432) | **0.499** | **0.097** | 0.304 | 1.877 | +0.008 | 0.11% |
| 18x32 (576) | 0.374 | 0.289 | 0.340 | 1.815 | **-0.155** | 0.11% |

The 1.87-tile maxima are the same 3 placements at BOTH sizes -- rows outside the grid's 7.91..27.62 span, clamped to
the edge row. Resolution does not fix them and 576 does not either. Everything else is bounded by ~0.34 tiles.

**C. The functional test (the owner's actual claim).** x-bow reach 11.5 tiles centre-to-centre + 1.5 tile tower
radius = 13.0 to tower centre (engine-measured 13.04, §5cs.43); enemy princess towers taken from the sim at
(3.5, 6.5) / (14.5, 6.5) and (3.5, 25.5) / (14.5, 25.5) tiles, the enemy pair chosen as the one on the other half
from the placement (avoids the unestablished blue/red -> side mapping). Of 2,617 pro x-bows, **240 are within reach
of a princess tower** ((b) the other 91% are defensive placements or my 13.0 threshold is too tight -- unverified,
and it does not affect the comparison since both grids use the same subset):
- **432: 0 of 240 pushed out of reach, worst distance added +0.000 tiles.**
- **576: 132 of 240 (55.0%) pushed out of reach, worst +0.340 tiles.**
Mechanism: pro x-bow placements sit on the HALF-TILE lattice (`tile_y` values are all X.5), 0.499 pitch lands on it,
0.374 does not. And because an offensive x-bow is placed AT the range boundary, a 0.2-0.3 tile backward shift is
exactly the difference between hitting the tower and sitting there -- which is why the finer grid is worse.

**D. What IS true, since the owner's observation is real.** The symptom was seen in `sim-view` on
`engA_kl_m253.pt` -- the COLLAPSED checkpoint (§5cs.46: 0.12 plays/match, gate constant, cell head 1+ nat from the
pro prior). (b) The most probable cause is the policy choosing the wrong CELL, not the grid quantising the right one:
at 0.499 tiles/row a ONE-CELL policy error is ~0.5 tiles, which for a boundary-placed x-bow is exactly "sits there
and does not reach". Note the asymmetry this creates: 576 would shrink a one-cell error to 0.374 tiles, but its
systematic phase penalty (+0.155 mean backward, 55% out of reach) costs far more than the 0.125 tiles it saves.
(b) A phase-preserving refinement -- 48 rows at 0.25 tiles/row (864 cells), still aligned to the half-tile lattice --
would give finer control without the phase cost; NOT recommended now, because it changes `n_cells` and therefore
invalidates the BC init, both `bc_pro` val sets and the running pair.

**E. Cost of the proposed change, for the record.** `n_cells` is baked into `bc_bias_native_s0.pt` (432), both
grading val sets, `engine_env.cell_to_engine`, and every engA/engB checkpoint. Switching grids is not a config flip:
it is a BC re-fit plus a new val set plus a relaunch, i.e. the whole IL pipeline. That cost is why this was measured
before it was attempted.

**Not established.** Why only 240/2,617 pro x-bows are in tower reach (threshold or frame; (b) worth a look because
if the frame is off by a row the subset changes -- the 432-vs-576 CONTRAST is robust to it, the absolute 55% is not);
what actually made the watched x-bow fall short (the collapsed checkpoint is the hypothesis, not a measurement);
whether the 3 clamped placements matter in play.

### §5cs.49 -- L62j (2026-09-05 20:1x-20:4x UTC): **engB m250 -- THE GATE PRIOR HELD THE GATE ALIVE IN BOTH ARMS, THE KL ARM'S CELL HEADS ARE AT THE INIT'S LEVEL, THE CONTROL'S HAVE COLLAPSED FASTER THAN engA's -- AND UNDER THE DEPLOY RULE (`sigmoid > 0.25`) BOTH ARMS STILL PLAY ALMOST NOTHING, BECAUSE A PRO-CALIBRATED GATE CANNOT BE GREEDY-THRESHOLDED AT 0.25.** Plus a RETRACTION of the lead's own alarm criterion from §5cs.47 ("frac_gt_tau < 0.02 = falsified"): a gate that matches the pro rate NEVER crosses 0.25 in single elixir, so that criterion would have flagged success as failure. The diagnostic is `p_gate` vs `gp_target` and the p50/p90/max spread, not the tau crossing.

Instruments this loop (all by the lead): `L61/read_ckpt.py` (cell agreement, conditional on a play, deterministic);
`L62/gate_probe.py` (sim, greedy tau 0.25, 3 matches, records p(play) every decision); `clashrl.cli policy-stats`
(sim, greedy tau 0.25, 16 matches, seed 4242, `--size 432`); the engB train logs' GATE readout (engine boards, SAMPLED
policy). Raw outputs `scratchpad/gauntlet/L62/grade_engB_m250/`. Checkpoints `icebow/data/bench/engB_{ctrl,kl}_m250.pt`
(written 20:18-20:19 UTC). (a) unless marked.

**A. Cell-head grade (read_ckpt; conditional on a play -- says nothing about play rate, per §5cs.46 B).**

| checkpoint | v1 top1/top5 (n 1004) | v2 top1/top5 (n 1333) | rails frac>8 / p99 |
| --- | --- | --- | --- |
| init `bc_bias_native_s0` (carried from §5cs.44) | 15.44 / 46.61 | 15.00 / 43.51 | -- / 6.3 |
| engA control m250 (carried, §5cs.45; NO gate prior) | 11.25 / 32.97 | 10.95 / 33.53 | 0.026 / 9.6 |
| engA KL m253 (carried, §5cs.45; NO gate prior) | 16.73 / 44.02 | 16.28 / 42.69 | 0.015 / 8.9 |
| **engB control m250** (kl 0, gate prior 2.0) | **7.47 / 26.79** | **6.83 / 26.86** | 0.027 / 9.8 |
| **engB KL m250** (kl 0.3, gate prior 2.0) | **16.33 / 44.02** | **14.25 / 42.76** | 0.019 / 9.8 |

Arm gap at m250: **+8.86 top-1 / +17.23 top-5** (v1), +7.42 / +15.90 (v2) -- larger than engA's +5.5 / +11.1, and
entirely because the CONTROL fell further (7.47 vs 11.25), not because the KL arm rose. Reading (b): with the gate
prior holding play rate up, the control's policy gradient gets ~4x more play rows per rollout than engA's control did
(p_play 0.05-0.08 vs 0.03-0.06 and falling), so the unshaped-reward drift of the cell heads runs faster -- kl_cell at
m290 is 0.56-0.75 nats (engA control reached ~1.2 by m422). The KL arm sits within noise of the init on top-1
(+0.89 v1 / -0.75 v2) and slightly under on top-5 (-2.59 / -0.75): the per-board KL at 0.3 is doing what it is for --
holding the cell heads at the pro prior (kl_cell 0.04-0.05 nats at m290) -- and NOT (yet) improving on it.
Per-card, the control's losses are again the low-frequency cards (skeletons 1.7, the_log 0.7, knight 0.0 top-1 on v1
vs the KL arm's 9.4 / 23.1 / 11.1). One seed, one coefficient; m500 (~21:15 UTC) is the next point.

**B. The gate is ALIVE in both arms (the thing engB was launched to test) -- but the deploy rule still hides it.**

Engine boards, sampled, from the train logs at m=284-290 (one rollout each, n 875-997 unmasked rows):

| arm | p_gate mean | p90 | frac_gt_tau | gp_target (pro rate on the same rows) | gp_ce | p_play (sampled) |
| --- | --- | --- | --- | --- | --- | --- |
| engB control | 0.058-0.080 | 0.098-0.150 | 0.000-0.012 | 0.090-0.111 | 0.30-0.35 | 0.049-0.067 |
| engB KL | 0.075-0.085 | 0.128-0.157 | 0.000-0.009 | 0.103-0.113 | 0.33-0.35 | 0.068-0.082 |

Sim boards, greedy tau 0.25, `gate_probe.py` (the deploy rule sim-view uses):

| checkpoint | decisions | plays | p(play) mean / p50 / p90 / max | frac > 0.25 | affordable cards |
| --- | --- | --- | --- | --- | --- |
| engA KL m253 (carried, §5cs.46) | 710 | 0 | 0.155 / -- / **0.2325 / 0.2326** | 0.000 | 3.98 |
| engB control m250 | 710 | **0** | 0.161 / 0.152 / 0.201 / 0.245 | 0.000 | 3.98 |
| engB KL m250 | 1089 | **63** | 0.191 / 0.194 / 0.241 / 0.318 | 0.058 | 3.72 |

Two readings. (1) **Not collapsed:** engA's KL arm emitted a constant (p90 = max to four decimals); engB's arms have a
p50->max spread of 0.09 (control) and 0.12 (KL) -- the gate still depends on the board. On the engine, p_gate tracks
gp_target at ~65-80% of the pro rate with gp_ce stable at 0.30-0.35 since update ~6 (a); the prior is holding it
where it was fitted to hold it. (2) **Still catatonic under the rule:** greedy tau 0.25 gives the control 0 plays in
710 decisions and `policy-stats` reads **0.1 plays/match** (control) and **1.5 plays/match** (KL) over 16 matches --
while `gate_probe` reads 21 plays/match for the SAME KL checkpoint under the SAME rule on 3 other matches. That
20x swing between two seed sets of one instrument is the finding, not noise to average: tau 0.25 sits at the gate's
~p92-p95, so the play count is decided by which boards happen to nudge over the line, i.e. by the threshold, not by
the policy. (Do not compare the sim-probe means 0.16-0.19 with the engine-log means 0.06-0.08: different boards,
different opponent, different elixir profile -- two instruments.)

**C. Why this is the deploy rule's bug and not the gate's (c against the §5cs.47 alarm; a on every number).**
`config/gate_prior.json` (519 replays, 23,620 plays, dt 0.6): pro mean P(play) per window **0.111**; the LARGEST
single-elixir entry is 0.203 (9 elixir); double-elixir at 9 is 0.446; only **8.14%** of 212,265 pro windows exceed
0.25. A gate trained to that table is BELOW 0.25 on essentially every single-elixir board by construction -- so
`sigmoid(g1-g0) > 0.25`, which sim-view, policy-stats, gate_probe and the sim trainer's greedy bench all apply, renders
any calibrated policy as "never plays". The BC init only looked active (36.2 plays/match, §5cs.46) because its gate was
MIScalibrated high -- the live-view agent's shadow run of the BC init on engine boards measured p(play) mean **0.47**
with **87%** of decisions above 0.25 (`ext/engine_view/live_selftest_full.json`, 527 decisions) -- four times the pro
rate. So: the owner's sim-view observation ("extremely inactive") is real for engB too, and it is now the viewer's
rule that is wrong, not the policy. **RETRACTION:** the §5cs.47 relaunch note set "frac_gt_tau below 0.02 = the prior
failed". Wrong criterion -- a working prior produces exactly that number. Diagnostic from now on: `p_gate` within ~0.7-
1.3x of `gp_target`, p50/p90/max NOT coincident, gp_ce flat. engB passes all three at m290.

**D. What the rule should be (owner-facing; NOT changed this loop -- doctrine, and sim-view/policy-stats/gate_probe/
live_view/play.py all read it).** Options, each with the number it implies: (1) **sample the gate** (what training
does): expected 0.05-0.08 plays per 0.5-s decision on the engine = ~20-30 plays/match, pro ghosts 45.1 (§5cs.41 D,
a different instrument); (2) **lower tau to the calibrated level** (~0.10, near the pro mean): greedy, deterministic,
but converts a probability into a step function -- at 9 elixir single (p 0.20) it plays every decision it can, at 3
elixir (p 0.06) never, which is not the pro behaviour either (b); (3) keep 0.25 -> catatonic. The lead's
recommendation is (1) for viewing/grading with a fixed seed, and the greedy-cell metric kept for the cell heads only.
`live_view.py` already defaults to `--rule sample` with `--rule threshold --gate_tau` as the option, so the new viewer
does not inherit the bug; `sim_view._policy_agent`, `policy-stats` (cli.py:336-380) and `gate_probe.py` do.

**Not established.** Whether the KL arm's cell heads move ABOVE the init by m2000 (m250 says "held", not "improved");
the across-seed band of any number in A (one seed); the true play rate of these checkpoints under sampling on the
ENGINE with a fresh seed (the train-log p_play is the on-policy rollout, which is the same policy but not a clean
measurement); whether the control's faster cell drift is caused by the higher play rate (b -- the natural test is the
engA/engB control pair at equal play counts, not available). Trap: **any instrument that applies
`ppo_gate_threshold` must print the play rate next to the agreement number** -- policy-stats does (0.1 / 1.5); the
§5cs.45 grade did not, and that is how a catatonic checkpoint was called "better".

### §5cs.50 -- L62k (2026-09-05 20:4x-21:1x UTC): **OWNER RULING ON THE DEPLOY RULE APPLIED -- viewers and graders now SAMPLE the gate (`sim.ppo_gate_rule: sample`, one shared `GateRule`), and under it the engB m250 arms play 17.2 (control) / 24.5 (KL) cards per match on the sim against the init's 36.6 -- the "catatonic" checkpoints of §5cs.49 were the rule, not the policy;** plus the LIVE ENGINE VISUALIZER is published: https://claude.ai/code/artifact/3aca72fa-8f09-40e9-9d59-65c0dc2e03d2 (5,268 engine frames, 527 policy decisions, radii + gate + ghost + term readout; agent's write-up `L62/live_view.md`, STATUS complete).

Owner ruling (chat, 2026-09-05 ~20:45 UTC): *"go with (1) [sample the gate], and if that doesn't work try (2) [tau ~0.10]."*
(a) unless marked.

**A. What changed in `icebow/` (instrument change; the live-play path `play.py` and the sim trainer's greedy bench are
NOT touched -- they still read `ppo_gate_threshold`).**
- New `src/clashrl/gate_rule.py` -- `GateRule(cfg, seed)`: `sample` draws play ~ Bernoulli(sigmoid(g1-g0)) from a
  seeded `torch.Generator`; `threshold` is the old `> ppo_gate_threshold`. Card and cell stay the caller's argmax.
  One implementation, because three greedy copies (sim_view, policy_stats, the cli drill helper) is how §5cs.46 was
  missed. Unit check: p 0.1192 -> sampled frequency 0.1206 over 20,000 draws; threshold path True/False at 0.269/0.231.
- `config/config.yaml` `sim.ppo_gate_rule: sample` (comment block records the why and the readers).
- `sim_view._policy_agent`, `policy_stats`, `cli._drill_policy` read it; policy-stats JSON now carries `gate_rule`
  so a number can never again be quoted without its rule. `L62/gate_probe.py` takes an optional third arg
  `sample|threshold`. `tests/test_sim_view_visibility_i9`: 15/15 OK. The threshold path REPRODUCES §5cs.49 exactly
  (engB KL m250: 63 plays / 1,089 decisions) -- the patch changed nothing on the old rule.

**B. Play rate under the ruling (sim, `--size 432`, seed 4242).**

| checkpoint | policy-stats 16 m, SAMPLE: plays/match | gate held | gate_probe 3 m SAMPLE: plays/match, p(play) mean / p50 / p90 / max, affordable | policy-stats 16 m THRESHOLD 0.25 (§5cs.49) |
| --- | --- | --- | --- | --- |
| init `engB_kl_m0` (= BC init) | **36.6** | -- | -- | 36.2 |
| engB control m250 | **17.2** | 91% | 20.0; 0.089 / 0.085 / 0.139 / 0.302; 2.87 cards | 0.1 |
| engB KL m250 | **24.5** | 83% | 31.3; 0.121 / 0.112 / 0.195 / 0.360; 2.04 cards | 1.5 |

Readings. (1) The rule was the bug: the same two checkpoints go from 0.1 / 1.5 to 17.2 / 24.5 plays per match with
NO change to the policy. (2) The sampled p(play) mean is LOWER than the threshold-run's (KL 0.121 vs 0.191) because the
policy now spends -- affordable cards fall from 3.72 to 2.04 -- i.e. the gate is elixir-conditioned, which is what the
prior fits. (3) The init's 36.6 is not a target: §5cs.49 C measured its gate at 4x the pro rate on engine boards; the
pro ghosts' 45.1/match (§5cs.41 D) is a different instrument (engine, humans) and is quoted as scale only. (4) Under
sampling, `rocket` is the only never-played card for all three (16 matches) -- the card-diversity collapse of §5cs.46
(9 of 10 cards never played) was ALSO the threshold. (5) The 16-match sampled rate is itself a random variable now
(one seed of the generator): quote it with the seed, and treat a few-plays/match difference as noise until a second
generator seed is run (b: band unmeasured).

**C. Discipline note.** m250 was graded under THRESHOLD (§5cs.49) and is now re-read under SAMPLE (this section);
m500 and later will be read under SAMPLE by default, with `gate_probe ... threshold` kept available so any
checkpoint can be put on the old instrument when a comparison to §5cs.45/46/49 is needed. Never mix the two columns.
Fallback per the ruling: if sampling misbehaves for viewing (the owner's call after watching), `ppo_gate_rule:
threshold` with `ppo_gate_threshold` lowered toward the pro mean (~0.10) is option (2), untested.

**D. The live engine visualizer (owner ask §5cs.43 A follow-up: "turn the sim view into the engine artifact, with all
the sim features + radii").** Agent stopped by accident mid-build, restarted from its on-disk state, finished.
- `L62/live_view.py` (58.7 KB): `LiveEngineView.attach(env)` hooks an `EngineMatchEnv` and renders one frame per
  decision through the UNCHANGED `render_frame`; `ProbePolicy` (rules sample / threshold / argmax); `ReplayEngineEnv`
  presents the EngineMatchEnv surface from a recording so the whole wire was exercised WITHOUT a socket (both slots
  are engB's). Self-test (a, replay-shadow): 527 decisions, cell round-trip 62/62 exact, obs (96,64,12) matches the
  sim, 3.35 ms/frame; BC init p(play) mean 0.4723, 86.7% > 0.25 on engine boards.
- Artifact "Engine decision view 00LYPLJLC80L" (3.74 MB, payload embedded): scrub/play 5,268 frames; per decision
  p(play) bar with tau marks, rule verdict, decided-on vs applied-at tick, elixir seen, p(cell), hand strip with costs/
  affordability/queue (hand INFERRED from the L61 cycle rule seeded from the engine queue, 0 mismatches on this
  recording); table ring vs engine fire ring vs sight toggles; P1 band annulus + threat link + 247 term readouts
  (`score_focus_play` on the post-step board); 93 ghost plays in table + timeline + board; phase clock 2x@2401 /
  3x@4801 (a: matches the engine regen 0.36 -> 0.72 -> 1.08/s; (c) sim_view's own HUD label "3x from 180 s" is wrong
  for 180-240 s on the engine -- display-only, not changed); `#tick=` deep link. Verified by a node harness + headless
  screenshots (`ext/engine_view/live_artifact_{check,headless}.json`).
- Parity table `live_view.md` §3. Rendered: board, bodies, towers/crowns/king-awake, elixir, clock/phase, hand, radii,
  fire ring, chosen cell/card, P1 band + terms, gate readout, ghost plays, projectiles. NOT rendered (not exported by the
  deployed v1 bridge): status timers, zones/Tornado/Rage/Log corridor, target links (in the raw observe, not the
  recorder frame), ability/arc events. The v2 bridge (§5cs.45 B) would supply buffs + zones once verified.
- (b) Not yet run live: the `engine accepted / refused` tag is only exercised as `shadow`; a live run reaches the page
  via `--rows` JSON (not yet in `build_payload`). Command (free slot only): `live_view.py live --port 3803x --matches 1
  --policy <ckpt> --rule sample --heads argmax --seed 0 --radii --out ... --rows ...` (`live_view.md` §6).

**Not established.** The across-generator-seed band of the sampled play rate; whether the owner finds sampled
viewing satisfactory (fallback (2) parked); anything live-socket for the visualizer. Trap: **a sampled instrument
must always be quoted with its rule and seed** -- policy-stats JSON now carries `gate_rule` for exactly this reason.

### §5cs.51 -- L62l (2026-09-05 21:2x-21:5x UTC, owner ruling "if the KL run has nothing left to contribute, kill it now"): **engB KILLED at m=602/609. THE VERDICT ON PPO-ON-THE-ENGINE: 500 matches moved the leashed policy NOWHERE (15.44 -> 16.33 -> 15.64 top-1, flat within noise) and destroyed the unleashed one (15.44 -> 7.47 -> 6.87, with a QUARTER of its placement logits railed).** The owner also played the KL checkpoint live and reported "not changed one bit, sloppy placements, wastes cards, worse than a scripted bot" -- the first three are (a) CONFIRMED by measurement and expected by construction; "throwing the match on purpose" is (c) contradicted (no mechanism exists). Engine-PPO as run is closed; the next direction is the owner's new gauntlet.

Instruments: `L61/read_ckpt.py` (deterministic, fixed val sets), the engB train logs, `clashrl.cli policy-stats`
under `sim.ppo_gate_rule: sample` (§5cs.50). Raw output `scratchpad/gauntlet/L62/grade_engB_m500/`,
final log lines `L62/engB_final_state.txt`. (a) unless marked.

**A. The full engB trajectory (v1 sim boards, n 1004; the ONLY instrument that ran on every point).**

| point | control (kl 0) top1/top5 | rails frac>8 / p99 | KL 0.3 top1/top5 | rails frac>8 / p99 |
| --- | --- | --- | --- | --- |
| m0 (= BC init) | 15.44 / 46.61 | -- / 6.3 | 15.44 / 46.61 | -- / 6.3 |
| m250 | 7.47 / 26.79 | 0.027 / 9.8 | 16.33 / 44.02 | 0.019 / 9.8 |
| **m500 (terminal)** | **6.87 / 22.21** | **0.262 / 18.0** | **15.64 / 45.12** | 0.017 / 9.2 |

Two clean results. (1) **The KL leash works and buys nothing.** Three points, 500 matches, and the leashed arm
is statistically indistinguishable from the file it started from (+0.89, +0.20 top-1 vs an instrument whose own band
on a moved checkpoint is 0.4-3.9pp, §5cs L39). It did not forget and it did not learn. (2) **The unleashed arm is
degenerating, and accelerating:** top-1 halved, and the railed-logit fraction went 0.027 -> 0.262 between m250 and
m500 while raw_p99 went 9.8 -> 18.0 -> (train log, m602) **31.25, max 70.6**. A quarter of its per-cell logits are
saturated; that is a policy contracting onto a few cells, not learning placement. Card-level: the control never
plays skeletons (0.0/0.9 on v2), knight 0.6, the_log 4.1. **Interpretation (b, and it is the important one):**
across engA and engB, four arms and ~1,500 engine matches, the unshaped engine reward has not produced a single
measured improvement in pro agreement. The reward, not the algorithm or the leash, is the thing with no evidence
behind it.

**B. Terminal state and the kill (owner ruling ~21:2x UTC).** Control m=602, upd 198, cum 101W/501L, pl +0.0022
vl 0.5340 kl_cell 1.5365 raw_p99 31.25, p_gate 0.0914 vs gp_target 0.1239, elapsed 112.0 min. KL m=609, upd 200,
cum 130W/479L, pl +0.0042 vl 0.4872 kl_cell 0.0617 kl_term +0.0185 raw_p99 8.33, p_gate 0.0988 vs gp_target 0.0945,
elapsed 111.9 min. `taskkill /PID 40540 /T /F` and `/PID 72932 /T /F` (the launcher shims) took their children
56708/71976 and 45856/46364. Verified: python **7 -> 3**, the three guarded survivors alive (crawler 29444 + 53824,
owner's uvicorn 63608), qemu 54304 UP (413 MB), free RAM 2.4 -> **5.0 GB**. Kept as evidence:
`engB_{ctrl,kl}_{m0,m250,m500/m502,latest}.pt` + both logs.
**TRAP (new, cost us the last 100 matches):** `_latest.pt` is written only at `save_every` crossings, NOT
continuously -- `engB_*_latest.pt` are byte-identical to m500/m502 and the weights from m500->m609 are GONE. Any
future driver should write `_latest` every update, or the kill must be timed to a crossing.

**C. The owner's live-play report, tested claim by claim.**
1. *"Has not changed one bit"* -- **(a) TRUE and expected.** See A: the KL arm is its own init. This is the leash
   working as designed, and it is the strongest evidence in the project that PPO is contributing nothing here.
2. *"Placements sloppy, little to no impact, wastes cards"* -- **(a) expected, not a malfunction.** 15.6% top-1
   means the policy does NOT pick the pro's cell on ~84% of boards. We have never had a good policy; we have one
   that agrees with a pro about one time in six. "Worse than a scripted bot" is entirely plausible: a script
   encodes hand-written correct answers, a 15%-agreement network does not.
3. *"It has to be throwing the match on purpose"* -- **(c) contradicted.** No mechanism: the reward has no term
   that pays for losing, and the policy carries no representation of the match outcome that it could sabotage.
   The appearance is produced by an undertrained policy with a value head reset at launch.
4. **Two live-path caveats, both (b) and both mine to have flagged earlier:** live play builds the observation
   from the SCREEN DETECTOR, while every number in A comes from perfect engine/sim state -- a distribution this
   checkpoint has never been graded on; and `play.py` still applies the OLD `> 0.25` gate rule (§5cs.50 changed
   viewers/graders only, deliberately). So live behaviour is not a clean read of the checkpoint. **Unresolved:
   which file the owner loaded.** If it was `engB_ctrl_*` rather than `engB_kl_*`, the observed play was the
   6.87 / 0.262-railed arm, which is far worse than the checkpoint discussed above.

**D. What is now closed, and what is not.** CLOSED: the engine-PPO pair (both arms), and with it the questions
"does the gate prior prevent the gate collapse" (yes, §5cs.49-50) and "does the KL leash prevent forgetting" (yes,
this section). NOT closed and NOT tested: whether a SHAPED or denser engine reward would move agreement; whether a
larger/better imitation corpus lifts the 15.44 ceiling; the distillation-from-rollout-search teacher the owner has
asked for twice (parked, spec in §6-PRIORITY-B); the bridge v2 dynamic verification (both engine slots are free now,
so `L62/re_verify_bridge.py deploy --bridge v2` on port 37041 can finally run); the live-socket run of the new
visualizer (`live_view.md` §6). The lead's recommendation, on the evidence in A: stop spending box time on RL
against this reward and spend it on the imitation side.

**Not established.** Everything in A is one seed and one KL coefficient -- "PPO cannot work here" is NOT what the
data says; what it says is that THIS reward, at THIS scale (500 matches), with THESE two settings, produced no
measurable gain and one degeneration. A shaped reward or a 10x longer run are untested, and the box cost of the
latter is ~4 h/1,000 matches per arm.


### §5cs.52 -- L63 (2026-09-05 22:0x-22:3x UTC, NEW GAUNTLET: "go back to square one, research, propose a new pipeline"): **THE OWNER'S "BC OVERFITS" PREMISE IS (c) CONTRADICTED -- THE BC INIT UNDERFITS: 17.62 / 48.85 top-1/top-5 ON ITS OWN TRAINING ROWS vs 15.44 / 46.61 on val (v1), CE 3.26 vs 3.52; on v2 val is ABOVE train (15.00 vs 14.09).** The model cannot fit the data it was trained on, and the +1.8 pt it holds over the board-blind card histogram (13.65, §5cs.34) is the whole of its board-conditioning. Research fan-out launched (5 agents, all writing to `scratchpad/gauntlet/L63/`); the pipeline proposal is next loop, gated on the owner's answers to five questions (below).

Instruments: `scratchpad/gauntlet/L63/bc_overfit_probe.py` and `mask_probe.py` (the read_ckpt.py scorer applied to
`split.json`'s TRAIN rows as well as VAL; raw output `bc_overfit_probe.out`, `mask_probe.out`). (a) unless marked.

**A. Train vs val, `bc_bias_native_s0.pt`, same scorer as every number in §5cs.44-51.**

| set | rows | top-1 | top-5 | CE (legal rows) | policy entropy H | uniform-over-legal H |
| --- | --- | --- | --- | --- | --- | --- |
| v1 sim boards TRAIN | 5,918 | **17.62** | 48.85 | 3.262 | 3.47 | 5.17 |
| v1 sim boards VAL | 1,004 | 15.44 | 46.61 | 3.521 | 3.48 | 5.17 |
| v2 engine boards TRAIN | 8,111 | 14.09 | 41.92 | 3.586 | 3.49 | 5.19 |
| v2 engine boards VAL | 1,333 | **15.00** | 43.51 | 3.620 | 3.46 | 5.17 |

Generalisation gap: 2.2 pt top-1 / 0.26 nats on v1 (binomial SE ~1.1 pt at n 1,004); NEGATIVE on v2. An overfit
model has a large train-val gap and low train CE; this one has train CE 3.26 nats over ~188 legal cells (entropy
3.47 = ~32 effective cells per decision) and misses the pro's cell on 82% of the boards it was fit on. **The
ceiling is not regularisation; it is that the model+data barely condition on the board at all** (consistent with
§5cs.34: trunk embedding cos 0.991 across pro boards, and the board-blind prior at 13.65).

**B. The action mask forbids the pro's cell on 3.0-5.1% of rows** (v1 train 300/5,918 = 5.07%, val 30/1,004 =
2.99%; v2 4.82% / 3.45%). §5cs.34 attributed the val 30 to "own-tower footprint"; the train rate is higher, and
the cause is untested (b). Whatever the new pipeline uses as its legal-placement mask must be validated against
the pro corpus (target: <0.5% of pro placements masked) before anything is trained on it.

**C. What this changes for the proposal.** "Overfitting" would call for regularisation, augmentation, more data
of the same kind. Underfitting-with-a-near-constant-embedding calls for a different STATE REPRESENTATION and
model (entity/token input with coordinates, not a rendered-board CNN with a tanh-capped cell head) and a
different OBJECTIVE for multimodal placements (a 3.5-nat entropy over 188 cells is what a unimodal head does to
a multimodal target). Both are (b) until the new BC is measured on the same rows. Owner's other premise, "the
architecture has something to do with it", is (a) supported by §5cs.34 (rails, constant embedding) and A.

**D. Loop bookkeeping.** Five research agents dispatched, each writing incrementally to
`scratchpad/gauntlet/L63/{lit_game_ai, cr_prior_art, recent_2025_2026, assets_audit, lessons}.md` (STATUS line
marks completion). Nothing is training; box: python 3 (guarded survivors), qemu UP, free RAM 3.9 GB.

**Questions posted to the owner (report L63, `--questions`), and what each answer does:**
1. Live training in the final layer conflicts with the gauntlet guardrail "do not touch the live-play path"; I
   read the new order as superseding it for the final layer ONLY, at implementation time, after proposal approval.
2. "Forget everything": I keep the DATA (crawl, replays, detector, BC datasets, val sets) and the REAL ENGINE
   SANDBOX as assets; I drop the hand-written sim, its reward, the PPO/DQN trainers and the policy architecture.
   Is the engine in or out as a training/proxy environment?
3. Which checkpoint file was loaded for the live-play session behind the "worse than a scripted bot" report
   (`engB_ctrl_*` = the 6.87 degenerate arm, `engB_kl_*` = the init-equivalent)?
4. Box budget per stage, and whether renting cloud compute for the offline stages is on the table.
5. Grading ladder: may the pipeline use proxy checkpoints (pro agreement WITH play rate -> engine winrate vs
   scripted bots at n>=100 -> live), or must every stage be graded live?

**Not established.** Whether a different model family lifts train top-1 above 17.6 on the same rows (the first
thing the new pipeline must show); the cause of the masked-target rows; anything the research agents return.

---

### §5cs.53 -- L63b (2026-09-05 22:4x-23:1x UTC): **PIPELINE PROPOSAL WRITTEN AND POSTED FOR APPROVAL -- "Square One": obs contract + corpus rebuild -> imitation v3 (entity/patch tokens, full-res cell head) -> corpus x3->x10 via crawler + detector-as-IDM -> engine search-teacher with DAgger-style supervised distillation (no policy gradient) -> live layer (critic-reranked top-k, live matches re-driven in the engine for the teacher). Owner grades live.** Artifact: https://claude.ai/code/artifact/0e57cffe-d199-46c2-b39c-5922032b6821 (source `scratchpad/gauntlet/L63/proposal.html`). Nothing implemented, nothing training; STOPPED for approval.

**A. Research inputs (all `STATUS: complete`, `scratchpad/gauntlet/L63/`):** `lessons.md` (269 lines, 37 measured mechanisms + top-12 constraints), `cr_prior_art.md` (181; every public CR agent incl. Supercell's Boney et al. 2020, SEAT IJCAI-2019, KataCR, YouTube captions), `lit_game_ai.md` (239; ~70 sourced claims), `recent_2025_2026.md` (556; 75 entries Jan-2025..Sep-2026), `assets_audit.md` (308), `cloud_options.md` (163). Owner rulings (L63, `ac74536`) applied: live path may be touched this gauntlet; engine is IN; the live-play report was the KL (init-equivalent) checkpoint; unlimited box budget, cloud if cheap/free; proxy gates allowed, live grading final.

**B. The diagnosis the proposal rests on (all (a), measured in §5cs.34/44-52 -- carried forward, not re-measured this loop):**
1. Representation: BC init 17.62 train / 15.44 val top-1 (v1), +1.8 over the board-blind histogram 13.65, trunk cosine 0.991 across boards; `model.py` has no coordinate input, 12x8 map upsampled to 24x18, tanh-capped head. -> UNDERFIT, board-blind.
2. Signal: 4 engine-PPO arms / ~1,500 matches: KL 15.44->16.33->15.64 flat; control ->7.47->6.87, 26% logits railed. Supercell's own DQN/Q-MC failed; their DAgger-of-search-oracle beat their BC 71.4+-8.8%.
3. Environment: sim 26.1% vs engine 77.7% crowns-match on the same 211 replays; engine deterministic 211/211, ~1,850 matches/h on two slots, accepts 99.2% of pro plays.
4. Live path: 12 W / 957 (1.3%); detector obs never graded; `play.py` gate threshold 0.25; act period 0.76 vs trained 0.6.

**C. Stages and pre-registered gates (all (b) until run):**
- S0 contract/instruments: one obs builder for engine state AND detector output, contract-tested on recorded frames (first engine-vs-live fidelity number); corpus rebuilt from all 613 x/y replays through the engine (v2 used 211 -> ~3x); mask validated (<0.5% pro cells forbidden; §5cs.52 measured 3.0-5.1%); scripted bot ported into the engine; eval harness = agreement+play-rate+board-blind control, engine winrate n=500 vs fixed opponents.
- S1 imitation v3: entity+patch tokens with coords, full-res per-cell head, supervised state-conditioned gate, categorical value head, past-actions channels, mirror aug, "wait for card" action; one ablation (outcome-weighted BC). GATE: train top-1 > 17.6; val > 15.44 + band on 3 seeds; embedding spread >> 0.991; engine winrate >= old init at n=500.
- S2 corpus x3 -> x10: crawler restored; detector-as-IDM precision/recall measured on engine ground truth before labelling video; two-point data-scaling fit.
- S3 search teacher + DAgger: Gumbel-top-k over the student's top 8-16 (card,cell)+wait at STUDENT-visited engine states; each candidate = re-drive prefix (deterministic) + ~15 s rollout; supervised update on pro corpus + search targets. GATE: searched targets agree with pros >= student on 500 pro states; teacher beats frozen student >= 60% (n=500); distilled > student on winrate AND agreement, 3 seeds. ~30 s/decision/slot; 1,000 decisions = 4-7 h on 2 slots.
- S4 live: shared obs builder, sampled gate (`gate_rule`), EMA weights, trained act period; critic-reranked top-k (Best-of-Q/IBRL) with the critic trained from engine + live matches; each live match re-driven in the engine from detected plays so the teacher improves the student on live-visited states. Owner grades in fixed N-match blocks.

**D. Old->new, one line each:** signal PG-on-sparse-reward -> supervised pro + search targets; model rendered-board CNN -> token transformer with full-res head; env 26%-parity sim -> engine with fidelity numbers; data 9.4k -> 28k -> x10; gate learned-from-reward -> supervised state-conditioned + wait action; deploy last-iterate/threshold/single-sample -> EMA/sampled/reranked through one obs builder; measurement single-seed agreement -> agreement+play rate+board-blind, engine winrate n=500 (SE 2.2 pp), 3 paired seeds, gates pre-registered.

**E. Cost.** S0-S2 box only (~1-4 weeks wall). S3 engine-heavy: box 2 slots ~150 decisions/h; GCP $300 trial spot n2-standard-16 nested-virt ~$0.30/h (~16,000 emulator-h) or Hetzner AX162 ~$283/mo -> ~1,000 decisions/h at 16 emulators. Free student compute does not cover an emulator fleet (Azure ~4 vCPU no GPU; NU Quest needs sponsor, no KVM).

**F. Questions posted (`--questions`):** (1) approve / modify the 5 stages; (2) live grading protocol -- proposed 20-match blocks, one fixed mode (trainer / ladder band / friendly), EMA ckpt, no learning during a block -- owner picks the mode; (3) crawler: stalled on expired Cloudflare clearance since 17:16 UTC (294 AuthErrors in `L61/crawl_icebow_wave4.log`, no output since) -- restart it or owner refreshes session; (4) cloud for S3: GCP trial / Hetzner / box-only.

**Not established.** Everything in C is (b). Risks named in the proposal §7: truncated-rollout value quality, engine-vs-live transition gap (no number exists yet), corpus may be too small even at x10, ghost opponents are non-reactive.

**Box.** Nothing training; python 3 (guarded survivors), qemu UP with in-guest worker services DEAD (needs ~73 s reboot at S0 start), free RAM ~3.9 GB (L63 read).

## Archive index (`HANDOFF_ARCHIVE.md`)

- `3.` What is running RIGHT NOW
- `3b.` 2026-08-19 daytime batch (user's five tasks)
- `3c.` 2026-08-19 evening batch — live reward truthing (3db2193)
- `3d.` 2026-08-19 ~22:00 — the "collapsed" PPO was a SCRATCH run (and the log was stale)
- `3e.` 2026-08-19 late — the live-reward batch crashed a real match (and why nothing caught it)
- `3f.` 2026-08-19 night — the advisor, the doctrine wheels, and a warp bug in hogeq
- `3g.` 2026-08-20 — reaction latency, phantom tracks, offense windows
- `3h.` 2026-08-20 late — enemy spells are not threats + the last phantom-cast path
- `3i.` 2026-08-20 — counter validity + the counter table
- `3j.` 2026-08-20 late — the phantom-credit bug, the defensive bow, the LLM out of the reaction path
- `3k.` 2026-08-20 — the king rocket was FREE, and live never paid for the tornado combo (c7aa9c3)
- `3l.` 2026-08-20 — FIVE-TRACK ARCHITECTURE AUDIT (read this before more training)
- `3m.` 2026-08-20 — decision period 1.0s → 0.6s (c328bef). RETRAIN REQUIRED (sim).
- `3n.` 2026-08-20 — why the drill pass rate sat at the random baseline (four root causes)
- `3o.` 2026-08-21 afternoon — THE REAL BUG: PPO training makes the policy WORSE THAN UNTRAINED
- `3p.` 2026-08-22 — THE DRILL EXPLORATION FLOORS WERE THE CAUSE (config shipped)
- `3q.` 2026-08-22 evening — THE POCKET (rule, always on) + the spell mask (strategy, anneals off)
- `3r.` 2026-08-23 — THE WINCON BANK FAILED TWICE, AND ITS REPLACEMENT IS 98% INERT
- `3s.` 2026-08-23 — ALL EIGHT OFFENSIVE BOW WINDOWS SHIPPED, AND THE MEASUREMENT SAYS THEY ARE NOT THE LEVER
- `3t.` 2026-08-23 — DEFENSIVE DOCTRINE AUDIT
- `3u.` 2026-08-23 — W1 REPRICED: the punish window was open 95% of the time, now 39%
- `3v.` 2026-08-23 — ⚠⚠⚠ §3p's UNTRAINED BASELINE DOES NOT REPRODUCE. "Training beats untrained" was never established
- `3w.` 2026-08-23 — --drill-frac 0.0 AND --workers 0 WERE BOTH SILENTLY IGNORED
- `3x.` 2026-08-23 — drill_frac SWEEP: 0.3 IS THE BEST OF FOUR, AND NONE OF THEM BEATS UNTRAINED
- `3y.` 2026-08-23 — THE ADVISOR REASONS CORRECTLY; THE BOARD IT IS SHOWN DOES NOT
- `4a.` 2026-08-24 — THE REWARD HAD NO BACKGROUND CLASS (fix 1 shipped; 2, 3, 4 queued)
- `4b.` 2026-08-24 — THE TWO P(play) NUMBERS WERE NEVER IN CONFLICT, AND THERE IS NO SPEEDUP TO BUY
- `4c.` 2026-08-24 — FIX 1 PAIRED READ AT 650 MATCHES: it changes behaviour, and two of four changes are wrong
- `4d.` 2026-08-24 — "THE RUN DEGRADES AFTER A WHILE" IS NOT WHAT THE DATA SHOWS
- `4e.` 2026-08-24 — ⚠ THE REWARD PAYS FOR DEFENDING THE WRONG LANE (fix 5, QUEUED — do not ship mid-experiment)
- `4f.` 2026-08-25 OVERNIGHT — MATCHED-CONTROL RESULTS (the design this project never had)
- `4g.` 2026-08-25 — FIX 6 SHIPPED: the cheap answer in the OTHER lane was worth nothing
- `4h.` 2026-08-25 — FIX 7 SHIPPED: the missed-defence penalty was a STEP FUNCTION
- `4i.` 2026-08-25 — ⚠ PENDING: CARD LEVEL UPGRADES (apply before the next PPO run)
- `4j.` 2026-08-25 — FIX 1 DROPPED (not deleted). Kept armed behind one config line.
- `4k.` 2026-08-25 — FIXES 4, 5, 6, 7 PORTED TO HOGEQ (2+3 and 1 deliberately not)
- `4l.` 2026-08-25 — CROSS-DECK DIVERGENCE AUDIT (owner asked for both folders 100% current)
- `4m.` 2026-08-25 — PLAY-OUT PORTED TO HOGEQ, AND THE VERIFICATION FOUND A LIVE BUG IN ICEBOW
- `4n.` 2026-08-25 — FIX 2+3 RETRY SHIPPED (unproven), ROYAL HOGS ABREAST, and ⚠ THE LOG IS THE WRONG WIDTH IN BOTH SI
- `4o.` 2026-08-25 — ⚠⚠ THE GATE'S GRADIENT IS INVERTED BY CLIPPING, AND TWO LEVERS FIX DIFFERENT HALVES
- `4z.` 2026-08-27 — THE SPELL CARD VETO SHIPPED, IN THE OWNER'S VALUE FORM (default OFF). RULING 30.
- `4y.` 2026-08-27 — ⚠⚠ THE SPELL EXPERIMENTS: THE SPELLS ARE NET-NEGATIVE, PLACEMENT IS WORTH NOTHING, AND THE SIM'S 
- `4x.` 2026-08-27 — QUEUED EXPERIMENT: EVAL-ONLY ROLLOUT SEARCH (owner's idea, scoped by measurement)
- `4w.` ⏳ PENDING CARD UPGRADE — apply on the sim-parity branch before the merge
- `4v.` 2026-08-26 — ⚠⚠ RETRACTION: "THE LOG'S PLACEMENT IMPROVED" WAS MY OWN MEASUREMENT BUG
- `4u.` 2026-08-26 — THE 40k RUN WAS STOPPED AT 26,600. Reference policy = policy_BEST_m18000_20260826.pt.
- `4t.` 2026-08-26 — ⚠⚠ THE 40k RUN PEAKED AT ~18k AND IS GIVING IT BACK. §4d's "runs never durably improve" STANDS.
- `4s.` 2026-08-26 — THE ROCKET IS NOT A WIN CONDITION: 19% land on a tower, and overtime is reached but never PLAYED
- `4r.` 2026-08-26 — ⚠⚠ SPELL DUMPING IS REAL AND SEVERE — BUT IT DID NOT COME FROM THIS PPO RUN
- `4q.` 2026-08-25 — ⚠⚠⚠ STAGE B: THE CLIP FIX FAILS ITS OWN CRITERION. REJECTED, reverted, NOT in the long run.
- `4p.` 2026-08-25 — SIM PARITY PROJECT OPENED (plan approved; research running, implementation parked until the PPO i
- `§5a` 3x's "the offence has no reachable positive signal" is CONTRADICTED by measurement
- `§5b` The ACTION TAX is dead too: a play is worth +5.45 sigma MORE than a wait
- `§5c` THE CLIP FLIPS THE SIGN OF THE GATE'S LEARNING SIGNAL (504 windows, 34 sigma)
- `§6` LADDER — Model capacity: the escalation order, and why it is LAST not first
- `§5d` The clip sweep: the mechanism was REPAIRED and it bought NOTHING. Ladder advances to the critic
- `§5e` P(play) IS INVARIANT TO THE GATE'S LEARNING SIGNAL (the sweep's missing middle)
- `§5f` THE GATE WAS NEVER COLLAPSED. P(play) over ALL steps is an affordability statistic
- `§5g` /!\ §5f IS RETRACTED. Affordability is 64%, and the trained gate declines 82% of its chances
- `§5h` THE SIGN WAS BACKWARDS ALL SESSION. The policy is TOO EAGER, not too reluctant
- `§5i` Restraint IS separable: AUC 0.667 from a LINEAR probe, and 74% of its plays are over-plays
- `§5j` THE RESTRAINT VETO IS HARMFUL. Declining the teacher's declines is not the teacher's edge
- `§5k` LIVE SEARCH: the blocker was a NET CONTRACT mismatch, and the real lesson is startup-time proof
- `§5l` LIVE SEARCH TIMEOUTS: the cost curve, and why discarding a finished search is dominated
- `§5m` THROUGHPUT: the GPU is not the lever, and --search-interval is nearly free
- `§5n` DRILL + MATCH READ ON THE SEARCH RUN AT m=1600 (and why the comparison is confounded)
- `§5o` INTERVAL-4 RESTART: throughput 2.85x confirmed; the card_ent alarm is an ARTIFACT; banking is the real regress
- `§5p` THE BANKING FAILURE IS DIAGNOSED: waiting is a strictly dominated ACTION CLASS
- `§5q` THE 4-ARM REWARD A/B IS BUILT (icebow only), and two design choices were MEASURED OUT first
- `§5r` INTERVAL-4 RUN CLOSED at m=6800, and the 4-arm A/B is RUNNING
- `§5s` THE A/B DOES NOT NEED 10k MATCHES. The endpoint saturates by m≈800, so the run stops at 1500
- `§5t` locate-anything.cpp EVALUATED AND REJECTED as a YOLO replacement (3 independent blockers)
- `§5u` WORKER-SIDE SEARCH IMPLEMENTED (§5m's structural fix). Mechanism VERIFIED, speedup NOT
- `§5v` m=500 READ: control has NOT collapsed yet, and §5s's saturation claim was CROSS-INSTRUMENT
- `§5w` RoyaleAPI REPLAY MINE: no placements, one player — but it CHALLENGES the "too eager" diagnosis
- `§5x` m=1000 READ: the dose-response APPEARED, and the arm ordering INVERTED. Seeds, not length
- `§5y` THE DEFENSIVE X-BOW BAND IS ALREADY WIRED, IN THREE PLACES, WITH DIFFERENT NUMBERS
- `§5z` A/B CLOSED at m=1500. Control never reached its floor; bank6 held across three reads
- `§5aa` OVERNIGHT CHAIN: throughput measured, parity unresolved-but-not-broken, and the X-BOW ANSWER
- `§5ab` LIVE POLICY PERFORMANCE BRAINSTORM COMPILED FOR HANDOFF
- `§5ab` /!\ THE 3-SEED CONFIRMATION REFUTES §5z AND §5x. The A/B was underpowered by ~10x
- `§5ac` GAUNTLET L1: brainstorm reviewed, response-regret benchmark v0 built, band retune staged
- `§5ad` 3-SEED FINAL: bank_hold is HARMFUL, dose-dependently, at p≈0.005. Band retune APPLIED
- `§5ae` GAUNTLET L2: regret corpus v1 built; the deficit is CONTINUATIONS, not event responses
- `§5af` GAUNTLET L3: canvas_stack 2 is NULL-NEGATIVE at 1500 matches; placement data EXISTS on RoyaleAPI
- `§5ag` GAUNTLET L4: the pro population dataset. Depth of the band VALIDATED, width CONTRADICTED
- `§5ah` GAUNTLET L5: SCRATCH-DEFENSIVE-BOW CONFIRMED AT 3 SEEDS; P4 design committed
- `§5ai` GAUNTLET L6 (hold loop): pro SPELL placement portraits — doctrine largely validated
- `§5aj` OWNER RULINGS EXECUTED: band widened to pro placements; P4 step 1 shipped (+ a design correction)
- `§5ak` GAUNTLET L7: continuation instrument SEES m18000's edge; chained plans cost 2x search
- `§5al` GAUNTLET L8: graphify current (12,018 nodes); PPO run spec posted for approval
- `§5am` GEOMETRY RUN VERDICT: NOT PASSED (1/3), and two SELF-INFLICTED flaws contaminate it
- `§5an` PARITY CLEARED: workers-12 carries the real run
- `§5ao` GEOMETRY REDO: CLEAN FAIL (0/3). Lane spots reverted; centre-only widened band stands
- `§5ap` HAZARD A/B: NULL (1 win / 1 tie / 1 disqualified). THE REAL RUN LAUNCHED 2026-09-01 17:50
- `§5aq` OWNER OVERRIDE: the real run RELAUNCHED 18:18 WITH the hazard head (coef 0.5)
- `§5ar` THROUGHPUT PROFILED: the PPO update was 70% of every cycle; on the GPU the same cycle is 2.9x faster (measured
- `§5as` THE REAL RUN RELAUNCHED ON CUDA, FROM SCRATCH (owner order 2026-09-01 21:2x); the CPU run stopped at m=2700 an
- `§5at` cr-native-sandbox ASSESSED (owner order 2026-09-01 21:2x): real CR engine headless, no renderer; NOT runnable 
- `§5au` cuda real run: both previously unexercised cuda-at-scale paths PASSED (episode 1000 league snapshot, EVAL@2000
- `§5av` sandbox runtime pulled from the owner's BlueStacks (22:26-22:32): engine payload byte-identical to the frozen 
- `§5aw` sandbox smoke on this box (23:05-23:35, owner-authorized "go now"): toolchain/AVD/install/libg load/DataTables
- `§5ax` THE TICK STALL IS SOLVED AND THE FIRST REPLAY->REAL-MATCH CONVERSION RAN (2026-09-01 23:41 - 09-02 00:12): the
- `§5ay` THE WHOLE USABLE SET CONVERTED THROUGH THE REAL ENGINE (2026-09-02 00:20-01:08): 211/268 converted (57 refused
- `§5az` GAUNTLET L1: DETECTOR UPGRADE RECON (2026-09-02 01:20-02:05). The approved isolated venv is probably unnecessa
- `§5ba` GAUNTLET L2: THE PPO CUDA RUN STOPPED AT 18k (its own eval curve says it cost nothing), YOLO26 SMOKE-TESTED ON
- `§5bb` GAUNTLET L3: KITKA FOLDED INTO THE SPRITE BANK, L1's COUNTS RETRACTED (duplicate folder), AND A HELD-OUT SYNTH
- `§5bc` HOGEQ BROUGHT UP TO ICEBOW'S VERSION: parity restored and 5 shared files converged, the LOG AIM ASSIST WAS DEA
- `§5bd` THE HOGEQ CORPUS IS BUILT AND THE DERIVATION HAS STARTED: tools/replay_priors.py, both bias gates passed, and 
- `§5be` GAUNTLET L5: THE SCREEN VERDICT (yolo11s, and yolo26s is slower too), BOARD-27 CANCELLED BY OWNER RULING, and 
- `§5bf` GAUNTLET L6: THE GATE-PRIOR RUN IS LAUNCHED (owner order) -- the pro WHEN-TO-PLAY table, the KL hook in both t
- `§5bg` GAUNTLET L7: THE GATE-PRIOR RUN READ AT m=2000 ON A NEW SAME-INSTRUMENT PROBE -- not yet distinguishable from 
- `§5bh` GAUNTLET L8: COEF 0.1 IS LOSING TO PPO (trainer trend + m=4000 probe), AND THE COUNTERFACTUAL BANK SHOWS THE G
- `§5bi` GAUNTLET L9: THE m=5k READ MOVED TOWARD THE PRIOR (first read below control, all 3 seeds) -- the relaunch orde
- `§5bj` GAUNTLET L10: m=7.5k READ = OSCILLATION, NOT A PULL; coef-0.1 run killed at m=7,575, coef-0.5 run launched (20
- `§5bk` GAUNTLET L11: COEF 0.5 BITES AT m=2k on both instruments; PPO push visibly fighting back; level-16 sandbox ans
- `§5bl` GAUNTLET L12: THE DECISION PATH WAS ALREADY MEASURED -- served cadence 0.76 s against a 0.6 s policy; stage ti
- `§5bm` GAUNTLET L13: owner's two live-play reports tested -- X-Bow at a dead tower; spell whiffs; rocket is dead in t
- `§5bn` GAUNTLET L14: X-Bow defensive doctrine -- tower gate removed, time gate verified against pros and kept, snap +
- `§5bo` owner steering: the overtime flip is a SOFT RAMP, hardening through OT; agent_dt verdict pinned in §6 (2026-09
- `§5bp` GAUNTLET L15: the m=5k wakeup landed early; same-instrument orientation only (2026-09-02 21:15-21:20)
- `§5bq` GAUNTLET L16 (final loop): does the policy know its spell NICHES? Pro reference + engine-truth probe; nado_ret
- `§5br` GAUNTLET L17 (aggro gauntlet, loop 1): what aggro concept the model HAS, measured against the engine; real-gam
- `§5bs` GAUNTLET L18 (aggro gauntlet, loop 2): the engine-backed aggro oracle + tests (2026-09-02 22:20-22:30)
- `§5bt` GAUNTLET L19 (aggro gauntlet, loop 3): do the existing aggro drills grade aggro? (2026-09-02 22:45-23:00)
- `§5bu` GAUNTLET L20 (aggro gauntlet, loop 4): aggro drills graded on the lock state (2026-09-02 23:05-23:45)
- `§5bv` GAUNTLET L21: the m10k read TRIPS the owner's rule; coef-0.5 run STOPPED (2026-09-03 00:55-)
- `§5bw` GAUNTLET L22: diagnosis cut 2 -- the ledger says the reward buys the collapse; the prior is board-blind; the s
- `§5bx.` GAUNTLET L23 (2026-09-03 01:31-01:55) -- the pressure-conditioned gate prior is BUILT, tested, smoke-run, LAUN
- `§5by.` GAUNTLET L24 (2026-09-03 02:45-02:55) -- m2k read of the pressure-conditioned test run: BELOW gate05, 3 seeds
- `§5bz.` GAUNTLET L25 (2026-09-03 03:52-04:25) -- gatep6 m5k read: bar FAILED, tie with gate05; run stopped
- `§5ca.` GAUNTLET L26 (2026-09-03 04:21-04:30) -- aggro wiring built behind two flags, both OFF (commit 39aa80b)
- `§5cb.` GAUNTLET L27 (2026-09-03 04:31-04:48) -- lock-aware predict_targets: built, flagged OFF, graded on the engine
- `§5cc.` GAUNTLET L29 (2026-09-03 06:50-07:05) -- Path A prepared: the opponent cadence knob (sim.bot_attack_floor), sc
- `§5cd.` GAUNTLET L30 (2026-09-03 07:45-07:52) -- owner ruling received; Path A LAUNCHED (floor7_run, from scratch)
- `§5ce.` GAUNTLET L31 (2026-09-03 08:52-09:10) -- floor7_run m2k read: below gate05, and the opponent-cadence premise f
- `§5cf.` GAUNTLET L32 (2026-09-03 10:38-10:52) -- Path A FAILED the m5k bar; run stopped; the prior term is too weak by
- `§5cg.` GAUNTLET L33 (2026-09-03 10:55-11:30) -- owner ruled; Path C LAUNCHED (gatec2_run: gate-prior coef 2.0, no flo
- `§5ch.` GAUNTLET L34 (2026-09-03 12:24-12:30) -- gatec2 m2k screen: gate05's level, 4-5x gatep6; the coef bites, on th
- `§5ci.` GAUNTLET L35 (2026-09-03 13:16-13:35) -- owner question: elixir / x-bow / spell trend. A reproducibility trap,
- `§5cj.` GAUNTLET L36 (2026-09-03 14:04-14:15) -- gatec2 m5k: bar passed, guards collapsed. The pre-registered "not a p
- `§5ck.` GAUNTLET L37 (2026-09-03 14:25-14:40) -- owner ruled: m10k first, then aggro work. Pre-registration of the m10
- `§5cl.` GAUNTLET L38 (2026-09-03 14:55-15:15) -- owner question: spells. A new engine-attributed probe; the spell supp
- `§5cm.` GAUNTLET L39 (2026-09-03 16:16-16:30) -- the 4th spell point kills my own "recovery" reading; the instrument's
- `§5cn.` GAUNTLET L40 (2026-09-03 17:15-17:35) -- the gatec2 m10k gate: NO-REBOUND + HELD; gatec2 stopped; aggro arm 1 
- `§5co.` GAUNTLET L42 (2026-09-03 17:50-19:05) -- the live spell whiff: owner's "mapping issue" contradicted, four real
- `§5cp.` GAUNTLET L43 (2026-09-03 19:10-20:00) -- owner strategic question ("too much scaffolding? GA/elitism?"); the C
- `§5cq.` GAUNTLET L44 (2026-09-03 20:23-21:0x) -- aggro1 m5k gate: FAILED on all three halves; aggro1 stopped; reward b
- `§5cr.` GAUNTLET L45 (2026-09-03 21:05-21:4x) -- NEW GAUNTLET: the sim->live gap. c2r PPO resume launched; live-obs ha
- `§5cs.` GAUNTLET L46 (2026-09-04 07:2x-08:0x) -- overnight: NO loops ran; the c2r gate read (pre-registered): NOT coll

**Housekeeping note (2026-09-05, §5cs.51):** this file was split. `HANDOFF_ARCHIVE.md` now holds
TWO splits -- the 2026-08-29 one (resolved 3x/4x sections) and today's (the old §3 run state, the
§5a..§5cs.42 narrative, and 270 lines of superseded header), separated by a `SECOND SPLIT` banner.
Verified lossless: every line of the pre-split HANDOFF and of the previous archive is present in
one of the two files. Pre-split backup: `scratchpad/gauntlet/L62/HANDOFF_prespllit_backup.md`.
TRAP: the archive file ALREADY EXISTED -- a split script that does `write_text` on it destroys the
previous split. Append, or read-merge first.

### §5cs.54 -- L62m (2026-09-05 22:0x UTC, background task completed unattended; RENUMBERED from
§5cs.52 at 23:2x -- a CONCURRENT SESSION had already claimed §5cs.52/.53 for L63/L63b while this
loop was writing. Two sessions were editing HANDOFF.md at once; see the trap at the end of this section): **THE WAVE-4 CRAWL FINISHED AND THE IMITATION CORPUS IS STILL ONLY ~HALF-USABLE -- 1,253 battles on disk but only 625 (49.9%) carry x/y placement coordinates, and the usable opponent-deck pool is 435, not the 781 the raw battle file suggests.** The owner's bar for the deck pool is >1,000, so the honest gap is 435 -> 1,000, more than double, NOT the "781, nearly there" a naive count gives.

Measured this loop from `icebow/data/royaleapi/crawl2/` (the crawl's own output; no experiment run, box idle).
Crawl log `scratchpad/gauntlet/L61/crawl_icebow_wave4.log`: **"DONE: 565 new replays in 478 min"**, exit 0; the two
crawler processes (29444 / 53824) exited on their own -- the guarded process list is now the owner's uvicorn alone.
(a) unless marked.

| quantity | value |
| --- | --- |
| battles rows | 1,253 |
| replay tags with any plays | 1,237 |
| **replay tags with x/y coordinates** | **625 (49.9%)** |
| play rows total / with x/y | 109,963 / **54,148 (49.2%)** |
| opponent decks, all battles | 781 |
| **opponent decks, USABLE (x/y present)** | **435** |
| usable battles by result | 413 win / 212 loss |

**Why this matters for the next direction.** §5cs.51 ranked "improve the imitation, not the RL" first, and the BC
init that everything failed to beat (15.44/46.61) was fit on ~1,000 pro boards. The corpus can supply more -- 54,148
placement rows now carry coordinates -- but the x/y-less half is the binding constraint on BOTH the board count and
the deck pool, and it has been at ~50% across waves (§5cs.41 recorded the same shape at a smaller scale). **The
cheapest next measurement is not another crawl wave: it is finding out WHY half the replays have no coordinates**
(b -- untested; candidates are the RateLimited errors visible in the log tail, the clearance-renewal path, and a
replay format the parser drops silently). A wave that doubles the battles at the same 50% yield doubles the wasted
half too.

**Not established.** Whether the 565 new replays actually lift the BC fit (untested -- no re-fit was run; the init
on disk is unchanged); whether the x/y-less half is recoverable by a re-parse or needs a re-fetch; whether deck
POOL size or board COUNT is the thing that limits the imitation ceiling (b -- these are different experiments, and
the owner's >1,000 bar is about the pool).

**TRAP (new, 2026-09-05 23:2x, cost a duplicate section number).** Two Claude sessions were live on this repo at
the same time -- this loop closing out L62 while the owner's NEW session ran L63/L63b -- and both appended to
`HANDOFF.md` and `GAUNTLET_LOG.md` and committed. Nothing was lost (this loop's commit `8544985` is verified
purely additive, 37 insertions / 0 deletions, and the L63 commits `9d9a019` / `ac74536` / `21da924` are intact),
but the section number collided and the log blocks are out of order (L62m sits AFTER L63b). Rules for next time:
**(1) before appending a § section, re-read the last section header from disk -- do not trust a number computed
earlier in the loop; (2) never rewrite HANDOFF.md wholesale (read-modify-write) when another session may be live --
append only; a scripted `write_text` would have silently destroyed the other session's work, and in this loop only
an assertion failure prevented exactly that; (3) `git add <named files>` then check `git log --oneline -3` for
commits you did not make before committing.**

