"""Offline privacy and no-patch source checks, with positive controls."""
import ast
import re
from common import HERE, PRIVATE, ROOT, ignored, load_inputs
from binding import ENTRIES, FIELDS, project, header


def leaked(text):
    return bool(re.search(r'\b0x[0-9a-fA-F]+\b', text))


def observer_safe(text):
    forbidden = ('mprotect(', 'pwrite(', 'ptrace(', 'process_vm_writev(', 'socket(', 'connect(',
                 'O_RDWR', 'O_WRONLY', '__atomic_store', 'memcpy(', 'memset(',
                 '*reinterpret_cast<uint8_t*>', 'JNI_OnLoad(')
    return not any(word in text for word in forbidden) and text.count('dlopen(') == 1 and \
        'RTLD_NOW | RTLD_LOCAL | RTLD_NOLOAD' in text and 'O_RDONLY | O_CLOEXEC' in text


def main():
    b, _, _, _ = load_inputs()
    runtime = project(b)
    addresses = [int(b['entries'][k]['rva'], 0) for k in ENTRIES]
    addresses += [int(b['fields'][k]['rva'], 0) for k in FIELDS if 'rva' in b['fields'][k]]
    for p in HERE.iterdir():
        if p.suffix not in ('.py', '.cpp', '.java', '.sh', '.md', '.json'): continue
        text = p.read_text(encoding='utf-8')
        assert not leaked(text), p.name + ': public hex literal'
        assert not any(re.search(r'\b' + str(v) + r'\b', text) for v in addresses), p.name + ': public address'
        assert b['libg_sha256'] not in text, p.name + ': target identity'
        if p.suffix == '.py': ast.parse(text)
        if p.suffix == '.sh': assert b'\r' not in p.read_bytes(), p.name + ': CRLF'
    assert leaked('0' + 'x123456'), 'privacy positive control'
    native = (HERE / 'observer.cpp').read_text()
    assert observer_safe(native)
    assert not observer_safe(native + '\nmprotect();'), 'write detector positive control'
    java = (HERE / 'JniHost.java').read_text() + (HERE / 'AppLibraryLoader.java').read_text()
    for forbidden in ('com.supercell', 'dzmxszrox', 'ActivityThread', 'createPackageContext',
                      'new Activity', 'new Application', 'new Surface', 'setDeviceVerificationResult',
                      'Runtime.getRuntime().exec', 'ServerSocket', 'nOnCreate(', 'nOnStart(', 'nOnResume('):
        assert forbidden not in java, 'client lifecycle or environment API'
    assert 'private_binding.h' not in native and 'binding_keys.h' in native
    assert not any(str(v) in header() for v in addresses)
    assert len(runtime['keys']) == len(runtime['values']) and len(set(runtime['keys'])) == len(runtime['keys'])
    ignored(PRIVATE / 'runtime-160402012-x86_64.json')
    ignored(HERE.parents[3] / '.local/jnihost-ro-build-v7/runtime-binding.json')
    # The original v6 kit stays byte-for-byte available as a regression oracle.
    print('ORACLE_V7_PRIVACY_OK')


if __name__ == '__main__': main()
