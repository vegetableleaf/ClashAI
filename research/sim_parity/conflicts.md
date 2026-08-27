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

### I3 RESOLVED 2026-08-26 — field every LEGAL evolution, drawn per match

The open question above listed three options: (a) curate a top-20 mapping by hand, (b) infer from
per-card evolution frequency, (c) leave opponents evo-less. **None was taken**, because all three
still try to answer "which card did this player slot?", and nothing published answers it.

Implemented instead: each deck carries `evo_candidates` -- its own cards that really HAVE an
evolution, the deck intersected with the 42 wiki-verified evolutions in `ledger/r1a_evolutions.json`
(which match the KB's 42 `_evo` rows exactly, zero additions, zero removals). `ScriptedBot` draws
ONE of them uniformly per match from its own RNG. That is DERIVED, VERIFIABLE DATA, not an
inference about a player: (a) would have been a guess with a curator's name on it, and (b) was
already measured non-bimodal (36 of the 109 cards with >=100 sightings sit between 0.15 and 0.85
P(evolved | in deck)), i.e. a guess wearing measured clothes. A fixed slot is also worse TRAINING
than a draw -- the policy would overfit one opponent evolution per deck instead of facing the
variety it meets on ladder.

MEASURED, `tools/evo_audit.py`, both decks (identical output):
```
                        before (84e144a)   after
decks fielding a REAL evolution      0     1000/1000 (100.0%)
phantoms                             0     0
candidates failing build_spec        n/a   0
mean candidates/deck                 n/a   3.269  (hist 1:26 2:263 3:337 4:215 5:121 6:28 7:7 8:3)
distinct evolutions fielded          0     42 of 42, over 20 draws x 1000 decks
```
Top of the sampled distribution: skeletons_evo 6.37%, zap_evo 6.33%, elite_barbarians_evo 4.74%,
valkyrie_evo 4.34%, giant_snowball_evo 3.71%.

`deck_import.py` no longer tallies `evolutionLevel` at all -- it wrote the 233 bad `evo:` slots and
the next `run.py decks-import` would have re-created them. It now writes the derived
`evo_candidates` instead, and `sim/meta_decks.py` re-derives them when an entry has none, so a
regenerated pool cannot silently go evolution-less. A stale `evo_candidates` in the YAML is
validated against the KB on load, so it can only ever under-report, never resurrect a phantom.

The DECLARED-slot path (`evo:`) is kept and still outranks the draw, for the day a source names a
real slot. Nothing ships one today.

**Cap:** ONE evolution. The 16/3/2026 loadout is one Evolution + one Hero + one Wild, so two are
legal, but the second is the WILD slot -- it also takes a Hero and the engine has no Hero model.
Out of scope, noted in the code.

### I3 SIDE EFFECT — three tests were passing on luck, not on logic

The draw takes one value from the bot's RNG, which is `env.rng`: `reset()` builds the opponent and
then shuffles OUR cycle from the same stream. One extra draw therefore shifts the deal, the sampled
enemy tower level and the sampled opponent deck. Three tests went red, and NONE of them was testing
what its name says:

1. `test_tesla_discipline` (icebow) -- `doctrine_cards` only nominates HOLDABLE cards, so the whole
   nomination half of that file was testing the deal. hogeq had already found and fixed this (its
   `_deal()` helper says so verbatim: "passed on the IceBow deck only because that deck's opening
   cycle happened to contain the Tesla"); icebow's copy had never been backported. Adopted hogeq's
   version, and dealt the Tesla in the last negative test too -- it was passing VACUOUSLY in both.
2. `test_rocket_doctrine.test_the_pump_is_not_rocketed_in_overtime` (icebow) -- `fresh()` disarms
   prior rule 5 with `_defensive = False`, but rule 5 has a SECOND trigger (`t >= _double_time`)
   that re-arms in overtime, and it then bumps rocket whenever `op_low >= my_low`. Whether that
   holds on a fresh board is decided by the randomly sampled enemy tower level (MEASURED: ours 4424
   vs theirs 4858 under one seed, the reverse under another). Added `win_the_tiebreak()`.
3. `test_hogeq_pressure_doctrine.test_a_pump_deep_in_their_half_is_a_punish_window` -- the T1 punish
   is VETOED when the opponent holds a P.E.K.K.A, and `reset()` deals a random meta deck. MEASURED:
   reset #2 of a run deals a pekka deck; the shift moved it onto this test. `fresh()` now pins a
   plain `NEUTRAL_OPPONENT` deck, putting all five deck-keyed doctrine rules
   (pekka/tornado/earthquake/rocket + `known`) on their default branch. All 19 tests in the file
   still pass, including the pekka veto test, which puts its P.E.K.K.A on the BOARD.

These are repairs to latent test fragility that the change EXPOSED, not to behaviour it broke: no
doctrine, engine or reward code was touched for any of the three.

## I1 — hogeq -> icebow backport, 2026-08-26

hogeq was strictly ahead; the two decks now share one engine, one card KB and one level scaler.
Ported, plus one fix that belonged in BOTH decks.

**`sim/engine.py` is now BYTE-IDENTICAL between the decks.** hogeq's was a strict superset: the
only icebow-only code was the superseded `trail_dmg`/`trail_next` spark model. Ported:
`spell_build_dmg` (+ CardSpec field, `build_damage` wiring, and the buildings branch in
`_tick_zones`, along with that hunk's `hits_hidden` / flyer filter), `zone_first_tick_now`,
`champion_ability()` + `_ability_uses_left()` + the four `ability_bomb_*` / `ability_delay` fields
+ the cooldown/transit tick, `recoil` + `_recoil()` + its `_launch` call site, and
`spark_end_dmg` + `_drop_spark_zone()` replacing the every-1.25-tiles trail.

**`cards.py` is now BYTE-IDENTICAL.** Ported `_ability` elixir pricing, `evo_cycles()` reading the
evo row directly, the `deck_slots()` 0-cycle guard, and `ability_identity()` /
`policy_identities()`.

**`config/cards.yaml` now differs ONLY in the `deck:` block.** Every other difference was a CARD
fact, not a deck fact: Earthquake's three-wave zone, Firecracker's 1-tile recoil, Evo Firecracker's
cycle count, and the Mighty Miner's ability block. Without them the ported engine paths would have
been dead code in icebow -- and they are not opponent-neutral there, since meta decks field all
four cards.

### MEASURED

`evo_cycles()` was gated on a curated `evolution.available` that only 6 base cards carry:
```
  evolutions reporting a cycle count:  6 / 42  ->  40 / 42  ->  42 / 42
```
The last step is a DATA gap this exposed: `minion_horde_evo` and `princess_evo` carry no
`evo_cycles` in the imported rows at all. Taken from the wiki's Cycles column via
`ledger/r1a_evolutions.json` (1 and 2) and curated in, with a test pinning all 42 against the
ledger. Minion Horde is the one that mattered -- 1, where the picker's `or 2` floor was fielding
its Evolution a full cycle late. No card that already reported a count changed, and no card without
an `_evo` row gained one (arrows / berserker / giant / hog_rider all still 0), so the wider gate
cannot invent an evolution.

`CardDB.deck()` was still on `1.1 ** (level - 11)` in BOTH decks while `build_spec` had long since
moved to `levels.PERCENT` -- so the two disagreed about the same card. Routed through `levels.scale`:
```
  icebow  worst delta -0.93%  (tesla damage L15 322 -> 319)
  hogeq   worst delta -0.76%  (mighty_miner hitpoints L15 3294 -> 3269)
```
Small, one-directional, and it grows with level: the table starts as 1.1^n rounded and stops
tracking it. Only `cli.py`'s deck display consumes this method, so no training path changed.

`opponents.py` no longer duplicates the cycle lookup: `db.evo_cycles()` now implements exactly the
same precedence for all 42, and the stale comment saying it could not be used is gone. The `or 2`
floor stays -- 0 would read as "already charged" forever.

### ICEBOW'S ACTION SPACE IS UNCHANGED, deliberately

icebow gets the champion_ability ENGINE path only. Its deck holds no champion, so
`ability_identity()` returns None and `policy_identities() == deck_identities()` -- MEASURED, card
head width 10 before and after, `env.n_cards == 10`, and `env` has no `ability_id` attribute at
all. Widening it to 11 would make every existing checkpoint refuse to load.
`tests/test_champion_ability_engine.py` (shared, byte-identical) pins the rule in the form that is
true of BOTH decks: the action space grows if and only if the deck holds a champion.

### Test-list reconciliation

New in BOTH, byte-identical: `test_champion_ability_engine.py` (17), and hogeq's
`test_evo_cycle_and_sparks.py` (22) made deck-agnostic -- the cycling tests now read whichever slot
the loaded deck marks evolved (Evo Firecracker in hogeq, Evo Tesla / Evo Knight in icebow) instead
of naming one, and the KB assertions are card facts both bases carry.

New in icebow, copied from hogeq: `test_earthquake.py` (19, engine zone mechanics) and hogeq's
`test_ramp_and_blast_geometry.py`, whose icebow copy had dropped the Firecracker recoil-retarget
class with the note "this engine has no self-recoil mechanic at all". It does now.

DELIBERATELY NOT shared, all deck doctrine or deck action space: `test_champion_ability.py`
(hogeq -- the action-space half), `test_earthquake_placement.py`, `test_hogeq_doctrine_cells.py`,
`test_hogeq_pressure_doctrine.py` (hogeq), `test_aim_assists.py`, `test_defensive_doctrine.py`,
`test_rocket_doctrine.py` (icebow).

## I0 — the parity harness, 2026-08-26

`tools/parity_check.py`, byte-identical in both decks and runnable from either. It fails on any
divergence that is not on its allow-list, so the failure mode this whole pass exists to remove --
a fix landing in one deck and never reaching the other -- is now loud instead of silent.

BASELINE RECORDED TODAY (both decks report identically, exit 0):
```
config (must be byte-identical):
  cards_stats.json 67,504 B | card_mechanics.json 22,438 B | detect_classes.yaml 5,542 B
  meta_decks.yaml 195,625 B | cards.yaml identical apart from its 783-byte deck block
src/clashrl: 80 files -- 60 shared identical, 20 declared different, 0 UNEXPECTED
tests/  (informational): 54 in both (45 identical, 9 differ), 3 icebow-only, 4 hogeq-only
tools/  (informational): 25 in both (23 identical, 2 differ), 5 icebow-only, 0 hogeq-only
```

`cards.yaml` is NOT allow-listed. It is checked by stripping the `deck:` block from both and
requiring the remainder to match -- a blanket allow would have hidden exactly the Earthquake /
Firecracker / Mighty Miner rows that were sitting in one KB and not the other before I1.

THE ALLOW-LIST IS TWO LISTS, and the split is the point:
* **DECK-SPECIFIC (11 entries, 12 files)** -- should differ forever: `sim/drills_*.py`,
  `sim/doctrine.py`, `sim/env.py`, `sim/opponents.py`, `train_sim_ppo.py`, `vision.py`,
  `policy_stats.py`, `llm_advisor.py`, `play.py`, `actions.py`, `cli.py`.
* **DRIFT (8 entries)** -- recorded, NOT blessed; this list should shrink: `sim/drill_env.py`
  (hogeq-only `_env_flag`, without which `CLASHRL_DRILL_*=0` silently selects the treatment arm),
  `sim/remote_pool.py` (icebow-only deck-record channel), `reward.py` (icebow-only
  `log_corridor_cell`), `train_rl.py` (two separate one-way ports), `perception.py` (hogeq's own
  comment says its threat-gate MEMORY fix is silently inert there -- a live bug), `replay_mine.py`
  and `env.py` (comment/docstring only, code agrees), `model.py` (icebow-only
  CLASHRL_SINGLE_CELL_MAP A/B switch).

VERIFIED TO ACTUALLY FAIL, not just to pass. Four probes, each reverted:
```
  shared engine.py edited          -> exit 1, "src/clashrl/sim/engine.py: contents differ"
  detect_classes.yaml edited       -> exit 1, "config/detect_classes.yaml: bytes differ"
  cards.yaml edited outside deck:  -> exit 1, "differs OUTSIDE the deck block"
  new unlisted file in one deck    -> exit 1, "only in icebow"
  clean                            -> exit 0, "PARITY OK"
```
It also reports allow-list entries that have since CONVERGED so the list can be pruned (`--strict`
fails on them). Currently 0.

NOT wired into the unit suites, deliberately: it would go red during any legitimate mid-work
divergence, and after a merge into the live tree the allow-list would describe a state that branch
has not reached yet. It is a CLI gate to run before a commit that touches shared code. Promoting it
to a suite test or a hook is a separate decision.

## I5 — applying the adjudicated ledger, 2026-08-26

340 changes applied (`ledger/i5_applied.jsonl`, one row each with key/field/before/after/route/
source/ruling), 50 recorded-not-applied, 23 deferred. Everything below is a place where the brief,
the ledger or a premise turned out to be wrong, or where a value was applied with a caveat that a
later pass must not silently "fix".

### ⚠ P1. `crown_damage_audit.py` could never have gone green. It audited the WIKI, not us.

The stage gate was "the crown audit is RED before I5 and GREEN after". As written the tool
compared the wiki's `crown_dmg_11` against the percentage in the wiki's OWN balance history --
a statement about Fandom. We do not edit the wiki, so applying data to our KB cannot change its
output: the 15 stale vardefines it printed are still there and always will be.

RETARGETED at our KB: same wiki-derived percentage (the only place the live figure exists),
but the number CHECKED is `build_spec(...).spell_tower_dmg` against `round(our full damage x
pct)`. The wiki-vs-wiki finding still prints as CONTEXT, because it is the entire justification
for `config/import_pins.json`, but it no longer drives the exit code. `--kb <path>` audits
another checkout so the negative control is reproducible rather than a story:

    pre-I5 configs (0905104)  exit 1, 9 stale IN OUR KB: fireball 207->172, arrows 31->24,
                              freeze 35->29, rage 54->45, vines 78->70, giant_snowball 54->45,
                              giant_snowball_evo 54->45, goblin_drill 26->0, goblin_drill_evo 26->0
    post-I5                   exit 0, "no discrepancies in our KB"

### ⚠ P2. "Discard royal_delivery's crown_tower_damage entirely" gave it FULL crown damage.

decisions.md #11 rules that Royal Delivery cannot hit crown towers. Deleting the field is the
literal reading and it does the opposite: `build_spec` had `tower_dmg = float(db.tower_damage(base)
or dmg)`, and with no crown value the fallback hands the card its full damage.
MEASURED: spell_tower_dmg 40 -> **385**. Fixed both ways -- the KB carries an explicit `0`, and the
falsy `or dmg` became `dmg if _td is None else _td` so a published 0 survives. Nothing else in the
KB was relying on the old behaviour (graveyard's 0 sat next to a damage of 0).

### ⚠ P3. The LAG bucket asks for a field whose DELETION was a fix (dark_prince).

`dark_prince.splash_radius_tiles: 1.1`. Commit ba71b8f deleted the curated
`splash_radius_tiles: 1.25` precisely because `_tiles_or` prefers the `*_tiles` spelling, so two
numbers on one row let the engine and every audit read different values in silence. The row's
imported `splash_radius` is already the bucket's 1.1. NOT APPLIED; recorded as a skip with the
reason. Caught by `tests/test_r2_engine_schema.DarkPrinceSplashShadowTests`.

### ⚠ P4. Five `verdict: update` rows carry a CORRUPT `proposed` in stat_diffs.jsonl.

The emitter took the first number out of the note instead of the value. Recovered from the notes
and applied from there; the ledger rows themselves are left as they are (the research is frozen):

    witch_evo.dps                     proposed 11.0   real 123  ("135/1.1 = 122.7 -> 123")
    witch_evo.damage                  proposed 135.0  real 135  (correct by luck)
    goblinstein.components[0].damage  proposed 11.0   real 135  ("92 x 1.47 = 135.24 -> 135")
    mighty_miner.damage_stages[0]     proposed 1.0    real 43   ("40 x 1.08 = 43.2 -> 43")
    skeleton_king.spawn_unit_stats.hitpoints  proposed 1.0  real 1  -- NOT corrupt: the summoned
        skeletons genuinely have 1 HP (table, prose, and the absence of any skel_hp vardefine).

### ⚠ P5. `ability_move_speed_tiles` was proposed in WIKI SPEED UNITS on a field named `_tiles`.

archer_queen 45 and golden_knight 120 are "Slow (45)" and "Very Fast (120)" -- 60 units = 1
tile/s. Applied as 0.75 and 2.0. Left as published they would have made the Archer Queen's cloak
a 45-tile-per-second sprint.

### ⚠ P6. The DUP bucket's probe order would have kept a stale value (zap_evo).

`zap_evo.crown_tower_damage`: p1 58 / p2 58 / p3 48, and the bucket's rule ("merge's pick", p1
first) lands on 58 -- the stale 30% vardefine -- while the row's own note says outright that
"THE OWNER PIN LANDED ON THE PARENT AND MISSED THE EVOLUTION" and zap's 48 is correct off the
IDENTICAL damage 192. Caught by `stat_sweep --all`, which is the first instrument in this project
that could have caught it. Applied as 48 via an OVERRIDE.

### ⚠ P7. Only TWO of the three predicted --force-field refusals were load-bearing.

I4 predicted refusals on mortar.dps, mortar_evo.dps and rage.attacks. After the LAG bucket
created a pin for mortar.dps, its refusal is absorbed (pins outrank verified), so the dry-run
refuses on two. All three were still forced individually and cited; forcing mortar.dps only
disables its own pin for that run and the importer's recompute lands on the same 57.

Separately, the guard first refused TWELVE, not two: ten more `verified: true` rows whose `dps`
moves only because an adjudicated damage or hit_speed landed above (barbarian_barrel 147->177,
furnace/furnace_evo 99->105, rune_giant 80->103, ...). Those were DECLARED as pins rather than
force-released -- blanket-forcing ten fields to land two would have discarded exactly the
protection I4 built.

### R2 rows applied WITH A CAVEAT (do not "correct" these back)

* `earthquake` crown 49 -- OWNER OVERRIDE, knowingly inconsistent. 49 is 58% of the SUPERSEDED
  damage 84; against the ruled 81 the same 58% gives 47, and 49/81 = 60.5%. The wiki says 53. All
  three were put to the owner. Written into the cards.yaml comment, the pin, and the crown audit's
  OVERRIDES so three separate tools state it.
* `tesla` / `tesla_evo` hitpoints 1182 -- the live wiki publishes 1152 on BOTH pages and the
  1/6/2026 "+3%" reconstruction gives 1187. The RULE (evo hp == base hp) is wiki-confirmed; the
  VALUE is the owner's. Both rows pinned so a re-import cannot pull them to 1152.
* `barbarian_hut` spawns.interval 15.0 -- the curated 13.5 is refuted by every path, but the two
  LIVE surfaces (table + prose) say 15 while the history RECONSTRUCTION says 14, and no dated entry
  documents 14 -> 15. 15 also makes the row self-consistent (it already carried spawn_interval_s
  15.0). **OWNER: 14 is the alternative and nothing here settles it.**
* `valkyrie_evo` attack_nado_crown_damage 37 -- published, but undated. If the 4/8/2026 -50% also
  halved the crown chip it is ~18. No entry says so. **OWNER.**
* `goblinstein` lightning_link_damage 107 -- published and provably pre-4/8/2026. That update
  nerfs "Ability DPS" -12%, which could land on damage (-> 94) or on hit speed (0.5 -> 0.568 s).
  Applied the published number. **OWNER.**
* `little_prince` spawn_unit_stats.damage 232 -- PLAN.md's I7 line still quotes the Guardienne as
  "1600/217/1.2s". 217 is the vardefine, byte-identical at revid 436758 and live, so it predates
  the 4/8/2026 "+7% Guardian Melee Damage": 217 x 1.07 -> 232. **I7 must not revert it to 217.**
* `x_bow` damage 43 -> 58, hit_speed 0.3 -> 0.4, dps 143 -> 145. Our own deck's WIN CONDITION.
  Classic vardefine lag: the 4/8/2026 entry states 0.4 "from 0.3 seconds", which is exactly what
  both surfaces still publish, proving neither absorbed it. Nearly DPS-neutral, but per-shot
  damage and cadence matter separately for a card that wins by chip rate.
* `witch_evo` spawn_death_heal 76 -> 220 lands WITH heal_source_cap 4 and overheal_frac 1.73. The
  cap partly offsets the heal; applying the 220 alone would have been a large sustain buff.

### RECORDED, NOT APPLIED

* **`electro_dragon_evo.hits_per_attack: 12` is a MODEL error, and the largest overstatement of
  enemy strength the sweep found.** The engine reads it as 12 hits at the full 267 = 3204 damage
  per swing. The wiki's shape is 3 hits at full damage WITH the 0.5 s stun, then unlimited SLOWER
  bounces at a reduced ~89 with NO stun (267 x 0.67 x 0.50; the published 64 is that chain applied
  to the pre-2026-08-09 base of 192). Needs `late_chain_damage` + an unlimited-bounce flag in the
  engine, so it is written into the cards.yaml comment and left for I7/I9.
* `electro_spirit.chain_tiles` -- its own page publishes 4 tiles, independently of the Electro
  Dragon's three. decisions.md #6 rules the ED FAMILY, so it stays on the 3.0 fallback. **OWNER:
  one word to move it, and the evidence is the same evidence.**
* `little_prince.royal_rescue_pushback_tiles: 2.5` -- resolves the little_prince half of C8 (the
  history chain 3.5 -> 2.5 -> 2 -> 2.5 is complete and monotone; the prose is stale). GLOBAL bucket
  was not in the approved apply set and the field is I7's Royal Rescue work. Ready to apply.
* **decisions.md #7 (adopt the wiki's floor() for derived DPS) was applied to the TEN adjudicated
  ROUNDING rows only, not as a global convention.** MEASURED: flipping the importer's `round()` to
  `floor()` moves **47 of 122 rows** that carry a dps, 38 of them never adjudicated -- and it
  CONTRADICTS two approved `update` rows (electro_giant.dps 91 vs floor 90, spear_goblins.dps 51
  vs floor 50). **OWNER: is #7 a convention for the whole KB, or a ruling on those ten rows?**
* The engine's DERIVE-DON'T-STORE defect, which is why the above matters at all: `build_spec`
  rebuilds per-hit damage as `hit_dmg = dps * hit_speed` even when the KB carries the exact
  integer `damage`. A floored dps therefore makes per-hit damage LOW by up to one hit_speed
  (measured worst case ~0.9%, inside stat_sweep's 2% band, but wrong in a way nothing else is).
* **23 deferred rows**, each with its reason in `ledger/i5_plan.json`: the seven champion
  `ability_cast_time_s` rows (C7 -- prose says 1 s, the tables say 0.933/0.944/0.766, and the
  engine needs ONE convention; mighty_miner's `ability_delay_s: 1.0` is the standing precedent, so
  I7 rules it), `boss_bandit.ability_delay_s` (same, and load-bearing for the ruling-7 refund
  window), `pekka_evo.kill_heal` (a 3-tier heal by victim max-hp, a model change not a number),
  `wall_breakers_evo.damage_vs_troops` (damage now splits by target class),
  `skeleton_king.ability_spawn_count` (a 6-16 RANGE driven by the soul bank, ruling 8 / I7),
  per-body `first_hit_speed_s` for goblinstein and skeleton_king, and
  `minion_horde_evo.invisible_hit_speed_mult` (0.67, direction undecidable from the stub).
* **30 rows the sweep itself declined** and this stage did not overrule: bats.hit_speed ("I am NOT
  updating on a mis-worded entry"), firecracker.projectile_speed ("no majority"),
  three_musketeers.hit_speed ("treat this History entry with suspicion"),
  goblin_barrel_decoy...damage ("I do NOT recommend acting on it" -- the 4/8/2026 line is a
  verbatim duplicate of the 8/7/2024 one and the owner user-verified 89 in game ten days after
  it), giant_skeleton.death_crown_mult ("Report only"), tombstone.spawns.interval (curation
  confirmed), fire_spirit.hitpoints (already the right surface), the five null-on-every-path rows,
  and the 14 princess_evo / minion_horde_evo stub-page stats.

### `stat_sweep --all`: 21 UNMAPPED, and that is the honest answer

15 of them are keys the importer never emits, so by construction they are not cards -- spawned
bodies (ghost_souldier, goblin_brawler, decoy_goblin, golemite, elixir_golemite, elixir_blob,
bush_goblin, royal_recruit, skarmy_general, lumberjack_ghost, phoenix_egg, mother_witch_hog,
goblin_barrel_decoy, lava_pups) and one second form (spirit_empress_air). The remaining 6 are real
pages that publish no `#vardefine` at all: Clone and Mirror (no stats to publish), the Elite
Barbarians / Minion Horde / Princess Evolution STUBS, and Ronin (a newer page whose numbers live
only in the attribute table, which is where cards-import gets them). The set is DERIVED from the
imported key set, so a card released tomorrow leaves it by itself.

Two page-shape bugs the full sweep exposed and the tool now handles: `tombstone_hero` reported
+5115% hp because a `_hero` page inherits its parent's shape (hp_11 is the Skeleton it spawns), and
`mini_pekka_hero` 404'd because the merged row's display drops the trailing dot the page keeps.

### I6 note: elite_barbarians_evo is no longer null

PLAN.md I6 expected it to still be an announcement-authored row. The I4 uncategorized-subpage
probe found the live stub and the import took what exists: hitpoints 1341, damage 384,
hit_speed 1.4 (the curated javelin block is untouched). Real null-hitpoint gaps across the whole
KB are now **0** -- the only two rows with a null hitpoints CELL are princess_evo and
minion_horde_evo, and build_spec resolves both through the base card (261 and 230), which is the
protocol those rows were left under.
