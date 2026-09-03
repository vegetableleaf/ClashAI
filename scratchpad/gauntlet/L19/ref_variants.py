"""nado_the_sneaky_lock: which part of the reference line earns the pass? Same seed -> same ladder rolls."""
import sys, dataclasses; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim import scenarios as sc
from clashrl.sim.drill_env import run_drill, scripted_policy
sc.load_all(); cfg = Config.load(); s = sc.get("nado_the_sneaky_lock")
variants = {
  "reference (nado 0.26,0.40 @1.2 + knight 0.26,0.56 @2.4)": s.reference,
  "knight only @2.4": (("knight", 0.26, 0.56, 2.4),),
  "nado only @1.2": (("tornado", 0.26, 0.40, 1.2),),
  "nado CENTRE (0.50,0.42) @1.2 only": (("tornado", 0.50, 0.42, 1.2),),
  "nado CENTRE @1.2 + knight @2.4": (("tornado", 0.50, 0.42, 1.2), ("knight", 0.26, 0.56, 2.4)),
  "knight @0.6 in front (0.26,0.50)": (("knight", 0.26, 0.50, 0.6),),
}
for label, ref in variants.items():
    v = dataclasses.replace(s, reference=ref)
    for lvl in (None, 11, 14, 16):
        r = run_drill(cfg, v, policy=scripted_policy(v), reps=40, seed=5, level=lvl)
        print(f"{label:<52} enemy L{lvl or 'ladder':<7} pass {100*r['pass_rate']:5.1f}%  fail {r['fail']:2d} timeout {r['timeout']:2d}", flush=True)
