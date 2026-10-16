"""Summarise logset_all.jsonl: confusion of live vs SIM hits on paired ground bodies + geometry of the mismatches."""
import json, sys, statistics
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import engine
eng = engine()
import royalesim as sim
cards = {c['name']: c for c in json.loads(sim.EMBEDDED_CARDS_160402017_JSON)['cards']}
rows = [json.loads(l) for l in open(sys.argv[1])]
mode = sys.argv[2] if len(sys.argv) > 2 else 'all'
HID = ('opp_spell_seen', 'opp_ability_unobserved')
def clean(r):
    if mode == 'all': return True
    from capture import F
    skip = HID if mode == 'core' else ()
    return not any(k.startswith(F.CLEAN_BLOCKERS) and not k.startswith(skip) for k in r['flags'])
conf = Counter(); mis = []
for r in rows:
    n = r['name']
    if n is None or n not in eng.ids or eng.cat[eng.ids[n]]['flying'] or not r['paired'] or not clean(r):
        continue
    k = (r['live_hit'] is not None, r['sim_hit'] is not None)
    conf[k] += 1
    # geometry at the hit (or tL+10 if none): lateral offset from the log line, along-roll distance from the tap
    t_ref = r['live_hit'] or r['sim_hit'] or r['tL']
    lt = min(r['live_traj'], key=lambda q: abs(q[0]-t_ref)) if r['live_traj'] else None
    st = min(r['sim_traj'], key=lambda q: abs(q[0]-t_ref)) if r['sim_traj'] else None
    rad = cards.get(n, {}).get('collision_radius_milli')
    geo = lambda q: (abs(q[1]-r['log'][0]), (q[2]-r['log'][1])*r['fwd']) if q else None
    r.update(k=k, rad=rad, lgeo=geo(lt), sgeo=geo(st), dlh=(r['live_hit']-r['tL']) if r['live_hit'] else None, dsh=(r['sim_hit']-r['tL']) if r['sim_hit'] else None)
    if k[0] != k[1]:
        mis.append(r)
print('mode', mode, 'confusion (live_hit, sim_hit):', dict(conf))
both = [r for r in rows if r.get('k') == (True, True)]
print('both-hit timing sim-live ticks median', statistics.median(r['sim_hit']-r['live_hit'] for r in both), Counter(r['sim_hit']-r['live_hit'] for r in both).most_common(8))
print('by name, mismatches:', Counter((r['name'], 'live_only' if r['k'][0] else 'sim_only') for r in mis).most_common(30))
for r in sorted(mis, key=lambda r: (r['k'], r['name'])):
    print(f"{r['k']} {r['name']:13s} rad {r['rad']} live dx/along {r['lgeo']} sim {r['sgeo']} hit dt live {r['dlh']} sim {r['dsh']} {r['match'][-6:]}@{r['t0']} tL {r['tL']}")
