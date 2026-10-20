"""Per-card values of the replay metrics (J2 victim, J5a deploy, J6 pathing) from a replay_metrics.py fights/whole output dir.

  python percard.py OUT_DIR [MIN_N]      -> a markdown table on stdout (cards with n >= MIN_N on any metric; default 10)
"""
from collections import defaultdict
import json
from pathlib import Path
import sys

FORMS = ('', ' evo', ' hero')


def main(out, min_n=10):
    j2, j6, j5 = defaultdict(list), defaultdict(list), defaultdict(list)
    for p in sorted(Path(out, 'matches').glob('*.json')):
        d = json.loads(p.read_text())
        for f in d.get('fights', []):
            jm = f.get('jm') or {}
            for r in jm.get('j2', []):
                if 'err' in r:
                    j2[r['victim'].split(' ', 1)[1]].append(r['agree'])
            for r in jm.get('j6', []):
                if r.get('both_alive') and not r.get('edge'):
                    j6[r['card'].split(' ', 1)[1]].append(r['agree'])
            for b in f.get('bodies', []):
                if b.get('deploy_live') is not None and b.get('deploy_sim') is not None and not b.get('setup'):
                    j5[b['name'] + FORMS[b.get('form') or 0]].append(abs(b['deploy_live'] - b['deploy_sim']) <= 3)
    cards = sorted(set(j2) | set(j6) | set(j5), key=lambda c: (-(len(j2[c]) + len(j6[c]) + len(j5[c])), c))
    cell = lambda xs: f'{sum(xs) / len(xs):.2f} ({len(xs)})' if xs else ''
    print('| card | J2 spell effect on it, agree (n) | J5a deploy, agree (n) | J6 pathing, agree (n) |')
    print('|---|---|---|---|')
    for c in cards:
        if max(len(j2[c]), len(j6[c]), len(j5[c])) >= min_n:
            print(f'| {c} | {cell(j2[c])} | {cell(j5[c])} | {cell(j6[c])} |')


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10)
