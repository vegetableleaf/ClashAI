"""Bot (live logs) tower-Rocket chip/catch classification + eligible-time series, same geometry as extract_pros.py, and
xbow_switch-format match records (for the Q3 X-Bow persistence re-run). Read-only on the live logs; completed logs only.
Own-frame tiles (core.to_own): enemy towers K (9,3), L (3.5,6.5), R (14.5,6.5)."""
import json, glob, os, pickle, sys, math, bisect, datetime, ctypes
import numpy as np
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
sys.path.insert(0, "C:/Users/benpe/ClashBot")
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_review")
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch")
import load as L, core
from extract import nav_outcomes, SLOTS
HERE = os.path.dirname(os.path.abspath(__file__))
D = L.D
ROCKET_ID, SPEED = 28000003, 350.0       # catalog Rocket card id; constant_projectile_speeds()['rocket'] millitiles/tick
SHAS = {"76fdfaac": "R1e", "e7359f2b": "live"}
TR = {"K": 1.4, "L": 1.0, "R": 1.0}


def phase(t): return "1x" if t < 2400 else ("2x" if t < 3600 else "OT")


def sha_of(f):
    for l in open(f):
        if l.startswith('{"event": "start"'):
            return (json.loads(l).get("ckpt_sha256") or "")[:8]
    return ""


def towers(s, obs):
    out = {}
    for b in s["bodies"]:
        sl = core.slot_of(b, obs)
        if sl and b[4] > 0: out[sl] = (b[4], b[5])
    return out


def enemy_troops(s, obs):
    return [core.to_own(obs, b[1], b[2]) for b in s["bodies"] if b[0] != obs and b[3] != -1 and b[4] > 0 and not (28000000 <= b[3] < 29000000)]


def tstate(tw, mx):
    mine = sum(tw[k][0] / mx[k] for k in ("mK", "mL", "mR") if k in tw)
    theirs = sum(tw[k][0] / mx[k] for k in ("eK", "eL", "eR") if k in tw)
    return mine - theirs, [2 - sum(k in tw for k in ("eL", "eR")), 2 - sum(k in tw for k in ("mL", "mR"))]


def q1_record(d, f):
    S = d["states"]
    if not S or d.get("state_src") != "decision": return None
    obs = S[0]["side"]; T = [s["tick"] for s in S]
    mx = {}
    for s in S:
        for k, v in towers(s, obs).items(): mx.setdefault(k, v[1])
    for k in SLOTS: mx.setdefault(k, 7032 if k.endswith("K") else 4424)
    series = []
    for i, s in enumerate(S):
        tw = towers(s, obs); tr = enemy_troops(s, obs)
        near = {}
        for k in ("eK", "eL", "eR"):
            if k not in tw: continue
            kind = "king" if k == "eK" else "princess"
            dm = min([math.hypot(x - core.TOWER_XY[k[1]][0], y - core.TOWER_XY[k[1]][1]) for x, y in tr] + [1e9])
            near[kind] = min(near.get(kind, 1e9), dm)
        lead, cr = tstate(tw, mx)
        dt = min(T[i + 1] - T[i], 40) if i + 1 < len(S) else 10
        series.append((s["tick"], s["el"], near.get("princess", 1e9) * 1000, near.get("king", 1e9) * 1000, lead, cr[0], cr[1], dt, "Rocket" in (s["hand"] or [])))
    m = core._plays({"file": d["file"]}, d)
    rk = []
    for p in m["plays"]:
        if p["name"] != "Rocket" or not p["conf"]: continue
        ax, ay = p["x"], p["y"]
        # landing: last own Rocket projectile sighting after the cast, plus remaining flight at catalog speed
        land, pt = None, (ax, ay)
        for s in S:
            if not (p["tick"] <= s["tick"] <= p["tick"] + 160): continue
            for q in s["proj"]:
                if q[0] == obs and q[3] == ROCKET_ID and q[4] is not None:
                    tx, ty = core.to_own(obs, q[4], q[5])
                    if math.hypot(tx - ax, ty - ay) < 2.5:
                        land = s["tick"] + math.hypot(q[4] - q[1], q[5] - q[2]) / SPEED; pt = (tx, ty)
        src = "proj" if land is not None else "fallback"
        if land is None: land = p["tick"] + 28 + math.hypot(ax - 9.0, ay - 29.0) * 1000 / SPEED
        j = bisect.bisect_right(T, land) - 1
        row = dict(tick=p["tick"], phase=phase(p["tick"]), landing=land, src=src, gap=(land - T[j]) if j >= 0 else None, towers=[], troops=None,
                   aim=(ax, ay), pt=pt)
        if j >= 0 and land - T[j] <= 25:
            s = S[j]; tw = towers(s, obs)
            row["troops"] = [(x, y) for x, y in enemy_troops(s, obs) if math.hypot(x - pt[0], y - pt[1]) <= 2.0]
            for k in ("eK", "eL", "eR"):
                if k in tw and math.hypot(pt[0] - core.TOWER_XY[k[1]][0], pt[1] - core.TOWER_XY[k[1]][1]) <= 2.0 + TR[k[1]]:
                    row["towers"].append(("king" if k == "eK" else "princess", tw[k][0] / mx[k]))
        jb = max(bisect.bisect_right(T, p["tick"]) - 1, 0)
        row["lead"], row["crowns"] = tstate(towers(S[jb], obs), mx)
        rk.append(row)
    return dict(id=d["file"], series=series, rockets=rk, end=T[-1])


def xbow_record(d, res):   # copy of xbow_switch/extract.build_bot's per-log body
    S = d["states"]
    m = core.build(d, res)
    if m is None or m["obs"] is None or not S: return None
    T = np.array([s["tick"] for s in S]); HP = {}; MX = {}
    for sl in SLOTS:
        ser = m["tower_hp"].get(sl, []); MX[sl] = ser[0][2] if ser else None
        arr = np.zeros(len(T)); j = 0; cur = None; dead = m["dead"].get(sl)
        for k, t in enumerate(T):
            while j < len(ser) and ser[j][0] <= t: cur = ser[j][1]; j += 1
            arr[k] = 0 if (dead is not None and t >= dead) else (cur if cur is not None else (ser[0][1] if ser else 0))
        HP[sl] = arr
    for sl in SLOTS:
        if MX[sl] is None: MX[sl] = 7032 if sl.endswith("K") else 4424
    xb = {}
    for s in S:
        for b in s["bodies"]:
            if b[3] == 27000008 and b[0] == m["obs"]:
                x, y = core.to_own(m["obs"], b[1], b[2])
                t = xb.setdefault(b[7], {"first": s["tick"], "x": x, "y": y}); t["last"] = s["tick"]
    for t in xb.values(): t["cens"] = t["last"] >= T[-1] - 15
    plays = [{"tick": p["tick"], "name": p["name"], "x": p["x"], "y": p["y"], "el": p["elixir"], "conf": p["conf"]} for p in m["plays"]]
    res_m = {"WIN": "W", "LOSS": "L", "DRAW": "D"}.get(m["result"].rstrip("*") if m["result"] else None)
    return {"kind": "bot", "id": m["file"], "cluster": m["file"], "res": res_m, "tiebreak": None, "end": int(T[-1]), "T": T, "HP": HP, "MX": MX,
            "EL": np.array([s["el"] for s in S]), "plays": plays, "xtracks": list(xb.values()), "model": m["model"], "ckpt": m["ckpt_sha"]}


if __name__ == "__main__":
    fs = sorted(glob.glob(D + "live_play_202610*.jsonl"))
    outs = nav_outcomes(); ot = [o[0] for o in outs]
    q1 = {v: [] for v in SHAS.values()}; xr = {v: [] for v in SHAS.values()}
    for i, f in enumerate(fs):
        sh = sha_of(f)
        if sh not in SHAS: continue
        d = L.load(f)
        if d["end"] is None and d["stop"] is None: continue      # in progress
        b = os.path.basename(f); st = datetime.datetime.strptime(b[10:25], "%Y%m%d_%H%M%S").timestamp()
        sec = (d["end"] or {}).get("seconds") or ((d["stop"] or {}).get("tick") or 3600) / 20.0
        k = bisect.bisect_left(ot, st + sec - 20); res = {}
        if k < len(ot) and ot[k] < st + sec + 300: res[b] = "WIN" if outs[k][1] else "LOSS"
        r = q1_record(d, f)
        if r: r["res"] = res.get(b); q1[SHAS[sh]].append(r)
        x = xbow_record(d, res)
        if x: xr[SHAS[sh]].append(x)
        if i % 50 == 0: print(i, len(fs), {k: len(v) for k, v in q1.items()}, flush=True)
    pickle.dump(q1, open(os.path.join(HERE, "bot_chip.pkl"), "wb")); pickle.dump(xr, open(os.path.join(HERE, "bot_xbow.pkl"), "wb"))
    print({k: (len(v), sum(len(r["rockets"]) for r in v)) for k, v in q1.items()}, {k: len(v) for k, v in xr.items()})
