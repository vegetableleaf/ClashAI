"""Elixir Golem death spawns: children's first-seen offsets from the dying parent's last point, live vs SIM, for parent
deaths that happen within 4 ticks of each other in a fight."""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import capture, setup, F, ps
STEMS = sys.argv[1].split(',')
for stem in STEMS:
    ctx = setup(stem); cat = ctx['catalog']; eg = next(c for c in cat.values() if c['display_name'] == 'ElixirGolem')['card_id']
    res, _ = capture(stem, lambda f, a: any(e['name'] == 'ElixirGolem' for e in [ctx['events'][j] for j in f['events']]) or a['name'] == 'ElixirGolem', ctx)
    for f, a, rows, st, r in res:
        def tracks(get):
            tr = {}
            for t, live, simb in rows:
                for b in get(live, simb):
                    tr.setdefault(b['id'], []).append((t, b['x'], b['y'], b['max_hp']))
            return tr
        L = tracks(lambda l, s: [b for b in l if not b['tower'] and b['card_id'] == eg])
        S = tracks(lambda l, s: [b for b in s if not b['tower'] and b.get('name') == 'ElixirGolem'])
        end = rows[-1][0]
        def deaths(tr):
            out = []
            for k, v in tr.items():
                if v[-1][0] < end - 2:
                    kids = [(w[0][0], w[0][1], w[0][2], w[0][3]) for kk, w in tr.items() if w[0][3] < v[0][3] and 0 <= w[0][0] - v[-1][0] <= 6 and v[0][0] < w[0][0]]
                    if kids: out.append((v[-1], kids))
            return out
        for (pl, kl) in deaths(L):
            m = [(ps_, ks) for ps_, ks in deaths(S) if abs(ps_[0]-pl[0]) <= 4 and ps_[3] == pl[3] and math.hypot(ps_[1]-pl[1], ps_[2]-pl[2]) < 800]
            if not m: continue
            ps_, ks = m[0]
            rel = lambda p, ks: sorted((round(k[1]-p[1]), round(k[2]-p[2]), k[0]-p[0]) for k in ks)
            print(stem[-6:], f['t0'], 'parent max', pl[3], 'death live', pl[0], 'sim', ps_[0], 'pos err', round(math.hypot(ps_[1]-pl[1], ps_[2]-pl[2])))
            print('    live kids (dx,dy,dt)', rel(pl, kl)); print('    sim  kids (dx,dy,dt)', rel(ps_, ks))
