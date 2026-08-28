# ClashAI

> Homemade bots that learn to play **Clash Royale** on PC (through Google Play Games) — a hobby /
> research project about getting an agent to *actually play* a live real-time game.

The bot never sees the game's internal state. It gets what a person gets: **a picture of the arena
and its hand of cards.** From that it decides *which card to play and where to drop it* — or to wait.

> [!WARNING]
> **Please use this responsibly.** Automating Clash Royale violates Supercell's Terms of Service.
> This project exists as a learning exercise. If you run it, use a throwaway account. I am not
> responsible for any lost accounts.

> [!TIP]
> **New here?** Read **[icebow/Instructions.txt](icebow/Instructions.txt)** first — a complete,
> plain-English, from-scratch walkthrough. Prerequisites, install, screen calibration, recording,
> training, and playing. No coding experience needed.

---

## What's in the repo

| Folder | Bot | Approach |
| :----- | :-- | :------- |
| **[`icebow/`](icebow/)** | **Learning bot — start here** | Imitation learning from your own recordings, then reinforcement learning (PPO in the simulator, DDQN live). Runs an **X-Bow control** deck. |
| **[`hogeq/`](hogeq/)** | **Second deck, same brain** | An independent copy running **Hog / Earthquake**. Shares a byte-identical engine with `icebow/`, so a sim fix lands in both and a parity check proves it. |
| [`trol/`](trol/) | Scripted bot — the first experiment | Hand-written rules plus a DQN scaffold. Kept for reference; you can ignore it. |
| [`research/`](research/) | Measurement ledgers | Decisions, conflicts, and the numbers behind them. |

The deck folders are named after their decks. Rename them freely — nothing depends on the name.

---

## The model

A single small convolutional network with a **shared trunk and three action heads**. It is
deliberately tiny: the match engine is the expensive part, not the network.

| | |
| :--- | :--- |
| **Total parameters** | **481,136** (~1.92 MB as fp32) |
| **Observation** | `96 × 64 × 12` — a downscaled arena image plus semantic channels |
| **Embedding width** | 328 |
| **Heads** | `gate` (play / wait, 2-way) · `card` (10-way) · `cell` (432-way placement) |
| **Critics** | two value heads — one for matches, one for drills |
| **Extra inputs** | hand, next card, elixir, a 52-dim threat vector |

<details>
<summary><b>Parameter breakdown</b></summary>

| Module | Parameters | Share |
| :----- | ---------: | ----: |
| `policy.trunk` | 393,472 | 81.8% |
| `policy.features` (conv stack) | 65,056 | 13.5% |
| `policy.cell_ctx` | 10,528 | 2.2% |
| `policy.cell_conv` | 6,082 | 1.3% |
| `policy.card_head` | 3,290 | 0.7% |
| `policy.threat_fc` | 848 | 0.2% |
| `gate` | 658 | 0.1% |
| `value` + `value_d` | 658 | 0.1% |
| other input projections | 544 | 0.1% |

</details>

The head shapes are **pinned**: `icebow` has 10 cards, `hogeq` has 11 (481,538 parameters). Changing
a head shape invalidates every existing checkpoint, so the test suites assert it.

### The simulator behind it

A headless, stat-driven match engine built from a card knowledge base — fast enough to train over
thousands of matches before the game is ever opened.

| | |
| :--- | :--- |
| **Cards modelled** | 203, including **41 evolutions** and **16 heroes** |
| **Opponent pool** | 1,000 real meta decks, plus a self-play league |
| **Modelled mechanics** | shields, tower troops, per-card sight and targeting, spells and rolling-spell corridors, champion and hero abilities, the 2×/3× elixir phases |
| **Test suites** | 1,186 (`icebow`) · 1,203 (`hogeq`) |

<img width="462" height="962" alt="ezgif-1fd67eca6dfde1eb" src="https://github.com/user-attachments/assets/055c27eb-6ab3-426a-861f-64f0fb1b0fd1" />


---

## How the learning bot works

```
   ┌──────────┐   record    ┌───────────┐   label    ┌──────────────┐
   │  You play │ ──────────▶ │ screen +  │ ─────────▶ │ (image, hand) │
   │  on PC    │   matches   │  mouse log│   frames   │  -> action    │
   └──────────┘             └───────────┘            └──────┬───────┘
                                                            │ train-bc
                                                            ▼
   ┌──────────┐   train-rl   ┌───────────────────────────────────┐
   │  Plays    │ ◀────────── │  CNN policy: copies you first,     │
   │  live     │   improve   │  then learns from tower/win rewards │
   └──────────┘             └───────────────────────────────────┘
```

1. **Record** — you play normally; it captures the screen and your mouse.
2. **Label** — turns each play into a `(what the screen looked like → what card, and where)` example.
3. **Train (imitation)** — the network learns to copy your decisions.
4. **Train (reinforcement)** — it then plays and is rewarded for **taking enemy towers**, **keeping
   its own alive**, and **winning** — penalised for the opposite, for wasted spells, and for idling
   through a live threat.
5. **Play** — the trained policy plays on its own.

**What it reads from the screen:** the arena image, the four cards in hand and the *next* card (so
it can plan its cycle), the elixir bar and 2×/3× clock, tower and king HP, and the end-of-match
result. Card recognition matches against small templates built from your own recordings — so it
learns *your* deck, evolutions included. **Optionally**, a trained object detector lets it also
*see* the opponent's units for much better defence and elixir trades.

---

## Under the hood

- **Imitation → RL.** Behaviour-cloned from your recordings, then fine-tuned with **Double-DQN**
  (n-step returns) live, or **PPO** in the simulator.
- **Factored action space.** Every decision is three choices — play or wait, which card, which of
  432 board cells — so the network can learn *when* to act separately from *what* and *where*.
- **Drill curriculum.** Alongside full matches, the policy trains on short scripted scenarios
  ("bank to six, then place the X-Bow", "don't rocket their king") that isolate one skill each.
- **Optional object detector.** A YOLO detector trained on your own frames gives the bot enemy
  unit identity, position, and short-term memory instead of raw pixels. Off by default. Its
  annotation tooling ranks the unlabelled backlog by detector confusion (`label-queue`), ingests
  externally labelled batches (`detect-adopt`), and reports the recall numbers that gate turning it
  on (`detect-eval`).
- **Robust live play.** Screen-scraped tower and king HP, a 2×/3× elixir clock, team tracking so
  your own units aren't mistaken for threats, and overtime handling.
- **Watch what it sees.** A live preview during training, plus an optional `overlay_replay` gate
  that records the opening minute of every match with the detector's boxes burned in:

  <img width="328" height="598" alt="ezgif-809f0756a3620006" src="https://github.com/user-attachments/assets/922065c6-d617-4247-8a5c-4159495bc0e4" />

### The deck it's currently tuned for

Tornado, Tesla (Evolved), Ice Wizard, X-Bow, Rocket, Knight (Evolved), The Log, Skeletons — the
standard **X-Bow 3.5 control** deck, at a real account's card levels (12–16).

The reward shaping teaches it to defend and cycle with the cheap cards, use the **X-Bow** as the win
condition (placed forward, in range to lock the enemy princess tower), the **Evolved Knight** as a
cheap mini-tank, and the **Rocket** to clear big pushes or chip during double elixir. It also
follows an **offence → defence doctrine**: if the X-Bow can't break through by double elixir, it
switches to a defensive X-Bow and rocket-cycle to close — and it plays purely defensively against
the fast-cycle, heavy-beatdown, and split-lane decks that hard-counter X-Bow.

---

## Quick start

```powershell
cd icebow
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# FASTEST START — no game, no recording: train in the built-in simulator
python run.py train-sim --matches 20000 --envs 16

# THE REAL THING — learn from your own play, then improve live:
python run.py record                              # 1. record yourself playing
python run.py hand-templates                      # 2. build card templates
python run.py verify --hand                       #    ...and check recognition
python run.py label --all                         # 3. turn recordings into data
python run.py outcomes --all
python run.py train-bc --init data/policy_sim.pt  # 4. imitate, then RL fine-tune
python run.py train-rl --init data/policy_sim_best.pt
python run.py play                                # 5. let it play
```

Training needs a GPU build of PyTorch; recording and labelling do not.

**Full guides:** [icebow/Instructions.txt](icebow/Instructions.txt) (beginner, step-by-step) ·
[icebow/README.md](icebow/README.md) (technical reference)

---

## Repo layout

```
icebow/     the learning bot (imitation -> RL), X-Bow control — start here
hogeq/      second deck, Hog/Earthquake, shares the engine
trol/       the earlier scripted / DQN bot
research/   measurement ledgers and decision records
config/     shared top-level config
log.txt     changelog of model & architecture updates
```

See [log.txt](log.txt) for how the model and architecture evolved.
