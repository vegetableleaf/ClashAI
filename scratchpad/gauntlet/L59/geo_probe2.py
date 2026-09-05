"""L59: credit ranges by kind over more seeds (fixed random stream, enabled=true)."""
import sys, random, statistics as st
sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/tests"); sys.path.insert(0, "C:/Users/benpe/ClashBot/icebow/src")
from test_geometry_wiring import make_cfg, fixed_stream_action, MAX_STEPS
from clashrl.sim.env import SimMatchEnv
cfg = make_cfg(True)
rows = []
seeds = list(range(20, 32))
for seed in seeds:
    env = SimMatchEnv(cfg, seed=seed); env.reset(); rng = random.Random(1000 + seed)
    for i in range(MAX_STEPS):
        a = fixed_stream_action(env, rng)
        _o, r, done, _ = env.step(a)
        c = env._geo_cache
        if c is not None and a[0]:
            t = c[1]; kind = env.specs[a[1]].kind
            rows.append((seed, kind, env.specs[a[1]].base, t))
        if done:
            break
print(f"seeds {seeds[0]}..{seeds[-1]} ({len(seeds)} matches), scored placements n={len(rows)}")
for kind in ("building", "troop", "spell"):
    rr = [t for _, k, _, t in rows if k == kind]
    paid = [t for t in rr if t.get("credit", 0.0) != 0.0]
    print(f"{kind}: scored {len(rr)}, paid (credit != 0) {len(paid)}, module-threat among paid {sum(1 for t in paid if t['threat_module'])}")
    if paid:
        cr = [t["credit"] for t in paid]
        print(f"   credit min {min(cr):+.3f} median {st.median(cr):+.3f} max {max(cr):+.3f}; "
              f"time part >0 {sum(1 for t in paid if t['p5_timing']>0)}, place part >0 {sum(1 for t in paid if (t['p1_pull_band']*(0.5+0.5*t['p2_cover'])+t['p6_siege'] if kind=='building' else t['p3_intercept'])>0)}, "
              f"close<0 {sum(1 for t in paid if t['p1_close_penalty']<0)}, gate<1 {sum(1 for t in paid if t['gate']<1)}")
    for k in ("p1_pull_band", "p1_snapshot", "p1_close_penalty", "p2_cover", "p3_intercept", "p5_timing", "p6_siege", "p4_spell_frac", "p7_fragility"):
        v = [t[k] for t in rr if t[k] != 0]
        if v:
            print(f"   {k:16s} nonzero {len(v)}/{len(rr)} min {min(v):+.3f} max {max(v):+.3f} mean {st.mean(v):+.3f}")
