# ClashBot — 2v2 Spell-Cycle Bot (educational)

An automation project that queues 2v2 quick matches in Clash Royale (running
via the Google Play Games app on Windows) and plays an all-spell "spell cycle"
deck: it emotes **"Good game!"**, then repeatedly drops every affordable spell
at a configurable on-screen spell target (currently the top-left corner), emotes
again at match end, exits, and re-queues. A lightweight learning layer tunes
the menu/queue timing so it moves from one match to the next as fast as
reliably possible.

> ⚠️ **Responsible use.** Automating gameplay violates the Clash Royale / Supercell
> Terms of Service and can get an account permanently banned. Per your own plan:
> use a **throwaway account** you don't mind losing, and only play **private
> matches against friends who have agreed to test with you** — never against
> unaware players in public matchmaking. You are responsible for how you use this.

---

## Handoff note for the next AI agent (READ FIRST)

This README is the single source of truth for understanding and continuing this
project. It is written so a fresh Copilot/AI on another machine can pick up the
work with no prior context.

**Rule: whenever you change the project, update this README in the same change.**
Keep all of the following in sync with the code:
- the component table (files + responsibilities),
- the state machine / control flow,
- the config schema reference,
- the "Project status" and "Next steps" sections.

After finishing an edit, re-read this file and correct anything now inaccurate.
A repo-scoped agent memory note mirrors the high-level facts; update it too if
your agent supports memory.

Quick orientation:
- Entry point: `run.py` -> `src/clashbot/cli.py`.
- Core loop: `src/clashbot/bot.py` (`ClashBot.run`).
- All tunables: `config/config.yaml` (coordinates are normalized 0-1).
- Validate edits with: `python -m py_compile src\clashbot\*.py`.
- Platform is fixed: **Clash Royale via the Google Play Games app on Windows**
  (the game renders in a PC window; capture uses `mss`, input uses `pyautogui`).

---

## How it works

```
capture ──► vision ──► bot state machine ──► controller ──► game
 (mss)     (OpenCV)     (queue → emote →       (pyautogui)
                         spell-cycle →
                         emote → exit)
                              │
                              └──► learning (adaptive transition timing)
```

All on-screen positions are **normalized** (`0.0–1.0` of the game area), so the
config is resolution-independent. Each tick reads a frame, classifies the game
state, acts, and repeats at `timing.loop_hz`.

## Components (file-by-file)

| Path | Responsibility | Key symbols |
| --- | --- | --- |
| `run.py` | Bootstrap: adds `src/` to `sys.path`, calls the CLI. | — |
| `src/clashbot/cli.py` | Argument parsing + wiring of all objects. Subcommands: `run`, `calibrate`, `capture-template`. | `main`, `_build` |
| `src/clashbot/config.py` | Loads `config/config.yaml`; nested `get(...)` access + project-relative `path(...)`. | `Config` |
| `src/clashbot/states.py` | Enum of recognized game states. | `GameState` = `UNKNOWN/HOME/PARTY/QUEUING/IN_MATCH/MATCH_END` |
| `src/clashbot/capture.py` | Locates the game window (by title or explicit region), grabs BGR frames with `mss`, maps normalized→screen pixels. | `WindowCapture`, `Region` |
| `src/clashbot/vision.py` | CV: template-match current state, read elixir via HSV pip sampling, identify hand cards, pick a randomized spell target. Frames scaled to `capture.work_width`. | `Vision.detect_state / read_elixir / identify_hand / tower_target / find` |
| `src/clashbot/controller.py` | Input via `pyautogui`: tap, play card (tap-select then tap-place), "Good game!" emote flow. | `Controller.tap / play_card / emote_good_game` |
| `src/clashbot/bot.py` | State machine running the whole loop; reports transition outcomes to the learner. | `ClashBot.run`, `_on_home / _on_party / _on_match / _spell_cycle / _on_match_end` |
| `src/clashbot/learning.py` | Default learner: ε-greedy **bandit** learning the fastest reliable wait per transition; persists to `learning_state.json`. | `TimingLearner`, `make_learner` |
| `src/clashbot/dqn.py` | Optional PyTorch **DQN** with the same `choose/update` interface (`learning.backend: dqn`); persists to `dqn_state.pt`. | `DQNTimingPolicy` |
| `src/clashbot/calibrate.py` | Interactive tools: live overlay to read normalized coords, and ROI-based template capture. | `calibrate`, `capture_template` |
| `config/config.yaml` | All tunables (window, coordinates, deck, elixir, targets, timing, learning). See schema below. | — |
| `templates/` | State PNGs (`home_menu`, `party_menu`, `in_match`, `match_end`, `match_end_dc`); `templates/cards/` holds one PNG per spell. Git-ignored. | — |

## State machine (the loop)

```
UNKNOWN ── dismiss a known popup (`recovery.popups`) if one shows, else keep polling
HOME ──(tap battle_button)──► PARTY ──(tap quick_match)──► IN_MATCH
IN_MATCH: emote "Good game!" once on entry, then spell-cycle every tick
IN_MATCH ──(match ends)──► MATCH_END ──(emote once, tap results_ok / results_ok_dc)──► HOME ──► repeat
```

- State is decided every tick by `Vision.detect_state` (priority
  `MATCH_END` → `IN_MATCH` → `PARTY` → `HOME`, else `UNKNOWN`).
- `_spell_cycle` reads elixir + hand and plays affordable spells in **random
  slot order** onto `tower_target()` (a configurable aim point — currently the
  top-left corner — randomized within `target.jitter_radius`). With no card
  templates it falls back to firing all four slots when elixir ≥ cheapest cost.
- After each menu tap the bot waits a **learned** delay, confirms the expected
  next state was reached, and reports success + latency to the learner. Learned
  transitions: `home_to_party`, `party_to_queue`, `results_to_home`.

## Setup

```powershell
cd c:\Users\benpe\OneDrive\Documents\ClashBot\trol
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run bot commands with the venv interpreter, e.g. `.\.venv\Scripts\python.exe run.py run`
(or activate once with `.\.venv\Scripts\Activate.ps1`, then use `python run.py ...`).

(Only install PyTorch if you want the `dqn` learning backend.)

> **Troubleshooting `pip install`.** If pip reports packages "already satisfied"
> in a global `...pythoncore-3.14...\site-packages` path, or fails with a Temp
> `PermissionError: ... output.json`, you were installing into global Python, not
> the venv. Install with the venv's own interpreter as shown above
> (`.\.venv\Scripts\python.exe -m pip ...`). Python 3.14 wheels for
> `opencv-python`/`numpy` exist; `pygetwindow`/`pyautogui` build from source
> (pure-Python, quick).

## Configure the capture region

Launch Clash Royale in Google Play Games. Then either:
- set `window.title_contains` in [config/config.yaml](config/config.yaml) so the
  window is found automatically, **or**
- set `window.region: [left, top, width, height]` to the exact game render area
  (exclude the Google Play Games sidebar/title bar).

## Calibrate coordinates

```powershell
python run.py calibrate
```

A live preview shows the detected state, estimated elixir, and overlays for the
hand slots, elixir pips, tower target, and emote points. **Left-click** anywhere
to print that point's normalized coordinates — paste them into the config.

## Capture detection templates

The bot needs a few reference images (captured at your resolution). Navigation
is two steps — the home page has a **Battle** button that opens the **2v2 party
menu**, which has the **quick match** button; after a match you return to the
home page. Capture each on its matching screen:

```powershell
python run.py capture-template home_menu    # the home page (Battle button visible)
python run.py capture-template party_menu    # the 2v2 party menu (quick match visible)
python run.py capture-template in_match       # a stable in-battle element
python run.py capture-template match_end      # results/OK screen (teammate online)
python run.py capture-template match_end_dc   # results screen when teammate disconnected (2v2)
```

`match_end` and `match_end_dc` are both listed under `states.match_end.templates`
in the config, so either results screen triggers `MATCH_END`.

Optionally, one image per spell so the bot knows each hand slot's cost:

```powershell
python run.py capture-template fireball --card
python run.py capture-template rocket --card
# ... one per deck entry in config.yaml
```

If no card templates are present, the bot falls back to firing all four slots
whenever elixir is at/above your cheapest spell's cost.

## Run

```powershell
python run.py run
```

Stop with **Ctrl+C**, or slam the mouse into a screen corner to trigger
PyAutoGUI's failsafe.

## Tuning

- Spell placement spread: `target.tower_center` / `target.jitter_radius`.
- Emote wheel positions: `emote.button` / `emote.good_game`.
- Learning: `learning.backend` (`bandit` or `dqn`), `epsilon`,
  `candidate_delays`. Learned values are saved to `learning_state.json`
  (or `dqn_state.pt`) and reused next session.

## Config reference (`config/config.yaml`)

All coordinates are `[x, y]` fractions of the game area (0–1).

- `window.title_contains` — substring to auto-locate the window; or set
  `window.region: [left, top, width, height]` to the exact game render area.
- `capture.work_width` — frames are scaled to this width for matching.
- `buttons.battle_button` / `quick_match` / `results_ok` / `results_ok_dc` — the
  menu taps for HOME → PARTY → match, and exit back to HOME. `results_ok` is the
  teammate-online results button ("Exit"); `results_ok_dc` is the teammate-
  disconnected results button ("OK"). The bot taps whichever matches the detected
  end screen (`match_end` vs `match_end_dc`).
- `emote.button` / `good_game` / `open_delay` / `send_delay` — the "Good game!"
  emote flow (`send_delay` lets the end-of-match emote send before exiting).
- `deck.cards` — 8 spells, each `name` (matches `templates/cards/<name>.png`) +
  elixir `cost`.
- `hand.slots` / `slot_size` / `identify_threshold` — the 4 hand-card positions
  and the card-ID crop/threshold.
- `elixir.bar_y` / `pip_xs` / `filled_hsv_lower` / `filled_hsv_upper` — where and
  how elixir pips are sampled (HSV magenta range = "filled").
- `target.tower_center` / `jitter_radius` — spell aim point + spread (currently the top-left corner, not the tower).
- `states.*` — per detectable state, a match `threshold` plus either a single
  `template` filename or a list of `templates` (any match wins; used by
  `match_end` to cover the 2v2 teammate-online and teammate-disconnected screens).
- `timing.*` — `loop_hz`, `select_delay`, `spell_replay_cooldown`, and the
  `menu_timeout` / `queue_timeout` / `exit_timeout` await limits.
- `recovery.*` — `enabled` plus a `popups` list; on an unknown screen the bot
  taps a popup's `dismiss` point if its `template` matches (rewards, level-up,
  reconnect, etc.). No timeout/auto-stop — unmatched screens just keep polling.
- `learning.*` — `backend` (`bandit`/`dqn`), `epsilon`, `lr`, `candidate_delays`,
  `state_file`, `transitions`.

## Project status

**Working / implemented:**
- Full pipeline: capture → vision → state machine → controller.
- Two-step menu navigation (HOME → PARTY → match → HOME).
- Spell-cycle with cost-aware (or fallback) play and randomized tower aim.
- "Good game!" emote at match start and end.
- Adaptive transition-timing learner (bandit default; optional DQN) with
  on-disk persistence.
- Calibration + template-capture tooling; resolution-independent config.
- All modules pass `python -m py_compile`.

**Not done yet / requires the user:**
- Dependencies are **not installed** and no venv is committed
  (`pip install -r requirements.txt`).
- No template PNGs captured yet — detection returns `UNKNOWN` and the bot idles
  until `home_menu`, `party_menu`, `in_match`, `match_end`, `match_end_dc` (and optional card
  art) are captured.
- Coordinates in `config.yaml` are placeholders — must be calibrated.
- Python 3.14 may lack prebuilt `opencv-python` / `torch` wheels; a 3.11–3.12
  venv is the safe fallback. The default `bandit` backend needs no PyTorch.
- Not runtime-tested against the live game (needs the game on-screen).
- Assumes 2v2 is already the selected mode (the game keeps it selected).

## Next steps / ideas

- Install deps, calibrate, capture templates, then `python run.py run`.
- Tune `learning.candidate_delays` to the real menu latency.
- Toward true deep RL: expand the DQN state vector (elixir, hand, timers,
  detected buttons) and action space (which card / where / when), shaping
  rewards around tower damage and match-cycle speed.
- Robustness upgrades: multi-scale template matching, OCR for the elixir number,
  detecting the enemy king-tower sprite instead of a fixed aim point.
