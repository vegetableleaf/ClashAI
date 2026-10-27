"""Re-run a fitted plan with one command changed and print the window diff count per frame:
python3 variant.py PLAN.json CMD_INDEX FIELD=VALUE[,FIELD=VALUE] LO HI OUTDIR"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sme import load_frames, canon_rec, canon_sim, diff, run_batch
plan = json.load(open(sys.argv[1]))
k = int(sys.argv[2])
v = json.loads(json.dumps(plan))
for kv in sys.argv[3].split(','):
    f, x = kv.split('=')
    v['cmds'][k][f] = int(x) if x.lstrip('-').isdigit() else x
    if f == 'run': v['cmds'][k]['given'] = int(x) - 20
lo, hi = int(sys.argv[4]), int(sys.argv[5])
rec = load_frames(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/rec.jsonl'), key='f')
outs = run_batch([(plan, hi + 1, lo), (v, hi + 1, lo)], sys.argv[6])
for name, o in zip(('base', 'variant'), outs):
    by = {x['t']: x for x in o}
    ds = [(t, len(diff(canon_rec(rec[t]), canon_sim(by[t])))) for t in range(lo, hi + 1) if t in rec and t in by]
    print(name, 'total', sum(n for _, n in ds), 'nonzero', [(t, n) for t, n in ds if n][:30])
