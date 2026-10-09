"""L74 DRILL SUITE, Phase 1 -- selectors, harvest, decision-only baseline (live model vs pros).  Measurement only.

  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/drills/drills.py run        -> out/moments_{live,pros}.jsonl.gz, out/baseline.json
  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/drills/drills.py selftest

Inputs (same per-match format, see build_live.py / build_pros.py):
  data/live.pkl.gz  every live log with decision states (build_live.py, a copy of L74/mistakes/build.py)
  data/pros.pkl.gz  2,241 pro icebow sides from corpus_v6/icebow_public_v1 (build_pros.py; all enemy bodies, own bodies, hp)
A DRILL = a SELECTOR (decision-time, public information only: my elixir/hand/bodies, enemy bodies on the board, tower hp) that
fires at real game moments, split into DO-moments (doing X is the doctrine's call) and HOLD-moments (refraining from Y is), plus
the action families X and Y.  The score here is only "did the agent do X / refrain from Y"; whether the doctrine is RIGHT is
Phase 2's job (forked rollouts).  Pass rates: DO% = share of do-moments where the agent did X in the window; HOLD% = share of
hold-moments where it did NOT do Y.  Higher is better for both.
A moment = the first state where the selector fires (onset), then a refractory per (drill, kind, key) so one situation counts once.
All selectors except D9 also require NO OWN PLAY PENDING (tapped and not yet landed), so the agent has a free choice.
Plays: live = TAP tick (the model's decision); pros = deploy - 26 ticks (as mistakes.py).  Own frame tiles: my king (9,3),
princesses (3.5,6.5)/(14.5,6.5), my half y <= 16, enemy princesses (3.5,25.5)/(14.5,25.5); forward = INCREASING y in this frame.
"""
import os, sys, gzip, pickle, json, math, bisect, collections, re
try:
    import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
MAIN = "C:/Users/benpe/ClashBot/"
OUT = HERE + "out/"
sys.path.insert(0, MAIN); sys.path.insert(0, HERE)
LOGDIR = MAIN + "scratchpad/gauntlet/L68/live_reader/"
CARDS_JSON = MAIN + "research/ext/Royale/RoyaleSim/data/derived/cards.json"

COST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
MT = {"mL": (3.5, 6.5), "mR": (14.5, 6.5), "mK": (9.0, 3.0)}
ET = {"eL": (3.5, 25.5), "eR": (14.5, 25.5), "eK": (9.0, 29.0)}
TPS = 20


def _norm(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())


# ---- card facts from the engine's card table (not assumed): which of OUR cards reach air, which enemy units are heavy
def card_facts():
    d = json.load(open(CARDS_JSON))
    air, reach = set(), set()
    for c in d["cards"]:
        if c["name"] not in COST: continue
        aoe = (c.get("spell") or {}).get("area_effect_object") or {}
        if c.get("attacks_air") or (c.get("projectile") or {}).get("aoe_to_air"): air.add(c["name"])      # damages air
        if c["name"] in air or aoe.get("hits_air"): reach.add(c["name"])                                  # reaches air at all
    heavy = {_norm(c["name"]) for c in d["cards"] if (c.get("mass") or 0) >= 15}
    heavy |= {_norm(u["name"]) for u in d["units"].values() if (u.get("mass") or 0) >= 15}
    hp = {}
    for u in d["units"].values():
        if u.get("hitpoints"): hp.setdefault(_norm(u["name"]), u["hitpoints"])
    for c in d["cards"]:
        if c.get("hitpoints"): hp[_norm(c["name"])] = c["hitpoints"]
    rocket = next(c["damage"] for c in d["cards"] if c["name"] == "Rocket")
    return air, reach, heavy, hp, rocket


# From cards.json (checked 10-09): AIRCAP (damages air) = {IceWizard, Rocket, Tesla}; Tornado reaches air (spell area_effect
# hits_air, 60 dps buff) but deals no damage of its own -> neither a D4 DO nor a ground-only HOLD failure; GROUND_ONLY =
# {Knight, Log, Skeletons, Xbow}.
AIRCAP, AIRREACH, HEAVY, HPT, ROCKET_DMG = card_facts()


def unit_hp(cls):
    """table hitpoints of a class (same table level as ROCKET_DMG, so the ratio is roughly level-free). ponytail: unknown
    classes (~5% of bodies: archers, guards, royal_recruit ...) get 600, a mid-HP troop; add aliases if D6 leans on them."""
    k = _norm(cls)
    for c in (k, k.replace("evo", "").replace("hero", ""), k.rstrip("s")):
        if c in HPT: return HPT[c]
    return 600
GROUND_ONLY = set(COST) - AIRREACH
NOT_AIR_THREAT = {"skeleton_barrel", "skeleton_barrel_evo"}   # owner's log-air exemption: the barrel drops ground skeletons
BUILDINGS = {"tombstone", "goblin_hut", "furnace", "barbarian_hut", "elixir_collector", "cannon", "tesla", "inferno_tower", "bomb_tower",
             "x_bow", "mortar", "goblin_cage", "goblin_drill", "tombstone_hero", "goblin_cage_evo", "furnace_evo", "mortar_evo", "cannon_evo",
             "tesla_evo", "elixir_golem"}   # (elixir_golem is not a building; harmless here: it is heavy anyway)
BUILDINGS.discard("elixir_golem")


def d2(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
def phase(t): return "1x" if t < 2400 else ("2x" if t < 3600 else "OT")
def play_lane(X): return "L" if X < 7.5 else ("R" if X > 10.5 else "C")


# ------------------------------------------------------------------ loading
def load(src):
    if src == "sim": return load_sim()
    with gzip.open(HERE + f"data/{src}.pkl.gz") as fh: ms = pickle.load(fh)
    if src == "live":
        ms = [m for m in ms if m.get("src_state") == "decision"]                      # frame-only logs have no hand
        ms = [m for m in ms if not m["P"] or sum(p[2] not in COST for p in m["P"]) / len(m["P"]) <= .1]   # other decks (mistakes.py)
        ms = [m for m in ms if sum(COST.get(p[2], 0) for p in m["P"] if p[0] < 2400) <= 80]                 # boosted-elixir modes
        for m in ms: m["src"] = "live"
    return ms


CANON = {"x_bow": "Xbow", "skeletons": "Skeletons", "the_log": "Log", "knight": "Knight", "tesla": "Tesla", "tornado": "Tornado",
         "ice_wizard": "IceWizard", "rocket": "Rocket"}


def canon(n):
    n = str(n or "")
    for suf in ("_evo", "_hero"):
        if n.endswith(suf): n = n[:-len(suf)]
    return CANON.get(n, CANON.get(n.lower(), n))


def load_sim(dump_dir=OUT + "sim_dump/dump/"):
    """sim_dump.py lines -> the live/pros per-match format. Board frame (x, y in [0, 1], my side at y = 1) -> own tiles
    (18 x, 32 (1 - y)). Enemy values / air flags as build_live.py. A unit's first-seen tick = tick - age_s x 20 when the engine
    gives an age, else the first dump tick where its class count rose (ponytail: no unit ids in BoardState)."""
    sys.path.insert(0, HERE)
    import build_live as BL
    if not BL.VAL: BL.load_values()
    from pipeline import vocab
    def v_of(n): return BL.VAL.get(n, BL.VAL.get(vocab.base_key(n), 1.0))
    rows = collections.defaultdict(list)
    for f in sorted(os.listdir(dump_dir)):
        if f.endswith(".jsonl"):
            for l in open(dump_dir + f):
                try: d = json.loads(l)
                except ValueError: continue
                rows[(d["tag"], d["side"])].append(d)
    out = []
    for (tag, side), R in rows.items():
        R.sort(key=lambda d: d["tick"]); S, P, prev, first = [], [], collections.Counter(), {}
        for d in R:
            t = d["tick"]; eb, own = [], []
            cnt = collections.Counter(u[0] for u in d["units"] if u[1] == 1)
            for c in cnt:
                if cnt[c] > prev[c]: first[c] = t
            prev = cnt
            for n, sd, x, y, hpf, age in d["units"]:
                X, Y = round(x * 18, 2), round((1 - y) * 32, 2)
                if n is None: continue
                if sd == 0: own.append((n, X, Y, hpf, 1)); continue
                tf = t - int(age * 20) if age is not None else first.get(n, t)
                eb.append((n, X, Y, v_of(n), None, tf, hpf, n in BL.AIR))
            tw = {k: (None if h is None else h * 1000) for k, h in zip(("mK", "mL", "mR", "eK", "eL", "eR"), d["towers"])}
            S.append((t, d["el"], tuple(canon(h) for h in d["hand"] if h), eb, tw, None, own, []))
            if d["play"] and d["card"] and d["xy"]:
                P.append((t, t + 26, canon(d["card"]), round(d["xy"][0] * 18, 2), round((1 - d["xy"][1]) * 32, 2), d["el"], None))
        out.append(dict(file=tag, src="sim", fam="sim", side=side, end=R[-1]["tick"], S=S, P=P))
    return out


def live_options():
    """file -> decision_options dict of its start event (cheap: the start line is near the top)."""
    out = {}
    for f in os.listdir(LOGDIR):
        if not f.startswith("live_play_2026"): continue
        with open(LOGDIR + f, encoding="utf8", errors="replace") as fh:
            for k, l in enumerate(fh):
                if l.startswith('{"event": "start"'):
                    try: out[f] = json.loads(l).get("decision_options") or {}
                    except ValueError: pass
                    break
                if k > 200: break
    return out


# ------------------------------------------------------------------ per-match view
class Match:
    def __init__(s, m):
        s.m = m; s.S = m["S"]; s.T = [x[0] for x in s.S]
        s.P = sorted(m["P"], key=lambda p: p[0])
        s.taps = [p[0] for p in s.P]
        s.opx = m.get("opx") or []

    def i(s, t): return max(0, bisect.bisect_right(s.T, t) - 1)

    def pending(s, t):
        k = bisect.bisect_right(s.taps, t)
        for p in s.P[max(0, k - 3):k]:
            land = p[1] if p[1] is not None else p[0] + 40
            if p[0] <= t < land: return True
        return False

    def plays(s, t0, t1):
        a, b = bisect.bisect_left(s.taps, t0), bisect.bisect_right(s.taps, t1)
        return s.P[a:b]

    def last_play_before(s, t):
        k = bisect.bisect_left(s.taps, t)
        return s.P[k - 1] if k else None

    def hp(s, i, k): return s.S[i][4].get(k)


def afford(st, cards=None):
    hand, el = st[2], st[1]
    if not hand or el is None: return []
    return [c for c in hand if c in COST and COST[c] <= el + 1e-6 and (cards is None or c in cards)]


def enemies(st, ymax=99.0, ground=None):
    out = []
    for b in st[3]:
        if b[2] > ymax: continue
        air = b[7] and b[0] not in NOT_AIR_THREAT
        if ground is True and air: continue
        if ground is False and not air: continue
        out.append(b)
    return out


def val(bs):
    """elixir value of enemy bodies; bodies of one class first seen on the same tick worth >= 2 each are ONE card (Ram Rider = ram +
    rider, both valued 5 by build_live) -- ponytail: two same-tick copies of a real >= 2-elixir card would also collapse (rare)."""
    seen, tot = set(), 0.0
    for b in bs:
        if b[3] >= 2.0 and b[5] is not None:
            if (b[0], b[5]) in seen: continue
            seen.add((b[0], b[5]))
        tot += b[3]
    return tot


def lost_hp(M, i, k, dt=20):
    """my tower k lost hp within the last dt ticks (public tower hp)."""
    j = M.i(M.T[i] - dt)
    a, b = M.hp(j, k), M.hp(i, k)
    return a is not None and b is not None and b < a and b > 0


# ------------------------------------------------------------------ the drills
# Each selector yields (kind, key, info) at a state i; the harvest loop applies onset + refractory, then the drill's judge
# returns (passed, action) from the agent's own plays after the moment.
REFRACT = 100        # 5 s between moments of the same (drill, kind, key)


def D1(M, i, st):
    """Defend under fire (M4 of the mistake catalogue, decision-time version). A tower of mine lost hp within the last 1 s, an
    enemy body is within 8 tiles of it, a 3+ elixir card other than X-Bow/Rocket is affordable, nothing pending.
    DO-moment: enemy value within 8 tiles >= 2.0 elixir.  HOLD-moment: <= 1.0 elixir and every body there <= 0.7 (trivial: the tower
    kills it alone).  DO = a play landing within 9 tiles of that tower within 2 s (M4's failure is >= 2 s idle).
    HOLD = no play landing within 9 tiles of that tower within 2 s."""
    if not afford(st, {"Knight", "Tornado", "IceWizard", "Tesla"}): return
    for k, xy in MT.items():
        if not lost_hp(M, i, k): continue
        near = [b for b in enemies(st) if d2((b[1], b[2]), xy) <= 8.0]
        if not near: continue
        v = val(near)
        if v >= 2.0: yield "do", k, dict(v=round(v, 2), tower=k)
        elif v <= 1.0 and max(b[3] for b in near) <= 0.7: yield "hold", k, dict(v=round(v, 2), tower=k)


def J1(M, t, kind, info):
    xy = MT[info["tower"]]
    ps = [p for p in M.plays(t, t + 40) if d2((p[3], p[4]), xy) <= 9.0]
    act = ps[0][2] if ps else "WAIT"
    return (bool(ps) if kind == "do" else not ps), act


def lane_bodies(st, lane):
    return [b for b in st[3] if (b[1] < 9.0) == (lane == "L")]


def D2(M, i, st):
    """Defend the threatened lane (M3). A push forms: enemy value >= 5 elixir in one lane (any y), its closest body still at y > 12
    (not yet at my tower), the other lane <= 2 elixir, my elixir >= 3, nothing pending; one moment per lane per 15 s (one push).
    One moment, both scores:
    DO = a play landing in the push lane or centre on my half (y <= 16) by crossing + 2 s, OR >= 5 elixir held at the crossing
    (crossing = the push's closest body reaches y <= 16; window capped at 10 s).  HOLD = < 4 elixir tapped OFF-side (other lane,
    or y > 18) between onset and crossing + 1 s (M3's flag is >= 4)."""
    if st[1] is None or st[1] < 3: return
    for lane, oth in (("L", "R"), ("R", "L")):
        lb = lane_bodies(st, lane)
        if val(lb) >= 5.0 and min(b[2] for b in lb) > 12.0 and val(lane_bodies(st, oth)) <= 2.0:
            yield "dohold", lane, dict(v=round(val(lb), 2), lane=lane)


def J2(M, t, kind, info):
    lane = info["lane"]; i0 = M.i(t); x = None
    for j in range(i0, len(M.S)):
        if M.T[j] > t + 200: break
        lb = [b for b in lane_bodies(M.S[j], lane) if b[3] >= 0.5]
        if lb and min(b[2] for b in lb) <= 16.0: x = M.T[j]; break
    end_off = (x + 20) if x is not None else t + 200
    end_def = (x + 40) if x is not None else t + 200
    off = sum(COST.get(p[2], 0) for p in M.plays(t, end_off) if play_lane(p[3]) not in (lane, "C") or p[4] > 18.0)
    dfn = [p for p in M.plays(t, end_def) if play_lane(p[3]) in (lane, "C") and p[4] <= 16.0]
    el_x = M.S[M.i(x)][1] if x is not None else None
    do = bool(dfn) or (el_x is not None and el_x >= 5.0)
    return dict(do=do, hold=off < 4, off=off, el_x=el_x, crossed=x is not None), (dfn[0][2] if dfn else "WAIT")


def lane_threat(st, lane):
    """enemy bodies of a lane (incl. the centre strip) and the distance of the closest one to that lane's target tower."""
    k = "m" + lane
    tgt = MT[k] if (st[4].get(k) or 0) > 0 else MT["mK"]
    lb = [b for b in st[3] if (b[1] < 9.0) == (lane == "L")]
    return lb, (min(d2((b[1], b[2]), tgt) for b in lb) if lb else 99.0), tgt


def D3(M, i, st):
    """Pool elixir, don't dribble (N1/F3). A lane threat of 3-10 elixir whose closest body is still > 9 tiles from its target tower,
    my elixir in [1, 4), nothing pending.  One moment, both scores (window 10 s):
    DO = the first answer (a play landing on my half in that lane/centre) is tapped with the threat within 9 tiles OR with >= 4 elixir,
    or no answer is needed (none within 10 s).  HOLD = no CHAIN: not >= 2 cheap cards (cost <= 3) tapped at < 4 elixir into that lane."""
    if st[1] is None or not (1.0 <= st[1] < 4.0): return
    for lane in ("L", "R"):
        lb, d, _ = lane_threat(st, lane)
        if 3.0 <= val(lb) <= 10.0 and d > 9.0:
            yield "dohold", lane, dict(v=round(val(lb), 2), lane=lane, d=round(d, 1))


def J3(M, t, kind, info):
    lane = info["lane"]
    ans = [p for p in M.plays(t, t + 200) if play_lane(p[3]) in (lane, "C") and p[4] <= 16.0]
    if ans:
        p = ans[0]; st = M.S[M.i(p[0])]; _, d, _ = lane_threat(st, lane)
        do = d <= 9.0 or (p[5] is not None and p[5] >= 4.0)
    else: do = True
    cheap = [p for p in ans if COST.get(p[2], 9) <= 3 and p[5] is not None and p[5] < 4.0]
    return dict(do=do, hold=len(cheap) < 2, n_ans=len(ans)), (ans[0][2] if ans else "WAIT")


def D4(M, i, st):
    """Answer air with air (owner: Knight vs a lone Balloon). AIR-ONLY threat: enemy flyers on my half (y <= 18; Skeleton Barrel is
    not counted as air -- it drops ground skeletons) worth >= 2 elixir, and NO enemy ground body worth >= 0.5 on my half; nothing pending.
    DO-moment: + an air-DAMAGING card affordable (cards.json attacks_air / aoe_to_air -> Tesla, Ice Wizard, Rocket; Tornado only
    reaches air, no damage of its own: not a DO, not a HOLD failure).
    HOLD-moment: the same threat, any hand.  Window 4 s.  A RESPONSE = a play landing within 7 tiles of the flyer closest to my
    towers or of the tower nearest it.  DO = the first response is air-damaging.  HOLD = no ground-only response (Knight, Skeletons,
    X-Bow, Log)."""
    air = enemies(st, 18.0, ground=False)
    if val(air) < 2.0 or val(enemies(st, 18.0, ground=True)) >= 0.5: return
    c = min(air, key=lambda b: min(d2((b[1], b[2]), xy) for xy in MT.values()))
    tw = min(MT, key=lambda k: d2((c[1], c[2]), MT[k]))
    info = dict(v=round(val(air), 2), cls=sorted({b[0] for b in air}), fly=(c[1], c[2]), tower=tw)
    yield "hold", "air", info
    if afford(st, AIRCAP): yield "do", "air", info


def J4(M, t, kind, info):
    ps = [p for p in M.plays(t, t + 80) if d2((p[3], p[4]), info["fly"]) <= 7.0 or d2((p[3], p[4]), MT[info["tower"]]) <= 7.0]
    if kind == "do": return (bool(ps) and ps[0][2] in AIRCAP), (ps[0][2] if ps else "WAIT")
    bad = [p for p in ps if p[2] in GROUND_ONLY]
    return (not bad), (bad[0][2] if bad else (ps[0][2] if ps else "WAIT"))


SMALL = 1.0


def swarm(st):
    """best clump of >= 3 small ground enemy bodies (value <= 1.0 each) within 2.5 tiles, on my half / bridge (y <= 18)."""
    g = [b for b in enemies(st, 18.0, ground=True) if b[3] <= SMALL and b[0] not in BUILDINGS]
    best = None
    for b in g:
        n = [c for c in g if d2((b[1], b[2]), (c[1], c[2])) <= 2.5]
        if len(n) >= 3 and (best is None or len(n) > best[0]): best = (len(n), b[1], b[2], round(val(n), 2))
    return best


def D5(M, i, st):
    """Log targets. Log affordable, nothing pending.  DO-moment: a swarm (>= 3 small ground bodies within 2.5 tiles on my half or the
    bridge, y <= 18; covers Goblin Barrel goblins and Skeleton Barrel skeletons after they drop).  HOLD-moment: enemy bodies on my
    half are ALL flyers (>= 1; Skeleton Barrel excluded) and no ground enemy body at y <= 20 (the corridor holds air only).
    Window 3 s.  DO = a Log whose corridor covers the swarm (|dx| <= 2.7 and 0 <= swarm_y - log_y <= 10.6; the Log rolls toward the
    enemy, i.e. increasing y).  HOLD = no Log landing at y <= 18."""
    if not afford(st, {"Log"}): return
    sw = swarm(st)
    if sw: yield "do", "swarm", dict(n=sw[0], x=sw[1], y=sw[2], v=sw[3])
    air = enemies(st, 18.0, ground=False)
    if air and not enemies(st, 20.0, ground=True): yield "hold", "air", dict(v=round(val(air), 2), cls=sorted({b[0] for b in air}))


def J5(M, t, kind, info):
    logs = [p for p in M.plays(t, t + 60) if p[2] == "Log"]
    if kind == "do":
        ok = [p for p in logs if abs(p[3] - info["x"]) <= 2.7 and 0 <= info["y"] - p[4] <= 10.6]
        return bool(ok), ("Log" if ok else ("Log_miss" if logs else "noLog"))
    bad = [p for p in logs if p[4] <= 18.0]
    return (not bad), ("Log" if bad else "noLog")


R_BLAST, R_PULL = 2.5, 5.5     # Rocket radius 2.0 + ~0.5 body radius (pc.py R_CLUMP); Tornado radius 5.5 (cards.json)


def clump(bs, r):
    best = (0.0, None, None)
    for b in bs:
        v = val([c for c in bs if d2((b[1], b[2]), (c[1], c[2])) <= r])
        if v > best[0]: best = (v, b[1], b[2])
    return best


def D6(M, i, st):
    """Rocket the clump (owner: Lava Hound push with 15+ elixir). Rocket affordable (elixir >= 6), nothing pending.  Enemy bodies on my
    half (y <= 16, the rocket_value rule's min_y 16 in board terms).  DO-moment: best blast value (bodies within 2.5 tiles of a body
    centre) >= 10 elixir AT DECISION TIME (impact-time lead is Phase 2's job; measured: 44% of the value walks out during flight).
    info.kill = the value the Rocket would DESTROY (each body's value x min(1, Rocket damage / its hp now; cards.json table level);
    the rocket_value worker's 'damage' mode) -- the table splits do-moments at kill >= 6.
    D6b-moment (do_combo): Tornado also in hand, elixir >= 9, best pull value (5.5 tiles) >= 10 while the best blast < 10.
    HOLD-moment: a threat on my half (>= 3 elixir) but the best blast < 5 elixir and elixir < 9 (a Rocket leaves < 3 to defend).
    Window 3 s (4 s combo).  DO = a Rocket landing within 3.5 tiles of the clump centre.  do_combo = a Tornado AND a Rocket, both
    landing within 5.5 tiles of the pull centre.  HOLD = no Rocket landing on my half (y <= 16)."""
    if not afford(st, {"Rocket"}): return
    bs = enemies(st, 16.0)
    if not bs: return
    vb, x, y = clump(bs, R_BLAST)
    if vb >= 10.0:
        hit = [b for b in bs if d2((b[1], b[2]), (x, y)) <= R_BLAST]
        kill = vb * sum(b[3] * min(1.0, ROCKET_DMG / max(1.0, unit_hp(b[0]) * (b[6] if b[6] is not None else 1.0))) for b in hit) / max(1e-9, sum(b[3] for b in hit))
        yield "do", "clump", dict(v=round(vb, 2), x=x, y=y, kill=round(kill, 2), cls=sorted({b[0] for b in hit}))
    elif "Tornado" in (st[2] or ()) and st[1] >= 9.0:
        vp, px, py = clump(bs, R_PULL)
        if vp >= 10.0: yield "do_combo", "pull", dict(v=round(vp, 2), vb=round(vb, 2), x=px, y=py)
    if val(bs) >= 3.0 and vb < 5.0 and st[1] < 9.0: yield "hold", "lowvalue", dict(v=round(vb, 2), threat=round(val(bs), 2))


def J6(M, t, kind, info):
    if kind == "do":
        rk = [p for p in M.plays(t, t + 60) if p[2] == "Rocket"]
        ok = [p for p in rk if d2((p[3], p[4]), (info["x"], info["y"])) <= 3.5]
        return bool(ok), ("Rocket" if ok else ("Rocket_elsewhere" if rk else (M.plays(t, t + 60) or [(0, 0, "WAIT")])[0][2]))
    if kind == "do_combo":
        ps = M.plays(t, t + 80); c = (info["x"], info["y"])
        r = [p for p in ps if p[2] == "Rocket" and d2((p[3], p[4]), c) <= 5.5]
        n = [p for p in ps if p[2] == "Tornado" and d2((p[3], p[4]), c) <= 5.5]
        return bool(r and n), "+".join(sorted({p[2] for p in ps})) or "WAIT"
    bad = [p for p in M.plays(t, t + 60) if p[2] == "Rocket" and p[4] <= 16.0]
    return (not bad), ("Rocket" if bad else "noRocket")


THREAT_V, THREAT_Y = 7.0, 16.0          # review.py / push-Rocket q4: a big push = >= 7 elixir of enemy bodies at y <= 16
TT_WIN, TT_R = 40, 8.0                  # decision_options TAU_THREAT_WINDOW_S 2.0 s, TAU_THREAT_RADIUS_TILES 8.0 (tau_threat_state)


def threatened(M, i, st):
    """decision_options.tau_threat_state (a tower of mine lost hp within 2 s AND an enemy body within 8 tiles of it) OR a big push
    (>= 7 elixir of enemy bodies on my half, review.py THREAT_V/THREAT_Y)."""
    if val(enemies(st, THREAT_Y)) >= THREAT_V: return True
    for k, xy in MT.items():
        if lost_hp(M, i, k, TT_WIN) and any(d2((b[1], b[2]), xy) <= TT_R for b in st[3]): return True
    return False


def D7(M, i, st):
    """Late-game tower Rocket (owner's example). 2x or overtime (t >= 120 s), Rocket affordable, an enemy princess alive, nothing
    pending.  DO-moment: NOT threatened (threatened() above = the deployed tau_threatened measure OR a >= 7-elixir push on my half).
    HOLD-moment: threatened.  Window 5 s, refractory 10 s.  DO = a Rocket landing within 3.5 tiles of an ALIVE enemy princess
    (king tower = fail unless lethal; logged separately).  HOLD = no Rocket landing on the enemy half (y > 18)."""
    if st[0] < 2400 or not afford(st, {"Rocket"}): return
    if not any((st[4].get(k) or 0) > 0 for k in ("eL", "eR")): return
    yield ("hold" if threatened(M, i, st) else "do"), "late", dict(ph=phase(st[0]), el=round(st[1], 1))


def J7(M, t, kind, info):
    rk = [p for p in M.plays(t, t + 100) if p[2] == "Rocket"]
    st = M.S[M.i(t)]
    def at(p):
        for k in ("eL", "eR"):
            if (st[4].get(k) or 0) > 0 and d2((p[3], p[4]), ET[k]) <= 3.5: return "princess"
        if d2((p[3], p[4]), ET["eK"]) <= 3.5: return "king"
        return "unit_my_half" if p[4] <= 16 else "other"
    w = [at(p) for p in rk]
    if kind == "do": return ("princess" in w), ("Rocket_" + w[0] if w else "noRocket")
    bad = [p for p in rk if p[4] > 18.0]
    return (not bad), ("Rocket_" + at(bad[0]) if bad else ("Rocket_" + w[0] if w else "noRocket"))


import sneaky_rule as SR      # the sneaky-lock worker's rule (copy of pipeline/sneaky_lock.py @ af50e7f), so D8 == the fork's trigger


def to_bs(st):
    """my state tuple -> the minimal BoardState the sneaky rule reads (units: cls, side, x, y in the board frame = own X / 18,
    (32 - own Y) / 32; towers[4], [5] = enemy princess L, R alive)."""
    from types import SimpleNamespace as NS
    from pipeline import vocab
    units = []
    for side, rows in ((0, st[6]), (1, st[3])):
        for r in rows:
            try: units.append(NS(cls=vocab.unit_id(r[0]), side=side, x=r[1] / 18.0, y=(32.0 - r[2]) / 32.0))
            except (KeyError, ValueError): pass
    alive = [(st[4].get(k) or 0) > 0 for k in ("mK", "mL", "mR", "eK", "eL", "eR")]
    return NS(units=units, towers=[NS(alive=a) for a in alive])


def D8(M, i, st):
    """Sneaky lock (owner spec), using the sneaky-lock worker's rule unchanged (sneaky_rule.py): my X-Bow reaches an alive enemy
    princess (13.04 tiles); BLOCKERS = enemy ground bodies within 12.1 + radius of it and nearer than that tower; the plan exists
    when there is EXACTLY ONE blocker, a troop, and some Tornado cell's forward-simulated pull (speed x 3.6 per tick, 21 ticks) holds
    it >= 0.3 tiles beyond the X-Bow's drop distance for 3 ticks without dragging another body into reach.  Tornado affordable,
    nothing pending.  DO-moment: the plan exists.  HOLD-moment: blockers exist but no plan (>= 2 blockers = "other blockers inside
    the range", a building, or not pullable).  Window 3 s.  DO = a Tornado landing within 6 tiles of the blocker.
    HOLD = no Tornado landing within 6 tiles of any blocker."""
    if not afford(st, {"Tornado"}) or not any(o[0] == "x_bow" for o in st[6]): return
    bs = to_bs(st)
    sit = SR.sneaky_situation(bs)
    if sit is None or not sit["blockers"]: return
    xb = (sit["xbow"][0], 32.0 - sit["xbow"][1]); key = f"{xb[0]:.0f},{xb[1]:.0f}"
    blk = [(r[1], 32.0 - r[2]) for r in sit["blockers"]]
    plan = SR.sneaky_lock_plan(bs) if len(blk) == 1 else None
    if plan: yield "do", key, dict(xb=xb, b=blk[0], d=round(plan["d_xbow"], 2), cell=(plan["cx"], 32.0 - plan["cy"]))
    else: yield "hold", key, dict(xb=xb, blk=blk, n=len(blk), why="blockers" if len(blk) >= 2 else "not_pullable")


def J8(M, t, kind, info):
    nd = [p for p in M.plays(t, t + 60) if p[2] == "Tornado"]
    if kind == "hold":
        bad = [p for p in nd if any(d2((p[3], p[4]), b) <= 6.0 for b in info["blk"])]
        return (not bad), ("Tornado_at_blockers" if bad else ("Tornado_other" if nd else "noTornado"))
    ok = [p for p in nd if d2((p[3], p[4]), info["b"]) <= 6.0]
    return bool(ok), ("Tornado_pull" if ok else ("Tornado_other" if nd else "noTornado"))


def tornado_value(st, xy):
    near = [b for b in st[3] if d2((b[1], b[2]), xy) <= R_PULL]
    return val(near), len(near)


def D9_moments(M):
    """The right second card (pd diag: Tornado as second card 27-30% in SIM vs pros 12%).  A FIRST card is tapped at t1 while enemy
    bodies worth >= 2 elixir are on my half (y <= 16) and the SECOND card is tapped within 3 s.  (This selector looks at plays, not
    states: the moment is the second-card decision.)  Pull value of a Tornado = enemy bodies within 5.5 tiles of where it lands worth
    >= 3 elixir and >= 2 bodies, at the decision state.  DO = the second card lands on my half and is not a no-pull Tornado.
    HOLD = the second card is not a no-pull Tornado."""
    for a, b in zip(M.P, M.P[1:]):
        if not (0 < b[0] - a[0] <= 60): continue
        st = M.S[M.i(a[0])]
        th = enemies(st, 16.0)
        if val(th) < 2.0: continue
        st2 = M.S[M.i(b[0])]
        v, n = tornado_value(st2, (b[3], b[4])) if b[2] == "Tornado" else (None, None)
        nopull = b[2] == "Tornado" and not (v >= 3.0 and n >= 2)
        yield a[0], dict(first=a[2], second=b[2], gap=b[0] - a[0], nopull=nopull, v=v, threat=round(val(th), 2),
                         do=(not nopull) and b[4] <= 16.0, hold=not nopull)


DRILLS = [("D1", D1, J1, REFRACT), ("D2", D2, J2, 300), ("D3", D3, J3, REFRACT), ("D4", D4, J4, REFRACT), ("D5", D5, J5, REFRACT),
          ("D6", D6, J6, REFRACT), ("D7", D7, J7, 200), ("D8", D8, J8, 60)]


def harvest(m):
    M = Match(m); out = []; last = {}
    for i, st in enumerate(M.S):
        t = st[0]
        if M.pending(t): continue
        for name, sel, judge, rf in DRILLS:
            for kind, key, info in sel(M, i, st):
                kk = (name, kind, key)
                if t - last.get(kk, -10 ** 9) < rf: continue      # one moment per refractory window
                last[kk] = t
                res, act = judge(M, t, kind, info)
                rec = dict(drill=name, kind=kind, t=t, el=st[1], ph=phase(t), act=act, info=info)
                if isinstance(res, dict): rec.update(do=res.pop("do"), hold=res.pop("hold")); rec["info"] = {**info, **res}
                else: rec["do" if kind.startswith("do") else "hold"] = res
                out.append(rec)
    for t, info in D9_moments(M):
        out.append(dict(drill="D9", kind="dohold", t=t, el=M.S[M.i(t)][1], ph=phase(t), act=info["second"], do=info.pop("do"),
                        hold=info.pop("hold"), info=info))
    return out


# ------------------------------------------------------------------ baseline
def wilson(k, n, z=1.96):
    if not n: return None
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round(100 * (c - h) / d, 1), round(100 * (c + h) / d, 1)]


def rates(recs):
    R = {}
    for dr in sorted({r["drill"] for r in recs}):
        rr = [r for r in recs if r["drill"] == dr]
        e = {}
        for kind, field in (("do", "do"), ("hold", "hold"), ("do_combo", "do")):
            sub = [r for r in rr if (r["kind"] == kind or (r["kind"] == "dohold" and kind != "do_combo")) and field in r]
            if kind == "do_combo": sub = [r for r in rr if r["kind"] == "do_combo"]
            if not sub: continue
            k = sum(bool(r[field]) for r in sub)
            e[kind] = dict(n=len(sub), pass_pct=round(100 * k / len(sub), 1), ci=wilson(k, len(sub)),
                           acts=dict(collections.Counter(r["act"] for r in sub).most_common(6)))
        if dr == "D6":
            sub = [r for r in rr if r["kind"] == "do" and (r["info"].get("kill") or 0) >= 6.0]
            if sub:
                k = sum(bool(r["do"]) for r in sub)
                e["do_kill6"] = dict(n=len(sub), pass_pct=round(100 * k / len(sub), 1), ci=wilson(k, len(sub)),
                                     acts=dict(collections.Counter(r["act"] for r in sub).most_common(6)))
        R[dr] = e
    return R


def run():
    os.makedirs(OUT, exist_ok=True)
    opts = live_options()
    summary = {}
    for src in ("live", "pros") + (("sim",) if os.path.isdir(OUT + "sim_dump") else ()):
        ms = load(src); allrec = []; mins = collections.Counter(); nm = collections.Counter()
        for m in ms:
            fam = m.get("fam", src)
            recs = harvest(m)
            o = opts.get(m["file"], {}) if src == "live" else {}
            for r in recs:
                r.update(file=m["file"], fam=fam, log_air=o.get("log_air", "off") if src == "live" else None,
                         depl=src == "live" and fam == "towerref_bundle" and o.get("tau_threatened") is not None)
            dk = fam + ("+depl" if src == "live" and fam == "towerref_bundle" and o.get("tau_threatened") is not None else "")
            allrec += recs; mins[dk] += m["end"] / 1200.0; nm[dk] += 1
        with gzip.open(OUT + f"moments_{src}.jsonl.gz", "wt") as fh:
            for r in allrec: fh.write(json.dumps(r, default=str) + "\n")
        groups = {src: allrec} if src in ("pros", "sim") else {
            "live_current": [r for r in allrec if r["fam"] == "towerref_bundle"],
            "live_deployed": [r for r in allrec if r["depl"]],
            "live_all": allrec}
        for g, rr in groups.items():
            fams = {"live_current": ["towerref_bundle", "towerref_bundle+depl"], "live_deployed": ["towerref_bundle+depl"]}.get(g, list(nm))
            summary[g] = dict(matches=sum(nm[f] for f in fams), minutes=round(sum(mins[f] for f in fams), 1), drills=rates(rr),
                              per_match={dr: round(sum(r["drill"] == dr for r in rr) / max(1, sum(nm[f] for f in fams)), 2)
                                         for dr in sorted({r["drill"] for r in rr})})
        print(src, "matches", dict(nm), "moments", len(allrec), flush=True)
    json.dump(summary, open(OUT + "baseline.json", "w"), indent=1)
    return summary


def d9_extra():
    out = {}
    for src, filt in (("live", lambda r: r["fam"] == "towerref_bundle"), ("pros", lambda r: True), ("sim", lambda r: True)):
        with gzip.open(OUT + f"moments_{src}.jsonl.gz", "rt") as fh:
            rr = [json.loads(l) for l in fh]
        rr = [r for r in rr if r["drill"] == "D9" and filt(r)]
        aft = [r for r in rr if r["info"]["first"] == "Log"]
        q = [r for r in rr if r["info"]["gap"] <= 24]
        out[src] = dict(n=len(rr), n_le24=len(q), tornado_share_le24=round(100 * sum(r["act"] == "Tornado" for r in q) / max(1, len(q)), 1), tornado_share=round(100 * sum(r["act"] == "Tornado" for r in rr) / max(1, len(rr)), 1),
                        nopull_share=round(100 * sum(r["info"]["nopull"] for r in rr) / max(1, len(rr)), 1),
                        after_log_n=len(aft), after_log_tornado=round(100 * sum(r["act"] == "Tornado" for r in aft) / max(1, len(aft)), 1))
    return out


# ------------------------------------------------------------------ selftest (synthetic boards: each selector fires / does not)
def selftest():
    def st(t, el, hand, eb, tw=None, own=()):
        base = {"mL": 3000, "mR": 3000, "mK": 4800, "eL": 3000, "eR": 3000, "eK": 4800}
        return (t, el, hand, eb, {**base, **(tw or {})}, None, list(own), [])
    def body(cls, X, Y, v, air=False): return (cls, X, Y, v, None, 0, 1.0, air)
    hand = ("Knight", "Tesla", "Log", "Rocket")
    # D1: tower mL drops 3000 -> 2900, a 4-elixir hog-ish body near it -> do; plays Knight near -> pass
    m = dict(S=[st(0, 6, hand, [body("hog_rider", 4, 9, 4)]), st(20, 6, hand, [body("hog_rider", 4, 8, 4)], {"mL": 2900})],
             P=[(30, 50, "Knight", 4.0, 7.0, 6, None)], end=100)
    r = [x for x in harvest(m) if x["drill"] == "D1"]
    assert r and r[0]["kind"] == "do" and r[0]["do"] is True, r
    # D1 hold: a lone skeleton -> refrain (no play) passes
    m = dict(S=[st(0, 6, hand, [body("skeleton", 4, 9, .33)]), st(20, 6, hand, [body("skeleton", 4, 8, .33)], {"mL": 2990})], P=[], end=100)
    r = [x for x in harvest(m) if x["drill"] == "D1"]
    assert r and r[0]["kind"] == "hold" and r[0]["hold"] is True, r
    # D4: lone balloon on my half; Knight played -> do fails, hold fails
    m = dict(S=[st(0, 6, hand, [body("balloon", 4, 12, 5, True)])], P=[(5, 30, "Knight", 4, 9, 6, None)], end=100)
    r = {x["kind"]: x for x in harvest(m) if x["drill"] == "D4"}
    assert r["do"]["do"] is False and r["hold"]["hold"] is False, r
    # D4 with Tesla: passes both
    m["P"] = [(5, 30, "Tesla", 9, 10, 6, None)]
    r = {x["kind"]: x for x in harvest(m) if x["drill"] == "D4"}
    assert r["do"]["do"] is True and r["hold"]["hold"] is True, r
    # D5: three goblins at (4, 10); Log from (4, 4) covers them
    gob = [body("goblin", 4, 10, .5), body("goblin", 4.5, 10.5, .5), body("goblin", 3.5, 10.2, .5)]
    m = dict(S=[st(0, 6, hand, gob)], P=[(5, 30, "Log", 4, 4, 6, None)], end=100)
    r = [x for x in harvest(m) if x["drill"] == "D5"]
    assert r and r[0]["kind"] == "do" and r[0]["do"] is True, r
    # D6: a 12-elixir clump -> Rocket at it passes
    cl = [body("lava_hound", 9, 12, 7, True), body("balloon", 9.5, 12.5, 5, True)]
    m = dict(S=[st(0, 7, hand, cl)], P=[(5, 30, "Rocket", 9, 13, 7, None)], end=100)
    r = [x for x in harvest(m) if x["drill"] == "D6" and x["kind"] == "do"]
    assert r and r[0]["do"] is True, r
    # D7: 2x, quiet board, Rocket at the left princess -> do passes
    m = dict(S=[st(2500, 8, hand, [])], P=[(2510, 2540, "Rocket", 3.5, 25.5, 8, None)], end=3000)
    r = [x for x in harvest(m) if x["drill"] == "D7"]
    assert r and r[0]["kind"] == "do" and r[0]["do"] is True, r
    # D8: my X-Bow at (4, 14) locks eL; one knight at 10 tiles -> do; Tornado behind it pulls it out
    hd = ("Tornado", "Knight", "Log", "Rocket")
    m = dict(S=[st(0, 6, hd, [body("knight", 4, 25, 3)], own=[("x_bow", 4, 14, 1000, 1000)])], P=[(5, 30, "Tornado", 4, 28, 6, None)], end=100)
    r = [x for x in harvest(m) if x["drill"] == "D8"]
    assert r and r[0]["kind"] == "do" and r[0]["do"] is True, r
    # D8 hold: two blockers -> no plan; a Tornado at them fails
    m = dict(S=[st(0, 6, hd, [body("knight", 4, 23.5, 3), body("valkyrie", 5, 20, 4)], own=[("x_bow", 4, 14, 1000, 1000)])],
             P=[(5, 30, "Tornado", 4, 25, 6, None)], end=100)
    r = [x for x in harvest(m) if x["drill"] == "D8"]
    assert r and r[0]["kind"] == "hold" and r[0]["hold"] is False, r
    # val: ram rider (2 bodies, same first tick) counts once
    assert val([body("ram_rider", 4, 10, 5), body("ram_rider", 4.1, 10, 5)]) == 5.0
    # D9: Log then Tornado on an empty spot -> no-pull Tornado, hold fails
    m = dict(S=[st(0, 8, hand, [body("knight", 4, 10, 3)]), st(20, 6, hand, [body("knight", 4, 10, 3)])],
             P=[(0, 20, "Log", 4, 8, 8, None), (30, 50, "Tornado", 14, 10, 6, None)], end=100)
    r = [x for x in harvest(m) if x["drill"] == "D9"]
    assert r and r[0]["hold"] is False, r
    assert AIRCAP == {"IceWizard", "Rocket", "Tesla"} and GROUND_ONLY == {"Knight", "Log", "Skeletons", "Xbow"}, (AIRCAP, GROUND_ONLY)
    print("selftest OK; AIRCAP", sorted(AIRCAP), "AIRREACH", sorted(AIRREACH), "GROUND_ONLY", sorted(GROUND_ONLY))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest": selftest()
    elif cmd == "run":
        s = run(); print(json.dumps(d9_extra(), indent=1))
