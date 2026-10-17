# Reader phase 3c: shields, building lifetime, spawner timers, the attack state of disabled bodies (10-17)

Layout-free semantic note. The memory side (where the fields live, how they were found, the build) is in the private
reader notes; nothing here is an offset, a binary hash, a device path or a command line.

## What the parity rounds asked for (HANDOFF 10-17 U items) and the verdict

| # | item | verdict |
|---|---|---|
| 1 | per-body SHIELD hp (Guards, Royal Recruits, Dark Prince, Evo Wizard, Hero Knight; the 'shielded' cue) | **found** -- current and max shield per body, read with the hp (no extra read) |
| 2a | spawner next-spawn timer (Furnace, Barbarian Hut, Tombstone, Goblin Hut, Witch ...) | **found** (free: inside the 3b body read). Derivable from the 3b creation tick + the definition only while no buff touches the spawner (Rage, freezes); the field is exact either way |
| 2b | building remaining lifetime (Tesla, Furnace, Cannon, X-Bow, Inferno ...) | **derivable from hp** -- there is no lifetime timer in normal play: LifeTime is an hp drain. The one hidden part, the drain's sub-hp carry, is now read (free) |
| 3 | Rune Giant enchant state + attacks left | **not exposed** by the objects the reader reads (no buff row; it lives in a separate action object). Not built |
| 4 | the attack row for bodies that lack one at fight start | **explained + captured**: those bodies have their attack bit cleared (deploying, staggered, frozen / stunned, hero cast, inactive king); the component still exists and is now read as `attack_disabled` |
| 5 | bodies that live less than one frame gap | **report only**: body generation ids are sequential, so the missing ids COUNT them for free (measured 19 of 1,714 bodies in 15 matches = 1.1%); no cheap per-tick spawn / death record was found; what they were is not recoverable without one |

## New fields (phase-3 capture, `phase3.bodies[]`, every listed body)

| JSON key | unit | meaning |
|---|---|---|
| `shield_hp_raw` | hp | Shield left. Damage takes it first; a heal on a shielded body refills the shield (up to its max). |
| `shield_max_raw` | hp | Shield size, level-scaled from the definition's ShieldHitpoints. A native shield (Guards, Dark Prince, Royal Recruits) starts full; an ability shield (Hero Knight) reads 0 / max until the ability raises it. |
| `life_decay_acc_raw` | 1/100 hp | LifeTime drain carry (0..99). |
| `life_decay_per_tick_raw` | 1/100 hp a tick | LifeTime drain rate = max_hp x 100000 // LifeTime // 20 (exact on every building seen). |
| `life_timer_ms_raw` | ms | A second, timer-mode lifetime (+50 a tick); live it ran only in end-of-match frames. |
| `spawn_timer_ms_raw` | ms | Time to the next spawn. Starts at SpawnStartTime, -50 a tick (0 under a freeze, faster under Rage: the spawn-speed buffs), on reaching 0 the body spawns and re-arms by SpawnInterval (inside a wave) or SpawnPauseTime (after the wave's last). Meaningless (0) for non-spawners. |
| `spawn_wave_index_raw` | count | Spawns already made in the current wave (0 = the next spawn starts a wave; the wave has SpawnNumber). |
| `spawn_count_raw` | count | Starts at the definition's SpawnLimit value, -1 per spawn. |
| `attack_disabled` | object or null | Only on rows with `attack: null`: the same fields as `attack` (target_gen, prev_target_gen, progress_raw, load_raw, ...), read from the body's attack component while its attack bit is clear. `attack` and `null_reason` keep their old meaning. |

All shield / life fields are null only when the hp read itself failed (hp -1: so far only the Evo Witch, as before 3c).

Per definition (`phase3.defs[]`, once): `SpawnStartTime`, `SpawnInterval`, `SpawnNumber`, `SpawnPauseTime` (ms / count,
from the spawner logic), `SpawnLimit` (the spawn-count start; name medium confidence), `LifeTime` (ms),
`LifeTimeTimerFlag` (0/1; gates the timer-mode lifetime together with a body condition not resolved; set on towers,
Tesla, X-Bow), `ShieldHitpoints` (table value before level scaling).

## Laws the capture confirmed (validate_p3.py V12; numbers below)

- Shield: while the shield is up, hp never drops; damage goes to the shield.
- Lifetime: every active sample pair of a LifeTime building drains exactly `dt x rate` hundredths (hp x 100 + carry)
  unless damaged (more); never less except the match-end freeze; no drain while deploying. An undamaged building
  vanishes in the frame gap where `ceil((hp x 100 - carry) / rate)` runs out.
- Spawner: -50 a tick or one re-arm by SpawnInterval / SpawnPauseTime per unbuffed pair; the first active value is
  SpawnStartTime - 50 x (active_ms / 50 + 1) (the timer takes its first step on the deploy-end tick).
- Sampling artefact (as in 3b): a frame whose state is one tick ahead of its label gives two adjacent pairs whose errors
  cancel; V12 pairs them up and counts them apart.

## Validation (live ranked matches beside the live run, game build 160402012)

Six ranked matches with the new probe running beside the live run (the live run's own probe untouched; two of them on
an earlier build that differed only in one definition key's name), plus two control matches with the 3b probe in the
same slot. 0 read errors, 0 definition read errors, empty stderr in all eight.

| check | result |
|---|---|
| unchanged 3a/3b checks (V1 definitions, V2 shooter target, V8 targets, V11 creation tick) | PASS in all 6 |
| V12a shield (Hero Knight, 13 bodies) | 13/13 start at 0 / max (818 = 4.09 x the table's 200); raised by the ability 2 times; 74 sample pairs with the shield up: hp lost 0/74, shield absorbed damage in 10; no-shield bodies read 0 / 0 in 125,428/125,428 rows. Native shields (Guards, Dark Prince, Royal Recruits) did not appear in these 6 matches: same field by the static map, not yet seen live |
| V12b lifetime (Tesla, Tesla evo, X-Bow, Hero IW IceCube; 83 bodies) | drain rate = formula 83/83; active pairs drained exactly dt x rate 9,219, more (damage) 294, less 0; 2 label-artefact pairs; 10 match-end freeze pairs; of 74 bodies that vanished, 34 vanished in the gap where the remaining-life formula ran out (the other 40 were destroyed earlier by damage); the timer-mode lifetime never ran |
| V12c spawner (Witch x5, Evo Witch x1) | 605 unbuffed pairs: -50 a tick 593, re-arm by SpawnPauseTime 10, label artefact 2, other 0; timer held while deploying (52 pairs); under Rage / freezes 44 pairs follow neither rule (the spawn-speed buffs) -> a creation-tick formula is exact only unbuffed, the field always; first active value SpawnStartTime - 50 x (active_ms / 50 + 1) in 6/6 |
| V12d attack_disabled | 30,677 rows: inactive king towers, deploying bodies (their component already holds a target), frozen / stunned / slowed bodies |

Spawner BUILDINGS (Furnace, huts, Tombstone) did not appear in these matches; they run through the same body-update
spawn logic by the static map (plausible, not yet validated live) -- `validate_p3.py` V12c checks them on any capture
that has one.

Item 4 census (15 stamped 3b captures): post-deploy, non-stagger rows with no attack row: 1,514, of which 1,498 (98.9%)
carry a freeze / stun buff (Hero IW freeze, Zap, Freeze, Tesla evo shock, snowball); the rest are one-frame edges and
Hero Mini PEKKA casts. Over 122 such gaps (row before vs first row after): progress 0 after 46, unchanged 25, moved
51; the target changed in 74. So the component is disabled, not rebuilt, and what the unit resumes with varies -- the
`attack_disabled` rows now show it frame by frame (a SIM-law question for the stun / freeze resume).

Item 5 census (same 15 captures): 19 body generation ids never seen out of 1,714 (1.1%); 12 more bodies were seen in
one frame only (Skeletons, Barrel goblins).

## What fights.py must do to use each field

- Shield at t0: set the SIM body's shield to `shield_hp_raw` (replaces the 'worn' heuristic: a setup body below max hp
  with no shield left, and the uniform redraw of a shield near an enemy). Hero Knight: 0 until raised, then the value.
  The live 'shielded' cue = `shield_hp_raw > 0`.
- Building lifetime at t0: the SIM drain's carry (`lifetime_acc` in the SIM's linear drain) = `life_decay_acc_raw`;
  the hp is already the live hp. Check the SIM's rate equals `life_decay_per_tick_raw` (same formula).
- Spawner at t0: `spawn_ms = spawn_timer_ms_raw`, `spawn_wave_left = SpawnNumber - spawn_wave_index_raw` (instead of
  the last-wave inference from first-seen children, which leaves `setup_spawner_unseen` when no wave was seen).
- Attack state at t0 for a disabled body: when `attack` is null and `attack_disabled` is set, its target / progress /
  load are the state the unit resumes with when the freeze / stun / deploy ends (the 3b-era t0 had no attack row for
  these bodies). Whether the SIM keeps or resets the swing over a stun is a SIM-law question this data can now answer.
- Unseen short-lived bodies: count the missing generation ids per match (no new field needed) to flag fights where a body
  the reader never saw may have acted.

## Cost

Memory reads: the hp read is the same read made longer, the spawner values come from the 3b body read, the
definition window replaces one per-definition read with one longer read -> 0 new reads per body; the only new per-frame
reads are the disabled-component reads (~2 a frame: the two inactive kings, plus deploying / frozen bodies).
Measured per frame against the live run's probe on the same match: median +33 to +51 us (6 matches; ~+10% of ~450-530
us), while the 3b probe in the same slot measured +2 / +5 us. The extra time is not explained by ~2 reads (~3 us); the
plausible cause (untested) is the longer unbuffered JSON line (each extra print is a write call). It is spent after the
frame's coherence check, so it does not widen the read window; 100 ms interval, so ~0.04% duty.
