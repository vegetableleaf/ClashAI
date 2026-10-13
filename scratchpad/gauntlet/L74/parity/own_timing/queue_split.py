"""Does the sim-ahead error of our own troops grow with the tap->confirmed gap (elixir-queue hypothesis)?"""
import glob, json, sys
from collections import defaultdict
TILE, TICK = 1000.0, 0.05
src = sys.argv[1]
by = defaultdict(lambda: defaultdict(list))   # card -> gap bucket -> forward errors at age 1.5-3.0 s since tap
gaps = defaultdict(list)
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
        if cid not in names or not prior: continue
        tap = max(prior, key=lambda c: c['tick'])
        if t0 - tap['tick'] > 60 or tap.get('confirmation_tick') is None: continue
        gap = (tap['confirmation_tick'] - tap['tick']) * TICK
        gaps[names[cid]].append(gap)
        b = 'gap<1.0s' if gap < 1.0 else 'gap1.0-1.5s' if gap < 1.5 else 'gap1.5-2.0s' if gap < 2.0 else 'gap>=2.0s'
        for t, _, lv, sm in rows:
            age = (t - tap['tick']) * TICK
            if 1.5 <= age < 3.0:
                by[names[cid]][b].append(f * (sm['y'] - lv['y']) / TILE)
for card in ('Knight', 'Skeletons', 'IceWizard', 'Tesla', 'Xbow'):
    g = sorted(gaps.get(card, []))
    if not g: continue
    print(f'== {card}: tap->confirm gap median {g[len(g)//2]:.2f}s (n {len(g)}, min {g[0]:.2f}, max {g[-1]:.2f})')
    for b in ('gap<1.0s', 'gap1.0-1.5s', 'gap1.5-2.0s', 'gap>=2.0s'):
        v = by[card].get(b)
        if v: print(f'   {b:12s} n {len(v):5d}  sim-ahead {sum(v)/len(v):+.3f} tiles')
