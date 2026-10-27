"""List the body-position first divergences of a run (unflagged, failing). python3 bp_list.py RUNDIR [INPUTS]"""
import json, os, sys
sys.path.insert(0, '/workspace/pilot/sme')
from agg_live import mech
run = sys.argv[1]
inp = sys.argv[2] if len(sys.argv) > 2 else '/workspace/pilot/inputs/inputs_rngfree.jsonl'
flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open(inp)}
for l in open(os.path.join(run, 'results.jsonl')):
    r = json.loads(l)
    m = r['match']
    if flags.get(m) or 'error' in r or (r['counts'].get('div', 0) == 0 and r['missing_in_sim'] == 0):
        continue
    e = r['episodes'][0]
    k = mech(e['detail'], any(e['start'] - 30 <= p[1] <= e['start'] for p in r['refused_plays']))
    if 'body position' in k:
        det = [d for d in e['detail'] if 'rec_only' in d[0] or 'sim_only' in d[0]][:4]
        print(m, e['start'], r['counts'].get('div'), json.dumps(det)[:400])
