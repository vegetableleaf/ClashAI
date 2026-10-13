"""Offline two-DEX build. No downloads, target execution or APK extraction."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from common import HERE, ROOT, BUILD, require, ignored, load_inputs, digest, write_json, isolated

def prepare(build, location_recipe=None):
    build = ignored(build)
    require(not build.exists(), 'BUILD_EXISTS_RETAINED')
    b, manifest, values, inputs = load_inputs()
    build.mkdir(parents=True, mode=511 if sys.platform == 'win32' else 448)
    for name in ('JniHost.java', 'AppLibraryLoader.java', 'observer.cpp'):
        shutil.copyfile(HERE / name, build / name)
    from binding import project, header, validate_recipe
    runtime = project(b)
    if location_recipe is not None:
        from common import read_json
        location_recipe = ignored(location_recipe)
        runtime['location_recipe'] = validate_recipe(read_json(location_recipe))
        inputs[str(location_recipe.relative_to(ROOT))] = digest(location_recipe)
    write_json(build / 'runtime-binding.json', runtime)
    (build / 'binding_keys.h').write_text(header(), encoding='utf-8', newline='\n')
    return {'schema_version': 7, 'inputs': inputs,
            'sources': {p.name: digest(p) for p in HERE.iterdir() if p.suffix in ('.py', '.java', '.cpp', '.sh') or p.name == 'results.schema.json'},
            'libg_sha256': b['libg_sha256'], 'jni_delta': str(values[0]),
            'client_shells_compiled': False, 'profile': 'staged_no_patches'}


def compile_build(build, sdk, jdk, location_recipe=None):
    receipt = prepare(build, location_recipe)
    win = sys.platform == 'win32'
    suffix = '.exe' if win else ''
    ndk = sdk / 'ndk/27.3.13750724/toolchains/llvm/prebuilt' / ('windows-x86_64' if win else 'linux-x86_64') / 'bin'
    jar = sdk / 'platforms/android-35/android.jar'
    d8 = sdk / 'cmdline-tools/latest/lib/r8.jar'
    require(all(p.exists() for p in (ndk / ('clang++' + suffix), jdk / ('bin/javac' + suffix), jar, d8)), 'OFFLINE_TOOLCHAIN_MISSING')
    host_classes = build / 'host-classes'
    child_classes = build / 'child-classes'
    host_classes.mkdir()
    child_classes.mkdir()
    commands = [
        [str(ndk / ('clang++' + suffix)), '--target=x86_64-linux-android32', '-std=c++17', '-shared', '-fPIC',
         '-O2', '-Wall', '-Wextra', '-Werror', '-static-libstdc++', '-DORACLE_NO_PATCHES=1', '-Wl,-z,defs',
         str(build / 'observer.cpp'), '-ldl', '-o', str(build / 'libjnihost_ro.so')],
    ]
    for source, dest in (('JniHost.java', host_classes), ('AppLibraryLoader.java', child_classes)):
        commands.append([str(jdk / ('bin/javac' + suffix)), '--release', '8', '-classpath', str(jar),
                         '-d', str(dest), str(build / source)])
    for classes, name in ((host_classes, 'jnihost-ro.jar'), (child_classes, 'jnihost-loader.jar')):
        commands.append([str(jdk / ('bin/java' + suffix)), '-cp', str(d8), 'com.android.tools.r8.D8',
                         '--min-api', '32', '--lib', str(jar), '--output', str(build / name)] +
                        [str(classes / ('royale/nativehost/' + ('JniHost' if classes == host_classes else 'AppLibraryLoader') + '.class'))])
    with (build / 'build.log').open('xb') as log:
        for command in commands:
            subprocess.run(command, stdout=log, stderr=log, check=True, timeout=120)
    # No upstream shells or child stub in the parent DEX, no host in the child DEX.
    import zipfile
    for name, wanted, forbidden in (
            ('jnihost-ro.jar', b'Lroyale/nativehost/JniHost;', b'Lroyale/nativehost/AppLibraryLoader;'),
            ('jnihost-loader.jar', b'Lroyale/nativehost/AppLibraryLoader;', b'Lroyale/nativehost/JniHost;')):
        with zipfile.ZipFile(build / name) as archive:
            dex = archive.read('classes.dex')
        require(wanted in dex and forbidden not in dex and b'Lcom/supercell/' not in dex,
                'DEX_CLASS_OWNERSHIP')
    imports = subprocess.check_output([str(ndk / ('llvm-nm' + suffix)), '-u', str(build / 'libjnihost_ro.so')], timeout=30).decode()
    (build / 'imports.txt').write_text(imports, encoding='utf-8')
    require(not re.search(r'\b(mprotect|ptrace|pwrite|process_vm_writev|socket|connect|sendto)\b', imports), 'FORBIDDEN_IMPORT')
    exports = subprocess.check_output([str(ndk / ('llvm-nm' + suffix)), '-D', '--defined-only', str(build / 'libjnihost_ro.so')], timeout=30).decode()
    (build / 'exports.txt').write_text(exports, encoding='utf-8')
    require(set(re.findall(r'\bJava_\w+', exports)) == {'Java_royale_nativehost_AppLibraryLoader_nativeRead', 'Java_royale_nativehost_AppLibraryLoader_nativeStage'}, 'UNEXPECTED_BRIDGE_API')
    dynamic = subprocess.check_output([str(ndk / ('llvm-readelf' + suffix)), '-d', str(build / 'libjnihost_ro.so')], timeout=30).decode()
    require(set(re.findall(r'Shared library: \[([^]]+)\]', dynamic)).issubset({'libdl.so', 'libm.so', 'libc.so'}), 'NON_SYSTEM_OBSERVER_DEPENDENCY')
    (build / 'dynamic.txt').write_text(dynamic, encoding='utf-8')
    receipt['artifacts'] = {p: digest(build / p) for p in ('libjnihost_ro.so', 'jnihost-ro.jar', 'jnihost-loader.jar', 'binding_keys.h', 'runtime-binding.json', 'imports.txt', 'exports.txt', 'dynamic.txt')}
    receipt['commands'] = commands
    receipt['runtime_tested'] = False
    write_json(build / 'build.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir', type=Path, default=BUILD)
    p.add_argument('--sdk', type=Path, default=Path(os.environ.get('ANDROID_SDK_ROOT', str(Path.home() / 'Android/Sdk'))))
    p.add_argument('--jdk', type=Path, default=Path(os.environ.get('JAVA_HOME', '/usr/lib/jvm/java-17-openjdk-amd64')))
    p.add_argument('--offline-compile-only', action='store_true', help='local compile only; no target or SDK downloads')
    p.add_argument('--location-recipe', type=Path, help='optional ignored, evidence-bound Location selector')
    a = p.parse_args()
    if not a.offline_compile_only: isolated()
    compile_build(a.build_dir.resolve(), a.sdk.resolve(), a.jdk.resolve(), a.location_recipe)
    print('ORACLE_V7_BUILD_OK (runtime untested)')


if __name__ == '__main__':
    try: main()
    except Exception:
        print('BUILD_BLOCKED: retain private build.log; no retry or target execution performed', file=sys.stderr)
        raise SystemExit(1)
