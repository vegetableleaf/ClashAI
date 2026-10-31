"""cycle-fit census on an inputs file: python cyc4.py INPUTS.jsonl RESULTS(.jsonl|.gz) OUT.json"""
import json, sys, itertools, gzip, collections

def fits(seq):
    for hand in itertools.combinations(range(8), 4):
        rest = [i for i in range(8) if i not in hand]
        for q in itertools.permutations(rest):
            h, qu, ok = set(hand), list(q), True
            for d in seq:
                if d not in h:
                    ok = False; break
                h.remove(d); qu.append(d); h.add(qu.pop(0))
            if ok:
                return True
    return False

def prefix_ok(seq):
    """longest fitting prefix length"""
    lo, hi = 0, len(seq)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(seq[:mid]): lo = mid
        else: hi = mid - 1
    return lo

def opn(p): return gzip.open(p, 'rt') if p.endswith('.gz') else open(p)
recs = [json.loads(l) for l in open(sys.argv[1])]
res = {}
for l in opn(sys.argv[2]):
    r = json.loads(l); res[r['match']] = r
out = []
for r in recs:
    opp = 1 - r['my_side']
    pl = sorted((p for p in r['plays'] if p['side'] == opp and p['kind'] == 'play'), key=lambda p: p['tick'])
    seq = [p['deck_index'] for p in pl]
    fl = any('opp_no_fitting' in f for f in r['flags'])
    k = prefix_ok(seq)
    row = dict(match=r['match'], n=len(seq), flag=fl, fits=k == len(seq), longest=k,
               fail_tick=pl[k]['tick'] if k < len(seq) else None, fail_card=pl[k]['card'] if k < len(seq) else None)
    x = res.get(r['match'], {})
    row['first_div'] = x.get('first_div'); row['counts'] = x.get('counts'); row['res_flags'] = x.get('flags')
    out.append(row)
json.dump(out, open(sys.argv[3], 'w'))
nf = [o for o in out if not o['fits']]
print(len(out), 'records;', len(nf), 'not fitting;', sum(o['flag'] for o in out), 'flagged;', sum(o['fits'] and o['flag'] for o in out), 'flagged but fit')
early = [o for o in nf if o['first_div'] is not None and o['fail_tick'] - o['first_div'] > 100]
print('not fitting with first_div > 100 ticks before the cycle failure:', len(early))
for o in nf:
    print(o['match'][-13:], 'n', o['n'], 'longest', o['longest'], 'fail_tick', o['fail_tick'], o['fail_card'], 'first_div', o['first_div'], o['counts'])
