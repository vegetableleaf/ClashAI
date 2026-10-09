"""Markdown per-drill table from out/baseline.json (CATALOG.md's numbers).  python table.py > out/table.md"""
import json
B = json.load(open(__file__.replace("table.py", "out/baseline.json")))
G = [g for g in ("live_current", "live_deployed", "pros", "sim") if g in B]
KINDS = (("do", "DO"), ("do_kill6", "DO (kill>=6)"), ("do_combo", "DO combo (D6b)"), ("hold", "HOLD"))
print("| drill | score | " + " | ".join(f"{g} n | {g} pass % [95% CI]" for g in G) + (" | SIM per 960 matches |" if "sim" in B else " |"))
print("|---|---|" + "---|---|" * len(G) + ("---|" if "sim" in B else ""))
for dr in sorted({d for g in G for d in B[g]["drills"]}):
    for k, lab in KINDS:
        cells, any_ = [], False
        for g in G:
            e = B[g]["drills"].get(dr, {}).get(k)
            if e: any_ = True; cells += [str(e["n"]), f"{e['pass_pct']:.1f} [{e['ci'][0]:.0f}, {e['ci'][1]:.0f}]"]
            else: cells += ["0", "-"]
        if not any_: continue
        tail = ""
        if "sim" in B:
            e = B["sim"]["drills"].get(dr, {}).get(k)
            tail = f" {round(e['n'] / B['sim']['matches'] * 960) if e else 0} |"
        print(f"| {dr} | {lab} | " + " | ".join(cells) + " |" + tail)
print()
print("matches / minutes: " + ", ".join(f"{g} {B[g]['matches']} / {B[g]['minutes']}" for g in G))
