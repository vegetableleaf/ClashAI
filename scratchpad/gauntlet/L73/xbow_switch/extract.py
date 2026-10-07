"""Stage 1: build unified per-match records for PROS (icebow_public_v1 re-drives) and BOT (live logs). CPU only, read-only on inputs."""
import json, glob, os, pickle, sys, time, bisect, datetime
import numpy as np
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch/"
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_review")
SLOTS = ["eK", "eL", "eR", "mK", "mL", "mR"]
TOWER_XY = {"K": (9.0, 3.0), "L": (3.5, 6.5), "R": (14.5, 6.5)}   # enemy towers, own frame (own edge y~32)
BASE = {"Xbow", "Skeletons", "Log", "Knight", "Tesla", "Tornado", "IceWizard", "Rocket"}
PRO_NAME = {"skeletons": "Skeletons", "ice-wizard": "IceWizard", "knight": "Knight", "the-log": "Log", "tesla": "Tesla", "x-bow": "Xbow", "tornado": "Tornado", "rocket": "Rocket"}

def slot_from_xy(x, y):  # own-frame tiles -> 'eK','mL',...
    for k, (tx, ty) in TOWER_XY.items():
        if abs(x - tx) < 0.2 and abs(y - ty) < 0.2: return "e" + k
        if abs(x - tx) < 0.2 and abs(y - (32 - ty)) < 0.2: return "m" + k
    return None

def pro_records(path):
    d = json.load(open(path))
    base = [{c.split("@")[0] for c in d["final_decks"][s]} for s in "01"]
    cb = d["expected"]["crowns_by_side"]; exp = d["expected"]["result"]
    out = []
    for s in (0, 1):
        if base[s] != BASE: continue
        o = 1 - s
        # result relative to icebow side s. 'expected.result' is relative to side 1 (verified: win <=> side1 crowns higher whenever crowns differ)
        if cb[str(s)] > cb[str(o)]: res = "W"
        elif cb[str(s)] < cb[str(o)]: res = "L"
        else: res = {"win": "W", "loss": "L"}.get(exp, "D") if s == 1 else {"win": "L", "loss": "W"}.get(exp, "D")
        fx = (lambda x, y: (x / 1000.0, y / 1000.0)) if s == 1 else (lambda x, y: ((18000 - x) / 1000.0, (32000 - y) / 1000.0))
        T = []; HP = {k: [] for k in SLOTS}; MX = {}; EL = []; xb = {}
        for fr in d["frames"]:
            T.append(fr["tick"]); EL.append(fr["elixir"][s])
            seen = set()
            for tw in fr["towers"]:
                sl = slot_from_xy(*fx(tw[3], tw[4]))
                if sl is None: continue
                HP[sl].append(tw[5]); MX[sl] = tw[6]; seen.add(sl)
            for sl in SLOTS:
                if sl not in seen: HP[sl].append(0)
            for e in fr["entities"]:
                if e[0] == s and e[3] == "Xbow":
                    t = xb.setdefault(e[8], {"first": fr["tick"], "x": e[1], "y": e[2]}); t["last"] = fr["tick"]
        last_tick = T[-1]
        for t in xb.values():
            t["cens"] = (t["last"] == last_tick); t["x"], t["y"] = fx(t["x"], t["y"])
        plays = []
        for p in d["log"]:
            if p["side"] != s or not p.get("accepted") or "ability" in p: continue
            x, y = fx(p["x"], p["y"])
            plays.append({"tick": p["tick"], "name": PRO_NAME.get(p["card"], p["card"]), "x": x, "y": y, "el": p.get("elixir_before")})
        g = d["grade"]
        eng = d["final"]["outcome"]; eng_res = "D" if eng not in ("side0_win", "side1_win") else ("W" if eng == f"side{s}_win" else "L")
        out.append({"kind": "pro", "id": os.path.basename(path)[7:19] + f"_s{s}", "cluster": os.path.basename(path), "res": res, "tiebreak": cb["0"] == cb["1"],
                    "end": d["final"]["tick"], "T": np.array(T), "HP": {k: np.array(v) for k, v in HP.items()}, "MX": MX, "EL": np.array(EL),
                    "plays": plays, "xtracks": list(xb.values()), "crowns_match": bool(g["crowns_match"]), "eng_agree": eng_res == res,
                    "term": d["final"]["termination_reason"], "side": s})
    return out

def build_pros():
    out = []; t0 = time.time()
    fs = sorted(glob.glob("C:/Users/benpe/ClashBot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json"))
    for i, f in enumerate(fs):
        out += pro_records(f)
        if i % 200 == 0: print("pro", i, len(fs), len(out), round(time.time() - t0), flush=True)
    pickle.dump(out, open(HERE + "pros.pkl", "wb"))
    print("pros", len(out))

# ---------------- bot
def nav_outcomes():
    outs = []
    for f in sorted(glob.glob("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/ladder_nav_*.jsonl")):
        for l in open(f):
            if '"outcome"' not in l: continue
            try: e = json.loads(l)
            except Exception: continue
            if e.get("event") == "outcome": outs.append((e["t"], e["won"]))
    return sorted(outs)

def build_bot():
    import load as L, core
    D = L.D
    fs = [f for f in sorted(glob.glob(D + "live_play_2026100[456]_*.jsonl"))]
    outs = nav_outcomes(); ot = [o[0] for o in outs]
    raw = []; res = {}
    for f in fs:
        d = L.load(f); raw.append(d)
        b = os.path.basename(f)
        st = datetime.datetime.strptime(b[10:25], "%Y%m%d_%H%M%S").timestamp()
        sec = (d["end"] or {}).get("seconds") or ((d["stop"] or {}).get("tick") or 3600) / 20.0
        # first outcome event after the match's expected end (within 40..400 s after start+dur)
        i = bisect.bisect_left(ot, st + sec - 20)
        if i < len(ot) and ot[i] < st + sec + 300 and (i + 1 >= len(ot) or True):
            res[b] = "WIN" if outs[i][1] else "LOSS"
    legacy = core.read_results()
    agree = [(res[k], legacy[k]) for k in res if k in legacy]
    print("nav-vs-overnight agreement", sum(a == b for a, b in agree), "/", len(agree), "nav matched", len(res), "of", len(fs), flush=True)
    out = []
    for d in raw:
        if not d["states"]: continue
        m = core.build(d, res)
        if m is None or m["obs"] is None: continue
        S = d["states"]; T = np.array([s["tick"] for s in S])
        HP = {}; MX = {}
        for sl in SLOTS:
            ser = m["tower_hp"].get(sl, [])
            MX[sl] = ser[0][2] if ser else None
            arr = np.zeros(len(T)); j = 0; cur = None; dead = m["dead"].get(sl)
            for k, t in enumerate(T):
                while j < len(ser) and ser[j][0] <= t: cur = ser[j][1]; j += 1
                if dead is not None and t >= dead: cur_v = 0
                else: cur_v = cur if cur is not None else (ser[0][1] if ser else 0)
                arr[k] = cur_v
            HP[sl] = arr
        for sl in SLOTS:
            if MX[sl] is None: MX[sl] = 4824 if sl.endswith("K") else 3052  # never sighted: nominal
        xb = {}
        for s in S:
            for b in s["bodies"]:
                if b[3] == 27000008 and b[0] == m["obs"]:
                    x, y = core.to_own(m["obs"], b[1], b[2])
                    t = xb.setdefault(b[7], {"first": s["tick"], "x": x, "y": y}); t["last"] = s["tick"]
        for t in xb.values(): t["cens"] = t["last"] >= T[-1] - 15
        plays = [{"tick": p["tick"], "name": p["name"], "x": p["x"], "y": p["y"], "el": p["elixir"], "conf": p["conf"]} for p in m["plays"]]
        res_m = {"WIN": "W", "LOSS": "L", "DRAW": "D"}.get(m["result"].rstrip("*") if m["result"] else None)
        out.append({"kind": "bot", "id": m["file"], "cluster": m["file"], "res": res_m, "res_src": m["result_src"], "tiebreak": None, "end": int(T[-1]), "T": T, "HP": HP, "MX": MX,
                    "EL": np.array([s["el"] for s in S]), "plays": plays, "xtracks": list(xb.values()), "model": m["model"], "ckpt": m["ckpt_sha"], "obs": m["obs"],
                    "dur_s": m["dur_s"], "nav": res.get(m["file"])})
    pickle.dump(out, open(HERE + "bot.pkl", "wb"))
    print("bot", len(out), "of", len(raw))

if __name__ == "__main__":
    what = sys.argv[1]
    if what == "pros": build_pros()
    else: build_bot()
