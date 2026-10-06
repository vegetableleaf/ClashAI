"""Isolated named-character reader adapter; not imported by the current live worker."""
from copy import deepcopy

HERO_ID = 203000023
ELITE_BASE = 26000043
ELITE_EVO = 13000043
BUILD = 160402012
ROLES = {
    'IceWizardHero': 'body',
    'IceWizardHeroFloatingCube': 'attached_auxiliary',
    'IceWizardHero_IceCube': 'unmodeled_ice_cube',
}


def extend_elite_names(original):
    result = dict(original)
    if result.get(ELITE_BASE) != 'AngryBarbarians':
        raise ValueError('Elite alias requires proved base identity')
    if ELITE_EVO in result and result[ELITE_EVO] != 'AngryBarbarians':
        raise ValueError('Conflicting evolved Elite identity')
    result[ELITE_EVO] = 'AngryBarbarians'
    return result


def extend_elite_forms(original):
    result = dict(original)
    if result.get(ELITE_BASE) != ('AngryBarbarians', 0):
        raise ValueError('Elite alias requires proved base form')
    if ELITE_EVO in result and result[ELITE_EVO] != ('AngryBarbarians', 1):
        raise ValueError('Conflicting evolved Elite form')
    result[ELITE_EVO] = ('AngryBarbarians', 1)
    return result


def adapt(frame):
    """Keep exact named Heroes; retain excluded public objects in diagnostics.

    Call only for the qualified successor. Unknown names cannot become full
    Ice Wizards. Other objects, including colocated real troops, remain exact.
    This contains no behavior/aim/holding decision and never consults players.
    """
    if frame.get('character_identity') != {'schema': 1, 'build': BUILD}:
        raise ValueError('Unqualified character identity schema/build')
    out = dict(frame)
    out['entities'] = []
    excluded = []
    for entity in frame.get('entities', []):
        if int(entity['card_id']) != HERO_ID:
            out['entities'].append(entity)
            continue
        name = entity.get('native_name')
        role = ROLES.get(name, 'unresolved') if entity.get('native_name_status') == 'ok' else 'unresolved'
        if role == 'body':
            out['entities'].append(entity)
        else:
            excluded.append(dict(entity=deepcopy(entity), role=role))
    out['excluded_public_objects'] = excluded
    return out
