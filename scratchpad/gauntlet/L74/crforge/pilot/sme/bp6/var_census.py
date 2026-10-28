"""A2c-BP6: census of the AimRun10 in-tracer engine variants (goal from another unit position 'vg'; route searched from
another cell 'vs'). python3 var_census.py RUNDIR LIB OUT.jsonl [THREADS]   (SKIP_RUN=1 parses WD outputs; ONLY=m,m)
Event: a vg / vs of unit u at tick t whose predicted node's pure step differs from the pure step toward crforge's aim
(the disp of u in the same tick). fr2: a fresh search from the start cell to the held goal (all ground units). Frames as bp4 goal_census: tf = first recorded frame >= t, tp = the frame before;
pre = u exact at tp. out at tf: 'crforge' (sim point recorded), 'var' (a recorded body of u's side within 3 units of the
sim point moved by the step difference), 'neither', 'gone'. clean = t <= the run's first divergence (or none)."""
import bisect, collections, json, math, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 32
WD = os.environ.get('WD', '/workspace/pilot/bp6/work/var')
FR = '/workspace/pilot/sme_live/frames2'
W = 36
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json'))
            and (not os.environ.get('ONLY') or m[10:] in os.environ['ONLY'].split(',')))
TARGETS = {('20261027_000233', 4598, 5000116), ('20261027_000233', 4599, 5000119), ('20261026_180336', 2910, 5000058),
           ('20261026_101112', 5923, 5000156), ('20261027_014928', 5182, 5000218)}


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
    nchk = collections.Counter()
    for t, ev in evs:
        for k, e in enumerate(ev):
            if e[0] == 'vchk':
                nchk['vchk'] += 1
            if e[0] not in ('vg', 'vs', 'fr2'):
                continue
            u = e[1]
            d = next((x for x in reversed(ev[:k]) if x[0] == 'disp' and x[1] == u), None)
            if d is None or u not in pos[t]:
                continue
            sx, sy, ax, ay, budget = d[2:7]
            node = e[4] if e[0] == 'vg' else e[2] if e[0] == 'fr2' else e[3]
            px, py = (node % W) * 500 + 250, (node // W) * 500 + 250
            p0, p1 = pure(sx, sy, ax, ay, budget), pure(sx, sy, px, py, budget)
            dv = (p1[0] - p0[0], p1[1] - p0[1])
            if dv == (0, 0):
                continue
            i = bisect.bisect_left(ft, t)
            if i == 0 or i >= len(ft):
                continue
            tp, tf = ft[i - 1], ft[i]
            pp, pf = pos.get(tp, {}).get(u), pos.get(tf, {}).get(u)
            pre = pp is not None and (pp[0], pp[1], pp[2]) in frames[tp][0]
            if pf is None:
                o_ = 'gone'
            elif (pf[0], pf[1], pf[2]) in frames[tf][0]:
                o_ = 'crforge'
            elif any(s == pf[0] and abs(x - pf[1] - dv[0]) <= 3 and abs(y - pf[2] - dv[1]) <= 3 for s, x, y in frames[tf][1]):
                o_ = 'var'
            else:
                o_ = 'neither'
            row = {'m': m[10:], 't': t, 'id': u, 'name': pos[t][u][3], 'kind': e[0], 'k': 0 if e[0] == 'fr2' else e[2], 'node': node, 'aim': [ax, ay],
                   'dv': dv, 'pre': pre, 'out': o_, 'clean': fd is None or t <= fd, 'tgt': (m[10:], t, u) in TARGETS}
            if e[0] == 'vg':
                row.update(vgoal=e[3], crgoal=e[5], rpch=e[6])
            elif e[0] == 'vs':
                row.update(walked=e[5], stick=e[6])
            else:
                row.update(on=e[3], cellch=e[4], walked=e[5], size=e[6], since=e[7], adj=e[8], onrem=e[9])
            out.append(row)
    return out, nchk


def parse_one(m):
    try:
        return parse(m)
    finally:
        if not os.environ.get('KEEP'):
            try:
                os.remove(os.path.join(WD, m + '.o.jsonl'))
            except OSError:
                pass


def summary(rows):
    dec = [x for x in rows if x['pre'] and x['clean']]
    print('events %d; clean with an exact frame before %d' % (len(rows), len(dec)))
    c = collections.Counter((x['kind'], x['k'], x['out']) for x in dec)
    for kind in ('vg', 'vs', 'fr2'):
        for k in sorted({x['k'] for x in dec if x['kind'] == kind}):
            tg = sorted({(x['m'], x['t'], x['out']) for x in dec if x['kind'] == kind and x['k'] == k and x['tgt']})
            print('%s %2d  crforge %7d  var %4d  neither %4d  gone %4d   targets: %s' % (
                kind, k, c[(kind, k, 'crforge')], c[(kind, k, 'var')], c[(kind, k, 'neither')], c[(kind, k, 'gone')], tg))
    fr = [x for x in dec if x['kind'] == 'fr2']
    for f in ('on', 'cellch', 'adj', 'onrem'):
        print('fr2', f, sorted(collections.Counter((x[f], x['out']) for x in fr).items()))
    print('fr2 on/cellch/adj/onrem', sorted(collections.Counter((x['on'], x['cellch'], x['adj'], x['onrem'], x['out']) for x in fr).items()))
    for x in dec:
        if x['out'] == 'var' or x['tgt']:
            print('VAR', x)


if __name__ == '__main__':
    if not os.environ.get('SKIP_RUN'):
        open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(job(m) for m in ms) + '\n')
        r = subprocess.run(['java', '-Xmx96g', '-cp', lib + '/*:/workspace/pilot/bp6/build_aim10', 'AimRun10',
                            '/workspace/crforge_cache/tables/16.402.22', os.path.join(WD, 'jobs.txt'), str(threads)],
                           capture_output=True, text=True)
        print(r.stdout.strip(), r.stderr[-600:])
    rows, chk = [], collections.Counter()
    with ProcessPoolExecutor(32) as ex:
        for o, n in ex.map(parse_one, [m for m in ms if os.path.exists(os.path.join(WD, m + '.o.jsonl'))]):
            rows += o
            chk += n
    with open(outp, 'w') as f:
        for x in rows:
            f.write(json.dumps(x) + '\n')
    print('vchk mismatches', chk['vchk'])
    summary(rows)
