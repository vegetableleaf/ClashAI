"""SIM (RoyaleSim) identity probe for every spawner family: what name/card_id/max_hp the sim gives parent and children,
what fv4 (legacy) / fv5 (body_identity) map them to, and what PublicObserver(source='sim') charges as opponent plays.
CPU only (CUDA hidden), read-only on pipeline. Side 1 plays the family card ONCE; side 0 plays nothing (Mother Witch: side 0
drops Skeletons on her so cursed bodies die)."""
import os, sys, json, collections
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'; os.environ['OMP_NUM_THREADS'] = '2'
ROOT = r'C:\Users\benpe\ClashBot'; sys.path.insert(0, ROOT)
from pipeline.royale_env import RoyaleSelfPlayEnv
from pipeline import vocab
from pipeline.body_identity import resolve
from pipeline.obs_contract import entity_form
from pipeline.public_observation import PublicObserver
from pipeline.opp_elixir_count import card_cost
inv = {v: k for k, v in vocab._ID.items()}
FILL = ['Knight', 'Skeletons', 'Log', 'Rocket', 'Tesla', 'IceWizard', 'Tornado', 'Arrows', 'Zap', 'Fireball', 'Musketeer']
# (card, x, y) in pool units, side 1 (top half, y>16000)
FAMS = [('Witch', 3500, 26500), ('DarkWitch', 3500, 26500), ('FirespiritHut', 6500, 22500), ('WitchMother', 3500, 19500),
        ('Tombstone', 6500, 22500), ('GoblinHut', 6500, 22500), ('BarbarianHut', 6500, 22500), ('Graveyard', 3500, 6500),
        ('GoblinDrill', 3500, 8500), ('SkeletonBalloon', 3500, 26500), ('GoblinGiant', 3500, 26500), ('ElixirGolem', 3500, 26500),
        ('Golem', 3500, 28500), ('LavaHound', 3500, 28500), ('GoblinCage', 6500, 22500), ('Phoenix', 3500, 26500),
        ('SuspiciousBush', 3500, 22500), ('SkeletonKing', 3500, 26500), ('Goblinstein', 3500, 26500), ('GoblinBarrel', 3500, 6500)]
probe = RoyaleSelfPlayEnv(feature_version=4)
have = set(probe.ids); probe.close() if hasattr(probe, 'close') else None
res = {}
for card, x, y in FAMS:
    if card not in have:
        res[card] = {'error': 'not in sim catalogue'}; print(card, 'NOT IN SIM'); continue
    fill = [c for c in FILL if c != card][:7]
    deck1 = [card] + fill; deck0 = (['Skeletons'] + [c for c in FILL if c != 'Skeletons'])[:8]
    env = RoyaleSelfPlayEnv(feature_version=4, tail_cap=2000)
    try:
        seed = next(s for s in range(200) if (env.reset(deck0, deck1, seed=s) is not None) and card in env.deal[1][:4])
        obs = env.raw(); obsv = PublicObserver(0, schedule=env.elixir_regen_schedule)
        t = env.tick; acc = None
        while t < 600 and not (acc and acc.get('accepted')):
            acc = env.act(1, 0, x, y); t += 10; obs = env.advance_to(t)
        if not acc.get('accepted'):
            res[card] = {'error': 'not accepted', 'act': str(acc)}; print(card, 'not accepted', acc); continue
        t_dep = t; mw_done = False
        bodies = {}; per_tick = []
        for tick in range(t, min(t + 1300, 1990), 5):
            obs = env.advance_to(tick)
            if card == 'WitchMother' and not mw_done and tick > t_dep + 60:
                mw = [e for e in obs['entities'] if e['side'] == 1 and e['name'] == 'WitchMother']
                if mw:
                    r = env.act(0, 0, int(mw[0]['x']), int(max(mw[0]['y'] - 2500, 15000))); mw_done = bool(r.get('accepted'))
            obsv.update(obs, source='sim')
            cnt4 = collections.Counter(); cnt5 = collections.Counter()
            for e in obs['entities']:
                if e['side'] != 1 or e['card_id'] < 0 or e['hp'] <= 0: continue
                f = entity_form(e)
                c4 = vocab.engine_unit_id(e['name'], float(e['max_hp'])); r5 = resolve(e['name'], float(e['max_hp']), f)
                cnt4[inv.get(c4)] += 1; cnt5[inv.get(r5.cls)] += 1
                if e['entity_id'] not in bodies:
                    bodies[e['entity_id']] = dict(tick=tick, name=e['name'], card_id=e['card_id'], max_hp=e['max_hp'],
                        status_flags=e.get('status_flags'), form=f, fv4=inv.get(c4), fv5=inv.get(r5.cls), fv5_reason=r5.reason)
            per_tick.append((tick, dict(cnt4), dict(cnt5)))
        groups = collections.Counter((b['name'], b['max_hp'], b['fv4'], b['fv5'], b['fv5_reason']) for b in bodies.values())
        plays = [(p['tick'], p['card']) for p in obsv.plays]
        peak4 = max((sum(v for k, v in c.items() if k == vocab.engine_key(card) or k == vocab.engine_key(vocab.engine_key(card) or '')) for _, c, _ in per_tick), default=0)
        res[card] = dict(seed=seed, deploy_tick=t_dep, bodies=[dict(name=a, max_hp=b, fv4=c, fv5=d, fv5_reason=e, n=n) for (a, b, c, d, e), n in groups.items()],
                         observer_plays=plays, observer_charged=sum(card_cost(k) or 0 for _, k in plays),
                         true_cost=card_cost(vocab.engine_key(card)), max_tokens_fv4=max((c for _, c, _ in per_tick), key=lambda c: sum(c.values()), default={}))
        print(card, 'seed', seed, 'bodies', [(a, b, c, d, n) for (a, b, c, d, e), n in groups.items()], 'plays', plays)
    except StopIteration:
        res[card] = {'error': 'no seed with card in hand'}; print(card, 'no seed')
    finally:
        if hasattr(env, 'close'): env.close()
json.dump(res, open('sim_probe.json', 'w'), indent=1, default=str)
