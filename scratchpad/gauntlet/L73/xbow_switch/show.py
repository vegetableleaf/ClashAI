import json, sys
R = json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch/results.json"))
def f(t, pct=True):
    if t is None or t[0] is None: return "n/a"
    if pct: return f"{100*t[0]:.0f}% [{100*t[1]:.0f},{100*t[2]:.0f}] n={int(t[4])}"
    return f"{t[0]:.2f} [{t[1]:.2f},{t[2]:.2f}] n={int(t[4])}"
S = sys.argv[1:] or ["pros_all", "bot"]
print(json.dumps(R["meta"]))
for s in S:
    r = R[s]; print("=====", s, r["n_matches"], "RD", r["RD"]); print(r["xbow_counts"])
    print("Q1")
    for k, v in r["q1"].items(): print(" ", k, "events", v["n_events"], "next_exists", f(v["p_next_exists"]), "| def|next", f(v["p_def_given_next"]), "| off|next", f(v["p_off_given_next"]))
    print("Q2")
    for k, v in r["q2"].items(): print(" ", k, f(v))
    print("Q3")
    for k, v in r["q3"].items(): print(" ", k, f(v, pct=not (("per_" in k) or ("rockets_total" in k))))
    print("Q4")
    for k, v in r["q4"].items():
        if k == "match_outcome_by_first_failure_response":
            for kk, vv in v.items(): print("   OUT", kk, vv["n"], {a: f(b) for a, b in vv.items() if a != "n"})
        else: print(" ", k, v["n"], {a: (f(b) if isinstance(b, list) else b) for a, b in v.items() if a != "n"})
    print("baseline", {k: f(v) for k, v in r["baseline"].items()}); print("Q5", r["q5_counts"])
