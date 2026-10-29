"""ENG-FIX5: the live frame rows (index, row) of ticks T0..T1, towers left out. python3 live_rows.py FRAMES MATCH T0 T1"""
import json, os, sys
fr, m, t0, t1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
for l in open(os.path.join(fr, m + '.jsonl')):
    o = json.loads(l)
    if t0 <= o['t'] <= t1:
        print('t=%d' % o['t'], [(k, e) for k, e in enumerate(o['E']) if e[4] not in (4858, 7728) or e[3] != -1][:20])
