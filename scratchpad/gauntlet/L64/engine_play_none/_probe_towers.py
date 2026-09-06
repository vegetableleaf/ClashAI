import sys, json
sys.path.insert(0, '.')
from pipeline.engine_play import RawEngineEnv, _load_engine_env
ee = _load_engine_env(); pool = ee.load_pool()
tag = sys.argv[1]
entry = next(e for e in pool if e['tag'] == tag)
env = RawEngineEnv(port=37031, pool=pool, decision_ticks=10, seed=0)
try:
    st = env.reset(entry)
    print('level', env.level, 'side', env.side, 'decks', str(env.final_decks)[:300])
    while not (env.terminated or env.tick >= env.tail_cap):
        env._advance_to(min(env.tick + 200, env.tail_cap)); st = env.eng.observe()
        tw = [(t['side'], t.get('type'), t.get('lane'), t['hp'], t['max_hp']) for t in st['episode'].get('crown_towers', [])]
        units = [(u.get('side'), u.get('name') or u.get('card') or u.get('kind')) for u in st.get('units', [])][:8]
        print(env.tick, round(env.tick/20,1), 'towers', tw, 'units', units, 'ghosts', env._gi, 'term', env.terminated)
    last = env.eng.last_episode or {}
    print('last_episode keys', list(last.keys())[:12], 'crowns', last.get('crowns'), 'winner', last.get('winner'), 'reason', last.get('termination_reason'))
finally:
    env.close()
