import json, sys
sys.path.insert(0, 'recon')
from r2_tally import klass, load
D = 'results/live/recon/r7/f12/'
G, V, C, F, R = (load(D + 'f12_%s_results.jsonl' % n) for n in ('gate', 'v3', 'cyc_aff', 'cycform', 'r7'))
C2 = dict(V); C2.update(C); R2 = dict(C2); R2.update(F); R2.update(R)
print('flagged records (v3 flags) and per pipeline class:')
for m in sorted(V):
    fl = V[m].get('flags')
    row = lambda P: klass(P[m]) if m in P and 'error' not in P[m] else 'E'
    if fl or klass(V[m]) == 0 or klass(R2[m]) != klass(V[m]) or m in R:
        print(m[-13:], 'flags', fl, 'gate', row(G), 'v3', row(V), 'recon5', row(C2), 'recon7', row(R2), '| r7 edits', [e for e in R2[m]['edits'] if not e.startswith('shift')][:6], '| first_div v3/r7', V[m]['first_div'], R2[m]['first_div'])
