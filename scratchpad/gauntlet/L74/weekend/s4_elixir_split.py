"""S4: re-split the rocket_tower fork (old live model, seeds 0:240 evo + lad) by OUR elixir at the root, >= 8 vs < 8.
python s4_elixir_split.py RUN_DIR[,RUN_DIR] OUT.txt   (rec["elixir"] = the decision board's my_elixir, logged by mech_fork)"""
import sys
from pathlib import Path
from wk_stats import load, win, tdiff, cr_mean, fmt

rows = load(sys.argv[1])
opps = [(r["_cl"], o) for r in rows for o in r["mech"]["opps"]]
L = [f"S4 rocket_tower fork re-split by own elixir at the moment: {len(rows)} matches, {len(opps)} opportunities"]
if not opps or "elixir" not in opps[0][1]:
    L.append("elixir was NOT logged in these records: split not possible")
else:
    for lab, f in (("elixir >= 8", lambda o: o["elixir"] >= 8), ("elixir < 8", lambda o: o["elixir"] < 8), ("all", lambda o: True)):
        sel = [(c, o) for c, o in opps if f(o)]
        cl = [c for c, _ in sel]
        fk = lambda o: "Bres" in o
        w = cr_mean([(win(o["Bres"]) - win(o["Ares"])) if fk(o) else 0.0 for _, o in sel], cl)
        t10 = cr_mean([(tdiff(o["Bres"], "10") - tdiff(o["Ares"], "10")) if fk(o) else 0.0 for _, o in sel], cl)
        t20 = cr_mean([(tdiff(o["Bres"], "20") - tdiff(o["Ares"], "20")) if fk(o) else 0.0 for _, o in sel], cl)
        L.append(f"{lab:12s} n {len(sel):4d} forked {sum(fk(o) for _, o in sel):4d} | win B - A {fmt(w, 4)} | tower diff @10 {fmt(t10, 0)} @20 {fmt(t20, 0)}")
    hi = [(c, o) for c, o in opps if o["elixir"] >= 8]
    wh = cr_mean([(win(o["Bres"]) - win(o["Ares"])) if "Bres" in o else 0.0 for _, o in hi], [c for c, _ in hi])
    lo = [(c, o) for c, o in opps if o["elixir"] < 8]
    wl = cr_mean([(win(o["Bres"]) - win(o["Ares"])) if "Bres" in o else 0.0 for _, o in lo], [c for c, _ in lo])
    L.append("VERDICT: elixir>=8 win B-A %s, elixir<8 %s; the late-game tower Rocket %s at high elixir" % (
        "n/a" if wh[0] is None else round(wh[0], 4), "n/a" if wl[0] is None else round(wl[0], 4),
        "still loses (CI < 0)" if wh[1] is not None and wh[0] + wh[1] < 0 else "does not clearly lose"))
Path(sys.argv[2]).write_text("\n".join(L) + "\n")
print("\n".join(L))
