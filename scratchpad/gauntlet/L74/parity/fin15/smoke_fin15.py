"""fin15-linux smoke (setup_fin15.sh): activate() the pinned runtime, check the Hero IW adapter is on, run a 600-tick battle, and
check the W8 laws are the shipped arms. Run with ROYALE_RUNTIME=fin15-linux and /workspace/venvf15's python, PYTHONPATH = the repo."""
import json

from pipeline.royale_runtime import activate

s = activate()
print(s['runtime_id'], s['pins'], s['card_table'])
import royalesim  # noqa: E402  (after activate: the pinned runtime)
from pipeline import royale_heroiw as h  # noqa: E402
assert h.ENABLED, 'royale_heroiw is off under fin15-linux'
b = royalesim.Battle(None, [[0, 1, 2], [0, 2, 1]], calibration_overrides={'cards.CARD_TABLE': json.dumps(h.CARD_TABLE)})
ids = {r['name']: i for i, r in enumerate(dict(zip(royalesim.CATALOGUE_FIELDS, x)) for x in json.loads(b.catalogue_json()))}
deck = [ids[n] for n in sorted(h.ICEBOW)]
b.reset(1, [deck, deck], 0, 0, [6000, 6000], None, [], levels=[[16] * 8, [16] * 8], tower_levels=[16, 16])
assert json.loads(b.save())['mana_unit'] == 10000, 'match.MANA_REGEN_STEP is not the floor arm'
b.step([], 600)
st = json.loads(b.state_json())
print('smoke: tick', st['tick'], 'elixir_milli', [p['elixir_milli'] for p in st['players']])
assert st['tick'] == 600
print('SMOKE_FIN15_OK')
