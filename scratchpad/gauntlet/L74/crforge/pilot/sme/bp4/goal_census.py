"""A2c-BP4 item 1: every goal change of a ground route search, crforge's new route against the held one, and which
endpoint-scan variant would have kept the held goal.
    python3 goal_census.py RUNDIR LIB OUT.jsonl [THREADS]      (SKIP_RUN=1: parse WD outputs already there)
LIB: an engine lib with MoveProbe 0004 (clashbot-bp4: replan v[11] = scan radius R, v[12..15] = goal at R-25/50/75/100,
v[16] = goal with the reference at its cell's centre). AimRun from /workspace/pilot/bp3/build_aim.
Per event (one jsonl row): an event is a replan with the goal changed, a held route (held next node >= 0), and a first
displacement after it whose pure step differs from the pure step toward the held next node (else no frame decides).
  pre   the body matched a recorded body exactly at the last frame before the step
  out   at the first frame at or after the step: 'crforge' (recorded body at the sim point), 'alt0' (a recorded body
        within 3 units of the sim point moved by the held-node step difference), 'neither', 'gone'
  keep  {variant: the variant's goal == the held goal} for start (tick-start reference), r25..r100, cell
  dnew / dheld  distance from the reference point to the new / held goal cell centre; R the scan radius
"""
import bisect, collections, json, math, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp4/work/goal')
FR = '/workspace/pilot/sme_live/frames2'
CELL, W = 500, 36
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json'))
            and (not os.environ.get('ONLY') or m[10:] in os.environ['ONLY'].split(',')))
VAR = ('start', 'r25', 'r50', 'r75', 'r100', 'cell')


def job(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), res[m]['live_end'] + 2, os.path.join(WD, m + '.o.jsonl'))


def ctr(node):
    return (node % W) * CELL + CELL // 2, (node // W) * CELL + CELL // 2


def tdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def pure(sx, sy, tx, ty, budget):
    dist = math.isqrt((tx - sx) ** 2 + (ty - sy) ** 2)
    safe = max(dist, 1)
    step = min(budget, safe, 250)
    return tdiv(tdiv((tx - sx) << 8, safe) * step, 256), tdiv(tdiv((ty - sy) << 8, safe) * step, 256)


def parse(m):
    r = res[m]
    fd = r.get('first_div')
    frames = {}
    for l in open(os.path.join(FR, m + '.jsonl')):
        f = json.loads(l)
        frames[f['t']] = {(e[0], e[1], e[2]) for e in f['E']}, [(e[0], e[1], e[2]) for e in f['E']]
    fticks = sorted(frames)
    pos = {}
    evs = []
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        pos[o['t']] = {c[0]: (c[2], c[3], c[4], c[1], c[6]) for c in o['C']}
        evs.append((o['t'], o['ev']))
    out = []
    last_rp, ref_since, ref_id = {}, {}, {}
    for t, ev in evs:
        for i, c in pos[t].items():  # ticks since the targeting reference id became the current one
            if ref_id.get(i) != c[4]:
                ref_id[i], ref_since[i] = c[4], t
        rp_prev = dict(last_rp)
        for e in ev:
            if e[0] == 'replan':
                last_rp[e[1]] = t
        for k, e in enumerate(ev):
            if e[0] != 'replan' or len(e) < 19:
                continue
            eid, v = e[1], e[2:]
            goal_ch, kept, held_next, goal, held_goal = v[0], v[1], v[5], v[6], v[7]
            if not goal_ch or kept or held_next < 0 or held_goal < 0:
                continue
            d = next((x for x in ev[k + 1:] if x[0] == 'disp' and x[1] == eid), None)
            if d is None or eid not in pos[t]:
                continue
            sx, sy, tx, ty, budget = d[2:7]
            p0 = pure(sx, sy, tx, ty, budget)
            ax, ay = ctr(held_next)
            pa = pure(sx, sy, ax, ay, budget)
            dv = (pa[0] - p0[0], pa[1] - p0[1])
            if dv == (0, 0):
                continue
            rx, ry, R = v[8], v[9], v[11]
            keep = {nm: g == held_goal for nm, g in zip(VAR, (v[10],) + tuple(v[12:17]))}
            gx, gy = ctr(goal)
            hx, hy = ctr(held_goal)
            row = {'m': m[10:], 't': t, 'id': eid, 'name': pos[t][eid][3], 'R': R, 'keep': keep, 'clean': fd is None or t <= fd,
                   'dnew': round(math.hypot(gx - rx, gy - ry), 2), 'dheld': round(math.hypot(hx - rx, hy - ry), 2),
                   'goal': goal, 'held': held_goal, 'ref': [rx, ry], 'dv': dv,
                   'since_rp': t - rp_prev[eid] if eid in rp_prev else None, 'since_ref': t - ref_since.get(eid, t),
                   'mutual': pos[t].get(pos[t][eid][4], (0, 0, 0, '', -2))[4] == eid,
                   'ref_name': pos[t].get(pos[t][eid][4], (0, 0, 0, '?'))[3], 'side': pos[t][eid][0],
                   'ref_id': pos[t][eid][4], 'ref_side': pos[t].get(pos[t][eid][4], (-1,))[0]}
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
                row['out'] = 'alt0'
            else:
                row['out'] = 'neither'
            out.append(row)
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


def summary(rows):
    dec = [x for x in rows if x['pre'] and x['out'] in ('crforge', 'alt0')]
    print('events %d, deciding (pre exact, crforge or alt0) %d, clean %d' % (len(rows), len(dec), sum(x['clean'] for x in dec)))
    print(collections.Counter((x['clean'], x['out']) for x in rows if x['pre']))
    for nm in VAR:
        c = collections.Counter((x['out'], x['keep'][nm]) for x in dec if x['clean'])
        agree = c[('crforge', False)] + c[('alt0', True)]
        print('%-6s clean: agrees %d / %d  (crforge&change %d, alt0&keep %d, crforge but keeps %d, alt0 but changes %d)' % (
            nm, agree, sum(c.values()), c[('crforge', False)], c[('alt0', True)], c[('crforge', True)], c[('alt0', False)]))


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
    summary(rows)
