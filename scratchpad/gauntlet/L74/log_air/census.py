"""Live census of every Log the bot cast in the recorded live logs (default: 10-05 .. 10-09), judged by the log_air rule on the
model's own decision board (public.model_bodies / model_towers, the very board the model saw) and the Log's played cell.

Per Log: ground = a ground unit / building in the roll corridor; tower = an enemy tower in it; air = a flyer in it. Classes:
  only_air  air, no ground, no tower  (the Logs log_air acts on; subset 'barrel' = a Goblin Barrel in flight inside it)
  empty     nothing at all in the corridor (information only; not blocked)
  hits      ground and/or tower (and maybe air)
For only_air: what retarget would do on a flat-logit board (a ground cell exists / the princess chip / unchanged), and the card
that came into the hand after the Log (hand diff on the next decisions), with whether it attacks air (catalog attacks_air).
usage: census.py OUT.json [glob]"""
import collections, glob, json, os, sys
import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
from pipeline.decision_options import (LOG_AIR_BLOCKED, LOG_AIR_UNIT_RADIUS, _covers, cell_centres_tiles, log_air_board,
                                      log_air_cell, rolling_corridor)
from pipeline.body_identity import CATALOG
from pipeline.model_v3 import cell_label
from pipeline.obs_contract import Tower, Unit

SRC = r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader'
CORRIDOR = rolling_corridor('Log')
ATTACKS_AIR = {c['name']: bool(c['attacks_air']) for c in json.loads(CATALOG.read_text(encoding='utf-8'))['cards']}
FLAT = torch.zeros(2304)


def board(pub):
    units = tuple(Unit(b['cls'], b['side'], b['x'], b['y'], None, None, None, 1.) for b in pub['model_bodies'])
    towers = tuple(Tower(t['side'], t['kind'], t['lane'], t['hp_frac'], t['alive']) for t in pub['model_towers'])
    return SimpleNamespace(units=units, towers=towers)


from types import SimpleNamespace


def classify(pub, xy):
    bs = board(pub)
    ground, air, towers = log_air_board(bs)
    x, y = xy[0] * 18.0, xy[1] * 32.0
    cx, cy = np.array([x]), np.array([y])
    g = _covers(cx, cy, [p[:2] for p in ground], CORRIDOR, LOG_AIR_UNIT_RADIUS).any()
    a = _covers(cx, cy, air, CORRIDOR, LOG_AIR_UNIT_RADIUS).any()
    t = any(_covers(cx, cy, [q[:2]], CORRIDOR, q[2]).any() for q in towers)
    names = []
    return g, a, t, (ground, air, towers)


def retarget_kind(board3, xy):
    """On a flat-logit board: which rule re-aims this Log (ground cell / princess chip / unchanged), and the ground elixir hit."""
    cell = int(cell_label(torch.tensor((xy[0], xy[1])), 'lattice'))
    got = log_air_cell(FLAT, CORRIDOR, board3, (), 'lattice', 'retarget', cell)
    if got == cell:
        return 'unchanged', 0.0
    x, y = cell_centres_tiles('lattice')
    value = float((_covers(x[got:got + 1], y[got:got + 1], [p[:2] for p in board3[0]], CORRIDOR, LOG_AIR_UNIT_RADIUS)
                   @ np.array([p[2] for p in board3[0]]))[0]) if board3[0] else 0.0
    return ('ground' if value > 0 else 'chip'), value


def main(out, pattern=None):
    files = sorted(glob.glob(pattern or os.path.join(SRC, 'live_play_2026100[5-9]*.jsonl')))
    res = dict(files=0, matches_with_log=0, logs=0, only_air=0, empty=0, hits=0, barrel=0, per_match=[], cases=[],
               retarget=collections.Counter(), retarget_value=[], after_only_air=collections.Counter(),
               after_only_air_attacks_air=collections.Counter(), after_all=collections.Counter(),
               units_in_path_only_air=collections.Counter(), seen_130607=[])
    for f in files:
        res['files'] += 1
        last = None
        n_log = 0
        pending = None
        for line in open(f, encoding='utf-8', errors='replace'):
            if line.startswith('{"event": "decision"'):
                if pending is not None and pending['wait'] > 0:
                    pending['wait'] -= 1
                    try:
                        hand = [h['name'] for h in json.loads(line)['public']['own_hand']]
                    except Exception:
                        continue
                    new = [h for h in hand if h not in pending['before']]
                    if len(new) == 1:
                        res['after_all'][new[0]] += 1
                        if pending['only_air']:
                            res['after_only_air'][new[0]] += 1
                            res['after_only_air_attacks_air'][str(ATTACKS_AIR.get(new[0]))] += 1
                        pending = None
                    elif pending['wait'] == 0:
                        pending = None
                last = line
            elif line.startswith('{"event": "play"') and '"name": "Log"' in line and last is not None:
                d = json.loads(line)
                dec = json.loads(last)
                pub = dec['public']
                if 'model_bodies' not in pub:
                    continue
                xy = dec['decision'].get('xy') or d['xy']
                g, a, t, b3 = classify(pub, xy)
                n_log += 1
                res['logs'] += 1
                kind = 'hits' if (g or t) else ('only_air' if a else 'empty')
                res[kind] += 1
                if kind == 'only_air':
                    # an ENEMY projectile (enemy flag 1) aimed into the corridor: the Goblin Barrel exemption, approximated
                    # (the live gate keys on the barrel's own model id; the census has no deck-specific id map)
                    pr = [(q[4] * 18.0, q[5] * 32.0) for q in pub.get('model_projectiles', []) if len(q) > 5 and q[1] == 1.0]
                    if pr and _covers(np.array([xy[0] * 18]), np.array([xy[1] * 32]), pr, CORRIDOR, 0.0).any():
                        res['barrel'] += 1
                    rk, val = retarget_kind(b3, xy)
                    res['retarget'][rk] += 1
                    res['retarget_value'].append(val)
                    from pipeline import vocab
                    for u in pub['model_bodies']:
                        if u['side'] != 0:
                            ux, uy = u['x'] * 18, u['y'] * 32
                            if _covers(np.array([xy[0] * 18]), np.array([xy[1] * 32]), [(ux, uy)], CORRIDOR, LOG_AIR_UNIT_RADIUS).any():
                                res['units_in_path_only_air'][vocab.UNIT_VOCAB[u['cls']]] += 1
                    case = dict(file=os.path.basename(f)[10:25], tick=d['tick'], xy=[round(xy[0] * 18, 1), round(xy[1] * 32, 1)],
                                retarget=rk, value=round(val, 2), hand=[h['name'] for h in pub['own_hand']])
                    res['cases'].append(case)
                pending = dict(before=[h['name'] for h in pub['own_hand']], only_air=kind == 'only_air', wait=6)
        if n_log:
            res['matches_with_log'] += 1
        res['per_match'].append(n_log)
    res['retarget'] = dict(res['retarget'])
    for k in ('after_only_air', 'after_only_air_attacks_air', 'after_all', 'units_in_path_only_air'):
        res[k] = dict(res[k].most_common())
    v = res.pop('retarget_value')
    res['retarget_value_mean'] = float(np.mean(v)) if v else 0.0
    pm = np.array(res.pop('per_match'))
    res['logs_per_match_mean'] = float(pm.mean()) if len(pm) else 0.0
    res['seen_130607'] = [c for c in res['cases'] if c['file'].startswith('20261009_130607')]
    json.dump(res, open(out, 'w'), indent=1, default=str)
    print({k: v for k, v in res.items() if k not in ('cases',)})


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
