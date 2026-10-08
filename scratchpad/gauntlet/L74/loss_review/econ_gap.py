"""Why does LIVE spend earlier / lower than SIM for the same checkpoint + options? (L74 econ gap, measurement only)

Two modes, ONE set of definitions:
  VM :  ~/venv/bin/python econ_gap.py --sim ~/loss_review/sim stack stack_bias r1e     -> econ_sim_<arm>.json (aggregates)
  local: icebow/.venv/Scripts/python.exe econ_gap.py                                   -> econ_live.json + econ_gap.md
SIM dumps come from econ_sim.sh (isolated repo patched by econ_sim_patch.py). Live = decision logs in L68/live_reader.

Per match, normalised to: own-frame tiles (my king (9,3)); 10-tick states (tick, my raw elixir, enemy bodies); decisions
(tick, p_play, play, tau, model elixir = raw + 26-tick forecast, raw elixir, opponent estimate); my card plays at the
DECISION/TAP tick with raw elixir there; abilities.
  pressure bucket pb at a tick = enemy body value on my half (own y <= 16): 0 (< .5), 1 (.5-3), 2 (3-7), 3 (>= 7)
  'quiet' = pb <= 1, 'press' = pb >= 2 (the loss review's 'press' = value >= 3)
  push episode = value >= 7 after >= 4 s below (review.py); elixir at push start = raw elixir then
Single process; low priority on the laptop.
"""
import os, sys, json, glob, math, bisect, collections, argparse
try:
    import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
ON_VM = not os.path.exists("C:/Users")
ROOT = os.path.expanduser("~/ClashBot/") if ON_VM else "C:/Users/benpe/ClashBot/"
LOGDIR = ROOT + "scratchpad/gauntlet/L68/live_reader/"
CATALOG = ROOT + "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json"
UNITV = LOGDIR + "unit_values.json"
REGEN = {"1x": 1 / 56.0, "2x": 2 / 56.0, "OT": 2 / 56.0}
TAUS = {"stack": (.35, .45, .55), "r1e": (.35, .35, .35)}
COST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
AIR = {"BabyDragon", "InfernoDragon", "ElectroDragon", "Balloon", "Minions", "MinionHorde", "MegaMinion", "SkeletonDragons", "Phoenix", "LavaHound", "LavaPups", "Bats"}


def ph(t): return "1x" if t < 2400 else ("2x" if t < 3600 else "OT")
def pidx(t): return 0 if t < 2400 else (1 if t < 3600 else 2)
def own(side, x, y): return ((18000 - x) / 1000.0, (32000 - y) / 1000.0) if side == 1 else (x / 1000.0, y / 1000.0)
def mean_(v):
    return sum(v) / len(v) if v else None


def med_(v):
    v = sorted(v); return v[len(v) // 2] if v else None


def pbk(v): return 0 if v < .5 else (1 if v < 3 else (2 if v < 7 else 3))
def eb(e): return max(0, min(9, int(e)))


NAME, NCOST, UV, LOW = {}, {}, {}, {}


def load_catalog():
    for c in json.load(open(CATALOG))["cards"]:
        for k in ("card_id", "evolution_form_id", "hero_form_id"):
            if c.get(k) is not None: NAME[int(c[k])] = c["display_name"]; NCOST[c["display_name"]] = c["elixir"]
    NAME[203000023] = "IceWizard"
    UV.update(json.load(open(UNITV))["value_per_unit"])
    for k in list(UV) + list(NCOST): LOW[k.lower()] = k


def canon(n): return LOW.get(str(n).lower().replace("-", "").replace("_", "").replace(" ", ""), str(n))
def uval(n): return UV[n] if n in UV else float(NCOST.get(n, .5))


# ------------------------------------------------------------------ loaders -> normalised match
def live_match(f):
    side = None; S = []; dec = []; plays = []; abil = []; drops = []; start = {}; end = None; forced = []
    with open(f, encoding="utf8", errors="replace") as fh:
        for l in fh:
            if not l.startswith('{"event": "'): continue
            ev = l[11:l.index('"', 11)]
            if ev not in ("start", "decision", "play", "ability", "ability_confirmed", "end", "stop"): continue
            d = json.loads(l)
            if ev == "start": start = d
            elif ev == "decision":
                p = d.get("public") or {}; dc = d.get("decision") or {}
                if "observer_side" not in p: continue
                side = p["observer_side"]
                bodies = [(canon(NAME.get(b["card_id"], str(b["card_id"]))), *own(side, b["x"], b["y"]), b["hp"], b.get("address"))
                          for b in p.get("raw_bodies", []) if b["side"] != side and b["card_id"] != -1 and b["hp"] > 0]
                S.append((d["tick"], p.get("own_elixir_raw"), bodies))
                dec.append((d["tick"], dc.get("p_play"), bool(dc.get("play")), dc.get("gate_tau"), p.get("model_own_elixir"), p.get("own_elixir_raw"),
                            p.get("opponent_elixir_estimate"), bool(dc.get("no_affordable"))))
            elif ev == "play":
                plays.append((d["tick"], d.get("name"), d.get("elixir")))
                if d.get("forced"): forced.append(d.get("elixir"))
            elif ev == "ability": abil.append(d["tick"])
            elif ev == "ability_confirmed": drops.append(d.get("elixir_drop"))
            elif ev in ("end", "stop"): end = d
    if side is None or len(S) < 50: return None
    return dict(file=os.path.basename(f), S=S, dec=dec, plays=plays, abil=abil, abil_drop=drops, end_tick=S[-1][0], spend=[(t, c) for t, c, e in plays], forced=forced, costs=[(t, c, e) for t, c, e in plays if e is not None and c],
                ckpt=(start.get("ckpt") or "").replace("\\", "/").split("/")[-1])


def sim_match(r, taus):
    b = r["behaviour"]; side = r["learner_side"]
    S = [(t, el, [(canon(c), *own(side, x, y), hp, i) for c, x, y, hp, i in bodies]) for t, el, bodies, _ in b["lr_frames"]]
    dec = [(t, p, play, taus[pidx(t)], elv, elr, opp, why == "no_affordable") for t, p, play, why, elv, elr, opp in r["lr_dec"]]
    plays = [(t, None, elr) for t, p, play, why, elv, elr, opp in r["lr_dec"] if play]
    opp_cost = sum(NCOST.get(canon(c), 0) for t, s, c, el, ab in b["lr_plays"] if s != side and not ab)
    return dict(file=r["tag"], S=S, dec=dec, plays=plays, abil=[t for t, s, c, el, ab in b["lr_plays"] if s == side and ab], abil_drop=[],
                spend=[(t - 26, canon(c)) for t, s, c, el, ab in b["lr_plays"] if s == side and not ab],
                costs=[(t - 26, canon(c), max(0.0, el - 26 * REGEN[ph(t)])) for t, s, c, el, ab in b["lr_plays"] if s == side and not ab and el is not None],
                end_tick=r["end_tick"], deploy_el=[(t, el) for t, s, c, el, ab in b["lr_plays"] if s == side and not ab and el is not None],
                opp_cost=opp_cost, outcome=r["outcome"], opp_deck=r.get("opp_deck"))


# ------------------------------------------------------------------ per-match aggregates
def metrics(M, A, live):
    S = M["S"]; T = [s[0] for s in S]; end = M["end_tick"]; mins = end / 1200.0
    A["n"] += 1; A["minutes"] += mins
    val = []; seen = set(); arrive = collections.Counter()
    occur = collections.Counter((i, n) for t, el, bodies in S for n, X, Y, hp, i in bodies)
    for t, el, bodies in S:
        v = sum(uval(n) for n, X, Y, hp, i in bodies if Y <= 16)
        val.append(v)
        for n, X, Y, hp, i in bodies:
            if Y <= 16 and (i, n) not in seen and occur[(i, n)] >= 2:     # first time on my half; one-state sightings ignored
                seen.add((i, n)); arrive[ph(t)] += uval(n)
    for p_ in arrive: A["arrive_" + p_] += arrive[p_]
    for p_, a_, b_ in (("1x", 0, 2400), ("2x", 2400, 3600), ("OT", 3600, 10 ** 9)):
        A["min_" + p_] += max(0, min(end, b_) - a_) / 1200.0
    # elixir balance: my card spend, Hero ability presses, waste at the cap, opponent spend from the public counter's drops
    my_spend = sum(COST.get(c, 0) for t, c in M["spend"])
    waste = sum(min(S[i + 1][0] - S[i][0], 30) * REGEN[ph(S[i][0])] for i in range(len(S) - 1) if S[i][1] is not None and S[i][1] >= 9.9)
    D_ = [d for d in M["dec"] if d[6] is not None]
    odrop = sum(max(0.0, min(10.0, a[6] + (b[0] - a[0]) * REGEN[ph(a[0])]) - b[6]) for a, b in zip(D_, D_[1:]) if b[0] - a[0] <= 40)
    A["my_spend"] += my_spend; A["waste"] += waste; A["opp_drop"] += odrop
    pm_start = len(A["push_el"])
    def pb_at(t):
        k = max(0, bisect.bisect_right(T, t) - 1); return pbk(val[k])
    # full-elixir states: total enemy value on the WHOLE board (their half included), bucket 0 (< .5) / 1 (.5-4) / 2 (4-8) / 3 (>= 8)
    board = [sum(uval(n) for n, X, Y, hp, i in b) for t, el, b in S]
    def bb(t):
        k = max(0, bisect.bisect_right(T, t) - 1); v = board[k]; return 0 if v < .5 else (1 if v < 4 else (2 if v < 8 else 3))
    for i in range(len(S) - 1):
        if S[i][1] is not None and S[i][1] >= 9:
            A["occ9"][f"{pidx(S[i][0])}|{pbk(val[i])}|{bb(S[i][0])}"] += min(S[i + 1][0] - S[i][0], 30) / 20.0
    for d in M["dec"]:          # every decision with the whole-board bucket too: [n, n p > tau, n play]
        if d[1] is not None and d[4] is not None:
            c = A["decB"].setdefault(f"{pidx(d[0])}|{pb_at(d[0])}|{bb(d[0])}|{eb(d[4])}", [0, 0, 0])
            c[0] += 1; c[1] += d[1] > (d[3] if d[3] is not None else .35); c[2] += d[2]
    for i in range(len(S) - 1):  # whole-board presence share by phase: time with board bucket 0/1/2/3
        A["boardT"][f"{pidx(S[i][0])}|{bb(S[i][0])}"] += min(S[i + 1][0] - S[i][0], 30) / 20.0
    for d in M["dec"]:
        if d[1] is not None and d[4] is not None and d[4] >= 9:
            c = A["dec9"].setdefault(f"{pidx(d[0])}|{pb_at(d[0])}|{bb(d[0])}", [0, 0]); c[0] += 1; c[1] += d[1] > (d[3] if d[3] is not None else .35)
    for t, card, el in M["plays"]:
        if el is not None and el >= 9: A["taps9"][f"{pidx(t)}|{pb_at(t)}|{bb(t)}"] += 1
    # occupancy (seconds) by (phase, pb, elixir bucket)
    for i in range(len(S) - 1):
        if S[i][1] is None: continue
        A["occ"][f"{pidx(S[i][0])}|{pbk(val[i])}|{eb(S[i][1])}"] += min(S[i + 1][0] - S[i][0], 30) / 20.0
    # card plays at the decision/tap tick by (phase, pb, raw elixir bucket)
    for t, card, el in M["plays"]:
        if el is None: continue
        A["taps"][f"{pidx(t)}|{pb_at(t)}|{eb(el)}"] += 1
    # elixir at deploy (live: tap raw + 26 ticks of regen; SIM: engine elixir at deploy)
    if live:
        for t, card, el in M["plays"]:
            if el is not None: A["deploy_" + ph(t)].append(min(10.0, el + 26 * REGEN[ph(t)]))
    else:
        for t, el in M["deploy_el"]: A["deploy_" + ph(t)].append(el)
    # decisions: by (phase, pb, model elixir bucket): n, sum p, n p>tau, n play; cadence; |dp|; crossings
    D = M["dec"]; prev = None
    for d in D:
        t, p, play, tau, elv, elr, opp, noaff = d
        if p is None or elv is None: prev = None; continue
        tau = tau if tau is not None else .35
        k = f"{pidx(t)}|{pb_at(t)}|{eb(elv)}"
        c = A["dec"][k] if k in A["dec"] else A["dec"].setdefault(k, [0, 0.0, 0, 0]); c[0] += 1; c[1] += p; c[2] += p > tau; c[3] += play
        if prev is not None:
            gap = t - prev[0]; A["gap"][str(min(gap, 40))] += 1
            if gap <= 12 and not prev[2]:
                A["dp"][f"{min(pb_at(t), 2)}|{min(int(abs(p - prev[1]) / .02), 25)}"] += 1
                if play and not noaff:
                    A["play_after"]["below" if prev[1] <= (prev[3] if prev[3] is not None else tau) else "above"] += 1
                    A["margin"][str(min(int((p - tau) / .05), 12))] += 1
        prev = (t, p, play, tau)
        if opp is not None: A["opp_est"].append(round(opp, 2))
    # push episodes
    last_hi = -10 ** 9; on = False; abil = M["abil"]; last_start = None
    for i, (t, el, bodies) in enumerate(S):
        if val[i] >= 7:
            if not on and t - last_hi >= 80 and el is not None:
                A["push_el"].append(round(el, 2)); A["push_v"].append(round(val[i], 1)); A["push_ph"].append(ph(t))
                A["push_since"].append(round((t - last_hi) / 20.0, 1) if last_start is not None else None); last_start = t
                A["push_abil10"] += sum(1 for a in abil if t - 200 <= a < t)
                A["push_spent10"].append(sum(COST.get(c, 0) for tt, c in M["spend"] if t - 200 <= tt < t))
            on = True; last_hi = t
        else: on = False
    A["abil"] += len(abil); A["abil_drop"] += [x for x in M["abil_drop"] if x is not None]; A["forced"] += len(M.get("forced", []))
    pe = A["push_el"][pm_start:]
    # pressure timeline for the counterfactual simulator (econ_report.simulate): states (tick, phase, pb), push-start ticks, ability ticks
    pst = []; on_ = False; lh = -10 ** 9
    for i, (t, el, b) in enumerate(S):
        if val[i] >= 7:
            if not on_ and t - lh >= 80: pst.append(t)
            on_ = True; lh = t
        else: on_ = False
    A["seq"].append([T, [pbk(v) for v in val], pst, list(abil), end, med_(pe), [bb(t) for t in T]])
    for t, card, el in M.get("costs", []):
        A["cost"][f"{eb(el)}|{COST.get(card, NCOST.get(card, 0))}"] += 1
    A["per_match"].append([M["file"], round(mins, 3), round(sum(arrive.values()), 1), len(pe), med_(pe), M.get("outcome"), M.get("opp_deck"),
                           sum(1 for t, c, e in M["plays"] if e is not None and e < 5), round(my_spend, 1), round(odrop, 1),
                           round(sum(min(S[i + 1][0] - S[i][0], 30) for i in range(len(S) - 1) if board[i] >= .5) / max(1, sum(min(S[i + 1][0] - S[i][0], 30) for i in range(len(S) - 1))), 3),
                           round(mean_([el for t, el, b in S if el is not None]), 2)])
    if live:   # reader artefacts: duplicated bodies (same card within .25 tiles in one state) and one-state phantoms
        ids = collections.Counter(); nb = 0; dup = 0; dup_v = 0.0
        for k_, (t, el, bodies) in enumerate(S[:-1]):
            for j, (n, X, Y, hp, i) in enumerate(bodies):
                ids[(i, n)] += 1; nb += 1
                if any(n2 == n and abs(X2 - X) < .25 and abs(Y2 - Y) < .25 for n2, X2, Y2, hp2, i2 in bodies[:j]):
                    dup += 1; dup_v += uval(n) if Y <= 16 else 0
        A["bodies"] += nb; A["dup"] += dup; A["dup_v_half"] += dup_v
        A["phantom"] += sum(1 for v in ids.values() if v == 1); A["ids"] += len(ids)
    else:
        A["opp_cost"] += M["opp_cost"]; A["outcomes"][M["outcome"]] += 1


def new_agg():
    return collections.defaultdict(float, occ=collections.Counter(), taps=collections.Counter(), dec={}, occ9=collections.Counter(), taps9=collections.Counter(), dec9={}, decB={}, boardT=collections.Counter(), cost=collections.Counter(), gap=collections.Counter(),
                                   dp=collections.Counter(), play_after=collections.Counter(), margin=collections.Counter(),
                                   outcomes=collections.Counter(), **{k: [] for k in ("push_el", "push_v", "push_ph", "push_spent10", "push_since", "per_match", "seq", "opp_est", "abil_drop",
                                                                                     "deploy_1x", "deploy_2x", "deploy_OT")})


def save(A, path):
    json.dump({k: (dict(v) if isinstance(v, (dict, collections.Counter)) else v) for k, v in A.items()}, open(path, "w"))


# ------------------------------------------------------------------ main
def sim_mode(d, arms):
    for arm in arms:
        A = new_agg(); taus = TAUS["r1e" if arm.startswith("r1e") else "stack"]
        for s in ("evo", "lad"):
            p = f"{d}/{arm}_{s}/matches.jsonl"
            if not os.path.exists(p): print("missing", p); continue
            for l in open(p):
                try: r = json.loads(l)
                except ValueError: continue          # a line still being written
                if r.get("arm") == "plain" and "lr_dec" in r: metrics(sim_match(r, taus), A, live=False)
        save(A, f"{d}/econ_sim_{arm}.json"); print(arm, int(A["n"]), "matches")


def live_mode():
    fam = {"stack": "barrel2k_cellref.pt", "towerref": "towerref_w2", "r1e": "r1e31"}
    aggs = {k: new_agg() for k in list(fam) + ["stack_al1", "stack_al0"]}
    for f in sorted(glob.glob(LOGDIR + "live_play_20261004_2*.jsonl") + glob.glob(LOGDIR + "live_play_2026100[5-9]_*.jsonl")):
        with open(f, encoding="utf8", errors="replace") as fh: st = json.loads(fh.readline())
        if st.get("dry_run"): continue
        ck = (st.get("ckpt") or "").replace("\\", "/")
        k = next((k for k, s in fam.items() if ck.endswith(s) or (s in ck and k != "stack")), None)
        if k is None: continue
        M = live_match(f)
        if M:
            metrics(M, aggs[k], live=True)
            if k == "stack": metrics(M, aggs["stack_al1" if st.get("anti_leak") else "stack_al0"], live=True)
    for k, A in aggs.items(): save(A, HERE + f"econ_live_{k}.json"); print(k, int(A["n"]), "matches")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sim", nargs="+"); ap.add_argument("--report", action="store_true")
    a = ap.parse_args(); load_catalog()
    if a.sim: sim_mode(a.sim[0], a.sim[1:])
    elif a.report:
        sys.path.insert(0, HERE); import econ_report; econ_report.write()
    else: live_mode()
