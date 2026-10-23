"""PUSH_CAL (10-23): opponent pushes on ONE definition for the SIM (gap.py --record-board 'hab' rows) and live (habits-cache
pickles of the same CLX logs exploit/ape_punish.py scored). PUSH_CAL.md has the findings.

  python push_cal.py sim OUT.jsonl SRC DIR [DIR ...]     (pod: per-push rows of every matches.jsonl under DIR/*/D3)
  python push_cal.py live OUT.jsonl                       (laptop: the 473 CLX matches in clx_live.txt)
  python push_cal.py report ROWS.jsonl [ROWS.jsonl ...]   (tables; SRC = e4 / iu40 / live)

Push = exploit/ape_punish.score() section 4, unchanged: enemy troops crossing onto our half, grouped from the first
crossing until our half is clear (>= 6 s, <= 20 s); value = each crossing body's elixir at its first sample on our half
(hp-scaled); counted if >= 3 elixir; lost = our tower HP from 1 tick before to 2 s after; spend = our plays on our half.
What changed vs ape_punish, to make both sides the same:
  * ONE body-value rule (the live one, ape_punish.body_value): the SIM engine name is the OWNER CARD (a Witch's skeletons
    are named 'Witch', a Furnace's spirits 'FirespiritHut'), exactly like the live card_id. ape_punish.sim_value treated it
    as the unit, so every spawned child was worth the full card ('val_old' keeps it for the reproduction check).
  * ONE sample grid: live frames (>= 6 ticks) resampled to the SIM's 20-tick grid.
  * Entities with max_hp < 20 (spawn / effect placeholders, not units) are dropped on both sides.
  * Our plays at their landing tick on both sides (SIM land tick, live confirmation = the game's elixir drop).
"""
from __future__ import annotations

import bisect
from collections import Counter, defaultdict
import glob
import json
import os
import pickle
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[1]
REPO = L74.parents[2]
sys.path[:0] = [str(REPO), str(L74 / 'log_use'), str(L74 / 'exploit'), str(L74 / 'clx_ranked')]
import log_use as L                                         # noqa: E402  (also sets idle priority)
from pipeline.opp_elixir_count import card_cost             # noqa: E402
import ape_punish as AP                                     # noqa: E402

PUSH_WIN, PUSH_CAP, PUSH_MIN, HP_GRACE = AP.PUSH_WIN, AP.PUSH_CAP, AP.PUSH_MIN, AP.HP_GRACE
STEP, MIN_MX, CLOCK_OFF = int(os.environ.get("PUSH_STEP", 20)), 20, 78          # common grid; placeholder cut; live tick - 78 = game clock (invlib)
RANKED_FROM = 'live_play_20261020_132855'      # clx_ranked/anatomy.load: first Ranked CLX match
WINCON = ('x_bow', 'mortar', 'royal_giant', 'lava_hound', 'golem', 'electro_giant', 'goblin_giant', 'giant', 'elixir_golem',
          'mega_knight', 'pekka', 'hog_rider', 'royal_hogs', 'ram_rider', 'battle_ram', 'balloon', 'graveyard', 'goblin_drill',
          'miner', 'goblin_barrel', 'wall_breakers', 'three_musketeers', 'sparky', 'skeleton_barrel', 'goblin_machine',
          'rune_giant', 'boss_bandit', 'giant_skeleton', 'skeleton_king', 'goblinstein', 'bowler', 'executioner')  # anatomy
GROUP = dict(hog_rider='hog', mega_knight='bridge', pekka='bridge', royal_hogs='bridge', ram_rider='bridge',
             battle_ram='bridge', boss_bandit='bridge', goblin_barrel='bait', skeleton_barrel='bait', goblin_drill='bait',
             wall_breakers='bait', graveyard='control', miner='control', x_bow='control', mortar='control',
             sparky='control', bowler='control', executioner='control', skeleton_king='control', goblin_machine='control')
GROUP.update({w: 'beatdown' for w in ('royal_giant', 'lava_hound', 'golem', 'electro_giant', 'goblin_giant', 'giant',
                                      'elixir_golem', 'balloon', 'three_musketeers', 'rune_giant', 'giant_skeleton',
                                      'goblinstein')})


def canon(c):
    return str(c).replace('-', '_').lower().replace('_evo', '').replace('_hero', '')


def arch(cards):
    w = next((w for w in WINCON if w in cards), 'other')
    return w, GROUP.get(w, 'other')


def phase(t):
    return '1x' if t < 2400 else '2x' if t < 3600 else 'OT'


def card_val(key, hp, mx, top):
    """ape_punish.body_value on a card key: None for buildings; role children (max_hp < 45% of the card's biggest body)
    and spell bodies not in BODY_COUNT = CHILD_VALUE; else cost / BODY_COUNT. hp-scaled."""
    tr = L.TRAITS.get(key, {})
    if tr.get('kind') == 'building' or 'tower' in key:
        return None, False
    cost = card_cost(key) or tr.get('elixir') or 3.0
    child = mx < .45 * top[key] or (tr.get('kind') == 'spell' and key not in L.BODY_COUNT)
    base = L.CHILD_VALUE if child else cost / L.BODY_COUNT.get(key, 1)
    return base * max(0, hp) / max(1, mx), child


def pushes(F, P, E, opp_plays, rule="card", end=None):
    """F: [(t, tower {slot: hp}, [(bid, key, hp, mx, ox, oy, old_value)])] on the grid; P: our plays [(t, name, ox, oy)];
    E: [(t, our elixir)]; opp_plays: [(t, card, cost, is_troop, own-frame y tiles: own king 29)]. -> per-push dicts."""
    top = defaultdict(int)
    for _, _, en in F:
        for b in en:
            top[b[1]] = max(top[b[1]], b[3])
    # towers: a slot missing from a frame (live reader gap) keeps its last reading; it is dead from the first sample after
    # its last positive reading only if its last present reading is <= 0 or it stays missing for >= 3 samples to the end
    slots = sorted({k for _, tw, _ in F for k in tw})
    death = {}
    for k in slots:
        pres = [(i, tw[k]) for i, (_, tw, _) in enumerate(F) if k in tw]
        alive = [i for i, hp in pres if hp > 0]
        gone = pres[-1][1] <= 0 or len(F) - 1 - pres[-1][0] >= 3
        death[k] = None if not gone else F[min(alive[-1] + 1, len(F) - 1)][0] if alive else F[0][0]
    # the match is decided at our deciding fall (an OT tower or the king): live reads the end 1.5-3 s late (DIAG_12)
    end = min([end or 10 ** 9] + [d for k, d in death.items() if d is not None and (d >= 3600 or k == 'K')])
    S, last = [], {}
    for t, tw, en in F:
        last = {k: 0 if death[k] is not None and t >= death[k] else tw.get(k, last.get(k, 0)) for k in slots}
        tw = last
        vh, on = 0.0, {}
        for bid, key, hp, mx, ox, oy, old in en:
            if rule == 'old':                   # ape_punish's own SIM rule on every entity (reproduction check)
                v, child = old, False
            elif mx < MIN_MX:
                continue
            else:
                v, child = card_val(key, hp, mx, top)
            if v is None:
                continue
            if oy > .5:
                vh += v
                on[bid] = (v, old, key, child, int(ox >= 9), mx)
        S.append((t, vh, on, tw))
    ts = [s[0] for s in S]
    et = [e[0] for e in E]

    def st(t):
        return S[max(0, bisect.bisect_right(ts, t) - 1)]

    def el(t):
        i = bisect.bisect_right(et, t) - 1
        return E[i][1] if i >= 0 else None

    seen, cross = set(), []
    for t, _, on, _ in S:
        for k, x in on.items():
            if k not in seen:
                seen.add(k); cross.append((t, x))
    out, i = [], 0
    while i < len(cross):
        t0 = cross[i][0]
        t1 = min(next((s[0] for s in S if s[0] >= t0 + PUSH_WIN and s[1] < .5), S[-1][0]), t0 + PUSH_CAP)
        grp, tc = [], {}                  # tc: first crossing tick per card (bodies >= 1 elixir)
        while i < len(cross) and cross[i][0] <= t1:
            tb, x = cross[i]
            grp.append(x)
            if x[0] >= 1:
                tc.setdefault(x[2], tb)
            i += 1
        val = sum(g[0] for g in grp)
        old = sum(g[1] or 0 for g in grp)
        a, b = st(t0 - 1)[3], st(t1 + HP_GRACE)[3]
        lost = sum(a.values()) - sum(b.values())
        fell = sum(1 for k in slots if k != 'K' and death[k] is not None and t0 <= death[k] <= t1 + HP_GRACE)
        spend = sum(AP.COST.get(q[1], 3) for q in P if t0 - HP_GRACE <= q[0] <= t1 and q[3] > .5)
        comp = Counter()
        for g in grp:
            comp[g[2]] += g[0]
        lanes = Counter()
        for g in grp:
            lanes[g[4]] += g[0]
        last = [q for q in P if q[0] < t0]
        recent = [q for q in P if t0 - 200 <= q[0] < t0]
        oc = [(c, x, tr, y) for t, c, x, tr, y in opp_plays if t0 - 200 <= t <= t1]
        ans = next((q[0] for q in P if q[0] >= t0 - 20 and q[3] > .5), None)
        out.append(dict(
            t0=t0, ph=phase(t0), dur=t1 - t0, val=round(val, 3), val_old=round(old, 3), n_b=len(grp),
            n_child=sum(g[3] for g in grp), v_child=round(sum(g[0] for g in grp if g[3]), 3),
            comp={k: round(v, 2) for k, v in comp.most_common()},
            split=int(min(lanes[0], lanes[1]) >= 1.5),
            v_tank=round(sum(g[0] for g in grp if g[5] >= 3000), 3), peak=round(max(s[1] for s in S if t0 <= s[0] <= t1), 2),
            spread=(max(tc.values()) - min(tc.values())) / 20 if len(tc) >= 2 else None,
            lost=round(max(0.0, lost), 1), fell=fell, spend=spend, el0=el(t0), cut=int(t1 + HP_GRACE > min(S[-1][0], end or 10 ** 9)),   # window reaches the decided end
            dt_last=(t0 - last[-1][0]) if last else None,
            off10=sum(AP.COST.get(q[1], 3) for q in recent if q[3] <= .5 or q[1] == 'Xbow'),   # our offensive spend, 10 s
            opp_el=round(sum(x for _, x, _, _ in oc), 2), opp_el_troop=round(sum(x for _, x, tr, _ in oc if tr), 2),
            opp_y=[round(y, 1) for _, _, tr, y in oc if tr], react=None if ans is None else (ans - t0) / 20,
            ok=val >= PUSH_MIN))
    return [p for p in out if p.pop('ok')]


# ------------------------------------------------------------------ SIM
def sim_match(j, src, file):
    h = j['hab']
    side = h['L']
    smp = h['samples']
    if not smp:
        return None
    king_y = next(t[3] for t in smp[0][5] if t[0] == side and t[1] == 'k')
    low = king_y < 16000

    def own(x, y):
        x, y = (x / 1000, y / 1000) if max(abs(x), abs(y)) > 100 else (x, y)
        return (x, 1 - y / 32) if low else (18 - x, y / 32)

    F, E, drop = [], [], 0
    for t, _a, _b, _c, el, tw, en, _xb in smp:
        slots = {}
        for s_, kind, x, y, hp in tw:
            if s_ == side:
                slots['K' if kind == 'k' else ('L' if own(x, y)[0] < 9 else 'R')] = max(0, hp)
        bodies = []
        for uid, name, hp, mx, x, y in en:
            drop += mx < MIN_MX
            k = L.vocab.engine_key(name) or ''
            ox, oy = own(x, y)
            bodies.append((uid, k, hp, mx, ox, oy, AP.sim_value(name, hp, mx)))
        F.append((t, slots, bodies))
        E.append((t, el))
    P, P0 = [], []                                  # landing tick; P0 = decision tick (as ape_punish)
    for q in h['own']:
        if q[3]:
            ox, oy = own(q[8], q[9])
            nm = AP.SIM_NAME.get(AP.slug(q[2]).replace('_evo', ''), q[2])
            P.append((q[1], nm, ox, oy)); P0.append((q[0], nm, ox, oy))
    opp = [(q[1], canon(q[2]), card_cost(canon(q[2])) or 3.0, L.TRAITS.get(canon(q[2]), {}).get('kind') == 'troop',
            32 * own(q[8], q[9])[1]) for q in h['opp'] if q[3]]
    w, g = arch({q[1] for q in opp})
    return dict(src=src, key=f"{Path(file).parent.parent.name}:{j.get('seed')}:{j.get('tag')}", win=float(j.get('outcome') == 'win'),
                end=j.get('end_tick'), wincon=w, arch=g, drop=drop, opp_el=round(sum(q[2] for q in opp), 1),
                pushes=pushes(F, P, E, opp, end=j.get('end_tick')), old=[(p['val'], p['lost'], p['spend']) for p in pushes(F, P0, E, opp, 'old')])


def sim_cmd(out, src, dirs):
    from multiprocessing import Pool
    files = sorted(f for d in dirs for f in glob.glob(f'{d}/*/D3/matches.jsonl'))
    with Pool(min(48, len(files) * 8)) as pool, open(out, 'w') as fo:
        for rows in pool.imap(_sim_file, [(f, src) for f in files]):
            for r in rows:
                fo.write(json.dumps(r) + '\n')
    print('files', len(files), 'out', out)


def _sim_file(a):
    f, src = a
    out = []
    for line in open(f):
        j = json.loads(line)
        if j.get('hab'):
            r = sim_match(j, src, f)
            if r:
                out.append(r)
    return out


# ------------------------------------------------------------------ live


def live_match(path):
    c = pickle.load(open(path, 'rb'))
    fr = c['frames']
    if not fr:
        return None
    o = CLOCK_OFF
    F, drop, j = [], 0, 0
    g = fr[0][0] - (fr[0][0] - o) % STEP          # grid on the game clock, like the SIM's
    while g <= fr[-1][0]:
        while j + 1 < len(fr) and fr[j + 1][0] <= g:
            j += 1
        t, T, en, _ = fr[j]
        slots = {s: max(0, hp) for (who, s), hp in T.items() if who == 'own'}
        bodies = []
        for bid, key, form, hp, mx, X, Y in en:
            drop += mx < MIN_MX
            bodies.append((bid, key or '?', hp, mx, X, Y / 32, None))     # '?' = unread card_id: 3 elixir, as ape_punish
        F.append((g - o, slots, bodies))
        g += STEP
    E = [(t - o, el) for t, _h, el, *_ in c['dec']]
    P = [(q['tick'] - o, q['name'], q['x'], q['y'] / 32) for q in c['own'] if q['name']]
    opp = [(q['tick'] - o, canon(q['card']), q.get('cost') or card_cost(canon(q['card'])) or 3.0, q.get('kind') == 'troop',
            q['y']) for q in c['opp']]
    cards = {q[1] for q in opp} | {b[1] for _, _, en in F for b in en}
    w, a = arch(cards)
    end = c['meta'].get('end') or {}
    stem = Path(path).stem
    return dict(src='live', key=stem, ranked=int(stem >= RANKED_FROM), win=float(bool((end.get('towers') or {}).get('won'))),
                end=F[-1][0], wincon=w, arch=a, drop=drop, opp_el=round(sum(q[2] for q in opp), 1),
                pushes=pushes(F, P, E, opp, end=((end.get('towers') or {}).get('tick') or 10 ** 9) - o))


def live_cmd(out):
    stems = open(HERE / 'clx_live.txt').read().split()
    n = 0
    with open(out, 'w') as fo:
        for s in stems:
            p = L74 / 'habits/cache' / f'{s}.pkl'
            p = p if p.exists() else HERE / 'cache_extra' / f'{s}.pkl'
            r = live_match(p)
            if r:
                fo.write(json.dumps(r) + '\n'); n += 1
    print('live matches', n, 'of', len(stems))


# ------------------------------------------------------------------ report
def load(paths):
    M = []
    for p in paths:
        M += [json.loads(x) for x in open(p)]
    return M


def per_match(m, f=lambda p: True):
    P = [p for p in m['pushes'] if f(p)]
    if m['src'] == 'live':          # live: ape_punish's rule IS the one rule
        P = [dict(p, val_old=p['val']) for p in P]
    return dict(n=len(P), val=sum(p['val'] for p in P), old=sum(p['val_old'] or 0 for p in P), lost=sum(p['lost'] for p in P),
                spend=sum(p['spend'] for p in P), fell=sum(p['fell'] > 0 for p in P),
                conv=sum(p['lost'] >= 1000 or p['fell'] > 0 for p in P), child=sum(p['v_child'] for p in P),
                tank=sum(p['v_tank'] for p in P), split=sum(p['split'] for p in P), nb=sum(p['n_b'] for p in P),
                ncard=sum(len(p['comp']) for p in P), top=sum(max(p['comp'].values()) / p['val'] for p in P),
                el0=sum(p['el0'] or 0 for p in P), oel=sum(p['opp_el'] for p in P), oelt=sum(p['opp_el_troop'] for p in P),
                dur=sum(p['dur'] for p in P))


STATS = [  # (label, numerator, denominator); denominators: 'm' = matches
    ('pushes / match', 'n', 'm'), ('elixir / push (one rule)', 'val', 'n'), ('elixir / push (ape_punish rule)', 'old', 'n'),
    ('opp elixir played -10 s..end / push', 'oel', 'n'), ('  of it troops', 'oelt', 'n'),
    ('our spend / push', 'spend', 'n'), ('defence trade / push (value - spend)', 'trade', 'n'),
    ('tower HP lost / push', 'lost', 'n'), ('tower HP lost / push elixir', 'lost', 'val'),
    ('conversion: lost >= 1000 or a tower fell', 'conv', 'n'), ('a princess fell in the push', 'fell', 'n'),
    ('cards / push', 'ncard', 'n'), ('bodies / push', 'nb', 'n'), ('top card share of value', 'top', 'n'),
    ('child-body share of value', 'child', 'val'), ('tank (max_hp >= 3000) share of value', 'tank', 'val'),
    ('both-lane (split) share', 'split', 'n'), ('push duration s', 'dur', 'n'), ('our elixir at push start', 'el0', 'n')]


def ratio(rows, num, den):
    if num == 'trade':
        s = sum(r['val'] - r['spend'] for r in rows)
    else:
        s = sum(r[num] for r in rows)
    d = len(rows) if den == 'm' else sum(r[den] for r in rows)
    k = 20.0 if num == 'dur' else 1.0
    return s / d / k if d else float('nan')


def boot(rows, num, den, B=400, seed=7):
    rng = random.Random(seed)
    n = len(rows)
    v = sorted(ratio([rows[rng.randrange(n)] for _ in range(n)], num, den) for _ in range(B))
    return v[int(.025 * B)], v[int(.975 * B)]


def table(sets, title, f=lambda p: True, ci=False):
    names = list(sets)
    R = {k: [per_match(m, f) for m in v] for k, v in sets.items()}
    print(f'\n### {title}\n')
    print('| metric | ' + ' | '.join(f'{k} (n {len(sets[k])})' for k in names) + ' |')
    print('|---|' + '---|' * len(names))
    for lab, a, b in STATS:
        cells = []
        for k in names:
            x = ratio(R[k], a, b)
            s = f'{x:.3f}' if abs(x) < 10 else f'{x:.1f}'
            if ci and len(R[k]) > 20:
                lo, hi = boot(R[k], a, b)
                s += f' [{lo:.2f}, {hi:.2f}]' if abs(x) < 10 else f' [{lo:.0f}, {hi:.0f}]'
            cells.append(s)
        print(f'| {lab} | ' + ' | '.join(cells) + ' |')


def report(paths):
    M = load(paths)
    by = defaultdict(list)
    for m in M:
        by[m['src']].append(m)
    live = by.pop('live', [])
    rk = [m for m in live if m['ranked']]
    sets = dict(by, live_all=live, live_ranked=rk)
    print('placeholder entities dropped / match:', {k: round(sum(m['drop'] for m in v) / max(1, len(v)), 1) for k, v in sets.items()})
    print('opponent elixir played / match:', {k: round(sum(m['opp_el'] for m in v) / max(1, len(v)), 1) for k, v in sets.items()},
          '| minutes / match:', {k: round(sum(m['end'] for m in v) / max(1, len(v)) / 1200, 2) for k, v in sets.items()})
    for k, v in by.items():
        O = [p for m in v for p in m.get('old', [])]
        if not O:
            continue
        print(f'reproduction of ape_punish on {k} (its SIM rule, decision ticks, every entity): pushes / match '
              f'{len(O) / len(v):.2f}, elixir / push {sum(x[0] for x in O) / len(O):.2f}, HP lost / push elixir '
              f'{sum(x[1] for x in O) / sum(x[0] for x in O):.1f}, trade / push {sum(x[0] - x[2] for x in O) / len(O):+.2f}')
    done = lambda p: not p.get('cut')                     # noqa: E731 -- push window complete before the recording ends
    cut = {k: sum(p.get('cut', 0) for m in v for p in m['pushes']) / max(1, sum(len(m['pushes']) for m in v)) for k, v in sets.items()}
    print('share of pushes cut by the end of the recording (dropped below):', {k: round(x, 3) for k, x in cut.items()})
    table(sets, 'Complete pushes (95% match-bootstrap CI)', done, ci=True)
    table(sets, 'All pushes, incl. the ones cut by the end of the recording', ci=False)
    gate(sets, done)
    for ph in ('1x', '2x', 'OT'):
        table(sets, f'Phase {ph} (complete pushes)', lambda p, ph=ph: p['ph'] == ph and done(p))
    archs = ['hog', 'bridge', 'beatdown', 'bait', 'control', 'other']
    print('\n### Archetype mix (share of matches)\n')
    print('| arch | ' + ' | '.join(sets) + ' |\n|---|' + '---|' * len(sets))
    for a in archs:
        print(f'| {a} | ' + ' | '.join(f"{sum(m['arch'] == a for m in v) / max(1, len(v)):.3f}" for v in sets.values()) + ' |')
    for a in archs:
        table({k: [m for m in v if m['arch'] == a] for k, v in sets.items()}, f'Archetype {a} (complete pushes)', done)
    P = {k: [p for m in v for p in m['pushes'] if done(p)] for k, v in sets.items()}
    buckets('Our elixir at push start', P, [('el0 < 4', lambda p: p['el0'] is not None and p['el0'] < 4),
                                             ('4-7', lambda p: p['el0'] is not None and 4 <= p['el0'] < 7),
                                             ('>= 7', lambda p: p['el0'] is not None and p['el0'] >= 7),
                                             ('our off-spend >= 6 in the 10 s before', lambda p: p['off10'] >= 6)])
    buckets('MATCHED: push value bucket', P, [(f'{a}-{b}', lambda p, a=a, b=b: a <= p['val'] < b)
                                               for a, b in ((3, 5), (5, 8), (8, 12), (12, 99))])
    buckets('MATCHED: push value 5-8 x our spend', P, [(f'spend {a}-{b}', lambda p, a=a, b=b: 5 <= p['val'] < 8 and a <= p['spend'] < b)
                                                        for a, b in ((0, 3), (3, 6), (6, 9), (9, 99))])
    print('\n### Composition: one-card vs multi-card pushes: share, value, peak value on our half at once, peak / value, '
          'card spread s (first crossing of the first to the last card), HP lost / push, conversion\n')
    print('| set | one-card | multi-card |\n|---|---|---|')
    for k, v in P.items():
        cells = []
        for f in (lambda p: len(p['comp']) == 1, lambda p: len(p['comp']) >= 2):
            Q = [p for p in v if f(p)]
            sp = [p['spread'] for p in Q if p.get('spread') is not None]
            cells.append(f"{len(Q) / len(v):.2f}, {sum(p['val'] for p in Q) / len(Q):.1f}, {sum(p['peak'] for p in Q) / len(Q):.1f}, "
                         f"{sum(p['peak'] for p in Q) / sum(p['val'] for p in Q):.2f}, {sum(sp) / len(sp) if sp else 0:.1f}, "
                         f"{sum(p['lost'] for p in Q) / len(Q):.0f}, {sum(p['lost'] >= 1000 or p['fell'] > 0 for p in Q) / len(Q):.3f}")
        print(f'| {k} | ' + ' | '.join(cells) + ' |')
    print('\n### Placement of the push\'s troop plays (own-frame y tiles, own king 29; their side < 15) and our answer: '
          'share our side (>= 16) / bridge (12.5-16) / mid (8-12.5) / back (< 8); our first defensive play after the first '
          'crossing (s, median); share with no answer within 3 s\n')
    print('| set | troop plays / push | our side | bridge | mid | back | answer s (median) | unanswered 3 s |\n|---|---|---|---|---|---|---|---|')
    for k, v in P.items():
        ys = [y for p in v for y in p.get('opp_y', [])]
        rs = sorted(p['react'] for p in v if p.get('react') is not None)
        bands = [sum(y >= 16 for y in ys), sum(12.5 <= y < 16 for y in ys), sum(8 <= y < 12.5 for y in ys), sum(y < 8 for y in ys)]
        print(f'| {k} | {len(ys) / len(v):.2f} | ' + ' | '.join(f'{b / len(ys):.3f}' for b in bands) +
              f' | {rs[len(rs) // 2]:.2f} | {sum(p.get("react") is None or p["react"] > 3 for p in v) / len(v):.3f} |')
    buckets('MATCHED: push value 5-12 x our answer time (first defensive play from 1 s before the crossing)', P,
            [(lab, lambda p, a=a, b=b: 5 <= p['val'] < 12 and p.get('react') is not None and a <= p['react'] < b)
             for lab, a, b in (('<= 0 s', -9, 0.001), ('0-1 s', 0.001, 1), ('1-3 s', 1, 3), ('> 3 s', 3, 99))] +
            [('none in the push', lambda p: 5 <= p['val'] < 12 and p.get('react') is None)])
    solo = Counter(next(iter(p['comp'])) for p in P['live_all'] if len(p['comp']) == 1)
    buckets('MATCHED: one-card pushes by card (live n >= 25)', P,
            [(c, lambda p, c=c: len(p['comp']) == 1 and c in p['comp']) for c, n in solo.most_common() if n >= 25])
    multi = Counter(next(iter(p['comp'])) for p in P['live_all'] if len(p['comp']) >= 2)
    buckets('MATCHED: multi-card pushes by their top card (live n >= 40)', P,
            [(c, lambda p, c=c: len(p['comp']) >= 2 and next(iter(p['comp'])) == c) for c, n in multi.most_common() if n >= 40])


def buckets(title, P, rows):
    print(f'\n### {title}: n, HP lost / push, conversion, our spend / push, value / push\n')
    print('| bucket | ' + ' | '.join(P) + ' |\n|---|' + '---|' * len(P))
    for lab, f in rows:
        cells = []
        for k, v in P.items():
            Q = [p for p in v if f(p)]
            cells.append(f"{len(Q)}: {sum(p['lost'] for p in Q) / len(Q):.0f}, {sum(p['lost'] >= 1000 or p['fell'] > 0 for p in Q) / len(Q):.3f}, "
                         f"{sum(p['spend'] for p in Q) / len(Q):.1f}, {sum(p['val'] for p in Q) / len(Q):.1f}" if Q else '-')
        print(f'| {lab} | ' + ' | '.join(cells) + ' |')


GATE = [('pushes / match', 'n', 'm', 'rel'), ('elixir / push', 'val', 'n', 'rel'), ('tower HP lost / push', 'lost', 'n', 'rel'),
        ('tower HP lost / push elixir', 'lost', 'val', 'rel'), ('conversion', 'conv', 'n', 'rel'),
        ('defence trade / push', 'trade', 'n', 'abs')]


def gate(sets, f, ref='live_all', tol=.25, abs_tol=1.0):
    """PUSH_CAL gate: SIM / live within +-25% (trade: within +-1 elixir, it sits near 0), overall and per archetype with
    live n >= 40 matches. Low-elixir conversion (el0 < 4) is the 'conversion after our mistakes' cell."""
    print(f'\n### PUSH GATE vs {ref} (complete pushes): SIM / live, PASS within +-{tol:.0%} (trade: +-{abs_tol} elixir)\n')
    archs = [None] + [a for a in ('hog', 'bridge', 'beatdown', 'bait', 'control') if sum(m['arch'] == a for m in sets[ref]) >= 40]
    sims = [k for k in sets if not k.startswith('live')]
    print('| cell | ' + ' | '.join(sims) + ' |\n|---|' + '---|' * len(sims))
    lowc = lambda p: f(p) and p['el0'] is not None and p['el0'] < 4      # noqa: E731
    for a in archs:
        sel = lambda v: [m for m in v if a is None or m['arch'] == a]     # noqa: E731
        live = [per_match(m, f) for m in sel(sets[ref])]
        livel = [per_match(m, lowc) for m in sel(sets[ref])]
        for lab, num, den, kind in GATE + [('conversion at our elixir < 4', 'conv', 'n', 'rel')]:
            L_ = livel if 'elixir < 4' in lab else live
            y = ratio(L_, num, den)
            cells = []
            for k in sims:
                S_ = [per_match(m, lowc if 'elixir < 4' in lab else f) for m in sel(sets[k])]
                x = ratio(S_, num, den)
                ok = abs(x - y) <= abs_tol if kind == 'abs' else abs(x / y - 1) <= tol
                cells.append(f"{x:.2f} vs {y:.2f} ({x - y:+.2f}) {'PASS' if ok else 'FAIL'}" if kind == 'abs' else
                             f"{x:.3g} vs {y:.3g} ({x / y:.2f}x) {'PASS' if ok else 'FAIL'}")
            print(f"| {a or 'all'}: {lab} | " + ' | '.join(cells) + ' |')


def selftest():
    """The one rule on SIM owner-card names (census: a Witch's skeletons are 'Witch' max_hp 130 under a 1,341 Witch)."""
    top = defaultdict(int, witch=1341, goblin_barrel=355, tombstone=931, golem=9000)
    assert abs(card_val('witch', 130, 130, top)[0] - 1 / 3) < 1e-9          # spawned skeleton = a child, not 5 elixir
    assert card_val('witch', 1341, 1341, top)[0] == 5.0
    assert abs(card_val('witch', 670, 1341, top)[0] - 5 * 670 / 1341) < 1e-9   # hp-scaled
    assert card_val('tombstone', 130, 130, top)[0] is None                     # building children: none (live rule)
    assert card_val('goblin_barrel', 323, 323, top)[0] == 1.0                  # spell in BODY_COUNT: 3 / 3
    assert abs(card_val('golem', 1827, 1827, top)[0] - 1 / 3) < 1e-9          # Golemite
    assert AP.sim_value('Witch', 130, 130) == 5.0                              # no top: the old whole-card price
    for nm, hp, mx in (('Witch', 130, 130), ('Witch', 670, 1341), ('Golem', 1827, 1827), ('GoblinBarrel', 323, 323)):
        k = AP.L.vocab.engine_key(nm) or ''                                    # 10-23: ape_punish.sim_value(top=) = this rule
        assert abs(AP.sim_value(nm, hp, mx, top=top) - card_val(k, hp, mx, top)[0]) < 1e-9, nm
    print('selftest ok')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'selftest':
        selftest()
    elif cmd == 'sim':
        sim_cmd(sys.argv[2], sys.argv[3], sys.argv[4:])
    elif cmd == 'live':
        live_cmd(sys.argv[2])
    else:
        report(sys.argv[2:])
