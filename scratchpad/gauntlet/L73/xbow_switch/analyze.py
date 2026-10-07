"""Stage 2: X-Bow offensive/defensive switch analysis, pros vs bot. Reads pros.pkl / bot.pkl from extract.py. Writes results.json + xrows.pkl."""
import pickle, json, collections, math
import numpy as np
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch/"
TOWER_XY = {"eK": (9.0, 3.0), "eL": (3.5, 6.5), "eR": (14.5, 6.5)}
REACH = 13.0385  # sqrt(170)=13.03840481: the (+-1,13)-tile offset grid cell is exactly the validated reach, so give float slack
RR = 2.0; WIN = 600  # response window 30 s
B = 2000; RNG = np.random.default_rng(7)

def phase(sec): return "1x" if sec < 120 else ("2x" if sec < 180 else "OT")
def hp_at(M, sl, t):
    i = int(np.searchsorted(M["T"], t, "right")) - 1
    return float(M["MX"][sl]) if i < 0 else float(M["HP"][sl][i])
def crowns(M, t):
    me = sum(hp_at(M, k, t) <= 0 for k in ("eL", "eR")) + (3 if hp_at(M, "eK", t) <= 0 else 0)
    op = sum(hp_at(M, k, t) <= 0 for k in ("mL", "mR")) + (3 if hp_at(M, "mK", t) <= 0 else 0)
    return me, op
def hp_lead(M, t):
    den = sum(M["MX"][k] for k in ("eK", "eL", "eR"))
    return (sum(hp_at(M, k, t) for k in ("mK", "mL", "mR")) - sum(hp_at(M, k, t) for k in ("eK", "eL", "eR"))) / den
def dist(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
def reach_towers(M, x, y, t):
    return [k for k, xy in TOWER_XY.items() if hp_at(M, k, t) > 0 and dist((x, y), xy) <= REACH]
def tower_target(M, x, y, t):
    for k, xy in TOWER_XY.items():
        if hp_at(M, k, t) > 0 and dist((x, y), xy) <= RR: return k
    return None

def rocket_damage(Ms):
    """median single-frame-step drop of the targeted tower within 100 ticks of a tower Rocket, when no own X-Bow is alive (so X-Bow cannot be the source)."""
    ds = []
    for M in Ms:
        for p in M["plays"]:
            if p["name"] != "Rocket" or (M["kind"] == "bot" and not p["conf"]): continue
            k = tower_target(M, p["x"], p["y"], p["tick"])
            if not k: continue
            if any(t["first"] - 50 <= p["tick"] + 100 and t["last"] + 50 >= p["tick"] for t in M["xtracks"]): continue
            i0 = int(np.searchsorted(M["T"], p["tick"], "right")) - 1; i1 = int(np.searchsorted(M["T"], p["tick"] + 100, "right"))
            h = M["HP"][k][max(i0, 0):i1]
            if len(h) > 1 and h[-1] > 0: ds.append(float(max(h[:-1] - h[1:])))
    return float(np.median(ds)), len(ds)

def xbow_rows(M, RD):
    plays = [p for p in M["plays"] if p["name"] == "Xbow"]
    tr = sorted(M["xtracks"], key=lambda t: t["first"]); used = set(); rows = []
    rk = [(p["tick"], tower_target(M, p["x"], p["y"], p["tick"])) for p in M["plays"] if p["name"] == "Rocket" and (M["kind"] == "pro" or p["conf"])]
    for p in sorted(plays, key=lambda p: p["tick"]):
        best = None
        for i, t in enumerate(tr):
            if i in used or not (p["tick"] - 30 <= t["first"] <= p["tick"] + 300): continue
            d = dist((p["x"], p["y"]), (t["x"], t["y"]))
            if d < 3.0 and (best is None or d < best[0]): best = (d, i)
        if best: used.add(best[1]); t = tr[best[1]]
        else:
            t = None
            if M["kind"] == "bot" and not p["conf"]: continue
        tk = p["tick"]; sec = tk / 20.0
        rt = reach_towers(M, p["x"], p["y"], tk)
        cls = "off" if rt else ("def" if p["y"] >= 16 else "other")
        r = {"tick": tk, "sec": sec, "ph": phase(sec), "cls": cls, "x": p["x"], "y": p["y"], "status": "unk", "dmg": None, "death": None, "track": t is not None}
        me, op = crowns(M, tk); r["cd"] = me - op; r["hl"] = hp_lead(M, tk)
        if t is not None:
            if t["cens"]: r["status"] = "alive"
            else:
                r["death"] = t["last"]
                if rt:
                    fr = []
                    for k in rt:
                        drop = hp_at(M, k, t["first"] - 1) - hp_at(M, k, t["last"] + 10)
                        nr = sum(1 for (rt_, kk) in rk if kk == k and t["first"] - 60 <= rt_ <= t["last"])
                        fr.append(max(0.0, drop - RD * nr) / M["MX"][k])
                    r["dmg"] = max(fr); r["status"] = "fail" if r["dmg"] < 0.10 else "ok"
                else: r["status"] = "dead"  # defensive X-Bow ended
        rows.append(r)
    return rows

def rocket_rows(M):
    out = []
    for p in M["plays"]:
        if p["name"] != "Rocket" or (M["kind"] == "bot" and not p["conf"]): continue
        k = tower_target(M, p["x"], p["y"], p["tick"])
        me, op = crowns(M, p["tick"])
        out.append({"tick": p["tick"], "sec": p["tick"] / 20.0, "tower": k, "frac": (hp_at(M, k, p["tick"]) / M["MX"][k]) if k else None, "cd": me - op,
                    "hp": hp_at(M, k, p["tick"]) if k else None})
    return out

def rci(universe, rows):
    """rows: list of (cluster, num, den). ratio of sums with cluster bootstrap over `universe` (all matches of that kind)."""
    idx = {c: i for i, c in enumerate(universe)}
    num = np.zeros(len(universe)); den = np.zeros(len(universe))
    for c, n, d in rows: num[idx[c]] += n; den[idx[c]] += d
    if den.sum() == 0: return (None, None, None, 0, 0)
    pt = num.sum() / den.sum()
    S = RNG.integers(0, len(universe), (B, len(universe)))
    dn = den[S].sum(1); ok = dn > 0
    r = num[S].sum(1)[ok] / dn[ok]
    return (float(pt), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5)), float(num.sum()), float(den.sum()))

def analyze(Ms, RD):
    U = list(dict.fromkeys(M["cluster"] for M in Ms))
    X = {M["id"]: xbow_rows(M, RD) for M in Ms}; RK = {M["id"]: rocket_rows(M) for M in Ms}
    res = {"n_matches": len(Ms), "RD": RD}
    # ---- Q1: P(next X-Bow defensive | previous offensive X-Bow failed)
    q1 = collections.defaultdict(list)
    for M in Ms:
        xs = X[M["id"]]; c = M["cluster"]
        for i, r in enumerate(xs):
            if r["cls"] != "off" or r["death"] is None or r["status"] not in ("fail", "ok"): continue
            kind = r["status"]
            nxt = next((q for q in xs[i + 1:] if q["tick"] > r["death"]), None)
            two = i > 0 and xs[i - 1]["cls"] == "off" and xs[i - 1]["status"] == "fail" and xs[i - 1]["death"] is not None and r["tick"] > xs[i - 1]["death"]
            ph = phase(r["death"] / 20.0)
            keys = [("prev_" + kind, "all"), ("prev_" + kind, ph)]
            if kind == "fail" and two: keys += [("prev_2fail", "all"), ("prev_2fail", ph)]
            for key in keys: q1[key].append((c, nxt is not None, bool(nxt and nxt["cls"] == "def"), bool(nxt and nxt["cls"] == "off")))
    res["q1"] = {}
    for key, v in sorted(q1.items()):
        res["q1"][f"{key[0]}|{key[1]}"] = {"n_events": len(v), "p_next_exists": rci(U, [(c, int(h), 1) for c, h, d, o in v]),
                                           "p_def_given_next": rci(U, [(c, int(d), 1) for c, h, d, o in v if h]),
                                           "p_off_given_next": rci(U, [(c, int(o), 1) for c, h, d, o in v if h])}
    # ---- Q2: defensive share
    q2 = {}
    allx = [(M["cluster"], r) for M in Ms for r in X[M["id"]] if r["cls"] in ("off", "def")]
    def share(sel, name): q2[name] = rci(U, [(c, int(r["cls"] == "def"), 1) for c, r in allx if sel(r)])
    for ph in ("1x", "2x", "OT"): share(lambda r, ph=ph: r["ph"] == ph, "phase|" + ph)
    share(lambda r: True, "phase|all")
    for nm, f in (("ahead", lambda r: r["cd"] > 0), ("level", lambda r: r["cd"] == 0), ("behind", lambda r: r["cd"] < 0)):
        share(f, "crowns|" + nm)
        for ph in ("1x", "2x", "OT"): share(lambda r, f=f, ph=ph: f(r) and r["ph"] == ph, f"crowns|{nm}|{ph}")
    for nm, f in (("deficit(<-10%)", lambda r: r["hl"] < -0.10), ("even(+-10%)", lambda r: abs(r["hl"]) <= 0.10), ("lead(>+10%)", lambda r: r["hl"] > 0.10)):
        share(f, "hp|" + nm)
        share(lambda r, f=f: f(r) and r["sec"] >= 120, "hp_late|" + nm)
    res["q2"] = q2
    res["xbow_counts"] = {"all": sum(len(v) for v in X.values()), "off": sum(r["cls"] == "off" for _, r in allx), "def": sum(r["cls"] == "def" for _, r in allx),
                          "other": sum(r["cls"] == "other" for v in X.values() for r in v),
                          "off_status": dict(collections.Counter(r["status"] for _, r in allx if r["cls"] == "off"))}
    # ---- Q3: rockets
    q3 = {}
    ntr = lambda M, a, b: sum(1 for r in RK[M["id"]] if r["tower"] and a <= r["sec"] < b)
    for ph, (a, b) in {"1x": (0, 120), "2x": (120, 180), "OT": (180, 300)}.items():
        expo = [(M, max(0.0, min(M["end"] / 20.0, b) - a)) for M in Ms]
        q3[f"tower_rockets_per_min|{ph}"] = rci(U, [(M["cluster"], ntr(M, a, b), e / 60.0) for M, e in expo if e >= 5])
        pm = [(M["cluster"], ntr(M, a, b)) for M, e in expo if e >= 30]
        q3[f"tower_rockets_per_match|{ph}"] = rci(U, [(c, n, 1) for c, n in pm])
        q3[f"P(>=1 tower rocket)|{ph}"] = rci(U, [(c, int(n >= 1), 1) for c, n in pm])
        q3[f"P(>=2 tower rockets)|{ph}"] = rci(U, [(c, int(n >= 2), 1) for c, n in pm])
    q3["tower_rockets_per_match|whole"] = rci(U, [(M["cluster"], ntr(M, 0, 999), 1) for M in Ms])
    q3["P(>=2 tower rockets)|whole"] = rci(U, [(M["cluster"], int(ntr(M, 0, 999) >= 2), 1) for M in Ms])
    q3["rockets_total_per_match"] = rci(U, [(M["cluster"], len(RK[M["id"]]), 1) for M in Ms])
    q3["share_of_rockets_on_tower"] = rci(U, [(M["cluster"], ntr(M, 0, 999), len(RK[M["id"]])) for M in Ms])
    for nm, a in (("late(>=120s)", 120), ("OT(>=180s)", 180)):
        for st, f in (("level", lambda d: d == 0), ("ahead", lambda d: d > 0), ("behind", lambda d: d < 0)):
            rows = []; pm = []
            for M in Ms:
                end = M["end"] / 20.0
                if end <= a: continue
                mins = sum(f(crowns(M, g * 20)[0] - crowns(M, g * 20)[1]) for g in np.arange(a, end, 1.0)) / 60.0
                n = sum(1 for r in RK[M["id"]] if r["tower"] and r["sec"] >= a and f(r["cd"]))
                rows.append((M["cluster"], n, mins))
                if mins >= 0.5: pm.append((M["cluster"], n))
            q3[f"tower_rockets_per_{st}_minute|{nm}"] = rci(U, rows)
            if st == "level":
                q3[f"P(>=1 tower rocket | >=30s level)|{nm}"] = rci(U, [(c, int(n >= 1), 1) for c, n in pm])
                q3[f"P(>=2 tower rockets | >=30s level)|{nm}"] = rci(U, [(c, int(n >= 2), 1) for c, n in pm])
    for nm, f in (("<=25%", lambda f_: f_ <= .25), ("25-50%", lambda f_: .25 < f_ <= .5), (">50%", lambda f_: f_ > .5)):
        q3["tower_rocket_target_hp|" + nm] = rci(U, [(M["cluster"], sum(1 for r in RK[M["id"]] if r["tower"] and f(r["frac"])), ntr(M, 0, 999)) for M in Ms])
    q3["tower_rocket_target_hp<=1_rocket_dmg"] = rci(U, [(M["cluster"], sum(1 for r in RK[M["id"]] if r["tower"] and r["hp"] <= RD), ntr(M, 0, 999)) for M in Ms])
    opp = []
    for M in Ms:
        low = None
        for k in ("eK", "eL", "eR"):
            ser = M["HP"][k]; ok = np.where((ser > 0) & (ser <= 0.40 * M["MX"][k]))[0]
            if len(ok): t = int(M["T"][ok[0]]); low = t if low is None else min(low, t)
        if low is None or M["end"] - low < 400: continue
        opp.append((M["cluster"], int(any(r["tower"] and low <= r["tick"] < low + 400 for r in RK[M["id"]])), 1))
    q3["P(tower rocket within 20s | an enemy tower first <=40% HP)"] = rci(U, opp)
    res["q3"] = q3
    # ---- Q4: what follows a failed offensive X-Bow (30 s window)
    q4 = {}; cat = collections.defaultdict(list); match_first = {}
    for M in Ms:
        xs = X[M["id"]]; rk = RK[M["id"]]
        for i, r in enumerate(xs):
            if r["cls"] != "off" or r["status"] != "fail" or r["death"] is None: continue
            d0 = r["death"]
            if M["end"] - d0 < 300: continue
            w1 = min(d0 + WIN, M["end"])
            wp = [p for p in M["plays"] if d0 < p["tick"] <= w1 and (M["kind"] == "pro" or p["conf"])]
            wx = [q for q in xs if d0 < q["tick"] <= w1]
            off = any(q["cls"] == "off" for q in wx); dfx = any(q["cls"] == "def" for q in wx)
            tr = any(r2["tower"] and d0 < r2["tick"] <= w1 for r2 in rk); tes = any(p["name"] == "Tesla" for p in wp)
            el = float(M["EL"][max(int(np.searchsorted(M["T"], w1, "right")) - 1, 0)])
            two = i > 0 and xs[i - 1]["cls"] == "off" and xs[i - 1]["status"] == "fail" and xs[i - 1]["death"] is not None and r["tick"] > xs[i - 1]["death"]
            ev = {"c": M["cluster"], "off": off, "def": dfx, "trock": tr, "tesla": tes, "el": el, "ph": phase(d0 / 20.0), "hold": not (off or dfx or tr or tes), "res": M["res"], "tb": M.get("tiebreak")}
            cat["all"].append(ev); cat["ph_" + ev["ph"]].append(ev)
            if two: cat["2fail"].append(ev)
            match_first.setdefault(M["id"], ev)
    for k, evs in cat.items():
        f = lambda g: rci(U, [(e["c"], int(g(e)), 1) for e in evs])
        q4[k] = {"n": len(evs), "new_offensive_Xbow": f(lambda e: e["off"]), "defensive_Xbow": f(lambda e: e["def"]), "tower_Rocket": f(lambda e: e["trock"]), "Tesla": f(lambda e: e["tesla"]),
                 "defXbow_and_Tesla": f(lambda e: e["def"] and e["tesla"]), "no_offX_but_defX_or_towerRocket": f(lambda e: (not e["off"]) and (e["def"] or e["trock"])),
                 "none_of_Xbow/Tesla/towerRocket(hold)": f(lambda e: e["hold"]),
                 "median_elixir_at_window_end_when_hold": (float(np.median([e["el"] for e in evs if e["hold"]])) if any(e["hold"] for e in evs) else None)}
    mo = {}
    for nm, f in (("re-offend (new offensive X-Bow <=30s)", lambda e: e["off"]), ("no re-offend", lambda e: not e["off"]),
                  ("no re-offend, def X-Bow or tower Rocket", lambda e: (not e["off"]) and (e["def"] or e["trock"])), ("no re-offend, hold (no X-Bow/Tesla/rocket)", lambda e: e["hold"])):
        evs = [e for e in match_first.values() if f(e)]
        mo[nm] = {"n": len(evs), "win": rci(U, [(e["c"], int(e["res"] == "W"), 1) for e in evs]), "loss": rci(U, [(e["c"], int(e["res"] == "L"), 1) for e in evs])}
        if Ms[0]["kind"] == "pro": mo[nm]["win_with_equal_crowns(tiebreak)"] = rci(U, [(e["c"], int(e["res"] == "W" and e["tb"]), 1) for e in evs])
    q4["match_outcome_by_first_failure_response"] = mo
    res["q4"] = q4
    res["baseline"] = {"win": rci(U, [(M["cluster"], int(M["res"] == "W"), 1) for M in Ms if M["res"]])}
    if Ms[0]["kind"] == "pro": res["baseline"]["win_with_equal_crowns"] = rci(U, [(M["cluster"], int(M["res"] == "W" and M["tiebreak"]), 1) for M in Ms])
    # ---- Q5 counts
    qc = lambda key: int(res["q1"][key]["p_def_given_next"][4]) if key in res["q1"] and res["q1"][key]["p_def_given_next"][0] is not None else 0
    res["q5_counts"] = {"matches": len(Ms), "play_rows": sum(len(M["plays"]) for M in Ms), "xbow_rows": res["xbow_counts"]["all"], "xbow_def_rows": res["xbow_counts"]["def"],
                        "xbow_off_rows": res["xbow_counts"]["off"],
                        "xbow_def_by_phase": {ph: sum(1 for _, r in allx if r["cls"] == "def" and r["ph"] == ph) for ph in ("1x", "2x", "OT")},
                        "failed_offensive_xbow_events": sum(1 for _, r in allx if r["cls"] == "off" and r["status"] == "fail"),
                        "fail_then_next_xbow_pairs": qc("prev_fail|all"), "2fail_then_next_xbow_pairs": qc("prev_2fail|all"),
                        "def_xbow_right_after_fail": int(res["q1"].get("prev_fail|all", {}).get("p_def_given_next", (0,) * 5)[3]), "def_xbow_right_after_2fail": int(res["q1"].get("prev_2fail|all", {}).get("p_def_given_next", (0,) * 5)[3]),
                        "tower_rockets": sum(1 for v in RK.values() for r in v if r["tower"]),
                        "matches_with_ge2_tower_rockets_in_a_phase": sum(1 for M in Ms if any(ntr(M, a, b) >= 2 for a, b in ((0, 120), (120, 180), (180, 300)))),
                        "level_late_tower_rocket_rows(>=120s)": sum(1 for v in RK.values() for r in v if r["tower"] and r["sec"] >= 120 and r["cd"] == 0),
                        "failure_windows(>=15s left)": len(cat["all"]), "failure_windows_no_reoffend": sum(1 for e in cat["all"] if not e["off"]),
                        "failure_windows_no_reoffend_with_defX_or_towerRocket": sum(1 for e in cat["all"] if not e["off"] and (e["def"] or e["trock"]))}
    return res, X

def main():
    pros = pickle.load(open(HERE + "pros.pkl", "rb")); bot = pickle.load(open(HERE + "bot.pkl", "rb"))
    RDp, nrp = rocket_damage(pros); RDb, nrb = rocket_damage(bot)
    print("rocket tower dmg pros", RDp, nrp, "bot", RDb, nrb, flush=True)
    out = {}; allX = {}
    for M in bot:  # live xy are normalized tile centres; undo the 4-dp rounding so (+-1,13)-tile cells are not misclassified at the reach boundary
        for p in M["plays"]: p["x"] = math.floor(p["x"]) + 0.5; p["y"] = math.floor(p["y"]) + 0.5
    for M in pros: M["tiebreak"] = M["term"].startswith("native_tiebreak")  # engine-side: real crowns never tie, so tiebreak is engine termination
    for M in bot: M["tiebreak"] = M["end"] >= 5900   # approx: ran to the clock (>=295 s)
    pro_clean = [M for M in pros if M["crowns_match"] and M["eng_agree"]]
    for k, (Ms, RD) in {"pros_all": (pros, RDp), "pros_engine_agrees": (pro_clean, RDp), "bot": (bot, RDb), "bot_r1e31": ([M for M in bot if M["model"] == "rseries_r1e31"], RDb)}.items():
        out[k], allX[k] = analyze(Ms, RD); print(k, "done", flush=True)
    out["meta"] = {"pros_icebow_sides": len(pros), "pros_replays": len({M["cluster"] for M in pros}), "pro_engine_agrees": len(pro_clean), "bot_matches": len(bot),
                   "bot_models": dict(collections.Counter(M["model"] for M in bot)), "bot_result": dict(collections.Counter(str(M["res"]) for M in bot)),
                   "pro_result": dict(collections.Counter(M["res"] for M in pros)), "pro_side": dict(collections.Counter(M["side"] for M in pros)),
                   "pro_term": dict(collections.Counter(M["term"] for M in pros)), "RD": {"pro": RDp, "bot": RDb, "n_pro": nrp, "n_bot": nrb}}
    json.dump(out, open(HERE + "results.json", "w"), indent=1, default=str)
    pickle.dump(allX, open(HERE + "xrows.pkl", "wb"))
    print("saved")

if __name__ == "__main__":
    main()
