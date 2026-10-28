import json, sys, glob
from collections import Counter
R = [json.loads(l) for f in sorted(glob.glob(sys.argv[1] + "/*/D3/matches.jsonl")) for l in open(f) if l.strip()]
o = [r["hab"]["opp"] for r in R]
n = sum(len(x) for x in o)
ppm = [len(x) / ((r["end_tick"] - 90) / 1200) for x, r in zip(o, R)]
c = Counter(r["outcome"] for r in R)
print(json.dumps({"rows": len(R), "outcomes": c, "learner_win": round(c["win"] / len(R), 4),
                  "mean_end_tick": round(sum(r["end_tick"] for r in R) / len(R), 1),
                  "ot_share": round(sum(r["end_tick"] > 3700 for r in R) / len(R), 3),
                  "opp_plays_per_row": round(n / len(R), 2), "opp_refused_share": round(sum(not p[3] for x in o for p in x) / n, 4),
                  "opp_ppm": round(sum(ppm) / len(ppm), 2), "crowns_against": round(sum(r["crowns_against"] for r in R) / len(R), 3),
                  "crowns_for": round(sum(r["crowns_for"] for r in R) / len(R), 3)}))
