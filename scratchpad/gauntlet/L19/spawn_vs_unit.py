"""Hand-built Unit(...) vs eng.deploy(): does the board behave the same? (drill_env warns it does not)"""
import sys; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import Unit, Tower, build_spec
env = SimMatchEnv(Config.load())
def run(mode):
    env.reset(); e = env.eng; e.units.clear(); e.spells.clear(); e.projectiles.clear()
    for key, team, x, y in (("x_bow", 0, 0.26, 0.53), ("knight", 1, 0.26, 0.47)):
        s = build_spec(e.db, key, 11)
        if mode == "unit":
            e.units.append(Unit(spec=s, team=team, x=x, y=y, hp=s.hp))
        else:
            e.elixir[team] = max(e.elixir[team], s.elixir + 1.0); e.deploy(team, s, x, y)
            for _ in range(20):
                if any(u.spec.base == key and u.team == team for u in e.units): break
                e.advance(0.1)
            for u in e.units:
                if u.team == team and u.deploy_left > 0: u.deploy_left = 0.0
    xb = [u for u in e.units if u.spec.base == "x_bow"][0]; kn = [u for u in e.units if u.spec.base == "knight"][0]
    hp0 = sum(t.hp for t in e.towers[1][:2]); tbow = tkn = t150 = None
    while e.t < 25:
        e.advance(0.1)
        if tbow is None and xb.hp <= 0: tbow = round(e.t, 1)
        if tkn is None and kn.hp <= 0: tkn = round(e.t, 1)
        if t150 is None and hp0 - sum(t.hp for t in e.towers[1][:2]) >= 150: t150 = round(e.t, 1)
    fields = {k: getattr(xb, k) for k in ("reload_left", "first_hit", "hit_dmg", "hit_speed", "deploy_left", "ammo", "reach_extra", "lifetime") if hasattr(xb, k)}
    print(f"{mode:<6}: bow dies {tbow}, knight dies {tkn}, tower-150 at {t150}; bow fields {fields}")
run("unit"); run("deploy")
