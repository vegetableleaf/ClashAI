"""SIM evolution-form probe (CPU): side 1 plays an evolved spawner card whenever it can; record every side-1 body of that
card: name, max_hp, status_flags, entity_form, fv4 class and PublicObserver plays. Writes sim_evo_probe.json."""
import os, sys, json, collections
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
ROOT = r'C:\Users\benpe\ClashBot'
sys.path.insert(0, ROOT)
from pipeline.royale_env import RoyaleSelfPlayEnv
from pipeline.public_observation import PublicObserver
from pipeline.obs_contract import entity_form
from pipeline.body_identity import resolve
from pipeline import vocab
inv = {v: k for k, v in vocab._ID.items()}
fill = ['Knight', 'Skeletons', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Arrows']
deck0 = ['Skeletons', 'Knight', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Tornado', 'Arrows']
res = {}
for card, pos in (('Witch', (3500, 26500)), ('FirespiritHut', (9000, 26500)), ('Tombstone', (9000, 26500))):
    sfx = '@hero' if card == 'Tombstone' else '@evolution'
    env = RoyaleSelfPlayEnv(feature_version=4, forms_mode='deck', tail_cap=3600)
    env.reset(deck0, [card + sfx] + fill, seed=3)
    o = PublicObserver(0, schedule=env.elixir_regen_schedule)
    bodies = {}; issued = []
    for tick in range(env.tick, 3500, 10):
        obs = env.advance_to(tick)
        r = env.act(1, 0, *pos)
        if r.get('accepted'):
            issued.append(tick)
        elif len(issued) < 6:
            for k in range(1, 8):   # cycle the other cards from the back so the evolution counter advances
                if env.act(1, k, 9000, 30500).get('accepted'):
                    break
        o.update(obs, source='sim')
        for e in obs['entities']:
            if e['side'] == 1 and e['name'] == card and e['entity_id'] not in bodies:
                f = entity_form(e)
                bodies[e['entity_id']] = (e['max_hp'], e.get('status_flags'), f, inv.get(vocab.engine_unit_id(e['name'], float(e['max_hp']))),
                                          inv.get(resolve(e['name'], float(e['max_hp']), f).cls))
    c = collections.Counter(bodies.values())
    res[card + sfx] = dict(issued=issued, bodies=[list(k) + [v] for k, v in c.items()],
                           observer_plays=[(p['tick'], p['card'], p['form']) for p in o.plays if p['card'] == vocab.engine_key(card)],
                           loaded_forms=env.loaded_forms, fallbacks=env.form_fallbacks)
    print(card + sfx, res[card + sfx])
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sim_evo_probe.json'), 'w'), indent=1)
