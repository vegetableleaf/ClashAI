"""Comparison table: pros | live groups | SIM arms. Reads xbow_switch/results.json, rocket_lead/results.json, live_results.json, sim_results.json. Writes table.txt."""
import json
L73 = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/"; H = L73 + "rocket_xbow_1008/"
XS = json.load(open(L73 + "xbow_switch/results.json"))["pros_all"]; RK = json.load(open(L73 + "rocket_lead/results.json"))
LV = json.load(open(H + "live_results.json")); SM = json.load(open(H + "sim_results.json"))
def f(t, pct=False, d=2):
    if t is None or t[0] is None: return "n/a"
    if pct: return f"{100*t[0]:.1f} [{100*t[1]:.1f},{100*t[2]:.1f}]"
    return f"{t[0]:.{d}f} [{t[1]:.{d}f},{t[2]:.{d}f}]"
PE = LV["pros_extra"]
cols = [("pros", None), ("R1e live", LV["a_R1e"]), ("stack AL-on", LV["b_stack_AL_on"]), ("stack AL-off", LV["c_stack_AL_off"])] + [(f"SIM {a}", SM[a]) for a in SM if a != "excluded_lt5_plays"]
def pro(key):
    ph = key.split("|")[-1]
    if key == "n": return "2244"
    if key == "rockets_total_per_match": return f(XS["q3"]["rockets_total_per_match"])
    if key.startswith("tower_rockets_per_match"): return f(XS["q3"][key])
    if key.startswith("def_share"): return f(XS["q2"]["phase|" + ph], True)
    if key.startswith("elig_share"): r = RK["A_decomp_all_rockets"]["phase=" + ph if ph != "all" else "all"]["eligible_share"]["pros"]; return f(r, True)
    if key.startswith("rockets_per_elig_min"): r = RK["A_decomp_all_rockets"]["phase=" + ph]["rate_when_eligible_per_min"]["pros"]; return f(r)
    if key.startswith("tower_rockets_per_elig_min"): r = RK["A_decomp_tower_rockets"]["phase=" + ph]["rate_when_eligible_per_min"]["pros"]; return f(r)
    if key in PE: return f(PE[key], "pct" in key or "reached" in key)
    return "n/a"
def val(r, key):
    if key == "n": return str(r.get("n_matches"))
    if key.startswith("def_share"):
        k = "phase|" + key.split("|")[-1]
        return f(r[k], True) if k in r else f(r.get("def_share(def/(def+off))|" + key.split("|")[-1]), True)
    if key not in r: return "n/a"
    return f(r[key], ("pct" in key or "share" in key or "reached" in key or key == "win"))
rows = ["n", "rockets_total_per_match", "rocket_pct_plays|all"] + [f"{m}|{p}" for m in ("rockets_per_match", "rocket_pct_plays", "tower_rockets_per_match", "def_share", "elig_share", "rockets_per_elig_min", "tower_rockets_per_elig_min", "elixir_at_play") for p in ("1x", "2x", "OT")] + ["reached_OT", "win"]
out = []
for k in rows:
    out.append(f"{k:30s}" + " | ".join([f"{c}: {pro(k) if r is None else val(r, k)}" for c, r in cols]))
open(H + "table.txt", "w").write("\n".join(out) + "\n"); print("\n".join(out))
