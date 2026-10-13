"""Own troops the live game shows walking forward: motion onset (deploy timing) and walking speed, live vs sim."""
import glob, json, sys, statistics as st
from collections import defaultdict
TILE, TICK = 1000.0, 0.05
src = sys.argv[1]
res = defaultdict(lambda: dict(on_l=[], on_s=[], sp_l=[], sp_s=[]))
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
        prior = [c for c in taps if c['card_id'] == cid and c['tick'] <= t0]
        if cid not in names or names[cid] in ('Tesla', 'Xbow') or not prior: continue
        tap = max(prior, key=lambda c: c['tick'])
        if t0 - tap['tick'] > 60: continue
        pts = [((t - tap['tick']) * TICK, f * lv['y'] / TILE, f * sm['y'] / TILE) for t, _, lv, sm in rows if (t - tap['tick']) * TICK <= 4.0]
        if len(pts) < 4: continue
        l0, s0 = pts[0][1], pts[0][2]
        if pts[-1][1] - l0 < 1.0: continue                      # keep only units the LIVE game shows walking >=1 tile forward
        onset = lambda k, base: next((a for a, *v in pts if v[k] - base > 0.2), None)
        ol, os_ = onset(0, l0), onset(1, s0)
        if ol is not None and os_ is not None:
            res[names[cid]]['on_l'].append(ol); res[names[cid]]['on_s'].append(os_)
        # walking speed over the part where both are clearly moving (age 2.0 -> 4.0 s)
        mv = [p for p in pts if 2.0 <= p[0] <= 4.0]
        if len(mv) >= 2 and mv[-1][0] > mv[0][0]:
            dt = mv[-1][0] - mv[0][0]
            res[names[cid]]['sp_l'].append((mv[-1][1] - mv[0][1]) / dt); res[names[cid]]['sp_s'].append((mv[-1][2] - mv[0][2]) / dt)
for card, v in res.items():
    if not v['on_l']: continue
    dl = [s - l for l, s in zip(v['on_l'], v['on_s'])]
    print(f"== {card}: {len(v['on_l'])} forward-walking units")
    print(f"   motion onset after tap: live median {st.median(v['on_l']):.2f}s  sim median {st.median(v['on_s']):.2f}s  (sim minus live median {st.median(dl):+.2f}s)")
    if v['sp_l']:
        print(f"   walking speed 2-4 s (tiles/s): live median {st.median(v['sp_l']):.3f}  sim median {st.median(v['sp_s']):.3f}  (n {len(v['sp_l'])})")
