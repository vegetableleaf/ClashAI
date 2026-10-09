"""Which bodies does an iteration-1 Rocket actually hit?  python diag_cat.py DIR [ARM=rv9]
Bodies inside the blast (+ collision radius) at the first fire's decision, by category (flying / ground x moving / still per the BASE
history of the last second), and what happened by impact: inside (still in the blast, counted as hit), outside (walked out), gone
(no same-class body within 5 tiles: dead or fled). Value-weighted (elixir = cost/bodies x hp)."""
import glob, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.getcwd())
import numpy as np
from pipeline import decision_options as D
from pipeline import vocab
from pipeline.body_identity import CATALOG

DIR, ARM = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'rv9')
T = D.rocket_unit_table()
cs = json.loads(CATALOG.read_text(encoding='utf-8'))
FLY = {vocab.engine_key(c['name']): bool(c.get('flying_height')) for c in cs['cards']}
SPEED = {vocab.engine_key(c['name']): c.get('speed') or 0 for c in cs['cards']}


def info(n): return T.get(vocab.base_key(n), (0.0, 0.0, 0.5))[:3]


def load(arm, c):
    out = defaultdict(list)
    for f in glob.glob(f'{DIR}/fires_{arm}_{c}/bw_*.jsonl'):
        for line in open(f):
            d = json.loads(line)
            out[d['tag']].append(d)
    for v in out.values():
        v.sort(key=lambda d: d['t'])
    return out


tab = defaultdict(lambda: defaultdict(float)); n = defaultdict(int)
for c in ('evo', 'lad'):
    FA, FB = load('base', c), load(ARM, c)
    for tag, rows in FB.items():
        f = next((d for d in rows if d['play'] and d['why'] == 'rocket_value'), None)
        if f is None:
            continue
        t0 = f['t']; cx, cy = f['cell']
        post = next((d for d in rows if d['t'] >= t0 + D.rocket_lands_in(cx, cy) * 0.05 - 1e-6), None)
        old = [d for d in FA.get(tag, []) if t0 - 1.0 - 1e-6 <= d['t'] < t0 - 1e-6]
        if post is None:
            continue
        ref = old[0] if old else None
        for nm, x, y, h in f['enemy']:
            ev, hp, r = info(nm)
            if ev <= 0 or np.hypot(x - cx, y - cy) > 2.0 + r:
                continue
            key = vocab.base_key(nm)
            fly = 'air' if FLY.get(key) else 'ground'
            mv = 'noref'
            if ref is not None:
                same = [(np.hypot(px - x, py - y), px, py) for pn, px, py, ph in ref['enemy'] if pn == nm]
                if same:
                    dd = min(same)[0]
                    mv = 'moving' if dd >= 0.3 else 'still'
            cat = (fly, mv)
            v = ev * h
            cand = [(np.hypot(px - x, py - y), px, py, ph) for pn, px, py, ph in post['enemy'] if pn == nm]
            cand = [q for q in cand if q[0] <= 5.0]
            if not cand:
                out = 'gone'
            else:
                q = min(cand)
                out = 'inside' if np.hypot(q[1] - cx, q[2] - cy) <= 2.0 + r else 'outside'
            tab[cat][out] += v; tab[cat]['all'] += v; n[cat] += 1
print('category (value-weighted share of the value that was in the blast at the decision)')
for cat in sorted(tab):
    t = tab[cat]
    print(f'  {cat[0]:6s} {cat[1]:7s} n={n[cat]:4d} value {t["all"]:6.0f}: inside at impact {t["inside"] / t["all"]:4.0%}  outside {t["outside"] / t["all"]:4.0%}  gone {t["gone"] / t["all"]:4.0%}')
