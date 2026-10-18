import json, sys
rows = [r for r in map(json.loads, open(sys.argv[1], encoding="utf-8")) if r.get("type") == "update"]
print("updates", rows[0]["update"], "..", rows[-1]["update"], "n", len(rows))
for k in ("kl_gate", "kl_card", "kl_cell"):
    v = [(r.get(k, 0), r["update"]) for r in rows]; print(k, "max", max(v))
print("first update with beta_used at floor:", next(r["update"] for r in rows if abs(r.get("beta_used", 1) - 0.03) < 1e-9))
