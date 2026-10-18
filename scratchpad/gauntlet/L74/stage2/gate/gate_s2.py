"""Stage-2 gate (PLAN.md section 3), frozen by FROZEN.txt before any candidate result is read. Built on gate_fit.py (its
rows, classify, two-proportion z, post-stratified overall, archetype omnibus); this file only fixes WHICH rows and cells.

  full gate  (S2-06 / S2-10): 13k band = Mark CXXXVIII rows at >= 13,000 (live 78); 12k band = Mark CXXIV 12,000-12,999 (live 300).
     per band (gate_fit.evaluate): Hog win | overtime win | OT share | overall post-stratified to the live archetype mix  -> 8 cells
     + POOLED non-Hog regulation win (both Marks, live 12/28 + 58/140 = 70/168): SIM per-Mark rate weighted by the live
       per-Mark share (28/168, 140/168), z = (SIM - live) / sqrt(var_SIM + var_live)              -> 9th primary cell
     + per band OMNIBUS (sum z^2 over archetypes with live n >= 10, rest pooled < chi2_0.95) = required secondary.
     Style distance (opp_behaviour.py, <= 0.70) is the other required secondary; it is scored separately when telemetry exists.
  hog gate   (S2-08): Hog-pool runs (stage2/mvp/decks_hog_eval.json); per band: Hog win + Hog OT share (gate_fit z) -> 4 cells.
     Diagnostics (never gated): Hog regulation / OT 2x2, regulation-loss rate.
PASS = every primary cell |z| < 1.96 (and, full gate, both omnibus). One checkpoint must pass both bands; only levels differ.

  python gate_s2.py full NAME CXXXVIII=<glob 13k-band SIM rows> CXXIV=<glob 12k-band SIM rows>
  python gate_s2.py hog  NAME CXXXVIII=<glob> CXXIV=<glob>
  python gate_s2.py --selftest
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_fit as G

HOG = lambda r: r[1].startswith("Hog")
BANDS = (("CXXXVIII", "13k"), ("CXXIV", "12k"))


def live_rows():
    return {mk: G.live(mk, band) for mk, band in BANDS}


def nonhog_reg(S, L):
    """pooled non-Hog regulation win -> (z, line)."""
    lk = ln = 0; ps = vs = 0.0; parts = []
    nl = {mk: G.kn(L[mk], lambda r: not HOG(r) and not r[2]) for mk in L}
    tot = sum(n for _, n in nl.values())
    for mk in L:
        k, n = G.kn(S[mk], lambda r: not HOG(r) and not r[2]); w = nl[mk][1] / tot
        lk += nl[mk][0]; ln += nl[mk][1]
        if n: p = k / n; ps += w * p; vs += w * w * p * (1 - p) / n
        parts.append(f"{mk} SIM {k}/{n}")
    pl = lk / ln
    z = (ps - pl) / math.sqrt(pl * (1 - pl) / ln + vs)
    return z, (f"  {'pooled':9s} {'non-Hog regulation win':24s} live {G.pc(lk, ln):32s} SIM {ps:6.1%} (live-share weighted; "
               f"{', '.join(parts)})  z {z:+5.2f} {'pass' if abs(z) < 1.96 else 'FAIL'}")


def full(S, L):
    ok, lines = True, []
    for mk, band in BANDS:
        o, ls = G.evaluate({mk: S[mk]}, {mk: L[mk]}); ok &= o
        lines += [f" band {band} ({mk}): {'pass' if o else 'FAIL'}"] + ls
    z, line = nonhog_reg(S, L); ok &= abs(z) < 1.96
    return ok, lines + [line]


def hog(S, L):
    ok, lines = True, []
    for mk, band in BANDS:
        Lh, Sh = [r for r in L[mk] if HOG(r)], [r for r in S[mk] if HOG(r)]
        for name, lv, sv in (("Hog win", G.kn(Lh), G.kn(Sh)),
                             ("Hog OT share", (sum(r[2] for r in Lh), len(Lh)), (sum(r[2] for r in Sh), len(Sh)))):
            z = G.z2(*lv, *sv); p = abs(z) < 1.96; ok &= p
            lines.append(f"  {band} {mk:9s} {name:14s} live {G.pc(*lv):32s} SIM {G.pc(*sv):32s} z {z:+5.2f} {'pass' if p else 'FAIL'}")
        for ot in (False, True):   # diagnostics
            lines.append(f"      diag {band} Hog {'OT ' if ot else 'reg'} win: live {G.pc(*G.kn(Lh, lambda r: r[2] == ot))}  "
                         f"SIM {G.pc(*G.kn(Sh, lambda r: r[2] == ot))}")
        rl = lambda R: (sum(not r[0] and not r[2] for r in R), len(R))
        lines.append(f"      diag {band} Hog regulation-loss rate: live {G.pc(*rl(Lh))}  SIM {G.pc(*rl(Sh))}")
    return ok, lines


def selftest():
    import random
    rnd = random.Random(1)
    L = live_rows()
    good = {mk: v * 20 for mk, v in L.items()}                  # SIM = the live rows exactly -> every z = 0
    assert full(good, L)[0] and hog(good, L)[0], "\n".join(full(good, L)[1] + hog(good, L)[1])
    bad = {mk: [(True, c, ot) for _, c, ot in v * 20] for mk, v in L.items()}   # SIM always wins
    assert not full(bad, L)[0] and not hog(bad, L)[0]
    z, _ = nonhog_reg(good, L); assert abs(z) < 1e-9
    nl = sum(G.kn(L[mk], lambda r: not HOG(r) and not r[2])[1] for mk in L)
    assert nl == 168, nl                                       # PLAN: 70/168 pooled
    print("SELFTEST PASS (live n:", {mk: len(v) for mk, v in L.items()}, "non-Hog regulation", nl, ")")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(); sys.exit()
    kind, name = sys.argv[1], sys.argv[2]
    S = {x.split("=", 1)[0]: G.sim(x.split("=", 1)[1]) for x in sys.argv[3:] if "=" in x}
    assert set(S) == {"CXXXVIII", "CXXIV"}, "need CXXXVIII=<glob> and CXXIV=<glob>"
    ok, lines = (full if kind == "full" else hog)(S, live_rows())
    print(f"== {name} | {kind} gate: {'GATE PASS' if ok else 'GATE FAIL'}  (SIM games: " + ", ".join(f"{k} {len(v)}" for k, v in S.items()) + ")")
    print("\n".join(lines))
