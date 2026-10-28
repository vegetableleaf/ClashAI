"""reneither.py GOAL6_ROWS TRACEDIR [OUTS] -- A2c-9R: re-decide bp5 goal-census events with the unit's real step: avoidance blend and
push from its 'prop' event (the census's pure step ignored both). alt0 = step toward the held route's next node (no rebuild).
Outcome at tf (first frame >= t): crforge / alt0 (a recorded body of the side within 3 units of the sim point + (alt - cr)) / neither."""
import glob, json, sys
sys.path.insert(0, '/workspace/pilot/bp9')
from stepsim import step
rows_p, td = sys.argv[1], sys.argv[2]
outs = set((sys.argv[3] if len(sys.argv) > 3 else 'neither,alt0').split(','))
W = 36
rows = [json.loads(l) for l in open(rows_p)]
rows = [x for x in rows if x['clean'] and x['pre'] and x['out'] in outs]
cache = {}


def trace(m):
    if m not in cache:
        d = {}
        for l in open(glob.glob(td + '/live_play_' + m + '.o.jsonl')[0]):
            o = json.loads(l); d[o['t']] = o
        fr = {}
        for l in open('/workspace/pilot/sme_live/frames2/live_play_' + m + '.jsonl'):
            f = json.loads(l); fr[f['t']] = [(e[0], e[1], e[2]) for e in f['E']]
        cache.clear(); cache[m] = (d, fr)
    return cache[m]


for x in sorted(rows, key=lambda r: (r['m'], r['t'])):
    d, fr = trace(x['m'])
    o = d[x['t']]
    ev = [e for e in o['ev'] if e[1] == x['id']]
    rp = next((e for e in ev if e[0] == 'replan'), None)
    pr = next((e for e in ev if e[0] == 'prop'), None)
    ds = next((e for e in ev if e[0] == 'disp'), None)
    if not (rp and pr and ds):
        print(x['m'], x['t'], x['id'], 'missing', bool(rp), bool(pr), bool(ds)); continue
    sx, sy, ax, ay, bud = ds[2:7]
    blend, push = pr[7], (pr[4], pr[5])
    hn = rp[7]
    hx, hy = (hn % W) * 500 + 250, (hn // W) * 500 + 250
    cr = step(sx, sy, ax, ay, bud, blend)
    al = step(sx, sy, hx, hy, bud, blend)
    ok = (cr[0] + push[0], cr[1] + push[1]) == (pr[12], pr[13])
    dv = (al[0] - cr[0], al[1] - cr[1])
    tf = min(t for t in fr if t >= x['t'])
    simp = next((c for c in d[tf]['C'] if c[0] == x['id']), None) if tf in d else None
    side = simp[2] if simp else None
    if simp is None: out = 'gone'
    elif (side, simp[3], simp[4]) in fr[tf]: out = 'crforge'
    elif dv != (0, 0) and any(s == side and abs(px - simp[3] - dv[0]) <= 3 and abs(py - simp[4] - dv[1]) <= 3 for s, px, py in fr[tf]): out = 'alt0'
    else: out = 'neither'
    near = sorted(((abs(px - simp[3]) + abs(py - simp[4]), (px - simp[3], py - simp[4])) for s, px, py in fr[tf] if simp and s == side))[:1]
    print(x['m'], x['t'], x['id'], x['name'], 'old', x['out'], 'new', out, 'tf', tf, 'blend', blend, 'push', push, 'stepchk', ok,
          'dv', dv, 'nearest rec-sim', near, 'acq_age', x['acq_age'], 'dheld-R', round(x['dheld'] - x['R']), 'ref_before', x['ref_before'], x['ref_name'])
