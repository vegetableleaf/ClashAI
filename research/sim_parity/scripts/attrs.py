import re, os, json, sys
CACHE = r"C:/Users/benpe/ClashBot/research/sim_parity/webcache"

def clean(s):
    s = re.sub(r'\{\{Rarity\|([^}]*)\}\}', r'\1', s)
    s = re.sub(r'\[\[:?[^|\]]*\|([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\[\[([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\{\{Icon\|[^}]*\}\}', '', s)
    s = re.sub(r'<br\s*/?>', ' ', s)
    s = re.sub(r"'''?", '', s)
    s = re.sub(r'\{\{[^}]*\}\}', '', s)
    return s.strip()

def parse_attr_table(text, tid="unit-attributes-table"):
    """Return list of dicts: header->cell, for each data row of the table with this id."""
    m = re.search(r'\{\|[^\n]*id="%s".*?\n\|\}' % re.escape(tid), text, re.S)
    if not m: return None
    body = m.group(0)
    lines = body.split("\n")
    heads, rows, cur = [], [], None
    for l in lines:
        ls = l.strip()
        if ls.startswith("!"):
            for h in re.split(r'\!\!', ls.lstrip("!")):
                h = re.sub(r'^scope="col"\s*\|', '', h.strip())
                heads.append(clean(h))
        elif ls.startswith("|-"):
            if cur: rows.append(cur)
            cur = []
        elif ls.startswith("|") and cur is not None and not ls.startswith("|}"):
            for cpart in re.split(r'\|\|', ls[1:]):
                cur.append(clean(cpart))
    if cur: rows.append(cur)
    rows = [r for r in rows if r]
    return heads, rows

if __name__ == "__main__":
    f = sys.argv[1]
    tid = sys.argv[2] if len(sys.argv) > 2 else "unit-attributes-table"
    t = open(os.path.join(CACHE, f), encoding="utf-8").read()
    r = parse_attr_table(t, tid)
    if not r: print("NO TABLE", tid); sys.exit()
    heads, rows = r
    for row in rows:
        for i, cell in enumerate(row):
            h = heads[i] if i < len(heads) else f"col{i}"
            print(f"   {h:24s} : {cell}")
        print("   " + "-"*40)
