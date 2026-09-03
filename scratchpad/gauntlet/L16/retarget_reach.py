"""Is the sim's nado_retarget credit REACHABLE? Enemy hog locked on our left princess, tornado cast 4 tiles
toward the bridge from it, 2.5 s of engine time, then the sim's own predicate. No policy involved."""
import os, sys, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[3] / "icebow"; sys.path.insert(0, str(_ROOT / "src")); os.chdir(_ROOT)
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import build_spec, Unit, tile_dist
env = SimMatchEnv(Config.load()); env.rng.seed(0); env.reset()
e = env.eng; e.units.clear(); e.spells.clear(); e.projectiles.clear()
tw = e.towers[0][0]; print("our princess", round(tw.x,3), round(tw.y,3), "alive", tw.alive)
hog = build_spec(env.db, "hog_rider", 11)
for back in (3.0, 4.0, 5.0):
    e.units.clear(); e.spells.clear(); env._nado_watch.clear()
    u = Unit(spec=hog, team=1, x=tw.x, y=tw.y - (hog.reach + 0.5) / 32.0, hp=hog.hp); e.units.append(u)
    e.advance(0.3)                       # let it lock
    print(f"\nback={back}: hog target is our tower? {getattr(u,'target',None) is tw}  d0={tile_dist(u.x,u.y,tw.x,tw.y):.2f}")
    ci = env.deck_keys.index("tornado"); sp = env.specs[ci]
    nx, ny = u.x, u.y - back / 32.0
    try: e.elixir[0] = 10.0
    except Exception: pass
    ok = e.deploy(0, sp, nx, ny); env._register_nado(nx, ny, sp)
    w = env._nado_watch[-1]; print("  deploy ok", ok, "pulled", len(w["pulled"]), "targeters", len(w["targeters"]))
    for _ in range(25):
        e.advance(0.1); env._nado_catch(w) if (e.t - w["t0"]) <= env.nado_pull_window else None
    d1 = tile_dist(u.x, u.y, tw.x, tw.y)
    fires = any(uu.hp > 0 and tile_dist(uu.x, uu.y, t.x, t.y) >= d0 + 1.6 for uu, t, d0 in w["targeters"])
    print(f"  after 2.5 s: hog d={d1:.2f} (moved {d1 - w['targeters'][0][2] if w['targeters'] else float('nan'):+.2f} tiles), hp {u.hp:.0f}, target still tower? {getattr(u,'target',None) is tw} -> RETARGET fires: {fires}")
