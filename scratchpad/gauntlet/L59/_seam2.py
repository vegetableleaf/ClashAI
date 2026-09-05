import sys; sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/tests"); sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/src")
import random
mode = sys.argv[1]
if mode == "perturb":
    from clashrl.config import Config; Config.load(); Config.load()
from test_geometry_wiring import make_cfg, fixed_stream_action
from clashrl.sim.env import SimMatchEnv
cfg = make_cfg(False); env = SimMatchEnv(cfg, seed=7); env.reset(); rng = random.Random(1007)
for step in range(400):
    a = fixed_stream_action(env, rng)
    before = {k: v.total for k, v in env.rw_stats.match.items()}
    _o, r, done, _ = env.step(a)
    if step in (93, 94):
        after = {k: v.total for k, v in env.rw_stats.match.items()}
        d = {k: round(after[k] - before.get(k, 0.0), 4) for k in after if abs(after[k] - before.get(k, 0.0)) > 1e-9}
        card = env.deck_keys[a[1]] if a[0] else "-"
        print(mode, "step", step, "t", round(env.eng.t, 1), "action", a, card, "r", round(r, 4), "terms", d)
    if done: break
