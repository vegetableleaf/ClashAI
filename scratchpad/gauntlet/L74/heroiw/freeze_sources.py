"""Offline maintainer utility: freeze fetched release sources, never fetch/install."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(ROOT/'research/ext/Royale'/repo), *args])


def main():
    pins = {r: git(r, 'rev-parse', f'{tag}^{{commit}}').decode().strip()
            for r, tag in [('RoyaleSim', 'v0.1.33'), ('RoyaleGym', 'v0.1.23')]}
    for repo, pin in pins.items():
        assert git(repo, 'rev-parse', 'origin/HEAD').decode().strip() == pin
    names = git('RoyaleGym', 'ls-tree', '-r', '--name-only', 'origin/HEAD', 'royalegym').decode().splitlines()
    files = {n: hashlib.sha256(git('RoyaleGym', 'show', f'origin/HEAD:{n}')).hexdigest()
             for n in names if n.endswith('.py')}
    manifest = dict(schema=1, pins=pins, versions={'royalesim': '0.1.33', 'royalegym': '0.1.23'},
                    wheels={'royalesim': 'royalesim==0.1.33', 'royalegym': 'royalegym==0.1.23'}, files=files,
                    card_table='client160402017_20261006',
                    note='Release tags equal fetched origin/HEAD. Wheel bytes/API must be verified on pod.')
    (HERE/'build_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf8')
    # Compact source diff used for the plain-language behavior review.
    old = json.loads(git('RoyaleSim', 'show', 'v0.1.18:data/calibration.json'))
    new = json.loads(git('RoyaleSim', 'show', 'origin/HEAD:data/calibration.json'))
    changes = {}
    for section, fields in new.items():
        if not isinstance(fields, dict):
            continue
        for key, row in fields.items():
            if not isinstance(row, dict) or 'value' not in row:
                continue
            previous = old.get(section, {}).get(key, {})
            if previous.get('value') != row['value']:
                changes[f'{section}.{key}'] = dict(old=previous.get('value'), new=row['value'],
                                                  meaning=row.get('meaning', ''))
    (HERE/'calibration_changes.json').write_text(json.dumps(changes, indent=2)+'\n', encoding='utf8')


if __name__ == '__main__':
    main()
