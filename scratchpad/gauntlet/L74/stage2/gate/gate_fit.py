"""Stage-2 reproduction GATE: does a SIM opponent set reproduce the LIVE results of Mark CXXXVIII and Mark CXXIV, per
trophy band?

  python gate_fit.py NAME --band 13k|12k [--live live_targets.json] CXXXVIII=<glob of matches.jsonl> [CXXIV=<glob>]
  python gate_fit.py --selftest
Live side = live_targets.json (live_targets.py; ladder-graded only). Bands: 13k = start trophies >= 13,000 (only CXXXVIII has
played there); 12k = 12,000-12,999 (CXXIV 300, CXXXVIII 39). The SIM has no trophy band (opponent levels do not step up at 13k:
15.54 vs 15.55), so an opponent set is gated against ONE band: the one it claims to represent.
Opponent decks classified with live_eval.classify (live: played cards; SIM: full deck, '@form' stripped).
SIM OT = end_tick > 3600; live OT = match clock >= 186 s (regulation ends at 181-185 s on the live clock).

Per Mark with >= 30 live matches in the band (two-proportion z, SIM noise included):
  PRIMARY, each |z| < 1.96:  Hog win | overtime win | overall win post-stratified to the live archetype mix | OT share
  OMNIBUS: sum z^2 over archetype cells (live n >= 10, rest pooled) < chi2_0.95(df)
ponytail: no multiplicity correction; 4 primaries x Marks at 5% each -> ~20% false-fail for a perfect set with 2 Marks (the gate
errs toward FAIL, the safe side for 'train against it').
"""
import collections, glob, json, math, os, sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_eval")
from live_eval import classify, wilson
HERE = os.path.dirname(os.path.abspath(__file__))
CHI95 = {1: 3.84, 2: 5.99, 3: 7.81, 4: 9.49, 5: 11.07, 6: 12.59, 7: 14.07, 8: 15.51, 9: 16.92, 10: 18.31, 11: 19.68,
         12: 21.03, 13: 22.36, 14: 23.68, 15: 25.0, 16: 26.3}
BANDS = {"13k": lambda s: s >= 13000, "12k": lambda s: 12000 <= s < 13000}


def live(mark, band, path=os.path.join(HERE, "live_targets.json")):
    return [(x["res"] == "WIN", x["cls"], x["ot"]) for x in json.load(open(path))
            if x["mark"] == mark and x["src"] == "ladder" and x["start"] is not None and BANDS[band](x["start"])]


def sim(pattern):
    out = []
    for f in sorted(glob.glob(pattern)):
        for l in open(f):
            if l.strip():
                r = json.loads(l)
                out.append((r["outcome"] == "win", classify([c.split("@")[0] for c in r["opp_deck"]]), (r.get("end_tick") or 0) > 3600))
    return out


def kn(rows, f=lambda r: True):
    s = [r for r in rows if f(r)]
    return sum(r[0] for r in s), len(s)


def z2(k1, n1, k2, n2):
    if not n1 or not n2: return float("nan")
    p = (k1 + k2) / (n1 + n2); se = math.sqrt(max(p * (1 - p), 1e-9) * (1 / n1 + 1 / n2))
    return (k1 / n1 - k2 / n2) / se


def pc(k, n):
    if not n: return "n/a"
    lo, hi = wilson(k, n); return f"{k / n:6.1%} [{lo:5.1%}, {hi:5.1%}] n {n}"


def evaluate(S, L):
    """S, L = {mark: rows}. -> (passed, lines)"""
    lines, ok, chi, df = [], True, 0.0, 0
    for mk in S:
        if len(L.get(mk, [])) < 30:
            lines.append(f"  {mk}: {len(L.get(mk, []))} live matches in this band (< 30) -> not gated"); continue
        Lm, Sm = L[mk], S[mk]
        c = collections.Counter(r[1] for r in Lm); big = {k for k, n in c.items() if n >= 10}
        g = lambda r: r[1] if r[1] in big else "rest"
        # post-stratified SIM overall win: SIM per-cell rate weighted by the live mix; its variance from the SIM cell counts
        ps = vs = 0.0
        for cell, m in collections.Counter(g(r) for r in Lm).items():
            k, n = kn(Sm, lambda r: g(r) == cell)
            if n: p = k / n; w = m / len(Lm); ps += w * p; vs += w * w * p * (1 - p) / n
        kl, nl = kn(Lm); pl = kl / nl
        z_ps = (pl - ps) / math.sqrt(pl * (1 - pl) / nl + vs)
        ot_l, ot_s = sum(r[2] for r in Lm), sum(r[2] for r in Sm)
        prim = [("Hog win", kn(Lm, lambda r: r[1].startswith("Hog")), kn(Sm, lambda r: r[1].startswith("Hog"))),
                ("overtime win", kn(Lm, lambda r: r[2]), kn(Sm, lambda r: r[2])),
                ("OT share", (ot_l, len(Lm)), (ot_s, len(Sm)))]
        for name, lv, sv in prim:
            z = z2(*lv, *sv); p = abs(z) < 1.96; ok &= p
            lines.append(f"  {mk:9s} {name:24s} live {pc(*lv):32s} SIM {pc(*sv):32s} z {z:+5.2f} {'pass' if p else 'FAIL'}")
        p = abs(z_ps) < 1.96; ok &= p
        lines.append(f"  {mk:9s} {'overall (post-strat.)':24s} live {pc(kl, nl):32s} SIM {ps:6.1%} (raw {pc(*kn(Sm))})  z {z_ps:+5.2f} {'pass' if p else 'FAIL'}")
        for cell in sorted(big) + ["rest"]:
            lv, sv = kn(Lm, lambda r: g(r) == cell), kn(Sm, lambda r: g(r) == cell)
            if not lv[1] or not sv[1]: continue
            z = z2(*lv, *sv); chi += z * z; df += 1
            lines.append(f"      {cell[:26]:26s} live {pc(*lv):32s} SIM {pc(*sv):32s} z {z:+5.2f}")
    if df:
        om = chi < CHI95.get(df, df + 2 * math.sqrt(2 * df)); ok &= om
        lines.append(f"  OMNIBUS sum z^2 {chi:.1f} on df {df} (chi2_0.95 {CHI95.get(df, 'approx')}) {'pass' if om else 'FAIL'}")
    return ok, lines


def selftest():
    import random
    rnd = random.Random(0)
    L = {"CXXXVIII": [(rnd.random() < (.35 if i % 4 == 0 else .55), "Hog (incl. Royal Hogs)" if i % 4 == 0 else ("Golem" if i % 2 else "Other"),
                       i % 2 == 0) for i in range(200)]}
    good = {k: v * 10 for k, v in L.items()}                       # SIM = the live frequencies exactly -> every z = 0
    bad = {k: [(True if r[1].startswith("Hog") else r[0], r[1], r[2]) for r in v * 10] for k, v in L.items()}   # Hog always won
    assert evaluate(good, L)[0], "\n".join(evaluate(good, L)[1])
    assert not evaluate(bad, L)[0]
    assert evaluate(good, {"CXXXVIII": L["CXXXVIII"][:20]})[1][0].endswith("not gated")
    print("SELFTEST PASS")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(); sys.exit()
    a = sys.argv[1:]; name = a.pop(0)
    band = a[a.index("--band") + 1]; lp = a[a.index("--live") + 1] if "--live" in a else os.path.join(HERE, "live_targets.json")
    S = {x.split("=", 1)[0]: sim(x.split("=", 1)[1]) for x in a if "=" in x}
    ok, lines = evaluate(S, {mk: live(mk, band, lp) for mk in S})
    print(f"== {name} | band {band}: {'GATE PASS' if ok else 'GATE FAIL'}  (SIM games: " + ", ".join(f"{k} {len(v)}" for k, v in S.items()) + ")")
    print("\n".join(lines))
