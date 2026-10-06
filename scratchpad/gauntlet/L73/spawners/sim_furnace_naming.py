"""Old-runtime Furnace naming counterfactual (CPU). The pre-2026-10-05 RoyaleSim runtime (used for R1e's RL) named Furnace
children 'FireSpirits' 215 HP (L71/spawners/sim_identity_probe.json); the pinned new runtime names them 'FirespiritHut'.
Run one Furnace in the new runtime, then feed PublicObserver(source='sim') twice: as recorded, and with the children
renamed to 'FireSpirits' (= old runtime). Count inferred opponent plays and model tokens under fv4. Writes sim_furnace_naming.json."""
import os, sys, json, copy, collections
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
ROOT = r'C:\Users\benpe\ClashBot'
sys.path.insert(0, ROOT)
from pipeline.royale_env import RoyaleSelfPlayEnv
from pipeline.public_observation import PublicObserver
from pipeline import vocab
inv = {v: k for k, v in vocab._ID.items()}
deck1 = ['FirespiritHut', 'Knight', 'Skeletons', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Tornado']
deck0 = ['Skeletons', 'Knight', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Tornado', 'Arrows']
env = RoyaleSelfPlayEnv(feature_version=4, tail_cap=2000)
seed = next(s for s in range(200) if env.reset(deck0, deck1, seed=s) is not None and 'FirespiritHut' in env.deal[1][:4])
t = env.tick; acc = None
while not (acc and acc.get('accepted')):
    acc = env.act(1, 0, 9000, 26500); t += 10; env.advance_to(t)
frames = [env.advance_to(tick) for tick in range(t, 1990, 5)]
out = {}
for label in ('new_runtime_names', 'old_runtime_names'):
    o = PublicObserver(0, schedule=env.elixir_regen_schedule); toks = collections.Counter(); bodies = set()
    for f in frames:
        f = copy.deepcopy(f)
        for e in f['entities']:
            if label == 'old_runtime_names' and e['name'] == 'FirespiritHut' and e['max_hp'] < 500:
                e['name'] = 'FireSpirits'
            if e['side'] == 1 and e['card_id'] >= 0 and e['hp'] > 0 and e['entity_id'] not in bodies:
                bodies.add(e['entity_id']); toks[inv.get(vocab.engine_unit_id(e['name'], float(e['max_hp'])))] += 1
        o.update(f, source='sim')
    out[label] = dict(plays=[(p['tick'], p['card']) for p in o.plays], fv4_body_classes=dict(toks), final_estimate=o.estimate_at(frames[-1]['tick']))
    print(label, out[label])
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sim_furnace_naming.json'), 'w'), indent=1)
