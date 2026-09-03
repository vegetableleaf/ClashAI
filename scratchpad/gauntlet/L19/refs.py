import sys, json; sys.path.insert(0, "src")
rows = json.load(open("../scratchpad/gauntlet/L19/drill_sweep.json"))
k = [r for r in rows["knight_guards_the_bow"] if r["took_lock"] and r["bow_alive"]]
print("knight combos where the lock is taken AND the bow lives to 20 s:", [(r["delay"], r["x"], r["y"], "valk_dead" if r["valk_dead"] else "") for r in k])
print("ref cell (0.25,0.5) by delay:", [(r["delay"], r["took_lock"], r["bow_alive"]) for r in rows["knight_guards_the_bow"] if (r["x"], r["y"]) == (0.25, 0.5)])
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import Unit, Tower, build_spec
from clashrl.sim.aggro_oracle import AggroOracle, TICK
env = SimMatchEnv(Config.load()); env.reset(); e = env.eng
e.units.clear(); e.spells.clear(); e.projectiles.clear()
for key, team, x, y in (("x_bow", 0, 0.26, 0.53), ("knight", 1, 0.26, 0.47)):
    s = build_spec(e.db, key, 11); e.units.append(Unit(spec=s, team=team, x=x, y=y, hp=s.hp))
e.advance(0.1); o = AggroOracle(e); xb, kn1 = e.units
hp0 = sum(t.hp for t in e.towers[1])
for wk in (False, True):
    f, back, fwd = o._fork(); fx = fwd[id(xb)]; fk = fwd[id(kn1)]; o._advance(f, 1.2); o._place(f, 0, "tornado", 0.26, 0.40, 11)
    relock=None; placed=None; ymin=fk.y
    while f.t < 22 and not f.done:
        f.advance(TICK); ymin = min(ymin, fk.y)
        if wk and placed is None and f.t >= 2.4: placed = o._place(f, 0, "knight", 0.26, 0.56, 11)
        if relock is None and fx.hp > 0 and isinstance(fx.target, Tower): relock = round(f.t, 1)
    print(f"EXACT reference tornado (0.26,0.40)@1.2 knight={wk}: enemy knight pulled to y={ymin:.3f} (from 0.47), bow relock at {relock}, tower lost {hp0-sum(t.hp for t in f.towers[1]):.0f}, bow alive {fx.hp>0}, enemy knight alive {fk.hp>0}")
