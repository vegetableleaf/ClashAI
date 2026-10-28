"""ENG-FIX: reader ents rows of the hero Tombstone card ids (any id whose phase2 name starts TombstoneHero) per frame."""
import json, sys
path, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for line in open(path, 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    t = d['tick']
    if t is None or not lo <= t <= hi:
        continue
    names = {u.get('address'): u.get('name') for u in (d.get('phase2') or {}).get('units', [])}
    rows = [(e[3], e[4], e[5], e[6], e[1], e[2], e[0], names.get(e[7])) for e in d['ents'] if 'TombstoneHero' in str(names.get(e[7])) and 'Skeleton' not in str(names.get(e[7]))]
    print(t, rows)
