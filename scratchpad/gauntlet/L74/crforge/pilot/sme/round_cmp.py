"""Round table row: python3 round_cmp.py INPUTS.jsonl BEFORE_RUN AFTER_RUN
Unflagged matches exact apart from torn frames (before -> after), exact frames, regressions (exact before, not after),
torn frames by class, and the first-true-divergence mechanisms after."""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agg_live import mech  # noqa: E402

flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open(sys.argv[1])}


def load(run):
    return {r['match']: r for r in map(json.loads, open(os.path.join(run, 'results.jsonl')))}


def exact(rs):
    return {m for m, r in rs.items() if not flags.get(m) and 'error' not in r and r['counts'].get('div', 0) == 0
            and r['missing_in_sim'] == 0}


a, b = load(sys.argv[2]), load(sys.argv[3])
ea, eb = exact(a), exact(b)
fr = lambda rs: sum(r['counts'].get('exact', 0) for r in rs.values() if 'error' not in r)  # noqa: E731
torn = collections.Counter()
for r in b.values():
    for k, v in r.get('counts', {}).items():
        if k.startswith('torn'):
            torn[k] += v
c = collections.Counter()
for m, r in b.items():
    if flags.get(m) or 'error' in r or m in eb:
        continue
    e = r['episodes'][0]
    c[mech(e['detail'], any(e['start'] - 30 <= p[1] <= e['start'] for p in r['refused_plays']))] += 1
n = sum(1 for m in b if not flags.get(m))
print('exact apart from torn: %d/%d -> %d/%d | exact frames %d -> %d | regressions %s | gained %d' %
      (len(ea), n, len(eb), n, fr(a), fr(b), sorted(ea - eb) or 0, len(eb - ea)))
print('torn frames after:', dict(torn))
for k, v in c.most_common():
    print('%4d  %s' % (v, k))
