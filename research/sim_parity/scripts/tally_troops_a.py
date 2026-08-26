# -*- coding: utf-8 -*-
"""Deterministic tally: how many (key, field) comparisons were made, and how many matched."""
import re, os, json, sys
sys.path.insert(0, r"C:/Users/benpe/ClashBot/research/sim_parity/scripts")
from attrs import parse_attr_table
CACHE = r"C:/Users/benpe/ClashBot/research/sim_parity/webcache"
L = r"C:/Users/benpe/ClashBot/research/sim_parity/ledger"
DB = json.load(open(os.path.join(L, "current_db_snapshot.json"), encoding="utf-8"))["cards"]
PAGES = json.load(open(os.path.join(L, "r2_troops_a_livecheck.json"), encoding="utf-8"))

SPEED = {"slow": 0.75, "medium": 1.0, "fast": 1.5, "very fast": 2.0}
def spd(c):
    m = re.match(r'([A-Za-z ]+?)\s*\(', c.strip())
    return SPEED.get((m.group(1) if m else c).strip().lower())
def num(s):
    if s is None: return None
    m = re.search(r'-?\d+(?:\.\d+)?', str(s).replace(",", ""))
    return float(m.group(0)) if m else None
def rng(c):
    m = re.search(r'\(([\d.]+)\)', c)
    return float(m.group(1)) if m else num(c)

# ---- P1 vardefine map (same as the sweep) ----
P1MAP = {
 'archers': {'hitpoints':'hp_base','damage':'dmg_base','hit_speed':'atk_speed'},
 'baby_dragon': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'balloon': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','death_damage':'death_11'},
 'bandit': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','dash_damage':'dash_11'},
 'barbarians': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'bats': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'battle_healer': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'battle_ram': {'hitpoints':'ram_hp_11','damage':'ram_dmg_11','charge_damage':'charge_dmg_11'},
 'berserker': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'bomber': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'bowler': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'bush_goblin': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'cannon_cart': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','lifetime_s':'life'},
 'dark_prince': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','shield_hp':'shield_11','charge_damage':'charge_11'},
 'dart_goblin': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'decoy_goblin': {'hitpoints':'de_hp_11','damage':'de_dmg_11','hit_speed':'de_atk_speed'},
 'electro_dragon': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','hits_per_attack':'dmg_hits'},
 'electro_giant': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','reflect_damage':'reflect_11'},
 'electro_spirit': {'hitpoints':'hp_11','damage':'dmg_11'},
 'electro_wizard': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','hits_per_attack':'dmg_hits','spawn_damage':'zap_11'},
 'elite_barbarians': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'elixir_golem': {'hitpoints':'golem_hp_11','damage':'golem_dmg_11','hit_speed':'golem_atk_speed'},
 'elixir_golemite': {'hitpoints':'mite_hp_11','damage':'mite__dmg_11','hit_speed':'mite_atk_speed'},
 'elixir_blob': {'hitpoints':'blob_hp_11','damage':'blob__dmg_11','hit_speed':'blob_atk_speed'},
 'executioner': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','hits_per_attack':'dmg_hits'},
 'fire_spirit': {'hitpoints':'hp_11','damage':'dmg_11'},
 'firecracker': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed','hits_per_attack':'dmg_hits'},
 'fisherman': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'flying_machine': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'furnace': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
 'ghost_souldier': {'hitpoints':'soul_hp_11','damage':'soul_dmg_11','hit_speed':'soul_atk_speed'},
 'giant': {'hitpoints':'hp_11','damage':'dmg_11','hit_speed':'atk_speed'},
}
# which attributes table carries each key's OWN row
TBL_ID = {"bush_goblin": "unit-attributes-table-secondary",
          "elixir_golemite": "unit-attributes-table-secondary",
          "elixir_blob": "unit-attributes-table-tertiary"}
TBL_IDX = {"decoy_goblin": ("Goblin_Barrel_Evolution.wikitext", 2),
           "ghost_souldier": ("Royal_Ghost_Evolution.wikitext", 2)}

def tables(t):
    return list(re.finditer(r'\{\|[^\n]*unit-attributes-table[^\n]*\n(.*?)\n\|\}', t, re.S))
def row_by_index(t, idx):
    blk = tables(t)[idx].group(0)
    heads = [re.sub(r'<br\s*/?>.*', '', h).strip() for h in re.findall(r'!\s*scope="col"\s*\|?\s*([^!\n]*)', blk)]
    heads = [h for h in heads if h]
    rows = [l for l in blk.split("\n") if l.startswith("|") and "||" in l]
    if not rows: return {}
    return dict(zip(heads, [c.strip() for c in rows[0].lstrip("|").split("||")]))

VD = {}
TXT = {}
for title, meta in PAGES.items():
    t = open(os.path.join(CACHE, meta["cache_file"]), encoding="utf-8").read()
    for k in meta["keys"]:
        VD[k] = {m.group(1): m.group(2).strip() for m in
                 re.finditer(r'\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}]*?)\s*\}\}', t)}
        TXT[k] = (t, meta["cache_file"])

checked = 0; matched = 0; mism = []

# ---- P1 pass ----
for k, fm in P1MAP.items():
    for f, vn in fm.items():
        wv = VD[k].get(vn); dbv = DB[k].get(f)
        if wv is None or dbv is None:
            checked += 1; mism.append((k, f, dbv, wv, "P1/missing")); continue
        checked += 1
        if abs(float(dbv) - float(wv)) < 1e-6: matched += 1
        else: mism.append((k, f, dbv, wv, "P1"))

# ---- P2 pass ----
for k in P1MAP:
    t, cf = TXT[k]
    if k in TBL_IDX:
        cells = row_by_index(open(os.path.join(CACHE, TBL_IDX[k][0]), encoding="utf-8").read(), TBL_IDX[k][1])
    else:
        at = parse_attr_table(t, TBL_ID.get(k, "unit-attributes-table"))
        cells = {}
        if at and at[1]:
            heads, arows = at
            for i, c in enumerate(arows[0]):
                if i < len(heads): cells[heads[i]] = c
    pairs = []
    if "Hit Speed" in cells:        pairs.append(("hit_speed", DB[k].get("hit_speed"), num(cells["Hit Speed"])))
    if "Deploy Time" in cells:      pairs.append(("deploy_time", DB[k].get("deploy_time"), num(cells["Deploy Time"])))
    if "Range" in cells:            pairs.append(("range_tiles", DB[k].get("range_tiles"), rng(cells["Range"])))
    if "Speed" in cells:            pairs.append(("speed_tiles", DB[k].get("speed_tiles"), spd(cells["Speed"])))
    if "Projectile Speed" in cells: pairs.append(("projectile_speed", DB[k].get("projectile_speed"), num(cells["Projectile Speed"])))
    if "Splash Radius" in cells:    pairs.append(("splash_radius", DB[k].get("splash_radius"), num(cells["Splash Radius"])))
    if "Cost" in cells:             pairs.append(("elixir", DB[k].get("elixir"), num(cells["Cost"])))
    if "Rarity" in cells:           pairs.append(("rarity", str(DB[k].get("rarity")).lower(), cells["Rarity"].strip().lower()))
    if "Projectile Range" in cells: pairs.append(("projectile_range", DB[k].get("projectile_range"), num(cells["Projectile Range"])))
    if "Lifetime" in cells:         pairs.append(("lifetime_s", DB[k].get("lifetime_s"), num(cells["Lifetime"])))
    if "Stun Duration" in cells:    pairs.append(("stun_duration_s", DB[k].get("stun_duration_s"), num(cells["Stun Duration"])))
    if "Projectile Width" in cells: pairs.append(("projectile_width_tiles", DB[k].get("projectile_width_tiles"), num(cells["Projectile Width"])))
    if "Projectile Radius" in cells: pairs.append(("projectile_radius", DB[k].get("projectile_radius"), num(cells["Projectile Radius"])))
    if "Invisibility Time" in cells: pairs.append(("invisibility_time_s", DB[k].get("invisibility_time_s"), num(cells["Invisibility Time"])))
    for f, dbv, wv in pairs:
        if wv is None: continue
        checked += 1
        if dbv is None: mism.append((k, f, dbv, wv, "P2/missing")); continue
        same = (abs(dbv - wv) < 1e-6) if isinstance(dbv, (int, float)) and isinstance(wv, (int, float)) else (dbv == wv)
        if same: matched += 1
        else: mism.append((k, f, dbv, wv, "P2"))

# ---- derived: dps internal consistency (damage / hit_speed) ----
for k in P1MAP:
    d = DB[k]
    if d.get("dps") and d.get("damage") and d.get("hit_speed"):
        checked += 1
        exp = round(d["damage"] / d["hit_speed"])
        if abs(exp - d["dps"]) <= 1: matched += 1
        else: mism.append((k, "dps", d["dps"], exp, "derived"))

# ---- evolution gate ----
for title, meta in PAGES.items():
    t = open(os.path.join(CACHE, meta["cache_file"]), encoding="utf-8").read()
    nav = re.search(r'\{\{SubpageNavBox[^}]*\}\}', t)
    wiki_evo = bool(nav and re.search(r'Evolution\s*=\s*yes', nav.group(0)))
    for k in meta["keys"]:
        ev = DB[k].get("evolution")
        dbev = bool(ev.get("available")) if isinstance(ev, dict) else bool(ev)
        checked += 1
        if dbev == wiki_evo: matched += 1
        else: mism.append((k, "evolution.available", dbev, wiki_evo, "P2/nav"))

print("fields_checked =", checked)
print("matches        =", matched)
print("non-matching   =", len(mism))
print()
for m in sorted(mism): print("   ", m)
