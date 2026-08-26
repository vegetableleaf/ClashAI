import re, os, json, sys
sys.path.insert(0, r"C:/Users/benpe/ClashBot/research/sim_parity/scripts")
from attrs import parse_attr_table
CACHE = r"C:/Users/benpe/ClashBot/research/sim_parity/webcache"
DB = json.load(open(r"C:/Users/benpe/ClashBot/research/sim_parity/ledger/current_db_snapshot.json", encoding="utf-8"))["cards"]
PAGES = json.load(open(r"C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_a_livecheck.json", encoding="utf-8"))

def vardefines(t):
    return {m.group(1): m.group(2).strip() for m in
            re.finditer(r'\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}]*?)\s*\}\}', t)}

SHOW = ["hitpoints","damage","hit_speed","dps","count","range_tiles","range","speed","speed_tiles",
        "deploy_time","projectile_speed","splash_radius","splash_radius_tiles","elixir","rarity",
        "targets","attacks","crown_tower_damage","death_damage","death_radius_tiles","shield_hp",
        "charge_damage","dash_damage","lifetime_s","load_time_s","sight","collision","mass"]

for title, meta in PAGES.items():
    t = open(os.path.join(CACHE, meta["cache_file"]), encoding="utf-8").read()
    vd = vardefines(t)
    at = parse_attr_table(t)
    print("="*78)
    print("PAGE:", title, " rev", meta["live_revid"], " keys:", meta["keys"])
    print("  P1 vardefines:", json.dumps(vd))
    if at:
        heads, arows = at
        for ri, row in enumerate(arows):
            print(f"  P2 attr-row {ri}: " + " | ".join(
                f"{(heads[i] if i<len(heads) else '?')}={c}" for i, c in enumerate(row)))
    else:
        print("  P2: NO unit-attributes-table")
    for k in meta["keys"]:
        d = DB.get(k, {})
        print(f"  -- DB[{k}] verified={d.get('verified')}")
        print("     " + ", ".join(f"{f}={d[f]}" for f in SHOW if f in d))
        extra = [f for f in d if f not in SHOW and f not in
                 ("display","kind","flags","movement","evolution","verified","win_condition","splash")]
        if extra:
            print("     EXTRA: " + ", ".join(f"{f}={d[f]}" for f in extra))
