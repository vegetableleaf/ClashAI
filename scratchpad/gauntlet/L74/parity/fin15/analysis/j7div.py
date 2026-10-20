"""J7 first divergence census over METRICS_J whole/matches: which tower (own/opp), sign, and the cards in the 12 s before."""
import json, glob, sys, statistics
from collections import Counter
D = sys.argv[1]
rows = []
for f in sorted(glob.glob(D + '/whole/matches/*.json')):
    d = json.load(open(f))
    s = d.get('summary') or {'match': f}; side = s.get('side')
    for fi in d.get('fights', []):
        j = fi.get('j7') or (fi.get('jm') or {}).get('j7')
        if not j:
            continue
        fd = j.get('first_div')
        rows.append((s['match'], side, j, fd))
print('matches', len(rows), 'with first_div', sum(1 for r in rows if r[3]))
own_opp = Counter(); sign = Counter(); cards = Counter(); cards_own = Counter(); ticks = []
detail = []
for m, side, j, fd in rows:
    if not fd:
        continue
    ticks.append(fd['tick'])
    for k in fd['towers']:
        whose = 'own' if int(k[1]) == side else 'opp'
        d = fd['sim'][k] - fd['live'][k]
        own_opp[whose] += 1
        sign[(whose, 'sim_more_dmg' if d < 0 else 'sim_less_dmg')] += 1
        detail.append((m, fd['tick'], k, whose, fd['live'][k], fd['sim'][k], d, [p[1] + ':' + p[2] for p in fd['plays']]))
    for p in fd['plays']:
        cards[p[1] + ':' + p[2]] += 1
print('first div tick median', statistics.median(ticks), 'quartiles', statistics.quantiles(ticks, n=4))
print('tower whose', dict(own_opp)); print('sign', dict(sign))
print('cards in 12 s before (match count weighted by play):', cards.most_common(40))
print('seq_same', sum(r[2]['seq_same'] for r in rows), '/', len(rows))
json.dump(detail, open(D + '/j7div_detail.json', 'w'))
for x in detail[:40]:
    print(x)
