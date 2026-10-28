"""SME-FRESH evidence (010824): raw reader ents near our Tesla (7000, 14000), projectiles near it, phase-2 buffs.
python -I rows_near_tesla.py LIVE.jsonl LO HI"""
import json, sys
path, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for line in open(path, 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line); t = d['tick']
    if t is None or not (lo <= t <= hi):
        continue
    ents = [e[:7] for e in d['ents'] if e[1] is not None and abs(e[1] - 7000) + abs(e[2] - 14000) < 6000 or e[3] in (26000085, 26000086)]
    pr = [p[:6] + [p[8]] for p in d['proj'] if abs(p[1] - 7000) + abs(p[2] - 16000) < 9000]
    bu = [(u.get('name'), u.get('side'), [b.get('name') for b in u.get('buffs') or [] if isinstance(b, dict)])
          for u in (d.get('phase2') or {}).get('units', []) if u.get('buffs')]
    print(t, 'E', ents, 'P', pr, 'B', bu)
