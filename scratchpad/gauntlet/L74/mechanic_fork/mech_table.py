"""Compact 6-job table from the per-job mech_summary --json outputs (s_<mech>_<census>.json) + matches.jsonl."""
import json, sys
from pathlib import Path
R = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
f = lambda v, nd=0, pc=False: "n/a" if v is None else (f"{v[0]*100:+.1f}pp +/-{v[1]*100:.1f}" if pc else f"{v[0]:+.{nd}f} +/-{v[1]:.{nd}f}")
rows = []
for m in ("sneaky", "rocket_tower", "patience"):
    for c in ("evo", "lad"):
        d = json.loads((R / f"s_{m}_{c}.json").read_text())
        b = d["B_minus_A"]["forked"] if "forked" in d["B_minus_A"] else d["B_minus_A"]
        opps = [json.loads(l) for l in (R / f"full_{m}_{c}_0_240" / "matches.jsonl").read_text().splitlines() if l.strip()]
        o = [x for r in opps for x in r["mech"]["opps"] if "Bres" in x]
        wa = sum(x["Ares"]["outcome"] == "win" for x in o) / len(o); wb = sum(x["Bres"]["outcome"] == "win" for x in o) / len(o)
        rows.append((m, c, d["matches"], d["opportunities"], d["skipped_unsnapshottable"], d["B_root_play"]["accepted"], d["B_root_play"]["n"],
                     f(b["tower_diff@10"]), f(b["tower_diff@20"]), f(b["tower_diff@end"]), f(b["win@end"], pc=True), f"{wa:.3f}->{wb:.3f}", d["faithfulness"]["n"], d["faithfulness"]["hash_equal_end"]))
print("| mech | census | matches | opps | skipped | B root accepted | tower diff +10s | +20s | end | win B-A (95% CI half-width) | win A->B | A-replay hash eq end |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]}/{r[6]} | {r[7]} | {r[8]} | {r[9]} | {r[10]} | {r[11]} | {r[13]}/{r[12]} |")
