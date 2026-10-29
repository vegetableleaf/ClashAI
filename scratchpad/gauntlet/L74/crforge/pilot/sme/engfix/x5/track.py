"""ENG-FIX5: live rows of one card id (and side) per frame in [T0, T1]. python track.py FRAMES MATCH T0 T1 CARD [CARD...]"""
import json, os, sys
fr, m, t0, t1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
cards = {int(c) for c in sys.argv[5:]}
for l in open(os.path.join(fr, m + '.jsonl')):
    o = json.loads(l)
    if t0 <= o['t'] <= t1:
        print(o['t'], [e for e in o['E'] if e[3] in cards], 'B', [b for b in o['B'] if 'Golden' in str(b) or 'Dash' in str(b)][:3])
