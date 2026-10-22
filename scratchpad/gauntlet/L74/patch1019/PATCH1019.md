# PATCH1019: the 2026-10-19 Clash Royale balance update vs our SIM data (W23, 2026-10-22)

Labels: **(a) measured**, **(b) plausible but untested**, **(c) contradicted**. Fetched pages are quoted as data.
Values at level 11 are the blog's convention ("Cards are scaled at Level 11"). Our scaling is `floor(base x M / 100)`
with unified-level multipliers M = 256 (L11), 372 (L15), 409 (L16).

## 0. Answer first

- **Icebow on 10-19: only Skeletons changed (a).** X-Bow, Tesla (and evo), Ice Wizard / Hero Ice Wizard, Knight (and
  evo), Log, Tornado, Rocket, the crown towers and the tower troops did not change on 10-19. Sources: the official
  post, and the client's own tables (the device's update folder, 16.402.21 -> 16.402.22).
- **The SIM already has the 10-06 patch (a).** That includes X-Bow 58 -> 61, Hero IW freeze 89 -> 46 and Skeletons
  SummonRadius 700 -> 400. Training (`pipeline/royale_heroiw.py`) and parity (`parity/fights.py`) load
  `client160402017_20261006` (content 16.402.19).
- **The premise "every model trained since 10-19 learned on outdated stats" needs correcting (a).** Every SIM-trained
  model, before and after 10-19, used the same 10-06 table. That table went stale for live play at the 10-19
  update. What is stale: the 13 values in section 1, and 3 small 16.402.21 changes (section 3).
- **Patch time (a): 10-19, between the match logs starting 05:58:41 and 06:03:27 EDT.** Every exact-value tower hit
  before that is an old value, and every one after is a new value (section 2). The device's update folder has mtime
  10-19 06:03.
- **"Skeletons always split on middle tiles" is not a new rule (a, with the geometry b).** The client binary did not
  change, and the only formation value that moved is SummonRadius 400 -> 500. The split follows from that radius
  under the fork's existing ring law (section 1.1).

## 1. The change table

Sources:
- **[S1]** the official post <https://supercell.com/en/games/clashroyale/blog/release-notes/october-balance-changes-2026/>
  (dated 6 Oct 2026; its section "Balance Update – October 19th" says "we are implementing the seasonal November
  balance changes earlier, in mid-October").
- **[S2]** the client's tables: a read-only adb pull of `/data/data/com.supercell.clashroyale/update` on 10-22
  (fingerprint version **16.402.22**), decoded and diffed against the 10-12 pull (**16.402.21**). The diff is the
  whole update: 13 single-value lines (`tools/` below).
- Wiki api.php, checked as a third source: the Skeletons page has no 2026 history entries yet, and third-party
  write-ups (sportsdunia, accountshark, youmind) only carry the 10-06 half. **[S1] and [S2] agree on every item.**

"Ours" = the fork table `cards-160402017-20261006.json` (fin15 305aaafc, wheel 88f3fdcb; level-1 values).

| card | stat | [S1] quote (L11) | [S2] client value (level 1) | ours (10-06 table) | L11 | L15 | L16 | live (section 2) |
|---|---|---|---|---|---|---|---|---|
| **Skeletons** (ICEBOW) | spawn spread | "Spawn Spread: 0.4 → 0.5 tiles (+25%)", "will now always split when placed on middle tiles" | spells_characters.toml [Skeletons] SummonRadius 400 -> 500 | summon_radius_milli 400 | ring 461 -> 577 mt (fork law, level-free) | same | same | (a) shape change, section 2.1 |
| Evo Skeletons | spawn spread | not in the post | spells_evolved.toml [Skeletons_EV1] SummonRadius 400 -> 500 | evolutions[Skeletons_EV1] 400 | same | same | same | not separated |
| Dart Goblin (+ evo) | damage | "Damage: 151 → 143 (-5%)" | blowdartgoblin.toml Damage 59 -> 56 | 59 | 151 -> 143 | 219 -> 208 | 241 -> 229 | (a) 151 old / 0 new before, 0 old / 79 new after |
| Cannon Cart (+ broken form) | damage | "Damage: 212 → 202 (-5%)" | cannon_cart.toml Damage 83 -> 79 | 83 | 212 -> 202 | 308 -> 293 | 339 -> 323 | (a) 53 / 0 before, 0 / 10 after |
| Cannon Cart | mass | "Mass: 3 → 6 (+100%)", "no longer be pushed around by Goblins" | cannon_cart.toml Mass 3 -> 6 | 3 | - | - | - | (b) not measured |
| Minion Giant | damage | "Damage: 168 → 153 (-9%)" | minion_giant.toml Damage 66 -> 60 | 66 | 168 -> 153 | 245 -> 223 | 269 -> 245 | see 2.2 |
| Rune Giant | enchant linger | "Enchantment Linger Duration: 5s → 0.5s (-90%)" | giant_buffer_v2.toml FinishIfInstigatorDies 5000 -> 500 | 5000 | - | - | - | (b) not measured |
| Hero Electro Wizard | attack delay | "Removed Attack Delay after Ability" | electro_wizard_hero.toml AttackStartDelay = 500 removed (2 lines) | ability attack_start_delay_ms 500 | - | - | - | (b); the fork refuses this hero form (W9) |
| Electro Dragon (+ evo) | first hit | "First Hit Time: 0.7s → 0.5s (-29%)" | electrodragon.toml LoadTime 1400 -> 1600 (HitSpeed 2100: first hit 2100 - LoadTime) | load_time_ms 1400 | - | - | - | (b) not measured |
| Flying Machine | damage | "Damage: 171 → 179 (+4%)" | dartbarrell.toml Damage 67 -> 70 | 67 | 171 -> 179 | 249 -> 260 | 274 -> 286 | (a) 98 / 0 before, 0 / 23 after |
| Void | 2-4 target damage | "2–4 Target Damage: 296 → 307 (+3%)" | dark_magic.toml DarkMagicAOE_Damage_lv2 DamagePerSecond 1155 -> 1200 (100 ms hits; tower hit 20 unchanged) | 1155 | 295.7 -> 307.2 per hit | 429.7 -> 446.4 | 472.4 -> 490.8 | (b) troop hits only, not measured |
| Skeleton Barrel | death damage | "Death Damage: 145 → 163 (+12%)" | skeleton_balloon.toml BaseDamage 57 -> 64 | SkeletonContainer death 57 | 145 -> 163 | 212 -> 238 | 233 -> 261 | (a) 22 old / 3 new before (coincident values), 0 / 9 after |
| Skeleton Barrel Evolution | death damage | "Death Damage: 192 → 163 (-15%)" | skeleton_balloon_ev1.toml BaseDamage 75 -> 64 | 75 | 192 -> 163 | 279 -> 238 | 306 -> 261 | not separated |
| (shop) | CHRONOS_MAX_FREE_VALUE | - | globals.csv 10000 -> 15000 | - | not a battle value | | | - |

### 1.1 Skeletons: why "always split on middle tiles" needs no new rule

- (a) Only SummonRadius moved (400 -> 500, base and evo). SummonNumber 3, the Skeleton's CollisionRadius 500 and
  DeployTime 1000 are unchanged. The APK is unchanged (versionCode 160402012, lastUpdateTime 2026-09-23), and the
  update folder carries data only.
- (b) Geometry under the fork's own law (`formation.rs scale_radius`: radius x 577 / trunc(1000 sin(90/3) / 1024)
  = radius x 577 / 500): 3 members stand at r = 461 (R 400) -> 577 (R 500). The two side members sit at
  x = +-r cos 30 = +-400 -> +-500 from the tap. A tap on a middle-tile centre (x 8500 or 9500) now puts one member
  at about x 9000, the lane boundary, so it walks the other lane. W19's dossier has a live member at 9003 for a
  tap near 8500 (FIN15.md 9.3).

### 1.2 The 10-06 half of the same post (already in our SIM, for reference)

The 10-06 table (16.402.19) holds these, verified on the table (a):
- X-Bow damage 23 -> 24 at level 1 = "58 → 61" at L11; 85 -> 89 at L15; 94 -> 98 at L16.
- Skeletons SummonRadius 700 -> 400 ("Tighter Spawn Spread").
- Minion Giant hit_speed 1700.
- The Hero IW freeze 46 (S1: "Freeze Damage: 89 → 46").
- The 10-12 apktables device audit found the 10-06 table equal to the device on all 99 cards it compares.

## 2. Live confirmation (`live_confirm.py`; public bodies only: positions, hp, max_hp)

The census covers 1,132 live logs from 10-18 00:00 to 10-21 23:59. The era is set by the log name: "post" means
`>= 20261019_0603`.

### 2.1 Skeleton ring (a)

Method: every group of 3 Skeleton bodies first seen together (same side, within 2 ticks, all deploying), own and
opponent. The ring radius is the mean member distance to the group's centroid.

| era | rings | median | mode (count) | share in 576-580 (the R 500 ring, 577) | < 520 | >= 640 |
|---|---|---|---|---|---|---|
| pre (16.402.21) | 3,295 | 571 | **468** (656), then 607, 585, 571 | **0.5 %** | 31 % | 2 % |
| post (16.402.22) | 4,173 | 578 | **578** (1,202), then 599, 645, 544 | **32 %** | 4 % | 20 % |

- The pre-patch mode 468 is the fork's R 400 ring (461), plus reader rounding. The post-patch mode 578 is the
  R 500 ring (577).
- The other modes are the clamped and lane-mirrored variants that W19 is fitting (FIN15.md 9.3). They are not
  separated here.
- Per file, the switch lands at the patch time (`skel_by_file` in the JSON):
  - 10-19 logs up to `055841`: per-match medians are mostly 571 / 585, ranging 467-607.
  - From `060327` on: 578.0 is the commonest per-match median.

### 2.2 Damage per hit on our crown towers (a)

Method: an exact drop that equals the value at the attacker's level read from its max_hp. Only values where old and
new differ are counted.

| card | before the patch: old / new value | after: old / new value |
|---|---|---|
| Dart Goblin | **151 / 0** | **0 / 198** |
| Flying Machine | **98 / 0** | **0 / 85** |
| Cannon Cart | **53 / 0** | **0 / 34** |
| Minion Giant | **5 / 0** | **0 / 113** |
| Skeleton Barrel death (credited to a balloon of that side seen in the last 40 ticks) | **22 / 3** | **0 / 43** |

- No max_hp failed to match a level (`nolevel` empty).
- The 3 pre-patch "new" Skeleton Barrel hits are probably coincident drops, i.e. other hits that happen to sum to
  that value (b).
- Every changed opponent damage value is visible live. The switch falls exactly between the match logs
  `20261019_055841` and `20261019_060327`.

### 2.3 Not measured (b)

These are untested, not unchanged:
- **Cannon Cart mass.** It needs a push census against Goblins.
- **Rune Giant linger.** It needs the buff rows (`phase2_buffs`) after her death.
- **Electro Dragon first hit.** It needs the time from target lock to the first drop.
- **The Void's troop hits.** Its tower hit, 20, did not change.
- **Hero E-Wiz attack delay.** Rare, and the fork refuses the form.
- **Evo Skeletons radius.** The evo plays are not separated from the base ones.

The client tables [S2] are the evidence for each of these. If one needs a live check, the probe is named above.

## 3. Not in our SIM and not part of 10-19: three 16.402.21 changes (live by 10-12)

Rebuilding the 10-06 table from the 10-12 device set (16.402.21) reproduces the committed table except 3 fields:
- `evolutions[ElectroGiant_EV1].evo_delevel_pulse.filter`: CommonAreaDamageFilter -> CommonAreaDamageFilterNoClones.
  This is the same filter plus "Clones": a Clone spell's copies are not hit. (a)
- The Hero Electro Wizard's `Set_Attack_Sequence_1/2` gained `NextAction = ElectroWizardHero_Forbid_Movement`, an
  ActionWithDuration of 150 ms. (a)
- The Hero Electro Wizard's ability gained `refund_window_ms` 400. (a)

The extractor's hero reader refuses the Forbid_Movement links, and the fork refuses the Hero E-Wiz form anyway (W9).
So the new table keeps the 10-06 Hero E-Wiz, with only the 10-19 `attack_start_delay_ms` 500 -> 0 applied.

## 4. The engine data patch (for W19, CLIENT-DATED)

- **Fork branch `patch1019`** (worktree `C:/Users/benpe/rsfork_w23`) = fin15 `305aaafc` + commit `b2809aa1`.
  The patch file is `patches/0001-*.patch` (25 KB: `-C -C --find-copies-harder`, so the new table is encoded as a
  copy of the 10-06 one plus its deltas). Apply with `git am patches/0001-*.patch` on 305aaafc. The commit holds:
  - `data/derived/cards-160402017-20261019.json` (version `cards-160402017-20261019.1`): the 10-06 table plus exactly
    the **56 field deltas** in `deltas_1019.txt`. Every other field is byte-identical.
    - `provenance.files` holds the 10-06 inputs, with the decoded 16.402.22 hashes for the 13 changed files.
    - `provenance.derivation` says how the table was made.
  - `tools/extract_cards.py`:
    - The vintage `160402017-20261019`: the raw pack plus `data/raw/cr-160402017-20261019` (the decoded update
      folder, gitignored).
    - The `Clones` filter entry, read as `filter_clones`. The engine ignores it (serde default).
  - A `.gitignore` exception for the new derived table, by the same option-B ruling as the 10-06 one.
- **How the 56 deltas were derived (reproducible):**
  1. Base = the 10-12 effective device set (`apktables/out/device_builds/20261012T221627332682Z-50188/tables/csv_logic`)
     copied to `data/raw/cr-160402017/csv_logic`. 135 of its 138 inputs hash-equal the 10-06 table's provenance.
  2. In scratch copies only, the 2 Forbid_Movement links were removed from the Hero E-Wiz file, so that the hero
     reader runs.
  3. `extract_cards.py --vintage 160402017-20261006` gives A (16.402.21). `--vintage 160402017-20261019` gives B
     (16.402.22).
  4. `make_table.py BASE A B DECODED OUT DELTAS` applies B - A to the committed 10-06 table. It stops if the base
     does not hold A's value at any delta; it did not stop.
  5. Checks: jdiff(10-06 table, OUT) = the 56 deltas. jdiff(B, OUT) = only the 3 section-3 fields.
- **Wiring still owed (W19):**
  - The arm `client160402017_20261019`: `card.rs` (an EMBEDDED json `include_str!` beside lines 83-94, and
    `CardDb` load_table near 15391), `state.rs` (the CARD_TABLE enum near 5247), `py.rs` (the export near 2527),
    `calibration.json` (the `cards.CARD_TABLE` candidates and provenance), `tests/card_table.rs`.
  - The harness: `fights.Engine(table=...)` already takes a table. Pick the 10-19 table for matches whose stamp
    is `>= '20261019_0600'` (`m['match'][10:23]`), and the 10-06 table before that.
  - `PARITY_FORM_SYM_FROM` should default to `20261019_0600`, not `_1000`.
- **Pipeline default (NOT applied):** `pipeline_card_table_after_wheel.diff` sets `royale_heroiw.CARD_TABLE` to
  the 10-19 table and keeps `CARD_TABLE_1006`. Apply it only together with a wheel that carries the arm; an older
  wheel refuses the name. A new runtime id also needs adding to `royale_heroiw.ENABLED`.

## 5. Pipeline-side tables

- `live_card_catalog.json`: identity, elixir and ability fields only. None changed on 10-19 (a). No patch needed.
- `pipeline/vocab.py`: a comment cites Minion Giant damage 66; it is 60 since 10-19. Comment only.
- **Separate, pre-existing finding:** `pipeline/extrapolate.py catalog()` reads
  `research/ext/Royale/RoyaleSim/data/derived/cards.json`, which is **cards-15535.1**. It holds Skeletons
  summon_radius 700 and X-Bow damage 23 (a).
  - `live_gen.pending_board` (live) and `e1_eval` use it to draw my in-flight plays. Pending Skeletons are drawn
    on an 808 ring: 700 / cos 30.
  - The SIM's own pending view uses the selected table instead, which lays them at 461 and will lay them at 577.
  - This train/live view gap predates 10-19 (b: its effect on play is untested). It is a live-path change, so it
    is left for the lead / owner.

## 6. Files

| file | what |
|---|---|
| `PATCH1019.md` | this report |
| `live_confirm.py` | the live census (Skeleton rings, tower-hit values by era) |
| `make_table.py` | builds the dated table from the 10-06 table + extractor deltas |
| `deltas_1019.txt` | the 56 field deltas |
| `patches/0001-*.patch` | the fork commit (table + vintage + Clones filter) |
| `pipeline_card_table_after_wheel.diff` | the training/eval default switch, to apply with the wheel |
| `live_confirm_1018_1021.json` | the census output |
