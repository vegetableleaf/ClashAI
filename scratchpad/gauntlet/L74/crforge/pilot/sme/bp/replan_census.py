"""Route replans in crforge, by trigger, against where the game first diverges (A2c-BP, coordinator item 2).
    python3 replan_census.py RUNDIR OUT.json [THREADS]
A replan: a body's route node count goes up, or its next node changes without a pop. Trigger at that tick:
  retarget       the body's reference changed on this tick or the one before
  target_jump    the reference moved more than 100 units in the tick before (a recoil / knockback / dash)
  target_moving  the reference moved 1-100 units
  target_still   the reference did not move, or no reference
Outcome per event: 'onset' when the match's first divergence (RUNDIR results) is within 20 ticks after it and a body
within 1,500 units of it diverges there (first detail), else 'clean' when the event and 20 ticks after it are before the
first divergence (or the match is exact), else 'after' (inside an already diverged stretch; not counted)."""
import collections, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, outp = sys.argv[1], sys.argv[2]
threads = int(sys.argv[3]) if len(sys.argv) > 3 else 16
WD = '/workspace/pilot/bp/work/replan'
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json')))


def job(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), res[m]['live_end'] + 2, os.path.join(WD, m + '.o.jsonl'))


def parse(m):
    r = res[m]
    fd = r.get('first_div')
    det = (r.get('first_detail') or [])
    onset_pts = [(x[1][1], x[1][2]) for x in det if 'only' in x[0] and isinstance(x[1], list) and len(x[1]) >= 3]
    prev, pos = {}, {}
    ev = []
    path = os.path.join(WD, m + '.o.jsonl')
    for l in open(path):
        o = json.loads(l)
        t = o['t']
        cur = {}
        for e in o['E']:
            if e[1] != 'C' or len(e) < 16:
                continue
            n, nodes, _ = (e[15].split(':') + ['', ''])[:3] if e[15] else ('0', '', '')
            cur[e[0]] = (int(n or 0), nodes.split(';')[0] if nodes else '', e[12], e[4], e[5], e[2])
        for i, c in cur.items():
            p = prev.get(i)
            if p is None or c[0] == 0:
                continue
            pop = c[0] == p[0] - 1
            rep = c[0] > p[0] or (c[0] == p[0] and c[1] != p[1]) or c[0] < p[0] - 1
            if not rep or pop:
                continue
            tg = c[2]
            tr = 'target_still'
            if tg != p[2]:
                tr = 'retarget'
            elif tg is not None and tg >= 0 and tg in pos and tg in cur:
                d = abs(cur[tg][3] - pos[tg][0]) + abs(cur[tg][4] - pos[tg][1])
                tr = 'target_jump' if d > 100 else 'target_moving' if d > 0 else 'target_still'
            if fd is not None and t <= fd <= t + 20 and any(abs(x - c[3]) + abs(y - c[4]) <= 1500 for x, y in onset_pts):
                out = 'onset'
            elif fd is None or t + 20 < fd:
                out = 'clean'
            else:
                out = 'after'
            ev.append((c[5], tr, out, t))
        prev = cur
        pos = {i: (c[3], c[4]) for i, c in cur.items()}
    os.remove(path)
    return m, ev


if __name__ == '__main__':
    open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(job(m) for m in ms) + '\n')
    r = subprocess.run(['java', '-Xmx24g', '-cp', '/workspace/pilot/lib_008aa626/*:/workspace/pilot/bp/build_bpx2', 'BpRun',
                        '/workspace/crforge_cache/tables/16.402.22', os.path.join(WD, 'jobs.txt'), str(threads)],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr[-300:])
    agg = collections.Counter()
    onsets = []
    with ProcessPoolExecutor(8) as ex:
        for m, ev in ex.map(parse, [m for m in ms if os.path.exists(os.path.join(WD, m + '.o.jsonl'))]):
            for name, tr, out, t in ev:
                agg[(tr, out)] += 1
                if out == 'onset':
                    onsets.append((m, name, tr, t, res[m]['first_div']))
    json.dump({'counts': {'%s|%s' % k: v for k, v in agg.items()}, 'onsets': onsets}, open(outp, 'w'), indent=0)
    for k, v in sorted(agg.items()):
        print(k, v)
    for x in onsets:
        print('onset', x)
