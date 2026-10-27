"""A2c-BP4 item 1b: route searches whose new next node is a node the unit already reached (popped) earlier, crforge's aim
(that node again) against the game's motion.
    python3 repop_census.py RUNDIR LIB OUT.jsonl [THREADS]      (env as goal_census.py; ONLY=match,match)
Per tick a unit 'pops' the node its displacement aimed at when the displacement reports arrival. An event is a replan
(route not kept) whose first displacement aims at the new route's next node, with that node popped by this unit within
the last POP_WINDOW ticks (default 30); alt1 = the new route's node after the next. Outcome as aim_census: crforge /
alt1 (recorded body within 3 units of the sim point moved by the alt1 step difference) / neither / gone; clean =
t <= the run's first divergence; pre = body exact at the frame before.
Rows also carry: ago (ticks since the pop), sub (goal / overlay), arrive (the first displacement reports arrival),
aim_d (distance to the aim node), same (node after next == held next)."""
import bisect, collections, json, math, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp4/work/repop')
FR = '/workspace/pilot/sme_live/frames2'
CELL, W = 500, 36
WIN = int(os.environ.get('POP_WINDOW', '30'))
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json'))
            and (not os.environ.get('ONLY') or m[10:] in os.environ['ONLY'].split(',')))


def job(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), res[m]['live_end'] + 2, os.path.join(WD, m + '.o.jsonl'))


def ctr(node):
    return (node % W) * CELL + CELL // 2, (node // W) * CELL + CELL // 2


def node_of(x, y):
    return (y // CELL) * W + x // CELL


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def pure(sx, sy, tx, ty, budget):
    dist = math.isqrt((tx - sx) ** 2 + (ty - sy) ** 2)
    safe = max(dist, 1)
    step = min(budget, safe, 250)
    return tdiv(tdiv((tx - sx) << 8, safe) * step, 256), tdiv(tdiv((ty - sy) << 8, safe) * step, 256)


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
        pos[o['t']] = {c[0]: (c[2], c[3], c[4], c[1], c[6]) for c in o['C']}
        evs.append((o['t'], o['ev']))
    popped = collections.defaultdict(dict)  # id -> {node: last tick it was popped}
    out = []
    for t, ev in evs:
        for k, e in enumerate(ev):
            if e[0] != 'replan' or e[3]:
                continue
            eid, v = e[1], e[2:]
            nxt, nxt2, held_next = v[3], v[4], v[5]
            d = next((x for x in ev[k + 1:] if x[0] == 'disp' and x[1] == eid), None)
            if d is None or eid not in pos[t] or nxt < 0 or nxt2 < 0:
                continue
            sx, sy, tx, ty, budget, reached = d[2:8]
            if (tx, ty) != ctr(nxt):
                continue
            ago = t - popped[eid].get(nxt, -10 ** 9)
            if ago > WIN:
                continue
            p0 = pure(sx, sy, tx, ty, budget)
            ax, ay = ctr(nxt2)
            pa = pure(sx, sy, ax, ay, budget)
            dv = (pa[0] - p0[0], pa[1] - p0[1])
            row = {'m': m[10:], 't': t, 'id': eid, 'name': pos[t][eid][3], 'ago': ago, 'sub': 'goal' if v[0] else 'overlay',
                   'arrive': reached, 'aim_d': math.isqrt((tx - sx) ** 2 + (ty - sy) ** 2), 'same': nxt2 == held_next,
                   'clean': fd is None or t <= fd, 'dv': dv, 'start_node': node_of(sx, sy)}
            if dv == (0, 0):
                row['out'] = 'nodisc'
                out.append(row)
                continue
            i = bisect.bisect_left(fticks, t)
            if i == 0 or i >= len(fticks):
                continue
            tp, tf = fticks[i - 1], fticks[i]
            pp, pf = pos.get(tp, {}).get(eid), pos.get(tf, {}).get(eid)
            row['tf'] = tf
            row['pre'] = pp is not None and (pp[0], pp[1], pp[2]) in frames[tp][0]
            if pf is None:
                row['out'] = 'gone'
            elif (pf[0], pf[1], pf[2]) in frames[tf][0]:
                row['out'] = 'crforge'
            elif any(s == pf[0] and abs(x - pf[1] - dv[0]) <= 3 and abs(y - pf[2] - dv[1]) <= 3 for s, x, y in frames[tf][1]):
                row['out'] = 'alt1'
            else:
                row['out'] = 'neither'
            out.append(row)
        for e in ev:  # pops of this tick, after its searches were read
            if e[0] == 'disp' and e[7]:
                popped[e[1]][node_of(e[4], e[5])] = t
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
    dec = [x for x in rows if x.get('pre') and x['out'] in ('crforge', 'alt1', 'neither')]
    print('events %d; deciding with an exact frame before %d' % (len(rows), len(dec)))
    for k in ('clean', 'ago', 'sub', 'arrive', 'same'):
        c = collections.Counter((x['clean'], min(x[k], 9) if k == 'ago' else x[k], x['out']) for x in dec)
        print(k, sorted(c.items(), key=str))
    for x in dec:
        if x['clean'] and x['out'] != 'crforge':
            print(x['m'], x['t'], x['id'], x['name'], 'ago', x['ago'], x['sub'], 'arrive', x['arrive'], 'same', x['same'], x['out'])
