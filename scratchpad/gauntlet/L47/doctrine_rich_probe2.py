import sys, collections
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
import numpy as np, torch, random
from rollout_search import play_match
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
from clashrl.sim.drill_env import doctrine_policy
from clashrl.sim import doctrine
cfg = Config.load(); env = SimMatchEnv(cfg, seed=12345); env.domain_rand.enabled = False; env.domain_rand.resample(); env.opponent_provider = None; env.scenario = None
print("deck_keys", list(env.deck_keys)); shown = 0
C = collections.Counter()
class D:
    def act(self, i):
        global shown
        a = doctrine_policy(None, env); e = float(env.eng.elixir[0]); hand = list(env._hand_ids())
        bowid = [c for c in range(len(env.deck_keys)) if env.deck_keys[c] == "x_bow"][0]
        onfield = any(u.team == 0 and u.spec.base == "x_bow" and u.hp > 0 for u in env.eng.units)
        if e >= 9:
            C["rich"] += 1; C["bow_in_hand"] += bowid in hand; C["bow_on_field"] += onfield
            if bowid in hand and shown < 4:
                pri = doctrine.doctrine_cards(env) or {}
                en = [u for u in doctrine._enemies(env) if u.y > 0.42 and u.spec.kind != "spell"]
                print(f"t={env.eng.t:.0f} e={e:.1f} hand={[env.deck_keys[c] for c in hand]} pri={{ {', '.join(env.deck_keys[k]+':'+str(v) for k,v in pri.items())} }} committed={[u.spec.base for u in en]} act={a} onfield={onfield}"); shown += 1
        C["dec"] += 1; C["bow_on_field_all"] += onfield
        return tuple(int(x) for x in a), False
s = D()
for m in range(6): play_match(env, s, 5000000 + m)
print(dict(C))
