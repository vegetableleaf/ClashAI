"""ENG-FIX5: run ProbeRun (lib_mp) on a run's final plan to tick T1 and print, per tick in [T0, T1], the SIM rows within R
units of (X, Y) with that tick's MoveProbe events for them, and the live frame's rows near the same point.
python3 pdump.py RUNDIR MATCH FRAMES T0 T1 X Y [R]"""
import json, os, subprocess, sys
run, m, fr, t0, t1, X, Y = sys.argv[1], sys.argv[2], sys.argv[3], *map(int, sys.argv[4:8])
R = int(sys.argv[8]) if len(sys.argv) > 8 else 3000
E5 = '/workspace/pilot/engfix5'
WD = '%s/work/p_%s' % (E5, m[-6:])
os.makedirs(WD, exist_ok=True)
p = json.load(open(os.path.join(run, m, 'plan.json')))
p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
json.dump(p, open(WD + '/p.json', 'w'))
open(WD + '/jobs.txt', 'w').write('%s/p.json %d %s/o.jsonl 0\n' % (WD, t1 + 1, WD))
env = dict(os.environ, SME_TGT='1')
r = subprocess.run(['java', '-cp', E5 + '/lib_mp/lib/*:' + E5 + '/build_probe', 'ProbeRun',
                    '/workspace/crforge_cache/tables/16.635.3', WD + '/jobs.txt', '1'], capture_output=True, text=True, env=env)
print(r.stdout.strip(), r.stderr.strip()[:500])
live = {}
for l in open(os.path.join(fr, m + '.jsonl')):
    o = json.loads(l)
    if t0 <= o['t'] <= t1:
        live[o['t']] = o
near = lambda x, y: abs(x - X) + abs(y - Y) <= R
for l in open(WD + '/o.jsonl'):
    o = json.loads(l)
    if not t0 <= o['t'] <= t1:
        continue
    rows = [e for e in o['E'] if e[1] in 'CT' and near(e[4], e[5])]
    ids = {e[0] for e in rows}
    print('t=%d SIM' % o['t'], [[e[0], e[2], e[3], e[4], e[5], e[6]] + e[12:] for e in rows if e[1] == 'C'])
    for ev in o.get('ev', []):
        if ev[1] in ids:
            print('    ev', ev)
    lv = live.get(o['t'])
    if lv:
        print('t=%d LIVE' % o['t'], [e for e in lv['E'] if near(e[1], e[2]) and e[4] != 4858 and e[4] != 7728])
