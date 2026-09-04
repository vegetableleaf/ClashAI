"""How often does the engine's crowns() (= dead enemy towers) undercount a real-CR 3-crown? Counts match
ends where a KING is dead while >=1 of its princesses stands. argv: leg(doctrine|policy) ckpt matches"""
import sys; sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
import torch, numpy as np, random
from rollout_search import play_match, Searcher, load_net
from clashrl.config import Config; from clashrl.sim.env import SimMatchEnv
from clashrl.sim.drill_env import doctrine_policy
leg, ckpt, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
torch.set_num_threads(1); torch.manual_seed(0); np.random.seed(0); random.seed(0)
cfg = Config.load(); env = SimMatchEnv(cfg, seed=12345); env.domain_rand.enabled = False; env.domain_rand.resample(); env.opponent_provider = None
if not hasattr(env, "scenario"): env.scenario = None
class Doc:
    def act(self, i): return tuple(int(x) for x in doctrine_policy(None, env)), False
s = Doc() if leg == "doctrine" else Searcher(env, load_net(ckpt, env, torch.device("cpu")), torch.device("cpu"), 1e-6, 0, 4, 1.0, 0.25)
under = [0, 0]; kings = [0, 0]; cd_engine = []; cd_real = []
for m in range(n):
    r = play_match(env, s, 5000000 + m)
    real = [0, 0]
    for team in (0, 1):                       # crowns TAKEN by team = enemy towers dead; real CR: king dead -> 3
        tw = env.eng.towers[1 - team]; dead = sum(1 for t in tw if not t.alive)
        if not tw[2].alive:
            kings[team] += 1; real[team] = 3
            if dead < 3: under[team] += 1
        else: real[team] = dead
    cd_engine.append(env.eng.crowns(0) - env.eng.crowns(1)); cd_real.append(real[0] - real[1])
print(f"[{leg}] n={n} our king kills {kings[0]} (undercounted {under[0]})  their king kills {kings[1]} (undercounted {under[1]})")
print(f"  crown_delta engine {np.mean(cd_engine):+.3f}  real-CR {np.mean(cd_real):+.3f}")
