"""cmp_rows.py A.json B.json KEY: eval_check rows A == rows B with KEY removed from B (exit 1 and the first mismatch
otherwise) -- a measurement-only option adds KEY and changes nothing else."""
import json
import sys

a, b, key = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
assert all(key in r for r in b), f'{key} missing from some rows of {sys.argv[2]}'
b = [{k: v for k, v in r.items() if k != key} for r in b]
for x, y in zip(a, b):
    if x != y:
        print('MISMATCH', {k: (x.get(k), y.get(k)) for k in set(x) | set(y) if x.get(k) != y.get(k)})
        sys.exit(1)
sys.exit(0 if len(a) == len(b) else 1)
