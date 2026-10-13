"""Offline evidence/privacy and fail-closed checks; not native acceptance."""
import ast
import hashlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

from binding_status import HERE, PRIVATE, REQUIRED, SITE_NAMES, assess

ROOT = HERE.parents[3]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify():
    binding = json.loads((PRIVATE / 'runtime-160402012-x86_64.json').read_text())
    receipt = json.loads((PRIVATE / 'v3_evidence.json').read_text())
    assert binding['status'] == 'STATIC_DERIVATION_INCOMPLETE'
    assert binding['deployable'] is False
    assert binding['boundary_revision'] == 3
    assert all(name in binding['entries'] for name in REQUIRED)
    assert {s['name'] for s in binding['patch_sites']} == set(SITE_NAMES)
    assert len(binding['patch_sites']) == len(SITE_NAMES)
    for row in binding['entries'].values():
        assert row.get('confidence') and row.get('evidence')
        assert row.get('runtime_verified') is False
    for row in binding['patch_sites']:
        assert row.get('classification') and row.get('evidence')
        assert row.get('alternative') and row.get('settling_observation')
        assert row['qualified'] is False, 'No target patch was qualified in this investigation'
        assert row.get('replacement_bytes') is None
    assert not any(receipt['execution'].values())
    for relative, expected in receipt['files'].items():
        assert digest(PRIVATE / relative) == expected, relative
    for relative, expected in receipt['upstream_files'].items():
        assert digest(ROOT / 'research/ext/cr-native-sandbox' / relative) == expected, relative
    capture = PRIVATE.parent / receipt['capture_relative_to_reader']
    regions = json.loads((capture / 'dump/regions.json').read_text())['regions']
    for region in regions:
        assert digest(capture / 'dump' / region['file']) == region['sha256']
    for name, expected in receipt['export_hashes'].items():
        assert digest(capture / 'analysis/export' / name) == expected, name

    private_files = [p for p in PRIVATE.rglob('*') if p.is_file()]
    ignored = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=ROOT,
                             input=''.join(p.relative_to(ROOT).as_posix() + '\n' for p in private_files),
                             capture_output=True, text=True, check=True)
    assert len(ignored.stdout.splitlines()) == len(private_files)
    tracked = subprocess.run(['git', 'ls-files', '--', str(PRIVATE)], cwd=ROOT,
                             capture_output=True, text=True, check=True)
    assert not tracked.stdout.strip()
    public = [p for p in [*HERE.iterdir(), *(HERE / 'linux').glob('*.sh')]
              if p.is_file() and p.suffix in ('.md', '.py', '.sh', '.json')]
    address = re.compile(r'\b0x[0-9a-fA-F]+\b')
    assert address.search('0' + 'x1234'), 'Privacy positive control failed'
    for p in public:
        content = p.read_text(encoding='utf-8')
        assert not address.search(content), p
        if p.suffix == '.sh':
            assert b'\r' not in p.read_bytes(), p
        if p.suffix == '.py':
            ast.parse(content)
    for name in ['deploy.sh', 'health.sh']:
        content = (HERE / 'linux' / name).read_text()
        assert content.strip().endswith('blocked')
        assert 'BLOCKED_TICK_CONTROL' not in content
    common = (HERE / 'linux/common.sh').read_text()
    assert 'binding_status.py' in common and 'exit 78' in common
    assert 'BLOCKED_TICK_CONTROL' not in common

    # A mutable manifest cannot turn this unported checkout into a launcher.
    assert 'target_bridge_and_launcher' in assess(binding)
    spoofed = json.loads(json.dumps(binding))
    spoofed['deployable'] = True
    for row in spoofed['entries'].values():
        row.update(rva='untrusted-manifest-value', confidence='high_runtime', evidence='claimed')
    spoofed['entries']['state_factory']['battle_type'] = 1
    for row in spoofed['patch_sites']:
        row.update(qualified=True, no_battle_state_writes_proven=True,
                   original_bytes='claimed', replacement_bytes='claimed')
    assert 'target_bridge_and_launcher' in assess(spoofed)
    cases = [None, [], {}, {'entries': None, 'patch_sites': None}, spoofed, binding]
    # Windows Python's private temporary-directory ACL is incompatible with this
    # sandbox token. Use unique files in the already ignored local-state folder;
    # remove only the exact files this invocation created.
    token = uuid.uuid4().hex
    fixtures = []
    try:
        for i, value in enumerate(cases):
            path = HERE / '.local' / f'v3-case-{token}-{i}.json'
            subprocess.run(['git', 'check-ignore', '-q', str(path)], cwd=ROOT, check=True)
            path.write_text(json.dumps(value), encoding='utf-8')
            fixtures.append(path)
            result = subprocess.run([sys.executable, str(HERE / 'binding_status.py'),
                                     '--binding', str(path)], capture_output=True, text=True)
            assert result.returncode == 78, (i, result.returncode)
            assert 'BLOCKED_BINDING_INCOMPLETE' in result.stdout
            assert not address.search(result.stdout)
        invalid = HERE / '.local' / f'v3-invalid-{token}.json'
        invalid.write_text('{', encoding='utf-8')
        fixtures.append(invalid)
        for path in [invalid, HERE / '.local' / f'v3-missing-{token}.json']:
            result = subprocess.run([sys.executable, str(HERE / 'binding_status.py'),
                                     '--binding', str(path)], capture_output=True, text=True)
            assert result.returncode == 78
    finally:
        for path in fixtures:
            path.unlink()
    result = dict(status='ORACLE_V3_OFFLINE_EVIDENCE_PASS', deployable=False,
                  native_acceptance='NOT_RUN', required_entries=len(REQUIRED),
                  high_static_required_entries=sum(binding['entries'][n]['confidence'].startswith('high_static')
                                                   for n in REQUIRED),
                  sites_reviewed=len(SITE_NAMES), patches_qualified=0,
                  capture_regions_verified=len(regions),
                  manifest_negative_cases=len(cases) + 2,
                  checks=['private ignored and untracked', 'public address scan with positive control',
                          'capture, export, source and retained evidence hashes',
                          'required entries and site coverage', 'Python AST and LF shell files',
                          'Python preflight exit 78 including spoofed manifest'],
                  shell_execution='NOT_VERIFIED: Git Bash CreateFileMapping Win32 error 5',
                  shellcheck='UNAVAILABLE',
                  public_files={p.relative_to(HERE).as_posix(): digest(p) for p in public
                                if p.name != 'VERIFICATION_V3.json'})
    (HERE / 'VERIFICATION_V3.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('ORACLE_V3_OFFLINE_EVIDENCE_PASS; NATIVE_NOT_RUN; DEPLOYABLE_NO')


if __name__ == '__main__':
    (HERE / '.local').mkdir(exist_ok=True)
    verify()
