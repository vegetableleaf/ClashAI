"""Matches whose results differ between two runs, and whether each had a changed input. python3 subset.py A B CHANGED_LIST"""
import json, os, sys
L = lambda r: {x['match']: x for x in map(json.loads, open(os.path.join(r, 'results.jsonl')))}  # noqa: E731
a, b = L(sys.argv[1]), L(sys.argv[2])
ch = set(open(sys.argv[3]).read().strip().split(','))
key = lambda r: json.dumps([r.get('counts'), r.get('first_div'), r.get('episodes'), r.get('error')], sort_keys=True)  # noqa: E731
diff = [m for m in a if key(a[m]) != key(b.get(m, {}))]
print('differ', len(diff), 'of which input changed', sum(m in ch for m in diff), '| unchanged-input matches identical',
      sum(1 for m in a if m not in ch and key(a[m]) == key(b.get(m, {}))), '/', sum(1 for m in a if m not in ch))
