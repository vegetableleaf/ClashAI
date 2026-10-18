"""Per card: strict n vs fights blocked from strict, by blocker (a fight can carry several) -> BLOCKERS.txt
usage: python blockers.py rows_fin12st.tsv CARD [CARD ...]   (no cards: totals + top cards)"""
import sys
from collections import Counter, defaultdict
n, blk, solo = Counter(), defaultdict(Counter), defaultdict(Counter)
for ln in open(sys.argv[1], encoding='utf-8'):
    c = ln.rstrip('\n').split('\t')
    if c[3] == '1':
        n[c[2]] += 1
        continue
    b = [x for x in c[10].split(',') if x]
    for x in b:
        blk[c[2]][x] += 1
    if len(b) == 1:
        solo[c[2]][b[0]] += 1
tot, tsolo = Counter(), Counter()
for k in blk:
    tot.update(blk[k]); tsolo.update(solo[k])
print('ALL: strict', sum(n.values()), '; blocked by ONE blocker only', sum(sum(v.values()) for v in solo.values()))
for b, v in tot.most_common():
    print(f"  {b}: on {v} fights, the ONLY blocker on {tsolo[b]}")
for k in sys.argv[2:]:
    print(f"{k}: strict {n[k]}; sole blockers " + ', '.join(f"{b} {v}" for b, v in solo[k].most_common()))
