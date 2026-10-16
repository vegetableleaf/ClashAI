"""Own Log hit set, live vs SIM, body by body (paired as fights.measure pairs). usage: logset.py OUT.jsonl [glob] [stride]
Hit = a single-frame hp drop equal to the Log's damage, or that damage plus one common other hit (tower/X-Bow/Knight...),
inside [log tick, log tick + 70]."""
import json, math, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import capture, F, ps

MULT = [100, 110, 121, 133, 146, 160, 176, 193, 212, 233, 256, 281, 309, 339, 372, 409]   # common scale, level 1..16
OTHER = {0, 98, 158, 118, 130, 323, 351, 4, 5, 6, 7, 8, 51}
out = open(sys.argv[1], 'w')
paths = sorted(ps.LIVE.glob(sys.argv[2] if len(sys.argv) > 2 else 'live_play_2026101[5-9]_*.jsonl'))[::int(sys.argv[3]) if len(sys.argv) > 3 else 1]


def pairing(rows, setup, catalog):
    pairs = {}
    _, live0, sim0 = rows[0]
    free = [s for s in sim0 if not s['tower']]
    for a in setup:
        c = [(math.hypot(a['x']-s['x'], a['y']-s['y']), s['id']) for s in free if s['side'] == a['side']]
        if c and min(c)[0] < 60:
            pairs[a['id']] = min(c)[1]; free = [f for f in free if f['id'] != min(c)[1]]
    for tick, live, simb in rows:
        F.pair_frame(pairs, live, simb, catalog)
    return pairs


def hits(series, t_lo, dmg, t_end):
    """series [(tick, hp)] -> first tick with a drop == dmg (+ one other hit), or of a vanishing (killed) body whose last
    hp was within dmg + 160, inside [t_lo, t_lo+70]; else None"""
    for (ta, a), (tb, b) in zip(series, series[1:]):
        if t_lo <= tb <= t_lo + 70 and (a - b - dmg) in OTHER and a - b >= dmg:
            return tb
    t, h = series[-1]
    if t_lo - 2 <= t <= t_lo + 70 and t < t_end - 4 and h <= dmg + 160:
        return t + 1
    return None


for p in paths:
    m, why = F.read_match(str(p))
    if not m:
        continue
    ctx = __import__('capture').setup(p.stem)
    side = ctx['m']['side']
    res, _ = capture(p.stem, lambda f, a: a['name'] == 'Log' and a['side'] == side and a['source'] == 'own_spell_tap+delay', ctx)
    lv_sim = ctx['levels'].get((side, 'Log')) or ctx['levels'][side, '*']
    d_sim = 105*MULT[lv_sim-1]//100
    if d_sim != 390 and not os.environ.get("DIAG_FIGHTS"):   # Log level not inferable here (no exact 390 drop): skip
        continue
    cat = ctx['catalog']
    for f, a, rows, setup, r in res:
        if not rows:
            continue
        pairs = pairing(rows, setup, cat)
        tL = a['tick']; fwd = -1 if side == 1 else 1
        L, S = {}, {}
        for t, live, simb in rows:
            for b in live:
                if not b['tower'] and b['side'] != side: L.setdefault(b['id'], []).append((t, b['hp'], b['x'], b['y'], b['card_id']))
            for b in simb:
                if not b['tower'] and b['side'] != side: S.setdefault(b['id'], []).append((t, b['hp'], b['x'], b['y']))
        for lid, ser in L.items():
            if ser[0][0] > tL + 40 or ser[-1][0] < tL:      # not on the board while the Log rolls
                continue
            c = cat.get(ser[-1][4], {})
            sid = pairs.get(lid); ss = S.get(sid, [])
            hl = hits([(t, h) for t, h, *_ in ser], tL, 390, rows[-1][0])
            hs = hits([(t, h) for t, h, *_ in ss], tL, d_sim, rows[-1][0]) if ss else None
            at = min(ser, key=lambda q: abs(q[0]-tL)); sat = min(ss, key=lambda q: abs(q[0]-tL)) if ss else None
            # position when the live roll reached it (or at tL): lateral |dx| and along-roll distance from the tap
            out.write(json.dumps(dict(match=p.stem, t0=f['t0'], tL=tL, log=[a['x'], a['y']], name=c.get('display_name'), card=ser[-1][4],
                                      paired=bool(ss), live_hit=hl, sim_hit=hs, d_sim=d_sim, flags=r.get('flags', {}),
                                      live_at=[at[0], at[2], at[3]], sim_at=[sat[0], round(sat[2]), round(sat[3])] if sat else None,
                                      live_traj=[(t, x, y, h) for t, h, x, y, _ in ser if tL-10 <= t <= tL+70],
                                      sim_traj=[(t, round(x), round(y), h) for t, h, x, y in ss if tL-10 <= t <= tL+70],
                                      fwd=fwd))+'\n')
    out.flush()
    print(p.stem, len(res), flush=True)
