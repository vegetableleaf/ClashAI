"""Pinned-runtime check (fresh process, royale_runtime activated by royale_env import): children's card_id vs parent's."""
import os, sys, json, collections
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
from pipeline.royale_runtime import activate
stamp = activate()
from pipeline.royale_env import RoyaleSelfPlayEnv
import royalesim
out = {'runtime_stamp': stamp, 'royalesim_file': royalesim.__file__}
for card in ('Witch', 'DarkWitch', 'FirespiritHut', 'Tombstone', 'GoblinHut', 'BarbarianHut', 'Graveyard', 'SkeletonBalloon', 'GoblinDrill', 'GoblinGiant', 'GoblinCage'):
    env = RoyaleSelfPlayEnv(feature_version=4, tail_cap=2000)
    d1 = [card, 'Knight', 'Skeletons', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Tornado']
    d0 = ['Skeletons', 'Knight', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Tornado', 'Arrows']
    seed = next(s for s in range(200) if env.reset(d0, d1, seed=s) is not None and card in env.deal[1][:4])
    pos = (3500, 6500) if card == 'Graveyard' else (3500, 8500) if card == 'GoblinDrill' else (6500, 22500)
    t = env.tick; a = None
    while not (a and a.get('accepted')):
        a = env.act(1, 0, *pos); t += 10; env.advance_to(t)
    rows = collections.Counter(); seen = set()
    for tick in range(t, 1500, 5):
        for e in env.advance_to(tick)['entities']:
            if e['side'] == 1 and e['entity_id'] not in seen and e['card_id'] >= 0:
                seen.add(e['entity_id']); rows[(e['name'], e['card_id'], e['max_hp'], e.get('status_flags'))] += 1
    out[card] = dict(own_card_id=env.ids[card], bodies=[list(k) + [v] for k, v in rows.items()])
    print(card, env.ids[card], dict(rows))
json.dump(out, open(r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L73\spawners\sim_pinned_ids.json', 'w'), indent=1, default=str)
