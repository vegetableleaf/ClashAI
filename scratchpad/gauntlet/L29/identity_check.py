"""L29: floor=0 must be the HISTORICAL bot: hash every opponent deploy (t, card, x, y) over N matches, eval-style
(adaptive=False) and training-style (adaptive=True), for HEAD's opponents.py vs the patched one."""
import sys, hashlib
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.opponents import make_opponent
cfg = Config.load("data/bench/gate05_run.yaml")
for adaptive in (False, True):
    env = SimMatchEnv(cfg); env.rng.seed(0)
    env.opponent_provider = lambda e: make_opponent(cfg, e.db, e.rng, e.meta_pool, adaptive=adaptive)
    env.reset(); h = hashlib.sha256(); done = 0; n = 0
    while done < 4:
        e = env.eng
        d = e.last_deploy.get(1)
        if d:
            h.update(repr((round(e.t, 3), d[0].base, round(d[1], 4), round(d[2], 4), round(d[3], 3))).encode()); n += 1
        _o, _r, dn, info = env.step((0, 0, 0))
        if dn:
            done += 1; env.reset()
    print(f"adaptive={adaptive}: {n} steps-with-a-deploy, sha {h.hexdigest()[:16]}")
