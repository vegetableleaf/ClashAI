"""Summarise rescore output: torn before/after per class (109 / 138), matches no longer exact, plant suite totals."""
import collections, json, sys

rs = [json.loads(l) for l in open(sys.argv[1])]
for name, keep in (('unflagged', lambda r: not r['flags']), ('all', lambda r: True)):
    sel = [r for r in rs if keep(r)]
    b, a = collections.Counter(), collections.Counter()
    for r in sel:
        for k, v in (r['old_counts'] or {}).items():
            b[k] += v
        for k, v in r['counts'].items():
            a[k] += v
    ex = lambda c: c.get('div', 0) == 0  # noqa: E731
    print('%s (%d): exact frames %d -> %d | div %d -> %d' % (name, len(sel), b['exact'], a['exact'], b['div'], a['div']))
    print('  torn before', dict(sorted((k, v) for k, v in b.items() if k.startswith('torn'))))
    print('  torn after ', dict(sorted((k, v) for k, v in a.items() if k.startswith('torn'))))
    lost = [r for r in sel if ex(r['old_counts'] or {'div': 1}) and not ex(r['counts'])]
    print('  no longer exact:', len(lost))
    for r in lost:
        print('   ', r['match'], r['flags'], 'first', r['first'], json.dumps(r['first_detail'])[:600])
tot, leg, tg = collections.Counter(), collections.Counter(), collections.Counter()
miss = []
for r in rs:
    p = r.get('plants')
    if not p:
        continue
    tot.update(plants=p['plants'], caught=p['caught'], missed=len(p['missed']), window_mismatch=len(p['window_mismatch']))
    leg.update(p['legal'])
    tg.update(p['targets'])
    miss += [[r['match']] + x for x in p['missed']]
print('plants', dict(tot), 'legal', dict(leg), 'targets', dict(tg))
for x in miss[:30]:
    print('  MISSED', x)
wm = [(r['match'], r['plants']['window_mismatch']) for r in rs if r.get('plants', {}).get('window_mismatch')]
print('window mismatches', wm[:10])
lc = collections.Counter((x[1], x[3].split('_')[-1], x[4], x[5]) for r in rs for x in r.get('plants', {}).get('legal_list', []))
for k, v in lc.most_common():
    print('  legal', v, k)
