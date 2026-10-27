"""MoveProbe events of one match over a tick range (A2c-BP3 dossier tool).
    python3 aim_one.py RUNDIR MATCH T0 T1 [ID ...]     (MATCH like 20261027_000233)
Prints per tick the replan / disp events (only for IDs if given) and the listed bodies' end-of-step points, and the
recorded bodies (frames2) of the same side within 80 units of each listed body."""
import json, os, subprocess, sys
run, m, t0, t1 = sys.argv[1], 'live_play_' + sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
ids = {int(x) for x in sys.argv[5:]}
WD = '/workspace/pilot/bp3/work/one_%s' % sys.argv[2]
os.makedirs(WD, exist_ok=True)
p = json.load(open(os.path.join(run, m, 'plan.json')))
p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
json.dump(p, open(WD + '/p.json', 'w'))
open(WD + '/jobs.txt', 'w').write('%s/p.json %d %s/o.jsonl 0\n' % (WD, t1 + 1, WD))
lib = os.environ.get('LIB', '/workspace/pilot/bp3/lib_bp3')
subprocess.run(['java', '-cp', lib + '/*:/workspace/pilot/bp3/build_aim', 'AimRun', '/workspace/crforge_cache/tables/16.402.22',
                WD + '/jobs.txt', '1'], check=True, capture_output=True)
fr = {}
for l in open('/workspace/pilot/sme_live/frames2/%s.jsonl' % m):
    f = json.loads(l)
    if t0 <= f['t'] <= t1:
        fr[f['t']] = f['E']
for l in open(WD + '/o.jsonl'):
    o = json.loads(l)
    if not t0 <= o['t'] <= t1:
        continue
    ev = [e for e in o['ev'] if not ids or e[1] in ids]
    cs = [c for c in o['C'] if not ids or c[0] in ids]
    print('t=%d' % o['t'], *ev)
    for c in cs:
        rec = [(e[1] - c[3], e[2] - c[4]) for e in fr.get(o['t'], []) if e[0] == c[2] and abs(e[1] - c[3]) + abs(e[2] - c[4]) < 80]
        print('   ', c, 'rec-sim' if o['t'] in fr else 'noframe', rec if o['t'] in fr else '')
