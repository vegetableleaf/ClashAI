import sys; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim import scenarios as sc
from clashrl.sim.drill_env import DrillEnv
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import build_spec
sc.load_all(); cfg = Config.load()
env = DrillEnv(cfg, sc.get("nado_the_sneaky_lock"), seed=5, level=11); env.reset(); e = env.eng
env.step((0,0,0))
for u in e.units: print("DRILL", u.spec.base, "team", u.team, "level", getattr(u.spec, "level", "?"), "hp", round(u.hp), "max", round(u.spec.hp), "dmg", getattr(u.spec, "hit_dmg", getattr(u.spec, "dmg", "?")), "x", round(u.x,3), "y", round(u.y,3))
print("DRILL towers", [(round(t.x,2), round(t.y,2), round(t.hp)) for t in e.towers[1]])
print("cfg sim.level:", cfg.get("sim", "level", default=None), " enemy_level:", cfg.get("sim", "enemy_level", default=None), " our:", cfg.get("sim", "our_level", default=None))
m = SimMatchEnv(cfg); m.reset()
for key in ("x_bow", "knight"):
    s = build_spec(m.eng.db, key, 11); print("build_spec L11", key, "hp", round(s.hp), "dmg", getattr(s, "hit_dmg", getattr(s, "dmg", "?")))
