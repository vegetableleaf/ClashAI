"""Does the SIM Mega Knight dash, and what does the engine say while it does? python probe_mk.py (PARITY_SIM_PATH set)"""
import json, os, sys
sys.path.insert(0, os.environ['PARITY_SIM_PATH'])
import royalesim as sim
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))
from pipeline.sim_unit_state import extract
K = 18000
b = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps('client160402017_20261006')})
ids = {dict(zip(sim.CATALOGUE_FIELDS, r))['name']: i for i, r in enumerate(json.loads(b.catalogue_json()))}
for dist in (3.0, 4.0, 5.0, 6.0):
    d = [ids['MegaKnight']]
    b.reset(1, [d, d], 0, 200, [10000, 10000], [[4824, 3052, 3052]] * 2,
            [(0, ids['MegaKnight'], int(9 * K), int(8 * K), -1), (1, ids['Skeletons'], int(9 * K), int((8 + dist) * K), -1)],
            levels=[[11]] * 2, tower_levels=[11, 11])
    seen = set()
    for t in range(120):
        b.step([], 1)
        sv = json.loads(b.save())
        E = sv['ents']
        for i, a in enumerate(E['alive']):
            if a and E['card'][i] == ids['MegaKnight']:
                seen.add((E['jumping'][i], E['dash_state'][i], next(u['state'] for u in extract(b)['units'] if u['name'] == 'MegaKnight')))
    print(dist, sorted(seen, key=str))
