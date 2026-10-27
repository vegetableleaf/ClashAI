"""River-jump landings (JUMPING state 5 -> other), with or without another body in contact at the landing, against
where the game first diverges (A2c-BP, coordinator item 3). python3 jump_census.py RUNDIR OUT.json [THREADS]
Contact: an enemy body (C row of the other side) within 1,200 units of the landing point on the landing line. Outcome as in
replan_census.py: onset (first divergence within 20 ticks after, a diverging body within 1,500 units), clean (the
landing and 20 ticks after are before the first divergence), after (not counted)."""
import collections, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, outp = sys.argv[1], sys.argv[2]
threads = int(sys.argv[3]) if len(sys.argv) > 3 else 16
WD = '/workspace/pilot/bp/work/jump'
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
    pts = [(x[1][1], x[1][2]) for x in (r.get('first_detail') or []) if 'only' in x[0] and isinstance(x[1], list) and len(x[1]) >= 3]
    prev, ev = {}, []
    path = os.path.join(WD, m + '.o.jsonl')
    for l in open(path):
        o = json.loads(l)
        t = o['t']
        cur = {e[0]: (e[13], e[4], e[5], e[2], e[3]) for e in o['E'] if e[1] == 'C' and len(e) > 13}
        for i, c in cur.items():
            p = prev.get(i)
            if p and p[0] == 5 and c[0] != 5:
                near = [j for j, d in cur.items() if j != i and d[4] != c[4] and abs(d[1] - c[1]) + abs(d[2] - c[2]) <= 1200]
                if fd is not None and t <= fd <= t + 20 and any(abs(x - c[1]) + abs(y - c[2]) <= 1500 for x, y in pts):
                    out = 'onset'
                elif fd is None or t + 20 < fd:
                    out = 'clean'
                else:
                    out = 'after'
                ev.append((c[3], 'contact' if near else 'alone', out, t))
        prev = cur
    os.remove(path)
    return m, ev


if __name__ == '__main__':
    open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(job(m) for m in ms) + '\n')
    r = subprocess.run(['java', '-Xmx24g', '-cp', '/workspace/pilot/lib_008aa626/*:/workspace/pilot/bp/build_bpx', 'BpRun',
                        '/workspace/crforge_cache/tables/16.402.22', os.path.join(WD, 'jobs.txt'), str(threads)],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr[-300:])
    agg, onsets = collections.Counter(), []
    with ProcessPoolExecutor(8) as ex:
        for m, ev in ex.map(parse, [m for m in ms if os.path.exists(os.path.join(WD, m + '.o.jsonl'))]):
            for name, ct, out, t in ev:
                agg[(name, ct, out)] += 1
                if out == 'onset':
                    onsets.append((m, name, ct, t, res[m]['first_div']))
    json.dump({'counts': {'|'.join(k): v for k, v in agg.items()}, 'onsets': onsets}, open(outp, 'w'), indent=0)
    for k, v in sorted(agg.items()):
        print(k, v)
    for x in onsets:
        print('onset', x)
