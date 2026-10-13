"""Pod-only: eight complete legal-deploy games through the production adapter."""
import argparse
import json
from pathlib import Path
import os
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    from pipeline.royale_runtime import activate
    stamp = activate()
    assert stamp['runtime_id'] == '20261012-linux'
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline.public_observation import public_frame
    from pipeline.own_ability import catalog
    from pipeline.royale_heroiw import selected_card_data
    own = ['Tornado', 'Tesla@evolution', 'IceWizard', 'Xbow', 'Rocket', 'Knight@evolution', 'Log', 'Skeletons']
    opp = ['Giant', 'Knight', 'Archer', 'Zap', 'Fireball', 'Musketeer', 'Minions', 'Log']
    spec = next(f for f in selected_card_data()['hero_forms'] if f['form_of'] == 'IceWizard')
    assert spec['elixir'] == 3 and spec['ability']['mana_cost'] == 2
    assert spec['ability']['max_charges'] == 1 and spec['ability']['cooldown_ms'] is None
    assert catalog()['ice-wizard', 2]['mana_cost'] == 2
    receipts = []
    normal = os.environ.get('ROYALE_HEROIW_FORM', 'hero') == 'normal'
    for seed in range(8):
        # Pin the scenario cards in the opening hand while retaining the production seeded deal.
        # Only the setup order changes; every card deployment and press remains a legal command.
        decks = [list(own), list(opp)]
        for side, name in ((0, 'IceWizard'), (1, 'Giant')):
            order = list(range(8))
            random.Random(f'deal:{seed}:{side}').shuffle(order)
            old_index = decks[side].index(name)
            decks[side][old_index], decks[side][order[0]] = decks[side][order[0]], decks[side][old_index]
        iw, giant = decks[0].index('IceWizard'), decks[1].index('Giant')
        env = RoyaleSelfPlayEnv(forms_mode='deck', hero_abilities=True, ability_policy='v2', feature_version=5)
        env.reset(*decks, seed)
        if normal:   # ROYALE_HEROIW_FORM=normal (IWDIAG N1): no hero, no button, no cube -- verify form + a full game
            assert env.loaded_forms[0][iw] != 2, 'ROYALE_HEROIW_FORM=normal must load the non-hero Ice Wizard'
            assert env.core._battle.card_table() == 'cards-160402017-20261006.1'
            deployed = False
            while not env.done:
                if not deployed and env.deck_ids[0][iw] in env.core.state().players[0].hand:
                    deployed = env.act(0, iw, 3500, 13500)['accepted']
                env.advance_to(env.tick+1)
            assert deployed and env.terminated, f'seed {seed}: normal IW deployed={deployed}, terminated={env.terminated}'
            receipts.append(dict(seed=seed, form='normal', deployed=deployed, final_tick=env.tick, outcome=env.outcome(0)))
            a.out.write_text(json.dumps(dict(runtime=stamp, games=receipts), indent=2)+'\n')
            print(f'SMOKE seed {seed}: normal-form Ice Wizard deployed and completed game verified', flush=True)
            continue
        assert env.loaded_forms[0][iw] == 2 and not any(n == 'IceWizard' for _, n, _ in env.form_fallbacks)
        assert env.core._battle.card_table() == 'cards-160402017-20261006.1'
        spawned = pressed = cube = False
        deploy_cost = ability_cost = None
        button_used = None
        # Cycle legally to the hero and a durable opponent; never inject state/debug-spawn.
        while not env.done:
            st = env.core.state()
            if not spawned:
                hand = st.players[0].hand
                choices = sorted((i for i, c in enumerate(env.deck_ids[0]) if c in hand),
                                 key=lambda i: (i != iw, env.costs(0)[i]))
                for i in choices:
                    before = env.core.state().players[0].elixir_milli
                    result = env.act(0, i, 3500, 13500 if i == iw else 4500)
                    if result['accepted']:
                        if i == iw:
                            deploy_cost = before-env.core.state().players[0].elixir_milli
                            assert deploy_cost == 3000
                            spawned = True
                        break
            if spawned and not pressed and env.tick % 20 == 10:
                hand = env.core.state().players[1].hand
                choices = sorted((i for i, c in enumerate(env.deck_ids[1]) if c in hand),
                                 key=lambda i: (i != giant, env.costs(1)[i]))
                for i in choices:
                    if env.act(1, i, 3500, 18500)['accepted']:
                        break
            raw = env.raw()
            bodies = [e for e in raw['entities'] if e.get('unit_name') in ('IceWizardHero', 'IceWizard_hero') and e['side'] == 0]
            if bodies:
                assert bodies[0]['public_card_id'] == 203000023
            commands = [c for c in env.ability_commands(0) if env.names[c[1]] == 'IceWizard']
            if not pressed and commands:
                assert bodies, 'button must belong to a visible hero body'
                button_used = commands[0][0]
                before = env.core.state().players[0].elixir_milli
                env.queue_abilities(0, commands, delay=0)
                ability_cost = before-env.core.state().players[0].elixir_milli
                assert ability_cost == 2000
                assert env.ability_presses[0]['IceWizard'] == 1
                assert not env.eng.act(side=0, ability_button=button_used)['accepted'], 'one charge per deploy'
                pressed = True
            if any(e.get('unit_name') == 'IceWizardHero_IceCube' and e['side'] == 0 for e in raw['entities']):
                public = public_frame(raw, source='sim')
                cubes = [e for e in raw['entities'] if e.get('unit_name') == 'IceWizardHero_IceCube' and e['side'] == 0]
                for c in cubes:
                    assert any(e['card_id'] == 203000023 and e['address'] == (0, c['entity_id']) for e in public['entities'])
                cube = True
            env.advance_to(env.tick+1)
        assert spawned and pressed and cube, f'seed {seed}: hero={spawned}, press={pressed}, cube={cube}'
        assert env.terminated, 'must reach engine game-over, not just a time cap'
        receipts.append(dict(seed=seed, hero=spawned, press=pressed, cube=cube, deploy_milli=deploy_cost,
                             press_milli=ability_cost, final_tick=env.tick, outcome=env.outcome(0)))
        a.out.write_text(json.dumps(dict(runtime=stamp, games=receipts), indent=2)+'\n')
        print(f'SMOKE seed {seed}: hero, press cost, cube and completed game verified', flush=True)


if __name__ == '__main__':
    main()
