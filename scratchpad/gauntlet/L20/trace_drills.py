"""Step one episode of each aggro drill under the scripted policy and print the lock state per step."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "icebow", "src"))
from clashrl.config import Config
from clashrl.sim import aggro_drills
from clashrl.sim.drill_env import DrillEnv, scripted_policy
from clashrl.sim.engine import Tower, Unit

def nm(t):
    if t is None: return "-"
    if isinstance(t, Tower): return f"Tower(x{t.x:.2f},y{t.y:.2f})"
    return f"{t.spec.base}[{t.team}]"

for sc in aggro_drills.ALL:
    print("=" * 20, sc.name)
    env = DrillEnv(Config.load(), sc, seed=5)
    obs = env.reset()
    pol = scripted_policy(sc)
    done = False; k = 0
    while not done and k < 40:
        a = pol(obs, env)
        obs, r, done, info = env.step(a)
        e = env.eng
        st = env._drill
        rows = [f"{u.spec.base}[{u.team}] ({u.x:.2f},{u.y:.2f}) hp{u.hp:.0f} dl{getattr(u,'deploy_left',0):.1f} tgt={nm(getattr(u,'target',None))} lk={getattr(u,'locked',False)}" for u in e.units if u.hp > 0]
        print(f"t={e.t:5.1f} a={a} r={r:+.2f} done={done} info={ {k2:v for k2,v in info.items() if k2 in ('drill','verdict','outcome')} } | " + " ; ".join(rows))
        k += 1
