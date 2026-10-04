"""Version-4 public projectile/effect tokens. Missing timing is explicitly unknown.

No speed, lifetime or landing event is inferred from future frames. Version 4
uses current public aim and catalog speed, with consecutive public motion as
fallback for ambiguous catalog stages. Area lifetime requires source evidence
and a shared capability mask for clocks the SIM adapter cannot expose.
Coordinates use the same observer orientation as obs_contract. This module never
reads player blocks, command logs, target entity IDs, or hidden ability state.
"""
from bisect import bisect_right
import math
import numpy as np
from functools import lru_cache

from . import vocab
from .obs_contract import catalog_card_form

PROJECTILE_K, EFFECT_K = 64, 32
PROJECTILE_COLS = ('card', 'enemy', 'x', 'y', 'target_x', 'target_y', 'tti_s', 'tti_known')
EFFECT_COLS = ('card', 'enemy', 'x', 'y', 'remaining_s', 'remaining_known')


@lru_cache(maxsize=1)
def constant_projectile_speeds():
    """Native speed units: millitiles per 50ms tick (calibration.json).

    Distance to the currently visible aim is an estimate, also for homing shots.
    Multi-stage projectiles with different speeds retain the motion fallback:
    the public card identity alone cannot identify their stage.
    """
    import json
    from .obs_contract import REPO
    data=json.loads((REPO/'research/ext/Royale/RoyaleSim/data/derived/cards.json').read_text())
    return {vocab.base_key(vocab.engine_key(c['display_name'])).replace('_','-'):p['speed']
            for c in data['cards'] if (p:=c.get('projectile')) and p.get('speed',0)>0
            and not p.get('spawn_projectile')}


def catalog_tti(key, x, y, tx, ty):
    """One shared instantaneous distance/speed definition, in milliseconds."""
    speed = constant_projectile_speeds().get(key)
    if not speed or tx is None or ty is None:
        return None
    return math.hypot(float(tx)-float(x), float(ty)-float(y))/speed*50


@lru_cache(maxsize=1)
def unavailable_area_timers():
    """SIM exports next-strike/count, not remaining life for these shapes.

    a deterministic source-capability mask, not a random change of experiment.
    """
    import json
    from .obs_contract import REPO
    data=json.loads((REPO/'research/ext/Royale/RoyaleSim/data/derived/cards.json').read_text())
    unavailable = {vocab.base_key(vocab.engine_key(c['display_name'])).replace('_','-')
            for c in data['cards'] if (a:=(c.get('spell') or {}).get('area_effect_object'))
            and (a.get('schedule') or a.get('hit_biggest_targets'))}
    # Actual twenty-deck SIM probe: these also expose one-shot/strike/fuse
    # phases without a remaining-area clock. Card identity cannot distinguish
    # the Lumberjack's fuse from its subsequent pulsing Rage in all adapters.
    return unavailable | {'royal-delivery','ice-golem','void','lumberjack'}


def sim_objects(state, names, scale):
    """Decode PROJECTILE_FIELDS / SPELL_FIELDS without using private players."""
    projectiles = [dict(side=p.team, x=p.x/scale, y=p.y/scale,
                        target_x=p.aim_x/scale, target_y=p.aim_y/scale,
                        name=names.get(p.firer_card_id, str(p.firer_card_id)), time_to_impact_ms=None)
                   for p in state.projectiles]
    effects = []
    for sp in state.spells:
        row = dict(side=sp.team, x=sp.x/scale, y=sp.y/scale, name=names.get(sp.card_id, str(sp.card_id)))
        if sp.motion in (0, 1, 2):
            projectiles.append(dict(row, target_x=sp.aim_x/scale, target_y=sp.aim_y/scale, time_to_impact_ms=None))
        else:
            effects.append(dict(row, remaining_ms=sp.delay_ticks*50 if sp.motion == 4 else None))
    for row in projectiles:
        key = vocab.engine_key(row['name'])
        if key:
            key = vocab.base_key(key).replace('_','-')
            row['time_to_impact_ms'] = catalog_tti(key,row['x'],row['y'],row['target_x'],row['target_y'])
    return dict(projectiles=projectiles, effects=effects)


def _timing(value):
    if value is None:
        return -1.0, 0.0
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('Invalid public timing')
    return value / 1000, 1.0


def _xy(x, y, side):
    x, y = float(x)/18000, float(y)/32000
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError('Invalid public coordinates')
    return (x, 1-y) if side == 0 else (1-x, y)


def objects(frame, *, source):
    if source not in ('native', 'sim', 'frame'):
        raise ValueError('Unknown projectile schema')
    out = {'projectiles': [], 'effects': []}
    for kind in out:
        # Native bridge `effects` is the generic nonunit list (includes shots).
        # Actual area effects are a separate export. An absent area_effects
        # field means unavailable, not empty.
        field = 'area_effects' if source == 'native' and kind == 'effects' else kind
        evidence = frame.get('public_objects') if source == 'native' else None
        rows = evidence.get(field, []) if evidence is not None else frame.get(field, [])
        for e in rows or []:
            if isinstance(e, dict):
                if source == 'sim':
                    key = vocab.engine_key(e.get('name', ''))
                else:
                    name, _ = catalog_card_form(int(e.get('card_id', -1)))
                    key = vocab.engine_key(name) if name else None
                side, x, y = (e[k] for k in ('side', 'x', 'y'))
                extra = ([e.get('target_x'), e.get('target_y'), e.get('time_to_impact_ms')]
                         if kind == 'projectiles' else [e.get('source_remaining_ms', e.get('remaining_ms'))])
            else:
                if source != 'native':
                    raise ValueError('Compact objects require native schema')
                expected = 6 if kind == 'projectiles' else 4
                if len(e) != expected:
                    raise ValueError('Unregistered compact projectile/effect schema')
                side, x, y = e[:3]
                key = vocab.engine_key(e[5 if kind == 'projectiles' else 3])
                extra = [e[3], e[4], None] if kind == 'projectiles' else [None]
            # Tower/unknown-projectile identities are not vocabulary card IDs.
            if key and str(key) not in ('-1', '-2') and int(side) in (0, 1):
                key = vocab.base_key(key).replace('_', '-')
                if kind == 'effects' and key in unavailable_area_timers():
                    extra = [None]
                elif kind == 'effects' and extra[0] is not None:
                    # SIM exposes ceil(remaining_ms / 50), not sub-tick ms.
                    value=float(extra[0])
                    if not math.isfinite(value) or value<0:raise ValueError('Invalid public area timing')
                    extra = [math.ceil(value/50)*50]
                out[kind].append((key, int(side), x, y, *extra))
    return out


def tokens(frame, side, gid, *, source, stats=None):
    return tokens_from_objects(objects(frame, source=source), side, gid, stats=stats)


def tokens_from_objects(observed, side, gid, *, stats=None):
    stats = stats if stats is not None else {}
    out = {}
    for kind, rows in observed.items():
        capacity, width = (PROJECTILE_K, 8) if kind == 'projectiles' else (EFFECT_K, 6)
        values = []
        for key, owner, x, y, *extra in rows:
            card = gid.get(key, 0)
            if not card:
                stats[kind+'_unknown_card'] = stats.get(kind+'_unknown_card', 0)+1
                continue
            pos = _xy(x, y, side)
            if kind == 'projectiles':
                tx, ty, ms = extra
                if tx is None or ty is None:
                    target=(-1.,-1.);ms=None
                else:target=_xy(tx,ty,side)
                row = [card, float(owner != side), *pos, *target, *_timing(ms)]
            else:
                row = [card, float(owner != side), *pos, *_timing(extra[0])]
            stats[kind+'_observed'] = stats.get(kind+'_observed', 0)+1
            if row[-1] == 0:
                stats[kind+'_missing_timing'] = stats.get(kind+'_missing_timing', 0)+1
                if kind == 'effects' and key in unavailable_area_timers():
                    stats['effects_capability_masked'] = stats.get('effects_capability_masked',0)+1
            values.append(row)
        # Order does not carry source-container identity; overflow is explicit.
        values.sort(key=tuple)
        if len(values) > capacity:
            stats[kind+'_overflow'] = stats.get(kind+'_overflow', 0)+len(values)-capacity
        arr = np.zeros((capacity, width), dtype=np.float32)
        if values:
            arr[:min(capacity, len(values))] = values[:capacity]
        out[kind] = arr
    return out


def recording_tokens(rec, ticks, sides, keys, stats):
    """Latest sampled board at or before each row; never the next frame."""
    frames = sorted(rec['frames'], key=lambda f: int(f['tick']))
    stats['native_area_effects_unavailable'] = sum('area_effects' not in f.get('public_objects', f) for f in frames)
    times = [int(f['tick']) for f in frames]
    for fr in frames:
        for rows in objects(fr, source='native').values():
            for key, *_ in rows:
                if key not in keys:
                    keys.append(key)
    gid = {key: i+1 for i, key in enumerate(keys)}
    encoded = {}
    from .projectile_motion import ProjectileMotion
    motion = ProjectileMotion(catalog_fallback=True)
    for i, fr in enumerate(frames):
        observed = motion.update(objects(fr, source='native'), times[i], stats)
        for side in (0, 1):
            encoded[i, side] = tokens_from_objects(observed, side, gid, stats=stats if side == 0 else None)
    rows = []
    for tick, side in zip(ticks, sides):
        i = bisect_right(times, int(tick))-1
        # Dataset rows before first observation contain no public objects.
        rows.append(encoded[i, int(side)] if i >= 0 else tokens({}, int(side), gid, source='native'))
    return {kind: np.stack([r[kind] for r in rows]) for kind in ('projectiles', 'effects')}


def require_complete_training(meta, *, allow_causal_tti_unknowns=False):
    """Fail before allocation/training instead of training the incomplete brief."""
    if int(meta.get('feature_version', 1)) < 4:
        return
    if meta.get('projectile_cols') != list(PROJECTILE_COLS) or meta.get('effect_cols') != list(EFFECT_COLS):
        raise ValueError('gen_v3.1 lacks the required projectile/effect contract')
    stats = meta.get('stats', {})
    bad = {k: v for k, v in stats.items() if v and
           (k.endswith('_missing_timing') or k.endswith('_unknown_card') or k.endswith('_overflow') or k.endswith('_unavailable'))}
    if allow_causal_tti_unknowns:
        # Owner decision2 authorizes past-motion estimates, whose new/ambiguous
        # observations deliberately retain an explicit unknown mask. It does
        # not authorize absent area inputs or unknown card/overflow losses.
        if not stats.get('projectiles_motion_estimated'):
            raise ValueError('No causal projectile motion estimates measured')
        bad.pop('projectiles_missing_timing', None)
        # R6 permits the common capability mask, counted separately from
        # missing source evidence. It is identical for each affected identity.
        missing=bad.get('effects_missing_timing',0)
        masked=stats.get('effects_capability_masked',0)
        if missing and missing == masked:
            bad.pop('effects_missing_timing')
        # Lead 2026-10-04: slot overflow at <= 1e-4 of observations is accepted (gen_dataset_v31_public: 40 of
        # 1,719,918 effects); the count stays in meta. Larger overflow still refuses (raise the slot count instead).
        for k in [k for k in bad if k.endswith('_overflow')]:
            if bad[k] <= 1e-4 * max(1, stats.get(k.replace('_overflow', '_observed'), 0)):
                bad.pop(k)
    if bad or not stats.get('projectiles_observed') or not stats.get('effects_observed'):
        raise ValueError(f'gen_v3.1 timing/coverage incomplete; owner/lead source decision required: {bad}')
