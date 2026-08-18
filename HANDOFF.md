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

Last updated: **2026-08-17 23:50**, at commit `1cfa07e`.

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
* **Bash tool cwd persists between calls.** A `cd` into icebow silently makes later relative paths
  resolve there — this caused a verification pass to run against the wrong deck. Prefer absolute
  paths, or re-`cd` in the same command.
* Git Bash is available alongside PowerShell; each needs its own syntax.

---

## 3. What is running RIGHT NOW

* **board-26 detector training** — started 2026-08-17 ~23:30 via
  `icebow/_train_board26.py`, `save_dir=C:\Users\benpe\ClashBot\icebow\runs\detect\board-26`.
  yolo11s.pt, 120 epochs, imgsz 960, batch 4, patience 30, workers 4, nc=230.
  17,821 training frames (12,821 real + 5,000 synth), 4,456 batches/epoch.
  Measured ~4.3–5.0 it/s → **~15.8 min/epoch**; expect **~18 h** if it early-stops near board-25's
  69 epochs, ~31 h for the full 120. A persistent Monitor is armed for per-epoch mAP, early stop,
  and `MemoryError`/OOM/traceback.
  **Epoch 1 completed 2026-08-17 23:46 in 15:00 flat at 5.0 it/s**, matching the estimate.
  A one-shot check is scheduled for **07:03 on 2026-08-18** (session-only cron `4c55594d` — it dies
  if the Claude session is closed; if that happens, just do the check manually: read
  `runs/detect/board-26/results.csv` and compare against board-25 / board-24-5 at the same epoch).
* **Both PPO runs are STOPPED** (user decision, to give board-26 the RAM). They were
  `train-sim-ppo --matches 800000 --envs 96 --workers 12 --size 432 --device cpu`, icebow started
  22:26 and hogeq 22:46, both checkpointed 23:18. **Restart them after board-26 finishes** — they
  were the first runs using the fixed reward and that test is still pending.

### The RAM constraint (important)
31.4 GB total. Two PPO trainers + 24 rollout workers hold ~5.2 GB; YOLO at imgsz 960 needs ~5 GB
(main ~2.5 GB + ~650 MB per dataloader worker). **The machine cannot run both.** board-26 died with
`MemoryError ... Unable to allocate 1.63 MiB` — that is *host* RAM, not GPU. If it OOMs again, drop
to `workers=2`. CPU contention is NOT the issue: the 5 it/s measurement was taken while PPO ran.

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
4. **Ability button calibration (hogeq)** — `hand.ability_button: [0.963, 0.758]` is still estimated
   off a scaled screenshot. Script ready at
   `…/scratchpad/ability_calib.py` (`--aim` draws a crosshair and presses nothing; no-flag plays the
   Miner then taps and reports PASS/FAIL from the 1-elixir drop; `--list-windows` catches the
   wrong-window trap). **Needs a live match.**
5. **`firecracker_evo` has no hand templates** (only `knight_evo`/`tesla_evo` exist) — run
   `run.py hand-templates` with the evo charged before live play.
6. **Placement collapse** (§4.3) — after a clean BC retrain, if the head still collapses, the lever
   is the soft-target loss that has never been exercised.
7. **hogeq is still full of icebow-specific reward terms** (`xbow_*`, `rocket_*`, `nado`). They are
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

## 10. Useful one-liners

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
