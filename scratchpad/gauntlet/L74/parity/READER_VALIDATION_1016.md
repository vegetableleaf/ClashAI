# Reader field validation, owner-played classic battles (2026-10-16)

Companion to `READER_UPGRADE.md`. **Semantics only**: field names, units, counts, ticks, video times. Where things
sit in memory and how the capture build reads them is in `icebow/data/reader_notes/` (git-ignored). No
opponent-private field is used: not the opponent's hand, next card or elixir. The frame log's old
`opp_elixir_true_EVAL_ONLY` field was not read (commit f3ab77a removes it from future logs).

Script: `reader_val/validate_1016.py FRAME_LOG P2_FRAMES`. It reads only the already-decoded JSON fields and prints
no runtime addresses. Full outputs (not tracked): `.foreman/scratch/reader_val_1016_m{1,2,3}.txt`.

## Data

| | match 1 (m1) | match 2 (m2) | match 3 (m3) |
|---|---|---|---|
| frame log (B, `--log-frames`, dry-run) | `live_play_20261016_115958`, 1,697 frames, ticks 151-3508 | `live_play_20261016_121354`, 1,778 frames, ticks 153-3681 | `live_play_20261016_122204`, 2,016 frames, ticks 150-4171 |
| phase-2 capture (A) | `p2_20261016T120616`, 1,688 frames, ticks 185-3508 (1 frame with read errors) | `p2_20261016T121845`, 1,524 frames, ticks 201-**3257** (ended early, see Concerns) | `p2_20261016T122649`, 2,001 frames, ticks 219-4171, 0 errors |
| observer side | 0 | 1 | 1 |
| who played own cards | owner | **mixed**: a parallel **non-dry-run** live_play (`121550`) made 13 confirmed taps | owner (0 confirmed taps) |
| opponent cards seen | Bowler, Royal Hogs, Furnace (+evo), Prince, Lumberjack (+evo), Hero Musketeer, Freeze, Log | Musketeer, Goblin Barrel, Witch, Valkyrie, Mega Knight, Bats, Skeleton Army | Furnace (+evo), Barbarian Barrel, **Hero Knight**, Goblin Drill (+evo), Poison, Ice Spirits, Cannon |
| raw video (`icebow/data/overlayed_replays/raw/`) | `lp_20261016_115958_{0,1,2}.mp4` | `lp_20261016_121354_{0,1,2}.mp4` | `lp_20261016_122204_{0,1}.mp4` |

Own deck in all three: X-Bow, Tesla (+evo), Hero Ice Wizard, Knight (+evo), Skeletons, Log, Tornado, Rocket. Video
times below are "segN m:ss" = time into raw clip N. The overlaid m1 render was still being written during the analysis
and had no index yet, so only the raw clips were used.

## Alignment (A vs B vs video)

- **A to B:** both captures stamp the game tick, and both use the device's uptime clock (A `sample_monotonic_us`,
  B `t_dev`). Shared ticks: 955 / 962 / 1,034. At the same tick, A's clock minus B's clock has a median of -17.8 /
  +11.7 / -18.6 ms (worst single frames -78 to +180 ms). On the same body at the same tick, (x, y, hp) is identical in
  9,111 of 9,118 / 7,492 of 7,496 / 11,790 of 11,793 rows. **Join on game tick plus body generation id**, which is the
  same number in both captures (B `ents_state[3]`, A `entities.category` and `phase2.units.generation`). Never join on
  the runtime address: it is reused. In m1 one address held a Tesla (ticks 727-995) and then a new Ice Wizard (1322).
- **B to video:** video second = `t_dev - segment_start` (each raw clip logs the device uptime just before recording).
  Five sharp events check out, each within one sample (0.2-0.25 s):
  - m1 tower last hp at tick 1535 (seg1 82.16 s), gone at 1537; the video shows it destroyed at 82.2 s.
  - m1 Tesla up at 2559 (133.24); the video shows it rising at 133.0 and up at 133.25.
  - m2 Mega Knight landing at 1397-1399 (seg1 17.59-17.69); the landing splash shows at 17.7.
  - m3 Hero Knight state 10 at 2133 (seg0 157.61); the taunt circle first shows at 157.6.
  - m3 second cast at 3223 (seg1 41.66); the circle shows at 41.8.

  Any screenrecord start-up offset is therefore below about 0.2 s. Match clock = tick / 20 s, and the on-screen
  "time left" agrees.
- **Video geometry:** for observer side 0 (m1) the screen's x axis is mirrored relative to reader x. The Royal Hogs
  at reader x 0.7-4.2 appear at the screen's right edge.
- **Own plays:** an own card shows on screen (placement ghost and card label) about 1.2 s before the reader shows its
  body or projectile. m1 Log: label at seg1 44.75, first projectile at tick 813 (46.02), rolling on video at 46.25.
  A's `own_queue` held a pending play only once per match (~1.15 s, e.g. m1 Tornado 3217-3229), so it is not a
  per-play record.

## Validation table

Verdicts: **VALID** = the field agrees with video and/or the bodies and SIM tables on every event checked. **PARTIAL**
= correct but incomplete or with a caveat. **NOT OBSERVED** = the situation did not occur. n = events.

| field | verdict | n (m1 / m2 / m3) | evidence |
|---|---|---|---|
| `behavior_state_raw` 1 moving / 2 engaged | **VALID** | all bodies | State-1 median speed equals the table walk speed: Prince 59 (table Speed 60), Knight 60, Hero Knight 59, Hero IW 59, Royal Hog 119, Lumberjack 119 (table 120), Bowler 44. State 2 is still in 87-100% of steps. Exception: Mega Knight's pre-jump wind-up is state 1 at zero speed (jump row) |
| state 4 deploying | **VALID** | 120+ / 40+ / 60+ | First frames after placement. Lengths match DeployTime: X-Bow 70 ticks, Tesla 20, troops 18-20 |
| state 0, Tesla hidden | **VALID** | 3+3+3 Teslas, 24 transitions | m1 Tesla 1: 2 at 747-869, 0 from 871 (seg1 48.92); video up at 48.5, flat at 49.0. m1 Tesla 2: 0 until 2557, 2 from 2559; video rising 133.0, up 133.25. In m2 and m3 the Tesla toggles 0↔2 repeatedly as enemies cross about 6.3 tiles centre to centre (range 5.5 plus collision radii) |
| Tesla rise wind-up | **NOT RESOLVED** | 2 checked | No separate value. The rise (≤ 0.5 s) falls inside one 2-tick sample of the 0→2 change |
| state 5, river jump | **VALID** | 3 / 0 / 0 | m1 Royal Hogs, ticks 695-733 (seg1 40.1-42.0). y 17.4→14.9 across the river at 159 mt/tick (table JumpSpeed 160). A puts `JumpHack_Ignore_Pushback_Buff` on the same hogs on exactly these ticks. The hog on the bridge and hogs deployed on our side never show state 5 |
| state 3, Mega Knight jump | **VALID** (new value) | 0 / 1 / 0 | m2 ticks 1383-1400 (seg1 16.89-17.79). 249 mt/tick (table JumpSpeed 250). About 16 ticks airborne (DashConstantTime 800 ms). Started 3.6 tiles from the Skeletons (DashMinRange 3.5). Landed at 1397-1399 at (13.25, 17.25); the 3 own Skeletons 1.2-2.4 tiles away disappear at 1399 (DashRadius 2.2) = the splash deaths. Video: airborne 16.9-17.5, splash 17.7. **Wind-up** = state 1 at zero speed for 16 ticks (1366-1380), distinguishable only by speed. No buff and no ability row in A. The owner's note (MK jumped onto Skeletons) agrees |
| state 6, tunnelling | **VALID** | 0 / 0 / 8 digs | m3 `GoblinDrillDig` / `GoblinDrill_EV1_Dig` move underground at 278-300 mt/tick from the opponent's King Tower line to our side. The evo drill re-burrows in state 6 at 190-212 mt/tick (ticks 2037-2055, 2109-2127, 4028-4101) |
| state 10, hero cast | **VALID** | 0 / 0 / **2 casts** (opponent Hero Knight) | m3 ticks 2133-2155 and 3223-3244: 11-12 frames each, about 22 ticks = 1.1 s, Hero Knight standing still. Video: taunt circle at seg0 157.6 and seg1 41.8. **Negative control:** the m1 opponent Hero Musketeer had 0 state-10 frames in 192, and the owner confirms it was never pressed |
| hero ability objects (opponent) | **VALID** | 0 / 0 / 2 | Each cast: an effect row with card Knight at the hero (3.7, 20.3) / (4.7, 18.2), remaining_ms 1100 → 0 at -50 per tick, starting 1 frame after state 10. Buff `Knight_hero_AbilitySelfBuff` 5000/5000 on the Hero Knight. Buff `Knight_hero_IsTauntedBuff` 3950/4000 (-50 per tick, 153/153) on **our** bodies within reach: princess tower ×2, Tesla, Skeletons ×2, Knight. **Effect on our units:** our princess tower's shots switch target from the Furnace (ticks 3180-3220) to the Hero Knight (from 3240) = the taunt |
| hero body indicators (A `pending_on_body`, `cast_timer_ms_raw`) | **PARTIAL** | m3 2 casts | `pending_on_body` stayed 0 on every frame, including both casts. `cast_timer_ms_raw` counts **ticks, not ms**: +2 at the cast start, then -1 per tick to -21, and it **stays at -21** for the rest of the body's life. Use state 10 (or the ability effect / buffs) as the activation signal |
| Prince charge (owner note m1) | **PARTIAL** (speed only) | 6 charges by 3 Princes / 0 / 0 | There is **no charge state** (it stays 1) and no charge buff or ability row in A. The speed doubles 59 → 119-120 mt/tick (table ChargeSpeedMultiplier 200) after 2.4-2.7 tiles of walking (ChargeRange 2.5). Charge 1: ticks 1318-1342 (seg1 71.25-72.45), with the video lance-down at 71.25. **Hit** at 1342/1344: our just-deployed Hero IW (688 hp) and its floating cube vanish in one blow. Other charge hits: tower -998 (783 charge + 215 other) at 1398, King -783 at 1604 and at 3307 (783 = 2 × the normal 391 hit), Skeletons at 2565, Tesla at 2641. A charge is detectable from 2 consecutive frames (speed ≥ 1.6 × walk) |
| `proj` source / target, ranged units and towers | **VALID** | all shots | The source is a live body of the shooter's side and card in 100% of resolved rows. The target is an enemy body in every resolved row. The target point equals the target body's position (median 0.00 tiles) = homing. Kamikaze or rolling shooters (Fire / Ice Spirits, Bowler) have a missing source or a null target |
| **X-Bow + Ice Wizard on different targets** | **VALID** | 0 / 0 / **18 frames** | m3: X-Bow and IW shots were in flight together in 26 frames, and in 18 of them the targets did not overlap. Ticks 561-633: X-Bow on Goblins / Ice Spirits / Barbarian while the IW was on the Furnace (seg0 78.9-82.5; video: IW bolt toward the left-lane Furnace while the X-Bow fires right). Also 1472 (X-Bow on Barbarian, IW on Goblin Drill) and 1502 (X-Bow on a princess tower, IW on a Goblin). m2: 19 such frames, all on the same target |
| `proj` spells (Log, Barbarian Barrel, Rocket, Goblin Barrel, MK appear) | **PARTIAL** | all casts | Log and Barbarian Barrel each show as 2 shots: a throw ending at the cast point, then the roll (Log about 10.1 tiles, Barbarian Barrel about 4.3 tiles and then a Barbarian body at the end). Their source is the King Tower in the throw phase, null in the roll. The target body is always null, so the cast point = the first shot's target point. Rocket and Goblin Barrel: source = King Tower. Mega Knight deploys as a projectile from the King Tower (table PROJECTILE.MegaKnightAppear). **Tesla attacks produce no projectile rows**, so the Tesla's target is not readable |
| `fx` Tornado | **VALID** | 2 / 1 / 1 | remaining_ms 950-1000 → 50 at -50 per tick (table LifeDuration 1050). The pull is visible in the bodies: m1 Bowler at 193 mt/tick in state 1 (ticks 3259-3275), m3 Ice Spirits at 402 and Hero Knight at 161 (ticks 3415-3431). No radius field; use the table (5.5 tiles) |
| `fx` Freeze spell (owner note m1) | **VALID** | 1 / 0 / 0 | m1 tick 1588 (seg1 84.77) at (5.5, 5.5), covering our left princess tower and the King Tower. remaining_ms 3400 → 0 at -50 per tick, so the cast tick is 1586 (table LifeDuration 3500). Video: clear at 84.5, ice circle and blue king at 84.9-85.5, gone by 88.5. Tower damage -38 on both (table TowerDamage 15 at level 1, scaled) |
| `fx` Poison | **VALID** | 0 / 0 / 3 | m3 ticks 2602, 3008 and 3753; 7950 → 50 (8 s spell). Poison buff 1000/1000 on our princess tower and X-Bow |
| `fx` Lumberjack death rage (card `RageBarbarian`) | **VALID** | 2 / 0 / 0 | A 1-frame row with remaining 0-50 (the 50 ms spawn dummy), then the rage area: 5500 → 0 (table BarbarianRage LifeDuration 5500) at ticks 1702-1812 and 2941-3050. Video: pink rage circle at seg1 90.7 |
| `fx` own Hero IW ability area | **VALID** | 1 / 0 / 0 | m1 (2.7, 21.6) ticks 2382-2425. remaining_ms 999,999 → 997,849 is a **sentinel** ("lives as long as the cube", table BuffTime 999999), not a time. The cube body `IceWizardHero_IceCube` covers ticks 2382-2424 |
| `fx` evo Tesla deploy pulse | **VALID** | 1 / 1 / 1 | 1450-1500 → 0; `Tesla_EV1_WithDamage` 500/500 stun buff on enemies hit |
| buffs: Freeze (spell) | **VALID** | 2 instances / 0 / 0 | m1 our KingTower and PrincessTower, source = opponent. 3450/3500, -50 per tick (68/68). Same ticks as the effect |
| buffs: Freeze (Ice Spirits) | **VALID** | 0 / 0 / 4 | m3 `Freeze` 1100/1100 on our Hero IW and its cube at ticks 2443 and 3831. That is the Ice Spirit hit: same buff name as the Freeze spell, different duration |
| buffs: Tornado | **VALID** | 8 / 3 / 4 | Opponent bodies only, source = own side. 500/500-550 and **re-set every tick** while inside (decrement 0): an "in area" buff, not a countdown |
| buffs: IW slow (`IceWizardHeroSlow`, `IceWizardHeroCold`) | **VALID** | 20 / 4 / 28+7 | The slow sits on the bodies the Hero IW hits: 2450/2500, -50 per tick (397/397 m1, 525/525 m3), new instances every 34 ticks = the IW hit rate. `IceWizardHeroCold` 2500 is applied around the IW at its deploy (m3 2193, 3815) |
| buffs: Hero IW ability chain | **PARTIAL** | 1 / 0 / 0 | `_FreezeBuff_dummy` 50/150 at 2382, then `_FreezeBuff` (sentinel 999,949/999,999) on the 2 opponent bodies within 1.72 tiles (table radius 2.5; nearest unbuffed opponent 3.94 tiles), then `_SlowBuff` 1900/2000 from 2428. Caveat: that slow buff's **source side reads the victim's side**, because the table spawns it from the frozen body's own remove-action |
| buffs: Knight evo shield (`Knight_Fortify_EV1`) | **VALID** | 3 / 0 / 5 | Own Knight_EV1, 100,000 or 180,000 ms, -50 per tick |
| buffs: Rage | **NOT OBSERVED** | 0 | Both m1 rage areas were real, but no opponent troop came within 3 tiles (nearest 17.2 and 8.4 tiles) |
| buffs: Zap / EQ / Lightning stun, Invisible | **NOT OBSERVED** | 0 | No such spell or invisible unit in 3 matches. `Invisible` flag rows: 0 |
| own hero ability state | **VALID** | 1 press / 0 / 0 | Values: 2 ready, 9 not enough own elixir, 7 pending, 6 all charges used. m1 press: 7 at 2358-2377 (seg1 2:03.4), then 6. The area and cube appear 22-24 ticks (1.1-1.2 s) after the press, the same latency as card plays |
| state 11, staggered spawn | **VALID** (new meaning) | 7 hogs / 3 Bats / 0 | 1-3 frames exactly at spawn, then state 4, only on multi-unit deploys that spawn one by one |
| spawner timers | **NOT AVAILABLE**, derivable | Furnaces, Witch | No timer field. Spawns show as new bodies, so the cadence can be derived when the deploy is inside the log. m2 Witch: deploy 535, spawns 574 (+39 = deploy 1 s + SpawnStartTime 1000), 714, 855 (+140/+141 = SpawnPauseTime 7000). m1 Furnace: +99, then +126 while under the IW -30% slow. A slowed spawner needs A's buffs to integrate the delay |
| melee target, attack wind-up / cooldown, facing | **NOT AVAILABLE** (c) | n/a | No field. Melee hits are visible only as hp drops on the victim. The m3 taunt retarget is readable only for ranged shooters |

## Opponent spells and abilities found

- **m1:** Freeze ×1 (cast tick 1586). Log ×1 (2663, cast point (3.5, 17.5)). Lumberjack death rage ×2 (1702, 2941).
  Hero Musketeer on the board 192 frames with no ability. Prince ×3 with 6 charges.
- **m2:** Goblin Barrel ×1 (tick 350, to (3.5, 25.5)). Mega Knight deploy-drop and 1 jump onto Skeletons (1383-1400).
  Skeleton Army (1474). Witch spawns. No opponent effect spell, no opponent hero.
- **m3:** **Hero Knight ability ×2** (ticks 2133 and 3223: taunt area 1.1 s, self-buff 5 s, taunt on our units 4 s).
  Poison ×3 (2602, 3008, 3753). Barbarian Barrel ×4 (593, 1368, 3373, 3673). Ice Spirits freeze on our Hero IW ×2
  (2443, 3831). Goblin Drill digs ×8, evo Furnace.

## Owner's list after matches 1-3

| owner item | status |
|---|---|
| Tesla hidden | **done** (state 0 / 2) |
| hero ability (opponent) | **done** for cast-time heroes (Hero Knight: state 10, effect, self-buff, taunt buffs). Champions untested |
| hero ability (own, instant) | **done** (own state 7 → 6, area, cube, freeze/slow buffs) |
| X-Bow + Ice Wizard targeting | **done** (m3, 18 frames with disjoint targets) |
| projectiles in flight | **done**; Tesla shots have no projectile rows |
| slow / freeze | **done** (IW slow, Freeze spell, Ice Spirit freeze, IW freeze chain) |
| stun | evo-Tesla stun only; Zap / EQ / Lightning not observed |
| rage | rage area seen; Rage **buff** not observed (no eligible troops) |
| charging | **derivable** from speed (×2.0 after 2.5 tiles), no native flag (m1 Prince) |
| jump | Royal Hog river jump = state 5; Mega Knight dash = state 3 plus a zero-speed wind-up |
| invisibility | flag mapped, **never observed** |
| aggro pathing / melee target | **missing (c)**: positions only. The taunt shows on ranged shooters only |
| attack wind-up / cooldown | **missing (c)**. The biggest parity item: attack-phase timing was 47% of the S2 anchor mismatches (`DIAG_1016.md`) |
| spawner timers | **derivable** (deploy tick + table + A buffs); native timer missing (c) |

## Next capture session (only what three matches did not show)

Friendly battle, dry-run **only**, with a **single** live_play process. Each item at least 5 s apart, on a known unit:

1. **A champion button**: Archer Queen cloak (also the only path to the **Invisible** flag), and Golden Knight or Boss
   Bandit dash (a dash wind-up that is not a jump).
2. **Stun spells** on our troops: Zap, then Lightning or Earthquake.
3. **Rage spell on the opponent's own push** (Rage buff on their bodies), and Royal Ghost (invisible).
4. Battle Ram or Dark Prince charge (is state 5 also used by chargers, as the earlier passive captures hinted?).
5. A spawner (Witch or Tombstone) left alone 10 s **while slowed by the Ice Wizard**, to test the derived timer.
6. Optional: one session at a 50 ms reader interval (Tesla rise, MK landing, cast start).

## Is a phase-3 build (new RE) needed?

**Yes, for two items only: the melee / Tesla target and the attack wind-up / cooldown.** No logged field gives either
one, and the attack phase is the largest measured parity residual. **Not needed** for:

- charge: speed ×2.0 after 2.5 tiles, from 2 frames;
- Mega Knight jump: state 3 plus the zero-speed wind-up;
- Tesla hidden: state 0;
- spawner cadence: deploy tick plus table plus A buffs;
- hero activation: state 10 plus the ability effect and buffs.

Facing and the native spawner timer are optional (death-spawn layout; spawners already on the board before the log
starts). RE starting points, where to look rather than what is there, are in
`icebow/data/reader_notes/READER_VALIDATION_1016_private.md`.

## Concerns

1. **m2 own plays are not all the owner's.** `live_play_20261016_121550` ran **without** `--dry-run` (explicit
   `emote_spam`) beside the dry-run logger and made 13 confirmed taps (Log at tick 191, then Ice Wizard 299,
   Skeletons 329, Tesla 363, Tornado 391, Knight 1099, X-Bow 1253, ...). The lead confirmed it was started from the
   owner's own window.
2. **m2 capture A ended at tick 3257, about 21 s early.** At device time ~2464.1 s (tick ~3255) the on-device samplers
   got SIGTERM. The dry-run reader logged `reader_closed rc 143 "Terminated"` at 3255 and restarted after a 14-tick
   gap. `121550`'s last frame is 3253, with no `end` event. This is consistent with the known `pkill -f live_sampler`
   cleanup also killing the phase-2 sampler. Run one live_play per session.
3. **Hero Ice Wizard = 2 bodies.** The hero and `IceWizardHeroFloatingCube` share one card id, so the frame log
   (catalog names only) shows **two "IceWizard" bodies** with identical states (e.g. m2 tick 3416, after A stopped). A
   consumer counting by card would double-count the IW. A's names separate them.
4. Sentinels: `remaining_ms` 999,999 (IW area) and buff 999,949/999,999 are not times. Hero `cast_timer_ms_raw` is a
   tick counter that sticks at -21.
5. Buff "source side" = the side of the object that spawned the buff, not always the card's owner (IW after-freeze
   slow). Use the buff name for ownership.
6. The Hero Knight was the only positive hero cast. Champions (separate ability objects) are still untested.
