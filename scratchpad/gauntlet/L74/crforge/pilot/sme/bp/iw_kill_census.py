"""Hero Ice Wizard (and cube) target-lost events by who killed the lost target (A2c-BP, coordinator item 4).
    python3 iw_kill_census.py RUNDIR OUT.jsonl [THREADS]
KillRun (BpRun rows + lethal-hit log) on every match. For each hero IW / cube whose target-lost countdown starts on
line t0: the target it held on t0 - 1, its killer in step t0 (own = the IW or its cube at the same point; third = any
other unit; none = no lethal hit logged), crforge's re-acquire line S, the game's re-acquire frame G (lost_census rule),
and whether the window lies before the match's first divergence (clean)."""
import collections, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
run, outp = sys.argv[1], sys.argv[2]
threads = int(sys.argv[3]) if len(sys.argv) > 3 else 16
WD = '/workspace/pilot/bp/work/iwkill'
os.makedirs(WD, exist_ok=True)
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
ms = sorted(m for m in res if 'error' not in res[m] and os.path.exists(os.path.join(run, m, 'plan.json')))


def job(m):
    p = json.load(open(os.path.join(run, m, 'plan.json')))
    p['cmds'] = [{k: v for k, v in c.items() if k != '_src'} for c in p['cmds']]
    json.dump(p, open(os.path.join(WD, m + '.plan.json'), 'w'))
    return '%s %d %s 0' % (os.path.join(WD, m + '.plan.json'), res[m]['live_end'] + 2, os.path.join(WD, m + '.o.jsonl'))


def parse(m):
    path = os.path.join(WD, m + '.o.jsonl')
    kills = collections.defaultdict(list)
    for l in open(path + '.kills.jsonl'):
        k = json.loads(l)
        kills[(k['T'], k['target'])].append(k)
    rec = {}
    for l in open('/workspace/pilot/bp/rdet/%s.jsonl' % m):
        f = json.loads(l)
        rec[f['t']] = f['G']
    rts = sorted(rec)
    fd = res[m].get('first_div')
    prevt, state, out, lastrow = {}, {}, [], {}
    for l in open(path):
        o = json.loads(l)
        t = o['t']
        rows = {e[0]: e for e in o['E'] if e[1] == 'C'}
        for i, e in rows.items():
            if not e[2].startswith('IceWizardHero') or len(e) < 15 or not e[14]:
                continue
            lost = int(e[14].split('/')[3])
            st = state.get(i)
            if lost == 1 and (st is None or st[0] != 'wait'):
                old = prevt.get(i)
                ks = kills.get((t, old), [])
                kid = ks[0]['killer'] if ks else None
                kr = lastrow.get(kid) or rows.get(kid)
                who = 'none' if not ks else 'own' if kid == i or (kr and kr[2].startswith('IceWizardHero') and kr[3] == e[3]
                                                                   and (kr[4], kr[5]) == (e[4], e[5])) else 'third'
                state[i] = ('wait', t, e, who, ks[0]['via'] if ks else None)
            elif st and st[0] == 'wait' and e[12] not in (-1, None):
                _, t0, e0, who, via = st
                out.append(dict(match=m, id=i, name=e0[2], t0=t0, S=t, who=who, via=via, pos0=[e0[3], e0[4], e0[5]], hp0=e0[6]))
                state[i] = None
        for i, e in rows.items():
            if len(e) > 12:
                prevt[i] = e[12]
        lastrow = rows
    os.remove(path)
    os.remove(path + '.kills.jsonl')
    for ev in out:
        fr0 = max((t for t in rts if t <= ev['t0']), default=None)
        g = [r for r in rec.get(fr0, []) if (r[0], r[1], r[2]) == tuple(ev['pos0'])] if fr0 is not None else []
        if len(g) > 1:
            g = [r for r in g if r[4] == ev['hp0']] or g
        if len(g) > 1:
            g = [r for r in g if r[5] == ev['id']] or g
        ev['clean'] = fd is None or ev['S'] + 2 < fd
        if len(g) != 1:
            ev['G'] = None
            continue
        gen = g[0][5]
        G = next((t for t in rts if t > fr0 and any(r[5] == gen and r[6] is not None for r in rec[t])), None)
        prev = max((t for t in rts if G is not None and t < G), default=None)
        ev.update(G=G, Gprev=prev, late=G is not None and G < ev['S'])
    return out


if __name__ == '__main__':
    open(os.path.join(WD, 'jobs.txt'), 'w').write('\n'.join(job(m) for m in ms) + '\n')
    r = subprocess.run(['java', '-Xmx24g', '-cp', '/workspace/pilot/lib_008aa626/*:/workspace/pilot/bp/build_kill', 'KillRun',
                        '/workspace/crforge_cache/tables/16.402.22', os.path.join(WD, 'jobs.txt'), str(threads)],
                       capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr[-300:])
    agg = collections.Counter()
    with ProcessPoolExecutor(8) as ex, open(outp, 'w') as w:
        for evs in ex.map(parse, [m for m in ms if os.path.exists(os.path.join(WD, m + '.o.jsonl'))]):
            for ev in evs:
                w.write(json.dumps(ev) + '\n')
                if ev.get('G') is not None:
                    agg[(ev['name'], ev['who'], 'clean' if ev['clean'] else 'diverged', 'late' if ev['late'] else 'agree')] += 1
    for k, v in sorted(agg.items()):
        print(k, v)
