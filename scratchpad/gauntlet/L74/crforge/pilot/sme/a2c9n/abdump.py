"""abdump.py MATCH T0 T1 NAMESUB -- the reader's phase-2 unit rows (ability fields etc.) whose name contains NAMESUB"""
import json, sys
p = r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\live_play_%s.jsonl' % sys.argv[1]
t0, t1, sub = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
seen = set()
for line in open(p, 'rb'):
    if b'"frame"' not in line[:40]:
        continue
    d = json.loads(line)
    t = d.get('tick')
    if t is None or t in seen or not t0 <= t <= t1:
        continue
    seen.add(t)
    for u in (d.get('phase2') or {}).get('units', []):
        if sub in u.get('name', ''):
            print(t, json.dumps({k: v for k, v in u.items() if k not in ('name',)})[:900])
