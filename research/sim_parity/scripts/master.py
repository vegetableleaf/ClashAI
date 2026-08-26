import re, os, json, sys
sys.path.insert(0, r"C:/Users/benpe/ClashBot/research/sim_parity/scripts")
from attrs import parse_attr_table, clean
CACHE = r"C:/Users/benpe/ClashBot/research/sim_parity/webcache"
DB = json.load(open(r"C:/Users/benpe/ClashBot/research/sim_parity/ledger/current_db_snapshot.json", encoding="utf-8"))["cards"]

PAGES = json.load(open(r"C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_a_livecheck.json", encoding="utf-8"))

def vardefines(t):
    return {m.group(1): m.group(2).strip() for m in
            re.finditer(r'\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}]*?)\s*\}\}', t)}

def num(s):
    if s is None: return None
    m = re.search(r'-?\d+(?:\.\d+)?', str(s).replace(",", ""))
    return float(m.group(0)) if m else None

rows=[]
for title, meta in PAGES.items():
    t = open(os.path.join(CACHE, meta["cache_file"]), encoding="utf-8").read()
    vd = vardefines(t)
    at = parse_attr_table(t)
    heads, arows = at if at else ([], [])
    for k in meta["keys"]:
        d = DB.get(k, {})
        rows.append(dict(key=k, title=title, vd=vd, heads=heads, arows=arows, db=d))

# ---- identity test: wiki First Hit Speed  ==?  hit_speed - load_time_s
print("%-18s %-8s %-8s %-8s %-8s %-8s" % ("key","wikiFHS","db_hit","db_load","hit-load","match"))
for r in rows:
    if not r["heads"] or not r["arows"]: continue
    try: i = r["heads"].index("First Hit Speed")
    except ValueError: continue
    fhs = num(r["arows"][0][i]) if i < len(r["arows"][0]) else None
    hs, lt = r["db"].get("hit_speed"), r["db"].get("load_time_s")
    calc = round(hs-lt,3) if (hs is not None and lt is not None) else None
    ok = "YES" if (fhs is not None and calc is not None and abs(fhs-calc)<1e-6) else "** NO **"
    print("%-18s %-8s %-8s %-8s %-8s %-8s" % (r["key"], fhs, hs, lt, calc, ok))
