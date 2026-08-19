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

Last updated: **2026-08-18 23:10**, at commit `HEAD` (PPO-beside-YOLO measured infeasible; icebow doctrine research running overnight).

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
Hog Rider 13, Evo Firecracker 13, Mighty Miner 14 (champion), Evo Tesla 14, The Log 14,
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
* **Icebow doctrine research workflow running overnight** (started 2026-08-18 ~23:0x, run
  `wf_2fadd59a-18b`): 18 agents — 7 researchers (recency window Nov 2025+, **Hunter CR preferred
  authority**), up to 8 video watchers (2-at-a-time RAM throttle; <=45 min videos with
  transcript-guided selective sheet reading), 2 adversarial verifiers (misinterpretation +
  recency/conflict lenses — the user explicitly asked for close review of ambiguous statements),
  1 synthesizer -> `icebow/DOCTRINE_RESEARCH.md`. Focus: **Rocket decision procedure** (the
  recurring misuse/non-use complaint) and **defensive plays**. Implementation follows
  autonomously on completion: doctrine.py rocket/defense rules, llm_advisor prompt sharpening,
  llm_doctrine.json regen (port LLMDOC_CPU to icebow's tool first).

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
| `(this)` | **The live advisor told hogeq to play icebow.** `llm_advisor.py`'s prompt opened "ICEBOW deck (X-Bow control)... answer 'hold' and spend NOTHING", `tools/llm_doctrine.py`'s proposer described the icebow cards, `config/llm_doctrine.json` held 72 icebow rules (quiet board at 10 elixir -> Tesla), and `train_rl.py`'s quiet-board branch was HARD-CODED to "find the x_bow or HOLD" — the user-reported passivity, in four places. All four reworked from `DOCTRINE_RESEARCH.md`: pressure-first prompts, a regenerated 19-rule engine-verified table, and the live ladder = Hog at the bridge from 4 elixir -> cheapest cycle from 6 (ability excluded) -> hold only when too poor. | tiny-model probe of the exact reported case: quiet board -> **hog_rider** (was hold); table regen kept 19/27 with measured gains (e.g. quiet+10elx -> mighty_miner **+1.71**, deep_2+7elx -> hog_rider +0.36) |
| `(this)` | **The Hog had no placement rule** — `doctrine_cards` nominated it but `doctrine_cells` explored it uniformly over 432 cells. New branches from the research: hog (bridge column + inner-side tile + arena-edge auto-pig-push, lane picked opposite committed mass / weaker live tower, dead lanes excluded), mighty_miner (ON the tank, tile-exact; deliberate NO-SPOT vs swarms; bridge-punish spots on a quiet board), firecracker (kite band 4th-6th tile staggered to the other lane, behind-line anti-air off the tower column, layered behind a crossing Hog), ice_spirit (Hog escort > defensive freeze > bridge probes), skeletons (centreline dash-kite vs Bandit/Prince/Ram — the video short's tile-exact rule). | 12 new tests (`test_hogeq_doctrine_cells.py`), all green; suites: icebow 371 OK, hogeq back to the 41-failure baseline (+ the royaleapi Cloudflare flake) |
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
* Mighty Miner ability: 1 elixir, **single use, no cooldown**.
* Firecracker evo: `evo_cycles: 2`.

---

## 6. Open work

1. **Retrain BC for icebow with the fixed labels** — existing labels are biased forward 0–3 rows and
   the current policy learned that shift. Steps:
   `run.py label --all --size 432` → `run.py replay-bc --jobs 4` (required; it quantises through the
   same function) → `train-bc --data data/replay_bc --val-frac 0.2 --patience 3`. Then RL from the
   **new** `policy.pt`, not `policy_rl.pt`.
   Current BC set is small: **1,142** replay samples + 39 session samples; one 408 MB session
   (`20260815_222309`) has never been labelled.
2. **Restart both PPO runs** after board-26 — first real test of the reward fix. Train **from
   scratch**, not `--resume`; `--reset-gate` should no longer be needed.
3. **board-26 verdict**: it only replaces board-24-5 if `detect-eval` beats it on
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

## 8. Measurement traps (each of these produced a wrong conclusion first)

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
