"""A2c-BP4 item 2b: neighbour pushes from a body that already moved earlier in the same tick. crforge pushes B from A's
moved point; the alternative ('premove') pushes B from A's point at the start of the tick (A moves after B's push pass).
    python3 order_census.py RUNDIR LIB OUT.jsonl [THREADS]      (MoveProbe 0004 with push masses; AimRun4)
For each visit of B with pushes (MoveProbe 'push' events, then B's 'prop'): the push is recomputed from the events
(the replica must equal crforge's push, else the row is skipped and counted), then again with each pusher A that moved
earlier in the tick put back at its start point. Rows only where the two final points differ and B's step was not
clamped by GridMove.
  out   at the first frame tf at or after the tick (at most 2 later): crforge (B exact) / premove (a recorded body within
        1 unit of the alternative point; when tf is later, within 2 of B's sim point at tf moved by the difference) /
        neither / gone;  pre: B exact at the frame before;  clean: t <= the run's first divergence
  lander_k  ticks since A's last JUMPING (5) -> other transition (None: none), as land_census.py"""
import bisect, collections, json, math, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp4/work/order')
FR = '/workspace/pilot/sme_live/frames2'
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json'))
            and (not os.environ.get('ONLY') or m[10:] in os.environ['ONLY'].split(',')))


def job(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), res[m]['live_end'] + 2, os.path.join(WD, m + '.o.jsonl'))


def tdiv(a, b):
    if b == 0:
        return 0
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def one(dx, dy, reach, mass_term, own_mass):
    """PushPass's contribution of one neighbour, or None when it is out of reach."""
    if abs(dx) > reach or abs(dy) > reach:
        return None
    sq = dx * dx + dy * dy
    if sq == 0 or sq > reach * reach:
        return None
    d = math.isqrt(sq)
    mag = max(min(reach - d, 300), 0)
    if mass_term != -1:
        mag = tdiv(mag * mass_term, own_mass)
    mag = min(mag, 299) + 1
    return tdiv(mag * dx, max(d, 1)), tdiv(mag * dy, max(d, 1))


def total(parts):
    """Displacement's averaged push, clamped to 150 (unclamped push not modelled; the replica check skips it)."""
    if not parts:
        return 0, 0
    n = len(parts)
    x, y = tdiv(sum(p[0] for p in parts), n), tdiv(sum(p[1] for p in parts), n)
    if x * x + y * y >= 22501:
        ln = math.isqrt(x * x + y * y)
        x, y = tdiv(x * 150, ln), tdiv(y * 150, ln)
    return x, y


def parse(m):
    fd = res[m].get('first_div')
    frames = {}
    for l in open(os.path.join(FR, m + '.jsonl')):
        f = json.loads(l)
        frames[f['t']] = {(e[0], e[1], e[2]) for e in f['E']}, [(e[0], e[1], e[2]) for e in f['E']]
    fticks = sorted(frames)
    out, bad, prevpos, landed = [], 0, {}, {}
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        t = o['t']
        cur = {c[0]: (c[2], c[3], c[4], c[1], c[7]) for c in o['C']}
        for i, c in cur.items():
            if i in prevpos and prevpos[i][4] == 5 and c[4] != 5:
                landed[i] = t
        moved, pushes, lastprop = {}, collections.defaultdict(list), {}
        for e in o['ev']:
            if e[0] == 'push':
                pushes[e[1]].append(e[2:])
            elif e[0] == 'prop':
                lastprop[e[1]] = e[2:]
                b, v, ps = e[1], e[2:], pushes.pop(e[1], [])
                if not ps or b not in cur or not any(p[0] in moved for p in ps):
                    continue
                parts = [(p[8], p[9]) for p in ps]
                if total(parts) != (v[2], v[3]) or v[4] != len(ps):
                    bad += 1
                    continue
                start = (v[10] - v[8], v[11] - v[9])
                if start[0] + v[8] != v[10]:  # (identity; GridMove clamp is tested below on the disp start)
                    continue
                alt, movers = [], []
                for p in ps:
                    a = p[0]
                    if a in moved:
                        (sx, sy), (ex, ey) = moved[a]
                        movers.append(a)
                        c = one(p[1] + ex - sx, p[2] + ey - sy, p[3], p[10], p[11])
                        if c is not None:
                            alt.append(c)
                    else:
                        alt.append((p[8], p[9]))
                ax, ay = total(alt)
                altpt = (start[0] + v[0] + ax, start[1] + v[1] + ay)
                if altpt == (v[10], v[11]):
                    continue
                row = {'m': m[10:], 't': t, 'id': b, 'name': cur[b][3], 'movers': [cur[a][3] if a in cur else '?' for a in movers],
                       'lander_k': min((t - landed[a] for a in movers if a in landed), default=None),
                       'diff': [altpt[0] - v[10], altpt[1] - v[11]], 'clean': fd is None or t <= fd, 'start': start,
                       'same_side': all(a in cur and cur[a][0] == cur[b][0] for a in movers),
                       'bstate': cur[b][4], 'astate': [cur[a][4] if a in cur else -1 for a in movers]}
                row['_alt'] = altpt
                out.append(row)
            elif e[0] == 'disp':
                if e[1] in lastprop:
                    moved[e[1]] = ((e[2], e[3]), (lastprop[e[1]][10], lastprop[e[1]][11]))
                for r in out:  # the row's start must be the disp start (no GridMove clamp hidden in it)
                    if r['t'] == t and r['id'] == e[1] and 'chk' not in r:
                        r['chk'] = tuple(r['start']) == (e[2], e[3])
        prevpos = cur
        o = None
    final = []
    for r in out:
        if not r.pop('chk', False):
            continue
        t, b, altpt = r['t'], r['id'], r.pop('_alt')
        r.pop('start')
        i = bisect.bisect_left(fticks, t)
        if i == 0 or i >= len(fticks) or fticks[i] > t + 2:
            continue
        r['tf'] = fticks[i]
        final.append((r, fticks[i - 1], altpt))
    return final, bad, frames


def parse_one(m):
    try:
        rows, bad, frames = parse(m)
        # positions at frame ticks need the trace: re-read only the frame ticks we need
        need = {r['tf'] for r, _, _ in rows} | {tp for _, tp, _ in rows}
        pos = {}
        for l in open(os.path.join(WD, m + '.o.jsonl')):
            o = json.loads(l)
            if o['t'] in need:
                pos[o['t']] = {c[0]: (c[2], c[3], c[4]) for c in o['C']}
        out = []
        for r, tp, altpt in rows:
            b, t = r['id'], r['tf']
            pp, pf = pos.get(tp, {}).get(b), pos.get(t, {}).get(b)
            if pf is not None and t != r['t']:  # a later frame: the alternative carried forward by its difference
                altpt = (pf[1] + r['diff'][0], pf[2] + r['diff'][1])
            r['pre'] = pp is not None and pp in frames[tp][0]
            if pf is None:
                r['out'] = 'gone'
            elif pf in frames[t][0]:
                r['out'] = 'crforge'
            elif any(s == pf[0] and abs(x - altpt[0]) <= (1 if t == r['t'] else 2) and abs(y - altpt[1]) <= (1 if t == r['t'] else 2)
                     for s, x, y in frames[t][1]):
                r['out'] = 'premove'
            else:
                r['out'] = 'neither'
            out.append(r)
        return out, bad
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
    rows, bad = [], 0
    with ProcessPoolExecutor(16) as ex:
        for o, b in ex.map(parse_one, [m for m in ms if os.path.exists(os.path.join(WD, m + '.o.jsonl'))]):
            rows += o
            bad += b
    with open(outp, 'w') as f:
        for x in rows:
            f.write(json.dumps(x) + '\n')
    print('rows %d (replica mismatches skipped: %d)' % (len(rows), bad))
    c = collections.Counter((x['clean'], x['pre'], x['out']) for x in rows)
    for k, v in sorted(c.items(), key=str):
        print(' ', k, v)
    dec = [x for x in rows if x['pre'] and x['clean']]
    c = collections.Counter((x['lander_k'] is not None and x['lander_k'] <= 3, x['same_side'], x['out']) for x in dec)
    print('clean, pre exact: (pusher landed <= 3 ticks ago, same side, out)')
    for k, v in sorted(c.items(), key=str):
        print(' ', k, v)
    for x in dec:
        if x['out'] != 'crforge' or (x['lander_k'] is not None and x['lander_k'] <= 3):
            print(x)
