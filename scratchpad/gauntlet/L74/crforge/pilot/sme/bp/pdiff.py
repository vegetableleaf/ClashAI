"""Ability/play differences between two inputs files. python -I pdiff.py A B [CARD]"""
import json, sys
A = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[1])}
B = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[2])}
k = lambda p: (p['side'], p['kind'], p['card'], p['tick'], tuple(p['run_ticks']), p.get('source'), p.get('dated'))  # noqa: E731
for m in A:
    a, b = {k(p) for p in A[m]['plays']}, {k(p) for p in B[m]['plays']}
    if a != b:
        print(m, 'only A', sorted(a - b, key=lambda x: x[3]), '| only B', sorted(b - a, key=lambda x: x[3]))
