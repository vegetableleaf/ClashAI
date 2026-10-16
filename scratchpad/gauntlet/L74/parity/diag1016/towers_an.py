"""Classify the failing towers of towers.py output."""
import json, sys
from collections import Counter, defaultdict
R = [json.loads(l) for l in open(sys.argv[1])]
seen = set(); C = Counter(); ex = defaultdict(list); vals = Counter()
for r in R:
    for t in r['towers']:
        key = (r['match'], r['t0'], t['tower'])
        if key in seen: continue          # the same fight window can repeat across anchors only by t0; keep unique
        seen.add(key)
        d = [x[1] for x in t['live_drops'] + t['sim_drops']]
        if not t['own'] and d and all(x % 98 == 0 for x in d):
            c = 'own X-Bow on tower: hit count/timing'
        elif t['live_drops'] and not t['near_live'] and not t['sim_drops']:
            c = 'live-only hit, no live enemy within 9 tiles (unseen opp spell)'; vals[tuple(x[1] for x in t['live_drops'])] += 1
        elif t['sim_drops'] and not t['near_sim'] and not t['live_drops']:
            c = 'SIM-only hit, no SIM enemy within 9 tiles'
        elif {n for _, n in t['near_live'][:3]} != {n for _, n in t['near_sim'][:3]}:
            c = 'attackers differ (earlier survival/position cascade)'
        else:
            c = 'same attackers, different hits (attack timing/phase)'
        C[c] += 1; ex[c].append(f"{r['match'][-6:]}@{r['t0']}:{t['tower']}+{t['first_tick']}")
n = sum(C.values())
for c, k in C.most_common():
    print(f'{k:3d} ({k/n:.0%}) {c}; e.g. {ex[c][:4]}')
print('unseen live hit amounts:', vals.most_common())
print('first divergence <= 40 ticks after t0:', sum(1 for r in R for t in r['towers'] if t['first_tick'] <= 40), 'of', sum(len(r['towers']) for r in R))
