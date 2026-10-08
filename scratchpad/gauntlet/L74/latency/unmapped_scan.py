"""Owner 10-08: can the model see Minion Giant? Count opponent reader bodies whose card_id has no catalog name
(-> obs_contract drops them live: from_engine(unmapped=set())). Logs = current bundle era by default."""
import glob, json, sys
from collections import Counter
sys.path.insert(0, '.')
from pipeline.obs_contract import _catalog_names
names = _catalog_names()
bad, total, per_match = Counter(), 0, Counter()
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
            cid = int(b['card_id'])
            if cid not in names:
                bad[cid] += 1
                seen.add(cid)
    for cid in seen:
        per_match[cid] += 1
print('logs', len(files), 'catalog size', len(names), 'opponent body sightings', total)
print('UNMAPPED card_ids (sightings, matches):', [(c, bad[c], per_match[c]) for c, _ in bad.most_common(15)])
