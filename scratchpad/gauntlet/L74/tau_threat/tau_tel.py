"""MEASUREMENT ONLY (VM tree ~/tau_threat/repo, hooked by vm_tel_patch.py): per-match defence metrics from the public telemetry
frames of side ``side`` -- M4 "frozen under fire" runs (the L74 catalogue's definition on 10-tick states), my tower HP lost,
tower falls, 3-crown loss, and a RUN-OVER proxy (fall <= 20 s after the enemy first stood on my half in that lane, quiet gap
60 ticks; no push-value threshold, so it over-counts cheap chains).

M4 state (every tick % 10 == 0): some tower of mine lost HP within +-20 ticks, an enemy body within 8 tiles of it, a card in my
hand other than X-Bow/Rocket with cost <= floor(elixir), and no accepted card play of mine in [t-30, t+10]. Consecutive states of
the same tower <= 30 ticks apart merge; duration = (t1 - t0)/20 + 0.5; STRICT = duration x (share of states holding a 3+ elixir
card) >= 2 s.
"""
import bisect
import math
from collections import defaultdict

from .dataset_gen import card_key
from .opp_elixir_count import card_cost

NO_IDLE = ('x-bow', 'rocket')


def metrics(frames, plays, side):
    fr = [f for f in frames if side in f.get('elixir', {})]
    if len(fr) < 20:
        return {}
    ticks = [f['tick'] for f in fr]
    towers = defaultdict(dict)                       # (kind, round x) -> {frame index: hp}
    pos = {}
    seen = set()
    for i, f in enumerate(fr):
        mine = {(t['kind'], round(t['x'] / 100)): t for t in f['towers'] if t['side'] == side}
        for k, t in mine.items():
            towers[k][i] = float(t['hp']); pos[k] = (t['x'], t['y']); seen.add(k)
        for k in seen - set(mine):
            towers[k][i] = 0.0
    series = {k: [towers[k].get(i, 0.0 if k in seen else None) for i in range(len(fr))] for k in towers}
    # forward-fill missing as the previous value (a tower in the list keeps its hp)
    for k, v in series.items():
        last = None
        for i, x in enumerate(v):
            if x is None: v[i] = last
            else: last = x
    idx = lambda t: max(0, bisect.bisect_right(ticks, t) - 1)
    hp = lambda k, t: series[k][idx(t)]
    out = {}
    first = {k: next((v for v in s if v is not None), 0.0) for k, s in series.items()}
    lost = sum(max(0.0, first[k] - (series[k][-1] or 0.0)) for k in series)
    fall = {}
    for k, s in series.items():
        for i, x in enumerate(s):
            if x is not None and x <= 0 and first[k] > 0:
                fall[k] = ticks[i]; break
    kings = [k for k in series if k[0] == 'king']
    out.update(hp_lost=round(lost, 1), falls=len(fall), king_fell=int(any(k in fall for k in kings)))
    # ---- M4
    my_plays = sorted(q['tick'] for q in plays if q['side'] == side and not q.get('ability'))
    has_play = lambda a, b: bisect.bisect_right(my_plays, b) > bisect.bisect_left(my_plays, a)
    runs, cur = [], None
    for i, f in enumerate(fr):
        t = f['tick']
        if t % 10: continue
        hurt = None
        for k in series:
            a, b = hp(k, t - 20), hp(k, t + 20)
            if a is not None and b is not None and a - b > 0:
                px, py = pos[k]
                if any(bd['side'] != side and bd['hp'] > 0 and math.hypot(bd['x'] - px, bd['y'] - py) <= 8000 for bd in f['bodies']):
                    hurt = k; break
        el = int(f['elixir'][side])
        keys = [card_key(n) for n in f['hand'].get(side, [])]
        costs = [card_cost(c) for c in keys if c and c not in NO_IDLE]
        aff = [c for c in costs if c is not None and c <= el]
        if hurt and aff and not has_play(t - 30, t + 10):
            strong = any(c >= 3 for c in aff)
            if cur and t - cur['t1'] <= 30 and cur['k'] == hurt:
                cur['t1'] = t; cur['n'] += 1; cur['ns'] += strong
            else:
                cur = dict(k=hurt, t0=t, t1=t, n=1, ns=int(strong)); runs.append(cur)
        elif cur and t - cur['t1'] > 30:
            cur = None
    allr = strict = 0; secs = 0.0; hpr = 0.0
    for r in runs:
        dur = (r['t1'] - r['t0']) / 20.0 + 0.5
        if dur < 2.0: continue
        allr += 1
        if dur * r['ns'] / r['n'] >= 2.0:
            strict += 1; secs += dur * r['ns'] / r['n']
            hpr += max(0.0, (hp(r['k'], r['t0']) or 0.0) - (hp(r['k'], r['t1'] + 20) or 0.0))
    out.update(m4_all=allr, m4_strict=strict, m4_strict_s=round(secs, 2), m4_strict_hp=round(hpr, 1))
    # ---- run-over proxy
    if kings:
        ky = pos[kings[0]][1]
        kx = pos[kings[0]][0]
        ro = 0; slow = 0
        for k, tf in fall.items():
            lane = None if k[0] == 'king' else (pos[k][0] < kx)
            j = idx(tf); present = []
            for i in range(j + 1):
                f = fr[i]
                present.append(any(bd['side'] != side and bd['hp'] > 0 and abs(bd['y'] - ky) <= 13000
                                   and (lane is None or (bd['x'] < kx) == lane) for bd in f['bodies']))
            start = tf; last_present = None
            for i in range(j, -1, -1):
                if present[i]:
                    if last_present is None or last_present - ticks[i] <= 60:
                        start = ticks[i]; last_present = ticks[i]
                    else:
                        break
            if (tf - start) / 20.0 <= 20.0: ro += 1
            else: slow += 1
        out.update(runover_falls=ro, slow_falls=slow)
    return out
