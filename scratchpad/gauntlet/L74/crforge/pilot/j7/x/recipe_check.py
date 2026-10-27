"""A2b-2b recipe check on the pod: crforge gate-mode refusals by tier and source over runs_x (deck8 log-only should be ~0
NOT_IN_HAND: the deal fits), plus one log-only deck8 record's plan in full."""
import json, glob, os, sys
from collections import Counter, defaultdict
inp = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[1])}
agg = defaultdict(Counter)
ex = None
for p in glob.glob('runs_x/crforge_gate_lo/*.json'):
    m = os.path.basename(p)[:-5]; r = inp[m]; d = json.load(open(p))
    cyc = r['own_cycle_fail'] is None and r['opp_fitting_deals'] > 0
    deck8 = cyc and not any(':deck_seen:' in f for f in r['flags'])
    tier = 'deck8' if deck8 else 'cycle_ok' if cyc else 'any'
    src = 'api' if r.get('source') != 'live_only' else 'log'
    k = (tier, src)
    agg[k]['matches'] += 1; agg[k]['plays'] += d['plays_n']
    for why, n in d['refused'].items():
        agg[k][why] += n
    if deck8 and src == 'log' and ex is None and len(r['plays']) > 60:
        ex = m
for k in sorted(agg):
    print(k, dict(agg[k]))
pl = json.load(open('plans_x/%s.json' % ex))
print('example', ex, {k: v for k, v in pl.items() if k != 'cmds'})
print('first cmds', pl['cmds'][:3])
d = json.load(open('runs_x/crforge_gate_lo/%s.json' % ex)); d.pop('rows')
print('crforge gate run', d)
