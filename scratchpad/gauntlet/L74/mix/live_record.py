"""Live W/L per checkpoint on the icebow main account (result inference = live_cost.one: last decision's towers).
    python live_record.py [--since 20261015_0000]
"""
import argparse, collections, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_cost import LOGS, one  # noqa: E402

NAMES = {"fce50ebb": "r1", "693889c3": "F1 s74 u65", "4987c582": "F1 s76", "00c845c0": "F1 u250"}
ap = argparse.ArgumentParser(); ap.add_argument("--since", default="20261015_0000"); a = ap.parse_args()
S = collections.defaultdict(lambda: [0, 0])
for f in sorted(glob.glob(LOGS + "live_play_2026*.jsonl")):
    if os.path.basename(f)[10:25] < a.since:
        continue
    with open(f, encoding="utf-8", errors="replace") as fh:
        h = json.loads(fh.readline())
    if h.get("dry_run"):
        continue
    r = one(f)
    if r is not None:
        S[NAMES.get(str(h.get("ckpt_sha256", ""))[:8], str(h.get("ckpt_sha256", ""))[:8])][1 - r[1]] += 1
for k, (w, l) in S.items():
    n = w + l; p = w / n; se = (p * (1 - p) / n) ** .5
    print(f"{k:12} {w}W-{l}L  {100*p:.1f}% [{100*(p-1.96*se):.1f}, {100*(p+1.96*se):.1f}]  n {n}")
