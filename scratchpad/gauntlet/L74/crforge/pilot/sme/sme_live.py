"""SME on live-log matches (ticket A2b-3b): no replay recording; A2b-1's extracted inputs + the live reader's frames.

On pod 33920 (next to sme.py / SmeRun):
  python3 sme_live.py all   --inputs INPUTS.jsonl --frames FRAMEDIR --out OUT [--workers 20] [--only M1,M2]
  python3 sme_live.py one   --inputs INPUTS.jsonl --frames FRAMEDIR --out OUT --only MATCH
  python3 sme_live.py check --plan PLAN.json --frames FRAMEDIR/MATCH.jsonl --side 1 --out OUT   # score a given plan

Per match:
1. Plan: decks, levels, slot flags, towers, words from the input record. Seed 1 (the match is RNG-free: no draw after
   the deal); both deals forced: ours from the log, the opponent's = A2b-1's `opp_deal_fit`.
   Commands at the extractor's `tick` and point; given = run - 20; an ability names the side's latest play of its card.
2. Repair loop (inputs only): at the first true divergence d, try each command run in [d-120, d] at the other run ticks
   of its extracted window [lo, hi], and (not our own taps) the 8 points 500 units around its point. Keep the variant
   that moves d latest; stop when none does (max 25 rounds).
3. Score: every live frame. exact / torn_t1 (the whole frame equals sim t+1) / torn_mixed (isolated, every object held
   by sim t or t+1) / div. First true divergence = first div frame.
4. Over-fit guard: run ticks outside [lo, hi] (lo-2..hi+2) for the commands before the final d; reported, never kept.
5. Deal check: up to 3 more fitting opponent deal classes (other hand sets / queue orders); traces compared.
"""
import argparse, collections, itertools, json, os, re, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sme  # noqa: E402
from sme import canon_sim, diff, run_batch, card_name  # noqa: E402

WIN = 120
MAX_ROUNDS = 40


def load_frames(path):
    return {f['t']: f for f in map(json.loads, open(path))}


def canon_live(f, my_side):
    c = {'T': [], 'U': [], 'P': [], 'A': []}
    for side, x, y, card, hp, kind in f['E']:
        c['T' if card == -1 else 'U'].append((side, x, y, hp))
    for side, x, y, card in f['P']:
        c['P'].append((side, x, y))
    for side, x, y, card in f['A']:
        c['A'].append((side, x, y))
    c['S%d' % my_side] = (f['el'], tuple(f['hand']) if f['hand'] else None, None)
    return c


# Optional reader-representation map (env SME_REPR = a JSON file): {"drop": [crforge names the reader never lists],
# "as": {crforge name: the reader's class T/U/P/A}}. Built from the episode census, documented in SME.md.
REPR = json.load(open(os.environ['SME_REPR'])) if os.environ.get('SME_REPR') else {'drop': [], 'as': {}}


def sim_canon(o, my_side):
    if REPR['drop'] or REPR['as'] or REPR.get('drop_no_hp'):
        es = []
        for e in o['E']:
            if e[2] in REPR['drop'] or (REPR.get('drop_no_hp') and e[1] == 'C' and e[6] == -1 and e[2] not in REPR['as']):
                continue
            k = REPR['as'].get(e[2])
            if k:
                e = list(e)
                e[1] = {'U': 'C'}.get(k, k)
            es.append(e)
        o = dict(o, E=es)
    c = canon_sim(o)
    c.pop('S%d' % (1 - my_side))
    return c


# ---------------------------------------------------------------- plan
def plan_from(rec, opp_deal):
    me = rec['my_side']
    sides = rec['sides']
    cmds, last = [], {}
    for p in sorted(rec['plays'], key=lambda p: p['tick']):
        s, d = p['side'], p['deck_index']
        if p['kind'] == 'play':
            last[(s, d)] = len(cmds)
            cmds.append({"kind": "play", "given": p['tick'] - 20, "run": p['tick'], "side": s, "card": p['card'],
                         "level": sides[str(s)]['levels'][d], "x": p['x'], "y": p['y']})
        elif (s, d) in last:
            cmds.append({"kind": "ability", "given": p['tick'] - 20, "run": p['tick'], "side": s,
                         "unit": "cmd%d_0" % last[(s, d)]})
        else:
            continue
        cmds[-1]['_src'] = {'lo': p['run_ticks'][0], 'hi': p['run_ticks'][1], 'tick': p['tick'],
                            'source': p.get('source'), 'own': s == me}
    deals = [None, None]
    own = list(rec['deal'][str(me)])
    if own.count(-1) == 1:  # one queue card never seen: it is the one index missing
        own[own.index(-1)] = (set(range(8)) - set(own)).pop()
    deals[me] = own if sorted(own) == list(range(8)) else None
    deals[1 - me] = opp_deal
    return {"seed": 1, "playerData": [1, 1], "words": [sides['0']['word'], sides['1']['word']],
            "decks": [sides['0']['deck'], sides['1']['deck']], "slots": [sides['0']['slot_flags'], sides['1']['slot_flags']],
            "towers": [[sides[k]['towers']['king_level'], sides[k]['towers']['level'], sides[k]['towers']['group']]
                       for k in ('0', '1')],
            "deals": deals, "cmds": cmds}


def runnable(plan):
    return dict(plan, cmds=[{k: v for k, v in c.items() if k != '_src'} for c in plan['cmds']])


def fitting_classes(rec, limit=None):
    """Opponent deals that keep every extracted opponent play legal under the 4-card cycle, one per class
    (initial hand set x queue order; the order inside the hand changes no legality)."""
    opp = 1 - rec['my_side']
    seq = [p['deck_index'] for p in sorted(rec['plays'], key=lambda p: p['tick']) if p['side'] == opp and p['kind'] == 'play']
    out = []
    for hand in itertools.combinations(range(8), 4):
        rest = [i for i in range(8) if i not in hand]
        for q in itertools.permutations(rest):
            h, qu, ok = set(hand), list(q), True
            for d in seq:
                if d not in h:
                    ok = False
                    break
                h.remove(d); qu.append(d); h.add(qu.pop(0))
            if ok:
                out.append(list(hand) + list(q))
                if limit and len(out) >= limit:
                    return out
    return out


# ---------------------------------------------------------------- analysis
def analyse(obs, frames, me, lo=0, hi=10 ** 9):
    by = {o['t']: o for o in obs}
    ts = [t for t in sorted(frames) if lo <= t <= hi and t in by]
    cls, ds = {}, {}
    for t in ts:
        r = canon_live(frames[t], me)
        d = diff(r, sim_canon(by[t], me))
        ds[t] = d
        if not d:
            cls[t] = 'exact'
        elif t + 1 in by and not diff(r, sim_canon(by[t + 1], me)):
            cls[t] = 'torn_t1'
        else:
            cls[t] = 'div'
    for i, t in enumerate(ts):  # isolated frames whose every object is held by sim t or t+1
        if cls[t] != 'div' or t + 1 not in by:
            continue
        nb = [cls.get(ts[j]) for j in (i - 1, i + 1) if 0 <= j < len(ts)]
        if any(c == 'div' for c in nb):
            continue
        r, a, b = canon_live(frames[t], me), sim_canon(by[t], me), sim_canon(by[t + 1], me)
        if all(x in a[k] or x in b[k] for k in 'TUPA' for x in r[k]) and \
                all(r[k] in (a.get(k), b.get(k)) or r[k][0] in (a.get(k, (None,))[0], b.get(k, (None,))[0])
                    for k in r if k.startswith('S')):
            cls[t] = 'torn_mixed'
    first = next((t for t in ts if cls[t] == 'div'), None)
    cnt = collections.Counter(cls.values())
    return {'frames': len(ts), 'counts': dict(cnt), 'first': first, 'first_diff': ds.get(first), 'cls': cls,
            'missing_in_sim': sum(1 for t in frames if lo <= t <= hi and t not in by)}


def variants_at(plan, d, rec_frames_end):
    vs = []
    for i, c in enumerate(plan['cmds']):
        s = c['_src']
        if not (d - WIN <= c['run'] <= d):
            continue
        for R in range(s['lo'], s['hi'] + 1):
            if R != c['run']:
                vs.append((i, {'run': R, 'given': R - 20}))
        if c['kind'] == 'play' and not s['own']:
            for dx, dy in itertools.product((-500, 0, 500), repeat=2):
                if dx or dy:
                    vs.append((i, {'x': c['x'] + dx, 'y': c['y'] + dy}))
    return vs


def apply(plan, i, ch):
    p = json.loads(json.dumps(plan))
    p['cmds'][i].update(ch)
    return p


def episodes(an):
    """Runs of consecutive div frames: [start, end, healed] (healed = a non-div frame follows)."""
    ts = sorted(an['cls'])
    out, cur = [], None
    for t in ts:
        if an['cls'][t] == 'div':
            if cur is None:
                cur = [t, t, False]
            cur[1] = t
        elif cur is not None:
            cur[2] = True
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out


def objective(an, hi, skip):
    """(first div frame outside the given-up episodes, - div frames outside them): larger is better."""
    div = [t for t, c in an['cls'].items() if c == 'div' and not any(a <= t <= b for a, b in skip)]
    return (min(div) if div else hi + 1, -len(div))


def base_run(plan, frames, me, end, work, log):
    """Full run; an ability naming a unit its play never made (the play was refused) is dropped and logged."""
    for _ in range(10):
        o = run_batch([(runnable(plan), end + 3, 0)], work)[0]
        if o is not None:
            return o, analyse(o, frames, me)
        msg = sme.ERRORS.get(0, '')
        mm = re.search(r'(cmd\d+) names cmd\d+_\d+, which no play', msg)
        if not mm:
            log.append({'error': msg[:300]})
            return None, None
        i = int(mm.group(1)[3:])
        plan['cmds'][i]['kind'] = 'skip'
        log.append({'dropped_ability': i, 'why': msg[:200]})
    return None, None


def fit_match(rec, frames, out):
    me = rec['my_side']
    end = max(frames)
    deal = rec['opp_deal_fit']
    if deal is None:  # no fitting deal (an opponent play missed or invented): the first deal, refused plays expected
        deal = list(range(8))
    plan = plan_from(rec, deal)
    work = os.path.join(out, 'work')
    log = []
    o, an = base_run(plan, frames, me, end, work, log)
    if o is None:
        return {'error': (log[-1].get('error') if log else '') or 'base plan failed', 'log': log}, plan, None
    given_up = []  # onsets of episodes that no input change in reach fixes
    for rnd in range(MAX_ROUNDS):
        eps = [e for e in episodes(an) if e[0] not in given_up]
        if not eps:
            break
        d = eps[0][0]
        skip = [(e[0], e[1]) for e in episodes(an) if e[0] in given_up]
        vs = variants_at(plan, d, end)
        lo, hi = max(0, d - WIN - 5), min(end, d + 400)
        best = None
        if vs:
            outs = run_batch([(runnable(apply(plan, i, ch)), hi + 3, lo) for i, ch in vs], work)
            for (i, ch), ob in zip(vs, outs):
                if ob is None:
                    continue
                key = objective(analyse(ob, frames, me, lo, hi), hi, skip)
                if best is None or key > best[0]:
                    best = (key, i, ch)
        if best is None or best[0][0] <= d:
            given_up.append(d)
            log.append({'round': rnd, 'd': d, 'variants': len(vs), 'best_first': best and best[0][0], 'kept': False})
            continue
        plan = apply(plan, best[1], best[2])
        o, an = base_run(plan, frames, me, end, work, log)
        if o is None:
            return {'error': 'a kept variant failed', 'log': log}, plan, None
        log.append({'round': rnd, 'd': d, 'variants': len(vs), 'cmd': best[1], 'change': best[2], 'new_first': an['first']})
    return {'log': log, 'given_up': given_up}, plan, (o, an)


def overfit_probe(plan, frames, me, d, end, out):
    """Run ticks outside each command's window, for the commands in [d-WIN, d]: does any move d later?"""
    if d is None:
        return []
    vs = []
    for i, c in enumerate(plan['cmds']):
        s = c['_src']
        if d - WIN <= c['run'] <= d:
            for R in list(range(s['lo'] - 2, s['lo'])) + list(range(s['hi'] + 1, s['hi'] + 3)):
                vs.append((i, {'run': R, 'given': R - 20}))
    if not vs:
        return []
    lo, hi = max(0, d - WIN - 5), min(end, d + 400)
    outs = run_batch([(runnable(apply(plan, i, ch)), hi + 3, lo) for i, ch in vs], os.path.join(out, 'work'))
    res = []
    for (i, ch), ob in zip(vs, outs):
        if ob is None:
            continue
        f2 = analyse(ob, frames, me, lo, hi)['first']
        if f2 is None or f2 > d:
            c = plan['cmds'][i]
            res.append({'cmd': i, 'card': c.get('card', 'ability'), 'side': c['side'], 'window': [c['_src']['lo'], c['_src']['hi']],
                        'run': ch['run'], 'first_div': f2})
    return res


def describe_first(o_by, frames, me, t):
    """The first true divergence with card names: recorded-only and sim-only objects."""
    if t is None:
        return None
    f, s = frames[t], o_by[t]
    r = canon_live(f, me)
    d = diff(r, sim_canon(s, me))
    names_r = {(e[0], e[1], e[2], e[4]): card_name(e[3]) or 'tower' if e[3] != -1 else 'tower' for e in f['E']}
    names_r.update({(p[0], p[1], p[2]): 'P:' + str(card_name(p[3]) if p[3] != -1 else 'tower_shot') for p in f['P']})
    names_r.update({(a[0], a[1], a[2]): 'A:' + str(card_name(a[3])) for a in f['A']})
    names_s = {}
    for e in s['E']:
        key = (e[3], e[4], e[5], e[6]) if e[1] in 'TC' else (e[3], e[4], e[5])
        names_s[key] = e[1] + ':' + e[2]
    out = []
    for kind, x, near in d:
        nm = names_r.get(x) if 'rec_only' in kind else names_s.get(x) if 'sim_only' in kind else None
        out.append([kind, list(x) if isinstance(x, tuple) else x, nm, list(near) if isinstance(near, tuple) else near])
    return out


def do_match(args):
    rec, frames_path, out = args
    m = rec['match']
    mo = os.path.join(out, m)
    os.makedirs(mo, exist_ok=True)
    try:
        frames = load_frames(frames_path)
        me, end = rec['my_side'], max(frames)
        info, plan, final = fit_match(rec, frames, mo)
        if final is None:
            res = {'match': m, **info}
        else:
            o, an = final
            by = {x['t']: x for x in o}
            plays = [p for x in o for p in x['plays']]
            moved = [(c.get('card', 'ability'), c['run'] - c['_src']['tick']) for c in plan['cmds'] if c['run'] != c['_src']['tick']]
            res = {'match': m, 'flags': rec['flags'], 'opp_fitting_deals': rec['opp_fitting_deals'],
                   'frames': an['frames'], 'counts': an['counts'], 'missing_in_sim': an['missing_in_sim'],
                   'exact_share': an['counts'].get('exact', 0) / max(an['frames'], 1),
                   'first_div': an['first'], 'first_detail': describe_first(by, frames, me, an['first']),
                   'sim_end': o[-1]['t'], 'live_end': end, 'commands': len(plan['cmds']),
                   'refused_plays': [p for p in plays if p[4] != 0 or not p[2]],
                   'nonzero_offset': moved, 'points_moved': sum(1 for c in plan['cmds'] if c['kind'] == 'play' and
                                                               (c['x'], c['y']) != tuple(_orig_xy(rec, c))),
                   'repair': info['log'],
                   'torn_ticks': sorted(t for t, c in an['cls'].items() if c.startswith('torn')),
                   'torn_t1_ticks': sorted(t for t, c in an['cls'].items() if c == 'torn_t1')}
            eps = episodes(an)
            res['episodes'] = [{'start': a, 'end': b, 'healed': h, 'frames': sum(1 for t in an['cls'] if a <= t <= b),
                                'detail': describe_first(by, frames, me, a) if k < 12 else None}
                               for k, (a, b, h) in enumerate(eps)]
            res['overfit'] = [x for a, _, _ in eps[:5] for x in overfit_probe(plan, frames, me, a, end, mo)]
            res['given_up'] = info.get('given_up')
            # deal check: other fitting classes must give the same trace on every frame tick
            if rec['opp_deal_fit'] is not None:
                alts = [d for d in fitting_classes(rec, 400) if d != rec['opp_deal_fit']]
                pick = [alts[i] for i in sorted({0, len(alts) // 2, len(alts) - 1}) if alts] if alts else []
                jobs = [(runnable(dict(plan, deals=[d if k != me else plan['deals'][k] for k in (0, 1)])), end + 3, 0)
                        for d in pick]
                outs = run_batch(jobs, os.path.join(mo, 'work')) if jobs else []
                base = [json.dumps([x['E'], x['S'][me]]) for x in o]
                res['deal_check'] = {'classes_tested': len(pick), 'identical': [ob is not None and
                                     [json.dumps([x['E'], x['S'][me]]) for x in ob] == base for ob in outs]}
        json.dump(plan, open(os.path.join(mo, 'plan.json'), 'w'), indent=0)
    except Exception as e:  # one bad match must not stop the batch
        import traceback
        res = {'match': m, 'error': repr(e), 'trace': traceback.format_exc()[-1500:]}
    json.dump(res, open(os.path.join(mo, 'result.json'), 'w'), indent=1, default=str)
    return res


def _orig_xy(rec, c):
    for p in rec['plays']:
        if p['kind'] == 'play' and p['side'] == c['side'] and p['tick'] == c['_src']['tick'] and p['card'] == c.get('card'):
            return p['x'], p['y']
    return c['x'], c['y']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['all', 'one', 'check'])
    ap.add_argument('--inputs'); ap.add_argument('--frames'); ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=20); ap.add_argument('--only')
    ap.add_argument('--plan'); ap.add_argument('--side', type=int)
    a = ap.parse_args()
    if a.mode == 'check':
        frames = load_frames(a.frames)
        plan = json.load(open(a.plan))
        o = run_batch([(runnable(plan), max(frames) + 3, 0)], os.path.join(a.out, 'work'))[0]
        an = analyse(o, frames, a.side)
        by = {x['t']: x for x in o}
        print(json.dumps({k: an[k] for k in ('frames', 'counts', 'first', 'missing_in_sim')}))
        print('first', json.dumps(describe_first(by, frames, a.side, an['first']))[:2500])
        print('torn', sorted(t for t, c in an['cls'].items() if c.startswith('torn')))
        return
    recs = [json.loads(l) for l in open(a.inputs)]
    if a.only:
        keep = set(a.only.split(','))
        recs = [r for r in recs if r['match'] in keep]
    jobs = [(r, os.path.join(a.frames, r['match'] + '.jsonl'), a.out) for r in recs]
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, 'results.jsonl'), 'a') as w, ProcessPoolExecutor(a.workers if a.mode == 'all' else 1) as ex:
        for res in ex.map(do_match, jobs):
            w.write(json.dumps(res, default=str) + '\n'); w.flush()
            print(res['match'], res.get('error') or (res.get('counts'), res.get('first_div')), flush=True)


if __name__ == '__main__':
    main()
