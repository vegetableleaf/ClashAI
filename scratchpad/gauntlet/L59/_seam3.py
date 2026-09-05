import sys; sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/tests"); sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/src")
import numpy as np
mode = sys.argv[1]
if mode == "perturb":
    from clashrl.config import Config; Config.load(); Config.load()
import test_geometry_wiring as T
from clashrl.sim.env import SimMatchEnv
import random
ref = np.load(T.REF, allow_pickle=True)
print(mode, "ref[0][94] =", ref[0][94])
cfg = T.make_cfg(False); env = SimMatchEnv(cfg, seed=7); env.reset(); rng = random.Random(1007)
for step in range(400):
    a = T.fixed_stream_action(env, rng)
    before = {k: v.total for k, v in env.rw_stats.match.items()}
    _o, r, done, _ = env.step(a)
    if step == 94:
        after = {k: v.total for k, v in env.rw_stats.match.items()}
        d = {k: round(after[k] - before.get(k, 0.0), 4) for k in after if abs(after[k] - before.get(k, 0.0)) > 1e-9}
        card = env.deck_keys[a[1]] if a[0] else "-"
        nx, ny = env.actions.cell_center(a[2] % env.gw, a[2] // env.gw) if a[0] else (0, 0)
        print(mode, "step", step, "t", round(env.eng.t, 1), "action", a, card, (round(nx,3), round(ny,3)), "r", round(r, 4), "terms", d,
              "enemy", [(u.spec.base, round(u.x*18,1), round(u.y*32,1)) for u in env.eng.units if u.team == 1 and u.hp > 0][:6])
    if done: break
