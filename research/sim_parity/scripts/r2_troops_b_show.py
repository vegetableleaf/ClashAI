import sys, re
sys.path.insert(0,'scripts')
from r2_troops_b_digest import digest
for fn in sys.argv[1:]:
    d=digest(fn)
    print("="*20, fn, "="*20)
    print("### VARDEFINES")
    for k,v in d['vardefines']: print(f"  {k} = {v}")
    print("### SUBHEADERS", d['subheaders'])
    for i,t in enumerate(d['attr_tables']):
        print(f"### ATTR TABLE {i}: {' | '.join(t['headers'])}")
        for r in t['rows']: print("   ROW:", r)
    recent=[l for l in d['history'] if re.search(r'/2024|/2025|/2026', l)]
    print("### RECENT HISTORY (%d of %d lines)" % (len(recent),len(d['history'])))
    for l in recent: print("  ", l[:600])
