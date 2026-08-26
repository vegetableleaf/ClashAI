# Sim-parity conflicts — every escalation, verified-row overturn request, and in-game check queued for the owner


## 2026-08-25 — hero ability extraction (bowler_hero, tombstone_hero, berserker_hero)

1. **berserker_hero release date** — `Berserker/Hero` infobox (revid 437529) says **4 August 2026**;
   `Heroes` master page History (revid 437509) says **3/8/2026** ("allowed the Berserker and Valkyrie
   to have a hero form"). Berserker/Hero has no History section to break the tie. UNRESOLVED —
   carried from the R1b sweep. YAML uses the subject page's infobox value (2026-08-04) with the
   conflict noted inline.

2. **bowler_hero Stone Swish shot count** — prose ("Ability: Stone Swish" section, revid 437528)
   says "a total of 3 shots"; the Stone Swish Attributes table gives Hit Speed 1.9 s over a 7.3 s
   duration, which allows 4+ shot opportunities. Both recorded in the YAML; actual count queued as
   an in-game check.

3. **(snapshot, not wiki)** `current_db_snapshot.json` base tombstone is internally inconsistent:
   `spawn_interval_s: 4.0` vs `spawns.interval: 3.5`. `Tombstone/Hero` (revid 437388) says
   Spawn Speed 4 sec. Snapshot cleanup item.

## 2026-08-25 — hero ability extraction (magic_archer_hero, balloon_hero, dark_prince_hero)

1. **magic_archer_hero rarity** — `Magic Archer/Hero` (revid 437520) infobox and attributes table
   say **Legendary**; the intro prose says "is a {{Rarity|Common}} card". Infobox/table used in
   the YAML; prose looks like boilerplate copy error (the same paragraph style appears on other
   hero pages).

2. **magic_archer_hero deploy cost** — same page: infobox `Cost=4` and attributes table say
   **4 elixir**; intro prose says "costs 3 {{Icon|I=Elixir}} to deploy". Infobox/table (4) used;
   prose (3) recorded as conflicting value.

3. **magic_archer_hero body damage vs snapshot** — hero vardefine `dmg_11|135` vs base
   `current_db_snapshot.json` magic_archer damage **133** (base row `verified: false`), and the
   page History logs a **6% hero damage nerf on 4/8/2026** that may or may not be baked into 135.
   +2 delta recorded as SUSPECT; needs base-page cross-check or in-game measure.

4. **balloon_hero Skeletrooper soar range** — `Balloon/Hero` (revid 437524): ability attributes
   table says **6.5** tiles; ability prose says "within **6** tiles". Both recorded; table
   preferred per extraction rules; in-game check queued.

5. **balloon_hero ability name** — subpage heading + {{Hero Ability}} say **"Coffin Cadets"**
   (plural); `Heroes` master table (r1b ledger) says **"Coffin Cadet"** (singular). Cosmetic but
   the in-game string should settle it.

6. **dark_prince_hero body hit speed** — `Dark Prince/Hero` (revid 437359): attributes table says
   **1.4 sec**; the page's own vardefine `atk_speed|1.3` (which drives its DPS column) and the
   base snapshot both say **1.3**. Both recorded; determines whether the hero body has a hit-speed
   delta at all.

7. **dark_prince_hero Rhino charge distance** — Rhino Attributes table "Charge Range" = **3**;
   History 1/6/2026 says "first charge distance increased to **2.5** tiles (from 0)". Possibly two
   different mechanics (windup distance vs detection range) or a stale table. Both recorded.

8. **dark_prince_hero charge splash vs snapshot** — hero page Charge Attributes Splash Radius =
   **1.1**; base snapshot `charge_splash_radius_tiles` = **2.2** (snapshot also carries
   `splash_radius: 1.1` vs `splash_radius_tiles: 1.25` for the normal attack, so the two scales
   are not directly comparable). Flagged as possible body delta, not asserted.

9. **dark_prince_hero ability uses** — page states **no** uses/cooldown anywhere. The other two
   assigned hero pages were made single-use on 4/8/2026; Dark Prince's History is silent. `uses:
   null` in the YAML; in-game check queued.

## 2026-08-25 — hero ability extraction (goblins_hero, mega_minion_hero, barbarian_barrel_hero)

1. **barbarian_barrel_hero barbarian hit speed** — `Barbarian Barrel/Hero` (revid 437523):
   Barbarian Attributes table says **1.3 sec**; the page's own `atk_speed` vardefine is **1.4**
   (it drives the DPS column of the level table). Both recorded in the YAML; which is live is
   queued as an in-game check. (Ledger base barrel-barbarian is 1.3; the Barbarians card is 1.4.)

2. **barbarian_barrel_hero rerolldmg_11 = 116, meaning** — same page: the vardefine is named
   `rerolldmg_11`, but the level-table column it feeds is headed **"Crown Tower Damage"**.
   116 is exactly 50% of the 232 barrel damage, consistent with either reading (half-damage
   second roll vs 50% crown-tower multiplier). Both recorded; in-game check queued.

3. **(cross-source, not wiki-internal) barbarian_barrel_hero barbarian HP** — hero page hp_11=716
   vs ledger base 670; the page History documents only a +4% buff (670*1.04 = 697 ≠ 716,
   716/1.04 = 688.5). Page number recorded as-is; noted in the YAML caveat.

In-game checks queued for the owner (full list in each YAML's open_questions):
- goblins_hero: Banner Brigade use count per banner; exact brigade spawn offset/formation;
  whether a brigade goblin's death can drop a second banner.
- mega_minion_hero: does the 25% crown-tower multiplier apply pre-warp or only post-warp
  (History says the reduction is "now permanent"); warp damage single-target vs area;
  marker eligibility (current vs max HP, buildings/towers included?); repeat use allowed?
- barbarian_barrel_hero: hit speed 1.3 vs 1.4; meaning of 116 (reroll damage vs crown tower
  damage); heal basis (damage taken vs damage dealt); reroll direction/start point;
  one-use-only?

---

## 2026-08-25 — R1c champion specs: conflicts for owner batch review

### C1. RESOLVED 2026-08-26 (decisions.md ruling 9): wiki 332 @L11 is correct; 366 was a reverse-derivation anchored at a nonexistent champion level 1. Fix lands in I5.
`hogeq/config/cards.yaml` has `ability_bomb_damage: 366` with a comment asserting the value "is not
published in the KB." **It is published**: `vardefine escape_11 = 332` (statistics column
"Explosive Escape Damage", Mighty_Miner.wikitext archive).

Scaling both bases through `levels.py` PERCENT (L11=256, L13=309, L14=339):
```
366 @L11 -> L12 402  L13 442  L14 485
332 @L11 -> L12 364  L13 401  L14 440   <-- 440 EXACTLY at L14
```
HANDOFF §5 records the owner's in-game observation as **440 @ L13**, and 366 was REVERSE-DERIVED
from it — the same note conceding "No integer level-1 base gives exactly that", which was the tell.
The wiki's 332 reproduces 440 **exactly at L14**.

**The single question that resolves this: was Mighty Miner level 13 or level 14 when 440 was
observed?** (HANDOFF records him at 15 since 2026-08-19, so 14 is plausible for an earlier reading.)
* If **L14** -> the wiki is right, `366 -> 332`, and the "not published" comment is deleted.
* If **L13** -> the owner's reading stands, 366 is kept, and the wiki row is pinned as contradicted.
NOT CHANGED PENDING THE ANSWER (ruling 2: never auto-overturn an owner-sourced value).

### C2. RESOLVED 2026-08-26 (R2 adjudication #10): owner confirms 2.5 tiles. The sim's guess was right.
The archived page publishes NO blast radius: not in prose ("medium area damage"), not in the
Explosive Escape attributes table (only Cost / Deploy Time / Cast Time / Cooldown), not in History
or Trivia. The sim's **2.5 tiles remains a guess**. ⚠ The only published tile figure is the
**1.8-tile knockback**, which is a DISPLACEMENT — do not let a later pass conflate the two.
Resolution path: owner in-game measurement, or leave flagged.

### C3. Monk combo damage IS published — `cards.yaml` says it is not.
`vardefine combo_11 = 422`. The KB comment claims "The 3rd hit's EXTRA DAMAGE is not published, so
only the shove is modelled." Same error class as C1. Wiki leaves ambiguous whether 422 REPLACES or
ADDS TO the 140 base hit — needs a ruling before implementation.

### C4. Goblinstein stats possibly stale after 4/8/2026.
That update gives no-cooldown/single-use PLUS Doctor damage **+47%** and ability DPS **-12%**, but
the KB still carries `dmg_11 = 92` / `link_11 = 107`. Recompute or re-source at R2; not changed.

### C5. Boss Bandit — the sim's AUTO-TRIGGER is not in the source.
Getaway Grenade is documented only as a manual button; History 8/7/2025 says it may be used twice
"independent on Boss Bandit's hitpoints", i.e. an HP-gated model was REMOVED. The sim fires it
automatically below a rolled HP fraction (`ability_hp_frac`). Enemy champions still need SOME
trigger, so the fix is likely to move it from an engine rule to an opponent-AI heuristic.
Owner ruling requested.

### C6. Champion pages are stale on single-use (class-wide).
Monk (History ends 12/12/2025) and Skeleton King (24/10/2025) still print 17s / 20s cooldowns;
only the master Version_History carries the 4/8/2026 "Champions and Heroes (minus Boss Bandit)"
single-use line. Treat per-page cooldowns as unreliable.

### C7. Timing boilerplate, all four pages.
Each publishes THREE unreconciled figures (prose 1s delay, table Cast Time ~0.933-0.944s, table
Deploy Time), and prose says the cooldown starts "after the duration ends" while three of four
publish no duration at all. Likely copied boilerplate. Engine needs one chosen convention.

### C8. Intra-page contradictions recorded with BOTH values (see each ability YAML).
Archer Queen attack-speed buff stated three ways (+80% prose / +180% table / "to 180% from 200%"
History); Little Prince pushback (prose 0-2 tiles vs History 1/9/2025 2.5 tiles); Skeleton King
spawn radius (prose 4 tiles vs History 24/10/2025 3.5 tiles); Monk knockback immunity
(ability-scoped vs unqualified); Golden Knight has NO duration and NO dash travel speed, so chain
timing is not simulatable from the page alone; Goblinstein link geometry ("2 tiles" from the
Doctor, the Monster, or the line between them — never stated).


## R2 sweep 2026-08-26

Eleven independent R2 claim files (8 family sweeps + 3 cross-checks) merged into one canonical
ledger, `ledger/stat_diffs.jsonl`. Full owner batch review table: **`ledger/R2_REVIEW.md`**.
Nothing in `icebow/config/cards.yaml` or `cards_stats.json` was touched.

- **Coverage** — 179 distinct card keys swept, 3,321 field-checks. 14 keys came back with no line
  at all. 2,799 field-checks (84.3%) produced no claim; 522 did.
- **Merge** — 595 claim lines in, **556** canonical rows out. 39 `(key, field)` pairs were claimed
  twice; the claim with more sources was kept and the loser preserved under `dup_verdicts`.
  **26 duplicates agreed, 13 did not** and were forced to `escalate` (review section 2a). Three
  of those were promoted from a clean verdict purely by the merge: `elixir_collector.lifetime`
  (update vs escalate), `tombstone.spawns.interval` (pin 3.5 vs escalate 4.0),
  `goblin_curse.damage` (update vs escalate — both sides agree the value is 35, they disagree on
  whether an owner gate is needed).
- **Verdicts, canonical** — 316 escalate, 101 update, 73 match, 66 pin.
- **Escalation buckets** — 13 duplicate-claim disagreements, 115 curated `verified: true`
  contradicted, 125 split votes, 63 where the sources agree but the fix is a schema/engine
  decision.
- **Edit-war quarantines — 0.** All 595 incoming claims carry `edit_war: "pass"`; every sweep
  re-fetched its pages live on 2026-08-26 and revid-compared (most byte-compared) against its own
  archive. Two false CHANGED flags were traced to a `<!-- revid:... -->` provenance line an earlier
  fetch script had prepended to the archived copies, and cleared.
- **Level-ladder question closed** — 41 of the 66 pins are one finding: the wiki's per-level table
  is a MediaWiki `round(v11 * 1.1^(L-11))` render, not game data, so it cannot adjudicate a scaling
  model. `levels.py` is correct for the post-31/3/2025 game. Do not "correct" these back.

Open items C1-C8 above are unchanged by the merge except where R2_REVIEW cites them: C1 and the
`mighty_miner.ability_bomb_damage` 366 -> 332 fix are re-verified and still unapplied; C4 is
resolved (goblinstein Doctor damage 92 -> 135); the `skeleton_king` and `little_prince` halves of
C8 are resolved by dated History entries.

## 2026-08-26 — R2 #8 ENGINE/SCHEMA batch: gaps found while applying

Recorded per the batch rule "implement what the evidence supports and record the gap rather than
inventing numbers". Each entry is a MEASURED side effect or a source disagreement the seven
approved items did not cover.

### E1. RESOLVED 2026-08-26 by MEASUREMENT (owner-approved). Was: dropping `lifetime` re-priced the Furnace on a guess.

**Fix:** `threat_value` now reads a third key, `effective_life_s`, after `lifetime`/`lifetime_s`.
A real lifetime still wins; the measured value only applies to a spawner that WALKS and therefore
has none. MEASURED by deploying an ENEMY spawner (the direction `ignore_cost_frac` models) across
4 enemy levels x 15 placements, n=60 each, and timing death to our towers:
```
furnace      median 19.4s (p25 17.0, p75 21.2) -> 3.87 waves at 5.0s
furnace_evo  median 19.1s (p25 18.1, p75 22.0) -> 7.96 waves at 2.4s
```
`ignore_cost_frac("furnace")` **0.0936 -> 0.1815** (the stale-28s value was 0.2620, so the measured
answer lands between the two, as the measurement predicted it would).

⚠ It also fixed an ordering bug the flat fallback had reintroduced: under `_SPAWNER_WAVES = 2.0`
BOTH furnace rows got exactly 2 waves, so the Evo -- which spawns at 2.4s against the base's 5.0s
-- priced IDENTICALLY to the base. That is the same defect the 2026-08 spawn-interval fix removed
(HANDOFF §5: "correctly ranking the evo ABOVE the base for the first time"). Now
**furnace_evo 0.3724 > furnace 0.1815** again. 4 tests, both decks.

### E1-original (kept for the record).

`threat_value._spawner_cost` computes "how many waves it actually gets" as `lifetime / interval`.
With the stale 28 s that was 28/5 = 5.6 waves; with no lifetime it falls back to the module's flat
`_SPAWNER_WAVES = 2.0`.

MEASURED `ignore_cost_frac("furnace")`: **0.2620 -> 0.0936**, i.e. the sim now treats an
unanswered Furnace as roughly a third as costly to ignore.

Neither number is sourced. The honest bound for a spawner that now WALKS is "however long it
survives", which the pricing model cannot see: MEASURED, a Furnace deployed at y=0.80 reaches a
crown tower and dies at **t = 18.7 s**, i.e. ~3.7 waves — between the old 5.6 and the new 2.0.
Applying the owner's ruling was still correct (the ruling is about the card's lifetime, not about
threat pricing), but `_SPAWNER_WAVES` is now load-bearing for this card and nothing measured it.
**Owner decision needed**: is a flat 2 waves the right reading for a walking spawner, or should
`_spawner_cost` bound waves by survival time instead?

### E2. `lifetime_s` is imported by `card_mechanics.json` but not DECLARED by it.

That file's own `meta.imports` reads "mass, sight, collision, load_time, deploy_delay,
knockback_immune" and its docstring justifies sitting above the wiki layer on the grounds that
only STRUCTURAL constants are imported. `lifetime_s` is neither declared nor structural — it is a
balance value from a dump frozen 2023-10-18, and it outranks the live wiki for every card that
carries one.

Only the Furnace row was removed here, because a blanket demotion is NOT behaviour-neutral.
MEASURED, comparing the mechanics layer against `cards_stats.json` for all 12 keys that carry
`lifetime_s`: 10 agree exactly, `goblin_drill` differs (9.0 vs 10.0) but is overridden by curation
anyway, and **`tesla` differs 30.0 (mechanics, live) vs 25.0 (stats)** — so demoting the field
across the board would silently change the Tesla's lifetime. Tesla lifetime is not in any R2
ruling; #5 rules only on its rarity and its evo's hitpoints. Left alone and flagged.

### E3. `furnace_evo.speed_tiles` 0.75 is stale but INERT — the LAG row overstates the impact.

r2_buckets LAG says the sim "copied the stale cell (furnace_evo 0.75 vs base furnace 1.0)". The KB
row does say 0.75, but `build_spec` reads movement speed via `db.speed_tiles(base)` and an evo's
base is the parent card, so MEASURED `build_spec("furnace_evo", 11).speed` is **1.0**, same as the
base. The stale cell never reaches the engine. Correcting the row is still right for tidiness, but
it is a data cleanup with no behavioural effect, not the sim defect the row implies.

### E4. giant_snowball_evo is still GROUND-ONLY, and flipping one field would break its roll.

Item 7 of the #8 batch asked me to verify the BASE Giant Snowball hits air and ground. It does:
`attacks ['air', 'ground']`, no cards.yaml override, and MEASURED 179.0 damage plus a slow applied
to knight, minions and bats alike. **No change was needed.**

But the item's stated premise — "the evo hits air+ground" — is FALSE of the current KB, and the
same is true of owner ruling #5, which says the Evo hits air AND ground. cards.yaml still reads
`giant_snowball_evo: {..., attacks: [ground], ...}`. MEASURED, Evo Snowball cast directly on top
of the target: knight 179.0 damage, **minions 0.0, bats 0.0** — the Evo cannot answer air at all
while the plain Snowball can.

Left unapplied ON PURPOSE, for a reason the ledger row anticipated but did not measure:
`rolls` is derived in build_spec as `kind == "spell" and "rolls" in flags and ground_only`, and
`ground_only` is `attacks == ["ground"]`. MEASURED by flipping the row in memory:

    attacks ['ground']         -> ground_only True,  rolls True,  roll_len 4.5
    attacks ['air','ground']   -> ground_only False, rolls False, roll_len 0.0

So the one-line data fix silently TURNS THE ROLL OFF. Fixing it properly means decoupling the
rolling corridor from `ground_only` — expressing the ground-only part of the pull on `carry_roll`,
as the r2_buckets row suggests — and it should land with the rest of the #5 Evo Snowball family
(roll_tiles 4.5 -> 4.0, slow_duration_s 4.0 -> 3.0, crown_tower_damage 54 -> 45), not alone.

## R4 collection 2026-08-26

Official CR API, 120 path-of-legends (2026-07) players, 3605 battles, **7173 deck-sightings**,
1771 distinct (cards, evo, support) rows -> `ledger/meta_evo_slots.json`. Comparable to the pool
in `config/meta_decks.yaml` (7353 sightings, same season). `evolutionLevel` and `supportCards` are
both present and usable; nothing was dropped as event-only this run.

### R4-1. A deck fields TWO OR THREE evolutions, not one. `opponents.py` said one.

The picker's own comment read "each deck fields ONE evolution (the 2026 slot rules)". MEASURED
distribution of evolution slots per deck-sighting:

    3 evos: 4282    2 evos: 2527    0 evos: 337    1 evo: 27

So **three is the mode** and one is nearly nonexistent. 6836 of 7173 sightings fielded at least
one. `ScriptedBot`'s slot machinery is single-slot, so it now fields the first DECLARED evolution
it can build and records the rest on `evo_declared`; MEASURED, that leaves **246 buildable slots
across the pool uncarried** (`tools/evo_audit.py`). **Owner decision needed**: widen the bot (and
the engine's charge accounting) to 2-3 concurrent evolution slots, or accept one as a deliberate
simplification of the opponent model?

### R4-2. Evolutions now have LEVELS, and the KB models a single stat block.

`evolutionLevel` is not a boolean. MEASURED across all card entries: level **1 x13346, 2 x4897,
3 x5**, with `maxEvolutionLevel` up to 3 (e.g. Wizard at evolutionLevel 2 of max 3). Every KB
`_evo` row is one undifferentiated stat block, so the sim cannot express an Evo Wizard at level 2
vs level 1. Not acted on -- flagged for R5/I4 scope.

### R4-3. TWELVE live evolutions have no KB row, and two of them are heavily played.

54 distinct cards were seen evolved; the KB carries 42 `_evo` rows. All 42 were observed (no dead
rows). MISSING, with sightings: **berserker 937**, **giant 277**, balloon 509, mega_minion 349,
mini_pekka 254, bowler 206, tombstone 195, barbarian_barrel 430, goblins 134, dark_prince 124,
ice_golem 71, magic_archer 79.

This CORRECTS the framing of the phantom-evo bug. Of the three examples in the I2 brief,
`arrows_evo` is a true phantom -- **arrows was never once seen evolved in 7173 sightings** -- but
`berserker_evo` and `giant_evo` are REAL evolutions the KB simply lacks. `build_spec` raising on
all three is still right (returning the base card under an evo name is wrong either way), but the
consequence differs: 35 decks declare a berserker evolution and 10 a giant one, and they field
NOTHING until the importer grows those rows. `meta_decks.yaml` already declares them, so they
light up on their own once I4 lands. Queued for I4 (importer hardening), not patched by hand.

### R4-4. Tower troops exist and the KB has no concept of them.

`supportCards` is populated on 7131 of 7173 sightings: **tower_princess 6455, cannoneer 288,
dagger_duchess 228, royal_chef 160**. None is a KB card, so all four appear in `unmapped_names` --
that is the honest report, not a mapping bug. Captured as `support:` per deck (data only): the
engine has one hard-coded crown-tower model, so a Cannoneer or Dagger Duchess currently plays as a
Tower Princess. ~10% of top-ladder opponents field a non-default tower. **Owner decision needed**:
is tower-troop variety in scope for sim parity at all?

### R4-5. Slot coverage is 235/1000 decks, because the pool is 19 days older than the sweep.

Joining on the exact 8-card set matches 235 of the 1000 pool decks -- but **69.3% of the pool's
sampling weight**, since the popular decks are stable and the long tail is one-offs. 233 of the
235 carry an evo (2 were only ever seen unevolved). The other 765 declare no slot and field no
evolution, which is the intended failure direction.

No inference was used to widen this: MEASURED, P(evolved | card in deck) is not bimodal -- 36 of
the 109 cards with >=100 sightings sit between 0.15 and 0.85 (cannon 0.63, mega_knight 0.57,
balloon 0.68) -- so a marginal rule would be a guess wearing measured clothes. `deck_import.py`
now writes `evo:`/`support:` alongside `cards:`, so the next `run.py decks-import` regenerates
pool and slots together at full coverage.

### ⚠⚠ R4 CORRECTION 2026-08-26 — `evolutionLevel` DOES NOT MEAN "this card was in an evolution slot"

The R4 collection agent read the battlelog's `evolutionLevel` as the deck's evolution slot and
concluded (a) decks field THREE evolutions as the mode and (b) `berserker_evo`/`giant_evo` are
real evolutions the KB lacks, seen 937/277 times. **Both conclusions are wrong.** Measured:

1. **Three evolutions is not legal.** Card Evolution page, verbatim: the 16/3/2026 Mid-March Update
   "changed the format of Evolution and Hero slots into one Evolution, one Hero and one Wild (from
   2 evo and 2 hero)". Max two evolutions. The field yields **3 for 153/233 decks** (live re-probe:
   3 evos ×114, 2 ×95, never 0 or 1). A field that reports an illegal state is not reporting slots.
2. **Berserker has NO evolution.** `Card Evolution` master page: **"Berserker" appears 0 times.**
   "Giant" appears only inside Royal Giant / Goblin Giant links; "Arrows" only as the Evo
   Princess's "Ice Arrows" ability. This CONFIRMS R1's negative probes (no `/Evolution` subpage)
   and refutes the collection's claim.
3. **Slot order does not identify them either.** Set positions across 209 live decks:
   index 0 ×209, index 1 ×115, index 2 ×208 — position 1 is LESS common than 2, so they are not a
   prefix; only 115/209 form one.

**Actual meaning:** the player's OWNED evolution level for that card (absent when they have not
unlocked it — e.g. a barbarian_barrel with `maxEvolutionLevel: 2` but `evolutionLevel: null`).
It cannot identify what was fielded.

**Action taken:** all 233 `evo:` declarations STRIPPED from both decks' meta_decks.yaml (a header
note records why). `support:` (tower troop, exactly one per deck — tower_princess 6455, cannoneer
288, dagger_duchess 228, royal_chef 160) IS reliable and is KEPT. The build_spec guard and the
opponents.py "declared slot or nothing" architecture are correct and stay; only the DATA was bad.

**Consequence, stated plainly:** `evo_audit` now reports 0 phantoms AND 0 real — opponents field
no evolution at all. That is honest but incomplete. NB the fidelity loss is smaller than it looks:
a phantom resolved to the BASE card's stats anyway, so it was a mislabel more than a strength
error. Real evo slots need another source — an owner decision (I3 remains OPEN):
  (a) curated top-20 mapping by hand (the plan's documented fallback), or
  (b) infer from per-card evolution frequency in the pool, or
  (c) leave opponents evo-less until a better source appears.
