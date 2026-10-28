"""python indiff10.py A.jsonl B.jsonl -- per match, the plays of B not in A and of A not in B (inputs files, CRLF-tolerant)."""
import json, sys
load = lambda f: {r['match']: r for r in (json.loads(l) for l in open(f, encoding='utf-8') if l.strip())}  # noqa: E731
a, b = load(sys.argv[1]), load(sys.argv[2])
assert set(a) == set(b), (len(a), len(b))
key = lambda p: json.dumps(p, sort_keys=True)  # noqa: E731
same = 0
for m in sorted(a):
    ra, rb = a[m], b[m]
    pa, pb = [key(p) for p in ra['plays']], [key(p) for p in rb['plays']]
    other = {k for k in set(ra) | set(rb) if k != 'plays' and ra.get(k) != rb.get(k)}
    if pa == pb and not other:
        same += 1
        continue
    print(m, 'other keys differ:', sorted(other), '| only B:', [x for x in pb if x not in pa], '| only A:', [x for x in pa if x not in pb])
print('identical records', same, 'of', len(a))
