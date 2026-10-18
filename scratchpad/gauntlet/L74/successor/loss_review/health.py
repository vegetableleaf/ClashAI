"""Live pipeline health by band: is the >= 13,000 drop a system slowdown (shared laptop) rather than opponents?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze as A
mean, med = A.mean, A.V.med
rows = sorted(A.load(), key=lambda r: r["ts"])
C124 = [r for r in rows if r["mark"] == "CXXIV" and r["ts"] < A.SWITCH][-200:]
C138 = [r for r in rows if r["mark"] == "CXXXVIII" and r["ts"] >= A.SWITCH]
for name, Q in (("CXXIV < 12,500", [r for r in C124 if r["start"] < 12500]), ("CXXIV >= 12,500", [r for r in C124 if r["start"] >= 12500]),
                ("CXXXVIII < 13,000", [r for r in C138 if r["start"] < 13000]), ("CXXXVIII >= 13,000", [r for r in C138 if r["start"] >= 13000])):
    lat = [x for r in Q for x in r.get("lat_s") or []]; err = [x for r in Q for x in r.get("err_tiles") or []]
    print(f"{name:20s} n {len(Q):3d} | cpu_starved/match {mean([r['starved'] for r in Q]):.2f} (>=3: {mean([r['starved'] >= 3 for r in Q]):.0%}) | decide_ms med {mean([r['decide_ms_med'] for r in Q]):.0f} "
          f"| backlog share {mean([r['backlog_share'] for r in Q]):.3f} | tap_ms med {mean([r['tap_ms_med'] for r in Q]):.0f} | confirm latency med {med(lat):.2f} s | err >= 1 tile {mean([e >= 1 for e in err]):.1%} "
          f"| unconfirmed/match {mean([r['n_unconf'] for r in Q]):.2f} | plays/match {mean([r['n_plays'] for r in Q]):.1f} conf {mean([r['n_conf'] for r in Q]):.1f} | pending {mean([r['pending_plays'] for r in Q]):.2f} "
          f"| reader_closed {mean([r['reader_closed'] for r in Q]):.2f} | forced {mean([r['forced'] for r in Q]):.2f}")
