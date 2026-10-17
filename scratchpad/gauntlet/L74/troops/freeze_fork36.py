"""Freeze the fork36-linux runtime manifest from a pod's INSTALLED files (run with /workspace/venvf36/bin/python).

    PYTHONDONTWRITEBYTECODE=1 /workspace/venvf36/bin/python -I freeze_fork36.py OUT.json RT35_MANIFEST.json WHEEL

As rt35/freeze_rt35.py (20261016-linux), for the ClashBot RoyaleSim fork branch clashbot36 head bc2bf9d (v0.1.36 +
12 measured law commits + Battle.set_tower_troops), built by parity/night1016/fork_build.sh from
pod_backup_weekend/fork35/clashbot36_bc2bf9d.bundle and pip-installed (--no-deps) into the venv. Pins every file under
purelib/royalesim and purelib/royalegym (no __pycache__ / .dist-info; versions come from metadata in activate).
Cross-checks: compiled provenance = bc2bf9d, clean; embedded card table; royalegym .py bytes == the 20261016-linux
(0.1.23) manifest's; the fork's tower-troop API is present.
"""
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import sys
import sysconfig

SIM_PIN = 'bc2bf9d71234002a9f1911fbf2ddae1ee924a7db'   # git rev-parse bc2bf9d (C:/Users/benpe/rsfork36, branch clashbot36)
GYM_PIN = 'a7deb6e48c3580fe2cd7d856b7c7d19ce67f02f9'   # royalegym v0.1.23, as the 20261016-linux manifest
VERSIONS = {'royalesim': '0.1.36', 'royalegym': '0.1.23'}


def main(out, rt35_manifest, wheel):
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
    assert tuple(royalesim.Battle.provenance()) == (SIM_PIN, 'clean'), royalesim.Battle.provenance()
    assert royalesim.card_table_source() == 'embedded'
    assert hasattr(royalesim.Battle, 'set_tower_troops'), 'not the tower-troop fork'
    manifest = dict(schema=1, pins={'RoyaleSim': SIM_PIN, 'RoyaleGym': GYM_PIN}, versions=VERSIONS,
                    wheels={'royalesim': Path(wheel).name, 'royalegym': 'royalegym==0.1.23'},
                    wheel_sha256=hashlib.sha256(Path(wheel).read_bytes()).hexdigest(), files=files,
                    card_table='client160402017_20261006',
                    note='Frozen from the installed purelib of /workspace/venvf36 (fork clashbot36 bc2bf9d wheel, '
                         'royalegym 0.1.23 PyPI, Linux x86_64) by troops/freeze_fork36.py; royalegym bytes == rt35.')
    Path(out).write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf8')
    print(f'{len(files)} files pinned -> {out}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
