# Training architecture review, 2026-10-13

Sources: the code as it is (pipeline/, the `l74-newsim` branch, live checkpoints read-only) and the measured history in
HANDOFF.md (line refs below). Measured = cited number; plausible = untested; contradicted = evidence against.

## What the pipeline is (as implemented)

- **Model:** GenModel, 1.5-1.8 M weights: 4-layer, 128-wide transformer over up to 64 unit tokens, 144 board patches and
  one global token (hand, deck, cycle, elixir, opponent counter, ability tokens). Heads: play/wait gate, card (4 hand
  slots), cell (2,304 half-tiles), wait-for-card, 7-class value (`model_gen.py:98-250`).
- **Imitation:** 14,661 pro replays re-driven through the real engine: 1.0 M play rows + 2.5 M wait rows. Validation:
  card top-1 .644, cell .198, gate balanced accuracy .743.
- **RL:** PPO, lr 1e-5, 2 epochs; reward +1/-1 at match end only (`rl_royale.py:173`); advantage = result minus the
  mean of the other 3 rollouts of the same matchup. KL leash to a frozen copy of **the run's own init**
  (`rl_royale.py:2151`), not to pro play; beta hits its .03 floor by ~update 10. Opponents (r1): PFSP-hard self-play
  league, styled, 60% unfavourable decks. r1: 60 updates x 256 games, learner wins flat at 30-42% per update.
- **Live decision:** greedy decoding with tau .35/.45/.55, a hazard rule, threatened-tower tau, lethal Rocket/Log,
  Rocket+Tornado value, X-Bow / spell / Log re-aims, dead-lane blocks, a legal-cell guard, a hand-written Hero IW press
  rule, and refine heads grafted on after RL. **None of these run in RL rollouts** (`rl_royale.py:152-170`).

## Where it loses the most (ranked)

### 1. The model is trained as one player and deployed as another (measured, biggest)
Training optimises a sampled policy (T .5, tau .27) with fixed 26-tick latency, level-11 cards, no live rules and (r1)
the NORMAL Ice Wizard. Live plays greedy with different taus, ~10 override rules, the hero form, variable latency and
real levels (Rocket 16, Log 15).
- Training win rate vs init +21 pp, greedy only +4-8 pp (HANDOFF ~4366).
- R3c base without add-ons vs R1e: 542 vs 548 (p .76). The +8.1 pp of stack2k came from add-ons and decode rules,
  not RL (~5979).
- The main live loss mechanism (economy: elixir at big-push start bot 2.2-2.7 vs pros 6.0, ~4913) is **live-only**:
  in the SIM the same model holds 5.2 (~4962).
So RL improves a player that never plays live, and the rules that do play live never get trained.

### 2. Credit assignment does not reach the actual loss mechanism (measured + plausible)
- Losses are mostly economic: 75% of pushes met with < 4 elixir (pros 24%), +17.9 pp lost-episode rate (loss review).
- The reward is one +-1 per match; estimated SNR ~0.2 per update for a 1 pp gate effect; GAE lambda .95 looks ~10 s
  ahead while overspending costs 20-40 s later (~4369).
- RL mostly moves the play/wait gate, and in the wrong direction: P(play) +3.1 pp (~4365).
- The value head is trained but used by nothing at play time.

### 3. The leash is not the pro anchor it was meant to be (contradicted claim)
Design intent (09-05): KL to pro. Code: KL to each run's own init, so the anchor drifts down the lineage (IL -> r3 ->
r3c -> ADAPT -> r1), and with beta at its floor it barely binds. Pro agreement only acts as a hard stop. r1's card
agreement with pros drifted -1.14 pp.

### 4. Evaluation cannot see the effect sizes RL produces (measured)
- 960 SIM pairs resolve +-3.6-3.9 pp; a 150/arm live A/B resolves +-11 pp. Most RL changes measured 1-4 pp, so most
  "nulls" are undecided, not negative.
- The SIM's ranking depends on the opponent pool: LIVECAL found only pool P1 reproduced live orderings, and the
  adaptive league (what r1 trained against) was the worst predictor (~11755).
- Training deck mix was far from the ladder (X-Bow/Mortar 38.4% vs 4.5% live, ~4368).

### 5. Simulator fidelity (background track, measured)
Hero IW pressing explains ~13 of the 17 pp SIM under-rating (IWDIAG3). Own-troop timing 1.18 -> 0.83 tiles (1,367
matches). Card levels are level 11 in the SIM.

### 6. Process
r1 (live A/B arm A) was trained by code that exists only on `l74-newsim`; main cannot reproduce it. Refine heads are
grafted after RL. The one-change rule was waived on most RL rounds (R1, R2l, R3).

## What has worked (measured)
Imitation data scaling (+1.6 pp per corpus doubling; bigger model -1.4 pp: "lever = data"); learner always icebow
(+3.7); evo/hero census + ability presses (R1e +4.35); loss-review decode rules (stack2k +8.1 SIM; 54% live, n 102).

## Proposed order (one change each, each measured)
1. **One decision stack everywhere:** rollouts and screens use the live decoder, live rules, live latency model
   (afford/early-release), hero IW + its press rule, and ladder card levels. First measure the train/deploy gap
   (same checkpoint, plain-sampled vs live-stack, paired). This reverses the 10-11 ruling "training rollouts use the
   plain model" -- owner decision.
2. **Fix the anchor:** KL to the IL (pro) policy instead of the run's init; check pro agreement and live behaviour.
3. **Credit for the economy:** per-decision advantage with a trained value baseline and a horizon that covers 20-40 s,
   judged first on elixir-at-push-start and lost-episode rate, then wins.
4. **Evaluation:** only the LIVECAL-validated pool; enough pairs to resolve +-2 pp (pods are cheap); live A/Bs reserved
   for SIM-positive candidates.
5. **Merge `l74-newsim`** so the model that may go live is reproducible from main.
