"""Merge actor_obscheck's per-actor JSONs: per key rows / equal / status; skipped / errors / diag summed.
    python obscheck_sum.py DIR [OUT.json]"""
import json
import sys
from pathlib import Path

keys, skip, err, diag, tot = {}, {}, {}, {}, dict(seat_rows=0, tick_mismatch=0, actors=0, batches=0)
for p in sorted(Path(sys.argv[1]).glob("*.json")):
    r = json.loads(p.read_text())
    tot["actors"] += 1
    for k in ("seat_rows", "tick_mismatch", "batches"):
        tot[k] += int(r[k])
    for src, dst in ((r["skipped"], skip), (r["errors"], err), (r["diag"], diag)):
        for k, v in src.items():
            dst[k] = dst.get(k, 0) + int(v)
    for k, v in r["keys"].items():
        a = keys.setdefault(k, dict(rows=0, equal=0, not_ported=0, dtype_shape_diff=0, first_diffs=[]))
        for x in ("rows", "equal", "not_ported", "dtype_shape_diff"):
            a[x] += int(v[x])
        a["first_diffs"] += v["first_diffs"][:max(0, 3 - len(a["first_diffs"]))]
for a in keys.values():
    a["status"] = ("NOT_PORTED" if a["not_ported"] == a["rows"] else "IDENTICAL" if a["equal"] == a["rows"] else "DIFF")
out = dict(**tot, skipped=skip, errors=err, diag=diag,
           status_by_key={k: f'{v["status"]} {v["equal"]}/{v["rows"]}' for k, v in sorted(keys.items())}, keys=keys)
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("actors", "batches", "seat_rows", "tick_mismatch", "skipped", "errors",
                                      "status_by_key")}, indent=1))
