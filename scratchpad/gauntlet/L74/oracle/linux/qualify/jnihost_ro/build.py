"""Offline private-copy build. No downloads, target execution or APK extraction."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from common import HERE, ROOT, BUILD, require, ignored, load_inputs, digest, write_json, isolated

UPSTREAM = ROOT / 'research/ext/cr-native-sandbox/android_probe'
DENY_CLASSES = ('ApplicationUtilBase', 'QuagoManager', 'BatteryMonitor', 'ThermalMonitor', 'SnowplowTitan')


def deny_callbacks(source, name):
    # These reviewed upstream sources have simple method bodies. Work backwards
    # so replacements do not change earlier match positions. Native descriptors
    # remain untouched; calling an unsupported host callback must STOP.
    pattern = re.compile(r'^    public (?![^\n]*\bnative\b)[^;={}]+\([^;{}]*\)\s*\{', re.M)
    matches = list(pattern.finditer(source))
    require(bool(matches), 'CALLBACK_SOURCE_DRIFT')
    for match in reversed(matches):
        start = match.end()
        depth, end = 1, start
        while depth:
            require(end < len(source), 'CALLBACK_PARSE_FAILED')
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        method = re.search(r'(\w+)\s*\(', match.group())[1]
        message = name + '.' + method
        source = source[:start] + '\n        throw royale.nativehost.JniHost.unsupportedCallback("' + message + '");\n    ' + source[end - 1:]
    source = source.replace('m_cachedAndroidId = "headless-native-host"', 'm_cachedAndroidId = null')
    return source


def prepare(build):
    build = ignored(build)
    require(not build.exists(), 'BUILD_EXISTS_RETAINED')
    b, manifest, values, inputs = load_inputs()
    require(UPSTREAM.is_dir(), 'UPSTREAM_MISSING')
    upstream_hashes = {str(p.relative_to(ROOT)): digest(p) for p in sorted(UPSTREAM.rglob('*')) if p.is_file()}
    build.mkdir(parents=True, mode=511 if sys.platform == 'win32' else 448)
    shutil.copytree(UPSTREAM, build / 'android_probe')
    java = build / 'android_probe/java'
    shutil.copyfile(HERE / 'JniHost.java', java / 'royale/nativehost/JniHost.java')
    app = java / 'com/supercell/titan/GameApp.java'
    source = app.read_text(encoding='utf-8')
    old = 'public static boolean isEmulator() {\n        return false;\n    }'
    require(source.count(old) == 1, 'EMULATOR_CALLBACK_SOURCE_DRIFT')
    # Truthful for the required AOSP emulator, not an environment disguise.
    source = source.replace(old, old.replace('false', 'true'))
    apk_path = 'public static String getAPKPath() {\n        return "";\n    }'
    require(source.count(apk_path) == 1, 'APK_CALLBACK_SOURCE_DRIFT')
    source = source.replace(apk_path, 'public static String getAPKPath() {\n'
                            '        if (instance == null) throw royale.nativehost.JniHost.unsupportedCallback("GameApp.getAPKPath");\n'
                            '        return instance.getApplicationInfo().sourceDir;\n    }')
    app.write_text(source, encoding='utf-8', newline='\n')
    for name in DENY_CLASSES:
        p = java / ('com/supercell/titan/' + name + '.java')
        p.write_text(deny_callbacks(p.read_text(encoding='utf-8'), name), encoding='utf-8', newline='\n')
    shutil.copyfile(HERE / 'observer.cpp', build / 'observer.cpp')
    header = ''.join('#define ' + key + ' ' + str(value) + 'ULL\n' for key, value in zip(
        ('EXPECTED_JNI_DELTA', 'GAME_MAIN_GLOBAL', 'GAME_MAIN_VTABLE'), values))
    (build / 'private_binding.h').write_text(header, encoding='utf-8', newline='\n')
    return {'schema_version': 1, 'inputs': inputs, 'upstream': upstream_hashes,
            'sources': {p.name: digest(p) for p in HERE.iterdir() if p.suffix in ('.py', '.java', '.cpp', '.sh')},
            'libg_sha256': b['libg_sha256'], 'jni_delta': str(values[0]),
            'upstream_bridge_compiled': False, 'environment_callback_policy': 'truthful_emulator_other_device_callbacks_fail_closed'}


def compile_build(build, sdk, jdk):
    receipt = prepare(build)
    win = sys.platform == 'win32'
    suffix = '.exe' if win else ''
    ndk = sdk / 'ndk/27.3.13750724/toolchains/llvm/prebuilt' / ('windows-x86_64' if win else 'linux-x86_64') / 'bin'
    jar = sdk / 'platforms/android-35/android.jar'
    d8 = sdk / 'cmdline-tools/latest/lib/r8.jar'
    require(all(p.exists() for p in (ndk / ('clang++' + suffix), jdk / ('bin/javac' + suffix), jar, d8)), 'OFFLINE_TOOLCHAIN_MISSING')
    classes = build / 'classes'
    classes.mkdir()
    commands = [
        [str(ndk / ('clang++' + suffix)), '--target=x86_64-linux-android32', '-std=c++17', '-shared', '-fPIC',
         '-O2', '-Wall', '-Wextra', '-Werror', '-static-libstdc++', '-DORACLE_READ_ONLY=1', '-Wl,-z,defs',
         str(build / 'observer.cpp'), '-ldl', '-o', str(build / 'libjnihost_ro.so')],
        [str(jdk / ('bin/javac' + suffix)), '--release', '8', '-classpath', str(jar), '-d', str(classes)] +
        [str(p) for p in sorted((build / 'android_probe/java').rglob('*.java'))],
    ]
    with (build / 'build.log').open('xb') as log:
        for command in commands:
            subprocess.run(command, stdout=log, stderr=log, check=True, timeout=120)
        dex_command = [str(jdk / ('bin/java' + suffix)), '-cp', str(d8), 'com.android.tools.r8.D8',
                       '--min-api', '32', '--lib', str(jar), '--output', str(build / 'jnihost-ro.jar')] + \
                      [str(p) for p in sorted(classes.rglob('*.class'))]
        subprocess.run(dex_command, stdout=log, stderr=log, check=True, timeout=120)
    imports = subprocess.check_output([str(ndk / ('llvm-nm' + suffix)), '-u', str(build / 'libjnihost_ro.so')], timeout=30).decode()
    (build / 'imports.txt').write_text(imports, encoding='utf-8')
    require(not re.search(r'\b(mprotect|ptrace|pwrite|process_vm_writev|socket|connect|sendto|memcpy|memset)\b', imports), 'FORBIDDEN_IMPORT')
    exports = subprocess.check_output([str(ndk / ('llvm-nm' + suffix)), '-D', '--defined-only', str(build / 'libjnihost_ro.so')], timeout=30).decode()
    (build / 'exports.txt').write_text(exports, encoding='utf-8')
    require(re.findall(r'\bJava_\w+', exports) == ['Java_royale_nativehost_JniHost_nativeRead'], 'UNEXPECTED_BRIDGE_API')
    dynamic = subprocess.check_output([str(ndk / ('llvm-readelf' + suffix)), '-d', str(build / 'libjnihost_ro.so')], timeout=30).decode()
    require(set(re.findall(r'Shared library: \[([^]]+)\]', dynamic)).issubset({'libdl.so', 'libm.so', 'libc.so'}), 'NON_SYSTEM_OBSERVER_DEPENDENCY')
    (build / 'dynamic.txt').write_text(dynamic, encoding='utf-8')
    receipt['artifacts'] = {p: digest(build / p) for p in ('libjnihost_ro.so', 'jnihost-ro.jar', 'private_binding.h', 'imports.txt', 'exports.txt', 'dynamic.txt')}
    receipt['commands'] = commands + [dex_command]
    receipt['runtime_tested'] = False
    write_json(build / 'build.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir', type=Path, default=BUILD)
    p.add_argument('--sdk', type=Path, default=Path(os.environ.get('ANDROID_SDK_ROOT', str(Path.home() / 'Android/Sdk'))))
    p.add_argument('--jdk', type=Path, default=Path(os.environ.get('JAVA_HOME', '/usr/lib/jvm/java-17-openjdk-amd64')))
    p.add_argument('--offline-compile-only', action='store_true', help='local compile only; no target or SDK downloads')
    a = p.parse_args()
    if not a.offline_compile_only: isolated()
    compile_build(a.build_dir.resolve(), a.sdk.resolve(), a.jdk.resolve())
    print('JNIHOST_RO_BUILD_OK (runtime untested)')


if __name__ == '__main__':
    try: main()
    except Exception:
        print('BUILD_BLOCKED: retain private build.log; no retry or target execution performed', file=sys.stderr)
        raise SystemExit(1)
