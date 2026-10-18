"""Live Tornado pull: enemy bodies' distance to the Tornado centre over its life (+ a few ticks), from logged frames.
    python live_pull.py LOG TORNADO_FX_START [PAD]"""
import json, math, sys

p, t0 = sys.argv[1], int(sys.argv[2])
pad = int(sys.argv[3]) if len(sys.argv) > 3 else 16
frames = []
with open(p, encoding='utf-8') as fh:
    for s in fh:
        if s.startswith('{"event": "frame"'):
            e = json.loads(s)
            if t0 - 4 <= e['tick'] <= t0 + 22 + pad:
                frames.append(e)
me = frames[0]['my_side']
c = None
for f in frames:
    fx = [x for x in f['fx'] if x[0] == me and x[3] == 28000012]
    if fx and c is None:
        c = (fx[0][1], fx[0][2])
rk = None
for f in frames:
    r = [x for x in f['proj'] if x[0] == me and x[3] == 28000003]
    if r:
        rk = (r[0][4], r[0][5])
print('tornado centre', c, 'rocket aim', rk, 'aim-centre', round(math.dist(c, rk) / 1000, 2) if rk else None)
track = {}
for f in frames:
    for x in f['ents']:
        if x[0] != me and x[6] not in (12, 13):
            track.setdefault(x[7], []).append((f['tick'], round(math.dist((x[1], x[2]), c) / 1000, 2), x[4]))
for a, v in track.items():
    if min(d for _, d, _ in v) <= 6.5:
        print(a[-6:], ' '.join(f"{t - t0:+d}:{d}" for t, d, hp in v[::2]), '| hp', v[0][2], '->', v[-1][2])
