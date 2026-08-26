import re, os, json, sys
sys.path.insert(0, r"C:/Users/benpe/ClashBot/research/sim_parity/scripts")
from attrs import parse_attr_table
CACHE = r"C:/Users/benpe/ClashBot/research/sim_parity/webcache"
L = r"C:/Users/benpe/ClashBot/research/sim_parity/ledger"
DB = json.load(open(os.path.join(L,"current_db_snapshot.json"), encoding="utf-8"))["cards"]
PAGES = json.load(open(os.path.join(L,"r2_troops_a_livecheck.json"), encoding="utf-8"))

SPEED = {"slow":0.75, "medium":1.0, "fast":1.5, "very fast":2.0}
def spd(cell):
    m = re.match(r'([A-Za-z ]+?)\s*\(', cell.strip())
    return SPEED.get((m.group(1) if m else cell).strip().lower())
def num(s):
    if s is None: return None
    m = re.search(r'-?\d+(?:\.\d+)?', str(s).replace(",",""))
    return float(m.group(0)) if m else None
def rng(cell):          # "Melee: Short (0.7)" -> 0.7 ; "5.5" -> 5.5
    m = re.search(r'\(([\d.]+)\)', cell)
    return float(m.group(1)) if m else num(cell)

# which attr table id holds each key's own row
TBL = {"bush_goblin":"unit-attributes-table-secondary",
       "elixir_golemite":"unit-attributes-table-secondary",
       "elixir_blob":"unit-attributes-table-tertiary"}

out=[]
for title, meta in PAGES.items():
    t = open(os.path.join(CACHE, meta["cache_file"]), encoding="utf-8").read()
    vd = {m.group(1): m.group(2).strip() for m in
          re.finditer(r'\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}]*?)\s*\}\}', t)}
    for k in meta["keys"]:
        d = DB.get(k, {})
        at = parse_attr_table(t, TBL.get(k, "unit-attributes-table"))
        cells = {}
        if at:
            heads, arows = at
            if arows:
                for i,c in enumerate(arows[0]):
                    if i < len(heads): cells[heads[i]] = c
        # P2-derived comparisons
        cmp = []
        if "Hit Speed" in cells:      cmp.append(("hit_speed", d.get("hit_speed"), num(cells["Hit Speed"])))
        if "Deploy Time" in cells:    cmp.append(("deploy_time", d.get("deploy_time"), num(cells["Deploy Time"])))
        if "Range" in cells:          cmp.append(("range_tiles", d.get("range_tiles"), rng(cells["Range"])))
        if "Speed" in cells:          cmp.append(("speed_tiles", d.get("speed_tiles"), spd(cells["Speed"])))
        if "Projectile Speed" in cells: cmp.append(("projectile_speed", d.get("projectile_speed"), num(cells["Projectile Speed"])))
        if "Splash Radius" in cells:  cmp.append(("splash_radius", d.get("splash_radius"), num(cells["Splash Radius"])))
        if "Cost" in cells:           cmp.append(("elixir", d.get("elixir"), num(cells["Cost"])))
        if "Rarity" in cells:         cmp.append(("rarity", str(d.get("rarity")).lower(), cells["Rarity"].strip().lower()))
        if "Projectile Range" in cells: cmp.append(("projectile_range", d.get("projectile_range"), num(cells["Projectile Range"])))
        if "Lifetime" in cells:       cmp.append(("lifetime_s", d.get("lifetime_s"), num(cells["Lifetime"])))
        if "Stun Duration" in cells:  cmp.append(("stun_duration_s", d.get("stun_duration_s"), num(cells["Stun Duration"])))
        for f, dbv, wv in cmp:
            if wv is None or dbv is None: continue
            same = (abs(dbv-wv) < 1e-6) if isinstance(dbv,(int,float)) and isinstance(wv,(int,float)) else (dbv==wv)
            if not same: out.append((k, f, dbv, wv, "P2"))
    # P1 comparisons handled per-key below
print("%-18s %-20s %-12s %-12s %s" % ("key","field","current_db","wiki_P2","path"))
for r in sorted(out): print("%-18s %-20s %-12s %-12s %s" % r)
print("\nTOTAL P2 MISMATCHES:", len(out))
