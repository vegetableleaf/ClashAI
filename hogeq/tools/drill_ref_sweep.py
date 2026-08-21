"""Find a reference line that still works at LADDER levels.

    python tools/drill_ref_sweep.py <drill> [step] [reps]

A `Scenario.reference` is not just documentation. It is the third column of `run.py drills` (the
proof a scenario is winnable at all) AND the source of `drill_prior_cells` -- the exploration prior
the trainer samples during a drill. So a reference that has gone stale does not merely look bad in
a report: it aims the trainer's own prior at a cell that no longer works.

Every reference was hand-written against level 11 enemies. Now that drills roll the ladder levels
the full sim uses, several lines pass well below their drill's doctrine column -- which is the tell
that the DRILL is fine and the LINE is stale (a broken drill fails both).

This sweeps one step of the line over a grid of placements and times, leaving the other steps where
they are, and reports the pass rate of each candidate at ladder levels.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim import scenarios as sc                 # noqa: E402
from clashrl.sim.drill_env import DrillEnv              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def line_policy(steps):
    """Play these (base, x, y, t) steps in order, mirroring with the board."""
    state = {"i": 0, "ep": None}

    def _policy(obs, env):
        if state["ep"] is not env._drill.get("t0"):
            state["ep"], state["i"] = env._drill.get("t0"), 0
        i = state["i"]
        if i >= len(steps):
            return (0, 0, 0)
        base, nx, ny, t = steps[i]
        if float(env.eng.t) - float(env._drill.get("t0", 0.0)) < float(t):
            return (0, 0, 0)
        cid = next((j for j, k in enumerate(env.deck_keys)
                    if str(k).replace("_evo", "") == str(base)), None)
        if cid is None or float(env.eng.elixir[0]) < float(env.specs[cid].elixir):
            return (0, 0, 0)
        x = 1.0 - float(nx) if getattr(env, "_drill_mirrored", False) else float(nx)
        state["i"] += 1
        return (1, cid, int(env.actions.cell_at(x, float(ny))))

    return _policy


def rate(cfg, scen, steps, reps):
    good = 0
    for k in range(reps):
        # FRESH POLICY PER REP. Reusing one across reps leaves its step index exhausted after the
        # first episode, so every later rep plays nothing -- which read as a 0% baseline on lines
        # the report scores at 40%.
        pol = line_policy(steps)
        env = DrillEnv(cfg, scen, seed=6000 + k, level=None)
        obs = env.reset()
        done, info = False, {}
        while not done:
            obs, _r, done, info = env.step(pol(obs, env))
        good += 1 if (info or {}).get("verdict") == "pass" else 0
    return 100.0 * good / reps


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "nado_clump_for_the_wizard"
    step_i = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    reps = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    cfg = Config.load(os.path.join(HERE, "..", "config", "config.yaml"))
    sc.load_all()
    s = sc.get(name)
    steps = [list(x) for x in (s.reference or ())]
    if not steps:
        print("%s has no reference line" % name)
        return
    base, x0, y0, t0 = steps[step_i]
    print("%s  step %d = %s at (%.3f, %.3f) t=%.1f" % (name, step_i, base, x0, y0, t0))
    print("baseline (current line): %.0f%%" % rate(cfg, s, [tuple(x) for x in steps], reps))
    print("")
    print("%-28s %s" % ("candidate", "pass%"))
    print("-" * 40)
    best = []
    for dy in (-0.08, -0.04, 0.0, 0.04, 0.08):
        for dx in (-0.06, 0.0, 0.06):
            for t in sorted({0.0, max(0.0, t0 - 0.6), t0, t0 + 0.6}):
                cand = [list(v) for v in steps]
                cand[step_i] = [base, round(x0 + dx, 3), round(y0 + dy, 3), t]
                r = rate(cfg, s, [tuple(v) for v in cand], reps)
                best.append((r, cand[step_i][1], cand[step_i][2], t))
    best.sort(reverse=True)
    for r, x, y, t in best[:12]:
        print("  x=%.3f y=%.3f t=%.1f      %5.0f%%" % (x, y, t, r))


if __name__ == "__main__":
    main()
