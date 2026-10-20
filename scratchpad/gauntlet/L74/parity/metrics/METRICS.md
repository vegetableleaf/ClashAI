# SIM parity metric suite, engine part J1-J8 + J-ALL-CARDS (W1, 2026-10-20)

Owner 10-19: fight parity alone does not establish SIM parity, because other mechanics can change the game state while each
fight still agrees. The goal is **>= 95% on every metric**, and for ALL cards, not only icebow's. This file covers the engine
metrics J1-J8 (plan1019/TUESDAY.md item J). J9-J11 (behaviour, predictive) belong to W3.

Every number below carries its label: **(a) measured** (with n), **(b) plausible but untested**, **(c) contradicted**.

## 0. Current values (all (a) measured)

Runtimes:
- **J1** is the fork (fin14c, FIN13).
- **Every other replay number** is the upstream royalesim **0.1.36** laptop wheel. It has the same card table and
  overrides as the fork, but not the fork's 20 measured laws and no tower troops. The pod job in section 6 re-measures
  them on the fork.
- **Levels** are read off the live bodies, which includes the 10-19+ level-16 matches.

| metric | one-line definition | value [95% CI] | n | ceiling | gap to 0.95 (point) |
|---|---|---|---|---|---|
| J7b crown sequence | same ordered tower falls in an open-loop whole-match replay | **0.444** [0.246, 0.663] | 18 matches | 0.958 | **-0.51** |
| J7d king wake (whole match) | same king wake tick (±5 s) or neither wakes | 0.639 | 36 king-sides | 1.000 | -0.31 |
| J7 result | same crowns per side at the replay's end | 0.444 [0.246, 0.663] | 18 | 0.958 | -0.51 |
| J8 tiebreak end tick | SIM tiebreak drain ends within 5 ticks of live | 0.783 (54/69) | 69 matches | 1 | -0.17 |
| J6 river crossing, all | same lane, crossing within 10 ticks (one-sided crossing fails) | 0.637 [0.565, 0.711] | 796 bodies / 53 matches | 0.978 | -0.31 |
| J6 pathing proper | the same, both bodies alive at the crossing, not at the window edge | 0.791 [0.726, 0.851] | 597 | 0.980 | -0.16 |
| J4 own elixir, open loop | own elixir within 0.1 on every live frame, 3 min + overtime | 0.820 [0.806, 0.834] | 1,207 matches (all frames) | 1 | -0.13 |
| J4 own elixir, re-synced per play | the same, the SIM set to live after each deduction | 0.982 [0.975, 0.989] | 302 matches | 1 | meets |
| J7a tower hp per minute | every tower's hp within max(300, 10%) at each minute | 0.872 [0.814, 0.930] | 18 matches | 0.998 | -0.08 |
| J2 spell effect | affected body's end point within 0.5 tile at the window's end | 0.907 [0.874, 0.935] | 685 bodies / 53 matches | 0.994 | -0.04 |
| J2 Tornado only | the same, Tornado casts | 0.787 [0.681, 0.881] | 122 | 1.000 | -0.16 |
| J1 fight (FIN13, fork) | tolerant card-level fight outcome | 0.926 [0.920, 0.932] | 13,049 fights / 403 matches | 0.992 | -0.02 |
| J3a king activation | trigger within ±10 ticks or neither (positives + risky negatives) | 0.956 [0.933, 0.978] | 435 side-windows / 53 matches | 0.997 | point meets; lower CI 0.933 < 0.95 |
| J3a positives only | windows holding a live trigger | 0.894 [0.833, 0.947] | 180 | 0.993 | -0.06 |
| J3a wake law given the SIM's trigger | SIM wake = its own trigger + 71 (±2) | 82/82 = 1.000 | 82 | 1 | meets |
| J5a deploy duration | first seen -> active within 3 ticks | 0.984 [0.962, 0.996] | 4,555 bodies | - | meets |
| J5b card cycle (FIFO) | the entering card is the one played 4 plays earlier | 0.986 [0.980, 0.990] | 42,714 plays / 1,425 matches | 1 | meets |
| J8 regulation winner | SIM winner from the live tower hp at 3590 | 0.993 (289/291) | 291 | 1 | meets |
| J8 tiebreak winner | SIM winner after the drain from the live tower hp at 5990 | 0.986 (68/69) | 69 | 1 | meets |
| static, device table | SIM table = the device's own tables (10-12), every record | 524 / 526 records equal | 206 card + 320 unit records | - | 2 mismatches |
| static, live hp at observed level | live (card, level, max_hp) = a SIM unit hp | 768 / 791 triples (99.83% of body-frames) | 166 cards, levels 10-17 | - | 0 confirmed; 6 unmapped |

**Reading.**
- The fight-level and law-level metrics are near or above 0.95: J1, J3 wake law, J5, J8 winner, static.
- The **compounding** metrics are far below it: J7 crown sequence, J6 crossings, J4 open loop. These are exactly what
  the owner said fight parity hides, and the owner's claim is confirmed (a). A 0.926 fight parity still gives the same crown sequence
  in only 8 of 18 recorded matches replayed open loop.
- The J7 ceiling is 0.958 with deploy-tick jitter only. That makes the 0.444 an engine / harness gap, not chaos
  (play-point jitter would lower the ceiling: (b), see the ceiling caveat in J7).

## 1. What "parity %" means (one rule for every metric)

- **Item.** Each metric grades one kind of item:
  - J1: a fight. J2: a body inside a spell's reach. J3: a king side-window. J4: a live frame.
  - J5: a body (deploy) or a play (cycle). J6: a body that crosses the river. J7: a match. J8: a match end.
- **Agreement.** Live and SIM agree on an item when they match within the metric's tolerance τ. Each tolerance is stated
  below, and each is set at about one reader quantum or one game "unit" (0.5 tile, 10 ticks, one X-Bow bolt).
- **Raw parity** is the share of items that agree.
  - Its 95% CI comes from a bootstrap that resamples **matches**, because items in one match share hidden state
    (`replay_metrics.boot`, as `fights.boot_ci`, 2,000 draws).
  - Where n is a handful of matches (J7), the CI is a Wilson interval instead.
- **Noise ceiling**, where chaos applies (J1, J2, J3, J6, J7).
  - It is the same agreement computed between the SIM replay as built and each of K SIM replays with the unobservable
    state redrawn. This is fights.py's `perturb` + `jitter_tick` (CEILING.md section 2): attack phase, ambiguous
    targets, Tesla state, shields, and the deploy tick inside its frame gap.
  - The perturbed replays use the same engine, so the ceiling is the engine's own sensitivity to what the reader cannot
    see.
  - **Normalised = raw / ceiling.**
- **Deterministic metrics have a ceiling of 1 by construction.** These are J4 elixir, J5b cycle, J8 law probes and the
  static check. The live value there is exact, or its quantum is inside τ.
- **Goal.** Raw lower 95% CI >= 0.95 for every metric. The same test applies per card with n >= 30 (the owner's per-card
  n, fight-parity-goal).
  - Normalised is reported beside raw. It is not the goal, because raw cannot exceed the ceiling by much (CEILING.md).
  - J1 keeps its own stricter owner goal (raw 0.975 overall / 0.95 per card).
- **Per card (J-ALL-CARDS).** Every item is attributed to a card label (`own`/`opp` + name + form):
  - J1: the anchor play. J2: the victim. J3: the activator in the king's reach. J4/J5: the played card.
  - J6: the crossing body. J7: every card present in the match (a weak, many-to-one attribution).
  - J8 is match-level, so it has no card attribution.
  - Coverage = whether a card has n >= 30 graded items (COVERAGE.md).

## 2. Definitions

Data:
- **Frame logs** are `scratchpad/gauntlet/L68/live_reader/live_play_*.jsonl` (frames every ~2 ticks since 10-15).
- **Ext logs** are the same logs with reader state / projectile / fx rows (10-16 on). They are the graded cohort here:
  1,102 ext matches out of 1,207 frame-logged matches.
- **Phase-3 captures** (`icebow/data/p3_captures`) are read by fights.py where present.
- Laptop runs use the upstream royalesim **0.1.36** Windows wheel (`PARITY_SIM_PATH`), because the fork has no Windows
  build. Its card values are byte-identical to the fork's: same table sha `153019dd`, same 11 overrides. It **lacks the
  fork's 20 measured laws** (Tesla hide, buff pulses, Evo Knight, dash / uppercut, ...) **and tower troops**
  (`set_tower_troops`). Fork numbers need the pod job (section 6).

### J1 fight parity (existing; CEILING.md, fights.py)
- **Item.** One fight per play: the SIM is rebuilt from the live board at the frame before the play, every live
  deployment inside 12 s is replayed, and the result is the play's card view.
- **Agreement.**
  - Bodies: death ticks match in order within 10 ticks, with a swarm slack of 10%.
  - Tower damage: within max(100 hp, 10%).
- **Ceiling.** K = 8 perturbed replays.
- **Current value.** FIN13 upgraded (stamped), fork fin14c: **raw 0.926 [0.920, 0.932]**, n = 13,049 fights, 403 matches.
  Ceiling 0.992, normalised 0.933 (R7_SUMMARY).
- **Per card.** It already exists (coverage.py: tier B 0.278 of live plays on MEETS cards).

### J2 spell mechanics: spell effect on bodies (new: `replay_metrics.py fights`, `j2`)
- **Item.** A (spell cast, enemy non-tower body inside the spell's reach at the cast frame) pair, for both sides' casts.
  - Ext logs date the cast tick and point: fights.py `seen_casts`.
  - Reach is the spell's area radius + 0.5 tile, or a rolling spell's box (Log, Barbarian Barrel: the table's
    projectile range x radius + 0.5 tile).
- **Window W.**
  - An area spell: the area's life, clamped to 20..80 ticks (Tornado 21, Freeze 70, Poison 80).
  - A rolling spell: 30 ticks.
  - An impact spell: 20 ticks, so knockback settles.
- **Agreement.** The body's end point at cast + W is within **0.5 tile** (500 mt) of the paired SIM body, and both are alive.
  - When both are dead, the pair is excluded from the displacement subset and scored as agreeing in "all".
  - When only one side has the body, it fails.
- **What it covers.**
  - Tornado pull, which depends on unit mass.
  - Log / Barbarian Barrel / Snowball / Fireball / Rocket knockback.
  - Freeze / Zap stun: a stunned body does not move.
  - Ice Wizard slows inside a spell window, by their effect on movement.
  - The damage and kill part of spells is J1's spell card view (bodies hit / killed by the spell, crown damage).
- **Slices.** By spell, and Tornado by victim mass (card table `mass`).
- **Ceiling.** K perturbed replays: the nearest same-card body in each one.

### J3 tower mechanics
- **J3a king activation (new: `j3`).**
  - **Live signal.** The king's reader kind goes 12 -> 13 on the tick it is awake. The trigger (a princess falls, or the
    king takes damage) comes **70 ticks before** that (measured: see results).
  - **SIM signal.** `king_active` flips 71 ticks after the trigger (`king_activate_time_ms` 3550; probe: princess down on
    tick 210, `king_wake_ms` counts 0..3550, awake on tick 281).
  - **Item.** A (fight window, side) pair where the king is asleep at t0 in both runs. Positives: the live trigger lies in
    the window. Risky negatives: no live trigger, but an enemy came within 9 tiles of the king. Up to 6 windows per
    trigger; as many negatives as positives.
  - **Agreement.** Both triggers within **±10 ticks**, or neither triggers. A trigger too close to the window end to see
    its wake is not judged.
  - **Ceiling.** K perturbed replays.
  - **Static part.** The wake delay, live vs SIM.
  - **Per card.** The activator is the enemy card in king reach (7 + 1.4 tiles) at the trigger tick of a damage trigger.
    This is the Tornado-to-king case (reward-redirect-to-king).
- **J3b tower targeting (defined, not measured).**
  - **Item.** Every live crown-tower shot on an ext log: proj row, source = tower, target body.
  - **Agreement.** The SIM tower's next shot after the same tick targets the paired body.
  - It needs the SIM projectile rows in the replay rows: a pod extension.
- **J3c tower damage per hit.**
  - **Static.** Tower damage at levels 11-16 in the table = the device table: equal.
  - **Live per-hit drops.** These are part of J1 tower damage.
  - The level-16 tower **hp** is checked against live (static check, below).

### J4 elixir economy (new: `replay_metrics.py elixir`, `j4`)
- **Item.** Every live frame's **own** elixir. The reader's own-elixir value is exact to 1e-4. Opponent elixir is never
  read (owner rule).
- **Replay (open loop).**
  - A SIM battle starts on the first live frame's tick, with the live elixir.
  - At every live elixir drop of >= 0.5, the SIM's mana is reduced by the played card's table cost (Hero Ice Wizard
    ability: 2). The drop is matched to the confirmed play / press within 6 ticks.
  - Nothing else is played, so towers and units cannot interfere.
  - This isolates regeneration, the 2x (tick 2400) / overtime (3600) / 3x (4800) switches and the cap.
  - The deduction timing (tap -> registration, ~24 ticks) is J5c's.
- **Agreement.** |SIM - live| <= **0.1 elixir** (about 3 ticks of 2x regen) on the frame.
- **Slices.** Per phase, plus the regen slope live vs SIM.

### J5 deploy / spawn timing and card cycle
- **J5a deploy duration.**
  - **Measured on.** Every body born inside a replayed fight (fights.py `measure`: first seen -> first active, live vs
    SIM).
  - **Agreement.** Within 3 ticks.
- **J5b own card cycle (new: `j5_cycle`, live-only law check).**
  - **SIM law.** FIFO: the played card goes to the back of a 4-card queue.
  - **Test.** From the 5th play on, the card that **enters** the hand must be the card played 4 plays earlier.
- **J5c tap -> registration delay (defined, not graded here).** This is the live input pipeline (fights.py measures it
  per match: `spell_delay_ticks`). It is not an engine law, so it is not a SIM-parity item. The SIM replays at the
  registration tick.

### J6 macro pathing: river crossings (new: `j6`)
- **Item.** Every body that crosses the river toward the enemy in live or in the paired SIM, inside a replayed fight:
  from below y 14.5 to past 17.5 tiles, in its own forward frame.
- **Agreement.** The same lane (board half) and the crossing tick within **10 ticks**. A crossing on one side only fails.
- **Ceiling.** The same SIM body (uid) in each perturbed replay.
- **Retarget choices.** These are J1 (target picks); diag map "target picks 61".

### J7 whole-match open-loop replay (new: `replay_metrics.py whole`, `j7`)
- **Replay.** One fights.py replay per match, from the first frame (full towers, empty board) to the last frame before
  tick 6000.
  - Every recorded play of both sides is replayed at its live tick and point, with nothing reset in between.
  - Divergence compounds by design.
- **Graded quantities.**
  1. **Tower-HP trajectory.** At each whole minute (1200-tick marks), every tower's hp agrees within max(300, 10% of its
     max hp).
  2. **Crown sequence.** The ordered list of tower falls is identical, and each fall is within 200 ticks (10 s).
  3. **Result.** Crowns per side at the replay's end.
  4. **King activation.** The wake tick agrees within 5 s (100 ticks), or neither king wakes.
- **Normalisation.** The same quantities SIM vs SIM over K = 8 perturbed replays (deploy ticks redrawn in their frame
  gaps; the t0 board is empty, so no other hidden state is drawn).
- **Ceiling caveat (b).** Play points are not jittered, so this ceiling is an upper bound. A wider perturbation
  (play-point noise) would lower it and raise the normalised scores.

### J8 match-end resolution (new: `j8_end`; regulation / tiebreak law probes on live tower hp)
- **Classes.** Each live match is classed by its tower falls: regulation end, overtime sudden death, overtime tiebreak,
  early 3 crowns.
  - The live end event trails the real end by 81 ticks: regulation ends read 3681.
- **Probe.**
  - Regulation and tiebreak: a SIM battle is reset from the live tower hp at tick 3590 / 5990 with no units, and run to
    its own end.
  - **Agreement.** The same winner, and for the tiebreak, the end tick within 5 ticks of live.
  - Overtime sudden death needs the plays, so it is J7's.

### Static stat check (J-ALL-CARDS b; new: `static_check.py`)
- **Inputs.** The SIM card table as the runtime loads it (embedded `cards-160402017-20261006` + calibration
  `card_value_overrides`) is compared against three sources:
  1. **DEVICE.** The game's own tables pulled from the device on 10-12 (apktables device build, private, gitignored),
     for every card / evolution / hero form / unit.
  2. **LIVE.** Every (card, level, max_hp) the reader saw on ext logs, at the observed level, including 16.
  3. **WIKI.** cards_stats.json, fandom level-11 vardefines fetched 2026-08-26.
- **Fields.** hp, damage, hit speed, first hit (load time), range, min range, sight, mass, speed, deploy time, collision
  radius, count, shield, plus every spell / projectile hop stat apktables compares.
- **Level scaling.** At level 16 = floor(base x ladder[15] / 100) on each table's own ladder. Equal base + equal ladder
  means an equal level-16 value.

## 3. Measured details per metric

All runs are laptop runs, one process. Raw outputs are in `parity/output/metrics/` (gitignored): census.json, static.json,
j23b/ (J2/J3/J6/J5a), j7b/ (J7), elixir_all/ + elixir_resync/ (J4), laws_all/ (J5b/J8), *.log.

### J2 spell effect (53 matches, stride 20 over 10-16..10-19, K = 4)
- **By spell**, agree (n bodies):
  - Log 0.932 (353); Tornado 0.787 (122); Fireball 1.000 (43); Zap 0.943 (35); Rocket 0.857 (21).
  - Snowball 1.000 (16); Rage 0.933 (15); Arrows 1.000 (11); Clone 0.636 (11); Barbarian Barrel 1.000 (11).
  - Lightning 1.000 (10); Freeze 1.000 (10); Poison 0.889 (9). Other spells have n < 9.
  - Ceilings are 0.98-1.0 for all of them, so the misses are engine / harness, not noise.
- **Tornado by victim mass** (live census: 6,678 Tornado exposures, 6,436 by our Tornado):
  - Mass 2 (Minion Horde, Royal Hogs, Hero Goblins) agrees on **4 of 13**. The live median pull is 1,808 mt against
    1,412 in the SIM: **the SIM pulls these light units about 22% less** (a, small n; the cause is untested (b)).
  - Mass 4 agrees 0.71 (31): Elite Barbarians, Night Witch, Hog Rider.
  - Mass 5-6: 0.84-0.92. Mass 18 (Mega Knight, Electro Giant, Giant Skeleton, P.E.K.K.A): 0.91 (23).
  - Buildings: not pulled in either run, 5/5.
  - Hog Rider (the owner's Tornado-to-king case) is 0.73 (11) as a J2 victim overall.
- **Fork comparison.** R7_SUMMARY says the fork's Rocket and Tornado flight / pull models "match live" on the J1 card
  view. J2 is a stricter end-point test on the upstream wheel, so the fork number is owed (pod job).

### J3a king activation (same 53 matches)
- **Live law (census, 1,578 king wakes on 1,207 matches).**
  - Princess down -> king awake: 70 ticks in 1,026 of 1,249 cases, and 69-71 ticks in 1,227 (98.2%).
  - King first damaged -> awake: 69-71 ticks in 250 of 253.
  - The SIM's wake is 71 ticks (3550 ms). It agrees within the frame quantum (±1 tick sampling: (b) whether the true
    delay is 70 or 71).
- **Triggers seen live.**
  - Princess falls: 1,250. King damage: 253, of which 212 are on our king.
  - 123 of those 212 had our own Tornado in the 4 s before. This is the Tornado-to-king trick, with live activators
    Goblin Barrel goblins 61, Hog Rider 38, Royal Hogs 6, Elixir Golem 5, Mega Knight 5.
  - 74 wakes are "other": all but a few at t > 6,000, the tiebreak drain.
- **Replay.**
  - All windows: 0.956 [0.933, 0.978]. Positives: 0.894. Negatives: 255 / 255.
  - Princess-fall triggers 0.838 (80); damage triggers 0.667 (18); damage after our own Tornado 0.769 (13).
- **Decomposition.**
  - The wake law given the SIM's own trigger is exact: 82/82.
  - Of the 16 live-only wakes, the SIM princess did not fall in 13 and the SIM king was not hit in any.
  - So **every J3 miss is an upstream tower-damage / fight difference, not the activation law** (a).
  - Sim-only wakes: 0.

### J4 own elixir (1,207 matches, every frame)
- **Open loop.** Per phase: 1x 0.897; 2x 0.728; overtime 2x 0.697; 3x 0.621. All frames: 0.820.
- **Re-synced at every deduction** (302 matches): 1x 0.985; 2x 0.982; overtime 2x 0.991; 3x 0.918. All frames: 0.982.
- **Mechanism (a).** The live game accrues a whole number of 1/10,000 elixir per tick:
  - Live elixir is 6 + 0.0178 x tick. At tick 150 the reader reads 8.67 exactly, against 8.678 in the SIM.
  - The live slopes are 0.0178 / 0.0357 / 0.0537 per tick for 1x / 2x / 3x, which is floor(500,000 / regen_ms) / 10,000.
  - The SIM accrues the exact rational: 1/56 = 0.017857 per tick at 1x.
  - So **the SIM is 0.32% fast at 1x**: +0.0057 elixir per 100 ticks, until the cap re-syncs it. On
    `20261019_200142` the open-loop drift is +0.098 at 3:00 and +0.135 at the match's end.
- **Deductions.** 530 of 42,438 drops (1.2%) matched no confirmed play / press (b: what these drops are is untested).
  The deduction amounts equal the table cost: drop minus cost is -0.0 / -0.1 (the regen inside the gap).
- **Untested (b).** The 3x re-synced score of 0.918: a 3x switch tick off by a few ticks, or close plays.

### J5
- **J5a deploy duration.** 0.984 over 4,555 bodies. Two failure modes:
  - **Clone copies (a): 0 / 60.** Live copies sit 9-10 ticks deploying; the SIM's are deployed at once
    (`clone_copy_deploy: Deployed`). Whether a live copy can act during those 10 ticks is untested (b).
  - Miner (7 of 7 off): a harness artefact of the tunnelling rows (b).
- **J5b cycle FIFO.** 0.986 over 42,714 plays. The 1.4% misses are hand changes the reader shows in an order other than
  FIFO (examples in laws.log). This is untested as a game law vs a reader lag (b).

### J6 river crossings (53 matches)
- **Totals.** 507 agree. Failures: 106 sim-only crossings, 93 live-only, 68 ticks off, 22 unpaired.
- **Pathing proper.** 199 of the 796 items are survival differences (one body died before the crossing: J1) or
  window-edge crossings. Removing them gives 0.791 (597).
- **Worst cards** (pathing proper, n >= 10):
  - opp Tombstone skeletons 0.27 (15); opp Witch evo skeletons 0.61 (23); own Knight 0.65 (46); own Evo Knight 0.67 (12).
  - Skeleton Army 0.79 (48); own Skeletons 0.80 (94); own Hero Ice Wizard 0.83 (41).
  - These are the defender-retarget / spawned-child cases. The lead (b): whether a body keeps a target past the bridge
    or walks on.
- **Timing.** Median |dt| = 0 when both cross: the walk speed is exact. The misses are **whether** a body crosses, and
  **which lane**.

### J7 whole-match open loop (18 matches, 10-18..10-19, stride 35, K = 8)
- **Trajectory.** Tower hp per minute 0.872.
- **Crown sequence.** 8 / 18 identical, against 7.7 / 8 SIM-vs-SIM.
- **First divergence.** This is the first frame where a tower differs beyond max(300, 10%).
  - On the 10 failing matches the median is 1,307 ticks (65 s), and 6 of 10 are before 1,350.
  - On that first frame past the 300-hp tolerance the difference is already 482-1,206 hp. That is consistent with one
    push dealing a different tower damage, not slow drift (b: the per-push cause is untested).
  - So J7 is driven by J1's tower-damage term in single pushes. The plays in the 12 s before each divergence are listed
    in j7b/matches.
- **Tower troops.** Present in 2 of the 18 matches (Duchess L16, Duchess L14); both agree. So the 0.1.36 wheel's
  missing tower troops do not explain the 10 failures (a).

### J8 (1,425 matches with an end)
- **Classes.** Regulation 291, overtime sudden death 250, early 3 crowns 72, tiebreak 69.
- **Winner.** The probe winner agrees 357 / 360. Two of the misses are regulation matches whose deciding tower fell
  between 3,590 and 3,600, after the probe's snapshot (a harness artefact, (b)).
- **Tiebreak end tick.** SIM - live is +2 ticks in 52 of 69, +3..+12 in 9, and +21..+68 in 8. The tail is the SIM's
  hp-drain law on some tower-hp combinations (b).

## 4. J-ALL-CARDS: coverage and static check

**Coverage** (COVERAGE.md, generated):
- **Records.** 206 SIM card records: 145 cards + 43 evolutions + 18 hero forms.
- **Verdict** on ext-log plays (n >= 30 per card): **159 covered**, 15 thin (10-29), **11 need battles** (< 10),
  21 event-only (Super / Chess / party modes).
- **Needs battles (0-9 graded plays).** Goblin Drill evo, Little Prince, Spirit Empress (both forms), Ice Spirit evo,
  Hero Barbarian Barrel, Hero Electro Wizard, Goblin Barrel evo, Minion Giant, Snowball evo, Zap evo.
- **Thin.** Ghost / Baby Dragon / Minion Horde / Electro Giant / Elite Barbarians / Goblin Giant / Furnace / Goblin Cage /
  Hunter / Bomber evos, Mirror, Barbarian Hut, Void, Rune Giant, Spirit Empress mounted.
- **Battles.** About 80 card-battles over 26 cards. That is about 10-12 owner-played classic battles with decks built
  from those cards, at ~6 plays per card per battle (a guess to calibrate on the first battles).
- **Per metric.** The coverage columns carry each metric's own n (J2 Tornado exposures, J3 activators, J5 deploy
  bodies, J6 crossings). The per-card replay values are the second table in COVERAGE.md.
- **Thinnest per-card evidence.** J3 activators (only 25 cards were ever in king reach at a damage trigger) and Tornado
  victims by mass class.

**Static check** (`static_check.py`; static.json):
- **DEVICE vs SIM.** 524 of 526 records equal (204 / 206 cards + evo + hero, 320 / 320 units) on every field: hp,
  damage, hit speed, load time, range, min range, **sight**, **mass**, speed, deploy time, radius, count, shield, spell /
  projectile hops, level ladders. Level-16 values are therefore equal. The table already equals the device, so the 11
  calibration overrides change nothing measurable here. The mismatches:
  1. **Hero Electro Wizard**: `crown_tower_damage_percent` 100 in the SIM vs 0 on the device (a, a table field). Its
     game effect is untested (b).
  2. **Evo Electro Giant**: `evo_delevel_pulse.hit_speed_ms` 50 in the SIM, absent on the device. The SIM fills a field
     the device leaves to a default (b).
- **LIVE vs SIM** (hp at the observed level, 791 (card, level, max_hp) triples, 166 cards, levels 10-17, 22.98 M
  body-frames):
  - 768 exact. This includes every king / princess at 11-16, 215 of the 222 level-16 triples (the 7 others are in the
    23 below), and the hero ice cube (104 x ladder).
  - Tower troops fit by ratio (±3 hp): Dagger Duchess 14 / 15 / 16, Cannoneer 14 / 15 / 16, Royal Chef 11-16. The exact
    probe needs the fork's `set_tower_troops`.
  - The 23 that do not match:
    - 12 are card-less reader rows near tower slots (221-1,006 hp, one -1). These are the rows fights.py already
      excludes from towers ((b): the census does not apply that slot filter).
    - 5 are Clone copies (1 hp: the SIM's `clone_hitpoints` 1, a false positive of the check).
  - **6 are unmapped (b):** Skeleton King 1-hp bodies, Mirror bodies at level 17 (355 / 1,260 hp), Hero Tombstone
    7,425 hp at 17, Hero Balloon 832 hp at 17. The SIM does support level 17 (Knight 3,105, ...), but these labels'
    units are not in the check.
  - **0 confirmed hp mismatches.**
- **WIKI vs SIM.** 97 field disagreements on 69 cards, and on **every one the SIM equals the device table**. Example:
  Wizard damage at level 11 is 304 in SIM and device and 281 on the wiki, which is the pre-balance value. **The 08-26
  wiki cache is contradicted as a truth source (c)**; the device table is the reference. Refetching the wiki is not
  needed for the stat check.
- **Not covered by static.** Behaviour laws (first-hit timing, pull law, retargets) are replay metrics, not table values.
  The device pull is 10-12, so a balance change after that needs a fresh pull (`apktables/pull_device_update.sh`; it
  needs MuMu / adb, so it is the owner's or lead's call).

## 5. RANKED GAP LIST (biggest first; the mechanism, then the proposed fix order)

| rank | metric | value | gap | likely mechanism | label |
|---|---|---|---|---|---|
| 1 | J7b crown sequence / result | 0.444 | -0.51 | A first tower divergence of 482-1,206 hp, at a median of 65 s, from push-level tower-damage differences (J1's tower term). The open loop then never re-converges. | (a) first-divergence data; per-push cause (b) |
| 2 | J6 crossings (all) | 0.637 | -0.31 | 2/3 survival differences (J1), 1/3 whether / which lane a defender or child crosses (Tombstone / Witch skeletons, own Knight / Skeletons) | (a) split; retarget cause (b) |
| 3 | J7d king wake in whole matches | 0.639 | -0.31 | Downstream of rank 1: the wake law itself is exact (82/82) | (a) |
| 4 | J8 tiebreak end tick | 0.783 | -0.17 | SIM drain law: +2 ticks on 52 of 69, +3..+12 on 9, +21..+68 on 8 | (a) offset; tail cause (b) |
| 5 | J2 Tornado | 0.787 | -0.16 | Light units (mass 2) pulled ~22% less in the SIM; mass 4 0.71 | (a) n = 13 / 31; law (b) |
| 6 | J4 elixir open loop | 0.820 | -0.13 | SIM regen is the exact rational; the client truncates per tick to 1e-4 elixir (1x 0.32% fast) | (a) |
| 7 | J3a positives | 0.894 | -0.06 | Upstream princess-fall timing (J1 tower damage), not the activation law | (a) |
| 8 | J7a tower hp per minute | 0.872 | -0.08 | Same as rank 1 | (a) |
| 9 | J2 all spells | 0.907 | -0.04 | Tornado (rank 5), Clone (0.64, n 11), Rocket (0.86, n 21) | (a) small n |
| 10 | J1 fight | 0.926 | -0.02 (owner goal 0.975: -0.05) | Gap map: timing 162 / movement 86 / target picks 61 / setup 43 (R7) | (a) |
| 11 | J5a Clone copy deploy | 0 / 60 | (card) | SIM copies deploy instantly; live copies show 9-10 ticks deploying | (a) rows; effect (b) |
| - | J3 wake law, J5a, J5b, J8 winner, static | >= 0.98 | meet | - | (a) |

**Fix order** (biggest lever first; one change per experiment; S = fork law, H = harness):
1. **J7 / J1 tower damage per push.**
   - Run the pod job to get the fork numbers. Then for each J7 first divergence, take the J1 card view of that fight in
     FIN13 and label it H / S / U.
   - This is the highest-value parity work. It also moves J3, J6 and J7a.
2. **S-ELIXIR-TRUNC.** Regen per tick = floor(500,000 / regen_ms) / 10,000 elixir. A one-line law; measured exactly.
   Expected: J4 open loop 0.82 -> ~0.98 (the re-synced score), at no risk to fights.
3. **J6 crossing / retarget census on the fork.** Find whether the SIM's own Knight / Skeletons cross where live ones
   stop (target kept vs dropped at the bridge). Then a targeted law A/B.
4. **J2 Tornado vs mass.** Re-measure on the fork first: its pull law already matches J1. If mass 2 / 4 still fail,
   probe the attract law (`attract_base: BaseSpeed`, `attract_onset`) against the 6,678 live exposures (pull vs mass vs
   distance from the centre).
5. **J8 drain law.** Fit the drain against the 69 tiebreak matches (hp, end tick).
6. **S-CLONE-DEPLOY** (10-tick copy deploy), after checking on video / phase-3 rows that the live copy is inert while
   deploying.
7. **Coverage.** About 10-12 owner-played classic battles with the 26 thin / missing cards (list above); the bait
   account adds Goblin Barrel / Skeleton Army / Valkyrie forms.

## 6. Pod jobs (not run: pods busy until ~06:00 EDT and the rules require the lead's OK)

- **The job.** `parity/metrics/run_metrics_pod.sh` (the FIN13 setup of `diag_night/r7_closer/fin13_pod.sh`):
  - SIM `/workspace/rsfork_fin14c`, code `/workspace/cb13` with `parity/metrics/` synced, logs `/workspace/caplogs13`,
    exports buffs13 / attacks13s, K = 8.
  - Order: fights (J2 / J3 / J6 / J5a), whole (J7 on 10-17..19), elixir, laws, a score of each, and J5a from the FIN13
    bodies (read only, written to `$O/fin13`).

```bash
# laptop -> pod (P3 layout, as FIN13)
scp -r scratchpad/gauntlet/L74/parity/metrics <pod>:/workspace/cb13/scratchpad/gauntlet/L74/parity/
# pod
cd /workspace/cb13 && nohup bash scratchpad/gauntlet/L74/parity/metrics/run_metrics_pod.sh > /dev/null 2>&1 < /dev/null &
# -> /workspace/results/METRICS_J/{SCORE_all.txt, SCORE_whole.txt, SCORE_fin13_deploy.txt, matches/, whole/, elixir/, laws/, DONE}
```

- **Cost** (laptop-measured, scaled; (b) until run).
  - Fights: ~13 spell / king fights a match x 5 replays at ~0.3 s, about 20 s / match / core. 638 logs on 47 workers
    is about 5-10 min.
  - Whole: ~3 s per replay x 9, about 27 s / match. About 735 logs / 47 is about 7 min.
  - Elixir + laws: single process, about 30 min. Use `--stride` if that is too long.
- **Extensions owed** (code, not run):
  1. J3b tower targeting (needs the SIM projectile rows in the replay rows).
  2. A wider J7 ceiling (play-point jitter ±0.5 tile).
  3. J7 at level 16 only (the 10-19+ matches) once there are >= 100.

## 7. Limits

- **Runtime.** Every replay number except J1 is on the upstream 0.1.36 wheel. It shares the fork's card values but not
  its 20 laws or tower troops, so the fork numbers will differ. Expect higher J2 / J6 (the hide / pulse / dash laws);
  untested (b).
- **J7 n = 18 matches** (Wilson CI 0.25-0.66). The per-minute tolerance and the 10 s fall tolerance are first choices.
- **J6.** The ceiling pairs perturbed bodies by SIM uid. An uid that differs between replays drops out (it never
  inflates).
- **J4.** Opponent elixir is never graded (owner rule: no opponent elixir is read). The deduction timing (tap ->
  registration) is not an engine law.
- **Coverage.** "Covered" uses graded plays (J1 / J5's unit). Each other metric's n is in its own column, and many
  cards are covered for plays but thin for J3 / J6.
