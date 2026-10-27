"""Summary of aim_census rows: outcome by (ref_mode, by_ref_move), all exact-pre events and clean ones (t <= first_div). python aim_sum.py ROWS.jsonl"""
import json, collections, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
pre = [r for r in rows if r.get('pre') and r['out'] != 'nodisc']
def clean(r): return r['first_div'] is None or r['t'] <= r['first_div']
for lab, sel in (('all pre', pre), ('clean', [r for r in pre if clean(r)])):
    c = collections.defaultdict(collections.Counter)
    for r in sel:
        c[(r.get('ref_mode'), r.get('by_ref_move'))][r['out']] += 1
    print('==', lab)
    for k, v in sorted(c.items(), key=str): print('  ', k, dict(v))
print('clean by_ref_move rows:')
for r in pre:
    if clean(r) and r.get('by_ref_move'):
        print(' ', r['m'], r['t'], r['name'], r['ref_mode'], r['out'], r.get('disc0'), r.get('same_alt'), r['aim_d'])
