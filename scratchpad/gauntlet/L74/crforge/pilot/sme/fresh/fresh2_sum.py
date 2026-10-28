import json, sys, collections
from math import comb
R = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[1])}
I = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[2])}
TRIAL = {'075349', '075553', '075911', '080427', '080947', '081253', '081813', '082325', '082643', '083011'}
pl = collections.Counter(); missed = []
for m, r in R.items():
    p = r.get('plants') or {}
    for k in ('plants', 'caught'):
        if isinstance(p.get(k), int): pl[k] += p[k]
    if p.get('missed'): missed.append((m, p['missed'][:3]))
print('plants', dict(pl), 'missed', missed)
def cp(k, n, a=0.05):
    if k == 0: return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        t = sum(comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(k, n + 1))
        lo, hi = (mid, hi) if t < a else (lo, mid)
    return lo
for lab, sel in (('all', lambda m: True), ('never scored before (not READER-TORN trial)', lambda m: m[19:25] not in TRIAL),
                 ('trial subset', lambda m: m[19:25] in TRIAL)):
    unf = [m for m in R if not I[m]['flags'] and sel(m)]
    ok = [m for m in unf if R[m]['counts'].get('div', 0) == 0 and R[m].get('missing_in_sim', 0) == 0]
    st = [m for m in ok if set(R[m]['counts']) == {'exact'}]
    print(f'{lab}: unflagged {len(unf)} pass {len(ok)} (CP95 {cp(len(ok), len(unf)):.3f}) strict {len(st)} (CP95 {cp(len(st), len(unf)):.3f})')
print('first-divergence census (unflagged failures):')
for m in sorted(R):
    r = R[m]
    if I[m]['flags'] or (r['counts'].get('div', 0) == 0 and r.get('missing_in_sim', 0) == 0): continue
    print(' ', m[10:], 'first_div', r['first_div'], 'div frames', r['counts'].get('div'), json.dumps(r.get('first_detail'))[:300])
