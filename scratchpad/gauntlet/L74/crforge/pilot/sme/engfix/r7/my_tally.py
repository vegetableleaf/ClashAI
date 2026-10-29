# tally7.py -- ENG-FIX4: my own re-tally of r7 (A vs B = SME_BANNER_GIVEN; A vs C = SME_ZAP_DEAD) from the result files
import json, os
O = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/engfix/r7/'
rd = lambda f: {json.loads(l)['match']: json.loads(l) for l in open(O + f)} if os.path.exists(O + f) else None  # noqa: E731
clean = lambda c: all(k == 'exact' or k.startswith('torn_') for k in c)  # noqa: E731
key = lambda r: (r['counts'], r['first_div'], r['flags'], r['plants']['missed'], r['refused_plays'])  # noqa: E731
tot = {'n': 0, 'identical': 0}
for s in ('dev', 'fresh1', 'fresh2', 'fresh3', 'fresh4', 'fresh5', 'fresh6'):
    A, B, C = rd('EF7_%s_A_results.jsonl' % s), rd('EF7_%s_B_results.jsonl' % s), rd('EF7_%s_C_results.jsonl' % s)
    if not A or not B:
        print(s, 'missing A/B'); continue
    assert set(A) == set(B), s
    diff = [m for m in A if key(A[m]) != key(B[m])]
    tot['n'] += len(A); tot['identical'] += len(A) - len(diff)
    missed = [m for m in A if A[m]['plants']['missed'] or B[m]['plants']['missed']]
    print(s, 'A/B', len(A), 'identical', len(A) - len(diff), 'plants missed', missed)
    for m in diff:
        a, b = A[m], B[m]
        cls = 'fixed' if not clean(a['counts']) and clean(b['counts']) else 'regressed' if clean(a['counts']) and not clean(b['counts']) else 'other'
        print('   BANNER', m[10:], a['counts'], a['first_div'], '->', b['counts'], b['first_div'], cls, 'dExact', b['counts'].get('exact', 0) - a['counts'].get('exact', 0))
    for m, c in (C or {}).items():
        a = A[m]
        cls = 'fixed' if not clean(a['counts']) and clean(c['counts']) else 'regressed' if clean(a['counts']) and not clean(c['counts']) else 'other'
        print('   ZAP_DEAD', m[10:], a['counts'], a['first_div'], '->', c['counts'], c['first_div'], cls, 'missed', c['plants']['missed'])
print(tot)
