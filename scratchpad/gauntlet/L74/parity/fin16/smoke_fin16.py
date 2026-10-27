"""fin16-linux smoke (setup_fin16.sh): activate() the pinned runtime, check the Hero IW adapter is on, run a 600-tick battle, and
check the W8 laws are the shipped arms and the battle loads the 10-19 table. Run with ROYALE_RUNTIME=fin16-linux and /workspace/venvf16's python, PYTHONPATH = the repo."""
import json

from pipeline.royale_runtime import activate

s = activate()
print(s['runtime_id'], s['pins'], s['card_table'])
import royalesim  # noqa: E402  (after activate: the pinned runtime)
from pipeline import royale_heroiw as h  # noqa: E402
assert h.ENABLED, 'royale_heroiw is off under fin16-linux'
assert h.CARD_TABLE == 'client160402017_20261019', h.CARD_TABLE
assert h.selected_card_data() == json.loads(royalesim.EMBEDDED_CARDS_160402017_20261019_JSON) != json.loads(royalesim.EMBEDDED_CARDS_160402017_JSON)
b = royalesim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps(h.CARD_TABLE)})
assert b.card_table() == 'cards-160402017-20261019.1', b.card_table()   # the loaded table's own version
ids = {r['name']: i for i, r in enumerate(dict(zip(royalesim.CATALOGUE_FIELDS, x)) for x in json.loads(b.catalogue_json()))}
deck = [ids[n] for n in sorted(h.ICEBOW)]
b.reset(1, [deck, deck], 0, 0, [6000, 6000], None, [], levels=[[16] * 8, [16] * 8], tower_levels=[16, 16])
assert json.loads(b.save())['mana_unit'] == 10000, 'match.MANA_REGEN_STEP is not the floor arm'
b.step([], 600)
st = json.loads(b.state_json())
print('smoke: tick', st['tick'], 'elixir_milli', [p['elixir_milli'] for p in st['players']])
assert st['tick'] == 600
print('SMOKE_FIN16_OK')
