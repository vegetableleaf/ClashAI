import sys
from collections import Counter
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import diag12 as D
PK, H = D.PK, D.H
def cls(k):
    c = H.cost(k) or 0
    return 'tank' if k in D.TANKS or k in ('mega_knight',) else ('c<=3' if c <= 3 else 'c4+')
# live: pocket deploys after our first princess fell
lv, n_l = Counter(), 0
for key, m in D.live_matches().items():
    fr = m['frames']; t_fall = None
    for t, Tw, *_ in fr:
        if any(('own', s) in m['tmax'] and Tw.get(('own', s), 0) <= 0 for s in 'LR'):
            t_fall = t; break
    if t_fall is None: continue
    for p in m['opp']:
        if p['tick'] >= t_fall and p['y'] is not None and PK.troop(p['card']) and p['y'] >= PK.POCKET_Y:
            lv[cls(p['card'])] += 1; lv['el'] += H.cost(p['card']) or 0; lv[('c', p['card'])] += 1; n_l += 1
sv, n_s = Counter(), 0
for j in D.sim_raw(D.POS_ROOT):
    r = PK.sim_match(j)
    if r is None or r[1] is None: continue
    me, tf = int(j['learner_side']), D._tf(j)
    for p in j['o3_pos']:
        if p[1] != me and p[0] >= r[1]:
            k = H.norm(p[2]); x, y = tf(p[3], p[4])
            if PK.troop(k) and y >= PK.POCKET_Y:
                sv[cls(k)] += 1; sv['el'] += H.cost(k) or 0; sv[('c', k)] += 1; n_s += 1
for nm, c, n in (('Ranked', lv, n_l), ('SIM-pos', sv, n_s)):
    print(nm, 'pocket deploys', n, 'mean elixir', round(c['el'] / max(1, n), 2), ' '.join(f'{k} {100*c[k]/max(1,n):.0f}%' for k in ('tank', 'c<=3', 'c4+')))
    print('   top', ' '.join(f'{k[1]} {v}' for k, v in sorted(((k, v) for k, v in c.items() if isinstance(k, tuple)), key=lambda x: -x[1])[:10]))
