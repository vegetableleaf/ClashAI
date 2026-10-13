"""Is the own-troop divergence a pure timing offset? For each forward-walking own troop find the time shift tau
(sim delayed by tau) minimising 2-D position error vs live; report best tau and the residual pathing error."""
import glob, json, sys, statistics as st
from collections import defaultdict
TILE, TICK = 1000.0, 0.05
src = sys.argv[1]
res = defaultdict(lambda: dict(tau=[], r0=[], rbest=[], lat=[]))

def interp(pts, a):
    if a < pts[0][0] or a > pts[-1][0]: return None
    for (a0, x0, y0), (a1, x1, y1) in zip(pts, pts[1:]):
        if a0 <= a <= a1:
            w = 0 if a1 == a0 else (a - a0) / (a1 - a0)
            return x0 + w * (x1 - x0), y0 + w * (y1 - y0)
    return pts[-1][1], pts[-1][2]

for path in sorted(glob.glob(src + '/*.json')):
    d = json.load(open(path))
    taps = [c for c in d.get('commands', []) if c.get('source') == 'confirmed_own_tap']
    if not taps: continue
    own = taps[0]['side']; f = 1.0 if own == 0 else -1.0
    names = {c['card_id']: c['name'] for c in taps}
    seen = defaultdict(list)
    for s in d['samples']:
        for r in s.get('rows', []):
            if r.get('tower') or r.get('side') != own or not r.get('live') or not r.get('sim'): continue
            seen[r['identity']].append((s['tick'], r['card_id'], r['live'], r['sim']))
    for rows in seen.values():
        rows.sort(key=lambda t: t[0]); t0, cid = rows[0][0], rows[0][1]
        card = names.get(cid)
        if card not in ('Knight', 'Skeletons', 'IceWizard'): continue
        prior = [c for c in taps if c['card_id'] == cid and c['tick'] <= t0]
        if not prior: continue
        tap = max(prior, key=lambda c: c['tick'])
        if t0 - tap['tick'] > 60: continue
        L = [((t - tap['tick']) * TICK, lv['x'] / TILE, lv['y'] / TILE) for t, _, lv, sm in rows if (t - tap['tick']) * TICK <= 5.0]
        S = [((t - tap['tick']) * TICK, sm['x'] / TILE, sm['y'] / TILE) for t, _, lv, sm in rows if (t - tap['tick']) * TICK <= 5.0]
        if len(L) < 5 or f * (L[-1][2] - L[0][2]) < 1.0: continue     # live walks >= 1 tile forward
        def err(tau):
            e = []
            for a, lx, ly in L:
                p = interp(S, a - tau)          # sim delayed by tau: compare live@a with sim@(a - tau)
                if p is not None: e.append(((p[0] - lx) ** 2 + (p[1] - ly) ** 2) ** 0.5)
            return (sum(e) / len(e), len(e)) if len(e) >= 4 else (None, 0)
        cands = [(err(t / 20)[0], t / 20) for t in range(-10, 41)]    # tau from -0.5 s to +2.0 s
        cands = [c for c in cands if c[0] is not None]
        if not cands or err(0.0)[0] is None: continue
        best, tau = min(cands)
        res[card]['tau'].append(tau); res[card]['r0'].append(err(0.0)[0]); res[card]['rbest'].append(best)
for card, v in res.items():
    print(f"== {card}: {len(v['tau'])} forward-walking units")
    print(f"   best sim delay tau: median {st.median(v['tau']):+.2f}s  (IQR {st.quantiles(v['tau'],n=4)[0]:+.2f}..{st.quantiles(v['tau'],n=4)[2]:+.2f})")
    print(f"   mean 2-D position error: at tau=0 median {st.median(v['r0']):.3f} tiles -> at best tau median {st.median(v['rbest']):.3f} tiles")
    print(f"   units with residual < 0.25 tiles after alignment: {sum(x < 0.25 for x in v['rbest'])}/{len(v['rbest'])}")
