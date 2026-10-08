"""Q4b: RoyaleSim Rocket damage on crown towers (pinned runtime 20261006, local). Side 0 casts one Rocket at an enemy
princess / king tower (several aim offsets); reports tower HP drop, the catalog expectation and the ratio to a troop hit.
Run: ROYALE_RUNTIME=20261006 icebow/.venv/Scripts/python.exe sim_rocket_probe.py"""
import os, sys, json
os.environ.setdefault('ROYALE_RUNTIME', '20261006'); os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, "C:/Users/benpe/ClashBot")
import gym_stub  # noqa: F401
from pipeline.royale_env import RoyaleSelfPlayEnv
D0 = ['Rocket', 'Tesla', 'IceWizard', 'Tornado', 'Knight', 'Skeletons', 'Log', 'Xbow']
D1 = ['Golem', 'Musketeer', 'Wizard', 'Arrows', 'Fireball', 'Zap', 'Valkyrie', 'Minions']


def towers(o):
    return {(t['side'], t['type'] if 'type' in t else t.get('kind'), t['x'], t['y']): t['hp'] for t in o.get('towers', o.get('episode', {}).get('crown_towers', []))} if isinstance(o.get('towers'), list) and o['towers'] and isinstance(o['towers'][0], dict) else o.get('towers')


def run(seed, aim, golem=False):
    env = RoyaleSelfPlayEnv(feature_version=4, tail_cap=2000)
    o = env.reset(D0, D1, seed=seed)
    if 'Rocket' not in env.deal[0][:4] or (golem and 'Golem' not in env.deal[1][:4]): return None
    t = env.tick
    if golem:
        while not env.act(1, env.decks[1].index('Golem'), aim[0], aim[1] + 1500).get('accepted'): t += 10; env.advance_to(t)
        t += 60; env.advance_to(t)
    before = env.advance_to(t)
    while True:
        r = env.act(0, env.decks[0].index('Rocket'), aim[0], aim[1])
        if r.get('accepted'): break
        t += 5; before = env.advance_to(t)
    snap = [before]
    for k in range(1, 30): snap.append(env.advance_to(t + 10 * k))
    return dict(t=t, before=before, snaps=snap)


def ct(o): return {(t['side'], t['type'], t['x']): t['hp'] for t in o['episode']['crown_towers']}


def main():
    AIMS = {'princess centre': (3500, 25500), 'princess front +2t': (3500, 23500), 'princess front +2.9t': (3500, 22600),
            'princess front +3.2t': (3500, 22300), 'king centre': (9000, 29000), 'between L-princess/king': (6250, 27250)}
    out = {}
    for name, aim in AIMS.items():
        for seed in range(60):
            r = run(seed, aim)
            if r is None: continue
            b = ct(r['before']); a = ct(r['snaps'][-1])
            drops = {f"{k[0]}{k[1][0]}{int(k[2])}": b[k] - a[k] for k in b if b[k] != a[k]}
            land = next((i * 10 for i, s in enumerate(r['snaps']) if ct(s) != b), None)
            out[name] = dict(seed=seed, aim=aim, drops=drops, landing_ticks_after_accept=land); print(name, out[name], flush=True); break
    for seed in range(80):     # troop reference: Rocket on a Golem in front of the princess
        r = run(seed, (3500, 22000), golem=True)
        if r is None: continue
        g0 = [e for e in r['before']['entities'] if e.get('name') == 'Golem' and e['side'] == 1]
        g1 = [e for e in r['snaps'][-1]['entities'] if e.get('name') == 'Golem' and e['side'] == 1]
        out['golem'] = dict(seed=seed, hp_before=[e['hp'] for e in g0], hp_after=[e['hp'] for e in g1]); print('golem', out['golem']); break
    json.dump(out, open(os.path.join(HERE, 'sim_rocket_probe.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
