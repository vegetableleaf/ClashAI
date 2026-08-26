"""Append verified finding rows (JSON via stdin, a list) to r2_evos_b.jsonl and keep tallies."""
import json, sys, os
LEDGER = "C:/Users/benpe/ClashBot/research/sim_parity/ledger"
OUT = os.path.join(LEDGER, "r2_evos_b.jsonl")
TALLY = os.path.join(LEDGER, "r2_evos_b_tally.json")

payload = json.load(sys.stdin)          # {"key":..., "fields_checked":N, "matches":N, "rows":[...]}
rows = payload["rows"]
with open(OUT, "a", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
t = {"keys": [], "fields_checked": 0, "matches": 0, "updates": 0, "pins": 0,
     "escalations": 0, "match_only_rows": 0}
if os.path.exists(TALLY):
    t = json.load(open(TALLY))
t["keys"].append(payload["key"])
t["fields_checked"] += payload["fields_checked"]
t["matches"] += payload["matches"]
for r in rows:
    v = r["verdict"]
    if v == "update": t["updates"] += 1
    elif v == "pin": t["pins"] += 1
    elif v == "escalate": t["escalations"] += 1
    elif v == "match": t["match_only_rows"] += 1
json.dump(t, open(TALLY, "w"), indent=1)
print("appended", len(rows), "rows for", payload["key"], "| tally:",
      {k: v for k, v in t.items() if k != "keys"})
