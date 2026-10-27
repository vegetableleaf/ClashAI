"""SmeRun rows (every entity class) of chosen ids over a tick range (A2c-BP4 dossier tool).
    python3 ent.py RUNDIR MATCH T0 T1 ID [ID ...]      (MATCH like 20261027_000233; LIB env = engine lib)"""
import json, os, subprocess, sys
run, m, t0, t1 = sys.argv[1], 'live_play_' + sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
ids = {int(x) for x in sys.argv[5:]}
WD = '/workspace/pilot/bp4/work/ent_%s' % sys.argv[2]
os.makedirs(WD, exist_ok=True)
p = json.load(open(os.path.join(run, m, 'plan.json')))
p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
json.dump(p, open(WD + '/p.json', 'w'))
open(WD + '/jobs.txt', 'w').write('%s/p.json %d %s/o.jsonl %d\n' % (WD, t1 + 1, WD, t0))
lib = os.environ.get('LIB', '/workspace/pilot/bp4/lib_bp4')
subprocess.run(['java', '-cp', lib + '/*:/workspace/pilot/bp4/from33920/sme/build_008aa626', 'SmeRun',
                '/workspace/crforge_cache/tables/16.402.22', WD + '/jobs.txt', '1'], check=True, capture_output=True)
for l in open(WD + '/o.jsonl'):
    o = json.loads(l)
    if t0 <= o['t'] <= t1:
        print('t=%d' % o['t'], [e for e in o['E'] if e[0] in ids])
