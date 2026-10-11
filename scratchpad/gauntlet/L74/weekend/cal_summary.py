"""L74 CAL: pick the harder-opponent set whose OLD-model win rate matches live (owner 2026-10-11).
    python cal_summary.py bestbc EV SETS.tsv                 -> prints "b" or "c" (the rule applied to those two sets)
    python cal_summary.py final EV SETS.tsv SUMMARY PICK.env -> table + pick
EV holds <set>_<old|e4>_<evo|lad>/matches.jsonl (search_s0 dirs, same seeds for OLD and E4).  SETS.tsv lines:
name <TAB> opps <TAB> opp_gen <TAB> T <TAB> decks <TAB> eligible(1/0)
RULE: among eligible sets with OLD >= E4 (paired point estimate, matching live) pick the OLD win rate closest to 55%;
none with OLD >= E4 -> the lowest OLD win rate, flagged "no set reproduces the live ranking"."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wk_compare import diff

TARGET = 55.0


def rows_of(ev, tsv, only=None):
    out = []
    for ln in open(tsv):
        f = ln.rstrip("\n").split("\t")
        if len(f) < 6 or (only and f[0] not in only):
            continue
        n, old, e4, mu, lo, hi = diff(ev, f[0] + "_old", f[0] + "_e4")
        if mu is not None:
            out.append(dict(name=f[0], opps=f[1], gen=f[2], T=f[3], decks=f[4], ok=f[5] == "1", n=n, old=old, e4=e4, mu=mu, lo=lo, hi=hi))
    return out


def pick(rows):
    """-> (row, reason) among the eligible rows."""
    el = [r for r in rows if r["ok"]]
    if not el:
        raise ValueError("no eligible set")
    good = [r for r in el if r["old"] >= r["e4"]]
    if good:
        return min(good, key=lambda r: abs(r["old"] - TARGET)), "OLD >= E4 and OLD win rate closest to 55%"
    return min(el, key=lambda r: r["old"]), "no set reproduces the live ranking (OLD < E4 everywhere): lowest OLD win rate"


def main(a):
    mode, ev, tsv = a[0], a[1], a[2]
    if mode == "bestbc":
        print(pick(rows_of(ev, tsv, ("b", "c")))[0]["name"])
        return
    rows = rows_of(ev, tsv)
    r, why = pick(rows)
    L = ["CAL: harder sim opponents vs live. OLD vs E4 as the learner, paired, 480 games per learner (evo 30000:30240 + lad 30240:30480), live flags as S2.",
         "live reference: ladder ~50%, owner sees E4 worse than OLD; S2 (gen_v1_s0 T .3, seeds 0:480) had OLD 69.3 / E4 70.2.",
         f"{'set':3s} {'opponent model':44s} {'T':>4s} {'decks':16s} {'n':>4s} {'OLD%':>6s} {'E4%':>6s} {'E4-OLD pp [95% CI]':>24s}  eligible"]
    for x in rows:
        L.append(f"{x['name']:3s} {os.path.basename(x['gen'])[:44]:44s} {x['T']:>4s} {x['decks']:16s} {x['n']:4d} {x['old']:6.1f} {x['e4']:6.1f} {x['mu']:+7.2f} [{x['lo']:+.2f}, {x['hi']:+.2f}]  {'yes' if x['ok'] else 'no (mirror)'}")
    L += [f"PICK: set {r['name']} ({r['opps']} {os.path.basename(r['gen'])} T {r['T']}); {why}.",
          "Notes: the rule uses point estimates only; at n=480 the paired CI half-width is about 6 pp, so close sets are not separated by this data.",
          "Set d is icebow-vs-icebow (S1 plays the icebow deck): reported, not eligible, the drills need non-mirror census decks.",
          "S9XL2b/S10XL2b keep the archetype-weighted census decks (as S9XL2); the pick sets only the opponent model and temperature. Only set e measured the weighted decks."]
    open(a[3], "w").write("\n".join(L) + "\n")
    open(a[4], "w").write(f"OPP_GEN={r['gen']}\nOPP_T={r['T']}\nPICK_SET={r['name']}\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1:])
