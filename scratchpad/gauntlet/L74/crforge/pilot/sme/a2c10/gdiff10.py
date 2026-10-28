"""python gdiff10.py LIVE_LOG T0 T1 GEN -- every field of one generation's reader records (ents_state, phase2 unit, phase3
body) that changes between consecutive frames in [T0, T1]."""
import json, sys
f, t0, t1, g = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])


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
    if b'"frame"' not in l[:30]:
        continue
    j = json.loads(l)
    t = j['tick']
    if not t0 <= t <= t1:
        continue
    cur = {}
    for i, e in enumerate(j.get('ents_state') or []):
        if e[-1] == g:
            cur.update(dict(flat(e, 'state')))
            cur.update(dict(flat(j['ents'][i], 'ent')))
    for u in (j.get('phase2') or {}).get('units', []):
        if u.get('generation') == g:
            cur.update(dict(flat(u, 'p2')))
    for b in (j.get('phase3') or {}).get('bodies', []):
        if b.get('generation') == g:
            cur.update(dict(flat(b, 'p3')))
    if prev is None:
        print(t, 'keys', sorted(cur)[:80])
    else:
        ch = {k: (prev.get(k), cur.get(k)) for k in set(prev) | set(cur) if prev.get(k) != cur.get(k)}
        print(t, ch)
    prev = cur
