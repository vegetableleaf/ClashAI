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

## I7 — the Electro Dragon chain, 2026-08-26

### ⚠ ED-1. RULING 15 RESOLVES the 267-vs-192 question — and the "192/3 = 64" arithmetic that reached it is a coincidence, not the mechanism.

The brief that opened I7 flagged ruling 12's `64` as an unexplained discrepancy: "the KB has
damage=267 (267/3 = 89, not 64; 64 implies a base of 192)". Owner ruling 15 then settled it by
in-game confirmation — **192 @L11** — citing `192 / 3 = 64` as corroboration.

**64 is not derived. It is PUBLISHED, in its own level-table column.**
`webcache/Electro_Dragon_Evolution.wikitext` (live revid 437294):

```
{{#vardefine: dmg_11       | 267 }}
{{#vardefine: dmg_hits     | 3   }}
{{#vardefine: late_dmg_11  | 64  }}      <- column header: "Damage after 5 chains"
```

and its own History gives the derivation:
* 8/1/2025 — "decreased the Evolved Electro Dragon's damage **after the first 3 chains** by 33%"
* 2/3/2026 — "decreased it's **chain damage by 50%**" (Version_History.wikitext: "Evolved
  Electro Dragon: Chain Damage -50%")

192 × 0.67 × 0.50 = **64.3 → 64** ✓ · 267 × 0.67 × 0.50 = **89.4** ✗

So the true falloff is 0.335, and 1/3 falls out of it numerically (0.3333 vs 0.335, a 0.5% gap
that both round to 64 at L11). The owner's two statements are therefore not two independent
observations of the same fact — the second one ("64 at level 11") is the wiki's own published
`late_dmg_11`. That does not weaken ruling 15; it changes which evidence carries it.

**What actually supports 192, recorded so a later pass does not re-litigate it:**
1. `late_dmg_11 = 64` reproduces from 192 through two DATED nerfs and does not reproduce from 267.
2. `webcache/Electro_Dragon.rev436720.wikitext` publishes `dmg_11 | 192` — 192 is this page's OWN
   older value, not an unsourced reading.
3. The page's stat block has drifted far past what its History documents: `hp_11` 949 → 1383 →
   1451 (+53%) across the three archived revisions, against History entries recording only two
   +5% hitpoint buffs. `atk_speed` moved 2.1 → 2.4 → 2.3 with no History entry at all.
4. Owner in-game observation, which decisions.md puts above wiki prose.

**THE COMPETING READING, not discarded.** I5 concluded the opposite: that 267 is live and
`late_dmg_11 = 64` is the STALE field, computed off a pre-buff 192 and never updated, so the live
late-chain damage should be ~89 (conflicts.md, "RECORDED, NOT APPLIED"). Under that reading the
sim now under-models the base Electro Dragon by 28%. Ruling 15 retires it, but the fact that the
two readings differ by exactly one stale-vardefine judgement — the single most common failure mode
this project has documented — is worth an in-game re-check of the BASE card's per-hit damage.
**OWNER: one number settles it — what does a level-11 Electro Dragon's first bolt hit for?**

Applied: `electro_dragon` and `electro_dragon_evo` damage 267 → **192**, dps 116 → **83.478**,
both decks, `verified: true`, four pins in `config/import_pins.json` (via
`scripts/gen_pins.py`, the documented regeneration path), and `stat_sweep --all` reports them as
KNOWN DEVIATIONS rather than mismatches (MISMATCHES: 0, exit 0).

### ED-2. `hits_per_attack: 12` was a MODEL error and is now a budget, not twelve full hits.

MEASURED, one Evo swing into a line of 13 knights 3 tiles apart, towers disarmed:

```
                       total     shape                                   stunned
before  (267 x 12)     3204.0    12 bodies, every one at full damage     all 12
after   (ruling 12)    1151.9    3 x 192.0 full  +  9 x 63.99 reduced    first 3 only
```

Implemented as a RULE, per ruling 12: `chain_full_hits: 3` (published as `dmg_hits` on BOTH the
base and the Evolution page) and `chain_falloff_frac: 0.3333`, so the reduced number follows the
card's damage instead of freezing a constant that has already gone stale once. `hits_per_attack:
12` is kept and re-read as the TOTAL bounce budget — the page calls the chain infinite, and
ruling 11's no-repeat rule bounds it on a real board anyway.

One engine trap found while doing it: `_multi_hit` withheld the stun from late bounces correctly,
but the **cosmetic arc projectile** (damage 0, drawn for sim_view) still lands, and
`_impact` → `_land_hit` re-applies the spec's status when it does. MEASURED: all 12 bodies stunned
even after the damage split was right. Late hops now carry a status-stripped copy of the spec.

### ⚠ ED-3. The Evolution page says the EVO chain CAN repeat targets. Ruling 11 says it cannot. Not acted on.

Ruling 11 (owner): "Electro Dragon chain cannot hit the same target twice in one attack",
verified as already correct in the engine (`seen = {id(ref)}`). Pinned by
`ChainFalloffAndNoRepeatTests.test_ONE_chain_attack_can_never_hit_the_same_body_twice`.

The Evolution page contradicts it, for the EVO specifically, in two places:
* card quote (infobox): "Evolved Electro Dragon's attack will chain between targets infinitely
  **and can hit the same target more than once**";
* Strategy: "If it's within the chain range, the lightning will bounce off the Crown Tower and hit
  the troop again. In this case, the Evolved Electro Dragon would've hit the Crown Tower twice."

This reads as a genuine BASE-vs-EVO difference — the base page says the opposite of itself
("The chain lightning will merely hit three individual troops... the chain lightning will only hit
three units"), which is consistent with only the Evolution having the repeat.

NOT IMPLEMENTED. Owner rulings outrank wiki prose, and unlimited repeats would be a large
unmeasured buff on top of a card the sim has just been corrected DOWN by 64%. **OWNER: does the
Evolved Electro Dragon's chain re-hit the same body within one attack? If yes, ruling 11 is a
base-card rule and the Evolution needs its own `seen` exemption.**

## I7 — champion abilities, 2026-08-26

Eight champions, eight `ability_kind` handlers, enemy-side only (decisions.md ruling 1). Below is
every place a page forced a CHOICE, every premise in the brief that turned out to be wrong, and
every question that needs the owner in a client rather than another sweep. The choices themselves
are argued in the test docstrings (`tests/test_champion_abilities_i7.py`) and in the KB comments;
this section is the ledger.

### CHOICES MADE FROM CONTRADICTORY EVIDENCE (implemented, argued, reversible)

| # | Card | The conflict | Taken | Why |
|---|---|---|---|---|
| I7-1 | ALL | Activation delay: prose "1 second" vs table Cast Time 0.933 / 0.944 / 0.766 s (C7) | **1 s** | The standing `mighty_miner.ability_delay_s: 1.0` precedent, and the only figure stated as a RULE anywhere: `Cards.wikitext`, "The abilities adhere to the server's 1 second deployment delay". The tables disagree with the prose AND with each other on all seven pages. This closes the seven `ability_cast_time_s` rows I5 deferred to I7. |
| I7-2 | Archer Queen | Attack-speed buff stated THREE ways: prose +80% (x1.8), table Boost "+180%" (x2.8), History "to 180% (from 200%)" (x1.8) | **x1.8** | The page's own level table is the only machine-readable statement: its "Damage per second (with Cloaking Cape)" column computes `Dps(dmg_11*1.80, atk_speed)`. Two of three land there; the table's leading "+" is the outlier. |
| I7-3 | Archer Queen | Invisibility class: "untargetable by troops" vs splash/spells/Tesla/retargeting behaviour | **Royal Ghost class** (`ghost`: targeting only) | Four independent page statements: 8/4/2022 FIXED her to RECEIVE splash, "since it is a spell, the player can reliably hit the Archer Queen", the Tesla stays down, X-Bow/Mortar retarget. `_valid_foe`'s own comment already named her. |
| I7-4 | Golden Knight | "no targets in range" — does it END the ability or pause it? | **ENDS it** | Owner ruling 10, explicitly. |
| I7-5 | Golden Knight | Chain targets: air? towers? | **Ground troops + Crown Towers** | His body is Ground and Strategy stresses he "cannot attack air troops"; towers must be seekable or the page's own counter-advice ("at most 5 tiles away from the river, to prevent the Golden Knight from connecting to the Crown Tower with his dash") is meaningless. |
| I7-6 | Skeleton King | Spawn radius: ability prose 4 tiles vs History 24/10/2025 3.5 | **3.5** | The History entry is the later edit and names 4 as the OLD value. |
| I7-7 | Skeleton King | "It continues, even if the Skeleton King dies" — the summon, or soul accrual? | **The summon** | Accrual is scoped to "while the Skeleton King is on the field" two paragraphs earlier, so the other reading is incoherent; History 30/3/2022 had to FIX a case where the summon could cancel. |
| I7-8 | Skeleton King | "random positions in the circle" — disc or ring? | **Disc** (uniform by area) | The page uses both words and specifies no distribution. A ring puts every Skeleton at maximum distance, which is not what the card looks like. |
| I7-9 | Little Prince | Pushback: prose "0-2 tiles ... sweet spot" vs History 1/9/2025 "2.5 tiles (from 2)" | **2.5 flat** | Later edit, and its chain is complete and monotone (3.5 → 2.5 → 2 → 2.5). The graded version is unimplementable regardless: the "sweet spot" is never located and no falloff curve is given. |
| I7-10 | Monk | Ability prose "reflect ALL incoming projectile-based ranged attacks" vs Strategy exempting Spirits "DESPITE BEING PROJECTILES" | **The specific list** | It is dated (the Heal Spirit exemption is History 12/12/2022, i.e. a change TO the blanket rule), enumerated card by card, and the literal reading would hand the Monk four matchups the same page says he loses. |
| I7-11 | Goblinstein | Link geometry: 2 tiles from the SEGMENT, from each endpoint, or from the Monster? | **The segment (a capsule)** | The prose makes the LINK the damaging object; the Strategy line that sounds like a circle never names a centre. **QUEUED for the owner — see below.** |
| I7-12 | Goblinstein | First shock at t=0 or after one interval (8 ticks vs 9, a 12.5% swing) | **At activation, 8 ticks** | The reading in which the published 4 s duration IS the ability rather than the duration plus a free tick. |

### ⚠ PREMISES IN THE I7 BRIEF THAT WERE WRONG

1. **"little_prince `guardian` — the Guardienne is fully specified: 1600 hp / 217 dmg / ..."**
   Her damage is **232**, not 217. I5 applied 217 × 1.07 = 232 for the 4/8/2026 "Guardian Melee
   Damage +7%" (217 is byte-identical at revid 436758 and live, so it predates the buff) and left
   an explicit warning that *"I7 must not revert it to 217"*. PLAN.md's I7 line repeats the stale
   217 as well. Implemented as 232, pinned by a test.
2. **"~10 generic params"** — 16 were needed, and every one is load-bearing (`ability_kind`,
   `_dmg`, `_crown_dmg`, `_radius_tiles`, `_duration_s`, `_range_tiles`, `_tick_s`, `_max_hits`,
   `_speed_mult`, `_move_speed`, `_spawn`, `_spawn_count`, `_shield_hp`, `_heal`,
   `_dmg_reduction`, `_knock`, `_ai`). Cutting to ten would have meant per-card fields for the
   difference, which is the thing the schema exists to remove.
3. **Ruling 15's supporting arithmetic** — see the Electro Dragon section above (ED-1).

### ⚠ IN-GAME CHECKS QUEUED FOR THE OWNER (each one is a single observation)

* **Goblinstein link geometry.** Stand the Doctor and Monster far apart and put a troop at the
  MIDPOINT, ~3 tiles from each and well inside the tether. Does it take damage? Yes = the capsule
  (what is implemented); no = two circles, and the handler needs to change.
* **Archer Queen shot count.** Strategy claims "exactly 7 shots for the full duration". Neither
  candidate multiplier reproduces it: x1.8 gives ~5.25 shots over 3.5 s and x2.8 gives ~8.2; 7
  would need ~2.4x, which nothing on the page states. Count them once in a training battle.
* **Golden Knight dash travel speed.** UNPUBLISHED. 8.33 tiles/s (the Bandit / Boss Bandit Dash
  Speed 500 analog) is in the KB marked untested. Time one full 10-dash chain and the constant
  follows.
* **Evolved Electro Dragon repeat targets** (ED-3 above) and **the base Electro Dragon's per-hit
  damage** (ED-1 above).
* **Skeleton King sub-troop souls.** "cards that make sub-troops ... do not count as a soul to it,
  but only the final forms of the troop, WITH GOBLIN GIANT AS AN EXCEPTION." The sentence supports
  both directions of the exception, so the sub-troop rule is NOT implemented at all — every troop
  death banks a soul except buildings, cloned bodies and his own Skeletons. Guessing the direction
  would move his output by up to 4 Skeletons. Kill a Golem in front of him and count the bar.

### NOT IMPLEMENTED, DELIBERATELY (recorded so a later pass does not read the gap as an oversight)

* **Monk SPELL reflection** ("Spells are always reflected to the closest opposing Crown Tower", at
  25% for splash/non-seeking, with the Barbarian Barrel exception at FULL crown damage, and The
  Log / Barbarian Barrel converting to fight for the reflector). PROJECTILE reflection is
  implemented in full; spells are not, and the reason is that the page never enumerates which
  spells count as "projectile spells" — it only carves out "non-projectile spells" without saying
  which those are. Zap and Lightning are instant electric by the same Strategy paragraph that
  exempts Tesla; Earthquake and Poison are zones; Arrows is named as reflectable; Fireball, Rocket
  and Snowball are lobbed. That is a four-way judgement call on an unstated boundary, and getting
  it wrong redirects real damage onto a Crown Tower. **OWNER: name the spells that bounce.**
* **The graded 0-to-2-tile Royal Rescue pushback** (I7-9): no sweet spot, no curve.
* **Skeleton King sub-troop soul exclusions** (above).
* **Golden Knight's facing arc.** Strategy says "he will not target any units behind him ... only
  chains to the troops that the Golden Knight can see", while History 5/5/2025 "allowed Dashing
  Dash to move Golden Knight backwards". The two read as contradictory, no arc is given in
  degrees, and the chain is implemented as omnidirectional within 5.5 tiles.

## I8 — heroes, enemy-side, 2026-08-27

Sixteen live heroes, twelve `ability_kind` handlers, the three-slot loadout and the tower-troop
wiring. Below is every place a page forced a CHOICE, every premise in the I8 brief that turned out
to be wrong, every measured bug the stage surfaced, and every question that needs the owner in a
client rather than another sweep. The choices themselves are argued in the KB comment beside each
number and in the test docstrings (`tests/test_hero_abilities_i8.py`); this section is the ledger.

THREE RULES settled most of it, each with an I7 precedent, and they are stated once so the table
below can just name them:
  (a) a dated HISTORY entry that names the OLD value supersedes an un-updated table or prose (I7-6);
  (b) an attributes table / level-table column beats PROSE, because it is the page's only
      machine-readable statement (I7-2);
  (c) the activation delay is 1 s unless the page publishes an agreed one (I7-1).

### CHOICES MADE FROM CONTRADICTORY EVIDENCE (implemented, argued, reversible)

| # | Card | The conflict | Taken | Why |
|---|---|---|---|---|
| I8-1 | ALL | Activation delay: every page either says "After a 1-second delay" or prints a Cast Time (0.933) or says nothing at all | **1 s** | Rule (c). The ONE exception is the Hero Bowler, whose table AND prose agree on 2.5 s — a published, self-consistent value, so rule (c) never applies to him. It also makes his ruling-7 refund window 2.5x everyone else's. |
| I8-2 | Knight | Taunt radius: prose AND table say 7.5; History 2/3/2026 says "decreased ... to 6.5 tiles (from 7.5 tiles)" | **6.5** | Rule (a): the History entry is later and names 7.5 as the OLD value, so both un-updated statements are the stale ones. |
| I8-3 | Knight | Shield: vardefine `Shild_11` 512, then two later nerfs (-6% 12/1/2026, -33% 6/7/2026) | **512** | Neither nerf publishes a new absolute, so there is nothing to substitute. Computing 512 x 0.94 x 0.67 = 322 would be inventing a number from two rounded percentages. See I8-19 for the ONE case where an equivalent computation WAS applied, and why. |
| I8-4 | Knight | Does the taunt grab units ENTERING the radius during the 5 s? And what does "still target him afterwards" mean? | **Snapshot at cast; forced for 5 s; then permanent until he dies** | The prose reads as one event ("taunting every enemy troop and building in a ... range"), and a re-sweep would need an invented cadence. The persistence is the page's own final clause, "until he is defeated" — and it has to be a REFERENCE rather than a re-aim: MEASURED, releasing it at 5 s and merely pointing the Hog at him lasted ONE TICK, because a building-targeter drops any lock on a body that is not a building. |
| I8-5 | Balloon | Soar range: table 6.5, prose "within 6 tiles" | **6.5** | Rule (b). |
| I8-6 | Balloon | Landing damage radius | **Single-target** | No radius is published anywhere on the page. The Skeletrooper lands ON the body he soars to and hits it once; a blast would need a circle nobody printed. |
| I8-7 | Wizard | Ability cost: infobox 2 + prose twice ("an additional 2 Elixir", "costs 2 Elixir") vs the on-page Tornado table 1 AND the Heroes master table 1 (5+1=6) | **1** | A GENUINE 2-vs-2 SPLIT, and the least comfortable call in the stage. Rule (b) breaks it: the two tables are machine-readable and they are on DIFFERENT pages, so they are two independent statements, where the infobox and the prose are one page's editor writing the same claim twice. **Owner: it is one button press — what does Fiery Flight cost?** |
| I8-8 | Wizard | Tornado radius: prose 3, table 4 | **4** | Rule (b). |
| I8-9 | Ice Golem | Pulse interval | **2.0 s [verify]** | PUBLISHED NOWHERE. This is the one genuinely invented cadence in I8. 2.0 is the ability's OWN published Slowdown Duration — the only cadence on the page — and it is the value that makes the slow continuous across the three pulses without stacking. The aura window follows from it (3 x 2.0) rather than being a second guess, and the pulse COUNT is enforced separately so a retuned interval can never buy a fourth blast. |
| I8-10 | Ice Golem | Slow duration: table 2 s vs History 2/3/2026 "decreased Freeze duration to 1.5sec (from 2sec)" | **2 s** | Rule (a) does NOT apply, because the History entry's subject is a FREEZE and the 3rd blast's freeze is exactly what History 4/8/2026 removed ("went from being a freeze effect to a slowdown effect"). The nerf reads as having hit an effect that no longer exists. |
| I8-11 | Ice Golem | Crown-tower damage: none published | **None dealt** | Silence read as "it does not", never as "full damage". Every hero ability that DOES hit a tower publishes a crown value; a bare fallback would have handed the Snowstorm its full 69 per pulse — which is precisely the trap I5 hit with Royal Delivery, where "discard its crown_tower_damage" gave it FULL crown damage. |
| I8-12 | Berserker | `bear_dmg_11` 167: the level table publishes it and the page NEVER SAYS WHAT IT IS (the subject page has no prose at all) | **Her per-hit damage while the ability runs** | Rule (b): the ability's attributes table publishes a Hit Speed of its own (0.2 s) and the level table publishes exactly one ability-damage column beside it. A cadence plus a damage is an attack profile. The alternative — her normal 102 at the faster cadence, with 167 meaning something else — is 510 dps against this reading's 835. **Owner: hit something for one second with Savage Survival up.** |
| I8-13 | Valkyrie | Is Ability Damage 97 PER TICK (0.25 s, 3.5 s = 14 ticks) or the total spread over the duration? | **Per tick** | "Hit Speed" means a cadence of hits everywhere else on the wiki. MEASURED so the size of the choice is visible rather than buried: **1358 area damage and 679 crown damage per activation**, for a 3-elixir ability on a body already on the board. If that is wrong the card is over-modelled by 14x. **Owner: this is the biggest single number I8 chose.** |
| I8-14 | Valkyrie | Does the spin REPLACE her normal 1.5 s swing or stack with it? | **Replaces** | A body spinning is not also swinging on its own cadence, and stacking would double-count. Not stated either way. |
| I8-15 | Bowler | Prose "a total of 3 shots" vs table 7.3 s / 1.9 s cadence, which allows 4 | **Both, and they reconcile** | 7.3 / 1.9 gives FOUR shots if the first lands at t=0 and exactly THREE (1.9 / 3.8 / 5.7) if the stance pays one of its own hit-speeds before its first shot. So no shot cap is curated anywhere: the published numbers produce the published count. MEASURED at 6.6 / 8.5 / 10.4 with his 2.5 s cast in front. |
| I8-16 | Barbarian Barrel | `rerolldmg_11` 116: the VARIABLE is named for reroll damage, the level-table column it feeds is headed "Crown Tower Damage" | **Crown tower damage** | Rule (b): the rendered column header is what the page actually says. 116 is exactly half of the barrel's 232 under either reading, so the two differ only in WHERE it lands. |
| I8-17 | Barbarian Barrel | "healling the barbarian for 50% of the damage" / table "Damage Healed 50%" | **Lifesteal on the reroll's own damage** | The label names DAMAGE as the thing being converted; a heal of damage TAKEN would read "Health Restored". The competing reading is a real one and is not discarded. |
| I8-18 | Mega Minion | "the lowest hitpoint target" — current or max hitpoints? And is the marker tracked from deployment? | **Current hp, computed at activation** | A marker defined as "the lowest-hitpoint enemy, moving on when that one dies" always points at the lowest-hitpoint enemy alive right now, so computing it at the press is the same object. Max-hp would make the choice a static property of the card and blind to the fight. |
| I8-19 | Mini P.E.K.K.A. | Body hp: vardefine `hp_base` 1433 vs History 12/1/2026 "decreased the it's Hitpoints by 3%" | **1390** | The ONE percentage in I8 that IS applied, and only because an INDEPENDENT absolute corroborates it: I5 already took the base card 1433 -> 1390 with a dated stale-page proof (time machine oldid 433647, 2025-12-25, still carrying the hardcoded L11 row "\\|11\\|\\|1,433\\|\\|755\\|" from before the change), and 1433 x 0.97 = 1390.01 reproduces it exactly. Same body, same staleness. Contrast I8-3 and I8-20, where no such absolute exists and nothing is computed. |
| I8-20 | Giant | Body hp: vardefine 3968 (= base) vs History 2/2/2026 "reduced hero giants hitpoints by 3%" | **3968 kept** | Identical wording to I8-19 and the OPPOSITE outcome, deliberately: the base Giant carries no post-nerf absolute, so there is nothing to corroborate 3849 and it would be a bare computation. Flagged, not applied. |
| I8-21 | Giant | "highest HP enemy troop"; the untargetable flight window | **Current hp; instant displacement; 2 s of AIR** | The flight is instant, which is the engine's standing convention for a carried displacement (Evo Snowball's Snow Bowling folds its untargetable window into the sweep the same way). The 2 s is the table's own Unit Stun Duration, which is the only duration the ability publishes — the page's own open question is whether that number IS the flight time. |
| I8-22 | Dark Prince | Body hit speed: attributes table 1.4 (= the base card) vs the page's own vardefine `atk_speed` 1.3 | **1.4** | Rule (b), and the spec file's own conclusion is "body_stat_deltas: none stated". An unstated hero-only 7% attack-speed buff is the less likely reading of a page that contradicts itself. |
| I8-23 | Magic Archer | Three arrows: no spread pattern, no pierce statement | **One attack carrying 3 x 48 down his existing piercing line** | The page publishes a count and a per-arrow damage and nothing about geometry. Total 144 against his normal 135, which is what "3 arrows ... with less damage" describes. |
| I8-24 | Magic Archer | Body damage: hero page `dmg_11` 135 vs base card 125 | **135 kept** | decisions.md ruling 2: stat conflicts are FLAGGED, never auto-overturned. Nothing reconciles: I5 took the base 133 -> 125 for the SAME 4/8/2026 -6% the hero page records, and 135 x 0.94 = 127, not 125. The hero page's number is left standing and the discrepancy is here. |
| I8-25 | Tombstone | Is the Tombstone consumed when the Queen rises? | **Not consumed** | The page never says it is, and it has a 30 s lifetime of its own that keeps running. |
| I8-26 | Musketeer | Turret deploy time: table 1 s vs History 12/1/2026 "increased turret deploy time to 2 seconds (from 1 second)" | **2 s** | Rule (a); no revert is recorded. |
| I8-27 | Goblins | The ability is pressed when every body is DEAD | **Engine state (`SimEngine._banner`), not a Unit** | The banner cannot be targeted, cannot die, and has to keep the ability pressable with no body on the board — so `champion_ability` gains one documented bodyless branch, and the banner is CONSUMED by the press, which is what enforces the single use with nothing to count on. |

### ⚠ THE ONE STRUCTURAL CONFLICT THE SLOT MODEL DOES NOT MODEL

The owner's slot ruling (Evolution + Hero + Wild) is implemented exactly as given. The Heroes page
says something the ruling does not mention, and it is recorded here rather than acted on:

> "Only two Heroes can be in a deck at a time, and only in the Hero and Wild slots. **Those slots
> are also shared with Champion cards**, which means that the player can have 1 Hero and 1 Champion
> at the same time." — Heroes, revid 437509

So a CHAMPION occupies a hero-family slot. In the sim a champion is an ordinary deck card that
carries its own `ability_kind`, so a deck holding e.g. `archer_queen` AND `knight` currently fields
BOTH the Archer Queen's ability and a Hero Knight — three ability-bearing slots where the page
allows two. MEASURED over the shipped pool: **137 of 1000 decks (15.3% of deck weight)** hold a
champion card AND at least one hero candidate, so it is not an edge case (meta_008 golden_knight +
bowler, meta_017 mighty_miner + barbarian_barrel, meta_018 little_prince + berserker, ...). Not
acted on because the owner's ruling is explicit and final, and because capping it would silently
delete either the champion's ability or the hero from those 137 decks.
**OWNER: should a deck holding a Champion card lose its Hero slot?**

### ⚠ PREMISES IN THE I8 BRIEF THAT WERE WRONG

1. **"dash_chain x3, zone x2, movement_flight x2, taunt_shield x2"** — that family census counted
   the spec files' `proposed_ability_kind` fields, which were first guesses at extraction time and
   are wrong in three places. NO hero uses `dash_chain`: the Hero Barbarian Barrel's Rowdy Reroll
   is a rolling-spell corridor and the Hero Mega Minion's Wounding Warp is an infinite-range
   teleport, and both spec files say so in their own rationale comments ("closest existing bucket
   ... flag for owner"). `zone` and `movement_flight` were counted x2 by including I7's Goblinstein
   and Boss Bandit.
2. **"movement_flight (fire tornadoes — reuse the existing `_Vortex`/tornado machinery)"** — the
   NAME was already taken: `movement_flight` is the Boss Bandit's Getaway Grenade, a teleport, and
   the registry dispatches on the string. The Hero Wizard's is a separate kind (`flight_nado`). The
   INSTRUCTION was right and is exactly what happened: his tornado is the Evo Valkyrie's vortex
   behind an ability gate, which is what his own page asks for by naming her.
3. **"ordered by how often each hero appears as a candidate in the meta pool: summon (…), dash_chain,
   buff_self, …"** — MEASURED, the order is different and `summon` is third:
   `buff_self` 38.6% > reroll+warp 29.5% > summon 28.4% > taunt+decoy 17.1% > throw 9.1% >
   flight 8.1% > zone_pulse 6.2% > levelup 4.6% (share of deck weight holding the candidate).
4. **"I4's `/Hero` scrape landed 16 `<base>_hero` BODY rows"** — it did, and three of them carry
   the WRONG TABLE. See below.

### ⚠ MEASURED BUGS THIS STAGE SURFACED (all fixed, all with a before/after)

* **I4 import, musketeer_hero**: hitpoints 1536 / damage 140 / hit speed 0.5 are the TURRET's
  vardefines (`tur_hp_11` / `tur_dmg_11` / `tur_atk_speed`) — the scrape took the page's LAST
  attributes table. A 1536 hp, 280 dps Musketeer is more than twice the card. Corrected to
  721 / 217 / 1.0.
* **I4 import, tombstone_hero**: hitpoints 4224 / damage 422 are the TOMB QUEEN's. The building's
  own vardefine is `tomb_hp_11` 529 and a Tombstone has no attack. Corrected to 529 / 0.
* **I4 import, barbarian_barrel_hero**: `damage` 192 is the spawned Barbarian's melee. On a SPELL
  row `damage:` is the roll's area damage (the base card carries 230 there), so the hero barrel
  rolled for LESS than the base card. Corrected to 232 (`spawn_11`) and pinned, which also took
  stat_sweep from MISMATCHES 1 to 0.
* **`_resolve_roll` never dropped a rolling spell's `spawn_spec`**, so the BASE Barbarian Barrel
  leaves NO BARBARIAN in this sim at all — MEASURED as 0 bodies from a full deploy. See the
  deliberate non-implementation below.
* **`_late_spawns` ignored `ghost_life_s`** where `_spawn_from` honoured it, which would have left
  the Hero Magic Archer's 7-second decoy standing for the whole match.
* **A stance that extends REACH is inert without SIGHT and PROJECTILE flight**: the Hero Bowler at
  his published 11.5 tiles fired ZERO shots at a tower 10 tiles away, because `_acquire` only
  notices bodies inside `spec.sight` (5.5 for him) and, once it did, his boulder expired in mid-air
  at the body's published 7-tile Projectile Range.
* **The Hero Giant's 2 s stun and 2 s of flight ran in SERIES** — 4 s airborne from a published 2 —
  because the airborne timer sat below the stun early-out in `_tick_units`.
* **The hero slot went unfilled for 194 of 4982 decks (3.9%)** on the first pass, because the
  Evolution slot took the deck's only hero-capable card. The Evolution now moves when that
  collision is what blocks the hero; the residue is 8 in 4988 (0.16%), decks whose ONE card is the
  sole candidate for both slots and where the two "always" rulings cannot both hold.
* **evo_audit's own sampling was biased**: re-seeding the RNG per deck made every deck in a pass
  draw from the same position in the same stream, and the wild slot's three-way split read
  43.9 / 30.0 / 26.1. Sharing one stream across the sweep lands it on 34.2 / 33.2 / 32.5.

### ⚠ IN-GAME CHECKS QUEUED FOR THE OWNER (each one is a single observation)

Ordered by how much the answer would move, biggest first.

1. **Hero Valkyrie's spin damage.** Is Ability Damage 97 per 0.25 s tick, or the total for the
   3.5 s? The sim now deals 1358 area / 679 crown per activation (I8-13). Spin her into a Crown
   Tower once and read the health bar.
2. **Hero Berserker's "Bear Damage" 167.** Is that her per-hit damage during Savage Survival, or
   does she keep her 102? 835 dps vs 510 (I8-12).
3. **Hero Wizard's ability cost: 1 or 2?** Two tables against one page's infobox-plus-prose (I8-7).
4. **Hero Ice Golem's blizzard pulse interval.** Time the three blasts (I8-9) — the only invented
   cadence in the stage.
5. **Hero Knight's shield.** 512, or ~322 after the two undated-absolute nerfs (I8-3)? And is the
   taunt radius 6.5 or 7.5 (I8-2)?
6. **Hero Giant's hitpoints.** 3968 or 3849 (I8-20)? One number settles it, and the answer also
   tells us whether the Mini P.E.K.K.A. precedent (I8-19) generalises.
7. **Hero Magic Archer's damage.** 135 or 125 (I8-24)?
8. **Tomb Queen's combat profile.** Hit speed, movement speed, attack range, lifetime — the page
   publishes NONE of them, so she currently fights on the engine's bare defaults. Everything else
   about her is real.
9. **Hero Barbarian Barrel**: is `rerolldmg_11` 116 the reroll's damage or its crown damage
   (I8-16), and is "Damage Healed 50%" lifesteal or a heal of damage taken (I8-17)?
10. **Trusty Turret's spawn-damage radius** and **the Rhino's** (the table literally prints
    "unknown") — both currently fall back to the engine's splash default.
11. **Does a deck holding a Champion CARD still get a Hero slot?** (the structural conflict above).

### NOT IMPLEMENTED, DELIBERATELY (recorded so a later pass does not read a gap as an oversight)

* **The BASE Barbarian Barrel's Barbarian.** `_resolve_roll` now drops a rolling spell's
  `spawn_spec`, and `spawns_troop` is curated on the HERO row only. Giving the base card its
  Barbarian is a real fidelity fix and a pool-wide change to the 198 decks that hold it, with no
  measurement behind it yet — so it belongs to its own commit under the owner's one-change rule,
  not to this one.
* **The Hero Valkyrie's move-speed boost.** The Heroes blurb claims one; her ability table prints
  Speed "Medium (60)", identical to her body. Rule (b): the table is the machine-readable
  statement, so no boost.
* **The Hero Valkyrie's "Dash Distance 5.5".** A lone table cell that no prose on either page
  mentions at all. There is nothing to implement — no trigger, no direction, no target.
* **"Plants his feet" (Hero Bowler).** A card QUOTE, not a rule, and the page's own open question
  is whether he is rooted during the 7.3 s. He keeps moving. His mortar shot's splash radius and
  any Mortar-style minimum range are likewise unpublished.
* **The Knight's "Taunt Trigger Window" (0.1 s, History 6/4/2026, "from 0.7s").** The term is
  defined NOWHERE on the page.
* **The Rhino's "first charge distance 2.5 tiles" (History 1/6/2026, "from 0 tiles").** A different
  quantity from the Charge Range 3 the table prints — the run-up he starts with — and the engine
  has no first-charge concept to hang it on.
* **Whether the Hero Magic Archer's decoy attacks.** The page gives it a hitpoint value and a
  duration and nothing else: no damage, no hit speed, no range. It is inert.
* **A hero body's `range_tiles` delta.** `build_spec` takes `reach` from the BASE card for every
  variant (this is pre-existing, and true of evolutions too), so a hero page's own Range is not
  read. It matters in exactly one place today: `ice_golem_hero` prints "Melee: Medium (1.2)" where
  the base row says 0.75, and the spec file itself calls that at least as likely a snapshot error
  as a real delta. Left at the base value, which is the conservative outcome.
* **The tower-troop FALLBACK weights.** `sim.opponent_tower_weights` (6/2/2/1) gives the Princess
  Tower 54.5% where the pool MEASURES 90.5% (tower_princess 6455 / cannoneer 288 / dagger_duchess
  228 / royal_chef 160). Wiring `support:` lifts the fielded share to 83.7%; the rest is the 765
  of 1000 decks whose battlelog predates the R4 slot sweep and names none. FLAGGED rather than
  changed: those weights are also the frozen eval benchmark's, so retuning them makes every run
  incomparable with every previous one. **OWNER: re-weight to the measurement, and re-baseline?**
* **Detector RETRAINING for the 16 hero classes + 16 hero abilities.** `detect_classes.yaml`
  already lists all 32 (I4), so the taxonomy is complete and nothing here needs a change. Training
  a detector that can SEE them is explicitly out of Phase I scope (PLAN.md, "Deferred").

## I9 — cross-cutting gaps, 2026-08-27

Friendly-target spells, drill evolution cycling, the sim-view debugger, the perception DRIFT
entry, and the I8 carry-overs. Below is every choice forced by contradictory or ABSENT evidence,
every premise in the I9 brief that turned out to be wrong, every bug the stage measured, and
every question that needs the owner in a client. Choices are argued in the test docstrings
(`tests/test_friendly_spells_i9.py`) and in the KB comments; this section is the ledger.

### ⚠ THE GAP ITSELF, measured

`SimEngine._resolve_spell` had FIVE branches and every one of them iterated `e.team != s.team`.
There was no own-team path at all, so:

| Card | Before | After |
|---|---|---|
| rage | a bare 179-damage blast; the buff the card is played FOR did not exist | +30% move and attack speed in a 3-tile zone for 4.5 s. MEASURED: a Knight covers **2.52 tiles in 3 s unraged, 3.18 raged (+26.0%)** — under 30% because the 0.5 s deploy timer eats the first sixth of the window, which is the card |
| clone | a 3-elixir NO-OP | MEASURED: 4 skeletons in radius -> **4 bodies become 8**, every clone at 1 hp and `spec.elixir == 0` |
| heal_spirit | a kamikaze troop whose heal was unmodelled | MEASURED: an ally at 100 hp ends the field at **501.00 hp (+401.00 = 4 x 100.25)** |

### CHOICES MADE FROM CONTRADICTORY OR ABSENT EVIDENCE (implemented, argued, reversible)

| # | Card | The conflict | Taken | Why |
|---|---|---|---|---|
| I9-1 | Rage | Target column "Friendly Troops & Buildings" vs the lead "It is an area-damage, air-targeting spell with a medium radius and low damage" | **BOTH, and they are not in conflict** | The Target column names who the spell BUFFS and `attacks` names what it HURTS — two different questions, and reading the first as the second is exactly the import bug I5 had to undo (`attacks: ['buildings']`). So `spell_targets: friendly` runs the own-team pass and the card still blasts for its published 179 / 45. The 12/12/2022 Clashmas Update "made the spell deal area damage" outright. |
| I9-2 | Rage | Should the buff be a SECOND system beside the Lumberjack's `drops_rage`? | **The same `rage_zones` list** | The page's own lead: the bottle "is also the same as that spawned by the Lumberjack and the Santa Hog Rider". Two models of one mechanic is how `evo_cycles()` and `CardDB.deck()` drifted (parity_check's own examples). One consequence worth naming: `_rage_mult` was already written to buff move AND attack speed for troops and building bodies alike, which is verbatim what the Rage card claims, so the spell needed no new effect code at all. |
| I9-3 | Rage | The FALLOFF — implemented, and it moves the Lumberjack too | **1 s, engine-wide** | Published twice: "added a falloff effect to Rage, causing troops to lose the bonus if they are out of its effect for 2 seconds" (29/2/2016) and "decreased the Rage's duration after leaving the radius to 1 second (from 2 seconds)" (4/3/2025). It is a property of the RAGE EFFECT, not of the card that laid it, so `_RAGE_FALLOFF_S` is one constant and the Lumberjack's bottle inherits it. Without it a 3-tile bubble buffs a marching body only on the ticks it happens to be standing inside, which for the card's whole purpose (a raged push) is a fraction of the spell. |
| I9-4 | Clone | Does the enemy blast run? | **No — it RETURNS** | Clone's attributes table has no damage column at all. Falling through would call `_damage_tower(tw, 0.0)` on every enemy tower in radius, and a zero-damage hit on the King still ACTIVATES him (see the measured bug below). The rule implemented is general: a friendly-target spell that publishes no damage stops at the friendly pass. |
| I9-5 | Clone | Where the elixir goes | **`elixir = 0` on the clone's SPEC** | This is the "cloned units have no elixir value" semantics the brief flagged as messy, and the mess is real: the reward layer prices bodies at `spec.elixir` in at least eight places (trade potential, spell value, the bow overcommit ledger, the wincon bank). Zeroing it on the spec fixes every call site at once and cannot be forgotten by a ninth. `spec.key` is untouched, so identity, counters and doctrine still see the card. |
| I9-6 | Clone | 1 hp on the UNIT or on the SPEC? | **The spec (`hp = 1`)** | The hp BAR then reads full on a 1-hp body, which is what the game shows, and the page's own rule about hp-threshold transforms comes along for free: "any troop that activates a special mode when they reach a certain hitpoint threshold will not be able to utilize these special modes" is automatic when 50% of 1 hp is unreachable while alive. |
| I9-7 | Clone | Placement | **One body-length BEHIND, published direction only** | "spawns fragile duplicates of all troops within its area of effect BEHIND the originals". The distance is not published; one collision diameter is the smallest choice that does not overlap the original. |
| I9-8 | Heal Spirit | WHERE the field lands — on the spirit or on its victim? | **On the victim** | Strategy, verbatim: "The Heal Spirit's healing radius will spawn around the enemy troop that it jumps on." With a 2.5-tile reach and a 2.5-tile radius those two centres differ by up to a full radius. |
| I9-9 | Heal Spirit | Does a spirit killed before it connects still heal? | **No** | The field is left by the LEAP, so it is created on the connecting kamikaze swing and not in the death path. The page describes exactly this counterplay: "it is important that the barrel itself defeats the Heal Spirit before the Barbarian spawns, otherwise it may result in the Heal Spirit jumping onto the Barbarian". |
| I9-10 | Heal Spirit | Buildings | **Not healed** | "the healing has no effect on buildings", which is also the page's reason the card "should not be used in X-Bow or Mortar decks". Crown towers are not troops either and take nothing. |

### ⚠ MIRROR — MEASURED, AND DELIBERATELY NOT IMPLEMENTED

The brief said to measure the pool first and skip it if the pool does not field it. MEASURED over
the shipped `config/meta_decks.yaml` (1000 decks, 5947 total weight, byte-identical in both decks):

    mirror   5 decks / 1000   17 weight / 5947  = 0.29% of matches
    clone    5 decks / 1000    7 weight / 5947  = 0.12% of matches
    rage    64 decks / 1000  321 weight / 5947  = 5.40%
    heal_spirit 64 decks     413 weight / 5947  = 6.94%

Mirror is skipped. It is not a board effect at all — "Mirrors your last card played for +1
Elixir", at one level higher, and "Does not appear in your starting hand" — so implementing it
means a second cost model, a +1-level spec rebuild and a starting-hand exclusion the cycle has no
concept of, to be exercised in 3 matches per 1000. The engine already carries the hook it would
need (`SimEngine.last_deploy[team]`, which records `(spec, x, y, t)` per team). `tests/
test_friendly_spells_i9.py::MirrorMeasurementTests` pins the measurement at <1% so a pool that
moves makes the decision loud instead of leaving a silent gap.

Clone at 0.12% was implemented anyway, because unlike Mirror it is a board effect that fits the
existing spell path in ~30 lines and because the brief asked for it explicitly if the numbers were
published — they are, all four of them (Clone Hitpoints, Clone Shield Hitpoints, Radius, and the
cloning time from History).

### ⚠ MEASURED BUGS THIS STAGE SURFACED

* **A zero-damage tower "hit" woke the King.** `_damage_tower` set `tw.active = True` on ANY
  call, including calls carrying 0 damage, and five spells reach it with none: `goblin_barrel`,
  `goblin_barrel_evo`, `goblin_barrel_decoy`, `royal_delivery` and `mirror` all publish no Crown
  Tower damage, because on those cards the BODIES do the work. MEASURED, casting each directly on
  the enemy King Tower, time until he activates — **goblin_barrel 0.0 s at 0 chip -> 1.2 s at
  372.9; goblin_barrel_evo 0.0 s -> 1.2 s; royal_delivery 0.0 s at 0 chip -> 1.2 s at 132.6;
  mirror 0.0 s -> never.** Royal Delivery is the sharpest case: decisions.md #11 ruled it "cannot
  hit crown towers" and I5 discarded its `crown_tower_damage` for exactly that reason, which
  handed it a free king activation instead. Graveyard and Void are NOT affected (Graveyard never
  reaches the call; Void's crown figure comes from its `zone_tiers`, so it is real damage).
  Found while deciding whether Clone should fall through to the enemy pass — it must not, and
  the general rule is the fix.

### ⚠ PREMISES IN THE I9 BRIEF THAT WERE WRONG

1. **"`drill_env.py` evolution cycling. Drills currently have NO evo cycling at all —
   `evo_charge`/`slot_cycles` do not exist there, so evolutions are ALWAYS ON in drills while
   matches cycle them properly."** Both halves are wrong, and the second is backwards.
   `DrillEnv` EXTENDS `SimMatchEnv`, so `evo_charge`, `slot_cycles`, `slot_evo_id`,
   `_slot_card_id` and `_play_slot` are all inherited and all work; `DrillEnv.reset()` calls
   `super().reset()`, which zeroes the charge exactly as a match does. A `grep` inside
   `drill_env.py` finds nothing, which is presumably where the premise came from.
   The REAL gap runs the other way: evolutions are permanently **OFF** in a restricted-hand
   drill, because `DrillEnv._play_slot` removes a played slot from the cycle (deliberately —
   a drill dealt one card could otherwise replay it forever), so the charge reaches 1 and never
   the 2 an Evolution needs. MEASURED: an evolution was presented in **0 of 26 icebow drills and
   0 of 24 hogeq drills**, against a match that first presents one after **9 plays**. Matchup
   drills (3 per deck, no declared hand) keep the full 8-slot cycle and already charge like a
   match. Implemented as `Scenario.evo_charged`, defaulting to match behaviour — with the flag on,
   10 of 26 icebow and 10 of 24 hogeq drills change.
2. **"`perception.py` hogeq TypeError ... the fix is SILENTLY INERT in that deck."** See the
   perception section below: MEASURED, it is not.

### ⚠ MORE MEASURED BUGS

* **A drill that named an `<base>_evo` key in its `hand` was silently dealt the BASE card.**
  `_restrict_hand` matches a declaration against `_slot_card_id(slot)` — the identity the slot
  CURRENTLY presents — which at charge 0 is always the base. So `hand: ('tesla_evo',)` dealt a
  plain Tesla under the evolution's name, and the drill would then fail for a reason that is not
  its own, which is the exact failure `_restrict_hand`'s docstring exists to prevent. No shipped
  drill in either deck names an `_evo` today (0 of 29 icebow, 0 of 27 hogeq), so this was latent.
  Naming one now charges its slot, whatever `evo_charged` says.
* **A compound drill's hand outlived its episode.** `_compound_hand` was assigned in
  `_place_components` and never cleared, and `_restrict_hand` reads `_compound_hand or
  scenario.hand` — so after one compound episode, every later single-scenario drill in the same
  env was dealt the compound hand instead of its own. Latent today (`sim.drill_compound_frac` is
  **0.0** in both decks) and found while adding the evolution twin beside it. Both are now cleared
  at the top of every `reset`.

### ⚠ perception.py: THE TYPEERROR DOES NOT FIRE — the DRIFT entry was the stale thing

The brief and `tools/parity_check.py`'s DRIFT list both said hogeq's `PerceptionLoop.enemy_tracks`
raises TypeError on `with_base=True`, that `train_rl`'s gate swallows it, and that the threat-gate
MEMORY fix is therefore silently inert in that deck.

MEASURED 2026-08-27, in BOTH decks, against a real `TeamTracker` holding one remembered enemy:

    TeamTracker.enemy_tracks    (self, now, with_base=False, max_age=None)
    PerceptionLoop.enemy_tracks (self, now, with_base=False, max_age=None)
    loop.enemy_tracks(now, with_base=True) -> [(0.5, 0.6, 0.0, 0.12, 'hog_rider')]   both decks

No TypeError, keyword or positional, in either deck. A `git show main:` confirms the same code on
`main`: the signature had been fixed and the COMMENT was never deleted, so the DRIFT entry has
been describing a bug that no longer exists — which is its own failure, because the DRIFT list is
what the project reads to decide what still needs fixing.

What was genuinely missing is that NOTHING PINNED IT, and the swallow that hid it is still there
and still has to be (a perception hiccup must not break training). So:

* the stale comment is replaced with a CONTRACT note in both decks, and the two files are now
  byte-identical — as is `replay_mine.py`, whose DRIFT entry was "docstring only";
* `parity_check.py`'s DRIFT list loses both entries (**20 declared-different files -> 18**);
* `train_rl.py`'s bare `except TypeError: pass` becomes `_memory_gate_inert(tracker)`, which
  prints once and counts, so the path can never again be BOTH taken and quiet;
* `tests/test_perception_with_base_i9.py` (9 cases, byte-identical) pins the signature, the
  keyword call, the positional call, the `max_age` forward and the counter. VERIFIED TO FAIL:
  deleting `with_base` from the passthrough turns it red with 2 failures and 4 errors.

### ⚠ sim_view: THE CHAIN WAS INVISIBLE BY CONSTRUCTION, not by omission

The brief said `sim_view.py` "labels units by `spec.key` but does not draw chain arcs or ability
effects". True, but the reason matters, because adding a draw call would not have been enough.

MEASURED: an Electro Dragon chaining into six Barbarians for 12 s of engine time produced **zero
frames** in which a `<base>_chain` projectile was alive — a chain hop is created and consumed
inside ONE `advance(dt)` call and never survives a frame boundary — while the damage ledger over
the same run read **192 / 960 / 1152 / 576 / 576** across the row. The mechanic worked and the
picture showed nothing, which is exactly the shape of the owner's original report.

So the debugger needed a RECORD, not a renderer: `SimEngine.arc_events` and
`SimEngine.ability_events`, in the same idiom as `splash_events` (whose own comment already says
"-- sim_view"). What is drawn now, with a pixel test behind each one:

* chain arcs, one line per hop, dim + ringless for a LATE bounce (ruling 12's reduced damage and
  no stun), **over** the bodies — under them they were 0 changed pixels, because an arc joins two
  body centres;
* ability activations (an expanding ring labelled with the `ability_kind`), casts still inside
  their activation delay (ruling 7's refund window), and the running-ability / cloak / airborne /
  taunt / souls / dash state on each body;
* LINGERING ZONES — `eng.zones` was not drawn at all, so a Poison was an 8-second area doing
  damage nothing on screen accounted for, and after I9 a Heal Spirit's field was the same in
  reverse. Heal fields are drawn in their own colour;
* RAGE ZONES while they are still ARMING. The spell publishes a 0.5 s deploy timer of its own and
  the old draw skipped the whole window, which is the same trap one layer down;
* the two pieces of BODILESS engine state — the Hero Goblins' banner and Goblinstein's antenna —
  plus the Goblinstein LINK capsule its zone tick actually damages along, and a `'` suffix on a
  cloned body.

### THE I8 CARRY-OVERS: all four landed, all four pinned, and the one open item closed

I8 reported fixing four measured engine bugs and leaving one data gap. VERIFIED here:

| Bug | Landed | Pinned by |
|---|---|---|
| `_resolve_roll` never dropped a rolling spell's `spawn_spec` | yes (`engine.py`, the `sp = s.spec.spawn_spec` block) | `test_hero_abilities_i8.py::test_rowdy_reroll_...` deploys the hero barrel and asserts exactly one `barrel_barbarian` body |
| `_late_spawns` ignored `ghost_life_s` | yes (the `n_ == 1` branch) | `test_triple_threat_blinks_back_...` asserts the Magic Archer's decoy is gone at its published 7 s |
| a reach-extending stance is inert without SIGHT and PROJECTILE flight | yes (`_ability_buff_self`) | `test_a_stance_that_extends_REACH_extends_sight_and_the_projectile_with_it` |
| the Hero Giant's 2 s stun and 2 s of flight ran in SERIES | yes (`flying_left` ticks ABOVE the stun early-out) | `test_a_thrown_body_is_AIR_while_it_flies_...`. **VERIFIED TO FAIL**: moving the decay back below the stun gate turns it red ("...and can again once it lands"), so the test really does pin the parallelism and not just the flags |

**THE OPEN ITEM IS NOW CLOSED.** The base Barbarian Barrel left no Barbarian (MEASURED: **0 bodies
from a full deploy**), which is the card's whole second half — Barbarian Barrel revid 437163 says
it twice ("then breaks open and out pops a Barbarian!", "Once the spell reaches its destination,
it spawns a single Barbarian") and its Strategy section is built on the body ("can follow up and
attack anything while alive"; "the spell can be used to separate a building-targeting troop from a
regular troop"). I8 held it back for its own measured commit because it changes **198 of 1000 pool
decks (24.95% of deck weight)** — that commit is `i9: the base barbarian barrel's barbarian`, and
the measurement is 0 -> 1 body at 670 hp.

A SEPARATE KB ROW, `base_barrel_barbarian`, and not the hero's `barrel_barbarian`: the hero page's
own vardefines are 716 / 192 against the base page's 670 / 191, so reusing the hero's row would
have handed the base card a 6.9% hitpoint buff nobody published. The base card's row was already
carrying `spawn_unit_stats` — the Barbarian's combat profile with nothing to attach it to — so the
only thing missing was the declaration. Neither deck plays the card, so this is enemy-side only,
which is the scope of the whole phase.

One I8 test had to change with it: `test_a_SPELL_hero_hands_its_button_to_the_body_it_leaves_behind`
asserted "the base card's gap is recorded, not fixed here". It now asserts the base card leaves its
OWN barbarian and that only the hero's carries the Rowdy Reroll button.

### RECORDED, NOT ACTED ON (I9)

* **Every spawned body is priced at 4 elixir.** A KB row with `elixir: null` falls through to the
  engine's default, and MEASURED that is **4** for `barrel_barbarian`, `base_barrel_barbarian`,
  `magic_archer_decoy`, `soul_skeleton` and `guardienne` alike. The reward layer prices bodies at
  `spec.elixir` in at least eight places, so a Skeleton King's Skeleton currently reads as 4 elixir
  of enemy investment. Pre-existing, pool-wide, and touching a dozen cards' reward values at once —
  so it is a measured commit of its own, not a side effect of this one. (I9's clones sidestep it by
  setting `elixir = 0` on the clone's spec explicitly.)

### NOT IMPLEMENTED, DELIBERATELY (I9 item 1)

* **The Clone's forward shove of the ORIGINAL body.** "When a troop is cloned, the original troop
  will be displaced forward slightly ... This displacement can allow Clone to be used with
  building-targeting troops to bypass certain defensive building placements, by shoving the
  original troop so that it is closer to a Crown Tower." The DIRECTION is published and the
  MAGNITUDE is not — and the magnitude is the entire tactic, because it decides whether a Balloon
  ends up inside a Crown Tower's reach. **OWNER: clone a Balloon at the bridge and see how far it
  jumps.**
* **Cloning a champion or hero body.** Clones are created and are excluded from the ability
  ("Champion cards can be cloned, but when you use its ability, only the non-cloned one will
  activate its ability"; "any heroic troop can be cloned, but only the non-cloned one will
  activate its ability") — a clone is always the NEWER body, so without the exclusion it would win
  ruling 5's newest-body selection and take the button away from the real champion. What is NOT
  modelled is Goblinstein's "Lightning Link will always target the non-cloned Monster, and if
  destroyed, it will not retarget to the cloned Monster", which needs a second anchor concept.
* **Whether a CLONED body's death banks a Skeleton King soul.** The page says his own summoned
  Skeletons "cannot be cloned as they are considered cloned troops themselves", which reads as
  cloned bodies being soul-exempt, so clones are excluded from the bank — the same sentence the
  existing soul_skeleton exclusion comes from. If the exception runs the other way this is 1 soul
  per clone, which is the same undecidable shape as the I7 sub-troop question.
