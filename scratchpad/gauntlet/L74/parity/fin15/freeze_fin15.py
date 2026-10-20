"""Freeze the fin15-linux runtime manifest from a pod's INSTALLED files (run with /workspace/venvf15's python).

    PYTHONDONTWRITEBYTECODE=1 /workspace/venvf15/bin/python -I freeze_fin15.py OUT.json RT35_MANIFEST.json WHEEL SIM_PIN

stepd/freeze_fin13.py with the pin passed in: the fork branch fin15 head (W8 10-20; parity/fin15/FIN15.md), installed --no-deps into
/workspace/venvf15 (a hard-link copy of venvf36: torch / royalegym bytes shared). Pins every file under purelib/royalesim and
purelib/royalegym. Cross-checks: compiled provenance = SIM_PIN, clean; embedded card table; royalegym .py bytes == the
20261016-linux (0.1.23) manifest's; the fork's tower-troop API is present.
"""
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import sys
import sysconfig

GYM_PIN = 'a7deb6e48c3580fe2cd7d856b7c7d19ce67f02f9'   # royalegym v0.1.23, as the 20261016-linux manifest
VERSIONS = {'royalesim': '0.1.36', 'royalegym': '0.1.23'}


def main(out, rt35_manifest, wheel, sim_pin):
    purelib = Path(sysconfig.get_paths()['purelib']).resolve()
    for name, v in VERSIONS.items():
        assert version(name) == v, (name, version(name))
    files = {}
    for pkg in VERSIONS:
        for p in sorted((purelib/pkg).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:
                files[p.relative_to(purelib).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    old = json.loads(Path(rt35_manifest).read_text(encoding='utf8'))['files']
    gym = {k: v for k, v in files.items() if k.startswith('royalegym/')}
    assert gym == {k: v for k, v in old.items() if k.startswith('royalegym/')}, 'royalegym bytes differ from 20261016-linux'
    sys.path.insert(0, str(purelib))
    import royalesim
    assert tuple(royalesim.Battle.provenance()) == (sim_pin, 'clean'), royalesim.Battle.provenance()
    assert royalesim.card_table_source() == 'embedded', royalesim.card_table_source()
    assert hasattr(royalesim.Battle, 'set_tower_troops'), 'not the tower-troop fork'
    manifest = dict(schema=1, pins={'RoyaleSim': sim_pin, 'RoyaleGym': GYM_PIN}, versions=VERSIONS,
                    wheels={'royalesim': Path(wheel).name, 'royalegym': 'royalegym==0.1.23'},
                    wheel_sha256=hashlib.sha256(Path(wheel).read_bytes()).hexdigest(), files=files,
                    card_table='client160402017_20261006',
                    note='Frozen from the installed purelib of /workspace/venvf15 (fork fin15 = fin14c + the W8 laws, '
                         'royalegym 0.1.23 PyPI, Linux x86_64) by parity/fin15/freeze_fin15.py; royalegym bytes == rt35.')
    Path(out).write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf8')
    print(f'{len(files)} files pinned -> {out}')


if __name__ == '__main__':
    main(*sys.argv[1:5])
