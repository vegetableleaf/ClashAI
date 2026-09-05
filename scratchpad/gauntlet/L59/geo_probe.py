"""L59: per-play detail of the geometry credits under the wiring test's fixed stream (enabled=true)."""
import os, sys, random
sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/tests"); sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/src")
from test_geometry_wiring import make_cfg, fixed_stream_action, SEEDS, MAX_STEPS
from clashrl.sim.env import SimMatchEnv
cfg = make_cfg(True)
creds, gates = [], []
for seed in SEEDS:
    env = SimMatchEnv(cfg, seed=seed); env.reset(); rng = random.Random(1000 + seed)
    print(f"== seed {seed}")
    for i in range(MAX_STEPS):
        a = fixed_stream_action(env, rng)
        _o, r, done, _ = env.step(a)
        c = env._geo_cache
        if c is not None:
            t = c[1]
            if t.get("credit", 0.0) != 0.0 or t.get("p1_pull_band", 0) or t.get("p6_siege", 0):
                base = env.specs[a[1]].base
                print(f"  step {i:3d} t={env.eng.t:5.1f} {base:14s} tile=({t.get('d_path','-')}) threat={t['threat_base']:12s} "
                      f"src={'module' if t['threat_module'] else 'env':6s} gate={t['gate']:.2f} p1={t['p1_pull_band']:.2f} "
                      f"p1c={t['p1_close_penalty']:.2f} p2={t['p2_cover']:.2f} p3={t['p3_intercept']:.2f} p5={t['p5_timing']:.2f} "
                      f"p6={t['p6_siege']:.2f} credit={t.get('credit', 0.0):+.3f} r={r:+.3f}")
            if t.get("credit", 0.0) != 0.0:
                creds.append(t["credit"]); gates.append(t["gate"])
        if done:
            break
print(f"paid credits n={len(creds)} min {min(creds) if creds else 0:+.3f} max {max(creds) if creds else 0:+.3f}; gates {sorted(round(g,2) for g in gates)}")
