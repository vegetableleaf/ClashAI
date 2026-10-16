"""Freeze the 20261016-linux runtime manifest from a pod's INSTALLED files (run with /workspace/venv35/bin/python).

    PYTHONDONTWRITEBYTECODE=1 /workspace/venv35/bin/python -I freeze_rt35.py OUT.json HEROIW_MANIFEST.json

Pins every file under purelib/royalesim and purelib/royalegym (the Linux .so and the data included; __pycache__ and
.dist-info excluded -- versions are checked from metadata by royale_runtime.activate). Cross-checks: royalesim's compiled
provenance is the v0.1.35 tag commit, clean; royalegym's .py bytes equal the 20261012 manifest's (0.1.23 at a7deb6e).
"""
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import sys
import sysconfig

SIM_PIN = '4fd4d54cdcbf6469aff4e4d87cb0dba523d295bc'   # git rev-parse v0.1.35^{commit} (RoyaleSim, fetched 2026-10-16)
GYM_PIN = 'a7deb6e48c3580fe2cd7d856b7c7d19ce67f02f9'   # v0.1.23, as the 20261012 manifest
VERSIONS = {'royalesim': '0.1.35', 'royalegym': '0.1.23'}


def main(out, heroiw_manifest):
    purelib = Path(sysconfig.get_paths()['purelib']).resolve()
    for name, v in VERSIONS.items():
        assert version(name) == v, (name, version(name))
    files = {}
    for pkg in VERSIONS:
        for p in sorted((purelib/pkg).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:
                files[p.relative_to(purelib).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    old = json.loads(Path(heroiw_manifest).read_text(encoding='utf8'))['files']
    gym = {k: v for k, v in files.items() if k.startswith('royalegym/') and k.endswith('.py')}
    assert gym == old, 'royalegym bytes differ from the 20261012 (0.1.23) manifest'
    sys.path.insert(0, str(purelib))
    import royalesim
    assert tuple(royalesim.Battle.provenance()) == (SIM_PIN, 'clean'), royalesim.Battle.provenance()
    assert royalesim.card_table_source() == 'embedded'
    manifest = dict(schema=1, pins={'RoyaleSim': SIM_PIN, 'RoyaleGym': GYM_PIN}, versions=VERSIONS,
                    wheels={k: f'{k}=={v}' for k, v in VERSIONS.items()}, files=files,
                    card_table='client160402017_20261006',
                    note='Frozen from the installed purelib of /workspace/venv35 (PyPI wheels, Linux x86_64) by '
                         'rt35/freeze_rt35.py; royalegym .py bytes == 20261012 manifest.')
    Path(out).write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf8')
    print(f'{len(files)} files pinned -> {out}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
