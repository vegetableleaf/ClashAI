# Learning ClashBot (`icebow/`) — imitation learning → RL

> 🚀 **New here / setting this up on another PC? Start with [Instructions.txt](Instructions.txt)** —
> a complete, plain-English, from-scratch guide: prerequisites → install → screen
> calibration → recording → processing the data → training (simulator + imitation + live RL)
> → letting the bot play. No coding experience needed.

> 🔀 **Current deck: Icebow X-Bow Control (Classic 1v1)** — the standard X-Bow 2.9 control list.
> [DECK_SWITCH.md](DECK_SWITCH.md) is the ordered runbook for switching the deck (record → templates → label → train).

A second, **learning** bot (separate from the scripted `../trol` bot). Goal: an
agent that actually *plays* 1v1 Clash Royale (Classic / ladder), rewarded for
**taking enemy towers**, **defending its own towers**, and **winning**, and punished
for the opposite. It runs on PC via Google Play Games — the same rendering it trains on.

> ⚠️ **Honest expectations.** Learning to play from scratch on a *live* game is a
> research-grade problem: matches are real-time (~3–4 min), you can't parallelize
> one game instance, and rewards must be screen-scraped. A from-scratch agent
> would start random and likely plateau at weak play. So the plan leads with
> **imitation learning** (clone *your* play first), then RL fine-tune. This is a
> **train-it-yourself framework**, not a turnkey pro bot.
>
> Same responsible-use rules as `trol`: throwaway account, private/consenting
> matches only. Automation violates Supercell ToS.

## Pipeline

```
0. train-sim headless simulator: pretrain vs ~400 meta decks + self-play   [BUILT]
1. record    you play on PC; capture screen + your mouse                    [BUILT]
2. label     sessions -> (observation, action) dataset                      [BUILT]
3. outcomes  auto win/loss per match from the results scoreboard            [BUILT]
4. train-bc  behaviour-cloning: CNN policy learns to copy you               [BUILT]
5. train-rl  Double-DQN fine-tune, tower/win rewards (live matches)         [BUILT]
6. play      the policy plays live                                          [BUILT]

optional (Stage 3): a YOLO object detector adds opponent awareness    [in progress]
```

The agent sees a **downscaled arena image + the hand** (which cards are in hand)
and picks a **discrete action**: which **card identity** to play — not the tray
slot (cards cycle), and an **evolved card counts as its own identity** since it
plays differently — placed on a grid cell, or no-op. Rewards: `+take_enemy_tower`,
`+` for keeping your towers alive (defense), `+win`; `−` for the opposite (see
`config/config.yaml`).

## Launcher: `run.py ui`

Instead of typing every command in the terminal: **double-click `ClashAI.bat`** in the repo
root (or `ClashAI.exe`, which is the same thing with an icon, or
`.\.venv\Scripts\python.exe run.py ui`). It opens a native window, not
a browser tab. Under it is a local server on `127.0.0.1:8765` — localhost only, no
sign-in, no outbound calls.

Full description in [docs/LAUNCHER.md](docs/LAUNCHER.md); the order that gets you to
usable data is in [docs/PIPELINE.md](docs/PIPELINE.md).

**The panel is built around the fact that this project trains TWO networks.** They share
nothing — different inputs, different training data, different files:

| | Playing AI | Vision AI |
|---|---|---|
| decides | which card, which cell | what each unit on the board is |
| trains on | the simulator, your recordings, live matches | frames you labelled by hand |
| lives in | `data/policy*.pt` | `runs/detect/vision/weights/best.pt` |
| needs the game running | only for `play` / `train-rl` | never |

There is exactly ONE vision model. Training replaces it; nothing selects between
generations. The Control tab is grouped the same way, so the count of models is readable
off the page.

The tabs:

* **Overview** — the setup checklist, in the order the project needs, read off what is
  actually on disk rather than a fixed list.
* **Control** — starts and stops every command, grouped by which network it belongs to
  (`Setup (no AI)` / `Playing AI` / `Vision AI` / `Check the setup`). Steps are numbered
  where a real order exists. Stop shuts down cleanly and saves on the way; two GPU jobs
  never run at once.
* **Live** — the current frame and what the bot reads from it. "Mark what the bot sees"
  draws every reader's region straight onto the picture: tray slots, elixir pips, tower
  bars, detector boxes.
* **Labelling** — the ONLY place boxes are drawn. The model pre-fills what it already
  recognises; you correct and save. Click to select, pick a class to rename, `Del` to
  remove, drag to add, `Enter` to save and move on.
* **Models** — one card per network with its measured quality, variants folded away, and
  the vision model's predictions drawn over your own labelled frames. Also packs the
  vision AI into a single `.zip` and installs one back: `model` (weights, ~18 MB) or
  `full` (weights + your labelled frames). An import replaces the model — saving the old
  one first — and MERGES frames, never overwriting one you already have. A bundle whose
  class list differs from yours is refused rather than silently relabelling every box.
* **Progress** — benchmark, reward, loss, throughput for the playing AI, plus the vision
  model's mAP curve. Written to `data/metrics.jsonl`, survives a restart.
* **Strategy** — which cards the policy actually plays, and where (`policy-stats`), plus
  a recorded simulator match (`sim-view`). The counts say WHAT it plays; the clip says
  whether it looks like play at all.
* **Deck** — recognises the deck from a recording and, on request, writes the hand
  templates with it (`deck-detect`, `cards-art`).
* **Towers / Tempo / Settings** — tower HP crops, matches per second on this PC
  (`sim-bench`), and line-by-line `config.yaml` edits with a backup, preserving every
  comment in the file.

The panel only shows the commands your checkout actually has (`run.py --help`), so it
degrades gracefully. The introduction opens from the button, never on its own.

> The same rule applies here: automated play violates the Supercell ToS. The notice sits
> in the launcher under "Notes".

### If the panel's Live tab shows no data

The bundled screen templates come from an English client at a particular window size. At
a different size or language, `detect_state` finds no match, and everything downstream
finds nothing without failing outright. `run.py calibrate` re-cuts the detection from
your own recording; see [docs/PIPELINE.md](docs/PIPELINE.md) for details.

## Setup

```powershell
cd <your-cloned-repo>\icebow
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# GPU PyTorch (needed for training, not for recording) — pick your CUDA build:
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## Step 1 — record your play (do this now)

You just play normally; the recorder captures the game region and logs your
mouse. No phone or tap-overlay needed — on PC your mouse *is* the action.

```powershell
.\.venv\Scripts\python.exe run.py record
```

- Have Clash Royale in its usual Google Play Games window (region in
  `config/config.yaml` is reused from the `trol` calibration — re-check if the
  window moved).
- Play your matches, then press **Ctrl+C** to stop.
- The more matches the better (imitation wants hundreds). You do **not** need to
  track win/loss by hand — `run.py outcomes` reads each match's result off the
  end screen (crowns per team) automatically.

Each run saves a session under `data/sessions/<timestamp>/`:
- `video.mp4` — the game region at `record.fps`.
- `events.jsonl` — every mouse click `{t, x, y, button, pressed}`.
- `meta.json` — fps, region, and per-frame timestamps (to align clicks to frames).

## Config — which file is which

Five files in `config/`, and they are easy to confuse because three of them are about
cards. What each one is FOR:

| file | what it is | who writes it |
|---|---|---|
| `config.yaml` | every tunable: `window.region`, `record.*`, `observation.arena_size`, `action.grid`, `rewards.*`, `env.*` (live RL + tower HP crops), `train.*`, `sim.*`, `detect.*` | you, or the Settings tab (line patches, comments preserved) |
| `cards.yaml` | **your deck** (top of file) plus hand-curated card behaviour the wiki does not state in numbers: spawners, multi-hit kinds, targeting quirks | you, for the deck; curated by hand for the rest |
| `cards_stats.json` | the imported stat block per card — hitpoints, damage, hit speed, range, movement. 163 cards, level 11, straight from the Fandom wiki | `cards-import`, never by hand |
| `detect_classes.yaml` | the vision AI's class list, 225 entries. **The authority** — `data/detect/data.yaml` and `data/detect/classes.txt` are both generated from it | regenerated, not edited by hand |
| `meta_decks.yaml` | the opponent deck pool the simulator benchmark plays against | `decks-import` |

Rules that are easy to get wrong:

* **The deck lives in `cards.yaml`, nowhere else.** Everything downstream — hand
  templates, the policy's card indices, the threat vector — reads it from there. A deck
  in the config that is not the deck on screen is the most expensive mistake in this
  project: measured, hand recognition sat at 17% and the bot acted blind on nearly every
  tick.
* **Class indices are only ever appended to `detect_classes.yaml`, never reordered.**
  Every label file on disk stores a number, not a name, so reordering silently relabels
  the whole dataset. That has already happened here: the picker read a stale 236-entry
  list while training read the 225-entry one, so boxes drawn as `mini_pekka` (86) trained
  as `minions` (86 in the other list).
* `cards_stats.json` is generated. Edits belong in `cards.yaml`, which overrides it.

### Watching it play

- `preview` — a side window during `train-rl` showing live frames with the detector's
  team-coloured boxes, fed from the detector pass the env already runs (no extra
  inference). It's a *screen* grab, so the window must never cover the game; it
  auto-positions to the right of the capture region.
- `overlay_replay` — **off by default.** When on, the first `seconds` of **every**
  match is recorded to `data/overlayed_replays/match_<stamp>.mp4` with the boxes burned
  in. The opening is where placement, the first read of the opponent, and the
  detector's coverage of a clean board are all visible at once.
  The video runs at `fps` (max 60, default 30) while the **boxes** refresh at
  `observation.perception_hz`, so a clip shows real perception latency instead of
  hiding it. Clips are wall-clock paced — if capture can't keep up, frames are
  duplicated rather than letting the clip play fast-forward — and the achieved capture
  rate prints when each clip closes. `max_clips` (default 5, `0` = unlimited) is a hard
  cap **per session**: an overnight `train-rl` would otherwise bury the disk in clips of
  the same policy. On the last one the recorder shuts its thread down, so it stops
  grabbing the screen entirely for the rest of the run.
- `monitor` — optional Discord screenshots/clips during long unattended runs.

## Status

- ✅ Project skeleton + `record` (screen + mouse capture).
- ✅ `verify` — overlays your logged clicks on a recorded session to sanity-check
  capture, timing, and coordinate mapping (`run.py verify [--session <path>]`).
  `--towers` instead overlays the RL tower-detection anchors on in-match frames
  (green = read alive, red = destroyed; yellow = HP-number crops with the CNN
  read) so you can calibrate tower shaping and the chip-damage reward.
- ✅ `label` — pairs clicks into card plays, **recognizes which deck card** was in
  the selected slot (so the target is card identity, not tray position), and saves
  an `(observation, hand, card, cell)` dataset per session as `dataset.npz`
  (`run.py label [--session <path>] [--all] [--debug]`). Needs card templates first
  (`hand-templates`).
- ✅ `hand-templates` — extracts your deck cards' tray portraits from a recording
  so the hand can be recognized by identity; you rename the crops to deck keys and
  check with `run.py verify --hand` (`run.py hand-templates [--session <path>]`).
- ✅ `outcomes` — auto-detects **win/loss per match** from the 1v1 results
  scoreboard (you = blue/bottom, enemy = red/top; counts gold crowns per
  side). No manual tracking. Writes `outcomes.json` per session and prints the
  W-L record (`run.py outcomes [--session <path>] [--all]`).
- ✅ `train-bc` — CNN behaviour-cloning: trains the policy to predict
  `(card identity, placement cell)` from the observation + hand (the card head is
  masked to the cards actually in hand), checkpoints to `train.checkpoint`
  (`run.py train-bc`). Needs PyTorch (install the CUDA build).
- ✅ `play` — runs the bot live and **fully autonomous**: a scripted state
  machine (reused from trol: `home_menu`/`party_menu`/`in_match`/`match_end`
  templates + button taps) navigates HOME → queue → exit → re-queue, while the
  learned CNN policy plays cards in-match (`run.py play`).
- ✅ `train-rl` — DQN fine-tune of the BC policy on **live matches**. Reuses the
  scripted nav to play match-to-match; reward = per-step **tower shaping** (take
  enemy towers / defend yours) + the **win/loss** terminal reward from the
  results scoreboard. The Q-net is the BC policy reused as a factored
  card/cell Q-function (card values masked to the hand) plus a learned **no-op**
  gate; it saves to
  `train.rl_checkpoint`, which `play` then prefers (`run.py train-rl`).

### Stage 3 — the board object detector (in progress)

Teaches the bot to actually *see* the opponent (what unit, where) instead of inferring
it from red pixels. Gated behind `observation.use_detector`; see
`Instructions.txt` → Stage 11 for the full workflow.

- ✅ `detect-frames` / `autolabel` — export in-match frames to hand-label, and
  auto-box **your own** troops (a card you played is a known class at a known spot).
- ✅ `label-queue` — rank the **unlabelled** backlog by how much labelling each frame
  would teach: **ambiguity** (two classes claiming one box) and **uncertainty**
  (mid-confidence guesses). Hand-labelling is the slowest part of the project, so
  don't work the queue in file order (`run.py label-queue --classes wizard,valkyrie
  --n 150 --copy`).
- ✅ `detect-adopt` — ingest **someone else's** export + image folder. Their frames are
  usually `frame_0001.png` with numbering that restarts every batch, so a second batch
  would overwrite the first and leave its annotations describing unrelated images.
  Each file is md5-compared against the queue and the batch is auto-prefixed on
  collision (`run.py detect-adopt --json their-export.json [--dry-run]`).
- ✅ `detect-merge` — fuse every `batch*.json` into one self-contained export,
  deduplicated by image (`run.py detect-merge`). The result is a **snapshot** — re-run
  it after any new export.
- ✅ `detect-import` — import Label Studio JSON (a file, a **comma list**, or a folder
  of several) into the Ultralytics train/val split, remapping classes **by name** and
  deduplicating repeated tasks (`run.py detect-import --export batch_all.json`).
- ✅ `sprites` — cut labelled units out of their background (GrabCut) into a per-class
  sprite bank, then `--synth N` composites them onto other arenas so the detector
  learns the **unit**, not the lawn. The cut is **occlusion-aware**: a box more than
  35% covered by a neighbour is rejected rather than guessed at. Always rebuild the
  bank *before* the synths.
- ✅ `detect-eval` — the gating numbers: presence recall, base-folded per-card recall,
  and a confidence sweep. Pass the **same `--subset`** to every generation — labelling
  grows the val set, so runs scored on their own val sets are not comparable
  (`run.py detect-eval --sweep --subset data/detect/val_board15.txt`).
- ✅ `detect-preview` / `detect-obs` — see the raw boxes, and the semantic
  enemy/ally/building/spell channels the policy would receive.
- ✅ `tools/detect/train.py --resume [RUN]` — continue an interrupted run in its own
  folder, keeping its epoch count and `best.pt`. Resume restores every other setting
  from the checkpoint, so you **cannot** lower `--batch` on a resume.

## Recording note

Record **continuously across many matches, including the menu navigation** — you
do not need to stop between matches. The labeler ignores menu clicks and extracts
only in-match card plays. The policy never has to learn navigation (that's the
scripted layer), so just play naturally and Ctrl+C when you're done for the session.

## Data collection loop

```powershell
run.py record          # play matches, Ctrl+C after the results screen
run.py hand-templates  # ONE-TIME per deck: build card templates from a recording,
                       #   rename each _cand_*.png to its deck key (extra crops of the
                       #   same card: <key>_2.png; evolved face: <key>_evo.png), then
                       #   check with run.py verify --hand
run.py label --all     # (re)build datasets from every recording (needs the templates)
run.py outcomes --all  # auto win/loss record from every recording
```
The policy acts on **card identity** (an evolved card is a **separate identity**
from the normal one), so labeling recognizes which card sits in each tray slot —
that needs `templates/cards/<identity>.png` (e.g. both `tesla.png` and
`tesla_evo.png`), built once per deck with `hand-templates` and verified with
`verify --hand`. Do this before `label`.
More recordings = a better behaviour-cloning start. `label --debug` writes
annotated frames under a session's `labeled/` so you can eyeball the pairing.

## Letting the bot play & train (train-rl)

`train-rl` improves the imitation policy by **playing real matches** and learning
from the reward. It reuses the same scripted navigation as `play`, so it queues,
plays, exits, and re-queues on its own.

**Set up the game interface first:**

1. Open Clash Royale in the **Google Play Games** desktop app, windowed, and
   leave the window where the capture region expects it. The region lives in
   [config/config.yaml](config/config.yaml) under `window.region`
   (`[left, top, width, height]`, physical pixels).
2. Sanity-check capture/coords on your latest recording:
   `run.py verify` (overlays clicks) — if they line up, the region is good. If the
   window moved, re-calibrate the region (reuse the `trol` calibrate step) and
   re-check. To calibrate the tower reward, `run.py verify --towers` overlays the
   tower anchors (green = alive, red = destroyed) on in-match frames. To calibrate
   card recognition, `run.py verify --hand` overlays the recognized card on each
   tray slot (green = recognized, red = not). To calibrate the spell/defense
   rewards, `run.py verify --spells` tints the pixels counted as enemy troops and
   shows the arena `enemy_mass`.
3. Leave the account on the **HOME** screen (the 1v1 battle mode selected, as in
   your recordings). Use a throwaway account and private/friendly matches only.
4. Keep the mouse hand free: **pyautogui failsafe** is on — slam the cursor into a
   screen corner to abort instantly. `Ctrl+C` stops and saves.

**Run the loop:**

```powershell
run.py train-bc      # 1) imitation baseline from your recordings (offline, GPU)
run.py train-rl      # 2) live RL fine-tune; it plays match-to-match, Ctrl+C to stop
run.py play          # watch the current policy (prefers the RL checkpoint)
```

`train-rl` prints a line per match (outcome, reward, W-L record) and checkpoints
to `data/policy_rl.pt` as it goes; stop and resume anytime. Re-run `train-bc`
to reset back to the pure-imitation baseline.

**Reward / tower shaping.** The **win/loss** reward reads the end-of-match
scoreboard crowns, **cross-checked against the towers felled during the match**
(crowns == towers destroyed): the two are combined per side so a crown the
scoreboard misses is recovered from the in-match tower latch (this fixes losses
that used to read as a "draw"), and a felled **king tower** is decisive. The
per-step **tower** reward reads each side's towers by team colour at fixed anchors
(`env.enemy_towers` / `env.my_towers`) and latches a tower "destroyed" only after
a few sustained empty reads. Because the win/loss cross-check now leans on these
anchors too, **calibrate them with `run.py verify --towers`** (green = alive, red
= destroyed). Each match line prints `crowns=b-r`, and `(sb=… tw=…)` when the
scoreboard and tower reads disagree, so mismatches are easy to spot. Set
`env.tower_shaping: false` to fall back to the scoreboard alone.

**Chip-damage reward.** Destroying a tower is rare; most games are decided by
*chipping* the enemy princess (exactly what a rocket-cycle deck does). So each
princess tower's printed HP is read by a small digit CNN (shipped as
`src/clashrl/hp_digits.npz`) and **partial** HP loss is rewarded even when the
tower survives — positive for chipping the enemy, negative for HP lost on yours,
normalized so a full tower's worth of chip equals `rewards.hp_scale`. Per-digit
OCR is only ~92%, but tower HP is piecewise-constant and monotonic, so a value is
only confirmed once it reads the same on `env.hp_consensus` frames — transient
misreads never reach consensus, giving near-zero false damage (it may miss a hit
during heavy occlusion; the destruction latch covers the actual kill). Calibrate
the HP-number crops with `run.py verify --towers` (yellow boxes show the read +
confidence); set `env.hp_reward: false` to disable it. The crops are tight and
calibrated for the standard **Princess Tower** — a tower troop (Cannoneer / Dagger
Duchess / Royal Chef) puts its bar at a different height, so recalibrate the boxes
(and, if needed, re-collect crops and retrain, see [tools/hp_ocr/](tools/hp_ocr/README.md))
from a recording that has that tower type.

**Combat, spell & defense rewards.** HP lost on **your** princess tower is penalised
**gradually** as it's chipped — accumulating up to `|rewards.lose_own_tower|` per tower
(and topped up to it on destruction) — so chip damage costs proportionally rather than a
flat hit only when the tower falls. **Defeating enemy troops** by any means is
rewarded each step by the **signed** change in enemy-troop (red) pixel mass over the
arena (`rewards.troop_defeat`): mass falling (you cleared troops) is positive, mass
rising (a push is building) is negative. It is **potential-based** — symmetric, so it
telescopes over a match and can't be farmed by idling while the enemy army naturally
ebbs and flows. **Spells** add to that: when one is cast, its
effect is sampled over a short window around its **predicted impact**. A rocket's
flight time scales ~linearly with the distance it travels, so the impact moment is
estimated per cast (`rocket_base_time + rocket_travel_rate ×` distance from
`rocket_origin`, capped at `spell_eval_time`); a tornado lands in `tornado_time`.
The most enemy-troop mass seen in the target box during that window is "troops in the
blast", and the reward **scales with the size of the biggest unit caught** — the
largest connected red blob, since one fat unit is a single big blob while a swarm is
many tiny ones. So a rocket that lands on a **group of skeletons/goblins earns little**
(their largest blob is small) while one that catches a **Witch/Bowler/Balloon earns
more** (a big high-HP blob). A caught unit that then dies earns `size × spell_troop_damage`;
one that **survives** earns the smaller `size × spell_hit`; a rocket that hits the
**enemy princess and troops at once** earns a flat `spell_combo` (a value play); a cast
on empty ground is a `spell_whiff` (this is what stops the random throwing / king
activations); aimed at a princess alone is the small tower-HP chip. Waiting while the
board is quiet is **neutral** (the old standing `patience` reward is now `0` — a per-step
bonus for doing nothing was itself an incentive to stall); waiting while a real enemy
push is on the board is penalised (`rewards.idle_penalty`).
This was **calibrated on your recorded casts** (correlating `events.jsonl` cast times
to the frames): the reliable signal is the troop-mass change *at the spell's target in
the seconds after the cast* (not the explosion/ring, which is always present and whose
exact timing is too noisy to detect — hence predicting the impact from distance
instead). Near the enemy princess the target box overlaps the tower's own red, so a
combo needs a clear kill or heavy troop presence (`spell_combo_present`) and the
size-scaling is only applied in the midfield (the blob size is capped at
`spell_size_cap` so a tight clump can't over-score). A tornado's
target-drop is a *pull*, not damage, so only a rocket earns the kill/combo; the
tornado's value (pulling troops off your tower / grouping them for the kill) shows up
in the defence + general-defeat rewards. Tune `env.spell_radius` / `spell_min_drop` /
`defeat_min` and check the detection with `run.py verify --spells` (red = troops);
`env.spell_effect_reward: false` disables the spell part.

**Rocket auto-aim.** Whenever the policy chooses to rocket an enemy *princess* tower,
the target is snapped to whichever of the two princesses has **less remaining HP** (read
by the tower-HP OCR), so the rocket finishes off the weaker tower instead of splitting
chip across both. It only kicks in when both princesses are still standing and their HP
differs — a tie, a downed princess, or a non-princess aim is left exactly as the model
chose. This applies both in live `play` and during RL training (so behaviour matches).

**Range-aware defensive placement (Ice Wizard / Musketeer / Tesla).** When there's a clear
push, these ranged units are placed on the **threatened lane** a **unit's attack reach
behind the enemy front** (`env.range_offsets`, keyed by the card's knowledge-base range) —
so the attackers have to close that gap under fire instead of landing on top of the unit.
The enemy "front" is the deepest enemy troop on that lane; a unit with longer range is set
further back. When there's no clear threat the model places the card itself (so the Tesla
stays free to be reward‑shaped). **Evo Musketeer** always goes to the **very back** for its
charged long-range first shot. Tune `ice_wizard_lanes`, `range_offsets`,
`musketeer_evo_center`, and `defense_threat_frac`.

**Tesla kill reward.** On top of the above, a placed Tesla is credited (`rewards.tesla_kill`)
for the enemy troops it kills near it over its life — a Tesla that survives and keeps
defending keeps earning, which a **central** placement does best. Tune `env.tesla_track_steps`
/ `tesla_radius`.

**King-damage penalty.** Damaging the enemy **king** tower with a spell just wakes it early,
so it's **heavily penalised** (`rewards.spell_king_penalty`). It fires when the king's HP
number shows it took damage (`env.enemy_king_hp_box`, read by the tower‑HP model) **or** the
spell was aimed at the king — discouraging wasting a Tornado/Rocket on the king (e.g. trying
to clip it alongside a princess). Calibrate the king box with `run.py verify --towers` (the
`K` box).

**Winning is the goal.** The terminal `rewards.win` / `rewards.loss` are large (±10) so the
policy is pushed to actually **win matches** rather than farm shaping rewards.

**Chat-icon guard.** The in-match emote/chat icon (bottom-left) opens a wheel that stalls
the bot if tapped, so any card placement that would land on it (`buttons.chat_avoid_box`)
is nudged up out of the way.

> Note: partial HP damage to a troop that survives isn't detectable (no per-troop
> bars), so "damage" is approximated as troops *removed* (killed/scattered).

> Reality check: this is live, one match at a time (~3–4 min each), so RL is slow
> and needs a decent BC start. It's a framework for steady improvement, not a
> quick path to a strong bot.

## Card knowledge base + elixir

A card knowledge base ([config/cards.yaml](config/cards.yaml), loaded by
`src/clashrl/cards.py`) holds per-card attributes — elixir, kind, targeting,
movement, splash, and behaviour flags — for your deck plus common opponent cards.
Inspect it or refresh the stats with:

```powershell
run.py cards          # deck, average elixir, and combat-stat coverage
run.py cards-import   # scrape current level-11 stats from the Clash Royale wiki
```

- **Curated fields** ([config/cards.yaml](config/cards.yaml)) — elixir, targeting,
  splash, behaviour flags, abilities (e.g. Ronin's Parry), and the deck definition
  — are hand-maintained and always win.
- **Combat stats** (hitpoints / damage / DPS / hit-speed at level 11) are imported
  by `cards-import` from **clashroyale.fandom.com** (community-maintained, so it
  tracks recent balance changes) into `config/cards_stats.json`, which the curated
  file overlays. Re-run `cards-import` after a balance update.
- **Champions and Evolutions** are imported too: champion (hero) cards from the
  Champion category, and each card's `<Card>/Evolution` variant keyed `<base>_evo`
  (e.g. `musketeer_evo`). A deck slot marked `evolved: true` overlays the Evolution
  stats, so Evo Musketeer / Evo Tesla show their evolved numbers in `run.py cards`.
- The deck's cards use their **real account levels** (12–16), set per card in the
  deck definition; the imported stats are a level-11 baseline the engine scales by
  card level.

**Elixir** is read from your bar (`Vision.read_elixir`, calibrated in the `elixir`
config) and used to avoid wasting cards while exploring (`train.min_play_elixir`).
Note: only *your* elixir is on screen, so a full **elixir-trade** signal (your
spend vs. theirs) needs identifying the opponent's cards — that's the next stage
(a troop detector trained from your recordings).
