"""ENG-FIX5: per raw frame in [T0, T1]: ents rows of a card id, and phase2 units whose name contains NAME (generation,
address, in-ents bit). python raw_units.py LOG T0 T1 CARD NAME"""
import json, sys
t0, t1, card, name = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
for line in open(sys.argv[1], 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    t = d['tick']
    if t is None or not t0 <= t <= t1:
        continue
    addr = {e[7]: e for e in d['ents'] if len(e) > 7}
    us = [(u['generation'], u['name'], u.get('address') in addr) for u in (d.get('phase2') or {}).get('units') or [] if name in u.get('name', '')]
    print(t, [e[:7] for e in d['ents'] if e[3] == card], us)
