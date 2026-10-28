"""indiff2.py A.jsonl B.jsonl -- per match, which top-level keys differ (and play-level diffs)"""
import json, sys
a = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[1])}
b = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[2])}
print('only a', sorted(set(a) - set(b))[:5], 'only b', sorted(set(b) - set(a))[:5])
for m in sorted(set(a) & set(b)):
    ka = [k for k in set(a[m]) | set(b[m]) if a[m].get(k) != b[m].get(k)]
    if ka:
        print(m, ka)
        if 'plays' in ka:
            pa, pb = a[m]['plays'], b[m]['plays']
            for x in pa:
                if x not in pb: print('  -', json.dumps(x)[:300])
            for x in pb:
                if x not in pa: print('  +', json.dumps(x)[:300])
