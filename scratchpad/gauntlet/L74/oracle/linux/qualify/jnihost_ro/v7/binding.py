"""Project private evidence into a runtime input. No target values in public code."""
import re
from common import PRIVATE, ROOT, require, ignored, read_json, digest

ENTRIES = ('jni_on_load', 'create_game_main', 'game_main_init',
           'data_tables_load_range', 'data_load_task_start', 'data_load_task_pump',
           'data_load_task_complete', 'loading_state_update', 'loading_state_complete',
           'resource_request_list_constructor', 'resource_request_list_append',
           'resource_request_list_load', 'resource_request_list_destructor',
           'location_field_primary', 'location_field_secondary', 'data_string_resolve',
           'build_battlefield_cache', 'battlefield_cache_root', 'data_row_instance_id',
           'location_battlefield', 'manager_update', 'manager_global')
FIELDS = ('manager.current_state', 'loading_state_vtable', 'loading_phase',
          'loading_task', 'data_task.tables', 'data_task.resources', 'data_task.phase',
          'resource_collection.count', 'data_tables.ready', 'resource_request_vtable',
          'battlefield_rows', 'battlefield_count')
EXTRA = ('game_main_global_rva', 'game_main_vtable_rva', 'game_main_context_offset')
# Order is the on-wire ABI; generated names contain no proprietary numbers.
KEYS = ENTRIES + FIELDS + EXTRA + ('resource_request_size',)


def number(value):
    n = int(value, 0) if isinstance(value, str) else value
    require(type(n) is int and 0 <= n < 2**32, 'BINDING_VALUE_RANGE')
    return n


def project(binding):
    extra = read_json(ignored(PRIVATE / 'v4-readonly.json'))
    values = [number(binding['entries'][k]['rva']) for k in ENTRIES]
    require(all(values), 'BINDING_NULL_FUNCTION')
    values += [number(binding['fields'][k].get('offset', binding['fields'][k].get('rva'))) for k in FIELDS]
    values += [number(extra[k]) for k in EXTRA]
    # This size is explicitly recorded in the target constructor ABI evidence.
    abi = binding['entries']['resource_request_list_constructor']['abi']
    match = re.search(r'observed stack allocation has (\S+) bytes available', abi)
    require(match is not None, 'REQUEST_SIZE_EVIDENCE_MISSING')
    size = number(match[1])
    require(0 < size <= 4096, 'REQUEST_SIZE_RANGE')
    values += [size]
    return {'schema_version': 7, 'runtime_version': binding['runtime_version'],
            'keys': list(KEYS), 'values': values,
            'location_recipe': None,
            'limitation': 'The supplied binding has no Location row selection recipe. Map stage stops unless a separately evidenced read-only recipe is supplied before build.'}


def header():
    # Indices are protocol slots, never target layout values.
    names = ['B_' + re.sub('[^A-Za-z0-9]', '_', key).upper() for key in KEYS]
    return 'enum BindingKey {\n' + ',\n'.join(names) + ',\nB_COUNT\n};\n'


def validate_recipe(recipe):
    """Optional private selector: root pointer -> pointer reads -> Location vtable.

    This is observation only. Never accept a captured heap address or silently
    pick an arbitrary row. Evidence must be hash-bound inside the private tree.
    """
    require(set(recipe) == {'global_rva', 'offsets', 'vtable_rva', 'evidence', 'rationale'}, 'LOCATION_RECIPE_SHAPE')
    require(recipe['rationale'].strip(), 'LOCATION_RECIPE_RATIONALE')
    require(number(recipe['global_rva']) > 0 and number(recipe['vtable_rva']) > 0, 'LOCATION_RECIPE_ROOT')
    require(type(recipe['offsets']) is list and 0 < len(recipe['offsets']) <= 16, 'LOCATION_RECIPE_DEPTH')
    for value in recipe['offsets']: number(value)
    require(recipe['evidence'], 'LOCATION_RECIPE_EVIDENCE')
    for rel, sha in recipe['evidence'].items():
        p = (PRIVATE / rel).resolve()
        require(p.is_relative_to(PRIVATE.resolve()) and digest(ignored(p)) == sha, 'LOCATION_RECIPE_EVIDENCE_DRIFT')
    return dict(recipe, global_rva=number(recipe['global_rva']),
                vtable_rva=number(recipe['vtable_rva']),
                offsets=[number(v) for v in recipe['offsets']])
