"""L48: the DOCTRINE on the 29 drills, stock vs an override module, same instrument as search_drills.py
(DrillEnv seed 5, 25 reps, first verdict decides).  argv: override_module|none out.json  [env D4_* as in _d6.sh]"""
import sys, json, time, importlib
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L48"); sys.path.insert(0, "src")
import numpy as np, torch
from clashrl.config import Config
from clashrl.sim import scenarios as sc
from clashrl.sim.drill_env import DrillEnv, doctrine_policy
ov, out = sys.argv[1], sys.argv[2]
if ov != "none": importlib.import_module(ov).install()
import os
cfg = Config.load("data/bench/c2r_run.yaml"); sc.load_all(); names = [n for n in sc.names() if os.environ.get("ONLY","") in n]

def run(scenario, reps=25, seed=5):
    env = DrillEnv(cfg, scenario, seed=seed); passed = 0
    for _ in range(reps):
        obs = env.reset(); done = False; v = None
        while not done:
            obs, r, done, info = env.step(doctrine_policy(obs, env))
            v = (info or {}).get("verdict")
            if v is not None: break
        passed += (v == "pass")
    return passed / reps

res = {}
for n in names:
    s = sc.get(n) if hasattr(sc, "get") else next(x for x in sc.all() if x.name == n)
    res[n] = run(s); print(f"{n:34s} {ov:14s} {res[n]*100:4.0f}%", flush=True)
json.dump(res, open(out, "w"), indent=1)
print(f"[{ov}] mean {100*np.mean(list(res.values())):.1f}%  zeros {sum(v==0 for v in res.values())}")
print("DONE")
