# L62 bridge RE: buffs + area effects (libg 15.535.29 x86_64, live dump pid 2937)

Started 2026-09-05. Owner-authorised RE. Artifacts: `scratchpad/gauntlet/ext/re/bridge_v2/` (outside git).
Helper scripts: `scratchpad/gauntlet/L62/re_*.py`. Labels: (a) measured/read from disassembly with address,
(b) plausible-untested, (c) contradicted.

Dump: `scratchpad/gauntlet/ext/dump/live/libg_7ad3d8ec7000_rwxp.bin` = RVA 0 (code+rodata, 25.9 MB);
`libg_7ad3da77d000_r--p.bin` = RVA 0x18b6000; `libg_7ad3da87e000_rw-p.bin` = RVA 0x19b7000.
v1 bridge snapshot: `bridge_v2/libnative_core_probe.v1_82887463.so` (sha256 verified below).

## 0. Starting facts (from the bridge source, read 2026-09-05)
* (a) Entity list: `battle+0xA8 -> logic; logic+0x08 -> registry; registry+0x40 -> collection;
  collection+0x08 -> data (ptr array), collection+0x14 -> count` (jni_bridge.cpp ~300).
* (a) `+0x08` on an entity is a GLOBAL GENERATION KEY (unique per entity: bridge throws on duplicates),
  characters are numbered 5,000,000+ordinal, the "4M series" are other entity types in the same list.
  The `effects` gate only accepts 4M-series entries with side in {0,1} and in-bounds x/y (or the
  projectile vtable 0x1969B38). Area effects could be (i) 4M with side outside {0,1}, (ii) a different
  series (3M/6M...), or (iii) not in this list at all. To be determined.
* (a) Names are NOT resolved in C++: the bridge exports `card_id` and the host maps it. For buffs I need
  a name string from the data record itself (LogicData rows carry the `Name` column string).


## 1. Data classes (a)
* `logic.data.LogicCharacterBuffData` (class-name string @0x324ce2, 19 xrefs). Loader/createReferences
  ~0xdedc20: Projectile->+0xB0, OverrideProjectile->+0xB8, NoDamageReductionForBuffs list +0xC8/+0xD0/+0xD4,
  OnDamageReductionAction->+0xD8, ChainedBuff (table type 9)->+0x130, OnStartAction->+0x208,
  OnRemoveAction->+0x210. Column ctor ~0xdede08-0xdee8b0 reads: Effect, MarkEffect, TopEffect,
  DamageReduction, HitSpeedMultiplier, SpeedMultiplier, HitFrequency, SpawnSpeedMultiplier,
  CrownTowerDamage*, Scale, ChainedBuffTime, Invisible, RemoveOnAttack/Heal/Hit, Attract*, Push*, Clone,
  EnableStacking, Jump, Shield, Rarity, ContinuousEffect, HitpointMultiplier, MorphTarget, DeathSpawn*,
  DamagePerSecond, HealPerSecond, DamageOnHit, DamageMultiplier, LockTarget, Rally, LevelIncrease,
  SwitchTeam, AddAsIndividualBuff, GameTagsToSet. Small getters: 0xdedb00 `([+0x110]|[+0x114])!=0`,
  0xdedb10 byte+0x12a, 0xdedb20 q+0x90, 0xdedb50 byte+0x128, 0xdedb60 q+0x98, 0xdedb70 walks the
  ChainedBuff chain via +0x130, 0xdedb90 q+0x170, 0xdedba0 level-scaled value from +0x1d0/+0x148/+0xe8.
  The column->offset map for the multipliers is NOT extracted (not needed: names are exported instead).
* `logic.data.LogicAreaEffectObjectData` (@0x2c2bcd, 18 xrefs). Loader ~0xdd6290-0xdd7a00; columns
  Buff, Projectile, SpawnsAEO, SpawnAreaEffectObject, LifeDuration (xref 0xdd68ed/0xdd78dc/0xdd8415),
  Radius, BuffTime (0xdd6ab8/0xdd78b5/0xdd8732), Damage, HitsGround/Air, Pushback, OnlyEnemies,
  ControlsBuff, Shape, FollowBehaviour.
* Other xrefs kept for the record: BuffType@0x2e9854 (0xe82483 0xed3b99 0xed4388 0x10ceea3 0x10cf725),
  AreaEffectType@0x2d9108 (0xed3bdb 0xed434f), AreaEffectObject@0x306e01 (0xdebaa5 0xdecace 0xe8258f),
  BuffName@0x30b51f (0xe39041), LifeTime@0x30559b (0xdf5d4b 0xdf8104 0xdfbc0a), DeathAreaEffect
  (0xdf493a 0xdfa66d), ActionSetShield/SoulDrain/Taunt 0xdd3ad6/0xdd3c8e/0xdd391e.
* (b) A second, plugin-style engine (`LogicPlugin*Asset`, BuffType loader 0x10cdf00..., flag parser
  0x118fe70) also exists; I read it as the Merge-Tactics engine. Its FlagType enum (a, parser
  0x118fe70): Invisible 0, InVincible 1, UnTargetable 2, Flying 3, Underground 4, Reborn 5,
  TraitStarting 6, SystemMoving 7, NoEnergyCost 8, Immovable 9, Dead 10, EnergyLock 11,
  ImmuneControl 12, ForceMoving 20, Stun 21, ForbidMove 22, ForbidRotate 23, ForbidAbility 24,
  ForbidAttack 25, SlowMove 26, SlowAttack 27, Wounded 28, Taunt 29, Fear 30, MaxCount 31.
  Whether classic-battle LogicCharacter carries this flag word is (b) at this point.

## 2. Buff runtime (a unless marked)
* `kind` (character +0x30, already exported by the bridge) is the COMPONENT-PRESENCE BITMASK:
  bit0 components[0] attack, bit1 components[1] move, bit2 components[2] hitpoints,
  bit3 components[3] = BUFF MANAGER. Evidence: getter 0xf852e0
  `test byte [rdi+0x30],8 ; jz ; cmp dword [rdi+0x24],4 ; jl ; mov rax,[rdi+0x18] ; mov rax,[rax+0x18]`
  (components ptr array at +0x18, count at +0x24). So kind 12=hp+buff, 13=attack+hp+buff,
  14=move+hp+buff, 15=all four.
* Buff manager (components[3]) layout: +0x10 owner LogicCharacter*, +0x18 buff-instance ptr array
  (LogicArray {data@+0x18, capacity@+0x20, count@+0x24}; grow fn 0xfb31b0, initial capacity 5).
  Remove 0xfb2240; add = 0xfb1130(mgr, ?, LogicCharacterBuffData*, time_ms, ..., instigator char)
  (call site 0xfb1816 shows the arg order); apply-on-add 0xfb1970; array decoder 0xfb0d90.
* Buff instance (0x70 bytes, ctor 0xf77c00(inst, owner=[mgr+0x10], mgr)):
  | off  | meaning | evidence |
  |------|---------|----------|
  | +0x00 | owner LogicCharacter* | ctor 0xf77c00 |
  | +0x08 | total time ms (-1 = permanent) | 0xf78710 sets +8 and +0xC = time |
  | +0x0C | remaining time ms | refresh 0xf78820: `if new-old>0 && old!=-1 {+8=new; +0xC+=diff}`; elapsed getter 0xf788c0 = min(abs(total-remaining), abs(total)) |
  | +0x18 | LogicCharacterBuffData* | ctor; checksum 0xf77e40 |
  | +0x20 | manager* | ctor |
  | +0x28 | buff level (0xf98220(level, data+0x148)) | add path |
  | +0x30 | source char (only if data byte +0x12b) | add path |
  | +0x38 | instigator LogicCharacter* | 0xf78720 |
  | +0x40 | instigator side | 0xf78720 |
  | +0x48..+0x54 | ints copied from data +0x188/+0x190/+0x140 | add path |
  | +0x58/+0x5c/+0x60 | ids from 0xf86b50/0xf86b40/0xf86ba0 of instigator | add path |
  | +0x68 | effect handle (-1 none) | ctor |
  Checksum encoder 0xf77e40 order: +0x8, +0xC, +0x28, +0x40, +0x10, +0x44, then objs +0x30, +0x38.
* Character getters used as anchors: 0xf84f10 side (+0x78), 0xf851c0/0xf851e0 x/1000,y/1000 (+0x7c/+0x80),
  0xf85480 &+0x7c, 0xf854b0/0xf85490 components[1], 0xf854d0 components[0].

### 2.1 CORRECTION to the instance table above (a): +0x08 is REMAINING, +0x0C is TOTAL
* Manager per-tick update = vtable slot 3 of the manager vtable @0x196ec68 (ctor 0xfb08f0 stores it):
  0xfb0b10. It copies the buff list into a scratch array (+0x50/+0x58/+0x5c), then for each buff calls
  0xf78200(inst) then 0xf786e0(inst) -> bool expired -> 0xfb0950(mgr, index) removes it.
* 0xf78200 (instance tick): `eax=[inst+8]; if eax==-1 skip; ecx=max(eax,0x32)-0x32; [inst+8]=ecx`
  (0xf78211-0xf7822b) -> +0x08 is decremented by 50 ms per logic tick (fixed 50 ms, no delta arg),
  -1 = permanent. Also evaluates data+0x230 (an expiry filter object) via 0x1292d60 and zeroes +8 if it fails.
* 0xf786e0 (expired?): `if [inst+0x30] (source char) and source->vtbl[3]() then true; else [inst+8]==0`.
* Therefore: instance +0x08 = remaining_ms, +0x0C = total_ms (0xf78710 sets both; refresh 0xf78820
  `diff=new-[+8]; if diff>0 && [+8]!=-1 {[+8]=new; [+0xC]+=diff}`; elapsed 0xf788c0 = min(|rem-total|,|rem|)).
* Manager +0x30 is a separate 50 ms countdown (`[+0x30]-=0x32`, clears +0x28 ptr when <=50), not a flag word.
* Manager vtable (RVA, from r--p dump @0x196ec68 minus base 0x7ad3d8ec7000): 0xfb30c0 0xfb3110 0xfb3160
  0xfb0b10(update) 0xfb10e0 0xfb1050 0xfb3170 0xfb3180 0xfb3190 0xfb31a0 0xfb0a80 0xfb0cb0 0xfb0f80.

## 3. Names and buff data columns (a)
* LogicData base: ctor 0xe1cba0 (vtable 0x1950620): +0x10 table*, +0x18 rows ptr-array, +0x24 row count,
  +0x28 NAME (native string, ctor 0x140f520), +0x38 byte, +0x40 global id (-1 init).
  getName = 0xe1d220 `lea rax,[rdi+0x28]; ret` (497 callers); debug formatter 0xe1d260 prints
  name + " (" + [+0x40]. That +0x28 is filled from the `Name` column is (b) -- strongly implied by
  0xe5fb09 (getName -> table vtbl+0x48 lookup) but the store site was not located.
* Native string layout (ctor 0x140f8f0, copy 0x140f970, dtor 0x140f7d0): +0x00 int hash (-1),
  +0x04 int len, +0x08: if len < 8 the chars are INLINE at +0x08 (NUL-terminated), else char* at +0x08.
  So a data record's name: len=[data+0x2C]; chars = len<8 ? data+0x30 : *(char**)(data+0x30).
* LogicCharacterBuffData column -> offset (ctor 0xdedde0, stores cited in bridge_v2/asm/buffdata_ctor.txt):
  DamageReduction +0xc0, HitSpeedMultiplier +0xe0 (getter 0xded7a0), SpeedMultiplier +0xe4 (0xded7b0),
  HitFrequency +0xe8, SpawnSpeedMultiplier +0xec (0xded950), CharacterCrownTowerDamagePercent +0xf0,
  CrownTowerDamagePerHit +0xf4, CrownTowerDamagePercent +0xf8, Scale +0x100, ChainedBuffTime +0x104,
  Invisible +0x108 (byte, getter 0xded960), RemoveOnAttack/Heal/Hit +0x109/+0x10a/+0x10b,
  NoEffectToCrownTowers +0x10c, AttractPercentage +0x110, LateralPushPercentage +0x114,
  PushMassFactor +0x120, PushSpeedFactor +0x124, IgnorePushBack +0x128, Clone +0x12a,
  EnableStacking +0x12b, Jump +0x12c, Shield +0x140, Rarity* +0x148, SpawnObject* +0x170,
  SpawnStartTime +0x188, SpawnInterval +0x18c, SpawnLimit +0x190, HitpointMultiplier +0x19c,
  HitTickFromSource +0x1a4, MorphTarget* +0x1a8, DeathSpawn* +0x1b8, DamagePerSecond +0x1d0,
  HealPerSecond +0x1d4, DamageOnHit +0x1d8, DamageMultiplier +0x1dc, LockTarget +0x200 (byte),
  Rally +0x201, LevelIncrease +0x204, SwitchTeam +0x220 (byte), AddAsIndividualBuff +0x228,
  GameTagsToSet +0x240, PlayerSpecificBuff +0x254. Full list in buffdata_ctor.txt.
* Aggregation the engine actually uses (a): manager 0xfb2b00 folds HitSpeedMultiplier (+0xe0) over all
  buffs (max positive, max negative), 0xfb2bc0 does the same for SpawnSpeedMultiplier (+0xec); i.e.
  "frozen"/"stunned" is NOT a flag on the character -- it is a buff whose multipliers are -100.
  There is NO per-character freeze/stun flag word in the classic engine that I could find; the
  plugin FlagType enum (section 1) belongs to the other engine. The bridge therefore exports, per buff,
  the raw multipliers/booleans plus a derived `flags` bitmask so the view can distinguish causes.
* Shield: instance +0x54 is initialised from data Shield (+0x140) when >0 (0xf788b0); that +0x54 is the
  live remaining shield HP is (b) (decrement site not read).

## 4. Area effect objects at runtime (a unless marked)
* Class-type dispatch (a): every LogicGameObject has vtable slot 2 (+0x10) = getObjectType.
  LogicAreaEffectObject 0xf6dd60 `mov eax,3; ret`; projectile 0xf7f250 `mov eax,4; ret`;
  characters are 5 (bridge, previously verified). 0x10b90b0 walks the sorted registry collection
  starting at 0xf7cc80(coll, 3) (first id >= 3*1M) and dispatches on that slot: type 4 -> remove
  (0xf7d1f0), type 3 -> 0xf6db40 (`[+0x100]=0`) + 0xf6de00 then remove, type 5 -> character
  cleanup. => global id series = objectType * 1,000,000 + n. AREA EFFECTS LIVE IN THE 3M SERIES.
  The bridge's existing "effects" gate (4M..5M) therefore only ever sees projectiles -- this is why
  zones never appeared in the v1 export. (Contradicts the v1 bridge's assumption that 4M = effects.)
* Factory 0xf7b220(data): data vtbl+0x80 (isCharacterData) -> alloc 0x3b8 + ctor 0xf8e2c0 (LogicCharacter,
  vtable 0x196a000); else data table type (0xe1d1a0): 0x16 -> alloc 0x150 + ctor 0xf6b410 =
  LogicAreaEffectObject (vtable 0x19691f8); 0x0a -> alloc 0x208 + ctor 0xf7e4c0 (projectile, vtable
  0x1969b38, matches the bridge's kProjectileVtableRva).
* LogicGameObject base (ctor 0xf7a6c0 / 0xf84bd0): +0x08 global id, +0x30 component bitmask,
  +0x48 data*, +0x58 ref, +0x78 side (0xf85200 setter, 0xf84f10 getter), +0x7c/+0x80 x/y (0xf853e0
  setter; getters 0xf851c0/0xf851e0 divide by 1000), +0x8c z, +0x94/+0x98/+0xa4/+0xac set by 0xf85270
  (owner ids / card ref; meaning (b)).
* LogicAreaEffectObject layout (ctor 0xf6b410, size 0x150): +0x48 LogicAreaEffectObjectData*,
  +0xf8 byte (data+0x1e0 != 0), +0xfc level, +0x100 elapsed ms (getter 0xf6b510; slot 3 0xf6db80 =
  `[+0x100] <= 0`; reset 0xf6db40), +0x108 ptr (freed in dtor), +0x114 life override (-1 => use
  0xf6b4f0 -> 0xdd5fd0(data, level) = level-scaled LifeDuration), +0x118 word, +0x119 byte,
  +0x120..+0x14f arrays. 0xf6b520 = current radius: data Radius (+0x17c) growing linearly to MaxRadius
  (+0xb8) by elapsed/life when data byte +0x1d0 is set or (+0x114 & 6).
  Create+init 0xf7b320(data, owner, level, side, ...) -> 0xf85200 side, 0xf85270, 0xf853e0 x/y,
  byte -> +0x119, FollowBehaviour (data+0x1e8 in {1,2}) -> 0xf6ddd0 follow target; 0xf6dd70(aeo, level, owner).
* LogicAreaEffectObjectData columns (loader 0xdd6290..0xdd7a00, annotated in bridge_v2/asm/aeo_data_ann.txt):
  MaxRadius +0xb8, Buff* +0xe8, HitSpeed +0x118, HitsAir +0x121, HitsGround +0x122, Damage +0x124,
  OnlyEnemies +0x129, OnlyOwnTroops +0x12a, CapBuffTimeToAreaEffectTime +0x12c, SpawnInterval +0x130,
  SpawnTime +0x134, SpawnMaxCount +0x13c, SpawnCharacter* +0x160, LifeDuration +0x170 (+0x174 per
  level, +0x178 after tournament cap; level getter 0xdd5fd0 uses Rarity +0x1b0), Radius +0x17c,
  Pushback +0x180, MaximumTargets +0x188, CrownTowerDamagePercent +0x190, ControlsBuff +0x194,
  BuffTime +0x1a0/+0x1a4/+0x1a8 (getter 0xdd6020), Rarity* +0x1b0, StayAfterParentDies +0x1b8,
  DeflectProjectilesEnabled +0x1d0, FollowBehaviour +0x1e8, Shape* +0x220, Filter* +0x228.
* Life duration used by the bridge: life = [+0x114] if >= 0, else 0xdd5fd0(data, level). The exact
  0xdd5fd0 arithmetic (tournament-cap level clamp) is (b); the bridge approximates it as
  data+0x170 + (level-1)*data+0x174 which is the un-capped path, and ALSO exports the raw fields
  (elapsed, life_override, base_life, life_per_level) so the verify run can check it.
* CORRECTION (a): 0xdd5fd0(data, level) read in full: cap = Rarity(+0x1b0)->vtbl[0x120]() (tournament
  level cap); if level <= cap: life = +0x170 + level*+0x174; else life = +0x170 + cap*+0x174 +
  (level-cap)*+0x178 (dd5ff5..dd6010). 0xf6b4f0 passes [aeo+0xfc] as `level` unchanged, so the bridge
  computes it with that raw value; the only remaining (b) is the cap value (needs the Rarity record's
  virtual), so the bridge uses the uncapped branch and exports elapsed/life_override/base/per_level raw.
  (BuffTime getter 0xdd6020 is the same formula over +0x1a0/+0x1a4/+0x1a8.)

## 5. Bridge patch (what v2 exports)
File: research/ext/cr-native-sandbox/android_probe/native/jni_bridge.cpp, sandbox git commit
**81e5dff** `bridge: export buffs + area_effects (RE, unverified)` (docs/API.md section 10.1 added).
Nothing committed in the ClashBot repo. ADD-ONLY: every pre-existing field, gate, sort and the
state_hash stream are untouched (new fields are not hashed; state_hash_scope stays public-observe-v6).
Compact observe: zero new reads (all v2 code is behind `!compact_observation`).

Per character entity (full observe): `buff_manager_count` (raw [manager+0x24], -1 if the character has no
component[3]), `buff_manager_vtable_rva` (expect 0x196ec68), `buffs: [{name, data_id, remaining_ms,
total_ms, level, instigator_side, shield_hp, flags, hit_speed_multiplier, speed_multiplier,
spawn_speed_multiplier, damage_reduction, hitpoint_multiplier, damage_per_second, heal_per_second,
data_shield, invisible, lock_target, switch_team, enable_stacking}]` (cap 64). `flags` is DERIVED:
1 cannot_attack (hit speed mult <= -100), 2 cannot_move (speed mult <= -100), 4 slowed, 8 hasted,
16 shield, 32 invisible, 64 dot, 128 heal, 256 damage_reduction, 512 switch_team, 1024 lock_target,
2048 permanent (remaining == -1); 0x40000000 manager vtable != 0x196ec68; 0x80000000 instance owner
(+0x00) != entity. Freeze vs stun is resolved by `name` + `total_ms` (there is no engine flag word).
Top level (full observe): `area_effects: [{id, name, data_id, data_ptr, vtable_rva, category, kind,
side, x, y, z, card_id, level, elapsed_ms, life_override_ms, life_base_ms, life_per_level_ms,
life_per_level_over_cap_ms, life_ms, remaining_ms, radius, max_radius, current_radius, grows,
buff_time_base_ms, buff_time_per_level_ms, damage, hit_speed_ms, controls_buff, has_buff, hits_air,
hits_ground, only_enemies, only_own_troops, follow_behaviour, owner_slot_a, owner_slot_b}]`,
`area_effect_count`, `class_histogram[16]` (entities per global-id series), `area_effect_vtable_histogram[16]`,
`bridge_ext = "buffs_area_effects_v2_unverified"`. Selection is keyed on vtable == 0x19691f8 with
category < 4M and side in {0,1}; existing 4M/5M paths unchanged.

Builds (scripts/build_bridge.ps1, x86_64-linux-android23, -O2 -Werror):
* v1 (pre-patch, restored into artifacts/ so the live workers' artifact-drift check is unaffected):
  sha256 82887463deee1f2c92acb70368dbb7d8f323433980a5c1b1abddd15241c81289
  -> scratchpad/gauntlet/ext/re/bridge_v2/libnative_core_probe.v1_82887463.so
* v2: sha256 9b63a7a0bce2dcdc8e24608e8b6f161396a05bced4b68f23dab865632ee4ce3f
  -> scratchpad/gauntlet/ext/re/bridge_v2/libnative_core_probe.v2.so
  NOTE: artifacts/libnative_core_probe.so is deliberately still v1. Deploy v2 only via the runbook
  (own remote root + port) or, once training is stopped, by copying v2 over artifacts/ and restarting
  the workers.
Verification runbook (NOT run): scratchpad/gauntlet/L62/re_verify_bridge.py (deploy / drive / stop /
compare; pool tag 092PPVPCRCPC covers Poison, Tornado, Graveyard, Ice Spirit, Log, Barbarian Barrel;
`--synthetic` scripts Freeze/Zap/Rage/Poison/Tornado/IceSpirit plays since the pool has no Freeze/Zap/Rage).
Helper scripts: re_xrefs.py, re_dis.py, re_range.py, re_strrefs.py, re_enum_table.py,
re_patch_bridge_loop.py, re_patch_bridge_json.py, re_fix_nul.py (all in scratchpad/gauntlet/L62).

## 6. Offset table (summary; every row (a) unless marked)
| what | offset / value | evidence |
| --- | --- | --- |
| object global id | obj+0x08 | base-base ctor 0xf7a6c0 zeroes it; sorted collection keyed on it (0xf7cc80/0xf7cce0) |
| object type | vtable slot 2 (+0x10) | 0xf6dd60 ret 3 (AEO), 0xf7f250 ret 4 (projectile); dispatch at 0x10b913b-0x10b915a |
| id series | type*1M + n | 0x10b90db searches from 3*1M then dispatches on slot 2; chars 5M (bridge) |
| component bitmask / array / count | obj+0x30 / +0x18 / +0x24 | 0xf852e0 `test byte [rdi+0x30],8; cmp [rdi+0x24],4; mov rax,[rdi+0x18]; mov rax,[rax+0x18]` |
| buff manager | component[3]; vtable 0x196ec68 | ctor 0xfb08f0; update = slot 3 = 0xfb0b10 |
| manager owner / array / cap / count | +0x10 / +0x18 / +0x20 / +0x24 | grow 0xfb31b0, add 0xfb1130, remove 0xfb2240/0xfb0950 |
| buff instance size | 0x70 | ctor 0xf77c00 |
| instance owner / remaining / total | +0x00 / +0x08 / +0x0C | 0xf78200 `eax=[inst+8]; if -1 skip; ecx=max(eax,0x32)-0x32; [inst+8]=ecx`; 0xf78710 sets both; refresh 0xf78820 |
| instance data / manager / level | +0x18 / +0x20 / +0x28 | ctor 0xf77c00, 0xf98220(level, data+0x148) |
| instance source / instigator / side | +0x30 / +0x38 / +0x40 | ctor; 0xf78720 |
| instance shield hp | +0x54 | 0xf788b0 init from data+0x140 when > 0 (live decrement (b)) |
| expired test | [+0x30] && source->vtbl[3]() else [+0x08]==0 | 0xf786e0 |
| LogicData name / global id | +0x28 (native string) / +0x40 | 0xe1d220 `lea rax,[rdi+0x28]`; ctor 0xe1cba0; Name column store site (b) |
| native string | +0x00 hash, +0x04 len, +0x08 inline(<8) or char* | 0x140f8f0/0x140f970/0x140f7d0 |
| buff data columns | see section 3 | ctor 0xdedde0 stores, bridge_v2/asm/buffdata_ctor.txt |
| AEO vtable / size / ctor | 0x19691f8 / 0x150 / 0xf6b410 | factory 0xf7b220 (table type 0x16) |
| AEO data / side / x / y / z | +0x48 / +0x78 / +0x7c / +0x80 / +0x8c | base ctor 0xf84bd0, setters 0xf85200/0xf853e0 |
| AEO level / elapsed / life override | +0xfc / +0x100 / +0x114 | 0xf6b4f0, 0xf6b510, 0xf6db80, 0xf6db40 |
| AEO life formula | 0xdd5fd0 | dd5ff5..dd6010 (section 4 correction) |
| AEO radius growth | 0xf6b520 | data+0x1d0 or (+0x114 & 6) |
| AEO data columns | see section 4 | loader 0xdd6290.., bridge_v2/asm/aeo_data_ann.txt |
| projectile vtable / size | 0x1969b38 / 0x208 | factory (table type 0x0a), ctor 0xf7e4c0 |

## 7. NOT established (owner-visible caveats)
* Nothing above has been observed in a running battle: all (a) claims are from disassembly of the
  live libg dump, none from a runtime read. The runbook in section 5 is the test.
* Whether LogicData +0x28 is filled from the `Name` column (b) -- names could in principle be another
  string column; the verify run's printed names settle it immediately.
* Tournament-cap branch of 0xdd5fd0 (needs Rarity vtbl+0x120 value); the bridge uses the uncapped branch
  and exports the raw terms. Same for BuffTime.
* Shield: +0x54 as LIVE remaining shield HP (b); the decrement site was not read.
* AEO +0x94/+0x98/+0xac meaning (exported raw as owner_slot_a/b, card_id) (b).
* Whether the sorted-collection walk includes area effects that are attached/following (FollowBehaviour)
  -- they should be ordinary registry objects (created by the same factory) but untested.
* Per-hit events: skipped (lowest priority), nothing located.
* No freeze/stun flag word exists in this engine as far as the disassembly shows (section 3); if the
  view needs a "cannot act" bit it must derive it from the buff multipliers (bridge `flags`).
* The plugin FlagType enum in section 1 belongs to a different (script-side) engine; ignore for libg.

STATUS: complete
