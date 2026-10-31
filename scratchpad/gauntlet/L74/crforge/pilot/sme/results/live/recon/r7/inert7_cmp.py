import json, sys
def load(p): return {json.loads(l)['match']: json.loads(l) for l in open(p)}
key = lambda r: (r['counts'], r['first_div'], r['edits'])
for new, old in (('r7_in_f9', 'smeR4/runs/f9_cyc_aff'), ('r7_in_dev', 'smeR4/runs/d49_cyc2'), ('r7_inL_f9', 'smeR4/runs/f9_cyc_aff'), ('r7_inL_dev', 'smeR4/runs/d49_cyc2')):
    try:
        N = load('/workspace/smeR6/runs/%s/recon_results.jsonl' % new); O = load('/workspace/%s/recon_results.jsonl' % old)
    except Exception as e:
        print(new, 'missing', e); continue
    same = sum(1 for m, r in N.items() if key(r) == key(O[m]))
    print(new, len(N), 'identical (counts, first_div, edits):', same)
    for m, r in N.items():
        if key(r) != key(O[m]): print('  DIFF', m, r['counts'], O[m]['counts'], r['edits'], O[m]['edits'])
