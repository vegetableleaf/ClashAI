"""Print the CXXXVIII match sequence: ts, start trophies (rolled estimate), result, delta, class, opp card level, duration."""
import json
R = json.load(open(__file__.replace("timeline.py", "cohort_rows.json")))
for r in R:
    if r["mark"] == "CXXXVIII":
        print(r["ts"][9:15], r["start"], r["result"][0], f"{r['delta']:+d}", (r["_cls"] or "")[:12], f"{r['opp_card_lv'] or 0:.2f}", r["opp_tower_lv"], int(r["dur_s"]), sep=" ")
