"""Diff two crforge table dirs: per table rows added / removed / changed, and per changed row the columns."""
import json, sys, os, collections
a, b, out = sys.argv[1:4]
lines, summ = [], []
tot = collections.Counter()
for f in sorted(os.listdir(b)):
    if not f.endswith('.json'):
        continue
    A = json.load(open(os.path.join(a, f))).get('rows', {}) if os.path.exists(os.path.join(a, f)) else {}
    B = json.load(open(os.path.join(b, f))).get('rows', {})
    if not isinstance(A, dict):
        continue
    add = sorted(set(B) - set(A)); rem = sorted(set(A) - set(B))
    ch = []
    for k in sorted(set(A) & set(B)):
        ca, cb = A[k].get('columns', {}), B[k].get('columns', {})
        cols = sorted(c for c in set(ca) | set(cb) if ca.get(c) != cb.get(c))
        if cols:
            ch.append((k, cols))
    summ.append('%-26s rows %4d -> %4d  added %3d removed %3d changed %3d' % (f, len(A), len(B), len(add), len(rem), len(ch)))
    tot.update(added=len(add), removed=len(rem), changed=len(ch))
    lines.append('== %s' % f)
    lines += ['  + ' + k for k in add] + ['  - ' + k for k in rem]
    for k, cols in ch:
        ca, cb = A[k]['columns'], B[k]['columns']
        lines.append('  ~ %s: %s' % (k, '; '.join('%s %s -> %s' % (c, json.dumps(ca.get(c))[:80], json.dumps(cb.get(c))[:80]) for c in cols)))
open(out, 'w').write('\n'.join(summ + ['total ' + str(dict(tot))] + lines) + '\n')
print('\n'.join(summ)); print('total', dict(tot))
