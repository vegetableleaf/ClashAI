import sys; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import Unit, Tower, build_spec
from clashrl.sim.aggro_oracle import AggroOracle, TICK
env = SimMatchEnv(Config.load())
def board(*spawns):
    env.reset(); e = env.eng; e.units.clear(); e.spells.clear(); e.projectiles.clear(); out=[]
    for key, team, x, y in spawns:
        s = build_spec(e.db, key, 11); u = Unit(spec=s, team=team, x=x, y=y, hp=s.hp); e.units.append(u); out.append(u)
    e.advance(0.1); return e, out
# sneaky lock: no tornado, knight only at 2.4 / nothing at all
e, (xb, kn1) = board(("x_bow", 0, 0.26, 0.53), ("knight", 1, 0.26, 0.47)); o = AggroOracle(e)
hp0 = sum(t.hp for t in e.towers[1])
for label, knight in (("nothing", False), ("knight only @2.4", True)):
    f, back, fwd = o._fork(); fx = fwd[id(xb)]; placed=None; relock=False; bow_hit_tower_t=None
    while f.t < 22.0 and not f.done:
        f.advance(TICK)
        if knight and placed is None and f.t >= 2.4: placed = o._place(f, 0, "knight", 0.26, 0.56, 11)
        if fx.hp > 0 and isinstance(fx.target, Tower): relock = True
    lost = hp0 - sum(t.hp for t in f.towers[1])
    who = "knight" if placed is not None and placed.target is not None else "-"
    print(f"{label:<18} tower lost {lost:6.0f}  bow relocked {relock}  bow alive {fx.hp>0}  enemy knight alive {fwd[id(kn1)].hp>0}")
# knight_guards_the_bow: when does the bow die with NO knight, and is the bow alive at each delay?
e, (xb, vk) = board(("x_bow", 0, 0.26, 0.56), ("valkyrie", 1, 0.24, 0.42)); o = AggroOracle(e)
f, back, fwd = o._fork(); fx = fwd[id(xb)]; fv = fwd[id(vk)]; first=None
while f.t < 25 and fx.hp > 0:
    f.advance(TICK)
    if first is None and fv.locked and fv.target is fx: first = f.t
print(f"no knight: valk first hit at {first}s, bow dies at {f.t:.1f}s -> a knight played any time before {f.t:.1f}s passes the drill")
