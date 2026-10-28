"""RX-X23 analysis: section-1 identity, three R_exchange variants fitted on HF exact traces, X1 (variant iii, + i/ii for
reference), X2 farm audit and X3 SIM calibration on the sim_worker.py runs. Nothing here is wired into training.

    python analyze.py HF.npz LIVE.npz BATTLELOG.jsonl OUT.json [SIMROOT ...]
HF.npz: hf_traces.py output with E_i (exact elixir both sides); LIVE.npz: build.py output with E_i (own elixir + the public
counter's opponent estimate); SIMROOT/<tag>/D3/{matches.jsonl, inputs/plan.json via ../inputs, NNNNN/x23/<seed>.npz};
tag = <policy>_<mode>_<seedstart> (imit_* = the imitation model under the clxiii policy).

Variants (R_win +1 / -1 / 0 unchanged in all three):
  (i)   tower terms + a_lin (candidates.terms: destroyed - committed, ours - theirs); phase-split (1x / 2x / OT) logistic,
        r = 0.5 * beta . dx per step, match total clipped to +-0.5 (r_exchange.step_rewards)
  (ii)  tower terms + ref_elixir (destroyed only); same fit, scale and cap
  (iii) Phi(s) = P_hat(win | tower terms, destroyed, own elixir, opp elixir, t) - 0.5, ONE logistic whose coefficients are
        continuous piecewise-linear in t (hat basis on KNOTS_S, no jump at 1x / 2x / OT); r_k = gamma^dt Phi_k+1 - Phi_k,
        gamma = 0.99994 per tick, Phi(terminal = last row) = 0
Composite: (i)/(ii) R_win + sum r (the plan's capped match total, undiscounted); (iii) gamma^T R_win + sum gamma^t r (the
discounted return GAE optimises; potential shaping is policy-invariant only there). Both forms are reported for every variant.
"""
import collections
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parents[5]), str(HERE.parents[2] / "memory")]
os.environ.setdefault("RX_SPLIT", str(HERE.parent / "SPLIT_HF.json"))
import fit as FIT  # noqa: E402
import candidates as CAND  # noqa: E402

RX = FIT.RX
F = list(RX.FEATURES)
BASE = CAND.BASE                                          # princess, king, king_on, crowns
GAMMA = 0.99994
KNOTS_S = np.array([0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300])
CK = FIT.CK                                               # 60 / 120 / 180 s
EXPLOITS = ("hold10", "nospell", "rocket_tower", "alldef", "xbow_spam", "rocket_tank")
POLICIES = ("clxiii",) + EXPLOITS + ("imit",)
SPLIT = FIT.SPLIT
SKIPPED = {}                                              # engine-gap matches per run (load_sim)


# ----------------------------------------------------------------------------------------------------- data
def match(t, L, C, LT, E, **meta):
    """one match's 1-s rows -> the three variants' inputs."""
    X = RX.features(L)
    T = CAND.terms(t, L, C, LT)
    E = np.array(E, float)
    for k in (0, 1):                                      # live opp estimate may be missing: forward fill, then 5
        col = E[:, k]
        for j in range(len(col)):
            if not np.isfinite(col[j]):
                col[j] = col[j - 1] if j and np.isfinite(col[j - 1]) else 5.0
    base = X[:, BASE]
    return dict(meta, t=np.asarray(t), L=L, C=C, LT=LT, E=E,
                Xi=np.c_[base, T["a_lin"]], Xii=np.c_[base, T["ref_elixir"]],
                Z=np.c_[base, T["ref_elixir"], E[:, 0], E[:, 1]])


def load_npz(path, frame_only=False):
    d = np.load(path)
    meta = json.loads(str(d["meta"]))
    out = []
    for i, r in enumerate(meta):
        if frame_only and r.get("trace") != "frame":
            continue
        out.append(match(d[f"t_{i}"], d[f"L_{i}"].astype(float), d[f"C_{i}"].astype(float), d[f"LT_{i}"].astype(float),
                         d[f"E_{i}"].astype(float), **{k: r[k] for k in ("file", "date", "y", "end_tick") if k in r},
                         hf_committed=r.get("hf_committed"), hf_leaked=r.get("hf_leaked")))
    return out


# ----------------------------------------------------------------------------------------------------- identity
def identity(M):
    """section 1: C_opp - C_own vs (leak_own + stock_own) - (leak_opp + stock_opp), per match (end) and over time."""
    def parts(m):
        lhs = m["C"][:, 1] - m["C"][:, 0]
        rhs = (m["L"][:, 0, 5] + m["E"][:, 0]) - (m["L"][:, 1, 5] + m["E"][:, 1])
        return lhs, rhs

    def stats(a, b):
        r = b - a
        return {"n": int(len(a)), "r": float(np.corrcoef(a, b)[0, 1]), "lhs_sd": float(a.std()),
                "resid_mean": float(r.mean()), "resid_sd": float(r.std()), "resid_abs_median": float(np.median(np.abs(r))),
                "resid_abs_p95": float(np.percentile(np.abs(r), 95)),
                "slope_rhs_on_lhs": float(np.polyfit(a, b, 1)[0])}
    out = {}
    lo, ro = zip(*[parts(m) for m in M])
    out["end"] = stats(np.array([x[-1] for x in lo]), np.array([x[-1] for x in ro]))
    out["all_rows"] = stats(np.concatenate(lo), np.concatenate(ro))
    for name, tick in CK.items():
        a, b = [], []
        for m, x, y in zip(M, lo, ro):
            if m["end_tick"] > tick:
                j = max(np.searchsorted(m["t"], tick, side="right") - 1, 0)
                a.append(x[j]); b.append(y[j])
        out[name] = stats(np.array(a), np.array(b))
    hf = [(m["hf_committed"][1] - m["hf_committed"][0], y[-1]) for m, y in zip(M, ro)
          if m.get("hf_committed") and None not in m["hf_committed"]]
    if hf:                                                # HF's own committed totals (engine-independent) vs the trace's stock + leak
        a, b = map(np.array, zip(*hf))
        out["end_hf_committed"] = stats(a, b)
    a = np.concatenate([m["Xi"][:, -1] for m in M])     # how much of a_lin is the committed difference
    out["a_lin_vs_committed_diff_r"] = float(np.corrcoef(a, np.concatenate(lo))[0, 1])
    out["a_lin_vs_stock_leak_diff_r"] = float(np.corrcoef(a, np.concatenate(ro))[0, 1])
    return out


# ----------------------------------------------------------------------------------------------------- models
def lin_fit(M, key):
    return FIT.fit_all([dict(t=m["t"], X=m[key], y=m["y"]) for m in M])


def lin_p(B, x, tick):
    return float(FIT.predict(B, x, RX.phase_index(tick)))


def hat(t):
    """[n, K] continuous piecewise-linear weights of tick t on KNOTS_S (sum 1; t clipped to the last knot)."""
    s = np.clip(np.asarray(t, float) / 20.0, KNOTS_S[0], KNOTS_S[-1])
    j = np.clip(np.searchsorted(KNOTS_S, s, side="right") - 1, 0, len(KNOTS_S) - 2)
    w = (s - KNOTS_S[j]) / (KNOTS_S[j + 1] - KNOTS_S[j])
    H = np.zeros((len(s), len(KNOTS_S)))
    H[np.arange(len(s)), j] = 1 - w
    H[np.arange(len(s)), j + 1] = w
    return H


def phi_design(Z, t):
    H = hat(t)
    return np.concatenate([H] + [H * Z[:, [k]] for k in range(Z.shape[1])], axis=1)


def phi_fit(M, every=3):
    Zs, ts, ys = [], [], []
    for m in M:
        k = np.arange(0, len(m["t"]), every)
        Zs.append(m["Z"][k]); ts.append(m["t"][k]); ys.append(np.full(len(k), m["y"], float))
    return FIT.logit(phi_design(np.concatenate(Zs), np.concatenate(ts)), np.concatenate(ys))


def phi_p(b, Z, t):
    z = b[0] + phi_design(np.atleast_2d(Z), np.atleast_1d(t)) @ b[1:]
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def models(train):
    return {"i": lin_fit(train, "Xi"), "ii": lin_fit(train, "Xii"), "iii": phi_fit(train)}


def predict(name, mod, m, j, tick):
    base = name.split("_")[0]                             # i / ii / iii, also their *_sym fits
    if base == "iii":
        return float(phi_p(mod, m["Z"][j], m["t"][j])[0])
    return lin_p(mod, m["Xi" if base == "i" else "Xii"][j], tick)


def mirror(m):
    """the same match seen from the other side (HF observer = the replay's owner, who wins 66%): sides swapped, y = 1 - y.
    Fitting on both views makes P(win) symmetric (0.5 at an even state), as SIM self-play and live need."""
    sw = lambda a: a[:, ::-1]                             # noqa: E731
    return match(m["t"], sw(m["L"]), sw(m["C"]), sw(m["LT"]), sw(m["E"]), y=1 - m["y"], end_tick=m["end_tick"],
                 date=m["date"], file=m["file"])


# ----------------------------------------------------------------------------------------------------- calibration (X1 / X3)
def calib(mods, M, boot=1000, seed=1, groups=None):
    """per variant per checkpoint: n, AUC [CI], ECE [CI], reliability table, mean predicted vs observed."""
    out = {}
    for name, mod in mods.items():
        out[name] = {}
        for ck, tick in CK.items():
            P, Y, G = [], [], []
            for m in M:
                if m["end_tick"] <= tick or m["y"] not in (0, 1):
                    continue
                j = max(np.searchsorted(m["t"], tick, side="right") - 1, 0)
                P.append(predict(name, mod, m, j, tick)); Y.append(m["y"]); G.append(m.get("group"))
            P, Y = np.array(P), np.array(Y)
            rng = np.random.default_rng(seed)
            bs = []
            for _ in range(boot):
                i = rng.integers(0, len(Y), len(Y))
                bs.append((FIT.auc(P[i], Y[i]), FIT.ece(P[i], Y[i])[0]))
            bs = np.array(bs)
            e, tab = FIT.ece(P, Y)
            r = {"n": int(len(Y)), "wins": int(Y.sum()), "auc": FIT.auc(P, Y), "auc_ci": FIT.ci(bs[:, 0]), "ece": e,
                 "ece_ci": FIT.ci(bs[:, 1]), "mean_pred": float(P.mean()), "mean_obs": float(Y.mean()),
                 "reliability": tab}
            if groups:
                by = collections.defaultdict(list)
                for p, y, g in zip(P, Y, G):
                    by[g].append((p, y))
                r["by_group"] = {g: {"n": len(v), "mean_pred": float(np.mean([p for p, _ in v])),
                                     "mean_obs": float(np.mean([y for _, y in v])),
                                     "ece": FIT.ece(np.array([p for p, _ in v]), np.array([y for _, y in v]))[0],
                                     "auc": FIT.auc(np.array([p for p, _ in v]), np.array([y for _, y in v]))}
                                 for g, v in sorted(by.items(), key=lambda kv: -len(kv[1]))}
            out[name][ck] = r
    return out


# ----------------------------------------------------------------------------------------------------- returns (X2)
def returns(mods, m, rwin):
    """per variant: (undiscounted composite, discounted composite)."""
    t = m["t"].astype(float)
    T = float(m["end_tick"])
    out = {"win_only": (rwin, GAMMA ** T * rwin)}
    for name in ("i", "ii"):
        B = mods[name]
        beta = np.array([b[1:] for b in B])
        r = RX.step_rewards(m["t"], m["Xi" if name == "i" else "Xii"], beta)
        out[name] = (rwin + float(r.sum()), GAMMA ** T * rwin + float((GAMMA ** t * r).sum()))
    phi = phi_p(mods["iii"], m["Z"], m["t"]) - 0.5
    phi[-1] = 0.0                                          # Phi(terminal) = 0: the last row is the match end
    r = GAMMA ** np.diff(t) * phi[1:] - phi[:-1]
    out["iii"] = (rwin + float(r.sum()), GAMMA ** T * rwin + float((GAMMA ** t[:-1] * r).sum()))
    out["iii_phi0"] = float(phi[0])
    # self-check: the discounted shaped sum telescopes to -gamma^t0 Phi(s0) (Phi(terminal) = 0), whatever the policy did
    assert abs(out["iii"][1] - (GAMMA ** T * rwin - GAMMA ** t[0] * phi[0])) < 1e-9, "potential shaping does not telescope"
    return out


def load_sim(roots):
    """-> {(policy, mode): {(census, seed): match dict with outcome, arch, returns inputs}}"""
    from xbow_arch import arch_of
    runs = {}
    for root in roots:
        for d in sorted(glob.glob(f"{root}/*/D3")):
            tag = Path(d).parent.name
            pol, mode = ("imit", tag.split("_")[1]) if tag.startswith("imit_") else (tag.rsplit("_", 2)[0], tag.rsplit("_", 2)[1])
            plan = json.load(open(Path(d).parent / "inputs" / "plan.json"))
            census_of = {}
            for i, job in enumerate(plan["jobs"]):
                for s in job["seeds"]:
                    census_of[(job["census"], s)] = i
            rows = [json.loads(x) for x in open(f"{d}/matches.jsonl") if x.strip()]
            got = runs.setdefault((pol, mode), {})
            for r in rows:
                if r.get("skipped"):                      # sim_worker: a crforge engine gap ended this match
                    SKIPPED[f"{pol}_{mode}"] = SKIPPED.get(f"{pol}_{mode}", 0) + 1
                    continue
                key = (r["census"], r["seed"])
                f = Path(d) / f"{census_of[key]:05d}" / "x23" / f"{r['seed']}.npz"
                z = np.load(f)
                y = {"win": 1, "loss": 0}.get(r["outcome"], -1)
                m = match(z["t"], z["L"].astype(float), z["C"].astype(float), z["LT"].astype(float), z["E"].astype(float),
                          y=y, end_tick=int(z["t"][-1]), date=None, file=str(f))
                m.update(outcome=r["outcome"], rwin={"win": 1, "loss": -1}.get(r["outcome"], 0), group=arch_of(r["opp_deck"]),
                         opp_deck=r["opp_deck"], over=r.get("x23", {}).get("over", {}))
                got[key] = m
    return runs


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def x2(mods, runs, boot=2000, seed=7):
    """per variant, per mode set (e4, iu40, pooled): per-policy mean composite (undisc / disc) and win rate, paired deltas vs
    clxiii with bootstrap CIs over the shared (mode, census, seed) keys, the exploit flags and Spearman(composite, win)."""
    modes = sorted({m for _, m in runs})
    R = {}
    for (pol, mode), ms in runs.items():
        for key, m in ms.items():
            R[(pol, mode) + key] = (m["rwin"] == 1, returns(mods, m, m["rwin"]))
    out = {}
    for mset in [[x] for x in modes] + [modes]:
        name = "+".join(mset)
        pols = [p for p in POLICIES if all((p, md) in runs for md in mset)]
        keys = sorted(set.intersection(*[{(md,) + k for md in mset for k in runs[(p, md)]} for p in pols]))
        out[name] = {"n_paired": len(keys), "policies": pols, "variants": {}}
        win = {p: np.array([R[(p,) + k][0] for k in keys], float) for p in pols}
        for var in ("win_only", "i", "ii", "iii"):
            res = {}
            for form, ix in (("undisc", 0), ("disc", 1)):
                comp = {p: np.array([R[(p,) + k][1][var][ix] for k in keys]) for p in pols}
                rex = {p: comp[p] - np.array([R[(p,) + k][1]["win_only"][ix] for k in keys]) for p in pols}
                rng = np.random.default_rng(seed)
                B = [rng.integers(0, len(keys), len(keys)) for _ in range(boot)]
                per = {}
                for p in pols:
                    dc = comp[p] - comp["clxiii"]; dw = win[p] - win["clxiii"]; dr = rex[p] - rex["clxiii"]
                    per[p] = {"win": float(win[p].mean()), "comp": float(comp[p].mean()),
                              "rex": float(rex[p].mean()), "d_rex": float(dr.mean()),     # the dense term alone
                              "d_rex_ci": FIT.ci([dr[i].mean() for i in B]),
                              "d_comp": float(dc.mean()), "d_comp_ci": FIT.ci([dc[i].mean() for i in B]),
                              "d_win": float(dw.mean()), "d_win_ci": FIT.ci([dw[i].mean() for i in B])}
                    per[p]["exploit_flag"] = bool(p != "clxiii" and per[p]["d_comp"] > 0 and per[p]["d_win"] < 0)
                    per[p]["exploit_flag_ci"] = bool(p != "clxiii" and per[p]["d_comp_ci"][0] > 0 and per[p]["d_win_ci"][1] < 0)
                rho = spearman([per[p]["comp"] for p in pols], [per[p]["win"] for p in pols])
                rb = [spearman([comp[p][i].mean() for p in pols], [win[p][i].mean() for p in pols]) for i in B[:500]]
                res[form] = {"per_policy": per, "spearman": rho, "spearman_ci": FIT.ci(rb),
                             "exploit_any": any(per[p]["exploit_flag"] for p in pols if p in EXPLOITS),
                             "pass": (not any(per[p]["exploit_flag"] for p in pols if p in EXPLOITS)) and rho >= 0.8}
            res["gate_form"] = "disc" if var == "iii" else "undisc"
            out[name]["variants"][var] = res
    return out


# ----------------------------------------------------------------------------------------------------- X3 localisation
def feature_shift(train, sim):
    """mean feature values at each checkpoint, HF train vs SIM (CLXIII), for every model input."""
    names = ["princess", "king", "king_on", "crowns", "ref_elixir", "e_own", "e_opp", "a_lin"]
    out = {}
    for ck, tick in CK.items():
        def at(M):
            X = []
            for m in M:
                if m["end_tick"] > tick:
                    j = max(np.searchsorted(m["t"], tick, side="right") - 1, 0)
                    X.append(np.r_[m["Z"][j], m["Xi"][j, -1]])
            return np.array(X)
        a, b = at(train), at(sim)
        out[ck] = {n: {"hf": float(a[:, k].mean()), "sim": float(b[:, k].mean()), "hf_sd": float(a[:, k].std()),
                       "shift_sd": float((b[:, k].mean() - a[:, k].mean()) / max(a[:, k].std(), 1e-9))}
                   for k, n in enumerate(names)}
    return out


def refit_compare(mods, sim):
    """the same model refitted on the SIM (CLXIII) matches: coefficient by coefficient vs the HF fit (linear variants)."""
    out = {}
    simd = [m for m in sim if m["y"] in (0, 1)]
    for name, key, cols in (("i", "Xi", BASE_N + ["a_lin"]), ("ii", "Xii", BASE_N + ["ref_elixir"])):
        Bs = lin_fit(simd, key)
        out[name] = {ph: {c: {"hf": float(mods[name][k][1 + q]), "sim": float(Bs[k][1 + q])} for q, c in enumerate(cols)}
                     | {"intercept": {"hf": float(mods[name][k][0]), "sim": float(Bs[k][0])}}
                     for k, (ph, _, _) in enumerate(RX.PHASES)}
    return out


BASE_N = ["princess", "king", "king_on", "crowns"]


def main():
    a = sys.argv[1:]
    hf_path, live_path, bl_path, out_path, sim_roots = a[0], a[1], a[2], a[3], a[4:]
    res = {"gamma_tick": GAMMA, "knots_s": KNOTS_S.tolist(), "split": SPLIT}
    HF = [m for m in load_npz(hf_path) if m["y"] in (0, 1)]
    tr = [m for m in HF if SPLIT["train_dates"][0] <= m["date"] <= SPLIT["train_dates"][1]]
    H = [m for m in HF if SPLIT["heldout_dates"][0] <= m["date"] <= SPLIT["heldout_dates"][1]]
    res["hf"] = {"decisive": len(HF), "train": len(tr), "heldout": len(H),
                 "end_tick_p50_p99_max": np.percentile([m["end_tick"] for m in HF], [50, 99, 100]).tolist()}
    print("HF", res["hf"], flush=True)
    res["identity"] = identity(HF)
    print("IDENTITY", json.dumps(res["identity"], indent=1), flush=True)
    mods = models(tr)
    sym = models(tr + [mirror(m) for m in tr])            # sensitivity: both views of every HF match (symmetric P(win))
    every = {**mods, **{k + "_sym": v for k, v in sym.items()}}
    res["models"] = {k: ([b.tolist() for b in v] if isinstance(v, list) else v.tolist()) for k, v in every.items()}
    res["models"].update(i_cols=BASE_N + ["a_lin"], ii_cols=BASE_N + ["ref_elixir"],
                         iii_cols=["1"] + BASE_N + ["ref_elixir", "e_own", "e_opp"])
    res["x1_hf_heldout"] = calib(every, H)
    LV = load_npz(live_path, frame_only=True)
    pairs = FIT.join(LV, FIT.battlelog(bl_path))
    for i, b in pairs.items():
        if b["cm"] != b["co"]:
            LV[i]["y"] = int(b["cm"] > b["co"])
    LV = [m for m in LV if m["y"] in (0, 1)]
    res["live"] = {"decisive": len(LV), "battlelog_matched": len(pairs)}
    res["x1_live_all"] = calib(every, LV)
    LH = [m for m in LV if "20261021" <= m["date"] <= "20261027"]
    res["x1_live_heldout_dates"] = calib(every, LH)
    for k in ("x1_hf_heldout", "x1_live_all", "x1_live_heldout_dates"):
        for v, r in res[k].items():
            print(k, v, {ck: f"n {x['n']} auc {x['auc']:.3f} {np.round(x['auc_ci'], 3)} ece {x['ece']:.3f} "
                             f"{np.round(x['ece_ci'], 3)} pred {x['mean_pred']:.3f} obs {x['mean_obs']:.3f}"
                         for ck, x in r.items()}, flush=True)
    if sim_roots:
        runs = load_sim(sim_roots)
        res["sim_runs"] = {f"{p}_{m}": len(v) for (p, m), v in runs.items()}
        res["sim_skipped_engine_gap"] = SKIPPED
        print("SIM runs", res["sim_runs"], "engine-gap skips", SKIPPED, flush=True)
        res["sim_overrides"] = {f"{p}_{m}": dict(sum((collections.Counter(x["over"]) for x in v.values()), collections.Counter()))
                                for (p, m), v in runs.items()}
        for key, mm in (("x2", mods), ("x2_sym", sym)):
            res[key] = x2(mm, runs)
            for ms, r in res[key].items():
                for var, v in r["variants"].items():
                    g = v[v["gate_form"]]
                    print(key, ms, var, v["gate_form"], "n", r["n_paired"], "PASS" if g["pass"] else "FAIL",
                          f"spearman {g['spearman']:.3f} {np.round(g['spearman_ci'], 3)}", flush=True)
                    for p, x in g["per_policy"].items():
                        ci = lambda k: f"[{x[k + '_ci'][0]:+.3f},{x[k + '_ci'][1]:+.3f}]"      # noqa: E731
                        print(f"   {p:13s} win {x['win']:.3f} dW {x['d_win']:+.3f} {ci('d_win')} comp {x['comp']:+.3f} "
                              f"dC {x['d_comp']:+.3f} {ci('d_comp')} rex {x['rex']:+.4f} dRex {x['d_rex']:+.4f} {ci('d_rex')}"
                              + (" EXPLOIT" if x["exploit_flag"] else "") + (" EXPLOIT_CI" if x["exploit_flag_ci"] else ""),
                              flush=True)
        res["x3"] = {}
        for mode in sorted({m for _, m in runs}):
            sim = list(runs.get(("clxiii", mode), {}).values())
            if not sim:
                continue
            res["x3"][mode] = {"calib": calib(every, sim, groups=True), "feature_shift": feature_shift(tr, sim),
                               "refit": refit_compare(mods, sim), "draws": sum(m["y"] == -1 for m in sim)}
            for v, r in res["x3"][mode]["calib"].items():
                print("X3", mode, v, {ck: f"n {x['n']} auc {x['auc']:.3f} ece {x['ece']:.3f} {np.round(x['ece_ci'], 3)} "
                                          f"pred {x['mean_pred']:.3f} obs {x['mean_obs']:.3f}" for ck, x in r.items()},
                      flush=True)
    json.dump(res, open(out_path, "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
