"""Recount sanitized conversion artifacts and write the reviewable summary; no SIM."""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.pro2.convert import phase
from scratchpad.gauntlet.L74.pro2.build_rows import card_catalog, CHAMPIONS


def audit(directory):
    rows = [json.loads(line) for line in (directory/'replays.jsonl').read_text(encoding='utf-8').splitlines()]
    summary = json.loads((directory/'summary.json').read_text(encoding='utf-8'))
    receipts = json.loads((directory/'audit.json').read_text(encoding='utf-8'))
    counts = Counter(r['status'] for r in receipts)
    assert len(rows)+len(receipts) == summary['counts']['input_files']
    assert len(rows) == len({r['tag'] for r in rows}) == summary['counts']['new_replays']
    for key in ('existing_corpus','input_duplicate','parse_error'):
        assert counts[key] == summary['counts'].get(key,0)
        summary['counts'][key] = counts[key]
    assert dict(Counter(t for r in rows for t in r['deck_types'].values())) == summary['deck_sides']
    assert dict(Counter(phase(e['tick']) for r in rows for e in r['plays'] if not e['ability'])) == summary['source_play_events_by_phase']
    ready = [r for r in rows if not r['blocks']]
    with (directory/'battles.csv').open(encoding='utf-8',newline='') as handle:
        battles = list(csv.DictReader(handle))
    assert len(battles) == len(ready) == summary['counts']['crawl_ready']
    expected_plays = sum(len(r['plays']) for r in ready)
    with (directory/'plays_ext.csv').open(encoding='utf-8',newline='') as handle:
        plays = list(csv.DictReader(handle))
    assert len(plays) == expected_plays == sum(int(b['plays']) for b in battles)
    assert all(p['attr_i']=='0' for p in plays)
    catalog = card_catalog()
    summary['counts']['battle_time_available'] = sum(r['battle_time'] is not None for r in rows)
    summary['catalog_preflight'] = dict(
        unsupported_card_sides=dict(Counter(c for r in ready for d in r['decks'].values() for c in d if c not in catalog)),
        replays_with_unsupported_cards=sum(any(c not in catalog for d in r['decks'].values() for c in d) for r in ready),
        replays_with_ability_events=sum(any(e['ability'] for e in r['plays']) for r in rows),
        ability_events_without_known_champion_or_visible_hero=sum(e['ability'] and not any(
            c in CHAMPIONS or c.endswith('-hero') for c in r['decks'][str(e['side'])]) for r in ready for e in r['plays']))
    summary['crawl_ready_deck_sides'] = dict(Counter(t for r in ready for t in r['deck_types'].values()))
    summary['crawl_ready_source_play_events_by_phase'] = dict(Counter(phase(e['tick']) for r in ready for e in r['plays'] if not e['ability']))
    return summary


if __name__ == '__main__':
    here = Path(__file__).resolve().parent
    directory = Path(sys.argv[1]) if len(sys.argv)>1 else here/'output'
    result = audit(directory)
    (directory/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (here/'conversion_summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PRO2_SOURCE_AUDIT_PASS', result['counts'])
