"""ENG-FIX5: summary of a FRESH inputs file for its freeze file: RNG-free / flagged records, tower_zap / zap_dead firings,
reader_hidden windows, ability sources. python -I inp_summary.py INPUTS_RNGFREE.jsonl"""
import collections, json, sys
recs = [json.loads(l) for l in open(sys.argv[1])]
flagged = {r['match'][10:]: r['flags'] for r in recs if r.get('flags')}
print('records', len(recs), 'flagged', len(flagged), 'unflagged', len(recs) - len(flagged))
for m, f in sorted(flagged.items()):
    print('  flagged', m, f)
print('tower_zap', [(r['match'][10:], [(z.get('R'), z.get('x'), z.get('y')) for z in r['tower_zap']]) for r in recs if r.get('tower_zap')])
print('zap_dead', [(r['match'][10:], [(z.get('R'), z.get('x'), z.get('y')) for z in r['zap_dead']]) for r in recs if r.get('zap_dead')])
print('reader_hidden windows', [(r['match'][10:], len(r['reader_hidden'])) for r in recs if r.get('reader_hidden')])
src = collections.Counter(p.get('source') for r in recs for p in r['plays'] if p['kind'] != 'play')
print('ability sources', dict(src))
