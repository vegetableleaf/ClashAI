# Shadow engine -- full game state for live play from on-screen events only (design, L68, 2026-09-24)

Owner request (2026-09-24): give the live model the real game state -- units, positions, exact HP, status effects
(charge, stun/freeze, rage/slow), targeting, predicted futures -- instead of computer-vision guesses, with the
opponent's hand masked. Constraint (lead): NO reading of the live client's memory/process and no injection; every input
must come from what is on the screen. This design gets the state by re-simulating the match locally.

## Why it is worth building (measured, HANDOFF §AR / §BC)
- Clean observations take the live deploy rule from 52% to 92% vs held-out ghosts (+40 pp); opponent elixir alone is
  +16 to +26 pp; the live detector's missing values (unit HP, exact/opp elixir, king HP), not its noise, drove the live
  placement collapse (§5cs.98). A shadow engine supplies exactly those values, in the format the model trained on
  (`obs_contract.from_engine` on an engine state = the training distribution, not `from_live`).

## Mechanism
The engine is deterministic: the same deploys at the same ticks give byte-identical states (corpus parity 20/20,
§AQ; RoyaleSim hashes every tick). So a match's full state is a function of (decks, levels, deploy events). The live
bot already knows its OWN deploys exactly (it issues the taps: card, cell, time). Only the OPPONENT's deploys must be
detected from the screen -- one event per play (placement animation, elixir drop), far easier than tracking every unit
through a fight.

```
screen frames --> [A] opponent deploy detector ---\
bot's own taps (exact) ---------------------------+--> [B] lockstep shadow engine --> [D] BoardState (from_engine,
                                                  |        (K branches)                  opp hand masked, opp elixir exact)
screen frames --> [C] re-sync observer -----------/            ^                           |
  (tower HP digits, unit positions, elixir bar, timer)          +--- predicted futures <----+ (step a snapshot forward)
```

A. Opponent deploy detector: from the existing YOLO detector + a deploy-onset classifier (new unit with the deploying
   flag / spell effect appearing in the opponent's territory or anywhere for spells). Output: (card, cell, tick
   estimate with an uncertainty). Card identity is taken from the deck once revealed (8 cards max), so the classifier
   picks among <= 8 known + unrevealed cards.
B. Lockstep engine: RoyaleSim in-process (fast, ~0.1 s per match of engine time, snapshot/branch in 12 kB) or the
   sandbox real engine (exact game code, no snapshot, heavier: an Android emulator next to Google Play Games). Keep K
   branches over the uncertain tick/cell of the latest opponent deploy; prune branches that disagree with [C].
C. Re-sync: every frame compare the shadow state with what the screen shows -- tower HP (digit CNN), unit presence and
   positions (detector), elixir bar, match timer -- score branches, correct slow drift (kill shadow units unseen for N
   frames, re-seat tower HP).
D. Output: `from_engine(shadow_state)` with the opponent's hand/next removed, opp elixir computed from the opponent's
   deploy history (exact if every opponent deploy is caught), plus optional look-ahead features from stepping a copy.

## Unknowns, and the experiments that settle them (cheapest first; none needs the live client)
- S1 DRIFT TOLERANCE (offline, CPU-light): take driven corpus replays, perturb the opponent's deploys with realistic
  noise (tick jitter 0/2/5/10/20, cell jitter 0/0.5/1 tile, 0-5% missed deploys), re-drive, and measure divergence from
  the true run over time: unit position error, HP error, target agreement, tower HP, and the S1 model's decision
  agreement on the two states. Both engines. This sets the accuracy bar for [A]. Owner rule: run only when the laptop
  is free, or on the VM.
- S2 DEPLOY DETECTION ACCURACY: on existing recorded live sessions, the bot's OWN taps are ground truth for timing and
  cell; measure the detector's deploy-onset latency and cell error on own units, as a proxy for opponent deploys.
- S3 RANDOMNESS: confirm which mechanics (if any) draw from a per-match RNG seed the live match does not reveal; any such
  mechanic diverges in the shadow and must be re-synced from the screen.
- S4 LEVELS / FORMS: friendly-battle levels and evolution/hero forms must match the engine's (sandbox: all forms except
  evolved Elite Barbarians; RoyaleSim: no forms yet).
- S5 LATENCY: the shadow must stay ahead of the 0.5 s decision cadence while Google Play Games runs on the same box.

## Out of scope (deliberately)
Reading or injecting into the Google Play Games / Clash Royale client in any form.
