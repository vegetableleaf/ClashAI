"""L74 combo: enemy bodies of a logged live frame in the BOARD frame (tiles, me at the bottom), for regression boards.
    python dump_live_board.py LOG TICK [TICK ...]      (nearest frame at or after each tick)"""
import json
import sys

from pipeline.body_identity import CATALOG

log, ticks = sys.argv[1], [int(t) for t in sys.argv[2:]]
names = {}
for c in json.loads(CATALOG.read_text(encoding='utf-8'))['cards']:
    for k in ('id', 'card_id', 'definition_id'):
        if c.get(k) is not None:
            names[int(c[k])] = c['name']
frames = [json.loads(s) for s in open(log, encoding='utf-8') if s.startswith('{"event": "frame"')]
for t in ticks:
    f = next(x for x in frames if x['tick'] >= t)
    me = f['my_side']
    print('tick', f['tick'], 'my_side', me, 'elixir', f['elixir'])
    for e in f['ents']:
        if e[0] == me or e[6] in (12, 13):
            continue
        bx, by = (18 - e[1] / 1000, e[2] / 1000) if me == 1 else (e[1] / 1000, 32 - e[2] / 1000)
        print(f"  {names.get(e[3], e[3])!s:16s} board ({bx:5.2f}, {by:5.2f}) hp {e[4]}/{e[5]} kind {e[6]} {e[7][-6:]}")
