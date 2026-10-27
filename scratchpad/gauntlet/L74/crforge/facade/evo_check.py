"""F1c item 3: evolved plays on crforge. public_plays form (from PlayerState.evo at the act) vs the bodies the play
put down (crforge row names: _EV1 = evolved per body_map). Per census match (icebow: Knight / Tesla evolution slots;
the opponent's evo slots too), random affordable plays; every accepted play's form is compared with the bodies of
that card that appear within 40 ticks of its run (new uids, unit type ending _EV1 or not).
usage: ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I evo_check.py --n 20
"""
import argparse
import json
import os
import random
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/f1/cb", "/workspace/f1"]
import accept_f1 as A  # noqa: E402
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=20)
a = ap.parse_args()
pairs = A.census()
agree, disagree, evo_plays, samples = 0, 0, 0, []
for i in range(a.n):
    pair = pairs[i % len(pairs)]
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=6)   # public_plays need fv >= 3
    assert env.engine_delay_ticks == 20, "ROYALE_ENGINE=crforge"
    env.reset([n + A.SFX[f] for n, f in zip(pair[0], pair[1])], [n + A.SFX[f] for n, f in zip(pair[2], pair[3])], seed=i)
    rng, seen = random.Random(i), set(e.uid for e in env.core.state().entities)
    while not env.done:
        side = rng.randrange(2)
        k = len(env.public_plays)
        env.act(side, rng.randrange(8), rng.randrange(2000, 16000), 6000 if side == 0 else 26000)
        if len(env.public_plays) == k:
            env.advance_to(env.tick + 10)
            continue
        p = env.public_plays[-1]
        env.advance_to(p["tick"] + 40)             # public plays are dated at the run (+20): bodies are down by then
        st, types = env.core.state(), env.core.unit_types()
        cid = env.ids[p["card"]]
        fresh = [e for e in st.entities if e.uid not in seen]
        new = [types[e.unit_type] for e in fresh if e.card_id == cid and e.team == side]
        seen |= {e.uid for e in st.entities}
        if os.environ.get("EVO_DEBUG"):
            print(p, env.tick, len(st.entities), len(seen), [(types[e.unit_type], e.card_id, e.team) for e in fresh][:6], cid, flush=True)
        if not new:
            continue                               # a spell, or nothing landed of this card
        body_evo = any(t.endswith("_EV1") or "_EV1_" in t for t in new)
        evo_plays += p["form"] == 1
        if (p["form"] == 1) == body_evo:
            agree += 1
        else:
            disagree += 1
            samples.append(dict(i=i, card=p["card"], form=p["form"], bodies=sorted(set(new))))
print(json.dumps(dict(matches=a.n, plays_checked=agree + disagree, agree=agree, disagree=disagree,
                      evolved_plays=evo_plays, samples=samples[:8])))
