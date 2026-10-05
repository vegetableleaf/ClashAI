"""Public body identity prototype, staged outside the running Q3 source snapshot.

This changes observations, never card choices. Exact catalog maximum-HP evidence
separates a spawned body from its originating card. Unrecognised or ambiguous
evidence retains the legacy identity and form. No current/future opponent state.
"""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

from pipeline import vocab
from pipeline.obs_contract import REPO

CATALOG = REPO / 'research/ext/Royale/RoyaleSim/data/derived/cards.json'
# Coverage boundary: these six families have native replay witnesses. This is
# observation normalisation, not a tactical preference or a spawn schedule.
FAMILIES = frozenset(('witch', 'night_witch', 'furnace', 'goblin_hut',
                      'barbarian_hut', 'tombstone'))
BODY_ALIASES = {'Skeleton': 'skeletons', 'Bat': 'bats',
                'Barbarian': 'barbarians', 'SpearGoblin': 'spear_goblins'}


@dataclass(frozen=True)
class Identity:
    cls: int | None
    form: int
    reason: str


def child_names(record):
    names = set()
    for field in ('spawner', 'death_spawn'):
        value = record.get(field) or {}
        names.update(value[k] for k in ('character', 'character2') if value.get(k))
    for value in (record.get('action_graph') or {}).get('spawns', []):
        if value.startswith('CharacterType:'):
            names.add(value.split(':', 1)[1])
    return names


def body_key(name, units):
    unit = units.get(name)
    if unit is None:
        return None
    # Derived variants retain their underlying character name in raw.Name.
    base = (unit.get('raw') or {}).get('Name', name)
    key = BODY_ALIASES.get(base, vocab.engine_key(base))
    return key if key in vocab.UNIT_VOCAB else None


@lru_cache(maxsize=1)
def tables():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    canonical = {}
    for card in catalog['cards']:
        key = vocab.engine_key(card['name'])
        canonical.setdefault(key, card)
    rows = {(key, 0): canonical[key] for key in FAMILIES}
    for field, form in (('evolutions', 1), ('hero_forms', 2)):
        for card in catalog[field]:
            key = vocab.engine_key(card.get('form_of', ''))
            if key in FAMILIES:
                rows[key, form] = card
    result = {}
    for (parent, form), record in rows.items():
        ls = record['level_scaling']
        levels = range(1 + ls['relative_level'], 1 + ls['relative_level'] + ls['level_count'])
        possibilities = {}
        units = catalog['units']
        children = [(name, body_key(name, units)) for name in child_names(record)]
        for level in levels:
            step = level - ls['base_level']
            if not 0 <= step < len(ls['multiplier_percent_by_level']):
                continue
            multiplier = ls['multiplier_percent_by_level'][step]
            hp = int(record['hitpoints']) * multiplier // 100
            possibilities.setdefault(hp, set()).add((vocab.unit_id(parent), form, 'parent'))
            for name, key in children:
                if key is None:
                    continue
                hp = int(units[name]['hitpoints']) * multiplier // 100
                if hp > 0:
                    # A child is its own character, not the parent's evo/hero.
                    possibilities.setdefault(hp, set()).add((vocab.unit_id(key), 0, 'child'))
        result[parent, form] = possibilities
    return result


def resolve(name, max_hp, form=0):
    legacy = vocab.engine_unit_id(str(name), max_hp)
    key = vocab.engine_key(str(name))
    table = tables().get((key, int(form)))
    if table is None:
        # SIM may already name a child directly. Recognise the same catalog
        # aliases without applying the originating parent's form to it.
        if name in BODY_ALIASES:
            return Identity(vocab.unit_id(BODY_ALIASES[name]), 0, 'explicit_child')
        return Identity(legacy, int(form), 'legacy')
    if max_hp is None or not math.isfinite(float(max_hp)) or int(max_hp) != float(max_hp):
        return Identity(legacy, int(form), 'unknown_hp')
    possibilities = table.get(int(max_hp), set())
    if len(possibilities) != 1:
        return Identity(legacy, int(form), 'ambiguous_hp' if possibilities else 'unknown_hp')
    cls, actual_form, reason = next(iter(possibilities))
    return Identity(cls, actual_form, reason)
