"""Paired Tornado pull: units inside RIN of the cast point in BOTH engines at the cast frame; pull = d(cast) - d(~1 s)
for the same unit identity, live vs sim. Usage: python tornado_pair.py <dir> [RIN]"""
import collections, glob, json, math, sys
src = sys.argv[1]; RIN = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
pairs = collections.defaultdict(list)
for path in sorted(glob.glob(src + '/*.json')):
    d = json.load(open(path))
    if 'samples' not in d: continue
    own = next((c['side'] for c in d.get('commands', []) if c.get('source') == 'confirmed_own_tap'), None)
    by_tick = {s['tick']: {r['identity']: r for r in s['rows']} for s in d['samples'] if s.get('rows')}
    ticks = sorted(by_tick)
    for c in d.get('commands', []):
        if c.get('source') != 'confirmed_own_tap' or c.get('name') != 'Tornado' or not c.get('accepted'): continue
        t0 = next((t for t in ticks if t >= c['tick']), None)
        if t0 is None: continue
        cx, cy = c.get('resolved_xy', [c['x'], c['y']])
        dist = lambda b: math.hypot(b['x'] - cx, b['y'] - cy) / 1000
        t1 = min((t for t in ticks if 14 <= t - t0 <= 26), key=lambda t: abs(t - t0 - 20), default=None)
        if t1 is None: continue
        for ident, r in by_tick[t0].items():
            if r['tower'] or r['side'] == own or not r.get('live') or not r.get('sim'): continue
            if dist(r['live']) > RIN or dist(r['sim']) > RIN: continue
            q = by_tick[t1].get(ident)
            if not q or not q.get('live') or not q.get('sim'): continue
            pairs[r['card_id']].append((dist(r['live']) - dist(q['live']), dist(r['sim']) - dist(q['sim']),
                                        dist(r['live']), dist(r['sim'])))
out = {}
for cid, v in pairs.items():
    n = len(v); dl = [a - b for a, b, _, _ in v]
    m = sum(dl) / n; sd = (sum((x - m) ** 2 for x in dl) / max(1, n - 1)) ** .5
    out[cid] = dict(n=n, pull_live=round(sum(a for a, *_ in v) / n, 2), pull_sim=round(sum(x[1] for x in v) / n, 2),
                    live_minus_sim=round(m, 2), se=round(sd / n ** .5, 2), d0_live=round(sum(x[2] for x in v) / n, 2),
                    d0_sim=round(sum(x[3] for x in v) / n, 2))
print(json.dumps(dict(RIN=RIN, by_card=out)))
