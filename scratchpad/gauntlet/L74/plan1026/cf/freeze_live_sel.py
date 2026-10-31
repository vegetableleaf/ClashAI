"""FREEZE-LIVE step 1 (laptop): from freeze_live_collect.py's rows (fl_rows.jsonl, one per (run, match)) pick, per match, the plan with the
fewest div frames (ties: fewest RECON-added presses, gate plans first) and keep the fully exact ones that contain a Hero IceWizard press.
  python -I freeze_live_sel.py ROWS.jsonl SEL.jsonl"""
import collections
import json
import sys

rows = [json.loads(l) for l in open(sys.argv[1])]


def iw(r):
    return [p for p in r['presses'] if p['card'] == 'IceWizard' and p['slotflag'] == 2]


def key(r):
    nadd = sum(1 for p in iw(r) if p['src'] == 'recon_add')
    gate = 0 if 'gate' in r['run'] else 1
    return (r['counts'].get('div', 0), nadd, gate, -r['frames'])


by = collections.defaultdict(list)
for r in rows:
    if r['frames']:
        by[r['match']].append(r)
sel = []
for m, rs in by.items():
    b = min(rs, key=key)
    if b['counts'].get('div', 0) == 0 and iw(b):
        sel.append(b)
print(len(sel), 'selected; presses', sum(len(iw(b)) for b in sel))
print('press source:', collections.Counter(p['src'] for b in sel for p in iw(b)))
print('run of best:', collections.Counter(b['run'] for b in sel).most_common(12))
with open(sys.argv[2], 'w') as w:
    for b in sel:
        w.write(json.dumps({'match': b['match'], 'path': b['path'], 'run': b['run']}) + '\n')
