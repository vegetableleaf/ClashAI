import sys, math, statistics as st
from collections import Counter
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import diag12 as D
import invlib as I
H = D.H
AIR = {'minions','minion_horde','bats','mega_minion','baby_dragon','inferno_dragon','balloon','lava_hound','skeleton_dragons',
       'electro_dragon','phoenix','flying_machine','skeleton_balloon','goblin_drill'}
def first_troop(ans):
    for k, d, dt in ans:
        if H.kind(k) != 'spell': return k, d, dt
    return None
out = {}
# live: answers with distance + time from the X-Bow (tick of the X-Bow = confirm tick)
L = []
for key, m in D.live_matches().items():
    for r in I.xbow_rows(m):
        if 'lock' not in r or r['type'] != 'bridge' or D.PK.state(r['our_cr'], r['their_cr']) != '0-0': continue
        f0 = r['end_tick'] - r['life_s'] / I.TICK_S
        ans = [(p['card'], math.hypot(p['x'] - r['x'], p['y'] - r['y']), (p['tick'] - r['tick']) / 20) for p in m['opp']
               if p['x'] is not None and f0 - 20 <= p['tick'] <= r['end_tick'] + 10 and math.hypot(p['x'] - r['x'], p['y'] - r['y']) <= 7]
        L.append((first_troop(ans), r['lock']))
S = []
for j in D.sim_raw(D.POS_ROOT):
    xs = D.sim_xbows(j)
    if not xs: continue
    me, tf = int(j['learner_side']), D._tf(j)
    opp = [(p[0], H.norm(p[2]), *tf(p[3], p[4])) for p in j['o3_pos'] if p[1] != me]
    deps = [(p[0], *tf(p[3], p[4])) for p in j['o3_pos'] if p[1] == me and p[2] == 'Xbow']
    for x in xs:
        if x['type'] != 'bridge' or x['state'] != '0-0': continue
        t = next((t for t, X, Y in deps if abs(X - x['x']) < 1e-6 and abs(Y - x['y']) < 1e-6), None)
        if t is None: continue
        ans = [(k, math.hypot(px - x['x'], py - x['y']), (tt - t) / 20) for tt, k, px, py in opp
               if t - 20 <= tt <= t + x['life_s'] * 20 + 10 and math.hypot(px - x['x'], py - x['y']) <= 7]
        S.append((first_troop(ans), x['lock_reach']))
for nm, R in (('Ranked', L), ('SIM', S)):
    a = [(f, l) for f, l in R if f]
    air = [(f, l) for f, l in a if f[0] in AIR]; gr = [(f, l) for f, l in a if f[0] not in AIR]
    print(f'{nm:6s} bridge 0-0 n {len(R)} with a troop answer {len(a)}: AIR first {100*len(air)/len(a):.0f}% (lock {100*sum(l for _, l in air)/max(1,len(air)):.0f}%) '
          f'GROUND first {100*len(gr)/len(a):.0f}% (lock {100*sum(l for _, l in gr)/max(1,len(gr)):.0f}%) | first troop answer: distance median {st.median(f[1] for f, _ in a):.1f} tiles, '
          f'time median {st.median(f[2] for f, _ in a):+.1f} s, within 3.5 s {100*sum(f[2] <= 3.5 for f, _ in a)/len(a):.0f}%')
    for lab, g in (('<= 3.5 s', lambda f: f[2] <= 3.5), ('> 3.5 s', lambda f: f[2] > 3.5)):
        z = [(f, l) for f, l in gr if g(f)]
        print(f'        ground first answer {lab}: n {len(z)} lock {100*sum(l for _, l in z)/max(1,len(z)):.0f}%  dist median {st.median(f[1] for f, _ in z) if z else float("nan"):.1f}')
