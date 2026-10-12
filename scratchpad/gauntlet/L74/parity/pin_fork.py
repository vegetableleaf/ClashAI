"""Write a Linux build receipt, binding the wheel, installed files and source SHA."""
import argparse
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wheel', type=Path, required=True)
    a = ap.parse_args()
    source = ROOT/'research/ext/Royale/RoyaleSim'
    target = ROOT/'research/ext/Royale-fork'
    runtime = target/'runtime'
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()
    if git('status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('tracked fork source is dirty')
    versions = {d.metadata['Name'].lower(): d.version for d in distributions(path=[str(runtime)])}
    if versions.get('royalegym') != '0.1.23' or 'royalesim' not in versions:
        raise RuntimeError('fork/gym installation missing')
    sys.path.insert(0, str(runtime))
    import royalesim
    if tuple(royalesim.Battle.provenance()) != (git('rev-parse', 'HEAD'), 'clean'):
        raise RuntimeError('compiled provenance mismatch')
    files = {p.relative_to(runtime).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(runtime.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    manifest = dict(schema=1, pins={'RoyaleSim': git('rev-parse', 'HEAD'),
                                  'RoyaleGym': 'a7deb6e48c3580fe2cd7d856b7c7d19ce67f02f9'},
                    upstream_base=git('merge-base', 'HEAD', 'origin/HEAD'), versions=versions,
                    wheels={'royalesim': a.wheel.name, 'royalegym': 'royalegym==0.1.23'},
                    wheel_sha256=hashlib.sha256(a.wheel.read_bytes()).hexdigest(), files=files,
                    engine_options={'calibration_overrides': {'cards.CARD_TABLE': 'client160402017_20261006'}})
    (target/'build_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf8')


if __name__ == '__main__':
    main()
