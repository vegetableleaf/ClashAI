"""Summarise j6diag dumps: per failing body, the kind (sim-only / live-only / ticks), and the y each run reached plus whether an
enemy was within 4 tiles when the other run crossed.  python j6show.py DIR [N_EXAMPLES]"""
import json, glob, sys
from collections import Counter
kinds, why = Counter(), Counter()
rows = []
for f in glob.glob(sys.argv[1] + '/*.jsonl'):
    for line in open(f):
        d = json.loads(line)
        cl, cs = d['live_cross'], d['sim_cross']
        k = 'sim_only' if cl is None else 'live_only' if cs is None else 'lane' if cl[1] != cs[1] else 'ticks'
        kinds[(d['card'], k)] += 1
        # at the crossing tick of the run that crossed (first if both): where was the other one, and had it an enemy near?
        t = (cs or cl)[0]
        def at(track):
            return min(track, key=lambda r: abs(r[0] - t)) if track else None
        L, S = at(d['live']), at(d['sim'])
        side_fwd = 1 if (d['live'][0][2] < 16000) else -1
        stuck = L and S and ((S[2] - L[2]) * side_fwd)
        rows.append((f.split('/')[-1].split('\\')[-1][10:25], d['card'], k, cl, cs, L and (L[1], L[2], L[3], len(L[4])), S and (S[1], S[2], S[3], len(S[4])), stuck))
        if k == 'sim_only':
            why['live had an enemy within 4 tiles at the SIM crossing' if L and L[4] else 'live had none'] += 1
print(sorted(kinds.items(), key=lambda kv: -kv[1]))
print(dict(why))
for r in rows[:int(sys.argv[2]) if len(sys.argv) > 2 else 25]:
    print(r)
