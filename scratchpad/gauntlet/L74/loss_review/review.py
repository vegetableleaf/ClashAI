"""STANDING live loss review (L74). Re-runnable, read-only on the live logs.

  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/loss_review/review.py            # analyse new logs, rebuild report.md
  ... review.py --report-only                                                              # no parsing, rebuild report.md
  ... review.py --limit 50                                                                 # parse at most 50 new logs this run
  ... review.py --selftest

Ledger analyzed.txt = one log file name per line. A log is analysed once (row appended to matches.jsonl) when it has an
'end'/'stop' event and is >= 10 min old; in-progress logs are left for the next run. Logs are read from the MAIN repo
(LOGDIR). Results are resolved at REPORT time (ladder lines in overnight.out can land after the log closes), so a rerun
picks up late results without reparsing.
Public information only: own state + enemy bodies/projectiles on the board + the public-play opponent elixir counter.
The single exception is the 'opp_elixir_true_EVAL_ONLY' field of old frame logs, used ONLY for the counter-bias diagnostic.
Single process, below-normal priority (the laptop is shared).
"""
import os, sys
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # below normal
except Exception:
    pass
import json, glob, math, bisect, time, datetime, argparse, collections, re, random

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
MAIN = "C:/Users/benpe/ClashBot/"
LOGDIR = MAIN + "scratchpad/gauntlet/L68/live_reader/"
NAVGLOB = LOGDIR + "ladder_nav_*.jsonl"
OVN = MAIN + "scratchpad/gauntlet/L70/live/overnight.out"          # read only
CATALOG = MAIN + "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json"
UNITV = LOGDIR + "unit_values.json"
LEDGER, ROWS, REPORT = HERE + "analyzed.txt", HERE + "matches.jsonl", HERE + "report.md"
PRO = HERE + "pro_baseline.json"                                    # written by pro_baseline.py (optional)

TPS = 20.0
MIN_AGE_S = 600
PH = (("1x", 0, 2400), ("2x", 2400, 3600), ("OT", 3600, 10 ** 9))
REGEN = {"1x": 1 / 56.0, "2x": 2 / 56.0, "OT": 2 / 56.0}           # elixir per tick; checked by the slope diagnostic in the report
CAP = 9.9                                                           # 'at the cap' (own_elixir_raw saturates at 10.0)
REACH = 13.04                                                       # X-Bow placement centre -> enemy tower centre (L70/gen_v31/xbow_reach_public.json)
ROCKET_DMG = 497                                                    # measured live Rocket tower damage (131352)
THREAT_V, THREAT_Y = 7.0, 16.0                                      # push-Rocket worker q4: >= 7 elixir of enemy bodies at own y <= 16
MY_T = {"mK": (9.0, 3.0), "mL": (3.5, 6.5), "mR": (14.5, 6.5)}
EN_T = {"eK": (9.0, 29.0), "eL": (3.5, 25.5), "eR": (14.5, 25.5)}
COST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
AIR = {"BabyDragon", "InfernoDragon", "ElectroDragon", "Balloon", "Minions", "MinionHorde", "MegaMinion", "SkeletonDragons", "Phoenix",
       "LavaHound", "LavaPups", "Bats", "SkeletonBalloon", "BatsEvo", "Minion", "Bat", "LavaPup"}
TOKENS = {"Skeletons", "Bats", "SkeletonWarriors", "SpearGoblins"}
XBOW_COUNTERS = {"InfernoTower", "InfernoDragon", "Earthquake", "Lightning", "Rocket", "Fireball", "Poison", "Pekka", "MiniPekka",
                 "Prince", "DarkPrince", "Valkyrie", "Knight", "Golem", "Giant", "RoyalGiant", "MegaKnight", "Bowler"}


def ph(t): return "1x" if t < 2400 else ("2x" if t < 3600 else "OT")


# ------------------------------------------------------------------ catalog (public card data)
def _catalog():
    names, costs = {}, {}
    for c in json.load(open(CATALOG))["cards"]:
        for k in ("card_id", "evolution_form_id", "hero_form_id"):
            if c.get(k) is not None:
                names[int(c[k])] = c["display_name"]; costs[c["display_name"]] = c["elixir"]
    names[203000023] = "IceWizard"          # hero Ice Wizard alias (reader_identity_aliases.py)
    uv = json.load(open(UNITV))["value_per_unit"]
    return names, costs, uv


NAME, NCOST, UV = {}, {}, {}


def uval(n):
    if n in UV: return UV[n]
    return float(NCOST.get(n, 0.5))


# Body-value fix (L74 econ2, 2026-10-08): the reader labels spawned children with the PARENT card (a Witch's skeletons are
# card 'Witch', max_hp 119 vs 1220, and were valued 5 elixir each). A body is worth uval(card) x min(1, its max_hp / the largest
# max_hp seen for that card in the match); spell cards whose bodies are all small units get a per-unit value.
SPELL_UNIT = {"Graveyard": 1 / 3.0, "GoblinBarrel": 1.0}
BODY_FIX = os.environ.get("REVIEW_BODY_FIX", "1") == "1"


def body_valuer(S):
    """-> bval(name, max_hp) for one match's states (S[i][4] bodies: mine, X, Y, cid, hp, max_hp, kind, addr)."""
    top = collections.Counter()
    for s in S:
        for b in s[4]:
            if not b[0] and b[3] != -1 and (b[5] or 0) > 0: top[b[3]] = max(top[b[3]], b[5])
    def bval(cid, mx):
        n = nm(cid)
        if not BODY_FIX: return uval(n)
        if n in SPELL_UNIT: return SPELL_UNIT[n]
        return uval(n) * (min(1.0, mx / top[cid]) if mx and mx > 0 and top[cid] else 1.0)
    return bval


def own(side, x, y):
    """raw millitiles -> own frame tiles: own king (9,3), enemy king (9,29); enemy side = larger y."""
    return ((18000 - x) / 1000.0, (32000 - y) / 1000.0) if side == 1 else (x / 1000.0, y / 1000.0)


def model_to_own(xy): return xy[0] * 18.0, (1.0 - xy[1]) * 32.0


# ------------------------------------------------------------------ parse one log -> compact record
def parse(f):
    r = dict(file=os.path.basename(f), start={}, end=None, stop=None, side=None, S=[], plays=[], conf=[], unconf=[], abil=[], abil_conf=0,
             starved=0, reader_closed=0, tap=[], est_true=[], n_dec=0, n_frame=0, decide_ms=[], backlog_pos=0)
    frames = []
    with open(f, encoding="utf8", errors="replace") as fh:
        for l in fh:
            if not l.startswith('{"event": "'): continue
            ev = l[11:l.index('"', 11)]
            if ev in ("button", "menu_guard_off", "recording", "waiting_clock"): continue
            try: d = json.loads(l)
            except ValueError: continue
            if ev == "decision":
                p = d.get("public") or {}; dc = d.get("decision") or {}
                if "observer_side" not in p: continue
                s = p["observer_side"]; r["side"] = s if r["side"] is None else r["side"]
                r["n_dec"] += 1; r["decide_ms"].append(d.get("decide_ms") or 0); r["backlog_pos"] += (d.get("backlog") or 0) > 0
                bodies = [(b["side"] == s, *own(s, b["x"], b["y"]), b["card_id"], b["hp"], b["max_hp"], b.get("kind"), b.get("address")) for b in p.get("raw_bodies", [])]
                proj = [(q["side"] == s, *own(s, q["x"], q["y"]), q["card_id"]) for q in p.get("raw_projectiles", [])]
                dec = (bool(dc.get("play")), dc.get("p_play"), dc.get("name"), dc.get("gate_tau"), bool(dc.get("no_affordable")), bool(dc.get("stalled")), bool(d.get("forced")))
                r["S"].append((d["tick"], p.get("own_elixir_raw"), p.get("opponent_elixir_estimate"), tuple(h["name"] for h in p.get("own_hand", [])), bodies, proj, dec))
            elif ev == "frame":
                r["n_frame"] += 1
                s = d.get("my_side")
                if s is None: continue
                if d.get("opp_elixir_true_EVAL_ONLY") is not None and d["tick"] % 20 < 2:
                    r["est_true"].append((d["tick"], d.get("opp_elixir_est"), d["opp_elixir_true_EVAL_ONLY"]))   # counter-bias diagnostic ONLY
                if r["n_dec"] or (frames and d["tick"] - frames[-1][0] < 6): continue
                bodies = [(e[0] == s, *own(s, e[1], e[2]), e[3], e[4], e[5], e[6], e[7] if len(e) > 7 else None) for e in d["ents"]]
                frames.append((d["tick"], d.get("elixir"), d.get("opp_elixir_est"), None, bodies, [], None)); r["side"] = s if r["side"] is None else r["side"]
            elif ev == "play":
                xy = d.get("xy"); xy = json.loads(xy) if isinstance(xy, str) else xy
                r["plays"].append(dict(tick=d["tick"], name=d.get("name"), xy=xy, el=d.get("elixir"), p=d.get("p_play"), forced=bool(d.get("forced"))))
            elif ev == "confirmed":
                r["conf"].append(dict(tick=d["tick"], name=d.get("name"), err=d.get("err_tiles"), lat=d.get("latency_s"), drop=d.get("elixir_drop")))
            elif ev == "unconfirmed": r["unconf"].append(dict(tick=d["tick"], name=d.get("name"), fails=d.get("fails")))
            elif ev == "ability": r["abil"].append(dict(tick=d["tick"], el=d.get("elixir"), why=(d.get("why") or "")[:40]))
            elif ev == "ability_confirmed": r["abil_conf"] += 1
            elif ev == "cpu_starved": r["starved"] += 1
            elif ev == "reader_closed": r["reader_closed"] += 1
            elif ev == "tap_timing": r["tap"].append(d.get("tap_ms") or 0)
            elif ev == "start":
                if not r["start"]: r["start"] = d
            elif ev == "end": r["end"] = d
            elif ev == "stop": r["stop"] = d
    if not r["S"]: r["S"] = frames
    r["state_src"] = "decision" if r["n_dec"] else ("frame" if frames else "none")
    return r


# ------------------------------------------------------------------ per-match features
def nm(cid): return NAME.get(cid, str(cid))


def s_bodies_half(s):
    """enemy non-tower live bodies on my half (own y <= THREAT_Y) in one state."""
    return [b for b in s[4] if not b[0] and b[3] != -1 and b[4] > 0 and b[2] <= THREAT_Y]


def tower_slot(b):
    mine, X, Y, cid, hp, mx, kind = b[:7]
    if cid != -1: return None
    if kind == 12 or (abs(X - 9) < 0.6 and (Y < 4 or Y > 28)): k = "K"
    else: k = "L" if X < 9 else "R"
    return ("m" if mine else "e") + k


def features(r):
    S = r["S"]; T = [s[0] for s in S]
    st = r["start"] or {}; do = st.get("decision_options") or {}
    ck = (st.get("ckpt") or "").replace("\\", "/").split("/")[-1]
    row = dict(file=r["file"], ts=r["file"][10:25], ckpt=ck, sha8=(st.get("ckpt_sha256") or "")[:8], dry_run=bool(st.get("dry_run")),
               cfg=dict(tau=st.get("tau"), tau_phase=do.get("tau_phase"), xbow_class=do.get("xbow_class"), spell_aim=do.get("spell_aim"),
                        anti_leak=st.get("anti_leak"), own_effects=st.get("own_effects"), opp_counter=st.get("opp_counter"), extrapolate=st.get("extrapolate")),
               state_src=r["state_src"], n_states=len(S), n_dec=r["n_dec"], has_end=bool(r["end"] or r["stop"]),
               stop_why=(r["stop"] or {}).get("why"), wall_s=(r["end"] or {}).get("seconds"))
    plays = r["plays"]; conf = r["conf"]
    # match plays to confirmations (same name, within 200 ticks)
    used = set()
    for p in plays:
        p["conf"] = None
        for i, c in enumerate(conf):
            if i not in used and c["name"] == p["name"] and 0 <= c["tick"] - p["tick"] < 200:
                used.add(i); p["conf"] = c; break
        p["X"], p["Y"] = model_to_own(p["xy"]) if p["xy"] else (None, None)
    CP = [p for p in plays if p["conf"]]
    row.update(n_plays=len(plays), n_conf=len(CP), n_unconf=len(r["unconf"]), unconf_names=dict(collections.Counter(u["name"] for u in r["unconf"])),
               err_tiles=[round(c["err"], 2) for c in conf if c.get("err") is not None], lat_s=[c["lat"] for c in conf if c.get("lat") is not None],
               starved=r["starved"], reader_closed=r["reader_closed"], decide_ms_med=sorted(r["decide_ms"])[len(r["decide_ms"]) // 2] if r["decide_ms"] else None,
               backlog_share=r["backlog_pos"] / r["n_dec"] if r["n_dec"] else None, tap_ms_med=sorted(r["tap"])[len(r["tap"]) // 2] if r["tap"] else None,
               forced=sum(p["forced"] for p in plays), abil=len(r["abil"]), abil_conf=r["abil_conf"],
               abil_el=[round(a["el"], 1) for a in r["abil"] if a.get("el") is not None])
    # play issued before the previous play was confirmed ("decision while pending")
    row["pending_plays"] = sum(1 for a, b in zip(plays, plays[1:]) if a["conf"] and b["tick"] < a["conf"]["tick"])
    if r["est_true"]:
        e = [x[1] - x[2] for x in r["est_true"] if x[1] is not None]
        row["counter_bias"] = dict(n=len(e), mean=sum(e) / len(e) if e else None, mae=sum(map(abs, e)) / len(e) if e else None)
    if len(S) < 20 or r["side"] is None:
        row["valid_state"] = False; return row
    row["valid_state"] = True
    end = T[-1]; row["end_tick"] = end; row["dur_s"] = end / TPS
    # ---- towers
    hp = collections.defaultdict(list); maxhp = {}
    for s in S:
        for b in s[4]:
            sl = tower_slot(b)
            if sl and b[4] > 0: hp[sl].append((s[0], b[4])); maxhp[sl] = b[5]
    dead = {}
    for sl in ("eL", "eR", "eK", "mL", "mR", "mK"):
        v = hp.get(sl)
        if not v: dead[sl] = None; continue
        after = [t for t in T if t > v[-1][0]]
        dead[sl] = after[0] if len(after) >= 3 else None
    def hp_at(sl, t):
        v = hp.get(sl)
        if not v: return None
        if dead[sl] is not None and t >= dead[sl]: return 0
        i = bisect.bisect_right([x[0] for x in v], t)
        return v[0][1] if i == 0 else v[i - 1][1]
    cm = min(3, sum(dead[k] is not None for k in ("eL", "eR")) + 3 * (dead["eK"] is not None))
    co = min(3, sum(dead[k] is not None for k in ("mL", "mR")) + 3 * (dead["mK"] is not None))
    fin_abs = {sl: (0 if dead[sl] is not None else v[-1][1]) for sl, v in hp.items()}
    fin = {sl: fin_abs[sl] / maxhp[sl] for sl in fin_abs}
    # equal crowns: the in-game tiebreaker compares each side's LOWEST remaining tower HP (absolute)
    a = min([fin_abs[k] for k in ("eK", "eL", "eR") if fin_abs.get(k)] or [0]); b_ = min([fin_abs[k] for k in ("mK", "mL", "mR") if fin_abs.get(k)] or [0])
    derived = "WIN" if cm > co else "LOSS" if cm < co else ("WIN" if a < b_ else "LOSS" if a > b_ else "DRAW")
    row.update(crowns_me=cm, crowns_opp=co, derived=derived, dead_s={k: (v / TPS if v is not None else None) for k, v in dead.items()},
               fin_hp={k: round(v, 3) for k, v in fin.items()}, fin_abs=fin_abs, tiebreak_min=dict(me=b_, opp=a), towers_seen=sorted(hp))
    ev = sorted([(dead[k], "me" if k[0] == "e" else "opp") for k in dead if dead[k] is not None])
    row["first_crown"], row["first_crown_s"] = (ev[0][1], ev[0][0] / TPS) if ev else (None, None)
    def taken(t0, t1):   # my tower HP lost in [t0, t1]
        return sum(max(0, (hp_at(k, t0) or 0) - (hp_at(k, t1) or 0)) for k in ("mL", "mR", "mK") if hp.get(k))
    def dealt(t0, t1):
        return sum(max(0, (hp_at(k, t0) or 0) - (hp_at(k, t1) or 0)) for k in ("eL", "eR", "eK") if hp.get(k))
    row["dmg"] = {p: dict(taken=taken(a0, min(b0, end)), dealt=dealt(a0, min(b0, end))) for p, a0, b0 in PH if end > a0}
    # ---- enemy bodies: values, first sightings (addresses), names seen
    seen_addr = {}; opp_cards = set(); ev_val = []; bval = body_valuer(S)
    for s in S:
        v_half = 0.0; v_all = 0.0; back = 0.0; air_half = False
        for b in s[4]:
            mine, X, Y, cid, h, mx, kind, addr = b
            if mine or cid == -1 or h <= 0: continue
            n = nm(cid)
            if not n.isdigit() and not n.startswith("CHAR_"): opp_cards.add(n)
            u = bval(cid, mx); v_all += u
            if Y <= THREAT_Y: v_half += u; air_half |= n in AIR
            if Y >= 27: back += u
            if addr is not None and addr not in seen_addr: seen_addr[addr] = (s[0], n, X, Y)
        for q in s[5]:
            if not q[0] and q[3] != -1:
                n = nm(q[3])
                if not n.isdigit(): opp_cards.add(n)
        ev_val.append((s[0], v_half, v_all, back, air_half))
    row["opp_cards"] = sorted(opp_cards - TOKENS)
    # ---- elixir: leak by phase and by situation; regen slope diagnostic
    thr_on = [x[1] >= THREAT_V for x in ev_val]
    leak = {p: [0.0, 0.0, 0.0] for p, _, _ in PH}         # [seconds observed, seconds at cap, elixir wasted]
    sit = collections.Counter(); sit_t = collections.Counter(); slope = {p: [0.0, 0.0] for p, _, _ in PH}
    last_threat_end = -10 ** 9
    for i in range(len(S) - 1):
        t, el = S[i][0], S[i][1]
        if el is None: continue
        dt = min(T[i + 1] - t, 30); p = ph(t); leak[p][0] += dt / TPS
        if thr_on[i]: last_threat_end = t
        tag = ("threat" if thr_on[i] else "post_defence" if t - last_threat_end <= 160 else
               "enemy_invest_back" if ev_val[i][3] >= 5 and ev_val[i][1] < 2 else "quiet" if ev_val[i][2] < 3 else "other")
        sit_t[tag] += dt / TPS
        if el >= CAP:
            leak[p][1] += dt / TPS; leak[p][2] += dt * REGEN[p]; sit[tag] += dt * REGEN[p]
        el2 = S[i + 1][1]
        if el2 is not None and el < 9.0 and el2 > el and T[i + 1] - t <= 30 and not any(t <= q["tick"] <= T[i + 1] + 30 for q in plays):
            slope[p][0] += el2 - el; slope[p][1] += T[i + 1] - t
    # play rate by own-elixir bucket, quiet (< 3 enemy elixir on my half) vs pressured: [seconds, taps] per bucket int(elixir)
    eh = {"quiet": collections.defaultdict(lambda: [0.0, 0]), "press": collections.defaultdict(lambda: [0.0, 0])}
    for i in range(len(S) - 1):
        if S[i][1] is None: continue
        eh["press" if ev_val[i][1] >= 3 else "quiet"][min(9, int(S[i][1]))][0] += min(T[i + 1] - S[i][0], 30) / TPS
    for p in plays:
        if p["el"] is None: continue
        k = max(0, bisect.bisect_right(T, p["tick"]) - 1)
        eh["press" if ev_val[k][1] >= 3 else "quiet"][min(9, int(p["el"]))][1] += 1
    row["el_hist"] = {k: {b: [round(v[0], 1), v[1]] for b, v in d.items()} for k, d in eh.items()}
    # confirmed plays by card x (quiet|press) x (elixir at tap < 5 | >= 5)
    cq = collections.Counter()
    for p in CP:
        if p["el"] is None: continue
        k = max(0, bisect.bisect_right(T, p["tick"]) - 1)
        cq[f"{p['name']}|{'press' if ev_val[k][1] >= 3 else 'quiet'}|{'lo' if p['el'] < 5 else 'hi'}"] += 1
    row["card_ctx"] = dict(cq)
    row["leak"] = {p: [round(x, 2) for x in v] for p, v in leak.items()}
    row["leak_sit"] = {k: round(v, 2) for k, v in sit.items()}; row["sit_time"] = {k: round(v, 1) for k, v in sit_t.items()}
    row["regen_slope"] = {p: [round(v[0], 2), v[1]] for p, v in slope.items()}
    # longest stretch at the cap (any decision state) and freeze (p_play < its tau, affordable) at >= 9.5
    best = cur = 0; t0 = None; fz = fz0 = 0; fzs = None; fz_list = []
    for s in S:
        if s[1] is not None and s[1] >= CAP:
            t0 = s[0] if t0 is None else t0; best = max(best, s[0] - t0)
        else: t0 = None
        d = s[6]
        if d is not None and s[1] is not None and s[1] >= 9.5 and not d[0] and d[1] is not None and d[1] < (d[3] or .35):
            fzs = s[0] if fzs is None else fzs; fz = max(fz, s[0] - fzs)
        else:
            if fzs is not None and s[0] - fzs >= 100: fz_list.append((fzs, s[0]))
            fzs = None
    row["cap_max_s"] = best / TPS; row["freeze_max_s"] = fz / TPS; row["freeze_ge5"] = [(a0, b0) for a0, b0 in fz_list][:8]
    # ---- threat episodes (defence units)
    ptick = [p["tick"] for p in plays]
    xb_ticks = [p["tick"] for p in CP if p["name"] == "Xbow"]
    eps = []; last_hi = -10 ** 9; on = False
    for i, (t, vh, va, back, air) in enumerate(ev_val):
        if vh >= THREAT_V:
            if not on and t - last_hi >= 80: eps.append(dict(i=i, t=t))
            on = True; last_hi = t
        else: on = False
    for e in eps:
        i, t = e["i"], e["t"]
        j = i; quiet_since = None
        while j + 1 < len(S) and S[j + 1][0] - t < 600:
            j += 1
            if ev_val[j][1] < 3: quiet_since = S[j][0] if quiet_since is None else quiet_since
            else: quiet_since = None
            if quiet_since is not None and S[j][0] - quiet_since >= 60: break
        t_end = S[j][0]
        k = bisect.bisect_left(ptick, t); rsp = (ptick[k] - t) / TPS if k < len(ptick) and ptick[k] - t <= 200 and ptick[k] <= end else None
        names = collections.Counter()
        for jj in range(i, j + 1):
            for b in S[jj][4]:
                if not b[0] and b[3] != -1 and b[4] > 0 and b[2] <= THREAT_Y: names[nm(b[3])] += 1
        spent = sum(COST.get(p["name"], 0) for p in CP if t - 20 <= p["tick"] <= t_end)
        pre = [p for p in CP if t - 200 <= p["tick"] < t]
        pre10 = sum(COST.get(p["name"], 0) for p in pre)
        # offence = X-Bow placed to lock, or a spell aimed on the enemy half (own y > 18); the rest counts as defence/cycle
        pre_off = sum(COST.get(p["name"], 0) for p in pre if (p["name"] == "Xbow" and p["Y"] is not None and any(math.hypot(p["X"] - EN_T[k][0], p["Y"] - EN_T[k][1]) <= REACH for k in EN_T))
                      or (p["name"] in ("Rocket", "Tornado", "Log") and p["Y"] is not None and p["Y"] > 18))
        k0 = bisect.bisect_left(T, t - 200); osp = 0.0
        for q in range(k0, j):
            if S[q][2] is not None and S[q + 1][2] is not None:
                osp += max(0.0, min(S[q][2] + (S[q + 1][0] - S[q][0]) * REGEN[ph(S[q][0])], 10.0) - S[q + 1][2])
        fr = [p for p in plays if t <= p["tick"] <= t + 200]
        cx = [b[1] for b in s_bodies_half(S[i])]
        lane_thr = (sum(cx) / len(cx)) if cx else None
        lk = sum(min(S[q + 1][0] - S[q][0], 30) for q in range(max(0, i - 40), i) if S[q][0] >= t - 300 and S[q][1] is not None and S[q][1] >= CAP) / TPS
        d0 = S[i][6]; s0 = S[i]
        hand = s0[3]
        e.update(t_end=t_end, dur=(t_end - t) / TPS, v=round(max(ev_val[x][1] for x in range(i, j + 1)), 1), v0=round(ev_val[i][1], 1), el=s0[1],
                 opp_el=s0[2], rsp=rsp, cens=(min(t + 200, end) - t) / TPS, spent=spent, pre10=pre10, pre_off=pre_off,
                 pre_cards=[p["name"] for p in pre], opp_spent=round(osp, 1), thr_x=round(lane_thr, 1) if lane_thr is not None else None,
                 first=[(p["name"], round(p["X"], 1) if p["X"] is not None else None, round(p["Y"], 1) if p["Y"] is not None else None, p["tick"] - t) for p in fr[:3]],
                 leak15=lk, air=any(n in AIR for n in names),
                 cards=[n for n, _ in names.most_common(4)], ph=ph(t), hand=list(hand) if hand else None,
                 off_xbow10=any(t - 200 <= x < t for x in xb_ticks),
                 hp_lost=taken(t, min(end, t_end + 60)), tower_fell=any(dead[k] is not None and t <= dead[k] <= t_end + 60 for k in ("mL", "mR", "mK")),
                 p0=(round(d0[1], 3) if d0 and d0[1] is not None else None), tau0=(d0[3] if d0 else None),
                 below3=None)
        if d0 is not None:   # gate below its threshold for >= 3 s with an affordable card before the first play
            run = 0; rs = None; stop_t = t + int(20 * (rsp if rsp is not None else e["cens"]))
            for jj in range(i, len(S)):
                if S[jj][0] > stop_t: break
                dd = S[jj][6]
                if dd and dd[1] is not None and dd[1] <= (dd[3] or .35) and not dd[4] and not dd[0]:
                    rs = S[jj][0] if rs is None else rs; run = max(run, S[jj][0] - rs)
                else: rs = None
            e["below3"] = run >= 60
        del e["i"]
    row["threats"] = eps
    # ---- my X-Bows (offence units)
    my_xbow_bodies = collections.defaultdict(list)    # addr -> [(t, X, Y, hp)]
    for s in S:
        for b in s[4]:
            if b[0] and b[3] != -1 and nm(b[3]) == "Xbow" and b[4] > 0: my_xbow_bodies[b[7]].append((s[0], b[1], b[2], b[4]))
    xbows = []
    for p in CP:
        if p["name"] != "Xbow": continue
        t = p["conf"]["tick"]; X, Y = p["X"], p["Y"]
        alive_en = [k for k in EN_T if hp_at(k, t)]
        lock = any(math.hypot(X - EN_T[k][0], Y - EN_T[k][1]) <= REACH for k in alive_en)
        # the body: an Xbow address first seen within 3 s of confirmation, near the intended cell
        body = None
        for addr, v in my_xbow_bodies.items():
            if abs(v[0][0] - t) <= 60 and math.hypot(v[0][1] - X, v[0][2] - Y) <= 3.0: body = v; break
        life = (body[-1][0] - body[0][0]) / TPS if body else None
        died_at = body[-1][0] if body else t + 600
        killers = collections.Counter()
        if body:
            k0 = bisect.bisect_left(T, died_at - 60); k1 = bisect.bisect_right(T, died_at)
            for s in S[k0:k1]:
                for b in s[4]:
                    if not b[0] and b[3] != -1 and b[4] > 0 and math.hypot(b[1] - body[-1][1], b[2] - body[-1][2]) <= 7: killers[nm(b[3])] += 1
                for q in s[5]:
                    if not q[0]: killers[nm(q[3])] += 1
        k = bisect.bisect_right(T, t) - 1; s0 = S[max(k, 0)]
        thr = ev_val[max(k, 0)][1]
        xbows.append(dict(t=t, ph=ph(t), X=round(X, 2), Y=round(Y, 2), lock=lock, defensive=(not lock) and Y < 16, err=p["conf"]["err"],
                          el_after=round((p["el"] or 0) - 6, 2), opp_el=s0[2], threat_on=thr >= 5, life=life, body_found=body is not None,
                          dealt20=dealt(t, min(end, t + 400)), dealt_life=dealt(t, min(end, died_at)),
                          counters=[n for n in killers if n in XBOW_COUNTERS], expired=life is not None and life >= 28))
    row["xbows"] = xbows
    # ---- spells: Rocket / Log / Tornado outcome (bodies at the impact state)
    def bodies_near(t, X, Y, rad, enemy=True):
        k = bisect.bisect_left(T, t); k = min(k, len(S) - 1)
        return [(nm(b[3]), b[1], b[2], bval(b[3], b[5])) for b in S[k][4] if b[0] != enemy and b[3] != -1 and b[4] > 0 and math.hypot(b[1] - X, b[2] - Y) <= rad]
    spells = []
    for p in CP:
        if p["name"] not in ("Rocket", "Log", "Tornado"): continue
        t = p["conf"]["tick"]; X, Y = p["X"], p["Y"]
        o = dict(name=p["name"], t=t, ph=ph(t), X=round(X, 2), Y=round(Y, 2))
        if p["name"] == "Rocket":
            imp = t + math.hypot(X - 9.0, Y - 3.0) / 0.35
            tw = [k for k in EN_T if hp_at(k, t) and math.hypot(X - EN_T[k][0], Y - EN_T[k][1]) <= 3.0]
            hits = bodies_near(imp, X, Y, 2.5)
            o.update(tower=tw[0] if tw else None, tower_hp_before=hp_at(tw[0], t) if tw else None,
                     tower_dmg=(hp_at(tw[0], t) - hp_at(tw[0], min(end, int(imp) + 40))) if tw and hp_at(tw[0], t) is not None and hp_at(tw[0], min(end, int(imp) + 40)) is not None else None,
                     n_hit=len(hits), v_hit=round(sum(h[3] for h in hits), 1), my_half=Y <= 18)
        elif p["name"] == "Log":
            k = bisect.bisect_left(T, t); hit = set(); air_only = False
            for s in S[k:k + 4]:
                for b in s[4]:
                    if b[0] or b[3] == -1 or b[4] <= 0: continue
                    n = nm(b[3])
                    if abs(b[1] - X) <= 2.4 and Y - 1.0 <= b[2] <= Y + 11.0:
                        (hit.add((b[7], n)) if n not in AIR else None)
                        air_only = air_only or n in AIR
            barrel = any(not q[0] and nm(q[3]) in ("GoblinBarrel", "SkeletonBarrel") for s in S[max(0, k - 3):k + 2] for q in s[5])
            o.update(n_hit=len(hit), air_only=(not hit) and air_only, barrel=barrel, cards=sorted({h[1] for h in hit})[:4])
        else:
            hits = bodies_near(t + 10, X, Y, 5.5)
            o.update(n_hit=len(hits), v_hit=round(sum(h[3] for h in hits), 1), d_king=round(math.hypot(X - 9.0, Y - 3.0), 1))
        spells.append(o)
    row["spells"] = spells
    # lethal Rocket windows: enemy princess alive <= ROCKET_DMG, Rocket in hand, >= 6 elixir, >= 3 s
    # (stretch.py definition: consecutive decision states that qualify; taps inside do not break it; kept if >= 3 s or it holds a Rocket tap)
    lw = []; run = None
    def lethal_lanes(t): return [k for k in ("eL", "eR") if 0 < (hp_at(k, t) or 0) <= ROCKET_DMG]
    rk_taps = [p for p in plays if p["name"] == "Rocket"]
    for s in S + [(10 ** 9, None, None, None, [], [], None)]:
        ok = s[3] is not None and "Rocket" in s[3] and (s[1] or 0) >= 6 and bool(lethal_lanes(s[0]))
        if ok:
            run = [s[0], s[0], lethal_lanes(s[0])] if run is None else [run[0], s[0], run[2]]
        elif run is not None:
            taps = [p for p in rk_taps if run[0] <= p["tick"] <= run[1] + 13]
            on = [p for p in taps if p["Y"] is not None and p["Y"] > 20 and any(math.hypot(p["X"] - EN_T[k][0], p["Y"] - EN_T[k][1]) <= 3.0 for k in run[2])]
            if run[1] - run[0] >= 60 or taps:
                lw.append(dict(t0=run[0], t1=run[1], ph=ph(run[0]), lanes=run[2], rocketed=bool(on), rocket_elsewhere=bool(taps) and not on,
                               hp=[hp_at(k, run[0]) for k in run[2]], tower_died=[dead[k] is not None for k in run[2]]))
            run = None
    row["lethal"] = lw
    last = [s for s in S if s[0] >= end - 400 and s[3] is not None]     # final 20 s: could a Rocket have been played?
    row["end_rocket"] = dict(in_hand=mean(["Rocket" in s[3] for s in last]), affordable=mean(["Rocket" in s[3] and (s[1] or 0) >= 6 for s in last]),
                             max_el=max([s[1] or 0 for s in last] or [None]) if last else None, taps=sum(1 for p in rk_taps if p["tick"] >= end - 400)) if last else None
    # hand composition: share of decision time Rocket sits in hand while >= 6 elixir and nothing threatening
    hs = [(s[0], s[3], s[1]) for s in S if s[3] is not None]
    row["rocket_in_hand_share"] = sum("Rocket" in h for _, h, _ in hs) / len(hs) if hs else None
    # per-phase plays / elixir at play / card mix
    pp = {p: collections.Counter() for p, _, _ in PH}; elp = {p: [] for p, _, _ in PH}
    for p in CP:
        pp[ph(p["tick"])][p["name"]] += 1
        if p["el"] is not None: elp[ph(p["tick"])].append(p["el"])
    row["cards_phase"] = {k: dict(v) for k, v in pp.items()}
    row["el_at_play"] = {k: (round(sum(v) / len(v), 2) if v else None) for k, v in elp.items()}
    row["spent_total"] = sum(COST.get(p["name"], 0) for p in CP)
    # opponent elixir (public counter) at my X-Bow commits / overall; enemy spend proxy = counter drops
    drops = 0.0
    for a1, b1 in zip(S, S[1:]):
        if a1[2] is not None and b1[2] is not None:
            reg = (b1[0] - a1[0]) * REGEN[ph(a1[0])]
            drops += max(0.0, min(a1[2] + reg, 10.0) - b1[2])
    row["opp_spent_counter"] = round(drops, 1)
    return row


# ------------------------------------------------------------------ results (resolved at report time)
def ladder_results():
    """overnight.out: '{"played" ... "log": X}' then '[ladder] result: W|L|D' and optionally '[ladder] trophies: +N'."""
    res = {}; last = None
    if not os.path.exists(OVN): return res
    for l in open(OVN, encoding="utf8", errors="replace"):
        if l.startswith('{"played"'):
            m = re.search(r'"log": "(.*?)"', l)
            last = m.group(1).replace("\\\\", "/").replace("\\", "/").split("/")[-1] if m else None
            continue
        m = re.search(r"\[ladder\] result: (WIN|LOSS|DRAW)", l)
        if m and last and last not in res: res[last] = [m.group(1), None]; continue
        m = re.search(r"\[ladder\] trophies: ([+-]\d+)\s*$", l.strip())
        if m and last in res and res[last][1] is None: res[last][1] = int(m.group(1))
    return res


def nav_outcomes():
    out = []
    for f in sorted(glob.glob(NAVGLOB)):
        for l in open(f, encoding="utf8", errors="replace"):
            if '"outcome"' in l:
                try: e = json.loads(l)
                except ValueError: continue
                if e.get("event") == "outcome": out.append((e["t"], e.get("won")))
    out.sort(); return out


def resolve(rows):
    lad = ladder_results(); nav = nav_outcomes(); nt = [o[0] for o in nav]
    for r in rows:
        r["ladder"], r["trophy_delta"] = (lad.get(r["file"]) or [None, None])
        r["nav"] = None
        try:
            st = datetime.datetime.strptime(r["file"][10:25], "%Y%m%d_%H%M%S").timestamp()
            sec = r.get("wall_s") or (r.get("end_tick") or 3600) / TPS
            k = bisect.bisect_left(nt, st + sec - 20)
            if k < len(nt) and nt[k] < st + sec + 300 and nav[k][1] is not None: r["nav"] = "WIN" if nav[k][1] else "LOSS"
        except ValueError: pass
        r["result"] = r["ladder"] or r["nav"] or r.get("derived")
        r["result_src"] = "ladder" if r["ladder"] else "nav" if r["nav"] else "derived" if r.get("derived") else None


# ------------------------------------------------------------------ stats helpers
Z = 1.96
def wilson(k, n):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + Z * Z / n; c = p + Z * Z / (2 * n); h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def newcombe(k1, n1, k2, n2):
    if not n1 or not n2: return (float("nan"),) * 3
    p1, p2 = k1 / n1, k2 / n2; l1, u1 = wilson(k1, n1); l2, u2 = wilson(k2, n2)
    return (p1 - p2, p1 - p2 - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), p1 - p2 + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def boot_diff(a, b, B=2000, seed=1):
    """mean(a) - mean(b) with a percentile bootstrap 95% CI."""
    a = [x for x in a if x is not None]; b = [x for x in b if x is not None]
    if len(a) < 3 or len(b) < 3: return (float("nan"),) * 3
    rng = random.Random(seed); d = []
    for _ in range(B):
        sa = [a[rng.randrange(len(a))] for _ in a]; sb = [b[rng.randrange(len(b))] for _ in b]
        d.append(sum(sa) / len(sa) - sum(sb) / len(sb))
    d.sort()
    return (sum(a) / len(a) - sum(b) / len(b), d[int(.025 * B)], d[int(.975 * B)])


def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def med(v):
    v = sorted(x for x in v if x is not None)
    return v[len(v) // 2] if v else None


def f2(x, d=2): return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"
def pc(x, d=0): return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.{d}f}%"


# ------------------------------------------------------------------ main
def family(r):
    c = r.get("ckpt") or "?"
    if "towerref_w2" in c: return "towerref_w2 (current live)"
    if "barrel2k_cellref" in c: return "stack2k_cellref"
    if "r1e31" in c: return "R1e (r1e31_u0155)"
    return c.replace(".pt", "")


def run(limit=None, report_only=False, rebuild=False):
    names, costs, uv = _catalog(); NAME.update(names); NCOST.update(costs); UV.update(uv)
    done = set(l.strip() for l in open(LEDGER)) if os.path.exists(LEDGER) else set()
    done.discard("")
    if rebuild:   # schema change: forget every row and reparse all logs
        for p in (LEDGER, ROWS):
            if os.path.exists(p): os.remove(p)
        done = set()
    if not report_only:
        now = time.time(); todo = []
        for f in sorted(glob.glob(LOGDIR + "live_play_2026*.jsonl")):
            b = os.path.basename(f)
            if b in done or now - os.path.getmtime(f) < MIN_AGE_S: continue
            todo.append(f)
        if limit: todo = todo[:limit]
        t0 = time.time(); skipped = 0
        for i, f in enumerate(todo):
            r = parse(f)
            if not (r["end"] or r["stop"]) and now - os.path.getmtime(f) < 86400: skipped += 1; continue   # maybe still running
            try: row = features(r)
            except Exception as e:   # one bad log must not stop the review; record why
                row = dict(file=r["file"], ts=r["file"][10:25], error=f"{type(e).__name__}: {e}", valid_state=False)
            with open(ROWS, "a") as fh: fh.write(json.dumps(row, default=str) + "\n")
            with open(LEDGER, "a") as fh: fh.write(r["file"] + "\n")
            if i % 50 == 0: print(f"[{i}/{len(todo)}] {r['file']} {time.time() - t0:.0f}s", flush=True)
        print(f"parsed {len(todo) - skipped} new logs in {time.time() - t0:.0f}s; skipped (no end, < 1 day old) {skipped}")
    rows = [json.loads(l) for l in open(ROWS)] if os.path.exists(ROWS) else []
    resolve(rows)
    import report as R
    R.write(rows, REPORT)
    print("report ->", REPORT)


def selftest():
    assert own(1, 9000, 29000) == (9.0, 3.0) and own(0, 9000, 3000) == (9.0, 3.0)
    assert model_to_own([0.5, 1.0]) == (9.0, 0.0)
    lo, hi = wilson(50, 100); assert abs(lo - .404) < .002 and abs(hi - .596) < .002
    d, lo, hi = newcombe(60, 100, 40, 100); assert abs(d - .2) < 1e-9 and .06 < lo < .08
    assert tower_slot((True, 9.0, 3.0, -1, 100, 100, 12, "a")) == "mK" and tower_slot((False, 14.5, 25.5, -1, 1, 1, 13, "b")) == "eR"
    d, lo, hi = boot_diff([1, 2, 3, 4], [0, 0, 1, 1]); assert lo < d < hi and abs(d - 2.0) < 1e-9
    NAME[26000007] = "Witch"; UV.setdefault("Witch", 5.0)    # body fix: a Witch skeleton (max_hp 119 of 1220) is not a 5-elixir Witch
    bv = body_valuer([(0, 5, 5, (), [(False, 9, 20, 26000007, 1220, 1220, 15, "a"), (False, 9, 20, 26000007, 119, 119, 15, "b")])])
    assert abs(bv(26000007, 1220) - UV["Witch"]) < 1e-9 and bv(26000007, 119) < .1 * UV["Witch"]
    import report as R   # within-match MH: match a differs by 1, match b by 0, equal weights -> 0.5
    u = [dict(_file="a", f=1, y=1), dict(_file="a", f=0, y=0), dict(_file="b", f=1, y=1), dict(_file="b", f=0, y=1)]
    d, lo, hi, n = R.mh(u, lambda x: x["f"], lambda x: x["y"], B=50); assert abs(d - .5) < 1e-9 and n == 2
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int); ap.add_argument("--report-only", action="store_true"); ap.add_argument("--selftest", action="store_true"); ap.add_argument("--rebuild", action="store_true", help="drop the ledger + rows and reparse every log (schema change)")
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    if a.selftest: selftest()
    else: run(a.limit, a.report_only, a.rebuild)
