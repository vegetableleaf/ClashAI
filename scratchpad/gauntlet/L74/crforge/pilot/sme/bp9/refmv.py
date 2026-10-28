"""refmv.py TRACEDIR M:T:UID ... -- A2c-9R: for a goal-change event, the unit's and its reference's probe events at t-1 and t
(disp / prop / push / replan), in tick order, from AimRun traces."""
import glob, json, sys
td = sys.argv[1]
for a in sys.argv[2:]:
    m, t, u = a.split(':'); t = int(t); u = int(u)
    f = glob.glob(td + '/live_play_' + m + '.o.jsonl')[0]
    rows = {}
    for l in open(f):
        o = json.loads(l)
        if t - 2 <= o['t'] <= t: rows[o['t']] = o
        if o['t'] > t: break
    ref = next((c[6] for c in rows[t]['C'] if c[0] == u), None)
    print('==', m, t, 'unit', u, 'ref', ref)
    for tk in sorted(rows):
        o = rows[tk]
        for c in o['C']:
            if c[0] in (u, ref): print('  ', tk, 'C', c)
        for e in o['ev']:
            if e[0] in ('disp', 'prop', 'replan', 'rpx') and e[1] in (u, ref) or e[0] == 'push' and e[1] in (u, ref):
                print('  ', tk, e[:20])
