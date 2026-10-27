"""Recorded track of one body, followed back and forward by nearest same-side position (ticket A2c round 6.0).
    python3 rectrack6.py MATCH T0 SIDE X Y [BACK] [FWD]   -> t, x, y, card, hp, kind(state), step per tick"""
import json, sys
m, t0, side, x, y = 'live_play_' + sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
back = int(sys.argv[6]) if len(sys.argv) > 6 else 40
fwd = int(sys.argv[7]) if len(sys.argv) > 7 else 10
fr = {f['t']: f for f in map(json.loads, open('/workspace/pilot/sme_live/frames2/%s.jsonl' % m))}
ts = sorted(fr)
i0 = ts.index(t0)


def follow(order):
    px, py, pt, card, out = x, y, t0, None, []
    for t in order:
        c = [e for e in fr[t]['E'] if e[0] == side and (card is None or e[3] == card)]
        if not c:
            break
        e = min(c, key=lambda e: abs(e[1] - px) + abs(e[2] - py))
        d = abs(e[1] - px) + abs(e[2] - py)
        if d > 600 * max(1, abs(t - pt)):
            break
        card = e[3]
        out.append((t, e[1], e[2], e[3], e[4], e[5], round(d / max(1, abs(t - pt)))))
        px, py, pt = e[1], e[2], t
    return out


for r in reversed(follow(reversed(ts[max(0, i0 - back):i0 + 1]))):
    print(*r)
for r in follow(ts[i0 + 1:i0 + 1 + fwd]):
    print(*r)
