"""Per body (j2diag dumps): median radial approach per tick toward the cast point, live vs SIM, over cast+4..cast+20."""
import json, sys, glob, math, statistics as S
for f in sorted(glob.glob(sys.argv[1] + '/*.json')):
    d = json.load(open(f)); c = d['cast']; rows = d['rows']
    out = []
    for lid in sorted({b[0] for r in rows for b in r['live']}):
        seq = []
        for r in rows:
            lb = next((b for b in r['live'] if b[0] == lid), None)
            if lb is None or not lb[1]:
                continue
            sb = next((b for b in r['sim'] if b[0] == lb[1]), None)
            if sb is None:
                continue
            seq.append((r['t'], math.hypot(lb[3] - c['x'], lb[4] - c['y']), math.hypot(sb[2] - c['x'], sb[3] - c['y']), sb[1]))
        w = [x for x in seq if c['tick'] + 4 <= x[0] <= c['tick'] + 20]
        if len(w) < 4:
            continue
        rl = [(a[1] - b[1]) / (b[0] - a[0]) for a, b in zip(w, w[1:]) if b[0] > a[0]]
        rs = [(a[2] - b[2]) / (b[0] - a[0]) for a, b in zip(w, w[1:]) if b[0] > a[0]]
        out.append((w[0][3], round(w[0][1]), round(S.median(rl)), round(S.median(rs))))
    print(f.split('/')[-1].split('\\')[-1], c['tick'], [o for o in out if sys.argv[2] in str(o[0])])
