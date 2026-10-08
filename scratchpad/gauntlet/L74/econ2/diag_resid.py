"""Diagnostic for the Q2 accounting residual: regen slope over play-free stretches and the spend-timing offset that zeroes
the residual, per source. python diag_resid.py live sim_stack pros"""
import sys, bisect, collections
import econ2 as E
G = E.G


def main(names):
    G.load_catalog()
    for n in names:
        ms = E.load(n); slope = collections.defaultdict(lambda: [0.0, 0.0]); res = collections.defaultdict(list)
        for m in ms[:300]:
            T, el = m["T"], m["el"]; pt = sorted(p[0] for p in m["pl"])
            for i in range(len(T) - 1):            # play-free 10-30 tick steps below 9: elixir gain per tick by phase
                a, b = el[i], el[i + 1]
                if a is None or b is None or a >= 9 or b >= 9.9: continue
                k = bisect.bisect_left(pt, T[i] - 60)
                if k < len(pt) and pt[k] <= T[i + 1] + 60: continue
                slope[G.ph(T[i])][0] += b - a; slope[G.ph(T[i])][1] += T[i + 1] - T[i]
            for i in range(len(T) - 30):            # 300-tick windows anywhere: residual vs spend-deduction offset
                j = bisect.bisect_left(T, T[i] + 300)
                if j >= len(T) or el[i] is None or el[j] is None: continue
                reg = sum((T[a + 1] - T[a]) * E.rg(T[a]) for a in range(i, j) if el[a] is not None and el[a] < 9.9)
                for off in (0, 13, 26, 40):
                    sp = sum(E.ccost(c) for t, c, e, f in m["pl"] if T[i] < t + off <= T[j])
                    res[off].append(el[j] - (el[i] + reg - sp))
        drop = collections.defaultdict(list)       # isolated plays: elixir change across the deduction vs the card cost
        for m in ms[:300]:
            T, el = m["T"], m["el"]; pt = [p[0] for p in m["pl"]]
            for t, c, e, f in m["pl"]:
                if sum(1 for x in pt if abs(x - t) <= 80) > 1: continue
                for off in (26, 40):
                    a = E.at(T, t + off - 30); b = bisect.bisect_left(T, t + off + 30)
                    if b >= len(T) or el[a] is None or el[b] is None or el[a] >= 9.9: continue
                    drop[(c, off)].append(el[b] - el[a] - (T[b] - T[a]) * E.rg(T[a]) + E.ccost(c))
        print(n, {f"{c}@{o}": round(E.mean(v), 2) for (c, o), v in sorted(drop.items()) if len(v) > 20}, "excess drop (0 = cost)")
        print(n, {p: round(v[0] / v[1] * 56, 3) for p, v in slope.items()}, "(x 1/56 per tick)",
              {o: round(E.mean(v), 3) for o, v in res.items()}, "resid by deduction offset")


if __name__ == "__main__":
    main(sys.argv[1:])
