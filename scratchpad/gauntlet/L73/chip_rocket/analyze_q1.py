"""Q1: chip vs catch tower Rockets, pros vs R1e vs live stack; and the conditional rate test
(tower Rockets per eligible minute | catchable enemy troop near an alive enemy tower vs not). Cluster bootstrap by match."""
import pickle, bisect, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
RNG = np.random.default_rng(0); B = 2000
pros = pickle.load(open(os.path.join(HERE, "pros_chip.pkl"), "rb"))
bot = pickle.load(open(os.path.join(HERE, "bot_chip.pkl"), "rb"))
hands = pickle.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/rocket_lead/hands_pros.pkl", "rb"))
CATCH = float(sys.argv[1]) if len(sys.argv) > 1 else 4000.0


def pro_rocket_in_hand(m):
    h = hands.get(m["id"])
    if not h: return None
    ts = [t for t, _ in h]
    out = []
    for row in m["series"]:
        i = bisect.bisect_left(ts, row[0])
        out.append(None if i >= len(ts) else ("Rocket" in h[i][1]))
    return out


def norm(pop):
    """-> list of matches: dict(rockets=[...], elig=[(tick, dt, near_pr, near_k)], ...)"""
    out = []
    for m in pop:
        if "res" in m:   # bot
            el = [(r[0], r[7], r[2], r[3]) for r in m["series"] if r[8] and r[1] >= 6]
            ticks = [r[0] for r in m["series"]]; ser = m["series"]
            minutes = sum(r[7] for r in ser) / 1200
        else:
            rh = pro_rocket_in_hand(m)
            if rh is None: continue
            ser = m["series"]; ticks = [r[0] for r in ser]
            el = [(r[0], 10, r[2], r[3]) for r, h in zip(ser, rh) if h and r[1] >= 6]
            minutes = len(ser) * 10 / 1200
        for rk in m["rockets"]:
            i = max(bisect.bisect_right(ticks, rk["tick"]) - 1, 0)
            rk["near_pr"], rk["near_k"] = ser[i][2], ser[i][3]
        out.append(dict(id=m["id"], rockets=m["rockets"], elig=el, minutes=minutes, end=m["end"]))
    return out


def boot(ms, num, den):
    a = np.array([num(m) for m in ms], float); b = np.array([den(m) for m in ms], float)
    pt = a.sum() / max(b.sum(), 1e-12)
    S = RNG.integers(0, len(ms), (B, len(ms))); bs = b[S].sum(1); ok = bs > 0
    r = a[S].sum(1)[ok] / bs[ok]
    return pt, np.percentile(r, 2.5), np.percentile(r, 97.5), a.sum(), b.sum()


def fmt(t, pct=False):
    if pct: return f"{100*t[0]:.0f}% [{100*t[1]:.0f},{100*t[2]:.0f}] ({t[3]:.0f}/{t[4]:.0f})"
    return f"{t[0]:.3f} [{t[1]:.3f},{t[2]:.3f}] ({t[3]:.0f}/{t[4]:.0f})"


tower = lambda r: bool(r["towers"])
chip = lambda r: bool(r["towers"]) and r["troops"] is not None and len(r["troops"]) == 0
catch = lambda r: bool(r["towers"]) and r["troops"] is not None and len(r["troops"]) > 0
hpb = lambda r: "hp>50%" if max(f for _, f in r["towers"]) > .5 else ("hp25-50%" if max(f for _, f in r["towers"]) > .25 else "hp<=25%")
leadb = lambda r: "deficit" if r["lead"] / 3 < -.1 else ("lead" if r["lead"] / 3 > .1 else "even")
POPS = {"pros": norm(pros), "R1e(76fdfaac)": norm(bot["R1e"]), "live(e7359f2b)": norm(bot["live"])}
for k, ms in POPS.items():
    allr = [r for m in ms for r in m["rockets"]]
    tw = [r for r in allr if tower(r)]
    print(f"===== {k}: matches {len(ms)} rockets {len(allr)} tower {len(tw)} (troops unknown {sum(r['troops'] is None for r in tw)}) "
          f"king-targeted {sum(any(t=='king' for t,_ in r['towers']) for r in tw)}; princess-only {sum(all(t=='princess' for t,_ in r['towers']) for r in tw)}")
    n = lambda m, f: sum(f(r) for r in m["rockets"])
    print("  per match: all", fmt(boot(ms, lambda m: len(m["rockets"]), lambda m: 1)), "| tower", fmt(boot(ms, lambda m: n(m, tower), lambda m: 1)),
          "| CHIP", fmt(boot(ms, lambda m: n(m, chip), lambda m: 1)), "| CATCH", fmt(boot(ms, lambda m: n(m, catch), lambda m: 1)))
    print("  chip share of tower Rockets (troops known):", fmt(boot(ms, lambda m: n(m, chip), lambda m: n(m, chip) + n(m, catch)), True))
    for lab, sel in [("phase", lambda r: r["phase"]), ("tower hp", hpb), ("lead", leadb),
                     ("target", lambda r: "king" if any(t == "king" for t, _ in r["towers"]) else "princess")]:
        for v in sorted({sel(r) for r in tw}):
            f = lambda m, c: sum(c(r) and sel(r) == v for r in m["rockets"])
            print(f"    {lab}={v:9s} chip/match {fmt(boot(ms, lambda m: f(m, chip), lambda m: 1))}  catch/match {fmt(boot(ms, lambda m: f(m, catch), lambda m: 1))}"
                  f"  chip share {fmt(boot(ms, lambda m: f(m, chip), lambda m: f(m, chip) + f(m, catch)), True)}")
    # conditional rate test: tower Rockets per eligible minute, catchable troop near an alive enemy PRINCESS tower vs not
    for nm, key in (("princess", 2), ("any tower", None)):
        def near(e): return (e[2] if key else min(e[2], e[3])) <= CATCH
        def rnear(r): return (r["near_pr"] if key else min(r["near_pr"], r["near_k"])) <= CATCH
        em = lambda m, c: sum(e[1] for e in m["elig"] if near(e) == c) / 1200
        num = lambda m, c: sum(tower(r) and rnear(r) == c for r in m["rockets"])
        a = boot(ms, lambda m: num(m, True), lambda m: em(m, True)); b = boot(ms, lambda m: num(m, False), lambda m: em(m, False))
        sh = boot(ms, lambda m: em(m, True), lambda m: em(m, True) + em(m, False))
        # ratio CI by paired bootstrap
        A = np.array([[num(m, True), em(m, True), num(m, False), em(m, False)] for m in ms])
        S = RNG.integers(0, len(ms), (B, len(ms))); s = A[S].sum(1)
        ok = (s[:, 1] > 0) & (s[:, 3] > 0) & (s[:, 2] > 0)
        rr = (s[ok, 0] / s[ok, 1]) / (s[ok, 2] / s[ok, 3])
        print(f"  [{nm}, troop within {CATCH/1000:.1f} t] eligible-time share with troop near {fmt(sh, True)} | tower Rockets/elig-min WITH troop {fmt(a)}"
              f" WITHOUT {fmt(b)} | ratio {a[0]/max(b[0],1e-9):.2f} [{np.percentile(rr,2.5):.2f},{np.percentile(rr,97.5):.2f}]")
