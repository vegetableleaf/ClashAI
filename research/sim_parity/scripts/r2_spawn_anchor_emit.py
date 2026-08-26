# -*- coding: utf-8 -*-
"""R2 adversarial cross-check 2: building-vs-spawned-unit contamination + the reverse-derivation
anchor sweep (decisions.md ruling 9 follow-on).

Emits research/sim_parity/ledger/r2_crosscheck_spawn_anchor.jsonl
"""
import json, pathlib
from collections import Counter

OUT = pathlib.Path(r'C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_crosscheck_spawn_anchor.jsonl')
API = "https://clashroyale.fandom.com/api.php?action=parse&page=%s&prop=wikitext%%7Crevid&format=json"


def src(page, revid, raw):
    return {"url": API % page.replace(' ', '+').replace('/', '%2F'), "revid": revid,
            "fetched": "2026-08-26", "raw": raw}


L = []


def row(**kw):
    kw.setdefault("cross_checks", {"edit_war": "pass"})
    L.append(kw)


# ==================== PART A1: the 4 buildings 95e9879 fixed -- REGRESSION CHECK ====================
for key, page, rev, bvar, bval, uvar, uval, unit in [
        ("goblin_hut",    "Goblin Hut",    437256, "hut_hp_11",   1228, "hp_11", 133, "Spear Goblin"),
        ("tombstone",     "Tombstone",     436518, "tomb_hp_11",   529, "hp_11",  81, "Skeleton"),
        ("barbarian_hut", "Barbarian Hut", 436519, "hut_hp_11",   1164, "hp_11", 670, "Barbarian"),
        ("goblin_drill",  "Goblin Drill",  437382, "drill_hp_11", 1313, "hp_11", 202, "Goblin")]:
    row(key=key, field="hitpoints", current_db=bval, p1_vardefine=bval, p2_table=None, p3_history=None,
        sources=[src(page, rev, "%s=%d (the CARD's body) vs %s=%d (the spawned %s)"
                     % (bvar, bval, uvar, uval, unit))],
        vote="2of2", verdict="match",
        notes=("NO REGRESSION of 95e9879. The building holds its own prefixed vardefine, not the spawned "
               "unit's bare hp_11. Confirmed by MEASUREMENT rather than by reading the DB: "
               "build_spec(db,'%s',11) returns hp=%.1f and dps=0.0, so the body is the building and it "
               "deals no direct damage." % (key, bval)))
    row(key=key, field="damage/hit_speed", current_db=None, p1_vardefine=None, p2_table=None, p3_history=None,
        sources=[src(page, rev, "the card's own Attributes table carries no Damage or Hit Speed column; the "
                                "dmg_11 / atk_speed on this page belong to the %s section" % unit)],
        vote="2of2", verdict="match",
        notes=("Absent in the DB, which is correct -- a spawner building has no attack. Contamination is "
               "structurally impossible on these rows while the fields stay null."))

# ==================== PART A2: goblin_cage -- 95e9879's heuristic is REFUTED on this page ============
row(key="goblin_cage", field="hitpoints", current_db=780, p1_vardefine=780, p2_table=None, p3_history=None,
    sources=[src("Goblin Cage", 436552,
                 "column header L74 [scope=col |Goblin Cage Hitpoints] is fed by {{#var:cage_hp_11}} = 780; "
                 "header L76 [scope=col |Goblin Brawler Hitpoints] is fed by {{#var:hp_11}} = 1080"),
             src("Goblin Cage/Evolution", 437374,
                 "identical header/variable binding, and intro prose L7: 'It spawns a Goblin Cage with "
                 "identical stats to the original'")],
    vote="2of2", verdict="pin",
    notes=("CURATION CONFIRMED CORRECT -- and it is the only thing holding the line. cards.yaml curates "
           "hitpoints: 780 in both decks, so the merged DB is right (measured: build_spec hp=780.0). But the "
           "IMPORTED layer, cards_stats.json in both decks, still says 1080: the Goblin Brawler's hitpoints "
           "written onto the building. 95e9879's stated rule -- 'the card's own body is the TANKIER one' -- is "
           "FALSE on this page (cage 780 < brawler 1080), and that commit's own table mislabels hp_11 1080 as "
           "'(building)'. The wiki column headers settle it. Do not drop the curation: the importer re-breaks "
           "this on every re-import until the rule becomes 'read the column header / prefixed var' rather than "
           "'pick the bigger number'."))
row(key="goblin_cage", field="hit_speed", current_db=1.1, p1_vardefine=None, p2_table=None, p3_history=None,
    sources=[src("Goblin Cage", 436552,
                 "Goblin Cage Attributes columns are Cost | Deploy Time | Lifetime | Type | Rarity, row "
                 "'|4||1 sec||20 sec||Building||Rare'. No Hit Speed, Damage, Range or Target column exists "
                 "for the cage."),
             src("Goblin Cage", 436552, "atk_speed = 1.1 is bound to the Goblin Brawler DPS column")],
    vote="2of2", verdict="escalate",
    notes=("VESTIGIAL CONTAMINATION, currently inert. The cage carries the Goblin Brawler's atk_speed 1.1 "
           "although the cage has no attack at all. Measured impact today is ZERO -- curated damage:0 / dps:0 "
           "means build_spec returns dps=0.0 and never reads hit_speed -- so this is a latent trap, not a live "
           "bug: any future path that derives a cadence from hit_speed would animate a building that does not "
           "attack. Delete the field or pin it null."))

# ==================== PART A3: goblin_cage_evo -- NEW, UNFIXED, LIVE IN THE SIM ======================
_EVO_SRC = [src("Goblin Cage/Evolution", 437374,
                "vardefines cage_hp_11=780, cage_dmg_11=337, cage_atk_speed=1, hp_11=1080, dmg_11=337, "
                "atk_speed=1.1; column headers L77-L83: Goblin Cage Hitpoints | Goblin Cage Hitpoints lost "
                "per second | Goblin Cage Damage | Goblin Cage Damage per second | Goblin Brawler Hitpoints "
                "| Goblin Brawler Damage | Goblin Brawler Damage per second")]
for fld, cur, want, note in [
        ("hitpoints", 1080, 780,
         "+38.5% hitpoints. The evo row takes {{#var:hp_11}}=1080, which the page's own column header binds "
         "to 'Goblin Brawler Hitpoints'. The cage's figure is cage_hp_11=780, identical to the base card."),
        ("hit_speed", 1.1, 1.0,
         "The evo cage DOES attack -- that is what the hook is for -- and the page gives it its own "
         "cage_atk_speed=1. The row instead carries atk_speed=1.1, the Goblin Brawler's cadence."),
        ("dps", 306, 337,
         "Follows from the wrong hit_speed: 337/1.1 = 306 is the Brawler's DPS column, where the page's "
         "'Goblin Cage Damage per second' column is 337/1 = 337.")]:
    row(key="goblin_cage_evo", field=fld, current_db=cur, p1_vardefine=want, p2_table=None, p3_history=None,
        sources=_EVO_SRC, vote="1of1", verdict="update",
        notes=("NEW CASE of exactly the defect class 95e9879 fixed, on an EVOLUTION page that commit never "
               "touched. " + note + " MEASURED LIVE: build_spec(db,'goblin_cage_evo',11) returns hp=1080.0 and "
               "dps=306.0. Unlike the base card there is NO cards.yaml curation to mask it -- the "
               "goblin_cage_evo entry curates only hook_max_tiles / hook_time_s / hook_speed_tiles -- so the "
               "sim really fields an Evo Goblin Cage wearing the Goblin Brawler's stat line. The entry's "
               "`verified: true` covers those three curated hook_* fields only; this value is IMPORTED, so "
               "ruling 2's no-overwrite protection does not attach to it. The owner may still prefer to convert "
               "it into an explicit curation rather than trust the importer here."))
row(key="goblin_cage_evo", field="damage", current_db=337, p1_vardefine=337, p2_table=None, p3_history=None,
    sources=_EVO_SRC, vote="1of1", verdict="escalate",
    notes=("RIGHT VALUE, WRONG PROVENANCE. 337 is correct for the evo cage, but the importer took it from the "
           "Goblin Brawler's dmg_11, not from cage_dmg_11 -- the two are equal only by coincidence on this "
           "revision. The moment a balance change moves one and not the other this becomes silently wrong with "
           "no diff to notice. Pin it explicitly in cards.yaml alongside the hitpoints fix."))

# ==================== PART A4: furnace ==============================================================
row(key="furnace", field="kind", current_db="troop", p1_vardefine=None, p2_table="Troop", p3_history="Troop",
    sources=[src("Furnace", 437285, "{{Card Infobox|Cost=4|Rarity=Rare|Type=Troop|...}}"),
             src("Furnace", 437285,
                 "Furnace Attributes row: |4||1.8 sec||Medium (60)||1 sec||7 sec||6||Air & Ground||1x||"
                 "Ground||[[:Category:Troop Cards|Troop]]||{{Rarity|Rare}}")],
    vote="2of2", verdict="pin",
    notes=("NOT A REGRESSION, though it looks like one. 95e9879 set furnace kind:building; the very next "
           "commit, a7bb144, reverted it to troop on the strength of the 4/8/2025 August 2025 Update "
           "('changed the Furnace into a troop that can walk and deal damage'). Re-verified LIVE today at "
           "revid 437285: Type=Troop, Speed Medium (60), Range 6, and no `life` vardefine. The later decision "
           "is sourced and still current -- keep it."))
row(key="furnace", field="hitpoints/damage/hit_speed/range_tiles", current_db="727/179/1.8/6.0",
    p1_vardefine="727/179/1.8", p2_table="1.8 sec, Range 6", p3_history=None,
    sources=[src("Furnace", 437285,
                 "vardefines hp_11=727, dmg_11=179, atk_speed=1.8, with the spawned unit kept separately as "
                 "fire_hp_11=230, fire_dmg_11=207; column headers L97-L99: 'Furnace Hitpoints' | 'Furnace "
                 "Damage' | 'Furnace Damage per second'")],
    vote="2of2", verdict="match",
    notes=("NO CONTAMINATION. Every combat field on the furnace row is bound by the page's own column headers "
           "to the Furnace, not to the Fire Spirit (whose figures are 230/207 under the fire_ prefix). The one "
           "thing that LOOKS like the old defect -- a spawner carrying a damage value and a movement speed -- "
           "is correct here precisely because the Furnace is no longer a building."))
for key in ("furnace", "furnace_evo"):
    row(key=key, field="lifetime_s", current_db=28.0, p1_vardefine=None, p2_table=None, p3_history=None,
        sources=[src("Furnace", 437285,
                     "NO `life` vardefine on the page, and the Furnace Attributes table has NO Lifetime column "
                     "(Cost|Hit Speed|Speed|Deploy Time|Spawn Speed|Range|Target|Count|Transport|Type|Rarity)"),
                 src("Furnace/Evolution", 437286, "same: no `life` vardefine, no Lifetime column")],
        vote="2of2", verdict="escalate",
        notes=("A 2023 GAME-FILE BELIEF IS OUTLIVING THE LIVE WIKI -- via the merge order, not via curation. "
               "MEASURED: build_spec(db,'%s',11) returns lifetime 28.0, so the sim despawns the Furnace after "
               "28 s when the live card is a permanent troop that does not decay. Source traced: "
               "hogeq/config/card_mechanics.json furnace = {\"character\": \"FirespiritHut\", "
               "\"lifetime_s\": 28.0, ...} -- the 2023 dump, whose key still literally calls it a Hut. CardDB "
               "layers card_mechanics ABOVE cards_stats.json, and its docstring justifies that by saying only "
               "STRUCTURAL constants are imported ('mass, sight range, collision radius, weapon load time'). "
               "lifetime_s is not a structural constant, it is a balance value, and it is the one field in that "
               "dump the 4/8/2025 rework invalidated. a7bb144 explicitly recorded 'no lifetime because troops "
               "do not decay' and validated it; the mechanics layer silently put it back. Fix by dropping "
               "lifetime_s from the mechanics import, or curating lifetime_s: null on both furnace rows. Note "
               "furnace_evo ALSO hand-curates lifetime_s: 28.0 ('same building lifetime as the base Furnace'), "
               "so the same stale belief is written twice." % key))
row(key="furnace", field="spawns.interval", current_db=5.0, p1_vardefine=None, p2_table=7.0, p3_history=None,
    sources=[src("Furnace", 437285, "Furnace Attributes 'Spawn Speed' column = 7 sec"),
             src("Furnace", 437285, "intro quote: 'Furnace spawns one Fire Spirit at a time'")],
    vote="2of2", verdict="escalate",
    notes=("SELF-CONTRADICTING CURATION, and the sim believes the wrong half. The cards.yaml line reads "
           "spawns: {unit: fire_spirit, count: 1, interval: 5.0} with the trailing comment "
           "'\"summon a Fire Spirit in front\" every 7s -- ONE, not a pair'. The comment says 7, the value says "
           "5. MEASURED: build_spec spawner_interval=5.0, i.e. 40% more Fire Spirits than the live card "
           "produces. The same row also carries the imported spawn_interval_s=7.0, so the DB holds two "
           "disagreeing values for one concept -- the identical shape already escalated for barbarian_hut in "
           "r2_buildings.jsonl. Curated verified:true, so flagged and not overwritten."))
row(key="tombstone", field="spawns.interval", current_db=3.5, p1_vardefine=None, p2_table=4.0, p3_history=None,
    sources=[src("Tombstone", 436518,
                 "Tombstone Attributes row: |3||4 sec||1 sec||30 sec||Building||Rare -- 'Spawn Speed' = 4 sec")],
    vote="1of1", verdict="escalate",
    notes=("Curated 3.5 against a table that says 4. The curation comment quotes 'a group of two Skeletons, "
           "with a 0.5 seconds delay from each other', which looks like 4 - 0.5 folded into the period -- but "
           "that 0.5 s is the gap BETWEEN the two skeletons of one spawn, not a shortening of the spawn "
           "period. MEASURED: build_spec spawner_interval=3.5 with count=2, about 14% too many skeletons. The "
           "row also carries the imported spawn_interval_s=4.0, the same double-storage. Curated "
           "verified:true, so flagged and not overwritten."))

# ==================== PART A5: mortar_evo -- a fixed bug that survived in the evolution row ==========
row(key="mortar_evo", field="range_tiles", current_db=3.5, p1_vardefine=None, p2_table=11.5, p3_history=None,
    sources=[src("Mortar/Evolution", 437361,
                 "Evolved Mortar Attributes row: |4||4 sec||1 sec||3.5 sec||30 sec||3.5-11.5||2||300||Ground||"
                 "Building||Common -- the Range cell is the BAND '3.5-11.5'"),
             src("Mortar", 437360, "the base page publishes the identical band '3.5-11.5' in the same column")],
    vote="2of2", verdict="update",
    notes=("THE SAME PARSE BUG THE BASE CARD WAS FIXED FOR, LEFT UNFIXED ON THE EVO ROW. The importer takes "
           "the leading number of the '3.5-11.5' band -- the DEAD-ZONE MINIMUM -- as the reach. The base mortar "
           "curation dated 2026-08-15 documents exactly this: 'The range table carried 3.5 -- the DEAD-ZONE "
           "minimum, not the reach -- so an opponent Mortar could never actually siege; a whole ladder "
           "archetype was a dud.' mortar_evo never received that fix and still carries range_tiles: 3.5 with "
           "no min_range_tiles. CORRECTION TO THE OBVIOUS READING, measured rather than assumed: THE ENGINE IS "
           "NOT AFFECTED. engine.build_spec line 548 calls db.attack_range_tiles(BASE), so Evo Mortar resolves "
           "through the base card and reaches 11.50 (measured). This is a latent DATA defect, not a live SIM "
           "defect -- but any caller that passes the '_evo' key straight to CardDB.attack_range_tiles gets 3.5, "
           "because that method returns the row's own range_tiles before it ever consults the base. Fixing the "
           "row (range_tiles 11.5 + min_range_tiles 3.5) closes the trap."))

# ==================== PART A6: cross-page staleness of the SPAWNED unit (reverse direction) ==========
row(key="spear_goblins", field="hit_speed", current_db=1.7, p1_vardefine=1.6, p2_table=1.6, p3_history=None,
    sources=[src("Spear Goblins", 437502,
                 "atk_speed vardefine = 1.6; Attributes row |2||1.6 sec||0.5 sec||Very Fast (120)||1 sec||5||"
                 "500||Air & Ground||x3||Ground||Troop||Common"),
             src("Goblin Hut", 437256,
                 "Spear Goblin Attributes row on the HUT page: |1.7 sec||0.5 sec||Very Fast (120)||5||500||"
                 "Air & Ground||Ground, and atk_speed=1.7"),
             src("Spear Goblins", 437502,
                 "History: the last dated entry touching cadence is 4/8/2025 ('increased the first attack time "
                 "interval to 0.5 seconds (from 0.4)... decreased their range to 5 tiles (from 5.5)'). NO "
                 "dated entry documents 1.7 -> 1.6.")],
    vote="split", verdict="escalate",
    notes=("THE CONTAMINATION RUNS BOTH WAYS, and this is the one instance that leaked. The KB holds 1.7, "
           "which is the GOBLIN HUT page's copy of the Spear Goblin, not the Spear Goblins card page's own "
           "1.6. The impact lands on the unit, not the hut: dps 81/1.7 = 48 (what the DB stores) against "
           "81/1.6 = 51, about 6% low, and it also feeds goblin_hut.spawn_unit_stats. Two live surfaces "
           "disagree with no dated history entry resolving them, so this is an owner call exactly like the "
           "barbarian_hut 13.5-vs-15 split -- but note that the card's own page is normally the authority, and "
           "every other spawner in this sweep shows the SPAWNER page carrying the stale copy."))
row(key="fire_spirit", field="hitpoints", current_db=215, p1_vardefine=215, p2_table=None, p3_history=None,
    sources=[src("Fire Spirit", 437343, "hp_11 = 215 on the card's own page"),
             src("Furnace", 437285, "fire_hp_11 = 230 on the Furnace page's copy of the same unit")],
    vote="split", verdict="escalate",
    notes=("Cross-page conflict on the spawned unit: 215 (card page) against 230 (Furnace page), about 7%. The "
           "KB uses the card page, which is the right default, so nothing is broken today -- but one of the two "
           "surfaces is stale and the Furnace's Fire Spirits are the ones the sim actually produces. Damage "
           "agrees on both pages (207), which makes a genuine 'the Furnace's spirit is a buffed variant' "
           "reading unlikely and a stale-copy reading likely. Owner call."))
row(key="goblins", field="damage", current_db=125, p1_vardefine=125, p2_table=None, p3_history=None,
    sources=[src("Goblins", 437504, "dmg_11 = 125 on the card's own page"),
             src("Goblin Drill", 437382, "dmg_11 = 120 in the Drill page's Goblin section"),
             src("Mortar/Evolution", 437361,
                 "gob_dmg_11 = 120, a second independent spawner page carrying the same stale 120")],
    vote="2of3", verdict="pin",
    notes=("KB CORRECT. Two spawner pages carry a stale 120 for the Goblin while the Goblins card page says "
           "125. The KB reads the card page, so the Drill's and the Evo Mortar's goblins come out right. Logged "
           "because it is the third independent confirmation that SPAWNER PAGES CARRY STALE DUPLICATES of the "
           "unit, which is the structural argument for 95e9879's design decision -- curate the spawn IDENTITY, "
           "read the stats from the unit's own card row -- and the reason spawn_unit_stats must never be "
           "promoted into a stat source."))
row(key="barbarian_hut", field="spawn_unit_stats", current_db="670/192/1.3", p1_vardefine="691/191/1.4",
    p2_table=None, p3_history=None,
    sources=[src("Barbarians", 437362, "hp_11=691, dmg_11=191, atk_speed=1.4 on the card's own page"),
             src("Barbarian Hut", 436519,
                 "hp_11=670, dmg_11=192, atk_speed=1.3 in the hut page's Barbarian section")],
    vote="2of2", verdict="pin",
    notes=("DESIGN WORKING AS INTENDED. The hut page's Barbarian copy is stale on all three fields; the KB's "
           "barbarians row is 691/191/1.4 from the card page, and build_spec wires the hut's spawner to that "
           "row (measured: spawner=barbarians, count=3). The stale numbers survive only inside "
           "spawn_unit_stats, which nothing reads as a stat source. Keep it that way."))

# ==================== PART A7: the remaining spawners, no contamination found =======================
row(key="elixir_collector", field="hitpoints", current_db=1070, p1_vardefine=1070, p2_table=None, p3_history=None,
    sources=[src("Elixir Collector", 436522, "hp_11 = 1070, life = 93")],
    vote="1of1", verdict="match",
    notes=("No spawned unit exists for this card, so the contamination class cannot apply. hitpoints and "
           "lifetime_s (93.0) both match the live page."))
row(key="elixir_collector", field="lifetime", current_db=70, p1_vardefine=93, p2_table=None, p3_history=None,
    sources=[src("Elixir Collector", 436522, "life = 93; the row also holds lifetime_s = 93.0")],
    vote="1of1", verdict="escalate",
    notes=("DOUBLE-STORAGE, one half stale: the row carries BOTH lifetime: 70 AND lifetime_s: 93.0. 93 is "
           "correct. 70 is a dead pre-change value sitting one key away from the live one -- the same footgun "
           "as the spawn_interval_s / spawns.interval pairs. Delete `lifetime`."))
row(key="party_hut", field="<presence>", current_db=None, p1_vardefine=None, p2_table=None, p3_history=None,
    sources=[src("Party Hut", 431993,
                 "{{Card Infobox|Cost=5|Rarity=Legendary|Type=Building|ReleaseDate=13 March 2023}}; sections: "
                 "Goblin Attributes, Spear Goblin Attributes, Goblin Brawler Attributes")],
    vote="1of1", verdict="match",
    notes=("A spawner building on the wiki that is ABSENT from the KB, correctly: purged as event-only by "
           "b29a8d9 (Category:Removed Cards). Checked so this sweep can claim completeness over spawner "
           "BUILDINGS rather than merely over existing KB keys. Its page is a third independent source for "
           "Goblin Brawler stats if the goblin_cage_evo fix ever needs a tie-breaker."))
for key, unit, note in [
        ("witch", "skeletons",
         "hit_speed 1.1 equals the Skeleton's 1.1, but the Witch's own atk_speed IS 1.1 -- coincidence, not "
         "contamination. Her hp 839 / dmg 135 are nowhere near the Skeleton's 81/81."),
        ("night_witch", "bats",
         "hit_speed 1.3 equals the Bat's 1.3 by the same coincidence; hp 906 / dmg 314 against the Bat's "
         "81/81."),
        ("goblin_drill_evo", "goblins",
         "inherits the base drill's 1313 hitpoints and null damage; there is no evo-specific stat row to "
         "contaminate."),
        ("goblin_giant", "spear_goblins",
         "3022/176/1.5 against the Spear Goblin's 133/81/1.7 -- the back-mounted pair appears only in "
         "spawn_unit_stats."),
        ("golem", "golemite",
         "hit_speed 2.5 and speed 0.75 match the Golemite because a Golemite genuinely inherits them; hp 5120 "
         "against 1039 and dmg 312 against 84 separate the bodies."),
        ("lava_hound", "lava_pups", "3581/53/1.3 against the Pup's 217/81/1.7 -- fully distinct."),
        ("elixir_golem", "elixir_golemite",
         "1569/253 against 762/128 -- the split chain halves each body, exactly as published.")]:
    row(key=key, field="hitpoints/damage/hit_speed", current_db="distinct", p1_vardefine=None, p2_table=None,
        p3_history=None,
        sources=[src("(offline)", 0,
                     "snapshot ledger/current_db_snapshot.json compared field-by-field against the spawned "
                     "unit's own KB row")],
        vote="offline", verdict="match",
        notes="NO CONTAMINATION against %s. %s" % (unit, note))

# ==================== PART B: reverse-derivation anchor sweep (ruling 9 follow-on) ==================
row(key="mighty_miner", field="ability_bomb_damage", current_db=366, p1_vardefine=332, p2_table=None,
    p3_history=None,
    sources=[src("Mighty Miner", 437349,
                 "{{#vardefine: escape_11 | 332 }}; column header 'Explosive Escape Damage'; editor note "
                 "'ONLY change the numbers in the three variables directly below ... THAT WILL BE LEVEL 11'")],
    vote="1of1", verdict="update",
    notes=("RULING 9 RE-VERIFIED AGAINST THE LIVE PAGE AND STILL NOT APPLIED. escape_11 = 332 confirmed live "
           "at revid 437349 today. hogeq/config/cards.yaml still holds ability_bomb_damage: 366 with the "
           "superseded comment ('The user's figure is 440 at level 13; no integer level-1 base produces "
           "exactly that, and base 143 ... gives 366 at L11'). The anchor error is the phrase 'at level 13': "
           "Mighty Miner is a CHAMPION, floor 11, and under levels.py the observed 440 is produced at L14 and "
           "at no other level (base 130, floor(130*3.39) = 440), which gives 332 at L11. Ruling 9 parks the "
           "edit in Phase I stage I5, so this is a PENDING-FIX flag rather than a new finding -- but it is "
           "still live in the file today. icebow does not carry the key (Mighty Miner is hogeq's champion)."))
row(key="phoenix_egg", field="hitpoints", current_db=239, p1_vardefine=240, p2_table=None, p3_history=None,
    sources=[src("Phoenix", 437212,
                 "{{#vardefine: egg_11 | 240 }}; column header L75 [scope=col |Phoenix Egg Hitpoints]")],
    vote="1of1", verdict="update",
    notes=("A SECOND VALUE THAT RESOLVES DIFFERENTLY, found by the ruling-9 arithmetic. The cards.yaml comment "
           "claims '239 hp at level 11 per the wiki'; the live page says 240, in BOTH decks. Independently of "
           "the wiki, 239 FAILS the levels.py inversion -- no integer level-1 base produces 239 at L11 (base 93 "
           "gives 238, base 94 gives 240) -- so 239 cannot be a real game value, which is the same signature "
           "that condemned 366. 240 inverts cleanly to base 94. Legendary, floor 9, but the floor does not "
           "bind here: the value is quoted at L11 directly, so this is an off-by-one transcription rather than "
           "a mis-anchored level."))
row(key="little_prince", field="hitpoints/damage", current_db="698/104", p1_vardefine="698/104", p2_table=None,
    p3_history=None,
    sources=[src("Little Prince", 437347,
                 "hp_11 = 698, dmg_11 = 104, 1_atk_speed = 1.2; guard_hp_11 = 1600, guard_dmg_11 = 217, "
                 "charge_11 = 256")],
    vote="1of1", verdict="pin",
    notes=("THE PRECEDENT CASE, CONFIRMED CLOSED. This is the same champion-floor error as "
           "ability_bomb_damage and it was already caught: the row previously held 653/98, described in "
           "cards.yaml as 'one scaling step low, because CHAMPIONS start at level 11 while the import treated "
           "the row as a common-card base'. Live values 698/104 match the KB exactly. It also carried the "
           "OTHER defect class this sweep is about -- the imported row had held the GUARDIAN's 1600/217 and "
           "the Guardian's charge_11 256 -- and charge_damage is now correctly curated to 0. Both are fixed; "
           "recorded so the sweep shows the champion-floor class was swept, not merely the one instance ruling "
           "9 named."))
row(key="<levels.py>", field="base_for vs rarity ladders", current_db="REF_LEVEL=11 + PERCENT table",
    p1_vardefine=None, p2_table=None, p3_history=None,
    sources=[src("Goblin Cage", 436552,
                 "ladder rows are rendered as {{#expr: {{#var:cage_hp_11}} * (1.1^(L-11)) round 0 }} -- the "
                 "wiki COMPUTES every non-11 row from the L11 vardefine with 1.1^n"),
             src("Mighty Miner", 437349,
                 "same 1.1^n rendering; L14 renders 442 where the game's percent table gives 440")],
    vote="2of2", verdict="escalate",
    notes=("THE 'CHECK base_for AGAINST FULL WIKI LADDERS PER RARITY' TASK CANNOT BE DONE THE OBVIOUS WAY, and "
           "the reason matters. The wiki does not PUBLISH per-level ladders: every page renders them from the "
           "single L11 vardefine with 1.1^(L-11), so a ladder comparison would only re-measure the known "
           "1.1^n-vs-percent-table drift instead of testing base_for. Consequence: only the L11 row of any "
           "wiki ladder is evidence, and rarity floors change NOTHING about what an L11 vardefine means -- "
           "rarity_floors.json already measured this across 78 archived pages, where every leveled stat "
           "anchors at the absolute suffix _11 and never at the rarity floor. Floors bind in exactly one "
           "place: clamping the candidate level set when INVERTING an in-game observation, which is what both "
           "ability_bomb_damage and little_prince got wrong. SEPARATE DEFECT FOUND WHILE CHECKING THIS: "
           "cards.py CardDB.resolved_deck (hogeq line 463, icebow line 451) still scales with "
           "mult = 1.1 ** (int(lvl) - 11), the exact formula levels.py's docstring exists to refute. It is NOT "
           "a live bug -- I grepped both trees and resolved_deck has ZERO callers, and the engine path "
           "(build_spec) correctly uses _lv.scale. Flagged as dead code that reintroduces the breakpoint errors "
           "levels.py was written to eliminate the moment anyone revives it."))
row(key="<anchor sweep>", field="curated level-scaled stats", current_db="16 non-invertible per deck",
    p1_vardefine=None, p2_table=None, p3_history=None,
    sources=[src("(offline)", 0,
                 "levels.base_for(v, 11) applied to every curated hitpoints / damage / dps / death_damage / "
                 "spawn_damage / charge_damage / recoil_damage / pulse_damage / shield_hp / kill_heal / "
                 "volley_damage / crown_tower_damage / build_damage value in both decks' cards.yaml, with the "
                 "candidate level set clamped to [rarity floor, 16]")],
    vote="offline", verdict="match",
    notes=("SWEEP RESULT: 16 curated values per deck (identical lists -- the two cards.yaml agree) fail the "
           "integer-L1-base inversion. Fifteen are EXPECTED failures and are not anchor errors: spell "
           "crown_tower_damage (rocket 342, lightning 264, poison 21, earthquake 49, vines 78, miner 39) is a "
           "FRACTION of body damage and is not stored with its own L1 base; the dps values "
           "(elite_barbarians_evo 274, elixir_golemite 116, lava_pups 47, ronin 265, mother_witch_hog 44) are "
           "quotients; pekka_evo.kill_heal 470 is 12.5% of 3760 by construction; earthquake.build_damage 283 "
           "is a building multiplier; vines.damage 306 is exactly 2x the imported 153 (multi-hit); "
           "lumberjack_ghost.hitpoints 4000 is an explicit 'big-but-finite hp pool' approximation for an "
           "untargetable body. The SIXTEENTH is phoenix_egg 239, reported above as an update. No other "
           "reverse-derivation in either deck resolves differently under rarity floors: the only two values in "
           "the KB ever derived from an observation at a level OTHER than 11 are ability_bomb_damage and "
           "little_prince, and both are champion-floor cases already adjudicated."))

OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in L) + "\n", encoding="utf-8")
print("lines:", len(L))
print(Counter(r["verdict"] for r in L))
print("keys:", len({r["key"] for r in L}))
