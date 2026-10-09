"""What did an iteration-1 Rocket do to the bodies it was aimed at?  python diag_landing.py DIR [ARM=rv9]
Per first fire: every enemy body inside the 2.0-tile blast + its collision radius at the DECISION board is followed to the first
board at/after the impact (decision + rocket_lands_in; SIM benchmark = no action delay) by the nearest same-class body within
`MAXD` tiles of where it was; classes (elixir value = cost/bodies x hp fraction at the decision):
  dead     no counterpart: killed (or left the matching radius)
  hit      counterpart inside the blast + radius at impact, hp lower than at the decision
  missed   counterpart OUTSIDE the blast + radius at impact (it walked out during the flight), hp not lower
  inside_unhurt  inside, hp not lower (impact not yet applied on that board, or immune)
and how far the survivors moved (tiles) between the two boards. Lead statistic: the share of the decision-time value that
a blast aimed at the bodies' positions at impact would have covered."""
import glob, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.getcwd())
import numpy as np
from pipeline import decision_options as D
from pipeline import vocab

DIR, ARM = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'rv9')
MAXD = 5.0
T = D.rocket_unit_table()


def info(n): return T.get(vocab.base_key(n), (0.0, 0.0, 0.5))


def load(arm, c):
    out = defaultdict(list)
    for f in glob.glob(f'{DIR}/fires_{arm}_{c}/bw_*.jsonl'):
        for line in open(f):
            d = json.loads(line)
            out[d['tag']].append(d)
    for v in out.values():
        v.sort(key=lambda d: d['t'])
    return out


tally = defaultdict(float); count = defaultdict(int); moved = []; nfire = 0; covered_at_impact = []; value_total = 0.0
for c in ('evo', 'lad'):
    FB = load(ARM, c)
    for tag, rows in FB.items():
        f = next((d for d in rows if d['play'] and d['why'] == 'rocket_value'), None)
        if f is None:
            continue
        cx, cy = f['cell']
        t_land = f['t'] + D.rocket_lands_in(cx, cy) * 0.05
        post = next((d for d in rows if d['t'] >= t_land - 1e-6), None)
        if post is None or post['t'] - t_land > 1.0:
            continue
        nfire += 1
        fire_val = 0.0; pos_at_impact = []
        for n, x, y, h in f['enemy']:
            ev, hp, r = info(n)
            if ev <= 0 or np.hypot(x - cx, y - cy) > 2.0 + r:
                continue
            v = ev * h; fire_val += v
            cand = sorted((np.hypot(px - x, py - y), px, py, ph) for pn, px, py, ph in post['enemy'] if pn == n)
            cand = [q for q in cand if q[0] <= MAXD]
            if not cand:
                tally['dead'] += v; count['dead'] += 1; continue
            dist, px, py, ph = cand[0]
            moved.append(dist)
            pos_at_impact.append((px, py, v, r))
            inside = np.hypot(px - cx, py - cy) <= 2.0 + r
            if inside and ph < h - 0.02:
                tally['hit'] += v; count['hit'] += 1
            elif not inside:
                tally['missed'] += v; count['missed'] += 1
            else:
                tally['inside_unhurt'] += v; count['inside_unhurt'] += 1
        value_total += fire_val
        # best blast aimed at the impact-time positions of the same bodies (edge hitbox), as the lead rule would have chosen
        if pos_at_impact:
            xs, ys = D.cell_centres_tiles('lattice')
            m = ys >= 16
            val = np.array([[v if np.hypot(xs[k] - px, ys[k] - py) <= 2.0 + r else 0.0 for px, py, v, r in pos_at_impact]
                            for k in np.flatnonzero(m)]).sum(axis=1)
            covered_at_impact.append((val.max(), sum(p[2] for p in pos_at_impact)))
print(f'{nfire} fires; value in the blast at the decision {value_total:.0f} ({value_total / nfire:.2f}/fire)')
for k in ('dead', 'hit', 'missed', 'inside_unhurt'):
    print(f'  {k:14s} bodies {count[k]:4d} value {tally[k]:7.1f} ({tally[k] / value_total:.0%})')
print(f'survivors moved between the boards: mean {np.mean(moved):.2f} tiles, median {np.median(moved):.2f}, >=2 tiles {np.mean(np.array(moved) >= 2):.0%}')
if covered_at_impact:
    a = np.array(covered_at_impact)
    print(f'a blast re-aimed at the impact-time positions would cover {a[:, 0].sum():.0f} of the {a[:, 1].sum():.0f} surviving-body value '
          f'(vs {tally["hit"] + tally["inside_unhurt"]:.0f} the real aim covered)')
