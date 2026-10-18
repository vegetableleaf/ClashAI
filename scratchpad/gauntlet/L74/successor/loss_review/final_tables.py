"""Per-archetype trophies lost per match (unfloored loss price) for CXXXVIII >= 13,000 and CXXIV last 200; cohort reconciliation."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze as A
rows = sorted(A.load(), key=lambda r: r["ts"])
lad = A.ladder()
since = [k for k in lad if k[10:25] >= A.SWITCH]
print("ladder results for logs since 13:29:", len(since), "| in cohort:", sum(1 for r in rows if r["mark"] == "CXXXVIII" and r["ts"] >= A.SWITCH),
      "| missing:", sorted(k[10:25] for k in since if k not in {r["file"] for r in rows}))
C124 = [r for r in rows if r["mark"] == "CXXIV" and r["ts"] < A.SWITCH][-200:]
C138 = [r for r in rows if r["mark"] == "CXXXVIII" and r["ts"] >= A.SWITCH]
for name, Q in (("CXXXVIII >= 13,000", [r for r in C138 if r["start"] >= 13000]), ("CXXXVIII all", C138), ("CXXIV last 200", C124)):
    n = len(Q); pw = A.mean([r["delta"] for r in Q if r["result"] == "WIN"]); pl = A.mean([r["delta"] for r in Q if r["result"] == "LOSS" and r["delta"] <= -20])
    print(f"\n== {name}: {n} matches; win price {pw:+.1f}, unfloored loss price {pl:.1f}; break-even win rate {-pl / (pw - pl):.1%}; "
          f"unfloored trophies/match {A.mean([pw if r['result'] == 'WIN' else pl for r in Q]):+.2f} (logged {A.mean([r['delta'] for r in Q]):+.2f})")
    g = collections.defaultdict(list)
    for r in Q: g[r["_cls"]].append(r)
    for k, v in sorted(g.items(), key=lambda kv: -sum(r["result"] == "LOSS" for r in kv[1])):
        w = sum(r["result"] == "WIN" for r in v); l = len(v) - w
        rest = [r for r in Q if r["_cls"] != k]; wr = A.mean([r["result"] == "WIN" for r in rest])
        print(f"   {k[:28]:28s} n {len(v):3d} W-L {w:2d}-{l:2d} win {w / len(v):5.1%} | trophies lost to it per match {l * -pl / n:5.2f} | "
              f"net {(w * pw + l * pl) / n:+5.2f} | recovered if it won like the rest ({wr:.0%}): {max(0, (wr - w / len(v))) * len(v) / n * (pw - pl):+5.2f}")
