"""L20b: the DrillEnv trace showed the first LEGAL agent row is y=0.5625 (18x24 grid, min_own_gy 13) and the
action lands +0.25 s late (action_latency). Redo the tank_for_bow sweep on LEGAL cells only, with the bow
further back so a knight can physically stand in front of it. Ours L16, enemy L14 and L16."""
import sys, collections; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.drill_env import deploy_unit
from clashrl.sim.aggro_oracle import AggroOracle, TICK
env = SimMatchEnv(Config.load()); A = env.actions
ROWS = [A.cell_center(0, gy)[1] for gy in range(A.min_own_gy, A.min_own_gy + 3)]
COLS = [A.cell_center(gx, A.min_own_gy)[0] for gx in range(0, 9)]
def board(*spawns):
    env.reset(); e = env.eng; e.units.clear(); e.spells.clear(); e.projectiles.clear()
    for key, team, x, y, lvl in spawns:
        deploy_unit(e, team, e.db, key, x, y, lvl)
    for _ in range(20):
        if len(e.units) >= len(spawns): break
        e.advance(TICK)
    for u in e.units: u.deploy_left = 0.0
    e.advance(TICK); return e
for bow_y in (0.60, 0.65, 0.70):
    for elvl in (14, 16):
        e = board(("x_bow", 0, 0.26, bow_y, 16), ("valkyrie", 1, 0.24, 0.42, elvl)); o = AggroOracle(e)
        xb = [u for u in e.units if u.spec.base == "x_bow"][0]; vk = [u for u in e.units if u.spec.base == "valkyrie"][0]
        f, _, fwd = o._fork(); fx, fv = fwd[id(xb)], fwd[id(vk)]; hit = None
        while f.t < 20 and hit is None:
            f.advance(TICK)
            if fv.locked and fv.target is fx: hit = round(f.t, 1)
        took = collections.defaultdict(list)
        for delay in (0.85, 1.45, 2.05, 2.65, 3.25, 3.85):   # agent step k*0.6 + 0.25 latency
            for y in ROWS:
                for x in COLS:
                    f, _, fwd = o._fork(); fx, fv = fwd[id(xb)], fwd[id(vk)]; o._advance(f, delay)
                    kn = o._place(f, 0, "knight", x, y, 16); ok = False
                    for _ in range(80):
                        f.advance(TICK)
                        if kn is not None and fv.hp > 0 and fv.target is kn: ok = True; break
                        if fv.locked and fv.target is fx: break
                    if ok: took[delay].append((round(x, 2), round(y, 3)))
        print(f"bow y={bow_y} enemy L{elvl}: first hit {hit}s; cells by delay: " + ", ".join(f"{d}:{len(v)}" for d, v in took.items()))
        for d in (0.85, 2.05, 3.25):
            print(f"   {d}: {took[d]}")
