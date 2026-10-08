"""Pro tower-Rocket classification (chip vs catch) + eligible-time series with 'catchable troop near an enemy tower' flags.
Read-only on the icebow_public_v1 re-drives. Geometry (millitiles, raw frame): tower hit = alive enemy tower centre within
Rocket radius (2000) + tower collision radius (princess 1000 / king 1400) of the landing point; troop catch = alive enemy
non-tower body centre within 2000 of the landing point (label_recording's own troop_hits, interpolated to the landing tick)."""
import json, glob, os, pickle, sys, math, ctypes
from multiprocessing import Pool
sys.path.insert(0, "C:/Users/benpe/ClashBot")
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = {"Xbow", "Skeletons", "Log", "Knight", "Tesla", "Tornado", "IceWizard", "Rocket"}
TR = {"princess": 1000, "king": 1400}
CATCH = (2500, 4000)      # enemy troop centre within this of an alive enemy tower centre ("could be hit together")


def phase(t): return "1x" if t < 2400 else ("2x" if t < 3600 else "OT")


def one(f):
    try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception: pass
    from pipeline.public_outcomes import label_recording, normalize
    d = json.load(open(f)); tag = os.path.basename(f)[7:19]
    sides = [s for s in (0, 1) if {c.split("@")[0] for c in d["final_decks"][str(s)]} == BASE]
    if not sides: return []
    lab = label_recording(d)
    frames = [normalize(fr) for fr in d["frames"]]
    el = {fr["tick"]: fr["elixir"] for fr in d["frames"]}
    mx = {}
    for fr in d["frames"]:
        for t in fr["towers"]: mx[(t[0], t[3], t[4])] = t[6]
    out = []
    for s in sides:
        o = 1 - s
        def tstate(fr):
            mine = sum(t["hp"] / mx[(t["side"], t["x"], t["y"])] for t in fr["towers"] if t["side"] == s and t["hp"] > 0)
            theirs = sum(t["hp"] / mx[(t["side"], t["x"], t["y"])] for t in fr["towers"] if t["side"] == o and t["hp"] > 0)
            cr = [sum(t["kind"] == "princess" and t["hp"] <= 0 for t in fr["towers"] if t["side"] == x) for x in (o, s)]
            return mine - theirs, cr          # cr = [my crowns, their crowns]
        series = []
        for fr in frames:
            alive = [t for t in fr["towers"] if t["side"] == o and t["hp"] > 0]
            near = {}
            for t in alive:
                dmin = min([math.hypot(b["x"] - t["x"], b["y"] - t["y"]) for b in fr["bodies"] if b["side"] == o and b["hp"] > 0] + [1e9])
                near[t["kind"]] = min(near.get(t["kind"], 1e9), dmin)
            lead, cr = tstate(fr)
            series.append((fr["tick"], el[fr["tick"]][s], near.get("princess", 1e9), near.get("king", 1e9), lead, cr[0], cr[1]))
        rk = []
        for r in lab["rockets"]:
            if r["side"] != s: continue
            row = dict(tick=r["tick"], phase=phase(r["tick"]), landing=r.get("landing_tick"), known=r.get("hp_window_known", False),
                       troops=[(e["card"], e["hp_drop"]) for e in (r["troop_hits"] or [])] if r["troop_hits"] is not None else None, towers=[])
            if r.get("landing_point") and r["landing_tick"] is not None:
                px, py = r["landing_point"]
                fr = max([x for x in frames if x["tick"] <= r["landing_tick"]], key=lambda x: x["tick"], default=None)
                if fr:
                    for t in fr["towers"]:
                        if t["side"] == o and t["hp"] > 0 and math.hypot(px - t["x"], py - t["y"]) <= 2000 + TR[t["kind"]]:
                            row["towers"].append((t["kind"], t["hp"] / mx[(t["side"], t["x"], t["y"])]))
            fb = max([x for x in frames if x["tick"] <= r["tick"]], key=lambda x: x["tick"], default=frames[0])
            row["lead"], cr = tstate(fb); row["crowns"] = cr
            rk.append(row)
        out.append(dict(id=f"{tag}_s{s}", tag=d.get("tag"), side=s, end=frames[-1]["tick"], series=series, rockets=rk))
    return out


if __name__ == "__main__":
    fs = sorted(glob.glob("C:/Users/benpe/ClashBot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json"))
    if len(sys.argv) > 1: fs = fs[:int(sys.argv[1])]
    res = []
    with Pool(3) as p:
        for i, r in enumerate(p.imap_unordered(one, fs, chunksize=4)):
            res += r
            if i % 200 == 0: print(i, len(res), flush=True)
    pickle.dump(res, open(os.path.join(HERE, "pros_chip.pkl" if len(sys.argv) == 1 else "pros_chip_small.pkl"), "wb"))
    print("sides", len(res), "rockets", sum(len(r["rockets"]) for r in res))
