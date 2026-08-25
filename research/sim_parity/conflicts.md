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
