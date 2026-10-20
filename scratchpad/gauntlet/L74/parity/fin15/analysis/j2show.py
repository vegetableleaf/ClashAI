"""Per-tick motion of Tornado victims (j2diag dumps): live vs paired SIM body, distance to the cast point and step length."""
import json, sys, math
d = json.load(open(sys.argv[1]))
c = d['cast']; print('cast', c)
for b in d['j2']:
    print('  j2', b['victim'], 'd0', b['d0'], 'pull live/sim', b.get('pull_live'), b.get('pull_sim'), 'agree', b['agree'])
rows = d['rows']
ids = sorted({b[0] for r in rows for b in r['live']})
for lid in ids:
    seq = []
    for r in rows:
        lb = next((b for b in r['live'] if b[0] == lid), None)
        if lb is None:
            continue
        sid = lb[1]
        sb = next((b for b in r['sim'] if b[0] == sid), None) if sid else None
        seq.append((r['t'], lb, sb))
    if not seq or not any(s for _, _, s in seq):
        continue
    name = next((s[1] for _, _, s in seq if s), None)
    if sys.argv[2] not in str(name):
        continue
    print('body', lid, '->', seq[0][1][1], name)
    prev = None
    for t, lb, sb in seq:
        dl = math.hypot(lb[3] - c['x'], lb[4] - c['y'])
        ds = math.hypot(sb[2] - c['x'], sb[3] - c['y']) if sb else None
        st = ''
        if prev:
            pt, pl, ps = prev
            n = t - pt
            stl = math.hypot(lb[3] - pl[3], lb[4] - pl[4]) / max(n, 1)
            sts = math.hypot(sb[2] - ps[2], sb[3] - ps[3]) / max(n, 1) if sb and ps else float('nan')
            st = f'step/tick live {stl:5.0f} sim {sts:5.0f}'
        print(f'   t{t} live ({lb[3]},{lb[4]}) d{dl:5.0f} hp{lb[5]} | sim ' + (f'({sb[2]},{sb[3]}) d{ds:5.0f} hp{sb[4]} dep{sb[5]}' if sb else '-') + '  ' + st)
        prev = (t, lb, sb)
