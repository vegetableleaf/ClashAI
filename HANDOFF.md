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

Last updated: **2026-08-24**, at commit `HEAD` (DRILLS: the segmented mini-sim framework is in and
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
* Mighty Miner ability: 1 elixir, **single use, no cooldown**.
* Firecracker evo: `evo_cycles: 2`.

---

## 6. Open work

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
