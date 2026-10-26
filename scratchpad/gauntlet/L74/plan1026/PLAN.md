# Plan: a faithful engine, human-like opponents, then one training stack that is identical from SIM to live

## Context
Owner, 10-26: no pods, training, experiments or live deploys until there is a plan that knows what it is doing. Three
requirements: (1) an engine that is more than 99.9% accurate, built from the game files plus our replays and live logs;
(2) opponents that play like real humans, deck by deck; (3) a reward and training design built from the whole project
history, so the old failures are not repeated, and aimed at adaptive play that beats humans (top 1,000 Ranked).

Grades used below: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted.

**Why the old approach failed (a).** Fifteen eras of training gave SIM gains that did not reach live play. For each
promotion, SIM gain vs live gain was: +10.2 vs +4.8, +7.1 vs +1.0, +4.4 vs +2.8, +3.4 vs +0.8, +5.6 vs +1.0. The slope of
live gain on SIM gain is 0.38 [-0.30, +1.06], so a SIM gain predicts almost nothing live. The SIM over-predicts the live
Mark by more each time: CXXIV +7.9, CLIII +18.4, CLX +24.3 pp; CLXIII is 72.6 / 58.8% in SIM vs 47.8% live.
The owner's diagnosis, "the SIM is too weak to train on", fits this. But the gap has **at least four measured causes, and
the engine is only one of them**:
- engine: fight parity 0.920 (goal 0.975); whole-match crown sequence 0.506;
- opponents: none passes the human-likeness test; one network serves every deck; every RL opponent trained only vs icebow;
- the bot's own live execution: lost and slow taps explain about half of the overtime gap (-5.2 of 10.3 pp);
- confounds: a tower level-up alone was worth +15.8 pp live for the same model.
A 99.9% engine with the old opponents would still mispredict live. Each cause is therefore measured separately (the
attribution rule in Pillar 2).

## No-discard rule (owner 10-26; governs every fallback below)
A core part of this plan is never dropped because it fails a test or gives unfavourable results. Only the owner can
remove one. Core parts:
- the three pillars and their 99.9% targets;
- R_exchange, fork credit and every trigger;
- every owner-named macro (sneaky lock, Rocket cycling, combo, king redirect, defensive Rockets ...);
- match memory;
- Mortar / siege defence;
- barrel_lane;
- the Hero IW ability.

A failure starts the **iterate loop**, in the same turn it is found:
1. Diagnose the cause with a measurement, choosing among: fidelity (engine), opponents, credit horizon, noise, an
   implementation bug, or the design itself.
2. Fix that cause.
3. Re-test.
4. Repeat until it passes.
Each round goes in LEDGER.md with its numbers. A failed test stops the CANDIDATE CHECKPOINT from advancing, never the
component. If two rounds go flat, the approach to the same goal is redesigned and reported to the owner with the evidence;
the goal stays. Iterating does not guarantee a fixed date, so dates below are estimates and are re-reported when a loop runs.

**The 13 failure patterns and the guardrail for each:**

| # | pattern (a) | guardrail in this plan |
|---|---|---|
| 1 | train/deploy mismatch (anti-stall, sampled vs hard gate = the 10-26 leak, IW press 5.4 vs 1.9, levels 11 vs 16, live-only rules) | ONE `decide()` for rollouts, forks, SIM eval and live; identity test L0 |
| 2 | SIM gains don't transfer | engine + opponent pillars first; every candidate gets a predicted live interval, checked on a sealed live block |
| 3 | reward terms that pay a behaviour get farmed | no behaviour terms. Dense terms are zero-sum outcomes (tower HP, elixir destroyed / leaked), weighted by a fit to REAL match results, and must pass a farm audit before any run |
| 4 | potential shaping is null | the dense terms are not a zero-terminal potential; their match totals change the objective on purpose (by at most half a win) |
| 5 | SIM win doesn't pay the wanted habits (chip Rockets LOSE in SIM: 0 chips 0.696 vs 1 chip 0.582; pros 0.392 -> 0.564) | incentive audit by SIM forks BEFORE training; a mismatch is a fidelity bug for pillar 1/2, never patched with reward |
| 6 | drift under continued RL; long runs never converge | NO leash. Remove drift's measured causes (decoder mismatch, SIM exploits, a moving pool); cut gradient noise; train on drift-prone states; detect, select and branch (P5) |
| 7 | opponents wrong in a new way each round | pre-registered, human-referenced scorecard (levels A-D) |
| 8 | instruments blind or gamed | metrics read played games through one code path, with a planted-bug test |
| 9 | seed noise SD 2.4 pp ~ effect size | 2 seeds per arm; select on one block, confirm on sealed blocks |
| 10 | imitation re-bases cost more than RL recovers | no imitation into policy heads (aux heads only, like the working S3-aux encoder) |
| 11 | decode rules don't generalise | only the finishers stay as rules, and they run in every path |
| 12 | long-horizon credit too thin | counterfactual fork credit (below) |
| 13 | adaptation can't pay without varied opponents (CLXIV: X-Bow again within 30 s after a fail 39% vs 10.5% after a lock) | human-model opponents must reproduce live's between-match spread; adaptation-value audit before any memory promotion |

## State now (10-26 ~11:20 EDT)
- Live off. `CKPT_OVERRIDE` still points at CLXIV MEMORY (3/11 live). Not reverted (the owner's call, decision 2).
- Pods: 33920, 33458 and 33411 idle. Their chains (brT10_s121, brT10_s122, brT05_s123) ended 14:28-14:31Z with
  "DRIFT FAIL" and an EMPTY drift report after ~25 min: a run failure, not a measured verdict. 32657 is still training
  brT10_s107 (4 h, GPU 0%): plan mode blocked stopping it; it is stopped first thing on approval (step 0).
- Stopped today: the fork-credit build agent. Its edits to `pipeline/e1_eval.py`, `pipeline/search_s0.py` and
  `pipeline/cf_credit.py` are uncommitted. It was sorting six test failures (pre-existing or its own) when stopped. They
  are reviewed in Pillar 3 before any use.

## What "99.9%" will mean
I can't promise the literal readings, because they cannot be checked. Below is the strictest version that can be.
1. **Engine: SME (seeded match exactness).** Run a held-out real match through the engine with its real inputs: decks,
   levels, deal orders, battle seed and every play. It passes only if every reader frame matches exactly: each unit's
   card, side, position and HP; tower HP; projectiles; spells; our elixir to 1e-4; our hand. **Target: the 95% lower
   bound on SME is at least 0.999**, i.e. 0 failures in 2,996 fresh matches (or at most 1 in 4,744). An exact match makes
   all ~35 of its fights exact, so this is stronger than any per-fight score. Frames the reader flags itself are
   excluded and counted. Per card: a bound from that card's own match count. Cards short of data get targeted supply (TV
   replays; lab battles with the owner's OK) until they are bounded.
2. **Opponents: coverage H.** "A judge can tell bot from human at most 50.05% of the time" would need about 3.8 M matches
   per side to verify. Instead, each live opponent falls in a cell: a head deck, or else its archetype (10 archetypes
   x 3 trophy bands). A cell passes only by an **equivalence test** (90% CI inside a margin set by how much two human
   populations differ: 12k vs 13k humans = 0.10). A small sample therefore fails a cell; it can never pass by default.
   **H = live-traffic-weighted share of passing cells; target H >= 0.999**, i.e. effectively every opponent the bot
   meets is modelled by a passing cell. One failing Hog cell (~18% of opponents) gives H ~ 0.82.
3. **Training: no % target.** The goal is live win rate and trophies. A SIM result counts only through its predicted-live
   interval checked on a sealed live block.

## Pillar 1: Engine
**Choice (b, decided by measurement on day 8): switch to crforge, keep fin16 as the fallback.**
Law-by-law RoyaleSim fixes cannot reach 99.9% (a). Each round moved fight parity by +0.0002 to +0.002, about 32% of
failures are unexplained, and RoyaleSim uses its own unit scale and update order. crforge reads Supercell's own tables,
models the game's random number generator and deck deal, and reads the game's replay format. It claims 10,000 / 10,000
battles tick-exact, but that data is private (b). Only our own measurement decides.

- **Stage 0 (days 0-2, 1 pod, CPU).**
  - Build fin16 with `L74/parity/fin16/fin16_chain.sh` (adds the 10-19 balance table). A/B: the c13 check must be
    byte-identical and c22 must improve. Register `fin16-linux` in `pipeline/royale_runtime.py` and
    `pipeline/royale_heroiw.py`. No further RoyaleSim law rounds after this.
  - Pin crforge (commit ad8ef3a or newer, JDK 17) on the pod.
  - G0, random-draw census: which cards draw random numbers after the deal. This sets how many matches need a seed.
  - G1, seed recovery from our logs: our deal order (8! = 15.3 bits) + our account word + a brute force over 2^28 draws
    (~5-10 s per match on 54 vCPU) + the opponent's deal. Pass: a unique verified seed on >= 90% of matches with an
    opponent tag (b).
- **Stage 1 (days 2-8): pilot.**
  - Build an extractor (live log -> crforge inputs). It reuses `L74/parity/fights.py` and crforge's `ReplayBattle.build`.
  - Score >= 300 post-10-19 live matches on crforge, fin16 and fin15 with the same inputs.
  - Score SME on >= 50 seeded matches, recording the first divergence of each failure.
  - Run 20k HF replays through crforge to count faults.
  - Measure throughput.
- **Decision D1 (day 8):**

  | check | go |
  |---|---|
  | crown sequence, crforge minus fin16 | >= +0.15, bootstrap CI above 0 (fin15 0.506) |
  | SME pilot | >= 45/50, failures traced to <= 5 mechanisms |
  | faults on HF replays | <= 0.5% |
  | cost | <= 1.5 core-s per match, <= 16 GB per pod for 24 actors |
  | parsed stats = device table pull | 100% |

  A failed D1 check starts the iterate loop on that check; the 99.9% target stays.
  - Cost above 1.5 core-s per match: a batched-env rework (+4-6 days), then JVM tuning and more actors per pod, until it
    passes.
  - Crown-sequence gain below target, or SME below 45/50: diagnose each failure's first divergence. Is it our input
    extraction (levels, deal, seed, play ticks), the game version, or crforge itself? Fix it in the extractor or our
    crforge fork, then re-pilot on fresh matches.
  - Training stays on fin16 meanwhile.
  - If crforge's own design proves unable to reach exactness, the same SME target moves to a fin16-based engine with
    crforge-confirmed laws ported one by one. That is a change of route, reported with the evidence, not a dropped target.
- **Stage 2 (days 8-22): integration.**
  - New `pipeline/crforge_core.py`, the same interface as RoyaleSim's engine. It covers reset / step / state / save_state /
    load_state, and the forking that `search_s0` and `cf_credit` need. It outputs RoyaleSim's units, so nothing
    downstream changes.
  - One engine seam in `pipeline/royale_env.py`, a runtime id with a jar / table hash manifest, and a small Java shim for
    tower troops, levels, seed setup and trace dumps.
  - **D2 (~day 22):** `rl_royale --smoke` passes; two runs give identical update-0 rows; time per update <= 1.15x fin16;
    CLXIII re-baselined; SME on dev >= 0.98. No checkpoint carries across engines without a re-gate.
- **Stage 3 (from day 3; certificate attempt ~days 30-45).**
  - Nightly: each live match + its battle-log entry -> seed recovery -> crforge replay -> SME into METRICS.md.
  - Each failure becomes a minimal scenario -> fix in our crforge fork -> re-run dev + crforge's 2,140 core tests.
  - Supply: continuous live play gives ~130 matches a day, so 3,000 seeded matches take ~23 days. TV Royale harvesting
    (owner-gated) adds up to ~800 a day for the no-seed stratum.
- Mortar specifics (a): stats equal the device tables; fight parity 0.971 [0.923, 1.0] on n 35. It gets its own SME
  per-card bound and a shot template.

## Pillar 2: Human-like opponents
**One network, conditioned on deck, trophy band, mode and match memory, trained by imitation on human data replayed
through the faithful engine.** Strength is calibrated in an order that costs no style first.
Why the old opponents failed (a):
- the imitation data was bad: public-elixir inputs, sightings 24% late, invisible spells;
- the timing target was a sampling artefact: wait rows every 40 ticks, so the gate stayed flat at 0.685;
- every RL partner was icebow;
- every family traded style for strength (O2b style 0.65 at 83.8% for CLX; I u40 at 48.8% but style 0.78).

- **Data.**
  - HF IL_Replay: 252k replays, 17.8 M actions, 52,566 decks; 86% Path of Legend, 88% at level 16.
  - The pro corpus at true levels.
  - ~3,100 live matches (51,285 opponent plays at >= 12k).
  - All of it is replayed through the D1 engine: tier A = full match valid; tier B = prefix up to the first divergence.
  - Live splits are strictly by time: train / calibration block / **sealed block** (never trained or tuned on).
  - Self-check: the same row builder on OUR seat must reproduce the live decision inputs on >= 99% of fields.
- **Model** (edits to `pipeline/model_gen.py`, `dataset_gen.py`, `train_gen.py`):
  - A **timing head** replaces the gate: per 10-tick slot, P(play) plus the exact tick inside the slot. It is trained as
    an exact survival likelihood.
  - A deck encoder: a set transformer over the 8 cards, plus a deck id with 20% dropout.
  - Band / mode / era tokens, an ability-press head, and match memory v2 trained jointly (not a zero-init adapter, so the
    S3 constant-offset bug cannot recur).
- **Training.**
  - Pretrain on HF + pro, then fine-tune on live rows (how humans play against OUR bot).
  - Per-deck fine-tunes serve only as a yardstick (within 0.03 nats, or add 10 archetype adapters).
- **Strength calibration per band**, stopping at the first step that passes:
  1. band token;
  2. card / cell temperature (timing untouched);
  3. RL with a FIXED pull toward the imitation policy, with the timing and ability heads frozen. Partners: the bot pool
     over every deck, plus human-model vs human-model.
  If no step reaches the band's strength with style intact, run the iterate loop on BOTH: diagnose why (model capacity,
  data, memory use, missing per-player style latent z, fixed-pull weight), fix, re-calibrate, until strength and style
  pass together. **A non-human opponent is never shipped, and strength is never given up.** The bot plays with its
  measured live tap handicap in every calibration.
- **Scorecard** (`L74/opp_model/humanlike/scorecard.py`, `disc.py`, `predict_live.py`; thresholds pre-registered in
  `THRESHOLDS.json` with a logged sha before any training):
  - A, per decision: card / cell agreement >= the human-human ceiling (43.7% card, 27.5% cell); NLL; calibration;
    timing gaps ~ Exp(1) after rescaling (KS <= 0.02); memory actually used.
  - B, closed loop: ~30 behaviour stats + per-archetype signature stats. Every stat |d| < 0.10 vs re-driven humans;
    vs live, RMS d <= 0.10 (today E4 0.93, I u40 0.78, O2b 0.65; human floor 0.05). B3: between-match spread ratio in
    [0.9, 1.1].
  - C: a freshly trained discriminator tells model matches from human matches at AUC <= 0.55 (<= 0.58 per archetype).
  - D, outcome parity on the sealed live block (>= 1,500 matches at one Mark): mean predicted win within +-4 pp of live;
    each archetype with n >= 150 within +-8 pp; today CLXIII is +24.8 / +11.0 pp and Mortar 28.8 vs 66.8%.
  - **Attribution rule:** if A-C pass and D fails, the gap is assigned to the engine or the bot's live execution, not
    the opponent.
- **Siege facts the opponents must reproduce** (this is what makes memory pay). Against our X-Bow, the live conditional
  structure: P(lock | our last X-Bow failed) vs P(lock | it locked), zero-lock share 9-16% (SIM today 3-7%), lock rate
  0.13-0.74 by archetype. Mortar decks are weighted 3x in training (today 2.9% of draws).
- **Timeline:** opponent day 0 = D1 (engine replays faithful) = calendar day 8.
  - Scorecard and baselines: before day 8.
  - Re-drive: days 9-11.
  - Rows: days 11-13.
  - Pretrain: days 13-17.
  - Live fine-tune: day 18.
  - SIM wiring and levels B / C: days 18-20.
  - Fix rounds: days 20-24.
  - Calibration: days 24-31.
  - Freeze -> **usable ~day 32 (day ~40 with a 30% buffer)**.
  - Sealed block and D verdict: **~day 43 (day ~55 with buffer)**.

## Pillar 3: Decision stack, reward, training
**P1, deploy exactly what is trained (fixes pattern 1 at the root).** Today there are three decision stacks that drift
apart (a): rollouts (`e1_eval.sample_decide_batch`), SIM eval (`decision_options.decide_batch` with a hand-copied subset
of the live flags in `L74/livecal/livecal.py:29`, which is missing barrel_lane, lethal_quiet, rocket_value, rocket_tornado,
log_air and the IW press), and live (`live_gen_v2.decide`, a line-by-line re-implementation).
- One `decide()` in `pipeline/decision_options.py`, called by all four paths.
- The SIM config is generated from `L70/live/LIVE_OPTIONS`; a SIM eval whose options differ from the deployed file is
  refused.
- Successors deploy the sampler itself: gate `Bernoulli(sigmoid((z - logit tau)/T))` at T 0.1, applied per unit of time
  so live and SIM cadence agree. Measured cost of a T 0.1 sampled gate vs greedy: -0.42 pp [-5.6, +5.0] (a).
- Rules: the finishers (lethal Rocket / Log + lethal_quiet) and **barrel_lane** (owner: it covers a reader issue that
  training cannot fix), inside `decide()` everywhere, so successors train with them. Rows they force are marked and left
  out of PPO.
- The IW press uses the live rule in every path.
- `pipeline/tests/test_decide_identity.py`: recorded rows give identical logits, log-probs and actions through every path.
**P2, the reward: R = R_win + R_exchange + R_fork (P3, incl. the macro alternatives of P6). No KL term toward any
reference policy.**
Is the owner right that win-only is too weak? (a) yes: win-only signal-to-noise was ~0.2 (10-07), and credit over ~20
decisions is thin (pattern 12). But every earlier non-win term also failed (a), for three identifiable reasons:
- it paid a behaviour (rocket_tower -4.7 / -6.5, tornado_king -7.9 / -10.9, the generic multiplier);
- it let passivity score (A3 trade: hold-to-10 and never-spells out-scored the imitation policy);
- it counted our own banked elixir as progress (LIVEPHI: P(win) .39 -> .60 with own elixir, so it paid banking).
R_exchange is built to remove each of those causes:
- **R_win:** +1 / -1 / 0 at match end, by the real tiebreak rule. Still the largest term.
- **R_exchange, dense, zero-sum, outcome-only.** Each tick: r = sum over k of beta_k x (our gain in f_k minus theirs).
  Each feature is counted identically for both sides:
  - princess / king HP lost, king activation, crowns;
  - **elixir destroyed**: the elixir cost x HP fraction of every unit or building killed or damaged, spells included;
  - **elixir leaked** at 10, counted as our loss, so holding at full elixir is never free (the fix for A3's
    hold-to-10 failure).
  There are no position terms, no banked-elixir term and no per-card or per-action terms. The weights beta_k are **not
  hand-set**: they are the coefficients of a phase-split (1x / 2x / OT) logistic fit of the REAL match result on these
  running totals. The fit uses HF replays re-driven on the D1 engine plus our live logs (2-tick HP frames), so the
  exchange rates are those of real games. Earlier fit: ~22-25 elixir per princess.
  - Because the terms are zero-sum and identical for both sides, any action the opponent can mirror nets zero; doing
    nothing earns nothing and leaks.
  - The match total is capped at 0.5 of a win, so a loss with a "good exchange" still scores below a win.
  - The objective becomes "win, and win the exchange the way winning humans do". This is a deliberate change of the
    optimum, not a potential.
- **Gates R_exchange must pass before ANY run** (`L75/ladder/farm_audit.py`):
  - X1, real-data validity: held-out AUC on real matches at 60 / 120 / 180 s, calibration, and signs as expected
    (destroying elixir +, leaking -, princess HP lost -).
  - X2, farm audit: score each policy by the composite return and by win rate. Policies: hold-to-10, never-spell,
    Rocket every tower chance, all-defence, X-Bow spam, Rocket-on-every-tank, CLXIII, pro imitation. **No exploit
    policy may score above CLXIII on the composite while winning less**, and rank correlation with win rate must be
    >= 0.8. A3 failed exactly this test.
  - X3, SIM vs real: the same fit applied to SIM matches must be calibrated on SIM results. A mismatch is a fidelity bug
    for pillar 1 / 2; it is fixed there and X3 is re-run.
  - X4: the incentive-audit signs (P4) hold under the composite reward.
  - A failing gate means R_exchange is revised (features, phase split, cap, fit data) and re-audited. It is never dropped.
- No habit, reward_terms, spell_value or shaping keys (the validator refuses them; the code stays for old A/Bs). The
  leak, idle-on-threat and over-paying are priced through R_exchange (leak = our elixir loss; ignored threats = tower
  HP lost), not through their own terms.
**P3, counterfactual fork credit** (extends `pipeline/cf_credit.py`).
- At a trigger, fork the SIM, play the alternative, and credit the difference in the SAME composite return (R_win +
  R_exchange). The value is read 30 s later (the exchange accrued in the window plus the critic), or from the real
  result once <= 60 s of overtime remain.
- It compares two actions from one state on one objective, so it cannot pay a card for being played (the rejected
  "generic multiplier" failure); a Rocket on a lone tank is credited only if it beats the alternatives on that objective.
- Triggers, each with at most 3 alternatives:

  | trigger | alternatives |
  |---|---|
  | Rocket available | clump, weakest princess, base |
  | Rocket played | wait, second card |
  | building-targeting win condition on our half | Rocket it, Knight in front, Skeletons pull, wait |
  | **Mortar / X-Bow in reach of our tower** | troop in front (pros: ~7 tiles in front within ~2 s), Rocket it |
  | after a failed X-Bow | wait, defensive X-Bow, chip Rocket |
  | our reach X-Bow | wait, defensive, other lane |
  | idle at full elixir | play now |
  | Rocket + Tornado | combo vs lone Rocket |
  | Tornado redirect | toward our king vs elsewhere |
  | Log | Log vs hold while a bait card is visible |

  The combo trigger computes the owner's "V_combo - V_lone" directly; the Tornado's elixir is already priced in by the
  win objective.
- Noise and bias controls:
  - K = 2 paired continuations with common random numbers, and the real trajectory reused as base sample 1;
  - noisy alternatives shrunk toward zero;
  - 10% of forks run to the end of the match, and the critic's slope against them must be in [0.7, 1.3];
  - a trigger with signal-to-noise < 0.5 gets more paired continuations (K), a horizon matched to its payoff, or a
    control-variate baseline, until it reaches 0.5. The trigger stays;
  - fork compute <= 1x rollouts.
**P4, audit the SIM's incentives before training (L1b).**
- Expected signs:
  - Rocket on Ram Rider / Balloon / Royal Hogs with Tesla out of cycle: positive;
  - Rocket on a lone Golem: negative;
  - troop in front of a locked Mortar: positive;
  - chip Rocket in a close overtime: positive;
  - X-Bow after failures vs a denier: negative.
- Also: the faithful SIM must reproduce the pro chip-Rocket relationship that today's SIM inverts.
- A wrong sign starts the iterate loop on that trigger, which stays in. Candidate causes, each checked by a measurement:
  - a fidelity bug: Rocket / Tornado / X-Bow / Mortar mechanics, the tiebreak rule;
  - an opponent that does not punish the way humans do;
  - a horizon too short for the payoff;
  - critic bias;
  - a badly specified alternative.
  The cause is fixed and the audit re-run until the sign matches pro / live evidence.
- **Rocket behaviour is a requirement, not an option.** Required: cycling on princesses, defensive Rockets on building
  win conditions, Rocket + Tornado. If the SIM says chip Rockets lose, that is a defect to find and fix through the causes
  above; the requirement stays. Rocket >= 1.0 / match is also a deploy check.
**P5, drift control without a leash** (owner: a leash caps how far the model can go past humans). No KL to B0, pros or
any earlier checkpoint. Drift is handled in five ways:
1. **Remove its measured causes.**
   - The decoder mismatch: (a) the 10-26 opening wait, and the long run's u175 (+7-9 under the training decoder but the
     worst checkpoint under the deploy decoder). Fixed by P1.
   - SIM exploits. Fixed by pillars 1-2 and the X3 / L1b audits.
   - A moving opponent pool. Fixed by a frozen, sha-registered pool per run with no learner snapshots.
   The leash existed mostly to hold these back.
2. **Cut the noise that makes habits random-walk.** Habits drift in rarely-visited states where the gradient is mostly
   noise (signal-to-noise ~0.2).
   - Double the batch to 512 matches per update with distributed rollouts.
   - Policy-gradient rows whose |advantage| is inside their own noise band (per-state-cluster SE) get zero weight, so
     noise cannot move the policy (b).
3. **Give drift-prone states real reward signal.** 20-25% of matches start from scenario states: opening, full elixir,
   under attack, Mortar / X-Bow locked, overtime, 1-0 up, 1-1, after failed X-Bows. These states then get gradient from
   outcomes instead of drifting by neglect.
4. **Step size, not destination.** PPO clip 0.2, plus an early stop of the epoch loop when KL to the PREVIOUS update's
   policy exceeds 0.02. This limits how fast the model moves per update, never how far it can go in total.
5. **Detect, select, branch.**
   - Drift check every 25 updates on a selection block. Gating metrics: win, first play, seconds at full elixir, idle on
     threat, trade, plus the habit metrics.
   - A flagged checkpoint is not trained on further. The run branches from the last clean checkpoint with a fresh seed
     (population-style), and the flag goes in the ledger with a diagnosis.
   - 2 seeds per arm; select on one block, confirm on sealed blocks.
   - No fixed update cap: a run continues while the drift checks stay clean and the gate keeps improving.

The OPPONENT pillar keeps its fixed pull toward human imitation. That is correct there, because the opponents' job is to
be human; it never applies to our model.
**Memory must have something to learn first.**
- Adaptation-value audit in the new opponent pool: does an X-Bow failure predict the next failure as it does live?
- Persona fork test: does the sign of "X-Bow again vs wait" change between opponents?
- If not, the opponent pool is fixed (pillar 2: per-player spread B3, the siege conditional facts, the style latent z)
  until it does. Memory stays in every successor.
- Gate: real memory minus memory shuffled from another match vs the same deck, CI low > 0, for an "ADAPTIVE" promotion.
- Live metric: X-Bow persistence ratio (P(X-Bow within 30 s | last failed) / P(same | last locked)) <= 1.0. Today
  CLXIII 1.34, CLXIV 3.7.
**P6, macro strategies: plans that pay off over many decisions.** Examples:
- the sneaky lock: Tornado pulls a far defender out of X-Bow range, then the X-Bow locks the princess;
- repeated Rocket cycles on a princess in 2x / overtime once X-Bows stop connecting.
Why they don't emerge today (a):
- per-step sampling almost never produces the coordinated sequence (the exploration problem);
- the payoff lands after GAE's ~20-decision reach and after a 30 s fork horizon (credit; Rocket cycling pays at the
  tiebreak);
- the SIM's opponents never punish the failed X-Bow lineage, so there is no reason to switch (pattern 13).
Five mechanisms:
1. **Macro library mined from human data, not hand-written.** Mine the 252k HF replays + pro corpus (icebow8) + live logs.
   - A candidate is a multi-play sequence over a window of up to 20 s: (card, place relative to enemy units / towers,
     gap).
   - A newly mined candidate is added if, in matched states (same phase, HP margin, elixir, deck archetypes), matches
     that use it win more than matches that don't, with a CI.
   - Each macro is stored as a plan with a start condition and a scripted prefix.
   - The owner-named and doctrine macros below are ALWAYS in the library; the data only refines their start conditions
     and prefixes. If one shows no win lift, diagnose: well-executed vs failed attempts, start condition too broad, or
     matching too coarse. Then refine it until its well-executed form is measured.
     1. sneaky lock (Tornado pull + X-Bow lock);
     2. Rocket cycling in 2x / OT after failed X-Bows (pros: a chip Rocket within 30 s of a failed bridge X-Bow 18.4%);
     3. Rocket + Tornado on a clump or into a princess;
     4. Tornado redirect into our king while both princesses stand (king activation);
     5. defensive X-Bow in a hard matchup, then the counter-lock;
     6. opposite-lane punish when the opponent commits elixir (Miyagi: price their back card);
     7. counter-push behind surviving defenders;
     8. counter-in-cycle timing: X-Bow when their known answer is out of cycle (needs memory);
     9. focusing the weakest princess;
     10. lead protection (1-0 up: defend out) and 1-1: take the other princess;
     11. situational banking before 2x or before their big push;
     12. pulls / kiting to split pushes;
     13. bait discipline: hold the Log for the Barrel;
     14. siege answer: troop in front within ~2 s, Rocket when locked;
     15. Hero IW press timing.
   - The miner reports any others it finds, with their win lift.
2. **Macros enter training only as fork alternatives, never as rules or rewards.**
   - When a macro's start condition holds, a fork plays its scripted prefix (for example the Tornado, then the X-Bow at
     the lock tile), and the learned policy continues from there.
   - The composite-return difference vs the base branch becomes the advantage on EVERY action of the prefix (alternative
     rows), so the policy learns the whole sequence.
   - Deployment runs only the learned policy. That satisfies "never reward the sneaky lock or the Tornado directly": a
     macro is credited only when the SIM shows it wins more from that state.
   - If the SIM credits an owner-named macro negative where humans win with it, that is a P4 defect: iterate (fidelity
     of the Tornado pull / X-Bow targeting, opponent reaction, prefix execution, horizon) until it matches.
3. **Horizon matched to the payoff.** Each macro's fork horizon is the window over which its human win lift is measured.
   For example, the sneaky lock pays inside ~20 s of lock damage; Rocket cycling in 2x / OT runs to the match end (with
   K = 2 paired continuations; the cost is budgeted per trigger). The 10% terminal-run bias audit covers each one.
4. **The phase-split R_exchange carries the long-term value of chip damage.** In real games, princess HP in overtime
   decides the tiebreak, so the fitted overtime weight on tower HP is large. Every chip Rocket then gets immediate credit
   in proportion to its real-game value, instead of waiting minutes for the result. X2 must show "Rocket every chance"
   does not out-score CLXIII.
5. **Memory carries the plan state.** Memory v2 already holds "X-Bow failed N times", their counter's cycle position and
   cards seen. The "after a failed X-Bow" and "counter-in-cycle" triggers compare macros whose value depends on that
   state, so the gradient has to pass through memory.
Not used: a separate plan / intent head. The C1 posture head was measured null (-0.38, "pressure" chosen 0%).
**Measured on every candidate (L3 / L4):** for each library macro, its rate and success vs the pro / live rate in the
same states (e.g. sneaky-lock attempts and lock share; Rocket cycles per minute in 2x / OT after >= 2 failed X-Bows; king
activation share; weakest-princess damage share). L4 adds a scenario per macro (start condition met, 200 runs): its use
there and the win vs the parent.

**Start point B0 = CLXIII + the S3-aux memory encoder (sha 3d75a25d), coupling zero** (identical to CLXIII at u0, CPU
identity test). Training learner: critic warm-up 5, GAE gamma_tick 0.99994, lambda 0.95, lr 1e-5, clip 0.2.
**Rounds, one change each, 2 seeds, ~15 h wall on 4 pods per round. All rounds use the unified decode and the pillar-2
opponents:**
- R1: R_win vs R_win + R_exchange. This is the control that shows whether the dense term helps. If it doesn't,
  R_exchange is diagnosed and revised and R1 is re-run; it is not dropped.
- R2: R1's winner + R_fork.
- R3: unfreeze the memory encoder.
Each winner is the next run's start.

**Evaluation ladder.** A candidate that fails a rung does not advance. The failure is diagnosed, and the responsible
component is fixed in the next round (no-discard rule).
- L0: identity.
- L0b: R_exchange gates X1-X4.
- L1: fork pilot.
- L1b: incentive audit.
- L2: drift.
- L3: SIM gate vs parent on 3,840 confirm pairs, all of:
  - pooled CI low > 0;
  - behaviour bars;
  - habit metrics not worse;
  - Rockets >= 1.0 per match;
  - **Mortar-deck win >= 45%**;
  - X-Bow persistence <= 1.0;
  - macro rates / success not below the parent and moving toward the pro rates;
  - memory ablation.
- L4: scenario forks rebuilt from ~800 live replays (Mortar locked, win condition with Tesla out of cycle, lone Golem,
  close overtime, 2 failed X-Bows vs a denier, 1-0 up, 1-1), 200 runs each.
- L5: predicted live interval.
- L6: live, which the owner starts. A 60-match block with alarms, then 300 matches.

## How the pillars share one live data stream (recommended)
- While pillars 1-2 are built, the owner runs ONE fixed live config: **CLXIII NOLEAK with today's LIVE_OPTIONS, through
  the unified `decide()`**. The SIM mirrors every option, so this is a pure code change, and L0 shows it is a no-op on
  replayed rows.
- Our battle log is polled after each match.
- That one stream feeds all three pillars:
  - engine: seeds -> SME, the certificate supply;
  - opponents: the live fine-tune rows, calibration block and sealed block;
  - training: the L5 calibration of SIM-to-live offsets.
- Changing the live Mark mid-stream would split every block, so successors go live only after the sealed block closes
  or with the owner's explicit OK.

## Merged timeline (calendar days after approval)

| days | engine | opponents | training |
|---|---|---|---|
| 0 | step 0 housekeeping | | |
| 0-3 | fin16 build, crforge on a pod, G0, G1 | scorecard on old baselines, THRESHOLDS.json, timing head / deck encoder code + tests | unified `decide()` + identity tests, SIM config from LIVE_OPTIONS, lethal_quiet + barrel_lane into the SIM, live_siege.py fix (laptop only) |
| 3- | nightly SME on the live stream | live command extractor | owner runs the fixed live config |
| 2-8 | pilot -> **D1 day 8** | | |
| 8-22 | integration -> **D2 ~day 22** | re-drive, rows, pretrain, live fine-tune (days 9-18) | cf_credit review + tests (laptop); R_exchange fit + X1 and the macro miner on the re-driven traces (days 12-18) |
| 18-32 | fix loop | SIM wiring, B/C, fix rounds, calibration -> **usable ~day 32-40** | after D2: X2-X4 farm / SIM audits, fork pilot, incentive audit, adaptation audit on crforge (audits only) |
| 32-48 | certificate attempt ~days 30-45 | sealed block -> D verdict ~day 43-55 | R1 -> R2 -> R3 -> first candidate at L6 ~day 40-48 |

**First successor is ~6-7 weeks out.** No successor training before both D2 and "opponents usable". That is the price of
the requirement: every earlier era trained on a SIM that over-predicted live by 8-24 pp. Top 1,000 is a weeks-to-months
goal after that; I won't put a date on it.

## Step 0 on approval (first hour)
0. Save this plan as `scratchpad/gauntlet/L74/plan1026/PLAN.md`, with the four design reports beside it (engine,
   opponents, reward, history), for the owner's other account. Plan mode blocked writing it before approval. Commit + push.
1. On 32657: copy brT10_s107's train log, drift dir and latest checkpoint to `pod_backup_weekend/night1025/`, then stop
   it by process group (bracket kill pattern, verify with pgrep). Copy the three idle pods' chain / drift outputs too.
   **No pod is stopped or released without the owner's answer to decision 6.**
2. LEDGER.md + succ48/EXPERIMENTS.md: the four arms' end state (3 run failures with empty drift reports, s107 halted),
   the stopped fork-credit agent and its uncommitted edits, the 10-26 Mortar / overtime measurements (measure1026 report
   draft -> `L74/memory/measure1026/REPORT.md`), CLXIV's live record, this plan. HANDOFF via `codex1018/stage_handoff.sh`.
   Commit + push with explicit paths.
3. Memory notes for the owner's 10-26 plan rulings: the no-discard rule, no KL leash on our model, a non-win-only
   reward, macros, barrel_lane kept. Update `iterate-dont-abandon.md` rather than duplicating it.

## Owner decisions (RESOLVED 10-26 -- see STATUS.md: 4 polling running, 5 device checks done, 7 TV harvesting approved)
1. The two "99.9%" definitions above (engine SME lower bound; opponent coverage H). Default: as written.
2. Live during the build: revert CKPT_OVERRIDE to CLXIII and run it as the fixed data config; you start and stop it.
   Default: yes. CLXIV stays registered.
3. barrel_lane: DECIDED (owner): kept live and moved into `decide()`, so successors train and deploy with it.
4. Poll our own battle log through the official API after each live match (read-only; for seeds and opponent tags).
   Default: yes.
5. Two read-only device checks with you present (~15 min each): the same match recorded live and from the replay viewer;
   and whether the client caches the official replay file (if yes, it gives exact inputs with the seed for every match).
   Default: yes, at a time you pick.
6. Pods: days 0-8 need 1-2 pods (CPU), days 8+ need 3-4. Default: keep 32657 + 33920, release 33458 + 33411 after their
   records are copied. Releasing risks none being rentable later (10-22).
7. TV Royale harvesting (the supply for a ~day-45 certificate): asked at D1, only if crforge passes.

## Verification
- **Engine:** SME and crown-sequence scorers get a planted-bug test (a 1-HP perturbation must fail the match).
  Thresholds and the held-out date split are fixed before the pilot. D1 / D2 tables are reported in full, including failures.
- **Opponents:** the scorecard must reproduce known values first (E4 RMS d 0.93, I u40 0.78, human floor 0.05) before
  any new model is scored. THRESHOLDS.json sha is logged before training. Sealed-block predictions are hashed before the
  block is played. The discriminator is retrained fresh each time.
- **Training:** `test_decide_identity.py`. Existing absent-key tests (config hash unchanged with no new keys). pyflakes and
  a real `rl_royale --smoke` after every trainer edit. cf_credit tests (fork determinism, baseline reproduces the real
  continuation, alternative log-probs within 1e-6). Every ladder rung reported with its CI.

## Critical files
- Engine: `pipeline/royale_env.py` (one seam), `pipeline/royale_runtime.py`, new `pipeline/crforge_core.py`,
  `L74/parity/metrics/replay_metrics.py`, `L74/parity/fights.py`, `L74/parity/fin16/fin16_chain.sh`, `L74/crapi/crapi.py`.
- Opponents: `pipeline/model_gen.py`, `pipeline/dataset_gen.py`, `pipeline/train_gen.py`, `tools/hf_to_crawl.py`,
  new `pipeline/human_traces.py`, `L74/human/opp_behaviour.py`, `L74/opp_model/w18/o4_gate.py`.
- Training: `pipeline/decision_options.py`, `pipeline/e1_eval.py`, `pipeline/live_gen_v2.py`, `pipeline/cf_credit.py`,
  `pipeline/rl_royale.py`, `L74/livecal/livecal.py`, `L70/live/LIVE_OPTIONS`.
- Reward: `pipeline/reward_terms.py` (new `exchange` term: zero-sum, fitted beta file with sha), new
  `L75/ladder/exchange_fit.py` + `farm_audit.py`; macros: new `L75/ladder/macro_mine.py` (library JSON with sha),
  `pipeline/cf_credit.py` (macro prefixes as alternatives, per-macro horizon); drift control: `pipeline/rl_royale.py`
  (batch 512, advantage noise gate, per-update KL early stop, scenario-start table, branch-on-flag in the chain script);
  remove the `kl_ref_*` anchor use from successor recipes.
- Full design reports (engine / opponents / reward / history) are kept in the session scratchpad and copied to
  `L74/plan1026/` in step 0.
