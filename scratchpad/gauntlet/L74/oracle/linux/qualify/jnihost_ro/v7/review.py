"""Review the actual single-attempt transcript; never authorize a retry."""
import argparse
import re
from pathlib import Path
from common import (HERE, LIMITS, STAGES, NATIVE_STAGES, BOUNDARY, SITES, STAGE_GROUPS,
                    selected_stages, require, ignored, read_json, write_json, verify_hashes, digest)
from run import events_from, calls_from

CALL_NAMES = {
    'create_game_main': {'CreateGameMain'},
    'game_main_init': {'GameMain::init'},
    'data_tables_range': {'DataTables::loadRange'},
    'data_load_tasks': {'DataLoadTask::start', 'DataLoadTask::complete', 'DataLoadTask::pump'},
    'loading_state': {'LoadingState::update', 'LoadingState::complete'},
    'map_resources': {'Location::FileName', 'Location::TileDataFileName', 'ResourceRequest::constructor',
                      'ResourceRequest::append_primary', 'ResourceRequest::append_secondary',
                      'ResourceRequest::load', 'resolve_primary', 'resolve_secondary'},
    'battlefield_cache': {'battlefield_cache_root', 'DataRow::instanceId', 'build_battlefield_cache',
                          'Location::battlefield', 'ResourceRequest::destructor'},
    'manager_update': {'Manager::update'},
}
FIXED_CALLS = {
    'create_game_main': ['CreateGameMain'], 'game_main_init': ['GameMain::init'],
    'data_tables_range': ['DataTables::loadRange'],
    'map_resources': ['Location::FileName', 'Location::TileDataFileName', 'ResourceRequest::constructor',
                      'ResourceRequest::append_primary', 'ResourceRequest::append_secondary',
                      'ResourceRequest::load', 'resolve_primary', 'resolve_secondary'],
    'battlefield_cache': ['battlefield_cache_root', 'DataRow::instanceId', 'build_battlefield_cache',
                          'Location::battlefield', 'ResourceRequest::destructor'],
    'manager_update': ['Manager::update'],
}


def validate_result(r):
    import jsonschema
    jsonschema.validate(r, read_json(HERE / 'results.schema.json'))


def timestamp(row):
    require(all(isinstance(row.get(k), str) and re.fullmatch('[0-9]+', row[k])
                for k in ('monotonic_ns', 'elapsed_ns')), 'EVENT_TIME')
    require(int(row['elapsed_ns']) <= int(row['monotonic_ns']), 'EVENT_DURATION')
    return int(row['monotonic_ns'])


def observation(v, identity):
    require(isinstance(v, dict) and v.get('atomic') is False, 'OBSERVATION_SHAPE')
    require(v.get('jni_delta') == identity['expected_jni_delta'] and
            isinstance(v.get('module_base'), str) and v['module_base'].isdigit() and int(v['module_base']) > 0,
            'OBSERVATION_IDENTITY')
    require(v.get('game_main_status') in ('unreadable', 'absent', 'identified', 'unverified_pointer'), 'OBSERVATION_GAME_STATUS')
    if v['game_main_status'] == 'identified':
        require(isinstance(v.get('game_main'), str) and v['game_main'].isdigit() and int(v['game_main']) > 0,
                'OBSERVATION_GAME_POINTER')
    else: require(v.get('game_main') is None, 'OBSERVATION_UNVERIFIED_POINTER')
    require(v.get('tables_ready') is None or type(v['tables_ready']) is bool, 'OBSERVATION_TABLES')
    require(v.get('loading_phase') is None or type(v['loading_phase']) is int, 'OBSERVATION_PHASE')


def sequence(r, text):
    """Validate a complete prefix plus at most one failing stage, in raw order."""
    import json
    selected = selected_stages(r['stage_limit'])
    completed, stage_rows, native_calls, all_rows = [], {}, {}, []
    active = None
    pending_call = None
    last_time = -1
    pid = None
    boundary = False
    errored = False
    for line in text.splitlines():
        is_call = line.startswith('ORACLE_V7_CALL ')
        if not is_call and not line.startswith('ORACLE_V7 '): continue
        row = json.loads(line.split(' ', 1)[1])
        require(row['token'] == r['token'] and row['schema_version'] == 7 and
                type(row['pid']) is int and row['pid'] > 0, 'TRANSCRIPT_IDENTITY')
        if pid is None: pid = row['pid']
        require(row['pid'] == pid, 'TRANSCRIPT_PID')
        t = timestamp(row); require(t >= last_time, 'TRANSCRIPT_TIME_ORDER'); last_time = t
        name, event = row['stage'], row['event']
        require(not boundary and not errored, 'EVENT_AFTER_STOP')
        if is_call:
            require(name == active and name in NATIVE_STAGES and row['call'] in CALL_NAMES[name], 'CALL_STAGE')
            native_calls.setdefault(name, [])
            if event == 'before':
                require(pending_call is None, 'CALL_OVERLAP'); pending_call = row['call']
            else:
                require(event == 'after' and pending_call == row['call'], 'CALL_PAIR')
                native_calls[name].append(row['call']); pending_call = None
        elif event == 'before':
            require(active is None and pending_call is None, 'STAGE_OVERLAP')
            expected = selected[len(completed)] if len(completed) < len(selected) else BOUNDARY
            require(name == expected, 'STAGE_ORDER_OR_CEILING')
            active = name; stage_rows[name] = [row]
        else:
            require(name == active, 'EVENT_STAGE_MISMATCH')
            stage_rows[name].append(row)
            if event.startswith('observation'):
                observation(row['value'], r['identity'])
            if event == 'after':
                require(pending_call is None, 'STAGE_WITH_UNFINISHED_CALL')
                # JNI load observation follows its after marker; keep stage open.
                if name != 'jni_on_load': completed.append(name); active = None
            if name == 'jni_on_load' and event == 'observation':
                require([e['event'] for e in stage_rows[name]] == ['before', 'after', 'observation'], 'LOAD_SEQUENCE')
                completed.append(name); active = None
            if event == 'boundary':
                require(name == BOUNDARY and completed == list(selected) and row['value'] == r['stage_limit'], 'BOUNDARY')
                boundary = True; active = None
            if event == 'error': errored = True
        all_rows.append(row)
    for name in completed:
        rows = stage_rows[name]
        events = [e['event'] for e in rows]
        if name in STAGES[:3]: require(events == ['before', 'after'], 'LOAD_STAGE_SEQUENCE')
        elif name in NATIVE_STAGES:
            expected = ['before', 'observation_before']
            if name == 'create_game_main': expected += ['arguments']
            expected += ['native_return', 'observation', 'after']
            require(events == expected, 'NATIVE_STAGE_SEQUENCE')
            require(rows[-1]['value'] == {'success': True}, 'STAGE_SUCCESS')
            require(rows[-2]['value']['game_main_status'] == 'identified', 'STAGE_GAME_MISSING')
            if name not in ('create_game_main', 'game_main_init'):
                require(rows[-2]['value']['tables_ready'] is True, 'STAGE_TABLES_NOT_READY')
            if name in ('map_resources', 'battlefield_cache', 'manager_update'):
                require(all(int(rows[-2]['value'][k]) > 0 for k in
                            ('location', 'primary_payload', 'secondary_payload')), 'STAGE_MAP_PAYLOADS_MISSING')
            if name in ('battlefield_cache', 'manager_update'):
                require(all(int(rows[-2]['value'][k]) > 0 for k in ('cache', 'battlefield')) and
                        rows[-2]['value']['instance_id'] >= 0, 'STAGE_CACHE_MISSING')
            if name == 'create_game_main':
                require(rows[-3]['value'] in (None, ''), 'CREATE_MESSAGE_NOT_SUCCESS')
                require(rows[2]['value'].get('activity') is None and rows[2]['value'].get('asset_source') == 'verified_installed_apks', 'CREATE_ARGUMENTS')
            calls = native_calls.get(name, [])
            if name in FIXED_CALLS: require(calls == FIXED_CALLS[name], 'NATIVE_CALL_SEQUENCE')
            elif name == 'data_load_tasks':
                require(calls and calls[0] == 'DataLoadTask::start' and
                        calls[1:] == ['DataLoadTask::complete', 'DataLoadTask::pump'] * ((len(calls)-2)//2) + ['DataLoadTask::complete'] and
                        len(calls) <= 2048, 'TASK_CALL_SEQUENCE')
            else:
                require(calls and len(calls) % 2 == 0 and len(calls) <= 1024 and
                        calls == ['LoadingState::update', 'LoadingState::complete'] * (len(calls)//2), 'LOADING_CALL_SEQUENCE')
    if 'class_loader' in completed:
        loader = r['identity']['loader']
        require(stage_rows['class_loader'][1]['value'] == {
            'stub_loader_verified': True, 'apk_paths': ':'.join(loader['apk_paths']),
            'native_search_path': ':'.join(loader['native_search_paths']), 'preload': r['identity']['preload_enabled']}, 'LOADER_RECEIPT')
    if 'dependency_preload' in completed:
        count = stage_rows['dependency_preload'][1]['value']
        require(type(count) is int and count == len(r['identity']['preloads']) and
                (r['identity']['preload_enabled'] or count == 0), 'PRELOAD_RECEIPT')
    bases = {row['value']['module_base'] for row in all_rows if row['event'].startswith('observation')}
    require(len(bases) <= 1, 'MODULE_BASE_CHANGED')
    return completed, active, boundary, stage_rows, pending_call


def finding_check(f, r, out, blocking):
    require(f['kind'] in ('libg_refusal', 'rendering_dependency'), 'FINDING_KIND')
    require(f['origin'] == 'libg' and f['reviewer'].strip() and f['rationale'].strip(), 'FINDING_ATTRIBUTION')
    require(f['result_sha256'] == digest(out / 'result.json') and f['stage'] == blocking, 'FINDING_RESULT_STAGE')
    require(r['returncode'] not in (None, 0), 'FINDING_NO_FAILURE')
    e = f['evidence']
    allowed = list(r.get('host_output', {}).values()) + r.get('diagnostics', [])
    require(e['file'] in allowed and e['sha256'] == r['receipts'].get(e['file']), 'FINDING_RECEIPT')
    lines = (out / e['file']).read_text(encoding='utf-8', errors='replace').splitlines()
    start, end = e['line_start'], e['line_end']
    require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), 'FINDING_LINES')
    require(e['excerpt'].strip() and '\n'.join(lines[start-1:end]) == e['excerpt'] and
            'HOST_' not in e['excerpt'], 'FINDING_EXCERPT')
    if f['kind'] == 'rendering_dependency':
        require(f['site_group'] in STAGE_GROUPS.get(blocking, ()), 'FINDING_STAGE_SITE_GROUP')
        require(isinstance(f['site_ids'], list) and f['site_ids'] and
                len(set(f['site_ids'])) == len(f['site_ids']) and
                set(f['site_ids']).issubset(SITES[f['site_group']]), 'FINDING_SITE_IDS')
        require(f['site_mapping_basis'].strip(), 'FINDING_SITE_BASIS')


def assess(r, out, finding=None):
    answer = {'schema_version': 7, 'classification': 'unclassified', 'stop_required': True,
              'stage_reached': None, 'blocking_stage': None, 'last_completed': None,
              'attributed_sites': [], 'candidate_sites': [], 'stages': [],
              'patches_qualified': 0, 'target_site_requirement_proven': False,
              'runtime_evidence': False, 'reason': 'No complete runtime evidence.'}
    try:
        validate_result(r)
        verify_hashes(r['receipts'], out) if r['receipts'] else None
        if r['host_error'] or r['status'] == 'blocked':
            answer.update(classification='blocked', reason=r['host_error'] or 'Collector precondition blocked.')
            # Still retain the collected prefix when postflight failed.
        if not r.get('host_output'):
            require(not r['events'] and not r['calls'], 'EVENTS_WITHOUT_RECEIPT')
            return answer
        require(all(name in r['receipts'] for name in r['host_output'].values()), 'UNBOUND_HOST_OUTPUT')
        text = (out / r['host_output']['stdout']).read_text(encoding='utf-8', errors='replace').replace('\r', '')
        require(r['events'] == events_from(text, r['token']) and r['calls'] == calls_from(text, r['token']), 'TRANSCRIPT_DERIVATION')
        done, active, boundary, rows, pending = sequence(r, text)
        last = done[-1] if done else None
        require(last == r['last_completed'], 'LAST_COMPLETED_DRIFT')
        blocking = active if not boundary else None
        require(r['failure_stage'] == (blocking if r['returncode'] else None), 'FAILURE_STAGE_DRIFT')
        reached = [s for s in rows if s != BOUNDARY]
        answer.update(runtime_evidence=bool(rows), stage_reached=reached[-1] if reached else None,
                      last_completed=last, blocking_stage=blocking, interrupted_call=pending)
        answer['candidate_sites'] = [site for group in STAGE_GROUPS.get(blocking, ()) for site in SITES[group]]
        for name in selected_stages(r['stage_limit']):
            stage = rows.get(name, [])
            answer['stages'].append({'stage': name, 'status': 'success' if name in done else 'stopped' if stage else 'not_reached',
                'elapsed_ns': stage[-1]['elapsed_ns'] if stage else None,
                'timing_complete': name in done,
                'observations': [e for e in stage if e['event'].startswith('observation')]})
        stderr = (out / r['host_output']['stderr']).read_text(encoding='utf-8', errors='replace')
        if answer['classification'] == 'blocked': return answer
        require(r['isolation_before'] is not None and r['isolation_after'] is not None and r['identity'] is not None,
                'ISOLATION_OR_IDENTITY_MISSING')
        require(r['isolation_before']['namespace'] == r['isolation_after']['namespace'], 'ISOLATION_CHANGED')
        if 'HOST_' in text + stderr:
            answer.update(classification='blocked', reason='Host prerequisite failed; no libg refusal or rendering cause inferred.')
        elif finding is not None:
            finding_check(finding, r, out, blocking)
            answer.update(classification='b' if finding['kind'] == 'libg_refusal' else 'c',
                          reason=finding['rationale'], attribution='receipt-bound reviewer judgment',
                          attributed_sites=finding.get('site_ids', []), finding=finding)
        elif r['returncode'] == 0 and not r['timeout'] and boundary:
            answer.update(classification='a', reason='Selected stage ceiling reached. Zero patches; no later calls authorized by this review.')
        else:
            answer['reason'] = 'First incomplete stage retained. Crash, timeout or native incomplete state alone does not establish refusal or a presentation dependency.'
    except Exception as error:
        answer.update(classification='blocked', reason='Invalid/incomplete receipts: ' + type(error).__name__ + ': ' + str(error))
    return answer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path); p.add_argument('--finding', type=Path)
    args = p.parse_args(); out = ignored(args.run)
    finding = read_json(ignored(args.finding)) if args.finding else None
    answer = assess(read_json(out / 'result.json'), out, finding)
    write_json(out / ('review-attributed.json' if finding else 'review-rechecked.json'), answer)
    print('ORACLE_V7_' + answer['classification'].upper() + ': STOP; zero patches')
    return 0 if answer['classification'] in ('a', 'b', 'c') else 78


if __name__ == '__main__': raise SystemExit(main())
