"""Where does a slowed Knight's buff live in Battle.save()? Usage: python savebuf.py <wheel dir>"""
import json
import sys
sys.path.insert(0, sys.argv[1])
import royalesim as sim  # noqa: E402

K = 18000
b = sim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps('client160402017_20261006')})
ids = {dict(zip(sim.CATALOGUE_FIELDS, r))['name']: i for i, r in enumerate(json.loads(b.catalogue_json()))}
deck = [ids[c] for c in ['IceWizard', 'Knight', 'Giant', 'Musketeer', 'Tesla', 'Log', 'Tornado', 'Rocket']]
b.reset(1, [deck, deck], 0, 200, [10000, 10000], [[4824, 0, 0], [4824, 3052, 3052]],
        [(1, ids['Knight'], 9 * K, 5 * K, -1), (0, ids['IceWizard'], 9 * K, int(9.2 * K), -1)],
        levels=[[11] * 8, [11] * 8], tower_levels=[11, 11])
b.step([], 45)
sv = json.loads(b.save())
E = sv['ents']
kn = [i for i in range(len(E['alive'])) if E['team'][i] == 'Red' and E['kind'][i] == 'Troop'][0]
print('knight idx', kn, 'attack_ms', E['attack_ms'][kn])
print('ent keys with buff:', [k for k in E if 'buff' in k.lower()])
print('type of ents.buffs:', type(E['buffs']).__name__, 'len', len(E['buffs']), 'n ents', len(E['alive']))
for k in E:
    if 'buff' in k.lower():
        print(k, json.dumps(E[k])[:600])
for k in sv:
    s = json.dumps(sv[k])
    if 'buff' in k.lower() or '"id": ' in s and k != 'ents':
        print('TOP', k, s[:400])
