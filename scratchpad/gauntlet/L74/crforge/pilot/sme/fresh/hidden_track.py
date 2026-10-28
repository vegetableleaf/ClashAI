"""SME-FRESH evidence: raw reader rows of one card id over [LO, HI] and every projectile whose target address is that
body's. python -I hidden_track.py LIVE.jsonl LO HI CARD_ID"""
import json, sys
path, lo, hi, cid = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
addr = None
for line in open(path, 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line); t = d['tick']
    if t is None or not (lo <= t <= hi):
        continue
    for e in d['ents']:
        if e[3] == cid:
            addr = e[7]
            print(t, 'ENT', e)
    tp = [p for p in d['proj'] if addr is not None and len(p) > 9 and p[9] == addr]
    pu = [(u.get('name'), u.get('side'), u.get('x'), u.get('y'), u.get('hp')) for u in (d.get('phase2') or {}).get('units', [])
          if 'Pekka' in str(u.get('name'))]
    if tp or pu:
        print(t, 'PROJ->addr', tp[:3], 'P2', pu[:3])
print('addr', addr)
