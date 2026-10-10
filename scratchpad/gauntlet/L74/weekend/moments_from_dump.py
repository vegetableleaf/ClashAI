"""S9 pass 1 -> moments: run the drills.py selectors on a sim_dump directory, keep D1 (do), D2, D3, D4 (do), D9, at most CAP per drill
per match and >= GAP ticks apart.  python moments_from_dump.py DUMP_DIR OUT.json [CAP=3] [GAP=200] [MAXN=150]   (MAXN: at most this many moments per drill, a seeded sample)
D9's moment tick is the SECOND card's decision (selector tick + info.gap); every other drill forks at the selector's own decision tick."""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "drills"))
import drills as D          # CB_MAIN must point at the repo root (drills.py MAIN)

dump, out = sys.argv[1], sys.argv[2]
cap, gap = (int(sys.argv[3]) if len(sys.argv) > 3 else 3), (int(sys.argv[4]) if len(sys.argv) > 4 else 200)
KEEP = {"D1": "do", "D2": "dohold", "D3": "dohold", "D4": "do", "D9": "dohold"}
res, n = {}, collections.Counter()
for m in D.load_sim(dump if dump.endswith("/") else dump + "/"):
    recs = [r for r in D.harvest(m) if KEEP.get(r["drill"]) == r["kind"]]
    for r in recs:
        r["t"] = r["t"] + (int(r["info"]["gap"]) if r["drill"] == "D9" else 0)
    last = {}
    for r in sorted(recs, key=lambda r: r["t"]):
        k = r["drill"]
        if last.get(k, (-10 ** 9, 0))[1] >= cap or r["t"] - last.get(k, (-10 ** 9, 0))[0] < gap:
            continue
        last[k] = (r["t"], last.get(k, (0, 0))[1] + 1)
        res.setdefault(m["file"], []).append({"t": r["t"], "drill": k, "kind": r["kind"], "info": r["info"]})
        n[k] += 1
maxn = int(sys.argv[5]) if len(sys.argv) > 5 else 150
import random
pool = [(tag, i) for tag, l in res.items() for i in range(len(l))]
random.Random(0).shuffle(pool)
keep, c = set(), collections.Counter()
for tag, i in pool:
    k = res[tag][i]["drill"]
    if c[k] < maxn:
        keep.add((tag, i)); c[k] += 1
res = {tag: [mo for i, mo in enumerate(l) if (tag, i) in keep] for tag, l in res.items()}
res = {t: l for t, l in res.items() if l}
json.dump(res, open(out, "w"), default=str)
print("matches", len(res), "moments before cap", dict(n), "kept", dict(c))
