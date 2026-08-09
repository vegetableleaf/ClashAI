# Start here

Double-click **`ClashAI.bat`**. That is the only starter in this folder; everything else is
a button inside the panel it opens.

If it complains about a missing Python environment, do the one-time setup below first.

---

## One-time setup (about five minutes)

You need **Python 3.11** (`py -3.11 --version` should answer) and, for training, an
NVIDIA GPU.

From this folder, in PowerShell:

```powershell
py -3.11 -m venv icebow\.venv
icebow\.venv\Scripts\python.exe -m pip install -r icebow\requirements.txt
```

For training you also want the CUDA build of PyTorch — the plain one runs on the CPU and
is roughly fifty times slower:

```powershell
icebow\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu121
```

Then double-click `ClashAI.bat`.

> Automating play violates the Supercell terms of service. This is a learning and research
> project; using it on an account you care about can get that account banned.

---

## What you are actually building

Two neural networks that have nothing to do with each other, plus a simulator:

```
SIMULATOR         a headless Clash Royale. No game needed, ~2 matches/second.
    │  produces numbers: units, positions, HP, elixir, hand
    ▼
PLAYING AI        decides: which card, which cell
    ▲  receives the same numbers
VISION AI         turns real screenshots into exactly those numbers
```

The point of the vision AI is to make the real game look like the simulator. If both are
right, the playing AI cannot tell them apart — it returns `(card, cell)` either way.

**Training happens in the simulator.** You do not need the vision AI, the game, or a
recording to train the playing AI. The vision AI is the door to the real game, not the
path to strength.

---

## The order to do things in

Every step below is a button in the panel. The Overview tab tracks which are done by
looking at what is actually on disk.

### 1. Set up (once, and again whenever you change deck)

| # | button | why |
|---|---|---|
| 1 | Fetch card pictures | reference art, so the deck can be recognised automatically |
| 2 | Record yourself playing | start in the menu, play one full match, keep recording a few seconds past the result screen |
| 3 | Detect the deck | reads your deck out of that recording; tick **Write hand templates** |
| 4 | Calibrate match detection | only if the Live tab shows `UNKNOWN` while you are in a match |

Check it worked: **Live** tab → tick *Mark what the bot sees*. You should see your hand
cards named, the elixir count matching the bar, and tower HP matching the numbers on
screen. If something reads `?`, the boxes drawn on the picture show you where it looked.

> The single most expensive mistake in this project is a deck in the config that is not
> the deck on screen. Measured: hand recognition at 17 %, and the bot acting blind on
> nearly every tick. Step 3 exists to prevent it.

### 2. Train the playing AI

Start with **Sim training (DDQN)**. It needs nothing else — no game, no recording.

Watch the **Progress** tab, and watch the right curve: the *benchmark* against fixed
opponents, not the training win rate. In self-play the win rate sits near 50 % by
definition; it looks like progress and measures nothing.

Optional extra routes into the same network:
* *Prepare imitation data* → *Behaviour cloning* — learns from what you played
* *Live RL* — fine-tunes on real matches (occupies the game window and the mouse)

### 3. Train the vision AI

Four steps, in order, in the Vision AI group:

1. **Get frames to label** — pulls in-match frames out of a recording
2. **Draw the boxes** — opens the Labelling tab. The model pre-fills what it already
   recognises; you correct it. Click a box to select, pick a class to rename, `Del` to
   delete, drag to add, `Enter` to save and move on.
3. **Multiply your labels** — cuts your boxes out of their background and pastes them
   onto other frames, generating extra labelled images. It multiplies what you drew; it
   invents nothing.
4. **Train the vision AI** — replaces the one model at
   `runs/detect/vision/weights/best.pt`

Check it worked: **Models** tab → *See the frames it was taught on*. Green boxes are
yours, dashed orange is what the model predicts on the same frame.

The lever here is the number of boxes, not the number of epochs. Measured on this repo:
63 hand-drawn boxes multiplied to 371 images gave mAP50 58 %, recall 56 %. Before that,
29 boxes gave recall 17 % — it found one unit in six.

### 4. Let it play

**Play (policy live)** needs the game window and the mouse. `train-rl` does the same but
keeps learning while it plays.

---

## Which file is which

| file / folder | what it is |
|---|---|
| `ClashAI.bat` | the starter. This one. |
| `ClashAI.exe` | the same thing with an icon, optional, built by `tools/build_exe.bat` |
| `icebow/config/config.yaml` | every setting; the Settings tab edits it line by line, keeping the comments |
| `icebow/config/cards.yaml` | **your deck**, plus hand-curated card behaviour |
| `icebow/config/cards_stats.json` | imported card stats from the wiki — generated, don't edit |
| `icebow/config/detect_classes.yaml` | the vision AI's class list — never reorder it, only append |
| `icebow/data/` | recordings, labels, checkpoints, metrics. Not in git. |
| `icebow/runs/detect/vision/` | THE vision model. One folder; training replaces it. |
| `icebow/run.py` | the CLI behind every button, if you prefer typing |
| `tools/` | build scripts. Nothing here is needed to use ClashAI. |

Two things in this folder belong to the **older, scripted bot** and have nothing to do
with the learning bot above — they are kept for reference, not used by anything here:

| | |
|---|---|
| `trol/` | the original rule-based bot |
| `config/config.yaml` | its config. **Not** the one you want — that is `icebow/config/config.yaml` |
| `log.txt`, `command list.png`, `Command flowchart.png` | project notes and diagrams |

---

## When something does not work

* **Live tab says `UNKNOWN` during a match** → run *Calibrate match detection*. The
  shipped screen templates come from one client at one window size and one language.
* **Hand cards read `?`** → that card has no template. Run *Detect the deck* with
  *Write hand templates*. The Labelling tab names the missing card explicitly.
* **A tower reads `?`** → either something covers the number on that frame, or the crop
  does not fit your window. The dashed boxes on the picture show where it looked;
  `env.*_tower_hp_boxes` in Settings moves them.
* **The vision AI finds nothing** → it needs boxes, not epochs. See step 3.
* **Nothing starts** → the panel refuses to run two GPU jobs at once. The Control tab
  says which one holds it.

## Where the other documents fit

| document | when |
|---|---|
| **this file** | you want to click buttons. One page, panel-first. |
| [`icebow/Instructions.txt`](icebow/Instructions.txt) | you want to type commands. 650 lines, every stage spelled out, no panel involved. |
| [`icebow/README.md`](icebow/README.md) | what each part is and why it is built that way |
| [`icebow/docs/PIPELINE.md`](icebow/docs/PIPELINE.md) | getting a recording to produce data, and the vision-AI pipeline in detail |
| [`icebow/docs/LAUNCHER.md`](icebow/docs/LAUNCHER.md) | the panel's internals and API |
| [`icebow/DECK_SWITCH.md`](icebow/DECK_SWITCH.md) | changing to a different deck |

The panel and the CLI do the same things — every button is a `run.py` subcommand, and
the panel only offers the ones your checkout actually has.
