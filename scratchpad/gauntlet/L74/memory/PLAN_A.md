# Plan A: match memory (APPROVED by the owner 10-25, with the scope change below)

**Owner scope change (10-25):** memory must inform overall strategy and plays across ALL cards and abilities ("which plays at which game states work? which plays don't?"), not only X-Bow and Rocket strategy. Section 2.1 carries a generic outcome for every play; the X-Bow / Rocket / combo outcomes stay as specialised fields.

**Compute (10-25):** owner offers one 5x RTX 4090 pod (~320 vCPU) replacing the double pod + 3 old pods. Lead: yes, if the cgroup quota is verified, and the new pod is rented and filled (code tree, venv + runtime, datasets, CLXIII / CLX / opponent ckpts, the running branches' latest ckpts, baselines) BEFORE the old pods stop. Use: one learner per GPU (~60 vCPU actors each) = 5 arms at once on one disk.

Owner 10-25: "a memory of every event that has happened so far in the match and their results will greatly benefit the model's
mid-match performance and adaptability"; deadline removed; go for A (full memory), B (compact summary) on top if needed. Bundle:
Rocket use, Rocket + Tornado combo, failed / forced X-Bows. Grades: (a) measured, (b) plausible but untested (with its test).

## 1. Where we are

**What the model sees at each decision today (a, code: `model_gen.global_features`, `obs_contract`, `public_observation`):**
- the current board (unit tokens + 22 cue floats each), own elixir, the clock, tower HP fractions for all 6 towers, crowns
- its own last **3** plays and the opponent's last **3** plays, each with "seconds ago" (`PAST_K = OPP_PAST_K = 3`)
- the opponent's cycle: up to 8 cards seen, with plays-since and age (`opponent_cycle`)
- no recurrent state

So it cannot know that its last 10 X-Bows failed, that the opponent always answers with the same card, or how much its
Rockets have chipped so far beyond the current tower HP.

**The three behaviour gaps (all measured on the CLXIII / CLX gate rows, 1,920 SIM matches each, plus live logs):**

| gap | CLXIII | reference | source |
|---|---|---|---|
| keeps forcing X-Bows: reach X-Bows played after 2+ failures in the same match | 1.27 / match (E4) | CLX 1.05; pros switch (INVESTMENT.md) | xbow_count.py (a) |
| matches with 3+ failed reach X-Bows | 29% (E4), 17% (cal I u40) | CLX 25% / 15% | (a) |
| Rockets / match | 0.34 SIM, 0.33 live (6 matches) | CLX 0.50 SIM, 0.51 live (234) | rocket_count / live_rocket (a) |
| tower Rockets / match (chip), OT | 0.27, OT 0.19 | CLX 0.41, OT 0.31; pros Rocket the tower 2.4-5.4x more / min | (a) |
| Rocket + Tornado combos | 0 live (6 matches) | CLX 14 in 234 matches, ~all from the live RULE | live_rocket (a) |
| tower Rockets in EQ-ready / Hog-unaffordable moments | ours 4% / 13% of investment plays | pros 55% / 70% | INVESTMENT.md (a) |

**Why RL has not fixed them (a / b):**
1. No memory: the within-match switch is not representable (a, code).
2. The SIM rewards forcing X-Bows: SIM opponents let X-Bows lock more than humans (with a blocker in the window 48 vs 37%,
   late answers 69 vs 54%; DIAG_12 section 8.8) (a). So even with memory, switching only pays if the opponent denies like
   humans do.
3. Rocket chip pays only at the match end (tiebreak / crowns): weak credit assignment (b).
4. The combo is a live RULE (`--rocket-tornado only`); the SIM eval and training have no combo rule and no combo reward, so the
   model never learned it (a).

## 2. Design

### 2.1 The event memory (what is remembered)
One builder, `pipeline/match_memory.py`, fed by `public_observation` (the code the SIM env, the live reader and the pro dataset
already share for `opp_cycle` / `opp_past`). Causal: a decision at tick t only sees events with tick < t, and outcomes that
were already decided by t. Events (up to the last 128 in the match, oldest dropped):

| event | fields | from |
|---|---|---|
| play (both sides) | side, card, form, x, y, tick, own elixir before (own side only) | the public play history |
| tower damage | side, tower (L / R / K), HP lost (fraction), tick; debounced (>= 2% per 1 s window) | tower HP per decision row |
| tower fall | side, tower, tick | tower alive flags |
| **play outcome (EVERY play, both sides, incl. abilities)** | within 10 s after the play: enemy tower HP lost, own tower HP lost, enemy elixir value removed within 5 tiles of the play, the play's own elixir, whether its units / building survived; pending until the window closes; the game state at the play (phase, elixir, crowns, tower HP margin) is in the play event itself | derived: play + board + tower HP series |
| X-Bow outcome (own and opponent) | locked / failed / pending, damage dealt in its life, which opponent card answered it (first enemy body placed within 6 tiles in its first 4 s) | derived: play + tower HP series |
| Rocket outcome (own) | tower hit (and HP), troop value killed, part of a combo (Tornado within -24..+40 ticks) | derived: play + board + tower HP |

Plus the compact summary (B), computed from the same events (per card for the generic outcome: plays, mean tower-HP swing, mean value removed per elixir; and): own X-Bows placed / locked / failed this match, failures since the
last lock, damage per X-Bow, tower Rockets and their total damage, time since our last lock, opponent's most frequent X-Bow
answer card, our princess HP lost per opponent push.

### 2.2 The model change
- A small causal event encoder: per-event embedding (card / form via the existing card embedding, side, type, x / y Fourier,
  time-ago, outcome fields) -> 2 transformer layers, d = 64, over the event list -> a 64-d memory vector, plus the summary (B)
  through a small MLP.
- Both enter the existing global feature vector through **zero-initialised** projections. Every existing CLXIII weight is
  kept. **At initialisation the new model plays exactly like CLXIII** (test: identical action log-probs on 10k rows). The
  memory can only change behaviour once training finds a use for it.
- New feature version (fv7); the loaders keep fv6 models working unchanged.
- Cost: ~128 events x 2 small layers per decision; measure live latency (today ~100 ms median on the laptop, on CUDA).

### 2.3 Training stages
- **S0 infrastructure (new pod 33906: 2x RTX 4090, 108.8 vCPU quota, 503 GB RAM, 120 GB disk).** Sync cb_stepd (with today's
  patches: habit + leak + xbow terms, tau_phase, exploiter tau), venvf15 + the fin15 runtime, datasets (gen_v32 fv5 466 MB), the
  CLXIII / CLX checkpoints, the calibrated opponents. Smoke the current recipe there.
- **S1 memory builder + tests.** Causality test (no event after t can change features at t), identical-output test for SIM
  vs pro-path on the same replay, unit tests per event type.
- **S2 memory parity, live vs SIM (gate).** On ~200 recorded live matches: build the memory from the live logs (reader path) and
  from the same matches re-run through the SIM path where possible (the parity harness), and compare per event type. This
  catches reader misreads that would give the model a false memory.
- **S3 imitation warm-start.** CLXIII + memory (zero-init) fine-tuned on the 3.52 M pro rows with memory inputs. GPU 0. Gates:
  pro agreement not worse than CLXIII by > 0.5 pp; pro-direction probes (below) move toward pros.
- **S4 opponent X-Bow denial (parallel, GPU 1 / CPU).** Without it, switching does not pay in the SIM. Train / select an opponent
  whose X-Bow lock rate matches live (target: with a blocker in the window ~37%, late answers ~54%; overall within +-5 pp of
  live) without breaking the push calibration (1/42 cells). Candidates: W18 R1 (princess redirect penalty, built), R4
  (starts from live Ranked bridge-X-Bow states, built, never run). Then train against a mix: calibrated I u40 + the denial
  opponent.
- **S5 RL.** The succ48 recipe (calibrated opponents, tau_phase, T_gate 0.3, leak penalty, idle / trade habit terms) plus:
  - `shaping: tower_crown` (potential-based tower-HP / crown margin: a chip Rocket or a tower hit is credited when it lands;
    the optimal policy is unchanged);
  - `habit_xbow_w` (failed reach X-Bow cost; already built and smoked);
  - the spell-value term for Rockets on troops with the lone / combo split (below).
  - Arms: 2-3 seeds of the memory model + 1 control (CLXIII, same recipe, no memory), so the memory's effect is measured
    separately from the reward changes.
- **S6 gates, then the owner's live trial** (no live without the owner).

## 3. The three concerns, integrated

### 3.1 Failed / forced X-Bows -> switching to defence + Rocket cycling
- Levers: memory (it can see "X-Bows failed N times, opponent answers with card C") + failed-X-Bow cost + an opponent that
  denies like humans + tower_crown shaping (Rocket chip and defensive tower HP get credit).
- Metrics (SIM, every check; live after deploy):
  - reach X-Bows per match after 2+ failures (CLXIII 1.27): target <= 0.6, without raising the failed share;
  - tower Rockets in matches with 2+ failed X-Bows: target >= 2x CLXIII;
  - P(bridge X-Bow | opponent answer ready) vs P(... | cycled): must flip to the pros' direction (pros 1.61 vs 2.46; CLX
    6.26 vs 3.84 per opportunity-minute).

### 3.2 Rocket use and Rocket cycling
- Levers: tower_crown shaping (dense chip credit), memory (Rocket damage so far, X-Bows failing), the spell-value term for
  defensive Rockets on troops (princess-in-blast bonus).
- Metrics: Rockets / match and tower Rockets / match by phase (targets >= CLX-with-hazard 0.50 / 0.41, OT >= 0.31), defensive
  Rockets on heavy pushes (rocket_slices S1), Rocket after a failed X-Bow (S3). Trade metrics must not get worse: a Rocket into
  nothing is a waste.

### 3.3 Rocket + Tornado combo (carefully: Rocket alone often suffices, Tornado sometimes needed, sometimes neither)
- An offline opportunity detector first (reuse `decision_options.rocket_tornado_plan` on recorded board states, SIM and live):
  classify every moment with Rocket (and Tornado) in hand into: lone Rocket worth it / combo needed (the pull holds >= V, no
  single blast does) / neither. Then measure what the model did in each class.
- Learned combo through the existing spell-value reward with the lone / combo split (`spell_value_lone`): the Tornado row is
  credited only with its MARGINAL value over the best lone Rocket. Tornado-for-its-own-sake earns nothing, and a combo where
  a lone Rocket was enough earns nothing extra.
- Metrics: in "combo needed" moments, combo rate >= the live rule's; in "lone enough", Tornado added <= 10%; in "neither",
  Rocket played <= 5%.
- SIM parity of Tornado pull + Rocket timing (the combo window measured 10-17) is checked before training on it.
- The live combo RULE stays until the learned combo matches or beats it on these metrics; then it is retired (owner's
  spell-use rule: learned spell use, live rules only for the finishing Rocket / Log).

### 3.4 All cards / abilities (owner scope change)
- The generic play outcome lets the model learn, per card and per game state, which plays worked earlier in THIS match (e.g. Tesla placements that held vs got bypassed, Knight vs Skeletons answers that traded well, Ice Wizard ability presses that saved a tower).
- Metric (new, every check): per card, the share of plays repeated after a bad outcome vs after a good one in the same match (adaptation index); pros as the reference (pro re-drive rows carry the same events). Target: our index moves toward the pros' without hurting win rate.
- The memory builder, tests and parity gates cover every card; the ability press events (Hero Ice Wizard) are included.

## 4. Gates (in order)

| gate | bar |
|---|---|
| G-mem-0 init identity | memory model = CLXIII on 10k rows (log-prob diff < 1e-6) |
| G-mem-1 causality | no future event changes any feature (randomised test) |
| G-mem-2 live parity | play events matched >= 95% (card + side within 1 s); tower-damage events >= 90%; X-Bow outcome agreement >= 90% |
| G-imit | pro cell / card agreement >= CLXIII - 0.5 pp; probes move toward pros |
| G-opp | opponent X-Bow lock within +-5 pp of live overall and in the blocker / late-answer cells; push gate still 1-2 / 42 |
| G-drift | succ48 drift checks (99%): no habit drift; leak <= 12.3 s at full |
| G-behaviour | section 3 targets (X-Bow switching, Rocket rates, combo classes) |
| G-promote | vs CLXIII paired, pooled E4 1,920 + calibrated I u40 1,920: CI low > 0 on one, not worse on the other |
| live | owner-run trial |

## 5. Rough timeline (no deadline; estimates)
- S0 infra: 2-3 h. S1 builder + tests: 6-8 h. S2 parity: 3-4 h. S3 pro memory dataset build 2-4 h CPU + imitation 4-8 h GPU.
- S4 opponent (parallel with S1-S3): 6-10 h. S5 RL: ~150-300 updates per arm, 2 arms at a time on 108 vCPU (~2.5 min / update
  each): 8-12 h per round. S6 gates: ~2 h per candidate.
- First memory-model candidate: ~2.5-4 days. Every run goes in the experiment ledger.

## 6. Risks
- Reader misreads -> false memory live (G-mem-2 catches it; events are debounced; unknown reads are "unknown", not zero).
- Pro data: tower HP per row comes from the replay pipeline; pro outcome labels (X-Bow locked) are as good as those rows (b:
  check on 100 replays against their recorded crowns / falls in S1).
- The opponent may not reach human-like denial; then switching is under-rewarded in SIM (G-opp is the check; fallback: a
  scenario curriculum from live Ranked X-Bow states, R4).
- Memory-model RL may drift like earlier recipes (G-drift every 25 updates; branches + gates, as in succ48).
- New pod: 108.8 vCPU (not 128), 120 GB disk, shared host (load ~33 at login).

## 7. Decisions for the owner
1. Approve the plan (or change scope).
2. The 4 old pods: my recommendation is to stop 3 once S0 is done and keep 32525 for baseline evals during S1-S3 (or stop all 4).
3. CLXIII stays wired for live meanwhile (your call when to play it).
