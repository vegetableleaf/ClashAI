import sys; sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/tests"); sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/src")
import numpy as np
mode = sys.argv[1]
if mode == "torch":
    import torch
elif mode == "random":
    import random; random.random(); np.random.random()
elif mode == "remote_import":
    import clashrl.sim.remote_pool
elif mode == "config_twice":
    from clashrl.config import Config; Config.load(); Config.load()
from test_geometry_wiring import make_cfg, run_matches, REF, SEEDS
ref = np.load(REF, allow_pickle=True)
rewards, ledgers = run_matches(make_cfg(False))
for i, (a, b) in enumerate(zip(rewards, ref)):
    bad = np.nonzero(a != b)[0] if len(a) == len(b) else ["len"]
    print(mode, "match", i, "differs at", list(bad)[:5], "" if not len(bad) or bad[0]=="len" else (a[bad[0]], b[bad[0]]))
