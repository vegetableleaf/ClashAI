"""F635: compare two RowDiff outputs (A = 16.402.22, B = 16.635.3). A status is OK (built, maybe with deferred
"unmodelled" lists that refuse at use) or the exception. Prints the rows whose status differs, grouped."""
import sys, collections
def load(p):
    d = {}
    for line in open(p, encoding='utf-8'):
        k, n, s = line.rstrip('\n').split('\t', 2)
        d[(k, n)] = s
    return d
clean = lambda s: s == 'OK'
A, B = load(sys.argv[1]), load(sys.argv[2])
groups = collections.defaultdict(list)
for key in sorted(set(A) | set(B)):
    a, b = A.get(key), B.get(key)
    if a == b: continue
    if a is None: groups['new in B, ' + ('clean' if clean(b) else 'refused or deferred')].append((key, b))
    elif b is None: groups['removed in B'].append((key, a))
    elif clean(a): groups['clean on A, refused or deferred on B'].append((key, b))
    elif clean(b): groups['refused or deferred on A, clean on B'].append((key, a))
    else: groups['status differs, neither clean'].append((key, a + '  ||  ' + b))
print('A rows', len(A), 'clean', sum(map(clean, A.values())), '| B rows', len(B), 'clean', sum(map(clean, B.values())))
for g, items in groups.items():
    print('\n== %s: %d' % (g, len(items)))
    for (k, n), s in items: print('  %-24s %-48s %s' % (k, n, s[:260]))
