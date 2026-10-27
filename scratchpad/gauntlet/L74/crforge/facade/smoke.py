"""F1 smoke: RoyaleSelfPlayEnv with its core swapped for CrforgeCore; a few plays; raw() -> from_engine."""
import os, sys, json
os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/f1/cb"]
from pipeline.royale_env import RoyaleSelfPlayEnv
from pipeline.crforge_core import CrforgeCore
from pipeline import obs_contract as oc

env = RoyaleSelfPlayEnv(forms_mode="deck", feature_version=6)
env.core = CrforgeCore()
ice = ["Knight@evolution", "IceWizard@hero", "Tesla@evolution", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"]
opp = ["Witch", "Golem", "Tombstone", "DarkWitch", "GoblinGiant", "FirespiritHut", "GoblinBarrel", "Graveyard"]
raw = env.reset(ice, opp, seed=3)
st = env.core.state()
print("tick", st.tick, "towers", [(e.team, e.kind, e.tower_slot, e.x, e.y, e.hp) for e in st.entities if e.kind >= 2])
print("hands", [p.hand for p in st.players], [p.elixir_milli for p in st.players])
print("deal", env.deal)
n = 0
for t in range(100, 3000, 30):
    for side in (0, 1):
        for i in range(8):
            r = env.act(side, i, 9000 if side == 0 else 9000, 10000 if side == 0 else 22000)
            if r["accepted"]:
                n += 1
                break
    env.advance_to(t)
    if env.done:
        break
raw = env.raw()
print("tick", env.tick, "plays", n, "ents", len(raw["entities"]), sorted({e["name"] for e in raw["entities"]}))
print("effects", raw["effects"][:3], "proj", raw.get("projectiles", [])[:2])
deck = oc.load_deck("icebow")
bs = oc.from_engine(raw, 0, deck, feature_version=6, unmapped=(um := set()))
tok, mask, sc = oc.to_tokens(bs)
print("tokens", int(mask.sum()), "unmapped", um)
print(json.dumps(env.core.unmapped())[:1500])
print(env.public_plays[:3])
