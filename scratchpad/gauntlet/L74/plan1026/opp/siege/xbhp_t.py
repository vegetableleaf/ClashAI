"""OPP-SIEGE2: our X-Bow's own HP after landing (hab s[7]) and tower time, on-time unit answers vs all, per source;
lock by X-Bow life bins.  python -I xbhp_t.py NAME=DIR ...  (needs out/siege_t_NAME.json for the uid + class)"""
import json, statistics as st, sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[3] / "succ48")]
import xbow_count as XC  # noqa: E402
for a in sys.argv[1:]:
    n, d = a.split("=", 1)
    recs = {(r["id"], r["t"]): r for r in json.load(open(f"out/siege_t_{n}.json"))["xbows"] if r.get("xb_uid") is not None}
    U = {}
    for r, h in XC.rows(d):
        for s in h["samples"]:
            for e in s[7]:
                U.setdefault(e[0], []).append((s[0], e[1]))
    rows = []
    for r in recs.values():
        ser = U.get(r["xb_uid"], [])
        if not ser:
            continue
        hp0 = ser[0][1]
        at = lambda dt: next((hp for t, hp in reversed(ser) if t <= r["t"] + dt), 0) / hp0 if r["t"] + dt <= ser[-1][0] + 20 else 0.0  # noqa: E731
        rows.append((r, at(100), at(200), at(300), r["xb_life"], r["tower_share"] * r["xb_life"]))
    for g, f in (("all", lambda r: True), ("ontime_unit", lambda r: r["cls"] == "answer_ontime" and r["kind"] != "spell")):
        s = [x for x in rows if f(x[0])]
        print(f"{n:6s} {g:11s} n {len(s)} X-Bow HP share at +5/+10/+15 s: " + " / ".join(f"{st.mean(x[i] for x in s):.2f}" for i in (1, 2, 3))
              + f" | tower ticks median {st.median(x[5] for x in s):.0f} | lock by life <200 / 200-400 / >400 ticks: " + " ".join(
                  f"{len(b) / len(s):.2f} ({sum(b) / max(1, len(b)):.2f})" for b in ([x[0]['locked'] for x in s if lo <= x[4] < hi] for lo, hi in ((0, 200), (200, 400), (400, 9999)))))
