"""Pooled paired comparison over several seed sets, split by opponent and by Goblin Barrel in the opponent's deck.
    python pooled.py BASE_A,BASE_B CAND_A,CAND_B [CAND2_A,CAND2_B ...]     (comma = seed sets to pool; same order)"""
import json, math, os, sys
O = os.path.expanduser("~/eval_ns")


def load(names):
    out = {}
    for name in names.split(","):
        for pre in ("react", "reactlad"):
            for l in open(f"{O}/{pre}_{name}/matches.jsonl"):
                r = json.loads(l)
                if r["arm"] == "plain":
                    out[(pre, r["tag"])] = r
    return out


score = lambda r: {"win": 1.0, "draw": 0.5}.get(r["outcome"], 0.0)
barrel = lambda r: any(c.split("@")[0] == "GoblinBarrel" for c in r.get("opp_deck") or [])


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


base = load(sys.argv[1])
for cand in sys.argv[2:]:
    c = load(cand)
    common = sorted(set(base) & set(c))
    for label, f in (("all", lambda r: True), ("gen", lambda r: r["opp"] == "gen"), ("s1", lambda r: r["opp"] == "s1"),
                     ("barrel-deck", barrel), ("no-barrel", lambda r: not barrel(r))):
        keys = [k for k in common if f(c[k])]
        up = sum(score(c[k]) > score(base[k]) for k in keys); dn = sum(score(c[k]) < score(base[k]) for k in keys)
        print(f"{cand[:40]:40s} {label:11s} n={len(keys):3d} wins {sum(score(c[k]) for k in keys):6.1f} vs "
              f"{sum(score(base[k]) for k in keys):6.1f}  better {up:3d} worse {dn:3d}  p={sign_p(up, dn):.3f}")
