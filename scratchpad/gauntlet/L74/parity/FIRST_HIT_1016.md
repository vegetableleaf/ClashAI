# First-hit and hit-speed check, SIM vs live (2026-10-16)

Owner question: units have a first hit that differs from their steady hit speed; if the SIM models it wrongly, many fights
change. Checked two ways: A) the card tables against the live client's decoded tables, B) the live frame logs.
Scripts: `first_hit/` (`table_compare.py`, `report_tables.py`, `measure.py`, `opp_presence.py`; outputs `measure.json`,
`measure_out.txt`, `TABLE_FULL.md`, `table_compare.json`). Decoded JSON fields only; no layout, no addresses printed.

## Verdict

1. **The table the 20261016-linux runtime really runs matches the live tables on every first-hit field.** Not one
   mismatch in LoadTime, HitSpeed, DeployTime, LoadFirstHit or any other timing-looking raw column, over the 341 units
   both tables share. The activation stamp's `cards_vintage: 15.535.29 client` is the **wheel's
   default file**, not the table the battle loads (see "Which table"). So (measured, A) the owner's worry does not
   come from a wrong table value for the runtime in use.
2. **The wheel's own default table (15.535.29, `cards-15.535.json`, `calibration cards.CARD_TABLE = client15535`)
   does differ from live in 8 units** (below). It only matters for a consumer that does not pass
   `cards.CARD_TABLE = client160402017_20261006`.
3. **The first-hit model itself is right on the cards that can be measured** (measured, B): over 26,435 frames of 14
   main-account logs, ranged first shots land at the predicted tick (median deviation 0.0 ticks over the 17 rows, ranged
   and melee, with n >= 5; 15 of them within 1 tick, the 2 others below) and all 19 measured cadences are within 1 tick
   of HitSpeed / 50. One unexplained residual: Goblin Giant's Spear Goblins (below).
4. **Not testable here**: melee first hits of the struggle cards (Mega Knight, Prince, Mini PEKKA, ...). They appear
   in 2-3 clean runs each, too few (see "Not checkable").

## Which table the runtime runs (evidence)

- `pipeline/royale_heroiw.py`: `ENABLED` for RUNTIME_ID in `20261012`, `20261012-linux`, `20261016-linux`;
  `engine_options()` = `{'calibration_overrides': {'cards.CARD_TABLE': 'client160402017_20261006'}}`;
  `pipeline/royale_env.py:184` builds `RustEngine(**heroiw.engine_options())`; `parity/fights.py:424` and
  `parity/driver.py:80` pass the same override. RoyaleSim `card.rs`: `EMBEDDED_CARDS_160402017_JSON` is compiled in
  beside the 15.535 file, and that table's own values are used (`CardTable::Client160402017`).
- The wheel default stays 15.535: pin 4fd4d54 (0.1.35) `data/calibration.json` has `CARD_TABLE = client15535`; the
  embedded `cards.json` hash c68d6c01 equals `cards-15.535.json` (rt35 build manifest).
- The stamp is the file hash and file vintage of the default `cards.json` (`rust_engine.py card_table_stamp`:
  "disk_at_construction"; `card_table_source()` = "embedded"), so it reads `15.535.29` whatever the override says.
- **Unverified**: I could not run the Linux 0.1.35 wheel here (the laptop's `royalesim.pyd` is the 10-01 build and
  rejects the key). One call settles it on the VM: `Battle(...).card_table()` should return
  `cards-160402017-20261006.1`.
- Runtimes outside `ENABLED` (`20261006`, `20261006-linux`, `unpinned-linux`, the default pin) run the 15.535 default.
  Anything trained or scored there carries the 8 mismatches.

## A) Table comparison

Sources: SIM runtime table `RoyaleSim/data/derived/cards-160402017-20261006.json` (16.402.19); wheel default
`cards-15.535.json`; live = `apktables/out/device_builds/20261012T221627332682Z-50188/cards.json` (APK 160402012 plus
the 2026-10-12 device update; same extractor, raw columns compared too). `cards-160402017.json` (install-time 16.402.2)
differs from live only in LavaHound, MinionGiant and GoblinDummy, as expected before the 10-06 update.

Engine reading (combat.rs `attack_step_progress`): a fresh lock starts progress at LoadTime + 50 and the shot leaves when
progress reaches HitSpeed, so **first shot = (HitSpeed - LoadTime) / 50 - 1 ticks after the lock, then every
HitSpeed / 50 ticks**. LoadTime therefore sets the first hit; HitSpeed the cadence. `LoadFirstHit` (live: **only the
Sparky**, ZapMachine, 3000/4000) starts the timer at deploy end.

### Mismatches (15.535 default vs live; the runtime table equals live)

| unit (card) | field | 15.535 | live = runtime | first hit after lock, old -> live | cadence, old -> live | seen as opponent in 105 main matches |
|---|---|---|---|---|---|---|
| Wizard, WizardHero, Wizard_EV1 | LoadTime | 1000 | 900 | 7 -> 9 ticks | 28 (same) | Wizard 7 |
| LavaHound | LoadTime, HitSpeed | 300, 1300 | 500, 1500 | 19 -> 19 (same) | 26 -> 30 | 2 |
| MinionGiant | LoadTime, HitSpeed | 700, 1500 | 900, 1700 | 15 -> 15 | 30 -> 34 | 0 |
| Ronin | LoadTime, HitSpeed | 1000, 1400 | 900, 1300 | 7 -> 7 | 28 -> 26 | 5 |
| MiniZapMachine (card Mini Sparkys) | LoadTime, HitSpeed | 1400, 2200 | 1500, 2300 | 15 -> 15 | 44 -> 46 | 5 |
| GoblinDummy | LoadTime | 700 | 800 | 7 -> 5 | 22 (same) | (dummy unit) |

Pattern: five of the six edits move LoadTime and HitSpeed together by 100 ms, so the **first-hit delay is unchanged and
only the cadence is off by 2 ticks (4-8 %)**. Only the Wizard family (first shot 2 ticks too early in the old table)
and GoblinDummy change a first hit. Also in the 15.535 raw diff, not first-hit: `MegaMonk.AttackSequence` 1 -> 0,
`SkeletonContainer(New).DeathSpawnDeployTime` 500 -> null.

Everything else is equal: DeployTime of every unit (1000 for troops, 3500 X-Bow, 3000 Golem), all LoadTime/HitSpeed,
the lone LoadFirstHit unit. Full 371-unit listing (LT/HS/Deploy per table, flag column): `first_hit/TABLE_FULL.md`.

### Priority cards (LoadTime/HitSpeed/DeployTime in ms; identical in all three tables unless noted)

| unit | LT/HS/Deploy | | unit | LT/HS/Deploy |
|---|---|---|---|---|
| Xbow | 0/400/3500 | | Mega Knight | 1200/1700/1000 |
| Tesla, Tesla_EV1 | 700/1100/1000 | | Mini PEKKA | 1100/1600/1000 |
| IceWizard, IceWizardHero | 1200/1700/1000 | | Barbarian / AngryBarbarian / RageBarbarian | 1000/1400, 900/1400, 400/800 |
| Knight, Knight_EV1, KnightHero | 700/1200/1000 | | Firecracker | 2350/3000/1000 |
| Skeleton, Skeleton_EV1 | 600/1100/1000 | | Witch / DarkWitch | 400/1100, 550/1300 |
| Skeleton Balloon / Balloon | 200/300, 1800/2000 | | Golem / Golemite | 1500/2500/3000, 1500/2500/1000 |
| Prince | 900/1400/1000 | | ElixirGolem1/2/4 | 300/1100/1000 |
| Recruit (Royal Recruits) | 800/1300/1000 | | Giant, Valkyrie, HogRider, RoyalHog | 1000/1500, 1400/1500, 1000/1600, 800/1200 |
| Wizard | **1000 -> 900**/1400 | | LavaHound | **300/1300 -> 500/1500** |

The hero Ice Wizard has the same 1200/1700 as the normal one. Evolutions copy their base (Tesla_EV1, Knight_EV1,
Skeleton_EV1 equal).

## B) Live measurement

Data: frame logs `live_play_20261016_{115958, 121354, 121550, 122204, 123836, 124439, 124905, 125246, 125620, 130008,
130346, 130952, 131434, 131812}` (14 logs, 26,435 frames; main account = own princess hp 4424 ladder or 3052 owner
classic, with an own X-Bow or Tesla on the board; no 4392 / 4656 bait logs). **The 10-15 logs carry no
`ents_state` / `proj`**, so they give no engagement state and are not used for timing (they are used only to count how
often a card appears: `opp_presence_out.txt`). Frames are 2 ticks apart (96.8 %), so every delay is +-1 tick.

Method (`first_hit/measure.py`, header has the definitions): entry = first frame of a body in `behavior_state_raw` 2.
Ranged delay = first projectile whose source is that body, minus entry (towers: each idle-to-engaged edge after 40
idle ticks; troops: first run only, they leave the deploy with the load timer at 0). Melee delay = first isolated hp
drop of an enemy in reach (a repeat of the same drop one HitSpeed later is required, DOT excluded), "clean" = no other
own-side troop within 3 tiles of the victim. The SIM column is the engine formula above applied to the table row, not
a fresh SIM run.

### Ranged, per card (ticks; mode share = fraction within +-1 of the mode)

| card | n | measured median (IQR) | SIM = live table | cadence measured / table |
|---|---|---|---|---|
| Princess Tower | 185 | 15 (14-16) | 15 | 16 / 16 |
| Ice Wizard (incl. hero) | 66 | 9 (8-10) | 9 | 34 / 34 |
| X-Bow | 45 | 7 (6-8) | 7 | 8 / 8 |
| King Tower | 28 | 8 (8-10) | 9 | 20 / 20 |
| Minion Horde | 12 | 10 (8-10) | 9 | 24 / 24 |
| Bomber | 11 | 2 (2-4) | 3 | 36 / 36 |
| Goblin Gang (Spear Goblins) | 11 | 9 (8-10) | 9 | 32 / 32 |
| Firecracker | 8 | 12 (12-12) | 12 | n/a |
| Lava Hound | 7 | 20 (20-20) | 19 | **30 / 30** (15.535 default: 26) |
| Witch | 7 | 13 (13-14) | 13 | 22 / 22 |
| Furnace (Fire Spirits) | 6 | 10 (10-10) | 9 | 34 / 34 |
| Minions | 6 | 9.5 (9-10) | 9 | 24 / 24 |
| Baby Dragon | 4 | 5.5 (5-6) | 5 | 30 / 30 |
| Mega Minion | 4 | 7 (6-10) | 7 | 30 / 30 |
| Bowler | 3 | 9 (8-10) | 9 | 50.5 / 50 |
| Electro Dragon | 3 | 14 (11-20) | 13 | 42 / 42 |
| Goblinstein (doctor) | 3 | 8 (7-8) | 9 | 36 / 36 |
| Musketeer | 2 | 13 (12-14) | 13 | 20 / 20 |
| Blowdart Goblin | 2 | 6 | 6 | 16 / 16 |
| Sparky (LoadFirstHit) | 1 | 20 | 19 after a 60+ tick walk (engine doc: 18-19) | n/a |
| **Goblin Giant (Spear Goblin riders)** | 6 | **14 (13-14)** | **9** | n/a |

Every row except the last is within 1 tick of the prediction; all 19 cadences with data (ranged and melee tables) are
within 1 tick of HitSpeed / 50.
The Lava Hound's cadence (n = 12 gaps, median 30 ticks = 1500 ms) is the one measured mismatch against the 15.535
default (26): this **confirms the live HitSpeed, 1500**, with the live table. Its first-hit delay (20 vs 19) cannot tell
LoadTime apart, because HitSpeed - LoadTime is 1000 in both tables.

### Melee (small n, see Not checkable)

| card | n clean (runs) | measured median | SIM | note |
|---|---|---|---|---|
| Knight | 9 (57) | 8 (8-10) | 9 | consistent; 3 crowded runs: 8 |
| Tesla (after it surfaces) | 6 (36) | 8 (6-8) | 7 | +1 tick, inside the sampling error; 4 crowded: 7 |
| Skeletons / Skeleton Army | 0 clean; 10 / 5 crowded | 10 (6-22) / 14 (14-20) | 9 | not a usable number: swarm hits overlap on one victim |
| Royal Hogs, Witch skeletons | 3 crowded each | 8 / 9.5 | 7 / 9 | too few |

Hog Rider by hand (log 130952): lock 2887, first hit on the Tesla at 2898 = 11 ticks, the predicted 11 (n = 1).

### Deploy length (state 4, ticks) vs DeployTime / 50

Skeletons 18 (n 187), Ice Wizard 20 (151), Skeleton Army 20 (139), Knight 19 (67), X-Bow 69 (48; table 70), Tesla
19.5 (40), Golem 60 (3; table 60), ordinary troops 17-20 with n >= 3: all agree with the table within the sampling
step. Exceptions (table 20, except Graveyard which has no unit row): **Furnace 10 (n 30), Goblin Drill 10 (22), Graveyard 10 (41), Goblin Giant 15.5 (8)**.
Not a table mismatch (live table equals the SIM table); these are different "deploying" semantics (spawner/burrow
cards, state 4 may end when the first spawn or dig starts) or a late first frame, not checked further.

## Mismatches confirmed by BOTH the live table and the live measurement

| card | field | SIM (15.535 default) | live | evidence | n |
|---|---|---|---|---|---|
| Lava Hound | HitSpeed | 1300 | 1500 | table; measured cadence 30 ticks | 12 gaps, 7 first shots |

Nothing else is confirmed by both; the other seven mismatching units (Wizard x3, MinionGiant, Ronin, MiniZapMachine,
GoblinDummy) are confirmed by the live table only (no such card was measurable in the 14 logs).

## Proposed patch (NOT applied)

The runtime table already carries all eight corrections, so no change to `cards-160402017-20261006.json` is needed.
Two options, owner's choice:

1. **Config (preferred, no table change)**: make the default `calibration.json cards.CARD_TABLE` =
   `client160402017_20261006` (RoyaleSim), or add the other runtime ids to `pipeline/royale_heroiw.ENABLED`. Effect:
   Wizard family first shot 7 -> 9 ticks; LavaHound 26 -> 30, MinionGiant 30 -> 34, Ronin 28 -> 26, MiniZapMachine
   44 -> 46 ticks per hit. Needs a re-baseline of anything scored on `20261006*` / the default pin.
2. **Data (not recommended)**: editing `cards-15.535.json` would break the older client's replay parity, because those
   values are what the 15.535 client had. If done anyway: `Wizard`, `WizardHero`, `Wizard_EV1`
   LoadTime 1000 -> 900; `LavaHound` LoadTime 300 -> 500, HitSpeed 1300 -> 1500; `MinionGiant` 700 -> 900, 1500 -> 1700;
   `Ronin` 1000 -> 900, 1400 -> 1300; `MiniZapMachine` 1400 -> 1500, 2200 -> 2300; `GoblinDummy` LoadTime 700 -> 800.

## Which fights the old values would affect

Only runs on the 15.535 default: the Wizard family (7 of 105 logged main-account matches), Ronin (5), Mini Sparkys (5),
Lava Hound (2; the owner-named lava_hound archetype, n = 37 in `exploit/STRUGGLE.txt`: the SIM Hound would have hit
15 % faster than live). MinionGiant: 0 of 105. In every case the damage rate or first shot is off by 2 ticks
(100 ms) at most per cycle. Struggle cards Mega Knight, Skeleton Balloon, Mini PEKKA, Barbarians, Firecracker, Skeleton
Army, Golem, Elixir Golem, Witch, Prince, Recruit: **table-equal in all three**.

## Not checkable, and why

- **Melee first hits of Mega Knight, Prince, Mini PEKKA, Pekka, Barbarians, Valkyrie, Golem, Elixir Golem, Royal
  Recruits**: they appear in the 14 logs 2-3 times each (Mega Knight 2 runs, Mini PEKKA 2, Prince 3, Golem 7, Valkyrie
  6) and the melee target / attack phase is not a logged field (READER_VALIDATION_1016: NOT AVAILABLE, phase-3 RE). Table
  parity only.
- **Skeleton Barrel, Elixir Golem, Royal Recruits as ranged**: none; melee units, same limit.
- **Nested `AttackSequenceList` timings** (Berserker, Dagger Duchess, Evo Mega Knight, Evo Musketeer, Evo Princess,
  Three Musketeers, Evo Angry Barbarian, Evo Electro / Inferno Dragon, Hero Bowler / Electro Wizard / Elite Archer): the
  decoded `cards.json` keeps only the top-level columns (`raw`), so per-entry `AttackStartDelay` / `VisualHitSpeed` /
  `CustomFirstProjectile` are not comparable from JSON. The runtime table has the live `AttackSequence` columns
  (equal); the nested entries need the 16.402 raw pack, which is not in the repo.
- **Tesla's rise**: the first hit of a hidden Tesla is the 0 -> 2 edge plus the shot; the rise itself (<= 0.5 s) is
  inside one sample.
- **Overlay**: no 10-15 timing (no `proj`).

## Concerns

1. The stamp wording `cards_vintage: 15.535.29` is misleading for a run that overrides the table; verify once with
   `Battle.card_table()` on the VM (unverified here).
2. The SIM column is the engine's documented formula plus the table row, not a SIM replay of the same scenarios. A
   replay of the Goblin Giant case would settle the one residual: measured 14 vs 9 ticks (n = 6, mode share 1.0, **all six in one log**, 125620, so possibly one match's two or three
   Giants). Candidate cause (untested): the rider's shot is keyed to the Giant body's engagement, not the rider's own.
3. Melee numbers are low-n and hit-attribution is inferred from hp drops; read them as consistency checks only.
4. Tesla +1 and Bomber -1 are within the 2-tick frame step; no action.
