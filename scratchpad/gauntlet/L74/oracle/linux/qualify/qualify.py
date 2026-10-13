"""Worker-side, offset-free, external read-only qualification collector (Python 3.10+).

No sockets, debugger, target calls, injection, or protection-policy changes.
Run inside the isolated emulator namespace, never against a host ADB server.
All receipts (including failures) are private. stdout contains no target values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
PRIVATE = ROOT / 'scratchpad/gauntlet/L70/reader/oracle_160402012'
sys.path.insert(0, str(HERE.parents[1]))
from binding_status import REQUIRED, SITE_NAMES


class Blocked(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise Blocked(reason)


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ignored(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT), 'PRIVATE_PATH_OUTSIDE_CHECKOUT')
    relative = path.relative_to(ROOT).as_posix()
    require(subprocess.run(['git', 'check-ignore', '-q', '--', relative], cwd=ROOT).returncode == 0,
            'PRIVATE_PATH_NOT_IGNORED')
    tracked = subprocess.run(['git', 'ls-files', '--', relative], cwd=ROOT,
                             capture_output=True, check=True)
    require(not tracked.stdout, 'PRIVATE_PATH_TRACKED')
    return path


def write_json(path, value):
    path = ignored(path)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def isolated():
    require(sys.platform == 'linux', 'LINUX_WORKER_REQUIRED')
    links = json.loads(subprocess.check_output(['ip', '-j', 'link', 'show']))
    require(len(links) == 1 and links[0]['ifname'] == 'lo', 'NETWORK_NOT_ISOLATED')
    for family in ('-4', '-6'):
        routes = json.loads(subprocess.check_output(['ip', family, '-j', 'route', 'show', 'table', 'all']))
        require(all(r.get('dev') == 'lo' for r in routes), 'NETWORK_ROUTE_PRESENT')
    require(not os.environ.get('ADB_SERVER_SOCKET') and not os.environ.get('ANDROID_ADB_SERVER_PORT'),
            'CUSTOM_ADB_SERVER_FORBIDDEN')
    require(not os.environ.get('ANDROID_SERIAL'), 'IMPLICIT_SERIAL_FORBIDDEN')


def run(argv, timeout=60):
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    require(p.returncode == 0, 'COMMAND_FAILED')
    return p.stdout.decode('utf-8', errors='replace').replace('\r', '')


class Device:
    def __init__(self, serial):
        require(bool(re.fullmatch(r'emulator-[0-9]+', serial)), 'LOCAL_EMULATOR_REQUIRED')
        sdk = Path(os.environ.get('ANDROID_SDK_ROOT', Path.home() / 'Android/Sdk'))
        self.sdk = sdk
        self.argv = [str(sdk / 'platform-tools/adb'), '-s', serial]

    def call(self, *args, timeout=60):
        return run(self.argv + list(args), timeout)

    def pids(self):
        p = subprocess.run(self.argv + ['shell', 'pidof', 'com.supercell.clashroyale'],
                           capture_output=True, timeout=15)
        require(p.returncode in (0, 1), 'PID_QUERY_FAILED')
        values = p.stdout.decode().split()
        require(all(v.isdigit() for v in values), 'PID_QUERY_INVALID')
        return values

    def check(self):
        isolated()
        require(self.call('shell', 'id', '-u').strip() == '0', 'ROOT_ADBD_REQUIRED_NO_POLICY_CHANGE')
        require(self.call('shell', 'getprop', 'ro.build.version.sdk').strip() == '32', 'API_MISMATCH')  # 160402012 splits declare minSdk 32 (10-13)
        require(self.call('shell', 'getprop', 'ro.product.cpu.abi').strip() == 'x86_64', 'ABI_MISMATCH')
        require(self.call('shell', 'getprop', 'ro.build.type').strip() in ('eng', 'userdebug'),
                'AOSP_DEBUG_IMAGE_REQUIRED')
        return {k: self.call('shell', 'getprop', k).strip() for k in
                ('ro.build.fingerprint', 'ro.build.version.sdk', 'ro.product.cpu.abi', 'ro.build.type')}


def binding_load(path):
    path = ignored(path)
    b = json.loads(path.read_text())
    require(b['runtime_version'] == '160402012' and b['abi'] == 'x86_64', 'BINDING_IDENTITY')
    require(all(k in b['entries'] for k in REQUIRED), 'BINDING_ENTRIES')
    require({s['id'] for s in b['patch_sites']} == set(SITE_NAMES), 'BINDING_SITES')
    x_path = ignored(path.parent / 'v4-readonly.json')
    x = json.loads(x_path.read_text())
    require(x['binding_sha256'] == digest(path), 'SUPPLEMENT_BINDING_DRIFT')
    for rel, sha in x['evidence_sha256'].items():
        require(digest(path.parent / rel) == sha, 'SUPPLEMENT_EVIDENCE_DRIFT')
    return b, x


def apk_check(device, directory, manifest, binding):
    directory = ignored(directory)
    require({p.name for p in directory.glob('*.apk')} == {a['name'] for a in manifest['apks']},
            'APK_SET_MISMATCH')
    receipts, signer = [], None
    for row in manifest['apks']:
        require(Path(row['name']).name == row['name'], 'APK_NAME_INVALID')
        path = directory / row['name']
        require(path.stat().st_size == row['size'] and digest(path) == row['sha256'], 'APK_HASH_MISMATCH')
        badging = run([str(device.sdk / 'build-tools/35.0.0/aapt'), 'dump', 'badging', str(path)])
        m = re.search(r"package: name='([^']+)' versionCode='([^']+)'", badging)
        require(m and m[1] == 'com.supercell.clashroyale' and m[2] == binding['runtime_version'],
                'APK_PACKAGE_VERSION_MISMATCH')
        cert = run([str(device.sdk / 'build-tools/35.0.0/apksigner'), 'verify', '--verbose',
                    '--print-certs', str(path)])
        signers = re.findall(r'Signer #[0-9]+ certificate SHA-256 digest: ([0-9a-fA-F]+)', cert)
        require(len(signers) == 1, 'APK_SIGNER_UNAVAILABLE')
        if signer is None:
            signer = signers
        require(signer == signers, 'APK_SIGNER_MISMATCH')
        receipts.append({'name': row['name'], 'sha256': row['sha256'], 'badging': badging, 'cert': cert})
    row = next(r for r in manifest['native_libraries'] if r['member'] == 'lib/x86_64/libg.so')
    apk = directory / row['apk']
    with zipfile.ZipFile(apk) as z:
        info = z.getinfo(row['member'])
        blob = z.read(info)
    require(hashlib.sha256(blob).hexdigest() == binding['libg_sha256'] == row['sha256'], 'ORIGINAL_LIBG_HASH')
    with apk.open('rb') as f:
        f.seek(info.header_offset)
        header = f.read(30)
    name_size, extra_size = struct.unpack_from('<HH', header, 26)
    member_offset = info.header_offset + 30 + name_size + extra_size
    return receipts, blob, row['apk'], member_offset if info.compress_type == zipfile.ZIP_STORED else None


def installed_check(device, manifest):
    paths = device.call('shell', 'pm', 'path', 'com.supercell.clashroyale').splitlines()
    require(len(paths) == len(manifest['apks']), 'INSTALLED_SPLIT_COUNT')
    actual = []
    for line in paths:
        path = line.removeprefix('package:')
        require(re.fullmatch(r'/data/app/[A-Za-z0-9_./+=~-]+\.apk', path), 'INSTALLED_PATH_INVALID')
        sha = device.call('shell', 'sha256sum', path).split()[0]
        actual.append({'path': path, 'sha256': sha})
    require(sorted(a['sha256'] for a in actual) == sorted(a['sha256'] for a in manifest['apks']),
            'INSTALLED_HASH_MISMATCH')
    info = device.call('shell', 'dumpsys', 'package', 'com.supercell.clashroyale')
    require(re.search(r'\bversionCode=' + re.escape(manifest['requested_build']) + r'\b', info),
            'INSTALLED_VERSION_MISMATCH')
    return actual


def probe_check(device=None):
    build = ignored(HERE.parents[1] / '.local/qualify-build')
    probe = build / 'observer'
    source = build / 'android_probe/native/oracle_readonly.c'
    require(probe.is_file() and source.is_file(), 'PROBE_NOT_BUILT')
    require(digest(source) == digest(HERE / 'observer.c'), 'PROBE_SOURCE_DRIFT_REBUILD_REQUIRED')
    sums = (build / 'SHA256SUMS').read_text().splitlines()
    require(len(sums) == 2 and sums[0].split()[0] == digest(probe)
            and sums[1].split()[0] == digest(source), 'PROBE_BUILD_RECEIPT_MISMATCH')
    if device:
        require(device.call('shell', 'sha256sum', '/data/local/tmp/oracle-readonly').split()[0] == digest(probe),
                'INSTALLED_PROBE_HASH')
    return probe


def parse_maps(text):
    rows = []
    for line in text.splitlines():
        parts = line.split(maxsplit=5)
        lo, hi = parts[0].split('-')
        rows.append({'lo': int(lo, 16), 'hi': int(hi, 16), 'perms': parts[1],
                     'offset': int(parts[2], 16), 'dev': parts[3], 'inode': parts[4],
                     'path': parts[5] if len(parts) > 5 else ''})
    return rows


def elf_headers(blob):
    require(blob[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', blob, 18)[0] == 62,
            'ELF_NOT_X86_64_LE')
    off = struct.unpack_from('<Q', blob, 32)[0]
    size, count = struct.unpack_from('<HH', blob, 54)
    require(size == 56 and 0 < count <= 128, 'ELF_PROGRAM_HEADERS')
    return [struct.unpack_from('<IIQQQQQQ', blob, off + i * size) for i in range(count)]


def module_base(maps, headers, apk_name, zip_offset):
    # Match every file-backed PT_LOAD by file offset and virtual address.
    # A map's start alone is NOT the ELF load bias; APK offsets are not RVAs.
    loads = [h for h in headers if h[0] == 1 and h[5]]
    candidates = set()
    for m in maps:
        origin = 0 if m['path'].endswith('/libg.so') else zip_offset if m['path'].endswith('/' + apk_name) else None
        if origin is None:
            continue
        for h in loads:
            file_start, va_start = h[2] // 4096 * 4096, h[3] // 4096 * 4096
            relative = m['offset'] - origin
            if file_start <= relative < h[2] + h[5]:
                candidates.add(m['lo'] - va_start - (relative - file_start))
    valid = []
    for base in candidates:
        identities = set()
        for h in loads:
            addr = base + h[3]
            matches = []
            for m in maps:
                origin = 0 if m['path'].endswith('/libg.so') else zip_offset if m['path'].endswith('/' + apk_name) else None
                if origin is not None and m['lo'] <= addr < m['hi'] and m['offset'] + addr - m['lo'] == origin + h[2]:
                    matches.append(m)
            if len(matches) != 1:
                break
            identities.add((matches[0]['dev'], matches[0]['inode'], matches[0]['path']))
        else:
            if len(identities) == 1:
                valid.append(base)
    require(valid, 'MODULE_BASE_MISSING')
    require(len(valid) == 1, 'MODULE_BASE_AMBIGUOUS')
    return valid[0]


class Reader:
    def __init__(self, device, pid, stderr):
        self.p = subprocess.Popen(device.argv + ['exec-out', '/data/local/tmp/oracle-readonly', str(pid)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, bufsize=0)
        self.maps = []

    def exact(self, n):
        result = b''
        deadline = time.monotonic() + 10
        while len(result) < n:
            ready, _, _ = select.select([self.p.stdout], [], [], max(0, deadline - time.monotonic()))
            require(ready, 'OBSERVER_TIMEOUT')
            chunk = os.read(self.p.stdout.fileno(), n - len(result))
            require(chunk, 'OBSERVER_EOF')
            result += chunk
        return result

    def command(self, command):
        self.p.stdin.write((command + '\n').encode())
        line = b''
        while not line.endswith(b'\n') and len(line) < 24:
            line += self.exact(1)
        require(bool(re.fullmatch(rb'-?\d+\n', line)), 'OBSERVER_PROTOCOL')
        n = int(line)
        require(n >= 0, 'READ_DENIED_OR_FAILED_NO_FALLBACK')
        require(n <= 1048576, 'OBSERVER_REPLY_TOO_LARGE')
        return self.exact(n)

    def refresh(self):
        raw = self.command('maps').decode()
        self.maps = parse_maps(raw)
        return raw

    def read(self, address, length):
        require(0 < length <= 65536, 'READ_LENGTH')
        require(any(m['lo'] <= address and address + length <= m['hi'] and 'r' in m['perms']
                    for m in self.maps), 'UNMAPPED_OR_CROSS_MAPPING_READ')
        data = self.command(f'read {address} {length}')
        require(len(data) == length, 'SHORT_READ')
        return data

    def scalar(self, address, kind):
        fmt = {'ptr': 'Q', 'u8': 'B', 'i32': 'i', 'u32': 'I', 'f32': 'f'}[kind]
        value = struct.unpack('<' + fmt, self.read(address, struct.calcsize(fmt)))[0]
        require(not isinstance(value, float) or math.isfinite(value), 'NONFINITE_VALUE')
        return value

    def close(self):
        self.p.stdin.close()
        try:
            self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.terminate()  # Only our host ADB client, never the target PID.
            self.p.wait(timeout=5)


def start_time(stat):
    return stat.rsplit(')', 1)[1].split()[19]


def live_jni(reader, base, headers):
    dyn = [h for h in headers if h[0] == 2]
    require(len(dyn) == 1 and dyn[0][6] <= 65536, 'DYNAMIC_TABLE_UNSUPPORTED')
    tags = {}
    for offset in range(0, dyn[0][6], 16):
        tag, value = struct.unpack('<qQ', reader.read(base + dyn[0][3] + offset, 16))
        if tag == 0:
            break
        tags[tag] = value
    def pointer(value):
        return value if any(m['lo'] <= value < m['hi'] for m in reader.maps) else base + value
    require(all(t in tags for t in (5, 6, 10, 11, 1879047925)), 'LIVE_GNU_SYMBOL_TABLE_MISSING')
    require(tags[11] == 24 and tags[10] < 64 * 1024 * 1024, 'LIVE_SYMBOL_LAYOUT')
    strings, symbols, table = pointer(tags[5]), pointer(tags[6]), pointer(tags[1879047925])
    buckets, first, bloom_size, _ = struct.unpack('<IIII', reader.read(table, 16))
    require(0 < buckets < 1000000 and 0 < bloom_size < 1000000, 'GNU_HASH_BOUNDS')
    name, hash_value = b'JNI_OnLoad', 5381
    for c in name:
        hash_value = (hash_value * 33 + c) & ((1 << 32) - 1)
    bucket_start = table + 16 + bloom_size * 8
    index = reader.scalar(bucket_start + (hash_value % buckets) * 4, 'u32')
    require(index >= first, 'JNI_SYMBOL_ABSENT')
    chain_start = bucket_start + buckets * 4
    for _ in range(4096):
        chain = reader.scalar(chain_start + (index - first) * 4, 'u32')
        if (chain | 1) == (hash_value | 1):
            st_name, info, other, section, value, size = struct.unpack('<IBBHQQ', reader.read(symbols + index * 24, 24))
            require(st_name + len(name) + 1 <= tags[10], 'SYMBOL_STRING_BOUNDS')
            if reader.read(strings + st_name, len(name) + 1) == name + b'\0':
                require(section != 0 and info & 15 == 2, 'JNI_NOT_DEFINED_FUNCTION')
                return value - base if value >= base else value
        if chain & 1:
            break
        index += 1
    raise Blocked('JNI_SYMBOL_ABSENT_OR_BOUND_EXCEEDED')


def snapshot(reader, base, b, x):
    """Non-atomic snapshots: recheck roots and identity, retain races as gaps."""
    e, f = b['entries'], b['fields']
    s = {'monotonic_ns': time.monotonic_ns(), 'values': {}, 'gaps': []}
    values = s['values']
    def scalar(key, addr, kind):
        value = reader.scalar(addr, kind)
        values[key] = {'address': addr, 'value': value}
        return value
    def field(key, root, kind):
        return scalar(key, root + number(f[key]['offset']), kind)
    def ptr(key, rva):
        return scalar(key, base + number(rva), 'ptr')
    manager = ptr('manager', e['manager_global']['rva'])
    locator = e['skip_core_and_presentation_flag']['locator']
    control = ptr('scheduling_control', locator['global_pointer_rva'])
    state, battle = 0, 0
    if manager:
        parent = scalar('manager.parent', manager + x['manager_parent_offset'], 'ptr')
        state = field('manager.current_state', manager, 'ptr')
        current = field('manager.current_state_type', manager, 'i32')
        field('manager.pending_state_type', manager, 'i32')
        field('manager.replay_data', manager, 'ptr')
        if control:
            addr = control + number(locator['member_offset'])
            require(any(m['lo'] <= control and addr + locator['width'] <= m['hi']
                        and 'r' in m['perms'] and 'w' in m['perms'] and 'x' not in m['perms']
                        for m in reader.maps), 'SCHEDULING_NOT_RW_NONEXEC_DATA')
            owner = scalar('scheduling_owner', control + x['control_owner_offset'], 'ptr')
            values['scheduling_owner_matches_parent'] = bool(owner) and owner == parent
            scalar('scheduling_flag', addr, 'u8')
        if state:
            vptr = scalar('state.vptr', state, 'ptr')
            state_type = scalar('state.type', state + x['state_type_offset'], 'i32')
            if vptr == base + number(f['loading_state_vtable']['rva']):
                values['loading_update_slot_matches'] = reader.scalar(vptr + number(f['loading_update_vtable_slot']['offset']), 'ptr') == base + number(e['loading_state_update']['rva'])
                values['loading_complete_slot_matches'] = reader.scalar(vptr + number(f['loading_complete_vtable_slot']['offset']), 'ptr') == base + number(e['loading_state_complete']['rva'])
                field('loading_phase', state, 'i32')
                field('loading_ready_latch', state, 'u8')
                field('loading_future_primary', state, 'ptr')
                field('loading_future_secondary', state, 'ptr')
                task = field('loading_task', state, 'ptr')
                if task:
                    tables = field('data_task.tables', task, 'ptr')
                    resources = field('data_task.resources', task, 'ptr')
                    field('data_task.phase', task, 'i32')
                    field('data_task.range_cursor', task, 'i32')
                    if tables:
                        field('data_tables.ready', tables, 'u8')
                    if resources:
                        field('resource_collection.count', resources, 'i32')
                gate = ptr('resource_gate', f['resource_gate_global']['rva'])
                if gate:
                    scalar('resource_gate.phase', gate + x['resource_gate_phase_offset'], 'i32')
            factory = e['state_factory']
            if current == state_type == factory['battle_type'] and vptr == base + number(factory['vtable_rva']):
                values['battle_update_slot_matches'] = reader.scalar(vptr + factory['update_slot'] * 8, 'ptr') == base + number(e['battle_state_update']['rva'])
                battle = field('battle_state.battle', state, 'ptr')
                field('battle_state.core_accumulator', state, 'f32')
                if battle:
                    field('battle.tick', battle, 'u32')
                    field('battle.logic', battle, 'ptr')
    game = ptr('game_main_candidate', x['game_main_global_rva'])
    if game:
        vptr = scalar('game_main.vptr', game, 'ptr')
        values['game_main_vtable_matches'] = vptr == base + x['game_main_vtable_rva']
        if values['game_main_vtable_matches']:
            context = scalar('game_main.context', game + x['game_main_context_offset'], 'ptr')
            values['game_main_context_mapped'] = any(m['lo'] <= context < m['hi'] and 'r' in m['perms'] for m in reader.maps)
            values['game_main_init_slot_matches'] = reader.scalar(vptr + x['game_main_init_slot'] * 8, 'ptr') == base + number(e['game_main_init']['rva'])
    require(reader.scalar(base + number(e['manager_global']['rva']), 'ptr') == manager
            and reader.scalar(base + number(locator['global_pointer_rva']), 'ptr') == control,
            'ROOT_CHANGED_DURING_SAMPLE')
    if manager:
        require(reader.scalar(manager + number(f['manager.current_state']['offset']), 'ptr') == state,
                'STATE_CHANGED_DURING_SAMPLE')
    if battle:
        require(reader.scalar(state + number(f['battle_state.battle']['offset']), 'ptr') == battle,
                'BATTLE_CHANGED_DURING_SAMPLE')
    s['end_monotonic_ns'] = time.monotonic_ns()
    s['atomic'] = False
    return s


def new_result(binding_sha):
    return {'schema_version': 1, 'status': 'NOT_RUN', 'binding_sha256': binding_sha,
            'target_writes': 0, 'software_breakpoints': 0, 'patches_qualified': 0,
            'method': 'external_proc_read_polling', 'execution_confirmed': False,
            'probes': [{'id': k, 'status': 'NOT_OBSERVED', 'evidence': [],
                        'limitation': 'Polling cannot establish function entry or full transitive effects.'} for k in REQUIRED],
            'sites': [{'id': k, 'status': 'NOT_RUN', 'patch_qualified': False, 'evidence': []} for k in SITE_NAMES],
            'limitations': ['No function calls, debugger attachment or data writes are performed.',
                            'Finite, non-atomic sampling cannot prove rendering-only or object lifetime safety.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('preflight', 'install', 'install-probe', 'collect'))
    p.add_argument('--binding', type=Path, default=PRIVATE / 'runtime-160402012-x86_64.json')
    p.add_argument('--apks', type=Path, default=ROOT / 'share/clashroyale_160402012_kit/apk')
    p.add_argument('--out', required=True, type=Path, help='New git-ignored run directory')
    p.add_argument('--serial', default='emulator-5554')
    p.add_argument('--pid', type=int)
    p.add_argument('--wait-seconds', type=float, default=0,
                   help='After identity checks wait for the original main app; worker launches it separately')
    p.add_argument('--seconds', type=float, default=30)
    p.add_argument('--interval', type=float, default=0.1)
    a = p.parse_args()
    os.umask(63)
    out = ignored(a.out)
    require(not out.exists(), 'OUTPUT_ALREADY_EXISTS')
    out.mkdir(parents=True, mode=448)
    result = new_result(digest(ignored(a.binding)))
    reader = None
    d = None
    try:
        b, x = binding_load(a.binding)
        d = Device(a.serial)
        result['environment'] = d.check()
        manifest = json.loads(ignored(a.binding.parent / 'artifact_manifest.json').read_text())
        receipts, blob, apk_name, zip_offset = apk_check(d, a.apks, manifest, b)
        write_json(out / 'apk-identity.json', receipts)
        if a.action == 'install-probe':
            probe = probe_check()
            # Never replace a helper in use. Each deployment starts with an absent path.
            exists = d.call('shell', 'ls', '/data/local/tmp').splitlines()
            require('oracle-readonly' not in exists, 'PROBE_PATH_EXISTS_RETAINED')
            d.call('push', str(probe), '/data/local/tmp/oracle-readonly')
            d.call('shell', 'chmod', '700', '/data/local/tmp/oracle-readonly')
            require(d.call('shell', 'sha256sum', '/data/local/tmp/oracle-readonly').split()[0] == digest(probe),
                    'INSTALLED_PROBE_HASH')
            result['probe_sha256'] = digest(probe)
            result['status'] = 'PREPARED'
        elif a.action == 'install':
            require('package:com.supercell.clashroyale' not in
                    d.call('shell', 'pm', 'list', 'packages', 'com.supercell.clashroyale').splitlines(),
                    'EXISTING_APP_NO_REPLACE_OR_CLEAR')
            d.call('install-multiple', *(str(a.apks / r['name']) for r in manifest['apks']), timeout=900)
            result['installed'] = installed_check(d, manifest)
            result['status'] = 'PREPARED'
        elif a.action == 'preflight':
            result['status'] = 'PREPARED'
        else:
            require((a.pid is not None) != (a.wait_seconds > 0), 'PID_OR_WAIT_REQUIRED')
            require(0 <= a.wait_seconds <= 300 and (a.pid is None or a.pid > 1), 'PID_OR_WAIT_INVALID')
            require(0 < a.seconds <= 300 and 0.02 <= a.interval <= 5, 'POLL_BUDGET_INVALID')
            result['installed'] = installed_check(d, manifest)
            result['probe_sha256'] = digest(probe_check(d))
            if a.wait_seconds:
                print('READY_WAITING_FOR_ORIGINAL_APP: worker may launch normally in the isolated namespace', flush=True)
                wait_deadline = time.monotonic() + a.wait_seconds
                while True:
                    pids = d.pids()
                    if pids:
                        require(len(pids) == 1, 'PID_NOT_UNIQUE_MAIN_APP')
                        a.pid = int(pids[0])
                        break
                    require(time.monotonic() < wait_deadline, 'APP_WAIT_EXPIRED')
                    isolated()
                    time.sleep(0.1)
            require(d.pids() == [str(a.pid)], 'PID_NOT_UNIQUE_MAIN_APP')
            with (out / 'observer-stderr.txt').open('xb') as err:
                reader = Reader(d, a.pid, err)
                require(reader.command('cmdline').split(b'\0')[0] == b'com.supercell.clashroyale', 'PID_COMMAND_MISMATCH')
                initial_stat = reader.command('stat').decode()
                generation = start_time(initial_stat)
                headers = elf_headers(blob)
                module_deadline = time.monotonic() + 15
                while True:
                    require(start_time(reader.command('stat').decode()) == generation, 'PID_GENERATION_CHANGED')
                    maps = reader.refresh()
                    try:
                        base = module_base(reader.maps, headers, apk_name, zip_offset)
                        break
                    except Blocked as exc:
                        if str(exc) != 'MODULE_BASE_MISSING' or time.monotonic() >= module_deadline:
                            raise
                        time.sleep(0.1)
                (out / 'maps.txt').write_text(maps)
                module_maps = [m for m in reader.maps if m['lo'] <= base < m['hi']]
                require(len(module_maps) == 1, 'MODULE_HEADER_MAPPING')
                mapped_path = module_maps[0]['path']
                if mapped_path.endswith('.apk'):
                    require(mapped_path in [r['path'] for r in result['installed']], 'MAPPED_APK_NOT_INSTALLED')
                else:
                    require(re.fullmatch(r'/data/app/[A-Za-z0-9_./+=~-]+/libg\.so', mapped_path),
                            'MODULE_OVERLAY_OR_UNTRUSTED_PATH')
                    require(d.call('shell', 'sha256sum', mapped_path).split()[0] == b['libg_sha256'],
                            'LOADED_MODULE_FILE_HASH')
                require(reader.read(base, 64) == blob[:64], 'LOADED_ELF_HEADER_MISMATCH')
                result['identity'] = {'pid': a.pid, 'start_time': generation, 'module_base': base,
                                      'original_libg_sha256': b['libg_sha256']}
                # Read named loaded dynamic symbol without dlsym or calling JNI.
                delta = live_jni(reader, base, headers)
                require(delta == number(b['version_guard']['expected_jni_on_load_rva'])
                        == number(b['entries']['jni_on_load']['rva']), 'JNI_DELTA_MISMATCH')
                result['identity']['jni_on_load_delta'] = delta
                result['probes'][0].update(status='OBSERVED', evidence=['result.json#identity'],
                                           limitation='Named live symbol delta, not invocation or app_process compatibility.')
                count = 0
                deadline = time.monotonic() + a.seconds
                with (out / 'samples.jsonl').open('x', encoding='utf-8') as samples:
                    while time.monotonic() < deadline:
                        isolated()
                        require(start_time(reader.command('stat').decode()) == generation, 'PID_GENERATION_CHANGED')
                        reader.refresh()
                        require(module_base(reader.maps, headers, apk_name, zip_offset) == base, 'MODULE_CHANGED')
                        s = snapshot(reader, base, b, x)
                        require(start_time(reader.command('stat').decode()) == generation, 'PID_GENERATION_CHANGED')
                        samples.write(json.dumps(s, allow_nan=False) + '\n')
                        samples.flush()
                        count += 1
                        time.sleep(a.interval)
                result['sample_count'] = count
                result['status'] = 'OBSERVED_PARTIAL'
                for item in result['probes'][1:]:
                    item['evidence'] = ['samples.jsonl', 'logcat.txt']
                    item['status'] = 'NEEDS_REVIEW'
    except (Blocked, OSError, ValueError, KeyError, struct.error, subprocess.SubprocessError) as exc:
        result['status'] = 'BLOCKED'
        # Private only: tool errors can contain path or address information.
        result['blocker'] = type(exc).__name__ + ': ' + str(exc)
    except KeyboardInterrupt:
        result['status'] = 'BLOCKED'
        result['blocker'] = 'OPERATOR_INTERRUPTED'
    finally:
        if reader:
            try:
                reader.close()
            except (OSError, subprocess.SubprocessError) as exc:
                result['status'] = 'BLOCKED'
                result['cleanup_error'] = str(exc)
        if reader and d and a.pid:
            # Ordinary logs remain useful when memory observation failed.
            # No buffer clearing, property changes, or increased logging.
            try:
                log = d.call('logcat', '-d', '-v', 'threadtime', '--pid=' + str(a.pid), '-t', '2000')
                (out / 'logcat.txt').write_text(log)
                result['logcat_scope'] = 'Last bounded records for PID; may predate this session; PID reuse not excluded.'
            except (Blocked, OSError, subprocess.SubprocessError):
                result['limitations'].append('Bounded logcat unavailable; no logging configuration changed.')
        write_json(out / 'result.json', result)
    print(result['status'] + ': private receipt written; zero patches qualified')
    return 78 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Blocked, OSError, ValueError) as error:
        print('BLOCKED: private input/output validation failed', file=sys.stderr)
        sys.exit(78)
