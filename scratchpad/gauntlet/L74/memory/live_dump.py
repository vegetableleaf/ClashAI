"""Plan A S1a acceptance (b): match memories from RECORDED live matches (read-only; live_play.py is never imported or run).

    icebow/.venv/Scripts/python.exe -B -X utf8 scratchpad/gauntlet/L74/memory/live_dump.py [LOG ...] > live_dump.out

Default: the newest 5 complete logs in L68/live_reader. Inputs exactly as the live pilot has them (live_gen.observe /
record_play / record_ability): every logged reader frame -> dedupe_hero_bodies -> PublicObserver(side).update(source='reader')
(the opponent's public plays); towers = the frame's cid -1 bodies at the 6 tower slots (habits/livelog.py rule; a missing tower
= destroyed, as obs_contract._tower_slots); units = public_frame(frame, 'reader')['entities']; own elixir = the frame's
'elixir'; one sample per logged decision (latest frame at or before it); own plays = 'confirmed' (tick, intended own-frame
xy) + 'late_landing' (xy of the matching 'unconfirmed'); own presses = 'ability' tap tick, seen at its 'ability_confirmed'
(record_ability stamps the TAP tick when the press confirms). Built offline AND incrementally (one observe per decision):
the two must agree at every decision tick; the per-decision cost is timed."""
from __future__ import annotations

import bisect
import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline import match_memory as M  # noqa: E402
from pipeline.dataset_gen import card_key  # noqa: E402
from pipeline.obs_contract import _engine_xy  # noqa: E402
from pipeline.public_observation import PublicObserver, public_frame  # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies  # noqa: E402

LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
TOWER_SLOTS = ((9000, 3000), (3500, 6500), (14500, 6500), (9000, 29000), (3500, 25500), (14500, 25500))
DECK = ['Xbow', 'Tesla', 'IceWizard', 'Tornado', 'Rocket', 'Knight', 'Log', 'Skeletons']


def read(path):
    side, pub, frames, dec, own, taps, presses, unconf, start, end = None, None, [], [], [], [], [], {}, None, None
    for raw in open(path, 'rb'):
        head = raw[:40]
        if b'"frame"' in head:
            j = json.loads(raw)
            side = j['my_side'] if side is None else side
            st = j.get('ents_state') or []
            ents, tw = [], {}
            for i, e in enumerate(j['ents']):
                s_, x, y, cid, hp, mx, kind, addr = e
                if cid == -1 and any(abs(x - tx) < 600 and abs(y - ty) < 600 for tx, ty in TOWER_SLOTS):
                    tw[(s_, x, y)] = (hp, mx)
                    continue
                d = dict(side=s_, x=x, y=y, card_id=cid, hp=hp, max_hp=mx, kind=kind, address=addr)
                if i < len(st):
                    d['category'] = st[i][3]
                ents.append(d)
            fr = dedupe_hero_bodies(dict(
                game_tick=j['tick'], entities=ents,
                projectiles=[dict(side=p[0], x=p[1], y=p[2], card_id=p[3], target_x=p[4], target_y=p[5]) for p in j.get('proj') or []],
                effects=[dict(side=e[0], x=e[1], y=e[2], card_id=e[3], remaining_ms=e[4]) for e in j.get('fx') or []]))
            pub = pub or PublicObserver(side)
            pub.update(fr, source='reader')
            hp6, al6 = [0.0] * 6, [False] * 6
            for (s_, x, y), (hp, mx) in tw.items():
                i = 3 * int(s_ != side) + (0 if abs(x - 9000) < 1000 else 1 if _engine_xy(x, y, side == 1)[0] < .5 else 2)
                if hp > 0 and mx > 0:
                    hp6[i], al6[i] = hp / mx, True
            frames.append((j['tick'], tuple(hp6), tuple(al6), j.get('elixir'), public_frame(fr, source='reader')['entities']))
        elif b'"decision"' in head:
            dec.append(json.loads(raw)['tick'])
        elif b'"confirmed"' in head or b'"late_landing"' in head or b'"unconfirmed"' in head:
            j = json.loads(raw)
            if j['event'] == 'unconfirmed':
                unconf[j['name']] = j.get('intended')
                continue
            xy = j.get('intended') if j['event'] == 'confirmed' else unconf.get(j['name'])
            own.append(dict(tick=j['tick'], side=side, card=j['name'], accepted=True,
                            **(dict(zip('xy', M.engine_xy(xy[0], xy[1], side))) if xy else {})))
        elif head.startswith(b'{"event": "ability"'):
            taps.append(json.loads(raw)['tick'])
        elif b'"ability_confirmed"' in head:
            presses.append(dict(tick=taps[-1], seen=json.loads(raw)['tick'], side=side, card='IceWizard', ability=True))
        elif b'"start"' in head and start is None:
            start = json.loads(raw)
        elif b'"end"' in head:
            end = json.loads(raw)
    ft = [f[0] for f in frames]
    samples = []
    for td in sorted(set(dec)):
        i = bisect.bisect_right(ft, td) - 1
        if i >= 0 and (not samples or td > samples[-1]['tick']):
            _, hp6, al6, el, units = frames[i]
            samples.append(dict(tick=td, towers=hp6, alive=al6, elixir=el, units=units))
    return dict(side=side, samples=samples, plays=list(pub.plays) + own + presses, start=start, end=end,
                last=ft[-1] if ft else 0)


def line(e, t0):
    who = 'OWN' if e['mine'] else 'opp'
    s = f"{e['tick']:5d} {e['tick'] * .05:6.1f}s {who} "
    if 'tower' in e:
        tw = ('K', 'L', 'R')[e['tower'] % 3]
        return s + (f"tower_damage {tw} -{e['lost']:.3f}" if e['type'] == 'tower_damage' else f"tower_FALL {tw}") + \
            f"  crowns {e['crowns'][0]}-{e['crowns'][1]}"
    xy = f"({e['xy'][0]:.2f},{e['xy'][1]:.2f})" if e['xy'] else '(?)'
    s += f"{e['type']:7s} {e['card']:12s} {xy:12s} " + (f"el {e['el']:4.1f} " if e['el'] is not None else '        ')
    o = e.get('out')
    if o is None:
        s += '| out pending'
    else:
        tl = 'tow ?' if o['enemy_lost'] is None else f"tow +{o['enemy_lost']:.3f}/-{o['own_lost']:.3f}"
        s += f"| {tl} val {'?' if o['value'] is None else round(o['value'], 2)}"
    if 'reach' in e:
        xb = e.get('xb')
        s += f" | XB reach={bool(e['reach'])} " + ('' if not e['reach'] else 'pending' if xb is None else
                                                    ('LOCKED' if xb['locked'] else 'FAILED') + f" dmg {xb['damage']:.3f}")
        s += f" ans={e.get('answer')!r}"
    if e.get('is_answer'):
        s += ' [answers X-Bow]'
    if 'aim' in e:
        rk = e.get('rk')
        s += f" | RK aim={'tower' if e['aim'] is not None else 'troops'} " + (
            'pending' if rk is None else f"tow {rk['tower_lost']} val {None if rk['value'] is None else round(rk['value'], 2)} "
                                         f"combo={rk['combo']}")
    return s


def one(path):
    t0 = time.time()
    m = read(path)
    side, sm, plays = m['side'], m['samples'], m['plays']
    t_read = time.time() - t0
    gid = {k: i + 1 for i, k in enumerate(sorted({card_key(str(p['card'])) for p in plays} | {card_key(c) for c in DECK}))}
    off = M.build(side, sm, plays)
    inc, bad, t1 = M.MatchMemory(side), 0, time.time()
    for s in sm:
        td = s['tick']
        inc.observe(**s, plays=[p for p in plays if p['tick'] <= td and p.get('seen', p['tick']) <= td])
        a, b = inc.features(td, gid, DECK), off.features(td, gid, DECK)
        bad += not all((a[k] == b[k]).all() for k in a)
    ms = (time.time() - t1) / max(1, len(sm)) * 1e3
    T = m['last'] + 1
    ev = off.events(T)
    end = (m['end'] or {}).get('towers') or {}
    print(f"\n=== {path.name}  side {side}  ckpt {Path((m['start'] or {}).get('ckpt', '?')).name}  result "
          f"{'WIN' if end.get('won') else 'LOSS' if end else '?'} {end.get('crowns_me')}-{end.get('crowns_opp')}  "
          f"decisions {len(sm)}  read {t_read:.1f}s")
    print(f"incremental vs offline: {len(sm) - bad}/{len(sm)} decisions identical; late plays {inc.late}; "
          f"{ms:.2f} ms per decision (incremental observe + features, offline features, compare)")
    by = Counter((e['type'], e['mine']) for e in ev)
    print('events:', ', '.join(f"{'own' if mine else 'opp'} {k} {n}" for (k, mine), n in sorted(by.items())))
    pl = [e for e in ev if e['type'] in ('play', 'ability')]
    unk = Counter()
    for e in pl:
        unk['xy?'] += e['xy'] is None
        unk['el? (own)'] += e['mine'] and e['el'] is None
        unk['value? (resolved)'] += e['out'] is not None and e['out']['value'] is None
        unk['tower? (resolved)'] += e['out'] is not None and e['out']['enemy_lost'] is None
    print('unknown fields:', dict(unk))
    for e in ev[:40]:
        print('  ' + line(e, T))
    oxb = [e for e in pl if e['card'] == 'x-bow' and e['mine']]
    pxb = [e for e in pl if e['card'] == 'x-bow' and not e['mine']]
    rch = [e for e in oxb if e['reach']]
    lk = [e for e in rch if e.get('xb') and e['xb']['locked']]
    fl = [e for e in rch if e.get('xb') and not e['xb']['locked']]
    ans = Counter(e['answer'] or 'none' for e in oxb if e.get('answer') is not None)
    rks = [e for e in pl if e['card'] == 'rocket' and e['mine']]
    falls = [(('own' if e['mine'] else 'opp') + ' ' + 'KLR'[e['tower'] % 3], e['tick']) for e in ev if e['type'] == 'tower_fall']
    fin = ev[-1]['crowns'] if ev else (0, 0)
    print(f"HIGHLIGHTS: own X-Bows {len(oxb)} (reach {len(rch)}: locked {len(lk)}, failed {len(fl)}), answered by {dict(ans)}; "
          f"opp X-Bows {len(pxb)}; own Rockets {len(rks)} (tower {sum(e['aim'] is not None for e in rks)}, combo "
          f"{sum(bool(e.get('rk') and e['rk']['combo']) for e in rks)}); falls {falls}; memory crowns at the last event "
          f"{fin[0]}-{fin[1]} vs end {end.get('crowns_me')}-{end.get('crowns_opp')}")
    s, a = M.summary(ev, T, DECK, gid)
    inv = {v: k for k, v in gid.items()}
    print('SUMMARY:', ' '.join(f'{k}={v:.3f}' for k, v in zip(M.SUMMARY_FIELDS, s)), f'| answer card {inv.get(a, "none")}')
    blk = s[len(M.SUMMARY_FIELDS):].reshape(M.DECK_N, len(M.CARD_FIELDS))
    print('  per card:', ' | '.join(f"{c} n={round(b[0] * 10)} swing={b[2]:+.3f} vpe={b[4] * 2:.2f}" for c, b in zip(DECK, blk)))
    return bad


def main():
    paths = [Path(a) for a in sys.argv[1:]]
    if not paths:
        for p in sorted(LOGS.glob('live_play_2026102*.jsonl'), reverse=True):
            if p.stat().st_size > 2e6 and b'{"event": "end"' in p.read_bytes():
                paths.append(p)
            if len(paths) == 5:
                break
    bad = sum(one(p) for p in paths)
    print(f'\nall matches: incremental != offline at {bad} decisions')


if __name__ == '__main__':
    main()
