"""A2c-BP3 item 1: every route search whose first displacement arrives at the new route's next node in the same step
("rebuild with a near node"), crforge's aim against the game's motion.
    python3 aim_census.py RUNDIR LIB OUT.jsonl [THREADS]
RUNDIR: a sme_live run (plan.json per match); LIB: an engine lib with MoveProbe (clashbot-bp3); AimRun built in
/workspace/pilot/bp3/build_aim. Per event (one jsonl row):
  ref_mode  the search's reference point: now = the reference's point after its own move this tick (it moved before
          this visit), prev = its point at the end of the last tick, still = it did not move, other / none / unknown
  by_ref_move  the goal from the reference's point at the start of the tick equals the held goal: the reference's
          own move earlier in this tick is what changed the goal
  sub     goal = the goal changed; overlay = same goal, cost overlay changed, held route replaced; kept = held route kept
  near    the first displacement after the search reported arrival (node popped in the same step)
  alt1    aim = the new route's node after the next one; alt0 = the held route's next node before the search
  disc1/disc0  the pure step toward alt differs from the pure step toward crforge's aim (else the frame cannot decide)
  pre     the body matched a recorded body exactly (side, x, y) at the last frame before the step
  out     at the first frame at or after the step: 'crforge' (recorded body at the sim point), 'alt1' / 'alt0' (a
          recorded body within 3 units of the sim point moved by the alternative's step difference), 'neither'
"""
import json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = '/workspace/pilot/bp3/work/aim'
FR = '/workspace/pilot/sme_live/frames2'
CELL = 500  # TileMap.CELL_UNITS; the routing grid is 36 cells wide (GRID_W)
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json')))


def job(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), res[m]['live_end'] + 2, os.path.join(WD, m + '.o.jsonl'))


def ctr(node, width):
    return (node % width) * CELL + CELL // 2, (node // width) * CELL + CELL // 2


def tdiv(a, b):  # Java int division (truncates toward zero)
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def isqrt_dist(dx, dy):
    import math
    return math.isqrt(dx * dx + dy * dy)


def pure(sx, sy, tx, ty, budget):
    """Displacement.displace's proposal with no blend / push / clamp (FixedMath.guardedDistance = isqrt)."""
    dist = isqrt_dist(tx - sx, ty - sy)
    safe = max(dist, 1)
    step = min(budget, safe, 250)
    return tdiv(tdiv((tx - sx) << 8, safe) * step, 256), tdiv(tdiv((ty - sy) << 8, safe) * step, 256)


def parse(m, width):
    r = res[m]
    frames = {}
    for l in open(os.path.join(FR, m + '.jsonl')):
        f = json.loads(l)
        frames[f['t']] = {(e[0], e[1], e[2]) for e in f['E']}, [(e[0], e[1], e[2]) for e in f['E']]
    fticks = sorted(frames)
    import bisect
    ticks = {}
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        ticks[o['t']] = o
    pos = {}  # tick -> {id: (side, x, y, name)}
    for t, o in ticks.items():
        pos[t] = {c[0]: (c[2], c[3], c[4], c[1], c[6]) for c in o['C']}
    out = []
    for t, o in sorted(ticks.items()):
        ev = o['ev']
        for k, e in enumerate(ev):
            if e[0] != 'replan':
                continue
            eid, goal_ch, kept, size, nxt, nxt2, held = e[1], e[2], e[3], e[4], e[5], e[6], e[7]
            d = next((x for x in ev[k + 1:] if x[0] == 'disp' and x[1] == eid), None)
            if d is None:
                continue
            sx, sy, tx, ty, budget, reached = d[2:8]
            if kept or not reached or (tx, ty) != ctr(nxt, width):
                continue
            sub = 'goal' if goal_ch else 'overlay'
            p0 = pure(sx, sy, tx, ty, budget)
            row = {'m': m[10:], 't': t, 'id': eid, 'sub': sub, 'size': size, 'aim_d': isqrt_dist(tx - sx, ty - sy),
                   'budget': budget, 'name': pos[t].get(eid, (0, 0, 0, '?'))[3], 'first_div': r.get('first_div')}
            alts = {}
            for nm, node in (('alt1', nxt2), ('alt0', held)):
                if node is None or node < 0:
                    continue
                ax, ay = ctr(node, width)
                pa = pure(sx, sy, ax, ay, budget)
                alts[nm] = (pa[0] - p0[0], pa[1] - p0[1])
                row['disc' + nm[-1]] = alts[nm] != (0, 0)
            row['same_alt'] = nxt2 == held
            if len(e) >= 12:  # goal node, held goal, reference point (MoveProbe v2)
                row['goal'], row['held_goal'] = e[8], e[9]
                rid = pos[t].get(eid, (0, 0, 0, '', -1))[4]
                rn, rp = pos[t].get(rid), pos.get(t - 1, {}).get(rid)
                rpt = (e[10], e[11])
                row['ref_mode'] = ('none' if rpt == (-1, -1) else 'unknown' if rn is None or rp is None else
                                   'still' if rpt == rn[1:3] == rp[1:3] else 'now' if rpt == rn[1:3] else
                                   'prev' if rpt == rp[1:3] else 'other')
            if len(e) >= 13:  # MoveProbe v3: the goal the reference's tick-start point gives
                row['start_goal'] = e[12]
                row['by_ref_move'] = e[12] == e[9] != e[8]  # the reference's own move this tick changed the goal
            if not any(v != (0, 0) for v in alts.values()) or eid not in pos[t]:
                row['out'] = 'nodisc'
                out.append(row)
                continue
            i = bisect.bisect_left(fticks, t)
            if i == 0 or i >= len(fticks):
                continue
            tp, tf = fticks[i - 1], fticks[i]
            pp = pos.get(tp, {}).get(eid)
            pf = pos.get(tf, {}).get(eid)
            row['tf'] = tf
            row['pre'] = pp is not None and (pp[0], pp[1], pp[2]) in frames[tp][0]
            if pf is None:
                row['out'] = 'gone'
            elif (pf[0], pf[1], pf[2]) in frames[tf][0]:
                row['out'] = 'crforge'
            else:
                row['out'] = 'neither'
                for nm, dv in alts.items():
                    if dv != (0, 0) and any(s == pf[0] and abs(x - pf[1] - dv[0]) <= 3 and abs(y - pf[2] - dv[1]) <= 3
                                            for s, x, y in frames[tf][1]):
                        row['out'] = nm
                        break
                near = [(x - pf[1], y - pf[2]) for s, x, y in frames[tf][1] if s == pf[0] and abs(x - pf[1]) + abs(y - pf[2]) < 60]
                row['rec_off'] = near[:3]
            out.append(row)
    return out


def parse_one(args):
    m, width = args
    try:
        return parse(m, width)
    finally:
        try:
            os.remove(os.path.join(WD, m + '.o.jsonl'))
        except OSError:
            pass


if __name__ == '__main__':
    width = int(os.environ.get('GRID_W', '36'))
    if not os.environ.get('SKIP_RUN'):
        open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(job(m) for m in ms) + '\n')
        r = subprocess.run(['java', '-Xmx48g', '-cp', lib + '/*:/workspace/pilot/bp3/build_aim', 'AimRun',
                            '/workspace/crforge_cache/tables/16.402.22', os.path.join(WD, 'jobs.txt'), str(threads)],
                           capture_output=True, text=True)
        print(r.stdout.strip(), r.stderr[-600:])
    rows = []
    with ProcessPoolExecutor(16) as ex:
        for out in ex.map(parse_one, [(m, width) for m in ms if os.path.exists(os.path.join(WD, m + '.o.jsonl'))]):
            rows += out
    with open(outp, 'w') as f:
        for x in rows:
            f.write(json.dumps(x) + '\n')
    import collections
    c = collections.Counter((x['sub'], x.get('pre'), x['out']) for x in rows)
    for k, v in sorted(c.items(), key=str):
        print(k, v)
