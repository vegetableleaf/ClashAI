"""Read-only deployment assessment. Never loads a module or emits private values.

This checkout has no qualified target bridge/launcher. A manifest alone cannot
enable deployment. Exit 78 is intentional until the implementation is ported.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIVATE = HERE.parents[3] / 'scratchpad/gauntlet/L70/reader/oracle_160402012'
REQUIRED = (
    'jni_on_load', 'create_game_main', 'game_main_init',
    'data_tables_load_range', 'data_load_task_start', 'data_load_task_pump',
    'data_load_task_complete', 'loading_state_update', 'loading_state_complete',
    'resource_request_list_constructor', 'resource_request_list_append',
    'resource_request_list_load', 'build_battlefield_cache', 'manager_update',
    'battle_load_replay', 'state_factory', 'battle_core_update',
    'skip_core_and_presentation_flag',
)
SITE_NAMES = (
    'renderer_bootstrap_call', 'renderer_device_block', 'renderer_resolution_call',
    'renderer_objects_block', 'renderer_late_configure_call',
    'loading_presentation_call', 'loading_platform_ui_call',
    'game_presentation_toggle', 'home_resolution_block',
    'home_graphics_create_call', 'headless_resource_variant',
)


def assess(binding):
    missing = []
    if not isinstance(binding, dict):
        return ['binding_schema', 'target_bridge_and_launcher']
    if (binding.get('runtime_version'), binding.get('abi')) != ('160402012', 'x86_64'):
        missing.append('target_identity')
    entries = binding.get('entries', {})
    if not isinstance(entries, dict):
        entries = {}
    for name in REQUIRED:
        row = entries.get(name, {})
        locator = row.get('locator', {}) if isinstance(row, dict) else {}
        indirect_flag = (name == 'skip_core_and_presentation_flag' and
                         isinstance(locator, dict) and
                         locator.get('kind') == 'indirect_global_pointer_plus_offset' and
                         locator.get('global_pointer_rva') and locator.get('member_offset') and
                         locator.get('width') == 1 and row.get('rva') is None)
        if not isinstance(row, dict) or not (
            (row.get('rva') or indirect_flag) and row.get('confidence') in
            ('high_static_identity', 'high_static_structural', 'high_runtime')
            and row.get('evidence')
        ):
            missing.append(name)
    flag = entries.get('skip_core_and_presentation_flag', {})
    if not isinstance(flag, dict) or flag.get('live_storage_confidence') != 'verified':
        missing.append('scheduling_flag_live_storage_and_lifetime')
    state = entries.get('state_factory', {})
    if not isinstance(state, dict) or state.get('battle_type') is None:
        missing.append('battle_state_type')
    sites = binding.get('patch_sites', [])
    if not isinstance(sites, list):
        sites = []
    by_name = {s.get('name'): s for s in sites if isinstance(s, dict)}
    for name in SITE_NAMES:
        row = by_name.get(name, {})
        patch = (row.get('qualified') is True and
                 row.get('no_battle_state_writes_proven') is True and
                 row.get('original_bytes') and row.get('replacement_bytes'))
        alternative = row.get('alternative', {})
        alternative = (isinstance(alternative, dict) and
                       alternative.get('qualified') is True and
                       alternative.get('evidence'))
        if not (patch or alternative):
            missing.append('site:' + name)
    # Deliberately independent of a mutable JSON deployable flag. The upstream
    # C++ bridge is hardcoded for a different version, and no launcher is ported.
    missing.append('target_bridge_and_launcher')
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', type=Path,
                        default=PRIVATE / 'runtime-160402012-x86_64.json')
    args = parser.parse_args()
    try:
        binding = json.loads(args.binding.read_text(encoding='utf-8'))
        missing = assess(binding)
    except (OSError, ValueError, TypeError):
        missing = ['binding_unreadable_or_invalid', 'target_bridge_and_launcher']
    print('BLOCKED_BINDING_INCOMPLETE: ORACLE v3 is not deployable.')
    print('Scheduling/control DATA writes and unmodified native calls are allowed.')
    print('Missing qualification: ' + ', '.join(missing))
    print('See V3_REPORT.md for evidence and the observation plan. No override is provided.')
    return 78


if __name__ == '__main__':
    raise SystemExit(main())
