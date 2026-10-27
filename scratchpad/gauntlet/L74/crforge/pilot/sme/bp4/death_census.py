"""A2c-BP4 item 3: delay from a target's removal to the first move of a unit that stood still while it held that target,
crforge against the game.
    python3 death_census.py RUNDIR LIB OUT.jsonl [THREADS]      (AimRun4 in /workspace/pilot/bp4/build_aim4)
Event: unit U held reference R at tick t-1, R is no longer listed at t (removed: killed or expired), U stood still at
t-3..t-1 and U was exact at the last frame before t. mc = crforge's first tick >= t at which U's point changes.
  out   at the first frame f >= mc (and the frames in [t, mc)): crforge (U exact at every frame to f), earlier (a frame
        before mc has no recorded body of U's side at U's standing point but one within 300 units, or at f the
        recorded body moved farther than the sim body), later (at f a recorded body still at the standing point),
        neither;  pre / clean as the other censuses
Rows: unit name, its state and timers at t-1 (attack/load/retarget cooldown/target lost/sequence), R's name and last hp,
delay mc - t, the distance from U to R at t-1, and U's reference at mc."""
import bisect, collections, json, math, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp4/work/death')
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


def cause(rr, pa0, pa1):
    """How R was removed, from what flew or lay near it: 'projectile' (an enemy projectile within 1,200 units at t-1
    gone at t), 'area' (an enemy area effect within 3,000 units at t-1 or t), else 'direct'."""
    ids1 = {p[0] for p in pa1}
    near = lambda p, d: p[3] != rr[2] and abs(p[4] - rr[3]) + abs(p[5] - rr[4]) <= d
    if any(p[1] == 'P' and p[0] not in ids1 and near(p, 1200) for p in pa0):
        return 'projectile'
    if any(p[1] == 'A' and near(p, 3000) for p in pa0 + pa1):
        return 'area'
    return 'direct'


def parse(m):
    fd = res[m].get('first_div')
    frames = {}
    for l in open(os.path.join(FR, m + '.jsonl')):
        f = json.loads(l)
        frames[f['t']] = {(e[0], e[1], e[2]) for e in f['E']}, [(e[0], e[1], e[2]) for e in f['E']]
    fticks = sorted(frames)
    C, PA = {}, {}
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        C[o['t']] = {c[0]: c for c in o['C']}  # [id, name, side, x, y, hp, ref, state, z, timers]
        PA[o['t']] = o.get('PA', [])  # [id, 'P'|'A', name, side, x, y]
    ticks = sorted(C)
    out = []
    for t in ticks:
        prev = C.get(t - 1)
        if prev is None:
            continue
        for u, c in prev.items():
            r = c[6]
            if r < 0 or r not in prev or r in C[t] or u not in C[t]:
                continue
            pt = (c[3], c[4])
            if any(tuple(C.get(t - k, {}).get(u, (0, 0, 0, -1, -1))[3:5]) != pt for k in (2, 3)):
                continue
            mc = next((s for s in ticks if s >= t and (C[s].get(u) is None or tuple(C[s][u][3:5]) != pt)), None)
            if mc is None or C[mc].get(u) is None:
                continue
            i = bisect.bisect_left(fticks, t)
            if i == 0:
                continue
            fp = fticks[i - 1]
            pp = C.get(fp, {}).get(u)
            row = {'m': m[10:], 't': t, 'id': u, 'name': c[1], 'state': c[7], 'timers': c[9], 'R': prev[r][1],
                   'R_hp': prev[r][5], 'delay': mc - t, 'dist': round(math.hypot(prev[r][3] - pt[0], prev[r][4] - pt[1])),
                   'ref_mc': C[mc][u][6], 'clean': fd is None or t <= fd,
                   'pre': pp is not None and (pp[2], pp[3], pp[4]) in frames[fp][0], 'cause': cause(prev[r], PA.get(t - 1, []), PA.get(t, [])),
                   'u_before_r': u < r}
            out_ = 'crforge'
            j = i
            while j < len(fticks) and fticks[j] < mc:
                f = fticks[j]
                if (c[2], pt[0], pt[1]) not in frames[f][0]:
                    near = any(s == c[2] and abs(x - pt[0]) + abs(y - pt[1]) <= 300 for s, x, y in frames[f][1])
                    out_ = 'earlier' if near else 'neither'
                    break
                j += 1
            if out_ == 'crforge':
                if j >= len(fticks):
                    continue
                f = fticks[j]
                sp = C.get(f, {}).get(u)
                if sp is None:
                    continue
                if (sp[2], sp[3], sp[4]) in frames[f][0]:
                    out_ = 'crforge'
                elif (c[2], pt[0], pt[1]) in frames[f][0]:
                    out_ = 'later'
                else:
                    ds = math.hypot(sp[3] - pt[0], sp[4] - pt[1])
                    cand = [math.hypot(x - pt[0], y - pt[1]) for s, x, y in frames[f][1]
                            if s == c[2] and abs(x - sp[3]) + abs(y - sp[4]) <= 300]
                    out_ = 'neither' if not cand else 'earlier' if min(cand, key=lambda d: abs(d - ds)) > ds else 'later'
                row['f'] = f
            row['out'] = out_
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
    dec = [x for x in rows if x['pre'] and x['clean']]
    print('events %d; pre exact and clean %d' % (len(rows), len(dec)))
    print(collections.Counter(x['out'] for x in dec))
    c = collections.defaultdict(collections.Counter)
    for x in dec:
        c[x['name']][(min(x['delay'], 20), x['out'])] += 1
    c2 = collections.Counter((x['delay'] if x['delay'] < 8 else 8, x['cause'], x['out']) for x in dec)
    print('(delay, cause, out):')
    for k, v in sorted(c2.items()):
        print(' ', k, v)
    for nm in sorted(c, key=lambda n: -sum(c[n].values())):
        print('%-28s' % nm, sorted(c[nm].items()))
    for x in dec:
        if x['out'] != 'crforge':
            print(x)
