# Live Policy Performance — Brainstorm and Experimental Roadmap

**Created:** 2026-08-29

**Status:** research brief; no proposal in this document is implemented merely by being listed

**Scope:** improve the playing policy's decisions in live training matches, especially choosing the
best available response to an enemy play

**Primary deck:** icebow, with ideas intended to generalise to hogeq where the deck-specific objective
permits it

This document is written so a fresh agent can understand the argument and continue the work without
the conversation that produced it. Read `README.md` and the current `HANDOFF.md` before acting. The
handoff contains later corrections to several earlier conclusions; newest measured entries win.

---

## 1. Executive conclusion

The strongest current diagnosis is:

> **The main policy bottleneck is not parameter count or card recognition. It is evaluating the whole
> response — including when to act and what must happen after a wait — as a temporally coherent
> decision.**

The project has unusually strong evidence for this:

1. Flat rollout search over the same frozen policy raises simulated win rate from **37.0% to 85.7%**
   and tower delta from **-0.928 to +0.651**. The useful actions are already reachable from the
   policy's ranking; selecting among them is the problem.
2. Card distillation works mechanically: teacher-card agreement improves by **+10.6 points at
   4.19 sigma**, but win rate changes by only **+3.0 percentage points at 0.63 sigma**. Better card
   identity alone does not recover the search advantage.
3. Gate/timing distillation from a single observation barely moves: **0.5892 -> 0.6012** with frozen
   features and **0.6305** with full training, below the misleading always-WAIT accuracy floor of
   0.7756.
4. A restraint veto identifies genuine teacher-declined plays at **95% precision** and still makes
   the policy worse. Removing a play is not useful unless the agent also makes the better later play
   that justified waiting.
5. The model uses a separate play/wait gate. The gate does not directly compare `WAIT` against the
   value of the particular card-and-placement response that would be executed.

Therefore the most promising direction is not “play less,” “pick better cards,” or “make the CNN
bigger.” It is:

* measure decision regret at enemy-play events;
* score complete candidate actions jointly against WAIT;
* give the policy temporal state;
* teach complete continuations instead of isolated action labels;
* make live replay concentrate on rare, consequential response transitions.

---

## 2. Relevant project architecture

The playing policy currently has approximately **481k parameters** and consumes a
`96 x 64 x 12` observation, hand, next card, elixir, and a 52-dimensional threat vector. It has a
shared convolutional trunk and factored heads:

* gate: play or wait;
* card: one of the deck identities;
* cell: placement on the 432-cell grid;
* value heads in simulator PPO.

The live learner is Double-DQN with n-step returns. Its replay buffer is a `deque`, and optimisation
draws a uniform `random.sample`. The simulator learner is PPO with drills, scripted doctrine, a
self-play/opponent pool, and optional search-generated imitation targets.

Perception is screen-only. A YOLO detector feeds semantic and predictive canvases plus threat
features. A timestamped canvas-history implementation already exists, but the configured
`canvas_stack` is **1**, so the current policy still receives only the newest slice.

Important architectural seam:

```text
state embedding z
    -> gate(z): WAIT vs PLAY
    -> card(z): which card
    -> cell(z, card): where
```

The gate is not explicitly conditioned on the best concrete `(card, cell)` candidate. In live DDQN,
the greedy play's centred card/cell advantages cancel, so the play-versus-wait comparison is the gate
head's comparison. This makes “should I play this exact counter here?” harder than it needs to be.

---

## 3. What “best response” should mean

There is no universally knowable best response in live Clash Royale because opponent hand, exact
elixir, hidden card cycle, precise unit HP, and detector misses are partially observed. The correct
target is:

> **The lowest-regret legal action under the bot's current belief, followed by a coherent continuation.**

The project should distinguish:

* **oracle regret:** regret against simulator ground truth, used for controlled research;
* **belief regret:** regret against what the live observation actually supports;
* **execution loss:** a good selected response that is late, redirected by an aim assist, or becomes
  a ghost play;
* **continuation failure:** WAIT is correct only if the promised later response occurs.

Whole-match win rate cannot isolate these. It is noisy, opponent-distribution dependent, and in some
training contexts servo-controlled. Response quality needs its own benchmark.

---

## 4. Priority 1 — build an enemy-play response-regret benchmark

### Purpose

Turn “always make the best response possible” into a direct, repeatable measurement before changing
the architecture.

### Proposed harness

At the instant the simulated opponent plays a card:

1. Clone the state immediately after the enemy action.
2. Generate legal candidates:
   * WAIT;
   * the policy's top card choices;
   * top 2-3 legal cells per affordable card;
   * researched counter-table candidates;
   * doctrine/reference placements where applicable.
3. Roll every candidate forward for the already-measured **12-second** horizon.
4. For a fair continuation, use the same continuation policy for all arms. Also run a second view in
   which the search teacher controls the full 12-second continuation; the difference reveals whether
   the first action or follow-through is the failure.
5. Score actual consequence, not shaped reward:
   * enemy tower fraction destroyed;
   * our tower fraction lost;
   * elixir spent at the established conversion;
   * surviving board value;
   * explicit crown value.

### Metrics

* mean and percentile regret: `best_score - policy_score`;
* top-1 and top-3 response agreement;
* response latency from enemy deployment to our executed play;
* card regret and placement regret separately;
* WAIT false-positive and false-negative rates;
* follow-through rate at +3, +6, and +12 seconds;
* illegal, unaffordable, clamped, redirected, and ghost-play rates;
* results by threat family and matchup.

Suggested buckets:

* Hog/Balloon/building targeters;
* tanks and support formations;
* ground and air swarms;
* barrel/spawn spells;
* split-lane pushes;
* enemy investment in the back;
* quiet-board punish windows;
* opponent building/pump;
* overtime/tiebreak states.

### Secondary product

Automatically export the highest-regret states into generated drills. This converts the drill suite
from a manually drafted curriculum into a failure-driven curriculum while retaining the existing
baseline-versus-oracle discrimination gate.

### Acceptance gate

Do not claim a policy improvement unless it improves response regret on held-out seeds and held-out
opponent decks, in addition to any whole-match outcome change.

---

## 5. Priority 2 — replace the independent gate with a joint candidate-value scorer

### Problem

The current factorisation answers:

```text
Should I play anything?
If yes, which card?
If yes, where?
```

The decision actually required is:

```text
Is WAIT better than Knight at this cell, Tesla at that cell, or Log along this corridor?
```

Card choice already distils well, yet outcome does not move. The missing comparison is the value of
the complete response versus waiting.

### Proposed model

Retain the existing encoder and spatial map as proposal generators. Add a small candidate scorer:

```text
Q(s, WAIT)
Q(s, card_id, cell_id, cost, geometry, threat context)
```

Candidate features can include:

* shared state embedding;
* learned card embedding;
* local spatial feature at the cell;
* cell-to-primary-threat delta and lane;
* card cost and current/post-play elixir;
* target compatibility and counter-table features;
* opponent belief features;
* time since the enemy play.

Use a bounded candidate set rather than all 4,320 card/cell combinations. A practical first pass is
WAIT plus the top 2 cells for every affordable card, counter-table candidates, and one doctrine
fallback.

### Training target

Do not throw away the rollout scores by keeping only the argmax label. Train on:

* pairwise preference: best candidate should outrank the others by their measured margin;
* listwise soft targets derived from rollout scores;
* calibrated value/regret regression;
* ordinary n-step TD targets from live replay.

This gives the learner information about close decisions and avoids treating a nearly tied choice
like a catastrophic error.

### First experiment

Train the scorer offline on the response-regret corpus while freezing the existing encoder. Compare:

1. current factored greedy policy;
2. candidate scorer with hard teacher labels;
3. candidate scorer with score/ranking targets.

Primary endpoint: held-out response regret. Secondary: tower delta and win rate. Only unfreeze the
encoder if the frozen-head result shows the target is representable.

---

## 6. Priority 3 — give the policy temporal memory

### Why

The search teacher decides timing by rolling the future forward. A single frame does not say:

* whether a unit has just appeared or has been advancing for several seconds;
* whether a push is accelerating, splitting, retargeting, or dying;
* whether the policy just spent a counter and should wait for it to engage;
* whether a WAIT is banking toward a scheduled play;
* whether the opponent's response card is likely back in cycle.

The failed gate-distillation result is consistent with missing temporal information, not necessarily
an intrinsically unlearnable gate.

### Low-risk experiment already enabled by the code

Run `canvas_stack: 1` versus `canvas_stack: 2` at the existing 0.5-second spacing. This adds motion
evidence without implementing recurrence. It requires a fresh checkpoint because the input width
changes.

Measure:

* response regret;
* reaction latency;
* king-activation and pull drills;
* moving-spell placement drills;
* `bank_to_six_then_bow` and other continuation-sensitive drills;
* sim-to-live agreement on recorded replays.

### Preferred second stage

Add a small GRU, approximately 128-256 hidden units, after the visual/context encoder. Carry state
within a match and reset it at match boundaries. Feed it the current embedding plus:

* previous executed action, not merely selected action;
* observed elixir delta;
* new-enemy-play event and inferred card;
* time since last friendly/enemy play;
* pending-deploy and ghost-play status;
* opponent cycle/belief summary.

Live DDQN must then sample **sequences**, not individual transitions. Use a burn-in prefix to
reconstruct hidden state before computing loss, as in recurrent replay approaches such as R2D2.

### Risk

Do not bolt a GRU onto uniform one-transition replay. That trains hidden state on disconnected
frames and would make the architecture look ineffective for an instrumentation reason.

---

## 7. Priority 4 — teach complete continuations, not isolated WAIT labels

### Evidence

The restraint classifier achieved held-out AUC 0.694 and 95% veto precision, yet the veto caused
monotone harm. The classifier was identifying the requested states. The intervention was incomplete:
it removed a play but supplied no better later action.

### Proposed teacher record

For every searched decision, store a short teacher plan:

```text
action now
time until next teacher play
next card and cell
optional third action
macro intent: defend / bank / punish / cycle / commit
teacher value after the continuation
```

Possible losses:

* current-action ranking;
* discrete-time hazard or survival loss for time-to-next-play;
* next-action card/cell prediction;
* plan-value regression;
* auxiliary intent classification.

Do not grade gate learning with raw accuracy. The teacher waits most of the time, so always-WAIT
looks accurate while winning nothing. Use decision regret, precision/recall on valuable play events,
and realised plan value.

### Dataset aggregation

Iteratively:

1. roll out the current student;
2. query the search teacher on states the student actually visits;
3. add the labelled continuation to the corpus;
4. retrain and repeat.

This is a DAgger-style correction for state-distribution drift. To contain search cost, query only
high-regret, high-uncertainty, novel, or threat-onset states. A risk/novelty gate in the style of
ThriftyDAgger is appropriate.

---

## 8. Priority 5 — create a two-speed reactive/strategic policy

One universal head currently learns two very different regimes:

1. urgent response to a newly observed enemy action;
2. quiet-board strategy, banking, cycling, and committing a win condition.

These regimes have different data balance, latency requirements, and acceptable failure modes.

### Proposed design

* **Reactive response specialist:** triggered by a new enemy play or a sharp urgency increase;
  scores WAIT and complete response candidates immediately.
* **Strategic policy:** runs on the normal cadence for banking, cycling, punish timing, and long-term
  deck plan.
* **Router:** based on threat urgency/event detection, with hysteresis so control does not flicker.
* **Abstention:** if the reactive specialist is uncertain, use the researched counter table or the
  main policy and log the state for later teacher labelling.

This creates a direct training distribution for the user's example — responding correctly to an
enemy play — without asking the same output head to learn every quiet and urgent state at their
natural, highly imbalanced frequency.

### Guardrail

The specialist must not become a permanent rules crutch whose corrected action is credited to the
uncorrected model choice. Store and train on the executed action, preserving the existing live
trainer rule.

---

## 9. Priority 6 — make live replay event-balanced and sequence-aware

### Current limitation

Live DDQN uniformly samples transitions. Rare decisive responses, crown swings, king activations,
and deployment failures are diluted by ordinary steps.

### Proposed replay mixture

A starting allocation, to be measured rather than treated as sacred:

* 25% enemy-play onset and the following response window;
* 20% tower-damage, crown, and major board-swing transitions;
* 15% terminal transitions;
* 15% high TD-error transitions;
* 25% uniform background, including correct waits.

Within each stratum, use TD-error prioritisation with importance weights. Keep the uniform component
so a reward bug or noisy rare event cannot monopolise training.

Store short chunks around events:

```text
2-4 decisions before enemy play
enemy play / urgency change
our response sequence
6-12 seconds of consequence
```

The current n-step return can remain, but event chunks make the causal transition much more likely to
be revisited.

### Update-to-data ratio

Live interactions are scarce and the playing net is tiny. Benchmark performing multiple replay
updates per live environment step or in a post-match burst. Start with 2x and 4x, with a frozen
held-out response-regret set to detect overfitting or catastrophic drift.

Rainbow's most relevant ideas here are prioritised replay and distributional value learning; the
project already has Double-DQN and n-step returns. Add one component at a time.

---

## 10. Priority 7 — learn an opponent belief state

Exact live reconstruction is not available, but the policy can maintain a calibrated belief over
hidden opponent information.

Add simulator-supervised auxiliary heads for:

* probability each opponent card is currently in hand;
* likely next card;
* opponent elixir interval/distribution;
* probability the primary counter is available;
* likely follow-up pressure by lane;
* confidence that an observed body represents a new play rather than a re-detection.

Feed the belief vector to the joint candidate scorer. At live inference, retain distributions and
confidence instead of committing to a fictional exact hand.

Evaluate calibration separately from policy outcome. The scorer should learn conservative responses
when several hidden states imply different best plays.

---

## 11. Priority 8 — improve sim-to-live evidence, not just simulator performance

The search control showed that perfect perception did not improve the existing policy, so perception
is not the leading explanation of the simulator policy's ceiling. It still limits live execution.

Continue the established practices:

* promote detectors only on the frozen live-image gate, never training mAP;
* weight new detector data toward genuine live captures and hard frames;
* use active labelling on uncertainty/confusion rather than more clean duplicates;
* simulate measured detector dropout, false positives, and timing jitter;
* verify grid/warp round trips and aim assists in the same coordinate frame;
* report ghost plays, detector staleness, search skips, and response latency every match.

For temporal policies, validate sim/live motion-channel agreement explicitly. A temporal network can
overfit perfect simulator trajectories more severely than a snapshot model.

---

## 12. Longer-term option — a compact learned world model

Full live `SimEngine` search is fragile because exact HP, opponent hand, unit fields, and precise
positions cannot be reconstructed. A learned model does not need to reproduce all of those fields.
It needs only decision-relevant predictions over the measured 12-second horizon:

* tower damage and crown probability;
* elixir change;
* surviving friendly/enemy board value;
* whether a counter succeeds;
* likely opponent follow-up;
* uncertainty in those predictions.

The candidate scorer could plan through this latent dynamics model, using the existing policy as a
proposal prior. Simulator trajectories provide abundant pretraining labels; recorded live
transitions can adapt the model to real perception and mechanics.

This follows the broad direction of MuZero, Dreamer, and TD-MPC-style planning. It is a substantial
project and should follow, not precede, the cheaper joint-scorer and temporal-memory experiments.

---

## 13. Uncertainty, fallback, and active data collection

“Always best” is not a realistic guarantee under hidden state. The deployable objective should be:

* act decisively when the best response has a clear margin;
* take a safe fallback when uncertainty is high;
* record uncertain/high-regret states for targeted training.

A small bootstrap ensemble or multiple candidate-value heads can estimate disagreement. Use it for:

* abstaining to the counter table on urgent known threats;
* selecting states for search-teacher queries;
* selecting live frames for annotation;
* coherent per-match exploration rather than independent epsilon-random actions.

Bootstrapped DQN is a relevant reference for temporally extended exploration. It should not be added
until the response benchmark can distinguish genuine improvement from behavioural diversity.

---

## 14. Current low-risk experiments that should finish first

### 14.1 Three-seed `bank_hold` confirmation

The one-seed A/B shows:

* control banking collapses monotonically;
* `bank6` remains flat-to-rising;
* `bank2` is unresolved;
* `bank6` ends closest to the one-player human anchor on play rate and X-Bow share.

This is not a verdict because the arm ordering changed during the run and only one seed exists.
Complete the already-prepared three-seed confirmation before replacing the reward or claiming the
banking mechanism is solved.

### 14.2 `canvas_stack` 1 versus 2

The code path already exists, directly addresses motion/timing information, and is smaller than a
recurrent rewrite. It is the most economical architecture screen after the banking confirmation.

### 14.3 Worker-side search parity/throughput

Worker-side search has a verified mechanism but unverified learning parity and speedup. Close those
measurements before using that path to generate a confirmation run or large teacher corpus.

---

## 15. Ideas to deprioritise or not repeat without new evidence

1. **Increase trunk/model size first.** Search extracts a 2.3x win-rate gain from the existing
   representation, and the current model can represent teacher card choice. Capacity may matter
   later, but it is not the leading measured bottleneck.
2. **Card-only distillation.** It works as a mechanism and does not move outcome at the tested
   budget.
3. **A global play threshold.** Search's restraint is state-dependent; the threshold sweep was worse
   in both directions.
4. **A restraint veto by itself.** It removes plays without providing the replacement continuation
   and is measured harmful.
5. **LLM advice in the reaction path.** It is too slow or stale at the current decision cadence and
   is best confined to offline doctrine generation or rare exploration.
6. **Full live simulator search as the primary answer.** Compute became manageable, but exact live
   state reconstruction and position sensitivity remain blockers; observed benefit is unproven.
7. **Simply train PPO longer.** Previous long runs peaked, drifted, or preserved the same banking and
   timing failures. More samples through the same decision interface do not guarantee the missing
   temporal comparison appears.
8. **Judge on training win rate or tiny match samples.** Use fixed-seed response regret and tower
   delta, three or more training seeds, the exact deck venv, pinned threads/hash seed, and matched
   code trees.
9. **Bundle several promising changes.** The project has repeatedly lost attribution. Run one
   intervention at a time with a mechanism metric and outcome metric.

---

## 16. Recommended execution order

### Phase A — establish the measurement

1. Finish the three-seed `bank_hold` confirmation.
2. Build the response-regret benchmark.
3. Freeze a held-out suite of opponent decks/seeds and threat buckets.
4. Reproduce the current reference policy on that suite.

**Gate:** the benchmark must reproduce known differences such as policy versus N=1 search.

### Phase B — test information versus decision structure

1. Run `canvas_stack` 1 versus 2.
2. Train a frozen-encoder joint candidate scorer on rollout scores.
3. Compare hard labels against score/ranking targets.

**Gate:** proceed only if response regret improves on held-out matches, not merely teacher
classification accuracy.

### Phase C — make timing learnable

1. Add short sequence replay and a GRU.
2. Add previous action and event timing inputs.
3. Generate teacher continuations and time-to-next-play targets.
4. Use DAgger-style relabelling on student-visited, high-regret states.

**Gate:** improve both WAIT decisions and their later follow-through. A policy that waits more but
fails to execute the replacement play fails this phase.

### Phase D — adapt to live learning

1. Event-stratified sequence replay.
2. Multiple replay updates per environment step.
3. Opponent-belief auxiliary heads.
4. Uncertainty-driven fallback and data collection.
5. Validate on recorded live sessions before risking autonomous live fine-tuning.

### Phase E — learned planning if needed

Only if the temporal candidate scorer plateaus, prototype a compact latent dynamics model and short
planning over candidates.

---

## 17. Experimental discipline

Every experiment should declare before launch:

* exact git commit and dirty status;
* exact deck venv/interpreter and torch version;
* `PYTHONHASHSEED` exported before interpreter start;
* pinned Torch threads for evaluation;
* training seeds as the unit of analysis, never pooled matches pretending to be independent;
* fixed opponent seeds/decks;
* one changed variable;
* mechanism metric and outcome metric;
* pre-committed stopping rule and minimum effect;
* whether the policy is sampled or greedy;
* whether drills are mixed in;
* whether the score uses shaped reward or outcome-grounded rollout value.

Suggested standard report:

```text
MECHANISM
  response regret
  top-1/top-3 candidate agreement
  WAIT false-positive/false-negative
  follow-through at +3/+6/+12 s
  banking, play rate, card mix, placement diversity

OUTCOME
  tower delta
  crown delta
  win rate with uncertainty
  foundational and generated-drill pass rates

LIVE ROBUSTNESS
  decision latency
  detector freshness/recall bucket
  ghost plays and redirected actions
  sim/live action agreement on recorded states
```

---

## 18. Primary external references

* Hausknecht and Stone, **Deep Recurrent Q-Learning for Partially Observable MDPs**:
  https://arxiv.org/abs/1507.06527
* Kapturowski et al., **Recurrent Experience Replay in Distributed Reinforcement Learning (R2D2)**:
  https://openreview.net/forum?id=r1lyTjAqYX
* Ross, Gordon, and Bagnell, **DAgger — A Reduction of Imitation Learning and Structured Prediction
  to No-Regret Online Learning**:
  https://proceedings.mlr.press/v15/ross11a.html
* Hoque et al., **ThriftyDAgger: Budget-Aware Novelty and Risk Gating for Interactive Imitation
  Learning**:
  https://proceedings.mlr.press/v164/hoque22a.html
* Hessel et al., **Rainbow: Combining Improvements in Deep Reinforcement Learning**:
  https://aaai.org/papers/11796-rainbow-combining-improvements-in-deep-reinforcement-learning/
* Osband et al., **Deep Exploration via Bootstrapped DQN**:
  https://arxiv.org/abs/1602.04621
* Schrittwieser et al., **MuZero — Mastering Atari, Go, Chess and Shogi by Planning with a Learned
  Model**:
  https://arxiv.org/abs/1911.08265
* Hafner et al., **DreamerV3 — Mastering Diverse Domains through World Models**:
  https://arxiv.org/abs/2301.04104
* Hansen, Su, and Wang, **TD-MPC2: Scalable, Robust World Models for Continuous Control**:
  https://arxiv.org/abs/2310.16828

These references motivate directions; they do not establish that those directions work in this
project. Local measurements remain the acceptance authority.

---

## 19. Local evidence map

Read these before implementing:

* `README.md` — architecture and pipeline overview.
* `HANDOFF.md` §4x / current §5 sections — rollout search, gate investigations, banking A/B,
  worker-side search, and retractions.
* `research/sim_parity/ledger/rollout_search.md` — full search sweeps and controls.
* `research/sim_parity/ledger/distillation.md` — privileged-teacher gap, card/gate agreement, and
  the null outcome result.
* `icebow/src/clashrl/model.py` — current factored network and spatial cell head.
* `icebow/src/clashrl/train_rl.py` — live DDQN, gate, replay, action selection, and exploration.
* `icebow/src/clashrl/train_sim_ppo.py` — simulator PPO and search imitation integration.
* `icebow/src/clashrl/sim/rollout_search.py` — teacher and outcome-grounded scorer.
* `icebow/src/clashrl/sim/live_search.py` — live reconstruction limitations and guards.
* `icebow/src/clashrl/detect_obs.py` plus `config/config.yaml` — semantic, predictive, and temporal
  canvas plumbing.
* `icebow/src/clashrl/sim/scenarios.py` and `drills_icebow.py` — drill infrastructure.

---

## 20. One-sentence handoff

If only one thing survives this document, it should be this:

> **Measure regret at enemy-play events, then teach a temporal model to rank complete
> WAIT/card/placement continuations; the evidence says editing individual heads cannot recover the
> search teacher's timing advantage.**
