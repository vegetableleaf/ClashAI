"""SIM (benchmark v2, ab_live2 arms): Rocket use, tower Rockets, X-Bow class and elixir at play by phase from matches.jsonl `behaviour`.
Copies fetched read-only from the VM into sim/. Definitions: phases 1x <2400 ticks <= 2x < 3600 <= OT (= pro sec<120/<180);
per-match-by-phase counts use matches with >= 30 s in that phase (analyze.py q3 rule); defensive share = defensive/(defensive+offensive_lock)
(the pro def/(def+off) ratio; telemetry n also counts 'other' = enemy half with no tower in reach). Writes sim_results.json."""
import json, glob, os, sys, collections
import numpy as np
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/rocket_xbow_1008/"
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch")
import analyze as A
PH = {"1x": (0, 120), "2x": (120, 180), "OT": (180, 300)}
EXCL = collections.Counter()
ARMS = ["t_r1e", "live2", "live2_rocket", "live2_filt", "live2_al"]

def load(arm):
    Ms = []
    for f in sorted(glob.glob(HERE + f"sim/react*_s[bc]_{arm}.jsonl")):
        for l in open(f):
            m = json.loads(l); b = m.get("behaviour") or {}
            if "phase_cards" not in b: continue
            if m["plays_accepted"] < 5: EXCL[arm] += 1; continue   # live_eval rule; these are mostly 0-play mutual-idle draws vs s1
            m["cluster"] = os.path.basename(f) + ":" + m["tag"]; Ms.append(m)
    return Ms

def stats(Ms):
    U = [m["cluster"] for m in Ms]; out = {"n_matches": len(Ms), "files": sorted({m["cluster"].split(":")[0] for m in Ms})}
    ex = lambda m, a, b: max(0.0, min(m["end_tick"] / 20.0, b) - a)
    for ph, (a, b) in PH.items():
        pm = [m for m in Ms if ex(m, a, b) >= 30]; B_ = lambda m: m["behaviour"]
        rk = lambda m: B_(m)["phase_cards"][ph].get("Rocket", 0)
        out[f"rockets_per_match|{ph}"] = list(A.rci(U, [(m["cluster"], rk(m), 1) for m in pm]))
        out[f"rocket_pct_plays|{ph}"] = list(A.rci(U, [(m["cluster"], rk(m), sum(B_(m)["phase_cards"][ph].values())) for m in Ms]))
        out[f"tower_rockets_per_match|{ph}"] = list(A.rci(U, [(m["cluster"], B_(m)["tower_rockets_phase"][ph], 1) for m in pm]))
        x = lambda m: B_(m)["xbow_phase"][ph]
        out[f"def_share(def/(def+off))|{ph}"] = list(A.rci(U, [(m["cluster"], x(m)["defensive"], x(m)["defensive"] + x(m)["offensive_lock"]) for m in Ms]))
        out[f"def_share(def/n_all)|{ph}"] = list(A.rci(U, [(m["cluster"], x(m)["defensive"], x(m)["n"]) for m in Ms]))
        out[f"xbow_other|{ph}"] = sum(x(m)["n"] - x(m)["defensive"] - x(m)["offensive_lock"] for m in Ms)
        e = lambda m: (B_(m).get("economy") or {}).get(ph) or {"plays": 0, "minutes": 0, "elixir_at_play": None}
        out[f"elixir_at_play|{ph}"] = list(A.rci(U, [(m["cluster"], (e(m)["elixir_at_play"] or 0) * e(m)["plays"], e(m)["plays"]) for m in Ms]))
        out[f"leak_ge_9.5|{ph}"] = list(A.rci(U, [(m["cluster"], B_(m)["leak_ge_9_5"][ph] * e(m)["minutes"], e(m)["minutes"]) for m in Ms if (B_(m).get("leak_ge_9_5") or {}).get(ph) is not None]))
    out["rockets_total_per_match"] = list(A.rci(U, [(m["cluster"], sum(m["behaviour"]["phase_cards"][p].get("Rocket", 0) for p in PH), 1) for m in Ms]))
    out["rocket_pct_plays|all"] = list(A.rci(U, [(m["cluster"], sum(m["behaviour"]["phase_cards"][p].get("Rocket", 0) for p in PH), sum(sum(m["behaviour"]["phase_cards"][p].values()) for p in PH)) for m in Ms]))
    out["tower_rockets_per_match|whole"] = list(A.rci(U, [(m["cluster"], sum(m["behaviour"]["tower_rockets_phase"].values()), 1) for m in Ms]))
    out["reached_OT"] = list(A.rci(U, [(m["cluster"], int(ex(m, 180, 300) >= 30), 1) for m in Ms]))
    out["win"] = list(A.rci(U, [(m["cluster"], int(m["outcome"] == "win"), 1) for m in Ms]))
    out["no_economy_matches"] = sum("economy" not in m["behaviour"] for m in Ms)
    out["unknown_rocket_impacts"] = sum(m["behaviour"]["unknown_rocket_impacts"] for m in Ms)
    return out

if __name__ == "__main__":
    R = {a: stats(Ms) for a in ARMS if (Ms := load(a))}
    R["excluded_lt5_plays"] = dict(EXCL)
    json.dump(R, open(HERE + "sim_results.json", "w"), indent=1)
    for a in ARMS:
        if a in R: print(a, R[a]["n_matches"], R[a]["files"], "excluded", EXCL[a])
