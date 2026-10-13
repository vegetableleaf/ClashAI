"""Offline verification of the stopped investigation, not native acceptance."""
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRIVATE = ROOT / 'scratchpad/gauntlet/L70/reader/oracle_160402012'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    binding = json.loads((PRIVATE / 'runtime-160402012-x86_64.json').read_text())
    evidence = json.loads((PRIVATE / 'v2_evidence.json').read_text())
    assert binding['runtime_version'] == '160402012'
    assert binding['deployable'] is False
    assert all(p['qualified'] is False and p['rva'] is None and
               p['no_battle_state_writes_proven'] is False for p in binding['patch_sites'])
    assert len(binding['patch_sites']) == 11
    assert not any(evidence['execution'].values())
    symbols = json.loads((PRIVATE / 'v2_dynamic_symbols.json').read_text())
    symbols = {s['name']: s for s in symbols['matches']}
    assert binding['version_guard']['expected_jni_on_load_rva'] == symbols['JNI_OnLoad']['value']
    assert binding['entries']['create_game_main']['rva'] == symbols[
        'Java_com_supercell_titan_GameApp_createGameMain']['value']
    bridge = ROOT / 'research/ext/cr-native-sandbox/android_probe/native/jni_bridge.cpp'
    assert digest(bridge) == evidence['stop']['source_sha256']
    for name, expected in evidence['export_hashes'].items():
        assert digest(PRIVATE.parent / 'redump/out/20261012T231715Z_da6737b4/analysis/export' / name) == expected
    for name, expected in evidence['evidence_files'].items():
        assert digest(PRIVATE / name) == expected
    tracked = subprocess.run(['git', 'ls-files', '--', str(PRIVATE)], cwd=ROOT,
                             capture_output=True, text=True, check=True)
    assert not tracked.stdout.strip(), 'Private evidence is tracked'
    for path in PRIVATE.iterdir():
        if path.is_file():
            subprocess.run(['git', 'check-ignore', '-q', str(path)], cwd=ROOT, check=True)
    public = [HERE / n for n in ['V2_REPORT.md', 'GATES_V2.md', 'PORT.md', 'ACCEPTANCE.md']]
    public += list((HERE / 'linux').glob('*.sh'))
    address_pattern = re.compile(r'\b0x[0-9a-fA-F]+\b')
    assert address_pattern.search('0' + 'x1234'), 'Address detector positive control failed'
    for path in public:
        assert not address_pattern.search(path.read_text(encoding='utf-8')), path
        if path.suffix == '.sh':
            assert b'\r' not in path.read_bytes(), path
    for path in [Path(__file__), *[PRIVATE / n for n in ['analyze_v2.py', 'leads_v2.py', 'record_v2.py']]]:
        ast.parse(path.read_text(encoding='utf-8'))
    diagnostic = (HERE / 'linux/common.sh').read_text()
    assert 'BLOCKED_TICK_CONTROL' in diagnostic
    assert 'BLOCKED_UNMODIFIED_LIBG' not in diagnostic
    for name in ['deploy.sh', 'health.sh']:
        assert (HERE / 'linux' / name).read_text().strip().endswith('blocked')
    result = dict(status='STOP_EVIDENCE_VERIFIED_NOT_A_PORT',
                  checks=['private ignored and untracked', 'public address scan with positive control',
                          'export and source hashes', 'symbol-bound partial guard', 'all patches disabled',
                          'Python AST', 'LF shell files', 'v2 stop diagnostic'],
                  native_acceptance='NOT_RUN', patch_sites_qualified=0,
                  files={p.relative_to(HERE).as_posix(): digest(p) for p in public})
    (HERE / 'VERIFICATION_V2.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('ORACLE_V2_STOP_EVIDENCE_PASS; NATIVE_NOT_RUN')

if __name__ == '__main__':
    main()
