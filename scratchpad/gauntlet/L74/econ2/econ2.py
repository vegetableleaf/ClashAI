"""L74 econ2 -- selection (Q1) and the seconds before a push (Q2) on ONE compact per-match format for LIVE, SIM and pros.

Modes (definitions shared with ../loss_review/econ_gap.py, imported):
  laptop: icebow/.venv/Scripts/python.exe econ2.py live              -> data/live.json.gz      (single core, below normal)
  VM:     ~/venv/bin/python econ2.py sim <dir> <arm> [<arm> ...]       -> data/sim_<arm>.json.gz (<dir>/<arm>_{evo,lad}/matches.jsonl)
  VM:     ~/venv/bin/python econ2.py pros <pros.pkl>                  -> data/pros.json.gz
  any:    python econ2.py report <name> [<name> ...]                  -> econ2_<names>.json (tables printed: Q1a-c, Q2, P1, P2, Q2d)
          python econ2.py calib live sim_<arm>[@seedcut][#evo|#lad]   -> Q3 pressure / economy table + calibration distance
          python econ2.py hazard live_r1e:sim_r1e ...                 -> whole-match tap hazard by elixir, matched on phase x board
          python econ2.py deploys|depcards|paired ...                  -> where enemy bodies appear; by card; paired SIM outcomes
          python econ2.py selftest
Body values use the econ2 fix (ALIAS / spawned-child hp ratio / SPELL_UNIT below); ECON2_BODY_FIX=0 restores econ_gap's values.
SIM arms come from ../loss_review/econ_sim*.sh and calib.sh / screen.sh (isolated VM repo ~/econ2/repo, LR_OPP_TAU knob).

Compact match: T (state ticks), el (my raw elixir), vm (enemy body value on my half, own y <= 16), vt (enemy value on their
half; pros see only 16 < y <= 20), tk (largest single enemy unit value on their half), opp (public opponent counter as the
model sees it = forecast at +26 ticks; pros: rebuilt from visible plays, same +26), ops (opponent plays from counter drops,
[tick, cost]), opx (exact opponent plays [tick, cost, card]: SIM lr_plays deploy tick, pros log), pl (my plays [tap tick,
card, elixir at tap, forced]; pros: deploy tick - 26, elixir before - 26 ticks of regen), ab (ability ticks), cm (push
commit tick per push start: first sighting of the push's units, pros: earliest matching opponent play), end, out, deck.
Push start = econ_gap: enemy value on my half >= 7 after >= 80 ticks below; elixir at push start = raw elixir then.
Public information only (the opponent counter is the public-play counter; no opponent hand / elixir truth).
"""
import os, sys, json, gzip, bisect, collections, math, glob
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
sys.path.insert(0, HERE + "../loss_review"); sys.path.insert(0, HERE)
import econ_gap as G       # sets below-normal priority on Windows

DATA = HERE + "data/"
CARDS = ("Xbow", "Rocket", "Tesla", "Knight", "IceWizard", "Tornado", "Log", "Skeletons")
PRO_CARD = {"x-bow": "Xbow", "the-log": "Log", "ice-wizard": "IceWizard", "skeletons": "Skeletons", "knight": "Knight",
            "tesla": "Tesla", "tornado": "Tornado", "rocket": "Rocket"}


def rg(t): return 3 / 56.0 if t >= 4800 else G.REGEN[G.ph(t)]     # last OT minute is 3x (live regen measured 3.0/56 there, diag_clock.py)
_CL = {c.lower(): c for c in CARDS}; _CL.update({"thelog": "Log", "xbow": "Xbow"})
def cardn(n): return _CL.get(str(n).lower().replace("-", "").replace("_", "").replace(" ", ""), str(n))
def ccost(c): return G.COST.get(c, 0)


# ------------------------------------------------------------------ compaction
def push_starts(T, el, vm):
    out = []; lh = -10 ** 9; on = False
    for t, e, v in zip(T, el, vm):
        if v >= 7:
            if not on and t - lh >= 80 and e is not None: out.append(t)
            on = True; lh = t
        else: on = False
    return out


def counter_plays(dec):
    """[tick, cost] opponent plays from drops of the public counter between consecutive decisions <= 40 ticks apart."""
    D = [(d[0], d[6]) for d in dec if d[6] is not None]; out = []
    for (ta, a), (tb, b) in zip(D, D[1:]):
        if tb - ta > 40: continue
        drop = min(10.0, a + (tb - ta) * rg(ta)) - b
        if drop >= .75: out.append([tb, int(round(drop))])
    return out


# Body valuation fix (econ2): (1) SIM names in RoyaleAPI key form that the unit-value table does not know (valued at the 0.5
# default before) -> internal names; (2) live AND SIM label spawned units with the PARENT card (a Witch's skeletons are 'Witch',
# 5 elixir each; live max_hp 119 vs 1220): a body is valued uval(card) x min(1, its first-seen hp / the card's largest first-seen
# hp in that match); (3) spell cards whose bodies are all small units: per-unit value.
ALIAS = {"skeleton-barrel": "SkeletonBalloon", "night-witch": "DarkWitch", "barbarian-barrel": "BarbLog", "furnace": "FirespiritHut",
         "zappies": "MiniSparkys", "royal-ghost": "Ghost", "ice-golem": "IceGolemite", "elite-barbarians": "AngryBarbarians",
         "ice-spirit": "IceSpirits", "guards": "SkeletonWarriors", "mother-witch": "MotherWitch", "heal-spirit": "HealSpirit",
         "bandit": "Assassin", "dart-goblin": "BlowdartGoblin", "archers": "Archer", "lumberjack": "AxeMan", "fire-spirit": "FireSpirits",
         "cannon-cart": "MovingCannon", "elixir-collector": "ElixirCollector", "rune-giant": "RuneGiant", "sparky": "ZapMachine",
         "magic-archer": "EliteArcher", "executioner": "Executioner", "flying-machine": "DartBarrell"}
SPELL_UNIT = {"Graveyard": 1 / 3.0, "GoblinBarrel": 1.0}
BODY_FIX = os.environ.get("ECON2_BODY_FIX", "1") == "1"


def vname(n): return ALIAS.get(n, n) if BODY_FIX else n
def bval(n): return SPELL_UNIT[n] if BODY_FIX and n in SPELL_UNIT else G.uval(n)


def compact_bodies(M, src, fam, file, ids=True, opx=(), pl=(), ab=(), dec=(), extra=None):
    S = M["S"]; T = [s[0] for s in S]; el = [None if s[1] is None or s[1] < 0 else round(s[1], 2) for s in S]
    S = [(t, e, [(vname(n), X, Y, hp, i) for n, X, Y, hp, i in b]) for t, e, b in S]
    hp0 = {}; hpmax = collections.Counter()                            # first-seen hp per body, largest per card (spawn fix)
    for t, e, bodies in S:
        for n, X, Y, hp, i in bodies:
            if (i, n) not in hp0: hp0[(i, n)] = hp; hpmax[n] = max(hpmax[n], hp or 0)
    def val(n, i):
        if not BODY_FIX or not hpmax[n] or n in SPELL_UNIT: return bval(n)
        return bval(n) * min(1.0, max(0.0, hp0[(i, n)] or 0) / hpmax[n])
    vm, vt, tk = [], [], []
    first = {}                                                         # (id, card) -> first sighting tick (anywhere)
    dep = []                                                           # first sightings [tick, card, x, y, value] (ids seen >= 2 states)
    occ = collections.Counter((i, n) for t, e, bodies in S for n, X, Y, hp, i in bodies)
    for t, e, bodies in S:
        a = b = mx = 0.0
        for n, X, Y, hp, i in bodies:
            u = val(n, i)
            if Y <= 16: a += u
            else: b += u; mx = max(mx, u)
            if ids and (i, n) not in first:
                first[(i, n)] = t
                if occ[(i, n)] >= 2: dep.append([t, n, round(X, 1), round(Y, 1), round(u, 2)])
        vm.append(round(a, 2)); vt.append(round(b, 2)); tk.append(round(mx, 2))
    DT = [d[0] for d in dec if d[6] is not None]; DV = [d[6] for d in dec if d[6] is not None]
    opp = []
    for t in T:
        k = bisect.bisect_right(DT, t) - 1; opp.append(round(DV[k], 2) if k >= 0 and t - DT[k] <= 40 else None)
    ps = push_starts(T, el, vm); cm = []
    for tp in ps:                                                      # commit = first sighting of the units on my half at tp
        k = T.index(tp)
        c = [first.get((i, n)) for n, X, Y, hp, i in S[k][2] if Y <= 16 and val(n, i) >= .5]
        c = [x for x in c if x is not None and x >= tp - 600]
        cm.append(min(c) if c else None)
    r = dict(src=src, fam=fam, file=file, T=T, el=el, vm=vm, vt=vt, tk=tk, opp=opp, ops=counter_plays(dec), opx=list(opx),
             pl=list(pl), ab=list(ab), ps=ps, cm=cm, end=M["end_tick"], dep=dep)
    r.update(extra or {}); return r


def live_mode():
    fam = {"stack": "barrel2k_cellref.pt", "towerref": "towerref_w2", "r1e": "r1e31"}
    import time
    out = []; now = time.time()
    for f in sorted(glob.glob(G.LOGDIR + "live_play_20261004_2*.jsonl") + glob.glob(G.LOGDIR + "live_play_2026100[5-9]_*.jsonl")):
        if now - os.path.getmtime(f) < 600: continue                   # a match still being played
        with open(f, encoding="utf8", errors="replace") as fh: st = json.loads(fh.readline())
        if st.get("dry_run"): continue
        ck = (st.get("ckpt") or "").replace("\\", "/")
        k = next((k for k, s in fam.items() if ck.endswith(s) or (s in ck and k != "stack")), None)
        if k is None: continue
        M = G.live_match(f)
        if not M: continue
        forced = set()
        with open(f, encoding="utf8", errors="replace") as fh:          # forced (anti-leak) plays by tick
            for l in fh:
                if l.startswith('{"event": "play"') and '"forced": true' in l: forced.add(json.loads(l)["tick"])
        pl = [[t, cardn(n), None if e is None else round(e, 2), t in forced] for t, n, e in M["plays"]]
        out.append(compact_bodies(M, "live", k, M["file"], pl=pl, ab=M["abil"], dec=M["dec"],
                                  extra=dict(al=bool(st.get("anti_leak")), opts=st.get("decision_options") or {})))
        if len(out) % 50 == 0: print(len(out), flush=True)
    save("live", out)


def sim_mode(d, arms):
    for arm in arms:
        out = []; taus = G.TAUS["r1e" if arm.startswith("r1e") else "stack"]
        for s in ("evo", "lad"):
            p = f"{d}/{arm}_{s}/matches.jsonl"
            if not os.path.exists(p): print("missing", p); continue
            for l in open(p):
                try: r = json.loads(l)
                except ValueError: continue
                if r.get("arm") != "plain" or "lr_dec" not in r: continue
                M = G.sim_match(r, taus); side = r["learner_side"]
                el_at = {t: elr for t, p_, play, why, elv, elr, opp in r["lr_dec"] if play}
                pl = [[t, cardn(c), None if el_at.get(t) is None else round(el_at[t], 2), False] for t, c in M["spend"]]
                opx = [[t, G.NCOST.get(G.canon(c), 0), G.canon(c)] for t, s_, c, e, ab in r["behaviour"]["lr_plays"] if s_ != side and not ab]
                out.append(compact_bodies(M, "sim", arm, f"{s}:{r['tag']}", pl=pl, opx=opx, ab=M["abil"], dec=M["dec"],
                                          extra=dict(out=r["outcome"], deck=r.get("opp_deck") or r.get("opp_deck_name"), cen=s, seed=r.get("seed"))))
        save("sim_" + arm, out); print(arm, len(out))


def pros_mode(pkl):
    import pickle
    P = pickle.load(open(pkl, "rb")); out = []
    for m in P:
        F = m["F"]
        if len(F) < 20: continue
        T = [f[0] for f in F]; el = [None if f[1] is None else round(float(f[1]), 2) for f in F]
        vm, vt, tk = [], [], []
        for f in F:
            a = b = mx = 0.0
            for n, X, Y in f[3]:
                u = G.uval(G.canon(n))
                if Y <= 16: a += u
                else: b += u; mx = max(mx, u)
            vm.append(round(a, 2)); vt.append(round(b, 2)); tk.append(round(mx, 2))
        op = sorted(m["op"])
        opx = [[t, int(c or 0), G.canon(n)] for t, n, X, Y, c in op]
        def counter(t):                                                # public counter rebuilt from visible plays, at t (+26 below)
            e, last = 6.0, 0                                           # match start elixir 6 (live raw 8.67 at tick 150)
            for (pt, c, n) in opx:
                if pt > t: break
                e = min(10.0, e + (pt - last) * rg(last)); e = max(0.0, e - c); last = pt
            return min(10.0, e + (t - last) * rg(last))
        opp = [round(counter(t + 26), 2) for t in T]
        pl = [[t - 26, cardn(PRO_CARD.get(n, n)), None if e is None else round(max(0.0, e - 26 * rg(t)), 2), False] for t, n, X, Y, e in sorted(m["me"])]
        ps = push_starts(T, el, vm); cm = []
        for tp in ps:
            k = T.index(tp); names = {G.canon(n) for n, X, Y in F[k][3] if Y <= 16}
            c = [t for t, cost, n in opx if tp - 600 <= t <= tp and n in names]
            cm.append(min(c) if c else None)
        out.append(dict(src="pros", fam="pros", file=m["id"], T=T, el=el, vm=vm, vt=vt, tk=tk, opp=opp, ops=[[t, c] for t, c, n in opx],
                        opx=opx, pl=pl, ab=[t for t, c in m.get("ab", [])], ps=ps, cm=cm, end=m["end"],
                        out="win" if m["win"] else ("draw" if m["draw"] else "loss")))
    save("pros", out)


def save(name, out):
    os.makedirs(DATA, exist_ok=True)
    with gzip.open(DATA + name + ".json.gz", "wt") as fh: json.dump(out, fh)
    print("saved", name, len(out))


def load(name):
    with gzip.open(DATA + name + ".json.gz", "rt") as fh: return json.load(fh)


# ------------------------------------------------------------------ analysis
EB = (0, 2, 4, 6, 8)                     # my elixir buckets 0-1.99 / 2-3.99 / 4-5.99 / 6-7.99 / 8-10
def ebk(e): return 0 if e < 2 else (1 if e < 4 else (2 if e < 6 else (3 if e < 8 else 4)))
def obk(e): return None if e is None else (0 if e < 4 else (1 if e < 7 else 2))
def mean(v): v = [x for x in v if x is not None]; return sum(v) / len(v) if v else None
def med(v): v = sorted(x for x in v if x is not None); return v[len(v) // 2] if v else None


def at(T, t):
    return max(0, bisect.bisect_right(T, t) - 1)


def trigger(vm, vt, tk):
    if vm >= 3: return "my_big"            # >= 3 elixir of enemy bodies on my half
    if vm >= .5: return "my_small"         # a small unit on my half (bait / chip / the push's first body)
    if tk >= 5: return "their_tank"        # nothing on my half, a unit worth >= 5 on theirs (a tank at the back)
    if vt >= .5: return "their_half"
    return "empty"


def window(T, el, vm, vt, tk, pl, ab, ta, tb):
    """Elixir accounting over (ta, tb]: e(tb) = e(ta) + regen - spend - abilities + resid. Spend = my plays whose deduction
    (tap + 26) falls inside; each [card, cost, elixir at tap, board trigger at tap, forced, seconds before tb]."""
    i0, i1 = at(T, ta), at(T, tb)
    if el[i0] is None or el[i1] is None: return None
    regen = waste = 0.0
    for a in range(i0, i1):
        g = (T[a + 1] - T[a]) * rg(T[a])
        if el[a] is not None and el[a] >= 9.9: waste += g
        else: regen += g
    spl = []
    for t, card, e, forced in pl:
        if T[i0] < t + 26 <= T[i1]:
            k = at(T, t); spl.append([card, ccost(card), e, trigger(vm[k], vt[k], tk[k]), forced, round((tb - t) / 20, 1)])
    spend = sum(x[1] for x in spl); nab = sum(1 for a in ab if T[i0] < a <= T[i1])
    return dict(e0=el[i0], e1=el[i1], dur=(T[i1] - T[i0]) / 20, regen=round(regen, 3), waste=round(waste, 3), spend=spend, nab=nab,
                resid=round(el[i1] - (el[i0] + regen - spend - nab), 3), pl=spl)


def analyse(ms):
    """Per-source aggregates for Q1 (selection) and Q2 (window accounting)."""
    H = collections.defaultdict(lambda: [0.0, 0.0, 0.0])        # (phase, opp bucket, my bucket) -> [time weight, push<=3s, push<=5s]
    OH = collections.defaultdict(lambda: [0.0, 0.0, 0.0])       # same strata -> [seconds, opponent plays (counter), big plays >= 5]
    OX = collections.defaultdict(lambda: [0.0, 0.0])            # exact opponent plays -> [seconds, plays]
    elig_el = collections.defaultdict(list)                     # phase -> my elixir over eligible states (time weighted by repeats)
    P = []                                                      # per push rows
    W = collections.defaultdict(float)                          # window spend by (card, trigger)
    WE = collections.defaultdict(float)                         # window spend by elixir-at-tap bucket
    nW = 0; minutes = 0.0
    WS = collections.defaultdict(lambda: [0.0, 0, 0.0]); WN = collections.Counter()   # (phase group, trigger, my bucket) -> [s, taps, cost]
    for m in ms:
        T, el, vm, vt, tk, opp = m["T"], m["el"], m["vm"], m["vt"], m["tk"], m["opp"]
        if len(T) < 50 or any(p[1] not in CARDS for p in m["pl"]): continue      # a hand/deck the icebow cost table does not cover
        minutes += m["end"] / 1200.0
        ps = set(m["ps"]); pst = sorted(ps)
        lh = -10 ** 9
        ops_t = [o[0] for o in m["ops"]]
        for i, t in enumerate(T):
            if vm[i] >= 7: lh = t
            if i + 1 >= len(T) or el[i] is None: continue
            w = min(T[i + 1] - t, 30) / 10.0; ob = obk(opp[i]); p = G.pidx(t)
            # opponent play hazard (all states; counter-derived plays in (t, t_next])
            if ob is not None:
                c = OH[(p, ob, ebk(el[i]))]; c[0] += w / 2.0
                j = bisect.bisect_right(ops_t, t); k = bisect.bisect_right(ops_t, T[i + 1])
                c[1] += k - j; c[2] += sum(1 for o in m["ops"][j:k] if o[1] >= 5)
            if vm[i] >= 7 or t - lh < 80 or t > m["end"] - 100 or ob is None: continue
            k = bisect.bisect_right(pst, t)
            nxt = pst[k] if k < len(pst) else 10 ** 9
            c = H[(p, ob, ebk(el[i]))]; c[0] += w; c[1] += w * (nxt - t <= 60); c[2] += w * (nxt - t <= 100)
            elig_el[p].append((el[i], w))
        if m.get("opx"):
            ox = [o[0] for o in m["opx"]]
            for i, t in enumerate(T[:-1]):
                if el[i] is None: continue
                c = OX[(G.pidx(t), ebk(el[i]))]; c[0] += min(T[i + 1] - t, 30) / 20.0
                c[1] += bisect.bisect_right(ox, T[i + 1]) - bisect.bisect_right(ox, t)
        # pushes
        pl = m["pl"]; ab = m["ab"]
        for tp, tc in zip(m["ps"], m["cm"]):
            i = T.index(tp); row = dict(ph=G.pidx(tp), el=el[i], opp=opp[i], v=vm[i], fam=m["fam"], al=m.get("al", False))
            if tc is not None:
                j = at(T, tc - 1); row.update(tc=(tp - tc) / 20.0, el_c=el[j], opp_c=opp[j])
            for wn, ta in (("w15", tp - 300 if tp >= 300 else None), ("wc", tc)):
                if ta is None: continue
                acc = window(T, el, vm, vt, tk, pl, ab, ta, tp)
                if acc is None: continue
                row[wn] = acc
                if wn == "w15":
                    nW += 1; g = 0 if row["ph"] == 0 else 1; WN[g] += 1
                    i0 = at(T, ta)
                    for a in range(i0, i):                              # time per stratum inside the window
                        if el[a] is None: continue
                        WS[(g, trigger(vm[a], vt[a], tk[a]), ebk(el[a]))][0] += (T[a + 1] - T[a]) / 20.0
                    for t, card, e, forced in pl:                       # taps inside the window, stratum at the tap
                        if ta < t <= tp and e is not None:
                            k = at(T, t); c = WS[(g, trigger(vm[k], vt[k], tk[k]), ebk(el[k] if el[k] is not None else e))]; c[1] += 1; c[2] += ccost(card)
                    for card, cost, e, trig, forced, dt in acc["pl"]:
                        W[(card, trig)] += cost; W[("ALL", trig)] += cost; W[(card, "ALL")] += cost
                        if forced: W[("FORCED", "ALL")] += cost
                        WE[ebk(e) if e is not None else -1] += cost
            P.append(row)
    return dict(H={"|".join(map(str, k)): v for k, v in H.items()}, OH={"|".join(map(str, k)): v for k, v in OH.items()},
                OX={"|".join(map(str, k)): v for k, v in OX.items()},
                elig={str(p): [round(sum(e * w for e, w in v) / sum(w for e, w in v), 3), round(sum(w for e, w in v), 1)] for p, v in elig_el.items()},
                P=P, W={"|".join(k): v / max(1, nW) for k, v in W.items()}, WE={str(k): v / max(1, nW) for k, v in WE.items()},
                nW=nW, n=len(ms), minutes=minutes, WS={"|".join(map(str, k)): v for k, v in WS.items()}, WN={str(k): v for k, v in WN.items()})


def hazard_table(H, idx):
    """{(phase, opp bucket, my bucket): rate}: pooled over phase and opp bucket with a given weight set."""
    out = {}
    for k, v in H.items():
        p, o, e = map(int, k.split("|")); out[(p, o, e)] = v
    return out


def standardised(A, W, col, base_col=0):
    """rate per my-elixir bucket, strata (phase, opp bucket) weighted by W = {(p, o): weight}."""
    cells = hazard_table(A, None); res = []
    for e in range(5):
        num = den = 0.0
        for (p, o), w in W.items():
            c = cells.get((p, o, e))
            if c and c[base_col] > 20: num += w * c[col] / c[base_col]; den += w
        res.append(None if den == 0 else num / den)
    return res


def report(names):
    R = {}
    for n in names:
        if not os.path.exists(DATA + n + ".json.gz"): print("missing", n); continue
        ms = load(n)
        if n == "live":                                   # split by family; anti-leak ON matches marked
            R["live_all"] = analyse(ms)
            for f in ("stack", "towerref", "r1e"): R["live_" + f] = analyse([m for m in ms if m["fam"] == f and not m.get("al")])
        else: R[n] = analyse(ms)
    json.dump(R, open(HERE + "econ2_" + "_".join(names) + ".json", "w"))
    return R


def f2(x, d=2): return "  n/a" if x is None else f"{x:.{d}f}"


def boot(a, b, fn=mean, B=1000, seed=3):
    import random
    rng = random.Random(seed); d = []
    for _ in range(B):
        d.append(fn([a[rng.randrange(len(a))] for _ in a]) - fn([b[rng.randrange(len(b))] for _ in b]))
    d.sort(); return fn(a) - fn(b), d[int(.025 * B)], d[int(.975 * B)]


def tables(R, ref="live_all", srcs=None):
    srcs = srcs or list(R)
    # strata weights: the reference's eligible time by (phase, opp bucket)
    W = collections.Counter()
    for k, v in R[ref]["H"].items():
        p, o, e = map(int, k.split("|")); W[(p, o)] += v[0]
    WO = collections.Counter()
    for k, v in R[ref]["OH"].items():
        p, o, e = map(int, k.split("|")); WO[(p, o)] += v[0]
    print(f"\n## Q1a  P(push starts within 3 s | 5 s) by MY elixir, eligible states (no push in the last 4 s); strata phase x opponent counter, weighted to {ref}")
    print("| source | n | " + " | ".join(f"{lo}-{lo + 2}" for lo in EB) + " | 0-4 / 6-10 ratio (5 s) |")
    for s in srcs:
        h3 = standardised(R[s]["H"], W, 1); h5 = standardised(R[s]["H"], W, 2)
        lo = mean(h5[:2]); hi = mean(h5[3:])
        print(f"| {s} | {R[s]['n']} | " + " | ".join(f"{f2(100 * a if a is not None else None, 1)}% / {f2(100 * b if b is not None else None, 1)}%" for a, b in zip(h3, h5))
              + f" | {f2(lo / hi if lo and hi else None)} |")
    print(f"\n## Q1b  opponent plays per second (public counter drops) | big plays (>= 5) by MY elixir; strata phase x counter, weighted to {ref}")
    for s in srcs:
        a = standardised(R[s]["OH"], WO, 1); b = standardised(R[s]["OH"], WO, 2)
        print(f"| {s} | " + " | ".join(f"{f2(x, 3)} / {f2(y, 3)}" for x, y in zip(a, b)) + f" | ratio 0-4/6-10 all {f2(mean(a[:2]) / mean(a[3:]) if a[0] else None)} big {f2(mean(b[:2]) / mean(b[3:]) if b[0] and mean(b[3:]) else None)} |")
    print("\n## Q1b'  exact opponent plays per second by MY elixir (no strata; SIM engine log / pro log)")
    for s in srcs:
        if not R[s]["OX"]: continue
        c = collections.defaultdict(lambda: [0.0, 0.0])
        for k, v in R[s]["OX"].items():
            p, e = map(int, k.split("|")); c[e][0] += v[0]; c[e][1] += v[1]
        print(f"| {s} | " + " | ".join(f2(c[e][1] / c[e][0] if c[e][0] else None, 3) for e in range(5)) + " |")
    print("\n## Q1c  selection decomposition (means): my elixir over eligible time (weighted to the push phase mix) -> at the opponent's commit (first sighting of the push's units) -> at push start; opponent counter (+26 forecast)")
    print("| source | pushes | eligible-time mean | at commit | at push start | timing (commit - time) | reaction (push - commit) | commit lead s (median) | opp counter at commit / push start | my - opp at push start |")
    for s in srcs:
        P = R[s]["P"]; ph = collections.Counter(r["ph"] for r in P)
        el_t = sum(ph[p] * R[s]["elig"][str(p)][0] for p in ph if str(p) in R[s]["elig"]) / max(1, sum(ph[p] for p in ph if str(p) in R[s]["elig"]))
        Pc = [r for r in P if r.get("el_c") is not None and r["el"] is not None]
        ec = mean([r["el_c"] for r in Pc]); ep = mean([r["el"] for r in Pc])
        print(f"| {s} | {len(P)} ({len(Pc)} with commit) | {f2(el_t)} | {f2(ec)} | {f2(ep)} | {f2(ec - el_t)} | {f2(ep - ec)} | {f2(med([r['tc'] for r in Pc]), 1)} | "
              f"{f2(mean([r['opp_c'] for r in Pc]))} / {f2(mean([r['opp'] for r in P]))} | {f2(mean([r['el'] - r['opp'] for r in P if r['el'] is not None and r['opp'] is not None]))} |")
    for wn, lab in (("w15", "15 s before the push"), ("wc", "opponent commit -> push start")):
        print(f"\n## Q2  {lab}: elixir accounting, means per push, by phase of the push. e(end) = e(start) + regen - spend - abilities + resid")
        print("| source | phase | pushes | window s | e(start) | regen | wasted | spend | plays | abilities | e(push) | resid |")
        for s in srcs:
            for ph in ((0,), (1, 2)):
                P = [r[wn] for r in R[s]["P"] if wn in r and r["ph"] in ph]
                print(f"| {s} | {'1x' if ph == (0,) else '2x+OT'} | {len(P)} | " + " | ".join(f2(mean([r[k] for r in P])) for k in ("dur", "e0", "regen", "waste", "spend")) + " | "
                      + f2(mean([len(r['pl']) for r in P])) + " | " + " | ".join(f2(mean([r[k] for r in P])) for k in ("nab", "e1", "resid")) + " |")
    trig = ("my_big", "my_small", "their_tank", "their_half", "empty")
    for wn in ("w15", "wc"):
        print(f"\n## Q2b  [{wn}] spend per push by board state at the tap | by card | by elixir at the tap (0-2/2-4/4-6/6-8/8-10). my_big = >= 3 elixir of enemy on my half; my_small = .5-3 on my half; their_tank = none on mine, a unit >= 5 on theirs; their_half; empty")
        print("| source | phase | " + " | ".join(trig) + " | " + " | ".join(CARDS) + " | " + " | ".join(f"e{lo}" for lo in EB) + " |")
        for s in srcs:
            for ph in ((0,), (1, 2)):
                P = [r[wn] for r in R[s]["P"] if wn in r and r["ph"] in ph]; n = max(1, len(P))
                c = collections.Counter()
                for r in P:
                    for card, cost, e, tg, forced, dt in r["pl"]:
                        c[tg] += cost; c[card] += cost; c[f"e{ebk(e) if e is not None else 9}"] += cost
                print(f"| {s} | {'1x' if ph == (0,) else '2x+OT'} | " + " | ".join(f2(c[t] / n) for t in trig) + " | " + " | ".join(f2(c[k] / n) for k in CARDS)
                      + " | " + " | ".join(f2(c[f'e{k}'] / n) for k in range(5)) + " |")


def pressure(ms):
    """Q3 calibration metrics, identical for live / SIM / pros (all from the compact format; public information only)."""
    t1 = tall = 0.0; P1 = []; Pall = []; lead = []; vm_s = b8 = v3 = vm_int = tkb = 0.0; ops = 0; el_t = cap = 0.0; outs = collections.Counter()
    tim = []
    for m in ms:
        T, el, vm, vt = m["T"], m["el"], m["vm"], m["vt"]
        if len(T) < 50 or any(p[1] not in CARDS for p in m["pl"]): continue
        outs[m.get("out")] += 1; ops += len(m["ops"])
        for i in range(len(T) - 1):
            dt = min(T[i + 1] - T[i], 30) / 20.0; tall += dt; t1 += dt * (T[i] < 2400)
            vm_int += dt * vm[i]; v3 += dt * (vm[i] >= 3); b8 += dt * (vm[i] + vt[i] >= 8); tkb += dt * (vm[i] < .5 and m["tk"][i] >= 5)
            if el[i] is not None: el_t += dt * el[i]; cap += dt * (el[i] >= 9.9)
        for tp, tc in zip(m["ps"], m["cm"]):
            k = T.index(tp); Pall.append((el[k], vm[k]))
            if tp < 2400: P1.append(el[k])
            if tc is not None: lead.append((tp - tc) / 20.0)
    n = sum(outs.values()); mins = tall / 60.0
    return dict(n=n, win=outs.get("win", 0) + outs.get("WIN", 0), draw=outs.get("draw", 0) + outs.get("DRAW", 0), outs=dict(outs),
                push_pm=len(Pall) / mins, push_pm_1x=len(P1) / (t1 / 60.0), push_v=mean([v for e, v in Pall]), lead=med(lead),
                vm_mean=vm_int / tall, t_vm3=v3 / tall, t_tank=tkb / tall, t_board8=b8 / tall, opp_pm=ops / mins, el_push=mean([e for e, v in Pall]),
                el_push_med=med([e for e, v in Pall]), el_push_1x=mean(P1), el_mean=el_t / tall, t_cap=cap / tall, minutes=mins / max(1, n))


CAL_KEYS = ("push_pm", "push_pm_1x", "push_v", "lead", "vm_mean", "t_vm3", "t_board8", "t_tank")


def calib_table(names):
    print("\n## Q3  opponent pressure and my economy (same definitions everywhere; distance = mean |relative error| vs live_all over " + ", ".join(CAL_KEYS) + ")")
    print("| source | matches | wins | pushes/min (1x) | push value | commit lead s | enemy value on my half (mean) | time vm>=3 | time board>=8 | time tank at back only | opp plays/min | my elixir mean | time at cap | push-start elixir mean / median / 1x | distance |")
    out = {}
    for n in names:
        n, _, cen = n.partition("#")                     # name#lad = one opponent census only
        n, _, cut = n.partition("@")                     # name@120 = seeds < 120 only (the screening arms' seed range)
        ms = [m for m in load(n) if (not cut or m.get("seed") is None or m["seed"] < int(cut)) and (not cen or m.get("cen") == cen)]
        groups = {n + ("#" + cen if cen else ""): ms} if n != "live" else {"live_all": ms, "live_towerref": [m for m in ms if m["fam"] == "towerref" and not m.get("al")],
                                                "live_r1e": [m for m in ms if m["fam"] == "r1e"]}
        for g, x in groups.items():
            r = pressure(x); out[g] = r
            ref = out.get("live_all")                 # calibration distance: mean |relative error| vs live_all on the pressure metrics
            d = mean([abs(r[k] / ref[k] - 1) for k in CAL_KEYS]) if ref and g != "live_all" else None
            print(f"| {g} | {r['n']} | {r['win']} | {f2(r['push_pm'])} ({f2(r['push_pm_1x'])}) | {f2(r['push_v'], 1)} | {f2(r['lead'], 1)} | {f2(r['vm_mean'])} | {f2(100 * r['t_vm3'], 1)}% | "
                  f"{f2(100 * r['t_board8'], 1)}% | {f2(100 * r['t_tank'], 1)}% | {f2(r['opp_pm'], 1)} | {f2(r['el_mean'])} | {f2(100 * r['t_cap'], 1)}% | {f2(r['el_push'])} / {f2(r['el_push_med'])} / {f2(r['el_push_1x'])} | {f2(d, 3)} |")
    json.dump(out, open(HERE + "calib_" + "_".join(names)[:80].replace("@", "-") + ".json", "w"), indent=1)


def deploys(names):
    """Where enemy bodies first appear (own frame y): elixir value per minute by band, 1x only (both sides reach 2x at different rates)."""
    bands = ((0, 16, "my half"), (16, 20, "their bridge 16-20"), (20, 26, "their mid 20-26"), (26, 33, "their back >= 26"))
    print("\n## Q3b  enemy body value first seen per 1x minute by own-frame y band (spawned units included)")
    print("| source | matches | " + " | ".join(b[2] for b in bands) + " | total |")
    for n in names:
        n, _, cut = n.partition("@")
        ms = [m for m in load(n) if (not cut or m.get("seed") is None or m["seed"] < int(cut)) and not any(p[1] not in CARDS for p in m["pl"])]
        groups = {n: ms} if n != "live" else {"live_all": ms, "live_towerref": [m for m in ms if m["fam"] == "towerref" and not m.get("al")]}
        for g, x in groups.items():
            v = collections.Counter(); mins = sum(min(m["end"], 2400) for m in x) / 1200.0
            for m in x:
                for d in m.get("dep", []):
                    t, c, X, Y = d[:4]
                    if t < 2400:
                        for lo, hi, lab in bands:
                            if lo <= Y < hi: v[lab] += d[4] if len(d) > 4 else G.uval(c)
            print(f"| {g} | {len(x)} | " + " | ".join(f2(v[b[2]] / mins, 1) for b in bands) + f" | {f2(sum(v.values()) / mins, 1)} |")


def dep_cards(a, b, top=25):
    """First-seen enemy body value per 1x minute by card, two sources, largest differences first."""
    def tab(n):
        n, _, cut = n.partition("@")
        ms = [m for m in load(n) if (not cut or m.get("seed") is None or m["seed"] < int(cut)) and not any(p[1] not in CARDS for p in m["pl"])]
        mins = sum(min(m["end"], 2400) for m in ms) / 1200.0; v = collections.Counter(); c = collections.Counter()
        for m in ms:
            for x in m.get("dep", []):
                t, card, X, Y = x[:4]
                if t < 2400: v[card] += (x[4] if len(x) > 4 else G.uval(card)) / mins; c[card] += 1 / mins
        return v, c
    (va, ca), (vb, cb) = tab(a), tab(b)
    print(f"\n## Q3c  first-seen enemy body value per 1x minute by card: {a} vs {b} (bodies per minute in brackets)")
    for k in sorted(set(va) | set(vb), key=lambda k: -abs(va[k] - vb[k]))[:top]:
        print(f"| {k} | {va[k]:.2f} ({ca[k]:.2f}) | {vb[k]:.2f} ({cb[k]:.2f}) | {va[k] - vb[k]:+.2f} |")


def hz_cells(ms):
    """Whole match: (phase 0/1/2, board trigger, my elixir bucket) -> [seconds, taps, elixir spent]."""
    C = collections.defaultdict(lambda: [0.0, 0, 0.0])
    for m in ms:
        T, el, vm, vt, tk = m["T"], m["el"], m["vm"], m["vt"], m["tk"]
        if len(T) < 50 or any(p[1] not in CARDS for p in m["pl"]): continue
        for i in range(len(T) - 1):
            if el[i] is not None: C[(G.pidx(T[i]), trigger(vm[i], vt[i], tk[i]), ebk(el[i]))][0] += min(T[i + 1] - T[i], 30) / 20.0
        for t, card, e, forced in m["pl"]:
            k = at(T, t)
            if e is not None: c = C[(G.pidx(t), trigger(vm[k], vt[k], tk[k]), ebk(e))]; c[1] += 1; c[2] += ccost(card)
    return C


def hazard(pairs_):
    """Per my-elixir bucket: share of time, taps per second and elixir per tap, live vs SIM with SIM re-weighted to live's
    (phase x board trigger) time mix inside each bucket; then the mean-elixir and spend-rate consequences."""
    for a, b in pairs_:
        A = hz_cells(load_named(a)); B = hz_cells(load_named(b))
        print(f"\n## H  {a} vs {b}: whole-match tap hazard by my elixir (taps/s, SIM matched to live's phase x board mix within the bucket) | elixir per tap | share of time")
        TA = sum(v[0] for v in A.values()); TB = sum(v[0] for v in B.values())
        for e in range(5):
            ka = {k: v for k, v in A.items() if k[2] == e}; ta = sum(v[0] for v in ka.values())
            ha = sum(v[1] for v in ka.values()) / ta if ta else None
            num = den = 0.0
            for k, v in ka.items():
                w = B.get(k)
                if w and w[0] > 5: num += v[0] * w[1] / w[0]; den += v[0]
            hb = num / den if den else None
            hb_raw = sum(v[1] for k, v in B.items() if k[2] == e) / max(1e-9, sum(v[0] for k, v in B.items() if k[2] == e))
            ca = sum(v[2] for v in ka.values()) / max(1, sum(v[1] for v in ka.values()))
            cb = sum(v[2] for k, v in B.items() if k[2] == e) / max(1, sum(v[1] for k, v in B.items() if k[2] == e))
            print(f"| {EB[e]}-{EB[e] + 2} | {f2(ha, 3)} / {f2(hb, 3)} (SIM raw {hb_raw:.3f}) | {ca:.2f} / {cb:.2f} | {100 * ta / TA:.1f}% / {100 * sum(v[0] for k, v in B.items() if k[2] == e) / TB:.1f}% |")
        mix = collections.Counter(); mixb = collections.Counter()
        for k, v in A.items(): mix[(k[0], k[1])] += v[0] / TA
        for k, v in B.items(): mixb[(k[0], k[1])] += v[0] / TB
        print("board-state time mix live vs SIM: " + ", ".join(f"{t} {100 * sum(v for k, v in mix.items() if k[1] == t):.1f}%/{100 * sum(v for k, v in mixb.items() if k[1] == t):.1f}%" for t in TRIG))


def load_named(n):
    n, _, cut = n.partition("@")
    if n.startswith("live_"):
        f = n[5:]; return [m for m in load("live") if (f == "all" or m["fam"] == f) and not m.get("al")]
    return [m for m in load(n) if not cut or m.get("seed") is None or m["seed"] < int(cut)]


def paired(a, b, cut=None):
    """Paired outcomes of two SIM arms on (census, seed): score 1 / .5 / 0, better / worse counts, two-sided sign test."""
    sc = {"win": 1.0, "draw": .5, "loss": 0.0}
    A = {(m["cen"], m["seed"]): sc.get(m["out"], .5) for m in load(a) if cut is None or m["seed"] < cut}
    B = {(m["cen"], m["seed"]): sc.get(m["out"], .5) for m in load(b) if cut is None or m["seed"] < cut}
    k = sorted(set(A) & set(B)); bt = sum(A[x] > B[x] for x in k); wr = sum(A[x] < B[x] for x in k)
    n = bt + wr; p = min(1.0, 2 * sum(math.comb(n, i) for i in range(0, min(bt, wr) + 1)) / 2 ** n) if n else 1.0
    print(f"paired {a} vs {b}: n={len(k)} score {sum(A[x] for x in k)} vs {sum(B[x] for x in k)}; better {bt} / worse {wr}; sign p {p:.3f}")
    return dict(n=len(k), a=sum(A[x] for x in k), b=sum(B[x] for x in k), better=bt, worse=wr, p=p)


TRIG = ("my_big", "my_small", "their_tank", "their_half", "empty")


def card_trig(R, srcs, wn="w15"):
    print(f"\n## Q2d  [{wn}] spend per push by card within each board state (elixir per push; columns = cards {', '.join(CARDS)})")
    for tg in TRIG:
        for s in srcs:
            for ph in ((0,), (1, 2)):
                P = [r[wn] for r in R[s]["P"] if wn in r and r["ph"] in ph]; n = max(1, len(P)); c = collections.Counter()
                for r in P:
                    for card, cost, e, t, forced, dt in r["pl"]:
                        if t == tg: c[card] += cost
                print(f"| {tg} | {s} | {'1x' if ph == (0,) else '2x+OT'} | " + " | ".join(f2(c[k] / n) for k in CARDS) + f" | {f2(sum(c.values()) / n)} |")


def pairs(R, PRS):
    print("\n## P1  per phase: my elixir over eligible time -> at the opponent's commit -> at push start (means; live - SIM with 95% bootstrap CI over pushes)")
    print("| pair | phase | pushes L/S | time mean L/S | at commit L/S | at push L/S | commit lead s L/S (median) | d commit [CI] | d reaction [CI] | d push [CI] |")
    for a, b in PRS:
        for ph in ((0,), (1, 2)):
            def rows(s): return [r for r in R[s]["P"] if r["ph"] in ph and r.get("el_c") is not None and r["el"] is not None]
            A, B = rows(a), rows(b)
            def tm(s): return mean([R[s]["elig"][str(p)][0] for p in ph if str(p) in R[s]["elig"]])
            dc = boot([r["el_c"] for r in A], [r["el_c"] for r in B]); dr = boot([r["el"] - r["el_c"] for r in A], [r["el"] - r["el_c"] for r in B])
            dp = boot([r["el"] for r in A], [r["el"] for r in B])
            print(f"| {a} vs {b} | {'1x' if ph == (0,) else '2x+OT'} | {len(A)}/{len(B)} | {f2(tm(a))}/{f2(tm(b))} | {f2(mean([r['el_c'] for r in A]))}/{f2(mean([r['el_c'] for r in B]))} | "
                  f"{f2(mean([r['el'] for r in A]))}/{f2(mean([r['el'] for r in B]))} | {f2(med([r['tc'] for r in A]), 1)}/{f2(med([r['tc'] for r in B]), 1)} | "
                  + " | ".join(f"{d[0]:+.2f} [{d[1]:+.2f}, {d[2]:+.2f}]" for d in (dc, dr, dp)) + " |")
    print("\n## P2  15 s before a push, by board state at the moment: seconds per push in it, spend rate (elixir/s), spend per push; live - SIM spend split into board-time mix vs spend rate (Shapley over trigger x my-elixir cells)")
    print("| pair | phase | state | s/push L/S | elixir/s L/S | spend/push L/S | d spend | from board-time mix | from spend rate |")
    for a, b in PRS:
        for g in (0, 1):
            na, nb = R[a]["WN"].get(str(g), 0), R[b]["WN"].get(str(g), 0)
            if not na or not nb: continue
            def cells(s, n):
                out = {}
                for k, v in R[s]["WS"].items():
                    gg, tg, e = k.split("|")
                    if int(gg) == g: out[(tg, int(e))] = (v[0] / n, v[2] / v[0] if v[0] > 0 else 0.0)
                return out
            CA, CB = cells(a, na), cells(b, nb)
            tot = [0.0, 0.0, 0.0]
            for tg in TRIG + ("ALL",):
                ks = [k for k in set(CA) | set(CB) if tg in ("ALL", k[0])]
                ta = sum(CA.get(k, (0, 0))[0] for k in ks); tb = sum(CB.get(k, (0, 0))[0] for k in ks)
                sa = sum(CA.get(k, (0, 0))[0] * CA.get(k, (0, 0))[1] for k in ks); sb = sum(CB.get(k, (0, 0))[0] * CB.get(k, (0, 0))[1] for k in ks)
                mix = sum((CA.get(k, (0, 0))[0] - CB.get(k, (0, 0))[0]) * (CA.get(k, (0, 0))[1] + CB.get(k, (0, 0))[1]) / 2 for k in ks)
                rate = sum((CA.get(k, (0, 0))[1] - CB.get(k, (0, 0))[1]) * (CA.get(k, (0, 0))[0] + CB.get(k, (0, 0))[0]) / 2 for k in ks)
                print(f"| {a} vs {b} | {'1x' if g == 0 else '2x+OT'} | {tg} | {f2(ta, 1)}/{f2(tb, 1)} | {f2(sa / ta if ta else None)}/{f2(sb / tb if tb else None)} | {f2(sa)}/{f2(sb)} | {sa - sb:+.2f} | {mix:+.2f} | {rate:+.2f} |")


def selftest():
    """Synthetic check of push detection, trigger labels and the window identity (python econ2.py selftest)."""
    T = list(range(0, 600, 10)); vm = [0.0] * 30 + [8.0] * 5 + [0.0] * 25
    el = [min(10.0, 5 + t / 56) for t in T]
    assert push_starts(T, el, vm) == [300]
    assert trigger(4, 0, 0) == "my_big" and trigger(0, 6, 6) == "their_tank" and trigger(0, 0, 0) == "empty"
    el2 = [1 + t / 56 - (3 if t >= 226 else 0) for t in T]                      # a 3-elixir play tapped at 200, deducted at 226 (no cap)
    w = window(T, el2, vm, [0.0] * len(T), [0.0] * len(T), [[200, "Knight", 8.6, False]], [], 100, 300)
    assert w["spend"] == 3 and abs(w["resid"]) < 1e-6, w
    print("selftest ok")


if __name__ == "__main__":
    G.load_catalog()
    mode = sys.argv[1]
    if mode == "selftest": selftest()
    if mode == "live": live_mode()
    elif mode == "sim": sim_mode(sys.argv[2], sys.argv[3:])
    elif mode == "pros": pros_mode(sys.argv[2])
    elif mode == "calib": calib_table(sys.argv[2:])
    elif mode == "deploys": deploys(sys.argv[2:])
    elif mode == "hazard": hazard([a.split(":") for a in sys.argv[2:]])
    elif mode == "depcards": dep_cards(sys.argv[2], sys.argv[3])
    elif mode == "paired": paired(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else None)
    elif mode == "report":
        R = report(sys.argv[2:]); tables(R)
        PRS = [(x, y) for x, y in (("live_r1e", "sim_r1e"), ("live_towerref", "sim_de10"), ("live_stack", "sim_stack"), ("pros", "sim_de10")) if x in R and y in R]
        pairs(R, PRS); card_trig(R, [s for s in ("live_r1e", "sim_r1e", "live_towerref", "sim_de10") if s in R])
