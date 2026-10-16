"""Per Log cast: SIM - live first-hit tick on bodies hit in both (median per cast), plus the tap->cast delay used."""
import json, sys, statistics
from collections import defaultdict, Counter
rows = [json.loads(l) for l in open(sys.argv[1])]
ev = defaultdict(list)
for r in rows:
    if r['live_hit'] and r['sim_hit']:
        ev[r['match'], r['tL']].append(r['sim_hit']-r['live_hit'])
med = {k: statistics.median(v) for k, v in ev.items()}
print('casts with a both-hit body', len(med), 'per-cast median sim-live:', sorted(Counter(round(v) for v in med.values()).items()))
print('within-cast spread (max-min) >4:', sum(max(v)-min(v) > 4 for v in ev.values()))
