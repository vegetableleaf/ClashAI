"""Why does the doctrine hold at elixir>=9? Instrument doctrine_cards / doctrine_cells at rich decisions."""
import sys, collections
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
import numpy as np, torch, random
from rollout_search import play_match
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
from clashrl.sim.drill_env import doctrine_policy
from clashrl.sim import doctrine
torch.set_num_threads(1); random.seed(0); np.random.seed(0)
cfg = Config.load(); env = SimMatchEnv(cfg, seed=12345); env.domain_rand.enabled = False; env.domain_rand.resample(); env.opponent_provider = None; env.scenario = None
C = collections.Counter(); BOW = collections.Counter()
class D:
    def act(self, i):
        a = doctrine_policy(None, env); e = float(env.eng.elixir[0])
        if e >= 9:
            pri = doctrine.doctrine_cards(env) or {}; hand = list(env._hand_ids())
            bow = next((c for c in hand if env.deck_keys[c] == "x_bow"), None)
            C["rich"] += 1; C["play"] += a[0] == 1; C["nominated_any"] += bool(pri); C["bow_in_hand"] += bow is not None
            if bow is not None:
                C["bow_nominated"] += bow in pri
                cells = doctrine.doctrine_cells(env, bow); C["bow_cells"] += bool(cells)
                if bow in pri and not cells: C["bow_nominated_no_cell"] += 1
            en = [u for u in doctrine._enemies(env) if u.y > 0.42 and u.spec.kind != "spell"]
            C["committed_enemies>0"] += len(en) > 0
            if pri: BOW[env.deck_keys[max(pri, key=pri.get)]] += 1
        return tuple(int(x) for x in a), False
s = D()
for m in range(12): play_match(env, s, 5000000 + m)
print(dict(C)); print("top nominated card at rich decisions:", dict(BOW))
