"""A2c-BP4 item 1c: every GridMove cell-edge clamp (MoveProbe 'prop': the point after GridMove differs from start +
proposal), crforge vs the game at the next frame.
    python3 clamp_census.py RUNDIR LIB OUT.jsonl [THREADS]
Row per clamp: axis ('x', 'y', 'xy'), water bit (the blocked neighbour cell is water: the river / bridge edge) unknown
here, so 'bridge' = the start cell's row is a river row (rows 30..33) and its column a bridge column; pre = body exact
at the frame before; out = crforge (exact at the next frame) / unclamped (a recorded body within 2 units of start +
proposal, i.e. the game did not clamp) / neither / gone. clean = t <= the run's first divergence."""
import bisect, collections, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp4/work/clamp')
FR = '/workspace/pilot/sme_live/frames2'
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json')))


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
        frames[f['t']] = {(e[0], e[1], e[2]) for e in f['E']}, [(e[0], e[1], e[2]) for e in f['E']]
    fticks = sorted(frames)
    pos, evs = {}, []
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        pos[o['t']] = {c[0]: (c[2], c[3], c[4], c[1]) for c in o['C']}
        evs.append((o['t'], o['ev']))
    out = []
    for t, ev in evs:
        disp = {e[1]: e for e in ev if e[0] == 'disp'}
        for e in ev:
            if e[0] != 'prop' or e[1] not in disp or e[1] not in pos[t]:
                continue
            v, d = e[2:], disp[e[1]]
            sx, sy = d[2], d[3]
            free = (sx + v[8], sy + v[9])
            end = (v[10], v[11])
            if free == end:
                continue
            axis = ('x' if free[0] != end[0] else '') + ('y' if free[1] != end[1] else '')
            row = {'m': m[10:], 't': t, 'id': e[1], 'name': pos[t][e[1]][3], 'axis': axis, 'clean': fd is None or t <= fd,
                   'cell': [sx // 500, sy // 500], 'push': v[4], 'free_off': [free[0] - end[0], free[1] - end[1]]}
            i = bisect.bisect_left(fticks, t)
            if i == 0 or i >= len(fticks):
                continue
            tp, tf = fticks[i - 1], fticks[i]
            pp, pf = pos.get(tp, {}).get(e[1]), pos.get(tf, {}).get(e[1])
            row['tf'] = tf
            row['pre'] = pp is not None and (pp[0], pp[1], pp[2]) in frames[tp][0]
            if pf is None:
                row['out'] = 'gone'
            elif (pf[0], pf[1], pf[2]) in frames[tf][0]:
                row['out'] = 'crforge'
            elif tf == t and any(s == pf[0] and abs(x - free[0]) <= 2 and abs(y - free[1]) <= 2 for s, x, y in frames[tf][1]):
                row['out'] = 'unclamped'
            else:
                row['out'] = 'neither'
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
    r = subprocess.run(['java', '-Xmx64g', '-cp', lib + '/*:/workspace/pilot/bp3/build_aim', 'AimRun',
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
    river = lambda x: 30 <= x['cell'][1] <= 33
    c = collections.Counter((x['clean'], river(x), x['axis'], x['out']) for x in rows if x.get('pre'))
    print('clamps %d (pre exact %d); (clean, river rows 30-33, axis, out):' % (len(rows), sum(c.values())))
    for k, v in sorted(c.items(), key=str):
        print(' ', k, v)
    for x in rows:
        if x.get('pre') and x['clean'] and x['out'] != 'crforge':
            print(x)
