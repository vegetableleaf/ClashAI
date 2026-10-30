"""SPEED2: markdown rows from srvshape.py JSON files. usage: python tab.py FILE.json [...]  (several files of one
multi-server run: pass them with --sum to add their rows/s)."""
import json
import sys

files = [f for f in sys.argv[1:] if not f.startswith("--")]
rows = [(json.load(open(f))["mode"], r) for f in files for r in json.load(open(f))["rows"]]
if "--sum" in sys.argv:
    m, r0 = rows[0]
    tot = sum(r["rows_per_s"] for _, r in rows)
    print(f"| {len(rows)} servers x {r0['K']}x{r0['producers']}, {m} | {tot:,} (" + " + ".join(f"{r['rows_per_s']:,}" for _, r in rows)
          + ") | " + " / ".join(f"{r['round_ms']:.0f}" for _, r in rows) + " | "
          + " / ".join(f"{r['per_round_ms']['fwd']:.0f}" for _, r in rows) + " | "
          + " / ".join(f"{r['per_round_ms']['cell']:.0f}" for _, r in rows) + " | "
          + " / ".join(f"{r['server_cpu_frac']:.2f}" for _, r in rows) + " |")
else:
    for m, r in rows:
        c = r["server_thread_cpu_s"]
        fpb = 1000 * c.get("_fwd_loop", 0) / max(1e-9, r["batches_per_s"] * r["window_s"])
        cpc = 1000 * c.get("_cell_loop", 0) / max(1e-9, r["cell_calls_per_s"] * r["window_s"])
        print(f"| {r['K']}x{r['producers']} {m} | {r['rows_per_s']:,} | {r['round_ms']:.0f} | {r['per_round_ms']['fwd']:.0f} | "
              f"{r['per_round_ms']['cell']:.0f} | {r['per_round_ms']['decide'] - r['per_round_ms']['cell']:.0f} | "
              f"{r['server_cpu_frac']:.2f} | {fpb:.1f} | {cpc:.1f} | {r['batches_per_s']:.0f} | {r['mean_batch']['learner']:.0f} / "
              f"{r['mean_batch']['init']:.0f} |")
