"""Does the enemy DISTRACTOR (sim.drill_noise) block the 'no enemy alive' success predicates?
Same drills, same seed, doctrine oracle; drill_noise 0.0 vs 0.5 (c2r_run.yaml's value).
The predicates read `e.units` unfiltered, so the tagged distractor is visible to the grader."""
import sys, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3] / "icebow"
sys.path.insert(0, str(ROOT / "src"))
from clashrl.config import Config
from clashrl.sim import scenarios as sc
from clashrl.sim.drill_env import run_drill, doctrine_policy
sc.load_all()
src = (ROOT / "src/clashrl/sim/drills_icebow.py").read_text(encoding="utf-8")
# the drills whose SUCCESS is a global "no enemy alive"
affected = []
for m in re.finditer(r'name="([a-z_0-9]+)"(.*?)(?=name="|\Z)', src, re.S):
    body = m.group(2)
    if re.search(r'success=lambda e, s: \(not any\(u\.team == 1 and u\.hp > 0 for u in e\.units\)', body) \
       or re.search(r'success=.*?not any\(u\.team == 1 and u\.hp > 0 for u in e\.units\)', body[:400], re.S):
        affected.append(m.group(1))
print("affected drills:", len(affected), affected)
reps = int(sys.argv[1]) if len(sys.argv) > 1 else 25
byname = {s.name: s for s in sc.all_scenarios()}
tot = {0.0: [0, 0], 0.5: [0, 0]}
print("%-34s %8s %8s   %s" % ("drill", "noise0", "noise.5", "doctrine pass"))
for n in affected:
    s = byname.get(n)
    if s is None:
        continue
    row = []
    for noise in (0.0, 0.5):
        cfg = Config.load(ROOT / "config" / "config.yaml")
        cfg.data["sim"]["drill_noise"] = noise
        cfg.data["sim"]["drill_play_out"] = False
        r = run_drill(cfg, s, policy=doctrine_policy, reps=reps, seed=5)
        row.append(r["pass_rate"]); tot[noise][0] += r["pass"]; tot[noise][1] += reps
    print("%-34s %7.0f%% %7.0f%%" % (n, 100 * row[0], 100 * row[1]))
print("POOLED doctrine pass: noise 0 %.1f%%  noise 0.5 %.1f%%  (n=%d each)"
      % (100 * tot[0.0][0] / tot[0.0][1], 100 * tot[0.5][0] / tot[0.5][1], tot[0.0][1]))

# ---- third arm: noise 0.5 boards, but the SUCCESS predicate sees the engine through a view that
# hides drill_noise-tagged units (what enemy_units() would have done). Isolates grading from behaviour.
class _View:
    def __init__(self, eng): self._e = eng
    def __getattr__(self, k): return getattr(self._e, k)
    @property
    def units(self): return [u for u in self._e.units if not getattr(u, "drill_noise", False)]
import copy
tot3 = [0, 0]
print("\n%-34s %8s %8s %8s" % ("drill", "noise0", "noise.5", ".5+hide"))
for n in affected:
    s = byname.get(n)
    if s is None: continue
    import dataclasses
    orig_succ = s.success
    s2 = dataclasses.replace(s, success=(lambda e, sc_, _o=orig_succ: _o(_View(e), sc_)))
    cfg = Config.load(ROOT / "config" / "config.yaml")
    cfg.data["sim"]["drill_noise"] = 0.5; cfg.data["sim"]["drill_play_out"] = False
    r = run_drill(cfg, s2, policy=doctrine_policy, reps=reps, seed=5)
    tot3[0] += r["pass"]; tot3[1] += reps
    print("%-34s %26.0f%%" % (n, 100 * r["pass_rate"]))
print("POOLED noise 0.5 + grading hides distractor: %.1f%% (n=%d)" % (100 * tot3[0] / tot3[1], tot3[1]))
