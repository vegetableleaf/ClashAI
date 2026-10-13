"""Evidence-bound outcome review. Never changes the binding or enables execution."""
import argparse
from pathlib import Path
from common import STAGES, BOUNDARY, SITES, require, ignored, read_json, write_json, verify_hashes, digest


def validate_result(result):
    require(result['schema_version'] == 1 and result['runtime_version'] == '160402012', 'RESULT_VERSION')
    require(result['policy'] == {'client_launched': False, 'bridge_writes': 0, 'code_patches': 0,
            'environment_spoofing': False, 'unpacking': False, 'patches_qualified': 0}, 'RESULT_POLICY')
    require(result['status'] in ('blocked', 'collected'), 'RESULT_STATUS')
    require(type(result['events']) is list and type(result['receipts']) is dict, 'RESULT_SHAPE')
    require(result['returncode'] is None or type(result['returncode']) is int, 'RESULT_RETURN_CODE')


def complete_sequence(result):
    expected = []
    for stage in STAGES:
        expected.extend(((stage, 'before'), (stage, 'after')))
        if stage in ('jni_on_load', 'native_libraries_loaded', 'application_create', 'create_game_main'):
            expected.append((stage, 'observation'))
    expected.extend(((BOUNDARY, 'before'), (BOUNDARY, 'boundary')))
    actual = [(e['stage'], e['event']) for e in result['events']]
    if actual != expected: return False
    if len({e['pid'] for e in result['events']}) != 1: return False
    if any(e['token'] != result['token'] for e in result['events']): return False
    bases = []
    for e in result['events']:
        if e['event'] != 'observation': continue
        v = e['value']
        if set(v) != {'module_base', 'jni_delta', 'game_main', 'game_main_status', 'atomic'}: return False
        if not isinstance(v['module_base'], str) or not v['module_base'].isdigit() or int(v['module_base']) <= 0: return False
        bases.append(v['module_base'])
        if v['jni_delta'] != result['identity']['expected_jni_delta'] or v['atomic'] is not False: return False
        if v['game_main_status'] not in ('unreadable', 'absent', 'identified', 'unverified_pointer'): return False
        if v['game_main_status'] == 'identified':
            if not isinstance(v['game_main'], str) or not v['game_main'].isdigit() or int(v['game_main']) <= 0: return False
        elif v['game_main'] is not None: return False
    return len(set(bases)) == 1


def finding_check(finding, result, out):
    require(finding['kind'] in ('libg_refusal', 'rendering_dependency'), 'FINDING_KIND')
    require(finding['origin'] == 'libg' and finding['reviewer'].strip() and finding['rationale'].strip(), 'ATTRIBUTION_REQUIRED')
    require(finding['result_sha256'] == digest(out / 'result.json'), 'FINDING_RESULT_DRIFT')
    evidence = finding['evidence']
    require(evidence['file'] in result.get('host_output', {}).values(), 'FINDING_NOT_HOST_OUTPUT')
    require(evidence['sha256'] == result['receipts'][evidence['file']], 'FINDING_EVIDENCE_DRIFT')
    lines = (out / evidence['file']).read_text(encoding='utf-8', errors='replace').splitlines()
    start, end = evidence['line_start'], evidence['line_end']
    require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), 'FINDING_LINES')
    require(evidence['excerpt'].strip() and '\n'.join(lines[start - 1:end]) == evidence['excerpt'], 'FINDING_EXCERPT')
    require('HOST_' not in evidence['excerpt'], 'HOST_FAILURE_NOT_LIBG_REFUSAL')
    require(result['returncode'] not in (None, 0), 'NO_RUNTIME_FAILURE_TO_ATTRIBUTE')
    require(finding['stage'] == result['failure_stage'], 'FINDING_STAGE_MISMATCH')
    if finding['kind'] == 'rendering_dependency':
        require(finding['site_group'] in SITES, 'FINDING_SITE_GROUP')
        require(type(finding['site_ids']) is list and finding['site_ids'] and
                len(set(finding['site_ids'])) == len(finding['site_ids']) and
                set(finding['site_ids']).issubset(SITES[finding['site_group']]), 'FINDING_SITE_IDS')
        require(finding['site_mapping_basis'].strip(), 'FINDING_SITE_BASIS_REQUIRED')


def assess(result, out, finding=None):
    validate_result(result)
    if result['receipts']: verify_hashes(result['receipts'], out)
    answer = {'schema_version': 1, 'classification': 'unclassified', 'stop_required': True,
              'last_completed': result['last_completed'], 'failure_stage': result['failure_stage'],
              'libg_loaded': any(e['stage'] == 'jni_on_load' and e['event'] == 'after' for e in result['events']),
              'reason': 'A crash, timeout, obfuscated exception, missing JNI method or null pointer does not establish cause.',
              'required_sites': [], 'upstream_site_groups': SITES, 'patches_qualified': 0,
              'target_site_requirement_proven': False, 'runtime_evidence': bool(result['events'])}
    host_text = ''
    for name in result.get('host_output', {}).values():
        host_text += (out / name).read_text(encoding='utf-8', errors='replace')
    if result['host_error'] or result['status'] == 'blocked' or 'HOST_UNSUPPORTED_CALLBACK:' in host_text:
        answer.update(classification='blocked', reason='Host precondition, isolation, artifact or unsupported callback failed; do not infer a libg refusal.')
    elif result['isolation_before'] is None or result['isolation_after'] is None or result['identity'] is None:
        answer.update(classification='blocked', reason='Missing isolation or identity receipt.')
    elif finding is not None:
        finding_check(finding, result, out)
        answer.update(classification='b' if finding['kind'] == 'libg_refusal' else 'c',
                      reason=finding['rationale'], manual_attribution=finding)
        if answer['classification'] == 'c':
            answer['required_sites'] = finding['site_ids']
            answer['site_attribution'] = 'manual source/runtime attribution, not independent patch qualification'
    elif result['returncode'] == 0 and not result['timeout'] and complete_sequence(result):
        answer.update(classification='a', stop_required=False,
                      reason='libg loaded and the normal minimal init calls returned; stopped before direct resources and patch-dependent GameMain init.')
    return answer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path)
    p.add_argument('--finding', type=Path)
    args = p.parse_args()
    out = ignored(args.run)
    result = read_json(out / 'result.json')
    finding = read_json(ignored(args.finding)) if args.finding else None
    reviewed = assess(result, out, finding)
    name = 'review-attributed.json' if finding else 'review-rechecked.json'
    write_json(out / name, reviewed)
    print('JNIHOST_RO_' + reviewed['classification'].upper() + ': zero patches qualified')


if __name__ == '__main__': main()
