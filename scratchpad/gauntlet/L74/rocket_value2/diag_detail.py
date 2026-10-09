"""Per-fire detail of the iteration-1 diagnosis. python diag_detail.py DIR [ARM=rv9] [N=25] [seed]
For each first fire: the bodies in the 2.5-tile blast at the decision, then the same bodies' fate at the first board after the
Rocket lands (action delay 26 + flight), by nearest same-class body within 4 tiles; hp-weighted elixir value before/after, the
card BASE played at the same decision, what the arm did in the next 10 s, and the two outcomes."""
import glob, json, os, random, sys
from collections import defaultdict
sys.path.insert(0, os.getcwd())
import numpy as np
from pipeline import decision_options as D
from pipeline import vocab

DIR, ARM = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'rv9')
N = int(sys.argv[3]) if len(sys.argv) > 3 else 25
random.seed(int(sys.argv[4]) if len(sys.argv) > 4 else 0)
T = D.rocket_unit_table()


def info(name):
    return T.get(vocab.base_key(name), (0.0, 0.0, 0.5))


def load(arm, census):
    out = defaultdict(list)
    for f in glob.glob(f'{DIR}/fires_{arm}_{census}/bw_*.jsonl'):
        for line in open(f):
            d = json.loads(line)
            out[d['tag']].append(d)
    for v in out.values():
        v.sort(key=lambda d: d['t'])
    return out


def score(c, arm, tag):
    for line in open(f'{DIR}/{arm}_{c}/matches.jsonl'):
        r = json.loads(line)
        if r.get('arm') == 'plain' and r['tag'] == tag:
            return r['outcome']


def flight(cx, cy): return D.rocket_lands_in(cx, cy)


out = []
for c in ('evo', 'lad'):
    FA, FB = load('base', c), load(ARM, c)
    for tag, rows in FB.items():
        fires = [d for d in rows if d['play'] and d['why'] == 'rocket_value']
        if not fires:
            continue
        f = fires[0]
        cx, cy = f['cell']
        t_land = f['t'] + flight(cx, cy) * 0.05
        after = [d for d in rows if d['t'] >= t_land - 0.001]
        post = after[0] if after else None
        ins = [(n, x, y, h) for n, x, y, h in f['enemy'] if np.hypot(x - cx, y - cy) <= 2.0 + info(n)[2]]
        pre_val = sum(info(n)[0] * h for n, x, y, h in ins)
        pre_dmg = sum(info(n)[0] * min(580.0, h * info(n)[1]) / max(info(n)[1], 1) for n, x, y, h in ins)
        fate = []
        if post:
            for n, x, y, h in ins:
                cand = [(np.hypot(px - x, py - y), ph) for pn, px, py, ph in post['enemy'] if pn == n]
                cand = [q for q in cand if q[0] <= 4.5]
                fate.append((n, round(h, 2), None if not cand else round(min(cand)[1], 2),
                             None if not cand else round(min(cand)[0], 1)))
        b0 = next((d for d in FA.get(tag, []) if abs(d['t'] - f['t']) < 0.01), None)
        arm_plays = [(round(d['t'] - f['t'], 1), d['card']) for d in rows if f['t'] - 0.01 <= d['t'] <= f['t'] + 10 and d['play']]
        out.append(dict(c=c, tag=tag, t=f['t'], el=f['el'], cell=(cx, cy), pre_val=pre_val, pre_dmg=pre_dmg, fate=fate,
                        base=(b0['card'], b0['why']) if b0 and b0['play'] else None, arm_plays=arm_plays, t_land=t_land,
                        post_t=None if not post else post['t'], bo=score(c, 'base', tag), ao=score(c, ARM, tag)))
sel = random.sample(out, min(N, len(out)))
for r in sel:
    print(f"{r['c']} {r['tag']} t={r['t']:.1f} el={r['el']:.1f} cell=({r['cell'][0]:.1f},{r['cell'][1]:.1f}) land~{r['t_land']:.1f} post board t={r['post_t']} "
          f"| cost-val {r['pre_val']:.1f} dmg-val {r['pre_dmg']:.1f} | base {r['base']} | outcome {r['bo']} -> {r['ao']}")
    print('    fate (name, hp@fire, hp@landing board or None=gone, dist moved):', r['fate'])
    print('    arm plays next 10s:', r['arm_plays'])
# summary: how many bodies of the clump are gone / hp lost at the landing board
tot = [0, 0, 0]
survive_val = 0.0; start_val = 0.0; kill_val = 0.0
for r in out:
    for n, h0, h1, d in r['fate']:
        v = info(n)[0]
        start_val += v * h0
        if h1 is None:
            kill_val += v * h0
        else:
            survive_val += v * h1
            kill_val += v * max(0.0, h0 - h1)
print(f'ALL {len(out)} fires: value in blast at decision {start_val:.0f}, destroyed by the landing board {kill_val:.0f} ({kill_val / max(start_val, 1):.0%}), survivors {survive_val:.0f}')
print(f"mean predicted cost-val {np.mean([r['pre_val'] for r in out]):.2f}, dmg-val {np.mean([r['pre_dmg'] for r in out]):.2f}, destroyed per fire {kill_val / len(out):.2f}")
