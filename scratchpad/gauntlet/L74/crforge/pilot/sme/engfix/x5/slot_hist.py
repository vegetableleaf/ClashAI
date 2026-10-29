"""ENG-FIX5: per live frame in [T0, T1], print the row list as side:card(last 3 digits) when it changes, to follow slots.
python3 slot_hist.py FRAMES MATCH T0 T1"""
import json, os, sys
fr, m, t0, t1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
prev = None
for l in open(os.path.join(fr, m + '.jsonl')):
    o = json.loads(l)
    if not t0 <= o['t'] <= t1:
        continue
    sig = ['%d:%s@%d,%d' % (e[0], 'T' if e[3] == -1 else str(e[3]), e[1] // 100, e[2] // 100) for e in o['E']]
    key = [s.split('@')[0] for s in sig]
    if key != prev:
        print('t=%d n=%d' % (o['t'], len(sig)), ' '.join('%d=%s' % (k, s) for k, s in enumerate(sig)))
        prev = key
