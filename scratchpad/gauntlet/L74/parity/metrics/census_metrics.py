"""J-ALL-CARDS live evidence census (W1, 10-20): one pass over the frame-logged live matches -> per match, the live
observations every engine metric J1-J8 is graded on, and per card how much evidence exists (METRICS.md section 3).

Engine-free except for card-table reads (Tornado radius / life, unit mass). Public reader values only; addresses are never
written (read_match hashes them per match). Any account counts here: a mechanic is a mechanic, whoever played it.

  python census_metrics.py OUT.json [--files GLOB] [--limit N]

Per match it records:
  plays     label -> count            (J1 fights, J5 deploy timing: one fight per play)
  casts     spell label -> count      (J2)
  tornado   one row per (Tornado cast, enemy body inside its radius at the cast): victim label, mass, live pull (tiles)
  king      per side: awake tick (kind 12 -> 13), trigger tick (awake - wake delay), cause, activators, own Tornado before
  deploy    label -> {live deploy ticks: count}  (first seen deploying -> first active)
  bridge    label -> [ticks from birth to the river crossing]   (J6)
  levels    (card label, level, max_hp) -> frames              (static check vs the SIM at the observed level)
  end       the end event's crowns / tick + last frame tick     (J8)
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

FORMS = ('', ' evo', ' hero')
WAKE_TICKS = 70            # live: princess down -> king kind 13 is 70-71 ticks on 9 of 9 checked 10-19 matches (3.55 s)
KING_REACH = 7000 + 1400   # millitiles: king range 7 tiles + its radius (attribution of the activator only, not a law)
RIVER_LO, RIVER_HI = 14500, 17500


def label(side, own_side, c, cid):
    return ('own ' if side == own_side else 'opp ') + c['display_name'] + FORMS[F.form_of(cid, c)]


def own_princess(path):
    """The own princess max hp on the first frame (account signature) -> lets read_match take any account."""
    with open(path, 'rb') as f:
        for raw in f:
            if b'"frame"' in raw[:40]:
                j = json.loads(raw)
                hp = {e[5] for e in j['ents'] if e[3] == -1 and e[0] == j['my_side'] and e[6] == 13 and abs(e[1]-9000) > 1000}
                return max(hp) if hp else None
    return None


def raw_levels(path, catalog, side):
    """(label, level, max_hp) -> frames, from ents_state (ext logs only)."""
    out = Counter()
    with open(path, 'rb') as f:
        for raw in f:
            if b'"frame"' not in raw[:40] or b'ents_state' not in raw:
                continue
            j = json.loads(raw)
            for e, s in zip(j['ents'], j['ents_state']):
                if e[3] == -1:
                    out[('tower ' + ('own' if e[0] == side else 'opp') + (' king' if abs(e[1]-9000) < 1000 else ' princess'),
                         s[2], e[5])] += 1
                    continue
                c = catalog.get(e[3])
                if c and e[5] > 0:
                    out[(label(e[0], side, c, e[3]), s[2], e[5])] += 1
    return out


def one(path, eng, catalog):
    pr = own_princess(path)
    F.OWN_PRINCESS_MAX = pr          # any account (read_match's main-account gate is for the icebow fights only)
    m, reason = F.read_match(path)
    if m is None:
        return dict(match=Path(path).stem, skipped=reason)
    side = m['side']
    events, _ = F.deployments(m, catalog, eng.effect_life, own_unit=lambda n, hp: eng.level(n, hp) is not None, stats=eng.stats)
    rec = dict(match=m['match'], side=side, own_princess=pr, ext=bool(m['ext']), t_first=m['frames'][0][0], t_last=m['frames'][-1][0],
               own_cards=sorted({p['name'] for p in m['plays']}))
    plays, casts = Counter(), Counter()
    for ev in events:
        if ev['kind'] != 'play':
            continue
        lab = ('own ' if ev['side'] == side else 'opp ') + ev['name'] + FORMS[ev.get('form') or 0]
        plays[lab] += 1
        if ev['source'] in F.SPELL_SOURCES:
            casts[lab] += 1
    rec['plays'], rec['casts'] = dict(plays), dict(casts)
    ticks = [t for t, _ in m['frames']]
    byt = dict(m['frames'])
    # ---- J2 Tornado exposures (live side)
    tst = eng.stats('Tornado')
    R = ((tst.get('spell') or {}).get('radius_milli')) or 5500
    life = (eng.effect_life('Tornado') or 1050) // 50
    torn = []
    for ev in events:
        if ev['kind'] != 'play' or ev['name'] != 'Tornado' or ev['source'] not in F.SPELL_SOURCES:
            continue
        i = bisect_left(ticks, ev['tick'])
        if i >= len(ticks):
            continue
        t0 = ticks[i]
        j = bisect_left(ticks, ev['tick'] + life)
        if j >= len(ticks):
            continue
        t1 = ticks[j]
        later = {b['id']: b for b in byt[t1] if not b['tower']}
        for b in byt[t0]:
            c = catalog.get(b['card_id'])
            if b['tower'] or b['side'] == ev['side'] or c is None or c.get('type') == 'spell':
                continue
            d0 = math.hypot(b['x']-ev['x'], b['y']-ev['y'])
            if d0 > R + 500:
                continue
            e1 = later.get(b['id'])
            d1 = math.hypot(e1['x']-ev['x'], e1['y']-ev['y']) if e1 else None
            st = eng.stats(c['display_name'])
            torn.append(dict(t=t0, caster='own' if ev['side'] == side else 'opp', victim=label(b['side'], side, c, b['card_id']),
                             mass=st.get('mass'), flying=bool(st.get('flying_height')), d0=round(d0), d1=None if d1 is None else round(d1),
                             pull=None if d1 is None else round(d0 - d1), dt=t1 - t0))
    rec['tornado'] = torn
    # ---- J3 king activation
    king = []
    for s_ in (0, 1):
        awake = down = hurt = None
        prin = {f'T{s_}L', f'T{s_}R'}
        seen_p = set()
        for t, bodies in m['frames']:
            tw = {b['id']: b for b in bodies if b['tower']}
            k = tw.get(f'T{s_}K')
            if k is not None:
                if awake is None and k['kind'] == 13:
                    awake = t
                if hurt is None and 0 < k['hp'] < k['max_hp']:
                    hurt = t
            for p in prin:
                if p in tw and tw[p]['hp'] > 0:
                    seen_p.add(p)
                elif p in seen_p and down is None:
                    down = t
        if awake is None:
            king.append(dict(side='own' if s_ == side else 'opp', awake=None, down=down, hurt=hurt))
            continue
        trig = awake - WAKE_TICKS
        cause = 'at_start' if awake <= m['frames'][0][0] + 2 else \
            'princess' if down is not None and abs(down - trig) <= 4 else \
            'damage' if hurt is not None and abs(hurt - trig) <= 4 else 'other'
        acts = []
        i = bisect_left(ticks, trig)
        if 0 <= i < len(ticks) and cause in ('damage', 'other'):
            kx, ky = 9000, (3000 if s_ == 0 else 29000)
            for b in byt[ticks[i]]:
                c = catalog.get(b['card_id'])
                if not b['tower'] and b['side'] != s_ and c and math.hypot(b['x']-kx, b['y']-ky) <= KING_REACH:
                    acts.append(label(b['side'], side, c, b['card_id']))
        tb = [ev['tick'] for ev in events if ev['name'] == 'Tornado' and ev['side'] == s_ and trig - 80 <= ev['tick'] <= trig]
        king.append(dict(side='own' if s_ == side else 'opp', awake=awake, trigger=trig, cause=cause, down=down, hurt=hurt,
                         activators=sorted(set(acts)), tornado_before=tb[-1] if tb else None))
    rec['king'] = king
    # ---- J5 deploy, J6 bridge
    dep, bridge = defaultdict(Counter), defaultdict(list)
    for r in F.tracks(m['frames']).values():
        c = catalog.get(r['card_id'])
        if c is None or r['first'] <= rec['t_first'] + 2:
            continue
        lab = label(r['side'], side, c, r['card_id'])
        k0 = next(b['kind'] for b in byt[r['first']] if b.get('id') == r['id'])
        if k0 in (12, 14) and r['active'] is not None:
            dep[lab][r['active'] - r['first']] += 1
        fwd = 1 if r['side'] == 0 else -1
        ys = [(t, y*fwd) for t, _, y in r['traj']]
        lo, hi = (RIVER_LO, RIVER_HI) if fwd == 1 else (-RIVER_HI, -RIVER_LO)
        if ys[0][1] < lo:
            cross = next((t for t, y in ys if y > hi), None)
            if cross is not None:
                bridge[lab].append(cross - r['first'])
    rec['deploy'] = {k: dict(v) for k, v in dep.items()}
    rec['bridge'] = dict(bridge)
    rec['levels'] = [list(k) + [v] for k, v in raw_levels(path, catalog, side).items()] if m['ext'] else []
    # ---- J8 end
    end = None
    with open(path, 'rb') as f:
        for raw in f:
            if b'"end"' in raw[:30]:
                end = (json.loads(raw).get('towers') or {})
    last = {b['id']: max(0, b['hp']) for b in m['frames'][-1][1] if b['tower']}
    rec['end'] = dict(end or {}, last_frame=m['frames'][-1][0], tower_hp_last=last)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--files', default='live_play_2026101[5-9]_*.jsonl,live_play_2026102*.jsonl')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    paths = sorted({p for g in a.files.split(',') for p in F.ps.LIVE.glob(g)})
    if a.limit:
        paths = paths[:a.limit]
    catalog, _ = F.load_catalog()
    eng = F.Engine()
    done = {}
    if a.out.exists():                      # resumable
        done = {r['match']: r for r in json.loads(a.out.read_text())['matches']}
    t = time.monotonic()
    for n, p in enumerate(paths, 1):
        if p.stem in done:
            continue
        try:
            done[p.stem] = one(str(p), eng, catalog)
        except Exception as e:                   # one bad log must not drop the census
            done[p.stem] = dict(match=p.stem, crash=type(e).__name__ + ':' + str(e)[:200])
        if n % 200 == 0:
            a.out.write_text(json.dumps(dict(stamp=eng.stamp, matches=list(done.values()))))
            print(f'{n}/{len(paths)} {time.monotonic()-t:.0f}s', flush=True)
    a.out.write_text(json.dumps(dict(stamp=eng.stamp, matches=list(done.values()))))
    print(f'{len(done)} logs, {sum("skipped" in r for r in done.values())} skipped, '
          f'{sum("crash" in r for r in done.values())} crashed, {time.monotonic()-t:.0f}s -> {a.out}')


if __name__ == '__main__':
    main()
