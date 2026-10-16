# Reader upgrade for fight parity (2026-10-16)

Owner, 10-16: "upgrade the reader to collect data such as the invisible spells, opponent hero ability presses, and
internal states". The goal is SIM fight parity above 95% overall and above 90% per card (`fights.py`). The owner widened
the scope the same day: per-unit states that are **visible on screen** are public. They go into parity logs now and may
become model inputs later.

**Rules kept.** Nothing in this file says where anything sits in memory. Memory-side notes, the capture procedure and
build details are in `icebow/data/reader_notes/` (git-ignored). No opponent-private field is captured or proposed:
not the opponent's hand, next card, elixir, ability readiness, cooldown or charges.

## Key finding

The default live reader (`v2`, the one `live_play.py` and `replay_rec/recorder.py` use) **already sends** three things
on every frame. `live_play`'s `frame` event dropped all three:

- per-body `behavior_state_raw`, `evo`, `level` and `category`;
- the full `projectiles` list (side, position, target point, identity, **source body, target body**);
- the full `effects` list (area spells and ability areas: side, position, card, **remaining_ms**, level).

The `decision` event logged projectiles only at decision ticks (about every 0.65 s), without identity or target body,
and it logged no effects at all. The fields are now logged on every frame (see "Logging added").

A second, private **phase-2 capture build** also exists. It was validated live once (10-12, one full match:
1,778/1,778 frames valid, 0 read errors). It adds:

- the **status effects (buffs) on every body**: name, remaining and total ms, source side, and the flags `Invisible`,
  `Clone` and `Shield`;
- **own** hero ability state;
- per-hero-body pending and cast indicators.

It does not read any player block (no hand or elixir for either side), so it runs **beside** the v2 reader, not
instead of it.

## Inventory

Key: **a** = the reader samples it and only logging was missing (now logged). **b** = a mapped structure exists
(phase-2 build or RE notes) but it is not in the live stream. **c** = needs new mapping.

| target | a/b/c | evidence |
|---|---|---|
| Opponent hero ability, cast-time (Hero Knight, Mini PEKKA, Bowler, Musketeer seen) | **a** | `behavior_state_raw == 10` in 2-6-frame bursts (10-40 ticks) on exactly these hero cards in 3 raw captures (`L72/.../passive_v2_raw.jsonl`, `icebow/data/replay_rec/rec_20261008_210824.jsonl`). RE ties state 10 to the champion "casting" condition. Not yet timed against a press on video |
| Opponent hero ability, instant (CastTime 0, e.g. Hero Ice Wizard) | **a** (objects) | Own Hero IW: 0 frames in state 10 across 2 confirmed presses (10-12 phase-2 run). The press shows as **new objects**: a freeze-area effect row (`IceWizard`, 55 rows), the cube body and slow buffs. Evo/hero ability areas also show as effect rows (Valkyrie 30, Knight 14, Tesla 78, Cannon 108, Ice Golem 35) |
| Champion abilities (Skeleton King, Archer Queen, Golden Knight, Mighty Miner, Boss Bandit, Little Prince, Goblinstein) | **a, unverified** | No raw capture contains a champion. The same generic champion code path (state 10 and the ability's objects) is expected but untested |
| Opponent hero pending/cast indicator on the body | **b** | Phase-2 `ability.pending_on_body` and `cast_timer_ms_raw`, validated on own Hero IW only. For model input use the visible cast, not the pending flag (see Concerns) |
| Log, Arrows, Fireball, Rocket, Snowball, Barbarian Barrel, Goblin Barrel | **a** | Projectile rows in raw captures: Arrows 511, Log 377, Fireball 20, Snowball 18. Rocket target equals the cast point (L70). `fights.py` already sees these at decision ticks (`opp_spell_seen`) |
| Poison, Tornado, Graveyard | **a** | Effect rows: Poison 400 (first remaining_ms 7,950 = the 8 s spell), Graveyard 135 (~8,950), Tornado 24. remaining_ms drops 50 ms per tick (101/101 pairs, L70) |
| Zap, Lightning, Earthquake, Freeze, Rage | **a, unverified** | Not cast by any opponent in the 5 raw captures. The effect path is generic by object class, not by card, so they should appear. Zap is short-lived and may fall between 100 ms samples (L70: "empty output is not proof of absence"). Their buffs (Freeze, Stun, Rage) are **b** |
| Projectiles in flight, with their target | **a** | `target` is a live body in 1,692 of 2,941 rows. It is null in 1,195 rows (point-targeted spells) and always an enemy body. `source` is a body in 2,532 rows. Tower shots carry card -1, so tower targets are visible too |
| Unit target (ranged attackers and towers) | **a** | Read from the projectile's source and target bodies: who shoots whom while a shot is in flight |
| Unit target (melee), aggro/pathing pull, two units moving to each other | **c** (positions only) | No target field on the body is mapped. Positions plus `behavior_state_raw` (moving vs engaged) give a derived guess, not the engine's target |
| Attack phase | **a**, coarse | `behavior_state_raw`: 1 moving (median 60 millitiles/tick, 0.7% still), 2 stationary/engaged (91% still), 4 deploying (only on deploying kinds), 0 idle building/tower, 6 tunnelling (Miner, 647 mt/tick), 10 hero cast, 5 Hog Rider/Dark Prince, 11 Mini Sparkys. The 0/1/2/4/6 readings come from movement; the 5 and 11 readings are unverified |
| Attack timer / wind-up / hit cooldown | **c** | Not in any mapped structure |
| Tesla hidden / up | **a, unverified** | Tesla shows 0 (idle) or 2 (engaged) and never 1. Hidden = 0 is expected but not yet checked on video |
| Charging (Prince, Battle Ram, Dark Prince) | **a** candidate / **c** | State 5 appears on Dark Prince (2 frames) and Hog Rider (12; probably the river jump). No Prince or Battle Ram in the captures. Charge state, if separate from 5, is **c** |
| Dash/jump wind-up (Mega Knight jump, Bandit and Golden Knight dash) | **c** (a candidate) | No such state seen: Mega Knight only 0/1/2 in 20 frames. Needs video-correlated frames |
| Invisibility (Royal Ghost, Archer Queen cloak) | **b** | Phase-2 buff `config.Invisible` flag. RE maps Archer Queen's cloak buff; Royal Ghost is not captured yet |
| Status effects (stun, slow, rage, freeze) + remaining time | **b** | Phase-2 buffs, live 10-12: 1,661 buff rows, remaining_ms drops 50/tick in 1,403 of 1,404 pairs. Names seen: IceWizardHeroSlow, Poison, IceWizardHero_FreezeBuff, Tornado, Knight_Fortify_EV1, Valkyrie buffs, Tesla_EV1. Freeze, Stun and Rage rows are mapped statically. Stun and freeze have the same modifiers, so they are told apart by **name** |
| Spawner timers (Witch, Tombstone, Furnace, huts) | **c** | Only buff-driven spawn counters are mapped |
| Facing (the death-spawn layout reads it) | **c** | Not mapped; motion direction is a proxy |
| Deploying units | **a** | `kind` was already logged; `behavior_state_raw == 4` confirms it |
| Opponent spell level | **a** (effects) | Effect `level_raw`. Projectile rows carry no level |
| Frame rate | **a** (a knob) | `--interval-ms` (default 100). Read cost is 0.42 ms median (p95 1.0 ms). Live 10-15: 96.8% of frame gaps are 2 ticks, and backlog is 0 in 99.7% of frames. One frame per tick (50 ms) looks affordable, but it changes the decision cadence, so it is a live change, not logging only |

## Logging added (opt-in, under `--log-frames`)

`scratchpad/gauntlet/L68/live_reader/live_play.py`: `frame_extras()` and the field lists `ENT_STATE_LOG`, `PROJ_LOG`
and `FX_LOG` (next to `CONFIRM_BASE`). The `frame` event gets three new keys **only when `--log-frames` is on**. A run
with recording only writes the old event unchanged.

- `ents_state`: `[behavior_state_raw, evo, level, category]`, parallel to `ents` (same order; the `ents` rows keep their
  8 columns, because consumers unpack 8);
- `proj`: `[side, x, y, card_id, target_x, target_y, address, generation_key, source, target]`;
- `fx`: `[side, x, y, card_id, remaining_ms, level_raw, address, generation_key]`.

The players block is never read. Code-location fields from the reader are never copied. `LIVE_OPTIONS` already has
`--log-frames`, so the next live, friendly or dry-run session captures these with no further change. Decisions and taps
are unchanged. Test: `test_frame_extras.py`.

## How `fights.py` would use each item, and the fights it unblocks

These are counts from the 0.1.35 full run (`FIGHTS35`: 84 matches, 4,439 fights; strict 1,201, core 2,746). "Only" means
the fight's sole blocker. Each count is an upper bound: a fight leaves the blocked set only once `fights.py` consumes the
field.

| item | use in `fights.py` | fights |
|---|---|---|
| Opponent hero/champion activation (state 10 + ability objects) | **Deploy event** at the first cast frame. Fights with the hero on board but no press in the window become clean | flagged 2,323; **only blocker in 1,222** (Skeleton King 205, Bowler 191, Elite Archer 117, Mini PEKKA 95, Boss Bandit 91, Mighty Miner 88, Knight 83, ...) |
| Opponent projectile spells every frame, with identity | **Deploy event** at the first frame; cast point = target point (rolling Log/Barbarian Barrel = first-seen point); level from the body/effect | flagged 1,046; **only blocker in 165** (Log 54, Arrows 41, Fireball 40, Goblin Barrel 18, Rocket 12, Snowball 7) |
| Opponent effect spells (Poison, Zap, Lightning, EQ, Freeze, Rage, Graveyard, Tornado) | **Deploy event** at cast tick = first-seen tick, or first-seen minus (full life - remaining_ms). Also **de-contaminates strict**: these casts are invisible today, so some "strict" fights contain them | unknown until logged. Strict today = 1,201 |
| Hidden-info total (core minus strict) | both rows above | **1,545** |
| Own spell in flight at t0 (projectile position/target, effect remaining_ms) | **Setup state**: seed the object mid-flight, or exclude exactly when the SIM cannot | flagged 449; only blocker in 110 |
| Ability active at t0 (IW freeze area, cube, freeze/slow buffs) | **Setup state**: remaining freeze per body from buffs (phase 2) | flagged 113; only blocker in 13 |
| Ranged/tower target from projectiles | **Setup state**: measured target lock replaces the inferred tower lock (`setup_target_tower`) and covers unit targets | 613 fights use the inferred lock today |
| `behavior_state_raw` (deploying, engaged, moving) | **Setup state**: deploying flag; engaged vs moving at t0 | `setup_was_deploying` 72 (only blocker in 6) |
| Status buffs (stun, slow, rage, freeze, invisible), phase 2 | **Setup state** at t0 and an **exclusion** check during the fight | not counted (no phase-2 logs on the 0.1.35 set) |
| Melee target, wind-up, facing, spawner timers, charge | Setup state | **c**: blocks the Mega Knight (#4), death-spawn layout (#1) and Witch (#2) residuals |

## Live mapping plan (semantic steps; memory steps are in `icebow/data/reader_notes/`)

**Today (owner's classic 1v1, MuMu open). Nothing needs to be built.** Two read-only captures run during the same
battle:

- **Capture A:** `live_play.py` in **dry-run** (it decides and logs but never taps; the owner plays) with
  `--log-frames` (from LIVE_OPTIONS) and the screen recording on. This gives the frame log with the new
  `ents_state` / `proj` / `fx` keys, plus video.
- **Capture B:** the phase-2 capture build beside it. It gives buffs on every body, own ability state and hero cast
  indicators. Its runner keys on capture A's log for the start time and own side.

Start-up is about 2 minutes. Capture B needs the game build to be the one mapped (10-12); if the game updated, both
captures fail at once and a re-find plus rebuild comes first (estimate in the private notes). Use the main account and
the icebow deck, because the dry-run pilot loads the icebow model.

Ordered steps for the owner during that battle. Own-side steps are controllable; opponent-side steps happen only if
the opponent does them:

1. Place Tesla with no enemy in range and wait about 5 s, then let an enemy walk in. Maps Tesla hidden/up (expected
   0 → 2).
2. Cast Log on a known unit and Tornado on a group. Rocket a tower if the match allows. Maps projectile identity and
   source/target, the Tornado effect and buff.
3. Press the Hero IW ability with enemies in range. Maps state 10 (expected absent), the freeze-area effect, the cube
   body, the freeze-then-slow buffs on opponent bodies with remaining ms, and own ability state.
4. Let X-Bow and Ice Wizard shoot different targets. Maps projectile target = body (unit targeting).
5. Opponent side, whatever happens: any hero/champion press, charge, jump or dash, invisible unit, and any spell. The
   tick on the video overlay matches the frame log.

**Next session (targeted, friendly battle with a second account).** The opponent casts, one at a time and ≥ 5 s apart,
each on a known unit:

- Zap, Lightning, Earthquake, Freeze, Rage, Poison;
- then the hero/champion buttons (Knight, Mini PEKKA, Skeleton King, Golden Knight dash, Boss Bandit dash, Archer Queen
  cloak);
- Royal Ghost, Prince, Battle Ram, Dark Prince charge, and a Mega Knight jump;
- a Witch and a Tombstone left alone for 10 s (spawner timers, c).

Then run an offline correlation of field values against the video.

**After that (c items):** new RE for the melee target, the attack/wind-up timer, facing, charge state and spawner timers,
then a phase-3 build and the same friendly script.

## Concerns

- The existing `frame` event writes `opp_elixir_true_EVAL_ONLY` (the opponent's true elixir, for offline grading of
  the counter). As stated here, owner rule 1 forbids opponent elixir in logs. This predates this change and was not
  touched. **Owner decision needed.**
- Phase-2 `pending_on_body` on an opponent hero can precede the visible animation by a few frames. For parity logs only;
  any model input must use the visible cast (state 10 or the ability's objects).
- "a, unverified" rows (Zap, Lightning, EQ, Freeze, Rage, champions, Tesla 0 = hidden, state 5) rest on one
  structural argument each. The mapping session decides them.
