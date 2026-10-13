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
from common import (HERE, ROOT, BUILD, RUNS, STAGES, BOUNDARY, Device, require,
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
        if line.startswith('ORACLE_V5 '):
            row = json.loads(line[len('ORACLE_V5 '):])
            require(row.get('token') == token and type(row.get('pid')) is int and row['pid'] > 0,
                    'EVENT_IDENTITY')
            require(row.get('schema_version') == 1, 'EVENT_SCHEMA')
            require(row.get('stage') in STAGES + (BOUNDARY,), 'EVENT_STAGE')
            require(row.get('event') in ('before', 'after', 'observation', 'boundary', 'error'), 'EVENT_KIND')
            events.append(row)
    require(len({e['pid'] for e in events}) <= 1, 'MULTIPLE_HOST_PIDS')
    return events


def new_result(token):
    return {'schema_version': 1, 'token': token, 'runtime_version': '160402012',
            'policy': {'client_launched': False, 'bridge_writes': 0, 'code_patches': 0,
                       'environment_spoofing': False, 'unpacking': False, 'patches_qualified': 0},
            'status': 'blocked', 'events': [], 'last_completed': None, 'failure_stage': None,
            'returncode': None, 'timeout': False, 'host_error': None,
            'isolation_before': None, 'isolation_after': None, 'identity': None, 'receipts': {},
            'limitation': 'Native init may write its own state/files; read-only describes our observer, not purity of libg calls.'}


def select_installed_libg(device, manifest, binding, installed, info):
    matches = re.findall(r'^\s*legacyNativeLibraryDir=(\S+)', info, re.M)
    require(len(set(matches)) == 1, 'INSTALLED_NATIVE_DIRECTORY_UNAVAILABLE')
    libdir = matches[0]
    require(re.fullmatch(r'/data/app/[A-Za-z0-9_./+=~-]+/lib', libdir), 'NATIVE_DIRECTORY_INVALID')
    libg = libdir + '/x86_64/libg.so'
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
    build = ignored(args.build_dir)
    b, manifest, _, inputs = load_inputs()
    built = read_json(ignored(build / 'build.json'))
    require(built['inputs'] == inputs and built['libg_sha256'] == b['libg_sha256'], 'BUILD_BINDING_DRIFT')
    verify_hashes(built['artifacts'], build)
    verify_hashes(built['sources'], HERE)
    verify_hashes(built['upstream'], ROOT)
    result['isolation_before'] = isolation(args.emulator_pid, args.serial)
    d = RecordingDevice(args.serial, out)
    properties = d.check()
    # Never start/stop the real client, including an already running process.
    ps = d.call('shell', 'ps', '-A', '-o', 'NAME')
    require(not any(line.strip().startswith('com.supercell.clashroyale') for line in ps.splitlines()), 'CLIENT_ALREADY_RUNNING')
    installed = installed_check(d, manifest)
    info = d.call('shell', 'dumpsys', 'package', 'com.supercell.clashroyale')
    libg, hash_path, hash_value, load_route = select_installed_libg(d, manifest, b, installed, info)
    result['identity'] = {'properties': properties, 'installed': installed, 'installed_libg': libg,
                          'libg_sha256': b['libg_sha256'], 'build_sha256': digest(build / 'build.json'),
                          'expected_jni_delta': built['jni_delta'], 'inputs': inputs, 'load_route': load_route}
    remote = '/data/local/tmp/oracle-jnihost-ro-' + result['token']
    d.call('shell', 'mkdir', '-m', '700', remote)
    for name in ('jnihost-ro.jar', 'libjnihost_ro.so'):
        d.call('push', str(build / name), remote + '/' + name)
        require(d.call('shell', 'sha256sum', remote + '/' + name).split()[0] == built['artifacts'][name], 'GUEST_ARTIFACT_DRIFT')
    # Check the stock guest timeout tool before consuming the one-attempt latch.
    d.call('shell', 'timeout', '-s', 'KILL', '2', '/system/bin/true')
    result['isolation_before'] = isolation(args.emulator_pid, args.serial)
    write_json(build / 'ATTEMPT.json', {'token': result['token'], 'result_directory': str(out),
                                      'rule': 'One host attempt only. A refusal must not be worked around.'})
    command = ['env', 'CLASSPATH=' + remote + '/jnihost-ro.jar',
               'timeout', '-s', 'KILL', '45', '/system/bin/app_process', '/system/bin',
               '--nice-name=oracle-jnihost-ro-' + result['token'], 'royale.nativehost.JniHost', libg, remote, result['token']]
    rc, text, prefix = d.capture(['shell', shlex.join(command)], timeout=60, allow=tuple(range(256)))
    result['returncode'] = rc
    result['timeout'] = rc in (124, 137)
    result['events'] = events_from(text, result['token'])
    result['host_output'] = {'stdout': prefix + '.stdout', 'stderr': prefix + '.stderr'}
    completed = [r['stage'] for r in result['events'] if r['event'] == 'after']
    result['last_completed'] = completed[-1] if completed else None
    before = [r['stage'] for r in result['events'] if r['event'] == 'before']
    result['failure_stage'] = before[-1] if rc and before else None
    result['status'] = 'collected'
    result['isolation_after'] = isolation(args.emulator_pid, args.serial)
    # Preserve only this probe's logcat when a process ID was actually observed.
    if result['events']:
        d.capture(['logcat', '-d', '-v', 'threadtime', '--pid=' + str(result['events'][0]['pid']), '-t', '2000'],
                  allow=(0, 1))
    require(d.call('shell', 'sha256sum', hash_path).split()[0] == hash_value, 'POST_LIBG_FILE_DRIFT')
    # Never retry a failed host, change properties, add missing JNI declarations,
    # relax security policy or run any later init/manager/replay function here.


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--emulator-pid', type=int, required=True)
    p.add_argument('--serial', default='emulator-5554')
    p.add_argument('--build-dir', type=Path, default=BUILD)
    args = p.parse_args()
    require(args.emulator_pid > 1, 'EMULATOR_PID_INVALID')
    require(re.fullmatch(r'emulator-[0-9]+', args.serial), 'LOCAL_EMULATOR_REQUIRED')
    token = uuid.uuid4().hex
    out = ignored(RUNS / (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + token))
    out.mkdir(parents=True, mode=448)
    result = new_result(token)
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
    print('JNIHOST_RO_' + reviewed['classification'].upper() + ': private result and review retained; zero patches')
    return 0 if reviewed['classification'] == 'a' else 78


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception:
        print('BLOCKED: cannot safely create private receipt', file=sys.stderr)
        raise SystemExit(78)
