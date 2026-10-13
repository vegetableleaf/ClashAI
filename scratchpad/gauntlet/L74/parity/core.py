"""Public-only extraction and comparison. Standard library; never imports SIM."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[4]
PHASE = ROOT / 'scratchpad/gauntlet/L74/phase_stats'
sys.path.insert(0, str(PHASE))  # phase_stats's existing video_metrics import
import phase_stats as ps


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def raw_xy(side, x, y):
    """Inverse of phase_stats.own_xy; output native millitiles."""
    return [round(x * 1000), round(y * 1000)] if side == 1 else [round((18-x)*1000), round((32-y)*1000)]


def observations(data, catalog):
    """Reuse the audited cube/spell exclusions; retain raw coordinates and identity."""
    out = []
    for d in data['decisions']:
        keep = {u['key'] for u in ps.units(d, catalog)}
        bodies = []
        for b in d['bodies']:
            tower = ps.is_tower(b)
            if not tower and ps.body_key(b) not in keep:
                continue
            # Never export reader addresses; hash only to join this match's observations.
            key = hashlib.sha256(ps.body_key(b).encode()).hexdigest()[:20]
            bodies.append({k: b[k] for k in ('card_id', 'side', 'x', 'y', 'hp', 'max_hp')} |
                          dict(key=key, tower=tower))
        out.append(dict(tick=d['tick'], side=d['side'], bodies=bodies,
                        own_elixir=d['elixir']))
    return out


def extract_plays(data, catalog, names):
    """Confirmed own taps + EXACT phase_stats/video_metrics placement proxy rules.

    Call the existing extractor, rather than maintain a second swarm/gap heuristic.
    Its other video metrics are discarded. No opponent hand/elixir is read.
    """
    ds = data['decisions']; side = ds[0]['side']
    own = []
    for p in ps.match_plays(data):
        if not p['confirmed']:
            continue
        xy = p.get('actual_xy') or p['xy']
        c = names.get(p['name'])
        if c is None or xy is None:
            raise ValueError('unmapped_confirmed_play:' + p['name'])
        # phase_stats conversion from normalized/model coordinates, then inverse own frame.
        x, y = raw_xy(side, 18-xy[0]*18, xy[1]*32)
        own.append(dict(tick=p['tick'], side=side, name=p['name'], card_id=c['card_id'],
                        x=x, y=y, source='confirmed_own_tap',
                        previous_tick=p['tick'], confirmation_tick=p['confirmation_tick']))
    uss = [ps.units(d, catalog) for d in ds]
    m = {}
    ps.vm.bot(m, ds, uss, [], [], [], catalog, ps.ARCH_ORDER, ps.towers, ps.own_xy, ps.in_spell)
    enemy = []
    for event in m['video']['events']:
        if event['kind'] != 'enemy_placement_proxy':
            continue
        c = names.get(event['name'])
        if c is None:
            continue
        x, y = raw_xy(side, event['x'], event['y'])
        enemy.append(dict(tick=event['tick'], previous_tick=event['previous_tick'], side=1-side,
                          name=event['name'], card_id=c['card_id'], x=x, y=y,
                          source='first_seen_body_proxy', bodies=len(event['body_keys'])))
    return sorted(own+enemy, key=lambda p: (p['tick'], p['side']))


def prepare(path, data, catalog, names, assumed_level=None):
    side = data['decisions'][0]['side']
    decks = {0: {}, 1: {}}
    for d in data['decisions']:
        for h in d['hand']:
            if h['name'] in names:
                c = names[h['name']]
                old = decks[side].get(c['display_name'], {}).get('form', 0)
                decks[side][c['display_name']] = dict(name=c['display_name'], card_id=c['card_id'],
                                                     form=max(old, int(h.get('form', 0))))
        for b in d['bodies'] + d['projectiles']:
            c = catalog.get(b['card_id'])
            if c is None or b['side'] == side:
                continue
            form = 2 if b['card_id'] in (c.get('hero_form_id'), 203000023) else int(b['card_id'] == c.get('evolution_form_id'))
            old = decks[1-side].get(c['display_name'], {}).get('form', 0)
            decks[1-side][c['display_name']] = dict(name=c['display_name'], card_id=c['card_id'], form=max(old, form))
    plays = extract_plays(data, catalog, names)
    blocks = [f'public_deck_side_{s}_has_{len(decks[s])}_cards' for s in (0, 1) if len(decks[s]) != 8]
    if assumed_level is None:
        blocks.append('card_and_tower_levels_unobserved_supply_explicit_assumed_level')
    for s in (0, 1):
        for c in decks[s].values():
            c['level'] = assumed_level
    frames = observations(data, catalog)
    return dict(schema=1, match=path.stem, sha256=data['sha256'], observer_side=side,
                decks={str(s): list(decks[s].values()) for s in (0, 1)}, plays=plays, frames=frames,
                tower_levels=[assumed_level, assumed_level], blocks=blocks,
                quality=dict(levels='assumed_uniform' if assumed_level else 'unknown',
                             assumed_level=assumed_level, deck_completeness='public_candidates_not_certified',
                             enemy_plays='first_sighting_proxies', exact_reconstruction=False,
                             forms='observed_lower_bound', first_tick=frames[0]['tick'],
                             opening_bodies=sum(not b['tower'] for b in frames[0]['bodies']),
                             unconfirmed_own_attempts=sum(not p['confirmed'] for p in ps.match_plays(data)),
                             undriven_own_abilities=len(data['abilities']),
                             gaps_over_40_ticks=sum(b['tick']-a['tick'] > 40 for a,b in zip(frames, frames[1:])),
                             read_errors=data['errors']))


def select(live, since='20261008', limit=100, assumed_level=None):
    catalog, names = ps.load_catalog()
    selected, excluded = [], []
    for path in sorted(Path(live).glob('live_play_*.jsonl')):
        if path.name[10:18] < since:
            continue
        data, reason = ps.read_live(path)
        if reason:
            excluded.append(dict(file=path.name, reason=reason)); continue
        selected.append(prepare(path, data, catalog, names, assumed_level))
        if len(selected) >= limit:
            break
    return selected, excluded


class Tracks:
    """Match card ID + absolute side + first-observed spawn order across engines.

    Local identity preserves order through motion/death. Reused addresses after
    >60 ticks split, matching phase_stats. Same-tick ties use x,y,key and are uncertain.
    """
    def __init__(self, role_limits=None):
        self.seen = {}; self.counts = Counter()
        self.role_limits = role_limits or {}

    def assign(self, tick, bodies):
        out = {}
        for b in sorted(bodies, key=lambda b: (b['card_id'], b['side'], b['x'], b['y'], str(b['key']))):
            if b.get('tower'):
                key = f"tower:{b['side']}:" + ('king' if abs(b['x']-9000)<1000 else ('left' if b['x']<9000 else 'right'))
            else:
                role = ''
                limits = self.role_limits.get((b['card_id'], b['side']))
                if limits:
                    name, maximum = limits
                    role = 'child' if b['max_hp'] < .45*maximum else (
                        'travel' if name == 'GoblinDrill' and b['max_hp'] >= .8*maximum else 'parent')
                local = (b['card_id'], b['side'], b['key'], role)
                if local not in self.seen or tick-self.seen[local][1] > 60:
                    group = (b['card_id'], b['side'], role); self.counts[group] += 1
                    self.seen[local] = (self.counts[group], tick)
                order, _ = self.seen[local]; self.seen[local] = (order, tick)
                key = f"unit:{b['card_id']}:{b['side']}:{order}"
                if role:
                    key += ':'+role
            if key in out:
                raise ValueError('duplicate_body_identity:' + key)
            out[key] = b
        return out


def compare(live, sim, position_threshold=0.5, hp_threshold=1):
    rows = []
    for key in sorted(live.keys() | sim.keys()):
        a, b = live.get(key), sim.get(key)
        body = a or b
        missing = 'sim' if b is None else 'live' if a is None else None
        pos = math.hypot(a['x']-b['x'], a['y']-b['y'])/1000 if not missing else None
        hp = abs(a['hp']-b['hp']) if not missing else None
        # Absence is NOT zero HP: separate count + visible HP at risk, no invented death.
        rows.append(dict(identity=key, card_id=body['card_id'], side=body['side'], tower=body.get('tower', False),
                         position_error_tiles=pos, hp_error=hp, missing=missing,
                         unmatched_visible_hp=max(0, body['hp']) if missing else 0,
                         mismatch=bool(missing or (pos is not None and pos>position_threshold) or
                                       (hp is not None and hp>=hp_threshold))))
    return rows


def mechanic(name, kind='troop'):
    return {'Tesla': 'Tesla deploy', 'Xbow': 'X-Bow target switch', 'Tornado': 'Tornado pull',
            'Log': 'Log knockback'}.get(name, 'spell damage' if kind == 'spell' else name+' movement/combat')


def rank(samples, catalog):
    """Associated error, NOT causal attribution. One row per group per sampled tick.

    Exposure-normalized means and mismatch frequency prevent cards with many bodies
    from multiplying the same tower damage. Groups may overlap; scores are not additive.
    """
    groups = defaultdict(list)
    for sample in samples:
        active = set()
        spell_context = set()
        for row in sample['rows']:
            if not row['tower']:
                c = catalog.get(row['card_id'], {})
                active.add(mechanic(c.get('display_name', str(row['card_id'])), c.get('type')))
        for p in sample.get('recent_plays', []):
            c = catalog.get(p['card_id'], {})
            label = mechanic(p['name'], c.get('type'))
            active.add(label)
            if c.get('type') == 'spell':
                spell_context.add(label)
        active.add('elixir regen/queue')
        if not active - {'elixir regen/queue'}:
            active.add('unattributed tower/state')
        for group in active:
            unit = [r for r in sample['rows'] if not r['tower'] and
                    (group in spell_context or
                     mechanic(catalog.get(r['card_id'], {}).get('display_name', str(r['card_id'])),
                              catalog.get(r['card_id'], {}).get('type')) == group)]
            tower = [r for r in sample['rows'] if r['tower']]
            special = group == 'elixir regen/queue'
            elixir = sample.get('own_elixir_error')
            rejected = sample.get('command_rejections', 0)
            mismatch = ((elixir is not None and elixir > .1) or rejected>0) if special else any(r['mismatch'] for r in unit+tower)
            groups[group].append(dict(match=sample['match'], mismatch=mismatch,
                                     unit_hp=mean(r['hp_error'] for r in unit),
                                     position=mean(r['position_error_tiles'] for r in unit),
                                     tower_hp=mean(r['hp_error'] for r in tower),
                                     unmatched=sum(r['missing'] is not None for r in unit+tower),
                                     elixir=elixir if special else None, rejections=rejected if special else 0))
    out = []
    for group, rows in groups.items():
        frequency = sum(r['mismatch'] for r in rows)
        hp, tower = mean(r['unit_hp'] for r in rows), mean(r['tower_hp'] for r in rows)
        # Tower HP prioritized; missing bodies and movement count even at zero measured HP error.
        impact = frequency/len(rows) * (4*(tower or 0)+(hp or 0)+100*(mean(r['unmatched'] for r in rows) or 0)
                                      +100*(mean(r['position'] for r in rows) or 0)
                                      +100*(mean(r['elixir'] for r in rows) or 0)+100*sum(r['rejections'] for r in rows)/len(rows))
        out.append(dict(group=group, frequency=frequency, exposures=len(rows), matches=len({r['match'] for r in rows}),
                        mean_unit_hp_error=hp, mean_tower_hp_error=tower,
                        mean_position_error_tiles=mean(r['position'] for r in rows),
                        mean_own_elixir_error=mean(r['elixir'] for r in rows),
                        command_rejections=sum(r['rejections'] for r in rows), impact=impact,
                        attribution='association_only'))
    return sorted(out, key=lambda r: (-r['impact'], r['group']))
