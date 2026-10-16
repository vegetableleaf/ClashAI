"""RT35 re-baseline comparison: old engine (royalesim 0.1.33, 20261012-linux) vs new (0.1.35, 20261016-linux), D3, 960 games
(seeds 741200 + 742000) per checkpoint and set.

    python rt_cmp.py NEW_DIR [--old-root C:/Users/benpe/pod_backup_weekend]

NEW_DIR = /workspace/results/RT35 (rebaseline_pod.sh: <set>_<name>_<seed>/D3/matches.jsonl). OLD = the runs the old numbers
came from (paths under --old-root below). Games pair on (census, seed) when opp_deck / learner_side / opponent sha agree on
every key (the opponent draw does not depend on the engine); otherwise the engine row is reported UNPAIRED (two-proportion CI).
Per set: (1) per checkpoint new - old; (2) new-engine f1u250 - r1 and f1u250 - f1u65, beside the old-engine deltas, and the
change of each delta (difference in differences; is the ranking preserved?). 10,000 bootstrap draws within census x side.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

SEEDS = (741200, 742000)
NAMES = ('f1u250', 'f1u65', 'r1')
OLD = {('live', 'f1u250'): 'pod1015_s5/LIVEEVAL/f1u250_{s}', ('live', 'f1u65'): 'pod1015_s5/LIVEEVAL/f1u65_{s}',
       ('live', 'r1'): 'pod1015_s5/LIVEEVAL/r1_{s}',
       ('std', 'f1u250'): 'pod1014b_arms/rlarm_gae_to250/D3_{s}', ('std', 'f1u65'): 'pod1014b_arms/rlarm_gae/D3_{s}',
       ('std', 'r1'): 'pod1014b_twin/TWIN_live_{s}'}
OLD_WINS = {('live', 'f1u250'): 580, ('live', 'f1u65'): 506, ('live', 'r1'): 427,
            ('std', 'f1u250'): 521, ('std', 'f1u65'): 467, ('std', 'r1'): 402}


def load(pattern):
    rows = {}
    for s in SEEDS:
        p = Path(pattern.format(s=s))/'D3/matches.jsonl'
        if not p.is_file():
            return None
        for line in p.read_text(encoding='utf8').splitlines():
            if line.strip():
                r = json.loads(line)
                key = r['census'], r['seed']
                if key in rows or r['outcome'] not in ('win', 'loss', 'draw'):
                    raise ValueError(f'{p}: duplicate/invalid row {key}')
                rows[key] = r
    return rows


def pairable(*runs):
    keys = runs[0].keys()
    return all(r.keys() == keys for r in runs) and all(
        len({(tuple(r[k]['opp_deck']), r[k]['learner_side'], r[k].get('opp_gen_sha256')) for r in runs}) == 1
        for k in keys)


def win(r):
    return int(r['outcome'] == 'win')


def boot(runs, coef):
    """Paired: per key sum(c * win), resampled within (census, learner_side) strata; returns delta pp and 95% CI."""
    base = runs[0]
    strata = {}
    for k in sorted(base):
        strata.setdefault((k[0], base[k]['learner_side']), []).append(sum(c*win(r[k]) for c, r in zip(coef, runs)))
    rng = np.random.default_rng(20261016)
    b = np.zeros(10000)
    for v in strata.values():
        v = np.asarray(v)
        b += v[rng.integers(len(v), size=(len(b), len(v)))].sum(axis=1)
    n = len(base)
    return 100*sum(map(sum, strata.values()))/n, (100*np.quantile(b/n, [.025, .975])).tolist()


def unpaired(a, b):
    pa, pb = sum(map(win, a.values()))/len(a), sum(map(win, b.values()))/len(b)
    se = math.sqrt(pa*(1-pa)/len(a)+pb*(1-pb)/len(b))
    d = 100*(pb-pa)
    return d, [d-196*se, d+196*se]


def fmt(d, ci, tag='paired'):
    return f'{d:+6.2f} pp [{ci[0]:+.2f}, {ci[1]:+.2f}] ({tag})'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('new', type=Path)
    ap.add_argument('--old-root', type=Path, default=Path('C:/Users/benpe/pod_backup_weekend'))
    a = ap.parse_args()
    for st, label in (('live', 'LIVE-MIRRORED POOL'), ('std', 'STANDARD SET (CAL c)')):
        print(f'== {label}: D3, seeds 741200 + 742000; draws count as non-wins')
        old = {n: load(str(a.old_root/OLD[st, n])) for n in NAMES}
        new = {n: load(str(a.new/f'{st}_{n}_{{s}}')) for n in NAMES}
        for n in NAMES:
            o, w = old[n], new[n]
            if o is None or w is None:
                print(f'  {n:7s} missing ({"old" if o is None else "new"})')
                continue
            ow, nw = sum(map(win, o.values())), sum(map(win, w.values()))
            check = '' if ow == OLD_WINS[st, n] else f'  (!! old file gives {ow}, expected {OLD_WINS[st, n]})'
            d = fmt(*boot([o, w], [-1, 1])) if pairable(o, w) else fmt(*unpaired(o, w), 'UNPAIRED')
            print(f'  {n:7s} old {ow}/{len(o)} ({100*ow/len(o):.1f}%)  new {nw}/{len(w)} ({100*nw/len(w):.1f}%)  '
                  f'new-old {d}{check}')
        for other in ('r1', 'f1u65'):
            if any(x[m] is None for x in (old, new) for m in ('f1u250', other)):
                continue
            runs = [old['f1u250'], old[other], new['f1u250'], new[other]]
            if not pairable(*runs):
                print(f'  f1u250 - {other}: keys/decks differ across runs; paired deltas not computed')
                continue
            print(f'  f1u250 - {other:6s} old {fmt(*boot(runs, [1, -1, 0, 0]))}  new {fmt(*boot(runs, [0, 0, 1, -1]))}  '
                  f'change {fmt(*boot(runs, [-1, 1, 1, -1]))}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
