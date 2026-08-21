"""What should a drill's thresholds BE? Measure the board instead of guessing.

    python tools/drill_calibrate.py <drill> [reps]

A drill's success/failure numbers are claims about the board: "a correct answer holds this under
X". Every one of them was tuned against LEVEL 11 enemies, and drills now roll the ladder levels the
full sim uses (13-16, mean ~14.1) -- +32% HP and +32% damage. Several thresholds became
unreachable, and their reference lines went to 0%.

This runs the drill's own two extremes with the predicates STRIPPED, so nothing ends early and the
interaction plays out in full:

    IGNORED     do nothing -- what the threat costs unanswered
    REFERENCE   the drill's hand-written correct line

and reports each arm's tower damage, spend, and enemy survival. A threshold belongs in the GAP
between the two distributions; if there is no gap, the drill is not separating the play from the
board and the scenario itself needs rethinking, not a new number.

This is the tool that found `skeletons_kill_the_miner` was asking for negation from a card that
mitigates: ignored 401 HP, answered 217, so its "under 350" bar was unreachable and its 0% was
never about the policy.
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim import scenarios as sc                 # noqa: E402
from clashrl.sim.drill_env import DrillEnv, scripted_policy   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def arm(cfg, scen, ref_scen, policy, reps, horizon):
    lost, spent, alive, spawned = [], [], 0, 0
    for k in range(reps):
        env = DrillEnv(cfg, scen, seed=6000 + k, level=None)   # ladder roll, as training does
        obs = env.reset()
        hp0 = sum(float(t.hp) for t in env.eng.towers[0][:2])
        pol = policy() if callable(policy) else None
        done, saw = False, False
        while not done:
            a = pol(obs, env) if pol else (0, 0, 0)
            obs, _r, done, _i = env.step(a)
            if any(u.team == 1 for u in env.eng.units):
                saw = True
        lost.append(hp0 - sum(float(t.hp) for t in env.eng.towers[0][:2]))
        spent.append(float(env._drill.get("spent", 0.0)))
        alive += 1 if any(u.team == 1 and u.hp > 0 for u in env.eng.units) else 0
        spawned += 1 if saw else 0
    lost.sort()
    n = len(lost)
    return {"mean": sum(lost) / n, "min": lost[0], "max": lost[-1],
            "p25": lost[n // 4], "p75": lost[(3 * n) // 4],
            "spent": sum(spent) / n, "alive": alive, "n": n, "spawned": spawned}


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "skeletons_stop_the_wall_breakers"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    cfg = Config.load(os.path.join(HERE, "..", "config", "config.yaml"))
    sc.load_all()
    base = sc.get(name)
    horizon = max(14.0, float(base.time_limit))
    open_s = dataclasses.replace(base, success=lambda e, s: False, failure=lambda e, s: False,
                                 time_limit=horizon)
    print("%s   (%d reps, ladder levels, predicates stripped, %.0fs horizon)"
          % (name, reps, horizon))
    print("%-11s %9s %9s %9s %9s %9s %8s %8s" % ("arm", "mean", "min", "p25", "p75", "max",
                                                 "spent", "enemy alive"))
    print("-" * 84)
    rows = {}
    for label, pol in (("IGNORED", None),
                       ("REFERENCE", (lambda: scripted_policy(base)))):
        r = arm(cfg, open_s, base, pol, reps, horizon)
        rows[label] = r
        print("%-11s %9.1f %9.1f %9.1f %9.1f %9.1f %8.1f %6d/%d"
              % (label, r["mean"], r["min"], r["p25"], r["p75"], r["max"], r["spent"],
                 r["alive"], r["n"]))
    a, b = rows["IGNORED"], rows["REFERENCE"]
    print("")
    if b["max"] < a["min"]:
        mid = (b["max"] + a["min"]) / 2.0
        print("CLEAN SEPARATION: reference tops out at %.0f, ignored bottoms out at %.0f."
              % (b["max"], a["min"]))
        print("  -> a success bar near %.0f cannot be met by doing nothing, and the correct line "
              "always clears it." % mid)
    else:
        print("OVERLAP: reference reaches %.0f and ignored can be as low as %.0f, so no single HP "
              "bar separates the play from the board." % (b["max"], a["min"]))
        print("  -> the scenario needs rethinking (deeper spawn, longer horizon, different card), "
              "not a new number.")
    print("MITIGATION: %.0f HP for %.1f elixir" % (a["mean"] - b["mean"], b["spent"]))


if __name__ == "__main__":
    main()
