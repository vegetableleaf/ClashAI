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

### C2. Mighty Miner bomb RADIUS — still unsourced after a full page sweep.
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
