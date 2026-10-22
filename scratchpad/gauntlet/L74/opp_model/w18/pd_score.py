"""W18 P-D payoff probe score: per arm, the X-Bow's lock (its lane princess loses >= 5% of a princess in the 12 s) and the
opponent's princess HP lost, PAIRED across arms on the same seeds (same live state, deck, deal); bootstrap 95% CI.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w18/pd_score.py [DIR]   (DIR: pulled w18pd_* runs)
Pays (lead 10-22) if a FRONT arm beats its NEAR arm and the policy by >= 10 pp lock."""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np

D = Path(sys.argv[1] if len(sys.argv) > 1 else 'C:/Users/benpe/pod_backup_weekend/w18')
ARMS = ('policy', 'bfront', 'bnear', 'tfront', 'tnear')


def load(arm):
    out = {}
    for f in glob.glob(str(D / f'w18pd_{arm}' / '*' / 'D3' / '*' / 'matches.jsonl')):
        for line in open(f, encoding='utf-8'):
            j = json.loads(line)
            if 'probe' in j:
                out[(j['seed'], j['tag'], j['learner_side'], j.get('opp_deck_name'))] = j['probe']
    return out


def main():
    rows = {a: load(a) for a in ARMS}
    have = [a for a in ARMS if rows[a]]
    keys = sorted(set.intersection(*(set(rows[a]) for a in have))) if have else []
    keys = [k for k in keys if all(rows[a][k]['forced'] for a in have)]
    print(f'P-D: arms {have}; {len(keys)} paired starts with our X-Bow accepted in every arm')
    if not keys:
        return
    lock = {a: np.array([rows[a][k]['lane_lost'] >= 0.05 for k in keys], float) for a in have}
    dmg = {a: np.array([rows[a][k]['lane_lost'] for k in keys], float) for a in have}
    for a in have:
        acc = np.mean([bool(rows[a][k]['answer_accepted']) for k in keys]) if a != 'policy' else float('nan')
        print(f'  {a:7s} lock {100 * lock[a].mean():5.1f}%  lane princess lost {dmg[a].mean():.3f}  scripted answer landed '
              f'{100 * acc:5.1f}%')
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(keys), size=(2000, len(keys)))
    for a, b in (('bfront', 'bnear'), ('bfront', 'policy'), ('tfront', 'tnear'), ('tfront', 'policy'), ('bfront', 'tfront'),
                 ('bnear', 'policy'), ('tnear', 'policy')):
        if a in have and b in have:
            d = lock[a] - lock[b]
            lo, hi = np.percentile(d[idx].mean(1), [2.5, 97.5])
            dd = dmg[a] - dmg[b]
            lo2, hi2 = np.percentile(dd[idx].mean(1), [2.5, 97.5])
            print(f'  {a} - {b}: lock {100 * d.mean():+5.1f} [{100 * lo:+5.1f}, {100 * hi:+5.1f}] pp | lane princess lost '
                  f'{dd.mean():+.3f} [{lo2:+.3f}, {hi2:+.3f}]')


if __name__ == '__main__':
    main()
