"""python ab10.py LIVE_LOG T0 T1 SIDE -- the phase-2 ability state and buffs of SIDE's Ice Wizard units in [T0, T1]."""
import json, sys
f, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
for l in open(f, 'rb'):
    if b'"frame"' not in l[:30]:
        continue
    j = json.loads(l)
    if t0 <= j['tick'] <= t1:
        for u in (j.get('phase2') or {}).get('units', []):
            if 'IceWizard' in u['name'] and u['side'] == int(sys.argv[4]):
                print(j['tick'], u['generation'], u['name'], json.dumps(u.get('ability'))[:300], [b['name'] for b in u['buffs']])
