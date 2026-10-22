"""Read a div.py dossier by eye: card views, events, flags, the first divergences, then a frame-by-frame live | SIM diff of the
bodies named in the first N divergences (plus the anchor's bodies), every frame until the window end or --until.
  python show.py DOSSIER.json [--n 4] [--until TICK] [--ids id8,id8]"""
import json
import sys

d = json.load(open(sys.argv[1]))
n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 4
until = int(sys.argv[sys.argv.index('--until') + 1]) if '--until' in sys.argv else 10 ** 9
for key, x in d.items():
    print('=' * 100); print(key)
    print('live card view:', json.dumps(x['card']['live'])[:400]); print('SIM  card view:', json.dumps(x['card']['sim'])[:400])
    print('events:', x['events']); print('flags:', x['flags'])
    print('first divergences:')
    for v in x['div'][:15]:
        print('  ', v)
    ids = {str(v[4])[:6] for v in x['div'][:n]}
    for ab in x['anchor_bodies']:
        ids.add(ab['id'][:6])
    if '--ids' in sys.argv:
        ids = set(sys.argv[sys.argv.index('--ids') + 1].split(','))
    t0 = x['rows'][0][0]
    print('frames (live: hp x y ->tgt state | SIM: hp x y ->tgt phase stun kb charge), bodies', sorted(ids))
    for t, live, sim in x['rows']:
        if t > until:
            break
        L = {r[0][:6]: r for r in live}
        S = {str(r[0])[:6]: r for r in sim}
        parts = []
        for i in sorted(ids):
            a, b = L.get(i), S.get(i)
            if a is None and b is None:
                continue
            la = f"{a[3]} ({a[4]},{a[5]}) ->{a[6][:6]} s{a[7]}" if a else '-'
            sb = f"{b[3]} ({b[4]},{b[5]}) ->{str(b[6])[:6]} {b[7]} {b[8] or ''} {b[9] or ''} {b[10] or ''}" if b else '-'
            nm = (a or b)[1]
            parts.append(f"{nm}:{i} L[{la}] S[{sb}]")
        tw = [f"{r[0][:3]}:{r[3]}/{(S.get(r[0][:6]) or [None]*4)[3]}" for r in live if str(r[0]).startswith('T')]
        print(f"t{t} (+{t - t0}) | " + ' || '.join(parts) + ' | towers ' + ' '.join(tw))
