"""Does the decision-history velocity predict where the bodies are at impact?  python diag_lead.py DIR [ARM=rv9]
BASE and ARM are identical until the first fire, so the BASE boards of [t0 - 1 s, t0] are the history the live rule would have (the
SIM decides every 10 ticks). For every first fire: the enemy bodies inside the blast + radius at the decision, their position at
impact (ARM board at impact, nearest same-class body within 5 tiles), and the prediction p + v * (impact - decision) with v from
decision_options.rocket_velocities. Reports mean position error (static vs lead) and the share of the bodies' value that a
blast aimed at the best cell would cover with the static / lead / true positions (the best cell is chosen on the prediction,
the coverage scored on the true impact positions)."""
import glob, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.getcwd())
import numpy as np
from pipeline import decision_options as D
from pipeline import vocab

DIR, ARM = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'rv9')
T = D.rocket_unit_table()


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


def bodies_of(board):
    rows = []
    for n, x, y, h in board['enemy']:
        ev, hp, r = info(n)
        if ev > 0:
            rows.append((float(vocab.unit_id(n)), x, y, ev * h, r))
    return np.array(rows).reshape(-1, 5)


xs, ys = D.cell_centres_tiles('lattice')
mine = ys >= 16
err_static, err_lead, DISP, DISPMETA = [], [], [], []
alt_err = defaultdict(list)
from pipeline.body_identity import CATALOG as _CAT
SPEED = {vocab.engine_key(c['name']): c.get('speed') for c in json.loads(_CAT.read_text(encoding='utf-8'))['cards'] if c.get('speed')}
cov = defaultdict(float); tot = 0.0; nfire = 0
for c in ('evo', 'lad'):
    FA, FB = load('base', c), load(ARM, c)
    for tag, rows in FB.items():
        f = next((d for d in rows if d['play'] and d['why'] == 'rocket_value'), None)
        if f is None:
            continue
        t0 = f['t']; cx, cy = f['cell']
        hist = [(int(round(d['t'] / 0.05)), bodies_of(d)) for d in FA.get(tag, []) if t0 - 1.0 - 1e-6 <= d['t'] < t0 - 1e-6]
        if not hist:
            continue
        post = next((d for d in rows if d['t'] >= t0 + D.rocket_lands_in(cx, cy) * 0.05 - 1e-6), None)
        if post is None:
            continue
        now = bodies_of(f)
        tick = int(round(t0 / 0.05))
        vel = D.rocket_velocities(hist, tick, now)
        horizon = D.rocket_lands_in(cx, cy)
        pred = np.clip(now[:, 1:3] + vel * horizon, (0, 0), (18, 32))
        # forward-drift priors: +y (toward my side) at the catalog speed (tiles/s = speed / 60) x KAPPA; 'blend' = history where it moves
        spd = np.array([SPEED.get(vocab.base_key(vocab.UNIT_VOCAB[int(c)]), 60) for c in now[:, 0]]) / 60.0 / 20.0
        drift = np.zeros_like(vel); drift[:, 1] = spd
        alts = {'drift': np.clip(now[:, 1:3] + drift * horizon, (0, 0), (18, 32))}
        mv = np.hypot(vel[:, 0], vel[:, 1]) > 0.01
        alts['blend'] = np.clip(now[:, 1:3] + np.where(mv[:, None], vel, drift) * horizon, (0, 0), (18, 32))
        alts['half'] = np.clip(now[:, 1:3] + 0.5 * np.where(mv[:, None], vel, drift) * horizon, (0, 0), (18, 32))
        true = []
        for i, b in enumerate(now):
            same = [(np.hypot(px - b[1], py - b[2]), px, py) for pn, px, py, ph in post['enemy'] if vocab.unit_id(pn) == int(b[0])]
            same = [q for q in same if q[0] <= 5.0]
            true.append(None if not same else (min(same)[1], min(same)[2]))
        keep = [i for i, q in enumerate(true) if q is not None and now[i, 3] > 0]
        if not keep:
            continue
        nfire += 1
        tp = np.array([true[i] for i in keep]); v = now[keep, 3]; r = now[keep, 4]
        DISP.append((tp - now[keep, 1:3], pred[keep] - now[keep, 1:3]))
        DISPMETA.append((now[keep, 0], horizon))
        if os.environ.get('SHOW') and nfire <= int(os.environ['SHOW']):
            for j, i in enumerate(keep):
                print(f'  {tag} t={t0:.1f} h={horizon} {vocab.UNIT_VOCAB[int(now[i, 0])]:18s} now ({now[i, 1]:5.1f},{now[i, 2]:5.1f}) '
                      f'vel/tick ({vel[i, 0]:+.3f},{vel[i, 1]:+.3f}) pred disp ({pred[i, 0] - now[i, 1]:+.1f},{pred[i, 1] - now[i, 2]:+.1f}) '
                      f'actual disp ({tp[j, 0] - now[i, 1]:+.1f},{tp[j, 1] - now[i, 2]:+.1f}) hist n={len(hist)}')
        err_static += list(np.hypot(now[keep, 1] - tp[:, 0], now[keep, 2] - tp[:, 1]))
        err_lead += list(np.hypot(pred[keep, 0] - tp[:, 0], pred[keep, 1] - tp[:, 1]))

        def score(positions):
            """aim the best cell on `positions`, score the true coverage"""
            inside = np.hypot(xs[:, None] - positions[None, :, 0], ys[:, None] - positions[None, :, 1]) <= 2.0 + r[None, :]
            k = int(np.where(mine, inside @ v, -1).argmax())
            return float(v[np.hypot(xs[k] - tp[:, 0], ys[k] - tp[:, 1]) <= 2.0 + r].sum())
        cov['static'] += score(now[keep, 1:3]); cov['lead'] += score(pred[keep]); cov['true'] += score(tp); tot += v.sum()
        for k, a in alts.items():
            cov[k] += score(a[keep]); alt_err[k] += list(np.hypot(a[keep, 0] - tp[:, 0], a[keep, 1] - tp[:, 1]))
print(f'{nfire} fires, {len(err_static)} bodies followed to impact')
print(f'position error at impact (tiles): static mean {np.mean(err_static):.2f} median {np.median(err_static):.2f} | lead mean {np.mean(err_lead):.2f} median {np.median(err_lead):.2f}')
if os.environ.get('SPEED'):
    from pipeline.body_identity import CATALOG
    cs = json.loads(CATALOG.read_text(encoding='utf-8'))
    sp = {vocab.engine_key(c['name']): c.get('speed') for c in cs['cards'] if c.get('speed')}
    byspeed = defaultdict(list)
    for (a, p), (cls, h) in zip(DISP, DISPMETA):
        for ai, ci in zip(a, cls):
            k = sp.get(vocab.base_key(vocab.UNIT_VOCAB[int(ci)]))
            if k:
                byspeed[k].append((ai[1] / h, np.hypot(*ai) / h))
    for k in sorted(byspeed):
        v = np.array(byspeed[k])
        print(f'catalog speed {k:4d}: n={len(v):3d} mean dy/tick {v[:, 0].mean():+.3f} mean |d|/tick {v[:, 1].mean():.3f}  ratio |d| to speed/60/20: {v[:, 1].mean() / (k / 60 / 20):.2f}')
act = np.vstack([a for a, p in DISP]); prd = np.vstack([p for a, p in DISP])
print(f'displacement to impact: actual mean |d| {np.hypot(*act.T).mean():.2f} (dy {act[:, 1].mean():+.2f}), predicted {np.hypot(*prd.T).mean():.2f} '
      f'(dy {prd[:, 1].mean():+.2f}), predicted ~0 for {(np.hypot(*prd.T) < 0.05).mean():.0%}; regression slope actual~predicted '
      f'{(act * prd).sum() / max((prd * prd).sum(), 1e-9):.2f}, corr {np.corrcoef(act.ravel(), prd.ravel())[0, 1]:.2f}')
for k in alt_err:
    print(f'  prior {k:6s}: position error mean {np.mean(alt_err[k]):.2f} median {np.median(alt_err[k]):.2f}; covered {cov[k]:.0f} ({cov[k] / tot:.0%})')
print(f'value covered by the best blast, scored on the TRUE impact positions, of {tot:.0f}: static aim {cov["static"]:.0f} ({cov["static"] / tot:.0%}), '
      f'lead aim {cov["lead"]:.0f} ({cov["lead"] / tot:.0%}), oracle {cov["true"]:.0f} ({cov["true"] / tot:.0%})')
