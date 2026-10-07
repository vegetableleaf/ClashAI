"""Targeted SIM probe: does the pinned runtime ever produce a Phoenix egg or Skeleton King summoned skeletons?
Prints every distinct side-1 body (name, card_id, max_hp, status_flags) including EMPTY_CARD ones."""
import os, sys, collections
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
from pipeline.royale_runtime import activate
activate()
from pipeline.royale_env import RoyaleSelfPlayEnv, EntityKind
for card in ('Phoenix', 'SkeletonKing'):
    env = RoyaleSelfPlayEnv(feature_version=5, forms_mode='deck', hero_abilities=True, ability_policy='v2', tail_cap=3000)
    env.reset(['Fireball', 'Arrows', 'Musketeer', 'Skeletons', 'Knight', 'Valkyrie', 'MiniPekka', 'Archer'],
              [card, 'Knight', 'Skeletons', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Arrows'], seed=5)
    seen = collections.Counter(); presses = 0
    for tick in range(env.tick, 3000, 5):
        env.advance_to(tick)
        if env.done: break
        if tick % 10 == 0:
            env.act(1, 0, 3500, 20000) or None
            for k in range(1, 8):
                if env.act(1, k, 3500, 20000).get('accepted'): break
            st = env.core.state()
            mine = [e for e in st.entities if e.team == 1 and e.card_id == env.ids[card]]
            for e in mine[:1]:
                for k in range(0, 8):
                    if env.act(0, k, int(e.x / 1), int(min(e.y, 14000))).get('accepted'): break
        for e in env.core.state().entities:
            if e.team == 1 and e.kind not in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER):
                seen[(env.names.get(e.card_id, e.card_id), e.max_hp, e.status_flags, int(e.kind))] += 1
    print(card, 'ability presses', dict(env.ability_presses[1]))
    for k, v in sorted(seen.items(), key=str): print('   ', k, v)
