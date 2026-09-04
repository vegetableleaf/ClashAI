"""L48: does the ROLLOUT-SEARCH teacher pass the drill suite? Same instrument as L46 drills.sh
(c2r_run.yaml, seed 5, 25 reps), columns: doctrine / policy greedy / search (H12 N1 K4 cells3).
Episodes stop at the verdict (the pass rate is recorded at its natural moment; play-out only
matters for training length). argv: ckpt shard nshards out.json"""
import sys, json, time
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, "src")
import numpy as np, torch
torch.set_num_threads(1)
from rollout_search import load_net, Searcher
from clashrl.config import Config
from clashrl.sim import scenarios as sc
from clashrl.sim.drill_env import DrillEnv, doctrine_policy
from clashrl.cli import _drill_policy_from_checkpoint

ckpt, shard, nsh, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
cfg = Config.load("data/bench/c2r_run.yaml")
sc.load_all()
names = sc.names()[shard::nsh]
gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
dev = torch.device("cpu")
greedy = _drill_policy_from_checkpoint(ckpt, "cpu", spell_min_value=0.0)

def run(scenario, policy_factory, reps=25, seed=5):
    env = DrillEnv(cfg, scenario, seed=seed)
    passed = 0; t0 = time.perf_counter()
    for _ in range(reps):
        obs = env.reset(); pol = policy_factory(env); step = 0; done = False; v = None
        while not done:
            a = pol(obs, env, step); step += 1
            obs, r, done, info = env.step(a)
            v = (info or {}).get("verdict")
            if v is not None:
                break
        passed += (v == "pass")
    return passed / reps, time.perf_counter() - t0

def f_doc(env):
    return lambda obs, env, i: doctrine_policy(obs, env)
def f_pol(env):
    return lambda obs, env, i: greedy(obs, env)
def f_search(env):
    net = load_net(ckpt, env, dev)
    s = Searcher(env, net, dev, 12.0, 1, 4, 1.0, gate_tau, cells=3)
    def p(obs, env, i):
        a, _ = s.act(i)
        return tuple(int(x) for x in a)
    return p

res = {}
for n in names:
    s = sc.get(n) if hasattr(sc, "get") else next(x for x in sc.all() if x.name == n)
    row = {}
    for lab, fac in (("doctrine", f_doc), ("policy", f_pol), ("search", f_search)):
        pr, wall = run(s, fac)
        row[lab] = pr; row[lab + "_s"] = round(wall, 1)
    res[n] = row
    print(f"{n:34s} doctrine {row['doctrine']*100:4.0f}%  policy {row['policy']*100:4.0f}%  search {row['search']*100:4.0f}%   ({row['search_s']}s)", flush=True)
    json.dump(res, open(out, "w"), indent=1)
print("SHARD_DONE")
