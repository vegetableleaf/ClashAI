"""L20: choose the two aggro drill boards at TRAINING levels (ours: x_bow 16, knight 16; enemy 14 = the modal ladder roll).
(1) tank_for_bow: which knight cells x delays take the Valkyrie's lock off the standing bow?
(2) bow_lane_choice: enemy knight walking down the left lane; which bow cells give a FIRST lock on a tower vs the knight?"""
import sys, time, collections; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import Unit, Tower, build_spec
from clashrl.sim.drill_env import deploy_unit
from clashrl.sim.aggro_oracle import AggroOracle, TICK
env = SimMatchEnv(Config.load())
def board(*spawns):
    env.reset(); e = env.eng; e.units.clear(); e.spells.clear(); e.projectiles.clear()
    for key, team, x, y, lvl in spawns:
        deploy_unit(e, team, e.db, key, x, y, lvl)
    for _ in range(20):
        if len(e.units) >= len(spawns): break
        e.advance(TICK)
    for u in e.units: u.deploy_left = 0.0
    e.advance(TICK); return e
XS = [round(0.05 * i, 2) for i in range(1, 20)]
def cells(y_lo, y_hi): return [(x, round(0.05 * j, 2)) for j in range(int(y_lo*20), int(y_hi*20)+1) for x in XS]

# (1) tank_for_bow at 16/16 vs 14
for elvl in (14, 16):
    e = board(("x_bow", 0, 0.26, 0.56, 16), ("valkyrie", 1, 0.24, 0.42, elvl)); o = AggroOracle(e)
    xb = [u for u in e.units if u.spec.base == "x_bow"][0]; vk = [u for u in e.units if u.spec.base == "valkyrie"][0]
    took = collections.defaultdict(list); hit = None
    f, _, fwd = o._fork(); fx, fv = fwd[id(xb)], fwd[id(vk)]
    while f.t < 15 and hit is None:
        f.advance(TICK)
        if fv.locked and fv.target is fx: hit = round(f.t, 1)
    for delay in (0.6, 1.2, 1.8, 2.4, 3.0):
        for (x, y) in cells(0.50, 0.95):
            f, _, fwd = o._fork(); fx, fv = fwd[id(xb)], fwd[id(vk)]; o._advance(f, delay)
            kn = o._place(f, 0, "knight", x, y, 16); ok = False
            for _ in range(60):
                f.advance(TICK)
                if kn is not None and fv.hp > 0 and fv.target is kn: ok = True; break
                if fv.locked and fv.target is fx: break
            if ok: took[delay].append((x, y))
    print(f"tank_for_bow enemy L{elvl}: valk first hit on bow at {hit}s; lock-taking cells by delay:",
          {d: len(v) for d, v in took.items()}, "| delay 0.6:", took[0.6], "| delay 1.8:", took[1.8])

# (2) bow_lane_choice: enemy knight L14 at (0.26, 0.45) walking; bow placed at t=0.6 on each of our cells
e = board(("knight", 1, 0.26, 0.45, 14)); o = AggroOracle(e)
kn = e.units[0]; first = {}
t0 = time.time()
for (x, y) in cells(0.50, 0.95):
    f, back, fwd = o._fork(); fk = fwd[id(kn)]; o._advance(f, 0.6)
    b = o._place(f, 0, "x_bow", x, y, 16)
    if b is None: first[(x, y)] = "refused"; continue
    tgt = None
    for _ in range(80):
        f.advance(TICK)
        if b.hp <= 0: tgt = "dead"; break
        if b.deploy_left <= 0 and b.target is not None:
            tgt = "TOWER" if isinstance(b.target, Tower) else f"unit:{b.target.spec.base}"; break
    first[(x, y)] = tgt or "none@8s"
print(f"\nbow_lane_choice ({len(first)} cells, {time.time()-t0:.1f}s):", collections.Counter(first.values()))
for y in sorted(set(c[1] for c in first), reverse=True):
    print(f"  y={y:.2f} " + " ".join({"TOWER": "T", "unit:knight": "k", "refused": "-", "dead": "x"}.get(first[(x, y)], "?") for x in XS))
