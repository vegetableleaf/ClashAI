"""ENG-FIX5 re-tally of r9 (SME_ZD_BLDG): OFF vs ON inputs of every set (all records), then the pod results of the
changed records. python -I my_tally.py"""
import json
from pathlib import Path
D = Path(__file__).resolve().parent
changed = []
for s in ('dev', 'fresh1', 'fresh2', 'fresh3', 'fresh4', 'fresh5', 'fresh6'):
    a = {json.loads(l)['match']: l for l in open(D / ('%s_off_all.jsonl' % s))}
    b = {json.loads(l)['match']: l for l in open(D / ('%s_on_all.jsonl' % s))}
    ch = sorted(m for m in a if a[m] != b.get(m))
    print(s, 'records', len(a), len(b), 'changed', ch)
    for m in ch:
        ra, rb = json.loads(a[m]), json.loads(b[m])
        keys = sorted(k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k))
        print('   ', m, 'fields', keys, 'zap_dead', rb.get('zap_dead'))
    changed += ch
res = {}
for mode in ('off', 'on'):
    for l in open(D / ('EF9_fresh4_%s_results.jsonl' % mode)):
        x = json.loads(l)
        res[(x['match'], mode)] = (x['flags'], x['counts'], x['first_div'], x['plants']['missed'])
for m in changed:
    print(m, 'OFF', res.get((m, 'off')), 'ON', res.get((m, 'on')))
