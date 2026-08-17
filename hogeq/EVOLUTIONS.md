# Evolutions — research catalog + sim implementation plan

**Status: PLAN for user review (2026-08-14).** Covers (0) the engine-fidelity audit that gates this
work, (1) all 42 current evolutions and what each changes, (2) the phased plan for putting evos
into the opponent pool. Stats for 41 evos are ALREADY imported (`cards_stats.json` `<base>_evo`
keys — `cards-import` scrapes the Evolution pages); what the sim lacks is (a) opponents ever
*fielding* them and (b) the special mechanics beyond stats.

---

## 0. Engine-fidelity audit (2026-08-14) — prerequisites, measured

| Finding | Status | Fix |
|---|---|---|
| **The Log vs buildings** | ✅ correct — corridor damages buildings (pump 1070→695 verified) + tower chip; knockback properly anchored-blocked | none |
| **MK landing splash** | ✅ fixed today — gate tested the generic `splash` flag (False for MK); every jump was silently single-target; slam now splashes units AND crown towers (king activation verified) | done |
| **Splash FLAGS wrong on real splash troops** | ❌ `dark_prince`, `executioner`, `witch`, `skeleton_king` (+ MK's normal swings) read `splash=False` → they fight **single-target** in the sim | curate `splash` flags in cards.yaml (one line each); same bug family as the leap gate |
| **No per-card splash RADIUS** | ❌ every splash attack uses the flat `_SPLASH_R = 1.9` fallback — Valk's 360° spin, Wizard's blast, Bowler's path all identical | add `splash_radius_tiles` (curate from Fandom per card; import where published); plumb `CardSpec.splash_r`; engine uses it over the constant |
| **E-Giant zap reflect** | ❌ not implemented — KB has only `[tank, building_targeting]`; sim E-Giant is a plain tank, so the "ranged-only" doctrine vs him is unlearnable in sim | add `reflect_dmg` + `reflect_radius_tiles` (Fandom: Zap Pack) to KB; engine: attacker within radius that damages him takes the zap back (attack-path change — spells excluded); unit test like today's |
| **Spawn damage coverage** | ⚠️ modeled (`_deploy_blast`) and curated for MK (430), Goblin Drill (84), Ice Wizard (84 nova) — but the Fandom "spawn damage" category needs a sweep for the rest (Royal Delivery's recruit, Suspicious Bush, Goblin Demolisher, Void-class...) | audit pass against the category page; curate missing `spawn_damage` entries |
| **sim-view AOE circles** | 💡 user request — draw each splash troop's `splash_r` circle in sim-view so radius errors are *visible* | small sim_view addition once `splash_r` exists |

These land BEFORE evo mechanics (several evos modify exactly these systems).

### §0.1 Sweep results (2026-08-15) — FOR USER VERIFICATION, then restart as round 5

Both sweeps resolved from the stats import itself (`cards-import` had scraped the published
values all along — `build_spec` just never read the `splash_radius` key; now wired through, with
a curated `splash_radius_tiles` override retained for corrections). My earlier hand-curated
Skeleton King 1.5 was WRONG (published 1.3) and has been removed — the import is the single
source; the three curated radii were deleted.

**Table 1 — AOE attack radii (tiles, published, now flowing into `CardSpec.splash_r`):**

| Card | r | Card | r | Card | r |
|---|---|---|---|---|---|
| baby_dragon (+evo) | 1.5 | ice_spirit | 1.5 | skeleton_dragons | 1.5 |
| bomb_tower | 1.5 | ice_spirit_evo | **2.0** | skeleton_king | 1.3 |
| bomber (+evo) | 1.5 | ice_wizard | 1.5 | sparky | 1.8 |
| dark_prince | **1.25** (2.2 charged) | mega_knight (+evo) | 1.3 | valkyrie (+evo) | 2.0 |
| fire_spirit | 2.3 | mortar (+evo) | 2.0 | wall_breakers (+evo) | 1.5 |
| goblin_demolisher | 1.5 | princess | 2.0 | witch (+evo) | 1.5 |
| heal_spirit | 1.5 | — | — | wizard (+evo) | 1.5 |

Cards with splash but NO published radius stay on the 1.9-tile fallback: bowler + executioner
(their area is really a rolling/boomerang PATH — modeled separately via `multi`), electro_dragon
(chain, not blast).

Dark Prince is **user-verified**: 1.25 base, widened to **2.2 on a charged strike** — the engine
now carries `charge_splash_r` (a completed run-up replaces the hit's damage AND its blast radius).

**Table 2 — spawn damage (deploy/surface blast; engine `_deploy_blast` reads these already):**

| Card | Spawn dmg | Crown dmg | Blast radius |
|---|---|---|---|
| barbarian_barrel | 230 | — | 1.9 fallback |
| electro_wizard | 115 | — | 3.0 — spawn ZAP also **stuns** (blast now applies status) |
| goblin_drill (+evo) | 84 | 26 | 1.9 fallback |
| ice_wizard | 84 | — | 1.5 — spawn nova now also applies his **slow** |
| mega_knight (+evo) | 430 | — | 1.3 |
| royal_delivery | 437 | — | 1.9 fallback |
| royal_ghost_evo | 81 | — | 1.9 fallback |

`_deploy_blast` now runs `_apply_status` on everything it hits, so status flags ride spawn
blasts: E-Wiz's zap stuns, Ice Wizard's nova slows. (MK/drill/delivery have no status flags —
unchanged.) E-Wiz values **user-verified** (115 dmg / 3.0 tiles) — both sweep tables are now
fully verified; no [verify] tags remain in §0.1.

**Ranged-AOE audit (no change needed):** bomber, wizard, princess, sparky, firecracker already
fire real projectiles (speed imported) whose impact blast radius = their published splash radius
(bomber 1.5, wizard 1.5, princess 2.0, sparky 1.8). The bomber pattern was already the general
pattern. magic_archer remains the known exception — his is a piercing LINE (T2 primitive, §2).

**Bonus — death-damage radii the import also carries** (death blasts partially modeled; radii
now available to plumb the same way): balloon 3.0, bomb_tower 3.0, giant_skeleton 3.0,
goblin_demolisher 2.5, golem 2.0, phoenix 1.5, skeleton_barrel (+evo) 2.0.

**Death mechanics landed (2026-08-14, user-requested):** lumberjack drops a Rage on death
(3 tiles / 4.5 s / +30% move+attack speed, 0.5 s arm); phoenix drops an egg once (239 hp,
hatches in 3.8 s → reborn at 80% hp/dmg, no death blast, no second egg); skeleton_barrel
kamikaze-dives on reaching a building (death blast 145/2.0 + 7 skeletons — no contact damage);
rascal girls' collision radius 0.45 vs the boy's 0.75 (`component_collision_tiles`). The evo
barrel's second mid-flight drop stays a Phase-B/T1 row.

**CRITICAL FIX (2026-08-14): imported `_evo` stat rows were never read.** `build_spec` stripped
the `_evo` suffix and read only the BASE row plus a curated `evolution:` dict — so every
Phase-A T0 evo silently fielded **base stats** (Evo Bomber 304 hp instead of 332, all 41
affected). The evo row now overlays the base before parsing; curated mechanic dicts (our
Knight/Tesla) still apply on top. Phase A's "T0 stat-evos work end-to-end" is only true from
this fix onward. Also landed: **Evo Bomber bouncing bombs** (T2 projectile-continuation
primitive: 2 bounces, 2.5 tiles apart along the heading, same blast, once-per-attack dedup per
16/12/2024) and **Suspicious Bush** rebuilt (81 hp ghost — invisible for life, building-only,
never attacks, breaks into 2 Bush Goblins 304 hp / 227 dmg on arrival or death; the imported
row had pinned the goblins' stats on the parent).

---

## 1. The 42 evolutions

All 41 in the KB + **Evo Elite Barbarians** (Season 86 — wiki page still unscrapeable; full row
curated from the announcement). **The [verify] sweep is COMPLETE (2026-08-14)** — every row below
is wiki-swept. ✅ = modeled and unit-tested in the sim. Tier = engine effort for the rest: **T0**
stat-only (works via the `_evo` stat overlay), **T1** maps onto an existing engine primitive,
**T2** needs a new primitive.

**2026-08-14 (sweep 3): EVERY row below is now MODELED and unit-tested** (`tests/test_evo_t1.py`,
`test_evo_phase_b.py`, `test_evo_wave3.py`). The per-row tier notes are kept as implementation
references. Honest approximations: the Cage reels victims to REACH (fisherman semantics) rather
than inside the building; the Snowball's carry is an instant sweep to the corridor end; the LJ
ghost's "unlimited health" is a big-but-finite pool (spells can still clear it); the Drill's
resurfacing triggers on quarter-hp thresholds; the Baby Dragon's 8x9 gust is a 4-tile aura.
Values marked [verify] remain: dart-goblin poison numbers, cannon per-ball 87, skarmy General
stats, royal-hogs fall damage 74, LJ-ghost lifetime 5 s, hunter net range 5.5, cage reel timing.

| Evolution | Cycles | Special mechanic vs base (SWEPT) | Status / engine mapping |
|---|---|---|---|
| Knight | 2 | −60% damage while not attacking | ✅ done (`damage_reduction`) |
| Tesla | 2 | periodic stun pulse; 25 s life | ✅ done (pulse fields) |
| Skeletons | 2 | +1 evo skeleton per landed swing, hard cap 8 alive | ✅ done (spawn_on_hit) |
| Royal Giant | 1 | every shot blasts 2.5 t AROUND HIMSELF, 1-tile shove, air immune | ✅ done (recoil; dmg 154 [verify]) |
| Royal Recruits | 1 | charge arms only AFTER the shield breaks; 2.5 t run-up, 2× | ✅ done (charge_after_shield) |
| Barbarians | 1 | self-rage per swing: +30% move/attack for 3 s, no stacking | ✅ done (hit_rage) |
| Musketeer | 2 | 3 SNIPER rounds: infinite range, only when out of reach, 1.8×, never at crowns | ✅ done (sniper ammo) |
| Archers | 2 | POWER SHOT at ≥4 tiles: 1.5×; reach 6 | ✅ done (power_mult) |
| Valkyrie | 2 | 0.5 s whirlwind per swing: 5.5 t pull (ground AND air), 76 dmg | ✅ done (attack_nado) |
| Zap | 2 | growing TRIPLE pulse: 2.5→3.0→3.5 t, ~1 s apart, full zap each | ✅ done (zap_pulses) |
| Firecracker | 2 | shots leave SPARK ZONES: tick every 0.25 s, 15% slow, 2.5 s | ✅ done (tick dmg 12 [verify]) |
| Bomber | 2 | bomb BOUNCES twice, 2.5 t apart, once-per-attack dedup | ✅ done (bounce chain) |
| Bats | 2 | heal 99 per swing, OVERHEAL to 2× (244) | ✅ done (hit_heal) |
| PEKKA | 1 | flat 470 heal per kill, overheal to 150% | ✅ done (kill_heal) |
| Skeleton Barrel | 2 | 2 barrels: first drops at 75% hp, second on death, both on unspent arrival | ✅ done (mid_drop) |
| Goblin Barrel | 2 | second DECOY barrel to the MIRRORED tile: 3 decoy goblins (32 hp [verify]) | ✅ done (decoy_mirror) |
| **Elite Barbarians (S86)** | 1 | rage-tipped JAVELIN every 5 s (284, hits crowns) + rage TRAIL | ✅ done (javelin; page pending import) |
| Wizard | 2 | FIRE SHIELD; on shield break: 231 explosion + 3-tile knockback in 3 t | T1 — shield exists; break-blast hook |
| Witch | 1 | HEALS when each of her spawned skeletons dies; overheal to 124% | T1 — death-hook heal |
| Skeleton Army | 1 | 15 skels + shielded GENERAL: skels dying while he lives become invisible INDESTRUCTIBLE GHOSTS that keep attacking; ghosts vanish with him | T2 — ghost-body lifecycle |
| Mortar | 2 | hit speed 1 s faster + every shot spawns a GOBLIN at the mortar | T1 — spawner-on-attack |
| Cannon | 2 | DEPLOY VOLLEY: 9 cannonballs in 2 rows (5+4), area + knockback | T1 — deploy burst |
| Goblin Cage | 1 | ground troops within 3 t get PULLED INTO the cage and fought inside | T2 — hook machinery (fisherman) reusable |
| Goblin Drill | 2 | near crowns: submerges/reappears around the tower as it takes damage, spawning goblins each surfacing | T2 — relocation loop |
| Goblin Giant | 1 | below 50% hp: passively spawns a goblin every 2.2 s | T1 — conditional spawner |
| Battle Ram | 2 | SUPER CHARGE: re-charges and bounces off buildings repeatedly until its hp is gone; breaks into EVO barbarians | T2 — bounce-recharge loop |
| Hunter | 2 | NET every 5 s: roots the closest unit 3 s (no move/attack), resets charges/ramps | T1 — stun-with-attackable ≈ root |
| Ice Spirit | 1 | bigger freeze (2.0 t radius in Table 1) | T0 — radius flows already |
| Inferno Dragon | 1 | KEEPS its damage stage on kill (9 s memory); 4th stage at 20 s = 2× stage 3 | T1 — focus_time carry-over |
| Lumberjack | 2 | death rage (base ✅) + his GHOST spawns on death: untargetable, spell-only, short-lived, keeps swinging | T2 — untargetable attacker |
| Mega Knight | 1 | MEGA UPPERCUT: every swing launches the target 4 tiles TOWARD the nearest enemy crown tower, ignoring weight | T1 — directed knockback_all |
| Minion Horde | 2 | HORDE IMMUNITY: first hit against each minion makes it INVINCIBLE for 3 s | T1 — per-unit i-frames |
| Princess | 2 | every volley cycle: 1 SLOWING shot (3-tile, 7 s slow) then 2 normal | T1 — periodic status shot |
| Royal Ghost | 2 | spawns 2 SOLDIERS on deploy; stealth unchanged | T1 — deploy companions (spawn_spec) |
| Royal Hogs | 2 | deploy FLYING (ground-targeters can't touch them); FALL on attacking/getting hurt with small area impact | T2 — air→ground transition |
| Baby Dragon | 2 | WIND AURA around him: enemies −30% speed, allies +30% | T1 — moving rage/slow aura |
| Dart Goblin | 2 | POISON darts (DoT on hit) that grow stronger the longer he lives | T1 — stacking DoT |
| Electro Dragon | 1 | chain hops INDEFINITELY (3.5 t hops while >1 enemy in range) | T1 — chain count ∞ |
| Executioner | 1 | AXE SMASH: pushes ground AND air back 2 tiles, resets charges; 3.5 t | T1 — knockback on hit |
| Furnace | 2 | spawns every 2.4 s, fire spirits emerge to the SIDES | T0.5 — spawner params |
| Giant Snowball | 2 | SNOW BOWLING: rolls 4.5 t GATHERING troops (untargetable inside), frees them at the end; 4 s slow | T2 — carry-roll |
| Wall Breakers | 2 | rolling BARREL bodies whose blast is death damage (Super Wall Breaker) | T1 — death blast (radius in import) |

## 2. Implementation plan

**Phase A — opponents field evos at all** (highest value, no new mechanics):
1. Re-run `cards-import` (pulls Evo E-Barbs + any stat drift).
2. `meta_decks.yaml` schema: each deck gains one `evo:` slot (2026 rules: exactly 1 per deck).
   Populate from RoyaleAPI deck data where `decks-import` can see it; fallback heuristic = the
   deck's most-played evolution card (curate the top-20 pool by hand).
3. `ScriptedBot` evo-cycle tracking: mirror the agent-side `evo_charge` slot machinery (play the
   base `cycles` times → next play fields the `_evo` spec via the existing `build_spec` overlay).
   **T0 stat-evos work end-to-end at this point** — opponents field stronger versions on the
   right cadence, and the obs canvas/identity blocks already fold `_evo` onto base keys.
4. Gate: policy-stats vs the evo-pool must hold the standing gates; expect a real difficulty
   step (this is the point).

**Phase B — mechanics, by meta priority** (each with a unit test like today's MK/BB tests):
1. ~~Fidelity prerequisites from §0~~ **DONE 2026-08-14** (splash flags, radii, E-Giant, spawn
   sweep, plus the critical evo-stat-overlay fix above).
2. ~~T1 batch 1~~ **DONE 2026-08-14** — all eight, wiki-swept and unit-tested
   (`tests/test_evo_t1.py`): **Evo RG** recoil blast (2.5 t around himself per shot, 1-tile
   shove, air immune; recoil damage 154 curated **[verify]** — the wiki publishes the row but
   no scrapeable value); **Evo Skeletons** +1 evo skeleton per landed swing, hard cap 8 alive;
   **Evo Recruits** shield-gated charge (arms after 2.5 t once the shield is GONE, 2× = 266);
   **Evo Barbarians** self-rage per swing (+30% move/attack for 3 s, no stacking with rage
   zones); **Evo Valkyrie** whirlwind per swing (0.5 s vortex, 5.5 t, pulls ground AND air,
   76 dmg — reuses the tornado machinery); **Evo Zap** growing triple pulse (2.5→3.0→3.5 t,
   ~1 s apart, full damage+stun+crown each); **Evo PEKKA** flat 470 kill-heal with overheal to
   150% (imported hp 5640 was the CAP — deploy hp re-curated 3760, damage row restored);
   **Evo Skeleton Barrel** first barrel at 75% hp, second on death, both at once on an unspent
   arrival (KB `count: 2` was barrels-carried, re-curated to one body).
3. ~~[verify] sweep~~ **DONE 2026-08-14** — all 41 rows swept and re-tiered (see §1; several of
   my earlier guesses were wrong: Musketeer/Archers have SPECIAL shots, not piercing; Royal
   Ghost spawns Soldiers, no recoil; Mortar spawns goblins per shot, no rolling shell).
4. ~~T2 primitives~~ **DONE 2026-08-14**: sniper ammo (Musketeer), power shot (Archers),
   lingering ground effect (FC spark zones + E-Barbs rage trail), projectile continuation
   (Bomber), decoy (Goblin Barrel mirror). Plus the GOBLIN BARREL BASE FIX (it spawned nothing).
5. ~~Phase B remainder~~ **DONE 2026-08-14 (sweep 3)** — all remaining evos modeled + tested
   (see the banner above §1's table). Originally scoped as: (see table): T1 batch 2 candidates
   in meta order: Mega Knight uppercut, Executioner axe smash, Hunter net, Wizard shield-burst,
   Witch skeleton-heal, E-Drag infinite chain, Inferno stage-keep, Baby Dragon aura, Princess
   slow shot, Mortar/Furnace/Goblin Giant spawner tweaks, Minion Horde i-frames, Dart Goblin
   DoT, Cannon deploy volley, Wall Breakers death blast, Royal Ghost soldiers. T2: Skarmy
   general-ghosts, Snowball carry-roll, Goblin Cage pull-in, Goblin Drill relocation, Battle
   Ram bounce, Royal Hogs air-drop, Lumberjack ghost.
5. Evo E-Barbs specifically (midladder-hot per the user's 10k context): javelin = ranged attack
   with tower damage + the rage-trail ground effect; DOCTRINE.md will need a counter row once
   its behavior is testable.

**Phase C — verification + doctrine**: per-evo unit tests; a policy-stats run against an
evo-heavy pool; DOCTRINE.md rows for the evos that change our counters (Evo RG's recoil vs our
Tesla pull, Evo E-Barbs rage trails vs our IW slow, Evo Valk's pull vs our skels spacing).

**Cost honestly**: A ≈ one working session + a training run to gate. B.1–B.2 ≈ a session each.
T2 primitives are individually small-project-sized. The [verify] sweep is an hour of reading.

## Sources
- Imported KB (`cards_stats.json`: 41 `_evo` stat blocks; `cards-import` scrapes Evolution pages)
- gamingonphone + RoyaleAPI blog + kabutom note (Evo Elite Barbarians, Season 86: rage javelins,
  rage trail, cycle 1; Hero Berserker/Hero Valkyrie same season)
- sportskeeda evolution tier list (meta frequency prior); Fandom per-card Evolution pages are the
  [verify] source of record
