# ClashAI

Homemade bots that learn to play **2v2 Clash Royale** on PC (through Google Play
Games). This is a hobby / research project about getting an agent to *actually
play* a live real-time game.

There are two very different agents in this repo:

| Folder | Bot | Approach |
| ------ | --- | -------- |
| [`icebow/`](icebow/) | **Learning bot** — the main project | Watches *you* play and copies you (imitation learning), then improves by trial-and-error (reinforcement learning), rewarded for taking towers, defending its own, and winning. Follows a DDQN architecture.|
| [`trol/`](trol/) | **Scripted bot** — the first experiment | Hand-written rules plus a DQN scaffold. Kept for reference. |

> ⚠️ **Please use this responsibly.** Automating Clash Royale violates Supercell's
> Terms of Service. This project only exists as a learning exercise. If you run
> it, use a throwaway account. I am not responsible for any lost accounts due to breaking of ToS.

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
the *next* card coming up (so it can plan its cycle), tower and king HP (for
rewards), and the win/loss screen at the end. Card recognition is done by
matching against small template images built from your own recordings — so it
learns *your* deck, including evolved cards (which count as their own card).

### The deck it's currently tuned for

Royal Delivery, Tesla (Evolved), Ice Wizard, X-Bow, Rocket, Miner, The Log,
Skeletons — a **Miner X-Bow control** deck (Classic 1v1, all cards level 11). The
reward shaping teaches: defend + cycle with the cheap cards, use the **X-Bow** as the
win condition (placed forward, within firing range, to lock the enemy princess tower),
the **Miner** to chip the tower / tank / snipe support (it deploys anywhere), and the
**Rocket** to clear big pushes or cycle-chip the tower during double/triple elixir.

---

## Quick start

Everything for the learning bot lives in [`icebow/`](icebow/). Full, step-by-step
instructions (setup, recording, training, and playing) are in
**[icebow/README.md](icebow/README.md)**. The short version:

```powershell
cd icebow
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 1. record yourself playing a bunch of matches
python run.py record
# 2. build card templates + check recognition
python run.py hand-templates
python run.py verify --hand
# 3. turn recordings into data, then train
python run.py label --all
python run.py train-bc
python run.py train-rl
# 4. let it play
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
