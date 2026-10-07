"""Match-level 'turtler' proxy (player identity is unavailable): share of sides whose whole remainder after the K-th resolution
(>= 60 s left) has ZERO offensive X-Bows but >= 1 defensive X-Bow or tower Rocket. Time-stratified fail-ok difference, cluster bootstrap."""
import json, pickle, math, collections
import numpy as np
import turtle as Tt   # this folder's turtle.py (shadows stdlib turtle only when run from here)
A = Tt.A

def flags(P, K):
    U = []
    for M, xs, RK, AT in P:
        offs = [r for r in xs if r["cls"] == "off"]
        if len(offs) < K or any(r["status"] not in ("fail", "ok") for r in offs[:K]): continue
        tK = max(r["death"] for r in offs[:K])
        if M["end"] - tK < 1200: continue
        nf = sum(r["status"] == "fail" for r in offs[:K]); g = "fail" if nf == K else ("ok" if nf == 0 else "mixed")
        num, den = Tt.window(M, xs, RK, AT, tK, M["end"])
        turtle = num[0] == 0 and (num[1] >= 1 or num[2] >= 1); rkmain = num[9] == 1
        U.append({"c": M["cluster"], "g": g, "b": min(int(tK / 20 / Tt.BIN), Tt.NB - 1),
                  "num": [float(turtle), float(num[0] == 0), float(rkmain)] + [0.0] * (len(Tt.MET) - 3), "den": [1.0] * len(Tt.MET)})
    return U

def main():
    SW = Tt.SW; pros = pickle.load(open(SW + "pros.pkl", "rb")); bot = pickle.load(open(SW + "bot.pkl", "rb")); X = pickle.load(open(SW + "xrows.pkl", "rb"))
    for M in bot:
        for p in M["plays"]: p["x"] = math.floor(p["x"]) + 0.5; p["y"] = math.floor(p["y"]) + 0.5
    RD = json.load(open(SW + "results.json"))["meta"]["RD"]; out = {}
    for nm, Ms, XX, rd in (("pros_all", pros, X["pros_all"], RD["pro"]), ("bot", bot, X["bot"], RD["bot"])):
        W, idx = Tt.boot_W(Ms); P = Tt.prep(Ms, XX, rd)
        for K in (1, 2):
            U = flags(P, K); CE = Tt.cells(U, W, idx); e = Tt.std_effect(CE, "fail", "ok", range(Tt.NB))
            names = ["turtle(no offX, defX or towerRocket>=1)", "no offensive X-Bow at all", "rocket >50% of remainder tower dmg"]
            out[f"{nm}|K{K}"] = {"n": dict(collections.Counter(u["g"] for u in U)), "_n": e["_n"],
                                 **{names[j]: {k: e[Tt.MET[j]][k] for k in ("A", "B", "diff", "ci")} for j in range(3)}}
            print(nm, K, json.dumps(out[f"{nm}|K{K}"], default=float), flush=True)
    json.dump(Tt.strip(out), open(Tt.HERE + "results_proxy.json", "w"), indent=1)

if __name__ == "__main__":
    main()
