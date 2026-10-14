# Reward architecture for icebow RL — DRAFT for owner review (2026-10-14)

Owner request (10-14): a (possibly) complex reward-shaping architecture built on everything measured so far, the owner's
strategy material (MiyagiCR transcripts, doctrine notes) and the owner's complaints about the bot's play. Every term
says **why** it exists (linked to evidence IDs below) and **how it is made to stick** (persist in the trained model
after the shaping is gone). Nothing here has been run.

---

## 0. Ground rules this design is built on

Two facts decide what reward shaping can and cannot do here. Both are measured or proven, not opinions.

1. **A "potential" term cannot change which play is best; it only makes the best play faster to find.** If a shaping
   term has the form `F = γ·Φ(next state) − Φ(current state)` (Φ = a score of the board, "potential"), the optimal policy
   is unchanged (Ng, Harada & Russell 1999). With a critic, it is the same as giving the critic a head start (Wiewiora
   2003). The old tower-HP shaping (R2, which DID run with per-decision credit and a critic) measured +0 (O14): a flat
   tower potential gave no learning-speed benefit — the owner's point that tower damage alone is not enough. Free-standing terms ("+x for doing Y") DO change what is optimal — and every collapse
   in this project's history came from one (§6 table).
2. **Our current learner throws shaping away.** r1 trained with `advantage: match_loo`: every decision in a match gets
   the same credit (win/loss minus a group baseline). Potential terms summed over a match telescope to a constant, so
   under match_loo **any potential shaping changes nothing at all** (L69/reward_plan.md §1, proven there). Per-decision
   credit (a critic + GAE) is therefore a prerequisite, not an option.

So the architecture has three kinds of pieces:
- **Foundations** (F): changes to the learner/environment without which no shaping can work.
- **Potential terms** (A, B): safe by construction; they teach *faster*, they cannot teach something that loses.
- **Strategy layer** (C): the part that makes long-term play (how aggressive to be by matchup and phase) learnable.
- **Constraints, not rewards** (D): owner rules that must hold ~100% (a reward only ever shifts odds).

---

## 1. Evidence base (IDs used below)

**Measured (O)** — all numbers from HANDOFF / the files named; live = r1 unless stated.

| ID | Observation |
|---|---|
| O1 | 60 RL updates did not improve the plain policy (+1.35 pp [-2.50, +5.10]); the deployed player fell -5.21 because add-ons lost fit (rltest/FINDING.md) |
| O2 | r1 used match_loo advantage: potential shaping telescopes to nothing under it (reward_plan.md §1) |
| O3 | RL samples the gate at T .5, which loses 25 pp vs greedy (16.7% vs 42.1%); RL learns from games the deployed bot never plays (gap/FINDING.md) |
| O4 | Approach spending: elixir spent between the opponent committing a push and it arriving — pros 0.57, SIM r1 1.49, live r1 2.43; live r1 meets 66% of pushes with < 4 elixir (pros 24%) (econ2) |
| O5 | Low-elixir penalty (tower or >= 1000 HP lost within 15 s): live +26.9 pp; SIM +17.1 (E4 @ .1) to +23.0 (E4 @ .03) (calib_20261014.txt, level-scaled) |
| O6 | Cheap plays at < 5 elixir 2-3x pros; above-median cheap-play matches win 44% vs 62% (loss review rank 2) |
| O7 | Air in a push: +10.3 pp lost episodes; Golem 38% vs 54% WR; Lava, Balloon weak (loss review) |
| O8 | Locked X-Bow placed into a full opponent elixir bar: -405 HP dealt in 20 s, dud rate +8.6 pp (rank 5) |
| O9 | 15% of losses end with the enemy tower within one Rocket; Rocket in hand 64% of the last 20 s but affordable 7%; Rocket 0.29/match vs pros ~2 |
| O10 | Log/Tornado on nothing (>= 2/match): WR 46% vs 54%; Tornado as the first answer: +14 pp lost episodes |
| O11 | Win rate by crowns conceded: 0 -> 90%, 1 -> 15%; the first conceded crown is worth 0.75 wins; first crown taken 0.62 |
| O12 | 47% of matches reach overtime; OT win rate 55% |
| O13 | Hero IW press: never pressing +3.33 pp [+0.62, +6.15] in SIM for r1 (A/B3 twin; live A/B3 running) |
| O14 | Past shaping: R2 tower+crown potential -0.7 [-4.0, +2.7]; R4c value-head potential ~= baseline; a free-standing penalty emptied the bar (91% of steps at 0-2 elixir) |
| O15 | Rules + grafted heads worth +8.75 pp on ADAPT, +2.2 on r1; refitting the heads did not help (REFIT_RESULT.md) |
| O16 | SIM opponents already match live push rate and size; opponent choice moves r1's SIM win rate 40.6-54.6%; SIM is level 11, live level 15 |
| O17 | Option 1 (econ2/PRO_EAGERNESS.md): the pure imitation model's gate is calibrated on pro states (approach +1.3 [-0.3, 3.0]); RL made it progressively more eager ON PRO STATES (under attack, 1x, 0-4 elixir: imitation +2.2 -> ADAPT +7.2 -> r1 +11.8 pp over pros); and on the bot's OWN states ADAPT plays more again in the approach window (+5.7 [3.0, 8.4] raw, +3.3 reweighted) = ~2/3 of the approach excess. The live rule `--tau-threatened 0.2` adds under-attack plays (24% of them are below the normal threshold) |

**Owner strategy (S)** — MiyagiCR transcripts (`Downloads/transcripts`), doctrine memories.

| ID | Strategy |
|---|---|
| S1 | 1x: cycling 1-2 elixir cards is free only while the opponent places nothing; once they place, stop cycling and play something meaningful |
| S2 | Price the cheapest defence of their back card: cheap -> pressure the opposite lane; otherwise defend safely |
| S3 | Elixir alive on the board counts |
| S4 | Track their key counters; once (e.g.) Zap is out of cycle, break through |
| S5 | When ahead: protect position, tank with the tower not troops, no snowball push, keep evos for defence, zero risk; tower HP only matters if the tower falls |
| S6 | Card order: building first, protect it with the cheapest unit, cycle quickly back to the high-DPS card |
| S7 | Pathing: pull troops to the side (longest path to tower and building); second building high to drag the tank |
| S8 | Spacing: stagger buildings, split supports against spells, punish the opponent's clumping |
| S9 | Cut DPS: kill the supports before the tank |
| S10 | Win condition by matchup: if it is hard-countered, play passive and spell-cycle instead of feeding negative trades |
| S11 | Far behind vs a spell-cycler: mirroring spells cannot win; take a calculated risk |
| S12 | Against a pump: pressure rather than spell it |
| S13 | Defence chain: recognise -> classify -> counter (Tesla for win conditions, Ice Wizard for swarms), fallback mitigation is legitimate; synergies Rocket+Tornado, IW+Tornado, Tornado pull to the king for activation, Tornado drag back into a building's aggro |
| S14 | Fundamentals: triage (ignore what the tower kills alone), outrange beats health, minimise damage rather than prevent it, cheapest card that works, read the push as a whole |
| S15 | 3.5 cycle deck: banking to ~10 for X-Bow + Tesla is correct; no anti-hoarding pressure |
| S16 | Ahead 1-0: defend out the match; 1-1: take the OTHER princess; never the king tower |
| S17 | Overtime: always Rocket a princess that one Rocket finishes |
| S18 | Train hard on unfavourable matchups: hyperbait, PEKKA bridge spam, Lava, RG (+Monk), Golem |
| S20 | (owner 10-14) Rocket+Tornado: a Tornado cannot drag GROUND troops over the river, so ground troops on opposite banks are separate groups; place the Tornado so the target ground troops really clump (air units are not blocked) |
| S19 | (owner 10-14) Rocket-cycle an enemy princess even when it is not finishable, to gain or keep a damage lead: it pays off through the end-of-overtime TIEBREAKER (weakest standing tower loses). A long-horizon strategy, hard to instil |

**Owner complaints (C)** — memories overnight-2026-10-08, tower-targeting-doctrine, HANDOFF 10-02.

| ID | Complaint |
|---|---|
| C1 | 9 elixir spent on the other lane during a Mega Knight bridge push |
| C2 | 8+ elixir to defend a 3-elixir push |
| C3 | A whole Tesla on 2-elixir Bats |
| C4 | Knight defending an opposite-lane X-Bow while a Lumberjack walks to a 200-HP tower |
| C5 | Rocket rarely used, never finishes a low tower |
| C6 | Damage spread over both princess towers |
| C7 | X-Bow in a dead lane; few defensive X-Bows; at 1-1 should chip the other princess |
| C8 | Forward play in overtime |
| C9 | Hero Ice Wizard ability trigger-happy |
| C10 | "Doing nothing correctly": hoarding then dumping; spells ineffective |
| C11 | Gate freezes at full elixir |

---

## 2. Foundations (F) — required before any shaping

| ID | Change | Why | How it sticks / what it protects |
|---|---|---|---|
| F1 | **Per-decision credit**: `advantage: gae` with a critic warm-up (the R1 design, already built: `critic_warmup_updates`, residual critic `shaping_critic_scale`) | O2: without it every potential term below is a no-op; O1: one credit per match is also a plausible reason RL learned nothing in 60 updates (a 4-minute match gives ~380 decisions one shared signal) | Its own arm vs match_loo before any term is added (one change). The critic is kept: every later term is absorbed into it (Wiewiora), so the value function itself learns the concepts |
| F2 | **Context-aware critic**: the value head sees matchup archetype (from the opponent's public cards so far), phase (1x/2x/OT), crown state, elixir trade (public counter) | The same board is good or bad depending on matchup and score (S5, S10, S11, S16); a critic that cannot see context gives the wrong credit to the right move | The critic's inputs are the policy's inputs (shared trunk) plus explicit context tokens; checked by the critic's outcome AUC by matchup and phase before training |
| F3 | **Calibrated, weighted opponents**: league mix with E4 @ .03 (closest low-elixir penalty, +23.0 vs live +26.9) and gen_v1 @ .3 (closest overall), archetype-weighted per S18 (already 60% unfavourable) | O5, O16: the environment itself must punish what live punishes, or no reward can make a habit worth keeping | This is what makes behaviour stick **after** shaping is removed: if the opponents punish overspending, not overspending stays optimal with the plain win/loss reward |
| F4 | **Exploration that looks like deployment**: learner gate at low temperature (T_gate, built), exploration on card/cell | O3: the learner currently trains on games 25 pp worse than it plays; credit learned there does not transfer | Its own arm (T_gate 0.1 was tested on match_loo: no gain; re-test under F1, where it can matter) |
| F5 | **Level-normalised HP**: every HP term as a fraction of max HP | O16: the SIM is level 11, live is level 15 (x1.45); absolute HP thresholds mismeasure | Unit test: same Φ for the same fractional state at both levels |
| F6 | **Anchor the leash to the imitation model, not to each run's own start** (at least for the gate head): KL to the pro-trained gate, so RL can only move it where winning pays | O17: the eagerness grows down the lineage (imitation -> ADAPT -> r1) because each run's KL anchor is its own, already-drifted init (il-pivot memory: verified in code) | Its own arm. It removes the RL-drift part of O17 (larger for r1); it cannot touch the own-state part, which needs on-policy terms (A2, F3) |

---

## 3. Potential terms (A) — state scores Φ(s); safe by construction

All use only public information (own state, visible enemy units, the public opponent-elixir counter — never hidden
opponent state). Shaping per step `F = γ·Φ(s') − Φ(s)`, Φ = 0 at the end of the match. The total of all Φ terms is
budgeted at |Φ| <= 0.5 x the terminal reward (lesson 7 in §6).

### A1. Tower potential, weighted by score state ("what a tower is worth right now")
- **Form.** `Φ_tower = Σ_own w_own(c, t)·h(hp_frac_t) − Σ_enemy w_foe(c, t)·hp_frac_t`, c = crown state.
  `h` is concave near death: a tower's value is mostly whether it **survives**, not its exact HP.
  Weights by crown state: ahead 1-0 -> own weight up, enemy weight down ("defend out"); 1-1 -> the remaining enemy
  princess carries all the enemy weight; **king tower enemy weight = 0 in every state**; behind -> enemy weight up.
- **Why.** O11 (a conceded crown costs 0.75 wins); S5 (tower HP only matters if it falls; tank with the tower);
  S16 (1-0 defend out, 1-1 the other princess, never king); C6 (damage spread over both princesses), C7, C8.
  R2's flat tower potential was +0 even with per-decision credit (O14): it valued all HP equally and ignored the score
  state, so it told the learner nothing the win/loss signal did not. A1 differs in exactly those two respects.
- **How it sticks.** Potential form → it cannot make the bot worse at winning; it speeds up learning the score-dependent
  priorities the win/loss reward already implies. The critic (F1/F2) absorbs it, so after the weight is annealed to 0
  the value function still prefers saving a near-dead tower. The "never king" part is ALSO a hard rule (D1), because a
  potential only shifts odds.
- **A1b — tiebreak margin (S19).** The SIM plays out the real tiebreaker (`RoyaleSim state.rs::overtime_tiebreak`: level
  on crowns at the end of overtime -> the side whose weakest standing tower has less HP loses). Add
  `Φ_tb = w_tb(t)·(min own standing-tower HP frac − min enemy standing-tower HP frac)`, with `w_tb(t)` ~0 in 1x and
  rising through 2x and overtime, so chip damage concentrated on ONE enemy princess earns credit long before the match
  ends. Potential form, so it only speeds learning what the tiebreaker already rewards; the reward itself is the real
  rule. Acceptance: Rocket-on-tower chip rate vs pros, damage concentration on the weakest enemy princess, tiebreak wins.
- **Hack risk / guard.** Concave `h` could teach "let healthy towers soak damage forever" — that is S5's own advice
  (tank with the tower) and is bounded by the terminal reward. Alarm: share of matches losing a tower in 1x vs init.

### A2. Solvency potential (the approach-economy term — the biggest measured problem)
- **Form.** `Φ_solv = −w·max(0, k·T_incoming − (E_own + D_board))`. `T_incoming` = elixir value of enemy units that
  have committed a push (econ2's commit definition: seen, heading to my half). `E_own` = own elixir. `D_board` = elixir
  value of own units or buildings on the board that can engage that push. Zero whenever no push is committed.
- **Why.** O4 (r1 spends 1.5 SIM / 2.4 live elixir on the approach vs pros 0.6; 66% of pushes met with < 4 elixir),
  O5 (meeting a push short costs +17 to +27 pp), O6; S1 (stop cycling once they place), S2, S3 (elixir alive on the
  board counts — so defending early with a real defender is NOT penalised, only spending on things that will not
  defend), S14.3/S14.4; C1 (9 elixir on the other lane during a MK push), C2.
- **How it sticks.** (1) Potential form: it rewards *keeping enough to defend* only through credit timing, so if banking
  for the push really wins (O5 says it does) the habit is optimal and stays. (2) F3's opponents punish the habit
  directly, so it stays after annealing. (3) Zero outside committed pushes, so it never pushes toward hoarding in quiet
  play (S15: banking is fine but not forced). (4) Acceptance uses econ2's live definitions (O4) — the target is
  "approach spending toward 0.6, pushes met < 4 elixir toward pros' 24%".
- **Hack risk / guard.** "Never spend" would raise E_own — but the terminal reward and A1 punish undefended pushes,
  and the term is capped. Scripted audit (§5): never-play and spend-immediately must score below the IL policy.
  Alarm: plays/match < 50% of init; elixir-at-play outside [0.6x, 1.5x] init.

### A3. Elixir-trade potential ("1 elixir burned is 1 elixir gone once they place")
- **Form.** `Φ_trade = w·clip((E_own + V_own_board) − (Ê_opp + V_opp_board), ±cap)`, with Ê_opp the public counter.
  A spell is priced by what it removes (the enemy board value drops), so a Log that kills 3 elixir of units is +1, a Log
  on nothing is −2 — the mispricing that sank the friend's elixir term (lesson 7) does not arise.
- **Why.** S1 (cheap cycling is free only while they place nothing — in trade terms, a wasted elixir is lost the moment
  they commit), S3, S14.4 (cheapest card that works); C2 (8 elixir for 3), C3 (Tesla on Bats), C10; O6, O10 (Log/Tornado
  on nothing, WR 46% vs 54%).
- **How it sticks.** Potential form; the critic learns elixir advantage as part of value. Kept small (cap) and only
  added after A1+A2 are measured, because an elixir term is exactly what went wrong before (O14, lesson 7).
- **Hack risk / guard.** Board value of buildings and spells must be priced fairly (both unit tests and the §6 alarm
  "spell and building share of plays >= 50% of init"). Opponent counter error (+0.3 over-read, measured) is inside the cap.

### A4. DPS-cut potential ("kill the supports first")
- **Form.** `Φ_dps = −w·Σ DPS(enemy units on my half or targeting my structures) / norm`, DPS from the card catalog,
  level-normalised (F5).
- **Why.** S9 (cut DPS: supports before the tank), S14.5 (read the push as a whole); O7 (air in a push +10.3 pp lost
  episodes — air supports are high-DPS and out of ground reach); Golem/Lava/Balloon matchups (S18).
- **How it sticks.** Potential form: killing a 4-elixir high-DPS support raises Φ more than chipping the tank, which is
  exactly when the win/loss signal would eventually agree (fewer tower hits). Acceptance: time-to-kill of supports vs
  tank in defended pushes, moved toward pros (measurable from replays).
- **Hack risk.** Low (can only be raised by removing enemy DPS). Guard: per-card play rates (Tornado/Log) do not collapse.

### A5. Path and aggro potential ("make them walk the longest way")
- **Form.** `Φ_path = w·Σ_enemy ground units on my half (remaining path length to their current target)/norm`, plus a
  term when a building-targeting win condition is locked on my BUILDING rather than my tower.
- **Why.** S7 (pull to the side, longest path; second building high to drag the tank), S13 (Tornado drag back into
  the building's aggro), S6 (building first); C4 (troops wandering to a 200-HP tower).
- **How it sticks.** Potential form; acceptance = enemy unit path length and building-lock share in defended pushes vs
  pros. If it does not move, the next step is a placement-cell advice term (B-layer), not a bigger weight.
- **Hack risk.** "Keep enemies alive and walking" could raise Φ — capped, and A4/A1 lose more than A5 gains if units are
  left alive; audit includes a "kite forever" scripted policy.

### A6. Splash-exposure potential ("spacing")
- **Form.** `Φ_space = −w·max over the opponent's SHOWN spells (in likely cycle, public) of own value inside one spell
  circle` + `w'·(enemy value clumped inside a Rocket/Log circle while we hold that spell)`.
- **Why.** S8 (stagger buildings, split supports, punish clumping), S13 (Rocket + Tornado: pull a clump into a Rocket),
  O9 (Rocket underused; only 7% of the time affordable when it mattered — partly an economy issue, A2).
- **How it sticks.** Potential form; acceptance = mean own value per enemy spell hit (down), Rocket value per cast (up).
- **Hack risk.** Medium (it could teach never grouping a defence that needs grouping) — lowest weight, last to enter.

---

## 4. Look-ahead advice (B) — action-dependent potentials for rare, specific plays

Some owner strategies are about a *specific card in a specific moment* (Rocket finish, X-Bow commit timing). A state
potential cannot single those out; a **look-ahead advice** term `F = γ·Φ(s', a') − Φ(s, a)` can, and it is still
policy-invariant when the critic is corrected for it (Wiewiora, Cottrell & Elkan 2003). Each Φ(s, a) below is
**estimated from data where possible** (pro games / our own SIM outcomes), not hand-set.

| ID | Advice Φ(s, a) | Why | How it sticks |
|---|---|---|---|
| B1 | Cycle discipline: negative for a ≤ 2-elixir play that is neither an answer nor pressure within N s of an opponent placement | S1, S2; O6 (cheap plays at < 5 elixir 2-3x pros, WR 44% vs 62%); C10 | Advice only biases exploration; the habit stays if F3's opponents punish it (they do: O5). Acceptance: cheap taps at < 5 elixir per minute toward pros |
| B2 | Counter class: positive when the card's class matches the threat class (Hunter matrix: Tesla vs win condition, IW vs swarm, Skeletons as distraction); negative for answering an ignorable threat (triage table) | S13, S14.1, S14.4; C3 (Tesla on Bats) | Φ values from the Hunter/pro response matrix (measured, 189 plays) — learned evidence, not opinion. Acceptance: response-class agreement with pros by threat class |
| B3 | X-Bow commit value: Φ(s, X-Bow placement) = estimated lock value given the opponent's public elixir, their counters seen and not yet cycled back, the lane's tower state | O8 (-405 HP when committed into a full bar); S4 (counters out of cycle -> break through), S10 (passive when countered), S2 (pressure the opposite lane after a cheap back card); C7 (dead lane, 1-1 other princess) | Φ is FIT on our SIM X-Bow outcomes (damage in 20 s by context), refreshed each league epoch, so it tracks what actually works for the current model. Acceptance: X-Bows committed into >= 7 public opp elixir toward pros' share; X-Bow damage per placement up |
| B4 | Rocket value: Φ(s, Rocket at target) = expected value removed (units + tower), with a large term when it finishes a princess, and tower chip on the WEAKEST enemy princess valued at its tiebreak worth (A1b's weight at that moment) | O9 (15% of losses one Rocket short; 0.29 Rockets/match vs ~2); S13 (Rocket+Tornado); S19 (Rocket cycling toward the tiebreaker); C5 | Rare action → advice is the right tool (a state term would never single it out). The chip value is fit from SIM outcomes (P(win) change per 100 HP of weakest-tower margin by phase), so it tracks the real tiebreaker. The OT finish stays a hard decode rule (D2) because it must be ~100% |
| B7 | **Rocket+Tornado as ONE decision** (S13, S20; O9): (1) a combo option — choosing Tornado can schedule the Rocket follow-up (point + delay) in the same decision, so the pair gets one shared credit (the SIM's follow-up machinery exists for live; it must be added to the learner's SIM action path); (2) advice Φ(s, Tornado at p) = the predicted Rocket value after the pull, from a pull model where GROUND units only gather with units on the SAME river bank as the pull (far-bank ground units stay a separate group), air units cross; (3) snapshot curriculum: episodes restarted from saved states where a clump approaches with Rocket + Tornado in hand, so the rare moment is practised often; (4) pro combos as imitation seeds | 10-11 SIM test: the combo put 61% of the clump's value in the blast vs 15% for a lone Rocket, but no combo arm beat its lone twin and 11-33% of combo Rockets were refused at landing — the two-step credit and timing are the problem, not the pull itself | Only valid if the SIM pulls like the real game: a SIM test of Tornado vs the river is running (TORNADO_RIVER.md); if the SIM drags ground troops across, that is a parity fix BEFORE any combo training, or RL would learn combos that fail live. Acceptance: combo rate, value in the Rocket blast per combo, share of combos whose ground targets were on one bank |
| B5 | Defensive reserve when ahead: negative for spending an evo or the last win-condition answer on offence while ahead | S5 (keep evos for defence; zero risk when ahead) | Only active in the "ahead" crown state (context from F2) |
| B6 | Hero IW ability: priced by its measured value (elixir removed / damage prevented by the freeze), never a flat bonus | O13, C9 (trigger-happy; never-press +3.3 pp in SIM) | Depends on live A/B3: if never-press wins live, the ability is a learned action with this advice instead of a rule |

---

## 5. Strategy layer (C) — long-term play by matchup and phase

The owner's concern: tower-damage shaping cannot teach *how aggressive or defensive to play* depending on the matchup
and the match phase. This layer is the part designed for that.

### C1. A posture head (hierarchical control)
- **Form.** A small extra head chooses a **posture** z ∈ {defend, balanced, pressure, spell-cycle} every ~10 s
  (spell-cycle = S10/S19: hold the win condition, Rocket/Log the weakest princess to build or keep a tiebreak lead), from the context
  (matchup archetype, phase, crown state, elixir trade, win-condition viability from B3, opponent counters seen). The
  play policy conditions on z (an input token), and the A/B weights depend on z: under `defend`, A1's own-tower weight
  and A2's solvency weight are high and B3's commit value is discounted; under `pressure`, the enemy-tower weight is
  high and A2 relaxes. The posture head itself is trained only on the **terminal win/loss** (plus its critic) — it is
  never paid for choosing a posture.
- **Why.** S10 (passive and spell-cycle when the win condition is countered), S11 (far behind: calculated risk), S12
  (pressure the pump), S5/S16 (ahead: defend out), S2 (pressure the opposite lane when their back card is cheap);
  C1, C8 (forward play in overtime); O11/O12 (score state and OT decide most matches); S18 (the hard matchups are
  exactly where posture matters).
- **How it sticks.** (1) **Imitation first**: label pro games with a posture from their own behaviour (share of elixir
  committed on the enemy half, X-Bow forward vs defensive, by matchup and phase) and pre-train the posture head on it,
  so it starts sensible. (2) RL then refines it with the win/loss signal only, so the posture it ends with is the one
  that wins in each context, not one we prescribed. (3) The posture is an explicit, logged variable: we can measure
  per matchup and phase whether the bot defends vs Golem and pressures a pump, and compare with pros.
- **Risk.** It is an architecture change (a new head and an input token): its own experiment, after A1/A2 are measured.
  Guard: posture entropy alarm (no collapse to one posture), per-archetype win rates.

### C2. Matchup-fair credit
- **Form.** Leave-one-out / critic baselines computed **per opponent archetype**, so a loss to Golem is compared with
  other Golem games, not with easy matchups.
- **Why.** S18 (train hard on unfavourable matchups); O7 (Golem 38%). With a shared baseline, the hard matchups' signal
  is swamped by the matchup's own difficulty.
- **How it sticks.** No reward change at all — it only makes the existing signal informative where it matters.

---

## 6. Constraints, not rewards (D)

| ID | Rule | Why a rule |
|---|---|---|
| D1 | Never target or place for the king tower (action mask) | S16; a reward only shifts odds, the owner wants never |
| D2 | OT lethal Rocket on a princess (existing decode option `--lethal-rocket`) | S17; owner ruled a learned emphasis is not enough (10-08) |
| D3 | No forced spending, ever (anti-stall stays removed) | anti-stall ruling 10-07; SIM must match live |

These stay outside the reward so the reward never has to fight them. Over time, distillation (step 4) can move D2 into
the model.

---

## 7. History we must not repeat (from L69/reward_plan.md §0, still valid)

| # | What broke | Lesson applied here |
|---|---|---|
| 1 | A free-standing penalty emptied the bar (91% of steps at 0-2 elixir) | Every term is a potential difference or look-ahead advice; nothing pays for a behaviour |
| 2 | Gate collapsed (0.12 plays/match) | Unconditional play-rate alarm |
| 3 | Placement collapsed under PPO | Per-card cell-entropy alarm |
| 4 | Graded placement reward narrowed cells, no control | Every arm has a matched no-change control |
| 5 | The KL leash froze learning | Leash tightness is its own experiment |
| 7 | The friend's elixir potential was as loud as winning and killed spells/buildings | Magnitude budget (total |Φ| <= 0.5 x terminal), spells priced by removal, A3 enters late |

---

## 8. How every term is made to stick (shared mechanisms)

1. **Potential/advice form only** (§0): the shaped behaviour survives only if it actually wins; the shaping cannot lock
   in a behaviour that loses. This is the main protection against teaching the model the wrong lesson.
2. **The environment keeps the incentive** (F3): calibrated opponents punish overspending and reward good defence, so
   the behaviour stays optimal under the plain win/loss reward once shaping is gone.
3. **Annealing with a retention check**: each term's weight decays to 0 over the last third of a run; the behaviour
   metrics (below) are measured at the peak and at the end. A term "stuck" if its metric holds within 20% after
   annealing; if not, the habit was only being paid for, and the next iteration changes the environment or the data,
   not the weight.
4. **The critic carries it**: with F1/F2 the value function absorbs each potential (Wiewiora), so the concepts live in
   the model's own value estimate and keep guiding its credit after the shaping weight is zero.
5. **Distillation**: the final player (model + any decode rules) is distilled into the plain model (step 4), so rules
   become removable — the owner's stated goal.
6. **Measured with live definitions**: every term's acceptance metric is computed the same way on SIM, live and pro
   data (econ2, loss review, punish.py), so "it stuck" is checked live, not only in the SIM.

**Acceptance metrics per term** (SIM 960 pairs + live A/B; pro value in brackets where known):
A1 towers lost in 1x, damage concentration on one princess; A2 approach spending (0.57), pushes met < 4 elixir (24%),
low-elixir penalty; A3 elixir trade at match end, spells on nothing; A4/A5 support-kill order, enemy path length;
A6 own value per enemy spell, Rocket value per cast; B1 cheap taps < 5 elixir/min; B2 response class vs Hunter matrix;
B3 X-Bow dealt in 20 s, commits into >= 7 opp elixir (pros 46%); B4 Rockets/match (~2), one-Rocket-short losses;
C1 posture by matchup/phase vs pro labels, per-archetype win rates.

---

## 9. Pre-flight checks before any shaped run (cheap, CPU)

1. Telescoping test (sum of F per match = −Φ(s0)).
2. Magnitude budget on 100 IL-policy matches.
3. Scripted-policy audit **under F1's critic**: never-play, spend-immediately, hold-to-10, spam-one-card, never-buildings,
   never-spells, kite-forever must each score BELOW the IL policy on the shaped return. Any that scores above → redesign.
4. Unit tests: level normalisation (F5), spell pricing by removal (A3), king weight = 0 (A1).

---

## 10. Order of experiments (one change each; each vs a matched control)

| Step | Change | Needs | Decides |
|---|---|---|---|
| 0 | Option 1 — DONE (O17): not imitation fit; RL drift + own-state shift (~2/3 of the approach excess) | — | RL with an on-policy signal is needed (steps 1-3); F6 removes the drift part |
| 0b | F6 leash to the imitation gate | small code change | Removes RL drift (O17) |
| 1 | F3 calibrated opponents (environment only) | pod | Does RL learn the economy at all when punished like live? |
| 2 | F1 per-decision credit (gae + critic warm-up) | built | Whether shaping can work at all here |
| 3 | + A1 + A2 (score-aware tower + solvency) | new Φ code | The biggest measured loss factor (O4/O5) |
| 4 | + F4 deployment-like exploration (T_gate) | built | Train/deploy mismatch (O3) |
| 5 | + A3 trade, + B1/B2 | Φ code + Hunter matrix | Cheap cycling, overspending on small threats |
| 6 | + A4/A5/A6, + B3/B4 (fit from data) | Φ fits | Defence quality, X-Bow timing, Rocket |
| 7 | C1 posture head (imitation-pretrained) + C2 | architecture | Long-term strategy by matchup and phase |
| 8 | Distil the winner (step 4 machinery), live A/B | — | Rules removable; live trophies |

Each step: 960-pair SIM vs its control (per-archetype breakdown), the behaviour metrics of §8, the alarms of §7, and a
live A/B for anything that passes the SIM pre-filter (owner's bar: live decides).

---

## 11. Honest limits

- Potential shaping **speeds learning; it cannot make a losing habit win**. If a behaviour the owner wants does not win
  in the SIM, shaping will not make it stick — the fix then is the environment (F3) or the data (imitation), and we
  will say so per term.
- About **one third of the live economy gap is live-only** (O4: SIM 1.49 vs live 2.43): SIM training alone cannot close
  it; the live encoding/latency causes (e.g., the Hero IW readiness token) need their own fixes.
- R2 (flat tower + crown potential, WITH per-decision credit) and R4c (a frozen value-head potential) were both nulls
  (O14). So per-decision credit plus a generic potential is known not to be enough; this design rests on terms aimed at
  the measured loss mechanisms (A2 solvency, B3 X-Bow timing, B4 Rocket) and on context (A1's score weights, C1
  posture), plus opponents that punish like live (F3). If step 3 is also null, that is strong evidence the bottleneck
  is not the reward at all (then: data/imitation and the environment).
- Everything in §3-§5 is a design. Each term's weights, thresholds (k, N, caps) and Φ fits are untested.
