"""Dump reader fx rows (side,x,y,card,remaining_ms,level,addr,gen) for ticks in [lo,hi] of a live log."""
import json, sys
path, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
seen = set()
for line in open(path, 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    t = d['tick']
    if t is None or not lo <= t <= hi or t in seen:
        continue
    seen.add(t)
    print(t, d.get('game_tick'), [a for a in d['fx']])
