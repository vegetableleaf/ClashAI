import sys, math
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import xbow_window as W
D, H = W.D, W.H
# re-extract with the blocker's distance and card for the inside-window case
def first_blk(t_x, xy, opp):
    b = [((t - t_x) / 20, k, math.hypot(x - xy[0], y - xy[1]), y) for t, k, x, y in opp
         if W.ground(k) and -20 <= t - t_x <= 200 and math.hypot(x - xy[0], y - xy[1]) <= W.RANGE]
    return min(b) if b else None
import invlib as I
L, S = [], []
for key, m in D.live_matches().items():
    opp = [(p['tick'], p['card'], p['x'], p['y']) for p in m['opp'] if p['x'] is not None]
    for r in I.xbow_rows(m):
        if 'lock' not in r or r['type'] != 'bridge' or W.PK.state(r['our_cr'], r['their_cr']) != '0-0': continue
        f = first_blk(r['tick'], (r['x'], r['y']), opp)
        if f and f[0] <= W.WIN: L.append((f, r['lock'], r['y']))
for j in D.sim_raw(D.POS_ROOT):
    xs = D.sim_xbows(j)
    if not xs: continue
    me, tf = int(j['learner_side']), D._tf(j)
    opp = [(p[0], p[2], *tf(p[3], p[4])) for p in j['o3_pos'] if p[1] != me]
    deps = [(p[0], *tf(p[3], p[4])) for p in j['o3_pos'] if p[1] == me and p[2] == 'Xbow']
    for x in xs:
        if x['type'] != 'bridge' or x['state'] != '0-0': continue
        t = next((t for t, X, Y in deps if abs(X - x['x']) < 1e-6 and abs(Y - x['y']) < 1e-6), None)
        f = first_blk(t, (x['x'], x['y']), opp) if t is not None else None
        if f and f[0] <= W.WIN: S.append((f, x['lock_reach'], x['y']))
def tank(k): return H.norm(k) in D.TANKS or H.norm(k) in ('mega_knight', 'golem', 'giant_skeleton')
for nm, R in (('Ranked', L), ('SIM', S)):
    print(nm, 'inside-window blockers', len(R))
    for lab, f in (('dist <= 4', lambda b: b[2] <= 4), ('4 - 8', lambda b: 4 < b[2] <= 8), ('8 - 11.5', lambda b: b[2] > 8)):
        z = [(b, l) for b, l, _ in R if f(b)]
        print(f'   {lab:9s} share {100*len(z)/len(R):4.1f}% lock {100*sum(l for _, l in z)/max(1,len(z)):4.1f}')
    for lab, f in (('tank', lambda b: tank(b[1])), ('building', lambda b: H.kind(H.norm(b[1])) == 'building'), ('other ground', lambda b: not tank(b[1]) and H.kind(H.norm(b[1])) != 'building')):
        z = [(b, l) for b, l, _ in R if f(b)]
        print(f'   {lab:12s} share {100*len(z)/len(R):4.1f}% lock {100*sum(l for _, l in z)/max(1,len(z)):4.1f}')
    for lab, f in (('t <= 1.5 s', lambda b: b[0] <= 1.5), ('1.5 - 3.5 s', lambda b: b[0] > 1.5)):
        z = [(b, l) for b, l, _ in R if f(b)]
        print(f'   {lab:12s} share {100*len(z)/len(R):4.1f}% lock {100*sum(l for _, l in z)/max(1,len(z)):4.1f}')
    # blocker on THEIR side of the river (between our X-Bow and their tower) vs on ours
    for lab, f in (('blocker y < 16 (their half)', lambda b: b[3] < 16), ('y >= 16 (river / our half)', lambda b: b[3] >= 16)):
        z = [(b, l) for b, l, _ in R if f(b)]
        print(f'   {lab:28s} share {100*len(z)/len(R):4.1f}% lock {100*sum(l for _, l in z)/max(1,len(z)):4.1f}')
