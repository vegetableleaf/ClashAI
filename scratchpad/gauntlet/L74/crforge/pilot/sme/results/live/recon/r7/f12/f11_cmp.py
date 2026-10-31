import sys, json
sys.path.insert(0, 'recon')
from r2_tally import klass, load
R = 'C:/Users/benpe/ClashBot/.foreman/scratch/recon6/f11/'
import glob, os
print(os.listdir('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/results/live/recon/r6')[:3])
V = load('results/live/recon/r6/f11_v3_results.jsonl'); C = load('results/live/recon/r6/f11_cycform_results.jsonl'); R7 = load('results/live/recon/r7/f11/f11_r7_results.jsonl')
base = dict(V); base.update(C)
chg = 0
for m in sorted(R7):
    b = base[m]; r = R7[m]
    same = (b['counts'], b['first_div'], b['edits']) == (r['counts'], r['first_div'], r['edits'])
    if not same:
        chg += 1
        print(m[-13:], 'RECON-5+forms class', klass(b), 'first_div', b['first_div'], '-> RECON-7 class', klass(r), 'first_div', r['first_div'], [e for e in r['edits'] if 'press' in e], 'flags', r.get('flags'))
print('records in the RECON-7 set', len(R7), 'rows that differ from RECON-5 + forms:', chg)
print('classes RECON-5+forms', sorted(klass(base[m]) for m in R7), '\n        RECON-7      ', sorted(klass(R7[m]) for m in R7))
