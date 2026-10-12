"""Verify an existing private device audit without executing SIM or contacting adb."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_build import ROOT, git_blob, with_related
from compare import compare_cards, cards_by_name, ICEBOW
from decoder import decode, sha, csv_records
from levels import level_report


def main():
    latest = json.loads((HERE/'out/device_builds/latest.json').read_text())
    run = Path(latest['report']).parent
    report = json.loads((run/'report.json').read_text(encoding='utf-8'))
    manifest = report['manifest']
    update = Path(manifest['device_update']['path'])
    assert not manifest['failures'] and not manifest['conflicts']
    assert manifest['device_update']['input_files'] == sum(p.is_file() for p in update.rglob('*'))
    for name, meta in manifest['device_update']['metadata'].items():
        assert sha((update/name).read_bytes()) == meta['sha256']
    for name, entry in manifest['files'].items():
        assert sha((run/'tables'/name).read_bytes()) == entry['sha256'], name
        if entry['source'] == 'device_update':
            raw = (update/name).read_bytes()
            assert sha(raw) == entry['input_sha256'], name
            assert sha(decode(raw)[0]) == entry['sha256'], name
        else:
            assert entry['source'] == 'apk_fallback' and not (update/name).exists(), name
    for apk in manifest['apks']:
        # Stream large split archives; all source inputs stay read-only.
        import hashlib
        with (Path(report['sources']['apk_dir'])/apk['name']).open('rb') as f:
            assert hashlib.file_digest(f, 'sha256').hexdigest() == apk['sha256']
    for name, digest in report['sources']['tool'].items():
        assert sha((HERE/name).read_bytes()) == digest, name
    for name in ('census', 'pro2', 'live_options'):
        source = report['sources'][name]
        assert sha(Path(source['path']).read_bytes()) == source['sha256'], name
    for name, digest in report['normalization']['sources'].items():
        assert sha((run/'parser/tools'/name).read_bytes()) == digest, name
    doc = json.loads((run/'cards.json').read_text(encoding='utf-8'))
    raw_rarities = csv_records((run/'tables/csv_logic/rarities.csv').read_bytes())
    for rarity, parsed in doc['rarities'].items():
        rows = raw_rarities[rarity]
        percentages = [r['PowerLevelMultiplier'] for r in rows if r.get('PowerLevelMultiplier') is not None]
        assert parsed['relative_level'] == rows[0]['RelativeLevel']
        assert parsed['multiplier_percent_by_level'] == [100, *percentages[:rows[0]['LevelCount']-1]]
    xbow = cards_by_name(doc)['Xbow']
    assert xbow['damage'] == xbow['projectile']['damage'] == 24
    assert xbow['level_scaling']['ladder_rarity'] == 'Common'
    assert doc['rarities']['Common']['multiplier_percent_by_level'][10] == 256
    assert report['xbow_l11']['damage'] == 61
    assert len(report['opponents']['top']) == 60
    assert set(ICEBOW) <= set(report['main_names'])
    per_level = level_report(doc, [r['card'] for r in report['opponents']['top']])
    assert report['per_level'] == per_level
    assert all(r['status'] == 'ok' for r in per_level)
    assert json.loads((run/'per_level.json').read_text()) == per_level
    counts = {}
    for label, rows in report['comparisons'].items():
        source = report['sources']['tables'][label]
        if source['path'].startswith('git:'):
            _, ref, path = source['path'].split(':', 2)
            raw = git_blob(ROOT/'research/ext/Royale/RoyaleSim', ref, path)
        else:
            raw = Path(source['path']).read_bytes()
        assert sha(raw) == source['sha256'], label
        assert rows == compare_cards(doc, with_related(json.loads(raw)), [r['card'] for r in rows])
        assert set(report['main_names']) <= {r['card'] for r in rows}
        counts[label] = dict(main=dict(Counter(r['status'] for r in rows if r['card'] in report['main_names'])),
                             all=dict(Counter(r['status'] for r in rows)))
    assert {'old/cards-15.535.json', 'selected-0.1.33'} <= counts.keys()
    # Positive control: source files must NOT be ignored by the same predicate.
    for path, expected in [(run/'cards.json', 0), (update/'fingerprint.json', 0), (HERE/'levels.py', 1)]:
        assert subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-q', str(path)]).returncode == expected
    receipt = dict(run=str(run), source_hashes_verified=True, per_level_rows=len(per_level),
                   device_tables=len(manifest['device_update']['files']),
                   apk_fallbacks=len(manifest['apk_fallbacks']), comparisons=counts,
                   xbow_l11=report['xbow_l11']['damage'])
    (HERE/'out/device_audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))
    print('APKTABLES_DEVICE_PASS')


if __name__ == '__main__':
    main()
