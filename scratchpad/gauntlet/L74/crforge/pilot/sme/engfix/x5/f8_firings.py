"""ENG-FIX5: FRESH8 firings of each new flag = records whose extraction without that flag differs from the frozen inputs
(all 19 flags). Prints, per flag, the changed records, the differing fields / plays, and the record's F8_main result.
python -I f8_firings.py FROZEN_ALL.jsonl RESULTS.jsonl MINUS_<FLAG>.jsonl [...]"""
import json, sys
from pathlib import Path
frozen = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[1])}
res = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[2])}
key = lambda p: json.dumps(p, sort_keys=True)  # noqa: E731
for f in sys.argv[3:]:
    flag = Path(f).stem.replace('f8_minus_', '')
    minus = {json.loads(l)['match']: json.loads(l) for l in open(f)}
    ch = [m for m in frozen if frozen[m] != minus.get(m)]
    print('==', flag, 'firings (records changed):', len(ch))
    for m in ch:
        a, b = frozen[m], minus[m]
        fields = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        pa, pb = {key(p) for p in a['plays']}, {key(p) for p in b['plays']}
        r = res.get(m)
        print('  ', m[10:], 'rng_free', a['rng_free'], 'flags', a['flags'], 'fields', fields)
        print('     with flag only:', [(p['kind'], p.get('card'), p['side'], p['tick'], p.get('source'), p.get('x'), p.get('y')) for p in map(json.loads, pa - pb)])
        print('     without only  :', [(p['kind'], p.get('card'), p['side'], p['tick'], p.get('source'), p.get('x'), p.get('y')) for p in map(json.loads, pb - pa)])
        if a.get('plays') == b.get('plays') and fields:
            print('     non-play fields:', {k: (str(a.get(k))[:120], str(b.get(k))[:120]) for k in fields})
        print('     F8_main:', (r['counts'], r['first_div']) if r else 'not scored (not RNG-free)')
