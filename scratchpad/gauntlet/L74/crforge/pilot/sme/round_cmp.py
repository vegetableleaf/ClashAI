"""Round table row: python3 round_cmp.py INPUTS.jsonl BEFORE_RUN AFTER_RUN
Unflagged matches (the 109) exact apart from torn frames (before -> after), regressions (exact before, not after), exact
frames and torn frames by class -- each on the unflagged matches and, separately, on all matches (the 138) -- the
first-true-divergence mechanisms after, and the planted-divergence suite (plant_suite.py; exit 1 on any miss).
SME-HARDEN: "exact frames" was the all-match total; it is now reported per set."""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agg_live import mech  # noqa: E402

flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open(sys.argv[1])}


def load(run):
    return {r['match']: r for r in map(json.loads, open(os.path.join(run, 'results.jsonl')))}


def exact(rs):
    return {m for m, r in rs.items() if not flags.get(m) and 'error' not in r and r['counts'].get('div', 0) == 0
            and r['missing_in_sim'] == 0}


def frames(rs, keep):
    return sum(r['counts'].get('exact', 0) for m, r in rs.items() if 'error' not in r and keep(m))


def torn(rs, keep):
    c = collections.Counter()
    for m, r in rs.items():
        if keep(m):
            for k, v in r.get('counts', {}).items():
                if k.startswith('torn'):
                    c[k] += v
    return dict(sorted(c.items()))


a, b = load(sys.argv[2]), load(sys.argv[3])
ea, eb = exact(a), exact(b)
unf = lambda m: not flags.get(m)  # noqa: E731
every = lambda m: True  # noqa: E731
n = sum(1 for m in b if unf(m))
print('unflagged (%d): exact apart from torn %d/%d -> %d/%d | regressions %s | gained %d' %
      (n, len(ea), n, len(eb), n, sorted(ea - eb) or 0, len(eb - ea)))
print('unflagged (%d): exact frames %d -> %d' % (n, frames(a, unf), frames(b, unf)))
print('all (%d): exact frames %d -> %d' % (len(b), frames(a, every), frames(b, every)))
print('torn before, unflagged:', torn(a, unf))
print('torn after,  unflagged:', torn(b, unf))
print('torn before, all:', torn(a, every))
print('torn after,  all:', torn(b, every))
c = collections.Counter()
for m, r in b.items():
    if flags.get(m) or 'error' in r or m in eb:
        continue
    e = r['episodes'][0]
    c[mech(e['detail'], any(e['start'] - 30 <= p[1] <= e['start'] for p in r['refused_plays']))] += 1
for k, v in c.most_common():
    print('%4d  %s' % (v, k))
pl = [r['plants'] for r in b.values() if 'plants' in r]
if pl:
    tot = collections.Counter()
    leg, tg = collections.Counter(), collections.Counter()
    for p in pl:
        tot.update(plants=p['plants'], caught=p['caught'], missed=len(p['missed']), window_mismatch=len(p['window_mismatch']))
        leg.update(p['legal'])
        tg.update(p['targets'])
    print('plant suite (%d matches): %s | legal %s | targets %s' % (len(pl), dict(tot), dict(leg), dict(tg)))
    for m, r in sorted(b.items()):
        for x in r.get('plants', {}).get('missed', [])[:5]:
            print('  MISSED', m, x)
    if tot['missed']:
        print('PLANT SUITE FAILED')
        sys.exit(1)
else:
    print('plant suite: not run (SME_PLANTS=0 or a pre-HARDEN run)')
