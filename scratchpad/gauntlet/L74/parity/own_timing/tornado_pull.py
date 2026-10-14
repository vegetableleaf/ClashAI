"""Tornado pull parity (10-13, PARITY_ALL post-fix ranking: our Tornado is the most frequent icebow-relevant group).
For every accepted own Tornado in PARITY result JSONs: enemy units within R of the cast point at the cast frame (both
engines present), then their distance to the cast point over the next frames, live vs sim. Read-only.
Usage: python tornado_pull.py <dir with match .json> [out.json]"""
import collections, glob, json, math, sys

R = 6.5            # tiles; generous capture radius (Tornado radius ~5.5) -- pull is judged by the change in distance
HORIZON = 50       # ticks (2.5 s) after the cast
src, out = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
per_card = collections.defaultdict(list)   # card -> [(age, live_dist, sim_dist)]
casts = 0
for path in sorted(glob.glob(src + '/*.json')):
    d = json.load(open(path))
    if 'samples' not in d:
        continue
    own = next((c['side'] for c in d.get('commands', []) if c.get('source') == 'confirmed_own_tap'), None)
    torn = [c for c in d.get('commands', []) if c.get('source') == 'confirmed_own_tap' and c.get('name') == 'Tornado'
            and c.get('accepted')]
    if not torn:
        continue
    by_tick = {s['tick']: s for s in d['samples'] if s.get('rows')}
    ticks = sorted(by_tick)
    for c in torn:
        t0 = next((t for t in ticks if t >= c['tick']), None)
        if t0 is None:
            continue
        cx, cy = c.get('resolved_xy', [c['x'], c['y']])
        dist = lambda b: math.hypot(b['x'] - cx, b['y'] - cy) / 1000
        start = {r['identity']: r for r in by_tick[t0]['rows']
                 if not r['tower'] and r['side'] != own and r.get('live') and r.get('sim') and dist(r['live']) <= R}
        if not start:
            continue
        casts += 1
        for t in [t for t in ticks if t0 <= t <= t0 + HORIZON]:
            for r in by_tick[t]['rows']:
                s = start.get(r['identity'])
                if s and r.get('live') and r.get('sim'):
                    per_card[s['card_id']].append((t - t0, dist(r['live']), dist(r['sim'])))
report = {}
for card, pts in sorted(per_card.items(), key=lambda kv: -len(kv[1])):
    bins = collections.defaultdict(list)
    for age, lv, sm in pts:
        bins[min(age // 10, 5)].append((lv, sm))
    report[card] = {f'{b*0.5:.1f}s': dict(n=len(v), live=round(sum(x for x, _ in v)/len(v), 2),
                                         sim=round(sum(y for _, y in v)/len(v), 2),
                                         abs_diff=round(sum(abs(x-y) for x, y in v)/len(v), 2)) for b, v in sorted(bins.items())}
print(json.dumps(dict(casts_with_targets=casts, by_card=dict(list(report.items())[:12])), indent=1))
if out:
    json.dump(dict(casts=casts, report=report), open(out, 'w'))
