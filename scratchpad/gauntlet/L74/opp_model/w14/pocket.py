"""W14 post-princess-fall cells (owner 10-21), live Ranked (CLX's 233) vs SIM rows that carry o3_pos / o3_trace
(w14/pos_patch.py v2). One frame on both sides: OUR frame in tiles, river y 16, OUR half = y > 16 (invlib.live_matches'
frame: own king y 29).
  (a) pocket share: of the opponent's troop / building deploys AFTER our first princess fell, the share placed on our half
      at y >= POCKET_Y (1.5 tiles past the river). Before a fall that area is illegal for troops, so the same share BEFORE
      the fall is the detection / rule floor. Excluded everywhere: spells and the anywhere-deployers (Miner, Goblin Drill).
  (b) pocket deploys per minute after the fall.
  (c) our KING's HP lost after the fall, per minute and per match (princess units; NOT attributed to pocket units --
      neither side tracks which unit dealt it), and P(our king falls | our princess fell).
  (d) our SURVIVING princess's HP lost after the first fall, per minute and per match (princess units).
  (e) X-Bow locks by crown state at placement (0-0 / 1-0 / 0-1 / 1-1 = our crowns - theirs): lock rate per X-Bow placed and
      locks per minute of time in that state. Lock = enemy tower HP lost >= 5% of a princess while the X-Bow lived
      (live: invlib.xbow_rows, towers in reach; SIM: HP lost by the tower an X-Bow targeted, from o3_trace).
Live clock = game tick - 78; SIM tick = clock. Deploys are not independent: the shares carry Wilson CIs on deploys (too
narrow) and the per-match share of matches with >= 1 pocket deploy.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w14/pocket.py [SIM_ROOT ...]"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[1]
sys.path[:0] = [str(HERE), str(L74 / 'investment'), str(L74 / 'clx_ranked')]
import o4r_table as T  # noqa: E402
import invlib as I  # noqa: E402
import anatomy as A  # noqa: E402

H = T.AN.H
POCKET_Y = 17.5
ANYWHERE = {'miner', 'goblin_drill'}
STATES = ('0-0', '1-0', '0-1', '1-1')
MIN = 1200.0                      # ticks per minute


def troop(card):
    k = H.norm(card)
    return k not in ANYWHERE and H.kind(k) not in (None, 'spell')


def blank():
    return dict(n=0, pre_n=0, pre_pocket=0, post_n=0, pocket=0, post_min=0.0, m_fell=0, m_pocket=0, king=0.0, king_fell=0,
                surv=0.0, xb=defaultdict(lambda: [0, 0]), st_min=defaultdict(float))


def add_match(acc, deploys, t_fall, end, king_loss, surv_loss, king_fell, xbows, state_ticks):
    """deploys: opponent troop deploys [(tick, y_our_frame)]; t_fall: our first princess fall tick or None."""
    acc['n'] += 1
    for t, y in deploys:
        if t_fall is None or t < t_fall:
            acc['pre_n'] += 1
            acc['pre_pocket'] += y >= POCKET_Y
        else:
            acc['post_n'] += 1
            acc['pocket'] += y >= POCKET_Y
    if t_fall is not None:
        acc['m_fell'] += 1
        acc['post_min'] += max(0, end - t_fall) / MIN
        acc['m_pocket'] += any(t >= t_fall and y >= POCKET_Y for t, y in deploys)
        acc['king'] += king_loss
        acc['surv'] += surv_loss
        acc['king_fell'] += king_fell
    for st, lock in xbows:
        acc['xb'][st][0] += 1
        acc['xb'][st][1] += bool(lock)
    for st, ticks in state_ticks.items():
        acc['st_min'][st] += ticks / MIN


def state(oc, tc):
    return f'{min(oc, 1)}-{min(tc, 1)}'


# ---------------------------------------------------------------------------------------------------------- live
def live():
    keep, _, _ = A.load()
    rk = {n: v for n, v in keep.items() if v['sample'] == 'ranked'}
    sub = HERE / '_index_ranked.json'
    json.dump({n: dict(mark=v['mark'], result=v['result'], tro=v['tro']) for n, v in rk.items()}, open(sub, 'w'))
    acc = blank()
    try:
        for m in I.live_matches({'CLX'}, index=sub):
            fr = m['frames']
            pm = m['tmax'].get(('own', 'L')) or 1
            t_fall = slot = None
            for t, Tw, *_ in fr:
                down = [s for s in 'LR' if ('own', s) in m['tmax'] and Tw.get(('own', s), 0) <= 0]   # missing = destroyed
                if down:
                    t_fall, slot = t, down[0]
                    break
            dep = [(p['tick'], p['y']) for p in m['opp'] if p['y'] is not None and troop(p['card'])]
            king = surv = 0.0
            kf = 0
            if t_fall is not None:
                a, b = I._tower_at(m, t_fall), I._tower_at(m, m['end'])
                king = max(0, a.get(('own', 'K'), 0) - b.get(('own', 'K'), 0)) / pm
                o = 'R' if slot == 'L' else 'L'
                surv = max(0, a.get(('own', o), 0) - b.get(('own', o), 0)) / pm
                kf = b.get(('own', 'K'), 1) <= 0
            xb = [(state(r['our_cr'], r['their_cr']), r.get('lock')) for r in I.xbow_rows(m) if 'lock' in r]
            st = defaultdict(int)
            for (t0, *_), (t1, *_) in zip(fr, fr[1:]):
                st[state(*I.crowns(m, t0))] += t1 - t0
            add_match(acc, dep, t_fall, m['end'], king, surv, kf, xb, st)
    finally:
        sub.unlink()
    return acc


# ----------------------------------------------------------------------------------------------------------- SIM
def sim_match(j):
    pos, tr = j.get('o3_pos'), j.get('o3_trace')
    if pos is None or tr is None or not tr.get('snaps'):
        return None
    me = int(j['learner_side'])
    mine = [p for p in pos if p[1] == me and troop(p[2])]
    flip = sum(p[4] for p in mine) / max(1, len(mine)) < 16000      # our troops sit on OUR half: make it y > 16
    yo = (lambda y: (32000 - y) / 1000) if flip else (lambda y: y / 1000)
    dep = [(p[0], yo(p[4])) for p in pos if p[1] != me and troop(p[2])]
    towers = {int(u): v for u, v in tr['towers'].items()}
    pmax = next((v[2] for v in towers.values() if v[0] == me and v[1] in (1, 2)), 1)
    snaps = []
    for t, tw, xb in tr['snaps']:
        hp = {u: 0 for u in towers}
        hp.update({int(u): h for u, h in tw})                          # a tower missing from a snap is destroyed
        snaps.append((t, hp, xb))
    own_p = [u for u, v in towers.items() if v[0] == me and v[1] in (1, 2)]
    opp_p = [u for u, v in towers.items() if v[0] != me and v[1] in (1, 2)]
    king = next((u for u, v in towers.items() if v[0] == me and v[1] == 0), None)
    t_fall = surv_u = None
    for t, hp, _ in snaps:
        d = [u for u in own_p if hp[u] <= 0]
        if d:
            t_fall, surv_u = t, next((u for u in own_p if u != d[0]), None)
            break
    end = int(j['end_tick'])
    k_loss = s_loss = 0.0
    kf = 0
    if t_fall is not None:
        a = next(hp for t, hp, _ in snaps if t >= t_fall)
        b = snaps[-1][1]
        k_loss = max(0, a[king] - b[king]) / pmax if king is not None else 0.0
        s_loss = max(0, a[surv_u] - b[surv_u]) / pmax if surv_u is not None else 0.0
        kf = int(j['crowns_against']) >= 3 or (king is not None and b[king] <= 0)
    cr = lambda hp: (sum(hp[u] <= 0 for u in opp_p), sum(hp[u] <= 0 for u in own_p))  # noqa: E731
    born, dmg = {}, defaultdict(float)
    st = defaultdict(int)
    for (t0, hp0, xb0), (t1, hp1, _) in zip(snaps, snaps[1:]):
        st[state(*cr(hp0))] += t1 - t0
        for uid, team, _, tgt in xb0:
            if team != me:
                continue
            born.setdefault(uid, state(*cr(hp0)))
            if tgt in towers and towers[tgt][0] != me:
                dmg[uid] += max(0, hp0.get(tgt, 0) - hp1.get(tgt, 0)) / pmax
    for _, hp, xb in snaps[-1:]:
        for uid, team, *_ in xb:
            if team == me:
                born.setdefault(uid, state(*cr(hp)))
    xbows = [(s, dmg[u] >= I.LOCK_MIN) for u, s in born.items()]
    return dep, t_fall, end, k_loss, s_loss, kf, xbows, st


def sim(root):
    out = {}
    for name, raw in sorted(T.load_sim(root).items()):
        acc = blank()
        for j in raw:
            r = sim_match(j)
            if r is not None:
                add_match(acc, *r)
        if acc['n']:
            out[name] = acc
    return out


def show(name, a):
    f = lambda k, n: T.AN.fmt(k, n)  # noqa: E731
    print(f'\n== {name}: {a["n"]} matches; our first princess fell in {a["m_fell"]}')
    print(f'  (a) pocket share of opp troop deploys AFTER the fall: {f(a["pocket"], a["post_n"])}; BEFORE (floor): '
          f'{f(a["pre_pocket"], a["pre_n"])}; matches with >= 1 pocket deploy: {f(a["m_pocket"], a["m_fell"])}')
    print(f'  (b) pocket deploys per minute after the fall: {a["pocket"] / max(1e-9, a["post_min"]):.2f} '
          f'(post-fall time {a["post_min"]:.0f} min)')
    print(f'  (c) our king HP lost after the fall: {a["king"] / max(1e-9, a["post_min"]):.3f} princess/min, '
          f'{a["king"] / max(1, a["m_fell"]):.3f} per match; P(king falls | princess fell) {f(a["king_fell"], a["m_fell"])}')
    print(f'  (d) surviving princess HP lost after the fall: {a["surv"] / max(1e-9, a["post_min"]):.3f} princess/min, '
          f'{a["surv"] / max(1, a["m_fell"]):.3f} per match')
    print('  (e) X-Bow locks by crown state (ours-theirs): ' + ' | '.join(
        f'{s}: {f(a["xb"][s][1], a["xb"][s][0])}, {a["xb"][s][1] / max(1e-9, a["st_min"][s]):.2f} locks/min '
        f'({a["st_min"][s]:.0f} min)' for s in STATES))


def main():
    show('LIVE Ranked (CLX)', live())
    for root in sys.argv[1:]:
        for name, a in sim(root).items():
            show('SIM ' + name, a)


if __name__ == '__main__':
    main()
