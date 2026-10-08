"""Defence outcomes per live checkpoint family (did towerref_w2 change defence vs its stack2k base?) -> appended to out/extra.txt"""
import gzip, pickle, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
A = [a for a in pickle.load(gzip.open(HERE + "data/live_an.pkl.gz")) if a["res"] in ("WIN", "LOSS", "DRAW")]
out = ["\n(7) per family: defended >= 5 episodes fail(>=1000)/dmg by el0 (<4 | >=4); first-defence-landed-by-crossing share; per-card dmg10 (all elixir)"]
fams = collections.defaultdict(list)
for a in A: fams["towerref (both)" if a["fam"].startswith("towerref") else a["fam"]].append(a)
for f, ms in sorted(fams.items(), key=lambda x: -len(x[1])):
    r = collections.defaultdict(lambda: [0, 0, 0.0]); pre = [0, 0]; c = collections.defaultdict(list)
    for a in ms:
        for e in a["eps"]:
            if e["vmax"] < 5 or not e["n_def"] or e["el0"] is None: continue
            k = "<4" if e["el0"] < 4 else ">=4"
            r[k][0] += 1; r[k][1] += e["dmg"] >= 1000; r[k][2] += e["dmg"]
            pre[0] += 1; pre[1] += e["rsp_land"] is not None and e["rsp_land"] <= 0
        for d in a["dplays"]: c[d["card"]].append(d["dmg10"])
    w = sum(a["res"] == "WIN" for a in ms)
    out.append(f"{f:26s} n={len(ms):3d} WR {w / len(ms):.2f}  " + "  ".join(f"el0{k}: n={v[0]} fail {v[1] / v[0]:.2f} dmg {v[2] / v[0]:.0f}" for k, v in sorted(r.items()))
               + f"  pre-placed {pre[1] / max(1, pre[0]):.2f}  dmg10 " + " ".join(f"{x} {sum(v) / len(v):.0f}" for x, v in sorted(c.items()) if len(v) >= 20))
print("\n".join(out))
open(HERE + "out/extra.txt", "a").write("\n".join(out) + "\n")
