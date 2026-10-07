import json, numpy as np
H = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_counter/"
R = json.load(open(H + "results.json")); S1 = json.load(open(H + "step1.json")); Cj = json.load(open(H + "C_set.json"))
def f(t, pct=True):
    if t is None or t[0] is None: return "n/a"
    g = (lambda v: f"{100*v:.1f}%") if pct else (lambda v: f"{v:.2f}")
    return f"{g(t[0])} [{g(t[1])},{g(t[2])}]" + (f" n={int(t[4])}" if len(t) > 4 else "")
def d(t, pct=True):
    if t is None or t[0] is None: return "n/a"
    g = (lambda v: f"{100*v:+.1f}pp") if pct else (lambda v: f"{v:+.2f}")
    return f"{g(t[0])} [{g(t[1])},{g(t[2])}]"
print("C sets", json.dumps(Cj["C_main"]), json.dumps(Cj["C_wide"]), json.dumps(Cj["C_emp"]))
print("STEP1 base fail", f(S1["base_fail"]), "n", S1["n_inst"])
for w in S1["windows"]:
    W = S1["windows"][w]; print("window", w, "tested", W["n_cards_tested"], "sig+", W["n_sig_pos"], "sig-", W["n_sig_neg"])
    for k, v in W["classes"].items(): print("   class", k, "n", v["n_exposed"], f(v["fail_exposed"]), "vs", f(v["fail_unexposed"]), "diff", d(v["diff"]))
for r in S1["windows"]["post10s"]["ranked"]: print("   ", r["card"], r["n_exposed"], f(r["fail_exposed"]), "diff", d(r["diff_vs_unexposed"]), "dmg", round(r["mean_dmg_frac_exposed"], 3))
print(json.dumps(R["pros_rows"]), json.dumps(R.get("model_rows")))
for sname in R["step2_pros"]:
    S = R["step2_pros"][sname]; print("== STEP2 pros", sname, "A1 share", f(S["A1_share_of_eligible_rows"]))
    for out in ("offX", "defX", "anyX"):
        T = S["all_splits"][out]
        for ph in ("1x", "2x", "OT", "all"): print("  ", out, ph, "A1", f(T[ph + "|A1"]), "| A2", f(T[ph + "|A2"]), "| A0k", f(T[ph + "|A0k"]), "| A0u", f(T[ph + "|A0u"]), "| notA1", f(T[ph + "|notA1"]))
        print("  ", out, "stddiff", d(T["std_diff(A1-notA1)"]), "MH RR", np.round(T["MH_RR(A1/notA1)"], 2))
    T = S["val_split"]["offX"]; print("   VAL offX A1", f(T["all|A1"]), "notA1", f(T["all|notA1"]), "stddiff", d(T["std_diff(A1-notA1)"]), "RR", np.round(T["MH_RR(A1/notA1)"], 2))
for sname in R.get("step2_model_val", {}):
    print("== STEP2 model (val)", sname)
    for lab, T in R["step2_model_val"][sname].items():
        print("  ", lab, "A1", f(T["all|A1"]), "notA1", f(T["all|notA1"]), "|1x", f(T["1x|A1"]), f(T["1x|notA1"]), "|2x", f(T["2x|A1"]), f(T["2x|notA1"]), "|OT", f(T["OT|A1"]), f(T["OT|notA1"]), "| stddiff", d(T["std_diff(A1-notA1)"]), "RR", np.round(T["MH_RR(A1/notA1)"], 2))
for src in ("pros", "bot"):
    for sname, T in R["step3"][src].items():
        print("== STEP3", src, sname, "share A1", f(T["share_A1"]), {k: f(v) for k, v in T["share_status"].items()})
        for grp in ("A1", "notA1", "A2", "A0k", "A0u"):
            g = T[grp]; print("   ", grp, "n", g["n"], "fail", f(g["fail"]), "dmg", f(g["dmg_frac"]), "own30", f(g["own_dmg30"]), "lost30", f(g["own_tower_lost30"]))
        print("    diff A1-notA1", {k: d(v, pct=True) for k, v in T["diff_A1_minus_notA1"].items()}, "std fail", d(T["std_diff_fail"]), "| vs A0k(all 8 seen, no C in hand):", {k: d(v) for k, v in T["diff_A1_minus_A0k"].items()}, "std fail vs A0k", d(T["std_diff_fail_vs_A0k"]))
print("pros-bot share A1", {k: d(v) for k, v in R["step3"]["pros_minus_bot_share_A1"].items()})
for k, v in R["step3_pros_crossfit"].items(): print("crossfit", k, v["n_A1"], v["n_notA1"], f(v["fail_A1"]), f(v["fail_notA1"]), d(v["diff"]))
print("reader acc", json.dumps(R["reader_accuracy_pros"]))
for sname, T in R["step3b_bot_opportunity"].items():
    print("== STEP3b bot", sname, {k: f(v, pct=False) for k, v in T.items() if "|" in k and "std" not in k}, "stddiff/min", d(T["std_diff_per_min(A1-notA1)"], pct=False), "MH RR", np.round(T["MH_RR_per_min(A1/notA1)"], 2), "opp-min share A1", f(T["share_of_opportunity_minutes_A1"]))
for src in ("pros", "bot"):
    print("== STEP4", src, "no-lock share", {k: f(v) for k, v in R["step4"][src]["nolock_share"].items()})
    for nl in ("dmg==0", "dmg<1%", "dmg<5%"):
        for k, d_ in R["step4"][src][nl].items():
            print("  ", nl, k, "nolock all/commit", d_["n_nolock_all"], d_["n_nolock_committed"], "| spend nolock", f(d_["spend_nolock_mean"], pct=False), "lock", f(d_["spend_lock_mean"], pct=False), "| P>=4", f(d_["P(spend>=4)_nolock"]), "vs lock", f(d_["P(spend>=4)_lock"]))
            print("       buckets own_dmg30:", {b: (v["n"], f(v["own_dmg30"]).split(" n=")[0], f(v["own_tower_lost30"]).split(" n=")[0]) for b, v in d_["buckets_nolock"].items()}, "diff(>=4 - <4)", d(d_["own_dmg30_diff(spend>=4 - <4)"]), "lost", d(d_["own_tower_lost30_diff(spend>=4 - <4)"]))
print("pros-bot spend", {k: d(v, pct=False) for k, v in R["step4"]["pros_minus_bot_spend"].items()})
print("STEP5", json.dumps(R["step5_counts"], indent=0))
