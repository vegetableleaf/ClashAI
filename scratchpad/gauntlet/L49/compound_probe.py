"""COMPOUND-DRILL INSTRUMENT READ (L49). Force every drill episode to be a compound board
(sim.drill_compound_frac 1.0 in-process; the on-disk configs stay 0.0) and read, on the SAME
boards (same seed -> same component draws), what NOTHING, the DOCTRINE oracle and a checkpoint
score. Also: does compound_verdict fire at all, how long the boards run, and the per-component
pass pattern. No training, no config file touched.

    PYTHONHASHSEED=0 ./.venv/Scripts/python.exe <this> --ckpt data/bench/c2r_m20k.pt --reps 48 --seed 5
"""
import argparse, collections, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3] / "icebow"
sys.path.insert(0, str(ROOT / "src"))
from clashrl.config import Config                                     # noqa: E402
from clashrl.sim import scenarios as sc                               # noqa: E402
from clashrl.sim.drill_env import DrillEnv, doctrine_policy, compound_verdict   # noqa: E402
from clashrl.cli import _drill_policy_from_checkpoint                 # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ckpt", action="append", default=[])
ap.add_argument("--reps", type=int, default=48)
ap.add_argument("--seed", type=int, default=5)
ap.add_argument("--out", default=None)
ap.add_argument("--full-elixir", action="store_true",
                help="start every compound board at 10 elixir (is the per-component collapse scarcity?)")
args = ap.parse_args()

sc.load_all()
cfg = Config.load(ROOT / "config" / "config.yaml")
cfg.data.setdefault("sim", {})["drill_compound_frac"] = 1.0
cfg.data["sim"]["drill_play_out"] = False          # end at the verdict: the read is the verdict
print("[compound] pass_frac %s hp_frac %s n_max %s (config VALUES)" % (
    cfg.get("sim", "drill_compound_pass_frac"), cfg.get("sim", "drill_compound_hp_frac"),
    cfg.get("sim", "drill_compound_n")))
anchor = [s for s in sc.all_scenarios() if getattr(s, "hand", ())][0]   # ignored: every reset composes
if args.full_elixir:
    _orig = DrillEnv._place_components

    def _full(self):
        _orig(self)
        self.eng.elixir[0] = 10.0
    DrillEnv._place_components = _full
    print("[compound] FULL ELIXIR override: every board starts at 10")


def run(policy, label):
    env = DrillEnv(cfg, anchor, seed=args.seed)
    tally = collections.Counter(); comp = collections.Counter(); boards = []
    t0 = time.time()
    for r in range(args.reps):
        obs = env.reset()
        names = [c["scenario"].name for c in env._components]
        done, total, steps = False, 0.0, 0
        info = {}
        while not done:
            a = (0, 0, 0) if policy is None else policy(obs, env)
            obs, rew, done, info = env.step(a)
            total += float(rew); steps += 1
        v, res = compound_verdict(env)
        verdict = (info or {}).get("verdict", "timeout")
        tally[verdict] += 1
        for n, cres in zip(names, res):
            comp[(n, cres)] += 1
        boards.append({"components": names, "verdict": verdict, "per_component": res,
                       "steps": steps, "reward": round(total, 3),
                       "elapsed": round(float((info or {}).get("elapsed", 0.0)), 1),
                       "spent": round(float((info or {}).get("spent", 0.0)), 1)})
    n = max(1, args.reps)
    print("%-10s pass %5.1f%%  fail %5.1f%%  timeout %5.1f%%  | %.1f s/board wall, mean %.1f steps, "
          "elapsed %.1f s, spent %.1f elixir"
          % (label, 100 * tally["pass"] / n, 100 * tally["fail"] / n, 100 * tally["timeout"] / n,
             (time.time() - t0) / n, sum(b["steps"] for b in boards) / n,
             sum(b["elapsed"] for b in boards) / n, sum(b["spent"] for b in boards) / n))
    return {"label": label, "tally": dict(tally), "boards": boards,
            "components": {"%s|%s" % k: v for k, v in comp.items()}}


results = [run(None, "nothing"), run(doctrine_policy, "doctrine")]
for ck in args.ckpt:
    pol = _drill_policy_from_checkpoint(ck)
    if pol is not None:
        results.append(run(pol, Path(ck).stem))

# per-component pass rates by policy, for the components that appeared
print("\nper-component PASS share (component pass / times it appeared):")
allnames = sorted({k.split("|")[0] for r in results for k in r["components"]})
print("  %-34s " % "component" + " ".join("%10s" % r["label"][:10] for r in results))
for nme in allnames:
    row = []
    for r in results:
        seen = sum(v for k, v in r["components"].items() if k.split("|")[0] == nme)
        ok = r["components"].get(nme + "|pass", 0)
        row.append("%4d/%-4d" % (ok, seen) if seen else "     -   ")
    print("  %-34s " % nme + " ".join("%10s" % x for x in row))
# board size distribution and stagger
sizes = collections.Counter(len(b["components"]) for b in results[0]["boards"])
print("\nboards: %d, components per board %s" % (args.reps, dict(sizes)))
if args.out:
    Path(args.out).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("wrote", args.out)
