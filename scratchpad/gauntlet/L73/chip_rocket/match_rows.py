"""Map pro Rocket events (pros_chip.pkl) to gen_dataset_v32_fv5 play rows (deck 90, y_card=rocket). Saves chip_rows.pkl."""
import numpy as np, json, pickle, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
NPZ = "C:/Users/benpe/ClashBot/icebow/data/pipeline/gen_dataset_v32_fv5.npz"
z = np.load(NPZ)
meta = json.loads(str(z["meta"])) if "meta" in z.files else json.load(open(NPZ[:-4] + ".json"))
cv = meta["card_vocab"]; RK = cv.index("rocket")
tags = z["tags"]; rep = z["rep"]; side = z["side"]; tick = z["tick"]; yg = z["y_gate"]; yc = z["y_card"]; dk = z["deck_id"]; split = z["split"]
sel = np.flatnonzero((dk == 90) & (yg == 1) & (yc == RK))
print("deck90 rocket play rows", len(sel), "split", collections.Counter(split[sel].tolist()))
idx = {(tags[rep[i]], int(side[i])): [] for i in sel}
for i in sel: idx[(tags[rep[i]], int(side[i]))].append(i)
pros = pickle.load(open(os.path.join(HERE, "pros_chip.pkl"), "rb"))
print("example tag", pros[0]["tag"], tags[:2])
out = []; miss = 0; dts = collections.Counter()
for m in pros:
    cand = idx.get((m["tag"], m["side"]), [])
    for r in m["rockets"]:
        best = min(cand, key=lambda i: abs(int(tick[i]) - r["tick"]), default=None)
        if best is None or abs(int(tick[best]) - r["tick"]) > 20: miss += 1; continue
        dts[int(tick[best]) - r["tick"]] += 1
        kind = "chip" if r["towers"] and r["troops"] == [] else ("catch" if r["towers"] and r["troops"] else "notower")
        out.append(dict(row=int(best), kind=kind, phase=r["phase"], tick=r["tick"], split=int(split[best]), hp=max([f for _, f in r["towers"]], default=None),
                        lead=r["lead"], id=m["id"]))
print("matched", len(out), "miss", miss, "dt", dts.most_common(5), collections.Counter((o["kind"], o["split"]) for o in out))
pickle.dump(out, open(os.path.join(HERE, "chip_rows.pkl"), "wb"))
