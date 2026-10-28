"""rdorder9.py M:RUN:X0,Y0:X1,Y1 ... -- A2c-9R: in the first recorded frames after a same-run pair of plays (side-0 play point
X0,Y0 and side-1 play point X1,Y1), the reader's row order of the new bodies: is the reader's list order the game's creation order?
Prints, per frame in [RUN, RUN+6], the row indices and sides of bodies within 1,500 of either play point and not present before RUN."""
import json, sys
for a in sys.argv[1:]:
    m, run, p0, p1 = a.split(':'); run = int(run)
    pts = [tuple(map(int, p0.split(','))), tuple(map(int, p1.split(',')))]
    old = set()
    print('==', m, run)
    for l in open('/workspace/pilot/sme_live/frames2/live_play_' + m + '.jsonl'):
        f = json.loads(l)
        if f['t'] < run - 2: continue
        if f['t'] < run:
            old |= {(e[0], e[3]) for e in f['E']}; continue
        if f['t'] > run + 6: break
        rows = [(k, e[0], e[1], e[2], e[3]) for k, e in enumerate(f['E'])
                if any(abs(e[1] - x) + abs(e[2] - y) < 1500 for x, y in pts) and e[3] != -1]
        print('  ', f['t'], rows)
