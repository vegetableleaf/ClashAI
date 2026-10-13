"""Offline syntax/privacy/coverage checks. No target, build, ADB or network."""
import ast
import json
from pathlib import Path
import re

from qualify import HERE, PRIVATE, REQUIRED, SITE_NAMES, binding_load, ignored
from review import validate_result
from qualify import new_result


def leaked(text):
    return bool(re.search(r'\b0x[0-9a-fA-F]+\b', text))


def main():
    assert leaked('address ' + '0' + 'x123456'), 'Address detection positive control'
    b, x = binding_load(PRIVATE / 'runtime-160402012-x86_64.json')
    assert len(REQUIRED) == 18
    # Count the already-proven site's actual classification, not a guessed vocabulary.
    proven = next(s for s in b['patch_sites'] if s['id'] == 'renderer_resolution_call')
    assert all(s['classification'] != proven['classification'] for s in b['patch_sites'] if s is not proven)
    assert len(b['patch_sites']) - 1 == 10
    assert all(not s.get('qualified') and not s.get('patch_approved') for s in b['patch_sites'])
    for file in HERE.iterdir():
        if not file.is_file() or file.suffix not in ('.py', '.c', '.sh', '.md', '.json'):
            continue
        text = file.read_text(encoding='utf-8')
        assert not leaked(text), 'Public private-address leakage'
        if file.suffix == '.py':
            ast.parse(text)
        if file.suffix == '.sh':
            assert b'\r' not in file.read_bytes(), 'Shell CRLF'
    readme = (HERE / 'README.md').read_text()
    for name in REQUIRED + SITE_NAMES:
        assert '`' + name + '`' in readme, 'Missing plan coverage'
    native = (HERE / 'observer.c').read_text()
    # Lexical audit plus compiler-import audit on VM; not a semantic proof.
    for forbidden in ('ptrace(', 'pwrite(', 'process_vm_writev(', 'mprotect(', 'dlopen(', 'socket(', 'connect('):
        assert forbidden not in native
    assert 'O_WRONLY' not in native and 'O_RDWR' not in native
    assert native.count('O_RDONLY | O_CLOEXEC') == 2
    assert 'ORACLE_READ_ONLY' in native
    validate_result(new_result('a' * 64))
    schema = json.loads((HERE / 'results.schema.json').read_text())
    assert set(schema['properties']['probes']['items']['properties']['id']['enum']) == set(REQUIRED)
    assert set(schema['properties']['sites']['items']['properties']['id']['enum']) == set(SITE_NAMES)
    ignored(PRIVATE / 'v4-readonly.json')
    print('QUALIFY_PRIVACY_OK')


if __name__ == '__main__':
    main()
