"""Print aux_compare_ci.py JSON: per group / head / metric the variants' point values and the paired differences with 95% CIs.
    python show_cmp_ci.py OUT.json [group ...]     (default: all gt128 le128; '*' marks a CI that excludes 0)"""
import json
import sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
print({k: r[k] for k in ("new_step", "val_rows", "matches", "rows", "boot", "auc_boot", "seconds")})
groups = sys.argv[2:] or ["all", "gt128", "le128"]
order = ["sum_all", "sum_main", "swing", "vpe", "cyc_el", "opp_el10", "opp_el_now", "threat", "commit", "rk_dmg", "opp_hand",
         "xb_lock", "cyc", "opp_next"]


def f(d, nd=4):
    return "-" if d is None else f"{d['point']:+.{nd}f} [{d['ci'][0]:+.{nd}f},{d['ci'][1]:+.{nd}f}]" if d["ci"][0] is not None else f"{d['point']:+.{nd}f} [-]"


def star(d):
    return " " if d is None or d["ci"][0] is None else ("*" if d["ci"][0] > 0 or d["ci"][1] < 0 else " ")


for g in groups:
    print(f"\n== {g}: {r['rows'][g]} rows   (loss: lower better; others higher better)")
    rows = [x for x in r["summary"] if x["group"] == g]
    for h in order:
        for x in sorted((x for x in rows if x["head"] == h), key=lambda x: (x["metric"] != "loss", x["metric"])):
            pt = lambda t: f"{x[t]['point']:.4f}" if t in x else "   -  "
            d = x.get("new-old")
            pb = f" p_better={d['p_better']:.2f}" if d and d.get("p_better") is not None else ""
            print(f"{h:10s} {x['metric']:9s} n={x.get('n')} m={x.get('matches')}{'(CI?)' if (x.get('matches') or 99) < 20 else ''} old {pt('old')} old256 {pt('old256')} new128 {pt('new128')} new {pt('new')} | "
                  f"new-old {f(d)}{star(d)}{pb} | old256-old {f(x.get('old256-old'))}{star(x.get('old256-old'))} | "
                  f"new-old256 {f(x.get('new-old256'))}{star(x.get('new-old256'))} | new-new128 {f(x.get('new-new128'))}{star(x.get('new-new128'))}")
