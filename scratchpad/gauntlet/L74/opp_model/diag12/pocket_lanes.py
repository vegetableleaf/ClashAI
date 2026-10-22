import sys
from collections import Counter
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import diag12 as D
PK, H = D.PK, D.H
c = Counter(); ex = []
for j in D.sim_raw(D.POS_ROOT):
    r = PK.sim_match(j)
    if r is None or r[1] is None: continue
    t_fall = r[1]; me, tf = int(j['learner_side']), D._tf(j)
    tr = j['o3_trace']; towers = {int(u): v for u, v in tr['towers'].items()}
    own_p = [u for u, v in towers.items() if v[0] == me and v[1] in (1, 2)]
    snaps = [(t, dict((int(u), h) for u, h in tw)) for t, tw, _ in tr['snaps']]
    def down_at(tt):
        hp = next((h for t, h in reversed(snaps) if t <= tt), snaps[0][1])
        return sum(hp.get(u, 0) <= 0 for u in own_p)
    lanes = set()
    for p in j['o3_pos']:
        if p[1] == me or p[0] < t_fall or not PK.troop(H.norm(p[2])): continue
        x, y = tf(p[3], p[4])
        if y >= PK.POCKET_Y and abs(x - 9) >= 2 and down_at(p[0]) == 1:
            lanes.add('L' if x < 9 else 'R')
            if len(ex) < 6: ex.append((j['seed'], p[0], p[2], round(x, 1), round(y, 1)))
    if lanes: c[''.join(sorted(lanes))] += 1
print('SIM matches with non-centre pocket deploys while exactly ONE own princess is down, by the lanes used:', dict(c))
print('examples', ex)
L = Counter()
import invlib as I
for key, m in D.live_matches().items():
    fr = m['frames']; t_fall = next((t for t, Tw, *_ in fr if any(('own', s) in m['tmax'] and Tw.get(('own', s), 0) <= 0 for s in 'LR')), None)
    if t_fall is None: continue
    lanes = {('L' if p['x'] < 9 else 'R') for p in m['opp'] if p['tick'] >= t_fall and p['y'] is not None and PK.troop(p['card'])
             and p['y'] >= PK.POCKET_Y and abs(p['x'] - 9) >= 2 and sum(('own', s) in m['tmax'] and I._tower_at(m, p['tick']).get(('own', s), 0) <= 0 for s in 'LR') == 1}
    if lanes: L[''.join(sorted(lanes))] += 1
print('Ranked matches, the same:', dict(L))
# y of opponent troop deploys on our half while ONE princess is down: rows by lane-consistency (SIM: per match, the majority lane = pocket)
from collections import defaultdict
ys = defaultdict(Counter)
for j in D.sim_raw(D.POS_ROOT):
    r = PK.sim_match(j)
    if r is None or r[1] is None: continue
    me, tf = int(j['learner_side']), D._tf(j)
    pts = [tf(p[3], p[4]) for p in j['o3_pos'] if p[1] != me and p[0] >= r[1] and PK.troop(H.norm(p[2]))]
    pts = [(x, y) for x, y in pts if y >= 16.5 and abs(x - 9) >= 2]
    if not pts: continue
    maj = Counter('L' if x < 9 else 'R' for x, y in pts).most_common(1)[0][0]
    for x, y in pts:
        ys['majority' if ('L' if x < 9 else 'R') == maj else 'minority'][y] += 1
print('SIM our-half deploys (non-centre) by y, majority lane vs the other lane:', {k: dict(sorted(v.items())) for k, v in ys.items()})
