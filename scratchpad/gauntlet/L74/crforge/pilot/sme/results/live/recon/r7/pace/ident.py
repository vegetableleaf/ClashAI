import json, sys
def load(p): return {r['seed']: r for r in map(json.loads, open(p))}
P, A = load(sys.argv[1]), load(sys.argv[2])
keys = ['outcome', 'plays_attempted', 'plays_accepted', 'end_tick', 'decisions', 'crowns_for', 'tower_hp_diff']
same = sum(all(P[s][k] == A[s][k] for k in keys) for s in P)
print('rr_p1 (pod code, no key) vs rr_a (patched code, no key): identical on', same, 'of', len(P), 'matches', keys)
same2 = sum(P[s]['own_reasons'] == A[s]['own_reasons'] for s in P)
print('own play lists identical (tick, land, card, accepted, reason, elixir):', same2, 'of', len(P))
