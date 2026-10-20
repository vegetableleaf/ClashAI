"""Classify each J7 first divergence (j7diag dumps): (A) one-hit phase offset (the tower hp series agree again within the
tolerance inside 60 ticks, or live / SIM differ by one step that the other side repeats), (B) downstream of an earlier troop
divergence near the tower (a body near the tower whose hp or presence differs >= 30% / 1 tile before the tower diverges),
(C) neither (candidate engine law)."""
import json, glob, sys, math
from collections import Counter
D = sys.argv[1]
cls = Counter(); out = []
for f in sorted(glob.glob(D + '/*.json')):
    d = json.load(open(f)); j = d['j7']; fd = j.get('first_div')
    if not fd or 'diag' not in j:
        continue
    k = fd['towers'][0]; rows = j['diag']
    tol = max(300, 0.1 * max(r['live_hp'].get(k, 0) for r in rows[:1]) or 300)
    # tower agreement again within 60 ticks after the first divergence?
    after = [r for r in rows if fd['tick'] <= r['t'] <= fd['tick'] + 60 and k in r['live_hp'] and k in r['sim_hp']]
    rejoin = any(abs(r['live_hp'][k] - r['sim_hp'][k]) <= 0.5 * tol for r in after[1:])
    # earlier troop divergence: bodies near the tower in the 300 ticks before
    first_troop = None
    for r in rows:
        if r['t'] >= fd['tick']:
            break
        L = [b for b in r['live_near'] if b[1] != 2]; S = r['sim_near']
        def match(b, pool):
            c = [s for s in pool if s[1] == b[1] and math.hypot(s[2] - b[2], s[3] - b[3]) <= 1000]
            return min(c, key=lambda s: math.hypot(s[2] - b[2], s[3] - b[3])) if c else None
        bad = []
        for b in L:
            s = match(b, S)
            if s is None or abs(s[4] - b[4]) > 0.3 * max(b[4], s[4], 1):
                bad.append(('L', b, s))
        for s in S:
            if match(s, L) is None:
                bad.append(('S', s, None))
        if bad:
            first_troop = (r['t'], bad[:3]); break
    lead = fd['tick'] - first_troop[0] if first_troop else None
    c = 'A_rejoins' if rejoin else ('B_troops_first' if lead and lead >= 20 else 'C_tower_only')
    cls[c] += 1
    out.append((Path := f.split('/')[-1][:-5], d['side'], fd['tick'], k, fd['live'][k], fd['sim'][k], c, lead, first_troop and first_troop[1][:1]))
print(dict(cls))
for o in out:
    print(o)
