"""J6 failure split (replay_metrics.py fights output): per card, the pathing-proper crossings (both alive, not at the window edge)
by failure kind: live-only, sim-only, other lane, ticks off (> 10).  python j6split.py OUT_DIR"""
import json, glob, sys
from collections import Counter, defaultdict
kinds, byc = Counter(), defaultdict(Counter)
ex = defaultdict(list)
for f in glob.glob(sys.argv[1] + '/matches/*.json'):
    d = json.load(open(f))
    for fi in d.get('fights', []):
        for r in (fi.get('jm') or {}).get('j6', []):
            if not r.get('both_alive') or r.get('edge'):
                continue
            k = 'agree' if r['agree'] else 'live_only' if r['sim'] is None else 'sim_only' if r['live'] is None else \
                'lane' if not r['lane_agree'] else 'ticks'
            kinds[k] += 1; byc[r['card']][k] += 1
            if k != 'agree' and len(ex[k]) < 4:
                ex[k].append((d['summary']['match'], r['live'], r['sim'], r['card']))
print(dict(kinds))
for c, v in sorted(byc.items(), key=lambda kv: -sum(x for k, x in kv[1].items() if k != 'agree'))[:20]:
    n = sum(v.values())
    print(f"{c:28s} n {n:4d} agree {v['agree']/n:.2f}  live_only {v['live_only']:3d} sim_only {v['sim_only']:3d} lane {v['lane']:3d} ticks {v['ticks']:3d}")
for k, v in ex.items():
    print(k, v)
