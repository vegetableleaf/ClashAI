"""Miss mass by round-7 bucket and tier (joined.tsv + census) -> stdout.
usage: python buckets.py joined.tsv CENSUS.json"""
import json, sys
from collections import defaultdict
R7 = {'r7a': {'own Skeletons'}, 'r7b': {'own Tesla', 'own Tesla evo', 'own IceWizard hero'},
      'r7c': {'own Knight', 'own Knight evo', 'own Rocket', 'own Tornado'},
      'r7d': {'opp HogRider', 'opp Witch', 'opp Witch evo', 'opp Bats', 'opp Bats evo', 'opp Firecracker', 'opp Firecracker evo',
              'opp SkeletonArmy', 'opp SkeletonArmy evo', 'opp GoblinGang'}}
if __name__ == '__main__':
    cen = json.load(open(sys.argv[2], encoding='utf-8'))
    tot = sum(cen['plays'].values())
    share = {k: v/tot for k, v in cen['plays'].items()}
    mass, rec, cnt = defaultdict(float), defaultdict(float), defaultdict(int)
    for ln in open(sys.argv[1], encoding='utf-8'):
        c = ln.rstrip('\n').split('\t')
        card, aK, ceil = c[2], float(c[3]), float(c[4]) if c[4] not in ('', 'None') else 1.
        b = next((k for k, v in R7.items() if card in v), None)
        if b is None:
            b = 'own other (X-Bow, Log)' if card.startswith('own ') else 'opp tier B (not r7d)' if share.get(card, 0) >= .003 \
                else 'opp tier C only' if share.get(card, 0) >= .002 else 'opp below tier C'
        mass[b] += 1 - aK; rec[b] += max(0., ceil - aK); cnt[b] += 1
    T = sum(mass.values())
    print('bucket | failing fights | miss mass | share of mass | recoverable to ceiling')
    for b in sorted(mass, key=lambda b: -mass[b]):
        print(f"{b} | {cnt[b]} | {mass[b]:.1f} | {mass[b]/T:.3f} | {rec[b]:.1f}")
    print(f"TOTAL | {sum(cnt.values())} | {T:.1f} | 1 | {sum(rec.values()):.1f}")
