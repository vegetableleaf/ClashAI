"""Offline private result validation and bounded state/transition summary."""
import argparse
import json
from pathlib import Path
import re

from qualify import REQUIRED, SITE_NAMES, Blocked, ignored, require, write_json


def validate_rule(value, rule):
    """The local schema's small keyword subset; no dependency or remote resolution."""
    types = {'object': dict, 'array': list, 'string': str, 'integer': int, 'boolean': bool}
    if 'type' in rule:
        require(type(value) is types[rule['type']], 'RESULT_TYPE')
    if 'const' in rule:
        require(type(value) is type(rule['const']) and value == rule['const'], 'RESULT_CONSTANT')
    if 'enum' in rule:
        require(value in rule['enum'], 'RESULT_ENUM')
    if 'pattern' in rule:
        require(re.fullmatch(rule['pattern'], value), 'RESULT_PATTERN')
    if 'minLength' in rule:
        require(len(value) >= rule['minLength'], 'RESULT_STRING_LENGTH')
    if 'minimum' in rule:
        require(value >= rule['minimum'], 'RESULT_MINIMUM')
    if isinstance(value, dict):
        require(set(rule.get('required', [])) <= set(value), 'RESULT_REQUIRED_FIELDS')
        properties = rule.get('properties', {})
        if rule.get('additionalProperties') is False:
            require(set(value) <= set(properties), 'RESULT_UNKNOWN_FIELDS')
        for key in value.keys() & properties.keys():
            validate_rule(value[key], properties[key])
    if isinstance(value, list):
        require(rule.get('minItems', 0) <= len(value) <= rule.get('maxItems', len(value)), 'RESULT_COVERAGE')
        for item in value:
            validate_rule(item, rule.get('items', {}))


def validate_result(result):
    schema = json.loads(Path(__file__).with_name('results.schema.json').read_text())
    validate_rule(result, schema)
    for name, ids in (('probes', REQUIRED), ('sites', SITE_NAMES)):
        rows = result[name]
        require(isinstance(rows, list) and len(rows) == len(ids), 'RESULT_COVERAGE')
        require({r['id'] for r in rows} == set(ids), 'RESULT_DUPLICATE_OR_MISSING_ID')


def summarize(samples):
    observations = {'samples': len(samples), 'flag_samples': 0, 'flag_changes': 0,
                    'owner_matches': 0, 'owner_mismatches': 0, 'battle_samples': 0,
                    'tick_increases': 0, 'tick_decreases_or_resets': 0,
                    'accumulator_changes': 0, 'game_main_layout_samples': 0,
                    'loading_samples': 0, 'generation_changes': 0,
                    'function_entry_proven': False,
                    'lifetime_safety_proven': False,
                    'rendering_only_proven': False}
    previous = None
    def val(v, name):
        item = v.get(name)
        return item.get('value') if isinstance(item, dict) else item
    for sample in samples:
        require(sample.get('atomic') is False, 'SAMPLE_ATOMIC_CLAIM')
        v = sample['values']
        generation = tuple(val(v, k) for k in ('manager', 'manager.current_state', 'battle_state.battle', 'scheduling_control'))
        if 'scheduling_flag' in v:
            observations['flag_samples'] += 1
        if 'scheduling_owner_matches_parent' in v:
            observations['owner_matches' if v['scheduling_owner_matches_parent'] else 'owner_mismatches'] += 1
        if v.get('game_main_vtable_matches') and v.get('game_main_init_slot_matches') and v.get('game_main_context_mapped'):
            observations['game_main_layout_samples'] += 1
        if v.get('loading_update_slot_matches') and v.get('loading_complete_slot_matches'):
            observations['loading_samples'] += 1
        if v.get('battle_update_slot_matches') and val(v, 'battle_state.battle'):
            observations['battle_samples'] += 1
        if previous:
            old_gen, old = previous
            if old_gen != generation:
                observations['generation_changes'] += 1
            else:
                for key, counter in (('scheduling_flag', 'flag_changes'), ('battle_state.core_accumulator', 'accumulator_changes')):
                    if key in old and key in v and val(old, key) != val(v, key):
                        observations[counter] += 1
                if 'battle.tick' in old and 'battle.tick' in v:
                    before, after = val(old, 'battle.tick'), val(v, 'battle.tick')
                    if after > before:
                        observations['tick_increases'] += 1
                    elif after < before:
                        observations['tick_decreases_or_resets'] += 1
        previous = generation, v
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    a = parser.parse_args()
    directory = ignored(a.run)
    result = json.loads((directory / 'result.json').read_text())
    validate_result(result)
    path = directory / 'samples.jsonl'
    samples = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    result['observations'] = summarize(samples)
    result['limitations'].extend([
        'GameMain layout/context corroborates initialization; exact CreateGameMain/init entry is not observed.',
        'A constant scheduling byte or accumulator is retained without inventing transitions.',
        'Map request/cache/replay-wrapper arguments are not captured by stable-root polling.',
        'Generation equality between endpoints does not exclude intervening destruction/reuse (ABA).'])
    validate_result(result)
    write_json(directory / 'review.json', result)
    print('PRIVATE_REVIEW_WRITTEN: state evidence only; zero patches qualified')


if __name__ == '__main__':
    try:
        main()
    except (Blocked, OSError, KeyError, ValueError):
        raise SystemExit('BLOCKED: invalid private result; no review written')
