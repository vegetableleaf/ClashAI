"""Fix the counter set C from step 1 (post-10s window) BEFORE steps 2-5. Also build 2-fold cross-fit sets (select on one half of replays, evaluate on the other)."""
import json, pickle, collections, numpy as np
import common as C
step = json.load(open(C.HERE + "step1.json"))
HEAVY = ["golem", "giant", "electrogiant", "goblingiant", "pekka", "megaknight", "lavahound", "royalgiant", "runegiant", "giantskeleton"]
OWNER = set(HEAVY) | {"royalrecruits"}
rk = {r["card"]: r for r in step["windows"]["post10s"]["ranked"]}
C_main = sorted(c for c in OWNER if c in rk and rk[c]["n_exposed"] >= 40 and rk[c]["diff_vs_unexposed"][1] > 0)
C_emp = sorted(c for c, r in rk.items() if r["n_exposed"] >= 60 and r["diff_vs_unexposed"][1] >= 0.05)
C_wide = sorted(OWNER)
out = {"C_main": C_main, "C_wide": C_wide, "C_emp": C_emp,
       "rule": {"C_main": "owner-named classes with >=40 exposed X-Bows in the post-10s window and a 95% CI for (fail|exposed - fail|unexposed) above 0",
                "C_wide": "the owner's whole named list, unfiltered", "C_emp": "any card, >=60 exposed, CI lower bound of the fail lift >= +5 pp"}}
# cross-fit
P, Bt, XP, XB = C.load_all(); op = pickle.load(open(C.HERE + "opp_pros.pkl", "rb"))
U = sorted({M["cluster"] for M in P}); fold = {c: i % 2 for i, c in enumerate(U)}
inst = []
for M in P:
    for r in XP[M["id"]]:
        if r["cls"] != "off" or r["status"] not in ("fail", "ok"): continue
        w = {C.norm(p[1]) for p in op[M["id"]]["opp"] if r["tick"] <= p[0] <= r["tick"] + 200}
        inst.append((fold[M["cluster"]], int(r["status"] == "fail"), w))
cf = {}
for f in (0, 1):
    sub = [i for i in inst if i[0] == f]; cnt = collections.Counter(c for i in sub for c in i[2])
    mains, emps = [], []
    for card, n in cnt.items():
        if n < 25: continue
        ex = np.array([i[1] for i in sub if card in i[2]]); un = np.array([i[1] for i in sub if card not in i[2]])
        d = ex.mean() - un.mean(); se = np.sqrt(ex.var() / len(ex) + un.var() / len(un))
        if card in OWNER and n >= 20 and d - 1.96 * se > 0: mains.append(card)
        if n >= 30 and d - 1.96 * se >= 0.05: emps.append(card)
    cf[f] = {"C_main": sorted(mains), "C_emp": sorted(emps)}
out["crossfit_selected_on_fold"] = cf; out["fold_of_cluster_rule"] = "sorted unique replay file names, alternating 0/1"
json.dump(out, open(C.HERE + "C_set.json", "w"), indent=1); print(json.dumps(out, indent=1))
