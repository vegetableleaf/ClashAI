"""ENG-FIX5: compare extracted records by match. python cmp_ex.py A.jsonl B.jsonl [--plays]
Prints per match: identical / differs (keys that differ); --plays also lists the play-order differences."""
import json, sys
a = {json.loads(l)['match']: l.rstrip('\n') for l in open(sys.argv[1])}
b = {json.loads(l)['match']: l.rstrip('\n') for l in open(sys.argv[2])}
for m in sorted(set(a) & set(b)):
    if a[m] == b[m]:
        print(m[10:], 'IDENTICAL'); continue
    ra, rb = json.loads(a[m]), json.loads(b[m])
    print(m[10:], 'DIFFERS', [k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k)])
    if '--plays' in sys.argv:
        for i, (p, q) in enumerate(zip(ra['plays'], rb['plays'])):
            if p != q:
                print('   slot %d: %s %s %d -> %s %s %d' % (i, p['side'], p.get('card'), p['tick'], q['side'], q.get('card'), q['tick']))
print('only in A', sorted(set(a) - set(b))[:5], 'only in B', len(set(b) - set(a)))
