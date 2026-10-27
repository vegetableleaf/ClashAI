"""A2c-BP5 item 3: does the game re-search a held ground route that crforge keeps? (AimRun9 'fr' events)
    python3 fresh_census.py RUNDIR LIB OUT.jsonl [THREADS]
Event: a 'fr' at tick t (the fresh search from the unit's start cell to its held goal answers a next node other than the one
crforge stepped toward) with no crforge replan of the unit at t, a recorded frame at t, the unit exact at the last frame
before t, and pure steps toward the two nodes that differ. out at frame t: 'crforge' (sim point recorded), 'fresh' (a
recorded body of the side within 2 units of the sim point moved by the step difference), 'neither', 'gone'.
cell = the start cell changed since the unit's last visit. clean = t <= the run's first divergence or none."""
import bisect, collections, json, math, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp5/work/fresh')
FR = '/workspace/pilot/sme_live/frames2'
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json')))
W = 36


def job(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), res[m]['live_end'] + 2, os.path.join(WD, m + '.o.jsonl'))


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def pure(sx, sy, tx, ty, budget):
    d = math.isqrt((tx - sx) ** 2 + (ty - sy) ** 2)
    s = max(d, 1)
    st = min(budget, s, 250)
    return tdiv(tdiv((tx - sx) << 8, s) * st, 256), tdiv(tdiv((ty - sy) << 8, s) * st, 256)


def parse(m):
    fd = res[m].get('first_div')
    frames = {}
    for l in open(os.path.join(FR, m + '.jsonl')):
        f = json.loads(l)
        frames[f['t']] = ({(e[0], e[1], e[2]) for e in f['E']}, [(e[0], e[1], e[2]) for e in f['E']])
    ft = sorted(frames)
    pos, evs = {}, []
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        pos[o['t']] = {c[0]: (c[2], c[3], c[4], c[1]) for c in o['C']}
        evs.append((o['t'], o['ev']))
    out = []
    for t, ev in evs:
        if t not in frames:
            continue
        rp = {e[1] for e in ev if e[0] == 'replan'}
        for k, e in enumerate(ev):
            if e[0] != 'fr' or e[1] in rp:
                continue
            u = e[1]
            d = next((x for x in reversed(ev[:k]) if x[0] == 'disp' and x[1] == u), None)
            if d is None or u not in pos[t]:
                continue
            sx, sy, ax, ay, budget = d[2:7]
            fx, fy = (e[2] % W) * 500 + 250, (e[2] // W) * 500 + 250
            p0, p1 = pure(sx, sy, ax, ay, budget), pure(sx, sy, fx, fy, budget)
            dv = (p1[0] - p0[0], p1[1] - p0[1])
            if dv == (0, 0):
                continue
            i = bisect.bisect_left(ft, t)
            if i == 0:
                continue
            tp = ft[i - 1]
            pp = pos.get(tp, {}).get(u)
            if pp is None or (pp[0], pp[1], pp[2]) not in frames[tp][0]:
                continue
            pf = pos[t][u]
            if (pf[0], pf[1], pf[2]) in frames[t][0]:
                o_ = 'crforge'
            elif any(s == pf[0] and abs(x - pf[1] - dv[0]) <= 2 and abs(y - pf[2] - dv[1]) <= 2 for s, x, y in frames[t][1]):
                o_ = 'fresh'
            else:
                o_ = 'neither'
            out.append({'m': m[10:], 't': t, 'id': u, 'name': pf[3], 'cell': e[6], 'held': e[7], 'fresh': e[2], 'aim': [ax, ay],
                        'dv': dv, 'gap': t - tp, 'clean': fd is None or t <= fd, 'out': o_})
    return out


def parse_one(m):
    try:
        return parse(m)
    finally:
        if not os.environ.get('KEEP'):
            try:
                os.remove(os.path.join(WD, m + '.o.jsonl'))
            except OSError:
                pass


if __name__ == '__main__':
    if not os.environ.get('SKIP_RUN'):
        open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(job(m) for m in ms) + '\n')
        r = subprocess.run(['java', '-Xmx64g', '-cp', lib + '/*:/workspace/pilot/bp5/build_aim9', 'AimRun9',
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
    print('events %d' % len(rows))
    print(collections.Counter((x['clean'], x['cell'], x['out']) for x in rows))
    for x in rows:
        if x['clean'] and x['out'] == 'fresh':
            print(x)
