"""Per-match feature extraction from live_play logs (cache.pkl built by load.py)."""
import pickle, re, collections, math, sys
sys.path.insert(0, "C:/Users/benpe/ClashBot")
from pipeline.obs_contract import _catalog_names
NAMES = _catalog_names()
BS = chr(92)
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_review/"
OVN = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L70/live/overnight.out"
COST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
TPS = 20.0
REACH = 13.04  # tiles, X-Bow placement centre to enemy tower centre
TOWER_XY = {"K": (9.0, 3.0), "L": (3.5, 6.5), "R": (14.5, 6.5)}  # enemy towers, own frame (tiles)

def phase_of(sec):
    return "P1" if sec < 120 else ("P2" if sec < 180 else "P3")

def nm(cid):
    return NAMES.get(cid, str(cid))

def read_results():
    res = {}; last = None
    for l in open(OVN, encoding="utf8", errors="replace"):
        if l.startswith('{"played"'):
            m = re.search(r'"log": "(.*?)"', l)
            if m: last = m.group(1).replace(BS + BS, "/").replace(BS, "/").split("/")[-1]
            continue
        m = re.search(r"\[ladder\] result: (WIN|LOSS|DRAW)", l)
        if m and last and last not in res:
            res[last] = m.group(1)
    return res

def to_own(side_obs, x, y):
    """raw millitiles -> own-frame tiles (own edge at y~32)."""
    if side_obs == 1: return x / 1000.0, y / 1000.0
    return (18000 - x) / 1000.0, (32000 - y) / 1000.0

def slot_of(b, obs):
    """b=(side,x,y,card,hp,maxhp,kind,addr). Return tower slot like 'eL','mK' or None."""
    if b[3] != -1: return None
    x, y = to_own(obs, b[1], b[2])
    mine = (b[0] == obs)
    for k, (tx, ty) in TOWER_XY.items():
        ty2 = 32 - ty if mine else ty
        if abs(x - tx) < 0.2 and abs(y - ty2) < 0.2:
            return ("m" if mine else "e") + k
    return None

def build(d, results):
    states = d["states"]
    if not states and not d["plays"]: return None
    obs = states[0]["side"] if states else None
    m = {"file": d["file"], "n_states": len(states), "obs": obs, "state_src": d.get("state_src")}
    st = d["start"] or {}
    ck = (st.get("ckpt") or "").replace(BS, "/")
    m["model"] = ck.split("/")[-2] if ck else "?"
    m["ckpt_sha"] = (st.get("ckpt_sha256") or "")[:8]
    m["end_tick"] = states[-1]["tick"] if states else ((d["stop"] or {}).get("tick") or max(p["tick"] for p in d["plays"]))
    m["dur_s"] = m["end_tick"] / TPS
    m["wall_s"] = (d["end"] or {}).get("seconds")
    m["overnight_result"] = results.get(d["file"])
    # tower timelines
    if not states:
        m.update({"tower_hp": {}, "dead": {k: None for k in ("eL","eR","mL","mR","eK","mK")}, "crowns_me": None, "crowns_opp": None, "final_hpfrac": {}, "derived_result": None})
        m["result"] = m["overnight_result"]; m["result_src"] = "ladder" if m["overnight_result"] else "unknown"
        return _plays(m, d)
    hp = collections.defaultdict(list)
    for s in states:
        for b in s["bodies"]:
            sl = slot_of(b, obs)
            if sl and b[4] > 0: hp[sl].append((s["tick"], b[4], b[5]))
    m["tower_hp"] = {k: v for k, v in hp.items()}
    dead = {}
    nst = len(states)
    for sl in ("eL", "eR", "mL", "mR", "eK", "mK"):
        v = hp.get(sl)
        if not v: dead[sl] = None; continue
        last = v[-1][0]
        after = [s["tick"] for s in states if s["tick"] > last]
        dead[sl] = after[0] if len(after) >= 3 else None  # tick of first state without the tower
    m["dead"] = dead
    m["crowns_me"] = sum(dead[k] is not None for k in ("eL", "eR")) + (3 if dead["eK"] is not None else 0)
    m["crowns_opp"] = sum(dead[k] is not None for k in ("mL", "mR")) + (3 if dead["mK"] is not None else 0)
    m["crowns_me"] = min(m["crowns_me"], 3); m["crowns_opp"] = min(m["crowns_opp"], 3)
    # final hp frac per slot (last sighting)
    fin = {}
    for sl, v in hp.items():
        fin[sl] = v[-1][1] / v[-1][2]
    m["final_hpfrac"] = fin
    # derived result
    if m["crowns_me"] > m["crowns_opp"]: dr = "WIN"
    elif m["crowns_me"] < m["crowns_opp"]: dr = "LOSS"
    else:
        # same crowns: compare total remaining tower hp fraction (approx. tiebreak)
        a = sum(fin.get(k, 0) * 1 for k in ("eK", "eL", "eR")); b = sum(fin.get(k, 0) for k in ("mK", "mL", "mR"))
        dr = "WIN" if a < b else ("LOSS" if a > b else "DRAW")
    m["derived_result"] = dr
    # The log ends at the final blow, so the last tower kill is never in a state. If the ladder result disagrees with the observed crowns and the
    # match ended before the clock ran out (<295 s), the decisive crown was scored after the last state: attribute it to the winner's side.
    m["crowns_adjusted"] = False
    ov = m["overnight_result"]
    if ov in ("WIN", "LOSS") and m["dur_s"] < 295 and ov != dr:
        mine = ov == "WIN"
        cand = [k for k in (("eL", "eR") if mine else ("mL", "mR")) if dead[k] is None]
        if not cand: cand = [("eK" if mine else "mK")]
        k = min(cand, key=lambda z: fin.get(z, 1.0))
        dead[k] = states[-1]["tick"]; m["crowns_adjusted"] = True
        if k in ("eK", "mK"): m["crowns_me" if mine else "crowns_opp"] = 3
        else: m["crowns_me" if mine else "crowns_opp"] += 1
        dr = ov; m["derived_result"] = ov + "*"  # '*' = needed the unobserved final blow
    m["result"] = m["overnight_result"] or dr
    m["result_src"] = "ladder" if m["overnight_result"] else "derived"
    return _plays(m, d)

def _plays(m, d):
    # plays (confirmed ones)
    conf = list(d["conf"]); used = set(); plays = []
    for p in d["plays"]:
        ok = False
        for i, c in enumerate(conf):
            if i in used: continue
            if c["name"] == p["name"] and c["tick"] >= p["tick"] and c["tick"] - p["tick"] < 200:
                used.add(i); ok = True; break
        x, y = 18 - p["xy"][0] * 18, p["xy"][1] * 32  # xy x-axis is mirrored vs raw own frame (verified on 835 Xbow/Tesla plays)
        plays.append({"tick": p["tick"], "sec": p["tick"] / TPS, "name": p["name"], "x": x, "y": y, "elixir": p["elixir"],
                      "conf": ok, "p": p.get("p_play")})
    m["plays"] = plays
    m["n_plays"] = len(plays); m["n_conf"] = sum(p["conf"] for p in plays)
    m["abil"] = [{"tick": a["tick"], "why": a["why"], "elixir": a["elixir"]} for a in d["abil"]]
    m["abil_conf"] = len(d["abil_conf"])
    return m

def load_all():
    data = pickle.load(open(HERE + "cache.pkl", "rb"))
    res = read_results()
    out = []
    for d in data:
        m = build(d, res)
        if m: out.append((m, d))
    return out

if __name__ == "__main__":
    xs = load_all()
    print(len(xs))
    c = collections.Counter((m["result_src"], m["result"], m["derived_result"]) for m, d in xs)
    for k, v in sorted(c.items()): print(k, v)
    # print a few
    for m, d in xs[:3] + xs[-3:]:
        print(m["file"], m["model"], m["result"], m["derived_result"], m["crowns_me"], m["crowns_opp"], round(m["dur_s"]), m["n_plays"], m["n_conf"], {k: (v // 20 if v else None) for k, v in m["dead"].items()})
