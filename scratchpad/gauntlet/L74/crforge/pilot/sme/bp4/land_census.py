"""A2c-BP4 item 2: pushes on a unit in its first visits after a landing (JUMPING 5 -> other: Hog / Ram / Royal Hog
river jumps) or an arrival (DEPLOYING 4 / WAITING_TO_DEPLOY 11 -> other: Miner / Drill emergence, Graveyard, every
deploy), crforge against the game.
    python3 land_census.py RUNDIR LIB OUT.jsonl [THREADS]      (AimRun4 in /workspace/pilot/bp4/build_aim4)
One row per visit k = 0..3 after the transition tick L (k = 0 is the visit on which the state changes) in which a
displacement of the unit carried a push (MoveProbe 'prop' push count > 0):
  from    the state left (5 / 4 / 11); enemy / ally  pushers of the other / same side ('push' events)
  out     at the first frame at or after the visit: crforge (unit exact), nopush (a recorded body within 2 units of
          the unit's start + its proposal without the push, the frame being that same tick), neither, gone
  pre     the unit exact at the frame before; clean  t <= the run's first divergence"""
import bisect, collections, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp4/work/land')
FR = '/workspace/pilot/sme_live/frames2'
FROM = (4, 5, 11)
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json'))
            and (not os.environ.get('ONLY') or m[10:] in os.environ['ONLY'].split(',')))


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
        pos[o['t']] = {c[0]: (c[2], c[3], c[4], c[1], c[7], c[8]) for c in o['C']}
        evs.append((o['t'], o['ev']))
    out, prev, land = [], {}, {}  # land: id -> (L, from state)
    for t, ev in evs:
        cur = pos[t]
        for i, c in cur.items():
            p = prev.get(i)
            if p is not None and p[4] in FROM and c[4] != p[4] and c[4] not in FROM:
                land[i] = (t, p[4])
        prev = cur
        pushes = collections.defaultdict(list)
        for e in ev:
            if e[0] == 'push':
                pushes[e[1]].append(e[2])
        disp = {e[1]: e for e in ev if e[0] == 'disp'}
        for e in ev:
            if e[0] != 'prop' or e[1] not in land or e[1] not in cur or e[1] not in disp:
                continue
            L, fr = land[e[1]]
            k = t - L
            if not 0 <= k <= 3 or e[2 + 4] == 0:
                continue
            v, d = e[2:], disp[e[1]]
            side = cur[e[1]][0]
            enemy = [o for o in pushes[e[1]] if o in cur and cur[o][0] != side]
            ally = [o for o in pushes[e[1]] if o in cur and cur[o][0] == side]
            nopush = (d[2] + v[0], d[3] + v[1])
            row = {'m': m[10:], 't': t, 'id': e[1], 'name': cur[e[1]][3], 'from': fr, 'k': k, 'enemy': len(enemy),
                   'ally': len(ally), 'enemy_names': sorted({cur[o][3] for o in enemy}), 'push': [v[2], v[3]],
                   'z_before': prev.get(e[1], (0,) * 6)[5] if False else None, 'clean': fd is None or t <= fd}
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
            elif tf == t and any(s == pf[0] and abs(x - nopush[0]) <= 2 and abs(y - nopush[1]) <= 2 for s, x, y in frames[tf][1]):
                row['out'] = 'nopush'
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
    dec = [x for x in rows if x.get('pre') and x['clean']]
    print('pushed visits after a transition %d; pre exact and clean %d' % (len(rows), len(dec)))
    c = collections.Counter((x['from'], x['k'], x['enemy'] > 0, x['out']) for x in dec)
    print('(from state, visit k, enemy pusher, out):')
    for kk, v in sorted(c.items(), key=str):
        print(' ', kk, v)
    c = collections.Counter((x['name'], x['k'], x['out']) for x in dec if x['from'] == 5 and x['enemy'])
    print('jump landings with an enemy pusher (name, k, out):')
    for kk, v in sorted(c.items(), key=str):
        print(' ', kk, v)
    for x in rows:
        if x.get('pre') and x['clean'] and x['out'] != 'crforge':
            print(x)
