"""Shared live-log reader for L74/habits: one pass over a live_play_*.jsonl -> frames rebuilt as reader dicts, own plays,
decisions, and the opponent's public plays from the SAME code the live model uses (pipeline.public_observation.
PublicObserver, fed every logged frame, dedupe_hero_bodies first, as live_gen.observe). Positions in the OWN frame, tiles:
own king y 29, enemy king y 3, river 16 (x mirrored with y so lanes stay consistent within a match).
Public reader values only; nothing here touches the live process."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline.public_observation import PublicObserver  # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies  # noqa: E402
from pipeline.opp_elixir_count import card_cost  # noqa: E402
from pipeline import vocab  # noqa: E402
from pipeline.obs_contract import catalog_card_form  # noqa: E402

TOWER_SLOTS = ((9000, 3000), (3500, 6500), (14500, 6500), (9000, 29000), (3500, 25500), (14500, 25500))
OWN_COST = {'Xbow': 6, 'Tesla': 4, 'IceWizard': 3, 'Tornado': 3, 'Rocket': 6, 'Knight': 3, 'Log': 2, 'Skeletons': 1}


def key_of(cid):
    name, form = catalog_card_form(int(cid))
    return (vocab.engine_key(name) if name else None), form


def kind_of(key, _c={}):
    if key not in _c:
        from pipeline.opp_elixir_count import card_db
        _c[key] = card_db().kind(key) if key else None
    return _c[key]


def cost_of(key):
    c = card_cost(key) if key else None
    return 3.0 if c is None else float(c)


def read(path):
    """-> dict(side, flip, frames=[(tick, ents, towers, opp_est_logged)], own=[plays], opp=[plays], dec=[...], end, start)
    ents: [(addr, side, X, Y, key, form, hp, max_hp)] own-frame tiles (towers excluded); towers: {('own'|'opp', 'K'|'L'|'R'): hp}
    own plays: dict(tick, name, x, y) (confirmed; tick = confirmation); opp plays: dict(tick, card, x, y, cost, kind) from the
    public observer (tick = first sighting), est = the rebuilt counter right before the play."""
    frames, own, dec, start, end = [], [], [], None, None
    pub, side, flip = None, None, None
    ests = []          # (tick, rebuilt estimate_at(tick), logged opp_elixir_est)
    with open(path, 'rb') as f:
        for raw in f:
            head = raw[:40]
            if b'"frame"' in head:
                j = json.loads(raw)
                if side is None:
                    side = j['my_side']
                tick = j['tick']
                st = j.get('ents_state') or []
                ents, towers = [], {}
                for i, e in enumerate(j['ents']):
                    s_, x, y, cid, hp, mx, kind, addr = e
                    if cid == -1 and any(abs(x - tx) < 600 and abs(y - ty) < 600 for tx, ty in TOWER_SLOTS):
                        if flip is None and s_ == side and abs(x - 9000) < 1000:
                            flip = y < 16000              # own king at low engine y -> rotate to the own frame
                        towers[(s_, x, y)] = hp
                        continue
                    d = dict(side=s_, x=x, y=y, card_id=cid, hp=hp, max_hp=mx, kind=kind, address=addr)
                    if i < len(st):
                        d['category'] = st[i][3]
                    ents.append(d)
                fr = dict(game_tick=tick, entities=ents,
                          projectiles=[dict(side=p[0], x=p[1], y=p[2], card_id=p[3], target_x=p[4], target_y=p[5])
                                       for p in j.get('proj') or []],
                          effects=[dict(side=e[0], x=e[1], y=e[2], card_id=e[3], remaining_ms=e[4]) for e in j.get('fx') or []])
                fr = dedupe_hero_bodies(fr)
                if pub is None:
                    pub = PublicObserver(side)
                est = pub.update(fr, source='reader')
                ests.append((tick, est, j.get('opp_elixir_est')))
                frames.append((tick, fr['entities'], towers))
            elif b'"decision"' in head:
                j = json.loads(raw)
                p = j.get('public') or {}
                d = j.get('decision') or {}
                dec.append(dict(tick=j['tick'], hand=[h.get('name') for h in p.get('own_hand', [])],
                                own_el=p.get('own_elixir_raw'), opp_est=p.get('opponent_elixir_estimate'),
                                play=d.get('play'), name=d.get('name'), xy=d.get('xy'), why=d.get('why'),
                                p_play=d.get('p_play')))
            elif b'"confirmed"' in head:
                j = json.loads(raw)
                own.append(dict(tick=j.get('tick') or 0, name=j.get('name'), sxy=j.get('intended')))
            elif b'"start"' in head and start is None:
                start = json.loads(raw)
            elif b'"end"' in head:
                end = json.loads(raw)
    if side is None:
        return None
    flip = bool(flip)

    def tr(x, y):          # engine millitiles -> own-frame tiles
        return ((18000 - x) / 1000, (32000 - y) / 1000) if flip else (x / 1000, y / 1000)

    for q in own:          # screen-normalised intended xy: own side at the bottom = own frame (x as the screen shows it)
        sx, sy = q['sxy'] or (None, None)
        q['y'] = None if sy is None else sy * 32
        # screen x -> own-frame x consistent with tr(): live_play maps screen (sx, sy) to engine via raw_xy(side, 18-sx*18, sy*32)
        if sx is None:
            q['x'] = None
        else:
            ex = (18 - sx * 18) * 1000 if side == 1 else (18 - (18 - sx * 18)) * 1000
            ey = sy * 32000 if side == 1 else (32 - sy * 32) * 1000
            q['x'] = tr(ex, ey)[0]
    out_frames = []
    for tick, ents, towers in frames:
        E = []
        for e in ents:
            k, form = key_of(e['card_id'])
            X, Y = tr(e['x'], e['y'])
            E.append((e['address'], 'own' if e['side'] == side else 'opp', X, Y, k, form, e['hp'], e['max_hp']))
        T = {}
        for (s_, x, y), hp in towers.items():      # slot by OWN-frame x: L = x < 9 (as every other position here)
            X = tr(x, y)[0]
            T[('own' if s_ == side else 'opp', 'K' if abs(X - 9) < 1 else 'L' if X < 9 else 'R')] = hp
        out_frames.append((tick, E, T))
    opp = []
    ests_t = [t for t, _, _ in ests]
    import bisect
    for p in pub.plays if pub else []:
        X, Y = tr(p['x'], p['y'])
        i = bisect.bisect_left(ests_t, p['tick']) - 1
        opp.append(dict(tick=p['tick'], card=p['card'], x=X, y=Y, cost=cost_of(p['card']), kind=kind_of(p['card']),
                        est_before=ests[i][1] if i >= 0 else None))
    return dict(side=side, flip=flip, frames=out_frames, own=own, opp=opp, dec=dec, end=end, start=start, ests=ests,
                counter=pub.counter if pub else None)


if __name__ == '__main__':
    import statistics
    m = read(sys.argv[1])
    d = [abs(a - b) for _, a, b in m['ests'] if b is not None]
    print('frames', len(m['frames']), 'flip', m['flip'], 'side', m['side'], 'opp plays', len(m['opp']),
          '| rebuilt vs logged counter: mean |diff|', round(statistics.fmean(d), 4), 'max', round(max(d), 3),
          'exact(<1e-6)', sum(x < 1e-6 for x in d), '/', len(d))
    for p in m['opp'][:12]:
        print('  opp', p)
    for q in m['own'][:8]:
        print('  own', q)
    print(m['frames'][300][2])
