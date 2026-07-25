# ClashAI

Homemade bots that learn to play **2v2 Clash Royale** on PC (through Google Play
Games). This is a hobby / research project about getting an agent to *actually
play* a live real-time game — not a polished cheat tool.

There are two very different agents in this repo:

| Folder | Bot | Approach |
| ------ | --- | -------- |
| [`real/`](real/) | **Learning bot** — the main project | Watches *you* play and copies you (imitation learning), then improves by trial-and-error (reinforcement learning), rewarded for taking towers, defending its own, and winning. |
| [`trol/`](trol/) | **Scripted bot** — the first experiment | Hand-written rules plus a DQN scaffold. Kept for reference. |

> ⚠️ **Please use this responsibly.** Automating Clash Royale violates Supercell's
> Terms of Service. This project only exists as a learning exercise. If you run
> it, use a throwaway account in private matches with people who have agreed to
> it — don't ruin real ladder games for real people.

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

Royal Delivery, Tesla (Evolved), Ice Wizard, Tornado, Rocket, Ronin, Ice Spirit,
Skeletons. The reward shaping teaches a **defensive** style: defend with troops,
use the **Rocket** as the only real offense (aimed at the weaker princess tower),
and cheaply cycle Ice Spirit / Skeletons.

---

## Quick start

Everything for the learning bot lives in [`real/`](real/). Full, step-by-step
instructions (setup, recording, training, and playing) are in
**[real/README.md](real/README.md)**. The short version:

```powershell
cd real
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

## Honest expectations

Learning to play a **live** game from scratch is genuinely hard: matches run in
real time (you can't fast-forward or run 1000 in parallel), and every reward has
to be read off the screen. That's why the bot **imitates you first** and only
then fine-tunes with reinforcement learning. Think of this as a
*train-it-yourself* framework — how good it gets depends on how much you record
and train. It is not a turnkey pro player.

## Repo layout

```
real/     the learning bot (imitation learning -> RL) — start here
trol/     the earlier scripted / DQN bot
config/   shared top-level config
log.txt   changelog of model & architecture updates
```

See [log.txt](log.txt) for the history of how the model and architecture evolved.
