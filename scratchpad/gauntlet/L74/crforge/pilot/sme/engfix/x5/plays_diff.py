"""ENG-FIX5: per match, plays only in A / only in B (kind, card, tick, source). python plays_diff.py A.jsonl B.jsonl"""
import json, sys
a = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[1])}
b = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[2])}
for m in sorted(set(a) & set(b)):
    k = lambda p: json.dumps(p, sort_keys=True)
    pa, pb = {k(p) for p in a[m]['plays']}, {k(p) for p in b[m]['plays']}
    ra, rb = dict(a[m], plays=None), dict(b[m], plays=None)
    print(m[10:], 'only A', [(p['kind'], p.get('card'), p['tick'], p.get('source')) for p in map(json.loads, pa - pb)],
          'only B', [(p['kind'], p.get('card'), p['tick']) for p in map(json.loads, pb - pa)], 'other fields equal', ra == rb)
