"""Unconfirmed-tap rate per match since CLXIII (health_rows.jsonl): is the post-decoy 5.2% a shift or load noise?"""
import json, statistics as st
from pathlib import Path
rows = [json.loads(l) for l in open(Path(__file__).parent / "results" / "health_rows.jsonl")]
rows = [r for r in rows if r["played"]]
def rate(rs): return sum(r["unconfirmed"] for r in rs) / max(1, sum(r["played"] for r in rs))
pre = [r for r in rows if r["stem"][10:25] < "20261028_114500"]
post = [r for r in rows if r["stem"][10:25] >= "20261028_114500"]
print("pre ", len(pre), "matches, rate", round(100 * rate(pre), 2), "% ; per-match median", st.median(r["unconfirmed"] / r["played"] for r in pre), "p90",
      sorted(r["unconfirmed"] / r["played"] for r in pre)[int(.9 * len(pre))])
print("post", len(post), "matches, rate", round(100 * rate(post), 2), "% ; per-match median", st.median(r["unconfirmed"] / r["played"] for r in post))
# 26 blocks of ~27 matches in the pre stream: how often does a block reach the post rate?
blocks = [pre[i:i + len(post)] for i in range(0, len(pre) - len(post) + 1, len(post))]
rs = [rate(b) for b in blocks]
print("pre-stream blocks of", len(post), "matches:", len(blocks), "rates (%) min/median/max", round(100 * min(rs), 1), round(100 * st.median(rs), 1), round(100 * max(rs), 1),
      "; blocks >= post rate:", sum(x >= rate(post) for x in rs))
print("post per match (hhmm, unconfirmed/played, fails):", [(r["start_hhmm"], f'{r["unconfirmed"]}/{r["played"]}') for r in post])
sl = [rate(pre[i:i + len(post)]) for i in range(0, len(pre) - len(post) + 1)]
print("sliding windows of", len(post), "pre matches:", len(sl), "; rate min/median/max %.1f / %.1f / %.1f %%" % (100 * min(sl), 100 * st.median(sl), 100 * max(sl)),
      "; windows >= post rate:", sum(x >= rate(post) for x in sl))
