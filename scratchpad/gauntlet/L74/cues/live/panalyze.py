"""Per-float agreement of the 22 cue floats, live builder vs SIM extract (pcollect.py output).

    python panalyze.py out/*.jsonl.gz

A = the body was on the board at the fight start and dt <= 20 ticks (the SIM state is the seeded live state: mostly
DEFINITION disagreement); B = every other paired frame (definition + SIM divergence). Only aligned pairs (<= 250 mt).
"""
import collections
import gzip
import json
import sys

F = (['known'] + ['st_' + s for s in ('idle', 'moving', 'engaged', 'deploying', 'jumping', 'tunnelling', 'casting')]
     + ['charging', 'tesla_hidden', 'has_target', 'target_tower'] + ['ph_' + s for s in ('idle', 'windup', 'hit')]
     + ['frac'] + ['frozen', 'slowed', 'raged', 'invisible', 'shielded'] + ['slow_frac'])
TOL = {15: 0.10, 21: 0.15}
rows = {'A': [], 'B': []}
for p in sys.argv[1:]:
    for line in gzip.open(p, 'rt'):
        r = json.loads(line)
        if r[0] == 'err' or r[2] > 250:
            continue
        rows['A' if r[0] <= 20 and r[1] else 'B'].append(r)


def agree(i, lv, sv):
    return abs(lv[i] - sv[i]) <= TOL.get(i, 0.001)


print('aligned paired body-frames: A %d, B %d' % (len(rows['A']), len(rows['B'])))
print('%-14s %-22s %-22s %s' % ('float', 'A agree', 'B agree', 'B counts: live!=0 / sim!=0 / both'))
worst = {}
for i, name in enumerate(F):
    out = []
    for k in 'AB':
        n = len(rows[k])
        a = sum(agree(i, r[4], r[5]) for r in rows[k])
        out.append('%.4f (%d/%d)' % (a / n if n else float('nan'), a, n))
    B = rows['B']
    l1, s1 = sum(r[4][i] != 0 for r in B), sum(r[5][i] != 0 for r in B)
    both = sum(r[4][i] != 0 and r[5][i] != 0 for r in B)
    print('%-2d %-11s %-22s %-22s %d / %d / %d' % (i, name, out[0], out[1], l1, s1, both))
    bad = collections.Counter((r[3], 'live>sim' if r[4][i] > r[5][i] else 'sim>live') for r in B if not agree(i, r[4], r[5]))
    worst[name] = bad.most_common(5)
for k in 'AB':
    n = len(rows[k])
    allb = sum(all(agree(i, r[4], r[5]) for i in range(22)) for r in rows[k])
    print('%s: all 22 floats agree on %.4f (%d/%d) of body-frames' % (k, allb / n if n else 0, allb, n))
# mean absolute difference of the whole vector = what the projection sees, A / B
for k in 'AB':
    d = [sum(abs(a - b) for a, b in zip(r[4], r[5])) for r in rows[k]]
    print('%s: mean L1 |live - sim| per body-frame %.4f' % (k, sum(d) / max(1, len(d))))
print('\nlargest B disagreements by unit name (name, direction): count')
for name in F[1:]:
    if worst[name]:
        print('  %-12s %s' % (name, worst[name]))
