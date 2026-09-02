# Level-16 matches in the cr-native-sandbox engine — research (2026-09-02, L11)

Read-only investigation (subagent) + spot-verification of every load-bearing claim by the main loop.
No engine was run; the emulator stayed down and the training box was untouched.

## Bottom line

Card level is a **free parameter — one integer**, and level 16 is in range for every rarity. It is NOT
baked into replay data: the RoyaleAPI crawl contains no card levels at all, so the current 11 is an
**assumption the harness makes**, not a fact recovered from the replays. Cards at 16 = `--level 16`,
zero code edits. Tower/king level is a **separate** knob, hardcoded at 11 in the replay template, and
needs a small JSON edit.

## 1. Where card level is set — (a) all verified in code

| Layer | file:line | value |
|---|---|---|
| CLI flag | `research/sandbox_tools/replay_drive.py:434` | `--level`, default **11**, help: "card level for both sides (crawl has none; 11 = tournament)" |
| Batch CLI | `research/sandbox_tools/replay_batch.py:85` | `--level`, default 11 |
| Applied to all 8 cards, both sides | `replay_drive.py:236-239` (`deck_spec`), used at :268, :285, :307 | one int -> every card |
| Deck builder | `research/ext/cr-native-sandbox/native_core/decks.py:30-46` (`normalize_deck`), `:49-62` (`build_replay`) | default 11 |
| Validation | `native_core/card_catalog.py:104-105` -- `if level < 1 or level > 16: raise` | accepts 1..16 |
| JSON encoding | `card_catalog.py:116-125` -- `{"d": card_id, "l": level - 1}` | zero-based |
| Template on disk | `examples/full-card-bootstrap.json` (read by `replay_drive.py:249`) | every `"l": 10` = level 11 |
| Observation | `android_probe/native/jni_bridge.cpp:1291` -- `raw_i32(0x120) + 1`; filter accepts <17 at :1316 | 16 passes |

Verified by hand: `card_catalog.py:104` is exactly `if level < 1 or level > 16`; `decks.py:30-62` matches;
`replay_drive.py:236-239` and `:434` match. It really is 11, in six independent places, all **defaulting**
rather than deriving.

### `l` is an ABSOLUTE 0-based level, not a per-rarity index — (a)

From `runtime/extracted-assets/csv_logic/rarities.csv` (Supercell-LZMA, decompressed read-only):
Common 16 levels / RelativeLevel 0; Rare 14/2; Epic 11/5; Legendary 8/8; Champion 6/10.
`RelativeLevel + LevelCount = 16` for every rarity, and `TournamentLevelIndex = 10 - RelativeLevel`.
Proof it is absolute: the certified bootstrap deck holds The Log (`28000011`, **Legendary**, 8 levels)
at `"l": 10` and still produces the certified hash `96598dc9028e1802`.
**Consequence: `l = 15` (level 16) is legal for all five rarities.** No card is excluded.

## 2. Is level baked into the replays? NO — (a)

Verified directly on this box:
* `icebow/data/royaleapi/crawl2/battles.csv` header has `team_deck`/`opponent_deck` as slug strings and
  **no level column**; `grep -ci level` on `battles.csv` and `plays_ext.csv` returns **0** in both.
* `battles_raw.json` (537 records): the substring `level` does not occur.
* `HANDOFF.md:5303-5304` says so itself: "card levels (NOT crawled; extend the crawler or assume
  tournament level 11 = the bootstrap default)"; `:5732` confirms the batch ran "WITHOUT card levels".
* `build_replay` (`decks.py:57-62`) rewrites only `rndSeed`, `deck0.sp`, `deck1.sp` and deep-copies the
  rest, so nothing else in the replay object constrains level.

**(c) CONTRADICTED:** `HANDOFF.md:5737` claims "RoyaleAPI has the levels per card in the crawl -> pass
them through `battle`". False for the crawl files on this box -- there is no level data in any of them.
The "Levels pass-through" next-step at `HANDOFF.md:5770` is blocked on a **crawler change**, not an edit.

## 3. What level changes, and who owns the math — (a)

* The sandbox has **zero stat tables and zero level math**: the only `level` occurrences in `native_core/`
  and `jni_bridge.cpp` are the plumbing above plus the observation reader.
* `libg.so` owns it. Level enters as `l`, is parsed by libg's replay parser, and reappears at entity
  offset `0x120`. Every HP/damage number in `observe()` is what the real engine computed.
* The per-level curve is NOT in the extracted CSVs: a search of all 383 tables for the certified level-11
  tower HP values (4824 king / 3052 princess) returns zero hits. `rarities.csv` has
  `PowerLevelMultiplier = 110` for all rarities; `characters/princesstower.toml` has base HP 1400 and a
  named `DamageScalingMode`. **(b)** whether the curve is a compiled formula in libg or a non-CSV binary
  table is unsettled; it would need a disassembly. **Practically this is a feature: you cannot get level
  scaling wrong, because you are not implementing it.**
* Cheap verification hook (a, available): every entity in `observe()` carries `level`. One reset at
  `--level 16` plus one `observe()` confirms `entity["level"] == 16` and a raised `max_hp`. ~15 s once up.

## 4. Tower and king level are SEPARATE and NOT covered by `--level` — (a) verified in the template

`examples/full-card-bootstrap.json` (checked directly):
```
deck0.sc = [{"d": 159000000, "l": 10, "t": 0, "c": 0}]   # tower princess, level 11
deck1.sc = [{"d": 159000000, "l": 10, "t": 0, "c": 0}]
avatar0.kt = 11, avatar0.expLevel = 11
hbd = [{kt: 11}, {kt: 11}]
deck0.sp all l = 10                                       # the 8 cards, level 11
```
Three knobs, all pinned at 11, all untouched by `build_replay`. Note `159000000` (tower princess) is
absent from `live_card_catalog.json`, so it gets no catalog validation.

`csv_logic/exp_levels.csv` maps `ExperienceLevel -> TowerLevel/TroopLevel`, capped at 16; `expLevel 11`
maps to TowerLevel 6, yet the certified opening HP is level-11 tower HP. **(b) plausible, untested:**
`kt` is authoritative and `expLevel` is cosmetic in the battle document. Settle it by setting
`expLevel: 75` (first exp level giving TowerLevel 16) with `kt: 11` and seeing whether opening tower HP
moves. First exp level per tower level: `11 -> 30`, `16 -> 75`.

## 5. Recipe

**Cards only, zero file edits:** `replay_drive.py --level 16` / `replay_batch.py --level 16`.
Everything downstream already handles it (validation accepts 16, encoding emits `"l": 15`, the
observation filter accepts up to 17).

**Towers/king too, one JSON file:** in `examples/full-card-bootstrap.json` set `avatar0/avatar1.kt: 16`,
`hbd[].kt: 16`, `deck0/deck1.sc[0].l: 15`, and for consistency `expLevel: 75`.

**Safety (a):** the driver's template (`full-card-bootstrap.json`) and the **certified boot** replay
(`eight-card-bootstrap.json`) are DIFFERENT files. The boot/acceptance path pushes only the eight-card
one (`scripts/start_direct_service.ps1:106`, `native_core/worker.py:277,290`), as do all four acceptance
scripts. Editing `full-card-bootstrap.json` does NOT break hash `96598dc9028e1802` or any gate; editing
`eight-card-bootstrap.json` breaks all of them. Better: copy the template and add a `--template` arg.

**(b) cleaner shape:** `normalize_deck` (`decks.py:35-38`) already accepts per-card
`{"card_id","level","form"}` dicts, so mixed real levels work today -- only `deck_spec`
(`replay_drive.py:236-239`) flattens them to one int. Widening that one function is all a future
per-card-level crawl would need.

## 6. Divergence risk — what level 16 costs

1. **For REPLAY RECONSTRUCTION, level 16 is a regression, not an improvement.** The 99.2% play
   acceptance / 77.7% crown match / 21-21 determinism grade (§5ay.2) was measured **at level 11 both
   sides**. Real top-ladder players had real, mixed, mostly-not-16 levels; forcing 16 replaces one wrong
   assumption with another and moves every crown race in an unknown direction. For **generating
   self-play / oracle data at top-ladder power**, level 16 is exactly right and reconstruction accuracy
   is not the metric. Two different projects -- pick one before running.
2. **Mixed-level footgun:** `--level 16` alone gives level-16 cards attacking level-**11** towers. That
   configuration does not exist in the real game and systematically inflates offence (the 81/211
   HP-drain tiebreak terminations would shift). Change `kt` and `sc` in the same run or the result is
   meaningless.
3. **Every certified hash is a level-11 artifact** -- state hashes fold entity level in
   (`jni_bridge.cpp:1591`). A level-16 run will not reproduce any recorded hash; that is expected.
   Re-establish determinism fresh (two runs, same hash) at 16 instead of gating on old hashes.
4. **(b) untested engine path:** no test or acceptance script anywhere exercises a level other than 11
   (`tests/test_full_card_catalog.py:52` is `level=11`; the 122/122-card and 41/41-evo coverage runs were
   all at 11). Level 16 is in range per the tables, but "libg accepts `l=15` for a Champion and produces
   sane stats" is unverified. **Highest-value next action: one reset at `--level 16` + one `observe()`.**
5. The 57 refused replays and 428 skipped ability plays are level-independent; those gaps stay.

## Claim ledger
* **(a)** everything in §1, §2, §4's template values, the rarity arithmetic, the absence of level data in
  the crawl, the absence of stat tables in the sandbox, the absence of the tower HP curve in the CSVs,
  the two-different-bootstrap-files fact.
* **(b)** `kt` (not `expLevel`) is the authoritative tower knob; libg accepts `l=15` for all rarities and
  produces correct level-16 stats; elixir-legality of recorded timelines survives a level change; the
  per-level curve is compiled rather than tabled.
* **(c)** `HANDOFF.md:5737`'s "RoyaleAPI has the levels per card in the crawl".

**Cannot be determined from code alone:** the actual level-16 HP/damage numbers (inside `libg.so`),
whether libg clamps an out-of-range level silently, and whether crown-match accuracy improves or degrades
at 16. All three need the engine running.

STATUS: complete
