"""Overtime anatomy by band: tower-damage balance entering OT (1x + 2x taken vs dealt), what the bot did in OT, by result.
Also CXXIV's win rate by time of day (is the evening pool harder?)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze as A
mean = A.mean
rows = sorted(A.load(), key=lambda r: r["ts"])
C124 = [r for r in rows if r["mark"] == "CXXIV" and r["ts"] < A.SWITCH][-200:]
C138 = [r for r in rows if r["mark"] == "CXXXVIII" and r["ts"] >= A.SWITCH]
win = lambda r: r["result"] == "WIN"
def pre(r, k): return sum((r["dmg"].get(p) or {}).get(k, 0) for p in ("1x", "2x"))
for name, Q in (("CXXIV last 200", C124), ("CXXXVIII < 13,000", [r for r in C138 if r["start"] < 13000]), ("CXXXVIII >= 13,000", [r for r in C138 if r["start"] >= 13000])):
    ot = [r for r in Q if r["dur_s"] >= 186]
    print(f"== {name}: {len(ot)} OT matches")
    for lab, f in (("entering OT ahead on tower damage (dealt - taken >= +300)", lambda r: pre(r, "dealt") - pre(r, "taken") >= 300),
                   ("level (|diff| < 300)", lambda r: abs(pre(r, "dealt") - pre(r, "taken")) < 300),
                   ("behind (<= -300)", lambda r: pre(r, "dealt") - pre(r, "taken") <= -300)):
        S = [r for r in ot if f(r)]
        if S: print(f"   {lab:58s} n {len(S):2d} win {A.wil(sum(map(win, S)), len(S))}")
    for res in ("WIN", "LOSS"):
        S = [r for r in ot if r["result"] == res]
        if not S: continue
        ox = mean([sum(1 for x in r["xbows"] if x["lock"] and x["ph"] == "OT") for r in S]); orr = mean([sum(1 for s in r["spells"] if s["name"] == "Rocket" and s["ph"] == "OT") for r in S])
        ort = mean([sum(1 for s in r["spells"] if s["name"] == "Rocket" and s["ph"] == "OT" and s.get("tower")) for r in S])
        oth = [e for r in S for e in r["threats"] if e["ph"] == "OT"]
        for e in oth: e["bad"] = e["hp_lost"] >= 1000 or e["tower_fell"]
        print(f"   OT {res}: n {len(S)}; OT length {mean([r['dur_s'] - 180 for r in S]):.0f} s; locked X-Bows in OT {ox:.2f}, Rockets in OT {orr:.2f} (on a tower {ort:.2f}); "
              f"OT pushes {len(oth) / len(S):.1f}/match lost {mean([e['bad'] for e in oth]):.0%}, own elixir at OT push {A.V.med([e['el'] for e in oth]) or 0:.1f}; "
              f"OT taken/dealt {mean([r['dmg'].get('OT', {}).get('taken') for r in S]):.0f}/{mean([r['dmg'].get('OT', {}).get('dealt') for r in S]):.0f}; "
              f"enemy lowest tower at end {A.V.med([(r.get('tiebreak_min') or {}).get('opp') for r in S])}")
print("\n== CXXIV all ladder matches by hour of day (time-of-day pool check) and trophies")
allc = [r for r in rows if r["mark"] == "CXXIV"]
g = collections.defaultdict(list)
for r in allc: g[(r["ts"][:8], int(r["ts"][9:11]) // 4 * 4)].append(r)
for k in sorted(g):
    v = g[k]; st = [r["start"] for r in v if r["start"]]
    print(f"   {k[0]} {k[1]:02d}-{k[1] + 3:02d}h n {len(v):3d} win {A.wil(sum(map(win, v)), len(v)):22s} trophies {min(st) if st else '-'}..{max(st) if st else '-'}")
