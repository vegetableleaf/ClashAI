"""Fresh-process smoke for the selected runtime: activate, one scripted RoyaleSim match through royale_env, unit_type check."""
import json, sys, collections
sys.path.insert(0, r"C:\Users\benpe\ClashBot")
from pipeline.royale_runtime import activate
stamp = activate()
print("RUNTIME", stamp["pins"], stamp.get("runtime_id"))
from pipeline import royale_env as RE
import royalesim, royalegym
print("royalesim", royalesim.__file__, royalesim.Battle.provenance(), "gym", royalegym.__file__)
D0 = ["Witch", "Skeletons", "Giant", "Archer", "Fireball", "Zap", "Musketeer", "Knight"]
D1 = ["Tombstone", "Hog Rider".replace(" ", ""), "Valkyrie", "Arrows", "Minions", "Cannon", "Wizard", "Bomber"]
env = RE.RoyaleSelfPlayEnv()
raw = env.reset(D0, D1, seed=3)
ut = env.core._engine.unit_types() if hasattr(env.core, "_engine") else None
print("raw keys", sorted(raw), "tick", raw["tick"])
st = env.core.state()
plays = []
def play(side, name):
    di = env.decks[side].index(name)
    r = env.act(side, di, 9000, 9000 if side == 0 else 23000)
    plays.append((env.tick, side, name, r["accepted"], r["result_code"])); return r
# deal is seeded; hand may not hold the card -> wait until it does, bounded
seen = collections.Counter(); skel_ut = {}
for step in range(1, 400):
    env.advance_to(env.tick + 10)
    for side, prio in ((0, ["Witch", "Skeletons", "Giant", "Musketeer", "Knight", "Archer"]), (1, ["Tombstone", "Valkyrie", "Wizard", "Cannon", "Minions"])):
        hand = [env.names[c] for c in env.core.state().players[side].hand if c in env.names]
        for n in prio:
            if n in hand and play(side, n)["accepted"]: break
    st = env.core.state()
    for e in st.entities:
        if e.card_id in env.names:
            seen[(env.names[e.card_id], e.unit_type)] += 1
    if env.done: break
types_ = env._engine_unit_types() if hasattr(env, "_engine_unit_types") else None
print("plays accepted", sum(p[3] for p in plays), "of", len(plays), "final tick", env.tick, "done", env.done)
vocab = json.loads(env.core._battle.unit_types_json())
print("vocab size", len(vocab), "digest", env.core._battle.unit_types_digest())
byname = collections.defaultdict(set)
for (card, u), n in seen.items(): byname[card].add(vocab[u] if u >= 0 else None)
for k, v in sorted(byname.items()): print(" card", k, "-> unit types", sorted(map(str, v)))
st = env.core.state()
print("crowns", [int(p.crowns) for p in st.players], "entity fields", type(st.entities[0]).__struct_fields__[-3:] if st.entities else None)
assert byname["Witch"] == {"Witch"} or "Witch" in byname["Witch"], byname["Witch"]
assert "Skeleton" in byname["Witch"] or "Skeleton" in set().union(*byname.values())
# Witch's skeletons: entities produced by card Witch whose unit_type is Skeleton
print("WITCH_SKELETONS", "Skeleton" in byname["Witch"], "Skeletons-card units", sorted(map(str, byname["Skeletons"])))
print("OK")
