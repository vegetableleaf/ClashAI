"""report.md generator for review.py. review.py parses logs into rows (matches.jsonl); every statistic lives here.

Units and estimators
  match factors   : share of losses vs share of wins with the factor (Newcombe 95% CI); wins at stake = (WR absent - WR present) x n present.
  episode factors : threat episodes (review.py: >= 7 elixir of enemy bodies at own y <= 16). Effect = Mantel-Haenszel risk difference
                    WITHIN matches (each match is a stratum, so the opponent and the checkpoint are held fixed), 95% CI = match-cluster
                    bootstrap. Crowns at stake = MH difference in tower falls x episodes with the factor; wins = crowns x the measured
                    value of the first conceded crown (WR(0 conceded) - WR(1 conceded)).
  X-Bow factors   : same MH design on locked X-Bows, outcome = enemy tower HP lost in the 20 s after placement.
All 'at stake' numbers are associational CEILINGS (they assume the factor causes the gap); the fix proposals give smaller expected sizes.
"""
import sys, os, math, json, random, collections, datetime
import review as V
from review import wilson, newcombe, boot_diff, mean, med, f2, pc, family, ph

sys.path.insert(0, V.MAIN + "scratchpad/gauntlet/L73/live_eval")
from live_eval import classify     # opponent class from public cards (live_eval RULES)

LINEAGE_FROM = "20261004_205129"           # first R1e live log: R-lineage population for the factor analysis
PRINCESS_HP = 4424
BAD_HP = 1000                              # a threat episode is 'lost' if my towers lose >= 1000 HP (or a tower falls) in it + 3 s
CHEAP = ("Skeletons", "Log", "Knight", "IceWizard", "Tornado", "Tesla")


def valid(r): return r.get("result") in ("WIN", "LOSS", "DRAW") and not r.get("dry_run") and (r.get("n_plays") or 0) >= 5
def lineage(r): return r.get("ts", "") >= LINEAGE_FROM


def wl(Q):
    w = sum(r["result"] == "WIN" for r in Q); l = sum(r["result"] == "LOSS" for r in Q)
    return w, l, len(Q) - w - l, len(Q)


# ------------------------------------------------------------------ within-match (Mantel-Haenszel) difference, match-cluster bootstrap
def mh(units, f, y, B=500, seed=7):
    """-> (MH difference of mean y between f and not-f units within matches, lo, hi, n_strata_informative)."""
    by = collections.defaultdict(lambda: [0, 0.0, 0, 0.0])
    for u in units:
        s = by[u["_file"]]; v = float(y(u))
        if f(u): s[0] += 1; s[1] += v
        else: s[2] += 1; s[3] += v
    S = [s for s in by.values() if s[0] and s[2]]
    def est(ss):
        num = den = 0.0
        for n1, y1, n0, y0 in ss:
            w = n1 * n0 / (n1 + n0); num += w * (y1 / n1 - y0 / n0); den += w
        return num / den if den else float("nan")
    e = est(S); rng = random.Random(seed); bs = sorted(est([S[rng.randrange(len(S))] for _ in S]) for _ in range(B)) if S else []
    return e, (bs[int(.025 * B)] if bs else float("nan")), (bs[int(.975 * B) - 1] if bs else float("nan")), len(S)


def label(lo, hi, direction=+1):
    """(a) CI excludes 0 in the claimed direction, (c) CI excludes 0 against it, (b) otherwise."""
    if lo != lo: return "(b)"
    if (lo > 0 and direction > 0) or (hi < 0 and direction < 0): return "(a)"
    if (hi < 0 and direction > 0) or (lo > 0 and direction < 0): return "(c)"
    return "(b)"


def ex_units(units, f, bad, k=3, span=True):
    out = []
    for u in units:
        if f(u) and bad(u) and u["_res"] == "LOSS":
            out.append(f"{u['_file'][10:25]} t{u['t']}-{u.get('t_end', u['t'] + 400)}")
        if len(out) >= k: break
    return out


# ------------------------------------------------------------------ factor builders
def efactor(name, defin, TH, f, cv, pro=None, direction=+1, extra=None):
    pres = [e for e in TH if f(e)]
    if len(pres) < 10: return None
    d, lo, hi, ns = mh(TH, f, lambda e: e["bad"])
    df, flo, fhi, _ = mh(TH, f, lambda e: e["tower_fell"])
    nL = sum(e["_res"] == "LOSS" for e in TH); nW = sum(e["_res"] == "WIN" for e in TH)
    kL = sum(e["_res"] == "LOSS" for e in pres); kW = sum(e["_res"] == "WIN" for e in pres)
    crowns = df * len(pres) if df == df else float("nan")
    lab = label(lo, hi, direction)
    det = [f"pooled lost-episode rate with/without: {pc(mean([e['bad'] for e in pres]))} / {pc(mean([e['bad'] for e in TH if not f(e)]))}; "
           f"tower-fall MH difference {pc(df, 1)} [{pc(flo, 1)}, {pc(fhi, 1)}]; informative matches {ns}"]
    if pro: det.append("pros (same definition, pro_baseline.json): " + pro)
    det += extra or []
    return dict(name=name, d=defin, mh=(d, lo, hi), inL=f"{kL}/{nL} eps ({pc(kL / nL)})", inW=f"{kW}/{nW} eps ({pc(kW / nW)})",
                eff=f"MH P(lost episode) {pc(d, 1)} [{pc(lo, 1)}, {pc(hi, 1)}]", crowns=f"{f2(max(crowns, 0), 1)}",
                wins=max(crowns, 0) * cv if (crowns == crowns and lab == "(a)") else (0.0 if lab == "(c)" else float("nan")),
                label=lab, det=det, ex=ex_units(TH, f, lambda e: e["bad"]))


def mfactor(name, defin, Q, f, direction=+1, extra=None, ex=None, stake=None):
    a = [r for r in Q if r["result"] in ("WIN", "LOSS")]
    L_ = [r for r in a if r["result"] == "LOSS"]; W_ = [r for r in a if r["result"] == "WIN"]
    pres = [r for r in a if f(r)]; absn = [r for r in a if not f(r)]
    kl = sum(map(f, L_)); kw = sum(map(f, W_)); d, lo, hi = newcombe(kl, len(L_), kw, len(W_))
    wp = mean([r["result"] == "WIN" for r in pres]); wa = mean([r["result"] == "WIN" for r in absn])
    lab = label(lo, hi, direction)
    w = stake if stake is not None else ((wa - wp) * len(pres) if (wp is not None and wa is not None and lab == "(a)") else (0.0 if lab == "(c)" else float("nan")))
    return dict(name=name, d=defin, inL=f"{kl}/{len(L_)} ({pc(kl / len(L_))})", inW=f"{kw}/{len(W_)} ({pc(kw / len(W_))})",
                eff=f"L-W {pc(d, 1)} [{pc(lo, 1)}, {pc(hi, 1)}]; WR with/without {pc(wp)} / {pc(wa)}", crowns="-", wins=w, label=lab,
                det=extra or [], ex=ex or [])


# ------------------------------------------------------------------ report
def write(rows, path):
    L = []; P = L.append
    PB = json.load(open(V.PRO)) if os.path.exists(V.PRO) else None
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    allv = [r for r in rows if valid(r)]
    Q = [r for r in allv if lineage(r) and r.get("valid_state")]
    for r in Q: r["_cls"] = classify(r.get("opp_cards") or [])
    W_, L_ = [r for r in Q if r["result"] == "WIN"], [r for r in Q if r["result"] == "LOSS"]
    TH, XB = [], []
    for r in Q:
        for e in r.get("threats", []):
            e = dict(e, _file=r["file"], _res=r["result"]); e["bad"] = e["hp_lost"] >= BAD_HP or e["tower_fell"]; TH.append(e)
        for x in r.get("xbows", []): XB.append(dict(x, _file=r["file"], _res=r["result"]))
    globals().update(_TH=TH, _XB=XB, _Q=Q)
    src = collections.Counter(r.get("result_src") for r in allv)
    agree = sum(1 for r in rows if r.get("ladder") and r.get("derived") and r["ladder"] == r["derived"]); both = sum(1 for r in rows if r.get("ladder") and r.get("derived"))
    nagree = sum(1 for r in rows if r.get("ladder") and r.get("nav") and r["ladder"] == r["nav"]); nboth = sum(1 for r in rows if r.get("ladder") and r.get("nav"))
    P(f"# Live loss review (L74, standing) -- generated {now}")
    P("")
    P(f"Ledger: {len(rows)} logs analysed (analyzed.txt); rows in matches.jsonl; tool review.py + report.py (+ pro_baseline.py, run once). "
      f"Valid matches (result known, >= 5 plays, not dry-run): {len(allv)}. **Factor population = R-lineage** (logs >= {LINEAGE_FROM}: R1e and later) "
      f"with board state: **{len(Q)} matches, {len(W_)} W / {len(L_)} L / {len(Q) - len(W_) - len(L_)} D**; {len(TH)} threat episodes; {len(XB)} confirmed X-Bows.")
    P("")
    P(f"**Result rule:** the ladder line in L70/live/overnight.out after the log's 'played' line; else the ladder_nav 'outcome' event within "
      f"[end-20 s, end+300 s]; else tower-derived (crowns; equal crowns -> lower minimum tower HP loses). Sources: {dict(src)}. "
      f"Agreement where both exist: nav vs ladder {nagree}/{nboth}; tower-derived vs ladder {agree}/{both} "
      f"(error {pc(1 - agree / both, 1) if both else 'n/a'}, always toward WIN: the final blow is never in the log). Trophy deltas exist for "
      f"{sum(r.get('trophy_delta') is not None for r in rows)} matches only -> not used.")
    P("")
    summary_at = len(L)
    # ---------------------------------------------------------- 1 families
    P("## 1. Win/loss per checkpoint family (all valid matches)")
    P("")
    P("| family | matches | W-L-D | win rate [95% CI] | with board state | first log | last log |")
    P("|---|---|---|---|---|---|---|")
    fam = collections.defaultdict(list)
    for r in allv: fam[family(r)].append(r)
    for k, v in sorted(fam.items(), key=lambda kv: min(r["ts"] for r in kv[1])):
        w, l, d, n = wl(v); lo, hi = wilson(w, n)
        P(f"| {k} | {n} | {w}-{l}-{d} | {pc(w / n)} [{pc(lo)}, {pc(hi)}] | {sum(bool(r.get('valid_state')) for r in v)} | {min(r['ts'] for r in v)} | {max(r['ts'] for r in v)} |")
    P("")
    P("Older families (gen_s0, league1c, rseries_r1) mostly lack board state in their logs (no decision/frame events), so the factor analysis uses the R-lineage.")
    P("")
    # ---------------------------------------------------------- 2 anatomy
    P("## 2. How the R-lineage loses")
    P("")
    cr = collections.Counter((r["crowns_me"], r["crowns_opp"]) for r in L_)
    three = sum(r["crowns_opp"] >= 3 for r in L_); zero = sum(r["crowns_me"] == 0 for r in L_)
    ot = [r for r in Q if r["dur_s"] >= 186]; otw = sum(r["result"] == "WIN" for r in ot)
    fcl = collections.Counter(ph(int(r["first_crown_s"] * 20)) if r["first_crown"] == "opp" else ("bot first" if r["first_crown"] == "me" else "none") for r in L_)
    wbc = {k: (mean([r["result"] == "WIN" for r in Q if r["crowns_opp"] == k]), sum(r["crowns_opp"] == k for r in Q)) for k in range(4)}
    wbt = {k: (mean([r["result"] == "WIN" for r in Q if r["crowns_me"] == k]), sum(r["crowns_me"] == k for r in Q)) for k in range(4)}
    cv = (wbc[0][0] - wbc[1][0]) if wbc[0][1] and wbc[1][1] else .5
    cvt = (wbt[1][0] - wbt[0][0]) if wbt[0][1] and wbt[1][1] else .5
    gol = [r for r in L_ if r["crowns_opp"] >= 3]
    P(f"* {len(L_)} losses. The bot scored **0 crowns in {zero} ({pc(zero / len(L_))})**; three-crowned in {three} ({pc(three / len(L_))}; "
      f"{sum(r['_cls'] == 'Golem' for r in gol)} of them vs Golem). Score lines (bot-opp): " + ", ".join(f"{a}-{b} {n}" for (a, b), n in cr.most_common(7)) + ".")
    P(f"* Opponent's first crown came in: " + ", ".join(f"{k} {v}" for k, v in fcl.most_common()) + ". "
      f"{len(ot)}/{len(Q)} matches reach overtime ({pc(len(ot) / len(Q))}); OT win rate {pc(otw / len(ot)) if ot else 'n/a'}.")
    P("* Win rate by crowns conceded: " + ", ".join(f"{k}: {pc(v[0])} (n={v[1]})" for k, v in wbc.items() if v[1]) +
      f". Value of the first conceded crown (used for 'wins at stake'): **{f2(cv)}**. Value of the first crown TAKEN: {f2(cvt)}.")
    P("* Tower HP per match (taken / dealt), losses vs wins: " + "; ".join(
        f"{p}: L {f2(mean([r['dmg'][p]['taken'] for r in L_ if p in r['dmg']]), 0)} / {f2(mean([r['dmg'][p]['dealt'] for r in L_ if p in r['dmg']]), 0)} vs "
        f"W {f2(mean([r['dmg'][p]['taken'] for r in W_ if p in r['dmg']]), 0)} / {f2(mean([r['dmg'][p]['dealt'] for r in W_ if p in r['dmg']]), 0)}" for p in ("1x", "2x", "OT")))
    P("")
    # ---------------------------------------------------------- 3 the elixir economy vs pros
    mins = sum(r["dur_s"] for r in Q) / 60
    cc = collections.Counter()
    for r in Q: cc.update(r.get("card_ctx", {}))
    P("## 3. The economy, measured against pros (same definitions)")
    P("")
    if PB:
        T = PB["threat"]
        elL = med([e["el"] for e in TH if e["_res"] == "LOSS"]); elW = med([e["el"] for e in TH if e["_res"] == "WIN"])
        lt4 = mean([e["el"] is not None and e["el"] < 4 for e in TH])
        bad_lt4 = mean([e["bad"] for e in TH if e["el"] is not None and e["el"] < 4]); bad_ge4 = mean([e["bad"] for e in TH if e["el"] is not None and e["el"] >= 4])
        P("| measure | bot (R-lineage live) | pros (2,244 icebow sides) |")
        P("|---|---|---|")
        P(f"| own elixir when a push arrives (median) | **{f2(med([e['el'] for e in TH]), 1)}** (losses {f2(elL, 1)}, wins {f2(elW, 1)}) | **{f2(T['el_med'], 1)}** |")
        P(f"| share of pushes met with < 4 elixir | **{pc(lt4)}** | {pc(T['el_lt4'])} |")
        P(f"| lost-episode rate at < 4 / >= 4 elixir | **{pc(bad_lt4)} / {pc(bad_ge4)}** | {pc(T['bad_el_lt4'][0])} / {pc((T['bad_el_4_7'][0] * T['bad_el_4_7'][1] + T['bad_el_ge7'][0] * T['bad_el_ge7'][1]) / (T['bad_el_4_7'][1] + T['bad_el_ge7'][1]))} |")
        P(f"| lost-episode rate overall | {pc(mean([e['bad'] for e in TH]))} | {pc(T['bad'][0])} |")
        P(f"| first play within 2 s of a push | {pc(mean([e['rsp'] is not None and e['rsp'] <= 2 for e in TH]))} (taps) | {pc(T['rsp_le2'])} (deploys) |")
        P(f"| >= 7 elixir spent in the 10 s before a push | {pc(mean([e['pre10'] >= 7 for e in TH]))} | {pc(T['pre10_ge7'])} |")
        P(f"| elixir at play 1x / 2x / OT (bot = raw at TAP; +0.46 / +0.93 at deploy) | " + " / ".join(f2(mean([r['el_at_play'][p] for r in Q if r['el_at_play'][p] is not None]), 2) for p in ("1x", "2x", "OT"))
          + " | " + " / ".join(f2(PB['el_at_play'][p], 2) for p in ("1x", "2x", "OT")) + " |")
        P(f"| elixir wasted at the cap per match | {f2(mean([sum(v[2] for v in r['leak'].values()) for r in Q]), 1)} | {f2(PB['waste_per_match'], 1)} |")
        P(f"| plays/min with < 5 elixir: quiet / pressured | **{f2(sum(v for k, v in cc.items() if k.endswith('quiet|lo')) / mins)} / {f2(sum(v for k, v in cc.items() if k.endswith('press|lo')) / mins)}** | "
          f"{f2(sum(v for k, v in PB['card_ctx_per_min'].items() if k.endswith('quiet|lo')))} / {f2(sum(v for k, v in PB['card_ctx_per_min'].items() if k.endswith('press|lo')))} |")
        P(f"| plays/min with >= 5 elixir: quiet / pressured | {f2(sum(v for k, v in cc.items() if k.endswith('quiet|hi')) / mins)} / {f2(sum(v for k, v in cc.items() if k.endswith('press|hi')) / mins)} | "
          f"{f2(sum(v for k, v in PB['card_ctx_per_min'].items() if k.endswith('quiet|hi')))} / {f2(sum(v for k, v in PB['card_ctx_per_min'].items() if k.endswith('press|hi')))} |")
        P(f"| Rocket in hand (share of time) | {pc(mean([r['rocket_in_hand_share'] for r in Q]))} | {pc(PB['rocket_in_hand'])} |")
        P(f"| locked X-Bows placed with opponent public elixir >= 7 | {pc(mean([(x['opp_el'] or 0) >= 7 for x in XB if x['lock']]))} | {pc(PB['xbow']['opp_el_ge7'])} |")
        P("")
        top = sorted(((k, cc[k] / mins - PB["card_ctx_per_min"].get(k, 0)) for k in cc), key=lambda kv: -kv[1])[:6]
        P("Biggest per-card excess over pros (plays/min, card|context|elixir<5=lo): " + ", ".join(f"{k} +{f2(v)}" for k, v in top) + ". "
          "Biggest deficits: " + ", ".join(f"{k} {f2(v)}" for k, v in sorted(((k, cc.get(k, 0) / mins - v) for k, v in PB["card_ctx_per_min"].items()), key=lambda kv: kv[1])[:5]) + ".")
        P("")
        P("Per checkpoint family (the pattern is not one checkpoint's quirk):")
        P("")
        P("| family | matches | gate tau (1x/2x/OT) | anti-leak | win rate | elixir at push start (median) | pushes met < 4 | tap elixir 1x / 2x / OT | plays/min at < 5 elixir |")
        P("|---|---|---|---|---|---|---|---|---|")
        fq = collections.defaultdict(list)
        for r in Q: fq[family(r)].append(r)
        for k, v in sorted(fq.items(), key=lambda kv: min(r["ts"] for r in kv[1])):
            fs = {r["file"] for r in v}; E = [e for e in TH if e["_file"] in fs]
            lo_pm = sum(x for r in v for kk, x in r.get("card_ctx", {}).items() if kk.endswith("|lo")) / max(1, sum(r["dur_s"] for r in v) / 60)
            taus = collections.Counter(str(r['cfg'].get('tau_phase') or r['cfg'].get('tau')) for r in v).most_common(1)[0][0]; al = collections.Counter(str(r['cfg'].get('anti_leak')) for r in v).most_common(1)[0][0]
            P(f"| {k} | {len(v)} | {taus} | {al} | {pc(mean([r['result'] == 'WIN' for r in v]))} | {f2(med([e['el'] for e in E]), 1)} | {pc(mean([e['el'] is not None and e['el'] < 4 for e in E]))} | "
              + " / ".join(f2(mean([r['el_at_play'][p] for r in v if r['el_at_play'][p] is not None]), 1) for p in ("1x", "2x", "OT")) + f" | {f2(lo_pm, 2)} |")
        P("")
        P("Reading: total plays/min are the same as pros ("+ f"{f2(sum(cc.values()) / mins, 1)} vs {f2(sum(PB['card_ctx_per_min'].values()), 1)}" + "), but the bot plays "
          "its cheap cards EARLY -- at < 5 elixir -- two to three times as often, so it never holds a bank: it meets 70% of pushes with < 4 elixir and almost never "
          "has the 6 elixir for a Rocket. Pros sit at full elixir far more (they waste more), so 'elixir leak' is not what separates the bot from pros. "
          "The push-Rocket worker measured the same model at elixir 5.2 at big-push start in SIM vs 3.0-3.6 live, and its follow-up A found the live "
          "26-tick extrapolation raises the gate's p_play by a median +0.05..+0.09 relative to the training input path (live_path_test.out) -- a "
          "live-only push toward earlier plays. Which of the two (extrapolation, or live opponents' pressure) drives the live trickle is UNTESTED (proposal P1 measures it).")
        P("")
        P("Natural experiment in the family table (b, confounded by checkpoint): the families that run tau_phase (.35/.45/.55) tap at 1-2 elixir MORE in 2x/OT "
          "than R1e (flat .35), while 1x (tau .35 in both) barely moves, and they make fewer low-elixir plays. The gate threshold sets the bank; "
          "the gate decision is the lever for P1.")
    P("")
    # ---------------------------------------------------------- 4 ranked factors
    F = []
    add = lambda x: F.append(x) if x else None
    T = PB["threat"] if PB else None
    low = lambda e: e["el"] is not None and e["el"] < 4
    rob = []
    for nm_, S in (("1x only", [e for e in TH if e["ph"] == "1x"]), ("pushes >= 13 elixir", [e for e in TH if e["v"] >= 13]), ("no air", [e for e in TH if not e["air"]]),
                   ("R1e", [e for e in TH if e["_file"] < "live_play_20261008_04"]), ("stack2k + towerref_w2", [e for e in TH if e["_file"] >= "live_play_20261008_04"])):
        d_, l_, h_, _ = mh(S, low, lambda e: e["bad"]); rob.append(f"{nm_} {pc(d_, 1)} [{pc(l_, 1)}, {pc(h_, 1)}] (n={len(S)})")
    add(efactor("Low elixir when a push arrives (< 4)", "own elixir < 4 at threat-episode start", TH, low, cv,
                pro=f"{pc(T['el_lt4'])} of pro episodes start < 4 and their lost rate does not depend on it ({pc(T['bad_el_lt4'][0])} vs {pc(T['bad_el_4_7'][0])} at 4-7)" if T else None,
                extra=["robustness, MH lost-episode difference in subsets: " + "; ".join(rob),
                       f"only {pc(mean([e['pre10'] == 0 for e in TH]))} of pushes arrive after 10 s without a bot play (the bot is almost never banking when a push comes)"]))
    add(efactor("Air unit in the push", "an air unit among the threat bodies", TH, lambda e: e["air"], cv))
    add(efactor("X-Bow committed <= 10 s before a push", "a confirmed X-Bow in the 10 s before threat start", TH, lambda e: e["off_xbow10"], cv))
    add(efactor("Offence spending before a push (>= 3 elixir)", "elixir on locked X-Bows or spells aimed past own y 18 in the 10 s before threat start", TH, lambda e: e.get("pre_off", 0) >= 3, cv))
    add(efactor("Opponent public elixir lead >= 3 at push start", "opponent_elixir_estimate - own elixir >= 3", TH, lambda e: e["opp_el"] is not None and e["el"] is not None and e["opp_el"] - e["el"] >= 3, cv))
    add(efactor("Tornado as the first answer", "the first play after threat start is Tornado", TH, lambda e: bool(e.get("first")) and e["first"][0][0] == "Tornado", cv))
    slow = lambda e: e["rsp"] is None or e["rsp"] > 2
    by_size = "; ".join(f"push {a}-{b if b < 99 else '+'} elixir: lost {pc(mean([e['bad'] for e in TH if a <= e['v'] < b and not slow(e)]))} answered <= 2 s vs "
                        f"{pc(mean([e['bad'] for e in TH if a <= e['v'] < b and slow(e)]))} slower" for a, b in ((7, 10), (10, 13), (13, 99)))
    add(efactor("Slow first answer (> 2 s)", "no play (tap) within 2 s of threat start", TH, slow, cv,
                pro=f"pros answer within 2 s in {pc(T['rsp_le2'])}" if T else None,
                extra=["by push size (pooled): " + by_size + ". Slow answers are not worse at ANY size; the likely reading is that the bot waits on pushes its towers handle."]))
    add(efactor("Heavy spending in the 10 s before a push (>= 7)", "confirmed card elixir in the 10 s before threat start >= 7", TH, lambda e: e["pre10"] >= 7, cv,
                pro=f"pros {pc(T['pre10_ge7'])} of episodes" if T else None))
    add(efactor("Gate below threshold >= 3 s while threatened", "p_play <= its tau for >= 3 s with an affordable card before the first play", [e for e in TH if e.get("below3") is not None], lambda e: e["below3"], cv))
    add(efactor("Sat at full elixir just before a push", ">= 3 s at >= 9.9 elixir in the 15 s before threat start", TH, lambda e: e["leak15"] >= 3, cv))
    # --- end-states one Rocket short
    short = []
    for r in L_:
        tm = r.get("tiebreak_min") or {}
        if 0 < (tm.get("opp") or 0) <= V.ROCKET_DMG:
            d = r["dur_s"]; kind = "regulation end (Rocket -> tie -> OT)" if d < 186 and r["crowns_opp"] < 3 else ("3-crowned" if r["crowns_opp"] >= 3 else ("OT sudden death" if d < 295 else "OT end"))
            short.append((r, kind))
    flip = {"OT sudden death": 1.0, "regulation end (Rocket -> tie -> OT)": (otw / len(ot)) if ot else .5, "OT end": .5, "3-crowned": 0.0}
    kinds = collections.Counter(k for _, k in short)
    stake = sum(flip[k] for _, k in short)
    F.append(dict(name="Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end",
                  d="final enemy lowest-tower HP <= measured Rocket tower damage 497; see section 4b for elixir/Rocket availability",
                  inL=f"{len(short)}/{len(L_)} ({pc(len(short) / len(L_))})", inW="n/a (end state of losses)",
                  eff="by ending: " + ", ".join(f"{k} {v}" for k, v in kinds.items()), crowns=f"{len(short) - kinds['3-crowned']}",
                  wins=stake, label="(a)", det=[f"wins at stake = OT sudden death x1 + regulation end x OT win rate {pc(flip['regulation end (Rocket -> tie -> OT)'])} + OT end x .5 (ceiling: needs 6 elixir + the Rocket on that tower in time)"],
                  ex=[f"{r['file'][10:25]} ({k}, enemy tower {r['tiebreak_min']['opp']} HP)" for r, k in short[:3]]))
    # --- X-Bow into opponent elixir
    off = [x for x in XB if x["lock"]]
    hi7 = lambda x: (x["opp_el"] or 0) >= 7
    d, lo, hi, ns = mh(off, hi7, lambda x: x["dealt20"])
    dd, dlo, dhi, _ = mh(off, hi7, lambda x: x["dealt20"] < 300)
    hp_stake = -d * sum(map(hi7, off)) if d == d else float("nan")
    labx = label(-hi, -lo)
    # empirical HP -> crowns conversion: least-squares slope of crowns taken on enemy tower HP dealt per match
    pts = [(sum(v["dealt"] for v in r["dmg"].values()), r["crowns_me"]) for r in Q if r.get("dmg")]
    mx_, my_ = mean([p[0] for p in pts]), mean([p[1] for p in pts])
    slope = sum((a - mx_) * (b - my_) for a, b in pts) / sum((a - mx_) ** 2 for a, _ in pts)
    F.append(dict(name="Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)", d="enemy tower HP lost in the 20 s after a locked X-Bow, opponent estimate >= 7 vs < 7, within matches",
                  inL=f"{sum(1 for x in off if hi7(x) and x['_res'] == 'LOSS')}/{sum(x['_res'] == 'LOSS' for x in off)} X-Bows", inW=f"{sum(1 for x in off if hi7(x) and x['_res'] == 'WIN')}/{sum(x['_res'] == 'WIN' for x in off)}",
                  eff=f"MH dealt20 {f2(d, 0)} HP [{f2(lo, 0)}, {f2(hi, 0)}]; MH dud rate {pc(dd, 1)} [{pc(dlo, 1)}, {pc(dhi, 1)}]",
                  crowns=f"{f2(hp_stake * slope, 1)} ({f2(hp_stake / 1000, 0)}k HP x {f2(slope * 1000, 3)} crowns/1k HP)", wins=(hp_stake * slope * cvt) if labx == "(a)" else float("nan"), label=labx,
                  det=[f"share of locked X-Bows placed at >= 7: bot {pc(mean([hi7(x) for x in off]))} vs pros {pc(PB['xbow']['opp_el_ge7']) if PB else 'n/a'} "
                       f"(pro dud rate {pc(PB['xbow']['dud_opp_ge7']) if PB else 'n/a'} at >= 7 vs {pc(PB['xbow']['dud_opp_lt7']) if PB else 'n/a'} at < 7; pro counter rebuilt from visible plays)",
                       f"the live counter over-reads by {f2(mean([r['counter_bias']['mean'] for r in Q if r.get('counter_bias')]), 2)} elixir on average (EVAL_ONLY truth, frame logs), so part of the >= 7 share is counter bias",
                       f"HP -> crowns uses the fitted slope of crowns taken on HP dealt per match ({f2(slope * 1000, 3)} crowns per 1,000 HP, {len(pts)} matches); informative matches {ns}"] + xbow_detail(off),
                  ex=[f"{x['_file'][10:25]} t{x['t']}-{x['t'] + 400} opp_el {f2(x['opp_el'], 1)} dealt {x['dealt20']}" for x in off if hi7(x) and x["dealt20"] < 300 and x["_res"] == "LOSS"][:3]))
    # --- match factors
    waste = lambda r: sum(v[2] for v in r["leak"].values())
    F.append(mfactor("Elixir wasted at the cap >= 5 in a match", f"sum over time at >= {V.CAP} elixir of the regen rate", Q, lambda r: waste(r) >= 5,
                     extra=[f"pros waste {f2(PB['waste_per_match'], 1)} per match ({pc(PB['waste_ge5'])} of pro sides >= 5): banking is normal for this deck; the bot's waste comes from gate freezes (next row)" if PB else ""],
                     ex=[f"{r['file'][10:25]} longest stretch at the cap {f2(r['cap_max_s'], 1)} s" for r in sorted(L_, key=lambda r: -waste(r))[:3]]))
    dec = [r for r in Q if r["state_src"] == "decision"]
    F.append(mfactor("Gate freeze >= 10 s at >= 9.5 elixir", "longest run of decisions with p_play < tau and no play at >= 9.5 elixir (decision logs)", dec, lambda r: (r.get("freeze_max_s") or 0) >= 10,
                     extra=["W4 hazard_below_tau at >= 9 elixir (hbt9) targets exactly this and is being deployed"],
                     ex=[f"{r['file'][10:25]} freeze {f2(r['freeze_max_s'], 1)} s" for r in sorted([r for r in dec if r['result'] == 'LOSS'], key=lambda r: -(r.get('freeze_max_s') or 0))[:3]]))
    lo_rate = lambda r: sum(v for k, v in r.get("card_ctx", {}).items() if k.endswith("|lo")) / max(r["dur_s"] / 60, .5)
    medlo = med([lo_rate(r) for r in Q])
    a_, b_ = [lo_rate(r) for r in L_], [lo_rate(r) for r in W_]; dlo_, llo_, hlo_ = boot_diff(a_, b_)
    F.append(mfactor(f"Cheap low-elixir plays above the median ({f2(medlo, 1)}/min at < 5 elixir)", "confirmed plays tapped at < 5 elixir per minute", Q, lambda r: lo_rate(r) > medlo,
                     extra=[f"mean per match L {f2(mean(a_), 2)} vs W {f2(mean(b_), 2)}/min (diff {f2(dlo_, 2)} [{f2(llo_, 2)}, {f2(hlo_, 2)}]); pros {f2(sum(v for k, v in PB['card_ctx_per_min'].items() if k.endswith('|lo')), 2) if PB else 'n/a'}/min",
                            "the match-level link is weak because the whole lineage trickles (section 3); the episode-level cost is the 'low elixir when a push arrives' row"]))
    for c in ("Golem", "Lava Hound", "Balloon"):
        F.append(mfactor(f"Opponent archetype: {c}", "primary class from public cards (live_eval.classify)", Q, lambda r, c=c: r["_cls"] == c))
    F.append(mfactor("Lethal Rocket window not used (>= 3 s)", f"enemy princess <= {V.ROCKET_DMG} HP, Rocket in hand, >= 6 elixir for >= 3 s (or a Rocket tap), no Rocket on that tower", Q,
                     lambda r: any(not w["rocketed"] and (w["t1"] - w["t0"]) >= 60 for w in r.get("lethal", [])),
                     extra=[f"windows {sum(len(r.get('lethal', [])) for r in Q)}: rocketed {sum(w['rocketed'] for r in Q for w in r.get('lethal', []))}, Rocket elsewhere {sum(w['rocket_elsewhere'] for r in Q for w in r.get('lethal', []))}; "
                            f"OT windows {sum(w['ph'] == 'OT' for r in Q for w in r.get('lethal', []))} (rocketed {sum(w['ph'] == 'OT' and w['rocketed'] for r in Q for w in r.get('lethal', []))})",
                            "match-level association runs the other way because lethal windows happen when the bot is ahead; the real cost is the elixir-blocked end-state row"]))
    logs = [s for r in Q for s in r.get("spells", []) if s["name"] == "Log"]; tors = [s for r in Q for s in r.get("spells", []) if s["name"] == "Tornado"]
    F.append(mfactor("Log or Tornado on nothing (>= 2 in a match)", "Log with no enemy ground body in its path (no barrel in flight) or Tornado with no enemy within 5.5 tiles", Q,
                     lambda r: sum(1 for s in r.get("spells", []) if (s["name"] == "Log" and s["n_hit"] == 0 and not s.get("barrel")) or (s["name"] == "Tornado" and s["n_hit"] == 0)) >= 2,
                     extra=[f"Logs on nothing {pc(mean([s['n_hit'] == 0 and not s.get('barrel') for s in logs]))} of {len(logs)}; Tornadoes on nothing {pc(mean([s['n_hit'] == 0 for s in tors]))} of {len(tors)}; "
                            f"Tornado centre on the enemy side {pc(mean([s['Y'] > 16 for s in tors]))} (pros {pc(PB['tornado_enemy_side']) if PB else 'n/a'})"]))
    F.append(mfactor("Unconfirmed play (>= 1 in a match)", "a tapped play the reader never confirmed", Q, lambda r: r["n_unconf"] >= 1))
    F.append(mfactor("Placement error >= 1 tile", "any confirmed play with err_tiles >= 1", Q, lambda r: any(e >= 1 for e in r.get("err_tiles", []))))
    F.append(mfactor("CPU starvation (>= 3 warnings)", "cpu_starved events", Q, lambda r: r["starved"] >= 3))
    F.append(mfactor("Rocket held >= 90% of the match", f"Rocket in hand share of decisions >= .9 (pros {pc(PB['rocket_in_hand']) if PB else 'n/a'} on average)", Q, lambda r: (r.get("rocket_in_hand_share") or 0) >= .9))
    F.append(mfactor("Hero Ice Wizard ability pressed >= 3 times", "ability events", Q, lambda r: r["abil"] >= 3))
    F = [x for x in F if x]
    F.sort(key=lambda x: (-(x["wins"]) if x["wins"] == x["wins"] else 1e9, x["label"]))
    P("## 4. Ranked loss factors")
    P("")
    P(f"Episode rows: MH difference WITHIN matches (opponent and checkpoint held fixed), CI = match-cluster bootstrap; 'lost episode' = my towers lose >= {BAD_HP} HP or a tower falls. "
      f"Wins at stake are associational CEILINGS (episode rows: tower-fall difference x episodes x {f2(cv)}; match rows: (WR without - WR with) x matches with). "
      "Labels: **(a) measured** = behaviour measured and its link to losing has a CI excluding 0; **(b) plausible-untested** = measured behaviour, link not established; "
      "**(c) contradicted** = the CI excludes 0 the other way (the claimed cause goes with winning or with fewer lost episodes). Ranked by wins at stake; (b)/(c) rows carry no stake.")
    P("")
    P("| rank | factor | in losses | in wins | effect [95% CI] | crowns at stake | wins at stake | label |")
    P("|---|---|---|---|---|---|---|---|")
    for i, x in enumerate(F, 1):
        P(f"| {i} | **{x['name']}** | {x['inL']} | {x['inW']} | {x['eff']} | {x['crowns']} | {f2(x['wins'], 1) if x['wins'] == x['wins'] else '-'} | {x['label']} |")
    P("")
    P("Rows overlap: 'low elixir when a push arrives', 'cheap low-elixir plays', 'one Rocket short' and 'offence spending before a push' are views of ONE "
      "mechanism (the spending economy, section 3); 'elixir wasted' and 'gate freeze' are one mechanism (W4). Do not add their stakes.")
    P("")
    P("### 4a. Factor details (examples = log timestamp + tick range in L68/live_reader/live_play_<ts>.jsonl)")
    P("")
    for i, x in enumerate(F, 1):
        P(f"**{i}. {x['name']}** -- {x['d']}")
        for d_ in x.get("det", []):
            if d_: P(f"  * {d_}")
        if x.get("ex"): P("  * examples: " + "; ".join(x["ex"]))
        P("")
    # ---------------------------------------------------------- 4b end-state Rocket availability
    P("### 4b. Why the finishing Rocket did not come (losses ending with the enemy tower <= 497 HP)")
    P("")
    av = [r.get("end_rocket") for r, _ in short if r.get("end_rocket")]
    if av:
        P(f"Last 20 s of those {len(av)} losses: Rocket in hand {pc(mean([a['in_hand'] for a in av]))} of the time; Rocket in hand AND >= 6 elixir "
          f"{pc(mean([a['affordable'] for a in av]))}; matches that EVER had Rocket + 6 elixir in those 20 s: {sum(a['affordable'] > 0 for a in av)}/{len(av)}; "
          f"median of the max elixir reached {f2(med([a['max_el'] for a in av]), 1)}; Rocket taps in the window {sum(a['taps'] for a in av)}.")
        P("The card is there; the elixir is not. The owner's OT lethal-Rocket option only fires when Rocket is affordable, so on these end-states it can act only in the "
          "matches that reached 6 elixir; the economy fix (P1) is what makes the Rocket affordable.")
    P("")
    # ---------------------------------------------------------- 4c archetypes
    P("### 4c. Win rate by opponent class (public cards; live_eval.classify)")
    P("")
    P("| class | n | win rate [95% CI] | 3-crowned | lost-episode rate |")
    P("|---|---|---|---|---|")
    cls = collections.defaultdict(list)
    for r in Q: cls[r["_cls"]].append(r)
    for k, v in sorted(cls.items(), key=lambda kv: -len(kv[1])):
        w = sum(r["result"] == "WIN" for r in v); lo, hi = wilson(w, len(v)); fs = {r["file"] for r in v}
        P(f"| {k} | {len(v)} | {pc(w / len(v))} [{pc(lo)}, {pc(hi)}] | {sum(r['crowns_opp'] >= 3 for r in v)} | {pc(mean([e['bad'] for e in TH if e['_file'] in fs]))} |")
    P("")
    proposals(P, Q, TH, XB, PB, short, flip, cv, cvt, ot, otw)
    limits(P, Q)
    diagnostics(P, Q, L_, W_)
    contra = [x["name"] for x in F if x["label"] == "(c)"]; LOWX = next(x for x in F if x["name"].startswith("Low elixir"))
    S_ = ["## Summary", ""]
    if PB:
        S_.append(f"* **The economy is the main loss mechanism.** The bot meets {pc(mean([e['el'] is not None and e['el'] < 4 for e in TH]))} of pushes with < 4 elixir "
                  f"(pros {pc(PB['threat']['el_lt4'])}); median {f2(med([e['el'] for e in TH]), 1)} vs pros {f2(PB['threat']['el_med'], 1)}. Within the same match, a push met with "
                  f"< 4 elixir is lost {pc(LOWX['mh'][0], 1)} [{pc(LOWX['mh'][1], 1)}, {pc(LOWX['mh'][2], 1)}] more often (absolute); "
                  f"pros show no such penalty. Cause: cheap cards played at < 5 elixir 2-3x as often as pros (same total play rate).")
    av_ = [r['end_rocket'] for r, _ in short if r.get('end_rocket')]
    S_.append(f"* **{len(short)} of {len(L_)} losses ended with the enemy tower within one Rocket**; Rocket was in hand {pc(mean([a['in_hand'] for a in av_]))} of the final 20 s but in hand AND affordable {pc(mean([a['affordable'] for a in av_]))}: the same economy problem.")
    S_.append("* Other measured factors: locked X-Bows into a full opponent elixir bar, air in pushes, Golem/Lava/Balloon matchups, gate freezes at full elixir.")
    S_.append("* **Contradicted** as loss causes on this data: " + "; ".join(contra) + ".")
    S_.append("* Top fix (P1, section 5): measure then remove the live-only early-spending shift (extrapolated gate input) or recalibrate the gate per elixir bucket on pro data.")
    S_.append("")
    L[summary_at:summary_at] = S_
    open(path, "w", encoding="utf8").write("\n".join(L) + "\n")


def xbow_detail(off):
    dud = lambda x: x["dealt20"] < 300
    def rate(f):
        s = [x for x in off if f(x)]
        return f"{pc(mean([dud(x) for x in s]))} dud, mean {f2(mean([x['dealt20'] for x in s]), 0)} HP (n={len(s)})"
    return [f"all locked X-Bows {rate(lambda x: True)}; in losses {rate(lambda x: x['_res'] == 'LOSS')} vs wins {rate(lambda x: x['_res'] == 'WIN')}",
            f"enemy push on my half at placement {rate(lambda x: x['threat_on'])} vs not {rate(lambda x: not x['threat_on'])}",
            f"< 1 elixir left after placing {rate(lambda x: x['el_after'] < 1)} vs >= 1 {rate(lambda x: x['el_after'] >= 1)}",
            "by phase: " + "; ".join(f"{p} {rate(lambda x, p=p: x['ph'] == p)}" for p in ("1x", "2x", "OT")),
            f"a hard counter seen near it before it died {rate(lambda x: bool(x['counters']))}; X-Bow life median {f2(med([x['life'] for x in off]), 1)} s"]


def proposals(P, Q, TH, XB, PB, short, flip, cv, cvt, ot, otw):
    lt4 = mean([e["el"] is not None and e["el"] < 4 for e in TH])
    P("## 5. Fix proposals (learned, or decodings of the model's own learned quantities; nothing scripted; public information only)")
    P("")
    P("Ranked by expected wins. Each is ONE experiment (one change at a time). Expected sizes are (b) estimates below the section-4 ceilings.")
    P("")
    P(f"**P1. Bring live spending timing back to the model's own SIM/pro behaviour (economy).** Targets rows 'low elixir when a push arrives' and "
      f"'one Rocket short'. Step 1 (measurement, cheap, VM): SIM A/B of the live checkpoint with the live 26-tick extrapolation applied to its "
      f"observations vs without, same seeds; if elixir at play / at push start drops toward live (live tap elixir 1x/2x/OT "
      + " / ".join(f2(mean([r['el_at_play'][p] for r in Q if r['el_at_play'][p] is not None]), 1) for p in ("1x", "2x", "OT")) +
      f" vs SIM 7.1/6.6/6.7 measured by W4 on SIM v3 with the live config, HANDOFF), the extrapolation is the live cause. Step 2 (fix, decoding): evaluate the GATE on the non-extrapolated batch (the "
      f"distribution it was trained and calibrated on) while card/cell keep the extrapolated batch; or (learned) fine-tune the gate on extrapolated "
      f"training rows so it is calibrated on the live input. If step 1 shows no extrapolation effect, the cause is the live state mix and the fix is "
      f"learned instead: per-elixir-bucket recalibration of the gate fitted on pro VAL rows (pros' measured play hazard by elixir and pressure, "
      f"section 3), checked first offline (is the gate already calibrated per elixir bucket on pro rows?). "
      f"Proof it worked (live, >= 100 matches): pushes met with < 4 elixir {pc(lt4)} -> <= 45%; median elixir at push start "
      f"{f2(med([e['el'] for e in TH]), 1)} -> >= 4; plays at < 5 elixir per min down >= 30%; lost-episode rate {pc(mean([e['bad'] for e in TH]))} -> <= 30%; "
      f"Rocket+6 elixir in the last 20 s of close losses up; no rise in tower damage taken in 1x. Expected size (b): +3 to +6 pp win rate "
      f"(about 1/3 of the low-elixir ceiling); risk: slower answers -- but slow answers are contradicted as a loss cause (row 'slow first answer').")
    P("")
    P(f"**P2. OT sudden-death and end-game Rocket (pending option + P1).** {len(short)} losses ended with the enemy tower within one Rocket. The owner's "
      f"OT lethal-Rocket option (being deployed) converts only states where Rocket is affordable (section 4b). Proof: share of losses ending one Rocket short "
      f"{pc(len(short) / max(1, sum(r['result'] == 'LOSS' for r in Q)))} -> lower; lethal windows rocketed up; OT win rate {pc(otw / len(ot)) if ot else 'n/a'} up. "
      f"Expected size (b): +1 to +2 pp alone, more on top of P1.")
    P("")
    P("**P3. Beatdown / air matchups (learned data weighting).** Golem / Lava Hound / Balloon are the worst classes (section 4c) and air in a push is the "
      "second-largest episode factor. Fix: up-weight pro rows from games against Golem / Lava / Balloon decks in the imitation data, and add those decks to "
      "the SIM/RL opponent pool. Proof: SIM win rate vs those archetypes (paired seeds) up without loss elsewhere; live class win rate up (needs ~60 matches "
      "per class for +-12 pp). Expected size (b): Golem 31% -> ~40% is about +1 pp overall.")
    P("")
    P("**P4. X-Bow commit timing against the opponent's public elixir (learned).** Locked X-Bows placed into a full opponent bar deal less (section 4 row). "
      "Measure first: offline sensitivity of the X-Bow logit to the opponent-elixir input (perturb +-3 on pro rows); if near zero, add a training weight "
      "on pro X-Bow rows by the opponent-counter context (pros place 46% of X-Bows at >= 7 vs the bot's share in section 3). Also correct the counter's "
      "+0.3 over-read. Proof: share of X-Bows at >= 7 down toward pros, mean 20-s X-Bow damage up, X-Bows per match not down by more than 10%. Expected size (b): small, < 1 pp.")
    P("")
    P("**P5. Gate freeze at full elixir (W4 hbt9, being deployed).** Proof: matches with a >= 10 s freeze at >= 9.5 elixir -> near 0; wasted elixir down; "
      "no rise in lost episodes. Expected size (b): < 1 pp (freeze matches are ~10% of losses).")
    P("")
    P("Not proposed (contradicted or no measured link): faster first answers, less spending right before pushes, fewer unconfirmed plays / placement errors / "
      "CPU starvation, cycling Rocket out of the hand, fewer 'wasted' Logs/Tornadoes -- see their rows.")
    P("")


def limits(P, Q):
    P("## 6. What this tool cannot measure yet")
    P("")
    P("* Opponent card plays and their timing are inferred from first sightings of enemy bodies; spells without a projectile (Earthquake, Lightning, Poison, Freeze) "
      "are invisible, so 'X-Bow killed by a spell' and opponent spell cycles are not measured.")
    P(f"* Enemy body values (threat episodes, spell hits): the reader labels spawned children with the parent card, so review.py values a body at "
      f"card value x its max_hp / the card's largest max_hp in the match, and Graveyard / Goblin Barrel bodies per unit (L74 econ2 fix; "
      f"REVIEW_BODY_FIX={'on' if V.BODY_FIX else 'OFF'}). Before the fix a Witch's skeletons counted 5 elixir each.")
    P("* Causality: every 'at stake' number is associational. Episode rows hold the match fixed (MH) but not the moment-to-moment situation; only an A/B can prove a fix.")
    P("* The 26-tick forecast's own error (model_bodies vs the next raw state) is not measured here (model bodies carry no entity address).")
    P("* Hand cycle / next card: logs carry the 4-card hand only; 'Rocket stuck' is measured as time in hand, not as cycle position.")
    P("* Tesla/Knight kiting and pull-to-centre quality, Tornado pulls into King/Tesla range, Ice Wizard ability value: positions are logged, but no hit/damage "
      "attribution per defender exists in the logs.")
    P("* Trophies: logged for a handful of matches only (the ladder_nav OCR prints totals rarely).")
    P("* Older families (gen_s0 / league1c / rseries_r1) have results but mostly no board state.")
    P("* Pro baselines come from pro-vs-pro replays (stronger opponents, lower tower levels): rates are comparable in kind, not in absolute value.")
    P("")


def diagnostics(P, Q, L_, W_):
    P("## 7. Diagnostics")
    P("")
    sl = collections.defaultdict(lambda: [0.0, 0.0])
    for r in Q:
        for p, v in r.get("regen_slope", {}).items(): sl[p][0] += v[0]; sl[p][1] += v[1]
    P("* Elixir regen measured from no-play intervals (elixir per 2.8 s): " + ", ".join(f"{p} {f2(v[0] / v[1] * 56, 2) if v[1] else 'n/a'}" for p, v in sl.items()) + " (constants used: 1 / 2 / 2).")
    cb = [r["counter_bias"] for r in Q if r.get("counter_bias") and r["counter_bias"]["n"] > 20]
    if cb:
        P(f"* Opponent elixir counter vs EVAL_ONLY truth ({len(cb)} frame-log matches): bias {f2(mean([c['mean'] for c in cb]), 2)}, mean abs error {f2(mean([c['mae'] for c in cb]), 2)} elixir. Diagnostic only, never an input or a factor.")
    P(f"* Plays tapped before the previous play confirmed: {sum(r.get('pending_plays', 0) for r in Q)} in {len(Q)} matches. Play-event elixir is the RAW elixir at the tap (checked 597/597).")
    P(f"* Hero Ice Wizard ability presses per match L {f2(mean([r['abil'] for r in L_]))} vs W {f2(mean([r['abil'] for r in W_]))}.")
    P("")
