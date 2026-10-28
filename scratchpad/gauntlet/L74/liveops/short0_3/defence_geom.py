"""For my defensive buildings (Tesla, Xbow): nearest enemy troops (tiles) and hp, every STEP ticks, until the building dies. Raw ents coords are milli-tiles."""
import json, math, sys
f, STEP = sys.argv[1], int(sys.argv[2])
names, last = {}, -999
for l in open(f, 'rb'):
    if not l.startswith(b'{"event": "frame"'): continue
    d = json.loads(l); ms = d['my_side']; t = d['tick']
    for u in ((d.get('phase2') or {}).get('units') or []): names[u['address']] = u.get('name')
    if t - last < STEP: continue
    last = t
    ents = [(e[0], e[1] / 1000, e[2] / 1000, names.get(e[7]) or str(e[3]), e[4], e[7]) for e in d.get('ents') or []]
    for b in [e for e in ents if e[0] == ms and e[3] in ('Tesla', 'Xbow')]:
        near = sorted((math.hypot(b[1] - e[1], b[2] - e[2]), e[3], e[4]) for e in ents if e[0] != ms and 'Tower' not in e[3])[:3]
        print(f"t{t} {b[3]} hp{b[4]} at ({b[1]:.1f},{b[2]:.1f}) nearest enemies (tiles,name,hp):", [(round(a, 1), n, h) for a, n, h in near])
