"""Per-checkpoint LIVE evaluation report (read-only on the live logs).

  icebow/.venv/Scripts/python.exe live_eval.py --ckpt-sha 76fdfaac --label R1e          # one checkpoint
  icebow/.venv/Scripts/python.exe live_eval.py --since 2026-10-07 --ckpt-sha 1a2b3c4d   # new checkpoint, only its newer logs
  icebow/.venv/Scripts/python.exe live_eval.py                                          # every checkpoint found, grouped by sha
  icebow/.venv/Scripts/python.exe live_eval.py --compare R1e NEW                        # side by side, no log parsing

Writes results_<label>.json (+ report_<label>.txt) next to this file. Per-match features are cached in cache/ (keyed by
log name+size), so reruns only parse new logs. In-progress logs (no 'end' event) are skipped. Reuses ../live_review/{load,core}.py.
Group key = ckpt_sha256 from the log's 'start' event; logs from before the sha was logged are assigned the sha of the file at
their logged ckpt path ("sha_src": "path"). Opponent HIDDEN state is never used: only enemy bodies/projectiles on the board.
"""
import os, sys
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"
try:  # below-normal priority (Windows); the laptop is shared
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import re, json, glob, math, bisect, pickle, hashlib, argparse, collections, statistics, datetime

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
LR = HERE + "../live_review"
LOGDIR = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
CACHE = HERE + "cache/"
TPS = 20.0
PHASES = (("1x", 0, 2400), ("2x", 2400, 3600), ("OT", 3600, 10 ** 9))   # ticks; 1x 0-120 s, 2x 120-180 s, OT >=180 s
EARLY_S = 172.0     # a decisive match that ends before the 180 s timer can only end by a king-tower kill (3 crowns)
OT_S = 186.0        # last-state time; timer-end matches log 181-185 s, so >=186 s means the match went to overtime
MIN_N = 8           # min matches for a per-card / per-class flag
Z = 1.96

# ---------------------------------------------------------------- opponent deck classification (public cards only)
TOKENS = {"Skeletons", "Bats", "SkeletonWarriors", "SpearGoblins"}   # spawned by Witch/Graveyard/Night Witch/huts -> not evidence of the card
WINCON = [  # (class, cards) -- primary class = FIRST row with any card seen (priority order = how deck-defining the card is)
    ("X-Bow/Mortar", {"Xbow", "Mortar"}), ("Lava Hound", {"LavaHound"}), ("Golem", {"Golem", "ElixirGolem"}),
    ("Giant (incl. Goblin/Electro)", {"Giant", "GoblinGiant", "ElectroGiant"}), ("Royal Giant", {"RoyalGiant"}),
    ("Balloon", {"Balloon"}), ("Graveyard", {"Graveyard"}), ("Hog (incl. Royal Hogs)", {"HogRider", "RoyalHogs"}),
]
BRIDGE = {"Assassin", "BossBandit", "DarkPrince", "Prince", "Ghost", "Wallbreakers", "Berserker"}
BAIT = {"GoblinBarrel", "SkeletonArmy", "Princess", "GoblinGang", "Rascals", "DartBarrell", "SkeletonBalloon", "Goblins"}
SPAWNERS = {"Witch", "DarkWitch", "WitchMother", "FirespiritHut", "GoblinHut", "BarbarianHut", "Tombstone", "GoblinDrill", "BarbarianLauncher"}
TANKS = {"Golem", "ElixirGolem", "ElectroGiant", "Giant", "GoblinGiant", "RoyalGiant", "LavaHound", "Pekka", "MegaKnight", "GiantSkeleton"}
AIR = {"BabyDragon", "InfernoDragon", "ElectroDragon", "Balloon", "Minions", "MinionHorde", "MegaMinion", "SkeletonDragons", "Phoenix", "LavaHound"}
RULES = ("primary class = first match in: " + "; ".join(f"{c}={sorted(s)}" for c, s in WINCON) +
         f"; Ram/Bridge spam = BattleRam|RamRider or >=2 of {sorted(BRIDGE)}; Miner = Miner|MightyMiner; Mega Knight; P.E.K.K.A; "
         f"Spawners = any of {sorted(SPAWNERS)}; Bait = >=3 of {sorted(BAIT)}; else 'Other/no clear wincon'. Ignored spawn tokens: {sorted(TOKENS)}. "
         f"Traits (non-exclusive): spawner-heavy = >=2 spawner cards, heavy tank = any of {sorted(TANKS)}, air = >=2 of {sorted(AIR)}, "
         f"spell-bait = >=3 bait cards, bridge spam = class rule above, has building = Cannon/Tesla/BombTower/InfernoTower.")

def classify(cards):
    c = set(cards)
    for name, s in WINCON:
        if c & s: return name
    if c & {"BattleRam", "RamRider"} or len(c & BRIDGE) >= 2: return "Ram/Bridge spam"
    if c & {"Miner", "MightyMiner"}: return "Miner"
    if "MegaKnight" in c: return "Mega Knight"
    if "Pekka" in c: return "P.E.K.K.A"
    if c & SPAWNERS: return "Spawners (Witch/huts)"
    if len(c & BAIT) >= 3: return "Bait"
    return "Other/no clear wincon"

def traits(cards):
    c = set(cards)
    t = {"spawner-heavy": len(c & SPAWNERS) >= 2, "heavy tank": bool(c & TANKS), "air (>=2)": len(c & AIR) >= 2,
         "spell-bait (>=3)": len(c & BAIT) >= 3, "bridge spam": bool(c & {"BattleRam", "RamRider"}) or len(c & BRIDGE) >= 2,
         "has building": bool(c & {"Cannon", "Tesla", "BombTower", "InfernoTower"}), "has Witch/Night Witch": bool(c & {"Witch", "DarkWitch"})}
    return t

# ---------------------------------------------------------------- stats helpers (stdlib only)
def wilson(k, n, z=Z):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)

def newcombe(k1, n1, k2, n2):
    """95% CI for p1-p2 (Newcombe hybrid score) -> (diff, lo, hi)."""
    if n1 == 0 or n2 == 0: return (float("nan"),) * 3
    p1, p2 = k1 / n1, k2 / n2; l1, u1 = wilson(k1, n1); l2, u2 = wilson(k2, n2)
    return (p1 - p2, (p1 - p2) - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), (p1 - p2) + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))

def welch(a, b):
    """mean(b)-mean(a) with a normal-approx 95% CI (z=1.96; small n is optimistic)."""
    a = [x for x in a if x is not None]; b = [x for x in b if x is not None]
    if len(a) < 2 or len(b) < 2: return (float("nan"),) * 3
    se = math.sqrt(statistics.variance(a) / len(a) + statistics.variance(b) / len(b)); d = statistics.mean(b) - statistics.mean(a)
    return (d, d - Z * se, d + Z * se)

def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None

def mci(v):
    v = [x for x in v if x is not None]
    if len(v) < 2: return (mean(v), None)
    return (statistics.mean(v), Z * statistics.stdev(v) / math.sqrt(len(v)))

def pct(x, d=1): return "  n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.{d}f}%"
def pp(x): return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:+.1f}pp"
def ci_s(lo, hi): return f"[{100 * lo:.0f},{100 * hi:.0f}]" if not math.isnan(lo) else "[n/a]"

# ---------------------------------------------------------------- feature extraction (one log -> one compact record)
def _imports():
    sys.path.insert(0, LR)
    import load as L, core as C, analyze as A   # noqa
    return L, C, A

_sha_cache = {}
def sha_of(path):
    if path not in _sha_cache:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for ch in iter(lambda: fh.read(1 << 20), b""): h.update(ch)
            _sha_cache[path] = h.hexdigest()
        except OSError:
            _sha_cache[path] = ""
    return _sha_cache[path]

def peek_start(f):
    """(start dict | None, has_end) without parsing the heavy decision lines."""
    st, end = None, False
    with open(f, encoding="utf8", errors="replace") as fh:
        for l in fh:
            if l.startswith('{"event": "start"'): st = json.loads(l)
            elif l.startswith('{"event": "end"') or l.startswith('{"event": "stop"'): end = True
    return st, end

def damage(m, dead):
    end = m["end_tick"]; out = {"dealt": {p: 0.0 for p, _, _ in PHASES}, "taken": {p: 0.0 for p, _, _ in PHASES}}
    tot = {"dealt": 0.0, "taken": 0.0}; seen = []
    for slot in ("eL", "eR", "eK", "mL", "mR", "mK"):
        v = m["tower_hp"].get(slot)
        if not v: continue
        seen.append(slot); mx = v[0][2]; ticks = [x[0] for x in v]; cm = []; cur = mx
        for _, h, _ in v: cur = min(cur, h); cm.append(cur)
        def hp(t, slot=slot, mx=mx, ticks=ticks, cm=cm):
            if dead[slot] is not None and dead[slot] <= t: return 0.0
            i = bisect.bisect_right(ticks, t)
            return float(mx if i == 0 else cm[i - 1])
        key = "dealt" if slot[0] == "e" else "taken"; tot[key] += mx
        for p, a, b in PHASES:
            if end > a: out[key][p] += hp(a) - hp(min(b, end))
    return out, tot, seen

def extract(f, results, L, C, A):
    d = L.load(f)
    if d["end"] is None and d["stop"] is None: return None          # in progress / aborted before the end event
    m = C.build(d, results)
    if m is None: return None
    st = d["start"] or {}
    ck = (st.get("ckpt") or "").replace("\\", "/")
    sha, src = (st.get("ckpt_sha256") or ""), "log"
    if not sha: sha, src = sha_of(ck), "path"
    do = st.get("decision_options") or {}
    r = {"file": m["file"], "ts": m["file"][10:25], "sha8": sha[:8] or "unknown", "sha_src": src, "ckpt": ck.split("/")[-1],
         "cfg": f"tau={st.get('tau')} card={do.get('card_choice')}/{do.get('card_ratio')}/{do.get('card_T')} spell={do.get('spell_aim')} opp_counter={st.get('opp_counter')} anti_leak={st.get('anti_leak')}",
         "ladder": m["overnight_result"], "derived": m["derived_result"], "state_src": m["state_src"], "n_plays": m["n_plays"], "n_conf": m["n_conf"],
         "dur_s": m["dur_s"], "end_tick": m["end_tick"], "crown_fix": None}
    res = m["result"]
    if m["state_src"] in ("decision", "frame"):
        dead = m["dead"]
        if res in ("WIN", "LOSS") and m["dur_s"] < EARLY_S:      # king kill = unobserved final blow
            k = "eK" if res == "WIN" else "mK"
            if dead[k] is None: dead[k] = m["end_tick"]; r["crown_fix"] = "king_inferred"
        cm = min(3, sum(dead[k] is not None for k in ("eL", "eR")) + (3 if dead["eK"] is not None else 0))
        co = min(3, sum(dead[k] is not None for k in ("mL", "mR")) + (3 if dead["mK"] is not None else 0))
        r["crowns_me"], r["crowns_opp"] = cm, co
        ev = [(dead[k], "me" if k[0] == "e" else "opp") for k in dead if dead[k] is not None]
        r["first_crown"], r["first_crown_s"] = (min(ev)[1], min(ev)[0] / TPS) if ev else (None, None)
        r["dead_s"] = {k: (v / TPS if v is not None else None) for k, v in dead.items()}
        dm, tot, seen = damage(m, dead)
        r["dmg"], r["hp_total"], r["towers_seen"] = dm, tot, seen
        S = d["states"]; T = [s["tick"] for s in S]
        el = {p: [0.0, 0.0, 0.0] for p, _, _ in PHASES}   # sum(el*dt), sum(dt), leak dt
        for i in range(len(S) - 1):
            dt = min(T[i + 1] - T[i], 30) / TPS; p = next(p for p, a, b in PHASES if a <= T[i] < b)
            el[p][0] += S[i]["el"] * dt; el[p][1] += dt; el[p][2] += dt if S[i]["el"] >= 9.5 else 0.0
        r["el_state"] = el
        obs = m["obs"]; seen_c = set()
        for s in S:
            for b in s["bodies"]:
                if len(b) >= 4 and b[0] != obs and b[3] != -1: seen_c.add(b[3])
            for q in s["proj"]:
                if q[0] != obs and q[3] != -1: seen_c.add(q[3])
        r["opp_cards"] = sorted({C.nm(c) for c in seen_c} - TOKENS - {x for x in {C.nm(c) for c in seen_c} if x.isdigit() or x.startswith("CHAR_")})
    else:
        r.update({"crowns_me": None, "crowns_opp": None, "first_crown": None, "first_crown_s": None, "dmg": None, "hp_total": None, "opp_cards": None, "el_state": None})
    pe = {p: [0, 0.0] for p, _, _ in PHASES}
    for p_ in m["plays"]:
        if not p_["conf"]: continue
        p = next(p for p, a, b in PHASES if a <= p_["tick"] < b); pe[p][0] += 1; pe[p][1] += p_["elixir"]
    r["plays_phase"] = pe
    r["result"] = res; r["result_src"] = "ladder" if m["overnight_result"] else ("derived" if res else None)
    return r

def load_records(args, results):
    """-> (records, info). Parses only logs of the wanted checkpoint whose cache entry is missing/stale."""
    os.makedirs(CACHE, exist_ok=True)
    L = C = A = None
    recs, info = [], {"logs_in_window": 0, "in_progress_skipped": 0, "parsed_now": 0}
    for f in sorted(glob.glob(LOGDIR + "live_play_2026*.jsonl")):
        base = os.path.basename(f); ts = base[10:25]
        if args.since and ts < args.since: continue
        if args.until and ts > args.until: continue
        cp = CACHE + base + ".pkl"; size = os.path.getsize(f); ent = None; dirty = False
        if os.path.exists(cp) and not args.rebuild:
            try: ent = pickle.load(open(cp, "rb"))
            except Exception: ent = None
            if ent and ent["size"] != size: ent = None
            if ent and ent["parsed"] and ent["rec"] is not None and ent["rec"]["ladder"] is None and results.get(base): ent["parsed"] = False; dirty = True
        if ent is None:
            st, has_end = peek_start(f); st = st or {}
            sha = (st.get("ckpt_sha256") or sha_of((st.get("ckpt") or "").replace("\\", "/")))[:8] or "unknown"
            ent = {"size": size, "sha8": sha, "has_end": has_end, "parsed": False, "rec": None, "tau": st.get("tau")}; dirty = True
        if "tau" not in ent:                         # cache entries from before --tau existed
            ent["tau"] = (peek_start(f)[0] or {}).get("tau"); dirty = True
        if args.ckpt_sha and not ent["sha8"].startswith(args.ckpt_sha[:8]):
            if dirty: pickle.dump(ent, open(cp, "wb"))
            continue
        if args.tau is not None and (ent["tau"] is None or abs(float(ent["tau"]) - args.tau) > 1e-9):
            if dirty: pickle.dump(ent, open(cp, "wb"))
            continue
        info["logs_in_window"] += 1
        if not ent["has_end"]:
            info["in_progress_skipped"] += 1
            if dirty: pickle.dump(ent, open(cp, "wb"))
            continue
        if not ent["parsed"]:
            if L is None: L, C, A = _imports()
            try: ent["rec"] = extract(f, results, L, C, A)
            except Exception as e:
                print(f"[warn] {base}: {type(e).__name__}: {e}", file=sys.stderr); ent["rec"] = None
            ent["parsed"] = True; dirty = True; info["parsed_now"] += 1
        if dirty: pickle.dump(ent, open(cp, "wb"))
        if ent["rec"] is not None: recs.append(ent["rec"])
    return recs, info

# ---------------------------------------------------------------- aggregation
def valid(r): return r["result"] in ("WIN", "LOSS", "DRAW") and r["n_plays"] >= 5
def has_state(r): return r["crowns_me"] is not None

def wr_block(Q):
    n = len(Q); w = sum(r["result"] == "WIN" for r in Q); l = sum(r["result"] == "LOSS" for r in Q); dr = n - w - l
    lo, hi = wilson(w, n)
    return {"n": n, "W": w, "L": l, "D": dr, "wr": w / n if n else None, "ci": [lo, hi]}

def phase_of_sec(s): return "1x" if s < 120 else ("2x" if s < 180 else "OT")

def agg(Q):
    S = [r for r in Q if has_state(r)]
    o = {"wr": wr_block(Q), "n_state": len(S)}
    o["crowns_me_mean"] = mci([r["crowns_me"] for r in S]); o["crowns_opp_mean"] = mci([r["crowns_opp"] for r in S])
    o["crowns_me_dist"] = [sum(r["crowns_me"] == k for r in S) for k in range(4)]
    o["crowns_opp_dist"] = [sum(r["crowns_opp"] == k for r in S) for k in range(4)]
    o["first_crown"] = {k: sum(r["first_crown"] == k for r in S) for k in ("me", "opp", None)}
    o["wr_given_first"] = {k: wr_block([r for r in S if r["first_crown"] == k]) for k in ("me", "opp", None)}
    L_ = [r for r in S if r["result"] == "LOSS"]; W_ = [r for r in S if r["result"] == "WIN"]
    o["three_crown_losses"] = [sum(r["crowns_opp"] >= 3 for r in L_), len(L_)]
    o["three_crown_wins"] = [sum(r["crowns_me"] >= 3 for r in W_), len(W_)]
    o["king_inferred"] = sum(r["crown_fix"] == "king_inferred" for r in S)
    o["dur_mean"] = mean([r["dur_s"] for r in Q]); o["dur_median"] = statistics.median([r["dur_s"] for r in Q]) if Q else None
    o["ot_share"] = (sum(r["dur_s"] >= OT_S for r in Q), len(Q))
    o["ot_wr"] = wr_block([r for r in Q if r["dur_s"] >= OT_S])
    # tower damage: ratio of sums (% of the side's total tower HP over matches that reached the phase) + per-match mean abs HP
    D = [r for r in S if r["dmg"] and len(r["towers_seen"]) >= 5]
    o["n_dmg"] = len(D); dmg = {}
    for key, tk in (("dealt", "dealt"), ("taken", "taken")):
        dd = {}
        for p, a, b in (("ALL", 0, 0),) + PHASES:
            if p == "ALL": rows = D; val = lambda r: sum(r["dmg"][key].values())
            else: rows = [r for r in D if r["end_tick"] > a]; val = lambda r, p=p: r["dmg"][key][p]
            num = sum(val(r) for r in rows); den = sum(r["hp_total"][key] for r in rows)
            minutes = sum((min(r["end_tick"], b) - a) / TPS / 60 for r in rows) if p != "ALL" else sum(r["end_tick"] / TPS / 60 for r in rows)
            per = [val(r) / r["hp_total"][key] for r in rows if r["hp_total"][key]]
            dd[p] = {"n": len(rows), "pct_of_total": num / den if den else None, "mean_pct": mci(per), "mean_hp": mean([val(r) for r in rows]), "pct_per_min": (num / den) / minutes * len(rows) if den and minutes else None}
        dmg[key] = dd
    o["damage"] = dmg
    # elixir economy
    el = {}
    for p, a, b in PHASES:
        rs = [r for r in S if r["el_state"] and r["el_state"][p][1] > 0]
        sdt = sum(r["el_state"][p][1] for r in rs)
        pl = [r for r in Q if r["plays_phase"][p][0] or True]
        n_pl = sum(r["plays_phase"][p][0] for r in Q); e_pl = sum(r["plays_phase"][p][1] for r in Q)
        exp = sum(max(0, (min(r["end_tick"], b) - a)) / TPS / 60 for r in Q)
        el[p] = {"state_mean_elixir": sum(r["el_state"][p][0] for r in rs) / sdt if sdt else None, "pct_time_ge_9.5": sum(r["el_state"][p][2] for r in rs) / sdt if sdt else None,
                 "elixir_at_play": e_pl / n_pl if n_pl else None, "plays": n_pl, "plays_per_min": n_pl / exp if exp else None}
    o["elixir"] = el
    return o

def class_tables(Q):
    C_ = [r for r in Q if r["opp_cards"] is not None]
    o = {"n": len(C_)}; overall = wr_block(C_)["wr"]
    for r in C_: r["_cls"] = classify(r["opp_cards"])
    classes = {}
    for name in sorted({r["_cls"] for r in C_}):
        sub = [r for r in C_ if r["_cls"] == name]; rest = [r for r in C_ if r["_cls"] != name]; b = wr_block(sub)
        dlt = newcombe(b["W"], b["n"], sum(r["result"] == "WIN" for r in rest), len(rest))
        flag = "small n" if b["n"] < MIN_N else ("ABOVE" if b["ci"][0] > overall else "BELOW" if b["ci"][1] < overall else "-")
        classes[name] = {**b, "vs_rest": list(dlt), "flag": flag}
    o["classes"] = classes; tr = {}
    for t in traits([]):
        sub = [r for r in C_ if traits(r["opp_cards"])[t]]; rest = [r for r in C_ if not traits(r["opp_cards"])[t]]; b = wr_block(sub)
        dlt = newcombe(b["W"], b["n"], sum(r["result"] == "WIN" for r in rest), len(rest))
        tr[t] = {**b, "vs_rest": list(dlt), "flag": "small n" if b["n"] < MIN_N else ("ABOVE" if b["ci"][0] > overall else "BELOW" if b["ci"][1] < overall else "-")}
    o["traits"] = tr; cards = {}
    names = sorted({c for r in C_ for c in r["opp_cards"]})
    for c in names:
        pres = [r for r in C_ if c in r["opp_cards"]]; ab = [r for r in C_ if c not in r["opp_cards"]]
        if len(pres) < MIN_N or len(ab) < MIN_N: continue
        wp = sum(r["result"] == "WIN" for r in pres); wa = sum(r["result"] == "WIN" for r in ab)
        dlt = newcombe(wp, len(pres), wa, len(ab))
        cards[c] = {"n_present": len(pres), "wr_present": wp / len(pres), "wr_absent": wa / len(ab), "n_absent": len(ab), "delta": dlt[0], "ci": [dlt[1], dlt[2]],
                    "sig": "BELOW" if dlt[2] < 0 else "ABOVE" if dlt[1] > 0 else "-"}
    o["cards"] = cards; o["overall_wr"] = overall
    return o

def how_lost(Q):
    """Loss anatomy for the matches of one class (Q already filtered)."""
    L_ = [r for r in Q if r["result"] == "LOSS" and has_state(r)]; n = len(L_)
    if not n: return {"n_losses": 0}
    fc = collections.Counter()
    for r in L_:
        fc["bot never scored a crown" if r["crowns_me"] == 0 else "bot scored >=1 crown"] += 1
    first = collections.Counter(phase_of_sec(r["first_crown_s"]) if r["first_crown"] == "opp" else ("bot_first" if r["first_crown"] == "me" else "none") for r in L_)
    early = sum(1 for r in L_ if r["first_crown"] == "opp" and r["first_crown_s"] < 120)
    out = {"n_matches": len(Q), "wr": wr_block(Q)["wr"], "n_losses": n, "first_crown_lost_phase": dict(first), "opp_first_crown_before_120s": early, "bot_scored_any": fc["bot scored >=1 crown"],
           "three_crowned": sum(r["crowns_opp"] >= 3 for r in L_), "ot_losses": sum(r["dur_s"] >= OT_S for r in L_), "dur_mean": mean([r["dur_s"] for r in L_]),
           "crowns_me_mean": mean([r["crowns_me"] for r in L_]), "crowns_opp_mean": mean([r["crowns_opp"] for r in L_])}
    D = [r for r in L_ if r["dmg"] and len(r["towers_seen"]) >= 5]; tk = {}
    for p, a, b in PHASES:
        rows = [r for r in D if r["end_tick"] > a]
        tk[p] = {"n": len(rows), "taken_pct_of_total": (sum(r["dmg"]["taken"][p] for r in rows) / sum(r["hp_total"]["taken"] for r in rows)) if rows else None,
                 "dealt_pct_of_total": (sum(r["dmg"]["dealt"][p] for r in rows) / sum(r["hp_total"]["dealt"] for r in rows)) if rows else None}
    out["phase_damage_in_losses"] = tk
    return out

def trajectory(Q, block=25):
    Q = sorted(Q, key=lambda r: r["ts"]); out = []
    for i in range(0, len(Q), block):
        b = Q[i:i + block]; w = wr_block(b)
        out.append({"from": b[0]["ts"], "to": b[-1]["ts"], "n": w["n"], "W": w["W"], "L": w["L"], "wr": w["wr"], "net_cum": sum(1 if r["result"] == "WIN" else -1 if r["result"] == "LOSS" else 0 for r in Q[:i + len(b)])})
    return out

def build_results(label, recs, info, args):
    Q = [r for r in recs if valid(r)]
    excl = [r["file"] for r in recs if not valid(r)]
    R = {"label": label, "generated": datetime.datetime.now().isoformat(timespec="seconds"),
         "params": {"since": args.since, "until": args.until, "ckpt_sha": args.ckpt_sha}, "info": info, "excluded_logs": excl,
         "sha8": sorted({r["sha8"] for r in recs}), "sha_src": dict(collections.Counter(r["sha_src"] for r in recs)), "cfg": dict(collections.Counter(r["cfg"] for r in recs)),
         "ts_range": [min(r["ts"] for r in Q), max(r["ts"] for r in Q)] if Q else None, "result_src": dict(collections.Counter(r["result_src"] for r in Q)),
         "derived_vs_ladder": [sum(1 for r in Q if r["ladder"] and r["derived"] and r["ladder"] == r["derived"].rstrip("*")), sum(1 for r in Q if r["ladder"] and r["derived"])],
         "overall": agg(Q), "class_rules": RULES, "trophies": "NOT LOGGED (see report footer)", "trajectory": trajectory(Q)}
    ct = class_tables(Q); R["matchups"] = ct
    worst = sorted((k for k, v in ct["classes"].items() if v["n"] >= MIN_N), key=lambda k: ct["classes"][k]["wr"])[:5]
    hl = {"class: " + k: how_lost([r for r in Q if r.get("_cls") == k]) for k in worst}
    for t, v in ct["traits"].items():
        if v["flag"] == "BELOW": hl["trait: " + t] = how_lost([r for r in Q if r["opp_cards"] is not None and traits(r["opp_cards"])[t]])
    for c, v in sorted(ct["cards"].items(), key=lambda kv: kv[1]["delta"])[:4]:
        if v["sig"] == "BELOW": hl["card: " + c] = how_lost([r for r in Q if r["opp_cards"] is not None and c in r["opp_cards"]])
    hl["ALL MATCHES"] = how_lost(Q)
    R["how_lost"] = hl
    for r in Q: r.pop("_cls", None)
    R["matches"] = Q
    return R

# ---------------------------------------------------------------- printing
def render(R):
    L = []; P = L.append; o = R["overall"]; w = o["wr"]
    P(f"=== LIVE EVAL  {R['label']}  (sha {','.join(R['sha8'])}; sha_src {R['sha_src']}) ===")
    P(f"logs {R['ts_range'][0]} .. {R['ts_range'][1]}; in window {R['info']['logs_in_window']}, in-progress skipped {R['info']['in_progress_skipped']}, "
      f"excluded (<5 plays / no result) {len(R['excluded_logs'])}; result source {R['result_src']} (crown-derived result agrees with the ladder result in {R['derived_vs_ladder'][0]}/{R['derived_vs_ladder'][1]} matches that have both); with board state {o['n_state']}/{w['n']}")
    P(f"config variants: {R['cfg']}")
    P("")
    P(f"OVERALL  matches {w['n']}  W/L/D {w['W']}/{w['L']}/{w['D']}  win rate {pct(w['wr'])} 95% CI {ci_s(*w['ci'])}  (draws count as non-wins)")
    cm, co = o["crowns_me_mean"], o["crowns_opp_mean"]
    P(f"crowns taken/match {cm[0]:.2f} +-{cm[1]:.2f}   lost/match {co[0]:.2f} +-{co[1]:.2f}   (n={o['n_state']})")
    P("crown distribution (share of matches with 0/1/2/3 crowns):  taken " + " / ".join(pct(x / o['n_state'], 0) for x in o["crowns_me_dist"]) + "   lost " + " / ".join(pct(x / o['n_state'], 0) for x in o["crowns_opp_dist"]))
    fc = o["first_crown"]; ns = o["n_state"]
    P(f"first crown: bot took it {pct(fc['me'] / ns)} ({fc['me']}), opponent took it {pct(fc['opp'] / ns)} ({fc['opp']}), nobody {pct(fc[None] / ns)} ({fc[None]})")
    for k, nm_ in (("me", "bot first"), ("opp", "opp first"), (None, "no crown")):
        b = o["wr_given_first"][k]
        P(f"   win rate when {nm_:9s}: {pct(b['wr'])} {ci_s(*b['ci'])}  n={b['n']}")
    a, b_ = o["three_crown_losses"], o["three_crown_wins"]
    P(f"three-crown losses {a[0]}/{a[1]} losses ({pct(a[0] / a[1] if a[1] else None)}) | three-crown wins {b_[0]}/{b_[1]} | king-kill inferred from early end: {o['king_inferred']}")
    P(f"match length mean {o['dur_mean']:.0f}s median {o['dur_median']:.0f}s | reached OT (>= {OT_S:.0f}s) {o['ot_share'][0]}/{o['ot_share'][1]} = {pct(o['ot_share'][0] / o['ot_share'][1])}; win rate in OT matches {pct(o['ot_wr']['wr'])} {ci_s(*o['ot_wr']['ci'])} n={o['ot_wr']['n']}")
    P("")
    P(f"TOWER DAMAGE (% of that side's total tower HP, ratio of sums; matches with >=5 towers sighted: n={o['n_dmg']}); per-min = % of total per match-minute in that phase")
    P(f"  {'phase':6s}{'n':>5s} | {'dealt %':>8s} {'/min':>7s} {'abs HP':>7s} | {'taken %':>8s} {'/min':>7s} {'abs HP':>7s} | net(dealt-taken)")
    for p in ("ALL", "1x", "2x", "OT"):
        d_, t_ = o["damage"]["dealt"][p], o["damage"]["taken"][p]
        net = (d_["pct_of_total"] or 0) - (t_["pct_of_total"] or 0)
        P(f"  {p:6s}{d_['n']:5d} | {pct(d_['pct_of_total']):>8s} {pct(d_['pct_per_min']):>7s} {d_['mean_hp'] or 0:7.0f} | {pct(t_['pct_of_total']):>8s} {pct(t_['pct_per_min']):>7s} {t_['mean_hp'] or 0:7.0f} | {pp(net)}")
    P("  (whole-match mean per-match dealt %  " + f"{pct(o['damage']['dealt']['ALL']['mean_pct'][0])} +-{100 * (o['damage']['dealt']['ALL']['mean_pct'][1] or 0):.1f}   taken {pct(o['damage']['taken']['ALL']['mean_pct'][0])} +-{100 * (o['damage']['taken']['ALL']['mean_pct'][1] or 0):.1f})")
    P("")
    P("ELIXIR ECONOMY (own elixir from the decision states; 'at play' = elixir when a confirmed card was played)")
    P(f"  {'phase':6s}{'mean elixir':>12s}{'% time >=9.5':>14s}{'at play':>9s}{'plays':>7s}{'plays/min':>10s}")
    for p in ("1x", "2x", "OT"):
        e = o["elixir"][p]
        P(f"  {p:6s}{(e['state_mean_elixir'] or 0):12.2f}{pct(e['pct_time_ge_9.5']):>14s}{(e['elixir_at_play'] or 0):9.2f}{e['plays']:7d}{(e['plays_per_min'] or 0):10.2f}")
    P("")
    P(f"TRAJECTORY (chronological blocks of 25 matches; trophies are NOT logged, so this is win rate and cumulative net wins W-L)")
    for t in R["trajectory"]:
        P(f"  {t['from']}..{t['to']}  n={t['n']:3d}  W-L {t['W']}-{t['L']}  wr {pct(t['wr'])}  net wins so far {t['net_cum']:+d}")
    mt = R["matchups"]; ov = mt["overall_wr"]
    P("")
    P(f"MATCHUPS by opponent primary class (public cards seen; n={mt['n']}; overall {pct(ov)}). flag = class 95% CI excludes the overall rate; 'vs rest' = Newcombe diff CI. {MIN_N}+ matches needed to flag.")
    P(f"  {'class':32s}{'n':>4s}{'W-L-D':>9s}{'win rate':>9s}{'95% CI':>11s}{'vs rest':>20s}  flag")
    for k, v in sorted(mt["classes"].items(), key=lambda kv: kv[1]["wr"]):
        P(f"  {k:32s}{v['n']:4d}{str(v['W']) + '-' + str(v['L']) + '-' + str(v['D']):>9s}{pct(v['wr']):>9s}{ci_s(*v['ci']):>11s}{pp(v['vs_rest'][0]):>9s} {ci_s(*v['vs_rest'][1:]) if not math.isnan(v['vs_rest'][1]) else '':>10s}  {v['flag']}")
    P("")
    P("TRAITS (non-exclusive; same flagging)")
    for k, v in sorted(mt["traits"].items(), key=lambda kv: kv[1]["wr"] if kv[1]["wr"] is not None else 9):
        P(f"  {k:32s}{v['n']:4d}{str(v['W']) + '-' + str(v['L']) + '-' + str(v['D']):>9s}{pct(v['wr']):>9s}{ci_s(*v['ci']):>11s}{pp(v['vs_rest'][0]):>9s} {ci_s(*v['vs_rest'][1:]) if not math.isnan(v['vs_rest'][1]) else '':>10s}  {v['flag']}")
    P("")
    cs = sorted(mt["cards"].items(), key=lambda kv: kv[1]["delta"])
    P(f"PER-CARD PRESENCE EFFECT (win rate when opponent shows the card minus when not; cards with >={MIN_N} present and >={MIN_N} absent; {len(cs)} cards tested, so ~{len(cs) * 0.05:.0f} CI-excluding-0 hits are expected by chance)")
    P(f"  {'card':18s}{'present n':>10s}{'wr present':>11s}{'wr absent':>10s}{'delta':>9s}{'95% CI':>14s}  sig")
    def row(k, v): return f"  {k:18s}{v['n_present']:10d}{pct(v['wr_present']):>11s}{pct(v['wr_absent']):>10s}{pp(v['delta']):>9s}{'[' + format(100 * v['ci'][0], '+.0f') + ',' + format(100 * v['ci'][1], '+.0f') + ']':>14s}  {v['sig']}"
    P("  -- worst 12 (bot wins less when present)")
    for k, v in cs[:12]: P(row(k, v))
    P("  -- best 8 (bot wins more when present)")
    for k, v in cs[::-1][:8]: P(row(k, v))
    P("  Caveat: cards are only counted once SEEN, so presence correlates with match length (short 3-crown losses reveal fewer cards); treat as association, not cause.")
    P("")
    P("HOW THE WEAK SPOTS ARE LOST (5 worst classes with n>=8, every BELOW-flagged trait, up to 4 BELOW-flagged cards; losses only; phases 1x <120s, 2x 120-180s, OT >=180s)")
    for k, h in R["how_lost"].items():
        if not h.get("n_losses"): continue
        P(f"  [{k}]  matches {h['n_matches']}  win rate {pct(h['wr'])}  losses (with state) {h['n_losses']}")
        P(f"     first crown lost: " + ", ".join(f"{a}={b}" for a, b in sorted(h["first_crown_lost_phase"].items())) + f"  | opp first crown before 120s: {h['opp_first_crown_before_120s']}/{h['n_losses']}"
          f"  | bot scored >=1 crown in {h['bot_scored_any']}/{h['n_losses']}  | three-crowned {h['three_crowned']}  | OT losses {h['ot_losses']}  | mean length {h['dur_mean']:.0f}s | crowns for/against {h['crowns_me_mean']:.2f}/{h['crowns_opp_mean']:.2f}")
        P("     tower damage in these losses (% of total): " + "; ".join(f"{p}: taken {pct(v['taken_pct_of_total'])} dealt {pct(v['dealt_pct_of_total'])} (n={v['n']})" for p, v in h["phase_damage_in_losses"].items()))
    P("")
    P("TROPHIES: not recorded anywhere in the logs (live_play_*.jsonl start/end events, overnight.out, ladder_state.json carry only W/L/D tallies). Capture points:")
    P("  (a) scratchpad/gauntlet/L68/live_reader/ladder_nav.py ~line 286-292: on the 'results' screen the classifier already runs once per match; OCR the trophy delta (+/-) under the WINNER banner")
    P("      there, add it to the outcome event W(event='outcome', ...) and to the '[ladder] result:' print; (b) the main-menu screen (ladder_nav 'main') shows the total trophy counter top-left:")
    P("      OCR it each time the planner passes through 'main' and write it to the nav jsonl. Not built here (read-only task).")
    P(f"CLASS RULES: {R['class_rules']}")
    return "\n".join(L)

def compare(a, b):
    A_, B_ = a["matches"], b["matches"]; L = []; P = L.append
    sa, sb = agg(A_), agg(B_)
    P(f"=== COMPARE  A={a['label']} (n={len(A_)}, sha {','.join(a['sha8'])}, {a['ts_range'][0]}..{a['ts_range'][1]})   B={b['label']} (n={len(B_)}, sha {','.join(b['sha8'])}, {b['ts_range'][0]}..{b['ts_range'][1]}) ===")
    P("delta = B - A; CI = 95% (Newcombe for rates, normal-approx Welch for means; small n makes both optimistic). 'sig' = CI excludes 0.")
    P(f"  {'metric':44s}{'A':>9s}{'B':>9s}{'B-A':>9s}{'95% CI':>16s} sig")
    def rate(name, ka, na, kb, nb):
        d, lo, hi = newcombe(kb, nb, ka, na)
        P(f"  {name:44s}{pct(ka / na if na else None):>9s}{pct(kb / nb if nb else None):>9s}{pp(d):>9s}{'[' + format(100 * lo, '+.1f') + ',' + format(100 * hi, '+.1f') + ']':>16s} {'*' if (lo > 0 or hi < 0) else ''}")
    def mval(name, fa, fb, scale=1.0, unit=""):
        va = [fa(r) for r in A_]; vb = [fb(r) for r in B_]; d, lo, hi = welch(va, vb)
        ma, mb = mean(va), mean(vb)
        P(f"  {name:44s}{(ma or 0) * scale:9.2f}{(mb or 0) * scale:9.2f}{d * scale:+9.2f}{'[' + format(lo * scale, '+.2f') + ',' + format(hi * scale, '+.2f') + ']':>16s} {'*' if (lo > 0 or hi < 0) else ''}{unit}")
    rate("win rate", sa["wr"]["W"], sa["wr"]["n"], sb["wr"]["W"], sb["wr"]["n"])
    SA = [r for r in A_ if has_state(r)]; SB = [r for r in B_ if has_state(r)]
    mval("crowns taken / match", lambda r: r["crowns_me"], lambda r: r["crowns_me"])
    mval("crowns lost / match", lambda r: r["crowns_opp"], lambda r: r["crowns_opp"])
    for nm_, key in (("first crown taken by bot", "me"), ("first crown taken by opp", "opp")):
        rate(nm_ + " (share of matches w/ state)", sum(r["first_crown"] == key for r in SA), len(SA), sum(r["first_crown"] == key for r in SB), len(SB))
    la = [r for r in SA if r["result"] == "LOSS"]; lb = [r for r in SB if r["result"] == "LOSS"]
    rate("three-crown losses (share of losses)", sum(r["crowns_opp"] >= 3 for r in la), len(la), sum(r["crowns_opp"] >= 3 for r in lb), len(lb))
    rate("reached OT (share of matches)", sum(r["dur_s"] >= OT_S for r in A_), len(A_), sum(r["dur_s"] >= OT_S for r in B_), len(B_))
    mval("match length (s)", lambda r: r["dur_s"], lambda r: r["dur_s"])
    START = {"1x": 0, "2x": 2400, "OT": 3600}
    def dm(key, p):
        def f(r):
            if not r["dmg"] or len(r["towers_seen"]) < 5: return None
            if p == "ALL": return 100 * sum(r["dmg"][key].values()) / r["hp_total"][key]
            return 100 * r["dmg"][key][p] / r["hp_total"][key] if r["end_tick"] > START[p] else None
        return f
    for p in ("ALL", "1x", "2x", "OT"):
        mval(f"tower dmg dealt, % of enemy total [{p}]", dm("dealt", p), dm("dealt", p))
        mval(f"tower dmg taken, % of own total   [{p}]", dm("taken", p), dm("taken", p))
    for p in ("1x", "2x", "OT"):
        mval(f"mean own elixir (state-time) [{p}]", lambda r, p=p: (r["el_state"][p][0] / r["el_state"][p][1]) if r["el_state"] and r["el_state"][p][1] else None,
             lambda r, p=p: (r["el_state"][p][0] / r["el_state"][p][1]) if r["el_state"] and r["el_state"][p][1] else None)
    P("")
    P(f"MATCHUP CLASSES  (win rate A vs B per opponent class; diff CI Newcombe; classes with n<{MIN_N} in either arm are shown but not flagged)")
    ca, cb = class_tables(A_)["classes"], class_tables(B_)["classes"]
    P(f"  {'class':32s}{'A n':>5s}{'A wr':>8s}{'B n':>5s}{'B wr':>8s}{'B-A':>9s}{'95% CI':>16s} sig")
    for k in sorted(set(ca) | set(cb), key=lambda k: -(ca.get(k, {"n": 0})["n"] + cb.get(k, {"n": 0})["n"])):
        x, y = ca.get(k), cb.get(k)
        if not x or not y:
            P(f"  {k:32s}{x['n'] if x else 0:5d}{pct(x['wr']) if x else '  --':>8s}{y['n'] if y else 0:5d}{pct(y['wr']) if y else '  --':>8s}   (only one arm)"); continue
        d, lo, hi = newcombe(y["W"], y["n"], x["W"], x["n"])
        sig = "*" if (min(x["n"], y["n"]) >= MIN_N and (lo > 0 or hi < 0)) else ""
        P(f"  {k:32s}{x['n']:5d}{pct(x['wr']):>8s}{y['n']:5d}{pct(y['wr']):>8s}{pp(d):>9s}{'[' + format(100 * lo, '+.0f') + ',' + format(100 * hi, '+.0f') + ']':>16s} {sig}")
    return "\n".join(L)

# ---------------------------------------------------------------- main
def norm_ts(s):
    if not s: return None
    d = re.sub(r"\D", "", s)
    if len(d) < 8: raise SystemExit(f"bad timestamp {s!r}")
    return d[:8] + "_" + (d[8:] + "000000")[:6]

def read_results():
    sys.path.insert(0, LR); import core as C
    return C.read_results()

def selftest():
    lo, hi = wilson(50, 100); assert abs(lo - 0.404) < 0.002 and abs(hi - 0.596) < 0.002
    d, lo, hi = newcombe(60, 100, 40, 100); assert abs(d - 0.2) < 1e-9 and 0.06 < lo < 0.08 and 0.32 < hi < 0.34
    assert classify({"Xbow", "HogRider"}) == "X-Bow/Mortar" and classify({"Witch", "Valkyrie"}) == "Spawners (Witch/huts)"
    assert classify({"GoblinBarrel", "Princess", "SkeletonArmy"}) == "Bait" and classify({"Knight"}) == "Other/no clear wincon"
    m = {"end_tick": 4000, "tower_hp": {"eL": [(100, 3000, 3000), (2000, 1500, 3000)], "mL": [(100, 3000, 3000), (3000, 600, 3000)]}}
    dead = {"eL": 3800, "eR": None, "eK": None, "mL": None, "mR": None, "mK": None}
    dm, tot, seen = damage(m, dead)
    assert dm["dealt"] == {"1x": 1500.0, "2x": 0.0, "OT": 1500.0} and dm["taken"] == {"1x": 0.0, "2x": 2400.0, "OT": 0.0} and tot == {"dealt": 3000.0, "taken": 3000.0}
    print("selftest ok")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="20261004_205129", help="log start >= this local time (YYYYMMDD_HHMMSS | 'YYYY-MM-DD HH:MM'); default = first R1e live log")
    ap.add_argument("--until", help="log start <= this local time")
    ap.add_argument("--ckpt-sha", help="sha256 prefix of the checkpoint to evaluate (default: group every checkpoint found)")
    ap.add_argument("--tau", type=float, help="only matches whose start event logged this play threshold (owner A/B, --tau-alternate)")
    ap.add_argument("--label", help="output label (default: first 8 chars of the sha)")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"), help="print two saved labels side by side (reads results_<label>.json)")
    ap.add_argument("--rebuild", action="store_true", help="ignore the per-log cache")
    ap.add_argument("--selftest", action="store_true", help="run the built-in sanity asserts and exit")
    ap.add_argument("--quiet", action="store_true", help="write files, print only the headline")
    args = ap.parse_args()
    if args.selftest: return selftest()
    args.since, args.until = norm_ts(args.since), norm_ts(args.until)
    if args.compare:
        a, b = (json.load(open(HERE + f"results_{x}.json")) for x in args.compare)
        txt = compare(a, b); open(HERE + f"compare_{args.compare[0]}_vs_{args.compare[1]}.txt", "w").write(txt + "\n"); print(txt); return
    results = read_results()
    recs, info = load_records(args, results)
    if args.ckpt_sha: recs = [r for r in recs if r["sha8"].startswith(args.ckpt_sha[:8]) or r["sha8"] == args.ckpt_sha]
    groups = collections.defaultdict(list)
    for r in recs: groups[r["sha8"]].append(r)
    if not groups: raise SystemExit("no matching finished logs")
    if args.label and len(groups) > 1: raise SystemExit(f"--label given but {len(groups)} checkpoints matched ({sorted(groups)}); add --ckpt-sha")
    for sha, rs in sorted(groups.items()):
        label = args.label or sha
        R = build_results(label, rs, info, args)
        json.dump(R, open(HERE + f"results_{label}.json", "w"), indent=1, default=str)
        txt = render(R); open(HERE + f"report_{label}.txt", "w").write(txt + "\n")
        print(txt if not args.quiet else txt.split("\n")[3])
        print(f"\n[saved] {HERE}results_{label}.json  {HERE}report_{label}.txt\n")

if __name__ == "__main__":
    main()
