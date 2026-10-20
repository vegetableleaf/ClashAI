"""Print one j6diag body's live / SIM tracks side by side.  python j6trace.py FILE.jsonl CARD [INDEX] [STRIDE]"""
import json, sys
f, card = sys.argv[1], sys.argv[2]
idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
stride = int(sys.argv[4]) if len(sys.argv) > 4 else 4
ds = [json.loads(x) for x in open(f) if json.loads(x)['card'] == card]
d = ds[idx]
print(d['card'], 'fight', d['t0'], '-', d['t1'], 'live cross', d['live_cross'], 'sim cross', d['sim_cross'])
L = {r[0]: r for r in d['live']}; S = {r[0]: r for r in d['sim']}
for t in sorted(set(L) | set(S))[::stride]:
    l, s = L.get(t), S.get(t)
    print(t, 'L', l and l[1:4], 'S', s and s[1:4], '| enemies L', l and l[4][:2], 'S', s and s[4][:2])
