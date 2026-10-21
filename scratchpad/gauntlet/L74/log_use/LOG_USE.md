# LOG_USE -- is every model "trigger happy" with the Log? (owner claim, 10-21)

Owner claim (a hypothesis, tested here): *"every model is trigger happy with the Log: it throws it at virtually every enemy
ground push, and half the time the opponent then punishes with Goblin Barrel / Skeleton Barrel / Dart Goblin because the Log
was wasted. Sometimes holding the Log for a specific enemy card is right."*

Labels: **(a)** measured (numbers given), **(b)** plausible but untested (a measurement is proposed), **(c)** contradicted.

## Verdict in one paragraph

**Partly right; the details are different.** The models do **not** Log more often than pros overall (CLX 1.53 Logs/min, pros
1.55), and opponents do **not** time their bait to our Log being out (at chance level, the same as against pros). What the
models get wrong is **when** they spend it and **what** they spend it on. (1) **Early spending.** In the first 60 s CLX throws
**1.25 Logs vs the pros' 0.94**. In matches where the opponent has a bait card, **pros have spent no Log before the
opponent's first bait card 73% of the time; CLX 56% (live) / 52% (SIM)**. Every Mark since CXII shows this. (2) **Low-value
targets.** 52% of CLX Logs kill less than 1 elixir of units outright, mostly Logs into Valkyrie / Mega Knight / Witch / Hog /
Wizard / Mini PEKKA, which a 429-damage Log cannot kill. (3) **The cost is real.** A bait card played while our Log is out of
hand does **2.3x the tower damage** (283 vs 125 hp; Goblin Barrel 643 vs 245). (4) **The model sees the bait cards** in
`opp_cycle` (checked on all 27 first plays) **but barely reacts to them**: adding a Goblin Barrel to its memory changes P(Log)
by +1.7% (no effect; the sign is even wrong). **Most likely cause:** the reward is win/loss only. A held Log is worth about
150-400 tower hp, and that saving shows up seconds to tens of seconds later, so the learner gets almost no credit for holding
it. Bait decks are also under-represented in training (~23% of matchups vs 42% live). The fix proposed below is a learned
change (more bait decks in training first, then denser reward). The proposed gate metric is the **bait-hold rate**.

## Data and method

- **Live**: `log_use.py` on every main-account icebow log since 10-13 that has board frames: own princess max_hp 4424 (until
  10-19 ~14:00) or 4858 (level-16 towers), deck holds X-Bow + Log. That gives 1,571 matches; CLX = 533 (10-19 00:20 to 10-21
  14:03, ladder + Ranked).
  - Model per match: `card_use.mark_of`. Result: `card_use.results()`, else the end event.
  - Opponent plays come ONLY from `pipeline.public_observation.PublicObserver`, the model's own public detector and the source
    of `opp_cycle`. The opponent's hand, deck and elixir are never read (`opp_elixir_est` / `opponent_elixir_estimate` are
    never touched).
  - Our hand comes from the decision events.
- **Log path**: the card table's rolling box (1.95 tiles half-width + 0.5 body pad, 10.1 tiles reach) moving 177 mt/tick
  (`LOG_HIT_TICKS` 57) from the confirmation tick. A crossed enemy ground body is **killed by the Log** if its hp at the
  crossing is <= **429**, the measured level-16 Log damage (the most common hp drop of crossed bodies: 85 of 124 on the
  10-21 logs).
  - Elixir value = card elixir / bodies. A role-child (max_hp < 45% of its card's biggest) counts 1/3.
  - **Low-value Log** = units crossed, but < 1 elixir killed outright (half the Log's cost).
  - **Chip** = no unit crossed, but the roll reaches an enemy tower.
- **Log-bait cards**:
  - **CORE** = Goblin Barrel, Skeleton Barrel, Dart Goblin, Princess, Goblin Gang (the owner's three + the two other classic
    Log Bait win-condition cards);
  - **EXT** = CORE + Skeleton Army, Goblins, Spear Goblins, Wall Breakers, Rascals, Guards, Firecracker, Goblin Giant,
    Goblin Hut.
- **Bait damage**: every own-tower hp drop between two frames, times the share of that card's bodies among the enemy bodies
  within 9.5 tiles of the tower, summed over the 15 s after the play. It is approximate: a mixed push shares its damage by
  body count.
- **Pros**: `habits/pro_sides.jsonl` = 2,210 Path of Legend sides of the exact icebow8 deck (mirror matches dropped). It has
  the play lists of both seats. It has **no board**, so Log targets cannot be measured for pros.
- **SIM**: W12 eval matches (vs the W7 opponent; `o3_plays` holds both seats' play lists) for CLX and the 6 tn_base seeds +
  4 arms, 3,840 matches each, in `pod_backup_weekend/tonight1020/*/w12_*`. SIM eval logs hold **no per-play board or tower
  hp**, so SIM Log targets and SIM punish damage cannot be measured from them.
- **Play-list metrics** (`playlist.py`, `early.py`) are computed the same way on all three sources. Our hand is rebuilt
  from our play order: a played card is back in hand after 4 more of our plays, so the hand is known after our first Log.

Run: `python log_use.py --out per_match.jsonl` (~40 min at idle priority on the laptop, single thread), then
`python playlist.py --live per_match.jsonl`, `python early.py --live per_match.jsonl`, `python cycle_probe.py --matches 20 --every 2`.

## 1. Live (a)

| Mark | matches | Logs / match | Logs / min | low-value | good (>= 2 elixir killed) | chip | Log back in hand (median) | win |
|---|---|---|---|---|---|---|---|---|
| CXII PLAINIW | 80 | 4.75 | 1.46 | 0.482 | 0.308 | 0.095 | 22.9 s | 0.575 |
| CXXIV LONGER | 304 | 5.03 | 1.44 | 0.451 | 0.340 | 0.080 | 21.1 s | 0.507 |
| CXXXVIII CUES | 271 | 4.94 | 1.45 | 0.469 | 0.333 | 0.093 | 21.1 s | 0.465 |
| CLIII LEVELS | 172 | 4.81 | 1.43 | 0.522 | 0.318 | 0.054 | 20.9 s | 0.477 |
| CLIX PRESS | 104 | 4.88 | 1.47 | 0.484 | 0.327 | 0.079 | 20.4 s | 0.471 |
| **CLX PARITY** | **533** | **5.65 [5.46, 5.86]** | **1.53** | **0.516** | 0.301 | 0.067 | 19.9 s | 0.507 |
| all | 1,571 | 5.18 | 1.48 | 0.488 | 0.319 | 0.077 | 20.6 s | 0.493 |

- No Log was forced by a rule (`lethal_log` never fired). Live decoding still has `log_aim log_barrel` (aim at a visible
  Barrel) and `log_air block` (no air-only Logs).
- **CLX low-value Logs most often crossed** (count of Logs): Valkyrie 166, Mega Knight 135, Witch 116, Hog Rider 102,
  Wizard 96, Mini PEKKA 96, Knight 77, Musketeer 73. These are big units that a 429-damage Log only knocks back.
  - Whether a knock-back Log on a Hog Rider or Mega Knight is a mistake depends on the moment (b). The 52% is an upper bound
    on "wasted", not a count of mistakes.
  - The pros' share cannot be measured (no board in the pro data). The pro re-drive corpus (`ext/corpus_v6`, INVESTMENT.md)
    could give it: a pod job (b).
- **"Virtually every ground push"** (c):
  - of enemy ground-troop plays made while our Log was in hand, the Log actually **rolled over that card within 12 s for
    44.6%** (CLX; all Marks 42.3%; cost <= 3: 37.2%, >= 4: 48.8%);
  - the looser play-list test (any Log within 12 s) gives **CLX 0.681 vs pros 0.630**, so CLX is ~5 pp more reactive than
    pros, but not "every push".
- **Early spending** (a; `early.py`, game clock from battle start):

  | source | Logs in the first 60 s | first 120 s | bait matches: no Log spent before the opponent's first CORE bait card | first bait card at (median) |
  |---|---|---|---|---|
  | **pros** | **0.94** | 1.90 | **0.733** (401) | 16 s |
  | live CXII / CXXIV / CXXXVIII / CLIII / CLIX | 1.41 / 1.30 / 1.25 / 1.25 / 1.24 | 2.30-2.44 | 0.320 / 0.580 / 0.557 / 0.603 / 0.538 | 13-24 s |
  | **live CLX** | **1.25** | 2.32 | **0.559** (222) | 13 s |
  | SIM CLX (W12) | 1.21 | 2.28 | 0.516 (1,218) | 26 s |
  | SIM tn_base s74..s79 | 1.08-1.16 | 2.08-2.21 | 0.521-0.583 | 24-26 s |

  This is the clearest gap to the pros. It is chronic (every Mark), not a recent regression.
- **Bait timing and cost** (a; CLX, CORE cards, our hand known):
  - **Timing.** 1,531 CORE bait plays (2.87 / match), **63.2% with our Log out of hand, while the Log is out 63.8% of all
    decision time**. Opponents do not time bait to our Log; the timing is at chance. The play-list version: CLX 0.666 vs
    0.675; pros 0.583 vs 0.616.
  - **Cost.** Own-tower damage per CORE bait play: **Log out 283 [252, 317], Log in hand 125 [95, 159]**.
    - Goblin Barrel 643 / 245; Skeleton Barrel 323 / 248; Goblin Gang 244 / 36; Dart Goblin 101 / 57; Princess ~0 / 0.
  - **Punishes** (a CORE bait play <= 6 s after one of our Logs): 277 plays, **353 [290, 422] hp each** (Goblin Barrel 724,
    Skeleton Barrel 433, Dart Goblin 133).
  - **Punish rate** (share of our Logs, in CORE-bait matches, followed by a CORE bait play within 6 s): **CLX 20.6%
    [18.5, 23.0]**, CXXIV 16.3%, CXXXVIII 18.3%. The lead's W14 figure is 19.2%. **Pros 29.5% [27.7, 31.2]**: pros are
    "punished" more often by this timing definition. So the owner's "half the time" is (c).
  - **Per match.** CORE-revealed CLX matches (222, 41.7% of matches) lose **1,234 [1,057, 1,418] tower hp per match** to
    CORE bait played while our Log is out. Wins 954 vs losses 1,569 (correlation, not cause).
  - **The model already changes its Logs once bait is revealed** (part of this is because bait decks hold more Log targets):
    after a CORE reveal, low-value Logs are 39.0% vs 59.3% in matches without one, and 48% of the Logs hit a bait card.
- **Win rate**: CLX wins 54.5% of CORE-revealed matches vs 47.9% of the rest. Bait matchups are not CLX's weak spot; they
  were for CXXXVIII (34.1% vs 52.5%).
- Upper bound on the prize (CLX): ~1.7 Log-out CORE bait plays per bait match x (283 - 125) ~ **270 tower hp per bait
  match**, ~5% of a princess tower. It is real but small, which matters for the cause (section 4).

## 2. Pros (a, within the data's limits)

2,210 icebow8 Path of Legend sides:
- 6.23 Logs / match [6.11, 6.35], **1.55 / min**, win 0.471;
- opponent revealed a CORE bait card in 18.1% of matches (live CLX 41.7%: Ranked / ladder at 14k is much baitier);
- bait timing at chance (0.583 Log out vs 0.616 of time);
- punish rate 29.5%;
- a Log within 12 s of an enemy ground-troop play (Log in hand) 0.630;
- **first 60 s 0.94 Logs; Log held until the first bait card 73.3%**.

**What the pro data cannot show:** Log targets (no board), tower damage, and whether a held Log was then used on the bait card
(no board). Pro hands are rebuilt from the play order, the same as for every other source here.

## 3. SIM

**(i) The same metrics on SIM evals (a, play lists only).** W12 vs the W7 opponent: CLX 5.80 Logs / match, 1.62 / min; tn_base
seeds 5.39-5.92; bait timing at chance (CLX 0.691 vs 0.691); punish rate CLX 25.8% [24.9, 26.8], tn_base 25.6-27.9%; hold rate
in the table above. The SIM eval logs (`matches.jsonl`, `--crown-log`) hold no per-play board or tower hp, so **SIM Log
targets and SIM punish damage are unmeasured** (b). The D3 (E4) eval logs hold only our own plays.

**(ii) Training opponents.**
- **Deck exposure (a).** Decks holding a CORE bait card:
  - league census `decks_rl.json` (share/data_20261020 copy) **17.8%** (EXT 34.6%);
  - W7 exploiter `decks_live_train.json` **35.8%** (EXT 62.1%);
  - at the 0.7 / 0.3 split that is **~23% of training matchups**, before PFSP / deck weights, vs **41.7% of live CLX
    matches**. Training sees bait decks about half as often as live does.
- **Punish frequency (c for the exploiter).** Lead W14: bait cards / match and the 6-s punish rate are at parity (live
  19.2%, R6 u20 19.9%, E4 14.6%); here W12 25.8% vs live 20.6%. The W7 opponent punishes at least as often as live
  humans.
- **Gap 1, the census-pool opponent (70% of matchups) (b, untested).** These are snapshots of our own icebow-trained policy
  playing the bait decks. Their punish rate and timing are not in any local log: no eval runs vs league snapshots with
  `o3_plays`. Measurement: one pod eval of CLX vs 3 league snapshots on the CORE-bait decks of `decks_rl.json`, with
  `o3_plays` (480 games, CPU pod).
- **Gap 2, punish cost SIM vs live (b, untested).** Live: 353 hp per punish, 283 vs 125 hp per CORE bait play Log out / in.
  SIM: no per-play tower hp in eval logs. Parity facts on file:
  - the Log meets fight parity (J1 0.971, FIN15.md);
  - Log on packs J2: Royal Hogs 0.67, Barbarians 0.88;
  - Goblin Barrel goblins are a harness set-up gap (in-flight spawns), not an engine law;
  - **no per-card tower-damage parity for Goblin Barrel / Skeleton Barrel / Dart Goblin exists**.

  Measurement: add the own-tower hp delta in the 15 s after each opponent play to the gap.py crown-log record (a few lines),
  re-run one W12 block, and compare to section 1.
- **Does training punish a wasted Log?**
  - In frequency, yes, as often as live, for the 30% exploiter share.
  - In reward, only through the final win / loss (`shaping: none` in tn_base; KL anchor on the card head).
  - Whether the SIM punish is as costly as live is unknown (gap 2).

## 3b. Does the model see the opponent's bait cards, and does it use them? (lead's addition)

`cycle_probe.py`. CLX (`rlarm_stepd_ctrl_nos2_u0130_grafted.pt`, feature_version 6, cue layer) on the 20 newest CLX matches
whose opponent played a Goblin Barrel / Skeleton Barrel / Dart Goblin. The decision inputs are rebuilt exactly as live:
`logframes.full_frames` + `live_gen_v2.GenPilot`, the deployed LIVE_OPTIONS, extrapolate 24, afford 23, identity_ext,
LiveCues.

**(A) opp_cycle is populated correctly (a).**
- All 27 first plays of a probe card in the 20 matches appear at **opp_cycle slot 0, plays_since 0, age 1.3-1.5 s** at the
  first rebuilt decision after the play.
- The age reads 1.2 s high because the inputs are built on the +24-tick look-ahead board. That is consistent with
  training.
- Older cards shift down the list as expected, e.g. `goblin-barrel, goblins, spear-goblins, goblin-gang, bowler,
  dart-goblin`.

**(B) Counterfactual on 1,934 decision states.** States: Log in hand and affordable, an enemy ground troop on our half; every
2nd frame. P(Log) = sigmoid(gate) x softmax(card | affordable)[Log]. P(low Log) = P(Log) x [the Log's argmax cell rolls over
< 1 elixir of bodies it can kill]. Change vs as-is: mean, then the cluster-bootstrap CI by match (states within a match are
correlated, so the match CI is the honest one).

| variant | dP(Log) | match CI | relative | dP(low-value Log) | match CI | relative |
|---|---|---|---|---|---|---|
| as-is | P = 0.2036 | | | P = 0.0674 | | |
| bait cards removed from opp_cycle + opp_past | +0.0187 | [-0.0021, +0.0447] | +9.2% | **+0.0199** | **[+0.0043, +0.0411]** | +29.5% |
| + Goblin Barrel, newest, 3 s ago (cycle only) | +0.0034 | [-0.0059, +0.0130] | +1.7% | +0.0034 | [-0.0021, +0.0103] | +5.1% |
| + Dart Goblin, newest, 3 s ago | +0.0102 | [+0.0012, +0.0178] | +5.0% | +0.0058 | [+0.0016, +0.0108] | +8.6% |
| + Goblin Barrel in opp_cycle AND opp_past (at our princess, 3 s) | +0.0171 | [+0.0021, +0.0333] | +8.4% | +0.0129 | [+0.0052, +0.0239] | +19.2% |
| **+ Goblin Barrel seen 25 s ago, 4 plays since** (run 2) | **+0.0034** | **[-0.0067, +0.0149]** | **+1.7%** | +0.0059 | [+0.0004, +0.0146] | +9.4% |
| **+ Dart Goblin seen 25 s ago, 4 plays since** (run 2) | **+0.0105** | **[+0.0002, +0.0203]** | **+5.3%** | +0.0089 | [+0.0032, +0.0166] | +14.2% |

Run 2 (`--every 4`, 959 states, same 20 matches) adds the two "seen 25 s ago" rows. It reproduces every run-1 row within
0.001 (e.g. + Goblin Barrel 3 s: +0.0035 [-0.0062, +0.0132]; bait removed: dP(low) +0.0213 [+0.0053, +0.0437]).

**Reading (a).**
- The model **sees** the bait cards and reacts **weakly**. With the real bait history removed it would throw ~9% more Logs
  and ~30% more low-value Logs, so the history does reduce low-value Logs a little.
- **Adding** a Goblin Barrel to its memory does nothing measurable (+1.7%, CI spans 0).
- A Dart Goblin or a Barrel in both channels slightly **raises** P(Log). A just-landed Barrel (3 s, at our tower) is a
  correct reason to Log the goblins, so the "recent" inserts mix two signals.
- The clean hold-it test is a Goblin Barrel seen 25 s ago with 4 opponent plays since, so it is probably back in their
  hand. It gives **dP(Log) +1.7% [-3.4%, +7.5%]**. For a Dart Goblin it is **+5.3%** (CI above 0): the wrong direction, and
  low-value Logs go up 9-14%. A model that had learned to hold would show a clearly negative dP(Log) there.
- The model sees the information but has not learned to hold the Log for it. That points back to training never rewarding a
  held Log strongly enough (section 4).

## 4. Cause

| candidate | label | evidence |
|---|---|---|
| reward pays for Log kills | **(c)** | `shaping: none` in tn_base / CLX recipes: the reward is win / loss only |
| training opponent never punishes | **(c)** for frequency (exploiter); **(b)** for the census pool | W14 + W12 punish rate at / above live; census snapshots unmeasured (gap 1) |
| model cannot see revealed cards | **(c)** | (A): opp_cycle correct on 27 / 27; (B): the history reduces low-value Logs ~23%, so the channel is read |
| model sees but does not use them | **(a)** | (B): Goblin Barrel seen 25 s ago (likely back in their hand): dP(Log) +1.7% [-3.4%, +7.5%]; Dart Goblin +5.3% (wrong sign) |
| imitation prior | **(b)**, unlikely the main cause | pros hold the Log early (0.733) and Log only 0.94 times in 60 s; our Marks 1.24-1.41 since CXII, so the deviation is from the pros, not toward them; S1 / pro-imitation checkpoint not measured |
| bait decks under-represented in training | **(a)**, size bounded | ~23% of training matchups vs 41.7% live |
| SIM parity gap (Barrel / Log) | **(b)** | Log J1 0.971 meets; Barrel / Skeleton Barrel / Dart Goblin tower-damage parity never measured (gap 2) |
| **weak credit for holding** | **(b), most likely** | a held Log saves ~150-400 hp per later bait play (section 1), seconds to tens of seconds later, ~270 hp per bait match. A terminal-only reward over a ~3-minute match with tower HP swings of thousands gives that decision almost no gradient, and bait decks are only ~23% of training. Test = E1 / E2 below |

## 5. Proposed fix (learned; not implemented, not trained) and gate metric

Owner rule: no hard-coded habit rules live. Each experiment changes ONE key vs tn_base (seed 74 = the control already on
file), evaluated on the standard gate + the new metric.

- **E1, exposure.** `league_deck_weights` (existing key, the W15 lever-3 mechanism) with weight **2.5** for GoblinBarrel,
  SkeletonBalloon, BlowdartGoblin, Princess, GoblinGang.
  - CORE-bait share rises to ~35% of census and ~58% of exploiter matchups, **~42% overall = the live CLX rate**.
  - The sum: share' = w s / (w s + 1 - s), with s = 0.178 / 0.358.
  - Cheapest change; tests whether more bait games alone teach holding.
- **E2, credit** (only if E1 fails the gate). `shaping: tower` (the existing potential-based Phi_tower, w_tower 0.3). Every
  hp a bait card takes off our tower becomes an immediate, policy-invariant credit at the decisions before it, instead of a
  faint change in P(win). It is generic (not a Log rule), and Ng et al. potential shaping keeps the optimal policy.
- Not proposed: a Log-specific penalty (e.g. "-x per bait hp while the Log is out"). It is closer to a habit rule and would
  teach "never Log". It is kept as a last resort if E1 / E2 both fail.
- Before E1, do the gap-2 measurement (gap.py per-play tower-hp delta, one W12 block). If the SIM Barrel does much less
  damage than live 643 / 724 hp, fix that parity first, because no amount of exposure teaches holding against a harmless
  Barrel.

**Gate metric (SIM, W12 eval vs the W7 opponent, computed from the existing `o3_plays` with `early.py` logic, no new
logging):**
- **G-LOG1 bait-hold rate** = share of CORE-bait matches in which no Log was spent before the opponent's first CORE bait card.
  - CLX 0.516 (n 1,218); tn_base seeds 0.521-0.583 (sd ~0.024); pros 0.733.
  - **PASS: >= 0.60 AND the match-bootstrap CI of (candidate - CLX) has its low end > 0.**
  - Why 0.60: it sits above the best of the 6 current-recipe seeds (0.583), so seed luck cannot pass it. At n ~1,220 bait
    matches per arm the difference's 95% half-width is ~4 pp. It closes ~40% of the pro gap. Long-run target 0.70.
- **G-LOG2 guard against "never Log"**: Logs / min >= 1.3 (pros 1.55, CLX SIM 1.62) and the win-rate gate unchanged. A
  model that simply stops Logging would pass G-LOG1 and fail this.
- **Live review after a deploy** (not pass / fail: live n is small). Over the first ~100 matches compare to CLX:
  - Log-out CORE bait damage per CORE-bait match (CLX 1,234 [1,057, 1,418]);
  - low-value Log share (CLX 0.516);
  - first-60-s Logs (CLX 1.25, pros 0.94).

  `log_use.py --since <deploy>` + `early.py` produce all three.
- Once gap.py logs per-play tower hp, add **G-LOG3 = Log-out CORE bait damage per CORE-bait match in the SIM** (must not
  exceed CLX's).

## Files

- `log_use.py`: live per-Log / per-bait-play extraction and the per-Mark summary (`--from-out` re-summarises).
- `playlist.py`: play-list metrics on pros / SIM / live; training-deck bait shares.
- `early.py`: early-spending and bait-hold metrics (G-LOG1).
- `cycle_probe.py`: (A) opp_cycle check and (B) the counterfactual probe.
- `per_match.jsonl` (1,571 rows) is regenerated by `log_use.py` and is not committed.
