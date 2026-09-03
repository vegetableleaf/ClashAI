import sys; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import Tower
from clashrl.sim.drill_env import deploy_unit
from clashrl.sim.aggro_oracle import AggroOracle, TICK
env = SimMatchEnv(Config.load()); A = env.actions
def board(*spawns):
    env.reset(); e = env.eng; e.units.clear(); e.spells.clear(); e.projectiles.clear()
    for key, team, x, y, lvl in spawns: deploy_unit(e, team, e.db, key, x, y, lvl)
    for _ in range(20):
        if len(e.units) >= len(spawns): break
        e.advance(TICK)
    for u in e.units: u.deploy_left = 0.0
    e.advance(TICK); return e
for elvl in (13, 16):
    e = board(("knight", 1, 0.26, 0.45, elvl)); o = AggroOracle(e); kn = e.units[0]
    for gy in range(A.min_own_gy, A.min_own_gy + 2):
        row = []
        for gx in range(A.gw):
            x, y = A.cell_center(gx, gy)
            f, _, fwd = o._fork(); o._advance(f, 0.85); b = o._place(f, 0, "x_bow", x, y, 16)
            tgt = "-"
            if b is None: tgt = "refused"
            else:
                for _ in range(100):
                    f.advance(TICK)
                    if b.hp <= 0: tgt = "x"; break
                    if b.deploy_left <= 0 and b.target is not None:
                        tgt = "T" if isinstance(b.target, Tower) else "k"; break
            row.append(tgt)
        print(f"L{elvl} row y={y:.3f}: " + " ".join(row))
