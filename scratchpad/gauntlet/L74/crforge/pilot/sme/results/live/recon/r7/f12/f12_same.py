import json, sys
sys.path.insert(0, 'recon')
from r2_tally import klass, load
D = 'results/live/recon/r7/f12/'
C, R = load(D + 'f12_cyc_aff_results.jsonl'), load(D + 'f12_r7_results.jsonl')
for m in sorted(C):
    print(m[-13:], 'cyc_aff vs r7 identical (counts, first_div, edits):', (C[m]['counts'], C[m]['first_div'], C[m]['edits']) == (R[m]['counts'], R[m]['first_div'], R[m]['edits']) if m in R else 'not in r7')
