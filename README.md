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
> plain-English, from-scratch walkthrough of the original pipeline (prerequisites, install, screen
> calibration, recording, training, playing). No coding experience needed.

> [!NOTE]
> **The training pipeline is being rebuilt (September 2026).** The first version — a hand-written
> simulator, a pixel CNN, reinforcement learning from win/loss — was measured over ~60 experiment
> loops and did not improve the bot beyond its imitation starting point. The rebuild ("Square One",
> below) trains from **professional replays** driven through the **real game engine**. Stage 0 is
> done; stages 1–4 are in progress. The old pipeline still runs and is kept as the baseline every
> new stage has to beat. Day-by-day state lives in [HANDOFF.md](HANDOFF.md) and
> [GAUNTLET_LOG.md](GAUNTLET_LOG.md).

---

## What's in the repo

| Folder | What | Notes |
| :----- | :--- | :---- |
| **[`pipeline/`](pipeline/)** | **The new pipeline (deck-agnostic)** | One observation contract shared by the engine and the live screen reader, per-deck yaml in `pipeline/decks/`. Both decks inherit every change from here. |
| **[`icebow/`](icebow/)** | **X-Bow control deck** — screen reader, detector, live play, original trainer | The live-play path (`play.py`, `replay_mine.py`, the YOLO detector) is what deploys a trained policy into the real game. |
| **[`hogeq/`](hogeq/)** | **Hog / Earthquake deck** | Same tooling, second deck. Its crawled pro corpus and live path are separate; its models come from the shared `pipeline/`. |
| [`research/`](research/) | Measurement ledgers, decision records, engine tools | `research/sandbox_tools/` drives pro replays through the game engine (`replay_drive.py`, `replay_batch.py`). |
| [`trol/`](trol/) | Scripted bot — the first experiment | Hand-written rules plus a DQN scaffold. Kept for reference. |

The deck folders are named after their decks. Rename them freely — nothing depends on the name.

---

## The new architecture ("Square One")

The idea in one paragraph: **stop asking a sparse win/loss reward to teach placement, and instead
copy the pros, then let the real engine improve on the copy.** For any board, the policy proposes
its best few (card, cell) moves; the deterministic engine plays each forward a few seconds and keeps
the one that leaves the board better. That improved move is a supervised target for the next round
of training — a teacher that is strictly better than the student under the value used. Live play
comes last, through exactly the same observation builder that training used.

```
   pro replays (RoyaleAPI)        real CR engine (Android emulator, deterministic)
   1,253 icebow · 598 hogeq  ───▶  every replay re-driven, every frame recorded
                                              │
                                              ▼
                              pipeline/obs_contract.py  ◀──  live screen: YOLO detector,
                              one BoardState for both        hand/elixir/tower readers
                                              │
                    ┌─────────────────────────┼──────────────────────────┐
                    ▼                         ▼                          ▼
        S1 imitation v3            S3 search teacher + DAgger      S4 live layer
        copy pro placements        engine improves the student's   deploy through the same
        (entity + patch tokens,    own moves, student learns them  contract; EMA weights;
        full-res per-cell head)    by supervised training          graded on the ladder
```

### The five stages and their gates

Each stage ends in a pre-registered gate. A stage that fails its gate is reported as a null and the
next one does not start.

| Stage | What it builds | Gate |
| :---- | :------------- | :--- |
| **S0 — contract & instruments** *(done)* | One observation builder for engine state and detector output (`pipeline/`); the pro corpus rebuilt through the engine for both decks; engine-vs-live fidelity measured | Placement mask forbids < 0.5% of pro cells; detector→obs vs engine→obs agreement reported |
| **S1 — imitation v3** | New network: entity tokens + spatial patch tokens *with coordinates*, a full-resolution per-cell head (no upsampling, no tanh cap), card head, a supervised play/wait gate conditioned on the state, a categorical value head, "wait for card X" as an action | Top-1 agreement with pro placements above the old model's 15.44% on the same validation rows, 3 seeds; engine winrate ≥ the old init at n = 500 |
| **S2 — corpus ×3 → ×10** | Crawler restored; every positioned replay converted; then the detector used as an *inverse-dynamics model* to label pro video | Precision/recall of the recovered placements measured on engine ground truth; validation agreement rises with corpus size |
| **S3 — search teacher** | At states the student itself visits, Gumbel-top-k over its top 8–16 proposals + wait, each scored by re-driving the prefix and rolling out ~15 s; the improved targets are aggregated with the pro corpus (DAgger) | Teacher beats the frozen student ≥ 60% (n = 500); distilled student beats the student on winrate and agreement, 3 seeds |
| **S4 — live layer** | Deployment through the shared contract, sampled gate, EMA checkpoint; a critic trained from engine rollouts + live matches re-ranks the proposer's top-k; every live match is re-driven in the engine so the teacher can improve the student on the states it actually met | Ladder at a fixed trophy band, 20-match blocks, no learning during a block — the owner grades here |

### Why this instead of the old pipeline

| Axis | Old (measured) | New |
| :--- | :------------- | :-- |
| Learning signal | Win/loss reward → PPO on an imitation init. 4 arms / ~1,500 engine matches: a KL leash defended the init and bought nothing; without it the placement head railed | Supervised targets from pro placements and from the engine's own search — a supervised update cannot rail a head |
| Model | Rendered-board CNN, 12×8 feature map upsampled to a 24×18 grid, no coordinate input. Trunk embeddings had cosine 0.991 across *different* boards — it barely looked at the board | Entity tokens + patch tokens with coordinates, per-cell head at full resolution, past-actions channels |
| Environment | Hand-written stat-driven simulator: 26% agreement with the real engine on crowns | The real engine only, with a fidelity table measured first |
| Data | 9,444 placements from 211 replays; 43% of pro plays dropped by the converter | All positioned replays of both decks, every phase kept; then pro video via the detector |
| Play/wait gate | Learned from reward; collapsed to a constant twice | Supervised state-conditioned target from day one, plus a "wait for this card" action |
| Measurement | Single seeds; winrate at n = 16–150; two instruments compared | 3 paired seeds; engine winrate at n = 500 (SE 2.2 pp) — the engine's throughput (~1,850 matches/h) is what makes winrate usable as a discriminator at all |

### The engine

Training and evaluation run against the **real Clash Royale engine** inside a headless Android
emulator (kept outside the repo — it holds game binaries). It is deterministic: driving the same
replay twice produces byte-identical states, which is what makes the S3 search teacher possible
(the engine has no snapshot, so branching means re-driving the prefix — ~4.4 s per replay). Two
engine slots run on the training box; S3 is the one stage that scales with emulator count.

### What the bot reads from the screen (live)

The arena image goes through a **YOLO11s object detector** (230 classes, trained on this project's
own labelled frames; measured presence recall 0.855 / precision 0.886), plus template matching for
the four cards in hand and the *next* card, an HSV read of the elixir bar, a digit CNN for tower HP,
and a wall-clock 2×/3× elixir clock. `pipeline/obs_contract.py` turns those detections into the same
`BoardState` the engine produces, and `degrade()` corrupts engine states with the measured detector
error so training sees what live play will see.

---

## The original pipeline (still runs, kept as the baseline)

Record yourself playing → label each play as `(screen → card, cell)` → behaviour-clone a small CNN →
fine-tune with reinforcement learning (PPO in a hand-written simulator, Double-DQN live) → play.
This is what [icebow/Instructions.txt](icebow/Instructions.txt) and [icebow/README.md](icebow/README.md)
document, and the `run.py` commands below still work. Its best imitation checkpoint is the number
every new stage has to beat; its simulator and reward-shaping code are retired from training but
remain on disk.

```powershell
cd icebow
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

python run.py record                              # 1. record yourself playing
python run.py hand-templates                      # 2. build card templates
python run.py verify --hand                       #    ...and check recognition
python run.py label --all                         # 3. turn recordings into data
python run.py outcomes --all
python run.py train-bc --init data/policy_sim.pt  # 4. imitate
python run.py play                                # 5. let it play
```

Training needs a GPU build of PyTorch; recording and labelling do not.

The new pipeline's contract tests run from the same venv:

```powershell
.\icebow\.venv\Scripts\python.exe -m unittest pipeline.tests.test_obs_contract
```

---

## Repo layout

```
pipeline/   the new deck-agnostic pipeline: observation contract, vocab, per-deck yaml, tests
icebow/     X-Bow deck: screen reader, detector, live play, original trainer — start here
hogeq/      Hog/Earthquake deck: same tooling, second deck
research/   measurement ledgers, decision records, engine replay tools (sandbox_tools/)
trol/       the earlier scripted / DQN bot
HANDOFF.md  the project journal: measured results, open work, traps (HANDOFF_ARCHIVE.md for older)
GAUNTLET_LOG.md  one block per autonomous research loop
log.txt     changelog of model & architecture updates
```

See [log.txt](log.txt) for how the model and architecture evolved.
