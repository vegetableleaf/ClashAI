"""Rocket gap + lead-protection gap: pros vs live model (teacher-forced) vs bot live. CPU only. Reuses xbow_counter/xbow_switch tooling read-only."""
import sys, pickle, json, math, collections, os
import numpy as np
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_counter")
import common as C
A = C.A
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/rocket_lead/"; XC = C.HERE
B = 2000; RNG = np.random.default_rng(5)
OUT = {}
P, Bt, XP, XB = C.load_all()
hands = pickle.load(open(HERE + "hands_pros.pkl", "rb")); bs = pickle.load(open(XC + "bot_states.pkl", "rb"))
PHN = ["1x", "2x", "OT"]; CDN = ["ahead", "level", "behind"]; HLN = ["deficit(<-10%)", "even", "lead(>+10%)"]
def hl_bin(x): return 0 if x < -0.10 else (2 if x > 0.10 else 1)
def cd_bin(d): return 0 if d > 0 else (1 if d == 0 else 2)
UP = list(dict.fromkeys(M["cluster"] for M in P)); UB = list(dict.fromkeys(M["cluster"] for M in Bt)); iP = {c: i for i, c in enumerate(UP)}; iB = {c: i for i, c in enumerate(UB)}

# ============================================================ time-based cubes (cluster, ph, crowns, hp-lead): total / eligible time (s) and Rocket plays
def frame_state(M):
    T = M["T"]; HP = M["HP"]
    me = (HP["eL"] <= 0) * 1 + (HP["eR"] <= 0) * 1 + (HP["eK"] <= 0) * 3; op = (HP["mL"] <= 0) * 1 + (HP["mR"] <= 0) * 1 + (HP["mK"] <= 0) * 3
    cd = np.where(me > op, 0, np.where(me == op, 1, 2))
    den = sum(M["MX"][k] for k in ("eK", "eL", "eR")); hl = (HP["mK"] + HP["mL"] + HP["mR"] - HP["eK"] - HP["eL"] - HP["eR"]) / den
    hb = np.where(hl < -0.10, 0, np.where(hl > 0.10, 2, 1)); sec = T / 20.0; ph = (sec >= 120) * 1 + (sec >= 180) * 1
    return ph, cd, hb
def play_cell(M, t):
    i = max(int(np.searchsorted(M["T"], t, "right")) - 1, 0)
    me = int(M["HP"]["eL"][i] <= 0) + int(M["HP"]["eR"][i] <= 0) + 3 * int(M["HP"]["eK"][i] <= 0); op = int(M["HP"]["mL"][i] <= 0) + int(M["HP"]["mR"][i] <= 0) + 3 * int(M["HP"]["mK"][i] <= 0)
    den = sum(M["MX"][k] for k in ("eK", "eL", "eR")); hl = (sum(M["HP"][k][i] for k in ("mK", "mL", "mR")) - sum(M["HP"][k][i] for k in ("eK", "eL", "eR"))) / den
    return (1 if t / 20.0 >= 120 else 0) + (1 if t / 20.0 >= 180 else 0), cd_bin(me - op), hl_bin(hl)
def new_cubes(n): return {k: np.zeros((n, 3, 3, 3)) for k in ("tot", "elig", "inhand", "play_t", "play_n")}
def add(cu, ci, ph, cd, hb, w, key):
    np.add.at(cu[key], (ci, ph, cd, hb), w)
CP = new_cubes(len(UP)); CB = new_cubes(len(UB)); meta_p = {"frames_total_s": 0, "matches": 0}
for M in P:
    H = hands[M["id"]]; ht = np.array([h[0] for h in H]); hasrk = np.array(["Rocket" in h[1] for h in H])
    T = M["T"]; idx = np.searchsorted(ht, T, "left"); valid = idx < len(H)
    rk = hasrk[np.minimum(idx, len(H) - 1)] & valid; elig = rk & (M["EL"] >= 6.0)
    dt = np.diff(T, append=T[-1] + 10) / 20.0; ph, cd, hb = frame_state(M); ci = iP[M["cluster"]]
    v = valid
    add(CP, ci, ph[rk], cd[rk], hb[rk], dt[rk], "inhand"); add(CP, ci, ph[v], cd[v], hb[v], dt[v], "tot"); add(CP, ci, ph[elig], cd[elig], hb[elig], dt[elig], "elig")
    for p in M["plays"]:
        if p["name"] != "Rocket": continue
        a, b_, c_ = play_cell(M, p["tick"]); tw = A.tower_target(M, p["x"], p["y"], p["tick"])
        add(CP, ci, np.array([a]), np.array([b_]), np.array([c_]), 1.0, "play_t" if tw else "play_n")
nb_used = 0
for M in Bt:
    st = bs[M["id"]]
    if not any(s[2] is not None for s in st): continue
    nb_used += 1; ci = iB[M["cluster"]]; phA, cdA, hbA = frame_state(M)
    st = [s for s in st if s[2] is not None]; ticks = np.array([s[0] for s in st]); fi = np.maximum(np.searchsorted(M["T"], ticks, "right") - 1, 0)
    ph, cd, hb = phA[fi], cdA[fi], hbA[fi]
    dt = np.array([(min(ticks[k + 1] - ticks[k], 60) if k + 1 < len(st) else 10) / 20.0 for k in range(len(st))])
    ok = np.ones(len(st), bool); inh = np.array([("Rocket" in s[2]) for s in st]); add(CB, ci, ph[inh], cd[inh], hb[inh], dt[inh], "inhand"); elig = np.array([("Rocket" in s[2]) and math.floor(s[1] + 1e-3) >= 6 for s in st])
    add(CB, ci, ph[ok], cd[ok], hb[ok], dt[ok], "tot"); add(CB, ci, ph[elig], cd[elig], hb[elig], dt[elig], "elig")
    for p in M["plays"]:
        if p["name"] != "Rocket" or not p["conf"]: continue
        a, b_, c_ = play_cell(M, p["tick"]); tw = A.tower_target(M, p["x"], p["y"], p["tick"])
        add(CB, ci, np.array([a]), np.array([b_]), np.array([c_]), 1.0, "play_t" if tw else "play_n")
print("bot matches with hand states", nb_used, "of", len(Bt), flush=True)
OUT["bot_matches_used"] = nb_used

SPLITS = [("all", (None, None, None))] + [(f"phase={PHN[i]}", (i, None, None)) for i in range(3)] + [(f"crowns={CDN[i]}", (None, i, None)) for i in range(3)] + [(f"hp={HLN[i]}", (None, None, i)) for i in range(3)]
def sl(a): return slice(None) if a is None else slice(a, a + 1)
def sums(cu, sp, key): return cu[key][:, sl(sp[0]), sl(sp[1]), sl(sp[2])].sum(axis=(1, 2, 3))
SIDX = {"P": RNG.integers(0, len(UP), (B, len(UP))), "B": RNG.integers(0, len(UB), (B, len(UB)))}
def draws(cu, src, sp, plays):
    S = SIDX[src]; tot = sums(cu, sp, "tot")[S].sum(1); el = sums(cu, sp, "elig")[S].sum(1)
    pl = sum(sums(cu, sp, k) for k in plays)[S].sum(1)
    pt = [sums(cu, sp, "tot").sum(), sums(cu, sp, "elig").sum(), sum(sums(cu, sp, k) for k in plays).sum()]
    return pt, tot, el, pl
def ci(x):
    x = x[np.isfinite(x)]
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if len(x) > 20 else [float('nan'), float('nan')]
def decomp(plays):
    res = {}
    for name, sp in SPLITS:
        (pt_p, tot_p, el_p, pl_p), (pt_b, tot_b, el_b, pl_b) = draws(CP, "P", sp, plays), draws(CB, "B", sp, plays)
        with np.errstate(all="ignore"):
            sh_p, sh_b = el_p / tot_p, el_b / tot_b; re_p, re_b = pl_p / (el_p / 60.0), pl_b / (el_b / 60.0); rt_p, rt_b = pl_p / (tot_p / 60.0), pl_b / (tot_b / 60.0)
            lg_share = np.log(sh_p / sh_b); lg_rate = np.log(re_p / re_b); lg_tot = np.log(rt_p / rt_b)
        pe = lambda a: a[0]
        pts = {"share": (pt_p[1] / max(pt_p[0], 1e-9), pt_b[1] / max(pt_b[0], 1e-9)), "rate_elig": (pt_p[2] / (pt_p[1] / 60), pt_b[2] / (pt_b[1] / 60) if pt_b[1] > 0 else float("nan")),
               "rate_tot": (pt_p[2] / (pt_p[0] / 60) if pt_p[0] > 0 else float("nan"), pt_b[2] / (pt_b[0] / 60) if pt_b[0] > 0 else float("nan"))}
        res[name] = {"minutes_total": (pt_p[0] / 60, pt_b[0] / 60), "minutes_elig": (pt_p[1] / 60, pt_b[1] / 60), "plays": (pt_p[2], pt_b[2]),
                     "eligible_share": {"pros": [pts["share"][0], *ci(sh_p)], "bot": [pts["share"][1], *ci(sh_b)]},
                     "rate_when_eligible_per_min": {"pros": [pts["rate_elig"][0], *ci(re_p)], "bot": [pts["rate_elig"][1], *ci(re_b)]},
                     "rate_per_match_min": {"pros": [pts["rate_tot"][0], *ci(rt_p)], "bot": [pts["rate_tot"][1], *ci(rt_b)]},
                     "log_ratio_total": [float(np.log(pts["rate_tot"][0] / pts["rate_tot"][1])) if pts["rate_tot"][1] > 0 and pts["rate_tot"][0] > 0 else None, *ci(lg_tot)],
                     "log_ratio_share": [float(np.log(pts["share"][0] / pts["share"][1])), *ci(lg_share)],
                     "log_ratio_rate_when_eligible": [float(np.log(pts["rate_elig"][0] / pts["rate_elig"][1])) if pts["rate_elig"][1] > 0 and pts["rate_elig"][0] > 0 else None, *ci(lg_rate)]}
        r = res[name]
        if r["log_ratio_total"][0]: r["share_of_log_gap_from_eligible_share"] = [r["log_ratio_share"][0] / r["log_ratio_total"][0], *ci(lg_share / lg_tot)]
    return res
INH = {}
for name, sp in SPLITS:
    (a_, b_) = [(sums(cu, sp, "tot"), sums(cu, sp, "inhand"), sums(cu, sp, "elig")) for cu in (CP, CB)]
    INH[name] = {src: {"rocket_in_hand_share": float(x[1].sum() / x[0].sum()), "P(elixir>=6 | Rocket in hand)": float(x[2].sum() / max(x[1].sum(), 1e-9))} for src, x in (("pros", a_), ("bot", b_))}
OUT["A_inhand_vs_elixir"] = INH
print("===== Rocket-in-hand share and P(el>=6 | in hand), time based")
for k, v in INH.items(): print(f"{k:22s} pros in-hand {v['pros']['rocket_in_hand_share']:.3f} P(el>=6|in hand) {v['pros']['P(elixir>=6 | Rocket in hand)']:.3f} | bot in-hand {v['bot']['rocket_in_hand_share']:.3f} P(el>=6|in hand) {v['bot']['P(elixir>=6 | Rocket in hand)']:.3f}")
OUT["A_decomp_all_rockets"] = decomp(["play_t", "play_n"]); OUT["A_decomp_tower_rockets"] = decomp(["play_t"]); OUT["A_decomp_nontower_rockets"] = decomp(["play_n"])
def pr(res, title):
    print("=====", title)
    for k, r in res.items():
        f = lambda t, p=3: f"{t[0]:.{p}f} [{t[1]:.{p}f},{t[2]:.{p}f}]" if t[0] is not None and t[0] == t[0] else "n/a"
        print(f"{k:22s} min(P/B) {r['minutes_total'][0]:.0f}/{r['minutes_total'][1]:.0f} elig-min {r['minutes_elig'][0]:.0f}/{r['minutes_elig'][1]:.1f} plays {r['plays'][0]:.0f}/{r['plays'][1]:.0f} | share P {f(r['eligible_share']['pros'])} B {f(r['eligible_share']['bot'])} | rate/elig-min P {f(r['rate_when_eligible_per_min']['pros'])} B {f(r['rate_when_eligible_per_min']['bot'])} | rate/match-min P {f(r['rate_per_match_min']['pros'])} B {f(r['rate_per_match_min']['bot'])} | ln gap {f(r['log_ratio_total'],2)} = share {f(r['log_ratio_share'],2)} + rate {f(r['log_ratio_rate_when_eligible'],2)}; frac from share {f(r.get('share_of_log_gap_from_eligible_share', [None]*3),2)}")
pr(OUT["A_decomp_tower_rockets"], "TOWER Rockets: decomposition (all minutes basis)"); pr(OUT["A_decomp_all_rockets"], "ALL Rockets"); pr(OUT["A_decomp_nontower_rockets"], "NON-TOWER Rockets")

# ============================================================ row-based: pros IL rows (+ model teacher forced on VAL)
R = pickle.load(open(XC + "rows.pkl", "rb")); CV = R["CV"]; RKi = CV.index("rocket"); XBi = CV.index("x-bow")
inv = {"Skeletons": "skeletons", "IceWizard": "ice-wizard", "Knight": "knight", "Log": "the-log", "Tesla": "tesla", "Xbow": "x-bow", "Tornado": "tornado", "Rocket": "rocket"}
g = np.flatnonzero(R["y_gate"] == 1); sig = {}
for i in g: sig.setdefault((int(R["rep"][i]), int(R["side"][i])), []).append((int(R["tick"][i]), CV[int(R["y_card"][i])]))
sigidx = {tuple(v[:6]): k for k, v in sig.items()}
key = R["rep"].astype(np.int64) * 2 + R["side"]; order = np.argsort(key, kind="stable"); ks = key[order]
el_int = np.floor(R["sc"][:, 0] * 10 + 1e-3)
rk_elig = (R["hand_card"] == RKi).any(1) & (el_int >= 6); xb_elig = (R["hand_card"] == XBi).any(1) & (el_int >= 6)
MP = {M["id"]: M for M in P}; rowrec = {}
for M in P:
    rp, sd = sigidx[tuple((p["tick"], inv[p["name"]]) for p in M["plays"][:6])]; k = rp * 2 + sd; a, b_ = np.searchsorted(ks, [k, k + 1]); rows = np.sort(order[a:b_])
    rkp = {p["tick"]: p for p in M["plays"] if p["name"] == "Rocket"}
    for i in rows:
        if not (rk_elig[i] or xb_elig[i]): continue
        t = int(R["tick"][i]); ph, cd, hb = play_cell(M, t)
        rec = {"id": M["id"], "c": M["cluster"], "ph": ph, "cd": cd, "hb": hb, "split": int(R["split"][i]), "rk_elig": bool(rk_elig[i]), "xb_elig": bool(xb_elig[i]), "tick": t}
        isrk = R["y_gate"][i] == 1 and int(R["y_card"][i]) == RKi
        rec["rk_play"] = bool(isrk)
        rec["rk_tower"] = bool(isrk and t in rkp and A.tower_target(M, rkp[t]["x"], rkp[t]["y"], t) is not None)
        rec["alive"] = "".join(kk for kk in "KLR" if A.hp_at(M, "e" + kk, t) > 0)
        rowrec[int(i)] = rec
print("pros rows kept", len(rowrec), flush=True)
def rows_ci(U, recs, num, den=lambda r: 1): return C.rci(U, [(r["c"], num(r), den(r)) for r in recs])
def fm(t, pct=True, nd=1):
    if t is None or t[0] is None: return "n/a"
    g_ = (lambda v: f"{100*v:.{nd}f}%") if pct else (lambda v: f"{v:.{nd+1}f}")
    return f"{g_(t[0])} [{g_(t[1])},{g_(t[2])}]" + (f" n={int(t[4])}" if len(t) > 4 else "")
ALLR = [r for r in rowrec.values() if r["rk_elig"]]
def split_filter(recs, name):
    if name == "all": return recs
    k, v = name.split("="); idx = {"phase": ("ph", PHN), "crowns": ("cd", CDN), "hp": ("hb", HLN)}[k]
    return [r for r in recs if r[idx[0]] == idx[1].index(v)]
A1 = {}
for name, _ in SPLITS:
    sub = split_filter(ALLR, name)
    A1[name] = {"n_rows": len(sub), "pros_P(Rocket)": rows_ci(UP, sub, lambda r: int(r["rk_play"])), "pros_tower": rows_ci(UP, sub, lambda r: int(r["rk_tower"])), "pros_nontower": rows_ci(UP, sub, lambda r: int(r["rk_play"] and not r["rk_tower"]))}
OUT["A1_pros_rows"] = A1
# ---- model (val)
MR = pickle.load(open(HERE + "model_rk.pkl", "rb")) if os.path.exists(HERE + "model_rk.pkl") else None
if MR is not None:
    gidx = np.searchsorted(R["sel"], MR["sel"]); sub_ix = {s: k for k, s in enumerate(MR["subsets"])}; vrec = []
    for j, i in enumerate(gidx):
        r = rowrec.get(int(i))
        if r is None or not r["rk_elig"] or not r["alive"]: continue
        r = dict(r); soft = float(MR["p_play"][j] * MR["p_xb_given_play"][j]); tm = float(MR["towermass"][j, sub_ix[r["alive"]]])
        r["m_soft"] = soft; r["m_soft_t"] = soft * tm; r["m_soft_n"] = soft * (1 - tm); live = bool(MR["p_play"][j] > 0.35 and MR["argmax_is_xb"][j])
        cx = 18.0 - (int(MR["argcell"][j]) % 36) / 2.0; cy = (int(MR["argcell"][j]) // 36) / 2.0
        near = any(A.dist((cx, cy), A.TOWER_XY["e" + k]) <= 2.0 for k in r["alive"])
        r["m_live"] = int(live); r["m_live_t"] = int(live and near); r["m_live_n"] = int(live and not near); r["rank"] = int(MR["rank"][j]); r["p_play"] = float(MR["p_play"][j]); vrec.append(r)
    Um = list(dict.fromkeys(r["c"] for r in vrec)); OUT["model_val_rows"] = {"n": len(vrec), "clusters": len(Um)}
    def pair_ratio(recs, fa, fb):
        na, da = C.rows_to_arrays(Um, [(r["c"], fa(r), 1) for r in recs]); nb, db = C.rows_to_arrays(Um, [(r["c"], fb(r), 1) for r in recs])
        S = RNG.integers(0, len(Um), (B, len(Um))); a, b_ = na[S].sum(1), nb[S].sum(1); ok = b_ > 0
        return [float(na.sum() / nb.sum()) if nb.sum() > 0 else None, *[float(x) for x in np.percentile((a[ok] / b_[ok]), [2.5, 97.5])]]
    A2 = {}
    for name, _ in SPLITS:
        sub = split_filter(vrec, name)
        A2[name] = {"n_rows": len(sub), "pros_P": rows_ci(Um, sub, lambda r: int(r["rk_play"])), "pros_tower": rows_ci(Um, sub, lambda r: int(r["rk_tower"])), "pros_nontower": rows_ci(Um, sub, lambda r: int(r["rk_play"] and not r["rk_tower"])),
                    "model_soft": rows_ci(Um, sub, lambda r: r["m_soft"]), "model_soft_tower": rows_ci(Um, sub, lambda r: r["m_soft_t"]), "model_soft_nontower": rows_ci(Um, sub, lambda r: r["m_soft_n"]),
                    "model_live": rows_ci(Um, sub, lambda r: r["m_live"]), "model_live_tower": rows_ci(Um, sub, lambda r: r["m_live_t"]), "model_live_nontower": rows_ci(Um, sub, lambda r: r["m_live_n"]),
                    "ratio_model_soft/pros": pair_ratio(sub, lambda r: r["m_soft"], lambda r: int(r["rk_play"])), "ratio_model_live/pros": pair_ratio(sub, lambda r: r["m_live"], lambda r: int(r["rk_play"])),
                    "ratio_soft_tower/pros_tower": pair_ratio(sub, lambda r: r["m_soft_t"], lambda r: int(r["rk_tower"]))}
    OUT["A2_model_val"] = A2
    pr_rows = [r for r in vrec if r["rk_play"]]
    rk = collections.Counter(r["rank"] for r in pr_rows)
    OUT["rank_of_rocket_on_pro_rocket_rows"] = {"n": len(pr_rows), "counts": dict(rk), "shares": {str(k): C.rci(Um, [(r["c"], int(r["rank"] == k), 1) for r in pr_rows]) for k in (1, 2, 3, 4)},
                                                "mean_gate_p_play": float(np.mean([r["p_play"] for r in pr_rows])), "mean_soft_P(Rocket)": float(np.mean([r["m_soft"] for r in pr_rows])),
                                                "share_gate_over_0.35": float(np.mean([r["p_play"] > 0.35 for r in pr_rows]))}
    OUT["rank_tower_only"] = {"n": sum(r["rk_tower"] for r in pr_rows), "top1": float(np.mean([r["rank"] == 1 for r in pr_rows if r["rk_tower"]]))}
    print("===== A2 model on pro VAL rows (Rocket in hand & >=6 elixir)", OUT["model_val_rows"])
    for name, d in A2.items():
        print(f"{name:22s} n={d['n_rows']:6d} pros {fm(d['pros_P'])} (tower {fm(d['pros_tower'])}) | model soft {fm(d['model_soft'])} (tower {fm(d['model_soft_tower'])}) | live {fm(d['model_live'])} (tower {fm(d['model_live_tower'])}) | ratio soft/pros {np.round(d['ratio_model_soft/pros'],2)} live/pros {np.round(d['ratio_model_live/pros'],2)} tower soft/pros {np.round(d['ratio_soft_tower/pros_tower'],2)}")
    print("rank of Rocket on pro Rocket rows", OUT["rank_of_rocket_on_pro_rocket_rows"], OUT["rank_tower_only"])
print("===== A1 pros rows")
for name, d in A1.items(): print(f"{name:22s} n={d['n_rows']:6d} P(Rocket) {fm(d['pros_P(Rocket)'])} tower {fm(d['pros_tower'])} nontower {fm(d['pros_nontower'])}")

# ============================================================ B: defensive share of X-Bow placements by lead bin x phase
def xb_recs(Ms, X, src):
    out = []
    for M in Ms:
        for r in X[M["id"]]:
            if r["cls"] not in ("off", "def"): continue
            out.append({"c": M["cluster"], "ph": PHN.index(r["ph"]), "hb": hl_bin(r["hl"]), "cd": cd_bin(r["cd"]), "def": int(r["cls"] == "def"), "sec": r["sec"]})
    return out
XPr, XBr = xb_recs(P, XP, "pros"), xb_recs(Bt, XB, "bot")
def table_B(recs, U):
    t = {}
    for hb in range(3):
        for ph in range(-1, 3):
            sub = [r for r in recs if r["hb"] == hb and (ph < 0 or r["ph"] == ph)]
            t[f"{HLN[hb]}|{'all' if ph < 0 else PHN[ph]}"] = C.rci(U, [(r["c"], r["def"], 1) for r in sub])
    t["late(>=120s)|lead"] = C.rci(U, [(r["c"], r["def"], 1) for r in recs if r["hb"] == 2 and r["sec"] >= 120])
    t["late(>=120s)|deficit"] = C.rci(U, [(r["c"], r["def"], 1) for r in recs if r["hb"] == 0 and r["sec"] >= 120])
    t["shift(lead-deficit)"] = C.diff_ci(U, [(r["c"], r["def"], 1) for r in recs if r["hb"] == 2], [(r["c"], r["def"], 1) for r in recs if r["hb"] == 0])
    t["shift_late(lead-deficit)"] = C.diff_ci(U, [(r["c"], r["def"], 1) for r in recs if r["hb"] == 2 and r["sec"] >= 120], [(r["c"], r["def"], 1) for r in recs if r["hb"] == 0 and r["sec"] >= 120])
    return t
OUT["B_pros_actual"] = table_B(XPr, UP); OUT["B_bot_actual"] = table_B(XBr, UB)
if os.path.exists(XC + "model_rows.pkl"):
    MX_ = pickle.load(open(XC + "model_rows.pkl", "rb")); gidx = np.searchsorted(R["sel"], MX_["sel"]); sub_ix = {s: k for k, s in enumerate(MX_["subsets"])}; brec = []
    for j, i in enumerate(gidx):
        r = rowrec.get(int(i))
        if r is None or not r["xb_elig"] or not r["alive"]: continue
        M = MP[r["id"]]; t = r["tick"]; om = float(MX_["offmass"][j, sub_ix[r["alive"]]]); soft = float(MX_["p_play"][j] * MX_["p_xb_given_play"][j])
        cx = 18.0 - (int(MX_["argcell"][j]) % 36) / 2.0; cy = (int(MX_["argcell"][j]) // 36) / 2.0
        arg_def = int(not any(A.dist((cx, cy), A.TOWER_XY["e" + k]) <= A.REACH for k in r["alive"]))
        live = bool(MX_["p_play"][j] > 0.35 and MX_["argmax_is_xb"][j])
        den = sum(M["MX"][k] for k in ("eK", "eL", "eR")); hlv = (sum(A.hp_at(M, k, t) for k in ("mK", "mL", "mR")) - sum(A.hp_at(M, k, t) for k in ("eK", "eL", "eR"))) / den
        brec.append({"c": r["c"], "ph": r["ph"], "hb": hl_bin(hlv), "sec": t / 20.0, "pro_xb": int(r["rk_play"] is not None and False), "soft": soft, "defmass": 1 - om, "arg_def": arg_def, "live": int(live), "split": r["split"]})
    # pro actual X-Bow plays on the same rows: need class -> from XP by (id,tick); rebuild quickly
    xcls = {(M["id"], x["tick"]): x["cls"] for M in P for x in XP[M["id"]]}
    for (i, r_) in zip([int(i) for i in gidx if int(i) in rowrec and rowrec[int(i)]["xb_elig"] and rowrec[int(i)]["alive"]], brec):
        rr = rowrec[i]; isx = R["y_gate"][i] == 1 and int(R["y_card"][i]) == XBi
        r_["pro_play"] = int(isx); r_["pro_def"] = int(isx and xcls.get((rr["id"], rr["tick"])) == "def")
    Um2 = list(dict.fromkeys(r["c"] for r in brec)); OUT["B_model_rows"] = {"n": len(brec), "clusters": len(Um2)}
    def tB(recs):
        t = {}
        pl = [r for r in recs if r["pro_play"]]
        for hb in range(3):
            for ph in range(-1, 3):
                nm = f"{HLN[hb]}|{'all' if ph < 0 else PHN[ph]}"; f_ = lambda r: r["hb"] == hb and (ph < 0 or r["ph"] == ph)
                s1 = [r for r in pl if f_(r)]; s2 = [r for r in recs if f_(r)]; s3 = [r for r in recs if f_(r) and r["live"]]
                t[nm] = {"n_pro_xbow_plays": len(s1), "pros_actual_def": C.rci(Um2, [(r["c"], r["pro_def"], 1) for r in s1]),
                         "model_defmass_on_pro_xbow_rows": C.rci(Um2, [(r["c"], r["defmass"], 1) for r in s1]), "model_argcell_def_on_pro_xbow_rows": C.rci(Um2, [(r["c"], r["arg_def"], 1) for r in s1]),
                         "model_chosen_soft_weighted_def": C.rci(Um2, [(r["c"], r["soft"] * r["defmass"], r["soft"]) for r in s2]), "n_live_chosen": len(s3),
                         "model_live_chosen_argcell_def": C.rci(Um2, [(r["c"], r["arg_def"], 1) for r in s3])}
        for nm, f_ in (("all", lambda r: True), ("late", lambda r: r["sec"] >= 120)):
            for lab, fn in (("pros_actual_def", lambda s: [(r["c"], r["pro_def"], 1) for r in s]), ("model_defmass_on_pro_xbow_rows", lambda s: [(r["c"], r["defmass"], 1) for r in s]),
                            ("model_chosen_soft_weighted_def", lambda s: [(r["c"], r["soft"] * r["defmass"], r["soft"]) for r in s])):
                base = pl if lab != "model_chosen_soft_weighted_def" else recs
                lead = [r for r in base if r["hb"] == 2 and f_(r)]; dfc = [r for r in base if r["hb"] == 0 and f_(r)]
                t[f"shift_{nm}(lead-deficit)|{lab}"] = C.diff_ci(Um2, fn(lead), fn(dfc))
        return t
    OUT["B_model_on_val"] = tB(brec)
    print("===== B pros actual (all splits) vs bot actual: P(defensive | X-Bow placed)")
    for k in OUT["B_pros_actual"]:
        v1, v2 = OUT["B_pros_actual"][k], OUT["B_bot_actual"][k]
        print(f"{k:34s} pros {fm(v1) if len(v1)>3 else [round(x,3) for x in v1]} | bot {fm(v2) if len(v2)>3 else [round(x,3) for x in v2]}")
    print("===== B model teacher-forced (val rows)", OUT["B_model_rows"])
    for k, v in OUT["B_model_on_val"].items():
        if isinstance(v, dict): print(f"{k:28s} n_pro_xb={v['n_pro_xbow_plays']:4d} pros {fm(v['pros_actual_def'])} | model defmass(on pro rows) {fm(v['model_defmass_on_pro_xbow_rows'])} argcell {fm(v['model_argcell_def_on_pro_xbow_rows'])} | model chosen soft {fm(v['model_chosen_soft_weighted_def'])} | live-chosen n={v['n_live_chosen']} {fm(v['model_live_chosen_argcell_def'])}")
        else: print(k, [round(x, 3) for x in v])
json.dump(OUT, open(HERE + "results.json", "w"), indent=1, default=str); print("saved")
