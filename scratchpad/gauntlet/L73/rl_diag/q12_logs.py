"""L73 rl_diag Q1/Q2/Q4: does training punish what live punishes? EXISTING logs only, CPU, read-only outside this folder.

Q1  win ~ economy feature, per match: LIVE (R1e results_R1e.json) vs SIM ghost screens (behaviour telemetry) vs SIM reactive
    (search_s0) vs RL training aggregates (train_log.jsonl, per update).
Q2  win rate by opponent class (live_eval.classify / traits) live vs sim reactive vs ghost screen; RL opponent policy + deck mix.
Q4  RL signal-size numbers from train_log.jsonl.
run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/rl_diag/q12_logs.py   -> q12_results.json + q12_report.txt
"""
import os, sys, json, glob, math, collections
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "../../../.."))
sys.path.insert(0, os.path.join(REPO, "scratchpad/gauntlet/L73/live_eval"))
import live_eval as LE                       # classify / traits / wilson / PHASES (module has a main guard; sets below-normal prio)

L73 = os.path.join(REPO, "scratchpad/gauntlet/L73")
OUT = []
def P(*a): OUT.append(" ".join(str(x) for x in a))

# ------------------------------------------------------------------ stats (numpy only)
def logit_fit(X, y, ridge=1e-3, it=50):
    """IRLS logistic regression with intercept prepended; returns (beta, se)."""
    X = np.column_stack([np.ones(len(X)), X]).astype(float); y = np.asarray(y, float)
    b = np.zeros(X.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30))); W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + ridge * np.eye(X.shape[1]); g = X.T @ (y - p) - ridge * b
        st = np.linalg.solve(H, g); b += st
        if np.abs(st).max() < 1e-8: break
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    return b, se

def ncdf(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))

def slope(x, y, fe=None):
    """win ~ x (+ fixed effects). Reports OR per 1 unit and per 1 SD of x, with 95% CI and p."""
    x = np.asarray(x, float); y = np.asarray(y, float); m = np.isfinite(x)
    x, y = x[m], y[m]
    if fe is not None:
        fe = np.asarray(fe)[m]; lv = sorted(set(fe))[1:]
        D = np.column_stack([(fe == v).astype(float) for v in lv]) if lv else np.zeros((len(x), 0))
    else:
        D = np.zeros((len(x), 0))
    n, k = len(x), int(y.sum())
    if n < 10 or k in (0, n): return {"n": n, "wins": k, "note": "degenerate"}
    b, se = logit_fit(np.column_stack([x, D]), y)
    sd = float(x.std())
    z = b[1] / se[1]
    return {"n": n, "wins": k, "losses": n - k, "x_mean": float(x.mean()), "x_sd": sd,
            "x_mean_win": float(x[y == 1].mean()), "x_mean_loss": float(x[y == 0].mean()),
            "OR_per_unit": math.exp(b[1]), "OR_per_unit_ci": [math.exp(b[1] - 1.96 * se[1]), math.exp(b[1] + 1.96 * se[1])],
            "OR_per_sd": math.exp(b[1] * sd), "OR_per_sd_ci": [math.exp((b[1] - 1.96 * se[1]) * sd), math.exp((b[1] + 1.96 * se[1]) * sd)],
            "p": 2 * (1 - ncdf(abs(z)))}

def wr(k, n):
    lo, hi = LE.wilson(k, n) if n else (float("nan"), float("nan"))
    return {"W": k, "n": n, "wr": k / n if n else None, "ci": [lo, hi]}

def phase_econ(plays, key_tick="tick", key_el="elixir"):
    """mean elixir-at-play per phase (needs >=3 plays in the phase) + all."""
    d = {p: [] for p, _, _ in LE.PHASES}
    for q in plays:
        p = next(p for p, a, b in LE.PHASES if a <= q[key_tick] < b); d[p].append(q[key_el])
    out = {p: (float(np.mean(v)) if len(v) >= 3 else float("nan")) for p, v in d.items()}
    allv = [e for v in d.values() for e in v]
    out["all"] = float(np.mean(allv)) if len(allv) >= 3 else float("nan")
    return out

def base_name(c): return c.split("@")[0]
CLASSES = ["Golem", "Mega Knight"]
def group_flags(cards):
    c = {base_name(x) for x in cards}
    t = LE.traits(c); cl = LE.classify(c)
    return {"class Golem": cl == "Golem", "class Mega Knight": cl == "Mega Knight", "MegaKnight card": "MegaKnight" in c,
            "trait heavy tank": t["heavy tank"], "trait Witch/Night Witch": t["has Witch/Night Witch"], "class Lava Hound": cl == "Lava Hound",
            "class Giant": cl == "Giant (incl. Goblin/Electro)", "class Hog": cl == "Hog (incl. Royal Hogs)", "class X-Bow/Mortar": cl == "X-Bow/Mortar", "ALL": True}
GROUPS = ["ALL", "class Golem", "trait heavy tank", "trait Witch/Night Witch", "class Mega Knight", "MegaKnight card",
          "class Lava Hound", "class Giant", "class Hog", "class X-Bow/Mortar"]

R = {}
# ================================================================== LIVE
live = json.load(open(os.path.join(L73, "live_eval/results_R1e.json")))
LM = [m for m in live["matches"] if m["result"] in ("WIN", "LOSS") and m["n_plays"] >= 5]
lv = {"win": [], "e1x": [], "e2x": [], "eOT": [], "eall": [], "ppm": [], "net1x": [], "net1x_has": []}
for m in LM:
    lv["win"].append(m["result"] == "WIN")
    pp = m["plays_phase"]
    for p in ("1x", "2x", "OT"):
        n, s = pp[p]; lv["e" + p].append(s / n if n >= 3 else float("nan"))
    N = sum(pp[p][0] for p in pp); S = sum(pp[p][1] for p in pp)
    lv["eall"].append(S / N if N >= 3 else float("nan"))
    lv["ppm"].append(N / (m["dur_s"] / 60))
    if m.get("dmg") and m["hp_total"]["dealt"] and m["hp_total"]["taken"]:
        lv["net1x"].append(m["dmg"]["dealt"]["1x"] / m["hp_total"]["dealt"] - m["dmg"]["taken"]["1x"] / m["hp_total"]["taken"])
    else:
        lv["net1x"].append(float("nan"))
y = np.array(lv["win"], float)
R["live"] = {"n": len(LM), "wins": int(y.sum()), **{f: slope(lv[f], y) for f in ("e1x", "e2x", "eOT", "eall", "ppm", "net1x")}}

# ================================================================== SIM ghost screens (behaviour telemetry; pinned pro replays, scripted opponent)
GH = {"chain2 r1e": "chain2/screen_r1e.jsonl", "econ t0.35 (r1e)": "econ_tau/screen_t0.35.jsonl",
      "econ t0.45 (r1e)": "econ_tau/screen_t0.45.jsonl", "econ t0.54 (r1e)": "econ_tau/screen_t0.54.jsonl",
      "chain2 v31c": "chain2/screen_v31c.jsonl", "chain2 v32": "chain2/screen_v32.jsonl",
      "chain2 v32b": "chain2/screen_v32b.jsonl", "chain2 r1f_u0080": "chain2/screen_r1f_u0080.jsonl"}
pool = {}
for l in open(os.path.join(REPO, "icebow/data/ghost_pool/pool_env_v1.jsonl"), encoding="utf-8"):
    e = json.loads(l); pool[e["tag"]] = e
G = []
for name, f in GH.items():
    for l in open(os.path.join(L73, f)):
        r = json.loads(l)
        if r["outcome"] not in ("win", "loss"): continue
        acc = [q for q in r["plays"] if q.get("accepted")]
        e = phase_econ(acc)
        G.append({"src": name, "r1e": "r1e" in name, "win": r["outcome"] == "win", **{"e" + k: v for k, v in e.items()},
                  "ppm": r["accepted_per_min"], "tag": r["tag"], "real": r.get("real_outcome"),
                  "ghost_deck": [c["name"] for c in pool[r["tag"]]["ghost_deck"]] if r["tag"] in pool else None})
def gsl(rows, fe):
    y = np.array([g["win"] for g in rows], float)
    return {"n": len(rows), "wins": int(y.sum()), **{f: slope([g[f] for g in rows], y, [g["src"] for g in rows] if fe else None)
                                                    for f in ("e1x", "e2x", "eOT", "eall", "ppm")}}
R["ghost_r1e_tau035"] = gsl([g for g in G if g["src"] in ("chain2 r1e", "econ t0.35 (r1e)")], True)
R["ghost_all_fe"] = gsl(G, True)
R["ghost_by_src"] = {s: {"wins": sum(g["win"] for g in G if g["src"] == s), "n": sum(1 for g in G if g["src"] == s),
                         "e1x": float(np.nanmean([g["e1x"] for g in G if g["src"] == s])),
                         "e2x": float(np.nanmean([g["e2x"] for g in G if g["src"] == s])),
                         "eall": float(np.nanmean([g["eall"] for g in G if g["src"] == s])),
                         "ppm": float(np.mean([g["ppm"] for g in G if g["src"] == s]))} for s in GH}

# ================================================================== SIM reactive (search_s0; opp gen_v1 on census decks, or S1 icebow mirror)
RX = []
for d in sorted(glob.glob(os.path.join(L73, "*/react*/matches.jsonl"))):
    src = os.path.relpath(os.path.dirname(d), L73).replace("\\", "/")
    for l in open(d):
        r = json.loads(l)
        if r["outcome"] not in ("win", "loss"): continue
        RX.append({"src": src, "opp": r["opp"],
                   "win": r["outcome"] == "win", "ppm": r["plays_accepted"] / (r["end_tick"] / 20 / 60),
                   "opp_ppm": r["opp_plays_accepted"] / (r["end_tick"] / 20 / 60), "deck": r["opp_deck"], "seed": r["seed"],
                   "hpdiff": r["tower_hp_diff"]})
yR = np.array([r["win"] for r in RX], float)
R["reactive_all_fe"] = {"n": len(RX), "wins": int(yR.sum()), "ppm": slope([r["ppm"] for r in RX], yR, [r["src"] + r["opp"] for r in RX]),
                        "ppm_minus_opp": slope([r["ppm"] - r["opp_ppm"] for r in RX], yR, [r["src"] + r["opp"] for r in RX])}
R["reactive_sources"] = sorted({r["src"] for r in RX})
# intervention: R1e at tau .35/.45/.54 (econ_tau) -- same model, same seeds, only the play threshold changes
R["econ_tau_intervention"] = {}
for t in ("0.35", "0.45", "0.54"):
    rows = [r for r in RX if r["src"] in (f"econ_tau/react_t{t}", f"econ_tau/reactevo_t{t}")]
    gh = [g for g in G if g["src"] == f"econ t{t} (r1e)"]
    R["econ_tau_intervention"][t] = {"reactive": wr(sum(r["win"] for r in rows), len(rows)),
                                     "reactive_gen_only": wr(sum(r["win"] for r in rows if r["opp"] == "gen"), sum(r["opp"] == "gen" for r in rows)),
                                     "reactive_ppm": float(np.mean([r["ppm"] for r in rows])),
                                     "ghost": wr(sum(g["win"] for g in gh), len(gh)), "ghost_ppm": float(np.mean([g["ppm"] for g in gh])),
                                     "ghost_e1x": float(np.nanmean([g["e1x"] for g in gh])), "ghost_e2x": float(np.nanmean([g["e2x"] for g in gh])),
                                     "ghost_eOT": float(np.nanmean([g["eOT"] for g in gh]))}

# ================================================================== RL training rollouts (per-update aggregates only; no per-match file exists)
def train_log(run):
    rs = [json.loads(l) for l in open(os.path.join(REPO, f"scratchpad/gauntlet/L68/rl/{run}/train_log.jsonl"))]
    return rs[0], [r for r in rs if r.get("type") == "update"]
cfgrec, U = train_log("rseries_r1e31")
wrU = np.array([u["winrate"] for u in U]); elU = np.array([u["elixir_at_play_mean"] for u in U]); ppmU = np.array([u["plays_per_min"] for u in U])
s1sh = np.array([u["league"]["by_opp"]["s1"]["n"] / u["matches"] for u in U]); initsh = np.array([u["league"]["by_opp"]["init"]["n"] / u["matches"] for u in U])
Xo = np.column_stack([elU, s1sh, initsh, np.arange(len(U)) / len(U)])
bo, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(U)), Xo]), wrU, rcond=None)
res = wrU - np.column_stack([np.ones(len(U)), Xo]) @ bo
s2 = res @ res / (len(U) - Xo.shape[1] - 1)
cov = s2 * np.linalg.inv(np.column_stack([np.ones(len(U)), Xo]).T @ np.column_stack([np.ones(len(U)), Xo]))
R["rl_train_per_update"] = {"updates": len(U), "corr_wr_elixir": float(np.corrcoef(wrU, elU)[0, 1]), "corr_wr_ppm": float(np.corrcoef(wrU, ppmU)[0, 1]),
                            "ols_dwr_per_elixir_ctrl_mix_time": [float(bo[1]), float(bo[1] - 1.96 * math.sqrt(cov[1, 1])), float(bo[1] + 1.96 * math.sqrt(cov[1, 1]))],
                            "elixir_at_play_mean": [float(elU[:10].mean()), float(elU[-10:].mean())], "ppm": [float(ppmU[:10].mean()), float(ppmU[-10:].mean())],
                            "note": "64-match aggregates; between-update elixir sd %.3f" % elU.std()}

# ================================================================== Q2 opponent classes
def by_group(rows, deck_key):
    out = {}
    for gname in GROUPS:
        sel = [r for r in rows if r[deck_key] is not None and group_flags(r[deck_key])[gname]]
        out[gname] = wr(sum(r["win"] for r in sel), len(sel))
        out[gname]["distinct_decks"] = len({tuple(sorted(r[deck_key])) for r in sel})
    return out
LQ = [{"win": m["result"] == "WIN", "deck": m["opp_cards"]} for m in LM if m.get("opp_cards") is not None]
R["q2_live"] = by_group(LQ, "deck")
RG = [r for r in RX if r["opp"] == "gen"]
R["q2_reactive_r1e"] = by_group([r for r in RG if r["src"] in ("chain2/react_r1e", "chain2/reactevo_r1e", "econ_tau/react_t0.35", "econ_tau/reactevo_t0.35")], "deck")
R["q2_reactive_all_models"] = by_group(RG, "deck")
R["q2_reactive_s1_mirror"] = wr(sum(r["win"] for r in RX if r["opp"] == "s1"), sum(r["opp"] == "s1" for r in RX))
GR = [g for g in G if g["src"] in ("chain2 r1e", "econ t0.35 (r1e)")]
R["q2_ghost_r1e"] = by_group(GR, "ghost_deck")
# the pro icebow player's REAL result on the same replays the ghost opponent replays (same deck, same opponent commands)
R["q2_ghost_real_pro"] = by_group([{"win": g["real"] == "win", "ghost_deck": g["ghost_deck"]} for g in GR if g["src"] == "chain2 r1e"], "ghost_deck")

# RL training opponents: policy mix + deck-class exposure (no per-match outcome is logged in training)
pol = collections.Counter(); polW = collections.Counter(); cls = collections.Counter(); ngames = 0
decks = {f"r{d['rank']}": d["engine"] for d in json.load(open(os.path.join(REPO, "scratchpad/gauntlet/L70/pool_forms/loadable_decks.json")))["decks"]}
decks["icebow"] = ["Tornado", "Tesla", "IceWizard", "Xbow", "Rocket", "Knight", "Log", "Skeletons"]
G_ = cfgrec["config"]["G"]
for u in U:
    for k, v in u["league"]["by_opp"].items(): pol[k] += v["n"]; polW[k] += v["W"]
    for m in u["matchups"]:
        f = group_flags(decks.get(m["opp_deck"], []))
        for gname in GROUPS:
            if f[gname]: cls[gname] += G_
        cls["icebow mirror"] += G_ * (m["opp_deck"] == "icebow")
tot = sum(pol.values())
R["q2_rl_opp_mix"] = {k: {"games": pol[k], "share": pol[k] / tot, "learner_wr": polW[k] / pol[k]} for k in pol}
R["q2_rl_deck_exposure"] = {k: {"games": v, "share": v / cls["ALL"]} for k, v in cls.items()}
R["q2_rl_cfg"] = {k: cfgrec["config"][k] for k in ("league_mix", "league_opp_policy", "league_icebow_share", "league_learner_icebow_share", "T", "tau", "E", "G")}
# sampled-play win rate vs FIXED opponents over training (Q3 evidence: does R1e beat base / S1 more under T=0.5?)
def blk(a, b, k):
    W = sum(u["league"]["by_opp"][k]["W"] for u in U[a:b]); N = sum(u["league"]["by_opp"][k]["n"] for u in U[a:b]); return wr(W, N)
R["q3_sampled_vs_fixed"] = {k: {"u0000-0009": blk(0, 10, k), "u0010-0049": blk(10, 50, k), "u0050-0099": blk(50, 100, k), "u0100-0154": blk(100, 155, k)}
                            for k in ("init", "s1")}

# ================================================================== Q4 signal size
gae = [u["gae"] for u in U if "gae" in u]
R["q4"] = {"matches_per_update": float(np.mean([u["matches"] for u in U])), "updates": len(U), "total_matches": int(sum(u["matches"] for u in U)),
           "rows_per_update": float(np.mean([u["rows"] for u in U])), "rows_played_per_update": float(np.mean([u["rows_played"] for u in U])),
           "rows_per_match": float(np.mean([u["rows"] / u["matches"] for u in U])),
           "adv_std": [float(np.mean([g["adv_std"] for g in gae])), float(np.min([g["adv_std"] for g in gae])), float(np.max([g["adv_std"] for g in gae]))],
           "explained_var": [float(np.mean([g["explained_var"] for g in gae[5:]])), float(np.min([g["explained_var"] for g in gae[5:]])), float(np.max([g["explained_var"] for g in gae[5:]]))],
           "stochastic_share": float(np.mean([u["stochastic_share"] for u in U])),
           "kl_gate_last10": float(np.mean([u["kl_gate"] for u in U[-10:]])), "kl_card_last10": float(np.mean([u["kl_card"] for u in U[-10:]])),
           "kl_cell_last10": float(np.mean([u["kl_cell"] for u in U[-10:]])), "kl_target": cfgrec["config"]["kl_target"],
           "beta_last": U[-1]["beta_next"], "beta_min": cfgrec["config"]["beta_min"], "clip_frac_mean": float(np.mean([u["clip_frac"] for u in U])),
           "lr": cfgrec["config"]["lr"], "ppo_epochs": cfgrec["config"]["ppo_epochs"], "gae_lambda": cfgrec["config"]["gae_lambda"],
           "gae_gamma_tick": cfgrec["config"]["gae_gamma_tick"], "decide_every": cfgrec["config"].get("decide_every"),
           "p_gate_mean": [float(np.mean([u["p_gate_mean"] for u in U[:10]])), float(np.mean([u["p_gate_mean"] for u in U[-10:]]))],
           "winrate_per_update_sd": float(wrU.std()), "binomial_sd_at_64": math.sqrt(0.25 / 64)}

json.dump(R, open(os.path.join(HERE, "q12_results.json"), "w"), indent=1, default=float)

# ------------------------------------------------------------------ report
def f(x, d=2): return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"
def row(lbl, s):
    if "OR_per_unit" not in s: return f"  {lbl:34s} n={s['n']} {s.get('note')}"
    return (f"  {lbl:34s} n={s['n']:4d} L={s['losses']:3d}  mean W/L {f(s['x_mean_win'])}/{f(s['x_mean_loss'])}  "
            f"OR/unit {f(s['OR_per_unit'])} [{f(s['OR_per_unit_ci'][0])},{f(s['OR_per_unit_ci'][1])}]  "
            f"OR/SD {f(s['OR_per_sd'])} [{f(s['OR_per_sd_ci'][0])},{f(s['OR_per_sd_ci'][1])}]  p={s['p']:.3g}")
P("Q1  win ~ feature (logistic; OR>1 = more of x -> more wins). elixir features = mean own elixir at accepted plays.")
for src in ("live", "ghost_r1e_tau035", "ghost_all_fe"):
    P(f" [{src}] n={R[src]['n']} wins={R[src]['wins']}")
    for k in ("e1x", "e2x", "eOT", "eall", "ppm", "net1x"):
        if k in R[src]: P(row(k, R[src][k]))
P(f" [reactive_all_fe] n={R['reactive_all_fe']['n']} wins={R['reactive_all_fe']['wins']}")
P(row("ppm (own plays/min)", R["reactive_all_fe"]["ppm"])); P(row("ppm - opp ppm", R["reactive_all_fe"]["ppm_minus_opp"]))
P(" [econ_tau intervention, R1e, only tau changes]")
for t, v in R["econ_tau_intervention"].items():
    P(f"  tau {t}: reactive {v['reactive']['W']}/{v['reactive']['n']} (gen-opp {v['reactive_gen_only']['W']}/{v['reactive_gen_only']['n']}) ppm {f(v['reactive_ppm'])} | "
      f"ghost {v['ghost']['W']}/{v['ghost']['n']} ppm {f(v['ghost_ppm'])} e@play 1x/2x/OT {f(v['ghost_e1x'])}/{f(v['ghost_e2x'])}/{f(v['ghost_eOT'])}")
P(" [ghost by source]"); [P(f"  {s:20s} {v['wins']}/{v['n']} e1x {f(v['e1x'])} e2x {f(v['e2x'])} eall {f(v['eall'])} ppm {f(v['ppm'])}") for s, v in R["ghost_by_src"].items()]
P(f" [rl train per update] {json.dumps(R['rl_train_per_update'], default=float)}")
P("\nQ2  win rate by opponent group (W/n, Wilson 95%)")
srcs = ("q2_live", "q2_reactive_r1e", "q2_reactive_all_models", "q2_ghost_r1e", "q2_ghost_real_pro")
P("  " + f"{'group':26s}" + "".join(f"{s[3:]:>28s}" for s in srcs))
for gname in GROUPS:
    cells = []
    for s in srcs:
        v = R[s][gname]; cells.append(f"{v['W']}/{v['n']} {100 * v['wr']:.0f}% [{100 * v['ci'][0]:.0f},{100 * v['ci'][1]:.0f}]" if v["n"] else "0/0")
    P("  " + f"{gname:26s}" + "".join(f"{c:>28s}" for c in cells))
P("  exposure share (games in group / all): live vs RL training")
for gname in GROUPS[1:]:
    P(f"    {gname:26s} live {R['q2_live'][gname]['n'] / R['q2_live']['ALL']['n']:.3f}   RL {R['q2_rl_deck_exposure'].get(gname, {'share': 0})['share']:.3f}")
P("  distinct decks per group: " + json.dumps({s: {g: R[s][g]["distinct_decks"] for g in GROUPS} for s in srcs}))
P(f"  reactive vs S1 icebow mirror (all models): {R['q2_reactive_s1_mirror']['W']}/{R['q2_reactive_s1_mirror']['n']}")
P(f"  RL opponent policy mix: {json.dumps(R['q2_rl_opp_mix'], default=float)}")
P(f"  RL deck exposure (games): {json.dumps({k: v['games'] for k, v in R['q2_rl_deck_exposure'].items()})}")
P(f"\nQ3 sampled-play win rate vs fixed opponents across R1e training: {json.dumps(R['q3_sampled_vs_fixed'], default=float)}")
P(f"\nQ4 {json.dumps(R['q4'], default=float)}")
open(os.path.join(HERE, "q12_report.txt"), "w").write("\n".join(OUT) + "\n")
print("\n".join(OUT))
