"""ENG-FIX5: a gate run's per-match lines and totals (exact apart from torn / strict, unflagged), with the one-sided 95%
Clopper-Pearson lower bound. python3 gate_sum.py RESULTS.jsonl [POOL_PASS POOL_N]"""
import json, sys
from math import comb


def cp_lower(k, n, a=0.05):
    if k == 0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(60):  # P(X >= k | p) = a
        p = (lo + hi) / 2
        tail = sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
        lo, hi = (p, hi) if tail < a else (lo, p)
    return lo


rows = [json.loads(l) for l in open(sys.argv[1])]
torn_ok = strict = n = 0
for x in sorted(rows, key=lambda x: x['match']):
    c = x['counts']
    bad = {k: v for k, v in c.items() if k != 'exact'}
    if x['flags']:
        print(x['match'][10:], 'FLAGGED', x['flags'], c); continue
    n += 1
    a = 'div' not in bad
    s = not bad
    torn_ok += a; strict += s
    print(x['match'][10:], 'PASS' if a else 'FAIL', 'strict' if s else '', c, 'first_div', x['first_div'],
          'missed', x['plants']['missed'], str(x['first_detail'])[:150] if not a else '')
print('unflagged %d: exact apart from torn %d (CP lower %.3f), strict %d (CP lower %.3f); plants missed %d' % (
    n, torn_ok, cp_lower(torn_ok, n), strict, cp_lower(strict, n), sum(len(x['plants']['missed']) for x in rows)))
if len(sys.argv) > 3:
    k, m = int(sys.argv[2]) + torn_ok, int(sys.argv[3]) + n
    print('pooled %d / %d = %.3f (CP lower %.3f)' % (k, m, k / m, cp_lower(k, m)))
