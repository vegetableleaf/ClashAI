"""python fdiff10.py LIVE_LOG T0 T1 [SKIP_SUBSTR ...] -- flattened fields of whole frame records that change between
consecutive frames in [T0, T1], minus keys containing any SKIP substring; plus non-frame events in the range."""
import json, sys
f, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
skip = sys.argv[4:]


def flat(x, pre=''):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from flat(v, pre + '.' + str(k))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from flat(v, pre + '[%d]' % i)
    else:
        yield pre, x


prev = None
for l in open(f, 'rb'):
    j = json.loads(l)
    t = j.get('tick')
    if t is None or not t0 <= t <= t1:
        continue
    if j.get('event') != 'frame':
        print('EV', t, json.dumps(j)[:300])
        continue
    cur = {k: v for k, v in flat(j) if not any(s in k for s in skip)}
    if prev is not None:
        print(t, {k: (prev.get(k), cur.get(k)) for k in set(prev) | set(cur) if prev.get(k) != cur.get(k)})
    prev = cur
