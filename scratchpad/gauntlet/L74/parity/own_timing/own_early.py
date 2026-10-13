"""Own-side early-life parity: placement (buildings) and movement (troops) error vs time since our confirmed tap.
Reads PARITY fixed-rerun match JSONs (raw paired live/sim x,y in native units, 1000 per tile). Read-only.
Usage: python own_early.py <dir with match .json> [out.json]"""
import glob, json, math, sys
from collections import defaultdict

TILE = 1000.0
TICK_S = 0.05
BUILDINGS = {'Tesla', 'Xbow'}
src, out = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)

tap_tick = lambda c: c.get('tap_tick', c['tick'])   # injected later than the tap in --own-timing spawn* runs
traj = []   # one entry per own unit identity: card, side, tap tick, list of (age_ticks, live xy, sim xy)
for path in sorted(glob.glob(src + '/*.json')):
    d = json.load(open(path))
    taps = [c for c in d.get('commands', []) if c.get('source') == 'confirmed_own_tap']
    if not taps:
        continue
    own = taps[0]['side']
    names = {c['card_id']: c['name'] for c in taps}
    seen = defaultdict(list)
    for s in d['samples']:
        for r in s.get('rows', []):
            if r.get('tower') or r.get('side') != own or not r.get('live') or not r.get('sim'):
                continue
            seen[r['identity']].append((s['tick'], r['card_id'], r['live'], r['sim']))
    for ident, rows in seen.items():
        rows.sort(key=lambda t: t[0])
        first_tick, cid = rows[0][0], rows[0][1]
        prior = [c for c in taps if c['card_id'] == cid and tap_tick(c) <= first_tick]
        if cid not in names or not prior:
            continue
        tap = max(prior, key=tap_tick)
        if first_tick - tap_tick(tap) > 60:        # first sighting >3 s after the tap: not a fresh deploy, skip
            continue
        traj.append(dict(card=names[cid], side=own, match=d['match'], tap=tap_tick(tap), spawn=(tap['x'], tap['y']),
                         pts=[(t - tap_tick(tap), (lv['x'], lv['y']), (sm['x'], sm['y'])) for t, _, lv, sm in rows]))


def fwd(side):
    # side 0 sits at small y and advances toward larger y; side 1 the reverse.
    return 1.0 if side == 0 else -1.0


stats = defaultdict(lambda: defaultdict(list))
for u in traj:
    f = fwd(u['side'])
    for age, lv, sm in u['pts']:
        dx, dy = (sm[0] - lv[0]) / TILE, (sm[1] - lv[1]) / TILE
        b = min(int(age * TICK_S / 0.5), 8)          # 0.5 s bins, last bin = 4 s+
        stats[u['card']][b].append((math.hypot(dx, dy), f * dy, dx))
    # walking speed over the first 2 s where both are sampled at the same ages
    pts = [p for p in u['pts'] if p[0] * TICK_S <= 2.0]
    if len(pts) >= 2 and pts[-1][0] > pts[0][0]:
        dt = (pts[-1][0] - pts[0][0]) * TICK_S
        lv = f * (pts[-1][1][1] - pts[0][1][1]) / TILE / dt
        sm = f * (pts[-1][2][1] - pts[0][2][1]) / TILE / dt
        stats[u['card']]['speed'].append((lv, sm))

report = {}
for card in sorted(stats):
    rows = {}
    for b in range(9):
        v = stats[card].get(b)
        if v:
            rows[f'{b*0.5:.1f}-{b*0.5+0.5:.1f}s' if b < 8 else '4.0s+'] = dict(
                n=len(v), err=round(sum(x[0] for x in v) / len(v), 3),
                ahead=round(sum(x[1] for x in v) / len(v), 3), lateral=round(sum(x[2] for x in v) / len(v), 3))
    sp = stats[card].get('speed', [])
    report[card] = dict(kind='building' if card in BUILDINGS else 'troop', units=sum(u['card'] == card for u in traj),
                        bins=rows, speed=dict(n=len(sp),
                        live=round(sum(a for a, _ in sp) / len(sp), 3) if sp else None,
                        sim=round(sum(b for _, b in sp) / len(sp), 3) if sp else None))
print(json.dumps(report, indent=1))
if out:
    json.dump(dict(report=report, units=traj), open(out, 'w'))
