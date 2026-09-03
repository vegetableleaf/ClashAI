"""Oracle cost on a fixed board (L18): per-fork and per-query wall time."""
import sys, os, time
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import Unit, build_spec
from clashrl.sim.aggro_oracle import AggroOracle
env = SimMatchEnv(Config.load()); env.reset(); e = env.eng
e.units.clear(); e.spells.clear(); e.projectiles.clear()
for key, team, x, y in [("x_bow",0,0.26,0.53),("valkyrie",1,0.26,0.40),("musketeer",0,0.30,0.60),
                        ("hog_rider",1,0.75,0.35),("goblin_gang",1,0.5,0.4),("tesla",0,0.5,0.6)]:
    s = build_spec(e.db, key, 11); e.units.append(Unit(spec=s, team=team, x=x, y=y, hp=s.hp))
e.advance(0.1)
o = AggroOracle(e); xb, vk = e.units[0], e.units[1]
print("units on board:", len(e.units))
def T(label, fn, n=5):
    t0 = time.perf_counter()
    for _ in range(n): r = fn()
    print(f"{label:<28} {1000*(time.perf_counter()-t0)/n:8.1f} ms  -> {r}")
T("fork only", lambda: o._fork() and None, 20)
T("targets_at(0)", lambda: len(o.targets_at(0.0)))
T("targets_at(3s)", lambda: len(o.targets_at(3.0)))
T("next_target_after_kill", lambda: o.next_target_after_kill(vk))
T("draws(knight,1s)", lambda: o.draws(0,"knight",0.26,0.46,horizon_s=1.0).z_alive)
T("after_spell(tornado,1.5s)", lambda: len(o.after_spell(0,"tornado",0.472,0.771)))
T("interpose_window(6s/0.2)", lambda: o.interpose_window(0,"knight",0.26,0.46,vk,xb), 2)
T("duel(knight,valk)", lambda: o.duel("knight","valkyrie").winner, 2)
