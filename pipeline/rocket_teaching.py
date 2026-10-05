"""

Thresholds describe owner-requested audit cohorts, not action targets. Expert
cards, locations and WAIT labels are preserved. Geometry is a conservative
centre-coverage proxy, not a simulation of Tornado pull or Rocket impact.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import numpy as np

from .dataset_gen import card_key
from .obs_contract import REPO, catalog_card_form

ICEBOW = {'ice-wizard', 'knight', 'rocket', 'skeletons', 'tesla', 'the-log', 'tornado', 'x-bow'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@lru_cache(maxsize=1)
def catalog():
    path = REPO / 'research/ext/Royale/RoyaleSim/data/derived/cards.json'
    data = json.loads(path.read_text())
    result = {}
    for c in data['cards']:
        key = card_key(c['name'])
        if key:
            # Catalog lists canonical cards before aliases such as SuperWitch
            # and GoblinPartyRocket. Never overwrite real damage with a variant.
            result.setdefault(key, c)
    return result


def scaled_stat(card, field, level):
    """Catalog's explicit unified-level table, matching card.rs level_multiplier.

    No implicit tournament level or folklore 1.1**level fallback.
    """
    c = catalog()[card]
    ls = c['level_scaling']
    local = int(level) - ls['relative_level']
    step = int(level) - ls['base_level']
    if not 1 <= local <= ls['level_count'] or not 0 <= step < len(ls['multiplier_percent_by_level']):
        raise ValueError('Level outside explicit catalog bounds')
    return int(c[field]) * int(ls['multiplier_percent_by_level'][step]) // 100


def durable(body, rocket_damage, log_damage):
    """Strictly survives two Logs; Rocket kills or leaves <10% of maximum HP.

    Two Logs is a numeric damage yardstick even for flying troops, not a claim
    that Log hits air. Shields/unknown damage modifiers are excluded upstream.
    """
    hp, maximum = body.get('hp'), body.get('max_hp')
    return (hp is not None and maximum is not None and maximum > 0 and
            hp > 2 * log_damage and (hp - rocket_damage) * 10 < maximum)


def groups(bodies, rocket_damage, log_damage, rocket_radius=2000, pull_radius=5500):
    """Find qualifying subsets on the SAME half-tile placement grid as the policy.

    Cost is counted once per observed deployment, never once per swarm member.
    Unknown bodies never become positives. A positive is only an opportunity
    proxy; absence is not a proof that a combo cannot work.
    """
    good = [b for b in bodies if b.get('is_troop') and b.get('pullable') and
            b.get('deployment') is not None and b.get('cost') is not None and
            b.get('shield', 0) == 0 and durable(b, rocket_damage, log_damage)]
    result = dict(rocket_only=False, pull_candidate=False, eligible_troops=len(good),
                  compact_elixir=0, pull_elixir=0, compact_troops=0, pull_troops=0)
    if len(good) < 2:
        return result
    centres = np.array([(x, y) for y in range(0, 32000, 500) for x in range(0, 18000, 500)])
    xy = np.array([(b['x'], b['y']) for b in good])
    dist2 = ((centres[:, None, :] - xy[None, :, :]) ** 2).sum(-1)
    compact = dist2 <= rocket_radius ** 2
    wide = dist2 <= pull_radius ** 2
    seen = set()
    for mode, masks in (('compact', compact), ('pull', wide)):
        for hit in np.unique(masks[masks.sum(1) >= 2], axis=0):
            ids = tuple(np.flatnonzero(hit))
            if len(ids) < 2 or (mode, ids) in seen:
                continue
            seen.add((mode, ids))
            costs = {}
            for i in ids:
                b = good[i]
                if b['deployment'] in costs and costs[b['deployment']] != b['cost']:
                    raise ValueError('Inconsistent cost for the same public deployment')
                costs[b['deployment']] = b['cost']
            value = sum(costs.values())
            if value < 9:
                continue
            result[mode + '_elixir'] = max(result[mode + '_elixir'], value)
            result[mode + '_troops'] = max(result[mode + '_troops'], len(ids))
            if mode == 'compact':
                result['rocket_only'] = True
            elif not np.any(compact[:, ids].all(1)):
                result['pull_candidate'] = True
    return result


class PublicBodies:
    """Causal birth-to-public-play attribution for native replays with stable IDs.

    forms with changed stats, shielded units and ambiguous birth attribution.
    Missing attribution is counted and excluded, never assigned full card cost.
    """
    def __init__(self, plays, level):
        self.plays = plays
        self.level = level
        self.births = {}
        self.stats = Counter()

    def read(self, frame):
        out = []
        tick = int(frame['tick'])
        for e in frame.get('entities', []):
            if not isinstance(e, list) or len(e) != 9 or int(e[-2]) < 0:
                continue
            side, x, y, _, hp, maximum, kind, cid, eid = e
            name, form = catalog_card_form(int(cid))
            key = card_key(name) if name else None
            c = catalog().get(key)
            ident = (int(side), int(eid))
            if not c or c['kind'] != 'troop' or hp <= 0:
                continue
            reason = None
            if form:
                reason = 'nonbase_form'
            elif c.get('shield_hitpoints') or c.get('ignore_pushback'):
                reason = 'shield_or_pull_immunity'
            elif not c.get('hitpoints') or maximum != scaled_stat(key, 'hitpoints', self.level):
                reason = 'child_or_modified_max_hp'
            if reason:
                self.stats[reason] += 1
                continue
            if ident not in self.births:
                near = [p for p in self.plays if p['side'] == side and p['card'] == key and
                        0 <= tick - p['tick'] <= 60 and
                        (x-p['x'])**2 + (y-p['y'])**2 <= 3000**2]
                self.births[ident] = near[0] if len(near) == 1 else None
                self.stats['birth_attributed' if len(near) == 1 else 'birth_ambiguous'] += 1
            p = self.births[ident]
            out.append(dict(side=int(side), id=int(eid), card=key, x=x, y=y, hp=hp,
                            max_hp=maximum, is_troop=True, pullable=True, shield=0,
                            deployment=None if p is None else p['deployment'],
                            cost=None if p is None else p['cost']))
        return out


def sequence_rows(ticks, sides, rocket_labels):
    """Expert context windows; both actions AND intervening WAIT/other plays.

    Two seconds of lead-in and one second after impact. The future determines
    sampling membership only, never an input or a fabricated action label.
    """
    windows = np.zeros(len(ticks), dtype=bool)
    combos = np.zeros(len(ticks), dtype=bool)
    finish = np.zeros(len(ticks), dtype=bool)
    for event in rocket_labels:
        landing = event.get('landing_tick')
        if event.get('card') != 'rocket' or landing is None:
            continue
        use = ((sides == event['side']) & (ticks >= event['tick'] - 40) & (ticks <= landing + 20))
        windows |= use
        if event.get('rocket_then_tornado'):
            combos |= use
        if any(t.get('finish') for t in event.get('tower_hits', [])):
            finish |= use
    return windows, combos, finish


def sampling_probabilities(pool, opportunity, sequence, split, *, uniform=False):
    """Frozen mixture: 80% ordinary Icebow, 10% opportunity, 10% expert sequence.

    All buckets include original negatives. Validation/test rows are forbidden.
    A uniform control uses exactly the same pool/steps/optimizer.
    """
    pool, opportunity, sequence = [np.asarray(v, bool) for v in (pool, opportunity, sequence)]
    if not (pool.shape == opportunity.shape == sequence.shape == np.asarray(split).shape):
        raise ValueError('Row shapes do not match')
    if np.any((opportunity | sequence) & ~pool):
        raise ValueError('Curriculum rows outside declared pool')
    train = pool & (np.asarray(split) == 0)
    buckets = [(1.0, train)] if uniform else [(.8, train), (.1, train & opportunity), (.1, train & sequence)]
    result = np.zeros(len(pool), np.float64)
    for weight, mask in buckets:
        if not mask.any():
            raise ValueError('Empty training bucket: cannot silently change the experiment')
        result[mask] += weight / mask.sum()
    return result


def load_curriculum(path, dataset, split):
    path = Path(path)
    m = json.loads((path / 'manifest.json').read_text())
    if (m.get('schema') != 1 or m.get('dataset_sha256') != sha(dataset) or
            not m.get('trainable') or not m.get('public_only')):
        raise ValueError('Curriculum dataset mismatch')
    arrays = path / 'cohorts.npz'
    if m.get('cohorts_sha256') != sha(arrays) or not m.get('expert_targets_unchanged'):
        raise ValueError('Curriculum provenance mismatch')
    with np.load(arrays, allow_pickle=False) as z:
        data = {k: z[k] for k in z.files}
    p = sampling_probabilities(data['pool'], data['opportunity'], data['sequence'], split)
    if len(p) != m['rows']:
        raise ValueError('Curriculum row count mismatch')
    return data, m
