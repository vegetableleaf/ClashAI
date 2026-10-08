"""Own ability state from visible controllers and confirmed own action history.

No opposing entity ability flags are read. The recordings and reader v2 lack
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


# Hero forms the pinned RoyaleSim cards.json lacks (L74 econ2 parity fix). Without a spec, tokens() leaves a live controller
# 'readiness unknown' (ready_known 0, charges -1, cooldown -1) -- a state absent from training (695,286 hero ability rows,
# all ready_known 1) that measurably inflates the gate. Values: elixir drop per confirmed press 1.143 (n 763: 1 + regen
# during confirmation) (a); <= 1 press per life in 98.6% of 2,825 lives and the button 'absent' after a press (a, max 1
# charge, no cooldown -- as every other hero in cards.json); deploy -> first 'ready' <= 2.3 s at 2 s button sampling,
# consistent with the 1000 ms deploy every hero form uses (b). Measured: scratchpad/gauntlet/L74/econ2/diag_hero.py.
SUPPLEMENT = {('ice-wizard', 2): dict(name='IceWizardHero_Ability', mana_cost=1, max_charges=1, cooldown_ms=None,
                                      deploy_ms=1000, source='L74 econ2 live record (diag_hero.py)')}
# The supplement is OPT-IN and passed explicitly (live-only flag --hero-ability-spec): 'off' (default, every SIM /
# training / native path) = the pinned cards.json only, byte-identical to before; 'supplement' = + SUPPLEMENT.
HERO_SPECS = ('off', 'supplement')


@lru_cache(maxsize=2)
def catalog(hero_spec='off'):
    if hero_spec not in HERO_SPECS:
        raise ValueError(f'hero_spec {hero_spec!r} not in {HERO_SPECS}')
    from .obs_contract import REPO
    from .dataset_gen import card_key
    data=json.loads((REPO/'research/ext/Royale/RoyaleSim/data/derived/cards.json').read_text())
    out = {(card_key(c.get('form_of',c['name'])),form):dict(c['ability'],deploy_ms=c.get('deploy_time_ms') or 0)
           for form,source in ((0,'cards'),(2,'hero_forms')) for c in data[source] if c.get('ability')}
    if hero_spec == 'supplement':
        for k, spec in SUPPLEMENT.items():
            out.setdefault(k, dict(spec))   # the engine's own data wins once RoyaleSim carries the form
    return out


def tokens(rows, gid, events=(), tick=0, *, hero_spec='off'):
    from .dataset_gen import card_key
    if len(rows) > ABILITY_K:
        raise ValueError('Own ability controller capacity exceeded')
    out = np.zeros((ABILITY_K, len(ABILITY_COLS)), np.float32)
    for i, (key, *values) in enumerate(rows):
        spec=catalog(hero_spec).get((key,int(values[0])))
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
