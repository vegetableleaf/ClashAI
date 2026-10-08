"""L74 DEFENSE diagnosis (measurement only): why does the live icebow bot defend poorly?  D1-D5 on ONE normalised format for
LIVE (R-lineage decision logs) and PROS (2,244 icebow sides, push-Rocket worker's pros.pkl).

  icebow/.venv/Scripts/python.exe defense.py live            -> data/live.pkl.gz   (single core, below normal; parses the logs)
  icebow/.venv/Scripts/python.exe defense.py pros            -> data/pros.pkl.gz
  icebow/.venv/Scripts/python.exe defense.py report          -> out/results.json + printed tables (out/report.txt)
  icebow/.venv/Scripts/python.exe defense.py selftest

Normalised match: S = [(t, el, hand, eb, tw, dec)] states every ~10 ticks (live: decision states; pros: frames)
  eb  = enemy bodies at own y <= 20: (name, X, Y, value)   value = econ2 body fix on live (spawned units valued by their hp share
        of the card's largest first-seen hp; Graveyard / Goblin Barrel per unit), card-cost cap on pros (pros have no hp:
        all bodies with one label in a state are worth at most cost x max(1, plays of that card in the last 20 s))
  tw  = my towers {mL, mR, mK: hp} (a princess seen then missing = 0)
  dec = live only: (play, p_play, top card, tau, no_affordable)
  P   = my plays (tap, land, card, X, Y, el): live tap = play event tick, land = confirmed tick (None if never confirmed);
        pros: tap = None, land = engine deploy tick, el = elixir before the deploy.
Own frame tiles: my king (9,3), my princesses (3.5,6.5) / (14.5,6.5), my half y <= 16.
Public information only: own state, enemy bodies/projectiles on the board, the public-play counter (unused here).  The
opp_elixir_true_EVAL_ONLY frame field is never read (decision states only).
"""
import os, sys, json, gzip, pickle, bisect, collections, math, glob, time, random

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
sys.path.insert(0, HERE + "../loss_review"); sys.path.insert(0, HERE + "../econ2")
import review as V        # sets below-normal priority on Windows; parse(), features(), resolve()
import econ_gap as G
import econ2 as E2
DATA, OUT = HERE + "data/", HERE + "out/"
PKL = "C:/Users/benpe/ClashBot/.claude/worktrees/agent-a8aad346ac44709a7/scratchpad/gauntlet/L73/push_rocket/pros.pkl"
LINEAGE_FROM = "20261004_205129"
COST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
TW = {"mL": (3.5, 6.5), "mR": (14.5, 6.5), "mK": (9.0, 3.0)}
HALF_Y = 16.0              # enemy value on my half
DEF_Y = 18.0               # a play landing at own y <= 18 is defensive (my half + bridge)
LANE_ON, LANE_OFF = 3.0, 1.0   # lane episode: lane value >= 3 after >= 80 ticks below 3; ends after >= 60 ticks below 1
WIN_MAX = 600              # episode max length (ticks)
AIR = V.AIR | {"LavaHound", "LavaPups", "SkeletonDragons", "InfernoDragon", "ElectroDragon", "Phoenix", "BabyDragon"}
AIR_ANSWER = {"IceWizard", "Tesla", "Xbow", "Rocket"}
BUILDING_TARGET = {"HogRider", "RoyalHogs", "Giant", "Golem", "Golemite", "RoyalGiant", "Balloon", "BattleRam", "RamRider", "ElectroGiant",
                   "GoblinGiant", "ElixirGolem", "LavaHound", "Wallbreakers", "SkeletonBalloon", "GoblinDrill", "RuneGiant", "Goblinstein"}


def ph(t): return "1x" if t < 2400 else ("2x" if t < 3600 else "OT")
def lane_of(X): return "L" if X < 9.0 else "R"
def play_lane(X): return "L" if X < 7.5 else ("R" if X > 10.5 else "C")


# ------------------------------------------------------------------ LIVE: parse with review.py, normalise
def live_one(f):
    r = V.parse(f)
    if not (r["end"] or r["stop"]) or not r["n_dec"]: return None
    row = V.features(r)
    if not row.get("valid_state") or row.get("dry_run"): return None
    S = r["S"]; side = r["side"]
    st = r["start"] or {}; do = st.get("decision_options") or {}
    # econ2 body fix: first-seen hp per (addr, card), largest first-seen hp per card in the match
    hp0 = {}; hpmax = collections.Counter()
    for s in S:
        for b in s[4]:
            mine, X, Y, cid, hp, mx, kind, addr = b
            if mine or cid == -1: continue
            n = G.canon(E2.vname(V.nm(cid)))
            if (addr, n) not in hp0: hp0[(addr, n)] = hp; hpmax[n] = max(hpmax[n], hp or 0)
    first = {}            # enemy body first sighting anywhere (commit)
    NS = []; seen_tw = set()
    for s in S:
        t, el, _, hand, bodies, proj, dec = s
        eb = []; tw = {}
        for b in bodies:
            mine, X, Y, cid, hp, mx, kind, addr = b
            if cid == -1:
                sl = V.tower_slot(b)
                if sl and sl[0] == "m" and hp > 0: tw[sl] = hp
                continue
            if mine or hp <= 0: continue
            n = G.canon(E2.vname(V.nm(cid)))
            if (addr, n) not in first: first[(addr, n)] = t
            if Y > 20: continue
            u = E2.bval(n) if (n in E2.SPELL_UNIT or not hpmax[n]) else E2.bval(n) * min(1.0, max(0.0, hp0[(addr, n)] or 0) / hpmax[n])
            eb.append((n, round(X, 2), round(Y, 2), round(u, 3), addr, first[(addr, n)]))
        seen_tw |= set(tw)
        for k in seen_tw:
            tw.setdefault(k, 0)
        pr = [(G.canon(V.nm(q[3])), round(q[1], 2), round(q[2], 2)) for q in proj if not q[0] and q[3] != -1]
        d = None if dec is None else (dec[0], dec[1], dec[2], dec[3] or .35, dec[4])
        NS.append((t, el, tuple(hand) if hand else None, eb, tw, d, pr))
    P = []
    for p in r["plays"]:
        if p["X"] is None: continue
        P.append((p["tick"], p["conf"]["tick"] if p["conf"] else None, p["name"], round(p["X"], 2), round(p["Y"], 2), p["el"]))
    gate = do.get("gate_decode")
    ck = row.get("ckpt") or ""
    fam = ("towerref_bundle" if gate else "towerref_pre") if "towerref_w2" in ck else V.family(row)
    return dict(src="live", file=r["file"], fam=fam, side=side, end=row["end_tick"], pmax=4424.0, S=NS, P=P,
                row={k: row.get(k) for k in ("file", "ts", "wall_s", "end_tick", "derived", "crowns_me", "crowns_opp", "n_plays", "dry_run")})


def live_mode(limit=None):
    fs = sorted(f for f in glob.glob(V.LOGDIR + "live_play_2026*.jsonl") if os.path.basename(f)[10:25] >= LINEAGE_FROM)
    now = time.time(); fs = [f for f in fs if now - os.path.getmtime(f) >= 600]
    if limit: fs = fs[-limit:]
    names, costs, uv = V._catalog(); V.NAME.update(names); V.NCOST.update(costs); V.UV.update(uv); G.load_catalog()
    out = []; t0 = time.time()
    for i, f in enumerate(fs):
        try: m = live_one(f)
        except Exception as e:
            print("ERR", os.path.basename(f), type(e).__name__, e, flush=True); continue
        if m: out.append(m)
        if i % 50 == 0: print(f"[{i}/{len(fs)}] {time.time() - t0:.0f}s kept {len(out)}", flush=True)
    rows = [m["row"] for m in out]
    V.resolve(rows)
    for m, r in zip(out, rows): m["res"] = r["result"]; m["res_src"] = r["result_src"]
    os.makedirs(DATA, exist_ok=True)
    with gzip.open(DATA + "live.pkl.gz", "wb") as fh: pickle.dump(out, fh)
    print("live matches", len(out), collections.Counter(m["fam"] for m in out), collections.Counter(m["res"] for m in out))


# ------------------------------------------------------------------ PROS
def pros_mode():
    G.load_catalog()
    Pr = pickle.load(open(PKL, "rb")); out = []
    for m in Pr:
        F = m["F"]
        if len(F) < 20: continue
        op = sorted(m["op"]); opn = [(t, G.canon(n)) for t, n, X, Y, c in op]; opt = [t for t, _ in opn]
        NS = []; seen = set()
        for t, el, hand, en, tw in F:
            k1 = bisect.bisect_right(opt, t); k0 = bisect.bisect_left(opt, t - 400)
            recent = collections.Counter(n for _, n in opn[k0:k1])
            by = collections.defaultdict(list)
            for n, X, Y in en: by[G.canon(n)].append((X, Y))
            eb = []
            for n, L in by.items():
                u = E2.bval(n); cap = float(G.NCOST.get(n, u)) * max(1, recent[n])
                tot = u * len(L); f_ = min(1.0, cap / tot) if tot > 0 else 1.0
                for X, Y in L: eb.append((n, X, Y, round(u * f_, 3), None, None))
            twm = {k: v for k, v in tw.items() if k[0] == "m"}; seen |= set(twm)
            for k in seen:
                if k != "mK": twm.setdefault(k, 0)
            NS.append((t, el, tuple(E2.cardn(h) for h in hand) if hand else None, eb, twm, None, []))
        P = [(None, t, E2.cardn(E2.PRO_CARD.get(n, n)), X, Y, e) for t, n, X, Y, e in sorted(m["me"])]
        out.append(dict(src="pros", file=m["id"], fam="pros", end=m["end"], pmax=3052.0, S=NS, P=P,
                        res="DRAW" if m["draw"] else ("WIN" if m["win"] else "LOSS"), opx=[(t, n, X, Y, c) for t, n, X, Y, c in op]))
    os.makedirs(DATA, exist_ok=True)
    with gzip.open(DATA + "pros.pkl.gz", "wb") as fh: pickle.dump(out, fh)
    print("pro sides", len(out))


def load(name):
    with gzip.open(DATA + name + ".pkl.gz", "rb") as fh: return pickle.load(fh)


# ------------------------------------------------------------------ shared analysis
def lane_val(eb, lane, ymax=HALF_Y):
    return sum(b[3] for b in eb if b[2] <= ymax and lane_of(b[1]) == lane)


def is_def(p, lane=None):
    """landed defensive play (own y <= 18); with lane: in that lane or the centre."""
    if p[1] is None or p[4] > DEF_Y: return False
    return lane is None or play_lane(p[3]) in (lane, "C")


def tower_for(tw, lane):
    k = "m" + lane
    return k if tw.get(k, 1) > 0 else "mK"


def hp_series(S):
    T = [s[0] for s in S]
    return T, {k: [s[4].get(k) for s in S] for k in ("mL", "mR", "mK")}


def dmg(T, H, k, t0, t1):
    """HP lost on tower k between t0 and t1 (state values, step function)."""
    if t1 <= t0: return 0.0
    i0 = max(0, bisect.bisect_right(T, t0) - 1); i1 = max(0, bisect.bisect_right(T, t1) - 1)
    a, b = H[k][i0], H[k][i1]
    if a is None or b is None: return 0.0
    return float(max(0, a - b))


def episodes(m):
    """lane episodes -> list of dict(lane, i0, t, t_end, vmax, v0, tower, cards, air, bt)."""
    S = m["S"]; out = []
    for lane in ("L", "R"):
        v = [lane_val(s[3], lane) for s in S]
        last_hi = -10 ** 9; on = None
        i = 0
        while i < len(S):
            t = S[i][0]
            if v[i] >= LANE_ON and on is None and t - last_hi >= 80:
                j = i; quiet = None
                while j + 1 < len(S) and S[j + 1][0] - t < WIN_MAX:
                    j += 1
                    if v[j] < LANE_OFF: quiet = S[j][0] if quiet is None else quiet
                    else: quiet = None
                    if quiet is not None and S[j][0] - quiet >= 60: break
                names = collections.Counter()
                for jj in range(i, j + 1):
                    for b in S[jj][3]:
                        if b[2] <= HALF_Y and lane_of(b[1]) == lane: names[b[0]] += b[3]
                cards = [n for n, _ in names.most_common(4)]
                out.append(dict(lane=lane, i0=i, i1=j, t=t, t_end=S[j][0], v0=round(v[i], 2), vmax=round(max(v[i:j + 1]), 2),
                                tower=tower_for(S[i][4], lane), cards=cards, air=any(n in AIR for n in names),
                                air_only=bool(names) and all(n in AIR for n in names),
                                bt=any(n in BUILDING_TARGET for n in names), ph=ph(t)))
                last_hi = S[j][0]
                i = j + 1; continue
            if v[i] >= LANE_ON: last_hi = t
            i += 1
    return sorted(out, key=lambda e: e["t"])


def state_label(m, s, lane, busy):
    """why no defensive play for `lane` at decision state s (live)."""
    d = s[5]; el = s[1] or 0.0; hand = s[2] or ()
    if busy: return "pending_other"
    if d is None: return "unknown"
    if d[0]: return "played_other"
    if d[4]: return "no_elixir"
    if d[1] is not None and d[1] < d[3]: return "gate"
    return "other"


def analyse_episode(m, e, T, H):
    """response timing, interval labels and damage split for one lane episode."""
    S, P = m["S"], m["P"]; lane = e["lane"]; t, te = e["t"], e["t_end"]; k = e["tower"]
    live = m["src"] == "live"
    tail = te + 60
    defp = [p for p in P if is_def(p, lane) and (p[0] if live else p[1] - 26) is not None and t - 40 <= (p[0] if live else p[1] - 26) <= te]
    first = defp[0] if defp else None
    e["n_def"] = len(defp); e["el_def"] = sum(COST.get(p[2], 0) for p in defp)
    e["def_cards"] = [p[2] for p in defp][:4]
    e["dmg"] = dmg(T, H, k, t, tail)
    e["dmg_all"] = sum(dmg(T, H, kk, t, tail) for kk in ("mL", "mR", "mK"))
    e["el0"] = S[e["i0"]][1]
    # commit = earliest first sighting (anywhere) of the lane bodies on my half at the start state; pros: earliest matching opponent play
    lb = [b for b in S[e["i0"]][3] if b[2] <= HALF_Y and lane_of(b[1]) == lane and b[3] >= .5]
    if live: cm = [b[5] for b in lb if b[5] is not None and b[5] >= t - 600]
    else:
        names = {b[0] for b in lb}
        cm = [x[0] for x in m.get("opx", ()) if t - 600 <= x[0] <= t and G.canon(x[1]) in names]
    e["t_commit"] = min(cm) if cm else None
    hand0 = S[e["i0"]][2] or ()
    e["hand0"] = list(hand0)
    e["air_ans_in_hand"] = any(c in AIR_ANSWER for c in hand0)
    # first damage tick on the lane tower
    fd = None
    for j in range(e["i0"], len(S)):
        if S[j][0] > tail: break
        if j > e["i0"] and (H[k][j] or 0) < (H[k][j - 1] or 0): fd = S[j - 1][0]; break
    e["t_first_dmg"] = fd
    if first:
        tap = first[0] if live else first[1] - 26
        e["rsp_tap"] = (tap - t) / 20.0 if live else None
        e["rsp_land"] = (first[1] - t) / 20.0
        e["first_card"] = first[2]; e["first_xy"] = (first[3], first[4]); e["first_land"] = first[1]
    else:
        tap = None; e["rsp_tap"] = e["rsp_land"] = None; e["first_card"] = None; e["first_land"] = None
    # labelled intervals [a, b, label]
    iv = []
    if live:
        stop = tap if tap is not None else tail
        pend = [(p[0], p[1] if p[1] is not None else p[0] + 28) for p in P if not (first and p is first)]
        for j in range(e["i0"], len(S)):
            a = S[j][0]
            if a >= stop: break
            b = min(S[j + 1][0] if j + 1 < len(S) else a + 10, stop)
            busy = any(x <= a < y for x, y in pend)
            iv.append([a, b, state_label(m, S[j], lane, busy)])
        if first:
            # HP is only observed at decision states and none exist inside the tap -> land lock, so the latency window runs to the
            # first state at/after the landing (damage done during the lock shows up there)
            allp = [(p[0], p[1] if p[1] is not None else p[0] + 28) for p in P]
            j0 = bisect.bisect_left(T, first[1])
            iv.append([tap, S[j0][0] if j0 < len(S) else first[1], "latency"])
            # after the first defence lands: why is the NEXT card (not) coming?
            for j in range(j0, len(S)):
                a = S[j][0]
                if a >= tail: break
                b = min(S[j + 1][0] if j + 1 < len(S) else a + 10, tail); d = S[j][5]
                if d is not None and d[0] or any(x <= a < y for x, y in allp): l = "d_pending"
                elif d is None: l = "d_unknown"
                elif d[4]: l = "d_no_elixir"
                elif d[1] is not None and d[1] < d[3]: l = "d_gate"
                else: l = "d_other"
                iv.append([a, b, l])
    else:
        stop = first[1] if first else tail
        for j in range(e["i0"], len(S)):
            a = S[j][0]
            if a >= stop: break
            b = min(S[j + 1][0] if j + 1 < len(S) else a + 10, stop)
            hand = S[j][2] or ()
            aff = bool(hand) and (S[j][1] or 0) >= min(COST.get(c, 9) for c in hand)
            iv.append([a, b, "had_elixir" if aff else "no_elixir"])
        if first:
            j0 = bisect.bisect_left(T, first[1])
            for j in range(j0, len(S)):
                a = S[j][0]
                if a >= tail: break
                b = min(S[j + 1][0] if j + 1 < len(S) else a + 10, tail); hand = S[j][2] or ()
                aff = bool(hand) and (S[j][1] or 0) >= min(COST.get(c, 9) for c in hand)
                iv.append([a, b, "d_had_elixir" if aff else "d_no_elixir"])
    # merge
    mg = []
    for a, b, l in iv:
        if b <= a: continue
        if mg and mg[-1][2] == l and mg[-1][1] >= a: mg[-1][1] = max(mg[-1][1], b)
        else: mg.append([a, b, l])
    e["iv"] = mg
    sec = collections.Counter(); dm = collections.Counter()
    for a, b, l in mg:
        sec[l] += (b - a) / 20.0; dm[l] += dmg(T, H, k, a, b)
    e["sec"] = dict(sec); e["dm"] = dict(dm)
    # gate states: p, tau, top card
    if live:
        g = [(S[j][5][1], S[j][5][3], S[j][5][2]) for j in range(e["i0"], len(S)) if S[j][0] < (tap if tap is not None else tail)
             and S[j][5] is not None and not S[j][5][0] and not S[j][5][4] and S[j][5][1] is not None and S[j][5][1] < S[j][5][3]]
        e["gate_p"] = [round(x[0], 3) for x in g][:40]; e["gate_tau"] = g[0][1] if g else None
        e["gate_top"] = collections.Counter(x[2] for x in g).most_common(2)
        if first:   # gate waits AFTER the first defence landed, while the lane tower is losing HP in that interval
            dg = []
            for a, b, l in mg:
                if l != "d_gate" or dmg(T, H, k, a, b) <= 0: continue
                for j in range(bisect.bisect_left(T, a), bisect.bisect_left(T, b)):
                    d = S[j][5]
                    if d is not None and d[1] is not None: dg.append((round(d[1], 3), d[3], d[2], S[j][1]))
            e["dgate_hurt"] = dg[:40]
        # non-defensive plays made during the wait (what the bot played instead)
        e["other_plays"] = [(p[2], p[3], p[4], (p[0] - t) / 20.0) for p in P if p[0] is not None and t <= p[0] < (tap if tap is not None else tail)
                            and not is_def(p, lane)][:4]
    else:
        e["other_plays"] = [(p[2], p[3], p[4], (p[1] - t) / 20.0) for p in P if t <= p[1] - 26 < (first[1] - 26 if first else tail) and not is_def(p, lane)][:4]
    return e


def split_moments(m, T, H):
    """D1: plays made while BOTH lanes hold enemy value on my half, one clearly heavier."""
    S, P = m["S"], m["P"]; live = m["src"] == "live"; out = []
    for p, (dname, ymax) in ((p, d) for p in P for d in (("half", HALF_Y), ("approach", 20.0))):
        if p[1] is None: continue
        td = p[0] if live else p[1] - 26
        i = max(0, bisect.bisect_right(T, td) - 1)
        s = S[i]; vL, vR = lane_val(s[3], "L", ymax), lane_val(s[3], "R", ymax)
        hv, lv = max(vL, vR), min(vL, vR)
        if lv < 1.0 or hv < 4.0 or hv < 2 * lv: continue
        heavy = "L" if vL >= vR else "R"; light = "R" if heavy == "L" else "L"
        pl = play_lane(p[3])
        where = "offence" if p[4] > DEF_Y else ("heavy" if pl == heavy else "light" if pl == light else "centre")
        # already answered the heavy lane in the 5 s before?
        prior = any(q is not p and q[1] is not None and td - 100 <= (q[0] if live else q[1] - 26) < td and is_def(q, heavy) for q in P)
        kh = tower_for(s[4], heavy); kl = tower_for(s[4], light)
        out.append(dict(defn=dname, t=td, ph=ph(td), card=p[2], where=where, vh=round(hv, 2), vl=round(lv, 2), prior_heavy=prior,
                        dmg_heavy10=dmg(T, H, kh, td, td + 200), dmg_light10=dmg(T, H, kl, td, td + 200), el=p[5]))
    return out


def def_plays(m, eps, T, H):
    """D4: every landed defensive play inside a lane episode window."""
    S, P = m["S"], m["P"]; live = m["src"] == "live"; out = []
    for e in eps:
        lane = e["lane"]; k = e["tower"]
        for p in P:
            if not is_def(p, lane): continue
            td = p[0] if live else p[1] - 26
            if not (e["t"] - 40 <= td <= e["t_end"]): continue
            i = max(0, bisect.bisect_right(T, p[1]) - 1); s = S[i]
            th = [b for b in s[3] if b[2] <= HALF_Y + 2 and lane_of(b[1]) == lane and b[3] >= .5] or [b for b in s[3] if b[2] <= HALF_Y + 2 and b[3] >= .5]
            near = min((math.hypot(b[1] - p[3], b[2] - p[4]), b) for b in th)[1] if th else None
            big = max(th, key=lambda b: b[3]) if th else None
            v_after = lane_val(S[min(len(S) - 1, bisect.bisect_right(T, p[1] + 200))][3], lane)
            out.append(dict(card=p[2], ph=ph(p[1]), X=p[3], Y=p[4], lane=play_lane(p[3]), ep_lane=lane, vmax=e["vmax"], bt=e["bt"], air=e["air"],
                            ep_cards=e["cards"][:2],
                            d_near=round(math.hypot(near[1] - p[3], near[2] - p[4]), 2) if near else None,
                            big=big[0] if big else None, big_xy=(big[1], big[2]) if big else None,
                            in_front=(big is not None and p[4] < big[2]),
                            d_king=round(math.hypot(p[3] - 9.0, p[4] - 3.0), 2), d_tower=round(math.hypot(p[3] - TW[k][0], p[4] - TW[k][1]), 2),
                            dmg10=dmg(T, H, k, p[1], p[1] + 200), v_after10=round(v_after, 2), el=p[5],
                            first=(e.get("first_card") is not None and p[1] == e["first_land"]), ep_t=e["t"], rsp_land=e["rsp_land"]))
    return out


def damage_chunks(m, eps, T, H):
    """D5: every drop of my tower HP -> (tower, phase, attributed cards, response label of the matching lane episode)."""
    S = m["S"]; out = []
    byl = collections.defaultdict(list)
    for e in eps:
        for a, b, l in e["iv"]: byl[e["lane"]].append((a, b, l, e))
    for i in range(1, len(S)):
        for k in ("mL", "mR", "mK"):
            a, b = S[i - 1][4].get(k), S[i][4].get(k)
            if a is None or b is None or b >= a: continue
            d = a - b; t0, t1 = S[i - 1][0], S[i][0]; mid = (t0 + t1) / 2
            cx, cy = TW[k]
            cand = [(bb[0], bb[3]) for bb in S[i - 1][3] if math.hypot(bb[1] - cx, bb[2] - cy) <= 9.0 and bb[3] > 0]
            pr = [q[0] for q in S[i - 1][6] + S[i][6] if math.hypot(q[1] - cx, q[2] - cy) <= 4.0]
            if cand:
                tot = sum(v for _, v in cand) or 1.0; att = collections.Counter()
                for n, v in cand: att[n] += d * v / tot
            elif pr: att = collections.Counter({pr[0] + "(spell)": d})
            else: att = collections.Counter({"unseen": d})
            lanes = ["L"] if k == "mL" else ["R"] if k == "mR" else ["L", "R"]
            lab = "no_episode"; ep = None
            for ln in lanes:
                for a_, b_, l_, e_ in byl[ln]:
                    if a_ <= mid < b_: lab, ep = l_, e_; break
                if ep: break
            out.append(dict(t=t0, ph=ph(t0), k=k, d=d, att=dict(att), lab=lab, ep_v=ep["vmax"] if ep else None, ep_t=ep["t"] if ep else None))
    return out


def analyse(m):
    T, H = hp_series(m["S"])
    eps = episodes(m)
    for e in eps: analyse_episode(m, e, T, H)
    return dict(file=m["file"], src=m["src"], fam=m["fam"], res=m["res"], end=m["end"], pmax=m["pmax"],
                eps=eps, split=split_moments(m, T, H), dplays=def_plays(m, eps, T, H), chunks=damage_chunks(m, eps, T, H),
                taken={p: sum(dmg(T, H, k, a, min(b, m["end"])) for k in ("mL", "mR", "mK")) for p, a, b in V.PH if m["end"] > a})


def build(name):
    G.load_catalog(); ms = load(name); out = []
    for i, m in enumerate(ms):
        try: out.append(analyse(m))
        except Exception as ex:
            print("ERR", m["file"], type(ex).__name__, ex, flush=True)
    with gzip.open(DATA + name + "_an.pkl.gz", "wb") as fh: pickle.dump(out, fh)
    print(name, "analysed", len(out))


def selftest():
    S = [(t, 5.0, ("Knight",), ([("HogRider", 3.0, 10.0, 4.0, "a", 0)] if 100 <= t <= 300 else []), {"mL": 4424 - max(0, t - 200), "mR": 4424, "mK": 7032},
          (False, .2, "Knight", .35, False), []) for t in range(0, 600, 10)]
    m = dict(src="live", file="x", fam="t", res="LOSS", end=590, pmax=4424.0, S=S, P=[(150, 178, "Knight", 4.0, 9.0, 5.0)])
    a = analyse(m)
    e = a["eps"][0]
    assert e["lane"] == "L" and e["t"] == 100 and e["rsp_tap"] == 2.5 and e["rsp_land"] == 3.9, e
    assert abs(e["sec"]["gate"] - 2.5) < 1e-9 and e["sec"]["latency"] == 1.5 and "d_gate" in e["sec"], e["sec"]
    assert e["dm"].get("gate", 0) == 0 and e["dm"]["d_gate"] > 0
    assert a["chunks"] and all(c["att"].get("HogRider") or c["att"].get("unseen") for c in a["chunks"])
    assert play_lane(9.0) == "C" and lane_of(3.0) == "L" and is_def((1, 2, "Log", 4.0, 18.0, 5)) and not is_def((1, 2, "Rocket", 4.0, 25.0, 5))
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:] or ["selftest"]
    if a[0] == "live": live_mode(int(a[1]) if len(a) > 1 else None); build("live")
    elif a[0] == "pros": pros_mode(); build("pros")
    elif a[0] == "build": build(a[1])
    elif a[0] == "selftest": selftest()
    else: print(__doc__)
