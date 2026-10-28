"""SME-FRESH summary of one run: python3 fresh_summary.py INPUTS_ALL.jsonl INPUTS_RNGFREE.jsonl RUNDIR
Matches by filter, unflagged exact apart from torn, strictly exact (no torn frame either), exact frames, torn classes, the
fitter's activity (repair moves; FITNEXT = a command run after the onset was moved; ghost presses enabled), first
divergences, and the one-sided 95% Clopper-Pearson lower bounds on the pass share."""
import collections, json, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', os.path.dirname(os.path.abspath(__file__))))
allr = [json.loads(l) for l in open(sys.argv[1])]
free = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[2])}
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(sys.argv[3], 'results.jsonl'))}


def cp_lower(k, n, a=0.05):
    """one-sided exact (Clopper-Pearson) lower bound: the p with P(X >= k | n, p) = a (bisection; k = n gives a ** (1/n))"""
    if k == 0:
        return 0.0
    from math import comb
    tail = lambda p: sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))  # noqa: E731
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if tail(mid) < a else (lo, mid)
    return lo


print('matches', len(allr), '| RNG-free', len(free), '| not RNG-free', len(allr) - len(free),
      dict(collections.Counter(','.join(r['drawers']) for r in allr if not r['rng_free'])))
print('flags (all):', dict(collections.Counter(f.split(':')[1] for r in allr for f in r['flags'])),
      '| flags (RNG-free):', dict(collections.Counter(f.split(':')[1] for r in free.values() for f in r['flags'])))
unf = [m for m, r in free.items() if not r['flags']]
ok = [m for m in unf if 'error' not in res[m] and res[m]['counts'].get('div', 0) == 0 and res[m]['missing_in_sim'] == 0]
strict = [m for m in ok if set(res[m]['counts']) == {'exact'}]
print('unflagged', len(unf), '| exact apart from torn', len(ok), '| strictly exact (no torn frame)', len(strict))
print('exact frames (all RNG-free)', sum(r['counts'].get('exact', 0) for r in res.values() if 'error' not in r),
      '| frames', sum(r['frames'] for r in res.values() if 'error' not in r),
      '| unflagged exact frames', sum(res[m]['counts'].get('exact', 0) for m in unf), 'of', sum(res[m]['frames'] for m in unf))
torn = collections.Counter(); tm = collections.Counter()
for m in unf:
    for k, v in res[m]['counts'].items():
        if k.startswith('torn'):
            torn[k] += v; tm[k] += 1
print('torn frames (unflagged):', dict(torn), '| matches with each:', dict(tm))
mv = fn = gh = 0
for m in unf:
    plan = json.load(open(os.path.join(sys.argv[3], m, 'plan.json'))) if os.path.exists(os.path.join(sys.argv[3], m, 'plan.json')) else None
    for e in res[m]['repair']:
        if 'change' in e:
            mv += 1
            fn += e['change'].get('run', -1) > e['d']
    if plan:
        gh += sum(1 for c in plan.get('cmds', []) if (c.get('_src') or {}).get('ghost') and c.get('kind') != 'skip')
print('fitter moves kept (unflagged):', mv, '| of them FITNEXT (run after the onset):', fn, '| ghost presses enabled:', gh)
for m in sorted(free):
    r = res[m]
    print('  %s %-28s first_div %-5s counts %s detail %s' % (m[10:], ','.join(f.split(':')[1] for f in free[m]['flags']) or 'unflagged',
          r.get('first_div'), r.get('counts'), json.dumps(r.get('first_detail'))[:160]))
for k, n, lab in ((len(ok), len(unf), 'exact apart from torn'), (len(strict), len(unf), 'strictly exact')):
    print('95%% one-sided CP lower bound, %s: %d/%d -> %.4f' % (lab, k, n, cp_lower(k, n)))
