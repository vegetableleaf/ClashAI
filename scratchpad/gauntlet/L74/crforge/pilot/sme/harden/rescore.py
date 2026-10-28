"""SME-HARDEN: a10G1's fitted plans (no re-fit) under the hardened comparator + plant suite.
python3 rescore.py MATCH OUT.jsonl  (env.sh with SME_DIR=/workspace/pilot/sme11)"""
import json, os, sys, time
sys.path.insert(0, os.environ['SME_DIR'])
import sme_live as L
import plant_suite
from sme import run_batch

m, outp = sys.argv[1], sys.argv[2]
t0 = time.time()
rec = next(r for r in map(json.loads, open('/workspace/pilot/inputs_v29/inputs_rngfree.jsonl')) if r['match'] == m)
frames = L.load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
for h in rec.get('reader_hidden') or ():
    for t in frames:
        if h['last'] < t <= h['end']:
            frames[t].setdefault('H', []).append([h['side'], h['name'], (h['track'] or {}).get(str(t))])
me, end = rec['my_side'], max(frames)
plan = json.load(open('/workspace/pilot/sme_live/%s/%s/plan.json' % (os.environ.get('PLANS', 'a10G1'), m)))
old = json.load(open('/workspace/pilot/sme_live/a10G1/%s/result.json' % m))
work = '/dev/shm/hardenwork/rs_%s' % m
o = run_batch([(L.runnable(plan), end + 3, 0)], work)[0]
an = L.reclassify(plan, frames, me, L.analyse(o, frames, me), o, work)
by = {x['t']: x for x in o}
res = {'match': m, 'flags': rec['flags'], 'old_counts': old.get('counts'), 'counts': an['counts'], 'first': an['first'],
       'first_detail': L.describe_first(by, frames, me, an['first']),
       'changed': {t: [c0, an['cls'].get(int(t))] for t, c0 in
                   [(t, 'torn') for t in old.get('torn_ticks', [])] if an['cls'].get(int(t)) == 'div'},
       'prov': {t: p for t, p in an['prov'].items() if an['cls'][t].startswith('torn')}}
if os.environ.get('SME_PLANTS', '1') != '0':
    res['plants'] = plant_suite.run(plan, frames, me, an, o, work)
res['sec'] = round(time.time() - t0, 1)
with open(outp, 'a') as w:
    w.write(json.dumps(res, default=str) + '\n')
