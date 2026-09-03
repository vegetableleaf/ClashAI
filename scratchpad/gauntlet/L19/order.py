import sys; sys.path.insert(0, "src")
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
def run(nado, knight_t, knight_xy=(0.26, 0.56)):
    f, back, fwd = o._fork(); fx = fwd[id(xb)]; fk = fwd[id(kn1)]; placed=None; t150=None; tbow=None; tk=None; bow_shots_on_tower=0
    while f.t < 22 and not f.done:
        f.advance(TICK)
        if nado and abs(f.t-1.2) < 0.05: o._place(f, 0, "tornado", nado[0], nado[1], 11)
        if knight_t is not None and placed is None and f.t >= knight_t: placed = o._place(f, 0, "knight", *knight_xy, 11)
        lost = hp0 - sum(t.hp for t in f.towers[1])
        if t150 is None and lost >= 150: t150 = round(f.t, 1)
        if tbow is None and fx.hp <= 0: tbow = round(f.t, 1)
        if tk is None and fk.hp <= 0: tk = round(f.t, 1)
    verdict = "PASS" if (t150 is not None and (tbow is None or t150 < tbow)) else ("FAIL(bow died first)" if tbow else "timeout")
    return f"nado={nado} knight@{knight_t}{knight_xy}: enemy knight dies {tk}, bow dies {tbow}, tower-150 at {t150}, lost {lost:.0f} -> drill {verdict}"
print(run(None, None)); print(run(None, 2.4)); print(run((0.26, 0.40), None)); print(run((0.26, 0.40), 2.4))
print(run((0.5, 0.4), None)); print(run((0.5, 0.4), 2.4)); print(run(None, 0.6, (0.26, 0.50))); print(run(None, 0.6, (0.26, 0.44)))
