"""FREEZE-LIVE step 1 (pod): for each exact RECON record with Hero IceWizard presses:
  base run  = the stored plan (re-scored against the live frames: must reproduce 'exact'),
  per press = the same plan with THAT press dropped (kind skip): the engine's no-press counterfactual from the true history,
  plus freeze exposure (enemy troops of the cube's side within 2.5 t when the cube stands) and the HP / unit differences press - no press.
Run (pod, CPUs 226-237):  cd /workspace/smeR6/sme && R=/workspace/smeR6 SME_THREADS=2 bash recon/envR.sh python3 /dev/shm/fl_cf.py LIST.jsonl OUT.jsonl [WORKERS]
SME_TABLES (env) selects the tables: a perturbed copy in /dev/shm for the sensitivity runs (engine code untouched).
LIST row: {match, plan_path, frames_path, me}"""
import collections, copy, json, math, os, shutil, sys, time
from concurrent.futures import ProcessPoolExecutor

R = os.environ.get('R', '/workspace/smeR6')
sys.path.insert(0, R + '/sme'); sys.path.insert(0, R + '/sme/recon')
import sme_live  # noqa: E402
import sme  # noqa: E402
from sme import run_batch  # noqa: E402
import recon  # noqa: E402

TAB = os.environ['SME_TABLES']
BASE_TAB = '/workspace/crforge_cache/tables/16.635.3'
WIN = (0, 25, 50, 75, 100, 150, 200, 300, 450, 600, 900)
CUBE = 'IceWizardHero_IceCube'


def cost_map():
    """unit name -> approximate elixir per body (card ManaCost / bodies)."""
    out = {}
    for f in ('spells_characters.json', 'spells_hero_form.json', 'spells_evolved.json'):
        try:
            rows = json.load(open(os.path.join(BASE_TAB, f)))['rows']
        except Exception:
            continue
        for n, r in rows.items():
            c = r['columns']
            mc, sc = c.get('ManaCost'), c.get('SummonCharacter')
            if not mc or not sc:
                continue
            k = c.get('SummonNumber')
            k = k if isinstance(k, int) and k > 0 else 1
            out.setdefault(sc, mc / k)
            out.setdefault(n, mc / k)
    return out


COST = cost_map()


def refused(o, me):
    return {(p[0], p[1]) for x in o for p in x['plays'] if p[3] == me and (p[4] != 0 or not p[2])}


def is_iw_press(plan, c):
    if c.get('kind') != 'ability':
        return False
    u = c.get('unit') or ''
    if u.startswith('cmd'):
        try:
            k = int(u[3:].split('_')[0])
            return plan['cmds'][k].get('card') == 'IceWizard'
        except Exception:
            return False
    return False


def rows_of(o, cls, side=None):
    return [e for e in o['E'] if e[1] == cls and (side is None or e[3] == side)]


def exposure(by, run, press_side, hz=(10, 20, 30, 45, 60, 80)):
    """At ticks run+d: the cube(s) of press_side, enemy bodies within 2.5 t of a cube, their elixir (approx) -> the best over d."""
    best = None
    for d in hz:
        o = by.get(run + d)   # run = the tick the command runs; the cube deploys ~8-10 ticks later
        if o is None:
            continue
        cubes = [e for e in o['E'] if e[1] == 'C' and e[2] == CUBE and e[3] == press_side]
        if not cubes:
            continue
        n, el, names = 0, 0.0, []
        for e in o['E']:
            if e[1] == 'C' and e[3] != press_side and e[2] != CUBE:
                if any(math.hypot(e[4] - c[4], e[5] - c[5]) <= 2500 for c in cubes):
                    n += 1
                    el += COST.get(e[2], 3.0)
                    names.append(e[2])
        if best is None or el > best['el']:
            best = {'d': d, 'n': n, 'el': round(el, 1), 'names': names[:12], 'cubes': len(cubes)}
    return best


def hp_by_side(o):
    """princess / king HP per side, and total HP of non-tower bodies per side."""
    tw = {}
    for e in o['E']:
        if e[1] == 'T':
            tw[(e[3], e[4], e[5])] = e[6]
    bod = {0: 0, 1: 0}
    for e in o['E']:
        if e[1] == 'C' and e[2] != CUBE:
            bod[e[3]] += max(e[6], 0)
    return tw, bod


def one(item):
    m = item['match']
    t0 = time.time()
    try:
        plan = json.load(open(item['plan_path']))
        frames = sme_live.load_frames(item['frames_path'])
        me, end = item['me'], max(frames)
        presses = [i for i, c in enumerate(plan['cmds']) if is_iw_press(plan, c)]
        plans = [plan]
        for i in presses:
            p = copy.deepcopy(plan)
            p['cmds'][i] = {'kind': 'skip', 'given': 0, 'run': 0, 'side': plan['cmds'][i]['side'], '_src': {}}
            plans.append(p)
        mode = item.get('mode', 'full')   # 'base' = base run only
        if mode == 'base':
            plans = plans[:1]
        work = '/dev/shm/fl_work_%d' % os.getpid()
        shutil.rmtree(work, ignore_errors=True)
        res = run_batch([(recon.runnable(p), end + 3, 0) for p in plans], work)
        out = {'match': m, 'me': me, 'presses': [], 'frames': len(frames)}
        if res[0] is None:
            out['error'] = 'base run failed: ' + str(sme.ERRORS.get(0, ''))[:200]
            return out
        by0 = {x['t']: x for x in res[0]}
        an0 = sme_live.analyse(res[0], frames, me)
        out['base'] = {'counts': an0['counts'], 'first': an0['first']}
        for j, i in enumerate(presses):
            c = plan['cmds'][i]
            row = {'i': i, 'side': c['side'], 'run': c['run'], 'src': (c.get('_src') or {}).get('source')}
            row['exposure'] = exposure(by0, c['run'], c['side'])
            row['cube_ticks'] = sum(1 for t in range(c['run'], c['run'] + 200) if t in by0 and any(e[1] == 'C' and e[2] == CUBE and e[3] == c['side'] for e in by0[t]['E']))
            o1 = res[j + 1] if mode != 'base' else None
            if o1 is not None:
                by1 = {x['t']: x for x in o1}
                an1 = sme_live.analyse(o1, frames, me)
                row['nopress'] = {'counts': an1['counts'], 'first': an1['first']}
                # recorded plays the live history REFUSED but the no-press branch accepts (the press's 2 elixir): they favour the no-press branch
                row['ref_gain'] = sorted(t for (cc, t) in refused(res[0], me) - refused(o1, me) if c['run'] <= t <= c['run'] + 900)
                eff = {}
                for d in WIN:
                    t = c["run"] + d
                    a, b = by0.get(t), by1.get(t)
                    if a is None or b is None:
                        continue
                    tw0, bod0 = hp_by_side(a)
                    tw1, bod1 = hp_by_side(b)
                    # units of the cube-side's ENEMY that differ (side,x,y,hp multiset) between press and no-press
                    v = 1 - c['side']
                    u0 = sorted((e[4], e[5], e[6]) for e in a['E'] if e[1] == 'C' and e[3] == v)
                    u1 = sorted((e[4], e[5], e[6]) for e in b['E'] if e[1] == 'C' and e[3] == v)
                    d0, d1 = collections.Counter(u0), collections.Counter(u1)
                    ndiff = sum(((d0 - d1)).values())
                    # princess HP of the presser's side (the side the freeze defends when the press is on our own half) and of the victim side
                    ptw = {k: (tw0.get(k), tw1.get(k)) for k in tw0 if k[0] == c['side']}
                    vtw = {k: (tw0.get(k), tw1.get(k)) for k in tw0 if k[0] == v}
                    eff[d] = {'ndiff_enemy_units': ndiff, 'presser_towers': [[k[1], k[2], x, y] for k, (x, y) in ptw.items()],
                              'victim_towers': [[k[1], k[2], x, y] for k, (x, y) in vtw.items()],
                              'enemy_body_hp': [bod0[v], bod1[v]], 'own_body_hp': [bod0[c['side']], bod1[c['side']]]}
                row['eff'] = eff
            out['presses'].append(row)
        out['secs'] = round(time.time() - t0, 1)
        shutil.rmtree(work, ignore_errors=True)
        return out
    except Exception:  # noqa
        import traceback
        return {'match': m, 'error': traceback.format_exc()[-600:]}


def main():
    lst = [json.loads(l) for l in open(sys.argv[1])]
    outp = sys.argv[2]
    nw = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    if len(sys.argv) > 4:
        for r in lst:
            r['mode'] = sys.argv[4]
    with open(outp, 'a') as w, ProcessPoolExecutor(nw) as ex:
        for r in ex.map(one, lst):
            w.write(json.dumps(r) + '\n'); w.flush()
            print(r['match'], r.get('error') or (r.get('base'), r.get('secs')), flush=True)


if __name__ == '__main__':
    main()
