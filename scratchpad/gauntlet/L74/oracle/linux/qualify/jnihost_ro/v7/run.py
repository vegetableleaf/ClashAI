"""One no-retry app_process qualification in the existing isolated emulator."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import uuid
import time
from common import (HERE, ROOT, BUILD, RUNS, STAGES, ALL_STAGES, LIMITS, BOUNDARY, Device, require,
                    ignored, digest, isolated, installed_check, load_inputs,
                    write_json, read_json, verify_hashes, verify_network, verify_emulator_command)


def isolation(pid, serial):
    isolated()
    links = json.loads(subprocess.check_output(['ip', '-j', 'link', 'show']))
    routes = {family: json.loads(subprocess.check_output(['ip', family, '-j', 'route', 'show', 'table', 'all']))
              for family in ('-4', '-6')}
    verify_network(links, routes['-4'] + routes['-6'])
    proc = Path('/proc') / str(pid)
    own_ns, emulator_ns = os.readlink('/proc/self/ns/net'), os.readlink(proc / 'ns/net')
    require(own_ns == emulator_ns, 'EMULATOR_OUTSIDE_NAMESPACE')
    require(proc.stat().st_uid == os.getuid(), 'EMULATOR_NOT_OWNED_BY_WORKER')
    argv = (proc / 'cmdline').read_bytes().decode().rstrip('\0').split('\0')
    verify_emulator_command(argv, serial)
    return {'namespace': own_ns, 'emulator_pid': pid, 'emulator_argv': argv, 'links': links, 'routes': routes}


def events_from(text, token):
    events = []
    for line in text.splitlines():
        if line.startswith('ORACLE_V7 '):
            row = json.loads(line[len('ORACLE_V7 '):])
            require(row.get('token') == token and type(row.get('pid')) is int and row['pid'] > 0,
                    'EVENT_IDENTITY')
            require(row.get('schema_version') == 7, 'EVENT_SCHEMA')
            require(row.get('stage') in ALL_STAGES + (BOUNDARY,), 'EVENT_STAGE')
            require(row.get('event') in ('before', 'after', 'observation', 'observation_before', 'observation_failure', 'native_return', 'arguments', 'boundary', 'error'), 'EVENT_KIND')
            events.append(row)
    require(len({e['pid'] for e in events}) <= 1, 'MULTIPLE_HOST_PIDS')
    return events


def calls_from(text, token):
    rows = []
    for line in text.splitlines():
        if not line.startswith('ORACLE_V7_CALL '): continue
        r = json.loads(line[len('ORACLE_V7_CALL '):])
        require(r.get('schema_version') == 7 and r.get('token') == token and
                type(r.get('pid')) is int and r['pid'] > 0, 'CALL_IDENTITY')
        require(r.get('stage') in LIMITS[1:] and r.get('event') in ('before', 'after') and
                isinstance(r.get('call'), str), 'CALL_SHAPE')
        rows.append(r)
    return rows


def new_result(token):
    return {'schema_version': 7, 'token': token, 'runtime_version': '160402012',
            'policy': {'client_launched': False, 'bridge_writes': 0, 'code_patches': 0,
                       'environment_spoofing': False, 'unpacking': False, 'patches_qualified': 0},
            'stage_limit': 'load-only', 'calls': [], 'status': 'blocked', 'events': [], 'last_completed': None, 'failure_stage': None,
            'collection_duration_ns': None, 'returncode': None, 'timeout': False, 'host_error': None,
            'isolation_before': None, 'isolation_after': None, 'identity': None, 'receipts': {},
            'limitation': 'Native calls may have side effects. Observer makes no target memory writes or patches. No app lifecycle, fabricated native objects, network, replay or battle calls.'}


def loader_paths(installed, info):
    paths = [r['path'] for r in installed]
    require(paths and len(paths) == len(set(paths)), 'APK_PATHS_EMPTY_OR_DUPLICATE')
    require(all(re.fullmatch(r'/data/app/[A-Za-z0-9_+=~-]+(?:/[A-Za-z0-9_.+=~-]+)*/[A-Za-z0-9_.+=~-]+\.apk', p)
                for p in paths) and not any('..' in p for p in paths), 'APK_PATH_INVALID')
    bases = [p for p in paths if p.endswith('/base.apk')]
    require(len(bases) == 1, 'APK_BASE_REQUIRED')
    parent = bases[0].rsplit('/', 1)[0]
    require(all(p.rsplit('/', 1)[0] == parent for p in paths), 'APK_INSTALL_ROOT_MISMATCH')
    dirs = re.findall(r'^\s*(?:legacyNativeLibraryDir|nativeLibraryDir)=(\S+)', info, re.M)
    # dumpsys legacyNativeLibraryDir is the root; ApplicationInfo nativeLibraryDir
    # may already have the ABI suffix. Accept either but reject disagreement.
    dirs = {d if d.endswith('/x86_64') else d + '/x86_64' for d in dirs}
    require(dirs == {parent + '/lib/x86_64'}, 'INSTALLED_NATIVE_DIRECTORY_UNAVAILABLE')
    ordered = bases + sorted(p for p in paths if p != bases[0])
    native = next(iter(dirs))
    return {'apk_paths': ordered, 'native_library_dir': native,
            'native_search_paths': [native] + [p + '!/lib/x86_64' for p in ordered]}


def preload_paths(build, enabled, device, manifest, installed, native_dir):
    if not enabled: return [], []
    order = build / 'preload.txt'
    require(order.is_file(), 'PRELOAD_REQUESTED_BUT_MISSING')
    names = [s.strip() for s in order.read_text(encoding='utf-8').splitlines() if s.strip()]
    closure = {'libc++_shared.so', 'libscid_sdk.so', 'libfmod.so', 'libfmodstudio.so',
               'libsentry.so', 'libsentry-android.so'}
    require(names and len(names) == len(set(names)) and
            set(names).issubset(closure), 'PRELOAD_NAMES_INVALID')
    paths, backing = [], []
    for name in names:
        rows = [r for r in manifest['native_libraries'] if r['member'] == 'lib/x86_64/' + name]
        require(len(rows) == 1, 'PRELOAD_NOT_IN_MANIFEST')
        row = rows[0]
        path = native_dir + '/' + name
        present, _, _ = device.capture(['shell', 'test', '-f', path], allow=(0, 1))
        if present == 0:
            require(device.call('shell', 'sha256sum', path).split()[0] == row['sha256'], 'PRELOAD_HASH')
            backing.append({'path': path, 'sha256': row['sha256']})
        else:
            apk = next(r for r in manifest['apks'] if r['name'] == row['apk'])
            matches = [r for r in installed if r['sha256'] == apk['sha256']]
            require(len(matches) == 1, 'PRELOAD_APK_AMBIGUOUS')
            path = matches[0]['path'] + '!/' + row['member']
        paths.append(path)
    return paths, backing


def select_installed_libg(device, manifest, binding, installed, info):
    libg = loader_paths(installed, info)['native_library_dir'] + '/libg.so'
    present, _, _ = device.capture(['shell', 'test', '-f', libg], allow=(0, 1))
    if present == 0:
        require(device.call('shell', 'sha256sum', libg).split()[0] == binding['libg_sha256'], 'INSTALLED_LIBG_HASH')
        return libg, libg, binding['libg_sha256'], 'package_manager_native_file'
    # Android can map an uncompressed APK member directly. Select this route
    # BEFORE the single load attempt; do not extract, decrypt or try a fallback
    # if its normal linker refuses the member.
    lib = next(r for r in manifest['native_libraries'] if r['member'] == 'lib/x86_64/libg.so')
    apk = next(r for r in manifest['apks'] if r['name'] == lib['apk'])
    rows = [r for r in installed if r['sha256'] == apk['sha256']]
    require(len(rows) == 1, 'INSTALLED_LIBG_APK_AMBIGUOUS')
    return rows[0]['path'] + '!/' + lib['member'], rows[0]['path'], apk['sha256'], 'android_linker_apk_member'


class RecordingDevice(Device):
    def __init__(self, serial, out):
        super().__init__(serial)
        # Explicit local namespace server; never inherit a remote ADB endpoint.
        self.argv[1:1] = ['-H', '127.0.0.1', '-P', '5037']
        self.out, self.seq = out, 0

    def capture(self, args, timeout=30, allow=(0,)):
        self.seq += 1
        prefix = 'cmd-' + str(self.seq).zfill(3)
        stdout, stderr = self.out / (prefix + '.stdout'), self.out / (prefix + '.stderr')
        write_json(self.out / (prefix + '.json'), {'argv': self.argv + list(args)})
        with stdout.open('xb') as so, stderr.open('xb') as se:
            try:
                p = subprocess.run(self.argv + list(args), stdout=so, stderr=se, timeout=timeout)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = 124
        text = stdout.read_text(encoding='utf-8', errors='replace').replace('\r', '')
        require(rc in allow, 'DEVICE_COMMAND_FAILED:' + prefix)
        return rc, text, prefix

    def call(self, *args, timeout=30):
        return self.capture(args, timeout)[1]


def run_once(args, out, result):
    require(args.stage_limit in LIMITS, 'STAGE_LIMIT_INVALID')
    result['stage_limit'] = args.stage_limit
    build = ignored(args.build_dir)
    require(not (build / 'ATTEMPT.json').exists(), 'PREVIOUS_ATTEMPT_NO_RETRY')
    b, manifest, _, inputs = load_inputs()
    built = read_json(ignored(build / 'build.json'))
    require(built.get('schema_version') == 7 and built.get('profile') == 'staged_no_patches' and
            built.get('client_shells_compiled') is False, 'BUILD_PROFILE')
    require(all(built['inputs'].get(k) == v for k, v in inputs.items()) and built['libg_sha256'] == b['libg_sha256'], 'BUILD_BINDING_DRIFT')
    verify_hashes(built['inputs'], ROOT)
    from binding import project, validate_recipe
    runtime_binding = read_json(build / 'runtime-binding.json')
    expected_binding = project(b)
    if runtime_binding.get('location_recipe') is not None:
        expected_binding['location_recipe'] = validate_recipe(runtime_binding['location_recipe'])
    require(runtime_binding == expected_binding, 'RUNTIME_BINDING_DRIFT')
    verify_hashes(built['artifacts'], build)
    verify_hashes(built['sources'], HERE)
    result['isolation_before'] = isolation(args.emulator_pid, args.serial)
    d = RecordingDevice(args.serial, out)
    properties = d.check()
    # Never start/stop the real client, including an already running process.
    ps = d.call('shell', 'ps', '-A', '-o', 'NAME')
    require(not any(line.strip().startswith('com.supercell.clashroyale') for line in ps.splitlines()), 'CLIENT_ALREADY_RUNNING')
    installed = installed_check(d, manifest)
    info = d.call('shell', 'dumpsys', 'package', 'com.supercell.clashroyale')
    libg, hash_path, hash_value, load_route = select_installed_libg(d, manifest, b, installed, info)
    loader = loader_paths(installed, info)
    preloads, preload_backing = preload_paths(build, args.preload_dependencies, d, manifest, installed,
                                              loader['native_library_dir'])
    result['identity'] = {'properties': properties, 'installed': installed, 'installed_libg': libg,
                          'libg_sha256': b['libg_sha256'], 'build_sha256': digest(build / 'build.json'),
                          'expected_jni_delta': built['jni_delta'], 'runtime_binding_sha256': digest(build / 'runtime-binding.json'), 'inputs': inputs, 'load_route': load_route,
                          'loader': loader, 'preload_enabled': args.preload_dependencies, 'preloads': preloads}
    remote = '/data/local/tmp/oracle-jnihost-ro-' + result['token']
    d.call('shell', 'mkdir', '-m', '700', remote)
    loader['native_search_paths'].append(remote)
    for name in ('jnihost-ro.jar', 'jnihost-loader.jar', 'libjnihost_ro.so', 'runtime-binding.json'):
        d.call('push', str(build / name), remote + '/' + name)
        require(d.call('shell', 'sha256sum', remote + '/' + name).split()[0] == built['artifacts'][name], 'GUEST_ARTIFACT_DRIFT')
    if args.preload_dependencies:
        result['identity']['preload_sha256'] = digest(build / 'preload.txt')
        write_json(out / 'preload-selection.json', {'paths': preloads, 'backing': preload_backing,
                                                   'sha256': result['identity']['preload_sha256']})
    # Check the stock guest timeout tool before consuming the one-attempt latch.
    d.call('shell', 'timeout', '-s', 'KILL', '2', '/system/bin/true')
    result['isolation_before'] = isolation(args.emulator_pid, args.serial)
    write_json(build / 'ATTEMPT.json', {'token': result['token'], 'result_directory': str(out),
                                      'stage_limit': args.stage_limit, 'rule': 'One host attempt only. A refusal must not be worked around.'})
    command = ['env', 'CLASSPATH=' + remote + '/jnihost-ro.jar',
               'timeout', '-s', 'KILL', '45', '/system/bin/app_process', '/system/bin',
               '--nice-name=oracle-jnihost-ro-' + result['token'], 'royale.nativehost.JniHost', libg, remote, result['token'],
               ':'.join(loader['apk_paths']), ':'.join(loader['native_search_paths']),
               'on' if args.preload_dependencies else 'off', args.stage_limit] + preloads
    collection_started = time.monotonic_ns()
    rc, text, prefix = d.capture(['shell', shlex.join(command)], timeout=60, allow=tuple(range(256)))
    result['collection_duration_ns'] = str(time.monotonic_ns() - collection_started)
    result['returncode'] = rc
    result['timeout'] = rc in (124, 137)
    result['host_output'] = {'stdout': prefix + '.stdout', 'stderr': prefix + '.stderr'}
    result['events'] = events_from(text, result['token'])
    result['calls'] = calls_from(text, result['token'])
    jni_observed = any(r['stage'] == 'jni_on_load' and r['event'] == 'observation' for r in result['events'])
    completed = [r['stage'] for r in result['events'] if r['event'] == 'after' and
                 (r['stage'] != 'jni_on_load' or jni_observed)]
    result['last_completed'] = completed[-1] if completed else None
    before = [r['stage'] for r in result['events'] if r['event'] == 'before']
    result['failure_stage'] = before[-1] if rc and before else None
    result['status'] = 'collected'
    result['isolation_after'] = isolation(args.emulator_pid, args.serial)
    # Preserve only this probe's logcat when a process ID was actually observed.
    if result['events']:
        _, _, diagnostic_prefix = d.capture(['logcat', '-d', '-v', 'threadtime', '--pid=' + str(result['events'][0]['pid']), '-t', '2000'],
                  allow=(0, 1))
        result['diagnostics'] = [diagnostic_prefix + '.stdout', diagnostic_prefix + '.stderr']
    require(d.call('shell', 'sha256sum', hash_path).split()[0] == hash_value, 'POST_LIBG_FILE_DRIFT')
    require(installed_check(d, manifest) == installed, 'POST_APK_DRIFT')
    require(loader_paths(installed, d.call('shell', 'dumpsys', 'package', 'com.supercell.clashroyale'))['native_library_dir']
            == loader['native_library_dir'], 'POST_NATIVE_DIRECTORY_DRIFT')
    for row in preload_backing:
        require(d.call('shell', 'sha256sum', row['path']).split()[0] == row['sha256'], 'POST_PRELOAD_DRIFT')
    # Never retry a failed host, change properties, add missing JNI declarations,
    # relax security policy or advance beyond the requested ceiling here.


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--emulator-pid', type=int, required=True)
    p.add_argument('--serial', default='emulator-5554')
    p.add_argument('--build-dir', type=Path, default=BUILD)
    p.add_argument('--preload-dependencies', action='store_true',
                   help='opt-in preload.txt before loadLibrary; never an automatic retry/fallback')
    p.add_argument('--stage-limit', choices=LIMITS, default='load-only',
                   help='inclusive ceiling; default preserves v6 load-only boundary')
    args = p.parse_args()
    require(args.emulator_pid > 1, 'EMULATOR_PID_INVALID')
    require(re.fullmatch(r'emulator-[0-9]+', args.serial), 'LOCAL_EMULATOR_REQUIRED')
    token = uuid.uuid4().hex
    out = ignored(RUNS / (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + token))
    out.mkdir(parents=True, mode=448)
    result = new_result(token)
    result['stage_limit'] = args.stage_limit
    try:
        require(not (ignored(args.build_dir) / 'ATTEMPT.json').exists(), 'PREVIOUS_ATTEMPT_NO_RETRY')
        run_once(args, out, result)
    except Exception as error:
        result['status'] = 'blocked'
        result['host_error'] = type(error).__name__ + ': ' + str(error)
    result['receipts'] = {p.name: digest(p) for p in out.iterdir() if p.is_file()}
    write_json(out / 'result.json', result)
    from review import assess
    reviewed = assess(result, out)
    write_json(out / 'review.json', reviewed)
    print('ORACLE_V7_' + reviewed['classification'].upper() + ': private result and review retained; zero patches')
    print('PRIVATE_RUN=' + str(out))
    return 0 if reviewed['classification'] == 'a' else 78


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception:
        print('BLOCKED: cannot safely create private receipt', file=sys.stderr)
        raise SystemExit(78)
