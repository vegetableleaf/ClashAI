# -*- coding: utf-8 -*-
"""r1a stage 3: build final r1a_evolutions.json from stage1/stage2 + master history."""
import json, io, sys, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
LEDGER = "C:/Users/benpe/ClashBot/research/sim_parity/ledger/"
FETCH_DATE = "2026-08-25"

s1 = json.load(open(LEDGER + "r1a_stage1.json", encoding="utf-8"))
s2 = json.load(open(LEDGER + "r1a_stage2.json", encoding="utf-8"))

def kb_key(card):
    return card.lower().replace(".", "").replace(" ", "_") + "_evo"

# canonical release dates (DD/MM/YYYY wiki-euro format -> ISO), assembled from
# master-page History (==History== of Card Evolution, revid 437535) cross-checked
# against each subpage's infobox/trivia (stage2). Verified consistent except Hunter.
release = {
 "Barbarians": "2023-06-19", "Royal Giant": "2023-06-19", "Firecracker": "2023-06-19", "Skeletons": "2023-06-19",
 "Mortar": "2023-07-03", "Knight": "2023-08-07", "Royal Recruits": "2023-09-04", "Bats": "2023-10-02",
 "Archers": "2023-11-06", "Ice Spirit": "2023-12-04", "Valkyrie": "2024-01-01", "Bomber": "2024-02-05",
 "Wall Breakers": "2024-02-14", "Tesla": "2024-03-04", "Zap": "2024-03-11", "Battle Ram": "2024-04-01",
 "Wizard": "2024-05-06", "Goblin Barrel": "2024-06-03", "Goblin Giant": "2024-07-01", "Goblin Drill": "2024-07-15",
 "Goblin Cage": "2024-08-05", "P.E.K.K.A.": "2024-09-02", "Mega Knight": "2024-09-14", "Electro Dragon": "2024-10-07",
 "Musketeer": "2024-11-04", "Cannon": "2024-11-15", "Giant Snowball": "2024-12-02", "Dart Goblin": "2025-01-06",
 "Lumberjack": "2025-02-03", "Hunter": "2025-03-03", "Executioner": "2025-04-07", "Witch": "2025-05-05",
 "Inferno Dragon": "2025-06-02", "Skeleton Barrel": "2025-07-07", "Furnace": "2025-08-04", "Baby Dragon": "2025-09-01",
 "Skeleton Army": "2025-10-06", "Royal Ghost": "2025-10-17", "Royal Hogs": "2025-11-03", "Minion Horde": "2026-04-06",
 "Princess": "2026-06-01", "Elite Barbarians": "2026-08-03",
}

kb42 = ["archers_evo", "baby_dragon_evo", "barbarians_evo", "bats_evo", "battle_ram_evo", "bomber_evo",
 "cannon_evo", "dart_goblin_evo", "electro_dragon_evo", "elite_barbarians_evo", "executioner_evo",
 "firecracker_evo", "furnace_evo", "giant_snowball_evo", "goblin_barrel_evo", "goblin_cage_evo",
 "goblin_drill_evo", "goblin_giant_evo", "hunter_evo", "ice_spirit_evo", "inferno_dragon_evo", "knight_evo",
 "lumberjack_evo", "mega_knight_evo", "minion_horde_evo", "mortar_evo", "musketeer_evo", "pekka_evo",
 "princess_evo", "royal_ghost_evo", "royal_giant_evo", "royal_hogs_evo", "royal_recruits_evo",
 "skeleton_army_evo", "skeleton_barrel_evo", "skeletons_evo", "tesla_evo", "valkyrie_evo",
 "wall_breakers_evo", "witch_evo", "wizard_evo", "zap_evo"]

today = datetime.date(2026, 8, 25)
rows = []
live_keys = []
for title, info in s2["pages"].items():
    card = title.split("/")[0]
    key = kb_key(card)
    rel = release.get(card)
    cyc = s2["master_cycles"].get(card)
    d = datetime.date.fromisoformat(rel) if rel else None
    status = "live" if (d and d <= today) else ("announced" if d else "uncertain")
    notes = []
    if card == "Hunter":
        notes.append("WIKI-INTERNAL CONFLICT: master History prose says 3/2/2025 but its own Version-History anchor says 3/3/2025 ('March 2025 Update') and the subpage says 3 March 2025; recorded 2025-03-03, conflict left on record")
    if card == "Elite Barbarians":
        notes.append("subpage is a stub ('Coming soon...', 13 bytes) with no infobox; release + Cycles=1 documented on master page Card Evolution revid 437535 History ('On 3/8/2026 the August 2026 Update allowed the Elite Barbarians to evolve'); official CR API lags this evo (measured 2026-08-25)")
    if card == "Princess":
        notes.append("subpage infobox says only 'June 2026' (Season 84, alongside Heroic Tombstone); precise 1/6/2026 from master History")
    if card == "Minion Horde":
        notes.append("released alongside Hero Balloon per subpage trivia; infobox 'April 6,2026' confirms 6/4/2026 is DD/MM")
    rows.append({"key": key, "page": title, "revid": info["revid"], "fetched": FETCH_DATE,
                 "release_date": rel, "evo_cycles": cyc, "status": status,
                 "release_doc": ("Card Evolution#History (revid 437535) only" if card == "Elite Barbarians"
                                 else "Card Evolution#History (revid 437535) + subpage"),
                 "notes": "; ".join(notes) if notes else None})
    if status == "live":
        live_keys.append(key)

rows.sort(key=lambda r: r["release_date"] or "9999")

probes = [
 {"key": "berserker_evo", "page": "Berserker/Evolution", "revid": None, "fetched": FETCH_DATE,
  "release_date": None, "evo_cycles": None, "status": "absent",
  "notes": "mandatory negative probe: page missing on wiki as expected; CONFLICT: official CR API forward-declares a Berserker evo (measured 2026-08-25) -- wiki says it does not exist; not resolved here"},
 {"key": "giant_evo", "page": "Giant/Evolution", "revid": None, "fetched": FETCH_DATE,
  "release_date": None, "evo_cycles": None, "status": "absent",
  "notes": "mandatory negative probe: page missing on wiki as expected; CONFLICT: official CR API forward-declares a Giant evo (measured 2026-08-25) -- wiki says it does not exist; not resolved here"},
 {"key": "arrows_evo", "page": "Arrows/Evolution", "revid": None, "fetched": FETCH_DATE,
  "release_date": None, "evo_cycles": None, "status": "absent",
  "notes": "mandatory negative probe: page missing on wiki as expected"},
]

live_set = set(live_keys)
kb_set = set(kb42)
additions = sorted(live_set - kb_set)
removals = sorted(kb_set - live_set)

out = {
 "meta": {
  "fetched": FETCH_DATE,
  "method": "category members (Troop/Building/Spell/Champion Cards, 196 unique titles) x subpage existence probes, crossed against master page Card Evolution (revid 437535); every extracted page archived to webcache/",
  "master_page": {"title": "Card Evolution", "revid": 437535,
                  "redirects": {"Evolution": 424247, "Evolutions": 436135}},
  "probe_results": {"Berserker/Evolution": "absent (expected)", "Giant/Evolution": "absent (expected)",
                    "Arrows/Evolution": "absent (expected)",
                    "Elite Barbarians/Evolution": "live (expected; stub subpage, release documented on master page)"},
  "date_format_note": "wiki uses DD/MM/YYYY; anchored by 19/6/2023 Card Evolution Update and Minion Horde infobox 'April 6,2026' == 6/4/2026",
  "cycles_source": "master table (42/42), cross-checked vs subpage infobox CycleCost (41/42 present, 0 mismatches; Elite Barbarians stub lacks one)",
 },
 "live_count": len(live_keys),
 "kb_comparison": {"kb_count": len(kb42), "live_count": len(live_keys),
                   "additions_live_not_in_kb": additions, "removals_in_kb_not_live": removals},
 "conflicts": [
  "Hunter/Evolution release date: master History prose '3/2/2025' vs its own linked anchor 'March 2025 Update (3/3/2025)' and subpage '3 March 2025' (revid 436718)",
  "Berserker evolution: official CR API forward-declares it; wiki page absent (mandatory probe)",
  "Giant evolution: official CR API forward-declares it; wiki page absent (mandatory probe)",
  "Elite Barbarians evolution: official CR API lags it; wiki documents live since 3/8/2026 (master revid 437535), subpage is a stub",
 ],
 "evolutions": rows,
 "negative_probes": probes,
}
with open(LEDGER + "r1a_evolutions.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print("live:", len(live_keys), "additions:", additions, "removals:", removals)
print("statuses non-live:", {r["key"]: r["status"] for r in rows if r["status"] != "live"})
for r in rows:
    print(r["release_date"], r["key"], "cycles=" + str(r["evo_cycles"]), "revid=" + str(r["revid"]))
