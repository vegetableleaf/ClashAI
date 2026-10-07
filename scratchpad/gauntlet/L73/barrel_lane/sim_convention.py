"""SIM (RoyaleSim, the RL training engine of R1e) Goblin Barrel convention probe. CPU, a few hundred ticks.

Each side casts one Goblin Barrel at an enemy princess tower; we record the SIM public projectile rows
(sim_objects aim = target), the goblins' spawn points, and the observer-side model tokens
(objects(source='sim') -> tokens_from_objects), and check target lane == landing lane in the own frame.
"""
import json, math, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))  # gym_stub unused with the Royale venv

from pipeline.royale_env import RoyaleSelfPlayEnv
from pipeline.projectile_observation import objects, tokens_from_objects

DECK = ["GoblinBarrel", "Knight", "Cannon", "IceSpirits", "Log", "Skeletons", "Musketeer", "Valkyrie"]
CAST = {1: (3500, 6500), 0: (14500, 25500)}     # side -> target (an enemy princess tower)
GID = {'goblin-barrel': 42}


def own(x, y, side):
    x, y = x / 18000, y / 32000
    return (x, 1 - y) if side == 0 else (1 - x, y)


def run(seed):
    env = RoyaleSelfPlayEnv(feature_version=4)
    obs = env.reset(DECK, DECK, seed)
    hands = {s: [h['name'] for h in next(p for p in obs['players'] if p['side'] == s)['hand']] for s in (0, 1)}
    if not all('GoblinBarrel' in hands[s] for s in (0, 1)):
        return None
    t = env.tick
    while min(next(p for p in obs['players'] if p['side'] == s)['elixir_exact'] for s in (0, 1)) < 3:
        t += 1; obs = env.advance_to(t)
    for s in (0, 1):
        r = env.act(s, DECK.index('GoblinBarrel'), *CAST[s])
        assert r['accepted'], r
    seen_ids, rows, landing = set(e['entity_id'] for e in obs['entities']), [], {0: [], 1: []}
    tok = None
    for _ in range(200):
        t += 1; obs = env.advance_to(t)
        for p in obs['projectiles']:
            if 'Barrel' in p['name']:
                rows.append(dict(tick=t, side=p['side'], x=p['x'], y=p['y'], tx=p['target_x'], ty=p['target_y']))
                if tok is None:   # the production token path, both observer sides, on the first barrel frame
                    tok = {o: tokens_from_objects(objects(obs, source='sim'), o, GID)['projectiles'] for o in (0, 1)}
        for e in obs['entities']:
            if e['entity_id'] not in seen_ids and 'Goblin' in e['name']:
                seen_ids.add(e['entity_id'])
                landing[e['side']].append(dict(tick=t, x=e['x'], y=e['y'], name=e['name']))
        if t % 10 == 0 or not rows:
            pass
        if all(len(landing[s]) >= 3 for s in (0, 1)):
            break
    # model-frame tokens at the first tick a barrel of each side is visible, from the OTHER side's view
    out = dict(seed=seed, casts={})
    for s in (0, 1):
        r = [x for x in rows if x['side'] == s]
        if not r:
            out['casts'][s] = 'no projectile rows'
            continue
        g = landing[s][:3]
        cx, cy = sum(e['x'] for e in g)/len(g), sum(e['y'] for e in g)/len(g)
        obs_side = 1 - s
        tx, ty = own(r[0]['tx'], r[0]['ty'], obs_side)
        lx, ly = own(cx, cy, obs_side)
        out['casts'][s] = dict(cast=CAST[s], first_row=r[0], last_row=r[-1], flight_ticks=r[-1]['tick']-r[0]['tick']+1,
                               goblins=g, centroid=(cx, cy), err_tiles=math.hypot(cx-r[0]['tx'], cy-r[0]['ty'])/1000,
                               observer_side=obs_side, target_own=(tx, ty), landing_own=(lx, ly),
                               lane_agree=(tx < .5) == (lx < .5),
                               production_token_row=[v for v in tok[obs_side].tolist() if v[0] == 42 and v[1] == 1])
    # the actual token path on one mid-flight SIM frame for observer side 1 and 0
    return out


def main():
    res = []
    for seed in range(60):
        r = run(seed)
        if r:
            res.append(r)
        if len(res) >= 3:
            break
    # token-path check on a frame with both barrels in flight
    env = RoyaleSelfPlayEnv(feature_version=4)
    print(json.dumps(res, indent=1, default=str))
    json.dump(res, open(os.path.join(os.path.dirname(__file__), 'sim_results.json'), 'w'), indent=1, default=str)


if __name__ == '__main__':
    main()
