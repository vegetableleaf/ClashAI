# Labelling scope — the win-condition blind spot

**Written 2026-08-16, then corrected by measurement the same day.** `tools/blindspot_probe.py`
was written to decide whether this work is worth doing before doing it. It settled the question
and it also **rewrote the target list** — see "What the probe actually found", which supersedes
the four-card scope below.

## What the probe actually found

Over 40 greedy matches against the meta pool, counting every step where an enemy **win condition
is committed on our half** and asking whether the reward's own threat vector could see anything
at all:

> **1683 such steps. The reward read NOTHING on 665 of them — 39.5%.**

So the blind spot is live and large, and the labelling is justified. But the priority list is not
the one I guessed. Ranked by how often each win condition was actually committed-and-invisible,
against the boxes that are **actually in the training split**:

| card | blind commits | train boxes | val boxes | in frozen val subset? |
|---|---|---|---|---|
| **wall_breakers** | 168 | **7** | 2 | no |
| **giant** | 140 | **5** | 1 | no |
| **battle_ram** | 87 | **7** | 1 | no |
| **golem** | 81 | **13** | 3 | no |
| **skeleton_barrel** | 69 | **19** | 6 | no |
| **goblin_drill** | 55 | **1** | 1 | no |
| **goblin_giant** | 46 | **11** | 2 | no |
| ram_rider | 19 | 31 | 4 | no |
| royal_giant | 0 | 39 | 8 | no |
| graveyard | 0 | **0** | 0 | no |
| *balloon (the bar)* | — | *40* | *12* | *yes — **R 1.00*** |
| *hog_rider* | — | *91* | *19* | *yes — moderate* |

**The bar is far lower than I first claimed.** Balloon reaches **R 1.00 on 40 training boxes**.
Giant has 5. Wall Breakers has 7. Golem has 13. Graveyard has never been labelled at all. These
classes are not *hard*, they are **untrained** — which is the cheap kind of problem.

**None of the ten appears in the frozen val subset**, so no detector generation has ever been
graded on any of them. "Broken on board-13" was never measured for these; they were simply never
in the test.

> **Correction to an earlier version of this file.** It listed 56–131 instances per class. That
> count swept every `.txt` under `data/detect`, including staging and batch folders that are not
> in the training split, and overstated the real numbers by roughly 10x. The table above counts
> `labels/train` and `labels/val` only.

**Two corrections to my original scope.** `royal_giant` and `graveyard` did not commit once in
this sample and drop off the list. `wall_breakers`, `battle_ram`, `skeleton_barrel`,
`goblin_drill` and `goblin_giant` were never in it and belong near the top — Wall Breakers alone
outranks the Giant.

**The 39.5% is a LOWER bound.** "Saw a threat" only means the identity block was lit by
*something*; when a visible support unit walks beside an invisible Giant the step counts as seen
even though the win condition itself is not. Wall Breakers appearing in both columns (168 blind,
80 lit) is exactly that.

**What the probe could NOT settle:** whether fixing it raises win rate. Changing a reward does
not change a fixed policy's play, so that needs a retrain to measure. The archetype split came
back 0/6 vs 3/34 — far too few matches, on a checkpoint 400 matches into training, to mean
anything. Question 1 alone is the justification.

---

## Original scope (superseded by the table above, kept for the reasoning)

Target: get `giant`, `golem`, `royal_giant` and `graveyard` into `observation.detector_cards`.

## Why this is worth doing

That whitelist gates **two** things, not one: the identity block the policy observes, *and* the
defensive rewards (`threat_miss_idle`, `threat_response`) — both read
`view.identity_items(..., detector_cards, ...)`. None of these four are in it.

The result is inverted in the worst possible way. Measured on the sim:

| enemy on the board | ignore cost | holding costs the agent |
|---|---|---|
| lone Skeletons | 0.4% of a tower | **−1.0** (until the triage waiver landed) |
| Giant | 72.8% of a tower | **0.0 — never fires** |

The sim literally cannot teach the Giant/Golem/Royal Giant matchups, and DOCTRINE.md already
names heavy beatdown / RG / split-lane as this deck's *worst* matchup. Fixing the whitelist is
the upstream cause; everything downstream is currently arguing about the wrong boards.

## Current state (measured, not estimated)

Instances in `data/detect` versus the classes that already earned their place:

| class | instances | detector status |
|---|---|---|
| **giant** | 53 | not whitelisted |
| **golem** | 51 | not whitelisted |
| **royal_giant** | 84 | not whitelisted |
| **graveyard** | 99 | not whitelisted |
| hog_rider | 166 | whitelisted, moderate tier (R 0.4–0.6) |
| balloon | 104 | whitelisted, **R 1.00** |
| valkyrie | 226 | **held back, R 0.33** |
| knight | 780 | reliable |
| ice_wizard | 1137 | reliable |

## The thing that decides the effort

**Instance count is not the binding constraint.** Valkyrie has 226 instances and scores 0.33;
Balloon has 104 and scores 1.00. The existing diagnosis in config.yaml says why — valkyrie's val
boxes come from *~4 scenes* and it lacks pose variety, and copy-paste synthesis cannot help
because it replays the same 72 sprites.

So the target is **distinct scenes**, not raw boxes. That is good news here: Giant, Golem and
Royal Giant are large, slow, high-contrast silhouettes with very low pose variance — much closer
to Balloon than to a mid-spin Valkyrie. Expect them to clear the bar at Balloon-like counts.

**Graveyard is the odd one out** and should be scoped separately: it is a spell whose visual is a
cloud of spawning skeletons, so it behaves like a swarm class, not a body. If it does not clear
the bar, the fallback is to key off its *skeletons* (already a class) plus the spawn footprint
rather than the spell itself.

## Effort (revised against the corrected counts)

- **No new capture needed for a first pass.** 20,075 images on disk, 6,408 labelled →
  **13,667 already unlabelled**.
- Target **~40 train boxes per class** — Balloon's demonstrated bar for R 1.00 — plus **~10 val
  boxes** so recall becomes measurable at all. That is roughly 8 classes x 50 boxes ≈ **400
  boxes**, most frames carrying one instance.
- Add those val frames to the frozen subset, otherwise the next generation still cannot be graded
  on them and we repeat this exercise.
- The old target below (~150 instances from ≥20 scenes) was set before the counts were corrected
  and is more than these classes need.
- `pre-annotate` turns the job into *correcting* boxes, not drawing them.
- Estimate: **~600 frames to review, roughly 2–3 hours** of hand-labelling, plus one detector
  retrain (board-14). The retrain is GPU work and the PPO run is `--device cpu`, so they coexist.

## Pipeline

```
run.py label-queue --classes giant,golem,royal_giant,graveyard --n 300 --device cpu
run.py pre-annotate                     # Label Studio tasks, current boxes as pre-annotations
#   ... correct in Label Studio ...
run.py detect-import <export.json>
#   ... retrain -> runs/detect/board-14 ...
run.py detect-eval                      # per-class recall, the number that decides
```

Then add each class that clears the bar to `observation.detector_cards`. **No policy retrain is
required** — the identity vector is a fixed role aggregate, so growing the whitelist is
resume-safe. It does change what the reward can see, which is the entire point.

Bar to clear: R ≥ 0.6 for the reliable tier, or R ≈ 0.4–0.6 with high precision (hog_rider,
pekka, mega_knight all sit in that band today).

## Measure the payoff BEFORE paying the cost

Recommended first step, ~10 lines and no labelling at all: let the **sim reward** read ground
truth for these four instead of filtering through the detector whitelist, and run `policy-stats`
against beatdown opponents. The sim has perfect information — the whitelist filter is there to
mimic live detector coverage, not because the sim cannot see a Giant.

If win rate against beatdown moves, the labelling is worth the afternoon. If it does not, the
blind spot is not what is costing those matchups and the 3 hours should go somewhere else.

The caveat that makes this a *test* and not a fix: a reward that teaches defending a Giant the
policy cannot perceive live would train a skill that does not transfer. So this stays a
measurement until the detector can actually name the card.
