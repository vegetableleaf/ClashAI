"""S1b probe: what a mid-match RoyaleSim Battle exposes besides save() (sizes and timings of each accessor)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline.royale_runtime import activate  # noqa: E402
activate()
from pipeline.e1_eval import ICEBOW_ENGINE_DECK  # noqa: E402
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402

env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", hero_abilities=True)
env.reset(list(ICEBOW_ENGINE_DECK), list(ICEBOW_ENGINE_DECK), 5)
for t, (side, i, x, y) in enumerate([(0, 3, 9000, 25000), (1, 7, 9000, 25000), (0, 2, 6000, 20000), (1, 1, 12000, 22000)]):
    env._advance_to(200 + 60 * t)
    print(env.eng.act(side=side, deck_index=i, x=x, y=y))
env._advance_to(700)
b = env.core._battle
for name in ("save", "state_json", "debug_units", "hide_states", "charge_states", "unit_types_digest"):
    f = getattr(b, name)
    t = time.perf_counter()
    for _ in range(20):
        out = f()
    dt = (time.perf_counter() - t) / 20 * 1000
    print(name, round(dt, 3), "ms", len(out) if hasattr(out, "__len__") else out, str(out)[:300].replace("\n", " "))
sv = json.loads(b.save())
print("save keys", list(sv), "ents keys", list(sv["ents"]), {k: len(v) if hasattr(v, "__len__") else v for k, v in sv.items() if k != "ents"})
