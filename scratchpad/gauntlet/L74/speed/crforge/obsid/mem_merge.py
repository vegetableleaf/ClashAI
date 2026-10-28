"""LOOP-MEM: sum mem_par.sh's per-process obs_id.py JSONs (part*.json) -> OUTDIR/merged.json + a short summary on stdout.
usage: python -I mem_merge.py OUTDIR"""
import json
import sys
from pathlib import Path


def main():
    d = Path(sys.argv[1])
    parts = [json.loads(p.read_text()) for p in sorted(d.glob("part*.json"))]
    keys, diag, stats, tabs = {}, {}, {}, {}
    for j in parts:
        for k, r in j["keys"].items():
            m = keys.setdefault(k, dict(rows=0, equal=0, not_ported=0, first_diffs=[]))
            for x in ("rows", "equal", "not_ported"):
                m[x] += r[x]
            m["first_diffs"] += r["first_diffs"][:2]
        for k, v in j["diag"].items():
            diag[k] = diag.get(k, 0) + v
        for k, v in j["memory"]["stats"].items():
            stats[k] = stats.get(k, 0) + v
        for k, r in j["memory"]["tables"].items():
            m = tabs.setdefault(k, dict(tables=0, equal=0, first_diffs=[]))
            m["tables"] += r["tables"]; m["equal"] += r["equal"]; m["first_diffs"] += r["first_diffs"][:2]
    status = {k: "NOT_PORTED" if r["not_ported"] == r["rows"] else "IDENTICAL" if r["equal"] == r["rows"] else "DIFF"
              for k, r in keys.items()}
    rows = sum(j["seat_rows"] for j in parts)
    mem = [k for k in status if k.startswith("mem_")]
    n = max(diag.get("mem_rows_events", 0), 1)
    out = dict(parts=len(parts), matches=sum(j["matches"] for j in parts), skipped=sum((j["skipped"] for j in parts), []),
               seat_rows=rows, tick_mismatch=sum(j["tick_mismatch"] for j in parts), status_by_key=status,
               mem_identical=all(status[k] == "IDENTICAL" for k in mem) and len(mem) == 6,
               tables_identical=bool(tabs) and all(r["equal"] == r["tables"] for r in tabs.values()),
               memory_stats=stats, tables=tabs, diag=diag, keys=keys,
               us_per_row={k: round(diag[f"mem_{k}_ns"] / rows / 1e3, 1) for k in ("py", "java_obs", "java_feat", "jcall")},
               mean_visible_events_per_row_with_events=round(diag.get("mem_events", 0) / n, 1),
               facade_src_sha256=parts[0].get("facade_src_sha256") if parts else None)
    (d / "merged.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("parts", "matches", "skipped", "seat_rows", "tick_mismatch", "mem_identical",
                                          "tables_identical", "memory_stats", "us_per_row",
                                          "mean_visible_events_per_row_with_events")}, default=str))
    print(json.dumps({k: v for k, v in status.items() if v != "IDENTICAL"}))


if __name__ == "__main__":
    main()
