import json
_C = json.load(open('C:/Users/benpe/ClashBot/research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json'))['cards']
NAME, COST = {}, {}
for c in _C:
    for k in ('card_id', 'evolution_form_id', 'hero_form_id'):
        if c.get(k) is not None: NAME[int(c[k])] = c['display_name']; COST[int(c[k])] = c['elixir']
NAME[203000023] = 'IceWizard'; COST[203000023] = 3
UV = json.load(open('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/unit_values.json'))['value_per_unit']
def uval(cid): return UV.get(NAME.get(int(cid), ''), 0.5)
