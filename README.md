# ClashAI

Homemade bots that learn to play **Clash Royale** on PC (through Google Play
Games). This is a hobby / research project about getting an agent to *actually
play* a live real-time game.

There are two very different agents in this repo:

| Folder | Bot | Approach |
| ------ | --- | -------- |
| [`icebow/`](icebow/) | **Learning bot** — the main project | Watches *you* play and copies you (imitation learning), then improves by trial-and-error (reinforcement learning), rewarded for taking towers, defending its own, and winning. Follows a DDQN architecture. _**NOTE**: this folder is called "icebow" because I am having it run an icebow deck. You can rename it to anything depending on what deck you want to choose for the AI._|
| [`trol/`](trol/) | **Scripted bot** — the first experiment | Hand-written rules plus a DQN scaffold. Kept for reference, but you can ignore it. |

> ⚠️ **Please use this responsibly.** Automating Clash Royale violates Supercell's
> Terms of Service. This project only exists as a learning exercise. If you run
> it, use a throwaway account. I am not responsible for any lost accounts due to breaking of ToS.

> 🚀 **New here? Read [icebow/Instructions.txt](icebow/Instructions.txt) first.** A complete,
> plain-English, from-scratch walkthrough — prerequisites, install, screen calibration,
> recording, training (simulator + imitation + live RL), and playing. No coding experience needed.

---

## How the learning bot works (the short version)

The bot never sees the game's internal state — it only gets what a person would:
**a picture of the arena and its current hand of cards.** From that it decides
*which card to play and where to drop it*, or to wait.

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
2. **Label** — turns each of your plays into a `(what the screen looked like →
   what card you played, and where)` training example.
3. **Train (imitation)** — a small convolutional neural network learns to copy
   your decisions.
4. **Train (reinforcement)** — the same network then plays live and is rewarded
   for **taking enemy towers**, **keeping its own towers alive**, and **winning**
   (and penalised for the opposite, for wasting spells, etc.).
5. **Play** — the trained policy plays on its own.

**What it reads from the screen:** the arena image, the four cards in hand and
the *next* card coming up (so it can plan its cycle), your elixir bar and the
2×/3× elixir clock, tower and king HP (for rewards), and the win/loss screen at
the end. Card recognition is done by matching against small template images built
from your own recordings — so it learns *your* deck, including evolved cards (which
count as their own card). **Optionally** (advanced) a trained object detector can be
added so the bot also *sees* the **opponent's** units — what they are and where — for
much better defence and elixir-trade decisions.

### The deck it's currently tuned for

Tornado, Tesla (Evolved), Ice Wizard, X-Bow, Rocket, Knight (Evolved), The Log,
Skeletons — the **standard icebow (X-Bow 2.9) control** deck (Classic 1v1; the card levels are set to a
real account's, 12–16). The reward shaping teaches: defend + cycle with the cheap
cards, use the **X-Bow** as the win condition (placed forward, within firing range, to
lock the enemy princess tower), the **Evolved Knight** as a cheap mini-tank (its evolution
takes 60% less damage while it's not attacking) to defend and tank for the X-Bow, and the
**Rocket** to clear big pushes or cycle-chip the tower during double/triple elixir. It also follows a simple **offense→defense doctrine**: if
the X-Bow can't break through by double elixir (or once it's up a tower) it switches to a
defensive X-Bow + rocket-cycle to close the game — and it plays purely defensively
against fast-cycle, heavy-beatdown, and Royal-Recruits/Royal-Hogs split-lane decks that
hard-counter X-Bow.

### Under the hood

- **Imitation → RL.** A CNN policy is behaviour-cloned from your recordings, then
  fine-tuned with a **Double-DQN** (n-step returns) on live matches.
- **Headless simulator.** A fast, stat-driven match engine (built from the card
  knowledge base) trains the same policy over thousands of matches against a pool of
  ~1000 real meta decks — including a **self-play league** — so you get a strong prior
  before ever opening the game. It models shields, tower troops, per-card sight and
  targeting, spells, and the 2×/3× elixir phases.
- **Optional object detector (Stage 3).** A YOLO detector trained on your own frames
  lets the bot perceive enemy units (identity + position + short-term memory) instead
  of guessing from raw pixels. Off by default; see the Instructions.
- **Robust live play.** Screen-scraped tower/king HP, a 2×/3× elixir clock, team
  tracking (your own units aren't mistaken for threats), and overtime handling.

---

## Quick start

Everything for the learning bot lives in [`icebow/`](icebow/). For the full, step-by-step
beginner guide (setup, screen calibration, recording, training, and playing) read
**[icebow/Instructions.txt](icebow/Instructions.txt)**; a more technical reference is in
**[icebow/README.md](icebow/README.md)**. The short version:

```powershell
cd icebow
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# FASTEST START — no game, no recording: train in the built-in simulator
python run.py train-sim --matches 20000 --envs 16

# THE REAL THING — learn from your own play, then improve live:
# 1. record yourself playing a bunch of matches
python run.py record
# 2. build card templates + check recognition
python run.py hand-templates
python run.py verify --hand
# 3. turn recordings into data
python run.py label --all
python run.py outcomes --all
# 4. imitate your play (warm-started from the simulator brain), then RL fine-tune live
python run.py train-bc --init data/policy_sim.pt
python run.py train-rl --init data/policy_sim_best.pt
# 5. let it play
python run.py play
```

Training needs a GPU build of PyTorch; recording and labeling do not.

---

## Repo layout

```
icebow/   the learning bot (imitation learning -> RL) — start here
trol/     the earlier scripted / DQN bot
config/   shared top-level config
log.txt   changelog of model & architecture updates
```

See [log.txt](log.txt) for the history of how the model and architecture evolved.
