"""D1-D5 tables from defense.py's analysed data (data/live_an.pkl.gz, data/pros_an.pkl.gz) -> out/report.txt + out/results.json.

  icebow/.venv/Scripts/python.exe dreport.py
Populations: TR = current bundle era (checkpoint towerref_w2, logs 2026-10-08 13:05 on; TRB = its LIVE_OPTIONS bundle part, 15:51 on),
RL = R-lineage (all live logs >= 20261004_205129), PRO = pro icebow sides. Pro HP is scaled to live level-15 HP (x 4424/3052).
CIs: match-cluster bootstrap (ratio of sums), 95%.
"""
import os, sys, gzip, pickle, json, random, collections, math
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
try:
    import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
COST = {"Skeletons": 1, "Log": 2, "Knight": 3, "Tornado": 3, "IceWizard": 3, "Tesla": 4, "Xbow": 6, "Rocket": 6}
LIVE_P = 4424.0
OUTL = []


def pr(*a):
    s = " ".join(str(x) for x in a); OUTL.append(s); print(s)


def load(n):
    with gzip.open(HERE + "data/" + n + "_an.pkl.gz", "rb") as fh: return pickle.load(fh)


def sc(m): return LIVE_P / m["pmax"]          # HP -> live-equivalent HP


def boot(ms, num, den, B=400, seed=5):
    """ratio of sums over matches with a match-cluster bootstrap CI. num/den: match -> number."""
    a = [(num(m), den(m)) for m in ms]
    tot_d = sum(d for _, d in a)
    if not tot_d: return (float("nan"),) * 3
    est = sum(n for n, _ in a) / tot_d
    rng = random.Random(seed); bs = []
    for _ in range(B):
        s = [a[rng.randrange(len(a))] for _ in a]; d = sum(x[1] for x in s)
        if d: bs.append(sum(x[0] for x in s) / d)
    bs.sort()
    return est, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1]


def fmt(t, d=2, pct=False):
    e, lo, hi = t
    if e != e: return "n/a"
    if pct: return f"{100 * e:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"
    return f"{e:.{d}f} [{lo:.{d}f}, {hi:.{d}f}]"


def med(v):
    v = sorted(x for x in v if x is not None); return v[len(v) // 2] if v else None


def q(v, p):
    v = sorted(x for x in v if x is not None); return v[min(len(v) - 1, int(p * len(v)))] if v else None


def size_b(v): return "3-5" if v < 5 else ("5-8" if v < 8 else "8+")


R = {}


def main():
    L = [m for m in load("live") if m["res"] in ("WIN", "LOSS", "DRAW")]
    P = load("pros")
    pops = {"TR": [m for m in L if m["fam"].startswith("towerref")], "TRB": [m for m in L if m["fam"] == "towerref_bundle"],
            "RL": L, "PRO": P}
    pr("# L74 defense diagnosis -- tables (defense.py + dreport.py)")
    for k, ms in pops.items():
        c = collections.Counter(m["res"] for m in ms)
        pr(f"{k}: matches {len(ms)}  W {c['WIN']} L {c['LOSS']} D {c['DRAW']}  episodes {sum(len(m['eps']) for m in ms)}")
    fams = collections.Counter(m["fam"] for m in L); pr("live families:", dict(fams))
    R["pops"] = {k: len(v) for k, v in pops.items()}

    # ------------------------------------------------------------ D2 response timing
    pr("\n## D2 response timing (lane episodes: >= 3 elixir of enemy value in one lane on my half; first defensive play in that lane or the centre)")
    pr("rsp = seconds from the threat crossing to my first defensive card: tap (bot only) / land (bot = reader confirmation, pros = engine deploy).")
    for k, ms in pops.items():
        for sb in ("3-5", "5-8", "8+"):
            E = [e for m in ms for e in m["eps"] if size_b(e["vmax"]) == sb]
            if not E: continue
            land = [e["rsp_land"] for e in E if e["rsp_land"] is not None]
            tap = [e["rsp_tap"] for e in E if e.get("rsp_tap") is not None]
            com = [(e["first_land"] - e["t_commit"]) / 20 for e in E if e.get("first_land") is not None and e.get("t_commit") is not None]
            r = dict(n=len(E), answered=len(land) / len(E), land_med=med(land), land_p75=q(land, .75), le2=sum(x <= 2 for x in land) / len(E),
                     tap_med=med(tap) if tap else None, commit_to_land_med=med(com),
                     dmg=sum(e["dmg"] for e in E) / len(E) * (LIVE_P / (3052 if k == "PRO" else LIVE_P)))
            R.setdefault("D2", {})[f"{k}|{sb}"] = r
            pr(f"{k:4s} {sb:4s} n={r['n']:5d} answered {r['answered']:.2f}  land<=2s {r['le2']:.2f}  land med {r['land_med']}  p75 {r['land_p75']}"
               f"  tap med {r['tap_med']}  commit->land med {r['commit_to_land_med']}  lane dmg/ep {r['dmg']:.0f}")
    # time + damage decomposition before the first defensive card lands
    pr("\nWhere the time and the lane-tower damage go, per episode, from the crossing to the end (+3 s). Labels (bot, at each decision state")
    pr("before the first defensive TAP): gate = affordable card, p_play < tau, no play; no_elixir = nothing affordable; played_other = a play")
    pr("that is not a defence of this lane; pending_other = locked by such a play; latency = tap -> land of the defence; defended = after it")
    pr("lands. Pros: had_elixir / no_elixir before the deploy, defended after.")
    for k, ms in pops.items():
        for sb in ("all", "5+", "8+"):
            E = [e for m in ms for e in m["eps"] if sb == "all" or (sb == "5+" and e["vmax"] >= 5) or (sb == "8+" and e["vmax"] >= 8)]
            if not E: continue
            sec = collections.Counter(); dm = collections.Counter()
            for m in ms:
                for e in m["eps"]:
                    if not (sb == "all" or (sb == "5+" and e["vmax"] >= 5) or (sb == "8+" and e["vmax"] >= 8)): continue
                    for l, v in e["sec"].items(): sec[l] += v
                    for l, v in e["dm"].items(): dm[l] += v * sc(m)
            tot = sum(dm.values()) or 1
            R.setdefault("D2dec", {})[f"{k}|{sb}"] = dict(n=len(E), sec={l: sec[l] / len(E) for l in sec}, dmg={l: dm[l] / len(E) for l in dm})
            pr(f"{k:4s} {sb:3s} n={len(E):5d} sec/ep: " + "  ".join(f"{l} {sec[l] / len(E):.2f}" for l, _ in sec.most_common()))
            pr(f"          dmg/ep (live HP): " + "  ".join(f"{l} {dm[l] / len(E):.0f} ({100 * dm[l] / tot:.0f}%)" for l, _ in dm.most_common()))
    # damage rate per second of waiting by label
    pr("\nDamage RATE in each interval type (live HP per second of that interval, all episodes):")
    for k, ms in pops.items():
        sec = collections.Counter(); dm = collections.Counter()
        for m in ms:
            for e in m["eps"]:
                for l, v in e["sec"].items(): sec[l] += v
                for l, v in e["dm"].items(): dm[l] += v * sc(m)
        pr(f"{k:4s} " + "  ".join(f"{l} {dm[l] / sec[l]:.1f}/s ({sec[l]:.0f}s)" for l in sorted(sec) if sec[l] > 0))
    # owner's 1.3 s: damage inside the latency window vs the bot's own waiting, per match
    pr("\nOwner hypothesis '1.3 s gap': lane-tower damage per MATCH inside each window (live HP; CI = match bootstrap):")
    for k in ("TR", "TRB", "RL"):
        ms = pops[k]
        for l in ("latency", "gate", "no_elixir", "pending_other", "d_pending", "d_gate", "d_no_elixir", "d_other"):
            r = boot(ms, lambda m, l=l: sum(e["dm"].get(l, 0) for e in m["eps"]), lambda m: 1)
            R.setdefault("D2owner", {})[f"{k}|{l}"] = r
            pr(f"  {k:4s} {l:14s} {fmt(r, 0)}")
    # waiting episodes: gate p vs tau, what the model's top card was
    pr("\nGate waits inside threat episodes (bot): states with an affordable card and p_play < tau before the first defensive tap")
    for k in ("TR", "RL"):
        G_ = [(p, e["gate_tau"]) for m in pops[k] for e in m["eps"] for p in e.get("gate_p", []) if e.get("gate_tau")]
        tops = collections.Counter(t for m in pops[k] for e in m["eps"] for t, c in e.get("gate_top", []) for _ in range(c))
        if not G_: continue
        gap = [t - p for p, t in G_]
        pr(f"  {k}: states {len(G_)}  p median {med([p for p, _ in G_]):.3f}  tau-p median {med(gap):.3f}  share within .05 of tau {sum(g <= .05 for g in gap) / len(gap):.2f}"
           f"  top card while waiting: {tops.most_common(8)}")
    # association: lane damage by response time bucket (episodes >= 5)
    pr("\nLane damage per episode (live HP) by when the first defence LANDED (episodes >= 5 value). Association, not causation:")
    for k in ("TR", "RL", "PRO"):
        rows = collections.defaultdict(list)
        for m in pops[k]:
            for e in m["eps"]:
                if e["vmax"] < 5: continue
                r_ = e["rsp_land"]
                b = "none" if r_ is None else ("<=0" if r_ <= 0 else "0-2" if r_ <= 2 else "2-4" if r_ <= 4 else "4-8" if r_ <= 8 else ">8")
                rows[b].append(e["dmg"] * sc(m))
        pr(f"  {k:4s} " + "  ".join(f"{b}: n={len(rows[b])} {sum(rows[b]) / len(rows[b]):.0f}" for b in ("<=0", "0-2", "2-4", "4-8", ">8", "none") if rows[b]))

    # ------------------------------------------------------------ D3 non-responses
    pr("\n## D3 non-responses: lane episodes whose lane tower lost >= 300 live HP with NO defensive card landed in that lane/centre")
    for k, ms in pops.items():
        thr = lambda m: 300 / sc(m)
        r = boot(ms, lambda m: sum(1 for e in m["eps"] if e["n_def"] == 0 and e["dmg"] >= thr(m)), lambda m: len(m["eps"]))
        dmgsum = boot(ms, lambda m: sum(e["dmg"] * sc(m) for e in m["eps"] if e["n_def"] == 0 and e["dmg"] >= thr(m)), lambda m: 1)
        late = boot(ms, lambda m: sum(1 for e in m["eps"] if e["n_def"] > 0 and e["t_first_dmg"] is not None and e["first_land"] is not None
                                         and e["first_land"] > e["t_first_dmg"] and e["dmg"] >= thr(m)), lambda m: len(m["eps"]))
        allnd = boot(ms, lambda m: sum(1 for e in m["eps"] if e["n_def"] == 0), lambda m: len(m["eps"]))
        R.setdefault("D3", {})[k] = dict(rate=r, dmg_per_match=dmgsum, late=late, no_def_any=allnd)
        pr(f"{k:4s} non-response with >= 300 dmg: {fmt(r, pct=True)} of episodes; dmg/match {fmt(dmgsum, 0)}; landed AFTER damage began (>= 300): "
           f"{fmt(late, pct=True)}; no defence at all (any dmg) {fmt(allnd, pct=True)}")
    for k in ("TR", "RL", "PRO"):
        reasons = collections.Counter(); rdmg = collections.Counter(); other = collections.Counter(); n = 0
        for m in pops[k]:
            for e in m["eps"]:
                if not (e["n_def"] == 0 and e["dmg"] * sc(m) >= 300): continue
                n += 1
                sec = collections.Counter(e["sec"])
                # dominant reason before the first damage (fallback: whole episode)
                lab = sec.most_common(1)[0][0] if sec else "?"
                if e["air_only"] and not e["air_ans_in_hand"]: lab = "no_air_answer_in_hand|" + lab
                reasons[lab] += 1; rdmg[lab] += e["dmg"] * sc(m)
                for c, X, Y, dt in e.get("other_plays", []):
                    other[c + ("(off)" if Y > 18 else "(other lane)")] += 1
        if not n: continue
        R.setdefault("D3why", {})[k] = dict(n=n, reasons=dict(reasons), dmg=dict(rdmg), other=dict(other))
        pr(f"  {k} why (dominant interval label, n={n}): " + "  ".join(f"{l} {c} ({rdmg[l] / 1000:.1f}k HP)" for l, c in reasons.most_common()))
        pr(f"     what it played instead during those episodes: {other.most_common(8)}")
    # threat class of non-responses
    for k in ("TR", "RL", "PRO"):
        cl = collections.Counter()
        for m in pops[k]:
            for e in m["eps"]:
                if e["n_def"] == 0 and e["dmg"] * sc(m) >= 300: cl[(e["cards"] or ["?"])[0]] += 1
        pr(f"  {k} non-response threats (lead card): {cl.most_common(12)}")
    # small-threat triage: share of 3-5 episodes answered and their damage when ignored
    pr("\nTriage of small threats (vmax 3-5): answered share, damage when answered / ignored (live HP per episode):")
    for k, ms in pops.items():
        E = [(e, m) for m in ms for e in m["eps"] if e["vmax"] < 5]
        a = [e["dmg"] * sc(m) for e, m in E if e["n_def"]]; i = [e["dmg"] * sc(m) for e, m in E if not e["n_def"]]
        ela = [e["el_def"] for e, m in E if e["n_def"]]
        pr(f"  {k:4s} n={len(E)} answered {len(a) / max(1, len(E)):.2f}  dmg answered {sum(a) / max(1, len(a)):.0f}  ignored {sum(i) / max(1, len(i)):.0f}"
           f"  elixir spent when answered {sum(ela) / max(1, len(ela)):.2f}")

    # ------------------------------------------------------------ D1 lane triage
    pr("\n## D1 lane triage: plays made while BOTH lanes hold enemy value (light >= 1, heavy >= 4 and >= 2x light); half = own y <= 16, approach = own y <= 20")
    for k, defn, ms in [(k, d, [dict(m, split=[s for s in m["split"] if s["defn"] == d]) for m in v]) for d in ("half", "approach") for k, v in pops.items()]:
        if k == "TRB": continue
        k = f"{k}/{defn}"
        SP = [(s, m) for m in ms for s in m["split"]]
        if not SP: continue
        c = collections.Counter(s["where"] for s, m in SP); el = collections.Counter()
        for s, m in SP: el[s["where"]] += COST.get(s["card"], 0)
        n = len(SP)
        wrong = [(s, m) for s, m in SP if s["where"] == "light" and not s["prior_heavy"]]
        right = [(s, m) for s, m in SP if s["where"] in ("heavy", "centre")]
        dw = sum(s["dmg_heavy10"] * sc(m) for s, m in wrong) / max(1, len(wrong)); dr = sum(s["dmg_heavy10"] * sc(m) for s, m in right) / max(1, len(right))
        bad = sum(1 for s, m in wrong if s["dmg_heavy10"] * sc(m) >= 300)
        r_light = boot(ms, lambda m: sum(1 for s in m["split"] if s["where"] == "light"), lambda m: len(m["split"]))
        r_wrong = boot(ms, lambda m: sum(1 for s in m["split"] if s["where"] == "light" and not s["prior_heavy"] and s["dmg_heavy10"] * sc(m) >= 300), lambda m: 1)
        R.setdefault("D1", {})[k] = dict(n=n, where=dict(c), elixir=dict(el), light_share=r_light, wrong_per_match=r_wrong,
                                         heavy_dmg_after_wrong=dw, heavy_dmg_after_right=dr, wrong_n=len(wrong), wrong_bad=bad)
        pr(f"{k:4s} split plays {n} ({n / len(ms):.2f}/match): " + "  ".join(f"{w} {c[w] / n:.2f}" for w in ("heavy", "centre", "light", "offence"))
           + f" | elixir share " + "  ".join(f"{w} {el[w] / max(1, sum(el.values())):.2f}" for w in ("heavy", "centre", "light", "offence")))
        pr(f"     light-lane share {fmt(r_light, pct=True)}; light play with heavy unanswered in prior 5 s: n={len(wrong)}, heavy-lane dmg next 10 s {dw:.0f} vs"
           f" {dr:.0f} after a heavy/centre play; 'wrong-lane' episodes (heavy tower then >= 300) per match {fmt(r_wrong, 3)}")
        cards = collections.Counter(s["card"] for s, m in wrong)
        pr(f"     light-lane cards: {cards.most_common(8)}")

    # ------------------------------------------------------------ D4a why defended episodes fail
    pr("\n## D4a defended episodes (>= 5 value): failure (lane dmg >= 1000 live HP) by my elixir at the crossing (el0), bot vs pros")
    for k in ("TR", "RL", "PRO"):
        rows = collections.defaultdict(lambda: [0, 0, 0.0, 0.0])
        for m in pops[k]:
            for e in m["eps"]:
                if e["vmax"] < 5 or not e["n_def"] or e["el0"] is None: continue
                b = "<2" if e["el0"] < 2 else "2-4" if e["el0"] < 4 else "4-6" if e["el0"] < 6 else "6-8" if e["el0"] < 8 else "8+"
                r_ = rows[b]; r_[0] += 1; r_[1] += e["dmg"] * sc(m) >= 1000; r_[2] += e["dmg"] * sc(m); r_[3] += e["el_def"]
        R.setdefault("D4a", {})[k] = {b: dict(n=v[0], fail=v[1] / v[0], dmg=v[2] / v[0], spent=v[3] / v[0]) for b, v in rows.items()}
        pr(f"  {k:4s} " + "  ".join(f"el0 {b}: n={rows[b][0]} fail {rows[b][1] / rows[b][0]:.2f} dmg {rows[b][2] / rows[b][0]:.0f} spent {rows[b][3] / rows[b][0]:.1f}"
                                   for b in ("<2", "2-4", "4-6", "6-8", "8+") if rows[b][0]))
    pr("Gate waits AFTER the first defence landed, in intervals where the lane tower lost HP (bot): p_play, tau-p, top card, elixir")
    for k in ("TR", "RL"):
        G_ = [x for m in pops[k] for e in m["eps"] for x in e.get("dgate_hurt", [])]
        if not G_: continue
        pr(f"  {k}: states {len(G_)} p med {med([x[0] for x in G_]):.3f}  tau-p med {med([x[1] - x[0] for x in G_]):.3f}  elixir med {med([x[3] for x in G_])}"
           f"  share elixir >= 4 {sum((x[3] or 0) >= 4 for x in G_) / len(G_):.2f}  top {collections.Counter(x[2] for x in G_).most_common(6)}")
    # within-match (MH) associations on live defended episodes >= 5
    sys.path.insert(0, HERE + "../loss_review")
    import report as RP
    pr("Within-match (MH) differences in P(defended episode fails), live RL episodes >= 5 value, 95% match-cluster bootstrap:")
    U = [dict(e, _file=m["file"], _bad=e["dmg"] >= 1000) for m in pops["RL"] for e in m["eps"] if e["vmax"] >= 5 and e["n_def"]]
    for name, f in (("el0 < 4", lambda u: (u["el0"] or 0) < 4), ("spent < value", lambda u: u["el_def"] < u["vmax"]),
                    ("one card only", lambda u: u["n_def"] == 1), ("first card Tornado", lambda u: u["first_card"] == "Tornado"),
                    ("first card Log", lambda u: u["first_card"] == "Log"), ("first card Skeletons", lambda u: u["first_card"] == "Skeletons"),
                    ("first card Tesla", lambda u: u["first_card"] == "Tesla"), ("landed before crossing (<= 0 s)", lambda u: u["rsp_land"] is not None and u["rsp_land"] <= 0),
                    ("landed > 2 s after crossing", lambda u: u["rsp_land"] is not None and u["rsp_land"] > 2), ("air in push", lambda u: u["air"])):
        d, lo, hi, ns = RP.mh(U, f, lambda u: u["_bad"])
        R.setdefault("D4mh", {})[name] = (d, lo, hi, ns, sum(map(f, U)))
        pr(f"  {name:32s} n={sum(map(f, U)):5d} MH {100 * d:+.1f} pp [{100 * lo:+.1f}, {100 * hi:+.1f}]  strata {ns}")

    # ------------------------------------------------------------ D4 defensive quality
    pr("\n## D4 defensive quality: landed defensive plays inside lane episodes (dmg10 = lane-tower damage in the 10 s after landing, live HP)")
    for k in ("TR", "RL", "PRO"):
        D = [(d, m) for m in pops[k] for d in m["dplays"]]
        pr(f"{k}: plays {len(D)}")
        for card in ("Knight", "IceWizard", "Tesla", "Skeletons", "Tornado", "Log", "Xbow", "Rocket"):
            X = [(d, m) for d, m in D if d["card"] == card]
            if len(X) < 10: continue
            dm = [d["dmg10"] * sc(m) for d, m in X]
            fail = sum(x >= 442 for x in dm) / len(X)
            clr = sum(d["v_after10"] < 1 for d, m in X) / len(X)
            R.setdefault("D4", {})[f"{k}|{card}"] = dict(n=len(X), dmg10=sum(dm) / len(X), fail=fail, cleared=clr, d_near=med([d["d_near"] for d, m in X]),
                                                         in_front=sum(d["in_front"] for d, m in X) / len(X), d_tower=med([d["d_tower"] for d, m in X]))
            pr(f"  {card:9s} n={len(X):5d} dmg10 {sum(dm) / len(X):5.0f}  fail(>=10% princess) {fail:.2f}  lane cleared at +10 s {clr:.2f}  dist to nearest threat {med([d['d_near'] for d, m in X])}"
               f"  in front {sum(d['in_front'] for d, m in X) / len(X):.2f}  d_tower {med([d['d_tower'] for d, m in X])}  d_king {med([d['d_king'] for d, m in X])}")
    pr("\nTesla vs building-targeting threats: placement (|X-9| = distance from the centre column; Y)")
    for k in ("TR", "RL", "PRO"):
        X = [(d, m) for m in pops[k] for d in m["dplays"] if d["card"] == "Tesla" and d["bt"]]
        if not X: continue
        cx = [abs(d["X"] - 9) for d, m in X]; ys = [d["Y"] for d, m in X]
        pr(f"  {k:4s} n={len(X)} |X-9| med {med(cx):.1f} share<=1.5 {sum(c <= 1.5 for c in cx) / len(cx):.2f}  Y med {med(ys):.1f} (p25 {q(ys, .25):.1f} p75 {q(ys, .75):.1f})"
           f"  dmg10 {sum(d['dmg10'] * sc(m) for d, m in X) / len(X):.0f}  fail {sum(d['dmg10'] * sc(m) >= 442 for d, m in X) / len(X):.2f}")
    pr("Tornado: distance from the king (9,3) and from the threat")
    for k in ("TR", "RL", "PRO"):
        X = [(d, m) for m in pops[k] for d in m["dplays"] if d["card"] == "Tornado"]
        if not X: continue
        pr(f"  {k:4s} n={len(X)} d_king med {med([d['d_king'] for d, m in X]):.1f}  share <= 6 {sum(d['d_king'] <= 6 for d, m in X) / len(X):.2f}"
           f"  d_near med {med([d['d_near'] for d, m in X])}  dmg10 {sum(d['dmg10'] * sc(m) for d, m in X) / len(X):.0f}")
    pr("Episode-level: elixir spent on defence / threat value, and defended-episode failure (lane dmg >= 1000 live HP)")
    for k, ms in pops.items():
        for sb in ("3-5", "5-8", "8+"):
            E = [(e, m) for m in ms for e in m["eps"] if size_b(e["vmax"]) == sb and e["n_def"]]
            if not E: continue
            ratio = med([e["el_def"] / e["vmax"] for e, m in E]); over = sum(e["el_def"] > e["vmax"] + .5 for e, m in E) / len(E)
            fail = sum(e["dmg"] * sc(m) >= 1000 for e, m in E) / len(E)
            R.setdefault("D4ep", {})[f"{k}|{sb}"] = dict(n=len(E), spend_ratio=ratio, overspend=over, fail=fail, n_def=sum(e["n_def"] for e, m in E) / len(E))
            pr(f"  {k:4s} {sb:4s} defended n={len(E):5d} spend/value med {ratio:.2f}  spent > value {over:.2f}  cards/ep {sum(e['n_def'] for e, m in E) / len(E):.2f}  fail(>=1000) {fail:.2f}")
    pr("First defensive card by threat type (share):")
    for k in ("TR", "RL", "PRO"):
        for typ, f in (("building-target", lambda e: e["bt"]), ("air", lambda e: e["air"] and not e["bt"]), ("other ground", lambda e: not e["air"] and not e["bt"])):
            c = collections.Counter(e["first_card"] for m in pops[k] for e in m["eps"] if f(e) and e["vmax"] >= 5 and e["first_card"])
            n = sum(c.values())
            if n: pr(f"  {k:4s} {typ:15s} n={n:5d} " + "  ".join(f"{x} {v / n:.2f}" for x, v in c.most_common(8)))

    # ------------------------------------------------------------ D5 damage accounting
    pr("\n## D5 damage accounting: every drop of my tower HP, labelled by the bot's response state in that lane at that moment")
    for k in ("TR", "RL", "PRO"):
        for res in ("LOSS", "WIN"):
            ms = [m for m in pops[k] if m["res"] == res]
            if not ms: continue
            lab = collections.Counter(); phs = collections.Counter(); cards = collections.Counter(); tot = 0
            for m in ms:
                for c in m["chunks"]:
                    d = c["d"] * sc(m); tot += d; lab[c["lab"]] += d; phs[c["ph"]] += d
                    for n, v in c["att"].items(): cards[n] += v * sc(m)
            R.setdefault("D5", {})[f"{k}|{res}"] = dict(n=len(ms), per_match=tot / len(ms), lab={l: v / len(ms) for l, v in lab.items()},
                                                       ph={p: v / len(ms) for p, v in phs.items()}, cards={c: v / len(ms) for c, v in cards.most_common(15)})
            pr(f"{k:4s} {res:4s} n={len(ms)} tower HP lost/match {tot / len(ms):.0f}")
            pr("     by response state: " + "  ".join(f"{l} {v / len(ms):.0f} ({100 * v / tot:.0f}%)" for l, v in lab.most_common()))
            pr("     by phase: " + "  ".join(f"{p} {v / len(ms):.0f}" for p, v in sorted(phs.items())))
            pr("     by enemy card: " + "  ".join(f"{c} {v / len(ms):.0f}" for c, v in cards.most_common(12)))
    with open(HERE + "out/results.json", "w") as fh: json.dump(R, fh, indent=1, default=str)
    with open(HERE + "out/report.txt", "w") as fh: fh.write("\n".join(OUTL) + "\n")




if __name__ == "__main__":
    main()
