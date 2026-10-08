"""Rocket use, Rocket eligibility and X-Bow class by phase for three LIVE groups, with the SAME definitions as the pro comparison
(xbow_switch/extract.py build_bot + analyze.py; rocket_lead/analyze_rk.py eligibility). Read-only on logs and on the reference tools.
Writes live_records.pkl + live_results.json in this folder."""
import sys, os, glob, json, math, pickle, bisect, datetime, collections, ctypes
import numpy as np
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
L73 = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/"
HERE = L73 + "rocket_xbow_1008/"
sys.path.insert(0, L73 + "live_review"); sys.path.insert(0, L73 + "xbow_switch")
import load as L, core
import analyze as A  # before extract: extract.py puts live_review (which has its own analyze.py) first on sys.path
import extract as X
assert hasattr(A, "xbow_rows")
B = 2000; RNG = np.random.default_rng(3)
PH = {"1x": (0, 120), "2x": (120, 180), "OT": (180, 300)}

def start_info(f):
    st, end = None, False
    with open(f) as fh:
        for l in fh:
            if l.startswith('{"event": "start"'): st = json.loads(l)
            elif l.startswith('{"event": "end"') or l.startswith('{"event": "stop"'): end = True
    return st or {}, end

def group_of(base, st):
    ts = base[10:25]; sha = (st.get("ckpt_sha256") or "")[:8]; al = st.get("anti_leak")
    if sha == "76fdfaac" and "20261004" <= ts[:8] <= "20261006": return "a_R1e"
    if sha == "e7359f2b" and ts >= "20261008_040027":
        if al is True: return "b_stack_AL_on"
        if al is False: return "c_stack_AL_off"
    return None

def build_one(f, outs, ot):
    """extract.build_bot per-file body, verbatim logic (nav result, tower HP series, X-Bow tracks, plays), plus own hand/elixir states."""
    d = L.load(f); b = os.path.basename(f)
    st = datetime.datetime.strptime(b[10:25], "%Y%m%d_%H%M%S").timestamp()
    sec = (d["end"] or {}).get("seconds") or ((d["stop"] or {}).get("tick") or 3600) / 20.0
    i = bisect.bisect_left(ot, st + sec - 20); res = {}
    if i < len(ot) and ot[i] < st + sec + 300: res[b] = "WIN" if outs[i][1] else "LOSS"
    if not d["states"]: return None
    m = core.build(d, res)
    if m is None or m["obs"] is None: return None
    S = d["states"]; T = np.array([s["tick"] for s in S]); HP = {}; MX = {}
    for sl in X.SLOTS:
        ser = m["tower_hp"].get(sl, []); MX[sl] = ser[0][2] if ser else None
        arr = np.zeros(len(T)); j = 0; cur = None; dead = m["dead"].get(sl)
        for k, t in enumerate(T):
            while j < len(ser) and ser[j][0] <= t: cur = ser[j][1]; j += 1
            arr[k] = 0 if (dead is not None and t >= dead) else (cur if cur is not None else (ser[0][1] if ser else 0))
        HP[sl] = arr
    for sl in X.SLOTS:
        if MX[sl] is None: MX[sl] = 4824 if sl.endswith("K") else 3052
    xb = {}
    for s in S:
        for bd in s["bodies"]:
            if bd[3] == 27000008 and bd[0] == m["obs"]:
                x, y = core.to_own(m["obs"], bd[1], bd[2]); t = xb.setdefault(bd[7], {"first": s["tick"], "x": x, "y": y}); t["last"] = s["tick"]
    for t in xb.values(): t["cens"] = t["last"] >= T[-1] - 15
    plays = [{"tick": p["tick"], "name": p["name"], "x": math.floor(p["x"]) + 0.5, "y": math.floor(p["y"]) + 0.5, "el": p["elixir"], "conf": p["conf"]} for p in m["plays"]]
    res_m = {"WIN": "W", "LOSS": "L", "DRAW": "D"}.get(m["result"].rstrip("*") if m["result"] else None)
    return {"kind": "bot", "id": m["file"], "cluster": m["file"], "res": res_m, "tiebreak": int(T[-1]) >= 5900, "end": int(T[-1]), "T": T, "HP": HP, "MX": MX,
            "EL": np.array([s["el"] for s in S]), "plays": plays, "xtracks": list(xb.values()), "ckpt": m["ckpt_sha"], "obs": m["obs"],
            "states": [(s["tick"], s["el"], s["hand"]) for s in S]}

def build():
    outs = X.nav_outcomes(); ot = [o[0] for o in outs]; G = collections.defaultdict(list); cfg = collections.defaultdict(collections.Counter); skipped = collections.Counter()
    for f in sorted(glob.glob(L.D + "live_play_2026100[4-8]_*.jsonl")):
        st, end = start_info(f); g = group_of(os.path.basename(f), st)
        if g is None: continue
        if not end: skipped[g] += 1; continue
        M = build_one(f, outs, ot)
        if M is None: skipped[g + "_nostate"] += 1; continue
        G[g].append(M); do = st.get("decision_options") or {}
        cfg[g][f"tau={st.get('tau')} tau_phase={do.get('tau_phase')} xbow_class={do.get('xbow_class')}/{do.get('xbow_class_floor')} al={st.get('anti_leak')}/{st.get('anti_leak_elixir')}"] += 1
    pickle.dump({"G": dict(G), "cfg": {k: dict(v) for k, v in cfg.items()}, "skipped": dict(skipped)}, open(HERE + "live_records.pkl", "wb"))
    return dict(G), cfg, skipped

# ---------------- metrics (cluster = match; ratio of sums with match bootstrap, as A.rci)
def rci(U, rows): return list(A.rci(U, rows))

def exposure(M, a, b): return max(0.0, min(M["end"] / 20.0, b) - a)

def metrics(Ms, kind):
    """kind 'bot' (conf plays only, as the reference) or 'pro' (accepted plays)."""
    U = [M["cluster"] for M in Ms]; out = {"n_matches": len(Ms)}
    ok = (lambda p: True) if kind == "pro" else (lambda p: p["conf"])
    for ph, (a, b) in PH.items():
        ins = lambda p: a <= p["tick"] / 20.0 < b
        pm = [M for M in Ms if exposure(M, a, b) >= 30]   # analyze.py q3 per-match rule
        out[f"rockets_per_match|{ph}"] = rci(U, [(M["cluster"], sum(1 for p in M["plays"] if ok(p) and ins(p) and p["name"] == "Rocket"), 1) for M in pm])
        out[f"rocket_pct_plays|{ph}"] = rci(U, [(M["cluster"], sum(1 for p in M["plays"] if ok(p) and ins(p) and p["name"] == "Rocket"), sum(1 for p in M["plays"] if ok(p) and ins(p))) for M in Ms])
        out[f"elixir_at_play|{ph}"] = rci(U, [(M["cluster"], sum(p["el"] for p in M["plays"] if ok(p) and ins(p) and p["el"] is not None), sum(1 for p in M["plays"] if ok(p) and ins(p) and p["el"] is not None)) for M in Ms])
    out["rocket_pct_plays|all"] = rci(U, [(M["cluster"], sum(1 for p in M["plays"] if ok(p) and p["name"] == "Rocket"), sum(1 for p in M["plays"] if ok(p))) for M in Ms])
    out["reached_OT"] = rci(U, [(M["cluster"], int(exposure(M, 180, 300) >= 30), 1) for M in Ms])
    return out

def eligibility(Ms):
    """rocket_lead/analyze_rk.py bot branch: per decision state, dt = min(next-tick gap, 60)/20 s (last state 10 ticks); in hand = 'Rocket' in own hand;
    eligible = in hand and floor(elixir + 1e-3) >= 6. Plus Rocket plays (conf) split tower / non-tower by A.tower_target, per eligible minute."""
    U = [M["cluster"] for M in Ms]; rows = collections.defaultdict(list)
    for M in Ms:
        st = [s for s in M["states"] if s[2] is not None]
        if not st: continue
        c = M["cluster"]; tk = np.array([s[0] for s in st])
        dt = np.array([(min(tk[k + 1] - tk[k], 60) if k + 1 < len(st) else 10) / 20.0 for k in range(len(st))])
        inh = np.array(["Rocket" in s[2] for s in st]); el = inh & np.array([math.floor(s[1] + 1e-3) >= 6 for s in st])
        ph = (tk / 20.0 >= 120).astype(int) + (tk / 20.0 >= 180).astype(int)
        for i, nm in enumerate(PH):
            sel = ph == i
            if not sel.any(): continue
            rk = [p for p in M["plays"] if p["name"] == "Rocket" and p["conf"] and PH[nm][0] <= p["tick"] / 20.0 < PH[nm][1]]
            ntw = sum(1 for p in rk if A.tower_target(M, p["x"], p["y"], p["tick"]))
            rows[nm].append((c, dt[sel].sum(), dt[sel & inh].sum(), dt[sel & el].sum(), len(rk), ntw))
    out = {}
    for nm in list(PH) + ["all"]:
        R = [r for k in PH for r in rows[k]] if nm == "all" else rows[nm]
        out[f"elig_share|{nm}"] = rci(U, [(c, e, t) for c, t, h, e, n, w in R])
        out[f"P(el>=6|in hand)|{nm}"] = rci(U, [(c, e, h) for c, t, h, e, n, w in R])
        out[f"rockets_per_elig_min|{nm}"] = rci(U, [(c, n, e / 60) for c, t, h, e, n, w in R])
        out[f"tower_rockets_per_elig_min|{nm}"] = rci(U, [(c, w, e / 60) for c, t, h, e, n, w in R])
        out[f"rockets_per_match_min|{nm}"] = rci(U, [(c, n, t / 60) for c, t, h, e, n, w in R])
        out[f"minutes|{nm}"] = [sum(r[1] for r in R) / 60, sum(r[3] for r in R) / 60]
    return out

def summarize(Ms, RD=497.0):
    r, _ = A.analyze(Ms, RD)   # analyze.py exactly: q2 defensive share by phase, q3 tower Rockets per match by phase, rockets_total_per_match
    keep = {k: v for k, v in r["q2"].items() if k.startswith("phase|")}
    keep.update({k: v for k, v in r["q3"].items() if k.startswith("tower_rockets_per_match|") or k == "rockets_total_per_match" or k.startswith("P(>=1 tower rocket)|")})
    keep["xbow_counts"] = r["xbow_counts"]; keep["xbow_def_by_phase"] = r["q5_counts"]["xbow_def_by_phase"]
    allx = collections.Counter()
    for M in Ms:
        for row in A.xbow_rows(M, RD): allx[(row["ph"], row["cls"])] += 1
    keep["xbow_class_by_phase"] = {f"{p}|{c}": n for (p, c), n in sorted(allx.items())}
    keep.update(metrics(Ms, "bot")); keep.update(eligibility(Ms))
    keep["win"] = r["baseline"]["win"]
    return keep

if __name__ == "__main__":
    if os.path.exists(HERE + "live_records.pkl") and "--rebuild" not in sys.argv:
        D = pickle.load(open(HERE + "live_records.pkl", "rb")); G, cfg, skipped = D["G"], D["cfg"], D["skipped"]
    else: G, cfg, skipped = build()
    excl = {g: [M["id"] for M in v if len(M["plays"]) < 5] for g, v in G.items()}   # live_eval.py rule: < 5 plays is not a match (stuck-loading logs)
    G = {g: [M for M in v if len(M["plays"]) >= 5] for g, v in G.items()}
    out = {"meta": {"excluded_lt5_plays": excl, "n": {g: len(v) for g, v in G.items()}, "cfg": {k: dict(v) for k, v in cfg.items()}, "skipped": dict(skipped),
                    "ids": {g: [v[0]["id"], v[-1]["id"]] for g, v in G.items()}}}
    for g in sorted(G): out[g] = summarize(G[g]); print(g, "done", len(G[g]), flush=True)
    # pros: same per-phase helpers on the reference pros.pkl (rockets per match / % of plays / elixir at play by phase)
    P = pickle.load(open(L73 + "xbow_switch/pros.pkl", "rb")); out["pros_extra"] = metrics(P, "pro")
    json.dump(out, open(HERE + "live_results.json", "w"), indent=1, default=str); print("saved")
