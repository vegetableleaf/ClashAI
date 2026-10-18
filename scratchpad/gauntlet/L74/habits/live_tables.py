"""L74/habits live tables (A bridge X-Bow + punish window, B heavy pushes, C Rockets) per Mark, from cache/*.pkl.
    python live_tables.py [--json live_rows.json]"""
from __future__ import annotations

import argparse
import bisect
import glob
import json
import math
import pickle
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hablib as H  # noqa: E402

RULES = {'lethal_rocket', 'rocket_tornado', 'rocket_value'}   # decode rules that play a Rocket; anything else = the model
MARKS = {'ICEBOW Mark CXXIV: LONGER': 'CXXIV', 'ICEBOW Mark CXXXVIII: CUES': 'CXXXVIII', 'ICEBOW Mark CLIII: LEVELS': 'CLIII'}


def load():
    out = []
    for f in sorted(glob.glob(str(HERE / 'cache/*.pkl'))):
        c = pickle.load(open(f, 'rb'))
        mk = MARKS.get(c['meta']['mark'])
        if mk is None:
            continue
        est_t = [t for t, _ in c['est']]
        est_v = [e for _, e in c['est']]

        def est(t, est_t=est_t, est_v=est_v):
            i = bisect.bisect_right(est_t, t) - 1
            if i < 0:
                return 6.0
            from pipeline.opp_elixir_count import regen_between, MAX_ELIXIR
            return min(MAX_ELIXIR, est_v[i] + regen_between(est_t[i], t)) if t - est_t[i] < 20 else est_v[i]
        dec_t = [d[0] for d in c['dec']]

        def hand(t, dec=c['dec'], dec_t=dec_t):
            i = bisect.bisect_right(dec_t, t) - 1
            if i < 0:
                return None, None
            return [H.norm(n) for n in dec[i][1]], dec[i][2]
        own = [dict(tick=q['tick'], card=H.norm(q['name']), x=q['x'], y=q['y'], why=q['why'], est_model=q['opp_est_model'])
               for q in c['own']]
        opp = [dict(tick=p['tick'], card=H.norm(p['card']), x=p['x'], y=p['y']) for p in c['opp']]
        frames = [(t, T, [(b[0], H.norm(b[1]) if b[1] else None, b[2], b[3], b[4], b[5], b[6]) for b in E],
                   [(b[0], H.norm(b[1]), b[2], b[3], b[4]) for b in O]) for t, T, E, O in c['frames']]
        out.append(dict(src='live', group=mk, key=c['meta']['log'], win=1.0 if c['meta']['result'] == 'WIN' else 0.0,
                        own=own, opp=opp, frames=frames, est=est, hand=hand, check=c['check'], meta=c['meta']))
    return out


def body_pushes(m):
    """Body-based heavy pushes (live frames): value = elixir of the distinct opponent troop plays with >= 1 body on our half
    (y >= 16); a body belongs to the latest same-card play first seen <= 200 ticks before it. Event = value first >= 10
    (re-armed once it falls below 3). Response: our plays in [t - 40, t + 160]; outcome over [t, t + 400]."""
    plays = sorted([p for p in m['opp'] if H.kind(p['card']) == 'troop'], key=lambda p: p['tick'])
    first = {}
    for t, T, E, O in m['frames']:
        for b in E:
            first.setdefault(b[0], t)
    owner = {}
    keyof = {}
    for t, T, E, O in m['frames']:
        for b in E:
            keyof[b[0]] = b[1]
    for bid, t0 in first.items():
        k = keyof[bid]
        cand = [i for i, p in enumerate(plays) if p['card'] == k and p['tick'] - 2 <= t0 and t0 - p['tick'] <= 200]
        if cand:
            owner[bid] = cand[-1]
    ev, armed = [], True
    alive_last = {}
    for t, T, E, O in m['frames']:
        on = {owner[b[0]] for b in E if b[0] in owner and b[6] >= H.OUR_HALF_Y and b[3] > 0}
        for b in E:
            if b[0] in owner:
                alive_last[owner[b[0]]] = t
        v = sum(H.cost(plays[i]['card']) for i in on)
        if armed and v >= H.PUSH_VALUE:
            ev.append((t, v, sorted(on)))
            armed = False
        elif v < 3:
            armed = True
    rows = []
    for t, v, idx in ev:
        ours = [q for q in m['own'] if t - 40 <= q['tick'] <= t + 160]
        cards = [q['card'] for q in ours]
        rk = [q for q in ours if q['card'] == 'rocket']
        tn = [q for q in ours if q['card'] == 'tornado']
        combo = any(abs(a['tick'] - b['tick']) <= 60 for a in rk for b in tn)
        cheap = [q for q in ours if H.cost(q['card']) <= H.CHEAP_COST]
        resp = 'rocket+tornado' if combo else 'rocket' if rk else 'cheap_only' if ours and len(cheap) == len(ours) else \
            'none' if not ours else 'other'
        h, el = m['hand'](t)
        T0, T1 = H.tower_at(m, t), H.tower_at(m, t + 400)
        killed = sum(H.cost(plays[i]['card']) for i in idx if alive_last.get(i, 0) <= t + 400)
        rows.append(dict(group=m['group'], key=m['key'], win=m['win'], tick=t, value=v, cards=sorted({plays[i]['card'] for i in idx}),
                         resp=resp, n_cheap=len(cheap), spent=sum(H.cost(c) for c in cards), ours=cards,
                         rocket_in_hand=bool(h and 'rocket' in h), own_el=el,
                         taken=H.tower_sum(T0, 'own') - H.tower_sum(T1, 'own'),
                         lost_tower=sum(T0.get(('own', s), 0) > 0 and T1.get(('own', s), 0) <= 0 for s in 'KLR'),
                         killed=killed, trade=killed - sum(H.cost(c) for c in cards)))
    return rows


def pct(x):
    return f'{100 * x:.1f}%' if x == x else 'n/a'


def timing(ms, groups):
    print('\n## A-pro. FIRST bridge X-Bow of the match: when, at what opponent elixir, after what')
    print('  group                    matches  with-bridge  t_first_s(med)  idx(med)  in-first-2  est(med)  band <=3/4-6/>=7     punish   heavy-next  win(with)')
    for g in groups:
        M = [m for m in ms if m['group'] == g]
        if not M:
            continue
        F = []
        for m in M:
            rows = H.xbow_events(m)
            if rows:
                F.append(rows[0])
        if not F:
            continue
        b = Counter(r['band'] for r in F)
        print(f"  {g:24s} {len(M):6d}  {len(F) / len(M):9.3f}  {statistics.median(r['tick'] for r in F) * H.TICK_S:9.1f}  "
              f"{statistics.median(r['idx'] for r in F):7.1f}  {pct(H.mean([r['early'] for r in F])):>8s}  "
              f"{statistics.median(r['est'] for r in F):6.2f}  {pct(b['<=3'] / len(F))}/{pct(b['4-6'] / len(F))}/{pct(b['>=7'] / len(F))}  "
              f"{pct(H.mean([r['punish'] for r in F])):>7s}  {pct(H.mean([r['heavy'] for r in F])):>7s}  {pct(H.wr(F))}")


def table_xbow(rows, groups, title):
    print(f'\n## {title}')
    for g in groups:
        R = [r for r in rows if r['group'] == g]
        if not R:
            continue
        n_m = len({r['key'] for r in R})
        life = [r['life_s'] for r in R if 'life_s' in r]
        print(f"\n{g}: {len(R)} bridge X-Bows in {n_m} matches; first-2-play share {pct(H.mean([r['early'] for r in R]))}; "
              f"win {pct(H.wr(R))}; life median {statistics.median(life) if life else 'n/a'} s (n {len(life)})")
        print('  split                     n    win%   heavy-at-it%  life_s  dmg   taken  est   punish%')
        for lab, f in [('all', lambda r: True), ('first X-Bow', lambda r: r['first']), ('early (first 2 plays)', lambda r: r['early'])] + \
                [(f'est {b}', lambda r, b=b: r['band'] == b) for b in ('<=3', '4-6', '>=7')] + \
                [('punish yes', lambda r: r['punish']), ('punish no', lambda r: not r['punish'])] + \
                [(f'punish no & est {b}', lambda r, b=b: not r['punish'] and r['band'] == b) for b in ('<=3', '4-6', '>=7')] + \
                [('first & punish no', lambda r: r['first'] and not r['punish']), ('first & punish yes', lambda r: r['first'] and r['punish']),
                 ('heavy came', lambda r: r['heavy']), ('no heavy', lambda r: not r['heavy'])]:
            S = [r for r in R if f(r)]
            if not S:
                continue
            L = [r['life_s'] for r in S if 'life_s' in r]
            ci = H.boot_ci(S, H.wr) if len(S) >= 10 else ('', '')
            print(f"  {lab:24s} {len(S):5d}  {pct(H.wr(S)):>6s} {str(ci):18s} {pct(H.mean([r['heavy'] for r in S])):>6s}  "
                  f"{statistics.median(L) if L else float('nan'):5.1f}  {H.mean([r.get('dmg') for r in S]):5.0f}  "
                  f"{H.mean([r.get('taken') for r in S]):5.0f}  {H.mean([r['est'] for r in S]):4.1f}  {pct(H.mean([r['punish'] for r in S]))}")


def table_push(rows, groups, title, body=False):
    print(f'\n## {title}')
    for g in groups:
        R = [r for r in rows if r['group'] == g]
        if not R:
            continue
        n_m = len({r['key'] for r in R})
        print(f"\n{g}: {len(R)} heavy pushes in {n_m} matches (value mean {H.mean([r['value'] for r in R]):.1f})")
        print('  response          n   share   win%  [95% CI]           taken  lost_tw  cheap#  spent  rocket_in_hand  ' +
              ('killed  trade' if body else ''))
        for resp in ('rocket+tornado', 'rocket', 'cheap_only', 'other', 'none'):
            S = [r for r in R if r['resp'] == resp]
            if not S:
                continue
            ci = H.boot_ci(S, H.wr) if len(S) >= 10 else ''
            extra = f"  {H.mean([r.get('killed') for r in S]):5.1f}  {H.mean([r.get('trade') for r in S]):+5.1f}" if body else ''
            print(f"  {resp:15s} {len(S):4d}  {pct(len(S) / len(R)):>6s}  {pct(H.wr(S)):>6s} {str(ci):18s} "
                  f"{H.mean([r.get('taken') for r in S]):6.0f}  {H.mean([r.get('lost_tower') for r in S]):.2f}  "
                  f"{H.mean([r['n_cheap'] for r in S]):4.1f}  {H.mean([r['spent'] for r in S]):4.1f}  "
                  f"{pct(H.mean([r.get('rocket_in_hand') for r in S]))}{extra}")
        S = [r for r in R if r.get('rocket_in_hand')]
        if S:
            print(f"  -- Rocket in hand at the event: {len(S)} pushes; responses " +
                  ', '.join(f"{k} {pct(v / len(S))}" for k, v in Counter(r['resp'] for r in S).most_common()))


def table_rocket(ms, rows, groups):
    print('\n## C. Rockets per match by use (aim) and by who played it (decision why)')
    for g in groups:
        M = [m for m in ms if m['group'] == g]
        R = [r for r in rows if r['group'] == g]
        if not M:
            continue
        n = len(M)
        per = lambda f: sum(1 for r in R if f(r)) / n
        print(f"  {g:9s} matches {n:4d}  Rockets/match {per(lambda r: True):.2f}  tower {per(lambda r: r['aim'] == 'tower'):.2f}  "
              f"defence(our half) {per(lambda r: r['aim'] == 'defence'):.2f}  enemy-half troops {per(lambda r: r['aim'] == 'enemy_half'):.2f}"
              f"  | model {per(lambda r: r['why'] not in RULES):.2f}  lethal rule {per(lambda r: r['why'] == 'lethal_rocket'):.2f}  "
              f"combo rule {per(lambda r: r['why'] == 'rocket_tornado'):.2f}  late(>=2400) {per(lambda r: r['late']):.2f}")
        rpm = {m['key']: 0 for m in M}
        for r in R:
            rpm[r['key']] += 1
        xs = [dict(key=k, v=v) for k, v in rpm.items()]
        print(f"            Rockets/match 95% CI {H.boot_ci(xs, lambda s: H.mean([r['v'] for r in s]))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', default=str(HERE / 'live_rows.json'))
    a = ap.parse_args()
    ms = load()
    groups = ['CXXIV', 'CXXXVIII', 'CLIII']
    print('matches:', Counter(m['group'] for m in ms))
    chk = [m['check'] for m in ms]
    print('counter rebuilt == logged on', sum(c['exact'] for c in chk), '/', sum(c['n'] for c in chk), 'frames; matches with any',
          'rebase (estimate proven LOW):', sum((c['rebases'] or 0) > 0 for c in chk), 'of', len(chk), '; rebases', sum(c['rebases'] or 0 for c in chk),
          'adding', round(sum(c['rebase_total'] or 0 for c in chk), 1), 'elixir')
    X = [r for m in ms for r in H.xbow_events(m)]
    # sanity: own X-Bow play vs body position
    P = [r for m in ms for r in H.push_events(m)]
    B = [r for m in ms for r in body_pushes(m)]
    K = [r for m in ms for r in H.rocket_uses(m)]
    timing(ms, groups)
    table_xbow(X, groups, 'A. Bridge X-Bows (16 <= y <= 20.5), live')
    table_push(B, groups, 'B1. Heavy pushes, BODY-based (>= 10 elixir of opponent troops on our half), live', body=True)
    table_push(P, groups, 'B2. Heavy pushes, PLAY-based (>= 10 elixir of opponent troops played in 15 s; same rule as pros / SIM), live')
    table_rocket(ms, K, groups)
    json.dump(dict(xbow=X, push_body=B, push_play=P, rocket=K), open(a.json, 'w'), default=str)


if __name__ == '__main__':
    main()
