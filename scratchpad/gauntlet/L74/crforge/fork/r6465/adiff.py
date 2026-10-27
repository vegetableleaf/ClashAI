"""Diff actions.json (actions dict + references list) between two table dirs."""
import json, sys, os
a, b = [json.load(open(os.path.join(d, 'actions.json'))) for d in sys.argv[1:3]]
A, B = a['actions'], b['actions']
print('actions', len(A), '->', len(B), 'added', sorted(set(B) - set(A)), 'removed', sorted(set(A) - set(B)))
for k in sorted(set(A) & set(B)):
    if A[k] != B[k]:
        fa, fb = A[k].get('fields', {}), B[k].get('fields', {})
        cols = sorted(c for c in set(fa) | set(fb) if fa.get(c) != fb.get(c))
        print('  ~', k, '; '.join('%s %s -> %s' % (c, json.dumps(fa.get(c))[:100], json.dumps(fb.get(c))[:100]) for c in cols) or 'non-field change')
ra, rb = [json.dumps(x, sort_keys=True) for x in a['references']], [json.dumps(x, sort_keys=True) for x in b['references']]
print('references', len(ra), '->', len(rb), 'added', len(set(rb) - set(ra)), 'removed', len(set(ra) - set(rb)))
for x in sorted(set(rb) - set(ra))[:40]: print('  +ref', x[:200])
for x in sorted(set(ra) - set(rb))[:40]: print('  -ref', x[:200])
