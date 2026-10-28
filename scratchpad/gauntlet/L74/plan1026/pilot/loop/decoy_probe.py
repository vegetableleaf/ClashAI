"""LOOP-INT step 3 (GB-DECOY in the SIM): what production's crforge SIM path shows a policy during an evolved Goblin
Barrel cast. Plays evo Goblin Barrels from side 0 through RoyaleSelfPlayEnv (the e1_eval / rl_royale env) and prints,
per tick in flight, the raw state's spells / projectiles and production's projectile objects (projectile_observation
.sim_objects -> objects(source='sim')), i.e. what tokens_from_objects turns into the model's projectile rows.

usage (pod, run.sh's env): python decoy_probe.py [--casts 3] [--seed 5]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[5])]

ap = argparse.ArgumentParser()
ap.add_argument("--casts", type=int, default=3)
ap.add_argument("--seed", type=int, default=5)
a = ap.parse_args()
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from pipeline import projectile_observation as PO  # noqa: E402

d0 = ["GoblinBarrel@evolution", "BarbLog", "Fireball", "Minions", "Rascals", "MovingCannon", "Mortar", "Knight"]
d1 = ["BarbLog", "Fireball", "Minions", "Rascals", "MovingCannon", "Mortar", "Knight", "Goblins"]
env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", hero_abilities=False, ability_features="base")
env.reset(d0, d1, a.seed)
print("deck0", env.decks[0], "forms", getattr(env, "form_fallbacks", None))
bi = [i for i, n in enumerate(env.decks[0]) if "GoblinBarrel" in str(n)][0]
casts, tick, log = 0, int(env.tick), []
while casts < a.casts and tick < 5000:
    r = env.act(side=0, deck_index=bi, x=3500, y=26000)    # Blue's barrel at Red's left princess tower
    ok = bool(r.get("ok", r.get("accepted", False))) if isinstance(r, dict) else bool(r)
    if ok:
        casts += 1
        js = json.loads(str(env.core._cf.state()))
        print("cast", casts, "tick", tick, r, "evo", [x.get("evo") for x in js.get("players", js.get("sides", []))] if isinstance(js, dict) else None, list(js)[:12])
        for t in range(tick + 1, tick + 45):
            raw = env.advance_to(t)
            st = env.core.state() if hasattr(env.core, "state") else None
            sp = [dict(card=s.card_id, team=s.team, motion=s.motion, x=s.x, y=s.y, ax=s.aim_x, ay=s.aim_y)
                  for s in (st.spells if st is not None else [])]
            pr = [dict(firer=p.firer_card_id, team=p.team, x=p.x, y=p.y) for p in (st.projectiles if st is not None else [])]
            obj = PO.objects(PO.sim_objects(st, env.names, 1000.0) if st is not None else {}, source="sim")
            barrels = [o for o in obj["projectiles"] if "barrel" in json.dumps(o).lower()]
            if sp or barrels or any(p["team"] == 0 for p in pr):
                print(" t", t, "spells", sp, "shots", [dict(p, aim=(q.aim_x, q.aim_y)) for p, q in zip(pr, st.projectiles) if p["team"] == 0][:4],
                      "\n    objects.projectiles", obj["projectiles"])
        tick = int(env.tick)
    else:                                                    # cycle: any other card in hand at our own back
        for j in range(8):
            if j != bi and env.act(side=0, deck_index=j, x=9000, y=3000).get("accepted"):
                break
        tick += 10
        env.advance_to(tick)
print("DONE casts", casts)
