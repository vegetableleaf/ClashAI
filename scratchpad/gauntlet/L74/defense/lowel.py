"""Low-elixir defended episodes (>= 5 value, el0 < 4): was the low elixir already invested in THIS push (a defence landed by the
crossing) or spent elsewhere?  Bot vs pros, from the analysed data.  -> appended to out/extra.txt"""
import gzip, pickle, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
out = []
for name in ("live", "pros"):
    A = pickle.load(gzip.open(HERE + "data/" + name + "_an.pkl.gz"))
    for pop, f in (("TR", lambda a: a["fam"].startswith("towerref")), ("RL", lambda a: True)) if name == "live" else (("PRO", lambda a: True),):
        sc = lambda a: 4424.0 / a["pmax"]
        r = collections.defaultdict(lambda: [0, 0, 0.0])
        for a in A:
            if not f(a) or a["res"] not in ("WIN", "LOSS", "DRAW"): continue
            for e in a["eps"]:
                if e["vmax"] < 5 or not e["n_def"] or e["el0"] is None: continue
                k = ("el0<4" if e["el0"] < 4 else "el0>=4", "pre-placed" if (e["rsp_land"] is not None and e["rsp_land"] <= 0) else "after")
                r[k][0] += 1; r[k][1] += e["dmg"] * sc(a) >= 1000; r[k][2] += e["dmg"] * sc(a)
        n_lo = sum(v[0] for k, v in r.items() if k[0] == "el0<4")
        s = f"{pop:4s} " + "  ".join(f"{k[0]}/{k[1]}: n={v[0]} ({v[0] / max(1, sum(w[0] for kk, w in r.items() if kk[0] == k[0])):.2f}) fail {v[1] / v[0]:.2f} dmg {v[2] / v[0]:.0f}"
                                     for k, v in sorted(r.items()))
        out.append(s); print(s)
open(HERE + "out/extra.txt", "a").write("\n(6) defended >= 5 episodes by el0 and whether a defence had landed by the crossing:\n" + "\n".join(out) + "\n")
