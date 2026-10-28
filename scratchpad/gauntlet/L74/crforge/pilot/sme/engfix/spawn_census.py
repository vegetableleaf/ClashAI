"""ENG-FIX (SME_OWN_SPAWN): confirmed own plays whose confirmation saw the body >= 0.75 tiles from the tap, per log.
    python -I spawn_census.py LIVE_DIR LIST... (LIST: .jsonl with "match" or .tsv first column)"""
import collections, json, os, sys
live, n, hist = sys.argv[1], 0, collections.Counter()
for f in sys.argv[2:]:
    ms = [json.loads(l)['match'] for l in open(f)] if f.endswith('.jsonl') else \
        [l.split('\t')[0] for l in open(f) if l.strip() and not l.startswith('#')]
    for m in ms:
        for line in open(os.path.join(live, m + '.jsonl'), 'rb'):
            if b'"confirmed"' not in line[:30]:
                continue
            d = json.loads(line)
            if d['event'] != 'confirmed':
                continue
            n += 1
            e = d.get('err_tiles')
            hist['none' if e is None else '>=1' if e >= 1 else '>=0.75' if e >= .75 else '<0.75'] += 1
            if e is not None and e >= .75:
                print(os.path.basename(f), m[10:], d['tick'], d['name'], round(e, 2), d.get('intended'), d.get('spawn'))
print('confirmed', n, dict(hist))
