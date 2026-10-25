"""Paired win rates of run_skew.sh arms (same chunk + seed = same match setup). Usage: pair_arms.py OUT [OUT ...]
Also reads the gate eval rows of the running mem_o_s105_u0000 E4 eval (``--ref DIR``, its D3 dir) as arm 'ref'."""
import json
import random
import sys
from pathlib import Path


def rows(d):
    out = {}
    for f in sorted(Path(d).glob('[0-9]*/matches.jsonl')):
        for s in f.read_text().splitlines():
            if s.strip():
                r = json.loads(s)
                out[(f.parent.name, r['seed'])] = r
    return out


def main():
    args = sys.argv[1:]
    ref = None
    if '--ref' in args:
        i = args.index('--ref')
        ref = args[i + 1]
        del args[i:i + 2]
    A = {}
    for o in args:
        for arm in ('real', 'empty', 'base', 'delta', 'shadow'):
            for k, v in rows(Path(o) / arm).items():
                A.setdefault(arm, {})[(o,) + k] = v
    if ref:
        A['ref'] = {(o,) + k: v for o in args for k, v in rows(ref).items()}
    import os
    keep = os.environ.get('PAIR_ARMS')
    A = {a: v for a, v in A.items() if not keep or a in keep.split(',')}
    need = list(A)
    keys = set.intersection(*[set(A[a]) for a in need]) if A else set()
    print(f'paired matches (all arms present): {len(keys)}')
    win = {a: {k: A[a][k]['outcome'] == 'win' for k in keys} for a in A}
    for a in A:
        r = [A[a][k] for k in keys]
        n = len(r) or 1
        print(f'{a:6s} win {sum(win[a].values())}/{len(keys)} = {100 * sum(win[a].values()) / n:.1f}%  plays/game '
              f'{sum(x["plays_accepted"] for x in r) / n:.1f}  opp plays/game {sum(x["opp_plays_accepted"] for x in r) / n:.1f}  '
              f'decisions {sum(x["decisions"] for x in r) / n:.0f}  tower HP diff {sum(x["tower_hp_diff"] for x in r) / n:+.0f}')
    rng = random.Random(0)
    ks = sorted(keys)
    for a, b in (('real', 'base'), ('empty', 'base'), ('real', 'empty'), ('delta', 'base'), ('delta', 'real'), ('shadow', 'base'), ('real', 'ref')):
        if a in win and b in win and ks:
            d = [win[a][k] - win[b][k] for k in ks]
            bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(4000))
            print(f'{a} - {b}: {100 * sum(d) / len(d):+.1f} pp [{100 * bs[100]:+.1f}, {100 * bs[3899]:+.1f}]  '
                  f'identical outcomes {sum(x == 0 for x in d)}/{len(d)}')
    if 'ref' in A and 'real' in A:
        same = sum(A['ref'][k]['tower_hp_diff'] == A['real'][k]['tower_hp_diff'] for k in keys)
        print(f'real vs ref (hooks are read-only): identical tower_hp_diff {same}/{len(keys)}')


if __name__ == '__main__':
    main()
