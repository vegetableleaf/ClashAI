"""Per-match identity of two runs (counts, first divergence, episodes). python3 same.py RUN_A RUN_B"""
import json, os, sys
L = lambda r: {x['match']: x for x in map(json.loads, open(os.path.join(r, 'results.jsonl')))}  # noqa: E731
a, b = L(sys.argv[1]), L(sys.argv[2])
key = lambda r: json.dumps([r.get('counts'), r.get('first_div'), r.get('episodes'), r.get('error')], sort_keys=True)  # noqa: E731
diff = [m for m in a if m not in b or key(a[m]) != key(b[m])]
print('matches %d / %d, identical %d, differ %d %s' % (len(a), len(b), len(a) - len(diff), len(diff), diff[:10]))
