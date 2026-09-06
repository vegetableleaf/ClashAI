import sys, json, random, time
sys.path.insert(0, r"C:\Users\benpe\ClashBot")
from pipeline import engine_play as ep
from pipeline.obs_contract import load_deck
deck = load_deck("icebow")
model, _ = ep.load_model(__import__("pathlib").Path("icebow/data/pipeline/s1_icebow_s0.pt"), "cpu")
ee = ep._load_engine_env()
pool = ee.load_pool()
order = random.Random(0).sample(range(len(pool)), len(pool))
entry = pool[order[1]]
print("tag", entry["tag"], "icebow_side", entry["icebow_side"], "expected", entry.get("result"), entry.get("final_crowns"))
env = ep.RawEngineEnv(port=37031, pool=pool, decision_ticks=10, seed=0)
state = env.reset(entry)
print("RAW KEYS", sorted(state.keys()))
print("episode keys", sorted(state["episode"].keys()))
print("player0 keys", sorted(state["players"][0].keys()))
print("player me", {k: v for k, v in state["players"][env.side].items() if k != "hand"}, "hand0", state["players"][env.side]["hand"][0])
print("tower0", state["episode"]["crown_towers"][0])
# advance without playing, print tower hp every 200 ticks; print entities at first tick with any
rng = random.Random(1)
done_plays=[]
last_print=0
ent_shown=False
while not env.terminated and env.tick < 7200:
    if not ent_shown and state.get("entities"):
        e = state["entities"][0]; print("ENTITY", e); ent_shown=True
    if env.tick - last_print >= 200:
        last_print = env.tick
        hp = {f"{t['side']}{t.get('type')[0]}{(t.get('lane') or '')[:1]}": t["hp"] for t in state["episode"]["crown_towers"]}
        print(env.tick, round(env.tick*0.05,1), hp, "ghost_ok", env.ghost_ok, "n_ent", len(state.get("entities",[])), "crowns", state["episode"].get("crowns"))
    env._advance_to(env.tick+10)
    state = env.eng.observe()
print("END", env.tick, env.eng.last_episode)
env.eng.close()
