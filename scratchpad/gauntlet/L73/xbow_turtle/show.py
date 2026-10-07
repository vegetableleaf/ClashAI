import json
R = json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_turtle/results.json"))
PCT = {"defShare(X)", "shareRocket", "shareXbow", "shareOther", "rocketMain(>50%)", "fracTime>=9.9el"}
def f(k, v): return "  n/a  " if v is None else (f"{100*v:5.1f}%" if k in PCT else f"{v:6.3f}")
def fc(k, c): return "[n/a]" if c[0] is None else f"[{f(k, c[0]).strip()},{f(k, c[1]).strip()}]"
def tab(e, title):
    if not e: print("  ", title, "n/a"); return
    print(f"  -- {title}  nA={e['_n']['A']} nB={e['_n']['B']} coverage={100*e['_n']['coverage_of_A']:.0f}%")
    for k, v in e.items():
        if k == "_n": continue
        print(f"     {k:18s} A {f(k, v['A'])}  B {f(k, v['B'])}  diff {f(k, v['diff'])} {fc(k, v['ci'])}")
for ds in ("pros_all", "pros_engine_agrees", "bot"):
    D = R[ds]; print("=" * 20, ds, "sides", D["n_sides"])
    for spec in ("K1", "K2", "K1_strict(0dmg_vs_>=25%)", "K1_level0-0", "K2_level0-0"):
        S = D[spec]; print(f"## {spec} n={S['n_by_group']} median t_K s={S['sec_median_by_group']} drop={S['drop']}")
        for comp in [k for k in S if "-" in k and k not in ("drop",)]:
            for ph in ("all", "1x", "2x", "OT"): tab(S[comp][ph], f"{comp} | {ph} (time-stratified)")
            print("     raw unstratified diff: " + "; ".join(f"{k} {f(k, v['diff'])} {fc(k, v['ci'])}" for k, v in S[comp]["raw_unstratified"].items()))
        if "learnability" in S: print("   learnability", S["learnability"])
    print("## DiD", D["DiD"]["n_by_group"])
    for ph in ("all", "1x", "2x", "OT"): tab(D["DiD"][ph], f"DiD (after-before)fail - (after-before)ok | {ph}")
    for g, lv in D["DiD"]["levels_unstratified"].items():
        print("   ", g, "before", {k: round(v, 3) for k, v in lv["before"].items()}); print("   ", g, "after ", {k: round(v, 3) for k, v in lv["after"].items()})
print("=" * 20, "pro - bot (K matched fail-ok effect)")
for spec, d in R["pro_minus_bot_effect"].items():
    for k, v in d.items(): print(f"  {spec} {k:18s} pro {f(k, v['pro'])} bot {f(k, v['bot'])} pro-bot {f(k, v['pro-bot'])} {fc(k, v['ci'])}")
print(R["meta"])
