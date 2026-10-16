"""Residual Log hit mismatches (logset_fix.jsonl) by geometry: position cascade vs lateral box edge vs neither."""
import json, sys
from collections import Counter
sys.path.insert(0, 'scratchpad/gauntlet/L74/parity/diag1016')
from capture import engine
eng = engine()
import royalesim as sim
cards = {c['name']: c for c in json.loads(sim.EMBEDDED_CARDS_160402017_JSON)['cards']}
R = [json.loads(l) for l in open(sys.argv[1])]
C = Counter(); A = Counter(); ex = {}
for r in R:
    n = r['name']
    if n not in eng.ids or eng.cat[eng.ids[n]]['flying'] or not r['paired']: continue
    t_ref = r['live_hit'] or r['sim_hit'] or r['tL'] + 10
    q = min(r['live_traj'], key=lambda q: abs(q[0]-t_ref)) if r['live_traj'] else None
    s = min(r['sim_traj'], key=lambda q: abs(q[0]-t_ref)) if r['sim_traj'] else None
    if not q or not s: continue
    rad = cards.get(n, {}).get('collision_radius_milli') or 500
    m = abs(q[1]-r['log'][0]) - 1950 - rad
    gap = ((q[1]-s[1])**2 + (q[2]-s[2])**2) ** .5
    k = (r['live_hit'] is not None, r['sim_hit'] is not None)
    if k[0] == k[1]:
        A['near edge' if abs(m) < 300 else 'not near edge'] += 1; continue
    c = 'live/SIM body > 250 apart near the hit (position cascade)' if gap > 250 else ('within 300 of the lateral edge' if abs(m) < 300 else 'same place, not at the edge')
    C[c] += 1; ex.setdefault(c, []).append(f"{n} {r['match'][-6:]}@{r['tL']}")
print('mismatches:', dict(C)); print('agreeing bodies:', dict(A))
for c, v in ex.items(): print(c, v[:12])
