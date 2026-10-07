"""Turtle hypothesis: after failed offensive X-Bows, do icebow players shift (rest of match) to defensive X-Bows / tower Rockets / banked elixir?
Reuses L73/xbow_switch extraction (pros.pkl, bot.pkl, xrows.pkl) and its definitions (analyze.py). CPU only. Writes results.json here."""
import os, sys, pickle, json, math, collections
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"): os.environ[_v] = "4"
import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # below normal
import numpy as np
SW = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch/"
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_turtle/"
sys.path.insert(0, SW)
import analyze as A   # import only: hp_at, crowns, rocket_rows, REACH, TOWER_XY, phase

B = 2000; RNG = np.random.default_rng(11); BIN = 30.0; NB = 10
MET = ["offX/min", "defX/min", "towerRocket/min", "allRocket/min", "defShare(X)", "dmgHP/min", "shareRocket", "shareXbow", "shareOther",
       "rocketMain(>50%)", "elixirMean", "fracTime>=9.9el"]

def attrib(M, RD, RK):
    """per frame-step enemy-tower HP drops split into rocket / xbow-window / other. Returns (t, rocket, xbow, other) arrays."""
    T = M["T"]; n = len(T); R = np.zeros(n); X = np.zeros(n); O = np.zeros(n)
    rk = [[r["tick"], r["tower"], RD] for r in RK if r["tower"]]
    for k in ("eK", "eL", "eR"):
        h = np.minimum.accumulate(np.asarray(M["HP"][k], float))  # HP never rises: kills read noise (bot)
        d = np.r_[0.0, h[:-1] - h[1:]]
        xy = A.TOWER_XY[k]
        reach = [(t["first"], t["last"] + 10) for t in M["xtracks"] if math.hypot(t["x"] - xy[0], t["y"] - xy[1]) <= A.REACH]
        for i in np.nonzero(d > 0)[0]:
            t = T[i]; left = d[i]
            for r in rk:
                if r[1] == k and r[0] <= t <= r[0] + 110 and r[2] > 0 and left > 0:
                    a = min(left, r[2]); r[2] -= a; left -= a; R[i] += a
            if left > 0 and any(a <= t <= b for a, b in reach): X[i] += left
            else: O[i] += left
    return T, R, X, O

def window(M, xs, RK, AT, a, b):
    """metric num/den over ticks (a, b]."""
    mins = (b - a) / 1200.0
    off = sum(1 for r in xs if a < r["tick"] <= b and r["cls"] == "off"); dfx = sum(1 for r in xs if a < r["tick"] <= b and r["cls"] == "def")
    tr = sum(1 for r in RK if r["tower"] and a < r["tick"] <= b); ar = sum(1 for r in RK if a < r["tick"] <= b)
    T, R, X, O = AT; m = (T > a) & (T <= b)
    r_, x_, o_ = R[m].sum(), X[m].sum(), O[m].sum(); tot = r_ + x_ + o_
    me = (M["T"] > a) & (M["T"] <= b); el = M["EL"][me]
    elm = float(el.mean()) if len(el) else 0.0; full = float((el >= 9.9).mean()) if len(el) else 0.0
    num = [off, dfx, tr, ar, dfx, tot, r_, x_, o_, float(tot > 0 and r_ > 0.5 * tot), elm * mins, full * mins]
    den = [mins, mins, mins, mins, off + dfx, mins, tot, tot, tot, float(tot > 0), mins, mins]
    return num, den

def prep(Ms, X, RD):
    out = []
    for M in Ms:
        RK = A.rocket_rows(M); out.append((M, X[M["id"]], RK, attrib(M, RD, RK)))
    return out

def units_K(P, K, strict=False, level0=False):
    U = []; drop = collections.Counter()
    for M, xs, RK, AT in P:
        offs = [r for r in xs if r["cls"] == "off"]
        if len(offs) < K: drop["<K offensive"] += 1; continue
        f = offs[:K]
        if any(r["status"] not in ("fail", "ok") for r in f): drop["unresolved(alive/unk) in first K"] += 1; continue
        tK = max(r["death"] for r in f)
        if M["end"] - tK < 300: drop["<15s left"] += 1; continue
        if strict:
            if f[0]["dmg"] == 0: g = "fail"
            elif f[0]["dmg"] >= 0.25: g = "ok"
            else: drop["strict middle"] += 1; continue
        else:
            nf = sum(r["status"] == "fail" for r in f); g = "fail" if nf == K else ("ok" if nf == 0 else "mixed")
        if level0 and A.crowns(M, tK) != (0, 0): drop["not 0-0 at tK"] += 1; continue
        num, den = window(M, xs, RK, AT, tK, M["end"])
        U.append({"c": M["cluster"], "g": g, "b": min(int(tK / 20 / BIN), NB - 1), "num": num, "den": den, "sec": tK / 20})
    return U, dict(drop)

def units_did(P):
    """first failure / first success of an offensive X-Bow; before = [0, play), after = (death, end]."""
    U = []
    for M, xs, RK, AT in P:
        for g, st in (("fail", "fail"), ("ok", "ok")):
            r = next((r for r in xs if r["cls"] == "off" and r["status"] == st), None)
            if r is None or r["tick"] < 600 or M["end"] - r["death"] < 300: continue
            na, da = window(M, xs, RK, AT, r["death"], M["end"]); nb, db = window(M, xs, RK, AT, 0, r["tick"] - 1)
            U.append({"c": M["cluster"], "g": g, "b": min(int(r["death"] / 20 / BIN), NB - 1), "num": na + nb, "den": da + db, "sec": r["death"] / 20})
    return U

def boot_W(Ms):
    C = sorted({M["cluster"] for M in Ms}); idx = {c: i for i, c in enumerate(C)}
    W = np.ones((B + 1, len(C)), np.float32)
    for j in range(B): W[j + 1] = np.bincount(RNG.integers(0, len(C), len(C)), minlength=len(C))
    return W, idx

def cells(U, W, idx):
    cl = np.array([idx[u["c"]] for u in U]); Wu = W[:, cl]
    NUM = np.array([u["num"] for u in U], np.float64); DEN = np.array([u["den"] for u in U], np.float64)
    g = np.array([u["g"] for u in U]); b = np.array([u["b"] for u in U]); out = {}
    for gg in set(g):
        for bb in range(NB):
            m = (g == gg) & (b == bb)
            if m.any(): out[(gg, bb)] = (Wu[:, m] @ NUM[m], Wu[:, m] @ DEN[m], Wu[:, m].sum(1), int(m.sum()))
    return out

def ratio(sn, sd):
    with np.errstate(invalid="ignore", divide="ignore"): return np.where(sd > 0, sn / np.where(sd > 0, sd, 1), np.nan)

def ci(v):
    v = v[1:]; v = v[np.isfinite(v)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) > 50 else [None, None]

def std_effect(CE, gA, gB, bins, cols=None, did=False):
    """time-stratified (30 s bins of resolution time) difference gA - gB, weights = gA unit count per bin (bootstrap-recomputed).
    did: num/den hold [after.., before..]; effect = (after-before)_A - (after-before)_B."""
    m = len(MET); acc = 0; wsum = 0; LA = 0; LB = 0; nA = nB = 0; cov = 0; tot = 0
    for bb in bins:
        a = CE.get((gA, bb)); c = CE.get((gB, bb))
        if a: tot += a[3]
        if not a or not c or a[3] < 3 or c[3] < 3: continue
        cov += a[3]; nA += a[3]; nB += c[3]
        RA = ratio(a[0], a[1]); RB = ratio(c[0], c[1])
        if did: RA = RA[:, :m] - RA[:, m:]; RB = RB[:, :m] - RB[:, m:]
        ok = np.isfinite(RA) & np.isfinite(RB); w = a[2][:, None] * ok
        acc = acc + w * np.nan_to_num(RA - RB); LA = LA + w * np.nan_to_num(RA); LB = LB + w * np.nan_to_num(RB); wsum = wsum + w
    if nA == 0: return None
    with np.errstate(invalid="ignore", divide="ignore"):
        D = acc / wsum; la = LA / wsum; lb = LB / wsum
    return {MET[j]: {"A": float(la[0, j]), "B": float(lb[0, j]), "diff": float(D[0, j]), "ci": ci(D[:, j]), "draws": D[1:, j]} for j in range(m)} | \
           {"_n": {"A": nA, "B": nB, "coverage_of_A": cov / max(tot, 1)}}

def raw_effect(CE, gA, gB):
    m = len(MET); S = {}
    for gg in (gA, gB):
        sn = sum(v[0] for k, v in CE.items() if k[0] == gg); sd = sum(v[1] for k, v in CE.items() if k[0] == gg); S[gg] = ratio(sn, sd)[:, :m]
    D = S[gA] - S[gB]
    return {MET[j]: {"diff": float(D[0, j]), "ci": ci(D[:, j])} for j in range(m)}

PH = {"all": range(NB), "1x": range(0, 4), "2x": range(4, 6), "OT": range(6, NB)}

def run(Ms, X, RD, label):
    W, idx = boot_W(Ms); P = prep(Ms, X, RD); res = {"n_sides": len(Ms)}
    specs = [("K1", dict(K=1), [("fail", "ok")]), ("K2", dict(K=2), [("fail", "ok"), ("mixed", "ok"), ("fail", "mixed")]),
             ("K1_strict(0dmg_vs_>=25%)", dict(K=1, strict=True), [("fail", "ok")]), ("K1_level0-0", dict(K=1, level0=True), [("fail", "ok")]),
             ("K2_level0-0", dict(K=2, level0=True), [("fail", "ok")])]
    for nm, kw, comps in specs:
        U, drop = units_K(P, **kw); CE = cells(U, W, idx)
        r = {"drop": drop, "n_by_group": dict(collections.Counter(u["g"] for u in U)),
             "sec_median_by_group": {g: float(np.median([u["sec"] for u in U if u["g"] == g])) for g in set(u["g"] for u in U)}}
        for gA, gB in comps:
            r[f"{gA}-{gB}"] = {ph: std_effect(CE, gA, gB, bins) for ph, bins in PH.items()}
            r[f"{gA}-{gB}"]["raw_unstratified"] = raw_effect(CE, gA, gB)
        if nm == "K1":  # learnability: excess rows in post-fail remainders vs time-matched success rates
            ex = {}
            for j, k in enumerate(MET[:4]):
                e = 0.0; obs = 0.0; mins = 0.0
                for bb in range(NB):
                    a = CE.get(("fail", bb)); c = CE.get(("ok", bb))
                    if not a: continue
                    obs += a[0][0, j]; mins += a[1][0, j]
                    if c and c[3] >= 3: e += (a[0][0, j] / a[1][0, j] - c[0][0, j] / c[1][0, j]) * a[1][0, j]
                ex[k.split("/")[0]] = {"rows_in_postfail_remainders": round(obs), "excess_vs_matched_success": round(e, 1), "postfail_minutes": round(mins, 1)}
            r["learnability"] = ex
        res[nm] = r
    U = units_did(P); CE = cells(U, W, idx)
    res["DiD"] = {"n_by_group": dict(collections.Counter(u["g"] for u in U)), **{ph: std_effect(CE, "fail", "ok", bins, did=True) for ph, bins in PH.items()}}
    # before/after levels per arm (unstratified) for readability
    lv = {}
    for g in ("fail", "ok"):
        sn = sum(v[0] for k, v in CE.items() if k[0] == g); sd = sum(v[1] for k, v in CE.items() if k[0] == g); R = ratio(sn, sd)[0]
        lv[g] = {"before": dict(zip(MET, map(float, R[len(MET):]))), "after": dict(zip(MET, map(float, R[:len(MET)])))}
    res["DiD"]["levels_unstratified"] = lv
    print(label, "done", flush=True)
    return res

def strip(o):
    if isinstance(o, dict): return {str(k): strip(v) for k, v in o.items() if k != "draws"}
    if isinstance(o, (list, tuple)): return [strip(v) for v in o]
    if isinstance(o, (np.floating, np.integer)): return o.item()
    return o

def main():
    pros = pickle.load(open(SW + "pros.pkl", "rb")); bot = pickle.load(open(SW + "bot.pkl", "rb")); X = pickle.load(open(SW + "xrows.pkl", "rb"))
    for M in bot:  # same normalisation as analyze.main (rocket_rows reads play xy)
        for p in M["plays"]: p["x"] = math.floor(p["x"]) + 0.5; p["y"] = math.floor(p["y"]) + 0.5
    RD = json.load(open(SW + "results.json"))["meta"]["RD"]
    clean = [M for M in pros if M["crowns_match"] and M["eng_agree"]]
    out = {"pros_all": run(pros, X["pros_all"], RD["pro"], "pros_all"), "pros_engine_agrees": run(clean, X["pros_engine_agrees"], RD["pro"], "clean"),
           "bot": run(bot, X["bot"], RD["bot"], "bot")}
    # pro - bot difference of the matched K1 fail-ok effect (independent bootstraps)
    pb = {}
    for spec in ("K1", "K2"):
        p = out["pros_all"][spec]["fail-ok"]["all"]; b = out["bot"][spec]["fail-ok"]["all"]
        if p and b: pb[spec] = {k: {"pro": p[k]["diff"], "bot": b[k]["diff"], "pro-bot": p[k]["diff"] - b[k]["diff"], "ci": ci(np.r_[0, p[k]["draws"] - b[k]["draws"]])} for k in MET}
    out["pro_minus_bot_effect"] = pb
    out["meta"] = {"B": B, "bin_s": BIN, "RD": RD, "strict_X": "0 vs >=25% of target tower max HP (X-Bow dmg net of Rockets, as xbow_switch)",
                   "player_identity": "unavailable: corpus is the anonymized RoyaleAPI/HF set (source.anonymized=true, requested_player_tag empty, no player tag/name fields)"}
    json.dump(strip(out), open(HERE + "results.json", "w"), indent=1)
    print("saved")

if __name__ == "__main__":
    main()
