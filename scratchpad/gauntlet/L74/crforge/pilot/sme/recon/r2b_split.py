"""r2b_split.py A_RUNS D -- split the flags-off records by the baseline result: D/off_v2a.jsonl = not strictly exact, off_v2b = rest."""
import json, sys

A, D = sys.argv[1:3]
rc = {}
for p in (A + '/r2_fail/recon_results.jsonl', A + '/r2_rest/recon_results.jsonl'):
    for line in open(p):
        r = json.loads(line)
        rc[r['match']] = r
bad = {m for m, r in rc.items() if 'error' in r or r['counts'].get('exact', 0) != r['frames']}
recs = [line for p in (D + '/off_fail.jsonl', D + '/off_rest.jsonl') for line in open(p)]
a = [x for x in recs if json.loads(x)['match'] in bad]
b = [x for x in recs if json.loads(x)['match'] not in bad]
open(D + '/off_v2a.jsonl', 'w').writelines(a)
open(D + '/off_v2b.jsonl', 'w').writelines(b)
print(len(a), len(b))
