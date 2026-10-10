"""Paired win-rate comparison of two eval_defence dirs (run_eval.sh: <EVAL_DIR>/<NAME>_{evo,lad}/matches.jsonl), same seeds + decks.
    python wk_compare.py EVAL_DIR BASE CAND            -> one line: n pairs, win % of each, CAND - BASE in pp with a 95% CI (paired, games independent)
win = 1, draw = 0.5, loss = 0 (compare.py's score).  Importable: diff(eval_dir, base, cand) -> (n, base_pct, cand_pct, mean_pp, lo_pp, hi_pp)."""
import json, math, os, sys


def games(d, name):
    out = {}
    for c in ("evo", "lad"):
        p = f"{d}/{name}_{c}/matches.jsonl"
        if os.path.exists(p):
            for ln in open(p):
                r = json.loads(ln)
                if not r.get("skipped"):
                    out[(c, r["tag"])] = {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)
    return out


def diff(d, a, b):
    A, B = games(d, a), games(d, b)
    ks = sorted(set(A) & set(B))
    if len(ks) < 2:
        return len(ks), None, None, None, None, None
    x = [B[k] - A[k] for k in ks]
    mu = sum(x) / len(x)
    sd = math.sqrt(sum((v - mu) ** 2 for v in x) / (len(x) - 1))
    hw = 1.96 * sd / math.sqrt(len(x))
    return len(ks), 100 * sum(A[k] for k in ks) / len(ks), 100 * sum(B[k] for k in ks) / len(ks), 100 * mu, 100 * (mu - hw), 100 * (mu + hw)


def line(d, a, b):
    n, pa, pb, mu, lo, hi = diff(d, a, b)
    if mu is None:
        return f"{b} vs {a}: n/a (pairs {n})"
    return f"{b} vs {a}: {n} paired games | {a} {pa:.1f}% | {b} {pb:.1f}% | {b} - {a} {mu:+.2f} pp [{lo:+.2f}, {hi:+.2f}]"


def arch_table(d, a, b):
    """per-archetype win % of both arms (same games; archetype = archetypes.classify of the opponent deck)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import archetypes as A
    deck = {}
    for c in ("evo", "lad"):
        for name in (a, b):
            p = f"{d}/{name}_{c}/matches.jsonl"
            if os.path.exists(p):
                for ln in open(p):
                    r = json.loads(ln)
                    if r.get("opp_deck"):
                        deck[(c, r["tag"])] = r["opp_deck"]
    ga, gb = games(d, a), games(d, b)
    ks = sorted(set(ga) & set(gb) & set(deck))
    out = ["by opponent archetype (n | %s %% | %s %%):" % (a, b)]
    for arch in sorted({A.classify(deck[k]) for k in ks}):
        kk = [k for k in ks if A.classify(deck[k]) == arch]
        out.append(f"  {arch:18s} n {len(kk):4d} | {100 * sum(ga[k] for k in kk) / len(kk):5.1f} | {100 * sum(gb[k] for k in kk) / len(kk):5.1f}")
    return chr(10).join(out)


def rule(d, a, b, r):
    n, pa, pb, mu, lo, hi = diff(d, a, b)
    if mu is None:
        return "VERDICT: n/a"
    if r == "s2":
        return "VERDICT: worse: recommend owner revert" if hi < 0 else "VERDICT: not worse"
    if r == "s6":
        return "VERDICT: own-cycle helps" if lo > 0 else "VERDICT: own-cycle not shown to help"
    if r == "s10":
        return "VERDICT: non-inferior (lower > -3 pp)" if lo > -3 else "VERDICT: inferior or unproven (lower <= -3 pp)"
    if r == "pos":
        return "VERDICT: positive" if mu > 0 else "VERDICT: not positive"
    return ""


def unpaired(d, a, b):
    A, B = games(d, a), games(d, b)
    xa, xb = list(A.values()), list(B.values())
    ma, mb = sum(xa) / len(xa), sum(xb) / len(xb)
    va = sum((x - ma) ** 2 for x in xa) / (len(xa) - 1)
    vb = sum((x - mb) ** 2 for x in xb) / (len(xb) - 1)
    hw = 1.96 * math.sqrt(va / len(xa) + vb / len(xb))
    return len(xa), len(xb), 100 * ma, 100 * mb, 100 * (mb - ma), 100 * (mb - ma - hw), 100 * (mb - ma + hw)


if __name__ == "__main__":
    d, a, b = sys.argv[1:4]
    if len(sys.argv) > 4 and sys.argv[4] == "unpaired":
        na, nb, pa, pb, mu, lo, hi = unpaired(d, a, b)
        print(f"unpaired: {a} {pa:.1f}% (n {na}) | {b} {pb:.1f}% (n {nb}) | shift {mu:+.2f} pp [{lo:+.2f}, {hi:+.2f}]")
        sys.exit(0)
    print(line(d, a, b))
    print(arch_table(d, a, b))
    if len(sys.argv) > 4:
        print(rule(d, a, b, sys.argv[4]))
