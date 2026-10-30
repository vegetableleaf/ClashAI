"""RECON-2: from the flags-off / flags-on re-extractions, write the pod input files over the 151 scored strict-fresh
matches (F2_fe .. F8_main unflagged): off_fail (the 37 not strictly exact), off_rest, on_all, and *_hidden (records with
a reader_hidden window, for the ASSIGN off guard). Prints flag changes vs the strict results."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
O = 'C:/Users/benpe/ClashBot/.foreman/scratch/recon2/'
B = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/crforge/pilot/sme/results/live/'
RUNS = {2: 'fresh2/F2_fe_results.jsonl', 3: 'fresh3/F3_fe_results.jsonl', 4: 'fresh4/F4_fe_results.jsonl',
        5: 'fresh5/F5_main_results.jsonl', 6: 'fresh6/F6_main_results.jsonl', 7: 'fresh7/F7_main_results.jsonl',
        8: 'fresh8/F8_main/results.jsonl'}
scored, fail = [], set()
for n, p in RUNS.items():
    for l in open(B + p):
        r = json.loads(l)
        if r.get('flags') or 'counts' not in r:
            continue
        scored.append(r['match'])
        if r['counts'].get('exact', 0) != r['frames']:
            fail.add(r['match'])
recs = {}
for mode in ('off', 'on'):
    recs[mode] = {}
    for n in RUNS:
        for l in open(O + '%s/f%d.jsonl' % (mode, n)):
            r = json.loads(l)
            recs[mode][r['match']] = r
miss = [m for m in scored if m not in recs['off'] or m not in recs['on']]
print('scored', len(scored), 'fail', len(fail), 'missing', miss)
def w(name, mode, ms):
    with open(O + 'sets/' + name + '.jsonl', 'w', newline='\n') as f:
        for m in ms:
            f.write(json.dumps(recs[mode][m]) + '\n')
    print(name, len(ms))
os.makedirs(O + 'sets', exist_ok=True)
w('off_fail', 'off', [m for m in scored if m in fail])
w('off_rest', 'off', [m for m in scored if m not in fail])
w('on_all', 'on', scored)
hid = [m for m in scored if recs['on'][m].get('reader_hidden') or recs['off'][m].get('reader_hidden')]
w('off_hidden', 'off', hid); w('on_hidden', 'on', hid)
for mode in ('off', 'on'):
    fl = {m: recs[mode][m].get('flags') for m in scored if recs[mode][m].get('flags')}
    print(mode, 'flagged now', len(fl), fl)
