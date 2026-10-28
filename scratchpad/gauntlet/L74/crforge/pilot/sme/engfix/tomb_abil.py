"""ENG-FIX: the hero Tombstone units' phase2 ability fields and names, per frame where anything changes."""
import json, sys
path = sys.argv[1]
last = None
for line in open(path, 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    t = d['tick']
    us = tuple((u.get('side'), u.get('name'), u.get('generation'), json.dumps(u.get('ability'), sort_keys=True),
                tuple(b.get('name') if isinstance(b, dict) else str(b) for b in u.get('buffs') or []))
               for u in (d.get('phase2') or {}).get('units', []) if str(u.get('name', '')).startswith('TombstoneHero') and 'Skeleton' not in str(u.get('name')))
    if us != last:
        print(t, us)
        last = us
