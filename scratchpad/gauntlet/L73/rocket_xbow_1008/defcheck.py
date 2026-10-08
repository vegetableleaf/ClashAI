"""Definition check: the SIM telemetry labels (pipeline.public_outcomes.label_recording: defensive_xbow lead rule, offensive lock, tower_rocket)
vs the pro-comparison definitions (xbow_switch/analyze.py: xbow_rows cls off/def/other, tower_target within 2 tiles of an alive enemy tower).
Both run on the SAME pro replays (every 8th icebow_public_v1 replay). Read-only. Writes defcheck.json."""
import sys, glob, json, os, pickle, collections, ctypes
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
L73 = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/"
sys.path.insert(0, L73 + "xbow_switch"); sys.path.insert(0, "C:/Users/benpe/ClashBot")
import analyze as A
from pipeline.public_outcomes import label_recording
P = {M["id"]: M for M in pickle.load(open(L73 + "xbow_switch/pros.pkl", "rb"))}
XR = pickle.load(open(L73 + "xbow_switch/xrows.pkl", "rb"))["pros_all"]
ph = lambda t: "1x" if t < 2400 else ("2x" if t < 3600 else "OT")
xc = collections.Counter(); rc = collections.Counter(); n_rep = 0; tick_mismatch = 0
fs = sorted(glob.glob("C:/Users/benpe/ClashBot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json"))[::8]
for f in fs:
    d = json.load(open(f)); tag = os.path.basename(f)[7:19]; sides = [s for s in (0, 1) if f"{tag}_s{s}" in P]
    if not sides: continue
    n_rep += 1; lab = label_recording(d)
    for s in sides:
        M = P[f"{tag}_s{s}"]
        pro_x = sorted(XR[M["id"]], key=lambda r: r["tick"]); sim_x = sorted([b for b in lab["xbows"] if b["side"] == s], key=lambda b: b["tick"])
        if len(pro_x) != len(sim_x) or any(a["tick"] != b["tick"] for a, b in zip(pro_x, sim_x)): tick_mismatch += 1; continue
        for a, b in zip(pro_x, sim_x):
            sim = "def" if b["defensive_xbow"] else ("off" if b["offensive_xbow"] else "other")
            xc[(ph(a["tick"]), a["cls"], sim)] += 1
        for b in lab["rockets"]:
            if b["side"] != s: continue
            p = next(p for p in M["plays"] if p["name"] == "Rocket" and p["tick"] == b["tick"])
            pro_t = A.tower_target(M, p["x"], p["y"], p["tick"]) is not None
            rc[(ph(b["tick"]), pro_t, b["tower_rocket"])] += 1
out = {"replays": n_rep, "sides_skipped_tick_mismatch": tick_mismatch,
       "xbow_confusion(phase|pro_cls|sim_cls)": {"|".join(map(str, k)): v for k, v in sorted(xc.items())},
       "rocket_confusion(phase|pro_tower_aim2tiles|sim_tower_rocket)": {"|".join(map(str, k)): v for k, v in sorted(rc.items())}}
for p_ in ("1x", "2x", "OT"):
    pd = sum(v for (q, a, b), v in xc.items() if q == p_ and a == "def"); po = sum(v for (q, a, b), v in xc.items() if q == p_ and a == "off")
    sd = sum(v for (q, a, b), v in xc.items() if q == p_ and b == "def"); so = sum(v for (q, a, b), v in xc.items() if q == p_ and b == "off")
    n = sum(v for (q, a, b), v in xc.items() if q == p_)
    out[f"def_share|{p_}"] = {"pro_def/(def+off)": pd / max(pd + po, 1), "sim_def/(def+off)": sd / max(sd + so, 1), "sim_def/n_all": sd / max(n, 1), "n_all": n,
                              "agree": sum(v for (q, a, b), v in xc.items() if q == p_ and a == b) / max(n, 1)}
    pt = sum(v for (q, a, b), v in rc.items() if q == p_ and a); st = sum(v for (q, a, b), v in rc.items() if q == p_ and b is True)
    out[f"tower_rockets|{p_}"] = {"pro_aim_def": pt, "sim_landing_def": st, "sim_unknown": sum(v for (q, a, b), v in rc.items() if q == p_ and b is None),
                                  "rockets": sum(v for (q, a, b), v in rc.items() if q == p_)}
json.dump(out, open(L73 + "rocket_xbow_1008/defcheck.json", "w"), indent=1); print(json.dumps(out, indent=1))
