"""Buff rows and ability field of units with a given name in a raw live log. python -I unitbuf.py LOG NAME LO HI"""
import json, sys
name, lo, hi = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
seen = set()
for line in open(sys.argv[1], 'rb'):
    if b'"frame"' not in line[:40] or name.encode() not in line:
        continue
    d = json.loads(line)
    t = d['tick']
    if t is None or not lo <= t <= hi or t in seen:
        continue
    seen.add(t)
    for u in (d.get('phase2') or {}).get('units', []):
        if name in (u.get('name') or ''):
            print(t, u['generation'], u['side'], [(b['name'], b['remaining_ms_raw'], b['duration_ms_raw']) for b in u.get('buffs') or []], u.get('ability'))
