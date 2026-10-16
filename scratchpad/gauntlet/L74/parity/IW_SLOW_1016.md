# Ice Wizard slow in the SIM vs live (2026-10-16)

**Question.** A harness worker reported: "in 0.1.35 the Ice Wizard projectile carries buff id 0 and never slows anything
(probed)". If that were true, every model trained here learned an Ice Wizard that does not slow.

**Answer: (c) contradicted.** Every RoyaleSim runtime I could run slows the target of an Ice Wizard hit, in both
forms. The amount matches the live game: -30% walk speed, attack progress 35 per tick instead of 50, 2500 ms that
re-arms on every hit. The Hero form's freeze and its 2 s after-slow also match. The "buff id 0" came from reading the
save format wrongly (section 2). The harness problem behind the report is real, but it is a different one: the harness
cannot *seed* a slow that is already on a body when a fight starts. Section 5 gives a tested fix.

Scripts: `iw_slow/` (`probe.py`, `analyze.py`, `tower.py`, `freeze_sim.py`, `inject.py`, `live.py`, `live_p3.py`,
`dump_table.py`, `savebuf.py`). Bulk probe JSON is in `.foreman/scratch/iw_slow/`. Text outputs are next to the scripts.

## Verdict

| runtime | IceWizard (base) | IceWizard@hero (shot slow + deploy chill) | hero ability (freeze + after-slow) | how established |
|---|---|---|---|---|
| **20261016-linux** (royalesim 0.1.35, 4fd4d54) | **SLOWS** -30% walk, 35/tick attack, 2500 ms | **SLOWS** same numbers (IceWizardHeroSlow / IceWizardHeroCold) | **FREEZES** (progress + load held) then **SLOWS** 2000 ms | probed: laptop's 0.1.35 Windows wheel, provenance `4fd4d54 clean` |
| **20261012-linux** (royalesim 0.1.33, cacb700) | **SLOWS** (not probed directly) | **SLOWS** (not probed directly) | **FREEZES / SLOWS** (not probed directly) | (b) **no 0.1.33 wheel on this laptop** (`research/ext/Royale-20261012/runtime` does not exist; no wheel or pip cache). From source: v0.1.33→v0.1.35 does not touch the buff path (below), and both the older 0.1.13/0.1.17 and the newer 0.1.35 slow |
| 20261006 (0.1.17, d088f53), older | **SLOWS** (same numbers) | n/a (the table has no hero form) | n/a | probed |
| 20261005 (0.1.13, 015f9b0), older | **SLOWS** (same numbers) | n/a | n/a | probed |

What ties 0.1.33 to 0.1.35: `git diff v0.1.33 v0.1.35` changes `status.rs` by one serde field (`BuffHit::reach_rider`,
for Rage on attached riders only). `combat.rs` gains one `held` projectile flag (for dash immunity). Neither file's
change touches the attack buff. Nothing changes under `data/derived/`. The `calibration.json` diff touches 11 keys, and
none of them is about buffs or speed (DASH_*, STRIKE_*, ROLLING_*, THROW_PICK, ...). Both versions build the same
`client160402017_20261006` table. The status-effect engine (composition, the hold, `attack_buff`) has been in the code
since 185bc9d (2026-09-21, inside v0.1.0). **To close the gap with a direct probe, the lead can run:**
`pip download royalesim==0.1.33 --no-deps --platform win_amd64 --only-binary=:all: -d <new dir>`, unzip it, then
`python iw_slow/probe.py <dir>` and `python iw_slow/analyze.py <out.json>`. I did not download anything (see Concerns).

## 1. SIM probe (0.1.35; 0.1.17 and 0.1.13 give the same base-form numbers)

Setup: level 11, card table `client160402017_20261006`, blue's princess towers down. The red target is alone. The
controls are no shooter at all, and a Musketeer (ranged, no buff). Unit: 1 tick = 50 ms. Positions are in subtiles
(18,000 per tile).

| measurement | no shooter | Musketeer | IceWizard base | IceWizard hero |
|---|---|---|---|---|
| Giant walk step, subtiles/tick (median) | 936 | 936 | 922 before the first hit → **648** after (×0.70) | 921 → **648** |
| Knight attack-progress gain per tick | 50 (259/259) | 50 | **35** (203 ticks) | **35** (193 ticks) |
| Knight hit interval on the king, ticks | 24 ×10 | 24 | **32-35** (1200 ms / 35 = 34.3) | 24, then **33-35** |
| red princess tower's hit interval on the shooter, ticks | — | 16 ×5 | **22-23** (800 / 35 = 22.9) | 16, 16, then **21-23** once slowed |
| buff on the target (id, ms at application) | none | none | id 1 `IceWizardSlowDown`, 2500 | id 67 `IceWizardHeroSlow`, 2500 |
| slow after the shooter is Rocketed (last hit → buff gone → walk) | — | — | last re-apply t127, buff gone at t177 (**50 ticks = 2500 ms**, -50 ms per tick), walk back to 936 | t103 → t153 (**50 ticks**), back to 936 |
| deploy chill when played from hand 2 tiles from the Giant | — | — | slowed from tick 1 (id 1) | `IceWizardHeroCold` (id 66) for ticks 1-49, then the shot slow (67) |

Hero ability (`giant_hero_press` and `freeze_sim.py`, a Knight swinging at the king):

- Press accepted at t70. Ticks 74-76: dummy buff (id 2, 150 ms) and stun_ms 150.
- Ticks 77-174: `IceWizardHero_FreezeBuff` (id 68, 999,999 sentinel). Walk step 0. **Attack progress held at 3880 and
  load timer held at 300**, for 98 ticks.
- Then the after-slow (id 1, 2000 ms): 40 ticks at a 648 walk step. Progress +35/tick, load -50/tick (the load timer is
  not scaled).

Code path at 4fd4d54:

- `card.rs:3590-3593`: `RawProjectileObj::target_buff` / `buff_time_ms` ("ice_wizardProjectile -> IceWizardSlowDown
  2500 ms").
- `card.rs:10405-10410`: loaded onto `CardDef::attack_buff`.
- `status.rs:9-44`: the composition law. Speed goes to `state.rs effective_speed` / `buffed_speed` (25895-25940).
  Hit speed is `compose(HitSpeed, 50)` per tick on attack progress.
- Upstream tests pin this: `tests/status.rs` item 3 says "the Ice Wizard's hands it IceWizardSlowDown, which scales the
  victim's walk and its attack advance".

Embedded table (`dump_table.py` → `table35.txt`):

- `projectiles/ice_wizardProjectile/target_buff = IceWizardSlowDown`, Speed / HitSpeed / SpawnSpeed multiplier -30,
  `buff_time_ms 2500`.
- The hero: `IceWizardHeroProjectile` → `IceWizardHeroSlow` -30/-30/-30, 2500, `enable_stacking`. Deploy area
  `IceWizardColdHero` → `IceWizardHeroCold` -30, 2500. Ability: `IceWizardHero_FreezeBuff` (-100), after-buff
  `IceWizardHero_SlowBuff`.
- APK 160402012 (`apktables/out/.../characters/ice_wizard.toml:60-98`, `hero_form/ice_wizard_hero.toml`) has the same
  values.

## 2. Where "buff id 0" came from

`Battle.save()["ents"]["buffs"]` is a **flat** list. Each entity owns `len(buffs) // len(alive)` slots: 4 in 0.1.35,
with 24 slots for 6 entities. Entity *i* owns `buffs[4i : 4i+4]`. Reading `buffs[i]` (one entry per entity) returns
entity *i/4*'s slot, which is usually an empty tower slot with id 0. With the correct indexing, a slowed Knight shows
`{"id": 1, "ms": 1050, ...}` (`savebuf.py`). Ids are interned per table, one past the row index. In 0.1.35's 160402017
table: 1 IceWizardSlowDown (the base shot and chill, and also the after-slow), 2 freeze dummy, 66 IceWizardHeroCold,
67 IceWizardHeroSlow, 68 IceWizardHero_FreezeBuff. **Do not hard-code these ids.** Read them from a probe, as
`inject.py` does.

## 3. Live truth

The live data is hero form only. Icebow plays the Hero IW, and no capture holds a base `IceWizardSlowDown`. So the
base form's live numbers are the APK table's (identical to the hero's slow row), not a live measurement.

Phase-3 captures `p3_20261016T133738` and `p3_20261016T134735` (`live_p3.py` → `live_p3_1016.txt`). Each attacker's
attack progress per tick, over sample pairs with the same target and the same buff set:

| state | buff on the body (phase-2 row) | step per tick | n intervals |
|---|---|---|---|
| (a) unbuffed | none | **50** (3,095 of 3,102; 4×100 and 3×25 are sample-gap artefacts) + **50** (2,252 of 2,258) | 5,360 |
| (b) Hero IW ability freeze | `IceWizardHero_FreezeBuff` (-100/-100/-100, 999,999 sentinel) | **held**: the attack component is absent (`no_component`) for the whole freeze, and progress **and** load come back unchanged (E-Wiz hero: load 900 at t2185, 800 after the freeze at t2289; Pekka 300 then 250, the same 250 after). Lasts about 100 ticks (t2187→2287, t3239→3339) | 4 bodies, 2 presses |
| (c) after-slow | `IceWizardHero_SlowBuff`, 2000 ms, -30/-30/-30 | **35** (19/19) | 19 |
| (d) shot slow (Hero IW projectile) | `IceWizardHeroSlow`, 2500 ms, -30/-30/-30 | **35** (125/125, 140/140): Goblin Demolisher, Bomb Tower, Battle Healer, Baby Dragon, P.E.K.K.A, Mega Minion, E-Wiz hero, **PrincessTower** | 265 |
| deploy chill | `IceWizardHeroCold`, 2500 ms, -30 | **35** (3/3) | 3 |
| (d') plain Ice Wizard projectile | `IceWizardSlowDown` | **not observed live** (APK row: -30/-30/-30, BuffTime 2500) | 0 |

**Live HitSpeedMultiplier.** -30, read from the buff rows. The measured step is exactly 35 = 50 × 0.70, so the attack
speed is -30%. The freeze is -100 and holds both the progress and the load timer. The SIM is identical, including the
held load (`freeze_sim35.txt`). The load timer drops a flat 50 per tick while slowed, both live (E-Wiz 800→700 in 2
ticks) and in the SIM.

**Live movement** (`live.py` / `live_p3.py`: per-tick displacement on moving samples, slowed ÷ unslowed for the same
card):

- `IceWizardHeroSlow`: Bowler 0.700, Furnace 0.694 / 0.705, Hero Knight 0.695, Goblin 0.700, Fire Spirits 0.696-0.706,
  Ice Spirits 0.703, Bat 0.703, Dark Witch 0.707, Royal Giant 0.707, Elixir Golem pieces 0.677-0.707, Goblin Demolisher
  0.697, Battle Healer 0.696, Mega Minion 0.696, Baby Dragon 0.697, E-Wiz hero 0.699, P.E.K.K.A 0.684.
- `IceWizardHero_SlowBuff`: P.E.K.K.A 0.677, Mega Minion 0.707, Baby Dragon 0.694.
- Outliers have their own movement mechanics: Royal Hog 0.53 (river jump), Prince 0.88 (charge), Valkyrie 0.95,
  Skeleton 0.47-0.53 (pushes), Miner (tunnel), Barrel Goblin (barrel flight).
- **Live is -30% walk, the same as the SIM's 648 / 922-936 = 0.69-0.70.**

**Live tower cadence under the slow** (a PrincessTower carrying `IceWizardHeroSlow`):

- 10-16 m2: 16, 16 unslowed vs 21, 23, 24 slowed.
- 10-12: 15-17 (n=26) unslowed vs 22, 23, 23, 24 slowed.
- SIM: 16 vs 21-23. **Match.**

Buff timers live: 2500 / 2000 ms, -50 per tick, refreshed on each hit about every 34 ticks
(`READER_VALIDATION_1016.md` row 81; `live_1016.txt`).

Side note on the phase-3 validator's V6 "no qualifying intervals": `validate_p3.py:375` (and `linear()` at :168) keeps
an interval only when `seq_idx == -1`, but all 5,782 attack intervals kept above have `seq_idx == 0`. So V6 skipped
everything. The live step under the slow is 35, as predicted.

## 4. Patch proposal for the engine

**None.** The SIM already slows: the data is present, the loader reads it, the engine applies it, and the magnitudes
match live. A fork patch would add nothing, and no re-baseline is needed for this.

## 5. What to fix instead: seeding a slow at fight start in the harness (not applied; `fights.py` is read-only for me)

`fights.py:1287-1301` (its setup) maps only `STUN_BUFFS` to `stun_ms`. Any other buff on a body at t0 is flagged
`status_unset:<name>`.

- **Measured:** in the latest `fights_newkeys/after` run, 21 of 126 phase-2 fight windows (16.7%) start with an
  `IceWizardHero*` buff on some body that the SIM replay does not carry. The flag counts across all outputs are
  `status_unset:IceWizardHeroSlow` ×1 in 52 records, ×2 in 24, ×4 in 4, plus `IceWizardHero_SlowBuff`.
- **Tested seam** (`inject.py` → `inject35.txt`): write the body's first free buff slot (`buffs[i*slots + k]`) with the
  probed id and the live `remaining_ms_raw`, then call the harness's own `mechanics.load_edited` (rehash-once). A plain
  `load` refuses the edit: a missing `state_hash` is refused, and so is a stale one. Result on a Knight hitting the king:
  the untouched control runs 50/tick with 24-tick hits. With 2500 ms injected: **35/tick for 49 ticks**, a 33-tick hit,
  then back to 50 and 24.
- **Proposal:** in `fights.py`'s t0 setup, a name → id map built once per engine by a probe like `inject.hero_slow_id`
  (shot slow, chill, after-slow; the freeze stays as `stun_ms` plus held progress). For each live buff at t0 in that
  map, write the slot with `ms = remaining_ms_raw`. Leave `pulse_*` / `source` at 0: these buffs have no pulse.
- **Test:** the A/B above as a unit test, plus a fight whose t0 carries `IceWizardHeroSlow`. The SIM victim's step
  should be 35 until the remaining ms run out.

## 6. Impact estimate

- **Training:** no impact from the claimed bug. Every probed runtime (0.1.13, 0.1.17, 0.1.35) slows, and 0.1.33 has
  the same buff path in source. The SIM Ice Wizard that models trained against slows by the live amount.
- **Parity harness:** 16.7% of fight windows (21/126, n=3 matches) start with an unseeded IW slow. Each one carries up
  to 2.5 s of 30%-faster victims in the SIM. For a speed-60 victim that is 1.19 instead of 0.83 tiles/s (about 0.36
  tiles/s too fast while the timer runs), and it swings 43% more often (50 vs 35 per tick). It is a setup error in those windows only. Its size in
  the scoreboard is untested. Proposed measurement: rerun `fights.py` on the 3 phase-2 matches with section 5 applied
  and compare per-card scores for the 21 windows.

## Concerns

- **0.1.33 was not probed directly.** No 0.1.33 wheel exists on the laptop, and downloading one needs the owner's OK.
  The verdict rests on the source/data diff and the probed runtimes on either side of it. The Linux wheels (pod
  training) were not probed. They are built from the same source.
- The base-form slow was not seen live (icebow plays the hero). Its live magnitude comes from the APK table, which has
  the same columns as the hero rows that were measured.
- The tower slow live is n=7 slowed intervals over 2 matches.
- The SIM's Giant walk step (936 subtiles = 52 millitiles per tick) and live slow-walker steps (about 44 millitiles per
  tick for speed-45 cards) differ. That is a walk-speed question separate from the slow, and the ratio, not the base
  speed, is what this note compares.
- The freeze duration was compared on 2 live presses only (about 100 ticks each; the SIM gives 98-101).
