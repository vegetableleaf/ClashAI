"""ENG-FIX5: copy a run's final plan with two commands swapped (indices I, J), run ProbeRun to T1, and print the rows of
the given SIM ids (by spawn source cmd) at ticks T0..T1 next to the live frame's rows near them.
python3 swap_probe.py RUNDIR MATCH FRAMES I J T0 T1"""
import json, os, subprocess, sys
run, m, fr = sys.argv[1:4]
I, J, t0, t1 = map(int, sys.argv[4:8])
E5 = '/workspace/pilot/engfix5'
WD = '%s/work/s_%s_%d_%d' % (E5, m[-6:], I, J)
os.makedirs(WD, exist_ok=True)
p = json.load(open(os.path.join(run, m, 'plan.json')))
p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
p['cmds'][I], p['cmds'][J] = p['cmds'][J], p['cmds'][I]
json.dump(p, open(WD + '/p.json', 'w'))
open(WD + '/jobs.txt', 'w').write('%s/p.json %d %s/o.jsonl 0\n' % (WD, t1 + 1, WD))
r = subprocess.run(['java', '-cp', E5 + '/lib_mp/lib/*:' + E5 + '/build_probe', 'ProbeRun',
                    '/workspace/crforge_cache/tables/16.635.3', WD + '/jobs.txt', '1'], capture_output=True, text=True)
print(r.stdout.strip(), r.stderr.strip()[:300])
live = {}
for l in open(os.path.join(fr, m + '.jsonl')):
    o = json.loads(l)
    live[o['t']] = o
for l in open(WD + '/o.jsonl'):
    o = json.loads(l)
    if not t0 <= o['t'] <= t1:
        continue
    rows = [e[:7] for e in o['E'] if e[1] == 'C' and e[8] in ('cmd%d' % I, 'cmd%d' % J)]
    print('t=%d SIM' % o['t'], rows)
    if o['t'] in live:
        print('      LIVE', [e for e in live[o['t']]['E'] if e[3] not in (-1,) and e[4] not in (4858, 7728)][:8])
