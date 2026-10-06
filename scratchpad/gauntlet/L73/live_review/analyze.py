"""Event-level analysis for each match. Imports core.build() output (m) and the raw cache entry (d)."""
import bisect, collections, math
from core import *

BARRELS = {28000004, 13000081}
WINCON = {"HogRider", "RoyalHogs", "Balloon", "Giant", "RoyalGiant", "GoblinGiant", "Golem", "ElixirGolem", "ElectroGiant",
          "LavaHound", "BattleRam", "RamRider", "Miner", "Pekka", "MegaKnight", "SkeletonBalloon", "Wallbreakers", "GoblinDemolisher",
          "BossBandit", "Prince", "DarkPrince", "Ghost", "GoblinMachine", "MovingCannon"}
TESLA = {27000006, 13000102}
XBOW = 27000008
CHEAP = {"Skeletons", "Log", "Knight"}

def own_bodies(s, obs):
    mine, enemy = [], []
    for b in s["bodies"]:
        if b[3] == -1: continue
        x, y = to_own(obs, b[1], b[2])
        (mine if b[0] == obs else enemy).append((x, y, b[3], b[4], b[5], b[7]))
    return mine, enemy

def lane(x): return "L" if x < 9 else "R"

def analyze(m, d):
    obs = m["obs"]; S = d["states"]; T = [s["tick"] for s in S]
    dead = m["dead"]
    def near(t):
        i = bisect.bisect_left(T, t)
        if i >= len(T): return len(T) - 1
        if i > 0 and abs(T[i - 1] - t) <= abs(T[i] - t): return i - 1
        return i
    def alive(sl, t):
        return (dead[sl] is None or dead[sl] > t) and sl in m["tower_hp"]
    def crowns_at(t):
        me = sum(1 for k in ("eL", "eR") if dead[k] is not None and dead[k] <= t) + (3 if dead["eK"] is not None and dead["eK"] <= t else 0)
        op = sum(1 for k in ("mL", "mR") if dead[k] is not None and dead[k] <= t) + (3 if dead["mK"] is not None and dead["mK"] <= t else 0)
        return me, op
    def hp_at(sl, t):
        v = m["tower_hp"].get(sl)
        if not v: return None
        best = None
        for tk, h, mx in v:
            if tk <= t: best = (h, mx)
            else: break
        return best
    def hp_min(sl, t0, t1):
        v = m["tower_hp"].get(sl)
        if not v: return None
        hs = [h / mx for tk, h, mx in v if t0 <= tk <= t1]
        return min(hs) if hs else None
    out = {}
    plays = [p for p in m["plays"] if p["conf"]]
    # ---------- per-phase play counts, cheap share, elixir at play
    ph = {k: collections.Counter() for k in ("P1", "P2", "P3", "T3")}
    phel = {k: [] for k in ph}
    for p in plays:
        k = phase_of(p["sec"]); ph[k][p["name"]] += 1; phel[k].append(p["elixir"])
        if p["sec"] >= 240: ph["T3"][p["name"]] += 1; phel["T3"].append(p["elixir"])
    out["phase_plays"] = {k: dict(v) for k, v in ph.items()}
    out["phase_elixir"] = {k: (sum(v) / len(v) if v else None) for k, v in phel.items()}
    out["phase_cheap"] = {k: sum(v[c] for c in CHEAP) for k, v in ph.items()}
    out["phase_n"] = {k: sum(v.values()) for k, v in ph.items()}
    if not S:  # play-only log (no state events): only play-based metrics exist
        out.update({"leak": None, "abil": [{"tick": a["tick"], "sec": a["tick"] / TPS, "why": a["why"], "elixir": a["elixir"], "enemies_near": None, "hero_seen": None} for a in m["abil"]],
                    "enemy_events": [], "enemy_cards": [], "barrels": [], "wincons": [], "rocket_avail_s": None, "rocket_inhand_s": None, "tower_tl": None, "first_crown": None, "dead_s": {},
                    "rockets": [{"tick": p["tick"], "sec": p["sec"], "elixir": p["elixir"], "x": p["x"], "y": p["y"], "target": None, "crowns": None} for p in plays if p["name"] == "Rocket"],
                    "xbows": [{"tick": p["tick"], "sec": p["sec"], "lane": lane(p["x"]), "x": p["x"], "y": p["y"], "reach": None, "lane_dead": None, "tesla_adj": None, "crowns": None, "elixir": p["elixir"]} for p in plays if p["name"] == "Xbow"],
                    "no_state": True})
        return out
    # ---------- elixir leak: share of state-time with own elixir >= 9.5, by phase
    leak = {k: [0.0, 0.0] for k in ("P1", "P2", "P3")}
    for i in range(len(S) - 1):
        dt = min(T[i + 1] - T[i], 30) / TPS
        k = phase_of(T[i] / TPS); leak[k][1] += dt
        if S[i]["el"] >= 9.5: leak[k][0] += dt
    out["leak"] = leak
    # ---------- hero ability presses
    ab = []
    for a in m["abil"]:
        i = near(a["tick"]); mine, enemy = own_bodies(S[i], obs)
        hero = [b for b in mine if b[2] == 203000023]
        n = None
        if hero:
            hx, hy = hero[0][0], hero[0][1]
            n = sum(1 for e in enemy if math.hypot(e[0] - hx, e[1] - hy) <= 5.5)
        ab.append({"tick": a["tick"], "sec": a["tick"] / TPS, "why": a["why"], "elixir": a["elixir"], "enemies_near": n, "hero_seen": bool(hero)})
    out["abil"] = ab
    # ---------- enemy spawn events
    seen = set(); ev = []
    for i, s in enumerate(S):
        mine, enemy = own_bodies(s, obs)
        for e in enemy:
            if e[5] in seen: continue
            seen.add(e[5])
            if s["tick"] < 160: continue  # initial state of match, not a play
            ev.append({"tick": s["tick"], "card": e[2], "name": nm(e[2]), "x": e[0], "y": e[1], "i": i})
    # cluster
    cl = []
    for e in sorted(ev, key=lambda z: z["tick"]):
        for c in cl:
            if c["card"] == e["card"] and abs(c["tick"] - e["tick"]) <= 30 and abs(c["x"] - e["x"]) < 5: break
        else:
            cl.append(dict(e))
    out["enemy_events"] = [{k: v for k, v in c.items() if k != "i"} for c in cl]
    out["enemy_cards"] = sorted({c["name"] for c in cl if not c["name"].isdigit()})
    # ---------- barrels: Log response. The barrel is visible as an enemy PROJECTILE (flight ~1.5 s, with target_x/y) before it lands.
    logs = [p for p in plays if p["name"] == "Log"]
    bar = []
    fl = []  # (tick, own-frame landing x, y, state index)
    if m["state_src"] == "decision":
        prev_n = 0; prev_t = -999
        for i, s_ in enumerate(S):
            qs = [q for q in s_["proj"] if q[3] in BARRELS and q[0] != obs]
            n = len(qs)
            if s_["tick"] - prev_t > 40: prev_n = 0
            if n > prev_n:
                for q in qs[prev_n:n]:
                    tx, ty = to_own(obs, q[4] or q[1], q[5] or q[2]); fl.append((s_["tick"], tx, ty, i))
            prev_n = n; prev_t = s_["tick"]
    else:
        for c in cl:
            if c["card"] in BARRELS: fl.append((c["tick"], c["x"], c["y"], near(c["tick"])))
    for (t, bx, by, i) in fl:
        hand = S[i]["hand"]; el = S[i]["el"]; hand_known = hand is not None; hand = hand or []
        prev = [p for p in logs if p["tick"] < t - 10]   # a Log decided >=0.5 s before the barrel appeared = "spent before"
        dt_prev = (t - prev[-1]["tick"]) / TPS if prev else None
        resp = [p for p in logs if t - 10 <= p["tick"] <= t + 60 and abs(p["x"] - bx) <= 5]
        resp_any = [p for p in logs if t - 10 <= p["tick"] <= t + 60]
        ln = lane(bx); tw = "m" + ln
        before = hp_at(tw, t); after = hp_min(tw, t + 30, t + 230)  # tower HP in the 10 s after the goblins land
        dmg = None
        if before and after is not None: dmg = before[0] / before[1] - after
        bar.append({"tick": t, "sec": t / TPS, "lane": ln, "x": bx, "y": by, "log_in_hand": ("Log" in hand) if hand_known else None, "elixir": el,
                    "since_last_log_s": dt_prev, "log_responded": bool(resp), "log_any_near_time": bool(resp_any),
                    "tower_dmg_frac_10s": dmg, "lane_tower_alive": alive(tw, t), "crowns": crowns_at(t)})
    out["barrels"] = bar
    # ---------- win-cons vs Tesla
    wc = []
    for c in cl:
        if c["name"] not in WINCON or c["card"] in BARRELS: continue
        t = c["tick"]; i = near(t)
        mine, enemy = own_bodies(S[i], obs)
        tes = [b for b in mine if b[2] in TESLA]
        prevT = [p for p in plays if p["name"] == "Tesla" and p["tick"] <= t]
        ln = lane(c["x"]); tw = "m" + ln
        before = hp_at(tw, t); after = hp_min(tw, t, t + 300)
        dmg = (before[0] / before[1] - after) if (before and after is not None) else None
        wc.append({"tick": t, "sec": t / TPS, "name": c["name"], "lane": ln, "tesla_on_board": len(tes), "tesla_in_hand": ("Tesla" in S[i]["hand"]) if S[i]["hand"] is not None else None,
                   "elixir": S[i]["el"], "since_tesla_play_s": (t - prevT[-1]["tick"]) / TPS if prevT else None,
                   "tower_dmg_frac_15s": dmg, "crowns": crowns_at(t)})
    out["wincons"] = wc
    # ---------- Rocket
    rk = []
    for p in plays:
        if p["name"] != "Rocket": continue
        t = p["tick"]; x, y = p["x"], p["y"]
        best = None
        for sl, (tx, ty) in (("eL", TOWER_XY["L"]), ("eR", TOWER_XY["R"]), ("eK", TOWER_XY["K"])):
            dd = math.hypot(x - tx, y - ty)
            if dd <= 3.5 and alive(sl, t) and (best is None or dd < best[1]): best = (sl, dd)
        i = near(t + 30); mine, enemy = own_bodies(S[i], obs)
        n_en = sum(1 for e in enemy if math.hypot(e[0] - x, e[1] - y) <= 2.5)
        r = {"tick": t, "sec": p["sec"], "elixir": p["elixir"], "x": x, "y": y, "target": best[0] if best else ("troops" if n_en else "empty"),
             "enemies_in_radius": n_en, "crowns": crowns_at(t)}
        if best:
            sl = best[0]; b = hp_at(sl, t); a = hp_min(sl, t + 30, t + 100)
            r["tower_hp_frac_before"] = b[0] / b[1] if b else None
            r["tower_drop_frac"] = (b[0] / b[1] - a) if (b and a is not None) else None
            r["killed_within_5s"] = dead[sl] is not None and t <= dead[sl] <= t + 100
        rk.append(r)
    out["rockets"] = rk
    # rocket availability: state-time with Rocket in hand and elixir >= 6
    av = [0.0, 0.0]
    for i in range(len(S) - 1):
        dt = min(T[i + 1] - T[i], 30) / TPS
        if S[i]["hand"] and "Rocket" in S[i]["hand"]:
            av[1] += dt
            if S[i]["el"] >= 6: av[0] += dt
    out["rocket_avail_s"] = av[0]; out["rocket_inhand_s"] = av[1]
    # ---------- X-Bow
    xb = []
    xb_bodies = collections.defaultdict(list)  # addr -> [(tick,x,y,hp)]
    for s in S:
        mine, _ = own_bodies(s, obs)
        for b in mine:
            if b[2] == XBOW: xb_bodies[b[5]].append((s["tick"], b[0], b[1], b[3] / b[4]))
    tesla_plays = [p for p in plays if p["name"] == "Tesla"]
    claimed = set()
    for p in plays:
        if p["name"] != "Xbow": continue
        t = p["tick"]; x, y = p["x"], p["y"]
        dists = {}
        for sl, (tx, ty) in (("eL", TOWER_XY["L"]), ("eR", TOWER_XY["R"]), ("eK", TOWER_XY["K"])):
            if alive(sl, t): dists[sl] = math.hypot(x - tx, y - ty)
        reach = [sl for sl, dd in dists.items() if dd <= REACH]
        ln = lane(x)
        lane_dead = not alive("e" + ln, t) and ("e" + ln) in m["tower_hp"]
        # tesla adjacency: tesla played within +-10 s and <= 6 tiles
        tes = [q for q in tesla_plays if abs(q["tick"] - t) <= 200 and math.hypot(q["x"] - x, q["y"] - y) <= 6]
        # find body
        body = None
        for addr, v in xb_bodies.items():
            if addr in claimed: continue
            if t - 20 <= v[0][0] <= t + 260 and math.hypot(v[0][1] - x, v[0][2] - y) <= 3.5:
                if body is None or v[0][0] < xb_bodies[body][0][0]: body = addr
        if body: claimed.add(body)
        life = None; shells = 0; tdmg = None; killed = None
        if body:
            v = xb_bodies[body]; life = (v[-1][0] - v[0][0]) / TPS
            killed = v[-1][0] < T[-1] - 40 and life < 24  # natural decay lasts ~26.5 s from first sighting (after the 3.5 s deploy)
            bx, by = v[0][1], v[0][2]
            for s in S:
                if v[0][0] <= s["tick"] <= v[-1][0]:
                    for q in s["proj"]:
                        if q[3] == XBOW and q[0] == obs:
                            qx, qy = to_own(obs, q[4] or 0, q[5] or 0)
                            if math.hypot(qx - TOWER_XY["L"][0], qy - TOWER_XY["L"][1]) < 1 or math.hypot(qx - TOWER_XY["R"][0], qy - TOWER_XY["R"][1]) < 1 or math.hypot(qx - 9, qy - 3) < 1:
                                if math.hypot(*(a - b for a, b in zip(to_own(obs, q[1], q[2]), (bx, by)))) < 14: shells += 1
            if reach:
                sl = min(reach, key=lambda z: dists[z]); b0 = hp_at(sl, v[0][0]); b1 = hp_min(sl, v[0][0], v[-1][0] + 20)
                tdmg = (b0[0] / b0[1] - b1) if (b0 and b1 is not None) else None
        me, op = crowns_at(t)
        xb.append({"tick": t, "sec": p["sec"], "lane": ln, "x": x, "y": y, "reach": bool(reach), "reach_slots": reach,
                   "min_dist": min(dists.values()) if dists else None, "lane_dead": lane_dead, "tesla_adj": bool(tes), "crowns": (me, op),
                   "elixir": p["elixir"], "life_s": life, "shell_states": shells, "tower_dmg_frac": tdmg, "killed_early": killed})
    out["xbows"] = xb
    # ---------- base rates (state-time shares) used to judge whether barrel/win-con arrivals are special
    base = {"t": 0.0, "log_in_hand": 0.0, "within10s_after_log": 0.0, "tesla_on_board": 0.0, "tesla_in_hand": 0.0, "log_ticks": [p["tick"] for p in logs]}
    lt = base["log_ticks"]
    for i in range(len(S) - 1):
        dt = min(T[i + 1] - T[i], 30) / TPS
        base["t"] += dt
        if S[i]["hand"] and "Log" in S[i]["hand"]: base["log_in_hand"] += dt
        if S[i]["hand"] and "Tesla" in S[i]["hand"]: base["tesla_in_hand"] += dt
        j = bisect.bisect_right(lt, T[i] - 10)  # last Log decided at or before tick-10
        if j > 0 and (T[i] - lt[j - 1]) / TPS <= 10: base["within10s_after_log"] += dt
        if any(b[3] in TESLA and b[0] == obs for b in S[i]["bodies"]): base["tesla_on_board"] += dt
    base.pop("log_ticks"); out["base"] = base
    # ---------- tower timeline
    tl = {}
    for sec in (60, 120, 180):
        tl[sec] = {sl: (hp_at(sl, sec * 20)[0] / hp_at(sl, sec * 20)[1] if hp_at(sl, sec * 20) else None) for sl in ("eL", "eR", "eK", "mL", "mR", "mK")}
    out["tower_tl"] = tl
    out["first_crown"] = None
    evs = [(dead[k], "me") for k in ("eL", "eR") if dead[k] is not None] + [(dead[k], "opp") for k in ("mL", "mR") if dead[k] is not None]
    if evs: out["first_crown"] = min(evs)
    out["dead_s"] = {k: (v / TPS if v is not None else None) for k, v in dead.items()}
    return out

if __name__ == "__main__":
    xs = load_all()
    m, d = xs[5]
    o = analyze(m, d)
    import json
    print(m["file"], m["result"])
    for k, v in o.items():
        print(k, json.dumps(v, default=str)[:900])
