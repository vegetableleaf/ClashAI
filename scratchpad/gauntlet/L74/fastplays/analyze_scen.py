"""L74 fastplays: designed Rocket + Tornado scenarios.
    python analyze_scen.py sweep SWEEP.jsonl            the forced-timing curves (scenarios.py sweep)
    python analyze_scen.py model DIR [DIR ...]          the model's own plays (scenario_model.py), one DIR per arm
    python analyze_scen.py lines DIR                    one line per model run (debug)
Sweep: per scenario, the Rocket flight (deploy -> impact, measured), the lone Rocket's group damage, and the combo's group damage
by GAP = Tornado deploy - Rocket deploy; the window = gaps whose damage >= 1.5 x lone (and >= 80 % of the best combo); the rule's
window (decision_options.rocket_tornado_plan: [max(4, F - 33), F - 12] with F its flight model) and where each mechanism's
earliest Tornado lands: SIM fast OFF 30 ticks (the pending lock, decide_every grid), live OFF ~27 (confirmation ~25 + a frame),
fast ON / follow-up 2-4."""
import collections
import json
import statistics
import sys
from pathlib import Path


def load(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]


def sweep(path):
    rs = load(path)
    by = collections.defaultdict(list)
    for r in rs:
        by[r["scenario"]].append(r)
    print("scenario      flight(meas/rule)  lone dmg  best combo (gap)   window (>=1.5x lone & >=80% best)   rule window  "
          "OFF@30   ON@2-4")
    for name, xs in by.items():
        lone = [x for x in xs if x["gap"] is None]
        combo = [x for x in xs if x["gap"] is not None and x.get("impact_tick")]
        ld = statistics.mean(x.get("group_hp_drop_at_impact", 0) for x in lone)
        fl = statistics.mean(x["impact_tick"] - x["rocket"][0] for x in lone)
        fr = statistics.mean(x["flight_rule"] for x in lone)
        g = collections.defaultdict(list)
        for x in combo:
            g[x["gap"]].append(x.get("group_hp_drop_at_impact", 0))
        curve = {k: statistics.mean(v) for k, v in sorted(g.items())}
        best_gap = max(curve, key=curve.get)
        best = curve[best_gap]
        pre = {x["gap"] for x in combo if (x.get("impact_minus_tornado_deploy") or -1) >= 0}   # Tornado started before the impact
        win = [k for k, v in curve.items() if k in pre and v >= 1.5 * ld and v >= 0.8 * best]
        F = round(fr)
        rule = (max(4, F - 33), F - 12)
        at = lambda k: curve.get(k, float("nan"))        # noqa: E731
        print(f"{name:13s} {fl:5.1f} / {fr:5.1f}      {ld:6.0f}    {best:6.0f} ({best_gap:+d})     "
              f"{(min(win), max(win)) if win else None}  {len(win)} gaps        {rule}   "
              f"{at(30):6.0f}   {statistics.mean([at(2), at(4)]):6.0f}")
    print("\ncurves (group hp lost at the Rocket's impact, mean of both sides; gap step 4 shown):")
    for name, xs in by.items():
        g = collections.defaultdict(list)
        for x in xs:
            if x["gap"] is not None and x.get("impact_tick"):
                g[x["gap"]].append((x.get("group_hp_drop_at_impact", 0), x.get("impact_minus_tornado_deploy")))
        print(f"  {name:13s} " + " ".join(f"{k:+d}:{statistics.mean(v[0] for v in vs):.0f}" for k, vs in sorted(g.items()) if k % 4 == 0))
        print(f"  {'':13s} impact - Tornado deploy at gap 0: {g[0][0][1] if g.get(0) else None}; group hp0 {xs[0]['group_hp0']}")


def model_rows(d):
    rs = [r for r in load(Path(d) / "matches.jsonl") if r.get("skipped") == "scenario"]
    return rs


def run_line(r):
    ps = " ".join(f"{p['card'][:7]}@{p['land'] - r['T0'] - 26}{'' if p['acc'] else 'x'}({p['xy'][0]:.0f},{p['xy'][1]:.0f}){p['why'][0]}"
                  for p in r["plays"][:5])
    rk = " ".join(f"R{x.get('group_hp_drop', 0)}h{x.get('hit')}k{x.get('killed')}" for x in r["rockets"])
    return f"{r['scenario']:12s} T0 {r['T0']} L{r['learner_side']} | {ps} | {rk}"


def model(dirs):
    print("arm   scenario      n  rocket%  tornado%  R+T%  T-after-R gap (median, range)  rule%  R dmg mean  combo dmg  "
          "lone dmg   T before R")
    for d in dirs:
        rs = model_rows(d)
        by = collections.defaultdict(list)
        for r in rs:
            by[r["scenario"]].append(r)
        for name, xs in by.items():
            n = len(xs)
            rk = tor = both = rule = tfirst = 0
            gaps, cd, ld, rd = [], [], [], []
            for r in xs:
                ps = [p for p in r["plays"] if p["acc"]]
                R = next((p for p in ps if p["card"] == "rocket"), None)
                T = next((p for p in ps if p["card"] == "tornado"), None)
                rk += R is not None
                tor += T is not None
                if R:
                    dmg = r["rockets"][0].get("group_hp_drop", 0) if r["rockets"] else 0
                    rd.append(dmg)
                    rule += R["why"] == "rocket_tornado"
                if R and T:
                    both += 1
                    if T["land"] >= R["land"]:                 # deploy order (a follow-up records the first decision tick)
                        gaps.append(T["land"] - R["land"])
                        cd.append(r["rockets"][0].get("group_hp_drop", 0) if r["rockets"] else 0)
                    else:
                        tfirst += 1
                elif R:
                    ld.append(r["rockets"][0].get("group_hp_drop", 0) if r["rockets"] else 0)
            gs = sorted(gaps)
            m = lambda v: f"{statistics.mean(v):6.0f}" if v else "     -"   # noqa: E731
            print(f"{Path(d).name:5s} {name:13s} {n:2d}  {100 * rk / n:5.0f}   {100 * tor / n:5.0f}   {100 * both / n:4.0f}  "
                  f"{str((gs[len(gs) // 2], gs[0], gs[-1])) if gs else '-':>18}           {100 * rule / n:4.0f}  {m(rd)}      {m(cd)}    "
                  f"{m(ld)}    {tfirst}")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "sweep":
        sweep(sys.argv[2])
    elif mode == "model":
        model(sys.argv[2:])
    else:
        for r in model_rows(sys.argv[2]):
            print(run_line(r))
