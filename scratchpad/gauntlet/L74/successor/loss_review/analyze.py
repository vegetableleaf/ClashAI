"""Successor loss review (10-17 night): Mark CXXXVIII (live since 13:29) vs Mark CXXIV's last 200 ladder matches.
Reads loss_review/matches.jsonl rows (review.py features), extras.jsonl (ingest.py) and overnight.out (results, trophy deltas,
trophy totals). Writes report_<cohort>.md here with report.py's own factor tables, and prints the comparison tables.

  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/successor/loss_review/analyze.py
"""
import collections, json, math, os, re, sys
LR = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/loss_review/"
sys.path.insert(0, LR); sys.path.insert(0, "C:/Users/benpe/ClashBot/")
import review as V
import report as R
from scratchpad.gauntlet.L74.livecal.census import unfavorable

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
SWITCH = "20261017_132900"
KING_LV = {6408: 14, 7032: 15, 7728: 16}


def ladder():
    """log -> dict(res, delta, start): overnight.out summary line names the log, the next result line carries the delta; start =
    the last '[ladder] trophies: N total' read, rolled forward by the deltas since that read."""
    out, last, est = {}, None, None
    for line in open(V.OVN, encoding="utf8", errors="replace"):
        m = re.match(r"\[ladder\] trophies: (\d+) total", line)
        if m: est = int(m[1]); continue
        if line.startswith("{") and '"log"' in line:
            try: last = os.path.basename(json.loads(line)["log"].replace("\\", "/"))
            except (ValueError, KeyError): last = None
            continue
        m = re.match(r"\[ladder\] result: (\w+).*?trophies ([+-]?\d+)", line)
        if m and last:
            out[last] = dict(res=m[1], delta=int(m[2]), start=est)
            if est is not None: est += int(m[2])
            last = None
    return out


def wil(k, n):
    lo, hi = V.wilson(k, n); return f"{k / n:.1%} [{lo:.1%}, {hi:.1%}]" if n else "n/a"


def mean(v): v = [x for x in v if x is not None]; return sum(v) / len(v) if v else float("nan")


def load():
    names, costs, uv = V._catalog(); V.NAME.update(names); V.NCOST.update(costs); V.UV.update(uv)
    X = {}
    for l in open(HERE + "extras.jsonl"):
        x = json.loads(l); X[x["file"]] = x
    rows = []
    for l in open(V.ROWS):
        if '"file": "live_play_2026101' not in l[:60]: continue
        r = json.loads(l)
        if r["file"] in X: rows.append(r)
    V.resolve(rows)
    lad = ladder()
    out = []
    for r in rows:
        x = X[r["file"]]; L = lad.get(r["file"])
        if not L or r.get("dry_run") or (r.get("n_plays") or 0) < 5 or not r.get("valid_state"): continue
        r.update(mark=x["mark"], result=L["res"], delta=L["delta"], start=L["start"])
        k = max((t[0] for t in x["opp_towers"]), default=None)
        r["opp_tower_lv"] = KING_LV.get(k, None)
        r["opp_king_hp"] = k
        lv = [v for vs in x["opp_card_levels"].values() for v in vs if v and v > 0]
        r["opp_card_lv"] = mean(lv) if lv else None
        r["opp_card_lv16"] = (sum(v >= 16 for v in lv) / len(lv)) if lv else None
        r["_cls"] = R.classify(r.get("opp_cards") or [])
        r["unfav"] = unfavorable(r.get("opp_cards") or [])
        out.append(r)
    return out


def summary(name, Q):
    w = sum(r["result"] == "WIN" for r in Q); n = len(Q)
    dw = mean([r["delta"] for r in Q if r["result"] == "WIN"]); dl = mean([r["delta"] for r in Q if r["result"] == "LOSS"])
    st = [r["start"] for r in Q if r["start"]]
    print(f"\n== {name}: {n} matches {Q[0]['ts']}..{Q[-1]['ts']}, win {wil(w, n)}, trophies/match {mean([r['delta'] for r in Q]):+.2f}, "
          f"win +{dw:.1f} / loss {dl:.1f} (break-even win rate {-dl / (dw - dl):.1%}), trophies {min(st) if st else '-'}..{max(st) if st else '-'}")
    return dw, dl


def table(title, Q, key, order=None):
    g = collections.defaultdict(list)
    for r in Q: g[key(r)].append(r)
    n = len(Q); base = mean([r["result"] == "WIN" for r in Q])
    dw = mean([r["delta"] for r in Q if r["result"] == "WIN"]); dl = mean([r["delta"] for r in Q if r["result"] == "LOSS"])
    print(f"  {title}: class | n (share) | win [95% CI] | trophies/match | net trophies per match of ALL matches | lost vs the rest (per match of all)")
    ks = order or sorted(g, key=lambda k: -len(g[k]))
    res = {}
    for k in ks:
        v = g.get(k, [])
        if not v: continue
        w = sum(r["result"] == "WIN" for r in v)
        rest = [r for r in Q if key(r) != k]; wr_rest = mean([r["result"] == "WIN" for r in rest])
        net = sum(r["delta"] for r in v) / n
        gap = len(v) / n * (wr_rest - w / len(v)) * (dw - dl)          # trophies/match recovered if this class won like the rest
        res[k] = dict(n=len(v), wr=w / len(v), net=net, gap=gap)
        print(f"    {str(k)[:28]:28s} | {len(v):3d} ({len(v) / n:5.1%}) | {wil(w, len(v)):22s} | {mean([r['delta'] for r in v]):+6.1f} | {net:+6.2f} | {gap:+6.2f}")
    return res


def anatomy(Q):
    L = [r for r in Q if r["result"] == "LOSS"]; W = [r for r in Q if r["result"] == "WIN"]
    ot = [r for r in Q if r["dur_s"] >= 186]
    cr = collections.Counter((r["crowns_me"], r["crowns_opp"]) for r in L)
    fc = collections.Counter(V.ph(int(r["first_crown_s"] * 20)) if r["first_crown"] == "opp" else ("bot first" if r["first_crown"] == "me" else "none") for r in L)
    print(f"  losses {len(L)}: 0 crowns scored {sum(r['crowns_me'] == 0 for r in L)}, three-crowned {sum(r['crowns_opp'] >= 3 for r in L)}; "
          f"score lines {dict(cr.most_common(6))}; opp first crown in {dict(fc)}")
    print(f"  overtime: {len(ot)}/{len(Q)} ({len(ot) / len(Q):.0%}) reach OT, OT win {wil(sum(r['result'] == 'WIN' for r in ot), len(ot))}; "
          f"losses decided in OT {sum(r['dur_s'] >= 186 for r in L)}/{len(L)}")
    # tower damage taken by lane in losses: my princess / king final hp fraction; the lane the first fallen tower was on vs my X-Bow lane
    for lab, S in (("losses", L), ("wins", W)):
        tk = {k: mean([(1 - (r["fin_hp"].get(k, 1) or 0)) * (4424 if k != "mK" else 7032) for r in S]) for k in ("mL", "mR", "mK")}
        print(f"  tower HP taken per match ({lab}): left {tk['mL']:.0f}, right {tk['mR']:.0f}, king {tk['mK']:.0f}; "
              f"by phase " + ", ".join(f"{p} {mean([r['dmg'][p]['taken'] for r in S if p in r['dmg']]):.0f}/{mean([r['dmg'][p]['dealt'] for r in S if p in r['dmg']]):.0f}" for p in ("1x", "2x", "OT")) + " (taken/dealt)")
    same = opp = nox = 0
    for r in L:
        f = [(v, k) for k, v in r["dead_s"].items() if k in ("mL", "mR") and v is not None]
        if not f: continue
        lane = min(f)[1][1]
        xs = [x["X"] for x in r["xbows"] if x["lock"]]
        if not xs: nox += 1; continue
        xl = "L" if sum(x < 9 for x in xs) >= len(xs) / 2 else "R"
        same += lane == xl; opp += lane != xl
    print(f"  losses where a princess fell: first fallen on my X-Bow lane {same}, on the OPPOSITE lane {opp}, no locked X-Bow {nox}")


def economy(Q):
    TH = [dict(e, _res=r["result"]) for r in Q for e in r["threats"]]
    for e in TH: e["bad"] = e["hp_lost"] >= R.BAD_HP or e["tower_fell"]
    lt4 = [e for e in TH if e["el"] is not None and e["el"] < 4]; ge4 = [e for e in TH if e["el"] is not None and e["el"] >= 4]
    mins = sum(r["dur_s"] for r in Q) / 60
    lo = sum(v for r in Q for k, v in r.get("card_ctx", {}).items() if k.endswith("|lo")) / mins
    lead = [e for e in TH if e["opp_el"] is not None and e["el"] is not None and e["opp_el"] - e["el"] >= 3]
    print(f"  pushes {len(TH)} ({len(TH) / len(Q):.1f}/match): elixir at push start median {V.med([e['el'] for e in TH]):.1f}, met < 4 {len(lt4) / len(TH):.0%}; "
          f"lost-episode rate < 4 {mean([e['bad'] for e in lt4]):.0%} / >= 4 {mean([e['bad'] for e in ge4]):.0%}; air in push {mean([e['air'] for e in TH]):.0%} "
          f"(lost {mean([e['bad'] for e in TH if e['air']]):.0%} vs {mean([e['bad'] for e in TH if not e['air']]):.0%}); opp public lead >= 3 {len(lead) / len(TH):.0%}; "
          f"cheap plays at < 5 elixir {lo:.2f}/min; push size median {V.med([e['v'] for e in TH]):.1f} elixir; lost-episode rate {mean([e['bad'] for e in TH]):.0%}")
    XB = [dict(x, _res=r["result"]) for r in Q for x in r["xbows"]]; off = [x for x in XB if x["lock"]]
    print(f"  X-Bows {len(XB) / len(Q):.2f}/match, locked {len(off) / len(Q):.2f}/match; locked at opp counter >= 7 {mean([(x['opp_el'] or 0) >= 7 for x in off]):.0%}; "
          f"dealt in 20 s {mean([x['dealt20'] for x in off]):.0f} HP; dud (< 300 HP) {mean([x['dealt20'] < 300 for x in off]):.0%}; life {mean([x['life'] for x in off]):.1f} s")


def late(Q):
    def lt(r):
        xb = sum(1 for x in r["xbows"] if x["lock"] and x["ph"] != "1x")
        rk = sum(1 for s in r["spells"] if s["name"] == "Rocket" and s["ph"] != "1x" and s.get("tower"))
        rka = sum(1 for s in r["spells"] if s["name"] == "Rocket" and s["ph"] != "1x")
        return xb, rk, rka
    for lab, S in (("X-Bow-unfavourable (owner six)", [r for r in Q if r["unfav"]]), ("other", [r for r in Q if not r["unfav"]])):
        if not S: continue
        v = [lt(r) for r in S]
        print(f"  late (2x + OT) {lab}: {len(S)} matches, win {wil(sum(r['result'] == 'WIN' for r in S), len(S))}; locked X-Bows {mean([a for a, _, _ in v]):.2f}/match, "
              f"tower Rockets {mean([b for _, b, _ in v]):.2f}, all Rockets {mean([c for _, _, c in v]):.2f}")
    L = [r for r in Q if r["result"] == "LOSS"]
    short = [r for r in L if 0 < ((r.get("tiebreak_min") or {}).get("opp") or 0) <= V.ROCKET_DMG]
    av = [r["end_rocket"] for r in short if r.get("end_rocket")]
    print(f"  losses ending with the enemy's lowest tower <= 497 HP (one Rocket): {len(short)}/{len(L)}; final 20 s Rocket in hand {mean([a['in_hand'] for a in av]):.0%}, "
          f"in hand AND >= 6 elixir {mean([a['affordable'] for a in av]):.0%}")
    sp = [s for r in Q for s in r["spells"]]
    for c in ("Rocket", "Tornado", "Log"):
        s = [x for x in sp if x["name"] == c]
        print(f"  {c}: {len(s) / len(Q):.2f}/match, on nothing {mean([x['n_hit'] == 0 and not x.get('barrel') for x in s]):.0%}" +
              (f", on a tower {mean([bool(x.get('tower')) for x in s]):.0%}" if c == "Rocket" else ""))
    print(f"  Hero IW ability presses {mean([r['abil'] for r in Q]):.2f}/match (confirmed {mean([r['abil_conf'] for r in Q]):.2f}); "
          f"Tornado first answer {mean([bool(e.get('first')) and e['first'][0][0] == 'Tornado' for r in Q for e in r['threats']]):.1%} of pushes")


def levels(Q):
    t = collections.Counter(r["opp_tower_lv"] for r in Q)
    cl = [r["opp_card_lv"] for r in Q if r["opp_card_lv"] is not None]
    print(f"  opponent king-tower level {dict(sorted(t.items(), key=lambda kv: str(kv[0])))}; mean opp card level {mean(cl):.2f} over {len(cl)} matches "
          f"(share of opp units at >= 16: {mean([r['opp_card_lv16'] for r in Q]):.0%})")
    for lv in (14, 15, 16):
        S = [r for r in Q if r["opp_tower_lv"] == lv]
        if S: print(f"    opp towers L{lv}: {wil(sum(r['result'] == 'WIN' for r in S), len(S))}, n {len(S)}")
    for lab, f in (("opp card level < 15.5", lambda x: x < 15.5), ("15.5-16.0", lambda x: 15.5 <= x < 16.0), (">= 16.0", lambda x: x >= 16.0)):
        S = [r for r in Q if r["opp_card_lv"] is not None and f(r["opp_card_lv"])]
        if S: print(f"    {lab}: {wil(sum(r['result'] == 'WIN' for r in S), len(S))}, n {len(S)}")


def factors(name, Q):
    path = HERE + f"report_{name}.md"
    rows = [dict(r) for r in Q]
    for r in rows: r["result_src"] = "ladder"; r["ladder"] = r["result"]
    R.write(rows, path)
    F = []
    for l in open(path, encoding="utf8"):
        m = re.match(r"\| (\d+) \| \*\*(.+?)\*\* \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (\(.\)) \|", l)
        if m: F.append(dict(rank=int(m[1]), name=m[2], inL=m[3], inW=m[4], eff=m[5], wins=m[7], label=m[8]))
    return path, F


def main():
    rows = sorted(load(), key=lambda r: r["ts"])
    C138 = [r for r in rows if r["mark"] == "CXXXVIII" and r["ts"] >= SWITCH]
    C124 = [r for r in rows if r["mark"] == "CXXIV" and r["ts"] < SWITCH][-200:]
    hi = [r for r in C138 if (r["start"] or 0) >= 12800]
    early = [r for r in C138 if (r["start"] or 0) < 12800]
    cohorts = (("CXXIV_last200", C124), ("CXXXVIII_all", C138), ("CXXXVIII_12800plus", hi), ("CXXXVIII_below12800", early))
    DW = {}
    for name, Q in cohorts:
        if not Q: continue
        DW[name] = summary(name, Q)
        table("by trophy band at match start", Q, lambda r: "-" if not r["start"] else f"{(r['start'] // 250) * 250}-{(r['start'] // 250) * 250 + 249}",
              order=[f"{a}-{a + 249}" for a in range(11750, 13500, 250)])
        table("by archetype (live_eval.classify)", Q, lambda r: r["_cls"])
        table("owner's X-Bow-unfavourable six", Q, lambda r: "unfavourable" if r["unfav"] else "other", order=["unfavourable", "other"])
        levels(Q); anatomy(Q); economy(Q); late(Q)
        path, F = factors(name, Q)
        print(f"  report.py factors -> {path}")
        dw, dl = DW[name]
        for x in F:
            try: w = float(x["wins"])
            except ValueError: w = None
            tro = f"{w * (dw - dl) / len(Q):+.2f} trophies/match ceiling" if w is not None else "-"
            print(f"    {x['rank']:2d} {x['label']} {x['name'][:70]:70s} | L {x['inL']} | W {x['inW']} | {x['eff'][:70]} | wins {x['wins']} | {tro}")
    # deck mix shift CXXIV vs CXXXVIII 12.8k+
    print("\n== deck mix: archetype share CXXIV last 200 vs CXXXVIII >= 12,800 (and all CXXXVIII)")
    ks = sorted({r["_cls"] for r in C124 + C138}, key=lambda k: -sum(r["_cls"] == k for r in C124 + C138))
    for k in ks:
        a = sum(r["_cls"] == k for r in C124); b = sum(r["_cls"] == k for r in hi); c = sum(r["_cls"] == k for r in C138)
        d, lo, up = V.newcombe(b, len(hi), a, len(C124)) if hi else (float("nan"),) * 3
        print(f"    {k[:28]:28s} {a / len(C124):5.1%} -> {b / max(1, len(hi)):5.1%} (all CXXXVIII {c / len(C138):5.1%}); diff {d:+.1%} [{lo:+.1%}, {up:+.1%}]")
    # per-archetype win rate change: is the drop uniform (opponent strength) or concentrated (matchup weakness)?
    print("\n== per-archetype win rate: CXXIV last 200 -> CXXXVIII all")
    for k in ks:
        a = [r for r in C124 if r["_cls"] == k]; b = [r for r in C138 if r["_cls"] == k]
        if len(a) >= 5 and len(b) >= 5:
            wa = sum(r["result"] == "WIN" for r in a); wb = sum(r["result"] == "WIN" for r in b)
            d, lo, up = V.newcombe(wb, len(b), wa, len(a))
            print(f"    {k[:28]:28s} {wa}/{len(a)} {wa / len(a):5.1%} -> {wb}/{len(b)} {wb / len(b):5.1%}  diff {d:+.1%} [{lo:+.1%}, {up:+.1%}]")
    json.dump([{k: r.get(k) for k in ("file", "ts", "mark", "result", "delta", "start", "_cls", "unfav", "opp_tower_lv", "opp_card_lv", "opp_cards", "crowns_me", "crowns_opp", "dur_s")}
               for r in C124 + C138], open(HERE + "cohort_rows.json", "w"), indent=0)


if __name__ == "__main__":
    main()
