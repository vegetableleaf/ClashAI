# -*- coding: utf-8 -*-
"""r2 troops_c: extraction helpers -- dump P1 vardefines, P2 attribute tables + infobox,
P3 History section for a cached wikitext page."""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
WEBCACHE = "C:/Users/benpe/ClashBot/research/sim_parity/webcache/"

def load(fn):
    return open(WEBCACHE + fn, encoding="utf-8").read()

def vardefines(wt):
    return re.findall(r"\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}|]+?)\s*\}\}", wt)

def infobox(wt):
    m = re.search(r"\{\{Card[_ ]Infobox([^}]*)\}\}", wt)
    return m.group(1).strip() if m else None

def attr_tables(wt):
    """Return list of (subheader, header_cells, data_rows) for wikitable blocks whose id
    contains 'unit-attributes-table'."""
    out = []
    for m in re.finditer(r"\{\|[^\n]*id=\"(unit-attributes-table[^\"]*)\"[^\n]*\n(.*?)\n\|\}", wt, re.S):
        tid, body = m.group(1), m.group(2)
        # preceding subheader
        pre = wt[:m.start()]
        sh = re.findall(r"\{\{StatisticsSubheader\|([^}]+)\}\}", pre)
        sub = sh[-1] if sh else "?"
        headers = re.findall(r"!\s*(?:scope=\"col\"\s*\|)?\s*([^\n!]+)", body)
        headers = [re.sub(r"<br\s*/?>.*|\{\{Icon[^}]*\}\}", "", h).strip() for h in headers]
        rows = []
        for rowm in re.split(r"\n\|-\s*\n", body):
            lines = [l for l in rowm.split("\n") if l.startswith("|") and not l.startswith("|}")]
            if lines:
                cells = []
                for l in lines:
                    cells += [c.strip() for c in l.lstrip("|").split("||")]
                if any(c and not c.startswith("!") for c in cells):
                    rows.append(cells)
        out.append((tid, sub, headers, rows))
    return out

def history(wt):
    m = re.search(r"==\s*History\s*==\n(.*?)(\n==[^=]|\Z)", wt, re.S)
    return m.group(1) if m else ""

def dump(fn):
    wt = load(fn)
    print("######", fn, "len", len(wt))
    print("--INFOBOX:", infobox(wt))
    print("--VARDEFINES:")
    for k, v in vardefines(wt):
        print("   %s = %s" % (k, v))
    print("--ATTR TABLES:")
    for tid, sub, headers, rows in attr_tables(wt):
        print("  [%s] %s" % (tid, sub))
        print("   H:", " | ".join(headers))
        for r in rows:
            print("   R:", " | ".join(r))
    print("--HISTORY:")
    h = history(wt)
    # only lines with numbers/dates (stat-relevant), keep short
    for line in h.split("\n"):
        s = line.strip()
        if s.startswith("*") and re.search(r"\d", s):
            print("   ", s[:400])

if __name__ == "__main__":
    for fn in sys.argv[1:]:
        dump(fn)
