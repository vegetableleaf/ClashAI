"""Reader id churn check: share of 'new' enemy bodies (first sighting, seen in >= 2 states) that continue a body of the SAME card
which vanished in the previous 20 ticks within 1.5 tiles (a re-identified unit, not a new deployment). Live vs SIM, 1x only.
  laptop: python diag_churn.py live N        VM: python diag_churn.py sim <matches.jsonl> N"""
import sys, json, glob, math, collections
sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
import econ2 as E
G = E.G


def churn(S):
    first, last = {}, {}
    occ = collections.Counter((i, n) for t, e, b in S for n, X, Y, hp, i in b)
    for t, e, bodies in S:
        for n, X, Y, hp, i in bodies:
            if (i, n) not in first: first[(i, n)] = (t, X, Y)
            last[(i, n)] = (t, X, Y)
    new = cont = 0.0; nv = cv = 0
    for k, (t, X, Y) in first.items():
        if t >= 2400 or t < 20 or occ[k] < 2: continue
        v = G.uval(k[1]); new += v; nv += 1
        if any(k2[1] == k[1] and k2 != k and t - 20 <= lt < t and math.hypot(lX - X, lY - Y) <= 1.5 for k2, (lt, lX, lY) in last.items()):
            cont += v; cv += 1
    return new, cont, nv, cv


def main():
    G.load_catalog(); tot = [0.0, 0.0, 0, 0]
    if sys.argv[1] == "live":
        fs = sorted(glob.glob(G.LOGDIR + "live_play_2026100[6-8]_*.jsonl"))[-int(sys.argv[2]):]
        Ss = (M["S"] for M in (G.live_match(f) for f in fs) if M)
    else:
        def gen():
            for k, l in enumerate(open(sys.argv[2])):
                if k >= int(sys.argv[3]): break
                r = json.loads(l)
                if "lr_dec" in r: yield G.sim_match(r, G.TAUS["stack"])["S"]
        Ss = gen()
    for S in Ss:
        for j, x in enumerate(churn(S)): tot[j] += x
    print(sys.argv[1], "new body value", round(tot[0]), "continuations", round(tot[1]), f"({100 * tot[1] / max(1, tot[0]):.1f}% of value, {100 * tot[3] / max(1, tot[2]):.1f}% of bodies)")


if __name__ == "__main__":
    main()
