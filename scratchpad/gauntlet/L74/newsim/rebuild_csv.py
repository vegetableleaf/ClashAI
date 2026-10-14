"""Recover the ignored CSV from saved public pages, entirely offline.

This is source-input dedupe, not a new audit against the absent training corpus.
The earlier PRO2 conversion reported zero corpus overlaps. Counts are checked
against its tracked receipt before the CSV is used for NEWSIM.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.pro2.convert import convert

if __name__ == '__main__':
    out = ROOT/'scratchpad/gauntlet/L74/pro2/output'
    result = convert([Path('C:/Users/benpe/Downloads/raw2/raw'), Path('C:/Users/benpe/Downloads/bait')], out, [], [])
    prior = json.loads((out.parent/'conversion_summary.json').read_text())
    for name in ('input_files', 'new_replays', 'crawl_ready', 'source_blocked', 'input_duplicate', 'parse_error'):
        assert result['counts'].get(name, 0) == prior['counts'][name], name
    print(json.dumps(result, indent=2))
