"""Step 1: which opponent cards, played in the window after an offensive X-Bow, go with failure? (pros, native re-drive HP)."""
import pickle, json, collections, numpy as np
import common as C
P, Bt, XP, XB = C.load_all(); op = pickle.load(open(C.HERE + "opp_pros.pkl", "rb"))
U = list(dict.fromkeys(M["cluster"] for M in P))
HEAVY = ["golem", "giant", "electrogiant", "goblingiant", "pekka", "megaknight", "lavahound", "royalgiant", "runegiant", "giantskeleton"]
CLASSES = {"heavy_tanks": set(HEAVY), "royal_recruits": {"royalrecruits"}, "owner_union": set(HEAVY) | {"royalrecruits"}}
WIN = {"post10s": (0, 200), "pre5s_post10s": (-100, 200), "life": None}
inst = []
for M in P:
    for r in XP[M["id"]]:
        if r["cls"] != "off" or r["status"] not in ("fail", "ok"): continue
        pl = op[M["id"]]["opp"]
        w = {}
        for k, v in WIN.items():
            a, b = (r["tick"] + v[0], r["tick"] + v[1]) if v else (r["tick"], r["death"])
            w[k] = {C.norm(p[1]) for p in pl if a <= p[0] <= b}
        inst.append({"c": M["cluster"], "fail": int(r["status"] == "fail"), "dmg": r["dmg"], "w": w, "ph": r["ph"]})
print("offensive resolved X-Bows", len(inst))
base = C.rci(U, [(i["c"], i["fail"], 1) for i in inst]); print("base fail", C.fm(base))
res = {"n_inst": len(inst), "base_fail": base, "windows": {}}
for wn in WIN:
    cnt = collections.Counter(c for i in inst for c in i["w"][wn])
    rows = []
    for card, n in cnt.items():
        if n < 40: continue
        ex = [(i["c"], i["fail"], 1) for i in inst if card in i["w"][wn]]; un = [(i["c"], i["fail"], 1) for i in inst if card not in i["w"][wn]]
        d = C.diff_ci(U, ex, un); f = C.rci(U, ex)
        dm = np.mean([i["dmg"] for i in inst if card in i["w"][wn]])
        rows.append({"card": card, "n_exposed": n, "fail_exposed": f, "diff_vs_unexposed": d, "lift_vs_base": f[0] - base[0], "mean_dmg_frac_exposed": float(dm)})
    rows.sort(key=lambda r: -r["diff_vs_unexposed"][0])
    cls = {}
    for k, S in CLASSES.items():
        ex = [(i["c"], i["fail"], 1) for i in inst if S & i["w"][wn]]; un = [(i["c"], i["fail"], 1) for i in inst if not (S & i["w"][wn])]
        cls[k] = {"n_exposed": len(ex), "fail_exposed": C.rci(U, ex), "fail_unexposed": C.rci(U, un), "diff": C.diff_ci(U, ex, un)}
    res["windows"][wn] = {"ranked": rows, "classes": cls, "n_cards_tested": len(rows),
                          "n_sig_pos": sum(1 for r in rows if r["diff_vs_unexposed"][1] > 0), "n_sig_neg": sum(1 for r in rows if r["diff_vs_unexposed"][2] < 0)}
    print("==", wn, "cards tested", len(rows), "sig+", res["windows"][wn]["n_sig_pos"], "sig-", res["windows"][wn]["n_sig_neg"])
    for k, v in cls.items(): print("  class", k, v["n_exposed"], C.fm(v["fail_exposed"]), "vs", C.fm(v["fail_unexposed"]), "diff", np.round(v["diff"], 3))
    for r in rows[:15]: print("  top", r["card"], r["n_exposed"], C.fm(r["fail_exposed"]), "diff", np.round(r["diff_vs_unexposed"], 3))
    for r in rows[-6:]: print("  bot", r["card"], r["n_exposed"], C.fm(r["fail_exposed"]), "diff", np.round(r["diff_vs_unexposed"], 3))
    for h in HEAVY + ["royalrecruits"]:
        rr = [r for r in rows if r["card"] == h]
        print("   owner-list", h, (rr[0]["n_exposed"], C.fm(rr[0]["fail_exposed"]), np.round(rr[0]["diff_vs_unexposed"], 3)) if rr else ("n<40", cnt.get(h, 0)))
json.dump(res, open(C.HERE + "step1.json", "w"), indent=1)
