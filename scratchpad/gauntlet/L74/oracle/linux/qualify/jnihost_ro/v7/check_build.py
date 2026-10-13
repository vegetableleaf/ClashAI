"""Recheck an offline build's exact inputs, sources and artifact hashes."""
import argparse
from pathlib import Path
from common import HERE, ROOT, BUILD, ignored, read_json, verify_hashes, load_inputs, require
from binding import project, validate_recipe, header


def check(build):
    build = ignored(build)
    receipt = read_json(build / 'build.json')
    require(receipt['schema_version'] == 7 and receipt['profile'] == 'staged_no_patches' and
            receipt['client_shells_compiled'] is False, 'BUILD_PROFILE')
    b, _, _, inputs = load_inputs()
    require(all(receipt['inputs'].get(k) == v for k, v in inputs.items()), 'BUILD_INPUT_SET')
    verify_hashes(receipt['inputs'], ROOT)
    verify_hashes(receipt['sources'], HERE)
    verify_hashes(receipt['artifacts'], build)
    runtime = read_json(build / 'runtime-binding.json')
    expected = project(b)
    if runtime['location_recipe'] is not None:
        expected['location_recipe'] = validate_recipe(runtime['location_recipe'])
    require(runtime == expected and (build / 'binding_keys.h').read_text() == header(), 'BUILD_BINDING')
    require(receipt['runtime_tested'] is False, 'OFFLINE_RECEIPT_NOT_RUNTIME_EVIDENCE')
    print('ORACLE_V7_BUILD_HASHES_OK')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir', type=Path, default=BUILD)
    check(p.parse_args().build_dir)
