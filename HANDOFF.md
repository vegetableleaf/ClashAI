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

Last updated: **2026-08-20**, at commit `HEAD` (DRILLS: the segmented mini-sim framework is in and
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
