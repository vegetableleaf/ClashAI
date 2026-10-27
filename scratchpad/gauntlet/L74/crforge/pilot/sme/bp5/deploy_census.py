"""A2c-BP5 item 3: deploy end of every character crforge spawns, crforge against the game.
    python3 deploy_census.py RUNDIR LIB OUT.jsonl [THREADS]     (AimRun5, /workspace/pilot/bp5/build_aim5)
crforge: born tick tb (first C row, state 4 = DEPLOYING) at point P; end ce = first tick its state is not 4.
game: the recorded bodies of its side at P with the deploy code (frame E row [side, x, y, card, hp, code], code 14) are
matched by count (k-th unit born at P on that side this tick = k-th code-14 body there); the game's end lies in
(g_lo, g_hi]: g_lo = last frame where the count of code-14 bodies at P is >= k, g_hi = the next frame.
out: 'agree' (g_lo < ce <= g_hi), 'game_earlier' (ce > g_hi), 'game_later' (ce <= g_lo), 'nomatch' (no code-14 body at P
at the first frame >= tb), 'gone'.  src: from the BarbLog when a BarbLog projectile of that side vanished within 3 ticks of
tb within 600 units of P.
mv (first move): crforge's first tick cm its point leaves P; the game's lies in (m_lo, m_hi], the frames around the
last frame with >= k bodies of the side at P (any code); mv = agree / game_earlier / game_later.  clean: ce <= the run's first divergence or none; pre: every body of the side at P matched at
the first frame >= tb."""
import bisect, collections, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, lib, outp = sys.argv[1], sys.argv[2], sys.argv[3]
threads = int(sys.argv[4]) if len(sys.argv) > 4 else 16
WD = os.environ.get('WD', '/workspace/pilot/bp5/work/deploy')
FR = '/workspace/pilot/sme_live/frames2'
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json')))
islog = lambda n: 'barblog' in n.lower()


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
        frames[f['t']] = collections.Counter((e[0], e[1], e[2], e[5] == 14) for e in f['E'])
        frames[f['t']].update((e[0], e[1], e[2], None) for e in f['E'])
    ft = sorted(frames)
    born, state, logs_gone, moved = {}, {}, [], {}
    prev_pa = {}
    for l in open(os.path.join(WD, m + '.o.jsonl')):
        o = json.loads(l)
        t = o['t']
        for c in o['C']:
            if c[0] not in born:
                born[c[0]] = (t, c[1], c[2], c[3], c[4], c[7])
            if c[0] not in moved and (c[3], c[4]) != born[c[0]][3:5]:
                moved[c[0]] = t
            if c[0] not in state and c[7] != 4 and born[c[0]][5] == 4:
                state[c[0]] = t
        cur = {p[0]: p for p in o.get('PA', [])}
        for i, p in prev_pa.items():
            if i not in cur and islog(p[2]):
                logs_gone.append((t, p))
        prev_pa = cur
    out = []
    groups = collections.defaultdict(list)
    for i, b in born.items():
        if b[5] == 4:
            groups[(b[0], b[2], b[3], b[4])].append(i)
    for (tb, sd, x, y), ids in groups.items():
        j = bisect.bisect_left(ft, tb)
        if j >= len(ft):
            continue
        n0 = frames[ft[j]][(sd, x, y, True)]
        for k, i in enumerate(sorted(ids)):
            ce = state.get(i)
            src = 'barblog' if any(abs(tl - tb) <= 3 and p[3] == sd and abs(p[4] - x) + abs(p[5] - y) <= 600 for tl, p in logs_gone) else ''
            row = {'m': m[10:], 'id': i, 'name': born[i][1], 'side': sd, 'tb': tb, 'ce': ce, 'src': src, 'pre': n0 >= len(ids),
                   'clean': ce is not None and (fd is None or ce <= fd)}
            if ce is None:
                row['out'] = 'gone'
            elif n0 <= k:
                row['out'] = 'nomatch'
            else:
                lo = j
                while lo + 1 < len(ft) and frames[ft[lo + 1]][(sd, x, y, True)] > k:
                    lo += 1
                g_lo, g_hi = ft[lo], ft[lo + 1] if lo + 1 < len(ft) else None
                row.update({'g_lo': g_lo, 'g_hi': g_hi})
                row['out'] = 'agree' if g_hi is not None and g_lo < ce <= g_hi else 'game_earlier' if g_hi is not None and ce > g_hi else 'game_later'
            cm = moved.get(i)
            if cm is not None and frames[ft[j]][(sd, x, y, None)] > k:
                lo = j
                while lo + 1 < len(ft) and frames[ft[lo + 1]][(sd, x, y, None)] > k:
                    lo += 1
                if lo + 1 < len(ft):
                    row.update({'cm': cm, 'm_lo': ft[lo], 'm_hi': ft[lo + 1]})
                    row['mv'] = 'agree' if ft[lo] < cm <= ft[lo + 1] else 'game_earlier' if cm > ft[lo + 1] else 'game_later'
                    row['mv_clean'] = fd is None or cm <= fd
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


if __name__ == '__main__':
    if not os.environ.get('SKIP_RUN'):
        open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(job(m) for m in ms) + '\n')
        r = subprocess.run(['java', '-Xmx64g', '-cp', lib + '/*:/workspace/pilot/bp5/build_aim5', 'AimRun5',
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
    print('units %d; pre and clean %d' % (len(rows), len(dec)))
    print('all  ', collections.Counter(x['out'] for x in dec))
    print('barblog', collections.Counter(x['out'] for x in dec if x['src']))
    c = collections.Counter((x['name'], x['out']) for x in dec)
    for k, v in sorted(c.items(), key=lambda z: -z[1])[:40]:
        print(' ', k, v)
    mv = [x for x in rows if x['pre'] and x.get('mv_clean') and 'mv' in x]
    print('first move, all', collections.Counter(x['mv'] for x in mv))
    print('first move, barblog', collections.Counter(x['mv'] for x in mv if x['src']))
    for x in mv:
        if x['src'] and x['mv'] != 'agree':
            print(x)
