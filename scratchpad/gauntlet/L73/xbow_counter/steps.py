"""Steps 2-5 of the X-Bow-into-counter study. Public-only availability (opp_cycle plays_since>=4 + public elixir estimate)."""
import pickle, json, collections, math, os
import numpy as np
import common as C
A = C.A
OUT = {}
P, Bt, XP, XB = C.load_all()
Cj = json.load(open(C.HERE + "C_set.json"))
SETS = {"C_main": set(Cj["C_main"]), "C_wide": set(Cj["C_wide"]), "C_emp": set(Cj["C_emp"])}
R = pickle.load(open(C.HERE + "rows.pkl", "rb")); CV = R["CV"]; CVn = [C.norm(c) if c != "<pad>" else "" for c in CV]; XBi = CV.index("x-bow")
op = pickle.load(open(C.HERE + "opp_pros.pkl", "rb")); ob = pickle.load(open(C.HERE + "opp_bot.pkl", "rb")); bs = pickle.load(open(C.HERE + "bot_states.pkl", "rb"))
OWNCOST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
PH = lambda sec: "1x" if sec < 120 else ("2x" if sec < 180 else "OT")
UP = list(dict.fromkeys(M["cluster"] for M in P)); UB = list(dict.fromkeys(M["cluster"] for M in Bt))
MP = {M["id"]: M for M in P}
inv = {"Skeletons": "skeletons", "IceWizard": "ice-wizard", "Knight": "knight", "Log": "the-log", "Tesla": "tesla", "Xbow": "x-bow", "Tornado": "tornado", "Rocket": "rocket"}
# ---- join pros records <-> npz rows by the first six (tick, card) plays
g = np.flatnonzero(R["y_gate"] == 1); sig = {}
for i in g: sig.setdefault((int(R["rep"][i]), int(R["side"][i])), []).append((int(R["tick"][i]), CV[int(R["y_card"][i])]))
sigidx = {tuple(v[:6]): k for k, v in sig.items()}
rs_of = {M["id"]: sigidx[tuple((p["tick"], inv[p["name"]]) for p in M["plays"][:6])] for M in P}
key = R["rep"].astype(np.int64) * 2 + R["side"]; order = np.argsort(key, kind="stable"); ks = key[order]
rows_of = {}
for M in P:
    rp, sd = rs_of[M["id"]]; k = rp * 2 + sd; a, b = np.searchsorted(ks, [k, k + 1]); rows_of[M["id"]] = np.sort(order[a:b])
el_int = np.floor(R["sc"][:, 0] * 10 + 1e-3); est_pub = R["sc"][:, 1] * 10
def row_cyc(i): oc = R["opp_cycle"][i]; return [(CVn[int(c)], int(ps)) for c, ps in zip(oc[:, 0], oc[:, 2]) if int(c) > 0]
def xb_tmap(M):
    return {int(R["tick"][i]): int(i) for i in rows_of[M["id"]] if R["y_gate"][i] == 1 and int(R["y_card"][i]) == XBi}

# ================= pros row table (X-Bow in hand & affordable)
xb_in = (R["hand_card"] == XBi).any(1) & (el_int >= 6)
rowinfo = {}
for M in P:
    xr = {r["tick"]: r for r in XP[M["id"]]}
    for i in rows_of[M["id"]]:
        if not xb_in[i]: continue
        cyc = row_cyc(i); e = float(est_pub[i]); t = int(R["tick"][i])
        play = bool(R["y_gate"][i] == 1 and int(R["y_card"][i]) == XBi)
        cls = xr[t]["cls"] if play and t in xr else None
        rowinfo[int(i)] = {"id": M["id"], "c": M["cluster"], "ph": PH(t / 20.0), "split": int(R["split"][i]), "play": play, "cls": cls,
                           "g": {k: C.avail(cyc, e, S)["group"] for k, S in SETS.items()}, "st": C.avail(cyc, e, SETS["C_main"])["status"]}
print("pros X-Bow-eligible rows", len(rowinfo), "x-bow play rows", sum(v["play"] for v in rowinfo.values()), "unmatched play", sum(v["play"] and v["cls"] is None for v in rowinfo.values()), flush=True)
OUT["pros_rows"] = {"eligible": len(rowinfo), "xbow_play_rows": sum(v["play"] for v in rowinfo.values()), "play_rows_unmatched_to_instance": sum(v["play"] and v["cls"] is None for v in rowinfo.values()),
                    "status_share(C_main)": dict(collections.Counter(v["st"] for v in rowinfo.values()))}
def row_contrast(infos, U, sname, outc):
    res = {}
    for ph in ("1x", "2x", "OT", "all"):
        for grp, f in (("A1", lambda v: v["g"][sname] == "A1"), ("A2", lambda v: v["g"][sname] == "A2"), ("A0k", lambda v: v["g"][sname] == "A0k"),
                       ("A0u", lambda v: v["g"][sname] == "A0u"), ("notA1", lambda v: v["g"][sname] != "A1")):
            res[f"{ph}|{grp}"] = C.rci(U, [(v["c"], outc(v), 1) for v in infos if (ph == "all" or v["ph"] == ph) and f(v)])
    ra = [(v["c"], v["ph"], outc(v), 1) for v in infos if v["g"][sname] == "A1"]; rb = [(v["c"], v["ph"], outc(v), 1) for v in infos if v["g"][sname] != "A1"]
    res["std_diff(A1-notA1)"] = C.std_diff(U, ra, rb, None)
    res["MH_RR(A1/notA1)"] = C.mh_rr(U, ra, rb)
    return res
S2 = {}
allinfo = list(rowinfo.values()); valinfo = [v for v in allinfo if v["split"] == 1]
for sname in SETS:
    S2[sname] = {"all_splits": {"offX": row_contrast(allinfo, UP, sname, lambda v: int(v["play"] and v["cls"] == "off")),
                                "defX": row_contrast(allinfo, UP, sname, lambda v: int(v["play"] and v["cls"] == "def")),
                                "anyX": row_contrast(allinfo, UP, sname, lambda v: int(v["play"]))},
                 "val_split": {"offX": row_contrast(valinfo, UP, sname, lambda v: int(v["play"] and v["cls"] == "off"))},
                 "A1_share_of_eligible_rows": C.rci(UP, [(v["c"], int(v["g"][sname] == "A1"), 1) for v in allinfo])}
    print("step2 pros", sname, "A1 share", C.fm(S2[sname]["A1_share_of_eligible_rows"]), "| offX|A1", C.fm(S2[sname]["all_splits"]["offX"]["all|A1"]), "| offX|notA1", C.fm(S2[sname]["all_splits"]["offX"]["all|notA1"]),
          "| std diff", np.round(S2[sname]["all_splits"]["offX"]["std_diff(A1-notA1)"], 4), flush=True)
OUT["step2_pros"] = S2

# ================= model rows (teacher forced, VAL split)
if os.path.exists(C.HERE + "model_rows.pkl"):
    MR = pickle.load(open(C.HERE + "model_rows.pkl", "rb")); gidx = np.searchsorted(R["sel"], MR["sel"]); sub = {s: k for k, s in enumerate(MR["subsets"])}
    mv = []
    for j, i in enumerate(gidx):
        v = rowinfo.get(int(i))
        if v is None: continue
        M = MP[v["id"]]; t = int(R["tick"][i]); alive = "".join(k for k in "KLR" if A.hp_at(M, "e" + k, t) > 0)
        if not alive: continue
        om = MR["offmass"][j, sub[alive]]
        cx = 18.0 - (int(MR["argcell"][j]) % 36) / 2.0; cy = (int(MR["argcell"][j]) // 36) / 2.0
        off_arg = any(A.dist((cx, cy), A.TOWER_XY["e" + k]) <= A.REACH for k in alive)
        v = dict(v); soft = float(MR["p_play"][j] * MR["p_xb_given_play"][j])
        v["m_soft_off"] = soft * float(om); v["m_soft_any"] = soft
        v["m_live_off"] = int(MR["p_play"][j] > 0.35 and MR["argmax_is_xb"][j] and off_arg); v["m_live_any"] = int(MR["p_play"][j] > 0.35 and MR["argmax_is_xb"][j])
        mv.append(v)
    OUT["model_rows"] = {"n": len(mv), "clusters": len({v["c"] for v in mv})}
    Um = list(dict.fromkeys(v["c"] for v in mv)); S2m = {}
    for sname in SETS:
        d = {}
        for lab, f in (("pro_offX", lambda v: int(v["play"] and v["cls"] == "off")), ("model_soft_P(offX)", lambda v: v["m_soft_off"]), ("model_live(tau.35)_offX", lambda v: v["m_live_off"]),
                       ("model_soft_P(anyX)", lambda v: v["m_soft_any"]), ("model_live(tau.35)_anyX", lambda v: v["m_live_any"]), ("pro_anyX", lambda v: int(v["play"]))):
            d[lab] = row_contrast(mv, Um, sname, f)
            print("step2 model", sname, lab, "A1", C.fm(d[lab]["all|A1"], pct=True), "notA1", C.fm(d[lab]["all|notA1"]), "stddiff", np.round(d[lab]["std_diff(A1-notA1)"], 4), flush=True)
        S2m[sname] = d
    OUT["step2_model_val"] = S2m
else: print("model_rows.pkl missing -> skip model part")

# ================= instance tables (steps 3 and 4)
def own_dmg(M, death):
    end = M["end"]
    if end - death < 300: return None, None
    t1 = min(death + 600, end); den = sum(M["MX"][k] for k in ("mK", "mL", "mR"))
    drop = sum(max(0.0, A.hp_at(M, k, death) - A.hp_at(M, k, t1)) for k in ("mK", "mL", "mR"))
    lost = any(A.hp_at(M, k, death) > 0 and A.hp_at(M, k, t1) <= 0 for k in ("mK", "mL", "mR"))
    return drop / den, int(lost)
def spend(M, r, tc, mode):
    s = 0
    for p in M["plays"]:
        if not (tc < p["tick"] <= r["death"]): continue
        if p["tick"] == r["tick"] and p["name"] == "Xbow": continue
        if M["kind"] == "bot" and not p["conf"]: continue
        near = A.dist((p["x"], p["y"]), (r["x"], r["y"])) <= 7.0 if mode == "radius7" else ((p["x"] < 9) == (r["x"] < 9))
        if near: s += OWNCOST.get(p["name"], 0)
    return s
def build(Ms, X, kind):
    out = []
    for M in Ms:
        oplays = sorted(op[M["id"]]["opp"]) if kind == "pro" else sorted(ob[M["id"]]["plays"])
        tmap = xb_tmap(M) if kind == "pro" else None
        for r in X[M["id"]]:
            if r["cls"] != "off" or r["status"] not in ("fail", "ok") or r["death"] is None: continue
            if kind == "pro":
                if r["tick"] not in tmap: continue
                i = tmap[r["tick"]]; cyc = row_cyc(i); e = float(est_pub[i])
            else:
                cyc = C.cycle_from_plays(oplays, r["tick"]); e = C.est_bot(ob[M["id"]], r["tick"])
            av = {k: C.avail(cyc, e, S) for k, S in SETS.items()}
            od, lost = own_dmg(M, r["death"])
            life = [p for p in oplays if r["tick"] <= p[0] <= r["death"]]
            commit = {"D1_Cmain": next((p[0] for p in life if C.norm(p[1]) in SETS["C_main"]), None),
                      "D2_opp_cost>=4": next((p[0] for p in life if not C.is_spell(C.norm(p[1])) and (C.cost_n(C.norm(p[1])) or 0) >= 4), None)}
            inst = {"id": M["id"], "c": M["cluster"], "ph": r["ph"], "fail": int(r["status"] == "fail"), "dmg": r["dmg"], "own": od, "lost": lost, "av": av, "commit": commit, "life": (r["death"] - r["tick"]) / 20.0}
            for cn, tc in commit.items():
                for mode in ("radius7", "lane"): inst[f"spend|{cn}|{mode}"] = spend(M, r, tc, mode) if tc is not None else None
            out.append(inst)
    return out
IP = build(P, XP, "pro"); IB = build(Bt, XB, "bot")
print("instances pros", len(IP), "bot", len(IB), flush=True)
OUT["n_instances"] = {"pros": len(IP), "bot": len(IB)}
S3 = {}
for src, I, U in (("pros", IP, UP), ("bot", IB, UB)):
    S3[src] = {}
    for sname in SETS:
        d = {}
        d["share_A1"] = C.rci(U, [(i["c"], int(i["av"][sname]["group"] == "A1"), 1) for i in I])
        d["share_status"] = {s: C.rci(U, [(i["c"], int(i["av"][sname]["status"] == s), 1) for i in I]) for s in ("known", "partly", "unknown")}
        for grp, f in (("A1", lambda i: i["av"][sname]["group"] == "A1"), ("notA1", lambda i: i["av"][sname]["group"] != "A1"), ("A2", lambda i: i["av"][sname]["group"] == "A2"),
                       ("A0k", lambda i: i["av"][sname]["group"] == "A0k"), ("A0u", lambda i: i["av"][sname]["group"] == "A0u")):
            sl = [i for i in I if f(i)]
            d[grp] = {"n": len(sl), "fail": C.rci(U, [(i["c"], i["fail"], 1) for i in sl]), "dmg_frac": C.rci(U, [(i["c"], i["dmg"], 1) for i in sl]),
                      "own_dmg30": C.rci(U, [(i["c"], i["own"], 1) for i in sl if i["own"] is not None]), "own_tower_lost30": C.rci(U, [(i["c"], i["lost"], 1) for i in sl if i["own"] is not None])}
        a = [i for i in I if i["av"][sname]["group"] == "A1"]; b = [i for i in I if i["av"][sname]["group"] != "A1"]
        d["diff_A1_minus_notA1"] = {"fail": C.diff_ci(U, [(i["c"], i["fail"], 1) for i in a], [(i["c"], i["fail"], 1) for i in b]),
                                    "dmg_frac": C.diff_ci(U, [(i["c"], i["dmg"], 1) for i in a], [(i["c"], i["dmg"], 1) for i in b]),
                                    "own_dmg30": C.diff_ci(U, [(i["c"], i["own"], 1) for i in a if i["own"] is not None], [(i["c"], i["own"], 1) for i in b if i["own"] is not None]),
                                    "own_tower_lost30": C.diff_ci(U, [(i["c"], i["lost"], 1) for i in a if i["own"] is not None], [(i["c"], i["lost"], 1) for i in b if i["own"] is not None])}
        d["std_diff_fail"] = C.std_diff(U, [(i["c"], i["ph"], i["fail"], 1) for i in a], [(i["c"], i["ph"], i["fail"], 1) for i in b], None)
        k0 = [i for i in I if i["av"][sname]["group"] == "A0k"]
        d["diff_A1_minus_A0k"] = {"fail": C.diff_ci(U, [(i["c"], i["fail"], 1) for i in a], [(i["c"], i["fail"], 1) for i in k0]),
                                  "own_dmg30": C.diff_ci(U, [(i["c"], i["own"], 1) for i in a if i["own"] is not None], [(i["c"], i["own"], 1) for i in k0 if i["own"] is not None]),
                                  "own_tower_lost30": C.diff_ci(U, [(i["c"], i["lost"], 1) for i in a if i["own"] is not None], [(i["c"], i["lost"], 1) for i in k0 if i["own"] is not None])}
        d["std_diff_fail_vs_A0k"] = C.std_diff(U, [(i["c"], i["ph"], i["fail"], 1) for i in a], [(i["c"], i["ph"], i["fail"], 1) for i in k0], None)
        S3[src][sname] = d
        print("step3", src, sname, "share A1", C.fm(d["share_A1"]), "| fail A1", C.fm(d["A1"]["fail"]), "notA1", C.fm(d["notA1"]["fail"]), "diff", np.round(d["diff_A1_minus_notA1"]["fail"], 3),
              "std", np.round(d["std_diff_fail"], 3), "| own30 diff", np.round(d["diff_A1_minus_notA1"]["own_dmg30"], 4), flush=True)
S3["pros_minus_bot_share_A1"] = {s: C.indep_diff(UP, [(i["c"], int(i["av"][s]["group"] == "A1"), 1) for i in IP], UB, [(i["c"], int(i["av"][s]["group"] == "A1"), 1) for i in IB]) for s in SETS}
OUT["step3"] = S3

# cross-fit variant (C re-selected on the OTHER half of replays) for the pros fail contrast
UPs = sorted({M["cluster"] for M in P}); fold = {c: k % 2 for k, c in enumerate(UPs)}
def xfit(nm):
    a, b = [], []
    for M in P:
        tmap = xb_tmap(M); Sx = set(Cj["crossfit_selected_on_fold"][str(1 - fold[M["cluster"]])][nm])
        for r in XP[M["id"]]:
            if r["cls"] != "off" or r["status"] not in ("fail", "ok") or r["tick"] not in tmap: continue
            i = tmap[r["tick"]]; av = C.avail(row_cyc(i), float(est_pub[i]), Sx)["group"] == "A1"
            (a if av else b).append((M["cluster"], int(r["status"] == "fail"), 1))
    return {"n_A1": len(a), "n_notA1": len(b), "fail_A1": C.rci(UP, a), "fail_notA1": C.rci(UP, b), "diff": C.diff_ci(UP, a, b)}
OUT["step3_pros_crossfit"] = {nm: xfit(nm) for nm in ("C_main", "C_emp")}
for nm, v in OUT["step3_pros_crossfit"].items(): print("crossfit", nm, v["n_A1"], v["n_notA1"], C.fm(v["fail_A1"]), C.fm(v["fail_notA1"]), np.round(v["diff"], 3), flush=True)

# ---- reader accuracy (pros: true opp hand/elixir at each own X-Bow play)
acc = {}
for sname, S in SETS.items():
    tp = fp = fn = tn = 0
    for M in P:
        tmap = xb_tmap(M)
        for t, (hand, el) in op[M["id"]]["true_at_xbow"].items():
            if t not in tmap: continue
            i = tmap[t]; pub = C.avail(row_cyc(i), float(est_pub[i]), S)["group"] == "A1"
            true = any(C.norm(h) in S and el >= (C.cost_n(C.norm(h)) or 99) for h in hand)
            tp += pub and true; fp += pub and not true; fn += (not pub) and true; tn += (not pub) and not true
    acc[sname] = {"n": tp + fp + fn + tn, "public_A1&true_A1": tp, "public_A1_only": fp, "true_A1_only": fn, "neither": tn, "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1)}
    print("reader accuracy", sname, acc[sname], flush=True)
OUT["reader_accuracy_pros"] = acc

# ================= step 3b: bot opportunity-based avoidance (offensive X-Bow plays per minute of X-Bow-in-hand-and-affordable time)
BR = []
for M in Bt:
    o = ob[M["id"]]; plays = sorted(o["plays"]); st = bs[M["id"]]; T = [s[0] for s in st]
    for k, (tick, el, hand, _) in enumerate(st):
        if hand is None or "Xbow" not in hand or math.floor(el + 1e-3) < 6: continue
        dt = (min(T[k + 1] - tick, 60) if k + 1 < len(T) else 10) / 20.0
        cyc = C.cycle_from_plays(plays, tick); e = C.est_bot(o, tick)
        BR.append({"c": M["cluster"], "ph": PH(tick / 20.0), "min": dt / 60.0, "g": {kk: C.avail(cyc, e, S)["group"] for kk, S in SETS.items()}, "play": 0})
    for r in XB[M["id"]]:
        if r["cls"] != "off": continue
        cyc = C.cycle_from_plays(plays, r["tick"]); e = C.est_bot(o, r["tick"])
        BR.append({"c": M["cluster"], "ph": PH(r["tick"] / 20.0), "min": 0.0, "g": {kk: C.avail(cyc, e, S)["group"] for kk, S in SETS.items()}, "play": 1})
S3b = {}
for sname in SETS:
    d = {}
    for ph in ("1x", "2x", "OT", "all"):
        for grp, f in (("A1", lambda v: v["g"][sname] == "A1"), ("notA1", lambda v: v["g"][sname] != "A1")):
            d[f"{ph}|{grp}"] = C.rci(UB, [(v["c"], v["play"], v["min"]) for v in BR if (ph == "all" or v["ph"] == ph) and f(v)])
    d["std_diff_per_min(A1-notA1)"] = C.std_diff(UB, [(v["c"], v["ph"], v["play"], v["min"]) for v in BR if v["g"][sname] == "A1"], [(v["c"], v["ph"], v["play"], v["min"]) for v in BR if v["g"][sname] != "A1"], None)
    d["MH_RR_per_min(A1/notA1)"] = C.mh_rr(UB, [(v["c"], v["ph"], v["play"], v["min"]) for v in BR if v["g"][sname] == "A1"], [(v["c"], v["ph"], v["play"], v["min"]) for v in BR if v["g"][sname] != "A1"])
    d["share_of_opportunity_minutes_A1"] = C.rci(UB, [(v["c"], v["min"] if v["g"][sname] == "A1" else 0.0, v["min"]) for v in BR])
    S3b[sname] = d
    print("step3b bot", sname, "offX/opp-min A1", C.fm(d["all|A1"], pct=False), "notA1", C.fm(d["all|notA1"], pct=False), "std diff", np.round(d["std_diff_per_min(A1-notA1)"], 3), "opp-min share A1", C.fm(d["share_of_opportunity_minutes_A1"]), flush=True)
OUT["step3b_bot_opportunity"] = S3b

# ================= step 4: abandonment
NL = {"dmg==0": lambda i: i["dmg"] <= 1e-9, "dmg<1%": lambda i: i["dmg"] < 0.01, "dmg<5%": lambda i: i["dmg"] < 0.05}
BUCK = [("0", lambda s: s == 0), ("1-3", lambda s: 1 <= s <= 3), ("4-6", lambda s: 4 <= s <= 6), ("7+", lambda s: s >= 7)]
S4 = {}
for src, I, U in (("pros", IP, UP), ("bot", IB, UB)):
    S4[src] = {}
    for nl, nlf in NL.items():
        S4[src][nl] = {}
        for cn in ("D1_Cmain", "D2_opp_cost>=4"):
            for mode in ("radius7", "lane"):
                col = f"spend|{cn}|{mode}"
                nolock = [i for i in I if nlf(i) and i[col] is not None]; lock = [i for i in I if (not nlf(i)) and i[col] is not None]
                d = {"n_nolock_committed": len(nolock), "n_nolock_all": sum(1 for i in I if nlf(i)), "n_lock_committed": len(lock),
                     "spend_nolock_mean": C.rci(U, [(i["c"], i[col], 1) for i in nolock]), "spend_lock_mean": C.rci(U, [(i["c"], i[col], 1) for i in lock]),
                     "P(spend>=4)_nolock": C.rci(U, [(i["c"], int(i[col] >= 4), 1) for i in nolock]), "P(spend>=4)_lock": C.rci(U, [(i["c"], int(i[col] >= 4), 1) for i in lock])}
                bk = {}
                for bn, bf in BUCK:
                    sl = [i for i in nolock if bf(i[col]) and i["own"] is not None]
                    bk[bn] = {"n": len(sl), "own_dmg30": C.rci(U, [(i["c"], i["own"], 1) for i in sl]), "own_tower_lost30": C.rci(U, [(i["c"], i["lost"], 1) for i in sl])}
                d["buckets_nolock"] = bk
                hi = [i for i in nolock if i[col] >= 4 and i["own"] is not None]; lo = [i for i in nolock if i[col] < 4 and i["own"] is not None]
                d["own_dmg30_diff(spend>=4 - <4)"] = C.diff_ci(U, [(i["c"], i["own"], 1) for i in hi], [(i["c"], i["own"], 1) for i in lo])
                d["own_tower_lost30_diff(spend>=4 - <4)"] = C.diff_ci(U, [(i["c"], i["lost"], 1) for i in hi], [(i["c"], i["lost"], 1) for i in lo])
                S4[src][nl][f"{cn}|{mode}"] = d
    S4[src]["nolock_share"] = {nl: C.rci(U, [(i["c"], int(nlf(i)), 1) for i in I]) for nl, nlf in NL.items()}
S4["pros_minus_bot_spend"] = {}
for nl, nlf in NL.items():
    for cn in ("D1_Cmain", "D2_opp_cost>=4"):
        col = f"spend|{cn}|radius7"
        a = [(i["c"], i[col], 1) for i in IP if nlf(i) and i[col] is not None]; b = [(i["c"], i[col], 1) for i in IB if nlf(i) and i[col] is not None]
        S4["pros_minus_bot_spend"][f"{nl}|{cn}"] = C.indep_diff(UP, a, UB, b)
OUT["step4"] = S4
for src in ("pros", "bot"):
    for nl in NL:
        d = S4[src][nl]["D1_Cmain|radius7"]
        print("step4", src, nl, "nolock n(all/commit)", d["n_nolock_all"], d["n_nolock_committed"], "spend", C.fm(d["spend_nolock_mean"], pct=False), "lock-spend", C.fm(d["spend_lock_mean"], pct=False),
              "P>=4", C.fm(d["P(spend>=4)_nolock"]), "| own30 by bucket", {k: (v["n"], round(v["own_dmg30"][0], 3) if v["own_dmg30"][0] is not None else None) for k, v in d["buckets_nolock"].items()}, flush=True)

# ================= step 5 counts
cnt = {"pros": {"matches": len(P), "xbow_eligible_rows": len(rowinfo), "xbow_eligible_rows_by_phase": dict(collections.Counter(v["ph"] for v in rowinfo.values())),
                "offensive_xbow_play_rows": sum(1 for v in rowinfo.values() if v["play"] and v["cls"] == "off"), "resolved_offensive_xbow_instances": len(IP)},
       "bot": {"matches": len(Bt), "resolved_offensive_xbow_instances": len(IB), "opportunity_records": len(BR)}}
for sname in SETS:
    cnt["pros"][sname] = {"eligible_rows_A1": sum(1 for v in rowinfo.values() if v["g"][sname] == "A1"), "eligible_rows_A1_by_phase": dict(collections.Counter(v["ph"] for v in rowinfo.values() if v["g"][sname] == "A1")),
                          "offX_plays_into_A1": sum(1 for v in rowinfo.values() if v["g"][sname] == "A1" and v["play"] and v["cls"] == "off"),
                          "offX_plays_not_A1": sum(1 for v in rowinfo.values() if v["g"][sname] != "A1" and v["play"] and v["cls"] == "off"),
                          "resolved_inst_A1": sum(1 for i in IP if i["av"][sname]["group"] == "A1"), "resolved_inst_A1_failed": sum(1 for i in IP if i["av"][sname]["group"] == "A1" and i["fail"]),
                          "val_rows_A1": sum(1 for v in valinfo if v["g"][sname] == "A1")}
    cnt["bot"][sname] = {"resolved_inst_A1": sum(1 for i in IB if i["av"][sname]["group"] == "A1"), "resolved_inst_A1_failed": sum(1 for i in IB if i["av"][sname]["group"] == "A1" and i["fail"])}
for nl in NL:
    for src, I in (("pros", IP), ("bot", IB)):
        cnt[src][f"nolock[{nl}]"] = {"total": sum(1 for i in I if NL[nl](i)), "with_C_commit": sum(1 for i in I if NL[nl](i) and i["spend|D1_Cmain|radius7"] is not None),
                                      "with_C_commit_and_support>=4": sum(1 for i in I if NL[nl](i) and i["spend|D1_Cmain|radius7"] is not None and i["spend|D1_Cmain|radius7"] >= 4),
                                      "with_oppcost4_commit": sum(1 for i in I if NL[nl](i) and i["spend|D2_opp_cost>=4|radius7"] is not None)}
OUT["step5_counts"] = cnt
json.dump(OUT, open(C.HERE + "results.json", "w"), indent=1, default=str); print("saved")
