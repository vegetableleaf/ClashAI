"""SCALE-only public area age. No source timers, player blocks or engine IDs enter a model."""
from bisect import bisect_right
from collections import Counter

import numpy as np
import torch


def add_richer_inputs(batch, age=None, *, richer_inputs=False):
    if not richer_inputs:
        return batch  # no copy, dtype conversion, random draw, or tensor mutation
    if age is None or tuple(age.shape) != (*batch['effects'].shape[:-1], 2):
        raise ValueError('Area observed-age channels are required')
    return dict(batch, effects=torch.cat((batch['effects'], age.to(batch['effects'])), -1))


def effect_key(card, enemy, x, y):
    return tuple(np.asarray([card, enemy, x, y], dtype=np.float32).tolist())


def public_area_timeline(frames, gid):
    """Causal continuous observed age; disappearance resets tracks, collisions mask age.

    IDs are only tracking/join keys, never numeric features. Times are observation
    ticks, never unvalidated source_elapsed/source_life/source_remaining fields.
    """
    from pipeline.obs_contract import catalog_card_form
    from pipeline import vocab
    from pipeline.projectile_observation import _xy
    tracks, result = {}, []
    previous_tick = -1
    # 20% of native recordings repeat a frame at the same tick (measured on pod E: 2,950 dups, 2,948 byte-identical,
    # 2 differ): keep the LATER frame per tick, then the strict-increase check below still guards real disorder.
    by_tick = {}
    for f in sorted(frames, key=lambda f: int(f['tick'])):
        by_tick[int(f['tick'])] = f
    for frame in by_tick.values():
        tick = int(frame['tick'])
        if tick <= previous_tick:
            raise ValueError('Native sampled frame ticks must increase strictly')
        previous_tick = tick
        objects = frame.get('public_objects', {}).get('area_effects')
        if objects is None:
            raise ValueError('Native area export missing; cannot silently drop D')
        identities = [(e.get('side'), e.get('card_id'), e.get('category'), e.get('id')) for e in objects]
        counts = Counter(identities)
        now, maps = {}, ({}, {})
        for e, identity in zip(objects, identities):
            name, _ = catalog_card_form(int(e.get('card_id', -1)))
            key = vocab.engine_key(name) if name else None
            card = gid.get(vocab.base_key(key).replace('_', '-'), 0) if key else 0
            owner = int(e['side'])
            if not card or owner not in (0, 1):
                continue
            known = e.get('id') is not None and counts[identity] == 1
            start = tracks.get(identity, tick)
            if known:
                now[identity] = start
            age = (min((tick - start) * .05 / 30., 1.), 1.) if known else (0., 0.)
            for side in (0, 1):
                x, y = _xy(e['x'], e['y'], side)
                k = effect_key(card, owner != side, x, y)
                maps[side][k] = (0., 0.) if k in maps[side] else age
        tracks = now
        result.append((tick, maps))
    return result


def align_area_age(timeline, ticks, sides, effects):
    times = [x[0] for x in timeline]
    out = np.zeros((*effects.shape[:-1], 2), np.float32)
    for row, (tick, side) in enumerate(zip(ticks, sides)):
        i = bisect_right(times, int(tick)) - 1
        lookup = timeline[i][1][int(side)] if i >= 0 else {}
        for j, effect in enumerate(effects[row]):
            if effect[0] == 0:
                continue
            k = tuple(effect[:4].tolist())
            if k not in lookup:
                raise ValueError(f'fv5 effect cannot join public sampled frame: row={row}, tick={tick}, effect={k}')
            out[row, j] = lookup[k]
    return out


def bridge_events(frames):
    """First sampled crossing of river at a bridge lane; per defending side.

    Follow the SAME living non-tower body over adjacent samples <=20 ticks apart.
    Bridge corridors x=2500..6500 or 11500..15500, river y=16000 native units.
    Reject jumps >2500 units. A push can contain one or more visible bodies.
    """
    prev, last_tick, events = {}, None, ([], [])
    for f in sorted(frames, key=lambda x: int(x['tick'])):
        tick, now = int(f['tick']), {}
        for e in f.get('entities', []):
            if isinstance(e, dict):
                side, x, y, name, hp, mhp, eid = (e[k] for k in ('side', 'x', 'y', 'name', 'hp', 'max_hp', 'entity_id'))
            else:
                if len(e) not in (8, 9):
                    raise ValueError('Unsupported native entity schema')
                side, x, y, name, hp, mhp = e[:6]
                eid = e[-1]
            if int(side) not in (0, 1) or str(name) == '-1' or (hp <= 0 and mhp > 0):
                continue
            key = (int(side), eid, str(name))
            now[key] = (float(x), float(y))
            old = prev.get(key)
            if old is None or last_tick is None or not 0 < tick-last_tick <= 20:
                continue
            if not (2500 <= x <= 6500 or 11500 <= x <= 15500):
                continue
            if (x-old[0])**2 + (y-old[1])**2 > 2500**2:
                continue
            defender = 1-int(side)
            crossed = old[1] > 16000 >= y if defender == 0 else old[1] < 16000 <= y
            if crossed:
                events[defender].append(tick)
        prev, last_tick = now, tick
    return tuple(np.unique(e) for e in events)


def bridge_mask(events, ticks, sides, window=20):
    out = np.zeros(len(ticks), bool)
    for s in (0, 1):
        ids = np.flatnonzero(np.asarray(sides) == s)
        if len(events[s]):
            j = np.searchsorted(events[s], np.asarray(ticks)[ids], side='right')-1
            out[ids] = (j >= 0) & (np.asarray(ticks)[ids]-events[s][j.clip(min=0)] <= window)
    return out
