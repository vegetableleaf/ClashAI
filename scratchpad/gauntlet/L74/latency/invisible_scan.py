"""Opponent bodies the live model never sees: card_id without a catalog name, or a name with no model unit id
(pipeline.vocab.engine_unit_id -> None; from_engine(unmapped=set()) drops both silently)."""
import glob, json, sys
from collections import Counter
sys.path.insert(0, '.')
from pipeline.obs_contract import _catalog_names
from pipeline.vocab import engine_unit_id
names = _catalog_names()
drop, total, matches = Counter(), 0, Counter()
files = sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else 'scratchpad/gauntlet/L68/live_reader/live_play_20261008_*.jsonl'))
for f in files:
    seen = set()
    for line in open(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('event') != 'decision':
            continue
        pub = d['public']
        for b in pub.get('raw_bodies', []):
            if b['side'] == pub['observer_side'] or int(b.get('card_id', -1)) < 0:
                continue
            total += 1
            nm = names.get(int(b['card_id']))
            key = 'id:%d' % int(b['card_id']) if nm is None else (None if engine_unit_id(str(nm), float(b.get('max_hp') or 0)) is not None else nm)
            if key:
                drop[key] += 1; seen.add(key)
    for k in seen:
        matches[k] += 1
print('logs', len(files), 'opponent sightings', total, 'dropped', sum(drop.values()))
for k, n in drop.most_common(20):
    print('  ', k, 'sightings', n, 'matches', matches[k])
