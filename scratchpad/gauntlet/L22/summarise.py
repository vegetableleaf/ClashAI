import json, glob, sys, collections, numpy as np
mode = sys.argv[1]
ck = ["m2k", "m5k", "m10k"]
D = {k: [json.load(open(f)) for f in sorted(glob.glob(f"led_{k}_{mode}_s*.json"))] for k in ck}
D = {k: v for k, v in D.items() if v}
print(f"mode={mode}  seeds per ckpt: " + ", ".join(f"{k}:{len(v)}" for k, v in D.items()))
print(f"{'':12s}" + "".join(f"{k:>18s}" for k in D))
def row(name, f):
    print(f"{name:12s}" + "".join(f"{np.mean([f(j) for j in v]):+11.3f}±{np.std([f(j) for j in v]):5.3f}" for v in D.values()))
row("plays%", lambda j: 100*j["plays"]/j["steps"]); row("elixir", lambda j: j["elixir_mean"]); row(">=6 %", lambda j: 100*j["ge6"])
terms = sorted({t for v in D.values() for j in v for t in j["terms"]}, key=lambda t: -max(abs(j["terms"].get(t, {"total":0})["total"]/j["matches"]) for v in D.values() for j in v))
tot = lambda j, t: j["terms"].get(t, {"total": 0.0})["total"] / j["matches"]
fires = lambda j, t: j["terms"].get(t, {"fires": 0})["fires"] / j["matches"]
print("\nper-match TOTAL (mean±sd over seeds)        | fires/match")
for t in terms:
    print(f"{t:22s}" + "".join(f"{np.mean([tot(j,t) for j in v]):+9.3f}±{np.std([tot(j,t) for j in v]):5.3f}" for v in D.values())
          + " |" + "".join(f"{np.mean([fires(j,t) for j in v]):7.1f}" for v in D.values()))
# play-side vs wait-side split (§5p classes)
wait_side = {"threat_miss_idle", "leak", "restraint_hold", "bank_hold"}
outcome = {"outcome", "take_enemy_tower", "lose_own_tower", "tower_chip", "chip_tower"}
def side(j, S): return sum(tot(j, t) for t in j["terms"] if t in S)
def pos_play(j): return sum(max(0.0, tot(j, t)) for t in j["terms"] if t not in wait_side and t not in outcome)
def neg_play(j): return sum(min(0.0, tot(j, t)) for t in j["terms"] if t not in wait_side and t not in outcome)
print()
row("play+ (shaping)", pos_play); row("play- (shaping)", neg_play); row("wait-side", lambda j: side(j, wait_side)); row("outcome", lambda j: side(j, outcome))
row("TOTAL", lambda j: sum(tot(j, t) for t in j["terms"]))
