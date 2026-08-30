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

Last updated: **2026-08-27**, branch `main` (**RULING 30 + RULING 31c DONE, AND THE PINS GENERATOR
NO LONGER REVERTS ITS OWN RULINGS** -- the spell CARD VETO ships in both decks at
`sim.ppo_spell_min_value: 0.0` = OFF, and the close-out measurement is why it stays off: re-run at
HEAD under the DECK's own venv over 600 paired matches, the owner's VALUE form does **not** beat a
volume-matched RANDOM spell ban (+0.047, 0.98σ) and is measurably **worse** than the body-count
form it replaced (-0.127, 2.99σ). Two confounds were each worth more than the effect under test:
every earlier arm ran under the ROOT `.venv`'s torch 2.13.0+cpu instead of the deck's 2.11.0+cu128
(**-6.0pp winrate on the same seeds, same tree, same checkpoint**), and the random-ban control is
ONE DRAW whose own effect swung +0.301 (4.54σ) to +0.051 (0.76σ) between seed blocks. What
survives: every owner-named single-target reference drill still plays at 0.45, `choose_greedy`
applied NO spell mask before this (eval graded behaviour training never produced), and the veto
now reaches a `--workers 12` run at all -- it was guarded by `and not remote`, which is every real
run. **Ruling 31c**: the Hero Wizard's tornado is 3 tiles, not 4, and spawns at his FIREBALL'S
LANDING POINT (measured dy 0.00 -> 5.00 tiles); the Evo Valkyrie's melee spin is unchanged at
dy=0.00 / radius 5.5. Rulings 31a+31b+31c together move the eval baseline by NOTHING (43.0% ->
43.0%). **Pins**: ruling 31a hand-edited `import_pins.json` without the generator, which would
have silently reverted it plus ruling 31b's two owner-supplied radii -- `gen_pins.py --check` now
exits 1 on any disagreement, with a per-pin report, a run negative control and 4 suite tests.
icebow 1159 OK / hogeq 1182 OK. Previously **ROLLING SPELLS DONE, rulings 20-28** -- The Log and the
Barbarian Barrel now CAST own-half while their corridors still cross the river (a clamped Log reaches
7.60 tiles past it, measured), and a rolling spell SWEEPS instead of resolving its whole corridor in
one frame: the_log 2.88 s, barbarian_barrel 1.35 s, giant_snowball_evo 0.80 s, from a `roll_speed`
that was DEAD DATA -- published in the KB and read by nothing. A body 8 tiles ahead that steps clear
at 1.5 s now takes 0 instead of 266, and one that steps in takes 266 instead of 0. The barrel's
Barbarian appears at the same place but 1.35 s later; the hero's Rowdy Reroll is a literal second
roll that ABSORBS the Barbarian and redeploys the same body healed. The spell-waste verdict had to
move 0.75 -> 3.63 s or every good Log would have been billed for damage it had not dealt yet. A
Barbarian is 716 hp (owner in-game, and the Evo + Hero pages already said so) and the barrel drops a
normal one, 716/190.4/1.4; the barrel's missing crown value had been falling back to its FULL 230,
now 116. 48 new tests (icebow 1091 OK / hogeq 1114 OK), pins 184 -> 195, `parity_check --strict`
fixed from a PRE-EXISTING LF/CRLF failure whose `git diff` was empty. Drill deltas explained and
measured in §5 -- `log_the_barrel_on_landing` fell 100 -> 56 because its reference line is now
0.2-0.5 s LATE, not because the drill broke. Previously **I9 CROSS-CUTTING GAPS DONE** -- the engine had NO own-team spell path at all (`_resolve_spell` iterated `e.team != s.team` in all five branches), so Rage was a bare blast with its whole buff missing, Clone was a 3-elixir no-op and the Heal Spirit did not heal: all three now measured (a raged Knight covers +26.0% more ground, 4 skeletons become 8 at 1 hp and 0 elixir, an ally goes 100 -> 501.00 hp). MIRROR measured and SKIPPED (5/1000 decks, 0.29% of deck weight, and a hand mechanic rather than a board effect). Three engine bugs found and fixed with before/afters: a ZERO-DAMAGE hit woke the enemy King (goblin_barrel / royal_delivery / mirror all activated him at 0.0 s for 0 chip), drills could NEVER present an evolution (0 of 26 icebow / 0 of 24 hogeq, the OPPOSITE of the brief's premise), and a chain hop never survived a physics frame so sim_view showed NOTHING while the Electro Dragon chained for 192/960/1152/576/576. The base Barbarian Barrel now leaves its Barbarian (0 -> 1 body). perception's DRIFT entry was STALE -- measured, the TypeError does not fire in either deck -- and parity's declared-different list shrank 20 -> 18. 62 new tests; head shapes unchanged (icebow 10 / hogeq 11). See conflicts.md's I9 section. Previously **I8 HEROES DONE** -- all 16 LIVE heroes fire ENEMY-SIDE, twelve new `ability_kind` shapes on I7's registry, the 16/3/2026 three-slot loadout (Evolution + Hero + Wild at 1/3, an UNMEASURED choice behind `sim.wild_evo_prob`/`wild_hero_prob`), and `support:` finally consumed -- the opponent's princess-tower share went 54.6% -> 83.7% against a measured 90.5%. THREE I4 import bugs corrected (the turret's stats were on the Musketeer, the Tomb Queen's on the Tombstone, the Barbarian's melee on the barrel). 45 new tests; head shapes unchanged (icebow 10 / hogeq 11), so every checkpoint still loads. See research/sim_parity/conflicts.md's I8 section for 27 evidence conflicts, 4 wrong brief premises, 9 measured bugs, 11 owner in-game checks and 10 deliberate non-implementations -- the two biggest open numbers are the Hero Valkyrie's spin (1358 damage per activation under the per-tick reading) and the Hero Berserker's "Bear Damage". Previously **I7 CHAMPION ABILITIES DONE** -- `ability_kind` dispatch + a 16-field generic ability schema, all 8 live champions firing ENEMY-SIDE through `ScriptedBot._try_ability`, ruling 5's newest-body bug fixed, ruling 7's refund added, the Boss Bandit's HP auto-trigger DELETED, and the Evo Electro Dragon's swing corrected 3204 -> 1152; head shapes unchanged, icebow 890 OK / hogeq at its exact 42-known baseline. See SS5's I7 rows and research/sim_parity/conflicts.md's I7 section for the 12 evidence conflicts, 3 wrong brief premises and 5 owner in-game checks. Previously I5 DATA APPLICATION DONE -- 340 adjudicated ledger rows applied and verified 340/340, 81 pins + 258 curated cards.yaml fields, E4 closed, per-card chain_tiles, stat_sweep --all green in both decks, crown audit RED->GREEN after being RETARGETED at our KB; previously I4 importer hardening DONE -- dry-run-default cards-import, hero scrape, allowlist + pins guards, provenance, crown audit RED negative control, dry-run reconciled 0 surprises; see Phase I progress in SS3's sim-parity block). Previous: **2026-08-25** (DRILLS: the segmented mini-sim framework is in and
validated in BOTH decks -- `sim/scenarios.py` + `sim/drill_env.py` + 4 icebow / 5 hogeq drills, each
measured baseline-vs-oracle, plus `run.py drills` and a `sim.drill_frac` mixing ratio into PPO (default
0.0, so an un-opted run is unchanged). Building it surfaced FIVE real bugs, all fixed, all cross-deck:
the triage gate counted bodies as cards (a lone Skeletons scored 9x the ignore threshold -- the reported
"defends small threats" failure), the Log prior spent itself on those trickles, every spell but Rocket
was forbidden from the enemy half (the whole Hog+EQ combo was an UNREACHABLE action), every legal Hog
send scored -1.0, and the king-activation prior aimed 8.7 tiles from a 5.5-tile pull. See SS5, SS6.0 and
the four new traps in SS8.)

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

1. **Crown damage + user's EQ values — DONE `7bfe6ed`.** Curated overrides in BOTH decks
   (rocket 342, log 35, lightning 264, zap 48, poison 21; EQ 81/49/283 user-read in-game).
   Damage-sensitive suites pass unchanged (they measure relatively, per §8).
2. **Mighty Miner 14 → 15 — DONE `7bfe6ed`.** hp 2979→3269, stages [58/296/594], bomb 531.
3. **Spirit Empress — DONE `4d2ebe5`.** Was a 4-elixir 1798-HP flying hybrid: the 08-14 import
   caught the Fandom page MID-EDIT-WAR. Now two curated forms + ONE deploy choke point picking by
   caster elixir (<3 uncastable, [3,6) ground 3e melee fast ground-only, ≥6 air 6e ranged-5
   flying; exactly 6.0 = air). 10 tests per deck. Mirror rule N/A (no Mirror in sim).
4. **Sim speed — DONE `935350c`, +24%** (3.04→3.77 matches/s), byte-identical fixed-seed digest
   at every step: `__deepcopy__→self` on CardSpec/CardDB/Config (deepcopy was 34% of runtime via
   counterfactual forks), `slots=True` on 6 engine dataclasses (NOT _Zone — custom __init__),
   `card_threat.profile` memoised per-db. Top remaining costs are SEMANTIC (CF rollouts ~0.9s,
   obs building ~26%) — do not "optimise" them without a reward decision.
5. **Pathing — DONE `6c1eec8`.** Both bugs reproduced, measured, fixed from mechanism research
   (game-file Mass/CollisionRadius datamine + April-2025 rework notes + push-mechanics video):
   * STICK: a Hog vs ONE pinned defender dead-centre went from **NEVER (60 s cap) → knight +0.6 s
     / ice_golem +0.8 s / pekka +1.5 s / skeleton_king +1.4 s** over the 6.5 s baseline — mass-
     graded slide, never a latch. Mechanism: walking bodies slide along the contact TANGENT toward
     their target (k = clamp(0.45·m/o, 0.12, 0.9)); attackers hold ground (tested).
   * CRAM: 8-body push **24.7 s → 17.3 s** all-across, worst stall **6.6 → 4.5 s**. Mechanism:
     between two same-team walkers the REAR pushes the FRONT — a follower's velocity is never
     zeroed. The 2026-08-15 stopped-attacker WALL rule is untouched.
   * ⚠ TRAP for the next reader: the Evo-Recruits charge probe misread the flow fix as a
     charge-through-shield bug — two simultaneous 133 swings ≡ one 266 charge hit numerically.
     The probe now isolates the centre recruit. If a damage test breaks after a pathing change,
     check simultaneity before doctrine.
   * 4 regression tests per deck (`test_pathing_flow.py`). Research corpus incl. the datamined
     mass tiers is in the CR pathing report (session log 2026-08-19); `card_mechanics.json`
     already carries per-card mass/collision the engine uses.

## 3c. 2026-08-19 evening batch — live reward truthing (`3db2193`)

Three user reports, all confirmed real:
1. **Live `spell_waste` did not exist** — the spell-impact frame sampler was RETIRED (env.py's own
   note) and spells were paid AT CAST by aim geometry. Now: a pending-impact queue verifies every
   spell against the TEAM TRACKER at impact (tracks bridge the detector's ~31% per-pass misses, so
   a blinked frame can't fake a whiff). Tower-aim exempt on LIVE towers only.
2. **`nado_bad`** (both sims + live-approx): pulled units that survive, wake no king, and end ≥1
   TRUE tile closer to our princess towers = the cast improved the enemy's position. The
   verification caught a real bug pre-ship: normalized-space distance mixes the 18×32 anisotropy
   (a 2.2-tile pull measured 0.9), distances are now per-axis tiles.
3. **The HOLD-despite-enemy-plays gate**: `_needs_answer` read only the latest detector pass →
   a threat blinking out on the decision tick made the board "quiet" (the model FORGOT enemies it
   saw). The gate now triages the tracker's remembered enemies (with_base ported to hogeq),
   deduped against live dets — and the advisor's `_situation` string appends them too, labelled
   "briefly out of sight" (follow-up commit), since the LLM was otherwise still TOLD an empty
   board. **Deliberately NOT counting unknowns** — post-553fe5c they're mostly
   our own cards; recorded so nobody "fixes" it back.
4. **Training wheels ON** (`train.training_wheels`): doctrine aim-correction for all live spells
   (log→corridor, tornado→king-cell else clump, else nearest enemy). CELL-ONLY — the card axis of
   the stored DQN action is never altered, same contract as the existing aim assists.

⚠ CORRECTED (the NOTE inside 3db2193's commit message is WRONG about this): the overnight
icebow PPO spawned its workers 19:39 on 08-19, BEFORE the 21:44 sim edits -- Python imports once,
so that run has NO `nado_bad` anywhere in it, and it has had the crown-damage values since step 0
(committed earlier that day). Nothing straddled. `nado_bad` first applies to the NEXT sim launch;
the live terms (spell_waste-at-impact, wheels, gate memory) to the next train-rl session. Caveat
only if a worker crashes and respawns after 21:44: that worker imports the NEW sim -- check worker
process creation times before comparing per-term stats.

## 3d. 2026-08-19 ~22:00 — the "collapsed" PPO was a SCRATCH run (and the log was stale)

The user saw the evening PPO's winrate "collapse". Findings, all verified from checkpoints:
- **`data/ppo_percard.log` stopped 08-17 17:28** — everything read from it about the evening run
  (including the "19k matches, ladder 9%" I sent to Discord) described the Aug-17 run. Tonight's
  run logged only to its console. **Tee future runs to a file.**
- **Tonight's 19:39 launch had NO `--resume`/`--init`** (verified from the process command line) —
  it trained FROM SCRATCH, reached 3,016 matches, banked ladder-avg 12.2% @1500, and **overwrote
  `policy_sim_ppo.pt` + `policy_sim_ppo_best.pt`**, clobbering the Aug-17→19 warm lineage's end
  state (no backup of it exists). Rollout winrate is curriculum-pinned near ~30% BY DESIGN
  (difficulty rises whenever the window beats it) — judge runs by the `EVAL @` avg-5 lines only.
- **`policy.pt` (BC, Aug 17) is `in_ch: 3`** — the sim needs `in_ch: 12`, so `--init data/policy.pt`
  silently falls back to scratch (shape gate). A BC warm start needs BC re-run on the 12-channel
  canvas first.
- **Strongest surviving compatible checkpoint: `policy_sim_ppo_best_win40_14300.pt`** (Aug 16,
  banked ladder avg-5 33.2%, in_ch 12/thr 52/gate present, heads measured healthy: card-head norm
  0.09, gate absmax 0.90 — no `--reset-gate` needed). Recommended restart:
  `run.py train-sim-ppo --matches 800000 --envs 96 --workers 12 --size 432 --init data\policy_sim_ppo_best_win40_14300.pt`
- **Fix (both decks): value warmup now engages on `--init` warm starts** (`warm_loaded`), not just
  resume — before, a RANDOM critic trained alongside a warm policy from minibatch 0, the exact
  hazard class of the 2026-08-14 head-sharpness incident.

## 3e. 2026-08-19 late — the live-reward batch crashed a real match (and why nothing caught it)

User ran `train-rl` (icebow); it died mid-match at `float(value)` in reward_stats.add.

- **icebow:** `self.w_spell_waste_live = ("spell_waste", -0.3)` — the reader call had lost its
  function name in patching, so the weight was a TUPLE. The detection worked perfectly; billing
  the FIRST TRUE WHIFF is what crashed. Live env.py's reader is `rw`, defined ~55 lines BELOW
  where I put the reads.
- **hogeq:** same lines read `r(...)` — a name that exists nowhere in live env.py. Its live env
  would have raised NameError on construction: `train-rl` was 100% broken there, undetected.
- **Both weights now live in the `rw()` block** with every other reward weight.
- **Third bug, found while auditing:** `reset()` never cleared `_pending_spells`, so a spell cast
  in a match's closing seconds came due during the NEXT match and was judged against its empty
  opening board — a guaranteed phantom whiff billed to a match that never cast it. Fixed.

**WHY THE 16 TESTS MISSED IT: no test constructs the live `MatchEnv`.** It needs a window and a
detector, so every test in both decks uses `SimMatchEnv`; the live wiring had never executed. The
new `LiveEnvInitLintTests` lints the SOURCE instead (AST): no `self.w_*` may be a container, no
function may call a bare name unbound in local+module+builtin scope, both spell weights must come
from a reader call, and `reset()` must clear the queue. **Verified non-vacuous** by re-injecting
both shipped bugs and confirming each test fails (`scratchpad/verify_lint_catches.py`).
Building the lint exposed a bug IN the lint: `ast.walk` for module scope descends into function
bodies, so a local `r` inside `_wheels_spell_aim` masked the very NameError being checked — module
scope is now collected from top-level statements only.

Suites after: icebow 427 OK, hogeq 42 (its documented baseline; none from these files).

## 3f. 2026-08-19 night — the advisor, the doctrine wheels, and a warp bug in hogeq

**The advisor (`b07b983`).** User: "the advisor keeps timing out which causes the model to play
randomly." Both halves confirmed, two independent causes:
- The single-card answer was a JSON object (`{ "card": "tornado" }` = 10 generated tokens at ~44
  ms) -> p50 **0.855 s** against a 0.90 s budget. It was losing by 20 ms. Reproduction: **0 of 15**
  calls answered. Bare card name (3 tokens) -> p50 **0.492 s**, **15 of 15**.
- The circuit breaker was PERMANENT (`disabled=True` for the session). At a ~40% timeout rate five
  in a row arrives immediately, so every later exploration step was a uniform-random card. Now a
  cooldown (30 s, doubling, 300 s cap) that any single good answer clears.
- **The prompt's last line is load-bearing** — scored on tools/llm_eval.py's 13 engine-verified
  cases: `"Answer with the card name only."` **11/13**; `"...or hold."` **3/13** (holds 11x);
  nothing appended **0/13**; the old JSON schema **7/13**. Shipped the 3/13 wording first and the
  eval caught it. A top-level string enum was fast, "valid", and answered `hold` 12/12 — latency
  alone would have shipped a bot that never plays.

**Doctrine wheels for the defenders + the buffer fix (this batch).** Already wheeled before:
x_bow lane/lock/depth, tesla centre-pull, rocket weaker-tower/pump/intercept (unconditional,
predating the flag), plus 08-19's spell wheels. Added: `_wheels_troop_aim` for **knight**
(bodyguard one row in front of the bow on the threat's side; body-block between attacker and tower
when no bow is out), **skeletons** (onto the attacker), **ice_wizard** (behind and offset, out of
one spell radius with the bow) — mirroring sim `_bow_defence_cells`, geometry derived from the real
tower anchors, king-footprint guarded, and a one-cell tolerance so a placement the model already
got right is left alone.

⚠ **THE PREREQUISITE, do not undo:** `train_rl` stored the action the POLICY chose while `env.step`
executes a doctrine-corrected CELL. That teaches backwards — the model's bad cell gets credited
with the corrected cell's reward, so it learns the mistake was right and the wheel can never come
off. `env._last_exec_action` now carries the executed action and the replay buffer stores THAT
(Q-learning is off-policy, so this is the correct form). This affected the pre-existing rocket/xbow
/tesla assists too, for as long as they have existed.

**hogeq's `coords_to_grid` never got icebow's warp fix.** Measured: round-tripping every cell
through `cell_center -> coords_to_grid` mismatched **412 of 432** cells in hogeq, **0 of 432** in
icebow. hogeq still rescaled the arena box LINEARLY while `cell_center` maps through the
perspective warp. Everything that turns a POINT into a CELL goes through it — the labeller (human
tap -> training cell) and every aim assist — so **hogeq's recorded demonstrations were stored ~2
rows toward the enemy end of where the human actually tapped, and its aim assists landed short by
the same amount**. Fixed (now 0/432). Consequence worth acting on: hogeq BC data labelled before
this is systematically shifted, so a re-label (or re-record) is the honest next step there.

Suites: icebow 450 OK, hogeq 42 (unchanged baseline — the warp fix added none).

## 3g. 2026-08-20 — reaction latency, phantom tracks, offense windows

User: reactions land 4-5 s late (hog reaches the tower first); false positives on the allied side
whiff spells into random tiles; and the model needs offensive windows, not all-game defence.

**Latency.** The healthy chain is ~1.3 s (10 Hz perception → event wake → 0.5 s advisor → act).
The 4-5 s sessions were the DEGRADED chain: the perception thread dies silently → `_detect_enemies`
falls back to 1 Hz synchronous detection with nothing in the log → motion classification needs
seconds → (pre-`b07b983`) the advisor burned another 0.9 s timing out. Fixes:
- `PerceptionLoop.ensure_alive()` — a dead loop restarts itself and SAYS SO; `_detect_enemies`
  warns (rate-limited) on a dead loop or a stale snapshot instead of silently degrading.
- The wake event now also fires on a **fresh first sighting** (track hits == 1) at gy ≤ 0.50 of a
  card we don't own — placement IS the commitment; waiting for the classifier ("enemy" needs
  motion_min = 0.05 of net march) cost 0.3-0.7 s per reaction.
- Found while testing: an unowned card deep in OUR half classifies enemy on FIRST sighting via
  the deck veto — Miner/Barrel-style materialisations already wake with zero classification delay.
- **Per-match health line**: `[perception] running/passes/wakes` + `det_age` in the cadence line.
  passes ≈ hz × seconds when healthy; det_age near act_period = blind-between-decisions again.

**Phantoms.** Confirmed the user's guess: a 1-frame false positive classified by side-prior or a
bar misread became an enemy TRACK served for forget_s = 4.5 s → gate opened → spell wheels aimed
at it → whiff into grass. Now: tracks carry `hits`; `enemy_tracks` serves only ≥ `min_hits`
(**observation.team_track_min_hits: 2**, ~0.1-0.2 s corroboration at 10 Hz), dets carry
`d.trk_hits`, and `_needs_answer`'s live-det path requires ≥ 2 (default 2 when unannotated).

**Offense.** The quiet-board pressure rule (bow at 6+) lived on EXPLORATION steps only — a greedy
model at 10 elixir just leaked. New leak-guard wheel (**train.offense_leak_guard: 9.5**): a greedy
WAIT on a quiet board at ≥ 9.5 elixir becomes the pressure play (icebow X-Bow, hogeq Hog at the
bridge) — the punish/outcycle/second-bow window. The ONE sanctioned wait→play conversion; sound
only because the buffer stores the EXECUTED action (a683d46). Defence always outranks it
(needs_answer suppresses).

16 new tests per deck. Suites: icebow 466 OK, hogeq 42 baseline.

## 3h. 2026-08-20 late — enemy spells are not threats + the last phantom-cast path

- **Enemy spells ignored everywhere** (user rule: "nothing can be placed to counter a spell"):
  `enemy_tracks` never serves a non-spawn spell (so our spell wheels can't aim at THEIR spell and
  a rocket landing near their zap no longer dodges its whiff bill), the threat gate skips spell
  dets, and `_situation` never describes them to the advisor. Exception `SPAWN_SPELLS =
  {graveyard, goblin_barrel, royal_delivery}` — those land units and demand answers.
- **The remaining hallucinated casts had a measured path**: live_20260819_230129 shows tornado
  casts at board mass 0.009 (empty screen) with raw_cell == cell — the CHOICE was the
  hallucination, and it came from `_situation`, which had NO trk_hits filter (the gate got one
  earlier, the advisor string didn't). A 1-frame phantom was described, the advisor answered
  "tornado". `_situation` now requires trk_hits ≥ 2.
- **Static-phantom demotion** (`observation.team_phantom_stale_s: 6.0`): a misdetected decoration
  re-sights every pass so min_hits never kills it, and the deck veto reads it enemy forever. A
  REAL enemy deep in our half (y > 0.55) marches or takes tower fire (bar evidence within
  seconds); a track that has done neither for 6 s stops being served. Their side is exempt
  (buildings legitimately stand still and unhurt).
- The Karpathy-skills repo (multica-ai/andrej-karpathy-skills) was inspected, NOT installed:
  third-party name-squat packaging four generic coding maxims as AI instruction files; nothing
  technical to integrate, and third-party instruction files don't get vendored into this project.

12 new tests per deck (spell serving + spawn exception, static demotion with all three escape
hatches — march/bars/their-side — situation filter). Suites: icebow 478 OK, hogeq 42 baseline.

## 3i. 2026-08-20 — counter validity + the counter table

User: "the advisor is suggesting unrealistic counters... knight on a balloon (knight can't even
see the balloon) or rocketing wall breakers (a horrible elixir trade)."

**The veto (`65fda67`), `threat_value.pick_invalid`** — both failures were ALREADY forbidden in
the advisor prompt IN WORDS and shipped anyway; same lesson as the triage tier (52a238e), so the
rule is KB code:
- `can_touch`: an ALL-flying group needs an air-attacker, tornado (repositioning air is the
  answer), or a non-ground-only spell. `the_log` rolls, `earthquake` shakes the ground — neither
  reaches a balloon. A MIXED group never vetoes a ground card.
- `trade_sane`: a SPELL costing 3+ more than the whole group it erases is a losing move (rocket 6
  on wall_breakers 2). Troops are never trade-vetoed — which is why **skeletons stay a legal wall
  breakers answer with the tower helping** (user's note, pinned by a test).
- LIVE: vetoes the advisor's pick, falls back to the doctrine/cheapest-valid answer, never random.
  `_needs_answer` split so the triaged group is computed once and shared with the veto.
- SIM: `doctrine_cards` filters nominations at BOTH exits; offensive nominations exempt.
- MEASURED on tools/llm_eval.py (+3 cases for the reported bugs): old prompt **13/16** and it
  answered the balloon case with `the_log` — the user's bug reproduced in the harness; new prompt
  **14/16** (balloon→tesla, wall_breakers→the_log). The remaining miss (three_musketeers: rocket
  vs tornado) is the known nado→rocket ordering item, not a regression.

**The table plumbing (`a363a87`), `clashrl/counters.py`** — rows are threat_cards → ordered
respond[{card, when, where, note}], looked up combo-first (an exact combo beats its parts; a
superset push still finds it), filtered to what is in hand. Consumers: advisor-vetoed → doctrine
answer; **advisor-silent → doctrine answer instead of a uniform-random card** (the measured cause
of the "plays randomly" sessions); sim `doctrine_cards` nominates the same rows at 5.0/4.0.
Data lives in `config/counters.yaml` (`train.counter_table`); first row for a key wins so a
hand-written override survives a regenerate. **No table shipped yet** → empty table → every path
keeps its previous behaviour.

**DONE (`0aad2c0`): 108 researched rows per deck** in `config/counters.yaml`. 17 agents, 178
entries from deckshop / the CR wiki API / reddit guides, covering all 131 cards + 38 meta combos.
The `where`→wheels mapping shipped in `1ea0cc6`.
- Highlights: balloon→tesla PRE-PLACED centre (never knight); wall_breakers→the_log then
  **skeletons at_tower** (the user's own note, found independently); lavaloon→ONE mitigation row;
  graveyard→ice_wizard pre-placed ON the tower; three_musketeers→**tornado then rocket** (the
  ordering the eval wanted); hog→tesla 4-3 centre. 16 icebow rows are `mitigation: true`.
- ⚠ icebow's adversarial agent DIED on a session limit → I ran that audit locally
  (`scratchpad/local_audit.py` pattern): 1 hard fail (rocket on a lone elixir_golem), 0 mechanics
  contradictions. hogeq's agent passed with 7 corrections.
- Two bugs the audit exposed, both fixed: `lookup()` broke ties by DICT ORDER (a golem+firecracker
  push could answer the firecracker) → rows now carry `danger` and the most dangerous match wins;
  and the sim's table nominations at 5.0/4.0 OVERRODE the hand-written rocket gates (two existing
  doctrine tests caught it) → now 2.5/2.0. **Hierarchy: measured doctrine > researched table >
  uniform floor.** Do not raise those weights.
- Regenerate: `python tools/counters_build.py <research.json> --deck <deck>`. First row for a
  threat key wins, so hand-written overrides go ABOVE the generated rows.

Suites: icebow 527 OK, hogeq 42 baseline.

## 3j. 2026-08-20 late — the phantom-credit bug, the defensive bow, the LLM out of the reaction path

**Why `spell_waste` stopped firing AND whiffs still paid (`5b04c17`).** ONE mechanism, and it was
my own 08-19 fix biting back: the tracker BRIDGES a track for `team_forget_s` (4.5 s) so a real
unit blinking out is not forgotten — and a FALSE POSITIVE is remembered exactly as long. A
rocket's whole flight is ~1 s, so at impact the phantom was still "inside the blast" → no whiff
billed → and the credit `_wincon_exec_live` paid at cast STOOD. **The model was being taught that
casting at ghosts pays.**
- Verdicts now run on FRESH sightings only (`env.spell_verify_fresh_s: 0.8` — still several 10 Hz
  periods, so real 1-3 frame gaps are bridged). `enemy_tracks` grew `max_age`; memory callers
  (threat gate, `_situation`) are untouched.
- A whiff HANDS BACK the at-cast credit (`spell_waste_clawback`) → a whiffed spell is strictly
  negative.
- **`[spell]` log line per impact**: aim, radius, `N fresh, M remembered`, and a `PHANTOM` marker
  when only memory saw the target. This is the line that separates "detector false positive" from
  "model casting at nothing" — read it before diagnosing further.

**Defensive bow / "a back build is not a quiet board" (user).** `_needs_answer` only triaged OUR
half, so a golem assembling behind their king read as quiet and the loop hunted for PRESSURE —
which is how the leak-guard fired an offensive bow into a push already paid for.
`threat_value.massing_in_back` (shared): real elixir at/behind their princess line (y ≤ 0.28) AND
nothing on our half (y > 0.42). On that board: the gate says answer, the wheel plays the bow into
the back-centre band, **env.step SKIPS its forward lane/lock/depth snap** (that snap is what makes
a bow offensive), the sim doctrine aims the same spot ABOVE the phase flag, and the prompt says it.

**Reaction latency, part 2** (perception healthy, det age 0.07 s). The loop is
`choose(obs) → execute → wait → observe`, so the advisor's ~0.5 s sits between seeing a threat and
tapping. Defence decisions now consult the **counter table first** (dict lookup, and measurably
more accurate) and skip the LLM on a hit — **75% of answerable meta threats covered (66/88**;
spells and triage-ignorable cards excluded, since neither should be answered). Gaps still go to the
advisor. `react_min_gap` 0.30 → 0.15 (it is slept BEFORE the event is checked = a hard floor).
⚠ Uncovered-but-answerable, worth a follow-up research pass: berserker, electro/ice/fire/heal
spirits, knight, goblins, mini_pekka, and enemy buildings (tesla, bomb_tower, furnace, goblin_cage).

**Latent bug found on the way:** hogeq's `PerceptionLoop.enemy_tracks` never got the `with_base`
port — the gate calls it with `with_base=True`, raising TypeError, swallowed by the gate's own
except. **hogeq's threat-gate memory has been inert whenever its perception loop runs.** Fixed.

Suites: icebow 543 OK, hogeq 42 baseline.

## 3k. 2026-08-20 — the king rocket was FREE, and live never paid for the tornado combo (`c7aa9c3`)

**"It learned to rocket cycle the opponent king tower."** Chip on the king was ALREADY off and was
never the payoff — `_chip_progress` slices `[:2]` in both envs and live does not even read the
king's HP (`enemy_tower_hp_boxes` has 2 boxes). **Measured: a king rocket scored exactly 0.0.**
Zero was the bug — not a reward, but not a cost, while it dodges the leak penalty, so it was a
FREE six-elixir cycle. The live `near_enemy_king → w_wincon_mis` guard exists but sits in the
MINER branch; the rocket branch fell through to `return 0.0`. Now an explicit misplace both sides
(sim 0.0 → **-1.0**, princess unchanged +0.75).
⚠ Do not "restore" chip on the king: the overtime tiebreak reads PRINCESS HP, so king chip is
worth nothing at any point in a match.

**"It still doesn't understand the placement for rocket tornado."** Root cause: the sim has priced
the combo since 2026-08-16 (`rocket_nado_mult`, `rocket_nado_window_s`) and **live had no term for
it at all** — so a sim-trained checkpoint carried the TIMING across and had no gradient toward the
TILE. Live now mirrors it: `_last_nado` remembers the cast point/time; a rocket within
`rocket_nado_window_s` (2.5 s) AND `rocket_nado_radius` (**0.11 — deliberately tight, "the same
tile" not "nearby"**) pays `w_wincon * rocket_nado_mult`; and with wheels on the rocket is SNAPPED
to the tornado's tile ahead of the intercept assist.

Suites: icebow 555 OK, hogeq 42 baseline.

## 3l. 2026-08-20 — FIVE-TRACK ARCHITECTURE AUDIT (read this before more training)

Five parallel audits: reward architecture, sim↔live parity, deck divergence, hogeq's test
baseline, RL pipeline. **The headline: live training has been learning from plays that never
happened.** Fixed items are in `0ab0dc4`; everything else below is an open, prioritised backlog.

### THE VERDICT ON THE ARCHITECTURE
BC → sim-PPO → live-DQN is **not** the blocker; the design is standard and defensible. Two other
things are:
1. **The live data contract was fiction.** Measured over 12 sessions / 3,647 plays: six-elixir
   cards show a BIMODAL drop distribution — 27% drop by 4+ (deployed), **33% drop by ≤ 0**, which
   is impossible if 6 elixir left the bar. Mechanism found: illegal cells. 122 of 188 illegal-cell
   plays sat on grid row 12 with `min_own_gy` 13 — the X-Bow snap ran AFTER `deploy_clamp`.
   *Fixed (re-clamp + deploy confirmation), but legal cells still only deploy ~42% by that metric —
   **a second failure mode remains unidentified. Next live session, watch the `[deploy]` lines.***
2. **The live sample budget is 2-3 orders short and cannot be fixed by tuning.** 72,378 live
   decisions EVER vs 479,820 params and 2,072 legal actions = **0.15 decisions/param**, ~3.6
   deployed plays per (card, cell). `policy_rl.pt` carries **743** cumulative live gradient steps.
   The replay buffer is a local `deque` **discarded every launch** (never exceeds ~1,500 of
   100,000; each transition redrawn ~64×; SB3/Rainbow use replay ratio 0.25, we use 1.0).
   The sim yields ~300× more decisions per wall-clock hour.
   **RECOMMENDATION: demote `train-rl` from trainer to VERIFIED EVALUATOR + corpus collector.**
   Run greedy at the sim's gate threshold, record win rate, append verified transitions to a
   persistent corpus, feed that back through BC. Live win rate (0.87% over 805 matches) vs sim
   benchmark (27.6%) is the project's central unexplained quantity and is currently unmeasurable.

### OPEN, RANKED (not yet fixed)
1. **Live builds identity/memory/interaction blocks in FRAME coords; the sim uses BOARD coords.**
   30 of 52 threat dims wrong. `env.py:510-511, 516, 550-555` (+ `play.py:371-392`). The warp
   already exists 80 lines below (`env.py:586-611`) — mechanical fix, no retrain. Consequences
   measured: `identity_front 0.44` lands at board 0.497 (the fix is inert); depth saturates at
   0.575 so `threat_max_depth 0.65` **can never fire live**; interaction ETAs ~42% short.
2. **Threat dims 0-15 mean different things in sim vs live** (`sim/view.py:200` vs
   `threats.py:186`): sim slots 6-15 are always 0.0; live drives all 16. Needs a layout decision +
   fresh PPO run.
3. **hogeq's Hog earns ZERO wincon reward** in sim AND live — `_wincon_exec*` branch on
   xbow/tornado/rocket/miner ids, all empty for that deck. Its largest positive term is inert.
4. **The sim's whole X-Bow/tornado ledger is absent live** (8 terms incl. `xbow_into_push` −4.0).
   Live pays a flat +3.0 for ANY forward bow including into a committed push; sim pays −4.0.
   "Sim teaches bow-and-tornado; live un-teaches both."
5. **Junk beats waiting**: with a threat on the board, waiting = −1.0 (`threat_miss_idle`) while a
   tornado at nothing ≈ 0.0. There is NO spend term live at all. Live `threat_miss_idle` also
   lacks all four guards the sim added after measuring "always play" as 8× optimal.
6. **Live `_bonus` cap wraps only 2 of ~10 terms** → once the penalty budget saturates, wrong-card
   spam becomes exactly free.
7. **Deck divergence, Tier 1**: icebow's Earthquake building bonus is dead data (10.5× under-
   modelled, EQ in 33/1000 meta decks); hogeq's Log aim assist is permanently disabled via a
   `None` fallback though it runs the Log; icebow never got Firecracker recoil; hogeq never got the
   Tesla king-clearance; `hogeq/tools/llm_eval.py` grades hogeq's prompt against ICEBOW doctrine
   (7/13 expected answers are cards hogeq cannot play).
8. **hogeq's 42-failure baseline: 0 are real bugs** — 41 are icebow tests copied into a deck
   without those cards, 1 is a Cloudflare block. But ~55-70 MORE tests **pass green while
   exercising unreachable code**. Plan: 6 rewrite, 35 skip-with-reason, 1 environment.

### THE ROOT CAUSE BEHIND #7/#8
The code forked, **so the tests forked too**. `test_aim_assists.py` exists only in icebow;
`test_earthquake.py` only in hogeq — **each deck deleted the exact test that would have caught its
own bug.** Recommended Phase 0 (~1 day, zero behaviour change, would have caught all six Tier-1
findings): add `.gitattributes` (the CRLF mismatch is why `git diff` showed 614 changed lines where
4 were real, which is why this drift went unreviewed), plus `tools/deck_parity.py` +
`tests/test_deck_parity.py` with an explicit allow-list so divergence becomes opt-in and reviewed.
Then Phases 1-5: reconcile → decouple `Config.load`'s root → one shared package, two deck dirs →
deck plugin → one test suite run twice.

## 3m. 2026-08-20 — decision period 1.0s → 0.6s (`c328bef`). RETRAIN REQUIRED (sim).

Driven by the user's cadence line: pipeline 0.37 s vs **paced wait 0.49 s** — the loop waited more
than it worked. 0.6 s keeps the wait positive (~0.23 s); **do not go below ~0.45 s** or the period
becomes shorter than the pipeline and the served cadence drifts off the trained one again.

**Everything that had to move with it** (a lone `agent_dt` edit would have been silently
destructive):
| knob | 1.0s | 0.6s | why |
|---|---|---|---|
| `sim.agent_dt` / `play.act_period` | 1.0 | **0.6** | must always match each other |
| `train.gamma` | 0.99 | **0.994** | `0.99^0.6` — holds the half-life at 69 SECONDS, not 41 |
| `train.n_step` | 3 | **5** | keeps ~3.0 s of credit reach-back |
| `leak`, `threat_miss_idle` | — | **× dt** | charged per DECISION; would otherwise bill 1.67× per second |
| `llm_advisor_timeout_s` | 0.9 | **0.55** | a 0.9 s call overran a 0.6 s decision every time |

Per-tick scaling is applied **in code** (`self._tick_scale`, both envs) rather than by editing
weights, so it stays correct through any future period change. Event-driven terms (wincon_exec,
threat_response, crown, chip, spell_waste) are per PLAY and untouched.

### RETRAINING: what is and isn't needed
- **Checkpoints still LOAD** — no observation/action shape depends on dt (verified against
  `policy_sim_ppo_best_win40_14300.pt`: in_ch 12, threat 52, cells 432 unchanged).
- **But the MDP changed**, so the value head is calibrated to the old horizon and the old per-tick
  reward rates. **Run a fresh `train-sim-ppo --init <best>` (warm start, NOT from scratch)** and
  let the critic re-converge — the value-warmup path added in `ea25251` now covers `--init`, which
  is exactly this case.
- Judge it on the `EVAL @` avg-5 ladder lines; the bar to beat is the 33.2% banked by
  `policy_sim_ppo_best_win40_14300.pt`.
- ⚠ Sim reward totals before and after are **not comparable** — leak/idle now bill 0.6× per
  decision by design. Compare per-SECOND or compare win rates, not raw episode sums.
- Two latent test bugs surfaced (not caused) by the change: `_tick(env, seconds)` stepped once per
  second regardless of dt, and a quiet-refill loop used `range(5)` for "≥3 s". Both are now
  time-based.

## 3n. 2026-08-20 — why the drill pass rate sat at the random baseline (four root causes)

Owner's call after three PPO runs stuck at 17–20% against a 16.7% random baseline: *"I'd rather the
process be slow and accurate… go with option 1"* — fix each interaction's reward individually
rather than bolt a drill-completion bonus on top. Doing that end-to-end on the first drill found
that the problem was never a single reward weight.

**`run.py drills --outcomes` is the acceptance test now.** `--reward` asks whether the correct play
beats idling, and a drill can pass that while still teaching its own opposite. `--outcomes` asks the
question the optimiser actually asks: *under the trainer's own exploration, does PASSING pay more
than every other outcome?* At the start, **14 of 28 icebow drills said no.**
`tools/drill_terms.py <drill> [reps]` is the follow-up — per-REWARD-TERM means split by outcome, so
when a drill pays for the wrong thing it names the term responsible.

### The four causes, in the order they were found

1. **The king-activation credit measured a different event than the drill.** `king_hit` required the
   king to be AWAKE plus something NEAR it. Waking is a consequence of the king taking *damage*,
   which is strictly after the retarget — and the proximity proxy is the §6.0a false positive (a
   king woken by chip collects the credit while the attacker walks past). The real event is the
   owner's own wording: *the attacker is now going for the KING* — an identity test on `u.target`,
   which the drill's success predicate already used. It was also gated behind `age >= 3.5`, and **a
   drill ENDS the instant its success predicate fires**, so the episode was over before the window
   opened. Now per-tick, on `u.target`.

2. **The tornado graded itself on a snapshot taken before the pull happened.** `_register_nado`
   recorded membership at the DECISION instant; the engine applies the pull on the following
   advance. Measured on the drill's own reference line, which passes 100%:

   | t | hog distance to vortex centre | radius 5.5 |
   |---|---|---|
   | 3.60 | 5.53 tiles — snapshot taken here | OUT |
   | 4.20 | 5.09 tiles — vortex applies here | IN |
   | 4.80 | on the centre, targeting our KING | — |

   `pulled` was **empty**, and clump/retarget/combo/king/bad-pull all iterate it, so the entire
   `nado` family was silent. Same defect already fixed for rocket and log (judge a spell when it
   LANDS); the tornado was never included, and unlike those it is not an instant — the vortex pulls
   for its duration, so membership now accrues across the window, recording each unit's position and
   tower lock AT CAPTURE. **The tornado is in the icebow hand for every matchup drill**, so this one
   silent credit was suppressing far more than the tornado drills.

3. **The gate was the one head with no exploration prior.** Five drills recorded ZERO passes in 60
   episodes and four were the same kind — the skill is WHEN, not where. Each is passed by waiting
   several seconds and then playing; the card head has a prior and the cell head has one, but the
   gate sampled from the policy alone at ~50/50 per step, so a twelve-step hold arrives with
   probability ~0.5¹². **No reward can fix that**: `hold_the_tesla` already paid correctly in the
   direction it could express (timeout +0.66 beat playing early +0.01), but the outcome it exists to
   teach was never once generated. Every drill already carries the answer — its `reference` line
   records WHEN each card is played, a field used until now only by the report's third column.

4. **`hand=("tornado",)` did not restrict the hand.** `_restrict_hand` set
   `cycle = wanted_slots + rest` and the hand is `cycle[:4]`, so a drill naming one card still dealt
   three others, all playable — against its own docstring ("a rep must fail for the RIGHT reason").
   Measured on `nado_king_activation`: `threat_response` pays **zero** for a pull spell by design
   (it is judged by `_nado_shaping`), yet it read +0.286 on passes and **+0.839 on timeouts** — the
   policy was answering the Hog with the rest of the deck and collecting +1.0 a time, so episodes
   that never performed the technique out-earned the ones that did. Not a broken reward: blocking a
   Hog with a body IS a real answer. A broken **drill** — it claimed to present one card and
   presented four, so its pass rate was never evidence about the technique. This contaminated all 25
   drills that declare a hand.

5. **The reward paid for the second card thrown at a one-card threat.** `threat_credit_budget` is a
   flat **2** — "a real defense is 1-2 cards, not 4" — which is right for a push and wrong for a lone
   Miner. `skeletons_kill_the_miner` passes only if the answer costs ≤ 1.5 elixir (one Skeletons), so
   a passing episode can collect at most one +1.0 credit while an episode that keeps throwing
   Skeletons collects both and fails on `spent > 3.0`:

   | term | pass (n=9) | fail (n=46) |
   |---|---|---|
   | `threat_response` | +0.556 | **+1.130** |
   | `elixir_trade` | +0.271 | +0.141 |
   | **episode** | +0.587 | **+1.188** |

   The cheapest sufficient answer is the tier *above* every counter rule, and this term was paying a
   premium to violate it. The budget now scales with how many enemy **cards** are committed (via the
   same `cards_from_bodies` collapse `_threat_miss_idle` triages with — bodies are not cards), still
   capped by the configured budget, so a real two-card push funds exactly what it funded before.
   ⚠ The depth window was the other suspect and is **not** at fault — measured, the Miner sits at
   depth 0.526 inside the 0.12–0.65 window and the reference line duly collects its credit.

### Drill realism: NOISE (shipped on) and COMPOUND boards (built, default off) — 2026-08-21

Owner's diagnosis of why drills did not transfer: *"the situations in drills are highly specific,
but in real matches the game state will almost always consist of multiple drill-specific
interactions along with some other cards that … exist purely as noise."* It matches the measured
failure — a single-interaction board makes WAIT correct for most of the episode, and training 30% of
steps on that took plays/step from 10.4% to 5.9% and winrate from 10% to 0%.

**NOISE (`sim.drill_noise: 0.5`, ON).** Distractor cards per episode. Tagged (`Unit.drill_noise`) and
skipped by `enemy_units()`, so the engine simulates them and the POLICY sees them while the GRADER
is blind — otherwise the 12 "no enemy alive" and 37 HP predicates all become lies. They spawn in the
lane the drill is NOT about, and `princess_hp_lost`/`hits_taken` are lane-aware. Level chosen by
measurement (the reference line must still pass, or the drill grades luck): 0 → ~98%, **0.5 → 93%**,
1.0 → 89%, 1.5 → ~83% with one drill unwinnable.

**COMPOUND (`sim.drill_compound_frac: 0.0`, OFF).** Several interactions on one board.
* **SIMULTANEOUS, not consecutive** (owner's correction — consecutive "would not be much different
  from non-compound drills"). Offsets are bimodal: ~45% land exactly together so the policy must
  triage, the rest overlap at 0.6–3.5s. Measured, **17 of 25 boards carry ≥2 simultaneous
  components**. My first cut used 3–9s × i, which against 12–22s time limits was two drills in a
  trench coat.
* **TWO-LEVEL GRADING**, as specified: each component judged by its own predicates against ONLY its
  own units (`Unit.drill_tag` + the `_drill_component` filter — without it one drill's "no enemy
  alive" is answered by another's Hog), AND the overall board (`drill_compound_hp_frac: 0.25`),
  because acing two interactions while the third takes the tower is not playing the board well.
* Calibrated: **do-nothing 5%, doctrine 55%**. Bars are `pass_frac 0.5`, `hp_frac 0.25` — the first
  cut (0.6/0.45) had the oracle at 28% and the HP bar never binding at all.

**Sequencing (owner):** noise-only run first, compounds after it has a verdict — one training change
at a time.

### ⚠⚠⚠ THE RUN IS DEGRADING, AND `best_wr` HID IT (2026-08-21, 10:50)

**`best_wr` is a HIGH-WATER MARK, not a current score.** It only ever ratchets upward, so "flat at
11.525" does not mean "not improving" — it meant the policy peaked at match 1500 and has been
getting WORSE ever since. Measured directly, 40 full-difficulty matches per arm, identical
opponents and the trainer's own greedy rule:

| checkpoint | winrate | plays / step |
|---|---|---|
| **untrained net** | **15.0%** (6W-34L) | ~50% |
| `policy_ppo_drill_best.pt` @ match 1500 | 10.0% (4W-36L) | 10.4% |
| current @ match 7900 | **0.0%** (0W-40L) | **5.9%** |

The harness reproduces the banked 11.525 for the match-1500 checkpoint, so it is sound. **A policy
trained for 7,900 matches now loses every match and is 15 points WORSE than random init.**

**The mechanism is the collapsing play rate.** P(play) fell 0.286 → 0.14 and plays/step 10.4% →
5.9%, while elixir rose 2.45 → 4.25. An untrained gate plays ~50% of steps and wins 15%; in a
three-minute match a policy that rarely answers anything simply loses. ⚠ **The banking I reported
all morning as the drills working is the failure, not the progress.**

**Prime suspect: the drill mix teaches WAITING.** A drill is mostly waiting for one right moment,
so at `drill_frac 0.3` a large share of training states have "wait" as the correct action — and the
0.85 gate prior makes the sampled action a wait even more often than that. Global passivity is
exactly what would transfer.

**THE EXPERIMENT THAT SETTLES IT** (and it is the one this whole session set out to answer): train
`--drill-frac 0.0` against `--drill-frac 0.3`, equal budget, and compare winrate AND plays/step at a
fixed match count. Use `wr_eval2.py`-style direct measurement, never `best_wr`.

⚠ **Never quote `best_wr` as current performance again.** Six thousand matches of degradation were
invisible behind it, including in my own reports this morning.

### ⚠ RESTART REQUIRED: the run started 07:44 has the dead-match-accounting bug (fixed in `9e7d15f`)

`3a3dd73` (self-imitation, ~03:50) inserted `if True:` immediately after the `if is_drill:` block,
which stole the `else:` belonging to it and made the **entire match-accounting branch dead code**:

```python
if is_drill: ...
if True:  ep_from[i] = ...
else:                                  # never runs
    wins += ...; losses += ...; win_hist.append(...)
```

* **Visible symptom:** `0W-0L-0D` on a run with real matches (owner spotted it).
* **Real damage:** `win_hist` drives the winrate EMA, and the EMA drives **curriculum difficulty**
  (`d_tgt = max(0.15, wr_ema / full_wr)`), the PFSP ledger and the checkpoint gate. With `win_hist`
  permanently empty the EMA is 0, so difficulty collapses to its **0.15 floor** — the policy trains
  against the weakest opponents in the pool while `evaluate()` (independent, still correct) scores
  it against full-strength ones.

**This fully explains the "very odd results"**: `best_wr` 3.778 at 3000 matches against the previous
run's 11.333 at 2500, banking up but execution down. That run was not testing the floor anneal; it
was training on a broken curriculum.

⚠ **The 07:44 run is compromised from its first match.** Restart it on `9e7d15f` or later. The
earlier run (01:14–07:44) loaded its code *before* `3a3dd73` and is unaffected — its 11.333 is real.

⚠ **Void:** every old-vs-new comparison made from the 07:44 run, including the claim that the floor
anneal made things worse.

### PARKED, deliberately: anneal `ppo_drill_gate_floor` too (2026-08-21)

`ppo_drill_cell_floor` now anneals 0.75 → 0.20 (`01c036b`). **`ppo_drill_gate_floor` is still a
fixed 0.85 and has the same problem** — the gate is sampled from `(1-floor)*policy + floor*prior`
and the stored log-prob is the mixture's, so the gate's importance ratio is crushed exactly like the
cell head's was, and the timing prior does the work the policy should be learning. Measured
consequence: the drills where the policy scores 0% against a passing doctrine are mostly TIMING
drills (`hold_the_spell_for_a_target`, `log_the_ground_swarm`, `nado_the_sneaky_lock`).

**Not changed on purpose.** Owner: ship one training change at a time "so we don't confound the
effects of multiple changes". The cell-floor anneal is being measured on its own first; both share a
motivation, so shipping them together would make either result unattributable.

**Revisit when** the cell-floor anneal has a verdict — if placement improves and timing drills stay
at 0%, this is the next lever.

### ⚠⚠ CORRECTION: THE CELL HEAD WAS LEARNING ALL ALONG (2026-08-21, 05:15)

**I raised a false alarm and recommended a restart on the strength of it. Retracted.** Entropy is
the wrong instrument for this head, and three of my four overnight alerts came from measuring
badly rather than from anything wrong with the run.

Separating PLACEMENT structure (spread *within* one card's own map) from a per-card bias:

| checkpoint | within-card logit sd | vs untrained |
|---|---|---|
| fresh (untrained) | 0.000267 | 1× |
| A/B, 5000 drill episodes | 0.003846 | 14× |
| **live run, 6000 matches** | **0.191689** | **719×** |

A head carrying **719× an untrained net's placement structure** still sits within 0.018 nats of
maximum entropy, because a 0.19 logit spread over 157 cells is still a near-uniform softmax. The
"cell head is indistinguishable from untrained" alert was an artefact of the metric, full stop.

**What survives:** the importance ratio `r = 0.0125` is measured independently and is real, so the
drill's advantage genuinely does arrive attenuated and learning is slower than it could be. The
floor anneal (`01c036b`) is therefore a reasonable OPTIMISATION — but it is not repairing a broken
thing, and **restarting the run is not urgent.**

**What is now measured and true:**
* `ppo_sil_coef: 0.05` is HARMFUL — A/B at 5000 drill episodes: pass rate 40% → 11%, entropy 0.24 →
  0.00, reward +0.0 → −3.7. It collapses the policy. Stays off.
* The watchdog alerts on **within-card logit spread vs an untrained net**, not entropy. Entropy is
  kept only for the COLLAPSE direction, which it does detect well.

**The lesson, three times over in one night:** measure the thing the way the trainer sees it, at a
sample size that can see it. Too small a sample (elixir), the wrong support (unmasked 432 vs
deployable 157), and the wrong statistic entirely (entropy vs structure) each produced a confident,
wrong alert.

### ☀ WHEN YOU WAKE (2026-08-21 morning) — what happened overnight, ranked

1. ~~RESTART THE icebow RUN~~ — **RETRACTED, see the correction above.** The run is healthy and IS
   learning placement (within-card structure 375-719× an untrained net at 6000-12500 matches).
   Restarting only picks up the floor anneal, which is an optimisation, not a repair. Your call,
   not an emergency.
2. **hogeq drills are clean and ready** (`c8e6059`): 27/27, 0 unwinnable, 0 not-discriminating.
   Pull and the hogeq run is good to go.
3. **One real finding**: the drill prior was throwing away its own gradient (r = 0.0125, so the
   drill advantage arrived at ~1% strength). Floor anneal shipped; `ppo_sil_coef` shipped OFF as the
   deeper fix, **unvalidated — decide against a baseline**.
4. **Two false alarms, both from my own instrument, both fixed.** The elixir alerts were a
   640-observation sample of a ~1% event; at 2400 observations the bar reaches 6 in 9.8% of steps
   and `x_bow` is played *more* often than it is affordable. The watchdog now samples 2400 and
   debounces over two consecutive cycles. ⚠ **Treat a single watchdog cycle as a hypothesis, not a
   finding** — that is the lesson, and it cost two Discord alarms to learn.
5. **Open, not urgent**: `rocket` is never SELECTED even when affordable (0.0% of plays against 1.8%
   affordability) — the exact failure the doctrine CARD prior exists to address. Re-check on a run
   that has the floor anneal.

### ⚠ THE DRILL PRIOR WAS THROWING AWAY ITS OWN GRADIENT (2026-08-21, ~02:30)

The overnight watchdog caught the cell head still untrained at 4000 matches, and the diagnosis is
the most important thing in this batch: **a high fixed exploration floor buys the rare success and
then discards it.**

    trained cell entropy   6.0652 of 6.0684      fresh (untrained)   6.0684 of 6.0684

Not the entropy bonus — that anneal completed at 3000 episodes and the head did not move. It is the
IMPORTANCE RATIO. Cells are sampled from `(1-floor)*policy + floor*prior` with floor **0.75** inside
a drill, and the stored log-prob is the mixture's (which is what keeps PPO exact). So the update
forms `r = pi/mu`, and measured on the live checkpoint, on the cell the prior recommends:

| | |
|---|---|
| `pi(cell)` — the policy | 0.0101 (uniform 0.00231) |
| `mu(cell)` — what the sampler used | **0.2827** |
| `r = pi/mu` | **median 0.0125** |

The surrogate delivers `r*A`, so **the drill's advantage arrives at ~1% of its strength** — an ~80×
attenuation on precisely the samples carrying the drill's signal. Every drill fix in this batch was
real, and almost none of it could reach the cell head.

**Fixed (small, reversible):** `ppo_drill_cell_floor` now anneals 0.75 → 0.20 over 6000 episodes,
exactly as the cell-entropy coefficient does and for the symmetric reason — high early when the
success has to be generated at all, decaying so `mu` approaches `pi` and the successes finally
teach. Trainer smoke-tested.

⚠ **This does not fully close the gap.** At floor 0.20 with `pi` at 0.01 the ratio is ~0.08 — 6×
better, still small. **The real fix is an auxiliary self-imitation term** (cross-entropy pulling the
card/cell heads toward the actions taken in episodes that PASSED a drill), which does not pass
through the ratio at all. That is a change to the update itself and wants a waking decision.

**A general lesson for any prior in this trainer:** the strength of a sampling prior and the
learnability of what it demonstrates trade off directly. A prior strong enough to make a rare
action common is, by the same arithmetic, strong enough to stop that action from teaching.

### hogeq drills retuned for ladder levels (2026-08-21 overnight)

**0 UNWINNABLE, 0 NOT DISCRIMINATING, 0 passable by doing nothing** across all 27, at the levels the
model actually plays. Same tools as icebow (`drill_calibrate.py`, `drill_ref_sweep.py`), both ported.

**The bug that was hiding six of them:** a restricted hand let ONE CARD BE REPLAYED FOREVER. The
hand is `cycle[:4]`, so a drill dealt one or two cards has every card permanently in hand and a
played card returns with no cycle cost (a real hand is 4 of 8). Doctrine columns were passing by
spamming — `ice_spirit` ×5, `the_log` ×3-4, `earthquake` ×2, icebow's `tornado` ×3 in two seconds —
while each drill's own single-cast reference scored 0%. That reads as "stale line" and was really
"the column is cheating". **The trainer explores inside drills too, so it was a line the POLICY
could learn.** A drill that declares a hand now gets ONE PLAY PER DEALT CARD.

**Two new measurement primitives, both forced by the ladder level roll:**
* `hits_taken` / `hits_at_most` — enemy levels roll 13-16 (±32% damage), so for a drill whose play
  buys one denied hit the effect is *smaller than the spread the roll itself produces* and no HP bar
  can separate it. A denied hit is the same event at 13 and at 16. This is what made
  `ice_spirit_denies_the_hit` (7.56 → 6.04 hits) and `log_resets_the_charge` measurable at all.
* `enemy_base_below_frac` — a FRACTION of a card's own bar. One Earthquake takes a level 16 pump to
  22% and a level 13 one to nearly nothing, so "the pump died" scored the LEVEL ROLL, not the play.

⚠ **`drill_ref_sweep.py` had a real defect, now fixed**: it played on the clock while
`scripted_policy` HOLDS until the first enemy appears (timings are relative to the arrival, since
`randomise` jitters spawns). The sweep therefore scored a different policy than the report's third
column — it read 35% where the report read 0%, and its "100%" candidate scored 0% once shipped.
**Always confirm a swept placement against `run.py drills` before keeping it.**

### Drill state at ladder levels (2026-08-21, ready to train)

`run.py drills` — **0 UNWINNABLE, 0 passable by doing nothing**, 24 of 28 reference lines at 100%,
none below 84%. `run.py drills --outcomes` — **28 of 28 pay most for passing.**

Reference lines are not documentation: they are the report's winnability proof AND the source of
`drill_prior_cells`, the exploration prior the trainer samples inside a drill. A stale line aims the
trainer's own prior at a cell that no longer works, which is why they were refreshed rather than
left as a cosmetic gap. `tools/drill_ref_sweep.py` sweeps one step of a line and reports each
candidate's pass rate; `tools/drill_calibrate.py` reports the do-nothing vs correct-line damage
distributions so a threshold lands in the measured gap (it falls back to the DOCTRINE arm for
matchup drills, which have no reference line by design).

**The doctrine of the retune, and it is real Clash Royale:** every drill wanted its defender
placed DEEPER, where our own tower is already shooting, instead of out front where it fights alone.
Level-11 boards hid this because a weak attacker died either way.

⚠ **TRAPS this batch added to the list**
* **A 1-2 card restricted hand lets a card be REPLAYED IMMEDIATELY.** Both cards are always in
  `cycle[:4]`, so there is no cycle cost — a real hand is 4 of 8. `nado_clump_for_the_wizard`'s
  doctrine column read 96% by casting tornado three times in two seconds. Elixir is the only brake;
  keep drill starting elixir tight, and distrust a doctrine column that spams one card.
* **"All enemies dead" is not evidence** when the tower kills them anyway (Miner), when they are
  kamikaze (Wall Breakers), or when every line kills them eventually (minions).
* **Do not interpolate a placement.** For `tesla_pulls_the_wincon`, (0.56, 0.725) passes 100% and
  (0.50, 0.725) — the obvious "same but deeper" — passes **0%**. Measure the point you ship.

⚠ **hogeq's 27 drills have NOT been retuned.** The level fix landed in both decks, so its
thresholds are still level-11 numbers facing ladder enemies — expect the same breakage icebow had.

### Retuning the curriculum for ladder levels (2026-08-21)

Levelling the drills correctly broke four of them. All four are fixed, and `tools/drill_calibrate.py`
is the tool that did it: it runs a drill's two extremes -- **do nothing** and **its own reference
line** -- with the predicates stripped, and reports each arm's damage distribution. A threshold
belongs in the GAP between them; if there is no gap, the scenario needs rethinking rather than a new
number. Every bar below is now measured, not guessed.

* **`skeletons_kill_the_miner`** -- a MITIGATION drill (owner). Ignored 401 HP, answered 217: 184 HP
  saved for ~1 elixir, 46%. Old bars demanded the Miner die (he dies either way -- the tower gets
  him) and under 350 HP, which no one-elixir answer can reach.
* **`knight_guards_the_bow`** -- its predicate required the Valkyrie DEAD while its own notes said
  *"scored on the BOW SURVIVING… killing the Valkyrie would be the wrong play"*. She is a
  Knight-counter by design: pinned by level, the reference went 75% at L11 → 65/55/35/35% at L13-16.
  Scored on the bow surviving now: **100% at every level including 16**, baseline 0%.
* **`skeletons_stop_the_wall_breakers`** -- swept the answer: `y=0.66 at t=0.0` holds damage to a
  mean of 183 against 497 for the old `(0.70, t=0.6)` (breakers are fast; the half second cost more
  than the placement). Bar at 450 because **ignored never drops below 472** -- doing nothing cannot
  pass, by measurement. "All enemies dead" dropped: Wall Breakers are kamikaze.
* **`nado_pull_the_flock_back`** -- the Tornado is the ENABLER, not the answer, the same correction
  `nado_the_sneaky_lock` already carries. Six ladder minions deal ~950 dps and kill a 4424 HP tower
  in ~5 s, so a damage-free pull bought 130 HP for 3 elixir. With the Ice Wizard dealt alongside it:
  ignored 4372 (min 4150) vs 2588 (max 3132) -- clean separation, bar at 3600.

**State: 0 UNWINNABLE, 0 passable by doing nothing.** Reference lines still below par at ladder
levels (drill winnable, hand-written line stale): `nado_clump_for_the_wizard` scripted **0%** while
doctrine passes 96%, `split_lane` 40%, `knight_blocks_the_charge` 68%, `tesla_pulls_the_wincon` 68%.

### ⚠⚠ EVERY DRILL PUT OUR REAL-LEVEL CARDS AGAINST LEVEL 11 ENEMIES (owner caught this, 2026-08-21)

> *"just need to make sure it isn't putting the model's level 14-16 cards up against level 11
> opponents, because that mismatch is a fatal mistake and large level differences will completely
> change how interactions work."*

It was. `DrillEnv` hardcoded `level=11` for every scripted spawn, while:

* **our hand** plays at the deck's real account levels — `x_bow` 16, `knight` 16, `skeletons` 15,
  `tornado`/`tesla`/`rocket`/`the_log` 14, `ice_wizard` 12 (`SimMatchEnv` builds specs from
  `db.deck_levels()`);
* **full-match training** rolls the opponent from `sim.enemy_levels` [13,14,15,16] weighted
  [3,5,2,1] — mean ≈ 14.1 — explicitly *"so the opponent's card levels vary like a real ladder
  opponent"*.

So a drill was a level 16 Knight against a level 11 Prince where training is a level 16 Knight
against a level 14 one. **Level 11 → 14 is +32% HP and +32% damage** on every card measured.

**It changes the answer, not the margin.** Each drill's own hand-written reference line — the play
the report certifies as correct — run against the enemy level it should have faced:

| drill | L11 | L14 | L16 |
|---|---|---|---|
| `skeletons_kill_the_miner` | 100% | **0%** | 0% |
| `knight_blocks_the_charge` | 100% | 90% | **0%** |
| `tesla_pulls_the_wincon` | 100% | 100% | **0%** |

`skeletons_kill_the_miner` teaches *"one elixir answers a Miner"*. Against the Miner training
actually faces, it does not. **The drill was rehearsing a play that loses**, and every pass rate in
this batch before this point was measured on the wrong board.

**The fix** mirrors `make_opponent`: enemy spawns roll their level from the same ladder
distribution, per spawn, off the env's seeded rng (a rep stays reproducible), and an explicit
`--level` still pins them for fair eval — the same override `make_opponent(level=...)` already
offers. Our own pre-placed bodies take our deck's real level for that card, since a level 11 Knight
beside the level 16 one from hand is the same bug wearing a different hat.

**FALLOUT — the curriculum was calibrated on an easier board.** At ladder levels, four drills are
now UNWINNABLE (reference, doctrine and baseline all fail) and several reference lines have
degraded:

* `skeletons_kill_the_miner` 0% · `skeletons_stop_the_wall_breakers` 0% ·
  `nado_pull_the_flock_back` 0% · `knight_guards_the_bow` 36%
* degraded: `knight_blocks_the_charge` 68%, `tesla_pulls_the_wincon` 68%, `split_lane` 40%,
  `nado_clump_for_the_wizard` scripted 0% (but doctrine 96% — the reference line, not the drill)

These need retuning against the real levels — thresholds and reference placements both. **Do not
"fix" them by pinning the level back to 11**: that is the bug, and it is the reason they looked
fine. ⚠ Any drill pass rate quoted from before this commit was measured against level 11 enemies
and is not comparable to one measured after.

### ⚠ THE BIGGEST ONE: half the cards in the game could not be answered, so every answer was fined

`card_threat.counters()` is the role table the referee grades defence with — air-defence vs flying,
splash vs swarm, DPS/building vs tank, building vs building-targeter, body vs a bare win condition.
A threat matching **none** of those falls off the end and returns False for *every card in the
deck*, and `_threat_response` then charges `w_threat_miss` (−1.0) for the defence as a misread.

Measured across the card database:

> **154 non-spell cards; 74 match NO threat class, and no card in the deck counters them.**
>
> `mini_pekka` (472 dps), `sparky` (333), `lumberjack` (320), `prince` (279), `elite_barbarians`
> (274), `musketeer` (217), `wizard` (201), `bandit` (194), `archer_queen` (188), `witch` (123) …

None is a tank, a swarm, air, siege or building-targeting, and none carries the curated
`win_condition` flag — so to the referee, a Prince charging your tower is a threat nothing can
answer, and **defending is always a mistake**. This is not a drill artefact: `card_threat` is shared
with the live side, so the same hole sat under `train_rl`'s counter validation and the advisor.

Surfaced by `knight_blocks_the_charge`, a drill whose entire content is putting a body in front of a
Prince: `threat_response` read **−0.604 on the episodes that PASSED it**. The drill's correct play,
fined every time, on the drill built to teach it.

**The fix**: the branch that should have caught them was already there and already argued the case —
a bare win condition "walks (or tunnels) straight at the tower, so the answer is simply a BODY that
engages it". Equally true of a Prince or a Musketeer. The only thing stopping them was that the
branch also demanded the `win_condition` bit, which is a **deck-role label** ("this is what the deck
wins with"), not a claim about what answers the card. Gate dropped to what the reasoning needs: a
ground threat that is not a tank and not siege is answered by a body. 74 → **0**.

Deliberately unchanged, because these are the cases where "any body will do" is false: tanks still
need real DPS, a building, or a melee swarm to surround them; air still needs air defence; siege
keeps its own rule; our own siege still cannot defend; a spell is still not a body.

**`tools/counters_check.py`** (both decks) is the permanent guard — twelve cases, each one a real bug
once, each recorded in that function's comments. This table has been widened or narrowed five times
in the project's history, so it now fails loudly instead of relying on a careful reading of the diff.

### What the hand restriction broke, and the two follow-on fixes

* **A discipline drill needs the temptation in hand.** `bank_to_six_then_bow` fails if you dump the
  bar on knight/skeletons/ice_wizard/tesla but declared `hand=("x_bow",)`. Once the hand actually
  restricted, that branch became unreachable and the drill passed **60/60** — a drill nothing can
  fail measures nothing. Its hand now deals the temptations, as `ignore_the_ignorable` already did
  ("THE TEMPTATION MUST BE A COUNTER, not the whole deck"). A source scan found this was the **only**
  such mismatch across both decks.
* **`_restrict_hand` dealt in slot order**, so with more than four wanted cards which ones reached
  the opening hand was an accident of deck layout — a drill could open without the card it is named
  for. It follows the scenario's declared order now.
* **The timing prior has to know what the line costs.** `bank_to_six` opens at 2 elixir with a 6-cost
  X-Bow written at `t=0` ("first thing" — you cannot bank before the match starts). The gate prior
  read that literally, nominated PLAY from the opening tick, and the card head — which can only pick
  among *affordable* cards — chose the cheap ones the drill fails you for. The prior holds until the
  next reference card is affordable, which also survives `randomise=("elixir",)` moving the moment
  the bank fills every episode.
* **The gate floor went 0.6 → 0.85.** At 0.6 the mixture still plays at 0.23/step while the prior
  says HOLD; `bank_to_six` needs ~19 consecutive holds, so 0.77¹⁹ ≈ 1 in 80 (measured: 0 passes in
  60, twice). At 0.85 it is ~1 in 6, and a prior that says PLAY still fires at 0.84.

### Two left open, deliberately

* **`bow_defends_from_the_centre` — the reward is RIGHT and the drill is wrong.** Its failing
  episodes out-earn its passing ones because the bow locked and chipped the enemy tower
  (`xbow_lock` +0.309, `chip_offence` +0.267, `take_enemy_tower` firing in one of four): those are
  **crown trades** — our princess ate the Giant, their tower came down — which is good Clash Royale.
  The drill fails on our princess HP alone and cannot tell a tower lost for nothing from one traded
  for theirs. A fix is written (stop failing once an enemy princess tower has fallen) but **not
  applied**: at n=4 it does not clear the evidence bar the acceptance test now enforces, and acting
  on four episodes is the exact mistake that bar exists to prevent.
* **`skeletons_kill_the_miner` residue.** The budget fix cut the over-answering premium
  (`threat_response` on fails +1.130 → +0.783) and the verdict fell to `weak`, but passing still
  trails slightly. The remaining cause is that a *single* correct answer earns credit only if it
  lands inside the narrow `intercept` lane window, while repeat plays get more chances at it — more
  shots, more likely to collect. Fixing that means changing the shape of every `threat_response`
  credit in both decks, so it is measured and recorded rather than rushed.

### Also fixed: the acceptance test was convicting drills on two-sample means

It failed a drill whenever *any* outcome out-earned PASS, regardless of evidence — `timeout +5.55
(n=2)` beating `pass +2.15 (n=13)`. Acting on that would have meant rewriting reward terms that
work. A rival now needs **n ≥ 5 AND a lead wider than two standard errors of the difference**; a
real-but-unproven lead prints as `weak` and is left alone. Separately, a **restraint** drill is
passed by doing nothing, so exploration can never record a pass and "nothing to learn from" was
backwards — when no episode passes, the do-nothing line is scored and, if it is the drill's own
correct answer, becomes the PASS column.

### Traps this batch (add to §8)

* **A drill ends on its success predicate, so any reward that resolves on a delay cannot pay it.**
  The king credit waited 3.5 s for an episode that ended at 0.6 s.
* **A cast-time snapshot is one agent step stale.** Anything measuring "what this spell caught" must
  read the board when the spell APPLIES, not when it is requested.
* **`--reward` (correct play beats idling) is not the same question as `--outcomes` (passing pays
  most).** The king drill scored +1.10 on the first while paying +0.24 to time out and −0.28 to pass.
* **A significance-free comparison of outcome means is noise.** Two episodes cannot outvote thirteen.

## 3o. 2026-08-21 afternoon — THE REAL BUG: PPO training makes the policy WORSE THAN UNTRAINED

**Read this before touching drills, curriculum, or reward shaping again.** Everything in SS3n was
addressing drill CONTENT. The fault is in the OPTIMISER, it predates the drills, and it is large.

### The measurement that matters

Same eval harness, 24 episodes/checkpoint, icebow, 700 matches of `train-sim-ppo`, drills at 0.3:

```
untrained  5 inits x 40 eps    reward -13.57 +- 0.24 (sd ACROSS INITS)   <- the baseline
mult=4.0   seeds 41,42         reward -25.46     1.9x worse than doing nothing
mult=1.0   seeds 41,42         reward -29.53 / -33.96   2.2-2.5x worse
drill_frac 0.0 (no drills)     reward -28.22     2.1x worse
per-head clipping ON           reward -35.35     2.6x worse (NO improvement)
```

> **CORRECTION (same day).** An earlier version of this section, and commit `4767a7b`, quoted the
> untrained baseline as **-6.78** and claimed 3.8x-5.0x degradation. That number came from a
> differently-configured one-off eval and is NOT reproducible. Re-measured properly -- 5 independent
> inits x 40 episodes -- untrained is **-13.57 with sd 0.24**, so the degradation is ~2x, not ~5x.
> The direction and the significance are unchanged (every trained result is dozens of standard
> deviations below baseline); only the magnitude was wrong. Baseline script:
> `<scratch>/baseline.py`. Do not quote a single-draw untrained number again -- it moved by 2x.

Training does not plateau, it does not overfit -- it moves the policy AWAY from its own reward
signal, hard, from the very first episodes. An untrained net beats every checkpoint we produced.

> ## ⚠⚠ THIS SECTION'S CENTRAL CLAIM IS WRONG — THE DRILLS **ARE** THE CAUSE (2026-08-22)
>
> Everything below that says "not the drills" came from **a single `drill_frac 0.0` run** that
> scored P(play) 0.225. Re-run at **three seeds**, HEAD does not collapse without drills at all:
>
> ```
> HEAD, drill_frac 0.0, 3 seeds:  P(play) 0.993  0.922  0.964   ALL HEALTHY (untrained 0.49)
> HEAD, drill_frac 0.3, 4 runs:   P(play) 0.151  0.107  0.151  0.107   COLLAPSED
> ```
>
> The one run that "proved" drills innocent was one of the ~2-in-6 that collapse by chance — the
> collapse is **bistable** (measured escape rate 4/6), so n=1 decides nothing. No seed overlap
> between the two groups. The owner suspected drills from the start and was right.
>
> Consequences: (1) there is **no commit regression** — the bisect below measured seed noise, and
> HEAD is as healthy as the "known-good" `74ac441` in the pure-match regime (0.96-0.99 vs 0.98);
> (2) `ppo_clip_play_mult` and `ppo_value_detach` were mitigating a **drill-induced** collapse;
> (3) NEVER call a bistable result from one run again — 3 seeds minimum.

### It is NOT the drills — ⚠ RETRACTED, see the box above (this was n=1)

```
drill_frac = 0.0  (pure matches)   P(play) 0.493 -> 0.225     winrate 24% -> 10%, reward -5.9 -> -9.3
drill_frac = 0.3  (with drills)    P(play) 0.535 -> 0.174
```

With drills entirely OFF the run still degrades monotonically in its own training log. Drills make
it modestly worse; they do not cause it. The 43% drill pass-rate plateau is DOWNSTREAM of this.

### The gate collapse ("decay from start"), and a cheap reproduction

P(play) falls from ~0.50 to ~0.06-0.25 in EVERY run. It is fully expressed in **700 matches
(~25 min on 8 envs)** -- no more overnight runs to test a hypothesis:

```bash
python run.py --config <scratch>/cfg.yaml train-sim-ppo --matches 700 --envs 8 --workers 0   --size 432 --drill-frac 0.3 --seed 41 --device cpu --out <scratch>/probe.pt
```

Corroborated at full scale: the 96-env run reached P(play) 0.177 at 3371 matches. The CELL head is
learning fine throughout (cell_struct 90.8x untrained, 60 distinct cells) -- the failure is the GATE.

### `ppo_clip_play_mult` (SHIPPED, default 1.0 = OFF)

A play's PPO ratio is a product over gate x card x cell (432-way); a wait's is the 2-way gate alone.
Measured, plays leave the trust region **12-25x** more often, and their gradient is killed 10x more
(0.078 vs 0.008). The knob widens the clip bound for PLAY actions only. At 4.0 it cuts the kill
asymmetry to 3.5x and buys ~8.5 reward and ~0.22 P(play).

**It is a MITIGATION, not a fix, and it is DEFAULT OFF.** It recovers about a quarter of the damage;
the policy is still 3.8x worse than untrained. Do not spend a night on it believing it solves this.
The value 4.0 is UNTUNED -- picked because it equalised clip rates. A variance argument says ~1.7.
A 5-value x 2-seed sweep scoring REWARD is staged and unrun.

### FOUR mechanism claims I made and had to withdraw -- do not re-derive these

1. *"Clipping is asymmetric: it zeroes positive-advantage gradients while negative ones keep
   pushing."* WRONG -- PPO's clip is deliberately two-sided (kills grad when A>0 and r>1+eps, OR
   A<0 and r<1-eps). I ignored the mirror branch.
2. *"Plays carry ~2x the downward push."* WRONG -- one noisy logging window. The next window flipped
   the sign (-0.11 then +0.70).
3. *"Clipping amplifies an already-negative gate pressure, 56/44 split."* WRONG -- the metric summed
   `play_push + wait_push`, which counts wait steps with the WRONG SIGN. The update is
   `+A*r*grad log pi(a)`, so a wait step with NEGATIVE advantage LOWERS log pi(wait), which RAISES
   P(play). A negative wait push pushes TOWARD playing.
4. *"mult=4.0 stops the decay"* (from 0.062 vs 0.419 at seed 21). OVERSTATED -- at seed 61 the fix
   arm tracked down to 0.117-0.28 as well. It reduces the damage; it does not stop it.

The correct gate projection (now in the code) is `A*r*(1-p)` on play steps and `A*r*(-p)` on wait
steps. Measured that way the PPO surrogate's net gate pressure is ~0 while P(play) is collapsing --
i.e. **something outside the PPO term is driving the gate down.** Candidates, uninstrumented:
the entropy bonus, `_clamp_heads()`, and the exploration floors' effect on the behaviour policy.
Note `ent=0.07` (drills) / `0.21` (no drills) at 600 matches -- the policy has stopped exploring.

### Diagnostics added to `train_sim_ppo.py` (icebow only; hogeq has the knob, not the prints)

Printed every `log_every` episodes:
* clip rate split PLAY vs WAIT
* gradient KILLED rate split (the two-sided-correct version)
* net surviving push/step, and the **unclipped CONTROL** -- if raw ~= surviving, the bias is in the
  ADVANTAGES, not the clip. That control is what caught claim #3.
* GATE LOGIT PRESSURE, projected with the correct sign, clipped vs unclipped

**The gate-pressure metric is UNDER-POWERED as written**: it resets each window, so sd (0.011)
exceeds the between-arm difference (0.010). Accumulate across a whole run before comparing arms.

### PER-HEAD CLIPPING: implemented, measured, DOES NOT FIX IT

`ppo_clip_per_head` (default false) gives each head its own ratio and its own trust region, so the
432-way cell head cannot delete the gate's update. Measured A/B, 700 matches, seeds 41/42:

```
per-head ON    P(play) 0.137   reward -35.35
baseline OFF   P(play) 0.186   reward -29.53
```

No improvement (worse, inside noise). The head-coupling defect is REAL -- sd(log r) gate 0.002 vs
cell 0.478, measured six times -- but it is NOT what degrades the policy. Left in, default off.

### WHERE THE COLLAPSE ACTUALLY COMES FROM (measured, narrow, unresolved)

The gate is **not** starved and **not** throttled:

```
GRAD NORM per head:  gate 0.028-0.049   card 0.010-0.031   cell 0.00003-0.0001   value 0.30-1.39
```

The gate has the LARGEST policy-head gradient. `_clamp_heads()` never touches it. The cell head's
+-61% log-prob swings come from Adam taking ~lr-sized steps on a near-zero gradient, not from
learning signal.

The engine is a small, near-noiseless, EVERY-UPDATE push on the gate at states where it PLAYED:

```
GATE drift:  PLAY steps -0.169 / -0.386 / -0.408     WAIT steps -0.044 / -0.007 / +0.012
```

Play log-prob falls 0.17-0.41 per update; wait is flat. The gate's mean movement is ~11x its own
sd -- a systematic drive, not noise -- and that compounds 0.5 -> 0.06 over hundreds of updates.

RULED OUT by measurement (not argument): drills (identical at drill_frac 0.0), joint-ratio clip
coupling (per-head fix did nothing), clip bound width (mult=4.0 mitigates ~25%, does not fix),
gate gradient starvation (largest gradient), `_clamp_heads()` (does not touch the gate), floors
clipping plays by construction (only 0-3% clipped at epoch 0).

STILL OPEN: three terms touch the gate logits -- the PPO surrogate, the entropy bonus, and the
value loss through the shared trunk `z`. A probe that takes each term's gradient w.r.t. the gate
logits and reports its signed push on (logit_play - logit_wait) is instrumented and was running
when this was written. Whichever term is large and negative is the cause.

### NEXT: find why plain-match PPO moves against its reward

Self-contained, cheap to reproduce, and it blocks everything else. Start with `drill_frac 0.0` so
the drills are out of the picture. The user does not know when this regressed -- a bisect over the
sim-PPO history against the "reward vs untrained" test is the direct answer.

---

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

### The distinction that matters when adding a mask

* **RULE masks** encode the GAME: no deploying past the river, no unaffordable cards, tile legality,
  and now THE POCKET. These are unconditional. There is no flag and there should not be one --
  turning one off does not create learning headroom, it just lets the policy waste actions on moves
  the game rejects. (I proposed a pocket flag; the owner correctly refused it.)
* **STRATEGY masks** encode HUMAN JUDGEMENT: no rocketing the king, no whiffed spells. These cap the
  model at whatever a human thought of, so they get flags AND they anneal off.

### THE POCKET (`d4d5ac2`, `20ab936`) -- unconditional

Destroying a princess grants deployment territory across the river on that side, for BOTH sides.
154 -> 254 -> 354 legal cells. Wired through the trainer with a 2-bit code stored per step so the
update rebuilds the mask sampling used. Opponents use it too (neural via mask variants chosen per
act(); heuristics via `_pocket_lane()` -- they already reached over with SPELLS but never walked a
troop into a pocket). Measured: enemy troops past the river 13 -> 23 after we lose a princess.

Still NOT pocket-aware (static masks): play.py, train_rl.py, policy_stats.py, train_bc.py.

### Spell target mask (`ff767f0`, `8393859`) -- strategy, so it anneals

`spell_waste` (-0.3) cannot fix whiffs: during exploration a whiff is a RANDOM choice, and this repo
already learned that in no_king_mask ("A reward cannot stop a random choice; only a mask can"). The
real cost is the ELIXIR -- a whiffed Rocket is 6 elixir missing for the next counter, so one bad
cast becomes a missed defence too (owner: the single biggest weakness in live play).

`sim.ppo_spell_target_mask` + `play.spell_target_mask` restrict casts to cells the env's OWN
`_spell_no_target` / `spell_whiffed` says would hit. Annealed 100% -> 0% over 25k episodes,
probabilistically, so the cell head keeps getting gradient there and the model can eventually
develop casts the criterion forbids.

### Deck exploiters (`8393859`, `659224e`) -- default OFF

AlphaStar's league exploiters, adapted: the league here is the 100-DECK META POOL, not self
snapshots. `sim.deck_pfsp_power` samples decks we LOSE to more often.

**Do NOT raise `selfplay_prob` to Dota-like levels.** I suggested it; it is wrong here and SS1414's
history already records why -- 0.5 + PFSP^2 drove the benchmark 19.3% -> 1.3% overnight. A frozen
self can only pilot OUR deck, so self-play trains the MIRROR: 1 matchup of ~100, and icebow is rare
on ladder. The OpenAI Five analogy breaks on this game's structure.

### ⚠ `--resume` RESTARTS EVERY ANNEAL

`done_n = 0` unconditionally, and `_prog["n"]` drives the drill cell floor, cell entropy, the
self-play ramp and the spell mask. Resume therefore gives trained weights + fresh early-training
scaffolding, not "continue where you left off". Prefer a fresh run when the action space changed.

### Three SILENT NO-OPS found today -- check the seams, not the pieces

1. `spell_whiffed` missing from play.py's imports, inside a bare `try/except`: the live mask would
   have disabled itself every decision while looking enabled in config.
2. The parent rebuilds worker `info` from four hand-listed keys and dropped `"deck"` -- deck PFSP
   was inert for every `--workers > 0` run. Worker sent it, parent binned it, no error.
3. `run.py drills` graded the DRILL, not the policy, so rows read "policy 0% ... ok".

Each was individually-correct pieces failing at the seam, with no exception. Every such feature now
prints ONCE when it first fires; if the line is absent, it is not running.

---

## 3r. 2026-08-23 — THE WINCON BANK FAILED TWICE, AND ITS REPLACEMENT IS 98% INERT

Three commits and one full eval at 10k matches. **Net result: the x_bow incentive did not work, and
the match benchmark is still at the untrained line.** Read this before trying a third wincon nudge.

### The bank failed in BOTH directions (`3003d50` on, `b53bb4c` off)

`sim.wincon_bank_floor` masks cards cheaper than a held win condition while the bar climbs to its
cost. It has now been tried twice and failed in opposite directions:

| | setting | what the policy did |
|---|---|---|
| 2026-08-14 | low floor | **70% forced waits** — the mask ate the whole action space |
| 2026-08-23 | 4.5 | **dumped elixir to stay UNDER the floor**: median 5.29 → 2.46, x_bow affordable 45% → 9% |

**The mechanism is the same both times and it is the reason a mask cannot work here: the policy
controls its own bar.** A floor that only binds above X elixir is avoidable by never being above X.
`wincon_bank_floor: 0` and it should stay there — this is not a tuning failure, it is structural.

### `rewards.wincon_reach: 0.5` — the replacement, and why it barely fires

A ONE-TIME credit the first time the bar reaches a held wincon's cost on a board with no answerable
threat. Chosen over a per-step hold bonus because a per-step bonus is farmable by hoarding — which
is precisely the failure to avoid (owner flagged this risk before it shipped; it was measured first:
a HOARD-always policy scores +0.50 reach/match but −17.17 `threat_miss_idle`, net −16.67).

**MEASURED AT 10k MATCHES — it is nearly inert.** Instrumented clause by clause, 6 matches:

```
steps            1589
holding           874    x_bow in hand
pre_ok            371    ... and bar >= 6.0
armed             210    ... and credit not yet taken this cycle
paid                4    <-- 2% of arms
blocked_threat    206    <-- 98%, killed by the no-answerable-threat guard
```

**The guard is the whole story: the board is essentially never quiet when the policy holds the bow
with 6+ elixir.** The term as written can only pay in a state this sim almost never produces. Any
third attempt must either relax that guard or price the EXECUTION rather than the reach.

### The 10k eval — the benchmark did not move, and x_bow went DOWN

Run: started 11:50, `--envs 192 --workers 12 --device cuda`, **`--init policy_ppo_drill_best.pt`**.

```
                    W-L-D    winrate   crowndiff        x_bow share   elixir median
UNTRAINED           1-39-0     2.5%    -1.850 +-0.148        -              -
m=6000 (best)       1-39-0     2.5%    -1.875 +-0.159       2.08%         2.29
m=10000             1-39-0     2.5%    -1.925 +-0.134       1.06%         2.14
```

All three are the same policy by the benchmark. **x_bow HALVED (2.08% → 1.06%) over the 10k matches
the incentive was live** — the opposite of the intended effect. Known-good reference is 36%.

**⚠ The elixir median (2.14) is inherited, not caused by this change.** The run was `--init`ed from
a checkpoint trained UNDER the 4.5 floor, i.e. from the weights that had learned to dump. Removing
the floor did not undo the habit in 10k matches. **A config revert does not revert the policy** —
if the dumping is to be unlearned, the run has to start from weights that never learned it.

### ⚠ CORRECTION (same day): the quiet-board guard CONTRADICTED THE DOCTRINE

Owner caught it: *"x_bow shouldn't only be played when the board is completely quiet. For offensive
x_bows, if the board is RELATIVELY quiet and the opponent is low on elixir, that's fine. And if
there's a lot of enemy activity, a defensive x_bow can be placed to set up defense."* Correct, and
it is already written down -- DOCTRINE.md:41 gives the bow **two** modes and a quiet board is
NEITHER:

* **OFFENSIVE** -- row 53 gates it on *"opponent spent >=7 elixir away from our bow lane"*, an
  ELIXIR condition. `_punish_window` is exactly that test, and `_wincon` already pays
  `xbow_punish_mult` (1.5x) on it.
* **DEFENSIVE** -- rows 56/63/79, centre band (0.48, 0.55), a second pull building. It requires a
  PUSH. `_xbow_into_push` already EXEMPTS it ("it IS a pull building").

So both modes were implemented and priced, and the new guard invented a third notion of a correct
bow that contradicted both -- suppressing the credit in exactly the state (a push) that most calls
for a defensive bow. Measured at m=10000 over 12 matches, on the 286 steps where the bow was in
hand and affordable:

```
old guard : board quiet             47   16.4%
OFFENSIVE : _punish_window         252   88.1%
DEFENSIVE : real push present      201   70.3%
either (doctrine says bow)         266   93.0%
```

**Fixed:** `_wincon_reach` now keys off those two predicates instead. Re-ran the exact diagnostic:
**10 arms / 10 paid (100%, was 4/210 = 2%)**, credit 0.33 -> **0.83 per match**. Arms fell 210 -> 10
because the one-time latch now actually latches rather than being blocked and re-arming every step.

**Lesson, and it is the general one:** when a reward needs to know "is this play correct here", reuse
the predicate the rest of the file already trusts. Two terms with different ideas of a correct bow
is a bug that no test catches, because each is internally consistent.

**Not caused by this batch:** `test_budget_caps_and_hysteresis_refills` fails in `_threat_response`
(`0.0 not greater than 0.0`). Verified pre-existing by stashing. 615/616 otherwise.

### FROM-SCRATCH WOULD BE WORSE — measured, and it corrects what I told the owner

The pre-bank checkpoint is gone (overwritten), so the question was whether to restart from zero. I
had blamed the elixir dumping on bank-trained weights carried in by `--init`. **That was wrong.**

```
                            elixir median   bow affordable
UNTRAINED (from scratch)        1.79            0.1% of steps
m=6000 (best)                   2.29            4.6%
m=10000 (current)               2.21            3.8%
```

An untrained gate dumps HARDER -- it plays ~half the time with random cards. The trained checkpoints
are strictly better on elixir and on bow-affordability, and identical to untrained on the benchmark.
So there is nothing to gain by discarding the drill progress (33.7% mean). **Keep the checkpoint.**

### OFFENSIVE BOW: it was gated on ONE condition, and the doctrine has EIGHT

Owner: *"offensive x-bow shouldn't be gated on a single condition."* Right. Researched and written up
in full in `DOCTRINE_RESEARCH.md` §3A (sources: the Fandom page for OUR exact deck, the 3.0 page, the
2.9 blog, Theria -- all via `api.php`, since page fetches 402). Eight windows; two are coded.

**The headline gap is CYCLE (W2)**, which our deck's own page makes the primary decision input and
states twice: *"know where your opponent's counter to the X-Bow is in their cycle... helps with
knowing whether to play an X-Bow on offense or not."* `_opp_can_block_now()` reads their HAND only.
The sim owns their true deck order, so cycle depth is a small extension of `_opp_block_cost`.

Also uncoded: counterpush-off-a-won-defence with surviving defenders (W3), near-full-bar-with-a-
defensive-hand (W4, and `_punish_window` tests a GAP not an absolute), pump-punish-with-the-BOW (W5),
they-hold-no-big-spell (W6), after-single-elixir (W7), their-big-spell-forced-out (W8).

**Two things that need resolving before compiling, both recorded in §3A:**
1. `_bow_split_punish` is **too broad**. Sources split by TANK, not by back-tank-ness: P.E.K.K.A in
   the back -> bow (IW-Control), but *"you don't want to offensive X-bow into a Golem"* (same page)
   and Theria/2.9 both say don't. Discriminator: a building-targeting tank WALKS INTO the bow. Same
   lane vs a Golem/Giant should be excluded; DOCTRINE row 79's OPPOSITE-lane bow survives.
2. W5 conflicts with the shipped `rocket_the_pump_on_sight` drill -- the page says answer a
   single-elixir pump with the BOW, not the Rocket. One source; not changed, not settled either.

**Pocket tie-in nobody has used yet:** the inside/centre offensive plant *"when you have lost a tower
allows it to only be hit from 2 sides, instead of 3 or 4"*. We shipped the pocket in §3q and no cell
preference reacts to a lost princess.

### Drills nearly TRIPLED while the benchmark stayed flat — the §3p decoupling, again

`run.py drills --policy` (priors off, the honest number): **mean 33.7%, 8 of 28 at zero**, against
the §3p baseline of **12% and 16 of 28 at zero**. Real, large drill improvement; **zero** benchmark
movement. This is the second clean instance of "drill learning does not predict match performance".
Do not read a rising drill mean as progress on the objective.

The drill that directly tests the behaviour this change was meant to induce:
`bank_to_six_then_bow` **16%** vs doctrine 100%. It is failing, consistent with the x_bow decline.

Still at 0%: `bow_never_into_the_push`, `hold_the_spell_for_a_target`, `ignore_the_ignorable`,
`log_rolls_forward_not_backward`, `log_the_ground_swarm`, `nado_king_activation`,
`rocket_then_tornado`, `skeletons_stop_the_wall_breakers`.

### `threat_miss_idle` is the largest negative term BY DESIGN — stop re-investigating it

Owner asked why it is still the most negative term after 10k matches. Measured: it fires on **0.8%
of decisions** (13 fires / 1610), at **median 5.29 elixir with a full affordable hand** — never once
below 2.0. It is the largest term because it is the largest PER FIRE (−1.00, versus `elixir_trade`
at −0.04/fire over 41 fires), not because it fires often. Two fires outweigh forty small ones.

So it is not a mispricing and not a mask artefact: those are genuine misses, ~2/match, on boards
where the policy had both the elixir and the counter. `bowler` was 3 of 13.

### Trap added (§8)

**An unmasked card-head sample is not a play distribution.** Sampling the card head without the
in-hand-AND-affordable mask counts plays `eng.deploy()` would reject — it read 153 plays/match
against the masked 38.5, and inflated x_bow from 1.06% to 8.61%. This is the SECOND time this
exact bug produced a wrong number in this project (the first: "tesla played 609 times while dealt
on 283 steps"). `cards.py` and `ledger.py` carry the mask; anything ad-hoc must copy it.

---

## 3s. 2026-08-23 — ALL EIGHT OFFENSIVE BOW WINDOWS SHIPPED, AND THE MEASUREMENT SAYS THEY ARE NOT THE LEVER

Owner asked for every window in DOCTRINE_RESEARCH.md §3A implemented, including W5. Done — and the
measurement that came with it matters more than the feature.

### Shipped

`env._bow_window(spend) -> (reason, is_punish) | None` ORs all eight, replacing the single
`_punish_window` test at the three sites that gate an offensive bow (`_wincon_exec`,
`_xbow_overaggression`'s exemption, `_wincon_reach`). Each window is switchable via
`env.bow_windows: [W1..W8]` so a run can attribute an effect to one of them.

* **W2 (cycle)** — the one the guides rank first — is new machinery: `_opp_cycle_depth(bases)` reads
  the opponent's true deck order (first four entries are the hand) and returns plays-until-in-hand.
  `_opp_can_block_now` only ever saw the current hand.
* **W3** `_counterpush_ready()`, **W4** `_defensive_card_in_hand()` + `bow_full_bar_elixir`,
  **W6/W8** via `bow_killer_spells` (curated, not a damage threshold — §8's "changing what a key
  MEANS is not local"), **W7** conditioned on `_opp_block_cost >= bow_slow_answer_cost` because
  unconditioned it would license the bow for the whole second half of every match.
* **PUNISH vs FAVOURABLE.** W6/W7 are standing matchup properties, not moments. They pay
  `xbow_window_mult` (1.2) rather than `xbow_punish_mult` (1.5) — otherwise they would be a global
  multiplier on the bow wearing a disguise.

### W5, and why NOTHING had to be removed

Owner's rule: *"rocketing the pump immediately applies if the opponent places a pump and x-bow is not
in cycle to punish."* `rocket_the_pump_on_sight` already has `hand=("rocket",)` — the bow is absent,
so the drill was **already** the correct branch and did not need deleting. What was missing was the
other branch: new drill **`bow_punishes_the_pump`** (`hand=("x_bow","rocket")`, rocketing scored as a
FAILURE). Discriminates: nothing 0% / scripted 100% / doctrine 88%. `_pump_rocket` now scales by
`rewards.pump_rocket_bow_frac` (0.0) when the bow is in hand and affordable.

### ⚠⚠ THE MEASUREMENT: THE WINDOWS WERE NEVER THE BOTTLENECK

269 bow-affordable states, m=10000 policy, 12 matches:

```
any window fires   268   99.6%
  W1_elixir        256   95.2%   <-- the ORIGINAL single condition, ALONE
  W4_full_bar       11    4.1%
  W3_counterpush     1    0.4%
  (none)             1    0.4%
```

**W1 alone was already open on 95% of them.** Adding seven windows moved the licence rate 95.2% ->
99.6%. So the offensive bow was never under-licensed, and the x_bow share of 1.06% is NOT explained
by the reward refusing to pay. Do not expect this change to move the bow share.

### ⚠⚠⚠ AND W1 ITSELF IS MISPRICED — clause B fires on 100% of steps

```
_opp_block_cost across 12 decks: min 2.0  median 3.0  max 5.0
opponent elixir:  median 2.07  mean 2.77
clause A  opp < block_cost      :  62.0% of steps
clause B  mine+6 - opp >= 4     : 100.0% of steps   <-- ALWAYS
veto      _opp_can_block_now    :  16.8% of steps
```

`_punish_window` adds the bow's cost BACK to our side (to undo a post-spend read), so clause B is
`elixir + 6 - opp >= 4`. With opponents sitting at a median 2.07, **merely affording the bow
satisfies it**: 0 + 6 - 2 = 4. The threshold and the bow's cost are numerically the same event.

So `xbow_punish_mult` has been the STANDARD rate for every forward bow, not a selective punish. This
also explains the history in the code comment: measured post-spend it *"fired EXACTLY ZERO times in
162 X-Bow plays"*, and adding the spend back overcorrected from 0% to 100%.

**NOT FIXED IN THIS BATCH, deliberately.** `_punish_window` has three callers and the key's meaning
is load-bearing (§8), so retuning it moves every bow measurement in the ledger at once. The doctrinal
answer is that what matters is what is LEFT after paying — the guides' *"only X-Bow at around 10
elixir and when you have a good defensive hand"* is a POST-spend test, i.e. W4's shape, not a
pre-spend gap. **This is the next single change, and it should be measured alone.**

### The opening ban outranks the windows — one named exception

`test_wincon_context_modifiers` caught the windows silently repricing the first 30 s from
`bow_first_frac` (0.25x) to 1.2x. "Never X-Bow the bridge first play" is explicit doctrine and both
outside guides agree — and Theria names the exception: *"avoid playing your X-Bow **unless the
opponent pumps up first**"*. So the ban outranks every window except **W5**. Two tests cover it.

Also updated: that test stubbed `_punish_window` to isolate the non-punish paths; the licence gate is
now `_bow_window`, so the stub had gone stale against the thing it was meant to switch off. It stubs
the gate now, and part (c) keeps it stubbed so `_bow_split_punish` is genuinely consulted.

### CORRECTION to §3A: `_bow_split_punish` is NOT too broad

§3A recorded it as needing a building-targeter exclusion. Re-read: it already returns `not same` for
ground tanks, i.e. it only ever fires for an OPPOSITE-lane bow, which is precisely the out-tempo case
row 79 licenses. The Golem-in-the-same-lane bow the guides forbid never fired. No change needed.

620 tests, 1 pre-existing failure (`test_budget_caps_and_hysteresis_refills`, `_threat_response`).

---

## 3t. 2026-08-23 — DEFENSIVE DOCTRINE AUDIT

Owner asked, after the offensive windows: *"check if there are any defensive segments in the
doctrine that have not been coded yet."* Audited DOCTRINE.md §0 (fundamentals), §1 (niches),
§2 (synergies) and §4 (standing placement priors) against `sim/doctrine.py`, `threat_value.py`
and `sim/env.py`.

### ⚠ FIRST, A CORRECTION I HAD TO MAKE MID-AUDIT

I initially reported the defensive coverage as four cards, reading it off `_bow_defence_cells`
(knight / skeletons / ice_wizard / tesla). Owner: *"every card in icebow deck can be used for
defense, not just the four you listed. Doctrine should agree with me and if not, something is
wrong."* **Correct on both counts, and the doctrine does agree** — DOCTRINE.md §1 gives all eight a
defensive role (X-Bow "second pull building", Rocket "heavy removal", Tornado "drag units off a
lock", Log "knockback/charge-reset"), and so does the code:

* **Placement rules exist for all eight** in `_doctrine_cells_rules`: `tesla`, `x_bow`, `knight`,
  `skeletons`, `ice_wizard`, `tornado`, `the_log`, `rocket`.
* **All eight are nominated defensively** in `doctrine_cards` (tesla 6.0 for their wincon, knight
  4.5 vs melee, skeletons 4.0, ice_wizard 3.5, tornado up to 5.0, log 4.5, rocket, bow 4.0).

`_bow_defence_cells` is only the *bow-bodyguard formation* — one context, not the defensive
inventory. Reading a subsystem's dispatch list as the whole picture was the error.

### CONFIRMED UNCODED (the list is short, because coverage is good)

1. **Log ahead of a locked X-Bow** (§2 synergy — the Log's one offensive-support role).
   `_bow_defence_cells` returns False for `the_log`, so it falls through to the generic ground-swarm
   rule, which targets the **deepest** ground unit in OUR half (`max(ground, key=u.y)`, clamped
   `0.46 <= y <= 0.62`). The defenders walking onto a FORWARD bow stand near the river on THEIR
   side, so that rule can never propose this cast. Worth 1–2 extra bow shots plus a charge reset.

2. **The Balloon chain-pull to the King** — Tesla 4-2, then a defensive bow 6-3 (new, §3A).
   Blocked by the SAME two-card sequencing gap as the doctrinal rocket→tornado order: the cell
   prior scores one placement at a time and cannot say "this card, then that one, in this order".
   One primitive unblocks both; building either as a special case would be building it twice.

3. **4-2 vs 4-3 plant discrimination.** `_spell_pair_risk` generically covers the anti-spell plant
   family, but not the CHOICE: 4-2 pulls **all** units coming off the bridge (better when they hold
   Goblin Barrel / Miner), while 4-3 pulls building-chasers farther from the towers **and** denies
   The Log tower value. Nothing reads their win condition to pick between them.

### PARTIAL

4. **Evo Knight walk-tank + IW slow** (§2). Kiting PEKKA/MK to centre is coded and is close in
   spirit, but *placed to WALK ACROSS the push* is not expressible today — and the evo's −60%
   damage-taken-**while-walking** is exactly what makes it near-free. Needs a path geometry, not a
   spot.

5. **X-Bow + Tesla double-building** (§2). Both spots exist independently (Tesla centre-pull at
   (0.48, 0.585); defensive bow band (0.48, 0.55)), and `_bow_defence_cells` will place a Tesla
   between a standing bow and something attacking it. Missing: the PROACTIVE two-pull formation vs
   RG/Hog — nothing places the second building *because the first is already down*, only in
   reaction to a threat already on the bow.

### ALREADY CODED — and DOCTRINE.md's own "implemented in" column is STALE about F4

* **F1/F2/F3** (triage, threats add, outrange) — `threat_value.py`, as documented.
* **F4** (*"minimise damage, don't prevent it; never spend more than the push cost"*). DOCTRINE.md
  lists this as **"advisor prompt"**. It is not — `elixir_trade` is literally *(enemy value
  eliminated − elixir spent)*, normalised and clipped: F4 priced as a reward on every play in the
  sim, 41 fires in a 12-match ledger. **The doctrine table should be corrected.**
* **F5's "keep the answer in hand"** — `_holdable` in `doctrine_cards`. The "cheapest card that
  works" half is priced implicitly by `elixir_trade` rather than by a rule.
* **§4.1 double-cover** (`_double_cover`, incl. the measured row-15 conflict); **§4.2 anti-spell
  spacing** (`_spell_pair_risk` — the GENERAL form of the guides' 4-2/3-4/4-4/4-6 table, radii read
  from the engine's own specs, so that table does not need transcribing and §8 forbids it anyway);
  **§4.4** IW depth; **§4.5** skeletons cycle corners; **§4.6** nado destinations.

### Ranking, if these get built

(1) is the cheap one — a few lines in `_bow_defence_cells`, fires in a common state, and it is the
only §2 synergy with no expression anywhere. (3) is small and reads only their known cards. (5) is
a weight, not new geometry. (4) needs path geometry. (2) waits for the sequencing primitive and
should be built with rocket→tornado, once.

---

## 3u. 2026-08-23 — W1 REPRICED: the punish window was open 95% of the time, now 39%

The single change flagged at the end of §3s. `_punish_window` had two clauses and **both** were
wrong in the same direction — they asked about the wrong instant and the wrong quantity.

### Clause A: the wrong TENSE — it ignored the bow's 3.5 s deploy

`opp < _opp_block_cost` asked whether they were broke **at the instant of casting**. But an X-Bow
takes 3.5 s to deploy — DOCTRINE.md §1 calls that window the thing "everything about protecting it
happens in" — and elixir accrues throughout it. The blocker that matters is the one they can afford
**when the bow starts firing**, not when it lands.

New `_opp_deploy_lead()` = `bow.deploy_time × eng.elixir_rate()`, both read from the engine so they
track the card data and the elixir phase. It tightens *itself* in double elixir, which is correct:
the same 3.5 s buys them twice the answer.

```
clause A, 148 bow-affordable states:   64.9%  ->  14.2%
```

### Clause B: the wrong QUANTITY — a pre-spend gap with the cost added back

`mine = elixir + spend` then `mine - opp >= punish_elixir_gap (4.0)`. With opponents at a median
2.07 elixir, that is `0 + 6 - 2 = 4` — **satisfied by merely being able to afford the bow**. The
threshold and the bow's price were numerically the same event, so it fired on **100% of steps**.

Replaced by `punish_reserve_gap` (1.0), measured **POST-spend**: what is LEFT to defend with after
paying still has to lead them. That is what the guides actually say — *"only X-Bow at around 10
elixir and when you have a good defensive hand"* is a statement about the **reserve**, not about the
bar you are about to empty. At 10 elixir the reserve is 4 against their 2; at exactly 6 it is 0,
and emptying the bar for a bow is not an elixir advantage.

`punish_elixir_gap` is RETIRED, not repurposed (§8: changing what a key MEANS is not a local
change). It still loads; nothing reads it.

### The call convention, which was also quietly wrong

`_punish_window(spend, cost)`: `spend` adds back what a post-spend caller was already debited,
`cost` takes the bow's price off. `_wincon_exec` passes `spend=cost=6` (already billed);
`_wincon_reach` now passes `spend=0, cost=6` — it runs on a board where **nothing was paid**, and
was previously passing `spend=6` there, overstating our bar by a full 6 elixir. A test pins the two
conventions to the same verdict on the same board.

### Result — and the part that matters most

```
                 before    after      (137 bow-affordable states)
W1_elixir         95.2%    39.4%
W2_cycle           0.0%    19.0%   <- the window the guides rank FIRST
W6_no_big_spell    0.0%     8.0%
W3_counterpush     0.4%     5.8%
W4_full_bar        4.1%     4.4%
W7_late            0.0%     2.9%
(none)             0.4%    20.4%
any window        99.6%    79.6%
```

**Fixing W1 is what made the other seven windows exist.** They were all implemented in §3s and all
inert, because W1 is tested first and was swallowing every state. The eight now form a real
discrimination and a fifth of affordable states get no licence at all.

### Trap (added to §8)

**A probe must use the caller's own frame.** The first re-measurement after this fix reported W1 at
89% — because the probe called `_bow_window(spend=6.0)` on a board where nothing had been paid, so
the "reserve" read as the full bar. The real caller is already debited. Same family as the
live-screen and illegal-coordinate traps: the check and the system under test were looking at
different worlds, and the check was the wrong one.

620 tests + 5 new (`PunishWindowTests`), 1 pre-existing failure
(`test_budget_caps_and_hysteresis_refills`, `_threat_response`).

**hogeq carries its own copy of the old `_punish_window`** (`hogeq/src/clashrl/sim/env.py:933`) and
was deliberately NOT changed: different deck, different win condition, different deploy time. If the
icebow repricing measures well in training, port it there as its own change.

---

## 3v. 2026-08-23 — ⚠⚠⚠ §3p's UNTRAINED BASELINE DOES NOT REPRODUCE. "Training beats untrained" was never established.

**Read this before citing any trained-vs-untrained number in this file.**

§3p is the section that ended the two-day drill-floor investigation, and its conclusion rests on
one table:

```
                              winrate   crowndiff        (untrained: 2.5%, -2.200)
floors 0.30/0.25 (SHIPPED)      6.7%     -1.600     <- "all 3 seeds beat untrained"
```

**The −2.200 does not reproduce at the commit where it was written.** Measured 2026-08-23, git
worktrees at five points spanning §3p → HEAD, 3 random inits × 24 fixed-seed matches each, card
head masked to in-hand-and-affordable:

```
commit    what landed there                          UNTRAINED crowndiff   crowns taken
63909f9   SHIP the drill floor fix  (§3p ITSELF)        -1.722 ±0.100          0.236
20ab936   opponents can use the POCKET                  -1.736 ±0.097          0.139
5cb295d   spell mask ON                                 -1.667 ±0.083          0.181
ebeca9d   RESTORE the drill floor fix                   -1.833 ±0.042          0.153
611ad32   reprice W1                          (HEAD)    -1.708 ±0.087          0.181
```

**Flat.** Every point lies in [−1.83, −1.67]. §3p's −2.200 is ~4.8 SE outside what its own commit
produces. Two consequences, and the second is the one that matters:

1. **The environment never shifted.** I had claimed (2026-08-23, earlier the same day) that the
   baseline drifted −2.200 → −1.75 and that the pocket/spell-mask changes had moved it, so
   cross-date comparisons were void. **That was wrong** — the pocket did not move it, the spell
   mask did not move it, nothing did. Comparisons across those commits are fine.
2. **The "sim rewards learning" result was an artefact of a bad baseline.** Against the untrained
   value that commit actually yields, §3p's trained −1.600 is a gap of **0.12 against noise of
   ~0.14**. It is not a result. Every later decision that assumed a working training loop and went
   looking for reward-shaping problems downstream was standing on it.

### This is the SECOND time an untrained baseline broke a conclusion here

The ledger already records `48bc8e7`: *"CORRECTION: untrained baseline is −13.57, not −6.78"* —
which had likewise made training look like it was destroying a good policy. Same shape, same
load-bearing role, four days apart.

### What is actually true, stated plainly

On a fixed opponent set, untrained and every trained checkpoint measured this session are the same
policy within noise (crowndiff −1.29 … −1.83), and **crowns TAKEN is ~0.18/match everywhere,
untrained included**. A win needs three crowns or a lead at time. The offence has never existed, so
the winrate has never been able to leave zero — and no reward-shaping change downstream of that can
show up in the benchmark.

**Do not run another reward-shaping experiment until a 3-seed A/B shows training beating untrained
on TODAY's code.** `scratchpad/ab3.sh` is that experiment, written and ready; it needs the machine
to itself (§3's RAM constraint: three trainers beside the main run means thrashing, not slowness).

### Trap (§8)

**An UNTRAINED baseline is the load-bearing number in every trained-vs-untrained claim, and it is
the easiest one to get wrong.** It has now been mis-measured twice, and both times a headline
conclusion rested on it. Measure it (a) in the SAME checkout as the trained policy, (b) over
several random inits — one untrained network is a single draw from a wide distribution, and (c)
with the card head masked. It costs no training: a random init's crowndiff is a property of the
ENVIRONMENT, which is exactly why bisecting it across commits is cheap and worth doing.

---

## 3w. 2026-08-23 — `--drill-frac 0.0` AND `--workers 0` WERE BOTH SILENTLY IGNORED

Found while running the §3v A/B. **Two falsy-zero bugs compounding**, and between them the
drills-off arm of every command-line A/B has actually been training *with drills at 0.3*.

### Bug 1 — `--workers 0` silently became 12

```python
workers = int(workers if workers else cfg.get("sim", "rollout_workers", default=0))
```

`0` is falsy, so an EXPLICIT `--workers 0` fell through to `sim.rollout_workers` (**12**) and took
the REMOTE path. The flag's own help says *"0/1 = classic in-process"*; it never did that. Fixed to
`workers is not None`, with the argparse default changed to `None` so "unspecified" and "explicitly
zero" stop being the same value.

### Bug 2 — `--drill-frac 0.0` became "no override"

Then, on the remote path it had just been forced onto:

```python
drill_frac=float(cfg.get("sim", "drill_frac", default=0.0)) or None
```

`0.0 or None` is `None` — and `None` is `RemotePool`'s sentinel for *"no override, re-read
config.yaml in the worker"*. So `--drill-frac 0.0` resolved correctly to 0.0 in the parent, became
`None` crossing the process boundary, and each worker went back to disk and got **0.3**.

The banner printed `drill mix: 0% of episodes are DRILLS` the whole time. **Exactly the class §3q
was written about: individually-correct pieces failing at the seam, with no exception.** Fixed by
always passing the resolved float — a number is never a sentinel.

### Measured, before and after

```
--drill-frac 0.0 --workers 0     BEFORE:  drills 25 (100% of eps, 100% of STEPS), 0W-0L-0D
                                 AFTER:   (see the verification line in the commit)
```

### What this invalidates, and what it does not

* **Every `--drill-frac 0.0` arm run from the COMMAND LINE is void** — it trained at 0.3.
* **Runs that set `sim.drill_frac: 0.0` in config.yaml are FINE.** Both paths read the file, so the
  bug never bit. §3p's *"3 seeds at drill_frac 0.0 gave 0.993/0.922/0.964 (healthy) -- drills ARE
  the cause"* is therefore **unverified, not disproved**: the numbers differ far too much from the
  collapsed 0.11-0.15 to be the same condition, so those runs were probably config edits. **Check
  before citing it.** The code comments at `train_sim_ppo.py:877` and `:1075` cite the same
  measurement and inherit the same doubt.
* **Non-zero overrides were always fine** (`0.02 or None` is `0.02`). Only the zero arm broke.

### It also explains the A/B's other failure

Six runs each launched with `--workers 0` became six runs with **12 workers each = 72 processes** on
16 cores. The logs filled with `bash: fork: retry: Resource temporarily unavailable` and children
dying with `0xC000012D`. That is the §3 RAM/oversubscription failure, arriving through a flag that
was supposed to prevent it.

### Trap (§8)

**`x or DEFAULT` is wrong for any numeric knob whose zero is meaningful.** Both bugs are one
idiom: `0` and `0.0` are falsy, so "explicitly off" and "unspecified" collapse into each other.
This repo has `drill_frac`, `workers`, `wincon_bank_floor`, `deck_pfsp_power` and several reward
weights where **zero is a deliberate setting**, and every one of them is a place this idiom silently
substitutes a default. Use `is None`. And the tell was visible in the log for two runs: a banner
that says one thing while the episode counter says another means the override never reached the
thing it names.

---

## 3x. 2026-08-23 — drill_frac SWEEP: 0.3 IS THE BEST OF FOUR, AND NONE OF THEM BEATS UNTRAINED

The first sweep of this knob where the knob actually worked (see §3w — `--drill-frac 0.0` had been
silently training at 0.3, so every previous drills-off arm was void). 4 arms × 3 seeds, 350 matches
each, from scratch, scored on 40 fixed-seed matches per policy with a 3-init untrained reference.

```
arm          crowndiff             crowns TAKEN      wins/40   x_bow
UNTRAINED    -1.692 +-0.030          0.158 +-0.036      0.7      0.1%
frac 0.0     -1.642 +-0.085          0.142 +-0.017      2.7      0.0%   +0.6 SE
frac 0.02    -1.742 +-0.159          0.100 +-0.029      1.3      0.5%   -0.3 SE
frac 0.03    -1.700 +-0.014          0.167 +-0.008      2.0      0.3%   -0.2 SE
frac 0.3     -1.617 +-0.068          0.233 +-0.008      3.0      0.0%   +1.0 SE
```
(+- is the spread ACROSS SEEDS; the SE column is versus untrained.)

### Conclusions

1. **The shipped 0.3 is the best of the four.** No config change. Owner asked which value to switch
   to; the answer is the one already in place.
2. **LOWERING drill_frac DOES NOT HELP.** 0.02 was the worst arm on every column — worse than
   untrained on crowndiff and on crowns taken. **This kills the hypothesis I had been carrying**
   (that 85%-drill episodes were starving match learning). It is not the lever.
3. **No arm clears untrained on crowndiff.** Best is 0.3 at **+1.0 SE**, which is nothing. At this
   training scale (350 matches) PPO does not produce a policy the benchmark can distinguish from a
   random init — consistent with §3v.
4. **The ONE signal in the table is crowns TAKEN for arm 0.3**: 0.233 ±0.008 vs untrained's
   0.158 ±0.036, about **+2.0 SE**, and 3.0 wins/40 against untrained's 0.7. Marginal, single
   experiment, small budget — but it is the first time anything in this project has moved the
   metric that actually gates the winrate, and it moved in the direction of MORE drills, not fewer.

### What this means for where the fix has to go

drill_frac is settled and it is not the problem. The remaining candidate is the one §3v pointed at:
**the offence has no reachable positive signal.** In the 8k ledger `take_enemy_tower` — the largest
carrot the reward can pay — has **zero fires**, because the policy has never taken a tower; while
the offence-related terms sum NEGATIVE (`xbow_into_push` −4.00 against `wincon_exec` +1.20 for one
fire each). If that ratio survives a proper sample, attempting offence is expected-value negative
and gradient descent is correctly learning to stop trying. **Measure that on a real sample before
changing anything** — those are 1-fire terms and this file already carries two retractions caused by
exactly that kind of extrapolation.

---

## 3y. 2026-08-23 — THE ADVISOR REASONS CORRECTLY; THE BOARD IT IS SHOWN DOES NOT

Owner: *"it still tells the model to hold when the enemy is CLEARLY attacking, and to play log on
air troops (which somehow STILL registers a hit)"* — and asked whether the advisor is worth keeping.
Three separate findings, and **the advisor's judgement is not the fault in any of them**.

### 1. The Log DID register hits on air — `air_bases` was permanently empty (FIXED)

`env.py` built it as `db.names() if hasattr(db, "names") else []`. **CardDB has no `names()`**, so
the guard yielded `[]` every run, `air_bases` was an empty frozenset, and
`log_hits(..., air=air_bases)` never skipped a flying unit. Every live Log cast on Minions / Bats /
Balloon / Baby Dragon scored as a HIT.

```
hasattr(db,'names'): False        is_flying('minions'): True      <- data was fine
air_bases as built:  0 cards      after fix: 21 cards
minions  before HIT=True -> after HIT=False      skeletons stays HIT=True
```

`log_hits`'s guard was written correctly; only the ENUMERATION was broken, and it failed the silent
way. Fixed to iterate `db.cards`, and env now PRINTS the count at startup and shouts when empty.
**The sim engine was never affected** — checked directly, the Log leaves all four air cards
untouched and kills skeletons/goblins. Live reward only, which is why it survived so long.

### 2. Given a correct board, the advisor gets BOTH reported cases right

Four cases added to `tools/llm_eval.py` (which uses the REAL `LLMAdvisor` prompt) reproducing the
reports. All four PASS on `qwen2.5:latest`:

```
minions_log_is_wrong      -> tesla       (not the_log)
bats_log_is_wrong         -> ice_wizard  (not the_log)
fresh_push_do_not_hold    -> tesla       (not HOLD)
hog_committed_do_not_hold -> tesla       (not HOLD)
```

16/20 overall, reproducible (temperature 0.0, identical misses on re-run). Its one HOLD-adjacent
miss runs the OTHER way: `lone_spear_goblins_ignore` -> *tesla* when the answer is *hold*. **It
over-spends on ignorable threats; it does not hold under real ones.**

So the fault is in what reaches it, and `train_rl` already documents where: **(a)** the detector
misses a unit in ~31% of passes (fixed via tracker memory); **(b)** a freshly played enemy card is
team "unknown" for its first seconds — *"precisely the answer window"* — and **(b) is deliberately
unfixed**. Plus a third, in the same gate: `if y < 0.42 or not b: continue`, a DEPTH filter that
ignores anything still on their side of the river, so a Giant just dropped at their bridge does not
count as a threat at all. A push in its first seconds is invisible, the board genuinely looks quiet,
and HOLD is the correct answer to the question actually asked.

### 3. ⚠ THE MODEL-CHOICE COMMENT IN config.yaml WAS BACKWARDS (corrected)

It read *"gemma3:4b scores better (8/10 vs 6/10)"*. On the 20-case set the ordering **reverses**:

```
qwen2.5:latest   16/20   p50 3.08s
gemma3:4b         8/20   p50 1.24s
```

gemma3:4b fails BOTH live-report cases and answers `the_log` in **7 of its 12 misses** — precisely
the behaviour the owner reports. Switching on the strength of the old comment would have made live
play worse. Corrected in place with the numbers and a "re-run the eval before changing this".

### ⚠ OPEN, and it may make the whole question moot

`llm_advisor_timeout_s: 0.55` while the config's own comment claims **0.590s p50** — by its own
figure more than half of calls miss the budget and fall back to a RANDOM card. (The 3.08s measured
here was with the GPU at 99% from a PPO run, so it is an upper bound, not the live number.)

**Before arguing about the advisor's judgement, read what it actually did:** `train_rl.py:1103`
prints `llm-advisor <model>: N calls, N answered (X%), N failed, mean N ms`. If answered% is low the
advisor is barely running, and "I haven't seen much change with it on" has a much duller
explanation than model quality.

### ⚠⚠ RESOLVED, AND IT MOOTS THE WHOLE DEBATE: THE ADVISOR HAS NEVER ANSWERED IN LIVE PLAY

Owner supplied the line this section asked for, from their last live session:

```
[train-rl] llm-advisor qwen2.5:latest: 10 calls, 0 answered (0%), 10 failed, mean 565 ms,
           last error TimeoutError: timed out
```

**0% answered.** 565 ms mean against `llm_advisor_timeout_s: 0.55` (550 ms) -- every call misses,
by about 15 ms, and falls back to a RANDOM card.

**Cause: a config drift from a change to a different key.** The budget was sized for a 1.0 s
act_period; `play.act_period` was lowered 1.0 -> 0.6 on 2026-08-20 with `sim.agent_dt` (S3m), and
the advisor's budget was never revisited. The comment on the timeout line still SAID "act_period is
1.0s" until today. A reaction-time change three days earlier silently switched the advisor off, and
the failure mode is a silent fallback, so nothing announced it.

**Raising the timeout does not fix it.** The bot is blind during the call, so a ~590 ms answer
inside a 600 ms period leaves nothing for perception or action. Synchronously this model does not
fit this act_period. Real options: run it ASYNCHRONOUSLY (answer applied on a later decision), a
~150 ms model (qwen2.5:0.5b -- scores badly), raise act_period back toward 1.0 (gamma / n_step /
the per-tick reward scale all move with it), or leave it OFF and rely on the counter table, which
is already the documented FAST PATH and resolves the researched cases in microseconds.

### THIS RE-EXPLAINS BOTH LIVE REPORTS -- neither was the LLM

With 0% answered the advisor produced no card at all, so:

* **"tells the model to hold when the enemy is CLEARLY attacking"** = the CODE's quiet-board rule,
  `if not needs_answer: ... return (0, 0, 0)` in train_rl. Which is fed by the `y >= 0.42` depth
  filter -- so the owner's separate instinct that the depth filter was implicated was RIGHT, by a
  route neither of us had argued.
* **"plays log on air troops"** = the RANDOM fallback (the counter table only fires when it has a
  row for the threat), and then the empty-`air_bases` bug scored it as a HIT.

The 16/20 eval score is still valid -- it just describes a component that has never been in the loop.
**Do not tune the advisor's prompt or model on live observations until answered% is non-zero.**

### Method note

An on/off A/B in live play was the wrong instrument for this question and I proposed it first: it
confounds advisor reasoning with detector noise, the unknown-team window and the veto logic, and it
costs hours of the owner's live play. The offline harness isolates the reasoning cleanly in ~90 s.
Reach for the A/B only once the board description is trusted.

---

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

### ⚠ CORRECTION TO §4a's WORDING — "the policy plays constantly" is false as written

§4a's premise was that nothing pays for a correct wait, so *"playing is weakly dominant at every
decision"* and the policy therefore plays constantly. The trainer's own telemetry says the gate
plays on **~3% of steps**, and has in every run for days:

```
run                    play% trajectory (first four updates ... last four)
ppo_run_night1      5.1 2.2 2.9 2.4  ...  3.4 3.3 3.6 3.0
ppo_run_dose10      5.1 2.0 3.2 2.1  ...  3.3 3.4 3.2 3.3
ppo_run_lever2      5.1 1.9 2.9 2.3  ...  3.2 3.4 2.9 3.5
ppo_run_crown3x     5.2 2.0 3.1 2.2  ...  2.9 2.9 2.7 2.9
ppo_restraint       5.1 2.2 3.0             <- fix 1, indistinguishable from all of them
```

**The two figures have different denominators, and both are correct:**

* the trainer's `plays are X% of steps` is `play = (g_b == 1)` (train_sim_ppo.py:1001) — the gate
  action ACTUALLY TAKEN, over ALL steps;
* `train_sim_ppo.py:434` masks the PLAY logit to `_NEG` whenever `none_play = ~playable.any(1)`,
  so on any step where nothing is affordable the gate is **FORCED** to wait — and that forced wait
  is recorded as an ordinary `g_b == 0` and counted in `n_wait`;
* the watcher's `P(play) 0.569` is conditional on a play being LEGAL.

At the measured ~5-12% affordability, `0.57 x 0.08 ~= 3%`. The two reconcile exactly. The
defensible claim is **"when the choice is real it plays ~57% of the time"**, which drains the bar
to ~2 and makes most later steps unaffordable. The elixir evidence fits that and does not fit the
raw rate: at a genuine 3% play rate the bar would climb to the cap and `leak` would fire constantly,
and for m=26000 `leak` fires **zero** times.

**Fix 1 survives this correction, and for a specific reason worth keeping:** guard 2 requires a
counter in hand AND affordable, so `restraint_hold` can only fire on the conditional decision —
the same denominator the problem lives in. **It cannot pay for a forced wait.** Had the guard been
written on "a threat is present" alone, this correction would have retired the fix.

### ⚠ UNADDRESSED, and it is in the code as a comment nobody carried forward

`train_sim_ppo.py:1098` records a measured finding that is a bigger effect than anything §4a
proposes: **`drill_frac 0.0` holds P(play) at 0.92-0.99, and four runs at 0.3 collapse it to
0.11-0.15.** Every run under discussion uses `drill_frac: 0.3`. The comment poses the mechanism
question and the current run answers it — on MATCH steps (drills excluded by construction):

```
gate drift on PLAY -0.41582  on WAIT +0.00574   (n_play 14, n_wait 294)
gate drift on PLAY -0.08759  on WAIT +0.00598   (n_play  9, n_wait 241)
```

Push is negative on PLAY and positive on WAIT **on match steps**, which is the comment's own
"drills corrupt something SHARED (advantage normalisation over the mixed batch, or the critic),
poisoning match steps too" branch — not the "drills directly teach the gate to wait" branch.
Related telemetry, same run: `clip rate PLAY 0.536 vs WAIT 0.006`, `gradient KILLED PLAY 0.225 vs
WAIT 0.004`, and `26.7% of plays ALREADY outside the 1.20 clip before any step`. With n_play ~14
per diagnostic sample the play branch is estimated from very few samples, which is self-reinforcing:
fewer plays -> noisier play gradient -> more clipping -> gate drifts off play.

**This is a candidate cause of the run-degrades-after-a-while pattern the owner has reported across
several runs regardless of what was changed.** It is NOT a reward defect, so fixes 1-3 cannot touch
it, and it is a different mechanism from fix 4's curriculum oscillation. Queue it as its own
experiment; do not bundle.

### THROUGHPUT — there is no speedup available, and the slow run was a DUPLICATE

Owner asked for faster test runs. Three levers measured, all flat:

```
lever                       result
OMP_NUM_THREADS 1 vs 2      0.70 vs 0.70 ep/s     no effect
--device cpu vs cuda        0.50 vs 0.50 ep/s     no effect (see caveat)
more workers                CPU already 96-100%   no headroom
```

**The actual cause of the slowness was a STALE RUN still alive** — killed with Git-Bash `pkill`,
which is the §2 trap, already documented from yesterday and repeated anyway. 28 processes, CPU
pinned, free RAM **0.8 GB**. Killed via PowerShell: RAM recovered to 5.6 GB. **Before diagnosing
throughput, count the processes.**

⚠ **The device A/B is weaker than it looks.** With `--envs 192` episodes complete in WAVES, so a
cumulative `ep/s` read at 100 episodes is partly wave timing rather than throughput. Both arms read
0.50 at ep100; treat that as "no visible difference", not as a clean 1.00x.

**`--device cpu` is still preferred** — same measured throughput, and it frees the GPU entirely,
which matters because the LLM advisor cannot load qwen2.5 while a trainer holds the card.

⚠ **The CLI help's claim that CPU is 5x faster for this trainer (1.0 vs 0.2 match/s) DID NOT
REPRODUCE.** It is stale; do not plan around it.

---

## 4c. 2026-08-24 — FIX 1 PAIRED READ AT 650 MATCHES: it changes behaviour, and two of four changes are wrong

First trustworthy read, using the pinned-determinism PAIRED design (same 12 seeds, both arms,
`torch.set_num_threads(1)` + `PYTHONHASHSEED=0`). Everything measured before this is withdrawn.

```
                     m=26000      restraint@650      delta
plays              570 (13.9%)    443 (11.4%)       -2.5pp
elixir median         2.14           2.86           +0.72
restraint_hold        0.67/m         1.00/m         +0.33  (sem 0.26 / 0.28)
threat_miss_idle      2.25/m         4.00/m         +1.75  (sem 0.43 / 0.79)   <-- WRONG WAY
leak                  0.75/m        10.83/m        +10.08  (sem 0.41 / 5.28)   <-- WRONG WAY
wincon_exec           1.67/m         2.83/m         +1.16
take_enemy_tower      0.50/m         0.50/m          0.00
```

**Intended direction present:** plays down, elixir banked up. That is what fix 1 was for.

**`threat_miss_idle` DOUBLED, and that is the diagnostic one.** `restraint_hold` and
`threat_miss_idle` are mutually exclusive BY CONSTRUCTION -- same `bodies_ignore_frac` call on the
same committed group, so a board is either worth answering or worth ignoring, never both. Targeted
restraint would hold this term flat or lower it. Doubling means the policy is learning **"waiting
pays"** in general rather than "waiting on IGNORABLE threats pays" -- the over-generalisation the
three guards exist to prevent.

**`leak` rose 14x**, the same hoarding signature that got `wincon_reach: 2.0` reverted. Weaker
(sd 18.3, ~1.9 sigma) but pointing the same way.

The magnitude ratio moved **0.30 -> 0.25**: the penalty is outgrowing the credit, so the policy is
currently NET-LOSING from this behaviour (-4.00 missed threats against +1.00 restraint credit). A
converged policy would not choose that, which is evidence for the confound below.

⚠ **CONFOUNDED, and the confound is large.** 650 matches is deep in the warm-start critic dip
(`vl` still climbing 0.717 -> 1.027; §4a measured the bottom at ~1,700 episodes and most recovery
by ~7,600). §4a's own rule says compare run-vs-run at matched episodes, not a mid-run checkpoint
against its init.

### ⚠ VERDICT AT 2600 EPISODES: THE EXPERIMENT CANNOT ANSWER THE QUESTION (design flaw)

The @650 alarm WAS the critic dip and reverted in full -- that call was right, and by the
pre-committed rule fix 1 is cleared of teaching blanket inaction:

```
                  base(n=30)   @650      @2600(n=30)   paired delta   sigma
threat_miss_idle    2.87       4.00        2.60          -0.27        0.5
leak                0.43      10.83        1.20          +0.77        1.2
restraint_hold      0.63       1.00        0.50          -0.13        0.8
elixir median       2.14       2.86        2.14           0.00         -
plays_pct          13.2       11.40       13.0           -0.2          -
```

**But nothing here is attributable to fix 1**, because the run is warm-started and the comparison
is against its own init -- see the new S8 trap. A sign test over the ledger says 16 of 21 terms
moved NEGATIVE (p=0.027), which is a general decline and is exactly what the warm-start tax alone
produces at this episode count. **Not "fix 1 is neutral" -- the design has no power to say either
way.**

WITHDRAWN (both were n=12 artefacts): "restraint_hold 0.67 -> 0.33, training made the rewarded
behaviour less frequent" (0.8 sigma at n=30), and "offence down / defence up, fix 1 suppresses the
win condition" (a hand-picked five-term partition; the aggregate offence test is 1.9 sigma and
falls in 18 of 30 matches where chance is 15).

### DECISION (2026-08-24): RUN TO 4000, THEN RUN THE MATCHED CONTROL

The control -- same init, same episodes, `restraint_hold: 0` -- is worth more than the fix-1
verdict: it is the **matched-episode reference baseline this project has never had**, and every
future reward experiment needs it. ~2.5 h.

### (superseded) original plan: PROBE AT 2000 / 3000 / 4000

A single endpoint cannot separate "the dip did it" from "the reward did it"; the TRAJECTORY can, and
the run is already launched with `--matches 4000` so it costs only probe time.

```
threat_miss_idle 4.0 -> 3.0 -> 2.3   =>  dip artifact, fix 1 clean, proceed to fixes 2+3
threat_miss_idle flat or rising      =>  credit teaches blanket inaction; REPAIR before 2+3
```

Repair, if needed, in order of preference:
1. dose `restraint_hold` 1.0 -> 0.5 (keeps the term live at ~0.15 of the penalty, still above the
   0.04 that measured decorative);
2. tighten guard 1 -- require the ignorable threat to be closer/committed, so fewer boards qualify;
3. only if both fail, gate the credit on `threat_miss_idle` not having fired in the same match.

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

Three arms from the SAME init (`policy_BEST_m26000_20260823.pt`), matched at the same episode
count, differing in exactly one thing each. The warm-start critic dip is present in ALL arms, so it
CANCELS -- which is precisely what every earlier reward experiment here was missing.

```
arm        restraint_hold   env.py       episodes
control         0.0         unpatched      2600 / 3600
fix 1           1.0         unpatched      2600 / 3600
fix 2+3         0.0         PATCHED        2600
fix 4            -          -              no run (validated synthetically)
```

### FIX 1 — FAILS its pre-committed criterion (paired, n=30)

```
                   control@2600   fix1@2600   paired delta   sigma
restraint_hold        1.30           0.60        -0.70        2.9   <-- WRONG WAY
threat_miss_idle      4.67           2.60        -2.07        2.8
plays                11.4%          13.0%
elixir median         2.64           2.14
```

Criterion was "`restraint_hold` fires MORE and `threat_miss_idle` does not rise, >=2 sigma".
**Clause 1 FAILS at 2.9 sigma in the wrong direction**: the policy trained WITH the restraint credit
performs the credited behaviour LESS THAN HALF as often as the control. Clause 2 passes -- missed
threats fell 2.07 (2.8 sigma), so it is not defensively harmful.

The picture is coherent: fix 1 made the policy MORE ACTIVE, not more restrained. It plays more
(13.0% vs 11.4%), banks less (elixir 2.14 vs 2.64), and therefore has fewer of BOTH idle-event
types. **Paying for restraint produced less restraint.**

⚠ MECHANISM NOT ESTABLISHED, only the effect. A plausible candidate worth testing before any
re-dose: a positive term available on idle steps raises the CRITIC'S BASELINE for those states, and
since the credit is small and capped (2.0/match, realised ~0.5), the realised return can fall SHORT
of the raised baseline -- making idling look WORSE in advantage terms than before the credit
existed. If that is right, a bigger dose does not fix it and may invert it further; the term would
need to be uncapped or moved off the idle step entirely.

### FIXES 2+3 — FAIL their pre-committed criterion (paired, n=30), and in the predicted way

```
                 control@2600   fix23@2600   paired delta   sigma
xbow_lock            8.93          3.20         -5.73        2.1   <-- WRONG WAY
chip_linear          9.23          3.33         -5.90        2.1   <-- WRONG WAY
xbow_defends         6.93          4.40         -2.53        1.0
xbow_no_lock         0.27          0.07         -0.20        1.8
plays               11.7%         11.0%
elixir median        2.57          2.79
```

Criterion was "`xbow_lock`/`chip_linear` UP, `xbow_no_lock` present, `xbow_defends` firing, >=2
sigma". **Both primary terms moved DOWN at 2.1 sigma** -- a 64% fall in bow uptime and in the bow's
damage lane.

**The policy is not playing BETTER bows, it is playing FEWER bows.** `xbow_no_lock` did fall
(0.27 -> 0.07) -- fewer useless bows -- but `xbow_lock` fell just as hard, so the useless bows were
removed by removing bows, not by improving them.

⚠ **THIS WAS PREDICTED IN WRITING BEFORE THE RUN**, in fix23.py's own docstring and in the note to
the owner: *"There is no existing penalty for a blocked bow (S4a corrected that belief), so 2a
already removes a credit; stacking a large penalty on top would suppress bow play further while
x_bow share is ALREADY collapsing."* The dose was deliberately kept small (-0.5) for exactly this
reason and it was still enough. **Penalising a bad OUTCOME of an action suppresses the ACTION** --
the policy cannot tell "play a better bow" from "stop playing bows", and the second is cheaper.

**REVERTED FROM THE TREE 2026-08-25.** A measurably-failing reward change left in place
contaminates every experiment after it -- fix 4, fix 5 and the entropy A/B all need a clean
baseline. The patch is preserved in `scratchpad/fix23.py` for the adjustment round. The three
tests that require the new terms were removed with it; **the corrected
`test_overcommit_credit_on_bow_death` STAYS**, because its repair is true of the unpatched reward
too -- the fixture's bow sat at y=0.60, 12.7 tiles from the enemy princess against an 11.7 range,
so it could never have locked a tower and the test was crediting a bow that was physically
incapable of threatening anything. Suite green at 625.

If this is retried, the penalty has to be removed and only the CREDIT GATE (2a) kept, so a useless
bow earns nothing rather than costing something -- or the penalty has to be conditioned on a bow
that was placed in range, so it cannot be avoided by simply not playing the card.

### FIX 4 — PASSES, and it is SHIPPED (the only fix of the three that worked)

Re-measured on the shipped code by replaying the controller's exact arithmetic against a synthetic
winrate held CONSTANT, so every difficulty move is by construction pure noise response:

```
noise-driven move rate:  current 52.5%  ->  deadband 0.06  0.2%
lag on a REAL step change (8% -> 20%):  current 236 matches  ->  0.06  199 matches
```

**Strictly better on both axes**: it removes 99.6% of the noise-driven movement AND tracks a real
change FASTER, because the rate limit is no longer being spent on coin flips. That is why it ships
as one line with no trade-off to weigh.

Widening the sensor window 50 -> 200 was measured and **REJECTED**: +0.1pp of noise immunity for
1.8x the tracking lag (199 -> 353 matches). The first draft of this fix contained it.

⚠ Validated SYNTHETICALLY, not by a training run -- deliberately. In a live run the policy and the
controller move together, so no difficulty change is attributable, and this run's difficulty spent
long stretches pinned at the 0.15 floor where the defect cannot appear at all. Replaying the
controller in isolation is the stronger evidence here, not the weaker. Harness: `scratchpad/curr_sim.py`
-- re-run it before ever changing `curriculum_deadband`.

### ⚠ MEASUREMENT BUG CAUGHT BEFORE IT PRODUCED A VERDICT

The first run of this comparison reported `restraint_hold 0.00` in BOTH arms. The probe reads the
CURRENT config, and the control arm trains at `restraint_hold: 0.0` -- so the TERM WAS DISABLED IN
THE EVALUATION ENV and could not fire whatever policy was loaded. The instrument was switched off,
not the behaviour absent (same shape as `air_bases` and `--drill-frac 0.0`).
Fixed by forcing `e.w_restraint` on the ENV INSTANCE (`PROBE_RESTRAINT_W`), never by editing
config.yaml: workers call `Config.load()` in their own processes, so a mid-run edit would have been
picked up by a respawn and contaminated the control. The cap is lifted for counting too -- at
w=1.0/cap=2.0 the count saturates at 2/match and cannot tell "restrained twice" from "nine times".

## 4g. 2026-08-25 — FIX 6 SHIPPED: the cheap answer in the OTHER lane was worth nothing

Owner's doctrine, and he is right: prioritising the greater threat must not mean IGNORING the
lesser one. Golem + support one side, a Mini Pekka the other -- the golem is the bigger threat, but
the mini pekka still needs an answer, cheaply (Skeletons usually suffice).

MEASURED on exactly that board, BEFORE the fix:

```
threat_response for the correct Skeletons in the mini-pekka lane   +0.000
threat_miss_idle fires, answered vs ignored                         5 vs 5
TOTAL dense step reward, both lanes vs golem only                  +0.05
our princess HP, both lanes vs golem only                          +2266
```

**The correct play saved ~2266 tower HP and the dense reward paid +0.05 for it.** Two causes:
* `_threat_response` requires the card to counter the PRIMARY identity in the PRIMARY lane, so a
  correct second-lane answer scores exactly zero;
* `_threat_miss_idle`'s waiver is GLOBAL -- `any(our unit counters tid)`, no lane test -- so once
  the golem is answered, ignoring the mini pekka is free.

That left only the DELAYED tower-survival outcome, which is the long-horizon credit assignment this
critic handles worst -- see the whole warm-start/critic-dip story.

### The fix, and what it deliberately does NOT do

`_secondary_lane_response` pays for a correct answer to a committed threat in a lane OTHER than the
primary, judged on that lane's OWN identity, OWN triage and OWN danger:

```
                              BEFORE     AFTER
skeletons in mini-pekka lane   0.000    +0.949     (= mini_pekka 0.667 / golem 0.703)
skeletons in the GOLEM lane      -       0.000     (primary is _threat_response's job)
empty lane                       -       0.000
TRICKLE in the second lane       -       0.000     (triage refuses it)
```

⚠ **IT ADDS A CREDIT AND DOES NOT TOUCH THE PENALTY.** Making `_threat_miss_idle` lane-aware would
make it fire MORE, and that term has been the dominant negative in this ledger TWICE (-152.00 over
152 fires in 323 steps; 1595 fires / 100 matches) -- both times teaching the policy to empty its
bar, the exact failure this project has spent a week undoing. If the credit proves insufficient,
the waiver is the NEXT lever, not this one.

The credit is the SAME for skeletons, knight and tesla, on purpose: "cheapest sufficient answer" is
enforced by the credit BUDGET (`min(threat_credit_budget, n_cards)`, added in `a925d88` precisely to
stop over-answering paying) plus elixir cost, not by varying this term.

**6 tests added; all 6 ERROR on the unpatched tree, so they detect the fix rather than merely
passing.** icebow 635 tests OK.

⚠ **THIS INVALIDATES ANY CONTROL ARM TRAINED BEFORE IT** (owner flagged this). `ARM_control2.pt` was
stopped mid-run and discarded; the adjustment round needs a fresh control on the fix 4+5+6 tree.

## 4h. 2026-08-25 — FIX 7 SHIPPED: the missed-defence penalty was a STEP FUNCTION

Owner's idea, and the measurement is stronger than the framing suggested. `_threat_miss_idle` is not
flat, it is a step: free below `IGNORE_FRAC` (0.05), a full -1.0 above it. Measured on real boards:

```
committed group            ignore_frac   BEFORE    AFTER
one skeletons                    0.004     0.000    0.000   (waived)
two trickles together            0.107    -1.000   -0.107
one knight                       0.302    -1.000   -0.302
one mini pekka                   0.667    -1.000   -0.667
two mini pekkas                  2.108    -1.000   -1.000   (capped)
golem + mega minion              2.074    -1.000   -1.000   (capped)
```

**Ignoring two trickles cost exactly what ignoring a golem push cost -- a 19x difference in real
threat priced identically.** The quantity that fixes it was already being computed ON THAT LINE:
`bodies_ignore_frac` IS "how much tower does this cost me", and it was thresholded and then thrown
away.

### The second benefit is bigger than the fidelity one

`threat_miss_idle` has been the DOMINANT NEGATIVE TERM in this ledger **twice** -- -152.00 over 152
fires in 323 steps (86% of a hold-policy's entire penalty), and 1595 fires / 100 matches at -16/match
(3x the next term). **Both times it taught the policy to empty its bar**, which is the failure this
project has spent a week undoing, and which fix 1 was itself an attempt to counteract. Real fires
land mostly at 0.3-0.7, so proportional pricing roughly HALVES the term's magnitude **while making
it more accurate**. Fidelity up and a known failure mode defused in one change.

⚠ **The `IGNORE_FRAC` early return is KEPT, and not because it is harmless.** The term is
rate-limited by `threat_miss_period` (4 s) and the limiter arms whenever it fires. A 0.004 fire for
a lone Skeletons costs nothing itself but would ARM THE LIMITER and mask a real push arriving a
second later. The threshold's real job is to keep trivial threats from consuming the rate limit, and
that job survives. What it stops doing is pricing a 0.107 board like a 2.074 one -- the cliff at the
boundary falls from (0 -> -1.00) to (0 -> -0.05).

Capped at 1.0 on purpose: this term is a PROXY that makes delayed tower damage learnable, not a
replacement for the outcome terms, so a two-tower push must not out-shout what it stands in for.

4 tests added; 2 of the 4 FAIL on the unpatched tree (the two that assert ordering and magnitude).
icebow 639 tests OK.

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

Owner's decision, on the evidence below: **drop it, but keep it available in case later runs go
sideways.** It is already in exactly that state -- `_restraint_hold` remains in `env.py` and is INERT
because `rewards.restraint_hold: 0.0`. **Re-enabling is one config line; there is no patch to
re-apply and nothing to reconstruct.**

### Why it was dropped

```
                          m=26000   OLD control   fix1 arm   control4 (4+5+6+7)
elixir median               2.14      2.57-2.64     2.14         2.79
restraint behaviour/match   0.63        1.30        0.50         1.40
threat_miss_idle /match    -2.87       -4.67       -2.60        -3.32
```

**With NO restraint credit, the corrected reward produces 2.8x the restraint behaviour fix 1
achieved (1.40 vs 0.50) and the best banking measured in this project (2.79).**

Fix 1 was a COUNTERWEIGHT to `threat_miss_idle` being over-sized. Fix 7 corrected that term at the
source -- measured on control4, it now fires at an average **-0.573**, not a flat -1.0, and its
per-match magnitude fell -4.67 -> -3.32 despite MORE fires (5.80 vs 4.67). So the thing fix 1 was
built to offset no longer exists at the size that motivated it, and its own measured failure mode
(reward a state -> get LESS of it, -0.70 at 2.9 sigma) makes a retry likely to misfire again.

⚠ **HONEST LIMIT ON THIS EVIDENCE.** control4 carries fixes 5+6+7 TOGETHER, so this is not a clean
isolation of fix 7, and it is not a paired comparison -- different arms, different seeds. Strong
evidence, not proof. The asymmetry is what decides it: shipping an unneeded reward term makes it
uncontrolled noise in every future experiment, while dropping it costs nothing measurable.

### RE-ENABLE IT IF, AND ONLY IF, THESE APPEAR

Set `rewards.restraint_hold: 1.0` (cap 2.0) again if a later run shows BOTH:
1. **elixir median falling back toward ~2.1-2.3** (the dumping signature), AND
2. **restraint behaviour/match dropping below ~0.8** measured with the probe's instrument FORCED ON
   (`PROBE_RESTRAINT_W=1.0`, cap lifted -- otherwise the counter is off and reads 0.00 whatever the
   policy does; see the trap in 4f).

⚠ If they do appear, DO NOT simply raise the dose. The measured failure was directional, not
magnitude-limited, and the standing hypothesis is that a capped positive term on idle steps inflates
the CRITIC'S BASELINE for those states until idling looks worse in advantage terms than before the
credit existed. Change the SHAPE first: pay once when an ignored threat expires harmlessly, rather
than per idle tick.

## 4k. 2026-08-25 — FIXES 4, 5, 6, 7 PORTED TO HOGEQ (2+3 and 1 deliberately not)

### What was ported, and what was NOT

```
fix 4  curriculum deadband 0.02 -> 0.06      PORTED   trainer-level, deck-agnostic
fix 5  _threat_pos ranks by DANGER           PORTED   hogeq's copy was byte-identical to the bug
fix 6  secondary-lane response               PORTED   anchor adapted (see below)
fix 7  proportional miss penalty             PORTED   deck-agnostic
fix 2+3  x_bow credit gate                   NOT      X-BOW SPECIFIC -- hogeq has no x_bow, and the
                                                      retry is still under test in icebow
fix 1  restraint_hold                        NOT      dropped in icebow; hogeq never had it (0 refs)
```

### Generated, not retyped

The hogeq patches are DERIVED from the icebow patch files by a script, not hand-copied. This repo's
ledger already records several bugs that lived in one deck only because a "cross-deck" fix was
applied by hand to one side. Deriving them makes the logic identical by construction; only the
ANCHORS are adapted.

**One adaptation was needed:** hogeq's `_punish_window(self, spend)` has no `cost` kwarg, and fix 6
uses that line purely as an INSERTION POINT for the new method. Cosmetic, but the anchor had to
match or the patch would have failed closed (which it did, until adapted).

**Every anchor and dependency was verified in hogeq BEFORE writing any patch** -- including
`threat_value.ignore_cost_frac`, which fixes 5 and 6 both need and which hogeq's `env.py` had never
called (the function exists in its `threat_value.py` with an identical signature; an early check
that grepped the wrong file said MISSING and was wrong).

### Verified behaviourally on HOGEQ's OWN deck (hog/firecracker/mighty_miner/tesla/log/EQ)

```
FIX 5  pekka(1.907) shallow vs skeletons(0.004) DEEPER -> _threat_pos x=0.25  (the PEKKA, correct)
FIX 7  knight -0.302 | mini pekka -0.667 | golem+mega_minion -1.000   (was -1.000 for ALL)
FIX 6  skeletons in the mini-pekka lane -> +0.949                      (was +0.000)
```

### Test result, against a MEASURED pre-port baseline

⚠ **hogeq's suite is NOT green and was not green before this.** Measured by stashing the ports and
re-running: **3 failures + 39 errors = 42, identical before and after** -- which is exactly the
"hogeq at its 42 baseline" this ledger has been quoting for days. 14 tests ported
(`ThreatPositionTests`, `SecondaryLaneTests`, `MissPenaltyScaleTests`), **all 14 pass**, suite
692 -> 706 tests, **zero regressions**.

**That 42-failure baseline is itself an open problem**: a suite with 42 known failures cannot be
trusted to catch a regression in this deck, which is why the ports were ALSO verified behaviourally
above rather than on test results alone. Worth its own session -- see the icebow precedent, where
one long-red test turned out to be STALE rather than broken and was masking the defensive path.

## 4l. 2026-08-25 — CROSS-DECK DIVERGENCE AUDIT (owner asked for both folders 100% current)

Compared every shared module by hash: **58 of 78 identical**, 20 differ, and only
`sim/drills_{icebow,hogeq}.py` are deck-exclusive. Line-count divergence alone does not separate a
MISSING BUG FIX from icebow-only diagnostics, so each known ledger fix was checked by signature.

### ⚠ FOUND LIVE IN HOGEQ: the `air_bases` bug — the Log's air exclusion is INERT

```python
# hogeq, before:
self.air_bases = frozenset(b for b in (db.names() if hasattr(db, "names") else [])
                           if db.is_flying(b))
```

`CardDB` HAS NO `names()`, so the generator iterated an empty list. **MEASURED: 0 cards instead of
21 flying.** The guard was written correctly and `is_flying` was fine; only the enumeration was
broken, so every call succeeded while the rule did nothing. **This is the owner's repeatedly-reported
"the Log still registers a hit on air troops" -- and `the_log` IS in the hogeq deck**, so that deck
has been scoring Log casts on flying units as hits the entire time. Fixed, with the same loud
empty-set diagnostic icebow carries.

### ALSO PORTED: falsy-zero `--workers 0`

hogeq still had `workers if workers else ...`, so an explicit `--workers 0` was silently replaced by
`sim.rollout_workers`, took the REMOTE path, and made "in-process, no workers" unreachable from the
CLI. Same family as `--drill-frac 0.0` (S8).

### DELIBERATELY *NOT* PORTED, with reasons

```
critic split + value_d      icebow has `ppo_value_head_split: false` -- TRIED AND REJECTED.
                            Porting a disabled experiment adds dead code and invites someone to
                            switch it on without re-reading why it was turned off.
ASYNC advisor               icebow has `llm_advisor_async: false` -- reverted 2026-08-25 on the
                            owner's slow-reaction report. Porting it would spread a known regression.
drill play-out              ✅ PORTED 2026-08-25 -- and my "cannot be ported" call above was WRONG.
                            I had searched for icebow's COMMENT text, which naturally differs
                            between decks, instead of the CODE sites. The structures are nearly
                            identical (`if v is not None:` + `done = True` vs the guarded form), and
                            all four sites ported cleanly. See 4m.
fixes 2+3                   x_bow specific; hogeq has no x_bow.
fix 1                       dropped in icebow; hogeq never had it.
```

### THE REAL LESSON HERE

`air_bases` was fixed in icebow days ago and the identical bug sat untouched in hogeq the whole
time, while the owner kept reporting the symptom. **A fix is not done when one deck is green.** The
audit that found it took minutes; the bug survived weeks. Run this comparison after any shared-module
fix.

## 4m. 2026-08-25 — PLAY-OUT PORTED TO HOGEQ, AND THE VERIFICATION FOUND A LIVE BUG IN ICEBOW

### ⚠ CORRECTION: "cannot be mechanically ported" was wrong

I reported play-out as a rewrite because 3 of 4 anchors were missing. **I had searched for icebow's
COMMENT text, which differs between decks by nature, rather than the code sites.** The structure is
nearly identical:

```
icebow:  if v is not None and self.last_verdict is None:  ... done = bool(done) or not self._play_out()
hogeq:   if v is not None:                                ... done = True
```

All four sites ported: `import os` + env globals, `_play_out()`, the verdict site, and the LENGTH
SEED. **The length seed is not optional** -- `_episode_prob` solves
`target = p*Ld / (p*Ld + (1-p)*Lm)`, so with play-out ON a 20.0 seed is wrong by ~25x (measured in
icebow: drills took 81% of STEPS against a configured 30%). Porting sites 1-3 without it would have
been worse than not porting.

VERIFIED behaviourally on hogeq: `play-out off -> episode ends at step 10` (its verdict);
`play-out ON -> verdict still at step 10, episode continues to step 501`. Config key
`sim.drill_play_out: true` added to hogeq.

### ⚠⚠ THE VERIFICATION FOUND A LIVE BUG IN **ICEBOW** — `CLASHRL_DRILL_PLAY_OUT=0` TURNED IT **ON**

```python
_PLAY_OUT_ENV = bool(os.environ.get("CLASHRL_DRILL_PLAY_OUT"))    # bool("0") is TRUE
```

**Any non-empty value -- including `"0"` and `"false"` -- evaluated True, so the override could only
ever ENABLE play-out, never disable it.** That flag exists specifically for command-line A/Bs, which
means **any A/B run as `CLASHRL_DRILL_PLAY_OUT=0` vs `=1` compared the feature against ITSELF** and
would have reported "no difference" for a change that is worth 50x the episode length.

Third member of the family, after `--drill-frac 0.0` and `--workers 0`: **a falsy value the code
could not express.** Now parsed properly (`""`/`0`/`false`/`no`/`off` -> False) in BOTH decks, with
proof: `icebow =0 -> False, =1 -> True`; `hogeq =0 -> False, =1 -> True`.

**Found only because the port was checked BEHAVIOURALLY rather than by "the patch applied cleanly".**
The port was correct; the flag it depended on was not.

icebow 639 OK. hogeq 706, 42 pre-existing failures, unchanged.

## 4n. 2026-08-25 — FIX 2+3 RETRY SHIPPED (unproven), ROYAL HOGS ABREAST, and ⚠ THE LOG IS THE WRONG WIDTH IN BOTH SIM AND LIVE

### FIX 2+3 RETRY — shipped on CORRECTNESS, not on a measured win

```
fix23 paired, n=30, control4 vs fix23b, both @2600 eps
  xbow_lock     5.37 -> 7.73   +2.37   1.1 sigma
  chip_linear   5.63 -> 8.57   +2.93   1.3 sigma
  xbow_defends  8.63 -> 7.97   -0.67   0.3 sigma
  xbow_no_lock  0.00 -> 0.00    0.00         (penalty removed; correctly never fires)
VERDICT: NO MEASUREMENT
```

The DIRECTION reversed -- the original was **-5.73 at 2.1 sigma (harmful)**, the retry **+2.37 at
1.1 sigma** -- an +8.1 swing in bow uptime confirming the -0.5 penalty was what suppressed bow play.
Nothing clears 2 sigma, so this is not a demonstrated benefit.

⚠ **THE EXPERIMENT WAS UNDER-POWERED BY CONSTRUCTION, AND THAT IS MY ERROR.** `xbow_overcommit` is
worth **0.07-0.08 per match**; gating it moves ~0.04 against a total reward magnitude of ~50, i.e.
**~0.08%**. No feasible sample size resolves that. A 1.5 h training arm was spent on a question the
instrument could never answer -- **compute the detectable effect size BEFORE running the arm**, not
after reading the result. "NO MEASUREMENT" here means the wrong instrument, not the absence of an
effect.

Shipped anyway because the GATE corrects a real defect (`led["cost"]` accrued independently of
`led["lock"]`, so a bow that never threatened still collected the credit) -- demonstrated
behaviourally, same basis as fixes 5/6/7.

### ROYAL HOGS SPAWN ABREAST (owner) — both decks

`cols = ceil(sqrt(n))` made the four hogs a 2x2. They enter in a HORIZONTAL LINE and fan into
separate lanes. Fixed DATA-DRIVEN via a `line_formation` flag rather than special-casing the card,
preserving the engine's "one rule, the card declares which" design. MEASURED: 4 distinct X, 1
distinct Y, span **3.96 tiles** against a 2x2's **~1.32**. Negative control: ordinary swarms still
grid.

⚠ **A PATCH-AUTHORING TRAP, recorded because it corrupted a file**: the anchor
`"    cols = int(math.ceil(math.sqrt(n)))"` (4 spaces) matches as a SUBSTRING of the real 8-space
line and replaces only part of it. Anchor on the full line INCLUDING its newlines.

### ⚠⚠ OPEN: THE LOG'S WIDTH IS WRONG IN BOTH SIM AND LIVE, AND THEY DISAGREE BY 1.9x

Surfaced when the owner corrected a claim of mine. **The real Log is 3.90 tiles wide.**

```
owner (real game)                      3.90 tiles
SIM   _LOG_ROLL_HALFW 2.2      ->      4.40 tiles    ~13% TOO WIDE
LIVE  log_half_width 0.064     ->      2.30 tiles    ~41% TOO NARROW
```

Wrong in OPPOSITE directions, so they cannot both be reasoned about with one mental model:
* **LIVE too narrow** -- the whiff verdict and the aim assist believe the Log covers half of what it
  does, so a cast that would really connect is scored a WHIFF and the assist demands precision the
  card does not need. This is the §4.2 family: "it knows it in sim but not live".
* **SIM too wide** -- over-credits the Log, teaching the policy it clips troops it would miss.

**PROPOSED (not yet applied):** set both to 3.90 -- sim `_LOG_ROLL_HALFW = 1.95`, live
`log_half_width = 1.95/18 = 0.1083`. NOT shipped in this batch because it moves a reward-relevant
quantity in the sim and belongs in its own change, and because the published width should be sourced
from the wiki first the way the spawn intervals were.

⚠ My original claim -- "four abreast exceed the Log's width" -- was WRONG twice: it quoted the LIVE
number in a SIM context, and that number is itself wrong. At 3.96 vs a real 3.90 the outer hogs sit
right AT the edge. The formation fix stands; that justification for it did not.

## 4o. 2026-08-25 — ⚠⚠ THE GATE'S GRADIENT IS INVERTED BY CLIPPING, AND TWO LEVERS FIX DIFFERENT HALVES

### The finding (supersedes §4a's "the bow is unaffordable, not unwanted")

```
gate P(play) by elixir (control4)          %steps with PLAY masked to -inf
  elixir:   0     1     2     3   ...  10        0: 97.9%   1: 82.5%   2: 61.4%   3+: 0.0%
  P(play): .473  .416  .353  .265  ...  .085
```

The gate's apparent enthusiasm lives ENTIRELY where it cannot act. At 0-2 elixir, 62-98% of steps
have zero affordable cards, so PLAY is masked and the output is inert. **Where every decision is
real (3+ elixir) it plays 9-27% of the time, falling monotonically as elixir rises.** The x_bow
costs 6 and can only be played there -> 0.75 bows/match, and raising affordability 4.6%
(2.7% -> 12.4%) moved usage 0.70 -> 0.75. **The card head PREFERS the bow at 1.48x fair share
(0.370 vs 0.250).** It is not unwanted and no longer unaffordable -- THE GATE WILL NOT ACT.

⚠ This also retires the "gate wants to play 57%" figure quoted earlier: that average is dominated
by masked steps where the output means nothing.

### The refusal is IRRATIONAL under its own reward

```
NEVER play                  -0.2127 /step        holding is 6.7x worse than playing
play only at elixir >= 6    -0.0316 /step
play whenever affordable    -0.0278 /step
```

And every loss term pushes the gate TOWARD playing (parameter-path probe, comparable units):
`VALUE +77.25 | POLICY GRAD (unclipped) +56.35 | ENTROPY +3.48`.

⚠ **The in-trainer probe (`CLASHRL_GATE_PROBE`) CANNOT SEE THE VALUE TERM** -- it takes
`autograd.grad(term, gate_logits)`, and the critic reaches the gate through shared-trunk PARAMETERS,
not through the gate logits. It returns `value +nan` on every sample. That is a good explanation for
why the previous investigation stalled: its instrument was blind to the largest candidate. Use
`scratchpad/gate_param_probe.py`, which measures `-<d(logit gap)/dtheta, d(term)/dtheta>` instead.

### STAGE A SWEEP — the two levers fix DIFFERENT HALVES, and neither works alone

```
arm  per_head  mult   clipPLAY  clipWAIT  sign-agree  mean clipped  verdict
A0   false     1.0      0.621     0.008      1/6        -0.00106    fail   (inversion reproduced)
A1   true      1.0      0.668     0.011      5/6        +0.00338    fail
A2   false     4.0      0.169     0.011      1/5        +0.00012    fail
A3   true      2.0      0.507     0.014      5/6        +0.00395    fail
A4   true      4.0      0.170     0.014      4/5        +0.00430    PASS
```

* **`ppo_clip_per_head` fixes the SIGN** (3-head coupling: a play's joint ratio is gate x card x
  cell, a wait's is the gate alone). A1 flips sign-agreement 1/6 -> 5/6 and the mean clipped
  pressure -0.00106 -> +0.00338 -- but leaves `clipPLAY` at 0.668, so the corrected gradient is
  censored on two thirds of plays.
* **`ppo_clip_play_mult` fixes the FREQUENCY** (minority-action volatility: d(log p)/d(logit) is ~1
  for the minority action and ~p for the majority, so the same logit move swings a play's log-ratio
  ~1/p harder -- MEASURED, gate log-ratio sd 0.518 on plays vs 0.027 on waits). A2 collapses
  `clipPLAY` 0.621 -> 0.169 but leaves the sign wrong, because the joint ratio still couples heads.
* **Only A4 gets both.** Dose 2.0 (A3) fails the clip-rate bar at 0.507, so 4.0 is the smallest that
  works, not the largest that passes.

**THIS RECONCILES THE OLD VERDICT.** HANDOFF recorded per-head as "no improvement, inside noise" and
that was not wrong, it was INCOMPLETE: A1 un-inverts the sign while still clipping 67% of plays, so
the corrected gradient barely reaches the gate.

### ⚠ THE LEVERS WERE MUTUALLY EXCLUSIVE UNTIL TODAY

`_surr` used the base `clip_eps` and the per-head branch OVERWRITES `pl`, so setting both applied
only per-head and `ppo_clip_play_mult` was a SILENT NO-OP. Fourth member of the family after
`--drill-frac 0.0`, `--workers 0` and `CLASHRL_DRILL_PLAY_OUT=0`. **The combination that passes
could not have been tested before this was fixed.** `_surr(r, eps)` now takes a per-sample bound;
the gate gets `eps_b`, card/cell keep `clip_eps` (they exist only on play steps, so they carry no
play/wait asymmetry to correct).

### STATUS: Stage B running — mechanism is NOT outcome

`ARM_clipfix.pt`, 2600 episodes, A4 config, matched against `ARM_control4.pt`. Un-inverting the
gradient is necessary, not sufficient, and this can still come back null. Pre-committed: >=2 sigma
on the paired probe or it is reported as NO MEASUREMENT.

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

Owner: "log is wider than 1.95 tiles, I thought we established this in the past." They were right,
and chasing it found an error in MY probe, not in the KB.

**The KB is correct.** `_LOG_ROLL_HALFW = 1.95` is the corridor HALF-width -> **3.90 tiles wide**
(the owner's own number from §4n), and `roll_len = 9.6` tiles FORWARD. So the Log covers a
**3.9 x 9.6 tile corridor**, not a circle.

**`scratchpad/spell_probe.py` judged EVERY spell as a circle of radius `spell_radius`.** For the
Log that is a 1.95-tile circle — it threw away ~9.6 tiles of forward sweep and scored good casts
as wasted. **This is the SAME circle-vs-corridor bug the engine's own whiff snapshot had and
fixed** (§5: "A rolling spell's whiff snapshot was a CIRCLE"). I reintroduced it in the
instrument after it had been fixed in the engine.

### What changes when the probe mirrors `_resolve_roll` instead
```
                              init     26k     delta   sigma
the_log  OLD probe (circle)    81%     66%   -15.1pp    2.84   <- REPORTED AS A REAL IMPROVEMENT
the_log  FIXED (corridor)      60%     59%    -0.7pp    0.11   <- FLAT. No improvement at all.
tornado  (circle, correct)     51%     60%    +9.3pp    1.34
ALL      FIXED                 54%     57%    +2.7pp    0.62
```
**RETRACTED: "the Log's dump rate genuinely improved 81% -> 66% (2.84 sigma)" (§4r, §4t).** With
correct geometry it is 60% -> 59%, i.e. nothing. The apparent gain was the policy drifting its
casts in a way the CIRCLE test rewarded and the corridor test already counted.

**What still stands:** spells are wasted at a high rate (57% of casts land with nothing in their
real hit area), and the cell-head entropy measurement (tornado 5.790 / the_log 5.400 vs a 6.068
uniform maximum) is untouched by this — it never used spell geometry. The two-failure split
(placement + restraint) also stands: the restraint evidence is drill-based, not geometry-based.

**What is now FALSE:** any claim that spell placement improved over the run. It did not.

### TRAP (§8): an instrument can carry a bug the code already fixed
The engine knew the Log is a corridor. The probe did not. When writing a measurement tool, mirror
the ENGINE'S OWN hit test (`_resolve_roll` here) rather than re-deriving geometry from a spec
field whose meaning you assumed — `spell_radius` means RADIUS for a blast and HALF-WIDTH for a
roll, and nothing in the name says so.

---

## 4u. 2026-08-26 — THE 40k RUN WAS STOPPED AT 26,600. Reference policy = `policy_BEST_m18000_20260826.pt`.

Owner's call, on the §4t degradation. Stopped via PowerShell process lifecycle (Git-Bash `pkill`
cannot see Windows processes and fails SILENTLY — §2): **16 processes killed, recount verified 0.**

* **`data/policy_BEST_m18000_20260826.pt`** (copy of `policy_ppo_long_best.pt`) is the REFERENCE
  POLICY from here. It is at **matches=18000**, which is exactly where the rolling eval peaked
  (ladder avg-5 33% / fair 22%) — the trainer's own best-gate and our independent eval reading
  agree, which is a useful cross-check on both.
* `data/policy_ppo_long.pt` (matches=26600) is the LAST policy, ~13pp of ladder worse. Do not use
  it as a baseline by accident — the filename does not say "worse".
* 7 "new BEST" saves happened over the run; the last was the 33% one.

**NO new PPO until sim-parity implementation is 100% complete** (owner). The merged restart, from
this reference policy, is that experiment's ONE change.

---

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

Owner asked whether the 86%-own-half rocket reading meant (a) overtime is never reached or (b)
overtime is reached but the rocket-cycle plan is not run. `scratchpad/rocket_probe.py`, 30 matches:

```
(a) REACHES overtime      18/30 (60%)   median match length 180.1s   max 255.3s
    BUT total overtime PLAYED = 86s across all 30 matches (~4.8s per OT match)
(b) rocket rate  OVERTIME 2.09/min   REGULATION 0.54/min   (3.9x -- the doctrine IS weakly present)
    ON an enemy crown tower: 9 of 47 casts (19%)
    median distance from the nearest enemy tower EDGE: 8.7 tiles (rocket radius is 2.0)
    enemy towers still alive at match end: mean 2.60 of 3
```
**Both hypotheses are wrong as stated.** It DOES reach the 3-minute mark (60%) and it DOES rocket
nearly 4x more often per minute once there — but the match RESOLVES AT THE BUZZER instead of
playing overtime (median end 180.1s, one tick past regulation), so the rocket-cycle window barely
exists. And the rockets that are cast are not tower-directed: **8.7 tiles from the nearest enemy
tower edge, four times the blast radius.** Same shape as §4r: the cell head is not aiming.

The number that frames all of it: **2.60 of 3 enemy towers alive at the end.** This policy almost
never takes a tower, so overtime is entered from behind or level, not as a closing plan.

⚠ METHOD CAVEAT: these probes read `data/policy_ppo_long.pt`, which the LIVE trainer overwrites
every checkpoint. Two probes minutes apart read DIFFERENT policies — the own-half rocket share
read 86% (n=28) in one probe and 57% (n=47) in this one. Copy the checkpoint before probing if a
figure needs to be stable, and never compare two probes taken at different times as if they were
the same policy.

---

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

### ⏳ QUEUED — SPLIT THIS FILE. It is 486 KB / 6,471 lines and is read in full every session.
Owner approved 2026-08-29. **Do it AFTER the A/B's m=1500 read**, so results are not written into a
file being restructured underneath them.

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
per section in place (`## 3n. ... -> HANDOFF_ARCHIVE.md`), keep the archive greppable and committed.
Re-run graphify afterwards -- the doc half of the graph goes stale the moment this lands.


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

## 8. Measurement traps (each of these produced a wrong conclusion first)

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
