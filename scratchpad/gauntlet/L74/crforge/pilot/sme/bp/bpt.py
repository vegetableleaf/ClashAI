"""Per-tick trace, sim vs reader, for named bodies (A2c-BP). Runs BpRun (state + target per body).
  python3 bpt.py PLAN.json MATCH LO HI SIMNAMES RECCARDS [cmd_index:run ...]
SIMNAMES: comma list of crforge row-name substrings; RECCARDS: comma list of reader card ids. Prints, per tick, the sim
rows [id name x y hp tgt state buffs] and, on recorded ticks, the reader rows [x y hp gen tgt_gen state buffs]."""
import json, os, subprocess, sys
IDS = {int(x) for x in os.environ.get('BPT_IDS', '').split(',') if x}
plan, m, lo, hi, names, cards = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5].split(','), \
    {int(c) for c in sys.argv[6].split(',')}
p = json.load(open(plan))
p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
for a in sys.argv[7:]:
    i, r = map(int, a.split(':'))
    p['cmds'][i].update(run=r, given=r - 20)
    print('cmd', i, '->', p['cmds'][i])
wd = '/workspace/pilot/bp/work/bpt_%d' % os.getpid()
os.makedirs(wd, exist_ok=True)
json.dump(p, open(wd + '/p.json', 'w'))
open(wd + '/jobs.txt', 'w').write('%s/p.json %d %s/o.jsonl %d\n' % (wd, hi + 1, wd, lo))
r = subprocess.run(['java', '-Xmx8g', '-cp', '/workspace/pilot/lib_008aa626/*:/workspace/pilot/bp/build_bpx', 'BpRun',
                    '/workspace/crforge_cache/tables/16.402.22', wd + '/jobs.txt', '1'], capture_output=True, text=True)
if 'failed=0' not in r.stdout:
    print(r.stdout, r.stderr[-2000:])
rec = {}
for l in open('/workspace/pilot/bp/rdet/%s.jsonl' % m):
    f = json.loads(l)
    if lo <= f['t'] <= hi:
        rec[f['t']] = [g for g in f['G'] if g[3] in cards]
ids = {}
for l in open(wd + '/o.jsonl'):
    o = json.loads(l)
    t = o['t']
    if not lo <= t <= hi:
        continue
    for e in o['E']:
        if e[1] == 'C' and any(n in e[2] for n in names) and (not IDS or e[0] in IDS):
            print('S %d %d %s (%d,%d) hp%d tgt%s st%s tm%s %s' % (t, e[0], e[2], e[4], e[5], e[6], e[12], e[13], e[14], e[11]))
    for g in [g for g in rec.get(t, []) if not IDS or g[5] in IDS]:
        print('R %d gen%s (%d,%d) hp%d tgt%s st%s att%s %s' % (t, g[5], g[1], g[2], g[4], g[6], g[7], g[8], ','.join(g[9] or [])))
    if o['ab']:
        print('AB', t, o['ab'])
import shutil
shutil.rmtree(wd)
