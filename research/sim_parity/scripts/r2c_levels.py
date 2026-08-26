# -*- coding: utf-8 -*-
"""Pull every unit-statistics-table (per-level hp/damage/dps) from a cached page and print
the LEVEL 11 row, which is the level the KB anchors on."""
import re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
CACHE = "C:/Users/benpe/ClashBot/research/sim_parity/webcache/"

def tables(wt):
    out = []
    for m in re.finditer(r'\{\|[^\n]*id="(unit-statistics-table[^"]*)"[^\n]*\n(.*?)\n\|\}', wt, re.S):
        tid, body = m.group(1), m.group(2)
        pre = wt[:m.start()]
        sh = re.findall(r"\{\{StatisticsSubheader\|([^}]+)\}\}", pre)
        sub = sh[-1] if sh else "?"
        hdr = [re.sub(r"\{\{Icon[^}]*\}\}|<br\s*/?>", "", h).strip()
               for h in re.findall(r"!\s*(?:scope=\"col\"\s*\|)?\s*([^\n!]+)", body)]
        rows = []
        for blk in re.split(r"\n\|-\s*\n", body):
            cells = [l[1:].strip() for l in blk.split("\n")
                     if l.startswith("|") and not l.startswith("|}") and not l.startswith("|-")]
            if cells:
                rows.append(cells)
        out.append((tid, sub, hdr, rows))
    return out

for fn in sys.argv[1:]:
    wt = open(CACHE + fn, encoding="utf-8").read()
    print("######", fn)
    for tid, sub, hdr, rows in tables(wt):
        print("  [%s] %s" % (tid, sub))
        print("   H:", " | ".join(hdr))
        for r in rows:
            if r and r[0].strip() in ("11", "9"):
                print("   L%-3s" % r[0], " | ".join(r[1:]))
