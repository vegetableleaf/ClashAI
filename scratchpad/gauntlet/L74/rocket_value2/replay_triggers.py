"""Offline: the FIRST TRIGGER of every rocket_value variant on BASE's logged boards (rv2_boards_s0.py).
  python replay_triggers.py BOARDS_DIR CENSUS VARIANTS_JSON [--workers 8] [--out DIR]
BOARDS_DIR/fires_base_<CENSUS>/boards_*.jsonl -> DIR/fires_base_<CENSUS>/scout_replay.jsonl (the format mk_subsets.py reads):
one line per (tag, variant) at the variant's first firing decision.  The replay IS the rule: decision_options.rocket_value_choice on a
board rebuilt from the log (names, the Rocket slot's affordability, pending, BASE's gate decision as `playing`, a per-(match, variant)
history holder for lead), with a prefilter that skips a call only when the variant's own best_rocket_clump value is below its V."""
import argparse, glob, json, os, sys
from collections import defaultdict
from multiprocessing import Pool
from types import SimpleNamespace

sys.path.insert(0, os.getcwd())
import numpy as np
from pipeline import decision_options as D
from pipeline.obs_contract import Unit

ap = argparse.ArgumentParser()
ap.add_argument('boards'); ap.add_argument('census'); ap.add_argument('variants')
ap.add_argument('--workers', type=int, default=4)
ap.add_argument('--out', default=None)
a = ap.parse_args()
VARS = {k: D.DecisionOptions(**v) for k, v in json.load(open(a.variants)).items()}


def load_tags(boards, census):
    per = defaultdict(list)
    for f in glob.glob(f'{boards}/fires_base_{census}/boards_*.jsonl'):
        for line in open(f):
            r = json.loads(line)
            per[r['tag']].append(r)
    return per


def board(r):
    units = tuple(Unit(c, 1, x / 18.0, y / 32.0, h, None, None, 1.0) for c, x, y, h in r['b'])
    return SimpleNamespace(units=units, t_sec=r['tick'] * 0.05, my_elixir=r['el'])


def first_triggers(item):
    tag, recs = item
    head = next(r for r in recs if 'names' in r)
    names, grid = head['names'], head['grid']
    dec = sorted((r for r in recs if 'n' in r), key=lambda r: r['n'])
    holders = {v: SimpleNamespace() for v in VARS}
    found, cache_keys = {}, {(o.rocket_value_mode, o.rocket_value_hitbox, o.rocket_value_min_y) for o in VARS.values()}
    for r in dec:
        bs = board(r)
        allowed = [bool(r['ra']) and str(n).lower() == 'rocket' for n in names]
        vals = {}
        for key in cache_keys:                       # one best_rocket_clump per (value mode, hitbox, min_y) per decision, only if it can matter
            if r['ra'] and not r['pe']:
                vals[key] = D.best_rocket_clump(D.rocket_bodies(bs, key[0]), grid, key[1], None, key[2])[0]
        for v, o in VARS.items():
            if v in found:
                continue
            lead = o.rocket_value_lead == 'on'
            if not lead and vals.get((o.rocket_value_mode, o.rocket_value_hitbox, o.rocket_value_min_y), 0.0) + 1e-9 < o.rocket_value:
                continue
            hit = D.rocket_value_choice(o, names, allowed, bs, grid, pending=r['pe'], holder=holders[v], playing=r['pl'])
            if hit is not None:
                found[v] = dict(tag=tag, v=v, t=round(r['tick'] * 0.05, 2), value=round(hit[2], 3), el=r['el'], play=r['pl'], card=r['card'],
                                why=r['why'], n_dec=r['n'])
    return list(found.values())


if __name__ == '__main__':
    per = load_tags(a.boards, a.census)
    out_dir = f'{a.out or a.boards}/fires_base_{a.census}'
    os.makedirs(out_dir, exist_ok=True)
    with Pool(a.workers) as pool:
        res = pool.map(first_triggers, sorted(per.items()), chunksize=4)
    n = defaultdict(int)
    with open(f'{out_dir}/scout_replay.jsonl', 'w') as f:
        for lst in res:
            for r in lst:
                f.write(json.dumps(r) + '\n'); n[r['v']] += 1
    print(f'{len(per)} matches; first-trigger matches per variant: ' + ', '.join(f'{v} {n[v]}' for v in VARS))
