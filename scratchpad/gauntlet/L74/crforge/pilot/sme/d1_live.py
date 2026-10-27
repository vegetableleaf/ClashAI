"""D1 'SME pilot' row from a run: unflagged matches exact apart from torn frames, and the first-true-divergence
mechanisms of the failures. python3 d1_live.py RUNDIR INPUTS.jsonl"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agg_live import mech  # noqa: E402

flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open(sys.argv[2])}
c, n, ok = collections.Counter(), 0, 0
for l in open(os.path.join(sys.argv[1], 'results.jsonl')):
    r = json.loads(l)
    if flags.get(r['match']):
        continue
    n += 1
    if 'error' in r:
        c['crforge refused the input (unsupported)'] += 1
        continue
    if r['counts'].get('div', 0) == 0 and r['missing_in_sim'] == 0:
        ok += 1
        continue
    e = r['episodes'][0]
    c[mech(e['detail'], any(e['start'] - 30 <= p[1] <= e['start'] for p in r['refused_plays']))] += 1
print('unflagged: exact apart from torn frames %d/%d' % (ok, n))
# what-if: failing unflagged matches whose every episode is one of these classes (episodes past the 12 described: no)
OWN = 'live client: own elixir down a card cost 1 frame before the sim'
SPELL = {'Lightning strike timing', 'Earthquake pulse timing', 'spell area effect timing'}
w = collections.Counter()
for l in open(os.path.join(sys.argv[1], 'results.jsonl')):
    r = json.loads(l)
    if flags.get(r['match']) or 'error' in r or not r['episodes']:
        continue
    ks = {mech(e['detail'], False) if e['detail'] else None for e in r['episodes']}
    w['only own-elixir'] += ks <= {OWN}
    w['only own-elixir or spell timing'] += ks <= {OWN} | SPELL
print('what-if (failing unflagged matches made only of):', dict(w))
for k, v in c.most_common():
    print('%4d  %s' % (v, k))
