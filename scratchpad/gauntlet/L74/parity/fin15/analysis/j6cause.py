"""Classify j6diag failures: (M) an enemy is within 4 tiles of the live body on some row while the SIM body has no enemy within 4
tiles on that row (a missing / different opponent unit near it), (F) the two bodies' hp differ first (a fight outcome), (P) neither
(a pathing candidate).  python j6cause.py DIR"""
import json, glob, sys
from collections import Counter
cls, cards_m = Counter(), Counter()
ex = []
for f in glob.glob(sys.argv[1] + '/*.jsonl'):
    for line in open(f):
        d = json.loads(line)
        L = {r[0]: r for r in d['live']}; S = {r[0]: r for r in d['sim']}
        first = None
        for t in sorted(set(L) & set(S)):
            l, s = L[t], S[t]
            if l[4] and not s[4]:
                first = ('M', t, sorted({str(e[0]) for e in l[4]})); break
            if abs(l[3] - s[3]) > max(20, .1 * max(l[3], s[3])):
                first = ('F', t, None); break
        k = first[0] if first else 'P'
        cls[(d['card'], k)] += 1
        if k == 'M':
            for c in first[2]:
                cards_m[c] += 1
        if k == 'P' and len(ex) < 10:
            ex.append((f.split('\\')[-1].split('/')[-1][10:25], d['card'], d['t0'], d['live_cross'], d['sim_cross']))
tot = Counter()
for (c, k), n in cls.items():
    tot[k] += n
print('totals', dict(tot))
print(sorted(cls.items(), key=lambda kv: -kv[1]))
print('live enemy ids near the body with none near the SIM body:', cards_m.most_common(12))
print('pathing candidates:', ex)
