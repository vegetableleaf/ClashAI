"""Offline privacy and source-boundary checks; no target or network."""
import ast
import re
from common import HERE, ROOT, PRIVATE, SITES, ignored, load_inputs


def leaked(text):
    return bool(re.search(r'\b0x[0-9a-fA-F]+\b', text))


def observer_safe(source):
    forbidden = ('mprotect(', 'pwrite(', 'ptrace(', 'process_vm_writev(', 'socket(', 'connect(',
                 'O_RDWR', 'O_WRONLY', 'memcpy(', 'memset(', 'nativeCreate', 'nativeInit', 'nativeAct')
    return not any(s in source for s in forbidden) and source.count('dlopen(') == 1 and \
        'RTLD_NOW | RTLD_LOCAL | RTLD_NOLOAD' in source and 'O_RDONLY | O_CLOEXEC' in source


def main():
    assert leaked('0' + 'x123456'), 'privacy detector positive control'
    b, _, values, _ = load_inputs()
    for p in HERE.iterdir():
        if p.suffix not in ('.py', '.cpp', '.java', '.sh', '.json', '.md'): continue
        text = p.read_text(encoding='utf-8')
        assert not leaked(text), 'public hex address'
        for v in values:
            assert not re.search(r'\b' + str(v) + r'\b', text), 'public binding value'
        assert b['libg_sha256'] not in text, 'public target hash'
        if p.suffix == '.py': ast.parse(text)
        if p.suffix == '.sh': assert b'\r' not in p.read_bytes(), 'shell CRLF'
    source = (HERE / 'observer.cpp').read_text()
    assert observer_safe(source)
    assert not observer_safe(source + '\nmprotect();'), 'mutation detector positive control'
    java = (HERE / 'JniHost.java').read_text()
    stub = (HERE / 'AppLibraryLoader.java').read_text()
    assert re.findall(r'public static native \w+ (\w+)', stub) == ['nativeRead']
    for forbidden in ('nativeInit', 'nativePump', 'nativeStep', 'nativeAct', 'nOnCreate(', 'nOnStart(',
                      'nOnResume(', 'nOnNativeLibrariesLoaded(', 'nOnApplicationCreate(', 'createGameMain(',
                      'com.supercell', 'dzmxszrox', 'ActivityThread', 'createPackageContext', 'new Surface', 'ServerSocket', 'Runtime.getRuntime().exec', 'setDeviceVerificationResult('):
        assert forbidden not in java + stub, 'forbidden host API'
    assert 'System.loadLibrary("g")' in stub
    assert 'System.load(' not in java and 'System.loadLibrary(' not in java
    assert 'stub.getClassLoader() != loader' in java
    assert 'Class.forName("royale.nativehost.AppLibraryLoader", false, loader)' in java
    readme = (HERE / 'README.md').read_text()
    for sites in SITES.values():
        for site in sites: assert '`' + site + '`' in readme
    assert len({s for sites in SITES.values() for s in sites}) == 11
    ignored(PRIVATE / 'runtime-160402012-x86_64.json')
    ignored(HERE.parents[2] / '.local/jnihost-ro-build-v6/build.json')
    print('JNIHOST_RO_PRIVACY_OK')


if __name__ == '__main__': main()
