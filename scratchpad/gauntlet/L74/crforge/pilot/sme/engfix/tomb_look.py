"""ENG-FIX: dump the hero Tombstone rows (phase2 names, ents, fx, proj) of a live log over a tick range."""
import json, sys
path, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for line in open(path, 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    t = d['tick']
    if t is None or not lo <= t <= hi:
        continue
    us = [u for u in (d.get('phase2') or {}).get('units', []) if 'omb' in str(u.get('name'))]
    print(t, [(u.get('side'), u.get('name'), u.get('hp'), u.get('x'), u.get('y'), [b.get('name') if isinstance(b, dict) else b for b in u.get('buffs') or []], {k: v for k, v in u.items() if k not in ('name', 'buffs', 'side', 'hp', 'x', 'y')}) for u in us])
    for k in ('ents', 'fx', 'proj'):
        for e in d[k]:
            if any(str(e[3]).startswith(p) for p in sys.argv[4:]):
                print('   ', k, e)
