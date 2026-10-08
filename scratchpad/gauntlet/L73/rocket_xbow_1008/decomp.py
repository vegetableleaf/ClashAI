"""rocket_lead decomposition for the live groups, per phase: ln(pros rate per match-minute / bot rate) = ln(eligible-share ratio) + ln(rate-when-eligible ratio).
Pros = rocket_lead/results.json point estimates (their CIs are ~10x narrower than the bot's; ignored). Bot CIs: match bootstrap. Writes decomp.json."""
import json, math, pickle, collections
import numpy as np
import live as LV
A = LV.A; HERE = LV.HERE
RK = json.load(open(LV.L73 + "rocket_lead/results.json"))
D = pickle.load(open(HERE + "live_records.pkl", "rb"))["G"]
RNG = np.random.default_rng(9); B = 2000
def arrays(Ms, ph):
    a, b = LV.PH[ph]; rows = []
    for M in Ms:
        if len(M["plays"]) < 5: continue
        st = [s for s in M["states"] if s[2] is not None]
        if not st: continue
        tk = np.array([s[0] for s in st]); dt = np.array([(min(tk[k + 1] - tk[k], 60) if k + 1 < len(st) else 10) / 20.0 for k in range(len(st))])
        sel = (tk / 20.0 >= a) & (tk / 20.0 < b)
        el = np.array([("Rocket" in s[2]) and math.floor(s[1] + 1e-3) >= 6 for s in st])
        rk = [p for p in M["plays"] if p["name"] == "Rocket" and p["conf"] and a <= p["tick"] / 20.0 < b]
        rows.append((dt[sel].sum(), dt[sel & el].sum(), len(rk), sum(1 for p in rk if A.tower_target(M, p["x"], p["y"], p["tick"]))))
    return np.array(rows)
out = {}
for g in ("a_R1e", "b_stack_AL_on"):
    for ph in LV.PH:
        X = arrays(D[g], ph); S = RNG.integers(0, len(X), (B, len(X))); T = X[S].sum(1)
        for kind, col, key in (("all", 2, "A_decomp_all_rockets"), ("tower", 3, "A_decomp_tower_rockets")):
            pr = RK[key][f"phase={ph}"]; ps, pe, pt = pr["eligible_share"]["pros"][0], pr["rate_when_eligible_per_min"]["pros"][0], pr["rate_per_match_min"]["pros"][0]
            with np.errstate(all="ignore"):
                sh, re_, rt = T[:, 1] / T[:, 0], T[:, col] / (T[:, 1] / 60), T[:, col] / (T[:, 0] / 60)
                parts = {"ln_gap_total": np.log(pt / rt), "ln_gap_share": np.log(ps / sh), "ln_gap_rate_when_elig": np.log(pe / re_)}
            pt_b = X.sum(0); pts = {"share": pt_b[1] / pt_b[0], "rate_elig": pt_b[col] / (pt_b[1] / 60), "rate_tot": pt_b[col] / (pt_b[0] / 60)}
            def ci(v): v = v[np.isfinite(v)]; return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) > 100 else [None, None]
            out[f"{g}|{ph}|{kind}"] = {"pros": {"share": ps, "rate_elig": pe, "rate_tot": pt}, "bot": pts, "bot_minutes": [float(pt_b[0] / 60), float(pt_b[1] / 60)], "bot_plays": float(pt_b[col]),
                                       **{k: [float(np.log(ps / pts["share"])) if k == "ln_gap_share" else (float(np.log(pe / pts["rate_elig"])) if k == "ln_gap_rate_when_elig" and pts["rate_elig"] > 0 else (float(np.log(pt / pts["rate_tot"])) if k == "ln_gap_total" and pts["rate_tot"] > 0 else None)), *ci(v)] for k, v in parts.items()}}
            if pts["rate_tot"] > 0: out[f"{g}|{ph}|{kind}"]["frac_of_gap_from_share"] = float(np.log(ps / pts["share"]) / np.log(pt / pts["rate_tot"]))
json.dump(out, open(HERE + "decomp.json", "w"), indent=1)
for k, v in out.items():
    f = lambda t: "n/a" if t[0] is None else f"{t[0]:.2f} [{t[1] if t[1] is None else round(t[1],2)},{t[2] if t[2] is None else round(t[2],2)}]"
    print(f"{k:28s} share P {v['pros']['share']:.3f} B {v['bot']['share']:.3f} | rate/elig P {v['pros']['rate_elig']:.3f} B {v['bot']['rate_elig']:.3f} | rate/min P {v['pros']['rate_tot']:.3f} B {v['bot']['rate_tot']:.3f} | "
          f"ln gap {f(v['ln_gap_total'])} = share {f(v['ln_gap_share'])} + choice {f(v['ln_gap_rate_when_elig'])} | frac share {v.get('frac_of_gap_from_share', float('nan')):.2f} | elig-min {v['bot_minutes'][1]:.1f} plays {v['bot_plays']:.0f}")
