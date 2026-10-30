"""RECON planted recall (RECON.md section 7 item 2; pod). Take EXACT final plans of earlier recon_search runs, plant one
known input error each, search from the planted plan, and ask: did the search restore the planted truth, fix the
window with a different edit, or not fix it?

  python3 recon/plant_recall.py --inputs I.jsonl --frames FRAMEDIR --plans RUN1,RUN2 --out OUT [--workers 4] [--only ..]
  python3 recon/plant_recall.py --summary OUT     (table from OUT/plant_results.jsonl)

Plant types (one per type per match when a candidate exists; candidate picked by a sha-seeded RNG):
  drop_zap    delete an opponent spell the reader can miss (Zap class: on the board <= recon.VIS_MAX ticks); add (a) restores
  drop_spell  delete an opponent spell the reader cannot miss (Log, Fireball, ...): outside add (a) by design (visible rule)
  drop_troop  delete an opponent troop play; add (b) restores (at the first-seen body point)
  shift       move one play's run tick to another tick of its extractor window [lo, hi]; shift restores
  swap        swap two same-tick plays' order; swap restores
  point_opp   move an opponent troop play's point by +500 x (or -500); the +-500 grid restores
  point_own   move one of our troop plays' point by +700 x (or -700); outside the grid by design (first-seen point only)
Outcomes: invisible (the planted plan is still exact), restored (the planted command's truth is back: same run / point /
order; for a drop, the same card and side re-added within 2 ticks and 300 units), alt_fix (exact, truth not restored),
not_fixed; restored_inexact = restored but the match is not exact. Rank: the first round whose ranked list (log 'top') holds the inverse edit, and its position there."""
import argparse, hashlib, json, math, os, random, sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import recon_search  # noqa: E402

TYPES = ('drop_zap', 'drop_spell', 'drop_troop', 'shift', 'swap', 'point_opp', 'point_own')


def rng(match, typ):
    return random.Random(int(hashlib.sha1((match + typ).encode()).hexdigest()[:8], 16))


def short_spell(tab, card, side, x, y):
    """The reader can miss it: on the board <= VIS_MAX ticks (recon.hypotheses' add (a) visible rule)."""
    if not tab.is_spell(card) or not tab.radius(card):
        return False
    pj = tab.projectile(card)
    if pj and pj[2]:
        return False
    k = recon.KINGS[side]
    vis = math.ceil(math.hypot(x - k[0], y - k[1]) / pj[0]) if pj else (tab.area_life_ticks(card) or 0)
    return vis <= recon.VIS_MAX


def plants(plan, me, end, tab, match):
    """-> [(type, edit, truth)]: truth = the command (or pair) the plant changed, as in the exact plan."""
    cmds = plan['cmds']
    ok = [i for i, c in enumerate(cmds) if c['kind'] == 'play' and 300 <= c['run'] <= end - 500]
    opp = [i for i in ok if cmds[i]['side'] != me]
    pick = {
        'drop_zap': [i for i in opp if short_spell(tab, cmds[i]['card'], cmds[i]['side'], cmds[i]['x'], cmds[i]['y'])],
        'drop_spell': [i for i in opp if tab.is_spell(cmds[i]['card'])
                       and not short_spell(tab, cmds[i]['card'], cmds[i]['side'], cmds[i]['x'], cmds[i]['y'])],
        'drop_troop': [i for i in opp if not tab.is_spell(cmds[i]['card'])],
        'shift': [i for i in ok if cmds[i]['_src']['hi'] > cmds[i]['_src']['lo']],
        'swap': [i for i in ok if i + 1 < len(cmds) and cmds[i + 1]['kind'] == 'play' and cmds[i + 1]['run'] == cmds[i]['run']],
        'point_opp': [i for i in opp if not tab.is_spell(cmds[i]['card'])],
        'point_own': [i for i in ok if cmds[i]['side'] == me and not tab.is_spell(cmds[i]['card'])],
    }
    out = []
    for typ in TYPES:
        cand = pick[typ][:]
        r = rng(match, typ)
        r.shuffle(cand)
        for i in cand:
            c = cmds[i]
            if typ.startswith('drop'):
                e = {'op': 'drop', 'i': i}
            elif typ == 'shift':
                R = r.choice([t for t in range(c['_src']['lo'], c['_src']['hi'] + 1) if t != c['run']])
                e = {'op': 'shift', 'i': i, 'run': R}
            elif typ == 'swap':
                e = {'op': 'swap', 'i': i, 'j': i + 1}
            else:
                dx = 500 if typ == 'point_opp' else 700
                x = c['x'] + dx if 0 <= c['x'] + dx <= 18000 else c['x'] - dx
                if typ == 'point_opp' and not recon.zone_ok(tab, c['card'], c['side'], x, c['y']):
                    continue
                e = {'op': 'point', 'i': i, 'x': x, 'y': c['y']}
            p = recon.apply_edit(plan, e)
            if p is None:
                continue
            truth = [dict(cmds[i])] + ([dict(cmds[i + 1])] if typ == 'swap' else [])
            out.append((typ, e, p, truth))
            break
    return out


def same(a, b, keys=('side', 'kind', 'card', 'run', 'x', 'y')):
    return all(a.get(k) == b.get(k) for k in keys)


def judge(typ, truth, final, exact, edits):
    """restored / alt_fix / not_fixed / invisible, and (for a drop) the re-added command's run / point error."""
    if exact and not edits:
        return 'invisible', None
    cs = final['cmds']
    t = truth[0]
    err = None
    if typ.startswith('drop'):
        adds = [c for c in cs if c['_src'].get('source') == 'recon_add' and c['kind'] == 'play' and c['side'] == t['side']
                and c['card'] == t['card']]
        if adds:
            c = min(adds, key=lambda c: abs(c['run'] - t['run']))
            err = (c['run'] - t['run'], round(math.hypot(c['x'] - t['x'], c['y'] - t['y'])))
        back = err is not None and abs(err[0]) <= 2 and err[1] <= 300
    elif typ == 'swap':
        k = [n for n, c in enumerate(cs) if same(c, t)]
        k2 = [n for n, c in enumerate(cs) if same(c, truth[1])]
        back = bool(k and k2 and k[0] < k2[0])
    else:
        back = any(same(c, t) for c in cs)
    if back:
        return ('restored' if exact else 'restored_inexact'), err
    return ('alt_fix' if exact else 'not_fixed'), err


def inverse_rank(typ, truth, log):
    """(round index, d, position in that round's ranked list) of the first round whose list holds the inverse edit."""
    t = truth[0]
    if typ.startswith('drop'):
        pre = 'add s%d %s R' % (t['side'], t['card'])

        def hit(s):
            if not s.startswith(pre):
                return False
            R = int(s[len(pre):].split(' ')[0])
            x, y = map(int, s.split('(')[1].split(')')[0].split(','))
            return abs(R - t['run']) <= 2 and math.hypot(x - t['x'], y - t['y']) <= 300
    elif typ == 'shift':
        want = 'shift s%d %s {"run": %d}' % (t['side'], t['card'], t['run'])
        hit = want.__eq__
    elif typ == 'swap':
        hit = lambda s: s.startswith('swap') and t['card'] in s and truth[1]['card'] in s and s.endswith('@%d' % t['run'])
    else:
        want = 'point s%d %s {"x": %d, "y": %d}' % (t['side'], t['card'], t['x'], t['y'])
        hit = want.__eq__
    rounds = [x for x in log if 'round' in x]
    for n, x in enumerate(rounds):
        for k, s in enumerate(x.get('top') or ()):
            if hit(s):
                return n, x['d'], k + 1
    return None


def job(args):
    rec, frames_path, out, typ, e, planted, truth = args
    res = recon_search.do_match((rec, frames_path, os.path.join(out, typ), 4, None, planted))
    if 'error' in res:
        return dict(match=rec['match'], type=typ, error=res['error'])
    final = json.load(open(os.path.join(out, typ, rec['match'], 'recon_plan.json')))
    exact = res['counts'].get('exact', 0) == res['frames']
    verdict, err = judge(typ, truth, final, exact, res['edits'])
    return dict(match=rec['match'], type=typ, plant=e, truth=[{k: v for k, v in c.items() if k != '_src'} for c in truth],
                counts=res['counts'], frames=res['frames'], first_div=res['first_div'], edits=res['edits'],
                verdict=verdict, add_err=err, inverse_rank=inverse_rank(typ, truth, res['log']),
                plants_missed=(res.get('plants') or {}).get('missed'))


def summary(out):
    rows = [json.loads(l) for l in open(os.path.join(out, 'plant_results.jsonl'))]
    print('type        n  invisible restored restored_inexact alt_fix not_fixed error | inverse rank1 / in top4 / listed (visible plants)')
    for typ in TYPES:
        rs = [r for r in rows if r['type'] == typ]
        if not rs:
            continue
        v = lambda k: sum(r.get('verdict') == k for r in rs)
        vis = [r for r in rs if r.get('verdict') not in ('invisible', None)]
        rk = [r['inverse_rank'] for r in vis if r.get('inverse_rank')]
        print('%-10s %2d  %9d %8d %16d %7d %9d %5d | %d / %d / %d of %d' % (
            typ, len(rs), v('invisible'), v('restored'), v('restored_inexact'), v('alt_fix'), v('not_fixed'), sum('error' in r for r in rs),
            sum(x[2] == 1 for x in rk), sum(x[2] <= 4 for x in rk), len(rk), len(vis)))
    for r in rows:
        print(r['match'][-6:], r['type'], r.get('verdict') or r.get('error'), 'first', r.get('first_div'), 'rank', r.get('inverse_rank'),
              'add_err', r.get('add_err'), '| plant', recon_plant_str(r), '| edits', [x for x in r.get('edits') or [] if not x.startswith('shift')]
              if r['type'] != 'shift' else r.get('edits'))


def recon_plant_str(r):
    t = (r.get('truth') or [{}])[0]
    return '%s %s s%s run %s (%s,%s) -> %s' % (r['type'], t.get('card'), t.get('side'), t.get('run'), t.get('x'), t.get('y'),
                                             {k: v for k, v in (r.get('plant') or {}).items() if k != 'op'})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs'); ap.add_argument('--frames'); ap.add_argument('--plans'); ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=4); ap.add_argument('--only'); ap.add_argument('--summary', action='store_true')
    a = ap.parse_args()
    if a.summary:
        return summary(a.out)
    tab = recon.Tab()
    recs = {json.loads(l)['match']: json.loads(l) for l in open(a.inputs)}
    jobs = []
    for run in a.plans.split(','):
        for line in open(os.path.join(run, 'recon_results.jsonl')):
            r = json.loads(line)
            m = r['match']
            if 'error' in r or r['counts'].get('exact', 0) != r['frames'] or m not in recs or (a.only and m[-6:] not in a.only):
                continue
            plan = json.load(open(os.path.join(run, m, 'recon_plan.json')))
            fp = os.path.join(a.frames, m + '.jsonl')
            end = max(recon_search.sme_live.load_frames(fp))
            for typ, e, p, truth in plants(plan, recs[m]['my_side'], end, tab, m):
                p['_cycle_base'] = [recon.cycle_ok(p, s) for s in (0, 1)]   # as the extractor would hand it over
                jobs.append((recs[m], fp, a.out, typ, e, p, truth))
    os.makedirs(a.out, exist_ok=True)
    print('jobs', len(jobs), flush=True)
    with open(os.path.join(a.out, 'plant_results.jsonl'), 'a') as w, ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(job, jobs):
            w.write(json.dumps(res, default=str) + '\n'); w.flush()
            print(res['match'][-6:], res['type'], res.get('verdict') or res.get('error'), res.get('inverse_rank'), flush=True)


if __name__ == '__main__':
    main()
