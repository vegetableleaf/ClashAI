"""LOOP-OPS: opponent shares of the pilot pool.

    python pool_shares.py CFG [N]          pre-run: N (512) draws in sample_matchups' order (exploiter share, then the PFSP pool at equal ratings)
    python pool_shares.py --log RECORDS    post-run: shares in a match log (one JSON per line with league.opp.id / opp.id)
Prints each opponent's count, share and the binomial band around 1/k (Bonferroni: joint 95% over the k shares) (k = pool size).
"""
import collections
import json
import math
from statistics import NormalDist
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[6]))


def report(ids, k):
    c, n = collections.Counter(ids), len(ids)
    z = NormalDist().inv_cdf(1 - 0.025 / k)              # Bonferroni over the k shares: a joint 95% band
    band = z * math.sqrt((1 / k) * (1 - 1 / k) / n)
    for i, m in sorted(c.items()):
        flag = '' if abs(m / n - 1 / k) <= band else '  OUTSIDE'
        print(f'{m:5d}  {m / n:.3f}  {i}{flag}')
    print(f'n {n}, pool {k}, expected {1 / k:.3f} +- {band:.3f} (joint 95%)')
    return all(abs(m / n - 1 / k) <= band for m in c.values()) and len(c) == k


def main(a):
    if a[0] == '--log':
        ids = []
        for ln in open(a[1]):
            r = json.loads(ln)
            o = (r.get('league') or {}).get('opp') or r.get('opp') or {}
            ids.append(o.get('id') if isinstance(o, dict) else o)
        return report(ids, len(set(ids)))
    from pipeline import adaptive_opponents as AO
    cfg = yaml.safe_load(open(a[0]))
    n = int(a[1]) if len(a) > 1 else 512
    rng = np.random.default_rng(int(cfg['seed']))
    ex = cfg.get('league_exploiters')                   # rl_royale.sample_matchups: one uniform first, below share = exploiter
    pool = AO.opponent_pool([], cfg, {})
    ids = ['exploiter:' + ex['ckpt'] if ex and rng.random() < float(ex['share']) else AO.sample_opponent(rng, [], cfg, {})['id']
           for _ in range(n)]
    return report(ids, len(pool) + bool(ex))


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:]) else 1)
