# Reader phase 3 scope: attack target + attack phase (2026-10-16)

Companion to `READER_UPGRADE.md` and `READER_VALIDATION_1016.md`. **Semantics only.** Where the fields sit in
memory, the build recipe and the probe's read list are in `icebow/data/reader_notes/` (git-ignored). Offline
evidence only: no device, sampler or game code was run for this scope.

## Why

`READER_VALIDATION_1016.md` left two visual cues NOT AVAILABLE: (1) the current target of melee units and
buildings (ranged shots already give it through projectiles), (2) the attack wind-up / hit phase. `DIAG_1016.md`
attributed 47% of the earlier fight-parity tower mismatches to attack-phase timing.

## Findings (static, game build 160402012)

- **One object holds both.** Every body that can attack carries an attack component, reached from the body the
  reader already reads (no new pointer chain). It is present on active troops, active buildings and princess towers
  and absent while a body deploys (measured on 70,939 body rows from the 4 existing phase-2 captures: the
  "engaged" behaviour state occurs with the component present in 17,073 of 17,189 rows).
- **Target:** the component stores the current target body and the previous one. The retarget routine writes
  both, and the update drops the target when the target enters a terminal state. Same code for troops, Tesla,
  Cannon, Inferno, towers and X-Bow (no other attack-update implementation exists in the build). Confidence:
  high (static); not live-validated.
- **Attack phase:** the component keeps a count-UP attack progress in game-time milliseconds, a load (wind-up)
  timer and a pre-attack countdown. The hit phase is progress modulo the unit's HitSpeed. Per tick, progress
  advances by 50 ms scaled by the body's buffs' HitSpeedMultiplier: Freeze (-100) stops it, the Hero Ice Wizard
  slow (-30) gives 35 per tick, a +30 rage-type buff 65. A retarget resets progress to 0 and re-arms the wind-up
  as LoadTime minus the old phase. Confidence: high for the step law, medium for the exact damage instant
  (plausible: phase = LoadTime; not traced to the damage call), low for the auxiliary flags and one reset gate.
- **Correction to the earlier plan:** the field is not a countdown that "hits 0 on the damage tick"; it counts up,
  and the observable is the phase.
- The unit's own HitSpeed / LoadTime / LoadFirstHit / range values are readable from its definition once per card
  type; the session checks them against the device tables (Knight 1200 / 700 ms, Tesla 1100 / 700, X-Bow 400,
  princess tower 800, king tower 1000 / 500).

## Build path

The 10-12 phase-2 capture binary was a static glibc x86_64 Linux build (Ubuntu 24.04's GCC 13.3.0, `-O2 -static`)
made on a Linux pod, not an Android NDK build. Such a binary runs on the emulator's Android kernel (4 captures, 0 read
errors). The production reader came from a different toolchain (GCC 15.2). Neither was recorded. A pinned,
receipted pod recipe now exists in the private notes. It checks whether a rebuild is byte-identical, or failing
that, whether our own code is identical.

## Validation plan (one owner classic battle, icebow deck)

| # | staged by the owner | pass condition |
|---|---|---|
| V1 | none | definition timings equal the device tables (exact) |
| V2 | any ranged shot | shooter's target = projectile's target at launch, >= 95% |
| V3 | own Knight vs the first single enemy troop | target constant; progress +50 / tick; every hp drop at one fixed phase (record it; prediction 700) |
| V4 | own Tesla (or Skeleton bait) vs 2+ troops | target and previous target change on kills; progress resets each change |
| V5 | X-Bow locked, then Log / Tornado its target | phase mod 400 matches the shot cadence; retarget resets |
| V6 | own Hero Ice Wizard ability on engaged enemies | progress constant while frozen, then +35 / tick while slowed |
| V7 | opponent Hero Knight taunt, if it appears | taunted bodies switch target on the same tick as tower projectiles |
| V8 | passive | target empty or a listed body >= 99%; read-time cost measured |

## Probe design (capture-only)

A separate, default-off capture build beside the normal reader. It reads only bodies already in the board list:
their attack component (one extra read per attack-capable body) and one definition read per card type. It reads no
player objects, hand, next card or elixir for either side. Target pointers are only compared with the board list,
never followed. Opponent bodies under an invisibility buff are proposed to get no attack fields; the lead decides.
Projected cost: median +12-25 us per frame on a 404 us median (about 3-6%), measured in V8. Proposed binary name
avoids the `live_sampler` substring, so the bot's end-of-match cleanup cannot kill it mid-match. That is the trap
that cut capture A short in match 2.

## Out of scope (not pursued, not needed)

Debugger attach / breakpoints / watchpoints, calling or hooking game code, running the game library outside the
emulator (including the oracle host and the native sandbox), touching the encrypted on-disk library or integrity
checks, writing or pausing the game process. This scope only reads memory of the running game, like the existing
reader.
