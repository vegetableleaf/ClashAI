"""For every chained-area pair the reader shows (two fx rows, same side / point / card on one frame, the child's
remaining ms at most its row life), and every parent area of a chaining card at its first sighting: the parent's
remaining ms at first sighting and whether a child row is on that frame. Live logs = argv[1], match list = argv[2]."""
import json, sys, collections, os
d, names = sys.argv[1], [l.strip() for l in open(sys.argv[2]) if l.strip()]
CH = {28000002: (4500, 'Rage')}   # Rage card id -> parent life
tally = collections.Counter(); ex = collections.defaultdict(list)
for m in names:
    seen_parent = {}
    prev = None
    for line in open(os.path.join(d, m + '.jsonl'), 'rb'):
        if b'"frame"' not in line[:40]:
            continue
        f = json.loads(line); t = f['tick']
        if t is None or t < 0 or t == prev:
            continue
        gap = None if prev is None else t - prev
        prev = t
        rows = [a for a in f['fx'] if a[3] in CH]
        for a in rows:
            full = CH[a[3]][0]
            if a[4] > 1 and a[6] not in seen_parent:
                seen_parent[a[6]] = t
                child = [b for b in rows if b is not a and b[4] == 1 and (b[0], b[1], b[2]) == (a[0], a[1], a[2])]
                k = (CH[a[3]][1], 'rem=%d' % a[4], 'child_on_frame' if child else 'no_child', 'gap=%s' % gap)
                tally[k] += 1; ex[k].append('%s@%d' % (m[10:], t))
            if a[4] == 1 and not any(b[4] > 1 and (b[0], b[1], b[2]) == (a[0], a[1], a[2]) for b in rows):
                tally[(CH[a[3]][1], 'child_without_parent')] += 1; ex[(CH[a[3]][1], 'child_without_parent')].append('%s@%d' % (m[10:], t))
for k, v in sorted(tally.items()):
    print(v, k, ex[k][:6])
