"""W18 DIAG_12 8.9 (W19 lead 1): pocket deploys after OUR first princess fell, live Ranked vs SIM-pos (I u40, block 741200):
spot (depth y, lane x relative to the fallen princess), timing vs our last play, CLX's first answer (latency, card), and our
KING's HP lost in the 20 s after each pocket deploy; plus the first king damage after the fall.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/diag12/pocket_timing.py"""
import sys, statistics as st
from collections import Counter
sys.path[:0]=['C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/diag12']
import diag12 as D
import invlib as I
PK, H = D.PK, D.H

def summarise(nm, recs, kfirst):
    n = len(recs)
    if not n: return
    dep = [r['y'] for r in recs]
    print(f'{nm:7s} pocket deploys {n} | depth y: median {st.median(dep):.1f}, y >= 24 (king zone) {100*sum(y >= 24 for y in dep)/n:.0f}% | '
          f'fallen lane {100*sum(r["dead_lane"] for r in recs)/n:.0f}%, centre (|x-9| < 2) {100*sum(abs(r["x"]-9) < 2 for r in recs)/n:.0f}%')
    gap = [r['since_own'] for r in recs if r['since_own'] is not None]
    rs = [r['resp'] for r in recs if r['resp'] is not None]
    print(f'        since our last play: median {st.median(gap):.1f} s | CLX answers within 3 s {100*sum(x <= 3 for x in rs)/n:.0f}%, '
          f'median {st.median(rs):.1f} s | first answer cards: ' + ' '.join(f'{k} {v}' for k, v in Counter(r['resp_card'] for r in recs if r['resp_card']).most_common(6)))
    kl = [r['king20'] for r in recs]
    print(f'        our king HP lost in the 20 s after it: mean {st.mean(kl):.3f} princess units; deploys with any king damage {100*sum(x > 0 for x in kl)/n:.0f}% '
          f'| first king damage after the fall: median {st.median(kfirst) if kfirst else float("nan"):.1f} s (n {len(kfirst)})')
    for lab, f in (('y < 24', lambda r: r['y'] < 24), ('y >= 24', lambda r: r['y'] >= 24)):
        z = [r for r in recs if f(r)]
        if z: print(f'          {lab}: n {len(z)} king HP lost 20 s {st.mean(r["king20"] for r in z):.3f}')

# live
L, KL = [], []
for key, m in D.live_matches().items():
    fr = m['frames']; t_fall = slot = None
    for t, Tw, *_ in fr:
        down = [s for s in 'LR' if ('own', s) in m['tmax'] and Tw.get(('own', s), 0) <= 0]
        if down: t_fall, slot = t, down[0]; break
    if t_fall is None: continue
    pm = m['tmax'].get(('own', 'L')) or 1
    k0 = I._tower_at(m, t_fall).get(('own', 'K'), 0)
    kd = next((t for t, Tw, *_ in fr if t > t_fall and Tw.get(('own', 'K'), 0) < k0), None)
    if kd is not None: KL.append((kd - t_fall) / 20)
    own = sorted((q['tick'], q['card']) for q in m['own'])
    for p in m['opp']:
        if p['tick'] < t_fall or p['y'] is None or not PK.troop(p['card']) or p['y'] < PK.POCKET_Y: continue
        t = p['tick']
        last = max((tt for tt, _ in own if tt <= t), default=None)
        nxt = next(((tt, c) for tt, c in own if tt > t), None)
        a, b = I._tower_at(m, t), I._tower_at(m, t + 400)
        L.append(dict(y=p['y'], x=p['x'], dead_lane=(p['x'] < 9) == (slot == 'L'), since_own=None if last is None else (t - last) / 20,
                      resp=None if nxt is None else (nxt[0] - t) / 20, resp_card=None if nxt is None else nxt[1],
                      king20=max(0, a.get(('own', 'K'), 0) - b.get(('own', 'K'), 0)) / pm))
# SIM-pos
S, KS = [], []
for j in D.sim_raw(D.POS_ROOT):
    r = PK.sim_match(j)
    if r is None or r[1] is None: continue
    t_fall = r[1]
    me, tf = int(j['learner_side']), D._tf(j)
    tr = j['o3_trace']; towers = {int(u): v for u, v in tr['towers'].items()}
    king = next(u for u, v in towers.items() if v[0] == me and v[1] == 0)
    pm = next(v[2] for v in towers.values() if v[1] in (1, 2))
    snaps = [(t, dict((int(u), h) for u, h in tw)) for t, tw, _ in tr['snaps']]
    hp_at = lambda tt: next((hp for t, hp in reversed(snaps) if t <= tt), snaps[0][1])
    k0 = hp_at(t_fall).get(king, 0)
    kd = next((t for t, hp in snaps if t > t_fall and hp.get(king, 0) < k0), None)
    if kd is not None: KS.append((kd - t_fall) / 20)
    # the fallen princess lane in our frame: the first own princess down
    own_p = [u for u, v in towers.items() if v[0] == me and v[1] in (1, 2)]
    fallen = next((u for u in own_p if hp_at(t_fall).get(u, 0) <= 0), None)
    lanes = D.slot_lane()
    dead_L = fallen is not None and lanes[(1 - me, towers[fallen][1])] == 'R'   # our own slot seen from the other side, rotated into our frame: L <-> R
    own = sorted((int(t), H.norm(c)) for t, c in j['o3_plays']['learner'])
    for p in j['o3_pos']:
        if p[1] == me or p[0] < t_fall: continue
        k = H.norm(p[2]); x, y = tf(p[3], p[4])
        if not PK.troop(k) or y < PK.POCKET_Y: continue
        t = p[0]
        last = max((tt for tt, _ in own if tt <= t), default=None)
        nxt = next(((tt, c) for tt, c in own if tt > t), None)
        S.append(dict(y=y, x=x, dead_lane=(x < 9) == dead_L, since_own=None if last is None else (t - last) / 20,
                      resp=None if nxt is None else (nxt[0] - t) / 20, resp_card=None if nxt is None else nxt[1],
                      king20=max(0, hp_at(t).get(king, 0) - hp_at(t + 400).get(king, 0)) / pm))
summarise('Ranked', L, KL)
summarise('SIM-pos', S, KS)
