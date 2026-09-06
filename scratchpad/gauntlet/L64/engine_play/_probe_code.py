import sys, random
sys.path.insert(0, r"C:\Users\benpe\ClashBot")
from pipeline import engine_play as ep
ee = ep._load_engine_env(); pool = ee.load_pool()
entry = pool[random.Random(0).sample(range(len(pool)), len(pool))[1]]
env = ep.RawEngineEnv(port=37031, pool=pool, decision_ticks=10, seed=0)
st = env.reset(entry); me = st["players"][env.side]
names = ep.engine_deck_names(env.final_decks[env.side]); print(names, "hand", me["hand_deck_indices"], "el", me["elixir_exact"])
cost = {"Xbow":6,"IceWizard":3,"Skeletons":1,"Log":2,"Rocket":6,"Tornado":3,"Knight@evolution":3,"Tesla@evolution":4}
hand = sorted(me["hand_deck_indices"], key=lambda i: -cost[names[i]])
X, Y = ep.cell_to_engine(1530, env._mirror)
for di in hand:
    r = env.eng.act(side=env.side, deck_index=di, x=X, y=Y)
    el = env.eng.observe()["players"][env.side]["elixir_exact"]
    print(names[di], cost[names[di]], "->", {k: r.get(k) for k in ("accepted","result_code","placement_valid","placement_reason","reason")}, "elixir now", el)
# card not in hand
di = [i for i in range(8) if i not in me["hand_deck_indices"]][0]
r = env.eng.act(side=env.side, deck_index=di, x=X, y=Y); print("not in hand", names[di], {k: r.get(k) for k in ("accepted","result_code","placement_valid","placement_reason")})
# enemy half placement of a troop
r = env.eng.act(side=env.side, deck_index=me["hand_deck_indices"][0], x=9000, y=(6000 if env._mirror else 26000)); print("enemy half", {k: r.get(k) for k in ("accepted","result_code","placement_valid","placement_reason")})
env.eng.close()
