"""SME (seeded match exactness) on crforge for one replay-recorded match (plan1026 Pillar 1, ticket A2b-3).

Runs on pod 33920 (python3 + the SmeRun.java batch driver):
  python3 sme.py fit   --rec REC.jsonl --p3 P3.jsonl --seed S --out DIR      # recover plays (tick + point), sequentially
  python3 sme.py polish --rec REC.jsonl --p3 P3.jsonl --plan DIR/plan.json --out DIR2   # run-tick polish
  python3 sme.py score --rec REC.jsonl --plan DIR/plan.json --out DIR [--perturb]   # full run + frame-by-frame census
  python3 sme.py selftest

Units (verified on tick 0, SME.md): reader x/y = crforge x/y (game units, 1 tile = 1000, side 0 = bottom, king
y=3000); reader elixir_raw = crforge MatchSide.elixir (1/10000); hand_deck_indices = Hand.slots(); cycle_deck_indices
= Hand.queue(). Reader frame game_tick g = crforge observation line t = g (the state before step g runs); a play with
run tick R is first visible at line R + 1.
"""
import argparse, collections, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = '/workspace/crforge/env/build/install/env/lib'
TABLES = '/workspace/crforge_cache/tables/16.402.22'
SHIFTS = (1, -1, 2, -2)
TIE_WINDOW = 120
THREADS = int(os.environ.get('SME_THREADS', '24'))

# Inputs fixed by the battle log (crapi own_battlelog 20261026T170813Z) and the recording's tick-0 frame.
DECKS = [["GoblinBarrel", "Valkyrie", "SkeletonArmy", "Wallbreakers", "Princess", "BlowdartGoblin", "IceSpirits", "Cannon"],
         ["Knight", "IceWizard", "Tesla", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"]]
SLOTS = [[1, 2, 1, 0, 0, 0, 0, 0], [1, 2, 1, 0, 0, 0, 0, 0]]
LEVELS = [[16, 16, 16, 16, 16, 16, 15, 16], [16] * 8]  # API: opponent Ice Spirit 15/16, every other card at max
WORDS = [29372692, 83616782]                           # seeds/jobs/rec1026_std.txt (side 0 = opponent #Y2PR8YLG9)
HERO = {0: 1, 1: 1}                                    # deck index of each side's hero card (slot flag 2)


def base_plan(seed):
    return {"seed": seed, "playerData": [1, 1], "words": WORDS, "decks": DECKS, "slots": SLOTS,
            "towers": [[16, 16], [16, 16]], "cmds": []}


# ---------------------------------------------------------------- canonical frames
def canon_rec(f, players=True):
    c = {'T': [], 'U': [], 'P': [], 'A': []}
    for e in f['entities']:
        if e['card_id'] == -1:
            c['T'].append((e['side'], e['x'], e['y'], e['hp']))
        else:
            c['U'].append((e['side'], e['x'], e['y'], e['hp']))
    for p in f['projectiles']:
        c['P'].append((p['side'], p['x'], p['y']))
    for a in f['effects']:
        c['A'].append((a['side'], a['x'], a['y']))
    if players and f.get('players'):
        for p in f['players']:
            c['S%d' % p['side']] = (p['elixir_raw'], tuple(p['hand_deck_indices']), tuple(p['cycle_deck_indices']))
    return c


def canon_sim(o, players=True):
    c = {'T': [], 'U': [], 'P': [], 'A': []}
    for e in o['E']:
        _, cls, name, side, x, y, hp = e[:7]
        if cls == 'T':
            c['T'].append((side, x, y, hp))
        elif cls == 'C':
            c['U'].append((side, x, y, hp))
        elif cls == 'P':
            c['P'].append((side, x, y))
        elif cls == 'A':
            c['A'].append((side, x, y))
        else:
            c.setdefault('?', []).append(tuple(e))
    if players:
        for s, (el, hand, q) in enumerate(o['S']):
            c['S%d' % s] = (el, tuple(hand), tuple(q))
    return c


def diff(r, s):
    """List of (type, detail) between a recorded and a simulated canonical frame; [] = exact."""
    out = []
    for k in ('T', 'U', 'P', 'A'):
        a, b = collections.Counter(r[k]), collections.Counter(s[k])
        ra, sb = sorted((a - b).elements()), sorted((b - a).elements())
        for x in ra:
            out.append((k + '_rec_only', x, nearest(x, sb)))
        for x in sb:
            out.append((k + '_sim_only', x, nearest(x, ra)))
    for k in ('S0', 'S1'):
        if k in r and r[k] != s.get(k):
            rr, ss = r[k], s.get(k)
            if rr[0] != ss[0]:
                out.append((k + '_elixir', rr[0], ss[0]))
            if rr[1:] != ss[1:]:
                out.append((k + '_hand', rr[1:], ss[1:]))
    out += [('sim_unknown_class', x, None) for x in s.get('?', [])]
    return out


def nearest(x, pool):
    """The same-side object in pool closest in position, with (dx, dy, dhp) to it, or None."""
    best = None
    for y in pool:
        if y[0] != x[0]:
            continue
        d = abs(y[1] - x[1]) + abs(y[2] - x[2])
        if best is None or d < best[0]:
            best = (d, y)
    if best is None:
        return None
    y = best[1]
    return (y[1] - x[1], y[2] - x[2]) + ((y[3] - x[3],) if len(x) > 3 else ())


# ---------------------------------------------------------------- recording
def load_frames(path, key=None):
    fr = {}
    for line in open(path):
        d = json.loads(line)
        if key and d.get('event') != 'frame':
            continue
        f = d['f'] if key else d
        if f.get('game_tick', -1) < 0 or not f.get('battle_active', True):
            continue
        fr.setdefault(f['game_tick'], f)  # 44 duplicated ticks: keep the first sample
    return fr


def extract_events(rec):
    """Plays (hand slot lost) and ability uses (elixir drop, hand unchanged), per side, with the recorded window."""
    ticks = sorted(rec)
    ev = []
    for i in range(1, len(ticks)):
        t0, t1 = ticks[i - 1], ticks[i]
        f0, f1 = rec[t0], rec[t1]
        old = {a['address'] for a in f0['entities']} | {p['address'] for p in f0['projectiles']} | \
              {a['address'] for a in f0['effects']}
        for p0, p1 in zip(f0['players'], f1['players']):
            s = p1['side']
            # a slot reads -1 while its next card is on its way: that is not a play
            lost = [d for d in p0['hand_deck_indices'] if d >= 0 and d not in p1['hand_deck_indices']]
            for d in lost:
                ev.append({'kind': 'play', 'side': s, 'deck': d, 't_prev': t0, 't': t1,
                           'anchor': anchor(f1, old, s, p1['deck_card_ids'][d])})
            if not lost and p1['elixir_raw'] < p0['elixir_raw']:
                ev.append({'kind': 'ability', 'side': s, 't_prev': t0, 't': t1, 'anchor': None})
    return ev


_NAMES = None


def card_name(cid):
    """Card id -> base row name (evolved table 13 and hero table 203 forms mapped to their card), as gen_jobs.id_names."""
    global _NAMES
    if _NAMES is None:
        import re
        _NAMES = {}
        for f in ('spells_characters', 'spells_buildings', 'spells_other', 'spells_evolved', 'spells_hero_form'):
            j = json.load(open(os.path.join(TABLES, f + '.json')))
            for name, row in j['rows'].items():
                _NAMES[j['id'] * 1000000 + row['index']] = re.sub(r'_(EV1|hero)$', '', name)
    return _NAMES.get(cid)


def same_card(cid, card):
    return cid != -1 and card_name(cid) == card_name(card)


def anchor(f, old, side, card):
    """Requested-point estimate from the play's new objects: spell target, effect centre, or unit centroid."""
    for p in f['projectiles']:
        if p['address'] not in old and p['side'] == side and same_card(p['card_id'], card):
            return (p['target_x'], p['target_y'], 'proj')
    for a in f['effects']:
        if a['address'] not in old and a['side'] == side and same_card(a['card_id'], card):
            return (a['x'], a['y'], 'effect')
    us = [e for e in f['entities'] if e['address'] not in old and e['side'] == side and same_card(e['card_id'], card)]
    if us:
        return (sum(e['x'] for e in us) / len(us), sum(e['y'] for e in us) / len(us), 'units%d' % len(us))
    return None


# ---------------------------------------------------------------- crforge runs
def run_batch(jobs, workdir):
    """jobs: list of (plan dict, ticks, from). Returns list of lists of observation dicts."""
    os.makedirs(workdir, exist_ok=True)
    lines = []
    for i, (plan, ticks, frm) in enumerate(jobs):
        pp = os.path.join(workdir, 'p%d.json' % i)
        json.dump(plan, open(pp, 'w'))
        lines.append('%s %d %s %d' % (pp, ticks, os.path.join(workdir, 'o%d.jsonl' % i), frm))
    jf = os.path.join(workdir, 'jobs.txt')
    open(jf, 'w').write('\n'.join(lines) + '\n')
    r = subprocess.run(['java', '-Xmx16g', '-cp', LIB + '/*:' + os.path.join(HERE, 'build'), 'SmeRun', TABLES, jf,
                        str(THREADS)], capture_output=True, text=True)
    if 'jobs=' not in r.stdout:
        raise SystemExit('SmeRun failed: ' + r.stdout + r.stderr[-3000:])
    bad = {l.split(':')[1].strip() for l in r.stderr.splitlines() if l.startswith('java.lang.RuntimeException')}
    return [None if os.path.join(workdir, 'p%d.json' % i) in bad else
            [json.loads(l) for l in open(os.path.join(workdir, 'o%d.jsonl' % i))] for i in range(len(jobs))]


def window_score(obs, rec, p3, lo, hi):
    n = 0
    by = {o['t']: o for o in obs}
    for t in range(lo, hi + 1):
        if t not in by:
            n += 50 if t in rec else 0  # the sim stopped (match over) where the recording goes on
            continue
        src, pl = (rec, True) if t in rec else (p3, False) if t in p3 else (None, None)
        if src is None:
            continue
        r = canon_rec(src[t], pl)
        m = len(diff(r, canon_sim(by[t], pl)))
        # a frame whose label is off by 1-2 ticks (the reader read across a step) is scored at its best shift, +1
        for k in SHIFTS if m else ():
            if t + k in by:
                m = min(m, 1 + len(diff(r, canon_sim(by[t + k], pl))))
        n += m
    return n


def cmd_for(e, R, pt, unit=None):
    if e['kind'] == 'play':
        s, d = e['side'], e['deck']
        return {"kind": "play", "given": R - 20, "run": R, "side": s, "card": DECKS[s][d], "level": LEVELS[s][d],
                "x": pt[0], "y": pt[1]}
    return {"kind": "ability", "given": R - 20, "run": R, "side": e['side'], "unit": unit}


def fit(a):
    rec = load_frames(a.rec, key='f')
    p3 = load_frames(a.p3) if a.p3 else {}
    evs = extract_events(rec)
    plan = base_plan(a.seed)
    log = []
    hero_cmd = {0: None, 1: None}
    for k, e in enumerate(evs):
        lo, hi = e['t_prev'], e['t'] + 20
        Rs = list(range(e['t_prev'], e['t'] + 1))  # + t itself: the first-seen frame's label may be one tick early
        if e['kind'] == 'play':
            ax, ay = (e['anchor'] or (9000, 16000, 'none'))[:2]
            gx, gy = int(round(ax / 500.0)) * 500, int(round(ay / 500.0)) * 500
            pts = [(int(round(ax)), int(round(ay)))] + [(gx + dx, gy + dy) for r in (1, 2)
                    for dx in range(-500 * r, 500 * r + 1, 500) for dy in range(-500 * r, 500 * r + 1, 500)
                    if max(abs(dx), abs(dy)) == 500 * r or (r == 1 and dx == dy == 0)]
            cands = [(R, p, None) for R in Rs for p in pts[:10]]
        else:
            hc = hero_cmd[e['side']]
            cands = [(R, None, '%s_%d' % (hc, u)) for R in Rs for u in (0, 1)] if hc else []
        best = None
        for stage in (0, 1):
            cs = cands if stage == 0 or e['kind'] != 'play' else [(R, p, None) for R in Rs for p in pts[10:]]
            if not cs:
                continue
            jobs = [(dict(plan, cmds=plan['cmds'] + [cmd_for(e, R, p, u)]), hi + 3, lo - 2) for R, p, u in cs]
            try:
                outs = run_batch(jobs, os.path.join(a.out, 'work'))
            except SystemExit as ex:
                log.append({'event': k, 'error': str(ex)[:500]})
                outs = None
            if outs is None:
                break
            scores = [10 ** 9 if o is None else window_score(o, rec, p3, lo, hi) for o in outs]
            m = min(scores)
            ties = [c for c, sc in zip(cs, scores) if sc == m]
            long_m = None
            if len(ties) > 1:
                # tie-break on a longer window (the next plays are missing from these runs, equally for every tie)
                hi2 = e['t'] + TIE_WINDOW
                outs2 = run_batch([(dict(plan, cmds=plan['cmds'] + [cmd_for(e, R, p, u)]), hi2 + 3, lo - 2)
                                   for R, p, u in ties], os.path.join(a.out, 'work'))
                s2 = [10 ** 9 if o is None else window_score(o, rec, p3, lo, hi2) for o in outs2]
                long_m = min(s2)
                ties = [c for c, sc in zip(ties, s2) if sc == long_m]
            if best is None or m < best[0]:
                best = (m, ties[0], len(ties), len(cs), long_m)
            if m == 0:
                break
        if best is None:
            log.append({'event': k, 'e': e, 'skipped': 'no candidate ran'})
            continue
        m, (R, p, u), nt, nc, lm = best
        idx = len(plan['cmds'])
        plan['cmds'].append(cmd_for(e, R, p, u))
        if e['kind'] == 'play' and e['deck'] == HERO[e['side']]:
            hero_cmd[e['side']] = 'cmd%d' % idx
        log.append({'event': k, 'kind': e['kind'], 'side': e['side'], 'card': DECKS[e['side']][e['deck']] if e['kind'] == 'play' else 'ability',
                    't_prev': e['t_prev'], 't': e['t'], 'anchor': e['anchor'], 'R': R, 'pt': p, 'unit': u,
                    'window_mismatch': m, 'ties': nt, 'cands': nc, 'long_mismatch': lm})
        print(json.dumps(log[-1]), flush=True)
    os.makedirs(a.out, exist_ok=True)
    json.dump(plan, open(os.path.join(a.out, 'plan.json'), 'w'), indent=1)
    with open(os.path.join(a.out, 'fit_log.jsonl'), 'w') as w:
        for x in log:
            w.write(json.dumps(x) + '\n')


def polish(a):
    """Greedy: move one command's run tick by 1 inside its observed interval [t_prev, t] when that lowers the
    full-match mismatch; repeat until no move helps. Points are not touched."""
    rec = load_frames(a.rec, key='f')
    p3 = load_frames(a.p3) if a.p3 else {}
    plan = json.load(open(a.plan))
    fl = [json.loads(l) for l in open(os.path.join(os.path.dirname(a.plan), 'fit_log.jsonl'))]
    iv = [(x['t_prev'], x['t']) for x in fl if 'R' in x]  # one per command, in command order
    assert len(iv) == len(plan['cmds'])
    end = max(rec)

    def total(p):
        o = run_batch([(p, end + 3, 0)], os.path.join(a.out, 'polish'))[0]
        return 10 ** 9 if o is None else window_score(o, rec, p3, 0, end)
    cur = total(plan)
    moves = []
    while True:
        vs = []
        for i, c in enumerate(plan['cmds']):
            for d in (-1, 1):
                R = c['run'] + d
                if iv[i][0] <= R <= iv[i][1]:
                    v = json.loads(json.dumps(plan))
                    v['cmds'][i].update(run=R, given=R - 20)
                    vs.append((i, R, v))
        outs = run_batch([(v, end + 3, 0) for _, _, v in vs], os.path.join(a.out, 'polish'))
        sc = [10 ** 9 if o is None else window_score(o, rec, p3, 0, end) for o in outs]
        j = min(range(len(sc)), key=sc.__getitem__)
        print(json.dumps({'cur': cur, 'best': sc[j], 'cmd': vs[j][0], 'R': vs[j][1]}), flush=True)
        if sc[j] >= cur:
            break
        i, R, plan = vs[j]
        moves.append({'cmd': i, 'R': R, 'score': sc[j]})
        cur = sc[j]
    json.dump(plan, open(os.path.join(a.out, 'plan.json'), 'w'), indent=1)
    json.dump({'moves': moves, 'final': cur}, open(os.path.join(a.out, 'polish.json'), 'w'), indent=1)


# ---------------------------------------------------------------- scoring
def perturb(obs, rec):
    """Planted bug: 1 HP off one non-tower unit on the first recorded tick that has one."""
    for o in (o for o in obs if o["t"] in rec):
        for e in o['E']:
            if e[1] == 'C':
                e[6] -= 1
                return o['t']
    return None


def score(a):
    rec = load_frames(a.rec, key='f')
    plan = json.load(open(a.plan))
    obs = run_batch([(plan, max(rec) + 5, 0)], os.path.join(a.out, 'full'))[0]
    planted = perturb(obs, rec) if a.perturb else None
    by = {o['t']: o for o in obs}
    frames, exact, first, census, census_frames = 0, 0, None, collections.Counter(), collections.Counter()
    exact_board = exact_s1 = 0
    per, label_shift = [], []
    for t in sorted(rec):
        if t not in by:
            census['frame_missing_in_sim'] += 1
            continue
        frames += 1
        d = diff(canon_rec(rec[t]), canon_sim(by[t]))
        board = [x for x in d if not x[0].startswith('S')]
        s1 = [x for x in d if x[0].startswith('S1')]
        exact += not d
        exact_board += not board
        exact_s1 += not s1
        # A frame that equals the sim one tick off is a reader label error (the read straddled a step), not an engine one.
        shift = None
        if d:
            for k in SHIFTS:
                if t + k in by and not diff(canon_rec(rec[t]), canon_sim(by[t + k])):
                    shift = k
                    break
        if shift is not None:
            census['frame_label_shift%+d' % shift] += 1
            census_frames['frame_label_shift%+d' % shift] += 1
            label_shift.append(t)
        else:
            for x in d:
                census[x[0]] += 1
            for k in {x[0] for x in d}:
                census_frames[k] += 1
            if d and first is None:
                first = (t, d)
        per.append({'t': t, 'n': len(d), 'shift': shift, 'd': d[:8]})
    res = {'seed': plan['seed'], 'frames': frames, 'exact_frames': exact, 'exact_share': exact / max(frames, 1),
           'exact_board_frames': exact_board, 'exact_side1_frames': exact_s1,
           'label_shift_frames': label_shift, 'exact_or_shift_frames': exact + len(label_shift),
           'first_divergence': first,'census_objects': dict(census), 'census_frames': dict(census_frames),
           'planted_tick': planted, 'sim_ended_tick': obs[-1]['t'], 'rec_last_tick': max(rec),
           'sme_pass': exact == frames and frames == len(rec)}
    if a.p3:  # secondary: the live client's own reader frames (P3 capture, board only, no hands/elixir)
        p3 = load_frames(a.p3)
        ok = [t for t in p3 if t in by and not diff(canon_rec(p3[t], False), canon_sim(by[t], False))]
        res['p3_frames'], res['p3_exact_board'] = sum(t in by for t in p3), len(ok)
        res['p3_nonexact_ticks'] = sorted(t for t in p3 if t in by and t not in set(ok))
    tag = 'perturb' if a.perturb else 'score'
    json.dump(res, open(os.path.join(a.out, tag + '.json'), 'w'), indent=1, default=str)
    with open(os.path.join(a.out, tag + '_frames.jsonl'), 'w') as w:
        for x in per:
            w.write(json.dumps(x, default=str) + '\n')
    print(json.dumps({k: v for k, v in res.items() if k != 'first_divergence'}, default=str))
    print('first_divergence', json.dumps(first, default=str)[:3000])


def selftest():
    f = {'entities': [{'card_id': -1, 'side': 0, 'x': 9000, 'y': 3000, 'hp': 7728},
                      {'card_id': 26000000, 'side': 1, 'x': 3499, 'y': 17499, 'hp': 2822}],
         'projectiles': [], 'effects': [], 'players': [{'side': 1, 'elixir_raw': 60000, 'hand_deck_indices': [5, 3, 7, 0],
                                                        'cycle_deck_indices': [6, 2, 4, 1]}]}
    o = {'E': [[1, 'T', 'KingTower', 0, 9000, 3000, 7728, 7728, ''], [2, 'C', 'Knight', 1, 3499, 17499, 2822, 2822, '']],
         'S': [[60000, [0, 1, 2, 3], [4, 5, 6, 7]], [60000, [5, 3, 7, 0], [6, 2, 4, 1]]]}
    assert diff(canon_rec(f), canon_sim(o)) == []
    o['E'][1][6] -= 1  # the planted 1-HP bug must fail
    d = diff(canon_rec(f), canon_sim(o))
    assert [x[0] for x in d] == ['U_rec_only', 'U_sim_only'] and d[0][2] == (0, 0, -1), d
    o['E'][1][6] += 1
    o['S'][1][0] += 1  # 1e-4 elixir must fail
    assert [x[0] for x in diff(canon_rec(f), canon_sim(o))] == ['S1_elixir']
    print('selftest ok')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['fit', 'polish', 'score', 'selftest'])
    ap.add_argument('--rec'); ap.add_argument('--p3'); ap.add_argument('--seed', type=int)
    ap.add_argument('--plan'); ap.add_argument('--out'); ap.add_argument('--perturb', action='store_true')
    a = ap.parse_args()
    {'fit': fit, 'polish': polish, 'score': score, 'selftest': lambda a: selftest()}[a.mode](a)
