# Folding the validated visual cues into the main live reader stream (spec, 2026-10-16)

**Status: spec only.** No build, no device, no model change. Semantics only: field names, units, budgets, plan. Where the
fields sit in memory, the exact flags and the pod commands are in `icebow/data/reader_notes/READER_STREAM_PRIVATE.md`
(git-ignored). Companions: `READER_UPGRADE.md`, `READER_VALIDATION_1016.md`, `READER_PHASE3.md`, `ATTACK_PHASE_1016.md`.
The SIM-side twin of everything below is `pipeline/sim_unit_state.py` (same fields, same buckets, tests in
`pipeline/tests/test_sim_unit_state.py`).

## 1. Today vs the goal

| layer | what it adds | where it runs | who can use it |
|---|---|---|---|
| v2 reader (main stream) | bodies (position, hp, `behavior_state_raw`, evo, level), projectiles with source/target body, area effects with `remaining_ms` | every frame, `live_play` reads it | the decision path (only bodies, hp, hand/elixir of OWN side) and the `--log-frames` parity log |
| phase-2 probe | buffs on every body (name, remaining, total, source side, flags), own hero ability state | a side process, written to a device file, pulled after the match | offline only |
| phase-3 probe (superset of phase 2) | attack target and previous target, attack progress, load timer, pre-attack timer, per-card definition timings | the same side process | offline only (`--capture-p3`) |

Goal: the buffs and the phase-3 fields arrive **in the main stream, every frame, joined to the body they belong to**, so
(a) the parity logs need no second process and no after-the-match pull, (b) a later model can see the same cues the SIM
extractor produces. Nothing in the decision path changes in this step.

## 2. Fields that go into the stream

All fields are public: visible on screen or derivable from what a player sees. Join key everywhere: **game tick plus
body generation id**, never the runtime address (addresses are reused: validated in `READER_VALIDATION_1016.md`).

| per body | unit | validated | SIM counterpart (`sim_unit_state`) |
|---|---|---|---|
| `behavior_state_raw` (already in the stream) | 0 idle / Tesla hidden, 1 moving, 2 engaged, 3 Mega Knight jump, 4 deploying, 5 river jump, 6 tunnelling, 10 hero cast, 11 staggered spawn | VALID (all) | `state`, `hide` |
| buffs: name, remaining ms, total ms, source side, flags (Invisible, Clone, Shield) | ms, 50 per tick | VALID (slow, freeze, taunt, poison, tornado, evo shield) | `status`, `buffs` |
| attack target (generation id of the target body, `null`, or `unlisted`) | id | V2 PASS (ranged); V3-V5 PASS where data | `attack.target` |
| previous target | id | seen; not a model input | none (SIM does not keep one) |
| attack progress | engine ms, count-up, carries across hits | linear step 50 / 35 / 0, 5,360+ intervals; `ATTACK_PHASE_1016.md` | `attack.progress_ms` |
| load timer | ms, counts down 50 per tick, re-armed on a fire | exact fire tick, 469 re-arms | `attack.load_ms` |
| per-card definition timings (HitSpeed, LoadTime, LoadFirstHit, Range, ...) | ms / milli-tiles, once per card per run | V1 exact vs device tables | `attack.hit_speed_ms` (from the card table) |

Not in the stream, by design: the pre-attack countdown and the raw flag bytes (kept in the side probe's log for
research only), the opponent's hand, next card, elixir, ability readiness, cooldown and charges. Invisible bodies ARE
read (owner 10-16: invisibility is visible to the player and ignored only by units). Own hero ability state stays
own-side only.

**Hit bucket resolution.** Live frames are 2 ticks apart in 96.8% of cases; the SIM extractor sees every tick. The
`hit` bucket (progress mod HitSpeed below a window) is therefore one tick wide by default in the SIM and must be 2 ticks
wide (`hit_window_ms=100`) when the SIM is read at the live cadence. A live consumer must also detect a hit as a
**crossing** between two samples (`progress // HitSpeed` grew), not as a phase test, because under a slow the phase does
not land on a fixed value (`ATTACK_PHASE_1016.md`).

## 3. Per-frame read-time budget

Measured: the v2 reader costs **0.42 ms median (p95 1.0 ms)** per frame, about 0.40 ms + 10 us per body, with no cost
per buff. The phase-3 side probe, which already does all of the above, ran at **0.42 to 0.51 ms median** on the three
10-16 captures. The frame interval is 100 ms, so the budget is not tight in absolute terms, but it is per-frame and the
reader also shares the emulator's CPU.

Budget for the merged reader (acceptance numbers, measured in the validation battle, section 6):

| quantity | limit |
|---|---|
| `read_us` median | at most 0.60 ms (probe: 0.42-0.51) |
| `read_us` p95 | at most 1.3 ms (v2: 1.0) |
| read errors / invalid frames | 0 |
| frame gap of 2 ticks | at least 96% (v2: 96.8%); backlog 0 in at least 99.5% (v2: 99.7%) |
| extra output per frame | at most about 3 KB (about 12 bodies x a few dozen bytes; definitions once per card) |

How the probe stays inside it, and the merged reader must keep it so:
1. **Reads are merged, not added.** The attack slot comes out of the same read that already fetches the HP slot (one
   wider read per body, zero extra system calls). The attack component is one further read per attack-capable body.
2. **Definitions are cached for the run** and emitted once per card.
3. **Buffs cost nothing extra** per buff in the measurements; they are read from the body's manager already visited.
4. **Guarded degrade, never block.** If a frame's `read_us` exceeds 2 ms twice in a row, the reader drops the new
   field groups for the next 20 frames and marks them `cues_degraded: true` in the frame. The v2 fields are never
   dropped. (Not in the probe; new, needs a fixture test.)
5. **Default off.** A flag selects the merged mode. Off = the current reader's output byte for byte.

## 4. Stream format

The merged reader emits, per entity row and in the frame header, the same blocks the probe emits today, under the same
key names, so `reader_val/validate_p3.py` and `fights.py` read them with no adapter. Rules:
- one row per body, keyed by generation id (the v2 `generation_key`);
- `attack: null` plus a reason counter when the attack component is absent (deploying body, frozen body, king tower
  asleep). Absent is data: a frozen body has no attack component and comes back with its progress and load unchanged
  (4/4 live resumes);
- `target` values are generation ids that appear in the same frame's body list; anything else is `unlisted` and is
  counted, never followed;
- definitions are in a `defs` record on the first valid frame that needs them and again on every reader restart
  (`live_play` restarts the reader up to 3 times after a closed stream; a restart must re-emit them).

## 5. How `live_play` / `pipeline/live_mem.py` would expose it (no model change)

1. `live_play` already logs `ents_state`, `proj`, `fx` under `--log-frames` (`frame_extras`). Add the new blocks to that
   same event, **only under `--log-frames`**. Decisions, taps and BoardState are unchanged.
2. New pure function `pipeline/live_unit_state.py: cues(frame) -> dict` with the **same schema as
   `sim_unit_state.extract`**. Mapping from the live frame:

   | cue | from the live frame |
   |---|---|
   | `state` | `behavior_state_raw`: 4 or 11 -> deploying, 3 or 5 -> jumping, 6 -> tunnelling, 10 -> casting, 2 -> engaged, 1 -> moving, 0 -> idle. Mega Knight wind-up reads 1 at zero speed: not distinguishable, left as moving |
   | `charging` | no native flag: speed at least 1.6 x walk over two consecutive frames (Prince, Dark Prince, Battle Ram), as `fights.py` derives it |
   | `hide` | state 0 on a hiding card = hidden, 2 = up. The rise itself (<= 0.5 s) is not resolvable at 2-tick sampling |
   | `attack.target` | the target generation id; uid space differs from the SIM, so consumers compare through body identity (side, card, position), not the number |
   | `attack.phase`, `frac` | from progress, HitSpeed (definition) and the crossing rule above; same buckets as the SIM |
   | `status.*` | buff names -> classes with the same rules as `sim_unit_state._statuses`: Freeze / ZapFreeze / Hero IW freeze (-100) = frozen, any negative speed or hit-speed = slowed, positive or Rage = raged, name contains Taunt / Invisible / Stun / Shield |
   | `slow_frac` | remaining / total straight from the buff (the live reader has the total; the SIM needs a memo) |
   | projectiles | `proj` rows: source, target, position, aim point; effect from the card |
3. `live_mem.board_state` stays as is: `to_observe` keeps dropping everything that is not in the verified contract
   (the module docstring says "absent here: spells/effects, projectiles, ability state"). When a model wants the cues,
   `cues(frame)` is called next to it and the result passed as a new optional BoardState field, with an
   `obs_contract` version bump. That is the model change, and it is out of scope here.
4. Offline gate (no device): replay the existing frame logs through `board_state` with and without the new blocks
   present; assert the BoardState is identical. This proves the decision path cannot see the new data.

## 6. Build recipe (see the private file for commands)

- The 10-12 phase-2 binary and the 10-16 phase-3 probe were built the same way: **static glibc x86_64, Ubuntu 24.04,
  gcc-13 13.3.0, `-O2 -static`, bare compile-unit name**. It runs on the emulator's Android kernel (4 captures, 0 read
  errors). The pinned script `build_sampler.sh` refuses any other gcc, records a receipt (compiler, libc, binutils,
  source and output hashes) and compares against a reference binary.
- **Proven:** rebuilding the phase-2 source on a fresh Ubuntu 24.04 pod reproduced the reference binary
  **byte-identically** (BYTE_IDENTICAL).
- The production v2 reader came from a different, unrecorded toolchain (GCC 15.2). A merged reader built with the
  gcc-13 recipe is therefore a **different binary from the live one even when its v2 output is unchanged**. This is the
  one real risk of the merge, and the validation battle below is what retires it: v2 fields must match the old reader's
  frames at the same tick (the phase-2 alignment check had 9,111 of 9,118 identical body rows; require at least 99.9%).
- Steps: (1) add the phase-3 block to the v2 source behind the new flag (the probe source is already a superset of
  phase 2); (2) the device-free fixture suite (22 phase-2 fixtures, 17 phase-3 fixtures, the JSON contract check) plus
  new fixtures for the degrade rule and the restart re-emit; (3) build with the recipe on a pod; (4) copy the binary
  and receipt back, check the hash on the device before it runs, stop it by exact PID.
- Keep the binary name containing the sampler name: `live_play`'s end-of-match cleanup then stops it with the reader
  (the side probe avoided the name on purpose, and that is why it outlived cleanups; a merged reader should die with
  the match). Keep the exact-PID stop as well.

## 7. One-battle validation plan

One owner classic battle, icebow deck, dry-run, one `live_play` process (see `READER_VALIDATION_1016.md`, Concerns 1-2).
The merged reader runs as the **main** reader with `--log-frames`, and the old phase-3 side probe runs **beside** it as
an independent second reading of the same bodies.

| # | check | pass |
|---|---|---|
| S1 | game build unchanged, binary hash on device = receipt | exact |
| S2 | budget table in section 3, from the stream's own `read_us` | all rows |
| S3 | v2 fields vs the same ticks of the side probe's v2 block (x, y, hp, state) | at least 99.9% identical rows |
| S4 | new fields vs the side probe's at the same tick and generation id (target, progress, load, buffs) | at least 99.9% identical (rows at different instants are not compared) |
| S5 | `validate_p3.py` on the stream's blocks, unchanged | V1, V2, V3, V4, V5, V8, V9, V10 as in `ATTACK_PHASE_1016.md` (PASS); V6 and V5L as before (known) |
| S6 | `sim_unit_state` vs live on matching situations: slowed Knight steps 35, Tesla hidden/up, X-Bow hit every 8 ticks, river jump | same buckets |
| S7 | the BoardState identity replay (section 5, last item) | identical |
| S8 | the battle's end: reader stops with the match, no orphan process | no process left |

Stop rules: S1, S3 or S7 failing stops the merge (the live reader would change). S2 failing means drop the guarded
degrade rule's thresholds or a field group, not the v2 fields.

## 8. Concerns

- **The toolchain change (section 6)** is the only way this affects live play, and only if the flag is on.
- **V6 is a known FAIL** (a frozen body has no attack component, so the validator gets no frozen interval) and **V5L
  FAILs on one capture**; both predate this and are not caused by the merge.
- **Hit instant at 2-tick sampling.** A single tick-wide hit event cannot be seen live; only crossings between samples.
  Training on `hit` with the one-tick window would show the model a cue it never gets live. Use `hit_window_ms=100`
  (or the crossing rule) when training.
- **Mega Knight wind-up and Tesla rise** are not resolvable from the stream at 2-tick sampling (0.5 s rise, zero-speed
  wind-up). A 50 ms reader interval is a separate live change.
- **SIM gaps.** The SIM extractor could not exercise a Mega Knight jump (see `sim_unit_state` tests: the dash did not
  start in the two scenarios tried); river jump, charge, deploy, tunnelling-by-flag are covered. Taunt is classified
  by name only and has no SIM test.
- **Buff totals.** The SIM stores remaining ms only; `slow_frac` needs a memo kept across calls and reads 1.0 for a buff
  first seen mid-way. Live has the total. Compare fractions only after a buff has been refreshed once, or give the SIM
  the same total from the card table.
