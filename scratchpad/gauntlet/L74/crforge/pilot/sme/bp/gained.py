"""Gained / lost exact matches and per-match changes between two runs. python3 gained.py RUN_A RUN_B"""
import json, os, sys
flags = {json.loads(l)["match"]: json.loads(l)["flags"] for l in open("/workspace/pilot/inputs/inputs_rngfree.jsonl")}
L = lambda r: {x["match"]: x for x in map(json.loads, open(os.path.join(r, "results.jsonl")))}  # noqa: E731
ex = lambda rs: {m for m, r in rs.items() if not flags.get(m) and "error" not in r and r["counts"].get("div", 0) == 0 and r["missing_in_sim"] == 0}  # noqa: E731
a, b = L(sys.argv[1]), L(sys.argv[2])
print("gained", sorted(m[10:] for m in ex(b) - ex(a)), "lost", sorted(m[10:] for m in ex(a) - ex(b)))
for m in a:
    if m in b and not flags.get(m) and "error" not in a[m] and "error" not in b[m]:
        x, y = (a[m].get("first_div"), a[m]["counts"].get("exact")), (b[m].get("first_div"), b[m]["counts"].get("exact"))
        if x != y:
            print("  changed", m[10:], "first", x[0], "->", y[0], "exact", x[1], "->", y[1])
