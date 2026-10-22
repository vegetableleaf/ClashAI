import json, sys
from collections import Counter
rows = []
for f in sys.argv[1:]:
    for line in open(f):
        x = json.loads(line)
        era = 'L16' if x['match'][10:23] >= '20261019_1356' else 'pre'
        for r in x['fights']:
            if 'error' in r: continue
            r['era'] = era; rows.append(r)
def key(r):
    b = r['bad'][0] if r['bad'] else None
    if not b: return 'none'
    f = b['first']
    if f is None: return 'direct'
    when = 'setup<=10' if f['dt'] <= 10 else 'early<=40' if f['dt'] <= 40 else 'late'
    k = f['kind']
    if k.startswith('gone') and b['dt'] - f['dt'] <= 4: k = 'direct_death'
    return (k, when)
for lab in (None, 'own Skeletons', 'opp Skeletons', 'opp HogRider'):
    sel = [r for r in rows if lab is None or r['lab'] == lab]
    c = {e: Counter(key(r) for r in sel if r['era'] == e) for e in ('pre', 'L16')}
    n = {e: sum(c[e].values()) for e in c}
    print('\n==', lab or 'ALL', n)
    for k in sorted(set(c['pre']) | set(c['L16']), key=lambda k: -(c['pre'][k] + c['L16'][k]))[:14]:
        print(f"{k} | pre {c['pre'][k]/max(1,n['pre']):.3f} ({c['pre'][k]}) | L16 {c['L16'][k]/max(1,n['L16']):.3f} ({c['L16'][k]})")
