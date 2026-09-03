"""Trace nado_the_sneaky_lock in the REAL DrillEnv with no play: who does the bow target, when does the
tower lose hp, when does the bow die? Explains the report's 'nothing 100%'."""
import sys; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim import scenarios as sc
from clashrl.sim.drill_env import DrillEnv
from clashrl.sim.engine import Tower, Unit
sc.load_all()
s = sc.get("nado_the_sneaky_lock"); cfg = Config.load()
env = DrillEnv(cfg, s, seed=5, level=11); obs = env.reset(); e = env.eng
hp0 = sum(t.hp for t in e.towers[1][:2]); done = False; k = 0
def name(t):
    if isinstance(t, Tower): return f"TOWER(king={t.king},x={t.x:.2f})"
    if isinstance(t, Unit): return f"unit {t.spec.base} t{t.team}"
    return "-"
while not done and k < 40:
    obs, r, done, info = env.step((0, 0, 0)); k += 1
    bows = [u for u in e.units if u.team == 0 and u.spec.base == "x_bow"]
    kns = [u for u in e.units if u.team == 1 and u.spec.base == "knight"]
    b = bows[0] if bows else None; kn = kns[0] if kns else None
    print(f"t={e.t:5.1f} bow hp {b.hp if b else 0:6.0f} dl={getattr(b,'deploy_left',0) if b else 0:.1f} tgt={name(b.target) if b else '-'} | "
          f"knight hp {kn.hp if kn else 0:5.0f} y={kn.y if kn else 0:.3f} tgt={name(kn.target) if kn else '-'} | "
          f"tower lost {hp0 - sum(t.hp for t in e.towers[1][:2]):5.0f} verdict={info.get('verdict')}")
    if info.get("verdict"): break
