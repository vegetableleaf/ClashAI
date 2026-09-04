import sys, os, importlib
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad"); sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L48"); sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim import scenarios as sc
from clashrl.sim.drill_env import DrillEnv, doctrine_policy
from clashrl.sim import doctrine as D
ov = sys.argv[1]
if ov != "none": importlib.import_module(ov).install()
cfg = Config.load("data/bench/c2r_run.yaml"); sc.load_all()
s = sc.get("skeletons_stop_the_wall_breakers"); env = DrillEnv(cfg, s, seed=5)
print("scenario:", {k: v for k, v in vars(s).items() if k in ("elixir", "our_elixir", "enemy_elixir", "hand", "our_hand", "verdict", "pass", "fail", "timeout", "spawn", "enemy", "enemies")})
for rep in range(2):
    obs = env.reset(); done = False; t = 0
    print(f"rep {rep} start elixir {float(env.eng.elixir[0]):.1f} hand {env._hand_ids()}")
    while not done:
        a = doctrine_policy(obs, env)
        if a[0] == 1:
            print(f"  t={env.eng.t if hasattr(env.eng,'t') else t:>6} elixir {float(env.eng.elixir[0]):.1f} PLAY {a} hand {env._hand_ids()} enemies {[ (u.spec.base, round(float(u.y),2)) for u in D._enemies(env)]}")
        obs, r, done, info = env.step(a); t += 1
        v = (info or {}).get("verdict")
        if v is not None: print(f"  verdict {v} at step {t} elixir {float(env.eng.elixir[0]):.1f}"); break
