"""Did the Tornado pull keep the clump in the Rocket blast?  python diag_combo.py DIR COMBO_ARM [RO_ARM] [CENSUSES=evo,lad,air]
COMBO_ARM = e.g. cb7 (rocket_tornado only: Rocket at the pull centre now, Tornado as the follow-up), RO_ARM = cb7_ro (the SAME trigger and
cell, the Rocket alone: "a lone Rocket at the same moment"); default RO_ARM = COMBO_ARM + '_ro'. Both arms are identical until the first
combo decision, so the clump (enemy bodies within the Tornado pull radius + their collision radius of the cell) is the same at the decision.
For each arm, the first board at/after the Rocket's impact (decision + rocket_lands_in) is read from the full-board windows
(DIR/fires_<arm>_<census>/bw_*.jsonl; rv2_diag_s0.py) and every clump body is followed to it (nearest same-class body within 6 tiles):
  in-blast   still inside the 2.0-tile blast + its radius at impact          (what the Rocket can hit)
  destroyed  elixir value (cost / bodies x hp fraction) killed or taken off  (dead/gone count in full; survivors by hp lost)
Shares are of the clump's value at the decision. The Tornado's own landing is in the combo arm's follow_ups tally (matches.jsonl)."""
import glob, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.getcwd())
import numpy as np
from pipeline import decision_options as D
from pipeline import vocab

DIR, ARM = sys.argv[1], sys.argv[2]
RO = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('evo') and ',' not in sys.argv[3] else ARM + '_ro'
CENS = (sys.argv[-1] if sys.argv[-1].split(',')[0] in ('evo', 'lad', 'air') else 'evo,lad,air').split(',')
T = D.rocket_unit_table()


def info(n): return T.get(vocab.base_key(n), (0.0, 0.0, 0.5, 0.05))[:3]


def load(arm, c):
    out = defaultdict(list)
    for f in glob.glob(f'{DIR}/fires_{arm}_{c}/bw_*.jsonl'):
        for line in open(f):
            d = json.loads(line)
            out[d['tag']].append(d)
    for v in out.values():
        v.sort(key=lambda d: d['t'])
    return out


def first_combo(rows):
    return next((d for d in rows if d['play'] and d.get('why') == 'rocket_tornado'), None)


def follow(rows, f):
    cx, cy = f['cell']
    t_imp = f['t'] + D.rocket_lands_in(cx, cy) * 0.05
    post = next((d for d in rows if d['t'] >= t_imp - 1e-6), None)
    if post is None or post['t'] - t_imp > 1.0:
        return None
    clump = [(n, x, y, h) for n, x, y, h in f['enemy'] if info(n)[0] > 0 and np.hypot(x - cx, y - cy) <= D.tornado_radius_tiles() + info(n)[2]]
    res = dict(value=0.0, inblast0=0.0, inblast=0.0, destroyed=0.0, killed=0, n=len(clump))
    for n, x, y, h in clump:
        ev, hp, r = info(n)
        v = ev * h
        res['value'] += v
        res['inblast0'] += v * (np.hypot(x - cx, y - cy) <= 2.0 + r)
        cand = sorted((np.hypot(px - x, py - y), px, py, ph) for pn, px, py, ph in post['enemy'] if pn == n)
        cand = [q for q in cand if q[0] <= 6.0]
        if not cand:
            res['destroyed'] += v; res['killed'] += 1; continue
        d_, px, py, ph = cand[0]
        res['inblast'] += v * (np.hypot(px - cx, py - cy) <= 2.0 + r)
        res['destroyed'] += ev * max(0.0, h - ph)
    return res


R = {'combo': [], 'ro': []}
nfire = defaultdict(int)
for c in CENS:
    A, B = load(ARM, c), load(RO, c)
    for tag, rows in A.items():
        fa = first_combo(rows)
        if fa is None:
            continue
        nfire[c] += 1
        fb = first_combo(B.get(tag, []))
        ra = follow(rows, fa)
        rb = follow(B[tag], fb) if fb is not None else None
        if ra is not None and rb is not None and abs(fa['t'] - fb['t']) < 1e-6:
            R['combo'].append(ra); R['ro'].append(rb)
print('first combo fires per census:', dict(nfire), '| paired with the Rocket-alone twin and followed to impact:', len(R['combo']))
if R['combo']:
    for k in ('combo', 'ro'):
        v = sum(r['value'] for r in R[k])
        print(f'{k:6s}: clump value at the decision {v:6.1f} ({v / len(R[k]):.2f}/fire, {np.mean([r["n"] for r in R[k]]):.1f} bodies); '
              f'in the blast at the decision {sum(r["inblast0"] for r in R[k]) / v:.0%}, at impact {sum(r["inblast"] for r in R[k]) / v:.0%}; '
              f'destroyed by the Rocket board {sum(r["destroyed"] for r in R[k]) / v:.0%} ({sum(r["destroyed"] for r in R[k]) / len(R[k]):.2f}/fire), '
              f'bodies gone {sum(r["killed"] for r in R[k])}')
    d = np.array([a['destroyed'] - b['destroyed'] for a, b in zip(R['combo'], R['ro'])])
    inb = np.array([a['inblast'] - b['inblast'] for a, b in zip(R['combo'], R['ro'])])
    rng = np.random.default_rng(0)
    bs = [rng.choice(d, len(d)).mean() for _ in range(4000)]
    print(f'paired combo - Rocket alone: destroyed {d.mean():+.2f} elixir/fire [{np.percentile(bs, 2.5):+.2f},{np.percentile(bs, 97.5):+.2f}]; '
          f'value in the blast at impact {inb.mean():+.2f}/fire; combo better {int((d > 0.05).sum())} / worse {int((d < -0.05).sum())} of {len(d)}')
