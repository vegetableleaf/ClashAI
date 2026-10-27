"""Hero Ice Wizard deploys: the floating cube's first positions, crforge vs the game (A2c-BP).
    python3 iwdeploy.py RUNDIR OUT.jsonl
For every IceWizard play from a hero slot (slot flag 2) in a run's plans: crforge (BpRun) lines R..R+14, the hero and
cube rows made by that play; the reader's new card-203000023 rows within 3,000 of the point on the frames R..R+14."""
import json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, outp = sys.argv[1], sys.argv[2]
WD = '/workspace/pilot/bp/work/iwd'
os.makedirs(WD, exist_ok=True)
jobs, meta = [], []
for m in sorted(os.listdir(run)):
    pp = os.path.join(run, m, 'plan.json')
    if not m.startswith('live_play_') or not os.path.exists(pp):
        continue
    p = json.load(open(pp))
    for i, c in enumerate(p['cmds']):
        if c['kind'] != 'play' or c.get('card') != 'IceWizard':
            continue
        k = p['decks'][c['side']].index('IceWizard')
        if p['slots'][c['side']][k] != 2:
            continue
        q = dict(p, cmds=[{kk: v for kk, v in cc.items() if kk != '_src'} for cc in p['cmds']])
        f = os.path.join(WD, '%s_%d.plan.json' % (m, i))
        json.dump(q, open(f, 'w'))
        o = f.replace('.plan.json', '.o.jsonl')
        jobs.append('%s %d %s %d' % (f, c['run'] + 15, o, c['run']))
        meta.append((m, i, c['run'], c['side'], c['x'], c['y'], o))
open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(jobs) + '\n')
r = subprocess.run(['java', '-Xmx24g', '-cp', '/workspace/pilot/lib_008aa626/*:/workspace/pilot/bp/build_bpx', 'BpRun',
                    '/workspace/crforge_cache/tables/16.402.22', os.path.join(WD, 'jobs.txt'), '16'], capture_output=True, text=True)
print(r.stdout.strip(), r.stderr[-300:])


def one(mt):
    m, i, R, side, x, y, o = mt
    rec = {}
    for l in open('/workspace/pilot/bp/rdet/%s.jsonl' % m):
        f = json.loads(l)
        if R - 40 <= f['t'] <= R + 14:
            rec[f['t']] = [g for g in f['G'] if g[3] == 203000023 and g[0] == side]
    old = {g[5] for t in rec if t <= R for g in rec[t]}
    sim = {}
    if os.path.exists(o):
        for l in open(o):
            ob = json.loads(l)
            sim[ob['t']] = [(e[2], e[4], e[5], e[6]) for e in ob['E'] if e[8] == 'cmd%d' % i or
                            (e[2].startswith('IceWizardHero') and e[3] == side and abs(e[4] - x) + abs(e[5] - y) < 3000 and ob['t'] >= R)]
        os.remove(o)
    rr = {t: [(g[1], g[2], g[4], g[5]) for g in v if g[5] not in old and abs(g[1] - x) + abs(g[2] - y) < 3000] for t, v in rec.items() if t > R}
    return dict(match=m, cmd=i, R=R, side=side, point=[x, y], sim={t: v for t, v in sorted(sim.items())}, rec=rr)


with ProcessPoolExecutor(8) as ex, open(outp, 'w') as w:
    for res in ex.map(one, meta):
        w.write(json.dumps(res) + '\n')
