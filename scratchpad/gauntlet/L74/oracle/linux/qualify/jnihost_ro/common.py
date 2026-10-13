"""Shared offset-free validation. Importing this module never contacts a device."""
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent))
from qualify import (ROOT, PRIVATE, Blocked, require, digest, ignored, isolated,
                     Device, installed_check, binding_load)

BUILD = HERE.parents[2] / '.local/jnihost-ro-build-v6'
RUNS = PRIVATE / 'runtime_qualification/jnihost_ro'
STAGES = ('class_loader', 'observer_load', 'dependency_preload', 'jni_on_load')
BOUNDARY = 'stop_after_library_load'
SITES = {
    'game_main_init': ['renderer_bootstrap_call', 'renderer_device_block',
                      'renderer_resolution_call', 'renderer_objects_block',
                      'renderer_late_configure_call'],
    'resource_variant': ['headless_resource_variant'],
    'loading_completion': ['loading_presentation_call', 'loading_platform_ui_call'],
    'manager_home': ['game_presentation_toggle', 'home_resolution_block', 'home_graphics_create_call'],
}


def write_json(path, value):
    path = ignored(path)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_inputs():
    bpath = PRIVATE / 'runtime-160402012-x86_64.json'
    b, extra = binding_load(bpath)
    manifest_path = ignored(PRIVATE / 'artifact_manifest.json')
    manifest = read_json(manifest_path)
    require(str(manifest['requested_build']) == b['runtime_version'], 'MANIFEST_VERSION')
    lib = next(r for r in manifest['native_libraries'] if r['member'] == 'lib/x86_64/libg.so')
    require(lib['sha256'] == b['libg_sha256'], 'MANIFEST_LIBG')
    values = [b['entries']['jni_on_load']['rva'], extra['game_main_global_rva'], extra['game_main_vtable_rva']]
    values = [int(v, 0) if isinstance(v, str) else v for v in values]
    require(all(type(v) is int and 0 < v < 2**32 for v in values), 'BINDING_RANGE')
    return b, manifest, values, {str(p.relative_to(ROOT)): digest(p) for p in
        (bpath, PRIVATE / 'v4-readonly.json', manifest_path)}


def verify_hashes(rows, base):
    require(bool(rows), 'EMPTY_HASH_SET')
    for name, sha in rows.items():
        path = (base / name).resolve()
        require(path.is_relative_to(base.resolve()), 'HASH_PATH_ESCAPE')
        require(re.fullmatch('[a-f0-9]{64}', sha) and path.is_file() and digest(path) == sha,
                'ARTIFACT_DRIFT')


def verify_network(links, routes):
    require(len(links) == 1 and links[0].get('ifname') == 'lo', 'NETWORK_NOT_LOOPBACK_ONLY')
    require(all(r.get('dev') == 'lo' for r in routes), 'EXTERNAL_ROUTE_PRESENT')


def verify_emulator_command(argv, serial):
    require(argv and Path(argv[0]).name in ('qemu-system-x86_64', 'qemu-system-x86_64-headless', 'emulator'), 'NOT_EMULATOR_PROCESS')
    require('-port' in argv and argv[argv.index('-port') + 1] == serial.split('-')[1], 'EMULATOR_PORT_MISMATCH')
    require('-avd' in argv and argv[argv.index('-avd') + 1].startswith('oracle_'), 'NOT_ORACLE_AVD')
    require(not any(a in argv for a in ('-http-proxy', '-netdev', '-net', '-netsim-args')), 'UNREVIEWED_NETWORK_BACKEND')
