"""A2c-BP4 item 4: every Barbarian Barrel end (any side), and every walking ground unit on the same lane, crforge's route
rebuilds against the game's motion.
    python3 barb_census.py RUNDIR LIB OUT.jsonl [THREADS]      (AimRun4 with PA rows in /workspace/pilot/bp4/build_aim4)
A log end te = the first tick a projectile / area named like BarbLog / BarbarianBarrel is no longer listed. Units: every
character with a displacement at te-1 (walking), on the log's lane (x on the same side of 9,000) within RAD (env, default 6,000) units
(Manhattan) of the log's last point, exact at the last frame before te. Per unit, over (te, te + WIN] (env, default 20):
  replan  crforge ran a route search for it (sub: goal / overlay); out  'exact' (every frame of the window has the
  unit exact), 'div' (first frame where it is not: div_t), 'gone'; clean: te + 20 <= the run's first divergence or none
"""
import bisect, collections, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp4/work/barb')
FR = '/workspace/pilot/sme_live/frames2'
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json')))
RAD, WIN = int(os.environ.get("RAD", "6000")), int(os.environ.get("WIN", "20"))
islog = lambda n: 'barblog' in n.lower() or 'barbarianbarrel' in n.lower() or 'barb_log' in n.lower()


def job(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), res[m]['live_end'] + 2, os.path.join(WD, m + '.o.jsonl'))


def parse(m):
    fd = res[m].get('first_div')
    frames = {}
    for l in open(os.path.join(FR, m + '.jsonl')):
        f = json.loads(l)
        frames[f['t']] = {(e[0], e[1], e[2]) for e in f['E']}
    fticks = sorted(frames)
    C, EV, logs = {}, {}, {}
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        C[o['t']] = {c[0]: c for c in o['C']}
        EV[o['t']] = o['ev']
        for p in o.get('PA', []):
            if islog(p[2]):
                logs[p[0]] = (o['t'], p)  # last tick listed, last row
    out = []
    for lid, (tl, p) in logs.items():
        te = tl + 1
        walkers = {e[1] for e in EV.get(te - 1, []) if e[0] == 'disp'}
        i = bisect.bisect_left(fticks, te)
        if i == 0:
            continue
        fp = fticks[i - 1]
        for u in walkers:
            c = C.get(te - 1, {}).get(u)
            pc = C.get(fp, {}).get(u)
            if c is None or pc is None or (c[3] < 9000) != (p[4] < 9000) or abs(c[3] - p[4]) + abs(c[4] - p[5]) > RAD:
                continue
            if (pc[2], pc[3], pc[4]) not in frames[fp]:
                continue
            rp = [('goal' if e[2] else 'overlay') for t in range(te, te + WIN + 1) for e in EV.get(t, []) if e[0] == 'replan' and e[1] == u]
            row = {'m': m[10:], 'te': te, 'log': p[2], 'log_side': p[3], 'id': u, 'name': c[1], 'side': c[2],
                   'replan': sorted(set(rp)), 'clean': fd is None or te + WIN <= fd, 'out': 'exact'}
            for f in fticks[i:]:
                if f > te + WIN:
                    break
                cf = C.get(f, {}).get(u)
                if cf is None:
                    row['out'] = 'gone'
                    break
                if (cf[2], cf[3], cf[4]) not in frames[f]:
                    row['out'], row['div_t'] = 'div', f
                    break
            out.append(row)
    return out


def parse_one(m):
    try:
        return parse(m)
    finally:
        try:
            os.remove(os.path.join(WD, m + '.o.jsonl'))
        except OSError:
            pass


if __name__ == '__main__':
    open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(job(m) for m in ms) + '\n')
    r = subprocess.run(['java', '-Xmx64g', '-cp', lib + '/*:/workspace/pilot/bp4/build_aim4', 'AimRun4',
                        '/workspace/crforge_cache/tables/16.402.22', os.path.join(WD, 'jobs.txt'), str(threads)],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr[-600:])
    rows = []
    with ProcessPoolExecutor(16) as ex:
        for o in ex.map(parse_one, [m for m in ms if os.path.exists(os.path.join(WD, m + '.o.jsonl'))]):
            rows += o
    with open(outp, 'w') as f:
        for x in rows:
            f.write(json.dumps(x) + '\n')
    print('unit-windows %d, log ends %d' % (len(rows), len({(x['m'], x['te']) for x in rows})))
    c = collections.Counter((x['clean'], x['side'] == x['log_side'], tuple(x['replan']), x['out']) for x in rows)
    print('(clean, unit on the log side, crforge replans, out):')
    for k, v in sorted(c.items(), key=str):
        print(' ', k, v)
    for x in rows:
        if x['out'] == 'div' and x['clean']:
            print(x)
