# EVAL-ONLY FLAT ROLLOUT SEARCH — measurement ledger

HANDOFF §4x. Harness: `scratchpad/rollout_search.py` (deliberately NOT in the repo tree, imported by
no source file, not committed; its JSON outputs and the checkpoint copy sit beside it).

**This is FLAT ROLLOUT SEARCH, not MCTS.** No tree, no reuse across iterations, no backup. Every
searched decision enumerates its candidates, rolls each one out once, and takes the argmax.

## VERDICT IN ONE BOX

```
policy alone                                    winrate 37.0%   tower delta -0.928
+ search, H=12 s, every 5th decision            winrate 59.0%   tower delta -0.234   (+9.53 sigma)
+ search, H=12 s, EVERY decision                winrate 78.7%   tower delta +0.450   (+18.81 sigma)
```
**Search >> policy, by a very large margin, and it survives every control that was built to kill
it** — a minimal-horizon control, a play-more ablation, a full gate-threshold sweep in BOTH
directions, removal of the opponent-future oracle, perfect perception for the policy, and a crown
weight sweep. By §4x's own decision rule that means the policy's ACTION SELECTION is the bottleneck
and AlphaZero-style distillation is worth costing out. Read §9 first: two cheaper things come
before it, and the obvious cheap imitation (retune the gate) is already measured and DEAD.

---

## 0. PRE-COMMITMENT (written before any arm was compared)

* **Reference policy** — a COPY of `icebow/data/policy_BEST_m18000_20260826.pt`
  (`scratchpad/_rs_policy.pt`), so the live file is read once and never again (§4s trap).
* **n = 300 matches per arm**, seeds `5_000_000 … 5_000_299`, **identical across every arm**, so
  every comparison is PAIRED.
* **Baseline** = the policy's greedy action, byte-identical to `train_sim_ppo.choose_greedy`
  (gate probability vs `sim.ppo_gate_threshold` 0.25, argmax card, argmax masked cell).
* **Arms** = horizon H ∈ {3, 5, 8, 12} s at a FIXED interval N = 5 decisions and K = 4.
* **Primary outcome: TOWER DELTA** — (our standing tower HP − theirs) at match end, each side
  normalised by its own princess tower, the normalisation `SimMatchEnv._position` uses. Continuous,
  so far more power per match than a win/loss bit.
* **Secondary: crown delta, winrate.**
* **THE BAR: |paired mean difference| / sem ≥ 2.0, or NO MEASUREMENT.** sem reported regardless.
* **Multiplicity, declared up front:** four arms on the primary metric means a single 2σ hit arrives
  by chance ~18% of the time. One arm at 2σ with three flat would NOT be a result; a monotone trend
  across horizons would be.

Everything after §4 was added AFTER the sweep, as controls and extensions. They are labelled as
such and none of them is used to rescue the primary claim.

---

## 1. THE HARNESS, and the three checks it had to pass first

Single process, `torch.set_num_threads(1)`, `PYTHONHASHSEED=0`, torch/numpy/random seeded, one
`SimMatchEnv` reused with `env.rng.seed(seed)` before every `reset()`, `domain_rand` OFF, ladder
opponent pool (`opponent_provider = None`) — the trainer's own eval configuration.

**The fork.** `copy.deepcopy((env.eng, env.opponent))` — ONE deepcopy of the PAIR, not two calls.
`SimMatchEnv` hands `env.rng` to the engine *and* to `make_opponent`, so in the live match those two
are the SAME `random.Random` object. The shipped `SimMatchEnv._fork` deepcopies them separately,
splitting one shared stream into two; copying the tuple preserves the aliasing and makes the branch
a faithful continuation. (Not a bug in `_fork` — its docstring only claims isolation from the real
match, which it has — but it is the wrong thing for a search branch.)

**Candidate set = every playable card at its policy-argmax cell, plus WAIT.**
K = 4, and **K = 4 is not a truncation**: MEASURED, `env._hand_ids()` returns exactly 4 identities at
every step (4 hand slots; an Evolution shares its base card's slot, so base and evo are never both
in hand), so top-4 over the PLAYABLE set is the *complete* set of card-level actions. Mean candidates
actually rolled out per searched decision: **3.02**, i.e. ~2 affordable cards, because mean elixir is
2.7-3.4. WAIT is always in the set.

**Rollout policy.** Our side idles for the horizon; the opponent keeps running its scripted line.
Identical to the shipped counterfactual fork (`_roll_fork`, *"the AGENT DOING NOTHING"*). §5 shows
this default is the reason the N=5 and N=1 arms disagree about restraint, so it is not a detail.

### ⚠ A FOURTH CHECK, forced by a concurrent edit
`icebow/config/cards.yaml` and `hogeq/config/cards.yaml` were modified by ANOTHER worker at
**13:55:19** (ruling 29, pricing the spawned bodies) while these arms were running. Every arm
STARTED before that (latest start 13:50:21) and the card DB is read once at process start, but that
is an argument, not a measurement. So it was measured: the 60-match baseline was re-run AFTER the
edit and its records are **byte-identical** to the corresponding rows of the pre-edit 300-match
baseline. The edit prices spawned bodies of OTHER decks and does not touch this one. **Every arm in
this ledger is comparable.**

### The three checks, all passed
```
baseline run 1 vs run 2, separate processes      IDENTICAL (8 matches, full records)
search   run 1 vs run 2, separate processes      IDENTICAL (8 matches, full records)
LEAK PROBE: --force-policy (run every rollout,
  discard the answer, play the policy's action)  IDENTICAL to the baseline record
```
The third is the one that matters: 225 searched decisions × ~3 candidates of forking, deploying and
ticking a cloned engine changed **nothing** about the live match, RNG included. The sim is
reproducible run-to-run as of the `deploy_seq` fix (conflicts.md I10-FOLLOWUP) and this harness
inherits that.

---

## 2. BASELINE — the policy alone, 300 matches

```
n=300   winrate 37.0%   crowns FOR 0.99 / AGAINST 1.46   tower delta -0.928
        189 losses, 111 wins, 0 draws       mean match length 176.0 s
        plays/match 32.6   casts/match 7.90   mean elixir 3.35   steps at >=6 elixir 13.8%
        1.56 s/match
```
Two cross-checks against numbers this project already has:
* §4t's trainer eval put this checkpoint at **ladder 34%**. 37.0% here — §7b is probably most of it.
* §4q measured `ARM_fix23b` at **mean elixir 3.10, 13.3% of steps at >=6**. This harness reads
  3.35 / 13.8% on a later checkpoint. Independent instrumentation, same ballpark, so the elixir
  diagnostics below are comparable with §4q's.

**Power.** Unpaired sem is 0.082 on tower delta and 2.8pp on winrate, so the pre-committed 2σ bar
corresponds to a minimum detectable effect of about **0.16 tower fractions or 5.6pp of winrate**
before pairing. A null here would have meant "smaller than that", not "zero". (It is not a null.)

---

## 3. THE CROWN TERM, and why its magnitude is 1.0

§4x asks for the crown term's magnitude to be justified rather than picked. The HP half of the score
already values a whole princess tower at exactly **1.0**. The crown term adds **1.0 more**, so a
tower TAKEN is worth 2.0 while a tower chipped to 1 HP is worth 1.0 — the last 100 HP of a 4424-HP
princess tower is worth 0.023 + 1.0 = **1.023, about 45x the first 100 HP**. That is §4x point 2's
discreteness. The doubling is anchored on two engine facts, not taste:
1. **The pocket opens** (`pocket_state` / `deployable_mask`) — deployment across the river on that
   side, permanently.
2. **Its DPS stops permanently** — `hit_dmg` ~158 every 0.8 s; over a typical 100 s of remaining
   match that is ~19,000 damage that no longer has to be survived.

**And it is not a free parameter — it was SWEPT and it does not matter** (n=300 each, paired tower
delta vs baseline):
```
crown weight 0.0   +0.705  (9.78 sigma)   winrate 57.0%
crown weight 1.0   +0.694  (9.53 sigma)   winrate 59.0%      <- the arms above
crown weight 3.0   +0.691  (9.47 sigma)   winrate 59.0%
```
A 0 → 3 sweep moves the effect by 2%. The term fires in 11.6% of candidate rollouts at H=12, so it
is active; it simply is not the lever. **The result does not rest on this choice.**

---

## 4. ⚠⚠ THE HORIZON SWEEP — SEARCH BEATS THE POLICY, MONOTONE TO ~12 s, THEN A PLATEAU

N = 5 (every 5th decision = every 3.0 s of game time), K = 4, crown 1.0, n = 300 paired.
H = 0.6, 20 and 40 s were added afterwards to find the ends of the curve.

```
arm         win%  crownsF crownsA towerdelta  plays/m  mean elx  >=6 elx  match len
base        37.0    0.99    1.46    -0.928     32.6      3.35     13.8%     176.0 s
H = 0.6 s   43.7    0.87    1.28    -0.865     31.7      3.25     12.6%     176.1 s
H = 3 s     39.7    0.76    1.10    -0.722     37.9      2.97      8.0%     193.3 s
H = 5 s     45.3    0.86    1.04    -0.590     38.2      2.86      6.1%     194.8 s
H = 8 s     49.7    1.00    1.05    -0.459     38.8      2.78      5.0%     194.7 s
H = 12 s    59.0    1.11    0.92    -0.234     38.6      2.74      4.5%     194.9 s   <- PEAK
H = 20 s    55.0    1.08    0.95    -0.239     37.1      2.72      4.3%     188.9 s
H = 40 s    53.3    1.09    1.02    -0.301     37.0      2.78      5.0%     188.8 s
```

PAIRED against the same 300 seeds. **Pre-committed bar was |sigma| >= 2.0.**
```
              TOWER DELTA (primary)          CROWN DELTA              WINRATE
          delta    sem   sigma           delta  sigma            delta   sigma
H = 0.6  +0.063  0.071  +0.88  NO MEAS.  +0.047 +0.56  n.s.     +6.7pp  +2.34  SIG
H = 3    +0.206  0.074  +2.78  SIG       +0.120 +1.50  n.s.     +2.7pp  +0.86  n.s.
H = 5    +0.337  0.073  +4.65  SIG       +0.280 +3.51  SIG      +8.3pp  +2.74  SIG
H = 8    +0.469  0.073  +6.43  SIG       +0.410 +5.03  SIG     +12.7pp  +3.97  SIG
H = 12   +0.694  0.073  +9.53  SIG       +0.653 +8.07  SIG     +22.0pp  +7.04  SIG
H = 20   +0.688  0.073  +9.49  SIG       +0.597 +7.72  SIG     +18.0pp  +6.17  SIG
H = 40   +0.626  0.075  +8.41  SIG       +0.530 +6.42  SIG     +16.3pp  +5.24  SIG
```

**The bar is cleared on the primary metric at every horizon from 3 s up, by 9.5σ at H = 12.** This
is not a multiplicity artefact: the effect is monotone in the horizon on all three metrics
independently up to 12 s. **The verdict does not FLIP with horizon** (§4x's stated worry) — it
grows, peaks at **H = 12 s**, and decays gently past 20 s. A horizon that long starts to include
consequences the current action does not control, which is a sensible place for the curve to turn
over, but that mechanism is NOT tested here.

Two honesty notes on the weak end:
* **H = 3 is the weak arm.** Trimmed mean (5 dropped each tail) +0.195 at 2.87σ, so it is not
  outlier-driven — but its SIGN TEST is +159/−140, z = +1.10, not significant, and its winrate delta
  is not either. Read it as the low end of a trend, not a standalone result.
* **H = 0.6 is a NULL on the primary metric** (+0.063, 0.88σ), while its winrate is marginal
  (+6.7pp, 2.34σ). Its role is as a control — see §6.1.

### The search's behaviour
```
arm       searched  disagree  dis%   policy WAITs  search WAITs   ms/cand
H = 0.6     10022     2665    26.6%     81.0%         80.8%         2.60
H = 3       11146     4134    37.1%     82.4%         67.8%         3.67
H = 5       11266     4446    39.5%     83.0%         64.1%         4.25
H = 8       11031     4499    40.8%     82.8%         62.1%         5.77
H = 12      11081     4539    41.0%     82.6%         62.2%         7.95
```
**Search disagrees with the policy's argmax on 37-41% of searched decisions.** This is emphatically
not the "null because search never changes anything" case.

### Spell placement is untouched, exactly as designed
```
            casts/m   ALL dumped   the_log        tornado       rocket
base          7.90      35.1%      44% d, 1.6t    13% d, 1.0t   11% d, 0.8t
H = 12 s      9.32      34.3%      46% d, 1.6t     9% d, 1.0t   14% d, 0.9t
```
Search casts more spells and aims them exactly as badly, because the candidate set searches CARDS
and takes the CELL from the policy. **The whole gain is "which card, and whether to play at all",
with the known-broken placement head left in place.** §5.2 relaxes that.

---

## 5. TWO EXTENSIONS — and the first one REVERSES the restraint reading

### 5.1 ⚠⚠ SEARCH DENSITY: at EVERY decision it wins 78.7%, AND IT GETS THERE BY WAITING MORE

`--interval 1` (H = 12, K = 4, n = 300, same seeds):
```
                   winrate   tower delta    paired sigma (tower / crown / win)
base                37.0%      -0.928            —
every 5th (N=5)     59.0%      -0.234       +9.53 / +8.07 / +7.04
EVERY decision      78.7%      +0.450      +18.81 / +14.93 / +13.23
```
+41.7pp of winrate at 13.2σ, and the tower delta goes **positive** — this policy under full search
ends matches ahead on towers, which it has never once done on its own.

**And the restraint sign flips.** Same states, policy vs search, on searched decisions:
```
                    policy WAITs   search WAITs        play->WAIT   WAIT->play
N = 5 (interleaved)     82.6%          62.2%              1053         3313      search PLAYS more
N = 1 (search-only)     59.3%          82.1%             17344         5044      search WAITS more
```
Per-card at N = 1, share of searched decisions:
```
WAIT        policy 59.3%  ->  search 82.1%   +22.8pp
ice_wizard         9.5%   ->          2.9%    -6.6pp
skeletons          8.2%   ->          3.5%    -4.7pp
the_log            7.0%   ->          2.3%    -4.7pp
tesla              4.8%   ->          2.1%    -2.8pp
tornado            3.5%   ->          1.3%    -2.2pp
x_bow              2.9%   ->          1.4%    -1.5pp
```
**Search declines every single card, and cheap chaff hardest.** Total plays/match ends up 32.3
versus the baseline's 32.6 — the same VOLUME of play, radically better SELECTION, and more than
double the winrate.

⚠ **Why the two arms disagree, and it is the rollout default.** The rollout assumes our side does
nothing for the horizon. At N = 1 that assumption is nearly true, so the search's choices are
self-consistent. At N = 5 it is false: search plays the one card the board needs, then four
*unsearched* policy decisions pile on top of it. plays/match goes 32.6 → 38.6 at N = 5 and stays at
32.3 at N = 1. **So "search chooses less restraint" is an artefact of INTERLEAVING search with the
policy; when search controls the decision stream it chooses substantially MORE restraint.**

That is a direct, independent confirmation of §4q's over-commit diagnosis, reached without going
near the shaped reward — and it does it while mean elixir stays LOW (2.81) and steps at >=6 elixir
stay at 5.6%. **Restraint here is not "bank to six"; it is "stop playing the cheap answer that does
not need playing".** Nothing in this experiment supports or refutes `bank_to_six_then_bow`.

### 5.2 SEARCHING PLACEMENT TOO adds a real but much smaller increment

`--cells 3` (top-3 cells per candidate card instead of the policy's argmax only; 6.87 candidates per
decision, H = 12, N = 5, n = 300):
```
                        winrate   tower delta   paired tower sigma
H=12, cell = argmax      59.0%      -0.234           +9.53
H=12, top-3 cells        62.3%      -0.018          +12.27
```
+3.3pp of winrate and +0.216 of tower delta on top of card search, with search moving the cell while
keeping the card on 319 decisions. Real, and much smaller than the card/gate effect — consistent
with §4 finding the entire first-order gain in *which card*.

---

## 6. THE CONTROLS — five attempts to kill the result, none succeeded

Every one of these was built to produce a cheaper explanation than "search is better".

### 6.1 "It is the scoring function, not the lookahead" — REFUTED
H = 0.6 s (one 0.6 s step: the candidate lands, almost nothing plays out) is a **NULL on the primary
metric**: +0.063 tower delta, **0.88σ**, `no measurement`. Its WAIT/play split is also balanced
(1308 vs 1287) where the long horizons run 3:1 toward playing. So the score has no meaningful
built-in action bonus, and the gain is *lookahead*, not a hand-written instantaneous heuristic.

### 6.2 "Search just plays more" — REFUTED, twice, decisively
**Ablation `--force-play`** (at every 5th decision, override the gate and play the policy's top card;
no rollouts at all), n=300:
```
                 winrate   tower delta   paired tower sigma
base              37.0%      -0.928           —
force-play        17.0%      -1.388        -6.85   (WORSE, 6.9 sigma AGAINST)
```
**Gate-threshold scan** (`sim.ppo_gate_threshold`) — the fair "play more / play less" control, since
tau moves P(play) smoothly in both directions. Swept BOTH ways; downward at n=60, upward at n=300
paired (the upward half is the interesting one, see §5.1):
```
tau     winrate   tower    plays/m  mean elx  >=6 elx    paired tower vs base
0.02     18.3%    -1.486      -        -         -        (n=60)
0.05     16.7%    -1.438      -        -         -        (n=60)
0.10     21.7%    -1.287      -        -         -        (n=60)
0.15     31.7%    -0.979      -        -         -        (n=60)
0.25     37.0%    -0.928     32.6     3.35     13.8%      BASELINE (shipped)
0.35     37.7%    -1.003     26.1     4.02     21.9%      -0.075   -0.91 sigma   n.s.
0.45     30.7%    -1.240     19.6     4.87     32.3%      -0.312   -3.67 sigma   WORSE
0.60     18.0%    -1.856     12.8     6.15     49.1%      -0.929  -11.05 sigma   WORSE
```
**The curve peaks at the shipped 0.25 and falls off in BOTH directions** (0.35 is statistically
indistinguishable from it; everything further out is worse). So the gate threshold is ALREADY at its
optimum, "play more" is harmful, and — the part that matters — **"play less" via a scalar is harmful
too**. Search's restraint (§5.1) is state-dependent and no threshold can imitate it.

⚠ **And note tau 0.60 in passing.** It banks exactly the way the doctrine asks — mean elixir 6.15,
49.1% of steps at >=6 — and it wins **18.0%** against the baseline's 37.0%, at 11σ. Forcing THIS
policy to hold elixir is severely harmful. That does not make banking wrong; it says this policy
cannot convert banked elixir into anything (which is precisely §4t's `bank_to_six_then_bow` 0%),
and therefore that elixir statistics alone cannot grade play in either direction.

### 6.3 "The clone knows the opponent's future dice rolls" — REFUTED (this was the biggest worry)
The fork carries the opponent's RNG state, so a branch replays the opponent's *actual* future draws
— which lane it will push, which card it will pick. That is information no real search could have.
`--reseed-opp` draws ONE fresh seed per searched decision and rolls every candidate at that decision
under it (common random numbers, so candidates stay comparable), turning the branch from THE future
into A SAMPLE of it:
```
                          winrate   tower delta   paired tower sigma
H=12, oracle (as above)    59.0%      -0.234          +9.53
H=12, opponent RESEEDED    57.3%      -0.281          +9.42
```
**93% of the effect survives.** The result is not an oracle artefact.

### 6.4 "Search sees the board and the policy does not" — REFUTED
The rollout clones the ENGINE (ground truth) while the policy's observation is deliberately degraded
(`sim_detector_recall 0.82`, `precision 0.89`, `sim_detector_presence_recall 0.85`). So the raw gap
mixes JUDGEMENT with PERCEPTION. `--perfect-obs` hands the policy clean perception, n=300:
```
                              winrate   tower delta   paired tower sigma
base (degraded obs)            37.0%      -0.928          —
policy with PERFECT obs        37.0%      -0.910        +0.25   no measurement
                                                        (+0.00 sigma on winrate)
```
**Exactly zero.** Clean perception buys this policy nothing (it plays slightly less: 29.4 vs 32.6
plays/match, mean elixir 3.65 vs 3.35, and wins identically).
⚠ This is a LOWER bound on the perception contribution, not an estimate of it: the policy was
TRAINED on the noisy observation, so being handed clean input is off-distribution and it may simply
not be able to use it. What it does establish is that **the perception gap is not something this
policy can convert into wins**, so "search only wins because it sees more" does not survive as an
explanation of the measured gap.

### 6.5 "It is the crown weight" — REFUTED
See §3: sweeping crown 0.0 / 1.0 / 3.0 moves the paired effect from +0.705 to +0.694 to +0.691.

---

## 7. THREE THINGS FOUND WHILE BUILDING THE BASELINE — none is about search

### 7a. ⚠⚠ §4r's SPELL-DUMP NUMBERS ARE THE *SAMPLING* POLICY'S. EVAL AND LIVE RUN GREEDY, AND GREEDY DUMPS FAR LESS.

The baseline's dump rate came out at **35.1%**, not the 61-66% §4r/§4t report. §4r's probe script is
no longer in the tree, so the difference could not be traced by reading — it was measured.
`scratchpad/cellmode_probe.py`, ONE checkpoint, ONE set of states, both selection modes, 25 matches,
every step at which the spell was playable:
```
card       greedy (argmax)             sampled (softmax of the SAME head)     §4r reported
the_log    52.7% dumped, med 2.10t     72.5% dumped, med 5.72t                73% dumped
tornado    14.2% dumped, med 1.17t     65.0% dumped, med 7.89t                58% dumped
rocket     25.2% dumped, med 1.21t     30.4% dumped, med 1.23t                53% (n~19)
```
**The sampled column reproduces §4r almost exactly; the greedy column does not resemble it.** And
`play.epsilon: 0.0`, so `play.py` takes `card_logits.argmax` / `cell_logits.argmax` — **live is
GREEDY**, and so is the trainer's eval (`choose_greedy`).

* **Does NOT overturn §4r's mechanism.** A near-uniform cell head with one modest peak is exactly
  what produces this split: sampling scatters, argmax lands on the peak. The entropy result stands.
* **DOES overturn the consequence claim for eval/live.** "66% of casts are dumped" is a property of
  the TRAINING-mode policy. The mode that ships dumps the Log at ~45% (in-match, greedy, n=1908
  casts) and the Tornado at ~10%. A spell A/B graded on the sampled dump rate grades behaviour that
  never ships.
* **It makes §4r's own untested caveat more important.** §4r flagged "whether LIVE adds its own
  error on top — untested". If live is greedy and greedy dumps the Tornado at 10%, the owner's live
  observation is NOT explained by the sim policy, and the live path (grid round-trip, detector, aim
  assists) is the first place to look.
⚠ CAVEAT: this is `policy_BEST_m18000_20260826`; §4r measured `policy_ppo_long@16k` and
`policy_BEST_m26000_20260823`. The sampled column matching §4r within 1-7pp on two of three cards is
strong evidence the MODE is the explanation, but the checkpoint is not controlled.

### 7b. The trainer's own eval is BIASED LOW, because it counts the first 150 matches to FINISH
`train_sim_ppo.evaluate()` runs ~96 envs in lockstep and stops at `while played < eval_matches`
(150). Matches that END SOONER are counted first, so ~54 of the 150 are length-selected. MEASURED on
the 300-match baseline:
```
losses  median match length 174.6 s      winrate over ALL 300 matches:   37.0%
wins    median match length 180.1 s      winrate over the FASTEST HALF:  20.7%
```
Short matches are losses. 96 unbiased + 54 short-selected predicts ~31% where the unbiased number is
37%; §4t reports 34% for this checkpoint. Direction confirmed, magnitude approximate.
⚠ **This does NOT explain §4t's decay.** A roughly constant offset cannot produce five consecutive
declining points; it moves the LEVEL, not the TREND. The one way it could touch the trend is if a
decaying policy loses FASTER, deepening the selection over training — **untested**, do not assert it.

### 7c. Four per-unit ledgers in `env.py` are still keyed on `id()` — but the corruption is RARE
conflicts.md's I10-FOLLOWUP re-keyed the five SPELL sites onto `Unit.deploy_seq`. Still on `id()`:
`_ev_enemy`/`_ev_own` (elixir-trade ledger, ~line 1938), `_nado_watch[...]["pulled"]` (~2401), and
`_bow_ledger` (~2667). Measured over 30 matches:
```
address reuse events (a dead unit's id() taken over by a live one)   488   in 25/30 matches
FALSE CONTINUATIONS in the step-to-step trade ledger                   1   in  1/30 matches
```
The precondition is common; the step-to-step trade ledger is almost never actually corrupted,
because it is rebuilt every 0.6 s and the address has to be recycled inside that window.
⚠ `_bow_ledger` is NOT covered by that reassurance — `led["ids"]` accumulates over a bow's whole
lifetime, so its window is seconds, not one step. **NOT measured** (it needs the policy to field
bows). Named so it is not mistaken for closed.

---

## 8. WALL CLOCK — §4x's 45-minute projection was ~8x pessimistic

Measured serially, one process, nothing else on the box:
```
arm         s/match   ms/candidate   -> 150-match eval    -> 300-match eval
baseline      1.56          -              3.9 min             7.8 min
H = 3 s       2.11        3.67             5.3 min            10.6 min
H = 5 s       1.97        4.25             4.9 min             9.9 min
H = 8 s       2.15        5.77             5.4 min            10.8 min
H = 12 s      2.35        7.95             5.9 min            11.8 min
H = 12, N=1   8.21       11.46            20.5 min            41.1 min   (contended, upper bound)
```
**A 150-match eval with search at H = 12 costs 5.9 minutes, not 45.** §4x's estimate assumed 20
candidates on a 72-unit board; the real candidate set averages **3.02** (4 hand slots, ~2 affordable)
and eval boards are mostly quiet. Per-candidate cost lands where §4x's *quiet* row predicted
(4.25 ms measured at H = 5 vs 4.0 ms projected), so the per-candidate model was right and only the
candidate COUNT was wrong. Search is 18-33% of wall clock at N = 5.
⚠ Arms after H = 12 ran up to 8-at-a-time on a 16-core box; their s/match is contended and is not
comparable with the serial block above.

**The training-time verdict in §4x is unchanged**: even the cheap N = 5 arm is ~11 s of search per
match against a 20-170 ms match, still ~100x.

---

## 9. WHAT THIS MEANS — and what it does NOT

### It means the policy's action selection is the bottleneck, and by a lot
Same weights, same observation, same opponent, same seeds. The only thing added is choosing among
the actions the policy already ranks, by rolling them out and reading the outcome. That takes 37.0%
to 59.0% (N = 5) and to 78.7% (N = 1). Every cheaper explanation was tested and failed: it is not the
scoring heuristic (§6.1), not playing more OR playing less (§6.2), not the opponent oracle (§6.3), not perception
(§6.4), not the crown weight (§6.5). **The information needed to play twice as well is already in
the policy's own action ranking; the policy is not using it.**

### ⚠ It does NOT address the §4t eval decay, and must not be sold as doing so
§4t's decay was measured and never diagnosed, and every candidate cause — curriculum ratcheting,
entropy floor, drill/match advantage gap, value-loss drift — is a TRAINING dynamic. Decision-time
search touches none of them. Nothing here is evidence about the decay in either direction.

### Is distillation worth costing out? YES — and the cheap alternative is already dead
1. ~~Retune the gate threshold.~~ **ALREADY TESTED AND CLOSED (§6.2).** The search's correction at
   N = 1 is almost entirely *decline more often*, so the obvious cheap imitation is to raise
   `ppo_gate_threshold`. It was swept 0.02 → 0.60 at n = 300 paired: the curve **peaks at the shipped
   0.25 and falls off both ways**, and tau 0.60 (mean elixir 6.15, 49% of steps at >=6) loses at
   11σ. **Search's restraint is state-dependent and no scalar reproduces it** — which is exactly the
   argument FOR distillation rather than against it, and it cost 25 minutes to establish.
2. **Search is cheap enough to SHIP in eval right now.** 5.9 min for a 150-match eval at H = 12.
   A policy+search eval alongside the plain one gives every future training experiment a second
   readout — "did the POLICY improve, or did its action RANKING improve" — which is exactly the
   question §4d/§4t keep failing to separate.
3. **Fix the eval protocol first (§7b) and re-read §4r in greedy mode (§7a).** Both are cheap and
   both change how existing measurements should be interpreted.

Then distillation. What the costing needs to account for, from these numbers:
* **The target is the GATE and the CARD head, not the CELL head.** Card search alone delivers the
  whole first-order effect (§4); adding cell search adds +3.3pp on top of +22.0pp (§5.2). A
  distillation run would leave §4r's placement collapse exactly where it is.
* **Generating targets is affordable; search INSIDE the PPO loop still is not.** §4x's ~100x
  training-time figure stands (§8). But AlphaZero-style distillation does not need search inside the
  loop — it needs a CORPUS of (state, search-action) pairs, and the N = 1 arm produced **53,954
  searched decisions over 300 matches in 41 min** (contended; ~30 min serial). A few hundred
  thousand labelled decisions is an overnight job on this box, not months. **That** is the version
  worth costing, and it is the one this measurement licenses.
* **Use N = 1, not N = 5.** §5.1: the interleaved arm's targets are contaminated by the unsearched
  policy decisions that follow them, and its restraint signal has the WRONG SIGN.
* **H = 12 s.** Measured optimum; 20 s and 40 s are worse.

### Open, and honestly not established
* Whether a policy can LEARN these targets from the degraded observation it actually gets. §6.4 shows
  perfect perception buys this policy nothing, which is encouraging (the targets do not obviously
  depend on hidden state) but is not the same as showing they are learnable.
* Whether the gain survives against opponents that are not this scripted pool. Every arm here used
  the frozen ladder benchmark.
* Why the horizon curve turns over past 20 s.
* Whether searching over MORE cells (top-3 was the only setting tried) keeps paying.

---

*Harness `scratchpad/rollout_search.py`; probes `scratchpad/cellmode_probe.py`,
`scratchpad/id_reuse_probe.py`, `scratchpad/id_reuse_probe2.py`; analysis `scratchpad/rs_analyze.py`.
None of them is in the repo tree. Raw per-match records in `scratchpad/rs_<arm>.json`.*
