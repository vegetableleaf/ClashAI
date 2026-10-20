# W5: X-Bow, Rocket and Tornado decisions in context (owner 10-19; TUESDAY items H, I, I2)

The owner asked for decisions analysed IN CONTEXT, not as matchup-blind averages. Every number below is conditioned on a
situation: the opponent's archetype, what their cycle holds at that moment, the elixir, the crowns. Pros and our models are
measured by the SAME code (`invlib.py`). Labels: **(a)** measured (the number is given), **(b)** plausible but untested
(the measurement that would settle it is named), **(c)** contradicted (the evidence is given).

## Bottom line

1. **The model ignores whether the opponent's X-Bow answer is ready. Pros do not. (a)**
   - "Ready" means: an answer card the opponent has already shown (Earthquake, a tank, Hog, ...) is back in their hand
     (4+ plays since they last played it) and they can afford it.
   - Pros in EQ matchups place 1.61 bridge X-Bows per opportunity-minute when EQ is ready, and 2.46 when it is cycled away.
   - Ours do the opposite: 6.26 when ready, 3.84 when cycled.
   - The information is already in the model's input: `public_observation.opponent_cycle` gives card + plays_since,
     and `model_gen.py:187` reads it. So the gap is in what the training rewards, not in what the model can see.
2. **An X-Bow placed into a ready answer is worth less, in both data sources. (a)**
   - Our live lock rate: 0.494 [0.44, 0.54] when the answer is ready vs 0.706 [0.67, 0.74] when no answer card has been
     seen yet.
   - Pros (re-drive, see Data): 0.302 vs 0.453.
   - Worst cluster, ours: BEATDOWN with the answer ready, lock 0.409 [0.30, 0.52].
3. **What pros play there instead is exactly the owner's turtle + Rocket cycle. (a)** Among their investment plays
   (X-Bows + tower Rockets) in that moment:
   - EQ matchup, EQ ready: pros 55% tower Rocket, ours 4%.
   - HOG matchup, Hog in hand but not affordable: pros 70% tower Rocket, ours 13%.
   - BEATDOWN matchup, answer ready: pros 29% defensive X-Bow + 28% tower Rocket, ours 11% + 7%.
   - Matchup-wide, pros Rocket the tower 2.4-5.4x more per minute (EQ 0.678 vs 0.154, HOG 0.569 vs 0.105).
4. **"A massive waste of elixir" is contradicted in its strong form at our ladder level. (c)**
   - Even into a ready answer, our live bridge X-Bows still gain on average: +0.150 princess-units net over 40 s
     (1.0 = one full princess tower).
   - They also deal 0.17-0.25 reach damage each. A tower Rocket deals ~0.11.
   - The 13k opponents answer worse than the pros' opponents do.
   - The loss is relative: about 21 pp of lock rate, a missing alternative, and no adaptation.
   - Whether switching to Rocket cycling would raise the live WIN rate is **(b) untested**.
5. **The worst matchup is HOG.**
   - (a) Win rate: ours 41.3% [33, 48] (n=138) vs pros 64.0% [57, 70] (n=172).
   - (a) We lose a princess in 60% of HOG matches; pros lose one in 36%.
   - (a) The defensive half of the gap is the Tornado. Against a bridge Hog, with Tornado in hand, >= 3 elixir and both
     princesses up: pros Tornado within 5 s 44.5%, ours 8.7%.
   - (a) That redirects the Hog onto the king: the Hog reached the king 59% of the time when pros Tornadoed, vs 14% when
     they did not.
6. **Tornado toward our king after a princess fell: (a) real, but rare.**
   - It happens 0.091 times per match (72 casts / 787 matches).
   - It is 24% of our post-fall Tornado casts; pros 28%.
   - What followed (association): king HP lost in 10 s 0.187 vs 0.072 for other post-fall casts; own tower HP lost in
     20 s 0.673 vs 0.463.
7. **The SIM reproduces the Tornado redirect, unit by unit. (a) on upstream 0.1.35; fin13 is (b), pod job written.**
   - Each pro "pull toward the king" cast was rebuilt in the SIM from the native engine's exact frame.
   - Per-case agreement on "this unit ended on the king": Hog 0.91 (native 43% vs SIM 46%), Balloon 0.86 (47% vs 61%),
     Mini PEKKA 0.85, Miner 0.90, Giant 0.85, Mega Knight 0.95. King hit: native 29.7% vs SIM 23.2%, agreement 86.2%
     (n=875).
   - The controlled grid shows the mechanism: the pull depends on mass and timing. A Hog cast at the pros' spot
     (8, 24) when it reaches y 21 is pulled onto the king, which activates, and the princess takes 0 damage (no-Tornado
     baseline: 0.73).
   - The same cast at y 17/19, or on Giant / Golem / E-Giant (mass 18-20), does not redirect. Troop-targeters never
     do. In the grid the Balloon did not redirect, but in the rebuilt real cases it did 61% of the time.

## Data

| source | what | n | outcome frames |
|---|---|---|---|
| live CXXXVIII / CLIII / CLIX / CLX | graded ladder matches (`index.json`; CLIX = cue_ab2 u65, CLX = stepd_ctrl_nos2 u130) | 262 / 168 / 104 / 253 = 787 | **real**: reader frames every ~6 ticks (towers, enemy bodies, own X-Bows) |
| pro icebow8 | Path of Legend sides of the exact deck (crawl2 + HF, `habits/pro_sides.jsonl`), mirrors dropped | 1,629 | **native-engine re-drive** of the recorded plays (`ext/corpus_v6/icebow`, level 11, open loop, frames every 20 ticks + every play) |

- **Pro DECISIONS are real** (what, where, when, with which hand and elixir). Hands come from the drive's deal inference.
  **Pro match results are real.**
- **Pro OUTCOMES (lock, damage, X-Bow life) are a counterfactual.** The real game logic replays both sides' recorded plays
  open loop. 76% of these re-drives end with the recorded crowns. Restricting to those changes the pro lock rates by
  <= 0.014 (analyze.out section 7).
- Pro re-drive lock rates sit far below live ones (bridge 0.413 vs 0.650). The cause is (b) untested: stronger opponents
  in the pros' games, level 11, or re-drive drift. Rule used everywhere: **compare decisions across sources; compare
  outcomes only within a source.**
- To settle it: re-drive a sample of OUR live matches in the native sandbox and compare the re-drive's lock rate with
  the real one (a pod job).
- Live clock = game_tick - 78. Positions are in the own frame (own king y 29, river 16, enemy princesses y 6.5).
- **Bridge X-Bow**: placed at y 16-20.5, i.e. rows 18.5 / 19.5, which can reach a princess. **Defensive**: y > 20.5.
  Measured: row 19.5 locks 65% live; rows 21.5 / 22.5 deal 0 reach damage.
- **Lock**: an enemy tower in X-Bow reach (centre to centre <= 13.5 tiles) lost >= 5% of a princess while the X-Bow lived.
- **Opportunity-minute**: a minute with the X-Bow in hand and own elixir >= 6. Propensity = placements per
  opportunity-minute. It is a hazard rate (an eagerness measure) and does not depend on how long matches last.

## Part 1: X-Bow and Rocket in context

### 1.1 What actually neutralised bridge X-Bows (the counter list comes from the data)

`counters.py`: for each opponent card, the bridge X-Bow outcomes when that card was played at the X-Bow, or its body came
within 7 tiles while the X-Bow lived. The card list **K** = cards whose engaged lock rate is >= 10 pp below the source's
base, in BOTH sources, with n >= 20 each:

**K = earthquake, electro_giant, giant, goblinstein, hog_rider, musketeer, pekka, royal_giant**

| card | live: lock when engaged (base 0.65) / died < 10 s | pro re-drive: lock when engaged (base 0.40) / died < 10 s |
|---|---|---|
| earthquake | 0.52 / 0.21 | 0.26 / 0.30 |
| electro_giant | 0.40 / 0.12 | 0.08 / 0.54 |
| royal_giant | 0.54 / 0.11 | 0.13 / 0.53 |
| pekka | 0.35 / 0.16 | 0.22 / 0.17 |
| giant | 0.48 / 0.03 | 0.19 / 0.08 |
| goblinstein | 0.38 / 0.04 | 0.29 / 0.10 |
| hog_rider | 0.51 / 0.11 | 0.28 / 0.17 |
| musketeer | 0.41 / 0.27 | 0.22 / 0.20 |

Lightning (live 0.78) and Inferno Tower (0.58) kill X-Bows fast (died < 10 s: 0.25 / 0.24) but do not stop the lock.
The tank cards neutralise by soaking the X-Bow's shots.

By deck (the matchup level), the bridge X-Bow damage drops most against cycle decks. Average relative damage drop over
the two sources: Earthquake -38%, Mighty Miner -36%, Skeletons -32%, Hog -32%, Ice Golem -31%. These are Hog-EQ / Hog
2.6 / X-Bow-mirror decks.

### 1.2 Matchups (opponent archetype from the cards it revealed by the match end)

Archetype rule, first match wins: EQ > SIEGE (X-Bow / Mortar) > HOG > BEATDOWN (a >= 6-elixir tank, Goblinstein, RG, ...)
> OTHER. `analyze.out` section 1 has the per-Mark table.

| matchup | win: pros | win: ours | bridge X-Bows / min: pro vs ours | tower Rockets / min: pro vs ours | our lock / bridge X-Bow |
|---|---|---|---|---|---|
| EQ | 0.564 (78) | 0.645 (31) | 0.627 vs **1.192** | **0.678 vs 0.154** | 0.619 |
| SIEGE | 0.400 (150) | 0.653 (49) | 0.637 vs 0.930 | 0.312 vs 0.086 | 0.722 |
| HOG | **0.640** (172) | **0.413** (138) | 0.660 vs 0.916 | **0.569 vs 0.105** | 0.554 |
| BEATDOWN | 0.455 (688) | 0.440 (375) | 0.645 vs 0.851 | 0.265 vs 0.109 | 0.651 |
| OTHER | 0.494 (541) | 0.619 (194) | 0.743 vs 0.981 | 0.367 vs 0.126 | 0.703 |

Win rates are not level-matched: pros play top Path of Legend, we play 13k ladder. HOG is the only matchup where pros
clearly do better than us. There we lose a princess in 60.1% of matches vs 36.0% for pros (real final crowns,
`matchup_crowns.out`).

### 1.3 Decision clusters: matchup x the opponent's answer state at that moment

`analyze.out` sections 2, 3, 8, 9; per-Mark rows in section 2b. CIs are match-bootstrap 95%.

| cluster | bridge X-Bows / opp-min: pro | ours | ratio | our lock | pro lock (re-drive) | investment shares, pro: bridge / def / tower Rocket | ours |
|---|---|---|---|---|---|---|---|
| EQ / ready | 1.61 [1.20, 2.00] | 6.26 [4.97, 7.92] | x3.89 | 0.507 [0.40, 0.63] | 0.337 | 0.39 / 0.06 / **0.55** | 0.87 / 0.09 / 0.04 |
| EQ / cycled | 2.46 [1.86, 3.06] | 3.84 [2.77, 5.33] | x1.56 | 0.653 | 0.320 | 0.51 / 0.06 / 0.43 | 0.83 / 0.03 / 0.14 |
| HOG / ready | 2.55 [2.12, 2.98] | 4.84 [4.01, 5.91] | x1.90 | 0.534 [0.44, 0.62] | 0.346 | 0.46 / 0.15 / 0.39 | 0.83 / 0.10 / 0.07 |
| HOG / short | 1.21 [0.67, 1.75] | 4.53 [2.90, 6.29] | x3.73 | 0.615 | 0.500 | 0.22 / 0.08 / **0.70** | 0.74 / 0.13 / 0.13 |
| HOG / cycled | 2.09 [1.79, 2.44] | 3.34 [2.97, 3.82] | x1.60 | 0.530 [0.46, 0.61] | 0.311 | 0.48 / 0.15 / 0.37 | 0.78 / 0.14 / 0.08 |
| BEATDOWN / ready | 2.29 [1.99, 2.64] | 4.32 [3.41, 5.32] | x1.88 | **0.409** [0.30, 0.52] | 0.270 | 0.44 / **0.29** / 0.28 | 0.82 / 0.11 / 0.07 |
| BEATDOWN / cycled | 2.77 [2.48, 3.06] | 4.49 [3.90, 5.11] | x1.62 | 0.668 | 0.394 | 0.55 / 0.23 / 0.22 | 0.77 / 0.18 / 0.05 |
| BEATDOWN / unrevealed | 2.49 [2.30, 2.69] | 3.39 [3.18, 3.66] | x1.36 | 0.699 | 0.489 | 0.62 / 0.20 / 0.19 | 0.70 / 0.19 / 0.11 |
| OTHER / unrevealed | 2.96 [2.76, 3.15] | 3.58 [3.25, 3.91] | x1.21 | 0.703 | 0.459 | 0.56 / 0.18 / 0.26 | 0.74 / 0.16 / 0.10 |

- ready = a K card in their hand and affordable; short = in hand, not affordable; cycled = every revealed K card is in
  their queue; unrevealed = no K card seen yet.
- Pros time their X-Bows to the answer. Within EQ and BEATDOWN they place fewer when it is ready (EQ 1.61 vs 2.46;
  BEATDOWN 2.29 vs 2.77). In the HOG matchup, when the Hog is in hand but not affordable, they Rocket instead (70%).
- Ours are flat or reversed (EQ 6.26 ready vs 3.84 cycled).
- Our X-Bows lose value when the answer is ready: pooled over matchups, lock 0.494 vs 0.706 unrevealed / 0.614 cycled.
  The pro re-drive moves the same way (0.302 / 0.453 / 0.363). That consistency makes the context effect robust, even
  though the absolute lock levels differ between sources.

### 1.4 Top 3 sunk-cost clusters (low X-Bow value AND far more placements than pros in the same context)

`sunk.out` ranks every cluster by excess failed X-Bows per 100 of our matches. Its top entry, BEATDOWN / unrevealed, has
lock 0.699: that is eagerness, not sunk cost. The three below are the clusters whose X-Bows are worth least:

1. **BEATDOWN, answer (tank) ready.**
   - Ours 4.32 vs pros 2.29 placements per opportunity-minute (x1.88).
   - Our lock 0.409 [0.30, 0.52], vs 0.668 / 0.699 in the same matchup when the answer is cycled / unrevealed.
   - Net over 20 s +0.129 vs +0.288 / +0.297.
   - CLX alone: lock 0.390, net +0.062 (n=41).
   - **Pros:** 29% defensive X-Bow + 28% tower Rocket. **Ours:** 11% + 7%.
2. **EQ, Earthquake ready.**
   - Ours 6.26 vs 1.61 (x3.89, the largest ratio of any cluster). CLX alone: 10.08 per opportunity-minute, lock 0.35
     (n=20).
   - Lock 0.507 [0.40, 0.63] and net20 +0.077, the lowest net of any of our clusters.
   - **Pros:** 55% tower Rocket, 2.25 tower Rockets per opportunity-minute. **Ours:** 4%, 0.27 per opportunity-minute.
3. **HOG, Hog in hand (ready / short) or cycled.**
   - Ours x1.60-x3.73 the pro rate. Lock 0.53-0.62, vs 0.70 when the Hog is not yet seen.
   - The worst matchup by result: 41.3% vs 64.0%.
   - In our HOG matches, 2+ failed bridge X-Bows go with a 27% win rate (n=51), vs 51% with none (n=49). Association
     only: a losing match also produces failures.
   - **Pros:** 37-70% tower Rocket here. Rocket-cycle rate 0.418 / min vs ours 0.082.

**After a failed bridge X-Bow** (analyze.out section 4):
- Our next X-Bow is a bridge X-Bow again 67.6% of the time; pros 63.7%. So "keeps re-trying the X-Bow" is **(c) not
  larger than pros** as a re-try rate.
- The difference is the follow-up. Within 30 s of a failure, pros Rocket the tower 21.3% of the time, ours 6.2%
  (HOG 29.5% vs 4.4%, EQ 30.6% vs 12.8%).
- The sunk cost is the missing Rocket cycle, not more X-Bow re-tries.

### 1.5 Verdicts on the owner's 10-19 statement

| claim | verdict |
|---|---|
| the model keeps trying offensive X-Bows in matchups that hard-counter them | **(a)**: ours 1.3-1.9x the pro bridge rate per minute in every matchup; x1.7-x3.9 in the answer-ready clusters, where pros cut back (EQ, BEATDOWN) or switch to Rockets (HOG) |
| those matchups "always" hard-counter the X-Bow | **(c)** at 13k: our worst-cluster lock is 0.41, not ~0; no matchup archetype is below 0.55 |
| it is a massive waste of elixir / sunk cost | **(c)** in the strong form: average net stays positive in every cluster (+0.08..+0.35 over 20 s). **(a)** in the relative form: -21 pp lock, x2-4 the placements, and the Rocket alternative pros take 39-70% of the time is missing |
| it should turtle with defensive X-Bows and Rocket-cycle | **(a)** that is what pros do in these exact contexts (shares above). That it would WIN more for us at 13k is **(b)**: our X-Bows still out-damage a Rocket there (0.17-0.25 vs 0.11). Settle it with a SIM arm whose opponents answer like live, then a live A/B |

## Part 2: Tornado

### 2.1 (a) Enemy bridge attacker, both princesses up, our Tornado in hand, >= 3 elixir (`tornado.out`)

| attacker | group | n | Tornado within 5 s | first card | own princess HP lost in 15 s | Hog itself onto our king |
|---|---|---|---|---|---|---|
| Hog | pros | 838 | **0.445** | Tesla 0.19, **Tornado 0.18**, IW 0.17 | 0.085 | 0.59 with Tornado / 0.14 without |
| Hog | ours | 437 | **0.087** | Tesla 0.31, Knight 0.18, IW 0.16 | 0.104 | 0.18 / 0.04 |
| Hog, exactly 3-4 elixir (the owner's case) | pros | 92 | - | **Tornado 0.25**, IW 0.17 | - | - |
| | ours | 65 | - | Tesla 0.34, Knight 0.20, Log 0.15, IW 0.12, **Tornado 0.03** | - | - |
| other building-targeters | pros / ours | 2147 / 704 | 0.177 / 0.054 | | 0.095 / 0.091 | |

Per Mark, Tornado vs a bridge Hog: CXXXVIII 0.080, CLIII 0.106, CLIX 0.094, CLX 0.083.

**The owner's IW-instead-of-Tornado case is real (a). IW is not even our most common answer:** with exactly 3-4 elixir
we open with Tesla (0.34) or Knight (0.20), and Tornado almost never (0.03).

Outcomes by our first card vs a Hog (own princess HP lost in 15 s, live):

| our first card | princess HP lost |
|---|---|
| Tesla | 0.055 |
| Skeletons | 0.073 |
| IW | 0.118 |
| Log | 0.154 |
| Knight | 0.175 |

Pros' Tornado-first lost 0.064 (re-drive). So Tesla already protects the princess as well as a Tornado does. Tornado's
extra is that it costs 3 instead of 4 and pulls the Hog onto the king.

**Where pros cast it:** the modal spot vs a left-lane Hog is (8, 24), 198 of 403 casts, about 4 s after the Hog appears.
Casts 4-6 tiles from our king hit the king 91% of the time.

**Live rule check (I):** no decode rule holds Tornado back. Card choice is the model's argmax over affordable cards
(`decision_options.choose_slot`). The only masks are X-Bow dead lane, Rocket dead target and Log air. Of 1,124 live
Tornado plays, 1,123 were the model's own choice (`why=None`); 1 came from the rocket_tornado combo. `tornado_river`
changes only the look-ahead pull model.

**King activation by itself is not a goal:**
- In our matches, the king being hit while both princesses stand goes with a 25.1% win rate vs 58.7% (`king_act.out`).
  Attackers that reach the king un-redirected are a sign of losing.
- Pros show +14 pp (56.4% vs 42.5%).
- So reward princess HP kept, as the owner specified. Do not reward king activation.

### 2.2 (b) Tornado toward our king after >= 1 own princess fell

"Toward the king" here: the cast is on average > 1 tile nearer our king than the enemy bodies in its radius.

| group | post-fall casts with enemies in radius | toward the king | per match | king HP lost in 10 s: toward vs other | own tower HP lost in 20 s: toward vs other | win: toward vs other |
|---|---|---|---|---|---|---|
| ours | 294 | 72 (0.24) | 0.091 | **0.187 vs 0.072** | **0.673 vs 0.463** | 0.125 vs 0.104 |
| CXXXVIII / CLIII / CLIX / CLX | | 30 / 15 / 9 / 18 | 0.115 / 0.089 / 0.087 / 0.071 | | | |
| pros | 107 | 30 (0.28) | 0.018 | 0.086 vs 0.046 | 0.365 vs 0.360 | |

- **(a)** The owner's observation holds. It occurs in all four Marks and is followed by about 2.6x the king damage.
- It is rare: 72 casts in 787 matches. And by then the match is mostly lost (P(win | lost the first princess) is 1-4%
  for us).
- Most pulled: Witch, Hog, Balloon, Elixir Golem, Goblin Barrel, Mega Knight.
- The I2 penalty is cheap to add but has a small ceiling: about 9% of matches have such a cast.
- Causal direction **(b)**: the pull may come because the enemy is already on the king side.

### 2.3 SIM check: does the Tornado pull units onto the king and activate it as the real engine does?

**Grid** (`sim_tornado.py`, laptop, upstream royalesim **0.1.35**, both sides level 16, no defenders): a unit dropped at
the left bridge, one Tornado at spot P when the unit reaches y 17 / 19 / 21. Full table: `sim_tornado_v35.table`.

- Hog: cast at (8, 24) or (7, 26) at y 21: pulled onto the king, targets it, king active about 6 s later, princess loss
  **0.00** (baseline 0.73).
- The same casts at y 17 / 19: the Hog is outside the 5.5-tile radius, so no redirect.
- Royal Hogs (mass 2): at (8, 24) / y 21 they retarget the king and the princess loss falls 0.70 -> 0.39.
- Giant / Golem / E-Giant / Goblin Giant (mass 18-20) are pulled about 1 tile and never redirected. Neither were
  Balloon, Ram Rider or Battle Ram at these spots and timings.
- Troop-targeters (Knight, Valkyrie, Mini PEKKA, Prince, P.E.K.K.A, Mega Knight) never take the king in this
  defender-free grid.
- Musketeer / Wizard / Royal Giant stop at range before y 19, so only the y-17 cast applies to them.

**Per-instance parity** (`sim_replay.py`, the stronger test): the 909 pro casts (both princesses up, king untouched,
pull toward the king) were rebuilt in the SIM from the native engine's exact frame at the cast. Bodies and hp come from
that frame, then the same Tornado at the same spot, run for 10 s. 34 cases were refused (bodies standing on the river).

| unit | n | native: onto the king | SIM: onto the king | per-case agreement |
|---|---|---|---|---|
| Balloon | 95 | 0.47 | 0.61 | 0.86 |
| Miner | 42 | 0.76 | 0.86 | 0.90 |
| Hog | 35 | 0.43 | 0.46 | 0.91 |
| Skeleton Barrel | 30 | 0.00 | 0.23 | 0.77 |
| Mini PEKKA | 27 | 0.56 | 0.63 | 0.85 |
| Giant | 20 | 0.10 | 0.15 | 0.85 |
| Mega Knight | 19 | 0.21 | 0.26 | 0.95 |
| king hit (any unit) | 875 | 0.297 | 0.232 | 0.862 |

- **(a)** on 0.1.35, the SIM gets the redirect right case by case 85-91% of the time for the units that matter.
- It over-predicts "onto the king" for air units (Balloon +14 pp, Skeleton Barrel +23 pp).
- It under-predicts the king hit (-6.5 pp). Part of that is the replica: multi-body cards (Skeletons, Goblins, Royal
  Hogs, Barbarians) and buildings are not spawned.
- In the defender-free grid the Balloon was never redirected. In the real cases it was, 61% of the time: real states
  differ from the grid in timing and position, which is why the per-instance test is the one to trust.
- **fin13 (the training SIM) is (b) untested.** `sim_tornado_pod.sh` runs both checks on fin13 under `/workspace/cpu.lock`
  (one process each). It was not run, because the pods are reserved until ~06:00 and the lead must approve their use.
- Comparison with live: of our live pulls toward the king with both princesses up, the Hog reached the king in 0.70 of
  cases (n=20); the pro native rate is 0.44. Live per-instance replay is not done yet: the cached live frames lack our
  own troops (follow-up below).

## Proposals: learned fixes, ranked (one change per experiment; nothing hard-coded for live)

1. **Eval slices per cluster first (cheap; all later arms need them).** For every SIM eval and the live monitor,
   per Mark:
   - bridge X-Bows per opportunity-minute by answer context. Targets are pros' context RATIOS, not averages:
     ready / cycled ~0.65 in EQ, ~0.83 in BEATDOWN;
   - the tower-Rocket share of investment plays in EQ / ready and HOG / short (pros 0.55 / 0.70);
   - the defensive share in BEATDOWN / ready (pros 0.29);
   - after a failed bridge X-Bow, the tower-Rocket rate within 30 s (pros 0.21);
   - Tornado within 5 s of a bridge Hog with Tornado in hand, both princesses up (pros 0.445, ours 0.087);
   - the HOG-matchup princess-loss rate (ours 0.60).
   - The SIM half needs gap.py `--record-plays` extended with opponent plays + tower HP per X-Bow life. Today's SIM
     records have own plays and final towers only, so **whether the SIM shows the -21 pp ready penalty at all is (b)
     untested**, and it is the first thing to measure.
2. **Opponent-model requirements (lever B, ahead of any reward).** The model already sees the opponent's cycle. It
   ignores it because, as far as we know, SIM opponents do not punish an X-Bow placed into a ready answer. The fitted
   live-opponent policy must:
   - hold answer cards and play them on X-Bows at the measured engagement rates (`counters.out`: EQ, tank, Hog at the
     X-Bow);
   - reproduce the X-Bow value drop by context (live lock 0.49 ready vs 0.71 unrevealed);
   - reproduce the HOG matchup's princess pressure (we lose a princess in 60% of HOG matches).
   - Gate a candidate opponent model on these slices, not on win % alone.
3. **Scenario curricula (on the CLX recipe, one arm each).**
   - C-ANSWER: starts from live-like states with a K card in the opponent's hand and affordable (EQ / tank / Hog), the
     X-Bow and Rocket in our hand. The policy meets the decision pros resolve with Rocket / defensive X-Bow.
   - C-TORNADO: a bridge attacker of many types (Hog, Royal Hogs, Balloon, Miner, Mini PEKKA, Giant, Musketeer, Valkyrie)
     with Tornado in hand and both princesses up. The SIM reproduces which units redirect (2.3), so the policy can learn
     unit identity x timing. The opp_cycle / unit identity inputs exist already; add explicit mass / range / sight
     features only if the curriculum arm shows it cannot separate the units.
4. **Reward I (owner's redirect-to-king), after 1-3.** Potential Phi = -w x own princess HP lost, active only while both
   princesses stand; no king term.
   - Supported: the SIM redirect agrees with native in 85-91% of cases (0.1.35; confirm fin13 first with the pod job).
   - Supported: Tesla and Tornado protect the princess about equally (0.055 vs 0.064), so the term mainly pays the
     3-elixir option.
   - **Do not reward king activation** (2.1).
5. **Reward I2 (penalise post-princess-loss pulls toward our king).** A penalty on our Tornado casts whose net pull is
   toward our king while >= 1 own princess is down. Measured volume is 0.091 per match, so the expected gain is small.
   Run it only as one arm after I, guarded by the post-fall Tornado slice.
6. **Not proposed:**
   - fitting the policy to pro averages (the owner's rule);
   - a reward that pays Rocket cycling directly. At 13k our X-Bows into answers still out-damage a Rocket (0.17-0.25 vs
     0.11), so paying Rockets would push the policy toward pro behaviour our opponents do not demand. The SIM opponent
     (2) should create that pressure if it is real.

## Follow-ups (measurements owed)

- fin13 Tornado checks: `POD=<id> bash sim_tornado_pod.sh` (lead approval; about 1-3 min CPU, single process).
- Re-drive fidelity: native re-drive of ~100 of OUR live matches, then compare its X-Bow lock with the real frames. This
  calibrates every pro-outcome number here.
- SIM X-Bow context slice: does the SIM show the -21 pp ready penalty (proposal 1)?
- Live per-instance Tornado replay: needs our own troops from the raw live frames (`livelog.read`; the habits cache drops
  them).

## Files (all in `scratchpad/gauntlet/L74/investment/`)

| file | what |
|---|---|
| `build_live.py` -> `index.json`, `build_live.out` | index + cache (L74/habits/cache) of the 787 live matches |
| `invlib.py` | the shared extractor (live + pro loaders, X-Bow / Rocket / opportunity / bridge-attacker / Tornado rows) |
| `extract_all.py` -> `rows.pkl` (38 MB, not committed; ~2 min to rebuild) | all rows |
| `counters.py` -> `counters.out`, `counters_raw.json` | the data-derived answer list K |
| `analyze.py` -> `analyze.out`, `clusters.json` | Part 1 tables, sections 1-11 |
| `sunk.py` -> `sunk.out`; `matchup_crowns.py` -> `matchup_crowns.out` | sunk-cost ranking; real-crown matchup stats |
| `tornado.py` -> `tornado.out`; `king_act.py` -> `king_act.out` | Part 2 (a) (b) |
| `sim_tornado.py`, `sim_tornado_table.py` -> `sim_tornado_v35.*` | SIM grid |
| `sim_replay.py` -> `sim_replay_cases.json`, `sim_replay_v35.*` | per-instance SIM vs native |
| `sim_tornado_pod.sh` | the fin13 pod job (not run) |
| `test_invlib.py` | self-check of the cycle / placement rules |

Rerun: `python build_live.py && python extract_all.py && python counters.py && python analyze.py && python tornado.py &&
python sunk.py && python matchup_crowns.py && python king_act.py`. Every step is a single process, so the laptop is safe.
