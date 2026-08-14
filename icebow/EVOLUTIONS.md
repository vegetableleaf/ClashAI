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

---

## 1. The 42 evolutions

41 in the imported KB + **Evo Elite Barbarians** (Season 86, Aug 2026 — not yet imported; re-run
`cards-import`). Icebow's own two (**Knight** — 60% DR while not attacking; **Tesla** — stun pulse
+ 25 s life) are **already fully modeled** for OUR side. Mechanics below from guides/knowledge;
rows marked **[verify]** need their Fandom Evolution page read before implementation — the
verification pass IS part of Phase B. Tier = engine effort: **T0** stat-only (works the moment an
opponent fields it — `build_spec` already overlays `_evo` stats), **T1** maps onto an existing
engine primitive (charge, pulse, DR, spawner, spawner_death, knockback, slow/stun/freeze, curse,
buff_mult, multi-hit), **T2** needs a new primitive.

| Evolution | Cycles | Special mechanic vs base | Tier / engine mapping |
|---|---|---|---|
| Knight | 2 | −60% damage while not attacking | ✅ done (`damage_reduction`) |
| Tesla | 2 | periodic stun pulse; 25 s life | ✅ done (pulse fields) |
| Skeletons | 1 | 4 bodies; each KILL spawns a new skeleton | T1 — spawn-on-kill ≈ spawner_death inverted; small add |
| Royal Giant | 1 | each shot RECOILS: knockback on the target + pushes himself back | T1 — knockback exists; self-push is a sign flip |
| Royal Recruits | 1 | shielded CHARGE dash across the lane | T1 — charge primitive exists |
| Barbarians | 1 | enrage themselves while attacking (speed/damage ramp) | T1 — buff_mult + focus_time ramp |
| Musketeer | 2 | charged SNIPER shot: extra-long-range piercing first shot | T2 — piercing projectile |
| Archers | 2 | charged power shot, pierces | T2 — same piercing primitive as Musketeer |
| Valkyrie | 2 | whirlwind PULLS enemies into her spin | T1 — tornado pull logic exists (small-radius pull on attack) |
| Zap | 2 | strikes twice (second zap after a beat) | T1 — two applications of the existing spell |
| Firecracker | 2 | lingering SPARKS burn the ground where shots land | T2 — lingering ground-effect primitive |
| Bomber | 2 | bombs BOUNCE past the first target | T2 — projectile continuation |
| Wall Breakers | 2 | [verify] survive/second blast behavior | T0/T1 pending verify |
| Bats | 1 | [verify] heal-on-hit (lifesteal) | T1 — small lifesteal add |
| Wizard | 2 | spawn shield + wider blast | T1 — shield ≈ temp DR; radius via splash_r work |
| Witch | 2 | [verify] | pending |
| Skeleton Army | 1 | [verify] re-summon behavior | pending |
| Skeleton Barrel | 2 | [verify] double pop | pending |
| Mortar | 2 | shells carry a passenger goblin (spawns at impact) | T1 — spawner-at-impact ≈ spawn primitive |
| Cannon | 2 | [verify] shockwave knockback shots | T1 if knockback-on-hit |
| Goblin Barrel | 2 | decoy barrel (second, empty barrel) | T2 — decoy entity (cheap: spawn nothing, draw fire) |
| Goblin Cage | 2 | [verify] | pending |
| Goblin Drill | 2 | [verify] extra goblin on surface hits | pending |
| Goblin Giant | 2 | [verify] | pending |
| Battle Ram | 2 | [verify] re-charge / bulldoze behavior | pending |
| Hunter | 2 | [verify] tighter spread or net | pending |
| Ice Spirit | 1 | [verify] bigger freeze / split | pending |
| Inferno Dragon | 2 | [verify] beam keeps ramp between targets | T1 — focus_time carry-over |
| Lumberjack | 2 | [verify] rage behavior on death exists base; evo = ? | pending |
| Mega Knight | 2 | [verify] jump changes | pending (leap system now correct) |
| Minion Horde | 2 | [verify] | pending |
| PEKKA | 3 | heals on kills (butterflies) | T1 — heal-on-kill |
| Princess | 2 | [verify] volley size/range | T0-ish pending |
| Royal Ghost | 2 | [verify] invisibility changes | T1 — invis fields exist |
| Royal Hogs | 1 | [verify] | pending |
| Baby Dragon | 2 | [verify] | pending |
| Dart Goblin | 2 | [verify] poison darts (stacking DoT) | T1 — curse-like DoT |
| Electro Dragon | 2 | [verify] | pending |
| Executioner | 2 | [verify] axe behavior | pending (splash-flag fix first) |
| Furnace | 2 | [verify] | pending |
| Giant Snowball | 2 | [verify] grows/rolls further | pending |
| **Elite Barbarians (NEW, S86)** | 1 | throw **Rage-tipped javelins** at range (hits troops AND towers) leaving a RAGE TRAIL that buffs allies moving through it | T2 — projectile + lingering ground buff; the season's midladder menace |

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
1. Fidelity prerequisites from §0 (splash flags, per-card radii, E-Giant reflect, spawn sweep).
2. T1 batch 1 (common ladder evos): Evo RG recoil, Evo Skeletons spawn-on-kill, Evo Recruits
   charge, Evo Barbarians self-rage, Evo Valkyrie pull, Evo Zap double-hit, Evo PEKKA heal.
3. [verify] sweep: read each pending evo's Fandom page, fill the table, re-tier.
4. T2 primitives, in order of reuse: piercing projectile (Musketeer+Archers), lingering ground
   effect (Firecracker sparks + **Evo E-Barbs rage trail**), projectile continuation (Bomber),
   decoy (Goblin Barrel).
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
