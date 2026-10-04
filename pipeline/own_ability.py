"""Own ability state from visible controllers and confirmed own action history.

readiness/charges. Lead R4 authorizes derivation from own deployment/press logs
and catalog limits; missing own history stays explicitly unknown.
"""
import numpy as np
import json
from functools import lru_cache
from . import vocab
from .obs_contract import catalog_card_form, entity_form

ABILITY_K = 8
ABILITY_COLS = ('card', 'form', 'living_controllers', 'ready', 'ready_known', 'remaining_charges', 'cooldown_s')
CHAMPIONS = {'archer-queen', 'golden-knight', 'skeleton-king', 'mighty-miner',
             'monk', 'little-prince', 'boss-bandit', 'goblinstein'}


def observe(frame, side, source):
    groups = {}
    for i, e in enumerate(frame.get('entities') or []):
        owner = int(e['side'] if isinstance(e, dict) else e[0])
        if owner != side:
            continue
        if isinstance(e, dict):
            hp = e['hp']
            if source == 'sim':
                key, form = vocab.engine_key(e.get('name', '')), entity_form(e)
            else:
                name, form = catalog_card_form(int(e.get('card_id', -1)))
                key = vocab.engine_key(name) if name else None
        else:
            hp = e[4]
            name, form = catalog_card_form(int(frame['native_card_ids'][i]))
            key = vocab.engine_key(name) if name else None
        key = vocab.base_key(key).replace('_', '-') if key else None
        if hp <= 0 or not key or not (form == 2 or key in CHAMPIONS):
            continue
        # Only visible controller presence is common to all three input paths.
        # Keep explicit unknown readiness even when SIM has privileged flags.
        groups[key, form] = groups.get((key, form), 0) + 1
    return [(key, form, count, -1., 0.) for (key, form), count in sorted(groups.items())]


@lru_cache(maxsize=1)
def catalog():
    from .obs_contract import REPO
    from .dataset_gen import card_key
    data=json.loads((REPO/'research/ext/Royale/RoyaleSim/data/derived/cards.json').read_text())
    return {(card_key(c.get('form_of',c['name'])),form):dict(c['ability'],deploy_ms=c.get('deploy_time_ms') or 0)
            for form,source in ((0,'cards'),(2,'hero_forms')) for c in data[source] if c.get('ability')}


def tokens(rows, gid, events=(), tick=0):
    from .dataset_gen import card_key
    if len(rows) > ABILITY_K:
        raise ValueError('Own ability controller capacity exceeded')
    out = np.zeros((ABILITY_K, len(ABILITY_COLS)), np.float32)
    for i, (key, *values) in enumerate(rows):
        spec=catalog().get((key,int(values[0])))
        before=[e for e in events if e.get('accepted',True) and int(e.get('engine_tick',e['tick']))<tick and card_key(e.get('card',''))==key]
        deploys=[e for e in before if not e.get('ability')]
        charges=cd=-1.
        if spec and deploys:
            born=max(int(e.get('engine_tick',e['tick'])) for e in deploys)
            presses=[e for e in before if e.get('ability') and int(e.get('engine_tick',e['tick']))>=born]
            charges=max(0,spec['max_charges']-len(presses))
            ready_tick=born+spec['deploy_ms']/50
            if presses:ready_tick=max(ready_tick,max(int(e.get('engine_tick',e['tick'])) for e in presses)+(spec.get('cooldown_ms') or 0)/50)
            cd=max(0,ready_tick-tick)*.05
            values[-2:]=[float(charges>0 and cd==0),1.]
        out[i] = (gid.get(key, 0), *values, charges, cd)
    return out
