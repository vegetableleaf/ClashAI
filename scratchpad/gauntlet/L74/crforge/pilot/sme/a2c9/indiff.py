"""python -I indiff.py OLD.jsonl NEW.jsonl -- plays that differ between two inputs files (per match, as a multiset)"""
import json, sys
a = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[1])}
b = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[2])}
n = 0
for m in sorted(set(a) | set(b)):
    ra, rb = a.get(m), b.get(m)
    if ra is None or rb is None:
        print(m, 'missing in', 'old' if ra is None else 'new'); continue
    pa = sorted(json.dumps(p, sort_keys=True) for p in ra['plays'])
    pb = sorted(json.dumps(p, sort_keys=True) for p in rb['plays'])
    for x in sorted(set(pa) - set(pb)):
        print(m, '-', x); n += 1
    for x in sorted(set(pb) - set(pa)):
        print(m, '+', x); n += 1
    oa = {k: v for k, v in ra.items() if k != 'plays'}
    ob = {k: v for k, v in rb.items() if k != 'plays'}
    if json.dumps(oa, sort_keys=True) != json.dumps(ob, sort_keys=True):
        print(m, 'other fields differ:', [k for k in set(oa) | set(ob) if oa.get(k) != ob.get(k)])
print('changed play rows', n)
