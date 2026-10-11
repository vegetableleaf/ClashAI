"""Public match-event contract, shared by SIM, reader and pro recording adapters.

Coordinates use the policy's own-side-at-bottom frame. Time is match seconds.
Kind 0 is padding; missing position/HP is -1. No private player block is read.
The archive permits causal replay queries; only the newest `cap` events are tokens.
"""
from __future__ import annotations

import bisect
import math
import numpy as np

DEFAULT_CAP = 256
COLS = ('kind', 'side', 'card', 'form', 'x', 'y', 'time', 'hp', 'delta', 'tower')
PLAY, TOWER_HP, TOWER_DEATH, SPELL_LANDING, ABILITY = range(1, 6)


class PublicHistory:
    def __init__(self):
        self.events = []
        self.ticks = []
        self.seen = set()
        self.towers = {}
        self.tower_positions = {}
        self.effects = {}

    def add(self, kind, *, tick, side, card='', form=0, x=-1, y=-1,
            hp=-1, delta=0, tower=0):
        # Explicit allowlist: callers cannot smuggle arbitrary observation fields.
        from .dataset_gen import card_key
        card = card_key(card) if card else ''
        values = (int(kind), int(side), str(card or ''), int(form), float(x), float(y),
                  int(tick), float(hp), float(delta), int(tower))
        if kind not in range(1, 6) or side not in (0, 1) or form not in range(4) or not all(
                math.isfinite(v) for i, v in enumerate(values) if i != 2):
            raise ValueError('invalid public event')
        if values in self.seen:
            return
        self.seen.add(values)
        index = bisect.bisect_left(self.ticks, int(tick))
        order = lambda e: (e[6], e[0], e[1], e[2], e[4], e[5])
        while index < len(self.events) and order(self.events[index]) <= order(values):
            index += 1
        self.ticks.insert(index, int(tick))
        self.events.insert(index, values)

    def plays(self, events):
        for e in events:
            if e.get('accepted', True) and not e.get('ability', False):
                self.add(PLAY, tick=e['tick'], side=e['side'], card=e['card'],
                         form=e.get('form', 0), x=e['x'], y=e['y'])

    def abilities(self, events, tick):
        for e in events:
            if e.get('ability') and e.get('accepted', False) and int(e['tick']) <= tick:
                self.add(ABILITY, tick=e['tick'], side=e['side'], card=e['card'], form=2)

    def frame(self, frame, *, source, tick):
        from .public_observation import public_frame
        from .opp_elixir_count import card_db
        rows = (frame.get('episode') or {}).get('crown_towers', frame.get('towers') or [])
        complete_towers = ('crown_towers' in (frame.get('episode') or {}) or 'towers' in frame or
                           (source == 'reader' and 'entities' in frame))
        if source == 'reader' and not rows:
            # Same public tower identification as live_mem.to_observe, without
            # touching its private own-player adapter.
            rows = [dict(side=e['side'], type='king' if abs(float(e['x'])-9000) < 1500 else 'princess',
                         x=e['x'], y=e['y'], hp=e['hp'], max_hp=e['max_hp'])
                    for e in frame.get('entities', []) if int(e.get('card_id', 0)) < 0 and e.get('kind') in (12, 13)]
        visible = set()
        for row in rows:
            if isinstance(row, dict):
                s, kind, x, y, hp, maximum = (row[k] for k in ('side', 'type', 'x', 'y', 'hp', 'max_hp'))
                dead = row.get('destroyed', False)
            else:
                s, kind, _, x, y, hp, maximum = row[:7]
                dead = False
            tower = 1 if kind == 'king' else (2 if x < 9000 else 3)
            key = (s, tower)
            visible.add(key)
            if s not in (0, 1) or (not dead and (maximum <= 0 or hp < 0)):
                continue  # unreadable but present is not a death
            hp = 0.0 if dead else float(hp) / maximum
            previous = self.towers.get(key)
            if previous is None or hp != previous:
                self.add(TOWER_HP, tick=tick, side=s, x=x, y=y, hp=hp,
                         delta=0 if previous is None else hp-previous, tower=tower)
                if hp == 0 and previous != 0:
                    self.add(TOWER_DEATH, tick=tick, side=s, x=x, y=y, hp=0, tower=tower)
            self.towers[key] = hp
            self.tower_positions[key] = (x, y)
        # Full coherent board exports remove dead towers. Match the existing
        # obs_contract tower-slot semantics, only for previously seen towers.
        if complete_towers:
            for (s, tower), previous in list(self.towers.items()):
                if (s, tower) not in visible and previous > 0:
                    x, y = self.tower_positions[s, tower]
                    self.add(TOWER_HP, tick=tick, side=s, x=x, y=y, hp=0, delta=-previous, tower=tower)
                    self.add(TOWER_DEATH, tick=tick, side=s, x=x, y=y, hp=0, tower=tower)
                    self.towers[s, tower] = 0.0
        # Only observed area effects certify landings. Projectile disappearance
        # is not proof of impact. Reuse the public schema/card normalization.
        f = dict(frame, projectiles=[])
        if source == 'native' and frame.get('public_objects') is not None:
            f['public_objects'] = dict(frame['public_objects'], projectiles=[])
        groups = {}
        for e in public_frame(f, source=source)['spells']:
            if card_db().kind(e['card']) == 'spell':
                groups.setdefault((e['side'], e['card']), []).append(e)
        for key, group in sorted(groups.items()):
            previous = self.effects.get(key)
            if previous is None or tick-previous > 100:
                self.add(SPELL_LANDING, tick=tick, side=key[0], card=key[1],
                         form=max(e['form'] for e in group),
                         x=sum(e['x'] for e in group)/len(group), y=sum(e['y'] for e in group)/len(group))
            self.effects[key] = tick

    def tokens(self, tick, side, gid, cap=DEFAULT_CAP):
        if isinstance(cap, bool) or int(cap) != cap or cap <= 0:
            raise ValueError('history cap must be a positive integer')
        end = bisect.bisect_left(self.ticks, int(tick))  # no same-tick target leakage
        selected = self.events[max(0, end-int(cap)):end]
        # Stable simultaneous-event ordering across adapters and ingestion order.
        selected = sorted(selected, key=lambda e: (e[6], e[0], e[1], e[2], e[4], e[5]))
        out = np.zeros((int(cap), len(COLS)), np.float32)
        for i, (kind, s, card, form, x, y, t, hp, delta, tower) in enumerate(selected):
            if x >= 0 and y >= 0:
                x, y = x/18000.0, 1-y/32000.0
                if side == 1:
                    x, y = 1-x, 1-y
            if side == 1 and tower in (2, 3):
                tower = 5-tower
            out[i] = kind, int(s != side), gid.get(card, 0), form, x, y, t*.05, hp, delta, tower
        return out


def canonical_config(cfg):
    if not cfg.get('history_events', False):
        return {k: v for k, v in cfg.items() if k not in ('history_events', 'history_cap')}
    return dict(cfg)


def mirror_history(events):
    """Left/right augmentation, preserving unknown positions and padding."""
    import torch
    out = events.clone()
    valid = (out[..., 0] > 0) & (out[..., 4] >= 0)
    out[..., 4] = torch.where(valid, 1-out[..., 4], out[..., 4])
    out[..., 9] = torch.where((out[..., 9] == 2) | (out[..., 9] == 3), 5-out[..., 9], out[..., 9])
    return out
