"""Summarise order_census output: per frame class, each subsystem's state (0 = all objects at sim t, 1 = all at t+1,
m = mixed, x = some at neither), and for every subsystem pair the frames where A shows 1 while B shows 0 (A updated, B
not yet). A step order A before B allows (A1, B0) and forbids (A0, B1). python3 order_sum.py ORDER.jsonl [CLASS,...]"""
import collections, itertools, json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if '"error"' not in l]
keep = set(sys.argv[2].split(',')) if len(sys.argv) > 2 else None
S = ['el', 'mv', 'dec', 'dmg', 'del', 'new', 'pmv', 'pdel', 'pnew', 'anew', 'adel']


def state(c):
    if not c:
        return None
    if c.get('x'):
        return 'x'
    if c.get('c'):
        return 'c'
    k = [s for s in ('0', '1') if c.get(s)]
    return k[0] if len(k) == 1 else 'm'


per = collections.defaultdict(collections.Counter)
pair = collections.Counter()
frames = []
for r in rows:
    if keep and r['cls'] not in keep:
        continue
    st = {s: state(r['f'].get(s)) for s in S}
    frames.append((r['match'][10:], r['t'], r['cls'], st))
    for s in S:
        if st[s] is not None:
            per[(r['cls'], s)][st[s]] += 1
    for a, b in itertools.permutations(S, 2):
        if st[a] == '1' and st[b] == '0':
            pair[(a, b)] += 1
print('frames', len(frames), collections.Counter(f[2] for f in frames))
for (c, s), v in sorted(per.items()):
    print('%-10s %-5s %s' % (c, s, dict(v)))
print('pairs (A=1, B=0) | (B=1, A=0):')
for a, b in itertools.combinations(S, 2):
    x, y = pair[(a, b)], pair[(b, a)]
    if x or y:
        print('  %-5s %-5s %4d | %4d' % (a, b, x, y))
