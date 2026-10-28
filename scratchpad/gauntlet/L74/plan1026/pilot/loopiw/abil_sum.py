"""Merge actor_abil's per-actor JSONs: per check rows / equal / first diffs; totals; cost per seat-row.
    python abil_sum.py DIR [OUT.json]"""
import json
import sys
from pathlib import Path

keys, err, tot = {}, {}, {}
for p in sorted(Path(sys.argv[1]).glob("*.json")):
    r = json.loads(p.read_text())
    tot["actors"] = tot.get("actors", 0) + 1
    for k, v in r.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and k != "pid":
            tot[k] = tot.get(k, 0) + v
    tot.setdefault("exact", set()).add(r.get("exact"))
    tot.setdefault("selftest", []).append(r.get("selftest"))
    for k, v in r["errors"].items():
        err[k] = err.get(k, 0) + v
    for k, v in r["keys"].items():
        a = keys.setdefault(k, dict(calls=0, equal=0, nonempty=0, first_diffs=[]))
        for x in ("calls", "equal", "nonempty"):
            a[x] += v.get(x, 0)
        a["first_diffs"] += v["first_diffs"][:max(0, 3 - len(a["first_diffs"]))]
tot["exact"] = sorted(map(str, tot.get("exact", [])))
tot["selftest"] = [s for s in tot.get("selftest", []) if s][:1] + [len([s for s in tot.get("selftest", []) if s])]
if tot.get("seat_rows"):
    tot["py_us_per_seat_row"] = round(tot["py_ns"] / tot["seat_rows"] / 1e3, 2)
    tot["java_us_per_seat_row_incl_jpype"] = round(tot["java_ns"] / tot["seat_rows"] / 1e3, 2)
    tot["java_us_per_seat_row_in_jvm"] = round(tot.get("java_nanos", 0) / tot["seat_rows"] / 1e3, 2)
out = dict(**tot, errors=err, status={k: f'{"IDENTICAL" if v["equal"] == v["calls"] else "DIFF"} {v["equal"]}/{v["calls"]} '
                                         f'(nonempty {v["nonempty"]})' for k, v in sorted(keys.items())}, keys=keys)
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "keys"}, indent=1)[:6000])
