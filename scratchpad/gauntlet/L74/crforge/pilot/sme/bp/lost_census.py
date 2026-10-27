"""Target-lost -> re-acquire census, crforge vs the game (A2c-BP). Every unit whose target-lost countdown starts
(RemovalNotice sets it to 1) is followed to the line where it holds a reference again (S). The game body is the reader
body at the same (side, x, y) as the sim body on the last recorded frame at or before the loss (exact there); the game
re-acquires on the first recorded frame G where that body (by generation) holds a target again.
    python3 lost_census.py RUNDIR OUT.jsonl [THREADS] [M1,M2,...]
Per event: unit row name, loss line, attack timer / load at the loss, S, G, the recorded frame before G, and
'late' = the game held a target on a frame earlier than S (crforge re-acquires later than the game)."""
import json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, outp = sys.argv[1], sys.argv[2]
threads = int(sys.argv[3]) if len(sys.argv) > 3 else 16
only = set(sys.argv[4].split(',')) if len(sys.argv) > 4 else None
WD = '/workspace/pilot/bp/work/lost'
os.makedirs(WD, exist_ok=True)
ms = sorted(m for m in os.listdir(run) if m.startswith('live_play_') and os.path.exists(os.path.join(run, m, 'plan.json'))
            and (only is None or m in only))


def rows_of(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    end = max(json.loads(l)['t'] for l in open('/workspace/pilot/sme_live/frames2/%s.jsonl' % m))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), end + 2, os.path.join(WD, m + '.o.jsonl'))


def events(m):
    rec = {}
    for l in open('/workspace/pilot/bp/rdet/%s.jsonl' % m):
        f = json.loads(l)
        rec[f['t']] = f['G']
    rts = sorted(rec)
    out, state = [], {}
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        t = o['t']
        for e in o['E']:
            if e[1] != 'C' or len(e) < 15 or not e[14]:
                continue
            tm = e[14].split('/')
            lost = int(tm[3])
            i = e[0]
            st = state.get(i)
            if lost == 1 and (st is None or st[0] != 'wait'):
                state[i] = ('wait', t, e[2], (e[3], e[4], e[5]), int(tm[0]), int(tm[1]), e[6])
            elif st and st[0] == 'wait' and e[12] not in (-1, None):
                _, t0, name, pos0, at, ld, hp0 = st
                out.append(dict(match=m, id=i, name=name, t0=t0, S=t, atk=at, load=ld, pos0=pos0, hp0=hp0))
                state[i] = None
    os.remove(os.path.join(WD, m + '.o.jsonl'))
    res = []
    for ev in out:
        fr0 = max((t for t in rts if t <= ev['t0']), default=None)
        if fr0 is None:
            continue
        side, x, y = ev['pos0']
        # the sim position at t0 equals the reader's at fr0 only if fr0 == t0 or the body stood still; require it
        g = [r for r in rec[fr0] if (r[0], r[1], r[2]) == (side, x, y)]
        if len(g) > 1:  # a hero and its cube at one point: the hp tells them apart
            g = [r for r in g if r[4] == ev['hp0']] or g
        if len(g) > 1:  # same hp too: the reader generation equal to the sim id, when there is one
            g = [r for r in g if r[5] == ev['id']] or g
        if len(g) != 1:
            ev['G'] = None
            res.append(ev)
            continue
        gen = g[0][5]
        G = next((t for t in rts if t > fr0 and any(r[5] == gen and r[6] is not None for r in rec[t])), None)
        prev = max((t for t in rts if G is not None and t < G), default=None)
        ev.update(gen=gen, fr0=fr0, G=G, Gprev=prev, late=G is not None and G < ev['S'])
        res.append(ev)
    return res


if __name__ == '__main__':
    jobs = [rows_of(m) for m in ms]
    jf = os.path.join(WD, 'jobs.txt')
    open(jf, 'w').write('\n'.join(jobs) + '\n')
    r = subprocess.run(['java', '-Xmx24g', '-cp', '/workspace/pilot/lib_008aa626/*:/workspace/pilot/bp/build_bpx', 'BpRun',
                        '/workspace/crforge_cache/tables/16.402.22', jf, str(threads)], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr[-500:])
    with ProcessPoolExecutor(8) as ex, open(outp, 'w') as w:
        for res in ex.map(events, [m for m in ms if os.path.exists(os.path.join(WD, m + '.o.jsonl'))]):
            for ev in res:
                w.write(json.dumps(ev) + '\n')
