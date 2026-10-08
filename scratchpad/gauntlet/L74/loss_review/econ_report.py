"""econ_gap.md from econ_live_<fam>.json (local) + econ_sim_<arm>.json (copied back from the VM). See econ_gap.py for definitions."""
import json, os, math, itertools, statistics, collections, datetime
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
PH = ("1x", "2x", "OT")


def load(name):
    p = HERE + name
    return json.load(open(p)) if os.path.exists(p) else None


def med(v): return statistics.median(v) if v else float("nan")
def mean(v): return sum(v) / len(v) if v else float("nan")
def f2(x, d=2): return "n/a" if x is None or x != x else f"{x:.{d}f}"
def pc(x, d=0): return "n/a" if x is None or x != x else f"{100 * x:.{d}f}%"


def boot_med_diff(a, b, B=1000, seed=3):
    import random
    rng = random.Random(seed); d = []
    for _ in range(B):
        d.append(med([a[rng.randrange(len(a))] for _ in a]) - med([b[rng.randrange(len(b))] for _ in b]))
    d.sort(); return med(a) - med(b), d[int(.025 * B)], d[int(.975 * B)]


def cells(A, key):
    out = collections.Counter()
    for k, v in A[key].items():
        p, pb, e = map(int, k.split("|")); out[(p, pb, e)] += v
    return out


def lo_rate(occ, taps, minutes, lo=5):
    """taps at < lo elixir per minute = 60 * sum_(s,e<lo) time(s,e)/T * taps(s,e)/time(s,e)."""
    return sum(v for (p, pb, e), v in taps.items() if e < lo) / minutes


def factors(A):
    """(w[s], occ[s][e], h[s][e]) with s = (phase, pb). h = taps per second; thin cells fall back to the phase x elixir hazard."""
    occ, taps = cells(A, "occ"), cells(A, "taps")
    T = sum(occ.values()); w = collections.Counter(); o = collections.defaultdict(dict); h = collections.defaultdict(dict)
    pool_t = collections.Counter(); pool_n = collections.Counter()
    for (p, pb, e), t in occ.items(): pool_t[(p, e)] += t; pool_n[(p, e)] += taps.get((p, pb, e), 0)
    for (p, pb, e), t in occ.items(): w[(p, pb)] += t / T
    for (p, pb, e), t in occ.items():
        s = (p, pb); o[s][e] = t / (w[s] * T)
        h[s][e] = taps.get((p, pb, e), 0) / t if t >= 5 else (pool_n[(p, e)] / pool_t[(p, e)] if pool_t[(p, e)] else 0.0)
    return w, o, h, T


def rate(w, o, h, hs, lo=5, only=None):
    """taps/min at < lo elixir from factors; h falls back to hs (other source) where h lacks the cell."""
    tot = 0.0
    for s, ws in w.items():
        if only and not only(s): continue
        for e, oe in o.get(s, {}).items():
            if e >= lo: continue
            he = h.get(s, {}).get(e)
            if he is None: he = hs.get(s, {}).get(e, 0.0)
            tot += ws * oe * he
    return 60 * tot


def shapley(live, sim, lo=5, only=None):
    """Shapley split of rate(live) - rate(sim) over the three factors (pressure mix w, elixir occupancy o, hazard h)."""
    L, S_ = live, sim; names = ("pressure mix", "elixir occupancy", "play hazard")
    def f(mask):
        w = L[0] if mask[0] else S_[0]; o = L[1] if mask[1] else S_[1]; h = L[2] if mask[2] else S_[2]
        return rate(w, o, h, S_[2] if mask[2] else L[2], lo, only)
    out = {}
    for i in range(3):
        tot = 0.0
        for perm in itertools.permutations(range(3)):
            k = perm.index(i); before = [0, 0, 0]
            for j in perm[:k]: before[j] = 1
            after = list(before); after[i] = 1
            tot += f(after) - f(before)
        out[names[i]] = tot / 6
    return f((1, 1, 1)), f((0, 0, 0)), out


def gate_match(L, S_, lo=5, pbs=(0, 1, 2, 3)):
    """mean p and P(p > tau) in the SAME (phase, pb, model-elixir) strata, weighted by live decisions, elixir < lo."""
    a = b = c = d = n = 0.0
    for k, v in L["dec"].items():
        p, pb, e = map(int, k.split("|"))
        if e >= lo or pb not in pbs or k not in S_["dec"] or v[0] < 5 or S_["dec"][k][0] < 5: continue
        s = S_["dec"][k]
        a += v[1]; b += v[2]; c += s[1] / s[0] * v[0]; d += s[2] / s[0] * v[0]; n += v[0]
    return (a / n, c / n, b / n, d / n, n) if n else (float("nan"),) * 5


def dp_med(A, pb):
    h = collections.Counter()
    for k, v in A["dp"].items():
        b, x = map(int, k.split("|"))
        if b == pb: h[x] += v
    tot = sum(h.values()); acc = 0
    for x in sorted(h):
        acc += h[x]
        if acc >= tot / 2: return x * .02
    return float("nan")


def summary_row(name, A):
    m = A["minutes"]
    return (f"| {name} | {int(A['n'])} | {f2(med(A['push_el']), 1)} | {pc(mean([x < 4 for x in A['push_el']]))} | "
            f"{f2(len(A['push_el']) / m)} | {f2(mean(A['push_v']), 1)} | "
            + f2(A.get('arrive_1x', 0) / max(1e-9, A.get('min_1x', 0)), 1) + " | "
            + f"{f2(lo_rate(None, cells(A, 'taps'), m))} | {f2(sum(cells(A, 'taps').values()) / m, 1)} | "
            + " / ".join(f2(mean(A['deploy_' + p]), 2) for p in PH) + f" | {f2(A['abil'] / m)} | {f2(mean(A['push_spent10']), 1)} | {f2(A.get('forced', 0) / m)} |")


def write():
    LV = {k: load(f"econ_live_{k}.json") for k in ("stack", "towerref", "r1e", "stack_al1", "stack_al0")}
    SM = {k: load(f"econ_sim_{k}.json") for k in ("stack", "stack_bias", "r1e", "de10", "de4")}
    L = []; P = L.append
    P(f"# Live vs SIM economy gap (L74 econ_gap) -- {datetime.datetime.now():%Y-%m-%d %H:%M}")
    P("")
    P("Same checkpoint + decision options in both. SIM = v3 benchmark (vs gen v1 sampling T .3, the W4 benchmark), 480 matches per arm, "
      "isolated VM repo (econ_sim_patch.py adds a decision/frame dump and an opponent-counter bias knob; nothing else changes). "
      "Live = decision logs of that family. Definitions in econ_gap.py; pressure = enemy body value on my half (own y <= 16).")
    P("")
    gap_at = len(L)
    P("## 1. The gap")
    P("")
    P("| source | matches | elixir at push start (median) | pushes met < 4 | pushes/min | push value | enemy value arriving on my half /min (1x) | taps at < 5 elixir /min | taps /min | elixir at deploy 1x / 2x / OT | IW ability /min | my spend in 10 s before push | forced (anti-leak) plays /min |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for nm, A in (("LIVE stack2k_cellref", LV["stack"]), ("  LIVE stack2k anti-leak ON", LV["stack_al1"]), ("  LIVE stack2k anti-leak OFF", LV["stack_al0"]), ("SIM stack2k_cellref", SM["stack"]), ("SIM stack + counter +0.34", SM["stack_bias"]),
                  ("LIVE R1e", LV["r1e"]), ("SIM R1e", SM["r1e"]), ("LIVE towerref_w2", LV["towerref"])):
        if A: P(summary_row(nm, A))
    P("")
    P("Arrival per minute is shown for 1x only (both sides of the comparison reach 2x/OT at different rates). 'taps' = my card plays at the decision tick "
      "(live: the tap; SIM: the decision before the 26-tick delay), elixir = raw elixir there. Elixir at deploy: SIM engine value; live tap + 26 ticks of regen.")
    P("")
    out = {}
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B): continue
        d, lo, hi = boot_med_diff(A["push_el"], B["push_el"])
        out[pair] = dict(push=(d, lo, hi))
        P(f"* {pair}: elixir at push start live - SIM = {f2(d)} [{f2(lo)}, {f2(hi)}] (bootstrap over pushes); taps at < 5 elixir/min live {f2(lo_rate(None, cells(A, 'taps'), A['minutes']))} vs SIM {f2(lo_rate(None, cells(B, 'taps'), B['minutes']))}.")
    P("")
    # ---------------------------------------------------- decomposition
    P("## 2. Decomposition of the low-elixir tap rate (Shapley over three factors)")
    P("")
    P("taps at < 5 elixir per minute = 60 x sum over strata s = (phase, pressure bucket) and elixir e < 5 of  w(s) x occ(e | s) x h(s, e):  "
      "w = share of time in each phase x pressure stratum (**opponent pressure mix**), occ = share of that time spent at elixir e (**elixir occupancy**: "
      "how low the bank sits, itself a consequence of earlier spending), h = taps per second at that elixir and stratum (**play hazard**: how readily "
      "the bot spends when it is there). Exact identity; the live-minus-SIM difference is split by Shapley values (average over the 6 orders).")
    P("")
    P("| pairing | live | SIM | gap | pressure mix | elixir occupancy | play hazard |")
    P("|---|---|---|---|---|---|---|")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B): continue
        fl, fs = factors(A)[:3], factors(B)[:3]
        rl, rs, sh = shapley(fl, fs)
        out[pair]["shapley"] = (rl, rs, sh)
        P(f"| {pair} | {f2(rl)} | {f2(rs)} | {f2(rl - rs)} | " + " | ".join(f"{f2(v)} ({pc(v / (rl - rs)) if rl != rs else 'n/a'})" for v in sh.values()) + " |")
        for nm, only in (("  quiet (pb <= 1)", lambda s: s[1] <= 1), ("  pressured (pb >= 2)", lambda s: s[1] >= 2)):
            rl2, rs2, sh2 = shapley(fl, fs, only=only)
            P(f"| {pair}{nm} | {f2(rl2)} | {f2(rs2)} | {f2(rl2 - rs2)} | " + " | ".join(f2(v) for v in sh2.values()) + " |")
    P("")
    P("Pressure mix (share of time by phase x pressure bucket 0/1/2/3), live vs SIM:")
    P("")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B): continue
        wl, ws = factors(A)[0], factors(B)[0]
        P(f"* {pair}: " + "; ".join(f"{PH[p]}: " + "/".join(f"{pc(wl.get((p, b), 0))}" for b in range(4)) + " vs " + "/".join(f"{pc(ws.get((p, b), 0))}" for b in range(4)) for p in range(3)))
    P("")
    # ---------------------------------------------------- gate in matched strata
    P("## 3. What the gate does in the SAME situation (decisions at model elixir < 5, matched phase x pressure x elixir strata, weighted to live)")
    P("")
    P("| pairing | decisions | mean p_play live / SIM | P(p > tau) live / SIM | decisions per second live / SIM | median abs change in p per decision (quiet / pb2 / pb3) live vs SIM |")
    P("|---|---|---|---|---|---|")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B): continue
        pl, ps, ql, qs, n = gate_match(A, B)
        dl = sum(v[0] for v in A["dec"].values()) / (A["minutes"] * 60); ds = sum(v[0] for v in B["dec"].values()) / (B["minutes"] * 60)
        out[pair]["gate"] = (pl, ps, ql, qs)
        P(f"| {pair} | {int(n)} | {f2(pl, 3)} / {f2(ps, 3)} | {pc(ql, 1)} / {pc(qs, 1)} | {f2(dl)} / {f2(ds)} | "
          + " / ".join(f2(dp_med(A, b), 2) for b in range(3)) + " vs " + " / ".join(f2(dp_med(B, b), 2) for b in range(3)) + " |")
        for nm, lo_, pbs in (("  quiet, < 5 elixir", 5, (0, 1)), ("  pressured, < 5 elixir", 5, (2, 3)), ("  all elixir levels", 10, (0, 1, 2, 3))):
            pl, ps, ql, qs, n = gate_match(A, B, lo_, pbs)
            P(f"| {pair}{nm} | {int(n)} | {f2(pl, 3)} / {f2(ps, 3)} | {pc(ql, 1)} / {pc(qs, 1)} | | |")
    P("")
    P("By elixir bucket (model elixir for the gate rows; raw elixir for time share and taps per second), all pressure levels, matched strata weighted to live:")
    P("")
    P("| pairing | elixir | P(p > tau) live / SIM | taps per second live / SIM | share of time live / SIM |")
    P("|---|---|---|---|---|")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B): continue
        oA, tA, oB, tB = cells(A, "occ"), cells(A, "taps"), cells(B, "occ"), cells(B, "taps")
        TA, TB = sum(oA.values()), sum(oB.values())
        for e in range(10):
            sub = lambda d, e=e: {k: v for k, v in d.items() if int(k.split("|")[2]) == e}
            Ae = dict(A, dec=sub(A["dec"])); Be = dict(B, dec=sub(B["dec"]))
            pl, ps, ql, qs, n = gate_match(Ae, Be, 10, (0, 1, 2, 3))
            ta = sum(v for k, v in tA.items() if k[2] == e) / max(1e-9, sum(v for k, v in oA.items() if k[2] == e))
            tb = sum(v for k, v in tB.items() if k[2] == e) / max(1e-9, sum(v for k, v in oB.items() if k[2] == e))
            P(f"| {pair} | {e} | {pc(ql, 1)} / {pc(qs, 1)} | {f2(ta, 3)} / {f2(tb, 3)} | {pc(sum(v for k, v in oA.items() if k[2] == e) / TA, 1)} / {pc(sum(v for k, v in oB.items() if k[2] == e) / TB, 1)} |")
    P("")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B): continue
        ml = A["margin"]; ms = B["margin"]
        nl = sum(ml.values()); ns_ = sum(ms.values())
        out[pair]["marginal"] = (ml.get("0", 0) / nl if nl else float("nan"), ms.get("0", 0) / ns_ if ns_ else float("nan"))
        P(f"* {pair} plays fired with the gate barely over threshold (0 <= p - tau < .05): live {pc(out[pair]['marginal'][0], 1)} of {nl} vs SIM {pc(out[pair]['marginal'][1], 1)} of {ns_}")
        gl = A["gap"]; gs = B["gap"]; tl = sum(gl.values()); ts = sum(gs.values())
        P(f"* {pair} decision spacing (ticks: share) live " + ", ".join(f"{k}: {pc(v / tl)}" for k, v in sorted(gl.items(), key=lambda kv: -kv[1])[:4])
          + " | SIM " + ", ".join(f"{k}: {pc(v / ts)}" for k, v in sorted(gs.items(), key=lambda kv: -kv[1])[:3]))
    P("")
    # ---------------------------------------------------- live-only spends, counter, artefacts
    P("## 4. Live-only spends, counter bias, reader artefacts")
    P("")
    for pair, lv in (("stack2k", "stack"), ("R1e", "r1e")):
        A = LV[lv]
        if not A: continue
        dr = med(A["abil_drop"]) if A["abil_drop"] else float("nan")
        per_push = A["push_abil10"] / max(1, len(A["push_el"]))
        out.setdefault(pair, {})["abil"] = per_push * dr
        P(f"* {pair} Hero Ice Wizard ability: {f2(A['abil'] / A['minutes'])} presses/min, median elixir drop {f2(dr)} (n={len(A['abil_drop'])}); "
          f"presses in the 10 s before a push start {f2(per_push, 3)} per push -> adds back about {f2(per_push * dr, 2)} elixir at push start. SIM has no Hero Ice Wizard.")
        P(f"  reader artefacts: duplicated enemy bodies (same card within .25 tiles, same state) {pc(A['dup'] / max(1, A['bodies']), 2)} of body sightings, "
          f"their value on my half {f2(A['dup_v_half'] / A['minutes'], 2)}/min vs arriving enemy value {f2(sum(A.get('arrive_' + p, 0) for p in PH) / A['minutes'], 1)}/min; "
          f"one-state ids {pc(A['phantom'] / max(1, A['ids']), 1)} of enemy ids.")
    S0, S1 = SM["stack"], SM["stack_bias"]
    if S0 and S1:
        d, lo, hi = boot_med_diff(S1["push_el"], S0["push_el"])
        out["bias"] = dict(push=(d, lo, hi), lo=(lo_rate(None, cells(S1, 'taps'), S1['minutes']) - lo_rate(None, cells(S0, 'taps'), S0['minutes'])))
        w0 = S0["outcomes"]; w1 = S1["outcomes"]
        P(f"* Opponent-counter over-read (+0.34, measured live): SIM stack +0.34 minus SIM stack: elixir at push start {f2(d)} [{f2(lo)}, {f2(hi)}]; "
          f"taps at < 5 elixir/min {f2(out['bias']['lo'])}; wins {w1.get('win', 0)} vs {w0.get('win', 0)} of {int(S1['n'])} / {int(S0['n'])}.")
    P("")
    pressure_sections(P, LV, SM, out)
    L[gap_at:gap_at] = attribution(LV, SM, out)
    json.dump(out, open(HERE + "econ_gap_numbers.json", "w"), indent=1, default=str)
    open(HERE + "econ_gap.md", "w", encoding="utf8").write("\n".join(L) + "\n")
    print("\n".join(L))


REC = ((0, 5), (5, 10), (10, 20), (20, 40), (40, 1e9))


def rec_bucket(s): return next(i for i, (a, b) in enumerate(REC) if a <= s < b)


def reweighted_push_el(L_, S_):
    """SIM push-start elixir re-weighted to LIVE's mix of (phase x recovery time since the previous push): the part of the
    gap that the opponent's push FREQUENCY explains. First pushes (no previous) form their own bucket."""
    def strata(A):
        d = collections.defaultdict(list)
        for el, p, s in zip(A["push_el"], A["push_ph"], A["push_since"]):
            d[(p, -1 if s is None else rec_bucket(s))].append(el)
        return d
    dl, ds = strata(L_), strata(S_)
    n = sum(len(v) for v in dl.values()); exp = 0.0; cov = 0
    for k, v in dl.items():
        if len(ds.get(k, [])) >= 5: exp += len(v) / n * mean(ds[k]); cov += len(v)
        else: exp += len(v) / n * mean(S_["push_el"])
    return exp, cov / n, dl, ds


def full_elixir(P, LV, SM, out):
    """At >= 9 elixir: time share, taps/s and per-decision P(p > tau) by (phase, my-half pressure, WHOLE-board enemy value)."""
    P("## 8. Where the bank leaks: behaviour at full elixir (>= 9)")
    P("")
    P("Strata = phase x my-half pressure bucket x whole-board enemy value bucket (0 < .5 / 1 .5-4 / 2 4-8 / 3 >= 8 elixir of enemy bodies anywhere). "
      "taps at >= 9 per minute = 60 x sum time-share(s) x hazard(s); Shapley split into board-state mix vs hazard.")
    P("")
    P("| pairing | time at >= 9 elixir (share of match) live / SIM | taps at >= 9 /min live / SIM | split: state mix / hazard | per-decision P(p > tau) at model elixir >= 9, matched strata live / SIM | whole-board bucket shares at >= 9 (0/1/2/3) live vs SIM |")
    P("|---|---|---|---|---|---|")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B and A.get("occ9")): continue
        def fac(X):
            o = X["occ9"]; t = X["taps9"]; tot = X["minutes"] * 60
            w = {k: v / tot for k, v in o.items()}
            h = {k: (t.get(k, 0) / v if v >= 5 else None) for k, v in o.items()}
            return w, h
        (wl, hl), (ws, hs) = fac(A), fac(B)
        def r(w, h, hb): return 60 * sum(v * (h.get(k) if h.get(k) is not None else (hb.get(k) or 0)) for k, v in w.items())
        rl, rs = r(wl, hl, hs), r(ws, hs, hl)
        mix = (r(wl, hs, hl) - rs + rl - r(ws, hl, hs)) / 2; haz = (r(ws, hl, hs) - rs + rl - r(wl, hs, hl)) / 2
        n = a = b = 0.0
        for k, v in A["dec9"].items():
            s = B["dec9"].get(k)
            if not s or v[0] < 5 or s[0] < 5: continue
            n += v[0]; a += v[1]; b += s[1] / s[0] * v[0]
        def bsh(X):
            c = collections.Counter()
            for k, v in X["occ9"].items(): c[int(k.split("|")[2])] += v
            T = sum(c.values()); return "/".join(pc(c[i] / T) for i in range(4))
        out.setdefault(pair, {})["full"] = dict(time=(sum(wl.values()), sum(ws.values())), taps=(rl, rs), mix=mix, hazard=haz, p=(a / n if n else None, b / n if n else None))
        P(f"| {pair} | {pc(sum(wl.values()), 1)} / {pc(sum(ws.values()), 1)} | {f2(rl)} / {f2(rs)} | {f2(mix)} / {f2(haz)} | {pc(a / n if n else None, 1)} / {pc(b / n if n else None, 1)} (n={int(n)}) | {bsh(A)} vs {bsh(B)} |")
    P("")


def ols(x, y):
    mx, my = mean(x), mean(y); sxx = sum((a - mx) ** 2 for a in x)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx if sxx else float("nan")
    return my - b * mx, b


def presence(P, LV, SM, out):
    """Per match: share of time with ANY enemy body on the board (>= .5 elixir of value). SIM's own match-to-match relation
    between that presence and the bank (mean elixir; median push-start elixir) predicts the SIM bank at LIVE's presence."""
    P("## 9. Whole-match board presence (SIM's own presence -> bank relation, applied at live presence)")
    P("")
    P("| pairing | enemy on board (share of time) live / SIM | mean own elixir live / SIM | SIM slope (elixir per +10 pp presence) | SIM predicted at live presence | share of the mean-elixir gap explained | push-start elixir: live / SIM / SIM predicted at live presence | share of the push-start gap explained |")
    P("|---|---|---|---|---|---|---|---|")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B) or len(A["per_match"][0]) < 12: continue
        la = [r for r in A["per_match"] if r[10] is not None and r[11] is not None]; sb = [r for r in B["per_match"] if r[10] is not None and r[11] is not None]
        bl, bs = mean([r[10] for r in la]), mean([r[10] for r in sb])
        el_l, el_s = mean([r[11] for r in la]), mean([r[11] for r in sb])
        a0, b1 = ols([r[10] for r in sb], [r[11] for r in sb]); pred = a0 + b1 * bl
        sp = [r for r in sb if r[4] is not None]; lp = [r for r in la if r[4] is not None]
        c0, c1 = ols([r[10] for r in sp], [r[4] for r in sp]); ppred = c0 + c1 * mean([r[10] for r in lp])
        pl_, ps_ = mean([r[4] for r in lp]), mean([r[4] for r in sp])
        out.setdefault(pair, {})["presence"] = dict(busy=(bl, bs), el=(el_l, el_s), pred=pred, push=(pl_, ps_, ppred))
        P(f"| {pair} | {pc(bl)} / {pc(bs)} | {f2(el_l)} / {f2(el_s)} | {f2(b1 * .1)} | {f2(pred)} | {pc((pred - el_s) / (el_l - el_s)) if el_l != el_s else 'n/a'} | "
          f"{f2(pl_)} / {f2(ps_)} / {f2(ppred)} | {pc((ppred - ps_) / (pl_ - ps_)) if pl_ != ps_ else 'n/a'} |")
    P("")
    P("Push-start values here are means of per-match medians (matches with >= 1 push). The prediction extrapolates SIM's linear relation to "
      "live's presence level (live presence sits at the busy end of SIM's range), so treat the explained share as an estimate (b).")
    P("")


def qtable(A):
    q = {}; pool = collections.defaultdict(lambda: [0, 0])
    for k, v in A["dec"].items():
        p, pb, e = map(int, k.split("|")); pool[(p, e)][0] += v[0]; pool[(p, e)][1] += v[3]
    for k, v in A["dec"].items():
        p, pb, e = map(int, k.split("|"))
        q[(p, pb, e)] = v[3] / v[0] if v[0] >= 30 else (pool[(p, e)][1] / pool[(p, e)][0] if pool[(p, e)][0] else 0.0)
    return q, {k: v[1] / v[0] for k, v in pool.items() if v[0]}


def qtableB(A):
    """P(play | decision) by (phase, my-half pressure, whole-board bucket, model elixir); thin cells fall back to (phase, elixir)."""
    q = {}; pool = collections.defaultdict(lambda: [0, 0])
    for k, v in A["decB"].items():
        p, pb, b, e = map(int, k.split("|")); pool[(p, e)][0] += v[0]; pool[(p, e)][1] += v[2]
    for k, v in A["decB"].items():
        p, pb, b, e = map(int, k.split("|"))
        q[(p, pb, b, e)] = v[2] / v[0] if v[0] >= 30 else (pool[(p, e)][1] / pool[(p, e)][0] if pool[(p, e)][0] else 0.0)
    return q, {k: v[1] / v[0] for k, v in pool.items() if v[0]}


def ctable(A):
    c = collections.defaultdict(list)
    for k, n in A["cost"].items():
        e, cost = map(int, k.split("|"))
        if cost: c[e].append((cost, n))
    return c


def simulate(seqs, Q, C, abil=False, seeds=8, seed0=11):
    """Elixir bookkeeping only: income by phase; a decision every 10 ticks (none for 30 ticks after a play, as SIM and live);
    play with the per-decision probability Q[(phase, pressure bucket, model-elixir bucket)]; cost drawn from the empirical
    cost-given-elixir table (affordable costs only), paid 26 ticks later; optional Hero ability drops (1.14) at the logged ticks.
    -> (mean per-match median elixir at push start, mean elixir over time, plays at < 5 elixir per minute)."""
    import random
    q, qp = Q; rng = random.Random(seed0); pm = []; mel = []; lo = []
    for sq in seqs:
        T, pbs, pushes, ab, end = sq[:5]; bbs = sq[6] if len(sq) > 6 and len(next(iter(q)) if q else ()) == 4 else None
        if len(T) < 10: continue
        for s in range(seeds):
            el = min(10.0, 6 + T[0] / 56.0); t = T[0]; nxt = t; pending = []; k = 0; pv = []; ps = set(pushes); abq = list(ab) if abil else []
            esum = 0.0; n = 0; lo_n = 0; pi = 0; pushes_sorted = sorted(pushes)
            while t < end:
                ph_ = 0 if t < 2400 else (1 if t < 3600 else 2)
                rate = (1 if ph_ == 0 else 2) / 56.0
                el = min(10.0, el + rate)
                while pending and pending[0][0] <= t: el = max(0.0, el - pending.pop(0)[1])
                while abq and abq[0] <= t: abq.pop(0); el = max(0.0, el - 1.14)
                while k + 1 < len(T) and T[k + 1] <= t: k += 1
                while pi < len(pushes_sorted) and pushes_sorted[pi] <= t: pv.append(el); pi += 1
                if t % 10 == 0: esum += el; n += 1
                if t >= nxt and t % 10 == 0:
                    eb_ = max(0, min(9, int(min(10.0, el + 26 * rate))))
                    key = (ph_, pbs[k], bbs[k], eb_) if bbs is not None else (ph_, pbs[k], eb_)
                    pr = q.get(key, qp.get((ph_, eb_), 0.0))
                    if rng.random() < pr:
                        opts = [(c, w) for c, w in C.get(max(0, min(9, int(el))), []) if c <= int(el) + 26 * rate * 1.0001 + 1e-9]
                        if opts:
                            tot = sum(w for _, w in opts); r = rng.random() * tot
                            for c, w in opts:
                                r -= w
                                if r <= 0: break
                            pending.append((t + 26, c)); nxt = t + 30
                            if el < 5: lo_n += 1
                t += 1
            if pv: pm.append(sorted(pv)[len(pv) // 2])
            mel.append(esum / max(1, n)); lo.append(lo_n / max(1e-9, (end - T[0]) / 1200.0))
    return mean(pm), mean(mel), mean(lo)


def counterfactual(P, LV, SM, out):
    P("## 10. Counterfactual: the SIM policy facing the LIVE opponents' pressure timeline")
    P("")
    P("A deliberately simple elixir simulator (econ_report.simulate) replays each match's own pressure timeline (my-half pressure and whole-board enemy value bucket every state, "
      "push starts) and decides every 10 ticks with a per-decision play probability estimated from one source's decisions (phase x pressure x whole board x "
      "model-elixir), costs from that source's cost-given-elixir table. Rows 1-2 check the simulator against the real numbers; rows 3-5 swap "
      "one ingredient at a time. Columns: mean of per-match median elixir at push start | mean own elixir | plays at < 5 elixir per minute.")
    P("")
    P("| pairing | scenario | push-start elixir | mean elixir | plays < 5 /min |")
    P("|---|---|---|---|---|")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B and A.get("seq") and B.get("seq")): continue
        qa, qb, ca, cb = (qtableB(A), qtableB(B), ctable(A), ctable(B)) if A.get("decB") and B.get("decB") else (qtable(A), qtable(B), ctable(A), ctable(B))
        actual_l = (mean([r[4] for r in A["per_match"] if r[4] is not None]), mean([r[11] for r in A["per_match"] if r[11] is not None]))
        actual_s = (mean([r[4] for r in B["per_match"] if r[4] is not None]), mean([r[11] for r in B["per_match"] if r[11] is not None]))
        rows = [("ACTUAL live", actual_l + (None,)), ("ACTUAL SIM", actual_s + (None,)),
                ("sim: SIM policy, SIM pressure (check)", simulate(B["seq"], qb, cb)),
                ("sim: live policy, live pressure, + Hero ability (check)", simulate(A["seq"], qa, ca, abil=True)),
                ("sim: SIM policy, LIVE pressure", simulate(A["seq"], qb, cb)),
                ("sim: SIM policy, LIVE pressure, + Hero ability", simulate(A["seq"], qb, cb, abil=True)),
                ("sim: LIVE policy, SIM pressure", simulate(B["seq"], qa, ca))]
        out.setdefault(pair, {})["cf"] = {k: v for k, v in rows}
        for nm, v in rows:
            P(f"| {pair} | {nm} | {f2(v[0])} | {f2(v[1])} | {f2(v[2]) if v[2] is not None else '-'} |")
    P("")


def play_vs_gate(P, LV, SM, out):
    """matched strata (phase x pressure x model elixir), weighted to live decisions: P(p > tau) vs P(a play is issued)."""
    P("## 10b. Gate verdict vs actual play, per decision, matched strata (weighted to live)")
    P("")
    P("| pairing | elixir | decisions | P(p > tau) live / SIM | P(play issued) live / SIM | live plays issued with p <= tau (forced / hazard / other) |")
    P("|---|---|---|---|---|---|")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B): continue
        for nm, lo_, hi_ in (("< 5", 0, 5), (">= 5", 5, 10), ("all", 0, 10)):
            n = g_l = g_s = p_l = p_s = 0.0
            for k, v in A["dec"].items():
                e = int(k.split("|")[2]); s = B["dec"].get(k)
                if not (lo_ <= e < hi_) or not s or v[0] < 5 or s[0] < 5: continue
                n += v[0]; g_l += v[2]; p_l += v[3]; g_s += s[2] / s[0] * v[0]; p_s += s[3] / s[0] * v[0]
            P(f"| {pair} | {nm} | {int(n)} | {pc(g_l / n, 1)} / {pc(g_s / n, 1)} | {pc(p_l / n, 1)} / {pc(p_s / n, 1)} | {f2(A.get('forced', 0) / A['minutes'], 2)}/min forced |")
    P("")
    P("Same, with the WHOLE-board enemy value bucket added to the strata (phase x my-half pressure x whole-board 0/1/2/3 x model elixir):")
    P("")
    P("| pairing | elixir | decisions | P(p > tau) live / SIM | P(play issued) live / SIM | whole-board bucket time shares 0/1/2/3 live vs SIM |")
    P("|---|---|---|---|---|---|")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B and A.get("decB") and B.get("decB")): continue
        def bsh(X):
            c = collections.Counter()
            for k, v in X["boardT"].items(): c[int(k.split("|")[1])] += v
            T = sum(c.values()); return "/".join(pc(c[i] / T) for i in range(4))
        for nm, lo_, hi_ in (("< 5", 0, 5), (">= 5", 5, 10), ("all", 0, 10)):
            n = g_l = g_s = p_l = p_s = 0.0
            for k, v in A["decB"].items():
                e = int(k.split("|")[3]); s = B["decB"].get(k)
                if not (lo_ <= e < hi_) or not s or v[0] < 5 or s[0] < 5: continue
                n += v[0]; g_l += v[1]; p_l += v[2]; g_s += s[1] / s[0] * v[0]; p_s += s[2] / s[0] * v[0]
            out.setdefault(pair, {})["decB_" + nm] = (g_l / n, g_s / n, p_l / n, p_s / n) if n else None
            P(f"| {pair} | {nm} | {int(n)} | {pc(g_l / n, 1)} / {pc(g_s / n, 1)} | {pc(p_l / n, 1)} / {pc(p_s / n, 1)} | {bsh(A) + ' vs ' + bsh(B) if nm == 'all' else ''} |")
    P("")


def noise_cadence_live(P, LV, SM, out):
    play_vs_gate(P, LV, SM, out)
    P("## 11. Decision cadence and gate noise, measured live vs SIM")
    P("")
    P("| source | decisions/s | decision gaps < 10 ticks | plays on a fresh crossing (prev decision p <= tau < p) | mean abs change of p per decision | share of changes >= .06 |")
    P("|---|---|---|---|---|---|")
    for nm, A in (("LIVE stack2k", LV["stack"]), ("LIVE R1e", LV["r1e"]), ("LIVE towerref_w2", LV["towerref"]), ("SIM stack2k (decide 10)", SM["stack"]), ("SIM R1e (decide 10)", SM["r1e"]),
                  ("SIM towerref_w2 + deployed options, decide 10", SM.get("de10")), ("SIM towerref_w2 + deployed options, decide 4", SM.get("de4"))):
        if not A: continue
        pa = A["play_after"]; n = sum(pa.values())
        dp = collections.Counter()
        for k, v in A["dp"].items():
            b, x = map(int, k.split("|")); dp[x] += v
        tot = sum(dp.values()); gt = sum(A["gap"].values())
        P(f"| {nm} | {f2(sum(v[0] for v in A['dec'].values()) / (A['minutes'] * 60))} | {pc(sum(v for k, v in A['gap'].items() if int(k) < 10) / gt, 1)} | "
          f"{pc(pa.get('below', 0) / n if n else None, 1)} | {f2(sum(x * .02 * v for x, v in dp.items()) / tot, 3)} | {pc(sum(v for x, v in dp.items() if x >= 3) / tot, 1)} |")
    P("")


def cadence_test(P, SM, out):
    A, B = SM.get("de10"), SM.get("de4")
    if not (A and B): return
    P("## 12. SIM cadence test: deployed live options (main 049772e) on towerref_w2, learner decides every 10 vs every 4 ticks")
    P("")
    P("Isolated repo = git archive 049772e pipeline + econ_sim_patch.py (LR_DECIDE_EVERY touches the learner only). Options: class_sample .3, tau_phase "
      ".35/.45/.55, rocket_area, own_effects, log_barrel, hazard_below_tau min 9, lethal_rocket ot (--iw-press-pstar is live-only: no Hero Ice Wizard in SIM). "
      "v3 benchmark, 480 paired matches per arm.")
    P("")
    def cheap(X):
        c = collections.Counter()
        for k, n in X["cost"].items(): c[int(k.split("|")[1]) <= 2] += n
        return c[True] / max(1, sum(c.values()))
    def lo_ctx(X, quiet):
        return sum(v for k, v in X["taps"].items() if int(k.split("|")[2]) < 5 and (int(k.split("|")[1]) <= 1) == quiet) / X["minutes"]
    P("| arm | decisions/s | elixir at push start (median) | pushes met < 4 | taps < 5 elixir /min quiet / pressured | cheap (Skeletons+Log) share | elixir at deploy 1x / 2x / OT | wins / 480 |")
    P("|---|---|---|---|---|---|---|---|")
    for nm, X in (("decide 10", A), ("decide 4", B)):
        P(f"| {nm} | {f2(sum(v[0] for v in X['dec'].values()) / (X['minutes'] * 60))} | {f2(med(X['push_el']), 2)} | {pc(mean([x < 4 for x in X['push_el']]))} | "
          f"{f2(lo_ctx(X, True))} / {f2(lo_ctx(X, False))} | {pc(cheap(X), 1)} | " + " / ".join(f2(mean(X['deploy_' + p]), 2) for p in PH)
          + f" | {X['outcomes'].get('win', 0)} (+{X['outcomes'].get('draw', 0)} draws) |")
    d, lo, hi = boot_med_diff(B["push_el"], A["push_el"])
    pa = {r[0]: r[5] for r in A["per_match"]}; pb = {r[0]: r[5] for r in B["per_match"]}
    sc = {"win": 1, "draw": .5}; up = sum(sc.get(pb[k], 0) > sc.get(pa[k], 0) for k in pa if k in pb); dn = sum(sc.get(pb[k], 0) < sc.get(pa[k], 0) for k in pa if k in pb)
    n_ = up + dn; k_ = min(up, dn); p_ = min(1.0, 2 * sum(math.comb(n_, i) for i in range(k_ + 1)) / 2 ** n_) if n_ else 1.0
    out["cadence"] = dict(push=(d, lo, hi), paired=(up, dn, p_))
    P("")
    P(f"* decide 4 minus decide 10: elixir at push start (median) {f2(d)} [{f2(lo)}, {f2(hi)}]; paired outcomes better {up} / worse {dn} (sign p {f2(p_, 3)}).")
    P("")


def attribution(LV, SM, out):
    """-> markdown lines for the top of econ_gap.md (computed from the sections' numbers)."""
    L = []; P = L.append
    s, r = out.get("stack2k", {}), out.get("R1e", {})
    cf_s, cf_r = s.get("cf", {}), r.get("cf", {})
    def cfd(cf, a, b, i): return (cf[a][i] - cf[b][i]) if a in cf and b in cf and cf[a][i] is not None and cf[b][i] is not None else float("nan")
    gap_el = lambda c: cfd(c, "ACTUAL live", "ACTUAL SIM", 1)
    ca = out.get("cadence"); de10 = SM.get("de10"); tw = LV.get("towerref")
    P("## Bottom line")
    P("")
    P("* The live economy gap is real for the same checkpoint + options (section 1). It is NOT a different gate: per decision, the same model plays "
      "with the same probability as in SIM once the situation is matched on phase, pressure on my half, enemy value anywhere on the board and elixir (section 10b).")
    P("* Live opponents keep more enemy units on the board and push onto my half more often at the SAME elixir spend (section 5), and the bot spends "
      "into that presence; this explains about a third of the mean-elixir gap. Small live-only drains add to it: Hero Ice Wizard ability (~0.1 elixir at push start), "
      "and in the anti-leak-ON stack2k matches forced plays (~0.4).")
    if ca:
        P(f"* Decision cadence is NOT the live cause: live decides 1.57-1.62 times/s, the SIM 1.60. The SIM test shows cadence WOULD matter if it rose: deciding every 4 ticks "
          f"costs {f2(ca['push'][0])} [{f2(ca['push'][1])}, {f2(ca['push'][2])}] elixir at push start and {f2(ca['paired'][0] - ca['paired'][1], 0)} net paired results (n.s.) -> any live change "
          "that raises the decision rate (e.g. pipelined plays) should be checked for this.")
    P("* The +0.34 opponent-counter over-read, reader duplicates and gate noise are contradicted as causes. Most of the push-start gap (about 1.0 of 1.6 elixir for stack2k) is left "
      "unexplained at this state resolution: it forms in the seconds before a live push (section 10's simulator reproduces SIM but not live there).")
    if de10 and tw:
        P(f"* Current live checkpoint (towerref_w2, live n={int(tw['n'])}, logs span several option sets): elixir at push start live {f2(med(tw['push_el']))} vs SIM with the deployed options {f2(med(de10['push_el']))}.")
    P("")
    P("## Attribution (live minus SIM, same checkpoint + options)")
    P("")
    P(f"Targets: elixir at push start (median) stack2k {f2(s.get('push', (float('nan'),) * 3)[0])} [{f2(s.get('push', (0, float('nan'), 0))[1])}, {f2(s.get('push', (0, 0, float('nan')))[2])}], "
      f"R1e {f2(r.get('push', (float('nan'),) * 3)[0])}; mean own elixir stack2k {f2(gap_el(cf_s))}, R1e {f2(gap_el(cf_r))}; taps at < 5 elixir/min "
      f"stack2k +{f2(s.get('shapley', (0, 0, {}))[0] - s.get('shapley', (0, 0, {}))[1])} (R1e +{f2(r.get('shapley', (0, 0, {}))[0] - r.get('shapley', (0, 0, {}))[1])}).")
    P("")
    P("| candidate | what was measured | size | label |")
    P("|---|---|---|---|")
    ca = out.get("cadence")
    P("| (1) decision cadence / gate noise | live 1.57-1.62 decisions/s vs SIM 1.60-1.61; live gaps < 10 ticks 6-8%; mean abs p change per decision live .033-.038 vs SIM .043-.046; "
      "fresh-crossing share 93-98% both (not discriminating) "
      + (f"; SIM decide-4 vs decide-10 (deployed options): push-start elixir {f2(ca['push'][0])} [{f2(ca['push'][1])}, {f2(ca['push'][2])}], paired better/worse {ca['paired'][0]}/{ca['paired'][1]}" if ca else "")
      + " | live does NOT decide faster than SIM -> ~0 of the live gap | (c) |")
    P(f"| (2a) Hero Ice Wizard ability (live only) | 0.39-0.56 presses/min x 1.14 elixir; simulator: SIM policy + ability on live timeline | push start -0.08..-0.09 (presses in the 10 s before a push); "
      f"mean elixir {f2(cfd(cf_s, 'sim: SIM policy, LIVE pressure, + Hero ability', 'sim: SIM policy, LIVE pressure', 1))} (stack), {f2(cfd(cf_r, 'sim: SIM policy, LIVE pressure, + Hero ability', 'sim: SIM policy, LIVE pressure', 1))} (R1e) | (a) small |")
    P("| (2b) anti-leak forced plays (live stack2k only: 77/102 matches ON) | 0.42 forced plays/min when ON; push start ON 3.1 vs OFF 3.5 | ~0.4 of the 1.6 stack2k gap in ON matches; 0 for R1e/towerref (OFF) | (b) (OFF n=26) |")
    P("| (2c) evolution forms | Tesla and Knight evolved in both live hands and the SIM deck | 0 | (c) |")
    P(f"| (3) opponent pressure | enemy value arriving on my half 1x 28.8 vs 18.3 /min; pushes/min 1.32 vs 1.02-1.06; same opponent spend (counter drops 25-27/min both); "
      f"time with >= 8 elixir of enemy units anywhere on the board 37-41% vs 26-28%; push-frequency re-weighting explains 4-8% of the push-start gap; "
      f"simulator (SIM policy, live vs SIM timeline): mean elixir {f2(cfd(cf_s, 'sim: SIM policy, LIVE pressure', 'sim: SIM policy, SIM pressure (check)', 1))} (stack), "
      f"{f2(cfd(cf_r, 'sim: SIM policy, LIVE pressure', 'sim: SIM policy, SIM pressure (check)', 1))} (R1e); push start "
      f"{f2(cfd(cf_s, 'sim: SIM policy, LIVE pressure', 'sim: SIM policy, SIM pressure (check)', 0))} / {f2(cfd(cf_r, 'sim: SIM policy, LIVE pressure', 'sim: SIM policy, SIM pressure (check)', 0))} | "
      f"about 1/3 of the mean-elixir gap; ~0 of the push-start gap in the simulator | (a) live presses harder; (b) as the cause of the push-start gap |")
    db = s.get("decB_all"); dbr = r.get("decB_all")
    P(f"| (4) state differences seen by the gate | P(play issued) per decision in matched phase x my-half pressure x WHOLE-board x elixir strata: stack2k "
      f"{pc(db[2], 1) if db else 'n/a'} vs {pc(db[3], 1) if db else 'n/a'}, R1e {pc(dbr[2], 1) if dbr else 'n/a'} vs {pc(dbr[3], 1) if dbr else 'n/a'} "
      f"(coarser strata without the whole board: live +0.7-0.9 pp, i.e. the excess is the board mix of (3)); simulator policy swap on the live timeline: mean elixir "
      f"{f2(cfd(cf_s, 'sim: live policy, live pressure, + Hero ability (check)', 'sim: SIM policy, LIVE pressure, + Hero ability', 1))} / {f2(cfd(cf_r, 'sim: live policy, live pressure, + Hero ability (check)', 'sim: SIM policy, LIVE pressure, + Hero ability', 1))} | "
      "the same model makes the same per-decision choice in the same coarse state; small cell-level differences remain | (c) for 'the gate reads live states differently' at this resolution |")
    P(f"| (5) reader / extrapolation artefacts | duplicated enemy bodies 0.7-0.9% of sightings (2.9 elixir/min of my-half value, ~8% of arrivals); one-state ids 6.5-8% (excluded); "
      f"counter +0.34 over-read in SIM: push start {f2(out.get('bias', {}).get('push', (float('nan'),) * 3)[0])} [{f2(out.get('bias', {}).get('push', (0, float('nan'), 0))[1])}, {f2(out.get('bias', {}).get('push', (0, 0, float('nan')))[2])}], wins 310 vs 310 | ~0 | (c) |")
    P(f"| unexplained | the elixir simulator reproduces SIM (push start {f2(cf_s.get('sim: SIM policy, SIM pressure (check)', (float('nan'),))[0])} vs actual {f2(cf_s.get('ACTUAL SIM', (float('nan'),))[0])}) "
      f"but overshoots live (push start {f2(cf_s.get('sim: live policy, live pressure, + Hero ability (check)', (float('nan'),))[0])} vs actual {f2(cf_s.get('ACTUAL live', (float('nan'),))[0])}): "
      "what happens in the seconds before a live push (card availability, hand order, how pushes form) is not captured by phase x pressure x board x elixir | "
      "~1/3 of the mean-elixir gap and most of the push-start gap | (b) |")
    P("")
    return L


def pressure_sections(P, LV, SM, out):
    _pressure_core(P, LV, SM, out)          # sections 5-7
    full_elixir(P, LV, SM, out)             # 8
    presence(P, LV, SM, out)                # 9
    counterfactual(P, LV, SM, out)          # 10, 10b
    noise_cadence_live(P, LV, SM, out)      # 11
    cadence_test(P, SM, out)                # 12


def _pressure_core(P, LV, SM, out):
    P("## 5. Opponent pressure: live opponents vs the SIM opponent")
    P("")
    P("| source | enemy value arriving on my half /min 1x / 2x / OT | opponent spend /min (public counter drops) | SIM opponent exact spend /min | pushes /min | recovery time before a push (median s) |")
    P("|---|---|---|---|---|---|")
    for nm, A in (("LIVE stack2k", LV["stack"]), ("SIM stack2k", SM["stack"]), ("LIVE R1e", LV["r1e"]), ("SIM R1e", SM["r1e"])):
        if not A: continue
        P(f"| {nm} | " + " / ".join(f2(A.get('arrive_' + p, 0) / max(1e-9, A.get('min_' + p, 0)), 1) for p in PH)
          + f" | {f2(A['opp_drop'] / A['minutes'], 1)} | {f2(A['opp_cost'] / A['minutes'], 1) if A.get('opp_cost') else '-'} | {f2(len(A['push_el']) / A['minutes'])} | "
          f"{f2(med([s for s in A['push_since'] if s is not None]), 1)} |")
    P("")
    P("Elixir balance per minute (income = regen over the phase minutes; spend = card costs; ability = presses x 1.14):")
    P("")
    P("| source | income | card spend | Hero ability | wasted at the cap | income - spend - ability - waste |")
    P("|---|---|---|---|---|---|")
    for nm, A in (("LIVE stack2k", LV["stack"]), ("SIM stack2k", SM["stack"]), ("LIVE R1e", LV["r1e"]), ("SIM R1e", SM["r1e"])):
        if not A: continue
        inc = sum(A.get("min_" + p, 0) * 1200 * {"1x": 1 / 56, "2x": 2 / 56, "OT": 2 / 56}[p] for p in PH) / A["minutes"]
        ab = A["abil"] * 1.14 / A["minutes"]
        P(f"| {nm} | {f2(inc, 1)} | {f2(A['my_spend'] / A['minutes'], 1)} | {f2(ab, 2)} | {f2(A['waste'] / A['minutes'], 2)} | "
          f"{f2(inc - A['my_spend'] / A['minutes'] - ab - A['waste'] / A['minutes'], 2)} |")
    P("")
    P("## 6. How much of the push-start gap does the opponent's push frequency explain?")
    P("")
    for pair, (lv, sm) in (("stack2k", ("stack", "stack")), ("stack2k anti-leak OFF", ("stack_al0", "stack")), ("R1e", ("r1e", "r1e"))):
        A, B = LV[lv], SM[sm]
        if not (A and B): continue
        exp, cov, dl, ds = reweighted_push_el(A, B)
        gap = mean(A["push_el"]) - mean(B["push_el"])
        out.setdefault(pair, {})["reweight"] = dict(live=mean(A["push_el"]), sim=mean(B["push_el"]), sim_rew=exp, coverage=cov)
        P(f"* {pair}: MEAN elixir at push start live {f2(mean(A['push_el']))} vs SIM {f2(mean(B['push_el']))} (gap {f2(gap)}). SIM re-weighted to live's "
          f"phase x recovery-time mix: {f2(exp)} -> frequency/phase mix explains {f2(exp - mean(B['push_el']))} of {f2(gap)} "
          f"({pc((exp - mean(B['push_el'])) / gap if gap else float('nan'))}); live pushes in strata with SIM data {pc(cov)}.")
        rows = []
        for k in sorted(set(dl) | set(ds), key=lambda k: (PH.index(k[0]), k[1])):
            if len(dl.get(k, [])) >= 20:
                lab = "first" if k[1] < 0 else f"{REC[k[1]][0]}-{REC[k[1]][1] if REC[k[1]][1] < 1e8 else '+'}s"
                rows.append(f"{k[0]} {lab}: live {f2(mean(dl[k]), 1)} (n={len(dl[k])}) vs SIM {f2(mean(ds.get(k, [])), 1)} (n={len(ds.get(k, []))})")
        P("  * by stratum: " + "; ".join(rows))
    P("")
    try:
        import sys; sys.path.insert(0, HERE); sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_eval")
        from live_eval import classify
        import review as V
        rows = {}
        for l in open(HERE + "matches.jsonl"):
            r = json.loads(l); rows[r["file"]] = r
        V.resolve(list(rows.values()))
    except Exception as e:
        P(f"(archetype table skipped: {e})"); return
    P("## 7. Pressure and elixir by opponent class (live R1e + stack2k + towerref; SIM opponents classified the same way from their decks)")
    P("")
    P("| class | live matches | live win rate | live enemy value on my half /min | live push-start elixir (median of match medians) | SIM matches | SIM enemy value /min | SIM push-start elixir |")
    P("|---|---|---|---|---|---|---|---|")
    agg = collections.defaultdict(lambda: [[], [], [], [], [], []])
    for k in ("stack", "r1e", "towerref"):
        A = LV[k]
        if not A: continue
        for f, mins, arr, npush, pmed, *_ in A["per_match"]:
            r = rows.get(f)
            if not r or not r.get("result"): continue
            g = agg[classify(r.get("opp_cards") or [])]
            g[0].append(r["result"] == "WIN"); g[1].append(arr / mins if mins else None); g[2].append(pmed)
    for k in ("stack", "r1e"):
        B = SM[k]
        if not B: continue
        for f, mins, arr, npush, pmed, outc, deck, *_ in B["per_match"]:
            g = agg[classify([str(x).split("@")[0] for x in (deck or [])])]
            g[3].append(1); g[4].append(arr / mins if mins else None); g[5].append(pmed)
    for c, g in sorted(agg.items(), key=lambda kv: -len(kv[1][0])):
        if len(g[0]) < 8: continue
        P(f"| {c} | {len(g[0])} | {pc(mean(g[0]))} | {f2(mean([x for x in g[1] if x is not None]), 1)} | {f2(med([x for x in g[2] if x is not None]), 1)} | "
          f"{len(g[3])} | {f2(mean([x for x in g[4] if x is not None]), 1)} | {f2(med([x for x in g[5] if x is not None]), 1)} |")
    P("")
