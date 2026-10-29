"""Decompose the lock-rate gap (SIM - live) into class mix vs within-class lock, + on-time answer distance and per-card lock.
python dec_b.py live NAME [NAME ...]"""
import json, sys
from collections import defaultdict
L = json.load(open(f'out/siege_b_{sys.argv[1]}.json'))
def cls(r): return r['cls'] if r['cls'] != 'answer_ontime' else f"answer_ontime_{r['kind']}"
def by(rs, f):
    d = defaultdict(list)
    for r in rs: d[f(r)].append(r['locked'])
    return d
lv = by(L['xbows'], cls)
nL = len(L['xbows'])
for n in sys.argv[2:]:
    S = json.load(open(f'out/siege_b_{n}.json'))
    sv = by(S['xbows'], cls); nS = len(S['xbows'])
    lr = lambda d, k: sum(d[k]) / len(d[k]) if d[k] else 0
    live = sum(L['xbows'][i]['locked'] for i in range(nL)) / nL
    sim = sum(r['locked'] for r in S['xbows']) / nS
    mixL_condS = sum(len(lv[k]) / nL * lr(sv, k) for k in lv)
    print(f'{n}: live {live:.3f} sim {sim:.3f} gap {sim-live:+.3f} | live mix x SIM within-class {mixL_condS:.3f} -> mix explains {sim-mixL_condS:+.3f}, within-class {mixL_condS-live:+.3f}')
    for nm, rs in (('live', L['xbows']), (n, S['xbows'])):
        on = [r for r in rs if r['cls'] == 'answer_ontime' and r['kind'] != 'spell']
        ds = sorted(r['dist'] for r in on)
        q = lambda p: ds[int(p * (len(ds) - 1))]
        bins = by(on, lambda r: '<3' if r['dist'] < 3 else '3-6' if r['dist'] < 6 else '>=6')
        print(f'   {nm:8s} on-time unit answers {len(on)} dist p25/50/75 {q(.25):.1f}/{q(.5):.1f}/{q(.75):.1f} | ' +
              ' '.join(f'{b}: {len(v)/len(on):.2f} lock {sum(v)/len(v):.2f}' for b, v in sorted(bins.items())))
    cl, cs = by([r for r in L['xbows'] if r['cls'] == 'answer_ontime'], lambda r: r['card']), by([r for r in S['xbows'] if r['cls'] == 'answer_ontime'], lambda r: r['card'])
    common = sorted((k for k in cl if len(cl[k]) >= 25 and len(cs.get(k, [])) >= 25), key=lambda k: -len(cl[k]))
    print('   per card on-time lock live/sim (n):', '; '.join(f'{k} {sum(cl[k])/len(cl[k]):.2f}/{sum(cs[k])/len(cs[k]):.2f} ({len(cl[k])}/{len(cs[k])})' for k in common))
