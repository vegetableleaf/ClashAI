"""Movement of every body of one card_id in one live log (decision raw_bodies): speed in tiles/s, path, kinds.
  python track.py <log basename> <card_id>"""
import json, sys
LOG = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
f, cid = sys.argv[1], int(sys.argv[2])
tr = {}
for l in open(LOG + f, encoding='utf8', errors='replace'):
    if not l.startswith('{"event": "decision"'):
        continue
    p = json.loads(l)['public']
    for b in p.get('raw_bodies', []):
        if int(b['card_id']) == cid:
            tr.setdefault(b['address'], []).append((p['raw_tick'], b['x'], b['y'], b['hp'], b['max_hp'], b['kind']))
for a, pts in tr.items():
    (t0, x0, y0, *_), (t1, x1, y1, *_) = pts[0], pts[-1]
    moving = [(pts[i + 1][0] - pts[i][0], ((pts[i + 1][1] - pts[i][1]) ** 2 + (pts[i + 1][2] - pts[i][2]) ** 2) ** .5)
              for i in range(len(pts) - 1)]
    sp = [d / 1000 / (dt / 20) for dt, d in moving if dt > 0]
    sp.sort()
    print(a, 'n', len(pts), 'ticks', t0, t1, 'from', (x0, y0), 'to', (x1, y1), 'max_hp', pts[0][4],
          'hp_end', pts[-1][3], 'median tiles/s %.2f' % (sp[len(sp) // 2] if sp else 0), 'kinds', sorted({q[5] for q in pts}))
