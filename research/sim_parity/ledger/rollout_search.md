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

**[added by sweep 2, 2026-08-27]** The ceiling is now measured: **H = 12, K = 4, N = 1, cells = 3
wins 85.7% at tower delta +0.651 (+1.578, 20.7 sigma)**, horizon saturates at H = 12 and FALLS if
rolled to the match end, K is inert, and N is the only real lever. Live search is ruled OUT on state
reconstruction and perception sensitivity; **distillation is the recommendation**. See §10-§19,
and §10 FIRST — the harness is not reproducible run-to-run and every number in this file carries
that error bar.

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

---
---

# SWEEP 2 — WHERE THE GAINS STOP (2026-08-27)

Sweep 1 (§0-§8) ended with a monotone horizon curve and **no saturation at its longest arm**, so it
could not say where the ceiling was. This sweep finds it, sweeps the two knobs sweep 1 held fixed
(K and N), and addresses the match-position confound sweep 1 never controlled.

Same harness, same reference checkpoint copy, same 300 paired seeds `5_000_000 … 5_000_299`, same
scoring function, same pre-committed bar: **|paired mean difference| / sem ≥ 2.0 on TOWER DELTA, or
NO MEASUREMENT.** Baseline arm kept for reference. Every sigma below is against the same
`rs_base.json`.

The harness gained four opt-in flags for this sweep (`--phase-lo/-hi`, `--jit-*`,
`--dump-decisions`, plus the `--cells` / `--reseed-opp` / `--force-play` flags an earlier session
added). **All default to the sweep-1 behaviour**, so arms from both sweeps are directly comparable.

## 10. ⚠⚠ FOUND FIRST, AND IT CORRECTS §1: THE HARNESS IS NOT REPRODUCIBLE. `PYTHONHASHSEED` IS SET TOO LATE.

§1 reports `baseline run 1 vs run 2, separate processes IDENTICAL`. **As the harness is invoked
today, that is false.** Two runs of a byte-identical command disagree on the FIRST match:

```
_rs_prepatch.py --matches 3 --seed0 5000000 --horizon 12   run A: match0 = 341 steps, t_end 204.3
                                              (same cmd)   run B: match0 = 301 steps, t_end 180.1
baseline H=0, same command twice                           235 steps  vs  446 steps
```

The cause is in the harness's own preamble:
```python
os.environ.setdefault("PYTHONHASHSEED", "0")     # line ~50, AFTER the interpreter has started
```
`PYTHONHASHSEED` is read by CPython **at interpreter start-up**. Setting it from inside the running
process is a no-op, so string-hash randomisation was live for every arm in both sweeps, and some
dict/set iteration inside the engine or env reaches the simulation. EXPORTING it fixes the problem
completely:
```
PYTHONHASHSEED=0, search H=12, run 1 vs run 2      IDENTICAL
PYTHONHASHSEED=0, baseline    , run 1 vs run 2      IDENTICAL
PYTHONHASHSEED unset, baseline, run 1 vs run 2      MISMATCH (235 vs 446 steps on match 0)
```
A second, much smaller effect also exists: with the hash seed fixed, a 3-match run and a 6-match run
still differ slightly from match 1 onward (305 vs 306 steps). **Rule: only compare runs with
identical `--matches`.** Every arm in both sweeps used `--matches 300`, so this one is satisfied.

### What this does and does not invalidate — measured, not asserted

* **It does NOT invalidate the effect sizes or the sigmas.** The reported sem is the empirical
  standard error OF THE OBSERVED PAIRED DIFFERENCES, so it already contains whatever noise hash
  order injected. Hash order is drawn independently of the arm, so it is noise, not bias.
* **Pairing still worked**, which is the thing worth checking rather than assuming. Measured on
  sweep 1's own arms:
```
        sd(paired diff)   sd if the arms were INDEPENDENT   variance removed by pairing
h5          1.258                   1.902                          56.3%
h12         1.261                   1.909                          56.4%
h20         1.255                   1.924                          57.4%
```
  The seed still fixes the matchup (opponent, deck, levels), which is most of the variance; hash
  order only perturbs fine-grained tie-breaking. So the paired design delivered a genuine 56%
  variance reduction despite the defect.
* **It DOES invalidate the three "IDENTICAL" checks in §1 as reproducible evidence**, including the
  leak probe. They cannot be re-run to the same result today. The leak probe's *conclusion* is still
  supported by construction (the fork is a deepcopy and is never written back), but it is no longer
  backed by a reproducible experiment.

### A worked example of the size of it, from this very ledger
Sweep 1's §5.1 and this sweep's §13 both ran **the identical configuration** — H = 12, K = 4,
N = 1, the same 300 seeds, the same checkpoint — in two different processes:
```
                       winrate   tower delta   paired tower sigma   play->WAIT / WAIT->play
§5.1 (sweep 1)          78.7%      +0.450          +18.81            17344 / 5044
§13 (this sweep)        80.7%      +0.484          +19.91            17220 / 5161
```
**A 2.0pp winrate spread on a supposedly deterministic re-run.** Neither number is wrong; the pair
is the measurement error of a single 300-match arm under randomised hash order, and it is a useful
scale to keep in mind when reading any 300-match difference below ~2pp of winrate as meaningful.
Both agree on everything that matters (tower delta positive, restraint reversal, ~19-20 sigma).

**Fix for anyone re-running this: `PYTHONHASHSEED=0 python rollout_search.py …`.** This sweep did
NOT export it, deliberately — every arm here stays on exactly the same footing as sweep 1's arms and
the shared `rs_base.json`. Adopting the fix means re-running the baseline too.

## 11. ⚠⚠ THE HORIZON CEILING IS H = 12. THE CURVE IS FLAT TO H = 30 AND FALLS AT FULL REMAINDER.

N = 5, K = 4, crown 1.0, n = 300 paired. H = 0.6 is a one-decision-period control; H = FULL rolls to
the end of the match.

```
arm        win%   tower   |  dTOWER   sem   sigma   |  dCROWN  sigma  |  dWIN   sigma
base       37.0  -0.928   |    --                   |                 |
H = 0.6    43.7  -0.865   |  +0.063  0.071  +0.88   |  +0.047  +0.56  |  +6.7   +2.34
H = 3      39.7  -0.722   |  +0.206  0.074  +2.78   |  +0.120  +1.50  |  +2.7   +0.86
H = 5      45.3  -0.590   |  +0.337  0.073  +4.65   |  +0.280  +3.51  |  +8.3   +2.74
H = 8      49.7  -0.459   |  +0.469  0.073  +6.43   |  +0.410  +5.03  | +12.7   +3.97
H = 12     59.0  -0.234   |  +0.694  0.073  +9.53   |  +0.653  +8.07  | +22.0   +7.04
H = 16     58.0  -0.176   |  +0.751  0.069 +10.84   |  +0.647  +8.24  | +21.0   +7.23
H = 20     55.0  -0.239   |  +0.688  0.072  +9.49   |  +0.597  +7.72  | +18.0   +6.17
H = 30     56.7  -0.201   |  +0.727  0.076  +9.54   |  +0.580  +6.94  | +19.7   +6.23
H = FULL   43.0  -0.584   |  +0.343  0.076  +4.53   |  +0.203  +2.37  |  +6.0   +1.93
```

**Head-to-head against H = 12 — this is the test that locates the bend:**
```
H = 16   vs H = 12    +0.057   sem 0.060   +0.95   no difference at 2 sigma
H = 20   vs H = 12    -0.006   sem 0.057   -0.10   no difference at 2 sigma
H = 30   vs H = 12    +0.033   sem 0.065   +0.50   no difference at 2 sigma
H = 16   vs H = 30    +0.025   sem 0.070   +0.35   no difference at 2 sigma
H = FULL vs H = 12    -0.351   sem 0.068   -5.14   ** SIGNIFICANTLY WORSE **
```

**The gains stop at H = 12.** Everything from 12 to 30 is one flat plateau — no pair of them is
separable at 2 sigma, and the nominal best (H = 16, +0.751) is +0.95 sigma over H = 12, i.e. noise.
Rolling to the actual end of the match is not the top of the curve, it is **5.1 sigma below it**.

### The two projections from sweep 1, graded

1. **The linear winrate fit `win = 33.9 + 2.07*H` was right up to H = 12 and then breaks, hard.**
```
H = 12   predicts 58.7%   MEASURED 59.0%    -0.3pp
H = 16   predicts 67.0%   MEASURED 58.0%    -9.0pp
H = 20   predicts 75.3%   MEASURED 55.0%   -20.3pp
H = 30   predicts 96.0%   MEASURED 56.7%   -39.3pp
```
2. **⚠ "Tower delta crosses break-even near H ≈ 16.5 s" is REFUTED.** The slope estimate that
   produced it was right (measured H = 8 -> 12 is +0.056/s against the projected 0.053/s), but the
   slope does not survive past 12: from H = 12 to H = 30 the tower delta moves by +0.033 in TOTAL
   (+0.002/s). **Tower delta never crosses zero as a function of horizon** — it plateaus at about
   -0.20, still a fifth of a tower behind. The only arm in either sweep that ends AHEAD on towers is
   N = 1 (§13), and it gets there by searching more often, not by looking further ahead.

### Why longer is not better — the default rollout policy runs out of validity

The rollout policy is *our side idles, the opponent keeps playing* (§1). That is a survivable
approximation for 12 s and a catastrophic one for 90. The search's own behaviour shows it going
blind, measured on the n = 60 instrumented probes:
```
        margin(best-2nd)   disagrees with policy   search picks WAIT
H = 12       0.197                40.4%                 62.4%
H = 20       0.246                43.2%                 59.7%
H = 30       0.295                41.5%                 63.0%
H = FULL     0.310                35.7%                 73.5%
```
The score margins keep GROWING with horizon (every branch is drifting further from the start) while
the search's ability to find a better action DROPS — at full remainder it disagrees least and falls
back on WAIT most, because a card played now is overwhelmed anyway in a branch where we never play
again. **The horizon ceiling is a property of the rollout policy, not of search.** A non-idling
default policy is the obvious way to push past H = 12 and is untested.

## 12. CANDIDATES K — A NULL. K IS NOT A LEVER, AND K = 8 NEVER BINDS.

H = 12, N = 5, n = 300 paired.
```
arm        win%   tower   |  dTOWER   sem   sigma   |  cards offered / decision
K = 2      60.0  -0.222   |  +0.706  0.073  +9.61   |   1.678
K = 4      59.0  -0.234   |  +0.694  0.073  +9.53   |   2.024
K = 8      59.3  -0.217   |  +0.710  0.077  +9.24   |   2.028
```
```
K = 8 vs K = 4   +0.016  sem 0.055  +0.29   no difference at 2 sigma
K = 2 vs K = 4   +0.012  sem 0.051  +0.23   no difference at 2 sigma
K = 2 vs K = 8   -0.005  sem 0.050  -0.09   no difference at 2 sigma
```

**K = 8 offers 2.028 cards per decision against K = 4's 2.024 — it binds essentially never**, which
confirms §1's claim by direct measurement rather than by the hand-size argument: the hand holds 4
cards and only ~2 are affordable at a mean elixir of 2.7, so **K = 4 already IS "all affordable"** and
K = 8 cannot add a candidate that exists.

The more useful half is the other end: **K = 2 is as good as K = 4** even though it genuinely does
truncate (1.678 cards offered vs 2.024, so the cap is binding ~35% of the time). Cutting the
candidate set costs nothing measurable and saves 11% of wall clock. The search's value is evidently
in *whether to play at all and roughly what*, not in ranking the 3rd-best card.

## 13. ⚠⚠ SEARCH INTERVAL N IS THE REAL LEVER — N = 1 REACHES 80.7% AND A POSITIVE TOWER DELTA

H = 12, K = 4, n = 300 paired. N = 1 searches EVERY decision (every 0.6 s), the strongest version of
this method that exists.
```
arm        win%   tower   |  dTOWER   sem   sigma    |  dCROWN  sigma  |  dWIN   sigma  | searched
base       37.0  -0.928   |    --                    |                 |                |
N = 10     48.0  -0.476   |  +0.451  0.069   +6.52   |  +0.397  +5.19  | +11.0   +3.65  |   5889
N = 5      59.0  -0.234   |  +0.694  0.073   +9.53   |  +0.653  +8.07  | +22.0   +7.04  |  11081
N = 3      57.3  -0.198   |  +0.729  0.073   +9.95   |  +0.613  +7.91  | +20.3   +6.62  |  17478
N = 1      80.7  +0.484   |  +1.412  0.071  +19.91   |  +1.273 +15.71  | +43.7  +14.29  |  54614
```
```
N = 1  vs N = 3    +0.683  sem 0.063  +10.76   ** DIFFERENT **
N = 1  vs N = 5    +0.718  sem 0.062  +11.67   ** DIFFERENT **
N = 10 vs N = 5    -0.243  sem 0.064   -3.82   ** DIFFERENT **
```

**N = 1 doubles the entire effect of the method** (+1.412 vs +0.694 at N = 5) and is the only arm in
either sweep whose tower delta is POSITIVE: this policy, searched every decision, ends matches
**ahead** on towers (+0.484) having started at -0.928, and wins 80.7% against a 37.0% baseline.

Note the shape: N = 10 -> 5 -> 3 is a gentle climb that had already flattened (N=3 vs N=5 is +0.57
sigma, a null), and then N = 1 jumps by a factor of two. **That is not "more search is better" on a
smooth curve — something specific happens at N = 1**, and the behavioural counters say what.

### The restraint reversal is sweep 1's §5.1 — and the N curve says when it switches on

§5.1 already reports the sign flip at N = 1 (search WAITs 82% against the policy's 59%, and
declines every card) and attributes it to INTERLEAVING: at N = 5 the search plays the card the board
needs and then four *unsearched* policy decisions pile on top of it. This sweep's contribution is
the intermediate points, which show the flip is not gradual:
```
        policy WAITs   search WAITs   wait->play   play->wait   ratio   plays/match
N = 10     80.0%          55.3%          2041          584       3.49       39.5
N = 5      82.6%          62.2%          3313         1053       3.15       38.6
N = 3      84.4%          68.9%          4329         1611       2.69       38.1
N = 1      59.9%          82.0%          5161        17220       0.30       32.8
```
**N = 3 still behaves like N = 5 (ratio 2.69, 38.1 plays/match); only N = 1 flips.** That is
consistent with §5.1's interleaving account — one unsearched decision between searched ones is
apparently already enough to produce the pile-on — and it is why the N curve jumps rather than
climbs. An additional mechanism is plausible and NOT tested here: at N = 5 a WAIT commits to doing
nothing for 3.0 s, so WAIT is a more expensive option than at N = 1 where it can be revisited 0.6 s
later.

⚠ Either way the practical consequence is §5.1's: **"search chooses less restraint" is a property
of the search INTERVAL, not of the policy or the deck**, and it must not be carried forward as
evidence about banking. §4q's over-commit story is not refuted by this experiment.

## 14. ⚠ THE MATCH-POSITION CONFOUND — MEASURED, AND THEN DISPOSED OF

The worry: a rollout launched late in a ~180 s match runs past the end, so long horizons increasingly
OBSERVE the terminal outcome rather than predicting it. Three independent measurements.

### 13a. How often a rollout actually reaches the end (instrumented, n = 60 probes)
```
H = 12    9.5% of rollouts reached eng.done
H = 20   14.5%
H = 30   23.6%
H = FULL 100.0%   (by construction)
```
By match position, at H = 12 (per-decision instrumentation):
```
                 decisions   rollouts   reached the end   search disagrees
early  < 60 s        746       2254        0     0.0%          37.3%
mid  60-120 s        595       1706       22     1.3%          32.6%
late  >= 120 s       870       2666      606    22.7%          48.5%
```
**The confound is real but confined: it is a late-match phenomenon and it is zero before 60 s.**

### 13b. Search restricted to ONE phase of the match (n = 300 paired, H = 12, N = 5)
Each arm searches only decisions in its window and plays the policy's greedy action everywhere else.
```
arm             win%   tower   |  dTOWER   sem   sigma   | searched | clamp | gain per 1000 decisions
early  < 60 s   44.0  -0.770   |  +0.158  0.078  +2.03   |   3789   |  0.0% |   +0.0417
mid  60-120 s   39.3  -0.821   |  +0.107  0.070  +1.52   |   2968   |  1.5% |   +0.0360
late  >= 120 s  49.7  -0.565   |  +0.363  0.064  +5.64   |   3731   | 20.4% |   +0.0972
all decisions   59.0  -0.234   |  +0.694  0.073  +9.53   |  11081   |  9.5% |   +0.0626
```
The three phases sum to +0.627 against the all-decisions arm's +0.694, so the effect is close to
additive. **Late decisions carry 52% of the gain from 33% of the searched decisions** — 2.3x more
valuable each — and late is exactly where the clamp lives. That much of the owner's worry is
confirmed.

But the confound cannot be more than a small part of it:
* **Early-phase search, where the clamp rate is measured at exactly 0.0%, still clears the bar on
  its own: +0.158 at 2.03 sigma.** Search with no possibility of seeing the end works.
* Even charging the ENTIRE late-phase gain in proportion to its clamp rate bounds the oracle's
  contribution at 0.204 x 0.363 = **+0.074, about 11% of the +0.694**.
* Late decisions should be worth more anyway, for a reason that has nothing to do with peeking: the
  outcome is scored at match end, so a decision at t = 150 s has less time for its effect to be
  undone than one at t = 20 s.

### 13c. ⚠⚠ THE DECISIVE ONE: the arm that sees the terminal outcome EVERY time is the WORST arm
If observing the true end were what makes search work, **H = FULL — where 100% of rollouts run to the
real result — would be the best arm in the sweep.** It is not:
```
H = FULL  vs  H = 12    -0.351   sem 0.068   -5.14 sigma   SIGNIFICANTLY WORSE
H = FULL  vs  base      +0.343   sem 0.076   +4.53 sigma   (still beats the policy)
```
**That falsifies the end-peeking explanation outright.** Terminal observation is not the mechanism;
going from 9.5% clamp to 100% clamp makes the method worse, not better, because the same change
destroys the rollout policy's validity (§11). The confound is real, bounded at roughly 11% of the
effect, and it is not what the method is running on.

## 15. THE STRONGEST CONFIGURATION AVAILABLE

Sweeping the three knobs independently gives **H = 12, K = 2-4, N = 1**. Horizon is capped by the
rollout policy (§11), K is inert (§12), and N is the whole story (§13).

One knob outside this sweep's brief also stacks, and sweep 1 has since written it up as §5.2:
searching each candidate card at its top-3 masked cells (`--cells 3`) instead of only the policy's
argmax cell is worth **+0.216 tower delta at +4.06 sigma** on top of card search at N = 5. It is
included below because the question here is what the STRONGEST available configuration is, and it
stacks with N = 1.

### The combined arm — everything at once
H = 12, K = 4, N = 1, cells = 3. n = 300 paired, same seeds.
```
arm                                  win%   tower   |  dTOWER   sem   sigma
base                                 37.0  -0.928   |    --
H=12 N=5 K=4 cells=1  (sweep 1)      59.0  -0.234   |  +0.694  0.073   +9.53
H=12 N=5 K=4 cells=3                 62.3  -0.018   |  +0.909  0.074  +12.27
H=12 N=1 K=4 cells=1                 80.7  +0.484   |  +1.412  0.071  +19.91
H=12 N=1 K=4 cells=3   <-- CEILING   85.7  +0.651   |  +1.578  0.076  +20.74
```
```
ceiling vs N=1 cells=1    +0.166  sem 0.056  +2.95   ** DIFFERENT ** (cell search still pays at N=1)
ceiling vs N=5 cells=3    +0.669  sem 0.063 +10.64   ** DIFFERENT **
ceiling vs H=12 N=5       +0.884  sem 0.063 +14.08   ** DIFFERENT **
```

**The strongest configuration measured is H = 12, K = 4, N = 1, cells = 3: 85.7% winrate and a
tower delta of +0.651**, from a policy that alone wins 37.0% at -0.928. The two knobs stack: N = 1
adds +0.718 over N = 5, and cell search adds a further +0.166 on top of N = 1.

It behaves like the N = 1 arm and not like the N = 5 arms — restraint, not volume:
```
plays/match 32.2 (baseline 32.6)   search WAITs 79.4% vs the policy's 62.6% in the same states
rollouts reaching the match end: 10.8%
```

⚠ **N = 1 is the floor of this knob, not a plateau.** Nothing can search more often than every
decision, so this is the ceiling of the METHOD AS DEFINED, not a point where the curve went flat.
The two directions that could still go further are both untested: a non-idling rollout policy
(which is what caps the horizon, §11) and more cells.
⚠ K was swept only at N = 5. K = 2 is as good as K = 4 there and ~10% cheaper, but **K = 2 at
N = 1 is untested**; the ceiling number above uses the measured K = 4.

## 16. ⚠⚠ LIVE SEARCH: THE COMPUTE IS FINE, AND IT IS STILL NOT SHIPPABLE

The five controls that rule out the cheaper explanations for all of the above — force-play, the
gate-threshold scan, the opponent-RNG oracle, perfect observations, and the crown weight — are sweep
1's §6 and are not repeated here. This sweep adds one more, and it is the one that decides whether
any of this can be deployed AS SEARCH.

### 16a. Compute — affordable, confirming the premise
`play.act_period` is 0.6 s. But the budget is NOT 0.6 s: `sim.agent_dt`'s own config note records
**MEASURED live: pipeline 0.37 s**, leaving **~0.23 s of slack** per decision. Against that:
```
measured 7.95 ms/candidate at H = 12 (serial, sweep 1 section 8) x 3.02 candidates = ~24 ms/decision
```
**~24 ms into a ~230 ms hole, ~10x headroom — and that holds at N = 1**, since N only changes how
OFTEN you pay it, not the per-decision cost. Compute is not the blocker.

### 16b. ⚠ Perception — this is the blocker that is measurable, and it is severe
Live search must roll out from the DETECTOR'S board, not ground truth. Probe: at each searched
decision run the search TWICE on the same candidates — once from the true fork, once from a
perturbed fork — with one coherent misperception per decision (common random numbers across
candidates, keyed on `Unit.deploy_seq`). The arm PLAYS the perturbed choice, so the cost is measured
end-to-end, and the agreement rate is recorded.

Perturbations grounded where the project has numbers: `observation.sim_detector_recall` is 0.823
(measured whitelist), so 18% dropout. **⚠ The positional sigma is NOT measured anywhere in this
project — 0.05/0.25/0.5/1.0 tiles are assumptions and are swept, which is why the SHAPE below
matters more than any single row.** HP is not observable live at all
(`use_hp_canvas: false`, and `troop_hp.py` is "a scaffold, NOT wired in").

```
arm                                     win%   tower   | dTOWER  sem   sigma | vs clean H=12
H = 12 clean                            59.0  -0.234   | +0.694 0.073  +9.53 |    --
drop 18% only                           56.7  -0.301   | +0.626 0.072  +8.64 | -0.067  -1.16  n.s.
pos 0.05 tiles only                     49.0  -0.453   | +0.474 0.072  +6.56 | -0.220  -3.64  SIG
pos 0.25 tiles only                     45.3  -0.663   | +0.264 0.072  +3.70 | -0.429  -6.64  SIG
pos 0.50 tiles only                     42.7  -0.658   | +0.269 0.073  +3.68 | -0.424  -7.00  SIG
pos 1.00 tiles only                     43.0  -0.665   | +0.263 0.077  +3.42 | -0.431  -6.59  SIG
drop 18% + pos 0.5 + HP +-25%           43.3  -0.617   | +0.310 0.068  +4.55 | -0.383  -6.21  SIG
```

**Action choice changed on 28.9% of searched decisions** under the combined perturbation (7277 of
10231 decisions kept the same action).

Two things fall out, and the second is the one that matters:
* **Missing 18% of units is survivable** (-1.16 sigma, a null). The rollout re-derives most of what a
  dropped body would have done.
* **Positional error is what breaks it.** The combined arm and the position-only arm are
  indistinguishable (jit vs pos-only: +0.041, +0.65 sigma), so **essentially all of the damage comes
  from position alone.** And the position damage **saturates almost
  immediately**:
```
  perturbation        win%    gain vs base   retains   search picks the SAME action
  none (exact)        59.0       +0.694       100.0%          --
  sigma 0.05 tiles    49.0       +0.474        68.3%         83.7%
  sigma 0.25 tiles    45.3       +0.264        38.1%         73.5%
  sigma 0.50 tiles    42.7       +0.269        38.8%         70.8%
  sigma 1.00 tiles    43.0       +0.263        37.9%         70.5%
```
  **A twentieth of a tile of positional error already costs a third of the gain, and a quarter-tile
  costs 62% — after which more error changes nothing.** This is a threshold, not a gradient: the
  engine's discrete decisions (which target is acquired, what is in range, what a blast covers) flip
  on tiny displacements, and once they flip the branch has decorrelated from the true future.
  The consequence is blunt: **there is no detector accuracy target that recovers this.** Even a
  detector an order of magnitude better than anything measured here gives back only two thirds.

  ⚠ Read this against sweep 1's §6.4, which points the other way and is not in conflict. There,
  handing the POLICY perfect perception bought exactly nothing (+0.25 sigma) — the policy cannot use
  clean input it was not trained on. Here, handing the SEARCH degraded state costs 62% of its gain.
  **Perception is worthless to the policy and load-bearing for the search**, which is precisely why
  search cannot be moved to the live board even though the policy already runs there.

  Note the contrast with §6.3, which is what makes this a real finding rather than "any perturbation
  breaks it": reseeding the opponent's ENTIRE FUTURE costs nothing (-0.95 sigma), while moving units
  a twentieth of a tile costs 3.64 sigma. **The search is robust to uncertainty about the future and
  fragile to error in the present.**

### 16c. ⚠⚠ AND THE HARDER PROBLEM: LIVE CANNOT BUILD THE STATE AT ALL
The jitter number above assumes a live search could construct a `SimEngine` and get the positions
slightly wrong. **It cannot construct one at any accuracy.** Audited across the live path:

* `play.py` **imports nothing from `.sim`** — this is a deliberate documented boundary
  (`env.py:61`, *"so the live path never drags in the sim engine"*). It maintains observation
  tensors, `hand_vec`, own elixir, a threat vector and tower-HP trackers — **no board object**.
* **No detector -> `Unit`/`SimEngine` conversion exists anywhere.** `SimEngine(...)` is constructed
  in exactly one place, `sim/env.py:477`. No `from_detections` / `build_engine` / `hydrate`.
  `sim_view.py` is the opposite direction and says so: *"a DEBUGGER, not a training input."*
* **Per-unit HP is unavailable.** The live `Detection` record has no `hp` field. `read_hp_frac`
  returns a *fraction*, is gated by `use_hp_canvas: false`, and returns 1.0 when no bar is found — so
  it cannot even distinguish "full" from "unreadable". Enemy card LEVELS are unknown, so a fraction
  could not be converted to absolute HP anyway. (Tower HP *is* available — OCR'd absolute — except
  the King, whose HP is never printed.)
* **No opponent model exists.** `make_opponent` never appears in the live path. Opponent elixir has a
  rough estimator; opponent HAND and DECK have nothing at all. `ScriptedBot` needs an 8-card deck,
  per-card levels and a shuffled cycle to run.
* **~80 further per-`Unit` fields are unobservable from pixels**: `target`/`locked`/`aggro_reset`
  (who is committed to whom), `cooldown`/`loaded`/`reload_left` (sub-second attack phase), every
  status timer, plus engine-global `spells`, `projectiles`, `zones`, `_pending`, `_late_spawns`.

**So live search is not a 0.23 s budget problem, it is a state-estimation problem**, and the two hard
blockers (per-unit absolute HP; an opponent deck/hand/level model) are each their own project. Even a
successful reconstruction would start every rollout from a board that is wrong in ways §16b shows the
search is most sensitive to.

## 17. DISTILLATION — THE COST, FROM MEASURED THROUGHPUT

Not built, as instructed; estimated from this sweep's own numbers.

Search at H = 12 / N = 1 produced **54,614 labelled decisions in 2622 s** of wall clock (n = 300,
under ~10x parallel load), i.e. **~1250 labelled decisions per minute per process**. On this 16-core
box, ~20k/min:
```
dataset                       single process      16 processes
100k decisions (~550 matches)      1.3 h              ~5 min
500k decisions (~2700 matches)     6.7 h             ~25 min
1.8M decisions (~10k matches)     24 h               ~1.5 h
```
For scale, `policy_BEST_m18000` is an 18,000-match checkpoint; labelling that many matches with
N = 1 search costs **~30 h single-process, ~2 h on 16 cores**. Against a normal training match at
20-170 ms this is ~60x the environment cost — but it is a ONE-OFF dataset build, not a per-epoch
cost, and 2 hours is nothing next to this project's training runs.

**The teacher is strong enough to be worth cloning: 80.7% winrate and +0.484 tower delta against the
policy's 37.0% and -0.928.** This project already has the machinery (`train_bc`, `replay_bc.py`).

⚠ Two caveats, both untested:
1. **The teacher is PRIVILEGED.** It plans on ground-truth engine state; the student sees the
   detector-limited observation. If the search's edge depends on information the student cannot
   perceive, the student cannot reach it. §16b is the relevant evidence and it is not encouraging in
   one direction (position matters a lot) and encouraging in another (the student only has to
   reproduce the ACTION, never to run rollouts).
2. **Nothing here shows a student can represent the rule.** §13 says much of the gain is fine-grained
   TIMING — hold, hold, hold, play now — which a policy queried every 0.6 s can express in principle,
   but "in principle" is not a measurement.

## 18. COST

**Measured SERIALLY on an otherwise idle box, n = 25 per config, at the end of this sweep:**
```
config                       s/match   ms/candidate   search share   cand/decision
baseline (no search)           1.85         --             --             --
H=12  N=5  K=4                 3.42       11.54          37.2%          2.96
H=12  N=5  K=2                 3.08       10.56          33.9%          2.68
H=12  N=1  K=4                 8.56       11.44          73.3%          2.89
H=12  N=1  K=4  cells=3       12.52       10.61          83.1%          6.30
```
So a **150-match eval costs 8.6 min at N = 5 and 31 min at the ceiling config**; a 300-match eval,
17 min and 63 min.

⚠ Two honesty notes on these numbers:
* This box is **~19% slower today than when sweep 1 §8 was measured** (baseline 1.85 s/match here vs
  §8's 1.56), and per-candidate cost reads 11.5 ms against §8's 7.95 ms. Only ~2 GB of RAM was free.
  Ratios within this table are sound; absolute values should not be compared across sweeps.
* The **300-match arms in §11-§16 were run 6-12 at a time on 16 cores** and their per-match times are
  inflated roughly 1.4-1.7x. They are reported in the arm tables as measured, not corrected.

No arm was dropped for cost. The most expensive single arm was the ceiling config at 4088 s
(68 min) for n = 300; H = FULL, at 2221 s, was run to full n because it is the arm that settles the
confound rather than the arm that wins.

## 19. WHAT TO SHIP — DISTILLATION, NOT LIVE SEARCH

**Recommendation: (b) distillation. Do not build live search.**

The case is not close, and only one of the three reasons is about the numbers in §16b:

1. **Live search cannot be built at all right now (§16c).** The live path deliberately never imports
   the sim; no detector -> `SimEngine` bridge exists; per-unit HP is unavailable and enemy card
   levels are unknown, so it cannot even be inferred; there is no opponent deck/hand/level model;
   and ~80 per-unit fields (aggro locks, cooldowns, status timers, in-flight projectiles) are not
   observable from pixels. Two of those are their own projects, not tickets.
2. **Even if it were built, perception error takes most of the gain, and no detector is good enough
   (§16b).** A quarter-tile position error costs 62% of the search's advantage; the damage saturates
   there, so accuracy improvements do not buy it back. Even a twentieth of a tile — better than
   anything this project has measured — still costs 32%. The search's edge depends on the rollout
   being an EXACT continuation of the present board, which live never is.
3. **Distillation is cheap and the teacher is strong (§17).** ~1250 labelled decisions per minute per
   process, ~20k/min on this box: an 18,000-match-equivalent dataset is ~2 h of wall clock. The
   teacher wins 85.7% against the policy's 37.0%, at +0.651 tower delta against -0.928.

Distillation also dissolves both live blockers at once: the student needs no engine at play time, so
the 0.23 s budget and the state-reconstruction problem simply do not arise. The privileged-teacher
gap (§17 caveat 1) remains the real risk and it is the thing to measure first.

**Suggested first step, one change, measurable:** generate ~100k labelled decisions with
H = 12 / N = 1 / K = 4 / cells = 3 (~5 min on 16 cores), train BC on them with the existing
`train_bc` path, and evaluate the student with the SAME 300 paired seeds and the same bar. The
teacher's +1.578 is the ceiling that student has to be measured against; anything short of it is the
imitation gap, quantified. ⚠ Note the eval must be the 300-seed protocol used here, not
`train_sim_ppo.evaluate()`, which §7b showed is biased low by counting the first 150 matches to
FINISH.

⚠ **What this sweep does NOT show.** Nothing here says the deployed policy can be made to play this
way; a search that wins 85.7% is an upper bound on what a distilled student could reach, not a
prediction. And every number in both sweeps is ONE checkpoint
(`policy_BEST_m18000_20260826`) against the LADDER pool.
