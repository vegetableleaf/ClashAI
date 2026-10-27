"""Inside-step update order of the game, from every torn / isolated single div frame (A2c-BP, coordinator item 1).
Run with the run's SME env (bpB: + SME_BP_MIXPH=1). python3 order_census.py RUNDIR OUT.jsonl [WORKERS]
Per frame t (classes torn_step / torn_cmd / torn_mixed, and div frames whose neighbours are not div), the sim objects
that change in step t+1 are sorted by subsystem, and each is read at its t state (0), its t+1 state (1) or neither (x):
  mv    a body that moves          dec   a building's hp change equal to its previous step's (decay)
  dmg   another hp change          del   a body removed in the step (0: still listed)
  new   a body made in the step    pmv / pdel / pnew   projectiles moving / removed / made
  anew / adel  area effects made / removed           el    our elixir (0: sim t, 1: sim t+1, c: t minus whole elixir)"""
import collections, json, os, sys
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, '/workspace/pilot/sme')
import sme_live
from sme import run_batch
from sme_live import load_frames, runnable, analyse, repr_rows

run, outp = sys.argv[1], sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
ME = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open('/workspace/pilot/inputs_v9/inputs_rngfree.jsonl')}


def feats(f, o0, o1, om, me):
    rows = lambda o: {e[0]: e for e in repr_rows(o)}  # noqa: E731
    a, b, z = rows(o0), rows(o1), rows(om) if om else {}
    rb = collections.Counter((e[0], e[1], e[2]) for e in f['E'])
    rbh = collections.defaultdict(list)
    for e in f['E']:
        rbh[(e[0], e[1], e[2])].append(e[4])
    rp = collections.Counter((p[0], p[1], p[2]) for p in f['P'])
    ra = collections.Counter((p[0], p[1], p[2]) for p in f['A'])
    out = collections.defaultdict(collections.Counter)
    for i in set(a) | set(b):
        ea, eb = a.get(i), b.get(i)
        cls = (ea or eb)[1]
        if cls in 'TC':
            if ea and eb:
                pa, pb = (ea[3], ea[4], ea[5]), (eb[3], eb[4], eb[5])
                if pa != pb:
                    out['mv']['1' if rb[pb] else '0' if rb[pa] else 'x'] += 1
                if ea[6] != eb[6] and ea[6] > 0:
                    pos = pb if rb[pb] else pa if rb[pa] else None
                    ez = z.get(i)
                    k = 'dec' if ez and cls == 'C' and ez[6] - ea[6] == ea[6] - eb[6] and 0 < ea[6] - eb[6] <= 60 else 'dmg'
                    hs = [h for h in rbh.get(pos, []) if h != -1] if pos else []
                    out[k]['1' if eb[6] in hs else '0' if ea[6] in hs else 'x'] += 1
            elif ea:
                out['del']['0' if rb[(ea[3], ea[4], ea[5])] else '1'] += 1
            else:
                out['new']['1' if rb[(eb[3], eb[4], eb[5])] else '0'] += 1
        elif cls in 'PA':
            pre = 'p' if cls == 'P' else 'a'
            r = rp if cls == 'P' else ra
            if ea and eb:
                if (ea[4], ea[5]) != (eb[4], eb[5]):
                    out[pre + 'mv']['1' if r[(eb[3], eb[4], eb[5])] else '0' if r[(ea[3], ea[4], ea[5])] else 'x'] += 1
            elif ea:
                out[pre + 'del']['0' if r[(ea[3], ea[4], ea[5])] else '1'] += 1
            else:
                out[pre + 'new']['1' if r[(eb[3], eb[4], eb[5])] else '0'] += 1
    e0, e1 = o0['S'][me][0], o1['S'][me][0]
    if e0 != e1:
        el = f['el']
        out['el']['1' if el == e1 else '0' if el == e0 else 'c' if (e0 - el) % 10000 == 0 and el < e0 else 'x'] += 1
    return {k: dict(v) for k, v in out.items()}


def one(m):
    try:
        plan = json.load(open(os.path.join(run, m, 'plan.json')))
        frames = load_frames('/workspace/pilot/sme_live/frames2/%s.jsonl' % m)
        me = ME[m]
        o = run_batch([(runnable(plan), max(frames) + 3, 0)], '/workspace/pilot/bp/work/ord_%s' % m)[0]
        if o is None:
            return []
        by = {x['t']: x for x in o}
        an = analyse(o, frames, me)
        cls = an['cls']
        ts = sorted(cls)
        res = []
        for k, t in enumerate(ts):
            c = cls[t]
            iso = c == 'div' and all(cls.get(ts[j]) != 'div' for j in (k - 1, k + 1) if 0 <= j < len(ts))
            if c not in ('torn_step', 'torn_cmd', 'torn_mixed') and not iso:
                continue
            if t + 1 not in by:
                continue
            res.append(dict(match=m, t=t, cls=c, f=feats(frames[t], by[t], by[t + 1], by.get(t - 1), me)))
        return res
    except Exception as e:  # noqa: BLE001
        return [dict(match=m, error=repr(e))]
    finally:
        import shutil
        shutil.rmtree('/workspace/pilot/bp/work/ord_%s' % m, ignore_errors=True)


if __name__ == '__main__':
    ms = sorted(x for x in os.listdir(run) if x.startswith('live_play_') and os.path.exists(os.path.join(run, x, 'plan.json')))
    with ProcessPoolExecutor(workers) as ex, open(outp, 'w') as w:
        for res in ex.map(one, ms):
            for r in res:
                w.write(json.dumps(r) + '\n')
            w.flush()
